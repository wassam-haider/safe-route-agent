from app.schemas import RouteOption, RouteRecommendation
from app.services.routing import ROUTE_STORE
from app.utils import geo


def finalize(rec: RouteRecommendation) -> RouteRecommendation:
    """Overwrite numeric fields with the deterministic values computed in code."""
    route = ROUTE_STORE.get(rec.route_id)
    if not route or not route.get("scores"):
        rec.warnings.append("Scores could not be verified against the scoring engine.")
        return rec

    s = route["scores"]
    rec.route_score = s["route_score"]
    rec.safety_score = s["safety_score"]
    rec.traffic_score = s["traffic_score"]
    rec.crime_score = s["crime_score"]
    rec.incident_score = s["incident_score"]
    rec.confidence = s["data_confidence"]
    rec.travel_time_minutes = route["duration_min"]
    rec.distance_km = route["distance_km"]

    others = [r for r in ROUTE_STORE.values() if r["batch"] == route["batch"] and r["route_id"] != rec.route_id and r.get("scores")]
    others.sort(key=lambda r: r["scores"]["rank"])
    rec.alternatives = [
        RouteOption(
            route_id=r["route_id"],
            summary=f'{r["label"]}: {r["summary"]}',
            travel_time_minutes=r["duration_min"],
            distance_km=r["distance_km"],
            route_score=r["scores"]["route_score"],
        )
        for r in others
    ]
    return rec


def render_text(rec: RouteRecommendation) -> str:
    lines = [
        f"Recommended: {rec.recommended_route} - {rec.travel_time_minutes} min, {rec.distance_km} km",
        f"Overall {rec.route_score}/100 | Safety {rec.safety_score}/100 | Confidence {rec.confidence:.0%}",
        f"Protest/event risk: {rec.protest_risk}",
        f"Weather: {rec.weather_risk}",
        "",
        "Why:",
        *[f"- {r}" for r in rec.reasons],
    ]
    if rec.warnings:
        lines += ["", "Caveats:", *[f"- {w}" for w in rec.warnings]]
    return "\n".join(lines)


def map_payload(rec: RouteRecommendation) -> dict | None:
    route = ROUTE_STORE.get(rec.route_id)
    if not route:
        return None
    batch = [r for r in ROUTE_STORE.values() if r["batch"] == route["batch"]]
    return {
        "origin": route["origin"],
        "destination": route["destination"],
        "routes": [
            {
                "route_id": r["route_id"],
                "label": r["label"],
                "is_best": r["route_id"] == rec.route_id,
                "points": [[lat, lng] for lat, lng in geo.decode_polyline(r["polyline"])],
            }
            for r in batch
        ],
    }