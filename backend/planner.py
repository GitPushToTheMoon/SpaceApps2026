"""Deterministic handoff scoring, with evidence-derived material points.

The CSV supports evidence screening, not calibration of the layout weights.
Unknown material points propagate as score intervals, never as zero fuel.
"""
import math
from . import data, matching, risk
from .planner_schemas import PlannerRequest, PlannerResponse

POINTS = {"low": 1, "elevated": 2, "high": 3}
HEAT = {"heater": 30, "3d_printer": 30, "li_ion": 25, "pump": 20,
        "exercise": 15, "consoles": 15, "laptop": 10, "fan": 5}
FACTOR_NAMES = ("materials_fuel_load", "oxygen_ventilation", "cabin_pressure", "airflow",
                "material_thickness", "machinery_proximity", "machinery_heat")
VERSION = "handoff-evidence-v1"


def clamp(value):
    return max(0.0, min(100.0, value))


def level(value):
    return next(label for upper, label in [(20, "Low"), (40, "Guarded"), (60, "Elevated"), (80, "High"), (100, "Severe")] if value <= upper)


def score_result(lo, hi, unknown, summary):
    lo, hi = clamp(lo), clamp(hi)
    return {"score": None if unknown else round(lo, 2),
            "level": None if unknown else level(lo), "lower_bound": round(lo, 2),
            "upper_bound": round(hi, 2), "status": "insufficient data" if unknown else "prototype",
            "summary": summary}


def material_screen(item, atmosphere, airflow, gravity, experiments):
    key = (item.material_key or "").strip()
    exact = experiments[experiments["material"].fillna("").str.casefold() == key.casefold()] if key else experiments.iloc[:0]
    base = {"item_id": item.id, "material_key": item.material_key, "verified_tests": len(exact), "evidence": [], "data_gaps": []}
    if exact.empty:
        return {**base, "risk_level": "insufficient data", "points": None,
                "reason": "No verified tests of this material; its flammability is unknown.",
                "data_gaps": ["No verified same-material evidence. Unknown material points span 1 to 3."]}
    # Rank only exact-material rows; unrelated fuels cannot displace the evidence.
    df = matching.find_matches(atmosphere.o2_percent, atmosphere.pressure_psia, airflow,
                               key, None, k=5, df=exact)
    known = df[df["outcome_category"].isin(risk.BURNED | risk.DID_NOT_BURN)]
    gaps = []
    if known.empty:
        rating, reason = "insufficient data", "The closest same-material tests have no usable combustion outcome."
    else:
        rating, reason = risk.rule_risk(known, atmosphere.o2_percent, key, None)
        # A low screen requires ALL selected outcomes known, non-burning and
        # atmosphere/airflow inside the reported ranges, not oxygen alone.
        if rating == "low" and (len(known) != len(df) or not (df["match_distance"] == 0).all()):
            rating = "elevated"
            reason = "Non-burning evidence comes from incomplete or different conditions; a low screen is not supported."
    if not (df["match_distance"] == 0).any():
        gaps.append("No selected test covers the requested oxygen, pressure and airflow together.")
    if df[["pressure_psi_min", "pressure_psi_max"]].isna().all(axis=1).any():
        gaps.append("Some selected tests do not report pressure.")
    if df[["airflow_cm_s_min", "airflow_cm_s_max"]].isna().all(axis=1).any():
        gaps.append("Some selected tests do not report airflow.")
    if len(known) != len(df):
        gaps.append("Some selected tests have mixed or unknown outcomes.")
    if gravity:
        gaps.append("Surface gravity is unvalidated by these microgravity tests; this is an evidence screen only.")
    gaps.append("Item thickness, construction and ignition exposure may differ from tested samples.")
    return {**base, "risk_level": rating, "points": POINTS.get(rating), "reason": reason,
            "data_gaps": gaps, "evidence": [{"id": row["id"], "what_happened": risk.evidence_sentence(row)} for row in df.to_dict("records")]}


def is_ignition(item):
    return item.ignition_source or item.equipment in HEAT or item.equipment == "other"


def is_passage(space):
    return space.kind == "passage" or space.type.casefold() in {"node", "hall", "tunnel", "hall / tunnel", "node (passage)"}


