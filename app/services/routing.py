import uuid
from datetime import datetime, timedelta

import httpx

from app.config import settings
from app.services import crime
from app.services.geocoding import resolve_point
from app.utils import geo, time_utils

ORS_URL = "https://api.openrouteservice.org/v2/directions/{profile}"
MODE_MAP = {
    "car": "driving-car",
    "motorcycle": "driving-car",
    "bicycle": "cycling-regular",
    "walking": "foot-walking",
    "public_transport": "driving-car",
}
MODE_NOTES = {
    "motorcycle": "No motorcycle profile in OpenStreetMap routing; used car routes as a proxy.",
    "public_transport": "No transit schedules available; approximated with road routes plus a rough delay. Treat times as rough.",
}

ROUTE_STORE: dict[str, dict] = {}  # route_id -> route (in-memory, prototype only)


def _remember(route: dict) -> None:
    ROUTE_STORE[route["route_id"]] = route
    while len(ROUTE_STORE) > 400:
        ROUTE_STORE.pop(next(iter(ROUTE_STORE)))


def _traffic_factor(dep: datetime, mode: str) -> float:
    """Rough Karachi congestion multiplier by time of day. An assumption, not live data. Tune freely."""
    if mode in ("bicycle", "walking"):
        return 1.0
    h = dep.hour + dep.minute / 60
    if 7.5 <= h < 10.5:
        f = 1.35
    elif 17 <= h < 21:
        f = 1.45
    elif 11 <= h < 17:
        f = 1.15
    elif h >= 22 or h < 6:
        f = 1.0
    else:
        f = 1.1
    if dep.weekday() >= 5:  # Sat/Sun
        f = 1 + (f - 1) * 0.6
    if mode == "motorcycle":
        f = 1 + (f - 1) * 0.6
    return f


def _call(profile: str, coords: list[tuple[float, float]], alternatives: int = 0) -> list[dict]:
    body = {
        "coordinates": [[lng, lat] for lat, lng in coords],  # ORS wants [lon, lat]
        "instructions": True,
        "geometry": True,
    }
    if alternatives > 1:
        body["alternative_routes"] = {
            "target_count": min(alternatives, 3),
            "weight_factor": 1.6,
            "share_factor": 0.6,
        }
    headers = {"Authorization": settings.ors_api_key, "Content-Type": "application/json"}
    r = httpx.post(ORS_URL.format(profile=profile), json=body, headers=headers, timeout=30)
    if r.status_code != 200:
        raise RuntimeError(f"OpenRouteService {r.status_code}: {r.text[:300]}")
    return r.json().get("routes", [])


def _via_label(route: dict) -> str:
    dist_by_name: dict[str, float] = {}
    for seg in route.get("segments", []):
        for step in seg.get("steps", []):
            name = (step.get("name") or "").strip()
            if name and name != "-":
                dist_by_name[name] = dist_by_name.get(name, 0.0) + float(step.get("distance", 0))
    top = sorted(dist_by_name, key=dist_by_name.get, reverse=True)[:3]
    return ("via " + ", ".join(top)) if top else ""


def _parse(r: dict) -> dict | None:
    enc = r.get("geometry")
    if not enc or not isinstance(enc, str):
        return None
    summary = r.get("summary") or {}
    return {
        "enc": enc,
        "distance_m": float(summary.get("distance", 0)),
        "duration_s": float(summary.get("duration", 0)),
        "description": _via_label(r),
        "pts": geo.sample_points(geo.decode_polyline(enc), 0.25),
    }


def _fetch(profile: str, coords: list[tuple[float, float]], alternatives: int = 0) -> list[dict]:
    return [p for p in (_parse(r) for r in _call(profile, coords, alternatives)) if p]


def _initial(o, d, profile: str, n: int) -> list[dict]:
    try:
        return _fetch(profile, [o, d], alternatives=n)
    except RuntimeError:
        return _fetch(profile, [o, d], alternatives=0)  # e.g. trip too long for alternatives


