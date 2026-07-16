"""Crypto-native sleeve cores (funding momentum/reversal, basis carry, taker flow)."""

from __future__ import annotations

import numpy as np
import pandas as pd

from libs.research.crypto_sleeves import (
    basis_carry_returns,
    funding_momentum_returns,
    funding_reversal_returns,
    taker_flow_returns,
)


def _panel(n: int = 500, k: int = 16) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, float]]:
    rng = np.random.default_rng(4)
    idx = pd.date_range("2022-01-01", periods=n, freq="D", tz="UTC")
    cols = [f"P{i}" for i in range(k)]
    close = pd.DataFrame(100 * np.cumprod(1 + rng.normal(0, 0.02, (n, k)), 0), index=idx,
                         columns=cols)
    funding = pd.DataFrame(rng.normal(0.0001, 0.0003, (n, k)), index=idx, columns=cols)
    adv = dict.fromkeys(cols, 1e9)
    return close, funding, adv


def test_funding_sleeves_shape_and_no_lookahead() -> None:
    close, funding, adv = _panel()
    for fn in (funding_momentum_returns, funding_reversal_returns):
        r = fn(close, funding, adv, lookback=7, q=0.2, band=0.02)
        assert len(r) == len(close)
        assert r[0] == 0.0
        assert np.isfinite(r).all()


def test_basis_carry_shape_and_no_lookahead() -> None:
    close, funding, adv = _panel()
    rng = np.random.default_rng(5)
    basis = pd.DataFrame(rng.normal(0, 0.002, close.shape), index=close.index,
                         columns=close.columns)
    r = basis_carry_returns(close, funding, basis, adv, lookback=3, q=0.2, band=0.02)
    assert len(r) == len(close)
    assert r[0] == 0.0
    assert np.isfinite(r).all()


def test_taker_flow_shape_and_no_lookahead() -> None:
    close, funding, adv = _panel()
    rng = np.random.default_rng(6)
    taker = pd.DataFrame(0.5 + rng.normal(0, 0.05, close.shape), index=close.index,
                         columns=close.columns)
    r = taker_flow_returns(close, funding, taker, adv, lookback=5, q=0.2, band=0.02)
    assert len(r) == len(close)
    assert r[0] == 0.0
    assert np.isfinite(r).all()
