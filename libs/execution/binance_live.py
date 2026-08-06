"""Binance USD-M Futures LIVE connector -- execution hands only, no alpha, no keys in code.

Mirrors libs/execution/binance_testnet.py's interface EXACTLY (drop-in: callers that already
work against the testnet module work against this one unchanged) but is pinned to the LIVE
base URL. Per docs/LIVE_CONNECTOR_SPEC.md section 1 + engineering_backlog.json
``live_connector_prebuild``: this module is FULLY INERT -- every signed call raises -- unless
ALL THREE hold:
  1. ``data/secrets/binance_live.json`` exists with a trade-only, withdrawal-disabled key
     (placed by the PRINCIPAL via SSH -- never chat, never env var, never committed);
  2. ``data/LIVE_ENABLE`` flag file exists (explicit arm switch, separate from key placement so
     "keys exist" and "trading is armed" are never the same moment);
  3. ``data/LIVE_VPS_VERIFIED`` marker exists (VPS-stability precondition -- set only after the
     operator confirms the deployment host is the durable one, not a rebuild-in-progress box).
Unlike the testnet connector, credentials are read from the KEYFILE ONLY -- no environment-
variable path. A systemd unit's environment is visible via ``/proc/<pid>/environ`` to anyone
with host access; live trade-only keys stay in one file with explicit, auditable placement.

CAPABILITY WHITELIST (hard, by construction -- not a runtime check): this module defines ONLY
order-placement, order-cancellation, and read functions. It has no withdrawal, transfer,
sub-account, or key-management function and never will -- those Binance endpoints are simply
never wrapped here. Adding one would need a from-scratch review, not an edit to this file.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import time
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

from libs.execution.idempotency import client_order_id

_BASE = "https://fapi.binance.com"              # PINNED live futures -- verified against docs
_KEYFILE = Path("data/secrets/binance_live.json")
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
    """All three go-live preconditions, evaluated together (see module docstring)."""
    checks = {
        "keys_present": has_keys(),
        "live_enable_flag": _ENABLE_FLAG.exists(),
        "vps_verified": _VPS_MARKER.exists(),
    }
    return all(checks.values()), ", ".join(f"{k}={v}" for k, v in checks.items())


def _get(path: str, params: dict[str, Any] | None = None) -> Any:
    """Public market data -- no keys, no arming required (read-only, harmless)."""
    url = f"{_BASE}{path}"
    if params:
        url += "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": "quant-live/1.0"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read())


def _signed(path: str, params: dict[str, Any], *, method: str = "GET") -> Any:
    armed, why = is_armed()
    if not armed:
        raise RuntimeError(f"binance_live not armed ({why}) -- refusing signed call {path}")
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
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read())


def exchange_filters() -> dict[str, dict[str, float]]:
    """Per-symbol step size, min qty, and price/qty precision (for valid order sizing)."""
    info = _get("/fapi/v1/exchangeInfo")
    out: dict[str, dict[str, float]] = {}
    for s in info.get("symbols", []):
        f = {flt["filterType"]: flt for flt in s.get("filters", [])}
        lot = f.get("LOT_SIZE", {})
        pf = f.get("PRICE_FILTER", {})
        out[s["symbol"]] = {
            "step": float(lot.get("stepSize", 0.001)), "min_qty": float(lot.get("minQty", 0.0)),
            "qty_prec": int(s.get("quantityPrecision", 3)),
            "tick": float(pf.get("tickSize", 0.01)), "price_prec": int(s.get("pricePrecision", 2)),
        }
    return out


def book_ticker() -> dict[str, tuple[float, float]]:
    """Best bid/ask per symbol (for passive maker pricing). {symbol: (bid, ask)}."""
    data = _get("/fapi/v1/ticker/bookTicker")
    if not isinstance(data, list):
        return {}
    return {d["symbol"]: (float(d["bidPrice"]), float(d["askPrice"])) for d in data}


def quote_depth(symbol: str, side: str, pct: float = 0.01) -> float:
    """Resting book liquidity: total QUOTE (USDT) value within ``pct`` of the touch on one side.

    side='BUY' sums the asks a buy would eat; side='SELL' sums the bids. Returns 0.0 on any
    failure or an empty book -- callers must treat 'unknown' as 'thin' and stand aside."""
    try:
        d = _get("/fapi/v1/depth", {"symbol": symbol, "limit": 100})
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
    """Venue-truth average fill price of OUR trades on ``symbol`` since ``start_ms`` (signed).

    None when no fills are visible yet, the read fails, or the connector isn't armed --
    callers fall back to the mark rather than fabricate a price."""
    try:
        trades = _signed("/fapi/v1/userTrades", {"symbol": symbol, "startTime": start_ms,
                                                 "limit": 100})
        fills = [t for t in trades if t.get("side") == side]
        base = sum(float(t["qty"]) for t in fills)
        quote = sum(float(t["quoteQty"]) for t in fills)
        return quote / base if base > 0 and quote > 0 else None
    except Exception:
        return None


def mark_prices() -> dict[str, float]:
    """Latest price per symbol (public endpoint -- no keys needed, used for sizing)."""
    data = _get("/fapi/v1/ticker/price")
    return {d["symbol"]: float(d["price"]) for d in data} if isinstance(data, list) else {}


def account_balance() -> float:
    """USDT wallet balance on the live futures account."""
    for b in _signed("/fapi/v2/balance", {}):
        if b.get("asset") == "USDT":
            return float(b.get("balance", 0.0))
    return 0.0


def account_summary() -> dict[str, float]:
    """Equity, wallet, unrealized PnL, available, and margin used (the live P&L snapshot)."""
    a = _signed("/fapi/v2/account", {})
    return {
        "wallet": float(a.get("totalWalletBalance", 0.0)),
        "equity": float(a.get("totalMarginBalance", 0.0)),
        "unrealized_pnl": float(a.get("totalUnrealizedProfit", 0.0)),
        "available": float(a.get("availableBalance", 0.0)),
        "margin_used": float(a.get("totalInitialMargin", 0.0)),
    }


def _income_rows(since_ms: int, income_type: str = "",
                 fetch: Any = None) -> list[dict[str, Any]]:
    """ALL income rows since ``since_ms`` -- paginated past the venue's 1000-row page cap."""
    get = fetch or (lambda p: _signed("/fapi/v1/income", p))
    params: dict[str, Any] = {"limit": 1000}
    if income_type:
        params["incomeType"] = income_type
    if not since_ms:
        rows = get(params)
        return list(rows) if isinstance(rows, list) else []
    out: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str, str]] = set()
    cursor = since_ms
    for _ in range(50):
        params["startTime"] = cursor
        rows = get(params)
        if not isinstance(rows, list) or not rows:
            break
        for r in rows:
            key = (str(r.get("tranId")), str(r.get("incomeType")),
                   str(r.get("symbol")), str(r.get("time")))
            if key not in seen:
                seen.add(key)
                out.append(r)
        if len(rows) < 1000:
            break
        last = int(rows[-1].get("time", cursor))
        cursor = last + 1 if last <= cursor else last
    return out


