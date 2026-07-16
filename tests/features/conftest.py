"""Fixtures and leaky-feature helpers for the feature test suite."""

from __future__ import annotations

import numpy as np
import pandas as pd

from libs.features.definition import FeatureDefinition


def make_bars(n: int = 60, *, seed: int = 0) -> pd.DataFrame:
    """Synthetic daily OHLC bars (UTC), valid and strictly positive."""
    idx = pd.date_range("2026-01-05", periods=n, freq="1D", tz="UTC")
    rng = np.random.default_rng(seed)
    close = 200.0 + np.cumsum(rng.normal(0, 0.5, size=n))
    open_ = np.concatenate([[200.0], close[:-1]])
    high = np.maximum(open_, close) + np.abs(rng.normal(0, 0.3, size=n))
    low = np.minimum(open_, close) - np.abs(rng.normal(0, 0.3, size=n))
    volume = rng.integers(100, 1000, size=n).astype("float64")
    return pd.DataFrame(
        {"timestamp": idx, "open": open_, "high": high, "low": low, "close": close,
         "volume": volume}
    )


# --- causal (good) feature -------------------------------------------------


def causal_feature() -> FeatureDefinition:
    return FeatureDefinition(
        "sma_3", 1, lambda df: df["close"].rolling(3, min_periods=1).mean(),
        inputs=("close",), min_periods=1,
    )


# --- leaky (bad) features --------------------------------------------------


def _future_return(df: pd.DataFrame) -> pd.Series:
    return df["close"].shift(-1) / df["close"] - 1.0  # reads the next bar


def future_return_feature() -> FeatureDefinition:
    return FeatureDefinition("future_ret", 1, _future_return, inputs=("close",), min_periods=1)


def _full_sample_zscore(df: pd.DataFrame) -> pd.Series:
    return (df["close"] - df["close"].mean()) / df["close"].std()  # full-sample stats


def full_sample_zscore_feature() -> FeatureDefinition:
    return FeatureDefinition("full_z", 1, _full_sample_zscore, inputs=("close",), min_periods=5)
