"""OVERNIGHT FINANCING -- the third cost, which this desk's backtests charge at zero.

`engine.Costs` models spread and commission. It does not model swap, and `book_years.py` says so
in its own assumptions list ("no slippage beyond the modelled cost, NO SWAP, no gap risk"). That
note reads like a rounding disclaimer. It is not, and the measurement is in this desk's own
trades:

    46.4% OF THE 15,932 BACKTESTED TRADES ACROSS THE GOLD AND AUDCAD BOOKS HOLD THROUGH AT LEAST
    ONE ROLLOVER STAMP, at a mean of 0.788 charged nights per trade.

Per sleeve it ranges from 22.0% (XAUUSD.ny_open) to 83.2% (XAUUSD.afternoon, 1.481 nights each).
The afternoon windows are not marginal cases: they signal at 17:00, wait up to 8 bars for a fill
and then run a 12-bar TTL, so by construction the modal afternoon trade is still open when the
broker charges. A cost charged on four trades in five is not a second-order omission.

**AND THEN THE MEASUREMENT SAYS THE EXPOSURE IS NOT DANGEROUS, WHICH IS THE ACTUAL FINDING.**
The count above is alarming in the wrong unit. What decides a sleeve is R, and one R on gold at
full lot is 1,800-3,075 account currency, because a session-range stop on a $3,300 instrument
across a 100oz contract is a large number. `swap_exposure.py` reports the rate that takes each
reproducible sleeve's edge to exactly zero:

    gold_asia        0.376 nights/trade, +0.2122R   ->  breakeven 1,734.31 per lot per night
    gold_london_am   0.834 nights/trade, +0.1529R   ->  breakeven   329.85
    gold_afternoon   1.481 nights/trade, +0.0957R   ->  breakeven   176.05   <- most exposed

A raw-spread broker charges XAUUSD in the tens per lot per night. Against 176.05 the worst sleeve
carries roughly an order of magnitude of headroom, and at a 20.00 rate the drag is 0.0109R against
a 0.0957R edge -- about 11% of the expectancy, real and worth modelling, and nowhere near a kill.

**SO THIS MODULE'S RESULT IS A NULL, AND THE NULL IS THE VALUABLE PART.** The hypothesis that a
46%-crossing book carried a material unmodelled cost was reasonable, checkable, and wrong by an
order of magnitude. Publishing it retires the worry permanently instead of leaving it to be
re-raised by the next session that notices `Costs` has no swap field.

The comparison that made it look dangerous is worth naming so it is not made again: gold's
modelled ROUND TRIP is 39.00 per lot, so one night of swap is indeed comparable to the entire
modelled cost. That is true and it is irrelevant, because BOTH are small against a 2,725 stop.
Two costs of similar size say nothing about whether either matters.

This desk has already shipped a cost defect of the other kind. `Costs` carries the forensics: gold
spread was passed in dollars per ounce into a field wanting dollars per lot, so "every gold
backtest on this desk has run very nearly spread-free" and the 3x cost stress meant to catch it
was stressing 3% up to 9%. `portfolio_projection.py` STILL passes 0.48 that way and does not call
`Costs.from_symbol` -- which is a live defect, unrelated to swap, found while measuring this one.

================================================================================================
WHAT THIS MODULE WILL NOT DO: INVENT THE RATE
================================================================================================

The honest input is the broker's actual swap table, and it is not in this repo. `gateway.py`
already reads realised `swap` off every closed deal, so a MEASURED rate is obtainable -- from the
account, not from a guess.

Until it is, `swap_per_lot` is None and every function here says UNMEASURED rather than zero.
That is L1.28a, and zero is the specific wrong answer: it is the value the desk is already
carrying, and defaulting to it would launder the omission into a modelled assumption.

**THE INVERSION IS THE DELIVERABLE IN THE MEANTIME.** `breakeven_swap_per_lot` asks the question
that does not need the rate: at this sleeve's measured expectancy and holding profile, WHAT SWAP
RATE TAKES THE EDGE TO ZERO? A sleeve killed by 2.00/lot/night is in danger whatever the broker
charges; one that survives 60.00 is safe whatever the broker charges. Only the sleeves in between
have to wait for the measurement, and naming them is what tells the desk where to look first.

================================================================================================
THE TWO CONVENTIONS THAT ARE BROKER FACTS, NOT CHOICES
================================================================================================

**THE STAMP.** Swap is charged at the broker's server rollover, conventionally 17:00 New York.
`ROLLOVER_HOUR_UTC` is 22, which is correct while New York is on daylight time and one hour early
while it is not. Fusion's server clock is the authority and this default is an assumption, flagged
as one by `stamp_provenance`. The count is a floor either way: a trade spanning the true stamp
also spans a stamp one hour from it in all but the narrowest cases.

**WEDNESDAY IS TRIPLE.** Spot FX and metals settle T+2, so Wednesday's rollover carries the
weekend and brokers charge three nights on it. Counting Wednesday once understates the annual
charge by 2/7 -- about 29% -- which is larger than most of the cost differences this desk argues
about. `TRIPLE_SWAP_WEEKDAY` is 2 (Monday=0).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Iterable, Sequence

FINANCING_VERSION = "financing-2026-08-19-a"

#: Broker server rollover, 17:00 New York expressed in UTC during US daylight time. An ASSUMPTION
#: until the server clock is read -- see `stamp_provenance`.
ROLLOVER_HOUR_UTC = 22

#: Monday=0, so 2 is Wednesday: the T+2 stamp that carries the weekend on spot FX and metals.
#:
#: A DEFAULT, NOT A UNIVERSAL, and it was written as one. The broker publishes the real answer per
#: symbol in `swap_rollover3days`, and measured on this desk's own contract-terms tape it disagrees
#: with Wednesday on the MAJORITY of the universe:
#:
#:     swap_rollover3days == 3 (Wednesday)    98 symbols   <- this default is right for these
#:     swap_rollover3days == 5 (Friday)      150 symbols   <- and wrong for these
#:
#: Wednesday is correct for spot FX and metals, which is where this module was measured, and the
#: Friday group is dominated by the share and index CFDs the desk had no sleeve on when this was
#: written. `rollover_nights(triple_weekday=...)` has always accepted the per-symbol value and
#: nothing ever supplied one; `desks/mt5/research/carry_state.triple_weekday_for()` is that supply,
#: and `carry_state.json` carries it per symbol as `triple_swap_weekday`.
#:
#: Getting it wrong does NOT change a symbol's annual financing cost -- it moves 2/7 of that cost
#: onto the wrong trades, so a per-sleeve gate cannot see the error at all.
TRIPLE_SWAP_WEEKDAY = 2

#: Nights charged on the triple stamp. Three, not two: the weekend is two extra nights on top of
#: the one that stamp would carry anyway.
TRIPLE_SWAP_NIGHTS = 3


@dataclass(frozen=True)
class SwapProfile:
    """A sleeve's exposure to the rollover, measured from its own trades.

    `crossing_rate` and `mean_nights` answer different questions and both are needed. A sleeve
    that crosses rarely but holds for a week when it does carries its cost in the tail; one that
    crosses nightly at one night each carries it in the median. Sizing sees the mean; a survival
    argument sees the tail, which is why `p90_nights` is here and not derivable from the other two.
    """

    trades: int
    crossings: int
    total_nights: int
    mean_nights: float
    p90_nights: int
    crossing_rate: float


@dataclass(frozen=True)
class SwapVerdict:
    """What the swap does to a sleeve's edge, or the reason it cannot be said.

    `state` is MEASURED only when a rate was supplied. UNMEASURED is a real verdict here and
    carries `breakeven_per_lot` instead -- the rate at which this sleeve's expectancy reaches
    zero, which needs no broker table and is the thing worth acting on first.
    """

    name: str
    state: str
    expectancy_r: float
    mean_nights: float
    drag_r: float | None
    expectancy_after_r: float | None
    breakeven_per_lot: float | None
    why: str


def stamp_provenance() -> str:
    """Why ROLLOVER_HOUR_UTC is an assumption. Published so a reader cannot mistake it for read.

    Named rather than silent because the desk's rule is that an assumed input must be visible at
    the point the number is used, not in a docstring nobody opens.
    """
    return (f"rollover assumed at {ROLLOVER_HOUR_UTC:02d}:00 UTC (17:00 New York on US daylight "
            "time); one hour early on standard time. NOT read from the broker server clock -- "
            "gateway.py can supply it and does not yet")


def rollover_nights(entry: datetime, exit_at: datetime, *,
                    hour: int = ROLLOVER_HOUR_UTC,
                    triple_weekday: int | None = TRIPLE_SWAP_WEEKDAY) -> int:
    """Nights CHARGED between entry and exit, Wednesday counted as three.

    Half-open on purpose: a stamp exactly at the entry is not charged and a stamp exactly at the
    exit is. A position opened at 22:00:00 has not been held overnight; one closed at 22:00:00 has
    been financed to that moment. Getting this backwards double-counts every trade that both opens
    and closes on a stamp, which on hourly bars is not a rare alignment -- it is the common one.

    Returns 0 for a non-positive interval rather than raising: an instantaneous or reversed
    timestamp is a data defect for the caller to find, and inventing a charge for it would hide it.

    `triple_weekday=None` disables the weekend rule, for instruments that do not settle T+2. Index
    and energy CFDs are financed daily and take no triple stamp, so passing None there is the
    correct call and not a way to make a sleeve look cheaper.
    """
    if exit_at <= entry:
        return 0
    total = 0
    day = entry.replace(hour=0, minute=0, second=0, microsecond=0)
    end = exit_at.replace(hour=0, minute=0, second=0, microsecond=0)
    while day <= end:
        stamp = day + timedelta(hours=hour)
        if entry < stamp <= exit_at:
            total += (TRIPLE_SWAP_NIGHTS
                      if triple_weekday is not None and stamp.weekday() == triple_weekday
                      else 1)
        day += timedelta(days=1)
    return total


def profile(nights: Sequence[int] | Iterable[int]) -> SwapProfile:
    """Aggregate a sleeve's per-trade night counts. An empty sleeve profiles to zeros, not to a
    division error -- a sleeve with no trades has no swap exposure and that is a real answer."""
    ns = [int(n) for n in nights]
    if not ns:
        return SwapProfile(0, 0, 0, 0.0, 0, 0.0)
    crossings = sum(1 for n in ns if n > 0)
    ordered = sorted(ns)
    # Nearest-rank p90: index ceil(0.9*n)-1. On integer night counts an interpolated quantile
    # would report 1.4 nights, which the broker cannot charge.
    idx = max(0, -(-len(ordered) * 9 // 10) - 1)
    return SwapProfile(
        trades=len(ns), crossings=crossings, total_nights=sum(ns),
        mean_nights=sum(ns) / len(ns), p90_nights=ordered[idx],
        crossing_rate=crossings / len(ns),
    )


def drag_r(mean_nights: float, swap_per_lot: float, stop_value_per_lot: float) -> float:
    """Swap expressed in R -- the only unit this desk's engine, sizing and gates speak.

    One R is the money risked to the stop, which is `stop_value_per_lot` per lot. So a charge of
    `swap_per_lot` per night, over `mean_nights` nights, costs `nights * swap / stop_value` R.
    Sign convention: POSITIVE is a cost. Pass a negative `swap_per_lot` for the rare financed side
    that is paid to hold, and the drag comes back negative, which is a credit.

    Raises on a non-positive stop value. That is not defensive coding -- a zero stop makes every
    trade infinite-R and the resulting drag would be reported as inf or nan next to a plausible
    expectancy, which is worse than stopping.
    """
    if stop_value_per_lot <= 0:
        raise ValueError("stop_value_per_lot must be positive -- R is undefined without a stop")
    return float(mean_nights) * float(swap_per_lot) / float(stop_value_per_lot)


def breakeven_swap_per_lot(expectancy_r: float, mean_nights: float,
                           stop_value_per_lot: float) -> float | None:
    """The nightly swap that takes this sleeve's expectancy to exactly zero.

    **THE QUESTION THAT DOES NOT NEED THE BROKER'S TABLE**, which is why it is the module's main
    output while the rate is unmeasured. Solve `exp_r = nights * swap / stop_value` for swap.

    Returns None when the sleeve cannot be killed by swap at all -- either it never crosses a
    rollover (`mean_nights == 0`) or its expectancy is already non-positive, in which case swap is
    not what is wrong with it. None here means "this question does not apply", NOT "safe", and the
    caller must render it as such.
    """
    if stop_value_per_lot <= 0:
        raise ValueError("stop_value_per_lot must be positive -- R is undefined without a stop")
    if mean_nights <= 0 or expectancy_r <= 0:
        return None
    return float(expectancy_r) * float(stop_value_per_lot) / float(mean_nights)


def assess(name: str, *, expectancy_r: float, mean_nights: float, stop_value_per_lot: float,
           swap_per_lot: float | None = None) -> SwapVerdict:
    """One sleeve's swap verdict, MEASURED or UNMEASURED, never silently zero.

    `swap_per_lot=None` is the desk's current state and produces the UNMEASURED verdict carrying
    the breakeven. Supplying a rate produces the drag and the post-swap expectancy, and the
    verdict says which of the two it is so a report can never blur them.
    """
    if swap_per_lot is None:
        be = breakeven_swap_per_lot(expectancy_r, mean_nights, stop_value_per_lot)
        if be is None:
            why = ("no rollover exposure or no positive edge to lose -- swap cannot be what "
                   f"decides this sleeve ({mean_nights:.3f} nights/trade, {expectancy_r:+.4f}R)")
        else:
            why = (f"UNMEASURED: no broker swap table on this box. This sleeve's edge reaches "
                   f"ZERO at {be:,.2f} per lot per night, over {mean_nights:.3f} charged nights "
                   f"per trade. {stamp_provenance()}")
        return SwapVerdict(name=name, state="UNMEASURED", expectancy_r=float(expectancy_r),
                           mean_nights=float(mean_nights), drag_r=None,
                           expectancy_after_r=None, breakeven_per_lot=be, why=why)

    d = drag_r(mean_nights, swap_per_lot, stop_value_per_lot)
    after = float(expectancy_r) - d
    survives = "SURVIVES" if after > 0 else "IS KILLED BY"
    return SwapVerdict(
        name=name, state="MEASURED", expectancy_r=float(expectancy_r),
        mean_nights=float(mean_nights), drag_r=d, expectancy_after_r=after,
        breakeven_per_lot=breakeven_swap_per_lot(expectancy_r, mean_nights, stop_value_per_lot),
        why=(f"{swap_per_lot:,.2f}/lot/night over {mean_nights:.3f} nights costs {d:+.4f}R "
             f"against a stop worth {stop_value_per_lot:,.2f}/lot; expectancy "
             f"{expectancy_r:+.4f}R -> {after:+.4f}R, so the sleeve {survives} its financing"),
    )
