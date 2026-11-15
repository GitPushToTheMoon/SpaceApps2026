"""Stowage Fire-Risk Planner endpoints: GET /library, POST /api/assess, POST /api/chat.

Who decides what:
  scores, levels, factors, fix/move points, valid actions -> code (scoring.py, actions.py)
  summary, room rationales, fix reasons, chat replies     -> Gemini, number-checked
If Gemini is down or gets a number wrong (twice), /api/assess still answers with plain
template text ("text_source": "template"); /api/chat answers 503.
"""
import hashlib
import json
import os
import re
import time
from collections import OrderedDict
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

from fastapi import APIRouter, HTTPException

from . import actions, adapter, ai, data, risk, scoring
from .api_schemas import AssessRequest, AssessResponse, ChatRequest, ChatResponse

router = APIRouter()

FACTORS = [  # scoring.WEIGHTS keys, in display order
    ("material", "Material hazard (NASA test data)"),
    ("fuel", "Fuel load"),
    ("sources", "Ignition & oxygen sources"),
    ("airflow", "Airflow"),
    ("thickness", "Material thickness"),
]
FACTOR_WORDS = {"material": "material hazard (NASA test data)", "fuel": "fuel load",
                "sources": "ignition and oxygen sources", "airflow": "airflow",
                "thickness": "material thickness"}
NOT_SCORED = ("Not in the score yet: cabin pressure, EVA-prep periods, machinery heat and "
              "Li-ion bagging. They are shown for context only.")
CACHE_SIZE = 64
LOG_PATH = Path(os.environ.get("ASSESSMENT_LOG", data.DATA_DIR / "assessments.jsonl"))
HISTORY_TURNS = 10

_cache: "OrderedDict[str, dict]" = OrderedDict()


# ------------------------------------------------------------------ helpers

def input_hash(req: dict) -> str:
    return hashlib.sha256(json.dumps(req, sort_keys=True, separators=(",", ":")).encode()).hexdigest()[:16]


def _band(values: List[float]) -> dict:
    if not values:
        return {"avg": 0.0, "min": 0.0, "max": 0.0}
    return {"avg": round(sum(values) / len(values), 1), "min": min(values), "max": max(values)}


def _gravity(req: dict) -> float:
    surf = req["conditions"].get("surface")
    return float(surf["gravity_g"]) if surf else 0.0


def _log(entry: dict) -> None:
    """Keep every assessment with its input so M&P can trace each rating."""
    try:
        LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with LOG_PATH.open("a") as f:
            f.write(json.dumps(entry) + "\n")
    except OSError as e:
        print(f"[api] could not write assessment log: {e}")


# ------------------------------------------------------------------ facts for the AI

_DID_NOT_BURN = {"self-extinguished", "no ignition", "no spread", "blowoff"}


def nasa_data_summary() -> List[dict]:
    """What our dataset actually contains, per material (verified rows only), so the AI can
    quote real test counts, investigations and oxygen ranges instead of guessing."""
    df = data.load_experiments()
    profiles = scoring.material_profiles()
    out = []
    for mat, rows in df.groupby(df["material"].fillna("")):
        if not mat:
            continue
        o2 = rows[["oxygen_pct_min", "oxygen_pct_max"]]
        prof = profiles.get(mat.lower(), {})
        out.append({
            "material": mat,
            "tests": int(len(rows)),
            "by_investigation": {k: int(v) for k, v in rows.groupby("investigation").size().items()},
            "oxygen_tested_pct": [float(o2.min().min()), float(o2.max().max())],
            "burned": int(rows["outcome_category"].isin(["burned", "ignited"]).sum()),
            "did_not_burn": int(rows["outcome_category"].isin(_DID_NOT_BURN).sum()),
            "threshold_pct": round(prof["threshold_pct"], 1) if prof.get("threshold_pct") is not None else None,
            "threshold_basis": prof.get("basis"),
        })
    tested = {m["material"].lower() for m in out}
    for lib in data.load_library():  # PSI materials we list but have no verified tests for
        mk = lib.get("material_key")
        if mk and mk.lower() not in tested:
            out.append({"material": mk, "tests": 0, "note": "listed in the PSI materials, no verified tests yet"})
    return out


