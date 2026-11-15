"""Fixes, item moves and action checks for the Stowage Fire-Risk Planner.

Every suggestion is scored the same way as the ship itself: apply the change to a copy
of the request, re-score it with scoring.py, and report the real drop in points.
Only changes that lower the score are suggested.

Action shapes (handoff README):
  {"type": "swap", "room_id", "item_id", "to": "<the item's swap key>"}
  {"type": "add",  "room_id", "key": "ext" | "det" | "mask"}
  {"type": "move", "item_id", "from_id", "to_id"}
"""
from typing import Dict, List, Optional

from . import adapter, data

ADDABLE = ("ext", "det", "mask")
MAX_FIXES_PER_ROOM = 3
MAX_MOVES = 5
MAX_TARGET_SCORE = 60.0   # never suggest moving fuel into a space rated High (>60) or worse


# ------------------------------------------------------------------ validation

def _swap_target(item: dict) -> Optional[str]:
    return item.get("swap_to") or adapter.item_info(item).get("swap")


def _has_key(space: dict, key: str) -> bool:
    lib = data.get_library_item(key) or {}
    return any(i.get("key") == key or (lib.get("name") and i.get("name") == lib["name"])
               for i in space.get("items") or [])


def validate_action(action: Optional[dict], req: dict) -> Optional[dict]:
    """Return a clean copy of the action, or None if it doesn't apply to this ship.
    Drops unknown ids/keys, a swap to anything but the item's swap, an add of something
    the room already has, and a move into a passage or into the same room."""
    if not isinstance(action, dict):
        return None
    kind = action.get("type")

    if kind == "swap":
        room = adapter.find_space(req, action.get("room_id"))
        item = adapter.find_item(room, action.get("item_id"))
        to = action.get("to")
        if not item or not to or to == item.get("key") or not data.get_library_item(to):
            return None
        if to != _swap_target(item):
            return None
        return {"type": "swap", "room_id": room["id"], "item_id": item["id"], "to": to}

    if kind == "add":
        room = adapter.find_space(req, action.get("room_id"))
        key = action.get("key")
        if not room or key not in ADDABLE or _has_key(room, key):
            return None
        return {"type": "add", "room_id": room["id"], "key": key}

    if kind == "move":
        src = adapter.find_space(req, action.get("from_id"))
        dst = adapter.find_space(req, action.get("to_id"))
        item = adapter.find_item(src, action.get("item_id"))
        if not item or not dst or dst["id"] == src["id"] or dst.get("passage"):
            return None
        return {"type": "move", "item_id": item["id"], "from_id": src["id"], "to_id": dst["id"]}

    return None


# ------------------------------------------------------------------ applying

def _library_item(key: str, item_id: str, qty: int = 1, cm: Optional[List[float]] = None) -> dict:
    lib = data.get_library_item(key)
    return {"id": item_id, "key": key, "name": lib["name"], "category": lib["category"],
            "flammability": lib.get("flammability"), "ignition_source": lib.get("ignition_source", False),
            "oxygen_source": lib.get("oxygen_source", False), "qty": qty,
            "cm": list(cm or lib.get("default_cm") or [10, 10, 10]),
            "bagged": lib.get("bagged"), "swap_to": lib.get("swap")}


def apply_action(req: dict, action: dict) -> dict:
    """A copy of the request with a VALID action applied (call validate_action first)."""
    new = adapter.clone(req)
    if action["type"] == "swap":
        room = adapter.find_space(new, action["room_id"])
        old = adapter.find_item(room, action["item_id"])
        room["items"][room["items"].index(old)] = _library_item(action["to"], old["id"], old["qty"], old["cm"])
    elif action["type"] == "add":
        room = adapter.find_space(new, action["room_id"])
        room["items"].append(_library_item(action["key"], f"new-{action['key']}-{room['id']}"))
    elif action["type"] == "move":
        src = adapter.find_space(new, action["from_id"])
        dst = adapter.find_space(new, action["to_id"])
        item = adapter.find_item(src, action["item_id"])
        src["items"].remove(item)
        dst["items"].append(item)
    return new


def label(action: dict, req: dict) -> str:
    """Button text, as in the prototype: 'Swap X → Y', 'Add smoke detector to Z', 'Move X to Z'."""
    if action["type"] == "swap":
        item = adapter.find_item(adapter.find_space(req, action["room_id"]), action["item_id"])
        return f"Swap {item['name']} → {data.get_library_item(action['to'])['name']}"
    if action["type"] == "add":
        room = adapter.find_space(req, action["room_id"])
        return f"Add {data.get_library_item(action['key'])['name'].lower()} to {room['name']}"
    item = adapter.find_item(adapter.find_space(req, action["from_id"]), action["item_id"])
    return f"Move {item['name']} to {adapter.find_space(req, action['to_id'])['name']}"


def points(req: dict, action: dict, base: Optional[dict] = None, room_id: Optional[str] = None) -> Dict[str, float]:
    """Real score drop from applying the action: {'ship': ..., 'room': ...} (positive = safer)."""
    base = base or adapter.score(req)
    after = adapter.score(apply_action(req, action))
    out = {"ship": round(base["overall"]["score"] - after["overall"]["score"], 1)}
    if room_id:
        b, a = base["rooms"][room_id]["overall"], after["rooms"][room_id]["overall"]
        out["room"] = round((b or 0) - (a or 0), 1)
    return out


