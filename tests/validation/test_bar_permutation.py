"""The permutation null, and the four ways it silently stops being a null.

A permutation test is only as good as the thing it permutes. Every failure here is silent: the
p-values keep coming out, they are just measured against a null that either still carries the
signal (under-shuffled) or is not the asset any more (over-shuffled). The tests that matter most
are test_total_log_return_is_preserved_exactly -- the property that makes asset drift score p~1 --
and test_the_intra_bar_triple_is_not_shuffled_apart, which is the one that produces bars no
exchange could emit.
"""
from __future__ import annotations

import numpy as np
import pytest

from libs.validation.bar_permutation import (
    MIN_PERMUTATIONS,
    Bars,
    invalid_bars,
    permutation_moment_report,
    permutation_pvalue,
    permute_bars,
    to_log_bars,
)


def _synthetic_ohlc(n: int = 400, *, seed: int = 11, drift: float = 0.0008):
    """A price path with realistic bar geometry: gaps, ranges, and closes inside the range."""
    rng = np.random.default_rng(seed)
    close = 100.0 * np.cumprod(1.0 + rng.normal(drift, 0.02, n))
    gap = rng.normal(0.0, 0.004, n)
    open_ = close * (1.0 + gap)
    span = np.abs(rng.normal(0.0, 0.012, n)) + 0.002
    high = np.maximum(open_, close) * (1.0 + span)
    low = np.minimum(open_, close) * (1.0 - span)
    return open_, high, low, close


def _bars(**kw) -> Bars:
    return to_log_bars(*_synthetic_ohlc(**kw))


# ------------------------------------------------------------------ the preserved quantities

def test_total_log_return_is_preserved_exactly():
    """THE property the whole module rests on. Close-to-close log return decomposes as
    gap + intra-bar close move, and shuffling preserves both SUMS, so the permuted series ends at
    exactly the same place. A candidate that is simply long a trending asset therefore scores the
    same on every permutation and gets p ~ 1 -- the asset drift is intact, only the timing is
    gone. If this drifts, the test stops discriminating skill from beta and starts rewarding it."""
    b = _bars(drift=0.002)
    rng = np.random.default_rng(0)
    real = b.close[-1] - b.close[0]
    for _ in range(25):
        p = permute_bars(b, rng=rng)
        assert p.close[-1] - p.close[0] == pytest.approx(real, abs=1e-9)


def test_the_multiset_of_intra_bar_moves_is_preserved():
    b = _bars()
    p = permute_bars(b, rng=np.random.default_rng(1))
    for real, perm in ((b.high - b.open, p.high - p.open),
                       (b.low - b.open, p.low - p.open),
                       (b.close - b.open, p.close - p.open)):
        assert np.allclose(np.sort(real[1:]), np.sort(perm[1:]))


def test_the_multiset_of_gaps_is_preserved():
    b = _bars()
    p = permute_bars(b, rng=np.random.default_rng(2))
    assert np.allclose(np.sort(b.open[1:] - b.close[:-1]),
                       np.sort(p.open[1:] - p.close[:-1]))


# --------------------------------------------------------------- the destroyed quantity

def test_serial_dependence_is_destroyed():
    """The point of the exercise. A series with strong momentum must come back with essentially
    no lag-1 autocorrelation, or the 'null' still contains the thing under test."""
    rng = np.random.default_rng(3)
    n = 1200
    r = np.zeros(n)
    for i in range(1, n):                      # AR(1): a signal any momentum rule can find
        r[i] = 0.35 * r[i - 1] + rng.normal(0, 0.015)
    close = 100.0 * np.cumprod(1.0 + r)
    open_ = np.concatenate([[close[0]], close[:-1]])
    high = np.maximum(open_, close) * 1.004
    low = np.minimum(open_, close) * 0.996
    b = to_log_bars(open_, high, low, close)
    real_ac = np.corrcoef(np.diff(b.close)[:-1], np.diff(b.close)[1:])[0, 1]
    assert real_ac > 0.20, "the fixture must actually contain serial dependence"
    perm_ac = [abs(np.corrcoef(np.diff(permute_bars(b, rng=rng).close)[:-1],
                               np.diff(permute_bars(b, rng=rng).close)[1:])[0, 1])
               for _ in range(30)]
    assert float(np.median(perm_ac)) < 0.10


# ------------------------------------------------------------------ the bar-geometry guarantee

def test_the_intra_bar_triple_is_not_shuffled_apart():
    """Shuffling high, low and close with three INDEPENDENT permutations would pair one bar's high
    with another's close and routinely emit close > high -- a series no exchange could produce and
    against which every high/low-touching rule scores nonsense. The guarantee is inherited: it
    holds on the permutation because it held on the input."""
    b = _bars()
    assert not invalid_bars(b).any(), "the fixture itself must have valid bars"
    rng = np.random.default_rng(4)
    for _ in range(30):
        assert not invalid_bars(permute_bars(b, rng=rng)).any()


