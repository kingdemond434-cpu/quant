"""Candidates must be causal and correctly aligned. A dip-buyer that peeks backtests beautifully
and is worthless, so these properties are pinned before any of them reaches the gauntlet."""
from __future__ import annotations

import numpy as np
import pytest

from libs.research import transcript_candidates as tc

_FNS = {
    "chaikin_money_flow": lambda d: tc.chaikin_money_flow(d["h"], d["l"], d["c"], d["v"]),
    "volume_surge_breakout": lambda d: tc.volume_surge_breakout(d["c"], d["v"]),
    "obv_trend": lambda d: tc.obv_trend(d["c"], d["v"]),
    "zscore_reversion": lambda d: tc.zscore_reversion(d["c"]),
    "bollinger_reversion": lambda d: tc.bollinger_reversion(d["c"]),
    "percent_b_reversion": lambda d: tc.percent_b_reversion(d["c"]),
    "rsi_mean_reversion": lambda d: tc.rsi_mean_reversion(d["c"]),
    "range_position_dip": lambda d: tc.range_position_dip(d["h"], d["l"], d["c"], trend_n=20),
    "squeeze_momentum": lambda d: tc.squeeze_momentum(d["h"], d["l"], d["c"]),
    "donchian_breakout": lambda d: tc.donchian_breakout(d["h"], d["l"], d["c"]),
    "golden_cross": lambda d: tc.golden_cross(d["c"], fast=5, slow=20),
    "absolute_momentum": lambda d: tc.absolute_momentum(d["c"], lookback=20),
    "trend_gated_rotation": lambda d: tc.trend_gated_rotation(d["c"], d["c"], n=20),
}


def _bars(n=400, seed=0):
    rng = np.random.default_rng(seed)
    c = 100.0 * np.exp(np.cumsum(rng.standard_normal(n) * 0.01))
    spread = np.abs(rng.standard_normal(n)) * 0.5
    return {"c": c, "h": c + spread, "l": c - spread,
            "v": np.abs(rng.standard_normal(n)) * 1000 + 100}


@pytest.mark.parametrize("name", sorted(_FNS))
def test_every_candidate_is_causal(name):
    """THE PROPERTY THAT DECIDES WHETHER ANY OF THIS IS REAL. Truncating the future must not
    change a single position that was already decided."""
    d = _bars()
    full = _FNS[name](d)
    cut = 250
    early = _FNS[name]({k: v[:cut] for k, v in d.items()})
    assert np.allclose(np.nan_to_num(full[:cut]), np.nan_to_num(early), atol=1e-12), (
        f"{name} changed an earlier decision when later bars were removed -- it peeks")


@pytest.mark.parametrize("name", sorted(_FNS))
def test_positions_are_bounded_finite_and_aligned(name):
    d = _bars()
    p = _FNS[name](d)
    assert len(p) == len(d["c"])
    assert np.all(np.isfinite(np.nan_to_num(p)))
    assert np.max(np.abs(np.nan_to_num(p))) <= 1.0 + 1e-12


def test_position_earns_the_NEXT_bar_not_this_one():
    """The alignment that separates a backtest from fiction: decide on today's close, earn
    tomorrow's move."""
    c = np.array([100.0, 110.0, 121.0])
    long_from_start = np.array([1.0, 1.0, 1.0])
    r = tc.positions_to_returns(long_from_start, c, cost_per_turn=0.0)
    assert len(r) == 2
    assert np.isclose(r[0], 0.10) and np.isclose(r[1], 0.10)
    # a position taken only on the LAST bar earns nothing, because there is no next bar
    late = np.array([0.0, 0.0, 1.0])
    assert np.allclose(tc.positions_to_returns(late, c, cost_per_turn=0.0), 0.0)


def test_costs_are_charged_on_every_turn():
    """Three transcripts independently name ignored costs as the reason backtests lie."""
    c = np.array([100.0, 100.0, 100.0, 100.0])
    flip = np.array([1.0, -1.0, 1.0, -1.0])
    free = tc.positions_to_returns(flip, c, cost_per_turn=0.0)
    paid = tc.positions_to_returns(flip, c, cost_per_turn=0.01)
    assert np.sum(paid) < np.sum(free)
    assert np.isclose(np.sum(free), 0.0)          # flat price, no cost -> no pnl


def test_vol_target_scales_down_in_a_loud_market():
    rng = np.random.default_rng(3)
    quiet = 100.0 * np.exp(np.cumsum(rng.standard_normal(300) * 0.002))
    loud = 100.0 * np.exp(np.cumsum(rng.standard_normal(300) * 0.05))
    pos = np.ones(300)
    assert np.nanmean(tc.vol_target(pos, loud)[50:]) < np.nanmean(tc.vol_target(pos, quiet)[50:])


def test_vol_target_is_capped():
    """An uncapped inverse-vol lever pushes hardest into the quiet period right before a break."""
    flat = np.full(300, 100.0)
    assert np.max(tc.vol_target(np.ones(300), flat, cap=3.0)) <= 3.0


def test_regime_filter_only_removes_never_adds():
    d = _bars()
    base = tc.rsi_mean_reversion(d["c"])
    gated = tc.regime_filter(base, d["c"], n=20)
    assert np.all(np.abs(gated) <= np.abs(np.nan_to_num(base)) + 1e-12)
    same_sign = (np.sign(gated) == np.sign(np.nan_to_num(base))) | (gated == 0)
    assert np.all(same_sign), "the filter flipped a position instead of removing it"


def test_the_family_map_matches_the_measured_base_rates():
    """The ordering is the point: gauntlet slots are scarce, and spending them in proportion to a
    measured survival rate rather than to intuition is free expected value."""
    assert set(tc.CANDIDATES.values()) <= set(tc.FAMILY_SURVIVAL)
    assert tc.FAMILY_SURVIVAL["volume"] > tc.FAMILY_SURVIVAL["trend"]
    assert tc.FAMILY_SURVIVAL["mean_reversion"] > tc.FAMILY_SURVIVAL["momentum"]
    # every advertised candidate actually exists and is callable
    for name in tc.CANDIDATES:
        assert callable(getattr(tc, name)), f"{name} is advertised but not implemented"


def test_a_flat_tape_produces_no_position_churn():
    flat = np.full(300, 100.0)
    d = {"c": flat, "h": flat.copy(), "l": flat.copy(), "v": np.full(300, 500.0)}
    for name in ("zscore_reversion", "rsi_mean_reversion", "percent_b_reversion"):
        p = np.nan_to_num(_FNS[name](d))
        assert np.all(p == 0.0), f"{name} traded a perfectly flat tape"
