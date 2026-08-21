"""Ratchet the stop-protected outcome of an open position upward, without choking the runner.

IT IS "STOP-PROTECTED", NOT "GUARANTEED", AND THE DIFFERENCE IS NOT PEDANTRY

An MT5 stop is a REQUEST, not a floor. Weekend gaps, news spikes, spread blowouts and thin
books all fill worse than the level asked for -- sometimes much worse. What the invariant below
actually guarantees is that this desk never REQUESTS a worse level of protection than it
already holds. The market decides the fill.

Calling it "guaranteed" would have been the same class of error this module exists to fix:
a number that reads as a certainty while the execution path quietly fails to deliver it. The
tail risk that survives here -- gap through the stop -- is real, unhedged, and belongs in the
ruin analysis rather than being papered over by the name of a variable.

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

Let P be the STOP-PROTECTED OUTCOME of the thesis -- what the position banks if the market
reverses and the stop fills as requested:

    P = banked_r + remaining_fraction * side * (stop - entry) / stop_distance

Management is only ever allowed to make P larger. Never smaller. Every action here is checked
against that, and a stop that would widen is REFUSED rather than clamped, because a management
routine that can loosen a stop is a way to lose more than the position was sized to lose.

THE BROKER IS THE STATE, AND THIS MODULE HOLDS NONE

The floor must advance only when the BROKER has acknowledged the new stop -- not when this
code has calculated one. A modify can be rejected (invalid stops level, market closed, requote,
connection lost); a manager that advanced its own internal floor on send would then believe it
held protection the account does not have, which is the same fiction the module was written to
eliminate, merely relocated.

That failure mode is designed out rather than guarded against: this module is stateless, and
`current_stop` MUST be the stop the broker last reported (`position.sl` from a fresh
`positions_get`). A rejected modify therefore changes nothing -- the next cycle re-reads the
unchanged stop and simply re-proposes. Idempotency and acknowledgement come free from having
no state to disagree with the account.

For the same reason `banked_r` and `remaining_fraction` MUST be derived from executed deals and
live position volume, never from what a simulation thinks was banked. If this module were told
30% was banked while the broker still held 100%, P would be fiction in the one direction that
matters -- overstating protection.

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
from typing import Literal

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

    new_stop: float | None      # None = leave the stop exactly where it is
    protected_r_before: float
    protected_r_after: float
    k_used: float
    stalled: bool
    reason: str

    @property
    def moves(self) -> bool:
        return self.new_stop is not None

    @property
    def improvement_r(self) -> float:
        return self.protected_r_after - self.protected_r_before


def stop_protected_r(*, entry: float, stop: float, stop_distance: float,
                     side: Literal[1, -1], banked_r: float = 0.0,
                     remaining_fraction: float = 1.0) -> float:
    """What this thesis banks if the market reverses and the stop fills AS REQUESTED.

    THE NUMBER THE RATCHET IS DEFINED ON. Unrealised P&L is not it: unrealised P&L can be
    +1,490 and still become a loss, which is precisely the outcome management exists to
    prevent. This quantity can only be changed by moving the stop or by banking, so it is the
    honest measure of what has actually been secured -- subject to the fill caveat in the
    module docstring, which is why it is "protected" and not "guaranteed".

    `stop` must be the BROKER-REPORTED stop and `banked_r`/`remaining_fraction` must come from
    executed deals and live volume. Passing intended-but-unacknowledged values overstates
    protection, which is the one direction of error that actually costs money.

    Negative until the stop passes entry, and that is correct rather than a flaw -- a trade
    whose stop is still below entry has secured nothing, however green it looks.
    """
    if stop_distance <= 0:
        raise ValueError(f"stop_distance must be positive, got {stop_distance}")
    if not 0.0 <= remaining_fraction <= 1.0:
        raise ValueError(f"remaining_fraction must be in [0,1], got {remaining_fraction}")
    return banked_r + remaining_fraction * side * (stop - entry) / stop_distance


def banked_state(*, original_volume: float, live_volume: float,
                 realised_quote: float, risk_per_lot_quote: float) -> tuple[float, float]:
    """Reconstruct (banked_r, remaining_fraction) FROM THE BROKER, never from intent.

    `original_volume` is the volume the position was opened with, `live_volume` what
    `positions_get` reports now, and `realised_quote` the summed profit of the DEAL_ENTRY_OUT
    deals that closed the difference. `risk_per_lot_quote` converts one lot's initial stop
    distance into quote currency, so the realised amount becomes an R multiple on the same
    scale as the open leg.

    THIS EXISTS SO THE TWO NUMBERS CANNOT BE GUESSED. `stop_protected_r` is only honest if
    what it is told was banked actually was; a partial close that was requested and rejected,
    or filled at a different size, has to show up here as the broker saw it. Everything is
    derived from executed quantities, so there is no path by which intent leaks in.

    A position whose live volume EXCEEDS the original is not a partial close -- it is a pyramid
    add, a reconciliation error, or the wrong ticket, and it refuses rather than returning a
    negative banked fraction that would flatter the protected outcome.
    """
    if original_volume <= 0:
        raise ValueError(f"original_volume must be positive, got {original_volume}")
    if live_volume < 0:
        raise ValueError(f"live_volume cannot be negative, got {live_volume}")
    if live_volume > original_volume:
        raise ValueError(
            f"live volume {live_volume} exceeds original {original_volume} -- this is not a "
            f"partial close; refusing rather than reporting a negative banked fraction")
    if risk_per_lot_quote <= 0:
        raise ValueError(f"risk_per_lot_quote must be positive, got {risk_per_lot_quote}")
    remaining_fraction = live_volume / original_volume
    banked_r = realised_quote / (risk_per_lot_quote * original_volume)
    return banked_r, remaining_fraction


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

    before = stop_protected_r(entry=entry, stop=current_stop, stop_distance=stop_distance,
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

    after = stop_protected_r(entry=entry, stop=candidate, stop_distance=stop_distance,
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
        f"extreme {extreme:.5f} -> stop {candidate:.5f}; "
        f"protected {before:+.3f}R -> {after:+.3f}R")
