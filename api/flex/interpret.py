from http.server import BaseHTTPRequestHandler

from flex_ai import AIError, AIUnavailable, ai_status, interpret_preferences
from flex_model import load_scenario
from vercel_api import ROOT, RequestProblem, internal_error, read_json, send_json


class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        try:
            body = read_json(self)
            text = body.get("text")
            if not isinstance(text, str) or not 1 <= len(text.strip()) <= 800:
                send_json(self, 422, {"error": "Preference text must be between 1 and 800 characters"})
                return
            scenario = load_scenario(ROOT / "data" / "flex_scenario.json")
            home_id = str(body.get("home_id") or scenario["your_home"])
            if home_id not in scenario["home_ids"]:
                send_json(self, 422, {"error": "Selected home is not in this scenario"})
                return
            send_json(self, 200, interpret_preferences(text.strip(), home_id, scenario))
        except RequestProblem as exc:
            send_json(self, exc.status, {"error": str(exc)})
        except AIUnavailable as exc:
            send_json(self, 503, {"error": str(exc), "code": "ai_unavailable", "ai": ai_status()})
        except AIError as exc:
            send_json(self, 502, {"error": str(exc), "code": "ai_error", "ai": ai_status()})
        except Exception:
            internal_error(self)

    def log_message(self, format, *args):
        return
