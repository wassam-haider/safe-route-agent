import logging
from typing import Any

from langchain.tools import tool

from app.services import scoring
from app.services.routing import ROUTE_STORE

logger = logging.getLogger("saferoute")


def _num(value: Any, default: float | None = None) -> float | None:
    try:
        if value is None or value == "":
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _clamp(x: float) -> float:
    return max(0.0, min(100.0, x))


def _clean_evidence(items: Any) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for item in items or []:
        d = item if isinstance(item, dict) else getattr(item, "model_dump", lambda: {})()
        rid = d.get("route_id")
        if not rid:
            continue
        out[str(rid)] = {
            "incident_risk": _clamp(_num(d.get("incident_risk"), 50.0)),
            "event_risk": _clamp(_num(d.get("event_risk"), 50.0)),
            "notes": str(d.get("notes") or ""),
        }
    return out


@tool
def score_routes(
    route_ids: list[str] | str,
    priority: str = "balanced",
    evidence: list[dict[str, Any]] | None = None,
    weather_risk: float | str | None = None,
    searches_with_results: float | str = 0,
) -> dict:
    """Deterministic weighted scoring and ranking of routes. Call it EXACTLY ONCE, with ALL route_ids.
    route_ids: the route_id values from get_routes, copied exactly.
    priority: balanced, fastest or safest.
    evidence: one object per route, like {"route_id": "r_ab12cd34", "incident_risk": 30, "event_risk": 20, "notes": "short reason"}.
      Both risks are numbers from 0 to 100, based ONLY on web_search results.
    weather_risk: the number from get_weather.
    searches_with_results: how many web_search calls returned results.
    If this returns an error or says routes are already scored, do NOT call it again."""
    try:
        ids = [route_ids] if isinstance(route_ids, str) else list(route_ids)
        routes = [ROUTE_STORE[r] for r in ids if r in ROUTE_STORE]
        unknown = [r for r in ids if r not in ROUTE_STORE]
        if not routes:
            return {"error": f"Unknown route_ids {ids}. Use the route_id values from get_routes exactly as given."}

        prio = str(priority or "balanced").strip().lower()
        if prio not in ("balanced", "fastest", "safest"):
            prio = "balanced"

        if all(r.get("scores") for r in routes):
            ranked = sorted(routes, key=lambda r: r["scores"]["rank"])
            note = "Routes were already scored. Do NOT call score_routes again. Return the RouteRecommendation now."
        else:
            if isinstance(weather_risk, dict):
                weather_risk = weather_risk.get("weather_risk")
            wr = _num(weather_risk, None)
            hits = int(_num(searches_with_results, 0) or 0)
            ranked = scoring.score_routes(routes, prio, _clean_evidence(evidence), wr, hits)
            note = "Scoring complete. Do NOT call score_routes again. Return the RouteRecommendation for best_route_id now."

        return {
            "priority": prio,
            "mode": routes[0]["mode"],
            "weights": scoring.weights_for(prio, routes[0]["mode"]),
            "best_route_id": ranked[0]["route_id"],
            "ranking": [
                {
                    "route_id": r["route_id"],
                    "label": r["label"],
                    "summary": r["summary"],
                    "distance_km": r["distance_km"],
                    "duration_min": r["duration_min"],
                    "traffic_delay_min": r["traffic_delay_min"],
                    **{k: v for k, v in r["scores"].items() if k != "weights"},
                }
                for r in ranked
            ],
            "unknown_route_ids": unknown,
            "note": note,
        }
    except Exception as exc:
        logger.exception("score_routes failed")
        return {
            "error": f"score_routes failed ({type(exc).__name__}: {exc}). Do NOT call it again; "
                     "tell the user scoring could not be completed."
        }