def test_a_corrupt_input_bar_is_visible_rather_than_assumed_away():
    o, h, low, c = _synthetic_ohlc(n=50)
    h[7] = c[7] * 0.5                       # high below the close: impossible
    b = to_log_bars(o, h, low, c)
    bad = invalid_bars(b)
    assert bad[7] and bad.sum() == 1


def test_non_positive_prices_raise_rather_than_producing_silent_nans():
    o, h, low, c = _synthetic_ohlc(n=50)
    low[3] = 0.0
    with pytest.raises(ValueError, match="non-positive"):
        to_log_bars(o, h, low, c)


def test_mismatched_lengths_raise():
    with pytest.raises(ValueError):
        Bars(open=np.zeros(10), high=np.zeros(10), low=np.zeros(10), close=np.zeros(9))


# ------------------------------------------------------------------------- walk-forward variant

def test_a_frozen_prefix_is_copied_through_untouched():
    """The walk-forward variant: the rule is fitted on REAL in-sample data and only the
    out-of-sample stretch is scrambled. Permuting the prefix too would scramble the data the rule
    was fitted on and answer a different question."""
    b = _bars()
    p = permute_bars(b, rng=np.random.default_rng(5), start=300)
    for real, perm in ((b.open, p.open), (b.high, p.high), (b.low, p.low), (b.close, p.close)):
        assert np.array_equal(real[:300], perm[:300])
    assert not np.array_equal(b.close[300:], p.close[300:])


def test_the_frozen_variant_still_lands_on_the_real_endpoint():
    b = _bars(drift=0.0015)
    p = permute_bars(b, rng=np.random.default_rng(6), start=250)
    assert p.close[-1] == pytest.approx(b.close[-1], abs=1e-9)


def test_an_out_of_range_start_raises():
    b = _bars(n=100)
    with pytest.raises(ValueError):
        permute_bars(b, rng=np.random.default_rng(7), start=99)
    with pytest.raises(ValueError):
        permute_bars(b, rng=np.random.default_rng(7), start=-1)


def test_permutations_differ_from_each_other():
    b = _bars()
    rng = np.random.default_rng(8)
    a, c = permute_bars(b, rng=rng), permute_bars(b, rng=rng)
    assert not np.array_equal(a.close, c.close)


# --------------------------------------------------------------------------------- the p-value

def test_the_pvalue_can_never_be_zero():
    """(#{perm >= real} + 1) / (N + 1). Without the +1 a strategy that beat all 1,000 permutations
    reports p = 0 -- 'impossible under the null' from 1,000 draws, which no finite sample
    licenses. The floor is the honest resolution limit."""
    p = permutation_pvalue(99.0, np.zeros(1000))
    assert p == pytest.approx(1 / 1001) and p > 0


def test_a_worthless_strategy_lands_near_one():
    rng = np.random.default_rng(9)
    stats = rng.normal(0, 1, 2000)
    assert permutation_pvalue(float(np.percentile(stats, 5)), stats) > 0.9


def test_it_is_one_sided_on_the_upside():
    """A strategy that LOST badly must not be handed a small p-value for being unusual. Two-sided
    significance would promote reliably terrible rules, which are only useful inverted -- and
    inverting them is a second free parameter nobody counted."""
    rng = np.random.default_rng(10)
    stats = rng.normal(0, 1, 2000)
    assert permutation_pvalue(-4.0, stats) > 0.99


def test_too_few_permutations_raise_rather_than_reporting_a_coarse_pvalue():
    """At 50 permutations the smallest attainable p-value is 1/51 = 0.0196, so a 1% threshold can
    never be met and 'not significant' would be an artifact of the draw count."""
    with pytest.raises(ValueError, match="permutations"):
        permutation_pvalue(1.0, np.zeros(MIN_PERMUTATIONS - 1))


def test_unusable_permutation_stats_shrink_the_denominator_rather_than_counting_as_losses():
    """A permuted run that produced no trades has no Sharpe. Scoring it as a loss for the null
    inflates significance in exactly the direction the researcher wants."""
    stats = np.concatenate([np.zeros(400), np.full(200, np.nan)])
    assert permutation_pvalue(1.0, stats) == pytest.approx(1 / 401)


def test_a_non_finite_real_statistic_is_not_significant():
    assert permutation_pvalue(float("nan"), np.zeros(500)) == 1.0


# ---------------------------------------------------------------- honest moment reporting

def test_the_report_says_drift_is_exact_and_measures_variance_rather_than_claiming_it():
    """The source asserts the permutation 'preserves the statistical moments'. Drift yes, exactly.
    Close-to-close variance no -- real gaps and intra-bar closes are correlated and shuffling them
    independently drops the covariance term. Reporting the ratio beats asserting a moment."""
    b = _bars()
    rng = np.random.default_rng(12)
    perms = [permute_bars(b, rng=rng) for _ in range(40)]
    rep = permutation_moment_report(b, perms)
    assert rep["drift_preserved_exactly"] is True
    assert rep["variance_ratio_median"] is not None
    assert abs(float(rep["median_permuted_lag1_autocorr"])) < 0.15
