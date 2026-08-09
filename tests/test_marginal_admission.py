"""Tests for the marginal-contribution admission gate.

The load-bearing case is "the inversion bites". Everything else checks the gate is not broken; that
one checks it actually INVERTED the desk's decision rule -- admitting a WEAKER uncorrelated signal
over a STRONGER correlated one. If that fails the module has failed at the only thing it exists
for, however green the rest of the suite is.

THE FIXTURE MATTERS AS MUCH AS THE ASSERTIONS. A first draft of this file built the incumbent book
with a fresh random base per column, so the three "incumbents" were mutually INDEPENDENT -- the
exact opposite of the live cohort, which is three names in one basis trade at pairwise rho near 1.
The gate then correctly reported that a near-duplicate of one column was only ~0.6 correlated to
the composite, and the test failed while the code was right. A fixture that does not reproduce the
structure being gated tests nothing, so the book here is built from ONE shared driver.

COLLECTABILITY (2026-08-01). This file shipped as a SCRIPT: a module-level `check()` collector
ending in `raise SystemExit`. pytest imports every tests/test_*.py during collection, so that
SystemExit killed the COLLECTOR -- INTERNALERROR, exit code 3, ZERO tests run repo-wide, from any
file. The desk had recorded that exact lesson 15 minutes earlier (L0057/R0337, commit 0240cfa,
"a red pytest leg can mean zero tests ran") and fixed the one instance without fencing the class,
so the next two commits reintroduced it twice. Converted to real test functions here; the class is
now fenced by tests/test_suite_collectable.py so it cannot come back a fourth time.

EVERY FIXTURE VALUE IS STILL COMPUTED AT MODULE LEVEL, IN THE ORIGINAL ORDER, ON PURPOSE. The RNG
is one seeded stream shared across the fixture, so drawing inside test functions would make the
numbers depend on pytest's execution order -- green today, mysteriously red under -p no:randomly
or a -k filter. Module-level construction keeps this suite byte-identical to the script it
replaces, and the assertions below are pure reads of those precomputed objects.
"""
from __future__ import annotations

import math

import numpy as np

from libs.research import marginal_admission as ma

RNG = np.random.default_rng(20260801)
T = 500
SD = 0.01
ANN = math.sqrt(365.0)


def _noise(n: int = T) -> np.ndarray:
    return RNG.normal(0.0, 1.0, n)


def _at_sharpe(shape: np.ndarray, sharpe: float) -> np.ndarray:
    """Rescale a series to a target annualised Sharpe, preserving its correlation structure."""
    z = (shape - shape.mean()) / shape.std(ddof=1)
    return sharpe / ANN * SD + SD * z


def _corr_with(base: np.ndarray, rho: float, sharpe: float) -> np.ndarray:
    """A series with ~`rho` correlation to `base`, rescaled to a chosen standalone Sharpe."""
    b = (base - base.mean()) / base.std(ddof=1)
    y = rho * b + math.sqrt(max(0.0, 1.0 - rho * rho)) * _noise(base.size)
    return _at_sharpe(y, sharpe)


# ---- fixture: the LIVE cohort's structure -- three names, one trade --------------------------
driver = _noise()
book = np.column_stack([_corr_with(driver, 0.97, 1.15) for _ in range(3)])
composite = ma._portfolio_series(book)
book_sharpe = ma._sharpe(composite, 365.0)

# A STRONGER standalone signal that is nearly the book already held.
strong_dupe = _corr_with(composite, 0.95, 1.00)
# A WEAKER standalone signal that is genuinely orthogonal.
weak_div = _at_sharpe(_noise(), 0.50)

a_dupe = ma.evaluate(strong_dupe, book)
a_div = ma.evaluate(weak_div, book)

neg = ma.evaluate(_corr_with(composite, -0.5, 0.30), book)
gains = [ma.evaluate(_corr_with(composite, r, 0.80), book).gain for r in (0.0, 0.3, 0.6, 0.9)]
sweep = [ma.evaluate(_at_sharpe(_noise(), s), book).gain for s in (0.1, 0.4, 0.8, 1.5)]


def test_fixture_reproduces_the_live_cohort_structure() -> None:
    """The fixture is an assertion too: a book of INDEPENDENT columns would test nothing."""
    assert ma._mean_pairwise(book) > 0.9, f"fixture book is not a single trade: {book_sharpe:.3f}"
    assert book_sharpe > 0, f"book Sharpe {book_sharpe:.3f} must be positive for the gate to run"


