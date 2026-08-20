"""Ruin must compare as worse than any drawdown budget, not as NaN.

The defect: `np.cumprod(1 + q*x)` goes negative once a day satisfies
1 + q*x <= 0, the drawdown expression yields NaN, and `NaN > target` is False --
so a bisection reads a wiped-out account as a satisfied budget and sizes UP.
Every arm of research/push_ceiling.py returned the hard upper bound and printed
CAGR of +inf and -100%.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

_DESK = Path(__file__).resolve().parents[1]
if str(_DESK) not in sys.path:
    sys.path.insert(0, str(_DESK))

from mt5desk.sizing import max_drawdown, q_for_drawdown, ruin_q     # noqa: E402


def test_ruin_reports_a_full_drawdown_not_a_nan():
    x = np.array([0.1, -0.5, 0.1])
    assert max_drawdown(x, 2.0) == 1.0          # 1 + 2*(-0.5) == 0 exactly
    assert max_drawdown(x, 5.0) == 1.0          # past ruin, product negative


def test_the_comparison_that_caused_the_bug():
    """`NaN > target` is False; 1.0 > target is True. That is the whole fix."""
    x = np.array([0.1, -0.5, 0.1])
    assert (max_drawdown(x, 5.0) > 0.35) is True


def test_a_normal_drawdown_is_computed_normally():
    x = np.array([0.5, -0.5, 0.0])
    # 1.5 then 0.75: peak 1.5, trough 0.75 -> 50%
    assert max_drawdown(x, 1.0) == pytest.approx(0.5)


def test_the_search_never_returns_a_size_that_breaches_the_budget():
    rng = np.random.default_rng(4)
    for seed_shift in range(6):
        x = rng.normal(0.02, 0.35, 800) - seed_shift * 0.01
        q = q_for_drawdown(x, 0.35)
        assert max_drawdown(x, q) <= 0.35 + 1e-6, "returned an over-budget size"


def test_the_search_is_not_pinned_to_its_upper_bound():
    """The symptom that exposed the bug: q == hi for every input."""
    rng = np.random.default_rng(11)
    x = rng.normal(0.01, 0.4, 1000)
    q = q_for_drawdown(x, 0.35)
    assert 0.0 < q < ruin_q(x) * 0.999


def test_bigger_budget_buys_a_bigger_size():
    rng = np.random.default_rng(5)
    x = rng.normal(0.02, 0.3, 900)
    qs = [q_for_drawdown(x, t) for t in (0.10, 0.20, 0.35, 0.50)]
    assert qs == sorted(qs), f"size did not increase with the budget: {qs}"


def test_ruin_q_is_set_by_the_worst_single_day():
    assert ruin_q(np.array([0.3, -0.25, 0.1])) == pytest.approx(4.0)
    assert ruin_q(np.array([0.3, 0.25])) == float("inf")


def test_a_series_that_never_loses_is_bounded_rather_than_infinite():
    q = q_for_drawdown(np.array([0.01] * 500), 0.35)
    assert np.isfinite(q) and q > 0


def test_empty_and_all_nan_inputs_return_zero_size():
    assert q_for_drawdown(np.array([]), 0.35) == 0.0
    assert q_for_drawdown(np.array([np.nan, np.nan]), 0.35) == 0.0


def test_a_single_catastrophic_day_caps_the_size():
    """One -80% day must bound q at 1.25 however good the rest looks."""
    x = np.concatenate([np.full(500, 0.05), [-0.8]])
    q = q_for_drawdown(x, 0.35)
    assert q < 1.25
    assert max_drawdown(x, q) <= 0.35 + 1e-6
