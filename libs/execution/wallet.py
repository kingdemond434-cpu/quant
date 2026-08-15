"""WHICH WALLET THE SLEEVES TRADE FROM -- one selector, so moving capital does not silence a book.

WHY THIS EXISTS. The momentum executor and the discretionary sleeve both imported
`binance_spot_live` directly. That is correct until the principal moves capital into the margin
wallet, at which point the spot wallet is empty and both sleeves keep working perfectly: the
executor reads ~$0 of equity and places nothing, the sleeve finds no free quote and refuses all
eleven rules for insufficient funds. No error, no alarm, and a book that has simply stopped.

Binance treats spot and cross-margin as SEPARATE WALLETS with separate balances. A transfer between
them is invisible to code that has hardcoded one of them, and the failure it produces looks exactly
like a quiet market.

**MARKET DATA COMES FROM THE SPOT ENDPOINTS EITHER WAY.** Prices and exchange filters are public
and identical -- there is one BNBUSDC market, not a spot one and a margin one. Only BALANCES and
ORDERS differ, so only those are routed.
"""

from __future__ import annotations

from typing import Any

__all__ = ["WALLETS", "connector", "is_margin", "locate_capital"]

WALLETS = ("spot", "margin")


def is_margin(name: str) -> bool:
    return str(name).strip().lower() == "margin"


def connector(name: str) -> Any:
    """The module that owns balances and orders for this wallet.

    Raises on an unknown name rather than defaulting to spot. A typo'd `--wallet margn` silently
    trading the wrong wallet is the failure this whole module exists to prevent, and a default
    would reintroduce it at the one place it is easiest to make.
    """
    key = str(name).strip().lower()
    if key == "spot":
        from libs.execution import binance_spot_live
        return binance_spot_live
    if key == "margin":
        from libs.execution import binance_margin_live
        return binance_margin_live
    raise ValueError(f"unknown wallet {name!r} -- expected one of {WALLETS}. Refusing to default: "
                     "a typo that silently trades the wrong wallet is the failure this prevents")


def locate_capital(quote: str = "USDC") -> dict[str, Any]:
    """Where the money ACTUALLY is, across both wallets. Read-only; it transfers nothing.

    **AN EMPTY WALLET AND AN UNCHANGED BOOK PRODUCE THE SAME ARTIFACT.** A sleeve pointed at a
    wallet the capital has left places no orders, reports no error, and its row reads exactly like
    a day when every target was already on side. That is the failure this module's header
    describes, and until now nothing could tell the two apart at runtime -- the header named the
    hazard and no code checked for it. This is the check.

    Every read is wrapped: an unreadable wallet is reported as None, NEVER as 0.0. Zero is a
    measurement that the money is gone; None is the statement that nobody looked successfully, and
    collapsing the second into the first is how "the API key lost margin permission" comes to read
    as "the account is empty".
    """
    out: dict[str, Any] = {"quote": quote, "balances": {}, "errors": {}}
    for w in WALLETS:
        try:
            out["balances"][w] = float(connector(w).balances().get(quote, 0.0))
        except Exception as exc:                    # reported below, never swallowed
            out["balances"][w] = None
            out["errors"][w] = f"{type(exc).__name__}: {exc}"
    readable = {w: v for w, v in out["balances"].items() if v is not None}
    out["richest"] = max(readable, key=lambda w: readable[w]) if readable else None
    out["total_readable"] = sum(readable.values()) if readable else None
    return out


def misplaced_capital(wallet: str, quote: str = "USDC", *,
                      min_notional: float = 10.0) -> str | None:
    """A sentence naming the other wallet when THIS one cannot fund a trade and the other can.

    Returns None when there is nothing to say -- either the chosen wallet has the money, or
    neither does, in which case "the book is out of capital" is the honest report and pointing at
    an equally empty wallet would be noise.
    """
    loc = locate_capital(quote)
    here = loc["balances"].get(wallet)
    if here is not None and here >= min_notional:
        return None
    other = next((w for w in WALLETS if w != wallet), None)
    there = loc["balances"].get(other) if other else None
    if there is None or there < min_notional:
        return None
    here_txt = "UNREADABLE" if here is None else f"${here:,.2f}"
    return (f"THE CAPITAL IS IN THE {str(other).upper()} WALLET. This run is pointed at "
            f"{wallet}, which holds {here_txt} {quote}, while {other} holds ${there:,.2f}. "
            f"Nothing was placed because there is nothing here to place with -- that is NOT a "
            f"quiet market. Re-run with --wallet {other}.")
