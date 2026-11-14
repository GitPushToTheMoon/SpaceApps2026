"""Flame in Freefall API (FastAPI).

Run from the repo root:  uvicorn backend.main:app --reload
Interactive docs:        http://localhost:8000/docs
Full JSON reference:     API.md
"""
from fastapi import FastAPI

app = FastAPI(title="Flame in Freefall API")

# TODO: add CORS middleware so the frontend (different URL/port) can call the API
# - allow all origins during the hackathon, or read FRONTEND_ORIGIN from env for the deployed version


@app.get("/health")
def health():
    # TODO: return {"status": "ok", "experiments": <number of verified experiments>}
    #       Used to check the backend is up (and by the frontend on load)
    return {"status": "ok"}


@app.get("/materials")
def materials():
    # TODO: return all materials from data.load_materials(), sorted by priority then display_name
    #       Frontend uses this for the material dropdown
    return []


@app.get("/experiments")
def experiments(investigation: str = None, material: str = None,
                fuel_type: str = None, environment: str = None, sort: str = "relevance"):
    # TODO: return verified experiments as Experiment objects
    # - optional filters: investigation, material, fuel_type (CSV columns),
    #   environment (from the AI analysis, e.g. "lunar base")
    # - sort by fire_safety_relevance (highest first) or by id
    return []


@app.get("/experiments/{exp_id}")
def experiment(exp_id: str):
    # TODO: return one Experiment, or 404 if the id doesn't exist
    return {}


@app.post("/assess")
def assess(request: dict):
    # TODO: the risk checker (change `dict` to AssessRequest once schemas.py is filled)
    # 1. If a material was given, look it up in materials -> 400 if unknown; get its fuel_type
    # 2. matching.find_matches(...) -> 5 closest experiments
    # 3. No matches (empty dataset) -> return risk_level "insufficient data" without calling AI
    # 4. ai.assess(conditions, matches) -> risk_level, explanation, evidence, data_gaps
    # 5. SAFETY CHECK: drop any evidence whose id isn't in the matches (AI made it up)
    # 6. Return AssessResponse (include the matches + disclaimer)
    # - cache results for identical inputs so repeat questions don't cost another AI call
    # - AI failure -> 502 with a readable message
    return {"risk_level": "insufficient data", "explanation": "TODO"}


@app.post("/admin/reload")
def reload_data():
    # TODO: call data.reload() and clear the /assess cache
    #       Run this after the data team updates the CSVs or analysis.json
    return {"status": "TODO"}
