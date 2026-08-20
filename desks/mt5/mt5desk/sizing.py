"""Solve the bet size that just fits a drawdown budget. One implementation.

THE BUG THIS EXISTS TO KILL

Three research scripts each carried their own copy of a bisection like:

    eq = np.cumprod(1.0 + q * x)
    if (1.0 - eq / np.maximum.accumulate(eq)).max() > target:
        hi = q
    else:
        lo = q

At a large enough q some day has `1 + q*x <= 0` -- the account is not drawn
down, it is GONE -- and from there the cumulative product goes negative, the
drawdown expression yields NaN or inf, and `NaN > target` evaluates to False.
So the search concludes the budget was respected and moves q UP. Every arm in
research/push_ceiling.py returned q = 2.0000, the hard upper bound, reporting
CAGR of +inf and -100%.

It is the worst shape of bug this desk keeps finding: a catastrophic outcome
that reads as a passing check. It did not announce itself in growth_now.py only
because that series never reached ruin inside the search bounds -- the defect
was there too, waiting for a sleeve with one bad enough day.

WHAT CORRECT LOOKS LIKE

Ruin is worse than any drawdown target, so it must compare as such. And the
search is bounded above by the q at which ruin FIRST becomes possible, which is
knowable in closed form from the worst single return: any q >= 1/|min(x)| can
wipe the account out on that day alone, so there is no reason to look there.
"""
from __future__ import annotations

import numpy as np

__all__ = ["max_drawdown", "q_for_drawdown", "ruin_q", "solve_size", "NO_LOSS_CAP"]

#: Fallback ceiling when a return series has no losing day at all. Such a series
#: has zero drawdown at every size, so a drawdown budget simply does not bind on
#: it; this is a declared stand-in, not a computed answer.
NO_LOSS_CAP = 10.0


def ruin_q(x: np.ndarray) -> float:
    """The smallest q at which a single observed day can wipe the account out.

    With fractional sizing, equity multiplies by (1 + q*x). The worst day sets
    the limit: q >= 1/|min(x)| makes that day a total loss. Searching above this
    is not conservative-but-fine, it is searching a region where the equity
    curve stops being a curve.
    """
    x = np.asarray(x, float)
    worst = float(np.nanmin(x)) if x.size else 0.0
    return float("inf") if worst >= 0 else 1.0 / abs(worst)


def max_drawdown(x: np.ndarray, q: float) -> float:
    """Peak-to-trough fraction for returns `x` at size `q`. Ruin returns 1.0.

    Returning 1.0 rather than NaN is the whole point: a caller comparing this
    against a budget must see ruin as a violation, and NaN compares False
    against everything.
    """
    x = np.asarray(x, float)
    growth = 1.0 + q * x
    if not np.all(np.isfinite(growth)) or np.any(growth <= 0.0):
        return 1.0
    # Overflow is EXPECTED while bisecting: the search deliberately probes sizes
    # that may run the product past float range, and the isfinite check below is
    # how that is handled. Letting the warning escape would turn a controlled
    # probe into a crash under `-W error`.
    with np.errstate(over="ignore", invalid="ignore"):
        eq = np.cumprod(growth)
        if not np.all(np.isfinite(eq)) or np.any(eq <= 0.0):
            return 1.0
        return float((1.0 - eq / np.maximum.accumulate(eq)).max())


def solve_size(measure, x: np.ndarray, target: float, *, hi: float | None = None,
               iters: int = 90) -> float:
    """The SEARCH, factored out so a different objective does not need a different bisection.

    `measure(q) -> float` is any risk statistic that rises with q; the answer is the largest q
    whose measure stays within `target`, returned from the LOW side of the bracket so it is a
    size that satisfied the budget rather than one that just breached it.

    **WHY THIS EXISTS SEPARATELY FROM `q_for_drawdown`.** `research/admission.py` solves for the
    MEAN OF THE FIVE DEEPEST TROUGHS rather than the single worst drawdown -- a legitimately
    different objective, and one `q_for_drawdown` cannot express. Before this it therefore had to
    carry its own bisection, and "one implementation" quietly became "one implementation plus the
    ones with a different objective", which is how the shape spreads. Now the objective varies and
    the SEARCH does not: the ruin bound and the low-side return live here, once.

    The bound still comes from the data -- `ruin_q(x)`, the q at which one observed day can wipe
    the account out -- so no caller can search past ruin regardless of what its measure returns
    there.
    """
    x = np.asarray(x, float)
    x = x[np.isfinite(x)]
    if x.size == 0:
        return 0.0
    cap = ruin_q(x)
    hi = min(hi, cap) if hi is not None else cap
    if not np.isfinite(hi):
        hi = NO_LOSS_CAP
    lo = 0.0
    for _ in range(iters):
        mid = (lo + hi) / 2
        if measure(mid) > target:
            hi = mid
        else:
            lo = mid
    return lo


def q_for_drawdown(x: np.ndarray, target: float, *, hi: float | None = None,
                   iters: int = 90) -> float:
    """Largest q whose worst drawdown stays within `target`.

    Returns the LOW side of the bracket, so the answer is always a size that
    satisfied the budget rather than one that just breached it.
    """
    x = np.asarray(x, float)
    x = x[np.isfinite(x)]
    if x.size == 0:
        return 0.0
    cap = ruin_q(x)
    hi = min(hi, cap) if hi is not None else cap
    if not np.isfinite(hi):
        # A series with no losing day has zero drawdown at every size, so a
        # drawdown budget cannot size it -- the honest answer is "this
        # constraint does not bind", and the caller needs a different one.
        # Returning a huge number instead would look like an answer.
        hi = NO_LOSS_CAP
    lo = 0.0
    for _ in range(iters):
        mid = (lo + hi) / 2
        if max_drawdown(x, mid) > target:
            hi = mid
        else:
            lo = mid
    return lo
