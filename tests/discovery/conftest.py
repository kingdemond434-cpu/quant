"""Fixtures and synthetic-data builders for the discovery test suite."""

from __future__ import annotations

import numpy as np
import pandas as pd

from libs.data.schema import validate_bars


def make_returns(*, n: int = 300, mu: float = 0.0, sd: float = 0.01, seed: int = 0) -> np.ndarray:
    return np.random.default_rng(seed).normal(mu, sd, size=n)


def make_returns_matrix(*, n: int = 300, k: int = 4, rho: float = 0.0, seed: int = 0) -> np.ndarray:
    rng = np.random.default_rng(seed)
    common = rng.normal(0, 1, size=(n, 1))
    idio = rng.normal(0, 1, size=(n, k))
    w = np.sqrt(max(0.0, min(1.0, rho)))
    return (w * common + np.sqrt(1.0 - w**2) * idio) * 0.01


def make_bars(
    *, n: int = 260, seed: int = 0, drift: float = 0.0, vol: float = 0.01,
    start: str = "2026-01-05",
) -> pd.DataFrame:
    """A valid daily OHLC frame with configurable drift (drift > 0 = a trending series)."""
    idx = pd.date_range(start, periods=n, freq="1D", tz="UTC")
    rng = np.random.default_rng(seed)
    log_ret = rng.normal(drift, vol, size=n)
    close = 100.0 * np.exp(np.cumsum(log_ret))
    open_ = np.concatenate([[close[0]], close[:-1]])
    high = np.maximum(open_, close) * (1.0 + np.abs(rng.normal(0, 0.002, size=n)))
    low = np.minimum(open_, close) * (1.0 - np.abs(rng.normal(0, 0.002, size=n)))
    volume = rng.integers(100, 1000, size=n).astype("float64")
    df = pd.DataFrame(
        {"timestamp": idx, "open": open_, "high": high, "low": low, "close": close,
         "volume": volume}
    )
    return validate_bars(df, require_sorted=True)
