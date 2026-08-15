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

__all__ = ["WALLETS", "connector", "is_margin"]

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
