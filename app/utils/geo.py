import math

import polyline as _polyline

EARTH_KM = 6371.0088


def haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = p2 - p1
    dl = math.radians(lng2 - lng1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * EARTH_KM * math.asin(math.sqrt(a))


def bearing_deg(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dl = math.radians(lng2 - lng1)
    y = math.sin(dl) * math.cos(p2)
    x = math.cos(p1) * math.sin(p2) - math.sin(p1) * math.cos(p2) * math.cos(dl)
    return (math.degrees(math.atan2(y, x)) + 360) % 360


def offset_point(lat: float, lng: float, bearing: float, dist_km: float) -> tuple[float, float]:
    br = math.radians(bearing)
    d = dist_km / EARTH_KM
    p1, l1 = math.radians(lat), math.radians(lng)
    p2 = math.asin(math.sin(p1) * math.cos(d) + math.cos(p1) * math.sin(d) * math.cos(br))
    l2 = l1 + math.atan2(math.sin(br) * math.sin(d) * math.cos(p1), math.cos(d) - math.sin(p1) * math.sin(p2))
    return math.degrees(p2), (math.degrees(l2) + 540) % 360 - 180


def point_along(a: tuple[float, float], b: tuple[float, float], frac: float) -> tuple[float, float]:
    return a[0] + (b[0] - a[0]) * frac, a[1] + (b[1] - a[1]) * frac


def decode_polyline(encoded: str) -> list[tuple[float, float]]:
    return _polyline.decode(encoded)  # [(lat, lng), ...]


def sample_points(points: list[tuple[float, float]], step_km: float = 0.25) -> list[tuple[float, float]]:
    if not points:
        return []
    out = [points[0]]
    acc = 0.0
    for a, b in zip(points, points[1:]):
        acc += haversine_km(a[0], a[1], b[0], b[1])
        if acc >= step_km:
            out.append(b)
            acc = 0.0
    if out[-1] != points[-1]:
        out.append(points[-1])
    return out


def overlap_ratio(a: list[tuple[float, float]], b: list[tuple[float, float]], tol_km: float = 0.08) -> float:
    """Share of points in `a` that lie within tol_km of some point in `b`."""
    if not a or not b:
        return 0.0
    hits = 0
    for p in a:
        if any(haversine_km(p[0], p[1], q[0], q[1]) <= tol_km for q in b):
            hits += 1
    return hits / len(a)