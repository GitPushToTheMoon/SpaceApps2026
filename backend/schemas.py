"""JSON shapes for the API. This file is the contract with the frontend.

Use Pydantic models (class X(BaseModel)) so FastAPI validates input and
documents everything automatically at /docs.
If you change a field here, update API.md and tell the frontend team.
"""
from pydantic import BaseModel


class Range(BaseModel):
    # TODO: min and max, both optional floats (null when the source didn't report it)
    pass


class Material(BaseModel):
    # TODO: one entry from data/materials.csv
    #   material        - exact key, e.g. "PMMA" (what the frontend sends back)
    #   display_name    - what users see, e.g. "Acrylic plastic (PMMA)"
    #   fuel_type       - "solid" | "liquid" | "gas"
    #   description
    #   investigations  - list of strings
    #   priority        - int, 1 = most relevant
    pass


class Analysis(BaseModel):
    # TODO: the AI-generated fields saved in data/analysis.json
    #   summary, fire_safety_relevance (1-10), relevance_reason,
    #   environments (list), category, key_findings (list)
    pass


class Experiment(BaseModel):
    # TODO: one row of experiments.csv, cleaned up for the frontend
    #   id, name, investigation, fuel_type, material
    #   oxygen_pct, pressure_psi, airflow_cm_s  -> each a Range
    #   gravity, outcome, description, source_url
    #   analysis -> Analysis or null if not analyzed yet
    # Leave out source_quote and verified (internal only)
    pass


class MatchedExperiment(Experiment):
    # TODO: add match_distance (float, 0 = user's conditions fall inside this test's ranges)
    pass


class AssessRequest(BaseModel):
    # TODO: what the frontend sends to POST /assess
    #   oxygen_pct (0-100), pressure_psi, airflow_cm_s, material (optional key from /materials)
    # Add validation limits so bad input returns a 422 automatically
    pass


class Evidence(BaseModel):
    # TODO: id (experiment id) + what_happened (string)
    pass


class AssessResponse(BaseModel):
    # TODO: what POST /assess returns
    #   risk_level   - "low" | "elevated" | "high" | "insufficient data"
    #   explanation  - 3-5 sentences citing experiment ids
    #   evidence     - list of Evidence
    #   data_gaps    - list of strings
    #   matches      - list of MatchedExperiment (the 5 closest)
    #   disclaimer   - fixed "research aid, not a safety certification" text
    pass