def adjacent(a, b):
    return bool(a.position and b.position and abs(a.position.x-b.position.x)+abs(a.position.y-b.position.y) == 1)


def room_values(space, phase, req, screens, unknown_points, neighbor_ignition):
    atmosphere = req.scenario.cruise_atmosphere if phase == "cruise" else req.scenario.cabin_atmosphere
    fuels = [i for i in space.items if i.category == "material" or i.material_key]
    points = {i.id: screens[i.id]["points"] or unknown_points for i in fuels}
    volumes = {i.id: i.dimensions_cm.l*i.dimensions_cm.w*i.dimensions_cm.h*i.quantity/1000 for i in fuels}
    sizes = {i.id: min(4, 1+math.floor(volumes[i.id]/5)) for i in fuels}
    fuel = sum(points[i.id]*sizes[i.id] for i in fuels)
    flammables = [i for i in fuels if points[i.id] >= 2]
    high = [i for i in fuels if points[i.id] == 3]
    ignitions = [i for i in space.items if is_ignition(i)]
    ignition_count = sum(i.quantity for i in ignitions)
    oxygen = any(i.oxygen_source for i in space.items)
    detector = any(i.equipment == "smoke_detector" for i in space.items)
    extinguisher = any(i.equipment == "extinguisher" for i in space.items)
    raw = fuel + (2*ignition_count if fuel else 0) + (4 if oxygen and flammables else 0)
    raw += 2 if fuels and is_passage(space) else 0
    raw -= int(detector)+int(extinguisher)
    reduced = req.scenario.ventilation == "reduced" and phase == "cruise"
    exploration = atmosphere.o2_percent >= 34
    if phase == "cruise":
        raw += min(3, sum(i.quantity for i in fuels if i.loose_soft_goods))
        raw += int(not detector)
        raw += 2 if reduced and not detector and ignitions else 0
        raw += 1 if not reduced and ignitions and flammables else 0
        raw += int(req.scenario.cruise_days > 180)
        raw += 1 if space.airflow_cm_s < 5 and ignitions else 0
    else:
        raw += 2 if any(i.equipment == "li_ion" and not i.bagged for i in space.items) else 0
        raw += 1 if ignitions and flammables else 0
        raw += 1 if req.mission == "mars" and flammables else 0
        raw += 2 if exploration and flammables else 0
        raw += 1 if exploration and oxygen else 0
        raw += 1 if req.scenario.surface_stay_days > 30 and fuel >= 5 else 0
    # Empty spaces do not accumulate missing-detector or duration penalties.
    raw = max(0, raw) if space.items else 0
    airflow = space.airflow_cm_s
    thin = min((min(i.dimensions_cm.l, i.dimensions_cm.w, i.dimensions_cm.h) for i in flammables), default=None)
    # Cabin-pressure weights are defined only for the two handoff atmospheres.
    if math.isclose(atmosphere.pressure_psia, 14.7) and math.isclose(atmosphere.o2_percent, 21):
        pressure = 25
    elif math.isclose(atmosphere.pressure_psia, 8.2) and math.isclose(atmosphere.o2_percent, 34):
        pressure = 70
    else:
        pressure = None
    factors = {
        "materials_fuel_load": clamp(fuel/14*100 + 5*len(high)),
        "oxygen_ventilation": clamp(10+15*oxygen+40*bool(oxygen and flammables)+25*exploration+10*reduced),
        "cabin_pressure": pressure,
        "airflow": clamp(75-8*airflow if airflow < 5 else 20 if airflow <= 15 else 20+6*(airflow-15)),
        "material_thickness": 0 if not flammables else 85 if thin < .5 else 55 if thin < 2 else 35 if thin < 5 else 20,
        "machinery_proximity": clamp(45+12*ignition_count) if ignitions and flammables else 35 if flammables and neighbor_ignition else 20 if ignitions else 0,
        "machinery_heat": clamp(sum(HEAT.get(i.equipment, 15)*min(i.quantity, 3) for i in ignitions) + (10 if ignitions and airflow < 5 else 0)),
    }
    return {"uncapped": raw*7, "score": clamp(raw*7), "factors": factors}


def combine(cruise, surface, req):
    if req.mission == "cruise":
        return cruise
    days = req.scenario.cruise_days+req.scenario.surface_stay_days
    return .6*max(cruise, surface)+.4*(cruise*req.scenario.cruise_days+surface*req.scenario.surface_stay_days)/days