TESTS_PER_OUTCOME = 3          # per material: closest burned / did-not-burn tests to each phase's oxygen
_ID_RE = re.compile(r"\bPSI-\d+-[A-Za-z0-9]+(?:-[A-Za-z0-9]+)*\b")
_URL_RE = re.compile(r"https?://[^\s)\]]+")


def _clip(text, n: int):
    text = "" if text is None or (isinstance(text, float) and text != text) else str(text)
    return text if len(text) <= n else text[: n - 1].rstrip() + "…"


def cited_tests(oxygen_levels: List[float]) -> List[dict]:
    """Individual verified experiments the chatbot may cite, per material:
    the tests that set the burn threshold (lowest burn, highest went-out) plus the closest
    burned and did-not-burn tests to each phase's oxygen. Every field comes from the CSV."""
    df = data.load_experiments().copy()
    df["_o2"] = df[["oxygen_pct_min", "oxygen_pct_max"]].mean(axis=1)
    burned = df["outcome_category"].isin(["burned", "ignited"])
    went_out = df["outcome_category"].isin(_DID_NOT_BURN)
    picked = []
    for mat, rows in df[df["material"].notna()].groupby("material"):
        ids = []
        rows = rows[rows["_o2"].notna()]  # tests without a reported oxygen level can't be compared
        b, w = rows[burned.loc[rows.index]], rows[went_out.loc[rows.index]]
        if not b.empty:
            ids.append(b[["oxygen_pct_min", "oxygen_pct_max"]].min(axis=1).idxmin())  # lowest O2 it burned at
        if not w.empty:
            ids.append(w[["oxygen_pct_min", "oxygen_pct_max"]].max(axis=1).idxmax())  # highest O2 it went out at
        for o2 in oxygen_levels:
            for part in (b, w):
                if not part.empty:
                    ids += list((part["_o2"] - o2).abs().nsmallest(TESTS_PER_OUTCOME).index)
        for i in dict.fromkeys(ids):
            r = df.loc[i]
            num = lambda c: None if r[c] != r[c] else float(r[c])  # NaN -> None
            picked.append({
                "id": r["id"], "material": mat, "investigation": r["investigation"],
                "oxygen_pct": [num("oxygen_pct_min"), num("oxygen_pct_max")],
                "pressure_psi": [num("pressure_psi_min"), num("pressure_psi_max")],
                "airflow_cm_s": [num("airflow_cm_s_min"), num("airflow_cm_s_max")],
                "gravity": r["gravity"], "outcome_category": r["outcome_category"],
                "outcome": _clip(r["outcome"], 160), "source_url": r["source_url"],
                "source_quote": _clip(r["source_quote"], 200),
            })
    return picked


def citations_ok(text: str, tests: List[dict]) -> bool:
    """Every experiment id and URL in the text must be one we gave the AI."""
    ids = {t["id"] for t in tests}
    urls = {t["source_url"] for t in tests}
    if any(i not in ids for i in _ID_RE.findall(text or "")):
        return False
    return all(u.rstrip(".,;:") in urls for u in _URL_RE.findall(text or ""))


def citations_in(text: str, tests: List[dict]) -> List[dict]:
    by_id = {t["id"]: t for t in tests}
    out = []
    for i in dict.fromkeys(_ID_RE.findall(text or "")):
        if i in by_id:
            t = by_id[i]
            out.append({"id": i, "material": t["material"], "investigation": t["investigation"],
                        "source_url": t["source_url"]})
    return out


def _sources(space: dict) -> dict:
    """Ignition/oxygen sources in a space, by name (and whether a Li-ion pack is unbagged)."""
    ign = [i["name"] for i in space.get("items") or [] if i.get("ignition_source")]
    oxy = [i["name"] for i in space.get("items") or [] if i.get("oxygen_source")]
    liion = any((data.get_library_item(i.get("key")) or {}).get("li_ion") and not
                (data.get_library_item(i.get("key")) or {}).get("bagged") for i in space.get("items") or [])
    return {"ignition_sources": ign, "oxygen_sources": oxy, "unbagged_li_ion": liion}


