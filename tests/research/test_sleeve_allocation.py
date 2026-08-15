"""Optimal-weight diversification, and the ways it manufactures a number that is not there.

The desk prices its own diversification with `k_eff = N/(1+(N-1)*rho_bar)`, which is exact under
EQUICORRELATION. The book is not equicorrelated -- seven of eleven discretionary rules share one
census class -- so the mean describes no pair in it. This module measures what optimal weights get
instead, and most of these tests are about the fact that the same arithmetic, run carelessly, is
the classic Markowitz error-maximizer.
"""

from __future__ import annotations

import numpy as np
import pytest

from libs.research.sleeve_allocation import (
    MIN_OBS_PER_SLEEVE,
    allocate,
    equicorrelation_sharpe,
    shrink_target,
    shrinkage_weight,
)


def _equicorr(n: int, rho: float) -> np.ndarray:
    c = np.full((n, n), float(rho))
    np.fill_diagonal(c, 1.0)
    return c


def _clustered(n_cluster: int, n_distinct: int, *, within: float, across: float) -> np.ndarray:
    """The desk's actual shape: a near-redundant cluster plus structurally unlike sleeves."""
    n = n_cluster + n_distinct
    c = np.full((n, n), float(across))
    c[:n_cluster, :n_cluster] = within
    np.fill_diagonal(c, 1.0)
    return c


# ------------------------------------------------------- the formula it must reduce to

def test_on_an_equicorrelated_book_it_reproduces_the_desks_own_number():
    """No free lunch where none exists. If every pair really does share one rho, optimal weights
    ARE equal weights and the two answers must agree."""
    n, rho, s = 8, 0.375, 0.48
    a = allocate([f"m{i}" for i in range(n)], np.full(n, s), _equicorr(n, rho), n_obs=400)
    assert a.usable
    assert a.optimal_sharpe == pytest.approx(equicorrelation_sharpe(s, n, rho), rel=0.02)
    assert a.uplift == pytest.approx(0.0, abs=0.02)


def test_equal_weights_are_recovered_on_a_symmetric_book():
    n = 6
    a = allocate([f"m{i}" for i in range(n)], np.full(n, 0.5), _equicorr(n, 0.3), n_obs=400)
    assert np.allclose(list(a.weights.values()), 1.0 / n, atol=1e-3)


# ------------------------------------------------------------- what it is actually for

def test_a_clustered_book_is_worth_more_than_its_mean_rho_says():
    """THE POINT. Seven sleeves at 0.85 with each other plus four unlike everything averages to a
    middling rho_bar that describes NO pair. Equal weights pay full freight for seven copies of
    one bet; optimal weights do not."""
    names = [f"cluster{i}" for i in range(7)] + [f"distinct{i}" for i in range(4)]
    corr = _clustered(7, 4, within=0.85, across=0.05)
    a = allocate(names, np.full(11, 0.48), corr, n_obs=600)
    assert a.usable
    assert a.optimal_sharpe > a.equicorrelation_sharpe * 1.15, (
        "optimal weighting found nothing in a book that is obviously clustered")


def test_the_redundant_cluster_is_down_weighted_per_member():
    names = [f"cluster{i}" for i in range(7)] + [f"distinct{i}" for i in range(4)]
    a = allocate(names, np.full(11, 0.48),
                 _clustered(7, 4, within=0.85, across=0.05), n_obs=600)
    per_cluster = np.mean([a.weights[n] for n in names[:7]])
    per_distinct = np.mean([a.weights[n] for n in names[7:]])
    assert per_distinct > per_cluster * 1.5, (
        "seven near-identical sleeves kept the same weight as four distinct ones")


def test_effective_bets_counts_the_cluster_as_roughly_one():
    a = allocate([f"c{i}" for i in range(7)] + [f"d{i}" for i in range(4)],
                 np.full(11, 0.48), _clustered(7, 4, within=0.95, across=0.0), n_obs=600)
    assert a.effective_bets is not None
    assert 3.0 < a.effective_bets < 7.0, (
        f"11 sleeves that are really ~5 bets reported {a.effective_bets:.2f}")


# --------------------------------------------------- the error-maximizer, refused

