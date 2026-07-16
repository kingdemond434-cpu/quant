"""Built-in, causal feature definitions registered into the default registry."""

from __future__ import annotations

import numpy as np
import pandas as pd

from libs.data.calendar import session_of
from libs.features.definition import FeatureDefinition
from libs.features.registry import FeatureRegistry

_SESSION_CODE = {"asia": 0.0, "london": 1.0, "overlap": 2.0, "newyork": 3.0, "off": 4.0}


def _ret_1(df: pd.DataFrame) -> pd.Series:
    return df["close"].pct_change(fill_method=None)


def _log_ret_1(df: pd.DataFrame) -> pd.Series:
    return np.log(df["close"] / df["close"].shift(1))


def _momentum_10(df: pd.DataFrame) -> pd.Series:
    return df["close"] / df["close"].shift(10) - 1.0


def _sma_10(df: pd.DataFrame) -> pd.Series:
    return df["close"].rolling(10, min_periods=1).mean()


def _rolling_vol_20(df: pd.DataFrame) -> pd.Series:
    returns = np.log(df["close"] / df["close"].shift(1))
    return returns.rolling(20, min_periods=2).std()


def _atr_14(df: pd.DataFrame) -> pd.Series:
    prev_close = df["close"].shift(1)
    true_range = pd.concat(
        [df["high"] - df["low"], (df["high"] - prev_close).abs(), (df["low"] - prev_close).abs()],
        axis=1,
    ).max(axis=1)
    return true_range.rolling(14, min_periods=1).mean()


def _zscore_20(df: pd.DataFrame) -> pd.Series:
    mean = df["close"].rolling(20, min_periods=5).mean()
    std = df["close"].rolling(20, min_periods=5).std()
    return (df["close"] - mean) / std


def _hour_of_day(df: pd.DataFrame) -> pd.Series:
    return df["timestamp"].dt.hour.astype("float64")


def _session_code(df: pd.DataFrame) -> pd.Series:
    return df["timestamp"].apply(lambda ts: _SESSION_CODE[session_of(ts)]).astype("float64")


BUILTIN_FEATURES: tuple[FeatureDefinition, ...] = (
    FeatureDefinition("ret_1", 1, _ret_1, inputs=("close",), category="price", min_periods=1),
    FeatureDefinition("log_ret_1", 1, _log_ret_1, inputs=("close",), category="price"),
    FeatureDefinition(
        "momentum_10", 1, _momentum_10, inputs=("close",), category="price", min_periods=10
    ),
    FeatureDefinition("sma_10", 1, _sma_10, inputs=("close",), category="price", min_periods=1),
    FeatureDefinition(
        "rolling_vol_20", 1, _rolling_vol_20, inputs=("close",), category="volatility",
        min_periods=20,
    ),
    FeatureDefinition(
        "atr_14", 1, _atr_14, inputs=("high", "low", "close"), category="volatility",
        min_periods=14,
    ),
    FeatureDefinition(
        "zscore_20", 1, _zscore_20, inputs=("close",), category="price", min_periods=20
    ),
    FeatureDefinition(
        "hour_of_day", 1, _hour_of_day, inputs=("timestamp",), category="session"
    ),
    FeatureDefinition(
        "session_code", 1, _session_code, inputs=("timestamp",), category="session"
    ),
)


def register_builtin_features(registry: FeatureRegistry) -> None:
    """Register all built-in features into ``registry`` (idempotent)."""
    for definition in BUILTIN_FEATURES:
        registry.register(definition, overwrite=True)
