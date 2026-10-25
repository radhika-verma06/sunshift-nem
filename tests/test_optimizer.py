import json
import unittest
from pathlib import Path

from optimizer import PlanError, optimize

ROOT = Path(__file__).resolve().parents[1]


class OptimizerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.weather = json.loads((ROOT / "data" / "demo_scenario.json").read_text(encoding="utf-8"))

    def test_peer_schedule_conserves_energy_and_stays_inside_limits(self):
        result = optimize({}, self.weather)
        self.assertTrue(result["metrics"]["flexible_energy_conserved"])
        self.assertAlmostEqual(sum(result["optimized_flexible_kwh"]), 18.0, places=6)
        self.assertTrue(all(v <= result["inputs"]["max_flexible_power_kw"] + 1e-9 for v in result["optimized_flexible_kwh"]))
        self.assertTrue(all(v <= result["inputs"]["transfer_limit_kw"] + 1e-9 for v in result["p2p_shared_kwh"]))

    def test_p2p_match_never_exceeds_solar_or_buyer_demand(self):
        result = optimize({}, self.weather)
        for index, matched in enumerate(result["p2p_shared_kwh"]):
            buyer_demand = result["site_load_kwh"][index] + result["optimized_flexible_kwh"][index]
            self.assertLessEqual(matched, result["solar_kwh"][index] + 1e-9)
            self.assertLessEqual(matched, buyer_demand + 1e-9)

    def test_coordinated_case_reduces_buyer_import_in_illustrative_scenario(self):
        result = optimize({}, self.weather)
        metrics = result["metrics"]
        self.assertGreater(metrics["p2p_energy_matched_kwh"], 0)
        self.assertGreater(metrics["grid_import_avoided_kwh"], 0)
        self.assertLessEqual(metrics["optimized_peak_kw"], metrics["baseline_peak_kw"])

    def test_plan_accounts_for_transfer_limit(self):
        result = optimize({"transfer_limit_kw": 3}, self.weather)
        self.assertLessEqual(max(result["p2p_shared_kwh"]), 3)

    def test_infeasible_flexible_energy_is_rejected(self):
        with self.assertRaisesRegex(PlanError, "capacity"):
            optimize({"flexible_energy_kwh": 100, "max_flexible_power_kw": 2}, self.weather)

    def test_invalid_weather_length_is_rejected(self):
        bad = {**self.weather, "ghi_wm2": self.weather["ghi_wm2"][:-1]}
        with self.assertRaisesRegex(PlanError, "Exactly 24"):
            optimize({}, bad)

    def test_non_finite_weather_is_rejected(self):
        bad = {**self.weather, "ghi_wm2": [float("nan"), *self.weather["ghi_wm2"][1:]]}
        with self.assertRaisesRegex(PlanError, "finite"):
            optimize({}, bad)

    def test_user_supplied_participant_profiles_override_modelled_site_curves(self):
        profile = {
            **self.weather,
            "solar_kwh_override": [0] * 8 + [10] * 8 + [0] * 8,
            "buyer_load_kwh_override": [5] * 24,
        }
        result = optimize({"flexible_energy_kwh": 6, "max_flexible_power_kw": 3}, profile)
        self.assertEqual(result["site_load_kwh"], [5.0] * 24)
        self.assertEqual(result["solar_kwh"], [0.0] * 8 + [10.0] * 8 + [0.0] * 8)

    def test_partial_uploaded_profile_is_rejected(self):
        profile = {**self.weather, "solar_kwh_override": [1] * 24}
        with self.assertRaisesRegex(PlanError, "both seller solar and buyer load"):
            optimize({}, profile)


if __name__ == "__main__":
    unittest.main()
