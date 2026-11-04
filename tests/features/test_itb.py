"""intelligent-trading-bot's feature generators and its bounded top/bottom labels."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from libs.features import itb


def _bars(n: int = 4000, seed: int = 7) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2024-01-01", periods=n, freq="h", tz="UTC")
    close = 1.1 * np.exp(np.cumsum(rng.normal(0, 0.001, n) * (1 + 3 * (idx.hour < 8))))
    w = np.abs(rng.normal(0, 0.0004, n))
    return pd.DataFrame({"open": close, "high": close + w, "low": close - w, "close": close,
                         "tick_volume": rng.integers(50, 500, n).astype(float)}, index=idx)


def test_port_matches_upstream_arithmetic():
    x = np.array([1.0, 3.0, 2.0, 5.0, 4.0])
    assert itb.slope_fn(x) == pytest.approx(np.polyfit(np.arange(5), x, 1)[0])
    assert itb.fmax_fn(x) == pytest.approx(3 / 5)
    assert itb.lsbm_fn(np.array([1.0, 1.0, 5.0, 1.0, 1.0, 1.0])) == pytest.approx(3 / 6)
    assert itb.area_fn(np.array([1.0, 2.0, 3.0])) == pytest.approx(-1.0)   # all below newest
    assert itb.area_fn(np.array([3.0, 2.0, 1.0])) == pytest.approx(1.0)    # all above newest
    assert np.isnan(itb.area_fn(np.ones(4)))


def test_every_itb_feature_is_a_past_window():
    d = _bars()
    full = itb.features(d)
    cut = itb.features(d.iloc[:1800])
    pd.testing.assert_frame_equal(full.iloc[:1800], cut)
    assert full.iloc[100:].notna().all().all()


def test_extremum_label_marks_a_planted_top_and_sees_only_h_bars_ahead():
    d = _bars()
    c = d["close"].copy()
    i = 1500
    c.iloc[i - 3:i + 4] *= np.array([1.00, 1.01, 1.02, 1.03, 1.02, 1.01, 1.00])
    lab = itb.extremum_labels(c, is_max=True, horizon=6)
    assert lab.iloc[i] == 1.0
    assert itb.extremum_labels(c, is_max=False, horizon=6).iloc[i] == 0.0
    short = itb.extremum_labels(c.iloc[:i + 7], is_max=True, horizon=6)
    assert short.iloc[i] == lab.iloc[i]
    pd.testing.assert_series_equal(short.iloc[:i + 1], lab.iloc[:i + 1])
