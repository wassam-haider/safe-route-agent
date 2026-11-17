from app.tools.intelligence_tools import get_crime_risk, get_weather, web_search
from app.tools.location_tools import geocode_location
from app.tools.route_tools import get_routes
from app.tools.scoring_tools import score_routes

ALL_TOOLS = [geocode_location, get_routes, get_crime_risk, get_weather, web_search, score_routes]