def ship_value(values):
    return .6*max(values)+.4*sum(values)/len(values) if values else 0


def evaluate(req: PlannerRequest) -> PlannerResponse:
    phases = ["cruise"] if req.mission == "cruise" else ["cruise", "surface"]
    experiments = data.load_experiments()
    hazards = ["Prototype score, not a probability or safety certification. Layout weights and evidence-to-points mapping are not experimentally calibrated.",
               "No mass validation: dimensions and quantities do not determine kilograms or capacity compliance."]
    if req.mission != "cruise":
        hazards.append("Surface gravity is not validated by the microgravity dataset. Launch is out of scope.")
    else:
        hazards.append("Launch and surface operations are out of scope for cruise-only missions.")
    if any(not s.position for s in req.spaces):
        hazards.append("Missing grid positions: neighboring machinery cannot be evaluated for those spaces.")
    # Cache repeated materials within the request, never across CSV reloads.
    cache, screens, values, rooms = {}, {}, {}, []

    def screen_for(item, atmosphere, airflow, gravity):
        key = ((item.material_key or "").strip().casefold(), atmosphere.o2_percent,
               atmosphere.pressure_psia, airflow, gravity)
        if key not in cache:
            cache[key] = material_screen(item, atmosphere, airflow, gravity, experiments)
        return {**cache[key], "item_id": item.id}

    for phase in phases:
        screens[phase], values[phase] = {}, {}
        atmosphere = req.scenario.cruise_atmosphere if phase == "cruise" else req.scenario.cabin_atmosphere
        gravity = 0 if phase == "cruise" else .166 if req.mission == "lunar" else .375
        for space in req.spaces:
            local = {}
            for item in space.items:
                if item.category != "material" and not item.material_key:
                    continue
                local[item.id] = screen_for(item, atmosphere, space.airflow_cm_s, gravity)
            screens[phase][space.id] = local
            neighbor = any(adjacent(space, other) and any(is_ignition(i) for i in other.items) for other in req.spaces if other.id != space.id)
            values[phase][space.id] = [room_values(space, phase, req, local, bound, neighbor) for bound in (1, 3)]
    for space in req.spaces:
        scores, factors, materials = {}, {}, {}
        for phase in phases:
            local = screens[phase][space.id]
            unknown = any(s["points"] is None for s in local.values())
            lo, hi = values[phase][space.id]
            scores[phase] = score_result(lo["score"], hi["score"], unknown, "Material evidence plus prototype inventory, equipment and phase weights.")
            factors[phase] = {name: {"lower_bound": 0 if lo["factors"][name] is None else lo["factors"][name],
                                      "upper_bound": 100 if hi["factors"][name] is None else hi["factors"][name]} for name in FACTOR_NAMES}
            if lo["factors"]["cabin_pressure"] is None:
                hazards.append(f"{space.id} {phase}: no prototype pressure-factor weight is defined for this atmosphere; factor spans 0 to 100.")
            materials[phase] = list(local.values())
        rooms.append({"id": space.id, "name": space.name, "scores": scores, "factors": factors, "materials": materials})
    stocked = [s for s in req.spaces if s.items]
    ship, factor_summary, ship_bounds = {}, {}, {}
    for phase in phases:
        unknown = any(s["points"] is None for loc in screens[phase].values() for s in loc.values())
        bounds = [ship_value([values[phase][s.id][b]["score"] for s in stocked]) for b in (0, 1)]
        ship_bounds[phase] = bounds
        ship[phase] = score_result(*bounds, unknown, "Weighted maximum and mean of stocked-room scores.")
        factor_summary[phase] = {}
        for name in FACTOR_NAMES:
            fs = [r["factors"][phase][name] for r in rooms if any(s.id == r["id"] for s in stocked)]
            factor_summary[phase][name] = {"lower_bound": sum(f["lower_bound"] for f in fs)/len(fs) if fs else 0,
                                           "upper_bound": sum(f["upper_bound"] for f in fs)/len(fs) if fs else 0,
                                           "min": min((f["lower_bound"] for f in fs), default=0), "max": max((f["upper_bound"] for f in fs), default=0)}
    overall_bounds = [combine(ship_bounds["cruise"][b], ship_bounds.get("surface", ship_bounds["cruise"])[b], req) for b in (0, 1)]
    unknown = any(s["status"] == "insufficient data" for s in ship.values())
    actions = []
    for room in rooms:
        if any(s["points"] is None for phase in phases for s in room["materials"][phase]):
            actions.append({"severity": "review", "space": room["id"], "title": "Obtain same-material combustion evidence before relying on a single score."})
    actions.extend(suggest_moves(req, phases, screens, values, screen_for))
    for space in stocked:
        if any(is_ignition(i) for i in space.items) and not any(i.equipment == "smoke_detector" for i in space.items):
            actions.append({"severity": "review", "space": space.id, "title": "Review smoke detection near ignition sources."})
    return PlannerResponse(phases=phases, ship=ship,
        overall=score_result(*overall_bounds, unknown, "Cruise score alone, or severity and duration weighted cruise/surface scores."),
        rooms=rooms, factors=factor_summary, actions=actions[:5], hazards=list(dict.fromkeys(hazards)),
        model_info={"version": VERSION, "basis": "prototype_with_experiment_material_screens", "ai_used": False,
                    "material_points": POINTS, "unknown_points_range": [1, 3],
                    "prototype_weights": ["evidence-to-points mapping", "volume size factors", "ignition and oxygen proximity", "safety equipment credits", "phase and duration adjustments", "seven factor formulas", "room and spacecraft aggregation"],
                    "thickness_assumption": "minimum item dimension is a proxy, not measured wall or fabric thickness",
                    "proximity_assumption": "same space means near; grid Manhattan adjacency defines neighboring modules"})


