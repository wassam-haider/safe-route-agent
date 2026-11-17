WEIGHTS = {
    "balanced": {"distance": .15, "time": .20, "traffic": .15, "crime": .20, "incidents": .15, "events": .10, "weather": .05},
    "fastest": {"distance": .20, "time": .50, "traffic": .00, "crime": .12, "incidents": .09, "events": .06, "weather": .03},
    "safest": {"distance": .10, "time": .20, "traffic": .10, "crime": .24, "incidents": .18, "events": .12, "weather": .06},
}
MODE_MULT = {
    "car": {"traffic": 1.3, "incidents": 1.2},
    "motorcycle": {"traffic": 1.3, "crime": 1.1, "weather": 1.3},
    "bicycle": {"traffic": 1.2, "crime": 1.1, "weather": 1.5, "distance": 1.2},
    "walking": {"crime": 1.3, "distance": 1.3, "weather": 1.5},
    "public_transport": {"time": 1.2},
}
SAFETY_KEYS = ("crime", "incidents", "events", "weather")


def _clamp(x: float) -> float:
    return max(0.0, min(100.0, float(x)))


def weights_for(priority: str, mode: str) -> dict[str, float]:
    w = dict(WEIGHTS.get(priority, WEIGHTS["balanced"]))
    for key, mult in MODE_MULT.get(mode, {}).items():
        w[key] *= mult
    total = sum(w.values())
    return {k: v / total for k, v in w.items()}


def score_routes(routes: list[dict], priority: str, evidence: dict[str, dict],
                 weather_risk: float | None, searches_with_results: int) -> list[dict]:
    mode = routes[0]["mode"]
    w = weights_for(priority, mode)
    min_time = min(r["duration_min"] for r in routes)
    min_dist = min(r["distance_km"] for r in routes)
    weather_missing = weather_risk is None
    wr = _clamp(weather_risk if weather_risk is not None else 0)

    ranked = []
    for r in routes:
        ev = evidence.get(r["route_id"])
        crime_risk = (r.get("crime") or {}).get("crime_risk")
        crime_missing = crime_risk is None
        cr = _clamp(crime_risk if crime_risk is not None else 50)
        inc = _clamp(ev["incident_risk"]) if ev else 50.0
        evt = _clamp(ev["event_risk"]) if ev else 50.0

        comps = {
            "distance": 100 * min_dist / max(r["distance_km"], 0.01),
            "time": 100 * min_time / max(r["duration_min"], 1),
            "traffic": max(0.0, 100 - r["delay_ratio"] * 200),
            "crime": 100 - cr,
            "incidents": 100 - inc,
            "events": 100 - evt,
            "weather": 100 - wr,
        }
        route_score = sum(w[k] * comps[k] for k in w)
        sw = sum(w[k] for k in SAFETY_KEYS)
        safety = sum(w[k] * comps[k] for k in SAFETY_KEYS) / sw if sw else 50.0

        conf = 1.0
        if crime_missing:
            conf -= 0.25
        if not ev:
            conf -= 0.15
        if searches_with_results == 0:
            conf -= 0.15
        if weather_missing:
            conf -= 0.05

        scores = {
            "route_score": round(route_score, 1),
            "safety_score": round(safety, 1),
            "traffic_score": round(comps["traffic"], 1),
            "crime_score": round(comps["crime"], 1),
            "incident_score": round(comps["incidents"], 1),
            "event_score": round(comps["events"], 1),
            "weather_score": round(comps["weather"], 1),
            "time_score": round(comps["time"], 1),
            "distance_score": round(comps["distance"], 1),
            "data_confidence": round(max(0.2, conf), 2),
            "evidence_notes": (ev or {}).get("notes", ""),
        }
        r["scores"] = scores
        ranked.append(r)

    ranked.sort(key=lambda x: x["scores"]["route_score"], reverse=True)
    for i, r in enumerate(ranked, start=1):
        r["scores"]["rank"] = i
    return ranked