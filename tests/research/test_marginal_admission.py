"""ADMIT ON MARGINAL CONTRIBUTION, NOT STANDALONE MERIT -- 99 statements, zero tests until now.

The live cohort is three signals -- BNB, ETH and BTC basis -- pairwise correlated near 1.0, so it
is ONE bet wearing three tickers. That is not a tuning miss; it is what standalone screening
produces by construction, because a fixed Sharpe bar cannot tell a diversifier from a duplicate.
This module is the gate that `cohort_independence`'s measurement always implied and never had.

THE TWO CLAIMS WORTH TESTING, both of which a standalone gate gets backwards:

  1. A WEAK UNCORRELATED SIGNAL BEATS A STRONG CORRELATED ONE. Sharpe 0.05 at rho=0 is admissible
     against a book at 0.40; Sharpe 0.35 at rho=0.95 is not, because 0.35 < 0.95*0.40. Both
     directions are asserted, because a gate that only rejected duplicates and never admitted a
     weak diversifier would be a stricter version of the bug rather than a fix.
  2. NEGATIVE CORRELATION IS WORTH MORE THAN POSITIVE SHARPE. At rho<0 the IR numerator grows, so
     a mediocre hedge beats a strong duplicate. Nothing in the standalone gate can express that.

And the discipline that makes it safe: FAIL CLOSED. Insufficient overlap, degenerate correlation,
non-finite inputs and a non-positive incumbent Sharpe all return admitted=False WITH A REASON. A
gate that counts "could not measure" as "passed" is exactly how a book ends up concentrated in the
one trade it already had, so each of those paths is asserted separately.
"""

from __future__ import annotations

import numpy as np
import pytest

from libs.research import marginal_admission as M

_PPY = 365.0


def _series(n: int, mean: float, sd: float, seed: int) -> np.ndarray:
    """A return series with an approximately known annualised Sharpe."""
    rng = np.random.default_rng(seed)
    x = rng.normal(0.0, sd, n)
    return x - x.mean() + mean


def _with_rho(base: np.ndarray, rho: float, mean: float, sd: float,
              seed: int) -> np.ndarray:
    """A series correlated `rho` with `base`, at a chosen mean and sd."""
    rng = np.random.default_rng(seed)
    e = rng.normal(0.0, 1.0, len(base))
    b = (base - base.mean()) / base.std()
    e = (e - e.mean()) / e.std()
    mix = rho * b + np.sqrt(max(0.0, 1.0 - rho * rho)) * e
    mix = (mix - mix.mean()) / mix.std()
    return mix * sd + mean


# ------------------------------------------------------------------ the Fisher bound

def test_the_bound_is_always_at_or_above_the_point_estimate() -> None:
    """The gate uses the UPPER bound, so a correlation the desk cannot yet pin down must read as
    HIGH (duplicate-like). Understating correlation concentrates the book; overstating costs a
    slot that later evidence reclaims."""
    for rho in (-0.9, -0.2, 0.0, 0.3, 0.85):
        for n in (10, 60, 500, 5_000):
            assert M._fisher_upper(rho, n) >= rho - 1e-12


def test_the_bound_tightens_toward_the_estimate_as_n_grows() -> None:
    wide = M._fisher_upper(0.3, 20)
    tight = M._fisher_upper(0.3, 5_000)
    assert wide > tight > 0.29


def test_at_tiny_n_the_bound_is_1_and_nothing_is_admitted() -> None:
    """The honest answer, not an obstacle to route around: at n<=3 you cannot tell a diversifier
    from a duplicate, and this desk's repeated failure has been treating 'not yet measurable' as
    'fine'."""
    assert M._fisher_upper(0.0, 3) == 1.0
    assert M._fisher_upper(-0.9, 2) == 1.0


