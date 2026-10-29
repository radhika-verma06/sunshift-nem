"""Server-only Nebius Token Factory client for SunShift Flex.

The language model interprets preferences and can explain results. It never
calculates energy, costs or schedules. If the key or API is unavailable, the
caller gets an explicit error and the UI uses the deterministic manual path.
"""

from __future__ import annotations

import json
import os
import re
import time
import urllib.error
import urllib.request
from typing import Any

DEFAULT_MODEL = "nvidia/Nemotron-3_5-Lightning"
DEFAULT_BASE_URL = "https://api.tokenfactory.nebius.com/v1"
KEY_ENV = "NEBIUS_API_KEY"
ALT_KEY_ENV = "NEBIUS_TOKEN_FACTORY_API_KEY"
TIMEOUT_SECONDS = 25


class AIError(RuntimeError):
    """The model call failed or returned output that cannot be trusted."""


class AIUnavailable(AIError):
    """No credentials are configured for the model call."""


def _api_key() -> str | None:
    return os.environ.get(KEY_ENV) or os.environ.get(ALT_KEY_ENV)


def _model() -> str:
    model = os.environ.get("NEBIUS_MODEL", DEFAULT_MODEL).strip()
    if not re.fullmatch(r"[A-Za-z0-9._:/-]{1,120}", model):
        raise AIError("NEBIUS_MODEL contains invalid characters")
    return model


def _base_url() -> str:
    return os.environ.get("NEBIUS_BASE_URL", DEFAULT_BASE_URL).rstrip("/")


def ai_status() -> dict[str, Any]:
    """Return safe model metadata. Never include the key or prompt content."""
    configured = bool(_api_key())
    try:
        model = _model()
    except AIError:
        model = DEFAULT_MODEL
    return {
        "available": configured,
        "model": model,
        "service": "Nebius Token Factory",
        "base_url": _base_url(),
        "key_env": KEY_ENV,
        "message": (
            "Nemotron is configured. A real model call will be attempted."
            if configured
            else f"{KEY_ENV} is not configured. Manual sample constraints are available; no model result is fabricated."
        ),
    }


def _extract_content(response: dict[str, Any]) -> str:
    choices = response.get("choices")
    if not isinstance(choices, list) or not choices:
        raise AIError("Nemotron returned no choices")
    message = choices[0].get("message") if isinstance(choices[0], dict) else None
    content = message.get("content") if isinstance(message, dict) else None
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, dict) and isinstance(item.get("text"), str):
                parts.append(item["text"])
            elif isinstance(item, str):
                parts.append(item)
        content = "".join(parts)
    if not isinstance(content, str) or not content.strip():
        raise AIError("Nemotron returned an empty response")
    return content.strip()


def _parse_json(content: str) -> dict[str, Any]:
    stripped = content.strip()
    if stripped.startswith("```"):
        stripped = re.sub(r"^```[a-zA-Z0-9_-]*\s*", "", stripped)
        stripped = re.sub(r"\s*```$", "", stripped)
    try:
        value = json.loads(stripped)
    except json.JSONDecodeError as exc:
        raise AIError("Nemotron did not return valid JSON") from exc
    if not isinstance(value, dict):
        raise AIError("Nemotron JSON must be an object")
    return value


PREFERENCE_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "battery_reserve_pct", "prefer_local_before_export",
        "prioritise_neighbour_evening", "no_discharge_start_hour",
        "no_discharge_end_hour", "summary",
    ],
    "properties": {
        "battery_reserve_pct": {"type": "number", "minimum": 0, "maximum": 100},
        "prefer_local_before_export": {"type": "boolean"},
        "prioritise_neighbour_evening": {"type": "boolean"},
        "no_discharge_start_hour": {"anyOf": [{"type": "integer", "minimum": 0, "maximum": 23}, {"type": "null"}]},
        "no_discharge_end_hour": {"anyOf": [{"type": "integer", "minimum": 0, "maximum": 23}, {"type": "null"}]},
        "summary": {"type": "string", "maxLength": 180},
    },
}


