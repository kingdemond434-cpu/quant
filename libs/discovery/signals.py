"""Causal signal generators for each research category.

Each generator maps a bar frame to a target-position array in [-1, 1], decided from data up to
and including bar i (the backtest engine executes the target at bar i+1's open, so there is no
look-ahead). These are deliberately simple, economically-motivated templates — the search's job
is to *disprove* them, not to curve-fit clever ones.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any, cast

import numpy as np
import pandas as pd

from libs.data.calendar import session_of
from libs.discovery.models import HypothesisCategory

Generator = Callable[[pd.DataFrame], np.ndarray]


def _finite(arr: np.ndarray) -> np.ndarray:
    cleaned = np.nan_to_num(np.asarray(arr, dtype="float64"), nan=0.0, posinf=0.0, neginf=0.0)
    return cast("np.ndarray", cleaned)


def _session(params: Mapping[str, Any]) -> Generator:
    target_session = str(params.get("session", "london"))

    def generate(bars: pd.DataFrame) -> np.ndarray:
        flags = [1.0 if session_of(ts) == target_session else 0.0 for ts in bars["timestamp"]]
        return np.asarray(flags, dtype="float64")

    return generate


def _trend(params: Mapping[str, Any]) -> Generator:
    fast, slow = int(params.get("fast", 10)), int(params.get("slow", 30))
    long_only = bool(params.get("long_only", True))

    def generate(bars: pd.DataFrame) -> np.ndarray:
        close = bars["close"]
        signal = (close.rolling(fast).mean() > close.rolling(slow).mean()).astype("float64")
        return _finite(signal if long_only else signal * 2.0 - 1.0)

    return generate


def _breakout(params: Mapping[str, Any]) -> Generator:
    window = int(params.get("window", 20))

    def generate(bars: pd.DataFrame) -> np.ndarray:
        close = bars["close"]
        upper = close.rolling(window).max().shift(1)
        lower = close.rolling(window).min().shift(1)
        target = np.where(close > upper, 1.0, np.where(close < lower, -1.0, 0.0))
        return _finite(target)

    return generate


def _mean_reversion(params: Mapping[str, Any]) -> Generator:
    window, z = int(params.get("window", 20)), float(params.get("z", 1.5))

    def generate(bars: pd.DataFrame) -> np.ndarray:
        close = bars["close"]
        mean = close.rolling(window).mean()
        std = close.rolling(window).std()
        zscore = (close - mean) / std
        target = np.where(zscore > z, -1.0, np.where(zscore < -z, 1.0, 0.0))
        return _finite(target)

    return generate


def _momentum(params: Mapping[str, Any]) -> Generator:
    lookback = int(params.get("lookback", 20))
    long_only = bool(params.get("long_only", False))

    def generate(bars: pd.DataFrame) -> np.ndarray:
        close = bars["close"]
        ret = close / close.shift(lookback) - 1.0
        target = np.sign(_finite(ret.to_numpy()))
        return cast("np.ndarray", np.clip(target, 0.0, 1.0) if long_only else target)

    return generate


def _vol_regime(params: Mapping[str, Any]) -> Generator:
    window = int(params.get("window", 20))
    mode = str(params.get("mode", "compression"))  # compression: long in calm

    def generate(bars: pd.DataFrame) -> np.ndarray:
        ret = np.log(bars["close"] / bars["close"].shift(1))
        vol = ret.rolling(window).std()
        median = vol.rolling(window * 3, min_periods=window).median()
        calm = (vol <= median).astype("float64")
        return _finite(calm if mode == "compression" else 1.0 - calm)

    return generate


def _seasonal(params: Mapping[str, Any]) -> Generator:
    weekday = int(params.get("weekday", 0))  # 0 = Monday

    def generate(bars: pd.DataFrame) -> np.ndarray:
        flags = [1.0 if ts.weekday() == weekday else 0.0 for ts in bars["timestamp"]]
        return np.asarray(flags, dtype="float64")

    return generate


def _carry(params: Mapping[str, Any]) -> Generator:
    direction = float(params.get("direction", 1.0))

    def generate(bars: pd.DataFrame) -> np.ndarray:
        return np.full(len(bars), direction, dtype="float64")

    return generate


_DISPATCH: dict[HypothesisCategory, Callable[[Mapping[str, Any]], Generator]] = {
    HypothesisCategory.SESSION: _session,
    HypothesisCategory.TREND: _trend,
    HypothesisCategory.BREAKOUT: _breakout,
    HypothesisCategory.MEAN_REVERSION: _mean_reversion,
    HypothesisCategory.MOMENTUM: _momentum,
    HypothesisCategory.RELATIVE_STRENGTH: _momentum,
    HypothesisCategory.VOL_REGIME: _vol_regime,
    HypothesisCategory.VOL_COMPRESSION: _vol_regime,
    HypothesisCategory.VOL_EXPANSION: _vol_regime,
    HypothesisCategory.SEASONAL: _seasonal,
    HypothesisCategory.CARRY: _carry,
}


def build_generator(category: HypothesisCategory, params: Mapping[str, Any]) -> Generator:
    """Return the causal target-position generator for a category (momentum proxy as fallback)."""
    factory = _DISPATCH.get(category, _momentum)
    return factory(params)
