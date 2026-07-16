"""Tests for the UTC-only time utilities."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from libs.core.errors import TimezoneError
from libs.core.time import (
    UTC,
    ensure_utc,
    from_epoch_ms,
    from_iso8601,
    is_utc,
    to_epoch_ms,
    to_iso8601,
    to_utc,
    utcnow,
)

PLUS_TWO = timezone(timedelta(hours=2))


def test_utcnow_is_utc_aware() -> None:
    now = utcnow()
    assert now.tzinfo is not None
    assert is_utc(now)


def test_is_utc() -> None:
    assert is_utc(datetime(2026, 1, 1, tzinfo=UTC))
    assert not is_utc(datetime(2026, 1, 1))  # naive
    assert not is_utc(datetime(2026, 1, 1, tzinfo=PLUS_TWO))


def test_ensure_utc_rejects_naive() -> None:
    with pytest.raises(TimezoneError):
        ensure_utc(datetime(2026, 1, 1))


def test_ensure_utc_rejects_non_utc_offset() -> None:
    with pytest.raises(TimezoneError):
        ensure_utc(datetime(2026, 1, 1, tzinfo=PLUS_TWO))


def test_ensure_utc_returns_value() -> None:
    dt = datetime(2026, 1, 1, tzinfo=UTC)
    assert ensure_utc(dt) is dt


def test_to_utc_converts_aware() -> None:
    dt = datetime(2026, 1, 1, 12, 0, tzinfo=PLUS_TWO)
    converted = to_utc(dt)
    assert is_utc(converted)
    assert converted.hour == 10


def test_to_utc_rejects_naive_by_default() -> None:
    with pytest.raises(TimezoneError):
        to_utc(datetime(2026, 1, 1))


def test_to_utc_assume_utc_tags_without_shifting() -> None:
    dt = datetime(2026, 1, 1, 12, 0)
    tagged = to_utc(dt, assume_utc=True)
    assert is_utc(tagged)
    assert tagged.hour == 12


def test_to_iso8601_uses_z_suffix() -> None:
    dt = datetime(2026, 6, 15, 8, 30, 0, tzinfo=UTC)
    assert to_iso8601(dt) == "2026-06-15T08:30:00Z"


def test_to_iso8601_rejects_naive() -> None:
    with pytest.raises(TimezoneError):
        to_iso8601(datetime(2026, 1, 1))


def test_from_iso8601_accepts_z() -> None:
    parsed = from_iso8601("2026-06-15T08:30:00Z")
    assert parsed == datetime(2026, 6, 15, 8, 30, tzinfo=UTC)


def test_from_iso8601_accepts_offset_and_normalizes() -> None:
    parsed = from_iso8601("2026-06-15T10:30:00+02:00")
    assert is_utc(parsed)
    assert parsed.hour == 8


def test_from_iso8601_rejects_naive() -> None:
    with pytest.raises(TimezoneError):
        from_iso8601("2026-06-15T08:30:00")


def test_iso_roundtrip() -> None:
    dt = utcnow().replace(microsecond=0)
    assert from_iso8601(to_iso8601(dt)) == dt


def test_epoch_ms_roundtrip() -> None:
    dt = datetime(2026, 6, 15, 8, 30, 0, tzinfo=UTC)
    assert from_epoch_ms(to_epoch_ms(dt)) == dt


def test_to_epoch_ms_rejects_naive() -> None:
    with pytest.raises(TimezoneError):
        to_epoch_ms(datetime(2026, 1, 1))
