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

`mt5desk/gateway.py` -- the only code that sends an order -- issued exactly two actions:
`TRADE_ACTION_PENDING` (open, with a stop fixed at entry) and `TRADE_ACTION_DEAL` (close the
whole position). A repo-wide search for `TRADE_ACTION_SLTP` returned NOTHING. No stop on this
desk had ever moved after the order was placed.

(STATUS, 2026-09-24: that gap is CLOSED and the paragraph above is history, not a live defect.
`gateway.manage_open_positions` calls `ratchet` every pass and sends `TRADE_ACTION_SLTP`. Left
standing because the reasoning is what justifies the module, and because a reader who finds the
claim and checks it will now find two call sites rather than none.)

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

from collections.abc import Sequence
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

#: Net open profit, in R, at which the stop may never again be worse than costed break-even.
#:
#: MEASURED, NOT CHOSEN (2026-09-24), on this desk's own 82 reconstructed XAUUSD trades --
#: gold_asia, gold_london_am, gold_afternoon, xau_m15_anti_breakout,
#: xau_m5_anti_breakout_overla, xau_m5_anti_momentum_ny -- replayed bar by bar on M1 from the
#: MT5 entry deal to the recorded close.  Growth Governance rule 1 demands that a risk-reduction
#: mechanism prove it raises robust forward E[log W] before it touches capital, and a break-even
#: stop is squarely one: it converts losers into scratches AND winners into scratches, and only
#: the arithmetic says which dominates.
#:
#: At 0.85R, on the realised sequence: 37 of 82 positions scratch -- 26 losers avoided
#: (+330.66) against 11 winners given up (-222.72), net +107.94 on a +227.90 base (+47.4%),
#: E[log W] +0.25883 -> +0.36139 (terminal wealth x1.108).  Under the pessimistic intrabar
#: ordering (favourable extreme first, so a bar may arm AND scratch) it is +90.25 / x1.090.
#:
#: THE VALUE IS THE CENTRE OF A SHELF, NOT AN ARGMAX.  Swept on a 0.05R grid the net effect is
#: positive under BOTH intrabar orderings everywhere from 0.30R to 1.10R, and 0.80R/0.85R/0.90R
#: select the identical trade set (+107.94 / +90.25) -- 0.85R is the midpoint of the widest band
#: that stays positive within +/-0.15R of itself.  Below 0.30R the stop sits inside ordinary
#: noise and scratches winners for nothing (-46.71 at 0.25R); above 1.10R it arms too late to
#: catch the losers (-97.32 at 2.00R).  Because the shelf is wide, this is not a number fitted
#: to a knife edge.
#:
#: THE SAME TRIGGER WAS RE-MEASURED ON THE NON-GOLD LANE, because E8's book is 7/8 forex and
#: applying a gold number to it would be borrowed evidence.  125 reconstructed forex trades
#: (12 symbols, the discovered-asia and overnight-gap-decay families) replayed identically:
#: +23.99 on a -86.20 base at 0.85R, E[log W] +0.03441, and POSITIVE AT EVERY TRIGGER from 0.25R
#: to 1.50R under both intrabar orderings.  The bootstrap there is far stronger than gold's --
#: P(net > 0) = 0.996, 90% interval [+7.70, +42.86], entirely above zero -- because that lane was
#: a LOSING one, so the floor converts losses to scratches with almost no winners to give up.
#: Combined evidence base: n = 207 positions on the desk's own account.
#:
#: WHAT THE EVIDENCE DOES NOT SAY.  The 20,000-resample bootstrap puts P(net > 0) at 0.776, with
#: a 90% interval of [-123.72, +350.94]: the sign is not established at conventional
#: significance and n=82 over 17 days is thin.  Per-sleeve the effect is NOT uniform --
#: gold_london_am (n=9) is -46.76 and xau_m5_anti_momentum_ny (n=23) is -1.21 -- but n<25 per
#: sleeve is noise, so the book-level number is the one that decides and no per-sleeve trigger
#: is fitted.  Leave-one-out: removing the single most favourable trade still leaves +30.26.
BREAKEVEN_TRIGGER_R = 0.85


@dataclass(frozen=True)
class RatchetDecision:
    """What management wants to do, and why -- in a form a human can audit before it is armed."""

    new_stop: float | None      # None = leave the stop exactly where it is
    protected_r_before: float
    protected_r_after: float
    k_used: float
    stalled: bool
    reason: str
    breakeven_floor: bool = False   # the move is the costed break-even floor, not the trail

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


