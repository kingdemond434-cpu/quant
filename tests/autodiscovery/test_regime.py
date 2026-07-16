"""Regime-robustness gate (committee Lever 3 / T8)."""

from __future__ import annotations

import numpy as np

from libs.autodiscovery.regime import regime_robust, vol_regime_labels


def test_short_series_is_not_robust() -> None:
    assert regime_robust(np.full(50, 0.001)) is False  # too short to confirm


def test_labels_cover_three_regimes() -> None:
    rng = np.random.default_rng(0)
    # vol rises across the series -> all three tercile labels should appear
    rets = np.concatenate([rng.normal(0, 0.001, 200), rng.normal(0, 0.01, 200)])
    labels = vol_regime_labels(rets)
    assert set(np.unique(labels[labels >= 0])) == {0, 1, 2}


def test_edge_confined_to_one_regime_fails() -> None:
    rng = np.random.default_rng(1)
    # three contiguous volatility blocks; only the high-vol block is profitable, others bleed
    low = rng.normal(-0.0006, 0.0004, 160)      # low vol, negative drift
    mid = rng.normal(-0.0006, 0.003, 160)       # mid vol, negative drift
    high = rng.normal(0.004, 0.010, 160)        # high vol, positive drift
    rets = np.concatenate([low, mid, high])
    assert regime_robust(rets) is False          # edge only in one regime -> not robust


def test_broad_edge_passes() -> None:
    rng = np.random.default_rng(2)
    rets = 0.0005 + rng.normal(0, 0.003, 400)   # small positive drift across all regimes
    assert regime_robust(rets) is True
