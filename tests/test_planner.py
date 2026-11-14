import asyncio
import json
import math
import unittest
from unittest.mock import patch
import pandas as pd
from pydantic import ValidationError
from backend import data, main, planner
from backend.planner_schemas import Atmosphere, PlannerRequest


def item(ident="panel", material="PMMA", **kwargs):
    return {"id": ident, "name": ident, "material_key": material,
            "dimensions_cm": {"l": 10, "w": 10, "h": 10}, **kwargs}


def space(ident="lab", items=None, **kwargs):
    return {"id": ident, "name": ident, "airflow_cm_s": 10, "items": items or [], **kwargs}


def request(spaces=None, **kwargs):
    return PlannerRequest.model_validate({"spaces": spaces or [], **kwargs})


def rows(material="PMMA", outcome="burned", pressure=14.7):
    return pd.DataFrame([{"id": "TEST-A", "material": material, "fuel_type": "solid",
        "oxygen_pct_min": 21, "oxygen_pct_max": 21,
        "pressure_psi_min": pressure, "pressure_psi_max": pressure,
        "airflow_cm_s_min": 10, "airflow_cm_s_max": 10,
        "outcome_category": outcome, "outcome": "Burn time 20 s", "gravity": "microgravity"}])


class PlannerTests(unittest.TestCase):
    def test_bands_and_aggregation(self):
        self.assertEqual([planner.level(x) for x in [0,20,20.01,40,40.01,60,60.01,80,80.01,100]],
                         ["Low","Low","Guarded","Guarded","Elevated","Elevated","High","High","Severe","Severe"])
        self.assertAlmostEqual(planner.ship_value([20,80]), 68)
        req = request(mission="lunar")
        self.assertAlmostEqual(planner.combine(20,80,req), .6*80+.4*(20*180+80*30)/210)
        self.assertEqual(planner.combine(20,80,request()), 20)

    def test_same_material_only_and_unknown_outcomes(self):
        i = request([space(items=[item()])]).spaces[0].items[0]
        result = planner.material_screen(i, Atmosphere(), 10, 0, rows(material="silicone"))
        self.assertEqual(result["risk_level"], "insufficient data")
        self.assertIsNone(result["points"])
        unknown = planner.material_screen(i, Atmosphere(), 10, 0, rows(outcome="other"))
        self.assertEqual(unknown["risk_level"], "insufficient data")

    def test_low_requires_matching_conditions(self):
        i = request([space(items=[item()])]).spaces[0].items[0]
        result = planner.material_screen(i, Atmosphere(), 10, 0, rows(outcome="no ignition"))
        self.assertEqual(result["points"], 1)
        result = planner.material_screen(i, Atmosphere(), 10, 0, rows(outcome="no ignition", pressure=float("nan")))
        self.assertEqual(result["risk_level"], "elevated")
        self.assertTrue(result["data_gaps"])

    def test_volume_conversion_quantity_and_raw_arithmetic(self):
        # 10x10x10 cm = 1 L; quantity 5 = 5 L -> size factor 2.
        req = request([space(items=[item(quantity=5)])])
        with patch.object(data,"load_experiments",return_value=rows()):
            result = planner.evaluate(req)
        # 3 points x size 2 + missing detector 1 = 7 raw -> 49.
        self.assertEqual(result.overall.score, 49)
        self.assertEqual(result.ship["cruise"].score, 49)
        self.assertEqual(result.rooms[0].materials["cruise"][0].evidence[0].id, "TEST-A")
        self.assertFalse(result.model_info["ai_used"])

    def test_unknown_is_interval_not_low_and_disables_moves(self):
        with patch.object(data,"load_experiments",return_value=rows()):
            result = planner.evaluate(request([space(items=[item(material="custom")]),space("empty")]))
        self.assertIsNone(result.overall.score)
        self.assertIsNone(result.overall.level)
        self.assertEqual(result.overall.status, "insufficient data")
        self.assertEqual((result.overall.lower_bound,result.overall.upper_bound),(14,28))
        self.assertFalse(any(a.target_space_id for a in result.actions))

    def test_phases_duration_atmosphere_and_gravity(self):
        req = request([space(items=[item()])], mission="mars", scenario={"cabin_atmosphere":{"pressure_psia":8.2,"o2_percent":34}})
        with patch.object(data,"load_experiments",return_value=rows()):
            result = planner.evaluate(req)
        self.assertEqual(result.phases,["cruise","surface"])
        self.assertEqual(result.ship["cruise"].score,28)
        self.assertEqual(result.ship["surface"].score,42)  # fuel 3 + Mars 1 + exploration 2
        self.assertEqual(result.rooms[0].factors["surface"]["cabin_pressure"].lower_bound,70)
        self.assertTrue(any("gravity" in g for g in result.hazards))
        expected = round(.6*42+.4*(28*180+42*30)/210,2)
        self.assertEqual(result.overall.score,expected)

    def test_seven_factors_and_custom_pressure_gap(self):
        req = request([space(items=[item()],airflow_cm_s=0)], scenario={"cruise_atmosphere":{"pressure_psia":10,"o2_percent":25}})
        with patch.object(data,"load_experiments",return_value=rows()):
            result = planner.evaluate(req)
        factors = result.rooms[0].factors["cruise"]
        self.assertEqual(len(factors),7)
        self.assertEqual(factors["airflow"].lower_bound,75)
        self.assertEqual((factors["cabin_pressure"].lower_bound,factors["cabin_pressure"].upper_bound),(0,100))
        self.assertTrue(any("pressure-factor" in g for g in result.hazards))
        for f in factors.values():
            self.assertLessEqual(0,f.lower_bound)
            self.assertLessEqual(f.lower_bound,f.upper_bound)
            self.assertLessEqual(f.upper_bound,100)

    def test_empty_and_capped_scores(self):
        self.assertEqual(planner.evaluate(request()).overall.score,0)
        with patch.object(data,"load_experiments",return_value=rows()):
            large = item(quantity=100,ignition_source=True)
            result = planner.evaluate(request([space(items=[large])]))
        self.assertEqual(result.overall.score,100)

    def test_move_is_real_and_reduces_uncapped_score(self):
        source = space("source",[item(), item("heater",None,category="machinery",equipment="heater")])
        target = space("target")
        with patch.object(data,"load_experiments",return_value=rows()):
            result = planner.evaluate(request([source,target]))
        moves = [a for a in result.actions if a.target_space_id]
        self.assertTrue(moves)
        move = moves[0]
        self.assertEqual((move.item_id,move.space,move.target_space_id),("panel","source","target"))
        self.assertGreater(move.combined_uncapped_before,move.combined_uncapped_after)
        moved_source = space("source",[source["items"][1]])
        moved_target = space("target",[source["items"][0]])
        with patch.object(data,"load_experiments",return_value=rows()):
            after = planner.evaluate(request([moved_source,moved_target]))
        self.assertLess(after.overall.score,result.overall.score)

    def test_input_validation(self):
        invalid = [dict(mission="launch"),dict(scenario={"cruise_days":0}),
                   dict(spaces=[space(items=[item(quantity=0)])]),
                   dict(spaces=[space(airflow_cm_s=float("nan"))]),
                   dict(spaces=[space("a"),space("a")]),
                   dict(spaces=[space("a",[item()]),space("b",[item()])]),
                   dict(spaces=[space(items=[item(dimensions_cm={"l":0,"w":1,"h":1})])])]
        for payload in invalid:
            with self.subTest(payload=payload),self.assertRaises(ValidationError):
                request(**payload)

    def test_real_csv_and_no_client_flammability_override(self):
        req = request([space(items=[{**item(),"flammability":"Low","dataset_tests":999},item("unknown","Ultem")])])
        result = planner.evaluate(req)
        pmma, unknown = result.rooms[0].materials["cruise"]
        self.assertEqual(pmma.verified_tests,27)
        self.assertTrue(pmma.evidence)
        self.assertEqual(unknown.verified_tests,0)
        self.assertIsNone(unknown.points)
        self.assertEqual(result.overall.status,"insufficient data")

    def test_aggregation_rounds_only_at_display(self):
        spaces = [space("a",[item("a1")]),space("b",[item("b1",quantity=5)]),
                  space("c",[item("c1",quantity=5)])]
        req = request(spaces,mission="lunar",scenario={"cruise_days":7,"surface_stay_days":23})
        with patch.object(data,"load_experiments",return_value=rows()):
            result = planner.evaluate(req)
        cruise = .6*49+.4*(28+49+49)/3
        surface = .6*42+.4*(21+42+42)/3
        expected = round(.6*max(cruise,surface)+.4*(cruise*7+surface*23)/30,2)
        self.assertEqual(result.overall.score,expected)

    def test_http_endpoint(self):
        async def send_request(payload):
            messages=[]
            async def receive():
                return {"type":"http.request","body":json.dumps(payload).encode(),"more_body":False}
            async def send(message):
                messages.append(message)
            scope={"type":"http","asgi":{"version":"3.0"},"http_version":"1.1","method":"POST","scheme":"http",
                   "path":"/planner/assess","raw_path":b"/planner/assess","query_string":b"","root_path":"",
                   "headers":[(b"content-type",b"application/json")],"client":("127.0.0.1",1),"server":("test",80)}
            await main.app(scope,receive,send)
            return messages[0]["status"],json.loads(b"".join(m.get("body",b"") for m in messages[1:]))
        with patch.object(data,"load_experiments",return_value=rows()):
            status, response = asyncio.run(send_request({"spaces":[space(items=[item()])]}))
        self.assertEqual(status,200)
        self.assertEqual(response["overall"]["score"],28)
        status,_ = asyncio.run(send_request({"mission":"launch"}))
        self.assertEqual(status,422)


if __name__ == "__main__":
    unittest.main()
