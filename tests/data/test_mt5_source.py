"""Tests for MT5 ingestion and timezone normalization."""

from __future__ import annotations

from datetime import datetime

import pandas as pd
from tests.data.conftest import FakeBarSource, make_raw_mt5

from libs.data.mt5_source import load_mt5_bars, normalize_timezone
from libs.data.schema import is_utc_series
from libs.data.timeframe import Timeframe


def test_normalize_localizes_naive_as_utc() -> None:
    df = pd.DataFrame({"timestamp": pd.to_datetime(["2026-01-05 10:00"])})
    out = normalize_timezone(df, input_tz="UTC")
    assert is_utc_series(out["timestamp"])
    assert out["timestamp"].iloc[0] == pd.Timestamp("2026-01-05 10:00", tz="UTC")


def test_normalize_converts_offset_zone_to_utc() -> None:
    df = pd.DataFrame({"timestamp": pd.to_datetime(["2026-01-05 10:00"])})
    out = normalize_timezone(df, input_tz="Etc/GMT-2")  # Etc/GMT-2 == UTC+2
    assert out["timestamp"].iloc[0] == pd.Timestamp("2026-01-05 08:00", tz="UTC")


def test_load_mt5_bars_utc_server() -> None:
    times = [datetime(2026, 1, 5, 10), datetime(2026, 1, 5, 11)]
    source = FakeBarSource(make_raw_mt5(times))
    df = load_mt5_bars("XAUUSD", Timeframe.H1, times[0], times[-1], source=source, server_tz="UTC")
    assert is_utc_series(df["timestamp"])
    assert df["timestamp"].iloc[0] == pd.Timestamp("2026-01-05 10:00", tz="UTC")
    assert list(df.columns) == ["timestamp", "open", "high", "low", "close", "volume"]


def test_load_mt5_bars_converts_server_offset() -> None:
    times = [datetime(2026, 1, 5, 10), datetime(2026, 1, 5, 11)]
    source = FakeBarSource(make_raw_mt5(times))
    df = load_mt5_bars(
        "XAUUSD", Timeframe.H1, times[0], times[-1], source=source, server_tz="Etc/GMT-2"
    )
    # 10:00 server (UTC+2) -> 08:00 UTC
    assert df["timestamp"].iloc[0] == pd.Timestamp("2026-01-05 08:00", tz="UTC")


def test_load_mt5_bars_sorted_and_volume_mapped() -> None:
    times = [datetime(2026, 1, 5, 11), datetime(2026, 1, 5, 10)]  # out of order
    source = FakeBarSource(make_raw_mt5(times))
    df = load_mt5_bars("XAUUSD", Timeframe.H1, times[0], times[1], source=source)
    assert df["timestamp"].is_monotonic_increasing
    assert (df["volume"] > 0).all()
