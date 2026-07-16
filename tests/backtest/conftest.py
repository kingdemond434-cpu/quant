"""Fixtures and helpers for the backtest test suite."""

from __future__ import annotations

import numpy as np
import pandas as pd


def make_bars(n: int = 60, *, seed: int = 0, start: str = "2026-01-05") -> pd.DataFrame:
    """Build a synthetic, valid daily OHLC bar frame (UTC)."""
    idx = pd.date_range(start, periods=n, freq="1D", tz="UTC")
    rng = np.random.default_rng(seed)
    close = 200.0 + np.cumsum(rng.normal(0, 0.5, size=n))
    open_ = np.concatenate([[200.0], close[:-1]])
    high = np.maximum(open_, close) + np.abs(rng.normal(0, 0.3, size=n))
    low = np.minimum(open_, close) - np.abs(rng.normal(0, 0.3, size=n))
    volume = rng.integers(100, 1000, size=n).astype("float64")
    return pd.DataFrame(
        {
            "timestamp": idx,
            "open": open_,
            "high": high,
            "low": low,
            "close": close,
            "volume": volume,
        }
    )


def explicit_bars() -> pd.DataFrame:
    """A tiny, hand-checkable 4-bar frame."""
    return pd.DataFrame(
        {
            "timestamp": pd.date_range("2026-01-05", periods=4, freq="1D", tz="UTC"),
            "open": [100.0, 100.0, 105.0, 102.0],
            "high": [101.0, 106.0, 106.0, 103.0],
            "low": [99.0, 99.0, 100.0, 100.0],
            "close": [100.0, 105.0, 102.0, 103.0],
            "volume": [500.0, 500.0, 500.0, 500.0],
        }
    )
