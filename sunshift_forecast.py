"""Open-Meteo day-ahead weather input for the SunShift scenario planner."""

from __future__ import annotations

import json
import urllib.parse
import urllib.request
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

REGIONS = {
    "NSW": {"name": "New South Wales · NEM region NSW1", "lat": -33.8688, "lon": 151.2093},
    "SA": {"name": "South Australia · NEM region SA1", "lat": -34.9285, "lon": 138.6001},
    "VIC": {"name": "Victoria · NEM region VIC1", "lat": -37.8136, "lon": 144.9631},
    "QLD": {"name": "Queensland · NEM region QLD1", "lat": -27.4698, "lon": 153.0251},
    "TAS": {"name": "Tasmania · NEM region TAS1", "lat": -42.8821, "lon": 147.3272},
}


def fetch_forecast(code: str, region: dict) -> dict:
    params = urllib.parse.urlencode({
        "latitude": region["lat"],
        "longitude": region["lon"],
        "hourly": "shortwave_radiation,temperature_2m,cloud_cover",
        "timezone": "Australia/Sydney",
        "forecast_days": 3,
    })
    request = urllib.request.Request(
        f"https://api.open-meteo.com/v1/forecast?{params}",
        headers={"User-Agent": "SunShift-NEM-prototype/0.1"},
    )
    with urllib.request.urlopen(request, timeout=10) as response:
        raw = json.loads(response.read().decode("utf-8"))
    hourly = raw["hourly"]
    times = hourly["time"]
    radiation = hourly["shortwave_radiation"]
    temperatures = hourly["temperature_2m"]
    now = datetime.now(ZoneInfo("Australia/Sydney"))
    target_day = now.date() if now.hour < 5 else (now + timedelta(days=1)).date()
    selected = [i for i, stamp in enumerate(times) if stamp.startswith(target_day.isoformat())]
    if len(selected) < 24:
        target_day += timedelta(days=1)
        selected = [i for i, stamp in enumerate(times) if stamp.startswith(target_day.isoformat())]
    selected = selected[:24]
    if len(selected) != 24:
        raise ValueError("provider returned fewer than 24 hours for the planning day")
    return {
        "region": code,
        "region_name": region["name"],
        "date": target_day.isoformat(),
        "hours": [int(times[i][11:13]) for i in selected],
        "labels": [times[i][11:16] for i in selected],
        "ghi_wm2": [float(radiation[i] or 0) for i in selected],
        "temperature_c": [float(temperatures[i]) for i in selected],
        "data_quality": "forecast",
        "source_label": "Open-Meteo hourly forecast · solar radiation and temperature",
        "attribution": "Weather data by Open-Meteo (CC BY 4.0). Forecast, not a metered NEM feed.",
    }
