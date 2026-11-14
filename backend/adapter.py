"""Planner JSON (POST /api/assess) -> the inputs backend/scoring.py reads, and back.

Requests are handled as plain dicts (req.model_dump()) so actions.py can copy and
change them ("what if this item moved?") and re-score.
"""
import copy
from typing import Dict, List, Optional, Tuple

from . import data, scoring

PHASES = ("cruise", "surf")


def item_info(item: dict) -> dict:
    """The library entry for an item, or a stand-in built from the item's own fields."""
    lib = data.get_library_item(item.get("key"))
    if lib:
        return lib
    return {"key": item.get("key"), "name": item.get("name"), "category": item.get("category", "material"),
            "flammability": item.get("flammability"), "ignition_source": item.get("ignition_source", False),
            "oxygen_source": item.get("oxygen_source", False), "material_key": None,
            "swap": item.get("swap_to")}


def _scoring_item(item: dict) -> dict:
    lib = data.get_library_item(item.get("key"))
    l, w, h = item["cm"]
    return {
        "id": item["id"],
        # detectors/extinguishers are found by name in scoring.py, so use the library name
        "name": lib["name"] if lib and lib["category"] == "safety" else item["name"],
        "category": item.get("category", "material"),
        "material_key": (lib or {}).get("material_key"),
        "flammability": (item.get("flammability") or "").lower() or None,
        "ignition_source": bool(item.get("ignition_source")),
        "oxygen_source": bool(item.get("oxygen_source")),
        "quantity": item.get("qty", 1),
        "dimensions_cm": {"l": l, "w": w, "h": h},
    }


def to_scoring_input(req: dict) -> Tuple[List[dict], Dict[str, dict], Optional[Dict[str, List[dict]]]]:
    """-> (spaces, phases, spaces_by_phase) for scoring.score_mission."""
    cond = req["conditions"]
    spaces = [{"id": s["id"], "name": s["name"], "airflow_cm_s": s["airflow_cm_s"],
               "neighbours": list(s.get("neighbours") or []),
               "items": [_scoring_item(i) for i in s.get("items") or []]}
              for s in req["spaces"]]

    cruise = cond["cruise"]
    phases = {"cruise": {"oxygen_pct": cruise["o2_percent"], "gravity_g": 0.0, "days": cruise["cruise_days"]}}
    if cond.get("surface"):
        surf = cond["surface"]
        phases["surf"] = {"oxygen_pct": surf["o2_percent"], "gravity_g": surf["gravity_g"],
                          "days": surf["stay_days"]}

    by_phase = None
    if cruise.get("ventilation") == "reduced":  # reduced cruise ventilation halves airflow
        by_phase = {"cruise": [{**s, "airflow_cm_s": s["airflow_cm_s"] / 2} for s in spaces]}
    return spaces, phases, by_phase


def score(req: dict) -> dict:
    """Score a planner request. Rooms are keyed by space id:
    {"overall": {...}, "phases": {"cruise": {...}, "surf": {...}},
     "rooms": {space_id: {"cruise": room, "surf": room, "overall": float|None}}}"""
    spaces, phases, by_phase = to_scoring_input(req)
    res = scoring.score_mission(spaces, phases, by_phase)
    days = {p: phases[p]["days"] for p in phases}
    rooms = {}
    for i, s in enumerate(spaces):
        per = {p: res["rooms"][p][i] for p in phases}
        stocked = per["cruise"]["stocked"]
        overall = (scoring.overall_from_phases({p: r["score"] for p, r in per.items()}, days)
                   if stocked else None)
        rooms[s["id"]] = {**per, "overall": overall}
    return {"overall": res["overall"], "phases": res["phases"], "rooms": rooms,
            "phase_names": list(phases)}


def find_space(req: dict, space_id: str) -> Optional[dict]:
    return next((s for s in req["spaces"] if s["id"] == space_id), None)


def find_item(space: Optional[dict], item_id: str) -> Optional[dict]:
    if not space:
        return None
    return next((i for i in space.get("items") or [] if i["id"] == item_id), None)


def clone(req: dict) -> dict:
    return copy.deepcopy(req)
