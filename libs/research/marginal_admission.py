"""ADMIT SIGNALS ON MARGINAL PORTFOLIO CONTRIBUTION, NOT STANDALONE MERIT.

THE STRUCTURAL INVERSION. This desk screens candidates on their OWN out-of-sample Sharpe against a
fixed bar. That is the wrong question, and it is why the live cohort is three signals -- BNB, ETH
and BTC basis -- that are pairwise correlated near 1.0 and therefore constitute ONE bet wearing
three tickers. Medallion-class construction asks a different question: does this candidate raise
the SHARPE OF THE PORTFOLIO I ALREADY HAVE? A weak uncorrelated signal usually does. A strong
correlated one usually does not. Standalone screening cannot tell those apart, so it keeps buying
the bet it already owns.

THE MATHEMATICS, and it is exact rather than a heuristic. For a tangency portfolio at Sharpe S_p,
adding a candidate of Sharpe s_c with correlation rho to that portfolio gives

    IR_c  = (s_c - rho * S_p) / sqrt(1 - rho**2)          <- the candidate's information ratio
                                                              ORTHOGONAL to what is already held
    S_new = sqrt(S_p**2 + IR_c**2)

Two consequences drive everything here:

  * The admission condition is s_c > rho * S_p. NOT s_c > some fixed bar. A candidate at Sharpe
    0.05 with rho = 0 is admissible against a portfolio at Sharpe 0.40; a candidate at Sharpe 0.35
    with rho = 0.95 is NOT, because 0.35 < 0.95 * 0.40 = 0.38. It is worse than useless -- it
    consumes slots, multiplicity budget and capital to re-buy an exposure already held.
  * NEGATIVE correlation is worth more than positive Sharpe. At rho < 0 the numerator grows, so a
    hedge with mediocre standalone performance can beat a strong duplicate. Nothing in the current
    standalone gate can express that, which is a structural blind spot rather than a tuning miss.

WHY THE CORRELATION IS DELIBERATELY OVERSTATED. rho is ESTIMATED, and the error is asymmetric in
its consequences: understating it admits a duplicate that quietly concentrates the book, while
overstating it costs one slot. So the gate uses the UPPER confidence bound on rho (Fisher-z, one
sided) rather than the point estimate. At small n that bound is close to 1 and almost nothing is
admitted -- which is correct, because at small n you genuinely cannot tell a diversifier from a
duplicate, and this desk's repeated failure has been treating "not yet measurable" as "fine".

WHY A MINIMUM GAIN AND NOT gain > 0. Every S_new above is computed from estimates. A gain of
+0.001 Sharpe is indistinguishable from zero and would let an endless stream of near-duplicates
each claim a sliver of improvement -- the multiplicity problem re-entering through the portfolio
door. MIN_GAIN makes admission mean something.

RELATIONSHIP TO cohort_independence.effective_bets. That module MEASURES what the cohort is worth
(N_eff = N / (1 + (N-1) * rho); 101 real production alphas at rho = 0.159 are worth 6.0 bets). It
has no authority -- nothing consults it before admitting anything. This module is the gate that
measurement always implied and never had, and it reports N_eff before and after so the cost of an
admission is visible at the moment it is taken.

FAIL CLOSED. Insufficient overlap, degenerate correlation (|rho| -> 1), non-finite inputs, or a
non-positive incumbent Sharpe all return admitted=False with a stated reason. An unmeasurable
candidate is never admitted; a gate that counts "could not measure" as "passed" is how a book ends
up concentrated in the one trade it already had.
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from typing import Any

import numpy as np

#: Minimum overlapping observations before a correlation is allowed to mean anything. Below this
#: the Fisher-z bound is so wide that every candidate reads as a possible duplicate -- which is the
#: honest answer, not an obstacle to route around.
MIN_OVERLAP = 60

#: One-sided confidence level for the UPPER bound on rho. 0.95 -> z = 1.645. Deliberately
#: conservative: understating correlation concentrates the book, overstating it costs one slot.
RHO_Z = 1.645

#: Minimum portfolio Sharpe improvement that counts as real. Below this the "gain" is estimation
#: noise, and admitting on noise re-imports the multiplicity problem through the portfolio door.
MIN_GAIN = 0.02


@dataclass(frozen=True)
class Admission:
    """The verdict, with every intermediate quantity kept so the decision is auditable."""

    admitted: bool
    reason: str
    candidate_sharpe: float
    portfolio_sharpe: float
    rho_hat: float          #: point estimate of correlation to the incumbent portfolio
    rho_used: float         #: the conservative UPPER bound actually gated on
    hurdle: float           #: rho_used * portfolio_sharpe -- the Sharpe the candidate must beat
    orthogonal_ir: float    #: candidate's information ratio orthogonal to what is already held
    portfolio_sharpe_after: float
    gain: float
    n_overlap: int
    n_eff_before: float
    n_eff_after: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _fisher_upper(rho: float, n: int, z: float = RHO_Z) -> float:
    """One-sided upper confidence bound on rho via the Fisher z transform.

    Conservative by construction and deliberately so: the bound is what the gate uses, so a
    correlation this desk cannot yet pin down reads as HIGH (duplicate-like) rather than low. The
    asymmetry is intentional -- understating correlation silently concentrates the book, while
    overstating it costs a single slot that later evidence can reclaim.
    """
    if n <= 3:
        return 1.0
    rho = float(np.clip(rho, -0.999999, 0.999999))
    zr = math.atanh(rho) + z / math.sqrt(n - 3)
    return float(min(1.0, math.tanh(zr)))


def _portfolio_series(incumbents: np.ndarray) -> np.ndarray:
    """Equal-risk-weighted composite of the incumbent signals.

    Equal RISK weight, not equal dollar weight: each column is standardised before summing, so a
    high-variance incumbent cannot dominate the composite and thereby understate a candidate's
    correlation to the book. Using raw columns here would bias rho DOWNWARD, which is exactly the
    direction that wrongly admits duplicates.
    """
    if incumbents.ndim == 1:
        incumbents = incumbents.reshape(-1, 1)
    sd = incumbents.std(axis=0, ddof=1)
    sd = np.where(sd > 0, sd, np.nan)
    return np.nansum(incumbents / sd, axis=1)


def _sharpe(x: np.ndarray, periods_per_year: float) -> float:
    sd = float(np.std(x, ddof=1))
    if not np.isfinite(sd) or sd <= 0:
        return 0.0
    return float(np.mean(x) / sd * math.sqrt(periods_per_year))


def _n_eff(n: int, mean_corr: float) -> float:
    """N / (1 + (N-1) * rho) -- the equicorrelation effective-bet count, floored at 1.0.

    Same formula as cohort_independence.effective_bets, restated locally so this gate has no import
    cycle. Reported before and after so the cost of an admission is visible at the moment it is
    taken rather than discovered later in an audit.
    """
    if n <= 0:
        return 0.0
    rho = float(np.clip(mean_corr, -1.0 / max(n - 1, 1) + 1e-9, 1.0))
    return float(max(1.0, n / (1.0 + (n - 1) * rho)))


def _mean_pairwise(mat: np.ndarray) -> float:
    if mat.ndim == 1 or mat.shape[1] < 2:
        return 0.0
    c = np.corrcoef(mat, rowvar=False)
    iu = np.triu_indices_from(c, k=1)
    vals = c[iu]
    vals = vals[np.isfinite(vals)]
    return float(np.mean(vals)) if vals.size else 0.0


def evaluate(
    candidate: np.ndarray,
    incumbents: np.ndarray,
    *,
    periods_per_year: float = 365.0,
    min_gain: float = MIN_GAIN,
    min_overlap: int = MIN_OVERLAP,
) -> Admission:
    """Does this candidate raise the Sharpe of the portfolio the desk ALREADY holds?

    `candidate` is a 1-D return series. `incumbents` is (T, k) of the live cohort's return series,
    row-aligned with the candidate -- same timestamps, same bar convention. Misaligned rows would
    compare two different rulers and produce a correlation that means nothing, which is the
    measurement-basis failure this desk keeps paying for; align upstream.

    An EMPTY incumbent set admits on standalone merit alone, because with nothing held there is
    nothing to duplicate -- the first signal cannot be redundant.
    """
    cand = np.asarray(candidate, dtype=float).ravel()
    inc = np.asarray(incumbents, dtype=float)
    if inc.size and inc.ndim == 1:
        inc = inc.reshape(-1, 1)

    blank = {"candidate_sharpe": 0.0, "portfolio_sharpe": 0.0, "rho_hat": float("nan"),
             "rho_used": 1.0, "hurdle": float("nan"), "orthogonal_ir": 0.0,
             "portfolio_sharpe_after": 0.0, "gain": 0.0, "n_overlap": int(cand.size),
             "n_eff_before": 0.0, "n_eff_after": 0.0}

    if not np.all(np.isfinite(cand)) or cand.size == 0:
        return Admission(False, "candidate series is empty or non-finite", **blank)

    # No incumbents: nothing to be redundant WITH, so standalone merit is the whole question.
    if inc.size == 0:
        s_c = _sharpe(cand, periods_per_year)
        return Admission(
            s_c > 0.0, "first signal -- no incumbent portfolio to duplicate"
            if s_c > 0 else "first signal but non-positive Sharpe",
            **{**blank, "candidate_sharpe": s_c, "orthogonal_ir": s_c,
               "portfolio_sharpe_after": max(s_c, 0.0), "gain": max(s_c, 0.0),
               "n_eff_before": 0.0, "n_eff_after": 1.0 if s_c > 0 else 0.0})

    n = min(cand.shape[0], inc.shape[0])
    cand, inc = cand[:n], inc[:n]
    if n < min_overlap:
        return Admission(False, f"only {n} overlapping obs (<{min_overlap}) -- correlation to the "
                                "book is not yet measurable, so a duplicate cannot be ruled out",
                         **{**blank, "n_overlap": n})

    port = _portfolio_series(inc)
    if not np.all(np.isfinite(port)):
        return Admission(False, "incumbent composite is non-finite (a zero-variance column?)",
                         **{**blank, "n_overlap": n})

    s_c = _sharpe(cand, periods_per_year)
    s_p = _sharpe(port, periods_per_year)

    with np.errstate(invalid="ignore"):
        rho_hat = float(np.corrcoef(cand, port)[0, 1])
    if not np.isfinite(rho_hat):
        return Admission(False, "correlation undefined (zero-variance series)",
                         **{**blank, "candidate_sharpe": s_c, "portfolio_sharpe": s_p,
                            "n_overlap": n})

    rho = _fisher_upper(rho_hat, n)
    mean_c_before = _mean_pairwise(inc)
    k = inc.shape[1]
    n_eff_before = _n_eff(k, mean_c_before)
    # After admission the cohort is k+1 wide; approximate its mean pairwise correlation by mixing
    # the incumbent mean with the candidate's k new pairs, using the CONSERVATIVE rho.
    pairs_before = k * (k - 1) / 2
    mean_c_after = ((mean_c_before * pairs_before + rho * k) / (pairs_before + k)
                    if (pairs_before + k) > 0 else rho)
    n_eff_after = _n_eff(k + 1, mean_c_after)

    common = {"candidate_sharpe": s_c, "portfolio_sharpe": s_p, "rho_hat": rho_hat,
              "rho_used": rho, "hurdle": rho * s_p, "n_overlap": n,
              "n_eff_before": n_eff_before, "n_eff_after": n_eff_after}

    if s_p <= 0.0:
        # A book with no measured edge cannot set a hurdle; falling back to standalone merit here
        # would quietly restore the very gate this module exists to replace, so it fails closed.
        return Admission(False, "incumbent portfolio Sharpe is non-positive -- fix the book before "
                                "admitting against it", orthogonal_ir=0.0,
                         portfolio_sharpe_after=s_p, gain=0.0, **common)

    if rho >= 0.999:
        return Admission(False, f"rho upper bound {rho:.3f} -- indistinguishable from the book "
                                "already held", orthogonal_ir=0.0, portfolio_sharpe_after=s_p,
                         gain=0.0, **common)

    ir = (s_c - rho * s_p) / math.sqrt(1.0 - rho * rho)
    # Only the ORTHOGONAL component can add. A candidate whose IR is negative is worse than nothing
    # once its correlation is paid for, however good its standalone number looks.
    s_after = math.sqrt(s_p * s_p + ir * ir) if ir > 0 else s_p
    gain = s_after - s_p

    if ir <= 0:
        return Admission(False, f"standalone Sharpe {s_c:.3f} does not clear the correlation "
                                f"hurdle rho*S_p = {rho:.3f}*{s_p:.3f} = {rho * s_p:.3f} -- this "
                                "is the book it already owns",
                         orthogonal_ir=ir, portfolio_sharpe_after=s_p, gain=0.0, **common)

    if gain < min_gain:
        return Admission(False, f"clears the hurdle but adds only {gain:+.4f} Sharpe (<{min_gain}) "
                                "-- inside estimation noise",
                         orthogonal_ir=ir, portfolio_sharpe_after=s_after, gain=gain, **common)

    return Admission(True, f"adds {gain:+.4f} portfolio Sharpe ({s_p:.3f} -> {s_after:.3f}) at "
                           f"rho<={rho:.3f}; effective bets {n_eff_before:.2f} -> "
                           f"{n_eff_after:.2f}",
                     orthogonal_ir=ir, portfolio_sharpe_after=s_after, gain=gain, **common)
