"""THE SHORT ENTRY PATH -- borrow the base, sell it, and rest a stop ABOVE the fill.

**WHY THIS DID NOT EXIST, AND WHY THAT COST MORE THAN ANY OTHER GAP ON THE DESK.** Every return
projection this desk publishes runs into rho_bar = 0.375, k_eff 2.0, and a ceiling near +17%/yr
that no number of additional sleeves can move. rho is that high for one structural reason: every
sleeve the book can hold is LONG CRYPTO, so they all load the same factor. Three pre-registered
fade mechanisms -- H1, H7, H11 -- journal a REFUSAL on every signal rather than a trade.

The desk believed shorts were forbidden. They were not. `probe_short_capability` read
`/sapi/v1/margin/maxBorrowable` on 2026-08-16 and found NINE OF TEN base assets borrowable, at
carry rates BELOW the cost of the long side's quote borrow -- BTC at 0.44%/yr against USDC's 5.1%.
Two different restrictions had been treated as one: MiCA blocks DERIVATIVES (the futures account
genuinely cannot be read), while `spot_order_path`'s SELL refusal was an UNBUILT PATH, and said so
in its own comment: it refuses "until a short path exists that borrows the base asset and inverts
the stop". This is that path.

================================================================================================
A SHORT IS NOT A MIRRORED LONG. FOUR WAYS, EACH OF WHICH IS A REFUSAL BELOW.
================================================================================================

1. THE LOSS IS UNBOUNDED ABOVE. A long can only fall to zero; a borrowed asset can triple. The
   per-trade risk fraction the long book uses is not transferable, and no caller may pass a
   leverage figure computed for the long book.

2. THE MARGIN-CALL BAND BINDS EARLIER. Selling borrowed base leaves the QUOTE proceeds as an asset
   and the BASE as a liability, so the level at entry is `(1+g)/g` against a long's `f/(f-1)`.
   Those are different functions and the short's is worse at every size: the call band starts at
   2.00x gross where a long reaches it only at 3.00x. `MAX_SHORT_GROSS` is therefore a separate,
   lower constant -- sharing one with the long book would silently open shorts inside the band.

3. LIQUIDATION ARRIVES SOONER AT THE SAME SIZE -- 36.4% adverse at 2x gross against a long's 45.0%
   -- and for a structural reason: an adverse move for a long shrinks the ASSET while the debt is
   fixed, but an adverse move for a short GROWS THE DEBT while the collateral sits still. The ratio
   deteriorates from both ends at once.

4. THE STOP IS ABOVE THE ENTRY, and it is a BUY. A stop below a short is not a loose stop, it is a
   TAKE-PROFIT wearing a stop's name -- it would close the winner and leave the loser running,
   which is precisely the trade that ends an account. A stop at or below entry is REFUSED here,
   never adjusted, because silently moving a caller's stop to the other side of the market would
   be this module deciding what the rule meant.

**AUTO_REPAY ON THE CLOSE, ALWAYS.** Buying the base back without repaying leaves the loan
outstanding and the position closed -- interest accruing against a book that no longer holds the
risk. On a short the repayment IS the exit.

**IT PLACES A TAKER ENTRY, DELIBERATELY, FOR NOW.** `maker_first` exists and saves the spread, but
its sell path carries AUTO_REPAY (it was built to CLOSE longs) and a short entry needs MARGIN_BUY.
Routing the first short through a passive path with the wrong side effect would repay a loan the
position needs. Maker-first on short entries is follow-up work, named here rather than implied.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from libs.execution.ruin_rail import frozen
from libs.execution.spot_order_path import (
    MIN_STOP_GAP,
    floor_2dp,
    retarget,
    round_step,
)

__all__ = ["ShortOutcome", "max_short_notional", "place_short_entry", "size_from_risk"]


@dataclass
class ShortOutcome:
    """What the short path did. `protected` is only ever True with a resting stop ABOVE the fill."""

    symbol: str
    usd: float
    placed: bool
    why: str
    protected: bool = False
    qty: float = 0.0
    result: dict[str, Any] = field(default_factory=dict)
    stop_result: dict[str, Any] = field(default_factory=dict)

    def as_row(self) -> dict[str, Any]:
        return {"symbol": self.symbol, "side": "SELL", "usd": round(self.usd, 2),
                "placed": self.placed, "protected": self.protected, "qty": self.qty,
                "why": self.why, "result": self.result, "stop_result": self.stop_result}


def max_short_notional(equity_usd: float, live: Any) -> tuple[float, str]:
    """The largest short this equity may carry, from the VENUE's own call band.

    Returns (usd, why). Bounded by `MAX_SHORT_GROSS`, which is `1/(call_level-1)` -- the gross at
    which a FRESH short opens already inside the margin-call band. Not a risk preference: above it
    the venue restricts the account on day zero and may close the position at its convenience.
    """
    cap = float(getattr(live, "MAX_SHORT_GROSS", 2.0))
    d = None
    fn = getattr(live, "short_liquidation_distance", None)
    if callable(fn):
        d = fn(cap)
    tail = "" if d is None else f", LIQUIDATED BY A {d:.1%} ADVERSE MOVE"
    return float(equity_usd) * cap, (
        f"{cap:.2f}x gross on ${float(equity_usd):,.2f} equity -- the venue's own margin-call band "
        f"for a SHORT, which binds at {cap:.2f}x where a LONG reaches it at 3.00x{tail}")


def size_from_risk(equity_usd: float, entry: float, stop: float, *,
                   risk_frac: float) -> tuple[float, str]:
    """Notional such that a stop-out costs `risk_frac` of equity. (usd, why); 0.0 when unsizeable.

    RISK IS THE DISTANCE TO THE STOP, NOT THE NOTIONAL. A short with a 2% stop and one with a 20%
    stop are the same trade at different sizes, and sizing by notional makes the second one twenty
    times the loss for the same idea. The long book learned this; the short book inherits it rather
    than rediscovering it with borrowed money.
    """
    e, s = float(entry), float(stop)
    if e <= 0 or s <= 0:
        return 0.0, "entry or stop is not a positive price"
    if s <= e:
        return 0.0, (f"stop {s:g} is AT OR BELOW the entry {e:g} -- on a short that is a "
                     "TAKE-PROFIT, not a stop. Refusing rather than inverting it")
    gap = (s - e) / e
    if gap < MIN_STOP_GAP:
        return 0.0, (f"stop is {gap:.4%} above entry, inside the {MIN_STOP_GAP:.2%} minimum gap -- "
                     "a stop that close is noise and would be swept before the idea resolves")
    return float(equity_usd) * float(risk_frac) / gap, (
        f"{risk_frac:.2%} of ${float(equity_usd):,.2f} at a {gap:.2%} stop distance")


def place_short_entry(live: Any, symbol: str, usd: float, *, cycle: str, quote: str,
                      equity_usd: float, entry_price: float, stop_price: float,
                      min_notional: float, step: float = 0.0,
                      gross_open_usd: float = 0.0,
                      place: bool = True) -> ShortOutcome:
    """Borrow the base, sell `usd` of it, and rest the protective BUY stop above the fill.

    THE ORDER OF THE REFUSALS IS THE ORDER OF THEIR COST: rail, then the connector's ability to
    borrow at all, then the stop's SIDE, then the venue's call band, then size. Checking size first
    would produce a beautifully-sized short on a halted book, or on a wallet that cannot borrow.
    """
    sym = retarget(symbol, quote)

    def out_refuse(why: str) -> ShortOutcome:
        return ShortOutcome(sym, float(usd), False, why)

    rail, why_rail = frozen()
    if rail:
        return out_refuse(f"RUIN RAIL LATCHED -- {why_rail}")

    # A SHORT REQUIRES A BORROWING WALLET. On spot there is nothing to borrow the base from, so a
    # SELL there closes inventory rather than opening a position -- the exact confusion that made
    # `spot_order_path` refuse SELL in the first place.
    if not getattr(live, "SUPPORTS_BORROW", False):
        return out_refuse(
            "WALLET CANNOT BORROW -- a short borrows the BASE asset, which a spot wallet cannot "
            "do. A SELL there would close inventory, not open a short")

    armed, why_armed = live.is_armed()
    if not armed:
        return out_refuse(f"NOT ARMED -- {why_armed}")

    # THE STOP'S SIDE, BEFORE ANYTHING ELSE ABOUT SIZE. See the module docstring: a stop below a
    # short is a take-profit, and placing one would close winners and let losers run.
    if not (stop_price > entry_price > 0):
        return out_refuse(
            f"STOP {stop_price:g} IS NOT ABOVE ENTRY {entry_price:g} -- on a short the stop sits "
            "ABOVE the fill. A stop below it is a TAKE-PROFIT wearing a stop's name: it would "
            "close the winner and leave the loser running, with an unbounded loss above")

    gap = (stop_price - entry_price) / entry_price
    if gap < MIN_STOP_GAP:
        return out_refuse(
            f"stop is {gap:.4%} above entry, inside the {MIN_STOP_GAP:.2%} minimum -- swept by "
            "noise before the idea resolves")

    cap_usd, why_cap = max_short_notional(equity_usd, live)
    if gross_open_usd + float(usd) > cap_usd + 1e-9:
        return out_refuse(
            f"SHORT GROSS CAP -- ${gross_open_usd:,.2f} already short plus ${float(usd):,.2f} "
            f"exceeds ${cap_usd:,.2f}. {why_cap}. REFUSED, never clamped: a silently shrunk short "
            "is a position nobody chose, and the caller's risk arithmetic no longer describes it")

    spend = floor_2dp(usd)
    if spend < min_notional:
        return out_refuse(f"${spend:,.2f} is below the venue minimum ${min_notional:,.2f}")
    if not place:
        return ShortOutcome(sym, spend, False,
                            f"DRY RUN -- would BORROW and SELL ${spend:,.2f}; stop at "
                            f"{stop_price:.8g} ({gap:.2%} above). {why_cap}")

    try:
        # MARGIN_BUY on a SELL borrows the BASE asset this order needs and no more. Borrowing
        # first and selling second would be two operations that can succeed apart, leaving a
        # borrowed coin with no position against it and interest running on idle debt.
        res = dict(live.place_market_quote(sym, "SELL", spend, cycle=cycle, borrow=True) or {})
    except Exception as exc:
        return out_refuse(f"SHORT ENTRY REJECTED ({type(exc).__name__}: {exc})")

    out = ShortOutcome(sym, spend, True,
                       f"borrowed and sold ${spend:,.2f}; {why_cap}", result=res)
    try:
        filled = max(0.0, float(res.get("executedQty") or 0.0))
    except (TypeError, ValueError):
        filled = 0.0
    # ROUND UP IS WRONG HERE AND ROUND DOWN IS RIGHT. The stop BUYS BACK what was sold; buying more
    # than was borrowed would leave a residual LONG in an asset the desk never chose to hold.
    qty = round_step(filled, step)
    out.qty = qty
    if qty <= 0:
        out.why += ("; STOP NOT PLACED -- venue reported no executed quantity, so there is no "
                    "borrowed size to buy back. THE SHORT MAY STILL BE OPEN AND IS UNPROTECTED")
        return out

    # The stop LIMIT sits ABOVE the trigger on a short: the closing order is a BUY, so it needs
    # room upward to fill, exactly inverting the long path's downward gap.
    limit = stop_price * (1.0 + MIN_STOP_GAP)
    try:
        out.stop_result = live.place_stop_loss_limit(sym, "BUY", qty, stop_price, limit,
                                                     cycle=cycle)
        out.protected = True
        out.why += f"; stop resting at {stop_price:.8g} (limit {limit:.8g}, AUTO_REPAY)"
    except Exception as exc:
        out.why += (f"; STOP FAILED ({type(exc).__name__}: {exc}) -- SHORT IS UNPROTECTED AND ITS "
                    "LOSS IS UNBOUNDED ABOVE. Reported rather than swallowed: this is the one "
                    "position on the desk with no natural floor under it")
    return out
