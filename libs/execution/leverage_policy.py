"""LEVERAGE AS MUCH AS GROWTH PERMITS -- and growth permits a specific, computable number.

THE PRINCIPAL'S INSTRUCTION, 2026-08-15: no fixed ceiling, minimum 3x, "as much as growth permits".
That phrase has an exact answer and this module computes it rather than choosing one.

**THE OBJECTIVE IS MAX E[log WEALTH], SO THE CEILING IS KELLY AND NOTHING ELSE.** For a book with
excess drift mu over borrow cost and volatility sigma, levering by f gives a geometric growth rate

    g(f) = f*mu - f^2 * sigma^2 / 2

That is a DOWNWARD PARABOLA, and the three facts that follow are arithmetic, not caution:

  * it is maximised at  f* = mu / sigma^2   -- the Kelly leverage,
  * beyond f* MORE LEVERAGE MEANS LESS GROWTH, because variance drag grows quadratically while
    return grows linearly,
  * at f = 2f* the growth rate is exactly ZERO, and past it a book with positive expected return
    compounds to zero almost surely.

So "as much as growth permits" is not an appetite to be turned up. It is a maximum, it can be
measured, and it is frequently far below what a venue will lend. A book at 8x whose Kelly is 1.8x
is not being aggressive -- it is sitting past the zero-growth line, taking more risk for LESS
terminal wealth. That is the one configuration this desk's own objective forbids outright.

**THERE IS NO HARDCODED CEILING HERE.** If the measured edge supports 10x, this returns 10x. The
bound moves with the evidence, which is what was asked for. What it will not do is return a number
the measurement does not support, because that number is not more growth -- it is less.

**HALF-KELLY IS THE DEFAULT FRACTION, AND THAT IS A STATED CHOICE.** Full Kelly assumes mu and
sigma are known. They are estimated, from a finite sample, on a book with NO forward evidence, and
the growth curve is far steeper on the right of f* than the left: overestimating mu by 2x puts a
full-Kelly book at 2x Kelly, which is the zero-growth point. Half-Kelly gives up 25% of the
theoretical growth rate and roughly halves the volatility of the outcome.

**THE LIQUIDATION CONSTRAINT BINDS SEPARATELY AND THE SMALLER OF THE TWO WINS.** Kelly is about
compounding; liquidation is about surviving to compound. Cross margin closes the book at level
1.10, so a k-sigma move must fit inside the liquidation distance:

    L_survive = LIQ / ((LIQ - 1) + k*sigma_daily)

Kelly can permit leverage that a liquidation would take away before the edge arrives. Neither
constraint substitutes for the other.

**WHAT NONE OF THIS PROTECTS AGAINST.** Both bounds size against ORDINARY volatility drawn from
the recent sample. Gaps, depegs, exchange outages and liquidation cascades deliver moves no
trailing sigma anticipates, and a cascade is precisely the regime where depth vanishes. This is a
growth and survival calculation, not a tail-risk control, and must never be described as one.
"""

from __future__ import annotations

import math
from typing import Any

from libs.execution.binance_margin_live import LIQUIDATION_LEVEL

__all__ = [
    "DEFAULT_KELLY_FRACTION",
    "DEFAULT_SIGMA_MULTIPLE",
    "MIN_LEVERAGE",
    "VENUE_MAX_LEVERAGE",
    "LeverageDecision",
    "choose",
    "growth_rate",
    "kelly_leverage",
    "leverage_for_distance",
    "realised_vol",
]

#: The principal's stated minimum, 2026-08-15. Binds even when the measurement asks for less, and
#: every decision that hits it is labelled so a floored number is never read as a measured one.
MIN_LEVERAGE = 3.0

#: NOT a risk preference -- what the venue will actually lend on cross margin. A policy that
#: returned 12x when Binance tops out lower would produce an order the venue refuses, and a refused
#: order at rebalance time is an unhedged intent nobody notices. Raise it if the account tier does.
VENUE_MAX_LEVERAGE = 10.0

#: Fraction of Kelly taken. Half, because mu and sigma are ESTIMATED and the growth curve is far
#: steeper right of the optimum than left: overestimating mu by 2x puts a full-Kelly book exactly
#: at the zero-growth point. Costs 25% of the theoretical growth rate; roughly halves outcome
#: volatility. A stated choice, not a derived constant.
DEFAULT_KELLY_FRACTION = 0.5

#: Daily standard deviations that must fit inside the liquidation distance. 3 is ~1-in-740 under a
#: normal and meaningfully more common under crypto returns, which have fat left tails.
DEFAULT_SIGMA_MULTIPLE = 3.0

#: Below this a volatility estimate is a rounding artifact, and dividing by it manufactures enormous
#: leverage out of a quiet week. Treated as UNMEASURED.
_MIN_CREDIBLE_SIGMA = 0.002

#: Trading days per year for crypto -- it does not close.
_PPY = 365.0


class LeverageDecision(dict[str, Any]):
    """A decision carrying its own reasoning, dict-shaped so it lands in a JSON report as-is. A
    leverage number published without the sigma, the Kelly bound and the survivable move behind it
    is the half of the trade that looks like opportunity."""


def realised_vol(returns: list[float] | Any, *, window: int = 30) -> float | None:
    """Trailing DAILY standard deviation, or None when it cannot be estimated.

    NONE, NEVER ZERO. Zero divides into infinite leverage, so the one value that must never be
    invented here is exactly the one a missing-data path would most naturally produce.
    """
    r = [float(x) for x in list(returns)[-window:] if x is not None and math.isfinite(float(x))]
    if len(r) < 5:
        return None
    mean = sum(r) / len(r)
    sd = math.sqrt(sum((x - mean) ** 2 for x in r) / (len(r) - 1))
    return sd if sd >= _MIN_CREDIBLE_SIGMA else None


