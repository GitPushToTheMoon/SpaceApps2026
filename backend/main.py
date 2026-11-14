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

from . import ai, api, data, matching, planner, risk
from .schemas import (AssessRequest, AssessResponse, Evidence, Experiment, Health,
                      Material, Preset)

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
# GET /library, POST /api/assess, POST /api/chat live in backend/api.py.

app.include_router(api.router)


# ------------------------------------------------------------------ admin

@app.post("/admin/reload")
def reload_data(x_admin_token: Optional[str] = Header(None)):
    """Re-read the CSVs/JSON and clear cached /assess answers.
    If ADMIN_TOKEN is set in the environment, send it as the X-Admin-Token header."""
    if ADMIN_TOKEN and x_admin_token != ADMIN_TOKEN:
        raise HTTPException(403, "Admin token required")
    data.reload()
    _assess_cached.cache_clear()
    api._cache.clear()
    return {"status": "reloaded", "experiments": data.experiment_count()}


# Placement contract is separate from the existing assessment API.
from . import placement
from .schemas import PlacementRequest, PlacementResponse, PlacementLocation


@app.get("/locations", response_model=List[PlacementLocation])
def locations():
    return placement.load_locations()


@app.post("/placement", response_model=PlacementResponse)
def placement_advice(req: PlacementRequest):
    return placement.evaluate(req)


@app.post("/planner/assess", response_model=PlannerResponse)
def planner_assessment(req: PlannerRequest):
    """Score cruise/surface inventory using CSV evidence and explicit prototype weights."""
    return planner.evaluate(req)
