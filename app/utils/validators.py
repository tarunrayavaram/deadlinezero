"""
app/utils/validators.py
------------------------
Reusable validation helpers used across schemas and services.
"""

from datetime import datetime, timezone
from typing import Optional


def validate_future_datetime(dt: Optional[datetime]) -> Optional[datetime]:
    """
    Ensure a deadline/due_date is in the future.
    Raises ValueError if the datetime is in the past.
    """
    if dt is None:
        return dt
    now = datetime.now(timezone.utc)
    # Make dt timezone-aware if it is naive
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    if dt <= now:
        raise ValueError("Deadline must be a future date/time.")
    return dt


def sanitise_string(value: str, max_length: int = 500) -> str:
    """Strip whitespace and enforce a maximum character length."""
    value = value.strip()
    if len(value) > max_length:
        raise ValueError(f"Value exceeds maximum length of {max_length} characters.")
    return value


def clamp(value: int, lo: int, hi: int) -> int:
    """Clamp an integer between lo and hi (inclusive)."""
    return max(lo, min(hi, value))
