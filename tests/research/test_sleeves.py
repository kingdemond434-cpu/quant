"""Relative-value and positioning sleeve cores (MT5 alpha portfolio)."""

from __future__ import annotations

import numpy as np
import pandas as pd

from libs.research.sleeves import (
    calendar_event_returns,
    cot_positioning_returns,
    cot_timeseries_returns,
    crisis_hedge_returns,
    ratio_meanrev_returns,
    swap_carry_returns,
)


def _prices(n: int = 600, k: int = 8) -> pd.DataFrame:
    rng = np.random.default_rng(3)
    idx = pd.date_range("2018-01-01", periods=n, freq="D", tz="UTC")
    cols = [f"S{i}" for i in range(k)]
    px = 100 * np.cumprod(1 + rng.normal(0, 0.01, (n, k)), 0)
    return pd.DataFrame(px, index=idx, columns=cols)


def test_ratio_meanrev_shape_and_no_lookahead() -> None:
    px = _prices()
    r = ratio_meanrev_returns(px["S0"], px["S1"], lookback=60)
    assert len(r) == len(px)
    assert r[0] == 0.0
    assert np.isfinite(r).all()


def test_ratio_meanrev_profits_on_mean_reverting_pair() -> None:
    # construct a cointegrated pair: B = A * stationary noise -> ratio mean-reverts
    rng = np.random.default_rng(5)
    idx = pd.date_range("2018-01-01", periods=800, freq="D", tz="UTC")
    a = pd.Series(100 * np.cumprod(1 + rng.normal(0, 0.01, 800)), index=idx)
    wobble = np.exp(rng.normal(0, 0.02, 800))            # mean-reverting multiplicative noise
    b = a * wobble
    r = ratio_meanrev_returns(a, b, lookback=30, cost=0.0, band=0.0)
    assert float(np.mean(r[r != 0.0])) > 0.0


def test_cot_positioning_and_timeseries_no_lookahead() -> None:
    px = _prices()
    rng = np.random.default_rng(7)
    cz = pd.DataFrame(rng.normal(0, 1, px.shape), index=px.index, columns=px.columns)
    rp = cot_positioning_returns(px, cz, dict.fromkeys(px.columns, 1e-4), band=0.05, min_names=3)
    rt = cot_timeseries_returns(px, cz, dict.fromkeys(px.columns, 1e-4), band=0.05)
    for r in (rp, rt):
        assert len(r) == len(px)
        assert r[0] == 0.0
        assert np.isfinite(r).all()


def test_calendar_event_only_active_in_tom_window() -> None:
    rng = np.random.default_rng(9)
    idx = pd.date_range("2018-01-01", periods=500, freq="B", tz="UTC")
    cols = ["I0", "I1", "I2"]
    raw = 100 * np.cumprod(1 + rng.normal(0, 0.01, (500, 3)), 0)
    px = pd.DataFrame(raw, index=idx, columns=cols)
    r = calendar_event_returns(px, cost=1e-4, tom_first=3)
    assert len(r) == len(px)
    assert r[0] == 0.0
    assert np.isfinite(r).all()
    # the book is flat most days (only active in the turn-of-month window)
    assert float(np.mean(r == 0.0)) > 0.5


def test_swap_carry_shape_and_carry_pnl() -> None:
    # low price noise + sizeable constant carry so the harvested carry dominates price P&L
    rng = np.random.default_rng(11)
    idx = pd.date_range("2018-01-01", periods=400, freq="B", tz="UTC")
    cols = [f"S{i}" for i in range(8)]
    pxv = 100 * np.cumprod(1 + rng.normal(0, 0.002, (400, 8)), 0)
    px = pd.DataFrame(pxv, index=idx, columns=cols)
    cl = pd.DataFrame(0.0, index=px.index, columns=px.columns)
    cs = pd.DataFrame(0.0, index=px.index, columns=px.columns)
    for i, c in enumerate(px.columns):
        cl[c] = 0.0006 if i < 4 else -0.0006        # high long-carry on half, negative on the rest
        cs[c] = -0.0006 if i < 4 else 0.0006        # shorting the negative-carry names also earns
    r = swap_carry_returns(px, cl, cs, dict.fromkeys(px.columns, 0.0), q=0.3, band=0.0)
    assert len(r) == len(px)
    assert np.isfinite(r).all()
    assert float(np.mean(r[r != 0.0])) > 0.0          # positive carry is harvested


def test_crisis_hedge_only_trades_in_riskoff() -> None:
    idx = pd.date_range("2018-01-01", periods=400, freq="D", tz="UTC")
    gold = pd.Series(100 * np.cumprod(1 + np.full(400, 0.001)), index=idx)   # gold drifts up
    equity = pd.Series(np.linspace(200, 100, 400), index=idx)                # equity declining
    r = crisis_hedge_returns(gold, equity, ma_window=50, cost=0.0)
    assert len(r) == len(gold)
    # equity always below its MA late in the decline -> hedge is active and long rising gold
    assert float(np.sum(r[200:])) > 0.0
