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


fails: list[str] = []


def check(name: str, cond: bool, detail: str = "") -> None:
    print(f"  {'PASS' if cond else 'FAIL'}  {name}{(' -- ' + detail) if detail else ''}")
    if not cond:
        fails.append(name)


# ---- fixture: the LIVE cohort's structure -- three names, one trade --------------------------
driver = _noise()
book = np.column_stack([_corr_with(driver, 0.97, 1.15) for _ in range(3)])
composite = ma._portfolio_series(book)
book_sharpe = ma._sharpe(composite, 365.0)
print(f"  [fixture] book Sharpe {book_sharpe:.3f}, mean pairwise rho {ma._mean_pairwise(book):.3f}")

# A STRONGER standalone signal that is nearly the book already held.
strong_dupe = _corr_with(composite, 0.95, 1.00)
# A WEAKER standalone signal that is genuinely orthogonal.
weak_div = _at_sharpe(_noise(), 0.50)

a_dupe = ma.evaluate(strong_dupe, book)
a_div = ma.evaluate(weak_div, book)

check("strong DUPLICATE is rejected", not a_dupe.admitted,
      f"S={a_dupe.candidate_sharpe:.3f} vs hurdle {a_dupe.hurdle:.3f} (rho<={a_dupe.rho_used:.3f})")
check("weak DIVERSIFIER is admitted", a_div.admitted,
      f"S={a_div.candidate_sharpe:.3f} rho<={a_div.rho_used:.3f} gain={a_div.gain:+.3f}")
check("THE INVERSION BITES: weaker signal wins",
      a_div.admitted and not a_dupe.admitted
      and a_div.candidate_sharpe < a_dupe.candidate_sharpe,
      f"S={a_div.candidate_sharpe:.3f} admitted over S={a_dupe.candidate_sharpe:.3f} rejected")

# ---- fail-closed behaviour ------------------------------------------------------------------
check("short overlap rejected, not guessed",
      not ma.evaluate(_at_sharpe(_noise(30), 3.0), book[:30]).admitted)
check("empty candidate rejected", not ma.evaluate(np.array([]), book).admitted)
check("non-finite candidate rejected",
      not ma.evaluate(np.r_[_at_sharpe(_noise(), 1.0)[:-1], np.nan], book).admitted)
check("zero-variance candidate rejected", not ma.evaluate(np.zeros(T), book).admitted)
check("non-positive book Sharpe fails closed (no standalone fallback)",
      not ma.evaluate(_at_sharpe(_noise(), 2.0),
                      np.column_stack([_at_sharpe(_noise(), -1.0) for _ in range(2)])).admitted)

# ---- structural properties -------------------------------------------------------------------
check("first signal admitted on standalone merit",
      ma.evaluate(_at_sharpe(_noise(), 1.0), np.empty((T, 0))).admitted)
check("first signal with no edge rejected",
      not ma.evaluate(_at_sharpe(_noise(), -1.0), np.empty((T, 0))).admitted)

neg = ma.evaluate(_corr_with(composite, -0.5, 0.30), book)
check("NEGATIVE correlation admitted despite weak standalone", neg.admitted,
      f"S={neg.candidate_sharpe:.3f} rho<={neg.rho_used:.3f} gain={neg.gain:+.3f}")

gains = [ma.evaluate(_corr_with(composite, r, 0.80), book).gain for r in (0.0, 0.3, 0.6, 0.9)]
check("gain is non-increasing in correlation",
      all(gains[i] >= gains[i + 1] - 1e-9 for i in range(len(gains) - 1)),
      " -> ".join(f"{g:+.4f}" for g in gains))

sweep = [ma.evaluate(_at_sharpe(_noise(), s), book).gain for s in (0.1, 0.4, 0.8, 1.5)]
check("gain is non-decreasing in candidate Sharpe",
      all(sweep[i] <= sweep[i + 1] + 1e-9 for i in range(len(sweep) - 1)),
      " -> ".join(f"{g:+.4f}" for g in sweep))

check("duplicate does not inflate effective bets", a_dupe.n_eff_after <= a_dupe.n_eff_before + 1.0,
      f"{a_dupe.n_eff_before:.2f} -> {a_dupe.n_eff_after:.2f}")
check("diversifier buys more effective bets than a duplicate",
      a_div.n_eff_after > a_dupe.n_eff_after,
      f"{a_div.n_eff_after:.2f} vs {a_dupe.n_eff_after:.2f}")
check("rho_used is a conservative upper bound",
      a_div.rho_used >= a_div.rho_hat and a_dupe.rho_used >= a_dupe.rho_hat)
check("Fisher bound widens toward 1.0 at small n",
      ma._fisher_upper(0.0, 10) > ma._fisher_upper(0.0, 1000),
      f"n=10 -> {ma._fisher_upper(0.0, 10):.3f}, n=1000 -> {ma._fisher_upper(0.0, 1000):.3f}")
check("portfolio Sharpe never reported below its starting point",
      a_div.portfolio_sharpe_after >= a_div.portfolio_sharpe
      and a_dupe.portfolio_sharpe_after >= a_dupe.portfolio_sharpe)

print("ALL PASS" if not fails else f"{len(fails)} FAILED: {fails}")
raise SystemExit(1 if fails else 0)
