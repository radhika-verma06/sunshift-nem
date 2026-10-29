from http.server import BaseHTTPRequestHandler

from vercel_api import send_json


class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        send_json(self, 503, {
            "error": "Receipt recording is disabled in the hosted demo because its function filesystem is not durable. Run locally to use the persistent hash-chain ledger."
        })

    def log_message(self, format, *args):
        return