def extreme_and_stall(*, highs: Sequence[float], lows: Sequence[float],
                      side: Literal[1, -1]) -> tuple[float, int]:
    """The high-water mark of the thesis, and how many bars have passed since it was set.

    `highs`/`lows` must cover ONLY the bars since the position opened, oldest first. Including
    bars from before entry would let a pre-entry extreme define the trail, which is a level the
    thesis never actually reached.

    LAST occurrence wins on ties, not first. A move that revisits its high after a pullback has
    RE-CONFIRMED the extreme, and treating it as three bars stale would tighten the stop on a
    trend that is still working -- the precise failure the stall switch exists to avoid.

    Returns bars-since as a count of bars AFTER the extreme bar, so the bar that sets a fresh
    extreme yields 0 and cannot be stalled.
    """
    if len(highs) != len(lows):
        raise ValueError(f"highs/lows length mismatch: {len(highs)} vs {len(lows)}")
    if not highs:
        raise ValueError("no bars since entry; cannot locate an extreme")
    series = highs if side == 1 else lows
    best = max(series) if side == 1 else min(series)
    idx = len(series) - 1 - list(reversed(series)).index(best)
    return float(best), len(series) - 1 - idx


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


def breakeven_level(*, entry: float, side: Literal[1, -1],
                    cost_per_unit: float) -> float:
    """The stop price at which closing nets EXACTLY zero after the full round trip.

    "BREAK EVEN" IS NOT "AT THE ENTRY PRICE", AND THE DIFFERENCE IS THE WHOLE POINT. A stop
    parked on `price_open` still pays commission on both legs, so every scratch it produces is a
    small LOSS -- on every single trade, scaling linearly with size. Here `cost_per_unit` is the
    round-trip commission expressed in PRICE units (account currency per lot, divided by the
    account currency one price unit is worth per lot), so the level clears the round trip by
    construction.

    THE SPREAD IS ALREADY IN THE LEVEL AND MUST NOT BE ADDED AGAIN. MetaTrader compares a long's
    stop against the BID and a short's against the ASK -- the same sides the position is closed
    on. A long filled at the ask has therefore already paid the spread at entry, and a bid
    returning to `price_open` means the ask has risen by one spread. Charging the spread a second
    time here would place the stop a spread too far into profit, which is not conservatism: it is
    a level the market has to reach twice.

    Symmetric in `side`: +1 puts it above the entry, -1 below, because the cost is paid in the
    direction the position must travel to escape it.
    """
    if cost_per_unit < 0:
        raise ValueError(f"cost_per_unit cannot be negative, got {cost_per_unit}")
    if side not in (1, -1):
        raise ValueError(f"side must be 1 or -1, got {side}")
    return entry + side * cost_per_unit


def net_open_excursion(*, entry: float, extreme: float, side: Literal[1, -1],
                       cost_per_unit: float, spread: float = 0.0) -> float:
    """Net profit per unit at the high-water mark, in price units, after the round trip.

    THE ASYMMETRY IS REAL AND IS NOT A TYPO. `extreme` comes from BID bars, because that is what
    a broker's bar feed is. A LONG realises at the bid, so its favourable extreme is already a
    price it could have sold into and no spread is charged. A SHORT must buy back at the ASK, so
    the bid low it reached is one spread better than anything it could actually have paid, and
    that spread is charged here.

    Getting this backwards would arm shorts a spread early -- which is exactly the error that
    turns a scratch into a loss, merely relocated from the level to the trigger.
    """
    if side not in (1, -1):
        raise ValueError(f"side must be 1 or -1, got {side}")
    if spread < 0:
        raise ValueError(f"spread cannot be negative, got {spread}")
    gross = side * (extreme - entry)
    return gross - cost_per_unit - (spread if side == -1 else 0.0)


def breakeven_armed(*, entry: float, extreme: float, stop_distance: float,
                    side: Literal[1, -1], cost_per_unit: float, spread: float = 0.0,
                    trigger_r: float = BREAKEVEN_TRIGGER_R) -> bool:
    """Has the thesis run far enough that its stop may never again be worse than break-even?

    Measured against the HIGH-WATER MARK, not spot, and in R rather than money, for the same
    reason the chandelier is: the question "did this trade earn the right to a free option" is a
    question about how far it got, and R is the only scale on which a 0.01-lot gold bracket and a
    0.27-lot forex scalp are the same question.

    Arming is one-way per pass and stateless -- the extreme only ever grows, so a position that
    armed once stays armed for as long as it is open, with no flag to persist and nothing that
    can disagree with the account after a restart.
    """
    if stop_distance <= 0:
        raise ValueError(f"stop_distance must be positive, got {stop_distance}")
    if trigger_r <= 0:
        raise ValueError(f"trigger_r must be positive, got {trigger_r}")
    net = net_open_excursion(entry=entry, extreme=extreme, side=side,
                             cost_per_unit=cost_per_unit, spread=spread)
    return net >= trigger_r * stop_distance


