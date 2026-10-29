from http.server import BaseHTTPRequestHandler

from flex_model import FlexError, load_scenario, simulate
from ledger import canonical_json, sha256_hex
from vercel_api import ROOT, RequestProblem, internal_error, read_json, send_json


class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        try:
            body = read_json(self)
            scenario = load_scenario(ROOT / "data" / "flex_scenario.json")
            result = simulate(scenario, body.get("preferences") or {}, body.get("tariffs") or {})
            result["plan_hash"] = sha256_hex(canonical_json(result))
            send_json(self, 200, result)
        except RequestProblem as exc:
            send_json(self, exc.status, {"error": str(exc)})
        except FlexError as exc:
            send_json(self, 422, {"error": str(exc)})
        except Exception:
            internal_error(self)

    def log_message(self, format, *args):
        return
