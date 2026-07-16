"""Return gap-guard (bad-print spike removal)."""

from __future__ import annotations

import numpy as np
import pandas as pd

from libs.data.cleaning import guard_close


def test_guard_removes_spike_keeps_real_moves() -> None:
    idx = pd.date_range("2020-01-01", periods=10, freq="D", tz="UTC")
    px = pd.Series([100, 101, 102, 101, 100, 250, 101, 102, 103, 104], index=idx, name="EURUSD")
    df = pd.DataFrame({"EURUSD": px})
    out = guard_close(df, {"EURUSD": 0.10})["EURUSD"]
    ret = out.pct_change(fill_method=None)
    assert ret.abs().max() <= 0.1001                      # the 250 spike is capped to <=10%/day
    assert abs(out.iloc[0] - 100.0) < 1e-6                # base price preserved


def test_guard_is_noop_on_clean_series() -> None:
    rng = np.random.default_rng(0)
    idx = pd.date_range("2020-01-01", periods=300, freq="D", tz="UTC")
    px = pd.DataFrame({"X": 100 * np.cumprod(1 + rng.normal(0, 0.01, 300))}, index=idx)
    out = guard_close(px, {"X": 0.10})
    assert np.allclose(out["X"].to_numpy(), px["X"].to_numpy(), rtol=1e-9)
