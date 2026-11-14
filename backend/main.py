"""Flame in Freefall API (FastAPI).

Run from the repo root:  uvicorn backend.main:app --reload
Interactive docs:        http://localhost:8000/docs
Full JSON reference:     API.md / API_examples.json
"""
import os
from functools import lru_cache
from typing import List, Optional

from fastapi import FastAPI, Header, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse

from . import ai, data, matching, risk, scoring
from .schemas import (AssessRequest, AssessResponse, Evidence, Experiment, Health,
                      Material, Preset, StowageAction, StowagePhase, StowageRequest,
                      StowageResponse, StowageRoom, StowageRoomPhase, StowageScore)

from .planner_schemas import PlannerRequest, PlannerResponse

app = FastAPI(
    title="Flame in Freefall API",
    description="Fire-safety insights from NASA microgravity combustion data (PSI).",
    version="1.0",
)

# Let the frontend (a different URL/port) call the API.
# FRONTEND_ORIGIN can be "*" or a comma-separated list of URLs.
_origins = [o.strip() for o in os.environ.get("FRONTEND_ORIGIN", "*").split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins or ["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

ADMIN_TOKEN = os.environ.get("ADMIN_TOKEN")  # optional; set it when deployed


@app.get("/", include_in_schema=False)
def root():
    return RedirectResponse("/docs")


@app.get("/health", response_model=Health)
def health():
    try:
        return Health(status="ok", experiments=data.experiment_count())
    except Exception as e:  # data files missing/broken
        print(f"[health] {e}")
        return Health(status="error", experiments=0)


@app.get("/materials", response_model=List[Material])
def materials():
    return data.load_materials()


@app.get("/presets", response_model=List[Preset])
def presets():
    return data.load_presets()


@app.get("/experiments", response_model=List[Experiment])
def experiments(
    investigation: Optional[str] = Query(None, description="e.g. FLEX, SAFFIRE, BASS-II, BRE, PSI-69"),
    material: Optional[str] = Query(None, description="Material key from /materials, e.g. PMMA"),
    fuel_type: Optional[str] = Query(None, description="solid, liquid or gas"),
    outcome_category: Optional[str] = Query(None, description="e.g. burned, self-extinguished"),
    environment: Optional[str] = Query(None, description="e.g. lunar base (from AI analysis)"),
    sort: str = Query("relevance", pattern="^(relevance|id)$"),
):
    return data.list_experiments(
        investigation=investigation, material=material, fuel_type=fuel_type,
        outcome_category=outcome_category, environment=environment, sort=sort,
    )


@app.get("/experiments/{exp_id}", response_model=Experiment)
def experiment(exp_id: str):
    exp = data.get_experiment(exp_id)
    if exp is None:
        raise HTTPException(404, f"No experiment with id {exp_id}")
    return exp


# ------------------------------------------------------------------ risk checker

@lru_cache(maxsize=256)
def _assess_cached(oxygen: float, pressure: float, airflow: float,
                   material: Optional[str], gravity: float) -> AssessResponse:
    """Same inputs -> same answer without another Gemini call.
    Failures raise, and exceptions are never cached, so a retry tries Gemini again."""
    fuel_type = None
    if material:
        mat = data.get_material(material)
        if mat is None:
            raise HTTPException(400, f"Unknown material '{material}'. See /materials.")
        material, fuel_type = mat.material, mat.fuel_type

    matches_df = matching.find_matches(oxygen, pressure, airflow, material, fuel_type)
    matches = matching.to_matched_experiments(matches_df)
    code_gaps = matching.coverage_gaps(matches_df, oxygen, pressure, airflow, material, gravity)

    if not matches:
        return AssessResponse(
            risk_level="insufficient data",
            explanation="No verified experiments are loaded yet, so there is nothing to compare against.",
            evidence=[], data_gaps=code_gaps, matches=[],
        )

    conditions = {
        "oxygen_pct": oxygen, "pressure_psi": pressure, "airflow_cm_s": airflow,
        "material": material or "any", "gravity_g": gravity,
    }

    # 1. Code decides the risk level and writes the evidence (never the AI)
    risk_level, reason = risk.rule_risk(matches_df, oxygen, material, fuel_type)
    rows = matches_df.to_dict("records")
    evidence_pairs = [(r["id"], risk.evidence_sentence(r)) for r in rows]
    evidence = [Evidence(id=i, what_happened=s) for i, s in evidence_pairs]

    # 2. AI writes the explanation; every number it uses must be a real value
    allowed = risk.allowed_numbers(matches_df, conditions)
    explanation, extra_gaps = None, []
    for _ in range(2):  # one retry if it gets a number wrong
        result = ai.assess(conditions, risk_level, reason,
                           [f"({i}) {s}" for i, s in evidence_pairs], code_gaps)
        text = str(result.get("explanation") or "").strip()
        ok, bad = risk.numbers_ok(text, allowed)
        if text and ok and "match distance" not in text.lower():
            explanation = text
            extra_gaps = [str(x).strip() for x in (result.get("data_gaps") or [])]
            break
        print(f"[assess] rejected AI explanation (bad numbers: {bad})")
    if explanation is None:
        explanation = risk.template_explanation(risk_level, reason, evidence_pairs)

    # 3. Gaps: code facts first, AI extras only if new and number-checked
    gaps: List[str] = list(code_gaps)
    covered = " ".join(code_gaps).lower()
    for g in extra_gaps:
        low = g.lower()
        repeats = (("gravity" in low and "gravity" in covered)
                   or ("oxygen" in low and "oxygen" in covered and "%" in low)
                   or ("pressure" in low and "pressure" in covered and "report" in low))
        if g and not repeats and g not in gaps and risk.numbers_ok(g, allowed)[0]:
            gaps.append(g)

    return AssessResponse(
        risk_level=risk_level,
        explanation=explanation,
        evidence=evidence,
        data_gaps=gaps,
        matches=matches,
    )


@app.post("/assess", response_model=AssessResponse)
def assess(req: AssessRequest):
    try:
        return _assess_cached(
            round(req.oxygen_pct, 1), round(req.pressure_psi, 2), round(req.airflow_cm_s, 1),
            req.material.strip() if req.material else None, round(req.gravity_g, 3),
        )
    except HTTPException:
        raise
    except ai.AIUnavailable:
        raise HTTPException(502, "AI assessment unavailable right now. Please try again in a minute.")
    except Exception as e:
        print(f"[assess] unexpected error: {e!r}")
        raise HTTPException(502, "AI assessment failed. Please try again.")


# ------------------------------------------------------------------ stowage planner

SURFACE_GRAVITY = {"moon": "moon_habitat", "mars": "mars_habitat"}   # preset ids
SEVERITIES = {"high", "medium", "low"}


def _surface_gravity(destination: str) -> float:
    preset = data.get_preset(SURFACE_GRAVITY.get(destination, ""))
    return preset.gravity_g if preset else {"moon": 0.165, "mars": 0.38}.get(destination, 0.0)


def _template_text(phases: dict, rooms_by_phase: dict, phase_names: List[str]) -> dict:
    """Plain text built from the scores, used when Gemini is down or gets a number wrong."""
    out = {"phases": {}, "rooms": {}, "actions": [], "hazards": []}
    for ph in phase_names:
        stocked = [r for r in rooms_by_phase[ph] if r["stocked"]]
        worst = max(stocked, key=lambda r: r["score"]) if stocked else None
        out["phases"][ph] = (f"Ship scores {phases[ph]['score']:g} ({phases[ph]['level']}) during {ph}."
                             + (f" Riskiest space: {worst['name']} ({worst['score']:g})." if worst else ""))
    last = phase_names[-1]
    for r in rooms_by_phase[last]:
        if not r["stocked"]:
            continue
        top = sorted(r["factors"].items(), key=lambda kv: -kv[1])[:2]
        out["rooms"][r["name"]] = "Main drivers: " + ", ".join(f"{k} ({v:g})" for k, v in top) + "."
    ranked = sorted([r for r in rooms_by_phase[last] if r["stocked"]], key=lambda r: -r["score"])
    for r in ranked[:5]:
        if r["score"] <= 40:
            break
        sev = "high" if r["score"] > 60 else "medium"
        flam = max(r["items"], key=lambda i: i["hazard"])["name"] if r["items"] else None
        title = (f"Review flammable items in {r['name']} (highest hazard: {flam}): bag, move or swap them"
                 if flam else f"Separate ignition sources from flammables in {r['name']}")
        out["actions"].append({"severity": sev, "room": r["name"], "title": title})
    return out


def _validated_text(raw: dict, phase_names: List[str], room_names: set, allowed: List[float]):
    """Keep only well-formed AI text that names real rooms and uses real numbers."""
    def ok(t):
        return isinstance(t, str) and t.strip() and risk.all_numbers_ok(t, allowed)[0]

    phases = {ph: str(raw.get("phases", {}).get(ph, "")).strip() for ph in phase_names}
    if not all(ok(t) for t in phases.values()):
        return None
    rooms = {k: str(v).strip() for k, v in (raw.get("rooms") or {}).items()
             if k in room_names and ok(str(v))}
    actions = []
    for a in raw.get("actions") or []:
        if not isinstance(a, dict) or str(a.get("severity", "")).lower() not in SEVERITIES:
            continue
        room = a.get("room") if a.get("room") in room_names else None
        if ok(str(a.get("title", ""))):
            actions.append({"severity": a["severity"].lower(), "room": room, "title": str(a["title"]).strip()})
        if len(actions) == 5:
            break
    hazards = [str(h).strip() for h in (raw.get("hazards") or []) if ok(str(h))][:4]
    return {"phases": phases, "rooms": rooms, "actions": actions, "hazards": hazards}


@app.post("/stowage/assess", response_model=StowageResponse)
def stowage_assess(req: StowageRequest):
    sc = req.scenario
    spaces = [s.model_dump() for s in req.spaces]

    # 1. phases from the scenario
    phases = {"cruise": {"oxygen_pct": sc.cruise_atmosphere.o2_percent, "gravity_g": 0.0,
                         "days": sc.cruise_days}}
    surface_g = 0.0
    if sc.destination != "cruise_only":
        surface_g = _surface_gravity(sc.destination)
        phases["surface"] = {"oxygen_pct": sc.surface_atmosphere.o2_percent, "gravity_g": surface_g,
                             "days": sc.surface_days}
    by_phase = None
    if sc.cruise_ventilation == "reduced":
        cruise_spaces = [{**s, "airflow_cm_s": (s["airflow_cm_s"] / 2 if s.get("airflow_cm_s") is not None
                                                else None)} for s in spaces]
        by_phase = {"cruise": cruise_spaces}

    # 2. scores: code only
    result = scoring.score_mission(spaces, phases, by_phase)
    phase_names = list(phases)
    room_names = {s["name"] for s in spaces}

    # 3. text: AI, checked; template if it fails
    facts = {
        "overall": result["overall"],
        "phases": result["phases"],
        "rooms": {ph: [{"name": r["name"], "score": r["score"], "level": r["level"], "factors": r["factors"],
                        "items": [{"name": i["name"], "hazard": i["hazard"], "evidence": i["evidence"]}
                                  for i in r["items"]], "gaps": r["gaps"]}
                       for r in result["rooms"][ph] if r["stocked"]]
                  for ph in phase_names},
    }
    scenario_facts = {"destination": sc.destination, "phases": phases}
    allowed = risk.collect_numbers(facts) + risk.collect_numbers(scenario_facts) \
        + risk.collect_numbers(spaces)
    text, source = None, "ai"
    try:
        for _ in range(2):
            text = _validated_text(ai.stowage_text(scenario_facts, facts, surface_g),
                                   phase_names, room_names, allowed)
            if text:
                break
            print("[stowage] rejected AI text (wrong numbers or missing parts), retrying")
    except Exception as e:  # AIUnavailable or anything else: scores never needed the AI
        print(f"[stowage] AI text unavailable: {e!r}")
        text = None
    template = _template_text(result["phases"], result["rooms"], phase_names)
    if not text:
        text, source = template, "template"
    else:  # AI skipped a stocked room: use the plain rationale for that one
        for name, rationale in template["rooms"].items():
            text["rooms"].setdefault(name, rationale)

    # 4. assemble
    rooms = []
    for i, s in enumerate(spaces):
        per_phase = {ph: result["rooms"][ph][i] for ph in phase_names}
        rooms.append(StowageRoom(
            name=s["name"],
            stocked=per_phase[phase_names[0]]["stocked"],
            phases={ph: StowageRoomPhase(score=r["score"], level=r["level"], factors=r["factors"],
                                         items=r["items"], gaps=r["gaps"])
                    for ph, r in per_phase.items()},
            rationale=text["rooms"].get(s["name"], ""),
        ))
    gaps = list(dict.fromkeys(g for ph in phase_names for r in result["rooms"][ph] for g in r["gaps"]))

    return StowageResponse(
        overall=StowageScore(**result["overall"]),
        phases={ph: StowagePhase(**result["phases"][ph], summary=text["phases"].get(ph, ""))
                for ph in phase_names},
        rooms=rooms,
        actions=[StowageAction(**a) for a in text["actions"]],
        hazards=text["hazards"],
        data_gaps=gaps,
        text_source=source,
    )


# ------------------------------------------------------------------ admin

@app.post("/admin/reload")
def reload_data(x_admin_token: Optional[str] = Header(None)):
    """Re-read the CSVs/JSON and clear cached /assess answers.
    If ADMIN_TOKEN is set in the environment, send it as the X-Admin-Token header."""
    if ADMIN_TOKEN and x_admin_token != ADMIN_TOKEN:
        raise HTTPException(403, "Admin token required")
    data.reload()
    _assess_cached.cache_clear()
    return {"status": "reloaded", "experiments": data.experiment_count()}
