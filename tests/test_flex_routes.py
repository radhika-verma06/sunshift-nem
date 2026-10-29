import io
import json
import os
import unittest
from unittest.mock import patch

from api.flex.explain import handler as ExplainHandler
from api.flex.health import handler as HealthHandler
from api.flex.interpret import handler as InterpretHandler
from api.flex.plan import handler as PlanHandler
from api.flex.receipt import handler as ReceiptHandler
from api.flex.scenario import handler as ScenarioHandler


class FakeRequest:
    def __init__(self, body=b"", path="/"):
        self.headers = {"Content-Length": str(len(body))}
        self.rfile = io.BytesIO(body)
        self.path = path
        self.request_version = "HTTP/1.1"
        self.status = None
        self.response_headers = {}
        self.wfile = io.BytesIO()

    def send_response(self, status):
        self.status = status

    def send_header(self, name, value):
        self.response_headers[name] = value

    def end_headers(self):
        pass

    def json(self):
        return json.loads(self.wfile.getvalue())


class FlexRouteTests(unittest.TestCase):
    def test_scenario_route_is_hosted_and_has_three_homes(self):
        request = FakeRequest()
        ScenarioHandler.do_GET(request)
        self.assertEqual(request.status, 200)
        body = request.json()
        self.assertEqual(body["deployment_mode"], "hosted")
        self.assertEqual(len(body["homes"]), 3)
        self.assertIn("ai", body)

    def test_health_route_is_explicit_about_simulation(self):
        request = FakeRequest()
        HealthHandler.do_GET(request)
        self.assertEqual(request.status, 200)
        self.assertEqual(request.json()["deployment_mode"], "hosted")

    def test_plan_route_returns_a_hash_and_zero_violations(self):
        payload = {
            "preferences": {"home_id": "home_a", "battery_reserve_pct": 40, "prefer_local_before_export": True, "prioritise_neighbour_evening": True},
            "tariffs": {"import_c_kwh": 34, "export_c_kwh": 8, "shared_c_kwh": 20, "transfer_limit_kw": 5},
        }
        request = FakeRequest(json.dumps(payload).encode())
        PlanHandler.do_POST(request)
        self.assertEqual(request.status, 200)
        body = request.json()
        self.assertEqual(len(body["plan_hash"]), 64)
        self.assertTrue(body["constraints"]["ok"])
        self.assertGreater(body["comparison"]["shared_kwh"], 0)

    def test_plan_route_rejects_malformed_json(self):
        request = FakeRequest(b"not json")
        PlanHandler.do_POST(request)
        self.assertEqual(request.status, 400)

    def test_plan_route_rejects_invalid_preferences(self):
        request = FakeRequest(json.dumps({"preferences": {"battery_reserve_pct": 150}}).encode())
        PlanHandler.do_POST(request)
        self.assertEqual(request.status, 422)

    def test_interpret_without_a_key_is_503_and_not_a_fake_result(self):
        with patch.dict(os.environ, {}, clear=True):
            request = FakeRequest(json.dumps({"text": "Keep 40 percent", "home_id": "home_a"}).encode())
            InterpretHandler.do_POST(request)
        self.assertEqual(request.status, 503)
        self.assertEqual(request.json()["code"], "ai_unavailable")
        self.assertNotIn("preferences", request.json())

    def test_explain_without_a_key_is_503(self):
        with patch.dict(os.environ, {}, clear=True):
            request = FakeRequest(json.dumps({"summary": {"shared_kwh": 10}}).encode())
            ExplainHandler.do_POST(request)
        self.assertEqual(request.status, 503)
        self.assertEqual(request.json()["code"], "ai_unavailable")

    def test_hosted_receipt_recording_is_disabled(self):
        request = FakeRequest(json.dumps({"event_id": "x", "plan_hash": "a" * 64}).encode())
        ReceiptHandler.do_POST(request)
        self.assertEqual(request.status, 503)
        self.assertIn("not durable", request.json()["error"])

    def test_scenario_does_not_expose_the_key(self):
        secret = "never-print-this-key"
        with patch.dict(os.environ, {"NEBIUS_API_KEY": secret}, clear=False):
            request = FakeRequest()
            ScenarioHandler.do_GET(request)
        self.assertEqual(request.status, 200)
        self.assertNotIn(secret, request.wfile.getvalue().decode("utf-8"))


if __name__ == "__main__":
    unittest.main()
