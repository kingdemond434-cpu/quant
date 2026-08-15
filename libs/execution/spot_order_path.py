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

__all__ = ["MIN_STOP_GAP", "OrderOutcome", "floor_2dp", "place_entry", "retarget"]

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

    def as_row(self) -> dict[str, Any]:
        return {"symbol": self.symbol, "side": self.side, "usd": round(self.usd, 2),
                "placed": self.placed, "protected": self.protected, "why": self.why,
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


def place_entry(live: Any, symbol: str, usd: float, *, cycle: str, quote: str,
                free_quote: float, min_notional: float, stop_price: float | None = None,
                step: float = 0.0, place: bool = True,
                borrow: bool = False) -> OrderOutcome:
    """Buy `usd` of `symbol`, then rest its protective stop. Refuses with a stated reason.

    `live` is the connector module, injected rather than imported, so this stays testable without
    a venue and so a caller cannot be pointed at the live venue by accident.

    THE ORDER OF THE CHECKS IS THE ORDER OF THEIR COST. Rail first (a frozen book must not place
    at all), then arming, then whether the cash exists, then whether the venue would accept the
    size. Checking size before the rail would produce a beautifully-validated order on a book that
    is halted.
    """
    from libs.execution.ruin_rail import frozen

    sym = retarget(symbol, quote)
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

    try:
        kw: dict[str, Any] = {"cycle": cycle}
        if borrow:
            kw["borrow"] = True          # MARGIN_BUY; absent means NO_SIDE_EFFECT on both venues
        res = live.place_market_quote(sym, "BUY", spend, **kw)
    except Exception as exc:
        return OrderOutcome(sym, "BUY", spend, False, f"ORDER REJECTED ({type(exc).__name__}: "
                                                      f"{exc})")

    out = OrderOutcome(sym, "BUY", spend, True, f"filled ${spend:,.2f}{clamped}", result=res)
    if stop_price is None or stop_price <= 0:
        out.why += "; NO STOP DECLARED by the rule -- position is unprotected by construction"
        return out

    # THE STOP, IMMEDIATELY. Sized from what actually filled, not from what was requested: a
    # partial fill with a full-size stop is a stop that cannot execute.
    filled = 0.0
    try:
        filled = float(res.get("executedQty") or 0.0)
    except (TypeError, ValueError):
        filled = 0.0
    qty = _round_step(filled, step)
    if qty <= 0:
        out.why += "; STOP NOT PLACED -- venue reported no executed quantity to protect"
        return out
    limit = stop_price * (1.0 - MIN_STOP_GAP)
    try:
        out.stop_result = live.place_stop_loss_limit(sym, "SELL", qty, stop_price, limit,
                                                     cycle=cycle)
        out.protected = True
        out.why += f"; stop resting at {stop_price:.8g} (limit {limit:.8g})"
    except Exception as exc:
        out.why += (f"; STOP FAILED ({type(exc).__name__}: {exc}) -- POSITION IS UNPROTECTED. "
                    "Reported rather than swallowed: a stop that was never placed and one that "
                    "was are indistinguishable in a journal that logs only the fill")
    return out


def _round_step(qty: float, step: float) -> float:
    """DOWN to the venue's lot step. Rounding up on a protective stop asks to sell more than is
    held, which the venue refuses -- leaving the position unprotected at the moment it matters."""
    if step <= 0:
        return qty
    return float(int(qty / step) * step)
