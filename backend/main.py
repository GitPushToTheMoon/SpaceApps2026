"""Flame in Freefall API (FastAPI).

Run from the repo root:  uvicorn backend.main:app --reload
Interactive docs:        http://localhost:8000/docs
Full JSON reference:     API.md
"""
import os
from functools import lru_cache
from typing import List, Optional

from fastapi import FastAPI, Header, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse

from . import ai, data, matching
from .schemas import (AssessRequest, AssessResponse, Evidence, Experiment, Health,
                      Material, Preset)

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

RISK_LEVELS = {"low", "elevated", "high", "insufficient data"}
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
    result = ai.assess(conditions, [m.model_dump(exclude={"analysis"}) for m in matches], code_gaps)

    # ---- never trust the AI's output blindly
    risk = str(result.get("risk_level", "")).strip().lower()
    if risk not in RISK_LEVELS:
        risk = "insufficient data"

    valid_ids = {m.id for m in matches}
    evidence = []
    for e in result.get("evidence") or []:
        if isinstance(e, dict) and e.get("id") in valid_ids and e.get("what_happened"):
            evidence.append(Evidence(id=e["id"], what_happened=str(e["what_happened"])))

    # code gaps first; AI gaps only if they add something (skip repeats of gravity/oxygen/pressure facts)
    gaps: List[str] = list(code_gaps)
    covered = " ".join(code_gaps).lower()
    for g in [str(x).strip() for x in (result.get("data_gaps") or [])]:
        low = g.lower()
        repeats = (("gravity" in low and "gravity" in covered)
                   or ("oxygen" in low and "oxygen" in covered and "%" in low)
                   or ("pressure" in low and "pressure" in covered and "report" in low))
        if g and not repeats and g not in gaps:
            gaps.append(g)

    return AssessResponse(
        risk_level=risk,
        explanation=str(result.get("explanation") or "").strip(),
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