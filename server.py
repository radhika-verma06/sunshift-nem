"""Local-only HTTP API and static web server for SunShift NEM."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from flex_ai import AIError, AIUnavailable, ai_status, explain_results, interpret_preferences
from flex_model import FlexError, load_scenario, simulate
from ledger import LedgerError, LocalAuditLedger, canonical_json, sha256_hex
from optimizer import PlanError, optimize
from sunshift_forecast import REGIONS, fetch_forecast

ROOT = Path(__file__).resolve().parent
WEB = ROOT / "web"
DATA = ROOT / "data"


def _load_local_env() -> None:
    """Load only NEBIUS_ settings from an ignored .env file, never print them."""
    path = ROOT / ".env"
    if not path.is_file():
        return
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return
    for raw in lines:
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, value = line.split("=", 1)
        name = name.strip()
        if name.startswith("NEBIUS_") and name not in os.environ:
            os.environ[name] = value.strip().strip('"').strip("'")


_load_local_env()
LEDGER = LocalAuditLedger(Path(os.environ.get("SUNSHIFT_LEDGER_PATH", DATA / "receipts.local.jsonl")))
FLEX_SCENARIO = load_scenario()


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(WEB), **kwargs)

    def log_message(self, format: str, *args) -> None:
        # Keep demo console output concise and avoid logging request payloads.
        print(f"{self.client_address[0]} - {format % args}")

    def _json(self, status: int, body: dict) -> None:
        encoded = json.dumps(body, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(encoded)

    def do_GET(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == "/api/demo":
            self._json(200, json.loads((DATA / "demo_scenario.json").read_text(encoding="utf-8")))
            return
        if parsed.path == "/api/sample-profile.csv":
            encoded = (DATA / "sample_participant_profile.csv").read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "text/csv; charset=utf-8")
            self.send_header("Content-Disposition", "attachment; filename=sample_participant_profile.csv")
            self.send_header("Content-Length", str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)
            return
        if parsed.path == "/api/health":
            self._json(200, {"ok": True, "service": "SunShift Flex local prototype", "hardware_control": False, "ai": ai_status()})
            return
        if parsed.path == "/api/flex/health":
            self._json(200, {"ok": True, "service": "SunShift Flex local prototype", "deployment_mode": "local", "ai": ai_status()})
            return
        if parsed.path == "/api/flex/scenario":
            self._json(200, {
                **FLEX_SCENARIO,
                "ai": ai_status(),
                "deployment_mode": "local",
                "sample_csv_url": "/api/flex/sample.csv",
            })
            return
        if parsed.path == "/api/flex/sample.csv":
            encoded = (DATA / "flex_homes_sample.csv").read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "text/csv; charset=utf-8")
            self.send_header("Content-Disposition", "attachment; filename=flex_homes_sample.csv")
            self.send_header("Content-Length", str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)
            return
        if parsed.path == "/api/ledger/verify":
            self._json(200, LEDGER.verify())
            return
        if parsed.path == "/api/forecast":
            query = urllib.parse.parse_qs(parsed.query)
            region_code = query.get("region", ["NSW"])[0].upper()
            region = REGIONS.get(region_code)
            if region is None:
                self._json(400, {"error": "Choose a supported NEM region"})
                return
            try:
                forecast = self._fetch_forecast(region_code, region)
            except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
                self._json(502, {"error": f"Live forecast unavailable: {exc.__class__.__name__}. Use the offline demo profile."})
                return
            self._json(200, forecast)
            return
        return super().do_GET()

    def _fetch_forecast(self, code: str, region: dict) -> dict:
        return fetch_forecast(code, region)

    def do_POST(self) -> None:
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length < 1 or length > 1_000_000:
                self._json(400, {"error": "Request must contain a JSON body under 1 MB"})
                return
            body = json.loads(self.rfile.read(length).decode("utf-8"))
            if self.path == "/api/flex/interpret":
                text = body.get("text")
                if not isinstance(text, str) or not 1 <= len(text.strip()) <= 800:
                    self._json(422, {"error": "Preference text must be between 1 and 800 characters"})
                    return
                home_id = str(body.get("home_id") or FLEX_SCENARIO["your_home"])
                if home_id not in FLEX_SCENARIO["home_ids"]:
                    self._json(422, {"error": "Selected home is not in this scenario"})
                    return
                result = interpret_preferences(text.strip(), home_id, FLEX_SCENARIO)
                self._json(200, result)
                return
            if self.path == "/api/flex/receipt":
                event_id = body.get("event_id")
                plan_hash = body.get("plan_hash")
                if not isinstance(event_id, str) or not 1 <= len(event_id) <= 100:
                    self._json(422, {"error": "A receipt needs a short event_id"})
                    return
                if not isinstance(plan_hash, str) or len(plan_hash) != 64:
                    self._json(422, {"error": "A receipt needs a 64-character plan_hash"})
                    return
                payload = {
                    "event_id": event_id,
                    "plan_hash": plan_hash,
                    "event_type": "flex_plan",
                    "scenario_id": str(body.get("scenario_id") or "")[:80],
                    "preferences": body.get("preferences") if isinstance(body.get("preferences"), dict) else {},
                    "comparison": body.get("comparison") if isinstance(body.get("comparison"), dict) else {},
                    "constraints_ok": bool(body.get("constraints_ok")),
                }
                receipt = LEDGER.append(payload)
                self._json(201, receipt)
                return
            if self.path == "/api/flex/plan":
                result = simulate(FLEX_SCENARIO, body.get("preferences") or {}, body.get("tariffs") or {})
                result["plan_hash"] = sha256_hex(canonical_json(result))
                self._json(200, result)
                return
            if self.path == "/api/flex/explain":
                summary = body.get("summary")
                if not isinstance(summary, dict) or len(json.dumps(summary, ensure_ascii=False)) > 20000:
                    self._json(422, {"error": "Explain request needs a compact result summary"})
                    return
                result = explain_results(summary)
                self._json(200, result)
                return
            if self.path == "/api/optimize":
                result = optimize(body.get("inputs", {}), body.get("weather", {}))
                result["plan_hash"] = sha256_hex(canonical_json(result))
                self._json(200, result)
                return
            if self.path == "/api/receipt":
                receipt = LEDGER.append(body)
                self._json(201, receipt)
                return
            self._json(404, {"error": "Unknown API route"})
        except (json.JSONDecodeError, UnicodeDecodeError):
            self._json(400, {"error": "Request must be valid UTF-8 JSON"})
        except (PlanError, LedgerError, FlexError) as exc:
            self._json(422, {"error": str(exc)})
        except AIUnavailable as exc:
            self._json(503, {"error": str(exc), "code": "ai_unavailable", "ai": ai_status()})
        except AIError as exc:
            self._json(502, {"error": str(exc), "code": "ai_error", "ai": ai_status()})
        except BrokenPipeError:
            return
        except (KeyError, TypeError, ValueError, OSError) as exc:
            self._json(500, {"error": f"Unexpected local server error: {exc.__class__.__name__}"})


def main() -> None:
    host = "127.0.0.1"
    port = int(os.environ.get("SUNSHIFT_PORT", "8788"))
    server = ThreadingHTTPServer((host, port), Handler)
    print(f"SunShift NEM running locally at http://{host}:{port}")
    print("No robot connection, live control, or public tunnel is configured.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping SunShift local server.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
