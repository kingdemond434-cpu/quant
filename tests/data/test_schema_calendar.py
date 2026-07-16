"""Tests for the bar schema and trading calendar."""

from __future__ import annotations

import pandas as pd
import pytest

from libs.data.calendar import expected_index, is_open, session_of
from libs.data.errors import DataError
from libs.data.instruments import AssetClass
from libs.data.schema import empty_bars, validate_bars
from libs.data.timeframe import Timeframe


def test_empty_bars_is_valid() -> None:
    validate_bars(empty_bars())


def test_validate_rejects_missing_columns() -> None:
    with pytest.raises(DataError):
        validate_bars(pd.DataFrame({"timestamp": []}))


def test_validate_rejects_naive_timestamp() -> None:
    df = pd.DataFrame(
        {
            "timestamp": pd.to_datetime(["2026-01-05 00:00"]),  # naive
            "open": [1.0], "high": [1.0], "low": [1.0], "close": [1.0], "volume": [1.0],
        }
    )
    with pytest.raises(DataError):
        validate_bars(df)


def test_validate_rejects_ohlc_nan() -> None:
    df = pd.DataFrame(
        {
            "timestamp": pd.to_datetime(["2026-01-05 00:00"], utc=True),
            "open": [float("nan")], "high": [1.0], "low": [1.0], "close": [1.0], "volume": [1.0],
        }
    )
    with pytest.raises(DataError):
        validate_bars(df)


def test_is_open_weekend_rules() -> None:
    saturday = pd.Timestamp("2026-01-10 12:00", tz="UTC")  # Saturday
    monday = pd.Timestamp("2026-01-05 12:00", tz="UTC")
    assert is_open(monday, AssetClass.FX) is True
    assert is_open(saturday, AssetClass.FX) is False
    assert is_open(saturday, AssetClass.CRYPTO) is True


def test_expected_index_excludes_weekends_for_fx() -> None:
    start = pd.Timestamp("2026-01-09 00:00", tz="UTC")  # Friday
    end = pd.Timestamp("2026-01-12 00:00", tz="UTC")  # Monday
    fx = expected_index(start, end, Timeframe.D1, AssetClass.FX)
    crypto = expected_index(start, end, Timeframe.D1, AssetClass.CRYPTO)
    assert all(ts.weekday() < 5 for ts in fx)
    assert len(crypto) == len(fx) + 2  # Saturday + Sunday included for crypto


@pytest.mark.parametrize(
    ("hour", "session"),
    [(2, "asia"), (8, "london"), (13, "overlap"), (18, "newyork"), (22, "off")],
)
def test_session_of(hour: int, session: str) -> None:
    assert session_of(pd.Timestamp(f"2026-01-05 {hour:02d}:00", tz="UTC")) == session
