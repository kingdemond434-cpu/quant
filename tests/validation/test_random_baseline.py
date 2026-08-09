"""The monkey test, and the one design choice that decides whether it means anything.

Every failure here is silent. An unmatched monkey still produces a beat rate, it is just a beat
rate on a different question -- "does this rule beat a coin flip that was in the market a
different amount", which a leveraged buy-and-hold wins trivially. The tests that matter are
test_a_buy_and_hold_rule_does_not_beat_its_own_monkeys and
test_exposure_is_matched_exactly_not_in_expectation.
"""
from __future__ import annotations

import numpy as np
import pytest

from libs.validation.random_baseline import (
    BEAT_RATE_TARGET,
    MIN_BASELINES,
    matched_random_positions,
    monkey_test,
    partition_return,
)


def _market(n=2000, *, seed=1, drift=0.0, sigma=0.02):
    return np.random.default_rng(seed).normal(drift, sigma, n)


# ------------------------------------------------------------------ the partition is an identity

def test_the_partition_is_exact_not_approximate():
    """mean(p*r) == mean(p)*mean(r) + cov(p,r) is the definition of covariance, so the residual
    must be floating-point dust on ANY input. If this ever fails, the decomposition is not the
    identity it claims to be and every share it reports is a different number's share."""
    rng = np.random.default_rng(3)
    for seed in range(8):
        r = _market(1500, seed=seed, drift=0.001)
        p = rng.choice([-1.0, 0.0, 1.0], size=1500)
        rep = partition_return(p, r)
        assert abs(rep["identity_residual"]) < 1e-15
        assert rep["total_per_bar"] == pytest.approx(
            rep["exposure_per_bar"] + rep["timing_per_bar"], abs=1e-15)


def test_a_pure_buy_and_hold_is_all_exposure_and_no_timing():
    """The case the partition exists to name. A constant position cannot covary with anything, so
    timing is exactly zero and the entire return is exposure."""
    r = _market(drift=0.001)
    rep = partition_return(np.ones(len(r)), r)
    assert rep["timing_per_bar"] == pytest.approx(0.0, abs=1e-18)
    assert rep["exposure_share"] == pytest.approx(1.0)


def test_perfect_foresight_is_almost_entirely_timing():
    """The opposite pole: a rule that knows tomorrow's sign has essentially no exposure component,
    because its average position is near zero while its returns are all positive."""
    r = _market(drift=0.0)
    rep = partition_return(np.sign(r), r)
    assert abs(rep["exposure_share"]) < 0.05
    assert rep["timing_share"] > 0.95


def test_a_cancelling_total_reports_undefined_shares_rather_than_huge_ones():
    """When total is ~0 the shares are a real component over a cancelling denominator, which
    produces enormous meaningless percentages that read as findings."""
    r = _market(drift=0.0, seed=9)
    p = np.zeros(len(r))
    rep = partition_return(p, r)
    assert np.isnan(rep["exposure_share"]) and np.isnan(rep["timing_share"])


def test_misaligned_inputs_raise_rather_than_broadcasting():
    with pytest.raises(ValueError):
        partition_return(np.zeros(100), np.zeros(99))


# ------------------------------------------------------------- exposure matching is the design

def test_exposure_is_matched_exactly_not_in_expectation():
    """THE DESIGN CHOICE. A Bernoulli monkey drawn at p=0.85 over 2,400 bars still varies by a
    couple of percent of time-in-market, and on an asset that tripled that slack is worth more
    than most timing effects under test. Permuting the real series matches the long count, the
    short count and the flat count EXACTLY, so only WHEN can differ."""
    rng = np.random.default_rng(4)
    p = np.concatenate([np.ones(1700), np.full(200, -1.0), np.zeros(100)])
    for _ in range(30):
        m = matched_random_positions(p, rng=rng)
        assert np.array_equal(np.sort(m), np.sort(p))