def test_the_bound_never_exceeds_1_even_at_a_degenerate_correlation() -> None:
    assert M._fisher_upper(1.0, 10_000) <= 1.0
    assert M._fisher_upper(0.99999999, 10_000) <= 1.0
    assert M._fisher_upper(1.0, 10_000) > 0.999, (
        "a perfect correlation must still bound near 1 -- clipping must not create headroom")


# ------------------------------------------------------------------ the incumbent composite

def test_the_composite_is_equal_RISK_weighted_not_equal_dollar_weighted() -> None:
    """Using raw columns lets a high-variance incumbent dominate, which biases rho DOWNWARD --
    exactly the direction that wrongly admits duplicates."""
    n = 400
    rng = np.random.default_rng(1)
    quiet = rng.normal(0, 0.001, n)
    loud = rng.normal(0, 0.100, n)
    port = M._portfolio_series(np.column_stack([quiet, loud]))
    z_quiet = (quiet - quiet.mean()) / quiet.std()
    z_loud = (loud - loud.mean()) / loud.std()
    c_quiet = abs(np.corrcoef(port, z_quiet)[0, 1])
    c_loud = abs(np.corrcoef(port, z_loud)[0, 1])
    assert abs(c_quiet - c_loud) < 0.15, (
        "the loud column dominated the composite; rho to a candidate would be biased down")


def test_a_single_incumbent_column_is_accepted_as_1d() -> None:
    x = _series(300, 0.001, 0.01, 3)
    assert M._portfolio_series(x).shape == (300,)


def test_n_eff_matches_the_equicorrelation_formula_and_floors_at_one() -> None:
    """Same formula as `cohort_independence.effective_bets`, restated locally so this gate has no
    import cycle -- so it has to agree with it."""
    assert M._n_eff(101, 0.159) == pytest.approx(101 / (1 + 100 * 0.159), rel=1e-9)
    assert M._n_eff(3, 1.0) == 1.0, "three perfectly correlated signals are ONE bet"
    assert M._n_eff(0, 0.5) == 0.0
    assert M._n_eff(5, 0.0) == pytest.approx(5.0)


def test_mean_pairwise_is_zero_for_a_single_column() -> None:
    assert M._mean_pairwise(np.zeros((100, 1))) == 0.0
    assert M._mean_pairwise(np.zeros(100)) == 0.0


# ------------------------------------------------------------------ the headline inversion

def test_a_WEAK_UNCORRELATED_candidate_is_ADMITTED() -> None:
    """The half a stricter standalone gate would still get wrong. If only rejection worked, this
    module would be a tighter version of the bug rather than a fix."""
    n = 4_000
    rng = np.random.default_rng(21)
    inc = np.column_stack([rng.normal(0.0012, 0.01, n) for _ in range(3)])
    port = M._portfolio_series(inc)
    cand = _with_rho(port, 0.0, mean=0.0009, sd=0.010, seed=77)
    a = M.evaluate(cand, inc, periods_per_year=_PPY)
    assert a.admitted, a.reason
    assert a.orthogonal_ir > 0 and a.gain >= M.MIN_GAIN
    assert a.portfolio_sharpe_after > a.portfolio_sharpe


def test_a_STRONG_CORRELATED_candidate_is_REJECTED_as_the_book_it_already_owns() -> None:
    """It is worse than useless: it consumes slots, multiplicity budget and capital to re-buy an
    exposure already held."""
    n = 4_000
    rng = np.random.default_rng(22)
    base = rng.normal(0.0012, 0.01, n)
    inc = np.column_stack([base + rng.normal(0, 0.0005, n) for _ in range(3)])
    port = M._portfolio_series(inc)
    cand = _with_rho(port, 0.97, mean=0.0011, sd=0.010, seed=78)
    a = M.evaluate(cand, inc, periods_per_year=_PPY)
    assert not a.admitted
    assert a.rho_used > 0.9
    assert "already owns" in a.reason or "indistinguishable" in a.reason


