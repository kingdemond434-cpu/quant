"""Fixtures and helpers for the data test suite."""

from __future__ import annotations

from datetime import UTC, datetime

import numpy as np
import pandas as pd
import pytest

from libs.data.calendar import expected_index
from libs.data.instruments import get_spec
from libs.data.lake import ParquetLake
from libs.data.schema import validate_bars
from libs.data.timeframe import Timeframe


def make_bars(
    symbol: str,
    timeframe: Timeframe,
    start: datetime,
    periods: int,
    *,
    seed: int = 0,
) -> pd.DataFrame:
    """Build a complete, valid, calendar-aware bar frame for ``symbol``."""
    spec = get_spec(symbol)
    horizon = start + timeframe.timedelta * (periods * 3 + 20)
    idx = expected_index(
        pd.Timestamp(start, tz="UTC"), pd.Timestamp(horizon, tz="UTC"), timeframe, spec.asset_class
    )[:periods]
    rng = np.random.default_rng(seed)
    close = 100.0 + np.cumsum(rng.normal(0, 0.5, size=len(idx)))
    open_ = np.concatenate([[100.0], close[:-1]])
    high = np.maximum(open_, close) + np.abs(rng.normal(0, 0.1, size=len(idx)))
    low = np.minimum(open_, close) - np.abs(rng.normal(0, 0.1, size=len(idx)))
    volume = rng.integers(100, 1000, size=len(idx)).astype("float64")
    df = pd.DataFrame(
        {
            "timestamp": idx,
            "open": open_,
            "high": high,
            "low": low,
            "close": close,
            "volume": volume,
        }
    )
    return validate_bars(df, require_sorted=True)


def make_raw_mt5(server_times: list[datetime], *, base: float = 2000.0) -> pd.DataFrame:
    """Build a raw MT5-shaped frame (``time`` epoch seconds + OHLC + ``tick_volume``).

    ``server_times`` are naive datetimes representing the broker's wall clock; they are encoded
    as epoch seconds the way MT5 does (wall clock interpreted as if UTC).
    """
    epochs = [int(t.replace(tzinfo=UTC).timestamp()) for t in server_times]
    n = len(server_times)
    return pd.DataFrame(
        {
            "time": epochs,
            "open": [base + i for i in range(n)],
            "high": [base + i + 0.5 for i in range(n)],
            "low": [base + i - 0.5 for i in range(n)],
            "close": [base + i + 0.2 for i in range(n)],
            "tick_volume": [100 + i for i in range(n)],
        }
    )


class FakeBarSource:
    """A :class:`libs.data.BarSource` that returns a fixed raw frame."""

    def __init__(self, raw: pd.DataFrame) -> None:
        self._raw = raw

    def fetch_bars(self, symbol, timeframe, start, end):  # type: ignore[no-untyped-def]
        return self._raw


@pytest.fixture
def lake(tmp_path) -> ParquetLake:  # type: ignore[no-untyped-def]
    return ParquetLake(tmp_path / "lake")


MONDAY = datetime(2026, 1, 5)  # a Monday, for clean weekday series
