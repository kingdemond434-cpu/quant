"""MAKER-FIRST ENTRY: quote passively, wait once, then cross for the UNFILLED REMAINDER ONLY.

**THE LEAK THIS CLOSES.** Every live entry on this desk crossed the spread. `spot_order_path`
called `place_market_quote`; `run_margin_executor` called `place_market_quote`; the only maker
router in the repo -- `libs/execution/maker.py` -- imports `binance_testnet` at module scope and
has never been able to reach a live venue. A post-only path existed on the spot connector
(`place_post_only`, LIMIT_MAKER) with ZERO callers, and did not exist on the margin connector at
all. So the capability was present, tested, and wired to nothing on the path that spends money:
III.16, on the money path, in the one place it converts directly into cost.

**WHAT IT IS ACTUALLY WORTH, INCLUDING THE PART THAT IS NOT A SAVING.** Crossing costs half the
spread per leg: ~1bp on BTC, 5-20bp on the thin alt legs the mechanism sleeves rotate through.
Against that, a resting quote is ADVERSELY SELECTED -- it fills preferentially when the market is
coming toward it, which is to say when the trade was about to be worse. That is a real cost and it
is not small; on a short-horizon signal it can consume most of the spread saved. Three things make
the trade still worth taking here, and they are the reason this is defensible rather than folklore:

    1. the sleeves this serves rebalance on DAILY signals, so a 15-second wait is a rounding error
       against the horizon the edge is measured on;
    2. the taker fallback bounds the loss -- an unfilled quote becomes a market order, so the worst
       case is the old behaviour plus the drift across the wait, not an unfilled target;
    3. the mode is RETURNED, so `maker_share` is measurable rather than assumed. If the realised
       maker share is high and the realised slippage does not improve, that is the adverse-selection
       case showing up in the data and the wait should go to zero.

**NEVER `cancel_all`.** The obvious way to pull an unfilled quote cancels every open order on the
symbol -- including a resting STOP_LOSS_LIMIT protecting a position from an earlier cycle. That
turns an execution-routing decision into an unprotected position, silently, and on the margin book
an unprotected position is one the venue closes for you. This module cancels BY ORDER ID.

**AN AMBIGUOUS CANCEL PLACES NOTHING.** If the quote cannot be resolved -- cancel failed and the
status read failed too -- the remaining size is NOT crossed. A resting quote of unknown state plus
a market order for the same size is double the intended exposure, and on margin double the borrow.
The refusal is reported as `UNRESOLVED` and the caller sees an underweight leg with a stated reason,
which is the recoverable error. The other one is not.
"""

from __future__ import annotations

import time
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any

from libs.execution.spot_order_path import floor_2dp, round_step

__all__ = ["DEFAULT_WAIT_S", "MakerOutcome", "maker_first_buy", "maker_share"]

#: How long a quote is given to fill before the remainder is crossed. Not tuned -- chosen against
#: the signal horizon: the sleeves this serves publish daily targets, so the alpha decay across 15
#: seconds is negligible while the spread saved is not. A short-horizon caller should pass less.
DEFAULT_WAIT_S = 15.0

#: Connector functions the passive path needs. A connector missing ANY of these routes straight to
#: taker with that stated, rather than half-executing a maker path it cannot finish or resolve.
_REQUIRED = ("book_ticker", "place_post_only", "cancel_order", "order_status")


@dataclass
class MakerOutcome:
    """What the routing actually did. `mode` is the KPI; `why` is why it is not something better."""

    symbol: str
    mode: str                    # maker | taker_fallback | taker | unfilled | UNRESOLVED
    requested_usd: float
    maker_usd: float = 0.0       # quote actually filled passively
    taker_usd: float = 0.0       # quote crossed afterwards
    maker_qty: float = 0.0       # BASE units filled passively
    taker_qty: float = 0.0       # BASE units crossed
    why: str = ""
    result: dict[str, Any] = field(default_factory=dict)      # the LAST venue response
    maker_result: dict[str, Any] = field(default_factory=dict)

    @property
    def placed(self) -> bool:
        """Did anything reach the venue at all? UNRESOLVED can still be True -- that is the point
        of the state: something is out there and its size is not known."""
        return bool(self.maker_result or self.result)

    @property
    def filled_qty(self) -> float:
        """TOTAL base units held after this entry, across BOTH orders.

        **THE PROTECTIVE STOP IS SIZED FROM THIS AND FROM NOTHING ELSE.** A maker-first entry can
        produce two fills, and `executedQty` on either response is a fraction of the position. A
        stop sized from one of them leaves the rest of the position naked while every line on
        screen reads `protected`, which is the failure mode this desk has already paid for once in
        stops that were never placed at all.
        """
        return self.maker_qty + self.taker_qty

    def as_row(self) -> dict[str, Any]:
        return {"symbol": self.symbol, "mode": self.mode,
                "requested_usd": round(self.requested_usd, 2),
                "maker_usd": round(self.maker_usd, 2), "taker_usd": round(self.taker_usd, 2),
                "filled_qty": self.filled_qty, "why": self.why}