def _post_json(payload: dict[str, Any], purpose: str) -> tuple[dict[str, Any], int]:
    key = _api_key()
    if not key:
        raise AIUnavailable(f"{KEY_ENV} is not configured")
    model = str(payload.get("model", ""))
    url = f"{_base_url()}/chat/completions"
    started = time.monotonic()
    request = urllib.request.Request(
        url,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
            status = int(getattr(response, "status", 200))
            raw = response.read()
    except urllib.error.HTTPError as exc:
        elapsed = int((time.monotonic() - started) * 1000)
        print(f"[flex-ai] purpose={purpose} model={model} outcome=http_error status={exc.code} latency_ms={elapsed}")
        raise AIError(f"Nemotron API returned HTTP {exc.code}") from exc
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        elapsed = int((time.monotonic() - started) * 1000)
        print(f"[flex-ai] purpose={purpose} model={model} outcome=network_error status=unavailable latency_ms={elapsed}")
        raise AIError("Nemotron API request failed or timed out") from exc
    elapsed = int((time.monotonic() - started) * 1000)
    try:
        body = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        print(f"[flex-ai] purpose={purpose} model={model} outcome=invalid_json status={status} latency_ms={elapsed}")
        raise AIError("Nemotron API returned invalid JSON") from exc
    print(f"[flex-ai] purpose={purpose} model={model} outcome=ok status={status} latency_ms={elapsed}")
    return body, elapsed


def _validated_hours(value: Any, name: str) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int):
        raise AIError(f"{name} must be an integer hour or null")
    if value < 0 or value > 23:
        raise AIError(f"{name} must be between 0 and 23")
    return value


def validate_interpretation(raw: dict[str, Any], home_id: str) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise AIError("Preference interpretation must be an object")
    allowed = set(PREFERENCE_SCHEMA["required"])
    if set(raw) != allowed:
        raise AIError("Preference interpretation has missing or unexpected fields")
    reserve = raw.get("battery_reserve_pct")
    if isinstance(reserve, bool) or not isinstance(reserve, (int, float)) or not 0 <= float(reserve) <= 100:
        raise AIError("Battery reserve must be a number from 0 to 100")
    for key in ("prefer_local_before_export", "prioritise_neighbour_evening"):
        if not isinstance(raw.get(key), bool):
            raise AIError(f"{key} must be true or false")
    start = _validated_hours(raw.get("no_discharge_start_hour"), "No-discharge start")
    end = _validated_hours(raw.get("no_discharge_end_hour"), "No-discharge end")
    if (start is None) != (end is None):
        raise AIError("No-discharge window needs both a start and an end")
    if start is not None and start >= end:
        raise AIError("No-discharge end must be later than its start")
    summary = raw.get("summary")
    if not isinstance(summary, str) or not summary.strip() or len(summary.strip()) > 180:
        raise AIError("Preference summary must be a short non-empty string")
    return {
        "home_id": home_id,
        "battery_reserve_pct": round(float(reserve), 1),
        "prefer_local_before_export": raw["prefer_local_before_export"],
        "prioritise_neighbour_evening": raw["prioritise_neighbour_evening"],
        "no_discharge_start_hour": start,
        "no_discharge_end_hour": end,
        "source": "nemotron",
        "summary": summary.strip(),
    }


def interpret_preferences(text: str, home_id: str, scenario: dict[str, Any]) -> dict[str, Any]:
    text = str(text or "").strip()
    if not 1 <= len(text) <= 800:
        raise AIError("Preference text must be between 1 and 800 characters")
    if not _api_key():
        raise AIUnavailable(f"{KEY_ENV} is not configured")
    home = next((item for item in scenario.get("homes", []) if item.get("id") == home_id), None)
    if home is None:
        raise AIError("Selected home is not in this scenario")
    model = _model()
    battery = home["battery"]
    system = (
        "You are the preference interpreter for SunShift Flex, a simulated neighbourhood solar-sharing prototype. "
        "Convert the household's plain-language preference into the exact JSON schema. "
        "Do not calculate or invent energy, costs, savings, schedules, feasibility or grid outcomes; the deterministic simulator does that. "
        "Apply these defaults only when the preference does not say otherwise: battery_reserve_pct 40, "
        "prefer_local_before_export true, prioritise_neighbour_evening true, both no-discharge hours null. "
        "Interpret '6pm to 9pm' as start 18 and end 21. "
        "A request to share or use the battery in the evening is NOT a no-discharge request: set prioritise_neighbour_evening true and leave both no-discharge hours null. "
        "Only set the no-discharge window when the preference explicitly asks not to discharge during a named time range. "
        "Return JSON only, with no markdown."
    )
    user = (
        f"Selected home: {home['name']}. Battery capacity: {battery['capacity_kwh']} kWh. "
        f"Current state of charge: {battery['initial_soc_kwh']} kWh ({round(battery['initial_soc_kwh'] / battery['capacity_kwh'] * 100)}%). "
        f"Other homes in the scenario: {', '.join(item['name'] for item in scenario['homes'] if item['id'] != home_id)}. "
        f"Household preference: {text}"
    )
    payload = {
        "model": model,
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
        "temperature": 0,
        "max_tokens": 900,
        "chat_template_kwargs": {"enable_thinking": False},
        "response_format": {
            "type": "json_schema",
            "json_schema": {"name": "sunshift_preferences", "strict": True, "schema": PREFERENCE_SCHEMA},
        },
    }
    body, latency = _post_json(payload, "interpret")
    raw = _parse_json(_extract_content(body))
    preferences = validate_interpretation(raw, home_id)
    return {
        "preferences": preferences,
        "model": model,
        "service": "Nebius Token Factory",
        "latency_ms": latency,
        "source": "nemotron",
    }