def income_summary(since_ms: int = 0, fetch: Any = None) -> dict[str, float]:
    """Realized PnL, funding earned/paid, and commission since ``since_ms`` (default: recent)."""
    # gross_profit/gross_loss = EVERY income event split by sign (winning closes + funding earned vs
    # losing closes + funding paid + fees) -> the true trading-report gross split, not a sign-split
    # of the NETTED realized_pnl (which hides winning trades inside a net-negative total). So these
    # two are NOT a trade-level profit factor: commission rows are always negative and land in
    # gross_loss, so gross_profit/|gross_loss| is a NET-OF-COSTS ratio. That is the intended
    # meaning, and it is written here rather than only in binance_testnet.py because the two
    # modules are drop-in replacements -- a reader who checks only the live one must not have to
    # infer it, and someone "fixing" the apparent asymmetry would silently redefine the number.
    # n_wins/n_losses = count of winning vs losing CLOSED trades (REALIZED_PNL events) -> trade
    # win rate = n_wins / (n_wins + n_losses).
    out = {"realized_pnl": 0.0, "funding": 0.0, "commission": 0.0,
           "gross_profit": 0.0, "gross_loss": 0.0, "n_wins": 0.0, "n_losses": 0.0}
    for r in _income_rows(since_ms, fetch=fetch):
        t, amt = r.get("incomeType"), float(r.get("income", 0.0))
        if t == "REALIZED_PNL":
            out["realized_pnl"] += amt
            if amt > 0:
                out["n_wins"] += 1
            elif amt < 0:
                out["n_losses"] += 1
        elif t == "FUNDING_FEE":
            out["funding"] += amt
        elif t == "COMMISSION":
            out["commission"] += amt
        if amt > 0:
            out["gross_profit"] += amt
        elif amt < 0:
            out["gross_loss"] += amt
    return out


def realized_trades(since_ms: int = 0) -> list[float]:
    """Per-close realized-PnL amounts (for win rate). One row per position-reducing fill."""
    return [float(r.get("income", 0.0)) for r in _income_rows(since_ms, "REALIZED_PNL")]