def _executed_base(res: dict[str, Any]) -> float:
    """BASE units an order response says it filled. Unreadable reads as 0.0 -- which understates
    the position and therefore the stop, and is the direction that fails loudly rather than the one
    that asks the venue to sell more than is held."""
    try:
        return max(0.0, float(res.get("executedQty") or 0.0))
    except (TypeError, ValueError):
        return 0.0


def _executed_quote(res: dict[str, Any], price: float) -> float:
    """Quote-asset amount an order response says it filled.

    `cummulativeQuoteQty` is authoritative when present. Falling back to executedQty*price is an
    APPROXIMATION and it is the safe direction only because the quote price is the worst price a
    LIMIT_MAKER buy can have filled at -- a passive bid never fills above its own price.
    """
    for key in ("cummulativeQuoteQty", "cumQuote"):
        try:
            v = float(res.get(key) or 0.0)
        except (TypeError, ValueError):
            v = 0.0
        if v > 0:
            return v
    try:
        return float(res.get("executedQty") or 0.0) * float(price)
    except (TypeError, ValueError):
        return 0.0


def _taker(live: Any, symbol: str, usd: float, *, cycle: str, borrow: bool) -> dict[str, Any]:
    kw: dict[str, Any] = {"cycle": cycle}
    if borrow:
        kw["borrow"] = True       # absent means NO_SIDE_EFFECT on both venues -- never defaulted on
    res = live.place_market_quote(symbol, "BUY", floor_2dp(usd), **kw)
    return dict(res) if isinstance(res, dict) else {"raw": res}


