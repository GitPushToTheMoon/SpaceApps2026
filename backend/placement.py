"""Rate supplied locations using the same evidence rules as /assess."""
import json
from fastapi import HTTPException
from . import ai, data, matching, risk
from .schemas import PlacementLocation, PlacementRequest, PlacementResponse


def load_locations():
    return [PlacementLocation.model_validate(row) for row in
            json.loads((data.DATA_DIR / "locations.json").read_text(encoding="utf-8"))]


def evaluate(req: PlacementRequest) -> PlacementResponse:
    locations = req.locations if req.locations is not None else load_locations()
    ids = [loc.id for loc in locations]
    if len(set(ids)) != len(ids):
        raise HTTPException(400, "Location ids must be unique.")
    if req.current_location_id not in ids:
        raise HTTPException(400, "Unknown current_location_id. See /locations.")
    materials = []
    for name in req.item.materials:
        mat = data.get_material(name)
        if mat is None:
            raise HTTPException(400, f"Unknown material '{name}'. See /materials.")
        materials.append(mat)
    gaps, evidence, rated = [], {}, []
    if req.locations is None:
        gaps.append("Using demo locations; replace with engineer-supplied mission layout and conditions.")
    for location in locations:
        loc = location.model_dump()
        loc["ratings"] = {}
        for phase in ai.PHASES:
            cond = loc["conditions"].get(phase)
            if cond is None:
                loc["ratings"][phase] = {"risk": "insufficient data", "reason": "Phase conditions not reported."}
                gaps.append(f"{location.id} {phase}: phase conditions not reported.")
                continue
            if phase == "pre_launch" and cond["gravity_g"] != 1:
                raise HTTPException(400, "pre_launch gravity_g must be 1 (Earth).")
            if phase == "pre_launch":
                gaps.append(f"{location.id} pre_launch: Earth normal gravity is not validated by microgravity experiments.")
            elif cond["gravity_g"] != 0:
                gaps.append(f"{location.id} surface: surface gravity is not validated by microgravity experiments.")
            levels, reasons = [], []
            for mat in materials:
                df = matching.find_matches(cond["oxygen_pct"], cond["pressure_psi"], cond["airflow_cm_s"], mat.material, mat.fuel_type)
                level, reason = risk.rule_risk(df, cond["oxygen_pct"], mat.material, mat.fuel_type)
                levels.append(level)
                reasons.append(reason)
                for row in df.to_dict("records"):
                    evidence[row["id"]] = risk.evidence_sentence(row)
                gaps.extend(f"{location.id} {phase}: {g}" for g in matching.coverage_gaps(
                    df, cond["oxygen_pct"], cond["pressure_psi"], cond["airflow_cm_s"], mat.material, 0))
            level = "high" if "high" in levels else ("insufficient data" if "insufficient data" in levels else max(levels, key=ai._rank))
            loc["ratings"][phase] = {"risk": level, "reason": " ".join(reasons)}
        rated.append(loc)
    gaps.append("Ratings screen material combustion evidence only; module geometry, crew access and neighboring hazards are not quantitatively modeled. Mitigations require engineering review.")
    current = next(loc for loc in rated if loc["id"] == req.current_location_id)
    candidates = [loc for loc in rated if loc["id"] != current["id"] and (not req.pre_cleared_only or loc["pre_cleared"])]
    lines = [f"({i}) {s}" for i, s in evidence.items()]
    try:
        advice = ai.advise_placement(req.item.model_dump(), current, candidates,
                                     current["conditions"], lines, gaps, req.destination)
    except (ai.AIUnavailable, ai.errors.APIError, ValueError, KeyError):
        advice = {"summary": "AI advice unavailable. Review phase ratings and evidence with an engineer.",
                  "options": [], "recommended": None, "data_gaps": ["AI placement advice unavailable."]}
    return PlacementResponse(**{**advice, "overall": ai.overall_risk(current["ratings"]),
        "locations": rated, "evidence": [{"id": i, "what_happened": s} for i, s in evidence.items()],
        "data_gaps": list(dict.fromkeys(gaps + advice["data_gaps"]))})