def suggest_moves(req, phases, screens, values, screen_for):
    """Try each destination; compare combined uncapped scores of affected rooms.

    Unknown materials anywhere disable optimization, so missing evidence cannot
    make a destination appear safe. Suggestions are independent, not a batch.
    """
    if any(s["points"] is None for phase in phases for local in screens[phase].values() for s in local.values()):
        return []
    moves = []
    for source in req.spaces:
        for item in source.items:
            if not any(screens[p][source.id].get(item.id, {}).get("points", 0) >= 2 for p in phases):
                continue
            if not (is_passage(source) or any(is_ignition(i) or i.oxygen_source for i in source.items)):
                continue
            best = None
            for target in req.spaces:
                if target.id == source.id:
                    continue
                src = source.model_copy(update={"items": [i for i in source.items if i.id != item.id]})
                dst = target.model_copy(update={"items": target.items+[item]})
                before, after = {}, {}
                valid = True
                for phase in phases:
                    atmosphere = req.scenario.cruise_atmosphere if phase == "cruise" else req.scenario.cabin_atmosphere
                    gravity = 0 if phase == "cruise" else .166 if req.mission == "lunar" else .375
                    moved = screen_for(item, atmosphere, target.airflow_cm_s, gravity)
                    if moved["points"] is None:
                        valid = False
                        break
                    before[phase] = sum(values[phase][s.id][0]["uncapped"] for s in (source, target))
                    after[phase] = 0
                    for updated, local in [(src, {k:v for k,v in screens[phase][source.id].items() if k != item.id}),
                                           (dst, {**screens[phase][target.id], item.id: moved})]:
                        neighbor = any(adjacent(updated, other) and any(is_ignition(i) for i in other.items) for other in req.spaces if other.id != updated.id)
                        after[phase] += room_values(updated, phase, req, local, 1, neighbor)["uncapped"]
                if not valid or any(after[p] > before[p] for p in phases):
                    continue
                old = combine(before["cruise"], before.get("surface", 0), req)
                new = combine(after["cruise"], after.get("surface", 0), req)
                reduction = old-new
                if reduction > 0 and (best is None or reduction > best["reduction"]):
                    best = {"severity": "improvement", "space": source.id, "item_id": item.id,
                            "target_space_id": target.id, "title": f"Review moving {item.name} to {target.name}.",
                            "combined_uncapped_before": round(old, 2), "combined_uncapped_after": round(new, 2), "reduction": round(reduction, 2)}
            if best:
                moves.append(best)
    return sorted(moves, key=lambda m: -m["reduction"])[:5]