def test_the_monkey_is_actually_shuffled():
    rng = np.random.default_rng(5)
    p = np.random.default_rng(6).choice([-1.0, 0.0, 1.0], size=800)
    assert not np.array_equal(matched_random_positions(p, rng=rng), p)


# ------------------------------------------------------------------------ discrimination

def test_a_buy_and_hold_rule_does_not_beat_its_own_monkeys():
    """THE TEST THAT MATTERS. Every permutation of a constant position is the same constant
    position, so the monkeys score IDENTICALLY and the rule cannot beat them. A rule that is
    simply long a trending asset must not read as timing skill, and this is the mechanism that
    prevents it."""
    r = _market(drift=0.0015)
    rep = monkey_test(np.ones(len(r)), r, rng=np.random.default_rng(7), n_baselines=300)
    assert rep["beat_rate"] == 0.0
    assert not rep["clears_target"]
    assert "NO TIMING EDGE" in rep["reading"]


def test_a_mostly_long_rule_on_a_bull_market_is_not_credited_for_exposure():
    """The subtler version, and the one an UNMATCHED monkey would get wrong. This rule is long 85%
    of the time on a strongly trending asset with position choices unrelated to returns. It makes
    plenty of money and has no timing skill whatsoever."""
    rng = np.random.default_rng(8)
    r = _market(2500, seed=8, drift=0.002)
    p = (rng.random(len(r)) < 0.85).astype("float64")
    rep = monkey_test(p, r, rng=np.random.default_rng(9), n_baselines=400)
    assert rep["real_statistic"] > 0, (
        "the rule must actually be profitable, else this proves nothing")
    assert rep["beat_rate"] < BEAT_RATE_TARGET


def test_real_timing_skill_beats_the_monkeys():
    """The power check. A rule with genuine (noisy) foresight must clear the target, or the test
    rejects everything and is useless."""
    rng = np.random.default_rng(10)
    r = _market(2000, seed=10, drift=0.0)
    noisy = np.sign(r + rng.normal(0, 0.02, len(r)))       # ~50/50 correct-ish, real signal
    rep = monkey_test(noisy, r, rng=np.random.default_rng(11), n_baselines=400)
    assert rep["beat_rate"] >= BEAT_RATE_TARGET
    assert "BEATS RANDOM" in rep["reading"]


def test_the_beat_rate_and_the_pvalue_are_the_same_number_seen_twice():
    """Both are reported so neither reader has to translate. Pinning the identity stops them
    drifting into two different statistics with one label each."""
    rng = np.random.default_rng(12)
    r = _market(1200, seed=12, drift=0.0005)
    p = rng.choice([-1.0, 1.0], size=len(r))
    rep = monkey_test(p, r, rng=np.random.default_rng(13), n_baselines=500)
    n = rep["n_baselines"]
    assert rep["p_value"] == pytest.approx((1 - rep["beat_rate"]) * n / (n + 1) + 1 / (n + 1),
                                           abs=1e-9)


def test_too_few_baselines_raise_rather_than_reporting_a_coarse_rate():
    r = _market(500)
    with pytest.raises(ValueError, match="MIN_BASELINES"):
        monkey_test(np.ones(len(r)), r, rng=np.random.default_rng(14),
                    n_baselines=MIN_BASELINES - 1)


def test_misaligned_inputs_raise():
    with pytest.raises(ValueError):
        monkey_test(np.zeros(100), np.zeros(99), rng=np.random.default_rng(15), n_baselines=300)


def test_a_flat_rule_is_unmeasurable_rather_than_scored():
    """A rule that never takes a position has no Sharpe. Reporting a beat rate for it would be
    scoring the absence of a strategy."""
    r = _market(1000)
    rep = monkey_test(np.zeros(len(r)), r, rng=np.random.default_rng(16), n_baselines=300)
    assert rep["beat_rate"] is None or rep["real_statistic"] is None
