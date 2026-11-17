from datetime import datetime, timedelta

import httpx

from app.config import settings
from app.utils import time_utils

CURRENT_URL = "https://api.openweathermap.org/data/2.5/weather"
FORECAST_URL = "https://api.openweathermap.org/data/2.5/forecast"

SENSITIVITY = {"car": 0.6, "public_transport": 0.7, "walking": 1.0, "bicycle": 1.2, "motorcycle": 1.2}


def _risk(main: str, temp: float, wind: float, vis: float | None, rain_h: float, mode: str) -> int:
    r = 0.0
    m = main.lower()
    if m == "thunderstorm":
        r += 60
    elif m in {"rain", "drizzle"}:
        r += 15 + min(rain_h * 8, 35)
    elif m in {"mist", "fog", "haze", "smoke", "dust", "sand"}:
        r += 15
    if vis is not None and vis < 2000:
        r += 15
    if temp >= 42:
        r += 30
    elif temp >= 38:
        r += 15
    if wind >= 14:
        r += 20
    elif wind >= 9:
        r += 8
    return int(min(100, r * SENSITIVITY.get(mode, 1.0)))


def fetch(lat: float, lng: float, when: datetime, mode: str) -> dict:
    now = time_utils.now_local()
    delta = when - now
    params = {"lat": lat, "lon": lng, "appid": settings.openweather_api_key, "units": "metric"}

    source, entry = "current", None
    if timedelta(minutes=90) < delta < timedelta(days=5):
        r = httpx.get(FORECAST_URL, params=params, timeout=15)
        r.raise_for_status()
        items = r.json().get("list", [])
        if items:
            entry = min(items, key=lambda it: abs(it["dt"] - when.timestamp()))
            source = "forecast"
    if entry is None:
        r = httpx.get(CURRENT_URL, params=params, timeout=15)
        r.raise_for_status()
        entry = r.json()

    w0 = (entry.get("weather") or [{}])[0]
    main = entry.get("main", {})
    wind = float(entry.get("wind", {}).get("speed", 0.0))
    vis = entry.get("visibility")
    rain = entry.get("rain", {}) or {}
    rain_h = float(rain.get("1h") or (float(rain.get("3h", 0)) / 3 if rain.get("3h") else 0.0))
    temp = float(main.get("temp", 0.0))

    risk = _risk(w0.get("main", ""), temp, wind, vis, rain_h, mode)
    return {
        "source": source,
        "condition": w0.get("description"),
        "temperature_c": temp,
        "feels_like_c": main.get("feels_like"),
        "wind_ms": wind,
        "rain_mm_per_h": round(rain_h, 2),
        "visibility_m": vis,
        "weather_risk": risk,
        "level": "low" if risk < 25 else "medium" if risk < 55 else "high",
        "note": "Weather is location-level; it is the same for every route.",
    }