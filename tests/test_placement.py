import unittest
from unittest.mock import patch
from fastapi import HTTPException
from pydantic import ValidationError
from backend import ai, main, placement
from backend.schemas import PlacementRequest


def option(kind="contain", location=None, action="Contain the item"):
    return {"type": kind, "location_id": location, "action": action, "why": "Engineering review is required for both phases."}


def location(ident, pre="low", surface="low"):
    return {"id": ident, "ratings": {"cruise": {"risk": pre}, "surface": {"risk": surface}}}


class PlacementTests(unittest.TestCase):
    def test_recommendation_tracks_original_option(self):
        raw = {"options": [option("move", "invented"), option()], "recommended": 1}
        result = ai._validate_placement(raw, set(), ["PMMA"])
        self.assertEqual(result["recommended"], 0)
        raw["recommended"] = 0
        self.assertIsNone(ai._validate_placement(raw, set(), ["PMMA"])["recommended"])

    def test_missing_phases_and_shared_scale(self):
        self.assertEqual(ai.overall_risk({}), "insufficient data")
        self.assertEqual(ai.overall_risk(location("x", "elevated", "low")["ratings"]), "elevated")
        self.assertEqual(ai.overall_risk(location("x", "low", "insufficient data")["ratings"]), "insufficient data")
        current = location("current", "high", "high")
        candidates = [location("unknown", "low", "insufficient data"), {"id": "missing"}, location("better", "elevated", "low")]
        self.assertEqual([c["id"] for c in ai._usable_candidates(current, candidates)], ["better"])
        self.assertIn("insufficient data", ai._fmt_ratings({}))

    def test_numbers_checked_in_every_text_field(self):
        raw = {"summary": "Safe for 999 seconds", "options": [option(action="Use 999 cm barrier"), option()],
               "recommended": 1, "data_gaps": ["Needs 999 psi", "Gravity is unvalidated."]}
        result = ai._validate_placement(raw, set(), ["PMMA"], "21% oxygen")
        self.assertNotIn("999", result["summary"])
        self.assertEqual(len(result["options"]), 1)
        self.assertEqual(result["recommended"], 0)
        self.assertEqual(result["data_gaps"], ["Gravity is unvalidated."])
        self.assertFalse(ai._placement_numbers_ok("Add 7 layers", "21% oxygen"))

    def test_endpoint_and_surface_gravity_gap(self):
        req = PlacementRequest(item={"name": "Panel", "materials": ["PMMA"]}, current_location_id="demo_cabin")
        with patch.object(ai, "ask_json", return_value={"summary": "Review phase ratings.", "options": [], "data_gaps": []}):
            result = main.placement_advice(req)
        self.assertTrue(result.evidence)
        self.assertFalse(any("Earth normal gravity" in g for g in result.data_gaps))
        self.assertTrue(any("surface gravity" in g for g in result.data_gaps))
        self.assertIn("/placement", main.app.openapi()["paths"])

    def test_missing_phase_request_and_ai_outage(self):
        req = PlacementRequest(item={"name": "Panel", "materials": ["PMMA"]}, current_location_id="custom",
                               locations=[{"id": "custom", "module": "Cabin", "crew_access": 3}])
        with patch.object(ai, "ask_json", side_effect=ai.AIUnavailable("offline")):
            result = placement.evaluate(req)
        self.assertEqual(result.overall, "insufficient data")
        self.assertEqual(result.options, [])
        self.assertTrue(any("unavailable" in g for g in result.data_gaps))

    def test_unknown_material_and_duplicate_locations(self):
        req = PlacementRequest(item={"name": "Panel", "materials": ["invented"]}, current_location_id="demo_cabin")
        with self.assertRaises(HTTPException) as error:
            placement.evaluate(req)
        self.assertEqual(error.exception.status_code, 400)
        req.item.materials = ["PMMA"]
        req.locations = placement.load_locations() * 2
        with self.assertRaises(HTTPException):
            placement.evaluate(req)

    def test_removed_prelaunch_field_is_rejected(self):
        with self.assertRaises(ValidationError):
            PlacementRequest(item={"name":"Panel","materials":["PMMA"]},current_location_id="x",
                             locations=[{"id":"x","module":"Cabin","crew_access":3,"conditions":{"pre_launch":None}}])

    def test_cruise_must_use_microgravity(self):
        req = PlacementRequest(item={"name": "Panel", "materials": ["PMMA"]}, current_location_id="demo_cabin")
        req.locations = placement.load_locations()
        req.locations[0].conditions.cruise.gravity_g = 1
        with self.assertRaises(HTTPException):
            placement.evaluate(req)


if __name__ == "__main__":
    unittest.main()
