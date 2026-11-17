import math
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from app.config import settings


def tz() -> ZoneInfo:
    return ZoneInfo(settings.timezone)


def now_local() -> datetime:
    return datetime.now(tz())


def parse_time(value: str | None) -> datetime:
    """ISO string -> aware local datetime. None / 'now' / bad input -> now."""
    if not value or value.strip().lower() in {"now", "asap", "today"}:
        return now_local()
    try:
        dt = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        return now_local()
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=tz())
    return dt.astimezone(tz())


def to_utc_rfc3339(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def safe_departure(dt: datetime) -> datetime:
    """Driving requests need a future departure time."""
    minimum = now_local() + timedelta(seconds=60)
    return dt if dt > minimum else minimum


def hour_window(dep: datetime, arr: datetime, pad: int = 1) -> set[int]:
    span = max(1, math.ceil((arr - dep).total_seconds() / 3600))
    return {(dep.hour + i) % 24 for i in range(-pad, span + pad + 1)}