def stop_rests_at_venue(*, stop: float, side: Literal[1, -1], bid: float, ask: float,
                        min_distance: float = 0.0) -> tuple[bool, str]:
    """Would this level REST at the venue as a stop, or fire the instant it arrives?

    THE 24-POINT LESSON, MEASURED ON THE MONEY PATH (2026-09-24, E8 position
    360287970193246861). A short filled at 4272.36 with a 29.55 stop distance sat unmanaged for
    four and three-quarter hours while price ran to 4244.21. When the ratchet finally reached it
    at 13:03:08 the extreme was three H1 bars old, so `is_stalled` collapsed k to 1 and the
    chandelier came out at 4244.21 + 1 x 15.57 = 4259.78 -- a perfectly correct trail level for a
    market that was still near its low, and 23.8 points BELOW a market that had already rallied
    back to 4283.5. The venue accepted the modification, the protective buy stop was instantly
    through its trigger, and it filled at market: 4283.91. The desk's own log recorded the move
    as "protected -1.000R -> +0.407R" while the account booked -0.391R, and the 24.13 points
    between the level and the fill cost 386.08 USD -- 97.6% of every point of adverse slippage
    this account has ever paid, in one send.

    NOTHING UPSTREAM CATCHES IT, AND THAT IS THE POINT. `ratchet` compares its candidate against
    the CURRENT STOP and against the protected-R invariant; both tests passed, because moving a
    short's stop from 4303.25 to 4259.78 genuinely does protect more -- IF it is ever reached
    from below. Neither test knows where the market is. A trail computed off an extreme is only a
    stop while price is still on the extreme's side of it; once price retraces past k x ATR, the
    same arithmetic yields a level that is no longer protection but a market order wearing a
    stop's name.

    THE TWO VENUES FAIL DIFFERENTLY, WHICH IS WHY THIS LIVES HERE AND NOT IN AN ADAPTER.
    MetaTrader refuses the request (retcode 10016, "Invalid stops") and the position keeps the
    stop it had -- 92 such refusals are in this desk's own gateway log, harmless every time.
    TradeLocker accepts it and executes it. The same defect is free on one account and expensive
    on the other, so the guard belongs where both lanes already agree: here, in the arithmetic,
    beside the never-widen rule it sits next to.

    THIS REFUSES A SEND; IT NEVER CLOSES, CAPS OR SHRINKS ANYTHING. A refused ratchet leaves the
    position exactly as the account already holds it, under a stop that is still valid, and the
    next pass re-proposes against a fresh quote -- the module's own stateless design doing the
    work. Growth Governance rule 1 is satisfied by construction rather than by argument: the
    refused alternative is an unintended market exit at an arbitrary price, so declining it
    cannot lower forward E[log W].

    A protective stop for a LONG is a sell stop and triggers on the BID falling to it, so it must
    sit strictly below the bid. For a SHORT it is a buy stop triggering on the ASK rising to it,
    so it must sit strictly above the ask. `min_distance` carries a venue's own minimum stop
    distance where it states one (MetaTrader's `trade_stops_level` x `trade_tick_size`); zero
    means the venue states none, not that none applies.

    An unreadable or degenerate quote REFUSES. The position keeps a stop that is known good; a
    send made blind is the one case where being wrong costs the whole giveback.
    """
    if side not in (1, -1):
        raise ValueError(f"side must be 1 or -1, got {side}")
    if min_distance < 0:
        raise ValueError(f"min_distance cannot be negative, got {min_distance}")
    if not (bid > 0 and ask > 0 and ask >= bid):
        return False, (f"refusing a stop against a degenerate quote bid={bid} ask={ask}; the "
                       f"position keeps the stop the account already holds")
    if side == 1:
        limit = bid - min_distance
        if stop < limit:
            return True, f"stop {stop:.5f} rests below the bid {bid:.5f}"
        return False, (f"stop {stop:.5f} is at or above the bid {bid:.5f} for a long"
                       + (f" (venue minimum distance {min_distance:.5f})" if min_distance else "")
                       + "; a stop there is not protection, it is a market exit at whatever the "
                         "book pays, so it is NOT sent and the current stop stands")
    limit = ask + min_distance
    if stop > limit:
        return True, f"stop {stop:.5f} rests above the ask {ask:.5f}"
    return False, (f"stop {stop:.5f} is at or below the ask {ask:.5f} for a short"
                   + (f" (venue minimum distance {min_distance:.5f})" if min_distance else "")
                   + "; a stop there is not protection, it is a market exit at whatever the "
                     "book pays, so it is NOT sent and the current stop stands")


