"""Tests for the breadth-aware concentration limit.

The load-bearing ones are the two reductions of N_eff, the UNMEASURABLE block on every bad
correlation input, and the live-book test -- which asserts that the book currently trading FAILS,
because a threshold picked to pass whatever is running is not a threshold.
"""

from __future__ import annotations

from itertools import pairwise

import numpy as np
import pytest
from tests.portfolio.conftest import constant_correlation

from libs.portfolio.concentration import (
    BRAIN_MAX_WEIGHT,
    LIVE_BOOK_MEAN_CORR,
    LIVE_BOOK_POSITIONS,
    MIN_EFFECTIVE_POSITIONS,
    concentration_verdict,
    effective_positions,
    max_weight_for,
)
from libs.portfolio.diversification import effective_bets as correlation_blind_bets


def _eye(n: int) -> np.ndarray:
    return np.eye(n, dtype="float64")


# --------------------------------------------------------------------------------------------
# max_weight_for: never below the floor, never unsatisfiable, converges on BRAIN at n >= 13
# --------------------------------------------------------------------------------------------


@pytest.mark.parametrize("n", list(range(1, 60)))
def test_cap_is_never_unsatisfiable(n: int) -> None:
    """cap * n >= 1 at every width: an equal-weight book of any size always has a solution."""
    cap = max_weight_for(n)
    assert cap * n >= 1.0 - 1e-12, f"cap {cap} at n={n} has an empty feasible set"


@pytest.mark.parametrize("n", list(range(1, 60)))
def test_cap_is_never_below_the_floor(n: int) -> None:
    assert max_weight_for(n) >= BRAIN_MAX_WEIGHT


def test_cap_auto_tightens_monotonically() -> None:
    caps = [max_weight_for(n) for n in range(1, 60)]
    assert all(b <= a + 1e-15 for a, b in pairwise(caps))


def test_cap_converges_to_brain_at_thirteen_names() -> None:
    """13 is the same 13 a fixed 0.08 cap needs before its feasible set is non-empty."""
    assert max_weight_for(12) == pytest.approx(1.0 / 12)
    assert max_weight_for(12) > BRAIN_MAX_WEIGHT
    for n in range(13, 60):
        assert max_weight_for(n) == pytest.approx(BRAIN_MAX_WEIGHT)


def test_cap_at_the_live_book_is_exactly_one_quarter() -> None:
    """The desk's 0.25 is not looseness -- it is 1/4, the tightest satisfiable cap at four names."""
    assert max_weight_for(LIVE_BOOK_POSITIONS) == pytest.approx(0.25)


def test_cap_degenerate_widths_do_not_produce_an_impossible_cap() -> None:
    for n in (-5, 0, 1):
        assert max_weight_for(n) == pytest.approx(1.0)
    # A nonsensical floor must not silently become "no floor" nor make the cap unsatisfiable.
    assert max_weight_for(4, floor=float("nan")) == pytest.approx(0.25)
    assert max_weight_for(4, floor=-1.0) == pytest.approx(0.25)
    assert max_weight_for(20, floor=0.10) == pytest.approx(0.10)


# --------------------------------------------------------------------------------------------
# effective_positions: both reductions
# --------------------------------------------------------------------------------------------


@pytest.mark.parametrize("weights", [
    [0.25, 0.25, 0.25, 0.25],
    [0.7, 0.2, 0.05, 0.05],
    [0.5, 0.3, 0.2],
    [0.1] * 10,
    [0.4, 0.4, 0.1, 0.05, 0.05],
])
def test_identity_correlation_reduces_to_inverse_herfindahl(weights: list[float]) -> None:
    """C = I  ->  1 / sum(w^2), exactly the correlation-blind number already shipped."""
    w = np.asarray(weights, dtype="float64")
    expected = 1.0 / float(np.sum(w**2))
    assert effective_positions(w, _eye(w.size)) == pytest.approx(expected, rel=1e-12)
    # ...and that is precisely libs/portfolio/diversification.effective_bets, whose blindness to
    # correlation is the defect this module exists to expose.
    assert effective_positions(w, _eye(w.size)) == pytest.approx(
        correlation_blind_bets(w), rel=1e-12)


@pytest.mark.parametrize("n", [2, 3, 4, 7, 13, 29])
def test_all_ones_correlation_collapses_to_one_bet(n: int) -> None:
    """C = all-ones -> 1.0. Identical exposures are ONE bet however many tickers hold them."""
    w = np.full(n, 1.0 / n)
    assert effective_positions(w, np.ones((n, n))) == pytest.approx(1.0, abs=1e-12)


@pytest.mark.parametrize("n", [2, 5, 13, 29])
def test_perfectly_correlated_book_is_one_bet_at_any_weights(n: int) -> None:
    rng = np.random.default_rng(11)
    for _ in range(5):
        w = rng.random(n) + 0.01
        w = w / w.sum()
        assert effective_positions(w, np.ones((n, n))) == pytest.approx(1.0, abs=1e-9)


