from http.server import BaseHTTPRequestHandler

from flex_ai import ai_status
from flex_model import load_scenario
from vercel_api import ROOT, send_json


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            payload = load_scenario(ROOT / "data" / "flex_scenario.json")
            payload["ai"] = ai_status()
            payload["deployment_mode"] = "hosted"
            payload["sample_csv_url"] = "/api/flex/sample.csv"
            send_json(self, 200, payload)
        except Exception:
            send_json(self, 500, {"error": "Flex scenario could not be loaded"})

    def log_message(self, format, *args):
        return
