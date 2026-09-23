"""What a sleeve is worth TO THE BOOK, not on its own. Applied as a sizing multiplier.

WHY THIS EXISTS (principal, 2026-08-29)

    "Promotion must consider portfolio contribution. A certified clone that adds no independent
     E[log W] should not receive the same allocation as a diversifying edge."

Until now every promoted sleeve got the same authority, so the book allocated on standalone
merit. That is the wrong objective and it fails in a specific, expensive direction: the search
finds correlated variants far more easily than it finds genuinely new mechanisms, so equal
allocation systematically concentrates capital into whatever the desk happened to over-search.
This desk has measured that concentration -- n_eff ~5.5 independent bets across 23 certificates.
Sizing them equally means the book carries roughly five bets wearing twenty-three name tags,
at twenty-three bets' worth of gross risk.

THE ARITHMETIC THAT MATTERS. Under log-wealth growth, what a new sleeve adds is not its own
expectancy but its expectancy AFTER projecting out what the book already earns. Two sleeves at
identical Sharpe are worth wildly different amounts: at rho = 0 the second one is a whole new
bet, at rho = 0.98 it is the first one bought twice at double the risk. Standalone metrics
cannot see the difference because the difference is not in either sleeve, it is between them.

WEIGHT = 1 - rho, FLOORED. Deliberately linear rather than the sqrt(1 - rho^2) variance split.
sqrt(1-rho^2) is 0.20 at rho = 0.98 -- it still hands a fifth-weight allocation to a sleeve that
is arithmetically the same bet -- because it measures independent VARIANCE, and a clone's
variance being partly independent does not make its EDGE independent. Linear reaches the floor
where the economics do.

A NEGATIVE CORRELATION GETS FULL WEIGHT, NOT A BONUS. It is tempting to size a hedge UP, and
this refuses to: a measured negative correlation over a short forward window is far more often
sampling noise than a real hedge, and rewarding it would make the noisiest estimates the biggest
positions. Full weight, never more.

THE FLOOR IS NOT ZERO. A clone is throttled to `MIN_WEIGHT`, not switched off, because the
correlation is an ESTIMATE from a short forward record and this must not be the mechanism that
silently kills a sleeve. Retirement is a decision with its own rules and its own evidence bar;
this only ever sizes.
"""
from __future__ import annotations

import math
from collections.abc import Sequence

#: Smallest multiplier a certified sleeve can be sized to. Non-zero on purpose -- see above; a
#: sizing rule must never become a back-door retirement.
MIN_WEIGHT = 0.10

#: Below this many overlapping observations the correlation is not an estimate, it is a rumour.
#: An unmeasurable correlation returns full weight: absence of evidence of redundancy is not
#: evidence of redundancy, and throttling on a rumour would penalise every NEW sleeve -- exactly
#: the diversifying ones this is meant to protect.
MIN_OVERLAP = 20


def _pearson(a: Sequence[float], b: Sequence[float]) -> float | None:
    n = min(len(a), len(b))
    if n < MIN_OVERLAP:
        return None
    a, b = list(a[:n]), list(b[:n])
    ma, mb = sum(a) / n, sum(b) / n
    va = sum((x - ma) ** 2 for x in a)
    vb = sum((x - mb) ** 2 for x in b)
    if va <= 0 or vb <= 0:
        return None
    cov = sum((a[i] - ma) * (b[i] - mb) for i in range(n))
    return cov / math.sqrt(va * vb)


def portfolio_weight(sleeve_returns: Sequence[float],
                     book_returns: Sequence[float]) -> tuple[float, str]:
    """Sizing multiplier for `sleeve_returns` given the book it is joining, and why.

    `book_returns` is the aggregate per-period return of everything already live, aligned to the
    same periods as `sleeve_returns`. An empty book means the first sleeve carries full weight --
    it cannot be redundant with nothing.
    """
    if not book_returns:
        return 1.0, "empty book: nothing to be redundant with"

    rho = _pearson(sleeve_returns, book_returns)
    if rho is None:
        return 1.0, (f"correlation unmeasurable (<{MIN_OVERLAP} aligned observations or no "
                     f"variance); full weight, because unmeasured is not redundant")
    if rho <= 0:
        return 1.0, f"rho={rho:+.2f} <= 0: full weight, never a bonus (short-window noise)"

    w = max(MIN_WEIGHT, 1.0 - rho)
    return w, f"rho={rho:+.2f} to the live book -> {w:.2f}x authority"


def effective_bets(weights: Sequence[float]) -> float:
    """How many independent bets a set of weights actually represents.

    The participation ratio (sum w)^2 / sum(w^2). Reported alongside the raw sleeve count so the
    book's real diversification is visible: twenty-three sleeves at n_eff 5.5 is a fact the desk
    should have to look at, not one it can average away.
    """
    ws = [w for w in weights if w > 0]
    if not ws:
        return 0.0
    return (sum(ws) ** 2) / sum(w * w for w in ws)
