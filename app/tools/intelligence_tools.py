from datetime import datetime
from typing import Literal

from langchain.tools import tool

from app.services import crime, search, weather
from app.services.routing import ROUTE_STORE


@tool
def get_crime_risk(route_ids: list[str]) -> dict:
    """Historical crime risk for each route, from the local Karachi crime dataset, for the hours of travel
    and the transport mode. Pass ALL route_ids from get_routes in one call."""
    results = []
    for rid in route_ids:
        route = ROUTE_STORE.get(rid)
        if not route:
            results.append({"route_id": rid, "error": "unknown route_id"})
            continue
        try:
            res = crime.route_crime_risk(route)
        except (FileNotFoundError, ValueError) as exc:
            return {"error": str(exc)}
        route["crime"] = res
        results.append(res)
    return {
        "results": results,
        "scale": "crime_risk is 0-100, higher = more dangerous (percentile of weighted historical crime in areas along the route).",
        "data_note": "Historical, area-level records. Not live and not street-level.",
    }


@tool
def get_weather(route_id: str) -> dict:
    """Weather (forecast if within 5 days, else current) near the route midpoint at expected arrival time.
    Call once with any route_id. Returns weather_risk 0-100 (higher = worse)."""
    route = ROUTE_STORE.get(route_id)
    if not route:
        return {"error": "unknown route_id"}
    pts = route["sample"]
    lat, lng = pts[len(pts) // 2]
    return weather.fetch(lat, lng, datetime.fromisoformat(route["arrival_iso"]), route["mode"])


@tool
def web_search(
    query: str,
    recency: Literal["day", "week", "month"] = "week",
    topic: Literal["news", "general"] = "news",
) -> dict:
    """Search the web for evidence (Tavily). Use for current incidents, news from the last 1-2 days,
    this week's events, and announced protests, rallies, road closures or public events.
    recency: 'day' = last 24h, 'week' = last 7 days. Keep queries short and specific to Karachi areas.
    Returns titles, urls, published dates and snippets. Never treat an empty result as proof of safety."""
    return search.search(query, recency, topic)