"""Portfolio stress testing."""

from __future__ import annotations

import numpy as np
import pandas as pd

from libs.risk.stress import beta_shock, crisis_replay, worst_window


def test_crisis_replay_slices_named_windows() -> None:
    idx = pd.date_range("2022-10-20", periods=60, freq="D", tz="UTC")
    r = np.full(60, -0.01)                                 # steady losses spanning the FTX window
    out = crisis_replay(r, idx)
    assert "ftx_collapse_2022" in out
    assert out["ftx_collapse_2022"]["cum_return"] < 0
    assert out["ftx_collapse_2022"]["max_dd"] < 0


def test_worst_window_finds_the_tail() -> None:
    rng = np.random.default_rng(0)
    r = rng.normal(0.001, 0.005, 300)
    r[150:160] = -0.05                                     # planted crash
    idx = pd.date_range("2023-01-01", periods=300, freq="D", tz="UTC")
    w = worst_window(r, idx, n=10)
    assert w["worst_cum_return"] < -0.3


def test_beta_shock_detects_market_exposure() -> None:
    rng = np.random.default_rng(1)
    m = rng.normal(0, 0.02, 500)
    r = 0.8 * m + rng.normal(0, 0.001, 500)               # beta ~0.8 to market
    out = beta_shock(r, m, shock=-0.30)
    assert abs(out["beta"] - 0.8) < 0.1
    assert out["est_pnl"] < 0                              # long-beta book loses on a crash
