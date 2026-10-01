"""ml4t's Wasserstein k-means regimes and trend-scanning target, ported causally."""
from __future__ import annotations

import numpy as np
import pandas as pd

from libs.features import wasserstein_regime as W


def _bars(n: int = 3000, seed: int = 3) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2024-01-01", periods=n, freq="h", tz="UTC")
    scale = np.where((np.arange(n) // 400) % 2 == 0, 0.001, 0.004)   # calm and stormy blocks
    close = 1.1 * np.exp(np.cumsum(rng.normal(0, 1, n) * scale))
    return pd.DataFrame({"close": close}, index=idx), scale


def test_distance_and_barycenter_are_quantile_operations():
    a, b = np.sort(np.array([0.0, 1.0, 2.0])), np.sort(np.array([1.0, 2.0, 3.0]))
    assert W.wasserstein_distance_1d(a, b) == 1.0
    m = np.array([[0.0, 1.0], [2.0, 3.0], [10.0, 11.0]])
    assert np.allclose(W.barycenter(m, 1.0), [2.0, 3.0])
    assert np.allclose(W.barycenter(m, 2.0), [4.0, 5.0])
    assert W.lift_stream(np.arange(3.0), 5).shape == (0, 5)


def test_kmeans_orders_regimes_calm_first():
    rng = np.random.default_rng(0)
    calm = np.sort(rng.normal(0, 1, (80, 48)), axis=1)
    wild = np.sort(rng.normal(0, 5, (80, 48)), axis=1)
    cent = W.kmeans(np.vstack([wild, calm]), 2)
    assert (cent[0, -1] - cent[0, 0]) < (cent[1, -1] - cent[1, 0])


def test_features_find_the_planted_regimes_and_never_see_ahead():
    df, scale = _bars()
    f = W.features(df)
    assert f.iloc[: W.WINDOW + W.MIN_FIT_WINDOWS * W.FIT_STRIDE]["wregime"].isna().all()
    lab = f["wregime"].dropna()
    stormy = scale[df.index.get_indexer(lab.index)] > 0.002
    # the calmest regime is the calm block; the stormy block lands in the wider ones
    assert (lab[stormy] >= 1).mean() > 0.8 and (lab[~stormy] == 0).mean() > 0.6
    # causality: changing the future leaves the past coordinates unchanged
    cut = 2000
    df2 = df.copy()
    df2.iloc[cut:, 0] = df2.iloc[cut:, 0] * np.exp(np.linspace(0, 1, len(df) - cut))
    f2 = W.features(df2)
    pd.testing.assert_frame_equal(f.iloc[:cut], f2.iloc[:cut])


def test_trend_scan_reads_the_forward_slope_with_bounded_lookahead():
    idx = pd.date_range("2024-01-01", periods=40, freq="h", tz="UTC")
    noise = np.random.default_rng(1).normal(0, 1e-4, 40)
    up = pd.Series(np.exp(np.r_[np.linspace(0, 0.02, 20), np.linspace(0.02, 0.0, 20)] + noise),
                   index=idx)
    t = W.trend_scan_t(up, horizon=6)
    assert np.isnan(t[-6:]).all() and np.isfinite(t[:-6]).all()
    assert (t[:12] > 2).all() and (t[22:33] < -2).all()
