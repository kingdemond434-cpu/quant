"""Tests for the alpha-lifecycle primitives."""

from __future__ import annotations

from libs.portfolio.lifecycle import (
    decay_state,
    promotion_stage,
    rank_by_roi,
    replacement_decision,
    research_roi,
)


def test_decay_accumulating_until_windows_exist() -> None:
    assert decay_state({"30d": None, "60d": None}, 1.0) == "Accumulating"


def test_decay_states_by_drop() -> None:
    assert decay_state({"30d": 1.0}, 1.0) == "Healthy"
    assert decay_state({"30d": 0.75}, 1.0) == "Watchlist"     # 25% drop
    assert decay_state({"30d": 0.5}, 1.0) == "Degraded"       # 50% drop
    assert decay_state({"30d": -0.1}, 1.0) == "Retire"        # negative


def test_promotion_ladder_is_conservative() -> None:
    assert promotion_stage(0, None, 4, 9) == "research"       # weak gates
    assert promotion_stage(10, None, 7, 9) == "shadow"        # no forward yet
    assert promotion_stage(95, 0.8, 7, 9) == "testnet"        # full window + edge
    assert promotion_stage(140, 0.8, 7, 9) == "small_capital"  # never auto past this


def test_replacement_defaults_keep_both() -> None:
    cur = {"sharpe": 1.0, "cagr": 0.2, "capacity": 1.0}
    better_orthogonal = {"sharpe": 1.3, "cagr": 0.25, "capacity": 1.0}
    better_same = {"sharpe": 1.3, "cagr": 0.25, "capacity": 1.0}
    worse = {"sharpe": 0.8, "cagr": 0.1, "capacity": 1.0}
    assert replacement_decision(cur, better_orthogonal, correlation=0.1) == "keep_both"
    assert replacement_decision(cur, better_same, correlation=0.8) == "replace"
    assert replacement_decision(cur, worse, correlation=0.9) == "reject"


def test_research_roi_and_ranking() -> None:
    assert research_roi(0.2, 0.5, 2.0) == 0.05
    ranked = rank_by_roi([
        {"name": "a", "benefit": 0.1, "p_success": 0.9, "effort": 1.0},
        {"name": "b", "benefit": 0.3, "p_success": 0.5, "effort": 5.0},
    ])
    assert ranked[0]["name"] == "a"            # 0.09 > 0.03
