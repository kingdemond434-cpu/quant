"""Binance CROSS MARGIN LIVE -- the first path on this desk that can be liquidated.

WHY THIS IS A SEPARATE MODULE AND NOT A FLAG ON THE SPOT ONE. Spot is 1x by construction: you hold
what you paid for, the worst case is the asset going to zero, and no third party can close your
position. Margin borrows. That single difference brings in a liability, an interest accrual, a
margin level, a margin call and a LIQUIDATION PRICE at which the venue closes the book for you, at
its convenience, in whatever liquidity exists at that moment. Every safety property the spot module
gets for free has to be re-established here explicitly, so mixing them into one file would let a
spot caller inherit a liquidation path by editing one argument.

**THE ARMING CONTRACT IS STRICTER, BY ONE FILE.** Spot needs keyfile + LIVE_ENABLE +
LIVE_VPS_VERIFIED. This needs all three PLUS ``data/MARGIN_ENABLE``, because "may this box trade"
and "may this box borrow" are different authorisations and the second is the one that can end the
account. The principal writes it; no organ ever does.

**NO TRANSFER SURFACE, DELIBERATELY.** Binance exposes ``/sapi/v1/margin/transfer`` and this module
does not use it and never will. Moving capital between the spot and margin wallets is the act that
decides how much can be lost, and it stays a principal act performed in the app. The practical
consequence is stated rather than hidden: this module can only trade what is ALREADY in the margin
wallet, and it will report a zero balance rather than fund itself. No withdrawal or sub-account
function exists here either.

**BORROWING HAPPENS THROUGH sideEffectType, NOT THROUGH A LOAN CALL.** ``MARGIN_BUY`` asks the venue
to borrow exactly what the order needs and no more; an explicit ``/loan`` followed by an order is
two operations that can succeed apart, leaving a borrowed balance with no position against it --
the worst of both, paying interest on idle debt. ``AUTO_REPAY`` on the closing side does the mirror.

**THE MARGIN LEVEL IS CHECKED BEFORE EVERY BORROW, NOT AFTER.** Binance calls at 1.5 and liquidates
at 1.1. `_MIN_LEVEL_TO_BORROW` sits well above both, because the level moves with the market and a
check performed at 1.15 is a check performed too late. Reads and repayments are never blocked by
it: refusing to let a book de-risk itself is how a margin call becomes a liquidation.

**LEVERAGE IS CAPPED IN CODE AND THE CAP IS NOT A SUGGESTION.** `MAX_LEVERAGE` bounds what any
caller may request. A number that lives only in a caller's argument is a number one bad cron line
away from 10x.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

from libs.execution.binance_spot_live import _open as _shared_open
from libs.execution.idempotency import client_order_id

_BASE = "https://api.binance.com"                  # PINNED live -- margin shares the spot host
_KEYFILE = Path("data/secrets/binance_live_spot.json")
_ENABLE_FLAG = Path("data/LIVE_ENABLE")
_VPS_MARKER = Path("data/LIVE_VPS_VERIFIED")

#: THE EXTRA AUTHORISATION. "May this box trade" and "may this box borrow" are different questions
#: and only the second one can end the account. Principal-written, never by an organ.
_MARGIN_FLAG = Path("data/MARGIN_ENABLE")

#: Venue thresholds, stated so the distance from them is visible at every call site rather than
#: living in a support article. Binance issues a margin call at 1.5 and liquidates at 1.1.
MARGIN_CALL_LEVEL = 1.5
LIQUIDATION_LEVEL = 1.1

#: THE FLOOR IS ON THE PROJECTED LEVEL, NOT AN ABSOLUTE ONE, and the difference is not a detail.
#: An absolute floor of 2.0 would have made 3x unreachable: entering at leverage L puts the account
#: at level L/(L-1) BY DEFINITION, so 3x arrives at exactly 1.50 -- the venue's own margin-call
#: line -- and 2x arrives at 2.00. A constant floor above those is a constant that forbids the
#: leverage it was written to govern, which is worse than no check: it reads as a safety property
#: and functions as an outage.
#:
#: 1.12 sits just above the 1.10 liquidation line. That is deliberately TIGHT, and it is tight
#: because the principal set the ceiling at 8x; a floor loose enough to be comfortable would
#: silently refuse the configuration that was asked for. The protection at high leverage is
#: therefore NOT this number -- it is the de-risk path and the size of the move, both published.
MIN_PROJECTED_LEVEL = 1.12

#: Hard ceiling on requested leverage, enforced here rather than trusted from the caller.
#: Set to 8.0 at the principal's explicit instruction, 2026-08-15, over a stated objection recorded
#: in `liquidation_distance` below. The venue may permit more; that is its risk appetite.
MAX_LEVERAGE = 8.0

#: What a caller gets when it does not choose. The principal's stated minimum.
DEFAULT_LEVERAGE = 3.0


def liquidation_distance(leverage: float) -> float:
    """The adverse move, as a fraction, that takes a fresh position at `leverage` to liquidation.

    ARITHMETIC, NOT OPINION. Borrowing B against equity E gives assets E+B and liabilities B, so
    the margin level is (E+B)/B. Entering at leverage L means B = E(L-1), so the level at entry is
    L/(L-1) and a price fall of d takes it to (E+B)(1-d)/B. Setting that equal to the liquidation
    level and solving:

        d = 1 - LIQUIDATION_LEVEL * (L-1) / L

        3x -> -26.7%      6x -> -8.3%      8x -> -3.75%

    THE NUMBER THAT MATTERS AT 8x IS 3.75%. The assets in this book move that much on an ordinary
    day, so at that leverage liquidation is not a tail event, it is the base case, and it fires
    against the WHOLE position rather than the borrowed part. The spot book's own backtest carries
    a 79.6% max drawdown; at 8x the account does not survive to experience it.

    Published as a function rather than a comment so every report can print it and nobody has to
    remember it.
    """
    if leverage <= 1.0:
        return 1.0
    return 1.0 - LIQUIDATION_LEVEL * (leverage - 1.0) / leverage

__all__ = [
    "DEFAULT_LEVERAGE",
    "LIQUIDATION_LEVEL",
    "MARGIN_CALL_LEVEL",
    "MAX_LEVERAGE",
    "MIN_PROJECTED_LEVEL",
    "account",
    "balances",
    "borrow_headroom",
    "cancel_all",
    "has_keys",
    "is_armed",
    "liabilities",
    "liquidation_distance",
    "margin_level",
    "open_orders",
    "place_market_quote",
    "place_market_reduce",
]


def _creds() -> tuple[str | None, str | None]:
    if not _KEYFILE.exists():
        return None, None
    try:
        d = json.loads(_KEYFILE.read_text("utf-8"))
        return d.get("key"), d.get("secret")
    except (json.JSONDecodeError, OSError):
        return None, None


def has_keys() -> bool:
    k, s = _creds()
    return bool(k and s)


def is_armed() -> tuple[bool, str]:
    """All four. The margin flag is listed last so its absence reads as the deliberate gate it is,
    rather than as a missing credential."""
    checks = {
        "keys_present": has_keys(),
        "live_enable_flag": _ENABLE_FLAG.exists(),
        "vps_verified": _VPS_MARKER.exists(),
        "margin_enable_flag": _MARGIN_FLAG.exists(),
    }
    return all(checks.values()), ", ".join(f"{k}={v}" for k, v in checks.items())


def _signed(path: str, params: dict[str, Any], *, method: str = "GET") -> Any:
    armed, why = is_armed()
    if not armed:
        raise RuntimeError(f"binance_margin_live not armed ({why}) -- refusing signed call {path}")
    key, secret = _creds()
    assert key is not None and secret is not None
    params = {**params, "timestamp": int(time.time() * 1000), "recvWindow": 5000}
    query = urllib.parse.urlencode(params)
    sig = hmac.new(secret.encode(), query.encode(), hashlib.sha256).hexdigest()
    body = f"{query}&signature={sig}".encode()
    if method == "GET":
        req = urllib.request.Request(f"{_BASE}{path}?{body.decode()}",
                                     headers={"X-MBX-APIKEY": key})
    else:
        req = urllib.request.Request(f"{_BASE}{path}", data=body, method=method,
                                     headers={"X-MBX-APIKEY": key})
    # Shares the spot module's opener: same IPv4 egress pin (the venue whitelist is matched against
    # the address we leave from) and the same error unwrapping that keeps the venue's own code.
    return _shared_open(req)


def account() -> dict[str, Any]:
    """Raw cross-margin account. `marginLevel`, `totalAssetOfBtc`, `totalLiabilityOfBtc`,
    `totalNetAssetOfBtc` and the per-asset rows including `borrowed` and `interest`."""
    return dict(_signed("/sapi/v1/margin/account", {}))


def margin_level() -> float | None:
    """Total assets / total liabilities. None when the venue does not report it -- NEVER a
    default: a missing level rendered as a large number would wave every borrow through, and
    rendered as a small one would block a book from repaying. Callers must handle None explicitly.
    """
    try:
        raw = account().get("marginLevel")
        lvl = float(raw) if raw is not None else 0.0
    except (KeyError, TypeError, ValueError, RuntimeError, urllib.error.URLError, OSError):
        return None
    # Binance reports 999 when nothing is borrowed. That is not a measurement of anything, but it
    # is unambiguous and safe in the only direction that matters here.
    return lvl if lvl > 0 else None


def balances() -> dict[str, float]:
    """FREE balance per asset in the margin wallet. Free, not net: borrowed funds sitting unspent
    are spendable, and netting them away would understate what an order can use."""
    out: dict[str, float] = {}
    for a in account().get("userAssets", []) or []:
        free = float(a.get("free") or 0.0)
        if free > 0:
            out[str(a.get("asset"))] = free
    return out


def liabilities() -> dict[str, float]:
    """Borrowed + accrued interest per asset. INTEREST IS INCLUDED because it is a real debt that
    grows hourly, and a book that repays only principal never actually closes."""
    out: dict[str, float] = {}
    for a in account().get("userAssets", []) or []:
        owed = float(a.get("borrowed") or 0.0) + float(a.get("interest") or 0.0)
        if owed > 0:
            out[str(a.get("asset"))] = owed
    return out


def borrow_headroom(equity_usd: float, leverage: float) -> tuple[float, str]:
    """How much MAY be borrowed at this leverage, and why -- bounded by `MAX_LEVERAGE`.

    Returns (usd, why). The cap is applied here rather than trusted from the caller, so a bad
    argument becomes a smaller number with a stated reason instead of a larger position.
    """
    if leverage <= 1.0:
        return 0.0, f"leverage {leverage:.2f}x is not leverage -- nothing to borrow"
    lev = min(float(leverage), MAX_LEVERAGE)
    capped = ""
    if lev < leverage:
        capped = (f" (requested {leverage:.2f}x, CAPPED at the module ceiling {MAX_LEVERAGE:.2f}x "
                  "-- the venue may permit more; that is its risk appetite, not this desk's)")
    # THE DISTANCE TRAVELS WITH THE SIZE. A headroom figure quoted without it is the half of the
    # trade that looks like opportunity, and the reader supplies the other half from optimism.
    d = liquidation_distance(lev)
    return equity_usd * (lev - 1.0), (
        f"{lev:.2f}x on ${equity_usd:,.2f} equity{capped}; entry margin level "
        f"{lev / (lev - 1.0):.2f}, LIQUIDATED BY A {d:.1%} ADVERSE MOVE")


def _check_borrow_allowed() -> None:
    """Raises unless a NEW borrow is safe right now. Called only on the borrowing side."""
    lvl = margin_level()
    if lvl is None:
        raise RuntimeError(
            "margin level UNREADABLE -- refusing to borrow. An unknown distance to the "
            f"liquidation line at {LIQUIDATION_LEVEL} is not the same as a safe one, and the only "
            "safe reading of 'unmeasured' on this path is no")
    if lvl < MIN_PROJECTED_LEVEL:
        raise RuntimeError(
            f"margin level {lvl:.3f} is below the floor {MIN_PROJECTED_LEVEL:.3f} "
            f"(venue calls at {MARGIN_CALL_LEVEL}, liquidates at {LIQUIDATION_LEVEL}) -- refusing "
            "to add leverage to a book already inside the liquidation band. Selling and repaying "
            "remain available and are the only things that raise this number")


def place_market_quote(symbol: str, side: str, quote_amount: float, *,
                       cycle: str, borrow: bool = False) -> dict[str, Any]:
    """Market order sized in the QUOTE asset.

    ``borrow=False`` (the default) sends ``NO_SIDE_EFFECT``: the order spends only funds already in
    the margin wallet and adds no liability. Defaulting the other way would mean a caller who
    forgot the argument borrowed money, which is not a mistake this module will make available.

    ``borrow=True`` sends ``MARGIN_BUY`` -- the venue borrows exactly what this order needs and no
    more. That is deliberately not the same as taking a loan and then trading: two operations can
    succeed separately and leave borrowed funds with no position against them, paying interest on
    idle debt.
    """
    if side not in {"BUY", "SELL"}:
        raise ValueError(f"side must be BUY or SELL, got {side!r}")
    if borrow:
        _check_borrow_allowed()
    return dict(_signed("/sapi/v1/margin/order", {
        "symbol": symbol, "side": side, "type": "MARKET",
        "quoteOrderQty": f"{quote_amount:.2f}",
        "sideEffectType": "MARGIN_BUY" if borrow else "NO_SIDE_EFFECT",
        "isIsolated": "FALSE",
        "newClientOrderId": client_order_id(symbol, side, "margin_open", cycle=cycle),
    }, method="POST"))


def place_market_reduce(symbol: str, side: str, qty: float, *, cycle: str) -> dict[str, Any]:
    """Closing order sized in the BASE asset, repaying debt from the proceeds (``AUTO_REPAY``).

    NEVER GATED ON THE MARGIN LEVEL. This is the operation that RAISES the level, and a rail that
    blocked it would trap a book above the liquidation line with no way down -- turning a margin
    call into a liquidation while every check reported working as designed.
    """
    if side not in {"BUY", "SELL"}:
        raise ValueError(f"side must be BUY or SELL, got {side!r}")
    return dict(_signed("/sapi/v1/margin/order", {
        "symbol": symbol, "side": side, "type": "MARKET", "quantity": f"{qty}",
        "sideEffectType": "AUTO_REPAY", "isIsolated": "FALSE",
        "newClientOrderId": client_order_id(symbol, side, "margin_close", cycle=cycle),
    }, method="POST"))


def open_orders(symbol: str | None = None) -> list[dict[str, Any]]:
    p: dict[str, Any] = {"isIsolated": "FALSE"}
    if symbol:
        p["symbol"] = symbol
    res = _signed("/sapi/v1/margin/openOrders", p)
    return list(res) if isinstance(res, list) else []


def cancel_all(symbol: str) -> dict[str, Any]:
    return dict(_signed("/sapi/v1/margin/openOrders",
                        {"symbol": symbol, "isIsolated": "FALSE"}, method="DELETE"))
