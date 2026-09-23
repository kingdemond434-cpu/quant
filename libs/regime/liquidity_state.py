"""What it costs to trade right now, named as a state rather than averaged into one number.

The allocator can pick the right alpha and still lose money by taking it in the wrong liquidity.
An edge worth 0.3R is not worth crossing a spread in its own 97th percentile, and the difference
between "this instrument is expensive" and "this instrument is expensive RIGHT NOW" is the whole
question. `universe.json` carries one `median_spread_pts` per symbol, so until this existed the
desk had no way to ask the second one.

    NORMAL           spread and depth within the instrument's own usual range
    THIN             wide for this instrument and quiet with it -- few ticks, little depth. The
                     cost is there but so is the option to wait
    TOXIC            wide AND moving: spread in its own extreme and widening. Waiting is not a
                     free option here, because the thing making it expensive is also moving price
    ROLLOVER         the broker's daily settlement window. Spreads gap by contract, not by
                     sentiment, and every desk that has ever backtested through it has overstated
                     its fills
    NEWS             a scheduled release is in its pre or shock window for THIS instrument's
                     currencies -- an execution state with a known cause and a known end
    BROKER_DEGRADED  the venue itself is the problem: a stale tape, a quote gap, or a run of
                     rejections. Not a market state at all, and the only correct response is to
                     stop rather than to size down

EVERY THRESHOLD IS THE INSTRUMENT'S OWN. Bands are percentiles of that symbol's recorded spread
history, so a structurally wide exotic is not permanently "toxic" for being itself, and a
normally-tight major is flagged the moment it stops being tight. A fixed points threshold would
do the opposite of what it is for.

PRECEDENCE IS DECLARED, because these overlap constantly -- a rollover during a news window in a
degraded feed is all three. The order is by what the desk should DO about it:

    BROKER_DEGRADED > TOXIC > NEWS > ROLLOVER > THIN > NORMAL

Degradation first because it is the only one where the instruction is "stop", not "cost more".
Toxic before news because a toxic tape is toxic whatever caused it. News before rollover because
the release is the reason the rollover looks unusual, not the other way round.

IT DECIDES NOTHING HERE. This returns a state and a measured cost multiple. Whether that is worth
waiting out is the allocator's arithmetic -- expected edge against expected cost -- and putting
that decision in here would hide it inside a classifier.
"""
from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any

import numpy as np

NORMAL = "NORMAL"
THIN = "THIN"
TOXIC = "TOXIC"
ROLLOVER = "ROLLOVER"
NEWS = "NEWS"
BROKER_DEGRADED = "BROKER_DEGRADED"
UNMEASURED = "UNMEASURED"

STATES = (BROKER_DEGRADED, TOXIC, NEWS, ROLLOVER, THIN, NORMAL)

#: Percentile of the instrument's own spread history above which it is "wide".
WIDE_PCT = 0.85
#: Percentile above which "wide" becomes a candidate for TOXIC, given it is also widening.
EXTREME_PCT = 0.95
#: Fraction by which the spread must have widened over the recent window to count as widening.
WIDENING_FRAC = 0.25
#: Tick activity below this percentile of its own history is "quiet" -- the THIN half of wide.
QUIET_PCT = 0.25
#: Broker stamp-hours of the daily settlement window. The desk's feed is broker-stamped, so this
#: is read in the same clock every family compares hours in.
ROLLOVER_HOURS = (23, 0)
#: Minutes without a tick before the feed is treated as stale rather than quiet.
STALE_MIN = 20.0
#: Observations of spread history needed before percentiles mean anything.
MIN_HISTORY = 200


@dataclass(frozen=True)
class LiquidityState:
    """One instrument's execution conditions, and what they cost against its own normal."""

    symbol: str
    state: str
    #: Current spread in quote units, and where it sits in this instrument's own history.
    spread: float | None = None
    percentile: float | None = None
    #: Current spread divided by the instrument's median. The number a cost model multiplies by.
    cost_multiple: float | None = None
    widening: bool = False
    quiet: bool = False
    minutes_since_tick: float | None = None
    n_history: int = 0
    why: str = ""
    gaps: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {"symbol": self.symbol, "state": self.state,
                "spread": (round(self.spread, 8) if self.spread is not None else None),
                "percentile": (round(self.percentile, 4)
                               if self.percentile is not None else None),
                "cost_multiple": (round(self.cost_multiple, 4)
                                  if self.cost_multiple is not None else None),
                "widening": self.widening, "quiet": self.quiet,
                "minutes_since_tick": (round(self.minutes_since_tick, 2)
                                       if self.minutes_since_tick is not None else None),
                "n_history": self.n_history, "why": self.why, "gaps": self.gaps}


