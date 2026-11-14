"""Fire-risk scores (0-100) for the Stowage Fire-Risk Planner.

How a score is built
--------------------
1. Material hazard M (0-100), from our NASA test data:
     T = the oxygen % where a material switches from "went out" to "burned"
     M = 50 + 8 x (cabin oxygen - T), kept between 5 and 95
   - burned and failed in the data -> T = halfway between highest "failed" and lowest "burned"
   - only burned                  -> T = lowest "burned" - 1   (it would likely burn a bit lower)
   - only failed                  -> T = highest tested + 1    (it held up there)
   - liquid fuels                 -> T = published limiting oxygen index (LIQUID_LOI)
   - never burned and the cabin is above anything tested -> M = 60 + "untested" gap
   - no tests at all              -> estimate: the item's guessed level at 21% oxygen,
                                     then the same 8 points per 1%; evidence "none"
2. Room score per phase (0-100):
     0.45 x material hazard + 0.20 x fuel load + 0.15 x ignition/oxygen sources
     + 0.10 x airflow + 0.10 x thickness - 5 per smoke detector - 5 per extinguisher
3. Ship score per phase:   0.6 x riskiest stocked room + 0.4 x average stocked room
4. Overall (cruise + surface): 0.6 x worse phase + 0.4 x day-weighted average

The weights in steps 2-4 are design choices (from the prototype), not measurements.
Evidence strength is reported next to every score and is never mixed into it.

Input shape: the prototype's request JSON ("spaces" -> "items").
"""
import math
from functools import lru_cache
from typing import Dict, List, Optional

from . import data

# ------------------------------------------------------------------ settings

POINTS_PER_PCT_OXYGEN = 8.0         # M changes 8 points per 1% oxygen above/below T
MATERIAL_MIN, MATERIAL_MAX = 5.0, 95.0
UNTESTED_ABOVE_SCORE = 60.0          # never burned, but cabin oxygen is above all its tests
NEAR_OXYGEN_PCT = 3.0                # tests within 3% oxygen count as "near" for evidence
STRONG_EVIDENCE_TESTS = 10

# Published limiting oxygen index for droplet fuels (FLEX, O2/N2 at ~1 atm):
# methanol 12%, heptane 15%. Droplet flames "going out" in FLEX is extinction
# after burning, not a failure to ignite, so the data alone can't give T.
LIQUID_LOI = {"methanol": 12.0, "heptane": 15.0}

# Fallback when a material has no tests: the prototype's guessed level sets M at
# normal cabin air (21%), and it still rises/falls 8 points per 1% oxygen like tested ones.
HINT_SCORE = {"low": 30.0, "moderate": 50.0, "high": 70.0}
DEFAULT_NO_DATA_SCORE = 50.0
REFERENCE_OXYGEN_PCT = 21.0

BURNED = {"burned", "ignited"}
DID_NOT_BURN = {"self-extinguished", "no ignition", "no spread", "blowoff"}

WEIGHTS = {"material": 0.45, "fuel": 0.20, "sources": 0.15, "airflow": 0.10, "thickness": 0.10}
DETECTOR_CREDIT = 5.0
EXTINGUISHER_CREDIT = 5.0

LEVELS = [(20, "Low"), (40, "Guarded"), (60, "Elevated"), (80, "High"), (100, "Severe")]


def level(score: float) -> str:
    for upper, name in LEVELS:
        if score <= upper:
            return name
    return "Severe"


def _clamp(v: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, v))


def _num(v) -> Optional[float]:
    if v is None:
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return None if math.isnan(f) else f


# ------------------------------------------------------------------ 1. material hazard

