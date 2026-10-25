import io
import json
import unittest

from api.demo import handler as DemoHandler
from api.optimize import handler as OptimizeHandler
from api.receipt import handler as ReceiptHandler


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


class VercelRouteTests(unittest.TestCase):
    def test_hosted_scenario_is_marked_as_scenario_only(self):
        request = FakeRequest()
        DemoHandler.do_GET(request)
        self.assertEqual(request.status, 200)
        self.assertEqual(request.json()["deployment_mode"], "hosted")

    def test_hosted_receipt_recording_is_disabled(self):
        request = FakeRequest(b'{"event_id":"test"}')
        ReceiptHandler.do_POST(request)
        self.assertEqual(request.status, 503)
        self.assertIn("not durable", request.json()["error"])

    def test_optimizer_returns_a_plan_hash(self):
        payload = {
            "inputs": {
                "pv_capacity_kw": 6,
                "average_site_load_kw": 2,
                "flexible_energy_kwh": 8,
                "max_flexible_power_kw": 2,
                "transfer_limit_kw": 2,
                "emissions_factor_kg_kwh": 0.7,
                "p2p_price_c_kwh": 20,
                "grid_reference_price_c_kwh": 35,
            },
            "weather": {"hours": list(range(24)), "ghi_wm2": [0] * 24},
        }
        request = FakeRequest(json.dumps(payload).encode())
        OptimizeHandler.do_POST(request)
        self.assertEqual(request.status, 200)
        self.assertEqual(len(request.json()["plan_hash"]), 64)

    def test_optimizer_rejects_malformed_json(self):
        request = FakeRequest(b"not json")
        OptimizeHandler.do_POST(request)
        self.assertEqual(request.status, 400)


if __name__ == "__main__":
    unittest.main()