def maker_first_buy(live: Any, symbol: str, usd: float, *, cycle: str, min_notional: float,
                    step: float = 0.0, tick: float = 0.0, borrow: bool = False,
                    wait_s: float = DEFAULT_WAIT_S,
                    sleep: Any = time.sleep) -> MakerOutcome:
    """Buy `usd` of `symbol`, passively first. Always ends in a placement or a stated refusal.

    `live` is injected, never imported, so this is testable without a venue and so no caller can be
    pointed at the live book by editing an argument.

    THE FALLBACKS ARE NOT ERRORS. Routing to taker because the book is unreadable, because the size
    rounds below the venue minimum in base units, or because the venue rejected the post-only quote
    as crossing, are all ordinary outcomes with the old behaviour as their result. They are named in
    `why` so a maker share of zero is diagnosable instead of mysterious.
    """
    out = MakerOutcome(symbol=symbol, mode="taker", requested_usd=float(usd))

    def _cross(amount: float, why: str) -> MakerOutcome:
        """Cross for `amount` and record it. Every fallback goes through here so none of them can
        forget to record the base quantity the stop will be sized from."""
        out.why += why
        out.result = _taker(live, symbol, amount, cycle=cycle, borrow=borrow)
        out.taker_usd = floor_2dp(amount)
        out.taker_qty = _executed_base(out.result)
        return out

    missing = [n for n in _REQUIRED if not callable(getattr(live, n, None))]
    if missing:
        return _cross(usd, f"connector has no passive path (missing {', '.join(missing)}) -- "
                           "crossing, which is what this caller did before maker-first existed")

    try:
        bid, ask = live.book_ticker().get(symbol, (0.0, 0.0))
    except Exception as exc:
        bid = ask = 0.0
        out.why = f"book unreadable ({type(exc).__name__}) -- "
    if bid <= 0 or ask <= 0 or ask < bid:
        return _cross(usd, "no top-of-book to quote against, crossing instead")

    # THE PASSIVE SIDE, ROUNDED DOWN. A BUY quotes at the BID; rounding the price UP to the tick
    # could lift it through the ask, and a LIMIT_MAKER that would cross is rejected outright -- so
    # rounding the safe direction is the difference between a maker fill and no order at all.
    price = round_step(float(bid), float(tick)) if tick > 0 else float(bid)
    qty = round_step(float(usd) / price, float(step)) if price > 0 else 0.0
    if price <= 0 or qty <= 0 or qty * price < min_notional:
        return _cross(usd, f"passive size {qty:g} @ {price:g} is below the venue minimum "
                           f"${min_notional:,.2f} in BASE units -- a quote-sized market order can "
                           "still express this, a lot-stepped limit cannot, so crossing")

    try:
        kw: dict[str, Any] = {"cycle": cycle}
        if borrow:
            kw["borrow"] = True
        quote = live.place_post_only(symbol, "BUY", qty, price, **kw)
        quote = dict(quote) if isinstance(quote, dict) else {"raw": quote}
    except Exception as exc:
        # LIMIT_MAKER rejects when it would cross -- an ordinary race, not a failure.
        return _cross(usd, f"post-only rejected ({type(exc).__name__}: {str(exc)[:80]}) -- the "
                           "quote would have crossed, crossing deliberately instead")

    order_id = quote.get("orderId")
    out.maker_result = quote
    if order_id is None:
        out.why += ("venue accepted the quote but returned no orderId, so it cannot be resolved or "
                    "cancelled. NOT crossing on top of an order of unknown state")
        out.mode = "UNRESOLVED"
        return out

    sleep(float(wait_s))

    # RESOLVE BY ID. Cancel first: its response carries the executed amount, so one call both pulls
    # the order and reports what it did. `open_orders` cannot do that -- it answers "is it resting",
    # which cannot separate a full fill from a partial one.
    filled_usd: float | None = None
    try:
        cancelled = dict(live.cancel_order(symbol, order_id) or {})
        filled_usd = _executed_quote(cancelled, price)
        out.maker_qty = _executed_base(cancelled)
    except Exception as cancel_exc:
        try:
            st = dict(live.order_status(symbol, order_id) or {})
        except Exception as status_exc:
            out.mode = "UNRESOLVED"
            out.why += (f"cancel failed ({type(cancel_exc).__name__}) AND status unreadable "
                        f"({type(status_exc).__name__}). The quote may be resting, partly filled "
                        "or complete; crossing the remainder now would double the position if it "
                        "is still live. Leaving the leg underweight is the recoverable error")
            return out
        state = str(st.get("status") or "").upper()
        filled_usd = _executed_quote(st, price)
        out.maker_qty = _executed_base(st)
        if state not in {"FILLED", "CANCELED", "EXPIRED", "REJECTED"}:
            out.mode = "UNRESOLVED"
            out.maker_usd = filled_usd
            out.why += (f"cancel failed ({type(cancel_exc).__name__}) and the order is still "
                        f"{state or 'UNKNOWN'} at the venue. It remains live and will be resolved "
                        "on the next cycle; nothing is crossed on top of a resting order")
            return out

    out.maker_usd = float(filled_usd or 0.0)
    remainder = floor_2dp(float(usd) - out.maker_usd)
    if remainder < min_notional:
        out.result = quote
        if out.maker_usd > 0:
            out.mode = "maker"
            out.why += (f"filled ${out.maker_usd:,.2f} passively; remainder ${remainder:,.2f} is "
                        f"below the venue minimum ${min_notional:,.2f} and is not worth crossing")
        else:
            # Reachable only when the requested size was itself within a cent of the minimum.
            # NOT called a taker: nothing was crossed, and a mode that names an order which was
            # never sent is exactly the kind of report the maker-share number would then average.
            out.mode = "unfilled"
            out.why += (f"quote never filled and the full ${remainder:,.2f} is below the venue "
                        f"minimum ${min_notional:,.2f} -- nothing crossed, leg is flat")
        return out

    out.result = _taker(live, symbol, remainder, cycle=cycle, borrow=borrow)
    out.taker_usd = remainder
    # THE BASE QUANTITY, WHICH THIS LINE FORGOT AND A TEST CAUGHT. `filled_qty` is what the caller
    # sizes the protective stop from; leaving the crossed leg out of it puts a stop over the maker
    # fill only and the rest of the position behind nothing, while the report reads `protected`.
    out.taker_qty = _executed_base(out.result)
    out.mode = "taker_fallback"
    out.why += (f"quoted passively at {price:g} for {wait_s:g}s, filled ${out.maker_usd:,.2f}; "
                f"crossed ${remainder:,.2f} for the remainder")
    return out


def maker_share(outcomes: Sequence[Any]) -> float | None:
    """Share of DOLLARS filled passively -- None when nothing was placed.

    BY NOTIONAL, NOT BY LEG. `libs/execution/maker.py` counts legs, which lets twenty $5 legs
    outvote one $500 leg on a number whose only purpose is to estimate money saved. None rather
    than 0.0 on an empty book: no legs is not a bad maker share, it is no measurement (L1.28a).

    TAKES ANYTHING CARRYING `maker_usd` AND `taker_usd` -- `MakerOutcome` from this module and
    `OrderOutcome` from the order path both do. ONE implementation, deliberately: two runners each
    computing their own maker share is two numbers that can disagree about the same book, and the
    disagreement would surface as a KPI nobody trusts rather than as an error anybody fixes.
    """
    def _pair(o: Any) -> tuple[float, float]:
        return (float(getattr(o, "maker_usd", 0.0) or 0.0),
                float(getattr(o, "taker_usd", 0.0) or 0.0))

    pairs = [_pair(o) for o in outcomes]
    total = sum(m + t for m, t in pairs)
    if total <= 0:
        return None
    return round(sum(m for m, _ in pairs) / total, 4)
