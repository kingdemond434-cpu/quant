"""EFFECTIVE BREADTH -- how many INDEPENDENT bets the desk actually holds, not how many sleeves.

WHY THIS IS THE NUMBER THAT DECIDES THE RETURN TARGET. The desk's objective is max E[log wealth],
whose maximum is S^2/2 at the Kelly point. So a monthly target is a Sharpe requirement:

    7%/month = 125%/yr  ->  S = 1.58        3%/month = 43%/yr  ->  S = 0.92

and the only reliable way to raise S is breadth: k INDEPENDENT sleeves of individual Sharpe s
combine to s*sqrt(k). Leverage cannot do it -- past Kelly more leverage lowers growth -- and a
better single edge is a hope rather than a plan. Breadth is the one multiplier the desk controls.

**THE WORD DOING ALL THE WORK IS "INDEPENDENT", AND IT IS ROUTINELY ASSUMED.** Eleven momentum
variants are one bet wearing eleven hats. With equal pairwise correlation rho, n sleeves are worth

    k_eff = n / (1 + (n-1) * rho)

n=11 at rho=0.8 is k_eff 1.7, not 11 -- so a book that looks eleven-wide compounds like a book
under two-wide, and the difference is invisible in every count of strategies the desk publishes.

**RHO IS MEASURED OR IT IS UNMEASURED. IT IS NEVER ASSUMED TO BE ZERO.** Assuming independence is
the single most flattering error available here: it multiplies the projected Sharpe by sqrt(n)
while the book behaves like one position. With no overlapping live history there is no correlation
to measure, and this module says UNMEASURED and shows the whole rho curve rather than picking a
point on it. That is L1.28a applied to the number the desk's return target rests on.

**MARGINAL BREADTH IS WHERE RESEARCH SHOULD GO.** Adding a twelfth sleeve to a family the book is
already 0.8-correlated with buys almost nothing; adding the FIRST sleeve of an uncorrelated family
buys the most that is available anywhere. `marginal_breadth` ranks that directly, so effort goes
where the derivative is, not where the ideas happen to be.
"""

from __future__ import annotations

import math
from typing import Any

__all__ = [
    "combined_sharpe",
    "effective_breadth",
    "growth_at",
    "marginal_breadth",
    "report",
    "required_sharpe",
    "sharpe_needed_for_monthly",
]


def growth_at(sharpe: float) -> float:
    """Max geometric growth at the Kelly point: S^2/2. The objective, in one line."""
    return max(0.0, float(sharpe)) ** 2 / 2.0


def required_sharpe(annual_growth: float) -> float:
    """Inverse of `growth_at` -- the Sharpe a growth target implies. Turns "we need X%" into a
    research requirement instead of an aspiration."""
    return math.sqrt(2.0 * max(0.0, float(annual_growth)))


def sharpe_needed_for_monthly(monthly: float) -> dict[str, float]:
    """A monthly target, priced in Sharpe and in effective breadth at today's per-sleeve quality."""
    annual = (1.0 + float(monthly)) ** 12 - 1.0
    s = required_sharpe(annual)
    return {"monthly": float(monthly), "annual": annual, "required_sharpe": s}


def effective_breadth(n: int, rho: float | None) -> float | None:
    """k_eff = n / (1 + (n-1)*rho) for n equally-weighted sleeves with equal pairwise rho.

    None when rho is unmeasured -- NEVER n, and never a default. Returning n would be the claim
    that the sleeves are independent, which is exactly the assumption this function exists to stop
    anyone making silently.

    rho <= -1/(n-1) is refused rather than clipped: at that point the correlation matrix is not
    positive semi-definite, so it is a measurement error and not a spectacular diversification
    result. Reporting the enormous k_eff it implies would be arithmetic on impossible data.
    """
    n = int(n)
    if n <= 0:
        return 0.0  # an empty book holds no bets. Not 1, and not None -- this one IS measured.
    # ONE SLEEVE IS ONE BET WHATEVER RHO IS -- there is no pair to correlate, so this is not a
    # default standing in for a measurement and the UNMEASURED rule does not bite. Ordering the
    # rho check first would have made a one-sleeve book report None and read as a defect.
    if n == 1:
        return 1.0
    if rho is None or not math.isfinite(rho):
        return None
    denom = 1.0 + (n - 1) * float(rho)
    if denom <= 1e-9:
        return None
    return n / denom