def test_the_hurdle_is_rho_times_portfolio_sharpe_and_is_reported() -> None:
    """NOT a fixed bar. The whole inversion lives in this one product, so it is kept on the record
    rather than recomputed by whoever is arguing with the verdict."""
    n = 2_000
    rng = np.random.default_rng(23)
    inc = np.column_stack([rng.normal(0.001, 0.01, n) for _ in range(2)])
    a = M.evaluate(rng.normal(0.001, 0.01, n), inc, periods_per_year=_PPY)
    assert a.hurdle == pytest.approx(a.rho_used * a.portfolio_sharpe)


def test_NEGATIVE_correlation_beats_a_positive_duplicate() -> None:
    """At rho<0 the IR numerator GROWS, so a hedge with mediocre standalone performance can beat a
    strong duplicate. Nothing in a standalone gate can express that -- it is a structural blind
    spot rather than a tuning miss."""
    n = 4_000
    rng = np.random.default_rng(24)
    inc = np.column_stack([rng.normal(0.0012, 0.01, n) for _ in range(3)])
    port = M._portfolio_series(inc)
    hedge = M.evaluate(_with_rho(port, -0.6, mean=0.0004, sd=0.010, seed=91), inc,
                       periods_per_year=_PPY)
    dup = M.evaluate(_with_rho(port, 0.9, mean=0.0012, sd=0.010, seed=92), inc,
                     periods_per_year=_PPY)
    assert hedge.candidate_sharpe < dup.candidate_sharpe, "the hedge is the WEAKER one standalone"
    assert hedge.orthogonal_ir > dup.orthogonal_ir, "and must still contribute more"


def test_the_cost_of_an_admission_is_visible_at_the_moment_it_is_taken() -> None:
    """N_eff before and after. A gate that admitted without reporting the concentration it caused
    would leave the measurement to an audit weeks later."""
    n = 3_000
    rng = np.random.default_rng(25)
    inc = np.column_stack([rng.normal(0.0012, 0.01, n) for _ in range(3)])
    a = M.evaluate(rng.normal(0.001, 0.01, n), inc, periods_per_year=_PPY)
    assert a.n_eff_before >= 1.0 and a.n_eff_after >= 1.0
    assert a.n_eff_after > a.n_eff_before, "a fourth signal must widen the cohort at all"


# ------------------------------------------------------------------ fail closed

def test_too_little_overlap_is_REJECTED_rather_than_waved_through() -> None:
    n = M.MIN_OVERLAP - 1
    rng = np.random.default_rng(31)
    a = M.evaluate(rng.normal(0.01, 0.01, n),
                   np.column_stack([rng.normal(0.001, 0.01, n) for _ in range(2)]),
                   periods_per_year=_PPY)
    assert not a.admitted and "not yet measurable" in a.reason
    assert a.n_overlap == n


def test_a_non_finite_candidate_is_REJECTED() -> None:
    n = 300
    rng = np.random.default_rng(32)
    cand = rng.normal(0.001, 0.01, n)
    cand[10] = np.nan
    a = M.evaluate(cand, np.column_stack([rng.normal(0.001, 0.01, n) for _ in range(2)]))
    assert not a.admitted and "non-finite" in a.reason


def test_an_empty_candidate_is_REJECTED() -> None:
    a = M.evaluate(np.asarray([]), np.zeros((300, 2)))
    assert not a.admitted


def test_a_zero_variance_candidate_is_REJECTED_rather_than_admitted_on_NaN() -> None:
    """`np.corrcoef` returns NaN here. A NaN silently compared against a hurdle is False for
    every operator, so an unguarded version would take the reject path by accident and the next
    refactor would flip it."""
    n = 300
    rng = np.random.default_rng(33)
    inc = np.column_stack([rng.normal(0.001, 0.01, n) for _ in range(2)])
    a = M.evaluate(np.zeros(n), inc, periods_per_year=_PPY)
    assert not a.admitted
    assert "undefined" in a.reason or "does not clear" in a.reason