def test_equal_weights_under_identity_give_exactly_n() -> None:
    for n in (1, 4, 13, 29):
        assert effective_positions(np.full(n, 1.0 / n), _eye(n)) == pytest.approx(float(n))


def test_weights_are_normalised_not_rejected() -> None:
    """A caller passing raw notionals gets the same answer as one passing fractions."""
    raw = np.array([50.0, 50.0, 50.0, 50.0])
    frac = np.array([0.25, 0.25, 0.25, 0.25])
    c = constant_correlation(4, LIVE_BOOK_MEAN_CORR)
    assert effective_positions(raw, c) == pytest.approx(effective_positions(frac, c))


def test_negative_correlation_cannot_manufacture_more_bets_than_names() -> None:
    """Desk lesson L0020: 29 perps once reported 64.4 independent bets. Clamp to [1, n]."""
    c = constant_correlation(2, -0.9)
    n_eff = effective_positions([0.5, 0.5], c)
    assert n_eff == pytest.approx(2.0)
    assert 1.0 <= n_eff <= 2.0


def test_dust_positions_do_not_raise_the_upper_clamp() -> None:
    w = np.array([0.5, 0.5, 1e-18, 1e-18])
    assert effective_positions(w, _eye(4)) <= 2.0 + 1e-9


# --------------------------------------------------------------------------------------------
# UNMEASURABLE blocks on every bad correlation input -- the #1 defect class
# --------------------------------------------------------------------------------------------


def _bad_matrices() -> list[tuple[str, object]]:
    non_psd = np.array([[1.0, 0.99, -0.99], [0.99, 1.0, 0.99], [-0.99, 0.99, 1.0]])
    asym = np.array([[1.0, 0.6, 0.2], [0.1, 1.0, 0.3], [0.2, 0.3, 1.0]])
    cov = np.array([[0.04, 0.01, 0.0], [0.01, 0.09, 0.0], [0.0, 0.0, 0.16]])
    nan_m = constant_correlation(3, 0.5)
    nan_m[0, 1] = nan_m[1, 0] = float("nan")
    inf_m = constant_correlation(3, 0.5)
    inf_m[2, 2] = float("inf")
    return [
        ("absent", None),
        ("non-square", np.ones((3, 4))),
        ("one-dimensional", np.ones(3)),
        ("wrong size for the weights", constant_correlation(5, 0.5)),
        ("nan entry", nan_m),
        ("inf entry", inf_m),
        ("asymmetric", asym),
        ("covariance not correlation", cov),
        ("not positive semi-definite", non_psd),
    ]


@pytest.mark.parametrize("label,corr", _bad_matrices(), ids=[lbl for lbl, _ in _bad_matrices()])
def test_unmeasurable_blocks_and_never_reads_as_diversified(label: str, corr: object) -> None:
    w = [1 / 3, 1 / 3, 1 / 3]
    assert np.isnan(effective_positions(w, corr))  # type: ignore[arg-type]
    v = concentration_verdict(w, corr)  # type: ignore[arg-type]
    assert v.measurable is False, label
    assert v.passes is False, label
    assert v.binding == ("unmeasurable",), label
    assert "UNMEASURABLE" in v.verdict and "BLOCKED" in v.verdict, label
    assert np.isnan(v.effective_positions), label


def test_unmeasurable_blocks_on_bad_weights() -> None:
    c = constant_correlation(3, 0.5)
    for weights in ([], [0.5, float("nan"), 0.5], [1.0, -1.0, 0.0]):
        v = concentration_verdict(weights, c if len(weights) == 3 else None)
        assert v.measurable is False
        assert v.passes is False
        assert v.binding == ("unmeasurable",)


def test_an_absent_matrix_is_not_quietly_treated_as_the_identity() -> None:
    """The tempting default would hand the live book 4.0 bets instead of 1.37 and pass it."""
    w = np.full(LIVE_BOOK_POSITIONS, 1.0 / LIVE_BOOK_POSITIONS)
    assert concentration_verdict(w, None).passes is False
    assert concentration_verdict(w, _eye(LIVE_BOOK_POSITIONS)).passes is True


# --------------------------------------------------------------------------------------------
# THE CURRENT LIVE BOOK
# --------------------------------------------------------------------------------------------


