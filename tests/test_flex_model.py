import math
import unittest

from flex_model import FlexError, load_scenario, simulate, validate_preferences


class FlexModelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.scenario = load_scenario()
        cls.result = simulate(cls.scenario)
        cls.tolerances = 1e-6

    def test_scenario_is_explicitly_synthetic(self):
        self.assertEqual(self.scenario["kind"], "synthetic")
        self.assertIn("not measured", self.scenario["label"])
        self.assertEqual(len(self.scenario["homes"]), 3)

    def test_constraint_checks_pass(self):
        self.assertTrue(self.result["constraints"]["ok"], self.result["constraints"]["violations"])
        self.assertEqual(self.result["constraints"]["violations"], [])
        self.assertTrue(all(check["passed"] for check in self.result["constraints"]["checks"]))

    def test_energy_balance_and_battery_state_for_every_home_and_hour(self):
        for mode in ("independent", "coordinated"):
            series = self.result[mode]["series"]
            for home in self.result["homes"]:
                home_id = home["id"]
                values = series[home_id]
                previous_soc = home["battery"]["initial_soc_kwh"]
                efficiency = home["battery"]["efficiency"]
                for hour in range(24):
                    solar = values["solar_kw"][hour]
                    demand = values["demand_kw"][hour]
                    self.assertAlmostEqual(
                        solar,
                        values["direct_solar_kw"][hour] + values["battery_charge_kw"][hour]
                        + values["solar_shared_kw"][hour] + values["export_kw"][hour],
                        places=4,
                    )
                    self.assertAlmostEqual(
                        demand,
                        values["direct_solar_kw"][hour] + values["battery_own_discharge_kw"][hour]
                        + values["shared_in_kw"][hour] + values["import_kw"][hour],
                        places=4,
                    )
                    expected_soc = previous_soc + values["battery_charge_kw"][hour] * efficiency - (
                        values["battery_own_discharge_kw"][hour] + values["battery_shared_kw"][hour]
                    ) / efficiency
                    self.assertAlmostEqual(values["soc_kwh"][hour], expected_soc, places=3)
                    self.assertGreaterEqual(values["soc_kwh"][hour], min(home["battery"]["initial_soc_kwh"], home["battery"]["capacity_kwh"] * 0.2) - 1e-5)
                    self.assertLessEqual(values["soc_kwh"][hour], home["battery"]["capacity_kwh"] + 1e-5)
                    previous_soc = values["soc_kwh"][hour]

    def test_no_flow_is_negative_or_non_finite(self):
        for mode in ("independent", "coordinated"):
            for home_series in self.result[mode]["series"].values():
                for key, values in home_series.items():
                    for value in values:
                        self.assertTrue(math.isfinite(value), key)
                        self.assertGreaterEqual(value, -self.tolerances, key)

    def test_sharing_never_exceeds_supply_demand_or_transfer_limit(self):
        transfer = self.result["tariffs"]["transfer_limit_kw"]
        series = self.result["coordinated"]["series"]
        batteries = {home["id"]: home["battery"] for home in self.result["homes"]}
        for hour in range(24):
            shared = sum(home_series["shared_in_kw"][hour] for home_series in series.values())
            self.assertLessEqual(shared, transfer + 1e-6)
            for home_id, home_series in series.items():
                self.assertLessEqual(home_series["shared_in_kw"][hour], home_series["demand_kw"][hour] + 1e-6)
                self.assertLessEqual(home_series["solar_shared_kw"][hour], home_series["solar_kw"][hour] + 1e-6)
                self.assertLessEqual(home_series["battery_shared_kw"][hour], batteries[home_id]["max_discharge_kw"] + 1e-6)

    def test_battery_charge_and_discharge_limits(self):
        for home in self.result["homes"]:
            battery = home["battery"]
            for mode in ("independent", "coordinated"):
                values = self.result[mode]["series"][home["id"]]
                for hour in range(24):
                    self.assertLessEqual(values["battery_charge_kw"][hour], battery["max_charge_kw"] + 1e-6)
                    self.assertLessEqual(
                        values["battery_own_discharge_kw"][hour] + values["battery_shared_kw"][hour],
                        battery["max_discharge_kw"] + 1e-6,
                    )

    def test_independent_and_coordinated_use_the_same_inputs(self):
        independent = self.result["independent"]["series"]
        coordinated = self.result["coordinated"]["series"]
        for home in self.result["homes"]:
            home_id = home["id"]
            self.assertEqual(independent[home_id]["solar_kw"], coordinated[home_id]["solar_kw"])
            self.assertEqual(independent[home_id]["demand_kw"], coordinated[home_id]["demand_kw"])

    def test_coordinated_case_uses_more_local_solar_and_imports_less(self):
        comparison = self.result["comparison"]
        self.assertGreater(comparison["shared_kwh"], 0)
        self.assertGreater(comparison["local_solar_delta_kwh"], 0)
        self.assertLess(comparison["grid_import_delta_kwh"], 0)
        self.assertLess(comparison["cost_delta_aud"], 0)
        self.assertAlmostEqual(comparison["savings_aud"], -comparison["cost_delta_aud"], places=2)

    def test_costs_are_calculated_from_visible_tariffs(self):
        tariffs = self.result["tariffs"]
        for mode, coordinated in (("independent", False), ("coordinated", True)):
            total = 0.0
            for home_id, home_totals in self.result[mode]["totals"].items():
                expected = (
                    home_totals["import_kwh"] * tariffs["import_c_kwh"]
                    - home_totals["export_kwh"] * tariffs["export_c_kwh"]
                ) / 100.0
                if coordinated:
                    expected += (
                        home_totals["shared_in_kwh"] - home_totals["shared_out_kwh"]
                    ) * tariffs["shared_c_kwh"] / 100.0
                self.assertAlmostEqual(home_totals["energy_cost_aud"], round(expected, 2), places=2)
                total += expected
            self.assertAlmostEqual(self.result[mode]["total_cost_aud"], round(total, 2), places=2)

    def test_monthly_is_exactly_thirty_sample_days(self):
        monthly = self.result["monthly"]
        self.assertEqual(monthly["days"], 30)
        self.assertIn("repeated 30 times", monthly["assumption"])
        self.assertAlmostEqual(
            monthly["independent_cost_aud"],
            round(self.result["independent"]["total_cost_aud"] * 30, 2),
            places=2,
        )
        self.assertAlmostEqual(
            monthly["coordinated_cost_aud"],
            round(self.result["coordinated"]["total_cost_aud"] * 30, 2),
            places=2,
        )
        self.assertAlmostEqual(
            monthly["savings_aud"],
            round((self.result["independent"]["total_cost_aud"] - self.result["coordinated"]["total_cost_aud"]) * 30, 2),
            places=2,
        )

    def test_export_first_preference_disables_sharing(self):
        sample = next(item for item in self.scenario["sample_preferences"] if item["id"] == "export-first")
        result = simulate(self.scenario, sample["constraints"])
        self.assertEqual(result["comparison"]["shared_kwh"], 0)
        self.assertEqual(result["comparison"]["grid_import_delta_kwh"], 0)
        self.assertEqual(result["comparison"]["cost_delta_aud"], 0)

    def test_no_discharge_window_blocks_battery_flow(self):
        sample = next(item for item in self.scenario["sample_preferences"] if item["id"] == "protect-evening")
        result = simulate(self.scenario, sample["constraints"])
        series = result["coordinated"]["series"]["home_a"]
        for hour in range(18, 21):
            self.assertEqual(series["battery_own_discharge_kw"][hour], 0)
            self.assertEqual(series["battery_shared_kw"][hour], 0)

    def test_reserve_is_applied_to_the_selected_home(self):
        result = simulate(self.scenario, {"home_id": "home_b", "battery_reserve_pct": 90})
        self.assertEqual(result["preferences"]["home_id"], "home_b")
        no_b_discharge = all(
            value == 0
            for value in result["coordinated"]["series"]["home_b"]["battery_own_discharge_kw"]
        )
        self.assertTrue(no_b_discharge)
        self.assertTrue(any(value > 0 for value in result["coordinated"]["series"]["home_a"]["battery_own_discharge_kw"]))

    def test_invalid_preferences_are_rejected(self):
        with self.assertRaisesRegex(FlexError, "reserve"):
            validate_preferences({"battery_reserve_pct": 101}, self.scenario)
        with self.assertRaisesRegex(FlexError, "both a start and an end"):
            validate_preferences({"no_discharge_start_hour": 18}, self.scenario)
        with self.assertRaisesRegex(FlexError, "later"):
            validate_preferences({"no_discharge_start_hour": 21, "no_discharge_end_hour": 18}, self.scenario)
        with self.assertRaisesRegex(FlexError, "not in this scenario"):
            validate_preferences({"home_id": "missing"}, self.scenario)
        with self.assertRaisesRegex(FlexError, "Sharing limit"):
            simulate(self.scenario, {}, {"transfer_limit_kw": -1})


if __name__ == "__main__":
    unittest.main()
