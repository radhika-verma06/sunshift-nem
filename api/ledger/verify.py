from http.server import BaseHTTPRequestHandler

from vercel_api import send_json


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        send_json(self, 200, {
            "valid": False,
            "count": 0,
            "hosted_disabled": True,
            "message": "The persistent receipt chain is available in the local demo, not the hosted preview.",
        })

    def log_message(self, format, *args):
        return
