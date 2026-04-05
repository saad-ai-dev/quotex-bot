"""Datetime utility helpers for the Quotex Alert Intelligence system.

ALERT-ONLY system -- timestamps are used for signal timing, not trade scheduling.
"""

from datetime import datetime, timedelta, timezone


def now_utc() -> datetime:
    """Return the current UTC datetime (timezone-aware)."""
    return datetime.now(timezone.utc)


def parse_timestamp(ts: str) -> datetime:
    """Parse an ISO-8601 timestamp string into a timezone-aware datetime.

    Handles both 'Z' suffix and '+00:00' offset formats.
    If the parsed datetime is naive, it is assumed to be UTC.
    """
    # Handle the 'Z' suffix that fromisoformat doesn't support in Python < 3.11
    cleaned = ts.replace("Z", "+00:00")
    dt = datetime.fromisoformat(cleaned)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def format_timestamp(dt: datetime) -> str:
    """Format a datetime as an ISO-8601 string with 'Z' UTC suffix."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    utc_dt = dt.astimezone(timezone.utc)
    return utc_dt.strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def add_seconds(dt: datetime, seconds: int) -> datetime:
    """Add a number of seconds to a datetime and return the result."""
    return dt + timedelta(seconds=seconds)
