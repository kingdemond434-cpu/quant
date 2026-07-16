"""Cross-asset diversified-portfolio strategy cores (MT5 edge search)."""

from __future__ import annotations

import numpy as np
import pandas as pd

from libs.research.crossasset import (
    combine_weights,
    trend_basket_returns,
    trend_basket_weights,
    vol_target,
    xsec_momentum_returns,
    xsec_momentum_weights,
)


def _panel(n_days: int = 500, n_names: int = 12, drift: float = 0.0) -> tuple[pd.DataFrame, dict]:
    rng = np.random.default_rng(1)
    idx = pd.date_range("2018-01-01", periods=n_days, freq="D", tz="UTC")
    cols = [f"A{i}" for i in range(n_names)]
    # per-name persistent drift so momentum/trend have something to find
    per = np.linspace(-drift, drift, n_names)
    rets = rng.normal(0, 0.01, (n_days, n_names)) + per
    close = pd.DataFrame(100 * np.cumprod(1 + rets, 0), index=idx, columns=cols)
    cost = dict.fromkeys(cols, 1.0e-4)
    return close, cost


def test_momentum_shape_and_no_lookahead() -> None:
    close, cost = _panel()
    r = xsec_momentum_returns(close, cost, lookback=60, q=0.3, band=0.05)
    assert len(r) == len(close)
    assert r[0] == 0.0                         # no prior signal on first bar -> flat
    assert np.isfinite(r).all()


def test_trend_basket_shape_and_no_lookahead() -> None:
    close, cost = _panel()
    r = trend_basket_returns(close, cost, lookback=50, band=0.05)
    assert len(r) == len(close)
    assert r[0] == 0.0
    assert np.isfinite(r).all()


def test_momentum_captures_persistent_dispersion() -> None:
    # strong persistent cross-sectional drift -> long-winners/short-losers should net positive
    close, cost = _panel(drift=0.0015)
    r = xsec_momentum_returns(close, cost, lookback=60, q=0.3, band=0.0, long_high=True)
    assert float(np.mean(r[r != 0.0])) > 0.0


def test_reversal_is_opposite_sign_of_momentum() -> None:
    close, cost = _panel(drift=0.0015)
    mom = xsec_momentum_returns(close, cost, lookback=60, q=0.3, band=0.0, long_high=True)
    rev = xsec_momentum_returns(close, cost, lookback=60, q=0.3, band=0.0, long_high=False)
    # on the same trending panel the reversal leg should not also be net positive
    assert float(np.mean(rev[rev != 0.0])) <= float(np.mean(mom[mom != 0.0]))


def test_trend_basket_weights_gross_normalized() -> None:
    close, _ = _panel()
    w = trend_basket_weights(close, lookback=50)
    assert w
    assert abs(sum(abs(v) for v in w.values()) - 1.0) < 1e-9   # gross-normalized to 1


def test_xsec_momentum_weights_dollar_neutral() -> None:
    close, _ = _panel()
    w = xsec_momentum_weights(close, lookback=60, q=0.3)
    assert w
    assert abs(sum(w.values())) < 1e-9                          # dollar-neutral (longs == shorts)
    assert abs(sum(abs(v) for v in w.values()) - 1.0) < 1e-9   # gross ~1


def test_vol_target_stabilizes_vol_and_no_lookahead() -> None:
    rng = np.random.default_rng(2)
    # regime-switching vol: calm then turbulent -> vol targeting should compress the gap
    r = np.concatenate([rng.normal(0, 0.005, 400), rng.normal(0, 0.03, 400)])
    vt = vol_target(r, target_ann_vol=0.10, lookback=30)
    assert len(vt) == len(r)
    assert vt[0] == 0.0                          # no trailing vol yet -> flat (no look-ahead)
    raw_gap = np.std(r[400:]) / np.std(r[:400])
    vt_gap = np.std(vt[430:]) / np.std(vt[60:400])
    assert vt_gap < raw_gap                      # turbulent/calm vol gap is compressed


def test_combine_weights_renormalizes() -> None:
    a = {"X": 0.6, "Y": -0.4}
    b = {"X": 0.2, "Z": 0.8}
    c = combine_weights(a, b)
    assert abs(sum(abs(v) for v in c.values()) - 1.0) < 1e-9
    assert not combine_weights()