def _room_facts(space: dict, scored: dict, names: List[str]) -> dict:
    r = scored["rooms"][space["id"]]
    last = r[names[-1]]
    return {
        "id": space["id"], "name": space["name"], "airflow_cm_s": space["airflow_cm_s"],
        **{p: {"score": r[p]["score"], "level": r[p]["level"], "factors": r[p]["factors"]} for p in names},
        "overall": r["overall"],
        "materials": [{"name": i["name"], "nasa_material": i["material_key"],
                       "nasa_tests": i["n_tests"], "evidence": i["evidence"],
                       "burn_threshold_oxygen_pct": i["threshold_pct"], "basis": i["basis"],
                       "hazard": {p: r[p]["items"][k]["hazard"] for p in names},
                       "gap": i["gap"]} for k, i in enumerate(last["items"])],
        **_sources(space),
    }


def _allowed(*objs) -> Dict[str, List[float]]:
    """Numbers the AI may use: anything in the facts; test counts and percentages in context."""
    nums = []
    for o in objs:
        nums += risk.collect_numbers(o)
    tests, pcts = set(), set()
    pct_keys = {"o2_percent", "oxygen_pct", "threshold_pct", "burn_threshold_oxygen_pct", "oxygen_tested_pct"}
    text_keys = {"basis", "threshold_basis", "gap", "plain", "data_gaps", "not_scored"}

    def walk(o):
        if isinstance(o, dict):
            for k, v in o.items():
                if k in ("tests", "nasa_tests", "n_tests") and isinstance(v, (int, float)) and not isinstance(v, bool):
                    tests.add(float(v))
                elif k == "by_investigation" and isinstance(v, dict):
                    tests.update(float(x) for x in v.values())
                elif k in pct_keys or k in text_keys:
                    pcts.update(risk.collect_numbers(v))
                elif k == "weight" and isinstance(v, (int, float)):
                    pcts.add(round(float(v) * 100, 1))
                walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)
    for o in objs:
        walk(o)
    return {"all": nums, "tests": sorted(tests), "percents": sorted(pcts)}


def _text_ok(t, allowed: Dict[str, List[float]]) -> bool:
    return (isinstance(t, str) and t.strip() != "" and risk.all_numbers_ok(t, allowed["all"])[0]
            and risk.context_numbers_ok(t, allowed["tests"], allowed["percents"])[0]
            and risk.unscored_causes_ok(t)[0])


# ------------------------------------------------------------------ text

def _template(scored: dict, req: dict, fixes: Dict[str, List[dict]]) -> dict:
    phases = scored["phases"]
    names = scored["phase_names"]
    driver = max(names, key=lambda p: phases[p]["score"])
    label = {"cruise": "Cruise", "surf": "Surface"}
    stocked = [(s, scored["rooms"][s["id"]]) for s in req["spaces"] if scored["rooms"][s["id"]]["overall"]]
    if stocked:
        worst_space, worst = max(stocked, key=lambda x: x[1]["overall"])
        summary = (f"{label[driver]} drives the overall score of {scored['overall']['score']:g} "
                   f"({scored['overall']['level']}). The riskiest space is {worst_space['name']} "
                   f"at {worst['overall']:g}.")
    else:
        summary = "No space is stocked yet, so there is nothing to score."
    rooms = {}
    for s, r in stocked:
        room = r[driver]
        top = sorted(room["factors"].items(), key=lambda kv: -kv[1])[:2]
        rooms[s["id"]] = "Main drivers: " + " and ".join(FACTOR_WORDS[k] for k, _ in top) + "."
        if any(i["evidence"] == "none" for i in room["items"]):
            rooms[s["id"]] += " Some items have no NASA test data."
        if _sources(s)["unbagged_li_ion"]:
            rooms[s["id"]] += " Unbagged Li-ion battery present (battery hazard is not scored)."
    return {"summary": summary, "rooms": rooms,
            "fixes": {sid: [f["why"] for f in fl] for sid, fl in fixes.items()}}


