import urllib.error
import urllib.parse
from http.server import BaseHTTPRequestHandler

from sunshift_forecast import REGIONS, fetch_forecast
from vercel_api import send_json


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        region_code = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query).get("region", ["NSW"])[0].upper()
        region = REGIONS.get(region_code)
        if region is None:
            send_json(self, 400, {"error": "Choose a supported NEM region"})
            return
        try:
            send_json(self, 200, fetch_forecast(region_code, region))
        except (urllib.error.URLError, TimeoutError, OSError, ValueError, KeyError, TypeError):
            send_json(self, 502, {"error": "Live forecast unavailable. Use the offline demo profile."})

    def log_message(self, format, *args):
        return
