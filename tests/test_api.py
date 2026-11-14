"""Tests for the Stowage Fire-Risk Planner API (GET /library, POST /api/assess, POST /api/chat).
Gemini is replaced with fakes, so these run offline:  python -m pytest -q tests
"""
import copy
import json
import os
from pathlib import Path

import pytest

os.environ.setdefault("GEMINI_API_KEY", "test")
os.environ.setdefault("ASSESSMENT_LOG", str(Path(__file__).parent / ".assessments-test.jsonl"))

from fastapi.testclient import TestClient  # noqa: E402

from backend import actions, adapter, ai, api, main  # noqa: E402
from backend.api_schemas import AssessRequest  # noqa: E402

FIX = Path(__file__).parent / "fixtures"
client = TestClient(main.app)


def load(name):
    return json.loads((FIX / f"{name}.json").read_text())


def ai_down(*a, **k):
    raise ai.AIUnavailable("503 overloaded")


@pytest.fixture(autouse=True)
def fresh(monkeypatch):
    api._cache.clear()
    monkeypatch.setattr(ai, "planner_text", ai_down)
    monkeypatch.setattr(ai, "planner_chat", ai_down)
    yield
    log = Path(os.environ["ASSESSMENT_LOG"])
    if log.exists():
        log.unlink()


def assess(body):
    r = client.post("/api/assess", json=body)
    assert r.status_code == 200, r.text
    return r.json()


# ------------------------------------------------------------------ library

def test_library_has_prototype_items_and_psi_keys():
    lib = {x["key"]: x for x in client.get("/library").json()}
    assert len(lib) == 42
    assert lib["pmma"]["material_key"] == "PMMA"
    assert lib["towels"]["swap"] == "nomexbag"
    assert lib["oxygen"]["oxygen_source"] and not lib["oxygen"]["ignition_source"]


# ------------------------------------------------------------------ assess

@pytest.mark.parametrize("name", ["iss_moon", "transit_mars"])
def test_assess_scores_are_code_and_in_range(name):
    j = assess(load(name))
    assert j["text_source"] == "template"  # AI down -> still 200
    for r in j["rooms"]:
        if r["stocked"]:
            for v in (r["cruise"], r["surf"], r["overall"]):
                assert 0 <= v <= 100
        else:
            assert r["cruise"] is None and r["overall"] is None
    ph = j["phases"]
    assert j["overall"]["driver"] == max(ph, key=lambda p: ph[p]["score"])
    assert ph["cruise"]["score"] <= j["overall"]["score"] + 1e-9 or ph["surf"]["score"] >= j["overall"]["score"]
    assert [f["key"] for f in j["factors"]] == ["material", "fuel", "sources", "airflow", "thickness"]
    assert len(j["moves"]) <= 5 and all(m["points"] > 0 for m in j["moves"])
    assert any("Not in the score yet" in g for g in j["data_gaps"])


def test_moon_adds_partial_gravity_gap_and_cruise_only_has_no_surface():
    j = assess(load("iss_moon"))
    assert any("partial-gravity" in g for g in j["data_gaps"])
    body = load("iss_moon")
    body["conditions"]["surface"] = None
    j = assess(body)
    assert set(j["phases"]) == {"cruise"} and j["overall"]["driver"] == "cruise"
    assert j["overall"]["score"] == j["phases"]["cruise"]["score"]


def test_reduced_ventilation_changes_cruise_only():
    base = assess(load("iss_moon"))
    body = load("iss_moon")
    body["conditions"]["cruise"]["ventilation"] = "reduced"
    red = assess(body)
    assert red["phases"]["surf"] == base["phases"]["surf"]
    assert red["phases"]["cruise"] != base["phases"]["cruise"]


def test_fix_points_equal_real_rescore():
    req = AssessRequest(**load("iss_moon")).model_dump()
    j = assess(load("iss_moon"))
    room = next(r for r in j["rooms"] if r["fixes"])
    fix = room["fixes"][0]
    after = adapter.score(actions.apply_action(req, fix["action"]))
    assert round(room["overall"] - after["rooms"][room["id"]]["overall"], 1) == fix["points"]
    assert round(j["overall"]["score"] - after["overall"]["score"], 1) == fix["ship_points"]


def test_moves_never_target_passages_or_sources():
    body = load("transit_mars")
    req = AssessRequest(**body).model_dump()
    for m in assess(body)["moves"]:
        dst = adapter.find_space(req, m["to_id"])
        assert not dst["passage"]
        assert not any(i["ignition_source"] or i["oxygen_source"] for i in dst["items"])


def test_input_hash_is_stable():
    assert assess(load("iss_moon"))["input_hash"] == assess(load("iss_moon"))["input_hash"]