def classify(symbol: str, spread_history: Sequence[float] | None,
             *, activity_history: Sequence[float] | None = None,
             broker_hour: int | None = None, in_news_window: bool = False,
             minutes_since_tick: float | None = None,
             recent_rejections: int = 0, rejection_limit: int = 3,
             recent_window: int = 6) -> LiquidityState:
    """Name the execution state from the instrument's own recorded tape.

    `spread_history` is oldest-to-newest with the CURRENT spread last. `activity_history` is the
    matching tick or flow count. Both may be None, and the answer is then UNMEASURED rather than
    NORMAL -- "no tape recorded" and "conditions are fine" are opposite facts and this desk has
    conflated them before.
    """
    gaps: dict[str, str] = {}

    # DEGRADATION FIRST, because it is the only state whose instruction is "stop".
    if recent_rejections >= rejection_limit:
        return LiquidityState(symbol, BROKER_DEGRADED, minutes_since_tick=minutes_since_tick,
                              why=f"{recent_rejections} recent order rejections", gaps=gaps)
    if minutes_since_tick is not None and minutes_since_tick > STALE_MIN:
        return LiquidityState(symbol, BROKER_DEGRADED, minutes_since_tick=minutes_since_tick,
                              why=f"no tick for {minutes_since_tick:.0f} minutes", gaps=gaps)

    arr = np.asarray([x for x in (spread_history or []) if x is not None], dtype=float)
    arr = arr[np.isfinite(arr)]
    if arr.size < MIN_HISTORY:
        gaps["spread_history"] = (f"{arr.size} spread observations, needs {MIN_HISTORY} before "
                                  "percentiles of this instrument's own history mean anything")
        # An UNCLASSIFIABLE tape is still allowed to report the states that need no history.
        if in_news_window:
            return LiquidityState(symbol, NEWS, n_history=int(arr.size),
                                  why="scheduled release window", gaps=gaps)
        if broker_hour is not None and int(broker_hour) in ROLLOVER_HOURS:
            return LiquidityState(symbol, ROLLOVER, n_history=int(arr.size),
                                  why="broker settlement window", gaps=gaps)
        return LiquidityState(symbol, UNMEASURED, n_history=int(arr.size),
                              why="no usable spread history", gaps=gaps)

    cur = float(arr[-1])
    pct = float((arr <= cur).mean())
    median = float(np.median(arr))
    cost_mult = (cur / median) if median > 0 else None
    prior = arr[-(recent_window + 1):-1]
    widening = bool(prior.size and cur > float(prior.mean()) * (1.0 + WIDENING_FRAC))

    quiet = False
    if activity_history is not None:
        act = np.asarray([x for x in activity_history if x is not None], dtype=float)
        act = act[np.isfinite(act)]
        if act.size >= MIN_HISTORY:
            quiet = bool(float((act <= act[-1]).mean()) <= QUIET_PCT)
        else:
            gaps["activity_history"] = f"{act.size} activity observations, needs {MIN_HISTORY}"
    else:
        gaps["activity_history"] = "no tick-activity series supplied; THIN cannot be separated"

    common: dict[str, Any] = {
        "spread": cur, "percentile": pct, "cost_multiple": cost_mult, "widening": widening,
        "quiet": quiet, "minutes_since_tick": minutes_since_tick, "n_history": int(arr.size),
        "gaps": gaps}

    if pct >= EXTREME_PCT and widening:
        return LiquidityState(symbol, TOXIC,
                              why=f"spread at the {pct:.0%} percentile and widening", **common)
    if in_news_window:
        return LiquidityState(symbol, NEWS, why="scheduled release window", **common)
    if broker_hour is not None and int(broker_hour) in ROLLOVER_HOURS:
        return LiquidityState(symbol, ROLLOVER, why="broker settlement window", **common)
    if pct >= WIDE_PCT:
        return LiquidityState(symbol, THIN if quiet else TOXIC,
                              why=(f"spread at the {pct:.0%} percentile and "
                                   + ("quiet" if quiet else "active")), **common)
    return LiquidityState(symbol, NORMAL, why=f"spread at the {pct:.0%} percentile", **common)