def test_it_refuses_to_invert_a_matrix_the_sample_cannot_support():
    """An inverted matrix on a short sample does not fail noisily -- it fails OPTIMISTICALLY,
    loading on whichever pair is most badly estimated, because an understated correlation is
    indistinguishable from real diversification. That is the worst direction for a number that
    sets leverage."""
    n = 11
    a = allocate([f"m{i}" for i in range(n)], np.full(n, 0.48),
                 _equicorr(n, 0.3), n_obs=MIN_OBS_PER_SLEEVE * n - 1)
    assert not a.usable
    assert a.optimal_sharpe is None
    assert "not a measurement" in a.why
    assert a.equicorrelation_sharpe > 0, "the honest fallback must still be reported"


def test_shrinkage_rises_as_the_sample_thins():
    # Measured above the MIN_SHRINKAGE floor, which flattens the curve at the long-sample end by
    # design -- the floor is asserted separately below.
    assert shrinkage_weight(400, 20) < shrinkage_weight(100, 20) < shrinkage_weight(20, 20)
    assert shrinkage_weight(10, 30) == pytest.approx(1.0, abs=0.1)


def test_shrinkage_never_reaches_zero():
    """There is no sample size at which a correlation from a non-stationary market is exact."""
    assert shrinkage_weight(10**9, 3) > 0.0


def test_the_shrink_target_is_equicorrelation_not_independence():
    """Shrinking toward the identity would assert the sleeves are INDEPENDENT -- the optimistic
    direction, and the exact claim under test. It must pull toward the conservative answer."""
    corr = _clustered(7, 4, within=0.85, across=0.05)
    t = shrink_target(corr)
    off = t[~np.eye(11, dtype=bool)]
    assert np.allclose(off, off[0]), "target is not equicorrelated"
    assert off[0] > 0.2, "target collapsed toward independence"


def test_shrinkage_pulls_the_answer_toward_the_conservative_one():
    names = [f"m{i}" for i in range(6)]
    corr = _clustered(4, 2, within=0.9, across=0.0)
    long_s = allocate(names, np.full(6, 0.5), corr, n_obs=2000)
    short_s = allocate(names, np.full(6, 0.5), corr, n_obs=60)
    assert long_s.usable and short_s.usable
    assert short_s.shrinkage > long_s.shrinkage
    assert short_s.optimal_sharpe < long_s.optimal_sharpe, (
        "a thinner sample produced a BOLDER claim")


def test_a_non_positive_definite_matrix_is_repaired_not_trusted():
    """Pairwise-complete estimation can produce a matrix that inverts to negative variances and
    prints a Sharpe of any size. It must be floored, not used as found."""
    c = np.array([[1.0, 0.9, -0.9], [0.9, 1.0, 0.9], [-0.9, 0.9, 1.0]])
    assert np.linalg.eigvalsh(c).min() < 0, "fixture is not actually non-PD"
    a = allocate(["a", "b", "c"], np.full(3, 0.5), c, n_obs=500)
    assert not a.usable, "an impossible covariance was accepted"
    assert a.optimal_sharpe is None
    assert "positive semi-definite" in a.why
    # The first version floored the eigenvalues and carried on, returning Sharpe 306 -- a
    # riskless-arbitrage claim built out of an estimation artifact.
    assert a.equicorrelation_sharpe > 0, "the honest fallback must survive the refusal"


def test_the_equicorrelation_number_is_always_reported_alongside():
    """The optimal figure must never SUBSTITUTE for the desk's existing answer -- the gap between
    them is the thing a reader needs to judge."""
    for n_obs in (30, 600):
        a = allocate([f"m{i}" for i in range(6)], np.full(6, 0.5),
                     _clustered(4, 2, within=0.9, across=0.0), n_obs=n_obs)
        assert a.equicorrelation_sharpe > 0


def test_the_uplift_is_labelled_in_sample():
    a = allocate([f"m{i}" for i in range(6)], np.full(6, 0.5),
                 _clustered(4, 2, within=0.9, across=0.0), n_obs=600)
    assert "IN-SAMPLE" in a.why or "in-sample" in a.why.lower()
