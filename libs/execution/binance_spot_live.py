"""Binance SPOT LIVE connector -- the spot leg of cash-and-carry, real money, no alpha here.

Mirrors libs/execution/binance_spot_testnet.py's interface EXACTLY; pinned to the LIVE spot
base URL. Same arming contract as libs/execution/binance_live.py (the futures leg) -- see that
module's docstring for the full rationale. Every signed call is inert unless
``data/secrets/binance_live_spot.json`` exists, ``data/LIVE_ENABLE`` exists, and
``data/LIVE_VPS_VERIFIED`` exists. Keyfile-only credentials (no env var path -- see futures
module docstring for why). No withdrawal/transfer/sub-account function exists in this module and
never will; the capability surface is order-placement, order-cancellation, and reads only.
"""

from __future__ import annotations

import hashlib
import hmac
import http.client
import json
import socket
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

from libs.execution.idempotency import client_order_id

_BASE = "https://api.binance.com"                # PINNED live spot -- verified against docs

#: EVERY CALL LEAVES OVER IPv4, BECAUSE THE VENUE'S WHITELIST IS AN IPv4 LIST.
#:
#: Measured 2026-08-15 on the live box. It holds two addresses -- 95.216.191.70 and
#: 2a01:4f9:c010:9451::1 -- and Python's default resolver preferred the IPv6 one. So the key was
#: whitelisted for the v4 address, every request arrived from the v6 address, and Binance returned
#: `-2015 Invalid API-key, IP, or permissions for action` on a key whose key, secret and
#: permissions were all correct. The message names three causes and the true one is a FOURTH that
#: it does not mention, which is why this constant is here rather than in an operator's memory.
#:
#: The alternative fixes were rejected: /etc/gai.conf needs root the box does not have, and adding
#: the v6 address to the venue whitelist leaves the desk one dual-stack host away from the same
#: silent failure. Pinning the egress family makes the address the venue sees a PROPERTY OF THIS
#: MODULE rather than of the host's resolver ordering.
FORCE_IPV4 = True
_KEYFILE = Path("data/secrets/binance_live_spot.json")
_ENABLE_FLAG = Path("data/LIVE_ENABLE")
_VPS_MARKER = Path("data/LIVE_VPS_VERIFIED")


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
    checks = {
        "keys_present": has_keys(),
        "live_enable_flag": _ENABLE_FLAG.exists(),
        "vps_verified": _VPS_MARKER.exists(),
    }
    return all(checks.values()), ", ".join(f"{k}={v}" for k, v in checks.items())


