"""UTC-only time utilities.

The platform stores and reasons about time in UTC exclusively. Naive datetimes are a
bug (they silently corrupt session/seasonal research and the audit chain), so every
function here rejects them rather than guessing a zone. Broker-server-time handling
is layered on top in later stages; the invariant *everything is UTC internally* starts here.
"""

from __future__ import annotations

from datetime import UTC, datetime

from libs.core.errors import TimezoneError

__all__ = [  # noqa: RUF022  # UTC first, then helpers
    "UTC",
    "utcnow",
    "is_utc",
    "ensure_utc",
    "to_utc",
    "to_iso8601",
    "from_iso8601",
    "to_epoch_ms",
    "from_epoch_ms",
]


def utcnow() -> datetime:
    """Return the current time as a timezone-aware UTC datetime."""
    return datetime.now(UTC)


def is_utc(dt: datetime) -> bool:
    """Return ``True`` iff ``dt`` is timezone-aware and its offset is exactly UTC."""
    if dt.tzinfo is None:
        return False
    offset = dt.utcoffset()
    return offset is not None and offset.total_seconds() == 0.0


def ensure_utc(dt: datetime) -> datetime:
    """Validate that ``dt`` is timezone-aware UTC and return it unchanged.

    Raises:
        TimezoneError: if ``dt`` is naive or carries a non-UTC offset.
    """
    if dt.tzinfo is None:
        raise TimezoneError("naive datetime is forbidden; datetimes must be UTC-aware")
    if not is_utc(dt):
        raise TimezoneError(f"datetime must be UTC, got offset {dt.utcoffset()}")
    return dt


def to_utc(dt: datetime, *, assume_utc: bool = False) -> datetime:
    """Convert ``dt`` to UTC.

    A timezone-aware datetime is converted by its offset. A naive datetime is rejected
    unless ``assume_utc`` is explicitly set, in which case it is *tagged* (not shifted) UTC.

    Raises:
        TimezoneError: if ``dt`` is naive and ``assume_utc`` is ``False``.
    """
    if dt.tzinfo is None:
        if not assume_utc:
            raise TimezoneError(
                "refusing to convert a naive datetime; pass assume_utc=True only if "
                "you are certain the value is already UTC"
            )
        return dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


def to_iso8601(dt: datetime) -> str:
    """Serialize a UTC datetime to ISO-8601 with a trailing ``Z``.

    Raises:
        TimezoneError: if ``dt`` is not UTC-aware.
    """
    ensure_utc(dt)
    return dt.isoformat().replace("+00:00", "Z")


def from_iso8601(value: str) -> datetime:
    """Parse an ISO-8601 string into a UTC datetime.

    Accepts a trailing ``Z`` or an explicit offset; the result is always UTC.

    Raises:
        TimezoneError: if the parsed value is naive (no zone information).
    """
    normalized = value.strip()
    if normalized.endswith(("Z", "z")):
        normalized = normalized[:-1] + "+00:00"
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        raise TimezoneError(f"ISO-8601 value lacks timezone information: {value!r}")
    return parsed.astimezone(UTC)


def to_epoch_ms(dt: datetime) -> int:
    """Return milliseconds since the Unix epoch for a UTC datetime."""
    ensure_utc(dt)
    return int(dt.timestamp() * 1000)


def from_epoch_ms(epoch_ms: int) -> datetime:
    """Return a UTC datetime from milliseconds since the Unix epoch."""
    return datetime.fromtimestamp(epoch_ms / 1000, tz=UTC)
