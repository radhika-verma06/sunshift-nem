"""Local tamper-evident receipt log for the demo.

This is deliberately not described as a blockchain. It provides a hash-chain
prototype and a matching Solidity registry is included for later testnet work.
"""

from __future__ import annotations

import hashlib
import json
import threading
from pathlib import Path
from typing import Any

GENESIS = "0" * 64


class LedgerError(ValueError):
    pass


def canonical_json(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class LocalAuditLedger:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self._lock = threading.Lock()

    def _read(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        rows: list[dict[str, Any]] = []
        for line_number, line in enumerate(self.path.read_text(encoding="utf-8").splitlines(), start=1):
            if not line.strip():
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise LedgerError(f"Local receipt log is malformed at line {line_number}") from exc
        return rows

    def verify(self) -> dict[str, Any]:
        rows = self._read()
        previous = GENESIS
        seen: set[str] = set()
        for index, row in enumerate(rows):
            payload = row.get("payload")
            if not isinstance(payload, dict):
                return {"valid": False, "count": len(rows), "bad_index": index}
            event_id = str(payload.get("event_id", ""))
            if not event_id or event_id in seen:
                return {"valid": False, "count": len(rows), "bad_index": index}
            seen.add(event_id)
            expected_payload_hash = sha256_hex(canonical_json(payload))
            expected_entry_hash = sha256_hex(canonical_json({"previous_hash": previous, "payload_hash": expected_payload_hash}))
            if row.get("previous_hash") != previous or row.get("payload_hash") != expected_payload_hash or row.get("entry_hash") != expected_entry_hash:
                return {"valid": False, "count": len(rows), "bad_index": index}
            previous = expected_entry_hash
        return {"valid": True, "count": len(rows), "head": previous}

    def append(self, payload: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            event_id = str(payload.get("event_id", "")).strip()
            if not event_id:
                raise LedgerError("event_id is required")
            if not payload.get("plan_hash"):
                raise LedgerError("plan_hash is required")
            status = self.verify()
            if not status["valid"]:
                raise LedgerError("Existing local receipt chain failed verification; refusing to append")
            rows = self._read()
            if any(row.get("payload", {}).get("event_id") == event_id for row in rows):
                raise LedgerError("This event ID already has a receipt; duplicate claim rejected")
            plan_hash = str(payload.get("plan_hash", ""))
            if any(row.get("payload", {}).get("plan_hash") == plan_hash for row in rows):
                raise LedgerError("This plan hash already has a receipt; duplicate claim rejected")
            previous = status["head"]
            payload_hash = sha256_hex(canonical_json(payload))
            entry_hash = sha256_hex(canonical_json({"previous_hash": previous, "payload_hash": payload_hash}))
            row = {"payload": payload, "previous_hash": previous, "payload_hash": payload_hash, "entry_hash": entry_hash}
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("a", encoding="utf-8") as stream:
                stream.write(json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n")
            return {"event_id": event_id, "payload_hash": payload_hash, "entry_hash": entry_hash, "previous_hash": previous, "chain_status": "valid"}