def _collect_numbers(value: Any, out: set[float]) -> None:
    if isinstance(value, bool):
        return
    if isinstance(value, (int, float)):
        number = float(value)
        out.add(round(number, 4))
        out.add(round(abs(number), 4))
        return
    if isinstance(value, dict):
        for item in value.values():
            _collect_numbers(item, out)
    elif isinstance(value, (list, tuple)):
        for item in value:
            _collect_numbers(item, out)


def _unsupported_numbers(text: str, summary: dict[str, Any]) -> list[str]:
    allowed: set[float] = {0.0}
    _collect_numbers(summary, allowed)
    unsupported: list[str] = []
    for raw in re.findall(r"(?<![\w.])-?\d+(?:,\d{3})*(?:\.\d+)?", text):
        token = raw.replace(",", "")
        try:
            value = float(token)
        except ValueError:
            continue
        if any(abs(value - candidate) <= 0.051 for candidate in allowed):
            continue
        unsupported.append(raw)
    return unsupported


def explain_results(result_summary: dict[str, Any]) -> dict[str, Any]:
    if not _api_key():
        raise AIUnavailable(f"{KEY_ENV} is not configured")
    model = _model()
    system = (
        "You explain an already-completed deterministic energy simulation to a neighbour. "
        "The numbers are supplied by code and are already visible in the interface. "
        "Write exactly two short sentences. You may cite a number only when it appears in the supplied result summary; "
        "never derive, estimate, round into a new figure or invent a number, percentage or dollar amount. "
        "Do not invent facts, measurements, guarantees or new calculations. "
        "Keep it under forty-five words and finish the last sentence. "
        "Mention what changed because of local sharing and one honest limitation. Return JSON only, with no markdown."
    )
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": "Deterministic result summary: " + json.dumps(result_summary, ensure_ascii=False)},
        ],
        "temperature": 0,
        "max_tokens": 700,
        "chat_template_kwargs": {"enable_thinking": False},
        "response_format": {
            "type": "json_schema",
            "json_schema": {
                "name": "sunshift_explanation",
                "strict": True,
                "schema": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["explanation"],
                    "properties": {"explanation": {"type": "string", "maxLength": 600}},
                },
            },
        },
    }
    body, latency = _post_json(payload, "explain")
    raw = _parse_json(_extract_content(body))
    explanation = raw.get("explanation") if isinstance(raw, dict) else None
    if not isinstance(explanation, str):
        raise AIError("Explanation must be a string")
    explanation = " ".join(explanation.split())
    if not 20 <= len(explanation) <= 600:
        raise AIError("Explanation must be between 20 and 600 characters")
    unsupported = _unsupported_numbers(explanation, result_summary)
    if unsupported:
        raise AIError("Explanation contained a number not present in the supplied result: " + ", ".join(unsupported[:3]))
    if any(word in explanation.lower() for word in ("guarantee", "guaranteed", "measured")):
        raise AIError("Explanation contained a claim the prototype cannot support")
    return {"explanation": explanation, "model": model, "service": "Nebius Token Factory", "latency_ms": latency}
