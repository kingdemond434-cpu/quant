"""Tests for the naive-baseline scorecard (qlib benchmark-harness philosophy)."""

from __future__ import annotations

import numpy as np
import pytest

from libs.validation.baselines import baseline_scorecard
from libs.validation.errors import ValidationError


def test_strategy_that_dominates_beats_all() -> None:
    rng = np.random.default_rng(0)
    strat = rng.normal(0.002, 0.01, 300)   # positive drift, low vol
    bh = rng.normal(0.0005, 0.03, 300)     # noisier, weaker benchmark
    sc = baseline_scorecard(strat, buy_hold_returns=bh)
    assert sc.strategy_sharpe > sc.buy_hold_sharpe
    assert sc.beats_all
    assert bool(sc) is True


def test_strategy_that_loses_to_buy_hold_is_flagged() -> None:
    rng = np.random.default_rng(3)
    bh = rng.normal(0.003, 0.01, 300)      # strong benchmark
    strat = rng.normal(0.0002, 0.01, 300)  # weak strategy, same vol
    sc = baseline_scorecard(strat, buy_hold_returns=bh)
    assert not sc.beats_all
    assert sc.excess_over_buy_hold < 0.0


def test_equal_weight_baseline_derived_from_universe() -> None:
    rng = np.random.default_rng(4)
    universe = rng.normal(0.001, 0.02, (200, 5))
    strat = rng.normal(0.002, 0.01, 200)
    sc = baseline_scorecard(strat, buy_hold_returns=universe[:, 0], universe_returns=universe)
    assert isinstance(sc.equal_weight_sharpe, float)
    # equal-weight baseline is the cross-sectional mean, distinct from the single-name buy-hold
    assert sc.equal_weight_sharpe != sc.buy_hold_sharpe


def test_length_mismatch_raises() -> None:
    with pytest.raises(ValidationError):
        baseline_scorecard(np.zeros(10), buy_hold_returns=np.zeros(9))
