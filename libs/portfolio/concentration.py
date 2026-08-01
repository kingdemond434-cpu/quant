"""MAKE THE CONCENTRATION LIMIT MEAN SOMETHING -- a breadth-aware cap, and bets you can count.

WHERE THE LIMIT STANDS TODAY. ``libs/portfolio/models.PortfolioConstraints.max_weight = 0.25``.
WorldQuant BRAIN -- the live institutional pipeline that pays research consultants, and the one
this desk has already measured itself as 4.0x STRICTER than on EVIDENCE (submits at fitness 1.0,
targets Sharpe 1.25, against this desk's certified floor of TRUE SHARPE 5.0; see
libs/validation/brain_calibration.py and libs/validation/screen_admission.py) -- caps a single
name at 0.08. On CONCENTRATION the direction reverses: 0.25 / 0.08 = 3.1x LOOSER.

The obvious correction is to write 0.08 and close the ticket. That correction is wrong twice, and
both reasons are measurements rather than opinions.

(a) 0.08 IS ARITHMETICALLY UNSATISFIABLE ON THE BOOK THAT ACTUALLY TRADES.
    The live cash-carry executor (scripts/run_cashcarry_executor.py) does not import
    PortfolioConstraints at all. It controls concentration by COUNT: data/cashcarry_config.json
    carries ``"top": 4``. Four names is 25% each BY CONSTRUCTION. A 0.08 cap needs 1/0.08 = 12.5,
    i.e. AT LEAST 13 NAMES, to admit any feasible weight vector whatsoever. Imposed on a 4-name
    book it has no solution: it is not a tighter constraint, it is a broken one, and broken
    constraints get commented out or crash a rebalance. The number 0.25 is not looseness -- it is
    exactly 1/4, the TIGHTEST SATISFIABLE cap at four names, and it was never a choice.

(b) AT 0.638 MEAN CORRELATION A NOMINAL WEIGHT CAP IS THEATRE.
    The desk's 29 crypto perps have mean pairwise correlation 0.638 raw, worth 1.54 independent
    bets (reports/cross_section_breadth.json, libs/research/cohort_independence.py; the current
    report snapshot is 28 survivors at 0.6821 -> 1.44, same story). Capping four 0.638-correlated
    names at 8% each does not buy 12 bets. It buys 1.37. Nominal weight is simply the wrong
    quantity: it measures how the book is LABELLED, not how many distinct things it is exposed to.

    The size of the illusion, measured: libs/portfolio/diversification.effective_bets is
    correlation-BLIND (1 / sum w^2) and reports 4.00 bets for the live book. The truth at
    rho = 0.638 is 1.37. That is a 2.9x OVERSTATEMENT sitting in a shipped function, and it is the
    same defect class cohort_independence.effective_bets was written to kill.

WHAT THIS MODULE DOES INSTEAD.

  1. ``max_weight_for(n)`` = max(0.08, 1/n). Breadth-aware. It CANNOT be unsatisfiable at any n,
     it AUTO-TIGHTENS as the book widens, and it lands exactly on BRAIN's 0.08 from n >= 13 --
     which is the same 13 that (a) says a 0.08 cap requires. The desk gets BRAIN's rule the moment
     the desk can honour it, and a satisfiable rule before that.

  2. ``effective_positions(w, C)`` = 1 / (w' C w). The correlation-adjusted inverse Herfindahl:
     at C = I it degenerates to the familiar 1 / sum w^2, and at C = all-ones it collapses to 1 --
     a book of identical exposures is ONE bet however many tickers it holds. This is the quantity a
     concentration limit was always trying to constrain.

  3. ``MIN_EFFECTIVE_POSITIONS = 2.0``, and it FAILS THE CURRENT LIVE BOOK. See the constant.

THE CEILING, WHICH IS THE REAL FINDING. Under equicorrelation, N_eff = N / (1 + (N-1) rho) is
bounded above by 1/rho as N grows. At rho = 0.638 that ceiling is 1.567. So NO long, unhedged
crypto-perp book of ANY width clears two effective positions: 4 names give 1.37, 13 give 1.50,
29 give 1.54, and infinitely many give 1.567. Widening the book is not the fix and never was.
The desk's own residual panel is: after market-factor removal mean pairwise correlation is
-0.0325, and four HEDGED names are worth 4.0 effective positions. The lever is the market factor,
not the ticker count -- and this module is built so the verdict string says exactly that instead
of quietly passing.

THIS MODULE SIZES NOTHING AND PROMOTES NOTHING. It reports how many bets a proposed book is
actually making. A book of six genuinely independent positions can still be six worthless ones.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np
import numpy.typing as npt

from libs.research.cohort_independence import effective_bets as equicorrelation_bets

__all__ = [
    "BRAIN_MAX_WEIGHT",
    "LIVE_BOOK_MEAN_CORR",
    "LIVE_BOOK_POSITIONS",
    "MIN_EFFECTIVE_POSITIONS",
    "ConcentrationVerdict",
    "concentration_verdict",
    "effective_positions",
    "max_weight_for",
]

#: WorldQuant BRAIN's single-name cap. Kept as a named FLOOR rather than a target, because at
#: n < 13 positions it is not a constraint, it is an empty feasible set (see module docstring (a)).
BRAIN_MAX_WEIGHT = 0.08

#: Positions in the live cash-carry book -- data/cashcarry_config.json ``"top": 4``. Recorded here
#: because every claim in this module about unsatisfiability is a claim about THIS number, and a
#: reader who does not know it will read max_weight_for(4) = 0.25 as laxity.
LIVE_BOOK_POSITIONS = 4

#: Mean pairwise correlation of the desk's 29 crypto perps, raw (reports/cross_section_breadth.json
#: via libs/research/cohort_independence.py). RAW, not residual, on purpose: the live book is long
#: the market, so the correlation it actually carries is the one before factor removal.
LIVE_BOOK_MEAN_CORR = 0.638

#: MINIMUM CORRELATION-ADJUSTED POSITIONS. THIS THRESHOLD FAILS THE CURRENT LIVE BOOK, AND THAT IS
#: THE POINT OF WRITING IT DOWN.
#:
#: WHY 2.0. Below two effective positions, 1/N_eff -- the share of book variance carried by the
#: single dominant independent bet -- exceeds one half. Every per-name risk statistic computed on
#: such a book is a statistic about one bet wearing several tickers, and a weight cap that the book
#: satisfies is describing an illusion. Two is the smallest number at which the word
#: "diversified" is not simply false. It is a FLOOR ON MEANING, not a target: BRAIN's 0.08 implies
#: 12.5 effective positions at zero correlation, and adopting 12.5 here would repeat failure mode
#: (a) one level up -- an unreachable bar that gets ignored.
#:
#: WHAT IT DOES TO THE LIVE BOOK, STATED PLAINLY. Four equal-weight names at rho = 0.638 are worth
#: 4 / (1 + 3 * 0.638) = 1.37 effective positions. 1.37 < 2.0, so THE BOOK THAT IS RUNNING RIGHT
#: NOW FAILS THIS GATE. The task's arithmetic was checked before the number was chosen: any
#: threshold above ~1.4 fails it, and every threshold at or below 1.4 was rejected precisely
#: BECAUSE it would pass. A limit calibrated to pass whatever happens to be running is not a limit,
#: it is a description with a comparison operator in it.
#:
#: AND IT IS NOT UNREACHABLE, WHICH IS WHAT SEPARATES IT FROM 0.08. The failure has a measured
#: remedy that is not "hold more coins": at rho = 0.638 the equicorrelation ceiling is 1/0.638 =
#: 1.567, so no unhedged long perp book of any width reaches 2.0 -- but the desk's own residual
#: panel, after market-factor removal, has mean pairwise correlation -0.0325, at which the SAME
#: FOUR NAMES are worth 4.0 effective positions and clear this bar with room. So a failure here
#: reads "hedge the market factor", never "add tickers".
#:
#: THE HONEST CAVEAT ON THAT REMEDY. cohort_independence.effective_bets records that cross-
#: sectional demeaning forces residual correlation toward -1/(N-1) by arithmetic alone (-0.037 at
#: N = 28, measured -0.0325, excess above the floor 0.0045). So residual N_eff ~= N is an UPPER
#: BOUND on what hedging buys, not a promise. It is still a different order of magnitude from 1.37.
MIN_EFFECTIVE_POSITIONS = 2.0

#: Magnitude floor on the quadratic form w'Cw, NOT a ``> 0`` test. ``> 0`` is the guard this desk
#: has been burned by: it passes 1e-300 -- which a nearly-singular correlation matrix produces
#: routinely -- and returns 1e300 effective positions, a number that would be read as a finding.
#: For a normalised book of n names, w'Cw is O(1/n) times the smallest relevant eigenvalue, so
#: anything under 1e-10 is a numerically degenerate direction, not diversification.
_MIN_QUADRATIC_FORM = 1e-10

#: Magnitude floor on the NET weight sum before normalisation. A dollar-neutral long/short book
#: sums to ~0, and 1/(w'Cw) on net-normalised weights is then undefined rather than large. Such a
#: book must be measured per leg on gross weights; silently switching to gross normalisation here
#: would be an ambiguous branch that ALLOWS, which is this desk's #1 defect class. It BLOCKS.
_MIN_WEIGHT_SUM = 1e-9

#: Weight magnitude below which a "position" is dust and does not count toward the upper clamp on
#: N_eff. A 1e-18 residual left by an optimiser is not a bet.
_DUST_WEIGHT = 1e-12

#: Symmetry / unit-diagonal tolerance for a matrix claiming to be a correlation matrix.
_MATRIX_TOL = 1e-8


def max_weight_for(n_positions: int, floor: float = BRAIN_MAX_WEIGHT) -> float:
    """BREADTH-AWARE single-name cap: ``max(floor, 1 / n_positions)``.

    THE PROPERTY THAT MATTERS IS THAT IT CAN NEVER BE UNSATISFIABLE. cap * n >= 1 holds for every
    n, so an equal-weight book of any width is always feasible. The desk's existing 0.25 fails
    silently in the other direction only because the live book happens to hold exactly four names;
    replace ``"top": 4`` with ``"top": 3`` in data/cashcarry_config.json and a fixed 0.25 becomes
    infeasible overnight with nothing to warn you. This function cannot do that.

    IT AUTO-TIGHTENS AND CONVERGES ON BRAIN. 1/n falls below 0.08 at n >= 12.5, so from THIRTEEN
    NAMES ONWARD this returns exactly BRAIN's 0.08 and stays there. Thirteen is not a coincidence:
    it is the same 13 that a fixed 0.08 cap requires before its feasible set is non-empty. The desk
    adopts the institutional rule at precisely the width where the institutional rule has meaning.

      n:      1     2     3     4     8    12      13    29
      cap: 1.000 0.500 0.333 0.250 0.125 0.0833  0.080 0.080

    AT n = 4 THE CAP CANNOT BIND, AND THAT IS ITSELF THE FINDING. It returns 0.250, which the live
    equal-weight book sits exactly on; no smaller cap has a solution. So at four names the weight
    cap has no room to do work in either direction -- concentration is governed entirely by
    POSITION COUNT, and "tighten the cap" is theatre. The two levers that exist there are raising
    ``"top"`` and removing the common factor; see ``effective_positions`` for why only the second
    one actually moves the number.

    ``floor`` is a parameter rather than a constant so a venue with a hard per-name limit can pass
    a stricter one; it is never allowed to make the cap unsatisfiable because 1/n always wins when
    it is larger. n <= 0 clamps to 1 and returns 1.0: an empty or single-name book IS 100% of
    itself, and reporting anything else would be a cap pretending to constrain arithmetic.
    """
    n = max(1, int(n_positions))
    f = float(floor)
    if not np.isfinite(f) or f <= 0.0:
        # An absent or nonsensical floor must not silently become "no floor". Fall back to the
        # breadth term alone, which is the tightest satisfiable cap and never unsatisfiable.
        f = 0.0
    return max(f, 1.0 / n)


def _clean_weights(weights: Sequence[float] | npt.NDArray[np.float64]) -> tuple[
        npt.NDArray[np.float64], str]:
    """Normalise a weight vector to sum 1, or return the reason it is unmeasurable."""
    w = np.asarray(weights, dtype="float64").ravel()
    if w.size == 0:
        return w, "no positions supplied"
    if not bool(np.all(np.isfinite(w))):
        return w, "weights contain non-finite values"
    total = float(np.sum(w))
    if abs(total) < _MIN_WEIGHT_SUM:
        return w, ("weights sum to ~0 (net-neutral book): effective positions is undefined on "
                   "net-normalised weights; measure each leg on gross weights instead")
    return w / total, ""


def _clean_corr(corr: npt.NDArray[np.float64] | None, n: int) -> tuple[
        npt.NDArray[np.float64], str]:
    """Validate a correlation matrix, or return the reason it is unmeasurable.

    EVERY BRANCH HERE BLOCKS. An absent, malformed, non-finite or non-PSD correlation matrix is an
    UNKNOWN correlation, and an unknown correlation must never be reported as diversification --
    that is the #1 defect class on this desk. The tempting default (missing matrix -> assume
    identity) would hand the live 4-name book 4.0 effective positions instead of 1.37 and pass it.
    """
    empty = np.zeros((0, 0), dtype="float64")
    if corr is None:
        return empty, "correlation matrix absent"
    c = np.asarray(corr, dtype="float64")
    if c.ndim != 2 or c.shape[0] != c.shape[1]:
        return empty, f"correlation matrix is not square (shape {c.shape})"
    if c.shape[0] != n:
        return empty, f"correlation matrix is {c.shape[0]}x{c.shape[0]} for {n} position(s)"
    if not bool(np.all(np.isfinite(c))):
        return empty, "correlation matrix contains non-finite values"
    if not bool(np.allclose(c, c.T, atol=_MATRIX_TOL, rtol=0.0)):
        return empty, "correlation matrix is not symmetric"
    if not bool(np.allclose(np.diag(c), 1.0, atol=_MATRIX_TOL, rtol=0.0)):
        # Almost always a covariance matrix passed where a correlation matrix was expected. The
        # quadratic form would still evaluate and return a plausible-looking number in the wrong
        # units, which is worse than a crash. Use libs.portfolio.covariance.cov_to_corr first.
        return empty, "matrix diagonal is not 1 -- this looks like a covariance, not a correlation"
    # Eigenvalues of a correlation matrix sum to n, so the PSD tolerance is scaled by n rather than
    # fixed: on a 29-name matrix a -1e-12 eigenvalue is float dust, on a 2-name matrix it is not.
    if float(np.min(np.linalg.eigvalsh(c))) < -_MATRIX_TOL * max(1, n):
        return empty, "correlation matrix is not positive semi-definite"
    return c, ""


def effective_positions(
    weights: Sequence[float] | npt.NDArray[np.float64],
    corr: npt.NDArray[np.float64] | None,
) -> float:
    """Correlation-adjusted effective positions: ``N_eff = 1 / (w' C w)``, weights summing to 1.

    THIS IS THE QUANTITY A CONCENTRATION LIMIT WAS ALWAYS REACHING FOR. It has two degenerate cases
    that pin it to things already understood, both locked by tests:

      * C = I  ->  1 / sum(w^2), the plain inverse Herfindahl, i.e. exactly what
        libs/portfolio/diversification.effective_bets computes. That function is the C = I case of
        this one, permanently, whatever the real correlations are -- which is why it reports 4.00
        bets for a live book worth 1.37 (a 2.9x overstatement).
      * C = all-ones  ->  1.0. N identical exposures are ONE bet. That is the whole argument
        against nominal weight caps in one line: you can spread across 13 names at 8% each and
        still hold one bet.

    MEASURED ON THE LIVE BOOK: 4 equal weights at rho = 0.638 give w'Cw = (4 + 12*0.638)/16 =
    0.7285 and N_eff = 1.373 -- matching the equicorrelation closed form 4/(1+3*0.638) that
    cohort_independence.effective_bets returns, which is the cross-check ``concentration_verdict``
    reports.

    CLAMPED TO [1, n_active], AND THE UPPER CLAMP IS NOT COSMETIC -- it is desk lesson L0020
    recurring in a new place. With negative off-diagonals the quadratic form shrinks without bound
    and this returns absurdities: two names at rho = -0.9 come out at 20 effective positions from a
    2-name book. cohort_independence.effective_bets already learned this the expensive way, when
    demeaning-induced negative correlation made 29 crypto perps report 64.4 independent bets and
    the number was read as a finding. Same clamp, same reason. The lower clamp matters for the
    opposite case: rho -> 1 sends this to 1, correctly.

    Returns NaN when the inputs cannot support the measurement -- absent, non-square, non-finite,
    asymmetric, non-unit-diagonal or non-PSD correlation, or a net-neutral weight vector. NaN
    rather than 0.0 (which would read as maximal concentration and might accidentally look
    conservative) and emphatically rather than n (which would read as perfect diversification).
    Callers must branch on ``concentration_verdict``'s ``measurable`` flag, never on the float:
    every comparison against NaN is False, and a gate that is safe only because of IEEE-754
    accident is a gate waiting to be refactored into a defect. UNMEASURED IS NOT PASSED.
    """
    w, why = _clean_weights(weights)
    if why:
        return float("nan")
    c, why = _clean_corr(corr, int(w.size))
    if why:
        return float("nan")
    quad = float(w @ c @ w)
    if not np.isfinite(quad) or quad < _MIN_QUADRATIC_FORM:
        return float("nan")
    n_active = int(np.count_nonzero(np.abs(w) > _DUST_WEIGHT))
    return min(float(max(1, n_active)), max(1.0, 1.0 / quad))


@dataclass(frozen=True)
class ConcentrationVerdict:
    """What a proposed book's concentration actually is, and which constraint decided it."""

    n_positions: int
    max_weight: float
    weight_cap: float
    cap_set_by_count: bool
    effective_positions: float
    min_effective_positions: float
    equicorrelation_check: float
    measurable: bool
    passes: bool
    binding: tuple[str, ...]
    verdict: str

    def summary(self) -> str:
        neff = "n/a" if not self.measurable else f"{self.effective_positions:.2f}"
        return (f"{self.n_positions} position(s), max weight {self.max_weight:.3f} "
                f"vs cap {self.weight_cap:.3f} -> {neff} effective position(s) "
                f"(floor {self.min_effective_positions:.2f}) :: {self.verdict}")


def _unmeasurable(n: int, max_w: float, cap: float, why: str,
                  min_effective: float) -> ConcentrationVerdict:
    return ConcentrationVerdict(
        n_positions=n,
        max_weight=max_w,
        weight_cap=cap,
        cap_set_by_count=bool(n >= 1 and 1.0 / max(1, n) > BRAIN_MAX_WEIGHT),
        effective_positions=float("nan"),
        min_effective_positions=min_effective,
        equicorrelation_check=float("nan"),
        measurable=False,
        passes=False,
        binding=("unmeasurable",),
        verdict=(f"UNMEASURABLE -- BLOCKED: {why}. An unknown correlation is not a diversified "
                 "book; UNMEASURED IS NOT PASSED."),
    )


def concentration_verdict(
    weights: Sequence[float] | npt.NDArray[np.float64],
    corr: npt.NDArray[np.float64] | None,
    *,
    min_effective_positions: float = MIN_EFFECTIVE_POSITIONS,
) -> ConcentrationVerdict:
    """Judge a proposed book on BOTH constraints and say which one bound.

    Two independent tests, and the verdict names the binder because the two carry completely
    different instructions:

      * ``max_weight`` bound  -> rebalance; the weights are lopsided for the width being run.
      * ``effective_positions`` bound -> the weights are fine and the BOOK is one bet. Adding
        names does not fix it (ceiling 1/rho = 1.567 at rho = 0.638); removing the common factor
        does.

    The second is the case the desk has never been able to see, because the only concentration
    control in the code is a nominal cap that the live book satisfies exactly.

    UNMEASURABLE BLOCKS. Bad or absent correlation returns ``passes=False`` with
    ``measurable=False``, never a pass and never a silently-assumed identity matrix.

    ``equicorrelation_check`` is cohort_independence.effective_bets evaluated at this matrix's mean
    off-diagonal correlation. On an equal-weight book with an equicorrelated matrix the two agree
    to floating point; where they diverge, the divergence is the finding -- a quadratic form far
    below the equicorrelation estimate means a few names carry the book, which is a clustering
    problem with a different fix. It is REPORTED, never used to decide, so that no gate depends on
    an approximation that assumes away the structure being looked for.
    """
    floor = float(min_effective_positions)
    w, why_w = _clean_weights(weights)
    n = int(w.size)
    cap = max_weight_for(n)
    max_w = float(np.max(np.abs(w))) if (n > 0 and not why_w) else float("nan")
    if why_w:
        return _unmeasurable(n, max_w, cap, why_w, floor)
    c, why_c = _clean_corr(corr, n)
    if why_c:
        return _unmeasurable(n, max_w, cap, why_c, floor)

    n_eff = effective_positions(w, c)
    if not np.isfinite(n_eff):
        return _unmeasurable(n, max_w, cap, "quadratic form w'Cw is numerically degenerate", floor)

    off = c[~np.eye(n, dtype=bool)]
    mean_corr = float(np.mean(off)) if off.size else 0.0
    check = equicorrelation_bets(n, mean_corr)

    cap_binds = bool(max_w > cap + _MATRIX_TOL)
    breadth_binds = bool(n_eff < floor)
    binding = tuple(
        name for name, hit in (("max_weight", cap_binds), ("effective_positions", breadth_binds))
        if hit)
    cap_set_by_count = bool(1.0 / max(1, n) > BRAIN_MAX_WEIGHT)

    if cap_binds and breadth_binds:
        verdict = (f"FAIL on BOTH: max weight {max_w:.3f} > cap {cap:.3f}, and the book is worth "
                   f"only {n_eff:.2f} effective position(s) against a floor of {floor:.2f}. Fixing "
                   "the weights will not fix the second one.")
    elif cap_binds:
        verdict = (f"FAIL -- NOMINAL WEIGHT CAP bound: max weight {max_w:.3f} exceeds the "
                   f"breadth-aware cap {cap:.3f} for {n} position(s). Rebalance; the book still "
                   f"carries {n_eff:.2f} effective position(s), which clears the floor.")
    elif breadth_binds:
        verdict = (
            f"FAIL -- EFFECTIVE POSITIONS bound: the nominal cap {cap:.3f} is SATISFIED (max "
            f"weight {max_w:.3f}) and told you nothing. At mean pairwise correlation "
            f"{mean_corr:.3f} these {n} name(s) are worth {n_eff:.2f} effective position(s), "
            f"below the floor of {floor:.2f}. Adding names cannot fix this -- the equicorrelation "
            f"ceiling is 1/rho = {1.0 / mean_corr:.2f} at this correlation. Remove the common "
            "factor.") if mean_corr > 0 else (
            f"FAIL -- EFFECTIVE POSITIONS bound: {n_eff:.2f} effective position(s) against a floor "
            f"of {floor:.2f}, with the nominal cap {cap:.3f} satisfied (max weight {max_w:.3f}).")
    else:
        verdict = (f"PASS: {n_eff:.2f} effective position(s) >= {floor:.2f}, max weight "
                   f"{max_w:.3f} <= cap {cap:.3f}. Neither constraint bound.")

    if cap_set_by_count:
        verdict += (f" [NOTE: at {n} name(s) the cap is 1/n = {cap:.3f}, set by POSITION COUNT and "
                    f"not by BRAIN's {BRAIN_MAX_WEIGHT:.2f} floor -- no tighter cap is "
                    "satisfiable, so tightening it here is theatre.]")

    return ConcentrationVerdict(
        n_positions=n,
        max_weight=max_w,
        weight_cap=cap,
        cap_set_by_count=cap_set_by_count,
        effective_positions=n_eff,
        min_effective_positions=floor,
        equicorrelation_check=check,
        measurable=True,
        passes=not binding,
        binding=binding,
        verdict=verdict,
    )