def _checked_text(raw: dict, template: dict, allowed: Dict[str, List[float]]) -> Optional[dict]:
    """AI text with every number checked. None = reject (wrong number or missing summary)."""
    def ok(t):
        return _text_ok(t, allowed)

    if not isinstance(raw, dict) or not ok(raw.get("summary")):
        return None
    rooms = dict(template["rooms"])
    for sid, text in (raw.get("rooms") or {}).items():
        if sid in rooms:
            if not ok(text):
                return None
            rooms[sid] = text.strip()
    fixes = {sid: list(w) for sid, w in template["fixes"].items()}
    for sid, whys in (raw.get("fixes") or {}).items():
        if sid in fixes and isinstance(whys, list) and len(whys) == len(fixes[sid]):
            if not all(ok(w) for w in whys):
                return None
            fixes[sid] = [w.strip() for w in whys]
    return {"summary": raw["summary"].strip(), "rooms": rooms, "fixes": fixes}


# ------------------------------------------------------------------ assessment

def build_assessment(req: dict, use_ai: bool = True) -> dict:
    scored = adapter.score(req)
    names = scored["phase_names"]
    fixes = {s["id"]: actions.candidate_fixes(req, s["id"], scored)
             for s in req["spaces"] if scored["rooms"][s["id"]]["overall"]}
    moves = actions.find_moves(req, scored)

    # text: Gemini writes it from code facts; numbers checked; template if it fails
    facts = {
        "conditions": req["conditions"],
        "overall": scored["overall"], "phases": scored["phases"],
        "rooms": [{**_room_facts(sp, scored, names), "fixes": [f["title"] for f in fixes[sp["id"]]]}
                  for sp in req["spaces"] if sp["id"] in fixes],
        "moves": [{"item": m["item"], "from": m["from_name"], "to": m["to_name"]} for m in moves],
        "not_scored": NOT_SCORED,
    }
    template = _template(scored, req, fixes)
    allowed = _allowed(facts, req, [f for fl in fixes.values() for f in fl], moves)
    text, source = None, "ai"
    try:
        for _ in range(2 if use_ai else 0):
            text = _checked_text(ai.planner_text(facts, _gravity(req)), template, allowed)
            if text:
                break
            print("[api/assess] rejected AI text (wrong numbers or missing parts), retrying")
    except Exception as e:  # AIUnavailable or anything else: scores never needed the AI
        print(f"[api/assess] AI text unavailable: {e!r}")
        text = None
    if not text:
        text, source = template, "template"

    # assemble
    driver = max(names, key=lambda p: scored["phases"][p]["score"])
    rooms = []
    for s in req["spaces"]:
        r = scored["rooms"][s["id"]]
        stocked = r["overall"] is not None
        hazards = {}
        for p in names:
            for i, it in enumerate(r[p]["items"]):
                hazards.setdefault(i, {})[p] = it["hazard"]
        mats = [i for i in s["items"] if i.get("category", "material") == "material"
                and not i.get("ignition_source")]
        items = [{"id": m["id"], "name": it["name"], "material_key": it["material_key"],
                  "hazard": hazards[k], "evidence": it["evidence"], "basis": it["basis"],
                  "n_tests": it["n_tests"], "threshold_pct": it["threshold_pct"], "gap": it["gap"]}
                 for k, (m, it) in enumerate(zip(mats, r[names[-1]]["items"]))]
        rooms.append({
            "id": s["id"], "name": s["name"], "stocked": stocked,
            "cruise": r["cruise"]["score"] if stocked else None,
            "surf": r["surf"]["score"] if stocked and "surf" in r else None,
            "overall": r["overall"],
            "cruise_level": r["cruise"]["level"] if stocked else None,
            "surf_level": r["surf"]["level"] if stocked and "surf" in r else None,
            "level": scoring.level(r["overall"]) if stocked else None,
            "rationale": text["rooms"].get(s["id"], ""),
            "fixes": [{**f, "why": text["fixes"].get(s["id"], [])[k] if k < len(text["fixes"].get(s["id"], []))
                       else f["why"]} for k, f in enumerate(fixes.get(s["id"], []))],
            "factors": {p: r[p]["factors"] for p in names} if stocked else {},
            "items": items,
        })

    stocked_rooms = [scored["rooms"][s["id"]] for s in req["spaces"] if scored["rooms"][s["id"]]["overall"]]
    factors = [{"key": k, "name": n, "weight": scoring.WEIGHTS[k],
                **{p: _band([r[p]["factors"][k] for r in stocked_rooms]) for p in names}}
               for k, n in FACTORS]

    gaps = [g for s in req["spaces"] for p in names for g in scored["rooms"][s["id"]][p]["gaps"]]
    gaps.append(NOT_SCORED)
    phase_out = dict(scored["phases"])
    return {
        "overall": {**scored["overall"], "driver": driver, "summary": text["summary"]},
        "phases": phase_out,
        "rooms": rooms,
        "factors": factors,
        "moves": moves,
        "data_gaps": list(dict.fromkeys(gaps)),
        "text_source": source,
        "input_hash": input_hash(req),
        "assessed_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }


def assess_cached(req: dict) -> dict:
    """Same input -> same answer. Template answers aren't cached, so the AI gets another try."""
    key = input_hash(req)
    if key in _cache:
        _cache.move_to_end(key)
        return _cache[key]
    t0 = time.time()
    result = build_assessment(req)
    if result["text_source"] == "ai":
        _cache[key] = result
        if len(_cache) > CACHE_SIZE:
            _cache.popitem(last=False)
    _log({"input_hash": key, "assessed_at": result["assessed_at"], "model": ai.MODEL,
          "seconds": round(time.time() - t0, 1), "input": req, "result": result})
    return result


# ------------------------------------------------------------------ routes

@router.get("/library", tags=["planner"])
def library():
    """Every item the planner can stow (materials, PSI test materials, machinery, safety)."""
    return data.load_library()


@router.post("/api/assess", response_model=AssessResponse, tags=["planner"])
def api_assess(req: AssessRequest):
    """Fire-risk assessment for a ship layout, both phases. Always 200 (template text if the AI is down)."""
    if len({s.id for s in req.spaces}) != len(req.spaces):
        raise HTTPException(422, "Space ids must be unique")
    return assess_cached(req.model_dump())


@router.post("/api/chat", response_model=ChatResponse, tags=["planner"])
def api_chat(req: ChatRequest):
    """One chat turn for a tab. Actions are checked against the ship and scored by code."""
    ship = req.assessment_input.model_dump()
    # scores for the chat: the cached assessment if there is one, otherwise code only (no extra AI call)
    result = _cache.get(input_hash(ship)) or build_assessment(ship, use_ai=False)
    history = [m.model_dump() for m in req.messages][-HISTORY_TURNS:]
    scored = adapter.score(ship)
    names = scored["phase_names"]
    compact = {k: result[k] for k in ("overall", "phases", "factors", "moves", "data_gaps")}
    compact["rooms"] = [{**_room_facts(sp, scored, names), "level": r["level"], "rationale": r["rationale"],
                         "fixes": [{"title": f["title"], "points": f["points"]} for f in r["fixes"]]}
                        for sp, r in zip(ship["spaces"], result["rooms"])]
    compact["nasa_dataset"] = nasa_data_summary()
    oxygen_levels = [ship["conditions"]["cruise"]["o2_percent"]] + (
        [ship["conditions"]["surface"]["o2_percent"]] if ship["conditions"].get("surface") else [])
    compact["nasa_tests"] = tests = cited_tests(oxygen_levels)
    allowed = _allowed(ship, result, compact)

    for attempt in range(2):
        try:
            raw = ai.planner_chat(req.tab, history, ship, compact, _gravity(ship))
        except Exception as e:  # AIUnavailable, bad key, quota... the frontend shows "could not be reached"
            print(f"[api/chat] AI unavailable: {e!r}")
            raise HTTPException(503, "The agent could not be reached. Try again in a moment.")
        reply = str((raw or {}).get("reply") or "").strip()
        if reply and _text_ok(reply, allowed) and citations_ok(reply, tests):
            break
        print("[api/chat] rejected reply (wrong numbers or empty), retrying")
    else:
        return ChatResponse(reply="I couldn't give an answer I could check against the scores. "
                                  "Try asking another way.", actions=[], citations=[], text_source="fallback")

    base = scored
    out, seen = [], set()
    for a in (raw.get("actions") or [])[:5]:
        a = actions.validate_action(a, ship)
        if not a or json.dumps(a, sort_keys=True) in seen:
            continue
        seen.add(json.dumps(a, sort_keys=True))
        out.append({**a, "label": actions.label(a, ship), "points": actions.points(ship, a, base)["ship"]})
    return ChatResponse(reply=reply, actions=out, citations=citations_in(reply, tests), text_source="ai")
