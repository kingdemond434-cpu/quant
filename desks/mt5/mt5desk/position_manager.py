"""Ratchet the guaranteed outcome of an open position upward, without choking the runner.

WHAT THIS EXISTS TO FIX, AND IT IS NOT A REFINEMENT

`mt5desk/engine.py` models `bank_frac`, `bank_protect_k`, `runner_trail_k`, `trail_tighten_k`
and `trail_stall_bars`. Every backtest expectancy figure on this desk is computed WITH that
management applied.

`mt5desk/gateway.py` -- the only code that sends an order -- issues exactly two actions:
`TRADE_ACTION_PENDING` (open, with a stop fixed at entry) and `TRADE_ACTION_DEAL` (close the
whole position). A repo-wide search for `TRADE_ACTION_SLTP` returns NOTHING. No stop on this
desk has ever moved after the order was placed.

So the backtest and the live account are running DIFFERENT STRATEGIES, and the difference is
the entire runner architecture. A live winner can round-trip to its opening stop, which the
backtest would never have shown, because in the backtest the stop had trailed. That is not a
modelling nicety: it is the money path silently disagreeing with the evidence used to justify
it (III.16 -- built is not a status; name the caller).

THE INVARIANT, WHICH IS THE WHOLE DESIGN

Let G be the GUARANTEED OUTCOME of the thesis -- what the position banks if the market
immediately reverses and takes the current stop:

    G = banked_r + remaining_fraction * side * (stop - entry) / stop_distance

Management is only ever allowed to make G larger. Never smaller. Every action here is checked
against that, and a stop that would widen is REFUSED rather than clamped, because a management
routine that can loosen a stop is a way to lose more than the position was sized to lose.

WHY A RATCHET AND NOT A TIGHT TRAIL

Protecting every unit of open profit is the failure mode that looks like discipline. A stop
dragged up under price exits the trade on the first ordinary pullback, and the 5R-10R outcomes
that pay for the losing majority never happen. The desk's own measurement says so: a static
chandelier at k=4 LOST $16.82/oz over 95 events while the same k tightened to 1 after three
bars without a new extreme MADE $9.80 -- +$11.63/oz paired, better 63% of the time, t=2.48.

The lesson in that number is not "tighten". It is that breathing room and profit protection are
wanted AT DIFFERENT TIMES, and a single constant cannot express a question with two answers.

SO THE GIVEBACK BUDGET IS DYNAMIC IN TWO INDEPENDENT WAYS, AND NEITHER IS A HARDCODED LEVEL

  1. It scales with LIVE ATR. The same nominal giveback is generous in a quiet tape and
     strangling in a violent one. Nothing here is expressed in euros or pips.
  2. It CONTRACTS when the move stops making new extremes -- `stall_bars` since the last
     extreme, the measured mechanism above.

`K_TREND`, `K_STALLED` and `STALL_BARS` are not chosen here. They are the exit this desk
already selected on 22 instruments of pullback entries (research/run_hunt14.py), reused rather
than re-fitted. That provenance matters and is a limitation, not a boast: those values were
selected on OTHER data, so a position managed by them has passed a slightly warmer test than a
genuinely cold one.

WHAT THIS MODULE DELIBERATELY DOES NOT DO

It does not talk to MetaTrader5, hold state, or decide when to trade. It is pure arithmetic over
numbers a caller supplies, so it can be tested without a terminal and cannot place an order by
accident. Arming it against a live account is a separate act, gated by the gateway's existing
`st["armed"]` flag, and is the principal's decision -- not this file's.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Optional

#: Chandelier multiple while the move is still printing new extremes. Wide on purpose: this is
#: the number that lets a winner become a 5R winner.
K_TREND = 4.0

#: Chandelier multiple once the move has stalled. The measured pair (t=2.48) is the whole
#: reason both constants exist instead of one.
K_STALLED = 1.0

#: Bars without a new extreme before the move counts as stalled.
STALL_BARS = 3


@dataclass(frozen=True)
class RatchetDecision:
    """What management wants to do, and why -- in a form a human can audit before it is armed."""

    new_stop: Optional[float]      # None = leave the stop exactly where it is
    guaranteed_r_before: float
    guaranteed_r_after: float
    k_used: float
    stalled: bool
    reason: str

    @property
    def moves(self) -> bool:
        return self.new_stop is not None

    @property
    def improvement_r(self) -> float:
        return self.guaranteed_r_after - self.guaranteed_r_before


def guaranteed_r(*, entry: float, stop: float, stop_distance: float,
                 side: Literal[1, -1], banked_r: float = 0.0,
                 remaining_fraction: float = 1.0) -> float:
    """What this thesis banks if the market reverses right now and takes the stop.

    THE NUMBER THE RATCHET IS DEFINED ON. Unrealised P&L is not it: unrealised P&L can be
    +1,490 and still become a loss, which is precisely the outcome management exists to
    prevent. `guaranteed_r` can only be changed by moving the stop or by banking, so it is the
    honest measure of what has actually been secured.

    Negative until the stop passes entry, and that is correct rather than a flaw -- a trade
    whose stop is still below entry has secured nothing, however green it looks.
    """
    if stop_distance <= 0:
        raise ValueError(f"stop_distance must be positive, got {stop_distance}")
    if not 0.0 <= remaining_fraction <= 1.0:
        raise ValueError(f"remaining_fraction must be in [0,1], got {remaining_fraction}")
    return banked_r + remaining_fraction * side * (stop - entry) / stop_distance


def is_stalled(bars_since_extreme: int, stall_bars: int = STALL_BARS) -> bool:
    """Has the move stopped making new extremes long enough to tighten?

    Deliberately a count of bars WITHOUT A NEW EXTREME rather than a price-distance test. A
    pullback that is still inside the trend prints no new extreme but also does not mean the
    move is over; what distinguishes the two is how LONG it goes without one.
    """
    return bars_since_extreme >= stall_bars


def chandelier_stop(*, extreme: float, atr: float, side: Literal[1, -1],
                    k: float) -> float:
    """The stop implied by an ATR-scaled offset from the best price the move has reached.

    `extreme` is the highest high since entry for a long, the lowest low for a short -- the
    high-water mark of the thesis, not the current price. Trailing from the extreme rather than
    from spot is what stops an ordinary pullback dragging the stop up behind it.
    """
    if atr <= 0:
        raise ValueError(f"atr must be positive, got {atr}")
    if k <= 0:
        raise ValueError(f"k must be positive, got {k}")
    return extreme - side * k * atr


def ratchet(*, entry: float, current_stop: float, stop_distance: float,
            extreme: float, atr: float, side: Literal[1, -1],
            bars_since_extreme: int,
            banked_r: float = 0.0, remaining_fraction: float = 1.0,
            k_trend: float = K_TREND, k_stalled: float = K_STALLED,
            stall_bars: int = STALL_BARS) -> RatchetDecision:
    """Decide the new stop, guaranteeing the secured outcome never decreases.

    Returns a decision rather than a bare number so the caller can log WHY before anything is
    sent, and so a shadow run and an armed run differ only in whether the decision is executed.

    THE REFUSAL THAT MATTERS: a computed stop that would sit further from price than the
    current one is DISCARDED, not applied. Widening a stop is how a position comes to risk more
    than it was sized for, and there is no market state in which this routine should do it --
    so the guard is unconditional rather than a tunable.
    """
    if stop_distance <= 0:
        raise ValueError(f"stop_distance must be positive, got {stop_distance}")
    if side not in (1, -1):
        raise ValueError(f"side must be 1 or -1, got {side}")

    before = guaranteed_r(entry=entry, stop=current_stop, stop_distance=stop_distance,
                          side=side, banked_r=banked_r,
                          remaining_fraction=remaining_fraction)

    stalled = is_stalled(bars_since_extreme, stall_bars)
    k = k_stalled if stalled else k_trend
    candidate = chandelier_stop(extreme=extreme, atr=atr, side=side, k=k)

    # NEVER LOOSEN. For a long the stop may only rise; for a short, only fall.
    improves = (candidate > current_stop) if side == 1 else (candidate < current_stop)
    if not improves:
        return RatchetDecision(
            None, before, before, k, stalled,
            f"hold: {'trending' if not stalled else 'stalled'} chandelier at k={k:g} sits "
            f"{'below' if side == 1 else 'above'} the current stop, and a stop is never widened")

    after = guaranteed_r(entry=entry, stop=candidate, stop_distance=stop_distance,
                         side=side, banked_r=banked_r,
                         remaining_fraction=remaining_fraction)

    # Belt and braces on the invariant itself. `improves` above is a price-space test; this is
    # the same claim in R-space, and if they ever disagree the arithmetic is wrong and nothing
    # should be sent on the strength of it.
    if after < before:
        return RatchetDecision(
            None, before, before, k, stalled,
            f"REFUSED: candidate stop improves in price but lowers guaranteed outcome "
            f"{before:+.3f}R -> {after:+.3f}R. Arithmetic disagrees with itself; not sending")

    return RatchetDecision(
        candidate, before, after, k, stalled,
        f"{'stalled' if stalled else 'trending'}: chandelier k={k:g} x ATR {atr:.5f} off "
        f"extreme {extreme:.5f} -> stop {candidate:.5f}; guaranteed {before:+.3f}R -> {after:+.3f}R")
