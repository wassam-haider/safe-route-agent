from langchain.tools import tool

from app.schemas import TransportMode
from app.services import routing


@tool
def get_routes(
    origin: str,
    destination: str,
    mode: TransportMode,
    departure_time: str | None = None,
    num_routes: int = 3,
) -> dict:
    """Fetch candidate routes (OpenStreetMap data) with distance, duration, arrival time, main roads
    ('summary') and the crime-dataset areas each route passes.
    There is NO live traffic: traffic_delay_min is only a rough peak-hour estimate, the same for every route.
    origin / destination: a place name or a 'lat,lng' string.
    mode: car, motorcycle, bicycle, walking or public_transport (motorcycle and public_transport are approximations).
    departure_time: ISO 8601 local time (Asia/Karachi); omit for 'now'.
    num_routes: 3, 5 or 10 (max 10). Each route gets a route_id used by the other tools.
    Read the 'notes' field and pass relevant limitations on as warnings."""
    try:
        return routing.fetch_routes(origin, destination, mode, departure_time, num_routes)
    except ValueError as exc:
        return {"error": str(exc)}