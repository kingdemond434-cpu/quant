"""Cohort independence, checked against correlations that are known by construction.

The headline this locks: at the benchmark's own correlation of 0.159, going from 101 candidates to
420 buys 6.0 -> 6.3 independent bets. That is the desk's measured "campaign WIDTH buys nothing"
result arrived at from a completely different direction, and it is the reason this file exists
rather than just reporting a correlation.
"""
from __future__ import annotations

import numpy as np

from libs.research.cohort_independence import (
    BENCHMARK_MEAN_CORR,
    BENCHMARK_N,
    effective_bets,
    measure,
)


def _cohort(rho: float, n: int, t: int = 1500, seed: int = 0) -> np.ndarray:
    """Equicorrelated panel: one common factor plus idiosyncratic noise."""
    rng = np.random.default_rng(seed)
    f = rng.normal(0.0, 1.0, (t, 1))
    idio = rng.normal(0.0, 1.0, (t, n))
    return np.sqrt(rho) * f + np.sqrt(max(1.0 - rho, 0.0)) * idio


def test_recovers_a_known_correlation():
    for rho in (0.0, 0.159, 0.6, 0.95):
        r = measure(_cohort(rho, 200, seed=1))
        assert abs(r.mean_corr - rho) < 0.03, f"rho={rho} measured {r.mean_corr}"


def test_identical_signals_are_one_bet():
    """The property that makes the number mean anything: copies are not hypotheses."""
    base = np.random.default_rng(2).normal(0.0, 1.0, (800, 1))
    assert measure(np.repeat(base, 50, axis=1)).n_eff < 1.5


def test_width_buys_almost_nothing_at_the_benchmark_correlation():
    """101 -> 420 candidates at rho=0.159 gains well under one independent bet. This is the
    external-benchmark form of the desk's own measured result that campaign width does not move
    power while campaign length does."""
    small = effective_bets(BENCHMARK_N, BENCHMARK_MEAN_CORR)
    big = effective_bets(420, BENCHMARK_MEAN_CORR)
    assert big - small < 1.0, f"{small:.2f} -> {big:.2f}"
    assert 5.0 < small < 7.0, "the published benchmark is ~6 independent bets, not ~101"


def test_more_candidates_never_reduces_independent_bets():
    prev = 0.0
    for n in (2, 10, 50, 101, 420, 2000):
        cur = effective_bets(n, BENCHMARK_MEAN_CORR)
        assert cur >= prev - 1e-9
        prev = cur


def test_effective_bets_is_floored_at_one():
    assert effective_bets(500, 1.0) >= 1.0
    assert effective_bets(1, 0.5) == 1.0


def test_dead_candidates_are_dropped_not_counted_as_diversifying():
    """A zero-variance column has undefined correlation with everything. Filling it with 0 would
    make a DEAD candidate read as the most diversifying member of the cohort."""
    live = _cohort(0.8, 10, seed=3)
    with_dead = np.column_stack([live, np.zeros((live.shape[0], 5))])
    r = measure(with_dead)
    assert r.n_series == 10, "dead columns must not enter the count"
    assert r.mean_corr > 0.7, "and must not dilute the measured correlation"


def test_noise_domination_is_reported_not_hidden():
    """With too few observations per series the mean off-diagonal correlation is biased upward.
    Reporting redundancy that is really estimation noise would send the desk to widen its
    mechanism space for no reason."""
    r = measure(_cohort(0.0, 200, t=100, seed=4))
    assert r.noise_dominated
    assert "NOISE-DOMINATED" in r.verdict


def test_degenerate_inputs_say_unmeasurable_rather_than_returning_a_number():
    for bad in (np.zeros((100, 1)), np.zeros((100, 0)), np.zeros((100, 8))):
        assert "UNMEASURABLE" in measure(bad).verdict


def test_verdict_does_not_punish_a_small_diverse_cohort():
    """The verdict keys on CORRELATION, not on N_eff, and this is the case that separates them.

    A tiny genuinely-distinct cohort has FEWER independent bets in absolute terms than a huge
    redundant one -- three orthogonal candidates are ~3 bets, a thousand candidates at rho=0.25
    are ~4. Ranking cohort quality by N_eff would therefore call the thousand-candidate parameter
    sweep the better research programme, which is precisely the width this desk already measured
    as buying nothing. Correlation is the scale-free statement and it is what the verdict uses.
    """
    small = measure(_cohort(0.02, 3, seed=5))
    huge = measure(_cohort(0.25, 1000, seed=6))
    assert small.n_eff < huge.n_eff, "premise: N_eff alone ranks the redundant sweep higher"
    assert "AT OR BETTER" in small.verdict
    assert "ABOVE BENCHMARK" in huge.verdict