def test_bad_input_is_422():
    body = load("iss_moon")
    body["spaces"][0]["items"][0]["cm"] = [10, 10]
    assert client.post("/api/assess", json=body).status_code == 422
    body = load("iss_moon")
    body["spaces"][1]["id"] = body["spaces"][0]["id"]
    assert client.post("/api/assess", json=body).status_code == 422


def test_ai_text_with_wrong_number_falls_back(monkeypatch):
    calls = []

    def liar(facts, g=0):
        calls.append(1)
        return {"summary": "Overall is 88.4, driven by surface.", "rooms": {}, "fixes": {}}
    monkeypatch.setattr(ai, "planner_text", liar)
    j = assess(load("iss_moon"))
    assert j["text_source"] == "template" and len(calls) == 2


def test_good_ai_text_is_used(monkeypatch):
    body = load("iss_moon")
    first = assess(body)
    api._cache.clear()
    sid = next(r["id"] for r in first["rooms"] if r["stocked"])
    score = first["overall"]["score"]

    def good(facts, g=0):
        return {"summary": f"Surface drives the overall score of {score}. Foam beside the oxygen outlet matters most.",
                "rooms": {sid: "Cotton clothing has no NASA test data and sits in low airflow."}, "fixes": {}}
    monkeypatch.setattr(ai, "planner_text", good)
    j = assess(body)
    assert j["text_source"] == "ai"
    assert next(r for r in j["rooms"] if r["id"] == sid)["rationale"].startswith("Cotton")


# ------------------------------------------------------------------ actions

def test_validate_action_rules():
    req = AssessRequest(**load("iss_moon")).model_dump()
    sp = {s["name"]: s for s in req["spaces"]}
    stow, lab, galley = sp["PMM Stowage & Logistics"], sp["Destiny Lab"], sp["Node 1 Galley"]
    cotton = next(i for i in stow["items"] if i["key"] == "cotton")
    v = actions.validate_action
    assert v({"type": "swap", "room_id": stow["id"], "item_id": cotton["id"], "to": "nomexbag"}, req)
    assert v({"type": "swap", "room_id": stow["id"], "item_id": cotton["id"], "to": "melamine"}, req) is None
    assert v({"type": "swap", "room_id": stow["id"], "item_id": "nope", "to": "nomexbag"}, req) is None
    assert v({"type": "add", "room_id": stow["id"], "key": "det"}, req) is None      # already has one
    assert v({"type": "add", "room_id": galley["id"], "key": "det"}, req)
    assert v({"type": "add", "room_id": galley["id"], "key": "printer"}, req) is None
    assert v({"type": "move", "item_id": cotton["id"], "from_id": stow["id"], "to_id": stow["id"]}, req) is None
    assert v({"type": "move", "item_id": cotton["id"], "from_id": stow["id"], "to_id": lab["id"]}, req)


# ------------------------------------------------------------------ chat

def chat_body(text="What should I fix first?"):
    return {"tab": "overall", "messages": [{"role": "user", "text": text}], "assessment_input": load("iss_moon")}


def test_chat_ai_down_is_503():
    r = client.post("/api/chat", json=chat_body())
    assert r.status_code == 503


def test_chat_validates_and_scores_actions(monkeypatch):
    req = AssessRequest(**load("iss_moon")).model_dump()
    air = next(s for s in req["spaces"] if s["name"] == "Quest Airlock")
    foam = next(i for i in air["items"] if i["key"] == "foam")

    def reply(tab, history, ship, result, g=0):
        return {"reply": "Swap the foam in Quest Airlock first.",
                "actions": [{"type": "swap", "room_id": air["id"], "item_id": foam["id"], "to": "melamine"},
                            {"type": "move", "item_id": foam["id"], "from_id": air["id"], "to_id": "ghost"}]}
    monkeypatch.setattr(ai, "planner_chat", reply)
    j = client.post("/api/chat", json=chat_body()).json()
    assert j["text_source"] == "ai" and len(j["actions"]) == 1
    a = j["actions"][0]
    assert a["label"] == "Swap Polyurethane foam → Melamine foam" and a["points"] > 0


def test_chat_wrong_number_is_rejected(monkeypatch):
    monkeypatch.setattr(ai, "planner_chat", lambda *a, **k: {"reply": "The ship scores 97.3.", "actions": []})
    j = client.post("/api/chat", json=chat_body()).json()
    assert j["text_source"] == "fallback" and "97.3" not in j["reply"]


def test_other_endpoints_still_exist():
    paths = client.get("/openapi.json").json()["paths"]
    for p in ("/assess", "/experiments", "/placement", "/planner/assess", "/locations",
              "/library", "/api/assess", "/api/chat"):
        assert p in paths
    assert "/stowage/assess" not in paths
