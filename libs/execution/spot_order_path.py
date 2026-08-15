"""ONE PLACEMENT PRIMITIVE, SHARED -- because eleven rules must not mean eleven sets of rails.

The discretionary sleeve detects setups for H1-H11 and the momentum book publishes target weights.
Both end at the same question: turn a dollar figure into a spot order, or refuse with a reason. If
each grew its own answer, the desk would have two implementations of the min-notional check, two
of the rounding direction, two readings of the ruin rail -- and they would drift, silently, in the
one place where drift costs money.

EVERY REFUSAL PATH HERE WAS PAID FOR IN A REAL REJECTED ORDER on 2026-08-15:

  * `-2010 This symbol is not permitted` -- the research universe is USDT-quoted and EEA retail
    may not trade Binance USDT pairs under MiCA. The quote is a settlement detail; `retarget`
    moves it without touching the signal.
  * `-2010 Account has insufficient balance` -- the target was computed from EQUITY, which counts
    coins already held, while a buy spends CASH. Orders are clamped to the free balance.
  * The same again -- because the clamp rounded 36.20972275 to 36.21, which is $0.00028 more than
    existed. Quote amounts FLOOR. Rounding to nearest is safe on every order except the one that
    spends the whole balance, which is exactly the order a rebalance ends on.

**A PROTECTIVE STOP RESTS AT THE VENUE OR THE ENTRY DOES NOT HAPPEN.** For a rule that declares a
stop -- every discretionary hypothesis does -- the stop is placed as a venue-held STOP_LOSS_LIMIT
immediately after the fill, and a failure to place it is reported as an UNPROTECTED position rather
than swallowed. A stop that lives in a journal is an intention that dies with the process, and the
outage that kills the process is the one it was needed for.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

__all__ = [
    "MIN_STOP_GAP", "OrderOutcome", "floor_2dp", "place_entry", "retarget", "round_step"]

#: Quote suffixes a research symbol may arrive in, longest first so BTCUSDT strips USDT rather than
#: matching a shorter suffix inside it. Order matters and is not alphabetical by accident.
_KNOWN_QUOTES = ("USDT", "USDC", "FDUSD", "TUSD", "EUR", "GBP", "BTC")

#: How far the protective LIMIT sits beyond the STOP trigger, as a fraction of the stop price.
#: Binance spot has no STOP_LOSS_MARKET, so a limit equal to the trigger is the version that looks
#: protected and fills least often -- in the fast move the stop exists for, the book is already
#: through it. 0.5% is wide enough to fill through ordinary slippage and tight enough that the
#: realised loss stays close to the declared one.
MIN_STOP_GAP = 0.005


@dataclass
class OrderOutcome:
    """What happened, in enough detail to audit later. `placed` false is never silent."""

    symbol: str
    side: str
    usd: float
    placed: bool
    why: str
    protected: bool = False
    result: dict[str, Any] = field(default_factory=dict)
    stop_result: dict[str, Any] = field(default_factory=dict)
    #: How the entry was routed, and how much of it rested. Recorded as FIELDS rather than left in
    #: the `why` prose because the maker share is the number that decides whether the passive wait
    #: is earning its adverse selection -- and a number nobody can aggregate is not a measurement.
    route: str = "taker"
    maker_usd: float = 0.0
    taker_usd: float = 0.0

    def as_row(self) -> dict[str, Any]:
        return {"symbol": self.symbol, "side": self.side, "usd": round(self.usd, 2),
                "placed": self.placed, "protected": self.protected, "why": self.why,
                "route": self.route, "maker_usd": round(self.maker_usd, 2),
                "taker_usd": round(self.taker_usd, 2),
                "result": self.result, "stop_result": self.stop_result}


def retarget(symbol: str, quote: str) -> str:
    """Re-quote a research symbol onto the asset THIS ACCOUNT MAY TRADE. `quote=""` gives the bare
    base, which is how balances are keyed."""
    for q in _KNOWN_QUOTES:
        if symbol.endswith(q):
            return symbol[: -len(q)] + quote
    return symbol + quote


def floor_2dp(x: float) -> float:
    """DOWN to the cent, never to nearest -- see the module docstring for what this cost."""
    return math.floor(x * 100.0) / 100.0


def _executed_qty(res: Any) -> float:
    """Base units a single venue response reports filling. Unreadable reads as 0.0, which
    UNDERSTATES the position and therefore the stop -- the direction that fails visibly rather
    than the one that asks the venue to sell more than is held."""
    try:
        return max(0.0, float(dict(res or {}).get("executedQty") or 0.0))
    except (TypeError, ValueError):
        return 0.0


def place_entry(live: Any, symbol: str, usd: float, *, cycle: str, quote: str,
                free_quote: float, min_notional: float, stop_price: float | None = None,
                step: float = 0.0, place: bool = True,
                borrow: bool = False, side: str = "BUY",
                tick: float = 0.0, maker: bool = True,
                maker_wait_s: float | None = None) -> OrderOutcome:
    """Buy `usd` of `symbol`, then rest its protective stop. Refuses with a stated reason.

    `live` is the connector module, injected rather than imported, so this stays testable without
    a venue and so a caller cannot be pointed at the live venue by accident.

    THE ORDER OF THE CHECKS IS THE ORDER OF THEIR COST. Rail first (a frozen book must not place
    at all), then arming, then whether the cash exists, then whether the venue would accept the
    size. Checking size before the rail would produce a beautifully-validated order on a book that
    is halted.

    **`maker=True` IS THE DEFAULT AND IT CHANGES WHAT THIS COSTS.** Until 2026-08-15 this function
    crossed the spread on every entry it ever placed, because `place_market_quote` was the only
    thing it knew how to call -- while a post-only path sat unused on the spot connector. On the
    thin alt legs the discretionary rules trade, half the spread is 5-20bps a side against an edge
    measured in tens of bps. `libs/execution/maker_first` quotes passively first and crosses only
    the unfilled remainder, so the worst case is the previous behaviour plus the drift across the
    wait. Pass `maker=False` for a signal whose decay does not survive a 15-second quote.
    """
    from libs.execution.ruin_rail import frozen

    sym = retarget(symbol, quote)
    # THIS PRIMITIVE BUYS. IT HAS NEVER DONE ANYTHING ELSE, and until 2026-08-15 nothing said so.
    #
    # MEASURED, LIVE, ON THE PRINCIPAL'S ACCOUNT. `run_discretionary_live` refused shorts only
    # under --spot-only. Run WITHOUT that flag against the margin wallet, two SELL signals reached
    # this function and were placed as BUYS -- the exact opposite of the trade the rule called --
    # and their stops, sized for a short, went in ABOVE the market where they protect nothing. Two
    # inverted, unprotected positions, and every printed line read TAKE.
    #
    # The caller's guard was a FLAG. A flag is an instruction to whoever types the command; this is
    # the mechanism. A short is not a smaller version of a buy: it borrows the base asset, its stop
    # is above the entry, and its liquidation arithmetic is different. Until a real short path
    # exists, a SELL is REFUSED here, loudly, on every wallet.
    if str(side).upper() != "BUY":
        return OrderOutcome(
            sym, str(side).upper(), usd, False,
            f"SIDE {side!r} REFUSED -- this order path opens LONGS ONLY. It has always sent BUY "
            "regardless of the side requested, so a SELL routed here would be filled in the "
            "opposite direction with a stop that cannot protect it. Refusing is the only correct "
            "behaviour until a short path exists that borrows the base asset and inverts the stop")
    rail, why_rail = frozen()
    if rail:
        return OrderOutcome(sym, "BUY", usd, False, f"RUIN RAIL LATCHED -- {why_rail}")

    armed, why_armed = live.is_armed()
    if not armed:
        return OrderOutcome(sym, "BUY", usd, False, f"NOT ARMED -- {why_armed}")

    # BORROW IS REFUSED BEFORE ANYTHING IS SENT, not caught afterwards. A levered size routed to a
    # connector that cannot borrow would otherwise be clamped to free cash and filled -- a leg that
    # looks successful while carrying a fraction of the exposure its sizing assumed, which is the
    # quietest way to be wrong about a position.
    if borrow and not getattr(live, "SUPPORTS_BORROW", False):
        return OrderOutcome(
            sym, "BUY", usd, False,
            f"BORROW REQUESTED of {getattr(live, '__name__', live)}, which cannot borrow. Refusing "
            "rather than placing an unlevered leg: the caller sized this expecting leverage")

    # THE FREE-CASH CLAMP DOES NOT APPLY TO A BORROWING LEG. On cross margin the venue funds the
    # difference (MARGIN_BUY), so clamping to free quote would cap the book at 1x and silently
    # discard the leverage the policy computed.
    spend = floor_2dp(usd if borrow else min(usd, free_quote))
    if spend < min_notional:
        return OrderOutcome(
            sym, "BUY", spend, False,
            f"${spend:,.2f} spendable (wanted ${usd:,.2f}, ${free_quote:,.2f} free in {quote}) is "
            f"below the venue minimum ${min_notional:,.2f} -- nothing placeable, and the leg says "
            "so rather than leaving the operator to infer it")
    if spend < usd:
        clamped = (f"; CLAMPED from ${usd:,.2f} to the ${free_quote:,.2f} actually free, so this "
                   "lands underweight")
    else:
        clamped = ""

    if not place:
        return OrderOutcome(sym, "BUY", spend, False,
                            f"DRY RUN -- would buy ${spend:,.2f}{clamped}"
                            f"{' (MARGIN_BUY: borrows the shortfall)' if borrow else ''}")

    from libs.execution.maker_first import DEFAULT_WAIT_S, maker_first_buy

    try:
        maker_usd = taker_usd = 0.0
        if maker:
            routed = maker_first_buy(
                live, sym, spend, cycle=cycle, min_notional=min_notional, step=step, tick=tick,
                borrow=borrow,
                wait_s=DEFAULT_WAIT_S if maker_wait_s is None else float(maker_wait_s))
            res, filled, mode, routing_why = (
                routed.result, routed.filled_qty, routed.mode, routed.why)
            maker_usd, taker_usd = routed.maker_usd, routed.taker_usd
        else:
            kw: dict[str, Any] = {"cycle": cycle}
            if borrow:
                kw["borrow"] = True      # MARGIN_BUY; absent means NO_SIDE_EFFECT on both venues
            res = live.place_market_quote(sym, "BUY", spend, **kw)
            filled = _executed_qty(res)
            taker_usd = spend
            mode, routing_why = "taker", "maker routing disabled by the caller"
    except Exception as exc:
        return OrderOutcome(sym, "BUY", spend, False, f"ORDER REJECTED ({type(exc).__name__}: "
                                                      f"{exc})")

    # AN UNRESOLVED QUOTE IS NOT A FILL. The passive order may still be live at the venue, so the
    # position can still GROW after this returns -- and a stop sized here would then cover part of
    # it. Reported as placed (something is out there) and never as protected.
    out = OrderOutcome(sym, "BUY", spend, True,
                       f"filled ${spend:,.2f}{clamped} [{mode}: {routing_why}]", result=res,
                       route=mode, maker_usd=maker_usd, taker_usd=taker_usd)
    if stop_price is None or stop_price <= 0:
        out.why += "; NO STOP DECLARED by the rule -- position is unprotected by construction"
        return out

    # THE STOP, IMMEDIATELY. Sized from what actually filled, not from what was requested: a
    # partial fill with a full-size stop is a stop that cannot execute. `filled` is the TOTAL
    # across both legs of a maker-first entry -- see `MakerOutcome.filled_qty` for why summing
    # them rather than reading one response is the whole point.
    qty = round_step(filled, step)
    if qty <= 0:
        out.why += "; STOP NOT PLACED -- venue reported no executed quantity to protect"
        return out
    limit = stop_price * (1.0 - MIN_STOP_GAP)
    try:
        out.stop_result = live.place_stop_loss_limit(sym, "SELL", qty, stop_price, limit,
                                                     cycle=cycle)
        # PROTECTED ONLY WHEN THE FILL IS FINAL. An UNRESOLVED passive quote can still fill after
        # this returns, and this stop covers only what was known at the time -- so the flag that
        # every downstream report reads as "safe" must not be set on a position whose size is
        # still moving. The stop is placed regardless: protecting part is better than none.
        out.protected = mode != "UNRESOLVED"
        out.why += f"; stop resting at {stop_price:.8g} (limit {limit:.8g})"
        if mode == "UNRESOLVED":
            out.why += ("; NOT MARKED PROTECTED -- the passive quote is unresolved, so the "
                        "position may grow past what this stop covers before the next cycle")
    except Exception as exc:
        out.why += (f"; STOP FAILED ({type(exc).__name__}: {exc}) -- POSITION IS UNPROTECTED. "
                    "Reported rather than swallowed: a stop that was never placed and one that "
                    "was are indistinguishable in a journal that logs only the fill")
    return out


def round_step(qty: float, step: float) -> float:
    """DOWN to the venue's lot step. Rounding up on a protective stop asks to sell more than is
    held, which the venue refuses -- leaving the position unprotected at the moment it matters."""
    if step <= 0:
        return qty
    # QUANTIZED IN DECIMAL, NOT MULTIPLIED BACK IN BINARY FLOAT. `int(qty/step) * step` is exact
    # in the abstract and produces 60.800000000000004 in practice -- and the venue rejects it:
    # measured live 2026-08-15, `{"code":51077,"msg":"Precision is over the maximum"}` on an ADA
    # reduce leg whose quantity was correct to the step and wrong in its 15th decimal place. The
    # order was refused, the position stayed, and every number on screen looked right.
    from decimal import ROUND_DOWN, Decimal

    # DIVIDE, FLOOR, MULTIPLY -- ALL IN DECIMAL. Quantizing to the step's DECIMAL PLACES is not the
    # same operation: a step of 1.0 has one decimal place, so quantize would return 59.9 for a
    # step that only permits whole units. Dividing by the step and flooring to an integer is the
    # step rule itself, and doing it in Decimal keeps the result free of the binary tail that the
    # venue rejected.
    d_step = Decimal(str(step))
    units = (Decimal(str(qty)) / d_step).to_integral_value(rounding=ROUND_DOWN)
    return float((units * d_step).normalize())
