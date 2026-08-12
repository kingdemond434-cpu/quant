"""ORDER-SENSITIVE DECAY BAR (R0312): does this edge get WORSE as it goes on?

WHY IT EXISTS, AND WHY DSR/PSR CANNOT ANSWER IT. Every statistic the gauntlet uses -- Sharpe,
DSR, PSR -- is a function of the return DISTRIBUTION, so it is invariant to the ORDER of the
observations. Shuffle a backtest and DSR does not move. But "the first half carried it and the
second half is dead" and "it worked evenly throughout" are the same distribution and completely
different edges, and only the second one is worth capital. L1.19 says hunt replacements BEFORE
advantages die, and L1.30 counts births against deaths; neither is answerable with an
order-invariant statistic. This module is the missing half.

THE CONSTRUCTION. Split the record into pre-registered sub-periods, take a one-sided p-value per
sub-period, and combine them with Edgington's mean-p: under the null of no edge each p is
Uniform(0,1), so their SUM is Irwin-Hall(n) and the combined error rate is its CDF. Order enters
through the SPLIT -- early sub-periods and late sub-periods are combined separately and compared.

WHAT WAS WRONG WITH THE PUBLISHED FORMULA, MEASURED RATHER THAN ASSUMED. The Irwin-Hall CDF is an
alternating sum of terms as large as C(n,k)*(x-k)^n, and in float arithmetic it suffers
catastrophic cancellation: computed naively at p_mean=0.8 it returns

        n=30  1.0000 (already wrong in the 7th place)      n=50  -3733.68
        n=40  0.9832 (true value 1.000000)                 n=80  -2.15e16

as a PROBABILITY. R0312 recorded this as "returns 8.53 at p_mean=0.8/N=5"; that specific figure
did not reproduce here (the correct value at n=5 is 0.991667, and the usual untruncated-sum error
gives 1.0), so the row's number is not confirmed -- but the defect class is real and considerably
worse than the row states, being a LARGE-n failure rather than a small-n one. That matters
directly: a decay bar wants many sub-periods, which is exactly where the naive formula explodes.

So the sum here is EXACT (Fraction), never float, and the domain is guarded at both ends. The
cost is real but bounded and it buys an answer that cannot be quietly wrong.

THE WINDOW IS PRE-REGISTERED, WHICH IS THE WHOLE DISCIPLINE. A published exploit of this metric
improves it by four orders of magnitude by DELETING a losing sub-period. Choosing the split, the
sub-period count, or the start date after seeing the result turns the bar into a search for the
kindest window. _SPLIT and _MIN_PERIODS are frozen constants for that reason, and
`decay_verdict` takes its segmentation from the caller only so tests can drive it -- production
callers pass nothing and get the frozen values.

NOTHING HERE PROMOTES ANYTHING. This is a DECAY detector for records the desk already has, not a
gauntlet gate. It grants no promotion authority, moves no threshold, and returns UNDERPOWERED
rather than a verdict when there are too few sub-periods to say anything (L1.28a).
"""
from __future__ import annotations

from fractions import Fraction
from math import comb, factorial, floor

#: PRE-REGISTERED, and frozen before any record was scored with them. Changing either of these
#: after seeing a verdict is the window-shopping exploit this module documents.
_SPLIT = 0.5          # early half vs late half
_MIN_PERIODS = 4      # below this, the mean-p combination has no resolution worth reporting

UNDERPOWERED = "UNDERPOWERED"
DECAYING = "DECAYING"
STABLE = "STABLE"
STRENGTHENING = "STRENGTHENING"


def irwin_hall_cdf(x: float, n: int) -> float:
    """P(sum of n iid Uniform(0,1) <= x). EXACT: the alternating sum is done in rationals.

    Float evaluation of this sum is not merely imprecise, it diverges -- at n=50 it returns
    -3733.68 and at n=80 it returns -2.15e16, both as probabilities. The domain is clamped at
    both ends because the summation formula is only valid on [0, n], and an unguarded call with
    x outside it silently returns a number rather than refusing.
    """
    if n < 1:
        raise ValueError(f"n must be >= 1, got {n}")
    if x <= 0:
        return 0.0
    if x >= n:
        return 1.0
    xf = Fraction(x).limit_denominator(10**9)
    total = sum(Fraction((-1) ** k) * comb(n, k) * (xf - k) ** n for k in range(floor(x) + 1))
    return float(total / factorial(n))


def mean_p_error_rate(pvals: list[float]) -> float:
    """Edgington mean-p combination: the chance n null p-values would look this good together.

    Small = the sub-periods agree there is something there.

    TWO ASSUMPTIONS, AND BOTH ARE THE CALLER'S TO HONOUR, because neither is checkable from the
    numbers alone -- a violated one produces a value that still looks exactly like a probability:

      * each p is a GENUINE one-sided p-value (something merely p-shaped makes the Uniform(0,1)
        null false);
      * the p-values are INDEPENDENT. Sub-periods cut from overlapping windows are not, and
        positive dependence makes this read far more significant than it is. The first caller
        here (signal_halflife) strides its rolling windows to non-overlapping ones for exactly
        this reason, at a real cost in resolution.
    """
    if not pvals:
        raise ValueError("no p-values to combine")
    if any(not 0.0 <= p <= 1.0 for p in pvals):
        raise ValueError(f"p-values must lie in [0,1], got {[p for p in pvals if not 0 <= p <= 1]}")
    return irwin_hall_cdf(sum(pvals), len(pvals))


def decay_verdict(pvals: list[float], *, split: float = _SPLIT,
                  min_periods: int = _MIN_PERIODS) -> dict[str, object]:
    """Compare the EARLY sub-periods against the LATE ones at the pre-registered split.

    Returns the two combined error rates and a verdict. The comparison is the order-sensitive
    part: mean-p is symmetric in its inputs, so combining the halves SEPARATELY is what makes the
    sequence matter. Refuses rather than guesses below `min_periods`.
    """
    n = len(pvals)
    if n < min_periods:
        return {"verdict": UNDERPOWERED, "n_periods": n,
                "why": f"{n} sub-periods < {min_periods} pre-registered minimum -- a decay claim "
                       "from this record would be a story about noise"}
    cut = max(1, min(n - 1, round(n * split)))
    early, late = pvals[:cut], pvals[cut:]
    e_early, e_late = mean_p_error_rate(early), mean_p_error_rate(late)
    # The error rate is a CDF of the p-sum: HIGHER means the sub-periods looked WORSE. So decay
    # is late > early. Reported as the raw pair, never as a single collapsed score, because the
    # two halves are the evidence and a reader must be able to see both.
    verdict = STABLE
    if e_late > e_early:
        verdict = DECAYING
    elif e_early > e_late:
        verdict = STRENGTHENING
    return {"verdict": verdict, "n_periods": n, "split_at": cut,
            "error_rate_early": round(e_early, 6), "error_rate_late": round(e_late, 6),
            "n_early": len(early), "n_late": len(late)}