# ---- the architecture ------------------------------------------------------------------------
def test_strong_duplicate_is_rejected() -> None:
    assert not a_dupe.admitted, (
        f"S={a_dupe.candidate_sharpe:.3f} vs hurdle {a_dupe.hurdle:.3f} "
        f"(rho<={a_dupe.rho_used:.3f})")


def test_weak_diversifier_is_admitted() -> None:
    assert a_div.admitted, (
        f"S={a_div.candidate_sharpe:.3f} rho<={a_div.rho_used:.3f} gain={a_div.gain:+.3f}")


def test_the_inversion_bites_weaker_signal_wins() -> None:
    """THE LOAD-BEARING CASE. If this passes and everything else fails, the module still works."""
    assert a_div.admitted and not a_dupe.admitted, "gate did not invert the decision"
    assert a_div.candidate_sharpe < a_dupe.candidate_sharpe, (
        f"S={a_div.candidate_sharpe:.3f} admitted over S={a_dupe.candidate_sharpe:.3f} rejected")


# ---- fail-closed behaviour ------------------------------------------------------------------
def test_short_overlap_rejected_not_guessed() -> None:
    assert not ma.evaluate(_at_sharpe(_noise(30), 3.0), book[:30]).admitted


def test_empty_candidate_rejected() -> None:
    assert not ma.evaluate(np.array([]), book).admitted


def test_non_finite_candidate_rejected() -> None:
    assert not ma.evaluate(np.r_[_at_sharpe(_noise(), 1.0)[:-1], np.nan], book).admitted


def test_zero_variance_candidate_rejected() -> None:
    assert not ma.evaluate(np.zeros(T), book).admitted


def test_non_positive_book_sharpe_fails_closed() -> None:
    """No standalone fallback: a losing book must not become a licence to admit anything."""
    losing = np.column_stack([_at_sharpe(_noise(), -1.0) for _ in range(2)])
    assert not ma.evaluate(_at_sharpe(_noise(), 2.0), losing).admitted


# ---- structural properties -------------------------------------------------------------------
def test_first_signal_admitted_on_standalone_merit() -> None:
    assert ma.evaluate(_at_sharpe(_noise(), 1.0), np.empty((T, 0))).admitted


def test_first_signal_with_no_edge_rejected() -> None:
    assert not ma.evaluate(_at_sharpe(_noise(), -1.0), np.empty((T, 0))).admitted


def test_negative_correlation_admitted_despite_weak_standalone() -> None:
    assert neg.admitted, (
        f"S={neg.candidate_sharpe:.3f} rho<={neg.rho_used:.3f} gain={neg.gain:+.3f}")


def test_gain_is_non_increasing_in_correlation() -> None:
    assert all(gains[i] >= gains[i + 1] - 1e-9 for i in range(len(gains) - 1)), (
        " -> ".join(f"{g:+.4f}" for g in gains))


def test_gain_is_non_decreasing_in_candidate_sharpe() -> None:
    assert all(sweep[i] <= sweep[i + 1] + 1e-9 for i in range(len(sweep) - 1)), (
        " -> ".join(f"{g:+.4f}" for g in sweep))


def test_duplicate_does_not_inflate_effective_bets() -> None:
    assert a_dupe.n_eff_after <= a_dupe.n_eff_before + 1.0, (
        f"{a_dupe.n_eff_before:.2f} -> {a_dupe.n_eff_after:.2f}")


def test_diversifier_buys_more_effective_bets_than_a_duplicate() -> None:
    assert a_div.n_eff_after > a_dupe.n_eff_after, (
        f"{a_div.n_eff_after:.2f} vs {a_dupe.n_eff_after:.2f}")


def test_rho_used_is_a_conservative_upper_bound() -> None:
    assert a_div.rho_used >= a_div.rho_hat
    assert a_dupe.rho_used >= a_dupe.rho_hat


def test_fisher_bound_widens_toward_one_at_small_n() -> None:
    assert ma._fisher_upper(0.0, 10) > ma._fisher_upper(0.0, 1000), (
        f"n=10 -> {ma._fisher_upper(0.0, 10):.3f}, n=1000 -> {ma._fisher_upper(0.0, 1000):.3f}")


def test_portfolio_sharpe_never_reported_below_its_starting_point() -> None:
    assert a_div.portfolio_sharpe_after >= a_div.portfolio_sharpe
    assert a_dupe.portfolio_sharpe_after >= a_dupe.portfolio_sharpe
