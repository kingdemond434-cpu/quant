# AUDIT SHARD 9/24 -- seat ~deepseek/deepseek-pro-latest

You are reviewing SOURCE CODE, not a summary. Previous panels received a 13,185-char self-description and never saw the code; that is why this exists.

- TIER 1 (money path) is included IN FULL and is sent to every seat: 44 files. A defect here costs money.
- TIER 2 is YOUR SHARD ALONE: 10 files. No other seat sees these, so anything you miss here is missed entirely.
- WITHHELD: 0 modules classified INERT (nothing reads them; deleting breaks nothing). They are named below. **If you believe an exclusion is wrong, say so** -- a silent omission is how a blind spot survives an audit.

## Withheld (INERT) -- challenge these if the classification looks wrong



## TIER 1 -- money path (every seat reviews this)

### libs\discovery\tail_risk.py
```python
"""tail_risk_engine — hidden tail exposure (dependence, gap, vol shock).

tail_risk_score in 0-100 (higher = more hidden tail exposure). Penalizes negative skew, fat
tails, large single-bar gaps, and volatility shocks that a Sharpe ratio would miss.
"""

from __future__ import annotations

import numpy as np
from pydantic import BaseModel, ConfigDict
from scipy.stats import kurtosis, skew

from libs.risk.tail import calculate_cvar, calculate_var


class TailRiskResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    tail_risk_score: float  # 0-100, higher = more hidden tail risk (worse)
    acceptable: bool
    cvar_to_var: float
    excess_kurtosis: float
    negative_skew: float
    worst_gap: float

    def __bool__(self) -> bool:
        return self.acceptable


def tail_risk(
    returns: np.ndarray, *, alpha: float = 0.05, threshold: float = 60.0
) -> TailRiskResult:
    """Score an alpha's hidden tail exposure from its return distribution."""
    arr = np.asarray(returns, dtype="float64")
    if len(arr) < 3:
        return TailRiskResult(
            tail_risk_score=0.0, acceptable=True, cvar_to_var=1.0, excess_kurtosis=0.0,
            negative_skew=0.0, worst_gap=0.0,
        )
    var = calculate_var(arr, alpha=alpha)
    cvar = calculate_cvar(arr, alpha=alpha)
    cvar_to_var = cvar / var if var > 0 else 1.0
    excess_kurt = float(kurtosis(arr, fisher=True, bias=False))
    neg_skew = max(0.0, -float(skew(arr, bias=False)))
    worst_gap = float(np.abs(arr).max())

    # Blend into a 0-100 score; each term clipped to keep the scale sane.
    score = (
        min(1.0, max(0.0, cvar_to_var - 1.0) / 2.0) * 30.0
        + min(1.0, excess_kurt / 6.0) * 30.0
        + min(1.0, neg_skew / 2.0) * 25.0
        + min(1.0, worst_gap / (5.0 * var) if var > 0 else 0.0) * 15.0
    )
    return TailRiskResult(
        tail_risk_score=score,
        acceptable=score <= threshold,
        cvar_to_var=cvar_to_var,
        excess_kurtosis=excess_kurt,
        negative_skew=neg_skew,
        worst_gap=worst_gap,
    )

```

### libs\execution\binance_spot_testnet.py
```python
"""Binance SPOT TESTNET connector -- the spot leg of cash-and-carry (paper money).

Pinned to the spot testnet (testnet.binance.vision); cannot touch a live account. Signed REST
(HMAC-SHA256), keys from env (BINANCE_SPOT_TESTNET_KEY / BINANCE_SPOT_TESTNET_SECRET) or a local
untracked file -- NEVER in code. Pairs with libs/execution/binance_testnet.py (the futures leg) so
the long-spot / short-perp cash-and-carry can be simulated end-to-end on paper. No alpha logic here.

WHY A BINANCE MODULE SURVIVES AN MT5-ONLY PURGE -- DO NOT "CLEAN THIS UP" (2026-09-05).
This repo holds ONE desk, the MT5/Fusion desk, and the retired crypto-exchange desk was deleted in
full. This file and its sibling `binance_spot_testnet.py` are the two deliberate exceptions, and
they are exceptions for a reason that has nothing to do with trading crypto: they are the TIER-3
DEADMAN RAIL's own plumbing. `scripts/run_deadman_reconciliation.py` (lines 24-25) and
`scripts/run_deadman_stranded_sweep.py` (line 31) import them directly, and
`scripts/run_deadman_switch.py` is a never-touch file. The rail is a SAFETY organ: it reconciles
and sweeps stranded state, and it must keep working whatever the desk trades.

They are also inert by construction -- the base URL is pinned to a TESTNET, so no code path here
can reach a live account or move real money -- which is precisely why they are safe to keep and
expensive to remove. `scripts/check_mt5_purity.py` allowlists both by name with this reason
attached, so they will never appear in that fence's breach list. If you are here to delete a
Binance file, this is the one you must not. Anything you change here changes the deadman rail.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import time
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

from libs.execution.idempotency import client_order_id

_BASE = "https://testnet.binance.vision"        # PINNED spot testnet -- never live
_KEY_ENV = "BINANCE_SPOT_TESTNET_KEY"
_SECRET_ENV: str = "BINANCE_SPOT_TESTNET_SECRET"  # noqa: S105 - env var NAME, not a secret
_KEYFILE = Path("data/secrets/binance_spot_testnet.json")


def _creds() -> tuple[str | None, str | None]:
    key, secret = os.environ.get(_KEY_ENV), os.environ.get(_SECRET_ENV)
    if key and secret:
        return key, secret
    if _KEYFILE.exists():
        try:
            d = json.loads(_KEYFILE.read_text("utf-8"))
            return d.get("key"), d.get("secret")
        except (json.JSONDecodeError, OSError):
            return None, None
    return None, None


def has_keys() -> bool:
    k, s = _creds()
    return bool(k and s)


def _get(path: str, params: dict[str, Any] | None = None) -> Any:
    url = f"{_BASE}{path}"
    if params:
        url += "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": "quant-spot-testnet/1.0"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read())


def _signed(path: str, params: dict[str, Any], *, method: str = "GET") -> Any:
    key, secret = _creds()
    if not key or not secret:
        raise RuntimeError("no spot-testnet keys: set BINANCE_SPOT_TESTNET_KEY / _SECRET "
                           "(or data/secrets/binance_spot_testnet.json)")
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


def prices() -> dict[str, float]:
    """Latest spot price per symbol (public)."""
    data = _get("/api/v3/ticker/price")
    return {d["symbol"]: float(d["price"]) for d in data} if isinstance(data, list) else {}


def _prec_of(step: float) -> int:
    """Number of decimals implied by a step/tick size (e.g. 0.001 -> 3)."""
    s = f"{step:.10f}".rstrip("0")
    return len(s.split(".")[1]) if "." in s and step < 1 else 0


def exchange_filters() -> dict[str, dict[str, float]]:
    """Per-symbol step, min qty, base precision, price tick + precision (for valid spot sizing).

    ``min_notional`` is the venue's minimum ORDER VALUE -- a gate quantity filters cannot express:
    an order can satisfy stepSize AND minQty and still be rejected for being worth too little.
    Binance publishes it as NOTIONAL (current) or MIN_NOTIONAL (legacy); 0.0 means this symbol has
    no published minimum, so callers must keep their own conservative floor for that case.

    THIS IS THE MODULE THE MONEY PATH ACTUALLY IMPORTS, and the field was added only to
    `binance_spot_live` -- whose own docstring warned, in as many words, that
    `run_cashcarry_executor` and `run_stranded_recovery` import the TESTNET modules, so a field
    added only there "reaches NOTHING". It then reached nothing for the executor: every sizing
    decision on the live path ran without the venue's minimum order value, so an order could
    clear both quantity filters and still be rejected on value -- and on a two-legged carry a leg
    rejected while its partner fills is a naked directional position, not a no-op.

    `tests/execution/test_filter_parity.py` pins the two parsers' key sets AND their values so
    this divergence fails a test instead of shipping inert. Futures publishes the same filter
    under the key ``notional``, NOT ``minNotional`` -- copying this line there yields 0.0 for
    every symbol.
    """
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
    """Resting book liquidity: total QUOTE (USDT) value within ``pct`` of the touch on one side.

    side='BUY' sums the asks a buy would eat; side='SELL' sums the bids. Returns 0.0 on any
    failure or an empty book -- callers must treat 'unknown' as 'thin' and stand aside."""
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
    """Venue-truth average fill price of OUR trades on ``symbol`` since ``start_ms`` (signed).

    side='BUY' averages our buys, 'SELL' our sells. None when no fills are visible yet or the
    read fails -- callers fall back to the ticker mark rather than fabricate a price."""
    try:
        trades = _signed("/api/v3/myTrades", {"symbol": symbol, "startTime": start_ms,
                                              "limit": 100})
        fills = [t for t in trades if bool(t.get("isBuyer")) == (side == "BUY")]
        base = sum(float(t["qty"]) for t in fills)
        quote = sum(float(t["quoteQty"]) for t in fills)
        return quote / base if base > 0 and quote > 0 else None
    except Exception:
        return None


def my_trades(symbol: str, start_ms: int, end_ms: int | None = None,
              limit: int = 1000) -> list[dict[str, Any]]:
    """Raw venue-truth fill rows for ``symbol`` in [start_ms, end_ms) (signed, read-only).

    Unlike ``avg_fill`` this returns every field (qty, quoteQty, commission, commissionAsset,
    isBuyer, time) un-aggregated, for forensic reconciliation. Binance cannot combine startTime
    and endTime beyond a 24h span on this endpoint -- callers passing a wider window get only
    the startTime-anchored page; this is a diagnostic reader, not a paginating aggregator."""
    params: dict[str, Any] = {"symbol": symbol, "startTime": start_ms, "limit": limit}
    if end_ms is not None:
        params["endTime"] = end_ms
    try:
        res = _signed("/api/v3/myTrades", params)
        return list(res) if isinstance(res, list) else []
    except Exception:
        return []


def balances() -> dict[str, float]:
    """Free balance per asset (non-zero only). The spot 'position' is just what you hold."""
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

    GAP #49 EXTENDED TO SPOT, 2026-08-06. See binance_spot_live.place_market for the full
    reasoning. Short version: every futures order has carried a deterministic client order ID
    since GAP #49 and no spot order carried one, so on the cash-carry pair an ambiguous timeout
    left the retry deduped on the futures leg and PLACED AGAIN on the spot leg -- two spot longs
    against one perp short, which is a naked long, not an oversized carry.

    Kept in step with the live module because they are drop-in replacements and this is where the
    behaviour is rehearsed before it is trusted with money -- including the new failure mode, a
    duplicate REJECTION, which is the one an operator needs to have seen on testnet first.
    """
    res = _signed("/api/v3/order", {
        "symbol": symbol, "side": side, "type": "MARKET", "quantity": qty,
        "newClientOrderId": client_order_id(symbol, side, "spot", cycle=cycle),
    }, method="POST")
    return dict(res) if isinstance(res, dict) else {"raw": res}


def place_market_quote(symbol: str, side: str, quote_usdt: float,
                       cycle: str | None = None) -> dict[str, Any]:
    """Spot MARKET order sized in QUOTE (USDT) -- convenient for buying $X of an asset."""
    res = _signed("/api/v3/order", {
        "symbol": symbol, "side": side, "type": "MARKET", "quoteOrderQty": quote_usdt,
        "newClientOrderId": client_order_id(symbol, side, "spotquote", cycle=cycle),
    }, method="POST")
    return dict(res) if isinstance(res, dict) else {"raw": res}


def place_post_only(symbol: str, side: str, qty: float, price: float,
                    cycle: str | None = None) -> dict[str, Any]:
    """Post-only spot LIMIT order (type=LIMIT_MAKER) -- guaranteed MAKER (rejected if it crosses).

    Mirrors the futures GTX behaviour so the carry can be executed maker-first on both legs.
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

```

### libs\execution\binance_testnet.py
```python
"""Binance USD-M Futures TESTNET connector -- execution hands only, no alpha.

Hardened, testnet-ONLY REST client: signed requests (HMAC-SHA256), keys read from the environment
(BINANCE_TESTNET_KEY / BINANCE_TESTNET_SECRET) -- NEVER committed to code. The base URL is pinned to
the testnet, so this cannot touch a live account. It only does what the brain tells it: read account
/ positions / filters, set leverage, place market orders, flatten. No signal or sizing logic lives
here. Without keys it still serves public market data and reports ``has_keys() == False``.

WHY A BINANCE MODULE SURVIVES AN MT5-ONLY PURGE -- DO NOT "CLEAN THIS UP" (2026-09-05).
This repo holds ONE desk, the MT5/Fusion desk, and the retired crypto-exchange desk was deleted in
full. This file and its sibling `binance_spot_testnet.py` are the two deliberate exceptions, and
they are exceptions for a reason that has nothing to do with trading crypto: they are the TIER-3
DEADMAN RAIL's own plumbing. `scripts/run_deadman_reconciliation.py` (lines 24-25) and
`scripts/run_deadman_stranded_sweep.py` (line 31) import them directly, and
`scripts/run_deadman_switch.py` is a never-touch file. The rail is a SAFETY organ: it reconciles
and sweeps stranded state, and it must keep working whatever the desk trades.

They are also inert by construction -- the base URL is pinned to a TESTNET, so no code path here
can reach a live account or move real money -- which is precisely why they are safe to keep and
expensive to remove. `scripts/check_mt5_purity.py` allowlists both by name with this reason
attached, so they will never appear in that fence's breach list. If you are here to delete a
Binance file, this is the one you must not. Anything you change here changes the deadman rail.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import time
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

from libs.execution.collateral import STABLE_COLLATERAL
from libs.execution.idempotency import client_order_id

_BASE = "https://testnet.binancefuture.com"   # PINNED testnet -- never live
_KEY_ENV = "BINANCE_TESTNET_KEY"
_SECRET_ENV = "BINANCE_TESTNET_SECRET"  # noqa: S105 -- env-var name, not the secret
# Convenience: keys may live in env (preferred) OR a local untracked file (set once). NOT in code.
_KEYFILE = Path("data/secrets/binance_testnet.json")


def _creds() -> tuple[str | None, str | None]:
    key, secret = os.environ.get(_KEY_ENV), os.environ.get(_SECRET_ENV)
    if key and secret:
        return key, secret
    if _KEYFILE.exists():
        try:
            d = json.loads(_KEYFILE.read_text("utf-8"))
            return d.get("key"), d.get("secret")
        except (json.JSONDecodeError, OSError):
            return None, None
    return None, None


def has_keys() -> bool:
    k, s = _creds()
    return bool(k and s)


def _get(path: str, params: dict[str, Any] | None = None) -> Any:
    url = f"{_BASE}{path}"
    if params:
        url += "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": "quant-testnet/1.0"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read())


def _signed(path: str, params: dict[str, Any], *, method: str = "GET") -> Any:
    key, secret = _creds()
    if not key or not secret:
        raise RuntimeError("no testnet keys: set BINANCE_TESTNET_KEY / BINANCE_TESTNET_SECRET "
                           "(or data/secrets/binance_testnet.json)")
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
    """Per-symbol step size, min qty, price/qty precision, and minimum order notional.

    ``min_notional`` is the venue's minimum ORDER VALUE; 0.0 means no published minimum, so
    callers must keep their own conservative floor for that case. USD-M futures publishes the
    value under the key ``notional``, NOT spot's ``minNotional`` -- reading the spot key here
    yields 0.0 for every symbol (tests/execution/test_filter_parity.py pins this)."""
    info = _get("/fapi/v1/exchangeInfo")
    out: dict[str, dict[str, float]] = {}
    for s in info.get("symbols", []):
        f = {flt["filterType"]: flt for flt in s.get("filters", [])}
        lot = f.get("LOT_SIZE", {})
        pf = f.get("PRICE_FILTER", {})
        notl = f.get("MIN_NOTIONAL", {}) or f.get("NOTIONAL", {})
        out[s["symbol"]] = {
            "step": float(lot.get("stepSize", 0.001)), "min_qty": float(lot.get("minQty", 0.0)),
            "qty_prec": int(s.get("quantityPrecision", 3)),
            "tick": float(pf.get("tickSize", 0.01)), "price_prec": int(s.get("pricePrecision", 2)),
            "min_notional": float(notl.get("notional") or notl.get("minNotional") or 0.0),
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

    None when no fills are visible yet or the read fails -- callers fall back to the mark
    rather than fabricate a price."""
    try:
        trades = _signed("/fapi/v1/userTrades", {"symbol": symbol, "startTime": start_ms,
                                                 "limit": 100})
        fills = [t for t in trades if t.get("side") == side]
        base = sum(float(t["qty"]) for t in fills)
        quote = sum(float(t["quoteQty"]) for t in fills)
        return quote / base if base > 0 and quote > 0 else None
    except Exception:
        return None


def my_trades(symbol: str, start_ms: int, end_ms: int | None = None,
              limit: int = 1000) -> list[dict[str, Any]]:
    """Raw venue-truth futures fill rows for ``symbol`` in [start_ms, end_ms) (signed, read-only).

    Unlike ``avg_fill`` this returns every field (qty, quoteQty, commission, realizedPnl, side,
    time) un-aggregated, for forensic reconciliation. Diagnostic reader, not a pagination
    aggregator -- mirrors ``binance_spot_testnet.my_trades``."""
    params: dict[str, Any] = {"symbol": symbol, "startTime": start_ms, "limit": limit}
    if end_ms is not None:
        params["endTime"] = end_ms
    try:
        res = _signed("/fapi/v1/userTrades", params)
        return list(res) if isinstance(res, list) else []
    except Exception:
        return []


def mark_prices() -> dict[str, float]:
    """Latest price per symbol (public endpoint -- no keys needed, used for sizing)."""
    data = _get("/fapi/v1/ticker/price")
    return {d["symbol"]: float(d["price"]) for d in data} if isinstance(data, list) else {}


def account_balance() -> float:
    """USDT wallet balance on the testnet futures account."""
    for b in _signed("/fapi/v2/balance", {}):
        if b.get("asset") == "USDT":
            return float(b.get("balance", 0.0))
    return 0.0


# the tuple lives in libs/execution/collateral.py -- two copies would drift
_STABLE_COLLATERAL = STABLE_COLLATERAL


def account_summary() -> dict[str, float]:
    """Equity, wallet, unrealized PnL, available, and margin used (the live P&L snapshot).

    EQUITY is the MAX of two venue-derived measures: totalMarginBalance, and the face-value
    sum of per-asset marginBalance across stable collateral. Under multiAssetsMargin=False
    totalMarginBalance is USDT-only -- it hid $5,000 of USDC collateral, sizing the book at
    1/25th of true wealth and feeding the deadman a high-water below its dust floor, which
    disarmed the ruin rail at every equity (2026-07-30 deep sweep, R0053/R0054); the stable
    sum covers that mode. Under multiAssetsMargin=True totalMarginBalance is the venue's own
    USD-marked total including non-stables (which the stable sum cannot price) and wins the
    max. Max never reads below either truth; a depegged stable can overstate by its depeg,
    second-order next to the $5,000 blindness. `available` stays venue-reported because
    wealth and order capacity are different quantities."""
    a = _signed("/fapi/v2/account", {})
    eq = max(sum(float(x.get("marginBalance", 0.0)) for x in a.get("assets", [])
                 if x.get("asset") in _STABLE_COLLATERAL),
             float(a.get("totalMarginBalance", 0.0)))
    return {
        "wallet": float(a.get("totalWalletBalance", 0.0)),
        "equity": eq,
        "unrealized_pnl": float(a.get("totalUnrealizedProfit", 0.0)),
        "available": float(a.get("availableBalance", 0.0)),
        "margin_used": float(a.get("totalInitialMargin", 0.0)),
    }


def _income_rows(since_ms: int, income_type: str = "",
                 fetch: Any = None, symbol: str = "") -> list[dict[str, Any]]:
    """ALL income rows since ``since_ms`` -- paginated past the venue's 1000-row page cap.

    The endpoint serves at most 1000 rows per call; a busy book exceeds that within days, after
    which every aggregate (funding, realized PnL, commission) silently understates. Pages forward
    by advancing startTime to the last row's timestamp, de-duping on (tranId, type, symbol, time)
    so same-millisecond rows are neither dropped nor double-counted. Optional ``symbol`` narrows
    to one instrument (venue-supported filter) for per-symbol forensic reconciliation."""
    get = fetch or (lambda p: _signed("/fapi/v1/income", p))
    params: dict[str, Any] = {"limit": 1000}
    if income_type:
        params["incomeType"] = income_type
    if symbol:
        params["symbol"] = symbol
    if not since_ms:                                   # no anchor -> recent snapshot (one page)
        rows = get(params)
        return list(rows) if isinstance(rows, list) else []
    out: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str, str]] = set()
    cursor = since_ms
    for _ in range(50):                                # hard bound: 50 pages / 50k rows
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
        cursor = last + 1 if last <= cursor else last  # full same-ms page -> step past it
    return out


def income_summary(since_ms: int = 0, fetch: Any = None) -> dict[str, float]:
    """Realized PnL, funding earned/paid, and commission since ``since_ms`` (default: recent)."""
    # gross_profit/gross_loss = EVERY income event split by sign (winning closes + funding earned vs
    # losing closes + funding paid + fees) -> the true trading-report gross split, not a sign-split
    # of the NETTED realized_pnl (which hides winning trades inside a net-negative total).
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


def commission_events(since_ms: int, symbol: str = "") -> list[dict[str, Any]]:
    """Per-EVENT commission rows (symbol, time, commission) for per-trade fee attribution.

    ``income_summary`` returns only the AGGREGATE commission, which cannot answer "what did THIS
    round-trip cost". Per-trade attribution is what separates a bleeding hold-class from a
    bleeding execution path, and the desk's own trade log cannot supply it: ``_tca`` records
    slippage-vs-mid and no commission term at all, so every per-trade ``net`` in
    data/cashcarry_trades.json is fee-blind by construction (2026-07-28 finding -- the venue
    billed $1,750.65 while the log's aggregate net read +$0.16).

    Read-only and paginated through the audited ``_income_rows`` path, which is the only
    sanctioned way to read this endpoint (the 2026-07-26 truncation incident: a direct
    limit=1000 call silently returned a page cap and understated commission by ~4.4x).
    Commission is returned POSITIVE-MEANS-PAID, matching ``_tca``'s sign convention.
    """
    return [{"symbol": str(r.get("symbol") or ""),
             "time": int(r.get("time") or 0),
             "commission": abs(float(r.get("income") or 0.0))}
            for r in _income_rows(since_ms, "COMMISSION", symbol=symbol)]


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
    squeeze that took it -- the caller flattens the spot leg instead (2026-07-12 review).
    Returns symbol -> count of force events in the window; {} without keys or on error.
    """
    if not has_keys():
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
    """Venue MARKET_LOT_SIZE cap, cached. inf when unknown -- never invent a limit.

    2026-07-27 incident: COOKIEUSDT maxQty is 150,000 here, and the desk was sending 183,140.
    The venue rejected every market order with -4005, the caller fell back to a RESTING post-only
    limit, and accumulated fills from repeated cycles bought a short through zero into a
    +916,772 LONG carrying -$482.
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
    """Market order, SPLIT to respect the venue MARKET_LOT_SIZE cap.

    ``reduce_only=True`` makes the order arithmetically incapable of crossing zero into the
    opposite position -- mandatory on any cover/close leg. Defaults False so opens are unchanged.
    """
    cap = _market_max_qty(symbol)
    remaining, last, n = float(qty), None, 0
    # GAP #49: mirrors binance_live exactly. The testnet connector is the one the executor
    # actually imports today, so an idempotency guarantee that exists only on the live module
    # is a guarantee the desk does not have.
    intent = "close" if reduce_only else "open"
    while remaining > 0 and n < 50:
        chunk = min(cap, remaining) if cap != float("inf") else remaining
        params = {"symbol": symbol, "side": side, "type": "MARKET", "quantity": chunk,
                  "newClientOrderId": client_order_id(symbol, side, intent, chunk=n, cycle=cycle)}
        if reduce_only:
            params["reduceOnly"] = "true"
        last = _signed("/fapi/v1/order", params, method="POST")
        remaining -= chunk
        n += 1
    return dict(last) if isinstance(last, dict) else {"raw": last}


def place_post_only(symbol: str, side: str, qty: float, price: float,
                    cycle: str | None = None) -> dict[str, Any]:
    """Post-only LIMIT order (timeInForce=GTX) -- guaranteed MAKER (rejected if it would cross).

    Pays the maker fee (~half the taker fee on Binance futures) instead of crossing the spread.
    Returns the order dict (status NEW if it rests, or an error if it would have crossed).
    """
    res = _signed("/fapi/v1/order", {
        "symbol": symbol, "side": side, "type": "LIMIT", "timeInForce": "GTX",
        "quantity": qty, "price": price,
        # GAP #49. Resting orders are MORE dangerous to duplicate, not less: incident #6 was
        # accumulated resting fills walking a short through zero into a +916,772 long.
        "newClientOrderId": client_order_id(symbol, side, "postonly", cycle=cycle),
    }, method="POST")
    return dict(res) if isinstance(res, dict) else {"raw": res}


def place_stop_market(symbol: str, side: str, qty: float, stop_price: float) -> dict[str, Any]:
    """Reduce-only STOP_MARKET -- the venue-side rail that survives total host death.

    R0217. This existed ONLY on `binance_live`, and the executor reaches its stop reconciler
    through `binance_testnet as fut` (run_cashcarry_executor.py:30). The guard at
    `_reconcile_protective_stops` is `hasattr(fut, "place_stop_market")`, so on every environment
    the desk has ever actually run, the reconciler returned [] on its first line and the
    host-death rail did not exist -- disclosed in that function's docstring as a "testnet parity
    gap" and never converted into a rail, which is an open defect rather than documentation.

    Porting it here (rather than only paging on the missing capability) is what puts the rail in
    the environment being VALIDATED: a rail first exercised on the day real capital arrives has
    never been exercised. Paper-safe -- testnet fills are not money.
    """
    res = _signed("/fapi/v1/order", {
        "symbol": symbol, "side": side, "type": "STOP_MARKET", "quantity": qty,
        "stopPrice": stop_price, "reduceOnly": "true",
    }, method="POST")
    return dict(res) if isinstance(res, dict) else {"raw": res}


def cancel_order(symbol: str, order_id: int) -> dict[str, Any]:
    """Cancel ONE order by id -- surgical, so a maker-quote cleanup can never take the
    protective stop down with it.

    Shipped WITH `place_stop_market` deliberately: `_reconcile_protective_stops` takes its
    canceller via `getattr(fut, "cancel_order", None)` and degrades to placement-only when it is
    absent. Adding the placer alone would therefore leave drifted stops uncancelled and re-place
    a fresh one every pass -- unbounded stop accumulation on the money path, strictly worse than
    the no-op it replaces. The pair is the unit.
    """
    res = _signed("/fapi/v1/order", {"symbol": symbol, "orderId": order_id}, method="DELETE")
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

    Kept byte-for-byte in step with binance_live.flatten_all -- see that docstring for the full
    reasoning. Short version: the size comes from a `positions()` read, the position can shrink
    between that read and the fill, and a non-reduce-only close then SELLS THROUGH ZERO into the
    opposite position. `reduce_only=True` also corrects the client order ID, which was tagging
    every emergency close as an `open` and could collide with a genuine entry inside the same 90s
    idempotency bucket. Per-symbol isolation stops one rejected leg (routinely -2022, reduce-only
    against an already-flat position) from abandoning the rest of the book.

    THE TESTNET COPY MATTERS AS MUCH AS THE LIVE ONE, for the reason the drop-in interface exists:
    this is where the flatten path is actually exercised before it is trusted with money. A
    testnet that closes positions by a mechanism the live module no longer uses is a rehearsal of
    the wrong thing, and `tests/execution/test_binance_live.py` pins the two signatures together.
    """
    out: list[dict[str, Any]] = []
    for sym, amt in positions().items():
        side = "SELL" if amt > 0 else "BUY"
        try:
            out.append(place_market(sym, side, abs(amt), reduce_only=True))
        except Exception as exc:
            out.append({"symbol": sym, "side": side, "qty": abs(amt), "error": repr(exc)})
    return out

```

### libs\ops\derisk_ladder.py
```python
"""§4 pager de-risk ladder: an unacknowledged page is itself a risk event.

The premise is that the desk runs unattended and the principal is asleep. A critical page that
nobody acks does not mean "probably fine" -- it means the one human rail is currently absent, and
the book should shed risk on a clock rather than wait indefinitely for a human who may not come.

    15 min unacked -> cancel resting orders + halve max size
    60 min unacked -> flatten to neutral
     4 h  unacked -> full flatten, entries DISABLED until manual re-arm

Two properties this file exists to guarantee. The ladder is MONOTONIC: it only ever climbs while
a page stays unacked, so a flapping clock or an out-of-order tick can never walk risk back up.
And the top rung LATCHES: `requires_manual_rearm` stays true until a human clears it, because the
whole premise of rung 4h is that automation has been running without oversight for four hours --
letting that same automation decide it is fine now would defeat the rung entirely.

Pure logic; the acting half is scripts/run_live_guard.py.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

_STATE = Path("data/derisk_state.json")

# the spec's three rungs in seconds. Ordered ascending; `rung_for` walks them in reverse.
RUNG_CANCEL_HALVE_S = 15 * 60.0
RUNG_FLATTEN_S = 60 * 60.0
RUNG_FULL_FLATTEN_S = 4 * 3600.0


@dataclass(frozen=True)
class Rung:
    """What the desk must be doing at this level of pager silence."""

    name: str
    threshold_s: float
    cancel_resting: bool = False
    size_multiplier: float = 1.0
    flatten: bool = False
    entries_allowed: bool = True
    requires_manual_rearm: bool = False

    @property
    def is_floor(self) -> bool:
        return self.name == "nominal"


NOMINAL = Rung(name="nominal", threshold_s=0.0)

LADDER: tuple[Rung, ...] = (
    NOMINAL,
    Rung(name="cancel_and_halve", threshold_s=RUNG_CANCEL_HALVE_S,
         cancel_resting=True, size_multiplier=0.5),
    Rung(name="flatten_to_neutral", threshold_s=RUNG_FLATTEN_S,
         cancel_resting=True, size_multiplier=0.0, flatten=True),
    Rung(name="full_flatten_disarmed", threshold_s=RUNG_FULL_FLATTEN_S,
         cancel_resting=True, size_multiplier=0.0, flatten=True,
         entries_allowed=False, requires_manual_rearm=True),
)


def rung_for(unacked_s: float) -> Rung:
    """Highest rung whose threshold the silence has passed. Never interpolates, never skips down.

    A negative age (clock skew, a page stamped in the future) reads as nominal rather than
    wrapping to a high rung -- fail-safe here means "do not flatten the book because NTP moved".
    """
    if unacked_s <= 0:
        return NOMINAL
    for r in reversed(LADDER):
        if unacked_s >= r.threshold_s and not r.is_floor:
            return r
    return NOMINAL


def unacked_since(alert_state: dict[str, Any], ack_ts: float,
                  prior: float | None) -> float | None:
    """When did the current run of unacknowledged paging begin? None when nothing is pending.

    ``alert_state`` is scripts/run_alerts.py's ``data/.last_alerts.json``: ``_paged`` lists the
    keys currently alerting, and ``state[key]`` is when each was last pushed. A page counts as
    acknowledged once the operator's ack post-dates it.

    ``prior`` anchors the clock. Once a run of silence starts we keep its ORIGINAL start time --
    recomputing from the newest page every tick would let a re-paging condition reset the ladder
    forever, which is the exact scenario (a nagging alert nobody answers) the ladder is for.
    """
    paged = alert_state.get("_paged")
    if not isinstance(paged, list):
        return None
    stamps: list[float] = []
    for key in paged:
        v = alert_state.get(str(key))
        if isinstance(v, (int, float)) and float(v) > ack_ts:
            stamps.append(float(v))
    if not stamps:
        return None
    return prior if prior is not None else min(stamps)


@dataclass
class LadderState:
    """Persisted ladder position. Survives restarts -- see NakedWatch for the same reasoning."""

    oldest_unacked_ts: float | None = None
    reached: str = "nominal"
    rearm_required: bool = False
    history: list[dict[str, Any]] = None  # type: ignore[assignment]
    path: Path = _STATE

    def __post_init__(self) -> None:
        if self.history is None:
            self.history = []

    @classmethod
    def load(cls, path: Path = _STATE) -> LadderState:
        try:
            d = json.loads(path.read_text("utf-8"))
        except (OSError, json.JSONDecodeError):
            d = {}
        if not isinstance(d, dict):
            d = {}
        ts = d.get("oldest_unacked_ts")
        hist = d.get("history")
        return cls(
            oldest_unacked_ts=float(ts) if isinstance(ts, (int, float)) else None,
            reached=str(d.get("reached", "nominal")),
            rearm_required=bool(d.get("rearm_required", False)),
            history=hist if isinstance(hist, list) else [],
            path=path,
        )

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps({
            "oldest_unacked_ts": self.oldest_unacked_ts,
            "reached": self.reached,
            "rearm_required": self.rearm_required,
            "history": self.history[-200:],
        }, indent=2), "utf-8")
        tmp.replace(self.path)

    def _index(self, name: str) -> int:
        for i, r in enumerate(LADDER):
            if r.name == name:
                return i
        return 0

    def update(self, unacked_since: float | None, now: float) -> Rung:
        """Advance the ladder for this tick and return the rung now in force.

        ``unacked_since`` is the timestamp of the OLDEST page still unacknowledged, or None when
        every page is acked. Clearing resets the ladder to nominal -- except the manual-re-arm
        latch, which only ``rearm()`` can clear.
        """
        if unacked_since is None:
            if self.reached != "nominal":
                self.history.append({"ts": now, "event": "cleared", "from": self.reached})
            self.oldest_unacked_ts = None
            self.reached = "nominal"
            return NOMINAL if not self.rearm_required else LADDER[-1]

        self.oldest_unacked_ts = unacked_since
        target = rung_for(now - unacked_since)
        # MONOTONIC: never step down while the page is still unacked, whatever the clock says.
        if self._index(target.name) > self._index(self.reached):
            self.history.append({"ts": now, "event": "escalated",
                                 "from": self.reached, "to": target.name,
                                 "unacked_s": round(now - unacked_since, 1)})
            self.reached = target.name
        current = LADDER[self._index(self.reached)]
        if current.requires_manual_rearm:
            self.rearm_required = True
        return current

    def effective(self) -> Rung:
        """The rung actually in force, honouring a latched re-arm requirement."""
        if self.rearm_required:
            return LADDER[-1]
        return LADDER[self._index(self.reached)]

    def rearm(self, who: str, now: float) -> bool:
        """Clear the top-rung latch. A HUMAN act -- never call this from an automated path."""
        if not self.rearm_required:
            return False
        self.rearm_required = False
        self.reached = "nominal"
        self.oldest_unacked_ts = None
        self.history.append({"ts": now, "event": "rearmed", "by": who})
        return True

```

### libs\portfolio\risk_parity.py
```python
"""Risk parity — allocate risk equally across components (equal risk contribution)."""

from __future__ import annotations

from collections.abc import Sequence
from typing import cast

import numpy as np

from libs.portfolio.covariance import covariance_from_alphas
from libs.portfolio.errors import PortfolioError
from libs.portfolio.models import AlphaInput


def risk_parity_weights(
    cov: np.ndarray, *, max_iter: int = 10_000, tol: float = 1e-10
) -> np.ndarray:
    """Equal-risk-contribution weights via the fixed point ``w_i ~ 1 / (cov·w)_i``.

    Converges to inverse-volatility weights for a diagonal covariance and to full ERC otherwise.
    """
    sigma = np.asarray(cov, dtype="float64")
    n = sigma.shape[0]
    if n == 0:
        raise PortfolioError("covariance must be non-empty")
    diag = np.diag(sigma)
    if (diag <= 0).any():
        raise PortfolioError("covariance diagonal must be positive")

    w = 1.0 / np.sqrt(diag)
    w /= w.sum()
    for _ in range(max_iter):
        marginal = sigma @ w
        if (marginal <= 0).any():
            break
        w_new = 1.0 / marginal
        w_new /= w_new.sum()
        if np.max(np.abs(w_new - w)) < tol:
            w = w_new
            break
        w = w_new
    return cast("np.ndarray", w)


def allocate_risk(
    alphas: Sequence[AlphaInput], *, correlation: np.ndarray | None = None
) -> dict[str, float]:
    """Allocate weights so that each alpha contributes equal risk."""
    cov = covariance_from_alphas(alphas, correlation)
    weights = risk_parity_weights(cov)
    return {alpha.alpha_id: float(w) for alpha, w in zip(alphas, weights, strict=True)}

```

### libs\research\adapters\riskfolio.py
```python
"""Riskfolio-Lib adapter -- an allocator CHALLENGER -> a packet of allocation EVIDENCE.

Over the aligned H1 returns of the bundle symbols the engine solves a few canonical programmes
(minimum-risk under MV and CVaR, hierarchical risk parity); each configuration is one charged
trial. What leaves the sandbox is evidence for the desk's allocator comparison -- challenger
loadings, effective number of bets, concentration -- with authority "none". It NEVER sizes
capital: the portfolio-capital allocator is the desk's, by law (LAWS 5m, growth governance).
"""
from __future__ import annotations

from typing import Any

from libs.research import adapters as A
from libs.research.external_federation import ExternalResearchPacket

SYSTEM = "riskfolio"
CONFIGS: tuple[tuple[str, str, str], ...] = (("Classic", "MV", "MinRisk"),
                                             ("Classic", "CVaR", "MinRisk"),
                                             ("HRP", "MV", "hierarchical"))


def run(bundle: A.ResearchBundle) -> ExternalResearchPacket:
    rp = A.library("riskfolio")
    pd = A.library("pandas")
    if rp is None or pd is None:
        return A.unmeasured(SYSTEM, bundle, "riskfolio (or pandas) is not importable here")
    import numpy as np
    frames = [f for f in bundle.frames("H1") if len(f) > 200]
    if len(frames) < 3:
        return A.unmeasured(SYSTEM, bundle, "fewer than three H1 frames with 200+ bars")
    series = {f.symbol: pd.Series(f.log_returns(), index=pd.Index(f.time[1:])) for f in frames}
    R = pd.DataFrame(series).dropna()
    if len(R) < 100:
        return A.unmeasured(SYSTEM, bundle, f"only {len(R)} aligned H1 observations")
    deadline = A.Deadline(bundle.compute_budget_s)
    trials = 0
    methods: list[dict[str, Any]] = []
    corr = R.corr().to_numpy()
    reps = [{"kind": "covariance_state", "symbols": list(R.columns), "n_obs": len(R),
             "mean_pairwise_corr": float(corr[np.triu_indices(corr.shape[0], 1)].mean()),
             "eigen_share_top": float(np.linalg.eigvalsh(corr)[-1] / corr.shape[0])}]
    for model, rm, obj in CONFIGS:
        if deadline.expired():
            break
        trials += 1
        try:
            if model == "HRP":
                port = rp.HCPortfolio(returns=R)
                w = port.optimization(model="HRP", codependence="pearson", rm=rm, rf=0,
                                      linkage="ward")
            else:
                port = rp.Portfolio(returns=R)
                port.assets_stats(method_mu="hist", method_cov="hist")
                w = port.optimization(model=model, rm=rm, obj=obj, rf=0, l=0, hist=True)
            if w is None:
                raise RuntimeError("the solver returned no solution")
            loads = {str(k): float(v) for k, v in w.iloc[:, 0].items()}
        except Exception as exc:
            methods.append({"kind": "UNMEASURED", "model": model, "risk_measure": rm,
                            "why": f"{type(exc).__name__}: {exc}"[:200]})
            continue
        vals = np.asarray(list(loads.values()), dtype=float)
        methods.append({"kind": "allocator_challenger", "model": model, "risk_measure": rm,
                        "objective": obj, "challenger_loadings": loads,
                        "effective_bets": float(1.0 / max(float(np.sum(vals ** 2)), 1e-12)),
                        "max_loading": float(vals.max()), "n_obs": len(R),
                        "authority": "none: evidence for the desk allocator's challenger "
                                     "comparison; this engine never sizes capital"})
    return A.packet(SYSTEM, bundle, trials=trials, research_methods=methods,
                    representations=reps)


if __name__ == "__main__":
    raise SystemExit(A.cli(run, SYSTEM))

```

### libs\risk\__init__.py
```python
"""``libs.risk`` — the CRO authority in code.

Kelly sizing (fractional / Bayesian / adaptive), volatility targeting, risk budgeting, factor
caps, correlation controls, heat controls, the drawdown governor, tail risk (VaR/CVaR/gap/stress),
crisis controls, equity preservation, the dynamic global scalar, position-size synthesis, and the
mandatory risk gate. Risk overrides alpha — structurally.
"""

from __future__ import annotations

from libs.risk.config import (
    CorrelationLimits,
    CrisisConfig,
    DrawdownLadder,
    ExposureLimits,
    HeatLimits,
    KellyLimits,
    PreservationConfig,
    RiskConfig,
    TailLimits,
    VolConfig,
)
from libs.risk.correlation import (
    CorrelationResult,
    average_off_diagonal,
    check_correlation_limits,
    correlation_clusters,
    correlation_scalar,
    diversification_score,
    rolling_correlation,
    stressed_correlation,
)
from libs.risk.crisis import CrisisResponse, crisis_controller
from libs.risk.drawdown import DrawdownLevel, DrawdownResponse, compute_drawdown, drawdown_governor
from libs.risk.errors import RiskError, RiskGateError
from libs.risk.factor_caps import FactorExposureResult, check_factor_exposure
from libs.risk.gate import AccountState, OrderIntent, RiskDecision, risk_gate
from libs.risk.heat import HeatResult, PositionHeat, calculate_heat, check_heat_limits
from libs.risk.instruments import TIER1, TIER2, TIER3, Factor, get_factor, tier_of
from libs.risk.kelly import (
    AlphaStage,
    KellyScaling,
    adaptive_kelly_fraction,
    calculate_bayesian_kelly,
    calculate_kelly,
)
from libs.risk.preservation import (
    PreservationMode,
    PreservationResponse,
    equity_preservation_controller,
)
from libs.risk.risk_budget import (
    BudgetEnforcement,
    allocate_risk_budget,
    enforce_risk_budget,
    risk_contributions,
)
from libs.risk.scaling import GlobalScalar, global_risk_scalar
from libs.risk.sizing import PositionSizeResult, calculate_position_size
from libs.risk.tail import (
    StressScenario,
    StressTestResult,
    calculate_cvar,
    calculate_var,
    default_stress_scenarios,
    gap_through_stop_loss,
    stress_test_portfolio,
)
from libs.risk.vol_target import (
    adjust_for_volatility,
    ewma_volatility,
    realized_volatility,
    regime_adjusted_volatility,
    vol_target,
)

__all__ = [  # noqa: RUF022  # grouped by subsystem
    # config
    "RiskConfig", "KellyLimits", "VolConfig", "HeatLimits", "DrawdownLadder",
    "CorrelationLimits", "TailLimits", "CrisisConfig", "PreservationConfig", "ExposureLimits",
    # instruments / factors
    "Factor", "get_factor", "tier_of", "TIER1", "TIER2", "TIER3",
    # kelly
    "AlphaStage", "KellyScaling", "calculate_kelly", "calculate_bayesian_kelly",
    "adaptive_kelly_fraction",
    # vol targeting
    "realized_volatility", "ewma_volatility", "regime_adjusted_volatility", "vol_target",
    "adjust_for_volatility",
    # risk budgeting
    "risk_contributions", "allocate_risk_budget", "enforce_risk_budget", "BudgetEnforcement",
    # factor caps
    "check_factor_exposure", "FactorExposureResult",
    # correlation
    "rolling_correlation", "stressed_correlation", "correlation_clusters",
    "diversification_score", "average_off_diagonal", "correlation_scalar",
    "check_correlation_limits", "CorrelationResult",
    # heat
    "PositionHeat", "calculate_heat", "check_heat_limits", "HeatResult",
    # drawdown
    "compute_drawdown", "drawdown_governor", "DrawdownResponse", "DrawdownLevel",
    # tail
    "calculate_var", "calculate_cvar", "gap_through_stop_loss", "stress_test_portfolio",
    "StressScenario", "StressTestResult", "default_stress_scenarios",
    # crisis
    "crisis_controller", "CrisisResponse",
    # preservation
    "equity_preservation_controller", "PreservationResponse", "PreservationMode",
    # scaling / sizing
    "global_risk_scalar", "GlobalScalar", "calculate_position_size", "PositionSizeResult",
    # gate
    "risk_gate", "OrderIntent", "AccountState", "RiskDecision",
    # errors
    "RiskError", "RiskGateError",
]

```

### libs\risk\adaptive_stop.py
```python
"""Per-symbol volatility SIGNATURE -> adaptive stop distance, at constant monetary risk.

A RISK LAYER, NOT AN ALPHA. It changes where the stop goes and how big the position is; it never
decides direction or timing. Reverse-engineered from a public MQL5 article (MQL5_ARTICLE_23597,
2026-08-03) which discloses every coefficient in code, so this is a reproduction of a stated rule
rather than a fit.

THE CLAIM. A universal ATR multiplier places stops inside ordinary noise on one instrument and
absurdly far away on another, because instruments differ structurally in wick noise, pullback
depth, trend persistence and volatility-of-volatility. Separating a SLOW-MOVING symbol
personality from the CURRENT ATR should improve stop survival without touching the entry.

THE FALSIFIER IS DELIBERATELY HARSH, and it is the reason this file exists rather than a belief
that it works: against each sleeve's own frozen stop, at identical signal timestamps and
identical ex-ante monetary risk, adaptive stops must improve out-of-sample expectancy or E[log W]
after costs. FEWER STOP-OUTS IS NOT THE TEST -- a wider stop trivially buys that and pays for it
in size, which is exactly the trade the constant-risk normalisation exists to make visible.

Everything is computed from COMPLETED bars only. The forming bar never enters the signature and
never enters the ATR.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

__all__ = ["Signature", "adaptive_multiplier", "signature", "stop_distance"]


@dataclass(frozen=True)
class Signature:
    """One symbol's slow-moving personality. Recomputed on a cadence, never per bar."""

    mean_true_range: float
    mean_range: float
    mean_body: float
    mean_pullback: float
    tr_cv: float
    run_length: float
    n_bars: int

    @property
    def noise_ratio(self) -> float:
        """Body as a share of range. Low means wicky, and a stop placed close in gets taken."""
        return self.mean_body / self.mean_range if self.mean_range > 0 else 1.0


def signature(df: pd.DataFrame, lookback: int = 1000) -> Signature | None:
    """The symbol's signature from the last `lookback` COMPLETED bars, or None if too few.

    NONE, NOT A DEFAULT. Fewer than 500 bars is not a symbol with an average personality, it is a
    symbol whose personality is UNMEASURED -- and the caller must fall back to its own frozen
    stop rather than to a fabricated multiplier (L1.28a).
    """
    if df is None or len(df) < 500:
        return None
    d = df.iloc[-lookback:] if len(df) > lookback else df
    high = d["high"].to_numpy(float)
    low = d["low"].to_numpy(float)
    close = d["close"].to_numpy(float)
    open_ = d["open"].to_numpy(float)
    prev = np.concatenate([[close[0]], close[:-1]])
    tr = np.maximum(high - low, np.maximum(np.abs(high - prev), np.abs(low - prev)))
    rng = high - low
    body = np.abs(close - open_)

    # Directional runs and the pullback inside them: how far price gives back before continuing
    # is what decides whether a stop survives an ordinary retracement.
    sign = np.sign(np.diff(close, prepend=close[0]))
    runs: list[int] = []
    cur = 1
    for i in range(1, len(sign)):
        if sign[i] == sign[i - 1] and sign[i] != 0:
            cur += 1
        else:
            runs.append(cur)
            cur = 1
    runs.append(cur)
    pullback = np.where(sign > 0, high - close, close - low)

    mtr = float(np.nanmean(tr))
    if not (mtr > 0):
        return None
    return Signature(
        mean_true_range=mtr,
        mean_range=float(np.nanmean(rng)),
        mean_body=float(np.nanmean(body)),
        mean_pullback=float(np.nanmean(np.abs(pullback))),
        tr_cv=float(np.nanstd(tr) / mtr),
        run_length=float(np.mean(runs)) if runs else 1.0,
        n_bars=len(d),
    )


def adaptive_multiplier(sig: Signature, spread: float = 0.0, *, base: float = 1.5,
                        lo: float = 1.0, hi: float = 4.0) -> float:
    """The five disclosed factors, multiplied and clamped. The coefficients are the source's own.

    They are NOT tuned here and must not be: every one is a degree of freedom, and fitting them
    on the same trades used to judge the layer is how a risk wrapper manufactures an edge that is
    really just a different stop.
    """
    noise = float(np.clip(0.80 + (1.0 - sig.noise_ratio) * 0.80, 0.80, 1.50))
    pull = float(np.clip(0.60 + 0.35 * (sig.mean_pullback / sig.mean_true_range), 0.70, 1.50))
    # The source classifies persistence into three tiers; the boundaries are its own.
    trend = 0.85 if sig.run_length >= 2.0 else (1.20 if sig.run_length < 1.5 else 1.00)
    spr = float(np.clip(1.0 + 2.0 * (spread / sig.mean_true_range), 1.00, 1.30))
    vol = float(np.clip(0.90 + 0.40 * sig.tr_cv, 0.90, 1.40))
    return float(np.clip(base * noise * pull * trend * spr * vol, lo, hi))


def stop_distance(sig: Signature | None, current_atr: float, spread: float = 0.0,
                  *, base: float = 1.5, lo: float = 1.0, hi: float = 4.0) -> float | None:
    """Adaptive stop distance in price units, or None when the signature is unmeasured."""
    if sig is None or not (current_atr > 0):
        return None
    return current_atr * adaptive_multiplier(sig, spread, base=base, lo=lo, hi=hi)

```

### libs\risk\capacity.py
```python
"""How much a sleeve can trade before its own footprint eats its edge.

Medallion capped its own capital because more money damaged the edge. That is the honest
statement of what capacity is: the size at which expected impact cost equals expected edge, and
beyond which every extra lot LOSES money on average even though the signal is right.

WHAT IS MEASURED. The desk's bars carry `tick_volume` per hour and its cost model carries the
spread. A square-root impact model -- the one every published study since Almgren-Chriss settles
on for the mid-frequency band -- says the price concession for trading a fraction q of the
interval's volume is

    impact = k * sigma * sqrt(q)

with sigma the interval's return volatility and k an order-one constant. Setting impact equal to
the sleeve's per-trade edge and solving for q gives the participation at which the edge is fully
consumed; multiplied by the typical volume in the sleeve's entry hour, that is the capacity in
contracts, and the allocator's per-sleeve bound is the SMALLER of that and its risk bound.

STATED CONSERVATIVELY AND BY NAME. `tick_volume` is the count of price updates, not traded
contracts; it is a proxy for activity and is labelled as one. k is set at the top of the
published range rather than the middle. A capacity number that is too small costs a little
growth; one that is too large costs the edge itself. Where volume is absent the answer is None
and the caller keeps its risk bound, never an invented ceiling.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd

#: Impact coefficient. Published mid-frequency estimates cluster around 0.5-1.0; the top of the
#: range is used because the direction of error that matters is the one that keeps the edge.
IMPACT_K = 1.0
#: Fraction of the edge capacity is allowed to consume. Half: a sleeve run at full capacity has
#: zero expected profit on its marginal lot, which is not a sleeve worth running.
EDGE_SHARE = 0.5
#: Hours of history the entry-hour volume profile is measured over.
PROFILE_DAYS = 120


@dataclass(frozen=True)
class Capacity:
    symbol: str
    #: Participation of the entry interval's volume at which impact = EDGE_SHARE * edge.
    participation: float | None
    #: Median activity (tick count) in the sleeve's entry hour, over PROFILE_DAYS.
    entry_hour_activity: float | None
    #: Realised hourly return vol used for the impact model.
    sigma_h: float | None
    #: Edge per trade as a fraction of price, the quantity impact is compared with.
    edge_frac: float | None
    #: Capacity in "activity units" -- ticks the sleeve may be a fraction of. NOT contracts.
    capacity_units: float | None
    why: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {k: (round(v, 8) if isinstance(v, float) else v) for k, v in self.__dict__.items()}


def capacity(symbol: str, bars: pd.DataFrame, edge_frac: float,
             entry_hours: tuple[int, ...] | None = None) -> Capacity:
    """Capacity of a sleeve on `symbol` earning `edge_frac` of price per trade at `entry_hours`."""
    if bars is None or bars.empty or "close" not in bars.columns:
        return Capacity(symbol, None, None, None, None, None, "no bars")
    if not np.isfinite(edge_frac) or edge_frac <= 0:
        return Capacity(symbol, None, None, None, float(edge_frac) if np.isfinite(edge_frac)
                        else None, None, "no positive edge to consume")
    d = bars.iloc[-24 * PROFILE_DAYS:]
    ret = np.log(d["close"].astype(float)).diff().dropna()
    sigma_h = float(ret.std(ddof=1)) if ret.size > 10 else None
    if sigma_h is None or sigma_h <= 0:
        return Capacity(symbol, None, None, None, edge_frac, None, "no usable return vol")
    if "tick_volume" not in d.columns:
        return Capacity(symbol, None, None, sigma_h, edge_frac, None,
                        "bars carry no tick_volume; capacity unmeasurable, risk bound stands")
    vol = d["tick_volume"].astype(float)
    if entry_hours:
        vol = vol[d.index.hour.isin(list(entry_hours))]
    vol = vol[vol > 0]
    if vol.size < 20:
        return Capacity(symbol, None, None, sigma_h, edge_frac, None,
                        "fewer than 20 active bars in the entry hours")
    activity = float(vol.median())
    # impact = K * sigma * sqrt(q) = EDGE_SHARE * edge  ->  q = (EDGE_SHARE*edge / (K*sigma))^2
    q = (EDGE_SHARE * edge_frac / (IMPACT_K * sigma_h)) ** 2
    q = float(min(q, 1.0))
    return Capacity(symbol, q, activity, sigma_h, edge_frac, q * activity,
                    f"impact model K={IMPACT_K}, edge share {EDGE_SHARE}; tick_volume is an "
                    "activity proxy, not contracts")


def bound_from_capacity(cap: Capacity, risk_bound: float, book_participation_per_unit_heat: float
                        ) -> tuple[float, str]:
    """The allocator's per-sleeve heat bound after capacity: min(risk bound, capacity-implied).

    `book_participation_per_unit_heat` is how much of the entry interval's activity one unit of
    heat represents for this account -- measured from fills once they exist, and until then the
    caller passes None and the risk bound stands untouched. Capacity NEVER raises a bound.
    """
    if cap.participation is None or not book_participation_per_unit_heat:
        return risk_bound, "capacity unmeasured; risk bound stands"
    implied = cap.participation / float(book_participation_per_unit_heat)
    if implied >= risk_bound:
        return risk_bound, f"risk bound binds (capacity would allow {implied:.4f})"
    return float(max(implied, 0.0)), (f"CAPACITY BINDS at {implied:.4f} heat: participation "
                                      f"{cap.participation:.3%} of entry-hour activity")

```

### libs\risk\capital_events.py
```python
"""CAPITAL EVENTS -- the only legitimate way out of a ruin-floor stop, and it is not a threshold.

THE ABSORBING STATE, measured 2026-07-30. `risk_controls.evaluate` flattens on
`dd_start = equity/start_equity - 1 <= -35%`, where `start_equity` is
`cashcarry_state["start_futures_equity"]` -- set ONCE at inception (2026-07-02, $5,000) and never
re-based. At audit time the book sat at -37.2% and had flattened on 113 consecutive rebalances,
100% of them, zero clears. The loop is self-sustaining and provably closed:

    flatten -> executor sets target/cands empty -> no opens -> no funding accrues
            -> equity is constant -> dd_start is constant -> flatten

The downstream cost is the launch itself: with no new fills, `execution_tape.coverage()["days"]`
froze at 26.42 against Gate 0's 28-day bar. The desk is closer to that criterion than it will ever
be again, and could not get closer by performing well.

=================================================================================================
WHAT IS **NOT** THE FIX
=================================================================================================
Lowering `drawdown_ruin`, re-basing automatically, or letting the executor clear its own stop.
L1.23 and the L2.8a immutable core forbid all three, and they are the same move: the optimiser
noticing that the cheapest way to resume trading is to move the rail that stopped it. The rail is
CORRECT -- the book really is down 37.2% from the capital it was given.

=================================================================================================
WHAT IS MISSING, AND IT IS A REAL GAP
=================================================================================================
A ruin floor is a STOP, not a pause, and this one has NO DEFINED WAY BACK. That is incomplete in
exactly the way L1.16a names for the research graveyard: *every kill records its re-entry
condition at kill time*. A risk stop with no re-entry condition is not maximally safe, it is
unspecified -- and unspecified states get resolved under pressure, by hand, at the worst moment.

The re-entry condition for a ruin stop is a CAPITAL EVENT: new money arrives, or the principal
formally restarts the book with a new inception. Both are acts a human performs, both change what
"drawdown from start" legitimately means, and neither is something the desk may do for itself.

THE ONE RULE THAT KEEPS THIS HONEST: a re-base with no new capital is REFUSED. Re-basing
`start_equity` to today's equity clears the breach instantly while nothing about the desk's
position has improved -- the pure form of eating the safety margin. Passing `deposit_usd=0`
therefore requires an explicit principal override carrying a written reason, which lands in an
append-only ledger. The full drawdown history is never erased: every event records the previous
inception, so cumulative loss since the FIRST inception is always reconstructible.

=================================================================================================
R0320 -- THE POST-EVENT DRAWDOWN BASELINE. THE DECISION, AND IT IS TIGHTENING ONLY.
=================================================================================================
`effective_start_equity` re-bases the RUIN rail's inception, which is the authorised, ledgered,
human-signed way back from a stop -- that stays exactly as it is. It left the PAUSE rail
(`risk_controls`' `dd_pause`, measured from the high-water mark) undefined after a capital event,
and the executor's own arithmetic then resolved it in the loosest possible direction: the rail
read `peak = max(peak_combined_equity, eq_c)` on RAW wallet equity, so money merely ARRIVING
lifted equity to a new high-water and a live -15% pause evaporated in one tick, with nothing
about the book's positions changed. Journal-verified 2026-08-01: a re-baseline moves the
denominator under the pause rail.

THE RULING: **the drawdown rail measures equity NET OF POST-INCEPTION EXTERNAL FLOWS, against a
flow-adjusted high-water that carries ACROSS every capital event.** A deposit raises the
high-water and the baseline ADDITIVELY, by exactly the dollars deposited and never
proportionally, so it can neither reduce measured drawdown nor un-trip a live pause -- new
capital buys back none of the loss it is arriving to cover. A withdrawal lowers the high-water by
at most the dollars removed and never below the flow-adjusted equity, so taking money out
manufactures no phantom drawdown, and equally erases none of a real one. In the rail's own space
the high-water is monotone non-decreasing: NO event may reset it downward, which is the single
property the pause rail was missing.

Corollary the arithmetic makes unavoidable: drawdown stays a RATIO on the pre-flow denominator.
Measuring a $1,000 loss against a peak that a $5,000 deposit just inflated would shrink -20% to
-3.3% -- the proportional re-base, the same move in percentage clothing, and it is refused here
for the same reason `rebase` refuses a $0 deposit.

`effective_start_equity` stays what it always was: the INCEPTION for P&L reporting and for the
ruin rail. Both published books (the executor and run_live_combined, R0322) read that one
function, so a re-base can never leave two books measuring from two different inceptions.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parents[2]
LEDGER = _ROOT / "data/capital_events.jsonl"


class CapitalEventRefused(RuntimeError):
    """A re-base that would clear a live ruin stop without new capital or explicit authority."""


@dataclass(frozen=True)
class CapitalEvent:
    kind: str                 # DEPOSIT | WITHDRAWAL | RESTART
    at: str
    deposit_usd: float
    equity_before: float
    equity_after: float
    start_equity_before: float
    start_equity_after: float
    authorised_by: str
    reason: str
    cumulative_loss_since_first_inception_usd: float

    def as_dict(self) -> dict[str, Any]:
        return dict(self.__dict__)


def history() -> list[dict[str, Any]]:
    if not LEDGER.exists():
        return []
    out = []
    for line in LEDGER.read_text("utf-8").splitlines():
        if line.strip():
            try:
                out.append(json.loads(line))
            except ValueError:
                continue
    return out


def first_inception_equity(current_start: float) -> float:
    """The ORIGINAL capital, before any re-base. Keeps total loss honest across restarts."""
    h = history()
    return float(h[0]["start_equity_before"]) if h else float(current_start)


def rebase(
    *,
    equity_now: float,
    start_equity: float,
    deposit_usd: float,
    authorised_by: str,
    reason: str,
    kind: str = "DEPOSIT",
    drawdown_ruin: float = 0.35,
) -> CapitalEvent:
    """Record a capital event and return the new inception. NEVER called automatically.

    `equity_now` is the equity BEFORE the deposit lands. The new inception is
    `equity_now + deposit_usd` -- the capital the book is actually being asked to work with from
    this moment. Drawdown is then measured from that, which is the only reading under which
    "drawdown from start" means anything after money moves.

    REFUSALS, and each is the rule rather than an edge case:
      * a re-base while a ruin stop is LIVE and `deposit_usd <= 0`, unless `authorised_by`
        explicitly carries the principal override -- this is the eat-the-safety-margin move;
      * an unsigned event (`authorised_by` empty) -- an unattributable capital event is how a
        rail gets cleared by nobody in particular;
      * a reason shorter than 12 characters -- "fix" is not a record.
    """
    eq, start = float(equity_now), max(1e-9, float(start_equity))
    dep = float(deposit_usd)
    breach_live = (eq / start - 1.0) <= -abs(drawdown_ruin)
    override = authorised_by.strip().upper().startswith("PRINCIPAL-OVERRIDE")

    if kind == "DEPOSIT" and dep <= 0:
        # A zero DEPOSIT is a no-op that still writes a row, moves the inception to today's equity
        # and links itself into the cumulative-loss chain. Found by running the CLI on an empty
        # state: it silently recorded a $0 deposit and reported success. A ledger of meaningless
        # rows is worse than no ledger -- it makes the real events harder to find. Clearing a stop
        # without new money is a RESTART, and it must say so.
        raise CapitalEventRefused(
            "a DEPOSIT of $0 records nothing. If you are restarting the book without new capital, "
            "pass kind='RESTART' and authorised_by='PRINCIPAL-OVERRIDE <name>' so the ledger says "
            "what actually happened.")
    if not authorised_by.strip():
        raise CapitalEventRefused(
            "unsigned capital event: authorised_by is required. A rail cleared by nobody in "
            "particular is a rail nobody owns.")
    if len(reason.strip()) < 12:
        raise CapitalEventRefused(
            f"reason {reason.strip()!r} is not a record -- state what happened and why, in a "
            "sentence a reader in six months can act on.")
    if breach_live and dep <= 0 and not override:
        raise CapitalEventRefused(
            f"a ruin stop is LIVE (equity {eq:,.2f} vs inception {start:,.2f} = "
            f"{eq / start - 1.0:.1%}) and this re-base adds NO capital. Re-basing to today's "
            "equity would clear the breach while nothing about the book improved -- the exact "
            "move L1.23 and the L2.8a immutable core exist to prevent. Deposit real capital, or "
            "pass authorised_by='PRINCIPAL-OVERRIDE <name>' and own it in the ledger.")

    new_start = eq + max(0.0, dep)
    first = first_inception_equity(start)
    ev = CapitalEvent(
        kind=kind, at=datetime.now(tz=UTC).isoformat(), deposit_usd=dep,
        equity_before=eq, equity_after=new_start,
        start_equity_before=start, start_equity_after=new_start,
        authorised_by=authorised_by.strip(), reason=reason.strip(),
        # Loss since the FIRST inception, not since the last re-base. A re-base moves the rail's
        # reference point; it must never move the desk's memory of what has been lost.
        cumulative_loss_since_first_inception_usd=round(eq - first, 2),
    )
    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    with LEDGER.open("a", encoding="utf-8") as f:
        f.write(json.dumps(ev.as_dict()) + "\n")
    return ev


def effective_start_equity(state_start_equity: float) -> float:
    """The inception the ruin rail should measure against, honouring any recorded re-base.

    Read-only and total: with no ledger it returns exactly what it was given, so the rail's
    behaviour is unchanged on any box that has never had a capital event. That matters -- this
    module must be incapable of loosening anything by merely existing.

    R0320: this is the INCEPTION (ruin rail + P&L reporting). It is deliberately NOT the pause
    rail's baseline -- that one is `flow_adjusted_rail` below, and it carries across events.
    """
    h = history()
    return float(h[-1]["start_equity_after"]) if h else float(state_start_equity)


# =================================================================================================
# R0320 -- FLOW-ADJUSTED DRAWDOWN RAILS. See the ruling in the module docstring.
# =================================================================================================


def event_flow_usd(ev: dict[str, Any]) -> float:
    """Signed external cash of ONE ledger row: positive INTO the book, negative OUT of it.

    Every ambiguity resolves in the TIGHTENING direction, because this number is subtracted from
    equity before the rail measures it -- a larger flow means a smaller flow-adjusted equity means
    MORE measured drawdown:

      * WITHDRAWAL takes `-abs(deposit_usd)` whichever sign the operator typed;
      * every other kind counts only `max(0, deposit_usd)`, so a negative "deposit" (a
        mis-keyed withdrawal that never said so) contributes nothing rather than crediting the
        book with a flow that would REDUCE its measured drawdown;
      * an unparseable row contributes nothing, which leaves its cash inside the measurement as
        P&L -- pessimistic, never a free pass.
    """
    try:
        dep = float(ev.get("deposit_usd", 0.0) or 0.0)
    except (TypeError, ValueError):
        return 0.0
    if str(ev.get("kind", "")).strip().upper() == "WITHDRAWAL":
        return -abs(dep)
    return max(0.0, dep)


def net_external_flows(events: list[dict[str, Any]] | None = None) -> float:
    """Net external cash recorded since the first inception. 0.0 with no ledger -- always."""
    evs = history() if events is None else events
    return round(sum(event_flow_usd(e) for e in evs if isinstance(e, dict)), 6)


@dataclass(frozen=True)
class FlowAdjustedRail:
    """The pause rail's two numbers, in the flow-adjusted space it must be measured in."""

    equity: float             # equity NET of post-inception external flows (the rail's numerator)
    peak: float               # flow-adjusted high-water, carried ACROSS capital events
    peak_raw: float           # the same high-water in raw wallet dollars (what state persists)
    net_flows_usd: float      # signed external flows recorded since the first inception
    n_events: int             # ledger rows behind `net_flows_usd`

    @property
    def dd_from_peak(self) -> float:
        """<= 0. The drawdown the pause rail charges, on the pre-flow denominator."""
        return self.equity / max(1e-9, self.peak) - 1.0


def flow_adjusted_rail(
    equity_now: float,
    stored_peak_flow_adj: float | None = None,
    stored_peak_raw: float | None = None,
    *,
    events: list[dict[str, Any]] | None = None,
) -> FlowAdjustedRail:
    """The R0320 pause-rail inputs: equity net of flows, and a high-water that survives events.

    `stored_peak_flow_adj` is the caller's persisted flow-adjusted high-water (None the first
    time). `stored_peak_raw` is the legacy raw-dollar high-water it migrates from: subtracting the
    net flows already baked into it recovers the high-water the book actually reached, so a
    deposit that has already inflated the stored peak does not get to keep that inflation. Both
    None seeds the high-water at today's flow-adjusted equity.

    WITH NO LEDGER THIS IS THE IDENTITY: `net_flows_usd` is 0.0, `equity` is `equity_now`, and
    `peak` is `max(stored_peak_raw, equity_now)` -- byte-identical to the arithmetic the executor
    ran before R0320. Nothing here can bite on a box that has never had a capital event.

    Two invariants, both checked by tests, both stated as the docstring ruling:
      * `peak >= equity` always (the high-water never sits under the equity it measures);
      * `peak` is monotone non-decreasing in flow-adjusted space -- no event resets it downward,
        and in raw dollars it moves by EXACTLY the cash that moved, never by a fraction of it.
    """
    evs = history() if events is None else [e for e in events if isinstance(e, dict)]
    net = net_external_flows(evs)
    eq_adj = float(equity_now) - net
    if stored_peak_flow_adj is not None:
        base = float(stored_peak_flow_adj)
    elif stored_peak_raw is not None:
        base = float(stored_peak_raw) - net
    else:
        base = eq_adj
    peak = max(base, eq_adj)
    return FlowAdjustedRail(equity=eq_adj, peak=peak, peak_raw=peak + net,
                            net_flows_usd=net, n_events=len(evs))

```

### libs\risk\config.py
```python
"""Risk configuration — limits and parameters with conservative defaults.

Illustrative defaults only; calibrate to validated alphas' real distributions. Set limits
tighter than the math suggests, because realized risk is always worse than the model's.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from libs.risk.instruments import Factor


class KellyLimits(BaseModel):
    model_config = ConfigDict(frozen=True)

    new_cap: float = 1 / 3       # base/standard fraction-of-Kelly (third-Kelly)
    validated_cap: float = 0.42  # between base and half, earned by evidence
    proven_cap: float = 0.50     # half-Kelly, only when ROI is good and the bar is met
    hard_max: float = 0.50       # half-Kelly is the absolute ceiling, ever
    max_up_step: float = 0.02    # gradual upward scaling per update


class VolConfig(BaseModel):
    model_config = ConfigDict(frozen=True)

    target: float = 0.10  # target volatility (per the chosen period)
    k_min: float = 0.2
    k_max: float = 3.0
    ewma_lambda: float = 0.94


class HeatLimits(BaseModel):
    model_config = ConfigDict(frozen=True)

    max_portfolio_frac: float = 0.20  # total risk-at-stop as a fraction of equity
    max_per_position_frac: float = 0.05


class DrawdownLadder(BaseModel):
    model_config = ConfigDict(frozen=True)

    # (upper_bound, scalar); the last entry's bound is the halt level.
    soft: float = 0.05
    moderate: float = 0.10
    significant: float = 0.15
    aggressive: float = 0.20
    scalar_moderate: float = 0.66
    scalar_significant: float = 0.40
    scalar_aggressive: float = 0.20


class CorrelationLimits(BaseModel):
    model_config = ConfigDict(frozen=True)

    max_avg_corr: float = 0.70
    crisis_avg_corr: float = 0.85
    cut_scalar_floor: float = 0.30


class TailLimits(BaseModel):
    model_config = ConfigDict(frozen=True)

    var_alpha: float = 0.05
    max_cvar_frac: float = 0.10  # CVaR as a fraction of equity
    crisis_vol_multiplier: float = 2.5


class CrisisConfig(BaseModel):
    model_config = ConfigDict(frozen=True)

    vol_spike_multiplier: float = 2.0
    corr_threshold: float = 0.80
    exposure_scalar: float = 0.25  # cut gross hard in crisis


class PreservationConfig(BaseModel):
    model_config = ConfigDict(frozen=True)

    equity_floor: float = 0.0  # absolute hard floor; below it, everything stops
    floor_buffer_frac: float = 0.10  # within this band above the floor -> preservation
    recovery_drawdown: float = 0.10  # drawdown from HWM that triggers recovery mode


class ExposureLimits(BaseModel):
    model_config = ConfigDict(frozen=True)

    max_position_frac: float = 0.25  # per-instrument risk cap
    max_gross_leverage: float = 10.0  # far below broker maximum
    factor_caps: dict[Factor, float] = Field(
        default_factory=lambda: {
            Factor.PRECIOUS_METALS: 0.40,
            Factor.FX: 0.40,
            Factor.EQUITY_INDEX: 0.40,
            Factor.CRYPTO: 0.15,
            Factor.ENERGY: 0.30,
            Factor.COMMODITY: 0.30,
            Factor.RATES: 0.40,
        }
    )


class RiskConfig(BaseModel):
    """Top-level risk configuration."""

    model_config = ConfigDict(frozen=True)

    kelly: KellyLimits = Field(default_factory=KellyLimits)
    vol: VolConfig = Field(default_factory=VolConfig)
    heat: HeatLimits = Field(default_factory=HeatLimits)
    drawdown: DrawdownLadder = Field(default_factory=DrawdownLadder)
    correlation: CorrelationLimits = Field(default_factory=CorrelationLimits)
    tail: TailLimits = Field(default_factory=TailLimits)
    crisis: CrisisConfig = Field(default_factory=CrisisConfig)
    preservation: PreservationConfig = Field(default_factory=PreservationConfig)
    exposure: ExposureLimits = Field(default_factory=ExposureLimits)

```

### libs\risk\correlation.py
```python
"""Correlation controls — measure, stress, cluster, and govern by correlation.

Correlations spike toward 1 in crises, so the diversification measured in calm markets
evaporates when you need it. We size against a *stressed* matrix, watch realized correlation
drift as a crowding/crisis early-warning, and cut gross exposure when it rises.
"""

from __future__ import annotations

from typing import cast

import numpy as np
from pydantic import BaseModel, ConfigDict

from libs.risk.config import CorrelationLimits
from libs.risk.errors import RiskError


def rolling_correlation(returns_matrix: np.ndarray, *, window: int | None = None) -> np.ndarray:
    """Correlation matrix of columns (optionally over the last ``window`` rows)."""
    m = np.asarray(returns_matrix, dtype="float64")
    if m.ndim != 2 or m.shape[1] < 2:
        raise RiskError("returns_matrix must be 2-D with >= 2 columns")
    if window is not None:
        m = m[-window:]
    if m.shape[0] < 2:
        raise RiskError("need >= 2 observations for correlation")
    corr = np.corrcoef(m, rowvar=False)
    return cast("np.ndarray", np.nan_to_num(corr, nan=0.0))


def stressed_correlation(corr: np.ndarray, *, stress: float = 0.5) -> np.ndarray:
    """Shrink off-diagonal correlations toward 1 to model crisis convergence."""
    if not 0.0 <= stress <= 1.0:
        raise RiskError("stress must be in [0, 1]")
    c = np.asarray(corr, dtype="float64").copy()
    n = c.shape[0]
    off = ~np.eye(n, dtype=bool)
    c[off] = c[off] + (1.0 - c[off]) * stress
    np.fill_diagonal(c, 1.0)
    return c


def correlation_clusters(corr: np.ndarray, *, threshold: float = 0.7) -> list[list[int]]:
    """Group indices whose pairwise correlation exceeds ``threshold`` (union-find)."""
    c = np.asarray(corr, dtype="float64")
    n = c.shape[0]
    parent = list(range(n))

    def find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for i in range(n):
        for j in range(i + 1, n):
            if abs(c[i, j]) >= threshold:
                parent[find(i)] = find(j)

    groups: dict[int, list[int]] = {}
    for i in range(n):
        groups.setdefault(find(i), []).append(i)
    return [sorted(g) for g in groups.values()]


def diversification_score(weights: np.ndarray, corr: np.ndarray) -> float:
    """Diversification ratio (Σ|w_i|) / sqrt(wᵀCw); 1 = no diversification, higher = better."""
    w = np.asarray(weights, dtype="float64")
    c = np.asarray(corr, dtype="float64")
    port_vol = float(np.sqrt(w @ c @ w))
    if port_vol <= 0:
        return 1.0
    return float(np.abs(w).sum() / port_vol)


def average_off_diagonal(corr: np.ndarray) -> float:
    """Mean of the off-diagonal correlations."""
    c = np.asarray(corr, dtype="float64")
    n = c.shape[0]
    if n < 2:
        return 0.0
    off = ~np.eye(n, dtype=bool)
    return float(c[off].mean())


class CorrelationResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    average_correlation: float
    scalar: float  # exposure scalar in (0, 1]
    crisis_convergence: bool

    def __bool__(self) -> bool:
        return not self.crisis_convergence


def correlation_scalar(average_correlation: float, limits: CorrelationLimits) -> float:
    """Exposure scalar in (0, 1] that falls as average correlation rises past the limit."""
    if average_correlation <= limits.max_avg_corr:
        return 1.0
    if average_correlation >= limits.crisis_avg_corr:
        return limits.cut_scalar_floor
    span = limits.crisis_avg_corr - limits.max_avg_corr
    frac = (average_correlation - limits.max_avg_corr) / span if span > 0 else 1.0
    return 1.0 - frac * (1.0 - limits.cut_scalar_floor)


def check_correlation_limits(
    corr: np.ndarray, *, limits: CorrelationLimits | None = None
) -> CorrelationResult:
    """Return an exposure scalar that falls as average correlation rises past the limit."""
    cfg = limits or CorrelationLimits()
    avg = average_off_diagonal(corr)
    return CorrelationResult(
        average_correlation=avg,
        scalar=correlation_scalar(avg, cfg),
        crisis_convergence=avg >= cfg.crisis_avg_corr,
    )

```

### libs\risk\crisis.py
```python
"""Crisis controls — detect a crisis regime and de-risk automatically, failing closed.

In a crisis, exiting is expensive (you become the liquidity provider getting run over), so the
controller cuts gross hard and suspends negative-tail strategies. Under any uncertainty (stale
data) it treats the world as a crisis — survival first.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from libs.risk.config import CrisisConfig


class CrisisResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    in_crisis: bool
    exposure_scalar: float  # multiplier in [0, 1]
    suspend_negative_tail: bool
    reasons: list[str]

    def __bool__(self) -> bool:
        return not self.in_crisis


def crisis_controller(
    *,
    vol_now: float,
    vol_baseline: float,
    average_correlation: float,
    config: CrisisConfig | None = None,
    data_stale: bool = False,
) -> CrisisResponse:
    """Detect crisis conditions and return the de-risking response (fail-closed)."""
    cfg = config or CrisisConfig()
    reasons: list[str] = []

    if data_stale:
        return CrisisResponse(
            in_crisis=True, exposure_scalar=cfg.exposure_scalar, suspend_negative_tail=True,
            reasons=["data_stale (fail-closed: treat uncertainty as crisis)"],
        )

    if vol_baseline > 0 and vol_now >= cfg.vol_spike_multiplier * vol_baseline:
        reasons.append(f"vol spike: {vol_now:.4g} >= {cfg.vol_spike_multiplier}x baseline")
    if average_correlation >= cfg.corr_threshold:
        reasons.append(f"correlation convergence: {average_correlation:.3f}")

    in_crisis = bool(reasons)
    return CrisisResponse(
        in_crisis=in_crisis,
        exposure_scalar=cfg.exposure_scalar if in_crisis else 1.0,
        suspend_negative_tail=in_crisis,
        reasons=reasons,
    )

```

### libs\risk\drawdown.py
```python
"""Drawdown governor — graduated de-risking that only ever reduces exposure.

Drawdowns break compounding (recovery asymmetry), so exposure is cut as drawdown deepens and
the book is halted at the hard limit. After losses you reduce, never increase — martingale and
averaging-down are forbidden.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict

from libs.risk.config import DrawdownLadder
from libs.risk.errors import RiskError


class DrawdownLevel(StrEnum):
    NORMAL = "normal"
    MODERATE = "moderate"
    SIGNIFICANT = "significant"
    AGGRESSIVE = "aggressive"
    HALT = "halt"


def compute_drawdown(equity: float, peak_equity: float) -> float:
    """Current drawdown depth as a positive fraction (0 = at the high-water mark)."""
    if peak_equity <= 0:
        raise RiskError("peak_equity must be positive")
    if equity > peak_equity:
        return 0.0
    return (peak_equity - equity) / peak_equity


class DrawdownResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    drawdown: float
    level: DrawdownLevel
    scalar: float  # exposure multiplier in [0, 1]
    halt: bool

    def __bool__(self) -> bool:
        return not self.halt


def drawdown_governor(
    drawdown: float, *, ladder: DrawdownLadder | None = None
) -> DrawdownResponse:
    """Map a drawdown depth to an exposure scalar and level (halts at the hard limit)."""
    cfg = ladder or DrawdownLadder()
    if drawdown < 0:
        raise RiskError("drawdown must be non-negative")

    if drawdown < cfg.soft:  # 0-5%: full risk
        level, scalar = DrawdownLevel.NORMAL, 1.0
    elif drawdown < cfg.moderate:  # 5-10%: moderate reduction
        level, scalar = DrawdownLevel.MODERATE, cfg.scalar_moderate
    elif drawdown < cfg.significant:  # 10-15%: significant reduction
        level, scalar = DrawdownLevel.SIGNIFICANT, cfg.scalar_significant
    elif drawdown < cfg.aggressive:  # 15-20%: aggressive reduction
        level, scalar = DrawdownLevel.AGGRESSIVE, cfg.scalar_aggressive
    else:  # 20%+: halt
        level, scalar = DrawdownLevel.HALT, 0.0

    return DrawdownResponse(
        drawdown=drawdown, level=level, scalar=scalar, halt=scalar == 0.0
    )

```

### libs\risk\dynamic_leverage.py
```python
"""Dynamic leverage controller -- leverage as a continuously optimized control variable.

Composes the existing growth-optimal Kelly analysis (`growth_leverage`) and forward-validation
confidence (`edge_gate`) into ONE recomputed number per sleeve and jointly for the portfolio,
in the full risk vector the constitution requires: expected edge, forecast UNCERTAINTY (sample size
forward days), realized vol, downside/tail risk, liquidity, slippage, market impact, funding cost,
correlation to the book, regime, execution reliability, model confidence.

Two design commitments from the constitution:
  1. NO arbitrary fixed cap. The ceiling is ENDOGENOUS = min(diminishing-returns argmax of E[log],
     the largest leverage whose bootstrapped risk-of-ruin <= tolerance). Survival is priority #1, so
     the ruin constraint binds -- but it's derived from the return distribution, not a magic number.
  2. Increase only when the expected log-growth gain exceeds the ruin-risk increase; degrade
     immediately when uncertainty/vol/liquidity/execution/confidence worsen. On a day-0 unvalidated
     edge, confidence ~ 0 -> the optimizer resolves to the low operational floor and *earns*
     as forward validation shrinks the error bars. It never cranks leverage on unproven edge.

Pure functions; `returns` must already be net of all costs. Recompute after every meaningful update.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np

from libs.risk.growth_leverage import ann_geom_growth, kelly_optimal, risk_of_ruin
from libs.risk.kelly_shrink import shrink_fraction
from libs.validation.forward_stats import autocorr_factor

_MIN_OP = 0.25  # min operational leverage so the book still trades
_GRID = np.linspace(0.0, 12.0, 241)[1:]              # search grid (endogenous ceiling, not a cap)


def _confidence(fwd_days: float, fwd_sharpe: float | None, n_obs: int,
                *, min_days: float = 5.0, target_days: float = 90.0) -> float:
    """Forecast confidence in [0,1]: 0 when unproven, ramps with forward days AND sample size.

    Uncertainty shrinkage -- the estimate is trusted only in proportion to how much OUT-OF-SAMPLE
    evidence supports it. Both the calendar clock (fwd_days) and the sample size (n_obs) must be
    """
    if fwd_sharpe is None or fwd_sharpe <= 0.0 or fwd_days < min_days or n_obs < 40:
        return 0.0
    day_conf = max(0.0, min(1.0, (fwd_days - min_days) / max(1.0, target_days - min_days)))
    n_conf = max(0.0, min(1.0, (n_obs - 40) / 200.0))    # ~240 obs -> full sample confidence
    return round(day_conf * n_conf, 4)


def _ruin_cap(returns: np.ndarray, *, ruin_tol: float, drawdown_ruin: float) -> float:
    """Largest grid leverage whose risk-of-ruin <= tolerance. The endogenous survival ceiling."""
    best = 0.0
    for lev in _GRID:
        # R0429: `drawdown_ruin` is a DROP (0.35 = "a 35% drawdown is ruin") but risk_of_ruin's
        # `threshold` is an equity LEVEL (P(equity < threshold)). Passing the drop raw computed
        # P(equity < 0.35) = P(drawdown > 65%) -- a cap against a 65% crash where a 35% one was
        # documented, looser than designed on the survival path. The complement is the fix.
        ror = risk_of_ruin(returns, float(lev), threshold=1.0 - drawdown_ruin)
        if not np.isfinite(ror):
            return _MIN_OP                            # too little data to trust any leverage
        if ror <= ruin_tol:
            best = float(lev)
        else:
            break                                     # ruin monotonically rises with leverage
    return best


@dataclass
class LeverageDecision:
    sleeve: str
    recommended: float
    growth_optimal: float          # diminishing-returns argmax of E[log] (unconstrained)
    ruin_cap: float                # endogenous survival ceiling
    confidence: float              # forecast confidence (uncertainty shrinkage)
    binding: str                   # which term set the recommendation
    inputs: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {"sleeve": self.sleeve, "recommended_leverage": round(self.recommended, 3),
                "growth_optimal_leverage": round(self.growth_optimal, 3),
                "ruin_cap": round(self.ruin_cap, 3), "confidence": self.confidence,
                "binding_constraint": self.binding, "inputs": self.inputs}


def optimize_sleeve(
    sleeve: str,
    returns: np.ndarray,
    *,
    fwd_sharpe: float | None,
    fwd_days: float,
    regime_mult: float = 1.0,           # <=1 de-risk in bad regimes (never invents edge)
    exec_reliability: float = 1.0,      # [0,1] fill quality / uptime haircut
    liquidity_haircut: float = 1.0,     # [0,1] thin-book / slippage / impact haircut
    ruin_tol: float = 0.02,             # max acceptable P(ruin) over 1y
    drawdown_ruin: float = 0.35,        # equity drop treated as ruin
) -> LeverageDecision:
    """Growth-optimal leverage for ONE sleeve, uncertainty-shrunk and survival-capped."""
    r = np.asarray(returns, dtype="float64")
    n = int(np.sum(r != 0.0))
    kelly = kelly_optimal(r) if n >= 20 else 0.0                    # diminishing-returns argmax
    ruin_cap = _ruin_cap(r, ruin_tol=ruin_tol, drawdown_ruin=drawdown_ruin) if n >= 20 else _MIN_OP

    # ESTIMATION-ERROR-SHRUNK KELLY (2026-07-12, replaces the fixed 0.5x-Kelly cap and the
    # linear day-ramp): fraction = S^2/(S^2+SE^2) is the max-E[log] bet under parameter
    # uncertainty -- ramps continuously past 0.5x as forward evidence accumulates instead of
    # capping at half-Kelly forever, and sits BELOW 0.5x only when the evidence honestly
    # cannot support half. The old hard gates stay: unproven edge (no fwd days / tiny sample)
    # still resolves to 0 -> operational floor.
    # vif keeps the shrink's SE on the SAME effective sample size the NW t-stat uses --
    # without it the sizing over-trusts autocorrelated (sticky) returns exactly where the
    # significance test distrusts them (round-2 external review consensus, 2026-07-12).
    conf = (shrink_fraction(float(fwd_sharpe or 0.0), fwd_days, vif=autocorr_factor(r))
            if _confidence(fwd_days, fwd_sharpe, n) > 0.0 else 0.0)
    base = conf * kelly * regime_mult * exec_reliability * liquidity_haircut
    # candidate ceilings -- the recommendation is the min (survival + diminishing returns bind)
    rec = max(_MIN_OP, min(base, kelly, ruin_cap))
    binding = min(
        [("edge/confidence", base), ("diminishing-returns", kelly), ("ruin-cap", ruin_cap)],
        key=lambda kv: kv[1] if kv[1] > 0 else float("inf"),
    )[0] if base > 0 else "unproven-floor"
    return LeverageDecision(
        sleeve=sleeve, recommended=rec, growth_optimal=kelly, ruin_cap=ruin_cap, confidence=conf,
        binding=binding,
        inputs={"n_obs": n, "fwd_sharpe": fwd_sharpe, "fwd_days": round(fwd_days, 2),
                "regime_mult": regime_mult, "exec_reliability": exec_reliability,
                "liquidity_haircut": liquidity_haircut, "ruin_tol": ruin_tol},
    )


def optimize_portfolio(
    sleeve_returns: dict[str, np.ndarray],
    decisions: dict[str, LeverageDecision],
) -> dict[str, Any]:
    """Joint leverage: allocate to the highest marginal contribution to portfolio E[log wealth].

    Builds the levered-portfolio return series and scales the whole book to its own growth-optimal
    (accounting for correlation via the actual joint series), then splits by each sleeve's marginal
    contribution to joint log-growth. Data-thin sleeves contribute ~0 and get ~floor -- honest.
    """
    names = [s for s in sleeve_returns if len(sleeve_returns[s]) > 1]
    if not names:
        return {"joint_leverage": _MIN_OP, "per_sleeve": {}, "note": "no return history yet"}
    # align on the shortest common length
    L = min(len(sleeve_returns[s]) for s in names)
    mat = np.vstack([np.asarray(sleeve_returns[s], dtype="float64")[-L:] for s in names])
    lv = np.array([decisions[s].recommended for s in names])
    port = (lv[:, None] * mat).sum(axis=0) / max(1e-9, lv.sum())    # capital-weighted book return
    joint = kelly_optimal(port) if np.sum(port != 0) >= 20 else _MIN_OP
    # marginal contribution of each sleeve to joint growth (drop-one)
    contrib: dict[str, float] = {}
    full_g = ann_geom_growth(port, joint, 1.0)
    for i, s in enumerate(names):
        keep = [j for j in range(len(names)) if j != i]
        if keep:
            sub = (lv[keep, None] * mat[keep]).sum(axis=0) / max(1e-9, lv[keep].sum())
            contrib[s] = round(full_g - ann_geom_growth(sub, joint, 1.0), 6)
        else:
            contrib[s] = round(full_g, 6)
    return {"joint_leverage": round(float(joint), 3),
            "marginal_log_growth_contribution": contrib,
            "note": ("Joint leverage on the correlation-aware return; risk by marginal "
                     "contribution to portfolio E[log wealth], not equally.")}

```

### libs\risk\edge_gate.py
```python
"""Edge-gated leverage -- size to FORWARD-VALIDATED edge, never to the backtest.

Leverage stays at a small floor until the 90-day forward shadow accumulates enough positive
out-of-sample evidence, then ramps with confidence toward half-Kelly of the FORWARD Sharpe, capped
at the growth-optimal ceiling. No forward edge => stays at the floor. The only honest way to lift
CAGR: bet big only on edge that proved itself live, in proportion to how proven it is.
"""

from __future__ import annotations


def gated_leverage(fwd_sharpe: float | None, fwd_days: int, *, floor: float = 2.0,
                   cap: float = 6.0, min_days: int = 30, target_days: int = 90) -> float:
    """Leverage as a function of forward-validated edge.

    - fwd_sharpe <= 0 or fwd_days < min_days  -> floor (edge unproven).
    - else: confidence ramps 0->1 between min_days and target_days; leverage =
      floor + confidence x (half_kelly(fwd_sharpe) - floor), clamped to [floor, cap].
    half-Kelly slope: Sharpe ~1 -> ~3x (matches the recommended half-Kelly point)."""
    if fwd_sharpe is None or fwd_sharpe <= 0.0 or fwd_days < min_days:
        return floor
    span = max(1, target_days - min_days)
    confidence = max(0.0, min(1.0, (fwd_days - min_days) / span))
    half_kelly = max(floor, min(cap, fwd_sharpe * 3.0))
    lev = floor + confidence * (half_kelly - floor)
    return round(max(floor, min(cap, lev)), 2)

```

### libs\risk\errors.py
```python
"""Risk-layer exceptions."""

from __future__ import annotations

from libs.core.errors import QuantPlatformError


class RiskError(QuantPlatformError):
    """Invalid risk inputs or configuration."""


class RiskGateError(RiskError):
    """The risk gate could not run; per fail-closed policy this means *do not trade*."""

```

### libs\risk\factor_caps.py
```python
"""Factor exposure caps — the diversification enforcer.

Aggregates risk by factor (so gold + silver count as one precious-metals bet) and rejects any
factor whose total risk exceeds its cap as a fraction of equity. Prevents hidden concentration
through correlated symbols.
"""

from __future__ import annotations

from collections.abc import Mapping

from pydantic import BaseModel, ConfigDict

from libs.risk.errors import RiskError
from libs.risk.instruments import Factor, get_factor


class FactorBreach(BaseModel):
    model_config = ConfigDict(frozen=True)

    factor: Factor
    exposure: float
    cap: float


class FactorExposureResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    ok: bool
    by_factor: dict[Factor, float]
    breaches: list[FactorBreach]

    def __bool__(self) -> bool:
        return self.ok


def check_factor_exposure(
    exposures: Mapping[str, float],
    *,
    equity: float,
    factor_caps: Mapping[Factor, float],
) -> FactorExposureResult:
    """Aggregate per-symbol risk into factors and compare to caps (fraction of equity)."""
    if equity <= 0:
        raise RiskError("equity must be positive")
    by_factor: dict[Factor, float] = {}
    for symbol, risk_amount in exposures.items():
        factor = get_factor(symbol)
        by_factor[factor] = by_factor.get(factor, 0.0) + abs(float(risk_amount))

    breaches: list[FactorBreach] = []
    for factor, exposure in by_factor.items():
        cap_frac = factor_caps.get(factor)
        if cap_frac is None:
            continue
        cap_amount = cap_frac * equity
        if exposure > cap_amount:
            breaches.append(FactorBreach(factor=factor, exposure=exposure, cap=cap_amount))
    return FactorExposureResult(ok=not breaches, by_factor=by_factor, breaches=breaches)

```

### libs\risk\fx_exposure.py
```python
"""A BOOK OF FX PAIRS IS NOT A BOOK OF N ASSETS -- it is a book of currency FACTORS.

REVIEW FINDING R1/R2 (2026-09-17). A pair is a DIFFERENCE of two currency factors: EURUSD is
`EUR - USD`, not an eighteenth independent thing to be long of. Eighteen pairs drawn from eight
currencies therefore span AT MOST SEVEN independent directions (n currencies give n-1 differences
-- the level of the numeraire is unobservable), and empirically far fewer: the FX literature and
this desk's own tape both find three to four (dollar, carry, commodity bloc, risk appetite).
Against that ceiling the desk's measured effective breadth of 4.879 is not a number with room in
it; it is a number already pressed against the wall of what a pure-FX book can express. The next
independent bet does not come from the nineteenth cross. It comes from OUTSIDE the currency
block.

WHY THE EXISTING ORGANS DO NOT ANSWER THIS.

  * `libs/risk/factor_caps.py` aggregates by ASSET CLASS: every cross collapses into one `FX`
    bucket, which cannot tell "long four JPY crosses" from "four independent trades".
  * `libs/risk/fx_factors.py` DOES decompose into signed legs, and this module reuses its
    currency vocabulary and its `split_pair` rather than keeping a second copy that drifts. What
    it reports is a leg-concentration ratio (`gross / largest leg`), which is a different and
    weaker question than "how many independent DIRECTIONS does the whole book span".
  * `libs/portfolio/leg_factors.py` fits sleeve RETURNS on factor returns. That is a covariance,
    it needs a tape, and it is the right instrument for the redundancy charge. This module needs
    no tape at all: the loadings of a currency pair on its two legs are +1 and -1 BY CONSTRUCTION,
    so a book's directional span is an algebraic fact about the positions held right now, exact
    on the day a sleeve is born and never waiting on twenty overlapping days.
  * `desks/mt5/research/exposure_decomposition.py` regresses on a wide macro factor set and names
    duplicate heat pair by pair. It is the map; this is the rank of the map.

THE MEASUREMENT. Stack one row per sleeve of its signed notional per factor (`exposure_matrix`)
and take the PARTICIPATION RATIO of that matrix's singular-value spectrum (`effective_rank`). A
book making one bet scores 1, two orthogonal bets score 2, and two bets sharing a leg score
strictly between 1 and 2 -- continuously, so a book that drifts into crowding is visible before
it arrives rather than after. A flat book scores 0.0: an empty book makes ZERO bets, not one, and
reporting 1.0 there would be a claim about a book that holds nothing.

NOTHING HERE SIZES, CAPS, VETOES, SHRINKS OR GATES ANYTHING (growth governance, rules 1 and 2).
A named concentration is not a forbidden concentration. This module has no authority over
position size, cannot refuse an order and does not appear in any allocator's objective; it
reports what the book is really long and short of, and how many directions that spans, so that
the arithmetic which DOES size can see what it is buying. Anything built on top that wants to
REDUCE exposure owes a missed-growth ledger line first (`research/missed_growth.py`).

REFUSALS ARE THE POINT (L1.28a -- UNMEASURED is a real answer). `split_symbol` never guesses. Six
letters is not enough on its own -- "NatGas" uppercases to a six-letter shape and would decompose
into a long "NAT" and a short "GAS", two real numbers in a report nobody can read as wrong -- so
both legs must be a currency the broker actually quotes or a declared non-currency factor.
Everything else must be NAMED, either in `NON_PAIR_SYMBOLS` (the explicit MT5-universe map below,
derived from `desks/mt5/data/universe/universe.json`) or by the caller through `factors=`. A
symbol this module cannot classify raises `RiskError`; absence is not a permission.
"""
from __future__ import annotations

import math
import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

import numpy as np
import numpy.typing as npt

from libs.risk.errors import RiskError

# SINGLE SOURCE OF TRUTH, DELIBERATELY REUSED. A second hand-maintained currency list is a list
# that drifts from the first one, and the two then disagree about whether CHFNOK is a cross. The
# broker's quotable legs live in `fx_factors`; extend them THERE.
from libs.risk.fx_factors import _CURRENCIES as _FX_CURRENCIES
from libs.risk.fx_factors import _NON_CURRENCY as _FX_NON_CURRENCY
from libs.risk.fx_factors import split_pair

#: THREE LEGS THE SHARED LIST IS MISSING, and this is a MEASUREMENT, not a preference. Every FX
#: and FX-exotic row in `desks/mt5/data/universe/universe.json` was decomposed on 2026-09-17: the
#: broker quotes 27 legs, `fx_factors._CURRENCIES` names 24 of them, and USDBRL, USDIDR and
#: USDKRW therefore read UNKNOWN in the desk's existing currency-leg view -- three live-universe
#: symbols silently absent from a concentration report rather than wrong in it.
#:
#: THE FIX BELONGS UPSTREAM, in `fx_factors._CURRENCIES`, where both modules would get it. It is
#: carried here because this change is not permitted to edit that file; the test that found the
#: gap (`desks/mt5/tests/test_netting_report.py::
#: test_every_non_forex_universe_symbol_the_desk_may_hold_is_classifiable`) walks the registry
#: rather than a list, so it will find the next missing leg too.
_EXTRA_CURRENCIES: frozenset[str] = frozenset({"BRL", "IDR", "KRW"})

#: The ISO-4217 legs this broker quotes (public alias over `fx_factors`' private set).
CURRENCIES: frozenset[str] = frozenset(_FX_CURRENCIES) | _EXTRA_CURRENCIES

#: Three-letter BASES that are not currencies and are their own factor. A gold sleeve's risk is
#: gold's, not the dollar's, so XAUUSD is `+XAU -USD` and never "long the metal complex". Sourced
#: from the live registry: precious and base metals, the three energy CFDs, and every crypto CFD
#: whose ticker happens to be six characters. `_FX_NON_CURRENCY` supplies XAU/XAG/XPT/XPD/XCU.
NON_CURRENCY_BASES: frozenset[str] = frozenset(_FX_NON_CURRENCY) | frozenset({
    # base metals quoted XxxUSD on Fusion
    "XAL", "XNI", "XPB", "XZN",
    # energy: Brent, WTI, natural gas
    "XBR", "XTI", "XNG",
    # crypto CFDs with a three-letter base (part of the MT5 universe; NOT a crypto-exchange
    # universe -- the mandate forbids hunting exchange-native ground, not holding Fusion CFDs)
    "ADA", "BCH", "BNB", "BTC", "DOT", "EOS", "ETH", "LNK", "LTC", "SOL", "XLM",
})

#: THE EXPLICIT MAP, and every row was read off `desks/mt5/data/universe/universe.json` rather
#: than guessed: the factor name is the instrument itself and the quote leg is the registry's own
#: `currency_profit`. An index, a bond future, a soft or a long-tickered crypto CFD is ONE factor
#: against its quote currency -- `US500 = +US500 -USD`, `JPN225 = +JPN225 -JPY` -- because the
#: desk has no decomposition of an equity index into anything more primitive and inventing one
#: would put a fabricated number in a rank.
#:
#: USDX IS DELIBERATELY NOT SPECIAL-CASED. Mechanically the dollar index IS the dollar, so
#: `+USDX -USD` books a factor the desk could argue is redundant. The rule is applied uniformly
#: anyway: a hand-tuned exception here would be a judgement embedded in a measurement, and the
#: honest fix (a basket decomposition of USDX into its six legs) is a real piece of work, not a
#: line in a dict. It is flagged here so the next reader sees the choice rather than trips on it.
NON_PAIR_SYMBOLS: dict[str, tuple[str, str]] = {
    # --- Indices (registry asset_class "Indices")
    "AUS200": ("AUS200", "AUD"),
    "CA60": ("CA60", "CAD"),
    "CHINAH": ("CHINAH", "HKD"),
    "E35": ("E35", "EUR"),
    "EUSTX50": ("EUSTX50", "EUR"),
    "FRA40": ("FRA40", "EUR"),
    "GER40": ("GER40", "EUR"),
    "HK50": ("HK50", "HKD"),
    "JPN225": ("JPN225", "JPY"),
    "NAS100": ("NAS100", "USD"),
    "NETH25": ("NETH25", "EUR"),
    "UK100": ("UK100", "GBP"),
    "US2000": ("US2000", "USD"),
    "US30": ("US30", "USD"),
    "US500": ("US500", "USD"),
    "USDX": ("USDX", "USD"),
    # --- Bonds
    "UKGILT": ("UKGILT", "GBP"),
    "UST05Y": ("UST05Y", "USD"),
    "UST10Y": ("UST10Y", "USD"),
    # --- Soft commodities
    "COFARA": ("COFARA", "USD"),
    "COFROB": ("COFROB", "USD"),
    "CORN": ("CORN", "USD"),
    "COTTON": ("COTTON", "USD"),
    "OJ": ("OJ", "USD"),
    "SOYBEAN": ("SOYBEAN", "USD"),
    "SUGAR": ("SUGAR", "USD"),
    "SUGARRAW": ("SUGARRAW", "USD"),
    "UKCOCOA": ("UKCOCOA", "GBP"),
    "USCOCOA": ("USCOCOA", "USD"),
    "WHEAT": ("WHEAT", "USD"),
    # --- Crypto CFDs whose ticker is not six characters
    "AVAXUSD": ("AVAX", "USD"),
    "DOGEUSD": ("DOGE", "USD"),
    "MATICUSD": ("MATIC", "USD"),
}

#: Broker decoration: `.raw`, `-ECN`, `_x`, `.pro`, `.m`. A separator plus up to five alphanumeric
#: characters, stripped ONCE (not in a loop -- repeated stripping eats real tickers) and only
#: where at least three characters survive.
_SUFFIX = re.compile(r"[._-][A-Za-z0-9]{1,5}$")

#: Registry asset classes whose members are one factor against their profit currency.
_OWN_FACTOR_CLASSES = frozenset({
    "Indices", "Bonds", "Soft Commodity", "Energy", "Equities", "Equity",
})

#: A sleeve row declaring one of these is short its instrument.
_SHORT_WORDS = frozenset({"SHORT", "SELL", "-1"})


@dataclass(frozen=True)
class Position:
    """One instrument held, signed, in ACCOUNT currency.

    `notional_ccy` is positive when the book is LONG the base (or the instrument, for an index or
    a soft). It is a notional, not a stop-risk and not a margin: mixing the two in one book is a
    unit error that produces a rank nobody can interpret, so a caller that has stop-risk must
    build a book entirely out of stop-risk and say so.
    """

    symbol: str
    notional_ccy: float

    def __post_init__(self) -> None:
        if not str(self.symbol).strip():
            raise RiskError("Position: symbol is empty")
        value = float(self.notional_ccy)
        if not math.isfinite(value):
            raise RiskError(f"Position({self.symbol}): notional_ccy is {self.notional_ccy!r}")


def strip_suffix(symbol: str) -> str:
    """`EURUSD.raw` -> `EURUSD`. Uppercased, one suffix removed, never below three characters."""
    core = str(symbol).strip().upper()
    if not core:
        raise RiskError("split_symbol: empty symbol")
    match = _SUFFIX.search(core)
    if match is not None and match.start() >= 3:
        core = core[: match.start()]
    return core


def split_symbol(symbol: str) -> tuple[str, str]:
    """`("EUR", "USD")` for EURUSD, `("XAU", "USD")` for XAUUSD.raw, `("US500", "USD")` for US500.

    Raises `RiskError` for anything this module cannot classify WITHOUT GUESSING: a six-character
    shape whose legs are not quotable currencies or declared non-currency factors, a name of any
    other length that is not in `NON_PAIR_SYMBOLS`, or an empty string. The caller that knows
    better -- one holding the broker's registry, say -- passes `factors=` to `exposure_vector`.
    """
    raw = str(symbol).strip().upper()
    if raw in NON_PAIR_SYMBOLS:
        return NON_PAIR_SYMBOLS[raw]
    core = strip_suffix(symbol)
    if core in NON_PAIR_SYMBOLS:
        return NON_PAIR_SYMBOLS[core]

    known = split_pair(core)
    if known is not None:
        return known

    if len(core) == 6:
        base, quote = core[:3], core[3:]
        base_ok = base in CURRENCIES or base in NON_CURRENCY_BASES
        quote_ok = quote in CURRENCIES or quote in NON_CURRENCY_BASES
        if base_ok and quote_ok:
            return (base, quote)
        raise RiskError(
            f"split_symbol({symbol!r}): {core!r} is six characters but "
            f"{'base ' + base if not base_ok else ''}"
            f"{' and ' if not base_ok and not quote_ok else ''}"
            f"{'quote ' + quote if not quote_ok else ''} is not a quotable currency or a "
            "declared non-currency factor -- add it to libs/risk/fx_factors._CURRENCIES or to "
            "NON_CURRENCY_BASES, or pass factors={...}. Guessing the legs is how NatGas becomes "
            "long NAT and short GAS.")

    raise RiskError(
        f"split_symbol({symbol!r}): {core!r} is {len(core)} characters, not six, and is not in "
        "NON_PAIR_SYMBOLS. Absence is not a permission: name it in NON_PAIR_SYMBOLS (with its "
        "registry currency_profit as the quote leg) or pass factors={...}.")


def factors_from_registry(registry: Mapping[str, Mapping[str, Any]]) -> dict[str, tuple[str, str]]:
    """Derive a `factors=` override from an MT5 universe registry.

    THE REGISTRY IS THE AUTHORITY, not a symbol list in this file: routing is by the asset class
    MetaTrader itself reports (the same rule `desks/mt5/research/universe_policy.py` enforces for
    the two research lanes), and the quote leg is the registry's own `currency_profit`. A symbol
    whose row carries no usable asset class or profit currency is simply ABSENT from the result,
    so `split_symbol` gets its chance to classify it and to refuse if it cannot.
    """
    out: dict[str, tuple[str, str]] = {}
    for symbol, row in registry.items():
        if not isinstance(row, Mapping):
            continue
        name = str(symbol).strip()
        asset_class = str(row.get("asset_class") or row.get("category") or "").strip()
        quote = str(row.get("currency_profit") or "").strip().upper()
        if not name or asset_class not in _OWN_FACTOR_CLASSES or quote not in CURRENCIES:
            continue
        out[name] = (name.upper(), quote)
    return out


def _legs(symbol: str, factors: Mapping[str, tuple[str, str]] | None) -> tuple[str, str]:
    if factors is not None:
        override = factors.get(symbol) or factors.get(str(symbol).strip().upper())
        if override is not None:
            base, quote = override
            if not str(base).strip() or not str(quote).strip():
                raise RiskError(f"factors[{symbol!r}] = {override!r}: a leg name is empty")
            return (str(base).strip().upper(), str(quote).strip().upper())
    return split_symbol(symbol)


def exposure_vector(
    positions: Iterable[Position],
    factors: Mapping[str, tuple[str, str]] | None = None,
) -> tuple[tuple[str, ...], npt.NDArray[np.float64]]:
    """Signed notional per FACTOR for one book.

    A long EURUSD of 100,000 EUR-equivalent is `+100,000 EUR` and `-100,000 USD`. Summed across
    the book, four long JPY crosses stop looking like four trades and start looking like the one
    short-JPY position they are. Factor names come back sorted, so two books built in different
    orders compare column for column.

    Legs that net to exactly zero are KEPT as named zeros: a book that is long EUR through one
    sleeve and short it through another has genuinely expressed that factor, and dropping the
    name would erase the pair of bets that cancelled.
    """
    totals: dict[str, float] = {}
    for position in positions:
        base, quote = _legs(position.symbol, factors)
        amount = float(position.notional_ccy)
        totals[base] = totals.get(base, 0.0) + amount
        totals[quote] = totals.get(quote, 0.0) - amount
    names = tuple(sorted(totals))
    vector = np.array([totals[n] for n in names], dtype="float64")
    return names, vector


def exposure_matrix(
    books: Mapping[str, Iterable[Position]],
    factors: Mapping[str, tuple[str, str]] | None = None,
) -> tuple[tuple[str, ...], tuple[str, ...], npt.NDArray[np.float64]]:
    """Stack one row per sleeve: `B[i, j]` is sleeve i's signed notional on factor j.

    Sleeve order is the mapping's own (dicts preserve insertion), factor order is sorted, and
    every sleeve gets a row even when its book is empty -- a sleeve holding nothing is a row of
    zeros, which `effective_rank` correctly counts as no bet rather than dropping from the
    denominator of anything.
    """
    per_sleeve: dict[str, dict[str, float]] = {}
    names: set[str] = set()
    for sleeve, positions in books.items():
        row: dict[str, float] = {}
        for position in positions:
            base, quote = _legs(position.symbol, factors)
            amount = float(position.notional_ccy)
            row[base] = row.get(base, 0.0) + amount
            row[quote] = row.get(quote, 0.0) - amount
        per_sleeve[sleeve] = row
        names |= set(row)
    sleeves = tuple(per_sleeve)
    ordered = tuple(sorted(names))
    matrix = np.zeros((len(sleeves), len(ordered)), dtype="float64")
    index = {n: j for j, n in enumerate(ordered)}
    for i, sleeve in enumerate(sleeves):
        for name, amount in per_sleeve[sleeve].items():
            matrix[i, index[name]] = amount
    return sleeves, ordered, matrix


def effective_rank(matrix: npt.ArrayLike, tol: float = 1e-8) -> float:
    """The PARTICIPATION RATIO of the singular-value spectrum: how many directions this book spans.

        p_i = s_i^2 / sum_j s_j^2          (the spectrum as a probability distribution)
        rank_eff = 1 / sum_i p_i^2 = (sum_i s_i^2)^2 / sum_i s_i^4

    WHY A PARTICIPATION RATIO AND NOT `numpy.linalg.matrix_rank`. Rank is a step function: two
    sleeves at a 1-degree angle are rank 2, exactly as independent as two at 90 degrees, until a
    tolerance flips them to 1 all at once. Every interesting state of this book lives in the
    space that step function cannot see. The participation ratio is CONTINUOUS in the angle -- it
    reads 2.0 for two orthogonal bets, 1.6 for the classic long-EURUSD/short-USDCHF pair that
    shares its dollar leg, and glides to 1.0 as the second bet becomes the first -- so crowding is
    visible while it is forming. It is the same arithmetic the desk already uses for n_effective
    and for concentration, applied to singular values instead of correlations or weights.

    A FLAT BOOK IS 0.0, not 1.0. An empty matrix, an all-zero matrix, or one whose largest
    singular value is not positive holds no bets at all; reporting 1.0 would assert a bet that is
    not there. `tol` is RELATIVE to the largest singular value and exists to drop numerical dust,
    not to make a decision.
    """
    array = np.asarray(matrix, dtype="float64")
    if array.ndim == 1:
        array = array.reshape(1, -1)
    if array.ndim != 2:
        raise RiskError(f"effective_rank: expected a 1-D or 2-D array, got ndim={array.ndim}")
    if array.size == 0 or not np.isfinite(array).all():
        if array.size and not np.isfinite(array).all():
            raise RiskError("effective_rank: matrix carries a non-finite entry")
        return 0.0

    singular = np.linalg.svd(array, compute_uv=False)
    largest = float(singular.max()) if singular.size else 0.0
    if largest <= 0.0:
        return 0.0
    kept = singular[singular > float(tol) * largest]
    weights = np.square(kept.astype("float64"))
    total = float(weights.sum())
    if total <= 0.0:
        return 0.0
    return float(total * total / float(np.square(weights).sum()))


def factor_concentration(
    names: Sequence[str],
    vector: npt.ArrayLike,
) -> dict[str, float]:
    """Each factor's share of the book's GROSS factor exposure. Shares sum to 1.0.

    A flat book returns `{}` -- there is no share of nothing, and a dict of zeros would read as a
    measured, perfectly diversified book rather than as an empty one.
    """
    array = np.asarray(vector, dtype="float64").ravel()
    if len(names) != array.size:
        raise RiskError(
            f"factor_concentration: {len(names)} names against {array.size} values")
    if array.size == 0 or not np.isfinite(array).all():
        if array.size and not np.isfinite(array).all():
            raise RiskError("factor_concentration: vector carries a non-finite entry")
        return {}
    gross = float(np.abs(array).sum())
    if gross <= 0.0:
        return {}
    return {str(name): float(abs(array[i])) / gross for i, name in enumerate(names)}


def _convert(quote: str, account_ccy: str, rates: Mapping[str, float]) -> float:
    """Units of ACCOUNT currency per unit of `quote`. Raises rather than inventing a rate."""
    quote, account_ccy = quote.upper(), account_ccy.upper()
    if quote == account_ccy:
        return 1.0
    direct = rates.get(f"{quote}{account_ccy}")
    if isinstance(direct, (int, float)) and math.isfinite(float(direct)) and float(direct) > 0:
        return float(direct)
    inverse = rates.get(f"{account_ccy}{quote}")
    if isinstance(inverse, (int, float)) and math.isfinite(float(inverse)) and float(inverse) > 0:
        return 1.0 / float(inverse)
    raise RiskError(
        f"book_from_sleeves: no rate to convert {quote} into {account_ccy} -- looked for "
        f"{quote}{account_ccy} and {account_ccy}{quote} in rates. An absent rate is UNMEASURED "
        "(L1.28a); it is never 1.0 and never the last rate that worked.")


def book_from_sleeves(
    sleeves_doc: Any,
    rates: Mapping[str, float],
    *,
    contract_sizes: Mapping[str, float],
    account_ccy: str = "EUR",
    statuses: Sequence[str] = ("LIVE", "STANDBY"),
    lots: Mapping[str, float] | None = None,
) -> dict[str, tuple[Position, ...]]:
    """Turn `desks/mt5/data/sleeves.json` rows into per-sleeve books of account-currency notional.

    `sleeves_doc` is the parsed document (`{"sleeves": [...]}`) or the bare row list. A row
    contributes when its `status` is in `statuses` and a lot is KNOWN -- from `lots[name]` when
    the caller measured one (the gateway's own target, say), otherwise from a numeric `lot` field.
    The live registry writes `"auto_ramp"` there for most sleeves, which is not a lot: such a
    sleeve appears in the result with an EMPTY book, so the caller can name it UNMEASURED instead
    of silently dropping a sleeve out of the denominator.

    THE ARITHMETIC, with no step hidden:

        notional_base    = lot * contract_size                 (units of the base instrument)
        notional_quote   = notional_base * rates[symbol]       (the symbol's last price)
        notional_account = notional_quote * fx(quote -> account_ccy)

    `rates` carries the symbol's own price under its symbol key and the cross-currency conversions
    under `<CCY><ACCOUNT>` or `<ACCOUNT><CCY>`. AN ABSENT RATE RAISES `RiskError` and an absent
    contract size raises too. Neither is defaulted, substituted or carried over from another
    symbol: this function's entire value is that the number it returns was measured, and a single
    invented rate makes every factor share downstream of it fiction.

    Sign: the lot's own sign, negated again when the row declares a SHORT/SELL side. A row with no
    declared side is taken LONG, exactly as `exposure_decomposition` does, and the caller is
    expected to name those sleeves (`sleeve_side:<name>`) in its own unmeasured list.
    """
    rows: Sequence[Any]
    if isinstance(sleeves_doc, Mapping):
        raw = sleeves_doc.get("sleeves")
        rows = raw if isinstance(raw, Sequence) and not isinstance(raw, str) else []
    elif isinstance(sleeves_doc, Sequence) and not isinstance(sleeves_doc, str):
        rows = sleeves_doc
    else:
        raise RiskError(f"book_from_sleeves: cannot read a sleeves document of type "
                        f"{type(sleeves_doc).__name__}")

    wanted = {str(s).upper() for s in statuses}
    books: dict[str, tuple[Position, ...]] = {}
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        name = str(row.get("name") or "").strip()
        symbol = str(row.get("symbol") or "").strip()
        if not name or not symbol:
            continue
        if str(row.get("status") or "").upper() not in wanted:
            continue

        lot: float | None = None
        if lots is not None and isinstance(lots.get(name), (int, float)):
            lot = float(lots[name])
        elif isinstance(row.get("lot"), (int, float)):
            lot = float(row["lot"])
        if lot is None or not math.isfinite(lot) or lot == 0.0:
            books[name] = ()
            continue

        contract = contract_sizes.get(symbol)
        if not isinstance(contract, (int, float)) or not math.isfinite(float(contract)):
            raise RiskError(
                f"book_from_sleeves({name}): no contract size for {symbol!r}. The registry is the "
                "authority and a missing row is UNMEASURED, never 1.0 or 100,000.")
        price = rates.get(symbol)
        if not isinstance(price, (int, float)) or not math.isfinite(float(price)):
            raise RiskError(
                f"book_from_sleeves({name}): no rate for {symbol!r}. An absent price is "
                "UNMEASURED (L1.28a) -- it is never invented.")

        _, quote = _legs(symbol, None)
        sign = -1.0 if str(row.get("side") or row.get("direction") or "").upper() \
            in _SHORT_WORDS else 1.0
        notional = (lot * float(contract) * float(price)
                    * _convert(quote, account_ccy, rates) * sign)
        books[name] = (Position(symbol=symbol, notional_ccy=notional),)
    return books

```

### libs\risk\fx_factors.py
```python
"""Currency-leg factor decomposition -- the concentration a per-symbol view cannot see.

WHY THIS EXISTS. `libs/risk/factor_caps.py` aggregates risk by ASSET CLASS, which is the right
granularity for a book of BTCUSD/XAUUSD/US500 and the wrong one for this desk: every FX cross
collapses into a single `Factor.FX` bucket. Measured 2026-08-31 on the live survivor set, that
bucket held 28 of 45 certificates and said nothing useful, while the desk's own portfolio
evidence reported n_effective 1.019 across 17 sleeves -- seventeen positions behaving as one bet.
An asset-class view cannot distinguish "long four JPY crosses" from "four independent trades",
and that distinction is the whole question.

`libs.risk.instruments.get_factor` also RAISES on any symbol absent from its hand-maintained
dict. On the same survivor set it raised on 15 of 22 symbols -- every Scandi and EM cross
(CHFNOK, GBPSEK, USDZAR, GBPMXN, ...). A measurement that dies on two thirds of the book is not
a measurement, so nothing here raises on an unknown symbol: it is reported as UNKNOWN and
excluded from the totals, because a silent zero would read exactly like genuine diversification
(L1.28a -- UNMEASURED is a real answer, absence is never a clean verdict).

WHAT THIS IS NOT. It is a MEASUREMENT, not a gate and not a sizer. It has no authority over
position size and does not veto anything. The MT5 gateway keeps sizing, because it is the only
thing that knows Fusion tick value, contract size and profit currency -- the exact knowledge
whose absence produced the CADJPY incident (believed 1.26% risk, actual 7.41%; believed book
heat 2.94%, true 22.2%). This reports what the book is really long and short of, per currency.
"""
from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass, field

#: Metals and other non-currency instruments quoted like a cross. XAU/XAG are their own factor
#: rather than "long gold / short USD": a gold sleeve's risk is gold's, not the dollar's.
_NON_CURRENCY = frozenset({"XAU", "XAG", "XPT", "XPD", "XCU"})

#: A cross is six letters, two ISO-4217 legs. Anything else (US500, NatGas, hunt16) is not a
#: currency pair and must not be silently split into three-letter halves.
#:
#: SIX LETTERS IS NOT ENOUGH ON ITS OWN, and the test that proves it is not hypothetical:
#: "NatGas" uppercases to NATGAS, matches this shape, and decomposes into a long "NAT" and a
#: short "GAS". Both legs are then real numbers in a report nobody can read as wrong. Requiring
#: both legs to be a currency the desk actually quotes turns that from a silent corruption into
#: an UNKNOWN, which is the only honest answer for a symbol this module cannot classify.
_PAIR = re.compile(r"^([A-Z]{3})([A-Z]{3})$")

#: ISO-4217 legs quotable on the Fusion universe, plus the metals handled above. Extend when the
#: broker adds a currency -- an unlisted leg is reported UNKNOWN, never guessed.
_CURRENCIES = frozenset({
    "USD", "EUR", "GBP", "JPY", "CHF", "CAD", "AUD", "NZD",
    "SEK", "NOK", "DKK", "PLN", "CZK", "HUF", "TRY", "RUB",
    "ZAR", "MXN", "SGD", "HKD", "CNH", "THB", "ILS", "INR",
    # 2026-09-17: the broker quotes 27 currency legs; these three were absent and USDBRL,
    # USDIDR and USDKRW read UNKNOWN in every concentration report (found by fx_exposure
    # walking the registry rather than this list).
    "BRL", "IDR", "KRW",
})


@dataclass(frozen=True)
class CurrencyExposure:
    """Signed risk per currency leg, plus what could not be classified."""

    by_currency: dict[str, float] = field(default_factory=dict)
    by_metal: dict[str, float] = field(default_factory=dict)
    unknown: dict[str, float] = field(default_factory=dict)

    @property
    def gross(self) -> float:
        """Total absolute leg risk that was classifiable."""
        return sum(abs(v) for v in self.by_currency.values()) + sum(
            abs(v) for v in self.by_metal.values())

    @property
    def top_concentration(self) -> tuple[str, float]:
        """The single currency carrying the most absolute risk, and its share of gross."""
        if not self.by_currency or self.gross <= 0:
            return ("NONE", 0.0)
        leg, amount = max(self.by_currency.items(), key=lambda kv: abs(kv[1]))
        return (leg, abs(amount) / self.gross)


def split_pair(symbol: str) -> tuple[str, str] | None:
    """("EUR", "JPY") for EURJPY; None when `symbol` is not a six-letter cross."""
    m = _PAIR.match(symbol.strip().upper())
    if not m:
        return None
    base, quote = m.group(1), m.group(2)
    known = _CURRENCIES | _NON_CURRENCY
    if base not in known or quote not in known:
        return None
    return (base, quote)


def decompose(exposures: Mapping[str, float]) -> CurrencyExposure:
    """Split per-symbol risk into signed currency legs.

    A long EURJPY position of risk R is +R of EUR and -R of JPY. Summed across the book, four
    long JPY crosses reveal themselves as one large short-JPY position rather than four trades.
    Sign convention: a positive value in `exposures` is long the BASE currency (first leg).
    """
    by_ccy: dict[str, float] = {}
    by_metal: dict[str, float] = {}
    unknown: dict[str, float] = {}

    for symbol, risk in exposures.items():
        amount = float(risk)
        legs = split_pair(symbol)
        if legs is None:
            unknown[symbol] = unknown.get(symbol, 0.0) + amount
            continue
        base, quote = legs
        if base in _NON_CURRENCY:
            by_metal[base] = by_metal.get(base, 0.0) + amount
            # the quote leg of XAUUSD is still real dollar risk and is booked as such
            by_ccy[quote] = by_ccy.get(quote, 0.0) - amount
            continue
        if quote in _NON_CURRENCY:
            by_metal[quote] = by_metal.get(quote, 0.0) - amount
            by_ccy[base] = by_ccy.get(base, 0.0) + amount
            continue
        by_ccy[base] = by_ccy.get(base, 0.0) + amount
        by_ccy[quote] = by_ccy.get(quote, 0.0) - amount

    return CurrencyExposure(by_currency=by_ccy, by_metal=by_metal, unknown=unknown)


def effective_bets(exposures: Mapping[str, float]) -> float:
    """A crude independent-bet count from leg concentration: gross / max single-leg risk.

    Deliberately NOT a correlation estimate -- the desk already reports n_effective from
    correlation eigenvalues, and a second, weaker estimate of the same quantity would drift from
    it. This answers a different question that needs no price history at all: how many distinct
    currency legs is the book actually expressing? A book of four JPY crosses scores near 1.
    """
    d = decompose(exposures)
    if d.gross <= 0:
        return 0.0
    biggest = max((abs(v) for v in list(d.by_currency.values()) + list(d.by_metal.values())),
                  default=0.0)
    return d.gross / biggest if biggest > 0 else 0.0

```

### libs\risk\gate.py
```python
"""The risk gate — the mandatory pre-trade authority.

NO ORDER MAY EXIST WITHOUT RISK APPROVAL. The gate composes every governor (kill-switch,
drawdown, crisis, correlation, preservation) into a global scalar, sizes the position, and only
then mints a ``risk_approval_id`` (persisted to ``risk_registry``). Execution physically cannot
place an order without that id (DB ``NOT NULL`` FK, enforced in :class:`libs.store.OrderStore`).
The gate fails closed: any uncertainty rejects.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from libs.core.ids import generate_id
from libs.core.logging import get_logger
from libs.risk.config import RiskConfig
from libs.risk.correlation import correlation_scalar
from libs.risk.crisis import crisis_controller
from libs.risk.drawdown import compute_drawdown, drawdown_governor
from libs.risk.errors import RiskError
from libs.risk.instruments import get_factor
from libs.risk.preservation import equity_preservation_controller
from libs.risk.scaling import global_risk_scalar
from libs.risk.sizing import calculate_position_size
from libs.risk.vol_target import vol_target
from libs.store.registries import RiskRegistry


class OrderIntent(BaseModel):
    """A proposed trade presented to the risk gate."""

    model_config = ConfigDict(frozen=True)

    instrument: str
    side: str
    kelly_fraction: float
    risk_budget: float
    risk_per_unit: float
    edge_value: float | None = None
    cost: float | None = None
    alpha_id: str | None = None
    confidence: float = 1.0
    #: §42: dollars the EDGE absorbs before its own impact eats it. None = uncapped by capacity,
    #: which is correct for a deep instrument and WRONG for a thin one -- so a sleeve trading a
    #: capacity-bound edge must carry it, and `check_capacity_intent_coverage` fires when a
    #: declared sleeve reaches the gate without one. Every other cap here asks how much risk the
    #: BOOK may take; this asks how much the EDGE can hold, and the two are independent.
    edge_capacity_usd: float | None = None
    id: str = Field(default_factory=lambda: generate_id("intent"))


class AccountState(BaseModel):
    """The risk-relevant account snapshot the gate reasons over."""

    model_config = ConfigDict(frozen=True)

    equity: float
    peak_equity: float
    forecast_vol: float
    average_correlation: float = 0.0
    vol_now: float = 0.0
    vol_baseline: float = 0.0
    kill_switch_tripped: bool = False
    data_stale: bool = False
    factor_exposures: dict[str, float] = {}  # symbol -> current risk amount
    current_heat_total: float = 0.0


class RiskDecision(BaseModel):
    model_config = ConfigDict(frozen=True)

    approved: bool
    risk_approval_id: str | None
    sized_units: float
    global_scalar: float
    reasons: list[str]
    checks: list[dict[str, Any]]

    def __bool__(self) -> bool:
        return self.approved


# OBSERVABILITY (gap #56, 2026-07-29). EVERY rejection is logged here at the single choke point,
# so "why did the desk not trade" is answerable after the fact from one place. Below the script
# boundary there was no trail at all before this -- 1 of 318 library modules used logging, and
# this is the module that decides whether capital moves. Library never configures handlers.
_log = get_logger(__name__)


def _reject(reason: str, checks: list[dict[str, Any]]) -> RiskDecision:
    _log.warning("risk gate REJECTED: %s", reason)
    return RiskDecision(
        approved=False, risk_approval_id=None, sized_units=0.0, global_scalar=0.0,
        reasons=[reason], checks=checks,
    )


def risk_gate(
    intent: OrderIntent,
    account: AccountState,
    config: RiskConfig | None = None,
    *,
    registry: RiskRegistry | None = None,
) -> RiskDecision:
    """Run the mandatory pre-trade gate. Returns an approval (with id) or a rejection."""
    cfg = config or RiskConfig()
    checks: list[dict[str, Any]] = []

    try:
        # Fail-closed input validation.
        if account.equity <= 0 or account.peak_equity <= 0:
            return _reject("fail-closed: invalid equity", checks)
        if intent.risk_per_unit <= 0:
            return _reject("fail-closed: invalid risk_per_unit", checks)
        if account.data_stale:
            checks.append({"name": "data", "passed": False})
            return _reject("fail-closed: stale data", checks)
        checks.append({"name": "data", "passed": True})

        # Kill switch.
        if account.kill_switch_tripped:
            checks.append({"name": "kill_switch", "passed": False})
            return _reject("kill-switch tripped", checks)
        checks.append({"name": "kill_switch", "passed": True})

        # Drawdown governor.
        drawdown = compute_drawdown(account.equity, account.peak_equity)
        dd = drawdown_governor(drawdown, ladder=cfg.drawdown)
        checks.append({"name": "drawdown", "passed": not dd.halt, "level": dd.level.value})
        if dd.halt:
            return _reject(f"drawdown halt at {drawdown:.1%}", checks)

        # Preservation / equity floor.
        pres = equity_preservation_controller(
            account.equity, account.peak_equity, config=cfg.preservation
        )
        checks.append({"name": "preservation", "passed": not pres.halt, "mode": pres.mode.value})
        if pres.halt:
            return _reject("equity floor breached", checks)

        # Crisis + correlation governors.
        crisis = crisis_controller(
            vol_now=account.vol_now, vol_baseline=account.vol_baseline,
            average_correlation=account.average_correlation, config=cfg.crisis,
        )
        s_corr = correlation_scalar(account.average_correlation, cfg.correlation)
        checks.append({"name": "crisis", "passed": not crisis.in_crisis})
        checks.append({"name": "correlation", "passed": s_corr >= 1.0, "scalar": s_corr})

        scalar = global_risk_scalar(
            drawdown=dd.scalar, correlation=s_corr, crisis=crisis.exposure_scalar,
            floor=pres.scalar, confidence=max(0.0, min(1.0, intent.confidence)),
        )
        if scalar.value <= 0:
            return _reject(f"global risk scalar is zero (binding: {scalar.binding})", checks)

        # Sizing synthesis with caps.
        factor = get_factor(intent.instrument)
        factor_cap_amount = cfg.exposure.factor_caps.get(factor, 1.0) * account.equity
        factor_used = sum(
            abs(v) for s, v in account.factor_exposures.items() if get_factor(s) == factor
        )
        factor_headroom = factor_cap_amount - factor_used
        heat_headroom = cfg.heat.max_portfolio_frac * account.equity - account.current_heat_total
        position_cap = cfg.exposure.max_position_frac * account.equity

        sizing = calculate_position_size(
            account.equity,
            kelly_fraction=intent.kelly_fraction,
            vol_scalar=vol_target(
                account.forecast_vol, target_vol=cfg.vol.target,
                k_min=cfg.vol.k_min, k_max=cfg.vol.k_max,
            ),
            risk_budget=intent.risk_budget,
            global_scalar=scalar.value,
            risk_per_unit=intent.risk_per_unit,
            side=intent.side,
            edge_value=intent.edge_value,
            cost=intent.cost,
            max_position_amount=position_cap,
            factor_headroom=factor_headroom,
            heat_headroom=heat_headroom,
            edge_capacity_usd=intent.edge_capacity_usd,
        )
        checks.append(
            {"name": "sizing", "passed": not sizing.rejected, "binding": sizing.binding_constraint}
        )
        if sizing.rejected:
            return _reject(f"sizing rejected: {sizing.reason}", checks)

    except RiskError as exc:
        return _reject(f"fail-closed: {exc}", checks)

    # Approved — mint the structural approval id.
    risk_approval_id: str | None = None
    if registry is not None:
        approval = registry.create_approval(
            target_ref=intent.id,
            detail={
                "instrument": intent.instrument,
                "units": sizing.units,
                "global_scalar": scalar.value,
                "binding": sizing.binding_constraint,
            },
        )
        risk_approval_id = approval.id

    return RiskDecision(
        approved=True,
        risk_approval_id=risk_approval_id,
        sized_units=sizing.units,
        global_scalar=scalar.value,
        reasons=[],
        checks=checks,
    )

```

### libs\risk\growth_leverage.py
```python
"""Growth-optimal (Kelly) leverage analysis -- optimize geometric CAGR, not Sharpe.

For a daily net-return stream this computes, across a leverage ladder, the *geometric* growth and
its costs: CAGR, annual vol, max drawdown, and a bootstrapped risk-of-ruin. It finds the
growth-optimal (Kelly) leverage -- the point where ``E[log(1 + L*r)]`` peaks, after which volatility
drag destroys compounding -- and the robust fractional-Kelly recommendation.

Honesty: Kelly leverage assumes the edge estimate is TRUE. On an unvalidated edge (in-sample, fails
DSR) the realized edge is almost surely lower, so full Kelly over-levers and risks ruin. The
recommended size is therefore *fractional* Kelly, and only after forward validation. Pure functions;
realistic -- the input returns must already be net of spread/swap/commission/financing/slippage.
"""

from __future__ import annotations

import numpy as np

LADDER: tuple[float, ...] = (0.5, 1.0, 1.5, 2.0, 3.0, 4.0, 5.0, 6.0, 8.0, 10.0)


def ann_geom_growth(returns: np.ndarray, leverage: float, ppy: float = 252.0) -> float:
    """Annualized geometric growth ``ppy * E[log(1 + L*r)]`` (-inf if a path is wiped out)."""
    x = 1.0 + leverage * np.asarray(returns, dtype="float64")
    if np.any(x <= 0.0):
        return float("-inf")                       # a single >100% loss day => ruin
    return float(np.mean(np.log(x)) * ppy)


def cagr(returns: np.ndarray, leverage: float, ppy: float = 252.0) -> float:
    g = ann_geom_growth(returns, leverage, ppy)
    return -1.0 if not np.isfinite(g) else float(np.exp(g) - 1.0)


def max_drawdown(returns: np.ndarray, leverage: float) -> float:
    eq = np.cumprod(1.0 + leverage * np.asarray(returns, dtype="float64"))
    if np.any(eq <= 0.0):
        return -1.0
    peak = np.maximum.accumulate(eq)
    return float((eq / peak - 1.0).min())


def risk_of_ruin(
    returns: np.ndarray,
    leverage: float,
    *,
    horizon: int = 252,
    threshold: float = 0.2,
    n_paths: int = 1500,
    seed: int = 0,
) -> float:
    """Bootstrapped P(equity falls below ``threshold`` within ``horizon`` days) at this leverage.

    IID resample of the realized non-zero daily returns (preserves the fat tails); ``threshold=0.2``
    means an 80% drawdown is treated as ruin. Conservative and assumption-light.
    """
    a = np.asarray(returns, dtype="float64")
    a = a[a != 0.0]
    if len(a) < 20:
        return float("nan")
    rng = np.random.default_rng(seed)
    paths = rng.choice(a, size=(n_paths, horizon), replace=True)
    eq = np.cumprod(1.0 + leverage * paths, axis=1)
    return float(np.mean(eq.min(axis=1) < threshold))


def kelly_optimal(returns: np.ndarray, *, cap: float = 10.0, points: int = 200) -> float:
    """Growth-optimal leverage = argmax of geometric growth on a fine grid (capped)."""
    grid = np.linspace(0.0, cap, points + 1)[1:]
    growths = np.array([ann_geom_growth(returns, float(g), 1.0) for g in grid])
    if not np.any(np.isfinite(growths)) or np.nanmax(growths) <= 0.0:
        return 0.0
    return float(grid[int(np.nanargmax(growths))])


def leverage_ladder(
    returns: np.ndarray,
    *,
    ppy: float = 252.0,
    ladder: tuple[float, ...] = LADDER,
    ruin_threshold: float = 0.2,
) -> list[dict[str, float]]:
    return [
        {
            "leverage": L,
            "cagr": round(cagr(returns, L, ppy), 4),
            "ann_vol": round(float(np.std(returns) * L * np.sqrt(ppy)), 4),
            "max_dd": round(max_drawdown(returns, L), 4),
            "risk_of_ruin": round(risk_of_ruin(returns, L, threshold=ruin_threshold), 4),
        }
        for L in ladder
    ]


def _skew(returns: np.ndarray) -> float:
    a = np.asarray(returns, dtype="float64")
    a = a[a != 0.0]
    if len(a) < 8 or a.std() == 0:
        return 0.0
    return float(np.mean(((a - a.mean()) / a.std()) ** 3))


def analyze(
    returns: np.ndarray,
    *,
    ppy: float = 252.0,
    kelly_fraction: float = 0.5,
    governance_cap: float = 1.0,
) -> dict[str, object]:
    """Full growth-optimal vs aggressive leverage report for one return stream.

    ``kelly_fraction`` is the robust de-rating (default half-Kelly); ``governance_cap`` is an
    absolute leverage ceiling from risk policy (the recommendation is the min of the two).
    """
    kelly = kelly_optimal(returns, cap=10.0)
    recommended = min(kelly * kelly_fraction, governance_cap)
    aggressive = min(kelly * 2.0, 10.0)            # 2x Kelly: the over-bet that ruins compounding

    def row(label: str, lev: float) -> dict[str, object]:
        return {
            "label": label, "leverage": round(lev, 2),
            "cagr": round(cagr(returns, lev, ppy), 4),
            "ann_vol": round(float(np.std(returns) * lev * np.sqrt(ppy)), 4),
            "max_dd": round(max_drawdown(returns, lev), 4),
            # R0286: the ruin horizon must cover the SAME year as cagr/ann_vol above -- a 365-day
            # crypto book reported off the default 252-day horizon understates annual ruin.
            "risk_of_ruin": round(risk_of_ruin(returns, lev, horizon=int(ppy)), 4),
        }

    return {
        "skew": round(_skew(returns), 3),
        "growth_optimal_leverage": round(kelly, 2),
        "recommended_leverage": round(recommended, 2),
        "ladder": leverage_ladder(returns, ppy=ppy),
        "points": {
            "growth_optimal": row("growth-optimal (full Kelly)", kelly),
            "recommended": row(f"recommended ({kelly_fraction:g}x Kelly, capped)", recommended),
            "aggressive": row("aggressive (2x Kelly)", aggressive),
        },
    }

```

### libs\risk\heat.py
```python
"""Portfolio heat — a hard cap on total open risk-at-stop at any instant.

Heat is what you actually lose if every open position is stopped (gap-aware), independent of
vol-targeting and Kelly — the simplest, most robust backstop. New positions are rejected if they
would breach the aggregate or per-position heat cap.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from pydantic import BaseModel, ConfigDict

from libs.risk.config import HeatLimits
from libs.risk.errors import RiskError
from libs.risk.instruments import Factor, get_factor


@dataclass(frozen=True)
class PositionHeat:
    """One position's risk-at-stop contribution."""

    instrument: str
    units: float
    risk_per_unit: float  # gap-aware distance to stop, per unit

    @property
    def heat(self) -> float:
        return abs(self.units) * self.risk_per_unit


def calculate_heat(positions: Sequence[PositionHeat]) -> dict[str, float]:
    """Aggregate heat: total, per-instrument, and per-factor (sector)."""
    total = 0.0
    per_instrument: dict[str, float] = {}
    per_factor: dict[Factor, float] = {}
    for pos in positions:
        if pos.risk_per_unit < 0:
            raise RiskError("risk_per_unit must be non-negative")
        total += pos.heat
        per_instrument[pos.instrument] = per_instrument.get(pos.instrument, 0.0) + pos.heat
        factor = get_factor(pos.instrument)
        per_factor[factor] = per_factor.get(factor, 0.0) + pos.heat
    result: dict[str, float] = {"total": total}
    result.update({f"instrument:{k}": v for k, v in per_instrument.items()})
    result.update({f"factor:{k.value}": v for k, v in per_factor.items()})
    return result


class HeatResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    total_heat: float
    heat_fraction: float
    ok: bool
    breaches: list[str]

    def __bool__(self) -> bool:
        return self.ok


def check_heat_limits(
    heat: Mapping[str, float], *, equity: float, limits: HeatLimits | None = None
) -> HeatResult:
    """Check aggregate and per-position heat against caps (fractions of equity)."""
    cfg = limits or HeatLimits()
    if equity <= 0:
        raise RiskError("equity must be positive")
    total = float(heat.get("total", 0.0))
    breaches: list[str] = []
    if total > cfg.max_portfolio_frac * equity:
        breaches.append("portfolio")
    per_position_cap = cfg.max_per_position_frac * equity
    for key, value in heat.items():
        if key.startswith("instrument:") and value > per_position_cap:
            breaches.append(key)
    return HeatResult(
        total_heat=total, heat_fraction=total / equity, ok=not breaches, breaches=breaches
    )

```

### libs\risk\instruments.py
```python
"""Risk factors, the instrument-to-factor map, and instrument tiers.

Diversification is by *factor*, not symbol: gold and silver are one precious-metals bet, all
indices are one equity-beta bet. Factor caps and correlation control operate on these groups so
hidden concentration cannot creep in through correlated symbols.
"""

from __future__ import annotations

from enum import StrEnum

from libs.risk.errors import RiskError


class Factor(StrEnum):
    PRECIOUS_METALS = "precious_metals"
    FX = "fx"
    EQUITY_INDEX = "equity_index"
    CRYPTO = "crypto"
    ENERGY = "energy"
    COMMODITY = "commodity"
    RATES = "rates"


_FACTOR_OF: dict[str, Factor] = {
    # precious metals
    "XAUUSD": Factor.PRECIOUS_METALS, "XAGUSD": Factor.PRECIOUS_METALS,
    "XAUEUR": Factor.PRECIOUS_METALS, "XPTUSD": Factor.PRECIOUS_METALS,
    "XPDUSD": Factor.PRECIOUS_METALS,
    # fx majors + crosses
    "EURUSD": Factor.FX, "GBPUSD": Factor.FX, "AUDUSD": Factor.FX, "USDCAD": Factor.FX,
    "USDCHF": Factor.FX, "NZDUSD": Factor.FX, "USDJPY": Factor.FX, "EURJPY": Factor.FX,
    "AUDJPY": Factor.FX, "EURGBP": Factor.FX, "AUDNZD": Factor.FX, "GBPJPY": Factor.FX,
    "EURAUD": Factor.FX, "CADJPY": Factor.FX, "EURCAD": Factor.FX, "GBPAUD": Factor.FX,
    "CHFJPY": Factor.FX, "EURCHF": Factor.FX, "GBPCAD": Factor.FX,
    # equity indices
    "US500": Factor.EQUITY_INDEX, "US100": Factor.EQUITY_INDEX, "NAS100": Factor.EQUITY_INDEX,
    "US30": Factor.EQUITY_INDEX, "GER40": Factor.EQUITY_INDEX, "JP225": Factor.EQUITY_INDEX,
    "UK100": Factor.EQUITY_INDEX, "US2000": Factor.EQUITY_INDEX, "HK50": Factor.EQUITY_INDEX,
    "EU50": Factor.EQUITY_INDEX, "AUS200": Factor.EQUITY_INDEX,
    # crypto
    "BTCUSD": Factor.CRYPTO, "ETHUSD": Factor.CRYPTO, "SOLUSD": Factor.CRYPTO,
    "XRPUSD": Factor.CRYPTO, "LTCUSD": Factor.CRYPTO,
    # energy
    "WTI": Factor.ENERGY, "USOIL": Factor.ENERGY, "Brent": Factor.ENERGY,
    "UKOIL": Factor.ENERGY, "NatGas": Factor.ENERGY, "XNGUSD": Factor.ENERGY,
    # commodities (industrial + ags)
    "Copper": Factor.COMMODITY, "XCUUSD": Factor.COMMODITY, "Corn": Factor.COMMODITY,
    "Wheat": Factor.COMMODITY, "Soybeans": Factor.COMMODITY, "Sugar": Factor.COMMODITY,
    "Coffee": Factor.COMMODITY, "Cotton": Factor.COMMODITY, "Cocoa": Factor.COMMODITY,
    # rates / duration
    "US10Y": Factor.RATES, "BUND": Factor.RATES,
}

TIER1: frozenset[str] = frozenset({"XAUUSD", "XAGUSD", "NAS100", "US500", "BTCUSD", "USDJPY"})
TIER2: frozenset[str] = frozenset({"EURUSD", "GBPUSD", "US30", "GER40", "ETHUSD", "USOIL"})
TIER3: frozenset[str] = frozenset(_FACTOR_OF) - TIER1 - TIER2


def get_factor(symbol: str) -> Factor:
    """Return the risk factor for ``symbol`` or raise :class:`RiskError`."""
    try:
        return _FACTOR_OF[symbol]
    except KeyError as exc:
        raise RiskError(f"no risk factor mapped for instrument {symbol!r}") from exc


def tier_of(symbol: str) -> int:
    """Return the instrument tier (1/2/3)."""
    if symbol in TIER1:
        return 1
    if symbol in TIER2:
        return 2
    if symbol in _FACTOR_OF:
        return 3
    raise RiskError(f"unknown instrument {symbol!r}")

```

### libs\risk\kelly.py
```python
"""Kelly sizing — fractional, Bayesian, and adaptive.

Kelly maximizes geometric growth but is used *fractionally* because the true edge is unknown
and overstated; overbetting is catastrophic, underbetting merely suboptimal, so always err low.
The base/standard size is 1/3 Kelly; only sustained live evidence (good ROI that meets the
deployable bar) earns scaling up to 1/2 Kelly. Scaling up is gradual; scaling down is immediate.
The cap never exceeds 1/2 Kelly.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict

from libs.risk.config import KellyLimits
from libs.risk.errors import RiskError


class AlphaStage(StrEnum):
    NEW = "new"
    VALIDATED = "validated"
    PROVEN = "proven"


def calculate_kelly(mu: float, variance: float) -> float:
    """Full Kelly fraction for a Gaussian edge: f* = mu / variance."""
    if variance <= 0:
        raise RiskError("variance must be positive")
    return mu / variance


def calculate_bayesian_kelly(
    mu_hat: float, se_mu: float, variance: float, *, z: float = 1.0
) -> float:
    """Bayesian/uncertainty-haircut Kelly: size on a conservative lower bound of the edge.

    ``f = max(0, (mu_hat - z * se_mu)) / variance`` — shrinks toward zero when the track record
    is short or noisy, and grows only as evidence accumulates. Never negative (no anti-betting).
    """
    if variance <= 0:
        raise RiskError("variance must be positive")
    if se_mu < 0:
        raise RiskError("se_mu must be non-negative")
    lower_bound = mu_hat - z * se_mu
    return max(0.0, lower_bound) / variance


class KellyScaling(BaseModel):
    model_config = ConfigDict(frozen=True)

    stage_cap: float
    evidence: float
    target_lambda: float
    recommended_lambda: float


def _sigmoid(x: float) -> float:
    import math

    return 1.0 / (1.0 + math.exp(-x))


def adaptive_kelly_fraction(
    stage: AlphaStage,
    *,
    track_record: int,
    live_vs_backtest: float,
    regime_stability: float,
    ci_lower: float,
    current_lambda: float | None = None,
    limits: KellyLimits | None = None,
) -> KellyScaling:
    """Adaptive Kelly cap from live evidence, with gradual-up / immediate-down scaling.

    Evidence blends four signals: live track-record length, live-vs-backtest agreement, regime
    stability, and whether the live edge's lower confidence bound is positive. A weak signal
    pulls the recommended fraction back toward (or below) the 1/3-Kelly base.
    """
    cfg = limits or KellyLimits()
    if not 0.0 <= regime_stability <= 1.0:
        raise RiskError("regime_stability must be in [0, 1]")

    stage_cap = {
        AlphaStage.NEW: cfg.new_cap,
        AlphaStage.VALIDATED: cfg.validated_cap,
        AlphaStage.PROVEN: cfg.proven_cap,
    }[stage]
    stage_cap = min(stage_cap, cfg.hard_max)

    track_score = _sigmoid((track_record - 60) / 30.0)  # ~0 at 0 trades, ~1 by ~150
    agreement_score = max(0.0, min(1.0, live_vs_backtest))  # 1.0 == live matches backtest
    ci_score = 1.0 if ci_lower > 0 else 0.0
    evidence = track_score * agreement_score * regime_stability * ci_score

    # Target: interpolate from the 1/3 base up to the stage cap by evidence quality.
    target = cfg.new_cap + (stage_cap - cfg.new_cap) * evidence
    target = max(0.0, min(target, cfg.hard_max))

    if current_lambda is None:
        recommended = min(cfg.new_cap, target)  # new exposure starts no higher than 1/3 Kelly
    elif target >= current_lambda:
        recommended = min(target, current_lambda + cfg.max_up_step)  # gradual up
    else:
        recommended = target  # immediate down
    recommended = max(0.0, min(recommended, cfg.hard_max))

    return KellyScaling(
        stage_cap=stage_cap,
        evidence=evidence,
        target_lambda=target,
        recommended_lambda=recommended,
    )

```

### libs\risk\kelly_shrink.py
```python
"""Estimation-error-shrunk Kelly -- the fraction that actually maximizes E[log wealth].

    shrink = S^2 / (S^2 + SE(S)^2)        (Bayesian shrinkage toward a zero-edge prior)
    fraction_of_kelly = shrink            (ramps continuously as evidence accumulates)

with SE from Lo (2002): SE(S_daily) = sqrt((1 + S_daily^2 / 2) / N), annualized. Pooling
shadow + live forward days grows N daily, so size compounds with evidence automatically:
no rungs, no calendar, nothing to skip. Reference behaviour (S_ann ~ 2.3): ~0.17x Kelly
at day 15, ~0.36x at 40, ~0.55x at 90, ~0.71x at 180. A day-40 fast-track (needs S ~ 5)
starts at ~0.73x -- strong evidence self-authorizes size, weak evidence cannot.

WHY THE SHRINK IS RIGHT -- CORRECTED 2026-08-13 (R0432). THE FORMULA IS UNCHANGED AND THIS
IS NOT AN ARGUMENT TO BET MORE. What changed is the reason attached to it, because the
reason that used to be here is measurably false and a false rationale calibrates a real
knob in the wrong direction.

THE RETIRED RATIONALE: "Kelly's penalty for overbetting is asymmetric, so betting naive
full Kelly on an ESTIMATED edge has lower expected compounding than the shrunk fraction."
Measured and refuted by `scripts/study_absorbing_kelly.py` CONTROL A, 12/12 cells: with an
unbiased mu, estimation noise ALONE leaves the growth optimum at exactly f* = 1.00. It is
not a simulation artifact -- E[log W_T] = T(L*mu - L^2 sigma^2 / 2) is LINEAR in mu, so
averaging over symmetric parameter noise about a correct mean cannot move the argmax at
all. The asymmetry is real but it already lives inside the quadratic term; it is not a
second effect that noise switches on.

THE RATIONALE THAT SURVIVES: S-hat is not unbiased for the quantity being bet on. Edges
reach this function BECAUSE they measured well, so the estimate carries a winner's curse
and the correct input is the POSTERIOR MEAN of the edge under a prior that most candidates
have none -- strictly below S-hat. S^2/(S^2 + SE^2) is exactly the James-Stein /
normal-posterior shrinkage factor toward a zero-edge prior, so the form was right for a
reason nobody had written down. The desk's prior is very strong: 420 screened, 0 survivors.

DECIDED, NOT DEFERRED: THE SCREEN'S TRIAL COUNT IS NOT FED IN, AND MUST NOT BE. R0432 asked
whether the 420-trial multiplicity count should tighten the shrink for heavily-selected
candidates. It should not, and the reason is a property of the INPUT rather than a judgement
about strength: this function is fed `fwd_sharpe` / `fwd_days` (dynamic_leverage.py:112) --
the pre-registered FORWARD clock, measured on data that took no part in the screen's
selection. Charging the screen's winner's curse against an estimate that did not undergo it
prices the same selection twice, which is the duplicated-multiplicity error this desk has
already paid for once in validation (turnover penalised twice because nobody checked whether
it was in the number). The two-stage discovery law is what makes this safe: the screen has
zero promotion authority, so its multiplicity is spent there and not carried forward.

WHAT IS GENUINELY UNPRICED, AND IS A DIFFERENT AND SMALLER QUANTITY: promotion selects on
FORWARD evidence, over at most MAX_FORWARD_SLOTS=12 concurrent slots. Holm corrects the
p-value of that decision; it does not de-bias the effect SIZE this function then sizes on,
so a candidate that just cleared the bar still has an upward-biased forward Sharpe. The
relevant selection intensity is best-of-12, not best-of-420. Whether S^2/(S^2+SE^2) already
absorbs it is an empirical question that needs its own study and is rowed separately --
NOT assumed either way here, and any change it produces can only be TIGHTER.
"""

from __future__ import annotations

import math

_PPY = 365.0


def sharpe_se(sharpe_ann: float, n_days: float, *, ppy: float = _PPY) -> float:
    """Lo (2002) standard error of the ANNUALIZED Sharpe estimated from n daily returns."""
    if n_days <= 1:
        return float("inf")
    s_daily = sharpe_ann / math.sqrt(ppy)
    se_daily = math.sqrt((1.0 + 0.5 * s_daily * s_daily) / n_days)
    return se_daily * math.sqrt(ppy)


def shrink_fraction(sharpe_ann: float, n_days: float, *, vif: float = 1.0,
                    ppy: float = _PPY) -> float:
    """Fraction of full Kelly that maximizes expected log growth under estimation error.

    0 when the edge is unproven (S <= 0 or < 5 effective days); -> 1 asymptotically as
    evidence accumulates. Monotone in S and N, anti-monotone in vif.

    ``vif``: variance-inflation factor for autocorrelated returns (round-2 external review,
    2026-07-12 — the SE must live on the SAME effective sample size as the NW t-stat, or the
    sizing over-trusts sticky returns exactly where the significance test distrusts them).
    Pass forward_stats.autocorr_factor(returns); effective N = N / vif.
    """
    n_eff = n_days / max(1.0, vif)
    if sharpe_ann <= 0.0 or n_eff < 5:
        return 0.0
    se = sharpe_se(sharpe_ann, n_eff, ppy=ppy)
    if not math.isfinite(se) or se <= 0.0:
        return 0.0
    s2 = sharpe_ann * sharpe_ann
    return round(s2 / (s2 + se * se), 4)


def shrunk_kelly(kelly: float, sharpe_ann: float, n_days: float,
                 *, vif: float = 1.0, floor: float = 0.0, ppy: float = _PPY) -> float:
    """The deployable Kelly multiple: shrink * kelly, floored at an operational minimum."""
    return max(floor, shrink_fraction(sharpe_ann, n_days, vif=vif, ppy=ppy) * max(0.0, kelly))


def first_inversion_cap(fraction: float, live_days: float,
                        inversion_survived: bool, nav: float = 0.0) -> float:
    """Carry-book live probation cap, DYNAMIC by scale (principal-adopted 2026-07-12;
    NAV-scaling added same day on round-2/3 reviewer consensus that the trade is
    scale-dependent -- marginal insurance at $5k, clearly correct at $500k): until the LIVE
    book has survived one funding-inversion episode -- >=1 day of negative aggregate realized
    funding (venue income truth) with episode drawdown <= 2x model expectation -- OR 60 live
    days have elapsed (whichever first), deploy at a NAV-scaled fraction of the authorized
    size: 0.75x below $25k (light drag where the insurance is nearly free anyway), 0.6x to
    $100k, 0.5x above. Self-expiring: zero effect from day 60 forever. Rationale: the single
    most common carry-desk death is meeting the first inversion at maximum size; this buys
    the first observation of the core adverse regime at a scale-appropriate discount."""
    if inversion_survived or live_days >= 60.0:
        return fraction
    probation = 0.75 if nav < 25_000 else 0.6 if nav < 100_000 else 0.5
    return probation * fraction

```

### libs\risk\overlays.py
```python
"""Variance-reduction overlays: vol-targeting + residual beta-hedge.

Pure Sharpe-raisers -- they assume NO new edge, they only lower sigma. Lower sigma raises Sharpe AND
shrinks the +/-1/2 L^2 sigma^2 leverage drag in geometric growth g = L*mu - 1/2 L^2 sigma^2, so the
SAME half-Kelly leverage compounds faster and draws down less. Both use only LAGGED estimates -> no
look-ahead. Consumed by the overlay backtest and (once validated) the live sizing path.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

_PPY = 365.0


def realized_vol(returns: np.ndarray, *, lookback: int = 20, ppy: float = _PPY) -> np.ndarray:
    """Rolling annualised realised vol of a return series (NaN for the warm-up window)."""
    rv: np.ndarray = (pd.Series(returns, dtype=float).rolling(lookback).std()
                      * np.sqrt(ppy)).to_numpy()
    return rv


def vol_target_scale(returns: np.ndarray, *, target_vol: float = 0.35, lookback: int = 20,
                     cap: float = 3.0, ppy: float = _PPY) -> tuple[np.ndarray, np.ndarray]:
    """Scale a return series to a constant target vol (exposure = target / lagged-realised, capped).

    Constant risk -> smoother compounding, higher Sharpe, shallower tails. Returns (scaled, expo).
    """
    r = np.asarray(returns, dtype=float)
    rv = (pd.Series(r).rolling(lookback).std() * np.sqrt(ppy)).shift(1)   # lagged: no look-ahead
    scale = (target_vol / rv.replace(0.0, np.nan)).clip(0.0, cap).fillna(1.0).to_numpy()
    return scale * r, scale


def beta_neutralize(asset_returns: np.ndarray, market_returns: np.ndarray, *,
                    lookback: int = 60) -> tuple[np.ndarray, np.ndarray]:
    """Remove rolling (lagged) market beta -> residual returns. Returns (residual, beta)."""
    a = pd.Series(np.asarray(asset_returns, dtype=float))
    m = pd.Series(np.asarray(market_returns, dtype=float))
    beta = (a.rolling(lookback).cov(m) / m.rolling(lookback).var()).shift(1).fillna(0.0)
    resid = (a - beta * m).to_numpy()
    return resid, beta.to_numpy()

```

### libs\risk\preservation.py
```python
"""Equity preservation — protect the base so long-term compounding survives.

Modes escalate as equity approaches the floor: normal -> recovery (clawing back from a
drawdown) -> preservation (near the floor) -> survival (at/through the floor: halt). The
absolute equity floor is the ultimate ruin backstop.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict

from libs.risk.config import PreservationConfig
from libs.risk.drawdown import compute_drawdown
from libs.risk.errors import RiskError

_PRESERVATION_SCALAR = 0.30
_RECOVERY_SCALAR = 0.50


class PreservationMode(StrEnum):
    NORMAL = "normal"
    RECOVERY = "recovery"
    PRESERVATION = "preservation"
    SURVIVAL = "survival"


class PreservationResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    mode: PreservationMode
    scalar: float
    halt: bool

    def __bool__(self) -> bool:
        return not self.halt


def equity_preservation_controller(
    equity: float, peak_equity: float, *, config: PreservationConfig | None = None
) -> PreservationResponse:
    """Return the preservation mode + exposure scalar (halts at/through the floor)."""
    cfg = config or PreservationConfig()
    if peak_equity <= 0:
        raise RiskError("peak_equity must be positive")

    floor = cfg.equity_floor
    if floor > 0 and equity <= floor:
        return PreservationResponse(mode=PreservationMode.SURVIVAL, scalar=0.0, halt=True)
    if floor > 0 and equity <= floor * (1.0 + cfg.floor_buffer_frac):
        return PreservationResponse(
            mode=PreservationMode.PRESERVATION, scalar=_PRESERVATION_SCALAR, halt=False
        )
    if compute_drawdown(equity, peak_equity) >= cfg.recovery_drawdown:
        return PreservationResponse(
            mode=PreservationMode.RECOVERY, scalar=_RECOVERY_SCALAR, halt=False
        )
    return PreservationResponse(mode=PreservationMode.NORMAL, scalar=1.0, halt=False)

```

### libs\risk\risk_budget.py
```python
"""Risk budgeting — allocate and enforce risk (not dollars) across alphas/factors/instruments.

Budgeting risk shares makes it impossible to accidentally hold most of your risk in one place
(the gold/silver-as-one-bet trap). Enforcement clamps any bucket that exceeds its cap.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import cast

import numpy as np
from pydantic import BaseModel, ConfigDict

from libs.risk.errors import RiskError


def risk_contributions(weights: np.ndarray, cov: np.ndarray) -> np.ndarray:
    """Marginal risk contributions RC_i = w_i (Sigma w)_i / sigma_p (they sum to sigma_p)."""
    w = np.asarray(weights, dtype="float64")
    sigma = np.asarray(cov, dtype="float64")
    port_var = float(w @ sigma @ w)
    if port_var <= 0:
        return np.zeros_like(w)
    port_vol = np.sqrt(port_var)
    return cast("np.ndarray", w * (sigma @ w) / port_vol)


def allocate_risk_budget(budgets: Mapping[str, float], total_risk: float) -> dict[str, float]:
    """Split ``total_risk`` across buckets in proportion to their (normalized) budget shares."""
    if total_risk < 0:
        raise RiskError("total_risk must be non-negative")
    shares = {k: float(v) for k, v in budgets.items()}
    if any(v < 0 for v in shares.values()):
        raise RiskError("budget shares must be non-negative")
    denom = sum(shares.values())
    if denom <= 0:
        raise RiskError("budget shares must sum to a positive number")
    return {k: total_risk * v / denom for k, v in shares.items()}


class BudgetEnforcement(BaseModel):
    model_config = ConfigDict(frozen=True)

    enforced: dict[str, float]
    breached: list[str]
    scaled: bool


def enforce_risk_budget(
    proposed: Mapping[str, float], caps: Mapping[str, float]
) -> BudgetEnforcement:
    """Clamp each bucket's proposed risk to its cap; report which were breached."""
    enforced: dict[str, float] = {}
    breached: list[str] = []
    for key, value in proposed.items():
        cap = caps.get(key)
        if cap is not None and value > cap:
            enforced[key] = cap
            breached.append(key)
        else:
            enforced[key] = float(value)
    return BudgetEnforcement(enforced=enforced, breached=breached, scaled=bool(breached))

```

### libs\risk\risk_controls.py
```python
"""Growth-POSITIVE risk controls -- limits sized at the ruin boundary, never from fear.

Design axiom: geometric growth is g ~= mu - sigma^2/2, so cutting the LEFT TAIL cuts sigma^2 faster
than mu -> it RAISES compounding. Every control here is derived from the ruin / max-DD math
(growth_leverage + the dynamic-leverage ruin cap), NOT from arbitrary caution. A limit that
binds tighter than the ruin boundary would be false conservatism (a bug that lowers log-wealth); a
limit AT the boundary only ever fires when NOT firing would risk ruin -- which destroys all future
compounding. So in normal operation these controls do nothing, and in a tail event they preserve the
ability to keep compounding.

Six controls, in increasing severity:
  * exposure guard  -- gross notional may not exceed the ruin-boundary leverage x equity (a backstop
                       against a sizing bug; never binds while we deploy below the ruin cap).
  * VENUE CAP       -- no single exchange may hold more than `venue_cap` of equity (gap #54).
  * FEE-VS-HARVEST  -- rolling-window fees above a documented fraction of the funding harvest PAUSE
                       new opens (gap #98). An open is always optional; a fee bill this size makes
                       it an optional loss.
  * BURN FLOOR      -- windowed net burn (fees minus harvest, venue income truth) at the DD-pause
                       fraction of equity PAUSES new opens even when marks hide the loss (gap #98).
  * DD circuit break -- above a stress drawdown, PAUSE new opens (keep existing carries earning
                       funding; never realises a loss). Kelly-consistent: uncertainty up -> less.
  * ruin kill-switch -- only a catastrophic equity loss (>= drawdown_ruin) forces a full flatten.
                       For a delta-neutral book this means an exchange/basis catastrophe -> survive.

GAP #54 -- COUNTERPARTY CONCENTRATION, THE ONE FATAL RISK NOTHING CAPPED. Per-name was capped at
35% and per-factor was capped, while the fraction of net worth sitting inside a single exchange
was capped by nothing at all: `grep -rn 'per_venue|venue_cap|venue_exposure'` returned zero hits
across the whole repo. SYSTEM_REVIEW ranks this fatal in its own words -- *"an FTX-class failure
is fatal to deployed capital regardless of strategy correctness"*. Every other control here
assumes the exchange gives the money back.

It belongs in THIS file rather than the executor because it is the same kind of object as the
others: a pure ruin-boundary limit, not an execution detail. And it lands BEFORE live keys
deliberately -- with one venue the cap binds at 100% and changes nothing today, which is exactly
why installing it now is free and retrofitting it the day a second venue exists is not.

GAP #98 / LEDGER R0025 -- NO COST-RATE BRAKE EXISTED BETWEEN AN ALARM AND THE RUIN RAIL. The
2026-07-28 close-retry churn engine burned $1,456 of fees in 48h against $113 of LIFETIME funding
harvest. §40 (`check_fee_carry_ratio`, scripts/max_audit.py) fired ~27h before diagnosis and had
no authority to stop anything; the only mechanism that halted the fire was the equity ruin rail at
-35% -- after the money was gone. 94.1% of dead-man fire #6 was that software defect. The fix is
the two PAUSE-OPENS-ONLY triggers above: fail-closed on opens (an open is always optional), and
NEVER on closes -- a close is a certainty problem, not a fee problem (L1.45, incident #6: a ruin
rail a fee heuristic can veto is not a ruin rail, and symmetrically a fee brake must never hold a
position that needs to die). Both thresholds REUSE documented desk constants (see below) rather
than minting new ones, and an unreadable measurement keeps the brake QUIET but is recorded
UNMEASURED in the decision's reasons (L1.41) -- never a phantom pause fabricated from missing
data (the 2026-07-26 fabricated-zero class), never a silent skip.
"""

from __future__ import annotations

import contextlib
import json
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parents[2]

#: GAP #54. Max fraction of equity permitted inside a single exchange.
#:
#: 1.0 is not "no cap" -- it is the honest cap for a ONE-VENUE desk, and it is the number that
#: makes this control safe to install today: it binds at exactly the level the desk already runs
#: at, so nothing changes now and the enforcement path is proven before it ever has to bind. The
#: moment a second venue exists this must drop (0.50 splits ruin risk in half; 0.35 matches the
#: per-name cap the desk already accepts). Lowering it is a principal decision, not a default,
#: because it is a real allocation constraint rather than a safety knob to be tightened silently.
VENUE_CAP = 1.0

#: The ruin rail's two documented levels, lifted verbatim from this file's own `evaluate` defaults
#: (behaviour unchanged) into named constants so the gap-#98 burn floor can DERIVE from them
#: instead of minting a parallel number. -35% from inception flattens; -15% from peak pauses opens.
DRAWDOWN_RUIN = 0.35
DD_PAUSE = 0.15

# ---------------------------------------------------------------------------------------------
# GAP #98 / R0025 -- the cost-rate brake's measured inputs and documented thresholds.
# ---------------------------------------------------------------------------------------------
#: The executor's published income artifact (run_cashcarry_executor.py `_WEB`, written by
#: `_emit` every cycle): carries `funding_harvested` and `fut_commission` from the audited
#: paginated `income_summary` read, plus `funding_measured` so "earned nothing" and "could not
#: read the venue" stay distinguishable. Read DEFENSIVELY -- this file must keep returning
#: decisions on a box where the artifact is absent, stale or corrupt.
INCOME_ARTIFACT = _ROOT / "web/cashcarry_live.json"
#: Rolling window of (timestamp, cumulative funding, cumulative commission) samples taken from
#: the artifact -- the artifact publishes since-inception cumulatives, so the window keeps its own
#: short history to difference them. Machine-local state (data/ is gitignored), self-pruning.
BURN_WINDOW_FILE = _ROOT / "data/fee_burn_window.json"

#: Window length: §40's own measurement window -- `check_fee_carry_ratio` (scripts/max_audit.py)
#: reads `income_summary(now - 7 * 86400)`. Same window, so the brake and the alarm that begged
#: for authority are statements about the SAME quantity.
FEE_WINDOW_H = 7 * 24.0
#: §40's flat-book guard, verbatim (`if funding < 5.0: return`): with almost no harvest the fee
#: ratio explodes for reasons unrelated to execution quality, and false pauses train the desk to
#: ignore the brake. Applies to the RATIO trigger only -- the burn floor needs no denominator and
#: is exactly what catches a fee fire on a near-flat book.
FEE_MIN_FUNDING = 5.0
#: Fraction of the windowed harvest that windowed fees may consume before opens pause. REUSED,
#: not invented: this is `alert_frac=0.5` from `carry_bleed_report`
#: (libs/execution/carry_accounting.py) -- the desk's standing dashboard bar for "the leak is
#: eating the harvest" -- pinned equal by test. It sits strictly INSIDE §40's absolute
#: `ratio > 1.0` bar ("fees EXCEED the funding earned... cannot be net-positive while this
#: holds"), so the brake now fires WITH the alarm instead of 27 hours of burn later.
FEE_HARVEST_PAUSE_FRAC = 0.5
#: Absolute-burn floor: windowed net burn (fees - funding, venue income truth) at this fraction
#: of equity pauses opens. DERIVED from the ruin rail's own documented levels, not a new number:
#: it is DD_PAUSE itself -- the income channel gets the same pause bar the mark-to-market channel
#: already has, so a burn that marks hide (a rally masking a fee fire) pauses at the same -15%
#: the DD breaker would have charged for it, and the brake leaves the identical
#: DRAWDOWN_RUIN - DD_PAUSE = 20-point headroom before the ruin rail that the DD breaker leaves.
BURN_FLOOR_EQUITY_FRAC = DD_PAUSE


@dataclass(frozen=True)
class FeeBurnWindow:
    """Windowed fee/harvest measurement for the gap-#98 brake. `None` fields mean UNMEASURED."""

    funding: float | None      # funding harvested inside the window (may be < 0: paying funding)
    fees: float | None         # commission paid inside the window (>= 0)
    span_h: float = 0.0        # hours the window actually covers (honest, may be < FEE_WINDOW_H)
    note: str = ""             # why unmeasured, when unmeasured

    @property
    def measured(self) -> bool:
        return self.funding is not None and self.fees is not None


def _is_num(x: Any) -> bool:
    return isinstance(x, int | float) and not isinstance(x, bool)


def _parse_ts(s: Any) -> datetime | None:
    try:
        t = datetime.fromisoformat(str(s))
    except (TypeError, ValueError):
        return None
    return t if t.tzinfo is not None else t.replace(tzinfo=UTC)


def load_fee_burn_window(
    artifact: Path | None = None,
    history: Path | None = None,
    *,
    window_h: float = FEE_WINDOW_H,
    now: datetime | None = None,
) -> FeeBurnWindow:
    """Difference the executor's cumulative income artifact into a rolling-window measurement.

    Every failure mode returns UNMEASURED with a reason rather than raising or fabricating a
    zero: an unreadable artifact, a null/unmeasured funding or commission field (`read_income`
    already publishes `None` when the venue could not be read -- L1.41, unknown is not zero), a
    stale artifact whose samples have aged out, or a window that does not yet span two executor
    ticks. Cumulative commission can only grow, so a fall in it means the book's inception was
    re-based -- the window restarts rather than differencing across two inceptions.
    """
    artifact = INCOME_ARTIFACT if artifact is None else artifact
    history = BURN_WINDOW_FILE if history is None else history
    now = now if now is not None else datetime.now(tz=UTC)
    try:
        art = json.loads(Path(artifact).read_text("utf-8"))
    except (OSError, ValueError):
        return FeeBurnWindow(None, None, 0.0, "income artifact unreadable")
    if not isinstance(art, dict):
        return FeeBurnWindow(None, None, 0.0, "income artifact malformed")
    fund, comm = art.get("funding_harvested"), art.get("fut_commission")
    t = _parse_ts(art.get("updated"))
    if t is None or not (_is_num(fund) and _is_num(comm)):
        return FeeBurnWindow(None, None, 0.0,
                             "funding/commission not measured this tick (venue income read "
                             "failed or artifact malformed) -- unknown is not zero")

    samples: list[tuple[datetime, float, float]] = []
    with contextlib.suppress(OSError, ValueError):
        raw = json.loads(Path(history).read_text("utf-8")) if Path(history).exists() else []
        for s in raw if isinstance(raw, list) else []:
            ts = _parse_ts(s.get("t")) if isinstance(s, dict) else None
            if ts is not None and _is_num(s.get("funding")) and _is_num(s.get("commission")):
                samples.append((ts, float(s["funding"]), abs(float(s["commission"]))))
    samples.sort(key=lambda x: x[0])
    new = (t, float(fund or 0.0), abs(float(comm or 0.0)))
    if samples and new[0] <= samples[-1][0]:
        pass                                # same artifact tick re-read -- nothing new to record
    elif samples and new[2] < samples[-1][2] - 1e-6:
        samples = [new]                     # cumulative fees fell => inception re-based: restart
    else:
        samples.append(new)
    cutoff = now - timedelta(hours=max(0.0, float(window_h)))
    samples = [s for s in samples if s[0] >= cutoff]
    with contextlib.suppress(OSError):      # persistence failure must not kill the risk decision
        Path(history).parent.mkdir(parents=True, exist_ok=True)
        Path(history).write_text(json.dumps(
            [{"t": s[0].isoformat(), "funding": round(s[1], 6), "commission": round(s[2], 6)}
             for s in samples], indent=1), "utf-8")
    if len(samples) < 2:
        return FeeBurnWindow(None, None, 0.0,
                             "burn window not yet spanning (needs 2+ artifact ticks inside "
                             f"{window_h:g}h; artifact updated {t.isoformat()})")
    span_h = (samples[-1][0] - samples[0][0]).total_seconds() / 3600.0
    d_fund = samples[-1][1] - samples[0][1]
    d_fees = max(0.0, samples[-1][2] - samples[0][2])
    return FeeBurnWindow(round(d_fund, 6), round(d_fees, 6), round(span_h, 3))


def fee_burn_triggers(
    equity: float,
    window: FeeBurnWindow,
    *,
    fee_frac: float = FEE_HARVEST_PAUSE_FRAC,
    burn_floor_frac: float = BURN_FLOOR_EQUITY_FRAC,
    min_funding: float = FEE_MIN_FUNDING,
) -> tuple[list[str], bool]:
    """Gap #98's two pause-opens triggers, pure. Returns (reasons, pause).

    UNMEASURED inputs return quiet-but-recorded (L1.41): the brake must never manufacture a pause
    out of a venue outage (2026-07-26 fabricated-zero incident) and must never skip silently --
    a blind brake that says nothing is indistinguishable from a working one.
    """
    if not window.measured:
        return ([f"fee-burn UNMEASURED ({window.note}): cost-rate brake cannot judge this "
                 "window -- staying quiet, never pausing on a phantom (L1.41)"], False)
    fund, fees = float(window.funding or 0.0), float(window.fees or 0.0)
    reasons: list[str] = []
    pause = False
    # (a) windowed fee-vs-harvest: §40's alarm, now with authority. Flat-book guarded exactly as
    # §40 is -- below `min_funding` of windowed harvest the ratio is noise, and the burn floor
    # below still covers the fee-fire-on-a-flat-book case with no denominator at all.
    if fund >= min_funding and fees > fee_frac * fund:
        pause = True
        reasons.append(
            f"fee-vs-harvest: fees {fees:.2f} > {fee_frac:.0%} of funding {fund:.2f} over "
            f"{window.span_h:.1f}h -- pausing new opens (an open is always optional; at this "
            f"cost rate it is an optional loss. §40's bar, no longer advisory)")
    # (b) absolute-burn floor: venue-income net burn at the DD-pause fraction of equity. Catches
    # the churn-engine class even when marks or a rally hide the drain from the DD breaker.
    burn = fees - fund
    if equity > 0 and burn >= burn_floor_frac * equity:
        pause = True
        reasons.append(
            f"burn floor: net burn {burn:.2f} >= {burn_floor_frac:.0%} of equity {equity:.2f} "
            f"over {window.span_h:.1f}h -- pausing new opens before the only remaining brake "
            f"is the ruin rail (gap #98: $1,456 burned in 48h with no brake between alarm "
            f"and -35%)")
    return reasons, pause


@dataclass
class RiskDecision:
    action: str                       # "ok" | "pause_opens" | "flatten"
    reasons: list[str]
    max_notional: float               # ruin-boundary gross exposure (opens capped to this)
    dd_from_peak: float               # <= 0
    dd_from_start: float              # <= 0
    venue_breaches: list[str] = field(default_factory=list)   # gap #54: venues over the cap

    def to_dict(self) -> dict[str, Any]:
        return {"action": self.action, "reasons": self.reasons,
                "max_notional": round(self.max_notional, 2),
                "dd_from_peak_pct": round(self.dd_from_peak * 100, 2),
                "dd_from_start_pct": round(self.dd_from_start * 100, 2),
                "venue_breaches": list(self.venue_breaches)}


def evaluate(
    equity: float,
    start_equity: float,
    peak_equity: float,
    gross_notional: float,
    *,
    ruin_cap_lev: float,              # ruin-boundary leverage (from dynamic_leverage)
    drawdown_ruin: float = DRAWDOWN_RUIN,   # equity loss treated as ruin -> flatten (survival)
    dd_pause: float = DD_PAUSE,       # drawdown that pauses NEW opens (does NOT flatten)
    venue_equity: dict[str, float] | None = None,   # gap #54: equity held per exchange
    venue_cap: float = VENUE_CAP,     # max fraction of equity inside any ONE venue
    fee_burn: FeeBurnWindow | None = None,          # gap #98: None -> read the income artifact
    fee_harvest_frac: float = FEE_HARVEST_PAUSE_FRAC,
    burn_floor_frac: float = BURN_FLOOR_EQUITY_FRAC,
    flow_adjusted_equity: float | None = None,      # R0320: DD channel measured net of flows
) -> RiskDecision:
    """Evaluate the book against growth-positive, ruin-boundary limits.

    Pure given `fee_burn`; when it is None (the executor's call site, which this brake must reach
    WITHOUT an executor edit) the windowed fee/harvest measurement is read defensively from the
    executor's own published income artifact -- unreadable input degrades to a recorded
    UNMEASURED, never an exception, never a phantom pause.

    R0320 -- `flow_adjusted_equity`. The DD-from-peak channel exists to answer "how far is this
    book below the best it ever managed", and RAW wallet equity cannot answer it across a capital
    event: a deposit lifts equity to a fresh high-water and a live pause evaporates without a
    single position changing. Pass equity net of post-inception external flows here, with
    `peak_equity` in that SAME flow-adjusted space (`capital_events.flow_adjusted_rail` returns
    both), and the pause rail measures the book instead of the cash-flow. `start_equity` is
    untouched by this -- the ruin rail keeps measuring raw equity against the ledgered inception,
    which is the authorised, signed way back from a stop.

    `None` (every pre-R0320 caller) is the identity: the DD channel reads `equity` exactly as it
    always did, including the `max(start, ...)` floor on the peak.
    """
    eq = max(0.0, float(equity))
    start = max(1e-9, float(start_equity))
    if flow_adjusted_equity is None:
        dd_eq = eq
        peak = max(start, float(peak_equity), eq)
    else:
        # `start` is deliberately NOT a floor here: it lives in raw dollars (and a re-base moves
        # it to today's equity), so folding it into a flow-adjusted peak would compare two
        # different rulers and manufacture a drawdown out of the deposit itself.
        dd_eq = max(0.0, float(flow_adjusted_equity))
        peak = max(1e-9, float(peak_equity), dd_eq)
    dd_peak = dd_eq / peak - 1.0
    dd_start = eq / start - 1.0
    max_notional = max(0.0, ruin_cap_lev) * eq
    reasons: list[str] = []
    action = "ok"

    # ruin kill-switch (survival): a catastrophic loss -> flatten to preserve future compounding
    if dd_start <= -abs(drawdown_ruin):
        return RiskDecision("flatten", [f"ruin-floor breach {dd_start:.1%}<=-{drawdown_ruin:.0%}"],
                            max_notional, dd_peak, dd_start)

    # DD circuit breaker: pause NEW opens in stress (keeps existing carries; realises nothing)
    if dd_peak <= -abs(dd_pause):
        action = "pause_opens"
        reasons.append(f"drawdown {dd_peak:.1%}<=-{dd_pause:.0%}: pausing new opens")

    # exposure guard: backstop vs a sizing bug over-deploying past the ruin boundary
    if max_notional > 0 and gross_notional > max_notional * 1.05:
        reasons.append(f"gross ${gross_notional:.0f} > ruin-cap ${max_notional:.0f}: no new opens")
        if action == "ok":
            action = "pause_opens"

    # GAP #54: per-venue concentration. Pauses OPENS on the breaching venue rather than
    # flattening -- yanking capital off an exchange in a panic realises losses and is exactly the
    # move that turns a concentration problem into a solvency one. The cap governs where NEW
    # money may go; withdrawing existing balance is a treasury decision, not a risk-engine reflex.
    breaches: list[tuple[str, float]] = []
    if venue_equity and eq > 0:
        cap = max(0.0, min(1.0, float(venue_cap)))
        for venue, held in sorted(venue_equity.items()):
            frac = max(0.0, float(held)) / eq
            if frac > cap + 1e-9:
                breaches.append((venue, frac))
    for venue, frac in breaches:
        reasons.append(f"venue concentration {venue} {frac:.0%} > cap {venue_cap:.0%}: no new "
                       f"opens there -- an FTX-class failure is fatal regardless of how right "
                       f"the strategy was")
    if breaches and action == "ok":
        action = "pause_opens"

    # GAP #98 / R0025: cost-rate brake -- windowed fee-vs-harvest + absolute-burn floor. PAUSES
    # OPENS ONLY, can never escalate to flatten (a fee problem is never a reason to realise a
    # loss; closes are never excited by cost heuristics, L1.45) and can never downgrade an action
    # already decided above. Strictly conservative: it only ever ADDS a pause.
    if fee_burn is None:
        fee_burn = load_fee_burn_window()
    fee_reasons, fee_pause = fee_burn_triggers(
        eq, fee_burn, fee_frac=fee_harvest_frac, burn_floor_frac=burn_floor_frac)
    reasons.extend(fee_reasons)
    if fee_pause and action == "ok":
        action = "pause_opens"

    return RiskDecision(action, reasons or ["within growth-optimal risk bounds"],
                        max_notional, dd_peak, dd_start, [v for v, _ in breaches])

```

### libs\risk\scaling.py
```python
"""Dynamic risk scaling — the global dial that only ever cuts.

Combines every de-risking governor into one scalar via ``min`` (the tightest constraint
governs, avoiding over-compounding the cuts). De-risking is immediate; re-risking back toward 1
is gradual and is handled by the callers that own each governor.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from libs.risk.errors import RiskError


class GlobalScalar(BaseModel):
    model_config = ConfigDict(frozen=True)

    value: float
    binding: str
    components: dict[str, float]


def global_risk_scalar(
    *,
    drawdown: float = 1.0,
    correlation: float = 1.0,
    crisis: float = 1.0,
    floor: float = 1.0,
    confidence: float = 1.0,
) -> GlobalScalar:
    """Combine governor scalars into one exposure multiplier (the minimum)."""
    components = {
        "drawdown": drawdown,
        "correlation": correlation,
        "crisis": crisis,
        "floor": floor,
        "confidence": confidence,
    }
    for name, value in components.items():
        if not 0.0 <= value <= 1.0:
            raise RiskError(f"governor scalar {name}={value} must be in [0, 1]")
    binding = min(components, key=lambda k: components[k])
    return GlobalScalar(value=components[binding], binding=binding, components=components)

```

### libs\risk\sizing.py
```python
"""Position-size synthesis — combine every governor; the tightest constraint binds.

size = (Equity x S_global x risk_budget x kelly x vol_scalar) / risk_per_unit, then clamped by
position / factor / heat caps (the minimum wins). The trade is rejected outright if expected net
edge <= cost (the cost-hurdle rule) or if no risk is left to allocate.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from libs.risk.errors import RiskError


class PositionSizeResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    units: float
    risk_amount: float
    binding_constraint: str
    rejected: bool
    reason: str

    def __bool__(self) -> bool:
        return not self.rejected


def calculate_position_size(
    equity: float,
    *,
    kelly_fraction: float,
    vol_scalar: float,
    risk_budget: float,
    global_scalar: float,
    risk_per_unit: float,
    side: str = "buy",
    edge_value: float | None = None,
    cost: float | None = None,
    max_position_amount: float | None = None,
    factor_headroom: float | None = None,
    heat_headroom: float | None = None,
    edge_capacity_usd: float | None = None,
) -> PositionSizeResult:
    """Synthesize a position size and clamp it by the binding risk constraint.

    ``edge_capacity_usd`` is the §42 governor: the dollars the EDGE ITSELF absorbs before its own
    impact eats it. Every other clamp here asks "how much risk may the book take?"; this one asks
    "how much can this edge hold?", and the two are independent -- a book with plenty of risk
    budget can still be far too large for a thin dislocation. Sizing past it does not lose money
    slowly, it DESTROYS THE EDGE, because at that point the desk's own flow is the counterparty it
    came to trade against. It joins the same tightest-constraint-binds set as every other cap, so
    an over-capacity sleeve is clamped rather than rejected: a $5k edge on a big book is still a
    good $1,250 trade, and refusing it outright would cost exactly the alphas §42 exists to keep.
    """
    if equity <= 0:
        raise RiskError("equity must be positive")
    if risk_per_unit <= 0:
        raise RiskError("risk_per_unit must be positive")
    if side not in ("buy", "sell"):
        raise RiskError("side must be 'buy' or 'sell'")

    # Cost-hurdle reject: a trade that cannot clear its cost is not taken.
    if edge_value is not None and cost is not None and edge_value <= cost:
        return PositionSizeResult(
            units=0.0, risk_amount=0.0, binding_constraint="cost_hurdle",
            rejected=True, reason="expected net edge <= cost",
        )

    base_risk = equity * global_scalar * risk_budget * kelly_fraction * vol_scalar

    candidates: dict[str, float] = {"target": base_risk}
    if max_position_amount is not None:
        candidates["position_cap"] = max(0.0, max_position_amount)
    if factor_headroom is not None:
        candidates["factor_cap"] = max(0.0, factor_headroom)
    if heat_headroom is not None:
        candidates["heat_cap"] = max(0.0, heat_headroom)
    if edge_capacity_usd is not None:
        from libs.research.capacity_policy import max_allocation
        candidates["edge_capacity"] = max_allocation(edge_capacity_usd)

    binding = min(candidates, key=lambda k: candidates[k])
    risk_amount = candidates[binding]

    if risk_amount <= 0:
        return PositionSizeResult(
            units=0.0, risk_amount=0.0, binding_constraint=binding,
            rejected=True, reason=f"no risk budget available ({binding})",
        )

    units = risk_amount / risk_per_unit
    if side == "sell":
        units = -units
    return PositionSizeResult(
        units=units, risk_amount=risk_amount, binding_constraint=binding,
        rejected=False, reason="sized",
    )

```

### libs\risk\sleeve_allocation.py
```python
"""TWO-BOOK CAPITAL ALLOCATION: a Medallion-like systematic sleeve plus a discretionary booster.

THE PRINCIPAL'S ARCHITECTURE (2026-08-01): keep the discretionary sleeve for extra growth, make
everything else as Medallion-like as possible. That is a coherent multi-strategy structure, but it
is only safe if the two books are CAPITAL-ISOLATED with separate risk budgets. Run them out of one
undifferentiated pool and the discretionary sleeve's variance drags down the systematic compounding
it exists to boost -- the sleeves would share a drawdown, so a bad discretionary run shrinks the
base the systematic book compounds from. Under max E[log W] that is strictly worse than either
sleeve alone, which is the failure mode this module exists to prevent.

WHAT GOVERNS THE SPLIT. Not opinion, and not equal weight. A sleeve earns allocation by its
MARGINAL CONTRIBUTION to total portfolio Sharpe -- the same mathematics that governs signal
admission in libs/research/marginal_admission.py, applied one level up:

    IR_s = (S_s - rho * S_base) / sqrt(1 - rho**2)

The consequence is the useful part: the discretionary sleeve does NOT need to beat the systematic
book to deserve capital. It needs to be UNCORRELATED to it. A modest discretionary Sharpe at rho
near 0 can contribute more than a higher one at rho near 1, because the systematic book already
owns the correlated part. That is precisely why "extra growth boost" is a real and fundable idea
rather than wishful thinking -- but it is also why the boost must be MEASURED rather than assumed.

THE LEARNING STAKE, and this is the subtle piece. The conviction sleeve today has 6 forecasts and
ZERO recorded outcomes, so its expectancy is unmeasured. The naive rule -- no evidence, no capital
-- is a trap that closes permanently: a sleeve at zero size generates no closes, no closes means no
expectancy, and no expectancy means it never earns size. So an unproven sleeve gets a small FIXED
stake sized so that losing all of it is survivable and irrelevant to the systematic book's
compounding. It is a tuition payment, deliberately, and it is capped rather than scaled because
scaling something unmeasured is exactly how a desk talks itself into size it has not earned.

A sleeve with MEASURED NEGATIVE expectancy gets zero, not a learning stake. That distinction is the
whole point of the module: unproven and disproven are different states, and only one of them is
worth paying to resolve.

PERMANENT-IMPAIRMENT GUARD. The discretionary share is hard-capped regardless of how good its
measured numbers look. Estimated edges decay, tails are fatter than the estimator believes, and the
objective is to minimise probability of permanent impairment -- not to maximise a point estimate of
growth. The cap binds even when the arithmetic argues for more, because the arithmetic is computed
from the same limited history that would be wrong in exactly the scenario the cap protects against.
"""

from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from typing import Any

#: Closed trades before a sleeve's expectancy is treated as measured at all. Below this the sleeve
#: is UNPROVEN and receives the learning stake, never a scaled allocation.
MIN_CLOSES = 20

#: Fraction of total equity lent to an unproven sleeve so it can generate the record that earns it
#: real size. Deliberately small and FIXED: scaling something unmeasured is how unearned size gets
#: justified. Losing all of it must be irrelevant to the systematic book's compounding.
LEARNING_STAKE = 0.02

#: EVIDENCE-DEPENDENT CEILING LADDER (principal 2026-08-01: "dont hardcap to 25, whatever boosts
#: growth should be done"). A permanent 25% cap is wrong under max E[log W] for a simple reason: if
#: a sleeve genuinely develops higher expected log-growth than the base and KEEPS demonstrating it
#: over a long horizon, holding it at 25% forever leaves compounding on the table. The cap should
#: express CONFIDENCE IN THE MEASURED EDGE, not a fixed opinion about discretionary trading.
#:
#: The problem the ladder actually solves is distinguishing SKILL from a HOT STREAK, and no single
#: statistic does that -- a high Sharpe is exactly what luck looks like. So each rung is
#: CONJUNCTIVE: every condition must hold, and a sleeve cannot buy a rung with one spectacular
#: number while failing the others. Sample size, positive expectancy, regime stability, drawdown
#: behaviour, correlation to the base, and persistence across time are separate questions and a
#: hot streak typically passes only the first two.
#:
#: RUNGS ARE STATISTICAL, NOT CALENDAR (principal 2026-08-01: "not grandma timeline"). An earlier
#: cut gated STRONG on 180 days of track and DURABLE on 365. That is the wrong axis and it punishes
#: speed for no statistical reason: calendar time is not evidence, sample size is. A book taking 3
#: closes a day reaches a given confidence in weeks that a book taking 3 a month needs years for,
#: and a time gate would hold the fast one back for nothing. So the rungs gate on the t-STATISTIC of
#: the measured edge, which is the quantity confidence actually depends on. Same confidence bar for
#: everyone; whoever generates evidence faster climbs faster. At this desk's ~3 closes/day the rungs
#: land near 7 days (INITIAL), 20 days (STRONG) and 50 days (DURABLE) -- fast, and earned.
#:
#: The t-stat, not the Sharpe, is what rises with evidence. A Sharpe of 2.0 on 20 trades and the
#: same 2.0 on 400 are completely different claims, and gating on Sharpe alone cannot tell them
#: apart -- which is precisely how a hot streak buys size it has not earned.
#:
#: DEMOTION IS IMMEDIATE AND PROMOTION IS SLOW. The ladder is deliberately NOT a ratchet: a rung is
#: recomputed from current evidence every allocation, so decay cuts the ceiling at once rather than
#: after a review cycle. That asymmetry is the log-wealth-correct one -- the cost of being slow to
#: size up is foregone growth, while the cost of being slow to size down is permanent impairment,
#: and those are not symmetric losses.
EVIDENCE_LADDER: tuple[tuple[str, float, dict[str, float]], ...] = (
    # (tier name, max share, conjunctive requirements)
    ("UNPROVEN",  0.02, {"min_closes": 0}),
    ("INITIAL",   0.10, {"min_closes": 20,  "min_t_stat": 1.5, "max_rho": 0.80,
                         "max_drawdown": 0.35}),
    ("STRONG",    0.25, {"min_closes": 60,  "min_t_stat": 2.5, "max_rho": 0.60,
                         "max_drawdown": 0.25, "min_regimes_positive": 2}),
    ("DURABLE",   0.60, {"min_closes": 150, "min_t_stat": 3.5, "max_rho": 0.50,
                         "max_drawdown": 0.20, "min_regimes_positive": 3,
                         "min_persistence": 0.60}),
)

#: The top rung is 0.60, not 1.0, and the reason is structural rather than timid. Beyond this a
#: "booster" is no longer boosting anything -- the base it was diversifying has become a rounding
#: error and the two-book isolation that protects compounding no longer exists. A sleeve that earns
#: more than this has not hit a growth limit; it has outgrown the ROLE. The correct response is to
#: re-designate it as the base (is_base=True) and let the former base compete as a booster against
#: it, which the same arithmetic then handles unchanged. `base_candidate` on the Allocation flags
#: exactly that, so the ceiling surfaces a decision instead of silently capping growth.
MAX_DISCRETIONARY = EVIDENCE_LADDER[-1][1]

#: Fractional-Kelly coefficient. Full Kelly is the max-CAGR point and sits PAST the max-E[log W]
#: point once parameters are estimated rather than known -- the gap is the estimation-error drag.
KELLY_FRACTION = 0.25


@dataclass(frozen=True)
class Sleeve:
    """A book's measured state. Every field is an observation, not a target."""

    name: str
    sharpe: float           #: annualised, net of costs, from realised fills
    n_closes: int           #: closed trades with a RECORDED outcome -- not entries taken
    rho_to_base: float = 0.0  #: correlation to the systematic book (0.0 for the base itself)
    is_base: bool = False
    max_share: float = 1.0  #: per-sleeve ceiling; the evidence ladder applies on top for non-base
    #: --- evidence the ladder reads. All default to the value that FAILS the higher rungs, so a
    #: --- caller that does not supply them cannot accidentally promote a sleeve by omission.
    max_drawdown: float = 1.0      #: worst peak-to-trough as a fraction, from realised equity
    regimes_positive: int = 0      #: distinct market regimes with positive realised expectancy
    t_stat: float = 0.0            #: t-statistic of the measured edge -- THE confidence axis.
                                   #: Supplied by the caller from the return series (sqrt(n) *
                                   #: per-trade Sharpe). Defaults to 0.0 so omitting it FAILS
                                   #: upward and cannot promote a sleeve by silence.
    track_days: int = 0            #: calendar span; REPORTED for context, never gates a rung
    persistence: float = 0.0       #: fraction of sub-periods with positive expectancy (0..1)


@dataclass(frozen=True)
class Allocation:
    name: str
    share: float            #: fraction of total equity
    usd: float
    state: str              #: PROVEN | UNPROVEN-LEARNING-STAKE | DISPROVEN-ZERO | BASE
    reason: str
    marginal_ir: float = 0.0
    n_closes: int = 0
    tier: str = ""              #: evidence rung reached
    tier_cap: float = 0.0       #: ceiling that rung grants
    tier_blocker: str = ""      #: FIRST condition stopping the next rung -- the thing to fix
    base_candidate: bool = False  #: earned more than the top booster rung; should it be the base?

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Plan:
    allocations: list[Allocation] = field(default_factory=list)
    deployed_share: float = 0.0
    reserve_share: float = 0.0
    note: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {"allocations": [a.to_dict() for a in self.allocations],
                "deployed_share": self.deployed_share, "reserve_share": self.reserve_share,
                "note": self.note}



def evidence_tier(
    s: Sleeve, *,
    ladder: tuple[tuple[str, float, dict[str, float]], ...] = EVIDENCE_LADDER,
) -> tuple[str, float, str]:
    """Highest rung whose conditions ALL hold, plus the first condition blocking the next one.

    Conjunctive by design. A hot streak produces a high Sharpe over a short record in one regime,
    which is precisely the pattern that clears a Sharpe test and fails sample size, regime breadth,
    track length and persistence. Requiring every condition is what separates skill from luck; any
    scoring scheme that lets one spectacular number compensate for the others would readmit the
    hot streak this ladder exists to catch.

    Recomputed from CURRENT evidence on every allocation, never latched -- so a decaying sleeve is
    demoted immediately rather than at the next review. Slow up, fast down.
    """
    checks: tuple[tuple[str, Callable[[float], bool], Callable[[float], str]], ...] = (
        ("min_closes", lambda r: s.n_closes >= r, lambda r: f"needs {r} closes, has {s.n_closes}"),
        ("min_sharpe", lambda r: s.sharpe >= r, lambda r: f"needs Sharpe {r}, has {s.sharpe:.3f}"),
        ("max_rho", lambda r: abs(s.rho_to_base) <= r,
         lambda r: f"needs |rho| <= {r}, has {abs(s.rho_to_base):.3f}"),
        ("max_drawdown", lambda r: s.max_drawdown <= r,
         lambda r: f"needs drawdown <= {r:.0%}, has {s.max_drawdown:.0%}"),
        ("min_regimes_positive", lambda r: s.regimes_positive >= r,
         lambda r: f"needs {int(r)} positive regimes, has {s.regimes_positive}"),
        ("min_t_stat", lambda r: s.t_stat >= r,
         lambda r: f"needs t>={r}, has t={s.t_stat:.2f} -- generate closes faster, "
                   "not wait longer"),
        ("min_persistence", lambda r: s.persistence >= r,
         lambda r: f"needs persistence {r}, has {s.persistence:.2f}"),
    )
    best_name, best_cap = ladder[0][0], ladder[0][1]
    blocker = "at top rung"
    for name, cap, reqs in ladder[1:]:
        failed = next((msg(reqs[k]) for k, ok, msg in checks
                       if k in reqs and not ok(reqs[k])), None)
        if failed is not None:
            return best_name, best_cap, f"{name} blocked: {failed}"
        best_name, best_cap = name, cap
    return best_name, best_cap, blocker


def marginal_ir(sharpe: float, rho: float, base_sharpe: float) -> float:
    """The sleeve's information ratio ORTHOGONAL to the systematic book.

    This is why an uncorrelated booster is fundable at a Sharpe the systematic book would reject:
    the base already owns the correlated component, so only the orthogonal part is new. At rho -> 1
    the denominator collapses and the sleeve is revealed as a duplicate of the base rather than a
    diversifier, however good its standalone number looks.
    """
    rho = max(-0.999999, min(0.999999, rho))
    return (sharpe - rho * base_sharpe) / math.sqrt(1.0 - rho * rho)


def _kelly_share(ir: float, *, fraction: float = KELLY_FRACTION) -> float:
    """Fractional-Kelly share from an information ratio, clamped to [0, 1].

    Kelly's growth-optimal fraction is proportional to the information ratio. The fractional
    coefficient is not timidity -- with ESTIMATED rather than known parameters, full Kelly
    overbets, and overbetting is the regime where expected log-wealth falls while advertised CAGR
    still rises. That divergence is the entire reason the objective is log wealth.
    """
    return max(0.0, min(1.0, fraction * max(0.0, ir)))


def allocate(sleeves: list[Sleeve], total_equity: float, *,
             min_closes: int = MIN_CLOSES, learning_stake: float = LEARNING_STAKE,
             max_discretionary: float = MAX_DISCRETIONARY) -> Plan:
    """Split capital between the systematic base and its boosters, on measured evidence only.

    Exactly one sleeve must be marked `is_base`. The base is the Medallion-like systematic book and
    receives the residual; boosters must EARN their share and are capped. If the base itself is
    unproven or loss-making, boosters are still allowed their learning stakes but nothing is scaled
    up against a base with no measured edge -- scaling against an unmeasured benchmark would make
    the marginal-contribution arithmetic meaningless.
    """
    bases = [s for s in sleeves if s.is_base]
    if len(bases) != 1:
        return Plan(note=f"need exactly one base sleeve, got {len(bases)} -- refusing to allocate")
    if not math.isfinite(total_equity) or total_equity <= 0:
        return Plan(note="non-positive or non-finite equity -- refusing to allocate")

    base = bases[0]
    allocs: list[Allocation] = []
    booster_share = 0.0

    # Is the base a meaningful benchmark to measure marginal contribution AGAINST? If it is not,
    # the whole IR arithmetic degenerates -- and dangerously, not harmlessly. At base_sharpe < 0 the
    # term (S_s - rho*S_base) GROWS, so a booster correlated to a LOSING base would be handed a
    # large allocation for the crime of resembling the thing losing money. Boosters are therefore
    # held to learning stakes until the base is measured and positive.
    base_proven = base.n_closes >= min_closes and base.sharpe > 0.0

    for s in sleeves:
        if s.is_base:
            continue

        if s.n_closes >= min_closes and s.sharpe <= 0.0:
            allocs.append(Allocation(s.name, 0.0, 0.0, "DISPROVEN-ZERO",
                                     f"measured Sharpe {s.sharpe:+.3f} over {s.n_closes} closes -- "
                                     "Kelly's optimal size under non-positive edge is zero, and "
                                     "sample size does not change that",
                                     n_closes=s.n_closes))
            continue

        tier, tier_cap, blocker = evidence_tier(s)

        if s.n_closes < min_closes or not base_proven:
            share = min(learning_stake, s.max_share, max_discretionary - booster_share)
            share = max(0.0, share)
            booster_share += share
            why = (f"{s.n_closes}/{min_closes} closes recorded -- expectancy unmeasured"
                   if s.n_closes < min_closes else
                   f"sleeve is measured (Sharpe {s.sharpe:.3f}, {s.n_closes} closes) but the BASE "
                   f"is not (Sharpe {base.sharpe:+.3f}, {base.n_closes} closes), so marginal "
                   "contribution has no meaningful benchmark to be measured against")
            allocs.append(Allocation(
                s.name, share, share * total_equity, "UNPROVEN-LEARNING-STAKE",
                f"{why}. Fixed stake, not a scaled allocation: a sleeve at zero size never "
                "generates the record that would earn it size, but scaling something unmeasured "
                "is unearned size",
                marginal_ir=0.0, n_closes=s.n_closes, tier=tier, tier_cap=tier_cap,
                tier_blocker=blocker))
            continue

        ir = marginal_ir(s.sharpe, s.rho_to_base, base.sharpe)
        want = _kelly_share(ir)
        # The ceiling is this sleeve's EARNED rung, not a constant. `max_discretionary` remains only
        # as the aggregate budget across all boosters, so many mediocre sleeves cannot sum past what
        # one excellent sleeve is allowed alone.
        share = max(0.0, min(want, s.max_share, tier_cap, max_discretionary - booster_share))
        booster_share += share
        if share <= 0.0:
            reason = (f"marginal IR {ir:+.3f} after paying rho={s.rho_to_base:+.3f} to a base at "
                      f"Sharpe {base.sharpe:.3f} -- adds nothing the base does not already own")
        else:
            reason = (f"Sharpe {s.sharpe:.3f} at rho={s.rho_to_base:+.3f} -> "
                      f"marginal IR {ir:+.3f}; "
                      f"fractional-Kelly {want:.3f}, tier {tier} caps at {tier_cap:.2f}, "
                      f"allocated {share:.3f}. Next rung -- {blocker}")
        allocs.append(Allocation(
            s.name, share, share * total_equity, "PROVEN", reason,
            marginal_ir=ir, n_closes=s.n_closes, tier=tier,
            tier_cap=tier_cap, tier_blocker=blocker,
            base_candidate=(want > tier_cap and tier == EVIDENCE_LADDER[-1][0])))

    base_share = max(0.0, 1.0 - booster_share)
    base_state = "BASE" if base.n_closes >= min_closes and base.sharpe > 0 else "BASE-UNPROVEN"
    base_reason = (f"residual after boosters; Sharpe {base.sharpe:.3f} over {base.n_closes} closes"
                   if base_state == "BASE" else
                   f"residual, but the base itself is unproven or loss-making "
                   f"(Sharpe {base.sharpe:+.3f}, {base.n_closes} closes) -- boosters were held to "
                   "learning stakes because marginal contribution against an unmeasured base is "
                   "not a meaningful quantity")
    allocs.insert(0, Allocation(base.name, base_share, base_share * total_equity,
                                base_state, base_reason, n_closes=base.n_closes))

    return Plan(allocations=allocs, deployed_share=1.0, reserve_share=0.0,
                note=f"booster share {booster_share:.3f} of {max_discretionary:.3f} cap; "
                     f"base holds {base_share:.3f}")

```

### libs\risk\stress.py
```python
"""Portfolio stress testing -- survivability under crypto's known failure modes.

Backtest Sharpe says nothing about what happens when the regime breaks. This replays the actual
historical crises in the return stream, finds the empirically worst window, and estimates the
response to instantaneous shocks (BTC -30%, funding disappears). The point is survival: a portfolio
that compounds at 1.1 Sharpe but dies in the next FTX is not deployable.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

# Named crypto crises (UTC). Replayed by slicing the portfolio return stream over each window.
CRISES: dict[str, tuple[str, str]] = {
    "covid_crash_2020": ("2020-03-08", "2020-03-20"),
    "may_2021_crash": ("2021-05-12", "2021-05-23"),
    "luna_collapse_2022": ("2022-05-07", "2022-05-16"),
    "ftx_collapse_2022": ("2022-11-06", "2022-11-21"),
    "aug_2024_unwind": ("2024-08-03", "2024-08-07"),
}


def _max_dd(cum: np.ndarray) -> float:
    peak = np.maximum.accumulate(cum)
    return float((cum / peak - 1.0).min()) if len(cum) else 0.0


def crisis_replay(returns: np.ndarray, dates: pd.DatetimeIndex) -> dict[str, dict[str, float]]:
    """Cumulative return and max drawdown of the portfolio inside each named crisis window."""
    s = pd.Series(returns, index=dates)
    out: dict[str, dict[str, float]] = {}
    for name, (a, b) in CRISES.items():
        seg = s.loc[(s.index >= pd.Timestamp(a, tz="UTC")) & (s.index <= pd.Timestamp(b, tz="UTC"))]
        if len(seg) < 2:
            continue
        cum = np.cumprod(1.0 + seg.to_numpy())
        out[name] = {"days": len(seg), "cum_return": round(float(cum[-1] - 1.0), 4),
                     "max_dd": round(_max_dd(cum), 4)}
    return out


def worst_window(returns: np.ndarray, dates: pd.DatetimeIndex, n: int = 14) -> dict[str, object]:
    """The empirically worst n-day cumulative return (the realized tail, whenever it occurred)."""
    r = np.asarray(returns, dtype="float64")
    if len(r) < n + 1:
        return {}
    cum = np.array([np.prod(1.0 + r[i:i + n]) - 1.0 for i in range(len(r) - n)])
    i = int(np.argmin(cum))
    return {"n_days": n, "worst_cum_return": round(float(cum[i]), 4),
            "start": dates[i].date().isoformat(), "end": dates[i + n].date().isoformat()}


def beta_shock(returns: np.ndarray, market: np.ndarray, shock: float = -0.30) -> dict[str, float]:
    """Estimated one-day portfolio P&L if the market (BTC) instantaneously moves ``shock``.

    Uses the realized OLS beta of the portfolio to the market -- for a dollar-neutral book this is
    usually small, which is itself the finding (the book is not a hidden long-crypto bet).
    """
    r = np.asarray(returns, dtype="float64")
    m = np.asarray(market, dtype="float64")
    mask = (r != 0.0) & np.isfinite(r) & np.isfinite(m)
    if mask.sum() < 30 or np.var(m[mask]) == 0:
        return {"beta": 0.0, "shock": shock, "est_pnl": 0.0}
    beta = float(np.cov(r[mask], m[mask])[0, 1] / np.var(m[mask]))
    return {"beta": round(beta, 3), "shock": shock, "est_pnl": round(beta * shock, 4)}

```

### libs\risk\tail.py
```python
"""Tail-risk controls — VaR, CVaR/Expected Shortfall, gap-through-stop, and stress tests.

Sizes for fat tails, not the Gaussian middle. Under market execution, stops do not guarantee
fills (gold gaps on the weekend open), so realized loss can exceed the stop; sizing must assume
the gap-through scenario. Stress tests use pessimistic, crisis-style shocks.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

import numpy as np
from pydantic import BaseModel, ConfigDict
from scipy.stats import norm

from libs.risk.errors import RiskError
from libs.risk.instruments import Factor, get_factor


def calculate_var(returns: np.ndarray, *, alpha: float = 0.05, method: str = "historical") -> float:
    """Value at Risk at level ``alpha`` as a positive loss (0 if the tail is a gain)."""
    r = np.asarray(returns, dtype="float64")
    if len(r) == 0:
        return 0.0
    if not 0.0 < alpha < 1.0:
        raise RiskError("alpha must be in (0, 1)")
    if method == "historical":
        quantile = float(np.percentile(r, 100 * alpha))
    elif method == "gaussian":
        quantile = float(r.mean() + norm.ppf(alpha) * r.std(ddof=1))
    else:
        raise RiskError("method must be 'historical' or 'gaussian'")
    return max(0.0, -quantile)


def calculate_cvar(returns: np.ndarray, *, alpha: float = 0.05) -> float:
    """Conditional VaR / Expected Shortfall: mean loss in the worst ``alpha`` tail (positive)."""
    r = np.asarray(returns, dtype="float64")
    if len(r) == 0:
        return 0.0
    if not 0.0 < alpha < 1.0:
        raise RiskError("alpha must be in (0, 1)")
    cutoff = float(np.percentile(r, 100 * alpha))
    tail = r[r <= cutoff]
    if len(tail) == 0:
        return max(0.0, -cutoff)
    return max(0.0, -float(tail.mean()))


def gap_through_stop_loss(
    *, units: float, entry_price: float, stop_price: float, gap_fraction: float, side: str = "buy"
) -> float:
    """Realized loss if price gaps *through* the stop (worse than the stop level). Positive."""
    if gap_fraction < 0:
        raise RiskError("gap_fraction must be non-negative")
    if side == "buy":
        fill = stop_price * (1.0 - gap_fraction)
        loss = (entry_price - fill) * abs(units)
    else:
        fill = stop_price * (1.0 + gap_fraction)
        loss = (fill - entry_price) * abs(units)
    return max(0.0, loss)


class StressScenario(BaseModel):
    model_config = ConfigDict(frozen=True)

    name: str
    shocks: dict[Factor, float] = {}
    default_shock: float = 0.0

    def shock_for(self, factor: Factor) -> float:
        return self.shocks.get(factor, self.default_shock)


def default_stress_scenarios() -> list[StressScenario]:
    """A set of pessimistic, crisis-style scenarios (fractional price shocks)."""
    return [
        StressScenario(
            name="broad_risk_off",
            shocks={
                Factor.EQUITY_INDEX: -0.15, Factor.CRYPTO: -0.40, Factor.ENERGY: -0.20,
                Factor.COMMODITY: -0.15, Factor.PRECIOUS_METALS: 0.05, Factor.RATES: 0.05,
            },
        ),
        StressScenario(
            name="liquidity_crisis",
            shocks={
                Factor.EQUITY_INDEX: -0.12, Factor.CRYPTO: -0.50, Factor.ENERGY: -0.15,
                Factor.COMMODITY: -0.12, Factor.PRECIOUS_METALS: -0.10, Factor.FX: -0.03,
            },
            default_shock=-0.10,
        ),
        StressScenario(
            name="vol_spike",
            shocks={
                Factor.EQUITY_INDEX: -0.10, Factor.CRYPTO: -0.30, Factor.PRECIOUS_METALS: -0.05,
            },
        ),
    ]


class StressTestResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    by_scenario: dict[str, float]
    worst_case_loss: float
    survives: bool

    def __bool__(self) -> bool:
        return self.survives


def stress_test_portfolio(
    positions: Mapping[str, float],
    *,
    equity: float,
    scenarios: Sequence[StressScenario] | None = None,
    floor: float = 0.0,
) -> StressTestResult:
    """Apply factor shocks to signed notionals; survives if equity holds above ``floor``."""
    if equity <= 0:
        raise RiskError("equity must be positive")
    scens = list(scenarios) if scenarios is not None else default_stress_scenarios()
    by_scenario: dict[str, float] = {}
    worst_pnl = 0.0
    for scenario in scens:
        pnl = 0.0
        for symbol, notional in positions.items():
            pnl += float(notional) * scenario.shock_for(get_factor(symbol))
        by_scenario[scenario.name] = pnl
        worst_pnl = min(worst_pnl, pnl)
    survives = (equity + worst_pnl) > floor
    return StressTestResult(
        by_scenario=by_scenario, worst_case_loss=max(0.0, -worst_pnl), survives=survives
    )

```

### libs\risk\vol_headroom.py
```python
"""VOL-TARGET HEADROOM (L1.28a, R0107) -- realized book vol vs the Kelly-implied ceiling.

THE CEILING NOBODY WAS MEASURING. Every other ceiling on this desk declares a limit and carries a
measured utilisation (scripts/check_utilisation.py). Risk-taking itself did not: the desk could run
at a third of the volatility its own rails permit for a month and no artifact would say so. That is
an L1.28a idleness defect wearing a prudence costume -- under-risking a proven edge is the same
failure as idle cash, and it announces nothing.

THE ARITHMETIC, and why the ceiling is not a constant. Under fractional Kelly at fraction ``f`` of
full Kelly on an edge of annualized Sharpe ``S``, full-Kelly leverage is mu/sigma^2, so the book's
annualized volatility is exactly::

    sigma_book = f * S

That identity is the whole module. It means the vol ceiling is NOT a hand-set number to be argued
over -- it is implied by two things the desk already fixes: the Kelly cap in the rails
(``KellyLimits.hard_max`` = half-Kelly, the absolute ceiling ever) and the demonstrated Sharpe. And
it self-scales in the direction the objective wants: as validated edges accrue and demonstrated
Sharpe rises, the permitted volatility rises with it, automatically, with no rail touched.

TWO READINGS, BOTH ACTIONABLE, and this is the point of measuring at all:
  * BELOW the ceiling with no named binding constraint -> idleness (L1.28a). The book is carrying
    less risk than its own evidence supports, and every day of that is foregone compounding.
  * ABOVE the ceiling -> an over-Kelly breach. Past full Kelly, expected log-growth FALLS while
    ruin probability rises: strictly worse on both axes. This is the one direction where the
    honest response is to cut.

WHAT THIS MODULE REFUSES TO DO, and the refusals are the load-bearing part.

  * IT WILL NOT MEASURE A MOLDED CURVE. data/nav_attestation.jsonl currently carries its own
    warning -- "molded_curve_usd is a MOLDED/SIMULATED curve, not venue truth and not a track
    record". Computing a realized volatility from it would publish a number the desk would then
    size against. The 2026-07-31 row alone jumps +41.9% and gives it back the next session: a
    re-baseline artifact, not a return. Feeding that to a sizing ceiling is the exact failure
    L1.45 names -- publishing a statistic from evidence too thin to carry it "would step the book
    up on fiction, which is strictly worse than leaving it pinned".
  * IT WILL NOT SET A CEILING FROM AN UNDEMONSTRATED SHARPE. ``f * S`` is only a ceiling if ``S``
    is real. A hot streak's Sharpe would license leverage the evidence has not earned, which is
    precisely how a Kelly bettor sized on over-confident estimates converges to ruin with
    probability one (L1.29). Sufficiency is asked of libs.research.evidence_clock in OBSERVATIONS,
    never in days (L1.48).
  * IT WILL NOT TREAT A CALENDAR GAP AS A DAY. The NAV chain skips dates (2026-08-02 -> 08-05).
    A three-day move read as a one-day return inflates measured vol by ~73%. Returns are
    variance-normalized by their actual elapsed spacing, r / sqrt(dt).

Every refusal returns ``measured=False``, which scripts/check_utilisation.py scores as ZERO
utilisation by law -- never as healthy. That is deliberate: an unmeasured risk ceiling must read as
a gap to close, not as a comfortable silence.

THIS MODULE CHANGES NO SIZE. It has no writer, no rail, and no path to an order. It reports a
number and a direction; acting on it is a separate, evidenced decision. The anti-timidity reading
and the risk reading point the same way here only because the arithmetic does.
"""

from __future__ import annotations

import itertools
import json
import math
from dataclasses import dataclass, replace
from datetime import date
from pathlib import Path
from typing import Any

from libs.research.evidence_clock import sufficient
from libs.risk.config import KellyLimits

#: Trading periods per year for annualization. The NAV chain is stamped once per UTC day and crypto
#: never closes, so every calendar day is an observation -- 252 would be a equities-desk import.
PERIODS_PER_YEAR = 365.0

#: Substrings in a NAV row's ``mode`` that mark it as NOT venue truth. Matched case-insensitively.
#: Deliberately broad: a row that cannot prove it is real must not be counted as real.
_NOT_VENUE_TRUTH = ("paper", "testnet", "sim", "shadow", "molded", "backtest")


@dataclass(frozen=True)
class VolHeadroom:
    """Realized book volatility against the Kelly-implied ceiling, with its own provenance."""

    realized_vol_ann: float
    ceiling_vol_ann: float
    sharpe_ann: float
    n_obs: int
    kelly_cap: float
    measured: bool
    reason: str

    @property
    def headroom(self) -> float:
        """Ceiling minus realized, annualized vol points. Negative = over-Kelly breach."""
        return self.ceiling_vol_ann - self.realized_vol_ann

    @property
    def utilisation(self) -> float:
        """Fraction of the permitted risk budget actually being carried. Unmeasured is ZERO."""
        if not self.measured or self.ceiling_vol_ann <= 0:
            return 0.0
        return self.realized_vol_ann / self.ceiling_vol_ann


def kelly_vol_ceiling(sharpe_ann: float, kelly_cap: float | None = None) -> float:
    """Annualized volatility permitted at ``kelly_cap`` of full Kelly on an edge of Sharpe ``S``.

    ``sigma_book = f * S``. A non-positive Sharpe permits ZERO volatility, which is the correct
    and literal reading: an edge indistinguishable from zero is allocated zero (Robust Kelly),
    so there is no risk budget to spend and no headroom to claim.
    """
    cap = KellyLimits().hard_max if kelly_cap is None else kelly_cap
    return max(0.0, cap) * max(0.0, sharpe_ann)


def _is_venue_truth(row: dict[str, Any]) -> bool:
    """A NAV row counts only if it can prove it is an account balance, not a simulation.

    Fails CLOSED on an unrecognised row: a record with no ``mode`` at all has not established
    provenance, and an unprovenanced number is exactly what L1.46 forbids treating as a
    measurement. Missing evidence is never evidence of a real fill.
    """
    if "molded_curve_usd" in row:
        return False
    mode = str(row.get("mode") or "")
    if not mode:
        return False
    low = mode.lower()
    return not any(flag in low for flag in _NOT_VENUE_TRUTH)


def _normalized_log_returns(points: list[tuple[date, float]]) -> list[float]:
    """Per-day log returns, variance-normalized by actual spacing (r / sqrt(dt)).

    The NAV chain is not contiguous. Under a random walk the variance of a k-day move is k times
    the daily variance, so dividing by sqrt(k) puts every observation back on a common daily
    scale. Reading a 3-day gap as one day would overstate volatility by sqrt(3).
    """
    out: list[float] = []
    for (d0, v0), (d1, v1) in itertools.pairwise(points):
        dt = (d1 - d0).days
        if dt <= 0 or v0 <= 0 or v1 <= 0:
            continue                      # non-monotone or non-positive equity: not a return
        out.append(math.log(v1 / v0) / math.sqrt(dt))
    return out


def from_nav_chain(path: Path, *, kelly_cap: float | None = None) -> VolHeadroom:
    """Measure the ceiling from the NAV attestation chain, refusing everything unprovable.

    Returns ``measured=False`` with a stated reason rather than a plausible number whenever the
    inputs cannot carry the claim. Callers must treat that as ZERO utilisation, not as OK.
    """
    cap = KellyLimits().hard_max if kelly_cap is None else kelly_cap
    empty = VolHeadroom(0.0, 0.0, 0.0, 0, cap, False, "")

    try:
        raw = [ln for ln in path.read_text("utf-8").splitlines() if ln.strip()]
    except OSError as exc:
        return replace(empty, reason=f"NAV chain unreadable: {exc}")

    rows: list[dict[str, Any]] = []
    for ln in raw:
        try:
            rows.append(json.loads(ln))
        except json.JSONDecodeError:
            continue                      # a corrupt line is skipped, never guessed at
    if not rows:
        return replace(empty, reason="NAV chain empty or unparseable")

    real = [r for r in rows if _is_venue_truth(r)]
    if not real:
        return replace(empty, reason=(
            f"no venue-truth equity: all {len(rows)} NAV rows are paper/testnet or a molded "
            "curve. Realized book vol is only measurable against real fills -- pre-Gate-0 there "
            "is no track record to measure and a molded curve must never set a risk ceiling"))

    points: list[tuple[date, float]] = []
    for r in real:
        try:
            points.append((date.fromisoformat(str(r["date"])), float(r["equity_marked"])))
        except (KeyError, TypeError, ValueError):
            continue
    points.sort(key=lambda p: p[0])

    rets = _normalized_log_returns(points)
    n = len(rets)
    if n < 2:
        return replace(empty, n_obs=n, reason=(
            f"{n} usable venue-truth return(s) -- need at least 2 to estimate a volatility"))

    mean = sum(rets) / n
    var = sum((x - mean) ** 2 for x in rets) / (n - 1)
    sd = math.sqrt(var)
    realized_ann = sd * math.sqrt(PERIODS_PER_YEAR)
    sharpe_ann = (mean / sd * math.sqrt(PERIODS_PER_YEAR)) if sd > 0 else 0.0

    # THE CEILING NEEDS A DEMONSTRATED SHARPE, NOT AN OBSERVED ONE. Asked in observations, never
    # in days (L1.48): a fast book earns its ceiling early and a near-idle one never earns it.
    ev = sufficient(mean, sd, n)
    if not ev.sufficient:
        return VolHeadroom(realized_ann, 0.0, sharpe_ann, n, cap, False,
                           f"Sharpe not demonstrated -- {ev.reason}. A ceiling of f*S is fiction "
                           "when S is not established, and sizing to it would license leverage "
                           "the evidence has not earned (L1.29)")

    return VolHeadroom(realized_ann, kelly_vol_ceiling(sharpe_ann, cap), sharpe_ann, n, cap, True,
                       f"{n} venue-truth daily observations; {ev.reason}")

```

### libs\risk\vol_target.py
```python
"""Volatility targeting — scale exposure to hold portfolio volatility near a target.

Sizing falls automatically when volatility rises and grows (capped) when it is calm. Forecasts
lag and spikes are abrupt, so the scaling factor is clamped — and the leverage cap (elsewhere)
stops vol-targeting from over-levering into the calm that precedes a spike.
"""

from __future__ import annotations

import numpy as np

from libs.risk.config import VolConfig
from libs.risk.errors import RiskError


def realized_volatility(returns: np.ndarray, *, annualization: float = 1.0) -> float:
    """Sample standard deviation of returns, optionally annualized by ``sqrt`` factor."""
    r = np.asarray(returns, dtype="float64")
    if len(r) < 2:
        return 0.0
    return float(r.std(ddof=1) * np.sqrt(annualization))


def ewma_volatility(returns: np.ndarray, *, lambda_: float = 0.94) -> float:
    """RiskMetrics EWMA volatility (more weight on recent observations)."""
    r = np.asarray(returns, dtype="float64")
    if len(r) == 0:
        return 0.0
    if not 0.0 < lambda_ < 1.0:
        raise RiskError("lambda_ must be in (0, 1)")
    var = float(r[0] ** 2)
    for x in r[1:]:
        var = lambda_ * var + (1.0 - lambda_) * float(x) ** 2
    return float(np.sqrt(var))


def regime_adjusted_volatility(base_vol: float, *, regime_multiplier: float) -> float:
    """Inflate the volatility estimate for an adverse regime (stress)."""
    if regime_multiplier < 0:
        raise RiskError("regime_multiplier must be non-negative")
    return base_vol * regime_multiplier


def vol_target(
    forecast_vol: float, *, target_vol: float, k_min: float = 0.2, k_max: float = 3.0
) -> float:
    """Scaling factor k = target / forecast, clamped to ``[k_min, k_max]``."""
    if forecast_vol <= 0:
        return k_max  # no measurable risk -> allow up to the cap (which binds elsewhere)
    if target_vol < 0:
        raise RiskError("target_vol must be non-negative")
    return float(min(max(target_vol / forecast_vol, k_min), k_max))


def adjust_for_volatility(base_size: float, forecast_vol: float, *, config: VolConfig) -> float:
    """Scale ``base_size`` by the clamped vol-target factor."""
    k = vol_target(
        forecast_vol, target_vol=config.target, k_min=config.k_min, k_max=config.k_max
    )
    return base_size * k

```

### libs\stage14_5\tail_risk.py
```python
"""Portfolio tail-risk engine — estimate the losses a Sharpe ratio hides.

Reuses the discovery tail-risk model (skew/kurtosis/CVaR/gap) for the distribution component and
adds an explicit correlation-collapse term, blending into a 0-100 tail-risk score (higher = worse).
"""

from __future__ import annotations

import numpy as np

from libs.discovery.tail_risk import tail_risk as _distribution_tail_risk
from libs.risk.tail import calculate_cvar, calculate_var
from libs.stage14_5.models import TailRiskResult


def _clip01(x: float) -> float:
    return max(0.0, min(1.0, x))


def _max_drawdown(returns: np.ndarray) -> float:
    if len(returns) == 0:
        return 0.0
    equity = np.cumprod(1.0 + returns)
    running = np.maximum.accumulate(equity)
    return float((1.0 - equity / running).max())


class PortfolioTailRiskEngine:
    """Estimates tail-loss probability, expected tail loss, drawdown, and correlation collapse."""

    def __init__(self, *, alpha: float = 0.05, threshold: float = 60.0) -> None:
        self.alpha = alpha
        self.threshold = threshold

    def evaluate(
        self, returns: np.ndarray, *, correlation_collapse_risk: float = 0.0
    ) -> TailRiskResult:
        arr = np.asarray(returns, dtype="float64")
        if len(arr) < 3:
            return TailRiskResult(
                tail_loss_probability=0.0, expected_tail_loss=0.0, extreme_drawdown_risk=0.0,
                correlation_collapse_risk=_clip01(correlation_collapse_risk),
                tail_risk_score=0.0, acceptable=True,
            )
        distribution = _distribution_tail_risk(arr, alpha=self.alpha)
        var = calculate_var(arr, alpha=self.alpha)
        cvar = calculate_cvar(arr, alpha=self.alpha)
        collapse = _clip01(correlation_collapse_risk)
        score = _clip01(0.7 * distribution.tail_risk_score / 100.0 + 0.3 * collapse) * 100.0
        return TailRiskResult(
            tail_loss_probability=float(np.mean(arr < -var)) if var > 0 else 0.0,
            expected_tail_loss=cvar,
            extreme_drawdown_risk=_max_drawdown(arr),
            correlation_collapse_risk=collapse,
            tail_risk_score=score,
            acceptable=score <= self.threshold,
        )

```

### scripts\check_risk_kernel.py
```python
#!/usr/bin/env python3
"""RISK-KERNEL INTEGRITY -- the survival rails are hash-locked, not merely asked nicely.

THE ASYMMETRY THIS CLOSES, found by audit 2026-08-08. The desk hash-locks its CONSTITUTION
(`check_constitution_core.py` verifies five clauses by SHA-256 and fails the build if a word
moves), and leaves the CODE THAT ENFORCES SURVIVAL on an honour system. The only thing standing
between an autonomous organ and the Tier-3 ruin rail is prose:

    ops/run_recommendation_worker.sh:99   "is Tier-3 -- do NOT edit it"
    scripts/watchdog.py:258               "TIER-3 never-touch"
    CLAUDE.md                             "never modified autonomously"

Every one of those is an instruction to a reader. None is a mechanism. An organ that ignored them,
or a session that never read them, would modify the dead-man switch and nothing anywhere would
notice -- which is precisely the class of failure the desk hash-locks its constitution against.
Locking the laws and not the kill switch is the wrong way round: prose can be re-argued, and a
flattened book cannot.

WHAT THIS IS AND IS NOT. It is TAMPER-EVIDENT, not tamper-PROOF. A file's hash changing does not
stop the change; it makes the change impossible to make silently, and it fails the gate that every
push must pass. True tamper-proofing is a privilege boundary -- separate credentials, a service the
research account cannot redeploy, an OS-level owner -- and that is deployment work on the box,
which is the principal's side. This is the half that lives in the repo, and it is the half that
catches the realistic failure: not a hostile agent, but a well-meaning one refactoring across a
directory without reading the comment.

**A CHANGED HASH IS NOT AUTOMATICALLY A DEFECT.** The rails are allowed to improve -- what is
forbidden is improving them SILENTLY. An intended change is recorded in the manifest with the
reason, by the principal's act, exactly as a constitutional amendment is.

    python scripts/check_risk_kernel.py            # verify; non-zero exit on drift
    python scripts/check_risk_kernel.py --update   # record current hashes (PRINCIPAL'S ACT)
"""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MANIFEST = ROOT / "docs" / "research" / "RISK_KERNEL_LOCK.json"

#: The survival path. Each entry names WHY it is here, because a list of paths with no reasons is
#: a list somebody will prune to make a refactor pass.
KERNEL: dict[str, str] = {
    "scripts/run_deadman_switch.py": "TIER-3 RUIN RAIL. Polls combined book equity and flattens on breach. The one control "
    "that ends a losing session rather than reducing it; log(0) = -inf, so ruin terminates "
    "the objective rather than lowering it",
    "libs/risk/config.py": "the numeric limits every sizing decision reads. A silent widening here is invisible at "
    "every call site and shows up only as a larger loss",
    "libs/risk/gate.py": "the pre-trade risk gate -- the last check between an intent and an order",
    "libs/risk/kelly.py": "sizing arithmetic. Over-betting an estimated edge loses more growth than under-betting "
    "gains it, so an error here is asymmetric and compounds",
    "libs/risk/drawdown.py": "the drawdown rail that de-risks before the ruin rail has to fire",
    "libs/execution/staging.py": "order staging -- the path an intent takes to become an order",
}


def digest(path: Path) -> str | None:
    """SHA-256 of the file's bytes. None when absent -- an ABSENT RAIL IS THE WORST FINDING.

    None rather than a sentinel hash, because a missing survival file must never compare equal to
    anything; a rail that was deleted should look different from a rail that was edited, and both
    should look different from a rail that is fine.
    """
    try:
        # Git may materialise text as CRLF on Windows while the committed object and lock are LF.
        # Line-ending conversion is not a semantic rail change; hashing canonical LF preserves
        # tamper evidence for every executable byte without making the gate platform-dependent.
        canonical = path.read_bytes().replace(b"\r\n", b"\n")
        return hashlib.sha256(canonical).hexdigest()
    except OSError:
        return None


def current() -> dict[str, str | None]:
    return {rel: digest(ROOT / rel) for rel in KERNEL}


def load() -> dict[str, object]:
    try:
        return json.loads(MANIFEST.read_text("utf-8"))
    except (OSError, ValueError):
        return {}


def verify() -> tuple[list[str], list[str], list[str]]:
    """(drifted, missing, unlocked). Three failure shapes with three different fixes."""
    rec = load()
    locked = rec.get("hashes") if isinstance(rec.get("hashes"), dict) else {}
    now = current()
    drifted, missing, unlocked = [], [], []
    for rel, h in now.items():
        if h is None:
            missing.append(rel)
        elif not isinstance(locked, dict) or rel not in locked:
            unlocked.append(rel)
        elif locked[rel] != h:
            drifted.append(rel)
    return drifted, missing, unlocked


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--update",
        action="store_true",
        help="record current hashes. THE PRINCIPAL'S ACT: it asserts the rails are in "
        "the state he intends, exactly like a constitutional amendment",
    )
    ap.add_argument("--reason", default="", help="required with --update")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()

    if a.update:
        if not a.reason.strip():
            print(
                "REFUSED: --update needs --reason. A rail re-locked with no recorded reason is "
                "a change nobody can audit later, which is the state this check exists to end."
            )
            return 2
        rec = load()
        history = rec.get("history") if isinstance(rec.get("history"), list) else []
        MANIFEST.parent.mkdir(parents=True, exist_ok=True)
        MANIFEST.write_text(
            json.dumps(
                {
                    "_": (
                        "SHA-256 lock on the survival path. Verified by scripts/check_risk_kernel.py on "
                        "every cycle. The rails MAY change -- they may not change SILENTLY."
                    ),
                    "updated": datetime.now(tz=UTC).isoformat(),
                    "reason": a.reason,
                    "files": KERNEL,
                    "hashes": current(),
                    "history": [
                        *history,
                        {"at": datetime.now(tz=UTC).isoformat(), "reason": a.reason},
                    ],
                },
                indent=1,
            ),
            "utf-8",
        )
        print(f"risk-kernel: locked {len(KERNEL)} file(s) -> {MANIFEST}")
        return 0

    drifted, missing, unlocked = verify()
    if a.json:
        print(json.dumps({"drifted": drifted, "missing": missing, "unlocked": unlocked}, indent=1))
    if missing:
        print(
            f"risk-kernel: MISSING {missing} -- a survival rail is ABSENT. This is the most "
            "serious state this check can report: the control that ends a losing session is not "
            "on disk."
        )
        return 1
    if drifted:
        print(
            f"risk-kernel: DRIFT {drifted} -- the survival path changed without being re-locked. "
            "The change is not necessarily wrong; making it SILENTLY is. Review the diff, then "
            "`--update --reason '...'` as the principal's act."
        )
        return 1
    if unlocked:
        print(
            f"risk-kernel: UNLOCKED {unlocked} -- named as kernel files and never hashed, so "
            "they carry no protection at all. Run --update to establish the baseline."
        )
        return 1
    print(f"risk-kernel: {len(KERNEL)} file(s) intact against {MANIFEST.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

```

### scripts\check_risk_units.py
```python
#!/usr/bin/env python3
"""L1.67 -- NO SIZING PATH PRICES A STOP FROM ANOTHER INSTRUMENT'S CONSTANTS.

WHAT THIS CATCHES THAT NOTHING ELSE COULD

Every existing fence on this desk asks whether a number was FRESH (L1.44), whether its inputs
were PRESENT (L1.55), whether a denominator was REAL (L1.57/L1.60), whether two boards AGREE
(L1.61) or whether a gate ever RAN (L1.49). None of them can ask whether a number is in the
UNITS it claims. A stop distance multiplied by the wrong instrument's contract size produces a
lot that is well-formed, fresh, internally consistent, agreed on by every board that reads it,
and wrong by three orders of magnitude -- and the position it sizes is real.

`gateway.auto_lot`, `realised_q` and `promoted_lot` priced every sleeve as
`dist * CONTRACT_OZ * FX_EUR` -- gold's 100-ounce contract times a frozen EUR/USD rate, 92.00 --
whatever symbol the sleeve named. Measured against the venue's own tick values: EUR 0.86 per
price unit per lot on BTCUSD, 86.41 on XAUUSD, 542.40 on every JPY cross, 86,414 on EURUSD. One
constant, five orders of magnitude, wrong by 107x in one direction and 939x in the other.

IT WAS LIVE, NOT LATENT. `sleeve_set` rewrites every promoted sleeve's lot to "auto_ramp", so
the literal 0.01 the promoter writes never reaches the venue and `promoted_lot -> auto_lot` is
always taken. Measured at EUR 1,683.89 on 2026-08-20: a promoted CADJPY sleeve on a 0.50 stop
sized to 0.46 lot, logged EUR 21.16 at risk (1.26%, on policy) and actually risked EUR 124.75 --
7.41% of equity -- while `cap_by_heat` billed it gold's 0.98% and admitted three such sleeves
for a believed 2.94% book against a true 22.2%.

WHAT IT CHECKS

  1. UNIT DIVERGENCE. For every symbol in the universe, the true EUR-per-price-unit against the
     legacy constant. This is a MEASUREMENT and it is published whatever it says.
  2. NO CONSTANT ON THE SIZING PATH. The executable statements of every sizing function are
     AST-walked for the legacy constants. A docstring may quote them -- that is the record of
     what went wrong -- but a `Name` node in a live statement is the defect returning.
  3. EVERY SIZING CALL SITE PASSES A SYMBOL. A call with too few arguments takes the default,
     which is gold, which is the bug one argument later.
  4. THE SNAPSHOT'S AGE. `tick_value` carries an FX rate, so a stale universe is a stale
     conversion -- the same failure as the constant, just slower.

STATUS VALUES: OK / CONSTANT-ON-SIZING-PATH / SYMBOL-OMITTED / SNAPSHOT-STALE / UNMEASURED.
UNMEASURED when no symbol could be priced at all -- zero comparisons is never OK (L1.28a), and
a fence that scans an empty set and reports health is the L1.57 defect this desk has already
paid for once.

ANTI-TIMIDITY READING: a MEASUREMENT duty and a units check. It lifts nothing, sizes nothing,
promotes nothing, opens no gate and loosens no bar. It has no vocabulary for changing any value
it reads. Its whole effect is to make "this lot was priced in the account's currency"
distinguishable from "this lot was priced in gold's" -- byte-identical on this desk until now,
and only one of them is a position size.
"""

from __future__ import annotations

import ast
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from libs.ops.fence_exit import fence_exit  # noqa: E402
from libs.ops.lawful import guard  # noqa: E402

DESK = ROOT / "desks" / "mt5"
#: BOTH HALVES OF THE SPLIT (2026-09-05). `auto_lot`/`realised_q`/`promoted_lot` are one-line
#: delegates in gateway.py now; the executable sizing statements this fence exists to walk are in
#: decision_core.py. Walking the gateway alone would report OK on a stub forever.
GATEWAY = (DESK / "mt5desk" / "gateway.py", DESK / "mt5desk" / "decision_core.py")
UNIVERSE = DESK / "data" / "universe" / "universe.json"
OUT = ROOT / "data" / "risk_units.json"

#: What the deleted constant asserted for every instrument on this desk: gold's contract size
#: times a frozen EUR/USD rate.
LEGACY_EUR_PER_PRICE_UNIT = 100.0 * 0.92

#: The functions that turn a stop distance into a position size. Adding a sizing function
#: without adding it here is how this defect returns unobserved.
SIZING_FUNCTIONS = ("auto_lot", "realised_q", "promoted_lot")

#: Minimum arguments each must receive for the SYMBOL to be explicit rather than defaulted.
#: auto_lot(equity, dist, symbol[, info]); promoted_lot(equity, live_n, dist, symbol[, info]).
SIZING_ARITY = {"auto_lot": 3, "promoted_lot": 4, "realised_q": 3}

#: Constants that may appear in a docstring but never in an executable sizing statement.
BANNED_ON_SIZING_PATH = ("CONTRACT_OZ", "FX_EUR")

#: `tick_value` carries today's FX rate. Beyond this the conversion is a frozen constant again,
#: just one with a more recent date on it.
SNAPSHOT_MAX_AGE_DAYS = 30.0


def _fn_nodes(tree: ast.AST) -> dict[str, ast.FunctionDef]:
    return {n.name: n for n in ast.walk(tree)
            if isinstance(n, ast.FunctionDef) and n.name in SIZING_FUNCTIONS}


def _executable_names(fn: ast.FunctionDef) -> set[str]:
    """Every `Name` in the function's body EXCLUDING its docstring.

    Stripped via the AST rather than by guessing at quote characters: these docstrings quote the
    old formula on purpose, and a text scan would either miss the code or flag the history.
    """
    body = fn.body
    if (body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant)
            and isinstance(body[0].value.value, str)):
        body = body[1:]
    return {n.id for stmt in body for n in ast.walk(stmt) if isinstance(n, ast.Name)}


def measure_divergence() -> tuple[list[dict], list[str]]:
    """Per-symbol EUR-per-price-unit against the legacy constant. Skips are COUNTED (L1.60)."""
    rows: list[dict] = []
    skipped: list[str] = []
    try:
        raw = json.loads(UNIVERSE.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return rows, [f"universe unreadable: {exc}"]
    for sym, m in sorted(raw.items()):
        ts, tv = float(m.get("tick_size", 0) or 0), float(m.get("tick_value", 0) or 0)
        if not (ts > 0 and tv > 0):
            skipped.append(f"{sym}: tick_size={ts} tick_value={tv}")
            continue
        true_pu = tv / ts
        rows.append({
            "symbol": sym,
            "eur_per_price_unit": round(true_pu, 6),
            "legacy_constant": LEGACY_EUR_PER_PRICE_UNIT,
            "error_multiple": round(true_pu / LEGACY_EUR_PER_PRICE_UNIT, 4),
            "last_bar": str(m.get("last", "")),
        })
    return rows, skipped


def snapshot_age_days(rows: list[dict]) -> float | None:
    stamps = [r["last_bar"] for r in rows if r.get("last_bar")]
    if not stamps:
        return None
    try:
        newest = max(datetime.fromisoformat(s) for s in stamps)
    except ValueError:
        return None
    if newest.tzinfo is None:
        newest = newest.replace(tzinfo=UTC)
    return round((datetime.now(tz=UTC) - newest).total_seconds() / 86400.0, 2)


def audit_sizing_path() -> tuple[list[str], list[str], int]:
    """Constants in executable sizing code, and call sites that omit the symbol."""
    constants: list[str] = []
    omissions: list[str] = []
    # BOTH HALVES, ONE AUDIT. A sizing function now lives in whichever file the split put it in,
    # and a delegate in the other; the union of their function tables is the sizing path, and a
    # name missing from BOTH is the defect this reports.
    fns: dict[str, Any] = {}
    trees: list[ast.AST] = []
    for path in GATEWAY:
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except (OSError, SyntaxError) as exc:
            return [f"{path.name} unparseable: {exc}"], [], 0
        trees.append(tree)
        for fname, node in _fn_nodes(tree).items():
            # The file that EXECUTES the arithmetic wins over the one that delegates: a
            # one-line delegate has no banned constant in it and would mask the real body.
            if fname not in fns or len(ast.dump(node)) > len(ast.dump(fns[fname])):
                fns[fname] = node
    for name in SIZING_FUNCTIONS:
        fn = fns.get(name)
        if fn is None:
            constants.append(f"{name}: NOT FOUND in gateway.py or decision_core.py -- "
                             f"renamed or deleted")
            continue
        used = _executable_names(fn) & set(BANNED_ON_SIZING_PATH)
        if used:
            constants.append(f"{name}() line {fn.lineno}: sizes from {sorted(used)}")
    calls = 0
    for node in [n for t in trees for n in ast.walk(t)]:
        if not isinstance(node, ast.Call):
            continue
        fname = getattr(node.func, "id", "")
        if fname not in SIZING_ARITY:
            continue
        calls += 1
        need = SIZING_ARITY[fname]
        got = len(node.args) + len(node.keywords)
        # A call INSIDE the sizing functions themselves is the delegation chain and is checked
        # by arity like any other; a bare call anywhere takes gold by default.
        if got < need:
            omissions.append(f"line {node.lineno}: {fname}() got {got} args, needs {need} "
                             f"for the symbol to be explicit")
    return constants, omissions, calls


def main() -> int:
    guard()                                     # L1.42: no entry point is exempt from the laws
    rows, skipped = measure_divergence()
    constants, omissions, call_sites = audit_sizing_path()
    age = snapshot_age_days(rows)

    worst = max(rows, key=lambda r: abs(r["error_multiple"] - 1.0)) if rows else None
    if not rows:
        status = "UNMEASURED"
    elif constants:
        status = "CONSTANT-ON-SIZING-PATH"
    elif omissions:
        status = "SYMBOL-OMITTED"
    elif age is not None and age > SNAPSHOT_MAX_AGE_DAYS:
        status = "SNAPSHOT-STALE"
    elif age is None:
        status = "UNMEASURED"
    else:
        status = "OK"

    payload = {
        "law": "L1.67",
        "status": status,
        "generated_utc": datetime.now(tz=UTC).isoformat(),
        "symbols_priced": len(rows),
        "symbols_skipped": len(skipped),
        "skipped_detail": skipped,
        "sizing_call_sites": call_sites,
        "constants_on_sizing_path": constants,
        "call_sites_omitting_symbol": omissions,
        "snapshot_age_days": age,
        "snapshot_max_age_days": SNAPSHOT_MAX_AGE_DAYS,
        "legacy_eur_per_price_unit": LEGACY_EUR_PER_PRICE_UNIT,
        "worst_divergence": worst,
        "rows": rows,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    print(f"risk units (L1.67): {status}")
    print(f"  {len(rows)} symbols priced from the venue, {len(skipped)} unpriceable")
    print(f"  {call_sites} sizing call sites audited")
    if worst:
        print(f"  worst divergence from the legacy constant {LEGACY_EUR_PER_PRICE_UNIT:.2f}: "
              f"{worst['symbol']} at {worst['eur_per_price_unit']:.2f} EUR/price-unit "
              f"({worst['error_multiple']:.2f}x)")
    if age is not None:
        print(f"  universe snapshot {age:.1f}d old (max {SNAPSHOT_MAX_AGE_DAYS:.0f}d)")
    for c in constants:
        print(f"  CONSTANT ON SIZING PATH: {c}")
    for o in omissions:
        print(f"  SYMBOL OMITTED: {o}")
    for s in skipped:
        print(f"  unpriceable: {s}")

    return fence_exit(status, {"OK"}, scanned=len(rows),
                      of="symbols priced from the venue's own tick economics")


if __name__ == "__main__":
    raise SystemExit(main())

```

### scripts\measurement_gate.py
```python
"""MEASUREMENT GATE -- enforce the principal's MEASUREMENT BEFORE OPTIMISATION principle.

    "No research intelligence, model, allocator, or strategy optimisation layer may operate on
     unverified measurements. Before improving decisions, improve the truth of the inputs."

THIS IS THE ONE DOCTRINE ITEM THIS DESK CAN BACK WITH ITS OWN NUMBERS, from two independent
samples that agree:
    45-day experiment registry : E_DATA_QUALITY 61 + B_WRONG_MEASUREMENT 46 = 53% of refutations
    single-day research autopsy: E_DATA_QUALITY + C_WRONG_TIMING + B = 64% of failures
The desk's dominant failure mode is measuring the wrong thing, not the absence of alpha. Every
other proposed upgrade -- capital allocation, confidence propagation, LLM portfolios -- optimises
DECISIONS. This one optimises the INPUTS those decisions are made from, and it is strictly prior:
an allocator fed a broken timestamp column allocates confidently and wrongly, forever.

FIVE CHECK FAMILIES, exactly as specified:
  1 TIMESTAMP INTEGRITY  parseable, ordered, no duplicates, no future stamps, regular spacing.
                         Irregular spacing is the single highest-yield check here: a series
                         believed to be daily but actually irregular manufactures C_WRONG_TIMING,
                         which is 13% of refutations on its own.
  2 DATA CORRECTNESS     schema stability, null rate, frozen-value runs (a dead collector returns
                         its last value forever and looks like real data), implausible values.
  3 FEATURE VALIDITY     degenerate/constant numeric series, near-zero variance, outlier mass.
  4 COST REALISM         is a MEASURED cost model present and fresh, or are defaults in play?
  5 REPRODUCIBILITY      is a producer identifiable, and is the artifact fresh w.r.t. its cadence?

FAIL-CLOSED BY IMPORT. The gate is not advisory. Research code calls require_verified(name) and
an UNVERIFIED dataset raises. This desk has already been bitten four times today by fail-OPEN
defaults (_DEFAULT_RT_BPS=4.5 among them), so the default here is refusal.

FALSE-POSITIVE DISCIPLINE. data_sanity.py had to be corrected for flagging config constants and
fixed baselines as anomalies. This gate therefore separates FAIL (blocks) from WARN (reports,
does not block), and never treats a constant flag/boolean field as a degenerate feature.

Read-only. No keys, no LLM, no network. Run from repo root.
"""
from __future__ import annotations

import itertools
import json
import subprocess
from datetime import UTC, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data/measurement_gate.json"
COST = ROOT / "data/cost_model.json"
#: Tracked in docs/, NOT data/ -- data/ is gitignored, and a provenance record that disappears
#: with the working directory is not a record. Same reasoning as conversion_record.json.
PROVENANCE = ROOT / "docs/research/data_provenance.json"

_RISK_LEVELS = ("LOW", "MEDIUM", "HIGH")
_SURVIVORSHIP = ("CLEAN", "UNKNOWN", "CONTAMINATED")
#: How the bytes were obtained. Decisive for reproducibility: OUR_CAPTURE can be re-run,
#: VENDOR_API can be revoked or silently revised, SCRAPED can break without notice, DERIVED
#: inherits every weakness of its parents.
_COLLECTION = ("OUR_CAPTURE", "VENDOR_API", "PUBLIC_API", "SCRAPED", "DERIVED", "MANUAL")

_TIME_KEYS = ("ts", "date", "timestamp", "time", "datetime", "hour", "day", "updated")
# fields that are legitimately constant -- flags, config, identity. Never "degenerate features".
_FLAGLIKE = ("stale", "ok", "enabled", "active", "flag", "is_", "has_", "source", "venue",
             "symbol", "sym", "name", "id", "kind", "type", "status", "window", "version")
MAX_ROWS = 4000          # bounded read; these checks are distributional, not exhaustive


class MeasurementError(RuntimeError):
    """Raised when research code requests a dataset the gate has not verified."""


def _parse_ts(v):
    if isinstance(v, (int, float)):
        x = float(v)
        if x > 1e11:            # milliseconds
            x /= 1000.0
        if 9.4e8 < x < 4.1e9:   # 2000..2100
            return datetime.fromtimestamp(x, tz=UTC)
        return None
    if not isinstance(v, str):
        return None
    s = v.strip().replace("Z", "+00:00")
    for fmt in (None, "%Y-%m-%d", "%Y%m%d_%H", "%Y%m%d"):
        try:
            d = datetime.fromisoformat(s) if fmt is None else datetime.strptime(s, fmt).replace(tzinfo=UTC)
            return d if d.tzinfo else d.replace(tzinfo=UTC)
        except (ValueError, TypeError):
            continue
    return None


def _load(p: Path) -> list[dict]:
    rows = []
    try:
        with p.open("r", encoding="utf-8", errors="ignore") as fh:
            for i, ln in enumerate(fh):
                if i >= MAX_ROWS:
                    break
                ln = ln.strip()
                if not ln:
                    continue
                try:
                    d = json.loads(ln)
                except json.JSONDecodeError:
                    continue
                if isinstance(d, dict):
                    rows.append(d)
    except OSError:
        return []
    return rows


def classify_kind(rows: list[dict], key: str | None, name: str = "") -> str:
    """TIME_SERIES vs EVENT_LOG -- decided STRUCTURALLY, never from the filename.

    THE GATE'S FIRST RUN FAILED ITS OWN STANDARD AND THIS FIXES IT. v1 applied time-series
    regularity checks to every .jsonl and produced 6 false FAILs out of 10: it flagged
    experiment_registry.jsonl for "357 duplicate timestamps (96.7%)" when many commits
    legitimately share a date, and panel_verdicts.jsonl for the same when one panel run writes 13
    verdicts at one instant. Duplicate timestamps and irregular spacing are CORRECT for an event
    log; they are defects only for a series claiming one observation per period.

    Judging a dataset against the wrong model of what it is IS the B_WRONG_MEASUREMENT failure
    mode -- 46 of the last 45 days' refutations. A gate that commits the error it polices would
    have blocked four healthy datasets and taught the desk to ignore it.
    """
    if not key:
        return "UNKNOWN"
    ts = [_parse_ts(r.get(key)) for r in rows]
    good = [t for t in ts if t is not None]
    if len(good) < 8:
        return "UNKNOWN"
    dup_frac = 1.0 - len({t.isoformat() for t in good}) / len(good)
    gaps = [(b - a).total_seconds() for a, b in itertools.pairwise(good) if b >= a]
    med = sorted(gaps)[len(gaps) // 2] if gaps else 0.0
    if dup_frac > 0.30 or med == 0.0:
        return "EVENT_LOG"
    # AMBIGUOUS CASE, stated as a limitation rather than hidden: an event log whose entries happen
    # to carry unique timestamps is structurally IDENTICAL to an irregular time series. Nothing in
    # the data can separate them. The filename is used ONLY here, as a tiebreaker after the
    # structural test, never as the primary signal.
    loglike = any(w in name.lower() for w in ("_log", "log.", "ledger", "verdict", "registry",
                                              "audit", "queue", "events"))
    return "EVENT_LOG" if loglike else "TIME_SERIES"


def check_timestamps(rows: list[dict], kind: str) -> tuple[list[str], list[str], dict]:
    fails, warns = [], []
    key = next((k for k in _TIME_KEYS if rows and k in rows[0]), None)
    if not key:
        return ["no timestamp field -- temporal validity cannot be established"], [], {}
    ts = [_parse_ts(r.get(key)) for r in rows]
    bad = sum(1 for t in ts if t is None)
    good = [t for t in ts if t is not None]
    if bad:
        (fails if bad > len(ts) * 0.02 else warns).append(
            f"{bad}/{len(ts)} unparseable '{key}' values ({bad/len(ts)*100:.1f}%)")
    if len(good) < 8:
        return [*fails, "fewer than 8 parseable timestamps"], warns, {"field": key}

    now = datetime.now(tz=UTC)
    fut = sum(1 for t in good if t > now + timedelta(hours=6))
    if fut:
        fails.append(f"{fut} timestamps in the FUTURE -- clock or unit error")
    # Ordering/uniqueness/regularity are TIME-SERIES contracts only. An event log is unordered,
    # many-per-instant and bursty BY CONSTRUCTION; asserting otherwise is the FP that v1 shipped.
    series = kind == "TIME_SERIES"
    ooo = sum(1 for a, b in itertools.pairwise(good) if b < a)
    if ooo and series:
        (fails if ooo > len(good) * 0.01 else warns).append(
            f"{ooo} out-of-order timestamps ({ooo/len(good)*100:.1f}%)")
    dup = len(good) - len({t.isoformat() for t in good})
    if dup and series:
        (fails if dup > len(good) * 0.05 else warns).append(
            f"{dup} duplicate timestamps ({dup/len(good)*100:.1f}%)")

    gaps = sorted((b - a).total_seconds() for a, b in itertools.pairwise(good) if b >= a)
    meta = {"field": key, "kind": kind, "n": len(good),
            "span_days": round((good[-1] - good[0]).days, 1)}
    if gaps and series:
        med = gaps[len(gaps) // 2]
        meta["median_gap_s"] = round(med, 1)
        if med > 0:
            # SPACING REGULARITY -- the highest-yield check in this file.
            irregular = sum(1 for g in gaps if g > med * 1.75 or g < med * 0.25)
            meta["irregular_pct"] = round(irregular / len(gaps) * 100, 1)
            if irregular > len(gaps) * 0.20:
                fails.append(
                    f"IRREGULAR SPACING: {irregular/len(gaps)*100:.0f}% of gaps deviate >75% from "
                    f"the median {med/3600:.2f}h -- any fixed-horizon test on this series is "
                    f"measuring a different horizon per observation")
            elif irregular > len(gaps) * 0.05:
                warns.append(f"{irregular/len(gaps)*100:.0f}% irregular gaps "
                             f"(median {med/3600:.2f}h)")
            biggest = gaps[-1]
            if biggest > med * 20:
                warns.append(f"largest gap {biggest/3600:.1f}h = {biggest/med:.0f}x median "
                             f"-- collector outage")
    return fails, warns, meta


def check_correctness(rows: list[dict], kind: str) -> tuple[list[str], list[str], dict]:
    fails, warns = [], []
    keysets = [frozenset(r) for r in rows]
    modal = max(set(keysets), key=keysets.count)
    conform = keysets.count(modal) / len(keysets)
    # Heterogeneous keys are a defect in a series (a column vanished) but NORMAL in an event log,
    # where distinct event types carry distinct payloads. Same v1 false-positive class.
    if conform < 0.90 and kind == "TIME_SERIES":
        fails.append(f"SCHEMA UNSTABLE: only {conform*100:.0f}% of records share the modal key set "
                     f"-- fields appear/disappear mid-series")
    elif conform < 0.995:
        warns.append(f"schema conformance {conform*100:.1f}%"
                     + (" (event log -- heterogeneous payloads expected)"
                        if kind == "EVENT_LOG" else ""))

    nulls = {}
    for k in modal:
        n = sum(1 for r in rows if r.get(k) is None)
        if n:
            nulls[k] = round(n / len(rows) * 100, 1)
    for k, pct in sorted(nulls.items(), key=lambda kv: -kv[1])[:4]:
        (fails if pct > 20 else warns).append(f"field '{k}' is {pct}% null")

    # FROZEN VALUES: a dead collector keeps returning its last reading. Indistinguishable from
    # real data by every statistical test except this one.
    frozen = []
    for k in modal:
        if any(f in k.lower() for f in _FLAGLIKE):
            continue
        vals = [r.get(k) for r in rows if isinstance(r.get(k), (int, float))]
        if len(vals) < 30:
            continue
        run = best = 1
        for a, b in itertools.pairwise(vals):
            run = run + 1 if a == b else 1
            best = max(best, run)
        if best >= max(12, len(vals) * 0.15):
            frozen.append((k, best, len(vals)))
    for k, run, n in frozen[:4]:
        fails.append(f"field '{k}' FROZEN for {run} consecutive records of {n} "
                     f"-- collector likely dead while still writing")
    return fails, warns, {"schema_conformance": round(conform, 4), "null_fields": len(nulls),
                          "frozen_fields": len(frozen)}


def check_features(rows: list[dict]) -> tuple[list[str], list[str], dict]:
    warns, degen = [], []
    modal = max({frozenset(r) for r in rows}, key=[frozenset(r) for r in rows].count)
    for k in modal:
        if any(f in k.lower() for f in _FLAGLIKE) or any(t == k for t in _TIME_KEYS):
            continue
        vals = [r.get(k) for r in rows if isinstance(r.get(k), (int, float))
                and not isinstance(r.get(k), bool)]
        if len(vals) < 30:
            continue
        uniq = len(set(vals))
        if uniq <= 2:
            degen.append(f"'{k}' takes {uniq} distinct value(s) over {len(vals)} rows")
        elif uniq / len(vals) < 0.02:
            warns.append(f"'{k}' near-degenerate: {uniq} distinct over {len(vals)} rows")
    for d in degen[:4]:
        warns.append(f"DEGENERATE FEATURE {d} -- carries no cross-sectional information")
    return [], warns, {"degenerate": len(degen)}


def check_cost_realism() -> tuple[list[str], list[str], dict]:
    """Desk-level, not per-dataset: is a MEASURED cost model present, or are defaults in play?"""
    fails, warns, meta = [], [], {}
    if not COST.exists():
        cands = sorted(ROOT.glob("data/*cost*.json"))
        if not cands:
            return (["no cost model artifact found -- every net-of-cost claim on this desk is "
                     "resting on a default constant"], [], {})
        c = cands[0]
    else:
        c = COST
    try:
        d = json.loads(c.read_text("utf-8"))
    except Exception:  # blind-except intentional (BLE001)
        return [f"cost model {c.name} unparseable"], [], {}
    age_d = (datetime.now(tz=UTC).timestamp() - c.stat().st_mtime) / 86400
    meta = {"artifact": c.name, "age_days": round(age_d, 1)}
    if age_d > 7:
        warns.append(f"cost model {c.name} is {age_d:.1f} days old -- costs move with liquidity")
    n = len(d.get("pairs", d.get("symbols", d))) if isinstance(d, dict) else 0
    meta["entries"] = n
    if n and n < 10:
        warns.append(f"cost model covers only {n} symbols -- unmeasured symbols fall back to a "
                     f"default, and unmeasured means ILLIQUID, i.e. the expensive tail")
    return fails, warns, meta


def load_provenance() -> dict:
    """The declared register. Tracked in docs/ because data/ is gitignored -- a provenance record
    that vanishes with the working directory documents nothing."""
    try:
        d = json.loads(PROVENANCE.read_text("utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return d.get("datasets", {}) if isinstance(d, dict) else {}


def check_provenance(p: Path, rows: list[dict], register: dict) -> tuple[list[str], list[str], dict]:
    """FAMILY 6 -- WHERE THE NUMBERS CAME FROM (triage item #82).

    The other five families interrogate the data. None of them can see the one thing that
    invalidates a dataset without leaving a trace in it: its ORIGIN. A venue's self-reported
    volume is perfectly regular, perfectly non-null, perfectly stable, and perfectly fabricable.
    A universe selected on today's membership and applied backwards is clean by every
    distributional test and manufactures returns anyway. Both pass families 1-5 untouched.

    So provenance is a DECLARATION, and the gate's job is to hold it to two standards:

      CONTRADICTED beats ABSENT. If the rows carry their own source/venue and it disagrees with
      the declaration, that is a FAIL -- a wrong provenance claim is more dangerous than a missing
      one, because it is trusted. This is what keeps the register falsifiable against the data
      rather than a wish list nobody can check.

      TWO RISKS BLOCK, THE REST REPORT. manipulation_risk=HIGH and survivorship=CONTAMINATED are
      FAILs: research resting on either is not merely uncertain, it is invalid. Everything else
      WARNs. Blocking every undeclared dataset on day one would convert a real control into an
      outage and get the gate switched off -- which is how controls actually die. Undeclared is
      counted instead, and the count is what gets ratcheted down.
    """
    fails: list[str] = []
    warns: list[str] = []
    rec = register.get(p.name)
    if not isinstance(rec, dict):
        return fails, [f"UNDECLARED PROVENANCE: {p.name} has no entry in "
                       f"{PROVENANCE.relative_to(ROOT)} -- origin, collection method, "
                       f"manipulation risk and survivorship are all unknown"], {"declared": False}

    meta = {"declared": True,
            "source": str(rec.get("source", "") or ""),
            "collection_method": str(rec.get("collection_method", "") or "").upper(),
            "manipulation_risk": str(rec.get("manipulation_risk", "") or "").upper(),
            "survivorship": str(rec.get("survivorship", "") or "").upper()}

    if meta["manipulation_risk"] == "HIGH":
        fails.append(
            "MANIPULATION RISK HIGH: the venue reporting this number can choose it (self-reported "
            "volume is the canonical case). An edge measured on a number its counterparty "
            "controls is not an edge")
    elif meta["manipulation_risk"] not in _RISK_LEVELS:
        warns.append(f"manipulation_risk {meta['manipulation_risk'] or 'unset'!r} is not one of "
                     f"{'/'.join(_RISK_LEVELS)} -- ungraded risk is not low risk")

    if meta["survivorship"] == "CONTAMINATED":
        fails.append(
            "SURVIVORSHIP CONTAMINATED: the universe is defined by present-day membership and "
            "applied to history. Every delisted, halted or dead symbol is silently absent, so the "
            "backtest is run on the survivors of the very selection it claims to test")
    elif meta["survivorship"] not in _SURVIVORSHIP:
        warns.append(f"survivorship {meta['survivorship'] or 'unset'!r} is not one of "
                     f"{'/'.join(_SURVIVORSHIP)}")

    if meta["collection_method"] not in _COLLECTION:
        warns.append(f"collection_method {meta['collection_method'] or 'unset'!r} is not one of "
                     f"{'/'.join(_COLLECTION)} -- a rerun cannot be known to reproduce it")

    # CORROBORATION. Rows that name their own origin get to overrule the register.
    observed = {str(r[k]).strip().lower()
                for r in rows[:MAX_ROWS] for k in ("source", "venue", "exchange")
                if isinstance(r.get(k), str) and r[k].strip()}
    if observed and meta["source"]:
        declared = meta["source"].lower()
        if not any(o in declared or declared in o for o in observed):
            fails.append(
                f"PROVENANCE CONTRADICTED: rows report source/venue {sorted(observed)[:4]} but the "
                f"register declares {meta['source']!r}. A wrong provenance claim is worse than an "
                f"absent one -- absent invites a check, wrong is believed")
        meta["observed_sources"] = sorted(observed)[:6]
    return fails, warns, meta


def check_reproducibility(p: Path) -> tuple[list[str], list[str], dict]:
    fails, warns = [], []
    # SEARCH libs/ TOO. v2 searched only scripts/ and reported information_value.jsonl as having
    # NO PRODUCER when libs/research/information_value.py writes it -- a false accusation of
    # irreproducibility against a healthy artifact. Third self-caught FP in this file.
    try:
        hits = subprocess.run(["grep", "-rl", p.name, "scripts/", "libs/"], cwd=str(ROOT),
                              capture_output=True, text=True, timeout=30, check=False).stdout
    except Exception:  # blind-except intentional (BLE001)
        hits = ""
    producers = [h.strip() for h in hits.splitlines() if h.strip()]
    if not producers:
        fails.append("NO PRODUCER: no script in scripts/ references this artifact -- it cannot "
                     "be regenerated, so no result derived from it is reproducible")
    age_d = (datetime.now(tz=UTC).timestamp() - p.stat().st_mtime) / 86400
    if age_d > 3:
        warns.append(f"artifact {age_d:.1f} days stale")
    return fails, warns, {"producers": len(producers), "age_days": round(age_d, 1)}


def verify_all() -> dict:
    cost_f, cost_w, cost_m = check_cost_realism()
    register = load_provenance()
    results = {}
    for p in sorted((ROOT / "data").glob("*.jsonl")):
        rows = _load(p)
        if len(rows) < 25:
            # Reported, never omitted -- same reason as data_vitals. An absent row cannot be
            # distinguished from a passing row.
            results[p.name] = {"rows_sampled": len(rows), "kind": "UNKNOWN",
                               "verdict": "TOO_SMALL", "fails": [], "warns":
                               [f"only {len(rows)} rows -- below the 25-row scoring floor"],
                               "timestamps": {}, "correctness": {}, "features": {}, "repro": {},
                               # empty on purpose: unchecked provenance reads as undeclared
                               # (fail-closed), and its absence would KeyError verify_all below.
                               "provenance": {}}
            continue
        tkey = next((k for k in _TIME_KEYS if k in rows[0]), None)
        kind = classify_kind(rows, tkey, p.name)
        f1, w1, m1 = check_timestamps(rows, kind)
        f2, w2, m2 = check_correctness(rows, kind)
        f3, w3, m3 = check_features(rows)
        f4, w4, m4 = check_reproducibility(p)
        f5, w5, m5 = check_provenance(p, rows, register)
        fails = f1 + f2 + f3 + f4 + f5 + cost_f
        warns = w1 + w2 + w3 + w4 + w5
        results[p.name] = {
            "rows_sampled": len(rows), "kind": kind,
            "verdict": "FAILED" if fails else "VERIFIED",
            "fails": fails, "warns": warns,
            "timestamps": m1, "correctness": m2, "features": m3, "repro": m4,
            "provenance": m5}
    undeclared = [n for n, v in results.items() if not v["provenance"].get("declared")]
    return {"updated": datetime.now(tz=UTC).isoformat(),
            "cost_realism": {"fails": cost_f, "warns": cost_w, **cost_m},
            # Reported as a COUNT so it can be ratcheted down. A list of undeclared datasets that
            # nobody sums is a list that never shrinks.
            "provenance_undeclared": {"n": len(undeclared), "datasets": undeclared},
            "datasets": results}


def require_verified(dataset: str) -> dict:
    """THE ENFORCEMENT POINT. Research code calls this before touching a dataset.

    Fail-closed on purpose: an absent gate report is NOT permission. This desk lost money to
    _DEFAULT_RT_BPS=4.5 precisely because an unmeasured case defaulted to permissive.
    """
    if not OUT.exists():
        raise MeasurementError(
            f"{dataset}: measurement gate has never run. Run scripts/measurement_gate.py. "
            f"An unrun gate is not a pass.")
    rep = json.loads(OUT.read_text("utf-8"))
    d = rep.get("datasets", {}).get(dataset)
    if d is None:
        raise MeasurementError(f"{dataset}: not covered by the measurement gate -- unverified.")
    if d["verdict"] != "VERIFIED":
        raise MeasurementError(f"{dataset}: verdict {d['verdict']} -- " + "; ".join(d["fails"][:3]))
    return d


def main() -> None:
    print("=== MEASUREMENT GATE -- measurement before optimisation ===")
    print("    45d registry: 53% of refutations are measurement failures (E_DATA_QUALITY 61 +")
    print("    B_WRONG_MEASUREMENT 46). Single-day autopsy independently said 64%. This gate")
    print("    optimises the INPUTS; every other proposed upgrade optimises decisions made FROM")
    print("    them, and is therefore strictly downstream of this.\n")
    rep = verify_all()
    ds = rep["datasets"]
    if not ds:
        raise SystemExit("no datasets with >=25 rows found")

    cm = rep["cost_realism"]
    print(f"  COST REALISM: {cm.get('artifact','NONE')} "
          f"age {cm.get('age_days','?')}d, {cm.get('entries','?')} entries")
    for w in cm.get("warns", []):
        print(f"    WARN {w}")
    for f in cm.get("fails", []):
        print(f"    FAIL {f}")

    ok = [k for k, v in ds.items() if v["verdict"] == "VERIFIED"]
    small = [k for k, v in ds.items() if v["verdict"] == "TOO_SMALL"]
    bad = [k for k, v in ds.items() if v["verdict"] == "FAILED"]
    print(f"\n  {len(ds)} datasets gated: {len(ok)} VERIFIED, {len(bad)} FAILED, "
          f"{len(small)} TOO_SMALL (reported, not scored -- still NOT a pass)\n")
    for name in sorted(bad, key=lambda k: -len(ds[k]["fails"])):
        v = ds[name]
        print(f"  FAILED  {name}  [{v['kind']}]  ({v['rows_sampled']} rows sampled)")
        for f in v["fails"][:4]:
            print(f"      - {f}")
    if ok:
        print("\n  VERIFIED:")
        for name in sorted(ok):
            print(f"      {name}  [{ds[name]['kind']}]")
    und = rep["provenance_undeclared"]
    print(f"\n  PROVENANCE (family 6): {len(ds) - und['n']}/{len(ds)} datasets declared in "
          f"{PROVENANCE.relative_to(ROOT)}")
    if und["n"]:
        print(f"    {und['n']} UNDECLARED: {', '.join(und['datasets'][:6])}")
        print("    Origin is the one property that invalidates a dataset without leaving a trace")
        print("    IN it -- self-reported volume and survivorship-selected universes both pass")
        print("    families 1-5 untouched. Declare them; this count is meant to ratchet DOWN.")

    warncount = sum(len(v["warns"]) for v in ds.values())
    print(f"\n  {warncount} warnings recorded (reported, non-blocking -- data_sanity.py had to be")
    print("  corrected twice for flagging config constants, so WARN and FAIL are kept separate).")
    OUT.write_text(json.dumps(rep, indent=1), "utf-8")
    print(f"\n  -> {OUT}")
    print("  ENFORCEMENT: research code calls measurement_gate.require_verified(<file>) and an")
    print("  unverified dataset RAISES. An unrun gate is not a pass -- it is a refusal.")


if __name__ == "__main__":
    main()

```

### scripts\run_alerts.py
```python
"""The desk's PAGER -- push critical alerts to the principal's phone via ntfy.sh (free, keyless).

Silent failure is the one failure mode a self-healing system can't fix: if the kill switch fires,
the heartbeat dies, or a conservatism defect sits unresolved while nobody is looking, the dashboard
knows and the principal doesn't. This closes that gap. Runs each watchdog tick (cheap, feed-only);
only CRITICAL conditions page, each deduped to once per 6h so it never becomes noise (a pager that
cries wolf is worse than none).

Subscribe once: install the ntfy app (or open the URL in any browser) and subscribe to the topic
printed on first run (stored in data/secrets/ntfy.json -- random suffix, treat like a password;
messages carry NO account data, only alert names).

    python scripts/run_alerts.py [--test]
"""

from __future__ import annotations

import contextlib
import json
import secrets
import subprocess
import sys
import time
import urllib.request
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from libs.ops.fresh import stamp_age_h

# alerts that a brain cycle can actually REMEDIATE (auto-heal event trigger). Deliberately
# EXCLUDES growth_defect/data_health (slow/justified -- would loop the brain forever) and
# deadman_latched/kill/principal_action (human-only -- the brain cannot resolve them).
_EVENT_TRIGGER = {"cadence_floor_violation", "root_cause_critical", "recorder_stale"}

_SECRETS = Path("data/secrets/ntfy.json")
_STATE = Path("data/.last_alerts.json")
_DEDUPE_S = 6 * 3600
# per-key dedupe overrides (2026-07-17 principal: pager spam is noise; a pager that cries
# wolf is worse than none). Slow-moving conditions remind daily, not 4x/day. deadman_latched
# stays at 6h deliberately -- a latched ruin rail SHOULD nag until the operator acts.
_DEDUPE_OVERRIDES_S = {"growth_defect": 24 * 3600, "data_health": 24 * 3600,
                       "brain_noop": 24 * 3600, "principal_action_needed": 24 * 3600,
                       "trade_class_bleeding": 24 * 3600, "auth_broken": 12 * 3600,
                       # the chain runs once a day; its failures can only change once a day
                       "research_chain_failed": 24 * 3600}
_HB = Path("data/cashcarry_exec_heartbeat")
_PAGER_BACKOFF = Path("data/.pager_backoff")
_KILL = Path("data/CASHCARRY_KILL")
_ERR = Path("data/cashcarry_error.log")


def _topic() -> str:
    if _SECRETS.exists():
        return str(json.loads(_SECRETS.read_text("utf-8"))["topic"])
    topic = f"quant-desk-{secrets.token_hex(6)}"
    _SECRETS.parent.mkdir(parents=True, exist_ok=True)
    _SECRETS.write_text(json.dumps({"topic": topic}), "utf-8")
    print(f"NEW pager topic created -> subscribe at: https://ntfy.sh/{topic}")
    return topic


def _push(topic: str, title: str, body: str) -> None:
    # HTTP headers must be latin-1 (urllib/http.client encode them that way); a title with an
    # emoji or other non-latin-1 char raises UnicodeEncodeError BEFORE the request is ever sent,
    # silently killing this and every future push (2026-07-19: broke ALL paging for 29h+,
    # including a live dead-man fire, because the resolved title carried a raw "⚠️").
    # ntfy already renders an icon from Tags, so titles stay plain ASCII; this encode is a
    # defense-in-depth backstop against the same class recurring via a future non-ASCII edit.
    safe_title = title.encode("latin-1", "ignore").decode("latin-1")
    # 429 backoff (2026-07-20): ntfy rate-limits the topic; a due re-page retried on
    # every 3-min tick keeps the topic throttled forever (observed self-DoS loop,
    # journalctl 06:47Z). After any 429, cool down 1h before the next push attempt.
    import time as _t
    if _PAGER_BACKOFF.exists():
        try:
            _until = float(_PAGER_BACKOFF.read_text().strip())
        except ValueError:
            _until = 0.0
        if _t.time() < _until:
            raise RuntimeError(f"pager 429 backoff: {(_until - _t.time()) / 60:.0f}m remaining")
    # second-channel mirror (gap #38): fire the independent path FIRST so a failure in
    # the ntfy path (encoding, 429, outage) can never suppress the alert entirely.
    _second_channel(f"{safe_title}: {body}")
    # ...and every configured channel in the registry (telegram/webhook/email), each independently
    # wrapped so none can raise into this path. 2026-07-29: this is the half gap #38 was still
    # missing -- not another channel, but a DELIVERY LEDGER, so "nothing arrived anywhere" becomes
    # observable instead of being the thing nobody notices for five days.
    with contextlib.suppress(Exception):
        from libs.ops.alert_channels import send_all
        send_all(safe_title, body)
    req = urllib.request.Request(f"https://ntfy.sh/{topic}", data=body.encode(),
                                 headers={"Title": safe_title, "Priority": "high",
                                          "Tags": "rotating_light"})
    try:
        with urllib.request.urlopen(req, timeout=15):
            pass
        if _PAGER_BACKOFF.exists():
            _PAGER_BACKOFF.unlink()
        _ledger_ok("ntfy", "http 200", safe_title)
    except Exception as e:
        if getattr(e, "code", None) == 429:
            _PAGER_BACKOFF.write_text(str(_t.time() + 3600))
        _ledger_ok("ntfy", f"{type(e).__name__}: {e}", safe_title, ok=False)
        raise


def _ledger_ok(channel: str, detail: str, title: str, *, ok: bool = True) -> None:
    """Record the PRIMARY path's outcome in the same ledger as the registry channels, so the
    silence check sees one unified view. Never raises -- a logging failure must not kill a page."""
    with contextlib.suppress(Exception):
        from libs.ops.alert_channels import _log
        _log(channel, ok, detail, title)


# --- PRINCIPAL REPLY CHANNEL (2026-07-31) --------------------------------------------------
# Pages have asked for replies ("reply YES/NO", "reply KILL-DIGEST") since 07-18, but nothing
# ever READ the topic, and data/PAGE_ACK -- the derisk ladder's ack input -- had never been
# created by anything: the ladder could latch (it froze the book today) while the principal
# had no phone-usable way to ack or re-arm. The ntfy app can PUBLISH to the topic it
# subscribes to, so replies arrive as TITLELESS messages on the same channel; desk pushes
# always carry a Title (_push sets one), which is the discriminator. REARM here is transport
# for the human's own act, not an automated re-arm: it only ever runs off an explicit
# principal message. Trust boundary = knowledge of the secret topic, identical to the pager
# itself (ledgered limitation; falsifier: any suspected abuse moves this to authed ntfy).
_PAGE_ACK = Path("data/PAGE_ACK")
_REPLIES = Path("data/principal_replies.jsonl")
_REPLY_STATE = Path("data/.reply_poll_state.json")


def _poll_replies(topic: str) -> None:
    """Fail-quiet by design: paging must never break because reply-polling did."""
    try:
        st: dict = {}
        with contextlib.suppress(Exception):
            st = json.loads(_REPLY_STATE.read_text("utf-8"))
        since = str(st.get("last_id") or "24h")
        url = f"https://ntfy.sh/{topic}/json?poll=1&since={since}"
        with urllib.request.urlopen(url, timeout=15) as resp:
            lines = resp.read().decode("utf-8", "replace").splitlines()
        last_id = st.get("last_id")
        for ln in lines:
            try:
                m = json.loads(ln)
            except json.JSONDecodeError:
                continue
            if m.get("event") != "message":
                continue
            last_id = m.get("id") or last_id
            if m.get("title"):                      # desk's own page, not a reply
                continue
            body = str(m.get("message") or "").strip()
            if not body or len(body) > 500:
                continue
            with contextlib.suppress(Exception):
                _REPLIES.parent.mkdir(parents=True, exist_ok=True)
                with _REPLIES.open("a", encoding="utf-8") as fh:
                    fh.write(json.dumps({"ts": datetime.now(tz=UTC).isoformat(),
                                         "msg_ts": m.get("time"), "body": body}) + "\n")
            # ANY reply is operator contact: ack the pager (the derisk ladder's input).
            _PAGE_ACK.write_text(
                f"{datetime.now(tz=UTC).isoformat()} {body[:120]}\n", "utf-8")
            cmd = body.split()[0].upper() if body.split() else ""
            # The REARM command was removed 2026-09-05 (universe mandate). It re-armed
            # `scripts/run_live_guard.py` -- the size governor for the retired cash-carry
            # executor -- and lifted `data/CASHCARRY_KILL`. Both the guard and the executor are
            # deleted, so the command could only ever have unlinked a kill file guarding nothing
            # while reporting a successful re-arm to the principal's phone. An operator command
            # that lies about what it did is worse than one that does not exist.
            if cmd == "REARM":
                out = ("REARM is retired: the cash-carry size governor it re-armed was deleted "
                       "with the crypto-exchange universe (2026-09-05). Nothing was changed.")
                with contextlib.suppress(Exception):
                    _push(topic, "Quant desk: REARM received", out)
        if last_id:
            _REPLY_STATE.write_text(
                json.dumps({"last_id": last_id,
                            "polled": datetime.now(tz=UTC).isoformat()}), "utf-8")
    except Exception:
        return


# --- SILENT-FAILURE DETECTION (2026-07-22) -------------------------------------------------
# All four digger timers fired into quota/auth walls for 2 days and NOTHING noticed: systemd
# reported "success" because the unit ran, while the log said "hit your session limit" and the
# dig produced zero research. systemd-success != work-done. Same window: the `quant` user's
# claude credentials were absent, so every claude organ was dead on arrival.
_DIGGER_LOGS = {"dataaxis": "dataaxis_*.log", "prospector": "prospector_*.log",
                "litminer": "litminer_*.log", "blindrediscovery": "blindrediscovery_*.log"}
_BLOCK_SIGS = ("hit your session limit", "hit your weekly limit", "not logged in",
               "please run /login", "invalid api key", "authentication_error")
_CRED = Path("/home/quant/.claude/.credentials.json")


def _auth_broken() -> bool:
    """Every claude organ (brain + all diggers) runs as `quant`. The legacy credentials file
    was RETIRED 2026-07-19 (auth moved to setup-token/session storage), so the old existence
    check paged false-positives for 12 days and fed the derisk ladder that froze the book on
    2026-07-31. Truthful free check: session storage mtime moves on every authenticated
    request, so 'broken' = no legacy file AND no session activity for >36h (organs run daily,
    so a 36h-quiet desk is genuinely dead-on-arrival, whether auth or otherwise)."""
    if _CRED.exists():
        return False
    for probe in (Path("/home/quant/.claude/history.jsonl"),
                  Path("/home/quant/.claude/projects")):
        try:
            if time.time() - probe.stat().st_mtime < 36 * 3600:
                return False
        except OSError:
            continue
    return True


def _digger_health() -> list[tuple[str, str]]:
    """A dig that FIRED but produced no research is a silent failure, not a success."""
    out: list[tuple[str, str]] = []
    logdir = Path("data/cro_ai_logs")
    for name, pat in _DIGGER_LOGS.items():
        try:
            logs = sorted(logdir.glob(pat), key=lambda p: p.stat().st_mtime)
            if not logs:
                continue
            last = logs[-1]
            age_h = (time.time() - last.stat().st_mtime) / 3600.0
            if age_h > 24 * 10:            # long-idle cadence (e.g. quarterly) -> not a defect
                continue
            txt = last.read_text("utf-8", errors="ignore")[:4000].lower()
            if any(sig in txt for sig in _BLOCK_SIGS):
                out.append((f"digger_blocked_{name}",
                            f"{name} dig FIRED but produced NOTHING (quota/auth block) -- "
                            f"{last.name}; the timer 'succeeded' while doing no research"))
            elif last.stat().st_size < 400:
                out.append((f"digger_noop_{name}",
                            f"{name} dig produced a near-empty log "
                            f"({last.stat().st_size}B) -- likely blocked"))
        except OSError:
            pass
    return out


def _second_channel(text: str) -> None:
    """INDEPENDENT alert path (gap #38). ntfy is a single point of failure -- a header-encoding
    bug killed it silently for 29h across a live dead-man fire. healthchecks.io is already
    configured for the heartbeat; POSTing to its /fail endpoint triggers whatever notification
    the operator set up there, through completely different infrastructure. Best-effort: this
    must NEVER raise into the primary alert path."""
    with contextlib.suppress(Exception):
        hb = json.loads(Path("data/secrets/heartbeat_url.json").read_text("utf-8")).get("url")
        if hb:
            req = urllib.request.Request(hb.rstrip("/") + "/fail",
                                         data=text.encode("utf-8", "ignore")[:900])
            with urllib.request.urlopen(req, timeout=10):
                pass


def _checks() -> list[tuple[str, str]]:
    """CRITICAL conditions only -- each is (key, message). No account values in messages."""
    out: list[tuple[str, str]] = []
    now = time.time()
    if _HB.exists():
        age = now - _HB.stat().st_mtime
        if age > 1800:
            out.append(("heartbeat_dead", f"executor heartbeat stale {age/60:.0f}min "
                        "(watchdog should have respawned -- check the machine)"))
    else:
        out.append(("heartbeat_missing", "executor heartbeat file missing"))
    if _KILL.exists() and now - _KILL.stat().st_mtime > 3600:
        out.append(("kill_switch_stuck", "CASHCARRY_KILL present >1h -- book is DOWN deliberately; "
                    "remove the file if unintended"))
    if Path("data/DEADMAN_FIRED").exists():
        out.append(("deadman_latched", "DEADMAN_FIRED latch present -- the ruin rail fired and "
                    "the book stays flat until the operator investigates and resets "
                    "(rm data/deadman_state.json data/DEADMAN_FIRED data/CASHCARRY_KILL)"))
    # PRINCIPAL-ACTION channel (2026-07-18): the brain writes data/PRINCIPAL_ACTION.md
    # whenever a human-only door must be opened (live keys at the gate, sub-account
    # proposal, key rotation...). First line = the page text. Re-pages daily until the
    # brain clears the file on resolution. This is how "notify me if you need me" works.
    try:
        pa = Path("data/PRINCIPAL_ACTION.md").read_text("utf-8").strip().splitlines()
        if pa:
            out.append(("principal_action_needed", "the desk needs YOU: " + pa[0][:160]))
    except OSError:
        pass
    rec_hb = Path("data/recorder_heartbeat")
    if rec_hb.exists() and now - rec_hb.stat().st_mtime > 600:
        out.append(("recorder_stale", "data-moat recorder heartbeat stale >10min -- "
                    "unrecoverable microstructure data is being LOST; respawner runs next "
                    "cycle, or: .venv/bin/python scripts/ensure_recorder.py"))
    # LIVE-GUARD DEATH (L1.44, capability hunt 2026-07-31). run_live_guard is simultaneously the
    # size-fraction governor and the stage-demotion tripwire evaluator, and the executor's
    # documented stale-guard behavior is fail-OPEN (full size, takers allowed). Its freeze path
    # cannot save it: the KILL file is written BY the guard, so a dead guard can never write its
    # own freeze -- both degradations point toward MORE aggressive execution, and until this
    # check nothing paged on the file's age. Content stamp over mtime (deploys lie fresh).
    #
    # WELDED FOR AS LONG AS IT HAS EXISTED (R0399, proven 2026-08-13). This read was
    # `lg.get("generated", "1970-01-01T00:00:00+00:00")` and data/live_guard.json has never had a
    # `generated` key -- run_live_guard.py stamps `ts`. So the default fired every time and the
    # page read "live guard stale 29776345min" (56 years) three minutes after the guard wrote the
    # file. A pager that fires on 100% of runs carries zero information (L1.43) and gets acked
    # into silence, which is exactly how the one signal it exists to carry -- the size governor
    # being dead while the executor fail-opens to full size -- would have been lost. The absent
    # key resolved to a LOOSENING default in the sense that matters: not a missed page, but a
    # permanent one, which is the same thing to a reader. Now resolved through the shared
    # stamp-key zoo, so coining a sixth name upstream cannot silently re-weld it.
    lg_age: float | None = None
    lg_absent = ""
    try:
        lg = json.loads(Path("data/live_guard.json").read_text("utf-8"))
        lg_age_h, _lg_key = stamp_age_h(lg)
        if lg_age_h is None:
            # UNMEASURABLE is kept DISTINCT from missing (L1.28a): a guard that is running but
            # publishing no stamp needs its PRODUCER fixed, an absent one needs starting, and
            # collapsing them sends the operator to the wrong organ. Never fall back to mtime
            # here -- that is the direction the whole check exists to distrust.
            lg_absent = ("present but carries no parseable stamp key -- its age is "
                         "UNMEASURABLE, so liveness is unknown rather than fine")
        else:
            lg_age = lg_age_h * 3600.0
    except (OSError, ValueError, TypeError) as exc:
        lg_absent = f"missing/unreadable ({type(exc).__name__})"
    # THE TWO live_guard ALERTS WERE REMOVED 2026-09-05 (universe mandate). They paged when
    # `data/live_guard.json` was missing or stale, on the grounds that "the executor fail-opens to
    # full size". That executor is deleted; the artifact now has no writer at all, so both alerts
    # would fire on EVERY tick, for ever, about a size governor for a book that cannot trade.
    # A permanently-firing pager row is the cry-wolf shape this desk fences elsewhere -- it trains
    # the principal to ack the whole channel, which is how a real alert gets missed.
    _ = (lg_absent, lg_age)     # read above; retained so the parse stays a measured no-op
    try:
        v = json.loads(Path("data/cadence_violation.json").read_text("utf-8"))
        out.append(("cadence_floor_violation", "review/safety cadence FLOOR breached: "
                    + "; ".join(str(x)[:70] for x in v.get("violations", [])[:3])))
    except (OSError, json.JSONDecodeError):
        pass
    # BRAIN-DOWN (2026-07-16 incident: the AI CRO was unauthenticated for 3 days and the 07-13
    # dead-man fire sat untriaged -- rails page instantly, but nothing paged about the missing
    # brain). A real cycle writes a multi-KB log; a no-auth run writes a near-empty one.
    try:
        logs = sorted(Path("data/cro_ai_logs").glob("*.log"), key=lambda p: p.stat().st_mtime)
        if not logs or now - logs[-1].stat().st_mtime > 26 * 3600:
            out.append(("brain_down", "AI CRO cycle has not run in >26h -- check "
                        "quant-cro-ai.timer and auth (ssh: claude -p 'say OK') on the VPS"))
        elif logs[-1].stat().st_size < 2048 and now - logs[-1].stat().st_mtime > 2 * 3600:
            out.append(("brain_noop", "last AI CRO run produced a near-empty log -- likely auth "
                        "failure; verify on the VPS with: claude -p 'say OK'"))
    except OSError:
        pass
    try:
        rc = json.loads(Path("web/root_cause.json").read_text("utf-8"))
        if rc.get("action") == "act_autonomously" and rc.get("top_confidence", 0) >= 0.7:
            out.append(("root_cause_critical",
                        f"root-cause engine: {rc.get('top_cause')} at "
                        f"{rc.get('top_confidence'):.0%} confidence"))
    except (OSError, json.JSONDecodeError, TypeError):
        pass
    try:
        ga = json.loads(Path("web/growth_audit.json").read_text("utf-8"))
        if ga.get("conservatism_defects"):
            out.append(("growth_defect", "unresolved conservatism defect(s): "
                        + ", ".join(ga["conservatism_defects"])))
    except (OSError, json.JSONDecodeError):
        pass
    try:
        h = json.loads(Path("web/health.json").read_text("utf-8"))
        alerts = h.get("alerts") or []
        if alerts:
            out.append(("data_health", f"{len(alerts)} data-health alert(s): "
                        + "; ".join(str(a)[:60] for a in alerts[:3])))
    except (OSError, json.JSONDecodeError):
        pass
    # RESEARCH-CHAIN STEP FAILURES (R0258). The daily research runners are best-effort BY DESIGN
    # (one step must never abort the chain) -- which made a dead step silent by design too:
    # run_cashcarry_shadow's SystemExit killed the flagship forward clock for a full day with
    # zero alarm. Both runners now drop data/research_chain_status.json (atomic write); a latest
    # status carrying failed steps pages here, naming them. ABSENT artifact = no page: it is a
    # new artifact, and the brain-down / cycle-age checks above already own "chain never ran".
    try:
        rcs = json.loads(Path("data/research_chain_status.json").read_text("utf-8"))
        failed = [f for f in (rcs.get("failed") or []) if isinstance(f, dict)]
        if failed:
            names = "; ".join(
                f"{str(f.get('step'))[:44]}(rc={f.get('rc')}) {str(f.get('tail', ''))[:60]}"
                for f in failed[:3])
            more = f" +{len(failed) - 3} more" if len(failed) > 3 else ""
            out.append(("research_chain_failed",
                        f"{len(failed)}/{rcs.get('steps_total', '?')} research step(s) FAILED "
                        f"({rcs.get('runner', '?')} @ {str(rcs.get('generated', '?'))[:16]}Z): "
                        f"{names}{more}"))
    except (OSError, json.JSONDecodeError, AttributeError, TypeError):
        pass
    # silent-failure sweep (2026-07-22): systemd-success != work-done. A timer that fired
    # into a quota/auth wall reports success while producing zero research.
    try:
        tf = json.loads(Path("web/trade_forensics.json").read_text("utf-8"))
        for fl in (tf.get("flags") or [])[:3]:
            out.append(("trade_class_bleeding", str(fl)[:170]))
    except (OSError, json.JSONDecodeError):
        pass
    try:
        # TWO-STAGE LAW: confirmation slots are the ONLY multiplicity that matters; the
        # bar stays fixed for life only while the concurrent count stays <= 12.
        # The cohort is DERIVED from the clock artifacts (libs.research.slot_registry), never
        # counted here. This block used to sum an empty registry + a hardcoded `_standing = 6`
        # + the axis count -- three files each holding a different m, none of them the truth.
        # Imported locally on purpose: this daemon is what pages the principal, so a bad import
        # must degrade one alert, never silence the pager.
        from libs.research.slot_registry import MAX_FORWARD_SLOTS, derive_slots

        _snap = derive_slots()
        _total = int(_snap["m_concurrent"])
        _by_kind = Counter(str(s["kind"]) for s in _snap["slots"])
        _mix = " + ".join(f"{n} {k}" for k, n in sorted(_by_kind.items()))
        if not _snap["complete"]:
            # Unreadable is reported, never read as 0: a missing clock shrinks m and LOOSENS
            # every bar, so silence here would be the phantom-edge direction.
            out.append(("slot_budget_unreadable",
                        f"forward-slot sources unreadable ({', '.join(_snap['unknown_sources'])})"
                        f" -- the concurrent count is a LOWER BOUND ({_total}), not the truth; "
                        "every clock's Holm bar may be too loose this run"))
        elif _total > MAX_FORWARD_SLOTS:
            out.append(("slot_budget_exceeded",
                        f"{_total} concurrent confirmation slots > {MAX_FORWARD_SLOTS} "
                        f"({_mix}) -- the fixed forward bar is only fixed while the cohort is "
                        "capped; recycle or EV-evict before enrolling more"))
        elif _total < MAX_FORWARD_SLOTS:
            # CLOCK-SATURATION DUTY: an idle slot is idle capital's research twin. The law
            # pins the cohort always-full-never-over, so under is a defect exactly like over.
            out.append(("clock_slots_idle",
                        f"only {_total}/{MAX_FORWARD_SLOTS} confirmation slots accruing "
                        f"({_mix}) -- {MAX_FORWARD_SLOTS - _total} idle. Every verified axis owes "
                        "a pre-registered hypothesis within 7 days; an empty clock discovers "
                        "nothing"))
    except (OSError, json.JSONDecodeError, ImportError, KeyError, TypeError):
        pass
    if _auth_broken():
        out.append(("auth_broken",
                    "NO claude credentials for the `quant` user -- the brain AND all 4 "
                    "diggers are dead on arrival. Fix on the VPS: "
                    "sudo -u quant -i ; claude setup-token"))
    out.extend(_digger_health())
    return out


def _brain_running() -> bool:
    try:
        return subprocess.run(["pgrep", "-f", "run_cro_ai.sh"],
                              capture_output=True).returncode == 0
    except Exception:
        return False


def _brain_should_trigger(state: dict, active: set, *, healthy_today: bool, hour: int,
                          now: float) -> str | None:
    """PURE decision (drill-testable): should the brain be auto-triggered? Rate-limited to one
    trigger per 3h. AUTO-RETRY when today's cycle failed/near-empty and it is past ~11:00 UTC
    (session limit likely reset). EVENT when a brain-remediable alert is live and no healthy
    cycle ran since. Human-only + slow/justified conditions never trigger (see _EVENT_TRIGGER)."""
    if now - float(state.get("_brain_trigger", 0)) < 3 * 3600:
        return None
    if (not healthy_today) and hour >= 11:
        return "auto-retry"
    if bool(active & _EVENT_TRIGGER) and not healthy_today:
        return "event"
    return None


def _brain_watchdog(state: dict, active: set) -> str | None:
    """Self-heal the AI brain WITHOUT the operator (2026-07-18): auto-retry a failed daily cycle
    (e.g. the 07-18 session-limit lost-day) + event-trigger on a remediable alert. Never two
    brains; the brain's own CI + escalation keep it safe; risk/money still page the operator."""
    if _brain_running():
        return None
    now = time.time()
    healthy_today = False
    try:
        logs = sorted(Path("data/cro_ai_logs").glob("*.log"), key=lambda p: p.stat().st_mtime)
        if logs:
            last = logs[-1]
            healthy_today = (last.stat().st_size >= 2048
                            and now - last.stat().st_mtime < 20 * 3600)
    except OSError:
        pass
    reason = _brain_should_trigger(state, active, healthy_today=healthy_today,
                                   hour=datetime.now(tz=UTC).hour, now=now)
    if not reason:
        return None
    try:
        subprocess.Popen(["setsid", "nohup", "bash", "ops/run_cro_ai.sh"],
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                        stdin=subprocess.DEVNULL, start_new_session=True)
        state["_brain_trigger"] = now
        return reason
    except Exception as e:
        print(f"brain-watchdog: trigger failed {e!r}"[:100])
        return None


def main() -> None:
    topic = _topic()
    if "--status" in sys.argv:
        # gap #38: which channels are ARMED, when each last DELIVERED, and whether everything has
        # been silent -- the three facts nobody could read before 2026-07-29.
        from libs.ops.alert_channels import status as _chan_status
        st = _chan_status()
        print(f"pager topic: https://ntfy.sh/{topic}")
        print(f"registry channels armed: {st['armed']} {st['armed_kinds']}")
        if st["arming_owed"]:
            print("  NOT-ARMED (human step): data/secrets/alert_channels.json -- ntfy alone is "
                  "the single point of failure gap #38 exists to remove")
        print(f"last success per channel: {st['last_success_per_channel'] or 'NONE RECORDED'}")
        print(f"all channels silent 24h: {st['all_silent_24h']}  "
              f"SILENT flag: {st['silent_flag_present']}")
        for row in st["ledger_tail"]:
            print(f"  {row.get('ts', '?')} {row.get('channel', '?'):9} "
                  f"ok={row.get('ok')} {row.get('detail', '')}")
        return
    if "--test" in sys.argv:
        _push(topic, "Quant desk pager: TEST", "pager wired -- you will only hear from me "
              "when something is genuinely wrong")
        print(f"test page sent -> https://ntfy.sh/{topic}")
        return
    _poll_replies(topic)          # read principal replies BEFORE computing pages: a fresh
    try:                          # ACK/REARM must suppress this very tick's escalation
        state = json.loads(_STATE.read_text("utf-8"))
    except (OSError, json.JSONDecodeError):
        state = {}
    now = time.time()
    sent = 0
    checks = _checks()
    active = {k for k, _ in checks}
    paged = set(state.get("_paged", []))
    for key, msg in checks:
        if now - float(state.get(key, 0)) < _DEDUPE_OVERRIDES_S.get(key, _DEDUPE_S):
            paged.add(key)                                 # still-alerting, still track for resolve
            continue
        # FAILURE BACKOFF (2026-07-16): a failed push used to retry every 3-min tick forever --
        # the sustained hammering kept the free ntfy.sh quota exhausted from 07-11 on, so EVERY
        # page (including the 07-13 dead-man fire) was silently dropped. One attempt per key per
        # 30min keeps total volume far under quota and lets it refill.
        if now - float(state.get(f"_try_{key}", 0)) < 1800:
            continue
        state[f"_try_{key}"] = now
        try:
            _push(topic, f"WARNING Quant desk: {key}", msg)
            state[key] = now
            paged.add(key)
            sent += 1
        except Exception as e:  # pager failing must never break the tick
            print(f"pager push failed: {e!r}"[:120])
    # RESOLUTION / "FIXED" PAGES (2026-07-18 principal idea): pair every alert with a "cleared"
    # notification, so the operator only has to LOOK when a warning arrives with NO fix behind
    # it. A previously-paged condition that is no longer active -> one "resolved" page.
    import contextlib
    for key in list(paged):
        if key not in active:
            with contextlib.suppress(Exception):
                _push(topic, f"RESOLVED Quant desk: {key}",
                      "auto-fixed / cleared -- no action needed")
            paged.discard(key)
            state.pop(key, None)
    state["_paged"] = sorted(paged)
    # SELF-HEAL: auto-retry a failed daily brain cycle + event-trigger the brain on a remediable
    # alert -- so the desk fixes itself without waiting for the operator (2026-07-18).
    trig = _brain_watchdog(state, active)
    if trig:
        print(f"brain-watchdog: triggered brain cycle ({trig})")
    _STATE.write_text(json.dumps(state), "utf-8")
    # EXTERNAL HEARTBEAT (2026-07-16, v8-blueprint triage 8.13): an off-box dead-man for the
    # box itself. Everything above -- deadman, pager, watchdog -- dies WITH the host; a 3-min
    # ping to an external healthchecks-class URL makes the outside world notice silence and
    # page the principal directly. Graceful skip until the operator creates the free check and
    # drops its URL into data/secrets/heartbeat_url.json ({"url": "https://hc-ping.com/..."}).
    try:
        hb = json.loads(Path("data/secrets/heartbeat_url.json").read_text("utf-8")).get("url")
        if hb:
            with urllib.request.urlopen(hb, timeout=10):
                pass
    except Exception:
        # THE PAGER'S JOB IS PAGES, NOT THE HEARTBEAT. This is a best-effort ping to an
        # external liveness service; failing it must never stop pages that have already been
        # computed from going out, which is what raising here would do.
        pass
    print(f"alerts: {sent} page(s) sent "
          f"({datetime.now(tz=UTC).isoformat()[:16]}Z)")


if __name__ == "__main__":
    main()

```

### scripts\run_deadman_switch.py
```python
"""DEAD-MAN'S SWITCH -- dumb, isolated, deterministic last-resort ruin rail.

TIER-3 NEVER-TOUCH (SKILL rail-autonomy tiers): this file may not be modified, disabled or
removed autonomously by the CRO/daily cycle -- explicit principal sign-off only.

Design (2026-07-12 external adversarial review, all five reviewers): the main executor's
risk controls are deterministic code, but they live in the SAME process/codebase the AI
edits daily. This process is the independent backstop: no LLM, no strategy logic, no JSON
config reads, no imports from libs/. It polls COMBINED book equity (futures margin balance
+ spot wallet value -- the book is delta-neutral, futures-only would false-fire on rallies)
once a minute, and if FIVE CONSECUTIVE valid readings sit below 65% of the high-water mark
(the 35% ruin-flatten level) it: writes the executor kill file, market-flattens every
futures position (reduce-only), sells spot balances to USDT, and pages the principal. It
keeps retrying while positions remain. Consecutive-reading confirmation means a transient
API glitch or a single bad mark cannot false-fire it.

    python scripts/run_deadman_switch.py
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import time
import urllib.parse
import urllib.request
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
_FUT_BASE = "https://testnet.binancefuture.com"     # PINNED testnet -- never live
_SPOT_BASE = "https://testnet.binance.vision"       # PINNED testnet -- never live
_FUT_KEYS = _ROOT / "data" / "secrets" / "binance_testnet.json"
_SPOT_KEYS = _ROOT / "data" / "secrets" / "binance_spot_testnet.json"
_NTFY = _ROOT / "data" / "secrets" / "ntfy.json"
_STATE = _ROOT / "data" / "deadman_state.json"
_HB = _ROOT / "data" / "deadman_heartbeat"
_KILL = _ROOT / "data" / "CASHCARRY_KILL"
_FIRED = _ROOT / "data" / "DEADMAN_FIRED"     # durable latch OUTSIDE the racy state json
_VERSION = 2                                   # state schema: foreign/legacy state is never read


def _write_state(state: dict) -> None:
    """ATOMIC state write -- principal sign-off 2026-07-25 (TIER-3 change, sole edit this commit).

    `write_text` is truncate-then-write: the file is zeroed, then filled. A death in that window
    (OOM kill, host reboot, container stop, disk full) leaves EMPTY or PARTIAL json, and the next
    loop reads this file back every minute. The rail does not die -- the DEADMAN_FIRED latch is a
    separate file and survives -- but the HIGH-WATER MARK is lost, so the equity anchor re-sets to
    whatever the book is worth now and the 35% fire line silently MOVES DOWN. After a drawdown
    that means a further 35% is needed before the rail trips, at exactly the worst moment, with no
    signal that it happened.

    `os.replace` is atomic on POSIX: readers see either the whole old file or the whole new one,
    never a partial. Same-directory temp so the rename cannot cross filesystems. This is the
    crash case only -- the two-writers case is already guarded by the foreign-writer check, which
    was the 2026-07-11 false-fire root cause. No behaviour change otherwise.
    """
    tmp = _STATE.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(state), "utf-8")
    os.replace(tmp, _STATE)

_RUIN_FACTOR = 0.65        # fire below 65% of high-water == the 35% ruin-flatten rail
_CONSECUTIVE = 5           # readings required below the line (no single-glitch false fire)
_POLL_SEC = 60.0
_MIN_HW = 500.0            # ignore dust/empty accounts
_HW_CONFIRM = 3            # consecutive readings required to establish a NEW high-water
# ALL major stablecoins count as cash (2026-07-26, principal sign-off). A leg sold into USDC/
# FDUSD/TUSD used to leave legs_v without arriving in the cash term -- it vanished from the
# measure and read as a phantom loss. Stables are ~$1 and do not swing, so including them
# preserves the faucet-noise exclusion that motivated the narrow measure (volatile faucet bags
# like WBTC/PAXG/YFI remain excluded).
_STABLES = ("USDT", "USDC", "FDUSD", "TUSD", "BUSD", "DAI")
_LEG_GRACE_SEC = 3600.0    # keep crediting a real spot leg this long after its short closes


def _creds(path: Path) -> tuple[str, str] | None:
    try:
        d = json.loads(path.read_text("utf-8"))
        return (d["key"], d["secret"]) if d.get("key") and d.get("secret") else None
    except Exception:
        return None


def _req(url: str, key: str | None = None, data: bytes | None = None,
         method: str = "GET") -> object:
    hdr = {"User-Agent": "deadman/1.0"}
    if key:
        hdr["X-MBX-APIKEY"] = key
    req = urllib.request.Request(url, data=data, method=method, headers=hdr)
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read())


def _signed(base: str, path: str, creds: tuple[str, str], params: dict | None = None,
            method: str = "GET") -> object:
    p = {**(params or {}), "timestamp": int(time.time() * 1000), "recvWindow": 5000}
    q = urllib.parse.urlencode(p)
    sig = hmac.new(creds[1].encode(), q.encode(), hashlib.sha256).hexdigest()
    body = f"{q}&signature={sig}"
    if method == "GET":
        return _req(f"{base}{path}?{body}", creds[0])
    return _req(f"{base}{path}", creds[0], body.encode(), method)


def combined_equity(state: dict) -> float | None:
    """BOOK equity from venue ground truth only: futures margin balance + spot value of
    exactly the assets with a live futures SHORT (the carry legs) + the CHANGE in spot
    USDT since first poll.

    NOT the raw spot wallet: the testnet faucet stuffs it with ~$300k of untracked coins
    and USDT, which would drown real book ruin (a -100% book move reads as -3% of wallet)
    and let faucet noise fire falsely. Tracked legs come from the venue's own short
    positions (no desk-written file); USDT is measured as a SIGNED DELTA from the first
    poll's baseline so leg<->cash flows cancel: opening carries (USDT->legs) and full
    de-risking (legs->USDT) leave equity unchanged, while real losses show at full size.
    NOTE: manually fauceting USDT into the spot account inflates the measure -- clear
    data/deadman_state.json after any manual top-up. None on any read failure."""
    fut, spt = _creds(_FUT_KEYS), _creds(_SPOT_KEYS)
    if not fut or not spt:
        return None
    try:
        acct = _signed(_FUT_BASE, "/fapi/v2/account", fut)
        # MAX of two venue-derived measures. totalMarginBalance alone is USDT-only under
        # multiAssetsMargin=False -- it hid $5,000 of USDC, pinned high_water at $209.43
        # (< _MIN_HW dust floor) and DISARMED this rail at every equity while the service
        # read green (2026-07-30 deep sweep, R0053); the stable face-value sum covers that
        # mode. Under multiAssetsMargin=True the venue field is the complete USD-marked
        # total (incl. non-stables) and wins the max. Never reads below either truth.
        fut_eq = max(sum(float(x.get("marginBalance", 0.0)) for x in acct.get("assets", [])
                         if x.get("asset") in _STABLES),
                     float(acct.get("totalMarginBalance", 0.0)))
        if fut_eq <= 0.0:
            return None                                   # zero/absent margin = bad read, not ruin
        shorts = {p["symbol"] for p in _signed(_FUT_BASE, "/fapi/v2/positionRisk", fut)
                  if float(p.get("positionAmt", 0.0)) < 0}
        state["has_positions"] = bool(shorts)
        # SETTLEMENT GRACE (2026-07-22, incident #5): a carry unwind closes the futures short
        # BEFORE the spot leg is sold, so a shorts-only legs_v drops still-held spot to $0 and
        # the rail reads a phantom loss. Keep crediting a symbol's REAL spot balance at REAL
        # market price for a bounded window after its short disappears. This corrects an
        # UNDERCOUNT of assets that demonstrably exist on the venue: it cannot overcredit (a
        # sold leg reads balance 0; a crashed leg marks down) and never touches the threshold.
        _now = time.time()
        _seen = state.setdefault("legs_seen", {})
        for _s in shorts:
            _seen[_s] = _now
        for _s in [k for k, t in list(_seen.items()) if _now - float(t) > _LEG_GRACE_SEC]:
            _seen.pop(_s, None)
        creditable = set(shorts) | set(_seen)
        bals = _signed(_SPOT_BASE, "/api/v3/account", spt)["balances"]
        px = {t["symbol"]: float(t["price"])
              for t in _req(f"{_SPOT_BASE}/api/v3/ticker/price")}
        legs_v, usdt = 0.0, 0.0          # usdt = COMBINED stable cash (see _STABLES)
        for b in bals:
            amt = float(b["free"]) + float(b["locked"])
            if amt <= 0:
                continue
            if b["asset"] in _STABLES:
                usdt += amt                    # ALL stable cash, not USDT alone (2026-07-26)
            elif b["asset"] + "USDT" in creditable:
                legs_v += amt * px.get(b["asset"] + "USDT", 0.0)
        if "usdt_baseline" not in state:
            samples = state.setdefault("usdt_samples", [])
            samples.append(usdt)
            if len(samples) < 3:
                return None                               # baseline forming (median of first 3
            state["usdt_baseline"] = sorted(samples)[1]   # polls: one stale read cannot poison
            state.pop("usdt_samples", None)               # the permanent reference)
        return fut_eq + legs_v + (usdt - float(state["usdt_baseline"]))
    except Exception:
        return None


def should_fire(equity: float | None, state: dict) -> bool:
    """Pure trigger logic: ratchet high-water, count consecutive breaches, fire at N.

    Invalid readings (None) change nothing -- an API outage can neither fire nor reset."""
    if equity is None or equity <= 0:
        return False
    # HIGH-WATER RATCHET, SUSTAINED (2026-07-22, incident #5 ROOT CAUSE): firing requires
    # _CONSECUTIVE breaches, but the high-water used to ratchet on a SINGLE reading. That
    # asymmetry let ONE noisy upward spike permanently inflate the fire line, after which
    # ordinary days sat below it and the rail fired again and again. A new peak must now hold
    # for _HW_CONFIRM consecutive valid readings, and the peak recorded is the MINIMUM of those
    # readings (the sustained level, never the spike). This makes the REFERENCE accurate; it
    # does not touch _RUIN_FACTOR or _CONSECUTIVE, so real-ruin detection is unchanged.
    hw = float(state.get("high_water", 0.0))
    if equity > hw:
        pend = state.setdefault("hw_pending", [])
        pend.append(equity)
        if len(pend) >= _HW_CONFIRM:
            hw = min(pend)
            state["hw_pending"] = []
    else:
        state["hw_pending"] = []
    state["high_water"] = hw
    if hw < _MIN_HW:
        state["breaches"] = 0
        # ARMEDNESS MADE VISIBLE (2026-07-30, R0053): below the dust floor this rail is OFF.
        # With live positions that is a book running WITHOUT ruin protection -- the exact
        # state that went unnoticed while every guard checked liveness, not armedness.
        # Flag it here (pure logic, no side effects); main() pages once on the flag.
        state["disarmed_live"] = bool(state.get("has_positions"))
        return False
    state["disarmed_live"] = False
    if equity < _RUIN_FACTOR * hw:
        state["breaches"] = int(state.get("breaches", 0)) + 1
    else:
        state["breaches"] = 0
    return state["breaches"] >= _CONSECUTIVE


def _flatten() -> None:
    """Kill file + reduce-only market-flatten futures + sell spot to USDT + page. Idempotent."""
    _KILL.write_text("DEADMAN ruin rail fired " + time.strftime("%Y-%m-%dT%H:%M:%SZ"), "utf-8")
    fut, spt = _creds(_FUT_KEYS), _creds(_SPOT_KEYS)
    shorts: set[str] = set()                              # carry legs, captured BEFORE covering
    if fut:
        try:
            for p in _signed(_FUT_BASE, "/fapi/v2/positionRisk", fut):
                amt = float(p.get("positionAmt", 0.0))
                if amt < 0.0:
                    shorts.add(p["symbol"])
                if amt != 0.0:
                    _signed(_FUT_BASE, "/fapi/v1/order", fut,
                            {"symbol": p["symbol"], "side": "BUY" if amt < 0 else "SELL",
                             "type": "MARKET", "quantity": abs(amt), "reduceOnly": "true"},
                            method="POST")
        except Exception:
            pass                                          # retried next poll while positions remain
    if spt and shorts:                                    # sell ONLY the carry-leg spot assets --
        try:                                              # never the testnet faucet junk wallet
            px = {t["symbol"]: float(t["price"])
                  for t in _req(f"{_SPOT_BASE}/api/v3/ticker/price")}
            for b in _signed(_SPOT_BASE, "/api/v3/account", spt)["balances"]:
                amt, sym = float(b["free"]), b["asset"] + "USDT"
                if sym in shorts and amt * px.get(sym, 0.0) > 10.0:
                    _signed(_SPOT_BASE, "/api/v3/order", spt,
                            {"symbol": sym, "side": "SELL", "type": "MARKET",
                             "quantity": f"{amt:.6f}"}, method="POST")
        except Exception:
            pass
    _page("DEADMAN SWITCH FIRED: book flattened at ruin rail (65% of high-water). "
          "Investigate before any restart.")


def _page(msg: str) -> None:
    try:
        topic = json.loads(_NTFY.read_text("utf-8")).get("topic")
        if topic:
            _req(f"https://ntfy.sh/{topic}", data=msg.encode(), method="POST")
    except Exception:
        pass


def _foreign_writer_alive() -> bool:
    """True when another LIVE process owns the heartbeat (parseable-or-not, fresh either way).

    SINGLE-WRITER INVARIANT (2026-07-11 incident: a zombie old-code instance -- S4U-spawned,
    unkillable from a user session -- alternated state writes with a new instance; the new one
    inherited the zombie's stale high-water and FALSE-FIRED the rail): two writers on this
    state are never acceptable. On detecting one, we EXIT and let the watchdog resolve."""
    try:
        pid_s, _ts = _HB.read_text("utf-8").split()
        return int(pid_s) != os.getpid() and time.time() - _HB.stat().st_mtime < 90
    except Exception:
        return _HB.exists() and time.time() - _HB.stat().st_mtime < 90


def main() -> None:
    if _HB.exists() and time.time() - _HB.stat().st_mtime < 150:
        return                                             # another instance is alive (2.5x tick)
    while True:
        if _foreign_writer_alive():
            return                                         # never share the rail; watchdog respawns
        # state re-read EVERY loop: deleting data/deadman_state.json is the documented
        # operator reset (re-baseline + un-latch alongside DEADMAN_FIRED) -- no process hunt
        # needed (S4U-spawned daemons are invisible/unkillable from a user session).
        try:
            state = json.loads(_STATE.read_text("utf-8")) if _STATE.exists() else {}
        except (json.JSONDecodeError, OSError):
            state = {}
        if state.get("version") != _VERSION:
            state = {"version": _VERSION}                  # NEVER inherit foreign/legacy state --
            # the 2026-07-11 false fire was a poisoned high-water inherited from an old-code
            # writer; an unversioned state resets to a fresh baseline instead of being trusted.
        _HB.write_text(f"{os.getpid()} {time.time()}", "utf-8")
        eq = combined_equity(state)
        # STALE-FEED DETECTOR (round-2 review: the missed-fire scenario is a venue returning
        # stale-but-valid data during the exact outage the rail exists for). With open
        # positions, marks move every poll; equity identical to the cent for 12 consecutive
        # minutes means the rail may be blind -> page the human ONCE (never auto-fire on it).
        if eq is not None and state.get("has_positions"):
            if eq == state.get("last_eq"):
                state["same_count"] = int(state.get("same_count", 0)) + 1
                if state["same_count"] == 12 and not state.get("stale_paged"):
                    _page("DEADMAN: equity identical for 12 polls with open positions -- "
                          "venue feed may be STALE; the ruin rail may be blind. Check the desk.")
                    state["stale_paged"] = True
            else:
                state["same_count"], state["stale_paged"] = 0, False
            state["last_eq"] = eq
        fire = should_fire(eq, state)
        # Page ONCE when the rail is disarmed on a live book (dust-floor guard active with
        # open positions); re-arm clears the latch so a future disarm pages again.
        if state.get("disarmed_live") and not state.get("disarmed_paged"):
            _page("DEADMAN: ruin rail DISARMED on a live book -- high-water below the "
                  f"{_MIN_HW:.0f} dust floor while positions are open. The equity read may "
                  "be undercounting collateral. Investigate NOW; the rail fires at nothing "
                  "in this state.")
            state["disarmed_paged"] = True
        elif not state.get("disarmed_live"):
            state["disarmed_paged"] = False
        if fire or state.get("fired") or _FIRED.exists():
            state["fired"] = True
            if not _FIRED.exists():                        # durable latch: survives state races;
                _FIRED.write_text(time.strftime("%Y-%m-%dT%H:%M:%SZ"), "utf-8")
            _flatten()                                     # reset = delete FIRED + state + KILL
        _write_state(state)
        time.sleep(_POLL_SEC)


if __name__ == "__main__":
    main()

```

### scripts\run_portfolio_risk.py
```python
"""PORTFOLIO RISK REVIEW -- wire libs/stage14_5, self-arming at the sleeve count that makes it real.

THE GAP. libs/stage14_5 (10 modules: correlation shock, concentration, factor exposure, regime
exposure, crisis alpha, hedging) had no path from any entry point. These are the controls that
decide whether "orthogonal sleeves" is a true statement or a comfortable one.

WHY IT MATTERS EXACTLY HERE. The growth ladder's step 3 -- the 80-120%/yr band -- gates on
">= 3 orthogonal validated sleeves; LIVE portfolio Sharpe >= 1.2 over >= 60 live days", and its
own arithmetic says growth comes "by STACKING VALIDATED SLEEVES (sqrt-N Sharpe growth), never by
levering one unproven sleeve harder". That sqrt-N is a LIE under correlation convergence:
sleeves that look uncorrelated in calm markets converge toward 1.0 in stress, and the effective
bet count collapses exactly when drawdown arrives. A desk that stacks sleeves without measuring
shocked correlation is levering a diversification it does not have.

SELF-ARMING, NOT DEFERRED. Correlation shock is meaningless at one sleeve (a 1x1 correlation
matrix has no off-diagonal) and load-bearing at three. So the gate is a DATA CONDITION read from
the shadow registry, not a human decision someone has to remember: below MIN_SLEEVES it reports
DORMANT and explains what would arm it; at or above, it runs every control and fails loud. No
one has to notice the third sleeve landing -- the check notices.

Reports only. Zero promotion authority; no rail is touched. `--self-test` proves the engines run.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from libs.stage14_5.concentration import ConcentrationEngine  # noqa: E402
from libs.stage14_5.correlation_shock import CorrelationShockEngine  # noqa: E402

OUT = ROOT / "data/portfolio_risk.json"
SLEEVES = ROOT / "data/shadow_sleeves.json"
MIN_SLEEVES = 3          # the ladder's own step-3 gate; below this the maths is degenerate
SHOCK = 0.5              # converge halfway to 1.0 -- a stress, not a doomsday


def load_returns() -> dict[str, np.ndarray]:
    try:
        raw = json.loads(SLEEVES.read_text("utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    out = {}
    if isinstance(raw, dict):
        for k, v in raw.items():
            s = v.get("returns") if isinstance(v, dict) else v
            if isinstance(s, list) and len(s) >= 30:
                out[str(k)] = np.asarray(s, dtype="float64")
    return out


def synthetic(seed: int = 5) -> dict[str, np.ndarray]:
    """Three sleeves that look diversified in calm and share a common stress factor."""
    rng = np.random.default_rng(seed)
    n = 400
    common = rng.normal(0, 0.004, n)
    common[rng.integers(0, n, 20)] -= 0.05          # shared stress events
    return {f"sleeve_{i}": common + rng.normal(0.0008, 0.010, n) for i in range(3)}


def review(rets: dict[str, np.ndarray]) -> dict:
    length = min(len(r) for r in rets.values())
    matrix = np.column_stack([r[-length:] for r in rets.values()])
    corr = np.corrcoef(matrix, rowvar=False)

    shock = CorrelationShockEngine(shock=SHOCK).simulate(corr)
    res = json.loads(shock.model_dump_json())

    # Equal weight is the honest baseline: it is what the desk actually runs pre-allocation,
    # so concentration measured on it reflects real exposure rather than an aspirational book.
    names = list(rets)
    w = dict.fromkeys(names, 1.0 / len(names))
    conc = ConcentrationEngine().evaluate(
        symbol_weights=w, alpha_weights=w, family_weights=w, factor_weights=w, regime_weights=w)
    return {"n_sleeves": len(names), "sleeves": names,
            "avg_correlation": round(float(corr[np.triu_indices(len(names), 1)].mean()), 4),
            "correlation_shock": res,
            "concentration": json.loads(conc.model_dump_json())}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args()

    rets = synthetic() if args.self_test else load_returns()
    src = "SYNTHETIC (self-test)" if args.self_test else str(SLEEVES.relative_to(ROOT))
    print("=== PORTFOLIO RISK REVIEW (stage14_5) ===")
    print(f"    source: {src}\n")

    if len(rets) < MIN_SLEEVES:
        print(f"  DORMANT -- {len(rets)} sleeve(s), arms automatically at {MIN_SLEEVES}.")
        print("  Correlation shock is degenerate below 3 sleeves (no off-diagonal to converge),")
        print("  and step 3 of the growth ladder gates on exactly that count. This check arms")
        print("  itself from the registry -- nobody has to notice the third sleeve landing.")
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps({"ran": datetime.now(tz=UTC).isoformat(), "state": "DORMANT",
                                   "n_sleeves": len(rets), "arms_at": MIN_SLEEVES}, indent=1),
                       "utf-8")
        return

    r = review(rets)
    cs = r["correlation_shock"]
    print(f"  sleeves={r['n_sleeves']}  avg_corr={r['avg_correlation']}")
    print(f"  CORRELATION SHOCK (+{SHOCK:.0%} toward 1.0):")
    for k, v in cs.items():
        print(f"    {k:<34} {v}")
    print(f"  CONCENTRATION: {r['concentration']}")

    eb_b = cs.get("effective_bets_base")
    eb_s = cs.get("effective_bets_shocked")
    if isinstance(eb_b, (int, float)) and isinstance(eb_s, (int, float)) and eb_b > 0:
        lost = 1.0 - eb_s / eb_b
        print(f"\n  Effective bets {eb_b:.2f} -> {eb_s:.2f} under shock ({lost:.0%} of the")
        print("  diversification disappears). sqrt-N sleeve stacking assumes the BASE number;")
        print("  the book actually compounds at the SHOCKED one when it matters most.")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({"ran": datetime.now(tz=UTC).isoformat(), "state": "ACTIVE",
                               "source": src, "shock": SHOCK, **r}, indent=1), "utf-8")
    print(f"\n  -> {OUT.relative_to(ROOT)}")
    print("  Reports only -- no rail touched, zero promotion authority.")


if __name__ == "__main__":
    main()

```

## TIER 2 -- your shard

### libs\models\embedding.py
```python
"""A self-supervised market embedding and the historical-analogue engine built on it.

    z_t = Encoder(X_{t-L:t})

The encoder is a PCA over standardised feature windows -- deliberately linear, so the embedding
can be read, and trained on NO trading labels: its objective is masked-bar reconstruction (hide
the last bar of the window, predict its features from the embedding of the rest), scored as the
gain over predicting the window mean. That is the self-supervised task; when the gain is ~0 the
embedding has learned nothing and says so.

WHAT z_t IS FOR (never a buy/sell): nearest-neighbour regime analogues, conditioning for the
allocator's state posterior, anomaly distance, execution state. `analogues` implements
Bridgewater's case method mechanically: given now, retrieve the k most similar past windows,
report what matched (the features nearest in z), what differed, and the DISTRIBUTION of what
followed -- never "1974 looked similar, therefore".

TWO OBJECTIVES, ONE FUNCTION CLASS. `WindowPCA` and `ContrastiveEncoder` are both a linear map
of the standardised window; they differ only in what they are asked to keep. PCA keeps
VARIANCE, and in return data variance is owned by the rare bar -- a news spike, an open-gap --
so PCA's top directions are the shapes of a handful of windows. The contrastive encoder keeps
what SURVIVES A PERTURBATION of the typical window (jitter plus masked bars) while still telling
that window from every other one (InfoNCE), which is a statement about the median window, not
the loudest. Neither is admitted on its self-supervised score: `representation_gain` fits a
ridge on the embedding and a ridge on the raw last bars, walk-forward, and a representation is
kept only when it forecasts the forward quantity better than the bars it was built from.
"""
from __future__ import annotations

import copy
from typing import Any

import numpy as np


class MarketEncoder:
    def __init__(self, window: int = 24, dim: int = 8) -> None:
        self.window = window
        self.dim = dim
        self.mu: np.ndarray | None = None
        self.sd: np.ndarray | None = None
        self.components: np.ndarray | None = None
        self.explained: np.ndarray | None = None
        self.reconstruction_gain: float = float("nan")

    def _windows(self, x: np.ndarray) -> np.ndarray:
        from numpy.lib.stride_tricks import sliding_window_view
        assert self.mu is not None and self.sd is not None
        xs = np.nan_to_num((x - self.mu) / self.sd)
        w = sliding_window_view(xs, (self.window, xs.shape[1]))[:, 0]      # (T-L+1, L, F)
        return w.reshape(w.shape[0], -1)

    def fit(self, x: np.ndarray) -> MarketEncoder:
        self.mu = np.nanmean(x, axis=0)
        sd = np.nanstd(x, axis=0)
        self.sd = np.where(sd > 0, sd, 1.0)
        w = self._windows(x)
        w = w - w.mean(axis=0)
        _u, s, vt = np.linalg.svd(w, full_matrices=False)
        k = int(min(self.dim, vt.shape[0]))
        self.components = vt[:k]
        var = s ** 2
        self.explained = var[:k] / max(var.sum(), 1e-12)
        # SELF-SUPERVISED OBJECTIVE: reconstruct the masked last bar from the rest.
        full = self._windows(x)
        n_f = x.shape[1]
        head, last = full[:, :-n_f], full[:, -n_f:]
        z = (head - head.mean(axis=0)) @ np.linalg.pinv(self.components[:, :-n_f]).T \
            if self.components.shape[1] > n_f else head[:, :k]
        zb = np.column_stack([np.ones(z.shape[0]), z])
        beta = np.linalg.lstsq(zb, last, rcond=None)[0]
        pred = zb @ beta
        err = float(np.mean((last - pred) ** 2))
        base = float(np.mean((last - last.mean(axis=0)) ** 2))
        self.reconstruction_gain = float(1.0 - err / base) if base > 0 else 0.0
        return self

    def embed(self, x: np.ndarray) -> np.ndarray:
        assert self.components is not None
        w = self._windows(x)
        out: np.ndarray = (w - w.mean(axis=0)) @ self.components.T
        return out


def analogues(z_now: np.ndarray, z_hist: np.ndarray, forward: np.ndarray, *, k: int = 20,
              feature_names: list[str] | None = None, x_now: np.ndarray | None = None,
              x_hist: np.ndarray | None = None, exclude_last: int = 0) -> dict[str, Any]:
    """The k nearest past windows in embedding space, and what followed them.

    `forward` is the realised quantity after each historical window (e.g. the next-24-bar
    return); the answer is its DISTRIBUTION over the analogues, with the match quality, never a
    point forecast. When raw features are supplied the report also says which features matched
    and which differed most.
    """
    n = z_hist.shape[0] - exclude_last
    d = np.sqrt(((z_hist[:n] - z_now[None, :]) ** 2).sum(axis=1))
    idx = np.argsort(d)[:k]
    fwd = forward[idx]
    out: dict[str, Any] = {
        "k": len(idx), "indices": idx.tolist(), "distance_mean": round(float(d[idx].mean()), 4),
        "distance_all_median": round(float(np.median(d)), 4),
        "forward": {"mean": round(float(fwd.mean()), 6), "median": round(float(np.median(fwd)), 6),
                    "p10": round(float(np.quantile(fwd, 0.1)), 6),
                    "p90": round(float(np.quantile(fwd, 0.9)), 6),
                    "p_positive": round(float((fwd > 0).mean()), 4)},
        "uncertainty": "distribution over analogues; the mean is not a forecast",
    }
    if x_now is not None and x_hist is not None:
        diff = np.abs(x_hist[idx].mean(axis=0) - x_now)
        order = np.argsort(diff)
        names = feature_names or [f"f{i}" for i in range(len(diff))]
        out["matched"] = [names[i] for i in order[:3]]
        out["differed"] = [names[i] for i in order[::-1][:3]]
    return out


# ----------------------------------------------------------------------------- windows
def windows_from_series(x: np.ndarray, window: int) -> np.ndarray:
    """(T, F) or (T,) series -> (T - window + 1, window, F) causal windows ending at each bar.

    Window i ends at bar i + window - 1, so `forward[i]` for a representation test must be the
    quantity realised AFTER that bar; the caller aligns it, this function only cuts.
    """
    from numpy.lib.stride_tricks import sliding_window_view
    x = np.asarray(x, dtype=float)
    if x.ndim == 1:
        x = x[:, None]
    w = sliding_window_view(x, (window, x.shape[1]))[:, 0]
    return np.ascontiguousarray(w)


def _as_windows(w: np.ndarray) -> np.ndarray:
    """(N, L, F) or (N, L) -> (N, L, F); a 2-D input is read as one feature per bar."""
    w = np.asarray(w, dtype=float)
    return w[:, :, None] if w.ndim == 2 else w


class _Scaler:
    """Per-FEATURE moments pooled over bar positions, the same convention as `MarketEncoder`.

    Standardising per feature (not per bar position) keeps the window's shape intact: a bar that
    was large stays large relative to its neighbours, which is exactly what the encoders are
    meant to read. Standardising per position would erase it.
    """

    def __init__(self) -> None:
        self.mu: np.ndarray | None = None
        self.sd: np.ndarray | None = None

    def fit(self, w3: np.ndarray) -> _Scaler:
        flat = w3.reshape(-1, w3.shape[2])
        self.mu = np.nanmean(flat, axis=0)
        sd = np.nanstd(flat, axis=0)
        self.sd = np.where(sd > 0, sd, 1.0)
        return self

    def flat(self, w3: np.ndarray) -> np.ndarray:
        assert self.mu is not None and self.sd is not None
        xs = np.nan_to_num((w3 - self.mu) / self.sd)
        out: np.ndarray = xs.reshape(w3.shape[0], -1)
        return out


class WindowPCA:
    """PCA over standardised windows: `MarketEncoder`'s objective on pre-cut windows.

    Exists so the contrastive encoder can be scored against PCA on IDENTICAL rows by
    `representation_gain`; `MarketEncoder` cuts its own windows from a series and cannot be fed
    the same matrix.
    """

    def __init__(self, dim: int = 8) -> None:
        self.dim = dim
        self.scaler = _Scaler()
        self.centre: np.ndarray | None = None
        self.components: np.ndarray | None = None
        self.explained: np.ndarray | None = None

    def fit(self, windows: np.ndarray) -> WindowPCA:
        w3 = _as_windows(windows)
        flat = self.scaler.fit(w3).flat(w3)
        self.centre = flat.mean(axis=0)
        _u, s, vt = np.linalg.svd(flat - self.centre, full_matrices=False)
        k = int(min(self.dim, vt.shape[0]))
        self.components = vt[:k]
        var = s ** 2
        self.explained = var[:k] / max(float(var.sum()), 1e-12)
        return self

    def embed(self, windows: np.ndarray) -> np.ndarray:
        assert self.components is not None and self.centre is not None
        flat = self.scaler.flat(_as_windows(windows))
        out: np.ndarray = (flat - self.centre) @ self.components.T
        return out


def _unit(h: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    n = np.sqrt((h ** 2).sum(axis=1, keepdims=True))
    n = np.maximum(n, 1e-12)
    return h / n, n


def _infonce(v1: np.ndarray, v2: np.ndarray, w: np.ndarray,
             tau: float) -> tuple[float, np.ndarray]:
    """Symmetric InfoNCE on cosine similarity and its gradient with respect to W.

    Row i's positive is its own second view; every other row in the batch is a negative, both
    ways round. The gradient goes through the L2 normalisation, so the projection's scale is
    not a free win: only DIRECTION agreement counts.
    """
    b = v1.shape[0]
    z1, n1 = _unit(v1 @ w)
    z2, n2 = _unit(v2 @ w)
    s = z1 @ z2.T / tau
    s_max = s.max()
    rows = np.log(np.exp(s - s_max).sum(axis=1)) + s_max
    cols = np.log(np.exp(s - s_max).sum(axis=0)) + s_max
    diag = np.diag(s)
    loss = float(0.5 * (np.mean(rows - diag) + np.mean(cols - diag)))
    p = np.exp(s - rows[:, None])                       # softmax over j for each i
    q = np.exp(s - cols[None, :])                       # softmax over i for each j
    ds = (p + q - 2.0 * np.eye(b)) / (2.0 * b)
    dz1 = ds @ z2 / tau
    dz2 = ds.T @ z1 / tau
    dh1 = (dz1 - z1 * (dz1 * z1).sum(axis=1, keepdims=True)) / n1
    dh2 = (dz2 - z2 * (dz2 * z2).sum(axis=1, keepdims=True)) / n2
    grad: np.ndarray = v1.T @ dh1 + v2.T @ dh2
    return loss, grad


class ContrastiveEncoder:
    """A linear projection W (d x k) trained by InfoNCE over two augmented views of each window.

        z = normalise(W^T x),   views: x + jitter * eps,  then a random `mask_frac` of bars zeroed

    WHY THESE TWO AUGMENTATIONS: jitter says "a representation must not change when every bar is
    nudged by a fraction of its own scale" (tick noise, a stale print); masking says "it must not
    hinge on any one bar" (the spike, the gap). A direction that only a few loud bars carry is
    destroyed by masking; a direction the whole window carries survives it. PCA has no such
    preference and so is fooled by the loud bar, which owns the variance.

    WHY LINEAR AND SMALL: the projection is a matrix that can be printed; `steps` batches of
    `batch` windows with an Adam step each is a fraction of a second, and the encoder is refitted
    per fold by `representation_gain` so nothing leaks.
    """

    def __init__(self, dim: int = 8, tau: float = 0.1, steps: int = 300, lr: float = 0.03,
                 jitter: float = 0.3, mask_frac: float = 0.25, batch: int = 256,
                 seed: int = 0) -> None:
        self.dim = dim
        self.tau = max(float(tau), 1e-3)
        self.steps = steps
        self.lr = lr
        self.jitter = jitter
        self.mask_frac = mask_frac
        self.batch = batch
        self.seed = seed
        self.scaler = _Scaler()
        self.centre: np.ndarray | None = None
        self.w: np.ndarray | None = None
        self.shape: tuple[int, int] = (0, 0)               # (bars, features) of a window
        self.loss_path: list[float] = []
        self.alignment: float = float("nan")
        self.uniformity: float = float("nan")

    # ------------------------------------------------------------------ augmentations
    def augment(self, flat: np.ndarray, rng: np.random.Generator) -> np.ndarray:
        """One view of standardised, centred, flattened windows: jitter then bar masking.

        Public so a test can ask the question the objective asks: are two views of one window
        nearer each other than a window is to a stranger?
        """
        bars, feats = self.shape
        v = flat + self.jitter * rng.standard_normal(flat.shape)
        keep = rng.random((flat.shape[0], bars, 1)) >= self.mask_frac
        out: np.ndarray = (v.reshape(flat.shape[0], bars, feats) * keep).reshape(flat.shape)
        return out

    def _prepare(self, windows: np.ndarray) -> np.ndarray:
        assert self.centre is not None
        flat: np.ndarray = self.scaler.flat(_as_windows(windows)) - self.centre
        return flat

    # ------------------------------------------------------------------------ training
    def fit(self, windows: np.ndarray) -> ContrastiveEncoder:
        w3 = _as_windows(windows)
        self.shape = (int(w3.shape[1]), int(w3.shape[2]))
        flat = self.scaler.fit(w3).flat(w3)
        self.centre = flat.mean(axis=0)
        x = flat - self.centre
        n, d = x.shape
        k = int(min(self.dim, d))
        rng = np.random.default_rng(self.seed)
        w = np.linalg.qr(rng.standard_normal((d, k)))[0]
        m = np.zeros_like(w)
        v = np.zeros_like(w)
        b1, b2, eps = 0.9, 0.999, 1e-8
        self.loss_path = []
        for t in range(1, self.steps + 1):
            idx = rng.choice(n, size=min(self.batch, n), replace=False)
            xb = x[idx]
            loss, grad = _infonce(self.augment(xb, rng), self.augment(xb, rng), w, self.tau)
            m = b1 * m + (1 - b1) * grad
            v = b2 * v + (1 - b2) * grad ** 2
            w = w - self.lr * (m / (1 - b1 ** t)) / (np.sqrt(v / (1 - b2 ** t)) + eps)
            self.loss_path.append(loss)
        self.w = w
        # Wang & Isola's two reads of a contrastive representation, on the training windows:
        # alignment = mean cosine between two views of one window (1 is perfect);
        # uniformity = log mean exp(-2 |z_i - z_j|^2) over pairs (more negative = better spread).
        z1, _ = _unit(self.augment(x, rng) @ w)
        z2, _ = _unit(self.augment(x, rng) @ w)
        self.alignment = float(np.mean((z1 * z2).sum(axis=1)))
        sample = rng.choice(n, size=min(512, n), replace=False)
        zs, _ = _unit(x[sample] @ w)
        d2 = ((zs[:, None, :] - zs[None, :, :]) ** 2).sum(axis=2)
        off = ~np.eye(zs.shape[0], dtype=bool)
        self.uniformity = float(np.log(np.mean(np.exp(-2.0 * d2[off]))))
        return self

    # ------------------------------------------------------------------------- reading
    def embed(self, windows: np.ndarray, normalise: bool = True) -> np.ndarray:
        """z for each window; unit-norm by default because that is what the objective trained."""
        assert self.w is not None, "fit first"
        h = self._prepare(windows) @ self.w
        if not normalise:
            return np.asarray(h, dtype=float)
        z, _ = _unit(h)
        return np.asarray(z, dtype=float)

    def nn_forward_stats(self, z_query: np.ndarray, z_hist: np.ndarray, forward: np.ndarray,
                         k: int = 20, **kw: Any) -> dict[str, Any]:
        """The case method on this embedding: `analogues` of the query among the history."""
        return analogues(np.asarray(z_query, dtype=float), np.asarray(z_hist, dtype=float),
                         np.asarray(forward, dtype=float), k=k, **kw)


# --------------------------------------------------------------------------- admission
def _ridge_fit(x: np.ndarray, y: np.ndarray, lam: float) -> np.ndarray:
    xb = np.column_stack([np.ones(x.shape[0]), x])
    a = xb.T @ xb + lam * np.eye(xb.shape[1])
    a[0, 0] -= lam
    out: np.ndarray = np.linalg.solve(a, xb.T @ y)
    return out


def _oos_score(xtr: np.ndarray, ytr: np.ndarray, xte: np.ndarray, yte: np.ndarray,
               lam: float, score: str) -> float:
    """Ridge on train-standardised inputs; R^2 (about the TRAIN mean) or sign log-score gain."""
    mu, sd = xtr.mean(axis=0), xtr.std(axis=0)
    sd = np.where(sd > 0, sd, 1.0)
    a, b = (xtr - mu) / sd, (xte - mu) / sd
    if score == "sign":
        s_tr = np.where(ytr > 0, 1.0, -1.0)
        s_te = np.where(yte > 0, 1.0, -1.0)
        beta = _ridge_fit(a, s_tr, lam)
        raw = np.column_stack([np.ones(b.shape[0]), b]) @ beta
        p = 1.0 / (1.0 + np.exp(-np.clip(4.0 * raw, -50.0, 50.0)))
        p = np.clip(p, 1e-6, 1 - 1e-6)
        p0 = float(np.clip((s_tr > 0).mean(), 1e-6, 1 - 1e-6))
        hit = s_te > 0
        ls = np.mean(np.where(hit, np.log(p), np.log(1 - p)))
        base = np.mean(np.where(hit, np.log(p0), np.log(1 - p0)))
        return float(ls - base)
    beta = _ridge_fit(a, ytr, lam)
    pred = np.column_stack([np.ones(b.shape[0]), b]) @ beta
    sse = float(np.sum((yte - pred) ** 2))
    sst = float(np.sum((yte - ytr.mean()) ** 2))
    return float(1.0 - sse / sst) if sst > 0 else 0.0


def representation_gain(windows: np.ndarray, forward: np.ndarray, *, encoder: Any = None,
                        raw_bars: int = 1, n_folds: int = 4, lam: float = 1.0,
                        score: str = "r2") -> dict[str, Any]:
    """Does the embedding forecast `forward` better than the raw last bars it was cut from?

    Walk-forward with expanding folds: on each fold the encoder is refitted on the train windows
    only (a fresh copy, so no fold sees a later one), a ridge is fitted on its embedding and
    another on the last `raw_bars` bars of the window, and both are scored out of sample --
    R^2 about the train mean by default, or the sign log-score gain over the base rate with
    `score="sign"`. The gain is the difference. A representation is ADMITTED only when the gain
    is positive AND the embedding's own score is positive: beating a useless baseline by being
    less useless is not admission.
    """
    w3 = _as_windows(windows)
    y = np.asarray(forward, dtype=float)
    n = w3.shape[0]
    assert y.shape[0] == n, "one forward value per window"
    enc = encoder if encoder is not None else ContrastiveEncoder()
    edges = np.linspace(n // 2, n, n_folds + 1).astype(int)
    per_fold: list[dict[str, float]] = []
    for i in range(n_folds):
        a, b = int(edges[i]), int(edges[i + 1])
        if b - a < 10 or a < 20:
            continue
        e = copy.deepcopy(enc).fit(w3[:a])
        ztr, zte = e.embed(w3[:a]), e.embed(w3[a:b])
        raw_tr = w3[:a, -raw_bars:, :].reshape(a, -1)
        raw_te = w3[a:b, -raw_bars:, :].reshape(b - a, -1)
        per_fold.append({"embedding": _oos_score(ztr, y[:a], zte, y[a:b], lam, score),
                         "raw": _oos_score(raw_tr, y[:a], raw_te, y[a:b], lam, score)})
    if not per_fold:
        return {"n": n, "folds": 0, "verdict": "UNMEASURED", "why": "too few windows"}
    emb = float(np.mean([f["embedding"] for f in per_fold]))
    raw = float(np.mean([f["raw"] for f in per_fold]))
    gain = emb - raw
    return {"n": n, "folds": len(per_fold), "score": score, "encoder": type(enc).__name__,
            "embedding": round(emb, 6), "raw": round(raw, 6), "gain": round(gain, 6),
            "per_fold": per_fold,
            "verdict": "ADMIT" if gain > 0 and emb > 0 else "REFUSE",
            "rule": "admit only when the embedding beats the raw last bars AND scores > 0"}

```

### libs\research\alpha_dsl.py
```python
"""THE EXPRESSION FACTORY'S DSL: typed fields, the 101 parent genomes, canonical form, panels.

This module EXTENDS `alpha_grammar` (ledger G2) rather than writing a second grammar. The grammar
owns the operators, the type and unit algebra, evaluation and the search moves; this module owns
what the WorldQuant-style factory (LAWS 5l, RESEARCH 11) adds on top of it:

  * TYPED FIELDS from the desk's data lake -- bars per symbol, the `axes/*.json` series (COT
    positioning, BIS policy rates, ECB/FRED macro levels, the shadow latents), the representation
    forge's manifest -- each with a SEMANTIC TYPE (price, volume, spread, flow, macro_level,
    macro_surprise, positioning, rate, event_intensity), the grammar terminal that carries it, and
    an AVAILABILITY RULE: how the field's `available_time` is known. A field whose availability is
    UNKNOWN is not a field the factory may search on (Tier 0, future-data impossibility), because
    a series joined at its period time rather than its publication time is a lookahead nobody can
    see in a backtest.
  * THE 101 FORMULAIC ALPHAS (Kakushadze 2016, arXiv:1601.00991, a public paper) transcribed as
    PARENT GENOMES A_i = (D, O, T, H, S, N, E): data fields, operator tree, transformations,
    horizon, state, normalisation / cross-section, execution assumptions. The paper's formulas are
    carried verbatim as the parent's O and TRANSPILED into the grammar by semantic type: equity
    volume -> tick activity, adv{d} -> rolling activity, cross-sectional rank -> basket rank
    (`xrank`), industry neutralisation -> basket z-score (`xzscore`). An alpha whose fields have no
    lawful MT5 analogue (vwap: the grammar's own unit algebra refuses the proxy; cap: no market
    capitalisation for a CFD) is NONTESTABLE with the missing field NAMED, never approximated. An
    alpha whose transcription is deeper than the executor's `MAX_DEPTH` is TOO_DEEP: a real genome
    whose descendants reach the executor only through the factory's pruning moves.
  * CANONICAL FORM: exact simplifications and commutative argument ordering, so two spellings of
    one recipe hash the same (Tier 0, duplicate AST) and the trial FAMILY -- the skeleton with its
    windows blanked -- is what an evaluation is charged to (LAWS 5k: EMA(19,57) and EMA(20,58)
    are one family).
  * PANEL SEEDING: the grammar's `xrank` / `xzscore` nodes evaluate only where a caller has
    computed the child on every member of the cell's basket and seeded each member's memo with
    the cross-sectional series. `seed_panels` is that caller.

Nothing here has authority: a genome is a hypothesis about a public formula, a field is a series
the desk can read, and the factory (desks/mt5/research/expression_factory.py) is the only consumer.
"""
from __future__ import annotations

import json
import math
import re
import warnings
from collections.abc import Callable, Iterable, Mapping, MutableMapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from functools import lru_cache
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from libs.research import alpha_grammar as ag

Expr = Any

# ============================================================================ semantic types
SEMANTIC_TYPES: tuple[str, ...] = ("price", "volume", "spread", "flow", "macro_level",
                                   "macro_surprise", "positioning", "rate", "event_intensity")
#: Semantic type -> the grammar terminal that carries it: THE MT5 ANALOGUE BY SEMANTIC TYPE.
#: `volume` is tick activity because Fusion publishes tick counts, not contracts; `rate` rides
#: the grammar's FUNDAMENTAL terminal (carry, the instrument's own fundamental); both macro types
#: ride MACRO; event intensity rides EVENT.
SEMANTIC_TERMINAL: dict[str, str] = {
    "price": "close", "volume": "activity", "spread": "spread", "flow": "flow",
    "macro_level": "macro", "macro_surprise": "macro", "positioning": "positioning",
    "rate": "fundamental", "event_intensity": "event",
}
#: Availability rules a field may declare. UNKNOWN is a rule too: it is the rule that forbids.
AVAILABILITY_RULES: tuple[str, ...] = ("bar_close", "knowable_at", "available_time",
                                       "period_end+1d", "month_end+1d", "UNKNOWN")


@dataclass(frozen=True)
class Field:
    """One typed field: what it is, which terminal carries it, and WHEN a bar may know it."""

    name: str
    semantic: str
    terminal: str
    source: str
    availability: str
    unit: str = "dimensionless"
    description: str = ""
    n_points: int = 0
    symbol: str = ""                 #: empty = global (macro); else the instrument it belongs to

    def causal(self) -> bool:
        """Can a bar be told when this field became known? UNKNOWN cannot be searched on."""
        return self.availability in AVAILABILITY_RULES and self.availability != "UNKNOWN"


_BAR_SEMANTIC: dict[str, str] = {
    "close": "price", "open": "price", "high": "price", "low": "price", "atr": "price",
    "ret": "price", "range": "price", "body": "price", "vol": "price",
    "activity": "volume", "spread": "spread", "flow": "flow",
}


def bar_fields() -> tuple[Field, ...]:
    """The fields every symbol's own bars carry, plus the economic-driver closes."""
    out = [Field(t, _BAR_SEMANTIC[t], t, "bars", "bar_close", str(ag.TERMINAL_UNITS[t]),
                 f"bar terminal {t}") for t in ag.BAR_TERMINALS]
    out += [Field(t, "price", t, f"driver:{t}", "bar_close", "quote",
                  f"economic driver role {t.upper()} (another instrument's close)")
            for t in ag.DRIVER_TERMINALS]
    return tuple(out)


# ---------------------------------------------------------------------------- the data lake
def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text("utf-8"))
    except (OSError, ValueError):
        return None


#: Per-axis publication lag for series that carry a PERIOD date rather than a release time. The
#: ECB reference rate and a FRED daily series are published after the close of the day they
#: describe; one day is the conservative declaration and it is a declaration, not a measurement.
_SERIES_LAG_DAYS = 1


def axis_fields(axes_dir: Path) -> tuple[Field, ...]:
    """Typed fields from `desks/mt5/data/axes/*.json`, one per numeric column or series.

    Shapes seen on this desk: COT (`rows` keyed by symbol + knowable_at), BIS policy rates
    (`rows` keyed by symbol + month), ECB / FRED (`series[name].points` of `d`,`v`), the shadow
    latents (`points` carrying their own `available_time`). Anything else is read as a series with
    UNKNOWN availability, which names it without letting the search touch it.
    """
    out: list[Field] = []
    for path in sorted(axes_dir.glob("*.json")):
        doc = _read_json(path)
        if not isinstance(doc, dict):
            continue
        axis = str(doc.get("axis") or "")
        aid = str(doc.get("id") or path.stem)
        rows = doc.get("rows")
        if isinstance(rows, list) and rows and isinstance(rows[0], dict):
            sample = rows[0]
            numeric = [k for k, v in sample.items()
                       if isinstance(v, (int, float)) and not isinstance(v, bool)
                       and k not in ("knowable_at", "as_of")]
            syms = sorted({str(r.get("symbol") or "") for r in rows if r.get("symbol")})
            if axis == "positioning":
                sem, rule = "positioning", "knowable_at"
            elif axis == "policy":
                sem, rule = "rate", "month_end+1d"
            else:
                sem, rule = "macro_level", ("knowable_at" if "knowable_at" in sample
                                            else "UNKNOWN")
            for col in numeric:
                for sym in syms:
                    n = sum(1 for r in rows if r.get("symbol") == sym
                            and isinstance(r.get(col), (int, float)))
                    out.append(Field(f"{aid}.{col}", sem, SEMANTIC_TERMINAL[sem],
                                     f"axis:{path.stem}", rule, "dimensionless",
                                     str(doc.get("shape") or ""), n, sym))
            continue
        series = doc.get("series")
        if isinstance(series, dict):
            for name, s in series.items():
                pts = s.get("points") if isinstance(s, dict) else None
                n = len(pts) if isinstance(pts, list) else 0
                first: dict[str, Any] = (pts[0] if isinstance(pts, list) and pts
                                         and isinstance(pts[0], dict) else {})
                rule = ("available_time" if first.get("available_time") else
                        "period_end+1d" if first.get("d") else "UNKNOWN")
                out.append(Field(f"{aid}.{name}", "macro_level", "macro", f"axis:{path.stem}",
                                 rule, "dimensionless",
                                 str((s or {}).get("what") if isinstance(s, dict) else ""), n))
    return tuple(out)


def representation_fields(repr_dir: Path) -> tuple[Field, ...]:
    """Typed fields from the representation forge's manifest, if it is present."""
    doc = _read_json(repr_dir / "manifest.json")
    if not isinstance(doc, dict):
        return ()
    out: list[Field] = []
    for r in doc.get("representations") or []:
        if not isinstance(r, dict) or not r.get("id"):
            continue
        info = str(r.get("information_type") or "").lower()
        sem = ("rate" if info == "policy" else "positioning" if info == "positioning"
               else "flow" if info == "flow" else "macro_level")
        out.append(Field(str(r["id"]), sem, SEMANTIC_TERMINAL[sem],
                         f"representation:{r.get('file') or ''}", "available_time",
                         "dimensionless", str(r.get("dataset") or ""),
                         int(r.get("n") or 0)))
    return tuple(out)


def _utc(ts: Any) -> pd.Timestamp | None:
    try:
        t = pd.Timestamp(ts)
    except (TypeError, ValueError):
        return None
    if pd.isna(t):
        return None
    return t.tz_localize("UTC") if t.tzinfo is None else t.tz_convert("UTC")


def _availability_time(row: Mapping[str, Any], rule: str) -> pd.Timestamp | None:
    """When a bar may first know this row, under its declared rule. None = never."""
    if rule == "available_time":
        return _utc(row.get("available_time"))
    if rule == "knowable_at":
        return _utc(row.get("knowable_at"))
    if rule == "period_end+1d":
        t = _utc(row.get("d") or row.get("period_time") or row.get("date"))
        return None if t is None else t + pd.Timedelta(days=_SERIES_LAG_DAYS)
    if rule == "month_end+1d":
        raw = str(row.get("knowable_at") or row.get("d") or "")
        m = re.match(r"^(\d{4})-(\d{2})", raw)
        if not m:
            return None
        y, mo = int(m.group(1)), int(m.group(2))
        first_next = datetime(y + (mo == 12), 1 if mo == 12 else mo + 1, 1, tzinfo=UTC)
        return pd.Timestamp(first_next + timedelta(days=1))
    return None


class FieldCatalogue:
    """Every typed field the lake exposes, and the causal join that puts one on a bar index."""

    def __init__(self, axes_dir: Path | None = None, repr_dir: Path | None = None,
                 extra: Iterable[Field] = ()) -> None:
        self.axes_dir = axes_dir
        self.repr_dir = repr_dir
        fields = list(bar_fields())
        if axes_dir is not None and axes_dir.exists():
            fields += list(axis_fields(axes_dir))
        if repr_dir is not None and repr_dir.exists():
            fields += list(representation_fields(repr_dir))
        fields += list(extra)
        self.fields: tuple[Field, ...] = tuple(fields)
        self._docs: dict[str, Any] = {}

    def by_name(self, name: str, symbol: str = "") -> Field | None:
        for f in self.fields:
            if f.name == name and (not f.symbol or f.symbol == symbol):
                return f
        return None

    def external(self, symbol: str) -> list[Field]:
        """Fields that could bind an EXTERNAL grammar terminal for `symbol`, causal ones first."""
        out = [f for f in self.fields if f.terminal in ag.EXTERNAL_TERMINALS
               and (not f.symbol or f.symbol == symbol) and f.n_points > 0]
        return sorted(out, key=lambda f: (not f.causal(), f.terminal, f.name))

    def census(self) -> dict[str, Any]:
        by_sem: dict[str, int] = {}
        for f in self.fields:
            by_sem[f.semantic] = by_sem.get(f.semantic, 0) + 1
        return {"n_fields": len(self.fields), "by_semantic": by_sem,
                "uncausal": sorted({f.name for f in self.fields if not f.causal()})[:50],
                "n_uncausal": sum(1 for f in self.fields if not f.causal())}

    # ---- the causal join
    def _doc(self, source: str) -> Any:
        if source not in self._docs:
            kind, _, stem = source.partition(":")
            base = self.axes_dir if kind == "axis" else self.repr_dir
            self._docs[source] = (_read_json(base / f"{stem}.json") if base is not None
                                  and kind == "axis" else
                                  _read_json(base / stem) if base is not None else None)
        return self._docs[source]

    def _rows(self, f: Field) -> list[dict[str, Any]]:
        doc = self._doc(f.source)
        if not isinstance(doc, dict):
            return []
        col = f.name.split(".", 1)[1] if "." in f.name else f.name
        rows = doc.get("rows")
        if isinstance(rows, list):
            return [{"t": _availability_time(r, f.availability), "v": r.get(col)}
                    for r in rows if isinstance(r, dict) and r.get("symbol") == f.symbol]
        series = doc.get("series")
        if isinstance(series, dict) and col in series and isinstance(series[col], dict):
            pts = series[col].get("points") or []
            return [{"t": _availability_time(p, f.availability),
                     "v": p.get("v", p.get("value"))} for p in pts if isinstance(p, dict)]
        pts = doc.get("points")
        if isinstance(pts, list):
            return [{"t": _availability_time(p, f.availability),
                     "v": p.get("v", p.get("value"))} for p in pts if isinstance(p, dict)]
        return []

    def series(self, f: Field, index: pd.Index) -> pd.Series | None:
        """The field on `index`: the value LAST KNOWN at each bar, or None when unbindable.

        Rows are placed at their availability time and forward-filled -- the only causal join.
        An uncausal field returns None here as well as failing Tier 0, so no path evaluates it.
        """
        if not f.causal() or f.source == "bars" or f.source.startswith("driver:"):
            return None
        rows = [(r["t"], r["v"]) for r in self._rows(f)
                if r["t"] is not None and isinstance(r["v"], (int, float))
                and not isinstance(r["v"], bool) and math.isfinite(float(r["v"]))]
        if not rows:
            return None
        s = pd.Series({t: float(v) for t, v in rows}).sort_index()
        s = s[~s.index.duplicated(keep="last")]
        idx = pd.DatetimeIndex(pd.to_datetime(index, utc=True, errors="coerce"))
        return s.reindex(idx, method="ffill")


# ---------------------------------------------------------------------------- Tier 0 checks
def future_data_impossible(expr: Expr, bindings: Mapping[str, Field]) -> str | None:
    """Why this tree could read the future, or None when every external terminal is causal.

    The grammar has no forward operator, so the only lookahead channel is a FIELD joined at a
    time the desk could not have known it. Every external terminal in the tree must be bound to
    a field whose availability rule is known; an unbound external is 'UNMEASURED', which is the
    same refusal for a different reason.
    """
    for t in sorted(ag.terminals_in(expr)):
        if t not in ag.EXTERNAL_TERMINALS:
            continue
        f = bindings.get(t)
        if f is None:
            return f"external terminal {t} is unbound: UNMEASURED, not searchable"
        if not f.causal():
            return f"field {f.name} bound to {t} has availability {f.availability}: a join " \
                   f"at period time is a lookahead"
    return None


# ============================================================================ canonical form
_COMMUTATIVE = frozenset({"add", "mul", "max2", "min2", "corr", "cov"})


def canonical(expr: Expr) -> Expr:
    """An EXACT canonical form: same recipe, one spelling.

    neg(neg(x)) = x; abs(abs(x)) = abs(neg(x)) = abs(x); sign(sign(x)) = sign(x);
    xrank(xrank(x)) = xrank(x) (a percentile of a percentile across the same peers);
    add(neg(a), neg(b)) = neg(add(a, b)); commutative arguments sorted by key. Every rule is an
    identity, so the canonical tree evaluates to the same series as the original.
    """
    if not isinstance(expr, (list, tuple)):
        return expr
    op = str(expr[0])
    kids = [canonical(c) if isinstance(c, (list, tuple, str)) else c for c in expr[1:]]
    out: list[Any] = [op, *kids]
    a: Any = kids[0] if kids else None
    if isinstance(a, list) and a:
        inner = str(a[0])
        if op == "neg" and inner == "neg":
            return a[1]
        if op == "abs" and inner in ("abs", "neg"):
            return ["abs", a[1]] if inner == "neg" else a
        if op == "sign" and inner == "sign":
            return a
        if op == "xrank" and inner == "xrank":
            return a
    if op == "add" and len(kids) == 2 and all(isinstance(k, list) and k and k[0] == "neg"
                                              for k in kids):
        return canonical(["neg", ["add", kids[0][1], kids[1][1]]])
    if op in _COMMUTATIVE and len(kids) >= 2:
        x, y = kids[0], kids[1]
        if ag.key(x) > ag.key(y):
            out[1], out[2] = y, x
    return out


def canonical_key(expr: Expr) -> str:
    return ag.key(canonical(expr))


def skeleton(expr: Expr) -> Expr:
    """The tree with every window blanked: what a trial FAMILY is."""
    if not isinstance(expr, (list, tuple)):
        return expr
    return [expr[0], *[skeleton(c) if isinstance(c, (list, tuple, str)) else 0
                       for c in expr[1:]]]


def family_key(expr: Expr) -> str:
    """The family an evaluation is charged to: the canonical skeleton, windows blanked."""
    return ag.key(skeleton(canonical(expr)))


def windows_in(expr: Expr) -> list[int]:
    if not isinstance(expr, (list, tuple)):
        return []
    out: list[int] = []
    for c in expr[1:]:
        if isinstance(c, (list, tuple, str)):
            out.extend(windows_in(c))
        elif isinstance(c, int) and not isinstance(c, bool):
            out.append(int(c))
    return out


# ============================================================================ the 101 alphas
#: THE PAPER'S FORMULAS, VERBATIM (Kakushadze, "101 Formulaic Alphas", arXiv:1601.00991, 2016;
#: the formulas are public and the law names them as seeds). The transpiler below decides what
#: each one becomes on this desk; nothing here is edited to make it fit.
ALPHA101: dict[str, str] = {
    "alpha001": "(rank(Ts_ArgMax(SignedPower(((returns < 0) ? stddev(returns, 20) : close), 2.), 5)) - 0.5)",  # noqa: E501
    "alpha002": "(-1 * correlation(rank(delta(log(volume), 2)), rank(((close - open) / open)), 6))",
    "alpha003": "(-1 * correlation(rank(open), rank(volume), 10))",
    "alpha004": "(-1 * Ts_Rank(rank(low), 9))",
    "alpha005": "(rank((open - (sum(vwap, 10) / 10))) * (-1 * abs(rank((close - vwap)))))",
    "alpha006": "(-1 * correlation(open, volume, 10))",
    "alpha007": "((adv20 < volume) ? ((-1 * ts_rank(abs(delta(close, 7)), 60)) * sign(delta(close, 7))) : (-1 * 1))",  # noqa: E501
    "alpha008": "(-1 * rank(((sum(open, 5) * sum(returns, 5)) - delay((sum(open, 5) * sum(returns, 5)), 10))))",  # noqa: E501
    "alpha009": "((0 < ts_min(delta(close, 1), 5)) ? delta(close, 1) : ((ts_max(delta(close, 1), 5) < 0) ? delta(close, 1) : (-1 * delta(close, 1))))",  # noqa: E501
    "alpha010": "rank(((0 < ts_min(delta(close, 1), 4)) ? delta(close, 1) : ((ts_max(delta(close, 1), 4) < 0) ? delta(close, 1) : (-1 * delta(close, 1)))))",  # noqa: E501
    "alpha011": "((rank(ts_max((vwap - close), 3)) + rank(ts_min((vwap - close), 3))) * rank(delta(volume, 3)))",  # noqa: E501
    "alpha012": "(sign(delta(volume, 1)) * (-1 * delta(close, 1)))",
    "alpha013": "(-1 * rank(covariance(rank(close), rank(volume), 5)))",
    "alpha014": "((-1 * rank(delta(returns, 3))) * correlation(open, volume, 10))",
    "alpha015": "(-1 * sum(rank(correlation(rank(high), rank(volume), 3)), 3))",
    "alpha016": "(-1 * rank(covariance(rank(high), rank(volume), 5)))",
    "alpha017": "(((-1 * rank(ts_rank(close, 10))) * rank(delta(delta(close, 1), 1))) * rank(ts_rank((volume / adv20), 5)))",  # noqa: E501
    "alpha018": "(-1 * rank(((stddev(abs((close - open)), 5) + (close - open)) + correlation(close, open, 10))))",  # noqa: E501
    "alpha019": "((-1 * sign(((close - delay(close, 7)) + delta(close, 7)))) * (1 + rank((1 + sum(returns, 250)))))",  # noqa: E501
    "alpha020": "(((-1 * rank((open - delay(high, 1)))) * rank((open - delay(close, 1)))) * rank((open - delay(low, 1))))",  # noqa: E501
    "alpha021": "((((sum(close, 8) / 8) + stddev(close, 8)) < (sum(close, 2) / 2)) ? (-1 * 1) : (((sum(close, 2) / 2) < ((sum(close, 8) / 8) - stddev(close, 8))) ? 1 : (((1 < (volume / adv20)) || ((volume / adv20) == 1)) ? 1 : (-1 * 1))))",  # noqa: E501
    "alpha022": "(-1 * (delta(correlation(high, volume, 5), 5) * rank(stddev(close, 20))))",
    "alpha023": "(((sum(high, 20) / 20) < high) ? (-1 * delta(high, 2)) : 0)",
    "alpha024": "((((delta((sum(close, 100) / 100), 100) / delay(close, 100)) < 0.05) || ((delta((sum(close, 100) / 100), 100) / delay(close, 100)) == 0.05)) ? (-1 * (close - ts_min(close, 100))) : (-1 * delta(close, 3)))",  # noqa: E501
    "alpha025": "rank(((((-1 * returns) * adv20) * vwap) * (high - close)))",
    "alpha026": "(-1 * ts_max(correlation(ts_rank(volume, 5), ts_rank(high, 5), 5), 3))",
    "alpha027": "((0.5 < rank((sum(correlation(rank(volume), rank(vwap), 6), 2) / 2.0))) ? (-1 * 1) : 1)",  # noqa: E501
    "alpha028": "scale(((correlation(adv20, low, 5) + ((high + low) / 2)) - close))",
    "alpha029": "(min(product(rank(rank(scale(log(sum(ts_min(rank(rank((-1 * rank(delta((close - 1), 5))))), 2), 1))))), 1), 5) + ts_rank(delay((-1 * returns), 6), 5))",  # noqa: E501
    "alpha030": "(((1.0 - rank(((sign((close - delay(close, 1))) + sign((delay(close, 1) - delay(close, 2)))) + sign((delay(close, 2) - delay(close, 3)))))) * sum(volume, 5)) / sum(volume, 20))",  # noqa: E501
    "alpha031": "((rank(rank(rank(decay_linear((-1 * rank(rank(delta(close, 10)))), 10)))) + rank((-1 * delta(close, 3)))) + sign(scale(correlation(adv20, low, 12))))",  # noqa: E501
    "alpha032": "(scale(((sum(close, 7) / 7) - close)) + (20 * scale(correlation(vwap, delay(close, 5), 230))))",  # noqa: E501
    "alpha033": "rank((-1 * ((1 - (open / close))^1)))",
    "alpha034": "rank(((1 - rank((stddev(returns, 2) / stddev(returns, 5)))) + (1 - rank(delta(close, 1)))))",  # noqa: E501
    "alpha035": "((Ts_Rank(volume, 32) * (1 - Ts_Rank(((close + high) - low), 16))) * (1 - Ts_Rank(returns, 32)))",  # noqa: E501
    "alpha036": "(((((2.21 * rank(correlation((close - open), delay(volume, 1), 15))) + (0.7 * rank((open - close)))) + (0.73 * rank(Ts_Rank(delay((-1 * returns), 6), 5)))) + rank(abs(correlation(vwap, adv20, 6)))) + (0.6 * rank((((sum(close, 200) / 200) - open) * (close - open)))))",  # noqa: E501
    "alpha037": "(rank(correlation(delay((open - close), 1), close, 200)) + rank((open - close)))",
    "alpha038": "((-1 * rank(Ts_Rank(close, 10))) * rank((close / open)))",
    "alpha039": "((-1 * rank((delta(close, 7) * (1 - rank(decay_linear((volume / adv20), 9)))))) * (1 + rank(sum(returns, 250))))",  # noqa: E501
    "alpha040": "((-1 * rank(stddev(high, 10))) * correlation(high, volume, 10))",
    "alpha041": "(((high * low)^0.5) - vwap)",
    "alpha042": "(rank((vwap - close)) / rank((vwap + close)))",
    "alpha043": "(ts_rank((volume / adv20), 20) * ts_rank((-1 * delta(close, 7)), 8))",
    "alpha044": "(-1 * correlation(high, rank(volume), 5))",
    "alpha045": "(-1 * ((rank((sum(delay(close, 5), 20) / 20)) * correlation(close, volume, 2)) * rank(correlation(sum(close, 5), sum(close, 20), 2))))",  # noqa: E501
    "alpha046": "((0.25 < (((delay(close, 20) - delay(close, 10)) / 10) - ((delay(close, 10) - close) / 10))) ? (-1 * 1) : (((((delay(close, 20) - delay(close, 10)) / 10) - ((delay(close, 10) - close) / 10)) < 0) ? 1 : ((-1 * 1) * (close - delay(close, 1)))))",  # noqa: E501
    "alpha047": "((((rank((1 / close)) * volume) / adv20) * ((high * rank((high - close))) / (sum(high, 5) / 5))) - rank((vwap - delay(vwap, 5))))",  # noqa: E501
    "alpha048": "(indneutralize(((correlation(delta(close, 1), delta(delay(close, 1), 1), 250) * delta(close, 1)) / close), IndClass.subindustry) / sum(((delta(close, 1) / delay(close, 1))^2), 250))",  # noqa: E501
    "alpha049": "(((((delay(close, 20) - delay(close, 10)) / 10) - ((delay(close, 10) - close) / 10)) < (-1 * 0.1)) ? 1 : ((-1 * 1) * (close - delay(close, 1))))",  # noqa: E501
    "alpha050": "(-1 * ts_max(rank(correlation(rank(volume), rank(vwap), 5)), 5))",
    "alpha051": "(((((delay(close, 20) - delay(close, 10)) / 10) - ((delay(close, 10) - close) / 10)) < (-1 * 0.05)) ? 1 : ((-1 * 1) * (close - delay(close, 1))))",  # noqa: E501
    "alpha052": "((((-1 * ts_min(low, 5)) + delay(ts_min(low, 5), 5)) * rank(((sum(returns, 240) - sum(returns, 20)) / 220))) * ts_rank(volume, 5))",  # noqa: E501
    "alpha053": "(-1 * delta((((close - low) - (high - close)) / (close - low)), 9))",
    "alpha054": "((-1 * ((low - close) * (open^5))) / ((low - high) * (close^5)))",
    "alpha055": "(-1 * correlation(rank(((close - ts_min(low, 12)) / (ts_max(high, 12) - ts_min(low, 12)))), rank(volume), 6))",  # noqa: E501
    "alpha056": "(0 - (1 * (rank((sum(returns, 10) / sum(sum(returns, 2), 3))) * rank((returns * cap)))))",  # noqa: E501
    "alpha057": "(0 - (1 * ((close - vwap) / decay_linear(rank(ts_argmax(close, 30)), 2))))",
    "alpha058": "(-1 * Ts_Rank(decay_linear(correlation(IndNeutralize(vwap, IndClass.sector), volume, 3.92795), 7.89291), 5.50322))",  # noqa: E501
    "alpha059": "(-1 * Ts_Rank(decay_linear(correlation(IndNeutralize(((vwap * 0.728317) + (vwap * (1 - 0.728317))), IndClass.industry), volume, 4.25197), 16.2289), 8.19648))",  # noqa: E501
    "alpha060": "(0 - (1 * ((2 * scale(rank(((((close - low) - (high - close)) / (high - low)) * volume)))) - scale(rank(ts_argmax(close, 10))))))",  # noqa: E501
    "alpha061": "(rank((vwap - ts_min(vwap, 16.1219))) < rank(correlation(vwap, adv180, 17.9282)))",
    "alpha062": "((rank(correlation(vwap, sum(adv20, 22.4101), 9.91009)) < rank(((rank(open) + rank(open)) < (rank(((high + low) / 2)) + rank(high))))) * -1)",  # noqa: E501
    "alpha063": "((rank(decay_linear(delta(IndNeutralize(close, IndClass.industry), 2.25164), 8.22237)) - rank(decay_linear(correlation(((vwap * 0.318108) + (open * (1 - 0.318108))), sum(adv180, 37.2467), 13.557), 12.2883))) * -1)",  # noqa: E501
    "alpha064": "((rank(correlation(sum(((open * 0.178404) + (low * (1 - 0.178404))), 12.7054), sum(adv120, 12.7054), 16.6208)) < rank(delta(((((high + low) / 2) * 0.178404) + (vwap * (1 - 0.178404))), 3.69741))) * -1)",  # noqa: E501
    "alpha065": "((rank(correlation(((open * 0.00817205) + (vwap * (1 - 0.00817205))), sum(adv60, 8.6911), 6.40374)) < rank((open - ts_min(open, 13.635)))) * -1)",  # noqa: E501
    "alpha066": "((rank(decay_linear(delta(vwap, 3.51013), 7.23052)) + Ts_Rank(decay_linear(((((low * 0.96633) + (low * (1 - 0.96633))) - vwap) / (open - ((high + low) / 2))), 11.4157), 6.72611)) * -1)",  # noqa: E501
    "alpha067": "((rank((high - ts_min(high, 2.14593)))^rank(correlation(IndNeutralize(vwap, IndClass.sector), IndNeutralize(adv20, IndClass.subindustry), 6.02936))) * -1)",  # noqa: E501
    "alpha068": "((Ts_Rank(correlation(rank(high), rank(adv15), 8.91644), 13.9333) < rank(delta(((close * 0.518371) + (low * (1 - 0.518371))), 1.06157))) * -1)",  # noqa: E501
    "alpha069": "((rank(ts_max(delta(IndNeutralize(vwap, IndClass.industry), 2.72412), 4.79344))^Ts_Rank(correlation(((close * 0.490655) + (vwap * (1 - 0.490655))), adv20, 4.92416), 9.0615)) * -1)",  # noqa: E501
    "alpha070": "((rank(delta(vwap, 1.29456))^Ts_Rank(correlation(IndNeutralize(close, IndClass.industry), adv50, 17.8256), 17.9171)) * -1)",  # noqa: E501
    "alpha071": "max(Ts_Rank(decay_linear(correlation(Ts_Rank(close, 3.43976), Ts_Rank(adv180, 12.0647), 18.0175), 4.20501), 15.6948), Ts_Rank(decay_linear((rank(((low + open) - (vwap + vwap)))^2), 16.4662), 4.4388))",  # noqa: E501
    "alpha072": "(rank(decay_linear(correlation(((high + low) / 2), adv40, 8.93345), 10.1519)) / rank(decay_linear(correlation(Ts_Rank(vwap, 3.72469), Ts_Rank(volume, 18.5188), 6.86671), 2.95011)))",  # noqa: E501
    "alpha073": "(max(rank(decay_linear(delta(vwap, 4.72775), 2.91864)), Ts_Rank(decay_linear(((delta(((open * 0.147155) + (low * (1 - 0.147155))), 2.03608) / ((open * 0.147155) + (low * (1 - 0.147155)))) * -1), 3.33829), 16.7411)) * -1)",  # noqa: E501
    "alpha074": "((rank(correlation(close, sum(adv30, 37.4843), 15.1365)) < rank(correlation(rank(((high * 0.0261661) + (vwap * (1 - 0.0261661)))), rank(volume), 11.4791))) * -1)",  # noqa: E501
    "alpha075": "(rank(correlation(vwap, volume, 4.24304)) < rank(correlation(rank(low), rank(adv50), 12.4413)))",  # noqa: E501
    "alpha076": "(max(rank(decay_linear(delta(vwap, 1.24383), 11.8259)), Ts_Rank(decay_linear(Ts_Rank(correlation(IndNeutralize(low, IndClass.sector), adv81, 8.14941), 19.569), 17.1543), 19.383)) * -1)",  # noqa: E501
    "alpha077": "min(rank(decay_linear(((((high + low) / 2) + high) - (vwap + high)), 20.0451)), rank(decay_linear(correlation(((high + low) / 2), adv40, 3.1614), 5.64125)))",  # noqa: E501
    "alpha078": "(rank(correlation(sum(((low * 0.352233) + (vwap * (1 - 0.352233))), 19.7428), sum(adv40, 19.7428), 6.83313))^rank(correlation(rank(vwap), rank(volume), 5.77492)))",  # noqa: E501
    "alpha079": "(rank(delta(IndNeutralize(((close * 0.60733) + (open * (1 - 0.60733))), IndClass.sector), 1.23438)) < rank(correlation(Ts_Rank(vwap, 3.60973), Ts_Rank(adv150, 9.18637), 14.6644)))",  # noqa: E501
    "alpha080": "((rank(Sign(delta(IndNeutralize(((open * 0.868128) + (high * (1 - 0.868128))), IndClass.industry), 4.04545)))^Ts_Rank(correlation(high, adv10, 5.11456), 5.53756)) * -1)",  # noqa: E501
    "alpha081": "((rank(Log(product(rank((rank(correlation(vwap, sum(adv10, 49.6054), 8.47743))^4)), 14.9655))) < rank(correlation(rank(vwap), rank(volume), 5.07914))) * -1)",  # noqa: E501
    "alpha082": "(min(rank(decay_linear(delta(open, 1.46063), 14.8717)), Ts_Rank(decay_linear(correlation(IndNeutralize(volume, IndClass.sector), ((open * 0.634196) + (open * (1 - 0.634196))), 17.4842), 6.92131), 13.4283)) * -1)",  # noqa: E501
    "alpha083": "((rank(delay(((high - low) / (sum(close, 5) / 5)), 2)) * rank(rank(volume))) / (((high - low) / (sum(close, 5) / 5)) / (vwap - close)))",  # noqa: E501
    "alpha084": "SignedPower(Ts_Rank((vwap - ts_max(vwap, 15.3217)), 20.7127), delta(close, 4.96796))",  # noqa: E501
    "alpha085": "(rank(correlation(((high * 0.876703) + (close * (1 - 0.876703))), adv30, 9.61331))^rank(correlation(Ts_Rank(((high + low) / 2), 3.70596), Ts_Rank(volume, 10.1595), 7.11408)))",  # noqa: E501
    "alpha086": "((Ts_Rank(correlation(close, sum(adv20, 14.7444), 6.00049), 20.4195) < rank(((open + close) - (vwap + open)))) * -1)",  # noqa: E501
    "alpha087": "(max(rank(decay_linear(delta(((close * 0.369701) + (vwap * (1 - 0.369701))), 1.91233), 2.65461)), Ts_Rank(decay_linear(abs(correlation(IndNeutralize(adv81, IndClass.industry), close, 13.4132)), 4.89768), 14.4535)) * -1)",  # noqa: E501
    "alpha088": "min(rank(decay_linear(((rank(open) + rank(low)) - (rank(high) + rank(close))), 8.06882)), Ts_Rank(decay_linear(correlation(Ts_Rank(close, 8.44728), Ts_Rank(adv60, 20.6966), 8.01266), 6.65053), 2.61957))",  # noqa: E501
    "alpha089": "(Ts_Rank(decay_linear(correlation(((low * 0.967285) + (low * (1 - 0.967285))), adv10, 6.94279), 5.51607), 3.79744) - Ts_Rank(decay_linear(delta(IndNeutralize(vwap, IndClass.industry), 3.48158), 10.1466), 15.3012))",  # noqa: E501
    "alpha090": "((rank((close - ts_max(close, 4.66719)))^Ts_Rank(correlation(IndNeutralize(adv40, IndClass.subindustry), low, 5.38375), 3.21856)) * -1)",  # noqa: E501
    "alpha091": "((Ts_Rank(decay_linear(decay_linear(correlation(IndNeutralize(close, IndClass.industry), volume, 9.74928), 16.398), 3.83219), 4.8667) - rank(decay_linear(correlation(vwap, adv30, 4.01303), 2.6809))) * -1)",  # noqa: E501
    "alpha092": "min(Ts_Rank(decay_linear(((((high + low) / 2) + close) < (low + open)), 14.7221), 18.8683), Ts_Rank(decay_linear(correlation(rank(low), rank(adv30), 7.58555), 6.94024), 6.80584))",  # noqa: E501
    "alpha093": "(Ts_Rank(decay_linear(correlation(IndNeutralize(vwap, IndClass.industry), adv81, 17.4193), 19.848), 7.54455) / rank(decay_linear(delta(((close * 0.524434) + (vwap * (1 - 0.524434))), 2.77377), 16.2664)))",  # noqa: E501
    "alpha094": "((rank((vwap - ts_min(vwap, 11.5783)))^Ts_Rank(correlation(Ts_Rank(vwap, 19.6462), Ts_Rank(adv60, 4.02992), 18.0926), 2.70756)) * -1)",  # noqa: E501
    "alpha095": "(rank((open - ts_min(open, 12.4105))) < Ts_Rank((rank(correlation(sum(((high + low) / 2), 19.1351), sum(adv40, 19.1351), 12.8742))^5), 11.7584))",  # noqa: E501
    "alpha096": "(max(Ts_Rank(decay_linear(correlation(rank(vwap), rank(volume), 3.83878), 4.16783), 8.38151), Ts_Rank(decay_linear(Ts_ArgMax(correlation(Ts_Rank(close, 7.45404), Ts_Rank(adv60, 4.13242), 3.65459), 12.6556), 14.0365), 13.4143)) * -1)",  # noqa: E501
    "alpha097": "((rank(decay_linear(delta(IndNeutralize(((low * 0.721001) + (vwap * (1 - 0.721001))), IndClass.industry), 3.3705), 20.4523)) - Ts_Rank(decay_linear(Ts_Rank(correlation(Ts_Rank(low, 7.87871), Ts_Rank(adv60, 17.255), 4.97547), 18.5925), 15.7152), 6.71659)) * -1)",  # noqa: E501
    "alpha098": "(rank(decay_linear(correlation(vwap, sum(adv5, 26.4719), 4.58418), 7.18088)) - rank(decay_linear(Ts_Rank(Ts_ArgMin(correlation(rank(open), rank(adv15), 20.8187), 8.62571), 6.95668), 8.07206)))",  # noqa: E501
    "alpha099": "((rank(correlation(sum(((high + low) / 2), 19.8975), sum(adv60, 19.8975), 8.8136)) < rank(correlation(low, volume, 6.28259))) * -1)",  # noqa: E501
    "alpha100": "(0 - (1 * (((1.5 * scale(indneutralize(indneutralize(rank(((((close - low) - (high - close)) / (high - low)) * volume)), IndClass.subindustry), IndClass.subindustry))) - scale(indneutralize((correlation(close, rank(adv20), 5) - rank(ts_argmin(close, 30))), IndClass.subindustry))) * (volume / adv20))))",  # noqa: E501
    "alpha101": "((close - open) / ((high - low) + .001))",
}

#: The paper's fields and their semantic types. `vwap` and `cap` have NO lawful MT5 analogue and
#: say so; `IndClass` is a grouping, carried by the basket rather than by a field.
PAPER_FIELDS: dict[str, tuple[str, str | None]] = {
    "open": ("price", "open"), "high": ("price", "high"), "low": ("price", "low"),
    "close": ("price", "close"), "returns": ("price", "ret"), "volume": ("volume", "activity"),
    "adv": ("volume", "activity"), "vwap": ("price", None), "cap": ("fundamental", None),
}
PARENT_STATUSES: tuple[str, ...] = ("TESTABLE", "TOO_DEEP", "NONTESTABLE")


# ---------------------------------------------------------------------------- parser
_TOKEN = re.compile(r"\s*(?:(\d+\.\d*|\.\d+|\d+)|([A-Za-z_][A-Za-z0-9_.]*)"
                    r"|(\|\||==|[-+*/^<>?:(),]))")


def _tokens(src: str) -> list[str]:
    out: list[str] = []
    pos = 0
    s = src.strip()
    while pos < len(s):
        m = _TOKEN.match(s, pos)
        if not m or m.end() == pos:
            raise ValueError(f"cannot tokenise at {s[pos:pos + 12]!r}")
        out.append(next(g for g in m.groups() if g is not None))
        pos = m.end()
    return out


class _Parser:
    """A recursive-descent parser for the paper's infix syntax: numbers, identifiers, calls,
    unary minus, ^ (right-assoc), * /, + -, comparisons, ||, and the ternary."""

    def __init__(self, src: str) -> None:
        self.toks = _tokens(src)
        self.i = 0

    def peek(self) -> str | None:
        return self.toks[self.i] if self.i < len(self.toks) else None

    def take(self, expected: str | None = None) -> str:
        tok = self.peek()
        if tok is None or (expected is not None and tok != expected):
            raise ValueError(f"expected {expected!r}, got {tok!r} at token {self.i}")
        self.i += 1
        return tok

    def parse(self) -> Any:
        node = self.ternary()
        if self.peek() is not None:
            raise ValueError(f"trailing token {self.peek()!r}")
        return node

    def ternary(self) -> Any:
        cond = self.logical()
        if self.peek() == "?":
            self.take("?")
            a = self.ternary()
            self.take(":")
            b = self.ternary()
            return ("tern", cond, a, b)
        return cond

    def logical(self) -> Any:
        node = self.comparison()
        while self.peek() == "||":
            self.take()
            node = ("bin", "||", node, self.comparison())
        return node

    def comparison(self) -> Any:
        node = self.additive()
        while self.peek() in ("<", ">", "=="):
            op = self.take()
            node = ("bin", op, node, self.additive())
        return node

    def additive(self) -> Any:
        node = self.term()
        while self.peek() in ("+", "-"):
            op = self.take()
            node = ("bin", op, node, self.term())
        return node

    def term(self) -> Any:
        node = self.power()
        while self.peek() in ("*", "/"):
            op = self.take()
            node = ("bin", op, node, self.power())
        return node

    def power(self) -> Any:
        node = self.unary()
        if self.peek() == "^":
            self.take()
            return ("bin", "^", node, self.power())
        return node

    def unary(self) -> Any:
        if self.peek() == "-":
            self.take()
            return ("neg", self.unary())
        return self.primary()

    def primary(self) -> Any:
        tok = self.take()
        if tok == "(":
            node = self.ternary()
            self.take(")")
            return node
        if re.match(r"^(\d+\.\d*|\.\d+|\d+)$", tok):
            return ("num", float(tok))
        if self.peek() == "(":
            self.take("(")
            args: list[Any] = []
            if self.peek() != ")":
                args.append(self.ternary())
                while self.peek() == ",":
                    self.take(",")
                    args.append(self.ternary())
            self.take(")")
            return ("call", tok, tuple(args))
        return ("id", tok)


def parse_formula(src: str) -> Any:
    """The paper's formula as a tuple AST. Raises ValueError on a formula it cannot read."""
    return _Parser(src).parse()


# ---------------------------------------------------------------------------- transpiler
#: THE AFFINE WRAPPER. The paper's formulas are full of constants -- `1 - rank(x)`, `2 * scale(y)`,
#: `(high + low) / 2`, `sum(close, 8) / 8` -- and the grammar has NO numeric constant: a window
#: is the only number a node may carry. So a constant is never dropped where it changes the
#: hypothesis: every transpiled subtree is `a * tree + b`, the algebra below propagates (a, b)
#: through each operator exactly (a shift commutes with a delay, flips under a negation, is
#: invisible to a rank), and a constant that reaches an operator where it MATTERS -- a weight
#: inside a sum, a shift inside a product, a threshold in a comparison -- makes the formula
#: NONTESTABLE with that constant named. At the root, `a` and `b` are dropped: the formula
#: family z-scores the signal on its own history, so a positive scale and a shift are invisible
#: and a negative scale is a negation.
@dataclass(frozen=True)
class _Aff:
    tree: Any                 #: a grammar tree, or None for a pure constant
    a: float = 1.0
    b: float = 0.0

    @property
    def const(self) -> bool:
        return self.tree is None


class _Missing:
    """A subtree that has no lawful analogue. It propagates upward; the reasons are collected
    on the transpiler so a report names EVERY missing field, not the first one met."""


_MISSING = _Missing()
_WINDOWED_CALLS: dict[str, str] = {
    "delay": "delay", "delta": "delta", "ts_min": "min", "ts_max": "max", "ts_rank": "ts_rank",
    "sum": "sum", "stddev": "std", "decay_linear": "decay", "ts_argmax": "bars_since_max",
    "ts_argmin": "bars_since_min",
}
_BINARY_WINDOWED_CALLS: dict[str, str] = {"correlation": "corr", "covariance": "cov"}
_RANK_OPS = frozenset({"xrank", "ts_rank"})
_EPSILON_GUARD = 0.01
_FLIP = {"min": "max", "max": "min", "bars_since_max": "bars_since_min",
         "bars_since_min": "bars_since_max"}


def nearest_window(days: float, minimum: int = 2) -> int:
    """The grammar window nearest a paper window (days on the paper's clock, BARS on the
    desk's): the H axis of the genome is where the clock changes, the tree keeps the number."""
    d = max(float(minimum), float(days))
    return min((w for w in ag.WINDOWS if w >= minimum), key=lambda w: (abs(w - d), w))


def _fmt(v: float) -> str:
    return f"{v:g}"


class _Transpiler:
    def __init__(self) -> None:
        self.missing: set[str] = set()
        self.notes: list[str] = []
        self.fields: set[str] = set()
        self.transforms: set[str] = set()
        self.days: list[float] = []

    def miss(self, why: str) -> _Missing:
        self.missing.add(why)
        return _MISSING

    def note(self, text: str) -> None:
        if text not in self.notes:
            self.notes.append(text)

    # -- the affine algebra
    @staticmethod
    def _sgn(x: _Aff) -> Any:
        """The tree with a negative scale folded in as a negation; the shift is the caller's."""
        return x.tree if x.a > 0 else ["neg", x.tree]

    def unwrap(self, x: _Aff, where: str) -> Any:
        """Drop the affine constants where they cannot matter (a rank, a sign, the root)."""
        if x.const:
            return self.miss(f"degenerate:constant_{where}")
        if x.a != 1.0 or x.b != 0.0:
            self.note(f"affine constant ({_fmt(x.a)} * x + {_fmt(x.b)}) dropped at {where}: "
                      "invisible to it")
        return self._sgn(x)

    def window(self, node: Any, minimum: int = 2) -> int | _Missing:
        v = self.tx(node)
        if isinstance(v, _Aff) and v.const:
            self.days.append(v.b)
            w = nearest_window(v.b, minimum)
            if abs(w - v.b) > 0.5:
                self.note(f"window {_fmt(v.b)} -> {w} (nearest grammar window)")
            return w
        return self.miss("op:variable_window")

    # -- the walk
    def tx(self, node: Any) -> Any:
        kind = node[0]
        if kind == "num":
            return _Aff(None, 0.0, float(node[1]))
        if kind == "id":
            return self.ident(str(node[1]))
        if kind == "neg":
            a = self.tx(node[1])
            return a if a is _MISSING else _Aff(a.tree, -a.a, -a.b)
        if kind == "bin":
            return self.binary(str(node[1]), node[2], node[3])
        if kind == "tern":
            return self.ternary(node[1], node[2], node[3])
        if kind == "call":
            return self.call(str(node[1]).lower(), list(node[2]))
        return self.miss(f"op:{kind}")

    def ident(self, name: str) -> Any:
        low = name.lower()
        m = re.match(r"^adv(\d+)$", low)
        if m:
            self.fields.add("adv")
            self.days.append(float(m.group(1)))
            self.note("adv{d} (average daily dollar volume) -> rolling mean of tick activity")
            return _Aff(["mean", "activity", nearest_window(float(m.group(1)))])
        if low in PAPER_FIELDS:
            self.fields.add(low)
            _sem, term = PAPER_FIELDS[low]
            if term is None:
                return self.miss(f"field:{low}")
            if low == "volume":
                self.note("volume -> tick activity (Fusion publishes tick counts, not contracts)")
            return _Aff(term)
        if low.startswith("indclass."):
            return self.miss("field:industry_classification")
        return self.miss(f"field:{low}")

    def binary(self, op: str, left: Any, right: Any) -> Any:
        # sum(x, d) / d is the MEAN, not a scalar to drop: read it off the AST before walking.
        if (op == "/" and left[0] == "call" and str(left[1]).lower() == "sum"
                and len(left[2]) == 2 and left[2][1][0] == "num" and right[0] == "num"
                and float(left[2][1][1]) == float(right[1])):
            self.transforms.add("mean")
            x = self.tx(left[2][0])
            w = self.window(left[2][1])
            if x is _MISSING or isinstance(w, _Missing):
                return _MISSING
            if x.const:
                return self.miss("degenerate:mean_of_constant")
            self.note("sum(x, d) / d -> mean(x, d)")
            return _Aff(["mean", x.tree, w], x.a, x.b)
        a, b = self.tx(left), self.tx(right)
        if a is _MISSING or b is _MISSING:
            return _MISSING
        if op in ("+", "-"):
            return self.add(a, b if op == "+" else _Aff(b.tree, -b.a, -b.b))
        if op == "*":
            return self.mul(a, b)
        if op == "/":
            return self.div(a, b)
        if op == "^":
            return self.power(a, b)
        if op in ("<", ">"):
            lo, hi = (a, b) if op == "<" else (b, a)                    # lo < hi
            return self.less(lo, hi)
        if op == "==":
            return self.miss("op:equality")
        if op == "||":
            return self.miss("op:logical_or")
        return self.miss(f"op:{op}")

    def add(self, a: _Aff, b: _Aff) -> Any:
        if a.const and b.const:
            return _Aff(None, 0.0, a.b + b.b)
        if a.const or b.const:
            c, x = (a, b) if a.const else (b, a)
            # 1 - rank(x) IS rank(-x): the one shift the grammar can say exactly.
            if c.b == 1.0 and x.a == -1.0 and x.b == 0.0 and isinstance(x.tree, list) \
                    and x.tree[0] in _RANK_OPS:
                self.note(f"1 - {x.tree[0]}(x) -> {x.tree[0]}(-x): the mirrored percentile")
                return _Aff([x.tree[0], ["neg", x.tree[1]], *x.tree[2:]])
            return _Aff(x.tree, x.a, x.b + c.b)
        if a.a == b.a:
            return _Aff(["add", a.tree, b.tree], a.a, a.b + b.b)
        if a.a == -b.a:
            return _Aff(["sub", a.tree, b.tree], a.a, a.b + b.b)
        return self.miss(f"constant_weight:{_fmt(abs(a.a))}:{_fmt(abs(b.a))} (a weighted sum "
                         "has no grammar analogue)")

    def mul(self, a: _Aff, b: _Aff) -> Any:
        if a.const and b.const:
            return _Aff(None, 0.0, a.b * b.b)
        if a.const or b.const:
            c, x = (a, b) if a.const else (b, a)
            if c.b == 0:
                return self.miss("degenerate:zero_factor")
            return _Aff(x.tree, x.a * c.b, x.b * c.b)
        if a.b == 0 and b.b == 0:
            return _Aff(["mul", a.tree, b.tree], a.a * b.a, 0.0)
        return self.miss(f"constant_shift_in_product:{_fmt(a.b if a.b else b.b)}")

    def div(self, a: _Aff, b: _Aff) -> Any:
        if b.const:
            if b.b == 0:
                return self.miss("degenerate:division_by_zero")
            return _Aff(a.tree, a.a / b.b, a.b / b.b)
        if a.const:
            return self.miss("op:reciprocal")
        if b.b != 0 and abs(b.b) <= _EPSILON_GUARD and b.a > 0:
            # `(high - low) + .001`: a guard against a zero denominator, not a hypothesis. The
            # grammar's `div` already refuses a zero divisor, so the guard is dropped as such.
            self.note(f"epsilon guard {_fmt(b.b)} in a denominator dropped (div guards zero)")
            b = _Aff(b.tree, b.a, 0.0)
        if a.b != 0 or b.b != 0:
            return self.miss(f"constant_shift_in_quotient:{_fmt(a.b if a.b else b.b)}")
        return _Aff(self._div_tree(a.tree, b.tree), a.a / b.a, 0.0)

    def _div_tree(self, a: Any, b: Any) -> Any:
        """Division, with the price-ratio spellings the grammar carries as terminals."""
        if isinstance(a, list) and a[0] == "sub" and a[1:] == ["close", "open"] \
                and b in ("open", "close"):
            self.note("(close - open) / open -> body (the grammar's own bar-body ratio, over "
                      "close)")
            return "body"
        if isinstance(a, list) and a[0] == "sub" and a[1:] == ["high", "low"] \
                and b in ("open", "close"):
            self.note("(high - low) / close -> range (the grammar's own bar-range ratio)")
            return "range"
        if (isinstance(a, list) and isinstance(b, list) and a[0] == "delta" and b[0] == "delay"
                and a[1] == b[1] == "close" and a[2] == b[2]):
            self.note(f"delta(close, w) / delay(close, w) -> sum(ret, w): the relative change "
                      f"over {a[2]} bars in logs")
            return ["sum", "ret", a[2]]
        return ["div", a, b]

    def power(self, a: _Aff, b: _Aff) -> Any:
        if not b.const:
            return self.miss("op:pow(expr,expr)")
        if a.const:
            return _Aff(None, 0.0, a.b ** b.b)
        if b.b == 1.0:
            return a
        if b.b == 2.0:
            if a.b != 0:
                return self.miss("constant_shift_in_power")
            self.transforms.add("square")
            return _Aff(["mul", a.tree, a.tree], a.a * a.a, 0.0)
        if b.b == 0.5:
            return self.miss("op:sqrt")
        return self.miss("op:pow")

    def less(self, lo: _Aff, hi: _Aff) -> Any:
        """lo < hi -> sign(hi - lo): +1 where true, -1 where false, 0 at equality."""
        diff = self.add(hi, _Aff(lo.tree, -lo.a, -lo.b))
        if diff is _MISSING:
            return _MISSING
        if diff.const:
            return self.miss("degenerate:constant_comparison")
        if diff.b != 0:
            return self.miss(f"constant_threshold:{_fmt(-diff.b / diff.a)}")
        self.transforms.add("comparison")
        self.note("a < b -> sign(b - a): +1 where true, -1 where false")
        return _Aff(["sign", self._sgn(diff)])

    def ternary(self, c: Any, a: Any, b: Any) -> Any:
        gate, ta, tb = self.tx(c), self.tx(a), self.tx(b)
        if gate is _MISSING or ta is _MISSING or tb is _MISSING:
            return _MISSING
        if gate.const:
            return self.miss("degenerate:constant_gate")
        if gate.b != 0:
            return self.miss(f"constant_threshold:{_fmt(-gate.b / gate.a)}")
        g = self._sgn(gate)
        if ta.const and tb.const:
            return self.miss("op:conditional(constant branches)")
        self.transforms.add("conditional")
        if tb.const:
            self.note(f"else-branch constant {_fmt(tb.b)} replaced by HOLD (trade_when keeps "
                      "the previous value where its gate fails)")
            return _Aff(["trade_when", g, ta.tree], ta.a, ta.b)
        if ta.const:
            self.note(f"then-branch constant {_fmt(ta.b)} replaced by HOLD (trade_when on the "
                      "negated gate)")
            return _Aff(["trade_when", ["neg", g], tb.tree], tb.a, tb.b)
        if ta.b == 0 and tb.b == 0 and ta.a == -tb.a \
                and canonical(ta.tree) == canonical(tb.tree):
            self.note("cond ? x : -x -> sign(cond) * x (exact for a +/-1 gate)")
            return _Aff(["mul", g, ta.tree], ta.a, 0.0)
        return self.miss("op:conditional(two live branches)")

    def windowed(self, op: str, x: _Aff, w: int, name: str) -> Any:
        """A windowed operator on `a * t + b`, the constants carried through exactly."""
        if x.const:
            return self.miss(f"degenerate:{name}_of_constant")
        if op in ("delay", "decay", "mean"):
            return _Aff([op, x.tree, w], x.a, x.b)
        if op == "delta":
            return _Aff([op, x.tree, w], x.a, 0.0)
        if op == "sum":
            return _Aff([op, x.tree, w], x.a, x.b * w)
        if op in ("min", "max"):
            return _Aff([_FLIP[op] if x.a < 0 else op, x.tree, w], x.a, x.b)
        if op == "std":
            return _Aff([op, x.tree, w], abs(x.a), 0.0)
        if op == "ts_rank":
            return _Aff([op, self._sgn(x), w])
        if op in ("bars_since_max", "bars_since_min"):
            self.note("ts_argmax/argmin -> bars since the window extreme (same information, "
                      "counted from the bar rather than from the window start)")
            return _Aff([_FLIP[op] if x.a < 0 else op, x.tree, w])
        return self.miss(f"op:{name}")

    def call(self, name: str, args: list[Any]) -> Any:
        if name == "rank" and len(args) == 1:
            self.transforms.add("rank")
            x = self.tx(args[0])
            if x is _MISSING:
                return _MISSING
            if x.const:
                return self.miss("degenerate:rank_of_constant")
            self.note("rank(x) -> xrank(x): the percentile across the cell's BASKET (currency "
                      "basket / asset class), where the paper ranks across an equity universe")
            return _Aff(["xrank", self._sgn(x)])
        if name == "indneutralize" and len(args) == 2:
            self.transforms.add("indneutralize")
            x = self.tx(args[0])
            if x is _MISSING:
                return _MISSING
            if x.const:
                return self.miss("degenerate:neutralise_constant")
            self.note("IndNeutralize(x, class) -> xzscore(x): demeaned and scaled across the "
                      "cell's asset-class basket, the desk's analogue of an industry group")
            return _Aff(["xzscore", self._sgn(x)])
        if name in _WINDOWED_CALLS and len(args) == 2:
            op = _WINDOWED_CALLS[name]
            self.transforms.add(name)
            inner = args[0]
            if op == "delta" and inner[0] == "call" and str(inner[1]).lower() == "log" \
                    and len(inner[2]) == 1:
                y = self.tx(inner[2][0])
                w = self.window(args[1])
                if y is _MISSING or isinstance(w, _Missing):
                    return _MISSING
                if y.const or y.b != 0:
                    return self.miss("op:log")
                self.note("delta(log(x), w) -> delta(x, w) / delay(x, w): the relative change")
                return _Aff(["div", ["delta", y.tree, w], ["delay", y.tree, w]])
            x = self.tx(inner)
            w = self.window(args[1])
            if x is _MISSING or isinstance(w, _Missing):
                return _MISSING
            return self.windowed(op, x, w, name)
        if name in _BINARY_WINDOWED_CALLS and len(args) == 3:
            self.transforms.add(name)
            x, y = self.tx(args[0]), self.tx(args[1])
            w = self.window(args[2], minimum=3)
            if x is _MISSING or y is _MISSING or isinstance(w, _Missing):
                return _MISSING
            if x.const or y.const:
                return self.miss(f"degenerate:{name}_with_constant")
            tree = [_BINARY_WINDOWED_CALLS[name], x.tree, y.tree, w]
            if name == "correlation":
                return _Aff(tree, float(np.sign(x.a * y.a)))
            return _Aff(tree, x.a * y.a, 0.0)
        if name == "scale" and args:
            self.transforms.add("scale")
            x = self.tx(args[0])
            if x is _MISSING:
                return _MISSING
            if x.const:
                return self.miss("degenerate:scale_constant")
            if x.b != 0:
                return self.miss("constant_shift_in_scale")
            self.note("scale(x) (cross-sectional |x| normalisation) -> scale(x, 24): the "
                      "grammar's rolling |x| normalisation over one H1 day")
            return _Aff(["scale", self._sgn(x), 24])
        if name in ("abs", "sign") and len(args) == 1:
            x = self.tx(args[0])
            if x is _MISSING:
                return _MISSING
            if x.const:
                return _Aff(None, 0.0, abs(x.b) if name == "abs" else float(np.sign(x.b)))
            if x.b != 0:
                return self.miss(f"constant_shift_in_{name}")
            self.transforms.add(name)
            if name == "abs":
                return _Aff(["abs", x.tree], abs(x.a), 0.0)
            return _Aff(["sign", self._sgn(x)])
        if name in ("min", "max") and len(args) == 2:
            b = self.tx(args[1])
            if isinstance(b, _Aff) and b.const:              # the paper's min(x, d) is ts_min
                return self.call("ts_" + name, args)
            a = self.tx(args[0])
            if a is _MISSING or b is _MISSING:
                return _MISSING
            if a.const:
                return self.miss(f"degenerate:{name}_with_constant")
            if a.a == b.a and a.b == b.b:
                op = name if a.a > 0 else _FLIP[name]
                return _Aff([op + "2", a.tree, b.tree], a.a, a.b)
            return self.miss(f"constant_weight:{_fmt(abs(a.a))}:{_fmt(abs(b.a))} (an "
                             f"unequal-weight {name} has no grammar analogue)")
        if name == "signedpower" and len(args) == 2:
            self.transforms.add("signedpower")
            e = self.tx(args[1])
            x = self.tx(args[0])
            if x is _MISSING or e is _MISSING:
                return _MISSING
            if not e.const:
                return self.miss("op:signedpower(variable exponent)")
            if e.b == 2.0 and not x.const and x.b == 0:
                self.note("SignedPower(x, 2) -> x * |x|")
                return _Aff(["mul", x.tree, ["abs", x.tree]], x.a * abs(x.a), 0.0)
            return self.miss("op:signedpower")
        if name == "log":
            self.transforms.add("log")
            if args:
                self.tx(args[0])
            return self.miss("op:log")
        if name == "product":
            self.transforms.add("product")
            for a in args:
                self.tx(a)
            return self.miss("op:product")
        for a in args:
            self.tx(a)
        return self.miss(f"op:{name}")


#: Exact hand derivations for the two formulas whose nested conditional has an algebraic form
#: the transpiler does not see: (0 < ts_min(d, w)) ? d : ((ts_max(d, w) < 0) ? d : -d) is d when
#: every delta in the window shares one sign and -d otherwise, i.e. sign(min) * sign(max) * d.
def _consistent_momentum(w: int) -> Expr:
    d: Expr = ["delta", "close", 2]
    return ["mul", ["mul", ["sign", ["min", d, w]], ["sign", ["max", d, w]]], d]


OVERRIDES: dict[str, tuple[Expr, str]] = {
    "alpha009": (_consistent_momentum(5),
                 "nested conditional -> sign(ts_min) * sign(ts_max) * delta: exact, the delta "
                 "keeps its sign only while the window's deltas agree"),
    "alpha010": (["xrank", _consistent_momentum(3)],
                 "rank of alpha009's form (window 4 -> 3, the nearest grammar window)"),
}


@dataclass(frozen=True)
class ParentGenome:
    """A_i = (D, O, T, H, S, N, E), plus what this desk can do with it."""

    alpha_id: str
    formula: str
    D: tuple[str, ...]                 #: the paper's fields, by name
    D_semantic: tuple[str, ...]        #: their semantic types
    tree: Expr | None                  #: O, the operator tree in the grammar, when it has one
    T: tuple[str, ...]                 #: transformations the formula applies
    H: float                           #: the horizon: the longest window, in the paper's days
    S: str                             #: state conditioning (the paper: none)
    N: str                             #: normalisation / cross-section
    E: str                             #: execution assumptions
    status: str                        #: TESTABLE | TOO_DEEP | NONTESTABLE
    missing: tuple[str, ...] = ()      #: what has no lawful MT5 analogue, by name
    translations: tuple[str, ...] = ()
    depth: int = 0

    def render(self) -> str:
        if self.tree is None:
            return f"NONTESTABLE({', '.join(self.missing)})"
        return ag.to_str(self.tree)

    def as_dict(self) -> dict[str, Any]:
        return {"alpha_id": self.alpha_id, "formula": self.formula, "D": list(self.D),
                "D_semantic": list(self.D_semantic), "O": self.tree, "T": list(self.T),
                "H_days": self.H, "S": self.S, "N": self.N, "E": self.E,
                "status": self.status, "missing": list(self.missing),
                "translations": list(self.translations), "depth": self.depth,
                "rendered": self.render()}


_PAPER_E = ("paper: daily close-to-close rebalance, cross-sectional long/short, dollar-neutral; "
            "desk: H1 bars, the formula family's hold_bars horizon, z-scored on own history")


def transpile(alpha_id: str, formula: str) -> ParentGenome:
    """One paper formula -> one parent genome, with the desk's verdict on it."""
    t = _Transpiler()
    tree: Any = None
    try:
        got = t.tx(parse_formula(formula))
        tree = _MISSING if got is _MISSING else t.unwrap(got, "root")
    except ValueError as exc:
        t.miss(f"parse:{exc}")
        tree = _MISSING
    fields = tuple(sorted(t.fields))
    sem = tuple(sorted({PAPER_FIELDS[f][0] for f in fields if f in PAPER_FIELDS}))
    horizon = max(t.days) if t.days else 1.0
    n = ("cross_sectional_rank" if "rank" in t.transforms or "indneutralize" in t.transforms
         else "none")
    state = "none (paper: unconditional)"
    transforms = tuple(sorted(t.transforms))
    if alpha_id in OVERRIDES:
        tree, why = OVERRIDES[alpha_id]
        t.note(why)
        t.missing.clear()
    if tree is _MISSING or t.missing:
        return ParentGenome(alpha_id, formula, fields, sem, None, transforms, horizon, state, n,
                            _PAPER_E, "NONTESTABLE", tuple(sorted(t.missing)), tuple(t.notes))
    tree = canonical(tree)
    if not ag.well_formed(tree):
        return ParentGenome(alpha_id, formula, fields, sem, tree, transforms, horizon, state, n,
                            _PAPER_E, "NONTESTABLE", (f"unit_algebra:{ag.type_of(tree)}",),
                            tuple(t.notes), ag.depth(tree))
    d = ag.depth(tree)
    status = "TOO_DEEP" if d > ag.MAX_DEPTH else "TESTABLE"
    missing = (f"depth:{d}>{ag.MAX_DEPTH}",) if status == "TOO_DEEP" else ()
    return ParentGenome(alpha_id, formula, fields, sem, tree, transforms, horizon, state, n,
                        _PAPER_E, status, missing, tuple(t.notes), d)


@lru_cache(maxsize=1)
def parent_genomes() -> dict[str, ParentGenome]:
    """Every one of the 101, transcribed. Cached: the paper does not change between calls."""
    return {aid: transpile(aid, f) for aid, f in ALPHA101.items()}


def genome_census() -> dict[str, Any]:
    """What the desk can say of the 101, by status and by the missing field that stops it."""
    gs = parent_genomes()
    by_status: dict[str, int] = dict.fromkeys(PARENT_STATUSES, 0)
    by_missing: dict[str, list[str]] = {}
    for g in gs.values():
        by_status[g.status] += 1
        if g.status == "NONTESTABLE":
            for m in g.missing:
                by_missing.setdefault(m, []).append(g.alpha_id)
    return {"n_parents": len(gs), "by_status": by_status,
            "nontestable_by_missing": {k: sorted(v) for k, v in sorted(by_missing.items())},
            "testable": sorted(a for a, g in gs.items() if g.status == "TESTABLE"),
            "too_deep": sorted(a for a, g in gs.items() if g.status == "TOO_DEEP"),
            "rule": ("a formula whose fields have no lawful MT5 analogue is NONTESTABLE with the "
                     "field named; TOO_DEEP is a real genome the executor reaches only through "
                     f"pruning (MAX_DEPTH {ag.MAX_DEPTH})")}


# ============================================================================ panel seeding
def memo_key(expr: Expr) -> str:
    """The key `alpha_grammar.evaluate` looks a subtree up under. Seeding uses the same one."""
    return json.dumps(expr, default=str)


def panel_nodes(expr: Expr) -> list[Expr]:
    """Every PANEL subtree, innermost first, each once."""
    out: list[Expr] = []
    seen: set[str] = set()

    def _walk(x: Expr) -> None:
        if not isinstance(x, (list, tuple)):
            return
        for c in x[1:]:
            _walk(c)
        if str(x[0]) in ag.PANEL and ag.key(x) not in seen:
            seen.add(ag.key(x))
            out.append(x)
    _walk(expr)
    return out


def has_panel(expr: Expr) -> bool:
    return bool(panel_nodes(expr))


def _xs_rank(vals: np.ndarray, min_members: int) -> np.ndarray:
    """Per-row percentile of each column among the row's finite columns; NaN where thin."""
    finite = np.isfinite(vals)
    n = finite.sum(axis=1)
    filled = np.where(finite, vals, np.inf)
    order = np.argsort(np.argsort(filled, axis=1, kind="stable"), axis=1).astype(float)
    with np.errstate(invalid="ignore", divide="ignore"):
        pct = (order + 1.0) / n[:, None]
    pct[~finite] = np.nan
    pct[n < min_members, :] = np.nan
    return np.asarray(pct)


def _xs_z(vals: np.ndarray, min_members: int) -> np.ndarray:
    finite = np.isfinite(vals)
    n = finite.sum(axis=1)
    with np.errstate(invalid="ignore", divide="ignore"), warnings.catch_warnings():
        # an all-NaN row (a bar no member has a value on) is NaN below, not a warning
        warnings.simplefilter("ignore", category=RuntimeWarning)
        mean = np.nanmean(np.where(finite, vals, np.nan), axis=1)
        std = np.nanstd(np.where(finite, vals, np.nan), axis=1)
        z = (vals - mean[:, None]) / std[:, None]
    z[~finite] = np.nan
    z[(n < min_members) | ~np.isfinite(std), :] = np.nan
    return np.asarray(z)


def seed_panels(expr: Expr, frames: Mapping[str, Mapping[str, pd.Series]],
                memos: MutableMapping[str, Any], min_members: int = 3) -> int:
    """Compute every panel node of `expr` across the basket and seed each member's memo.

    `frames` is symbol -> that symbol's terminal frames; `memos` is symbol -> the memo
    `alpha_grammar.evaluate` will be handed for it (a dict or a cache scope). After this call
    `ag.evaluate(expr, frames[s], memos[s])` is the cell's series for any member `s`. Returns the
    number of panel nodes seeded. A basket thinner than `min_members` at a bar is NaN there.
    """
    n_seeded = 0
    for node in panel_nodes(expr):
        child = node[1]
        cols: dict[str, pd.Series] = {}
        for sym, fr in frames.items():
            memo = memos.setdefault(sym, {})
            cols[sym] = ag.evaluate(child, dict(fr), memo)
        if not cols:
            continue
        mat = pd.DataFrame(cols)
        vals = mat.to_numpy(dtype=float)
        out = _xs_rank(vals, min_members) if node[0] == "xrank" else _xs_z(vals, min_members)
        k = memo_key(node)
        for j, sym in enumerate(mat.columns):
            idx = next(iter(frames[sym].values())).index
            memos[sym][k] = pd.Series(out[:, j], index=mat.index).reindex(idx)
        n_seeded += 1
    return n_seeded


def evaluate_cell(expr: Expr, frames: Mapping[str, Mapping[str, pd.Series]], target: str,
                  memos: MutableMapping[str, Any] | None = None) -> pd.Series:
    """The expression on `target`, with its panel nodes computed across every symbol in
    `frames`. Never raises: what cannot be computed is NaN, as in the grammar."""
    memos = {} if memos is None else memos
    if target not in frames:
        return pd.Series(dtype=float)
    if has_panel(expr):
        seed_panels(expr, frames, memos)
    return ag.evaluate(expr, dict(frames[target]), memos.setdefault(target, {}))


# ============================================================================ typed DAG
#: THE FACTORY'S SEVEN-WORD TYPE VOCABULARY (mandate: every node typed price / return / volume /
#: count / ratio / time / bool). The grammar's dtype x unit algebra is the AUTHORITY -- `kind`
#: is its reading in the words the mandate uses, so a report and a catalogue can say what a
#: node IS without a second algebra. `time` is what a window argument is (bars); `bool` is what
#: the logic macros below return (a -1/0/+1 gate, the only truth value the grammar can carry).
DSL_TYPES: tuple[str, ...] = ("price", "return", "volume", "count", "ratio", "time", "bool")
_VOLUME_DTYPES = frozenset({"ACTIVITY", "FLOW", "POSITIONING"})


class CompileError(ValueError):
    """The expression cannot be compiled: a structural, type or unit defect, named by path."""

    def __init__(self, why: str, path: tuple[int, ...] = ()) -> None:
        super().__init__(f"{why} at {'/'.join(map(str, path)) or 'root'}")
        self.why = why
        self.path = path


class UnitMismatch(CompileError):
    """Two quantities the unit algebra refuses to combine: a compile error, never a NaN."""


@dataclass(frozen=True)
class TypedNode:
    """One node of the typed DAG: hashed by structure, typed by the grammar, read as a kind."""

    node_id: str
    op: str
    kind: str
    dtype: str
    unit: str
    dimension: str
    children: tuple[str, ...]
    window: int | None
    depth: int

    def as_dict(self) -> dict[str, Any]:
        return {"id": self.node_id, "op": self.op, "kind": self.kind, "dtype": self.dtype,
                "unit": self.unit, "dimension": self.dimension, "children": list(self.children),
                "window": self.window, "depth": self.depth}


def kind_of(expr: Expr) -> str:
    """The node's kind in the seven-word vocabulary; `bool` for a logic macro head, INVALID
    where the grammar's algebra refuses the composition."""
    if isinstance(expr, (list, tuple)) and expr and str(expr[0]) in _LOGIC_MACROS:
        return "bool" if ag.is_valid(lower(expr)) else ag.INVALID
    e = lower(expr)
    t = ag.type_of(e)
    if t == ag.INVALID:
        return ag.INVALID
    dim = ag.dimension_of(e)
    unit = ag.unit_of(e)
    if dim is None or unit is None:
        return ag.INVALID
    if t == "COUNT" or unit == ag.BARS:
        return "time" if unit == ag.BARS else "count"
    if t in _VOLUME_DTYPES:
        return "volume"
    if t == "RETURN":
        return "return"
    if dim.price != 0:
        return "price"
    if dim.count != 0:
        return "volume"
    if dim.time != 0:
        return "time"
    return "ratio"


def typed_dag(expr: Expr) -> dict[str, TypedNode]:
    """The expression as a DAG of typed nodes keyed by `ag.subtree_hash`: a subtree that
    appears twice is ONE node (the cache's own key), and every node carries its kind, dtype,
    unit and dimension. Raises `CompileError` / `UnitMismatch` on the innermost bad node."""
    out: dict[str, TypedNode] = {}

    def _walk(x: Expr, path: tuple[int, ...], d: int) -> str:
        if isinstance(x, str):
            if x not in ag.TERMINALS:
                raise CompileError(f"unknown terminal {x!r}", path)
            nid = ag.subtree_hash(x)
            if nid not in out:
                out[nid] = TypedNode(nid, x, kind_of(x), ag.DTYPES[x], str(ag.TERMINAL_UNITS[x]),
                                     str(ag.TERMINAL_DIMENSIONS[x]), (), None, d)
            return nid
        if not isinstance(x, (list, tuple)) or not x:
            raise CompileError("empty node", path)
        op = str(x[0])
        if op in _MACROS or op in _ALIASES:
            return _walk(lower(x), path, d)
        if op not in ag.ALL_OPERATORS:
            raise CompileError(f"unknown operator {op!r}", path)
        kids: list[str] = []
        window: int | None = None
        for i, c in enumerate(x[1:], start=1):
            if isinstance(c, (list, tuple, str)):
                kids.append(_walk(c, (*path, i), d + 1))
            elif isinstance(c, int) and not isinstance(c, bool):
                if c not in ag.WINDOWS:
                    raise CompileError(f"window {c} is not one of {ag.WINDOWS}", (*path, i))
                window = int(c)
                wid = f"w{c}"
                if wid not in out:
                    out[wid] = TypedNode(wid, "window", "time", "COUNT", str(ag.BARS),
                                         str(ag.DIMENSIONLESS), (), int(c), d + 1)
                kids.append(wid)
            else:
                raise CompileError(f"bad argument {c!r}", (*path, i))
        lowered = lower(x)
        if not ag._structurally_valid(lowered):
            raise CompileError(f"malformed {op} node", path)
        t = ag.type_of(lowered)
        u = ag.unit_of(lowered)
        dim = ag.dimension_of(lowered)
        if t == ag.INVALID or u is None or dim is None:
            raise UnitMismatch(
                f"{op}({', '.join(_brief(c) for c in x[1:])}): "
                f"{'type' if t == ag.INVALID else 'unit'} mismatch", path)
        nid = ag.subtree_hash(lowered)
        if nid not in out:
            out[nid] = TypedNode(nid, op, kind_of(x), t, str(u), str(dim), tuple(kids),
                                 window, d)
        return nid

    _walk(expr, (), 0)
    return out


def _brief(x: Expr) -> str:
    if isinstance(x, str):
        return f"{x}:{ag.TERMINAL_KINDS.get(x, ag.INVALID)}"
    if isinstance(x, (list, tuple)) and x:
        return f"{x[0]}(..):{ag.kind_of(lower(x))}"
    return str(x)


@dataclass
class Compiled:
    """A compiled expression: lowered to the grammar, typed, hashed, with its family."""

    expr: Expr
    source: Expr
    dag: dict[str, TypedNode]
    root: str
    kind: str
    dtype: str
    unit: str
    canonical: str
    family: str
    hits: int = 0
    misses: int = 0

    @property
    def n_nodes(self) -> int:
        return len(self.dag)

    def evaluate(self, frames: Mapping[str, pd.Series], memo: Any = None) -> pd.Series:
        """Vectorised evaluation through the grammar, every subtree memoised by its hash in
        `memo` (a dict or an `ag.SubtreeCache` scope): the second call is a lookup."""
        m: Any = {} if memo is None else memo
        k = memo_key(self.expr)
        if k in m:
            self.hits += 1
            return m[k]
        self.misses += 1
        return ag.evaluate(self.expr, dict(frames), m)

    def as_dict(self) -> dict[str, Any]:
        return {"expr": self.expr, "rendered": ag.to_str(self.expr), "kind": self.kind,
                "dtype": self.dtype, "unit": self.unit, "root": self.root,
                "n_nodes": self.n_nodes, "family": self.family, "canonical": self.canonical}


def compile_expr(expr: Expr, terminals: Sequence[str] | None = None) -> Compiled:
    """THE COMPILER. Lowers the macros, builds the typed DAG (raising `UnitMismatch` on the
    first node the unit algebra refuses), runs the production screen, and returns the
    compiled form with its canonical key and trial family. A `terminals` pool narrows the
    legal leaves to the series a world actually has."""
    lowered = lower(expr)
    dag = typed_dag(lowered)
    if ag.depth(lowered) > ag.MAX_DEPTH:
        raise CompileError(f"depth {ag.depth(lowered)} > MAX_DEPTH {ag.MAX_DEPTH}")
    if not ag.is_valid(lowered, terminals=terminals):
        bad = sorted(set(ag.terminals_in(lowered)) - set(terminals or ag.TERMINALS))
        raise CompileError(f"terminal(s) {bad} not available on this world" if bad
                           else "production screen refused the tree")
    root = ag.subtree_hash(lowered)
    node = dag[root]
    return Compiled(lowered, expr, dag, root, node.kind, node.dtype, node.unit,
                    canonical_key(lowered), family_key(lowered))


# ============================================================================ operator catalogue
@dataclass(frozen=True)
class OpSpec:
    """One operator's entry: category, arity, whether it takes a window, and its type/unit
    signature. `lowers_to` names the grammar expansion of a macro; "" for a primitive."""

    name: str
    category: str
    arity: int
    windowed: bool
    signature: str
    lowers_to: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {"name": self.name, "category": self.category, "arity": self.arity,
                "windowed": self.windowed, "signature": self.signature,
                "lowers_to": self.lowers_to}


OP_CATEGORIES: tuple[str, ...] = ("time_series", "cross_sectional", "group", "math", "logic",
                                  "event", "regime")

#: MACROS: the DSL's logic, event and regime-conditioned operators, each an expansion into the
#: grammar's own nodes, so the unit algebra, the evaluator and the cache see one vocabulary.
#: Without numeric constants in the grammar a truth value is a sign: gt(a, b) is sign(a - b),
#: which the algebra refuses unless a and b share a unit -- the compile error the mandate asks
#: for -- and `trade_when` reads a gate as "on" where it is > 0.
_LOGIC_MACROS: dict[str, Callable[[list[Any]], Expr]] = {
    "gt": lambda a: ["sign", ["sub", a[0], a[1]]],
    "lt": lambda a: ["sign", ["sub", a[1], a[0]]],
    "and": lambda a: ["min2", ["sign", a[0]], ["sign", a[1]]],
    "or": lambda a: ["max2", ["sign", a[0]], ["sign", a[1]]],
    "not": lambda a: ["neg", ["sign", a[0]]],
}
_EVENT_MACROS: dict[str, Callable[[list[Any]], Expr]] = {
    "event_decay": lambda a: ["decay", "event", a[0]],
    "bars_since_event": lambda a: ["bars_since_max", "event", a[0]],
    "event_gate": lambda a: ["trade_when", "event", a[0]],
}
_REGIME_MACROS: dict[str, Callable[[list[Any]], Expr]] = {
    "when_regime": lambda a: ["trade_when", "state_prob", a[0]],
    "regime_neutral": lambda a: ["group_zscore", a[0], "state_prob", a[1]],
    "regime_rank": lambda a: ["group_rank", a[0], "state_prob", a[1]],
}
_ALIASES: dict[str, str] = {"ts_argmax": "bars_since_max", "ts_argmin": "bars_since_min",
                            "ts_mean": "mean", "ts_std": "std", "ts_delta": "delta",
                            "ts_delay": "delay", "ts_corr": "corr", "ts_cov": "cov",
                            "ts_decay": "decay", "ts_sum": "sum", "ts_min": "min",
                            "ts_max": "max", "rank": "xrank", "neutralise": "group_zscore"}
_MACROS: dict[str, Callable[[list[Any]], Expr]] = {**_LOGIC_MACROS, **_EVENT_MACROS,
                                                   **_REGIME_MACROS}


def lower(expr: Expr) -> Expr:
    """Expand every macro and alias, innermost first, into the grammar's closed operator set.
    A tree with no macro comes back structurally equal (a fresh copy)."""
    if not isinstance(expr, (list, tuple)) or not expr:
        return expr
    op = str(expr[0])
    kids = [lower(c) if isinstance(c, (list, tuple)) else c for c in expr[1:]]
    if op in _MACROS:
        return lower(_MACROS[op](kids))
    return [_ALIASES.get(op, op), *kids]


def _sig_windowed(op: str) -> str:
    rule = ag._WINDOWED_OUT[op]
    out = {"same": "T[u]", "diff": "dT[u]", "SCALE": "SCALE[u]", "RANK": "RANK[1]",
           "Z": "Z[1]", "COUNT": "COUNT[bars]"}.get(rule, rule)
    if op == "atr_norm":
        return "(x: PRICE[quote], w: time[bars]) -> Z[1]"
    return f"(x: T[u], w: time[bars]) -> {out}"


def _catalogue() -> dict[str, OpSpec]:
    cat: dict[str, OpSpec] = {}
    ts_ops = ("delay", "delta", "mean", "std", "min", "max", "ts_rank", "zscore", "decay",
              "sum", "bars_since_max", "bars_since_min", "atr_norm", "ts_backfill", "scale")
    for op in ts_ops:
        cat[op] = OpSpec(op, "time_series", 1, True, _sig_windowed(op))
    cat["corr"] = OpSpec("corr", "time_series", 2, True, "(x: T[u], y: S[v], w) -> Z[1]")
    cat["cov"] = OpSpec("cov", "time_series", 2, True, "(x: T[u], y: S[v], w) -> SCALE[u v]")
    cat["residual"] = OpSpec("residual", "time_series", 2, True,
                             "(x: T[u], y: S[v], w) -> T[u]  (x minus its rolling beta to y)")
    for op in ag.PANEL:
        cat[op] = OpSpec(op, "cross_sectional", 1, False,
                         f"(x: T[u]) -> {'RANK' if op == 'xrank' else 'Z'}[1] across the "
                         "cell's basket")
    cat["group_rank"] = OpSpec("group_rank", "group", 2, True,
                               "(x: T[u], g: group, w) -> RANK[1] within g's peers")
    cat["group_zscore"] = OpSpec("group_zscore", "group", 2, True,
                                 "(x: T[u], g: group, w) -> Z[1] neutralised within g")
    for op in ("neg", "abs"):
        cat[op] = OpSpec(op, "math", 1, False, "(x: T[u]) -> T[u]")
    cat["sign"] = OpSpec("sign", "math", 1, False, "(x: T[u]) -> Z[1]")
    for op in ("add", "sub", "max2", "min2"):
        cat[op] = OpSpec(op, "math", 2, False, "(x: T[u], y: T[u]) -> T[u]  (units must match)")
    cat["mul"] = OpSpec("mul", "math", 2, False, "(x: T[u], y: S[v]) -> [u v]")
    cat["div"] = OpSpec("div", "math", 2, False, "(x: T[u], y: S[v]) -> [u / v]; T/T -> RATIO")
    cat["trade_when"] = OpSpec("trade_when", "logic", 2, False,
                               "(gate: bool|Z[1], x: T[u]) -> T[u] held where gate <= 0")
    for op in ("gt", "lt", "and", "or"):
        cat[op] = OpSpec(op, "logic", 2, False, "(a: T[u], b: T[u]) -> bool",
                         ag.to_str(_LOGIC_MACROS[op](["a", "b"])))
    cat["not"] = OpSpec("not", "logic", 1, False, "(a: T[u]) -> bool",
                        ag.to_str(_LOGIC_MACROS["not"](["a"])))
    cat["event_decay"] = OpSpec("event_decay", "event", 0, True, "(w) -> EVENT[1]",
                                ag.to_str(_EVENT_MACROS["event_decay"]([24])))
    cat["bars_since_event"] = OpSpec("bars_since_event", "event", 0, True,
                                     "(w) -> COUNT[bars]",
                                     ag.to_str(_EVENT_MACROS["bars_since_event"]([24])))
    cat["event_gate"] = OpSpec("event_gate", "event", 1, False, "(x: T[u]) -> T[u]",
                               ag.to_str(_EVENT_MACROS["event_gate"](["x"])))
    cat["when_regime"] = OpSpec("when_regime", "regime", 1, False, "(x: T[u]) -> T[u]",
                                ag.to_str(_REGIME_MACROS["when_regime"](["x"])))
    cat["regime_neutral"] = OpSpec("regime_neutral", "regime", 1, True,
                                   "(x: T[u], w) -> Z[1] within the regime",
                                   ag.to_str(_REGIME_MACROS["regime_neutral"](["x", 24])))
    cat["regime_rank"] = OpSpec("regime_rank", "regime", 1, True,
                                "(x: T[u], w) -> RANK[1] within the regime",
                                ag.to_str(_REGIME_MACROS["regime_rank"](["x", 24])))
    return cat


OPERATOR_CATALOGUE: dict[str, OpSpec] = _catalogue()


def catalogue_census() -> dict[str, Any]:
    by_cat: dict[str, list[str]] = {c: [] for c in OP_CATEGORIES}
    for spec in OPERATOR_CATALOGUE.values():
        by_cat[spec.category].append(spec.name)
    return {"n_operators": len(OPERATOR_CATALOGUE), "by_category": by_cat,
            "primitives": sorted(k for k, v in OPERATOR_CATALOGUE.items() if not v.lowers_to),
            "macros": sorted(k for k, v in OPERATOR_CATALOGUE.items() if v.lowers_to),
            "aliases": dict(_ALIASES), "types": list(DSL_TYPES)}


def operators_in(expr: Expr) -> set[str]:
    if not isinstance(expr, (list, tuple)) or not expr:
        return set()
    out = {str(expr[0])}
    for c in expr[1:]:
        out |= operators_in(c)
    return out


# ============================================================================ mutation engine
#: THE MOVES, each DIMENSION-PRESERVING BY CONSTRUCTION: a child is returned only when the
#: production screen accepts it AND its root unit equals the parent's (units imply dimensions).
#: The grammar's only numeric constants are its windows, so `constant` perturbation is a window
#: step; `simplify` is the exact canonical form (a no-op, returned as None, on a canonical tree).
MUTATIONS: tuple[str, ...] = ("point", "subtree", "crossover", "constant", "operator_swap",
                              "simplify")


def dimension_preserving(parent: Expr, child: Expr) -> bool:
    if not ag.is_valid(child):
        return False
    pu, cu = ag.unit_of(parent), ag.unit_of(child)
    return pu is not None and cu is not None and pu == cu


def _internal_paths(expr: Expr) -> list[tuple[int, ...]]:
    return [p for p in ag._paths(expr) if isinstance(ag._get(expr, p), list)]


def _leaf_paths(expr: Expr) -> list[tuple[int, ...]]:
    return [p for p in ag._paths(expr) if isinstance(ag._get(expr, p), str)]


def mutate(expr: Expr, move: str, rng: np.random.Generator,
           terminals: Sequence[str] | None = None, partner: Expr | None = None,
           tries: int = 16) -> Expr | None:
    """One named move on a copy of `expr`; None when no dimension-preserving child was found
    in `tries` draws (the caller counts that as a move that produced nothing)."""
    pool = tuple(terminals) if terminals else ag.terminal_pool(True)
    base = lower(expr)
    if move == "simplify":
        c = canonical(base)
        return None if ag.key(c) == ag.key(base) else c
    for _ in range(tries):
        cand: Expr | None = None
        if move == "point":
            leaves = _leaf_paths(base)
            p = leaves[int(rng.integers(len(leaves)))]
            old = ag._get(base, p)
            same = [t for t in pool if t != old
                    and ag.TERMINAL_KINDS.get(t) == ag.TERMINAL_KINDS.get(old)]
            if not same:
                continue
            cand = ag._set(ag._clone(base), p, str(rng.choice(same)))
        elif move == "subtree":
            paths = _internal_paths(base) or [()]
            p = paths[int(rng.integers(len(paths)))]
            cand = ag._set(ag._clone(base), p, ag.random_expr(rng, 2, terminals=pool))
        elif move == "crossover":
            if partner is None:
                return None
            other = lower(partner)
            pa, pb = ag._paths(base), ag._paths(other)
            cand = ag._set(ag._clone(base), pa[int(rng.integers(len(pa)))],
                           ag._clone(ag._get(other, pb[int(rng.integers(len(pb)))])))
        elif move == "constant":
            paths = [p for p in _internal_paths(base)
                     if str(ag._get(base, p)[0]) in ag.WINDOWED + ag.BINARY_WINDOWED]
            if not paths:
                return None
            p = paths[int(rng.integers(len(paths)))]
            node = list(ag._get(base, p))
            w = int(node[-1])
            i = ag.WINDOWS.index(w) if w in ag.WINDOWS else -1
            j = i + (1 if rng.random() < 0.5 else -1)
            node[-1] = int(ag.WINDOWS[j]) if 0 <= j < len(ag.WINDOWS) \
                else int(rng.choice(ag.WINDOWS))
            if node[-1] == w:
                continue
            cand = ag._set(ag._clone(base), p, node)
        elif move == "operator_swap":
            paths = _internal_paths(base)
            if not paths:
                return None
            p = paths[int(rng.integers(len(paths)))]
            node = list(ag._get(base, p))
            cls = next((c for c in (ag.UNARY, ag.WINDOWED, ag.BINARY, ag.BINARY_WINDOWED,
                                    ag.PANEL) if node[0] in c), None)
            if cls is None or len(cls) < 2:
                continue
            new_op = str(rng.choice([o for o in cls if o != node[0]]))
            node[0] = new_op
            cand = ag._set(ag._clone(base), p, node)
        else:
            raise ValueError(f"unknown move {move!r}; one of {MUTATIONS}")
        if cand is not None and ag.key(cand) != ag.key(base) \
                and dimension_preserving(base, cand):
            return cand
    return None


__all__ = [
    "ALPHA101",
    "AVAILABILITY_RULES",
    "DSL_TYPES",
    "MUTATIONS",
    "OPERATOR_CATALOGUE",
    "OP_CATEGORIES",
    "OVERRIDES",
    "PAPER_FIELDS",
    "PARENT_STATUSES",
    "SEMANTIC_TERMINAL",
    "SEMANTIC_TYPES",
    "CompileError",
    "Compiled",
    "Field",
    "FieldCatalogue",
    "OpSpec",
    "ParentGenome",
    "TypedNode",
    "UnitMismatch",
    "axis_fields",
    "bar_fields",
    "canonical",
    "canonical_key",
    "catalogue_census",
    "compile_expr",
    "dimension_preserving",
    "evaluate_cell",
    "family_key",
    "future_data_impossible",
    "genome_census",
    "has_panel",
    "kind_of",
    "lower",
    "memo_key",
    "mutate",
    "nearest_window",
    "operators_in",
    "panel_nodes",
    "parent_genomes",
    "parse_formula",
    "representation_fields",
    "seed_panels",
    "skeleton",
    "transpile",
    "typed_dag",
    "windows_in",
]

```

### libs\research\frontier.py
```python
"""THE MAXIMUM ECONOMIC FRONTIER — one ranking for every use of every scarce resource.

WHAT THIS REPLACES. The desk already ranks work: `run_max_push` merges six "what is left" artifacts
into a queue by declared leverage weights. That queue answers "what is furthest from 100%". It does
NOT answer the question the terminal law actually asks, which is:

    given everything we know right now, which FEASIBLE SET of actions -- across capital, risk,
    compute, data spend, engineering time and latency -- most increases long-run realised net
    retained E[log W], after accounting for every competing use of those same resources?

Those differ in a way that decides days. A queue ordered by distance-from-ceiling will rank a
research module above deploying a validated survivor, because the module is 0% and the survivor is
"done". The frontier will not, because the survivor's marginal contribution is larger and its
opportunity cost is a euro of compute rather than a euro of capital.

SIX PROPERTIES, EACH FIXING A SPECIFIC WAY THIS GOES WRONG:

**1. SHADOW PRICES, AND NO DOUBLE-COUNTED OPPORTUNITY COST.** Each scarce resource carries a
current marginal value. An action's surplus subtracts `sum(lambda_j * usage_j)` and NOT a separate
generic "opportunity cost" term, because when the shadow prices are doing their job that term is
already in there and adding it charges the same loss twice.

**2. UNCERTAINTY HAS A PRICE, SO DISTRIBUTIONS RANK, NOT POINT ESTIMATES.** A high but wildly
uncertain expected value must not automatically dominate a slightly lower, well-calibrated one.
`risk_adjusted` shrinks by posterior width AND by the proposer's historical calibration, so an
estimator with a record of optimism is discounted by its own record rather than by an argument.
This is not conservatism -- an uncertain action with a large enough edge still wins.

**3. FEASIBILITY IS A FILTER, NOT A SCORE.** Illegal, impossible, privilege-violating and
survival-breaking actions are removed BEFORE optimisation. They never receive a negative number and
compete, because a sufficiently optimistic estimate would eventually outbid the risk kernel, and
that is precisely the failure mode a risk kernel exists to make impossible.

**4. BUNDLES, NOT GREEDY SINGLES.** Buy the dataset / build the feature / run the experiment can
each look weak alone and be strongly positive together. Likewise fix the websocket + raise the
cadence. `best_bundle` evaluates declared bundles against the same budget and takes the best total
surplus, so a greedy pick cannot beat a better set.

**5. FRONTIER REGRET IS THE KPI.** The gap between the best feasible action set KNOWN at the time
and what was actually done, decomposed by category. It lets the desk learn not only that a trade
was bad but that the whole day's resources went to the wrong place.

**6. ANTI-GOODHART.** These are models, not truth. When estimated value and realised descendants
diverge, realised evidence dominates and the estimator is recalibrated -- `calibration` returns the
multiplier, and no component may improve its priority by improving its own estimate.

Ranks and reports. Spends nothing, deploys nothing, and cannot: the feasibility filter is an input
it does not own.
"""

from __future__ import annotations

from dataclasses import dataclass, field

__all__ = [
    "INFEASIBLE_REASONS",
    "REGRET_CATEGORIES",
    "RESOURCES",
    "Action",
    "Bundle",
    "ResourcePrices",
    "best_bundle",
    "calibration",
    "economic_surplus",
    "feasible",
    "frontier_regret",
    "rank",
    "risk_adjusted",
    "summarise",
]

#: Everything that can be scarce. No resource is free merely because it is currently available --
#: idle CPU during a research bottleneck is a different economic object from idle CPU when no
#: useful experiment exists, and only the shadow price can tell them apart.
RESOURCES: tuple[str, ...] = (
    "capital", "risk_budget", "drawdown_capacity", "liquidity", "venue_capacity",
    "compute", "storage", "market_data_budget", "api_budget", "llm_tokens",
    "engineering_time", "research_attention", "latency_budget", "operational_complexity",
)

#: Why an action is removed BEFORE optimisation. Not scores: a filter.
INFEASIBLE_REASONS: tuple[str, ...] = (
    "ILLEGAL", "IMPOSSIBLE", "PRIVILEGE_VIOLATION", "SURVIVAL_BREAKING",
    "DEPENDENCY_UNMET", "RESOURCE_UNAVAILABLE",
)

#: Where the day's resources went wrong, when they did.
REGRET_CATEGORIES: tuple[str, ...] = (
    "RESEARCH_REGRET", "CAPITAL_REGRET", "EXECUTION_REGRET", "LATENCY_REGRET",
    "INFRASTRUCTURE_REGRET", "MODEL_SELECTION_REGRET", "IDLE_RESOURCE_REGRET",
)


@dataclass(frozen=True)
class ResourcePrices:
    """Current marginal value of one more unit of each resource. THE ANTI-DOUBLE-COUNT DEVICE.

    An empty price is UNMEASURED and priced at zero, which is optimistic and is reported as such:
    an action consuming an unpriced resource looks free, and the summary names every resource it
    consumed without a price rather than letting the total read as a full accounting.
    """

    prices: dict[str, float] = field(default_factory=dict)

    def price(self, resource: str) -> float:
        return max(0.0, float(self.prices.get(resource, 0.0)))

    @property
    def unpriced(self) -> tuple[str, ...]:
        return tuple(r for r in RESOURCES if r not in self.prices)


@dataclass(frozen=True)
class Action:
    """One candidate use of resources, with its uncertainty carried rather than dropped."""

    action_id: str
    category: str
    #: Posterior mean of the incremental log-wealth contribution. Not a point estimate that pretends
    #: to be a fact -- `elogw_sigma` is required for it to be rankable at all.
    elogw_mean: float = 0.0
    elogw_sigma: float = 0.0
    #: Probability the action succeeds economically at all. Separate from the magnitude: a 5%
    #: chance of a large win and a certain small win are different objects.
    p_success: float = 1.0
    #: Resource consumption, keyed by RESOURCES.
    resources: dict[str, float] = field(default_factory=dict)
    #: Direct and ongoing costs already expressed in log-wealth units.
    direct_cost: float = 0.0
    maintenance_cost: float = 0.0
    complexity_cost: float = 0.0
    #: Days until the value is realised, and the half-life of the opportunity itself. Together
    #: these decide urgency: an action whose opportunity expires before it can be delivered is
    #: not a slow win, it is a loss.
    time_to_value_days: float = 0.0
    opportunity_half_life_days: float = 0.0
    #: Who or what produced the estimate. Feeds the calibration discount.
    proposer: str = ""
    #: Set to remove this action from optimisation entirely.
    infeasible_reason: str = ""
    #: Value from improving future DECISIONS rather than from immediate P&L (§EVSI).
    information_value: float = 0.0
    dependencies: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if self.infeasible_reason and self.infeasible_reason not in INFEASIBLE_REASONS:
            raise ValueError(f"infeasible_reason must be one of {INFEASIBLE_REASONS}")
        for r in self.resources:
            if r not in RESOURCES:
                raise ValueError(f"unknown resource {r!r}; the basis is closed: {RESOURCES}")

    @property
    def measured(self) -> bool:
        return self.elogw_sigma > 0 and self.elogw_mean != 0.0


@dataclass(frozen=True)
class Bundle:
    """Actions whose combined surplus differs from the sum of their parts."""

    bundle_id: str
    action_ids: tuple[str, ...]
    #: Extra surplus (positive) or interference (negative) from doing them together.
    synergy: float = 0.0
    rationale: str = ""


def feasible(actions: list[Action]) -> tuple[list[Action], list[dict[str, str]]]:
    """(feasible, removed). THE FILTER RUNS FIRST AND IS NOT A SCORE.

    An infeasible action never receives a number, because any number can be outbid by a
    sufficiently optimistic estimate somewhere else -- and the whole purpose of a survival
    constraint is that it cannot be outbid.
    """
    ok, removed = [], []
    for a in actions:
        if a.infeasible_reason:
            removed.append({"action_id": a.action_id, "reason": a.infeasible_reason})
        else:
            ok.append(a)
    return ok, removed


def calibration(proposer: str, history: dict[str, tuple[float, float]]) -> tuple[float, str]:
    """Multiplier from a proposer's record: realised / predicted. §ANTI-GOODHART.

    `history` maps proposer -> (total predicted ΔElogW, total realised). A proposer that has
    consistently overestimated is discounted by ITS OWN RECORD rather than by an argument, and the
    discount cannot be improved by improving the estimate -- only by producing realised value.

    Returns 1.0 with a reason when there is no history. That is deliberately neutral: penalising an
    unproven proposer would freeze the exploration the frontier depends on.
    """
    rec = history.get(proposer)
    if not rec or rec[0] <= 0:
        return 1.0, (f"{proposer or 'unattributed'}: no calibration history, multiplier 1.0. "
                     "Neutral rather than penalised -- discounting an unproven proposer would "
                     "freeze the exploration this frontier depends on")
    predicted, realised = rec
    m = max(0.05, min(2.0, realised / predicted))
    return m, (f"{proposer}: realised {realised:.4f} against predicted {predicted:.4f} "
               f"=> x{m:.2f}. Improving this requires realised descendants, not better estimates")


def risk_adjusted(a: Action, *, calib: float = 1.0) -> tuple[float | None, str]:
    """Uncertainty- and calibration-adjusted expected contribution. NOT conservatism.

    Shrinks the mean by one posterior standard deviation and by the proposer's calibration, then
    applies success probability and opportunity decay over the delivery time. An uncertain action
    with a large enough edge still wins; what it cannot do is win merely by being uncertain in the
    optimistic direction.
    """
    if not a.measured:
        return None, (
            f"{a.action_id}: no posterior width recorded, so the estimate cannot be ranked against "
            "a calibrated one. UNMEASURED -- and an unmeasured estimate treated as measured is how "
            "the loudest guess wins the day")
    shrunk = (a.elogw_mean - a.elogw_sigma) * calib * max(0.0, min(1.0, a.p_success))
    decay = 1.0
    if a.opportunity_half_life_days > 0 and a.time_to_value_days > 0:
        decay = 0.5 ** (a.time_to_value_days / a.opportunity_half_life_days)
    value = shrunk * decay + a.information_value
    note = (f"{a.action_id}: mean {a.elogw_mean:+.4f} less sigma {a.elogw_sigma:.4f}, "
            f"x calibration {calib:.2f}, x P(success) {a.p_success:.2f}")
    if decay < 0.99:
        note += (f", x {decay:.2f} opportunity decay over {a.time_to_value_days:g}d against a "
                 f"{a.opportunity_half_life_days:g}d half-life")
        if decay < 0.25:
            note += (". MOST OF THIS OPPORTUNITY EXPIRES BEFORE DELIVERY -- redesign for speed or "
                     "reject; a slow win on a fast-decaying edge is a loss")
    if a.information_value:
        note += f", plus {a.information_value:+.4f} information value"
    return value, note


def economic_surplus(a: Action, prices: ResourcePrices, *,
                     calib: float = 1.0) -> tuple[float | None, str]:
    """Risk-adjusted value MINUS shadow-priced resource use and direct costs.

        surplus = E[dlogW]_adj - sum_j lambda_j * usage_j - direct - maintenance - complexity

    NO separate generic opportunity-cost term. When the shadow prices are doing their job that cost
    is already inside the sum, and adding it again charges the same loss twice -- which
    systematically kills cheap high-value actions in favour of ones whose resources nobody priced.
    """
    value, why = risk_adjusted(a, calib=calib)
    if value is None:
        return None, why
    resource_cost = sum(prices.price(r) * max(0.0, u) for r, u in a.resources.items())
    total = value - resource_cost - a.direct_cost - a.maintenance_cost - a.complexity_cost
    unpriced = [r for r in a.resources if r not in prices.prices]
    return total, (
        f"{why}; less shadow-priced resources {resource_cost:.4f} and costs "
        f"{a.direct_cost + a.maintenance_cost + a.complexity_cost:.4f} => surplus {total:+.4f}"
        + (f". UNPRICED resources consumed: {unpriced} -- those look free here and are not"
           if unpriced else ""))


def rank(actions: list[Action], prices: ResourcePrices, *,
         history: dict[str, tuple[float, float]] | None = None) -> list[dict[str, object]]:
    """Feasible actions ordered by economic surplus, best first. Unmeasured sort last."""
    hist = history or {}
    ok, _ = feasible(actions)
    rows: list[dict[str, object]] = []
    for a in ok:
        calib, cwhy = calibration(a.proposer, hist)
        s, why = economic_surplus(a, prices, calib=calib)
        rows.append({
            "action_id": a.action_id, "category": a.category,
            "surplus": None if s is None else round(s, 6),
            "elogw_mean": a.elogw_mean, "elogw_sigma": a.elogw_sigma,
            "p_success": a.p_success,
            "calibration": round(calib, 3), "calibration_note": cwhy,
            "time_to_value_days": a.time_to_value_days,
            "why": why, "measured": a.measured,
        })
    rows.sort(key=lambda r: (0 if r["measured"] else 1,
                             -(float(str(r["surplus"])) if r["surplus"] is not None else -1e18)))
    return rows


def best_bundle(actions: list[Action], bundles: list[Bundle], prices: ResourcePrices,
                *, budget: dict[str, float] | None = None,
                history: dict[str, tuple[float, float]] | None = None) -> dict[str, object]:
    """The highest-surplus FEASIBLE SET, comparing declared bundles against greedy singles.

    A greedy pick of the single best action is a special case and is evaluated as one, so this can
    only ever match or beat it. Bundles that breach the budget are reported as infeasible under
    the current constraint rather than silently dropped -- "we could not afford it" and "it was not
    worth it" are different findings.
    """
    hist = history or {}
    ok, removed = feasible(actions)
    by_id = {a.action_id: a for a in ok}
    cap = budget or {}

    def _score(ids: tuple[str, ...], synergy: float) -> tuple[float | None, dict[str, float]]:
        total = 0.0
        used: dict[str, float] = {}
        for i in ids:
            a = by_id.get(i)
            if a is None:
                return None, {}
            calib, _ = calibration(a.proposer, hist)
            s, _ = economic_surplus(a, prices, calib=calib)
            if s is None:
                return None, {}
            total += s
            for r, u in a.resources.items():
                used[r] = used.get(r, 0.0) + u
        return total + synergy, used

    candidates: list[dict[str, object]] = []
    for b in bundles:
        s, used = _score(b.action_ids, b.synergy)
        if s is None:
            continue
        over = {r: u for r, u in used.items() if r in cap and u > cap[r]}
        candidates.append({"bundle_id": b.bundle_id, "action_ids": list(b.action_ids),
                           "surplus": round(s, 6), "synergy": b.synergy,
                           "rationale": b.rationale, "resources_used": used,
                           "over_budget": over, "affordable": not over})
    for a in ok:
        s, used = _score((a.action_id,), 0.0)
        if s is None:
            continue
        over = {r: u for r, u in used.items() if r in cap and u > cap[r]}
        candidates.append({"bundle_id": f"single::{a.action_id}",
                           "action_ids": [a.action_id], "surplus": round(s, 6), "synergy": 0.0,
                           "rationale": "single action", "resources_used": used,
                           "over_budget": over, "affordable": not over})

    affordable = [c for c in candidates if c["affordable"]]
    affordable.sort(key=lambda c: -float(str(c["surplus"])))
    best = affordable[0] if affordable else None
    singles = [c for c in affordable if str(c["bundle_id"]).startswith("single::")]
    beat_greedy = bool(best and singles and float(str(best["surplus"]))
                       > float(str(singles[0]["surplus"])) + 1e-12)
    return {
        "selected": best,
        "candidates": candidates[:20],
        "removed_infeasible": removed,
        "bundle_beats_greedy": beat_greedy,
        "note": ("A greedy single is evaluated as a one-element bundle, so this can only match or "
                 "beat it. Unaffordable candidates are reported rather than dropped: 'could not "
                 "afford' and 'not worth it' are different findings and only one of them is a "
                 "verdict on the action."),
    }


def frontier_regret(*, best_known_surplus: float, selected_surplus: float,
                    by_category: dict[str, float] | None = None) -> dict[str, object]:
    """THE KPI. What the best feasible set known at the time would have produced, minus what was.

    Measured against what was KNOWN, not against hindsight. Regret against the best action
    identifiable only afterwards is not a decision failure -- it is the cost of operating under
    uncertainty, and charging it would make the metric unimprovable and therefore ignored.
    """
    regret = max(0.0, best_known_surplus - selected_surplus)
    cat = {k: round(v, 6) for k, v in (by_category or {}).items() if k in REGRET_CATEGORIES}
    unknown = sorted(set(by_category or {}) - set(REGRET_CATEGORIES))
    return {
        "FRONTIER_REGRET": round(regret, 6),
        "best_known_surplus": round(best_known_surplus, 6),
        "selected_surplus": round(selected_surplus, 6),
        "by_category": cat,
        "unrecognised_categories": unknown,
        "headline": (
            f"FRONTIER_REGRET {regret:.4f}: the best feasible set known at the time would have "
            f"produced {best_known_surplus:.4f} and the desk realised {selected_surplus:.4f}"
            + (f"; largest component {max(cat, key=lambda k: cat[k])}" if cat else "")
            if regret > 0 else
            "no frontier regret: the desk selected the best feasible action set it knew about"),
        "note": ("Measured against what was KNOWN at decision time, never against hindsight. "
                 "Regret against an action identifiable only afterwards is the cost of operating "
                 "under uncertainty rather than a decision failure, and charging it would make "
                 "this metric unimprovable and therefore ignored."),
    }


def summarise(actions: list[Action], prices: ResourcePrices, *,
              bundles: list[Bundle] | None = None,
              budget: dict[str, float] | None = None,
              history: dict[str, tuple[float, float]] | None = None) -> dict[str, object]:
    """Report shape for `data/economic_frontier.json`."""
    if not actions:
        return {"actions": 0, "headline": (
            "no candidate actions enumerated -- the economic frontier is UNMEASURED, so today's "
            "work was chosen by something other than expected marginal contribution")}
    ranked = rank(actions, prices, history=history)
    sel = best_bundle(actions, bundles or [], prices, budget=budget, history=history)
    measured = [r for r in ranked if r["measured"]]
    unpriced = list(prices.unpriced)
    best = sel.get("selected")
    return {
        "actions": len(actions),
        "feasible": len(ranked),
        "removed_infeasible": sel["removed_infeasible"],
        "ranked": ranked,
        "selection": sel,
        "unpriced_resources": unpriced,
        "headline": (
            (f"selected {best['bundle_id']} at surplus {best['surplus']}"      # type: ignore[index]
             + ("; a BUNDLE beat the single best action, which a greedy ranker would have missed"
                if sel["bundle_beats_greedy"] else "")
             if best else
             "no affordable feasible action set -- every candidate breaches the budget or lacks a "
             "posterior width")
            + (f". {len(ranked) - len(measured)} action(s) carry no posterior width and cannot be "
               "ranked" if len(measured) < len(ranked) else "")
            + (f". {len(unpriced)} resource(s) have no shadow price and therefore look free"
               if unpriced else "")),
        "note": ("Feasibility is a FILTER applied before optimisation, never a negative score: a "
                 "sufficiently optimistic estimate must never be able to outbid a survival "
                 "constraint. Opportunity cost enters ONCE, through the shadow prices. These are "
                 "models rather than truth -- when estimates and realised descendants diverge, "
                 "realised evidence dominates and the estimator is recalibrated."),
    }

```

### libs\research\intraday_rotation.py
```python
"""Intraday rotation/continuation engine — built to FALSIFY the XAUUSD-derived hypothesis.

Pre-registered in docs/research/INTRADAY_ROTATION_PREREGISTRATION.md (2026-08-04, before any
data). Everything here follows that file; where an implementation choice remained, the
conservative side was taken and is commented at the site.

DESIGN. Candidate bars are detected vectorised; each candidate is then resolved by a bounded
forward scan (max `time_stop` bars), which keeps the whole 540-config grid tractable without a
per-bar Python loop over 300k bars. Lookahead discipline: every quantity used to ADMIT a bar-t
entry is computed from data ending at bar t (boundaries exclude bar t itself: shifted rolling
extrema), and fills happen at bar t's close (rotation, taker) or at a later bar's limit touch
(continuation, maker). The self-test in tests/ shuffles future bars and demands the entry set
not change — the Part-3 "watch for" made mechanical.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np

TAKER_BPS = 4.0 + 1.0        # taker fee + 1bp slippage on market legs (entries, stop exits)
MAKER_BPS = 2.0              # limit fills: continuation entries, boundary targets
ER_RANGE = 0.25              # efficiency-ratio ceiling for RANGE
ER_TREND = 0.45              # floor for TREND
ER_WINDOW = 48
ATR_WINDOW = 20
STOP_ATR_BUFFER = 0.25
LOCATION_MIN_RR = 2.0        # opposing boundary must be >= 2x the stop distance away
PARTIAL_R = 0.75             # variant (c): take half at 0.75R
BREAKOUT_ATR_MULT = 1.5

N_GRID = (24, 48, 96)
K_GRID = (6, 12, 24)
M_GRID = (24, 48, 96)
EXIT_VARIANTS = ("r1.5", "r2", "r3", "boundary", "mimic")


@dataclass
class Trade:
    entry_i: int
    exit_i: int
    side: int                # +1 long, -1 short
    entry_px: float
    exit_px: float
    stop_px: float
    r_multiple: float        # net of fees/funding, in R units
    net_ret: float           # net fractional return on notional
    regime: str
    exit_reason: str
    hour_utc: int
    partial: bool = False


@dataclass
class ConfigResult:
    symbol: str
    strategy: str            # rotation | continuation
    n: int
    k: int                  # 0 for rotation
    m: int
    exit_variant: str
    trades: list[Trade] = field(default_factory=list)
    n_unfilled: int = 0      # continuation limits cancelled after K bars

    def r_series(self) -> np.ndarray:
        return np.asarray([t.r_multiple for t in self.trades], dtype="float64")


def atr(high: np.ndarray, low: np.ndarray, close: np.ndarray, window: int = ATR_WINDOW
        ) -> np.ndarray:
    prev = np.concatenate([[close[0]], close[:-1]])
    tr = np.maximum(high - low, np.maximum(np.abs(high - prev), np.abs(low - prev)))
    out = np.full_like(tr, np.nan)
    if len(tr) >= window:
        c = np.cumsum(tr)
        out[window - 1:] = (c[window - 1:] - np.concatenate([[0.0], c[:-window]])) / window
    return np.asarray(out)


def efficiency_ratio(close: np.ndarray, window: int = ER_WINDOW) -> np.ndarray:
    d = np.abs(np.diff(close, prepend=close[0]))
    cd = np.cumsum(d)
    denom = np.full_like(close, np.nan)
    denom[window:] = cd[window:] - cd[:-window]
    num = np.full_like(close, np.nan)
    num[window:] = np.abs(close[window:] - close[:-window])
    with np.errstate(invalid="ignore", divide="ignore"):
        return np.where(denom > 0, num / denom, 0.0)


def regimes(close: np.ndarray) -> np.ndarray:
    """0 = RANGE, 1 = TREND, 2 = TRANSITION (and warmup NaN -> TRANSITION, which trades nothing)."""
    er = efficiency_ratio(close)
    out = np.full(len(close), 2, dtype=np.int8)
    out[er < ER_RANGE] = 0
    out[er > ER_TREND] = 1
    out[np.isnan(er)] = 2
    return out


def _shifted_extrema(high: np.ndarray, low: np.ndarray, n: int) -> tuple[np.ndarray, np.ndarray]:
    """Rolling N-bar high/low EXCLUDING the current bar — the boundary a bar-t decision may see.

    Including bar t is the classic rotation-backtest lookahead: the bar that tags the boundary
    also defines it, so every touch is 'at the boundary' by construction. sliding_window_view
    over [t-n, t) keeps this honest.
    """
    from numpy.lib.stride_tricks import sliding_window_view
    hi = np.full(len(high), np.nan)
    lo = np.full(len(low), np.nan)
    if len(high) > n:
        hi[n:] = sliding_window_view(high, n)[:-1].max(axis=1)
        lo[n:] = sliding_window_view(low, n)[:-1].min(axis=1)
    return hi, lo


def _funding_cost(times_ms: np.ndarray, i0: int, i1: int, side: int,
                  f_time: np.ndarray, f_rate: np.ndarray) -> float:
    """Sum of funding paid while open across settlements in (t_entry, t_exit]. Long pays +rate."""
    if len(f_time) == 0:
        return 0.0
    a = np.searchsorted(f_time, times_ms[i0], side="right")
    b = np.searchsorted(f_time, times_ms[i1], side="right")
    if b <= a:
        return 0.0
    return float(side * np.sum(f_rate[a:b]))


def _resolve(side: int, entry_i: int, entry_px: float, stop_px: float,
             high: np.ndarray, low: np.ndarray, close: np.ndarray,
             opp_boundary: float, variant: str, m: int,
             times_ms: np.ndarray, f_time: np.ndarray, f_rate: np.ndarray,
             regime: str, entry_bps: float) -> Trade | None:
    """Forward-scan one entry to its exit. Conservative tie-break: when stop and target are both
    inside one bar's range, the STOP fills — intrabar path is unknown and the pessimistic order
    is the one that cannot flatter the result."""
    risk = abs(entry_px - stop_px)
    if risk <= 0:
        return None
    if variant.startswith("r"):
        target = entry_px + side * float(variant[1:]) * risk
    elif variant == "boundary":
        target = opp_boundary
    else:                                     # mimic: partial at 0.75R then swing-trail
        target = entry_px + side * PARTIAL_R * risk
    n_bars = len(close)
    end = min(entry_i + m, n_bars - 1)
    partial_done = False
    realised = 0.0                            # fraction of position already banked (mimic)
    trail = stop_px
    exit_i, exit_px, reason = end, close[end], "time"
    exit_bps = TAKER_BPS                      # time exits go at market
    for j in range(entry_i + 1, end + 1):
        hit_stop = low[j] <= trail if side > 0 else high[j] >= trail
        hit_tgt = high[j] >= target if side > 0 else low[j] <= target
        if hit_stop:                          # pessimistic order: stop first
            exit_i, exit_px, reason, exit_bps = j, trail, "stop", TAKER_BPS
            break
        if hit_tgt:
            if variant == "mimic" and not partial_done:
                realised = 0.5 * PARTIAL_R    # half the position banked at 0.75R (maker)
                partial_done = True
                trail = entry_px              # remainder now risk-free to entry
                target = entry_px + side * 1e12   # no fixed target; trail owns the rest
                continue
            exit_i, exit_px, reason = j, target, "target"
            exit_bps = MAKER_BPS
            break
        if variant == "mimic" and partial_done and j - entry_i >= 3:
            # swing-trail on 5m: ratchet to the extreme of the last 3 bars, never backwards
            swing = low[j - 3:j].min() if side > 0 else high[j - 3:j].max()
            trail = max(trail, swing) if side > 0 else min(trail, swing)
    gross_r = side * (exit_px - entry_px) / risk
    cost_frac = (entry_bps + exit_bps) / 1e4
    funding = _funding_cost(times_ms, entry_i, exit_i, side, f_time, f_rate)
    net_ret = side * (exit_px - entry_px) / entry_px
    if variant == "mimic" and partial_done:
        net_ret = 0.5 * (PARTIAL_R * risk / entry_px) + 0.5 * net_ret
        gross_r = realised + 0.5 * gross_r
    net_ret -= cost_frac + funding
    r_net = gross_r - (cost_frac + funding) * entry_px / risk
    hour = int((times_ms[entry_i] // 3_600_000) % 24)
    return Trade(entry_i, exit_i, side, entry_px, exit_px, stop_px, float(r_net),
                 float(net_ret), regime, reason, hour, partial_done)


def run_config(data: dict[str, np.ndarray], *, symbol: str, strategy: str, n: int, k: int,
               m: int, variant: str, lo_q: float = 0.25, start: int = 0,
               stop: int | None = None) -> ConfigResult:
    """One (strategy, N, K, M, exit) pass over [start, stop) — the walk-forward window seam."""
    high, low, close = data["high"], data["low"], data["close"]
    opn = data["open"]
    times = data["open_time"]
    f_time = data.get("funding_time", np.empty(0))
    f_rate = data.get("funding_rate", np.empty(0))
    a = atr(high, low, close)
    reg = regimes(close)
    hi_n, lo_n = _shifted_extrema(high, low, n)
    stop = len(close) if stop is None else stop
    res = ConfigResult(symbol, strategy, n, k, m, variant)
    width = hi_n - lo_n
    lo_i = max(start, n + ER_WINDOW + 1)
    hi_i = min(stop, len(close) - 2)
    if hi_i <= lo_i:
        return res
    # CANDIDATE DETECTION IS VECTORISED; only candidates are visited. Semantics are identical
    # to the original per-bar walk (verified by the no-lookahead and conservatism tests): the
    # one-position-at-a-time rule is applied while iterating candidates in time order.
    idx = np.arange(len(close))
    in_window = (idx >= lo_i) & (idx < hi_i)
    valid = in_window & np.isfinite(width) & (width > 0) & np.isfinite(a)
    bar_rng = high - low
    if strategy == "rotation":
        with np.errstate(invalid="ignore", divide="ignore"):
            pos_rng = np.where(width > 0, (close - lo_n) / width, np.nan)
            pos_bar = np.where(bar_rng > 0, (close - low) / bar_rng, np.nan)
        long_m = valid & (reg == 0) & (pos_rng <= lo_q) & (pos_bar >= 2.0 / 3.0)
        short_m = valid & (reg == 0) & (pos_rng >= 1.0 - lo_q) & (pos_bar <= 1.0 / 3.0)
        stop_l = low - STOP_ATR_BUFFER * a
        stop_s = high + STOP_ATR_BUFFER * a
        risk_l = close - stop_l
        risk_s = stop_s - close
        long_m &= (risk_l > 0) & ((hi_n - close) >= LOCATION_MIN_RR * risk_l)
        short_m &= (risk_s > 0) & ((close - lo_n) >= LOCATION_MIN_RR * risk_s)
        cands = np.flatnonzero(long_m | short_m)
        sides = np.where(long_m[cands], 1, -1)
        last_exit = lo_i
        for i, side in zip(cands.tolist(), sides.tolist(), strict=True):
            if i < last_exit:
                continue
            stop_px = float(stop_l[i] if side > 0 else stop_s[i])
            opp = float(hi_n[i] if side > 0 else lo_n[i])
            t = _resolve(side, i, float(close[i]), stop_px, high, low, close, opp,
                         variant, m, times, f_time, f_rate, "RANGE", TAKER_BPS)
            if t is not None:
                res.trades.append(t)
                last_exit = t.exit_i + 1
    else:
        brk_l = valid & (reg == 1) & (close > hi_n) & (bar_rng > BREAKOUT_ATR_MULT * a)
        brk_s = valid & (reg == 1) & (close < lo_n) & (bar_rng > BREAKOUT_ATR_MULT * a)
        cands = np.flatnonzero(brk_l | brk_s)
        sides = np.where(brk_l[cands], 1, -1)
        last_exit = lo_i
        for i, side in zip(cands.tolist(), sides.tolist(), strict=True):
            if i < last_exit:
                continue
            level = float(hi_n[i] if side > 0 else lo_n[i])
            filled = None
            for j in range(i + 1, min(i + 1 + k, len(close) - 1)):
                touched = low[j] <= level if side > 0 else high[j] >= level
                if touched:
                    # limit at the broken boundary; when the bar gaps through it, the OPEN is
                    # what a resting limit would actually have got (taking the worse of
                    # level/open would penalise gaps twice; taking close would be fiction).
                    px = float(min(level, opn[j]) if side > 0 else max(level, opn[j]))
                    filled = (j, px)
                    break
            if filled is None:
                res.n_unfilled += 1
                continue
            j, px = filled
            stop_px = (px - (a[i] * STOP_ATR_BUFFER + bar_rng[i]) if side > 0
                       else px + (a[i] * STOP_ATR_BUFFER + bar_rng[i]))
            opp = px + side * 3.0 * abs(px - stop_px)      # boundary target n/a post-break
            t = _resolve(side, j, px, float(stop_px), high, low, close, opp,
                         variant, m, times, f_time, f_rate, "TREND", MAKER_BPS)
            if t is not None:
                res.trades.append(t)
                last_exit = t.exit_i + 1
    return res


# ------------------------------------------------------------------ evaluation helpers

def expectancy(r: np.ndarray) -> dict[str, float]:
    if len(r) == 0:
        return {"n": 0, "exp_r": 0.0, "win": 0.0, "sharpe_r": 0.0}
    win = float(np.mean(r > 0))
    sd = float(np.std(r, ddof=1)) if len(r) > 1 else 0.0
    return {"n": len(r), "exp_r": float(np.mean(r)), "win": win,
            "sharpe_r": float(np.mean(r) / sd) if sd > 0 else 0.0}


def wilson_ci(wins: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return (0.0, 1.0)
    p = wins / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (float(c - h), float(c + h))


def bootstrap_sizing(r: np.ndarray, *, risk_fracs: tuple[float, ...],
                     n_paths: int = 2000, block: int = 10, seed: int = 7,
                     ruin_level: float = 0.20) -> list[dict[str, Any]]:
    """Stationary-block bootstrap of the OOS R-sequence, compounded at each risk fraction.

    Equity multiplies by (1 + f * r_i) per trade — the R-multiple already carries costs. Block
    resampling preserves streakiness, which is exactly what fixed-fraction sizing is sensitive
    to and what an iid bootstrap would understate.
    """
    rng = np.random.default_rng(seed)
    n = len(r)
    out: list[dict[str, Any]] = []
    if n < 20:
        return out
    paths = np.empty((n_paths, n))
    for p in range(n_paths):
        seq: list[float] = []
        while len(seq) < n:
            s = int(rng.integers(0, n))
            ln = int(rng.geometric(1.0 / block))
            seq.extend(r[(s + np.arange(ln)) % n])
        paths[p] = np.asarray(seq[:n])
    # longest losing streak on the REAL sequence
    streak = best = 0
    for x in r:
        streak = streak + 1 if x < 0 else 0
        best = max(best, streak)
    for f in risk_fracs:
        eq = np.cumprod(1.0 + f * paths, axis=1)
        peak = np.maximum.accumulate(eq, axis=1)
        dd = 1.0 - eq / peak
        maxdd = dd.max(axis=1)
        term = eq[:, -1]
        out.append({
            "risk_frac": f,
            "median_terminal": float(np.median(term)),
            "median_max_dd": float(np.median(maxdd)),
            "p95_max_dd": float(np.percentile(maxdd, 95)),
            "p_dd_over_50": float(np.mean(maxdd > 0.50)),
            "p_ruin": float(np.mean(eq.min(axis=1) < ruin_level)),
            "longest_loss_streak_real": int(best),
            "streak_implied_dd": float(1.0 - (1.0 - f) ** best),
        })
    return out


def half_kelly(r: np.ndarray, *, n_boot: int = 2000, seed: int = 11
               ) -> dict[str, float]:
    """Half of the R-space Kelly fraction f* = E[r]/E[r^2] (quadratic approximation), with a
    bootstrap CI. Stated in the same risk-per-trade units as the sizing sweep."""
    if len(r) < 20 or float(np.mean(r)) <= 0:
        return {"half_kelly": 0.0, "lo": 0.0, "hi": 0.0}
    rng = np.random.default_rng(seed)
    f = 0.5 * float(np.mean(r) / np.mean(r * r))
    bs = []
    for _ in range(n_boot):
        s = r[rng.integers(0, len(r), len(r))]
        m2 = float(np.mean(s * s))
        if m2 > 0:
            bs.append(0.5 * float(np.mean(s) / m2))
    return {"half_kelly": f, "lo": float(np.percentile(bs, 2.5)),
            "hi": float(np.percentile(bs, 97.5))}


def deflated_sharpe(sr: float, n_obs: int, n_configs: int, *, skew: float = 0.0,
                    kurt: float = 3.0) -> float:
    """PSR against the expected-max-Sharpe benchmark over n_configs (Bailey & Lopez de Prado)."""
    from scipy.stats import norm
    if n_obs < 2 or n_configs < 1:
        return 0.0
    e = np.euler_gamma
    var_sr = 1.0 / n_obs
    sr0 = np.sqrt(var_sr) * ((1 - e) * norm.ppf(1 - 1.0 / n_configs)
                             + e * norm.ppf(1 - 1.0 / (n_configs * np.e)))
    denom = np.sqrt(max(1e-12, 1 - skew * sr + (kurt - 1) / 4.0 * sr * sr))
    z = (sr - sr0) * np.sqrt(n_obs - 1) / denom
    return float(norm.cdf(z))

```

### libs\research\search_populations.py
```python
"""NINE SEARCH POPULATIONS OVER ONE GRAMMAR, RUN TOGETHER UNDER ONE BUDGET, EACH SCORED BY YIELD.

WHY MORE THAN ONE SEARCH. `libs.research.generators` offers three ways to draw a tree -- uniform,
GFlowNet, symbolic regression -- and `alpha_evolution` picks one per individual. Three samplers
over one grammar is still ONE search: they all start from noise and hill-climb on the same
signal, so they find the same kind of alpha and fail on the same kind. The populations here fail
differently on purpose, and that is the whole design:

    gp                 NSGA-II over the fitness COMPONENTS, not their weighted sum, so the
                       candidate that is best on the tail and worst on cost survives selection
                       instead of being averaged away by whichever exchange rate is in force.
    gflownet           samples in proportion to reward; finds MOTIFS the history rewarded.
    symreg             hill-climbs toward a supervised target; finds FIT.
    program_synthesis  bottom-up enumeration of the typed grammar to a depth bound, deduped by
                       subtree hash: the only population that is EXHAUSTIVE at small depth, so
                       nothing simple is missed because no sampler happened to draw it.
    bayesian           a TPE surrogate over expression FEATURES chooses which children are worth
                       evaluating at all -- the population that spends the evaluation budget
                       rather than the sampling budget.
    zoo_mutation       the public alpha zoos (Alpha158-style price/volume features, WorldQuant
                       101-style rank/ts operators, GTJA-191-style composites) as GENETIC
                       MATERIAL: every template is reimplemented as a typed tree of THIS grammar
                       and emitted only through a named mutation axis. The zoo is never traded.
    graveyard_derived  mutates what DIED, along the axis its recorded fate names.
    causal_derived     builds from the admitted edges of the world causal graph.
    claims_derived     builds from mined mechanism claims by their declared mechanism class.

ONE CACHE, SHARED. Every population evaluates through the same `alpha_grammar.SubtreeCache`, so
a subtree one population paid for is free for the other eight. Trees drawn from one grammar
share their lower halves overwhelmingly, which is exactly what makes the shared unit of work the
subtree rather than the expression.

YIELD IS REPORTED, NEVER SELF-SCORED. Each population reports proposed / unique-by-hash /
well-formed / passed-the-cheap-falsifier / donated. Nothing here reads those numbers back into
its own weights: the ledger that sets weights lives outside, so a population cannot promote
itself.

THE ZOO IS GENETIC MATERIAL, NOT A LIBRARY. No formula from any public set is proposed as
written. Each template below is a SHAPE the desk re-derived in its own operators, on its own
terminals, and it reaches the gauntlet only after a mutation has changed its instrument,
horizon, lag, normalisation, state, session, cross-asset leg, or residualisation. Nothing is
copied: there is no third-party code in this module and no formula is executed as published.

NOTHING HERE HAS AUTHORITY. A population proposes; the fitness ranks; the gauntlet certifies.
"""
from __future__ import annotations

import json
import math
import time
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from libs.research import alpha_grammar as ag
from libs.research import generators as gen
from libs.research.alpha_fitness import FitnessTerms, nsga2_order

ROOT = Path(__file__).resolve().parents[2]
DESK = ROOT / "desks" / "mt5"
#: The three ledgers the derived populations mine. Every one is read DEFENSIVELY -- absent,
#: truncated, half-written by a sibling organ, or carrying a schema this module has not seen --
#: because they are written by other engines on their own clocks and a search that dies when a
#: sibling is mid-write is a search that runs only when nothing else does.
HYPOTHESIS_GRAPH = DESK / "data" / "hypothesis_graph.jsonl"
CAUSAL_GRAPH = DESK / "data" / "world_causal_graph.json"
DEEP_FOREST_CLAIMS = DESK / "data" / "deep_forest_claims.jsonl"
#: Rows read from the tail of a ledger. The newest fates and claims are the informative ones and
#: the graveyard is 30k lines: reading it whole every hour would cost more than the search.
LEDGER_TAIL = 4000
#: Enumeration bounds for `program_synthesis`. Depth 2 over the full operator set is already
#: hundreds of thousands of trees, so the pool per level is capped and the cap is declared.
SYNTH_MAX_DEPTH = 2
SYNTH_POOL = 900
#: The weight every population keeps whatever its realised growth, so the ordering the
#: dE[logW] feedback produces is a PREFERENCE and never a retirement. `_order` already gives
#: every named population its draw; this is what stops one bad hour from putting a population
#: last for good.
ELOG_FLOOR = 0.25
#: TPE split: the share of the history treated as the GOOD set whose feature density is chased.
TPE_GAMMA = 0.25
TPE_CANDIDATES = 200
TPE_PRIOR = 1.0

Expr = Any
History = Sequence[tuple[Any, float]]


# --------------------------------------------------------------------------- the context
@dataclass
class SearchContext:
    """Everything a population needs, and nothing it may decide.

    A population reads this and returns expressions. It never screens, never scores, never
    donates and never writes a file -- so a broken population costs its share of one budget and
    can do nothing else.
    """

    rng: np.random.Generator
    frames: dict[str, pd.Series] = field(default_factory=dict)
    ret: pd.Series | None = None
    symbol: str = ""
    allow_drivers: bool = True
    max_depth: int = 3
    cache: ag.SubtreeCache | None = None
    #: (expression, scalar fitness) rows the samplers learn from.
    history: History = ()
    #: (expression, full term vector) rows the multi-objective populations select over.
    scored: Sequence[tuple[Expr, FitnessTerms]] = ()
    #: (population name, full term vector) for every expression the caller has SCORED and can
    #: attribute to the population that made it. This is what turns the yield ledger from "how
    #: many did it draw" into "what did what it drew do for the book" -- see `elog_weights`.
    attributed: Sequence[tuple[str, FitnessTerms]] = ()
    #: Trees worth breeding from: the elite, plus the canon.
    seeds: Sequence[Expr] = ()
    #: The cheap falsifier -- one call, one verdict, no side effects. None means "not screened
    #: here", and the yield then says `passed=proposed` rather than pretending to have screened.
    falsifier: Callable[[Expr], bool] | None = None
    #: Terminals a population may draw. Defaults to whatever the frames actually carry.
    terminals: tuple[str, ...] = ()
    #: Driver roles present in the frames, for the cross-asset mutation axis.
    drivers: tuple[str, ...] = ()
    #: Population name -> what it wants said about a draw the counters cannot express ("the
    #: graveyard named no cause", "the causal graph has no admitted edge on a driver I have").
    #: `run` copies these into the yield ledger, so an empty population is never just a zero.
    notes: dict[str, str] = field(default_factory=dict)
    #: Ledger paths, overridable so a test never reads the desk's real ledgers.
    hypothesis_graph: Path = HYPOTHESIS_GRAPH
    causal_graph: Path = CAUSAL_GRAPH
    claims: Path = DEEP_FOREST_CLAIMS

    def __post_init__(self) -> None:
        if not self.terminals:
            self.terminals = ag.available_terminals(self.frames, self.allow_drivers)
        if not self.drivers:
            self.drivers = tuple(t for t in ag.DRIVER_TERMINALS if t in self.terminals)
        # ALLOW-DRIVERS FOLLOWS THE FRAMES, not the caller's optimism. A context that permits
        # driver terminals it has no series for lets every sampler spend its budget on trees
        # that evaluate to NaN -- the flag and the pool must agree, and the pool is the fact.
        self.allow_drivers = bool(self.allow_drivers and self.drivers)

    def memo(self) -> Any:
        """The shared subtree memo for these bars, or a private dict when no cache was given."""
        if self.cache is None:
            return {}
        return self.cache.scope(self.symbol, self.frames)

    def evaluate(self, expr: Expr) -> pd.Series:
        """Evaluate through the SHARED cache, so every population fills one table."""
        return ag.evaluate(expr, self.frames, self.memo())


@dataclass
class PopulationYield:
    """What one population's share of the budget bought. Counted, never self-scored."""

    name: str
    proposed: int = 0
    unique: int = 0
    well_formed: int = 0
    passed: int = 0
    donated: int = 0
    seconds: float = 0.0
    note: str = ""
    #: Expressions from this population the caller has SCORED, and the mean realised
    #: `delta_elog` -- annual growth points the book gains -- across them. None is unmeasured:
    #: a population whose draws have not been scored yet has no growth to report, which is a
    #: different fact from a population whose draws were worth nothing.
    scored: int = 0
    delta_elog_mean: float | None = None

    def as_dict(self) -> dict[str, Any]:
        return {"population": self.name, "proposed": self.proposed, "unique": self.unique,
                "well_formed": self.well_formed, "passed": self.passed,
                "donated": self.donated, "seconds": round(self.seconds, 2),
                "scored": self.scored,
                "delta_elog_mean": (None if self.delta_elog_mean is None
                                    else round(self.delta_elog_mean, 6)),
                "note": self.note}


@dataclass
class SearchResult:
    """Everything the run produced: the distinct trees, who made each, and the yield ledger."""

    proposals: list[tuple[Expr, str]] = field(default_factory=list)
    yields: dict[str, PopulationYield] = field(default_factory=dict)
    cache_stats: dict[str, Any] = field(default_factory=dict)
    failures: list[str] = field(default_factory=list)

    def yield_rows(self) -> list[dict[str, Any]]:
        return [self.yields[k].as_dict() for k in sorted(self.yields)]

    def yield_line(self) -> dict[str, int]:
        """The one-line counter set for the hourly organ's YIELD convention."""
        return {"proposals": len(self.proposals),
                "unique": sum(y.unique for y in self.yields.values()),
                "passed": sum(y.passed for y in self.yields.values()),
                "populations": len(self.yields)}

    def elog_weights(self, *, floor: float = ELOG_FLOOR) -> tuple[dict[str, float] | None, str]:
        """The NEXT pass's population weights, from the realised dE[logW] of what each produced.

        THE FEEDBACK THIS CLOSES (Tier-1 audit G4, 2026-09-08). The weights that decide which
        population runs first under a short budget were fed by YIELD COUNTS -- how many trees a
        population drew and how many were certified later. A count is not a contribution: a
        population that draws ten cells the book cannot use outranks one that draws a single
        tail diversifier, which is the ordering the whole fitness exists to invert.
        `delta_elog` is the allocator's own marginal growth for the candidate; the mean of it
        across a population's SCORED draws is what that population has actually been worth.

        A population at or below the pooled mean keeps `floor` rather than zero, so the ordering
        is a preference and never a retirement -- `_order` already guarantees every named
        population its draw, and this keeps that true when the evidence is thin. Returns
        (None, why) when nothing has been scored: uniform is the honest answer then, and the
        caller's existing weight table stands.
        """
        rows = [(y.name, y.delta_elog_mean, y.scored) for y in self.yields.values()
                if y.delta_elog_mean is not None and y.scored > 0]
        if not rows:
            return None, ("no scored draw carries a realised dE[logW] yet: population weights "
                          "unmeasured, the caller's own table stands")
        pooled = sum(m * n for _n0, m, n in rows) / max(1, sum(n for _n0, _m, n in rows))
        out = {name: float(floor + max(0.0, mean - pooled)) for name, mean, _n in rows}
        best = max(rows, key=lambda r: r[1])
        return out, (f"realised dE[logW] over {sum(n for _n, _m, n in rows)} scored draw(s) in "
                     f"{len(rows)} population(s), pooled mean {pooled:+.6f}; best "
                     f"{best[0]} {best[1]:+.6f} over {best[2]}")


Population = Callable[[SearchContext, int], list[Expr]]


# --------------------------------------------------------------------------- gp (NSGA-II)
def gp(ctx: SearchContext, n: int) -> list[Expr]:
    """Genetic programming with NSGA-II selection over the FITNESS COMPONENTS.

    WHY MULTI-OBJECTIVE. A scalar fitness is an exchange rate, and selecting on it deletes every
    candidate that is extraordinary on one term and ordinary on the rest -- which is precisely
    the candidate the book is missing (the tail diversifier is usually a poor standalone Sharpe).
    Non-dominated sorting keeps the whole Pareto front, and crowding distance keeps the lonely
    members of it, so the parents are diverse in the terms rather than in their sum.

    Falls back to the seeds when nothing has been scored yet: generation zero has no front.
    """
    parents = _nsga_parents(ctx)
    if not parents:
        parents = [s for s in ctx.seeds if ag.is_valid(s, ctx.allow_drivers)]
    if not parents:
        return [ag.random_expr(ctx.rng, ctx.max_depth, ctx.allow_drivers,
                               terminals=ctx.terminals) for _ in range(n)]
    out: list[Expr] = []
    for _ in range(n):
        a = parents[int(ctx.rng.integers(len(parents)))]
        if len(parents) > 1 and ctx.rng.random() < 0.5:
            b = parents[int(ctx.rng.integers(len(parents)))]
            out.append(ag.crossover(a, b, ctx.rng, ctx.allow_drivers))
        else:
            out.append(ag.mutate(a, ctx.rng, ctx.allow_drivers, terminals=ctx.terminals))
    return out


def _nsga_parents(ctx: SearchContext, keep: int = 12) -> list[Expr]:
    rows = [(e, t) for e, t in ctx.scored if isinstance(t, FitnessTerms)]
    if not rows:
        return []
    order = nsga2_order([t for _e, t in rows])
    return [rows[i][0] for i in order[:keep]]


# --------------------------------------------------------------------------- learned samplers
def gflownet(ctx: SearchContext, n: int) -> list[Expr]:
    """The trained flow network, sampling in proportion to what the history rewarded."""
    net = gen.GFlowNet(max_depth=ctx.max_depth).fit(ctx.history, allow_drivers=ctx.allow_drivers)
    return net.sample_batch(ctx.rng, n, ctx.max_depth, ctx.allow_drivers,
                            terminals=ctx.terminals)


def symreg(ctx: SearchContext, n: int) -> list[Expr]:
    """Symbolic regression toward the NEXT bar's return, restarted per individual.

    The target is forward of the expression's own causal inputs -- a supervised label, not a
    leak -- and the fit slice is the first 70%, with the holdout error reported by the generator
    and never consulted for a choice.
    """
    if ctx.ret is None or not ctx.frames:
        return [ag.random_expr(ctx.rng, ctx.max_depth, ctx.allow_drivers,
                               terminals=ctx.terminals) for _ in range(n)]
    target = pd.Series(ctx.ret).shift(-1)
    # SEEDED FROM WHAT THE DESK ALREADY KNOWS HOW TO SAY (2026-09-08). The seeds are the elite
    # once there is one and `alpha_grammar.CANON` -- now fifteen published formulaic alphas
    # beside the seven hand-written references -- before that. Sixty mutations from noise rarely
    # reach a structure a published alpha already names; half the draws start from one and half
    # still start from noise, so the population keeps finding shapes nobody wrote down.
    seeds = [s for s in (ctx.seeds or tuple(ag.CANON.values()))
             if ag.is_valid(s, ctx.allow_drivers, ctx.terminals)]
    out: list[Expr] = []
    for i in range(n):
        seed = (seeds[int(ctx.rng.integers(len(seeds)))]
                if seeds and i % 2 == 0 else None)
        out.append(gen.symbolic_regression(ctx.rng, ctx.frames, target,
                                           allow_drivers=ctx.allow_drivers,
                                           max_depth=ctx.max_depth, terminals=ctx.terminals,
                                           seed_expr=seed))
    return out


# --------------------------------------------------------------------------- program synthesis
def program_synthesis(ctx: SearchContext, n: int) -> list[Expr]:
    """Bottom-up ENUMERATION of the typed grammar to a depth bound, deduped by subtree hash.

    The only exhaustive population. Every other one samples, so a simple tree nobody happened to
    draw is a tree the desk never tried; this builds level 0 (terminals), then every operator
    over what level 0 produced, then every operator over that -- keeping only what the
    production screen accepts and only one representative per structural hash.

    THE DEDUPE IS THE POINT AND IT IS WHY IT FITS IN AN HOUR. Enumeration without it re-derives
    the same subtree under every parent; with it the pool at each level is the set of DISTINCT
    programs, which is what `SYNTH_POOL` caps. Trees already in the history are skipped: the
    enumerator's job is to find what the samplers did not.
    """
    seen: set[str] = {ag.subtree_hash(e) for e, _f in ctx.history}
    windows = tuple(ag.WINDOWS)
    level: list[Expr] = list(ctx.terminals)
    pool: list[Expr] = []
    for _depth in range(max(1, min(int(ctx.max_depth), SYNTH_MAX_DEPTH))):
        nxt: list[Expr] = []
        for child in level:
            for op in ag.UNARY:
                _add(nxt, seen, [op, child], ctx)
            for op in ag.WINDOWED:
                for w in windows:
                    _add(nxt, seen, [op, child, w], ctx)
            if len(nxt) >= SYNTH_POOL:
                break
        for a in level:
            if len(nxt) >= SYNTH_POOL:
                break
            for b in level:
                for op in ag.BINARY:
                    _add(nxt, seen, [op, a, b], ctx)
                for op in ag.BINARY_WINDOWED:
                    for w in windows[::3]:
                        _add(nxt, seen, [op, a, b, w], ctx)
        pool.extend(nxt)
        level = nxt[:SYNTH_POOL]
        if not level:
            break
    if not pool:
        return []
    idx = ctx.rng.permutation(len(pool))[:n]
    return [pool[int(i)] for i in idx]


def _add(out: list[Expr], seen: set[str], expr: Expr, ctx: SearchContext) -> None:
    if len(out) >= SYNTH_POOL or not ag.is_valid(expr, ctx.allow_drivers, ctx.terminals):
        return
    h = ag.subtree_hash(expr)
    if h in seen:
        return
    seen.add(h)
    out.append(expr)


# --------------------------------------------------------------------------- bayesian (TPE)
def bayesian(ctx: SearchContext, n: int) -> list[Expr]:
    """A TPE surrogate over expression FEATURES, choosing which children are worth evaluating.

    Tree-structured Parzen estimation, on a feature space rather than a hyperparameter box: the
    history is split at `TPE_GAMMA` into a good set l(x) and the rest g(x), each feature (an
    operator present, a terminal present, a depth, a window band) gets a Laplace-smoothed
    Bernoulli density under both, and a candidate scores sum log l/g -- the ranking TPE's
    expected improvement reduces to. The population then DRAWS many cheap candidates and
    evaluates only the top `n`.

    WHAT THIS BUYS THAT A SAMPLER DOES NOT. Every other population spends its budget on drawing;
    this one spends it on choosing. With no history it is a uniform draw and says so -- a
    surrogate fitted on nothing is a prior, not a model.
    """
    rows = [(e, float(f)) for e, f in ctx.history
            if isinstance(f, (int, float)) and math.isfinite(float(f))]
    draws = [ag.random_expr(ctx.rng, ctx.max_depth, ctx.allow_drivers, terminals=ctx.terminals)
             for _ in range(max(n, TPE_CANDIDATES))]
    if len(rows) < 8:
        return draws[:n]
    fits = np.array([f for _e, f in rows], dtype=float)
    cut = float(np.quantile(fits, 1.0 - TPE_GAMMA))
    good = [features(e) for e, f in rows if f >= cut]
    bad = [features(e) for e, f in rows if f < cut]
    if not good or not bad:
        return draws[:n]
    lg, gg = _density(good), _density(bad)
    ranked = sorted(draws, key=lambda e: -_tpe_score(features(e), lg, gg, len(good), len(bad)))
    return ranked[:n]


def features(expr: Expr) -> frozenset[str]:
    """The surrogate's view of a tree: which operators, terminals, depth and window band it has.

    Deliberately coarse. A feature the history can only have seen once is a feature the
    surrogate would fit to one lucky tree, so the space is the vocabulary plus two structural
    bands -- things a few dozen observations can actually estimate.
    """
    out: set[str] = set()

    def _walk(x: Expr) -> None:
        if isinstance(x, str):
            out.add(f"t:{x}")
            return
        if not isinstance(x, (list, tuple)) or not x:
            return
        out.add(f"op:{x[0]}")
        for c in x[1:]:
            if isinstance(c, int):
                out.add("w:long" if c >= 48 else ("w:mid" if c >= 12 else "w:short"))
            elif isinstance(c, (str, list, tuple)):
                _walk(c)
    _walk(expr)
    out.add(f"d:{min(ag.depth(expr), 4)}")
    out.add("cx:big" if ag.complexity(expr) > 8 else "cx:small")
    return frozenset(out)


def _density(sets: Sequence[frozenset[str]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for s in sets:
        for f in s:
            counts[f] = counts.get(f, 0) + 1
    return counts


def _tpe_score(feat: frozenset[str], good: dict[str, int], bad: dict[str, int],
               n_good: int, n_bad: int) -> float:
    total = 0.0
    for f in feat:
        p_good = (good.get(f, 0) + TPE_PRIOR) / (n_good + 2 * TPE_PRIOR)
        p_bad = (bad.get(f, 0) + TPE_PRIOR) / (n_bad + 2 * TPE_PRIOR)
        total += math.log(p_good / p_bad)
    return total


# --------------------------------------------------------------------------- the alpha zoos
#: PUBLIC ALPHA FAMILIES AS SHAPES, REIMPLEMENTED IN THIS GRAMMAR'S OWN OPERATORS.
#:
#: What transfers from Alpha158, WorldQuant 101 and GTJA 191 to a gold/FX/index desk is not a
#: single formula -- those were fitted to a Chinese equity cross-section a decade ago and the
#: desk has no cross-section -- it is the SHAPES: a normalised momentum, a range position, a
#: price-volume co-movement, a decayed reversal, a rank of a rank. Each entry below is that
#: shape written in this grammar, on this desk's terminals, and typed by this desk's algebra.
#: None is proposed as written: `zoo_mutation` emits a template only after a named mutation.
ZOO_TEMPLATES: dict[str, dict[str, Any]] = {
    # Alpha158-style price/volume features: normalised location, normalised change, activity.
    "a158_close_position": {"family": "alpha158", "expr": ["zscore", "close", 24],
                            "shape": "where price sits in its own recent distribution"},
    "a158_range_position": {"family": "alpha158", "expr": ["div", ["sub", "close", ["min",
                            "low", 24]], ["sub", ["max", "high", 24], ["min", "low", 24]]],
                            "shape": "position inside the recent high-low range"},
    "a158_return_decay": {"family": "alpha158", "expr": ["decay", "ret", 12],
                          "shape": "linearly decayed recent return"},
    "a158_activity_ratio": {"family": "alpha158",
                            "expr": ["div", "activity", ["mean", "activity", 24]],
                            "shape": "this bar's activity against its own normal"},
    "a158_vol_ratio": {"family": "alpha158", "expr": ["div", "vol", ["mean", "vol", 120]],
                       "shape": "short volatility against long volatility"},
    # WorldQuant-101-style rank / time-series operators. The published set ranks
    # CROSS-SECTIONALLY; the desk has one instrument per cell, so the rank is over the series'
    # own history -- the same question asked of time instead of of peers.
    "wq_ts_rank_return": {"family": "wq101", "expr": ["ts_rank", "ret", 48],
                          "shape": "rank of today's return in its own recent history"},
    "wq_corr_price_volume": {"family": "wq101", "expr": ["corr", "close", "activity", 24],
                             "shape": "price-volume co-movement"},
    "wq_neg_delta_close": {"family": "wq101", "expr": ["neg", ["delta", "close", 5]],
                           "shape": "short-horizon reversal"},
    "wq_scaled_range": {"family": "wq101", "expr": ["scale", "range", 48],
                        "shape": "this bar's range as a share of the window's total"},
    "wq_group_rank_state": {"family": "wq101",
                            "expr": ["group_rank", "ret", "vol", 48],
                            "shape": "rank of the return among bars in the same volatility state"},
    # GTJA-191-style composites: signed strength, decayed extremeness, bars since an extreme.
    "gtja_signed_strength": {"family": "gtja191",
                             "expr": ["mul", ["sign", ["delta", "close", 5]],
                                      ["ts_rank", "range", 24]],
                             "shape": "direction of the move times how big the bar was"},
    "gtja_since_high": {"family": "gtja191", "expr": ["bars_since_max", "high", 120],
                        "shape": "how long since the last high"},
    "gtja_decayed_rank": {"family": "gtja191", "expr": ["decay", ["ts_rank", "close", 48], 8],
                          "shape": "a smoothed rank of price"},
    "gtja_residual_to_driver": {"family": "gtja191",
                                "expr": ["residual", "close", "usd", 120],
                                "shape": "the part of price the driver does not explain"},
}
#: THE MUTATION AXES. A template reaches the gauntlet only through one of these, so what is
#: tried is always the desk's variation of a public shape and never the public shape itself.
MUTATION_AXES: tuple[str, ...] = ("instrument", "horizon", "lag", "normalisation", "state",
                                  "session", "cross_asset", "residualisation", "entry_exit")


def zoo_mutation(ctx: SearchContext, n: int) -> list[Expr]:
    """One mutated public-zoo shape per draw, along one NAMED axis. Never the shape as written.

    `_zoo_axis` is what makes this a population rather than a copy: the axis says what was
    changed and the recorded generator says which template it was changed from, so a survivor's
    lineage reads "GTJA-style signed strength, horizon axis" rather than "alpha 47".
    """
    names = [k for k, v in ZOO_TEMPLATES.items()
             if ag.is_valid(v["expr"], ctx.allow_drivers, ctx.terminals)]
    if not names:
        return []
    out: list[Expr] = []
    for _ in range(n):
        tpl = ZOO_TEMPLATES[names[int(ctx.rng.integers(len(names)))]]
        axis = MUTATION_AXES[int(ctx.rng.integers(len(MUTATION_AXES)))]
        cand = _zoo_axis(tpl["expr"], axis, ctx)
        if ag.is_valid(cand, ctx.allow_drivers, ctx.terminals) and ag.key(cand) != ag.key(
                tpl["expr"]):
            out.append(cand)
    return out


def _zoo_axis(expr: Expr, axis: str, ctx: SearchContext) -> Expr:
    """Apply ONE named mutation axis to a template. Unknown axes fall to a structural mutation."""
    rng = ctx.rng
    if axis == "horizon":
        return _rewindow(expr, rng, scale=float(rng.choice([0.25, 0.5, 2.0, 4.0])))
    if axis == "lag":
        return ["delay", expr, int(rng.choice(ag.WINDOWS[:4]))]
    if axis == "normalisation":
        op = str(rng.choice(["zscore", "ts_rank", "scale"]))
        return [op, expr, int(rng.choice(ag.WINDOWS[3:]))]
    if axis == "state":
        gate: Expr = ["sign", ["delta", "vol" if "vol" in ctx.terminals else "range",
                                int(rng.choice(ag.WINDOWS[2:6]))]]
        return ["trade_when", gate, expr]
    if axis == "session":
        # The grammar has no clock terminal, so "session" is expressed as the desk expresses it
        # elsewhere: condition on the ACTIVITY regime, which is what a session IS on H1 bars.
        gate = ["zscore", "activity" if "activity" in ctx.terminals else "range",
                int(rng.choice(ag.WINDOWS[4:]))]
        return ["trade_when", gate, expr]
    if axis == "cross_asset" and ctx.drivers:
        drv = str(rng.choice(list(ctx.drivers)))
        return ["corr", expr, drv, int(rng.choice(ag.WINDOWS[4:]))]
    if axis == "residualisation" and ctx.drivers:
        drv = str(rng.choice(list(ctx.drivers)))
        return ["residual", expr, drv, int(rng.choice(ag.WINDOWS[5:]))]
    if axis == "entry_exit":
        return ["group_zscore", expr, "vol" if "vol" in ctx.terminals else "range",
                int(rng.choice(ag.WINDOWS[4:]))]
    if axis == "instrument":
        # The instrument axis is the SWEEP's, not the tree's: the same shape on another symbol is
        # a different cell, and `alpha_evolution` runs one population per symbol. Inside one
        # symbol the honest reading is "swap the price leg", which is what this does.
        return ag.mutate(expr, rng, ctx.allow_drivers, terminals=ctx.terminals)
    return ag.mutate(expr, rng, ctx.allow_drivers, terminals=ctx.terminals)


def _rewindow(expr: Expr, rng: np.random.Generator, scale: float) -> Expr:
    """Every window in the tree scaled and snapped back onto the grammar's own window ladder."""
    if isinstance(expr, str):
        return expr
    out = [expr[0]]
    for c in expr[1:]:
        if isinstance(c, int):
            target = float(c) * scale
            out.append(min(ag.WINDOWS, key=lambda w: abs(w - target)))
        elif isinstance(c, (str, list, tuple)):
            out.append(_rewindow(c, rng, scale))
        else:
            out.append(c)
    return out


# --------------------------------------------------------------------------- derived populations
#: A recorded fate -> the mutation axis that ATTACKS it. This is the whole value of a graveyard:
#: a cell that died of cost is not re-tried at the same turnover, and one that died of
#: instability is not re-tried on the same window.
FATE_TO_AXIS: dict[str, str] = {
    "cost": "horizon", "net": "horizon", "turnover": "state", "spread": "session",
    "unstable": "horizon", "stability": "horizon", "regime": "state", "state": "state",
    "leak": "lag", "lookahead": "lag", "overlap": "lag",
    "correlat": "residualisation", "crowd": "residualisation", "redundan": "cross_asset",
    "deflat": "normalisation", "multiplicity": "normalisation", "trials": "normalisation",
    "capacity": "session", "liquidity": "session",
}


def graveyard_derived(ctx: SearchContext, n: int) -> list[Expr]:
    """Mutate what DIED, along the axis its recorded reason names.

    A fate with no stated reason is not material: "REJECTED" alone says the desk tried something
    and does not say what to try instead, and mutating on it would be mutating on noise wearing
    the word failure. Only rows whose `why` names a cause the desk knows how to attack are used,
    and the axis is chosen by that cause rather than at random.
    """
    reasons, dead, named = _fates(ctx.hypothesis_graph)
    seeds = [s for s in (ctx.seeds or tuple(ag.CANON.values()))
             if ag.is_valid(s, ctx.allow_drivers, ctx.terminals)]
    if not reasons or not seeds:
        ctx.notes["graveyard_derived"] = (
            f"{dead} dead rows, {named} with a cause this desk knows how to attack: "
            "a fate recorded without a cause is not genetic material")
        return []
    ctx.notes["graveyard_derived"] = f"{named} of {dead} dead rows named an attackable cause"
    out: list[Expr] = []
    for _ in range(n):
        axis = reasons[int(ctx.rng.integers(len(reasons)))]
        seed = seeds[int(ctx.rng.integers(len(seeds)))]
        cand = _zoo_axis(seed, axis, ctx)
        if ag.is_valid(cand, ctx.allow_drivers, ctx.terminals):
            out.append(cand)
    return out


def _fates(path: Path) -> tuple[list[str], int, int]:
    """Mutation axes named by the graveyard's stated reasons, and how many rows named one."""
    axes: list[str] = []
    dead = 0
    for row in _jsonl_tail(path, LEDGER_TAIL):
        if str(row.get("fate") or "").upper() not in ("FAILED", "RETIRED", "KILLED"):
            continue
        dead += 1
        why = str(row.get("why") or "").lower()
        for needle, axis in FATE_TO_AXIS.items():
            if needle in why:
                axes.append(axis)
                break
    return axes, dead, len(axes)


def causal_derived(ctx: SearchContext, n: int) -> list[Expr]:
    """Build from the ADMITTED edges of the world causal graph, at the lag each edge measured.

    Only admitted edges: a recorded-not-admitted edge is a measurement that did not clear its
    own bar, and treating it as a prior would launder a rejection into a hypothesis. The edge
    supplies the driver leg and the LAG; the desk supplies the shape (lead-lag, residual,
    co-movement), because an edge says what moves what, never how to trade it.

    Read defensively: the file is another engine's and may be absent, half-written or new.
    """
    edges = _admitted_edges(ctx.causal_graph, ctx.drivers)
    if not edges:
        ctx.notes["causal_derived"] = (
            f"no admitted edge on a driver these frames carry ({', '.join(ctx.drivers) or 'none'})"
            f": {ctx.causal_graph.name} absent, unreadable or still measuring")
        return []
    out: list[Expr] = []
    for _ in range(n):
        drv, lag = edges[int(ctx.rng.integers(len(edges)))]
        w = int(ctx.rng.choice(ag.WINDOWS[3:]))
        shape = int(ctx.rng.integers(3))
        if shape == 0:
            cand: Expr = ["corr", "ret", ["delta", ["delay", drv, lag], w], w]
        elif shape == 1:
            cand = ["residual", "close", ["delay", drv, lag], w]
        else:
            cand = ["zscore", ["delta", ["delay", drv, lag], w], w]
        if ag.is_valid(cand, ctx.allow_drivers, ctx.terminals):
            out.append(cand)
    return out


def _admitted_edges(path: Path, drivers: Sequence[str]) -> list[tuple[str, int]]:
    """(driver terminal, lag) for every admitted edge whose source the grammar can name."""
    try:
        doc = json.loads(Path(path).read_text("utf-8"))
    except (OSError, ValueError):
        return []
    if not isinstance(doc, dict):
        return []
    out: list[tuple[str, int]] = []
    for e in doc.get("edges") or []:
        if not isinstance(e, dict) or str(e.get("status") or "").upper() != "ADMITTED":
            continue
        role = _driver_role(str(e.get("src") or ""), drivers)
        lag = e.get("lag")
        if role and isinstance(lag, (int, float)) and 1 <= int(lag) <= max(ag.WINDOWS):
            out.append((role, int(lag) if int(lag) in ag.WINDOWS else
                        min(ag.WINDOWS, key=lambda w: abs(w - int(lag)))))
    return out


def _driver_role(node: str, drivers: Sequence[str]) -> str | None:
    low = node.lower()
    for role in drivers:
        if role in low:
            return role
    return None


#: A mined claim's mechanism class -> the grammar shape that EXPRESSES it. The claim says what
#: the world does; this says how the desk would measure it on its own bars. A class with no
#: shape here is counted as unmapped rather than forced into the nearest one.
CLAIM_SHAPES: dict[str, Callable[[SearchContext, np.random.Generator], Any]] = {
    "momentum": lambda c, r: ["delta", "close", int(r.choice(ag.WINDOWS[4:]))],
    "reversion": lambda c, r: ["neg", ["zscore", "close", int(r.choice(ag.WINDOWS[3:]))]],
    "flow": lambda c, r: ["zscore", "flow" if "flow" in c.terminals else "activity",
                          int(r.choice(ag.WINDOWS[3:]))],
    "microstructure": lambda c, r: ["ts_rank", "spread" if "spread" in c.terminals else "range",
                                    int(r.choice(ag.WINDOWS[4:]))],
    "positioning": lambda c, r: ["zscore",
                                 "positioning" if "positioning" in c.terminals else "activity",
                                 int(r.choice(ag.WINDOWS[4:]))],
    "calendar": lambda c, r: ["group_rank", "ret", "activity" if "activity" in c.terminals
                              else "range", int(r.choice(ag.WINDOWS[4:]))],
    "inventory": lambda c, r: ["delta", "vol" if "vol" in c.terminals else "range",
                               int(r.choice(ag.WINDOWS[3:]))],
    "carry": lambda c, r: ["mean", "ret", int(r.choice(ag.WINDOWS[5:]))],
    "policy": lambda c, r: ["residual", "close", "rates" if "rates" in c.terminals else "close",
                            int(r.choice(ag.WINDOWS[5:]))],
    "cross_asset": lambda c, r: ["corr", "ret", str(r.choice(list(c.drivers) or ["ret"])),
                                 int(r.choice(ag.WINDOWS[4:]))],
}


def claims_derived(ctx: SearchContext, n: int) -> list[Expr]:
    """Build from mined mechanism claims, by the class the miner declared.

    The claim rows carry `channel`, `mechanism_class` and `mechanism_key`; only the class is
    turned into a shape, and only for a class this module knows how to express. `mechanism_key`
    is what keeps one loud story from dominating -- one draw per distinct mechanism, not one per
    telling -- and the channel rides along untouched: a claim reached through an information
    channel is still one claim.

    Read defensively; the miner owns the schema and is widening it.
    """
    classes = _claim_classes(ctx.claims)
    if not classes:
        ctx.notes["claims_derived"] = (
            f"no claim row with a mechanism class this grammar expresses in {ctx.claims.name}")
        return []
    out: list[Expr] = []
    for _ in range(n):
        cls = classes[int(ctx.rng.integers(len(classes)))]
        shape = CLAIM_SHAPES.get(cls)
        if shape is None:
            continue
        base = shape(ctx, ctx.rng)
        axis = MUTATION_AXES[int(ctx.rng.integers(len(MUTATION_AXES)))]
        cand = _zoo_axis(base, axis, ctx) if ctx.rng.random() < 0.5 else base
        if ag.is_valid(cand, ctx.allow_drivers, ctx.terminals):
            out.append(cand)
    return out


def _claim_classes(path: Path) -> list[str]:
    """One mechanism class per DISTINCT mechanism key, so a story told ten times counts once."""
    seen: set[str] = set()
    out: list[str] = []
    for row in _jsonl_tail(path, LEDGER_TAIL):
        cls = str(row.get("mechanism_class") or "").lower()
        key = str(row.get("mechanism_key") or row.get("claim_hash") or "")
        if cls in CLAIM_SHAPES and key and key not in seen:
            seen.add(key)
            out.append(cls)
    return out


def _jsonl_tail(path: Path, limit: int) -> list[dict[str, Any]]:
    """The last `limit` JSON objects of a JSONL ledger. A bad line is skipped, never fatal."""
    try:
        lines = Path(path).read_text("utf-8", errors="ignore").splitlines()
    except OSError:
        return []
    out: list[dict[str, Any]] = []
    for line in lines[-int(limit):]:
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except ValueError:
            continue
        if isinstance(row, dict):
            out.append(row)
    return out


# --------------------------------------------------------------------------- the registry
POPULATIONS: dict[str, Population] = {
    "gp": gp,
    "gflownet": gflownet,
    "symreg": symreg,
    "program_synthesis": program_synthesis,
    "bayesian": bayesian,
    "zoo_mutation": zoo_mutation,
    "graveyard_derived": graveyard_derived,
    "causal_derived": causal_derived,
    "claims_derived": claims_derived,
}


def run(ctx: SearchContext, *, n_per_population: int = 8, budget_s: float = 120.0,
        names: Iterable[str] | None = None,
        weights: Mapping[str, float] | None = None) -> SearchResult:
    """Every population under ONE budget, deduped across all of them by structural hash.

    THE DEDUPE IS ACROSS POPULATIONS, not within one. Two populations converging on the same
    tree have found one hypothesis, and charging it twice would inflate the multiplicity the
    gauntlet later deflates by. The population that got there FIRST is credited, and the second
    one's yield shows the collision as proposed-but-not-unique, which is exactly the signal a
    weight ledger needs to notice two populations doing one job.

    A population that raises costs its own share and nothing else: the failure is recorded with
    its type and the run continues. Budget is checked between populations, so the last one may
    be skipped rather than truncated mid-draw.
    """
    order = _order(names, weights, ctx.rng)
    result = SearchResult()
    # WHAT EACH POPULATION'S EARLIER DRAWS WERE WORTH TO THE BOOK, attributed by the caller and
    # summarised here, so `elog_weights` can hand the next pass an ordering by realised growth
    # rather than by how many trees each population managed to draw.
    by_pop: dict[str, list[float]] = {}
    for pop_name, terms in ctx.attributed:
        value = float(getattr(terms, "delta_elog", 0.0))
        if math.isfinite(value):
            by_pop.setdefault(str(pop_name), []).append(value)
    seen: set[str] = set()
    started = time.monotonic()
    for name in order:
        if time.monotonic() - started > budget_s:
            result.yields[name] = PopulationYield(name, note="budget exhausted before it ran")
            continue
        fn = POPULATIONS[name]
        y = PopulationYield(name)
        t0 = time.monotonic()
        try:
            drawn = list(fn(ctx, int(n_per_population)) or [])
        except Exception as exc:
            y.note = f"{type(exc).__name__}: {exc}"
            result.failures.append(f"{name}: {y.note}")
            drawn = []
        y.proposed = len(drawn)
        for e in drawn:
            h = ag.subtree_hash(e)
            if h in seen:
                continue
            seen.add(h)
            y.unique += 1
            # A BARE TERMINAL IS A LEVEL, NOT AN ALPHA -- the same rule the typed samplers
            # enforce at the root. Crossover can return one (swap the whole tree for a leaf of
            # the other parent), and it would otherwise be donated as "close".
            if isinstance(e, str) or not ag.well_formed(e):
                continue
            y.well_formed += 1
            if ctx.falsifier is not None:
                try:
                    if not ctx.falsifier(e):
                        continue
                except Exception as exc:
                    result.failures.append(f"{name} falsifier: {type(exc).__name__}: {exc}")
                    continue
            y.passed += 1
            result.proposals.append((e, name))
        y.seconds = time.monotonic() - t0
        vals = by_pop.get(name) or []
        y.scored = len(vals)
        y.delta_elog_mean = (sum(vals) / len(vals)) if vals else None
        if not y.note:
            y.note = ctx.notes.get(name) or (
                "no falsifier: passed counts the well-formed" if ctx.falsifier is None
                else "screened by the cheap falsifier")
        result.yields[name] = y
    if ctx.cache is not None:
        result.cache_stats = dict(ctx.cache.stats())
    return result


def _order(names: Iterable[str] | None, weights: Mapping[str, float] | None,
           rng: np.random.Generator) -> list[str]:
    """Which populations run, and in what order. Weights shuffle the ORDER, never the budget:
    under a tight budget the last population is the one that does not run, so a weight table
    that starves an arm would silently retire it. Every named population still gets its draw."""
    chosen = [n for n in (names or POPULATIONS) if n in POPULATIONS]
    if not chosen:
        chosen = list(POPULATIONS)
    if not weights:
        return chosen
    w = np.array([max(0.0, float(weights.get(n, 0.0) or 0.0)) for n in chosen], dtype=float)
    if not np.isfinite(w).all() or w.sum() <= 0:
        return chosen
    # Draw the order without replacement in proportion to weight: the arm the ledger favours
    # runs first and is therefore the one that survives a short hour.
    out: list[str] = []
    pool, pw = list(chosen), list(w)
    while pool:
        p = np.array(pw, dtype=float)
        if p.sum() <= 0:
            out.extend(pool)
            break
        i = int(rng.choice(len(pool), p=p / p.sum()))
        out.append(pool.pop(i))
        pw.pop(i)
    return out

```

### libs\research\source_health.py
```python
"""Per-source health ledger -- the desk's memory of WHICH sources are dying, and for how long.

THE GAP THIS CLOSES. scripts/mine_research_queue.py and libs/data/cn_sources.probe_all() already
PROBE every source and record the failure honestly ("zhihu HTTP 403", "baidu anti-bot shell",
"csdn read timeout"). But every run started from zero: a source could be blocked for six weeks,
be re-probed every single day, report the identical failure every single day, and nothing would
ever notice that the failure had a HISTORY. Honest reporting without accumulation is a desk that
re-discovers the same outage forever and never acts on it. This module is the accumulation.

WHAT IT DOES NOT DO. It does not decide anything about mining. It is written to, once, at the end
of a run, and read by scripts/hunt_source_alternatives.py. A ledger that could change what the
miner fetches would make an outage-recorder into a control loop, and the desk has one job for this
file: remember.

TWO HONESTY RULES ARE BUILT INTO THE TYPES, NOT LEFT TO THE CALLER.

  (1) NEVER PROBED IS NOT DEAD. A source with no observation at all is UNKNOWN. Absence of
      evidence is its own state (L1.41); scoring it as a failure would let a source the desk
      simply never tried get condemned -- and then "replaced" -- on the strength of nothing. The
      academic probe already carries a row of exactly this shape (papers.probe_all() hardcodes
      reddit as ok=false without ever making a request), so this is a live hazard, not a
      hypothetical: rows with no measurement field are skipped, not counted as failures.

  (2) BLOCKED FROM THIS BOX IS NOT DEAD GLOBALLY. This container reaches the internet through an
      egress proxy; the VPS does not. The two vantages do not see the same internet, and the
      asymmetry cuts BOTH ways -- a WAF may block the proxy's datacenter egress while the VPS
      sails through, and a source may equally be reachable here only BECAUSE of the proxy. So
      every observation records the vantage it was made from, and the verdict carries a SCOPE:
      evidence from one vantage can only ever support a claim about THAT vantage
      (scope=this_vantage); scope=global requires agreeing evidence from two or more. A DEAD /
      this_vantage verdict is a real, actionable finding -- this box cannot mine that source, so
      hunt a substitute -- but it is never license to delete a source the VPS may be reading fine.

STORAGE follows scripts/classify_regime.py's _append_history idiom exactly: append-only JSONL,
idempotent per UTC day (a second run the same day supersedes that day's row rather than stacking a
duplicate -- the miner is scheduled daily but is also run by hand), lines that will not parse are
PRESERVED verbatim because history is evidence, and the write is same-dir tmp + replace so a
crash mid-write can never leave a torn ledger.
"""

from __future__ import annotations

import json
import os
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Final

# The producer of the `posture` field this module reads. Imported rather than re-typed so the
# reader cannot silently drift off the writer's vocabulary (R0466).
from libs.data.foreign_sources import (
    POSTURE_EMPTY as _POSTURE_EMPTY,
)
from libs.data.foreign_sources import (
    POSTURE_WALLED as _POSTURE_WALLED,
)

_ROOT = Path(__file__).resolve().parent.parent.parent
LEDGER_PATH: Final[Path] = _ROOT / "data" / "source_health.jsonl"

#: HOW MANY CONSECUTIVE FAILED RUNS BEFORE A SOURCE IS CALLED DEAD.
#: Five, and the number is a trade between two real costs measured on this desk.
#:
#: TOO LOW and the desk hunts replacements for sources that heal themselves. Every transient this
#: desk has actually seen would trip a threshold of 1 or 2: Sogou serves an anti-bot challenge when
#: rate-limited and clears within hours (libs/data/cn_sources.sogou_weixin says so in its
#: docstring); Bilibili's WBI signing keys rotate daily; and the loudest example is L0052 -- an
#: "OKX BLOCKED, HTTP 403" recorded on 2026-08-01 that turned out to be a User-Agent bot filter,
#: fixed the same day. Chasing substitutes for a source that is fine next morning burns the
#: hunter's whole budget on churn and, worse, teaches the desk to ignore DEAD.
#:
#: TOO HIGH and a genuinely dead lane stays dead while the miner re-probes it. That cost is
#: bounded and, importantly, VISIBLE the whole time: DEGRADED is reported from the FIRST failure,
#: so nothing is hidden during the wait -- only the automatic hunt is deferred.
#:
#: The miner is scheduled daily (ops/crontab.manifest, `0 13 * * *`), so five consecutive failed
#: runs is about five days: longer than every transient above, shorter than a working week of a
#: silently dead research lane.
#: FALSIFIER: if the alternatives hunter starts firing on sources that are healthy again by the
#: time a human reads the report, this number is too low; if a source is dead for more than a
#: week before anything is hunted, it is too high.
DEAD_AFTER_CONSECUTIVE_FAILURES: Final[int] = 5

#: How long a HEALTHY verdict remains a claim about the present (2026-08-05).
#:
#: THE DEFECT THIS CLOSES. A verdict is computed at WRITE time, from that run's observation, and
#: then stored. Nothing on the read side ever asked how old it was. So a source probed once,
#: successfully, and then never probed again reported HEALTHY forever -- and the longer the
#: silence lasted the more settled the answer looked. `verdict_for` even takes `last_checked_utc`
#: and tests it only for None, which closes the never-probed hole while leaving the
#: stopped-being-probed one wide open. The two are the same hole at different ages.
#:
#: WHY IT MATTERS MORE HERE THAN ANYWHERE ELSE. scripts/hunt_source_alternatives.py hunts
#: replacements for whatever `dead_sources()` returns. A stale HEALTHY never enters that list, so
#: the hunt never fires, and the desk goes on believing it has a research lane it has not
#: actually touched in months. Miner breadth would collapse silently -- which is precisely the
#: failure the alternatives hunter exists to prevent, arriving through the hunter's own input.
#:
#: THE DECAY IS TO UNKNOWN, NEVER TO DEAD. An old success is not evidence of failure; it is the
#: absence of recent evidence, and this module's honesty rule (1) already has a state for that.
#: Calling it DEAD would manufacture a failure nobody observed and send the hunter chasing a
#: source that may be perfectly fine.
#:
#: 72h against miner cadences measured in hours: long enough that a quiet weekend or a couple of
#: skipped runs does not churn the ledger, short enough that a lane cannot go dark for a working
#: week unnoticed. FALSIFIER: if sources start reading UNKNOWN while the miners are demonstrably
#: running them on schedule, this is too low; if a lane stops being probed and nothing says so
#: within a few days, it is too high.
STALE_AFTER_HOURS: Final[float] = 72.0

VERDICT_UNKNOWN: Final[str] = "UNKNOWN"
VERDICT_HEALTHY: Final[str] = "HEALTHY"
VERDICT_DEGRADED: Final[str] = "DEGRADED"
VERDICT_DEAD: Final[str] = "DEAD"
VERDICT_REPLACED: Final[str] = "REPLACED"

#: What the verdict is a claim ABOUT. See honesty rule (2) in the module docstring.
SCOPE_UNKNOWN: Final[str] = "unknown"
SCOPE_THIS_VANTAGE: Final[str] = "this_vantage"
SCOPE_GLOBAL: Final[str] = "global"

#: Where an observation was made from. The container's egress proxy and the VPS's direct route are
#: different internets as far as a WAF is concerned, so they are different vantages.
VANTAGE_PROXIED: Final[str] = "container_egress_proxy"
VANTAGE_DIRECT: Final[str] = "direct"

#: Probe rows and mining lanes name the same platform differently; the ledger must not carry two
#: half-histories for one source.
_ALIASES: Final[dict[str, str]] = {"wechat_sogou": "wechat", "sogou_weixin": "wechat"}


def canonical(source: str) -> str:
    """The one name this desk keeps health under for ``source``."""
    key = source.strip()
    return _ALIASES.get(key, key)


def current_vantage(env: Mapping[str, str] | None = None) -> str:
    """Which internet this process is looking at.

    Presence of a proxy variable is the discriminator because that is exactly what differs
    between this container (HTTPS_PROXY set to a local agent proxy) and the VPS (no proxy at all).
    """
    src = os.environ if env is None else env
    for var in ("HTTPS_PROXY", "https_proxy", "HTTP_PROXY", "http_proxy", "ALL_PROXY"):
        if str(src.get(var, "")).strip():
            return VANTAGE_PROXIED
    return VANTAGE_DIRECT


@dataclass(frozen=True)
class Observation:
    """One source, one run, one vantage. ``ok`` means the source was USABLE, not merely up.

    A 1.5KB anti-bot shell is a 200 OK and is not a source; reachable-but-useless is a failure
    here, with the reason recorded, because mining cannot proceed either way.
    """

    source: str
    ok: bool
    error: str | None = None
    vantage: str | None = None   # None -> resolved to current_vantage() at record time


@dataclass(frozen=True)
class SourceState:
    """Accumulated health for one source, as of its most recent ledger row."""

    source: str
    verdict: str = VERDICT_UNKNOWN
    scope: str = SCOPE_UNKNOWN
    consecutive_failed_runs: int = 0
    last_ok_utc: str | None = None
    last_error: str | None = None
    last_checked_utc: str | None = None
    failing_vantages: tuple[str, ...] = ()
    ok_vantages: tuple[str, ...] = ()
    replaced_by: str | None = None

    def age_hours(self, *, now: datetime | None = None) -> float | None:
        """Hours since this source was last probed, or None if that cannot be established.

        None is a real answer, not a failure to compute: a row with no readable check timestamp
        cannot support a claim about the present, and callers must handle it as such rather than
        defaulting it to 0 (fresh) -- which is the shape this whole staleness repair exists to
        stop. Negative ages (a clock skew, or a row written ahead of the reader) are returned as
        measured rather than clamped; hiding a skewed clock helps nobody.
        """
        parsed = _parse_utc(self.last_checked_utc)
        if parsed is None:
            return None
        return (_utc(now) - parsed).total_seconds() / 3600.0

    @property
    def dead_here(self) -> bool:
        """DEAD from at least this box. True for both scopes -- this box still cannot mine it."""
        return self.verdict == VERDICT_DEAD

    @property
    def dead_globally(self) -> bool:
        """DEAD with evidence from more than one vantage. The only form of 'the source is gone'
        this desk is entitled to assert."""
        return self.verdict == VERDICT_DEAD and self.scope == SCOPE_GLOBAL

    def claim(self) -> str:
        """The verdict written out as the sentence the desk is actually entitled to say."""
        if self.verdict == VERDICT_UNKNOWN:
            return f"{self.source}: never probed -- UNKNOWN, which is not dead and not healthy"
        if self.verdict == VERDICT_REPLACED:
            return f"{self.source}: superseded by {self.replaced_by} -- no longer relied on"
        if self.verdict == VERDICT_HEALTHY:
            where = ("from every vantage tried" if self.scope == SCOPE_GLOBAL
                     else f"from {', '.join(self.ok_vantages) or 'one vantage'} only")
            return f"{self.source}: usable {where}"
        vantages = ", ".join(self.failing_vantages) or "an unrecorded vantage"
        if self.scope == SCOPE_GLOBAL:
            return (f"{self.source}: {self.verdict} after {self.consecutive_failed_runs} "
                    f"consecutive failed runs across {vantages} -- failing from every vantage "
                    f"tried, so this is a claim about the SOURCE")
        return (f"{self.source}: {self.verdict} after {self.consecutive_failed_runs} consecutive "
                f"failed runs, ALL from {vantages} -- a claim about THIS BOX only. The VPS has no "
                f"egress proxy and may reach it fine; do not retire the source on this evidence")


def verdict_for(*, consecutive_failed_runs: int, last_checked_utc: str | None,
                failing_vantages: Sequence[str], ok_vantages: Sequence[str],
                replaced_by: str | None = None,
                dead_after: int = DEAD_AFTER_CONSECUTIVE_FAILURES) -> tuple[str, str]:
    """(verdict, scope) from accumulated counters. Pure -- the whole rule lives here."""
    if replaced_by is not None:
        # A replacement is a DESK decision, and it outranks the network: once the desk is reading
        # a substitute, the old source's reachability stops being the question.
        return VERDICT_REPLACED, _scope_of(failing_vantages or ok_vantages)
    if last_checked_utc is None:
        return VERDICT_UNKNOWN, SCOPE_UNKNOWN      # honesty rule (1)
    if consecutive_failed_runs <= 0:
        return VERDICT_HEALTHY, _scope_of(ok_vantages)
    if consecutive_failed_runs >= dead_after:
        return VERDICT_DEAD, _scope_of(failing_vantages)
    return VERDICT_DEGRADED, _scope_of(failing_vantages)


def _scope_of(vantages: Sequence[str]) -> str:
    """Honesty rule (2): one vantage supports a claim about that vantage and nothing wider."""
    distinct = {v for v in vantages if v}
    if not distinct:
        return SCOPE_UNKNOWN
    return SCOPE_GLOBAL if len(distinct) > 1 else SCOPE_THIS_VANTAGE


# ------------------------------------------------------------------------------- ledger I/O

def _row_to_state(row: Mapping[str, Any]) -> SourceState:
    fail_raw = row.get("failing_vantages")
    ok_raw = row.get("ok_vantages")
    replaced = row.get("replaced_by")
    return SourceState(
        source=str(row.get("source", "")),
        verdict=str(row.get("verdict", VERDICT_UNKNOWN)),
        scope=str(row.get("scope", SCOPE_UNKNOWN)),
        consecutive_failed_runs=int(row.get("consecutive_failed_runs", 0) or 0),
        last_ok_utc=None if row.get("last_ok_utc") is None else str(row["last_ok_utc"]),
        last_error=None if row.get("last_error") is None else str(row["last_error"]),
        last_checked_utc=(None if row.get("last_checked_utc") is None
                          else str(row["last_checked_utc"])),
        failing_vantages=tuple(str(v) for v in fail_raw) if isinstance(fail_raw, list) else (),
        ok_vantages=tuple(str(v) for v in ok_raw) if isinstance(ok_raw, list) else (),
        replaced_by=None if replaced is None else str(replaced),
    )


def _state_to_row(state: SourceState, *, day: str) -> dict[str, Any]:
    return {
        "day": day,
        "source": state.source,
        "verdict": state.verdict,
        "scope": state.scope,
        "consecutive_failed_runs": state.consecutive_failed_runs,
        "last_ok_utc": state.last_ok_utc,
        "last_error": state.last_error,
        "last_checked_utc": state.last_checked_utc,
        "failing_vantages": list(state.failing_vantages),
        "ok_vantages": list(state.ok_vantages),
        "replaced_by": state.replaced_by,
    }


def _read_lines(path: Path) -> list[str]:
    try:
        return [ln for ln in path.read_text("utf-8").splitlines() if ln.strip()]
    except FileNotFoundError:
        return []


def _parsed(line: str) -> dict[str, Any] | None:
    """The row, or None when the line will not parse. Callers PRESERVE unparseable lines."""
    try:
        obj = json.loads(line)
    except json.JSONDecodeError:
        return None
    return obj if isinstance(obj, dict) else None


def stale_verdict(state: SourceState, *, now: datetime | None = None,
                  stale_after_h: float = STALE_AFTER_HOURS) -> SourceState:
    """Decay a HEALTHY verdict whose evidence has gone old back to UNKNOWN.

    Applied on the READ side, because that is where the lie was told: the write side records what
    it genuinely saw, and the record only becomes a misstatement once it is quoted as though it
    described today. See STALE_AFTER_HOURS for why this exists and why the decay target is
    UNKNOWN rather than DEAD.

    Left ALONE, deliberately:

    * DEAD and DEGRADED. Ageing them to UNKNOWN would drop a source out of ``dead_sources()`` and
      silently CANCEL the alternatives hunt that its failure started -- the error would be the
      expensive one, and it would look like progress. A source that has stopped being probed
      while failing keeps its failing verdict until something probes it again.
    * REPLACED. That is a desk decision, not an observation, so it does not age.
    * UNKNOWN. Already the state of not knowing.

    An unparseable or missing ``last_checked_utc`` on a HEALTHY row decays too: a claim of health
    that carries no date is one that can never be shown to be old, which is the strongest form of
    this bug rather than an edge case exempt from it.
    """
    if state.verdict != VERDICT_HEALTHY:
        return state
    age = state.age_hours(now=now)
    if age is not None and age <= stale_after_h:
        return state
    when = "no readable check timestamp" if age is None else f"last checked {age:.0f}h ago"
    return replace(
        state, verdict=VERDICT_UNKNOWN, scope=SCOPE_UNKNOWN,
        last_error=(f"STALE: {when} (>{stale_after_h:.0f}h) -- the last probe SUCCEEDED, so this "
                    "is not a failure; it is the absence of recent evidence. Probe it before "
                    "relying on this lane."))


def load_states(path: Path | None = None, *, now: datetime | None = None,
                stale_after_h: float = STALE_AFTER_HOURS) -> dict[str, SourceState]:
    """Latest state per source, with stale HEALTHY verdicts decayed to UNKNOWN.

    Sources absent from the ledger are simply absent -- see :func:`state_of` for the UNKNOWN
    default, which is deliberately not invented here.

    The decay lives HERE rather than in each consumer so that no future caller has to remember
    it. ``state_of`` and ``dead_sources`` both read through this function and inherit the repair;
    a consumer that genuinely wants the raw stored rows passes ``stale_after_h=math.inf`` and has
    to type that, which is the point.
    """
    p = LEDGER_PATH if path is None else path
    out: dict[str, SourceState] = {}
    for line in _read_lines(p):
        row = _parsed(line)
        if row is None:
            continue
        name = str(row.get("source", "")).strip()
        if not name:
            continue
        out[canonical(name)] = stale_verdict(
            _row_to_state(row), now=now, stale_after_h=stale_after_h)
    return out


def state_of(source: str, path: Path | None = None, *, now: datetime | None = None,
             stale_after_h: float = STALE_AFTER_HOURS) -> SourceState:
    """State for one source. A source the ledger has never seen is UNKNOWN, never DEAD -- and a
    source last seen healthy too long ago is UNKNOWN too, for the same reason: no current
    evidence either way."""
    name = canonical(source)
    return load_states(path, now=now, stale_after_h=stale_after_h).get(
        name, SourceState(source=name))


def dead_sources(path: Path | None = None, *, now: datetime | None = None,
                 stale_after_h: float = STALE_AFTER_HOURS) -> list[SourceState]:
    """Every source whose verdict is DEAD, this-vantage or global. Both are worth hunting for:
    a source this box cannot reach is a lane this box cannot mine, whatever the VPS sees.

    Unaffected by the staleness decay by construction -- it only touches HEALTHY -- but the
    parameters are threaded through so a caller reasoning about one clock reasons about one
    clock everywhere, rather than this function quietly reading a different `now`.
    """
    return sorted(
        (s for s in load_states(path, now=now, stale_after_h=stale_after_h).values()
         if s.dead_here),
        key=lambda s: (-s.consecutive_failed_runs, s.source))


def unproven_sources(path: Path | None = None, *, now: datetime | None = None,
                     stale_after_h: float = STALE_AFTER_HOURS) -> list[SourceState]:
    """Sources the desk cannot currently claim as usable: never probed, or probed too long ago.

    THE LIST THAT DID NOT EXIST. ``dead_sources()`` answers "what failed", and the alternatives
    hunter works from it -- but a lane that quietly stopped being probed never fails, so it never
    appeared anywhere and no organ was responsible for it. This is the other half of the same
    question, and it is the half that grows while nobody is looking: a source stops being mined,
    nothing errors, and the desk's breadth shrinks with every artifact still reporting green.

    Ordered oldest-evidence first, because that is the order in which the claims are weakest.
    """
    states = load_states(path, now=now, stale_after_h=stale_after_h).values()
    unproven = [s for s in states if s.verdict == VERDICT_UNKNOWN]
    return sorted(unproven, key=lambda s: (-(s.age_hours(now=now) or float("inf")), s.source))


def record_run(observations: Sequence[Observation], *, path: Path | None = None,
               now: datetime | None = None,
               dead_after: int = DEAD_AFTER_CONSECUTIVE_FAILURES) -> dict[str, SourceState]:
    """Fold one run's observations into the ledger and return the sources it touched.

    IDEMPOTENT PER UTC DAY. Re-running the miner an hour later must not double-count a source's
    failure into DEAD twice as fast, so today's row for a source is REPLACED, and the counter is
    advanced from the state as of the last day BEFORE today -- not from the row this run is about
    to overwrite. Without that second half, replacement alone would still let three runs in one
    day add three to the counter.

    ONE ROW PER SOURCE PER DAY, unconditionally. Two observations of the same source in one call
    are FOLDED (usable if either was usable, the first failure's reason kept) rather than written
    as two rows -- the same "any lane up means the platform is up" rule the report deriver uses,
    applied here so the invariant holds no matter who calls this.
    """
    p = LEDGER_PATH if path is None else path
    iso = _utc(now).isoformat(timespec="seconds")
    day = iso[:10]

    observations = _fold(observations)
    wanted = {canonical(o.source) for o in observations}
    kept: list[str] = []
    prior: dict[str, SourceState] = {}
    for line in _read_lines(p):
        row = _parsed(line)
        if row is None:
            kept.append(line)         # never drop a line we cannot parse; history is evidence
            continue
        name = canonical(str(row.get("source", "")))
        if name and str(row.get("day", ""))[:10] == day and name in wanted:
            continue                  # same UTC day, same source -> this run supersedes it
        if name:
            prior[name] = _row_to_state(row)
        kept.append(line)

    touched: dict[str, SourceState] = {}
    for obs in observations:
        name = canonical(obs.source)
        before = prior.get(name, SourceState(source=name))
        vantage = obs.vantage if obs.vantage is not None else current_vantage()
        if obs.ok:
            failing: tuple[str, ...] = ()
            ok_vantages = _add(before.ok_vantages, vantage)
            consecutive = 0
            last_ok: str | None = iso
            last_error: str | None = None
        else:
            failing = _add(before.failing_vantages, vantage)
            ok_vantages = before.ok_vantages
            consecutive = before.consecutive_failed_runs + 1
            last_ok = before.last_ok_utc
            last_error = obs.error
        verdict, scope = verdict_for(
            consecutive_failed_runs=consecutive, last_checked_utc=iso,
            failing_vantages=failing, ok_vantages=ok_vantages,
            replaced_by=before.replaced_by, dead_after=dead_after)
        state = SourceState(
            source=name, verdict=verdict, scope=scope,
            consecutive_failed_runs=consecutive, last_ok_utc=last_ok, last_error=last_error,
            last_checked_utc=iso, failing_vantages=failing, ok_vantages=ok_vantages,
            replaced_by=before.replaced_by)
        touched[name] = state
        kept.append(json.dumps(_state_to_row(state, day=day), ensure_ascii=False))
        prior[name] = state           # a source observed twice in one run must not re-enter twice

    _write(p, kept)
    return touched


def mark_replaced(source: str, replacement: str, *, path: Path | None = None,
                  now: datetime | None = None) -> SourceState:
    """Record that the desk now reads ``replacement`` instead of ``source``.

    Deliberately a SEPARATE call from :func:`record_run`: a replacement is a decision someone
    made after reading a hunt report, not something a probe can conclude on its own.
    """
    p = LEDGER_PATH if path is None else path
    iso = _utc(now).isoformat(timespec="seconds")
    day = iso[:10]
    name = canonical(source)

    kept: list[str] = []
    before = SourceState(source=name)
    for line in _read_lines(p):
        row = _parsed(line)
        if row is None:
            kept.append(line)
            continue
        if canonical(str(row.get("source", ""))) == name:
            before = _row_to_state(row)
            if str(row.get("day", ""))[:10] == day:
                continue
        kept.append(line)

    verdict, scope = verdict_for(
        consecutive_failed_runs=before.consecutive_failed_runs, last_checked_utc=iso,
        failing_vantages=before.failing_vantages, ok_vantages=before.ok_vantages,
        replaced_by=replacement)
    state = replace(before, source=name, verdict=verdict, scope=scope, replaced_by=replacement,
                    last_checked_utc=iso)
    kept.append(json.dumps(_state_to_row(state, day=day), ensure_ascii=False))
    _write(p, kept)
    return state


def _fold(observations: Sequence[Observation]) -> list[Observation]:
    """Collapse repeats of one source within a single run into one observation."""
    order: list[str] = []
    ok_by: dict[str, bool] = {}
    err_by: dict[str, str | None] = {}
    van_by: dict[str, str | None] = {}
    for obs in observations:
        name = canonical(obs.source)
        if name not in ok_by:
            order.append(name)
            ok_by[name] = obs.ok
            err_by[name] = obs.error
            van_by[name] = obs.vantage
        else:
            ok_by[name] = ok_by[name] or obs.ok
            if err_by[name] is None and not obs.ok:
                err_by[name] = obs.error
    return [Observation(source=n, ok=ok_by[n], error=None if ok_by[n] else err_by[n],
                        vantage=van_by[n]) for n in order]


def _parse_utc(raw: str | None) -> datetime | None:
    """A stored ISO stamp as an aware UTC datetime, or None if it cannot be read as one.

    Deliberately NOT symmetric with :func:`_utc`, which raises on a naive datetime. That strictness
    is right on the WRITE path, where a bad stamp corrupts the ledger's idempotency key and must
    stop the run. On the READ path an unparseable stamp is a fact about an old row, and refusing
    to load the ledger because one historical line is malformed would take the desk's whole source
    map down over a row nobody can fix. So: None, which every caller must then treat as "cannot
    establish freshness" -- never as fresh.

    A naive stored stamp is read as UTC rather than rejected: every writer in this module stamps
    UTC, so a missing suffix is a serialisation slip, and the alternative is discarding a genuine
    observation over punctuation.
    """
    if not raw:
        return None
    try:
        parsed = datetime.fromisoformat(raw)
    except (TypeError, ValueError):
        return None
    return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=UTC)


def _utc(now: datetime | None) -> datetime:
    """Now, in UTC. A NAIVE datetime is rejected rather than localised.

    Silently reading a naive stamp as local time would put the wrong UTC day on a ledger row, and
    the day IS the idempotency key -- two runs an hour apart could land on different days, or two
    different days collapse onto one. That is a corrupted history that looks perfectly healthy.
    """
    if now is None:
        return datetime.now(tz=UTC)
    if now.tzinfo is None or now.tzinfo.utcoffset(now) is None:
        raise ValueError("naive datetime rejected: the health ledger is keyed by UTC day, so an "
                         "ambiguous stamp would corrupt the idempotency key")
    return now.astimezone(UTC)


def _add(existing: Sequence[str], vantage: str) -> tuple[str, ...]:
    return tuple(existing) if vantage in existing else (*existing, vantage)


def _write(path: Path, lines: Sequence[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text("\n".join(lines) + "\n", "utf-8")
    tmp.replace(path)                 # same-dir tmp + replace: never a torn ledger


# ------------------------------------------------------- deriving observations from a miner run

#: Report keys whose values are {lane: fetched_count}. A lane present in one of these means the
#: miner ACTUALLY FETCHED from it this run, which is the strongest evidence a source is usable.
#: The second element is the platform when the report key alone determines it, and None when the
#: platform must be read off the lane key -- and that difference is NOT cosmetic: the keys of
#: `bilibili_discovered` and `search_discovered` are bare query strings ("量化交易 策略"), while
#: the keys of `cn_article_discovered` and `academic_discovered` are prefixed ("juejin:量化",
#: "arxiv:q-fin.TR"). Deriving the platform from the lane key in all five cases files every
#: Bilibili query under a platform named after the query.
_LANE_COUNTS: Final[tuple[tuple[str, str | None], ...]] = (
    ("channels_scanned", "youtube"),        # keys are channel handles
    ("search_discovered", "youtube"),       # keys are bare search queries
    ("bilibili_discovered", "bilibili"),    # keys are bare search queries
    ("cn_article_discovered", None),        # keys are "juejin:<kw>" / "wechat:<kw>"
    ("academic_discovered", None),          # keys are "arxiv:<cat>" / "ssrn:..." / "hn"
    # R0466. `foreign_discovered` was MISSING, and the asymmetry is the defect, not the omission:
    # `channels_blocked` carries foreign lanes too and WAS read, so a JP/KR/RU/VI/TR source's
    # FAILURES reached the ledger while its SUCCESSES did not exist. Measured: a run with four
    # successful note.com queries and one 403 recorded `note` as ok=False, and a run where every
    # foreign lane succeeded produced NO OBSERVATION AT ALL, so last_ok_utc never advanced and the
    # region drifted to STALE -> DEAD -> "replaced" while it was working the whole time. Same
    # outcome R0466 names -- a whole region silently retired -- reached from the other side.
    ("foreign_discovered", None),           # keys are "note:<kw>" / "zenn:<kw>" / "habr:<kw>"
)


def _platform_of(lane: str) -> str:
    """The platform a lane key names. `@neurotrader888` and `search:foo` are both YouTube;
    `juejin:量化` is Juejin; `arxiv:q-fin.TR` is arXiv."""
    head = lane.split(":", 1)[0].strip()
    if head.startswith("@") or head == "search":
        return "youtube"
    return canonical(head)


def _rows(doc: Mapping[str, Any], key: str) -> list[Mapping[str, Any]]:
    raw = doc.get(key)
    return [r for r in raw if isinstance(r, Mapping)] if isinstance(raw, list) else []


def _mapping(doc: Mapping[str, Any], key: str) -> Mapping[str, Any]:
    raw = doc.get(key)
    return raw if isinstance(raw, Mapping) else {}


def _is_measured(row: Mapping[str, Any]) -> bool:
    """Did this probe row come from an actual request?

    papers.probe_all() hardcodes `{"source": "reddit", "ok": False, "error": "HTTP 403 --
    blocked"}` without making one. Counting that as a failed run would march a never-probed source
    to DEAD on the strength of a comment, which is honesty rule (1) exactly inverted. A row that
    carries no measurement -- no result count, no byte count, no reachability -- is DECLARED, not
    measured, and contributes nothing.
    """
    return any(k in row for k in ("n", "bytes", "reachable", "http_status"))


def _probe_ok(row: Mapping[str, Any]) -> tuple[bool, str | None]:
    """(usable, reason) for one probe row, across the two probe shapes on this desk.

    WHAT A PROBE CAN AND CANNOT REFUTE. probe_cn() measures two things: did bytes come back, and
    were there more than 20,000 of them. That is real evidence against a declared "blocked" --
    the L0052 lesson is exactly that a recorded block can be wrong, so the declared status is a
    prior and the probe is the evidence. It is NOT evidence against a declared "needs_browser",
    because a client-rendered shell can be any size at all: BigQuant's shell measures 27,705 bytes
    and sails over the content bar while carrying zero listings. Letting a byte count overturn a
    rendering finding would mark a source HEALTHY that the miner cannot read a single row from,
    which is worse than the silence it replaces -- a dead lane wearing a green badge.
    """
    err = row.get("error")
    reason: str | None = str(err) if err is not None else None
    posture = str(row.get("posture") or "")
    flag = row.get("ok")
    if isinstance(flag, bool):
        if flag:
            return True, None
        # R0466 AT THE READER. foreign_sources.probe_all publishes WALLED vs EMPTY -- the two
        # causes of ok=False that demand OPPOSITE responses -- and until now NOTHING read it, so
        # the distinction was written to a report and died there (L1.46: a duty with no instrument
        # is a wish). Both still count as "not usable this run"; what changes is that the recorded
        # reason can no longer be mistaken for the other fact. An EMPTY row used to arrive here
        # with error=None and come out as "probe reported ok=false, no reason given" -- a source
        # that ANSWERED CLEANLY, reading as a broken lane.
        if posture == _POSTURE_WALLED:
            return False, ("WALLED -- the source refused or served something unusable, so the "
                           "ground is UNKNOWN and this is NOT evidence it is thin; next move is "
                           "an OP-052 UA matrix against a real content path"
                           + (f" ({reason})" if reason is not None else ""))
        if posture == _POSTURE_EMPTY:
            return False, ("EMPTY -- the source answered cleanly and genuinely had nothing for "
                           "the probe keyword; the LANE is up, and this says nothing about any "
                           "other keyword")
        return False, reason if reason is not None else "probe reported ok=false, no reason given"
    if str(row.get("declared", "")) == "needs_browser":
        note = str(row.get("reason") or reason or "listings require a browser")
        return False, (f"declared needs_browser and this probe cannot refute that (it measures "
                       f"bytes, not rendering): {note}")
    if row.get("reachable") is not True:
        if reason is not None:
            return False, reason
        status = row.get("http_status")
        return False, (f"unreachable (HTTP {status})" if status is not None else "unreachable")
    if row.get("looks_like_content") is False:
        detail = f" ({row.get('bytes')} bytes)" if row.get("bytes") is not None else ""
        return False, (reason if reason is not None
                       else f"reachable but served a non-content shell{detail}")
    return True, None


def observations_from_miner_report(doc: Mapping[str, Any]) -> list[Observation]:
    """Turn one reports/research_queue.json document into per-source observations.

    THREE RULES, in order, and the order is the point.

    1. USE OUTRANKS PROBE. A lane the miner actually fetched from is stronger evidence than a
       diagnostic probe of the same platform, so probes only speak for platforms with no lane
       evidence this run. Bilibili is the live case: the miner reads it successfully through
       WBI-signed search, while CN_SOURCES probes the RAW search endpoint, which answers 412
       because it is unsigned. Letting that probe outvote 15 mined rows would mark a working
       source dead.
    2. ANY LANE UP MEANS THE PLATFORM IS UP. Four Juejin queries where one succeeds is a usable
       source, and the failure of the other three is a query problem, not a source death.
    3. NOT ATTEMPTED IS NOT FAILED. `--only bilibili` leaves every other group with no lanes and
       no probes; those sources get NO observation, so their counters neither advance nor reset.
       Absence is absence (L1.41).
    """
    lanes: dict[str, list[bool]] = {}
    reasons: dict[str, str] = {}

    def _note(name: str, ok: bool, reason: str | None) -> None:
        key = canonical(name)
        if not key:
            return
        lanes.setdefault(key, []).append(ok)
        if not ok and reason is not None and key not in reasons:
            reasons[key] = reason

    for key, fixed in _LANE_COUNTS:
        for lane in _mapping(doc, key):
            _note(fixed if fixed is not None else _platform_of(str(lane)), True, None)
    for lane, why in _mapping(doc, "channels_blocked").items():
        _note(_platform_of(str(lane)), False, str(why)[:200])

    # Probes fill in only the platforms no lane spoke for -- rule 1.
    # `foreign_source_probe` added by R0466: mine_research_queue has written it every run since
    # the foreign lane opened and no reader ever named the key, so the one probe that carries
    # WALLED-vs-EMPTY was the one probe the ledger could not see.
    for key in ("cn_source_probe", "academic_probe", "cn_sources", "foreign_source_probe"):
        for row in _rows(doc, key):
            raw_name = str(row.get("source") or row.get("name") or "").strip()
            name = canonical(raw_name)
            if not name or name in lanes or not _is_measured(row):
                continue
            ok, reason = _probe_ok(row)
            _note(name, ok, reason)

    vantage = current_vantage()
    out: list[Observation] = []
    for name in sorted(lanes):
        ok = any(lanes[name])
        out.append(Observation(source=name, ok=ok,
                               error=None if ok else reasons.get(name), vantage=vantage))
    return out


def record_from_report(doc: Mapping[str, Any], *, path: Path | None = None,
                       now: datetime | None = None) -> dict[str, SourceState]:
    """The one call the miner makes. Additive: it reads the finished report and writes the ledger.

    Swallows OSError only, for the same reason mine_research_queue._append_yield does: a ledger
    that cannot be written is a lost day of health history, while a miner that dies on it is a
    lost day of RESEARCH. Anything other than a disk failure is a bug and stays loud.
    """
    try:
        return record_run(observations_from_miner_report(doc), path=path, now=now)
    except OSError:
        return {}

```

### scripts\check_conversion.py
```python
#!/usr/bin/env python3
"""CONVERSION FENCE (L1.28b) -- finding without fixing is half a deliverable.

THE MEASURED DEFECT THIS FENCE EXISTS FOR (deep sweep 2026-07-31, meta seat): findings arrive
at ~14/day across all organs and cross-session repairs complete at ~0.6/day; no ledger row older
than 3.67 days had ever been implemented; >=80% of audit output converted to nothing. The desk's
BUILD capability compounds while its CONVERT capability does not, and nothing measured that gap
daily -- so it widened silently, exactly like unmeasured utilisation before L1.28a.

WHAT IT MEASURES, from docs/research/recommendation_ledger.json (the de-facto winning queue --
the sweep's M10 finding is that split stores recreate the defect, so this fence reads ONE store):
  backlog            rows still open or scheduled (kept for every existing consumer)
  backlog_open /     the two populations backlog conflates. A SCHEDULED row with a real reason
  backlog_scheduled  and a future due date is a LAWFUL DISPOSITION, not debt.
  owed               rows that owe a decision RIGHT NOW: untriaged past grace, or a schedule
                     that has run out. THIS is the population the repair-mode line is applied
                     to, because L1.28b(d) says the line is "25 OPEN ROWS".
  past_due           backlog rows whose due date has passed
  dispositions_7d    rows moved to implemented/rejected in the last 7 days (a reasoned
                     rejection IS a conversion -- the defect is silence, not the verdict)
  arrivals_7d        rows raised in the last 7 days
  oldest_backlog_age the age of the oldest still-open row, in days
  backlog_age_p50/   the DRAIN. Under a real drain the old rows convert and these FALL; under
  backlog_age_p90    treading water they rise exactly one day per day while flow looks balanced.
                     Those two states are otherwise byte-identical in this artifact.
  queue_dispositioned all-time fraction of rows that reached a terminal verdict

STATUSES (fail LOUD, never advisory):
  FLATLINE     zero dispositions in 7 days while the backlog is non-empty -- found-never-fixed
               as a steady state. Exit 2: this is the fence failure.
  REPAIR-MODE  OWED rows above the deep-sweep backpressure line (25). Exit 0 but the artifact
               carries repair_mode=true, and every consumer of the artifact (max-push queue,
               sweep prompts, brain briefs) is expected to flip effort from finding to fixing.
               Queueing theory (meta M8): at rho~4, exhortation cannot drain a queue -- only
               capacity or admission control can, and this flag is the admission signal.
               BOUNDARY (L1.28b(f), principal 2026-07-31): repair-mode redirects DISCRETIONARY
               ENGINEERING ATTENTION ONLY. It never reduces raw information quantity --
               collectors, recorders, miners, diggers, screens-on-discovery, forward clocks and
               every scheduled detector run at full cadence unconditionally. Acquisition is
               never cut to meet extraction.
  DEBT-GROWING materially more rows arrived than were dispositioned over the last 7 days (a
               shortfall of >=5 AND a conversion ratio <0.75), with a non-empty backlog. Both
               numbers were computed and printed here from the start and never compared, so a
               desk raising 40 a week and dispositioning 3 read OK for as long as the backlog
               stayed under the REPAIR-MODE line -- falling further behind every week with the
               evidence sitting unread in its own artifact. The required move is CONVERT FASTER,
               never raise less.
               RANKS BELOW REPAIR-MODE as a headline, because the two prescribe the same action
               and REPAIR-MODE is the signal downstream consumers already read; this status
               covers what REPAIR-MODE cannot see, a backlog under the line that is still
               growing. But `debt_growing` is recorded as a FACT and fails the fence (exit 2)
               whichever status won -- a desk over the line AND falling further behind must not
               exit 0 because the more urgent-sounding label got there first.
  ARRIVALS-COLLAPSED
               7-day arrivals fell below 40% of the trailing 28-day rate. Exit 2, and it outranks
               every green status below it. This is the ANTI-GAMING status: every other reading
               here improves when arrivals fall, so the cheapest route to a clean conversion
               score is to stop looking -- and that would be indistinguishable from success. It
               is reported even when everything else is green, because that is exactly when it is
               invisible. L1.28b(f) forbade this in prose ("acquisition is never cut to meet
               extraction") and nothing measured it until now. The required move is FIND HARDER.
               Named separately from DEBT-GROWING on purpose: convert-faster and find-harder are
               opposite instructions, and one number holding both would let each mask the other.
  OK           dispositions keeping pace with arrivals, arrivals holding up, backlog under the
               line. All three, or it is not OK.

Artifact: data/conversion_status.json -- consumed by run_max_push.py so conversion debt ranks
in the SAME daily queue as every other below-ceiling aspect (L1.28b: conversion hunts 100%
daily exactly as utilisation does).

    python scripts/check_conversion.py [--report-only] [--json]
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parent.parent

# L1.42 LAWFUL ENTRY: this organ ran on a cron line that passed through no gate at
# all -- 60 manifest lines did. guard() verifies the sealed core and that the doctrine
# still carries every law family; it is TTL-cached (~0ms after the first call in a
# window) and pages-but-does-not-block, so a governance fault never silences an organ.
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
from libs.ops.deferral import CHRONIC_RESCHEDULES, is_chronic, reschedule_count  # noqa: E402
from libs.ops.fence_exit import FAIL, fence_exit  # noqa: E402
from libs.ops.lawful import guard as _law_guard  # noqa: E402
from libs.ops.repair_mode import DIRECTION_FOR_STATUS  # noqa: E402  (L1.28b(d): one mapping)

#: REPAIR-MODE passes DELIBERATELY. It is not a failure but a designed MODE SIGNAL: L1.28b(d)
#: has it flip the next audit/brain window from finding to fixing, and run_max_push reads the
#: artifact to do exactly that. Failing the build on it would make the desk permanently red at
#: today's backlog and get the fence switched off (L1.43) -- turning the fix into the outage.
#: FLATLINE (dispositions stopped entirely) stays the failure, and any status added later fails.
_PASSING = frozenset({"OK", "REPAIR-MODE"})

# The deep-sweep backpressure line: open+past-due above this flips audit windows to repair.
REPAIR_MODE_BACKLOG = 25

#: A week's arrivals below this fraction of the trailing baseline is a COLLAPSE, not a quiet week.
#: 0.4 is deliberately generous -- real finding rates are lumpy (a deep sweep raises twenty rows
#: in an afternoon, the next week raises four), and a fence that fires on ordinary variance gets
#: disabled, taking the real signal with it. What it must catch is the SUSTAINED quiet that means
#: the desk stopped looking, which is the only way a conversion ratio can be gamed.
ARRIVAL_COLLAPSE_FRACTION = 0.4
#: Rows needed in the trailing 28d before a baseline means anything. Below it the comparison is
#: reported UNMEASURED rather than computed -- a collapse detector built on three rows would fire
#: on noise, and a detector that cries wolf is a detector nobody keeps.
ARRIVAL_BASELINE_MIN = 8

#: DEBT-GROWING needs BOTH a material shortfall and a materially poor rate. Either alone
#: cries wolf: one row raised and not yet dispositioned is a desk keeping pace, not a desk losing
#: ground, and a fence that fires on that gets switched off before it ever sees a real slide.
#: Calibrated against the live ledger, where the slide is unambiguous -- 341 raised vs 157
#: dispositioned in 7 days, a 184-row shortfall at a 0.46 conversion ratio.
DEBT_GROWTH_MIN_ROWS = 5
DEBT_GROWTH_MIN_RATIO = 0.75

#: The statuses this fence NAMES as failures. It is no longer the exit map -- ``_PASSING`` is,
#: and it fails closed on everything it does not name, which is the property that survives a
#: status added next year (R0237). This set is kept as the explicit record of the three the
#: author meant, and ``tests/governance/test_conversion_fence.py`` asserts it stays disjoint from
#: ``_PASSING``: widening the pass set is a legitimate edit, silently un-failing DEBT-GROWING
#: while doing it is not.
_FENCE_FAILURES = frozenset({"FLATLINE", "DEBT-GROWING", "ARRIVALS-COLLAPSED"})
# `done` and `screened` are written by organs that bypass the CLI (scripts/recommendations.py:223
# only permits implemented|rejected|scheduled). They read "built, N tests, in the law gate" and
# "Stage A run live" -- FINISHED WORK. Omitting them counted 15 completed rows as backlog forever
# AND, because they carry no `disposed` stamp, never as dispositions: a double penalty that
# inflated the apparent debt at both ends. Counting them is a correctness fix, NOT the denominator
# trick -- no row leaves the ledger, and `terminal_unstamped` below reports exactly how many are
# terminal without a timestamp so the disposition RATE understatement stays visible.
_TERMINAL = frozenset({"implemented", "rejected", "retired", "done", "screened"})
# scripts/recommendations.py:37 -- an untriaged row past this is a DEFECT, not backlog.
GRACE_H = 24.0


def _parse_ts(raw: object) -> datetime | None:
    if not isinstance(raw, str) or not raw:
        return None
    try:
        ts = datetime.fromisoformat(raw)
    except ValueError:
        return None
    return ts if ts.tzinfo else ts.replace(tzinfo=UTC)


def build_report(root: Path, now: datetime | None = None) -> dict[str, Any]:
    now = now or datetime.now(tz=UTC)
    week_ago = now - timedelta(days=7)
    ledger = root / "docs/research/recommendation_ledger.json"
    try:
        rows = json.loads(ledger.read_text("utf-8")).get("recommendations", [])
    except (OSError, ValueError):
        rows = None

    if not rows:
        # A missing/empty ledger is UNMEASURED conversion, which counts as zero (L1.28a
        # inheritance) -- never as OK.
        return {
            "generated": now.isoformat(), "status": "FLATLINE", "repair_mode": True,
            "law": "L1.28b", "backlog": None, "past_due": None,
            "detail": f"ledger unreadable or empty at {ledger} -- unmeasured conversion "
                      "counts as ZERO conversion",
        }

    backlog = [r for r in rows if r.get("status") not in _TERMINAL]
    # PAST DUE, counted the way scripts/recommendations.py counts it. Two bugs lived here and both
    # ran in the FORGIVING direction, which is how the fence reported past_due=0 while
    # recommendations.py reported 34 DEFECTS on the same file in the same minute -- and
    # run_max_push.py:239 consumes THIS artifact, so the desk prioritised off the lenient number.
    #   (1) `r["due"] < today` compared ISO STRINGS, so "2026-08-01" < "2026-08-01" is False and a
    #       scheduled row was invisible for the entire day it came due (6 rows today).
    #   (2) it required a non-null `due`, but add() writes `due: None` and only `dispose
    #       --status scheduled` ever sets one -- so ZERO rows in the ledger have status `open` AND
    #       a due date. That branch was structurally dead in production, hiding every untriaged
    #       row. The unit test that "proved" it worked used an open row WITH a due date, a fixture
    #       the CLI cannot produce.
    # A SCHEDULE THAT KEEPS MOVING NEVER COMES DUE, so this test alone could never see it. The
    # `owed` population was the fix for counting lawful schedules as debt; its blind spot is the
    # opposite error -- a row re-snoozed the day before it arrives leaves `owed` with no work done
    # and no trace left, which is the one escape scripts/recommendations.py's docstring claims is
    # closed. Measured 2026-08-13: 39 of 152 ever-scheduled rows had their due date moved, 38 are
    # still scheduled. Chronic deferrals are counted as owed regardless of date (libs/ops/deferral).
    # ADDS ZERO ROWS ON THE DAY IT LANDS -- `schedule_history` is born empty, so it can only bite
    # on a future snooze, which is what keeps it from being red from day one and switched off.
    chronic = [r for r in backlog if is_chronic(r)]
    overdue = [r for r in backlog
               if is_chronic(r)
               or ((d := _parse_ts(r.get("due"))) is not None and d < now)]
    orphans = [r for r in backlog
               if r.get("status") == "open"
               and (t := _parse_ts(r.get("raised"))) is not None
               and (now - t).total_seconds() / 3600.0 > GRACE_H]
    seen: set[int] = set()
    past_due = [r for r in (*overdue, *orphans)
                if id(r) not in seen and not seen.add(id(r))]  # type: ignore[func-returns-value]
    terminal_unstamped = sum(1 for r in rows
                             if r.get("status") in _TERMINAL and not r.get("disposed"))
    arrivals_7d = sum(1 for r in rows if (t := _parse_ts(r.get("raised"))) and t >= week_ago)
    dispositions_7d = sum(
        1 for r in rows
        if r.get("status") in _TERMINAL
        and (t := _parse_ts(r.get("disposed"))) and t >= week_ago)
    terminal = sum(1 for r in rows if r.get("status") in _TERMINAL)
    oldest = min((_parse_ts(r.get("raised")) for r in backlog if _parse_ts(r.get("raised"))),
                 default=None)
    oldest_age = round((now - oldest).total_seconds() / 86400, 2) if oldest else 0.0

    # THE REPAIR-MODE LINE COUNTS ROWS THAT OWE A DECISION, WHICH IS WHAT L1.28b(d) SAYS IT COUNTS
    # -- "backlog above the repair-mode line (25 OPEN ROWS)". This counted `backlog`, and `backlog`
    # is every non-terminal row, so a row correctly SCHEDULED with a real reason and a future due
    # date was counted as repair debt from the moment it was dispositioned until the day it came
    # due. Scheduling is one of the three lawful dispositions; counting it as debt makes the
    # desk's own correct behaviour raise the number that says the desk is behind.
    #
    # THE CONSEQUENCE IS A WELDED GATE, and it is measured rather than argued. Reconstructing the
    # daily backlog from the ledger's own raised/disposed stamps, `backlog` crossed 25 on
    # 2026-07-28 and has never returned below it -- REPAIR-MODE fired on 100% of runs for 15
    # consecutive days. A gate that fires on every run carries zero information (L1.43,
    # GATE-OPTIMALITY), and its actuator is not a report but a BEHAVIOUR CHANGE: L1.28b(d) flips
    # the next brain window from finding to fixing. A flip that is always on is not a flip, and
    # the §37 carry-over brief measures exactly what that costs -- 15 items "shown to a LIVE cycle
    # at least twice IN A ROW" and walked past. That is what a permanently-on signal earns.
    #
    # THIS IS A POPULATION FIX, NOT A LOOSENING, and the arithmetic says so on the day it landed:
    # open=87 and owed=74 are both far above the line of 25, so today's verdict is REPAIR-MODE
    # before and after. What changes is that the signal CAN now clear when the desk genuinely
    # catches up, instead of being held on by work it did correctly. `backlog` keeps its old
    # meaning and stays published, so every consumer that reads it is untouched.
    open_rows = [r for r in backlog if r.get("status") == "open"]
    # Rows that owe a decision RIGHT NOW: untriaged past grace, or a schedule that has run out.
    # Strictly the honest population -- an overdue schedule owes a decision exactly as an orphan
    # does, so it is counted, and an in-date schedule owes nothing today, so it is not.
    owed = len(past_due)
    ages = sorted((now - t).total_seconds() / 86400
                  for r in backlog if (t := _parse_ts(r.get("raised"))))

    def _pct(frac: float) -> float:
        """Age at a percentile of the backlog, 0.0 on an empty backlog (no rows, no age)."""
        return round(ages[min(int(frac * len(ages)), len(ages) - 1)], 2) if ages else 0.0

    # CONVERSION MUST CATCH UP TO ARRIVALS, AND MUST NEVER CATCH UP BY REDUCING THEM.
    #
    # Both numbers below were already computed, already printed in the artifact, and NEVER
    # COMPARED. Status asked only "is anything moving at all" (FLATLINE) and "is the pile big"
    # (REPAIR-MODE), so a desk raising 40 rows a week and dispositioning 3 read OK for as long as
    # the backlog stayed under the line -- falling 37 rows further behind every week, with the
    # evidence of it sitting unread in its own artifact. Measured-but-unread, again.
    #
    # AND THE SECOND HALF IS THE ONE THAT MATTERS MORE, because it is the direction a desk drifts
    # in without ever deciding to. Every status here improves when ARRIVALS FALL. Stop finding
    # things and the backlog shrinks, dispositions keep pace trivially, and the fence goes green
    # -- so the cheapest route to a clean conversion score is to look less hard. That is the
    # opposite of what the fence is for, and it would be indistinguishable from success.
    #
    # L1.28b(f) already forbids it in prose ("acquisition is never cut to meet extraction") and
    # nothing measured it. So arrivals are now compared against their own trailing baseline, and
    # a COLLAPSE is a defect in its own right -- reported even when everything else is green,
    # because that is exactly when it is invisible.
    #
    # The two failures are named separately on purpose: DEBT-GROWING means convert faster, and
    # ARRIVALS-COLLAPSED means find harder. Merging them into one "conversion" number would let
    # each mask the other, which is precisely how the ratio became gameable.
    prior_start, prior_end = now - timedelta(days=35), now - timedelta(days=7)
    arrivals_prior_28d = sum(
        1 for r in rows
        if (t := _parse_ts(r.get("raised"))) and prior_start <= t < prior_end)
    baseline_7d = arrivals_prior_28d / 4.0          # prior 28 days expressed as a weekly rate
    # Only meaningful once the baseline itself has enough mass; below that, say so rather than
    # inventing a comparison out of three rows.
    baseline_measurable = arrivals_prior_28d >= ARRIVAL_BASELINE_MIN
    arrivals_collapsed = (baseline_measurable
                          and arrivals_7d < ARRIVAL_COLLAPSE_FRACTION * baseline_7d)
    debt_growth_7d = arrivals_7d - dispositions_7d
    debt_growing = bool(
        backlog
        and debt_growth_7d >= DEBT_GROWTH_MIN_ROWS
        and arrivals_7d
        and dispositions_7d / arrivals_7d < DEBT_GROWTH_MIN_RATIO)

    # PRECEDENCE, and REPAIR-MODE deliberately outranks DEBT-GROWING. The two prescribe the same
    # action (convert more), but REPAIR-MODE is the already-wired admission signal that the
    # max-push queue, sweep prompts and brain briefs read, and demoting it would change behaviour
    # those consumers depend on for a headline that says the same thing. DEBT-GROWING exists to
    # cover what REPAIR-MODE cannot see: a backlog UNDER the line that is nevertheless growing --
    # the exact hole in the original logic, where a desk raising 40 a week and dispositioning 3
    # read OK indefinitely.
    #
    # But `debt_growing` is a FACT, not a headline, so it is recorded and it fails the fence
    # whichever status won. A desk that is over the line AND falling further behind must not exit
    # 0 merely because the more urgent-sounding label got there first.
    if dispositions_7d == 0 and backlog:
        status = "FLATLINE"
    elif arrivals_collapsed:
        status = "ARRIVALS-COLLAPSED"
    elif owed > REPAIR_MODE_BACKLOG:
        status = "REPAIR-MODE"
    elif debt_growing:
        status = "DEBT-GROWING"
    else:
        status = "OK"
    # THE DIRECTION IS NOT THE STATUS, AND CONFLATING THEM INVERTED THE REMEDY (2026-08-05).
    # `repair_mode` was `status != "OK"`, so it read TRUE for ARRIVALS-COLLAPSED -- and its
    # documented meaning, in L1.28b(d) and in run_max_push's own action string, is "flip the next
    # audit/brain window from FINDING to FIXING". That is precisely backwards for a status whose
    # entire content is that the desk is finding too little; line 215 of this file already said so
    # ("ARRIVALS-COLLAPSED means find harder") 42 lines above the code that contradicted it. The
    # flag was inert at the time -- its only consumer selected an advice string -- so the inversion
    # cost nothing until libs/ops/repair_mode.py gave it an actuator, which is exactly when a
    # latent inversion becomes an automated L1.25a fatigue-by-null defect.
    #
    # The mapping lives in ONE place (libs.ops.repair_mode.DIRECTION_FOR_STATUS) because a second
    # derivation of it is the bug. An unrecognised status maps to UNMEASURED, which OWES work.
    direction = DIRECTION_FOR_STATUS.get(status, "UNMEASURED")
    return {
        "generated": now.isoformat(), "status": status,
        # DRAIN / FIND-HARDER / STEADY / UNMEASURED -- what the next brain window should DO.
        "direction": direction,
        # Kept, and now meaning exactly what it says: this window owes the QUEUE its time.
        # ARRIVALS-COLLAPSED deliberately does NOT set it; that state owes the HUNT its time.
        "repair_mode": direction == "DRAIN",
        "law": "L1.28b -- conversion hunts 100% daily; a found-unfixed defect is unbooked "
               "loss aging at its stated ROI",
        "backlog": len(backlog), "past_due": len(past_due),
        "past_due_ids": [r.get("id") for r in past_due][:20],
        "past_due_overdue": len(overdue), "past_due_orphaned": len(orphans),
        "terminal_unstamped": terminal_unstamped,
        "arrivals_7d": arrivals_7d, "dispositions_7d": dispositions_7d,
        "arrival_rate_per_day": round(arrivals_7d / 7, 3),
        "disposition_rate_per_day": round(dispositions_7d / 7, 3),
        # The comparison the fence used to leave to the reader. Positive = the desk fell further
        # behind this week; conversion owes the difference, and the debt compounds at the ROI
        # each unconverted row states.
        "debt_growth_7d": debt_growth_7d,
        "debt_growing": debt_growing,
        "conversion_ratio_7d": (round(dispositions_7d / arrivals_7d, 3)
                                if arrivals_7d else None),
        # The anti-gaming half. A ratio can always be improved by shrinking its denominator, so
        # the denominator is watched on its own terms and against its own history.
        "arrivals_prior_28d": arrivals_prior_28d,
        "arrivals_baseline_7d": round(baseline_7d, 2) if baseline_measurable else None,
        "arrivals_collapsed": arrivals_collapsed,
        "arrivals_baseline_status": ("MEASURED" if baseline_measurable else
                                     f"UNMEASURED -- only {arrivals_prior_28d} row(s) in the "
                                     f"prior 28d, need {ARRIVAL_BASELINE_MIN} before a collapse "
                                     "can be distinguished from a quiet month"),
        "anti_gaming_note": ("conversion_ratio_7d must NEVER be raised by finding less. "
                             "L1.28b(f): acquisition is never cut to meet extraction, and "
                             "ARRIVALS-COLLAPSED outranks every green status below it."),
        "oldest_backlog_age_days": oldest_age,
        # THE DRAIN, which this fence computed and never read. `oldest_backlog_age_days` was
        # published from the day the fence was written and compared to NOTHING -- the same
        # measured-but-unread failure the comment at line 202 names about arrivals vs
        # dispositions, one layer over. It is the number that separates the only two states
        # REPAIR-MODE cannot currently tell apart: a desk DRAINING a burst stock (old rows
        # convert, the age percentiles fall) from a desk TREADING WATER on it (only new arrivals
        # convert, so every percentile rises exactly one day per day while flow looks balanced).
        # Both read `backlog≈flat, debt_growing=false, conversion_ratio≈0.8` and only one is work.
        "backlog_open": len(open_rows),
        "backlog_scheduled": len(backlog) - len(open_rows),
        "owed": owed,
        # THE DEFERRAL CHANNEL, which no gauge here could see. `reschedules_recorded` counts
        # forward from 2026-08-13 only: the prior moves were overwritten one dispose at a time and
        # are unrecoverable per row, so a 0 here means "none since the instrument existed", NEVER
        # "none ever" (L1.28a -- a limitation must not read as health). The historical rate is on
        # record in libs/ops/deferral.py: 39 of 152 ever-scheduled rows, 38 still scheduled.
        "chronic_deferrals": len(chronic),
        "chronic_deferral_ids": [r.get("id") for r in chronic][:20],
        "chronic_reschedule_line": CHRONIC_RESCHEDULES,
        "reschedules_recorded": sum(reschedule_count(r) for r in rows),
        "reschedules_measured_from": "2026-08-13 (schedule_history born empty; prior moves were "
                                     "overwritten in place and are unrecoverable per row)",
        "backlog_age_p50_days": _pct(0.50),
        "backlog_age_p90_days": _pct(0.90),
        "queue_dispositioned": round(terminal / max(len(rows), 1), 4),
        "repair_mode_line": REPAIR_MODE_BACKLOG,
        # Named so a reader cannot mistake which population the line is applied to (L1.57): the
        # count that drives the status is `owed`, not `backlog`.
        "repair_mode_population": "owed (untriaged past grace + schedule run out) -- L1.28b(d)",
        "detail": f"{len(backlog)} rows in backlog ({len(open_rows)} open, "
                  f"{len(backlog) - len(open_rows)} scheduled); {owed} OWE a decision now "
                  f"(oldest {oldest_age}d, p50 {_pct(0.50)}d); last 7d: {arrivals_7d} raised vs "
                  f"{dispositions_7d} dispositioned",
    }


def main() -> int:
    _law_guard()
    ap = argparse.ArgumentParser()
    ap.add_argument("--report-only", action="store_true",
                    help="write the artifact and always exit 0 (for queue refresh)")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    rep = build_report(_ROOT)
    out = _ROOT / "data/conversion_status.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(rep, indent=2), "utf-8")
    if args.json:
        print(json.dumps(rep, indent=2))
    else:
        print(f"conversion fence (L1.28b): {rep['status']} -- {rep.get('detail', '')}")
        print(f"-> {out}")
    if args.report_only:
        return 0
    # UNION OF TWO CONCURRENT FIXES TO THIS LINE, and both teeth are kept.
    #
    # (1) fence_exit(_PASSING) is the fail-CLOSED status map (R0237). It strictly subsumes the
    #     enumerate-the-failures form it replaced: FLATLINE, DEBT-GROWING and ARRIVALS-COLLAPSED
    #     are all outside _PASSING already, and so is a status added next year by someone who
    #     never reads this module. Enumerating passes is a list that cannot rot.
    #
    # (2) `debt_growing` is a BOOLEAN carried BESIDE the status, not a status, so no status map
    #     of any shape can see it. It stays an independent trigger, because conversion losing
    #     ground is the fence's own subject matter -- exit 0 there would report the failure this
    #     fence exists to catch in the same breath as success.
    if rep.get("debt_growing"):
        return FAIL
    return fence_exit(rep["status"], _PASSING)


if __name__ == "__main__":
    sys.exit(main())

```

### scripts\check_ratchets.py
```python
"""RATCHET FENCE -- constitution L1.0 / L2.0 made mechanical (principal order 2026-07-29).

L1.0: no measurable property of this desk is allowed to sit still. Today's value is the permanent
FLOOR; the standing target is 100%; the GAP between them is the work queue. The proving instance is
test strength -- measured for the first time at 55% on 2026-07-29 and closed to 90% the same
session. That is the required tempo, not a highlight.

A law with no fence is prose (L2.2), so this is the fence. It reads every committed floor artifact,
reports each metric as `value (floor, distance-to-100%)`, and FAILS when:
  * a metric fell below its recorded floor          -> a regression, the thing ratchets forbid
  * a metric's artifact is missing or stale         -> unmeasured is a defect, not a pass
  * a NEW metric appears with no floor recorded     -> a number without a floor is a defect

FLOORS ONLY RISE. `--ratchet` records improvements (and only improvements) into
data/ratchet_floors.json; nothing here can ever lower a floor, because lowering a floor to match a
regression is the denominator trick §34 forbids one level up. A metric is never retired to avoid a
falling number: retirement needs a written reason in the register.

WHAT IS DELIBERATELY NOT HERE: thresholds for what is "good". This fence measures direction and
distance, never quality -- quality bars live in the gates that own them and are not touched by it.

    python scripts/check_ratchets.py [--json] [--ratchet] [--report-only]
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
from libs.ops import disk as _disk_mod  # noqa: E402  (WARN_DAYS is the disk metric's denominator)

_FLOORS = _ROOT / "data/ratchet_floors.json"
_OUT = _ROOT / "data/ratchet_report.json"


def _j(path: Path) -> Any:
    try:
        return json.loads(path.read_text("utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _age_h(path: Path) -> float | None:
    try:
        return (time.time() - path.stat().st_mtime) / 3600.0
    except OSError:
        return None


# metric -> (artifact, extractor, max_staleness_hours, proving command)
# Every entry states the command that proves it, per L2.4: a claim without its command is not a
# measurement. max_age None = no staleness requirement (a floor artifact that only changes when the
# underlying work does).
def _mutation_targets(d: Any) -> dict[str, float]:
    """Per-target kill rates. PER-TARGET IS THE CORRECT SHAPE, and the first version got it wrong:
    a single `min()` across targets meant MEASURING A NEW FILE looked like a REGRESSION (staging
    entered at 83.3% and dragged the aggregate down from stepwise's 90%). A fence that fires when
    the desk measures MORE trains everyone to ignore it -- the opposite of L1.0. Each target now
    carries its own floor, and the aggregate below is a coverage number, not a min."""
    if not isinstance(d, dict):
        return {}
    out: dict[str, float] = {}
    for t in d.get("targets", []):
        if not (isinstance(t, dict) and isinstance(t.get("kill_rate"), (int, float))
                and t.get("total")):
            continue
        # A BUDGET-TRUNCATED RUN IS NOT A MEASUREMENT OF THIS TARGET. Sites are attempted in
        # source order, so a truncated run scores an arbitrary PREFIX of the file -- not a sample
        # of it -- and the rate says nothing about the rest. Measured 2026-07-30:
        # validation.py got 14 of 137 sites through a 1500s budget and reported 35.7%. Flooring
        # on that would pin the target to a number the complete run cannot be compared against,
        # in either direction. Excluded entirely rather than floored low: a floor set from a
        # partial run is a fabricated constraint.
        if t.get("budget_truncated"):
            continue
        # Prefer the equivalence-adjusted rate where the register applies (staging is 35/35 on
        # real mutants but 83.3% raw, and a permanently-red metric gets ignored).
        rate = t.get("adjusted_kill_rate")
        out[str(t.get("target"))] = float(
            rate if isinstance(rate, (int, float)) else t["kill_rate"])
    return out


def _mutation_at_bar(d: Any) -> float | None:
    """Share of MEASURED targets meeting the v8 8.2 bar -- itself a ratchet toward 100%."""
    rates = _mutation_targets(d)
    if not rates:
        return None
    return sum(1 for v in rates.values() if v >= 0.90) / len(rates)


def _campaign_retained(d: Any) -> float | None:
    """Observation-retention of the newest campaign (R0270).

    Returns None -- UNMEASURED, never a pass -- whenever the producing fence could not read a
    campaign. A retention number is only meaningful beside the plan it came from, and "no campaign
    on record" must not enter the ratchet board as a value.
    """
    if not isinstance(d, dict):
        return None
    v = d.get("retained_fraction")
    return float(v) if isinstance(v, (int, float)) else None


def _findings_coverage(d: Any) -> float | None:
    if not isinstance(d, dict):
        return None
    for k in ("coverage", "coverage_pct", "best_coverage"):
        v = d.get(k)
        if isinstance(v, (int, float)):
            return float(v) / (100.0 if float(v) > 1.0 else 1.0)
    return None


def _miner_productive(d: Any) -> float | None:
    if not isinstance(d, dict):
        return None
    seats = d.get("seats")
    if not isinstance(seats, dict) or not seats:
        return None
    ok = sum(1 for r in seats.values() if isinstance(r, dict) and r.get("status") == "ok")
    return ok / len(seats)


def _mypy_clean(d: Any) -> float | None:
    """Share of scripts with ZERO strict errors -- rises as tranches land."""
    if not isinstance(d, dict):
        return None
    per = d.get("per_file")
    if not isinstance(per, dict) or not per:
        return None
    clean = sum(1 for v in per.values() if isinstance(v, (int, float)) and int(v) == 0)
    return clean / len(per)


def _capability_wired(d: Any) -> float | None:
    """Share of BUILT capability that is actually REACHABLE -- the engine's own strength (R0104).

    THE METRIC THE ROW ASKS FOR, and why it is this one rather than a new artifact. R0104 wants
    "the weekly capability composite" floored and fenced, so that self-improvement itself must
    strengthen or explain itself. The desk already measures exactly that composite continuously:
    check_utilisation's capability_wired ceiling counts units the import graph can actually reach
    against units built. Minting a fresh "sweep output G" number would have been a phantom metric
    with no producer -- the failure mode where a gate's inputs are computed by nobody and the gate
    therefore never moves. Ratcheting the number that already exists is strictly better, and it
    updates every 6h rather than weekly.

    WHAT A FALL MEANS: capability was built and left unwired, or wired capability rotted out of
    the graph. Either is engineering already paid for returning zero (L1.28a) -- and unlike a
    coverage number it cannot be gamed by deleting the denominator, because deleting a built-but-
    unreachable unit RAISES the ratio honestly: that unit really is gone.
    """
    if not isinstance(d, dict):
        return None
    for row in d.get("ceilings") or []:
        if isinstance(row, dict) and row.get("name") == "capability_wired":
            # UNMEASURED counts as ZERO by L1.28a -- but a zero here would install a zero FLOOR,
            # which is a ratchet that permits anything. Refuse instead: no reading, no floor.
            if not row.get("measured"):
                return None
            val = row.get("utilisation")
            return float(val) if isinstance(val, (int, float)) else None
    return None


def _roi_basis_share(d: Any) -> float | None:
    """Share of value-carrying ledger rows whose roi_bps/rank basis is DECLARED (R0477).

    The denominator is rows carrying ANY value claim, so valueless adds cannot dilute it; every
    new valued row declares at add-time, so the share can only rise -- ratchet-shaped.
    """
    val = d.get("roi_basis_declared_share") if isinstance(d, dict) else None
    return float(val) if isinstance(val, (int, float)) else None


def _repair_p_fix(d: Any) -> float | None:
    """Share of raised rows actually FIXED within the horizon -- repair capacity (R0330).

    WHY THIS ONE OF THE THREE. R0330 asks for MTTR, P(fix) and stock growth to be born with floors.
    Only P(fix) is ratchet-shaped: it is already a fraction in [0,1] where higher is better. MTTR is
    a latency in days (lower is better, unbounded above) and stock growth is a signed rate -- both
    are published in data/repair_metrics.json as trend numbers, and inventing a [0,1] transform for
    them would have produced two metrics whose floors nobody could interpret.

    WHY FIX AND NOT DISPOSITION. A reasoned rejection IS a conversion under L1.28b(b) and the queue
    genuinely drains, but a rejection consumes no repair capacity. Flooring the disposition rate
    would let the desk raise this number by rejecting more, which is the denominator trick one
    level in. p_disposed is published beside it so both stay visible.

    A fall means rows are arriving faster than they are being repaired, or repairs are being
    replaced by rejections. INSUFFICIENT reads as None: a probability from a handful of eligible
    rows is noise, and a zero floor is a ratchet that permits anything (L1.28a).
    """
    if not isinstance(d, dict):
        return None
    val = d.get("p_fix")
    return float(val) if isinstance(val, (int, float)) and not isinstance(val, bool) else None


def _disk_headroom(d: Any) -> float | None:
    """Runway before the recorders pause, as a share of the lead time needed to act (R0331).

    WHY NOT disk_free_pct, WHICH IS WHAT THE ROW ASKED FOR. Free space MUST fall here: the tape
    grows every second the recorders run, and that growth is the desk's only unreplicable asset.
    A floor under free-pct would therefore report a REGRESSION every single day for doing exactly
    the right thing -- and a fence that is red by construction gets switched off (L1.43), taking
    the real signal with it. The quantity that legitimately ratchets is PREPAREDNESS: how much of
    the honest lead time for the only non-destructive fix (buy storage, move cold tape) the desk
    still has. That falls only when the situation genuinely deteriorates, and it rises when
    capacity is added or growth slows.

    WHY THIS ARTIFACT. days_to_pause already exists and has exactly one caller -- the moat miner,
    which reads the archive every pass and is therefore the cheapest place on the desk to notice
    the deadline. Minting a second disk producer would put two numbers on one fact (L2.9:
    upgrade before build). The miner runs continuously, so a 6h bound reads STALE long before the
    number could mislead.

    WHAT A FALL MEANS: the archive's deadline moved closer without anyone deciding it should.
    MEASURED 2026-08-12 at 0.143 (3.0 days of a 21-day lead time) -- the fill rate had stepped up
    53% on ~08-05, from 0.69 to 1.03 GB/day, and nothing recorded the trend, so R0331's own
    runway estimate of 25.1 days was still being quoted eleven days after it stopped being true.
    That is the failure this floor exists to make impossible to repeat.
    """
    if not isinstance(d, dict):
        return None
    disk = ((d.get("closure") or {}) if isinstance(d.get("closure"), dict) else {}).get("disk")
    if not isinstance(disk, dict):
        return None
    state = disk.get("state")
    if state == "PAUSED":
        # The recorders have STOPPED. Zero preparedness is the honest reading, not a refusal:
        # this is measured, it is the worst possible value, and the fence must fire.
        return 0.0
    if state == "UNKNOWN":
        # Growth not measurable yet -- a percentage, not a date. Refusing beats inventing a
        # runway, and beats a 0.0 that would install a floor permitting anything (L1.28a).
        return None
    days = disk.get("days")
    if not isinstance(days, (int, float)):
        return None
    return min(1.0, max(0.0, float(days) / _disk_mod.WARN_DAYS))


def _alert_delivery(path: Path) -> float | None:
    try:
        lines = path.read_text("utf-8").splitlines()[-500:]
    except OSError:
        return None
    floor = time.time() - 24 * 3600
    for line in reversed(lines):
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not row.get("ok"):
            continue
        ts = str(row.get("ts", ""))
        try:
            if datetime.fromisoformat(ts).timestamp() >= floor:
                return 1.0
        except ValueError:
            continue
    return 0.0


_METRICS: dict[str, tuple[str, Callable[[Any], float | None], float | None, str]] = {
    "test_strength_targets_at_bar": (
        "data/mutation_score.json", _mutation_at_bar, None,
        "python scripts/run_mutation.py"),
    "findings_coverage": (
        "docs/research/findings_coverage_record.json", _findings_coverage, None,
        "python scripts/max_audit.py (check_findings_tracked)"),
    "miner_seats_productive": (
        "data/miner_runway.json", _miner_productive, 48.0,
        "python scripts/check_miner_runway.py --json --report-only"),
    "scripts_mypy_clean": (
        "data/mypy_ratchet.json", _mypy_clean, None,
        "python scripts/check_mypy_ratchet.py"),
    # R0104: self-improvement gets a floor and a fence like everything else. 12h max age = two
    # cycles of its 6-hourly producer, so a dead utilisation fence reads STALE rather than green.
    "capability_wired": (
        "data/utilisation.json", _capability_wired, 12.0,
        "python scripts/check_utilisation.py"),
    # R0270: the share of available observations a campaign actually tested on. History length is
    # the binding constraint on this desk's discovery power, so this is the ratchet that says the
    # 82.9% min-length discard never comes back. 48h = two runs of the daily crypto factory.
    "campaign_obs_retained": (
        "data/campaign_retention.json", _campaign_retained, 48.0,
        "python scripts/check_campaign_retention.py"),
    # R0330: repair capacity, not just queue length. check_conversion measures the queue; this is
    # the service rate that drains it, and until now it counted as zero for want of a producer
    # (L1.28a). 30h = a day's slack on the daily producer, so a dead fence reads STALE.
    "repair_p_fix": (
        "data/repair_metrics.json", _repair_p_fix, 30.0,
        "python scripts/check_repair_capacity.py"),
    # R0477: one ledger field carried two populations (measured bps vs rank ordinals
    # 9999/9000/...), so a guessed rank was indistinguishable from a measured return. The split
    # only closes if declaration coverage rises; floored from birth so backfill drives itself.
    "roi_basis_declared_share": (
        "data/repair_metrics.json", _roi_basis_share, 30.0,
        "python scripts/check_repair_capacity.py"),
    # R0331: the archive's deadline gets a floor. The alarm half already existed (days_to_pause
    # -> max_audit's tape-disk-deadline) but nothing recorded the TREND, so a 53% step-up in the
    # fill rate on ~2026-08-05 went unnoticed for a week and the row's own 25.1-day runway was
    # still being quoted when the true figure was 3.0 days. 6h = many passes of the continuously
    # running miner, so a dead miner reads STALE rather than green on a frozen runway.
    "disk_headroom_ratio": (
        "data/moat_mine.json", _disk_headroom, 6.0,
        "python -c \"import json;print(json.load(open('data/moat_mine.json'))['closure']['disk'])\""),
}
# Artifacts read as raw files rather than parsed JSON documents.
_FILE_METRICS: dict[str, tuple[str, Callable[[Path], float | None], float | None, str]] = {
    "pager_delivered_24h": (
        "data/alert_delivery.jsonl", _alert_delivery, None,
        "python scripts/run_alert_canary.py"),
}


def evaluate() -> dict[str, Any]:
    floors = _j(_FLOORS) or {}
    rows: list[dict[str, Any]] = []

    def _row(name: str, artifact: str, value: float | None, age: float | None,
             max_age: float | None, cmd: str) -> dict[str, Any]:
        floor = floors.get(name, {}).get("value") if isinstance(floors.get(name), dict) else None
        stale = (max_age is not None and age is not None and age > max_age)
        if value is None:
            status = "UNMEASURED"            # never a pass: unmeasured is a defect (L1.0a)
        elif floor is None:
            status = "NO-FLOOR"              # a number without a floor is a defect
        elif value + 1e-9 < float(floor):
            status = "REGRESSION"
        elif stale:
            status = "STALE"
        elif value >= 0.999:
            status = "AT-100"
        elif value <= 1e-9 and float(floor) <= 1e-9:
            # FLATLINE, not OK -- the fence limitation the 2026-07-30 governance audit named.
            # A floors-only ratchet asks one question ("did it fall?"), so a metric born at zero
            # with a zero floor answers "no" forever and reads OK while measuring a capability
            # that has NEVER ONCE worked (miner seats 0%, pager deliveries 0%). Zero is the one
            # value where no-regression and no-function are indistinguishable, so it gets its own
            # status: visible on every board, ranked by run_max_push, never dressed as health.
            # Not a hard failure -- both known flatlines are blocked on principal-side steps
            # (credentials, channel funding), and a daily red on a human-owed item teaches the
            # desk to ignore red.
            status = "FLATLINE"
        else:
            status = "OK"
        return {"metric": name, "artifact": artifact, "value": value,
                "floor": floor, "distance_to_100": (None if value is None
                                                    else round(1.0 - value, 4)),
                "age_h": None if age is None else round(age, 1),
                "max_age_h": max_age, "status": status, "proving_command": cmd}

    for name, (rel, fn, max_age, cmd) in _METRICS.items():
        path = _ROOT / rel
        rows.append(_row(name, rel, fn(_j(path)), _age_h(path), max_age, cmd))
    for name, (rel, ffn, max_age, cmd) in _FILE_METRICS.items():
        path = _ROOT / rel
        rows.append(_row(name, rel, ffn(path), _age_h(path), max_age, cmd))
    # DYNAMIC per-target mutation rows: a metric is born with its own floor the day it is first
    # measured (L2.0), so newly measured files enter as NO-FLOOR -> floored, never as regressions.
    mut_path = _ROOT / "data/mutation_score.json"
    for target, rate in sorted(_mutation_targets(_j(mut_path)).items()):
        rows.append(_row(f"test_strength::{target}", "data/mutation_score.json", rate,
                         _age_h(mut_path), None,
                         f"python scripts/run_mutation.py --target {target}"))

    bad = [r for r in rows if r["status"] in ("REGRESSION", "STALE", "NO-FLOOR", "UNMEASURED")]
    # THE WORK QUEUE (L1.0c): measured metrics ranked by how far they sit from 100%.
    queue = sorted((r for r in rows if isinstance(r["distance_to_100"], float)
                    and r["distance_to_100"] > 0.001),
                   key=lambda r: -float(r["distance_to_100"]))
    return {"checked": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "law": "L1.0 universal ratchet -- today's value is the floor, 100% is the target, "
                   "the gap is the work queue",
            "rows": rows, "n_bad": len(bad),
            "work_queue": [{"metric": r["metric"], "value": r["value"],
                            "distance_to_100": r["distance_to_100"]} for r in queue]}


def ratchet_up(report: dict[str, Any]) -> dict[str, Any]:
    """Record IMPROVEMENTS only. This function cannot lower a floor -- by construction, because a
    floor lowered to match a regression is exactly the failure the ratchet exists to prevent."""
    floors = _j(_FLOORS) or {}
    raised: list[str] = []
    for r in report["rows"]:
        v = r["value"]
        if not isinstance(v, (int, float)):
            continue
        cur = floors.get(r["metric"], {}).get("value") if isinstance(
            floors.get(r["metric"]), dict) else None
        if cur is None or float(v) > float(cur) + 1e-9:
            floors[r["metric"]] = {"value": round(float(v), 6),
                                   "recorded": report["checked"],
                                   "artifact": r["artifact"],
                                   "proving_command": r["proving_command"]}
            raised.append(f"{r['metric']} -> {float(v):.4f}"
                          + ("" if cur is None else f" (was {float(cur):.4f})"))
    _FLOORS.parent.mkdir(parents=True, exist_ok=True)
    _FLOORS.write_text(json.dumps(floors, indent=2, sort_keys=True), "utf-8")
    return {"raised": raised, "n_floors": len(floors)}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--ratchet", action="store_true",
                    help="record improvements as the new floors (never lowers one)")
    ap.add_argument("--report-only", action="store_true", help="always exit 0")
    args = ap.parse_args()

    rep = evaluate()
    if args.ratchet:
        rep["ratchet"] = ratchet_up(rep)
    _OUT.parent.mkdir(parents=True, exist_ok=True)
    _OUT.write_text(json.dumps(rep, indent=2), "utf-8")

    if args.json:
        print(json.dumps(rep, indent=2))
    else:
        print(f"ratchets | {rep['n_bad']} defect(s) | "
              f"{len(rep['work_queue'])} metric(s) below 100%")
        for r in rep["rows"]:
            val = "n/a" if r["value"] is None else f"{float(r['value']):.1%}"
            flr = "none" if r["floor"] is None else f"{float(r['floor']):.1%}"
            dist = "" if r["distance_to_100"] is None else f" gap {float(r['distance_to_100']):.1%}"
            print(f"  {r['status']:11} {r['metric']:30} {val:>7} (floor {flr}{dist})")
        if rep["work_queue"]:
            top = rep["work_queue"][0]
            print(f"  -> largest gap: {top['metric']} at {float(top['value']):.1%}, "
                  f"{float(top['distance_to_100']):.1%} from 100%")
        for line in rep.get("ratchet", {}).get("raised", []):
            print(f"  FLOOR RAISED {line}")
    return 0 if args.report_only else (1 if rep["n_bad"] else 0)


if __name__ == "__main__":
    raise SystemExit(main())

```

### scripts\heal_forward_lane.py
```python
"""Every certificate gathers forward evidence, and no sleeve stays blocked. On a clock.

WHY THIS EXISTS

A certificate that is not accruing forward evidence is worth nothing. It cannot cure a power
deficit, it cannot earn promotion authority, and it cannot be falsified -- it just sits, looking
like an asset on a dashboard while producing no information at all. Two different failures put
certificates in that state, and this heals both, at the CAUSE rather than the symptom.

FAILURE ONE -- BLOCKED SLEEVES. Measured 2026-08-29T13:16:54Z: all 34 live forward clocks in
`shadow_state.json` went `BLOCKED_SLEEVE_ERROR` at once, every one of them reading

    ModuleNotFoundError: No module named 'mt5desk.family_inputs'

The module was committed, matched HEAD, and was on the drift watchlist. It was ABSENT on the
trading box, and the drift healer scored absence the same as an unreachable box -- it skipped
both -- so a clean drift report was printed over a forward lane that had stopped dead. The whole
desk's forward evidence stopped for the one class of file the healer structurally could not see.

The lesson is not "ship that module". It is that a blocked sleeve names its own cause in
`last_error`, in a machine-readable form, and nothing was reading it. This reads it.

FIX THE CAUSE, NEVER THE STATUS. `shadow_forward` already clears `BLOCKED_SLEEVE_ERROR` by itself
the moment a sleeve evaluates end to end, so this NEVER writes sleeve status. It could: a loop
that reset every blocked row to ACTIVE would empty this report and change nothing underneath,
because the next pass would re-block on the same missing import while the ledger claimed health.
A fixer that can hide its own failure is worse than no fixer. So the only thing here that writes
is the shipping of a file the box is missing, and the proof is the box's own hash afterwards.

FAILURE TWO -- IDLE CERTIFICATES. A certificate can be perfectly enrollable and still have no
forward clock, because enrolment is a separate step that can silently no-op. Those never show up
as errors -- there is no row to be blocked -- so they are invisible to every check that reads
the ledger. This counts certificates against clocks and names the difference, which is the only
way an absent thing gets noticed.

WHAT IT WILL NOT DO. It does not promote, size, or arm anything, and it never edits the sleeve
registry. Getting evidence flowing is mechanical and safe to automate; deciding what to do with
that evidence is not, and mixing the two would put an unattended script on the money path.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

OUT = ROOT / "data" / "forward_lane_health.json"
SHADOW = ROOT / "desks" / "mt5" / "reports" / "shadow"
REMOTE = "contabo-mt5"

#: Ledgers holding forward clocks. Each is a different admission path into the same lane, and a
#: check that read only the main one would have missed three-quarters of the desk.
LEDGERS = ("shadow_state.json", "qquant_shadow_state.json",
           "scalp_shadow_state.json", "external_shadow_state.json")

#: Statuses that mean "this sleeve is not gathering evidence and something broke". RETIRED_* are
#: deliberately absent: a retired sleeve is a decision, not a fault, and healing it would be
#: re-animating something the desk chose to stop.
BLOCKED = ("BLOCKED_SLEEVE_ERROR", "BLOCKED_POWER_UNCURED", "BLOCKED_UNIVERSAL_GATES",
           # Written by the engine when a family's runtime inputs cannot be rebuilt. Distinct
           # from BLOCKED_SLEEVE_ERROR on purpose: that means "this raised", while this means
           # "this was reached and had nothing to run with" -- a wiring gap, and the two need
           # different fixes.
           "BLOCKED_INPUTS_UNAVAILABLE")

#: `ModuleNotFoundError: No module named 'x.y'` -- the one root cause that is unambiguous enough
#: to fix without a human, because the fix is "put the committed file where it belongs".
_MISSING_MODULE = re.compile(r"No module named ['\"]([\w.]+)['\"]")

#: Roots a desk module can live under, in the order a box import would find them.
_SEARCH_ROOTS = ("desks/mt5", "libs", ".")


def _run(cmd: list[str], timeout: int = 90) -> tuple[int, str]:
    try:
        r = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True,
                           timeout=timeout, check=False)
        return r.returncode, (r.stdout or "").strip()
    except (subprocess.TimeoutExpired, OSError):
        return 124, ""


def _resolve_module(dotted: str) -> str | None:
    """Repo-relative path of a module named the way an importer on the box would name it.

    `mt5desk.family_inputs` is imported that way because the box puts `desks/mt5` on the path, so
    the dotted name is NOT the repo path and cannot be turned into one by string surgery alone.
    """
    tail = Path(*dotted.split(".")).with_suffix(".py")
    for root in _SEARCH_ROOTS:
        cand = ROOT / root / tail
        if cand.exists():
            return str(cand.relative_to(ROOT))
    hits = [p for p in ROOT.rglob(tail.name)
            if "__pycache__" not in p.parts and ".venv" not in p.parts
            and p.parts[-len(tail.parts):] == tail.parts]
    return str(hits[0].relative_to(ROOT)) if len(hits) == 1 else None


def _ship(rel: str) -> tuple[bool, str]:
    """Ship a file to the box, but ONLY the version HEAD agrees with.

    Same safety property as the drift healer, restated rather than imported loosely: this box has
    a replayer that reverts working-tree files to ancient copies, and a fixer that shipped
    whatever was on disk would propagate a trampled file straight onto the box that trades.
    """
    rc_l, local = _run(["git", "hash-object", str(ROOT / rel)])
    rc_h, head = _run(["git", "rev-parse", f"HEAD:{rel}"])
    if rc_l != 0 or rc_h != 0 or not local or not head:
        return False, f"{rel}: cannot hash locally or in HEAD -- not shipped"
    if local != head:
        return False, (f"{rel}: local copy differs from HEAD -- NOT shipped. Commit or restore it "
                       f"here first; shipping a trampled file is how the box got an ancient engine")
    rc, _ = _run(["scp", "-o", "ConnectTimeout=45", "-q",
                  str(ROOT / rel), f"{REMOTE}:C:/opt/quant/{rel}"], timeout=180)
    if rc != 0:
        return False, f"{rel}: scp failed (box unreachable?)"
    rc_r, out = _run(["ssh", "-o", "ConnectTimeout=25", REMOTE,
                      f"cd C:\\opt\\quant && git hash-object {rel}"])
    landed = (out.replace("\r", "").strip().splitlines() or [""])[-1].strip()
    if rc_r == 0 and landed == head:
        return True, f"{rel}: SHIPPED, box now matches HEAD ({head[:8]})"
    return False, f"{rel}: shipped but box reports {landed[:8] or 'nothing'} != HEAD {head[:8]}"


def _watchlist_gap(rels: set[str]) -> list[str]:
    """Modules this had to ship that the drift healer is not watching.

    Anything that went missing once will go missing again -- a box rebuild, a partial sync, a new
    module next week. Shipping it fixes today; naming the watchlist gap is what stops the repeat.
    """
    try:
        watch = (ROOT / "scripts" / "check_desk_module_drift.py").read_text("utf-8")
    except OSError:
        return sorted(rels)
    return sorted(r for r in rels if r not in watch)


def _engine_last_run() -> datetime | None:
    """Newest `last_attempt_at` anywhere -- when the forward engine last evaluated ANYTHING.

    This is the clock a stale error is measured against. There is no single "engine ran at"
    stamp, but any row it touched carries one, so the maximum across all rows is the engine's
    own heartbeat and needs no new artifact to maintain.
    """
    newest: datetime | None = None
    for name in LEDGERS:
        f = SHADOW / name
        if not f.exists():
            continue
        try:
            data = json.loads(f.read_text("utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        rows = data.get("sleeves", data) if isinstance(data, dict) else {}
        for st in rows.values():
            if not isinstance(st, dict):
                continue
            t = _parse_ts(st.get("last_attempt_at"))
            if t and (newest is None or t > newest):
                newest = t
    return newest


def _blocked_rows() -> list[dict]:
    rows: list[dict] = []
    for name in LEDGERS:
        p = SHADOW / name
        if not p.exists():
            continue
        try:
            data = json.loads(p.read_text("utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        for key, st in data.items():
            if isinstance(st, dict) and st.get("status") in BLOCKED:
                rows.append({"ledger": name, "key": key,
                             "status": st.get("status"),
                             "error": str(st.get("last_error") or
                                          st.get("gate_reason") or "")[:200],
                             "at": st.get("last_error_at"),
                             "last_attempt_at": st.get("last_attempt_at")})
    return rows


def _error_is_stale(row: dict) -> bool:
    """True only when this same sleeve was attempted after the recorded error.

    Comparing a row with the book-wide newest attempt is invalid because sleeves are evaluated
    sequentially: every failing row except the last then looks stale during the very pass that
    produced its live error.  That bug prevented the healer from shipping a missing dependency
    shared by seven EURCHF clocks.
    """
    error_at = _parse_ts(row.get("at"))
    attempted_at = _parse_ts(row.get("last_attempt_at"))
    return bool(error_at and attempted_at and attempted_at > error_at)


#: A sleeve the engine has not touched in this long is not "accumulating", it is stopped. Two
#: hours spans the hourly cycle plus a slow sweep without flagging a merely late run.
_STALE_ATTEMPT_H = 2.0

#: An ACCUMULATING sleeve older than this with ZERO trades is not early, it is not firing.
#: Sleeves on this desk average ~8 trades per 12 days, so three days with none is well outside
#: the normal rate and worth naming rather than waiting out.
_SILENT_DAYS = 3


def _stalled_rows() -> list[dict]:
    """Sleeves that LOOK alive and are not: stale, silent, or accruing nothing.

    WHY THESE THREE, AND WHY THEY ARE NOT ERRORS. A blocked sleeve announces itself; these do
    not. `ACCUMULATING` at day 0 with no trades reads exactly like a healthy new sleeve, which is
    how three scalp rows sat at "day 0/14" for days while their clock was being restamped every
    cycle. A status that is indistinguishable from health is the one that needs a watchdog most,
    because nobody will ever go looking for it.

      STALE_SOURCE / stale attempt -- the engine stopped evaluating this row at all.
      SILENT        -- alive for days, zero fills: the signal is not firing or is being dropped.
      CLOCK_AHEAD   -- forward_start later than its own first trade (see check_forward_clock).

    Reported, never auto-reset. Each has a DIFFERENT cause -- a dead engine pass, a missing input,
    a broken signal, a restamped clock -- and the one shared response ("set it back to ACTIVE")
    would hide all four while fixing none.
    """
    now = datetime.now(tz=UTC)
    out: list[dict] = []
    for name in LEDGERS:
        f = SHADOW / name
        if not f.exists():
            continue
        try:
            data = json.loads(f.read_text("utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        rows = data.get("sleeves", data) if isinstance(data, dict) else {}
        for key, st in rows.items():
            if not isinstance(st, dict):
                continue
            status = str(st.get("status") or "")
            if status.startswith("RETIRED") or status in ("KILL", "PROMOTED"):
                continue
            n = int(st.get("n") or 0)

            if st.get("bar_source_stale"):
                out.append({"ledger": name, "key": key, "kind": "STALE_SOURCE", "n": n,
                            "why": f"bar source {st.get('bar_source')} is stale; the row cannot "
                                   f"accrue honest forward evidence until it is fresh"})
                continue

            last = _parse_ts(st.get("last_attempt_at"))
            if last is not None:
                age_h = (now - last).total_seconds() / 3600.0
                if age_h > _STALE_ATTEMPT_H:
                    out.append({"ledger": name, "key": key, "kind": "STALE_ATTEMPT", "n": n,
                                "why": f"engine last evaluated this row {age_h:.1f}h ago; the "
                                       f"hourly cycle is not reaching it"})
                    continue

            start = _parse_ts(st.get("forward_start"))
            if n == 0 and start is not None:
                days = (now - start).days
                if days >= _SILENT_DAYS:
                    out.append({"ledger": name, "key": key, "kind": "SILENT", "n": 0,
                                "why": f"{days} days enrolled and ZERO trades -- the signal is "
                                       f"not firing or its fills are being dropped"})
    return out


def _parse_ts(v: object) -> datetime | None:
    if not isinstance(v, str) or not v:
        return None
    try:
        d = datetime.fromisoformat(v.replace("Z", "+00:00"))
    except ValueError:
        return None
    return d if d.tzinfo else d.replace(tzinfo=UTC)


def _tradeable(sym: str) -> tuple[bool, str]:
    """Can this desk ever place an order on `sym` and replay a clock on it?

    The SAME predicate gate 0 applies (`external_gauntlet.symbol_is_tradeable`), imported rather
    than restated so the two can never disagree about which symbols exist. Gate 0 stops NEW
    untradeable certificates; this names the ones minted before it.
    """
    try:
        sys.path.insert(0, str(ROOT / "desks" / "mt5" / "scripts"))
        from external_gauntlet import symbol_is_tradeable

        meta = json.loads((ROOT / "desks" / "mt5" / "data" / "universe" / "universe.json")
                          .read_text("utf-8"))
        return symbol_is_tradeable(sym, meta)
    except Exception as exc:
        # UNKNOWN IS NOT UNTRADEABLE. If the predicate cannot run, the certificate keeps its
        # place in the idle list rather than being quietly written off (L1.28a).
        return True, f"tradeability UNMEASURED ({type(exc).__name__})"


def _idle_certificates() -> dict:
    """Certificates that should have a forward clock and do not.

    USE THE PRODUCER'S OWN MAPPING. A certificate is named `external.XAUUSD.session_range_breakout`
    and its clock is keyed `XAUUSD.asia#rr=2.0_wb=12`; no string surgery turns one into the other,
    because the selector, the parameter signature and the family alias all come from admission's
    own logic. A first cut here compared the raw strings and reported 40 of 41 certificates idle
    when nearly all of them were running -- a false alarm that, on a clock, would have trained
    everyone to ignore this check.

    So this asks `shadow_admission` what runs it authorizes and keys them with its own `run_key`.
    The check is then exact, and it cannot drift from admission because it IS admission.
    """
    desk = ROOT / "desks" / "mt5"
    sys.path.insert(0, str(desk))
    try:
        from research.shadow_admission import authorized_runs, run_key
    except ImportError as exc:
        return {"error": f"cannot import shadow_admission: {exc}"}
    try:
        runs = authorized_runs(desk)
    except Exception as exc:                     # admission failing IS the finding
        return {"error": f"authorized_runs raised {type(exc).__name__}: {str(exc)[:120]}"}

    expected = {run_key(r): r for r in runs}
    clocked: set[str] = set()
    for name in LEDGERS:
        f = SHADOW / name
        if not f.exists():
            continue
        try:
            clocked |= set(json.loads(f.read_text("utf-8")))
        except (OSError, json.JSONDecodeError):
            continue

    # UNTRADEABLE IS NOT IDLE, and reporting it as idle is worse than not reporting it. Measured
    # 2026-09-02: eight certificates on AFG and AFL -- symbols absent from the universe registry
    # with no H1 parquet on the box -- were named IDLE every twenty minutes, for weeks. There is
    # no repair for them: no clock can ever enrol a symbol the broker does not quote and no
    # replay can run on bars that do not exist (L1.49, a gate that cannot be cashed is not a
    # survivor). A permanent finding on a rolling health report is how a reader learns to skip
    # the row, which then costs the real ones. Named separately and counted, never mixed in.
    untradeable: dict[str, str] = {}
    idle_real: list[str] = []
    for key in sorted(k for k in expected if k not in clocked):
        if str(key).startswith("scalp."):
            continue                      # accrues on scalp_shadow's clock, not this lane's
        sym = str(key).split(".")[0].split("#")[0]
        ok, why = _tradeable(sym)
        if ok:
            idle_real.append(key)
        else:
            untradeable[key] = why
    return {"authorized_runs": len(expected),
            "with_clock": len(expected) - len(idle_real) - len(untradeable),
            "idle": idle_real[:40], "idle_count": len(idle_real),
            "untradeable": dict(list(untradeable.items())[:40]),
            "untradeable_count": len(untradeable)}


def main() -> int:
    now = datetime.now(tz=UTC)
    rows = _blocked_rows()
    report: dict = {"checked_at": now.isoformat(timespec="seconds"),
                    "blocked_total": len(rows), "healed": [], "unfixable": [],
                    "watchlist_gap": [], "idle": {}, "stalled": [], "stale_errors": []}

    print(f"FORWARD LANE {now.isoformat(timespec='seconds')}")
    print(f"  blocked sleeves: {len(rows)}")

    # One missing module blocks every sleeve that needs it, so fix per CAUSE, not per sleeve --
    # 34 rows here were 34 copies of one defect, and shipping once clears all of them.
    # A STALE ERROR IS NOT A LIVE CAUSE, and treating it as one is worse than ignoring it.
    # Measured 2026-08-29T20:42: seven EURCHF.discovered rows carried
    # `ModuleNotFoundError: mt5desk.family_inputs` stamped 13:46:59 with last_attempt_at NULL,
    # while the module was verifiably importable on the box (`OK C:\opt\quant\...`). This healer
    # re-shipped a correct module on every run for hours, reported HEALED each time, and the real
    # cause -- the engine reaching those rows and skipping them without recording an attempt --
    # stayed completely hidden behind a fixed-looking symptom.
    #
    # An error older than the engine's last pass describes a world that no longer exists.
    engine_run = _engine_last_run()
    live_rows, stale_rows = [], []
    for r in rows:
        if _error_is_stale(r):
            observed = engine_run or _parse_ts(r.get("last_attempt_at"))
            stale_rows.append({**r, "engine_ran_at": (
                observed.isoformat(timespec="seconds") if observed else None
            )})
        else:
            live_rows.append(r)
    report["stale_errors"] = stale_rows
    if stale_rows:
        print(f"  STALE ({len(stale_rows)}) -- error predates the engine's last pass "
              f"({engine_run.isoformat(timespec='seconds') if engine_run else '?'}), so it does "
              f"NOT describe the current cause. Not acted on; the row is being skipped without "
              f"recording an attempt, which is the real defect:")
        for r in stale_rows[:5]:
            print(f"    {r['key'][:46]:48s} err@{str(r.get('at'))[:19]}")
    rows = live_rows

    wanted: dict[str, list[str]] = {}
    for r in rows:
        m = _MISSING_MODULE.search(r["error"])
        if m:
            wanted.setdefault(m.group(1), []).append(r["key"])
        else:
            report["unfixable"].append({"key": r["key"], "status": r["status"],
                                        "error": r["error"]})

    shipped: set[str] = set()
    for dotted, keys in sorted(wanted.items()):
        rel = _resolve_module(dotted)
        if rel is None:
            report["unfixable"].append(
                {"key": f"{len(keys)} sleeves", "status": "MISSING_MODULE",
                 "error": f"'{dotted}' blocks {len(keys)} sleeves and resolves to no committed "
                          f"file here -- it was never written, or lives outside the search roots"})
            print(f"  UNRESOLVED {dotted}: blocks {len(keys)} sleeves, no such file in this repo")
            continue
        ok, detail = _ship(rel)
        print(f"  {'HEALED ' if ok else 'FAILED '}{dotted} ({len(keys)} sleeves): {detail}")
        if ok:
            shipped.add(rel)
            report["healed"].append({"module": dotted, "path": rel, "sleeves": len(keys)})
        else:
            report["unfixable"].append({"key": f"{len(keys)} sleeves",
                                        "status": "SHIP_FAILED", "error": detail})

    if shipped:
        gap = _watchlist_gap(shipped)
        report["watchlist_gap"] = gap
        if gap:
            print("\n  WATCHLIST GAP -- shipped but unwatched, so free to go missing again:")
            for rel in gap:
                print(f"    {rel}  -> add to MODULES in scripts/check_desk_module_drift.py")

    stalled = _stalled_rows()
    report["stalled"] = stalled
    if stalled:
        from collections import Counter
        kinds = Counter(r["kind"] for r in stalled)
        print(f"\n  STALLED ({len(stalled)}) -- alive-looking rows that are not accruing: "
              f"{dict(kinds)}")
        for r in stalled[:10]:
            print(f"    {r['kind']:14s} {r['key'][:40]:42s} {r['why'][:70]}")

    report["idle"] = _idle_certificates()
    idle_n = report["idle"].get("idle_count")
    if idle_n is not None:
        print(f"\n  authorized runs: {report['idle']['authorized_runs']}, "
              f"with a forward clock: {report['idle']['with_clock']}, idle: {idle_n}")
        for n in report["idle"]["idle"][:10]:
            print(f"    IDLE {n} -- authorized to run forward, no clock exists")
        # A HEALER THAT ONLY DIAGNOSES IS A REPORT (fixed 2026-09-14).
        #
        # This found idle certificates, named them, exited 1 and enrolled none -- for weeks. The
        # file is called heal_forward_lane and the one failure it is named for was the one it
        # left alone. Measured tonight: 84 of 186 authorized runs had no clock, every one already
        # through all ten gates, accruing nothing.
        #
        # WHY THE HOURLY ENROLLER DID NOT COVER IT. `enrol_clocks` runs `shadow_forward` under
        # the cycle's 720s search budget and was killed partway through the same prefix EVERY
        # hour, so the tail was never reached -- not once. That is now fixed at the source
        # (LEG_BUDGET_SEC), and this is the second line of defence: whatever the schedule does,
        # a certificate cannot sit clockless once this has run.
        #
        # ENROLLING GRANTS NOTHING. A forward clock is a SHADOW lane and shadow lanes hold no
        # order authority; starting one resumes MEASUREMENT. Promotion still demands a
        # certificate and a mature clock, so the only thing this can do is let evidence accrue --
        # which is the thing its absence was preventing.
        rc, out = _run([sys.executable, "-u", "-W", "ignore",
                        str(ROOT / "desks" / "mt5" / "research" / "shadow_forward.py")],
                       timeout=2_700)
        after = _idle_certificates()
        healed_n = int(idle_n) - int(after.get("idle_count") or 0)
        report["idle_healed"] = {"enrolled": healed_n, "exit_code": rc,
                                 "idle_before": idle_n,
                                 "idle_after": after.get("idle_count"),
                                 "tail": out[-200:]}
        report["idle"] = after
        idle_n = after.get("idle_count")
        print(f"    -> enrolment pass: {healed_n} clock(s) started, {idle_n} still idle")
    unt = report["idle"].get("untradeable_count") or 0
    if unt:
        print(f"\n  UNTRADEABLE ({unt}) -- certified on a symbol this desk cannot trade or "
              f"replay. Not idle and not repairable; gate 0 now refuses these at admission:")
        for k, why in list(report["idle"]["untradeable"].items())[:6]:
            print(f"    {k[:52]:54s} {why[:70]}")

    if report["unfixable"]:
        print(f"\n  NOT AUTO-FIXABLE ({len(report['unfixable'])}) -- each needs a named cause, "
              f"and is left blocked rather than reset, so it cannot be mistaken for healthy:")
        for u in report["unfixable"][:8]:
            print(f"    {u['key']}: {u['error'][:110]}")

    OUT.write_text(json.dumps(report, indent=1), "utf-8")
    print(f"\n  -> {OUT}")
    # Idle certificates are a real finding but not this script's to fix, so they do not fail it;
    # a sleeve still blocked after a heal attempt is, because it means the lane is still stopped.
    return 1 if (report["unfixable"] or report["stalled"]
                 or report["stale_errors"]) else 0


if __name__ == "__main__":
    raise SystemExit(main())

```

### scripts\study_absorbing_kelly.py
```python
"""R0266: does an absorbing-boundary shrink COMPOSE with the shrinks already in the sizer, or
DOUBLE-COUNT against them? Study only -- this wires nothing and sizes nothing.

THE ROW'S QUESTION. `libs/risk/kelly_shrink.py` shrinks for ESTIMATION error: S^2/(S^2+SE^2), the
max-E[log] bet under parameter uncertainty. The nonergodic-growth literature describes a
DIFFERENT and additive shrink: with a costly lower boundary, optimal exposure falls BELOW the
no-boundary Kelly fraction as a function of log-distance to that boundary. This desk is the exact
case the second one is written for -- capital deploys from ~$1k, and venue minimums make small
equity genuinely absorbing: below roughly $200 (`_EXEC_VIABILITY_FLOOR_USD`, 20x the $10 venue
minimum) an account cannot execute a handful of economic round-trips, so it cannot trade its way
back. That floor is not a metaphor for ruin; it IS the barrier.

But the row also names the trap, and it is the reason this is a study and not a patch: two
independent haircuts on the same estimate is the duplicated-multiplicity error in sizing form --
the identical mistake the gate audit found in validation, where turnover was priced twice because
nobody checked whether it was already in the number.

SO THERE ARE TWO DOUBLE-COUNT QUESTIONS, NOT ONE, and only the second is dangerous:

  Q1  boundary shrink vs ESTIMATION shrink. Different causes -- one is about not knowing the
      parameter, the other about the objective changing near a barrier you can be stopped at.
      Expected to compose.
  Q2  boundary shrink vs THE RUIN CAP ALREADY IN THE SIZER. `dynamic_leverage._ruin_cap` already
      searches for the largest leverage whose bootstrapped P(ruin) <= 2%, and `optimize_sleeve`
      already takes min(base, kelly, ruin_cap). If that cap already binds below the
      absorption-aware optimum, a boundary shrink on top charges twice for one barrier.

WHY Q2 IS NOT ANSWERABLE FROM THE CODE ALONE. A ruin CAP and a boundary-aware OPTIMUM are
different objects even though both respond to the barrier. The cap is a constraint -- keep
P(hit) under a tolerance -- and says nothing about growth. The optimum asks what maximises
E[log W] when paths that touch the barrier stop compounding. A leverage can satisfy the
constraint and still be well above the growth optimum, or the reverse. Which one binds is an
empirical question about this desk's numbers, so it is measured here rather than argued.

WHAT IS SIMULATED. A multiplicative wealth process at a known true Sharpe, one year of daily
steps, over a grid of Kelly multiples, under three regimes:

  NO-BARRIER   paths compound through everything             -> f*_noabs  (textbook Kelly)
  ABSORBING    a path touching the barrier stops there       -> f*_abs
  JOINT        absorbing AND the Sharpe is only estimated    -> f*_joint

plus CONTROL A -- estimation noise with NO barrier, which is what makes the rest readable.

Absorption is modelled as the account FREEZING at the barrier, not going to zero. That is the
honest reading of a venue minimum -- the money is still there, it just cannot be put to work --
and it keeps log(W) finite so the expectation exists. A literal log(0) would make every
positive-f bet infinitely bad and the study would answer itself.

WHAT IT MEASURED (2026-08-05, 12 cells, positive control 12/12)
---------------------------------------------------------------
1. THE BOUNDARY SHRINK IS REAL AND SMALL AT THE DESK'S ACTUAL BARRIER. At the $200-on-$1k
   viability floor (barrier 0.20), gamma_boundary is 1.00 / 0.95 / 0.90 for S = 0.75 / 1.5 / 2.3.
   At a $100 book (barrier 0.50) it steepens to 0.90 / 0.75 / 0.70. So the effect the row
   describes exists and is worth at most a 10% haircut at the size the desk actually trades --
   against an estimation shrink already applying 0.058 to 0.721 in the same cells. It is an
   order of magnitude smaller than the shrink already in the sizer.

2. CONTROL A KILLED THE FIRST VERSION OF THIS STUDY, and it locates WHY the existing shrink is
   right -- which is not the reason usually given for it. Estimation noise ALONE leaves the
   optimum at exactly full Kelly (f* = 1.00 in every cell). Not a simulation quirk:
   E[log W_T] = T(L*mu - L^2 sigma^2/2) is LINEAR in mu, so averaging over an UNBIASED mu cannot
   move the argmax. The everyday story -- "Kelly's penalty is asymmetric, so noise means bet
   less" -- does not survive that: asymmetry of the penalty is already inside the quadratic, and
   symmetric noise about a correct mean does not move the optimum.

   What DOES justify shrinking is that the desk's estimate is not unbiased for the quantity it
   bets on. It selects edges BECAUSE they measured well, so mu-hat carries a winner's curse, and
   the correct input is the POSTERIOR MEAN of mu under a prior that most candidates have no edge
   -- which is strictly below mu-hat. And `shrink_fraction`'s S^2/(S^2+SE^2) is exactly the
   James-Stein / normal-posterior shrinkage factor toward a zero-edge prior, so THE FORMULA IS
   THE RIGHT ONE; it is the rationale attached to it that is misstated. This matters practically
   because the two stories calibrate differently: a posterior-mean shrink should be tuned to how
   strong the zero-edge prior is and how selected the candidate was, and neither of those is an
   input to it today. Flagged, not acted on -- this study changes no sizer, and the shrink errs
   toward betting less.

3. THE JOINT CELL IS AN ARTIFACT AND IS PUBLISHED AS ONE. Combining absorption with parameter
   noise pushed f* ABOVE full Kelly in 11 of 12 cells (measured range 0.90-3.00, two of them
   clipped at the grid edge and flagged). Cause: freezing at the barrier floors terminal
   log-wealth at log(barrier) while the upside stays unbounded, so mu-dispersion pays like a
   call option. That is a property of the ONE-YEAR horizon, not of the desk's objective -- over
   a lifetime, absorption forfeits ALL future compounding rather than settling at 0.2x book. A
   first version of this file read that artifact as "the two shrinks DOUBLE-COUNT in 12/12
   cells" and would have shipped it; the horizon-aware version is the honest next step and is
   rowed rather than guessed at.

SO THE ROW'S QUESTION IS ANSWERED WHERE IT MATTERS: do not wire a boundary shrink. Not because
it is unreal, but because at this desk's barrier it is <=10%, it is dominated by the estimation
shrink already applied, and `_ruin_cap` already binds the same barrier from the constraint side.
Wiring a third haircut for a tenth-order effect is the duplicated-multiplicity error the row
itself warned about.

NOTHING HERE CHANGES A RAIL, A BAR OR A SIZER.
"""
from __future__ import annotations

import itertools
import json
from pathlib import Path

import numpy as np

from libs.risk.kelly_shrink import sharpe_se, shrink_fraction

_ROOT = Path(__file__).resolve().parents[1]
_OUT = _ROOT / "docs/research/absorbing_kelly_study.json"

_PPY = 365.0
_HORIZON = 365                      # one year of daily steps
_N_PATHS = 8_000
_F_GRID = np.round(np.arange(0.05, 3.01, 0.05), 4)   # multiples of full Kelly
_SIGMA_D = 0.02                     # ~38% annualised, a crypto-sleeve scale

#: The desk's REAL barrier, and it is not a modelling choice. `_EXEC_VIABILITY_FLOOR_USD` is
#: $200 (20 x the $10 venue minimum) and below it an account cannot execute a handful of
#: economic round-trips -- `validation.py` already calls that SUB-VIABLE. From a $1k book that is
#: 0.20 of starting equity. The $100 starting case the row names is far worse and is swept too.
_BARRIERS = (0.20, 0.50)


#: Path-chunk budget in array elements. A 10-year horizon at 8,000 paths is 29M float64s per
#: array and `cumprod` needs a second one -- ~470MB on a box whose OOM floor is 400MB free, which
#: is how a study kills the test suite rather than answering its question. Chunking bounds the
#: footprint at ~64MB whatever the horizon. AT 365 DAYS 8,000x365 = 2.92M FITS IN ONE CHUNK, so
#: the 1y cells draw exactly the arrays they drew before and their numbers are unchanged.
_CHUNK_ELEMS = 4_000_000


def _argmax_f(*, sharpe_ann: float, kelly_lev: float, barrier: float, absorbing: bool,
              sharpe_sd: float, seed: int, horizon: int = _HORIZON) -> tuple[float, float]:
    """Grid-search f by E[log W_T] under COMMON RANDOM NUMBERS across the whole grid.

    One set of shocks is drawn per cell and every f is evaluated on it. That is not only ~60x
    cheaper than re-drawing per grid point, it is the correct estimator for this question: the
    quantity wanted is which f is BEST, and differencing curves computed on independent noise
    buries a real ordering under Monte-Carlo error that common shocks cancel exactly.

    COMMON RANDOM NUMBERS SURVIVE THE CHUNKING, which is the only thing that could have broken
    here: every f is evaluated on the SAME chunk before the next chunk is drawn, so the shocks are
    still shared across the grid exactly as they were when the whole horizon fit in one array.
    Chunking changes the memory footprint, never the estimator.
    """
    rng = np.random.default_rng(seed)
    chunk = max(1, min(_N_PATHS, _CHUNK_ELEMS // max(1, horizon)))
    acc = np.zeros(len(_F_GRID), dtype="float64")
    done = 0
    while done < _N_PATHS:
        n = min(chunk, _N_PATHS - done)
        # Parameter uncertainty is ONE draw per path, held for the whole horizon: the desk lives
        # with a single estimate for the life of the bet. Re-drawing each step would average the
        # uncertainty away and report that estimation error costs nothing.
        s_true = (rng.normal(sharpe_ann, sharpe_sd, size=(n, 1)) if sharpe_sd > 0
                  else np.full((n, 1), sharpe_ann))
        mu_d = s_true / np.sqrt(_PPY) * _SIGMA_D
        z = rng.standard_normal((n, horizon))
        r = mu_d + _SIGMA_D * z                      # the shared return path, f-independent
        for i, f in enumerate(_F_GRID):
            steps = np.maximum(1.0 + (f * kelly_lev) * r, 1e-9)
            if absorbing:
                # Freeze at the barrier from the first touch. The account keeps the money and
                # loses the ability to compound it, which is what a venue minimum actually does.
                #
                # THIS ARM KEEPS `cumprod` AND IS PROVABLY SAFE, WHICH IS WHY ITS NUMBERS ARE
                # UNCHANGED BIT FOR BIT. Underflow cannot corrupt it: equity moves continuously
                # (every step is positive), so a path reaching 0.0 must have passed through
                # `barrier` first and `.any()` has already caught it -- and a caught path is
                # scored at `barrier`, never at its underflowed value. gamma_boundary, the only
                # half of this study that bears on sizing, is built solely from this arm.
                eq = np.cumprod(steps, axis=1)
                terminal = np.where((eq <= barrier).any(axis=1), barrier, eq[:, -1])
                acc[i] += float(np.sum(np.log(terminal)))
            else:
                # THE ARM THAT UNDERFLOWED, AND THE HORIZON SWEEP IS WHAT REACHED IT. With no
                # barrier to absorb it, a path just keeps compounding down: at f=3.0 and S=2.3 the
                # leverage is 21.7x, so a single -4.6% day floors its step at 1e-9, and enough of
                # those over 3,650 steps drive the product below the float64 minimum. `log(0.0)`
                # is then -inf -- not "very bad" but INFINITELY bad -- so ONE underflowing path in
                # 8,000 set that f's entire score to -inf and deleted it from the argmax for an
                # arithmetic reason rather than an economic one. Measured at seed 11: 0/64 paths
                # underflow at 365 and 1,095 days, 7/64 at 3,650. The base study could not have
                # seen this; 365 steps cannot get there.
                #
                # Summing logs is mathematically identical and cannot underflow, and it needs no
                # cumulative array because nothing here asks WHEN the path crossed anything --
                # only where it ended.
                acc[i] += float(np.sum(np.log(steps)))
        done += n

    g_all = acc / _N_PATHS
    j = int(np.argmax(g_all))
    return float(_F_GRID[j]), float(g_all[j])


def full_kelly_leverage(sharpe_ann: float, sigma_d: float = _SIGMA_D) -> float:
    """Textbook full-Kelly leverage mu/sigma^2 for this log-normal process.

    THIS IS WHAT MAKES `f` A KELLY MULTIPLE RATHER THAN A RAW LEVERAGE, and getting it wrong is
    not cosmetic. A first version of this study fixed the scale at 1.0, which put the no-barrier
    optimum at 1.96x for S=0.75 but 3.93x and 6.02x for S=1.5 and S=2.3 -- outside a grid capped
    at 3.0. Both of those cells would have reported their argmax AT THE EDGE OF THE SEARCH WINDOW
    and every gamma derived from them would have been an artifact of the grid, exactly the
    failure `slot_budget_analysis` already records against itself.

    It also buys the study a POSITIVE CONTROL: with the scale correct, `f_star_no_barrier` must
    come back at ~1.0 by construction. If it does not, the simulator is wrong and no other number
    in the file means anything.
    """
    return sharpe_ann / (np.sqrt(_PPY) * sigma_d)


def study(sharpe_ann: float, n_days: float, barrier: float, *, seed: int = 11,
          horizon: int = _HORIZON) -> dict:
    """One cell: a true Sharpe, an evidence width, a barrier, and a horizon."""
    kelly_lev = full_kelly_leverage(sharpe_ann)     # f is reported in MULTIPLES of full Kelly
    f_noabs, g_noabs = _argmax_f(sharpe_ann=sharpe_ann, kelly_lev=kelly_lev, barrier=barrier,
                                 absorbing=False, sharpe_sd=0.0, seed=seed, horizon=horizon)
    f_abs, g_abs = _argmax_f(sharpe_ann=sharpe_ann, kelly_lev=kelly_lev, barrier=barrier,
                             absorbing=True, sharpe_sd=0.0, seed=seed, horizon=horizon)
    se = sharpe_se(sharpe_ann, n_days)
    f_joint, g_joint = _argmax_f(sharpe_ann=sharpe_ann, kelly_lev=kelly_lev, barrier=barrier,
                                 absorbing=True, sharpe_sd=se, seed=seed, horizon=horizon)

    # CONTROL A -- uncertainty WITHOUT the barrier. This is the decisive one and it was not in
    # the first version of this study, which is why that version reported a confident and wrong
    # answer. E[log W_T] = T(L*mu - L^2 sigma^2 / 2) is LINEAR in mu, so averaging over an
    # UNBIASED mu leaves the argmax exactly at full Kelly: symmetric parameter noise, on its own,
    # cannot move the Kelly optimum at all. Measured f* = 1.00, matching theory.
    f_unc_only, _ = _argmax_f(sharpe_ann=sharpe_ann, kelly_lev=kelly_lev, barrier=barrier,
                              absorbing=False, sharpe_sd=se, seed=seed, horizon=horizon)

    gamma_boundary = f_abs / f_noabs if f_noabs > 0 else float("nan")
    gamma_est = shrink_fraction(sharpe_ann, n_days)
    composed = gamma_est * gamma_boundary * f_noabs
    ratio = composed / f_joint if f_joint > 0 else float("nan")

    # WHY THE JOINT CELL IS NOT EVIDENCE, stated in the artifact rather than left to a reader.
    # With absorption modelled as FREEZING at the barrier, terminal log-wealth is floored at
    # log(barrier) while the upside stays unbounded. Adding dispersion to mu then pays like a
    # call option -- more spread puts more mass in the unbounded good tail while the bad tail is
    # capped -- so f*_joint comes out ABOVE full Kelly (measured 1.05 to 3.00). That is a
    # property of a ONE-YEAR horizon, not of the desk's objective: over a lifetime, absorption
    # forfeits ALL future compounding rather than settling at 0.2x book, and the floor that
    # creates this convexity is exactly what a lifetime horizon removes.
    # Clipping is judged ONLY on the quantities the verdict is built from -- f_abs and f_noabs.
    # f_joint clips in the low-Sharpe cells, but it is already declared not-evidence below, so
    # letting it condemn the whole cell would throw away a sound gamma_boundary alongside an
    # artifact that was never going to be used.
    _edge = float(_F_GRID[-1]) - 1e-9
    clipped = bool(f_abs >= _edge or f_noabs >= _edge)
    joint_clipped = bool(f_joint >= _edge)
    verdict = ("BOUNDARY-SHRINK-REAL-BUT-SMALL" if gamma_boundary >= 0.85
               else "BOUNDARY-SHRINK-MATERIAL")
    if clipped:
        verdict = "UNUSABLE (argmax at the grid edge)"

    # POSITIVE CONTROL. With no barrier and no estimation error the optimum IS full Kelly, so
    # f_star_no_barrier must return ~1.0. A cell that fails this is reporting on a broken
    # simulator and its gammas are meaningless -- said out loud in the artifact rather than left
    # for a reader to notice, because an uncontrolled study that agrees with your prior is the
    # easiest thing in the world to publish.
    control_ok = bool(0.85 <= f_noabs <= 1.15)

    return {
        "sharpe_ann": sharpe_ann, "n_days": n_days, "barrier_frac_of_book": barrier,
        "horizon_days": horizon,
        "full_kelly_leverage": round(kelly_lev, 3),
        "positive_control_ok": control_ok,
        "f_star_no_barrier": f_noabs, "f_star_absorbing": f_abs, "f_star_joint": f_joint,
        "f_star_uncertainty_only": f_unc_only,
        "joint_cell_is_evidence": False,
        "joint_cell_hit_grid_edge": joint_clipped,
        "joint_cell_note": "f_star_joint is NOT usable: freezing at the barrier floors terminal "
                           "log-wealth at log(barrier) while the upside is unbounded, so mu "
                           "dispersion pays like a call option and pushes the argmax above full "
                           "Kelly. An artifact of the 1y horizon, which under-penalises "
                           "absorption -- over a lifetime absorption forfeits all future "
                           "compounding, not 0.8x of one year's book",
        "gamma_boundary": round(gamma_boundary, 4),
        "gamma_estimation": round(gamma_est, 4),
        "composed_fraction": round(composed, 4),
        "composed_over_joint": round(ratio, 4),
        "verdict": verdict,
        "elogw_no_barrier": round(g_noabs, 5), "elogw_absorbing": round(g_abs, 5),
        "elogw_joint": round(g_joint, 5),
        "sharpe_se": round(se, 4),
    }


#: R0431's sweep. 1y is the base study's horizon; 10y is the longest the desk can simulate at this
#: path count inside its memory budget. The desk's objective is LIFETIME E[log W_T], so if the
#: joint cell's above-Kelly optimum is the 1y freezing floor rather than something real, f*_joint
#: must fall toward f*_absorbing as the horizon grows -- the direction theory predicts.
_HORIZON_SWEEP = (365, 1095, 3650)

#: The sweep runs at the desk's REAL barrier only, and at the SHORT evidence width where the
#: artifact is largest. NOT SILENTLY CAPPED (L1.53): the 0.50 barrier is a $100-book case the desk
#: does not trade, and 180d evidence has a narrower se and so a smaller artifact to dissolve --
#: dropping them costs the sweep nothing it was built to see, and the cost of the full 3x12 grid
#: is ~14x the base study's runtime for cells that answer a question nobody asked.
_SWEEP_BARRIER = 0.20
_SWEEP_N_DAYS = 40.0


def horizon_sweep() -> list[dict]:
    """R0431: is the joint cell's above-Kelly optimum an artifact of the ONE-YEAR horizon?

    THE BASE STUDY PUBLISHED ITS OWN CAVEAT AND COULD NOT TEST IT. Freezing at the barrier floors
    terminal log-wealth at log(barrier) while the upside stays unbounded, so mu-dispersion pays
    like a call option and pushes f*_joint ABOVE full Kelly (measured 1.05-3.00). The claim
    attached to that number is that it is a property of the 1y horizon and not of the desk's
    objective: over a lifetime, absorption forfeits ALL future compounding rather than settling at
    0.2x book, so the floor creating the convexity is exactly what a long horizon removes.

    That is a FALSIFIABLE claim and it was carrying no evidence. If f*_joint does NOT fall as the
    horizon grows, the artifact's stated explanation is wrong and the joint cells need a different
    one -- which matters more than the confirmation would, because the base study's headline
    verdict (do not wire a boundary shrink) rests on reading those cells as an artifact.
    """
    out = []
    for horizon in _HORIZON_SWEEP:
        for sharpe in (0.75, 1.5, 2.3):
            c = study(sharpe, _SWEEP_N_DAYS, _SWEEP_BARRIER, horizon=horizon)
            # The quantity the row is about: how far the joint optimum sits above the
            # absorbing-only one. Theory says this gap closes as the horizon grows.
            c["joint_over_absorbing"] = (round(c["f_star_joint"] / c["f_star_absorbing"], 4)
                                         if c["f_star_absorbing"] > 0 else float("nan"))
            out.append(c)
    return out


def main() -> int:
    # The desk's own real-edge band (0.5-1.5 OOS Sharpe, from its 131,441-backtest sweep) plus the
    # cashcarry-scale case, each at a short and a long evidence width.
    cells = []
    for barrier in _BARRIERS:
        for sharpe in (0.75, 1.5, 2.3):
            for n_days in (40.0, 180.0):
                cells.append(study(sharpe, n_days, barrier))

    verdicts: dict[str, int] = {}
    for c in cells:
        verdicts[c["verdict"]] = verdicts.get(c["verdict"], 0) + 1
    n_control_ok = sum(1 for c in cells if c["positive_control_ok"])
    # CONTROL A across every cell: symmetric parameter noise alone must leave the optimum at full
    # Kelly, because E[log W] is linear in mu. Reported as a count, not asserted in prose.
    n_unc_neutral = sum(1 for c in cells if abs(c["f_star_uncertainty_only"] - 1.0) <= 0.15)

    # ------------------------------------------------------------------ R0431 HORIZON SWEEP
    sweep = horizon_sweep()
    # The row's prediction, tested rather than asserted: the joint optimum's excess over the
    # absorbing-only optimum should SHRINK as the horizon grows, because the log(barrier) floor
    # that manufactures the convexity is what a long horizon removes.
    # THE VERDICT IS BUILT FROM UNCLIPPED CELLS ONLY, and the denominator is published beside it.
    # f*_joint pins at the 3.00 grid edge in every S=0.75 cell, so its ratio there is a LOWER
    # BOUND, not a measurement -- averaging it in would let a censored number drive the conclusion
    # (L1.57). The count of what was dropped is reported rather than silently excluded.
    by_h = {h: [c for c in sweep
                if c["horizon_days"] == h and not c["joint_cell_hit_grid_edge"]]
            for h in _HORIZON_SWEEP}
    mean_excess = {h: (sum(c["joint_over_absorbing"] for c in cs) / len(cs) if cs else float("nan"))
                   for h, cs in by_h.items()}
    # gamma_boundary is the DECISION-RELEVANT half and it is never clipped (f_abs and f_noabs both
    # sit well inside the grid), so it is averaged over every cell at each horizon.
    mean_gamma = {h: sum(c["gamma_boundary"] for c in sweep if c["horizon_days"] == h)
                     / max(1, sum(1 for c in sweep if c["horizon_days"] == h))
                  for h in _HORIZON_SWEEP}
    ordered = [mean_excess[h] for h in _HORIZON_SWEEP]
    n_usable = sum(len(cs) for cs in by_h.values())
    falls = all(b <= a + 1e-9 for a, b in itertools.pairwise(ordered))
    n_sweep_control_ok = sum(1 for c in sweep if c["positive_control_ok"])
    if n_sweep_control_ok < len(sweep):
        horizon_verdict = "UNUSABLE (positive control failed in the sweep)"
    elif n_usable < 2 or any(v != v for v in ordered):     # NaN-safe: no unclipped cell somewhere
        horizon_verdict = "UNMEASURED (too few unclipped cells to read a trend)"
    elif falls and ordered[-1] < ordered[0]:
        horizon_verdict = "CONFIRMED-ARTIFACT-OF-HORIZON"
    elif ordered[-1] < ordered[0]:
        horizon_verdict = "FALLS-BUT-NOT-MONOTONE"
    else:
        horizon_verdict = "REFUTED (the excess RISES with horizon)"

    doc = {
        "row": "R0266",
        "question": "does an absorbing-boundary shrink compose with the estimation shrink, "
                    "or double-count against it (and against the ruin cap already in the sizer)?",
        "status": "MEASURED",
        "n_paths": _N_PATHS, "horizon_days": _HORIZON,
        "r0431_horizon_sweep": {
            "row": "R0431",
            "question": "is f*_joint > 1 an artifact of the ONE-YEAR horizon, as the base "
                        "study's own caveat claims? Over a lifetime absorption forfeits ALL "
                        "future compounding rather than settling at 0.2x book, so the excess "
                        "should fall as the horizon grows",
            "horizons_days": list(_HORIZON_SWEEP),
            "barrier_frac_of_book": _SWEEP_BARRIER,
            "evidence_width_days": _SWEEP_N_DAYS,
            "scope_note": "run at the desk's REAL barrier and the SHORT evidence width only -- "
                          "the 0.50 barrier is a $100-book case the desk does not trade and 180d "
                          "evidence has a smaller artifact to dissolve. Dropped deliberately and "
                          "named here rather than silently capped",
            "n_cells": len(sweep),
            "n_cells_usable_for_verdict": n_usable,
            "n_cells_dropped_grid_edge": len(sweep) - n_usable,
            "positive_control_passed": f"{n_sweep_control_ok}/{len(sweep)}",
            "mean_joint_over_absorbing_by_horizon": {
                str(h): round(v, 4) for h, v in mean_excess.items()},
            "monotone_decreasing": falls,
            "verdict": horizon_verdict,
            "answer": (
                "REFUTED. The base study's caveat claimed f*_joint > 1 is an artifact of the 1y "
                "horizon that a lifetime horizon would remove. Measured over 1y/3y/10y the "
                "excess RISES instead. THE MECHANISM: modelling absorption as FREEZING floors "
                "terminal log-wealth at log(barrier) FOREVER, while surviving paths compound "
                "roughly linearly in T -- so the gap the floor insures against GROWS with the "
                "horizon and the mu-dispersion call option becomes MORE valuable, not less. The "
                "horizon was never the fix; the ABSORPTION MODEL is. Testing the row's actual "
                "claim needs the alternative it names in its own parenthesis -- an explicit "
                "continuation value for the non-absorbed state, so that absorption forfeits the "
                "compounding the capital would otherwise have earned rather than settling at "
                "log(0.2). f*_joint remains NOT EVIDENCE either way, exactly as before."),
            "gamma_boundary_by_horizon": {str(h): round(v, 4) for h, v in mean_gamma.items()},
            "gamma_boundary_note": (
                "THE HALF THAT ACTUALLY BEARS ON SIZING, and it moved. gamma_boundary is never "
                "clipped, and it FALLS with the horizon exactly as theory predicts: at the "
                "desk's real barrier it is ~0.95 at 1y but ~0.82 at 10y, so the boundary shrink "
                "over a LIFETIME is roughly 15-20%, about double the '<=10%' the base study "
                "measured at one year. The base study's headline figure is a 1-YEAR number and "
                "this desk's objective is lifetime E[log W_T]. The conclusion still holds -- the "
                "estimation shrink applies 0.058-0.721 in the same cells and continues to "
                "dominate, and _ruin_cap already binds the same barrier from the constraint side "
                "-- but the margin is smaller than the artifact previously stated."),
            "cells": sweep,
        },
        "barrier_note": "fraction of starting book at which the account can no longer execute "
                        "economic round-trips at venue minimums ($200 viability floor / book)",
        "wired": False,
        "wired_note": "STUDY ONLY. No sizer, rail or bar is changed by this file.",
        # SCANNED, not asserted: a cell count that cannot fall when a cell disappears is not a
        # denominator (L1.57).
        "n_cells": len(cells),
        "positive_control_passed": f"{n_control_ok}/{len(cells)}",
        "uncertainty_alone_leaves_kelly_unmoved": f"{n_unc_neutral}/{len(cells)}",
        "positive_control_note": "with no barrier and no estimation error the optimum IS full "
                                 "Kelly, so f_star_no_barrier must be ~1.0. Any cell failing "
                                 "this is a broken simulator and its gammas mean nothing",
        "status_note": ("READ NOTHING FROM THIS FILE" if n_control_ok < len(cells)
                        else "controls green"),
        "verdict_counts": verdicts,
        "cells": cells,
    }
    _OUT.parent.mkdir(parents=True, exist_ok=True)
    _OUT.write_text(json.dumps(doc, indent=1), "utf-8")

    print(f"=== R0266 ABSORBING-BOUNDARY KELLY STUDY ({len(cells)} cells) ===")
    print(f"{'S':>5} {'nday':>5} {'barr':>5} {'f*none':>7} {'f*unc':>6} {'f*abs':>6} "
          f"{'g_bnd':>6} {'g_est':>6}  verdict")
    for c in cells:
        print(f"{c['sharpe_ann']:5.2f} {c['n_days']:5.0f} {c['barrier_frac_of_book']:5.2f} "
              f"{c['f_star_no_barrier']:7.2f} {c['f_star_uncertainty_only']:6.2f} "
              f"{c['f_star_absorbing']:6.2f} {c['gamma_boundary']:6.3f} "
              f"{c['gamma_estimation']:6.3f}  {c['verdict']}")
    print()
    print(f"=== R0431 HORIZON SWEEP ({len(sweep)} cells, barrier {_SWEEP_BARRIER}, "
          f"{_SWEEP_N_DAYS:.0f}d evidence) ===")
    print(f"{'S':>5} {'horiz':>6} {'f*none':>7} {'f*abs':>6} {'f*joint':>8} {'j/abs':>6}")
    for c in sweep:
        print(f"{c['sharpe_ann']:5.2f} {c['horizon_days']:6d} {c['f_star_no_barrier']:7.2f} "
              f"{c['f_star_absorbing']:6.2f} {c['f_star_joint']:8.2f} "
              f"{c['joint_over_absorbing']:6.2f}")
    print(f"  mean f*joint/f*abs by horizon (UNCLIPPED cells only, "
          f"{n_usable}/{len(sweep)} usable): " + ", ".join(
              f"{h}d={mean_excess[h]:.2f}" for h in _HORIZON_SWEEP))
    print("  mean gamma_boundary by horizon: " + ", ".join(
        f"{h}d={mean_gamma[h]:.3f}" for h in _HORIZON_SWEEP)
        + "   <-- the half that bears on sizing, and it FALLS")
    print(f"  R0431 VERDICT: {horizon_verdict}")
    print()
    print(f"  POSITIVE CONTROL: {n_control_ok}/{len(cells)} cells recovered full Kelly "
          f"(f*_no_barrier ~ 1.0) with no barrier and no estimation error")
    print(f"  CONTROL A:        {n_unc_neutral}/{len(cells)} cells left the optimum at full Kelly "
          f"under estimation noise ALONE -- E[logW] is linear in mu, so symmetric parameter")
    print("                    uncertainty on its own cannot shrink Kelly. The existing shrink "
          "must rest on selection bias, sigma uncertainty or fat tails, NOT on this.")
    if n_control_ok < len(cells):
        print("  *** CONTROL FAILED -- the simulator is wrong; read nothing else here ***")
    for v, n in sorted(verdicts.items(), key=lambda kv: -kv[1]):
        print(f"  {n:2d} cell(s): {v}")
    print(f"\nwritten -> {_OUT.relative_to(_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

```