def positions() -> dict[str, float]:
    """Current signed position quantity per symbol (long +, short -)."""
    out: dict[str, float] = {}
    for p in _signed("/fapi/v2/positionRisk", {}):
        amt = float(p.get("positionAmt", 0.0))
        if amt != 0.0:
            out[p["symbol"]] = amt
    return out


def force_orders(hours: float = 2.0) -> dict[str, int]:
    """Symbols force-closed by the VENUE (liquidation or auto-deleveraging) recently.

    A short perp leg that vanished via ADL/liquidation must NOT be re-shorted into the
    squeeze that took it. Returns symbol -> count of force events; {} without arming or on error.
    """
    if not is_armed()[0]:
        return {}
    since = int((time.time() - hours * 3600.0) * 1000)
    try:
        rows = _signed("/fapi/v1/forceOrders", {"startTime": since, "limit": 100}) or []
    except Exception:
        return {}
    out: dict[str, int] = {}
    for r in rows:
        s = str(r.get("symbol", ""))
        if s:
            out[s] = out.get(s, 0) + 1
    return out


def set_leverage(symbol: str, leverage: int) -> None:
    try:
        _signed("/fapi/v1/leverage", {"symbol": symbol, "leverage": leverage}, method="POST")
    except Exception:  # leverage already set / symbol issue -- non-fatal
        return


_MKT_MAX_CACHE: dict[str, float] = {}


def _market_max_qty(symbol: str) -> float:
    """Venue MARKET_LOT_SIZE cap for ``symbol``, cached. inf when unknown (never invent a limit).

    Added 2026-07-27 after COOKIEUSDT (maxQty 150,000) rejected every 183,140 market order with
    -4005, pushing the executor onto its resting-limit fallback, whose accumulated fills walked a
    short through zero into a +916,772 long.
    """
    if symbol in _MKT_MAX_CACHE:
        return _MKT_MAX_CACHE[symbol]
    cap = float("inf")
    try:
        info = _get("/fapi/v1/exchangeInfo")
        for s in info.get("symbols", []):
            for f in s.get("filters", []):
                if f.get("filterType") == "MARKET_LOT_SIZE":
                    _MKT_MAX_CACHE[s["symbol"]] = float(f["maxQty"])
        cap = _MKT_MAX_CACHE.get(symbol, float("inf"))
    except Exception:
        # A TRANSIENT FAILURE MUST NOT BE CACHED. This wrote inf into the cache on the way out,
        # so ONE network blip during the lookup permanently disabled the cap for that symbol --
        # for the whole process lifetime, and the executor runs for days between restarts. The
        # protection this function exists to provide is the one that stops a -4005 rejection
        # pushing the executor onto its resting-limit fallback, which is how a short once walked
        # through zero into a +916,772 long. Silently losing it to a timeout is the worst
        # available outcome and it left no trace at all.
        #
        # Returning inf for THIS call is still correct -- never invent a limit from a failed
        # lookup -- but the cache is left untouched so the next call retries.
        return float("inf")
    _MKT_MAX_CACHE[symbol] = cap
    return cap


def place_market(symbol: str, side: str, qty: float,
                 reduce_only: bool = False, cycle: str | None = None) -> dict[str, Any]:
    """Place a market order, SPLIT to respect the venue MARKET_LOT_SIZE cap.

    ``reduce_only=True`` makes the order arithmetically incapable of passing through zero and
    opening the opposite position -- mandatory on any cover/close leg.
    """
    cap = _market_max_qty(symbol)
    remaining, last, n = float(qty), None, 0
    # GAP #49: intent distinguishes a close from an open, so a cover and an entry on the same
    # symbol/side never share an ID inside one bucket.
    intent = "close" if reduce_only else "open"
    while remaining > 0 and n < 50:
        chunk = min(cap, remaining) if cap != float("inf") else remaining
        params = {"symbol": symbol, "side": side, "type": "MARKET", "quantity": chunk,
                  # GAP #49: without this, an ambiguous timeout is indistinguishable from a
                  # failure, and the retry places a SECOND leg -- which on a delta-neutral book
                  # is an unhedged directional position. The chunk index is in the ID because
                  # chunks are distinct orders; sharing one ID would have the venue reject
                  # chunks 2..n as duplicates and silently under-fill the leg.
                  "newClientOrderId": client_order_id(symbol, side, intent, chunk=n, cycle=cycle)}
        if reduce_only:
            params["reduceOnly"] = "true"
        last = _signed("/fapi/v1/order", params, method="POST")
        remaining -= chunk
        n += 1
    return dict(last) if isinstance(last, dict) else {"raw": last}