def _variants(o, d, profile: str, need: int, existing: list[dict]) -> list[dict]:
    """Extra candidates by routing through a waypoint beside the straight line."""
    dist_km = geo.haversine_km(*o, *d)
    brg = geo.bearing_deg(*o, *d)
    spread = max(0.4, min(dist_km * 0.18, 4.0))
    attempts = [
        (0.5, spread), (0.5, -spread), (0.35, spread * 1.6), (0.65, -spread * 1.6),
        (0.35, -spread * 1.6), (0.65, spread * 1.6), (0.5, spread * 2.4), (0.5, -spread * 2.4),
    ]
    shortest_km = min(p["distance_m"] for p in existing) / 1000
    pool = list(existing)
    found: list[dict] = []
    for frac, side in attempts[: min(need * 2, 8)]:
        if len(found) >= need:
            break
        base = geo.point_along(o, d, frac)
        via = geo.offset_point(base[0], base[1], brg + (90 if side > 0 else -90), abs(side))
        try:
            candidates = _fetch(profile, [o, via, d])
        except RuntimeError:
            continue
        for c in candidates:
            too_long = c["distance_m"] / 1000 > shortest_km * 1.7
            duplicate = any(geo.overlap_ratio(c["pts"], p["pts"]) >= 0.9 for p in pool)
            if not too_long and not duplicate:
                found.append(c)
                pool.append(c)
    return found


def fetch_routes(origin: str, destination: str, mode: str, departure_iso: str | None, num_routes: int) -> dict:
    if mode not in MODE_MAP:
        raise ValueError(f"Unknown mode {mode!r}. Use one of {list(MODE_MAP)}")
    num_routes = max(1, min(int(num_routes), settings.max_routes))

    o_lat, o_lng, o_label = resolve_point(origin)
    d_lat, d_lng, d_label = resolve_point(destination)
    o, d = (o_lat, o_lng), (d_lat, d_lng)
    dep = time_utils.parse_time(departure_iso)
    profile = MODE_MAP[mode]

    notes: list[str] = []
    if mode not in ("bicycle", "walking"):
        notes.append("OpenStreetMap routing has no live traffic; durations include a rough peak-hour estimate.")
    if mode in MODE_NOTES:
        notes.append(MODE_NOTES[mode])

    parsed = _initial(o, d, profile, num_routes)
    if not parsed:
        return {"error": "No route found between these places for this mode."}

    if len(parsed) < num_routes:
        parsed += _variants(o, d, profile, num_routes - len(parsed), parsed)

    parsed.sort(key=lambda p: p["duration_s"])
    parsed = parsed[:num_routes]
    if len(parsed) < num_routes:
        notes.append(f"Only {len(parsed)} distinct routes found (requested {num_routes}).")

    factor = _traffic_factor(dep, mode)
    batch = uuid.uuid4().hex[:6]
    out_routes = []
    for i, p in enumerate(parsed, start=1):
        base = p["duration_s"]
        dur = base * factor
        if mode == "public_transport":
            dur = dur * 1.3 + 600
        dur_min = max(1, round(dur / 60))
        static_min = max(1, round(base / 60))

        route = {
            "route_id": f"r_{uuid.uuid4().hex[:8]}",
            "batch": batch,
            "label": f"Route {i}",
            "summary": p["description"] or f"Route {i}",
            "mode": mode,
            "travel_mode": profile,
            "distance_km": round(p["distance_m"] / 1000, 2),
            "duration_min": dur_min,
            "static_duration_min": static_min,
            "traffic_delay_min": max(0, dur_min - static_min),
            "delay_ratio": factor - 1,
            "traffic_live": False,
            "departure_iso": dep.isoformat(),
            "arrival_iso": (dep + timedelta(seconds=dur)).isoformat(),
            "polyline": p["enc"],
            "sample": p["pts"],
            "origin": {"lat": o_lat, "lng": o_lng, "label": o_label},
            "destination": {"lat": d_lat, "lng": d_lng, "label": d_label},
            "crime": None,
            "scores": None,
        }
        _remember(route)
        out_routes.append({
            "route_id": route["route_id"],
            "label": route["label"],
            "summary": route["summary"],
            "distance_km": route["distance_km"],
            "duration_min": route["duration_min"],
            "traffic_delay_min": route["traffic_delay_min"],
            "departure_time": route["departure_iso"],
            "arrival_time": route["arrival_iso"],
            "areas_along_route": crime.areas_along(p["pts"])[:8],
        })

    return {
        "origin": o_label,
        "destination": d_label,
        "mode": mode,
        "traffic_live": False,
        "notes": notes,
        "routes": out_routes,
    }