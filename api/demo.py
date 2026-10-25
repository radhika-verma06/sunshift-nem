from http.server import BaseHTTPRequestHandler

from vercel_api import ROOT, send_json


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            import json

            payload = json.loads((ROOT / "data" / "demo_scenario.json").read_text(encoding="utf-8"))
            payload["deployment_mode"] = "hosted"
            send_json(self, 200, payload)
        except (OSError, ValueError):
            send_json(self, 500, {"error": "Hosted demo scenario could not be loaded"})

    def log_message(self, format, *args):
        return
