"""Regime-robustness gate (committee Lever 3 / T8).

A durable edge should not live in a single market state. We split the strategy's own return series
by realized-volatility regime (low / mid / high terciles) and require it to be net-positive in at
least two of them before it can reach REGISTRY. This is the price-derivable part of regime
intelligence; macro regimes (inflation/growth/credit) remain data-gated and are NOT faked.
"""

from __future__ import annotations

import numpy as np

_MIN_BARS = 90
_VOL_WINDOW = 20


def vol_regime_labels(returns: np.ndarray, *, window: int = _VOL_WINDOW) -> np.ndarray:
    """Label each bar 0/1/2 by realized-vol tercile (low/mid/high); -1 where vol is undefined."""
    n = len(returns)
    labels = np.full(n, -1, dtype="int64")
    if n < window + 1:
        return labels
    vol = np.full(n, np.nan, dtype="float64")
    for i in range(window, n):
        vol[i] = returns[i - window + 1: i + 1].std()
    valid = ~np.isnan(vol)
    if valid.sum() < 3:
        return labels
    lo, hi = np.nanquantile(vol, [1 / 3, 2 / 3])
    labels[valid & (vol <= lo)] = 0
    labels[valid & (vol > lo) & (vol <= hi)] = 1
    labels[valid & (vol > hi)] = 2
    return labels


def regime_robust(returns: np.ndarray, *, min_positive_regimes: int = 2) -> bool:
    """True iff the strategy is net-positive in at least ``min_positive_regimes`` vol regimes."""
    if len(returns) < _MIN_BARS:
        return False  # cannot confirm robustness on a short sample -> conservative reject
    labels = vol_regime_labels(returns)
    positive = 0
    present = 0
    for r in (0, 1, 2):
        mask = labels == r
        if mask.any():
            present += 1
            if float(np.sum(returns[mask])) > 0.0:
                positive += 1
    return present >= min_positive_regimes and positive >= min_positive_regimes
