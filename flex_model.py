"""Deterministic three-home solar sharing simulator for SunShift Flex.

The model is small on purpose. Every kWh shown in the UI comes from here.
It is not a grid, market, retailer or settlement simulation.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
DEFAULT_SCENARIO_PATH = ROOT / "data" / "flex_scenario.json"
EPS = 1e-7
EVENING_START = 17
EVENING_END = 21


class FlexError(ValueError):
    """Raised when a scenario or preference set cannot be simulated."""


def _finite(name: str, value: Any, low: float, high: float) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise FlexError(f"{name} must be a number") from exc
    if not math.isfinite(number) or number < low or number > high:
        raise FlexError(f"{name} must be between {low:g} and {high:g}")
    return number


def _bool(name: str, value: Any) -> bool:
    if not isinstance(value, bool):
        raise FlexError(f"{name} must be true or false")
    return value


def _hour(name: str, value: Any, allow_none: bool = True) -> int | None:
    if value is None and allow_none:
        return None
    if isinstance(value, bool):
        raise FlexError(f"{name} must be an hour from 0 to 23")
    try:
        hour = int(value)
    except (TypeError, ValueError) as exc:
        raise FlexError(f"{name} must be an hour from 0 to 23") from exc
    if hour < 0 or hour > 23:
        raise FlexError(f"{name} must be an hour from 0 to 23")
    return hour


def load_scenario(path: str | Path | None = None) -> dict[str, Any]:
    scenario_path = Path(path) if path else DEFAULT_SCENARIO_PATH
    try:
        scenario = json.loads(scenario_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise FlexError("Flex scenario could not be loaded") from exc
    return validate_scenario(scenario)


def validate_scenario(scenario: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(scenario, dict):
        raise FlexError("Scenario must be an object")
    homes = scenario.get("homes")
    if not isinstance(homes, list) or len(homes) < 2:
        raise FlexError("Scenario must contain at least two homes")
    if len(homes) > 6:
        raise FlexError("Scenario supports at most six homes")
    ids = [str(home.get("id", "")) for home in homes]
    if len(set(ids)) != len(ids) or any(not value for value in ids):
        raise FlexError("Each home needs a unique id")
    hours = scenario.get("hours")
    labels = scenario.get("labels")
    if hours != list(range(24)):
        raise FlexError("Scenario must contain hour values 0 to 23")
    if not isinstance(labels, list) or len(labels) != 24:
        raise FlexError("Scenario must contain 24 hour labels")
    for home in homes:
        solar = home.get("solar_kw")
        demand = home.get("demand_kw")
        if not isinstance(solar, list) or len(solar) != 24 or not isinstance(demand, list) or len(demand) != 24:
            raise FlexError(f"{home.get('name', home.get('id'))} needs 24 solar and demand values")
        for array_name, values in (("solar", solar), ("demand", demand)):
            for value in values:
                _finite(f"{home.get('id')} {array_name}", value, 0.0, 1000.0)
        battery = home.get("battery")
        if not isinstance(battery, dict):
            raise FlexError(f"{home.get('id')} needs a battery definition")
        capacity = _finite(f"{home.get('id')} battery capacity", battery.get("capacity_kwh"), 0.1, 1000.0)
        initial = _finite(f"{home.get('id')} initial SoC", battery.get("initial_soc_kwh"), 0.0, capacity)
        _finite(f"{home.get('id')} reserve", battery.get("reserve_pct", 0), 0.0, 100.0)
        _finite(f"{home.get('id')} max charge", battery.get("max_charge_kw"), 0.0, 1000.0)
        _finite(f"{home.get('id')} max discharge", battery.get("max_discharge_kw"), 0.0, 1000.0)
        _finite(f"{home.get('id')} efficiency", battery.get("efficiency", 0.95), 0.1, 1.0)
        battery["initial_soc_kwh"] = initial
    scenario["homes"] = homes
    scenario["home_ids"] = ids
    scenario["your_home"] = str(scenario.get("your_home") or ids[0])
    if scenario["your_home"] not in ids:
        raise FlexError("Your home must be one of the scenario homes")
    return scenario


def validate_preferences(raw: dict[str, Any] | None, scenario: dict[str, Any]) -> dict[str, Any]:
    raw = raw or {}
    if not isinstance(raw, dict):
        raise FlexError("Preferences must be an object")
    home_id = str(raw.get("home_id") or scenario["your_home"])
    if home_id not in scenario["home_ids"]:
        raise FlexError("Preference home is not in this scenario")
    reserve = _finite("Battery reserve percentage", raw.get("battery_reserve_pct", 40), 0.0, 100.0)
    prefer_local = _bool("Prefer local before export", raw.get("prefer_local_before_export", True))
    evening = _bool("Prioritise neighbour evening demand", raw.get("prioritise_neighbour_evening", True))
    start = _hour("No-discharge start", raw.get("no_discharge_start_hour"), allow_none=True)
    end = _hour("No-discharge end", raw.get("no_discharge_end_hour"), allow_none=True)
    if (start is None) != (end is None):
        raise FlexError("No-discharge window needs both a start and an end hour")
    if start is not None and start >= end:
        raise FlexError("No-discharge end must be later than its start")
    source = str(raw.get("source") or "manual")[:40]
    return {
        "home_id": home_id,
        "battery_reserve_pct": reserve,
        "prefer_local_before_export": prefer_local,
        "prioritise_neighbour_evening": evening,
        "no_discharge_start_hour": start,
        "no_discharge_end_hour": end,
        "source": source,
    }


def validate_tariffs(raw: dict[str, Any] | None, scenario: dict[str, Any]) -> dict[str, Any]:
    raw = raw or {}
    if not isinstance(raw, dict):
        raise FlexError("Tariffs must be an object")
    defaults = scenario.get("tariffs", {})
    import_price = _finite("Import price", raw.get("import_c_kwh", defaults.get("import_c_kwh", 34)), 0.0, 200.0)
    export_price = _finite("Export price", raw.get("export_c_kwh", defaults.get("export_c_kwh", 8)), 0.0, 200.0)
    shared_price = _finite("Shared price", raw.get("shared_c_kwh", defaults.get("shared_c_kwh", 20)), 0.0, 200.0)
    transfer_limit = _finite("Sharing limit", raw.get("transfer_limit_kw", scenario.get("transfer_limit_kw", 5)), 0.0, 100.0)
    return {
        "import_c_kwh": import_price,
        "export_c_kwh": export_price,
        "shared_c_kwh": shared_price,
        "transfer_limit_kw": transfer_limit,
        "currency": "AUD",
        "note": defaults.get("note", "Illustrative energy prices. Network, supply, tax and settlement charges are excluded."),
    }


def _in_window(hour: int, start: int | None, end: int | None) -> bool:
    return start is not None and end is not None and start <= hour < end


def _proportional(amount: float, weights: dict[str, float], ids: list[str]) -> dict[str, float]:
    total = sum(max(0.0, weights.get(home_id, 0.0)) for home_id in ids)
    if amount <= EPS or total <= EPS:
        return {home_id: 0.0 for home_id in ids}
    share = min(amount, total)
    return {home_id: share * max(0.0, weights.get(home_id, 0.0)) / total for home_id in ids}


def _allocate_demands(demands: dict[str, float], amount: float, priority_ids: list[str]) -> dict[str, float]:
    received = {home_id: 0.0 for home_id in demands}
    remaining = max(0.0, amount)
    first = [home_id for home_id in priority_ids if demands.get(home_id, 0.0) > EPS]
    if first and remaining > EPS:
        first_amount = min(remaining, sum(demands[home_id] for home_id in first))
        for home_id, value in _proportional(first_amount, demands, first).items():
            received[home_id] += value
        remaining -= first_amount
    if remaining > EPS:
        left = {home_id: max(0.0, demands[home_id] - received[home_id]) for home_id in demands}
        for home_id, value in _proportional(remaining, left, list(demands)).items():
            received[home_id] += value
    return received


SERIES_KEYS = (
    "solar_kw", "demand_kw", "direct_solar_kw", "battery_charge_kw",
    "battery_own_discharge_kw", "battery_shared_kw", "solar_shared_kw",
    "shared_in_kw", "shared_out_kw", "import_kw", "export_kw",
    "soc_kwh", "surplus_kw",
)


def _empty_series() -> dict[str, list[float]]:
    return {key: [] for key in SERIES_KEYS}


def _run_scenario(scenario: dict[str, Any], preferences: dict[str, Any], tariffs: dict[str, Any], mode: str) -> dict[str, Any]:
    homes = scenario["homes"]
    ids = scenario["home_ids"]
    user_home = preferences["home_id"]
    transfer_limit = tariffs["transfer_limit_kw"]
    series = {home_id: _empty_series() for home_id in ids}
    totals = {
        home_id: {
            "solar_kwh": 0.0, "demand_kwh": 0.0, "direct_solar_kwh": 0.0,
            "battery_charge_kwh": 0.0, "battery_own_discharge_kwh": 0.0,
            "battery_shared_kwh": 0.0, "solar_shared_kwh": 0.0,
            "shared_in_kwh": 0.0, "shared_out_kwh": 0.0,
            "import_kwh": 0.0, "export_kwh": 0.0,
            "battery_start_kwh": None, "battery_end_kwh": None,
        }
        for home_id in ids
    }
    soc = {home["id"]: float(home["battery"]["initial_soc_kwh"]) for home in homes}
    initial_soc = dict(soc)
    warnings: list[str] = []
    violations: list[str] = []
    pool_rows: list[dict[str, Any]] = []

    for home in homes:
        home_id = home["id"]
        battery = home["battery"]
        reserve_pct = preferences["battery_reserve_pct"] if home_id == user_home else float(battery["reserve_pct"])
        reserve_kwh = float(battery["capacity_kwh"]) * reserve_pct / 100.0
        if home_id == user_home and soc[home_id] < reserve_kwh - EPS:
            warnings.append(
                f"{home['name']} starts below the requested reserve; it will not discharge until solar recharges it."
            )
        totals[home_id]["battery_start_kwh"] = round(initial_soc[home_id], 3)
        totals[home_id]["battery_reserve_kwh"] = round(reserve_kwh, 3)

    for hour in range(24):
        rows: dict[str, dict[str, Any]] = {}
        for home in homes:
            home_id = home["id"]
            battery = home["battery"]
            solar = float(home["solar_kw"][hour])
            demand = float(home["demand_kw"][hour])
            direct = min(solar, demand)
            surplus = solar - direct
            remaining = demand - direct
            soc_start = soc[home_id]
            reserve_pct = preferences["battery_reserve_pct"] if home_id == user_home else float(battery["reserve_pct"])
            reserve_kwh = float(battery["capacity_kwh"]) * reserve_pct / 100.0
            efficiency = float(battery["efficiency"])
            room = max(0.0, float(battery["capacity_kwh"]) - soc_start)
            charge = min(surplus, float(battery["max_charge_kw"]), room / efficiency)
            charge = max(0.0, charge)
            soc[home_id] += charge * efficiency
            surplus -= charge
            no_discharge = home_id == user_home and _in_window(
                hour, preferences["no_discharge_start_hour"], preferences["no_discharge_end_hour"]
            )
            available = max(0.0, soc[home_id] - reserve_kwh) * efficiency
            own_discharge = min(remaining, float(battery["max_discharge_kw"]), available)
            own_discharge = 0.0 if no_discharge else max(0.0, own_discharge)
            soc[home_id] -= own_discharge / efficiency
            remaining -= own_discharge
            solar_offer = 0.0
            battery_offer = 0.0
            if mode == "coordinated":
                solar_offer = surplus if home_id != user_home or preferences["prefer_local_before_export"] else 0.0
                if (
                    home_id == user_home
                    and preferences["prioritise_neighbour_evening"]
                    and EVENING_START <= hour < EVENING_END
                    and not no_discharge
                    and remaining <= EPS
                ):
                    available_for_share = max(0.0, soc[home_id] - reserve_kwh) * efficiency
                    battery_offer = min(
                        float(battery["max_discharge_kw"]) - own_discharge,
                        available_for_share,
                    )
                    battery_offer = max(0.0, battery_offer)
            rows[home_id] = {
                "solar": solar, "demand": demand, "direct": direct,
                "charge": charge, "own_discharge": own_discharge,
                "surplus": surplus, "remaining": remaining,
                "soc_start": soc_start, "soc_end": soc[home_id],
                "reserve_kwh": reserve_kwh, "efficiency": efficiency,
                "solar_offer": solar_offer, "battery_offer": battery_offer,
                "no_discharge": no_discharge, "charge_limit": float(battery["max_charge_kw"]),
                "discharge_limit": float(battery["max_discharge_kw"]),
                "capacity": float(battery["capacity_kwh"]), "initial": initial_soc[home_id],
            }

        if mode == "coordinated":
            offers = {home_id: rows[home_id]["solar_offer"] + rows[home_id]["battery_offer"] for home_id in ids}
            demands = {home_id: rows[home_id]["remaining"] for home_id in ids}
            total_offer = sum(offers.values())
            total_demand = sum(demands.values())
            shared = min(total_offer, total_demand, transfer_limit)
            shared = max(0.0, shared)
            priority_ids = (
                [home_id for home_id in ids if home_id != user_home]
                if preferences["prioritise_neighbour_evening"] and EVENING_START <= hour < EVENING_END
                else ids
            )
            received = _allocate_demands(demands, shared, priority_ids)
            allocated = {home_id: (offers[home_id] * shared / total_offer if total_offer > EPS else 0.0) for home_id in ids}
            for home_id in ids:
                row = rows[home_id]
                solar_shared = min(max(0.0, allocated[home_id]), row["solar_offer"])
                battery_shared = min(max(0.0, allocated[home_id] - solar_shared), row["battery_offer"])
                soc[home_id] -= battery_shared / row["efficiency"]
                row["soc_end"] = soc[home_id]
                row["solar_shared"] = solar_shared
                row["battery_shared"] = battery_shared
                row["shared_in"] = received[home_id]
                row["shared_out"] = solar_shared + battery_shared
                row["import"] = max(0.0, row["remaining"] - row["shared_in"])
                row["export"] = max(0.0, row["surplus"] - solar_shared)
            pool_rows.append({
                "hour": hour,
                "offered_kw": round(total_offer, 3),
                "demand_kw": round(total_demand, 3),
                "shared_kw": round(shared, 3),
                "priority_homes": priority_ids,
            })
        else:
            for home_id in ids:
                row = rows[home_id]
                row["solar_shared"] = 0.0
                row["battery_shared"] = 0.0
                row["shared_in"] = 0.0
                row["shared_out"] = 0.0
                row["import"] = row["remaining"]
                row["export"] = row["surplus"]
            pool_rows.append({"hour": hour, "offered_kw": 0.0, "demand_kw": 0.0, "shared_kw": 0.0, "priority_homes": []})

        for home_id in ids:
            row = rows[home_id]
            home_series = series[home_id]
            values = {
                "solar_kw": row["solar"], "demand_kw": row["demand"],
                "direct_solar_kw": row["direct"], "battery_charge_kw": row["charge"],
                "battery_own_discharge_kw": row["own_discharge"],
                "battery_shared_kw": row["battery_shared"],
                "solar_shared_kw": row["solar_shared"],
                "shared_in_kw": row["shared_in"], "shared_out_kw": row["shared_out"],
                "import_kw": row["import"], "export_kw": row["export"],
                "soc_kwh": row["soc_end"], "surplus_kw": row["surplus"],
            }
            for key, value in values.items():
                home_series[key].append(round(max(0.0, value), 4))
            total = totals[home_id]
            total["solar_kwh"] += row["solar"]
            total["demand_kwh"] += row["demand"]
            total["direct_solar_kwh"] += row["direct"]
            total["battery_charge_kwh"] += row["charge"]
            total["battery_own_discharge_kwh"] += row["own_discharge"]
            total["battery_shared_kwh"] += row["battery_shared"]
            total["solar_shared_kwh"] += row["solar_shared"]
            total["shared_in_kwh"] += row["shared_in"]
            total["shared_out_kwh"] += row["shared_out"]
            total["import_kwh"] += row["import"]
            total["export_kwh"] += row["export"]

            solar_balance = row["solar"] - (row["direct"] + row["charge"] + row["solar_shared"] + row["export"])
            demand_balance = row["demand"] - (row["direct"] + row["own_discharge"] + row["shared_in"] + row["import"])
            battery_balance = row["soc_end"] - (row["soc_start"] + row["charge"] * row["efficiency"] - (row["own_discharge"] + row["battery_shared"]) / row["efficiency"])
            if abs(solar_balance) > 1e-6:
                violations.append(f"home {home_id} hour {hour}: solar balance off by {solar_balance:.6f}")
            if abs(demand_balance) > 1e-6:
                violations.append(f"home {home_id} hour {hour}: demand balance off by {demand_balance:.6f}")
            if abs(battery_balance) > 1e-6:
                violations.append(f"home {home_id} hour {hour}: battery balance off by {battery_balance:.6f}")
            if row["soc_end"] < min(row["initial"], row["reserve_kwh"]) - 1e-6:
                violations.append(f"home {home_id} hour {hour}: SoC below reserve")
            if row["soc_end"] > row["capacity"] + 1e-6:
                violations.append(f"home {home_id} hour {hour}: SoC above capacity")
            if row["charge"] > row["charge_limit"] + 1e-6:
                violations.append(f"home {home_id} hour {hour}: charge above limit")
            if row["own_discharge"] + row["battery_shared"] > row["discharge_limit"] + 1e-6:
                violations.append(f"home {home_id} hour {hour}: discharge above limit")
            if row["shared_in"] > row["remaining"] + 1e-6:
                violations.append(f"home {home_id} hour {hour}: shared in above unmet demand")
            if row["shared_out"] > row["solar_offer"] + row["battery_offer"] + 1e-6:
                violations.append(f"home {home_id} hour {hour}: shared out above offer")
            if min(row["import"], row["export"], row["shared_in"], row["shared_out"], row["solar_shared"], row["battery_shared"]) < -1e-6:
                violations.append(f"home {home_id} hour {hour}: negative flow")
        if mode == "coordinated":
            total_shared = sum(row["shared_in"] for row in rows.values())
            if total_shared > transfer_limit + 1e-6:
                violations.append(f"hour {hour}: sharing above transfer limit")

    for home_id in ids:
        totals[home_id]["battery_end_kwh"] = round(soc[home_id], 3)
    return {
        "mode": mode,
        "totals": totals,
        "series": series,
        "pool": pool_rows,
        "violations": violations,
        "warnings": warnings,
    }


def _home_cost(totals: dict[str, Any], tariffs: dict[str, Any], coordinated: bool) -> float:
    cost = (totals["import_kwh"] * tariffs["import_c_kwh"] - totals["export_kwh"] * tariffs["export_c_kwh"]) / 100.0
    if coordinated:
        cost += (totals["shared_in_kwh"] - totals["shared_out_kwh"]) * tariffs["shared_c_kwh"] / 100.0
    return cost


def _summary(scenario: dict[str, Any], independent: dict[str, Any], coordinated: dict[str, Any], comparison: dict[str, Any]) -> dict[str, Any]:
    homes = {home["id"]: home for home in scenario["homes"]}
    shared = sum(total["shared_in_kwh"] for total in coordinated["totals"].values())
    imported = sum(total["import_kwh"] for total in independent["totals"].values())
    coordinated_imported = sum(total["import_kwh"] for total in coordinated["totals"].values())
    exported = sum(total["export_kwh"] for total in independent["totals"].values())
    coordinated_exported = sum(total["export_kwh"] for total in coordinated["totals"].values())
    cost_delta = comparison["cost_delta_aud"]
    supplier_id = max(homes, key=lambda home_id: coordinated["totals"][home_id]["shared_out_kwh"])
    receiver_id = max(homes, key=lambda home_id: coordinated["totals"][home_id]["shared_in_kwh"])
    if shared > 0:
        headline = (
            f"{shared:.1f} kWh moved locally. Grid imports fell by "
            f"{max(0.0, imported - coordinated_imported):.1f} kWh and exports fell by "
            f"{max(0.0, exported - coordinated_exported):.1f} kWh."
        )
    else:
        headline = "No local sharing was feasible under these constraints, so the two scenarios match."
    if abs(cost_delta) < 0.005:
        cost_sentence = "The modelled neighbourhood energy cost is unchanged."
    elif cost_delta < 0:
        cost_sentence = f"The modelled neighbourhood energy cost is ${abs(cost_delta):.2f}/day lower."
    else:
        cost_sentence = f"The modelled neighbourhood energy cost is ${cost_delta:.2f}/day higher."
    points = [
        f"{homes[supplier_id]['name']} supplied {coordinated['totals'][supplier_id]['shared_out_kwh']:.1f} kWh to the local pool.",
        f"{homes[receiver_id]['name']} received {coordinated['totals'][receiver_id]['shared_in_kwh']:.1f} kWh.",
        f"Local solar used: {comparison['independent_local_solar_kwh']:.1f} kWh independent, {comparison['coordinated_local_solar_kwh']:.1f} kWh coordinated.",
        f"Unmet demand after the sample day: {coordinated_imported:.1f} kWh coordinated; unallocated surplus: {coordinated_exported:.1f} kWh.",
        cost_sentence,
    ]
    return {"headline": headline, "points": points, "disclaimer": "Simulated daily estimate. Not a bill, a settlement, a network approval, or a guarantee of savings."}


def simulate(scenario: dict[str, Any], raw_preferences: dict[str, Any] | None = None, raw_tariffs: dict[str, Any] | None = None) -> dict[str, Any]:
    scenario = validate_scenario(scenario)
    preferences = validate_preferences(raw_preferences, scenario)
    tariffs = validate_tariffs(raw_tariffs, scenario)
    independent = _run_scenario(scenario, preferences, tariffs, "independent")
    coordinated = _run_scenario(scenario, preferences, tariffs, "coordinated")

    for result, coordinated_mode in ((independent, False), (coordinated, True)):
        total_cost = 0.0
        for home_id, total in result["totals"].items():
            cost = _home_cost(total, tariffs, coordinated_mode)
            total["energy_cost_aud"] = round(cost, 2)
            total["import_cost_aud"] = round(total["import_kwh"] * tariffs["import_c_kwh"] / 100.0, 2)
            total["export_credit_aud"] = round(total["export_kwh"] * tariffs["export_c_kwh"] / 100.0, 2)
            total["shared_purchase_aud"] = round(total["shared_in_kwh"] * tariffs["shared_c_kwh"] / 100.0, 2) if coordinated_mode else 0.0
            total["shared_sale_aud"] = round(total["shared_out_kwh"] * tariffs["shared_c_kwh"] / 100.0, 2) if coordinated_mode else 0.0
            total_cost += cost
        result["total_cost_aud"] = round(total_cost, 2)

    independent_total = independent["totals"]
    coordinated_total = coordinated["totals"]
    ind_solar = sum(total["solar_kwh"] for total in independent_total.values())
    ind_demand = sum(total["demand_kwh"] for total in independent_total.values())
    ind_import = sum(total["import_kwh"] for total in independent_total.values())
    ind_export = sum(total["export_kwh"] for total in independent_total.values())
    co_solar = sum(total["solar_kwh"] for total in coordinated_total.values())
    co_demand = sum(total["demand_kwh"] for total in coordinated_total.values())
    co_import = sum(total["import_kwh"] for total in coordinated_total.values())
    co_export = sum(total["export_kwh"] for total in coordinated_total.values())
    shared_in = sum(total["shared_in_kwh"] for total in coordinated_total.values())
    shared_out = sum(total["shared_out_kwh"] for total in coordinated_total.values())
    battery_shared = sum(total["battery_shared_kwh"] for total in coordinated_total.values())
    comparison = {
        "independent_local_solar_kwh": round(ind_solar - ind_export, 3),
        "coordinated_local_solar_kwh": round(co_solar - co_export, 3),
        "local_solar_delta_kwh": round((co_solar - co_export) - (ind_solar - ind_export), 3),
        "independent_grid_import_kwh": round(ind_import, 3),
        "coordinated_grid_import_kwh": round(co_import, 3),
        "grid_import_delta_kwh": round(co_import - ind_import, 3),
        "independent_grid_export_kwh": round(ind_export, 3),
        "coordinated_grid_export_kwh": round(co_export, 3),
        "grid_export_delta_kwh": round(co_export - ind_export, 3),
        "independent_cost_aud": independent["total_cost_aud"],
        "coordinated_cost_aud": coordinated["total_cost_aud"],
        "cost_delta_aud": round(coordinated["total_cost_aud"] - independent["total_cost_aud"], 2),
        "savings_aud": round(independent["total_cost_aud"] - coordinated["total_cost_aud"], 2),
        "shared_kwh": round(shared_in, 3),
        "shared_out_kwh": round(shared_out, 3),
        "battery_shared_kwh": round(battery_shared, 3),
        "solar_kwh": round(co_solar, 3),
        "demand_kwh": round(co_demand, 3),
        "self_sufficiency_independent_pct": round((1.0 - ind_import / ind_demand) * 100.0, 1) if ind_demand else 0.0,
        "self_sufficiency_coordinated_pct": round((1.0 - co_import / co_demand) * 100.0, 1) if co_demand else 0.0,
    }
    all_violations = independent["violations"] + coordinated["violations"]
    warnings = list(dict.fromkeys(independent["warnings"] + coordinated["warnings"]))
    constraints = {
        "ok": not all_violations,
        "violations": all_violations,
        "warnings": warnings,
        "checks": [
            {"name": "Energy balance at every home and interval", "passed": not any("balance" in item for item in all_violations)},
            {"name": "Battery capacity, reserve and power limits", "passed": not any("SoC" in item or "charge" in item or "discharge" in item for item in all_violations)},
            {"name": "Sharing does not exceed supply, demand or transfer limit", "passed": not any("shared" in item or "sharing" in item for item in all_violations)},
            {"name": "All flows are finite and non-negative", "passed": not any("negative" in item for item in all_violations)},
        ],
    }
    monthly = {
        "days": 30,
        "assumption": "This sample day repeated 30 times. No seasonal, tariff, demand or battery change is assumed.",
        "independent_cost_aud": round(independent["total_cost_aud"] * 30, 2),
        "coordinated_cost_aud": round(coordinated["total_cost_aud"] * 30, 2),
        "savings_aud": round((independent["total_cost_aud"] - coordinated["total_cost_aud"]) * 30, 2),
        "independent_import_kwh": round(ind_import * 30, 1),
        "coordinated_import_kwh": round(co_import * 30, 1),
    }
    return {
        "plan_version": "flex-1",
        "scenario": {
            "id": scenario.get("id"), "name": scenario.get("name"), "region": scenario.get("region"),
            "region_name": scenario.get("region_name"), "label": scenario.get("label"),
            "source": scenario.get("source"), "kind": scenario.get("kind", "synthetic"),
            "hours": scenario["hours"], "labels": scenario["labels"],
        },
        "homes": [
            {
                "id": home["id"], "name": home["name"], "short": home.get("short", home["id"][-1].upper()),
                "color": home.get("color", "sage"),
                "solar_kw": home["solar_kw"], "demand_kw": home["demand_kw"],
                "daily_solar_kwh": round(sum(home["solar_kw"]), 2),
                "daily_demand_kwh": round(sum(home["demand_kw"]), 2),
                "battery": home["battery"],
            }
            for home in scenario["homes"]
        ],
        "preferences": preferences,
        "tariffs": tariffs,
        "independent": independent,
        "coordinated": coordinated,
        "comparison": comparison,
        "monthly": monthly,
        "constraints": constraints,
        "summary": _summary(scenario, independent, coordinated, comparison),
    }
