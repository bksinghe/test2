"""Clock helpers: aware datetimes and human duration parsing."""

from __future__ import annotations

import re
from datetime import UTC, datetime


def utcnow() -> datetime:
    return datetime.now(UTC)


def as_utc(value: datetime | None) -> datetime | None:
    """Attach UTC to naive datetimes coming from legacy documents."""
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value


def is_future(value: datetime | None) -> bool:
    moment = as_utc(value)
    return bool(moment and moment > utcnow())



DURATION_RE = re.compile(
    r"^(?P<amount>\d+)\s*"
    r"(?P<unit>s|sec|second|seconds|min|minute|minutes|hour|hours|day|days|month|months|year|years)$",
    re.IGNORECASE,
)

UNIT_SECONDS = {
    "s": 1, "sec": 1, "second": 1, "seconds": 1,
    "min": 60, "minute": 60, "minutes": 60,
    "hour": 3600, "hours": 3600,
    "day": 86400, "days": 86400,
    "month": 86400 * 30, "months": 86400 * 30,
    "year": 86400 * 365, "years": 86400 * 365,
}


def parse_duration(value: str) -> int | None:
    """``1day`` / ``10 days`` / ``2hours`` -> seconds, ``None`` when invalid."""
    match = DURATION_RE.match((value or "").strip())
    if not match:
        return None
    seconds = int(match["amount"]) * UNIT_SECONDS[match["unit"].lower()]
    return seconds if seconds > 0 else None


__all__ = ["UNIT_SECONDS", "as_utc", "is_future", "parse_duration", "utcnow"]
