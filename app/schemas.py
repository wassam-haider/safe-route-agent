from typing import Literal

from pydantic import BaseModel, Field

TransportMode = Literal["car", "motorcycle", "bicycle", "walking", "public_transport"]
Priority = Literal["balanced", "fastest", "safest"]


class AskUser(BaseModel):
    """Use this when required trip information is missing (start, destination, or transport mode).
    Ask for everything missing in ONE short message."""

    question: str = Field(description="The question to show to the user.")


class RouteOption(BaseModel):
    route_id: str
    summary: str
    travel_time_minutes: int
    distance_km: float
    route_score: float


class RouteRecommendation(BaseModel):
    """Final recommendation. Use ONLY after score_routes has been called.
    All scores are 0-100 where higher is better / safer."""

    route_id: str = Field(description="route_id of the best route from score_routes.")
    recommended_route: str = Field(description="Short human description, e.g. 'via Shahrah-e-Faisal'.")
    route_score: float = Field(description="Overall weighted score from score_routes.")
    safety_score: float = Field(description="Safety score from score_routes.")
    travel_time_minutes: int
    distance_km: float
    traffic_score: float
    crime_score: float
    incident_score: float
    protest_risk: str = Field(description="low / medium / high plus one short reason based on evidence.")
    weather_risk: str = Field(description="low / medium / high plus one short reason.")
    confidence: float = Field(description="data_confidence from score_routes (0-1).")
    reasons: list[str] = Field(description="3-5 short reasons grounded in tool results.")
    warnings: list[str] = Field(default_factory=list, description="Data limitations or fallbacks the user should know.")
    alternatives: list[RouteOption] = Field(default_factory=list)