def place_post_only(symbol: str, side: str, qty: float, price: float,
                    cycle: str | None = None) -> dict[str, Any]:
    """Post-only LIMIT order (timeInForce=GTX) -- guaranteed MAKER (rejected if it would cross)."""
    res = _signed("/fapi/v1/order", {
        "symbol": symbol, "side": side, "type": "LIMIT", "timeInForce": "GTX",
        "quantity": qty, "price": price,
        # GAP #49. A resting post-only order is MORE dangerous to duplicate than a market order,
        # not less: incident #6 was accumulated resting fills walking a short through zero.
        "newClientOrderId": client_order_id(symbol, side, "postonly", cycle=cycle),
    }, method="POST")
    return dict(res) if isinstance(res, dict) else {"raw": res}


def place_stop_market(symbol: str, side: str, qty: float, stop_price: float) -> dict[str, Any]:
    """Reduce-only STOP_MARKET -- the venue-side protective stop required by spec section 3
    (survives total host death; every live position must carry one at the ruin-line distance)."""
    res = _signed("/fapi/v1/order", {
        "symbol": symbol, "side": side, "type": "STOP_MARKET", "quantity": qty,
        "stopPrice": stop_price, "reduceOnly": "true",
    }, method="POST")
    return dict(res) if isinstance(res, dict) else {"raw": res}


def open_orders(symbol: str | None = None) -> list[dict[str, Any]]:
    """Resting (unfilled) orders, optionally for one symbol."""
    params = {"symbol": symbol} if symbol else {}
    res = _signed("/fapi/v1/openOrders", params)
    return list(res) if isinstance(res, list) else []


def cancel_all(symbol: str) -> dict[str, Any]:
    """Cancel all open orders for a symbol (clears stale maker quotes before re-pegging)."""
    res = _signed("/fapi/v1/allOpenOrders", {"symbol": symbol}, method="DELETE")
    return dict(res) if isinstance(res, dict) else {"raw": res}


def flatten_all() -> list[dict[str, Any]]:
    """Emergency: market-close every open position. Reduce-only, and isolated per symbol.

    TWO DEFECTS FIXED 2026-08-06, BOTH ON THE PATH THAT RUNS BECAUSE SOMETHING ALREADY WENT WRONG.

    `reduce_only` WAS MISSING. `place_market`'s own docstring three functions up calls it
    "mandatory on any cover/close leg", and this IS the close leg -- the last one, the one the
    guard fires at a flatten rung. The size comes from a `positions()` read, and between that read
    and the fill the position can shrink: a resting maker quote fills, a venue-side STOP_MARKET
    triggers, an earlier chunk of this same flatten lands. Then SELL(100) against a position that
    is now +40 does not close it, it SELLS THROUGH ZERO INTO A 60-LOT SHORT. That is incident #6's
    exact mechanism (+916,772 long), reproduced on the emergency path, at the one moment the book
    is most likely to be moving underneath the read. `reduceOnly` makes it arithmetically
    impossible: the venue clamps the fill at flat.

    It also fixes the client order ID, which is not a separate bug so much as the same one seen
    from the idempotency side. `place_market` derives `intent = "close" if reduce_only else
    "open"`, so every emergency close was being tagged an OPEN -- and libs/execution/idempotency.py
    exists precisely so "a cover and an entry on the same symbol/side never share an ID inside one
    bucket". A genuine entry on the same symbol and side inside the same 90s bucket would collide
    with the flatten leg, and the venue would reject THE FLATTEN as a duplicate. Fail-safe is a
    missed entry; this was the collision resolving the other way.

    ONE RAISING LEG ABANDONED EVERY REMAINING POSITION. The loop had no isolation and the only
    caller (scripts/run_live_guard.py) wraps the whole call in one try/except, so a single symbol
    erroring left the rest of the book open while the report read "flatten FAILED". Emergency
    semantics are per-symbol: try everything, close what closes, report what did not. This matters
    MORE now, not less -- reduce-only orders are rejected (-2022) when the position is already
    flat, which is a routine race here rather than an error, and without isolation that benign
    rejection would strand every position after it.

    Failures are returned as rows carrying ``error`` so the count of genuinely-closed positions
    stays honest; nothing is swallowed.
    """
    out: list[dict[str, Any]] = []
    for sym, amt in positions().items():
        side = "SELL" if amt > 0 else "BUY"
        try:
            out.append(place_market(sym, side, abs(amt), reduce_only=True))
        except Exception as exc:
            out.append({"symbol": sym, "side": side, "qty": abs(amt), "error": repr(exc)})
    return out
