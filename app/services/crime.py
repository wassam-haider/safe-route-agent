import functools
import json
from collections import Counter
from datetime import datetime

import pandas as pd

from app.config import settings
from app.utils import geo, time_utils

# first match wins, so order from most to least severe
SEVERITY = [
    ("murder", 5.0), ("kidnap", 5.0), ("abduct", 5.0), ("terror", 5.0), ("blast", 5.0),
    ("carjack", 4.5), ("robbery", 4.0), ("dacoity", 4.0), ("mugging", 4.0), ("snatch", 4.0),
    ("assault", 3.0), ("attack", 3.0), ("violence", 3.0), ("extortion", 3.0),
    ("theft", 2.5), ("burglary", 2.5), ("lifting", 2.5), ("stolen", 2.5),
]
MODE_BOOST = {
    "walking": [("snatch", 1.5), ("robbery", 1.3), ("mugging", 1.3), ("assault", 1.2)],
    "motorcycle": [("snatch", 1.5), ("robbery", 1.3), ("vehicle", 1.4), ("bike", 1.4), ("motorcycle", 1.4)],
    "bicycle": [("snatch", 1.3), ("robbery", 1.2), ("theft", 1.2)],
    "car": [("carjack", 1.5), ("vehicle", 1.3), ("robbery", 1.2)],
    "public_transport": [("snatch", 1.3), ("robbery", 1.2), ("pickpocket", 1.4)],
}


def _severity(c: str) -> float:
    for key, val in SEVERITY:
        if key in c:
            return val
    return 2.0


def _mode_mult(mode: str, c: str) -> float:
    m = 1.0
    for key, val in MODE_BOOST.get(mode, []):
        if key in c:
            m = max(m, val)
    return m


@functools.lru_cache(maxsize=1)
def load_crime() -> pd.DataFrame:
    path = settings.crime_csv_path
    if not path.exists():
        raise FileNotFoundError(f"Crime CSV not found at {path}. Download the Kaggle dataset and save it there.")
    df = pd.read_csv(path)
    df.columns = [str(c).strip() for c in df.columns]
    missing = {"Area", "Hour_24", "Crime_Type"} - set(df.columns)
    if missing:
        raise ValueError(f"Crime CSV is missing columns: {sorted(missing)}")
    df["Area"] = df["Area"].astype(str).str.strip()
    df["Hour_24"] = pd.to_numeric(df["Hour_24"], errors="coerce").fillna(-1).astype(int)
    df["crime_l"] = df["Crime_Type"].astype(str).str.lower()
    df["severity"] = df["crime_l"].map(_severity).astype(float)
    return df


@functools.lru_cache(maxsize=1)
def load_centroids() -> dict[str, tuple[float, float]]:
    p = settings.centroids_path
    if not p.exists():
        return {}
    raw = json.loads(p.read_text(encoding="utf-8"))
    return {k: (float(v[0]), float(v[1])) for k, v in raw.items()}


@functools.lru_cache(maxsize=8)
def _mode_mult_series(mode: str) -> pd.Series:
    df = load_crime()
    return df["crime_l"].map(lambda c: _mode_mult(mode, c)).astype(float)


def nearest_area(lat: float, lng: float, max_km: float = 4.0):
    best, best_d = None, 1e9
    for name, (alat, alng) in load_centroids().items():
        d = geo.haversine_km(lat, lng, alat, alng)
        if d < best_d:
            best, best_d = name, d
    return (best, best_d) if best is not None and best_d <= max_km else (None, None)


def areas_along(points: list[tuple[float, float]]) -> list[str]:
    seen: list[str] = []
    for lat, lng in points:
        area, _ = nearest_area(lat, lng)
        if area and area not in seen:
            seen.append(area)
    return seen


def area_risk(mode: str, hours: frozenset[int]):
    df = load_crime()
    in_window = df["Hour_24"].isin(hours).map({True: 1.0, False: 0.25})
    weight = df["severity"] * _mode_mult_series(mode) * in_window
    totals = weight.groupby(df["Area"]).sum()
    pct = totals.rank(pct=True) * 100  # 0-100 percentile across all areas
    return pct, totals


def route_crime_risk(route: dict) -> dict:
    dep = datetime.fromisoformat(route["departure_iso"])
    arr = datetime.fromisoformat(route["arrival_iso"])
    hours = frozenset(time_utils.hour_window(dep, arr))
    pct, _ = area_risk(route["mode"], hours)

    matched: list[float] = []
    counts: Counter = Counter()
    total = len(route["sample"])
    for lat, lng in route["sample"]:
        area, _ = nearest_area(lat, lng)
        if area is None or area not in pct.index:
            continue
        matched.append(float(pct[area]))
        counts[area] += 1

    if not matched:
        return {
            "route_id": route["route_id"],
            "crime_risk": None,
            "note": "No crime areas matched this route. Run scripts/build_area_centroids.py or check area names.",
        }

    df = load_crime()
    sub = df[df["Area"].isin(list(counts)) & df["Hour_24"].isin(hours)]
    return {
        "route_id": route["route_id"],
        "crime_risk": round(sum(matched) / len(matched), 1),
        "coverage": round(len(matched) / max(total, 1), 2),
        "hours_considered": sorted(hours),
        "top_areas": [
            {"area": a, "share_of_route": round(c / total, 2), "area_risk_pct": round(float(pct[a]))}
            for a, c in counts.most_common(5)
        ],
        "top_crime_types_in_window": sub["Crime_Type"].value_counts().head(3).to_dict(),
    }