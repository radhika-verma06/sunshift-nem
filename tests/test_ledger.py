import tempfile
import unittest
from pathlib import Path

from ledger import LedgerError, LocalAuditLedger


class LedgerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.ledger = LocalAuditLedger(Path(self.temp.name) / "receipts.jsonl")

    def tearDown(self):
        self.temp.cleanup()

    def test_append_verify_and_reject_duplicate_trade_event(self):
        payload = {"event_id": "trade-001", "plan_hash": "a" * 64, "interval_matches": [{"kwh": 1.2}]}
        receipt = self.ledger.append(payload)
        self.assertEqual(receipt["chain_status"], "valid")
        self.assertTrue(self.ledger.verify()["valid"])
        with self.assertRaisesRegex(LedgerError, "already has a receipt"):
            self.ledger.append(payload)
        with self.assertRaisesRegex(LedgerError, "plan hash already has a receipt"):
            self.ledger.append({**payload, "event_id": "trade-001-retry"})

    def test_tampering_is_detected_and_blocks_future_append(self):
        self.ledger.append({"event_id": "trade-002", "plan_hash": "b" * 64})
        self.ledger.path.write_text(self.ledger.path.read_text().replace("trade-002", "trade-x02"), encoding="utf-8")
        self.assertFalse(self.ledger.verify()["valid"])
        with self.assertRaisesRegex(LedgerError, "failed verification"):
            self.ledger.append({"event_id": "trade-003", "plan_hash": "c" * 64})

    def test_required_receipt_fields(self):
        with self.assertRaisesRegex(LedgerError, "event_id"):
            self.ledger.append({"plan_hash": "d" * 64})
        with self.assertRaisesRegex(LedgerError, "plan_hash"):
            self.ledger.append({"event_id": "trade-004"})


if __name__ == "__main__":
    unittest.main()
