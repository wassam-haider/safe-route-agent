import functools
import re
import threading
import time

import httpx

from app.config import settings

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
ORS_GEOCODE_URL = "https://api.openrouteservice.org/geocode/search"
KARACHI_VIEWBOX = "66.80,25.25,67.45,24.75"  # left,top,right,bottom
LAT_MIN, LAT_MAX, LNG_MIN, LNG_MAX = 24.70, 25.30, 66.70, 67.50

_LATLNG = re.compile(r"^\s*(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)\s*$")
_lock = threading.Lock()
_last_call = 0.0


def _throttle() -> None:
    """Nominatim public server: max 1 request per second."""
    global _last_call
    with _lock:
        wait = 1.1 - (time.monotonic() - _last_call)
        if wait > 0:
            time.sleep(wait)
        _last_call = time.monotonic()


def _in_karachi(lat: float, lng: float) -> bool:
    return LAT_MIN <= lat <= LAT_MAX and LNG_MIN <= lng <= LNG_MAX


def _nominatim(q: str) -> dict | None:
    _throttle()
    params = {
        "q": q,
        "format": "jsonv2",
        "limit": 1,
        "countrycodes": "pk",
        "viewbox": KARACHI_VIEWBOX,
        "bounded": 1,
    }
    r = httpx.get(NOMINATIM_URL, params=params, headers={"User-Agent": settings.osm_user_agent}, timeout=15)
    r.raise_for_status()
    data = r.json()
    if not data:
        return None
    top = data[0]
    return {
        "formatted_address": top.get("display_name", q),
        "lat": float(top["lat"]),
        "lng": float(top["lon"]),
        "source": "nominatim",
        "osm_ref": f'{top.get("osm_type")}/{top.get("osm_id")}',
    }


def _ors_geocode(q: str) -> dict | None:
    """Fallback: ORS geocoder (same API key as routing)."""
    if not settings.ors_api_key:
        return None
    params = {
        "api_key": settings.ors_api_key,
        "text": q,
        "size": 1,
        "boundary.country": "PK",
        "focus.point.lat": 24.8607,
        "focus.point.lon": 67.0011,
    }
    r = httpx.get(ORS_GEOCODE_URL, params=params, timeout=15)
    r.raise_for_status()
    feats = r.json().get("features") or []
    if not feats:
        return None
    f = feats[0]
    lng, lat = f["geometry"]["coordinates"]
    props = f.get("properties", {})
    return {
        "formatted_address": props.get("label", q),
        "lat": float(lat),
        "lng": float(lng),
        "source": "ors-geocoder",
        "confidence": props.get("confidence"),
    }


@functools.lru_cache(maxsize=512)
def geocode(query: str) -> dict | None:
    q = query.strip()
    variants = [q] if "karachi" in q.lower() else [q, f"{q}, Karachi"]
    for v in variants:
        res = _nominatim(v)
        if res and _in_karachi(res["lat"], res["lng"]):
            return res
    res = _ors_geocode(variants[-1])
    if res and _in_karachi(res["lat"], res["lng"]):
        return res
    return None


def resolve_point(text: str) -> tuple[float, float, str]:
    """'lat,lng' or a place name -> (lat, lng, label)."""
    m = _LATLNG.match(text)
    if m:
        return float(m.group(1)), float(m.group(2)), text.strip()
    res = geocode(text)
    if not res:
        raise ValueError(
            f"Could not find {text!r} in OpenStreetMap data. Ask the user for a nearby road, area, or a 'lat,lng'."
        )
    return res["lat"], res["lng"], res["formatted_address"]