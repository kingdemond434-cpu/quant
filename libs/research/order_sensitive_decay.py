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

A DIRECTION IS ONLY CALLED OUTSIDE THE NULL BAND (R0467). The first version compared the two
halves with a bare `>`, which sounds conservative and is the opposite: STABLE then required exact
float equality of two continuous quantities, so it was UNREACHABLE, and every real record got a
direction. Measured over 20,000 pure-null records: DECAYING 10,045 / STRENGTHENING 9,955 /
STABLE 0. The verdict was a fair coin wearing a statistic's clothes -- and being fair is exactly
what made it survive review, because the module's own null test asserted symmetry (which held)
rather than refusal (which never did). ASK OF ANY VERDICT WHETHER ITS QUIETEST OUTCOME CAN
HAPPEN AT ALL: an outcome with zero probability is not a bar, and a gate that cannot return
"nothing here" carries no information about anything (L1.43).

NOTHING HERE PROMOTES ANYTHING. This is a DECAY detector for records the desk already has, not a
gauntlet gate. It grants no promotion authority, moves no threshold, and returns UNDERPOWERED
rather than a verdict when there are too few sub-periods to say anything (L1.28a). The band added
by R0467 tightens what it will CLAIM and loosens nothing: strictly fewer directional calls than
before, never more.
"""
from __future__ import annotations

from fractions import Fraction
from math import comb, factorial, floor

#: PRE-REGISTERED, and frozen before any record was scored with them. Changing either of these
#: after seeing a verdict is the window-shopping exploit this module documents.
_SPLIT = 0.5          # early half vs late half
_MIN_PERIODS = 4      # below this, the mean-p combination has no resolution worth reporting

#: Two-sided rate at which a PURE NULL record is allowed to be called DECAYING or STRENGTHENING.
_DIRECTION_ALPHA = 0.05

#: The band inside which the two halves are NOT DISTINGUISHABLE, so the verdict is STABLE.
#:
#: DERIVED, NOT TUNED. `mean_p_error_rate` is the CDF of the p-sum, so under the null the
#: probability integral transform makes each half's error rate EXACTLY Uniform(0,1), and the two
#: halves are built from disjoint p-values, hence independent. Their difference is therefore
#: triangular on [-1, 1] with density (1-|d|), giving the closed form
#:
#:     P(|D| > t) = (1 - t)^2   ->   t = 1 - sqrt(alpha)
#:
#: Measured against this module's own code over 20,000 null records of 14 windows: empirical
#: P(|D| > t) = 0.0484 against the 0.0500 target.
_NULL_BAND = 1.0 - _DIRECTION_ALPHA**0.5      # == 0.776393...

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
    #
    # THE BAND IS WHAT MAKES STABLE REACHABLE (R0467). Before it, the comparison was a bare `>`,
    # so STABLE required EXACT float equality of two continuous quantities and was therefore
    # unreachable on any real record: measured over 20,000 pure-null records, this function
    # returned DECAYING 10,045 times and STRENGTHENING 9,955 times and STABLE ZERO times -- a
    # coin flip published as a verdict, which is precisely the "manufacture decay out of noise"
    # failure the docstring of its own null test names. Live proof it was not theoretical: the
    # stablecoin_supply row flipped STRENGTHENING -> DECAYING overnight on 2026-08-12/13 off a
    # 0.036 gap between two halves that both read ~0.33, i.e. both saying nothing is there.
    diff = e_late - e_early
    verdict = STABLE
    if diff > _NULL_BAND:
        verdict = DECAYING
    elif -diff > _NULL_BAND:
        verdict = STRENGTHENING
    return {"verdict": verdict, "n_periods": n, "split_at": cut,
            "error_rate_early": round(e_early, 6), "error_rate_late": round(e_late, 6),
            "diff": round(diff, 6), "null_band": round(_NULL_BAND, 6),
            "n_early": len(early), "n_late": len(late)}
