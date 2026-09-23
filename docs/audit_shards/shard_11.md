# AUDIT SHARD 11/24 -- seat sakana/fugu-ultra-v2

You are reviewing SOURCE CODE, not a summary. Previous panels received a 13,185-char self-description and never saw the code; that is why this exists.

- TIER 1 (money path) is included IN FULL and is sent to every seat: 44 files. A defect here costs money.
- TIER 2 is YOUR SHARD ALONE: 11 files. No other seat sees these, so anything you miss here is missed entirely.
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

### libs\data\asymmetry.py
```python
"""INFORMATION ASYMMETRY -- not "have we looked at this source", but "does anyone else have it".

THE GAP THIS FILLS, STATED AGAINST THE ORGAN THAT ALREADY EXISTS. `scripts/info_class_map.py`
maps MODALITY x ACCESS across 33 classes and answers "has the desk visited this carrier". It is a
breadth map and a good one. It has no axis for asymmetry, so it files two sources identically that
could not be more different in edge terms:

    exchange_api_ohlcv   "covered"   -- and every participant on earth has the identical bytes
    orderbook_l2         "covered"   -- self-recorded, and NOBODY else has this exact tape

Both read as green. One is infrastructure and one is the only genuinely proprietary asset the desk
owns. A coverage map that cannot tell them apart will keep directing effort at sources whose
information is already in the price, which is the most expensive way to look busy.

THE TAXONOMY IS ABOUT WHY A COMPETITOR CANNOT HAVE IT, because that is the only thing that
survives contact with a market:

  EXCLUSIVE       nobody else holds it and it CANNOT be reconstructed after the fact. Self-recorded
                  L2 tape, own fills, own research corpus. The strongest and the rarest, and the
                  only kind that does not decay by being used.
  RECONSTRUCTIBLE public raw material that requires real work to assemble. Wallet clustering,
                  entity graphs, mempool history. Everyone COULD have it; almost nobody does. The
                  asymmetry is in the PROCESSING, not the access -- which means it is bought with
                  engineering rather than with money, and is the class a small desk should hunt.
  PERISHABLE      public to all, valuable only inside a window. Mempool state, funding at
                  settlement. The asymmetry is LATENCY, and it is a race the desk will usually
                  lose to colocated firms -- worth holding only where the window is minutes.
  INTERPRETIVE    everyone has the raw data; the claim is a better model of it. The weakest form,
                  and the most self-flattering to assert. Almost every losing retail strategy
                  believes it is here.
  COMMODITY       everyone has it and processes it identically. OHLCV, headline funding. Necessary
                  infrastructure, never edge. Naming it as such is what stops it being counted.

ASYMMETRY DECAYS AND THE LEDGER MUST SAY SO. A source that is RECONSTRUCTIBLE today is COMMODITY
once a vendor productises it; the desk's own graveyard has vendor-replacement entries that are
exactly this transition. Every claim therefore carries a `verified` date and expires, and an
expired claim is reported as UNVERIFIED rather than silently believed -- the desk's own recurring
failure is reading "not measured" as "measured and fine", and a stale asymmetry claim is that
failure applied to the one thing that supposedly justifies the whole enterprise.

AND A CLAIM MUST BE EVIDENCED. `why_not_replicable` is REQUIRED for EXCLUSIVE and RECONSTRUCTIBLE.
A desk telling itself its data is special, with no stated reason a competitor cannot obtain it, is
the failure mode this module exists to prevent -- so the constructor refuses it rather than
recording a wish.

BREADTH AND DEPTH ARE DIFFERENT AXES AND BOTH ARE TRACKED. Breadth is how many asymmetric sources
exist; depth is how far each has actually been mined. A desk with twenty sources at depth 1 knows
less than one with three at depth 5, and only tracking breadth makes the first look better.

Pure stdlib + dataclasses. No I/O.
"""

from __future__ import annotations

import contextlib
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from libs.core.coerce import finite_float

__all__ = [
    "ASYMMETRY_AXES",
    "ASYMMETRY_CLASSES",
    "DEPTH_LEVELS",
    "REPLICATION_FACTORS",
    "SELF_FOOTPRINT_FIELDS",
    "AsymmetrySource",
    "Portfolio",
    "asymmetry_weight",
    "information_advantage_frontier",
    "replication_cost_profile",
    "requires_evidence",
    "self_footprint_coverage",
]

#: class -> (edge weight, how long a claim stays fresh in days). Weights are ORDINAL, not a
#: forecast: they rank where effort should go, and multiplying them by an expected return would be
#: inventing a number. Half-lives differ because a self-recorded tape does not stop being
#: exclusive, while a processing advantage erodes as soon as somebody productises it.
ASYMMETRY_CLASSES: dict[str, tuple[float, int]] = {
    "EXCLUSIVE": (1.00, 365),
    "RECONSTRUCTIBLE": (0.70, 180),
    "PERISHABLE": (0.40, 90),
    "INTERPRETIVE": (0.15, 90),
    "COMMODITY": (0.00, 3650),
}

#: Classes whose asymmetry claim must state WHY a competitor cannot replicate it.
requires_evidence = ("EXCLUSIVE", "RECONSTRUCTIBLE")

#: How far a source has actually been mined. The rungs are deliberately about ARTEFACTS, not
#: effort: "we looked at it a lot" is not a depth.
DEPTH_LEVELS: dict[int, str] = {
    0: "UNTOUCHED -- named only",
    1: "SAMPLED -- pulled by hand at least once, nothing persisted",
    2: "COLLECTED -- a collector runs and history accumulates",
    3: "STRUCTURED -- parsed into features with a schema and a causal guard",
    4: "SCREENED -- features have been through stage A and the verdicts are recorded",
    5: "EXHAUSTED -- screened, and the negative results are in the graveyard with mechanisms",
}


@dataclass(frozen=True)
class AsymmetrySource:
    """One source, on both axes, with the evidence for its claim and an expiry on that claim."""

    name: str
    asymmetry: str
    depth: int
    verified: str  # ISO date the asymmetry claim was last checked
    why_not_replicable: str = ""
    note: str = ""
    owner: str = ""

    def __post_init__(self) -> None:
        if self.asymmetry not in ASYMMETRY_CLASSES:
            raise ValueError(
                f"{self.name}: unknown asymmetry class {self.asymmetry!r}. "
                f"Use one of {sorted(ASYMMETRY_CLASSES)}"
            )
        if self.depth not in DEPTH_LEVELS:
            raise ValueError(f"{self.name}: depth must be one of {sorted(DEPTH_LEVELS)}")
        if self.asymmetry in requires_evidence and not self.why_not_replicable.strip():
            raise ValueError(
                f"{self.name}: {self.asymmetry} requires `why_not_replicable`. A desk telling "
                "itself its data is special, with no stated reason a competitor cannot obtain "
                "it, is recording a wish rather than an asset -- and it is the single most "
                "comfortable error available in this file."
            )
        try:
            datetime.fromisoformat(self.verified)
        except ValueError as e:
            raise ValueError(f"{self.name}: `verified` must be an ISO date -- {e}") from None

    @property
    def stale(self) -> bool:
        """Has the asymmetry claim outlived its half-life without re-verification?"""
        _, days = ASYMMETRY_CLASSES[self.asymmetry]
        return datetime.fromisoformat(self.verified).replace(tzinfo=UTC) < (
            datetime.now(tz=UTC) - timedelta(days=days)
        )

    @property
    def effective_class(self) -> str:
        """UNVERIFIED once the claim is stale. NEVER silently the class it used to be."""
        return "UNVERIFIED" if self.stale else self.asymmetry

    @property
    def weight(self) -> float:
        """Edge weight, zero while unverified -- an expired claim earns nothing until rechecked."""
        return 0.0 if self.stale else ASYMMETRY_CLASSES[self.asymmetry][0]

    @property
    def realised(self) -> float:
        """Asymmetry ACTUALLY REALISED = weight x depth fraction.

        Holding exclusive data at depth 0 realises nothing. This is the number that matters and
        the one a breadth-only map cannot express: it is the product, and a zero in either factor
        zeroes it. The desk's 8.2GB of self-recorded tape scored maximum asymmetry and depth 2 for
        months, which is a rounding error away from not having it.
        """
        return self.weight * (self.depth / max(DEPTH_LEVELS))


def asymmetry_weight(cls: str) -> float:
    return ASYMMETRY_CLASSES.get(cls, (0.0, 0))[0]


@dataclass(frozen=True)
class Portfolio:
    """The desk's asymmetric holdings, on both axes at once."""

    sources: tuple[AsymmetrySource, ...] = field(default=())

    def by_class(self) -> dict[str, list[AsymmetrySource]]:
        out: dict[str, list[AsymmetrySource]] = {}
        for s in self.sources:
            out.setdefault(s.effective_class, []).append(s)
        return out

    @property
    def breadth(self) -> int:
        """How many sources carry a LIVE, non-commodity asymmetry claim."""
        return sum(1 for s in self.sources if s.effective_class not in ("COMMODITY", "UNVERIFIED"))

    @property
    def mean_depth(self) -> float:
        live = [s for s in self.sources if s.effective_class != "COMMODITY"]
        return sum(s.depth for s in live) / len(live) if live else 0.0

    @property
    def realised_total(self) -> float:
        return sum(s.realised for s in self.sources)

    def stale_claims(self) -> list[AsymmetrySource]:
        return [s for s in self.sources if s.stale and s.asymmetry != "COMMODITY"]

    def shallow_gold(self) -> list[AsymmetrySource]:
        """High asymmetry, low depth -- the desk's most expensive waste.

        These are the sources where the hard part is already done (the data is genuinely hard for
        a competitor to get) and the easy part is not (nobody has mined it). Ranked FIRST for
        effort, ahead of acquiring anything new: buying a second asymmetric source while the first
        sits at depth 1 grows breadth and shrinks realised asymmetry.
        """
        return sorted(
            (
                s
                for s in self.sources
                if s.weight >= ASYMMETRY_CLASSES["RECONSTRUCTIBLE"][0] and s.depth <= 2
            ),
            key=lambda s: (-s.weight, s.depth),
        )


ASYMMETRY_AXES = (
    "temporal",
    "latency",
    "geographic",
    "language",
    "semantic",
    "structural",
    "participant_constraint",
    "market_knowledge",
    "data_cleaning",
    "entity_resolution",
    "archival",
    "computational",
    "cross_domain_synthesis",
    "cross_venue",
    "execution",
    "capital_size",
    "liquidity",
    "regulatory_timing",
    "information_diffusion",
)

REPLICATION_FACTORS = (
    "source_breadth",
    "historical_depth",
    "data_cleaning",
    "entity_resolution",
    "compute",
    "specialist_knowledge",
    "latency",
    "engineering",
    "endogenous_history",
    "calibration_history",
)

SELF_FOOTPRINT_FIELDS: dict[str, tuple[str, ...]] = {
    "orders_submitted": ("order_submitted",),
    "orders_cancelled": ("order_cancelled", "cancelled"),
    "fills": ("order_filled", "fill_price", "filled"),
    "partial_fills": ("partial_fill", "partial"),
    "rejected_orders": ("order_rejected", "order_failed", "rejected"),
    "queue_estimates": ("queue_ahead", "queue_position"),
    "slippage": ("slippage", "cost_bps"),
    "latency": ("latency", "timestamps"),
    "market_impact": ("market_impact", "impact_bps"),
    "venue_response": ("venue_response", "broker_order_id", "mt5_ticket"),
    "signal_state": ("signal_state", "signal"),
    "portfolio_state": ("portfolio_state", "positions"),
    "capital_state": ("capital_state", "equity", "deployable"),
    "model_disagreement": ("model_disagreement", "model_votes"),
    "realized_vs_expected": ("expected", "realised", "realized"),
    "research_decisions": ("research_decision", "hypothesis", "decision"),
}


def replication_cost_profile(factors: Mapping[str, object]) -> dict[str, object]:
    """Aggregate explicit 0..1 reverse-engineering barriers without inventing hidden weights."""
    measured: dict[str, float] = {}
    invalid = []
    for name in REPLICATION_FACTORS:
        value = factors.get(name)
        if value is None:
            continue
        if not isinstance(value, (int, float)) or not 0 <= float(value) <= 1:
            invalid.append(name)
            continue
        measured[name] = float(value)
    if not measured:
        return {
            "status": "UNMEASURED",
            "reason": "no explicit normalized replication factors",
            "missing": list(REPLICATION_FACTORS),
        }
    return {
        "status": "MEASURED" if len(measured) == len(REPLICATION_FACTORS) else "PARTIALLY_MEASURED",
        "replication_difficulty": sum(measured.values()) / len(measured),
        "hardest_factor": max(measured, key=lambda name: measured[name]),
        "weakest_factor": min(measured, key=lambda name: measured[name]),
        "factors": measured,
        "missing": [name for name in REPLICATION_FACTORS if name not in measured],
        "invalid": invalid,
        "weighting": "equal weight over supplied factors; no missing factor is imputed",
    }


def information_advantage_frontier(
    candidates: Sequence[Mapping[str, object]], *, as_of: str | datetime | None = None
) -> dict[str, object]:
    """Rank legally obtainable information moats on the mandate's multiplicative objective."""
    now = (
        as_of
        if isinstance(as_of, datetime)
        else datetime.fromisoformat(as_of)
        if as_of
        else datetime.now(tz=UTC)
    )
    if now.tzinfo is None:
        now = now.replace(tzinfo=UTC)
    rows = []
    required = (
        "economic_usefulness",
        "persistence",
        "independence",
        "actionability",
    )
    for candidate in candidates:
        row = {"id": candidate.get("id", candidate.get("name"))}
        if candidate.get("lawfully_obtainable") is not True:
            rows.append(
                {
                    **row,
                    "status": "INELIGIBLE_OR_LEGAL_REVIEW_REQUIRED",
                    "priority_score": None,
                }
            )
            continue
        replication = candidate.get("replication_difficulty")
        raw_factors = candidate.get("replication_factors")
        profile = replication_cost_profile(raw_factors if isinstance(raw_factors, Mapping) else {})
        if not isinstance(replication, (int, float)):
            replication = profile.get("replication_difficulty")
        values = {name: candidate.get(name) for name in required}
        values["replication_difficulty"] = replication
        if not all(
            isinstance(value, (int, float)) and 0 <= float(value) <= 1 for value in values.values()
        ):
            rows.append(
                {
                    **row,
                    "status": "UNMEASURED",
                    "missing_or_invalid": [
                        name
                        for name, value in values.items()
                        if not isinstance(value, (int, float)) or not 0 <= float(value) <= 1
                    ],
                    "replication_profile": profile,
                    "priority_score": None,
                }
            )
            continue
        decay = 1.0
        verified = candidate.get("verified_at")
        half_life = candidate.get("half_life_days")
        if verified and isinstance(half_life, (int, float)) and float(half_life) > 0:
            with contextlib.suppress(ValueError):
                stamp = datetime.fromisoformat(str(verified).replace("Z", "+00:00"))
                if stamp.tzinfo is None:
                    stamp = stamp.replace(tzinfo=UTC)
                age_days = max(0.0, (now - stamp).total_seconds() / 86400)
                decay = 0.5 ** (age_days / float(half_life))
        adjusted = {name: finite_float(value) for name, value in values.items()}
        adjusted["persistence"] *= decay
        moat_value = math.prod(adjusted.values())
        cost = candidate.get("acquisition_research_cost")
        priority = (
            moat_value / float(cost) if isinstance(cost, (int, float)) and float(cost) > 0 else None
        )
        capacity = candidate.get("capacity")
        desk_capital = candidate.get("desk_capital")
        institution_floor = candidate.get("institutional_minimum_capacity")
        small_scale = (
            finite_float(capacity) >= finite_float(desk_capital)
            and finite_float(capacity) < finite_float(institution_floor)
            if all(
                isinstance(value, (int, float)) and not isinstance(value, bool)
                for value in (capacity, desk_capital, institution_floor)
            )
            else None
        )
        rows.append(
            {
                **row,
                "status": "MEASURED",
                "asymmetry_class": candidate.get("asymmetry_class"),
                "components": adjusted,
                "moat_value": moat_value,
                "acquisition_research_cost": cost,
                "priority_score": priority,
                "small_scale_structural_fit": small_scale,
                "replication_profile": profile,
                "decay_multiplier": decay,
                "state_recipe": candidate.get("state_recipe", []),
            }
        )
    rows.sort(
        key=lambda row: (
            row.get("priority_score") is None,
            -finite_float(row.get("priority_score")),
            str(row.get("id")),
        )
    )
    represented = sorted(
        {str(row.get("asymmetry_class")) for row in rows if row.get("asymmetry_class") is not None}
    )
    return {
        "status": "MEASURED" if candidates else "UNMEASURED",
        "candidates": rows,
        "asymmetry_axes": list(ASYMMETRY_AXES),
        "represented_axes": represented,
        "missing_axes": [name for name in ASYMMETRY_AXES if name not in represented],
        "objective": (
            "economic usefulness x persistence x independence x actionability x "
            "replication difficulty"
        ),
        "authority": "RESEARCH PRIORITY ONLY -- law, evidence, cost and survival rails remain",
    }


def self_footprint_coverage(
    records: Sequence[Mapping[str, object]],
) -> dict[str, object]:
    """Measure preservation of endogenous observations that no external source can recreate."""
    counts = dict.fromkeys(SELF_FOOTPRINT_FIELDS, 0)
    stamps: list[datetime] = []
    for record in records:
        blob = repr(record).casefold()
        for name, aliases in SELF_FOOTPRINT_FIELDS.items():
            if any(alias.casefold() in blob for alias in aliases):
                counts[name] += 1
        for time_field in ("timestamp", "at", "_taped", "opened", "closed", "generated"):
            if record.get(time_field):
                with contextlib.suppress(ValueError):
                    stamp = datetime.fromisoformat(str(record[time_field]).replace("Z", "+00:00"))
                    if stamp.tzinfo is None:
                        stamp = stamp.replace(tzinfo=UTC)
                    stamps.append(stamp)
                    break
    covered = sum(value > 0 for value in counts.values())
    return {
        "status": "MEASURED" if records else "UNMEASURED",
        "records": len(records),
        "coverage": covered / len(counts) if counts else None,
        "covered_fields": [name for name, value in counts.items() if value > 0],
        "missing_fields": [name for name, value in counts.items() if value == 0],
        "observations_by_field": counts,
        "history_days": (
            (max(stamps) - min(stamps)).total_seconds() / 86400 if len(stamps) >= 2 else None
        ),
        "compounding": (
            "append-only endogenous history; missing past observations cannot be backfilled"
        ),
        "authority": "MOAT COVERAGE ONLY -- no execution or promotion authority",
    }

```

### libs\execution\carry_accounting.py
```python
"""Self-healing spot-realized accounting for the delta-neutral cash-and-carry book.

The book banks each CLOSED spot leg's realized PnL in ``realized_spot_pnl`` -- the sell proceeds sit
in the spot wallet where open-position marks can't see them, while the matching perp leg's realized
stays inside the futures-equity delta. Historically this was a hand-maintained accumulator
(incremented at each close), which is FRAGILE: a stale/crashed executor, or duplicate close-logs
during a flatten, let it silently drift. Because the perp side IS captured, any drift fabricates a
one-sided loss on the dashboard (the 2026-07-10 phantom: a ~breakeven book showed -$865 on the 3x
levered lab).

Permanent fix -- derive it from EXCHANGE GROUND TRUTH every cycle instead of trusting the
accumulator. For a delta-neutral carry each closed leg satisfies ``price_pnl = spot_real +
perp_real`` and the venue's own ``REALIZED_PNL`` income equals ``sum(perp_real)``. Therefore::

    spot_realized = sum(price_pnl over closed carries) - venue_realized_pnl

The venue term is EXACT; the basis term (``sum(price_pnl)``, ~0 for a tight hedge) comes from the
trade log, deduped by ``(symbol, opened)`` so duplicate close-logs never double-count. Substituting
into ``net = spot_open + spot_realized + (fut_eq - start_eq)`` the venue-realized term cancels, so
``net = spot_open + basis + funding - fees`` -- the true economic PnL, which cannot be faked.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any

from pydantic import BaseModel, ConfigDict


def read_income(
    fetch: Callable[[], Any],
    *,
    attempts: int = 3,
    sleeper: Callable[[float], None] = time.sleep,
) -> dict[str, Any] | None:
    """Venue income summary, or ``None`` when it cannot be read -- NEVER a zero-filled dict.

    UNKNOWN IS NOT ZERO. This exists because on 2026-07-26 the venue's ``/fapi/v1/income``
    endpoint returned HTTP 502 for hours while the executor's ``_safe()`` context swallowed the
    error and left ``funding`` at its initialised ``0.0``. The primary book then published a
    $0.00 harvest -- against a ground truth of $101.96 that the molded book had recorded two
    hours earlier -- and the carry-leak alarm divided by that fabricated zero to declare an
    ``inf%`` total bleed. An outage was rendered as an economic verdict.

    That is the same failure SHAPE as the 2026-07-19 stranded-inventory incident (GAP row 34),
    where ``_safe()`` made a rejected order indistinguishable from a filled one. That incident
    was fixed on the ORDER path (``_filled``) and left standing on the MEASUREMENT path.

    Reads are idempotent, so a transient 5xx is retried. Orders are deliberately NOT retried
    this way (see ``libs/execution/retry``) -- a duplicate GET is free, a duplicate POST is a
    second position. Every failure class collapses to ``None`` on purpose: the caller's only
    honest question is "did this measure or not", and a partially-parsed dict is not a
    measurement.
    """
    for attempt in range(1, attempts + 1):
        try:
            out = fetch()
        except Exception:                              # any venue/transport failure = unmeasured
            if attempt < attempts:
                sleeper(1.0 * attempt)
                continue
            return None
        return out if isinstance(out, dict) else None
    return None


def dedup_basis(trades: list[dict[str, Any]]) -> float:
    """Sum ``price_pnl`` over closed carries, deduped by ``(symbol, opened)``.

    A single carry closes once; the executor can log the same close several times (reconcile retries
    or a flatten), so keep one record per ``(symbol, opened)`` to avoid double-counting basis.
    """
    seen: dict[tuple[Any, Any], float] = {}
    for t in trades:
        if t.get("event") == "close":
            try:
                seen[(t.get("symbol"), t.get("opened"))] = float(t.get("price_pnl", 0.0) or 0.0)
            except (TypeError, ValueError):
                continue
    return round(sum(seen.values()), 2)


def derive_spot_realized(venue_realized_pnl: float, trades: list[dict[str, Any]]) -> float:
    """Exchange-anchored spot realized PnL = deduped basis - venue futures REALIZED_PNL.

    ``venue_realized_pnl`` is the cumulative futures realized (``income_summary`` ``realized_pnl``)
    since the book's inception -- exact and un-fakeable. Robust to executor restarts/crashes and
    duplicate close-logs; degrades gracefully if the trade log is trimmed (basis is small).
    """
    try:
        vr = float(venue_realized_pnl)
    except (TypeError, ValueError):
        vr = 0.0
    return round(dedup_basis(trades) - vr, 2)


class FuturesLegReconciliation(BaseModel):
    """Two independent measurements of the SAME futures leg, and their disagreement.

    Measured 2026-08-05: the primary carry book published ``net_pnl +2938.01`` while the venue's
    own income ledger said the futures leg was ``-4791.09`` since inception. The gap was
    ``+4807.75``, the book's ONLY deployed sleeve read as profitable while it had lost $1,869.74,
    and the note on the artifact says it "builds the forward track record the gate sizes on".

    THE CAUSE IS A SHARED SOURCE, NOT A BROKEN HEDGE. ``fut_pnl = fut_eq - start_eq`` and
    ``start_eq`` is ``capital_events.effective_start_equity`` -- the RUIN RAIL's inception, which a
    principal-signed re-base legitimately moves. On 2026-08-01 a ``RESTART`` moved it 10,547.78 ->
    5,757.08 so the rail would measure the post-fix book instead of latching on an already-fixed
    churn-loop bug. That is correct FOR THE RAIL. It is not correct for P&L REPORTING, which must
    measure from the first inception forever -- and both read one number, so the re-base silently
    became $4,790.70 of reported profit. Same family as L1.51's ``_capital()``: a rail's reference
    point and a performance number may not share a source when a re-base can move one of them.

    THE INCOME LEDGER WINS, and the reason is structural rather than a preference: ``realized +
    funding - commission`` is venue-native and has no re-baseable input, so no desk-side accounting
    act can move it. The equity delta has exactly one, and that one moved.

    EXPLAINED IS NOT THE SAME AS FINE, and keeping them apart is the whole point (L1.55's
    ABSENT-vs-UNREADABLE discipline): a gap matching a ledgered re-base is a REPORTING defect with
    a known cause, while a gap that matches nothing is the phantom class that earns a page. The
    previous code collapsed both into one field named ``residual`` that no verdict ever cited.
    """

    model_config = ConfigDict(frozen=True)

    equity_delta: float | None       # fut_eq - start_eq (start_eq is RE-BASEABLE)
    income_ledger: float | None      # realized + funding - commission + unrealized (venue-native)
    gap: float | None                # equity_delta - income_ledger; 0 on an honest flat book
    rebase_usd: float                # ledgered re-base that would explain a gap of this size
    explained: bool                  # gap is attributable to the known re-base, within tolerance
    measured: bool                   # False = an income term was unreadable; NOT a zero gap
    reporting_pnl: float | None      # the number P&L reporting should publish
    verdict: str


def reconcile_futures_leg(
    *,
    equity_delta: float | None,
    venue_realized: float | None,
    funding: float | None,
    commission: float | None,
    unrealized: float = 0.0,
    rebase_usd: float = 0.0,
    tol: float = 25.0,
) -> FuturesLegReconciliation:
    """Cross-check the equity-delta futures PnL against the venue income ledger.

    ``tol`` absorbs the honest slack between the two paths -- open-position marks move between the
    equity read and the income read, and both are rounded. It is deliberately NOT scaled to the
    gap: a tolerance that grows with the discrepancy it is meant to catch explains everything.

    UNMEASURED IS NOT AGREEMENT. Any missing income term returns ``measured=False`` with no gap and
    no reporting number, because "the venue read failed" and "the two agree" are different claims
    and only one of them is evidence (the 2026-07-26 ``inf%`` verdict came from judging one as the
    other). ``reporting_pnl`` then stays ``None`` so a caller cannot quietly substitute a fabricated
    zero for a measurement that did not happen.
    """
    if equity_delta is None or venue_realized is None or funding is None or commission is None:
        missing = [n for n, v in (("equity_delta", equity_delta),
                                  ("venue_realized", venue_realized),
                                  ("funding", funding), ("commission", commission)) if v is None]
        return FuturesLegReconciliation(
            equity_delta=equity_delta, income_ledger=None, gap=None, rebase_usd=rebase_usd,
            explained=False, measured=False, reporting_pnl=None,
            verdict=(f"UNMEASURED: {', '.join(missing)} unreadable -- the futures leg has one "
                     f"measurement, not two, so the cross-check is UNDECIDABLE. A missing term is "
                     f"not an agreeing term."))
    income = round(float(venue_realized) + float(funding) - abs(float(commission))
                   + float(unrealized), 2)
    gap = round(float(equity_delta) - income, 2)
    explained = abs(gap - float(rebase_usd)) <= tol
    if abs(gap) <= tol:
        verdict = (f"AGREE: equity delta {equity_delta:+.2f} and income ledger {income:+.2f} match "
                   f"within {tol:.2f} -- the futures leg is measured twice and both agree.")
    elif explained:
        verdict = (
            f"REBASE-LEAK: equity delta {equity_delta:+.2f} exceeds the venue income ledger "
            f"{income:+.2f} by {gap:+.2f}, which matches the ledgered inception re-base of "
            f"{rebase_usd:+.2f}. The rail's re-based inception has leaked into P&L REPORTING; the "
            f"book has NOT earned this. Publishing {income:+.2f}.")
    else:
        verdict = (
            f"PHANTOM: equity delta {equity_delta:+.2f} vs income ledger {income:+.2f} differ by "
            f"{gap:+.2f}, and the ledgered re-base of {rebase_usd:+.2f} does NOT account for it. "
            f"Two measurements of one leg disagree for an unknown reason -- treat as unexplained "
            f"until a venue read proves otherwise (2026-07-10 phantom class).")
    return FuturesLegReconciliation(
        equity_delta=round(float(equity_delta), 2), income_ledger=income, gap=gap,
        rebase_usd=round(float(rebase_usd), 2), explained=explained, measured=True,
        reporting_pnl=income, verdict=verdict)


class CarryBleedReport(BaseModel):
    """The standing carry-leak alarm: how much of the funding harvest survives to the net."""

    model_config = ConfigDict(frozen=True)

    real_net: float  # spot_pnl + fut_pnl -- the real delta-neutral book (excludes paper legs)
    funding: float | None  # the harvest; None = UNMEASURED (venue read failed), never "zero"
    non_funding_pnl: float | None  # real_net - funding = basis + fees + drift (None if unmeasured)
    harvest_eaten_frac: float | None  # share of harvest lost to the leak (0 = clean, >=1 = all)
    alert: bool
    verdict: str
    measured: bool = True  # False = the funding read failed; the leak is UNDECIDABLE, not clean

    def __bool__(self) -> bool:
        # An UNMEASURED book is not a healthy one. Truthiness means "nothing to worry about",
        # and a blind alarm is something to worry about -- so it must not read as fine.
        return self.measured and not self.alert


def attribute_non_funding(
    non_funding_pnl: float, basis: float, fut_commission: float
) -> dict[str, float]:
    """Split the carry leak into ``basis``, ``fut_fees`` and an UNEXPLAINED ``residual``.

    The bleed alarm answers *how much* leaked; this answers *where it went*, which is the only
    form the desk can act on. From the book identity ``net = spot_open + basis + funding - fees``::

        non_funding = basis - fees + residual   ->   residual = non_funding - basis + fees

    ``basis`` is the deduped trade-log price_pnl (hedge convergence, ~0 for a tight hedge) and
    ``fut_commission`` is the venue's exact FUTURES fee bill. The residual is everything neither
    explains: SPOT commission (paid in the spot wallet, absent from the futures income ledger),
    slippage, and hedge-drift incidents. It is deliberately NOT called "fees" -- naming an
    unexplained quantity after a known one is how a phantom gets rationalised (2026-07-10).

    A large residual is the phantom/broken-hedge class and deserves a page; a large ``fut_fees``
    term is an EXECUTION problem with a known lever (maker share, churn, BNB burn). Before this
    split the two were indistinguishable on the dashboard, so the standing duty to "attribute
    basis/fees/incidents" could not actually be discharged.
    """
    fees = abs(fut_commission)
    return {"basis": round(basis, 2), "fut_fees": round(fees, 2),
            "residual": round(non_funding_pnl - basis + fees, 2)}


def carry_bleed_report(
    *, funding: float | None, spot_pnl: float, fut_pnl: float, alert_frac: float = 0.5,
    open_legs: int | None = None, recon: FuturesLegReconciliation | None = None,
) -> CarryBleedReport:
    """Attribute the delta-neutral book's non-funding PnL and raise an alarm if the leak is eating
    the funding harvest.

    A tight cash-and-carry earns ``funding`` and its price legs cancel, so the honest target is
    ``non_funding_pnl ~= 0`` (only small fees). ``non_funding_pnl = (spot_pnl + fut_pnl) - funding``
    captures everything else -- basis convergence, fees/slippage, and hedge-drift incidents. The
    alarm fires when that leak is a drain worth at least ``alert_frac`` of the harvest (or any drain
    at all when there is no harvest to offset it), so a hedge quietly losing more than it earns can
    never again slide by unnoticed on the dashboard. Diagnose the dominant cause only when it fires.

    TWO-SIDED (2026-07-26): the target is ~0 in BOTH directions, so a large POSITIVE non-funding
    PnL alarms just as loudly. On a delta-neutral book the price legs cancel by construction -- a
    windfall that size is not luck, it is a BROKEN HEDGE (a naked/untracked leg carrying real
    directional risk that will reverse). A one-sided alarm would have called that state "clean".

    UNMEASURED (2026-07-26): ``funding=None`` means the venue read failed, and the leak is then
    UNDECIDABLE -- every term of this alarm is denominated in a harvest we do not know. Passing a
    zero instead produced a division by that zero and an ``inf%`` "hedge losing more than it
    earns" verdict out of nothing but an HTTP 502. The report says so plainly and declines to
    judge; ``measured=False`` is what downstream must alarm on, and it is deliberately NOT folded
    into ``alert`` -- a venue outage and a leaking hedge need different responses, so collapsing
    them into one boolean would just move the ambiguity rather than remove it.
    """
    real_net = round(spot_pnl + fut_pnl, 2)
    if funding is None:
        return CarryBleedReport(
            real_net=real_net, funding=None, non_funding_pnl=None, harvest_eaten_frac=None,
            alert=False, measured=False,
            verdict=(f"UNMEASURED: funding harvest unavailable (venue income read failed) -- "
                     f"leak undecidable on real_net {real_net:+.2f}. A swallowed venue error is "
                     f"NOT a zero harvest; judging one as the other fabricates a total-bleed "
                     f"verdict out of an outage."),
        )
    non_funding = round(real_net - funding, 2)
    if funding > 0:
        eaten = round(max(0.0, -non_funding) / funding, 3)
    else:
        eaten = float("inf") if non_funding < 0 else 0.0
    alert = (abs(non_funding) >= alert_frac * funding) if funding > 0.0 else (non_funding < 0.0)
    if alert and non_funding > 0.0:
        # NAME THE CAUSE THE DATA SUPPORTS, NEVER THE ONE THE SHAPE SUGGESTS. This branch used to
        # assert "a NAKED/UNTRACKED leg -- reconcile spot vs perp qty" unconditionally. On
        # 2026-08-05 it fired for four days against a book holding ZERO positions, so the remedy it
        # ordered was not merely wrong, it was IMPOSSIBLE TO PERFORM: there were no legs to
        # reconcile, and an operator who checked found nothing and moved on. The real cause was an
        # inception re-base leaking into P&L reporting, which `reconcile_futures_leg` identifies
        # exactly. A confident wrong diagnosis is worse than an honest open question, because it
        # closes the search (2026-07-10 phantom lesson, applied to the alarm rather than the book).
        head = (f"BLEED(inverted): non-funding PnL {non_funding:+.2f} is "
                f"{non_funding / funding:.0%} of {funding:+.2f} funding harvest")
        if recon is not None and recon.measured and not recon.explained and recon.gap is not None \
                and abs(recon.gap) > 0.0:
            verdict = f"{head} -- {recon.verdict}"
        elif recon is not None and recon.explained and recon.gap is not None and recon.gap != 0.0:
            verdict = f"{head} -- ACCOUNTING, NOT EDGE. {recon.verdict}"
        elif open_legs == 0:
            # `open_legs` counts TRACKED carries, and untracked exposure is precisely what the
            # naked-leg hypothesis is about -- so zero tracked legs narrows the field to two
            # candidates rather than clearing the hedge. Saying "this cannot be a naked leg" here
            # would repeat, inverted, the very error this branch exists to fix: on 2026-08-05 the
            # same executor was logging 476 SPOT-EXCESS lines about wallet balances it did not
            # track. State both, and name which one to check first.
            verdict = (
                f"{head} -- and the book tracks ZERO open carries, so the gain is realized and "
                "cannot come from a tracked hedge. Two candidates remain, in this order: an "
                "ACCOUNTING artifact (check the inception the futures leg is differenced against "
                "against the venue income ledger), or UNTRACKED exposure the position map does "
                "not know about (check wallet balances against tracked carries).")
        else:
            verdict = (
                f"{head} -- delta-neutral price legs cancel, so a gain this size means a "
                f"NAKED/UNTRACKED leg, not edge; reconcile spot vs perp qty across the "
                f"{open_legs if open_legs is not None else 'open'} open leg(s) before trusting it")
    elif non_funding >= 0.0:
        verdict = f"clean: non-funding PnL {non_funding:+.2f} not a drain; harvest survives"
    elif not alert:
        verdict = f"ok: {eaten:.0%} of the {funding:+.2f} funding harvest lost to non-funding PnL"
    else:
        verdict = (
            f"BLEED: non-funding PnL {non_funding:+.2f} is {eaten:.0%} of {funding:+.2f} funding "
            "harvest -- hedge losing more than it earns; attribute basis/fees/incidents"
        )
    return CarryBleedReport(
        real_net=real_net,
        funding=funding,
        non_funding_pnl=non_funding,
        harvest_eaten_frac=eaten,
        alert=alert,
        verdict=verdict,
    )

```

### libs\ops\deepseek_cycle.py
```python
"""DEEPSEEK SECOND FLYWHEEL -- the local core. Mandate III, IV, V, VIII, IX, X, CLXXVII, CXCV.

WHAT THIS IS. DeepSeek's IDENTITY IS LOCAL; OpenRouter is only an inference backend (IV). So
everything that constitutes the agent -- the policy gate, cold-context construction, sealing,
role allocation, cost accounting, the authority fences -- lives here and runs on the desk. Only
model inference leaves the box.

THE FIVE THINGS THIS REFUSES, each of which would turn a second flywheel into a second desk:

  * PROMOTING ANYTHING. CXCV-12/13/14/15: DeepSeek cannot promote a survivor, allocate capital,
    override policy, or merge authoritative code. The fences are functions that return REFUSED
    with a reason, not comments asking nicely. Stage-B forward clocks remain the sole promotion
    authority, exactly as they are for Claude.
  * RUNNING ON STALE POLICY. CXCV-4/5: the canonical policy hash is verified BEFORE every cycle
    and a mismatch fails VISIBLY. A research agent running yesterday's rules produces findings
    nobody can attribute to a ruleset.
  * A CONTAMINATED COLD PHASE. VIII: Phase A sees raw state only -- never Claude's opinion,
    Codex's conclusion, GPT's ranking, Kimi's interpretation, or a prior DeepSeek narrative. The
    cold context is FILTERED and the filter is tested, because independence asserted in a
    docstring is not independence.
  * UNSEALED COMPARISON. Phase A output is hashed and sealed BEFORE Phase B may look at anybody
    else's conclusions. Without the seal there is no way to tell an independent rediscovery from
    an agreement written after reading the answer -- and that distinction is the entire value of
    running a second brain.
  * SILENT IDENTITY SUBSTITUTION. IV: if the DeepSeek model is unavailable, record
    MODEL_UNAVAILABLE and preserve experiment integrity. Quietly serving the request from Claude
    or GPT would corrupt the one measurement the second flywheel exists to produce -- whether
    DeepSeek finds things Claude did not.

A DARK SEAT IS NOT A FAILURE. With no OPENROUTER_API_KEY the cycle reports DARK and exits 0. The
desk's improvement rate must never depend on a credential, and an organ that hard-fails on a
missing key is an organ that takes the whole scheduler down with it.

AUTHORITY: RESEARCH GENERATION ONLY -- everything it produces enters the SAME canonical empirical
engine as every other candidate, with no shortcut and no parallel registry.
"""
from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

__all__ = [
    "CAPABILITY_LEDGER",
    "CONTAMINATION_KEYS",
    "ESCALATION_STATES",
    "EVIDENCE",
    "INHERITED_REGISTRIES",
    "SEED_ROLES",
    "budget_gate",
    "cold_context",
    "escalation_mix",
    "fence",
    "inheritance_check",
    "policy_gate",
    "run_role",
    "seal",
    "seat_state",
]

_ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = "data/deepseek_evidence.jsonl"
SEALS = "data/deepseek_seals"

#: X. Roles are SEEDS, not permanent bureaucracy -- spawnable, splittable, mergeable, retirable.
#: They live here as DATA so adding one is a row rather than a branch, and so the allocator can
#: rank them by measured marginal contribution (CXCV-26) instead of by the order somebody typed
#: them. No role is sacred.
SEED_ROLES: tuple[tuple[str, str], ...] = (
    ("cold_alpha_inventor", "economically plausible hypotheses from first principles"),
    ("survivor_assassin", "attack every survivor: leakage, hidden beta, overfit, crowding, cost, "
                          "capacity, tails, dependence, execution, decay"),
    ("graveyard_resurrection", "reopen rejected research after new data/regimes/venues/methods"),
    ("regime_specialist", "conditional alpha, transitions, interactions, lifecycle"),
    ("validation_red_team", "attack CPCV, walk-forward, lockbox, FDR, PBO, effective sample "
                            "size, timestamping, cost realism, false-negative gates"),
    ("multilingual_intelligence", "mine CN/KR/JP/RU/PT/ES/AR/TR/VI/ID/HI ecosystems"),
    ("cross_domain_transfer", "information theory, control theory, network science, causal "
                              "inference, econometrics, OR, survival analysis, queueing"),
    ("execution_tca_challenger", "venue routing, maker/taker, queue, fill probability, impact, "
                                 "adverse selection, latency, fees, rebates"),
    ("portfolio_allocator_challenger", "does this deserve the next unit of risk?"),
    ("replication_brain", "reproduce claimed discoveries independently"),
    ("contrarian_brain", "strongest coherent alternative explanation"),
    ("research_factory_optimizer", "wasted tests, stranded data, unwired modules, bottlenecks"),
    ("external_replication_factory", "papers, AI/RL/LLM trading research, competitions, repos"),
    ("unknown_unknown_explorer", "search beyond the current ontology"),
    ("negative_space_miner", "low-coverage cells across data x mechanism x asset x venue x "
                             "horizon x regime x representation x execution x label"),
    ("proprietary_state_factory", "fuse public sources + archives + own execution footprint"),
    ("data_exhaustion_agent", "is each dataset's plausible information exhausted?"),
    ("source_ecosystem_expander", "source -> author -> repos -> citations -> datasets -> local "
                                  "equivalents -> upstream/downstream"),
    ("historical_backfill_hunter", "lawful historical versions of ephemeral information"),
    ("failure_science_agent", "classify failures: mechanism, regime, proxy, sample, execution, "
                              "crowding, break, data defect, test defect, selection, capacity"),
    ("experiment_designer", "the cheapest decisive experiment"),
    ("natural_experiment_hunter", "fee changes, outages, margin changes, listings, spec changes, "
                                  "protocol changes, ETF events, exogenous shocks"),
    ("data_integrity_red_team", "attack timestamps, revisions, gaps, survivorship, mappings, "
                                "clocks, backfills, duplicates, historical availability"),
    ("alpha_recombination", "recombine fragments of survivors, failures, datasets, regimes"),
    ("near_survivor_repair", "minimum defensible modification separating false negative from "
                             "genuine failure"),
    ("alpha_uniqueness_decomposer", "incremental information or repackaged exposures?"),
    ("portfolio_complementarity_hunter", "alpha in the portfolio's current weakness states"),
    ("capital_displacement_researcher", "what could displace the weakest unit of risk?"),
    ("alpha_decay_scientist", "persistence, decay, recurrence"),
    ("research_debt_hunter", "generated-but-untested, tested-but-unclassified, "
                             "data-without-consumers, failures-without-attribution, unwired code"),
    ("research_saturation_detector", "diminishing marginal information; reopen on change"),
    ("knowledge_compression_agent", "compress failure clusters into reusable knowledge"),
    ("research_technology_hunter", "superior data systems, labels, representations, search, "
                                   "validation, portfolio, execution, autonomous-R&D methods"),
    ("competitor_capability_intelligence", "lawful public capability signals -- never secrets"),
    ("model_agent_challenger", "test DeepSeek/Qwen/GPT/Kimi/Claude/future models continuously"),
)

#: IV. Bulk/deep split by state. NOT SACRED -- the mandate says so explicitly, and these are
#: starting points the allocator is expected to move on measured $/validated-information-gain.
ESCALATION_STATES: dict[str, tuple[float, float]] = {
    "LOW_VALUE": (0.97, 0.03),
    "NORMAL": (0.90, 0.10),
    "MAJOR_DISCOVERY": (0.70, 0.30),
    "CRITICAL_HIGH_VOI": (0.50, 0.50),
}

#: VIII/IX. Context keys that carry ANOTHER AGENT'S CONCLUSION. Phase A must never see these.
#: Note what is NOT here: measured metrics, raw evidence, schemas and portfolio state are all
#: FACTS and belong in the cold context. The filter removes interpretations, not information --
#: a cold phase starved of facts produces uninformed guesses, not independent ones.
CONTAMINATION_KEYS: tuple[str, ...] = (
    "claude_opinion", "claude_conclusion", "claude_rationale", "claude_ranking",
    "codex_conclusion", "codex_rationale", "gpt_ranking", "gpt_recommendation", "gpt_opinion",
    "kimi_interpretation", "kimi_findings", "consensus", "consensus_summary", "agent_summary",
    "previous_deepseek_conclusion", "prior_conclusion", "desired_answer", "expected_answer",
    "recommendation", "verdict_hint", "research_brief", "peer_rationale",
)

#: CXCV-12..15. What DeepSeek may never do, whatever any model response says.
_FENCED: dict[str, str] = {
    "promote_survivor": "CXCV-12. Promotion authority is the Stage-B forward clock alone, for "
                        "every agent. A second promoter is a second statistical universe",
    "allocate_capital": "CXCV-13. Capital allocation is the principal's and the portfolio "
                        "engine's; a research agent that can size is not a research agent",
    "override_policy": "CXCV-14. The canonical policy hierarchy is authoritative over every "
                       "agent including this one",
    "merge_authoritative_code": "CXCV-15. Merging into authoritative code is outside this "
                                "agent's authority",
    "loosen_statistical_gate": "standing desk law: alpha stays 0.05 and no gate is loosened to "
                               "manufacture a hit, by any agent, ever",
    "raise_leverage_or_size": "R0143 size fence. Size and leverage decisions are the principal's",
    "touch_deadman_switch": "scripts/run_deadman_switch.py is Tier-3 NEVER-TOUCH",
}


def _now() -> str:
    return datetime.now(tz=UTC).isoformat(timespec="seconds")


def _hash(obj: Any) -> str:
    return hashlib.sha256(
        json.dumps(obj, sort_keys=True, default=str, ensure_ascii=False).encode("utf-8")
    ).hexdigest()


@dataclass(frozen=True)
class Seat:
    """Whether inference is reachable at all, and on which identity."""

    lit: bool
    provider: str = "openrouter"
    bulk_model: str = ""
    deep_model: str = ""
    why: str = ""
    env_var: str = "OPENROUTER_API_KEY"
    key_source: str = ""                       # env:OPENROUTER_API_KEY | file:llm_panel.json


#: The desk's credential file -- the SAME one every other seat reads (llm_seat.SECRETS). Never
#: printed, never copied; only its presence and the provider names are ever reported.
SECRETS = _ROOT / "data" / "secrets" / "llm_panel.json"


def resolve_key(env: dict[str, str] | None = None, secrets: Path | None = None
                ) -> tuple[str, str]:
    """(key, source): the environment first, then data/secrets/llm_panel.json -- the order
    `llm_seat.seats` uses for every other organ.

    THE SEAT RAN DARK BY CONSTRUCTION (measured 2026-09-08 by a reconcile verifier): this module
    read OPENROUTER_API_KEY from the environment only, ops/brain_env.sh exports no such name,
    and quant-deepseek.service loads no EnvironmentFile -- while the key the desk actually holds
    sits in the secrets file that kimi_hunter, the director and llm_seat all read. Every daily
    run reported DARK and exited 0, honestly, and produced nothing. An openrouter provider row
    is preferred (one key reaches every free model); failing that, the first row with a key.
    """
    e = dict(os.environ if env is None else env)
    key = e.get("OPENROUTER_API_KEY", "").strip()
    if key:
        return key, "env:OPENROUTER_API_KEY"
    path = secrets or SECRETS
    try:
        cfg = json.loads(path.read_text("utf-8"))
    except (OSError, ValueError):
        return "", ""
    rows = [p for p in (cfg.get("providers") or []) if isinstance(p, dict)
            and str(p.get("key") or "").strip()]
    for p in rows:
        if "openrouter" in (str(p.get("name") or "") + str(p.get("base_url") or "")).lower():
            return str(p["key"]).strip(), "file:llm_panel.json"
    if rows:
        return str(rows[0]["key"]).strip(), "file:llm_panel.json"
    return "", ""


def seat_state(env: dict[str, str] | None = None, secrets: Path | None = None) -> Seat:
    """IV + the dark-seat rule. A missing key is a REPORTED state, never an exception.

    Model IDs are read from the environment and never hardcoded: the mandate is explicit that
    historical DeepSeek model IDs must not be assumed still valid, and a stale constant here
    would silently route the second flywheel to a model that no longer exists.
    """
    e = dict(os.environ if env is None else env)
    key, source = resolve_key(e, secrets)
    if not key:
        return Seat(lit=False, why=(
            "DARK: OPENROUTER_API_KEY is not set and data/secrets/llm_panel.json holds no key. "
            "This is a REPORTED STATE and exit 0 -- the "
            "desk's improvement rate must not depend on a credential, and an organ that "
            "hard-fails on a missing key takes the scheduler down with it"))
    return Seat(
        lit=True,
        key_source=source,
        provider=e.get("DEEPSEEK_PROVIDER", "openrouter"),
        bulk_model=e.get("DEEPSEEK_BULK_MODEL", ""),
        deep_model=e.get("DEEPSEEK_DEEP_MODEL", ""),
        why="seat lit",
    )


def budget_gate() -> dict[str, Any]:
    """SPEND CAP BEFORE THE CYCLE, not inside it (pre-flight 2026-08-12: READY_BUT_UNCAPPED).

    V's cadence is HOURLY, 24/7, and IV explicitly permits not capping call COUNT while positive
    marginal information value remains. Those two together are exactly how a month's budget
    disappears by the 3rd: 24 cycles a day against a $20 default needs only pennies each to
    exhaust it. Inference is abundant, empirical truth is scarce, and CAPITAL IS SCARCER -- so
    the cap is checked once, cheaply, before the cycle starts rather than per call.

    EXHAUSTED IS EXIT 0, NEVER A CRASH. A budget that has run out is a normal, expected state of
    a 24/7 organ; failing the scheduler on it would turn a spend limit into an outage and page
    somebody about arithmetic.
    """
    try:
        from libs.ops.llm_seat import (
            free_budget_left,
            free_daily_max,
            free_tier_only,
            month_spend_usd,
            monthly_cap_usd,
        )
    except ImportError as exc:
        return {"ok": False, "verdict": "CAP_UNREADABLE",
                "why": f"cannot import the spend ledger ({exc}) -- refusing to spend against an "
                       "unknown budget. UNKNOWN is not headroom"}

    # A DOLLAR CAP CANNOT HOLD A FREE RUN, and this gate was doing exactly that.
    #
    # `llm_spend.jsonl` books an ESTIMATED cost on every call from a deliberately over-stated
    # $/1k-token constant, free calls included. Measured on the trading box 2026-09-12: 446 calls
    # that day, every one on `nvidia/nemotron-3-ultra-550b-a55b:free`, ledgered at $13.44 -- and
    # this gate read the month at $24.97 against a $20 cap and held DeepSeek off entirely.
    #
    # So the second brain was switched off by money it never spent. `llm_seat.chat` was fixed for
    # exactly this earlier the same day; this gate is a SECOND, independent reader of the same
    # ledger and kept the bug. The free tier's real limit is REQUESTS PER DAY, so that is what
    # binds when the run is free.
    if free_tier_only():
        left = free_budget_left()
        return {
            "ok": left > 0,
            "verdict": "WITHIN_FREE_BUDGET" if left > 0 else "FREE_REQUESTS_EXHAUSTED",
            "free_requests_left": left, "free_daily_max": free_daily_max(),
            "month_spend_usd": month_spend_usd(),
            "why": (f"free tier: {left} of {free_daily_max()} request(s) left today. The dollar "
                    f"ledger is an ESTIMATE and books cost for free calls, so it is not the bound "
                    f"here" if left > 0 else
                    f"free-tier daily request budget exhausted ({free_daily_max()} used). Exit 0: "
                    f"a spent budget is a normal state of a 24/7 organ, and it resets at 00:00 "
                    f"UTC"),
        }

    spent, cap = month_spend_usd(), monthly_cap_usd()
    return {
        "ok": spent < cap,
        "verdict": "WITHIN_CAP" if spent < cap else "BUDGET_EXHAUSTED",
        "month_spend_usd": spent, "monthly_cap_usd": cap,
        "headroom_usd": round(cap - spent, 4),
        "why": (f"${spent:.2f} of ${cap:.2f} spent this month" if spent < cap else
                f"${spent:.2f} of ${cap:.2f} -- exhausted. Exit 0: a spent budget is a normal "
                "state of a 24/7 organ, not an outage to page about"),
    }


def policy_gate(root: Path | None = None) -> dict[str, Any]:
    """CXCV-4/5 + CLXXVIII. Verify canonical policy BEFORE any consequential work.

    Delegates to libs.ops.canonical_policy.resolve() -- the SAME resolver Claude and Codex use,
    which is the whole point of CXCV-27/38: a second agent resolving policy its own way would
    prove nothing about inheritance. A resolver import failure is itself a REFUSAL, never a pass:
    "we could not check" and "it checks out" are different answers.
    """
    try:
        # The resolver landed 2026-09-03 (libs/ops/canonical_policy.py). The except below is
        # still the designed behaviour, not dead code: it covers a tree where the resolver or
        # the constitution checker it delegates to is absent, and refusing there is the point.
        from libs.ops import canonical_policy
    except ImportError as exc:
        # ONE RETURN CONTRACT, ALWAYS. This branch used to omit `policy_hash` and `version`, and
        # the caller reads them unconditionally to report the refusal -- so the designed visible
        # refusal (BLOCKED_POLICY, exit 2) was replaced by `KeyError: 'version'` and exit 1.
        # Measured 2026-09-03: that crash was NINE of the fifteen dead seat launches in 24h, and
        # the seat-yield meter counted every one as DIED_AT_ATTEMPT -- a defect whose only cause
        # was the refusal being unable to describe itself. UNKNOWN is still not a pass; it is
        # simply reported as UNKNOWN (None) rather than by raising.
        return {"ok": False, "verdict": "RESOLVER_UNAVAILABLE",
                "policy_hash": None, "version": None, "detail": {},
                "why": f"cannot import the canonical resolver ({exc}); refusing to run "
                       "consequential work on unverified policy. UNKNOWN is not a pass"}
    res = canonical_policy.resolve(root)
    verdict = str(res.get("verdict", "MISSING_POLICY"))
    return {
        "ok": verdict == "RESOLVED",
        "verdict": verdict,
        "policy_hash": res.get("canonical_policy_hash"),
        "version": res.get("canonical_policy_version"),
        "detail": res,
        "why": ("canonical policy resolved; the cycle may proceed" if verdict == "RESOLVED" else
                f"policy verdict {verdict} -- FAILING VISIBLY rather than researching under rules "
                "nobody can attribute the findings to (CXCV-5)"),
    }


def cold_context(state: dict[str, Any]) -> dict[str, Any]:
    """VIII PHASE A. Strip every other agent's CONCLUSION, keep every FACT.

    The distinction is the design. Measured survivor metrics, near-survivor data, graveyard
    EVIDENCE, portfolio state, execution facts, regime measurements and schemas are all facts and
    stay. Opinions, rankings, rationales and consensus summaries go. A cold phase starved of facts
    would produce uninformed guesses rather than independent ones, which is a different and
    equally useless thing.
    """
    kept: dict[str, Any] = {}
    removed: list[str] = []
    for k, v in (state or {}).items():
        low = str(k).strip().lower()
        if low in CONTAMINATION_KEYS or any(
                low.endswith("_" + c) or low.startswith(c + "_") for c in
                ("opinion", "conclusion", "rationale", "ranking", "recommendation")):
            removed.append(k)
            continue
        kept[k] = v
    return {
        "cold_context": kept,
        "removed_keys": sorted(removed),
        "cold_context_hash": _hash(kept),
        "law": "facts in, interpretations out. Agreement is not independent evidence if the "
               "agents consumed the same interpretation (IX)",
    }


def seal(run_id: str, *, role: str, phase_a_output: Any, policy_hash: str,
         cold_context_hash: str, provider: str, model: str, prompt_version: str = "1",
         root: Path | None = None) -> dict[str, Any]:
    """VIII. Seal Phase A BEFORE Phase B may see anybody else's conclusions.

    Without a seal there is no way to distinguish an INDEPENDENT_REDISCOVERY from an agreement
    written after reading the answer -- and that distinction is the entire value of running a
    second brain. The seal is a content hash written to its own immutable file; re-sealing the
    same run_id with different content is REFUSED rather than overwritten, because a seal that
    can be rewritten is not a seal.
    """
    base = root or _ROOT
    d = base / SEALS
    d.mkdir(parents=True, exist_ok=True)
    safe = "".join(c if (c.isalnum() or c in "-_.") else "_" for c in str(run_id))[:120]
    p = d / f"{safe}.json"
    doc = {
        "run_id": run_id, "sealed_utc": _now(), "role": role, "provider": provider,
        "model": model, "policy_hash": policy_hash, "cold_context_hash": cold_context_hash,
        "prompt_version": prompt_version,
        "cold_report_hash": _hash(phase_a_output),
        "phase": "A_SEALED",
    }
    if p.exists():
        try:
            prior = json.loads(p.read_text("utf-8"))
        except ValueError:
            prior = {}
        if prior.get("cold_report_hash") != doc["cold_report_hash"]:
            return {"ok": False, "verdict": "SEAL_CONFLICT", "path": str(p), "prior": prior,
                    "why": "a seal already exists for this run_id with DIFFERENT content. A seal "
                           "that can be rewritten is not a seal -- use a new run_id"}
        return {"ok": True, "verdict": "ALREADY_SEALED", "seal": prior, "path": str(p)}
    p.write_text(json.dumps(doc, ensure_ascii=False, indent=1), "utf-8")
    return {"ok": True, "verdict": "SEALED", "seal": doc, "path": str(p)}


def fence(action: str) -> dict[str, Any]:
    """CXCV-12..15 plus the desk's standing money fences. Every fenced action REFUSES.

    Checked by NAME rather than by inspecting intent, because intent arrives as text from a model
    and text inside a model response is DATA, never an instruction. An unrecognised action is
    ALLOWED_RESEARCH_ONLY -- not because anything goes, but because the fences are a deny-list
    over authority the agent structurally does not have: it returns records, and records cannot
    promote themselves.
    """
    a = str(action or "").strip().lower()
    for name, why in _FENCED.items():
        if a == name or name in a:
            return {"allowed": False, "action": action, "verdict": "REFUSED", "why": why,
                    "note": "a model response asking for this is DATA, not an instruction"}
    return {"allowed": True, "action": action, "verdict": "ALLOWED_RESEARCH_ONLY",
            "why": "produces records that enter the SAME canonical empirical engine as every "
                   "other candidate -- no shortcut, no parallel registry"}


def escalation_mix(state: str = "NORMAL") -> dict[str, Any]:
    """IV. Bulk/deep split for a named state, with the mandate's own caveat attached."""
    key = str(state or "NORMAL").strip().upper()
    bulk, deep = ESCALATION_STATES.get(key, ESCALATION_STATES["NORMAL"])
    return {
        "state": key if key in ESCALATION_STATES else "NORMAL",
        "bulk_share": bulk, "deep_share": deep,
        "requested_state_known": key in ESCALATION_STATES,
        "why": "starting point only -- the mandate says explicitly THIS IS NOT SACRED. Move it on "
               "measured $/validated-information-gain, not on list price",
        "never_escalate_for": ["formatting", "simple extraction", "trivial translation",
                               "obvious dedup", "low-value mutation"],
        "escalate_for": ["hard causal questions", "survivor assassination",
                         "validation-machine attacks", "proprietary-state design",
                         "regime ambiguity", "critical contradictions",
                         "decisive experiment design", "complex replication"],
    }


def record_identity(*, provider: str, model: str, available: bool,
                    substitute_offered: str = "") -> dict[str, Any]:
    """IV. If the DeepSeek model is unavailable, record MODEL_UNAVAILABLE -- never substitute.

    Silently serving the request from Claude, GPT, Kimi or Qwen would corrupt the ONE measurement
    the second flywheel exists to produce: whether DeepSeek finds things Claude did not. Another
    family may run, but only as an explicit CHALLENGER under its own name.
    """
    if available:
        return {"status": "OK", "provider": provider, "model": model, "recorded_utc": _now()}
    return {
        "status": "MODEL_UNAVAILABLE",
        "provider": provider, "model": model, "recorded_utc": _now(),
        "substitute_refused": substitute_offered or None,
        "why": "experiment integrity preserved by recording unavailability rather than "
               "substituting another model family. A silent substitution would corrupt the only "
               "measurement this flywheel exists to produce -- whether DeepSeek finds what Claude "
               "did not. Another family may run, but only as an explicit CHALLENGER under its "
               "own name",
    }


@dataclass
class CycleReport:
    """One hourly cycle's outcome (V). Deliberately serialisable and small."""

    started_utc: str
    seat: str
    policy: str
    roles_run: list[str] = field(default_factory=list)
    findings: int = 0
    blocked: list[str] = field(default_factory=list)
    why: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {"started_utc": self.started_utc, "seat": self.seat, "policy": self.policy,
                "roles_run": self.roles_run, "findings": self.findings,
                "blocked": self.blocked, "why": self.why}


#: CXCV-38. The canonical registries DeepSeek INHERITS. Every one is written by the pre-DeepSeek
#: machinery and READ here -- listing them is what makes "no parallel registry" checkable rather
#: than promised. A DeepSeek-only copy of any of these would be a second statistical universe
#: assembled one well-meaning convenience at a time.
INHERITED_REGISTRIES: tuple[tuple[str, str], ...] = (
    ("data/edge_intake.jsonl", "universal edge intake -- every discovery's disposition"),
    ("data/alpha_lifecycle.jsonl", "conditional-survivor + hibernation state"),
    ("docs/research/capability_challengers.jsonl", "elite-factory capability challengers"),
    ("docs/research/research_auction.jsonl", "research-capital auction decisions"),
    ("docs/research/free_substitute_comparisons.json", "paid/free substitution verdicts"),
    ("docs/research/blowup_library.jsonl", "failure / blow-up negative memory"),
    ("docs/graveyard.md", "permanent rejection memory"),
    ("docs/research/recommendation_ledger.json", "the desk's open recommendation queue"),
)

#: Paths a DeepSeek implementation must NEVER create. Each would shadow an inherited registry.
_FORBIDDEN_PARALLELS: tuple[str, ...] = (
    "data/deepseek_edge_intake.jsonl",
    "data/deepseek_lifecycle.jsonl",
    "data/deepseek_survivors.jsonl",
    "data/deepseek_graveyard.jsonl",
    "docs/research/deepseek_recommendation_ledger.json",
    "data/deepseek_auction.jsonl",
)


def inheritance_check(root: Path | None = None) -> dict[str, Any]:
    """CXCV-38. Prove DeepSeek INHERITS the pre-DeepSeek capability rather than re-founding it.

    Two halves, and the second is the one with teeth. The first reports which canonical
    registries are READABLE -- a missing one is NOT a failure here, because a registry with no
    rows yet is a desk that has not produced that artifact, not a broken inheritance. The second
    fails on any DEEPSEEK-PREFIXED SHADOW of an inherited registry existing on disk.

    That asymmetry is deliberate. Absence of a canonical file is a fact about the desk's history;
    presence of a parallel one is a fact about this agent's behaviour, and it is the failure mode
    the mandate actually warns about -- a second statistical universe assembled one well-meaning
    convenience at a time.
    """
    base = root or _ROOT
    readable: list[dict[str, str]] = []
    absent: list[dict[str, str]] = []
    for rel, what in INHERITED_REGISTRIES:
        (readable if (base / rel).exists() else absent).append({"path": rel, "carries": what})
    shadows = [p for p in _FORBIDDEN_PARALLELS if (base / p).exists()]
    return {
        "checked_utc": _now(),
        "inherited_readable": readable,
        "inherited_absent": absent,
        "parallel_registries_found": shadows,
        "ok": not shadows,
        "verdict": ("INHERITS -- reads the canonical registries and founds none of its own"
                    if not shadows else
                    f"PARALLEL REGISTRY DEFECT: {shadows}. DeepSeek must consume existing "
                    "frontier-hunter findings, copy-trader findings, universal edge intake, "
                    "conditional-survivor state, micro-capacity state, free-data state and "
                    "elite-capability challengers WITHOUT creating competing stores (CXCV-38)"),
        "why_absent_is_not_a_failure": "a canonical registry with no rows yet is a desk that has "
                                       "not produced that artifact, not a broken inheritance; a "
                                       "PARALLEL one is this agent misbehaving",
    }


# --------------------------------------------------------------------- THE MISSING STEP 4/5
#
# Everything above this line was gate/plumbing: policy, budget, seat, cold-context filtering,
# sealing, fencing, inheritance. Every one of them was already built and tested. What was never
# built was the thing they all exist to protect -- an actual call out, generating an actual
# finding, landing in an actual place a human or another organ will read it. Without this,
# "DEEPSEEK READY" was the entire cycle: the scaffolding for a factory with no floor installed.
#
# THE EVIDENCE STORE IS SANCTIONED, NOT A SHADOW REGISTRY. EVIDENCE ("data/deepseek_evidence.jsonl")
# is DeepSeek's own raw-output ledger, distinct from every path in _FORBIDDEN_PARALLELS -- it
# is not a competing edge_intake, alpha_lifecycle or capability_challengers store, it is the
# audit trail of what DeepSeek actually said, which a human or Claude session then triages INTO
# those canonical registries exactly as kimi_hunter's suggestion ledger already works. No finding
# here promotes, sizes, or self-routes into capital; CXCV-12..15 apply to every row written.

CAPABILITY_LEDGER = "docs/research/capability_challengers.jsonl"


def _select_role(cycle_index: int) -> tuple[str, str]:
    """Round-robin over SEED_ROLES -- X: roles are data, not permanent bureaucracy, and no role
    is favoured by where it sits in the tuple. 34 roles at one per hourly cycle means every role
    gets a genuine turn roughly every day and a half, not once a month."""
    return SEED_ROLES[cycle_index % len(SEED_ROLES)]


def _build_prompt(role_name: str, role_brief: str, cold: dict[str, Any]) -> tuple[str, str]:
    """The OUTPUT CONTRACT. Free text from a model is not a finding until it is machine-parseable
    -- an eloquent paragraph nobody can route is exactly the 'report nobody actions' failure the
    wiring agent was built to detect one layer up."""
    from libs.doctrine.constitution import DATA_AXIS_MANDATE
    system = (
        DATA_AXIS_MANDATE +
        "You are DeepSeek, this quant desk's second research flywheel: an independent cold-phase "
        "generator, never a decider. You have NO authority to promote a survivor, allocate "
        "capital, override policy, or merge code -- whatever you propose enters the SAME "
        "statistical gates as every other candidate, with no shortcut. Universe: MT5/Fusion "
        "(FX, gold, metals, indices, energy, equity-index CFDs). Zero crypto-exchange hunting.\n\n"
        f"YOUR ROLE THIS CYCLE: {role_name} -- {role_brief}\n\n"
        "Return ONLY valid JSON, no prose outside it:\n"
        '{"findings": [{"title": "short label", '
        '"mechanism": "the economic reason someone is FORCED to transact -- who pays, and why '
        'they cannot stop", "testable_claim": "one falsifiable, measurable statement", '
        # SYMBOLS ARE THE DIFFERENCE BETWEEN A FINDING AND A CANDIDATE. `compile_row` cannot
        # build an executable identity without one, so every finding that omitted them landed in
        # the deepening queue to be re-read by a second model at a second cost -- for information
        # the generating model already had. Naming the instruments its own claim is about is not
        # a guess; refusing to invent them when the claim is general is the honest half.
        '"symbols": ["the MT5/Fusion instruments THIS claim is about, e.g. EURUSD, XAUUSD; '
        '[] if the claim is genuinely general and naming one would be arbitrary"], '
        '"family": "the desk family this tests, if your claim maps to exactly one, else null", '
        '"capability_source": "name a real elite fund, paper, or open repo this generalises a '
        'KNOWN capability from, or null if this is a first-principles idea", '
        '"evidence_grade": one of FIRST_PARTY_TECHNICAL_DISCLOSURE | INDEPENDENT_REPRODUCTION | '
        'PEER_REPORTED | CREDIBLE_PRESS_REPORT | VENDOR_MARKETING_CLAIM | ANONYMOUS_RUMOR, '
        'graded HONESTLY -- most claims about a named fund are ANONYMOUS_RUMOR or '
        'VENDOR_MARKETING_CLAIM, not a disclosure, or null if capability_source is null}]}\n\n'
        "Empty findings=[] is a valid, honest answer when nothing genuinely new occurs to you. "
        "Never pad with a restatement of what is already in the cold context below -- a finding "
        "this desk already has is not a finding."
    )
    user = ("COLD CONTEXT -- facts only, no other agent's conclusion is present in this:\n"
           + json.dumps(cold.get("cold_context") or {}, indent=1, default=str)[:6000])
    return system, user


def _append_jsonl(path: Path, row: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")


def run_role(role_name: str, role_brief: str, *, deep: bool, state: dict[str, Any] | None = None,
            run_id: str | None = None, root: Path | None = None,
            env: dict[str, str] | None = None) -> dict[str, Any]:
    """One role, one call, every fence checked. This is the step main() previously stopped short
    of -- 'cold phase and routing run here' was a comment; this function is what it should have
    called. Never raises: every failure mode returns a status string, matching every gate above.

    `env`, like `seat_state`'s own parameter, defaults to the real environment and exists so a
    test can inject one without monkeypatching os.environ globally.
    """
    from libs.ops import llm_seat

    base = root or _ROOT
    e = dict(os.environ if env is None else env)
    seat = seat_state(e)
    if not seat.lit:
        return {"status": "DARK", "role": role_name, "why": seat.why}
    model = seat.deep_model if deep else seat.bulk_model
    if not model:
        return {"status": "MODEL_UNAVAILABLE", "role": role_name,
                "why": f"{'DEEPSEEK_DEEP_MODEL' if deep else 'DEEPSEEK_BULK_MODEL'} is unset -- "
                       "recorded rather than substituted (record_identity's law applies here too)"}

    gate = policy_gate(base)
    if not gate["ok"]:
        return {"status": "BLOCKED_POLICY", "role": role_name, "why": gate["why"]}
    budget = budget_gate()
    if not budget["ok"]:
        return {"status": "BUDGET_EXHAUSTED", "role": role_name, "why": budget["why"]}

    cold = cold_context(state or {})
    system, user = _build_prompt(role_name, role_brief, cold)

    ls_seat = llm_seat.Seat(name=f"deepseek_{'deep' if deep else 'bulk'}",
                            base_url=e.get("DEEPSEEK_BASE_URL", "https://openrouter.ai/api/v1"),
                            key=resolve_key(e)[0], model=model)
    text, err = llm_seat.chat(user, system=system, seat=ls_seat,
                              max_tokens=(16000 if deep else 4000))
    if err:
        return {"status": "CALL_FAILED", "role": role_name, "model": model, "why": err}

    rid = run_id or f"{role_name}_{_now()}"
    sealed = seal(rid, role=role_name, phase_a_output=text, policy_hash=str(gate["policy_hash"]),
                 cold_context_hash=cold["cold_context_hash"], provider="openrouter", model=model,
                 root=base)
    if not sealed["ok"]:
        return {"status": "SEAL_CONFLICT", "role": role_name, "why": sealed["why"]}

    try:
        parsed = json.loads(text)
        findings = parsed.get("findings") if isinstance(parsed, dict) else None
        findings = findings if isinstance(findings, list) else []
    except ValueError:
        findings = []

    routed: list[str] = []
    donated: list[dict[str, Any]] = []
    capability_walks: list[dict[str, Any]] = []
    for f in findings:
        if not isinstance(f, dict) or not str(f.get("title", "")).strip():
            continue
        # A model response is DATA, never an instruction (fence()'s own law) -- checked per
        # finding rather than trusted because the check is cheap and the alternative is trusting
        # free text to police itself.
        check = fence("generate_hypothesis")
        syms = [str(s).upper().strip() for s in (f.get("symbols") or [])
                if str(s).strip()] if isinstance(f.get("symbols"), list) else []
        fam = f.get("family")
        fam = str(fam).strip() if isinstance(fam, str) and fam.strip() else None
        row = {"ts": _now(), "role": role_name, "model": model, "deep": deep,
              "seal_path": sealed.get("path"), "title": str(f.get("title"))[:300],
              "mechanism": str(f.get("mechanism") or "")[:2000],
              "testable_claim": str(f.get("testable_claim") or "")[:2000],
              "capability_source": f.get("capability_source"),
              "symbols": syms, "family": fam,
              "evidence_grade": f.get("evidence_grade"), "authority": check["verdict"]}
        _append_jsonl(base / EVIDENCE, row)
        donated.append(row)
        routed.append(row["title"])
        # REVERSE-ENGINEERING PATH (principal 2026-08-20): a finding naming a real capability
        # source is a High-Flyer-class walk candidate, not a bare hypothesis -- route it into
        # capability_challenger's own register() so it is VALIDATED against the mandate's eight
        # stations rather than silently sitting as one more evidence row nobody structures. This
        # only VALIDATES (register()); the benchmark/adopt() verdict needs a real controlled test
        # this text response cannot itself run, so it stays PROPOSED until a human or Claude
        # session executes that test -- same authority boundary as everything else DeepSeek does.
        src = f.get("capability_source")
        if src and str(src).strip():
            capability_walks.append(_propose_capability_walk(
                name=row["title"], source=str(src), mechanism=row["mechanism"],
                evidence_grade=f.get("evidence_grade"), root=base))

    donated_path = _donate(donated, role_name, root=base) if donated else None

    return {"status": "OK", "role": role_name, "model": model, "deep": deep,
           "seal": sealed["verdict"], "n_findings": len(findings), "routed_titles": routed,
           "capability_walks_proposed": len(capability_walks),
           "donated_to": str(donated_path) if donated_path else None,
           "cold_context_removed_keys": cold["removed_keys"]}


#: THE DONATION PATH, and why it is this directory and not the evidence store.
#:
#: The factory's whole stated purpose is that findings reach "every brain on every box within the
#: hour", and its donate step is `git add -- data/ docs/research/`. Measured 2026-09-03: EVERY
#: DeepSeek output store is matched by `.gitignore:11 data/*`, and `git add` on an ignored path is
#: a SILENT NO-OP. So the flywheel ran, committed, pushed, and published none of its own findings
#: -- while the commits it made ("independent cold-phase findings") carried other organs' files
#: swept up by the same blanket add. This is the identical defect sync_shadow_to_git.ps1 documents
#: about itself, in a second file, uncaught.
#:
#: `data/intelligence/` is ALLOWLISTED (`.gitignore:38`), and it is also the exact tree
#: `miner_candidate_compiler.recent_rows` globs for `discoveries_*.json`. Writing here therefore
#: fixes both halves at once: the finding becomes visible to every brain AND enters the same
#: candidate pipeline as all forty miners, through the door that already exists. No new admission
#: path, no compiler change, no gitignore exception.
DONATE_DIR = "data/intelligence/deepseek"


def _donate(rows: list[dict[str, Any]], role_name: str, *, root: Path | None = None) -> Path:
    """Publish this cycle's findings in the miner-discovery contract. Returns the file written."""
    base = root or _ROOT
    out = base / DONATE_DIR
    out.mkdir(parents=True, exist_ok=True)
    path = out / f"discoveries_{_now().replace(':', '').replace('-', '')[:15]}.json"
    path.write_text(json.dumps({
        "source": "deepseek",
        "role": role_name,
        "generated_at": _now(),
        # The compiler reads `discoveries`; each row carries what `compile_row` can actually use.
        # A row without symbols is not dropped -- it becomes a deepening task like any other
        # miner's, and is worked by research/deepening_worker.py rather than lost.
        "discoveries": [{
            "source": "deepseek",
            "title": r["title"],
            "symbols": r.get("symbols") or [],
            "family": r.get("family"),
            "mechanism": r.get("mechanism"),
            "testable_claim": r.get("testable_claim"),
            "mechanism_tags": [t for t in [r.get("family")] if t],
            "kind": "hypothesis",
            "url": f"deepseek://{role_name}/{r['ts']}",
        } for r in rows],
    }, indent=1, default=str), encoding="utf-8")
    return path


def _propose_capability_walk(*, name: str, source: str, mechanism: str,
                             evidence_grade: str | None, root: Path) -> dict[str, Any]:
    """Validate (never adopt) a DeepSeek-proposed High-Flyer/elite-fund/open-strategy capability
    walk against capability_challenger's eight stations, and log the proposal -- register() alone
    does not persist, and record() needs a benchmark verdict this text response cannot produce,
    so the PROPOSAL itself is what gets written here for a later controlled test to complete.
    """
    # FAIL SOFT ON A MISSING OPTIONAL MODULE, and this is not defensive padding -- it is the bug
    # that produced the zero. `libs/research/capability_challenger.py` was absent from the desk
    # branch entirely, so this import raised ModuleNotFoundError for EVERY finding that named a
    # capability_source -- which the prompt explicitly asks for. The exception left run_role()
    # after the seal was written and before anything was donated, so a productive cycle became a
    # crashed one, and `docs/research/capability_challengers.jsonl` (not gitignored, so its
    # emptiness was real) stayed at zero records for the life of the flywheel.
    #
    # The module is now on this branch. This guard stays anyway: a reverse-engineering walk is an
    # ENRICHMENT of a finding, and losing the enrichment must never cost the finding. A cycle that
    # generated ten hypotheses and cannot structure one of them into a walk has still done nine
    # tenths of its job, and the skip is recorded rather than swallowed.
    try:
        from libs.research.capability_challenger import (
            EVIDENCE_GRADES,
            Capability,
            register,
        )
    except ImportError as exc:
        return {"status": "CHALLENGER_UNAVAILABLE", "name": name, "source": source,
                "why": f"{type(exc).__name__}: {exc}"}

    grade = str(evidence_grade or "").strip().upper()
    if grade not in EVIDENCE_GRADES:
        grade = "ANONYMOUS_RUMOR"          # the weakest prior, never invented as something stronger
    cap = Capability(
        name=name, public_capability=f"{source}: {mechanism}"[:2000], evidence_grade=grade,
        economic_mechanism=mechanism, desk_analogue="UNASSESSED -- proposed by DeepSeek, not yet "
        "compared against this desk's current approach",
        gap="UNASSESSED", solo_scale_implementation="UNASSESSED",
        controlled_test="UNASSESSED -- needs a human/Claude session to design and run one",
        source=source)
    verdict = register(cap)
    row = {"ts": _now(), "proposed_by": "deepseek_cycle", "status": "PROPOSED_UNBENCHMARKED",
          "capability": {"name": cap.name, "source": cap.source,
                        "evidence_grade": cap.evidence_grade},
          "registration": verdict}
    _append_jsonl(root / CAPABILITY_LEDGER, row)
    return row

```

### libs\research\hypothesis_graph.py
```python
"""Every hypothesis with its parent and its fate, so the desk stops re-proposing what it buried.

TWO GRAPHS IN ONE LEDGER.

ANCESTRY. Each candidate records where it came from -- the miner row, the proposer sweep, the
deepening task, the certificate it descended from -- as a parent hash. That is what turns
"survivor count" into a lineage: a family that certifies only through one source, a source that
only ever produces one family, a descendant that outlives its parent. `research_queue.json`
already carries a `geneology_id` on 47,150 rows; this is that field made universal and joined
to outcomes.

TWO ANCESTORS, TWO FIELDS (2026-09-17). `seed_key` is the MINER ROW the idea entered the desk
on -- sha of (source, title, url), the join `lead_schema.compiler_parent_key` reproduces and
`knowledge_graph` BECAME resolves against. `parent` is the CELL this one was mutated from, and
until this date it held the seed too: measured on the live ledger, 0 of 35,199 `parent` values
resolved to any of the 23,972 node ids, because the writer recorded the seed it was handed and
threw the donor's explicit parent away. `descendants` had been writing `parent = root_id` (a
real node id) and `operator = descendant:<axis>` into a field that was overwritten one function
later, so `alpha_lineage_search.untried_mutations` found no mutation edge under any family and
`Graph.lineage` could never walk past the first row. A row with no explicit parent still carries
the seed in BOTH fields, so nothing that reads `parent` as a seed today changes.

NEGATIVE KNOWLEDGE. Every cell the gauntlet judged and failed is indexed by (symbol, family,
parameter region). Before a proposer or the compiler admits a candidate, it asks whether the desk
has already buried that region, and how many times. `funnel_census` knows cross_asset_residual
failed 348 times as a FAMILY; this knows that XAUUSD.cross_asset_residual with lookback in
[200, 300) and entry_z in [2, 2.5) failed six times and why. A candidate that lands in a buried
region is not rejected -- the compiler still decides -- but it is CHARGED: the ledger reports the
prior failures and the caller's deflation can count them.

APPEND-ONLY. A node is never edited; a new fate is a new row with the same node id. The current
state of a hypothesis is the last row about it, and its history is every row.

TYPED EDGES (2026-09-08). Until this date the only edge was the scalar `parent` hash, so a
question like "which hypotheses use the COT vintage on JPY crosses" could not be asked of the
ledger at all. Each row now carries `edges: list[dict]`, every edge `{"type", "to"}` plus any
detail, and the types are the ones the compiler's candidates already carry the facts for:

    applies_to_symbol   -> symbol:<SYM>                 from the candidate's `symbol`
    uses_data           -> data:<name>                  from params.input_source, factor_symbols,
                                                        input_symbol, peer_symbol, factors
    mutated_from        -> <parent certificate key>     from `parent` / evidence.parent, with the
                                                        named operator so mutation_yield can bill
    sourced_from        -> url:<source_url>             from the miner row's `source_url`

A row written before this field existed has no `edges` key and reads as []; nothing about the
30,313 existing rows changes. `Graph.query` filters the current state by edge type, target,
symbol, family and fate.
"""
from __future__ import annotations

import hashlib
import json
from collections.abc import Container, Iterable, Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
LEDGER = ROOT / "desks" / "mt5" / "data" / "hypothesis_graph.jsonl"

#: How a parameter is coarsened into a region, per parameter name. Anything not listed is
#: bucketed by its exact value -- most params are discrete already.
REGION_WIDTH: dict[str, float] = {
    "lookback": 100, "beta_win": 100, "window": 250, "refit_days": 100,
    "entry_z": 0.5, "entry_p_leave": 0.1, "hold_bars": 4, "lead_bars": 2,
    "ttl_bars": 24, "stop_atr": 0.5, "rr": 0.5, "min_age": 5,
}

BORN, JUDGED, CERTIFIED, FAILED, RETIRED, BURIED = (
    "BORN", "JUDGED", "CERTIFIED", "FAILED", "RETIRED", "BURIED")

#: The typed edges a row may carry. Anything else on an edge is detail, never a new type.
USES_DATA, APPLIES_TO_SYMBOL, MUTATED_FROM, SOURCED_FROM = (
    "uses_data", "applies_to_symbol", "mutated_from", "sourced_from")
EDGE_TYPES: tuple[str, ...] = (USES_DATA, APPLIES_TO_SYMBOL, MUTATED_FROM, SOURCED_FROM)
#: Parameter names whose VALUE names a dataset or an input series the hypothesis reads.
DATA_PARAMS: tuple[str, ...] = ("input_source", "factor_symbols", "input_symbol",
                                "peer_symbol", "factors")


@dataclass(frozen=True)
class Node:
    symbol: str
    family: str
    params: dict[str, Any]
    source: str = ""
    parent: str = ""
    fate: str = BORN
    why: str = ""
    gates: dict[str, Any] = field(default_factory=dict)
    at: str = ""
    #: Typed edges (`edges_for`). Absent on rows written before 2026-09-08, which read as [].
    edges: list[dict[str, Any]] = field(default_factory=list)
    #: The MINER-ROW hash (`compiler_parent_key`): where the idea entered the desk. Separate
    #: from `parent` since 2026-09-17 -- see `record_candidates`. Empty when there is no seed.
    seed_key: str = ""
    #: The transformation that produced this cell from its parent (`step_lookback_up`,
    #: `descendant:chart`). Written only when the donor named one; never inferred.
    operator: str = ""
    #: The gate the JUDGE said stopped this cell, passed through from the verdict rather than
    #: re-derived from `gates` -- which holds `canonical_report` and nothing else on most rows.
    terminal_gate: str = ""

    @property
    def id(self) -> str:
        return node_id(self.symbol, self.family, self.params)

    @property
    def region(self) -> str:
        return region_key(self.symbol, self.family, self.params)

    def to_row(self) -> dict[str, Any]:
        row = {"id": self.id, "region": self.region, "symbol": self.symbol,
               "family": self.family, "params": self.params, "source": self.source,
               "parent": self.parent, "fate": self.fate, "why": self.why, "gates": self.gates,
               "at": self.at or datetime.now(tz=UTC).isoformat(),
               "edges": [dict(e) for e in self.edges],
               # THE SEED IS NEVER DROPPED. Every caller that set only `parent` was setting the
               # seed, so an unset `seed_key` falls back to it and the BECAME join in
               # `knowledge_graph` keeps resolving on rows written either way.
               "seed_key": self.seed_key or self.parent}
        if self.operator:
            row["operator"] = self.operator
        if self.terminal_gate:
            row["terminal_gate"] = self.terminal_gate
        profile = death_profile(self.gates, self.fate)
        if profile:
            row["death"] = profile
        return row


#: The numeric reading each gate leaves behind, and where it sits inside that gate's dict.
#: Tier-1 item A3: the burial record kept symbol/family/params/region/source/parent/fate/why and
#: the whole `gates` blob, so WHAT it died of was a prose string and HOW BADLY was buried inside
#: a nested dict nothing read. A generator asking "has this region been tried, and how close did
#: it come?" could get the first answer and never the second, so a cell that missed the deflated
#: Sharpe by a hair and one that failed every gate were the same row to the novelty gate.
#: The ten gates in the order external_gauntlet runs them, plus the two pre-gates and the
#: observations check. THE ORDER IS SEPARATE FROM THE READINGS because two gates refuse without
#: leaving a number -- `economic_prior` and `symbol_eligibility` are terminal Gate-1 rejections
#: -- and deriving the order from the readings table put them last, so a cell rejected before it
#: was ever built was reported as dying of its deflated Sharpe.
GATE_ORDER = ("symbol_eligibility", "economic_prior", "observations", "in_sample_screen",
              "deflated_sharpe", "pbo", "reality_check_spa", "cpcv", "walk_forward",
              "stress_costs", "lockbox", "expected_value")

_READINGS = {
    "deflated_sharpe": ("dsr", ("dsr", "value", "deflated_sharpe")),
    "in_sample_screen": ("sharpe", ("sharpe", "value", "sharpe_ratio")),
    "pbo": ("pbo", ("pbo", "value")),
    "reality_check_spa": ("spa_p", ("p_value", "p", "value")),
    "cpcv": ("cpcv_oos_sharpe", ("mean_oos_sharpe", "oos_sharpe", "value")),
    "walk_forward": ("wf_oos_sharpe", ("oos_sharpe", "value")),
    "stress_costs": ("cost_stress_mean", ("mean", "value")),
    "lockbox": ("lockbox_sharpe", ("lockbox_sharpe", "value")),
    "expected_value": ("ev", ("ev", "mean", "value")),
    "observations": ("days", ("days",)),
}


def death_profile(gates: dict[str, Any], fate: str) -> dict[str, Any]:
    """What this cell died of, with the numbers -- not a sentence.

    Returns {} for a fate that is not a death and for a gates blob with nothing in it, so an
    absent profile means "never judged", never "judged and fine". `terminal_gate` is the FIRST
    gate that refused in the ten-gate order, because that is the one a generator must beat;
    `passed` names the gates it did clear, which is where the idea worked.

    ABSENT BY CONSTRUCTION, and named rather than omitted: a correlation profile against the live
    book cannot be computed here (the gauntlet judges a cell against its own returns, never
    against the book), so `correlation_profile` reads ABSENT until an organ that holds both
    writes it.
    """
    if fate not in (FAILED, BURIED, RETIRED) or not isinstance(gates, dict) or not gates:
        return {}
    passed, failed, readings = [], [], {}
    for name, g in gates.items():
        if not isinstance(g, dict):
            continue
        if g.get("passed") is True:
            passed.append(name)
        elif g.get("passed") is False:
            failed.append(name)
        spec = _READINGS.get(name)
        if spec:
            key, fields = spec
            for f in fields:
                v = g.get(f)
                if isinstance(v, (int, float)) and not isinstance(v, bool):
                    readings[key] = round(float(v), 6)
                    break
    terminal = next((k for k in GATE_ORDER if k in failed), failed[0] if failed else "")
    return {"terminal_gate": terminal, "failed": sorted(failed), "passed": sorted(passed),
            "n_gates": len(passed) + len(failed), "readings": readings,
            "unmeasured": bool(gates.get("observations", {}).get("passed") is False),
            "correlation_profile": ("ABSENT: the gauntlet judges a cell against its own returns, "
                                    "never against the live book"),
            "sample_days": readings.get("days")}


def edges_for(symbol: str, params: dict[str, Any], *, parent: str = "", operator: str = "",
              source_url: str = "") -> list[dict[str, Any]]:
    """The typed edges a candidate's own fields imply. Deterministic, deduplicated, ordered.

    Nothing here is inferred: every edge names a field the caller already carried. A candidate
    with no `input_source`, no factor list and no parent gets exactly one edge -- its symbol --
    and that is the honest graph of it.
    """
    out: list[dict[str, Any]] = []
    sym = str(symbol or "").strip().upper()
    if sym:
        out.append({"type": APPLIES_TO_SYMBOL, "to": f"symbol:{sym}"})
    seen: set[str] = set()
    for name in DATA_PARAMS:
        v = (params or {}).get(name)
        if v is None or v == "" or v == []:
            continue
        values = v if isinstance(v, (list, tuple)) else [v]
        for x in values:
            to = f"data:{str(x).strip()}"
            if to in seen or to == "data:":
                continue
            seen.add(to)
            out.append({"type": USES_DATA, "to": to, "via": name})
    if parent:
        e: dict[str, Any] = {"type": MUTATED_FROM, "to": str(parent)}
        if operator:
            e["operator"] = str(operator)
        out.append(e)
    if source_url:
        out.append({"type": SOURCED_FROM, "to": f"url:{str(source_url).strip()}"})
    return out


def edges_of(row: dict[str, Any]) -> list[dict[str, Any]]:
    """A row's typed edges; [] for the rows written before the field existed."""
    e = row.get("edges") if isinstance(row, dict) else None
    return [x for x in e if isinstance(x, dict)] if isinstance(e, list) else []


def node_id(symbol: str, family: str, params: dict[str, Any]) -> str:
    payload = json.dumps({"s": str(symbol).upper(), "f": family, "p": params},
                         sort_keys=True, default=str)
    return hashlib.sha256(payload.encode()).hexdigest()[:16]


def spec_identity(spec: Mapping[str, Any]) -> tuple[str, str, dict[str, Any]]:
    """(symbol, family, params) off any spelling of a spec: a compiled candidate (`symbol`), a
    gauntlet cell or a verdict row (`sym`). ONE reading, so the id a judge stamps on a verdict
    and the id the graph wrote for the same cell cannot drift apart by a field name.

    The chart and the session are NOT read here: both ride inside `params` on every producer
    this desk runs (`descendants.spec_of`, `miner_candidate_compiler.expand_axes`), and folding
    a row-level `timeframe` in would give a verdict an id the BORN row never had. A cell whose
    chart rides on the ROW therefore shares a node with the H1 cell of the same parameters --
    the pre-existing property of `node_id`, named here rather than silently inherited.
    """
    symbol = spec.get("symbol") or spec.get("sym") or ""
    params = spec.get("params")
    return (str(symbol), str(spec.get("family") or ""),
            dict(params) if isinstance(params, Mapping) else {})


def node_id_for_spec(spec: Mapping[str, Any]) -> str:
    """The graph's node id for a spec -- the join key between a judged cell and its hypothesis.

    `external_gauntlet` stamps this on every gate-verdict row as `graph_id`, because the verdict
    ledger names cells as `EURAUD.overnight_gap_decay.p=<sha of params>` while the graph names
    them by this hash: two ids for one cell, and no join between trials and candidates.
    """
    sym, family, params = spec_identity(spec)
    return node_id(sym, family, params)


def _bucket(name: str, value: Any) -> str:
    w = REGION_WIDTH.get(name)
    if w is None or not isinstance(value, (int, float)) or isinstance(value, bool):
        return json.dumps(value, sort_keys=True, default=str)
    lo = (float(value) // w) * w
    return f"[{lo:g},{lo + w:g})"


def region_key(symbol: str, family: str, params: dict[str, Any]) -> str:
    parts = ",".join(f"{k}={_bucket(k, v)}" for k, v in sorted((params or {}).items()))
    return f"{str(symbol).upper()}.{family}{{{parts}}}"


class Graph:
    """The ledger with a read cache keyed on (mtime, size): the backfilled graph holds ~47,000
    rows, and the deepening worker asks `prior_failures` once per queued task, so re-parsing
    the file per question would be O(tasks x rows). An append invalidates the cache."""

    def __init__(self, path: Path = LEDGER) -> None:
        self.path = path
        self._stamp: tuple[float, int] | None = None
        self._rows: list[dict[str, Any]] = []
        self._current: dict[str, dict[str, Any]] | None = None
        self._buried: dict[str, list[dict[str, Any]]] | None = None

    def append(self, node: Node) -> dict[str, Any]:
        row = node.to_row()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, default=str) + "\n")
        self._stamp = None
        return row

    def rows(self) -> list[dict[str, Any]]:
        try:
            st = self.path.stat()
            stamp = (st.st_mtime, st.st_size)
        except OSError:
            return []
        if self._stamp != stamp:
            try:
                self._rows = [json.loads(ln) for ln in self.path.read_text("utf-8").splitlines()
                              if ln.strip()]
            except (OSError, ValueError):
                self._rows = []
            self._stamp = stamp
            self._current = None
            self._buried = None
        return self._rows

    def current(self) -> dict[str, dict[str, Any]]:
        """Last row per node id -- the present fate of every hypothesis ever recorded."""
        rows = self.rows()
        if self._current is None:
            out: dict[str, dict[str, Any]] = {}
            for r in rows:
                out[str(r.get("id"))] = r
            self._current = out
        return self._current

    def buried(self) -> dict[str, list[dict[str, Any]]]:
        """region -> the FAILED/BURIED rows in it. This is the negative-knowledge index."""
        cur = self.current()
        if self._buried is None:
            out: dict[str, list[dict[str, Any]]] = {}
            for r in cur.values():
                if r.get("fate") in (FAILED, BURIED):
                    out.setdefault(str(r.get("region")), []).append(r)
            self._buried = out
        return self._buried

    def prior_failures(self, symbol: str, family: str, params: dict[str, Any]) -> dict[str, Any]:
        """What the desk already knows about this region. Empty means: never tried."""
        key = region_key(symbol, family, params)
        rows = self.buried().get(key, [])
        # HOW CLOSE IT CAME, NOT JUST THAT IT DIED (A3). A region whose best deflated Sharpe was
        # 0.94 against a 0.95 bar is a different object from one that failed every gate, and a
        # novelty gate that cannot tell them apart discards the desk's most promising ground.
        profiles = [p for p in (r.get("death") or death_profile(r.get("gates") or {},
                                                                str(r.get("fate") or ""))
                                for r in rows) if p]
        terminal: dict[str, int] = {}
        best: dict[str, float] = {}
        for p in profiles:
            t = str(p.get("terminal_gate") or "")
            if t:
                terminal[t] = terminal.get(t, 0) + 1
            for k, v in (p.get("readings") or {}).items():
                if isinstance(v, (int, float)):
                    best[k] = max(best.get(k, float(v)), float(v))
        return {"region": key, "n_failed": len(rows),
                "gates_failed": sorted({g for r in rows for g, v in (r.get("gates") or {}).items()
                                        if isinstance(v, dict) and v.get("passed") is False}),
                "last_why": (rows[-1].get("why") if rows else ""),
                "terminal_gates": dict(sorted(terminal.items(), key=lambda kv: -kv[1])),
                "best_readings": {k: round(v, 6) for k, v in sorted(best.items())},
                "profiles": len(profiles)}

    def lineage(self, node_id_: str) -> list[dict[str, Any]]:
        """Walk parents back to the root. A cycle or a missing parent ends the walk."""
        cur = self.current()
        out, seen = [], set()
        n = cur.get(node_id_)
        while n and n["id"] not in seen:
            out.append(n)
            seen.add(n["id"])
            n = cur.get(str(n.get("parent") or ""))
        return out

    def census(self) -> dict[str, Any]:
        cur = self.current()
        by_fate: dict[str, int] = {}
        by_source: dict[str, dict[str, int]] = {}
        by_edge: dict[str, int] = {}
        with_edges = 0
        for r in cur.values():
            by_fate[r.get("fate", "?")] = by_fate.get(r.get("fate", "?"), 0) + 1
            s = by_source.setdefault(str(r.get("source") or "?"), {})
            s[r.get("fate", "?")] = s.get(r.get("fate", "?"), 0) + 1
            es = edges_of(r)
            with_edges += int(bool(es))
            for e in es:
                t = str(e.get("type") or "?")
                by_edge[t] = by_edge.get(t, 0) + 1
        return {"nodes": len(cur), "by_fate": by_fate, "by_source": by_source,
                "buried_regions": len(self.buried()),
                # Nodes written before 2026-09-08 carry no edges; the count says how much of
                # the graph is typed rather than pretending the whole ledger is.
                "nodes_with_edges": with_edges, "by_edge_type": by_edge}

    def query(self, *, edge_type: str | None = None, to: str | None = None,
              symbol: str | None = None, family: str | None = None,
              fate: str | None = None) -> list[dict[str, Any]]:
        """Current-state rows matching every given filter; an omitted filter matches all.

        `edge_type` keeps rows carrying at least one edge of that type; `to` narrows to edges
        whose target is that string or starts with it (`data:` for every dataset edge,
        `symbol:USDJPY` for one instrument). `symbol` is matched case-insensitively.
        """
        if edge_type is not None and edge_type not in EDGE_TYPES:
            raise ValueError(f"unknown edge type {edge_type!r}; expected one of {EDGE_TYPES}")
        sym = str(symbol).upper() if symbol is not None else None
        out: list[dict[str, Any]] = []
        for r in self.current().values():
            if sym is not None and str(r.get("symbol") or "").upper() != sym:
                continue
            if family is not None and str(r.get("family") or "") != family:
                continue
            if fate is not None and str(r.get("fate") or "") != fate:
                continue
            if edge_type is not None or to is not None:
                hit = False
                for e in edges_of(r):
                    if edge_type is not None and e.get("type") != edge_type:
                        continue
                    target = str(e.get("to") or "")
                    if to is not None and not (target == to or target.startswith(to)):
                        continue
                    hit = True
                    break
                if not hit:
                    continue
            out.append(r)
        return out


#: Where a donated candidate may name the PARENT CELL it was mutated from. Read in this order,
#: on the candidate itself and on its `evidence` block, because six producers spell it six ways:
#: `descendants` writes `parent` + `lineage.root`, the distiller writes `evidence.parent`, the
#: recombiners write `parent_ids`, and `libs/moat/registry` reads `parent_ids` back out.
PARENT_FIELDS: tuple[str, ...] = ("parent", "parent_id", "mutated_from")
PARENT_LIST_FIELDS: tuple[str, ...] = ("parent_ids",)
#: The same, inside a `lineage` block.
LINEAGE_FIELDS: tuple[str, ...] = ("root", "parent")
LINEAGE_LIST_FIELDS: tuple[str, ...] = ("parents",)


def _as_parent_id(value: Any) -> str:
    """One claimed parent as a node id: a string is taken as written, a SPEC dict is hashed.

    A spec is canonical by construction -- it IS the node id of that rule -- so it needs no
    lookup; a bare string is only a claim until something resolves it.
    """
    if isinstance(value, Mapping):
        return node_id_for_spec(value) if (value.get("symbol") or value.get("sym")) else ""
    return str(value or "").strip()


def parent_claims(c: Mapping[str, Any]) -> list[str]:
    """Every parent cell id this candidate names, in priority order, deduplicated.

    Claims only. Nothing here is inferred from the mechanism, the family or the source: a row
    that names no parent returns [], which is the honest lineage of a cell nobody stepped from.
    """
    _ev = c.get("evidence")
    blocks: list[Mapping[str, Any]] = [c]
    if isinstance(_ev, Mapping):
        blocks.append(_ev)
    out: list[str] = []

    def _add(value: Any) -> None:
        pid = _as_parent_id(value)
        if pid and pid not in out:
            out.append(pid)

    for block in blocks:
        for name in PARENT_FIELDS:
            _add(block.get(name))
        for name in PARENT_LIST_FIELDS:
            for item in (block.get(name) or []) if isinstance(block.get(name), list) else []:
                _add(item)
        lin = block.get("lineage")
        if isinstance(lin, Mapping):
            for name in LINEAGE_FIELDS:
                _add(lin.get(name))
            for name in LINEAGE_LIST_FIELDS:
                for item in (lin.get(name) or []) if isinstance(lin.get(name), list) else []:
                    _add(item)
    return out


def resolve_parent(c: Mapping[str, Any], known: Container[str]) -> str:
    """The first claimed parent that IS a node of this graph, or "" when none is.

    RESOLUTION IS THE POINT. Measured 2026-09-17 on the live ledger: 0 of 35,199 `parent`
    references resolved to any of the 23,972 node ids, because the writer recorded the SEED it
    was handed rather than the cell that was mutated -- so `alpha_lineage_search.untried_mutations`
    skipped every family, `descendants` wrote `parent = root_id` into a field that was then
    overwritten, and `Graph.lineage` walked exactly one step. An unresolvable claim is NOT
    written into `parent` (that is how the field filled with prose in the first place); it keeps
    its `mutated_from` edge, where a claim is allowed to be a claim.
    """
    for pid in parent_claims(c):
        if pid in known:
            return pid
    return ""


def operator_of(c: Mapping[str, Any]) -> str:
    """The transformation the donor named, from the row or its evidence. Never inferred."""
    _ev = c.get("evidence")
    ev: Mapping[str, Any] = _ev if isinstance(_ev, Mapping) else {}
    return str(c.get("operator") or ev.get("operator") or "")


def seed_key_of(c: Mapping[str, Any]) -> str:
    """The miner row that produced this candidate: sha of (source, title, url), truncated.

    Byte-identical to what `record_candidates` has always stamped into `parent`, and reproduced
    by `lead_schema.compiler_parent_key` -- the ONLY deterministic join from a mined row to the
    cells it became, which is why it is kept in its own field rather than overwritten.
    """
    return hashlib.sha256(json.dumps({"u": c.get("source_url"), "t": c.get("source_title"),
                                      "s": c.get("source")}, sort_keys=True,
                                     default=str).encode()).hexdigest()[:16]


def _candidate_parent_key(c: dict[str, Any]) -> tuple[str, str]:
    """(certificate key the candidate was stepped from, operator) or ("", "").

    The distiller and the mutation proposers carry both on `evidence`; a candidate may also
    carry `parent`, `parent_ids` or a `lineage` block at the top level. A parent that is only
    the miner-row hash (`seed_key_of`) is NOT a mutation and gets no `mutated_from` edge.
    """
    claims = parent_claims(c)
    return (claims[0] if claims else ""), operator_of(c)


def record_candidates(cands: Iterable[dict[str, Any]], source: str,
                      graph: Graph | None = None) -> int:
    """Register newly compiled candidates as BORN, with the miner row that produced each.

    TWO DIFFERENT ANCESTORS, AND THEY USED TO SHARE ONE FIELD. `seed_key` is the miner row the
    idea entered on; `parent` is the CELL this one was mutated from. A candidate that names a
    parent the graph holds gets it -- that is the lineage `alpha_lineage_search`,
    `trajectory_evolution`, `descendants` and `lineage_dag` were written to walk. A candidate
    that names none keeps the seed in `parent` exactly as before, so every reader that treats
    `parent` as a seed still reads one.
    """
    g = graph or Graph()
    # Read once: `append` invalidates the row cache, so asking per candidate would re-parse an
    # 18 MB ledger per row. New nodes are added as they are written, so a batch can be its own
    # ancestry -- a mutation donated beside its parent still resolves.
    known: set[str] = set(g.current())
    n = 0
    for c in cands:
        seed = seed_key_of(c)
        params = dict(c.get("params") or {})
        sym, family, _ = spec_identity(c)
        claims = parent_claims(c)
        op = operator_of(c)
        resolved = next((p for p in claims if p in known), "")
        # The EDGE carries the claim even when nothing resolves it -- an edge is allowed to be a
        # claim, the scalar `parent` is not. The resolved id wins when there is one, so the edge
        # and the field never name two different ancestors.
        mut_parent = resolved or (claims[0] if claims else "")
        node = Node(symbol=sym, family=family,
                    params=params,
                    # THE CANDIDATE'S OWN SOURCE WINS. The compiler registers every candidate it
                    # admits, and stamping them all "miner_candidate_compiler" erased which
                    # proposer found each one -- the bandit's per-arm evidence and the research
                    # P&L attribute by this field.
                    source=str(c.get("source") or source),
                    parent=resolved or seed, seed_key=seed, operator=op,
                    fate=BORN, why=str(c.get("mechanism_note") or "")[:200],
                    edges=edges_for(sym, params, parent=mut_parent, operator=op,
                                    source_url=str(c.get("source_url") or "")))
        g.append(node)
        known.add(node.id)
        n += 1
    return n


def record_verdicts(verdicts: Iterable[dict[str, Any]], graph: Graph | None = None) -> int:
    """Record gauntlet outcomes. A cell that fails any gate is FAILED with the gates it failed."""
    g = graph or Graph()
    n = 0
    for v in verdicts:
        gates = v.get("gates") or {}
        passed_all = bool(gates) and all(isinstance(x, dict) and x.get("passed") is True
                                         for x in gates.values())
        failed = [k for k, x in gates.items() if isinstance(x, dict) and x.get("passed") is False]
        sym, family, params = spec_identity(v)
        g.append(Node(symbol=sym, family=family,
                      params=params, source=str(v.get("hunt") or "gauntlet"),
                      fate=CERTIFIED if passed_all else FAILED,
                      why=("passed all gates" if passed_all else
                           f"failed {', '.join(failed) or 'unmeasured'}"), gates=gates,
                      # WHAT THE JUDGE SAID, not what this row's `gates` blob can be made to
                      # say: 24,027 of 26,843 dead cells carry no terminal gate here because
                      # `gates` holds `canonical_report` alone, while the judging code had the
                      # answer in hand and dropped it on the way in.
                      terminal_gate=str(v.get("terminal_gate") or ""),
                      edges=edges_for(sym, params)))
        n += 1
    return n


CAUSAL_GATE = "causal_adjudication"


def record_causal_verdicts(rows: Iterable[Mapping[str, Any]], graph: Graph | None = None) -> int:
    """Record the causal adjudicator's verdict on a cell as a gate reading (LAWS 5m).

    `rows` carry `symbol`, `family`, `params` and `verdict` (SUPPORTED / REFUTED /
    UNIDENTIFIABLE / UNMEASURED) with `failing_test`. The node keeps its BORN fate: an
    adjudication is a reading about the mechanism, not a fate the gauntlet has not decided
    (L1.60), so it lands in `gates[CAUSAL_GATE]` where `death_profile` and the cartographer can
    see it beside the ten gates without any of them being edited.
    """
    g = graph or Graph()
    n = 0
    for row in rows:
        sym, family, params = spec_identity(row)
        if not sym or not family:
            continue
        verdict = str(row.get("verdict") or "UNMEASURED")
        g.append(Node(symbol=sym, family=family, params=params,
                      source=str(row.get("source") or "event_graph_lab"), fate=BORN,
                      why=f"causal adjudication: {verdict}"
                          + (f" ({row.get('failing_test')})" if row.get("failing_test") else ""),
                      gates={CAUSAL_GATE: {"passed": verdict == "SUPPORTED", "verdict": verdict,
                                           "failing_test": str(row.get("failing_test") or ""),
                                           "effect": row.get("effect"),
                                           "eligible": bool(row.get("eligible"))}},
                      edges=edges_for(sym, params)))
        n += 1
    return n

```

### libs\research\market_constitution.py
```python
"""THE MARKET CONSTITUTION COMPILER -- exchange rules as point-in-time state variables.

WHY A RULE IS A VARIABLE AND NOT A FOOTNOTE. A tape does not know that at 15:26 Tokyo time on
a 2025 trading day the cash market is in a five-minute closing auction that did not exist a
year earlier, that a Korean stock quoted 3% away from its last trade is sitting in a two-minute
single-price call, that an A-share bought this morning cannot be sold until tomorrow, or that
the futures exchange trebled its intraday fee one Monday in 2015. Every one of those is a state
the price was formed under, and a mechanism whose edge depends on it is a mechanism that must
be conditioned on it. This module makes the rule book a column set: deterministic, dated,
cited, and honest about which rows have been checked against their primary document.

THE DSL. A `Venue` is a clock (an IANA zone), a weekly closure, a holiday set and a tuple of
`RuleRow`s. Every RuleRow is one clause of the venue's constitution -- a session timetable of
`Window`s, a price band, a short-sale state, a settlement convention, a fee regime, an HFT
reporting regime -- in force from `effective_from` (inclusive) to `effective_to` (exclusive),
with a `Source` citation and a `verified` flag. `state_at(venue, ts)` evaluates the clauses in
force on the LOCAL date of `ts` and returns one `VenueRuleState`; `stamp` does it for a whole
tape. Nothing in the evaluation reads a row dated after the instant being evaluated, so the
stamp is point-in-time by construction, and `rule_version` names the youngest clause in force
so two stamps from different regimes can never be pooled unnoticed.

VERIFICATION IS A FLAG, NEVER AN ASSUMPTION. Every row is `DECLARED_VERIFY` until the primary
document (the exchange's own rule text, notice or calendar) has been read; `VERIFIED` is used
only for rows whose citation is a document this repository holds and this module's author read
(`desks/mt5/mt5desk/engine.py`, `decision_core.py`). A state built from declared rows lists
them in `unverified`, so a consumer can refuse to size on them.

COUNTRY PACKS ARE CONSUMED, NEVER COPIED. `venue_from_pack_rows` takes a pack's own
`Exchange` / `SessionWindow` / `HolidayRule` / `SettlementRule` instances, duck-typed on their
fields so this module never imports the desk, and turns them into venues. The three Asian
constitutions this module carries in full (TSE/JPX, KRX, SSE/SZSE/CFFEX) and the broker's own
clock (Fusion) are here because no pack holds their intraday state machines.

RULE CHANGES ARE NATURAL EXPERIMENTS. `rule_change_calendar()` lists every dated change with
its mechanism, the instruments it touches and the venues it does not; `rule_change_effect()`
is the one study run on each: a difference in differences of a window statistic between the
affected instrument and an unaffected control venue, with the null drawn from PLACEBO dates on
the same two tapes. A change outside the tape is UNMEASURED with the tape's first date named;
a change in the future is PROSPECTIVE and pre-registered rather than measured.

Sources are public exchange rule books and notices only (JPX, KRX, SSE, SZSE, CFFEX, CSRC,
HKEX), the broker's published conditions, and this repository's own files. No licensed feed.
"""
from __future__ import annotations

import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import asdict, dataclass, field
from datetime import UTC, date, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

import numpy as np

RULES_VERSION = "2026-09-22.1"

DECLARED_VERIFY = "DECLARED_VERIFY"
VERIFIED = "VERIFIED"
VERIFY_STATES = (DECLARED_VERIFY, VERIFIED)

SESSION_STATES = ("CLOSED", "PRE_OPEN", "OPENING_CALL", "CONTINUOUS", "LUNCH", "PRE_CLOSING",
                  "CLOSING_CALL", "AFTER_HOURS", "NIGHT_SESSION", "ROLLOVER", "HOLIDAY",
                  "WEEKEND", "UNDECLARED")
AUCTION_STATES = ("NONE", "ITAYOSE", "ZARABA", "SINGLE_PRICE_CALL", "CLOSING_ITAYOSE",
                  "VI_CALL", "SPECIAL_QUOTE", "SEQUENTIAL_TRADE_QUOTE", "UNOBSERVED",
                  "UNDECLARED")
PRICE_BAND_STATES = ("NO_LIMIT", "WITHIN_LIMITS", "LIMIT_UP", "LIMIT_DOWN", "UNOBSERVED",
                     "UNDECLARED")
SHORT_STATES = ("PERMITTED", "UPTICK_RULE", "PARTIAL_BAN", "BANNED", "OVERHEATED_DESIGNATED",
                "NOT_APPLICABLE", "UNDECLARED")
SETTLEMENT_STATES = ("T+0", "T+1", "T+2", "T+1_LOCKED", "CFD_ROLLOVER", "UNDECLARED")
FEE_REGIMES = ("STANDARD", "CFFEX_2015_CURBS", "CFFEX_RELAXED", "CFFEX_HFT_DIFFERENTIATED",
               "UNDECLARED")
HFT_REGIMES = ("UNREGULATED", "REPORTING", "REPORTING_WITH_THRESHOLDS", "UNDECLARED")

WEEKDAYS: tuple[int, ...] = (0, 1, 2, 3, 4)
KRX_VI_SECONDS = 120            # a volatility interruption is a two-minute single-price call
MIN_PLACEBOS = 20               # below this a placebo null is POORLY_MEASURED, never a verdict
MIN_REGIME_DAYS = 20            # the shorter side of a pre/post comparison must hold this many

_HHMM = re.compile(r"^(\d{1,2}):(\d{2})$")


# --------------------------------------------------------------------------- the DSL
@dataclass(frozen=True)
class Source:
    """Where a rule came from and whether anyone has read it."""

    citation: str
    url: str = ""
    verified: str = DECLARED_VERIFY
    note: str = ""

    def __post_init__(self) -> None:
        if self.verified not in VERIFY_STATES:
            raise ValueError(f"verified must be one of {VERIFY_STATES}: {self.verified!r}")


@dataclass(frozen=True)
class Window:
    """One named window of the venue's LOCAL day, [start, end) as HH:MM wall clock. A window
    whose start is later than its end wraps midnight (a night session)."""

    name: str
    start: str
    end: str
    session_state: str
    auction_state: str = "NONE"
    weekdays: tuple[int, ...] = WEEKDAYS

    def contains(self, minute: int, weekday: int) -> bool:
        lo, hi = _hhmm(self.start), _hhmm(self.end)
        if lo is None or hi is None or weekday not in self.weekdays:
            return False
        if lo <= hi:
            return lo <= minute < hi
        return minute >= lo or minute < hi


@dataclass(frozen=True)
class RuleRow:
    """One clause of a venue's constitution, dated, cited and flagged."""

    rule_id: str
    venue: str
    instrument_class: str
    kind: str
    effective_from: str
    effective_to: str = ""
    spec: Mapping[str, Any] = field(default_factory=dict)
    mechanism: str = ""
    source: Source = field(default_factory=lambda: Source(citation="UNDECLARED"))

    def in_force(self, day: date) -> bool:
        iso = day.isoformat()
        return self.effective_from <= iso and (not self.effective_to or iso < self.effective_to)

    def applies_to(self, instrument_class: str) -> bool:
        return self.instrument_class in ("*", instrument_class) or not instrument_class


@dataclass(frozen=True)
class Venue:
    """A venue: its clock, its closures, its rules and the desk instruments it stamps."""

    venue_id: str
    name: str
    tz: str
    country: str
    instrument_classes: tuple[str, ...]
    rules: tuple[RuleRow, ...] = ()
    weekly_closed: tuple[int, ...] = (5, 6)
    holidays: frozenset[str] = frozenset()
    fixed_md: tuple[str, ...] = ()
    mt5_symbols: tuple[str, ...] = ()
    source: Source = field(default_factory=lambda: Source(citation="UNDECLARED"))

    def with_holidays(self, days: Iterable[str]) -> Venue:
        merged = frozenset(self.holidays) | frozenset(str(d)[:10] for d in days)
        return Venue(venue_id=self.venue_id, name=self.name, tz=self.tz, country=self.country,
                     instrument_classes=self.instrument_classes, rules=self.rules,
                     weekly_closed=self.weekly_closed, holidays=merged, fixed_md=self.fixed_md,
                     mt5_symbols=self.mt5_symbols, source=self.source)


@dataclass(frozen=True)
class VenueRuleState:
    """The rule state of one venue/instrument class at one instant. Every field is a value
    from the vocabularies above; `UNOBSERVED` means the state needs an input the caller did
    not supply (a price against its band), `UNDECLARED` means no rule row covers it."""

    exchange: str
    instrument_class: str
    timestamp: str
    rule_version: str
    session_state: str
    auction_state: str
    price_band: str
    short_state: str
    settlement_state: str
    fee_regime: str
    hft_regime: str
    window: str = ""
    local_time: str = ""
    rule_ids: tuple[str, ...] = ()
    unverified: tuple[str, ...] = ()

    def as_row(self) -> dict[str, Any]:
        row = asdict(self)
        row["rule_ids"] = "+".join(self.rule_ids)
        row["unverified"] = "+".join(self.unverified)
        return row


@dataclass(frozen=True)
class RuleChange:
    """A dated change of one clause: the natural experiment it offers, named in advance."""

    change_id: str
    venue: str
    date: str
    kind: str
    before: str
    after: str
    mechanism: str
    experiment: str
    affected_symbols: tuple[str, ...]
    control_venues: tuple[str, ...]
    source: Source
    window_utc: tuple[str, str] = ("", "")
    control_symbols: tuple[str, ...] = ()
    prospective: bool = False

    def as_row(self) -> dict[str, Any]:
        row = asdict(self)
        row["source"] = asdict(self.source)
        return row


# --------------------------------------------------------------------------- helpers
def _hhmm(text: str) -> int | None:
    m = _HHMM.match(str(text or "").strip())
    if m is None:
        return None
    h, mi = int(m.group(1)), int(m.group(2))
    if h > 24 or mi > 59:
        return None
    return h * 60 + mi


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", str(text).lower()).strip("_")[:48]


_DAY_NAMES = {"mon": 0, "tue": 1, "wed": 2, "thu": 3, "fri": 4, "sat": 5, "sun": 6}


def _weekdays(value: Any, default: tuple[int, ...] = (5, 6)) -> tuple[int, ...]:
    """Weekday numbers from a pack's own spelling: ints, digit strings, or day names in one
    string ('Sat,Sun'). Anything unreadable is the default, never a silent empty closure."""
    if value is None:
        return default
    tokens: list[Any] = (re.split(r"[^A-Za-z0-9]+", value) if isinstance(value, str)
                         else list(value))
    out: list[int] = []
    for tok in tokens:
        if isinstance(tok, int | np.integer):
            out.append(int(tok))
        elif isinstance(tok, str) and tok.strip().isdigit():
            out.append(int(tok.strip()))
        elif isinstance(tok, str) and tok.strip()[:3].lower() in _DAY_NAMES:
            out.append(_DAY_NAMES[tok.strip()[:3].lower()])
    kept = tuple(sorted({d for d in out if 0 <= d <= 6}))
    return kept or default


def _ints(value: Any) -> tuple[int, ...]:
    if value is None or isinstance(value, str):
        return ()
    out: list[int] = []
    for x in value:
        try:
            out.append(int(x))
        except (TypeError, ValueError):
            continue
    return tuple(out)


def _pair(value: Any) -> tuple[str, str]:
    if isinstance(value, str):
        parts = value.split("-", 1)
        return (parts[0].strip(), parts[1].strip() if len(parts) > 1 else "")
    try:
        items = [str(x) for x in value]
    except TypeError:
        return ("", "")
    return (items[0] if items else "", items[1] if len(items) > 1 else "")


def _as_utc(ts: datetime) -> datetime:
    return ts.replace(tzinfo=UTC) if ts.tzinfo is None else ts.astimezone(UTC)


def local_time(ts: datetime, tz: str) -> datetime:
    """`ts` on the venue's wall clock; a naive `ts` is read as UTC."""
    return _as_utc(ts).astimezone(ZoneInfo(tz))


def closed_day_state(venue: Venue, day: date) -> str:
    """'' when the venue is open that day, else WEEKEND or HOLIDAY."""
    if day.weekday() in venue.weekly_closed:
        return "WEEKEND"
    if day.isoformat() in venue.holidays or f"{day.month:02d}-{day.day:02d}" in venue.fixed_md:
        return "HOLIDAY"
    return ""


def rules_in_force(venue: Venue, day: date, instrument_class: str = "") -> tuple[RuleRow, ...]:
    return tuple(r for r in venue.rules if r.in_force(day) and r.applies_to(instrument_class))


def _pick(rows: Sequence[RuleRow], kind: str) -> RuleRow | None:
    """The youngest row of `kind` in force -- a later clause supersedes an earlier one."""
    best: RuleRow | None = None
    for r in rows:
        if r.kind == kind and (best is None or r.effective_from >= best.effective_from):
            best = r
    return best


def _band_state(rule: RuleRow | None, observed: Mapping[str, Any] | None) -> str:
    if rule is None:
        return "UNDECLARED"
    spec = rule.spec
    if spec.get("no_limit"):
        return "NO_LIMIT"
    if not observed or "price" not in observed or "reference" not in observed:
        return "UNOBSERVED"
    try:
        price, ref = float(observed["price"]), float(observed["reference"])
    except (TypeError, ValueError):
        return "UNOBSERVED"
    if ref <= 0:
        return "UNOBSERVED"
    if spec.get("table") == "tse_daily_limit":
        width = tse_daily_price_limit(ref)
    else:
        pct = spec.get("limit_pct")
        if pct is None:
            return "UNOBSERVED"
        width = ref * float(pct) / 100.0
    if price >= ref + width:
        return "LIMIT_UP"
    if price <= ref - width:
        return "LIMIT_DOWN"
    return "WITHIN_LIMITS"


def _window_of(rows: Sequence[RuleRow], minute: int, weekday: int) -> tuple[str, str, str]:
    """(window name, session state, auction state) from the session clause in force."""
    srule = _pick(rows, "session")
    if srule is None:
        return "", "UNDECLARED", "UNDECLARED"
    for w in srule.spec.get("windows", ()):
        if isinstance(w, Window) and w.contains(minute, weekday):
            return w.name, w.session_state, w.auction_state
    return "", "CLOSED", "NONE"


def _fixed_states(rows: Sequence[RuleRow]) -> dict[str, str]:
    out: dict[str, str] = {}
    for kind in ("short", "settlement", "fee", "hft"):
        r = _pick(rows, kind)
        out[kind] = str(r.spec.get("state", "UNDECLARED")) if r is not None else "UNDECLARED"
    return out


def _version(venue: Venue, rows: Sequence[RuleRow]) -> str:
    youngest = max((r.effective_from for r in rows), default="")
    return f"{RULES_VERSION}:{venue.venue_id}@{youngest or 'no-rule'}"


def state_at(venue: Venue, ts: datetime, instrument_class: str = "",
             observed: Mapping[str, Any] | None = None) -> VenueRuleState:
    """The venue's rule state at `ts` (naive = UTC) for one instrument class.

    `observed` may carry what a clock cannot know: `price` and `reference` for the price band,
    `overheated=True` for a KRX overheated-short designation, `vi_until` (ISO UTC) for a
    volatility interruption in progress. Absent inputs read UNOBSERVED, never a guess.
    """
    cls = instrument_class or (venue.instrument_classes[0] if venue.instrument_classes else "")
    loc = local_time(ts, venue.tz)
    day = loc.date()
    rows = rules_in_force(venue, day, cls)
    closed = closed_day_state(venue, day)
    if closed:
        window_name, session, auction = "", closed, "NONE"
    else:
        window_name, session, auction = _window_of(rows, loc.hour * 60 + loc.minute,
                                                   day.weekday())
    obs = observed or {}
    if obs.get("vi_until") and session == "CONTINUOUS":
        try:
            until = datetime.fromisoformat(str(obs["vi_until"]))
            if _as_utc(ts) < _as_utc(until):
                auction = "VI_CALL"
        except ValueError:
            pass
    fixed = _fixed_states(rows)
    short = fixed["short"]
    if obs.get("overheated") and short not in ("BANNED", "NOT_APPLICABLE"):
        short = "OVERHEATED_DESIGNATED"
    return VenueRuleState(
        exchange=venue.venue_id, instrument_class=cls, timestamp=_as_utc(ts).isoformat(),
        rule_version=_version(venue, rows), session_state=session, auction_state=auction,
        price_band=_band_state(_pick(rows, "price_band"), observed),
        short_state=short, settlement_state=fixed["settlement"], fee_regime=fixed["fee"],
        hft_regime=fixed["hft"], window=window_name,
        local_time=loc.strftime("%Y-%m-%d %H:%M %Z"), rule_ids=tuple(r.rule_id for r in rows),
        unverified=tuple(r.rule_id for r in rows if r.source.verified != VERIFIED))


STAMP_COLUMNS: tuple[str, ...] = ("session_state", "auction_state", "price_band", "short_state",
                                  "settlement_state", "fee_regime", "hft_regime", "window",
                                  "rule_version", "n_unverified")


def stamp(venue: Venue, times: Sequence[datetime], instrument_class: str = "",
          observed: Mapping[str, Any] | None = None) -> dict[str, list[Any]]:
    """The PIT column set for a tape: one row per timestamp, columns `STAMP_COLUMNS`.

    Per-day rule resolution is cached, so a six-year hourly tape costs a few thousand rule
    lookups rather than fifty thousand; the per-minute window test is the only per-bar work.
    """
    cls = instrument_class or (venue.instrument_classes[0] if venue.instrument_classes else "")
    zone = ZoneInfo(venue.tz)
    cols: dict[str, list[Any]] = {c: [] for c in STAMP_COLUMNS}
    plans: dict[date, tuple[tuple[RuleRow, ...], str, dict[str, str], str, str, int]] = {}
    for ts in times:
        loc = _as_utc(ts).astimezone(zone)
        day = loc.date()
        plan = plans.get(day)
        if plan is None:
            rows = rules_in_force(venue, day, cls)
            plan = (rows, closed_day_state(venue, day), _fixed_states(rows),
                    _band_state(_pick(rows, "price_band"), observed), _version(venue, rows),
                    sum(1 for r in rows if r.source.verified != VERIFIED))
            plans[day] = plan
        rows, closed, fixed, band, version, n_unv = plan
        if closed:
            window_name, session, auction = "", closed, "NONE"
        else:
            window_name, session, auction = _window_of(rows, loc.hour * 60 + loc.minute,
                                                       day.weekday())
        cols["session_state"].append(session)
        cols["auction_state"].append(auction)
        cols["price_band"].append(band)
        cols["short_state"].append(fixed["short"])
        cols["settlement_state"].append(fixed["settlement"])
        cols["fee_regime"].append(fixed["fee"])
        cols["hft_regime"].append(fixed["hft"])
        cols["window"].append(window_name)
        cols["rule_version"].append(version)
        cols["n_unverified"].append(n_unv)
    return cols


# --------------------------------------------------------------------------- TSE / JPX
#: TSE daily price limits (値幅制限) by base price, yen. Thresholds are exclusive upper bounds.
TSE_LIMIT_TABLE: tuple[tuple[float, float], ...] = (
    (100, 30), (200, 50), (500, 80), (700, 100), (1_000, 150), (1_500, 300), (2_000, 400),
    (3_000, 500), (5_000, 700), (7_000, 1_000), (10_000, 1_500), (15_000, 3_000),
    (20_000, 4_000), (30_000, 5_000), (50_000, 7_000), (70_000, 10_000), (100_000, 15_000),
    (150_000, 30_000), (200_000, 40_000), (300_000, 50_000), (500_000, 70_000),
    (700_000, 100_000), (1_000_000, 150_000), (1_500_000, 300_000), (2_000_000, 400_000),
    (3_000_000, 500_000), (5_000_000, 700_000), (7_000_000, 1_000_000),
    (10_000_000, 1_500_000), (15_000_000, 3_000_000), (20_000_000, 4_000_000),
    (30_000_000, 5_000_000), (50_000_000, 7_000_000))


def tse_daily_price_limit(base_price: float) -> float:
    """The daily limit width (yen, each side) for a TSE base price, from the step table."""
    for upper, width in TSE_LIMIT_TABLE:
        if base_price < upper:
            return float(width)
    return 10_000_000.0


_JPX = Source(citation="JPX, 'Trading Rules of Domestic Stocks' and the 2024-11-05 trading "
                       "hours extension notice (arrowhead4.0: close moved 15:00 -> 15:30, "
                       "closing auction introduced)",
              url="https://www.jpx.co.jp/english/equities/trading/domestic/index.html")
_JPX_RANDOM = Source(citation="JPX announcement of a randomised closing-auction end, planned "
                              "for 2027-10-12 (date as declared to this desk 2026-09-22)",
                     note="prospective; the primary notice has not been read")
_JPX_LIMITS = Source(citation="JPX, daily price limit table (値幅制限) and special / "
                              "sequential-trade quote rules (特別気配, 連続約定気配)")
_OSE = Source(citation="OSE (JPX derivatives), Nikkei 225 futures trading hours; day session "
                       "close extended to 15:45 with the 2024-11-05 change, night session "
                       "17:00-06:00")


def _tse_cash_windows(close: str, closing_auction: bool) -> tuple[Window, ...]:
    """The TSE cash day: itayose open, zaraba, lunch, zaraba, then either a plain closing
    itayose (pre-2024-11-05) or a five-minute closing auction ending in the itayose."""
    tail: tuple[Window, ...]
    if closing_auction:
        tail = (Window("afternoon_zaraba", "12:30", "15:25", "CONTINUOUS", "ZARABA"),
                Window("closing_auction", "15:25", close, "PRE_CLOSING", "CLOSING_ITAYOSE"))
    else:
        tail = (Window("afternoon_zaraba", "12:30", close, "CONTINUOUS", "ZARABA"),)
    return (Window("pre_open_orders", "08:00", "09:00", "PRE_OPEN", "ITAYOSE"),
            Window("morning_zaraba", "09:00", "11:30", "CONTINUOUS", "ZARABA"),
            Window("lunch_orders", "11:30", "12:30", "LUNCH", "ITAYOSE"),
            *tail)


def venue_tse(holidays: Iterable[str] = ()) -> Venue:
    v = "TSE"
    rules = (
        RuleRow("tse.session.pre2024", v, "equity_cash", "session", "2010-01-04", "2024-11-05",
                {"windows": _tse_cash_windows("15:00", False)},
                "continuous zaraba to a 15:00 closing itayose; the last five minutes are "
                "continuous trading", _JPX),
        RuleRow("tse.session.2024_closing_auction", v, "equity_cash", "session", "2024-11-05",
                "", {"windows": _tse_cash_windows("15:30", True)},
                "the close moves to 15:30 and the last five minutes become an order-acceptance "
                "period with no continuous trading (the closing auction), matched by itayose at "
                "15:30 -- closing liquidity concentrates in one print instead of a tape", _JPX),
        RuleRow("tse.session.2027_random_close", v, "equity_cash", "session", "2027-10-12", "",
                {"windows": _tse_cash_windows("15:30", True), "random_end": True},
                "the closing itayose executes at a randomised instant after 15:30, so an order "
                "timed to the last second no longer sees the final imbalance", _JPX_RANDOM),
        RuleRow("tse.price_band.daily_limit", v, "equity_cash", "price_band", "2010-01-04", "",
                {"table": "tse_daily_limit", "special_quote_renewal_min": 3,
                 "sequential_trade_quote_min": 1},
                "a stock at its daily limit cannot print further in that direction; an order "
                "that would cross the renewal price interval posts a special quote renewed "
                "every three minutes, and a run of executions beyond it posts a sequential-"
                "trade quote", _JPX_LIMITS),
        RuleRow("tse.short.uptick", v, "equity_cash", "short", "2013-11-05", "",
                {"state": "UPTICK_RULE"},
                "the uptick rule applies only once a stock has fallen 10% from the previous "
                "close (trigger-type rule since 2013-11-05)", _JPX),
        RuleRow("tse.settlement.t2", v, "equity_cash", "settlement", "2019-07-16", "",
                {"state": "T+2"}, "T+2 settlement since 2019-07-16 (T+3 before)", _JPX),
        RuleRow("ose.session.pre2024", v, "index_futures", "session", "2010-01-04", "2024-11-05",
                {"windows": (Window("day_session", "08:45", "15:15", "CONTINUOUS"),
                             Window("night_session", "16:30", "06:00", "NIGHT_SESSION"))},
                "Nikkei 225 futures day session 08:45-15:15, night session 16:30-06:00", _OSE),
        RuleRow("ose.session.2024", v, "index_futures", "session", "2024-11-05", "",
                {"windows": (Window("day_session", "08:45", "15:45", "CONTINUOUS"),
                             Window("night_session", "17:00", "06:00", "NIGHT_SESSION"))},
                "the day session closes 15:45 after the cash close moved to 15:30", _OSE),
        RuleRow("ose.price_band.circuit", v, "index_futures", "price_band", "2010-01-04", "",
                {"limit_pct": 8.0},
                "a dynamic circuit breaker widens the futures band in steps (8%, 12%, 16%) with "
                "a ten-minute halt at each", _OSE),
        RuleRow("ose.settlement", v, "index_futures", "settlement", "2010-01-04", "",
                {"state": "T+1"}, "daily variation margin", _OSE),
        RuleRow("tse.hft.registration", v, "*", "hft", "2018-04-01", "", {"state": "REPORTING"},
                "high-speed traders register with the FSA under the 2018 FIEA amendment", _JPX),
        RuleRow("tse.hft.none", v, "*", "hft", "2010-01-04", "2018-04-01",
                {"state": "UNREGULATED"}, "no high-speed trading registration", _JPX),
        RuleRow("tse.fee.standard", v, "*", "fee", "2010-01-04", "", {"state": "STANDARD"},
                "no fee regime change in the window", _JPX),
    )
    return Venue(venue_id=v, name="Tokyo Stock Exchange / Osaka Exchange (JPX)", tz="Asia/Tokyo",
                 country="JP", instrument_classes=("equity_cash", "index_futures"), rules=rules,
                 holidays=frozenset(holidays), fixed_md=("01-01", "01-02", "01-03", "12-31"),
                 mt5_symbols=("JPN225", "USDJPY"), source=_JPX)


# --------------------------------------------------------------------------- KRX
_KRX = Source(citation="KRX, KOSPI Market Business Regulation: trading hours (15:30 close since "
                       "2016-08-01), the 15:20-15:30 closing call, dynamic VI (2014-09-01) and "
                       "static VI (2015-06-15), +/-30% daily limit (2015-06-15)")
_KRX_SHORT = Source(citation="FSC / KRX short-sale notices: bans 2008-10-01..2009-05-31, "
                             "2011-08-10..2011-11-09, 2020-03-16..2021-05-02 (partial "
                             "resumption 2021-05-03), 2023-11-06..2025-03-30; overheated-"
                             "stock designation")
_NXT = Source(citation="Nextrade (NXT) alternative trading system launch 2025-03-04: pre-market "
                       "08:00-08:50, after-market 15:30-20:00 KST")


@dataclass(frozen=True)
class VIState:
    """The KRX volatility-interruption machine's state: no call, or a two-minute single-price
    call that ends at `until` (UTC ISO) and was triggered by the named threshold."""

    state: str = "NONE"
    until: str = ""
    trigger: str = ""


def krx_vi_step(current: VIState, ts: datetime, price: float, dynamic_ref: float,
                static_ref: float, *, dynamic_pct: float = 3.0, static_pct: float = 10.0,
                seconds: int = KRX_VI_SECONDS) -> VIState:
    """One transition of the VI machine (deterministic, from the KRX rule).

    CONTINUOUS --(|price/dynamic_ref - 1| >= dynamic_pct or |price/static_ref - 1| >=
    static_pct)--> VI_CALL for `seconds`; VI_CALL --(ts >= until)--> CONTINUOUS, where the
    call's single price becomes the next dynamic reference. A call in progress is never
    re-triggered: the exchange extends nothing before the first one strikes.
    """
    now = _as_utc(ts)
    if current.state == "VI_CALL":
        until = datetime.fromisoformat(current.until) if current.until else now
        if now < _as_utc(until):
            return current
        return VIState()
    if dynamic_ref > 0 and abs(price / dynamic_ref - 1.0) * 100.0 >= dynamic_pct:
        return VIState("VI_CALL", (now + timedelta(seconds=seconds)).isoformat(), "dynamic")
    if static_ref > 0 and abs(price / static_ref - 1.0) * 100.0 >= static_pct:
        return VIState("VI_CALL", (now + timedelta(seconds=seconds)).isoformat(), "static")
    return VIState()


def _krx_windows(call_start: str, close: str) -> tuple[Window, ...]:
    """The KRX cash day: a ten-minute closing call ends the continuous session at `close`."""
    return (Window("pre_open_call", "08:30", "09:00", "PRE_OPEN", "SINGLE_PRICE_CALL"),
            Window("continuous", "09:00", call_start, "CONTINUOUS"),
            Window("closing_call", call_start, close, "CLOSING_CALL", "SINGLE_PRICE_CALL"),
            Window("after_hours_close_price", "15:40", "16:00", "AFTER_HOURS"),
            Window("after_hours_single_price", "16:00", "18:00", "AFTER_HOURS",
                   "SINGLE_PRICE_CALL"))


_KRX_SHORT_MECHANISM = {
    "BANNED": "no new short positions; borrowed-stock supply cannot express negative "
              "information",
    "PARTIAL_BAN": "shorting permitted only in KOSPI200 and KOSDAQ150 constituents",
    "UPTICK_RULE": "covered shorting on an uptick; naked shorting prohibited"}


def _krx_short_rows() -> tuple[RuleRow, ...]:
    spans = (("2008-01-01", "2008-10-01", "UPTICK_RULE"), ("2008-10-01", "2009-06-01", "BANNED"),
             ("2009-06-01", "2011-08-10", "UPTICK_RULE"), ("2011-08-10", "2011-11-10", "BANNED"),
             ("2011-11-10", "2020-03-16", "UPTICK_RULE"), ("2020-03-16", "2021-05-03", "BANNED"),
             ("2021-05-03", "2023-11-06", "PARTIAL_BAN"), ("2023-11-06", "2025-03-31", "BANNED"),
             ("2025-03-31", "", "UPTICK_RULE"))
    return tuple(RuleRow(f"krx.short.{a}", "KRX", "equity_cash", "short", a, b, {"state": s},
                         _KRX_SHORT_MECHANISM[s], _KRX_SHORT) for a, b, s in spans)


def venue_krx(holidays: Iterable[str] = ()) -> Venue:
    v = "KRX"
    rules = (
        RuleRow("krx.session.pre2016", v, "equity_cash", "session", "2008-01-01", "2016-08-01",
                {"windows": _krx_windows("14:50", "15:00")},
                "cash close at 15:00 with a ten-minute closing call from 14:50", _KRX),
        RuleRow("krx.session.2016_extension", v, "equity_cash", "session", "2016-08-01", "",
                {"windows": _krx_windows("15:20", "15:30")},
                "trading extended thirty minutes to a 15:30 close; the closing call is "
                "15:20-15:30 and KOSPI200 derivatives settle from it", _KRX),
        RuleRow("krx.price_band.15pct", v, "equity_cash", "price_band", "2008-01-01",
                "2015-06-15", {"limit_pct": 15.0}, "+/-15% daily limit", _KRX),
        RuleRow("krx.price_band.30pct_static_vi", v, "equity_cash", "price_band", "2015-06-15",
                "", {"limit_pct": 30.0, "static_vi_pct": 10.0, "dynamic_vi_pct": 3.0,
                     "vi_seconds": KRX_VI_SECONDS},
                "the daily limit widens to +/-30% and a static VI (10% from the reference "
                "price) joins the dynamic VI: a breach converts two minutes of continuous "
                "trading into one single-price call", _KRX),
        RuleRow("krx.auction.dynamic_vi", v, "equity_cash", "auction", "2014-09-01", "",
                {"dynamic_vi_pct": 3.0, "vi_seconds": KRX_VI_SECONDS},
                "an order that would execute 3% away from the last trade triggers a two-minute "
                "single-price call instead of a print", _KRX),
        *_krx_short_rows(),
        RuleRow("krx.settlement.t2", v, "equity_cash", "settlement", "2008-01-01", "",
                {"state": "T+2"}, "T+2 settlement", _KRX),
        RuleRow("krx.hft.none", v, "*", "hft", "2008-01-01", "", {"state": "UNREGULATED"},
                "no programmatic-trading reporting regime", _KRX),
        RuleRow("krx.fee.standard", v, "*", "fee", "2008-01-01", "", {"state": "STANDARD"},
                "securities transaction tax stepped down 2023-2025; no HFT differentiation",
                _KRX),
        RuleRow("nxt.session.2025", v, "ats_nxt", "session", "2025-03-04", "",
                {"windows": (Window("pre_market", "08:00", "08:50", "PRE_OPEN"),
                             Window("main", "09:00", "15:20", "CONTINUOUS"),
                             Window("after_market", "15:30", "20:00", "AFTER_HOURS"))},
                "a second venue extends the Korean cash day to twelve hours; the closing "
                "call keeps its monopoly on the settlement print", _NXT),
    )
    return Venue(venue_id=v, name="Korea Exchange (KRX)", tz="Asia/Seoul", country="KR",
                 instrument_classes=("equity_cash", "ats_nxt"), rules=rules,
                 holidays=frozenset(holidays), fixed_md=("01-01", "12-31"),
                 mt5_symbols=("USDKRW",), source=_KRX)


# --------------------------------------------------------------------------- SSE / SZSE / CFFEX
_SSE = Source(citation="SSE / SZSE Trading Rules: 09:15-09:25 opening call, continuous 09:30-"
                       "11:30 and 13:00-14:57, closing call 14:57-15:00 (SZSE since 2006, SSE "
                       "since 2018-08-20); +/-10% main boards, +/-20% ChiNext (2020-08-24) "
                       "and STAR (2019-07-22); T+1 for A shares")
_CSRC = Source(citation="CSRC Provisions on the Administration of Programmatic Trading in the "
                        "Securities Market (in force 2024-10-08); SSE/SZSE implementation rules "
                        "(in force 2025-07-07; HFT = >=300 orders/second or >=20,000 "
                        "orders/day); exchange reporting regime from 2023-10-09")
_CSRC_OCT25 = Source(citation="programmatic/HFT reporting and differentiated-fee regime from "
                              "October 2025, as declared to this desk (blueprint 2026-09-22)",
                     note="the exchange notice and its exact effective date have not been read")
_CFFEX = Source(citation="CFFEX notices: 2015-09-07 curbs (intraday round-trip fee 23bp, 40% "
                         "margin, 10-lot 'abnormal trading' threshold) and the relaxations of "
                         "2017-02-17, 2017-09-18, 2018-12-03 and 2019-04-22; 2026 "
                         "differentiated fees for high-frequency programmatic trading (date as "
                         "declared to this desk)")
_CONNECT = Source(citation="HKEX Stock Connect trading calendar: northbound trades only when "
                           "both markets are open and the money-settlement day is a Hong Kong "
                           "banking day")

_A_SHARE_WINDOWS: tuple[Window, ...] = (
    Window("opening_call", "09:15", "09:25", "OPENING_CALL", "SINGLE_PRICE_CALL"),
    Window("pre_open_gap", "09:25", "09:30", "PRE_OPEN"),
    Window("morning", "09:30", "11:30", "CONTINUOUS"),
    Window("lunch", "11:30", "13:00", "LUNCH"),
    Window("afternoon", "13:00", "14:57", "CONTINUOUS"),
    Window("closing_call", "14:57", "15:00", "CLOSING_CALL", "SINGLE_PRICE_CALL"))


def venue_sse_szse(holidays: Iterable[str] = ()) -> Venue:
    v = "SSE_SZSE"
    hft_thresholds = {"orders_per_second": 300, "orders_per_day": 20_000}
    rules = (
        RuleRow("sse.session.2018_closing_call", v, "a_share", "session", "2018-08-20", "",
                {"windows": _A_SHARE_WINDOWS},
                "the last three minutes of the SSE day become a single-price call (SZSE had "
                "one since 2006); the close is one print, and closing-price manipulation moves "
                "to the call", _SSE),
        RuleRow("sse.session.pre2018", v, "a_share", "session", "2010-01-04", "2018-08-20",
                {"windows": (*_A_SHARE_WINDOWS[:4],
                             Window("afternoon", "13:00", "15:00", "CONTINUOUS"))},
                "SSE closed on continuous trading", _SSE),
        RuleRow("sse.price_band.10pct", v, "a_share", "price_band", "2010-01-04", "",
                {"limit_pct": 10.0, "chinext_star_pct": 20.0, "st_pct": 5.0},
                "a +/-10% limit (20% on ChiNext since 2020-08-24 and STAR since 2019-07-22, "
                "5% on ST stocks) truncates the day's distribution and defers information to "
                "the next open", _SSE),
        RuleRow("sse.settlement.t1", v, "a_share", "settlement", "2010-01-04", "",
                {"state": "T+1_LOCKED"},
                "A shares bought today cannot be sold until tomorrow: intraday reversal is "
                "unavailable to the buyer, so the next open carries the unwind", _SSE),
        RuleRow("sse.short.designated", v, "a_share", "short", "2010-03-31", "",
                {"state": "PARTIAL_BAN"},
                "margin trading and securities lending only in designated securities; "
                "securities lending was curtailed from 2024-01-28 and suspended 2024-07-11",
                _SSE),
        RuleRow("sse.hft.unregulated", v, "*", "hft", "2010-01-04", "2023-10-09",
                {"state": "UNREGULATED"}, "no programmatic-trading reporting", _CSRC),
        RuleRow("sse.hft.reporting_2023", v, "*", "hft", "2023-10-09", "2025-07-07",
                {"state": "REPORTING"},
                "programmatic traders must file with the exchange before trading; the "
                "exchange can see who the machine is", _CSRC),
        RuleRow("sse.hft.thresholds_2025", v, "*", "hft", "2025-07-07", "2025-10-01",
                {"state": "REPORTING_WITH_THRESHOLDS", **hft_thresholds},
                "high-frequency trading is defined by order rate and put under differentiated "
                "supervision, fee and reporting duties", _CSRC),
        RuleRow("sse.hft.oct2025", v, "*", "hft", "2025-10-01", "",
                {"state": "REPORTING_WITH_THRESHOLDS", "differentiated_fees": True,
                 **hft_thresholds},
                "the October 2025 regime adds differentiated fees for high-frequency "
                "programmatic trading; the marginal cost of a cancelled order rises", _CSRC_OCT25),
        RuleRow("sse.fee.standard", v, "a_share", "fee", "2010-01-04", "", {"state": "STANDARD"},
                "stamp duty on sales halved to 0.05% on 2023-08-28", _SSE),
        RuleRow("connect.calendar", v, "a_share", "settlement_calendar", "2014-11-17", "",
                {"rule": "northbound open only when SSE/SZSE and SEHK are both open and T+1 "
                         "is a HK banking day"},
                "a mainland day the Connect is shut removes the northbound marginal buyer",
                _CONNECT),
    )
    return Venue(venue_id=v, name="Shanghai and Shenzhen Stock Exchanges", tz="Asia/Shanghai",
                 country="CN", instrument_classes=("a_share",), rules=rules,
                 holidays=frozenset(holidays), fixed_md=("01-01",),
                 mt5_symbols=("USDCNH", "CHINAH", "HK50"), source=_SSE)


_CFFEX_FEE_ERAS: tuple[tuple[str, str, str, str], ...] = (
    ("2010-04-16", "2015-09-07", "STANDARD", "intraday round-trip fee 0.23bp, margin 10-20%: "
     "an index-futures venue that clears a fifth of the cash turnover daily"),
    ("2015-09-07", "2017-02-17", "CFFEX_2015_CURBS", "intraday round-trip fee raised "
     "one-hundred-fold to 23bp, margin 40%, ten lots a day counted as abnormal: turnover fell "
     "~99% and the basis went to a persistent discount"),
    ("2017-02-17", "2019-04-22", "CFFEX_RELAXED", "stepwise relaxation: 20 lots, margin 20%, "
     "fee 9.2bp (2017-02-17); fee 6.9bp (2017-09-18); 50 lots, fee 4.6bp (2018-12-03)"),
    ("2019-04-22", "2026-01-01", "STANDARD", "500 lots, margin 10-12%, fee 3.45bp"),
    ("2026-01-01", "", "CFFEX_HFT_DIFFERENTIATED", "differentiated fees for high-frequency "
     "programmatic trading (2026, date as declared to this desk)"))


def venue_cffex(holidays: Iterable[str] = ()) -> Venue:
    v = "CFFEX"
    rules = (
        RuleRow("cffex.session.pre2016", v, "index_futures", "session", "2010-04-16",
                "2016-01-01", {"windows": (Window("morning", "09:15", "11:30", "CONTINUOUS"),
                                           Window("lunch", "11:30", "13:00", "LUNCH"),
                                           Window("afternoon", "13:00", "15:15", "CONTINUOUS"))},
                "futures opened fifteen minutes before the cash market and closed fifteen after",
                _CFFEX),
        RuleRow("cffex.session.2016", v, "index_futures", "session", "2016-01-01", "",
                {"windows": (Window("morning", "09:30", "11:30", "CONTINUOUS"),
                             Window("lunch", "11:30", "13:00", "LUNCH"),
                             Window("afternoon", "13:00", "15:00", "CONTINUOUS"))},
                "futures hours aligned to the cash market after the 2015 crash", _CFFEX),
        RuleRow("cffex.price_band.10pct", v, "index_futures", "price_band", "2010-04-16", "",
                {"limit_pct": 10.0}, "+/-10% daily limit", _CFFEX),
        RuleRow("cffex.settlement.t0", v, "index_futures", "settlement", "2010-04-16", "",
                {"state": "T+0"}, "daily mark-to-market", _CFFEX),
        RuleRow("cffex.short.na", v, "index_futures", "short", "2010-04-16", "",
                {"state": "NOT_APPLICABLE"}, "a future is sold, not shorted", _CFFEX),
        *(RuleRow(f"cffex.fee.{a}", v, "index_futures", "fee", a, b, {"state": s}, m, _CFFEX)
          for a, b, s, m in _CFFEX_FEE_ERAS),
        RuleRow("cffex.hft.follows_csrc", v, "index_futures", "hft", "2024-10-08", "",
                {"state": "REPORTING"}, "programmatic-trading reporting per the CSRC provisions",
                _CSRC),
    )
    return Venue(venue_id=v, name="China Financial Futures Exchange", tz="Asia/Shanghai",
                 country="CN", instrument_classes=("index_futures",), rules=rules,
                 holidays=frozenset(holidays), fixed_md=("01-01",),
                 mt5_symbols=("CHINAH", "HK50"), source=_CFFEX)


# --------------------------------------------------------------------------- Fusion (the broker)
_FUSION_ENGINE = Source(citation="desks/mt5/mt5desk/engine.py ROLLOVER_HOUR_UTC=21, "
                                 "TRIPLE_SWAP_WEEKDAY=2 (server UTC+2 winter / UTC+3 summer; "
                                 "the earlier hour is used deliberately)", verified=VERIFIED)
_FUSION_CLOSE = Source(citation="desks/mt5/mt5desk/decision_core.py CLOSE_HOUR=19.5 (the desk "
                                "force-closes the gold book at 19:30 UTC)", verified=VERIFIED)
_FUSION_EQUITY_HOURS = Source(citation="NYSE/Nasdaq core trading session 09:30-16:00 New York "
                                       "(public); Fusion share CFDs quote the underlying's "
                                       "cash session",
                              note="the broker's share-CFD specification page has not been "
                                   "read; the New York / Athens DST mismatch weeks are unread")
_FUSION_HOURS = Source(citation="Fusion Markets published trading hours (FX Sunday 22:05 - "
                                "Friday 21:55 UTC-equivalent; metals and index CFDs with a "
                                "daily break around server midnight)",
                       note="the broker's contract-specification page has not been read; the "
                            "server's DST switch dates (EU vs US) are unknown")


def venue_fusion() -> Venue:
    v = "FUSION"
    fx = (Window("fx_week", "00:05", "23:55", "CONTINUOUS"),
          Window("rollover", "23:55", "00:05", "ROLLOVER"))
    metals = (Window("metals_day", "01:00", "23:59", "CONTINUOUS"),
              Window("metals_break", "23:59", "01:00", "ROLLOVER"))
    # NYSE/Nasdaq core session 09:30-16:00 New York is 16:30-23:00 on the server's own clock
    # (Athens, seven hours ahead of New York in both seasons but for the two or three weeks the
    # two DST switches disagree, which the source note names as unread).
    equities = (Window("us_cash", "16:30", "23:00", "CONTINUOUS"),
                Window("us_closed", "23:00", "16:30", "CLOSED"))
    rules = (
        RuleRow("fusion.session.fx", v, "forex", "session", "2010-01-04", "", {"windows": fx},
                "24/5 with a rollover at server midnight; the desk counts it at 21:00 UTC "
                "and Wednesday's carries three days", _FUSION_HOURS),
        RuleRow("fusion.session.metals", v, "metals", "session", "2010-01-04", "",
                {"windows": metals}, "an hourly daily break around server midnight",
                _FUSION_HOURS),
        RuleRow("fusion.session.indices", v, "indices", "session", "2010-01-04", "",
                {"windows": metals},
                "index CFDs follow the underlying future's near-24h clock with a daily break",
                _FUSION_HOURS),
        RuleRow("fusion.session.equities", v, "equities", "session", "2010-01-04", "",
                {"windows": equities},
                "share CFDs trade the underlying's cash session only; an overnight gap is the "
                "whole of the close-to-open move", _FUSION_EQUITY_HOURS),
        RuleRow("fusion.rollover.swap", v, "*", "rollover", "2010-01-04", "",
                {"rollover_hour_utc": 21, "triple_swap_weekday": 2},
                "financing is charged at the rollover; a position held across it pays or "
                "earns the swap, three times on Wednesday", _FUSION_ENGINE),
        RuleRow("fusion.settlement.cfd", v, "*", "settlement", "2010-01-04", "",
                {"state": "CFD_ROLLOVER"}, "cash-settled CFD, financed nightly", _FUSION_ENGINE),
        RuleRow("fusion.desk_close.gold", v, "metals", "desk_close", "2025-01-01", "",
                {"close_utc": "19:30", "book": "gold"},
                "the desk's own rule: the gold book is flat by 19:30 UTC", _FUSION_CLOSE),
        RuleRow("fusion.short.cfd", v, "*", "short", "2010-01-04", "", {"state": "PERMITTED"},
                "a CFD is sold as freely as bought", _FUSION_HOURS),
        RuleRow("fusion.price_band.none", v, "*", "price_band", "2010-01-04", "",
                {"no_limit": True}, "no daily limit; the underlying venue's halts pass through",
                _FUSION_HOURS),
        RuleRow("fusion.fee.standard", v, "*", "fee", "2010-01-04", "", {"state": "STANDARD"},
                "commission per lot plus spread", _FUSION_HOURS),
        RuleRow("fusion.hft.none", v, "*", "hft", "2010-01-04", "", {"state": "UNREGULATED"},
                "no reporting regime", _FUSION_HOURS),
    )
    return Venue(venue_id=v, name="Fusion Markets (MT5 server clock)", tz="Europe/Athens",
                 country="AU", instrument_classes=("forex", "metals", "indices"), rules=rules,
                 mt5_symbols=("XAUUSD", "EURUSD", "USDJPY"), source=_FUSION_HOURS)


def builtin_venues(holidays: Mapping[str, Iterable[str]] | None = None) -> dict[str, Venue]:
    """The venues this module carries in full, with per-venue holiday sets injected by the
    caller (the desk reads them from the country packs and the Japan calendar; this module
    holds only the fixed-date closures every year shares)."""
    h = holidays or {}
    return {"TSE": venue_tse(h.get("TSE", ())), "KRX": venue_krx(h.get("KRX", ())),
            "SSE_SZSE": venue_sse_szse(h.get("SSE_SZSE", ())),
            "CFFEX": venue_cffex(h.get("CFFEX", ())), "FUSION": venue_fusion()}


# --------------------------------------------------------------------------- country packs
def venue_from_pack_rows(code: str, exchanges: Sequence[Any], session_windows: Sequence[Any],
                         holidays_rule: Any, settlement_rules: Sequence[Any],
                         mt5_symbols: Sequence[str] = ()) -> tuple[Venue, ...]:
    """Venues from a country pack's own rows (`libs.research.country_lab` types, duck-typed).

    One venue per `Exchange` row: its `open_utc`/`close_utc` become a CONTINUOUS window on a
    UTC clock (the pack already converted), every `SessionWindow` becomes a named window, the
    `HolidayRule` becomes the holiday set and weekly closure, every `SettlementRule` a
    settlement clause, and `expiry_dates` an expiry clause. Nothing is re-declared here: the
    citation is the pack file and the flag is DECLARED_VERIFY because the pack's rows carry
    their own VERIFY labels.
    """
    cc = str(code).lower()
    src = Source(citation=f"desks/mt5/research/countries/{cc}/pack.py",
                 note="consumed from the country pack's own rows")
    raw_dates = getattr(holidays_rule, "dates", ()) or ()
    hol_dates = frozenset(str(d)[:10] for d in ([raw_dates] if isinstance(raw_dates, str)
                                                else raw_dates))
    raw_md = getattr(holidays_rule, "fixed_md", ()) or ()
    fixed_md = tuple(str(x) for x in ([raw_md] if isinstance(raw_md, str) else raw_md))
    weekly = _weekdays(getattr(holidays_rule, "weekly_closed", None))
    named = tuple(Window(_slug(getattr(w, "name", "") or "window"),
                         str(getattr(w, "start_utc", "")), str(getattr(w, "end_utc", "")),
                         "CONTINUOUS")
                  for w in session_windows
                  if _hhmm(str(getattr(w, "start_utc", ""))) is not None
                  and _hhmm(str(getattr(w, "end_utc", ""))) is not None)
    out: list[Venue] = []
    for ex in exchanges:
        name = str(getattr(ex, "name", "") or "")
        if not name:
            continue
        vid = f"{cc.upper()}:{_slug(name)}"
        opn, cls = str(getattr(ex, "open_utc", "")), str(getattr(ex, "close_utc", ""))
        rules: list[RuleRow] = []
        if _hhmm(opn) is not None and _hhmm(cls) is not None:
            # the pack's NAMED windows are listed first: the first window that contains the
            # minute wins, and a closing call inside the cash day must outrank the cash day
            rules.append(RuleRow(f"{vid}.session", vid, "*", "session", "2000-01-01", "",
                                 {"windows": (*named, Window("cash", opn, cls, "CONTINUOUS"))},
                                 str(getattr(ex, "notes", "") or ""), src))
        elif named:
            rules.append(RuleRow(f"{vid}.session", vid, "*", "session", "2000-01-01", "",
                                 {"windows": named}, "pack session windows only", src))
        expiry = tuple(str(d) for d in (getattr(ex, "expiry_dates", ()) or ()))
        expiry_rule = str(getattr(ex, "expiry_rule", None) or "")
        if expiry or expiry_rule:
            rules.append(RuleRow(f"{vid}.expiry", vid, "*", "expiry", "2000-01-01", "",
                                 {"expiry_rule": expiry_rule, "expiry_dates": expiry},
                                 "index derivatives settle on these dates", src))
        for i, sr in enumerate(settlement_rules):
            rules.append(RuleRow(f"{vid}.settlement.{_slug(getattr(sr, 'name', '') or str(i))}",
                                 vid, "*", "settlement_convention", "2000-01-01", "",
                                 {"kind": str(getattr(sr, "kind", "")),
                                  "days": _ints(getattr(sr, "days", ())),
                                  "months": _ints(getattr(sr, "months", ())),
                                  "roll": str(getattr(sr, "roll", "")),
                                  "window_utc": _pair(getattr(sr, "window_utc", ("", ""))),
                                  "instruments": tuple(
                                      str(s) for s in (getattr(sr, "instruments", ()) or ())
                                      if not isinstance(s, str) or len(s) > 1)},
                                 str(getattr(sr, "notes", "") or ""), src))
        syms = (tuple(str(s) for s in (getattr(ex, "index_symbols", ()) or ()))
                or tuple(mt5_symbols))
        out.append(Venue(venue_id=vid, name=name, tz="UTC", country=cc.upper(),
                         instrument_classes=("*",), rules=tuple(rules), weekly_closed=weekly,
                         holidays=hol_dates, fixed_md=fixed_md, mt5_symbols=syms, source=src))
    return tuple(out)


# --------------------------------------------------------------------------- the calendar
_MAINLAND = ("01:30", "07:00")
_CN_SPILL = ("CHINAH", "HK50")


def rule_change_calendar() -> tuple[RuleChange, ...]:
    """Every dated rule change this module knows, with its mechanism and its experiment."""
    rows = (
        RuleChange("tse_closing_auction_2024", "TSE", "2024-11-05", "session",
                   "15:00 close, last five minutes continuous",
                   "15:30 close, 15:25-15:30 closing auction (no continuous trading)",
                   "closing liquidity concentrates in one itayose print thirty minutes later; "
                   "the cash close leaves the 14:00-15:00 JST hour and enters 15:00-16:00",
                   "share of JPN225's daily absolute move carried by the 06:00 UTC bar "
                   "(15:00-16:00 JST) before vs after, less the same on HK50 (no change), "
                   "null from placebo dates", ("JPN225",), ("HKEX",), _JPX,
                   ("06:00", "07:00"), ("HK50",)),
        RuleChange("tse_random_close_2027", "TSE", "2027-10-12", "session",
                   "closing itayose at exactly 15:30",
                   "closing itayose at a randomised instant after 15:30",
                   "the last-second order that reads the final imbalance loses its target; "
                   "pre-close positioning spreads over the auction window",
                   "PRE-REGISTERED (the statistic rule_change_effect runs, fixed now): share of "
                   "JPN225's daily absolute move carried by the 06:00 UTC bar, 120 trading days "
                   "each side, control HK50, placebo change dates every 10 trading days on the "
                   "same tapes; decision rule |DiD| beyond the 95th placebo percentile. The "
                   "15:25-15:30 JST return's autocorrelation with 15:30-16:00 is an EXTENSION "
                   "that needs M5 bars the desk does not yet hold for JPN225",
                   ("JPN225",), ("HKEX",),
                   _JPX_RANDOM, ("06:00", "07:00"), ("HK50",), prospective=True),
        RuleChange("krx_price_limit_30pct_2015", "KRX", "2015-06-15", "price_band",
                   "+/-15% daily limit", "+/-30% daily limit with static VI",
                   "a wider band lets a day's information print in a day; limit-hit "
                   "continuation moves to intraday VI calls", "USDKRW's KRX-hours share of "
                   "daily absolute move before vs after, control USDJPY", ("USDKRW",),
                   ("TSE",), _KRX, ("00:00", "06:30"), ("USDJPY",)),
        RuleChange("krx_hours_extension_2016", "KRX", "2016-08-01", "session",
                   "15:00 close", "15:30 close",
                   "thirty more minutes of Korean cash trading overlap the European pre-open",
                   "USDKRW's 06:00-07:00 UTC share before vs after, control USDJPY",
                   ("USDKRW",), ("TSE",), _KRX, ("06:00", "07:00"), ("USDJPY",)),
        RuleChange("krx_short_ban_2023", "KRX", "2023-11-06", "short",
                   "shorting in KOSPI200/KOSDAQ150 constituents", "full short-sale ban",
                   "negative information cannot be expressed through borrowed stock; foreign "
                   "hedged long-short books unwind and the currency leg goes with them",
                   "USDKRW's KRX-hours share of daily absolute move before vs after, control "
                   "USDJPY", ("USDKRW",), ("TSE",), _KRX_SHORT, ("00:00", "06:30"),
                   ("USDJPY",)),
        RuleChange("krx_nxt_launch_2025", "KRX", "2025-03-04", "session",
                   "one venue, 09:00-15:30", "NXT pre-market 08:00 and after-market to 20:00",
                   "Korean equity price discovery extends into the European morning; the "
                   "currency's after-hours window gains an equity print to react to",
                   "USDKRW's 06:30-11:00 UTC share before vs after, control USDJPY",
                   ("USDKRW",), ("TSE",), _NXT, ("06:30", "11:00"), ("USDJPY",)),
        RuleChange("krx_short_resumption_2025", "KRX", "2025-03-31", "short",
                   "full short-sale ban", "shorting resumed market-wide with an uptick rule",
                   "the reverse of 2023-11-06", "as krx_short_ban_2023, signs reversed",
                   ("USDKRW",), ("TSE",), _KRX_SHORT, ("00:00", "06:30"), ("USDJPY",)),
        RuleChange("krx_vi_activations", "KRX", "2014-09-01", "auction",
                   "continuous trading through a 3% jump",
                   "a two-minute single-price call on every 3% (dynamic) or 10% (static) jump",
                   "a VI converts a print into a call: the post-VI single price should carry "
                   "less short-horizon reversal than an uninterrupted jump",
                   "UNMEASURED by construction on this desk: per-stock VI activation records "
                   "(KRX market data) are not held; USDKRW cannot see a single stock's call",
                   (), ("TSE",), _KRX),
        RuleChange("sse_closing_call_2018", "SSE_SZSE", "2018-08-20", "session",
                   "SSE closed on continuous trading", "14:57-15:00 closing call on SSE",
                   "the Shanghai close becomes one print; closing-price manipulation and the "
                   "index-fund closing flow move into the call",
                   "CHINAH's 06:00-07:00 UTC share before vs after, control JPN225",
                   _CN_SPILL, ("TSE",), _SSE, ("06:00", "07:00"), ("JPN225",)),
        RuleChange("cffex_curbs_2015", "CFFEX", "2015-09-07", "fee",
                   "0.23bp intraday fee, 10-20% margin", "23bp intraday fee, 40% margin, "
                   "10-lot abnormal-trading threshold",
                   "index-futures turnover collapses ~99%; hedging demand moves to H shares "
                   "and offshore, the A/H basis and the CNH carry the unmet hedge",
                   "CHINAH's mainland-hours share before vs after, control JPN225",
                   ("CHINAH", "USDCNH"), ("TSE",), _CFFEX, _MAINLAND, ("JPN225",)),
        RuleChange("china_programmatic_2024", "SSE_SZSE", "2024-10-08", "hft",
                   "exchange reporting only", "CSRC programmatic-trading provisions in force",
                   "programmatic traders bear reporting, monitoring and differentiated "
                   "supervision; the marginal machine order costs more, spreads in the "
                   "mainland session widen and the H-share hedge absorbs the difference",
                   "CHINAH and HK50's mainland-hours (01:30-07:00 UTC) share before vs after, "
                   "control JPN225", _CN_SPILL, ("TSE",), _CSRC, _MAINLAND, ("JPN225",)),
        RuleChange("china_programmatic_impl_2025", "SSE_SZSE", "2025-07-07", "hft",
                   "provisions without thresholds", "HFT defined at 300 orders/s, 20,000/day",
                   "a named threshold caps the order rate of the fastest participants",
                   "as china_programmatic_2024", _CN_SPILL, ("TSE",), _CSRC, _MAINLAND,
                   ("JPN225",)),
        RuleChange("china_programmatic_oct_2025", "SSE_SZSE", "2025-10-01", "hft",
                   "thresholds", "differentiated fees for high-frequency programmatic trading",
                   "the cancelled order is charged; quote refresh rates fall and the mainland "
                   "book thins at the top", "as china_programmatic_2024",
                   _CN_SPILL, ("TSE",), _CSRC_OCT25, _MAINLAND, ("JPN225",)),
        RuleChange("cffex_hft_fee_2026", "CFFEX", "2026-01-01", "fee",
                   "one fee for all", "differentiated fees for high-frequency trading",
                   "index-futures liquidity provision by the fastest participants is taxed; "
                   "the futures basis widens intraday and the H-share hedge is used more",
                   "CHINAH and HK50's mainland-hours share before vs after, control JPN225",
                   _CN_SPILL, ("TSE",), _CFFEX, _MAINLAND, ("JPN225",)),
    )
    return tuple(sorted(rows, key=lambda r: (r.date, r.change_id)))


# --------------------------------------------------------------------------- the experiment
def window_share_by_day(times: np.ndarray, close: np.ndarray,
                        window_utc: tuple[str, str]) -> tuple[np.ndarray, np.ndarray]:
    """Per trading day: the share of the day's absolute log move carried by bars whose OPEN
    minute (UTC) falls in `window_utc`. Days with no move are dropped, never zero-filled."""
    lo, hi = _hhmm(window_utc[0]), _hhmm(window_utc[1])
    if lo is None or hi is None or close.size < 3:
        return np.zeros(0, dtype="datetime64[D]"), np.zeros(0)
    c = np.asarray(close, dtype="float64")
    t = np.asarray(times, dtype="datetime64[ns]")[1:]
    with np.errstate(divide="ignore", invalid="ignore"):
        r = np.abs(np.diff(np.log(c)))
    ok = np.isfinite(r)
    t, r = t[ok], r[ok]
    days = t.astype("datetime64[D]")
    mins = ((t - days).astype("timedelta64[m]").astype("int64")) % 1440
    in_w = ((mins >= lo) & (mins < hi)) if lo <= hi else ((mins >= lo) | (mins < hi))
    uniq, inv = np.unique(days, return_inverse=True)
    tot = np.bincount(inv, weights=r, minlength=uniq.size)
    win = np.bincount(inv, weights=r * in_w, minlength=uniq.size)
    keep = tot > 0
    return uniq[keep], win[keep] / tot[keep]


def placebo_dates(days: np.ndarray, change: np.datetime64, pre: int, post: int,
                  step: int = 10) -> np.ndarray:
    """Candidate placebo change dates on `days` (sorted datetime64[D]): every `step` trading
    days, with `pre` days of room before and `post` after, and no overlap with the true
    change's own pre/post windows. The true date is never a placebo of itself."""
    n = days.size
    if n < pre + post + 1:
        return np.zeros(0, dtype="datetime64[D]")
    true_idx = int(np.searchsorted(days, change))
    idx = np.arange(pre, n - post, max(1, int(step)))
    idx = idx[np.abs(idx - true_idx) >= (pre + post)]
    return days[idx]


def _did_at(days_a: np.ndarray, share_a: np.ndarray, days_c: np.ndarray, share_c: np.ndarray,
            at: np.datetime64, pre: int, post: int) -> tuple[float | None, dict[str, Any]]:
    ia, ic = int(np.searchsorted(days_a, at)), int(np.searchsorted(days_c, at))
    pa, qa = share_a[max(0, ia - pre):ia], share_a[ia:ia + post]
    pc, qc = share_c[max(0, ic - pre):ic], share_c[ic:ic + post]
    detail: dict[str, Any] = {"n_pre_affected": int(pa.size), "n_post_affected": int(qa.size),
                              "n_pre_control": int(pc.size), "n_post_control": int(qc.size)}
    if min(pa.size, qa.size, pc.size, qc.size) < MIN_REGIME_DAYS:
        return None, detail
    did = (float(qa.mean()) - float(pa.mean())) - (float(qc.mean()) - float(pc.mean()))
    detail.update({"pre_affected": round(float(pa.mean()), 6),
                   "post_affected": round(float(qa.mean()), 6),
                   "pre_control": round(float(pc.mean()), 6),
                   "post_control": round(float(qc.mean()), 6)})
    return did, detail


def rule_change_effect(times: np.ndarray, close: np.ndarray, ctrl_times: np.ndarray,
                       ctrl_close: np.ndarray, change_date: str, window_utc: tuple[str, str],
                       *, pre_days: int = 120, post_days: int = 120, step: int = 10,
                       today: date | None = None) -> dict[str, Any]:
    """The natural experiment: a difference in differences of the window share between the
    affected tape and an unaffected control tape across `change_date`, with the null drawn
    from placebo change dates on the same two tapes.

    Verdicts: PROSPECTIVE (the change is after today), UNMEASURED (the change is outside the
    tape, first/last dates named), POORLY_MEASURED (too few regime days or placebos, counts
    named), MEASURED (did, p_placebo, the placebo distribution's quantiles, and the four
    regime means so a reader can see which side moved).
    """
    out: dict[str, Any] = {"verdict": "UNMEASURED", "change_date": change_date,
                           "window_utc": list(window_utc), "pre_days": int(pre_days),
                           "post_days": int(post_days), "n_placebo": 0}
    try:
        change = np.datetime64(change_date[:10], "D")
    except ValueError:
        out["why"] = f"change_date {change_date!r} is not ISO"
        return out
    now = today or datetime.now(UTC).date()
    if change > np.datetime64(now.isoformat(), "D"):
        out["verdict"] = "PROSPECTIVE"
        out["why"] = f"{change_date} is after {now.isoformat()}: pre-registered, not measured"
        return out
    days_a, share_a = window_share_by_day(times, close, window_utc)
    days_c, share_c = window_share_by_day(ctrl_times, ctrl_close, window_utc)
    if days_a.size == 0 or days_c.size == 0:
        out["why"] = "a tape is empty or the window is malformed"
        return out
    first, last = str(days_a[0]), str(days_a[-1])
    out["tape"] = {"first": first, "last": last, "n_days": int(days_a.size),
                   "control_n_days": int(days_c.size)}
    if change < days_a[0] or change > days_a[-1]:
        out["why"] = f"{change_date} is outside the tape {first}..{last}"
        return out
    did, detail = _did_at(days_a, share_a, days_c, share_c, change, pre_days, post_days)
    out.update(detail)
    if did is None:
        out["verdict"] = "POORLY_MEASURED"
        out["why"] = f"a regime side holds fewer than {MIN_REGIME_DAYS} days"
        return out
    draws: list[float] = []
    for p in placebo_dates(days_a, change, pre_days, post_days, step):
        d, _ = _did_at(days_a, share_a, days_c, share_c, p, pre_days, post_days)
        if d is not None:
            draws.append(d)
    arr = np.asarray(draws, dtype="float64")
    out["did"] = round(did, 6)
    out["n_placebo"] = int(arr.size)
    if arr.size < MIN_PLACEBOS:
        out["verdict"] = "POORLY_MEASURED"
        out["why"] = f"{arr.size} placebo dates < {MIN_PLACEBOS}"
        return out
    p = float((1 + int((np.abs(arr) >= abs(did)).sum())) / (1 + arr.size))
    out.update({"verdict": "MEASURED", "p_placebo": round(p, 6),
                "placebo_abs_q50": round(float(np.quantile(np.abs(arr), 0.5)), 6),
                "placebo_abs_q95": round(float(np.quantile(np.abs(arr), 0.95)), 6),
                "significant_5pct": bool(p <= 0.05), "significant_10pct": bool(p <= 0.10),
                "controls": ["unaffected control venue (difference in differences)",
                             "placebo change dates on the same tapes"]})
    return out


def unverified_rules(venues: Iterable[Venue]) -> list[dict[str, str]]:
    """Every rule row still waiting for its document, by venue -- the reading list."""
    return [{"venue": v.venue_id, "rule_id": r.rule_id, "citation": r.source.citation}
            for v in venues for r in v.rules if r.source.verified != VERIFIED]


# --------------------------------------------------------------------------- constraints
#: THE REGISTRY COMPILED INTO CONSTRAINTS THE MACHINE CAN READ. `universe.json` is MetaTrader's
#: own answer about every symbol (tick size, digits, contract size, volume step, swaps) and the
#: venue rules above say when the symbol trades, when it halts and how it settles. Neither is a
#: constraint until the two are joined per symbol, and until that join is a FILE a placer and a
#: campaign runner can read without importing this module. `compile_constraints` is that join.
#: An axis the registry does not carry (margin: the terminal's `margin_initial` is never synced
#: into the registry; the stops/freeze distance: read live at the order) is UNMEASURED by name on
#: the row -- the gateway reads the terminal for those and the row says so.
MEASURED = "MEASURED"
UNMEASURED = "UNMEASURED"
PARTIAL = "PARTIAL"
#: The broker registry's `asset_class` vocabulary (MetaTrader's own path names, lower-cased) ->
#: the Fusion instrument class its rule rows are keyed by. A class absent here is UNCLASSIFIED:
#: its session clause reads UNDECLARED, never a neighbour's hours.
CLASS_OF_ASSET: dict[str, str] = {
    "forex": "forex", "forex exotics": "forex", "forex majors": "forex", "forex minors": "forex",
    # MetaTrader files the spot metals (XAUUSD, XAGUSD, XPTUSD, the base metals) under
    # "Commodities" on this broker (measured on the registry 2026-09-22: 12 symbols, all X??USD
    # metals); the softs carry their own class and no session clause yet.
    "metals": "metals", "commodities": "metals", "indices": "indices", "equities": "equities",
    "us share cfds": "equities", "share cfds": "equities",
    "soft commodity": "softs", "energy": "energy", "crypto": "crypto", "bonds": "bonds",
}
#: Registry fields a constraint row is compiled from, by axis.
TICK_FIELDS: tuple[str, ...] = ("tick_size", "digits", "tick_value", "contract_size",
                                "volume_min", "volume_step", "median_spread_pts",
                                "spread_pts_at_collection")
MARGIN_FIELDS: tuple[str, ...] = ("margin_initial", "margin_maintenance", "margin_rate",
                                  "margin_hedged", "margin_currency")
CONSTRAINT_AXES: tuple[str, ...] = ("sessions", "halts", "tick", "margin", "settlement")
CONSTRAINTS_RULE = ("one row per registry symbol: sessions, halts, tick, margin and settlement "
                    "joined from MetaTrader's registry row and the venue rules in force on the "
                    "broker's local date; an axis the registry does not carry is UNMEASURED by "
                    "name and the gateway reads the terminal for it; a row is an INPUT to the "
                    "placer and the campaign runner, never a cap, a veto or a filter")
STOPS_LEVEL_WHY = ("the registry does not carry trade_stops_level or trade_freeze_level; the "
                   "gateway reads both from the terminal's symbol_info at the order")
MARGIN_WHY = ("the registry carries no margin field (the terminal's margin_initial is not "
              "synced); the gateway reads it at the order")


def instrument_class_of(asset_class: Any) -> str:
    """The Fusion instrument class of a registry `asset_class`, '' when unclassified."""
    return CLASS_OF_ASSET.get(str(asset_class or "").strip().lower(), "")


def next_closed_day(venue: Venue, day: date, horizon_days: int = 14) -> tuple[str, str] | None:
    """(ISO date, WEEKEND | HOLIDAY) of the venue's next closed day at or after `day` inside the
    horizon; None when every day in the horizon is open."""
    for i in range(max(1, int(horizon_days))):
        d = day + timedelta(days=i)
        state = closed_day_state(venue, d)
        if state:
            return d.isoformat(), state
    return None


def symbol_venue_map(venues: Iterable[Venue]) -> dict[str, str]:
    """Upper-cased MT5 symbol -> the UNDERLYING venue that lists it. The broker's own venue is
    excluded because every symbol trades on it; the first listing venue wins."""
    out: dict[str, str] = {}
    for v in venues:
        if v.venue_id == "FUSION":
            continue
        for s in v.mt5_symbols:
            out.setdefault(str(s).upper(), v.venue_id)
    return out


def _num(v: Any) -> float | None:
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        return None
    f = float(v)
    return f if np.isfinite(f) else None


def _windows_of(rows: Sequence[RuleRow]) -> list[dict[str, Any]]:
    srule = _pick(rows, "session")
    if srule is None:
        return []
    return [{"name": w.name, "start": w.start, "end": w.end, "state": w.session_state,
             "auction": w.auction_state, "weekdays": list(w.weekdays)}
            for w in srule.spec.get("windows", ()) if isinstance(w, Window)]


def compile_symbol(symbol: str, meta: Mapping[str, Any], broker: Venue, now: datetime,
                   underlying: Venue | None = None) -> dict[str, Any]:
    """One symbol's constraint row: the registry row joined to the broker's rules in force on
    its local date at `now`, and to the underlying venue's state where one lists the symbol."""
    cls = instrument_class_of(meta.get("asset_class"))
    ts = _as_utc(now)
    st = state_at(broker, ts, cls or "unclassified")
    loc_day = local_time(ts, broker.tz).date()
    rows = rules_in_force(broker, loc_day, cls or "unclassified")
    windows = _windows_of(rows)
    roll = _pick(rows, "rollover")
    close = _pick(rows, "desk_close")
    under_state = state_at(underlying, ts) if underlying is not None else None
    nxt = next_closed_day(broker, loc_day)
    unmeasured: list[str] = []
    tick = {k: _num(meta.get(k)) for k in TICK_FIELDS}
    tick_ok = tick["tick_size"] is not None and tick["digits"] is not None
    if not tick_ok:
        unmeasured.append("tick: the registry row carries no tick_size/digits")
    margin_vals = {k: meta.get(k) for k in MARGIN_FIELDS if meta.get(k) is not None}
    if not margin_vals:
        unmeasured.append("margin: " + MARGIN_WHY)
    sessions_ok = st.session_state != "UNDECLARED"
    if not sessions_ok:
        unmeasured.append(f"sessions: no session clause for instrument class "
                          f"{cls or 'unclassified'!r} on {broker.venue_id}")
    status = (MEASURED if tick_ok and sessions_ok and margin_vals
              else PARTIAL if tick_ok else UNMEASURED)
    margin: dict[str, Any] = {"status": MEASURED if margin_vals else UNMEASURED, **margin_vals}
    if not margin_vals:
        margin["why"] = MARGIN_WHY
    return {
        "symbol": symbol, "asset_class": meta.get("asset_class"),
        "instrument_class": cls or UNMEASURED, "venue": broker.venue_id, "venue_tz": broker.tz,
        "sessions": {"status": MEASURED if sessions_ok else UNMEASURED, "windows": windows,
                     "state_now": st.session_state, "auction_now": st.auction_state,
                     "window_now": st.window, "local_time": st.local_time,
                     "closed_today": closed_day_state(broker, loc_day) or "",
                     "next_closed_day": nxt[0] if nxt else None,
                     "next_closed_state": nxt[1] if nxt else None,
                     "underlying_state_now": (under_state.session_state if under_state
                                              else None)},
        "halts": {"price_band": st.price_band, "weekly_closed": list(broker.weekly_closed),
                  "n_holidays": len(broker.holidays),
                  "daily_break": next((w for w in windows if w["state"] == "ROLLOVER"), None),
                  "desk_close_utc": (close.spec.get("close_utc") if close is not None
                                     else None),
                  "desk_close_book": close.spec.get("book") if close is not None else None,
                  "underlying_venue": underlying.venue_id if underlying is not None else None,
                  "underlying_price_band": (under_state.price_band if under_state
                                            else None)},
        "tick": {**tick, "status": MEASURED if tick_ok else UNMEASURED,
                 "stops_level": None, "freeze_level": None, "stops_level_why": STOPS_LEVEL_WHY},
        "margin": margin,
        "settlement": {"state": st.settlement_state,
                       "rollover_hour_utc": (roll.spec.get("rollover_hour_utc")
                                             if roll is not None else None),
                       "triple_swap_weekday": (roll.spec.get("triple_swap_weekday")
                                               if roll is not None else None),
                       "swap_long": _num(meta.get("swap_long")),
                       "swap_short": _num(meta.get("swap_short")),
                       "currency_profit": meta.get("currency_profit"),
                       "underlying_settlement": (under_state.settlement_state if under_state
                                                 else None)},
        "short_state": st.short_state, "fee_regime": st.fee_regime,
        "rule_version": st.rule_version, "rule_ids": list(st.rule_ids),
        "unverified": list(st.unverified), "status": status, "unmeasured": unmeasured,
    }


def compile_constraints(universe: Mapping[str, Any], venues: Sequence[Venue],
                        now: datetime) -> dict[str, Any]:
    """The whole registry compiled into machine-readable constraints at `now`.

    Pure: the registry mapping and the venues are given, nothing is read. The broker's venue is
    the FUSION venue among `venues` (or the module's own when absent); a symbol listed by another
    venue's `mt5_symbols` carries that venue's state beside the broker's as its underlying.
    """
    by_id = {v.venue_id: v for v in venues}
    broker = by_id.get("FUSION") or venue_fusion()
    under_ids = symbol_venue_map(venues)
    rows: dict[str, dict[str, Any]] = {}
    by_status: dict[str, int] = {}
    by_class: dict[str, int] = {}
    unmeasured_axes: dict[str, int] = {}
    for sym in sorted(universe):
        meta = universe[sym]
        if not isinstance(meta, Mapping):
            continue
        under = by_id.get(under_ids.get(str(sym).upper(), ""))
        row = compile_symbol(str(sym), meta, broker, now, under)
        rows[str(sym)] = row
        by_status[row["status"]] = by_status.get(row["status"], 0) + 1
        by_class[row["instrument_class"]] = by_class.get(row["instrument_class"], 0) + 1
        for u in row["unmeasured"]:
            axis = u.split(":", 1)[0]
            unmeasured_axes[axis] = unmeasured_axes.get(axis, 0) + 1
    return {
        "generated_at": _as_utc(now).isoformat(timespec="seconds"),
        "rules_version": RULES_VERSION, "venue": broker.venue_id, "venue_tz": broker.tz,
        "n_symbols": len(rows), "by_status": by_status, "by_instrument_class": by_class,
        "axes": list(CONSTRAINT_AXES), "unmeasured_axes": unmeasured_axes,
        "n_unverified_rules": sum(1 for r in broker.rules if r.source.verified != VERIFIED),
        "symbols": rows, "rule": CONSTRAINTS_RULE,
    }

```

### libs\research\model_families.py
```python
"""MODEL-FAMILY SEARCH as its own civilization (Tier-1 item 6).

Ten families -- linear, sparse, tree, boosting, neural, state-space, Bayesian, sequence, graph,
mixture-of-experts -- each with the same discipline a factor gets: a lineage (which family it
descends from), a novelty key (nothing is re-tested under a new name), a falsifier (the declared
tax it must clear out of sample) and a verdict that can be UNMEASURED.

WHY THIS FILE IMPORTS NOTHING HEAVY AT MODULE SCOPE. `libs.models.zoo` reaches straight into
sklearn: on a box without it, every model family in the desk is a crash, and a crash is not a
verdict. Here EVERY family has a pure-Python fallback -- no numpy, no pandas, no sklearn -- so
the civilization always runs, and the heavy backend is a guarded accelerator whose absence is
recorded as `heavy_verdict: UNMEASURED` on that family's row rather than raised. That is the
law's "absence is never a clean verdict" applied to the learner instead of the data.

THE TAX IS THE FALSIFIER. A family's declared tax (nats per prediction) prices its freedom:
capacity, instability across folds, and -- for `sequence` and `state_space` -- the staleness of
the labels it needs before it can predict at all. `net_gain = OOS log score - baseline - tax`,
and only `net_gain > 0` is EARNS_ITS_PLACE. Two families that tie on gain are separated by the
tax, which is why a boosted stump has to beat a ridge by a measurable margin to be preferred.

The scoring convention is `libs.models.zoo`'s, deliberately: expanding-window folds, mean OOS
log score against the train-fold base rate, so a row from here and a row from the zoo are
comparable in COEVOLUTION.json without a translation table.
"""
from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any

UNMEASURED = "UNMEASURED"
POSITIVE = "EARNS_ITS_PLACE"
NEGATIVE = "TAXED_OUT"
#: Rows a family needs before its mean is a number rather than an anecdote.
MIN_ROWS = 120
EPS = 1e-6


@dataclass(frozen=True)
class Family:
    """One model family as the civilization sees it."""

    name: str
    #: Declared tax in nats per prediction -- the bar this family's gain must clear.
    tax: float
    #: The family it descends from; "" for a root. Lineage, exactly as a factor carries one.
    parent: str = ""
    #: Heavy backends tried in order before the pure-Python fallback.
    backends: tuple[str, ...] = ()
    #: What the family assumes -- the sentence a falsification has to contradict.
    assumption: str = ""
    #: Axes this family can be mutated along when a residual asks for a challenger.
    mutations: tuple[str, ...] = field(default_factory=tuple)

    @property
    def novelty_key(self) -> str:
        return f"{self.name}|{self.parent}"


FAMILIES: dict[str, Family] = {
    "linear": Family("linear", 0.0, "", ("sklearn.linear_model",),
                     "the conditional mean is linear in the standardised features",
                     ("alpha", "features")),
    "sparse": Family("sparse", 0.0005, "linear", ("sklearn.linear_model",),
                     "only a few features carry signal; the rest are exactly zero",
                     ("l1", "features")),
    "tree": Family("tree", 0.0010, "", ("sklearn.tree",),
                   "the response is piecewise constant on axis-aligned regions",
                   ("depth", "min_leaf")),
    "boosting": Family("boosting", 0.0015, "tree", ("sklearn.ensemble",),
                       "many shallow, shrunken corrections beat one deep fit",
                       ("n_rounds", "shrinkage", "depth")),
    "neural": Family("neural", 0.0025, "", ("sklearn.neural_network", "torch"),
                     "a smooth low-dimensional nonlinearity fits the response",
                     ("hidden", "l2", "epochs")),
    "state_space": Family("state_space", 0.0015, "linear", ("statsmodels.tsa.statespace",),
                          "the edge is a slowly drifting latent level, observed with noise",
                          ("q_over_r", "window")),
    "bayesian": Family("bayesian", 0.0005, "linear", ("sklearn.naive_bayes",),
                       "class-conditional features are Gaussian and independent given the sign",
                       ("prior_strength",)),
    "sequence": Family("sequence", 0.0015, "linear", ("torch",),
                       "the recent path of the target itself predicts its next sign",
                       ("lags", "alpha")),
    "graph": Family("graph", 0.0015, "linear", ("networkx",),
                    "features are nodes; a consensus over correlated neighbours beats each one",
                    ("k", "threshold")),
    "mixture_of_experts": Family("mixture_of_experts", 0.0020, "linear",
                                 ("libs.models.router",),
                                 "the population is a mixture; one expert per gate bucket",
                                 ("n_experts", "gate_feature")),
}
#: The order a search walks the civilization in: cheapest tax first, so an expensive family is
#: only reached once the cheap ones have failed to explain the same rows.
ORDER: tuple[str, ...] = tuple(sorted(FAMILIES, key=lambda k: (FAMILIES[k].tax, k)))


# --------------------------------------------------------------- guarded heavy backends
def _import(mod: str) -> Any:
    try:
        __import__(mod)
    except Exception:
        return None
    import sys
    return sys.modules.get(mod)


def availability() -> dict[str, dict[str, Any]]:
    """Per family: which declared backends are importable here, and the verdict when none is.

    A family whose heavy backend is absent still RUNS on its pure-Python fallback; what is
    UNMEASURED is the heavy backend's own contribution, and that is what this records. An
    absent library is never a crash and never a zero.
    """
    out: dict[str, dict[str, Any]] = {}
    for name, fam in FAMILIES.items():
        present = [m for m in fam.backends if _import(m) is not None]
        out[name] = {
            "backends_declared": list(fam.backends),
            "backends_present": present,
            "backend": "heavy" if present else "fallback",
            "heavy_verdict": "MEASURED" if present else UNMEASURED,
            "why": "" if present else (
                f"none of {list(fam.backends) or ['(no heavy backend declared)']} importable "
                "here; the pure-Python fallback carries this family and the heavy backend's "
                "contribution is UNMEASURED, not zero"),
            "tax": fam.tax, "parent": fam.parent, "assumption": fam.assumption,
        }
    return out


# --------------------------------------------------------------- pure-Python linear algebra
def _solve(a: list[list[float]], b: list[float]) -> list[float] | None:
    """Gaussian elimination with partial pivoting. None when singular."""
    n = len(b)
    m = [row[:] + [b[i]] for i, row in enumerate(a)]
    for col in range(n):
        piv = max(range(col, n), key=lambda r: abs(m[r][col]))
        if abs(m[piv][col]) < 1e-12:
            return None
        m[col], m[piv] = m[piv], m[col]
        pv = m[col][col]
        for r in range(n):
            if r == col:
                continue
            f = m[r][col] / pv
            if f:
                for c in range(col, n + 1):
                    m[r][c] -= f * m[col][c]
    return [m[i][n] / m[i][i] for i in range(n)]


def _standardise(xtr: list[list[float]], xte: list[list[float]]
                 ) -> tuple[list[list[float]], list[list[float]]]:
    if not xtr:
        return xtr, xte
    p = len(xtr[0])
    mu = [sum(r[j] for r in xtr) / len(xtr) for j in range(p)]
    sd = []
    for j in range(p):
        v = sum((r[j] - mu[j]) ** 2 for r in xtr) / max(1, len(xtr))
        sd.append(math.sqrt(v) if v > 0 else 1.0)
    def _z(rows: list[list[float]]) -> list[list[float]]:
        return [[(r[j] - mu[j]) / sd[j] for j in range(p)] for r in rows]
    return _z(xtr), _z(xte)


def _squash(raw: float, k: float = 4.0) -> float:
    return 1.0 / (1.0 + math.exp(-max(-50.0, min(50.0, k * raw))))


def _ridge(x: list[list[float]], y: list[float], alpha: float) -> list[float] | None:
    p = len(x[0]) if x else 0
    if p == 0:
        return None
    xtx = [[sum(r[i] * r[j] for r in x) + (alpha if i == j else 0.0) for j in range(p)]
           for i in range(p)]
    xty = [sum(r[i] * t for r, t in zip(x, y, strict=True)) for i in range(p)]
    return _solve(xtx, xty)


def _pred_linear(w: list[float], x: list[list[float]], k: float = 4.0) -> list[float]:
    return [_squash(sum(wi * xi for wi, xi in zip(w, r, strict=True)), k) for r in x]


# --------------------------------------------------------------- the ten fallbacks
def _f_linear(xtr, ytr, xte, **kw):                                   # type: ignore[no-untyped-def]
    w = _ridge(xtr, [2.0 * v - 1.0 for v in ytr], float(kw.get("alpha", 10.0)))
    if w is None:
        return None
    return _pred_linear(w, xte)


def _f_sparse(xtr, ytr, xte, **kw):                                   # type: ignore[no-untyped-def]
    """ISTA: ridge start, then soft-threshold toward exact zeros."""
    lam = float(kw.get("l1", 0.15))
    w = _ridge(xtr, [2.0 * v - 1.0 for v in ytr], 10.0)
    if w is None:
        return None
    w = [0.0 if abs(c) < lam else math.copysign(abs(c) - lam, c) for c in w]
    if not any(w):
        return [0.5] * len(xte)
    return _pred_linear(w, xte)


def _best_split(x: list[list[float]], y: list[float], cols: Sequence[int]
                ) -> tuple[int, float, float, float] | None:
    n = len(y)
    if n < 8:
        return None
    best = None
    for j in cols:
        vals = sorted({r[j] for r in x})
        if len(vals) < 3:
            continue
        for q in (0.25, 0.5, 0.75):
            thr = vals[int(q * (len(vals) - 1))]
            lo = [y[i] for i in range(n) if x[i][j] <= thr]
            hi = [y[i] for i in range(n) if x[i][j] > thr]
            if len(lo) < 4 or len(hi) < 4:
                continue
            pl, ph = sum(lo) / len(lo), sum(hi) / len(hi)
            # weighted Gini reduction
            imp = (len(lo) * pl * (1 - pl) + len(hi) * ph * (1 - ph)) / n
            if best is None or imp < best[3]:
                best = (j, float(thr), pl, imp)
    if best is None:
        return None
    j, thr, pl, imp = best
    hi = [y[i] for i in range(n) if x[i][j] > thr]
    return (j, thr, pl, sum(hi) / len(hi))


def _f_tree(xtr, ytr, xte, **kw):                                     # type: ignore[no-untyped-def]
    cols = range(len(xtr[0]))
    root = _best_split(xtr, ytr, cols)
    if root is None:
        return None
    j, thr, p_lo, p_hi = root
    depth = int(kw.get("depth", 2))
    sub: dict[bool, tuple[int, float, float, float] | None] = {True: None, False: None}
    if depth > 1:
        for side in (True, False):
            idx = [i for i in range(len(ytr)) if (xtr[i][j] > thr) is side]
            if len(idx) >= 16:
                sub[side] = _best_split([xtr[i] for i in idx], [ytr[i] for i in idx], cols)
    out = []
    for r in xte:
        side = r[j] > thr
        node = sub[side]
        if node is not None:
            jj, tt, a, b = node
            out.append(b if r[jj] > tt else a)
        else:
            out.append(p_hi if side else p_lo)
    return [min(1 - EPS, max(EPS, v)) for v in out]


def _f_boosting(xtr, ytr, xte, **kw):                                 # type: ignore[no-untyped-def]
    """Shrunken stumps on the logit scale -- the smallest honest gradient booster."""
    rounds, eta = int(kw.get("n_rounds", 24)), float(kw.get("shrinkage", 0.18))
    n, p = len(ytr), len(xtr[0])
    p0 = sum(ytr) / n
    p0 = min(1 - EPS, max(EPS, p0))
    f_tr = [math.log(p0 / (1 - p0))] * n
    f_te = [math.log(p0 / (1 - p0))] * len(xte)
    for _ in range(rounds):
        resid = [ytr[i] - 1.0 / (1.0 + math.exp(-max(-50.0, min(50.0, f_tr[i]))))
                 for i in range(n)]
        best: tuple[float, int, float, float, float] | None = None
        for j in range(p):
            vals = sorted({r[j] for r in xtr})
            if len(vals) < 3:
                continue
            thr = vals[len(vals) // 2]
            lo = [resid[i] for i in range(n) if xtr[i][j] <= thr]
            hi = [resid[i] for i in range(n) if xtr[i][j] > thr]
            if len(lo) < 4 or len(hi) < 4:
                continue
            ml, mh = sum(lo) / len(lo), sum(hi) / len(hi)
            score = len(lo) * ml * ml + len(hi) * mh * mh
            if best is None or score > best[0]:
                best = (score, j, float(thr), ml, mh)
        if best is None:
            break
        _, j, thr, ml, mh = best
        for i in range(n):
            f_tr[i] += eta * (mh if xtr[i][j] > thr else ml) * 4.0
        for i, r in enumerate(xte):
            f_te[i] += eta * (mh if r[j] > thr else ml) * 4.0
    return [_squash(v, 1.0) for v in f_te]


def _f_neural(xtr, ytr, xte, **kw):                                   # type: ignore[no-untyped-def]
    """One tanh hidden layer, plain gradient descent, deterministic init."""
    h, epochs, lr = int(kw.get("hidden", 4)), int(kw.get("epochs", 120)), float(kw.get("lr", 0.2))
    n, p = len(ytr), len(xtr[0])
    w1 = [[math.sin(1.7 * (i + 1) * (j + 1)) * 0.4 for j in range(h)] for i in range(p)]
    b1 = [0.0] * h
    w2 = [math.cos(1.3 * (j + 1)) * 0.4 for j in range(h)]
    b2 = 0.0
    l2 = float(kw.get("l2", 1e-3))
    for _ in range(epochs):
        g1 = [[0.0] * h for _ in range(p)]
        gb1 = [0.0] * h
        g2 = [0.0] * h
        gb2 = 0.0
        for i in range(n):
            z = [sum(xtr[i][k] * w1[k][j] for k in range(p)) + b1[j] for j in range(h)]
            a = [math.tanh(v) for v in z]
            o = _squash(sum(a[j] * w2[j] for j in range(h)) + b2, 1.0)
            d = o - ytr[i]
            gb2 += d
            for j in range(h):
                g2[j] += d * a[j]
                dz = d * w2[j] * (1.0 - a[j] * a[j])
                gb1[j] += dz
                for k in range(p):
                    g1[k][j] += dz * xtr[i][k]
        for j in range(h):
            w2[j] -= lr * (g2[j] / n + l2 * w2[j])
            b1[j] -= lr * gb1[j] / n
            for k in range(p):
                w1[k][j] -= lr * (g1[k][j] / n + l2 * w1[k][j])
        b2 -= lr * gb2 / n
    out = []
    for r in xte:
        a = [math.tanh(sum(r[k] * w1[k][j] for k in range(p)) + b1[j]) for j in range(h)]
        out.append(_squash(sum(a[j] * w2[j] for j in range(h)) + b2, 1.0))
    return out


def _f_state_space(xtr, ytr, xte, **kw):                              # type: ignore[no-untyped-def]
    """Local-level Kalman on the linear score: the coefficient drifts, it is not fixed."""
    w = _ridge(xtr, [2.0 * v - 1.0 for v in ytr], 10.0)
    if w is None:
        return None
    q_over_r = float(kw.get("q_over_r", 0.05))
    level, var = 0.0, 1.0
    for i, r in enumerate(xtr):
        s = sum(wi * xi for wi, xi in zip(w, r, strict=True))
        var += q_over_r
        k = var / (var + 1.0)
        level += k * ((2.0 * ytr[i] - 1.0) - s - level)
        var *= (1.0 - k)
    return [_squash(sum(wi * xi for wi, xi in zip(w, r, strict=True)) + level) for r in xte]


def _f_bayesian(xtr, ytr, xte, **kw):                                 # type: ignore[no-untyped-def]
    """Gaussian naive Bayes with a conjugate prior on each class mean."""
    p = len(xtr[0])
    prior = float(kw.get("prior_strength", 1.0))
    stats: dict[int, tuple[list[float], list[float], float]] = {}
    for cls in (0, 1):
        rows = [xtr[i] for i in range(len(ytr)) if int(ytr[i]) == cls]
        if len(rows) < 3:
            return None
        mu = [(sum(r[j] for r in rows)) / (len(rows) + prior) for j in range(p)]
        var = [max(1e-4, sum((r[j] - mu[j]) ** 2 for r in rows) / len(rows)) for j in range(p)]
        stats[cls] = (mu, var, (len(rows) + prior) / (len(ytr) + 2 * prior))
    out = []
    for r in xte:
        lp = {}
        for cls in (0, 1):
            mu, var, pri = stats[cls]
            lp[cls] = math.log(pri) - 0.5 * sum(
                math.log(2 * math.pi * var[j]) + (r[j] - mu[j]) ** 2 / var[j] for j in range(p))
        m = max(lp.values())
        e1, e0 = math.exp(lp[1] - m), math.exp(lp[0] - m)
        out.append(min(1 - EPS, max(EPS, e1 / (e1 + e0))))
    return out


def _f_sequence(xtr, ytr, xte, **kw):                                 # type: ignore[no-untyped-def]
    """The target's own recent path, lagged into the design -- an AR(p) on the label."""
    lags = int(kw.get("lags", 3))
    def _aug(x: list[list[float]], y: list[float] | None) -> list[list[float]]:
        out = []
        for i, r in enumerate(x):
            tail = []
            for L in range(1, lags + 1):
                tail.append(2.0 * y[i - L] - 1.0 if (y is not None and i - L >= 0) else 0.0)
            out.append(list(r) + tail)
        return out
    a_tr = _aug(xtr, ytr)
    w = _ridge(a_tr, [2.0 * v - 1.0 for v in ytr], float(kw.get("alpha", 10.0)))
    if w is None:
        return None
    # The test fold cannot see its own labels: the lags carry the last TRAIN labels, decayed.
    carry = [2.0 * ytr[-L] - 1.0 if L <= len(ytr) else 0.0 for L in range(1, lags + 1)]
    return [_squash(sum(wi * xi for wi, xi in
                        zip(w, list(r) + [c * (0.8 ** t) for t, c in enumerate(carry)],
                            strict=True))) for r in xte]


def _f_graph(xtr, ytr, xte, **kw):                                    # type: ignore[no-untyped-def]
    """Features are nodes; each votes, and a node's weight is its degree in the corr graph."""
    p = len(xtr[0])
    thr = float(kw.get("threshold", 0.3))
    cols = [[r[j] for r in xtr] for j in range(p)]
    def _corr(a: list[float], b: list[float]) -> float:
        n = len(a)
        ma, mb = sum(a) / n, sum(b) / n
        num = sum((a[i] - ma) * (b[i] - mb) for i in range(n))
        da = math.sqrt(sum((v - ma) ** 2 for v in a))
        db = math.sqrt(sum((v - mb) ** 2 for v in b))
        return num / (da * db) if da > 0 and db > 0 else 0.0
    yc = [2.0 * v - 1.0 for v in ytr]
    votes = [_corr(cols[j], yc) for j in range(p)]
    deg = [1 + sum(1 for k in range(p) if k != j and abs(_corr(cols[j], cols[k])) > thr)
           for j in range(p)]
    # A node in a dense cluster is DOWN-weighted: its neighbours already said the same thing.
    w = [votes[j] / deg[j] for j in range(p)]
    return _pred_linear(w, xte, k=6.0)


def _f_moe(xtr, ytr, xte, **kw):                                      # type: ignore[no-untyped-def]
    """Hard gate on one feature's terciles, a ridge expert per bucket."""
    g = int(kw.get("gate_feature", 0)) % max(1, len(xtr[0]))
    vals = sorted(r[g] for r in xtr)
    q1, q2 = vals[len(vals) // 3], vals[2 * len(vals) // 3]
    def _bucket(v: float) -> int:
        return 0 if v <= q1 else (1 if v <= q2 else 2)
    experts: dict[int, list[float] | None] = {}
    for b in (0, 1, 2):
        idx = [i for i in range(len(ytr)) if _bucket(xtr[i][g]) == b]
        if len(idx) < 12:
            experts[b] = None
            continue
        experts[b] = _ridge([xtr[i] for i in idx], [2.0 * ytr[i] - 1.0 for i in idx], 10.0)
    glob = _ridge(xtr, [2.0 * v - 1.0 for v in ytr], 10.0)
    if glob is None:
        return None
    out = []
    for r in xte:
        w = experts[_bucket(r[g])] or glob
        out.append(_squash(sum(wi * xi for wi, xi in zip(w, r, strict=True))))
    return out


_FALLBACKS = {"linear": _f_linear, "sparse": _f_sparse, "tree": _f_tree,
              "boosting": _f_boosting, "neural": _f_neural, "state_space": _f_state_space,
              "bayesian": _f_bayesian, "sequence": _f_sequence, "graph": _f_graph,
              "mixture_of_experts": _f_moe}


def _heavy(name: str, xtr: list[list[float]], ytr: list[float], xte: list[list[float]],
           params: dict[str, Any]) -> list[float] | None:
    """The accelerated path, entirely optional. Any failure returns None and the fallback runs."""
    try:
        if name == "linear":
            from sklearn.linear_model import Ridge
            m = Ridge(alpha=float(params.get("alpha", 10.0))).fit(
                xtr, [2.0 * v - 1.0 for v in ytr])
            return [_squash(float(v)) for v in m.predict(xte)]
        if name == "sparse":
            from sklearn.linear_model import Lasso
            m = Lasso(alpha=float(params.get("l1", 0.02)), max_iter=2000).fit(
                xtr, [2.0 * v - 1.0 for v in ytr])
            return [_squash(float(v)) for v in m.predict(xte)]
        if name == "tree":
            from sklearn.tree import DecisionTreeClassifier
            m = DecisionTreeClassifier(max_depth=int(params.get("depth", 2)),
                                       min_samples_leaf=8, random_state=0).fit(xtr, ytr)
            return [float(v) for v in m.predict_proba(xte)[:, 1]]
        if name == "boosting":
            from sklearn.ensemble import HistGradientBoostingClassifier
            m = HistGradientBoostingClassifier(
                max_depth=3, max_iter=int(params.get("n_rounds", 120)),
                learning_rate=float(params.get("shrinkage", 0.05)), l2_regularization=1.0,
                random_state=0).fit(xtr, ytr)
            return [float(v) for v in m.predict_proba(xte)[:, 1]]
        if name == "neural":
            from sklearn.neural_network import MLPClassifier
            m = MLPClassifier(hidden_layer_sizes=(int(params.get("hidden", 16)), 8),
                              alpha=1e-2, max_iter=300, random_state=0).fit(xtr, ytr)
            return [float(v) for v in m.predict_proba(xte)[:, 1]]
        if name == "bayesian":
            from sklearn.naive_bayes import GaussianNB
            m = GaussianNB().fit(xtr, ytr)
            return [float(v) for v in m.predict_proba(xte)[:, 1]]
    except Exception:
        return None
    return None


def fit_predict(name: str, xtr: list[list[float]], ytr: list[float], xte: list[list[float]],
                *, params: dict[str, Any] | None = None, allow_heavy: bool = True
                ) -> tuple[list[float] | None, str]:
    """(probabilities, backend). The fallback ALWAYS runs when the heavy path is absent."""
    if name not in FAMILIES:
        raise KeyError(name)
    p = dict(params or {})
    if allow_heavy:
        out = _heavy(name, xtr, ytr, xte, p)
        if out is not None:
            return [min(1 - EPS, max(EPS, float(v))) for v in out], "heavy"
    got = _FALLBACKS[name](xtr, ytr, xte, **p)
    if got is None:
        return None, "fallback"
    return [min(1 - EPS, max(EPS, float(v))) for v in got], "fallback"


# --------------------------------------------------------------- scoring
def log_score(p: Sequence[float], y: Sequence[float]) -> float:
    n = len(y)
    if n == 0:
        return 0.0
    tot = 0.0
    for i in range(n):
        q = min(1 - EPS, max(EPS, p[i]))
        tot += y[i] * math.log(q) + (1 - y[i]) * math.log(1 - q)
    return tot / n


def walk_forward(name: str, x: list[list[float]], y: list[float], *, n_folds: int = 4,
                 params: dict[str, Any] | None = None, allow_heavy: bool = True,
                 min_rows: int = MIN_ROWS) -> dict[str, Any]:
    """Expanding-window folds; the zoo's convention so the two are comparable."""
    fam = FAMILIES.get(name)
    if fam is None:
        raise KeyError(name)
    n = len(y)
    avail = availability()[name]
    base_row = {"family": name, "n": n, "tax": fam.tax, "parent": fam.parent,
                "heavy_verdict": avail["heavy_verdict"], "backends_present":
                avail["backends_present"]}
    if n < min_rows:
        return {**base_row, "verdict": UNMEASURED, "backend": "none",
                "why": f"need {min_rows} rows, have {n}"}
    edges = [int(n // 3 + (n - n // 3) * i / n_folds) for i in range(n_folds + 1)]
    scores, bases, briers, backends = [], [], [], set()
    for i in range(n_folds):
        a, b = edges[i], edges[i + 1]
        if b - a < 10 or a < min_rows // 3:
            continue
        xtr, xte = _standardise(x[:a], x[a:b])
        ytr, yte = y[:a], y[a:b]
        if len(set(ytr)) < 2:
            continue
        probs, backend = fit_predict(name, xtr, ytr, xte, params=params, allow_heavy=allow_heavy)
        if probs is None:
            continue
        backends.add(backend)
        p0 = sum(ytr) / len(ytr)
        scores.append(log_score(probs, yte))
        bases.append(log_score([p0] * len(yte), yte))
        briers.append(sum((probs[k] - yte[k]) ** 2 for k in range(len(yte))) / len(yte))
    if not scores:
        return {**base_row, "verdict": UNMEASURED, "backend": "none",
                "why": "no scorable fold (constant labels or every fit refused)"}
    gain = sum(scores) / len(scores) - sum(bases) / len(bases)
    net = gain - fam.tax
    return {**base_row, "folds": len(scores),
            "log_score": round(sum(scores) / len(scores), 6),
            "baseline": round(sum(bases) / len(bases), 6),
            "gain": round(gain, 6), "net_gain": round(net, 6),
            "brier": round(sum(briers) / len(briers), 6),
            "backend": "heavy" if "heavy" in backends else "fallback",
            "verdict": POSITIVE if net > 0 else NEGATIVE}


def compete(x: list[list[float]], y: list[float], *, families: Sequence[str] = ORDER,
            n_folds: int = 4, allow_heavy: bool = True, min_rows: int = MIN_ROWS
            ) -> dict[str, Any]:
    """Every family on the same folds. The winner is the best NET gain, and only if positive."""
    res = {f: walk_forward(f, x, y, n_folds=n_folds, allow_heavy=allow_heavy,
                           min_rows=min_rows) for f in families}
    scored = {f: r for f, r in res.items() if r.get("net_gain") is not None}
    win = max(scored, key=lambda f: float(scored[f]["net_gain"])) if scored else None
    return {"results": res,
            "winner": win if win and float(scored[win]["net_gain"]) > 0 else None,
            "n_unmeasured": sum(1 for r in res.values() if r.get("verdict") == UNMEASURED),
            "rule": "winner = argmax (OOS log score - baseline - declared tax), only if > 0"}

```

### libs\validation\hostile.py
```python
"""HOSTILE VALIDATION -- eight adversaries that re-run the STRATEGY, not its return series.

WHAT THE GAUNTLET ALREADY OWNS, AND WHY IT IS NOT THIS. Every adversary the desk has judges a
candidate from its RETURNS: `redteam` re-places the signals it was handed, `falsifiers` regresses,
splits and stresses the trade series, `bar_permutation` scrambles the tape and re-scores a
statistic, `pbo`/`reality_check`/`dsr` price the search that found it. All of them take the
strategy's OUTPUT as given, so none can ask the question that killed the desk's largest ever
backtest number: would the same CODE, re-run on bars it did not choose, still say this?

THE CASE THAT PAID FOR THIS MODULE. An FVG cell scored t = +9.0 and nothing in the battery
objected -- the trades were real, the costs were charged, both halves carried it, the placebos
lost. The result came from a same-bar limit-fill ambiguity: the replay assumed a fill at a level
the signal bar merely TOUCHED, so every entry booked the distance from the touch to the close for
free. Fixing that one line took the cell to t = -6.0. Fifteen t-units and a sign, invisible to
every test that reads the R series, because the R series was faithfully reporting a fill nobody
could have got. `delayed_entry` is the instrument that catches it.

THE INTERFACE IS THE WHOLE DESIGN. `evaluate(bars) -> TradeStats` is the caller's own replay,
injected, so this module never re-implements a family, a cost model or an engine (the rule
`redteam.run` follows with `score`). Each test is a pure function of that callable and a frame and
returns one `Verdict`; `passed=None` is UNMEASURED, because absence never resolves to a clean
verdict (L1.28a). One report, and it is a gauntlet stage that knows nothing about the gauntlet.

THE EIGHT, AND THE ARTEFACT EACH ONE CATCHES:

    timestamp_permutation  day ordering destroyed, clock kept -- an edge that is the asset's own
                           marginal distribution wearing a schedule. BLOCKS.
    regime_permutation     labels shuffled across blocks -- a conditioner that is a second free
                           parameter rather than a state.
    nearby_instrument_placebo  the same code where the mechanism says it must NOT pay -- a
                           mechanism story fitted after the fact.
    delayed_entry          decision tape real, execution tape k bars on -- the fill artefact
                           above. BLOCKS at k=1: an edge that cannot survive one bar of lateness
                           was never an edge, it was a fill assumption.
    subperiod_removal      each contiguous fifth dropped in turn -- one episode with a calendar
                           around it. BLOCKS on a sign flip only.
    worst_year_removal     the year contributing the most R removed, i.e. the one it would be
                           worst to lose -- a single-year windfall. BLOCKS.
    transfer_test          another instrument the mechanism PREDICTS carries it -- a fit with a
                           story transfers nowhere.
    data_source_substitution  the same instrument from a second SOURCE -- an edge living inside
                           one vendor's bar construction, which is not a market fact.

`dual_engine` is the ninth and sits outside the roster because it needs a second implementation
only the caller can supply: two independent replays of ONE strategy on ONE frame must agree on
how many trades there were and what each was worth, or the certificate rests on a coin flip.

SEVERITY. Four tests BLOCK, because a measured failure there means the number is not a
measurement of the market. The rest are REPORTED: a placebo that also pays is a defect report for
a human (`redteam`'s standing rule), not an automatic withdrawal. This module withdraws nothing,
sizes nothing and promotes nothing -- `blocking` is the one bit a stage can act on, and a failing
test makes an edge UNPROVEN, which is a reason to keep testing it and never a reason to run a
smaller book somewhere else (GROWTH GOVERNANCE Rule 1).
"""
from __future__ import annotations

import math
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd

__all__ = ["BLOCKING_TESTS", "HostileReport", "TradeStats", "Verdict",
           "data_source_substitution", "delayed_entry", "dual_engine",
           "nearby_instrument_placebo", "regime_permutation", "run_all", "stats_from_r",
           "subperiod_removal", "timestamp_permutation", "transfer_test", "worst_year_removal"]

#: A t needs a spread and a spread needs three points: below this it is not small, it is
#: UNDEFINED, which is a different verdict (L1.28a). MIN_BARS refuses a frame too short to cut
#: into fifths or to have blocks to permute.
MIN_TRADES = 3
MIN_BARS = 60

#: One trading day of H1 bars. Blocks preserve within-day serial structure and destroy the
#: ordering ACROSS days, and -- because every block is placed at the same phase -- each bar keeps
#: its hour of day, so a session-conditioned rule still fires at its own hours in the null and
#: only the day it meets there is somebody else's. Below MIN_NULL_DRAWS usable draws a 95th
#: percentile is the maximum of a handful of numbers; dropping unusable draws and shrinking the
#: denominator with them is `bar_permutation`'s rule.
PERMUTATIONS = 20
PERM_BLOCK = 24
PERM_QUANTILE = 0.95
MIN_NULL_DRAWS = 5

PLACEBO_T_RATIO = 0.5
DELAYS: tuple[int, ...] = (1, 5, 15)
DELAY_RETENTION = 0.50
SUBPERIODS = 5
SUBPERIOD_MIN_T = 1.0
WORST_YEAR_MIN_T = 1.5
TRANSFER_MIN_T = 1.0
SOURCE_EXPECTANCY_TOL = 0.30
DUAL_COUNT_TOL = 0.10
DUAL_EXPECTANCY_TOL = 0.25

BLOCK = "block"
REPORT = "report"

#: The tests whose MEASURED failure means the number is not a measurement of the market.
#: `subperiod_removal` is in the roster but downgrades itself to ``report`` when its failure is one
#: of magnitude rather than a sign flip -- a thin fifth is weakness, a flipped fifth is a different
#: strategy. `_EXECUTION_COLS` is what a fill meets; `close` is deliberately absent, because it is
#: what the rule DECIDED on and moving it would move the signal instead of the fill.
BLOCKING_TESTS = frozenset({"timestamp_permutation", "delayed_entry", "subperiod_removal",
                            "worst_year_removal"})
_OHLC = ("open", "high", "low", "close")
_EXECUTION_COLS = ("open", "high", "low")


@dataclass(frozen=True)
class TradeStats:
    """What one replay of a strategy produced. The caller's own numbers, never recomputed here."""

    n: int
    mean_r: float
    t_stat: float
    expectancy: float
    per_trade_r: list[float] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {"n": int(self.n), "mean_r": _num(self.mean_r), "t_stat": _num(self.t_stat),
                "expectancy": _num(self.expectancy)}


def stats_from_r(rs: Sequence[float]) -> TradeStats:
    """Per-trade R multiples -> `TradeStats`. The one constructor, so every test agrees on `t`.

    Non-finite R values are dropped and `n` is what survived: a NaN trade is not a zero trade.
    ``t_stat`` IS NaN BELOW THREE TRADES, a deliberate divergence from ``falsifiers._t``, which
    returns 0.0. There 0.0 reads as "no edge" on the real series; here the same number joins a
    NULL DISTRIBUTION, where a fabricated 0.0 for every permutation that happened to trade nothing
    drags the null down -- significance manufactured out of the permutations that failed.
    """
    arr = np.asarray(list(rs), dtype=float)
    arr = arr[np.isfinite(arr)]
    n = int(arr.size)
    if n == 0:
        return TradeStats(n=0, mean_r=float("nan"), t_stat=float("nan"),
                          expectancy=float("nan"), per_trade_r=[])
    mean = float(arr.mean())
    if n < MIN_TRADES:
        t = float("nan")
    else:
        sd = float(arr.std(ddof=1))
        t = float(mean / (sd / math.sqrt(n))) if sd > 0.0 else 0.0
    return TradeStats(n=n, mean_r=mean, t_stat=t, expectancy=mean,
                      per_trade_r=[float(x) for x in arr])


#: The caller's replay: any bars frame in, that frame's trade statistics out.
Evaluate = Callable[[pd.DataFrame], TradeStats]


@dataclass(frozen=True)
class Verdict:
    """One adversary's finding. ``passed is None`` is UNMEASURED and is never folded into False."""

    name: str
    passed: bool | None
    statistic: float | None
    threshold: float | None
    why: str
    basis: dict[str, Any] = field(default_factory=dict)
    severity: str = REPORT

    @property
    def measured(self) -> bool:
        return self.passed is not None

    @property
    def blocks(self) -> bool:
        """A MEASURED failure on a blocking test. An unmeasured test blocks nothing."""
        return self.passed is False and self.severity == BLOCK

    def to_dict(self) -> dict[str, Any]:
        return {"name": self.name, "passed": self.passed, "statistic": _num(self.statistic),
                "threshold": _num(self.threshold), "severity": self.severity,
                "status": ("UNMEASURED" if self.passed is None else
                           ("PASS" if self.passed else "FAIL")),
                "why": self.why, "basis": self.basis}


@dataclass(frozen=True)
class HostileReport:
    """The roster's finding. `blocking` is the only bit a gauntlet stage needs to read."""

    verdicts: tuple[Verdict, ...]
    seed: int = 0
    real: TradeStats | None = None

    @property
    def n_passed(self) -> int:
        return sum(1 for v in self.verdicts if v.passed is True)

    @property
    def n_failed(self) -> int:
        return sum(1 for v in self.verdicts if v.passed is False)

    @property
    def n_unmeasured(self) -> int:
        return sum(1 for v in self.verdicts if v.passed is None)

    @property
    def blocking(self) -> bool:
        return any(v.blocks for v in self.verdicts)

    @property
    def blocked_by(self) -> list[str]:
        return [v.name for v in self.verdicts if v.blocks]

    def by_name(self, name: str) -> Verdict | None:
        for v in self.verdicts:
            if v.name == name:
                return v
        return None

    def to_dict(self) -> dict[str, Any]:
        return {"seed": int(self.seed), "n_tests": len(self.verdicts),
                "real": self.real.to_dict() if self.real is not None else None,
                "n_passed": self.n_passed, "n_failed": self.n_failed,
                "n_unmeasured": self.n_unmeasured, "blocking": self.blocking,
                "blocked_by": self.blocked_by,
                "verdicts": [v.to_dict() for v in self.verdicts],
                "why": (f"{self.n_passed} passed, {self.n_failed} failed, "
                        f"{self.n_unmeasured} unmeasured"
                        + (f"; BLOCKED BY {', '.join(self.blocked_by)}"
                           if self.blocking else ""))}


# --------------------------------------------------------------------------------------------
# helpers


def _num(x: float | None) -> float | None:
    """JSON-safe; NaN/inf become None rather than a number no reader can compare."""
    if x is None:
        return None
    f = float(x)
    return round(f, 8) if math.isfinite(f) else None


def _unmeasured(name: str, why: str, severity: str = REPORT,
                basis: dict[str, Any] | None = None) -> Verdict:
    return Verdict(name=name, passed=None, statistic=None, threshold=None, why=why,
                   basis=basis or {}, severity=severity)


def _safe(evaluate: Evaluate, frame: pd.DataFrame | None) -> TradeStats | None:
    """Re-run the caller's replay, returning None rather than raising into the roster.

    A replay that blows up on a permuted frame is a datum, not a crash: the callers COUNT the
    failures into their basis (`knob_sensitivity`'s rule -- record, never swallow).
    """
    if frame is None or len(frame) < MIN_BARS:
        return None
    try:
        out = evaluate(frame)
    except Exception:
        return None
    return out if isinstance(out, TradeStats) else None


def _has_ohlc(bars: pd.DataFrame | None) -> bool:
    return bars is not None and all(c in bars.columns for c in _OHLC)


def _usable(st: TradeStats | None) -> bool:
    return st is not None and st.n >= MIN_TRADES and math.isfinite(st.t_stat)


def _rel_gap(a: float, b: float) -> float:
    """|a-b| relative to the FIRST argument, which is always the reference measurement."""
    if not (math.isfinite(a) and math.isfinite(b)) or a == 0.0:
        return float("nan")
    return abs(b - a) / abs(a)


def _block_order(m: int, block: int, rng: np.random.Generator) -> np.ndarray | None:
    """A permutation of 0..m-1 that moves whole blocks and leaves the ragged tail in place."""
    b = max(1, int(block))
    nb = m // b
    if nb < 2:
        return None
    idx = np.arange(m)
    head = nb * b
    perm = rng.permutation(nb)
    body = idx[:head].reshape(nb, b)[perm].reshape(-1)
    return np.concatenate([body, idx[head:]])


def _block_permute(bars: pd.DataFrame, *, block: int,
                   rng: np.random.Generator) -> pd.DataFrame | None:
    """Rebuild the frame from a BLOCK permutation of its log-return decomposition.

    The decomposition is `bar_permutation`'s, including its correction: each bar's gap travels
    with its own intra-bar triple under ONE index permutation, so close-to-close log returns are an
    exact reordering of the real ones -- every moment preserved, order destroyed. Splitting them
    inflates the null's variance and hands a zero-skill rule a p-value. Two deliberate departures:
    BLOCKS rather than single bars, because a bar-wise shuffle also destroys the short-horizon
    autocorrelation a mean-reversion rule legitimately eats; and a closed-form reassembly of that
    module's sequential loop (`close = c0 + cumsum(gap + dclose)`), because this null is rebuilt
    twenty times per candidate inside a stage rather than once in a study.
    """
    if not _has_ohlc(bars) or len(bars) < MIN_BARS:
        return None
    o, h, lo, c = (bars[k].to_numpy(dtype=float) for k in _OHLC)
    if not all(np.all(np.isfinite(a)) and np.all(a > 0.0) for a in (o, h, lo, c)):
        return None
    ln_o, ln_h, ln_l, ln_c = (np.log(a) for a in (o, h, lo, c))
    gap = ln_o[1:] - ln_c[:-1]
    d_h, d_l, d_c = ln_h[1:] - ln_o[1:], ln_l[1:] - ln_o[1:], ln_c[1:] - ln_o[1:]
    order = _block_order(gap.size, block, rng)
    if order is None:
        return None
    g, dh, dl, dc = gap[order], d_h[order], d_l[order], d_c[order]
    close = np.concatenate([ln_c[:1], ln_c[0] + np.cumsum(g + dc)])
    open_ = np.concatenate([ln_o[:1], close[:-1] + g])
    high = np.concatenate([ln_h[:1], open_[1:] + dh])
    low = np.concatenate([ln_l[:1], open_[1:] + dl])
    out = bars.copy()
    for name, arr in zip(_OHLC, (open_, high, low, close), strict=True):
        out[name] = np.exp(arr)
    if "volume" in out.columns:
        vol = bars["volume"].to_numpy()
        out["volume"] = np.concatenate([vol[:1], vol[1:][order]])
    return out


def _delay_entry_frame(bars: pd.DataFrame, k: int) -> pd.DataFrame | None:
    """The decision tape real, the EXECUTION tape moved `k` bars on.

    A WHOLE-FRAME SHIFT WOULD BE DECORATIVE, which is why the frame is split. Any shift of every
    column is a relabelling and a rule that is a function of the path alone is invariant under one
    -- the test would buy nothing against exactly the class it exists to prosecute
    (`knob_sensitivity`). So `close` and volume stay where they are, because that is what the rule
    looked at, while `open`, `high` and `low` at row t become the real ones from row t+k, because
    that is the market the trade met after arriving k bars late. The trade enters later and exits
    on its original clock, holding k bars fewer: an edge spread over its horizon loses roughly
    k/hold, an edge that was a same-bar fill assumption loses all of it at k=1 (the FVG case). The
    blended bar is REPAIRED (`high >= max(open, close) >= min(open, close) >= low`) so nobody is
    handed a bar no venue could print -- basis points at k=1 on an hourly chart, wider at k=15.

    THE LONG DELAYS ARE A CURVE, NOT A VERDICT, which is why only k=1 blocks. Once k exceeds the
    holding period the entry sits AFTER the exit and a rule comparing a decision price with a fill
    price is re-selecting on a move it already knows: on the desk's own synthetic artefact
    retention at k=15 came back at 2.46, which means the construction has left the question behind.
    """
    if k <= 0 or not _has_ohlc(bars) or len(bars) - k < MIN_BARS:
        return None
    out = bars.iloc[:-k].copy()
    for name in _EXECUTION_COLS:
        out[name] = bars[name].to_numpy(dtype=float)[k:]
    o = out["open"].to_numpy(dtype=float)
    c = out["close"].to_numpy(dtype=float)
    out["high"] = np.maximum(out["high"].to_numpy(dtype=float), np.maximum(o, c))
    out["low"] = np.minimum(out["low"].to_numpy(dtype=float), np.minimum(o, c))
    return out


def _drop_slice(bars: pd.DataFrame, lo: int, hi: int) -> pd.DataFrame | None:
    """The frame without rows [lo, hi). The seam is real and is named in the verdict's basis."""
    parts = [p for p in (bars.iloc[:lo], bars.iloc[hi:]) if len(p) > 0]
    if not parts:
        return None
    return parts[0] if len(parts) == 1 else pd.concat(parts)


def _null_verdict(name: str, real: TradeStats, null: list[float], failed: int, *,
                  severity: str, what: str) -> Verdict:
    """Real t against the 95th percentile of a null of t's. Shared by the two permutation tests."""
    if len(null) < MIN_NULL_DRAWS:
        return _unmeasured(name, f"only {len(null)} usable null draw(s) of {len(null) + failed}; "
                                 f"{MIN_NULL_DRAWS} are needed before a {PERM_QUANTILE:.0%} "
                                 "quantile means anything", severity,
                           {"n_null": len(null), "n_null_failed": failed})
    arr = np.asarray(null, dtype=float)
    q = float(np.quantile(arr, PERM_QUANTILE))
    p = float((np.sum(arr >= real.t_stat) + 1) / (arr.size + 1))
    passed = bool(real.t_stat > q)
    return Verdict(
        name=name, passed=passed, statistic=float(real.t_stat), threshold=q, severity=severity,
        why=(f"real t={real.t_stat:.2f} {'beats' if passed else 'does not beat'} the "
             f"{PERM_QUANTILE:.0%} quantile of {what} (t={q:.2f}, p={p:.3f})"),
        basis={"real_t": _num(real.t_stat), "null_q": _num(q), "p_value": _num(p),
               "null_mean_t": _num(float(arr.mean())), "null_max_t": _num(float(arr.max())),
               "n_null": int(arr.size), "n_null_failed": int(failed), "n_trades": int(real.n)},
    )


# --------------------------------------------------------------------------------------------
# the eight


def timestamp_permutation(evaluate: Evaluate, bars: pd.DataFrame, *,
                          n_permutations: int = PERMUTATIONS, block: int = PERM_BLOCK,
                          seed: int = 0, real: TradeStats | None = None) -> Verdict:
    """(1) Is there information in the SEQUENCE, or only in the distribution it came from?"""
    name = "timestamp_permutation"
    real = real if real is not None else _safe(evaluate, bars)
    if not _usable(real) or real is None:
        return _unmeasured(name, "the strategy produced no measurable t on the real bars", BLOCK)
    rng = np.random.default_rng(seed)
    null: list[float] = []
    failed = 0
    for _ in range(max(0, int(n_permutations))):
        st = _safe(evaluate, _block_permute(bars, block=block, rng=rng))
        if st is None or not math.isfinite(st.t_stat):
            failed += 1
            continue
        null.append(float(st.t_stat))
    return _null_verdict(name, real, null, failed, severity=BLOCK,
                         what=f"the block-permuted tape (blocks of {block})")


def regime_permutation(evaluate: Evaluate, bars: pd.DataFrame, *,
                       regime: pd.Series | None = None, n_permutations: int = PERMUTATIONS,
                       block: int = PERM_BLOCK, seed: int = 0) -> Verdict:
    """(2) Is the conditioner a STATE, or a second free parameter with a state's name on it?

    The frame carries a `regime` column; the null shuffles that column in blocks and leaves the
    prices alone, so tape, clock and rule are unchanged and only the labelling moves. An edge that
    survives relabelled regimes was never conditioned on anything.
    """
    name = "regime_permutation"
    if regime is None:
        return _unmeasured(name, "no regime series supplied")
    reg = pd.Series(regime).reindex(bars.index)
    if int(reg.notna().sum()) * 2 < len(bars):
        return _unmeasured(name, "the regime series covers under half the bars once aligned",
                           basis={"n_labelled": int(reg.notna().sum()), "n_bars": len(bars)})
    framed = bars.copy()
    framed["regime"] = reg
    real = _safe(evaluate, framed)
    if not _usable(real) or real is None:
        return _unmeasured(name, "the strategy produced no measurable t with real regime labels")
    rng = np.random.default_rng(seed)
    values = reg.to_numpy()
    null: list[float] = []
    failed = 0
    for _ in range(max(0, int(n_permutations))):
        order = _block_order(values.size, block, rng)
        if order is None:
            failed += 1
            continue
        shuffled = framed.copy()
        shuffled["regime"] = values[order]
        st = _safe(evaluate, shuffled)
        if st is None or not math.isfinite(st.t_stat):
            failed += 1
            continue
        null.append(float(st.t_stat))
    return _null_verdict(name, real, null, failed, severity=REPORT,
                         what=f"block-shuffled regime labels (blocks of {block})")


def nearby_instrument_placebo(evaluate: Evaluate, bars: pd.DataFrame, *,
                              bars_neighbour: pd.DataFrame | None = None,
                              real: TradeStats | None = None) -> Verdict:
    """(3) The same code on a correlated instrument the mechanism says must NOT carry it.

    ABSOLUTE t ON THE PLACEBO, which is the point rather than a convenience: a neighbour scoring
    t = -6 has not failed to carry the mechanism, it is carrying something just as strong and
    mirrored, which is what a shared construction artefact looks like. `same_sign` is reported so
    a caller whose mechanism predicts the neighbour SHOULD carry it reads the other direction;
    this verdict grades the default prediction, that it should not.
    """
    name = "nearby_instrument_placebo"
    if bars_neighbour is None:
        return _unmeasured(name, "no neighbour instrument supplied")
    real = real if real is not None else _safe(evaluate, bars)
    if not _usable(real) or real is None or real.t_stat == 0.0:
        return _unmeasured(name, "the strategy produced no measurable t on the real bars")
    placebo = _safe(evaluate, bars_neighbour)
    if placebo is None or not math.isfinite(placebo.t_stat):
        return _unmeasured(name, "the strategy produced no measurable t on the neighbour",
                           basis={"n_placebo": 0 if placebo is None else int(placebo.n)})
    ratio = abs(placebo.t_stat) / abs(real.t_stat)
    passed = bool(ratio < PLACEBO_T_RATIO)
    return Verdict(
        name=name, passed=passed, statistic=float(ratio), threshold=PLACEBO_T_RATIO,
        why=(f"placebo |t|={abs(placebo.t_stat):.2f} is {ratio:.2f}x the real |t|="
             f"{abs(real.t_stat):.2f}; the neighbour "
             f"{'does not carry' if passed else 'ALSO carries'} the result"),
        basis={"real_t": _num(real.t_stat), "placebo_t": _num(placebo.t_stat),
               "placebo_n": int(placebo.n), "real_n": int(real.n),
               "same_sign": bool(np.sign(placebo.mean_r) == np.sign(real.mean_r))},
    )


def delayed_entry(evaluate: Evaluate, bars: pd.DataFrame, *, delays: Sequence[int] = DELAYS,
                  real: TradeStats | None = None) -> Verdict:
    """(4) Arrive k bars late at the same decision. The fill-artefact prosecutor.

    The verdict is the 1-BAR reading; 5 and 15 are the decay curve, reported because the SHAPE
    says what kind of edge it is (a slow decay is a real effect with a horizon, a cliff at 1 is an
    execution assumption). Retention is measured on expectancy, not on t, because t also moves
    with the trade count and a late arrival legitimately loses trades at the tape's edge.
    """
    name = "delayed_entry"
    real = real if real is not None else _safe(evaluate, bars)
    if real is None or real.n < MIN_TRADES or not math.isfinite(real.expectancy):
        return _unmeasured(name, "the strategy produced no measurable expectancy on real bars",
                           BLOCK)
    if real.expectancy <= 0.0:
        return _unmeasured(name, "real expectancy is not positive; there is nothing to retain",
                           BLOCK, {"real_expectancy": _num(real.expectancy)})
    # ZERO TRADES IS A MEASUREMENT, AND THE LOUDEST ONE THIS TEST MAKES: a rule whose entries all
    # vanish when the fill moves one bar was selecting on the fill price itself, so retention is 0
    # rather than unknown. UNMEASURED is kept for the frame that could not be built or the replay
    # that raised -- letting the worst case out through the gap reserved for missing inputs would
    # invert the test. A st.n of 0 is the first case, st is None the second.
    curve: dict[str, Any] = {}
    for k in delays:
        st = _safe(evaluate, _delay_entry_frame(bars, int(k)))
        if st is None:
            curve[str(int(k))] = {"measured": False}
        elif st.n == 0:
            curve[str(int(k))] = {"measured": True, "n": 0, "expectancy": None, "t_stat": None,
                                  "retention": 0.0}
        else:
            curve[str(int(k))] = {"measured": True, "n": int(st.n),
                                  "expectancy": _num(st.expectancy), "t_stat": _num(st.t_stat),
                                  "retention": _num(st.expectancy / real.expectancy)}
    first = str(int(delays[0])) if delays else ""
    head = curve.get(first) or {}
    if not head.get("measured") or head.get("retention") is None:
        return _unmeasured(name, f"the {first}-bar delayed frame could not be evaluated", BLOCK,
                           {"curve": curve})
    retention = float(head["retention"])
    passed = bool(retention >= DELAY_RETENTION)
    return Verdict(
        name=name, passed=passed, statistic=retention, threshold=DELAY_RETENTION, severity=BLOCK,
        why=(f"a {first}-bar delay retains {retention:.0%} of expectancy "
             f"(floor {DELAY_RETENTION:.0%}); "
             + ("the edge survives arriving late" if passed else
                "an edge that dies with one bar of delay is a fill artefact, not a market fact")),
        basis={"curve": curve, "real_expectancy": _num(real.expectancy), "real_n": int(real.n),
               "construction": ("close/volume real, open/high/low taken k bars later, bar "
                                "repaired to stay quotable")},
    )


def subperiod_removal(evaluate: Evaluate, bars: pd.DataFrame, *, n_parts: int = SUBPERIODS,
                      real: TradeStats | None = None) -> Verdict:
    """(5) Drop each contiguous fifth in turn. Catches one episode wearing a calendar.

    A SIGN FLIP AND A THIN FIFTH ARE NOT THE SAME FINDING: a fold whose t falls to 0.8 is an edge
    that needed that stretch, a fold whose MEAN flips sign is a different strategy that happened
    to average out. Only the second blocks, and the verdict's severity says which happened.
    """
    name = "subperiod_removal"
    real = real if real is not None else _safe(evaluate, bars)
    if not _usable(real) or real is None:
        return _unmeasured(name, "the strategy produced no measurable t on the real bars")
    parts = max(2, int(n_parts))
    n = len(bars)
    if n < parts * MIN_BARS:
        return _unmeasured(name, f"{n} bars cannot be cut into {parts} removable parts")
    edges = [round(i * n / parts) for i in range(parts + 1)]
    folds: list[dict[str, Any]] = []
    ts: list[float] = []
    flipped: list[int] = []
    real_sign = float(np.sign(real.mean_r))
    for i in range(parts):
        st = _safe(evaluate, _drop_slice(bars, edges[i], edges[i + 1]))
        row: dict[str, Any] = {"removed": [edges[i], edges[i + 1]], "measured": _usable(st)}
        if st is not None and row["measured"]:
            row.update({"n": int(st.n), "t_stat": _num(st.t_stat), "mean_r": _num(st.mean_r)})
            ts.append(float(st.t_stat))
            if float(np.sign(st.mean_r)) != real_sign:
                flipped.append(i)
        folds.append(row)
    if len(ts) < MIN_TRADES:
        return _unmeasured(name, f"only {len(ts)} of {parts} folds produced a measurable t",
                           basis={"folds": folds})
    min_t = float(min(ts))
    sign_flip = bool(flipped)
    passed = bool(min_t > SUBPERIOD_MIN_T and not sign_flip)
    return Verdict(
        name=name, passed=passed, statistic=min_t, threshold=SUBPERIOD_MIN_T,
        severity=BLOCK if sign_flip else REPORT,
        why=(f"worst of {len(ts)} fifth-removals t={min_t:.2f} (floor {SUBPERIOD_MIN_T})"
             + (f"; SIGN FLIPPED on fold(s) {flipped}" if sign_flip else "; sign held")),
        basis={"folds": folds, "min_t": _num(min_t), "n_measured_folds": len(ts),
               "sign_flipped_folds": flipped, "real_t": _num(real.t_stat)},
    )


def worst_year_removal(evaluate: Evaluate, bars: pd.DataFrame, *,
                       real: TradeStats | None = None) -> Verdict:
    """(6) Remove the year it would be worst to lose -- the one contributing the most R.

    THE BEST YEAR IS THE WORST ONE TO OWN, hence the name. The year is found by REMOVAL rather
    than by slicing: each calendar year is dropped in turn and the one whose absence costs the
    most total R is the contributor. Scoring a sliced-out year on its own would judge a different
    strategy, one whose warm-up, state and neighbouring context were cut away with it.
    """
    name = "worst_year_removal"
    real = real if real is not None else _safe(evaluate, bars)
    if real is None or real.n < MIN_TRADES or not math.isfinite(real.mean_r):
        return _unmeasured(name, "the strategy produced no measurable R on the real bars", BLOCK)
    try:
        years = pd.DatetimeIndex(bars.index).year.to_numpy()
    except (TypeError, ValueError):
        return _unmeasured(name, "the bars are not indexed by time; calendar years are undefined",
                           BLOCK)
    labels = sorted({int(y) for y in years})
    if len(labels) < 2:
        return _unmeasured(name, f"{len(labels)} calendar year(s) in the index; "
                                 "removing the only year leaves nothing to test", BLOCK,
                           {"years": labels})
    total_r = float(real.n * real.mean_r)
    per_year: dict[str, Any] = {}
    best: tuple[float, int, TradeStats] | None = None
    for y in labels:
        st = _safe(evaluate, bars[years != y])
        if st is None or not _usable(st):
            per_year[str(y)] = {"measured": False}
            continue
        contributed = total_r - float(st.n * st.mean_r)
        per_year[str(y)] = {"measured": True, "n_without": int(st.n),
                            "t_without": _num(st.t_stat), "r_contributed": _num(contributed)}
        if best is None or contributed > best[0]:
            best = (contributed, y, st)
    if best is None:
        return _unmeasured(name, "no year-removal produced a measurable t", BLOCK,
                           {"years": per_year})
    contributed, year, without = best
    passed = bool(without.t_stat > WORST_YEAR_MIN_T)
    return Verdict(
        name=name, passed=passed, statistic=float(without.t_stat), threshold=WORST_YEAR_MIN_T,
        severity=BLOCK,
        why=(f"{year} contributed {contributed:.2f}R of {total_r:.2f}R; without it "
             f"t={without.t_stat:.2f} (floor {WORST_YEAR_MIN_T})"),
        basis={"best_year": int(year), "r_contributed": _num(contributed),
               "total_r": _num(total_r), "t_without_best_year": _num(without.t_stat),
               "n_without": int(without.n), "years": per_year},
    )


def transfer_test(evaluate: Evaluate, bars: pd.DataFrame, *,
                  bars_alt: pd.DataFrame | None = None, alt_is_same_instrument: bool = False,
                  real: TradeStats | None = None) -> Verdict:
    """(7) Another instrument the mechanism PREDICTS carries it. A fit transfers nowhere."""
    name = "transfer_test"
    if bars_alt is None:
        return _unmeasured(name, "no transfer instrument supplied")
    if alt_is_same_instrument:
        return _unmeasured(name, "bars_alt is a second SOURCE of the same instrument; that is "
                                 "data_source_substitution's input, not a transfer")
    real = real if real is not None else _safe(evaluate, bars)
    if not _usable(real) or real is None:
        return _unmeasured(name, "the strategy produced no measurable t on the real bars")
    alt = _safe(evaluate, bars_alt)
    if alt is None or alt.n < MIN_TRADES or not math.isfinite(alt.t_stat):
        return _unmeasured(name, "the strategy produced no measurable t on the transfer "
                                 "instrument", basis={"n_alt": 0 if alt is None else int(alt.n)})
    same_sign = bool(np.sign(alt.mean_r) == np.sign(real.mean_r))
    passed = bool(same_sign and alt.t_stat > TRANSFER_MIN_T)
    return Verdict(
        name=name, passed=passed, statistic=float(alt.t_stat), threshold=TRANSFER_MIN_T,
        why=(f"transfer t={alt.t_stat:.2f} on {alt.n} trades, sign "
             f"{'agrees' if same_sign else 'DISAGREES'} with the real mean"),
        basis={"real_t": _num(real.t_stat), "alt_t": _num(alt.t_stat), "alt_n": int(alt.n),
               "real_mean_r": _num(real.mean_r), "alt_mean_r": _num(alt.mean_r),
               "same_sign": same_sign},
    )


def data_source_substitution(evaluate: Evaluate, bars: pd.DataFrame, *,
                             bars_alt: pd.DataFrame | None = None,
                             alt_is_same_instrument: bool = False,
                             real: TradeStats | None = None) -> Verdict:
    """(8) The same instrument from a second SOURCE. Catches an edge inside a bar construction.

    Two vendors disagree about a bar's high, where the session boundary is and which ticks were
    real. An edge on only one of them is a property of that feed, and the desk cannot trade a feed.
    """
    name = "data_source_substitution"
    if bars_alt is None:
        return _unmeasured(name, "no second data source supplied")
    if not alt_is_same_instrument:
        return _unmeasured(name, "bars_alt is another instrument (alt_is_same_instrument=False); "
                                 "that is transfer_test's input, not a source substitution")
    real = real if real is not None else _safe(evaluate, bars)
    if real is None or real.n < MIN_TRADES or not math.isfinite(real.expectancy):
        return _unmeasured(name, "the strategy produced no measurable expectancy on real bars")
    alt = _safe(evaluate, bars_alt)
    if alt is None or alt.n < MIN_TRADES or not math.isfinite(alt.expectancy):
        return _unmeasured(name, "the strategy produced no measurable expectancy on the second "
                                 "source", basis={"n_alt": 0 if alt is None else int(alt.n)})
    gap = _rel_gap(real.expectancy, alt.expectancy)
    if not math.isfinite(gap):
        return _unmeasured(name, "real expectancy is zero; a relative agreement is undefined")
    passed = bool(gap <= SOURCE_EXPECTANCY_TOL)
    return Verdict(
        name=name, passed=passed, statistic=float(gap), threshold=SOURCE_EXPECTANCY_TOL,
        why=(f"expectancy {real.expectancy:.6f} vs {alt.expectancy:.6f} on the second source, "
             f"a {gap:.0%} gap (tolerance {SOURCE_EXPECTANCY_TOL:.0%})"),
        basis={"real_expectancy": _num(real.expectancy), "alt_expectancy": _num(alt.expectancy),
               "real_n": int(real.n), "alt_n": int(alt.n), "relative_gap": _num(gap)},
    )


def dual_engine(evaluate_a: Evaluate, evaluate_b: Evaluate, bars: pd.DataFrame) -> Verdict:
    """Two independent implementations of ONE strategy on ONE frame must agree.

    Outside `run_all` because it needs a second implementation only the caller can supply -- the
    desk's is `libs.validation.replay2` against `mt5desk.engine.run_backtest`, written from the
    contract rather than from the engine's source, which is the only way the comparison is
    evidence. Trade COUNT first: two engines that disagree about how many trades there were are
    not two opinions about one strategy, they are two strategies.
    """
    name = "dual_engine"
    a, b = _safe(evaluate_a, bars), _safe(evaluate_b, bars)
    if a is None or b is None or min(a.n, b.n) < MIN_TRADES:
        return _unmeasured(name, "one of the two engines produced no measurable trade set",
                           basis={"n_a": None if a is None else int(a.n),
                                  "n_b": None if b is None else int(b.n)})
    count_gap = abs(a.n - b.n) / max(a.n, b.n)
    exp_gap = _rel_gap(a.expectancy, b.expectancy)
    if not math.isfinite(exp_gap):
        return _unmeasured(name, "engine A's expectancy is zero; relative agreement is undefined",
                           basis={"n_a": int(a.n), "n_b": int(b.n)})
    counts_ok = bool(count_gap <= DUAL_COUNT_TOL)
    exp_ok = bool(exp_gap <= DUAL_EXPECTANCY_TOL)
    passed = bool(counts_ok and exp_ok)
    return Verdict(
        name=name, passed=passed, statistic=float(exp_gap), threshold=DUAL_EXPECTANCY_TOL,
        why=(f"trade counts {a.n} vs {b.n} ({count_gap:.0%}, tol {DUAL_COUNT_TOL:.0%}); "
             f"expectancy {a.expectancy:.6f} vs {b.expectancy:.6f} ({exp_gap:.0%}, tol "
             f"{DUAL_EXPECTANCY_TOL:.0%})"),
        basis={"n_a": int(a.n), "n_b": int(b.n), "trade_count_gap": _num(count_gap),
               "trade_count_tolerance": DUAL_COUNT_TOL, "expectancy_a": _num(a.expectancy),
               "expectancy_b": _num(b.expectancy), "expectancy_gap": _num(exp_gap),
               "counts_agree": counts_ok, "expectancy_agrees": exp_ok},
    )


def run_all(evaluate: Evaluate, bars: pd.DataFrame, *, bars_alt: pd.DataFrame | None = None,
            bars_neighbour: pd.DataFrame | None = None, regime: pd.Series | None = None,
            alt_is_same_instrument: bool = False, seed: int = 0) -> HostileReport:
    """The whole roster, in one pass, on one seed. This is the gauntlet stage.

    The real replay runs ONCE and is handed to every test, so a candidate is scored on the number
    the certificate quotes rather than on eight redraws of it. `bars_alt` is read by test 7 OR
    test 8 according to `alt_is_same_instrument`, never both: one frame cannot be another
    instrument and the same instrument, and the wrong reader would report agreement it did not
    measure.
    """
    real = _safe(evaluate, bars)
    verdicts = (
        timestamp_permutation(evaluate, bars, seed=seed, real=real),
        regime_permutation(evaluate, bars, regime=regime, seed=seed),
        nearby_instrument_placebo(evaluate, bars, bars_neighbour=bars_neighbour, real=real),
        delayed_entry(evaluate, bars, real=real),
        subperiod_removal(evaluate, bars, real=real),
        worst_year_removal(evaluate, bars, real=real),
        transfer_test(evaluate, bars, bars_alt=bars_alt,
                      alt_is_same_instrument=alt_is_same_instrument, real=real),
        data_source_substitution(evaluate, bars, bars_alt=bars_alt,
                                 alt_is_same_instrument=alt_is_same_instrument, real=real),
    )
    return HostileReport(verdicts=verdicts, seed=int(seed), real=real)

```

### scripts\acquire_data.py
```python
#!/usr/bin/env python3
"""ADAPTIVE DATA ACQUISITION AGENT (triage #93) -- what to acquire NEXT, ranked on measurement.

WHY #93 SAT UNBUILT. It was blocked on "Information Advantage Score (item 17) existing first",
item 17 shipped 2026-07-29, and the row has been UNBLOCKED and untouched since -- caught
mechanically by check_triage_disposition, not by anyone re-reading it.

WHAT MAKES IT ADAPTIVE, AND WHY THE OBVIOUS BUILD WOULD NOT HAVE BEEN. `research_cio.py`'s
INFORMATION ADVANTAGE SCORE is a hardcoded table: uniqueness, predictive power, persistence and
replication difficulty, all hand-assigned per source class. Ranking acquisitions by that table
produces a confident-looking order built entirely out of somebody's priors, dressed in the
vocabulary of measurement -- the exact failure libs/doctrine/contribution.py refuses, and the
reason a "made-up basis" is rejected at construction there.

So this agent scores on what the desk has actually LEARNED, and the learning enters through one
term: the ontology's own record of attempts and survivors per frontier region.

  * A source that would inform regions the desk has hammered with ZERO survivors is scored DOWN.
    That is evidence, gathered here, that this class of data is barren for this desk -- and it is
    the term that makes the ranking move as the desk works, which a static table cannot do.
  * A source that would REOPEN an under-explored region is scored UP. `ontology.map_dataset`
    already answers "which questions would this dataset help answer", and `ontology.priority`
    already folds in exhaustion with a revival floor -- because a barren region reopened by new
    data is precisely where a desk finds what everyone else gave up on.
  * REPLICATION DIFFICULTY MULTIPLIES, exactly as in EVIG. A source anyone can pull yields edge
    that is already priced; the desk's own measured advantage ranks self-recorded tape at 1.03
    against 0.37 for the next best thing.
  * COST DIVIDES. Free-and-adequate beats paid-and-marginal every time under a log objective.

WHAT IT REFUSES. A candidate whose grade, cost or region mapping cannot be read is scored
UNMEASURED and ranked with an honest penalty -- never given a plausible default. That is WS-005
applied at construction: the least-known source must not become the most attractive one by virtue
of nobody having checked it.

NO ACQUISITION AUTHORITY. This ranks and explains. It spends nothing, signs nothing and starts no
collector; a human or a later organ acts on the ordering. No keys, no order paths.

THE MAP'S FIRST MACHINE WRITER (2026-09-08). `data/data_universe_map.json` holds 190 sources with
real licence and PIT verdicts, and until this date it had NO PRODUCER: grepping for a writer
returned readers only (acquire_data, max_audit, run_cadence, blind_trigger, orphan_scan), so the
six dig seats that would write it are the only path -- and they report `last=never` on missing
credentials. A map nothing can produce is a schedule pointing at a file.

So this registers what the desk's own miners have already PROBED: dataset pages the deep-forest
miner and the world crawler fetched, with the endpoints they found. Three fences, and they are
what make a machine writer safe on a file humans curate:

    REGISTRATION IS NOT A GRADE. Every appended row is `grade: UNVERIFIED` -- the map's own
    vocabulary for "found this session, not opened/confirmed first-party, DO NOT feed a live
    signal" -- and carries the probe result that justifies exactly that much.
    A HUMAN OR LLM GRADE IS NEVER OVERWRITTEN. A source already in the map by url or by name is
    skipped whole: not re-graded, not re-described, not touched. The writer only APPENDS.
    THE MANDATE IS ENFORCED AT THE WRITE. A probe naming a crypto-exchange venue is refused by
    `mechanism_claims.forbidden_venue` before it can reach the map.
"""
from __future__ import annotations

import json
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from libs.hypmax.evig import information_gain  # noqa: E402
from libs.hypmax.ontology import (  # noqa: E402
    SEED_QUESTIONS,
    load_state,
    map_dataset,
    priority,
)

UNIVERSE = ROOT / "data/data_universe_map.json"
ONTOLOGY_STATE = ROOT / "data/ontology_state.json"
MOAT = ROOT / "data/moat_mine.json"
REPORT = ROOT / "data/acquisition_plan.json"
HISTORY = ROOT / "data/acquisition_history.jsonl"
#: Where the miners write what they PROBED. Dataset-kind discovery rows carry the url, the host,
#: the endpoints found and when the desk could first have read them -- a probe result, not a
#: claim about quality.
PROBE_DIR = ROOT / "desks/mt5/data/intelligence/world"
PROBE_GLOB = "discoveries_*.json"
#: The grade every machine-registered row carries, in the map's own vocabulary.
MACHINE_GRADE = "UNVERIFIED"
MACHINE_ORIGIN = "machine:acquire_data (miner probe, never opened by a human)"

#: Source grade -> (P(the data is usable as claimed), why). Grades are the digger's own vocabulary
#: and already carry a verification level, so this maps VERIFICATION to a probability rather than
#: inventing one. A grade nobody assigned falls to the unmeasured floor, never to a middling guess.
GRADE_P: dict[str, tuple[float, str]] = {
    "verified-clean": (0.90, "URL opened and directly confirmed"),
    "needs-monitoring": (0.60, "corroborated but never diffed against ground truth"),
    "reconstructable": (0.50, "methodology is public; the series must be rebuilt, not fetched"),
    "unverified": (0.25, "found, not confirmed -- the desk's own rule says do not adopt"),
    "destroyed-at-source": (0.02, "honest negative: no free path found this session"),
}
#: Applied when a candidate carries no grade at all. Deliberately BELOW the worst real grade: an
#: ungraded source is less known than one somebody looked at and rejected, and ranking it above
#: `unverified` would reward never checking.
UNGRADED_P = 0.01

#: Replication difficulty by access class -- how hard it is for a competitor to hold the same data.
#: Anchored to the desk's OWN measured advantage figures (self-recorded tape 1.03, next-best 0.37)
#: rather than to opinion, and everything public collapses toward the bottom because it must.
REPLICATION: dict[str, tuple[float, str]] = {
    "self-recorded": (1.03, "cannot be bought at any price -- our snapshots, from our clock"),
    "reconstructed": (0.55, "public inputs, private method: replicable only by redoing the work"),
    "gated-free": (0.37, "free but rate-limited or keyed -- a real if modest barrier"),
    "public": (0.10, "pullable in an afternoon by anyone, so any edge found is already priced"),
}

#: Relative cost, in the same units EVIG uses: 1.0 is one routine collector build.
COST: dict[str, float] = {
    "self-recorded": 3.0,      # a recorder, plus disk, plus supervision, forever
    "reconstructed": 2.0,      # rebuild the methodology and diff it
    "gated-free": 1.0,
    "public": 0.5,
}


def _rel(p: Path) -> str:
    """Display path, relative to the repo when it is inside it. `relative_to` RAISES on a path
    outside ROOT, so the unguarded version turned an honest 'the file is missing' report into a
    ValueError the moment the constant was repointed -- an error path that only breaks when it is
    needed is the worst kind."""
    try:
        return str(p.relative_to(ROOT))
    except ValueError:
        return str(p)


def _read(p: Path):
    try:
        if not p.exists() or p.stat().st_size <= 2:
            return None
        return json.loads(p.read_text("utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _grade_p(grade: str) -> tuple[float, str]:
    g = (grade or "").strip().lower()
    for key, (p, why) in GRADE_P.items():
        if key in g:
            return p, why
    return UNGRADED_P, ("NO GRADE RECORDED -- ranked below every graded source, including the "
                        "rejected ones. An unchecked source must never outrank a checked-and-poor "
                        "one, or the ranking rewards not looking")


def _access_class(entry: dict) -> str:
    """Access class from the entry's own fields, never guessed from the name."""
    blob = " ".join(str(entry.get(k, "")) for k in
                    ("access", "class", "kind", "notes", "why", "grade")).lower()
    if "self-record" in blob or "own recorder" in blob:
        return "self-recorded"
    # Prose, not an enum: the digger writes "rebuilt from the public methodology" as readily as
    # "reconstructable". Matching one spelling silently demoted real reconstructions to `public`,
    # which is the most-discounted class -- so the miss was expensive in exactly one direction.
    if any(w in blob for w in ("reconstruct", "rebuil", "re-deriv", "rederiv", "self-comput")):
        return "reconstructed"
    if "key" in blob or "rate-limit" in blob or "gated" in blob or "community" in blob:
        return "gated-free"
    return "public"


def score_candidate(name: str, entry: dict, state: dict) -> dict:
    """One acquisition candidate, scored EVIG-shaped on measured terms.

    score = P(usable) x information_gain(P) x replication_difficulty x region_priority / cost

    Multiplicative for the reason EVIG is: no term rescues a dead one. A perfectly unique source
    informing a region the desk has proved barren is still not worth acquiring, and a rich region
    reachable only through data everyone already has yields edge that is already priced.
    """
    desc = " ".join(str(entry.get(k, "")) for k in ("description", "notes", "why", "metrics"))
    regions = map_dataset(name, desc, SEED_QUESTIONS)
    grade = str(entry.get("grade", ""))
    p, p_why = _grade_p(grade)
    access = _access_class(entry)
    rep, rep_why = REPLICATION[access]
    cost = COST[access]

    # THE ADAPTIVE TERM. Region priority already folds in the desk's recorded attempts and
    # survivors with a revival floor, so a class of data the desk has worked to exhaustion scores
    # down HERE, from evidence, rather than being demoted by an author's opinion in a table.
    by_id = {q.id: q for q in SEED_QUESTIONS}
    prios = [priority(by_id[r], state=state) for r in regions if r in by_id]
    region_p = max(prios) if prios else 0.0
    worked = sum(int(state.get(r, {}).get("attempts", 0)) for r in regions)
    survived = sum(int(state.get(r, {}).get("survivors", 0)) for r in regions)

    score = p * information_gain(p) * rep * region_p / max(cost, 1e-6)
    unmeasured = (p == UNGRADED_P) or not regions
    return {
        "source": name,
        "score": round(score, 6),
        "p_usable": p,
        "grade": grade or "(none)",
        "access_class": access,
        "replication": rep,
        "cost": cost,
        "regions": regions[:8],
        "region_priority": round(region_p, 6),
        "desk_record": f"{survived} survivor(s) from {worked} attempt(s) in these regions",
        "unmeasured": unmeasured,
        "why": (
            f"{p_why}; {rep_why}; "
            + (f"informs {len(regions)} frontier region(s), best priority {region_p:.3f} "
               f"({survived}/{worked} survived there)"
               if regions else
               "MAPS TO NO FRONTIER REGION -- either genuinely off-thesis or the entry carries too "
               "little description to match. Scored zero rather than defaulted: a source nobody "
               "can say what it would answer is not an acquisition, it is a wish")),
    }


# ------------------------------------------------------------------ the machine writer

def _norm(s: object) -> str:
    """A url or name reduced to what makes two entries the same source."""
    t = str(s or "").strip().lower().rstrip("/")
    for p in ("https://", "http://", "www."):
        if t.startswith(p):
            t = t[len(p):]
    return t


def _entries(universe: dict) -> list[dict]:
    """Every source entry in the map, whatever shape its class holds."""
    out: list[dict] = []
    for v in (universe.get("sources") or {}).values():
        for e in (v if isinstance(v, list) else [v]):
            if isinstance(e, dict):
                out.append(e)
    return out


def _known(universe: dict) -> set[str]:
    """Everything the map already names, by url and by name. Membership here is a REFUSAL to
    write: the entry may carry a human licence verdict this script must never touch."""
    keys: set[str] = set()
    for e in _entries(universe):
        for field in ("url", "name", "host"):
            if e.get(field):
                keys.add(_norm(e[field]))
    return keys


def _forbidden(text: str) -> str | None:
    """The crypto-exchange fence, from the same table the miners use. A failure to import it is
    a REFUSAL to write, never a silent pass: an unenforceable mandate must stop the writer."""
    from libs.research.mechanism_claims import forbidden_venue
    return forbidden_venue(text)


def probe_rows(probe_dir: Path | None = None) -> list[dict]:
    """Dataset-kind discovery rows the miners have written, newest file last.

    THE PATH IS RESOLVED AT CALL TIME, NOT BOUND AS A DEFAULT. A `Path = PROBE_DIR` default
    captures the real directory when this module is imported, so repointing the constant --
    which is how every caller and every test aims this script at another tree -- silently does
    nothing and the run reads the live desk instead. Measured here the first time it ran.
    """
    probe_dir = PROBE_DIR if probe_dir is None else probe_dir
    rows: list[dict] = []
    try:
        files = sorted(probe_dir.glob(PROBE_GLOB))
    except OSError:
        return rows
    for f in files:
        doc = _read(f)
        for r in (doc if isinstance(doc, list) else []):
            if isinstance(r, dict) and str(r.get("kind") or "") == "dataset" and r.get("url"):
                rows.append(r)
    return rows


def _candidate_entry(r: dict, now: str) -> dict:
    """One probe as a map entry. The probe RESULT is the whole justification, and it is written
    down beside the grade so a human re-grading this row can see what was actually observed."""
    eps = int(r.get("n_endpoints") or 0)
    return {
        "name": str(r.get("title") or r.get("host") or r.get("url"))[:160],
        "url": str(r.get("url")),
        "host": str(r.get("host") or ""),
        "grade": MACHINE_GRADE,
        "origin": MACHINE_ORIGIN,
        "cost": "free",
        "verification": ("NOT opened or confirmed first-party; registered from a miner fetch. "
                         "DO NOT feed a live signal until a human or a dig seat grades it"),
        "probe": {"probed_at": str(r.get("available_time") or r.get("published") or now),
                  "registered_at": now, "n_endpoints": eps,
                  "endpoints": [str(e) for e in (r.get("endpoints") or [])[:12]],
                  "ground": r.get("ground"), "region": r.get("region"),
                  "language": r.get("language") or r.get("lang"),
                  "source": r.get("source"), "source_hash": r.get("source_hash")},
        "class": str(r.get("dataset_class") or "unclassified"),
        "note": (f"machine-registered: the miner fetched this page and found {eps} data "
                 f"endpoint(s). Registration is not adoption and not a licence verdict"),
    }


def merge_probes(universe: dict, rows: list[dict], *, now: str | None = None) -> dict:
    """Append every probed source the map does not already name. Returns the report.

    `universe` is mutated in place. Nothing that already exists is read, re-graded or rewritten:
    the only operation this function performs on the document is appending new entries and
    stamping `machine_updated` / `machine_writer`. The human `updated` date is left alone, so a
    reader can still see when a person last curated the file.
    """
    now = now or datetime.now(tz=UTC).isoformat()
    known = _known(universe)
    added: list[dict] = []
    skipped_known = 0
    refused: list[dict] = []
    for r in rows:
        key = _norm(r.get("url"))
        if not key:
            continue
        if key in known or _norm(r.get("title")) in known:
            skipped_known += 1
            continue
        blob = " ".join(str(r.get(k) or "") for k in ("title", "url", "host", "ground",
                                                      "dataset_class"))
        venue = _forbidden(blob)
        if venue:
            refused.append({"url": str(r.get("url")), "venue": venue})
            continue
        entry = _candidate_entry(r, now)
        cls = entry["class"]
        # `sources` is created only when there is something to put in it. A `setdefault` here
        # added an empty `sources` key to a map that had none, and since every reader resolves
        # the document as `universe.get("sources", universe)`, that empty key HID the whole
        # flat-shaped universe: a writer that adds nothing must leave no trace at all.
        sources = universe.setdefault("sources", {})
        bucket = sources.get(cls)
        if bucket is None:
            sources[cls] = [entry]
        elif isinstance(bucket, list):
            bucket.append(entry)
        else:
            # A human wrote this class as something other than a list. Its shape is not this
            # writer's to change, so the machine rows go beside it under their own key.
            sources.setdefault(f"{cls}__machine_probed", []).append(entry)
        known.add(key)
        added.append(entry)
    if added:
        universe["machine_updated"] = now
        universe["machine_writer"] = (
            "scripts/acquire_data.py registers miner-probed sources at grade "
            f"{MACHINE_GRADE} and never edits an existing entry: a human or LLM grade is "
            "final until a person changes it. Registration is not adoption.")
    return {"probes_read": len(rows), "added": len(added),
            "skipped_already_known": skipped_known, "refused_forbidden_venue": refused,
            "added_names": [e["name"] for e in added[:12]]}


def write_universe(universe: dict, path: Path | None = None) -> bool:
    """Resolved at call time for the reason `probe_rows` states: a bound default would write the
    live map however the constant was repointed."""
    path = UNIVERSE if path is None else path
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(universe, indent=1, ensure_ascii=False), "utf-8")
        return True
    except OSError:
        return False


def main() -> int:
    t0 = time.time()
    universe = _read(UNIVERSE)
    state = load_state(ONTOLOGY_STATE)
    moat = _read(MOAT) or {}

    if not isinstance(universe, dict) or not universe:
        out = {
            "ts": datetime.now(tz=UTC).isoformat(),
            "state": "NO SOURCE UNIVERSE",
            "reason": (f"{_rel(UNIVERSE)} absent or empty -- the digger publishes it "
                       "and data/ is gitignored, so this is expected in a fresh checkout and a "
                       "REAL blocker on the VPS. No ranking is offered: ranking zero candidates "
                       "would print an empty plan that reads like 'nothing worth acquiring'."),
            "next": "run the data-axis digger (ops/run_dataaxis_dig.sh) to publish the map",
            "candidates": 0,
        }
        REPORT.parent.mkdir(parents=True, exist_ok=True)
        REPORT.write_text(json.dumps(out, indent=1), "utf-8")
        print(f"acquire: NO SOURCE UNIVERSE -- {_rel(UNIVERSE)} absent. "
              "Ranking refused rather than faked.")
        return 0

    # REGISTER WHAT THE MINERS PROBED, BEFORE RANKING, so a source found this cycle is ranked
    # this cycle rather than a day later. A write failure is reported and never fatal: the
    # ranking is the job, and losing it because the map is read-only would be the worse trade.
    try:
        merged = merge_probes(universe, probe_rows())
        merged["written"] = bool(merged["added"]) and write_universe(universe)
    except Exception as exc:
        merged = {"probes_read": 0, "added": 0, "written": False,
                  "why": f"{type(exc).__name__}: {exc}"}

    entries = universe.get("sources", universe)
    rows = [score_candidate(str(k), v if isinstance(v, dict) else {"description": str(v)}, state)
            for k, v in entries.items()]
    rows.sort(key=lambda r: (-r["score"], r["source"]))
    for i, r in enumerate(rows, 1):
        r["rank"] = i

    measured = [r for r in rows if not r["unmeasured"]]
    out = {
        "ts": datetime.now(tz=UTC).isoformat(),
        "seconds": round(time.time() - t0, 2),
        "candidates": len(rows),
        "measured": len(measured),
        "registered": merged,
        "moat_coverage_pct": (moat.get("cumulative_coverage", {}) or {}).get("coverage_pct"),
        "plan": rows[:25],
        "top": rows[0]["source"] if rows else None,
        "note": (
            "score = P(usable) x information_gain(P) x replication_difficulty x region_priority "
            "/ cost. Multiplicative, like EVIG: no term rescues a dead one. The ADAPTIVE term is "
            "region_priority, which reads the ontology's recorded attempts and survivors -- so a "
            "class of data this desk has worked to exhaustion falls from EVIDENCE rather than "
            "from an author's opinion in a table. An ungraded source ranks below every graded "
            "one including the rejected ones, because a ranking that rewards not looking is "
            "worse than no ranking."),
        "authority": ("RANK AND REGISTER. It spends nothing, signs nothing and starts no "
                      f"collector. It appends miner-probed sources to {_rel(UNIVERSE)} at grade "
                      f"{MACHINE_GRADE} and never edits an existing entry -- a human or LLM "
                      "grade is final until a person changes it."),
    }
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(out, indent=1), "utf-8")
    with HISTORY.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps({"ts": out["ts"], "candidates": len(rows),
                             "measured": len(measured),
                             "top": out["top"]}, separators=(",", ":")) + "\n")

    print(f"acquire: {len(rows)} candidate(s), {len(measured)} measured | {out['seconds']}s")
    print(f"  registered: {merged['added']} new source(s) at {MACHINE_GRADE} from "
          f"{merged.get('probes_read', 0)} probe(s), "
          f"{merged.get('skipped_already_known', 0)} already known, "
          f"{len(merged.get('refused_forbidden_venue') or [])} refused (forbidden venue)"
          + ("" if merged.get("written") or not merged["added"] else "  [MAP NOT WRITTEN]"))
    for r in rows[:8]:
        flag = "    " if not r["unmeasured"] else "UNM "
        print(f"  [{flag}] #{r['rank']:<2} {r['source'][:38]:<38} {r['score']:.5f}  "
              f"{r['access_class']:<14} {r['desk_record']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

```

### scripts\check_desk_tasks.py
```python
#!/usr/bin/env python3
"""DESK-BOX SCHEDULER FENCE -- a disabled task is a silently stopped organ.

WHY (measured 2026-08-26). Stopping the gauntlet process mid-sweep left its Windows scheduled task
in the Disabled state. The task then had an enabled trigger and a valid next-run time and still
would never have fired again -- hourly CONVERSION would have stopped permanently while every
artifact on the research box stayed exactly as fresh as the last successful run, and nothing
anywhere would have said so. It was found by reading the task state by hand.

That is the same shape as every other silent-stop this desk has hit: the tape recorder exiting 0
on ModuleNotFoundError, shadow_cycle exiting 1 for an unknown period, promotion_gate publishing
NO-PRODUCER and returning 0. The pattern is always an organ whose FAILURE MODE IS SILENCE, and
the answer is always the same -- check the thing that actually matters rather than the exit code.

Here that thing is the task STATE on the box that runs it. The research box cannot see Windows
Task Scheduler from its own systemd, so this asks over the SSH identity already used for deploys.

An UNREACHABLE desk box is reported as UNREACHABLE, never as healthy: "we could not check" and
"it checks out" are different answers (L1.28a), and treating the first as the second is how a
dead box looks fine for a week.
"""
from __future__ import annotations

import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "desk_tasks.json"
ALARM = ROOT / "data" / "DESK_TASKS_ALARM.txt"
REMOTE = "contabo-mt5"

#: task -> what stops if it stops. Named so an alarm says what is lost, not just what is off.
CRITICAL = {
    "MT5-Gauntlet": "hourly CONVERSION -- certificates stop being produced entirely",
    "MT5-Shadow": "forward clocks stop accruing; evidence freezes while day counters run",
    "MT5-Hourly": "the tick tape and bar refresh stop; every downstream input goes stale",
    "MT5-DeskState": "the dashboard stops reflecting the live account",
}
HEALTHY = {"Ready", "Running"}


def main() -> int:
    now = datetime.now(tz=UTC)
    # A DEPLOYED SCRIPT, NOT AN INLINE COMMAND. Passing PowerShell through ssh from Python mangles
    # the nested quoting -- the same query that works by hand returned nothing here, and the
    # fence read that as UNREACHABLE. A check whose own transport is fragile manufactures the
    # alarm it exists to detect, so the query lives in a file on the box.
    try:
        r = subprocess.run(
            ["ssh", "-o", "ConnectTimeout=25", REMOTE,
             "powershell -ExecutionPolicy Bypass -File C:/opt/quant/task_states.ps1"],
            capture_output=True, text=True, timeout=90, check=False)
        raw = " ".join(x for x in r.stdout.split() if "=" in x)
    except (OSError, subprocess.SubprocessError) as exc:
        # The exception text goes into the artifact rather than a dropped local: an UNREACHABLE
        # report that cannot say WHY is one an operator has to reproduce by hand.
        raw = ""
        transport_error = f"{type(exc).__name__}: {exc}"
    else:
        transport_error = None
    if not raw:
        why = ("desk box UNREACHABLE -- this is not a clean bill of health. Every conversion "
               "organ lives on that box, so an unanswered check means the desk's certificate "
               "production is in an UNKNOWN state, not a working one.")
        OUT.write_text(json.dumps({"checked_at": now.isoformat(timespec="seconds"),
                                   "status": "UNREACHABLE", "why": why,
                                   "transport_error": transport_error}, indent=1), "utf-8")
        ALARM.write_text(f"DESK TASKS UNREACHABLE {now.isoformat(timespec='seconds')}\n\n{why}\n",
                         "utf-8")
        print(f"desk tasks: UNREACHABLE -- {why}")
        return 1

    states = {}
    for part in raw.replace(";", " ").split():
        if "=" in part:
            k, v = part.split("=", 1)
            states[k] = v
    bad = {k: v for k, v in states.items() if v not in HEALTHY}

    OUT.write_text(json.dumps({"checked_at": now.isoformat(timespec="seconds"),
                               "states": states, "unhealthy": bad,
                               "status": "OK" if not bad else "STOPPED"}, indent=1), "utf-8")
    if not bad:
        if ALARM.exists():
            ALARM.unlink()
        print(f"desk tasks: all {len(states)} critical task(s) healthy {states}")
        return 0

    lines = [f"  - {k} is {v} -- {CRITICAL.get(k, 'unknown organ')}" for k, v in sorted(bad.items())]
    body = (f"DESK TASKS STOPPED {now.isoformat(timespec='seconds')}\n\n" + "\n".join(lines) +
            "\n\n  A Disabled task keeps an enabled trigger and a valid next-run time and still "
            "never fires. Re-enable with:\n"
            "    ssh contabo-mt5 \"powershell -Command Enable-ScheduledTask -TaskName <name>\"\n")
    ALARM.write_text(body, "utf-8")
    print(body)
    return 1


if __name__ == "__main__":
    sys.exit(main())

```

### scripts\run_cost_identification.py
```python
#!/usr/bin/env python3
"""COST IDENTIFICATION (L1.45) -- fit the execution cost surface from the desk's OWN fills.

This is the producer for the three `libs/execution/ramp_gate.py` step-up conditions that had NO
PRODUCER ANYWHERE IN THE REPO (verified 2026-08-01: `cost_ratio`, `slippage_ks_p` and
`calibration_mae_falling_months` appeared only in CONSUMERS -- ramp_gate.py:62,67,70 and
staging.py:84 -- plus mutation-test fixtures). `data/live_guard.json` shows the consequence:

    ramp.size_fraction = 0.10   blocked by: a_cost_le_1_25x, c_slippage_ks_p_gt_0_05,
                                            e_mae_falling_2_months, ...

The book was pinned to the FLOOR RUNG by three statistics nothing computed. The ramp could not
advance by waiting, because waiting was never what it was short of.

TWO NUMBERS, AND THEY ARE DIFFERENT KINDS OF THING:

  1. CALIBRATION (this file, today, from observational fills). "Is the modelled cost right?"
     realised pair slippage vs `data/cost_model.json`'s book-walk prediction. Purely
     observational, and that is FINE for calibration: comparing prediction to outcome needs no
     intervention. This is what unpins the ramp.

  2. THE CAUSAL SLOPE (this file, once excitation arms accrue). "What would cost be if we waited
     longer?" That is a COUNTERFACTUAL and observational fills CANNOT answer it: maker wait is a
     deterministic function of side today (240s iff spot BUY, 8s iff spot SELL,
     executor:1246), so wait and side are perfectly collinear. Reported UNIDENTIFIED until
     randomised arms exist -- never estimated from the confounded data and never defaulted.

WHY A BOOK-WALK CANNOT REPLACE THIS (and why the queued remedy of walking BIGGER sizes will not
work either): walking a recorded book measures the cost of consuming DISPLAYED depth in a book
that existed WITHOUT OUR ORDER IN IT -- biased down by refill and fade, biased up by hidden
liquidity, with neither bias signed a priori. No quantity of book-walking resolves a
counterfactual. Only our own fills measure our own cost.

THE REFUSAL PATH IS THE LOAD-BEARING PART. `cost_ratio` is a gate on SIZE INCREASES: publishing
one computed from too few fills would step the book up on fiction, which is strictly worse than
leaving it pinned. Below `MIN_FILLS_FOR_RAMP` this script writes NO ramp evidence at all, so
ramp_gate's fail-closed defaults (999.0 / 0.0 / 0.0) keep blocking. An UNDERPOWERED fit must
never read as a passed condition.

STATUS: OK / UNIDENTIFIED (no randomised arms -- causal slope unavailable) / UNDERPOWERED (fewer
than MIN_FILLS_FOR_RAMP instrumented fills) / NO-DATA (no usable fills at all).

    python scripts/run_cost_identification.py [--json] [--write-ramp]
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

# L1.42 LAWFUL ENTRY: pages, does not block -- a governance fault must never silently stop the
# organ that unpins the ramp.
from libs.execution import excitation, execution_tape  # noqa: E402
from libs.ops.lawful import guard as _law_guard  # noqa: E402

_COST_MODEL = _ROOT / "data/cost_model.json"
_OUT = _ROOT / "data/cost_surface.json"
_RAMP = _ROOT / "data/ramp_state.json"

# PRE-REGISTERED. The minimum instrumented fills before ANY ramp evidence is published. Chosen
# before looking at the fit, and it binds hard: at the 2026-08-01 measurement only 10 of 523 tape
# rows carried slippage fields, so this script's first run refuses on purpose.
MIN_FILLS_FOR_RAMP = 30
# Trailing window the ramp gate's conditions are defined over (ramp_gate.TRAILING_WEEKS_REQUIRED).
TRAILING_DAYS = 56


def _f(v: Any) -> float | None:
    try:
        if v is None:
            return None
        return float(v)
    except (TypeError, ValueError):
        return None


def _modelled_open_bps(cm: dict[str, Any], symbol: str, notional: float) -> float | None:
    """The book-walk prediction for opening `notional` in `symbol`, in bps of mid.

    Picks the NEAREST modelled size bucket rather than interpolating: the buckets are coarse
    (100/250/500/1000/2500) and a linear interpolation between them would invent a smoothness
    the book-walk never measured. Returns None when the symbol was never modelled -- which is
    itself the finding (the absorbing set), never a default.
    """
    try:
        pair = cm["symbols"][symbol]["pair"]
    except (KeyError, TypeError):
        return None
    best: tuple[float, float] | None = None
    for size_s, row in pair.items():
        size = _f(size_s)
        bps = _f(row.get("pair_open_bps")) if isinstance(row, dict) else None
        if size is None or bps is None:
            continue
        d = abs(size - notional)
        if best is None or d < best[0]:
            best = (d, bps)
    return None if best is None else best[1]


def _row_stamp(r: dict[str, Any]) -> str:
    return str(r.get("opened") or r.get("closed") or r.get("_taped") or "")


# A trading day counts as instrumented once at least this share of its fills carry slippage.
# Rollout days sit between 0 and 1 and must fall on the UNINSTRUMENTED side: the epoch is meant
# to mark where coverage became RELIABLE, not where it was first glimpsed.
_TCA_DAY_THRESHOLD = 0.5


def _tca_coverage(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Separate 'predates instrumentation' from 'should have been instrumented and was not'.

    THIS DISTINCTION IS THE WHOLE DIAGNOSIS AND GETTING IT WRONG COSTS A SESSION, in either
    direction. The raw ratio is 10 of 523 tape rows (1.9%), which reads as a catastrophic
    instrumentation hole and sends the next session to fix the TCA wrapper. Measured per day:

        07-20  0/20    07-21  0/38    07-22  1/47    07-26  1/12    07-27  2/5    07-31  6/6

    Instrumentation is at 100% and the fit is starved of FILLS, not of the FIELD -- the opposite
    next action (resume the book) from the one the raw ratio implies (go fix the recorder).

    THE EPOCH IS THE START OF THE LONGEST TRAILING RUN OF INSTRUMENTED DAYS, not the first
    instrumented row. The obvious first-row rule is what this function originally used and it was
    wrong on this very data: ONE stray instrumented fill on 07-22 dragged the epoch back nine
    days and reported '60 fills uninstrumented', recommending a fix to a recorder that now runs
    at 6/6. A single unrepresentative row must not be able to poison a diagnosis.
    """
    by_day: dict[str, list[bool]] = defaultdict(list)
    for r in rows:
        day = _row_stamp(r)[:10]
        if day:
            by_day[day].append(r.get("spot_slip_bps") is not None)
    days = sorted(by_day)
    per_day = {d: {"n": len(v), "instrumented": sum(v)} for d, v in by_day.items()}
    if not any(v["instrumented"] for v in per_day.values()):
        return {"epoch": None, "n_before_epoch": len(rows), "n_since_epoch": 0,
                "n_instrumented_since_epoch": 0, "uninstrumented_since_epoch": [],
                "per_day": per_day,
                "note": "no tape row has ever carried slippage fields"}
    # Walk back from the most recent day while coverage holds; the epoch is where it breaks.
    epoch = None
    for d in reversed(days):
        v = per_day[d]
        if v["n"] and (v["instrumented"] / v["n"]) >= _TCA_DAY_THRESHOLD:
            epoch = d
        else:
            break
    if epoch is None:
        return {"epoch": None, "n_before_epoch": len(rows), "n_since_epoch": 0,
                "n_instrumented_since_epoch": 0, "uninstrumented_since_epoch": [],
                "per_day": per_day,
                "note": ("no trading day has yet reached "
                         f"{_TCA_DAY_THRESHOLD:.0%} instrumentation -- rollout incomplete")}
    since = [r for r in rows if _row_stamp(r)[:10] >= epoch]
    missing = [f"{r.get('event')} {r.get('symbol')} {_row_stamp(r)[:10]}"
               for r in since if r.get("spot_slip_bps") is None]
    return {
        "epoch": epoch,
        "n_before_epoch": len(rows) - len(since),
        "n_since_epoch": len(since),
        "n_instrumented_since_epoch": len(since) - len(missing),
        "uninstrumented_since_epoch": missing,
        "per_day": per_day,
        "note": (f"instrumentation reliable from {epoch}; {len(rows) - len(since)} rows predate "
                 f"it and are NOT a defect. Gaps since the epoch, if any, are."),
    }


def _usable(rows: list[dict[str, Any]], cm: dict[str, Any],
            now: datetime) -> list[dict[str, Any]]:
    """Fills carrying BOTH realised slippage legs and a modelled counterpart.

    A row without slippage fields is not a cheap observation, it is NO observation: the tape
    records the fill, but the number this whole file is about was never captured on it.
    """
    out: list[dict[str, Any]] = []
    for r in rows:
        s, f = _f(r.get("spot_slip_bps")), _f(r.get("fut_slip_bps"))
        notional = _f(r.get("notional"))
        sym = str(r.get("symbol") or "")
        if s is None or f is None or not notional or notional <= 0 or not sym:
            continue
        stamp = str(r.get("opened") or r.get("closed") or r.get("_taped") or "")
        try:
            when = datetime.fromisoformat(stamp)
        except ValueError:
            continue
        if when.tzinfo is None:
            when = when.replace(tzinfo=UTC)
        if (now - when).days > TRAILING_DAYS:
            continue
        modelled = _modelled_open_bps(cm, sym, notional)
        out.append({
            "symbol": sym,
            "when": when,
            "notional": notional,
            "realised_bps": s + f,
            "modelled_bps": modelled,
            "wait_s": _f(r.get("wait_s")),
            "exc_arm": r.get("exc_arm"),
            "exc_baseline": r.get("exc_baseline"),
            "event": r.get("event"),
        })
    return out


def _ks_p(a: list[float], b: list[float]) -> float | None:
    """Two-sample KS p-value, realised vs modelled. None when either sample is empty."""
    if not a or not b:
        return None
    try:
        from scipy import stats
    except ImportError:
        return None
    return float(stats.ks_2samp(a, b).pvalue)


def _mae_falling_months(paired: list[dict[str, Any]]) -> tuple[int, dict[str, float]]:
    """Consecutive most-recent months in which calibration MAE FELL.

    Returns (streak, per-month MAE). A month with no paired fills breaks the streak rather than
    being skipped: 'MAE fell' across a gap is not evidence the model improved, it is evidence
    nothing was measured, and the ramp condition must not be satisfiable by silence.
    """
    by_month: dict[str, list[float]] = defaultdict(list)
    for p in paired:
        if p["modelled_bps"] is None:
            continue
        by_month[p["when"].strftime("%Y-%m")].append(
            abs(p["realised_bps"] - p["modelled_bps"]))
    mae = {m: round(statistics.mean(v), 4) for m, v in sorted(by_month.items())}
    months = sorted(mae)
    streak = 0
    for i in range(len(months) - 1, 0, -1):
        if mae[months[i]] < mae[months[i - 1]]:
            streak += 1
        else:
            break
    return streak, mae


def _collinearity(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Is maker wait still a deterministic function of side in the observed fills?

    This is the identification diagnostic itself. While every open shares one wait and every
    close shares another, the wait coefficient is not weakly identified -- it is NOT IDENTIFIED,
    and no sample size changes that. Reporting it as a number would be the single most dangerous
    output this file could produce.
    """
    waits_by_event: dict[str, set[float]] = defaultdict(set)
    for r in rows:
        if r["wait_s"] is not None:
            waits_by_event[str(r["event"])].add(round(r["wait_s"], 3))
    distinct = {k: sorted(v) for k, v in waits_by_event.items()}
    randomised = [r for r in rows if r.get("exc_baseline") is False]
    return {
        "distinct_waits_by_event": distinct,
        "n_randomised_arms": len(randomised),
        "arms_seen": sorted({str(r.get("exc_arm")) for r in randomised}),
        "identified": len(randomised) > 0,
    }


def _absorbing(cm: dict[str, Any], design: excitation.Design) -> dict[str, Any]:
    """Symbols the cost model can never measure because the recorder never records them.

    The recorder's universe is [_BENCH, book_symbols, recently_traded, _CORE][:32] and the cost
    model walks only recorded symbols, so an unmeasured name needs ~4x the funding of a measured
    one to clear the entry gate -- which is why it is never traded, never recorded, and never
    measured. This counts the reachable set; it does not fix it.
    """
    measured = sorted(cm.get("symbols", {}))
    return {
        "n_measured": len(measured),
        "measured": measured,
        "n_design_cells_unidentified": len(design.unidentified_cells),
        "unidentified_cells": design.unidentified_cells,
    }


def build_report(now: datetime | None = None, root: Path | None = None) -> dict[str, Any]:
    """Pure: read tape + cost model, return the surface. No writes, so tests call it directly."""
    root = root or _ROOT
    now = now or datetime.now(tz=UTC)
    try:
        cm = json.loads((root / "data/cost_model.json").read_text("utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        cm = {}
        cm_note = f"cost model UNREADABLE: {e!r}"
    else:
        cm_note = f"cost model: {len(cm.get('symbols', {}))} symbols"

    tape_path = root / "data/moat/execution_tape/cashcarry_trades.jsonl"
    rows = execution_tape.read(path=tape_path)
    design = excitation.load_design(root / "data/excitation_design.json")
    usable = _usable(rows, cm, now)
    paired = [u for u in usable if u["modelled_bps"] is not None]
    tca = _tca_coverage(rows)

    realised = [p["realised_bps"] for p in paired]
    modelled = [p["modelled_bps"] for p in paired]
    ident = _collinearity(usable)
    streak, mae_by_month = _mae_falling_months(paired)

    cost_ratio = None
    if paired and statistics.median(modelled) > 0:
        cost_ratio = round(statistics.median(realised) / statistics.median(modelled), 4)
    ks_p = _ks_p(realised, modelled)

    # STATUS, worst first, and the empty case BEFORE OK (L1.28a).
    if not usable:
        status = "NO-DATA"
        detail = (f"0 of {len(rows)} tape rows carry slippage fields -- the tape records the "
                  f"fill but not the number this file exists to fit (R0058/R0084)")
    elif len(paired) < MIN_FILLS_FOR_RAMP:
        status = "UNDERPOWERED"
        detail = (f"{len(paired)} usable fills (< MIN_FILLS_FOR_RAMP={MIN_FILLS_FOR_RAMP}) -- "
                  f"NO ramp evidence published, so ramp_gate's fail-closed defaults keep "
                  f"blocking the step-up. TCA began {tca['epoch']}: {tca['n_before_epoch']} of "
                  f"{len(rows)} tape rows PREDATE instrumentation and are not a defect; "
                  f"{tca['n_instrumented_since_epoch']}/{tca['n_since_epoch']} rows since the "
                  f"epoch are instrumented")
    elif not ident["identified"]:
        status = "UNIDENTIFIED"
        detail = ("calibration fit is powered, but ZERO randomised arms -- the wait coefficient "
                  "is not weakly identified, it is unidentified (wait is a deterministic "
                  "function of side)")
    else:
        status = "OK"
        detail = (f"{len(paired)} instrumented fills, {ident['n_randomised_arms']} randomised "
                  f"arms across {len(ident['arms_seen'])} conditions")

    # PUBLISHED ONLY WHEN POWERED. This dict is what a caller may merge into ramp evidence;
    # empty means "nothing proven", which the gate correctly reads as "do not step up".
    ramp_evidence: dict[str, Any] = {}
    if status in ("OK", "UNIDENTIFIED") and cost_ratio is not None:
        ramp_evidence = {
            "cost_ratio": cost_ratio,
            "slippage_ks_p": ks_p,
            "calibration_mae_falling_months": streak,
            "_source": "scripts/run_cost_identification.py",
            "_n_fills": len(paired),
            "_generated": now.isoformat(),
        }

    return {
        "generated": now.isoformat(),
        "law": "L1.45 -- execution excitation: a controller that never perturbs cannot identify "
               "the cost surface it gates on",
        "status": status,
        "detail": detail,
        "n_tape_rows": len(rows),
        "n_instrumented": len(usable),
        "n_paired_with_model": len(paired),
        "instrumented_frac": round(len(usable) / len(rows), 4) if rows else 0.0,
        "cost_model_note": cm_note,
        "tca_coverage": tca,
        "calibration": {
            "realised_median_bps": round(statistics.median(realised), 4) if realised else None,
            "modelled_median_bps": round(statistics.median(modelled), 4) if modelled else None,
            "cost_ratio": cost_ratio,
            "slippage_ks_p": ks_p,
            "mae_by_month": mae_by_month,
            "calibration_mae_falling_months": streak,
        },
        "identification": ident,
        "causal_wait_slope_bps_per_s": (
            None if not ident["identified"] else "see arms -- fit deferred until n>=cell target"),
        "absorbing_set": _absorbing(cm, design),
        "ramp_evidence": ramp_evidence,
        "next_action": (
            "Instrument the fill path: no tape row has ever carried slippage fields"
            if status == "NO-DATA" else
            # The accurate call depends on WHICH shortage binds, and the two point opposite ways.
            (f"ACCRUE FILLS -- instrumentation is healthy "
             f"({tca['n_instrumented_since_epoch']}/{tca['n_since_epoch']} since {tca['epoch']}); "
             f"the fit needs the book trading, not a recorder fix"
             if not tca["uninstrumented_since_epoch"] else
             f"FIX INSTRUMENTATION -- {len(tca['uninstrumented_since_epoch'])} fills since "
             f"{tca['epoch']} carry no slippage: {tca['uninstrumented_since_epoch'][:5]}")
            if status == "UNDERPOWERED" else
            "Enable excitation arms so the wait coefficient becomes identifiable"
            if status == "UNIDENTIFIED" else "Merge ramp_evidence into data/ramp_state.json"),
    }


def _merge_ramp(rep: dict[str, Any], path: Path) -> str:
    """Merge published evidence into ramp_state.json WITHOUT clobbering other producers' keys.

    `evidence` is shared: live_sharpe and drill_pass_streak_weeks come from elsewhere. A whole-
    file rewrite here would delete another organ's evidence and read as a ramp regression with no
    cause -- the read-without-writer class, inverted.
    """
    if not rep["ramp_evidence"]:
        return f"nothing published ({rep['status']}) -- ramp_state.json left untouched"
    try:
        state = json.loads(path.read_text("utf-8")) if path.exists() else {}
        if not isinstance(state, dict):
            state = {}
    except (OSError, json.JSONDecodeError) as e:
        return f"ramp_state.json UNREADABLE ({e!r}) -- refusing to overwrite it"
    ev = state.get("evidence")
    state["evidence"] = {**(ev if isinstance(ev, dict) else {}), **rep["ramp_evidence"]}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, indent=2) + "\n", "utf-8")
    return f"merged {len(rep['ramp_evidence'])} fields into {path}"


def main() -> int:
    _law_guard()
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--write-ramp", action="store_true",
                    help="merge published evidence into data/ramp_state.json")
    args = ap.parse_args()
    rep = build_report()
    _OUT.parent.mkdir(parents=True, exist_ok=True)
    _OUT.write_text(json.dumps(rep, indent=2, default=str) + "\n", "utf-8")
    if args.write_ramp:
        rep["ramp_write"] = _merge_ramp(rep, _RAMP)
        _OUT.write_text(json.dumps(rep, indent=2, default=str) + "\n", "utf-8")
    if args.json:
        print(json.dumps(rep, indent=2, default=str))
    else:
        print(f"cost identification (L1.45): {rep['status']} -- {rep['detail']}")
        c = rep["calibration"]
        print(f"  instrumented {rep['n_instrumented']}/{rep['n_tape_rows']} tape rows "
              f"({rep['instrumented_frac']:.1%}); paired with model: "
              f"{rep['n_paired_with_model']}")
        if c["cost_ratio"] is not None:
            print(f"  realised {c['realised_median_bps']} bps vs modelled "
                  f"{c['modelled_median_bps']} bps -> cost_ratio {c['cost_ratio']}")
        print(f"  identified: {rep['identification']['identified']} "
              f"(randomised arms: {rep['identification']['n_randomised_arms']}); "
              f"waits by event: {rep['identification']['distinct_waits_by_event']}")
        print(f"  next: {rep['next_action']}")
        if "ramp_write" in rep:
            print(f"  ramp: {rep['ramp_write']}")
    # A starved or unidentified fit is a REPORT, not a gate failure: this script's job is to
    # produce the number, and it cannot conjure fills that were never instrumented. The FENCE
    # (check_excitation.py) is what fails on it.
    return 0


if __name__ == "__main__":
    sys.exit(main())

```

### scripts\run_trade_forensics.py
```python
"""Daily trade-class forensics -- the mechanical version of the probes that found gaps #42/#43/#34.

On 2026-07-22 the principal's manual pushing surfaced three profit leaks the cycle had missed:
churn drag (-8.1%/yr in sub-8h holds), baseline-funding entries (-92.7 bps, ~80% of gross profit),
and concentrated leg-thrash losses. All three were visible in ONE artifact the desk already owned
-- data/cashcarry_trades.json -- bucketed three ways. Per the RECURSION RULE, that analysis is now
a standing daily check: pure python, quota-free, runs even when the brain is auth-dead (as it was
the day this was written). Writes web/trade_forensics.json (the executor's denylist source) plus a
tracked copy at docs/research/trade_forensics_latest.json; run_alerts pages on any bleeding class.

    python scripts/run_trade_forensics.py
"""
from __future__ import annotations

# PATH BOOTSTRAP. `python scripts/x.py` puts scripts/ on sys.path, NOT the repo root, so `libs`
# resolves only if the project happens to be pip-installed into the interpreter in use. The daily
# cycle invokes these by path. Without this the libs imports fail -- and in run_trade_forensics a
# broad `except Exception` caught exactly that and shipped {"error": "ModuleNotFoundError"} into
# the artifact, where an error string is indistinguishable from data to every reader downstream.
import sys as _sys
from pathlib import Path as _P

if str(_P(__file__).resolve().parent.parent) not in _sys.path:
    _sys.path.insert(0, str(_P(__file__).resolve().parent.parent))


import json
from collections import defaultdict
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from libs.execution import leg_modes
from libs.ops.desk_host import is_owning_host

_TRADES = Path("data/cashcarry_trades.json")
_OUT = Path("web/trade_forensics.json")
# A MODULE CONSTANT so a test can inject one (2026-08-13). This was a local inside main(), so the
# entry-gate detector's only test read the LIVE desk cost model: it asserted a BNBUSDT open was
# flagged, the measured book got cheaper (0.344 bps pair round-trip at that size), and the test
# went red for a reason having nothing to do with the behaviour it pins. A test that fails when
# the desk's state moves teaches readers to discount red -- which is how the merge-union defect
# this file's `bleeding_symbols` key repairs stayed invisible for eight days.
_COST_MODEL = Path("data/cost_model.json")
# web/ is untracked runtime state: evidence that exists ONLY there is invisible to any checkout
# and unciteable by an audit (R0160). _TRACKED is the governed, reports-parallel copy of the same
# doc; run_cashcarry_executor keeps reading _OUT -- the denylist read path must not move.
_TRACKED = Path("docs/research/trade_forensics_latest.json")
_MIN_N = 15            # a class needs this many trades before its verdict is trusted
_WINDOW_D = 14.0       # ROLLING window: all-history flags would re-page forever even
                       # after fixes work; the question is "is it bleeding NOW"
_BLEED_BPS = -1.0      # class net worse than this (bps of notional) = defect
# DENYLIST EVIDENCE IS ALL-TIME, ALERTS ARE ROLLING (2026-08-05, restored 2026-08-13). These
# mirror the executor's `_BLEED_BPS`/`_BLEED_MIN_N`; the mirror exists because importing the
# executor opens venue connections, so tests/execution/test_carry_entry_gate.py asserts the two
# pairs stay equal and drift fails CI instead of silently re-blinding the fence.
_DENY_BPS = -20.0      # all-time realised net bps at which a symbol is structurally bleeding
_DENY_MIN_N = 5        # minimum closed trades before that verdict is trusted
_FEE_RT_BPS = 10.0     # futures leg billed twice per round-trip at ~5 bps taker rack rate
_FEE_BPS_MAX = 50.0    # 5x that -- generous for maker/taker mix + partials, so anything above
                       # is fills the book never intended, not an execution-quality gradient
_BASELINE = 0.000100   # Binance default funding -- carries no premium information by itself
# entry-gate ship time. The CONTRACT CHANGED 2026-07-31 (R0057): the absolute funding floor was
# deleted in favour of the executor's per-symbol arithmetic -- allow an open iff
# funding * 1e4 * periods > pair_roundtrip_bps, periods = max(1, _MIN_HOLD_H/8) = 3. A baseline
# open on a tight measured major (BTC rt < 3 bps) is that design WORKING; flagging every
# baseline open forever re-litigates a ledgered decision and turns this flag into a
# permanently-red light nobody reads (L1.43). The regression test below now mirrors the
# executor's modelled cost (bucket-by-notional, legacy-500 fallback, p90 fail-closed default for
# unmeasured names). KNOWN LOOSER EDGE, deliberate and named: the executor additionally floors
# the model with each symbol's REALISED round-trip, which this reader cannot reconstruct -- so
# this detector can under-fire only where realised costs exceed modelled. The durable close is
# the executor stamping its gate arithmetic on the open row (rowed; blocked behind the pending
# executor-lineage merge -- see F0021).
_GATE_DATE = "2026-07-22T20:00:00+00:00"
_GATE_PERIODS = 3.0             # max(1, 24h min-hold / 8h funding period)
_GATE_DEFAULT_RT_BPS = 39.5     # p90 of measured round-trips; fail-closed for unmeasured names


def _gate_rt_bps(sym: str, notional: float, cost_model: dict[str, Any]) -> float:
    """Modelled pair round-trip for the entry-gate mirror. Bucket covering the per-leg notional,
    legacy-500 fallback, larger buckets clamped tighten-only vs 500 -- the executor's _rt_bps
    minus its realised floor (unavailable here; direction of the gap is documented above)."""
    try:
        pair = cost_model["symbols"][sym]["pair"]
        sizes = sorted(float(k) for k in pair)
        key = next((k for k in sizes if notional <= k), sizes[-1] if sizes else 500.0)
        v = pair.get(f"{key:g}", {}).get("pair_roundtrip_bps")
        if v is None:
            v = pair.get("500", {}).get("pair_roundtrip_bps")
        if v is None:
            return _GATE_DEFAULT_RT_BPS
        v = float(v)
        if key > 500.0:
            v500 = pair.get("500", {}).get("pair_roundtrip_bps")
            if v500 is not None:
                v = max(v, float(v500))
        return v
    except (KeyError, TypeError, ValueError):
        return _GATE_DEFAULT_RT_BPS


_BUCKETS = (("<2h", 0.0, 2.0), ("2-8h", 2.0, 8.0), ("8-24h", 8.0, 24.0), (">24h", 24.0, 1e9))


def _buckets(closes: list[dict[str, Any]],
             fees: dict[int, float] | None = None) -> dict[str, dict[str, Any]]:
    """Hold-class economics. With ``fees`` (id(trade) -> venue commission) the net is charged the
    actual fee bill; without it the net is the trade log's own fee-blind figure."""
    out: dict[str, dict[str, Any]] = {}
    for lbl, lo, hi in _BUCKETS:
        g = [x for x in closes if lo <= float(x.get("held_hours") or 0) < hi]
        nt = sum(float(x.get("notional") or 0) for x in g)
        net = sum(float(x.get("net") or 0) for x in g)
        row = {"n": len(g), "notional": round(nt, 2)}
        if fees is not None:
            fee = sum(fees.get(id(x), 0.0) for x in g)
            net -= fee
            row["fee"] = round(fee, 2)
        row["net"] = round(net, 2)
        row["bps"] = round(1e4 * net / nt, 2) if nt else 0.0
        out[lbl] = row
    return out


def _ms(stamp: Any) -> int | None:
    try:
        return int(datetime.fromisoformat(str(stamp)).timestamp() * 1000)
    except Exception:
        return None


def _fee_attribution(closes: list[dict[str, Any]], since_ms: int) -> dict[str, Any]:
    """Charge each logged round-trip the commission the VENUE actually billed for it.

    ORIGIN (2026-07-28). Every economic verdict this organ produces was computed from the trade
    log's ``net`` = price_pnl + est_funding. Neither term contains a fee: ``_tca`` records
    slippage-vs-mid only. So the hold-class verdicts, the symbol blacklist, and the forward track
    record that Gate 0 will size REAL capital on all omitted the dominant cost of the trade -- and
    this organ's own comment already called fees "the primary unit-economics lever". Disclosed and
    not gated is an open defect, so the gate is built here.

    The join is (symbol, open<=event<=close). The book holds at most one carry per symbol at a
    time, so those windows never overlap and each event is claimed by at most ONE trade; whatever
    is left over is UNATTRIBUTED -- commission the venue charged against no round-trip this book
    believes it made. That residual is the churn-loop fingerprint measured directly (the loop
    billed $1,746.66 against ~$126 of logged round-trips), so it is reported rather than spread
    silently over the trades that happen to be nearby.

    FUTURES COMMISSION ONLY -- /fapi income cannot see spot-leg fees, so this is a LOWER BOUND on
    the true bill and is labelled as one. A venue that cannot be read yields no fee-adjusted
    verdict at all: an unmeasured cost reported as zero is the phantom this whole organ exists to
    prevent.
    """
    try:
        import libs.execution.binance_testnet as _fut
        events = _fut.commission_events(since_ms)
    except Exception as e:                       # venue unreachable is not a fee defect
        return {"error": f"{type(e).__name__}: {e}",
                "note": "venue unreachable -- no fee-adjusted verdict this run"}

    spans: dict[str, list[tuple[int, int, dict[str, Any]]]] = defaultdict(list)
    for x in closes:
        o, c = _ms(x.get("opened")), _ms(x.get("closed"))
        if o is not None and c is not None:
            spans[str(x.get("symbol"))].append((o, c, x))
    for v in spans.values():
        v.sort(key=lambda r: r[0])

    fees: dict[int, float] = {}
    attributed = unattributed = 0.0
    for ev in events:
        amt = float(ev["commission"])
        for o, c, tr in spans.get(ev["symbol"], ()):
            if o <= ev["time"] <= c:
                fees[id(tr)] = fees.get(id(tr), 0.0) + amt
                attributed += amt
                break
        else:
            unattributed += amt

    venue_total = attributed + unattributed
    logged_nt = sum(float(x.get("notional") or 0) for x in closes)
    return {
        "_fees": fees,                                    # popped before publish (id-keyed)
        "venue_commission": round(venue_total, 2),
        "attributed": round(attributed, 2),
        "unattributed": round(unattributed, 2),
        "unattributed_share": round(unattributed / venue_total, 3) if venue_total else None,
        "n_events": len(events),
        "fee_bps_of_logged_notional": (round(1e4 * venue_total / logged_nt, 2)
                                       if logged_nt else None),
        "scope": "futures commission only (/fapi income); spot-leg fees not visible -> LOWER BOUND",
    }


def _leg_share(trades: list[dict[str, Any]], key: str) -> float | None:
    """Maker share of one leg. None when no record carries a measurable mode for it.

    TWO EXCLUSIONS, AND BOTH ARE THE DENOMINATOR RATHER THAN THE NUMERATOR (R0029). A fill rate
    may only count legs where a fill was ATTEMPTED, and a third of the logged legs never sent an
    order:

      * `already-flat` -- the leg was square, so nothing was placed. `libs.execution.leg_modes`
        owns that vocabulary for this organ and for scripts/fill_quality_monitor.
      * `close` events -- closes BYPASS the maker path DELIBERATELY. A post-only close carries
        neither reduceOnly nor a venue size cap, and twice accumulated resting fills that bought
        a short through zero into a long (+916,772 and +1,138,985 units). "Patient on opens, fast
        on closes" is the rule; counting a close as a failed maker fill scores a SAFETY POLICY as
        an execution defect.

    THE CLOSE EXCLUSION WAS DROPPED AND THE DISTORTION WAS UNEVEN, which is what made it
    dangerous rather than merely wrong: futures carries roughly twice as many excluded legs as
    spot, so the two legs were understated by different amounts and the real shape was hidden.
    R0029 read "spot maker share 23.8% vs a 60% target, futures 61.9%" and the true picture on
    genuine attempts is futures converting 100% with the entire gap sitting in the spot quote --
    a different problem, pointing at different work.
    """
    attempted = [x for x in trades if str(x.get("event") or "").lower() != "close"]
    modes = [x[key] for x in attempted if leg_modes.placed_order(x.get(key))]
    return round(sum(leg_modes.is_maker(m) for m in modes) / len(modes), 3) if modes else None


def _tape_sync(trades: list[dict[str, Any]]) -> dict[str, Any]:
    """Mirror the rolling buffer into the permanent execution tape, and report the margin.

    The buffer is capped at 500 events (run_cashcarry_executor._log_trade). At the observed event
    rate that is ~18.6 days of tape against this script's 14-day window -- only ~4.6 days of
    headroom before the buffer starts silently eating the window it is asked to analyse. Backfill
    is idempotent, so running it here makes the tape self-heal daily even when the executor is on
    an older build; the margin is surfaced so the squeeze can never arrive unannounced.
    """
    try:
        from libs.execution import execution_tape
        added = execution_tape.backfill(trades)
        cov = execution_tape.coverage()
        stamps = sorted(str(x.get("closed") or x.get("opened") or "") for x in trades if x)
        buf_days = 0.0
        if len(stamps) >= 2 and stamps[0] and stamps[-1]:
            buf_days = (datetime.fromisoformat(stamps[-1])
                        - datetime.fromisoformat(stamps[0])).total_seconds() / 86400
        return {"taped": cov["n"], "tape_days": cov["days"], "backfilled": added,
                "buffer_days": round(buf_days, 2),
                "window_margin_days": round(buf_days - _WINDOW_D, 2),
                "buffer_squeezing_window": bool(buf_days and buf_days < _WINDOW_D)}
    except Exception as e:  # observer -- never break the daily forensics run
        return {"error": f"{type(e).__name__}: {e}"}


def main() -> None:
    trades = json.loads(_TRADES.read_text("utf-8")) if _TRADES.exists() else []
    tape = _tape_sync(trades)
    all_closes = [x for x in trades
                  if x.get("event") == "close" and x.get("held_hours") is not None]
    cutoff = (datetime.now(tz=UTC) - timedelta(days=_WINDOW_D)).isoformat()
    closes = [x for x in all_closes if str(x.get("closed", "")) >= cutoff]
    flags: list[str] = []

    hold = _buckets(closes)
    for lbl, b in hold.items():
        if b["n"] >= _MIN_N and b["bps"] < _BLEED_BPS:
            flags.append(f"hold-class {lbl} bleeding: {b['bps']} bps over {b['n']} trades "
                         f"(net ${b['net']})")

    # VENUE-TRUTH COST (2026-07-28). Everything above this line is fee-blind; everything below
    # charges the bill the exchange actually sent. Both are published because the DIVERGENCE is
    # the diagnostic -- replacing one number with the other would hide the measurement gap that
    # let a $1,750 fee fire read as a break-even book.
    since_ms = int((datetime.now(tz=UTC) - timedelta(days=_WINDOW_D)).timestamp() * 1000)
    fee_attr = _fee_attribution(closes, since_ms)
    fees = fee_attr.pop("_fees", None)
    hold_nof: dict[str, dict[str, Any]] | None = None
    if fees is not None:
        hold_nof = _buckets(closes, fees)
        for lbl, b in hold_nof.items():
            if b["n"] < _MIN_N or not b["notional"]:
                continue
            if b["bps"] < _BLEED_BPS <= hold[lbl]["bps"]:
                flags.append(f"hold-class {lbl} is NET-OF-FEE NEGATIVE ({b['bps']} bps, fee "
                             f"${b['fee']}) while its fee-blind net reads {hold[lbl]['bps']} bps "
                             "-- the logged verdict was an artifact of not charging the trade")
            # FEE INTENSITY is the execution-integrity measure, and it generalises past the churn
            # loop: a carry round-trip bills the futures leg twice (~5 bps taker each), so a class
            # paying many multiples of that is being charged for fills the book never intended,
            # whatever the mechanism. A sign test alone misses this -- the 07-28 fire landed on a
            # class ALREADY flagged bleeding, so it moved -42 -> -635 bps in silence.
            fbps = 1e4 * b["fee"] / b["notional"]
            if fbps > _FEE_BPS_MAX:
                flags.append(f"FEE INTENSITY hold-class {lbl}: ${b['fee']} on ${b['notional']:.0f} "
                             f"= {fbps:.0f} bps, {fbps / _FEE_RT_BPS:.0f}x the ~{_FEE_RT_BPS:.0f} "
                             "bps a futures round-trip should bill -- the venue is charging for "
                             "fills this book did not intend (churn-loop fingerprint; see "
                             "max_audit check_close_retry_loop)")
        share = fee_attr.get("unattributed_share")
        if share is not None and share > 0.25 and fee_attr["venue_commission"] > 25.0:
            flags.append(f"UNATTRIBUTED COMMISSION {fee_attr['unattributed']} of "
                         f"{fee_attr['venue_commission']} ({share:.0%}) matches no logged "
                         "round-trip -- the venue is billing against no position this book "
                         "believes it opened")

    # funding-at-open: the class that ate ~80% of gross profit pre-gate
    base = [x for x in closes if abs(float(x.get("funding_rate") or 0) - _BASELINE) < 1e-9]
    bn = sum(float(x.get("net") or 0) for x in base)
    bnot = sum(float(x.get("notional") or 0) for x in base)
    # entry-gate regression check, R0057 contract: a post-gate open is a regression iff its
    # funding could NOT beat the symbol's modelled round-trip over the minimum hold. Baseline
    # funding on a tight measured major legitimately passes; baseline funding on an unmeasured
    # or expensive book cannot.
    try:
        _cost_model = json.loads(_COST_MODEL.read_text("utf-8")) if _COST_MODEL.exists() else {}
    except (OSError, json.JSONDecodeError):
        _cost_model = {}
    # Same rolling window as every other flag in this file: the question is "is the gate
    # filtering NOW", and judging pre-R0057 opens against today's contract and today's cost
    # model is anachronistic on both axes (the 7 opens of 07-26/27 passed the gate as it stood
    # then). Within 14d, model-at-read ~= model-at-open; the exact close is the executor
    # stamping its gate arithmetic on the open row (rowed, behind the executor-lineage merge).
    _gate_cutoff = max(_GATE_DATE, cutoff)
    post_gate_base = []
    n_gate_window_opens = 0
    for x in trades:
        if x.get("event") != "open" or str(x.get("opened", "")) <= _gate_cutoff:
            continue
        n_gate_window_opens += 1
        f_open = float(x.get("funding_rate") or 0)
        rt = _gate_rt_bps(str(x.get("symbol")), float(x.get("notional") or 500.0), _cost_model)
        if f_open * 1e4 * _GATE_PERIODS <= rt:
            post_gate_base.append(x)
    if post_gate_base:
        flags.append(f"ENTRY-GATE REGRESSION: {len(post_gate_base)} open(s) whose funding could "
                     f"not beat the symbol's modelled round-trip over the minimum hold "
                     f"(R0057 per-symbol contract) -- gate is not filtering")

    per_sym: dict[str, list[float]] = defaultdict(lambda: [0, 0.0, 0.0])
    for x in closes:
        s = str(x.get("symbol"))
        per_sym[s][0] += 1
        per_sym[s][1] += float(x.get("net") or 0)
        per_sym[s][2] += float(x.get("notional") or 0)
    worst = sorted(((s, n, net, 1e4 * net / nt if nt else 0.0)
                    for s, (n, net, nt) in per_sym.items() if n >= 5),
                   key=lambda r: r[2])[:5]
    for s, n, net, bps in worst:
        if net < -25.0 and bps < -20.0:
            flags.append(f"symbol {s} structurally bleeding: ${net:.0f} over {n} trades "
                         f"({bps:.0f} bps)")

    # THE DENYLIST'S EVIDENCE -- ALL-TIME, never windowed. Same bar as the executor's fence
    # (n >= 5 closes, realised <= -20 bps), computed over the FULL closed-trade record.
    #
    # WHY THIS KEY EXISTS SEPARATELY FROM `worst_symbols`: that list is 14d-ROLLING, which is
    # correct for the pager (an all-history flag re-pages forever after the fix works) and
    # exactly wrong for a fence. A symbol that PROVED it loses money does not stop having proved
    # it because a fortnight passed, so a windowed denylist rehabilitates every proven loser on a
    # fortnightly cycle and the desk re-buys the lesson it already paid for.
    #
    # RESTORED 2026-08-13 (R0158 sibling). This split shipped 2026-08-05 in a0026d98 and was
    # REVERTED by merge 8b981a50, which kept tests/execution/test_carry_entry_gate.py -- the file
    # asserting the fence reads this key -- while dropping the producer and reader that made it
    # true. The tests went red and stayed red, so the merge-union defect was visible the whole
    # time and read as an ordinary red suite. Measured at restoration: the rolling window held
    # 4 of 253 all-time closes and named ZERO bleeders, while SIX qualified all-time -- NOMUSDT
    # (-149.4 bps, the 2026-07-13 dead-man symbol), COMPUSDT (-106.4), ONEUSDT (-92.4),
    # 1000CATUSDT (-74.6), BNBUSDT (-65.8) and PEOPLEUSDT (-62.4). The book is paused on a
    # drawdown, which is WHY the window is nearly empty: the fence protects nothing at exactly
    # the moment a re-arm would re-open the names that caused the pause.
    #
    # The path back is a RE-MEASUREMENT that moves the all-time verdict, never the calendar.
    all_sym: dict[str, list[float]] = defaultdict(lambda: [0, 0.0, 0.0])
    for x in all_closes:
        s = str(x.get("symbol"))
        all_sym[s][0] += 1
        all_sym[s][1] += float(x.get("net") or 0)
        all_sym[s][2] += float(x.get("notional") or 0)
    bleeding: list[dict[str, Any]] = sorted(
        ({"symbol": s, "n": int(n), "net": round(net, 2),
          "bps": round(1e4 * net / nt, 1)}
         for s, (n, net, nt) in all_sym.items()
         if n >= _DENY_MIN_N and nt and 1e4 * net / nt <= _DENY_BPS),
        key=lambda r: float(r["bps"]))   # worst first, so a reader sees the sharpest evidence

    # MAKER FILL-RATE ON THE PRIMARY BOOK (2026-07-26). The patient-maker opens shipped 07-24 to
    # cut a fee bill running ~2.5x the funding harvest, and the desk carried a standing duty to
    # "re-measure weekly until >60%" -- with NO instrument: _execute_pair returned the fill mode
    # and _log_trade threw it away, and the only `maker_share` in the repo belongs to a different
    # organ (run_crypto_testnet) whose web/binance.json last updated 2026-06-28. A fix whose effect
    # cannot be measured is a fix on trust. Legs are counted independently: a pair can rest maker
    # on spot and cross taker on futures, and that asymmetry is exactly the cost detail we need.
    #
    # R0064 (2026-08-05): the denominator used to be EVERY truthy mode string, which swept in
    # `already-flat` -- the mode `_close_goal_state` writes when the venue says the leg is already
    # flat. No order was placed and no fill happened, so such a leg cannot be maker; counting it
    # scored it non-maker and pushed `maker_share` under the 0.60 target on arithmetic alone. That
    # is a FALSE INTEGRITY FLAG: the desk gets paged about maker conversion by legs that never
    # traded. The vocabulary now lives in `libs.execution.leg_modes`, shared with
    # scripts/fill_quality_monitor so both organs measure the same tape the same way (R0324).
    # Exclusion is limited to the no-order markers: every mode that DID place an order still counts
    # against the target, so this can only remove phantom legs, never soften the bar.
    legs = [m for x in trades for m in (x.get("spot_mode"), x.get("fut_mode"))
            if leg_modes.placed_order(m)]
    maker = {
        "n_legs": len(legs),
        "maker_share": (round(sum(leg_modes.is_maker(m) for m in legs) / len(legs), 3)
                        if legs else None),
        "spot": _leg_share(trades, "spot_mode"),
        "fut": _leg_share(trades, "fut_mode"),
        "target": 0.60,
        "note": ("instrumented 2026-07-26; records written before that carry no mode, so n_legs "
                 "climbs from 0 as new fills land -- a null share is thin data, not a regression. "
                 "n_legs counts only legs that PLACED AN ORDER: no-order legs "
                 f"{sorted(leg_modes.NO_ORDER_MODES)} are excluded from the denominator (R0064)"),
    }
    # Narrowed out of the heterogeneous dict before comparing: `maker` holds str values too, so
    # mypy reads these operands as `str | float | None` and rejects the ordering comparisons.
    _share, _legs = maker["maker_share"], maker["n_legs"]
    if isinstance(_share, float) and isinstance(_legs, int) and _legs >= 20 and _share < 0.60:
        flags.append(f"maker fill-rate {_share:.1%} below the 60% target over "
                     f"{_legs} legs -- patient-maker opens are not converting; fees are "
                     "the dominant carry cost, so this is the primary unit-economics lever")

    if tape.get("buffer_squeezing_window"):
        flags.append(f"trade-log buffer holds {tape['buffer_days']}d < the {_WINDOW_D}d forensics "
                     "window -- this analysis is now silently losing its own tail; the permanent "
                     "tape (data/moat/execution_tape/) has the full history, read from there")

    out = {
        "updated": datetime.now(tz=UTC).isoformat(),
        "n_closes": len(closes),
        "hold_buckets": hold,
        # fee-blind (above) vs venue-truth (below) -- see _fee_attribution
        "hold_buckets_net_of_fees": hold_nof,
        "fee_attribution": fee_attr,
        "baseline_funding_class": {"n": len(base), "net": round(bn, 2),
                                   "bps": round(1e4 * bn / bnot, 2) if bnot else 0.0},
        # numerator AND denominator (L1.57): 0 violations over 0 window opens is "no evidence"
        # (paused book), not "gate healthy" -- readers must be able to tell them apart
        "post_gate_baseline_opens": len(post_gate_base),
        "post_gate_opens_examined": n_gate_window_opens,
        "maker_fill": maker,
        "execution_tape": tape,
        "worst_symbols": [{"symbol": s, "n": n, "net": round(net, 2), "bps": round(bps, 1)}
                          for s, n, net, bps in worst],
        "bleeding_symbols": bleeding,
        "bleeding_basis": {"window": "all-time", "n_closes": len(all_closes),
                           "min_n": _DENY_MIN_N, "bleed_bps": _DENY_BPS,
                           "note": "the executor's structural-bleed denylist reads THIS key; "
                                   "worst_symbols is 14d-rolling and is for alerts only"},
        "flags": flags,
        "origin": "recursion rule 2026-07-22: mechanization of the principal-supplied probes "
                  "that found gaps #42/#43/#34",
    }
    _OUT.parent.mkdir(parents=True, exist_ok=True)
    _OUT.write_text(json.dumps(out, indent=1), "utf-8")
    # same doc plus a "written" stamp: a checkout must be able to cite WHEN the evidence was
    # captured, not merely that it exists.
    #
    # ONLY FROM THE HOST THAT HOLDS THE TRADES (GAP 113). `data/cashcarry_trades.json` is
    # gitignored, so on any other box this analysis runs over nothing and produces a perfectly
    # well-formed document reporting `n_closes: 0` with every net at zero -- then commits it over
    # the real one. Measured 2026-08-13: a `pytest` run did exactly that, replacing 27 closes with
    # zero. That is WS-005 written into a TRACKED artifact by merely observing the system, and it
    # is undetectable afterwards: an empty forensics doc and a desk that closed nothing are the
    # same bytes.
    #
    # The untracked `_OUT` above is written unconditionally and deliberately -- it is this host's
    # own runtime state, the executor's denylist reads it, and a stale denylist is the dangerous
    # direction. What is guarded is only the shared, committed copy.
    owns, why = is_owning_host()
    if owns:
        _TRACKED.parent.mkdir(parents=True, exist_ok=True)
        _TRACKED.write_text(
            json.dumps({**out, "written": datetime.now(tz=UTC).isoformat()}, indent=1), "utf-8")
    else:
        print(f"trade forensics: tracked copy NOT written -- {why}")
    print(f"trade forensics: {len(closes)} closes | flags: {len(flags)}")
    for fl in flags:
        print("  !", fl)


if __name__ == "__main__":
    main()

```