def kelly_leverage(mu_annual: float, sigma_annual: float, *, borrow_rate: float = 0.0) -> float:
    """f* = (mu - borrow) / sigma^2. The leverage that maximises the geometric growth rate.

    THE BORROW COST IS NOT OPTIONAL. Levered capital is rented, and margin interest comes off the
    numerator before anything is optimised. Omitting it overstates f* by exactly the rate the desk
    is paying, which is the direction that over-levers.

    Returns 0.0 when the excess drift is not positive: an edge that does not beat its own borrow
    cost is not made positive by borrowing more of it.
    """
    excess = float(mu_annual) - float(borrow_rate)
    if excess <= 0 or sigma_annual <= 0:
        return 0.0
    return excess / (sigma_annual ** 2)


def growth_rate(f: float, mu_annual: float, sigma_annual: float, *,
                borrow_rate: float = 0.0) -> float:
    """g(f) = f*(mu - borrow) - f^2 sigma^2 / 2. Published so the parabola can be printed rather
    than asserted -- the fastest way to see that 8x is on the far side of zero."""
    excess = float(mu_annual) - float(borrow_rate)
    return f * excess - (f ** 2) * (sigma_annual ** 2) / 2.0


def leverage_for_distance(distance: float, *, liquidation: float = LIQUIDATION_LEVEL) -> float:
    """The leverage whose liquidation sits exactly `distance` away -- the inverse of
    `binance_margin_live.liquidation_distance`. The two must agree or one of them is wrong."""
    if distance <= 0:
        return VENUE_MAX_LEVERAGE
    return liquidation / ((liquidation - 1.0) + distance)


def choose(daily_sigma: float | None, *, sharpe: float | None = None,
           kelly_fraction: float = DEFAULT_KELLY_FRACTION,
           k: float = DEFAULT_SIGMA_MULTIPLE, borrow_rate: float = 0.0,
           floor: float = MIN_LEVERAGE, ceiling: float = VENUE_MAX_LEVERAGE) -> LeverageDecision:
    """The leverage growth permits, bounded by survival, floored by the principal's instruction.

    `sharpe` is the book's ANNUAL Sharpe, which is how the desk already reports every strategy, and
    it is all Kelly needs: with mu = S*sigma, f* = S/sigma. Absent it, the growth bound cannot be
    computed and only the liquidation bound applies -- reported as such rather than silently
    dropping half the calculation.
    """
    if daily_sigma is None or not math.isfinite(daily_sigma) or daily_sigma < _MIN_CREDIBLE_SIGMA:
        return LeverageDecision(
            leverage=floor, state="UNMEASURED", floor_binding=True, sigma=None,
            kelly=None, survivable_move=None,
            why=("volatility UNMEASURED -- taking the principal's floor of "
                 f"{floor:.2f}x. Choosing more from an absent measurement would be inventing "
                 "confidence out of missing data, on the one path that can end the account"))

    sigma_ann = daily_sigma * math.sqrt(_PPY)
    survive = leverage_for_distance(k * daily_sigma)

    kelly = full = None
    if sharpe is not None and math.isfinite(sharpe):
        full = kelly_leverage(sharpe * sigma_ann, sigma_ann, borrow_rate=borrow_rate)
        kelly = full * kelly_fraction

    bounds = {"survival": survive, "venue/ceiling": ceiling}
    if kelly is not None:
        bounds["growth (Kelly)"] = kelly
    binding = min(bounds, key=lambda kname: bounds[kname])
    raw = bounds[binding]
    lev = max(floor, min(raw, ceiling))

    parts = [f"sigma {daily_sigma:.2%}/day ({sigma_ann:.0%} ann)"]
    if kelly is not None and full is not None:
        parts.append(f"full Kelly {full:.2f}x, {kelly_fraction:g}-Kelly {kelly:.2f}x "
                     f"(growth turns NEGATIVE beyond {2 * full:.2f}x)")
    parts.append(f"survival at k={k:g} allows {survive:.2f}x")
    parts.append(f"binding constraint: {binding} -> {raw:.2f}x")

    floored = raw < floor
    if floored:
        note = (f"BELOW the principal's floor, so {floor:.2f}x is taken ANYWAY. That is an "
                "instruction, not a calculation: the position is carried by the floor rather than "
                "by the measurement")
        if kelly is not None:
            mu = (sharpe or 0.0) * sigma_ann
            g_floor = growth_rate(floor, mu, sigma_ann, borrow_rate=borrow_rate)
            g_raw = growth_rate(raw, mu, sigma_ann, borrow_rate=borrow_rate)
            note += (f", and the objective says so: expected geometric growth is {g_floor:+.1%}/yr "
                     f"at {floor:.2f}x against {g_raw:+.1%}/yr at {raw:.2f}x")
        parts.append(note)

    return LeverageDecision(
        leverage=round(lev, 3), state="FLOOR BINDING" if floored else binding.upper(),
        floor_binding=floored, sigma=round(daily_sigma, 5), sigma_annual=round(sigma_ann, 4),
        kelly_full=None if full is None else round(full, 3),
        kelly=None if kelly is None else round(kelly, 3),
        zero_growth_leverage=None if full is None else round(2 * full, 3),
        survival_leverage=round(survive, 3), survivable_move=round(k * daily_sigma, 4),
        binding_constraint=binding, raw_leverage=round(raw, 3),
        why="; ".join(parts) + ". Sizes against ORDINARY volatility: gaps, depegs, outages and "
            "liquidation cascades deliver moves no trailing sigma anticipates, and this is not a "
            "tail-risk control")