def test_the_current_live_book_is_reported_as_one_and_a_third_bets_and_fails() -> None:
    """4 equal-weight names at rho = 0.638 -- data/cashcarry_config.json "top": 4.

    Every assertion here is the honest answer, not a desirable one: the cap is satisfied exactly,
    the book is worth 1.37 effective positions, and it FAILS.
    """
    n = LIVE_BOOK_POSITIONS
    w = np.full(n, 1.0 / n)
    c = constant_correlation(n, LIVE_BOOK_MEAN_CORR)
    v = concentration_verdict(w, c)

    assert v.measurable is True
    assert v.n_positions == 4
    assert v.max_weight == pytest.approx(0.25)
    assert v.weight_cap == pytest.approx(0.25)
    assert v.cap_set_by_count is True
    # 4 / (1 + 3 * 0.638) = 1.3727
    assert v.effective_positions == pytest.approx(1.3727, abs=5e-4)
    assert v.equicorrelation_check == pytest.approx(v.effective_positions, rel=1e-9)

    assert v.passes is False
    assert v.binding == ("effective_positions",)
    assert "EFFECTIVE POSITIONS bound" in v.verdict
    assert "SATISFIED" in v.verdict  # the nominal cap passed and told you nothing
    assert "theatre" in v.verdict  # the cap is set by count at n=4


def test_the_threshold_does_not_quietly_pass_the_live_book() -> None:
    """Guards the calibration itself: any floor <= ~1.37 would have been chosen to pass."""
    n = LIVE_BOOK_POSITIONS
    live = effective_positions(np.full(n, 1.0 / n), constant_correlation(n, LIVE_BOOK_MEAN_CORR))
    assert live < MIN_EFFECTIVE_POSITIONS
    assert live < 1.4


def test_the_nominal_cap_is_theatre_at_brain_width() -> None:
    """13 names at exactly BRAIN's 0.08 each, at the desk's real correlation, is still ~1.5 bets."""
    n = 13
    w = np.full(n, 1.0 / n)
    c = constant_correlation(n, LIVE_BOOK_MEAN_CORR)
    v = concentration_verdict(w, c)
    assert v.weight_cap == pytest.approx(BRAIN_MAX_WEIGHT)
    assert v.max_weight <= v.weight_cap + 1e-9
    assert v.effective_positions == pytest.approx(1.5018, abs=5e-4)
    assert v.passes is False
    assert v.binding == ("effective_positions",)


def test_widening_the_book_cannot_clear_the_floor_at_the_live_correlation() -> None:
    """The equicorrelation ceiling is 1/rho = 1.567: no unhedged long perp book of any width."""
    ceiling = 1.0 / LIVE_BOOK_MEAN_CORR
    assert ceiling < MIN_EFFECTIVE_POSITIONS
    for n in (4, 13, 29, 200, 1000):
        w = np.full(n, 1.0 / n)
        n_eff = effective_positions(w, constant_correlation(n, LIVE_BOOK_MEAN_CORR))
        assert n_eff < ceiling
        assert n_eff < MIN_EFFECTIVE_POSITIONS


def test_removing_the_common_factor_is_the_remedy_the_verdict_points_at() -> None:
    """Same four names at the desk's measured RESIDUAL correlation (-0.0325) clear the floor."""
    n = LIVE_BOOK_POSITIONS
    w = np.full(n, 1.0 / n)
    v = concentration_verdict(w, constant_correlation(n, -0.0325))
    assert v.effective_positions == pytest.approx(4.0)  # upper-clamped: N_eff ~= N after demeaning
    assert v.passes is True
    assert v.binding == ()
    assert "PASS" in v.verdict


# --------------------------------------------------------------------------------------------
# which constraint bound
# --------------------------------------------------------------------------------------------


def test_weight_cap_binding_is_named_separately_from_breadth() -> None:
    w = np.array([0.55, 0.15, 0.15, 0.15])
    v = concentration_verdict(w, _eye(4), min_effective_positions=1.5)
    assert v.max_weight == pytest.approx(0.55)
    assert v.binding == ("max_weight",)
    assert v.passes is False
    assert "NOMINAL WEIGHT CAP bound" in v.verdict


def test_both_constraints_can_bind_at_once() -> None:
    w = np.array([0.55, 0.15, 0.15, 0.15])
    v = concentration_verdict(w, constant_correlation(4, 0.9))
    assert set(v.binding) == {"max_weight", "effective_positions"}
    assert v.passes is False
    assert "BOTH" in v.verdict


def test_a_genuinely_diversified_book_passes_and_names_nothing() -> None:
    n = 20
    v = concentration_verdict(np.full(n, 1.0 / n), constant_correlation(n, 0.05))
    assert v.passes is True
    assert v.binding == ()
    assert v.cap_set_by_count is False
    assert v.weight_cap == pytest.approx(BRAIN_MAX_WEIGHT)
    assert "PASS" in v.verdict
    assert "theatre" not in v.verdict


def test_summary_is_readable_in_both_states() -> None:
    n = LIVE_BOOK_POSITIONS
    w = np.full(n, 1.0 / n)
    live = concentration_verdict(w, constant_correlation(n, LIVE_BOOK_MEAN_CORR)).summary()
    assert "1.37" in live
    unmeasured = concentration_verdict(w, None).summary()
    assert "n/a" in unmeasured and "UNMEASURABLE" in unmeasured
