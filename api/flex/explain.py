import json
from http.server import BaseHTTPRequestHandler

from flex_ai import AIError, AIUnavailable, ai_status, explain_results
from vercel_api import RequestProblem, internal_error, read_json, send_json


class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        try:
            body = read_json(self)
            summary = body.get("summary")
            if not isinstance(summary, dict) or len(json.dumps(summary, ensure_ascii=False)) > 20000:
                send_json(self, 422, {"error": "Explain request needs a compact result summary"})
                return
            send_json(self, 200, explain_results(summary))
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
