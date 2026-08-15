"""Maker-first execution for the TESTNET FUTURES batch. **NOT THE LIVE PATH -- see `maker_first`.**

Pays the MAKER fee (~half the taker fee on Binance futures) on quotes that rest, instead of crossing
the spread every rebalance -- pure net-edge on a thin carry book, no alpha change. Batch design:
quote ALL legs passively, wait once, then market-fill only the unfilled remainder, so a 20-symbol
rebalance still completes in one short window. No look-ahead / no edge logic -- execution only.

**THIS MODULE CANNOT REACH A LIVE VENUE AND THAT IS NOT A CONFIGURATION DETAIL.** It imports
`binance_testnet` at module scope, so the connector is fixed at import time and no caller can point
it anywhere else. `scripts/run_crypto_testnet.py` is its one caller and testnet is where it belongs.
Until 2026-08-15 this was the ONLY maker router in the repo, which is how the live spot and margin
books came to cross the spread on every entry while a "maker-first execution" module sat in the
tree: the capability was real, tested, and structurally unable to touch the money path.

`libs/execution/maker_first.py` is the live one. It takes the connector as an ARGUMENT, resolves a
quote by order id rather than by cancelling every order on the symbol (this module's `cancel_all`
would take a resting protective stop with it), and reports its maker share by notional rather than
by leg. Two differences worth keeping in mind before merging them:

    * this one batches N symbols behind ONE wait, which matters for a 20-leg carry rebalance;
    * `maker_first` handles ONE order and resolves partial fills exactly, which matters when a
      protective stop has to be sized from what actually filled.
"""

from __future__ import annotations

import time
from typing import Any

from libs.execution import binance_testnet as bt


def _round_price(price: float, tick: float, prec: int) -> float:
    return round(round(price / tick) * tick, prec) if tick > 0 else round(price, prec)


def maker_execute_batch(orders: list[tuple[str, str, float]], *,
                        filters: dict[str, dict[str, float]],
                        book: dict[str, tuple[float, float]],
                        wait_s: float = 10.0) -> dict[str, str]:
    """Quote every (symbol, side, qty) post-only at the passive side, wait, taker-fill the rest.

    Returns {symbol: mode} where mode is 'maker' (rested then filled), 'taker_fallback' (unfilled ->
    market), or 'taker' (could not quote). Caller still owns sizing/targets; this only routes fills.
    """
    pending: dict[str, tuple[Any, str, float]] = {}
    result: dict[str, str] = {}
    for sym, side, qty in orders:
        f = filters.get(sym)
        bid, ask = book.get(sym, (0.0, 0.0))
        if not f or bid <= 0 or ask <= 0:
            bt.place_market(sym, side, qty)
            result[sym] = "taker"
            continue
        price = _round_price(bid if side == "BUY" else ask, f["tick"], int(f["price_prec"]))
        try:
            o = bt.place_post_only(sym, side, qty, price)
            oid = o.get("orderId")
            if oid is None:                            # GTX rejected (would cross) -> taker
                bt.place_market(sym, side, qty)
                result[sym] = "taker"
            else:
                pending[sym] = (oid, side, qty)
        except Exception:                              # GTX reject / transient -> taker
            bt.place_market(sym, side, qty)
            result[sym] = "taker"

    if not pending:
        return result
    time.sleep(wait_s)
    for sym, (oid, side, qty) in pending.items():
        try:
            resting = {x.get("orderId") for x in bt.open_orders(sym)}
        except Exception:
            resting = {oid}                            # assume still there -> fall back safely
        if oid in resting:
            bt.cancel_all(sym)
            bt.place_market(sym, side, qty)
            result[sym] = "taker_fallback"
        else:
            result[sym] = "maker"                      # no longer resting -> filled as maker
    return result


def maker_share(modes: dict[str, str]) -> float:
    """Fraction of legs filled as MAKER (the execution-quality KPI)."""
    if not modes:
        return 0.0
    return sum(1 for m in modes.values() if m == "maker") / len(modes)
