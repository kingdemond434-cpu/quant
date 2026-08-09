"""The concentration measurement must not be a second implementation of the concentration gate.

`_equal_weight_neff` exists purely so 20,475 subsets can be priced as submatrix means instead of
20,475 quadratic forms. That is only legitimate if it is the SAME number
`libs.portfolio.concentration.effective_positions` returns -- otherwise the enumeration reports a
distribution of a quantity the desk's gate does not use, which is the quietest possible way to be
wrong. These tests pin the identity and the clamps.
"""

from __future__ import annotations

import math

import numpy as np
from scripts.measure_live_book_concentration import _equal_weight_neff, _pairwise

from libs.portfolio.concentration import effective_positions
from libs.research.cohort_independence import effective_bets


def _equicorr(n: int, rho: float) -> np.ndarray:
    c = np.full((n, n), float(rho))
    np.fill_diagonal(c, 1.0)
    return c


def test_submatrix_mean_matches_effective_positions() -> None:
    rng = np.random.default_rng(7)
    x = rng.standard_normal((400, 8))
    corr = np.corrcoef(x, rowvar=False)
    w = np.full(4, 0.25)
    for idx in ((0, 1, 2, 3), (1, 3, 5, 7), (4, 5, 6, 7)):
        sub = corr[np.ix_(idx, idx)]
        assert math.isclose(_equal_weight_neff(corr, idx), float(effective_positions(w, sub)),
                            rel_tol=1e-12)


def test_agrees_with_the_equicorrelation_closed_form() -> None:
    """At equicorrelation the quadratic form and N/(1+(N-1)rho) must be the same number."""
    for rho in (0.1, 0.638, 0.6821, 0.9):
        c = _equicorr(6, rho)
        assert math.isclose(_equal_weight_neff(c, (0, 1, 2, 3)), effective_bets(4, rho),
                            rel_tol=1e-12)


def test_identical_exposures_are_one_bet() -> None:
    assert math.isclose(_equal_weight_neff(_equicorr(4, 1.0), (0, 1, 2, 3)), 1.0, rel_tol=1e-12)


def test_clamped_at_the_position_count() -> None:
    """Negative off-diagonals must not manufacture more bets than there are names -- L0020."""
    c = _equicorr(4, -0.3)
    assert _equal_weight_neff(c, (0, 1, 2, 3)) <= 4.0 + 1e-12


def test_pairwise_returns_the_upper_triangle_only() -> None:
    c = _equicorr(5, 0.5)
    p = _pairwise(c)
    assert p.size == 10
    assert np.allclose(p, 0.5)
