from http.server import BaseHTTPRequestHandler

from ledger import canonical_json, sha256_hex
from optimizer import PlanError, optimize
from vercel_api import RequestProblem, internal_error, read_json, send_json


class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        try:
            body = read_json(self)
            result = optimize(body.get("inputs", {}), body.get("weather", {}))
            result["plan_hash"] = sha256_hex(canonical_json(result))
            send_json(self, 200, result)
        except RequestProblem as exc:
            send_json(self, exc.status, {"error": str(exc)})
        except PlanError as exc:
            send_json(self, 422, {"error": str(exc)})
        except (KeyError, TypeError, ValueError):
            send_json(self, 422, {"error": "Scenario inputs are invalid"})
        except Exception:
            internal_error(self)

    def log_message(self, format, *args):
        return