@lru_cache(maxsize=1)
def material_profiles() -> Dict[str, dict]:
    """Burn threshold + evidence for every material in the verified data (computed once)."""
    df = data.load_experiments()
    profiles = {}
    for key, rows in df.groupby(df["material"].fillna("")):
        if not key:
            continue
        burned = rows[rows["outcome_category"].isin(BURNED)]
        failed = rows[rows["outcome_category"].isin(DID_NOT_BURN)]
        lo_cols = ["oxygen_pct_min", "oxygen_pct_max"]
        lowest_burn = burned[lo_cols].min(axis=1).min() if not burned.empty else None
        highest_fail = failed[lo_cols].max(axis=1).max() if not failed.empty else None
        max_tested = rows[lo_cols].max(axis=1).max()
        oxygen_values = rows[lo_cols].mean(axis=1).dropna().tolist()

        lowest_burn, highest_fail, max_tested = map(_num, (lowest_burn, highest_fail, max_tested))
        k = key.lower()
        if k in LIQUID_LOI:
            threshold, basis = LIQUID_LOI[k], "published limiting oxygen index"
        elif lowest_burn is not None and highest_fail is not None:
            threshold = (lowest_burn + highest_fail) / 2
            basis = f"burned from {lowest_burn:g}%, went out at {highest_fail:g}% or below"
        elif lowest_burn is not None:
            threshold = lowest_burn - 1
            basis = f"burned in every test, from {lowest_burn:g}%"
        elif highest_fail is not None:
            threshold = (max_tested or highest_fail) + 1
            basis = f"never burned in tests up to {max_tested:g}%"
        else:
            threshold, basis = None, "outcomes not reported"

        profiles[k] = {
            "material": key,
            "threshold_pct": threshold,
            "basis": basis,
            "ever_burned": lowest_burn is not None,
            "max_tested_pct": max_tested,
            "n_tests": int(len(rows)),
            "oxygen_values": oxygen_values,
        }
    return profiles


def material_hazard(material_key: Optional[str], oxygen_pct: float,
                    flammability_hint: Optional[str] = None) -> dict:
    """M (0-100) for one material at one cabin oxygen level, with evidence and any gap."""
    prof = material_profiles().get((material_key or "").strip().lower())
    hint_score = HINT_SCORE.get((flammability_hint or "").strip().lower(), DEFAULT_NO_DATA_SCORE)

    if prof is None or prof["threshold_pct"] is None:
        est = _clamp(hint_score + POINTS_PER_PCT_OXYGEN * (oxygen_pct - REFERENCE_OXYGEN_PCT),
                     MATERIAL_MIN, MATERIAL_MAX)
        if (flammability_hint or "").strip().lower() == "low":
            # same ceiling as tested materials that never burned: a guess can't outrank a test
            est = min(est, max(hint_score, UNTESTED_ABOVE_SCORE))
        return {"score": round(est, 1), "evidence": "none", "n_tests": 0, "threshold_pct": None,
                "basis": "no NASA test data; estimate from the item's flammability level",
                "gap": "no NASA test data; score is an estimate"}

    near = sum(1 for o in prof["oxygen_values"] if abs(o - oxygen_pct) <= NEAR_OXYGEN_PCT)
    evidence = "strong" if near >= STRONG_EVIDENCE_TESTS else "limited"
    gap = None

    if (not prof["ever_burned"] and prof["max_tested_pct"] is not None
            and oxygen_pct > prof["max_tested_pct"] + 1):
        score = UNTESTED_ABOVE_SCORE
        gap = f"never tested above {prof['max_tested_pct']:g}% oxygen"
        evidence = "limited"
    else:
        score = _clamp(50 + POINTS_PER_PCT_OXYGEN * (oxygen_pct - prof["threshold_pct"]),
                       MATERIAL_MIN, MATERIAL_MAX)
        if near == 0:
            gap = f"no tests within {NEAR_OXYGEN_PCT:g}% of {oxygen_pct:g}% oxygen"

    return {"score": round(score, 1), "evidence": evidence, "n_tests": prof["n_tests"],
            "threshold_pct": round(prof["threshold_pct"], 1), "basis": prof["basis"], "gap": gap}


# ------------------------------------------------------------------ 2. room factors

def _is(item: dict, word: str) -> bool:
    return word in str(item.get("name", "")).lower()


def _volume_liters(item: dict) -> Optional[float]:
    d = item.get("dimensions_cm") or {}
    l, w, h = _num(d.get("l")), _num(d.get("w")), _num(d.get("h"))
    if None in (l, w, h):
        return None
    return l * w * h * max(1, int(_num(item.get("quantity")) or 1)) / 1000.0