class _IPv4HTTPSConnection(http.client.HTTPSConnection):
    """HTTPS pinned to A records. `socket.create_connection` walks whatever `getaddrinfo` returns
    in whatever order the host prefers, so on a dual-stack box the egress address -- the one the
    venue matches against its whitelist -- is decided by system configuration nobody here reads."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        # HELD EXPLICITLY. `HTTPSConnection._context` exists at runtime but is absent from the
        # typeshed stubs, and reaching for a private attribute the checker cannot see is how a
        # TLS context silently becomes None on a version bump -- on the module that places orders.
        self._tls: ssl.SSLContext = kwargs.get("context") or ssl.create_default_context()

    def connect(self) -> None:
        last: OSError | None = None
        for af, kind, proto, _canon, addr in socket.getaddrinfo(
                self.host, self.port, socket.AF_INET, socket.SOCK_STREAM):
            sock = socket.socket(af, kind, proto)
            try:
                if isinstance(self.timeout, int | float):
                    sock.settimeout(self.timeout)
                sock.connect(addr)
            except OSError as exc:
                sock.close()
                last = exc
                continue
            self.sock = self._tls.wrap_socket(sock, server_hostname=self.host)
            return
        raise last or OSError(f"no IPv4 address for {self.host}")


class _IPv4HTTPSHandler(urllib.request.HTTPSHandler):
    def https_open(self, req: urllib.request.Request) -> Any:
        return self.do_open(_IPv4HTTPSConnection, req,
                            context=getattr(self, "_context", None))


#: Socket bound on every venue call. An unbounded read on the order path does not fail, it HANGS,
#: and a hung order is the one state the desk cannot reconcile -- it does not know whether the leg
#: exists. Passed EXPLICITLY at the call site rather than defaulted, so the bound is visible where
#: the request is made and cannot be lost by a wrapper that forgets to forward it.
_TIMEOUT_S = 20


def _urlopen(req: urllib.request.Request, *, timeout: int = _TIMEOUT_S) -> Any:
    if not FORCE_IPV4:
        return urllib.request.urlopen(req, timeout=timeout)
    return urllib.request.build_opener(_IPv4HTTPSHandler()).open(req, timeout=timeout)


def _open(req: urllib.request.Request) -> Any:
    """urlopen, but a rejection carries the VENUE'S OWN REASON.

    `HTTPError.__str__` is "HTTP Error 401: Unauthorized" and the body is discarded unless
    something reads it. Binance puts the only actionable part there: -2015 "Invalid API-key, IP, or
    permissions for action" is a whitelist or permission problem on a key that is otherwise
    correct, -2014 is a malformed key, -1021 is a clock skew, -1022 a bad signature. Those need
    four different fixes and the bare status code distinguishes none of them, so an operator
    reading the refusal cannot tell "wrong key" from "right key, wrong IP" -- which is exactly the
    wall a first live arming hits.

    The body is quoted, never the credential: the request's headers are not touched here.
    """
    try:
        with _urlopen(req, timeout=_TIMEOUT_S) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as exc:
        try:
            detail = exc.read().decode("utf-8", "replace")[:300]
        except Exception:                                  # body already consumed or stream dead
            detail = "(no body)"
        raise RuntimeError(f"venue rejected the call: HTTP {exc.code} {detail}") from exc


def _get(path: str, params: dict[str, Any] | None = None) -> Any:
    url = f"{_BASE}{path}"
    if params:
        url += "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": "quant-live-spot/1.0"})
    return _open(req)


def _signed(path: str, params: dict[str, Any], *, method: str = "GET") -> Any:
    armed, why = is_armed()
    if not armed:
        raise RuntimeError(f"binance_spot_live not armed ({why}) -- refusing signed call {path}")
    key, secret = _creds()
    assert key is not None and secret is not None  # armed (checked above) => creds present
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
    return _open(req)


def prices() -> dict[str, float]:
    """Latest spot price per symbol (public)."""
    data = _get("/api/v3/ticker/price")
    return {d["symbol"]: float(d["price"]) for d in data} if isinstance(data, list) else {}


def _prec_of(step: float) -> int:
    s = f"{step:.10f}".rstrip("0")
    return len(s.split(".")[1]) if "." in s and step < 1 else 0


def exchange_filters() -> dict[str, dict[str, float]]:
    """Per-symbol step, min qty, base precision, price tick + precision (for valid spot sizing).

    ``min_notional`` is the venue's minimum ORDER VALUE -- a gate quantity filters cannot express:
    an order can satisfy stepSize AND minQty and still be rejected for being worth too little.
    Binance publishes it as NOTIONAL (current) or MIN_NOTIONAL (legacy); 0.0 means this symbol
    has no published minimum, so callers must keep their own conservative floor for that case.

    PARITY WARNING (2026-07-31): this is one of FOUR near-duplicate exchangeInfo parsers --
    binance_spot_live, binance_spot_testnet, binance_live, binance_testnet. The money path
    (run_cashcarry_executor, run_stranded_recovery) imports the TESTNET modules, so a field added
    only here reaches NOTHING. tests/execution/test_filter_parity.py pins the spot pair's key set
    so that divergence fails a test instead of shipping inert. Futures publishes the same filter
    under the key ``notional``, NOT ``minNotional`` -- copying this line there yields 0.0 for
    every symbol."""
    info = _get("/api/v3/exchangeInfo")
    out: dict[str, dict[str, float]] = {}
    for s in info.get("symbols", []):
        f = {flt["filterType"]: flt for flt in s.get("filters", [])}
        lot = f.get("LOT_SIZE", {})
        tick = float(f.get("PRICE_FILTER", {}).get("tickSize", 0.0) or 0.0)
        notl = f.get("NOTIONAL", {}) or f.get("MIN_NOTIONAL", {})
        out[s["symbol"]] = {
            "step": float(lot.get("stepSize", 0.0001)), "min_qty": float(lot.get("minQty", 0.0)),
            "qty_prec": int(s.get("baseAssetPrecision", 6)),
            "tick": tick, "price_prec": _prec_of(tick) if tick else 8,
            "min_notional": float(notl.get("minNotional", 0.0) or 0.0),
        }
    return out


def book_ticker() -> dict[str, tuple[float, float]]:
    """Best (bid, ask) per symbol (public) -- for passive maker quoting."""
    data = _get("/api/v3/ticker/bookTicker")
    return {d["symbol"]: (float(d["bidPrice"]), float(d["askPrice"]))
            for d in data} if isinstance(data, list) else {}


def quote_depth(symbol: str, side: str, pct: float = 0.01) -> float:
    """Resting book liquidity: total QUOTE (USDT) value within ``pct`` of the touch on one side."""
    try:
        d = _get("/api/v3/depth", {"symbol": symbol, "limit": 100})
        levels = d.get("asks" if side == "BUY" else "bids", [])
        if not levels:
            return 0.0
        touch = float(levels[0][0])
        if side == "BUY":
            return sum(float(p) * float(q) for p, q in levels if float(p) <= touch * (1.0 + pct))
        return sum(float(p) * float(q) for p, q in levels if float(p) >= touch * (1.0 - pct))
    except Exception:
        return 0.0


def avg_fill(symbol: str, side: str, start_ms: int) -> float | None:
    """Venue-truth average fill price of OUR trades since ``start_ms``. None if unarmed/no fills."""
    try:
        trades = _signed("/api/v3/myTrades", {"symbol": symbol, "startTime": start_ms,
                                              "limit": 100})
        fills = [t for t in trades if bool(t.get("isBuyer")) == (side == "BUY")]
        base = sum(float(t["qty"]) for t in fills)
        quote = sum(float(t["quoteQty"]) for t in fills)
        return quote / base if base > 0 and quote > 0 else None
    except Exception:
        return None


def balances() -> dict[str, float]:
    """Free balance per asset (non-zero only)."""
    a = _signed("/api/v3/account", {})
    return {b["asset"]: float(b["free"]) for b in a.get("balances", []) if float(b["free"]) > 0.0}


def usdt_balance() -> float:
    return balances().get("USDT", 0.0)


def account_value_usdt() -> float:
    """Approximate total account value in USDT (free balances marked at spot price)."""
    px = prices()
    total = 0.0
    for asset, qty in balances().items():
        if asset == "USDT":
            total += qty
        else:
            total += qty * px.get(f"{asset}USDT", 0.0)
    return round(total, 2)


def place_market(symbol: str, side: str, qty: float,
                 cycle: str | None = None) -> dict[str, Any]:
    """Spot MARKET order. side in {BUY, SELL}; qty in base asset units (e.g. BTC).

    GAP #49 EXTENDED TO SPOT, 2026-08-06 -- IT WAS ONLY EVER APPLIED TO HALF THE TRADE. Every
    futures order has carried a deterministic `newClientOrderId` since GAP #49; no spot order
    carried one at all. The desk's primary live strategy is a cash-and-carry pair, and
    scripts/run_cashcarry_executor.py placed it like this:

        _cycle = _pair_cycle(sym, spot_side, qty)
        spot_res = spot.place_market(sym, spot_side, qty)                  # no ID
        fut_res  = fut.place_market(sym, fut_side, qty, ..., cycle=_cycle) # ID

    -- with a comment above it stating that "a duplicated leg on a delta-neutral book is an
    unhedged directional position". On an ambiguous timeout the retry is then deduped by the venue
    on the futures leg and PLACED AGAIN on the spot leg: two spot longs against one perp short.
    Not a slightly-oversized carry -- a naked long, arrived at by the exact mechanism the
    protection was written to prevent, on the leg it was never wired into.

    THE TRADEOFF IS THE SAME ONE FUTURES ALREADY TOOK, and is worth restating because it is a real
    cost. Two genuinely distinct spot orders sharing symbol+side+intent inside one 90s bucket now
    collide, and the venue rejects the second: a missed order, visible and retryable. The
    alternative is a silent duplicated leg. libs/execution/idempotency.py argues that asymmetry at
    length; the answer does not change because the venue is spot.

    Pass `cycle` on any paired execution -- the wall-clock bucket is a fallback with an
    unobservable boundary, and a retry that lands the wrong side of it is placed as a new order.
    """
    res = _signed("/api/v3/order", {
        "symbol": symbol, "side": side, "type": "MARKET", "quantity": qty,
        "newClientOrderId": client_order_id(symbol, side, "spot", cycle=cycle),
    }, method="POST")
    return dict(res) if isinstance(res, dict) else {"raw": res}


def place_market_quote(symbol: str, side: str, quote_usdt: float,
                       cycle: str | None = None) -> dict[str, Any]:
    """Spot MARKET order sized in QUOTE (USDT) -- convenient for buying $X of an asset.

    Distinct intent from `place_market` so a base-sized and a quote-sized order for the same
    symbol and side inside one cycle are different logical orders, not a collision.
    """
    res = _signed("/api/v3/order", {
        "symbol": symbol, "side": side, "type": "MARKET", "quoteOrderQty": quote_usdt,
        "newClientOrderId": client_order_id(symbol, side, "spotquote", cycle=cycle),
    }, method="POST")
    return dict(res) if isinstance(res, dict) else {"raw": res}


def place_post_only(symbol: str, side: str, qty: float, price: float,
                    cycle: str | None = None) -> dict[str, Any]:
    """Post-only spot LIMIT order (type=LIMIT_MAKER) -- guaranteed MAKER.

    A RESTING order is more dangerous to duplicate than a market order, not less: incident #6 was
    accumulated resting fills. Separate intent again -- a maker quote and a taker sweep on the same
    symbol inside one cycle are deliberately different orders.
    """
    res = _signed("/api/v3/order", {
        "symbol": symbol, "side": side, "type": "LIMIT_MAKER", "quantity": qty, "price": price,
        "newClientOrderId": client_order_id(symbol, side, "spotmaker", cycle=cycle),
    }, method="POST")
    return dict(res) if isinstance(res, dict) else {"raw": res}


def open_orders(symbol: str | None = None) -> list[dict[str, Any]]:
    """Resting open orders (signed). Used to detect whether a maker quote has filled."""
    res = _signed("/api/v3/openOrders", {"symbol": symbol} if symbol else {})
    return list(res) if isinstance(res, list) else []


def cancel_all(symbol: str) -> dict[str, Any]:
    """Cancel all open orders on a symbol (signed) -- to pull an unfilled maker quote."""
    try:
        res = _signed("/api/v3/openOrders", {"symbol": symbol}, method="DELETE")
        return {"code": 200, "res": res}
    except Exception as e:  # nothing to cancel / transient -- non-fatal
        return {"code": 0, "msg": repr(e)[:80]}
