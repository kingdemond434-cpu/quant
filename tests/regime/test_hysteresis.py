"""Volatility hysteresis router: ranks use PRIOR bars only, the asymmetric band holds state in the
dead zone, `fixed` toggles at one cutoff, `persistence` waits for confirmation, and an unknown
mode is refused."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from libs.regime import hysteresis as H


def test_percentile_rank_is_strictly_prior() -> None:
    atr = pd.Series(np.arange(1.0, 61.0))
    r = H.percentile_rank(atr, history=30)
    # the first 30 bars (shifted window not yet 30 deep with min_periods 30) are unmeasured
    assert r.iloc[:30].isna().all()
    # rank compares the last PRIOR value against its own window, never the current bar
    assert r.iloc[40] == pytest.approx(29 / 30 * 100)
    spike = atr.copy()
    spike.iloc[50] = 1000.0
    r2 = H.percentile_rank(spike, history=30)
    assert r2.iloc[50] == r.iloc[50]                      # the spike cannot rank itself
    assert r2.iloc[51] == pytest.approx(29 / 30 * 100)


def _atr_from_ranks(levels: list[float], history: int = 40) -> pd.Series:
    """Random warm-up, four bars ranked at zero (so every classifier starts LOW), then `levels`.
    The rank shown at bar i is of bar i-1's ATR."""
    rng = np.random.default_rng(0)
    warm = list(rng.uniform(0, 100, history))
    return pd.Series([*warm, -50.0, -51.0, -52.0, -53.0, *levels], dtype=float)


def test_unknown_mode_is_refused() -> None:
    with pytest.raises(ValueError, match="unknown mode"):
        H.regime_series(pd.Series([1.0, 2.0]), mode="magic")


def test_nan_ranks_hold_the_initial_low_state() -> None:
    out = H.regime_series(pd.Series(np.linspace(1, 2, 20)), history=250)
    assert out["rank"].isna().all() and (out["level"] == H.LOW).all()
    assert not out["switch"].iloc[1:].any()
    assert list(out.columns) == ["rank", "level", "rising", "state", "switch"]
    assert out["state"].iloc[-1] == "low_vol_rising"


def test_hysteresis_holds_state_inside_the_dead_band() -> None:
    atr = _atr_from_ranks([200.0, 60.0, 58.0, 60.0, -100.0, 60.0])
    hyst = H.regime_series(atr, mode="hysteresis", history=40, enter_high=70, exit_high=45)
    fixed = H.regime_series(atr, mode="fixed", history=40, fixed_threshold=70)
    lv_h = list(hyst["level"].iloc[-6:])
    lv_f = list(fixed["level"].iloc[-6:])
    rank = hyst["rank"].iloc[-6:].to_numpy()
    # The rank at bar i is of bar i-1's ATR, so the spike shows one bar later.
    assert rank[1] > 70 and 45 < rank[2] < 70
    assert lv_h[1] == H.HIGH and lv_h[2] == H.HIGH        # dead band keeps HIGH
    assert lv_f[1] == H.HIGH and lv_f[2] == H.LOW         # fixed drops at once
    assert rank[5] < 45 and lv_h[5] == H.LOW              # below exit: leaves
    assert hyst["switch"].sum() <= fixed["switch"].sum()


def test_persistence_needs_consecutive_confirmation() -> None:
    atr = _atr_from_ranks([500.0, 600.0, 700.0, 800.0, 900.0])
    per = H.regime_series(atr, mode="persistence", history=40, fixed_threshold=70,
                          persistence=3)
    fixed = H.regime_series(atr, mode="fixed", history=40, fixed_threshold=70)
    lv_p = list(per["level"].iloc[-5:])
    lv_f = list(fixed["level"].iloc[-5:])
    # ranks of bars -4..-1 are all above 70; fixed flips on the first, persistence on the third
    assert lv_f[1] == H.HIGH
    assert lv_p[1] == H.LOW and lv_p[2] == H.LOW and lv_p[3] == H.HIGH


def test_rising_compares_against_slope_bars_back() -> None:
    atr = pd.Series([1.0, 2.0, 3.0, 2.0, 1.0, 0.5])
    out = H.regime_series(atr, history=250, slope_bars=2)
    assert list(out["rising"]) == [False, False, True, False, False, False]
    assert out["state"].iloc[2] == "low_vol_rising" and out["state"].iloc[3].endswith("_falling")