def ratchet(*, entry: float, current_stop: float, stop_distance: float,
            extreme: float, atr: float, side: Literal[1, -1],
            bars_since_extreme: int,
            banked_r: float = 0.0, remaining_fraction: float = 1.0,
            k_trend: float = K_TREND, k_stalled: float = K_STALLED,
            stall_bars: int = STALL_BARS,
            cost_per_unit: float | None = None, spread: float = 0.0,
            breakeven_trigger_r: float = BREAKEVEN_TRIGGER_R,
            floor_only: bool = False) -> RatchetDecision:
    """Decide the new stop, guaranteeing the secured outcome never decreases.

    Returns a decision rather than a bare number so the caller can log WHY before anything is
    sent, and so a shadow run and an armed run differ only in whether the decision is executed.

    THE REFUSAL THAT MATTERS: a computed stop that would sit further from price than the
    current one is DISCARDED, not applied. Widening a stop is how a position comes to risk more
    than it was sized for, and there is no market state in which this routine should do it --
    so the guard is unconditional rather than a tunable.

    THE BREAK-EVEN FLOOR (2026-09-24, principal's standing order: the gold sleeves "must carry a
    break-even stop at the least and must never give back floating profit turning into losses").
    Pass `cost_per_unit` to enable it. Once net open profit reaches `breakeven_trigger_r` x R the
    costed break-even level becomes a FLOOR under the trail, and the candidate sent is whichever
    of the two protects MORE. It is a floor and not a replacement because the chandelier at
    k=4 is deliberately wide -- wide enough that a winner can round-trip past entry, which is the
    giveback the principal named -- while the chandelier above break-even is the thing that lets
    a 5R winner happen, and clamping to break-even there would be the choking this module's own
    docstring warns against.

    The floor CANNOT widen a stop: it is composed with the same unconditional never-loosen guard,
    so a position whose trail has already climbed past break-even sees no change at all.
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
    if floor_only:
        # FLOOR WITHOUT TRAIL, for a certificate earned on a FIXED bracket. Trailing such a
        # position is a lookalike strategy under a certified name -- measured 2026-09-16, five
        # forex closes at a manage-tightened stop for -4.25 EUR on holds the certificate would
        # have carried to their time exit -- so the chandelier is suppressed entirely by seeding
        # the candidate with the stop the account already holds. The break-even floor below is a
        # different object: it never tightens INSIDE the bracket, it only refuses to let the
        # bracket's own stop stay under water once the trade has run, which is the exit the
        # principal ordered on 2026-09-24 and the one the 0.85R measurement covers.
        candidate = current_stop
        why = "fixed bracket: no trail (certified exit), break-even floor only"
    else:
        candidate = chandelier_stop(extreme=extreme, atr=atr, side=side, k=k)
        why = (f"{'stalled' if stalled else 'trending'}: chandelier k={k:g} x ATR {atr:.5f} off "
               f"extreme {extreme:.5f} -> stop {candidate:.5f}")

    # THE FLOOR, COMPOSED RATHER THAN SUBSTITUTED. Whichever of trail and break-even protects
    # more is the one sent; `max`/`min` on side is the same never-loosen rule applied between two
    # candidates instead of between a candidate and the account.
    on_floor = False
    if cost_per_unit is not None and breakeven_armed(
            entry=entry, extreme=extreme, stop_distance=stop_distance, side=side,
            cost_per_unit=cost_per_unit, spread=spread, trigger_r=breakeven_trigger_r):
        be = breakeven_level(entry=entry, side=side, cost_per_unit=cost_per_unit)
        better = (be > candidate) if side == 1 else (be < candidate)
        if better:
            trail_was = candidate
            candidate, on_floor = be, True
            # NAME ONLY WHAT ACTUALLY RAN. In floor-only mode `trail_was` is the account's own
            # stop, not a chandelier, and calling it "the k=4 trail" in the log would invent a
            # computation nobody performed -- the exact class of fiction this module exists to
            # keep out of the money path, merely in prose instead of arithmetic.
            loser = ("no trail ran (fixed bracket); the current stop" if floor_only
                     else f"the k={k:g} trail")
            why = (f"break-even floor: net open profit passed {breakeven_trigger_r:g}R, so the "
                   f"stop may not sit below the costed break-even {be:.5f} "
                   f"(entry {entry:.5f} {'+' if side == 1 else '-'} round trip "
                   f"{cost_per_unit:.5f}); {loser} at {trail_was:.5f} protects less")
        else:
            why += f"; already above the break-even floor {be:.5f}"

    # NEVER LOOSEN. For a long the stop may only rise; for a short, only fall.
    improves = (candidate > current_stop) if side == 1 else (candidate < current_stop)
    if not improves:
        return RatchetDecision(
            None, before, before, k, stalled,
            f"hold: {why}, which sits {'below' if side == 1 else 'above'} the current stop "
            f"{current_stop:.5f}, and a stop is never widened")

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
        f"{why}; protected {before:+.3f}R -> {after:+.3f}R", on_floor)