def combined_sharpe(per_sleeve: float, n: int, rho: float | None) -> float | None:
    """s * sqrt(k_eff). None when rho is unmeasured, for the same reason."""
    k = effective_breadth(n, rho)
    return None if k is None else float(per_sleeve) * math.sqrt(k)


def marginal_breadth(existing_n: int, rho_within: float,
                     candidate_rho: float) -> dict[str, float]:
    """What ONE more sleeve adds, given how correlated it is with the book already held.

    THE ASYMMETRY THIS EXPOSES is the whole reason to compute it. A twelfth sleeve at rho 0.8 to a
    book of eleven adds almost nothing; the FIRST sleeve of a genuinely uncorrelated family adds
    more than the previous five put together. Research effort should follow the derivative, and
    without this it follows whichever idea arrived most recently.
    """
    n = max(0, int(existing_n))
    k_before = 0.0 if n == 0 else (effective_breadth(n, rho_within) or 0.0)
    # A book of `existing_n` at rho_within, plus one at candidate_rho to all of them. The exact
    # k_eff for the mixed matrix, not the equal-rho shortcut -- the shortcut would hide precisely
    # the case being measured.
    var = n + n * (n - 1) * rho_within + 1.0 + 2.0 * n * candidate_rho
    if n and (k_before <= 0.0 or var <= 1e-9):
        # NOT clipped to something plausible. A total variance at or below zero means the supplied
        # correlations describe a matrix that is not positive semi-definite, i.e. a measurement
        # error -- and the k_eff it implies would be a spectacular result computed from impossible
        # data, which is worse than an exception because it looks like an answer.
        raise ValueError(
            f"rho_within={rho_within} with candidate_rho={candidate_rho} at n={n} is not a "
            "positive semi-definite correlation structure -- fix the measurement, never size on it")
    k_after = ((n + 1) ** 2) / var
    return {"k_before": k_before, "k_after": k_after, "delta_k": k_after - k_before,
            "sharpe_multiplier": math.sqrt(k_after / k_before) if k_before > 0 else float("inf")}


def report(sleeves: dict[str, float], rho: float | None, *,
           target_monthly: float = 0.07) -> dict[str, Any]:
    """The whole picture: what is held, what it is worth, and what the target would require.

    `sleeves` maps name -> per-sleeve Sharpe. `rho` is the MEASURED average pairwise correlation,
    or None. The rho curve is always published, because a single point estimate on a number this
    load-bearing invites the reader to forget it was estimated at all.
    """
    n = len(sleeves)
    s_bar = (sum(sleeves.values()) / n) if n else 0.0
    need = sharpe_needed_for_monthly(target_monthly)
    k = effective_breadth(n, rho)
    s_combined = combined_sharpe(s_bar, n, rho)
    curve = [{"rho": r, "k_eff": effective_breadth(n, r),
              "combined_sharpe": combined_sharpe(s_bar, n, r),
              "monthly": ((1 + growth_at(combined_sharpe(s_bar, n, r) or 0.0)) ** (1 / 12)) - 1}
             for r in (0.0, 0.2, 0.4, 0.6, 0.8)]
    return {
        "n_sleeves": n, "mean_sleeve_sharpe": round(s_bar, 3),
        "rho": rho, "rho_state": "MEASURED" if rho is not None else "UNMEASURED",
        "effective_breadth": None if k is None else round(k, 2),
        "combined_sharpe": None if s_combined is None else round(s_combined, 3),
        "annual_growth": None if s_combined is None else round(growth_at(s_combined), 4),
        "target": need,
        "sleeves_needed_at_rho_0": (math.ceil((need["required_sharpe"] / s_bar) ** 2)
                                    if s_bar > 0 else None),
        "rho_curve": curve,
        "why": (
            "k_eff = n/(1+(n-1)rho). rho is "
            + ("MEASURED" if rho is not None else
               "UNMEASURED -- there is no overlapping live history to compute it from, and "
               "assuming independence is the most flattering error available here: it multiplies "
               "the projected Sharpe by sqrt(n) while the book behaves like one position")
            + ". The curve shows what the same sleeves are worth across the plausible range, "
              "because a point estimate on this number invites the reader to forget it was one"),
    }
