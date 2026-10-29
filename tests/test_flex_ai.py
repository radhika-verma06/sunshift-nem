import io
import json
import os
import unittest
import urllib.error
from contextlib import redirect_stdout
from unittest.mock import patch

import flex_ai
from flex_ai import AIError, AIUnavailable, ai_status, explain_results, interpret_preferences
from flex_model import load_scenario


def content_body(payload):
    return {"choices": [{"message": {"content": json.dumps(payload)}}]}


class FlexAITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.scenario = load_scenario()

    def test_status_is_unavailable_without_a_key(self):
        with patch.dict(os.environ, {}, clear=True):
            status = ai_status()
        self.assertFalse(status["available"])
        self.assertIn("NEBIUS_API_KEY", status["message"])
        self.assertNotIn("key", status)

    def test_status_reports_configured_model_without_exposing_key(self):
        with patch.dict(os.environ, {"NEBIUS_API_KEY": "secret-value"}, clear=False):
            status = ai_status()
        self.assertTrue(status["available"])
        self.assertEqual(status["model"], flex_ai.DEFAULT_MODEL)
        self.assertNotIn("secret-value", json.dumps(status))

    def test_interpretation_returns_validated_constraints(self):
        payload = {
            "battery_reserve_pct": 35,
            "prefer_local_before_export": True,
            "prioritise_neighbour_evening": False,
            "no_discharge_start_hour": 18,
            "no_discharge_end_hour": 21,
            "summary": "Keep some battery and protect the evening.",
        }
        with patch.dict(os.environ, {"NEBIUS_API_KEY": "secret-value"}, clear=False), patch.object(
            flex_ai, "_post_json", return_value=(content_body(payload), 42)
        ):
            result = interpret_preferences("Keep 35 percent and protect 6 to 9pm", "home_a", self.scenario)
        self.assertEqual(result["preferences"]["battery_reserve_pct"], 35)
        self.assertEqual(result["preferences"]["home_id"], "home_a")
        self.assertEqual(result["preferences"]["source"], "nemotron")
        self.assertEqual(result["preferences"]["no_discharge_start_hour"], 18)
        self.assertEqual(result["latency_ms"], 42)
        self.assertEqual(result["model"], flex_ai.DEFAULT_MODEL)

    def test_missing_key_does_not_fabricate_an_interpretation(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(AIUnavailable):
                interpret_preferences("Keep 40 percent", "home_a", self.scenario)

    def test_malformed_model_output_is_rejected(self):
        invalid_payloads = [
            {"battery_reserve_pct": 150, "prefer_local_before_export": True, "prioritise_neighbour_evening": True, "no_discharge_start_hour": None, "no_discharge_end_hour": None, "summary": "bad"},
            {"battery_reserve_pct": 40, "prefer_local_before_export": True, "prioritise_neighbour_evening": True, "no_discharge_start_hour": 18, "no_discharge_end_hour": None, "summary": "bad"},
            {"battery_reserve_pct": 40, "prefer_local_before_export": True, "prioritise_neighbour_evening": True, "no_discharge_start_hour": None, "no_discharge_end_hour": None, "summary": "bad", "extra": 1},
        ]
        for payload in invalid_payloads:
            with self.subTest(payload=payload), patch.dict(os.environ, {"NEBIUS_API_KEY": "secret-value"}, clear=False), patch.object(
                flex_ai, "_post_json", return_value=(content_body(payload), 10)
            ):
                with self.assertRaises(AIError):
                    interpret_preferences("Keep 40 percent", "home_a", self.scenario)

    def test_api_failure_raises_and_never_returns_a_fake_result(self):
        with patch.dict(os.environ, {"NEBIUS_API_KEY": "secret-value"}, clear=False), patch.object(
            flex_ai, "_post_json", side_effect=AIError("upstream failed")
        ):
            with self.assertRaises(AIError):
                interpret_preferences("Keep 40 percent", "home_a", self.scenario)

    def test_explanation_rejects_numbers(self):
        payload = {"explanation": "You saved 3 dollars by sharing solar locally."}
        with patch.dict(os.environ, {"NEBIUS_API_KEY": "secret-value"}, clear=False), patch.object(
            flex_ai, "_post_json", return_value=(content_body(payload), 12)
        ):
            with self.assertRaisesRegex(AIError, "number"):
                explain_results({"shared_kwh": 10})

    def test_explanation_accepts_qualitative_text(self):
        payload = {"explanation": "More solar stayed in the neighbourhood, so the homes imported less from the grid. This is a modelled sample, not a settled outcome."}
        with patch.dict(os.environ, {"NEBIUS_API_KEY": "secret-value"}, clear=False), patch.object(
            flex_ai, "_post_json", return_value=(content_body(payload), 12)
        ):
            result = explain_results({"shared_kwh": 10})
        self.assertIn("neighbourhood", result["explanation"])
        self.assertEqual(result["latency_ms"], 12)

    def test_explanation_allows_only_numbers_from_the_supplied_summary(self):
        payload = {"explanation": "The shared energy was 10 kWh and the modelled cost moved by 1.66 dollars."}
        summary = {"shared_kwh": 10, "cost_delta_aud": -1.66}
        with patch.dict(os.environ, {"NEBIUS_API_KEY": "secret-value"}, clear=False), patch.object(
            flex_ai, "_post_json", return_value=(content_body(payload), 12)
        ):
            result = explain_results(summary)
        self.assertIn("10 kWh", result["explanation"])
        invented = {"explanation": "The shared energy was 99 kWh and the cost fell."}
        with patch.dict(os.environ, {"NEBIUS_API_KEY": "secret-value"}, clear=False), patch.object(
            flex_ai, "_post_json", return_value=(content_body(invented), 12)
        ):
            with self.assertRaisesRegex(AIError, "99"):
                explain_results(summary)

    def test_api_error_logs_do_not_contain_the_key(self):
        secret = "super-secret-test-value"
        with patch.dict(os.environ, {"NEBIUS_API_KEY": secret}, clear=False), patch(
            "urllib.request.urlopen", side_effect=urllib.error.URLError("offline")
        ):
            output = io.StringIO()
            with redirect_stdout(output):
                with self.assertRaises(AIError):
                    interpret_preferences("Keep 40 percent", "home_a", self.scenario)
        self.assertNotIn(secret, output.getvalue())
        self.assertIn("outcome=network_error", output.getvalue())


if __name__ == "__main__":
    unittest.main()
