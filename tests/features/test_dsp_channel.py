"""quants-lab's Ehlers channels and support/resistance levels, ported causally."""
from __future__ import annotations

import numpy as np
import pandas as pd

from libs.features import dsp_channel as D


def _bars(n: int = 1500, seed: int = 0) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2024-01-01", periods=n, freq="h", tz="UTC")
    c = 1.1 * np.exp(np.cumsum(rng.normal(0, 0.001, n)))
    w = np.abs(rng.normal(0, 0.0005, n))
    return pd.DataFrame({"open": c, "high": c + w, "low": c - w, "close": c}, index=idx)


def test_filters_pass_a_constant_and_lag_a_ramp():
    for kind in ("supersmoother", "butterworth", "gaussian"):
        flat = D.smooth(pd.Series(np.full(200, 3.0)), 20, kind)
        assert np.allclose(flat, 3.0)
        ramp = D.smooth(pd.Series(np.arange(300.0)), 20, kind)
        assert 0 < 299 - ramp.iloc[-1] < 20                       # smooths, so it trails
    assert D.smooth(pd.Series([np.nan, np.nan, 1.0, 1.0]), 10).isna().sum() == 2


def test_levels_cluster_repeated_peaks_into_one_level():
    t = np.arange(600)
    c = 1.0 + 0.01 * np.sin(2 * np.pi * t / 60)                   # tops near 1.01, every 60 bars
    idx = pd.date_range("2024-01-01", periods=600, freq="h", tz="UTC")
    df = pd.DataFrame({"high": c + 1e-4, "low": c - 1e-4, "close": c}, index=idx)
    lv = D.levels(df, window=240, confirm=6, prominence_atr=2.0, merge_atr=2.0)
    row = lv.dropna().iloc[-1]
    assert row["res_touches"] >= 3 or row["sup_touches"] >= 3


def test_every_column_is_causal():
    df = _bars()
    f = D.features(df)
    cut = 1000
    df2 = df.copy()
    df2.iloc[cut:, :] = df2.iloc[cut:, :] * 1.05
    pd.testing.assert_frame_equal(f.iloc[:cut], D.features(df2).iloc[:cut])
