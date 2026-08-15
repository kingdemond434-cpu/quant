"""PORTFOLIO VOLATILITY TARGETED AT THE GROWTH OPTIMUM -- exposure that leans in and sheds.

THE IDENTITY THIS RESTS ON, and it is worth stating because it makes the target computable rather
than chosen. The growth-optimal leverage is Kelly, f* = mu/sigma^2 = S/sigma for a book with
Sharpe S. The volatility that book actually RUNS at is f* * sigma = S. So:

    THE GROWTH-OPTIMAL PORTFOLIO VOLATILITY IS THE SHARPE RATIO ITSELF.

A Sharpe-1 book maximises E[log wealth] at 100% annualised volatility; a Sharpe-0.5 book at 50%.
Not a preference, not a risk budget somebody picked -- the same arithmetic as Kelly, expressed in
the units the portfolio is actually measured in. Taking a fraction of Kelly scales it identically:
half-Kelly targets S/2.

WHY THIS BEATS A FIXED GROSS AT THE SAME AVERAGE EXPOSURE. Realised volatility is persistent --
quiet weeks cluster, violent ones cluster -- while returns are not. A fixed gross therefore runs
too hot in the violent clusters and too cold in the quiet ones, and the variance drag term
(f^2 sigma^2 / 2) punishes the hot half more than the cold half rewards. Holding EXPOSURE constant
and letting risk float is the choice that maximises nothing in particular; holding RISK constant
is the one that tracks the objective.

**IT ADDS NO EDGE AND MUST NOT BE SOLD AS ONE.** Vol targeting does not improve mu. It stabilises
the ratio the objective is a function of, which raises the geometric mean at the same arithmetic
mean. That is a real gain and a bounded one.

**DIMINISHING RETURNS ARE THE WHOLE POINT AND THEY ARE ENFORCED.** Gross is capped: unlevered books
at 1.0, levered ones at whatever `leverage_policy` permits. Past the Kelly point more exposure
lowers growth, so a vol target computed from a flattering Sharpe must never be able to push the
book past it -- the cap and the target come from the same estimate, so the cap binds first.

**AN UNMEASURED SIGMA SHEDS, IT DOES NOT LEAN IN.** Missing volatility returns the FLOOR gross, not
the ceiling. The asymmetry is deliberate: being under-exposed costs return, being over-exposed on
an unmeasured tape costs the account.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

__all__ = [
    "DEFAULT_MAX_GROSS",
    "DEFAULT_MIN_GROSS",
    "REBALANCE_BAND",
    "GrossDecision",
    "gross_exposure",
    "growth_optimal_vol",
]

#: Unlevered ceiling: a spot account cannot hold more than it paid for. Levered callers pass the
#: leverage the policy permits, which is itself Kelly-bounded, so the cap always comes from the
#: same estimate as the target and binds before the target can overshoot it.
DEFAULT_MAX_GROSS = 1.0

#: Never fully flat from a vol reading alone. A book that de-grosses to zero on one violent week
#: stops compounding entirely and has to time its own re-entry, which is a second, harder bet that
#: nobody asked for. Shedding to 20% is risk control; going to cash is a market call.
DEFAULT_MIN_GROSS = 0.2

#: Gross moves only when it moves MEANINGFULLY. Sigma is estimated and wobbles daily; trading every
#: wobble pays turnover for noise. 10% of current gross is roughly the point where the expected
#: variance saving exceeds the round-trip cost on this book.
REBALANCE_BAND = 0.10

_PPY = 365.0


@dataclass(frozen=True)
class GrossDecision:
    """Gross exposure with the estimate behind it. Never published bare -- a gross without its
    sigma is a number nobody can audit after the fact."""

    gross: float
    target_vol: float | None
    realised_vol: float | None
    raw_gross: float | None
    state: str
    why: str

    def as_row(self) -> dict[str, Any]:
        return {"gross": round(self.gross, 4),
                "target_vol": None if self.target_vol is None else round(self.target_vol, 4),
                "realised_vol": None if self.realised_vol is None else round(self.realised_vol, 4),
                "raw_gross": None if self.raw_gross is None else round(self.raw_gross, 4),
                "state": self.state, "why": self.why}


def growth_optimal_vol(sharpe: float, *, kelly_fraction: float = 0.5) -> float:
    """The ANNUAL portfolio volatility that maximises E[log wealth]: `kelly_fraction * sharpe`.

    Falls out of Kelly directly -- f* = S/sigma, so the volatility run at the optimum is f*sigma =
    S -- which is why this function has no free parameters beyond the fraction of Kelly taken.

    A NON-POSITIVE SHARPE TARGETS ZERO VOLATILITY. A book with no measured edge has a
    growth-optimal exposure of zero, and inventing a floor here would be inventing an edge.
    """
    return max(0.0, float(kelly_fraction) * float(sharpe))


def gross_exposure(realised_vol_daily: float | None, *, sharpe: float | None,
                   kelly_fraction: float = 0.5, max_gross: float = DEFAULT_MAX_GROSS,
                   min_gross: float = DEFAULT_MIN_GROSS,
                   current_gross: float | None = None) -> GrossDecision:
    """Gross exposure from measured volatility, clamped, with a rebalance band.

    `realised_vol_daily` is the PORTFOLIO's daily standard deviation -- the book's own return
    series, not the average of its constituents'. Those differ by exactly the diversification the
    book provides, and using the constituent average would understate gross by the amount the
    portfolio construction earned.
    """
    if (realised_vol_daily is None or not math.isfinite(realised_vol_daily)
            or realised_vol_daily <= 0):
        return GrossDecision(
            gross=min_gross, target_vol=None, realised_vol=None, raw_gross=None,
            state="UNMEASURED",
            why=("portfolio volatility UNMEASURED -- shedding to the floor gross "
                 f"{min_gross:.0%} rather than leaning in. Being under-exposed costs return; "
                 "being over-exposed on a tape nobody has measured costs the account"))
    if sharpe is None or not math.isfinite(sharpe):
        return GrossDecision(
            gross=min_gross, target_vol=None, realised_vol=realised_vol_daily, raw_gross=None,
            state="NO-EDGE-ESTIMATE",
            why=("no Sharpe estimate, so the growth-optimal volatility cannot be computed. The "
                 "target is a function of the EDGE, and without one there is no optimum to aim at"))

    sigma_ann = realised_vol_daily * math.sqrt(_PPY)
    target = growth_optimal_vol(sharpe, kelly_fraction=kelly_fraction)
    raw = target / sigma_ann if sigma_ann > 0 else 0.0
    gross = max(min_gross, min(raw, max_gross))

    state = "MEASURED"
    if raw > max_gross:
        state = "CAPPED"
    elif raw < min_gross:
        state = "FLOORED"

    # THE BAND, applied last: a target inside it is not worth the turnover, and re-deriving gross
    # daily from a wobbling sigma would pay costs for noise. Applied AFTER clamping so the band
    # cannot hold the book above a cap it has just breached.
    banded = ""
    if (current_gross is not None and current_gross > 0
            and abs(gross - current_gross) < REBALANCE_BAND * current_gross):
        banded = (f"; held at the current {current_gross:.2f} -- the move to {gross:.2f} is "
                  f"inside the {REBALANCE_BAND:.0%} band and would pay turnover for noise")
        gross = current_gross

    return GrossDecision(
        gross=gross, target_vol=target, realised_vol=sigma_ann, raw_gross=raw, state=state,
        why=(f"Sharpe {sharpe:.2f} x {kelly_fraction:g}-Kelly => growth-optimal portfolio vol "
             f"{target:.0%}/yr; realised {sigma_ann:.0%}/yr => gross {raw:.2f}"
             + {"MEASURED": "",
                "CAPPED": f", CAPPED at {max_gross:.2f} -- past the cap more exposure lowers "
                          "growth, and the cap comes from the same estimate as the target",
                "FLOORED": f", FLOORED at {min_gross:.2f} -- shedding to zero would stop the "
                           "book compounding and require timing a re-entry, a second bet"}[state]
             + banded))