def _flam_points(m_score: float) -> int:
    return 3 if m_score >= 70 else 2 if m_score >= 40 else 1


def fuel_factor(materials: List[dict]) -> float:
    """Prototype's fuel load: flammability points x size factor (1-4, +1 per 5 L)."""
    load, highly = 0.0, 0
    for it in materials:
        vol = _volume_liters(it)
        size = 1 if vol is None else min(4, 1 + int(vol // 5))
        load += _flam_points(it["_hazard"]["score"]) * size
        highly += it["_hazard"]["score"] >= 70
    return _clamp(load / 14 * 100 + 5 * highly)


def sources_factor(materials: List[dict], ignition: List[dict], oxygen: List[dict],
                   neighbor_has_ignition: bool) -> float:
    """Prototype's proximity factor, plus oxygen sources next to flammables."""
    flammable = [it for it in materials if it["_hazard"]["score"] >= 40]
    n_ign = sum(max(1, int(_num(i.get("quantity")) or 1)) for i in ignition)
    if flammable and n_ign:
        score = 45 + 12 * n_ign
    elif flammable and neighbor_has_ignition:
        score = 35
    elif n_ign:
        score = 20
    else:
        score = 0
    if oxygen and flammable:
        score += 25
    return _clamp(score)


def airflow_factor(airflow_cm_s: Optional[float]) -> float:
    """Too little: smoke slow to reach detectors. Too much: feeds a flame."""
    v = _num(airflow_cm_s)
    if v is None:
        return 40.0
    if v < 5:
        return _clamp(75 - 8 * v)
    if v <= 15:
        return 20.0
    return _clamp(20 + 6 * (v - 15))


def thickness_factor(materials: List[dict]) -> float:
    """Thin flammables ignite and spread more easily."""
    flammable = [it for it in materials if it["_hazard"]["score"] >= 40]
    if not flammable:
        return 0.0
    thinnest = []
    for it in flammable:
        d = it.get("dimensions_cm") or {}
        dims = [x for x in (_num(d.get("l")), _num(d.get("w")), _num(d.get("h"))) if x is not None]
        if len(dims) == 3:
            thinnest.append(min(dims))
    if not thinnest:
        return 40.0
    t = min(thinnest)
    return 85.0 if t < 0.5 else 55.0 if t < 2 else 35.0 if t < 5 else 20.0


# ------------------------------------------------------------------ 2. room score

def score_room(space: dict, oxygen_pct: float, gravity_g: float = 0.0,
               neighbor_has_ignition: bool = False) -> dict:
    """One space (prototype JSON) at one phase's oxygen level."""
    items = space.get("items") or []
    materials, ignition, oxygen = [], [], []
    detectors = extinguishers = 0
    for it in items:
        if _is(it, "detector"):
            detectors += max(1, int(_num(it.get("quantity")) or 1))
            continue
        if _is(it, "extinguisher"):
            extinguishers += max(1, int(_num(it.get("quantity")) or 1))
            continue
        if it.get("oxygen_source"):
            oxygen.append(it)
        if it.get("ignition_source"):
            ignition.append(it)
        if it.get("category", "material") == "material" and not it.get("ignition_source"):
            hz = material_hazard(it.get("material_key"), oxygen_pct, it.get("flammability"))
            materials.append({**it, "_hazard": hz})

    if not materials and not ignition and not oxygen:
        return {"name": space.get("name"), "score": 0.0, "level": "Low", "stocked": False,
                "factors": {}, "items": [], "gaps": []}

    hazards = [m["_hazard"]["score"] for m in materials]
    material_score = (0.6 * max(hazards) + 0.4 * sum(hazards) / len(hazards)) if hazards else 0.0
    factors = {
        "material": round(material_score, 1),
        "fuel": round(fuel_factor(materials), 1),
        "sources": round(sources_factor(materials, ignition, oxygen, neighbor_has_ignition), 1),
        "airflow": round(airflow_factor(space.get("airflow_cm_s")), 1),
        "thickness": round(thickness_factor(materials), 1),
    }
    raw = sum(WEIGHTS[k] * v for k, v in factors.items())
    raw -= DETECTOR_CREDIT * min(detectors, 1) + EXTINGUISHER_CREDIT * min(extinguishers, 1)
    score = round(_clamp(raw), 1)

    gaps = []
    for m in materials:
        if m["_hazard"]["gap"]:
            gaps.append(f"{m.get('name') or m.get('material_key')}: {m['_hazard']['gap']}")
    if gravity_g and gravity_g > 0:
        gaps.append("No partial-gravity combustion data yet; scores use microgravity tests.")

    return {
        "name": space.get("name"),
        "score": score,
        "level": level(score),
        "stocked": True,
        "factors": factors,
        "items": [{"name": m.get("name"), "material_key": m.get("material_key"),
                   "hazard": m["_hazard"]["score"], "evidence": m["_hazard"]["evidence"],
                   "basis": m["_hazard"]["basis"]} for m in materials],
        "gaps": list(dict.fromkeys(gaps)),
    }


# ------------------------------------------------------------------ 3-4. ship + overall

def score_ship(spaces: List[dict], oxygen_pct: float, gravity_g: float = 0.0) -> dict:
    """All spaces at one phase. Neighbors are spaces whose positions touch (prototype x/y grid)."""
    def pos(s):
        p = s.get("position") or {}
        return _num(p.get("x")), _num(p.get("y"))

    def has_ignition(s):
        return any(it.get("ignition_source") for it in s.get("items") or [])

    rooms = []
    for s in spaces:
        x, y = pos(s)
        neighbor_ign = False
        if x is not None and y is not None:
            for other in spaces:
                ox, oy = pos(other)
                if other is not s and ox is not None and oy is not None \
                        and abs(ox - x) + abs(oy - y) == 1 and has_ignition(other):
                    neighbor_ign = True
                    break
        rooms.append(score_room(s, oxygen_pct, gravity_g, neighbor_ign))

    stocked = [r["score"] for r in rooms if r["stocked"]]
    ship = round(0.6 * max(stocked) + 0.4 * sum(stocked) / len(stocked), 1) if stocked else 0.0
    return {"score": ship, "level": level(ship), "rooms": rooms}


def overall_from_phases(phase_scores: Dict[str, float], days: Dict[str, float]) -> float:
    """0.6 x worse phase + 0.4 x day-weighted average (one phase -> that phase's score)."""
    if len(phase_scores) == 1:
        return next(iter(phase_scores.values()))
    d = {n: max(0.0, _num(days.get(n)) or 0.0) for n in phase_scores}
    total = sum(d.values())
    if total == 0:
        d, total = {n: 1.0 for n in phase_scores}, float(len(phase_scores))
    weighted = sum(phase_scores[n] * d[n] for n in phase_scores) / total
    return round(0.6 * max(phase_scores.values()) + 0.4 * weighted, 1)


def score_mission(spaces: List[dict], phases: Dict[str, dict],
                  spaces_by_phase: Optional[Dict[str, List[dict]]] = None) -> dict:
    """phases = {"cruise": {"oxygen_pct", "gravity_g", "days"},
                 "surface": {"oxygen_pct", "gravity_g", "days"}}   (surface optional)
    spaces_by_phase: optional per-phase copies of the spaces (e.g. reduced cruise airflow).
    Returns per-phase ship + room scores and the overall score."""
    results = {}
    for name, p in phases.items():
        phase_spaces = (spaces_by_phase or {}).get(name, spaces)
        results[name] = score_ship(phase_spaces, float(p["oxygen_pct"]), float(p.get("gravity_g") or 0))

    overall = overall_from_phases({n: r["score"] for n, r in results.items()},
                                  {n: phases[n].get("days") for n in results})
    return {
        "overall": {"score": overall, "level": level(overall)},
        "phases": {n: {"score": r["score"], "level": r["level"]} for n, r in results.items()},
        "rooms": {n: r["rooms"] for n, r in results.items()},
    }
