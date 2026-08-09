"""Selection concentrates correlation, and the test that matters is the NULL one.

A statistic that flags "the winners are all the same bet" is only worth having if it stays quiet
when they are not. test_the_null_is_calibrated is therefore the load-bearing test here: it runs
the statistic on cohorts with no common factor at all and asserts it fires at roughly its nominal
rate. A detector with an uncontrolled false-positive rate would push the desk to shrink a
perfectly diversified book.
"""
from __future__ import annotations

import numpy as np

from libs.research.cohort_independence import selection_amplification


def _factor_cohort(seed: int, *, mu_f: float, n: int = 51, t: int = 800):
    """A cohort with one common factor, heterogeneous loadings, and idiosyncratic noise.

    `mu_f` is what makes or breaks the whole thing. Column Sharpe is L*mu_f / sqrt(L^2 sf^2 + se^2),
    so at mu_f = 4e-4 the true Sharpe spans 0.013..0.036 while estimation noise on 800 bars is
    1/sqrt(800) = 0.035 -- selection reads almost pure noise and picks loadings at random. The
    factor has to actually PAY over the window for selection to load it, which is exactly the real
    mechanism: trend followers clustered in 2020-21 because the trend factor paid, not because
    they shared code.
    """
    rng = np.random.default_rng(seed)
    f = rng.normal(mu_f, 0.01, t)
    load = rng.uniform(0.0, 1.2, n)
    m = load * f[:, None] + rng.normal(0.0, 0.006, (t, n))
    return m, m.mean(0) / m.std(0, ddof=1)


def _independent_cohort(seed: int, *, n: int = 51, t: int = 800):
    rng = np.random.default_rng(seed)
    m = rng.normal(0.0, 0.01, (t, n))
    return m, m.mean(0) / m.std(0, ddof=1)


# ------------------------------------------------------------------------------- the null first

def test_the_null_is_calibrated() -> None:
    """THE TEST THAT MATTERS. No common factor anywhere, so selection cannot be concentrating one.
    The statistic must fire at about its nominal rate and no more -- an uncontrolled false-positive
    rate here would have the desk shrinking a genuinely diversified book."""
    fired = sum(selection_amplification(*_independent_cohort(1000 + s), k=11,
                                        n_null=300, seed=s).p_value <= 0.10
                for s in range(60))
    assert fired <= 12, f"fired {fired}/60 times at alpha=0.10 under a true null"


def test_an_independent_cohort_usually_reads_as_not_concentrating() -> None:
    e = selection_amplification(*_independent_cohort(7), k=11)
    assert e.p_value > 0.10
    assert "NOT CONCENTRATING" in e.verdict


# ------------------------------------------------------------------------------------- and power

def test_a_paying_common_factor_is_detected() -> None:
    """The finding this encodes: mean pairwise correlation 0.08 across the 2026-08-01 pool and
    0.85 among the candidates that actually won. The pool number was true and irrelevant."""
    m, sh = _factor_cohort(0, mu_f=3e-3)
    e = selection_amplification(m, sh, k=11)
    assert e.selected_corr > e.pool_corr
    assert e.p_value <= 0.01
    assert e.n_eff_selected < e.n_eff_pool
    assert "COLLAPSES" in e.verdict


def test_detection_is_reliable_not_lucky() -> None:
    hits = sum(selection_amplification(*_factor_cohort(5000 + s, mu_f=3e-3), k=11,
                                       n_null=300, seed=s).p_value <= 0.10
               for s in range(25))
    assert hits >= 22, f"only {hits}/25 paying-factor cohorts detected"


def test_a_factor_that_does_not_pay_is_not_flagged() -> None:
    """A common factor can be PRESENT without selection loading it. The pool is then highly
    correlated -- which `measure()` already reports -- but the winners are not a concentrated
    subset of it, and claiming otherwise would be a different, wrong finding."""
    m, sh = _factor_cohort(3, mu_f=0.0)
    assert selection_amplification(m, sh, k=11).p_value > 0.10


# ------------------------------------------------------------------ the ratio's domain, again

def test_amplification_is_nan_rather_than_absurd_when_the_baseline_is_noise() -> None:
    """An uncorrelated pool gives a random-subset baseline near zero, and dividing by it produced
    '-8.8x amplification' out of data with no structure whatsoever. Same domain error as the
    effective_bets upper clamp: a ratio needs a denominator that means something."""
    e = selection_amplification(*_independent_cohort(11), k=11)
    assert abs(e.random_subset_corr) < 0.02
    assert np.isnan(e.amplification)
    assert np.isfinite(e.p_value)          # the p-value still answers the question


def test_amplification_is_reported_when_the_baseline_is_real() -> None:
    m, sh = _factor_cohort(0, mu_f=3e-3)
    e = selection_amplification(m, sh, k=11)
    assert e.random_subset_corr >= 0.02
    assert e.amplification > 1.0


# ------------------------------------------------------------------------------- degenerate input

def test_selecting_the_whole_pool_is_unmeasurable_not_zero() -> None:
    """If k is the whole cohort there is no selection, so there is nothing to concentrate. A
    reported 1.0x here would read as evidence of safety."""
    m, sh = _independent_cohort(2, n=10)
    assert "UNMEASURABLE" in selection_amplification(m, sh, k=10).verdict


def test_a_tiny_pool_is_unmeasurable() -> None:
    m, sh = _independent_cohort(2, n=3)
    assert "UNMEASURABLE" in selection_amplification(m, sh, k=2).verdict


def test_mismatched_scores_are_rejected_not_guessed() -> None:
    m, _ = _independent_cohort(2, n=10)
    assert "UNMEASURABLE" in selection_amplification(m, np.zeros(4), k=3).verdict


def test_dead_columns_are_dropped_before_selection() -> None:
    """A flat column has undefined correlation with everything; keeping it would make the deadest
    candidate in the cohort read as the most diversifying."""
    m, sh = _independent_cohort(4, n=20)
    m = np.hstack([m, np.zeros((m.shape[0], 3))])
    e = selection_amplification(m, np.append(sh, [9.0, 9.0, 9.0]), k=8)
    assert e.n_pool == 20
