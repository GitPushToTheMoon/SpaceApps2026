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
    return {"summary": summary, "rooms": rooms,
            "fixes": {sid: [f["why"] for f in fl] for sid, fl in fixes.items()}}


def _checked_text(raw: dict, template: dict, allowed: List[float]) -> Optional[dict]:
    """AI text with every number checked. None = reject (wrong number or missing summary)."""
    def ok(t):
        return isinstance(t, str) and t.strip() and risk.all_numbers_ok(t, allowed)[0]

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
        "rooms": [{"id": s["id"], "name": s["name"],
                   **{p: {"score": scored["rooms"][s["id"]][p]["score"],
                          "factors": scored["rooms"][s["id"]][p]["factors"]} for p in names},
                   "items": [{"name": i["name"], "evidence": i["evidence"], "basis": i["basis"]}
                             for i in scored["rooms"][s["id"]][names[-1]]["items"]],
                   "fixes": [f["title"] for f in fixes[s["id"]]]}
                  for s in req["spaces"] if s["id"] in fixes],
        "moves": [{"item": m["item"], "from": m["from_name"], "to": m["to_name"]} for m in moves],
    }
    template = _template(scored, req, fixes)
    allowed = risk.collect_numbers(facts) + risk.collect_numbers(req) \
        + risk.collect_numbers([f for fl in fixes.values() for f in fl]) + risk.collect_numbers(moves)
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
                  "hazard": hazards[k], "evidence": it["evidence"], "basis": it["basis"]}
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
    compact = {k: result[k] for k in ("overall", "phases", "factors", "moves", "data_gaps")}
    compact["rooms"] = [{k: r[k] for k in ("id", "name", "cruise", "surf", "overall", "level", "rationale")}
                        | {"fixes": [{"title": f["title"], "points": f["points"]} for f in r["fixes"]]}
                        for r in result["rooms"]]
    allowed = risk.collect_numbers(ship) + risk.collect_numbers(result)

    for attempt in range(2):
        try:
            raw = ai.planner_chat(req.tab, history, ship, compact, _gravity(ship))
        except ai.AIUnavailable as e:
            print(f"[api/chat] AI unavailable: {e}")
            raise HTTPException(503, "The agent could not be reached. Try again in a moment.")
        reply = str((raw or {}).get("reply") or "").strip()
        if reply and risk.all_numbers_ok(reply, allowed)[0]:
            break
        print("[api/chat] rejected reply (wrong numbers or empty), retrying")
    else:
        return ChatResponse(reply="I couldn't give an answer I could check against the scores. "
                                  "Try asking another way.", actions=[], text_source="fallback")

    base = adapter.score(ship)
    out, seen = [], set()
    for a in (raw.get("actions") or [])[:5]:
        a = actions.validate_action(a, ship)
        if not a or json.dumps(a, sort_keys=True) in seen:
            continue
        seen.add(json.dumps(a, sort_keys=True))
        out.append({**a, "label": actions.label(a, ship), "points": actions.points(ship, a, base)["ship"]})
    return ChatResponse(reply=reply, actions=out, text_source="ai")
