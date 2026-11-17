import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


@dataclass(frozen=True)
class Settings:
    openrouter_api_key: str = os.getenv("OPENROUTER_API_KEY", "")
    openrouter_model: str = os.getenv("OPENROUTER_MODEL", "openai/gpt-4o-mini")
    tavily_api_key: str = os.getenv("TAVILY_API_KEY", "")
    ors_api_key: str = os.getenv("ORS_API_KEY", "")
    openweather_api_key: str = os.getenv("OPENWEATHER_API_KEY", "")
    osm_user_agent: str = os.getenv("OSM_USER_AGENT", "")
    crime_csv_path: Path = BASE_DIR / os.getenv("CRIME_CSV_PATH", "data/karachi_crime.csv")
    centroids_path: Path = BASE_DIR / "data" / "area_centroids.json"
    timezone: str = os.getenv("APP_TIMEZONE", "Asia/Karachi")
    max_routes: int = 10


settings = Settings()


def validate_settings() -> None:
    required = {
        "OPENROUTER_API_KEY": settings.openrouter_api_key,
        "TAVILY_API_KEY": settings.tavily_api_key,
        "ORS_API_KEY": settings.ors_api_key,
        "OPENWEATHER_API_KEY": settings.openweather_api_key,
        "OSM_USER_AGENT": settings.osm_user_agent,
    }
    missing = [k for k, v in required.items() if not v]
    if missing:
        raise RuntimeError(f"Missing environment variables in .env: {', '.join(missing)}")