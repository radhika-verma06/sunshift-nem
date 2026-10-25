"""Shared helpers for the Vercel serverless API routes."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent


class RequestProblem(ValueError):
    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status


def send_json(handler: Any, status: int, body: dict) -> None:
    encoded = json.dumps(body, ensure_ascii=False).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(encoded)))
    handler.send_header("Cache-Control", "no-store")
    handler.end_headers()
    handler.wfile.write(encoded)


def read_json(handler: Any) -> dict:
    try:
        length = int(handler.headers.get("Content-Length", "0"))
    except (TypeError, ValueError) as exc:
        raise RequestProblem(400, "Invalid Content-Length") from exc
    if length < 1 or length > 1_000_000:
        raise RequestProblem(400, "Request must contain a JSON body under 1 MB")
    try:
        value = json.loads(handler.rfile.read(length).decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise RequestProblem(400, "Request must be valid UTF-8 JSON") from exc
    if not isinstance(value, dict):
        raise RequestProblem(400, "JSON request body must be an object")
    return value


def internal_error(handler: Any) -> None:
    send_json(handler, 500, {"error": "Unexpected hosted API error"})
