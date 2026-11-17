from langchain.tools import tool

from app.services import geocoding


@tool
def geocode_location(query: str) -> dict:
    """Resolve a place name or landmark in Karachi (e.g. 'MAJU Block C', 'Hyderi Bhayani Garden')
    to a formatted address and lat/lng. Use it when a place is vague or to confirm it.
    Returns an error if nothing is found."""
    res = geocoding.geocode(query)
    if not res:
        return {"error": f"No result for {query!r}. Ask the user for a more specific place."}
    return res