# ------------------------------------------------------------------ fixes per room

def _is_flammable(item: dict) -> bool:
    return adapter.item_info(item).get("flammability") in ("Moderate", "High") \
        or item.get("flammability") in ("Moderate", "High")


def _fix_text(action: dict, req: dict, room: dict) -> Dict[str, str]:
    """Plain title + reason for a fix (Gemini may rewrite the reason; numbers are checked)."""
    if action["type"] == "swap":
        item = adapter.find_item(room, action["item_id"])
        to = data.get_library_item(action["to"])
        return {"title": f"Swap {item['name']} for {to['name']}",
                "why": f"{item.get('flammability') or 'Flammable'} item; the swap is rated {to.get('flammability') or 'lower'}"}
    if action["key"] == "det":
        return {"title": "Add a smoke detector", "why": "No smoke detection in this space"}
    if action["key"] == "ext":
        return {"title": "Add a portable extinguisher", "why": "Fuel is stowed with no extinguisher in reach"}
    return {"title": "Add an emergency breathing mask", "why": "No breathing mask in this space"}


def candidate_fixes(req: dict, room_id: str, base: Optional[dict] = None) -> List[dict]:
    """Up to 3 fixes for one stocked room, biggest real drop first.
    Each: {title, why, points (room), ship_points, action}."""
    base = base or adapter.score(req)
    room = adapter.find_space(req, room_id)
    if not room or not base["rooms"][room_id]["overall"]:
        return []
    tries = []
    for item in room.get("items") or []:
        to = _swap_target(item)
        if to and _is_flammable(item):
            tries.append({"type": "swap", "room_id": room_id, "item_id": item["id"], "to": to})
    has_fuel = any(i.get("category", "material") == "material" for i in room.get("items") or [])
    has_ign = any(i.get("ignition_source") for i in room.get("items") or [])
    if has_fuel or has_ign:  # as in the prototype: DET needed with fuel or ignition, EXT with fuel
        tries.append({"type": "add", "room_id": room_id, "key": "det"})
    if has_fuel:
        tries.append({"type": "add", "room_id": room_id, "key": "ext"})

    fixes = []
    for a in tries:
        a = validate_action(a, req)
        if not a:
            continue
        p = points(req, a, base, room_id)
        if p["room"] > 0:
            fixes.append({**_fix_text(a, req, room), "points": p["room"], "ship_points": p["ship"], "action": a})
    fixes.sort(key=lambda f: (-f["points"], -f["ship_points"]))
    return fixes[:MAX_FIXES_PER_ROOM]


# ------------------------------------------------------------------ moves

def _has_source(space: dict) -> bool:
    return any(i.get("ignition_source") or i.get("oxygen_source") for i in space.get("items") or [])


def find_moves(req: dict, base: Optional[dict] = None) -> List[dict]:
    """Up to 5 item moves that lower the ship's overall score, biggest drop first.
    Candidates (as in the prototype): Moderate/High flammables in a space with an ignition
    or oxygen source, or in a passage. Targets: other non-passage spaces with no ignition
    or oxygen source (moving fuel next to a heater or an O2 outlet is never suggested), that are
    not rated High or worse, and that stay at Elevated or below after the move."""
    base = base or adapter.score(req)
    moves = []
    for src in req["spaces"]:
        if not (_has_source(src) or src.get("passage")):
            continue
        for item in src.get("items") or []:
            if item.get("category", "material") != "material" or not _is_flammable(item):
                continue
            best = None
            for dst in req["spaces"]:
                if _has_source(dst) or (base["rooms"][dst["id"]]["overall"] or 0) > MAX_TARGET_SCORE:
                    continue
                a = validate_action({"type": "move", "item_id": item["id"], "from_id": src["id"],
                                     "to_id": dst["id"]}, req)
                if not a:
                    continue
                after = adapter.score(apply_action(req, a))
                if (after["rooms"][dst["id"]]["overall"] or 0) > MAX_TARGET_SCORE:
                    continue  # the move would make the target High or worse
                drop = round(base["overall"]["score"] - after["overall"]["score"], 1)
                if drop > 0 and (best is None or drop > best[0]):
                    best = (drop, dst)
            if best:
                drop, dst = best
                why = "no ignition or oxygen source there"
                if src.get("passage"):
                    why = "clears cargo from a passage; " + why
                else:
                    why = "away from the " + ("oxygen outlet" if any(i.get("oxygen_source") for i in src["items"])
                                              else "ignition sources") + "; " + why
                moves.append({"item_id": item["id"], "item": item["name"], "qty": item.get("qty", 1),
                              "from_id": src["id"], "from_name": src["name"],
                              "to_id": dst["id"], "to_name": dst["name"],
                              "reason": why[0].upper() + why[1:], "points": drop})
    moves.sort(key=lambda m: -m["points"])
    return moves[:MAX_MOVES]