def test_a_non_positive_incumbent_sharpe_FAILS_CLOSED() -> None:
    """A book with no measured edge cannot set a hurdle. Falling back to standalone merit here
    would quietly restore the very gate this module exists to replace."""
    n = 1_000
    rng = np.random.default_rng(34)
    losing = np.column_stack([rng.normal(-0.002, 0.01, n) for _ in range(3)])
    a = M.evaluate(rng.normal(0.003, 0.01, n), losing, periods_per_year=_PPY)
    assert not a.admitted
    assert "fix the book" in a.reason


def test_a_gain_inside_estimation_noise_is_REJECTED() -> None:
    """A gain of +0.001 Sharpe is indistinguishable from zero, and an endless stream of
    near-duplicates each claiming a sliver of improvement is the multiplicity problem re-entering
    through the portfolio door."""
    n = 3_000
    rng = np.random.default_rng(35)
    inc = np.column_stack([rng.normal(0.0015, 0.01, n) for _ in range(3)])
    port = M._portfolio_series(inc)
    # Clears the hurdle (positive orthogonal IR) but adds far less than the min_gain demanded --
    # the two rejections are DIFFERENT and must not be confused: one says "this is the book you
    # own", the other says "this is real but too small to measure".
    cand = _with_rho(port, 0.0, mean=0.0005, sd=0.010, seed=99)
    a = M.evaluate(cand, inc, periods_per_year=_PPY, min_gain=5.0)
    assert a.orthogonal_ir > 0, "precondition: this candidate must CLEAR the correlation hurdle"
    assert not a.admitted and "estimation noise" in a.reason


# ------------------------------------------------------------------ the empty book

def test_the_FIRST_signal_is_judged_on_standalone_merit_because_nothing_can_be_duplicated() -> None:
    n = 500
    rng = np.random.default_rng(41)
    a = M.evaluate(rng.normal(0.002, 0.01, n), np.empty((0, 0)), periods_per_year=_PPY)
    assert a.admitted and "first signal" in a.reason
    assert a.n_eff_before == 0.0 and a.n_eff_after == 1.0


def test_the_first_signal_still_has_to_be_positive() -> None:
    n = 500
    rng = np.random.default_rng(42)
    a = M.evaluate(rng.normal(-0.002, 0.01, n), np.empty((0, 0)), periods_per_year=_PPY)
    assert not a.admitted and "non-positive" in a.reason
    assert a.n_eff_after == 0.0


# ------------------------------------------------------------------ the record

def test_every_verdict_is_auditable_and_serialisable() -> None:
    """The decision is a portfolio-construction claim someone will challenge. Every intermediate
    quantity is kept so the challenge is against numbers rather than against a boolean."""
    n = 1_000
    rng = np.random.default_rng(51)
    inc = np.column_stack([rng.normal(0.001, 0.01, n) for _ in range(3)])
    d = M.evaluate(rng.normal(0.001, 0.01, n), inc, periods_per_year=_PPY).to_dict()
    for k in ("admitted", "reason", "candidate_sharpe", "portfolio_sharpe", "rho_hat",
              "rho_used", "hurdle", "orthogonal_ir", "portfolio_sharpe_after", "gain",
              "n_overlap", "n_eff_before", "n_eff_after"):
        assert k in d, k
    assert isinstance(d["n_overlap"], int), "n_overlap is a COUNT and must not become a float"
    assert d["reason"], "no verdict may be issued without a stated reason"


def test_ragged_inputs_are_truncated_to_the_overlap_rather_than_padded() -> None:
    """Padding would align two different rulers. The overlap is reported so the caller can see how
    much of each series actually informed the decision."""
    rng = np.random.default_rng(52)
    a = M.evaluate(rng.normal(0.001, 0.01, 900),
                   np.column_stack([rng.normal(0.001, 0.01, 300) for _ in range(2)]),
                   periods_per_year=_PPY)
    assert a.n_overlap == 300
