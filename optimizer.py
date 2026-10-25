"""Small, deterministic dispatch planner for the SunShift NEM prototype.

The planner is an optimization prototype, not a grid-control system. It keeps
the flexible energy requirement fixed and schedules it first into forecast
on-site solar surplus, then into the lowest-import hours to reduce the peak.
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from typing import Any


class PlanError(ValueError):
    """Raised when inputs cannot describe a safe, feasible demo plan."""


@dataclass(frozen=True)
class PlanInputs:
    pv_capacity_kw: float = 42.0
    average_site_load_kw: float = 17.0
    flexible_energy_kwh: float = 18.0
    max_flexible_power_kw: float = 6.0
    transfer_limit_kw: float = 24.0
    p2p_price_c_kwh: float = 18.0
    grid_reference_price_c_kwh: float = 32.0
    emissions_factor_kg_kwh: float = 0.65
    charge_from_hour: int = 7
    charge_by_hour: int = 22
    baseline_from_hour: int = 17
    baseline_by_hour: int = 22


def _number(name: str, value: Any, low: float, high: float) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise PlanError(f"{name} must be a number") from exc
    if not math.isfinite(result) or result < low or result > high:
        raise PlanError(f"{name} must be between {low:g} and {high:g}")
    return result


def _hour(name: str, value: Any) -> int:
    if isinstance(value, bool):
        raise PlanError(f"{name} must be an hour from 0 to 24")
    try:
        result = int(value)
    except (TypeError, ValueError) as exc:
        raise PlanError(f"{name} must be an hour from 0 to 24") from exc
    if result < 0 or result > 24:
        raise PlanError(f"{name} must be an hour from 0 to 24")
    return result


def validate_inputs(raw: dict[str, Any]) -> PlanInputs:
    fields = PlanInputs.__dataclass_fields__
    values = {key: raw.get(key, field.default) for key, field in fields.items()}
    result = PlanInputs(
        pv_capacity_kw=_number("PV capacity", values["pv_capacity_kw"], 0.0, 5000.0),
        average_site_load_kw=_number("Average site load", values["average_site_load_kw"], 0.1, 5000.0),
        flexible_energy_kwh=_number("Flexible energy", values["flexible_energy_kwh"], 0.0, 10000.0),
        max_flexible_power_kw=_number("Maximum flexible power", values["max_flexible_power_kw"], 0.1, 1000.0),
        transfer_limit_kw=_number("Microgrid transfer limit", values["transfer_limit_kw"], 0.1, 5000.0),
        p2p_price_c_kwh=_number("P2P contract price", values["p2p_price_c_kwh"], 0.0, 200.0),
        grid_reference_price_c_kwh=_number("Grid reference price", values["grid_reference_price_c_kwh"], 0.0, 200.0),
        emissions_factor_kg_kwh=_number("Emissions factor", values["emissions_factor_kg_kwh"], 0.0, 2.0),
        charge_from_hour=_hour("Charge window start", values["charge_from_hour"]),
        charge_by_hour=_hour("Charge window end", values["charge_by_hour"]),
        baseline_from_hour=_hour("Baseline start", values["baseline_from_hour"]),
        baseline_by_hour=_hour("Baseline end", values["baseline_by_hour"]),
    )
    if result.charge_by_hour <= result.charge_from_hour:
        raise PlanError("Charge window end must be after its start")
    if result.baseline_by_hour <= result.baseline_from_hour:
        raise PlanError("Baseline window end must be after its start")
    if result.flexible_energy_kwh > 0 and result.flexible_energy_kwh > result.max_flexible_power_kw * (result.charge_by_hour - result.charge_from_hour):
        raise PlanError("Flexible energy exceeds the available charge-window capacity")
    if result.flexible_energy_kwh > 0 and result.flexible_energy_kwh > result.max_flexible_power_kw * (result.baseline_by_hour - result.baseline_from_hour):
        raise PlanError("Baseline window is too short for this energy and power limit")
    return result


def _baseline_schedule(inputs: PlanInputs, hours: list[int]) -> list[float]:
    result = [0.0] * len(hours)
    eligible = [i for i, hour in enumerate(hours) if inputs.baseline_from_hour <= hour < inputs.baseline_by_hour]
    if not eligible and inputs.flexible_energy_kwh:
        raise PlanError("The baseline charging window is outside the forecast horizon")
    remaining = inputs.flexible_energy_kwh
    for index in eligible:
        amount = min(inputs.max_flexible_power_kw, remaining / max(1, len(eligible) - eligible.index(index)))
        result[index] = amount
        remaining -= amount
    if remaining > 1e-7:
        raise PlanError("Baseline schedule cannot fit within the power limit")
    return result


def _optimized_schedule(
    inputs: PlanInputs, hours: list[int], solar: list[float], load: list[float]
) -> list[float]:
    result = [0.0] * len(hours)
    eligible = [i for i, hour in enumerate(hours) if inputs.charge_from_hour <= hour < inputs.charge_by_hour]
    remaining = inputs.flexible_energy_kwh

    # Pass 1: consume forecast solar that would otherwise be exported/curtailed.
    surplus_order = sorted(eligible, key=lambda i: (-(solar[i] - load[i]), hours[i]))
    for index in surplus_order:
        solar_surplus = max(0.0, solar[index] - load[index])
        amount = min(inputs.max_flexible_power_kw, solar_surplus, remaining)
        result[index] += amount
        remaining -= amount
        if remaining <= 1e-8:
            return result

    # Pass 2: use remaining flexibility to flatten grid imports. This is a
    # bounded water-fill across the hours with the lowest projected imports.
    candidates = sorted(eligible, key=lambda i: (max(0.0, load[i] - solar[i]), hours[i]))
    for index in candidates:
        amount = min(inputs.max_flexible_power_kw - result[index], remaining)
        if amount > 0:
            result[index] += amount
            remaining -= amount
        if remaining <= 1e-8:
            return result
    if remaining > 1e-7:
        raise PlanError("Flexible energy does not fit in the selected charge window")
    return result


def optimize(raw_inputs: dict[str, Any], weather: dict[str, Any]) -> dict[str, Any]:
    inputs = validate_inputs(raw_inputs)
    try:
        hours = [int(value) for value in weather["hours"]]
        ghi = [float(value) for value in weather["ghi_wm2"]]
    except (KeyError, TypeError, ValueError) as exc:
        raise PlanError("Weather input must include 24 hour values and solar irradiance") from exc
    if len(hours) != 24 or len(ghi) != 24:
        raise PlanError("Exactly 24 hourly forecast values are required")
    if any(hour < 0 or hour > 23 for hour in hours):
        raise PlanError("Forecast hours must be from 0 to 23")
    if any(not math.isfinite(value) or value < 0 or value > 1500 for value in ghi):
        raise PlanError("Solar irradiance values must be finite and between 0 and 1500 W/m²")

    # A representative small-community-site shape, scaled by the user's
    # average load. This is explicitly illustrative unless replaced by meter data.
    shape = [0.68, 0.62, 0.59, 0.58, 0.59, 0.65, 0.77, 0.94, 1.08, 1.16, 1.20, 1.18,
             1.13, 1.08, 1.03, 1.02, 1.08, 1.18, 1.27, 1.28, 1.19, 1.05, 0.88, 0.75]
    mean_shape = sum(shape) / len(shape)
    modelled_load = [inputs.average_site_load_kw * value / mean_shape for value in shape]
    modelled_solar = [inputs.pv_capacity_kw * value / 1000.0 * 0.82 for value in ghi]
    load_override = weather.get("buyer_load_kwh_override")
    solar_override = weather.get("solar_kwh_override")
    if (load_override is None) != (solar_override is None):
        raise PlanError("Uploaded participant profile must include both seller solar and buyer load")
    if load_override is not None:
        try:
            load = [float(value) for value in load_override]
            solar = [float(value) for value in solar_override]
        except (TypeError, ValueError) as exc:
            raise PlanError("Uploaded participant profile must contain numeric kWh values") from exc
        if len(load) != 24 or len(solar) != 24:
            raise PlanError("Uploaded participant profile must contain exactly 24 hourly rows")
        if any(not math.isfinite(value) or value < 0 or value > 10000 for value in load + solar):
            raise PlanError("Uploaded participant values must be finite and between 0 and 10000 kWh")
    else:
        load = modelled_load
        solar = modelled_solar
    baseline_flex = _baseline_schedule(inputs, hours)
    optimized_flex = _optimized_schedule(inputs, hours, solar, load)
    # Two-participant virtual microgrid: the solar producer and consuming site
    # are distinct. Baseline assumes no peer match (seller exports; buyer imports).
    # The coordinated case matches solar to buyer demand within the transfer cap.
    p2p_shared = [min(inputs.transfer_limit_kw, solar[i], load[i] + optimized_flex[i]) for i in range(24)]
    baseline_grid = [load[i] + baseline_flex[i] for i in range(24)]
    optimized_grid = [max(0.0, load[i] + optimized_flex[i] - p2p_shared[i]) for i in range(24)]
    baseline_import = sum(baseline_grid)
    optimized_import = sum(optimized_grid)
    baseline_peak = max(baseline_grid)
    optimized_peak = max(optimized_grid)
    baseline_matched = 0.0
    optimized_matched = sum(p2p_shared)
    baseline_cost = baseline_import * inputs.grid_reference_price_c_kwh / 100.0
    coordinated_cost = (optimized_import * inputs.grid_reference_price_c_kwh + optimized_matched * inputs.p2p_price_c_kwh) / 100.0
    return {
        "hours": hours,
        "solar_kwh": [round(v, 3) for v in solar],
        "site_load_kwh": [round(v, 3) for v in load],
        "baseline_flexible_kwh": [round(v, 3) for v in baseline_flex],
        "optimized_flexible_kwh": [round(v, 3) for v in optimized_flex],
        "p2p_shared_kwh": [round(v, 3) for v in p2p_shared],
        "baseline_grid_import_kwh": [round(v, 3) for v in baseline_grid],
        "optimized_grid_import_kwh": [round(v, 3) for v in optimized_grid],
        "metrics": {
            "flexible_energy_kwh": round(inputs.flexible_energy_kwh, 3),
            "baseline_grid_import_kwh": round(baseline_import, 3),
            "optimized_grid_import_kwh": round(optimized_import, 3),
            "grid_import_avoided_kwh": round(max(0.0, baseline_import - optimized_import), 3),
            "baseline_peak_kw": round(baseline_peak, 3),
            "optimized_peak_kw": round(optimized_peak, 3),
            "peak_reduction_kw": round(max(0.0, baseline_peak - optimized_peak), 3),
            "baseline_solar_used_kwh": round(baseline_matched, 3),
            "optimized_solar_used_kwh": round(optimized_matched, 3),
            "additional_solar_used_kwh": round(max(0.0, optimized_matched - baseline_matched), 3),
            "p2p_energy_matched_kwh": round(optimized_matched, 3),
            "baseline_buyer_energy_cost_aud": round(baseline_cost, 2),
            "coordinated_buyer_energy_cost_aud": round(coordinated_cost, 2),
            "buyer_energy_cost_saved_aud": round(baseline_cost - coordinated_cost, 2),
            "seller_p2p_revenue_aud": round(optimized_matched * inputs.p2p_price_c_kwh / 100.0, 2),
            "solar_export_or_unmatched_kwh": round(sum(max(0.0, solar[i] - p2p_shared[i]) for i in range(24)), 3),
            "estimated_co2_avoided_kg": round(max(0.0, baseline_import - optimized_import) * inputs.emissions_factor_kg_kwh, 3),
            "emissions_factor_kg_kwh": inputs.emissions_factor_kg_kwh,
            "flexible_energy_conserved": abs(sum(optimized_flex) - inputs.flexible_energy_kwh) < 1e-6,
        },
        "inputs": asdict(inputs),
        "method": "Solar-surplus-first flexible dispatch, peer matching under transfer cap",
        "profile_mode": "user_supplied" if load_override is not None else "illustrative_or_forecast_solar_with_illustrative_load",
        "data_quality": weather.get("data_quality", "illustrative"),
        "source_label": weather.get("source_label", "Illustrative demo forecast"),
    }
