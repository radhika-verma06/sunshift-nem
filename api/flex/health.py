from http.server import BaseHTTPRequestHandler

from flex_ai import ai_status
from vercel_api import send_json


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        send_json(self, 200, {
            "ok": True,
            "service": "SunShift Flex hosted prototype",
            "deployment_mode": "hosted",
            "ai": ai_status(),
        })

    def log_message(self, format, *args):
        return
