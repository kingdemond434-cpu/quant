# AUDIT SHARD 1/24 -- seat x-ai/grok-4.6

You are reviewing SOURCE CODE, not a summary. Previous panels received a 13,185-char self-description and never saw the code; that is why this exists.

- TIER 1 (money path) is included IN FULL and is sent to every seat: 44 files. A defect here costs money.
- TIER 2 is YOUR SHARD ALONE: 9 files. No other seat sees these, so anything you miss here is missed entirely.
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

### libs\ops\completion.py
```python
"""RAN IS NOT COMPLETED, and this desk has spent months reading the first as the second.

THE CASE THAT NAMES THE CLASS, measured on this tree 2026-09-10. `pf_allocator` is the growth
sizer: it solves posterior E[log W] for the heat every sleeve should risk, and nothing else on
the desk answers "how big should this trade be" with an estimate of growth. It was armed
(`data/PF_ALLOCATOR_ARMED`, 2026-09-04). It had an hourly leg. `decision_core.allocator_heat`
read its artifact and `promoted_lot(from_book=True)` sized from its fractions. Every dashboard
panel that watches it read healthy.

    $ python desks/mt5/research/pf_allocator.py --mode normal
    REFUSING to project a portfolio without .../reports/hunt12_partial.json
    exit 1

`reports/pf_allocation.json` HAD NEVER EXISTED. For six days the leg ran on the hour, exited 1,
and the desk sized every sleeve off the authority ramp -- a count of closed trades with no
estimate of growth in it -- while reporting the allocator as armed and wired.

NOT ONE OF THE FENCES THIS DESK ALREADY OWNS COULD HAVE CAUGHT IT, and each was close:

    check_producer_schedules   asks "is there a clock?"           -- there was
    capability_graph           asks "does a consumer exist?"      -- one did
    module_rent                asks "is this node priced?"        -- it was
    compute_ledger             asks "what did the hour cost?"     -- it recorded the cost
    stall_watch                asks "did the task start?"         -- it started

Every one of them answered a question about ACTIVITY. The question none of them asked is whether
the thing the activity exists to produce is now on disk. That is the whole of this module.

WHAT IT JOINS, all of it already written down somewhere else -- this adds no registry:

    data/sync_marker.json        every leg of the last cycle and what it returned
    data/compute_ledger.jsonl    per-run history: when, what outcome, how expensive
    capability_graph.NODES       what each component DECLARES it writes, reads, and how fresh
                                 an authority node's inputs must be
    the filesystem               whether that declared artifact is actually there, and how old

THE VERDICTS, one per leg, in the order they are decided:

    UNDECLARED   the leg has no node in the capability graph, so NOTHING KNOWS what it should
                 have produced. This is the state pf_allocator's input was in and it is counted
                 as debt, never skipped: an undeclared leg cannot be judged by any of the rules
                 below, so it is permanently invisible to all of them.
    NEVER_RAN    no row in the ledger window and no key in the marker
    FAILING      the last observation failed -- a non-zero exit, a MISSING script, a recorded
                 exception, or a ledger outcome that is not ok
    NO_OUTPUT    the last run reported success AND a declared write is not on disk. THE
                 pf_allocator CLASS. A leg that returns 0 and produces nothing is the single
                 most expensive shape of failure here, because every downstream reader treats
                 the absence as "not yet" rather than "broken".
    STALE        the declared write exists but is older than the node's own freshness SLA
    UNREAD       fresh output that no node reads: work the desk pays for and never spends
    COMPLETED    ran, wrote, fresh, and something reads it

AND THE STREAK, because "repairs lack verified closure" is its own defect. A leg that has been
FAILING or NO_OUTPUT for N consecutive recorded runs is not a blip, and the count is what
separates "it failed once at 03:00" from "it has failed every hour since Tuesday". A repair is
closed by the streak returning to zero, never by a command having exited 0.

ABSENCE IS JUDGED, NEVER ASSUMED (L1.28a). On a two-machine desk an absent file has three
meanings, not two, and this uses the rule `microstructure_census.artifact_state` already
established: a path under a STATE_PREFIX that is NOT gitignored and is absent has never been
produced on ANY machine, because the box commits and pushes what it writes there; a gitignored
path says nothing from a research checkout and is reported UNKNOWN_HERE rather than failed.

WHAT GATES CI AND WHAT GATES THE BOX, kept apart on purpose. The STATIC findings -- a leg with no
node, a declared write nothing reads -- are true in any checkout and fail `check_completion.py`.
The RUNTIME findings -- NO_OUTPUT, STALE, FAILING -- need the machine that runs the clock, so
they are published to `reports/COMPLETION.json` for the issue board and fail only where the
artifact's absence is real. A gate that is red on every developer checkout is a gate nobody
reads, which is the failure this module exists to end, not to repeat.

    python -m libs.ops.completion            # the report
    python -m libs.ops.completion --json
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
DESK = ROOT / "desks" / "mt5"

MARKER = DESK / "data" / "sync_marker.json"
LEDGER = DESK / "data" / "compute_ledger.jsonl"
OUT_REL = "desks/mt5/reports/COMPLETION.json"

#: The cycles whose legs are judged. A leg is `_costed("name", ...)` in one of these.
CYCLES = ("desks/mt5/research/hourly_cycle.py", "desks/mt5/research/daily_cycle.py")

_LEG_RE = re.compile(r'_costed\(\s*"([^"]+)"')

#: How many recorded runs back the streak is counted over. Long enough that an organ on a daily
#: clock still shows several observations, short enough that a fix shows up as a falling streak
#: within a day rather than being averaged out by a fortnight of history.
STREAK_WINDOW = 200

#: Default freshness when a node declares none. A leg on the hourly cycle whose artifact is a day
#: old has missed twenty-three passes; anything longer would let a dead producer read healthy.
DEFAULT_SLA_S = 26 * 3600

UNDECLARED = "UNDECLARED"
NEVER_RAN = "NEVER_RAN"
FAILING = "FAILING"
NO_OUTPUT = "NO_OUTPUT"
STALE = "STALE"
UNREAD = "UNREAD"
COMPLETED = "COMPLETED"
UNKNOWN_HERE = "UNKNOWN_HERE"

#: The verdicts that mean the leg is not delivering. `UNKNOWN_HERE` is deliberately absent: it is
#: the honest answer of a checkout that cannot see the box, not a finding.
BREACH = (UNDECLARED, NEVER_RAN, FAILING, NO_OUTPUT, STALE, UNREAD)

#: Findings true in ANY checkout, so they can fail CI. The rest need the machine with the clock.
STATIC = (UNDECLARED, UNREAD)


@dataclass
class Leg:
    name: str
    cycle: str
    verdict: str = UNDECLARED
    why: str = ""
    node: str | None = None
    writes: tuple[str, ...] = ()
    readers: tuple[str, ...] = ()
    authority: tuple[str, ...] = ()
    last_at: str | None = None
    last_outcome: str | None = None
    streak: int = 0
    artifacts: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return dict(vars(self))


# ------------------------------------------------------------------ the four sources


def legs(root: Path | None = None) -> dict[str, str]:
    """Every `_costed` leg in the cycles -> the cycle it belongs to.

    READ FROM THE CODE, NEVER A LIST. A hand-kept roster of legs is right on the day it is
    written and silently wrong afterwards -- which is how fifteen legs came to sit in the hourly
    cycle with no entry in the layer registry, nine of them added the same day the registry's own
    fence was written.
    """
    root = Path(root or ROOT)
    out: dict[str, str] = {}
    for rel in CYCLES:
        p = root / Path(*rel.split("/"))
        if not p.is_file():
            continue
        for name in _LEG_RE.findall(p.read_text(encoding="utf-8", errors="replace")):
            out.setdefault(name, rel)
    return out


def _ignored(root: Path, rel: str) -> bool:
    """`git check-ignore`, which is the only authority on this. A hand-parsed .gitignore gets
    negation patterns wrong, and `!desks/mt5/data/sleeves.json` is exactly such a pattern."""
    try:
        r = subprocess.run(["git", "check-ignore", "-q", rel], cwd=str(root),
                           capture_output=True, timeout=20, check=False)
    except (OSError, subprocess.SubprocessError):
        return True                     # cannot tell -> never claim NEVER_PRODUCED
    return r.returncode == 0


def artifact_state(root: Path, rel: str, now: datetime | None = None) -> dict[str, Any]:
    """PRESENT (with its age), UNKNOWN_HERE, or NEVER_PRODUCED -- and never a guess between them.

    The rule is `microstructure_census.artifact_state`'s, restated for a path that carries an
    age: `desks/mt5/data/` is a STATE_PREFIX the box commits and pushes, so an absent path there
    that is not gitignored has never been written by any machine. A gitignored path (everything
    under `reports/`) is invisible from a research checkout and says nothing either way.
    """
    p = root / Path(*rel.split("/"))
    if p.exists():
        age = ((now or datetime.now(UTC)).timestamp() - p.stat().st_mtime)
        return {"path": rel, "state": "PRESENT", "age_s": round(max(0.0, age), 1),
                "bytes": p.stat().st_size}
    if _ignored(root, rel):
        return {"path": rel, "state": UNKNOWN_HERE,
                "why": ("gitignored: its absence in this checkout is not evidence. The box may "
                        "hold it, and only the box can judge this line")}
    return {"path": rel, "state": "NEVER_PRODUCED",
            "why": ("absent, not gitignored, under a prefix the box commits and pushes -- so had "
                    "any machine ever written it, the next adopt would have carried it here")}


def marker(path: Path | None = None) -> dict[str, Any]:
    """The last cycle's per-leg results, or {} when the marker is unreadable."""
    try:
        doc = json.loads((path or MARKER).read_text("utf-8"))
    except (OSError, ValueError):
        return {}
    return doc if isinstance(doc, dict) else {}


def ledger_runs(path: Path | None = None,
                window: int = STREAK_WINDOW) -> dict[str, list[dict[str, Any]]]:
    """Per leg, its most recent recorded runs, oldest first, from the append-only ledger."""
    rows: list[dict[str, Any]] = []
    try:
        with open(path or LEDGER, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                except ValueError:
                    continue
                if isinstance(row, dict) and row.get("run"):
                    rows.append(row)
    except OSError:
        return {}
    out: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        out.setdefault(str(row["run"]), []).append(row)
    return {k: v[-window:] for k, v in out.items()}


def _nodes() -> dict[str, Any]:
    """The capability graph's nodes by name, or {} when it cannot be imported.

    NOT A FALLBACK ROSTER. Without the graph nothing here knows what a leg should produce, and
    the whole report says so rather than judging legs against nothing.
    """
    try:
        from libs.ops.capability_graph import NODES
    except Exception:
        return {}
    return {n.name: n for n in NODES}


# ------------------------------------------------------------------ the verdict


def _failed(result: Any) -> str | None:
    """Why the last observation counts as a failure, or None. Reads the shapes the cycles
    actually write: an exit code, a MISSING status, a recorded exception, a timeout."""
    if not isinstance(result, dict):
        return None
    if result.get("error"):
        return f"the leg raised: {result['error']}"
    status = str(result.get("status") or "")
    if status in ("MISSING", "FAILED", "ERROR"):
        return f"status {status}: {result.get('why') or result.get('note') or ''}".strip()
    code = result.get("exit_code")
    if code is None and result.get("timeout_s"):
        return f"stopped at its {result['timeout_s']}s budget before finishing"
    if isinstance(code, int) and code != 0:
        tail = str(result.get("tail") or "").strip().replace("\n", " ")[-160:]
        return f"exit {code}{': ' + tail if tail else ''}"
    return None


def _streak(runs: list[dict[str, Any]]) -> int:
    """Consecutive non-ok recorded runs, counting back from the most recent.

    THE COUNT IS THE DIFFERENCE BETWEEN A BLIP AND AN OUTAGE, and it is what closes a repair: a
    fix is verified when this returns to zero, not when a command exits 0.
    """
    n = 0
    for row in reversed(runs):
        if str(row.get("outcome") or "ok") == "ok":
            break
        n += 1
    return n


def judge(root: Path | None = None, now: datetime | None = None,
          marker_path: Path | None = None, ledger_path: Path | None = None) -> list[Leg]:
    """One verdict per leg of the two cycles."""
    root = Path(root or ROOT)
    now = now or datetime.now(UTC)
    nodes = _nodes()
    mk = marker(marker_path)
    runs = ledger_runs(ledger_path)
    readers: dict[str, list[str]] = {}
    for node in nodes.values():
        for rel in getattr(node, "reads", ()):
            readers.setdefault(rel, []).append(node.name)

    out: list[Leg] = []
    for name, cycle in sorted(legs(root).items()):
        leg = Leg(name=name, cycle=cycle)
        mine = runs.get(name) or []
        if mine:
            leg.last_at = str(mine[-1].get("at") or "")
            leg.last_outcome = str(mine[-1].get("outcome") or "")
            leg.streak = _streak(mine)

        node = nodes.get(name)
        if node is None:
            leg.verdict = UNDECLARED
            leg.why = ("no node in libs/ops/capability_graph declares what this leg writes, so "
                       "nothing can tell a pass that produced its artifact from one that "
                       "produced nothing. Every check below is blind to it")
            out.append(leg)
            continue

        leg.node = node.name
        leg.writes = tuple(getattr(node, "writes", ()))
        leg.authority = tuple(getattr(node, "authority", ()))
        leg.readers = tuple(sorted({r for w in leg.writes for r in readers.get(w, [])
                                    if r != node.name}))

        if not mine and name not in mk:
            leg.verdict = NEVER_RAN
            leg.why = (f"no row in {LEDGER.name} and no key in {MARKER.name}: this leg is on a "
                       f"clock and there is no record of it ever completing a pass")
            out.append(leg)
            continue

        why = _failed(mk.get(name))
        if why is None and leg.last_outcome and leg.last_outcome != "ok":
            why = f"last recorded outcome {leg.last_outcome!r}"
        if why is not None:
            leg.verdict, leg.why = FAILING, why
            if leg.streak > 1:
                leg.why += (f" -- and it has failed {leg.streak} recorded runs in a row, so this "
                            f"is an outage, not a blip")
            out.append(leg)
            continue

        leg.artifacts = [artifact_state(root, w, now) for w in leg.writes]
        never = [a for a in leg.artifacts if a["state"] == "NEVER_PRODUCED"]
        if never:
            leg.verdict = NO_OUTPUT
            leg.why = (f"the last run reported success and {len(never)} declared artifact(s) have "
                       f"never been produced on any machine: {', '.join(a['path'] for a in never)}"
                       f". A leg that returns 0 and writes nothing reads downstream as 'not yet' "
                       f"rather than 'broken', which is how pf_allocator went six days unnoticed")
            out.append(leg)
            continue

        present = [a for a in leg.artifacts if a["state"] == "PRESENT"]
        if not present:
            leg.verdict = UNKNOWN_HERE
            leg.why = ("every declared artifact is gitignored and absent here, so this checkout "
                       "cannot judge the leg. Read it on the box")
            out.append(leg)
            continue

        sla = getattr(node, "freshness_s", {}) or {}
        old = [a for a in present
               if a["age_s"] > float(sla.get(a["path"], DEFAULT_SLA_S))]
        if old:
            worst = max(old, key=lambda a: a["age_s"])
            leg.verdict = STALE
            leg.why = (f"{worst['path']} is {worst['age_s'] / 3600:.1f}h old against an SLA of "
                       f"{float(sla.get(worst['path'], DEFAULT_SLA_S)) / 3600:.1f}h: the leg is "
                       f"running and its output is not moving")
            out.append(leg)
            continue

        if leg.writes and not leg.readers:
            leg.verdict = UNREAD
            leg.why = ("the output is fresh and no other node reads it: compute the desk pays "
                       "for every pass and never spends")
            out.append(leg)
            continue

        leg.verdict = COMPLETED
        leg.why = (f"ran, wrote {len(present)} artifact(s), inside SLA, and "
                   f"{len(leg.readers)} node(s) read them")
        out.append(leg)
    return out


def report(root: Path | None = None, now: datetime | None = None,
           **kw: Any) -> dict[str, Any]:
    root = Path(root or ROOT)
    rows = judge(root, now, **kw)
    by: dict[str, int] = {}
    for leg in rows:
        by[leg.verdict] = by.get(leg.verdict, 0) + 1
    static = [x.to_dict() for x in rows if x.verdict in STATIC]
    runtime = [x.to_dict() for x in rows
               if x.verdict in BREACH and x.verdict not in STATIC]
    return {
        "at": (now or datetime.now(UTC)).isoformat(timespec="seconds"),
        "n_legs": len(rows),
        "by_verdict": dict(sorted(by.items())),
        "graph_available": bool(_nodes()),
        "static_findings": static,
        "runtime_findings": runtime,
        "authority_breaches": [x.to_dict() for x in rows
                               if x.authority and x.verdict in BREACH],
        "legs": [x.to_dict() for x in rows],
        "rule": (
            "RAN IS NOT COMPLETED. A leg completes when its declared artifact is on disk, inside "
            "its freshness SLA, and something reads it. Every fence this desk owned asked "
            "whether a component was ACTIVE; none asked whether the thing it exists to produce "
            "is there. pf_allocator ran hourly, exited 1, and sized the whole book off the "
            "authority ramp for six days while every panel read healthy."),
        "closure": (
            "A repair is closed when the streak returns to zero, never when a command exits 0. "
            "`streak` counts consecutive non-ok recorded runs, so a fix that did not take shows "
            "as a number that keeps climbing rather than as a green run somebody remembers."),
    }


def render(doc: dict[str, Any]) -> str:
    lines = [f"COMPLETION  {doc['n_legs']} legs: " +
             ", ".join(f"{k} {v}" for k, v in doc["by_verdict"].items())]
    if not doc["graph_available"]:
        lines.append("  capability_graph UNIMPORTABLE -- no leg could be judged against a "
                     "declaration; every verdict below is UNDECLARED for that reason alone")
    for key, title in (("authority_breaches", "AUTHORITY"), ("static_findings", "STATIC"),
                       ("runtime_findings", "RUNTIME")):
        rows = doc[key]
        if not rows:
            continue
        lines.append(f"  {title} ({len(rows)}):")
        for r in rows[:20]:
            streak = f" x{r['streak']}" if r.get("streak", 0) > 1 else ""
            lines.append(f"    {r['verdict']:<11}{streak:<5} {r['name']}  {r['why'][:110]}")
        if len(rows) > 20:
            lines.append(f"    ... and {len(rows) - 20} more")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="whether a leg that ran actually completed")
    ap.add_argument("--root", default=str(ROOT))
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    root = Path(args.root)
    doc = report(root)
    out = root / Path(*OUT_REL.split("/"))
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=1, default=str), encoding="utf-8")
    print(json.dumps(doc, indent=1, default=str) if args.json else render(doc))
    print(f"written: {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

```

### libs\ops\value_staleness.py
```python
"""A LIVE PRODUCER TALKING TO A DEAF CONSUMER (L1.66) -- the value half of code staleness.

``check_stale_daemons`` (``max_audit.py:893``) asks one question of every long-lived process on
this desk: **is the running CODE the committed code?** It walks the transitive import closure,
compares source mtime to process start, and has measured 5 of 18 daemons stale. It is a good
detector and it answers half the question. Nothing has ever asked the other half: **are the
running VALUES the values on disk?**

THE DEFECT CLASS. A module-scope read executes exactly once, when python first imports the
module::

    _VENUE_MIN_NOTIONAL_USD = max(venue_min_notional_usd() or 10.0, 10.0)   # runs at import

Every later reference is to a value frozen at process start. Edit the artifact, and the file on
disk and the value in memory disagree for the entire life of the process -- silently, with no
exception, no log line, and no gauge anywhere going amber. The daemon is not running stale code;
it is running current code over a stale number.

WHY THREE EXISTING INSTRUMENTS ARE EACH BLIND TO IT BY CONSTRUCTION, WHICH IS WHY IT SURVIVED:

  * ``check_stale_daemons`` compares SOURCE mtime to process start. The source here is
    current -- often committed months ago and never touched again. The line is not stale; the
    value it produced once is. Code staleness and value staleness are independent, and the
    detector for one cannot see the other.
  * ``check_freshness`` (L1.44) audits ``data/freshness_contracts.jsonl``, a registry that
    BUILDS ITSELF FROM READS -- its proudest property and, here, precisely the blindness. A
    value read once at import emits one contract row that is byte-identical to the row emitted
    by a healthy per-tick read. *A registry that builds itself from reads cannot see a value
    that is read once and never read again.*
  * ``input_provenance`` (L1.55) asks whether MY inputs were present when I wrote my artifact.
    For a frozen read the answer is always yes: the input was present, at import, and was read
    correctly. The artifact is fine. The PRODUCER is fine. The consumer is deaf.

Every artifact-side and producer-side gauge on this desk reads green on this defect. That is
what makes it a distinct blindness rather than a variation on L1.44: the lens is INVERTED. The
desk has spent five laws on frozen producers feeding live consumers, and none on a live producer
talking to a consumer that stopped listening at import.

THE DESK'S OWN POSITIVE CONTROL, AND WHY IT EXISTS. ``run_cashcarry_executor._live_params``
(``:2398``, called at ``:2527`` INSIDE ``while forever``) re-reads ``data/cashcarry_config.json``
every rebalance: *"Changing a param used to require the flatten+restart the 2026-07-10 churn fix
needed; now just write the JSON and the running loop picks it up next cycle."* That is the
correct pattern, it was built by hand after an incident, it is on the money path, and NOTHING
verifies the pattern holds anywhere else. This module is that verification.

WHAT IT MEASURES, STATED NARROWLY, BECAUSE OVERSTATING IS HOW A FENCE GETS SWITCHED OFF (L1.43).
This fence measures **EXPOSURE, NOT DAMAGE**, and the distinction is load-bearing. A frozen read
whose artifact has changed since process start means the desk **CANNOT PROVE** the in-memory
value matches disk -- not that it provably differs. Measured on this box while building: all
three recorders freeze ``_SYMBOLS = _universe()`` from ``data/cashcarry_positions.json``, a state
file rewritten continuously, so an mtime test calls all three STALE -- while a set comparison of
the recomputed universe against the symbols actually receiving tape showed **zero difference**.
Reporting that as damage would be a false alarm three times over on the first run, and a detector
that cries wolf gets acked into silence (R0356, and L1.37 in terms).

So the verdict vocabulary says exactly what is known:

  FROZEN-STALE       the input changed after this process started. The in-memory value is
                     UNVERIFIABLE from outside the process. This is the finding.
  FROZEN-CURRENT     the input has not changed since start. Exposed, not yet bitten.
  REFRESHED          the import-time binding is a SEED -- the module re-runs its producer inside
                     a function body, so a live re-read path exists. Not a defect; the evidence
                     is published as a line number so the cadence claim can be checked.
  FROZEN-UNRESOLVED  the read is real but its artifact cannot be resolved statically. NEVER
                     silently dropped -- the first version of this analyser dropped exactly
                     these and reported a clean zero (see THE INSTRUMENT CAME FIRST, below).
  EXEMPT             tagged ``# frozen-ok: <reason>`` -- reported, never hidden.

THE REPAIR IS UPWARD, NEVER DOWNWARD (L1.49). The fix for a FROZEN-STALE pair is to move the
read inside the function that consumes it -- the ``_live_params`` shape -- after which the pair
stops being a frozen read and leaves this fence's denominator honestly. The fix is NEVER to
delete the detector, loosen the status, or restart the daemon and call it closed: a restart
re-freezes the same value one tick later.

THE INSTRUMENT CAME FIRST, AND ITS FIRST VERSION WAS WRONG IN THE DESK'S SIGNATURE WAY (L1.25).
The prototype of this analyser reported **0 frozen reads across all 13 live daemons**. Read as a
result that would have been "the class is real but this desk does not have it" -- a null that
retires a search. Run against three sites verified BY HAND minutes earlier, it scored **0 of 3**.
Two bugs, both worth naming because both are classes rather than typos:

  1. Reading functions were resolved only WITHIN the module under analysis. The dominant real
     shape is ``from libs.x import f`` at the top and ``_V = f()`` below, so the analyser was
     blind to the majority case. Resolution is now transitive across repo modules, exactly like
     ``_import_closure``.
  2. A frozen read whose artifact path could not be resolved was **silently dropped** -- the
     ``continue`` that makes "I could not tell" and "there is nothing here" byte-identical. That
     is WS-005, this desk's most-repeated defect class, committed by the instrument built to
     detect a cousin of it. Unresolvable reads are now a COUNTED status.

ANTI-TIMIDITY READING, THE ENTIRE PURPOSE (L1.28, required of every restraint clause). This is a
MEASUREMENT duty and a SCOPE EXPANSION. It lifts nothing, sizes nothing, promotes nothing, opens
no gate, loosens no statistical bar, and has NO VOCABULARY for changing any value it reads or for
turning a failing verdict into a passing one. Its whole effect is to make "this daemon's config
is live" distinguishable from "this daemon last read its config at boot and nobody has checked
since" -- byte-identical on this desk until now, and only one of them is evidence. Every verdict
it emits argues for MORE control surface: making "edit the JSON" a reliable desk-wide actuator is
the precondition for L1.28c's event-driven cadences and for retuning anything without a
flatten+restart.
"""

from __future__ import annotations

import ast
import os
import re
import subprocess
import time
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path

from libs.ops.box_state import data_root

# -- pair-level verdicts -------------------------------------------------------------------
FROZEN_STALE = "FROZEN-STALE"
FROZEN_CURRENT = "FROZEN-CURRENT"
FROZEN_UNRESOLVED = "FROZEN-UNRESOLVED"
REFRESHED = "REFRESHED"
SOURCE_DRIFTED = "SOURCE-DRIFTED"
EXEMPT = "EXEMPT"

# -- report-level verdicts -----------------------------------------------------------------
OK = "OK"
UNVERIFIABLE = "UNVERIFIABLE"          # >=1 FROZEN-STALE pair
UNRESOLVED = "UNRESOLVED"              # >=1 read we could not resolve; never a clean pass
NO_DAEMONS_HERE = "NO-DAEMONS-HERE"    # honest declared refusal: nothing of ours is running
UNMEASURED = "UNMEASURED"              # daemons running, nothing examined -- never OK (L1.28a)

#: Only a fully measured, fully current desk passes. Every refusal status is structurally absent
#: from this set, which is what the wiring test pins.
PASSING = frozenset({OK})

#: Attribute/name calls that constitute reading something off disk. Deliberately broad: a false
#: POSITIVE here costs one line in a report that a human reads, while a false NEGATIVE is the
#: defect this module exists to end and is invisible by construction.
READ_VERBS = frozenset({
    "read_text", "read_bytes", "read_json", "read_csv", "read_parquet", "read_fresh",
    "load", "loads", "open", "iterdir", "glob", "rglob", "load_policy", "read",
})

#: A repo-local package whose modules we follow. Mirrors ``max_audit._import_closure`` -- anything
#: outside this ships with the interpreter and cannot change under a running process.
_FIRST_PARTY = frozenset({"libs", "app", "scripts", "api"})

#: ``# frozen-ok: <reason>`` -- the exemption, which MUST carry a reason. A bare tag is not a tag.
#: Mirrors L1.60's ``attrition-ok`` deliberately: exempt sites are REPORTED, never hidden, because
#: an invisible exemption is this defect wearing a comment.
_EXEMPT_TAG = re.compile(r"#\s*frozen-ok:\s*(\S.*)$")

_MAX_DEPTH = 6          # transitive call resolution; cycles are guarded separately
_MIN_UPTIME_H = 1.0     # a just-started process loaded fresh values by definition


@dataclass(frozen=True)
class FrozenRead:
    """One module-scope binding whose value is decided once per process."""

    module: str          # repo-relative
    name: str
    lineno: int
    kind: str            # module-scope | memoized | default-arg
    artifacts: tuple[str, ...] = ()
    exempt_reason: str = ""
    #: Line of a call to this binding's producer from INSIDE a function body -- i.e. a live
    #: re-read path that supersedes the import-time value. 0 when there is none.
    refresh_line: int = 0

    @property
    def resolved(self) -> bool:
        return bool(self.artifacts)


@dataclass(frozen=True)
class Daemon:
    """A live repo process, discovered from the process table -- never from a hand roster."""

    script: str          # repo-relative
    pids: tuple[int, ...]
    started: float
    age_h: float


@dataclass(frozen=True)
class Pair:
    """A (daemon, frozen-read) pair -- the unit this fence counts and grades."""

    daemon: str
    read: FrozenRead
    status: str
    artifact: str = ""
    drift_h: float = 0.0     # hours between process start and the artifact's last change
    why: str = ""

    def as_dict(self) -> dict[str, object]:
        return {
            "daemon": self.daemon, "module": self.read.module, "name": self.read.name,
            "lineno": self.read.lineno, "kind": self.read.kind, "status": self.status,
            "artifact": self.artifact, "drift_h": round(self.drift_h, 2), "why": self.why,
        }


@dataclass
class Report:
    status: str
    pairs: list[Pair] = field(default_factory=list)
    daemons: list[Daemon] = field(default_factory=list)
    basis: str = ""
    root: str = ""
    attempted: int = 0        # L1.60: iterations entered
    skipped: int = 0          # L1.60: iterations abandoned, counted rather than invisible
    notes: list[str] = field(default_factory=list)

    @property
    def n_pairs(self) -> int:
        return len(self.pairs)

    def _n(self, status: str) -> int:
        return sum(1 for p in self.pairs if p.status == status)

    @property
    def n_stale(self) -> int:
        return self._n(FROZEN_STALE)

    @property
    def n_current(self) -> int:
        return self._n(FROZEN_CURRENT)

    @property
    def n_unresolved(self) -> int:
        return self._n(FROZEN_UNRESOLVED)

    @property
    def n_exempt(self) -> int:
        return self._n(EXEMPT)

    @property
    def n_refreshed(self) -> int:
        return self._n(REFRESHED)

    @property
    def n_source_drifted(self) -> int:
        return self._n(SOURCE_DRIFTED)

    def as_dict(self) -> dict[str, object]:
        return {
            "law": "L1.66",
            "status": self.status,
            "measures": ("EXPOSURE, not damage: a FROZEN-STALE pair means the in-memory value "
                         "cannot be PROVEN to match disk, never that it provably differs"),
            "basis": self.basis,
            "root": self.root,
            "n_daemons": len(self.daemons),
            "n_pairs": self.n_pairs,
            "n_frozen_stale": self.n_stale,
            "n_frozen_current": self.n_current,
            "n_frozen_unresolved": self.n_unresolved,
            "n_refreshed": self.n_refreshed,
            "n_source_drifted": self.n_source_drifted,
            "n_exempt": self.n_exempt,
            "attempted": self.attempted,
            "skipped": self.skipped,
            "daemons": [{"script": d.script, "pids": list(d.pids), "age_h": round(d.age_h, 2)}
                        for d in self.daemons],
            "pairs": [p.as_dict() for p in self.pairs],
            "notes": list(self.notes),
            "repair": ("move the read inside the function that consumes it (the "
                       "run_cashcarry_executor._live_params shape); a restart only re-freezes "
                       "the same value one tick later"),
        }


# ---------------------------------------------------------------------------------------------
# process discovery
# ---------------------------------------------------------------------------------------------
def proc_start(pid: int) -> float | None:
    """Wall-clock epoch a process started, or None if it is gone.

    Field 22 of /proc/<pid>/stat in clock ticks since boot, plus /proc/stat's btime. ``comm``
    can contain spaces and parens so the split starts after the LAST ')'. This is a deliberate
    second copy of ``max_audit._proc_start`` rather than an import: ``max_audit`` is a 5000-line
    module whose import has side effects, and a fence that has to import the audit engine to
    read a pid is a fence with an outage waiting in it. The subtlety it encodes -- that
    ``Path("/proc/<pid>").stat().st_mtime`` is NOT a start time and reads ~now for any polled
    process (L0070, a 10-day zero-recall bug) -- is pinned by this module's own test.
    """
    try:
        st = Path(f"/proc/{pid}/stat").read_text("utf-8")
        starttime = int(st[st.rindex(")") + 2:].split()[19])
        btime = next(int(ln.split()[1])
                     for ln in Path("/proc/stat").read_text("utf-8").splitlines()
                     if ln.startswith("btime "))
    except (OSError, ValueError, StopIteration, IndexError):
        return None
    # POSIX-ONLY: reached only after /proc/stat parsed, which cannot happen on
    # Windows. float() makes the Any from sysconf explicit rather than leaked.
    ticks = float(os.sysconf("SC_CLK_TCK"))  # type: ignore[attr-defined]
    return float(btime) + starttime / ticks


def live_daemons(root: Path, *, min_uptime_h: float = _MIN_UPTIME_H,
                 now: float | None = None) -> tuple[list[Daemon], int, int]:
    """Repo scripts currently running, from the PROCESS TABLE, never a hand list.

    Returns (daemons, attempted, skipped). R0668 is the standing reason: three live recorder
    units sat in NO supervision roster, so a roster-driven scan returned an empty plan and a
    recorder fix could never ship. ``ps`` cannot miss a process for want of registration.
    """
    now = time.time() if now is None else now
    attempted = skipped = 0
    try:
        out = subprocess.run(["ps", "-eo", "pid,args"], capture_output=True, text=True,
                             timeout=20, check=False).stdout
    except (OSError, subprocess.SubprocessError):
        return [], 0, 0
    by_script: dict[str, list[int]] = {}
    for line in out.splitlines()[1:]:
        attempted += 1
        parts = line.split()
        if len(parts) < 2 or not parts[0].isdigit():
            skipped += 1                      # attrition-ok: ps header or a malformed row
            continue
        if "python" not in Path(parts[1]).name:
            skipped += 1                      # attrition-ok: not a python process
            continue
        rel = _script_arg(parts[2:], root)
        if rel is None:
            skipped += 1                      # attrition-ok: no repo script in argv (-c, -m, REPL)
            continue
        by_script.setdefault(rel, []).append(int(parts[0]))

    daemons: list[Daemon] = []
    for rel, pids in sorted(by_script.items()):
        starts = [s for s in (proc_start(p) for p in pids) if s is not None]
        if not starts:
            skipped += 1                      # attrition-ok: every pid exited mid-scan
            continue
        started = min(starts)
        age_h = (now - started) / 3600.0
        if age_h < min_uptime_h:
            skipped += 1                      # attrition-ok: too young to hold a stale value
            continue
        daemons.append(Daemon(rel, tuple(sorted(pids)), started, age_h))
    return daemons, attempted, skipped


def _script_arg(argv: Iterable[str], root: Path) -> str | None:
    """The repo-relative .py this argv is running, if any."""
    for a in argv:
        if a.startswith("-") or not a.endswith(".py"):
            continue
        cand = Path(a)
        p = cand if cand.is_absolute() else root / cand
        try:
            if p.exists():
                return str(p.resolve().relative_to(root.resolve()))
        except (OSError, ValueError):
            return None
    return None


# ---------------------------------------------------------------------------------------------
# static analysis
# ---------------------------------------------------------------------------------------------
class _Analyser:
    """Resolves artifact reads across module boundaries, memoised per root.

    Kept as a class purely so the parse/resolve caches die with the run. A module-level cache
    would make a long-lived importer of THIS module hold a stale view of the tree -- which would
    be this module committing its own defect.
    """

    def __init__(self, root: Path) -> None:
        self.root = root
        self._parsed: dict[Path, ast.Module | None] = {}
        self._reads: dict[tuple[str, str], tuple[frozenset[str], bool]] = {}

    # -- parsing ------------------------------------------------------------------------
    def parse(self, path: Path) -> ast.Module | None:
        if path not in self._parsed:
            try:
                self._parsed[path] = ast.parse(path.read_text("utf-8", errors="ignore"))
            except (OSError, SyntaxError, ValueError):
                # A module we cannot parse is UNKNOWN, not clean. The caller counts it as a skip
                # so it lands in the attrition figure rather than vanishing (L1.60).
                self._parsed[path] = None
        return self._parsed[path]

    def resolve_module(self, dotted: str) -> Path | None:
        if dotted.split(".")[0] not in _FIRST_PARTY:
            return None
        for cand in (self.root / (dotted.replace(".", "/") + ".py"),
                     self.root / dotted.replace(".", "/") / "__init__.py"):
            if cand.exists():
                return cand
        return None

    def import_closure(self, entry: Path, seen: set[Path] | None = None) -> set[Path]:
        """Repo-local modules an entry point imports, transitively."""
        seen = set() if seen is None else seen
        if entry in seen or not entry.exists():
            return seen
        seen.add(entry)
        tree = self.parse(entry)
        if tree is None:
            return seen
        for node in ast.walk(tree):
            mods: set[str] = set()
            if isinstance(node, ast.Import):
                mods = {a.name for a in node.names}
            elif isinstance(node, ast.ImportFrom) and node.module and not node.level:
                mods = {node.module}
            for m in mods:
                target = self.resolve_module(m)
                if target is not None:
                    self.import_closure(target, seen)
        return seen

    # -- artifact resolution ------------------------------------------------------------
    def _bindings(self, mod: Path) -> dict[str, tuple[Path, str]]:
        """Imported name -> (defining module, original name). THE FIX FOR BUG 1.

        Without this, ``from libs.x import f`` followed by ``_V = f()`` is invisible -- and that
        is the majority shape on this desk, which is why the first prototype scored 0 of 3.
        """
        tree = self.parse(mod)
        out: dict[str, tuple[Path, str]] = {}
        if tree is None:
            return out
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module and not node.level:
                target = self.resolve_module(node.module)
                if target is None:
                    continue
                for a in node.names:
                    out[a.asname or a.name] = (target, a.name)
        return out

    def _module_constants(self, mod: Path) -> dict[str, set[str]]:
        """Module-level names bound to artifact-looking path literals."""
        tree = self.parse(mod)
        out: dict[str, set[str]] = {}
        if tree is None:
            return out
        for node in tree.body:
            if not isinstance(node, ast.Assign):
                continue
            lits = _artifact_literals(node)
            if not lits:
                continue
            for tgt in node.targets:
                if isinstance(tgt, ast.Name):
                    out[tgt.id] = lits
        return out

    def function_reads(self, mod: Path, name: str, depth: int = 0,
                       stack: frozenset[tuple[str, str]] = frozenset(),
                       ) -> tuple[frozenset[str], bool]:
        """(artifacts, reads_something) for a function, followed transitively across modules."""
        key = (str(mod), name)
        if key in self._reads:
            return self._reads[key]
        if key in stack or depth > _MAX_DEPTH:
            return frozenset(), False
        tree = self.parse(mod)
        if tree is None:
            return frozenset(), False
        fn = next((n for n in ast.walk(tree)
                   if isinstance(n, ast.FunctionDef | ast.AsyncFunctionDef) and n.name == name),
                  None)
        if fn is None:
            return frozenset(), False
        self._reads[key] = (frozenset(), False)      # cycle guard before recursing
        arts, reads = self._scan_calls(fn, mod, tree, depth, stack | {key})
        out = (frozenset(arts), reads)
        self._reads[key] = out
        return out

    def _scan_calls(self, node: ast.AST, mod: Path, tree: ast.Module, depth: int,
                    stack: frozenset[tuple[str, str]]) -> tuple[set[str], bool]:
        """Artifacts and read-ness of an arbitrary subtree, following first-party calls."""
        consts = self._module_constants(mod)
        binds = self._bindings(mod)
        local = {n.name for n in ast.walk(tree)
                 if isinstance(n, ast.FunctionDef | ast.AsyncFunctionDef)}
        arts: set[str] = set(_artifact_literals(node))
        for nm in {x.id for x in ast.walk(node) if isinstance(x, ast.Name)}:
            arts |= consts.get(nm, set())
        reads = False
        for call in (n for n in ast.walk(node) if isinstance(n, ast.Call)):
            fn = call.func
            attr = fn.attr if isinstance(fn, ast.Attribute) else (
                fn.id if isinstance(fn, ast.Name) else "")
            if attr in READ_VERBS:
                reads = True
            if not isinstance(fn, ast.Name):
                continue
            if fn.id in local:
                sub_arts, sub_reads = self.function_reads(mod, fn.id, depth + 1, stack)
            elif fn.id in binds:
                target, orig = binds[fn.id]
                sub_arts, sub_reads = self.function_reads(target, orig, depth + 1, stack)
            else:
                continue
            arts |= sub_arts
            reads = reads or sub_reads
        return arts, reads

    # -- the detector -------------------------------------------------------------------
    def frozen_reads(self, mod: Path) -> list[FrozenRead]:
        """Every binding in ``mod`` whose value is decided once, at import."""
        tree = self.parse(mod)
        if tree is None:
            return []
        try:
            rel = str(mod.resolve().relative_to(self.root.resolve()))
        except ValueError:
            rel = str(mod)
        lines = mod.read_text("utf-8", errors="ignore").splitlines()
        found: list[FrozenRead] = []
        frozen_names: set[str] = set()
        # THE REFINEMENT THAT KEEPS THIS FENCE FROM CRYING WOLF, and it was learned the hard way:
        # a module-scope binding is only frozen IN EFFECT if nothing re-runs its producer later.
        # `run_recorder.py` seeds `_SYMBOLS = _universe()` at import AND re-polls `_universe()`
        # inside its loop, so the seed is a seed, not a frozen value. Reporting it would have made
        # the first run 2 false alarms out of 3 -- and a detector that cries wolf gets acked into
        # silence (R0356). See `_live_reread_lines`.
        rereads = _live_reread_lines(tree)

        for node in tree.body:
            if isinstance(node, ast.Assign):
                arts, reads = self._scan_calls(node, mod, tree, 0, frozenset())
                if not reads:
                    continue
                names = [t.id for t in node.targets if isinstance(t, ast.Name)]
                if not names:
                    continue
                refresh = max((rereads.get(p, 0) for p in _called_names(node)), default=0)
                for nm in names:
                    found.append(FrozenRead(rel, nm, node.lineno, "module-scope",
                                            tuple(sorted(arts)), _exempt_reason(lines, node.lineno),
                                            refresh))
                    frozen_names.add(nm)
            elif isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                if not _is_memoised(node):
                    continue
                m_arts, m_reads = self.function_reads(mod, node.name)
                if m_reads:
                    found.append(FrozenRead(rel, node.name, node.lineno, "memoized",
                                            tuple(sorted(m_arts)),
                                            _exempt_reason(lines, node.lineno)))

        # DEFAULT ARGUMENTS ARE EVALUATED ONCE, AT DEFINITION -- the double-freeze. A frozen
        # name rebound as a default (``def f(..., floors=FLOORS)``) cannot be retuned even by a
        # caller that re-read the artifact, because the default was captured at import.
        by_name = {f.name: f for f in found}
        for fnode in ast.walk(tree):
            if not isinstance(fnode, ast.FunctionDef | ast.AsyncFunctionDef):
                continue
            defaults = [*fnode.args.defaults,
                        *[d for d in fnode.args.kw_defaults if d is not None]]
            for d in defaults:
                if not isinstance(d, ast.Name) or d.id not in frozen_names:
                    continue
                src = by_name.get(d.id)
                found.append(FrozenRead(rel, f"{fnode.name}(...={d.id})", fnode.lineno,
                                        "default-arg", src.artifacts if src else (),
                                        _exempt_reason(lines, fnode.lineno)))
        return found


def _called_names(node: ast.AST) -> set[str]:
    """Bare-name functions called anywhere under ``node``."""
    return {c.func.id for c in ast.walk(node)
            if isinstance(c, ast.Call) and isinstance(c.func, ast.Name)}


def _live_reread_lines(tree: ast.Module) -> dict[str, int]:
    """function name -> line where it is called from INSIDE some function body.

    A call at module scope runs once, at import. A call inside a function body can run again --
    every tick of a loop, every rebalance, every request -- so the artifact behind it has a live
    re-read path and the import-time binding is a SEED rather than a frozen value.

    THIS IS DELIBERATELY GENEROUS, and the direction is chosen rather than accidental. It does
    not prove the enclosing function is ever called, nor that it is called on a useful cadence;
    it proves the desk WROTE a re-read path. A false REFRESHED costs one missed row in a report;
    a false FROZEN-STALE costs the fence's credibility, and a fence nobody believes enforces
    nothing (L1.43). The evidence is published as a line number precisely so a human can check
    the cadence claim rather than take it on trust.
    """
    out: dict[str, int] = {}
    for fn in ast.walk(tree):
        if not isinstance(fn, ast.FunctionDef | ast.AsyncFunctionDef):
            continue
        for call in ast.walk(fn):
            if not isinstance(call, ast.Call) or not isinstance(call.func, ast.Name):
                continue
            if call.func.id == fn.name:
                continue                       # recursion is not a re-read path
            out.setdefault(call.func.id, call.lineno)
    return out


def _artifact_literals(node: ast.AST) -> set[str]:
    """String constants under ``node`` that look like repo artifact paths."""
    out: set[str] = set()
    for n in ast.walk(node):
        if not isinstance(n, ast.Constant) or not isinstance(n.value, str):
            continue
        v = n.value
        if 3 < len(v) < 200 and "\n" not in v and (
                "data/" in v or v.startswith("ops/") or "/ops/" in v):
            out.add(v)
    return out


def _is_memoised(node: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    names: set[str] = set()
    for d in node.decorator_list:
        if isinstance(d, ast.Name):
            names.add(d.id)
        elif isinstance(d, ast.Attribute):
            names.add(d.attr)
        elif isinstance(d, ast.Call):
            f = d.func
            names.add(f.attr if isinstance(f, ast.Attribute)
                      else (f.id if isinstance(f, ast.Name) else ""))
    return bool(names & {"cache", "lru_cache", "cached_property"})


def _exempt_reason(lines: list[str], lineno: int) -> str:
    """``# frozen-ok: <reason>`` on the line or the two above it. A bare tag is not a tag."""
    for i in range(max(0, lineno - 3), min(len(lines), lineno)):
        m = _EXEMPT_TAG.search(lines[i])
        if m:
            return m.group(1).strip()
    return ""


# ---------------------------------------------------------------------------------------------
# the report
# ---------------------------------------------------------------------------------------------
def build_report(root: Path | None = None, *, now: float | None = None) -> Report:
    """Grade every (live daemon, frozen read) pair on the box.

    ``root`` defaults to the BOX's main checkout, not this process's tree: a linked worktree has
    a gitignored ``data/`` and the running daemons import the main checkout's modules, so a
    worktree run that measured its own tree would fabricate a verdict about source nothing is
    executing and artifacts that do not exist (R0521, the standing worktree-blind-fence defect).
    """
    here = Path(__file__).resolve().parent.parent.parent if root is None else root
    box, basis = data_root(here)
    now = time.time() if now is None else now

    rep = Report(status=UNMEASURED, basis=basis, root=str(box))
    daemons, attempted, skipped = live_daemons(box, now=now)
    rep.attempted, rep.skipped = attempted, skipped
    rep.daemons = daemons

    if not daemons:
        # AN HONEST DECLARED REFUSAL, NOT A VACUOUS PASS. Off the box -- CI, a fresh clone, a
        # container that cannot see the process table -- there is genuinely nothing of ours
        # running, and the status says so rather than reporting a clean desk. Distinct from OK,
        # and structurally absent from PASSING.
        rep.status = NO_DAEMONS_HERE
        rep.notes.append("no long-lived repo processes visible from this vantage point; "
                         "this is a statement about the vantage point, never about the desk")
        return rep

    an = _Analyser(box)
    seen: set[tuple[str, str, int, str]] = set()
    for d in daemons:
        entry = box / d.script
        for mod in sorted(an.import_closure(entry)):
            rep.attempted += 1
            if an.parse(mod) is None:
                rep.skipped += 1              # attrition-ok: unparseable module, counted not hidden
                continue
            for fr in an.frozen_reads(mod):
                key = (d.script, fr.module, fr.lineno, fr.name)
                if key in seen:
                    continue
                seen.add(key)
                rep.pairs.extend(_grade(d, fr, box, now))

    if rep.n_stale:
        rep.status = UNVERIFIABLE
    elif rep.n_unresolved or rep.n_source_drifted:
        # NOT folded into UNVERIFIABLE, and not waved through either. "This daemon holds a value
        # whose input moved" and "this daemon is running source we did not analyse" are different
        # claims needing different repairs (move the read / restart the daemon), and only the
        # first is this law's finding. Both are refusals to certify, so neither reads as OK.
        rep.status = UNRESOLVED
    elif rep.n_pairs:
        rep.status = OK
    else:
        # Daemons ARE running and not one frozen read was found. That is a real possible state,
        # but it is also exactly what a broken analyser returns -- and this one returned it once
        # already, against three hand-verified positives. It reads UNMEASURED, never OK (L1.28a).
        rep.status = UNMEASURED
        rep.notes.append(f"{len(daemons)} daemon(s) running and ZERO frozen reads found -- "
                         "verify the analyser against tests/ops/test_value_staleness.py's "
                         "positive controls before reading this as a clean desk (L1.25)")
    return rep


def _grade(d: Daemon, fr: FrozenRead, box: Path, now: float) -> list[Pair]:
    # THE FALSE GREEN THIS FENCE WOULD OTHERWISE CREATE WITH ITS OWN REPAIRS, and it is the
    # subtlest thing in this module. Every verdict below is derived from SOURCE ON DISK, while
    # the claim being made is about VALUES IN A RUNNING PROCESS. Patch a frozen read into a
    # refreshing one and this fence flips to REFRESHED the instant the file is saved -- while
    # the daemon goes right on holding the frozen value until it restarts. The fix would report
    # itself fixed, which is L0004 exactly ("the --hold-top 3000 churn fix sat committed and dead
    # for 2 days") wearing a green checkmark. If the module's source post-dates the process, no
    # static verdict about that process's values is valid, and saying so is the only honest move.
    # This is the seam where this fence and `check_stale_daemons` compose: it needs the code
    # answer to earn the right to give a value answer.
    src = box / fr.module
    try:
        if src.stat().st_mtime > d.started:
            return [Pair(d.script, fr, SOURCE_DRIFTED,
                         drift_h=(src.stat().st_mtime - d.started) / 3600.0,
                         why=(f"{fr.module} was edited "
                              f"{(src.stat().st_mtime - d.started) / 3600.0:.1f}h after this "
                              "process started, so the running process is executing DIFFERENT "
                              "source than was analysed; no value verdict is valid until it "
                              "restarts (compose with check_stale_daemons)"))]
    except OSError:
        pass          # attrition-ok: unreadable source falls through to the value verdicts below
    if fr.exempt_reason:
        return [Pair(d.script, fr, EXEMPT, why=f"frozen-ok: {fr.exempt_reason}")]
    if fr.refresh_line:
        return [Pair(d.script, fr, REFRESHED,
                     why=(f"import-time binding is a SEED: its producer is re-run at "
                          f"{fr.module}:{fr.refresh_line}, inside a function body"))]
    if not fr.resolved:
        return [Pair(d.script, fr, FROZEN_UNRESOLVED,
                     why=("reads an artifact whose path is not statically resolvable; "
                          "UNRESOLVED is counted, never dropped (L1.28a)"))]
    out: list[Pair] = []
    for a in fr.artifacts:
        p = box / a.lstrip("/")
        try:
            mtime = p.stat().st_mtime
        except OSError:
            out.append(Pair(d.script, fr, FROZEN_UNRESOLVED, artifact=a,
                            why="named artifact is not readable from here"))
            continue
        if mtime > d.started:
            out.append(Pair(d.script, fr, FROZEN_STALE, artifact=a,
                            drift_h=(mtime - d.started) / 3600.0,
                            why=(f"{a} changed {(mtime - d.started) / 3600.0:.1f}h AFTER this "
                                 f"process started (up {d.age_h:.1f}h); the in-memory value "
                                 "cannot be proven to match disk")))
        else:
            out.append(Pair(d.script, fr, FROZEN_CURRENT, artifact=a,
                            why="artifact unchanged since process start -- exposed, not bitten"))
    return out

```

### libs\research\country_lab.py
```python
"""THE COUNTRY LAB -- the generic miner set every country runs, from its own mandate as DATA.

THE PRINCIPAL'S ORDER (2026-09-17): GLOBAL RESEARCH OS -> REGIONAL COMMANDS -> COUNTRY LABS ->
LOCAL MECHANISM DEPARTMENTS -> CELL COMPILER -> ONE GAUNTLET. Every country gets the same DEPTH
as Japan and the same PRIORITY. Countries are not disconnected copies of one another: the
universal frame Country x Actor x Constraint x Institution x Calendar x Information x Flow x
Asset x Horizon x Regime is shared, and each country DISCOVERS its own axes inside it -- when a
country exposes something the ontology has no word for, the ontology grows (that half lives in
`desks/mt5/research/transmission_engine.py`, which owns the axis-extension write).

WHAT THIS MODULE IS, AND WHAT IT DELIBERATELY IS NOT. It is the GENERIC HALF: fifteen miners that
need to know nothing about any particular country because everything country-specific reaches
them as DATA on a `CountryPack` -- the central bank and its decision dates, the fixing and
settlement conventions, the holiday table, the exchange and its expiry rule, the fiscal year end,
the positioning source, the native languages and the native terminology, the datasets, the actors
and domains, and the transmission channels the country already declares. A country pack is
therefore DATA PLUS OPTIONAL CUSTOM MINERS, and a new country costs a pack, not a fork of this
file. It is NOT a place where any country's name may ever appear: a `grep` for a country here
returning a hit is the defect.

WHY THE INPUTS ARRIVE THROUGH THE CONTEXT. `LabCtx` carries a `bars_loader` and a `series_loader`
rather than reading the desk's parquet estate itself, for three reasons that each cost something
once. (1) This module is `libs/`, checked under mypy strict, and the bar estate is pandas; the
loaders keep the import surface numpy-only and the measurement code array-shaped. (2) A test can
plant a tape with a KNOWN effect in it and assert the miner recovered exactly that, which is the
only way to know a miner measures rather than reports. (3) The trading box has 8 GB and holds the
live terminal: one loader with one cache is the difference between fifteen miners opening the
same parquet fifteen times and opening it once. `default_bars_loader` supplies the real thing,
importing pandas LAZILY so the module still imports where pandas does not.

UNMEASURED IS A VERDICT, BY NAME (L1.28a). Every miner here reports what it could not measure and
WHY -- the dataset that is not on this box, the calendar the pack does not declare, the symbol
with no bars, the currency absent from `cot.json`. None of those is a zero, none of them is a
clean pass, and a miner that found nothing to measure says which input was missing rather than
returning an empty result that reads like a negative finding.

TWO OUTPUTS, ALWAYS. A country lab produces DOMESTIC candidates (what its own actors are forced
to do, in its own instruments) and TRANSMISSION seeds (the channel by which that forcing reaches
somebody else's instrument). The second is not a by-product: a country whose only executable
instrument is a thin exotic is still worth mining if what happens there moves an index that is
liquid, and the transmission engine is what turns that seed into a measured edge.

    from libs.research import country_lab as CL
    problems = CL.validate_pack(pack, CL.universe())
    report   = CL.run_lab(pack, CL.LabCtx(code=pack.code, conn=conn), budget_s=180)
"""
from __future__ import annotations

import importlib
import importlib.util
import json
import math
import re
import sys
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from dataclasses import fields as dataclass_fields
from dataclasses import replace as dataclass_replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import numpy as np

from libs.moat import registry as R

ROOT = Path(__file__).resolve().parents[2]
DESK = ROOT / "desks" / "mt5"
#: Module-level so a test can point them somewhere else.
UNIVERSE_JSON: Path = DESK / "data" / "universe" / "universe.json"
BARS_DIR: Path = DESK / "data" / "universe"
COT_JSON: Path = DESK / "data" / "axes" / "cot.json"

# --------------------------------------------------------------------------- the vocabularies
#: The nine regional commands. A country belongs to exactly one; the command is what the global
#: OS groups by and what every discovery this lab writes carries in its payload.
REGION_COMMANDS: tuple[str, ...] = ("asia", "oceania", "russia_cis", "europe", "uk",
                                    "north_america", "latam", "mea", "africa")

#: Central-bank frameworks. The similarity table in the transmission engine reads this field: a
#: mechanism that lives on a BAND does not transfer to a free float, however alike the two
#: economies look, and `UNMEASURED` is a declaration that the pack has not said.
CB_FRAMEWORKS: tuple[str, ...] = ("inflation_targeter", "dual_mandate", "band", "peg",
                                  "crawling_peg", "ycc", "managed_float", "monetary_aggregate",
                                  "UNMEASURED")

#: What the country SELLS. The single most transferable institution there is: two commodity
#: exporters share a terms-of-trade mechanism whatever their politics.
EXPORT_TYPES: tuple[str, ...] = ("commodity_exporter", "energy_exporter", "metals_exporter",
                                 "agricultural_exporter", "manufacturing_exporter",
                                 "semiconductor_exporter", "services_exporter", "net_importer",
                                 "UNMEASURED")

#: Retail leverage regimes -- a real institution, not a footnote: a capped regime changes who is
#: on the other side of a stop cascade and therefore whether a microstructure mechanism exists.
LEVERAGE_REGIMES: tuple[str, ...] = ("restricted", "capped", "open", "UNMEASURED")

#: Settlement/fixing convention kinds the generic calendar miner can turn into windows.
SETTLEMENT_KINDS: tuple[str, ...] = ("day_of_month", "month_end", "quarter_end",
                                     "fiscal_year_end", "fiscal_quarter_end", "weekday",
                                     "week_of_month")

#: Asset-class spellings that may never be hunted for a statistical hypothesis (two-lane mandate,
#: 2026-09-06). Single names are traded on disclosures, in the event lane, by another organ.
EQUITY_CLASSES: frozenset[str] = frozenset({
    "equities", "equity", "equities us", "shares", "share", "stock", "stocks", "us shares"})

#: The instruments every country's shock is asked about in addition to its own, so a domestic
#: mechanism is measured against the global tape rather than only against itself. Filtered by the
#: broker universe at run time: a symbol this box cannot execute is never in a reaction set.
GLOBAL_REACTION_SET: tuple[str, ...] = ("US500", "NAS100", "GER40", "XAUUSD", "XAGUSD", "XTIUSD",
                                        "EURUSD", "USDJPY", "AUDUSD", "UST10Y")

#: The eight measurable outcomes of a generic miner. `UNMEASURED` is one of them.
OK, SKIPPED, UNMEASURED, FAILED = "ok", "skipped", "UNMEASURED", "failed"

#: Which region-framework miner kind each generic miner is, so `mandate_of` can hand the region
#: department a mandate whose miners route to the right loop step.
MINER_KIND: dict[str, str] = {
    "central_bank_surprise": "calendar", "release_surprise": "calendar",
    "calendar_settlement": "calendar", "holiday_liquidity": "calendar",
    "derivatives_expiry": "calendar", "session_microstructure": "mechanism",
    "positioning": "mechanism", "carry_funding": "mechanism", "corporate_flow": "mechanism",
    "institutional_flow": "mechanism", "equity_mechanics": "mechanism",
    "failure": "failure", "residual": "residual", "transfer": "transfer", "scouts": "scout",
}
#: The registry's `information` axis value each miner's discoveries carry.
MINER_INFORMATION: dict[str, str] = {
    "central_bank_surprise": "event", "release_surprise": "event",
    "calendar_settlement": "event", "holiday_liquidity": "event", "derivatives_expiry": "event",
    "session_microstructure": "price_only", "positioning": "positioning",
    "carry_funding": "carry", "corporate_flow": "macro", "institutional_flow": "macro",
    "equity_mechanics": "cross_asset", "failure": "price_only", "residual": "price_only",
    "transfer": "cross_asset", "scouts": "macro",
}

#: Measurement constants. Stated once so a reader and a test read the same numbers.
MIN_EVENTS = 6                  # below this an event study is POORLY_MEASURED, never a verdict
MIN_EVENT_DAYS = 2              # a null that resamples DATES needs at least two dates to resample
MIN_BARS = 200                  # below this a tape cannot carry a matched-control comparison
N_PERM = 200                    # permutation draws; the null randomises DATES, never returns
MAX_BARS = 200_000              # the box holds the live terminal: a miner never loads more
P_MAX = 0.05
#: Per-miner floors of the pool, and the protected cold share (section 27/28 of the region
#: framework: exploration and exploitation, permanently, and cold ground is protected AS A CLASS).
MINER_FLOOR = 0.04
COLD_SHARE = 0.10
MINER_FLOOR_S = 1.0

RULE = ("a country lab produces DOMESTIC and TRANSMISSION candidates from its mandate as data; "
        "an input the pack does not declare is UNMEASURED by name, never an empty finding")


# --------------------------------------------------------------------------- the pack's objects
@dataclass(frozen=True)
class CentralBank:
    """The country's rate-setting institution, enough of it to mine a surprise.

    `decision_dates` are what the miner actually uses; `decision_calendar_rule` is the prose that
    says how they are derived so a later pass can extend them. Both may be given: dates win, the
    rule is the provenance. `expected`/`actual`/`prior` name SERIES the context can load -- when
    the expectation is not on this box the surprise is measured against the PRIOR and the result
    says which of the two it was, because a surprise against a prior is a different quantity.
    """

    name: str = ""
    framework: str = "UNMEASURED"
    decision_dates: tuple[str, ...] = ()
    decision_calendar_rule: str = ""
    decision_time_utc: str = ""
    publication_classes: tuple[str, ...] = ()
    policy_rate_series: str = ""
    expected_rate_series: str = ""
    notes: str = ""


@dataclass(frozen=True)
class Fixing:
    """One published benchmark rate and the minutes it is struck in."""

    name: str = ""
    time_utc: str = ""
    dst_rule: str = "none"
    instruments: tuple[str, ...] = ()
    window_minutes: int = 60
    notes: str = ""


@dataclass(frozen=True)
class SettlementRule:
    """One settlement convention as a RULE, not a list of dates -- gotobi-like day-of-month
    conventions, month/quarter/fiscal ends, weekday conventions. `roll` says what happens when
    the convention day is closed: the preceding or the following open day, or nothing."""

    name: str = ""
    kind: str = "day_of_month"
    days: tuple[int, ...] = ()
    months: tuple[int, ...] = ()
    weekday: int = -1
    week_of_month: int = 0
    roll: str = "previous"
    window_utc: tuple[str, str] = ("", "")
    instruments: tuple[str, ...] = ()
    notes: str = ""


@dataclass(frozen=True)
class Exchange:
    """The country's exchange, its index symbols on THIS broker, and its expiry rule."""

    name: str = ""
    index_symbols: tuple[str, ...] = ()
    expiry_rule: str = ""
    expiry_dates: tuple[str, ...] = ()
    open_utc: str = ""
    close_utc: str = ""
    notes: str = ""


@dataclass(frozen=True)
class ReleaseClass:
    """One class of scheduled national statistic (CPI, trade balance, employment, PMI)."""

    name: str = ""
    cadence: str = "monthly"
    time_utc: str = ""
    dates: tuple[str, ...] = ()
    actual_series: str = ""
    expected_series: str = ""
    source: str = ""
    notes: str = ""


@dataclass(frozen=True)
class SessionWindow:
    """A named window of the country's own trading day, in UTC, on the tape the desk holds."""

    name: str = ""
    start_utc: str = ""
    end_utc: str = ""
    notes: str = ""


@dataclass(frozen=True)
class HolidayRule:
    """The country's closed days -- an explicit table, recurring month-day rules, or both. The
    weekly closure is declared rather than assumed: not every market rests on Saturday."""

    dates: tuple[str, ...] = ()
    fixed_md: tuple[str, ...] = ()
    weekly_closed: tuple[int, ...] = (5, 6)
    notes: str = ""


@dataclass(frozen=True)
class Era:
    """A policy era. Every measurement here is reported per era as well as pooled: an effect that
    exists only under a regime that ended is a historical fact, not a live edge."""

    name: str = ""
    start: str = ""
    end: str = ""
    notes: str = ""


@dataclass(frozen=True)
class TransmissionSeed:
    """A DECLARED channel out of this country: who is forced, by what, into which flow, landing
    on which foreign asset. A seed is a hypothesis about structure, never evidence -- the
    transmission engine measures it, and an unmeasurable leg is named."""

    to_country: str = "global"
    asset: str = ""
    actor: str = ""
    constraint: str = ""
    flow: str = ""
    source_series: str = ""
    source_symbol: str = ""
    lag_days: float = 1.0
    era: str = ""
    notes: str = ""


@dataclass(frozen=True)
class ActorRow:
    """Mirrors `region_mandate.Actor` field for field so `mandate_of` is a copy and this module
    needs no import of the region framework to be usable or testable."""

    name: str = ""
    holds: str = ""
    forced_to: tuple[str, ...] = ()
    when: str = ""
    information: tuple[str, ...] = ()
    constraints: tuple[str, ...] = ()
    instruments: tuple[str, ...] = ()
    counterparties: tuple[str, ...] = ()
    observables: tuple[str, ...] = ()
    impact: str = ""
    persistence: str = ""
    falsifier: str = ""
    notes: str = ""


@dataclass(frozen=True)
class DomainRow:
    """Mirrors `region_mandate.Domain`. `controls` is never optional: a domain that cannot name
    its negative control cannot tell an effect from its own selection."""

    id: str = ""
    title: str = ""
    objects: tuple[str, ...] = ()
    conditions: tuple[str, ...] = ()
    instruments: tuple[str, ...] = ()
    controls: tuple[str, ...] = ()
    notes: str = ""


@dataclass(frozen=True)
class DatasetRow:
    """Mirrors `region_mandate.DatasetSpec`. `pit_feasible` is the field it exists for."""

    name: str = ""
    source: str = ""
    coverage: str = ""
    frequency: str = ""
    publication_lag_days: float = 0.0
    revisions: str = ""
    licence: str = ""
    history_from: str = ""
    pit_feasible: bool = False
    assets: tuple[str, ...] = ()
    mechanism_families: tuple[str, ...] = ()
    how_to_fetch: str = ""


#: Rows a pack may declare as PLAIN MAPPINGS, BARE STRINGS or under their own field names.
#: Sixteen country departments were written against this contract in parallel, each with its
#: own small adapter that emits dicts precisely so the department depends on no shared helper
#: module. So the framework meets them where they are: a row is COERCED once, at construction,
#: and every consumer downstream sees the same typed object.
#:
#: NOTHING IS LOST SILENTLY. A key the row does not have is folded into `notes` when the row
#: has one (a pack's `control` and `falsifier` are the most valuable fields it wrote), else it
#: is recorded DROPPED; a row that cannot be built at all is recorded FAILED and
#: `validate_pack` then refuses the pack -- a pack claiming a settlement convention the
#: framework could not construct would otherwise be mined as if it had none.
_ROW_CLASSES: tuple[tuple[str, type], ...] = ()      # bound below, after the classes exist


#: HOW A PACK'S OWN SPELLING REACHES THE FRAMEWORK'S FIELD. Sixteen country departments were
#: written in parallel against this contract and each one named its rows slightly differently --
#: `target` for the asset, `mechanism` for the flow, `id` or `label` for the name. The data is
#: the deliverable and the container is not, so the aliases are here rather than in sixteen packs.
_ROW_ALIASES: dict[str, dict[str, str]] = {
    "TransmissionSeed": {"target": "asset", "symbol": "asset", "instrument": "asset",
                         "to": "to_country", "country": "to_country", "dest": "to_country",
                         "destination": "to_country", "mechanism": "flow",
                         "source": "source_series", "series": "source_series",
                         "lag": "lag_days", "note": "notes"},
    "Era": {"id": "name", "label": "name", "era": "name", "start_date": "start",
            "end_date": "end", "from": "start", "to": "end", "note": "notes"},
    "SettlementRule": {"id": "name", "label": "name", "type": "kind", "day": "days",
                       "window": "window_utc", "note": "notes"},
    "Fixing": {"id": "name", "label": "name", "time": "time_utc", "utc": "time_utc",
               "dst": "dst_rule", "note": "notes"},
    "Exchange": {"id": "name", "label": "name", "indices": "index_symbols",
                 "index": "index_symbols", "expiry": "expiry_rule", "note": "notes"},
    "ReleaseClass": {"id": "name", "label": "name", "time": "time_utc", "note": "notes"},
    "SessionWindow": {"id": "name", "label": "name", "start": "start_utc", "end": "end_utc",
                      "note": "notes"},
    "CentralBank": {"id": "name", "label": "name", "bank": "name", "regime": "framework",
                    "policy_framework": "framework", "dates": "decision_dates",
                    "rule": "decision_calendar_rule", "note": "notes"},
    "HolidayRule": {"table": "dates", "holidays": "dates", "recurring": "fixed_md",
                    "weekend": "weekly_closed", "note": "notes"},
    "ActorRow": {"id": "name", "label": "name", "actor": "name", "note": "notes"},
    "DomainRow": {"domain": "id", "name": "title", "label": "title", "note": "notes"},
    "DatasetRow": {"id": "name", "label": "name", "url": "how_to_fetch", "note": "notes"},
    "SourceRow": {"name": "label", "source_id": "id", "kind": "layer", "class": "layer",
                  "root": "roots", "url": "roots", "urls": "roots", "language": "languages",
                  "lang": "languages", "terms": "query_terms", "absent": "absent_reason",
                  "note": "notes"},
}
#: A row given as a BARE STRING lands on this field. `("month_end", "quarter_end")` is a perfectly
#: readable settlement declaration and refusing it would cost the framework five packs' calendars.
_ROW_FROM_STRING: dict[str, str] = {
    "TransmissionSeed": "asset", "SettlementRule": "kind", "Fixing": "name", "Exchange": "name",
    "ReleaseClass": "name", "SessionWindow": "name", "Era": "name", "ActorRow": "name",
    "DomainRow": "id", "DatasetRow": "name", "SourceRow": "id",
}
#: The nine commands are the framework's; a pack's own finer grouping maps into one of them and
#: the remap is RECORDED, never silent -- a country filed under a command nobody reads is a
#: country nobody funds.
REGION_COMMAND_ALIASES: dict[str, str] = {
    "east_asia": "asia", "northeast_asia": "asia", "north_asia": "asia", "greater_china": "asia",
    "southeast_asia": "asia", "sea": "asia", "south_asia": "asia", "asia_pacific": "asia",
    "apac": "asia", "eu": "europe", "eurozone": "europe", "euro_area": "europe",
    "nordics": "europe", "scandinavia": "europe", "east_eu": "europe",
    "eastern_europe": "europe", "central_europe": "europe", "emea": "europe",
    "middle_east": "mea", "mena": "mea", "gulf": "mea", "gcc": "mea",
    "sub_saharan_africa": "africa", "saharan_africa": "africa",
    "anz": "oceania", "australasia": "oceania", "pacific": "oceania",
    "cis": "russia_cis", "eurasia": "russia_cis", "ru": "russia_cis",
    "south_america": "latam", "central_america": "latam", "latin_america": "latam",
    "namerica": "north_america", "nafta": "north_america", "usa": "north_america",
    "united_kingdom": "uk", "britain": "uk", "gb": "uk",
}


def canonical_command(value: Any) -> str:
    """One of the nine REGION_COMMANDS, or the token itself when nothing maps it."""
    tok = _tok(value)
    if tok in REGION_COMMANDS:
        return tok
    return REGION_COMMAND_ALIASES.get(tok, tok)


def _coerce_row(cls: type, value: Any, where: str, notes: list[str]) -> Any:
    names = {f.name for f in dataclass_fields(cls)}
    alias = _ROW_ALIASES.get(cls.__name__, {})
    if isinstance(value, cls):
        return value
    if isinstance(value, str):
        field_name = _ROW_FROM_STRING.get(cls.__name__, "")
        if field_name in names:
            return cls(**{field_name: value})
        notes.append(f"FAILED {where}: a bare string cannot become a {cls.__name__}")
        return None
    if not isinstance(value, Mapping):
        notes.append(f"FAILED {where}: expected a {cls.__name__}, a mapping or a string, got "
                     f"{type(value).__name__}")
        return None
    kw: dict[str, Any] = {}
    spare: list[str] = []
    for k, v in value.items():
        key = alias.get(str(k), str(k))
        if key in names and key not in kw:
            kw[key] = tuple(v) if isinstance(v, list) else v
        elif "notes" in names:
            # NEVER DROPPED. A pack's `control`, `falsifier`, `sign` and `condition` are the most
            # valuable fields it wrote; folding them into `notes` keeps them readable by a human
            # and by the deepening worker instead of deleting the negative control on import.
            spare.append(f"{k}={v}")
        else:
            notes.append(f"DROPPED {where}.{k}: {cls.__name__} has no such field and no notes")
    if spare and "notes" in names:
        kw["notes"] = " | ".join([str(kw.get("notes") or ""), *spare]).strip(" |")
    for key, val in list(kw.items()):
        if key in _DATE_FIELDS:
            kw[key] = _flatten_dates(val)
        elif key in _TIME_FIELDS and isinstance(val, Mapping):
            # A DST-SPLIT FIXING TIME. `{"winter": "15:00Z", "summer": "14:00Z"}` is the honest
            # way to write a benchmark struck at a local hour, and the WINTER leg is the anchor
            # this desk has always used (the gold_asia window's measured +2 is the winter
            # anchor, CLAUDE.md). The other leg is kept in `notes`, never thrown away.
            winter = str(val.get("winter") or next(iter(val.values()), ""))
            kw[key] = winter.replace("Z", "").strip()[:5]
            if "notes" in names:
                kw["notes"] = " | ".join(x for x in [str(kw.get("notes") or ""),
                                                     f"{key} by season: {dict(val)}"] if x)
    try:
        row = cls(**kw)
    except (TypeError, ValueError) as exc:
        notes.append(f"FAILED {where}: {cls.__name__}({type(exc).__name__}: {exc})")
        return None
    if "name" in names and not str(getattr(row, "name", "") or "").strip():
        row = dataclass_replace(row, name=_tok(where))
        notes.append(f"DROPPED {where}: the row carried no name; it is filed as {_tok(where)!r}")
    return row


#: Fields whose value is a COLLECTION OF DATES however the pack chose to nest it -- a flat list,
#: a {year: [dates]} table, or a {date: label} table. All three are readable declarations and all
#: three appear in the shipped packs.
_DATE_FIELDS: frozenset[str] = frozenset({"decision_dates", "dates", "expiry_dates", "fixed_md"})
_TIME_FIELDS: frozenset[str] = frozenset({"time_utc", "start_utc", "end_utc", "open_utc",
                                          "close_utc", "decision_time_utc"})


def _flatten_dates(value: Any) -> tuple[str, ...]:
    """Every date in a nested declaration, in order, with no label mistaken for a date.

    A mapping whose KEYS all parse as dates is a {date: label} table and its keys are the answer;
    any other mapping (a {year: [dates]} table) is walked through its VALUES. Getting that
    backwards silently turns a holiday table into a list of holiday NAMES, which then matches no
    bar on any tape and reads as "the country has no closures".
    """
    out: list[str] = []

    def walk(v: Any) -> None:
        if v is None:
            return
        if isinstance(v, str):
            out.append(v)
            return
        if isinstance(v, Mapping):
            keys = list(v)
            if keys and all(parse_day(k) is not None for k in keys):
                out.extend(str(k) for k in keys)
            else:
                for sub in v.values():
                    walk(sub)
            return
        if isinstance(v, (list, tuple, set)):
            for sub in v:
                walk(sub)
            return
        out.append(str(v))

    walk(value)
    return tuple(out)


def _str_tuple(value: Any) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        return (value,)
    if isinstance(value, Mapping):
        return tuple(str(k) for k in value)
    return tuple(str(v) for v in value)


@dataclass(frozen=True)
class CountryPack:
    """ONE COUNTRY'S WHOLE STANDING ORDER AS DATA.

    Everything a generic miner needs to mine this country and nothing that names it in code. A
    field left at its default is a DECLARATION THAT THE COUNTRY HAS NOT SAID, and every miner
    that needs it reports UNMEASURED naming the field -- which is how a half-written pack shows
    up as a measurement rather than as a quiet absence.
    """

    code: str
    name: str
    region_command: str
    currency: str
    executable_instruments: tuple[str, ...] = ()
    central_bank: CentralBank = CentralBank(name="")
    fixing_conventions: tuple[Fixing, ...] = ()
    settlement_conventions: tuple[SettlementRule, ...] = ()
    exchanges: tuple[Exchange, ...] = ()
    release_classes: tuple[ReleaseClass, ...] = ()
    session_windows: tuple[SessionWindow, ...] = ()
    holidays_rule: HolidayRule = HolidayRule()
    fiscal_year_end: str = ""
    policy_eras: tuple[Era, ...] = ()
    positioning_sources: tuple[str, ...] = ()
    cot_currency: str = ""
    export_economy: str = "UNMEASURED"
    retail_leverage_regime: str = "UNMEASURED"
    native_languages: tuple[str, ...] = ()
    terminology: Mapping[str, tuple[str, ...]] = field(default_factory=dict)
    source_classes: tuple[str, ...] = ()
    sources: tuple[Any, ...] = ()
    absent_layers: Mapping[str, str] = field(default_factory=dict)
    institutional_flow_sources: tuple[str, ...] = ()
    series: Mapping[str, str] = field(default_factory=dict)
    datasets: tuple[DatasetRow, ...] = ()
    actors: tuple[ActorRow, ...] = ()
    domains: tuple[DomainRow, ...] = ()
    miner_domains: Mapping[str, tuple[str, ...]] = field(default_factory=dict)
    custom_miners: tuple[str, ...] = ()
    transmission_edges_seed: tuple[TransmissionSeed, ...] = ()
    mission: str = ""
    notes: str = ""
    coercion_notes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        """Accept a pack written as PLAIN DATA and hand every consumer a typed one."""
        notes: list[str] = list(self.coercion_notes)
        put = object.__setattr__
        if _tok(self.code) != str(self.code):
            notes.append(f"DROPPED code: {self.code!r} is filed under the canonical token "
                         f"{_tok(self.code)!r}; every row this lab writes is tagged with it")
            put(self, "code", _tok(self.code))
        command = canonical_command(self.region_command)
        if command != str(self.region_command):
            notes.append(f"DROPPED region_command: {self.region_command!r} is this pack's own "
                         f"grouping; the framework files it under {command!r}")
        put(self, "region_command", command)
        for name in ("executable_instruments", "positioning_sources", "native_languages",
                     "source_classes", "institutional_flow_sources", "custom_miners"):
            put(self, name, _str_tuple(getattr(self, name)))
        cb = _coerce_row(CentralBank, self.central_bank, "central_bank", notes)
        put(self, "central_bank", cb if cb is not None else CentralBank(name=""))
        hol = _coerce_row(HolidayRule, self.holidays_rule, "holidays_rule", notes)
        put(self, "holidays_rule", hol if hol is not None else HolidayRule())
        for name, cls in _ROW_CLASSES:
            rows = []
            for i, item in enumerate(getattr(self, name) or ()):
                got = _coerce_row(cls, item, f"{name}[{i}]", notes)
                if got is not None:
                    rows.append(got)
            put(self, name, tuple(rows))
        put(self, "terminology", {str(k): _str_tuple(v)
                                  for k, v in dict(self.terminology or {}).items()})
        put(self, "miner_domains", {str(k): _str_tuple(v)
                                    for k, v in dict(self.miner_domains or {}).items()})
        put(self, "series", {str(k): str(v) for k, v in dict(self.series or {}).items()})
        put(self, "absent_layers", {_tok(k): str(v)
                                    for k, v in dict(self.absent_layers or {}).items()})
        rows = []
        for i, item in enumerate(self.sources or ()):
            got = _coerce_row(SourceRow, item, f"sources[{i}]", notes)
            if got is not None:
                rows.append(got)
        put(self, "sources", tuple(rows))
        for row in rows:
            if row.layer and row.layer not in SOURCE_LAYERS:
                notes.append(f"DROPPED sources[{row.id}].layer: {row.layer!r} is not one of the "
                             f"ten SOURCE_LAYERS; the source reads as UNTAGGED")
        put(self, "coercion_notes", tuple(notes))


_ROW_CLASSES = (("fixing_conventions", Fixing), ("settlement_conventions", SettlementRule),
                ("exchanges", Exchange), ("release_classes", ReleaseClass),
                ("session_windows", SessionWindow), ("policy_eras", Era),
                ("transmission_edges_seed", TransmissionSeed), ("datasets", DatasetRow),
                ("actors", ActorRow), ("domains", DomainRow))


# ------------------------------------------------------------------- the ten source layers
#: THE PRINCIPAL'S PER-COUNTRY DEPTH RULE (2026-09-17). A country is not "covered" because five
#: obvious sources were added to it. Coverage is TWO conditions at once, and both are measured:
#:
#:   (1) EVERY LAYER THAT EXISTS FOR THAT COUNTRY IS MAPPED -- the pack names at least one
#:       verified source in the layer, or names the layer ABSENT WITH A REASON. A layer nobody
#:       has looked at is UNMAPPED, which is a third state and never a quiet zero.
#:   (2) AUTOMATIC DISCOVERY IS STILL ADDING SOURCES -- a non-zero rate of new rows for that
#:       country in the registry's `sources` table over the trailing window. A country whose
#:       every layer is mapped and whose discovery has stopped is STALLED, not covered: it means
#:       the scouts ran out of ideas, not that the ground ran out of sources.
#:
#: The ten layers are the vocabulary every country pack tags its sources with. They are ordered
#: from the most official to the most derived, and the last two are the ones a desk that only
#: reads press releases never reaches: PHYSICAL_ECONOMY (ports, power, freight, satellite,
#: tenders) and SOURCE_GRAPH (what the other nine cite, follow and argue with).
SOURCE_LAYERS: tuple[str, ...] = (
    "official",            # the state: central bank, statistics office, customs, treasury
    "institutional",       # exchanges, clearers, banks, funds, industry associations, SOEs
    "academic",            # universities, working papers, theses, conference proceedings
    "practitioner",        # broker research, trader blogs, prop desks, newsletters, podcasts
    "retail_ecology",      # forums, chat groups, margin/retail-flow statistics, brokers' own data
    "app_ecosystem",       # the trading and data apps a local actually uses, and their APIs
    "media",               # native-language financial press, TV transcripts, wire services
    "archive",             # historical records, gazettes, digitised ledgers, discontinued series
    "physical_economy",    # ports, power, freight, tenders, satellite, inventories, shipping
    "source_graph",        # what the other nine cite, link and reply to -- the expansion edges
)
#: How long a "trailing window" is for the discovery-rate half of coverage.
DISCOVERY_WINDOW_DAYS = 14
#: The states a country's coverage can be in. Four, and three of them are not "covered".
COVERAGE_STATES: tuple[str, ...] = ("COVERED", "MAPPING", "STALLED", "UNMEASURED")
COVERAGE_RULE = (
    "a country is COVERED only when every source layer is mapped or declared absent WITH A "
    "REASON and automatic discovery is still adding sources in the trailing window; five obvious "
    "sources is not coverage, and a mapped country whose discovery rate has fallen to zero is "
    "STALLED rather than finished")


@dataclass(frozen=True)
class SourceRow:
    """One source, tagged with the ONE layer it belongs to.

    `verified` is the field that stops a wish list from counting as coverage: a root somebody
    typed is not a source until something fetched it. `absent_reason` is the other half -- a
    layer a country genuinely does not have (no retail margin statistics, no native app
    ecosystem) is DECLARED absent with the reason, which counts as mapped, and a layer nobody
    looked at is neither.
    """

    id: str = ""
    layer: str = ""
    label: str = ""
    roots: tuple[str, ...] = ()
    languages: tuple[str, ...] = ()
    licence: str = ""
    verified: bool = False
    absent_reason: str = ""
    query_terms: tuple[str, ...] = ()
    notes: str = ""


_LAYER_RE = re.compile(r"\blayer\s*[:=]\s*([a-z_]+)", re.IGNORECASE)


def parse_source_layer(text: str) -> tuple[str, str]:
    """(layer, id) for a source declared as a STRING, or ("", text) when it carries no tag.

    The shipped packs write a source class as `"<id> :: <label> :: roots=... :: languages=..."`,
    and the layer arrives either as a `layer=<name>` token anywhere in that line or as a
    `::`-delimited field that happens to be one of the ten. Both are accepted; a line with
    neither is UNTAGGED, which is reported rather than guessed -- guessing a layer would make the
    coverage number a description of this parser instead of of the country.
    """
    raw = str(text or "")
    hit = _LAYER_RE.search(raw)
    if hit and _tok(hit.group(1)) in SOURCE_LAYERS:
        layer = _tok(hit.group(1))
    else:
        layer = next((_tok(p) for p in raw.split("::") if _tok(p) in SOURCE_LAYERS), "")
    first = raw.split("::", 1)[0].strip() or raw.strip()
    return layer, first


def source_rows(pack: CountryPack) -> list[SourceRow]:
    """Every source this pack declares, structured, whichever way it declared it."""
    out: list[SourceRow] = [s for s in pack.sources if isinstance(s, SourceRow)]
    have = {s.id for s in out}
    for text in pack.source_classes:
        layer, sid = parse_source_layer(text)
        if sid in have:
            continue
        have.add(sid)
        out.append(SourceRow(id=sid, layer=layer, label=str(text),
                             languages=tuple(pack.native_languages), verified=False))
    for layer, reason in dict(pack.absent_layers).items():
        out.append(SourceRow(id=f"absent:{_tok(layer)}", layer=_tok(layer),
                             absent_reason=str(reason)))
    return out


def layer_inventory(cc: str | CountryPack, *, pack: CountryPack | None = None
                    ) -> dict[str, list[dict[str, Any]]]:
    """{layer: [sources]} for one country, every one of the ten layers present as a key.

    An empty list is a layer NOBODY HAS MAPPED, and it is present in the answer for exactly that
    reason: a dictionary that only carries the layers with sources in it cannot be used to count
    what is missing. The eleventh key, `UNTAGGED`, holds the sources whose layer the pack did not
    say -- work for the pack's author, not a silent bucket.
    """
    got = pack if pack is not None else resolve_pack(cc)
    out: dict[str, list[dict[str, Any]]] = {layer: [] for layer in SOURCE_LAYERS}
    out["UNTAGGED"] = []
    if got is None:
        return out
    for row in source_rows(got):
        key = row.layer if row.layer in SOURCE_LAYERS else "UNTAGGED"
        out[key].append({"id": row.id, "label": row.label, "roots": list(row.roots),
                         "languages": list(row.languages), "licence": row.licence,
                         "verified": bool(row.verified),
                         "absent_reason": row.absent_reason,
                         "query_terms": list(row.query_terms)})
    return out


def discovery_rate(cc: str, conn: Any = None, *, window_days: int = DISCOVERY_WINDOW_DAYS
                   ) -> dict[str, Any]:
    """New sources per day for one country over the trailing window, from the registry.

    This is the half of coverage that cannot be faked by typing: it counts rows that the SCOUTS
    added to `sources`, not rows a pack declares. An unreadable table answers UNMEASURED, which
    blocks COVERED -- absence of evidence about discovery is never evidence that discovery is
    healthy.
    """
    code = _tok(cc if isinstance(cc, str) else getattr(cc, "code", ""))
    out: dict[str, Any] = {"country": code, "window_days": int(window_days),
                           "new_sources": None, "total_sources": None, "per_day": None,
                           "measured": False, "why": ""}
    c = conn
    close = c is None
    if c is None:
        try:
            c = R.connect()
        except Exception as exc:
            out["why"] = f"the registry is unreachable: {type(exc).__name__}: {exc}"
            return out
    try:
        cutoff = (datetime.now(tz=UTC) - timedelta(days=int(window_days))).isoformat()
        row = c.execute("SELECT COUNT(*) AS n FROM sources WHERE country=? AND first_seen>=?",
                        (code, cutoff)).fetchone()
        total = c.execute("SELECT COUNT(*) AS n FROM sources WHERE country=?", (code,)).fetchone()
    except Exception as exc:
        out["why"] = f"sources unreadable: {type(exc).__name__}: {exc}"
        return out
    finally:
        if close and c is not None:
            c.close()
    n = int(row["n"] if row is not None else 0)
    out.update({"new_sources": n, "total_sources": int(total["n"] if total is not None else 0),
                "per_day": round(n / max(1, int(window_days)), 4), "measured": True})
    return out


def coverage_state(cc: str | CountryPack, conn: Any = None, *,
                   pack: CountryPack | None = None,
                   window_days: int = DISCOVERY_WINDOW_DAYS) -> dict[str, Any]:
    """The country's coverage, as the principal's two conditions and nothing else."""
    got = pack if pack is not None else resolve_pack(cc)
    code = _tok(getattr(got, "code", cc) if got is not None else cc)
    inventory = layer_inventory(code, pack=got)
    layers: dict[str, dict[str, Any]] = {}
    for layer in SOURCE_LAYERS:
        rows = inventory[layer]
        verified = [r for r in rows if r["verified"]]
        declared_absent = [r for r in rows if r["absent_reason"]]
        if declared_absent:
            state, why = "ABSENT_DECLARED", str(declared_absent[0]["absent_reason"])
        elif verified:
            state, why = "MAPPED", f"{len(verified)} verified source(s)"
        elif rows:
            state, why = ("DECLARED_UNVERIFIED",
                          f"{len(rows)} declared source(s), none fetched yet")
        else:
            state, why = "UNMAPPED", "no source and no declared absence for this layer"
        layers[layer] = {"state": state, "sources": len(rows), "verified": len(verified),
                         "why": why}
    mapped = [k for k, v in layers.items() if v["state"] in ("MAPPED", "ABSENT_DECLARED")]
    unmapped = [k for k, v in layers.items() if v["state"] == "UNMAPPED"]
    unverified = [k for k, v in layers.items() if v["state"] == "DECLARED_UNVERIFIED"]
    disc = discovery_rate(code, conn, window_days=window_days)
    if got is None:
        state, why = "UNMEASURED", f"no country pack resolves for {code!r}"
    elif not disc["measured"]:
        state, why = "UNMEASURED", f"the discovery rate is unmeasured: {disc['why']}"
    elif unmapped or unverified:
        state = "MAPPING"
        why = (f"{len(mapped)}/{len(SOURCE_LAYERS)} layers mapped; unmapped={unmapped}; "
               f"declared but never fetched={unverified}")
    elif float(disc["per_day"] or 0.0) <= 0.0:
        state = "STALLED"
        why = (f"every layer is mapped but no new source was discovered for {code} in the last "
               f"{window_days} days; the scouts ran out of ideas, not the country out of sources")
    else:
        state = "COVERED"
        why = (f"all {len(SOURCE_LAYERS)} layers mapped or declared absent, and discovery is "
               f"still adding {disc['per_day']}/day")
    return {"country": code, "state": state, "why": why, "layers": layers,
            "layers_mapped": len(mapped), "layers_total": len(SOURCE_LAYERS),
            "layers_unmapped": unmapped, "layers_unverified": unverified,
            "untagged_sources": len(inventory["UNTAGGED"]), "discovery": disc,
            "rule": COVERAGE_RULE}


def native_query_seeds(cc: str | CountryPack, layer: str = "", *,
                       pack: CountryPack | None = None) -> list[dict[str, Any]]:
    """Native queries for one country and one layer, in the country's OWN script.

    THE ORDER IS THE POINT: native queries -> native sources -> native terminology -> native
    authors -> native code and community, and TRANSLATION ONLY AFTER RETRIEVAL. An English query
    against an English index cannot reach the forum where a local desk explains its own
    settlement convention, so nothing here is translated and nothing is generated from English.
    The terms come from the pack's own terminology (keyed by the layer when the pack tags it that
    way, else from every domain), and each is also emitted site-scoped to the layer's declared
    roots so a crawler can go straight at the ground rather than at a search engine's idea of it.
    """
    got = pack if pack is not None else resolve_pack(cc)
    if got is None:
        return []
    want = _tok(layer) if layer else ""
    inventory = layer_inventory(getattr(got, "code", ""), pack=got)
    terms: list[tuple[str, str]] = []
    vocab = dict(got.terminology)
    if want and want in vocab:
        terms.extend((want, t) for t in vocab[want])
    else:
        for domain, words in vocab.items():
            terms.extend((domain, t) for t in words)
    roots: list[str] = []
    extra: list[str] = []
    for row in inventory.get(want, []) if want else []:
        roots.extend(str(r) for r in row.get("roots") or [])
        extra.extend(str(t) for t in row.get("query_terms") or [])
    terms.extend((want or "layer", t) for t in extra)
    langs = list(got.native_languages) or ["UNMEASURED"]
    out: list[dict[str, Any]] = []
    for domain, term in terms:
        out.append({"country": getattr(got, "code", ""), "layer": want or "all",
                    "domain": domain, "query": term, "languages": langs,
                    "site_scoped": [f"site:{r} {term}" for r in roots[:6]],
                    "translate": "after retrieval only"})
    return out


#: A resolver the desk installs so `layer_inventory("kr")` works from a code alone. Module-level
#: so the coverage-tensor organ can point it at a loaded pack table instead of the filesystem.
PACK_RESOLVER: Callable[[str], CountryPack | None] | None = None
_PACK_CACHE: dict[str, CountryPack | None] = {}


def resolve_pack(cc: str | CountryPack) -> CountryPack | None:
    """One country's pack from its code: the installed resolver, then the desk's pack directory.

    Two export shapes are accepted, `PACK` and `pack()`, because the country departments ship the
    second: they build the dataclass through a LAZY import of this module so the department stays
    importable on a tree where this framework has not landed.
    """
    if isinstance(cc, CountryPack):
        return cc
    code = _tok(cc)
    if code in _PACK_CACHE:
        return _PACK_CACHE[code]
    got: CountryPack | None = None
    if PACK_RESOLVER is not None:
        try:
            got = PACK_RESOLVER(code)
        except Exception:
            got = None
    if got is None:
        got = _load_pack_file(code)
    _PACK_CACHE[code] = got
    return got


def _load_pack_file(code: str) -> CountryPack | None:
    path = DESK / "research" / "countries" / code / "pack.py"
    if not path.exists():
        return None
    for p in (str(DESK), str(DESK / "research"), str(ROOT)):
        if p not in sys.path:
            sys.path.insert(0, p)
    mod: Any = None
    try:
        mod = importlib.import_module(f"research.countries.{code}.pack")
    except Exception:
        try:
            spec = importlib.util.spec_from_file_location(f"country_{code}_pack", path)
            if spec is None or spec.loader is None:
                return None
            mod = importlib.util.module_from_spec(spec)
            sys.modules[spec.name] = mod
            spec.loader.exec_module(mod)
        except Exception:
            return None
    got = getattr(mod, "PACK", None)
    if not isinstance(got, CountryPack):
        factory = getattr(mod, "pack", None)
        if callable(factory):
            try:
                got = factory()
            except Exception:
                return None
    return got if isinstance(got, CountryPack) else None


# --------------------------------------------------------------------------- the tape objects
@dataclass(frozen=True)
class Bars:
    """One instrument's tape as arrays. `times` is UTC datetime64[ns], strictly increasing."""

    symbol: str
    timeframe: str
    times: np.ndarray
    close: np.ndarray
    high: np.ndarray | None = None
    low: np.ndarray | None = None
    volume: np.ndarray | None = None
    spread: np.ndarray | None = None

    def __len__(self) -> int:
        return int(self.close.size)


@dataclass(frozen=True)
class DataSeries:
    """One dated macro/positioning series. `dates` is datetime64[D]; `values` is float."""

    name: str
    dates: np.ndarray
    values: np.ndarray

    def __len__(self) -> int:
        return int(self.values.size)


# --------------------------------------------------------------------------- small helpers
def _now() -> str:
    return datetime.now(tz=UTC).isoformat(timespec="seconds")


def _tok(value: Any) -> str:
    text = " ".join(str(value or "").strip().lower().replace("-", " ").replace("_", " ").split())
    return text.replace(" ", "_") or "unknown"


def _read_json(path: Path) -> Any:
    try:
        return json.loads(Path(path).read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return None


_UNIVERSE_CACHE: dict[str, Any] = {}


def universe() -> dict[str, dict[str, Any]]:
    """The broker's own registry, or {} when it is not on this box. ABSENCE IS NOT PERMISSION and
    it is not a refusal: `validate_pack` reports which of the two it measured against."""
    path = Path(UNIVERSE_JSON)
    try:
        st = path.stat()
        key = f"{path}|{st.st_size}|{int(st.st_mtime)}"
    except OSError:
        _UNIVERSE_CACHE.clear()
        return {}
    if _UNIVERSE_CACHE.get("key") == key:
        cached: dict[str, dict[str, Any]] = _UNIVERSE_CACHE["doc"]
        return cached
    doc = _read_json(path)
    out: dict[str, dict[str, Any]] = ({str(k): v for k, v in doc.items() if isinstance(v, dict)}
                                      if isinstance(doc, dict) else {})
    _UNIVERSE_CACHE.clear()
    _UNIVERSE_CACHE.update({"key": key, "doc": out})
    return out


_DESK_MODULES: dict[str, Any] = {}


def desk_module(name: str) -> Any:
    """Lazily import one desk research organ, or None when it is not on this box.

    A `libs/` module may not DEPEND on the desk tree -- but the twelve transformation miners, the
    graveyard and the residual engine already exist there and reimplementing them here would be
    two machines answering one question differently. So they are reached optionally: absent, the
    miner that wanted one reports UNMEASURED naming the module, which is a measurement of this
    box rather than a silent branch.
    """
    if name in _DESK_MODULES:
        return _DESK_MODULES[name]
    mod: Any = None
    if (DESK / "research" / f"{name}.py").exists():
        for p in (str(DESK), str(DESK / "research"), str(ROOT)):
            if p not in sys.path:
                sys.path.insert(0, p)
        try:
            mod = importlib.import_module(name)
        except Exception:
            mod = None
    _DESK_MODULES[name] = mod
    return mod


def region_mandate_module() -> Any:
    """`libs.research.region_mandate` when a sibling builder has landed it, else None."""
    try:
        return importlib.import_module("libs.research.region_mandate")
    except Exception:
        return None


# --------------------------------------------------------------------------- calendar maths
def parse_day(text: Any) -> np.datetime64 | None:
    """One ISO date as datetime64[D], or None. Never raises: a malformed pack row is counted."""
    s = str(text or "").strip()[:10]
    if len(s) != 10:
        return None
    try:
        return np.datetime64(s, "D")
    except ValueError:
        return None


def parse_days(values: Sequence[Any]) -> np.ndarray:
    """A pack's date list as a sorted unique datetime64[D] array; unparseable rows are dropped
    by the caller's count, never by silence (`validate_pack` names them)."""
    out = [d for d in (parse_day(v) for v in values) if d is not None]
    if not out:
        return np.empty(0, dtype="datetime64[D]")
    return np.unique(np.array(out, dtype="datetime64[D]"))


def parse_hhmm(text: Any) -> tuple[int, int] | None:
    s = str(text or "").strip()
    if len(s) < 4 or ":" not in s:
        return None
    hh, _, mm = s.partition(":")
    try:
        h, m = int(hh), int(mm[:2])
    except ValueError:
        return None
    return (h, m) if 0 <= h < 24 and 0 <= m < 60 else None


def day_of_month(days: np.ndarray) -> np.ndarray:
    delta = (days.astype("datetime64[D]")
             - days.astype("datetime64[M]").astype("datetime64[D]")).astype("int64")
    out: np.ndarray = delta + 1
    return out


def month_of(days: np.ndarray) -> np.ndarray:
    return days.astype("datetime64[M]").astype("int64") % 12 + 1


def weekday_of(days: np.ndarray) -> np.ndarray:
    """Monday=0 .. Sunday=6. 1970-01-01 was a Thursday, hence the +3."""
    return (days.astype("datetime64[D]").astype("int64") + 3) % 7


def calendar_span(lo: np.datetime64, hi: np.datetime64) -> np.ndarray:
    if hi < lo:
        return np.empty(0, dtype="datetime64[D]")
    return np.arange(lo, hi + np.timedelta64(1, "D"), dtype="datetime64[D]")


def holiday_days(rule: HolidayRule, lo: np.datetime64, hi: np.datetime64) -> np.ndarray:
    """Every CLOSED day in [lo, hi] -- the explicit table, the recurring month-days, and the
    declared weekly closure. The weekly closure is declared per country, never assumed."""
    span = calendar_span(lo, hi)
    if span.size == 0:
        return span
    closed = np.zeros(span.size, dtype=bool)
    if rule.weekly_closed:
        wd = weekday_of(span)
        closed |= np.isin(wd, np.array(list(rule.weekly_closed), dtype="int64"))
    table = parse_days(rule.dates)
    if table.size:
        closed |= np.isin(span, table)
    if rule.fixed_md:
        md = np.array([f"{int(m):02d}-{int(d):02d}"
                       for m, d in zip(month_of(span), day_of_month(span), strict=True)])
        closed |= np.isin(md, np.array([str(x).strip() for x in rule.fixed_md]))
    return span[closed]


def _roll(day: int, closed: set[int], how: str) -> int | None:
    """One convention day moved off a closure, in DAYS-SINCE-EPOCH integers.

    Integers rather than datetime64 scalars on purpose: `np.ndarray.tolist()` on a datetime64[D]
    array yields `datetime.date` objects, so a set built that way silently never matches a
    datetime64 lookup -- the roll then appears to work and quietly never fires, which is the
    failure mode this function exists to prevent.
    """
    if how not in ("previous", "next"):
        return None if day in closed else day
    step = -1 if how == "previous" else 1
    cur = int(day)
    for _ in range(10):
        if cur not in closed:
            return cur
        cur += step
    return None


def settlement_days(rule: SettlementRule, pack: CountryPack, lo: np.datetime64,
                    hi: np.datetime64) -> np.ndarray:
    """One settlement/fixing convention turned into the DAYS it falls on, rolled off closures.

    This is the generic form of a gotobi: a day-of-month convention that must land on an open
    day, so the convention's economic force appears on the rolled day and NOT on the nominal one.
    A miner that tested the nominal day would measure the roll, not the flow.
    """
    span = calendar_span(lo, hi)
    if span.size == 0:
        return span
    closed = {int(v) for v in holiday_days(pack.holidays_rule, lo, hi).astype("int64")}
    kind = str(rule.kind or "").strip().lower()
    if kind == "day_of_month":
        want = np.array(list(rule.days) or [], dtype="int64")
        picked = span[np.isin(day_of_month(span), want)] if want.size else span[:0]
    elif kind in ("month_end", "quarter_end", "fiscal_year_end", "fiscal_quarter_end"):
        months = month_of(span)
        nxt = span + np.timedelta64(1, "D")
        is_last = month_of(nxt) != months
        if kind == "quarter_end":
            is_last &= np.isin(months, np.array([3, 6, 9, 12], dtype="int64"))
        elif kind in ("fiscal_year_end", "fiscal_quarter_end"):
            md = str(pack.fiscal_year_end or "").strip()
            fm = int(md[:2]) if len(md) == 5 and md[:2].isdigit() else 0
            if fm == 0:
                return span[:0]
            want_m = ([fm] if kind == "fiscal_year_end"
                      else [((fm - 1 + 3 * k) % 12) + 1 for k in range(4)])
            is_last &= np.isin(months, np.array(want_m, dtype="int64"))
        picked = span[is_last]
    elif kind == "weekday" and rule.weekday >= 0:
        picked = span[weekday_of(span) == int(rule.weekday)]
    elif kind == "week_of_month" and rule.weekday >= 0 and rule.week_of_month > 0:
        wd = weekday_of(span) == int(rule.weekday)
        nth = ((day_of_month(span) - 1) // 7) + 1 == int(rule.week_of_month)
        picked = span[wd & nth]
    else:
        return span[:0]
    if rule.months:
        picked = picked[np.isin(month_of(picked), np.array(list(rule.months), dtype="int64"))]
    rolled = [d for d in (_roll(int(x), closed, str(rule.roll or "none"))
                          for x in picked.astype("int64")) if d is not None]
    if not rolled:
        return span[:0]
    return np.unique(np.array(rolled, dtype="int64").astype("datetime64[D]"))


def era_masks(pack: CountryPack, days: np.ndarray) -> dict[str, np.ndarray]:
    """One boolean mask per declared policy era. A pack with no eras gets one `all` era, and the
    report SAYS the country declared none rather than pretending its history is homogeneous."""
    if days.size == 0:
        return {}
    out: dict[str, np.ndarray] = {}
    for era in pack.policy_eras:
        lo, hi = parse_day(era.start), parse_day(era.end)
        if lo is None or hi is None:
            continue
        out[str(era.name)] = (days >= lo) & (days <= hi)
    if not out:
        out["all"] = np.ones(days.size, dtype=bool)
    return out


# --------------------------------------------------------------------------- the lab context
@dataclass
class LabCtx:
    """What a generic miner is handed: the loaders, the registry door, its own clock and box.

    `record` is the ONE door a miner writes discoveries through, and it stamps the country tag
    (`generator = "<code>:<miner>"`), `payload.region = code` and `payload.region_command` -- so
    every row is findable again by the region framework's `is_region_row` and by the global OS's
    per-country registers without any miner having to remember to do it.
    """

    code: str
    region_command: str = ""
    conn: Any = None
    budget_s: float = 60.0
    deadline: float = 0.0
    dry_run: bool = False
    miner: str = ""
    seed: int = 20260917
    bars_loader: Callable[[str, str], Bars | None] | None = None
    series_loader: Callable[[str], DataSeries | None] | None = None
    recorded: list[str] = field(default_factory=list)
    unmeasured: list[str] = field(default_factory=list)
    transmission_seeds: list[dict[str, Any]] = field(default_factory=list)
    axis_proposals: list[dict[str, Any]] = field(default_factory=list)
    _bars: dict[tuple[str, str], Bars | None] = field(default_factory=dict)
    _series: dict[str, DataSeries | None] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.deadline <= 0.0:
            self.deadline = time.monotonic() + float(self.budget_s)

    @property
    def tag(self) -> str:
        return f"{_tok(self.code)}:"

    def remaining_s(self) -> float:
        return max(0.0, self.deadline - time.monotonic())

    def rng(self, salt: str = "") -> np.random.Generator:
        """A seeded generator per miner+salt: two runs of one miner draw the same null, and two
        different miners never share one, so a permutation p is reproducible and not correlated
        across tests by accident."""
        h = abs(hash((self.seed, self.code, self.miner, salt))) % (2**32)
        return np.random.default_rng(h)

    def bars(self, symbol: str, timeframe: str = "H1") -> Bars | None:
        key = (str(symbol).upper(), str(timeframe).upper())
        if key in self._bars:
            return self._bars[key]
        out: Bars | None = None
        if self.bars_loader is not None:
            try:
                out = self.bars_loader(key[0], key[1])
            except Exception as exc:
                self.note(f"bars:{key[0]}:{key[1]}", f"{type(exc).__name__}: {exc}")
                out = None
        self._bars[key] = out
        return out

    def series(self, name: str) -> DataSeries | None:
        key = str(name)
        if not key:
            return None
        if key in self._series:
            return self._series[key]
        out: DataSeries | None = None
        if self.series_loader is not None:
            try:
                out = self.series_loader(key)
            except Exception as exc:
                self.note(f"series:{key}", f"{type(exc).__name__}: {exc}")
                out = None
        self._series[key] = out
        return out

    def note(self, what: str, why: str) -> None:
        """UNMEASURED, by name. The first argument is WHAT could not be measured; the second is
        which input was missing. Both, always -- `unmeasured: ["positioning"]` tells nobody
        whether the currency has no COT row or the file is not on this box."""
        row = f"{self.miner or 'lab'}/{what}: {why}"
        if row not in self.unmeasured:
            self.unmeasured.append(row)

    def seed_transmission(self, **row: Any) -> None:
        self.transmission_seeds.append({"from_country": self.code, "miner": self.miner, **row})

    def propose_axis(self, axis_id: str, name: str, definition: str, **evidence: Any) -> None:
        """A coordinate this country exposed that the desk's ontology has no word for. Recorded
        as a PROPOSAL; the transmission engine owns the write into the axis extension file."""
        self.axis_proposals.append({"axis_id": _tok(axis_id), "name": name,
                                    "definition": definition, "country": self.code,
                                    "miner": self.miner, "evidence": dict(evidence)})

    def record(self, *, mechanism: str, source_id: str = "", source_type: str = "claim",
               **fields: Any) -> tuple[str, bool]:
        """Record one discovery for this country. Returns (discovery_id, created)."""
        sid = str(source_id or self.miner or "unattributed")
        if not sid.lower().startswith(self.tag):
            sid = f"{self.tag}{sid}"
        payload = dict(fields.pop("payload", None) or {})
        payload.setdefault("region", self.code)
        payload.setdefault("country", self.code)
        payload.setdefault("region_command", self.region_command)
        payload.setdefault("miner", self.miner)
        fields.setdefault("information", MINER_INFORMATION.get(self.miner, "macro"))
        origin = str(fields.pop("origin", "EXTERNAL"))
        if self.dry_run or self.conn is None:
            return "dry-run", False
        did, created = R.record_discovery(
            source_id=sid, source_type=source_type, mechanism=mechanism, origin=origin,
            generator=f"{self.tag}{self.miner or 'unnamed'}", payload=payload, conn=self.conn,
            **fields)
        self.recorded.append(did)
        return did, created


# --------------------------------------------------------------------------- default loaders
def default_bars_loader(symbol: str, timeframe: str = "H1") -> Bars | None:
    """The desk's parquet estate, read LAZILY through pandas so this module imports without it.

    Returns None -- never raises and never a partial frame -- when the file is absent, unreadable
    or shorter than the measurement floor; the caller reports which symbol that was.
    """
    path = Path(BARS_DIR) / f"{str(symbol).upper()}_{str(timeframe).upper()}.parquet"
    if not path.exists():
        return None
    try:
        import pandas as pd

        frame = pd.read_parquet(path)
    except Exception:
        return None
    if frame is None or len(frame) == 0 or "close" not in frame.columns:
        return None
    frame = frame.tail(MAX_BARS)
    idx = frame.index
    try:
        times = np.asarray(idx.tz_convert("UTC").tz_localize(None).values, dtype="datetime64[ns]")
    except (AttributeError, TypeError):
        times = np.asarray(idx.values, dtype="datetime64[ns]")

    def col(name: str) -> np.ndarray | None:
        if name not in frame.columns:
            return None
        return np.asarray(frame[name].to_numpy(), dtype="float64")

    close = col("close")
    if close is None:
        return None
    return Bars(symbol=str(symbol).upper(), timeframe=str(timeframe).upper(), times=times,
                close=close, high=col("high"), low=col("low"), volume=col("tick_volume"),
                spread=col("spread"))


def cot_series(currency_or_symbol: str) -> DataSeries | None:
    """`data/axes/cot.json` as a dated net-positioning series, or None when the symbol has no row.

    The COT axis is keyed by the FUSION SYMBOL the CFTC market maps to (AUDUSD, XAUUSD, US500 ...)
    and stamped with `knowable_at`, not `as_of` -- so the series is point-in-time by construction
    and a country whose currency the CFTC does not publish is UNMEASURED, not zero.
    """
    doc = _read_json(COT_JSON)
    if not isinstance(doc, dict):
        return None
    want = str(currency_or_symbol).upper()
    rows = [r for r in (doc.get("rows") or [])
            if isinstance(r, dict) and str(r.get("symbol") or "").upper() == want]
    if not rows:
        return None
    pairs = [(parse_day(r.get("knowable_at")), r.get("net_pct_oi")) for r in rows]
    keep = [(d, float(v)) for d, v in pairs if d is not None and isinstance(v, (int, float))]
    if not keep:
        return None
    keep.sort(key=lambda t: t[0])
    return DataSeries(name=f"cot:{want}",
                      dates=np.array([d for d, _ in keep], dtype="datetime64[D]"),
                      values=np.array([v for _, v in keep], dtype="float64"))


# --------------------------------------------------------------------------- validation
def validate_pack(pack: CountryPack, reg: Mapping[str, Mapping[str, Any]] | None = None
                  ) -> list[str]:
    """Every way this pack is not yet a pack, named. An empty list is the only pass.

    THE TWO-LANE MANDATE IS ENFORCED HERE (2026-09-06). A country lab mints STATISTICAL
    hypotheses, so a single-name equity in its instrument list is not breadth: it spends the
    program's shared multiple-testing budget on the asset class least suited to the method, and
    every FX and metals cell in the program pays for it. An instrument the broker registry does
    not know is REFUSED too -- absence is not permission (universe policy).
    """
    known: Mapping[str, Mapping[str, Any]] = reg if reg is not None else universe()
    problems: list[str] = [f"pack row: {n}" for n in pack.coercion_notes
                           if n.startswith("FAILED")]
    if not str(pack.code).strip():
        problems.append("code: empty; every row this lab writes is tagged with it")
    elif _tok(pack.code) != str(pack.code):
        problems.append(f"code {pack.code!r}: must be the canonical token {_tok(pack.code)!r}")
    if not str(pack.name).strip():
        problems.append("name: empty")
    if pack.region_command not in REGION_COMMANDS:
        problems.append(f"region_command {pack.region_command!r}: not one of "
                        f"{list(REGION_COMMANDS)}")
    if len(str(pack.currency).strip()) != 3:
        problems.append(f"currency {pack.currency!r}: expected a 3-letter code")
    if not pack.executable_instruments:
        problems.append("executable_instruments: empty; the lab can compile no cell")
    for sym in pack.executable_instruments:
        row = known.get(sym)
        if known and row is None:
            problems.append(f"instrument {sym}: not in the broker universe at {UNIVERSE_JSON}")
            continue
        klass = " ".join(str((row or {}).get("asset_class") or "").lower()
                         .replace("_", " ").split())
        if klass in EQUITY_CLASSES:
            problems.append(f"instrument {sym}: single-name equity; the two-lane mandate "
                            f"(2026-09-06) forbids hunting it for statistical hypotheses")
    if pack.central_bank.framework not in CB_FRAMEWORKS:
        problems.append(f"central_bank.framework {pack.central_bank.framework!r}: not one of "
                        f"{list(CB_FRAMEWORKS)}")
    if pack.central_bank.decision_dates:
        bad = [d for d in pack.central_bank.decision_dates if parse_day(d) is None]
        if bad:
            problems.append(f"central_bank.decision_dates: unparseable {bad[:3]}")
    if pack.export_economy not in EXPORT_TYPES:
        problems.append(f"export_economy {pack.export_economy!r}: not one of {list(EXPORT_TYPES)}")
    if pack.retail_leverage_regime not in LEVERAGE_REGIMES:
        problems.append(f"retail_leverage_regime {pack.retail_leverage_regime!r}: not one of "
                        f"{list(LEVERAGE_REGIMES)}")
    for fx in pack.fixing_conventions:
        if parse_hhmm(fx.time_utc) is None:
            problems.append(f"fixing {fx.name}: time_utc {fx.time_utc!r} is not HH:MM")
    for sr in pack.settlement_conventions:
        if sr.kind not in SETTLEMENT_KINDS:
            problems.append(f"settlement {sr.name}: kind {sr.kind!r} not one of "
                            f"{list(SETTLEMENT_KINDS)}")
        if sr.kind == "day_of_month" and not sr.days:
            problems.append(f"settlement {sr.name}: day_of_month with no days")
        if any(not 1 <= int(d) <= 31 for d in sr.days):
            problems.append(f"settlement {sr.name}: days outside 1..31")
        if sr.kind in ("fiscal_year_end", "fiscal_quarter_end") and not pack.fiscal_year_end:
            problems.append(f"settlement {sr.name}: needs fiscal_year_end on the pack")
    if pack.fiscal_year_end and len(str(pack.fiscal_year_end)) != 5:
        problems.append(f"fiscal_year_end {pack.fiscal_year_end!r}: expected MM-DD")
    execset = {s.upper() for s in pack.executable_instruments}
    for ex in pack.exchanges:
        for sym in ex.index_symbols:
            if known and sym not in known:
                problems.append(f"exchange {ex.name}: index symbol {sym} not in the universe")
            elif sym.upper() not in execset:
                problems.append(f"exchange {ex.name}: index symbol {sym} is not declared "
                                f"executable on this pack")
    for win in pack.session_windows:
        if parse_hhmm(win.start_utc) is None or parse_hhmm(win.end_utc) is None:
            problems.append(f"session_window {win.name}: start/end must be HH:MM UTC")
    for era in pack.policy_eras:
        lo, hi = parse_day(era.start), parse_day(era.end)
        if lo is None or hi is None or hi < lo:
            problems.append(f"policy_era {era.name}: start/end unparseable or reversed")
    if not pack.native_languages:
        problems.append("native_languages: empty; native-language mining is not optional "
                        "(native queries -> native sources -> native terminology)")
    for dom, terms in dict(pack.terminology).items():
        if not terms:
            problems.append(f"terminology[{dom}]: empty")
    for entry in pack.custom_miners:
        if ":" not in str(entry):
            problems.append(f"custom_miner {entry!r}: expected a dotted 'module:function' entry")
    domain_ids = {d.id for d in pack.domains}
    for d in pack.domains:
        if not d.objects:
            problems.append(f"domain {d.id}: no research objects")
        if not d.controls:
            problems.append(f"domain {d.id}: no negative controls; an effect with no control "
                            f"cannot be told from its own selection")
    for miner, ids in dict(pack.miner_domains).items():
        for did in ids:
            if did not in domain_ids:
                problems.append(f"miner_domains[{miner}]: unknown domain {did!r}")
    for a in pack.actors:
        if not str(a.name).strip():
            problems.append("actor: an actor with no name")
        elif not str(a.falsifier).strip():
            problems.append(f"actor {a.name}: falsifier is empty; an actor with no falsifier is "
                            f"a story, and a story is not a research object")
    for seed in pack.transmission_edges_seed:
        if known and seed.asset not in known:
            problems.append(f"transmission seed -> {seed.to_country}: asset {seed.asset} is not "
                            f"in the broker universe")
        if not str(seed.to_country).strip():
            problems.append("transmission seed: no to_country")
    return problems


#: The problems that must STOP a pack from running, as opposed to the ones a miner reports and
#: works around. The split matters: refusing to mine a whole country because one of its five
#: fixings has no pinned minute would cost the desk that country, while running a pack whose
#: instruments the broker cannot execute -- or which names a single-name equity -- puts cells on
#: the docket that spend the program's shared multiple-testing budget on ground the mandate
#: excludes. So the first kind is fatal and the second kind is UNMEASURED by name.
FATAL_PREFIXES: tuple[str, ...] = ("instrument ", "executable_instruments", "region_command",
                                   "code", "currency", "pack row: FAILED", "exchange ")


def fatal_problems(problems: Sequence[str]) -> list[str]:
    """The subset of `validate_pack`'s answer that means DO NOT RUN THIS PACK."""
    return [p for p in problems if p.startswith(FATAL_PREFIXES)]


def mandate_of(pack: CountryPack) -> Any:
    """This pack as a `region_mandate.Mandate`, so the region framework's registers, frontier and
    saturation measure a COUNTRY with no new code. Returns None when the framework is absent."""
    rm = region_mandate_module()
    if rm is None:
        return None
    all_domains = tuple(d.id for d in pack.domains)
    miners = tuple(
        rm.MinerSpec(name=name, kind=MINER_KIND.get(name, "mechanism"),
                     domain_ids=tuple(pack.miner_domains.get(name) or all_domains),
                     entry=f"libs.research.country_lab:generic_{name}",
                     steerable=name not in ("central_bank_surprise", "calendar_settlement"),
                     notes=f"generic country miner for {pack.code}")
        for name in GENERIC_MINERS)
    custom = tuple(
        rm.MinerSpec(name=f"custom_{i}", kind="mechanism",
                     domain_ids=tuple(pack.miner_domains.get(f"custom_{i}") or all_domains),
                     entry=entry, notes=f"{pack.code} custom miner")
        for i, entry in enumerate(pack.custom_miners))
    return rm.Mandate(
        region=pack.code,
        mission=pack.mission or f"mine {pack.name} to exhaustion under one mandate held as data",
        actors=tuple(rm.Actor(**{f.name: getattr(a, f.name) for f in _ACTOR_FIELDS})
                     for a in pack.actors),
        domains=tuple(rm.Domain(**{f.name: getattr(d, f.name) for f in _DOMAIN_FIELDS})
                      for d in pack.domains),
        instruments=tuple(pack.executable_instruments),
        native_languages=tuple(pack.native_languages),
        terminology=dict(pack.terminology),
        source_classes=tuple(pack.source_classes),
        datasets=tuple(rm.DatasetSpec(**{f.name: getattr(ds, f.name) for f in _DATASET_FIELDS})
                       for ds in pack.datasets),
        miners=miners + custom,
        capital_authority=False,
        controls_default=("matched days", "randomised dates", "adjacent days",
                          "other currencies"),
    )


# --------------------------------------------------------------------------- measurement kernel
def log_returns(close: np.ndarray) -> np.ndarray:
    """Bar-to-bar log returns, first element 0. Non-positive prices give 0, never a nan that
    silently poisons a mean three functions later."""
    c = np.asarray(close, dtype="float64")
    out = np.zeros(c.size, dtype="float64")
    if c.size < 2:
        return out
    prev, cur = c[:-1], c[1:]
    ok = (prev > 0) & (cur > 0) & np.isfinite(prev) & np.isfinite(cur)
    step = np.zeros(cur.size, dtype="float64")
    step[ok] = np.log(cur[ok] / prev[ok])
    out[1:] = step
    return out


def forward_returns(close: np.ndarray, horizon: int = 1) -> np.ndarray:
    """log(close[i+h] / close[i]); the last h entries are nan and are DROPPED by every caller,
    never zero-filled -- a zero at the end of a series is an invented observation."""
    c = np.asarray(close, dtype="float64")
    out = np.full(c.size, np.nan, dtype="float64")
    h = max(1, int(horizon))
    if c.size <= h:
        return out
    a, b = c[:-h], c[h:]
    ok = (a > 0) & (b > 0) & np.isfinite(a) & np.isfinite(b)
    vals = np.full(a.size, np.nan, dtype="float64")
    vals[ok] = np.log(b[ok] / a[ok])
    out[:-h] = vals
    return out


def bar_days(bars: Bars) -> np.ndarray:
    return np.asarray(bars.times, dtype="datetime64[ns]").astype("datetime64[D]")


def bar_hours(bars: Bars) -> np.ndarray:
    """Minutes since UTC midnight for every bar -- the hour-of-day coordinate every matched
    control and every session window is measured on."""
    t = np.asarray(bars.times, dtype="datetime64[ns]")
    out: np.ndarray = ((t.astype("datetime64[m]") - t.astype("datetime64[D]"))
                       .astype("timedelta64[m]").astype("int64"))
    return out


def permutation_p(observed: float, draws: np.ndarray, two_sided: bool = True) -> float:
    """(1 + #{draw at least as extreme}) / (1 + n). The +1 is not decoration: with 200 draws the
    smallest p a permutation test can honestly report is 1/201, and reporting 0 claims a
    precision the draw count does not have."""
    d = np.asarray(draws, dtype="float64")
    d = d[np.isfinite(d)]
    if d.size == 0 or not math.isfinite(observed):
        return 1.0
    hit = np.abs(d) >= abs(observed) if two_sided else d >= observed
    return float((1.0 + float(hit.sum())) / (1.0 + d.size))


def _matched_control_mask(days: np.ndarray, hours: np.ndarray, event: np.ndarray) -> np.ndarray:
    """Bars that are NOT event bars but share the event bars' (weekday, hour) profile.

    THIS IS THE CONTROL THAT MAKES A CALENDAR RESULT MEAN ANYTHING. Settlement days cluster on
    particular weekdays and fixings on particular hours, so comparing them with the unconditional
    mean measures the day-of-week and hour-of-day shape of the tape. The matched control holds
    both fixed and leaves only the convention.
    """
    if event.size == 0 or not event.any():
        return np.zeros(event.shape, dtype=bool)
    wd = weekday_of(days)
    profile = {(int(a), int(b)) for a, b in zip(wd[event], hours[event], strict=True)}
    keys = np.array([(int(a) << 16) | (int(b) & 0xFFFF)
                     for a, b in zip(wd, hours, strict=True)], dtype="int64")
    want = np.array([(a << 16) | (b & 0xFFFF) for a, b in profile], dtype="int64")
    out: np.ndarray = np.isin(keys, want) & ~event
    return out


def event_effect(bars: Bars, event_dates: np.ndarray, *, horizon: int = 1,
                 hours: tuple[int, int] | None = None, rng: np.random.Generator | None = None,
                 n_perm: int = N_PERM, eras: Mapping[str, np.ndarray] | None = None,
                 min_events: int = MIN_EVENTS) -> dict[str, Any]:
    """The one event study every calendar miner here runs, with its controls attached.

    Returns the signed mean forward return on the event bars, the MATCHED control mean (same
    weekday and hour, other days), the difference, a permutation p from randomised dates, the
    absolute-move ratio (a liquidity/volatility effect that a signed mean cannot see), the
    ADJACENT-day placebo, and the per-era split. An input too short or an event set too small
    returns `verdict: POORLY_MEASURED` with the counts -- never a p-value nobody should read.
    """
    out: dict[str, Any] = {"verdict": "POORLY_MEASURED", "n_events": 0, "n_control": 0,
                           "symbol": bars.symbol, "chart": bars.timeframe,
                           "horizon_bars": int(max(1, horizon))}
    n = len(bars)
    if n < MIN_BARS:
        out["why"] = f"{bars.symbol} {bars.timeframe}: {n} bars < {MIN_BARS}"
        return out
    days, hrs = bar_days(bars), bar_hours(bars)
    fwd = forward_returns(bars.close, horizon)
    finite = np.isfinite(fwd)
    in_window = np.ones(n, dtype=bool)
    if hours is not None:
        lo_m, hi_m = hours
        in_window = (hrs >= int(lo_m)) & (hrs <= int(hi_m))
    ev = np.isin(days, np.asarray(event_dates, dtype="datetime64[D]")) & in_window & finite
    n_ev = int(ev.sum())
    out["n_events"] = n_ev
    if n_ev < int(min_events):
        out["why"] = f"{n_ev} event bars < {min_events}"
        return out
    ctrl = _matched_control_mask(days, hrs, ev) & finite & in_window
    out["n_control"] = int(ctrl.sum())
    if int(ctrl.sum()) < int(min_events):
        out["why"] = f"{int(ctrl.sum())} matched control bars < {min_events}"
        return out
    mean_ev, mean_ct = float(fwd[ev].mean()), float(fwd[ctrl].mean())
    abs_ev, abs_ct = float(np.abs(fwd[ev]).mean()), float(np.abs(fwd[ctrl]).mean())
    diff = mean_ev - mean_ct
    # THE NULL RANDOMISES DATES, NEVER BARS. A calendar effect lives on DAYS: resampling
    # individual bars from inside the same event days gives a null that has already seen the
    # effect, so it is far too tight and every convention looks significant. Drawing k random
    # DAYS asks the question the miner is actually making -- are THESE dates special among all
    # dates -- and it is why a two-decision-date study honestly reports a weak p.
    gen = rng if rng is not None else np.random.default_rng(0)
    pool_bar = ctrl | ev
    pool_days = np.unique(days[pool_bar])
    ev_days = np.unique(days[ev])
    k = int(ev_days.size)
    out["n_event_days"] = k
    if k < MIN_EVENT_DAYS:
        out["why"] = (f"{k} distinct event date(s) < {MIN_EVENT_DAYS}: a randomised-date"
                      f" null cannot be drawn")
        return out
    draws = np.full(int(n_perm), np.nan, dtype="float64")
    if pool_days.size > k:
        for i in range(int(n_perm)):
            pick = gen.choice(pool_days, size=k, replace=False)
            mask = np.isin(days, pick) & pool_bar
            rest = pool_bar & ~mask
            if mask.any() and rest.any():
                draws[i] = float(fwd[mask].mean()) - float(fwd[rest].mean())
    p = permutation_p(diff, draws)
    adj = np.isin(days, np.asarray(event_dates, dtype="datetime64[D]")
                  + np.timedelta64(1, "D")) & finite & in_window & ~ev
    adjacent = float(fwd[adj].mean() - fwd[ctrl].mean()) if int(adj.sum()) >= min_events else None
    per_era: dict[str, Any] = {}
    for name, mask in (eras or {}).items():
        m = ev & mask
        c = ctrl & mask
        if int(m.sum()) >= min_events and int(c.sum()) >= min_events:
            per_era[name] = {"n": int(m.sum()),
                             "diff": round(float(fwd[m].mean() - fwd[c].mean()), 8)}
        else:
            per_era[name] = {"n": int(m.sum()), "diff": None, "why": "too few bars in this era"}
    out.update({
        "verdict": "MEASURED", "mean_event": round(mean_ev, 8), "mean_control": round(mean_ct, 8),
        "diff": round(diff, 8), "p_perm": round(p, 6),
        "abs_event": round(abs_ev, 8), "abs_control": round(abs_ct, 8),
        "abs_ratio": round(abs_ev / abs_ct, 6) if abs_ct > 0 else None,
        "adjacent_day_placebo": None if adjacent is None else round(adjacent, 8),
        "eras": per_era, "n_perm": int(n_perm),
        "significant": bool(p <= P_MAX),
        "controls": ["matched weekday+hour", "randomised dates (permutation)", "adjacent day"],
    })
    return out


def window_effect(bars: Bars, start_utc: str, end_utc: str, *,
                  eras: Mapping[str, np.ndarray] | None = None) -> dict[str, Any]:
    """One intraday window against the REST OF THE SAME DAYS: mean return, absolute move, and the
    share of the day's absolute move the window carries. The control is the same day's other
    bars, so a result cannot be a property of the days the window happens to fall on."""
    out: dict[str, Any] = {"verdict": "POORLY_MEASURED", "window": f"{start_utc}-{end_utc}",
                           "symbol": bars.symbol, "chart": bars.timeframe}
    lo, hi = parse_hhmm(start_utc), parse_hhmm(end_utc)
    if lo is None or hi is None:
        out["why"] = "window is not HH:MM-HH:MM UTC"
        return out
    n = len(bars)
    if n < MIN_BARS:
        out["why"] = f"{bars.symbol} {bars.timeframe}: {n} bars < {MIN_BARS}"
        return out
    mins = bar_hours(bars)
    lo_m, hi_m = lo[0] * 60 + lo[1], hi[0] * 60 + hi[1]
    inside = ((mins >= lo_m) & (mins < hi_m)) if lo_m <= hi_m else ((mins >= lo_m) | (mins < hi_m))
    rets = log_returns(bars.close)
    ok = np.isfinite(rets)
    if int((inside & ok).sum()) < MIN_BARS // 4 or int((~inside & ok).sum()) < MIN_BARS // 4:
        out["why"] = "too few bars inside or outside the window"
        return out
    a, b = rets[inside & ok], rets[~inside & ok]
    abs_a, abs_b = float(np.abs(a).mean()), float(np.abs(b).mean())
    per_era: dict[str, Any] = {}
    for name, mask in (eras or {}).items():
        m = inside & ok & mask
        per_era[name] = ({"n": int(m.sum()), "mean": round(float(rets[m].mean()), 8)}
                         if int(m.sum()) >= MIN_BARS // 10
                         else {"n": int(m.sum()), "mean": None, "why": "too few bars in this era"})
    out.update({"verdict": "MEASURED", "n_inside": int(a.size), "n_outside": int(b.size),
                "mean_inside": round(float(a.mean()), 8),
                "mean_outside": round(float(b.mean()), 8),
                "abs_inside": round(abs_a, 8), "abs_outside": round(abs_b, 8),
                "abs_ratio": round(abs_a / abs_b, 6) if abs_b > 0 else None,
                "eras": per_era,
                "controls": ["the same days' bars outside the window"]})
    return out


def align_daily(series: DataSeries, bars: Bars, horizon: int = 1) -> tuple[np.ndarray, np.ndarray]:
    """A dated series against an instrument's forward return on the SAME day, aligned by day.

    The series' own stamp is taken as knowable at that day's close, which is why every caller
    passes a point-in-time series (`knowable_at`, not `as_of`): this function cannot repair a
    series that was stamped with its reference date instead of its publication date.
    """
    if len(series) == 0 or len(bars) == 0:
        return np.empty(0), np.empty(0)
    days = bar_days(bars)
    fwd = forward_returns(bars.close, horizon)
    uniq = np.unique(days)
    daily = np.full(uniq.size, np.nan, dtype="float64")
    order = np.argsort(days, kind="stable")
    sd, sf = days[order], fwd[order]
    idx = np.searchsorted(sd, uniq, side="right") - 1
    ok = (idx >= 0) & np.isfinite(sf[np.clip(idx, 0, sf.size - 1)])
    daily[ok] = sf[np.clip(idx, 0, sf.size - 1)][ok]
    pos = np.searchsorted(uniq, np.asarray(series.dates, dtype="datetime64[D]"))
    valid = (pos < uniq.size) & (pos >= 0)
    pos = np.clip(pos, 0, max(0, uniq.size - 1))
    good = valid & np.isfinite(daily[pos]) & np.isfinite(series.values)
    return np.asarray(series.values, dtype="float64")[good], daily[pos][good]


def corr_with_null(x: np.ndarray, y: np.ndarray, *, rng: np.random.Generator | None = None,
                   n_perm: int = N_PERM, block: int = 5) -> dict[str, Any]:
    """Pearson correlation with a CIRCULAR-BLOCK permutation null.

    Blocks, not an i.i.d. shuffle: shuffling an autocorrelated regressor destroys its persistence
    and manufactures significance for exactly the class of variable a macro series is. The null
    rolls x by a random offset, which keeps x's own structure and destroys only its alignment
    with y -- the hypothesis actually under test.
    """
    a = np.asarray(x, dtype="float64")
    b = np.asarray(y, dtype="float64")
    ok = np.isfinite(a) & np.isfinite(b)
    a, b = a[ok], b[ok]
    if a.size < 30:
        return {"verdict": "POORLY_MEASURED", "n": int(a.size), "why": "fewer than 30 pairs"}
    a = a - a.mean()
    b = b - b.mean()
    den = float(np.sqrt((a * a).sum() * (b * b).sum()))
    r = float((a * b).sum() / den) if den > 0 else 0.0
    gen = rng if rng is not None else np.random.default_rng(0)
    draws = np.empty(int(n_perm), dtype="float64")
    for i in range(int(n_perm)):
        shift = int(gen.integers(block, max(block + 1, a.size - block)))
        rolled = np.roll(a, shift)
        d = float(np.sqrt((rolled * rolled).sum() * (b * b).sum()))
        draws[i] = float((rolled * b).sum() / d) if d > 0 else 0.0
    return {"verdict": "MEASURED", "n": int(a.size), "corr": round(r, 6),
            "p_perm": round(permutation_p(r, draws), 6),
            "significant": bool(permutation_p(r, draws) <= P_MAX),
            "null": "circular block shift of x (keeps x's autocorrelation)"}


# --------------------------------------------------------------------------- the generic miners
def _reaction_set(pack: CountryPack, reg: Mapping[str, Mapping[str, Any]]) -> list[str]:
    """The pack's own instruments plus the global set, filtered by what this box can execute.

    Both halves, always: a domestic shock measured only against domestic instruments cannot tell
    a local mechanism from a global risk day, and measured only against the global set cannot
    find the mechanism at all.
    """
    out = [s.upper() for s in pack.executable_instruments]
    for sym in GLOBAL_REACTION_SET:
        if sym in out:
            continue
        if not reg or sym in reg:
            out.append(sym)
    return out


def _eras_for(pack: CountryPack, bars: Bars) -> dict[str, np.ndarray]:
    return era_masks(pack, bar_days(bars))


def generic_central_bank_surprise(pack: CountryPack, ctx: LabCtx) -> dict[str, Any]:
    """Rate decisions: the surprise, and what it moved -- domestically and globally.

    Surprise = actual - expected where an expectation series is on this box, else actual - prior,
    and the discovery SAYS WHICH: a surprise against a prior is a different economic quantity
    (it contains the whole expected path) and reading the two as one is how a central-bank study
    quietly becomes a momentum study.
    """
    cb = pack.central_bank
    if not str(cb.name).strip():
        ctx.note("central_bank", "the pack declares no central bank")
        return {"outcome": UNMEASURED, "why": "no central bank on the pack"}
    dates = parse_days(cb.decision_dates)
    if dates.size == 0:
        ctx.note("decision_dates", f"{cb.name}: no decision dates on the pack"
                                   f" (rule: {cb.decision_calendar_rule or 'none declared'})")
        return {"outcome": UNMEASURED, "why": "no decision dates"}
    actual = ctx.series(cb.policy_rate_series) if cb.policy_rate_series else None
    expected = ctx.series(cb.expected_rate_series) if cb.expected_rate_series else None
    basis = "vs_expected" if expected is not None else ("vs_prior" if actual is not None
                                                        else "date_only")
    if actual is None:
        ctx.note("policy_rate_series",
                 f"{cb.policy_rate_series or 'not declared'}: no rate series on this box; the "
                 f"study measures the DECISION DAY, not the surprise")
    reg = universe()
    rows: list[dict[str, Any]] = []
    for sym in _reaction_set(pack, reg):
        if ctx.remaining_s() <= 0:
            break
        bars = ctx.bars(sym, "H1")
        if bars is None:
            ctx.note(f"bars:{sym}", "no H1 tape on this box")
            continue
        res = event_effect(bars, dates, horizon=4, rng=ctx.rng(sym), eras=_eras_for(pack, bars))
        res["symbol"] = sym
        rows.append(res)
    measured = [r for r in rows if r.get("verdict") == "MEASURED"]
    hits = [r for r in measured if r.get("significant")]
    n = 0
    for r in hits:
        did, created = ctx.record(
            mechanism=f"{pack.code}_central_bank_decision_reaction",
            source_id=f"central_bank:{_tok(cb.name)}", source_type="calendar",
            actor=f"{pack.name} central bank ({cb.name}) and the desks positioned into its "
                  f"decisions",
            constraint=f"the {cb.framework} framework binds the decision to a published calendar; "
                       f"whoever is wrong on the day must reprice within hours",
            economic_rationale=f"a {cb.framework} decision on a known date reprices the {sym_of(r)}"
                               f" leg; the surprise basis here is {basis}",
            assets=[sym_of(r)], horizons=["intraday"], sessions=["all"],
            regimes=["unconditional"],
            required_data=[cb.policy_rate_series or "policy rate (absent)",
                           cb.expected_rate_series or "expectation (absent)"],
            pit_requirements=["decision timestamp", "publication time of the expectation"],
            novelty=0.5, confidence=0.5,
            falsifier=f"the decision-day effect on {sym_of(r)} does not survive the matched "
                      f"weekday+hour control or the randomised-date null",
            payload={"basis": basis, "reading": r, "framework": cb.framework,
                     "publication_classes": list(cb.publication_classes)})
        n += int(created or did != "dry-run")
    return {"outcome": OK if measured else UNMEASURED, "discoveries": n, "basis": basis,
            "n_symbols": len(rows), "measured": len(measured), "significant": len(hits),
            "why": "" if measured else "no instrument carried a measurable decision-day study",
            "readings": measured[:12]}


def sym_of(row: Mapping[str, Any]) -> str:
    return str(row.get("symbol") or "")


def generic_release_surprise(pack: CountryPack, ctx: LabCtx) -> dict[str, Any]:
    """The country's scheduled statistics: each release class as its own event study."""
    if not pack.release_classes:
        ctx.note("release_classes", "the pack declares no national release calendar")
        return {"outcome": UNMEASURED, "why": "no release classes"}
    out: list[dict[str, Any]] = []
    n = 0
    for rc in pack.release_classes:
        if ctx.remaining_s() <= 0:
            break
        dates = parse_days(rc.dates)
        if dates.size == 0:
            ctx.note(f"release:{rc.name}",
                     f"no dates on the pack (cadence {rc.cadence}, source {rc.source or 'none'})")
            continue
        for sym in [s.upper() for s in pack.executable_instruments][:6]:
            bars = ctx.bars(sym, "H1")
            if bars is None:
                ctx.note(f"bars:{sym}", "no H1 tape on this box")
                continue
            res = event_effect(bars, dates, horizon=2, rng=ctx.rng(f"{rc.name}:{sym}"),
                               eras=_eras_for(pack, bars))
            res.update({"release": rc.name, "symbol": sym})
            out.append(res)
            if res.get("significant"):
                did, created = ctx.record(
                    mechanism=f"{pack.code}_release_{_tok(rc.name)}_reaction",
                    source_id=f"release:{_tok(rc.name)}", source_type="calendar",
                    actor=f"{pack.name} hedgers and macro books that must mark to the "
                          f"{rc.name} print",
                    constraint=f"the {rc.name} print lands on a published {rc.cadence} calendar "
                               f"and cannot be traded before it",
                    economic_rationale=f"scheduled {rc.name} releases reprice {sym}",
                    assets=[sym], horizons=["intraday"], sessions=["all"],
                    regimes=["unconditional"],
                    required_data=[rc.actual_series or f"{rc.name} actual (absent)",
                                   rc.expected_series or f"{rc.name} expectation (absent)"],
                    pit_requirements=["release timestamp", "revision history"],
                    novelty=0.5, confidence=0.5,
                    falsifier=f"the {rc.name} reaction on {sym} does not clear the matched "
                              f"weekday+hour control",
                    payload={"reading": res, "release": rc.name, "source": rc.source})
                n += int(created or did != "dry-run")
    measured = [r for r in out if r.get("verdict") == "MEASURED"]
    return {"outcome": OK if measured else UNMEASURED, "discoveries": n,
            "releases": len(pack.release_classes), "measured": len(measured),
            "why": "" if measured else "no release class produced a measurable study",
            "readings": measured[:12]}


def generic_calendar_settlement(pack: CountryPack, ctx: LabCtx) -> dict[str, Any]:
    """Settlement and fixing conventions as WINDOWS, with four negative controls.

    The controls are the whole point and they are named in the result: non-convention days (the
    matched control), randomised dates (the permutation null), adjacent days (the placebo that
    catches a roll), and OTHER CURRENCIES -- the same window on an instrument that does not carry
    this country's currency, which is the control that separates a settlement flow from a
    time-of-day effect the whole tape shares.
    """
    if not pack.settlement_conventions and not pack.fixing_conventions:
        ctx.note("settlement_conventions", "the pack declares no settlement or fixing convention")
        return {"outcome": UNMEASURED, "why": "no conventions declared"}
    reg = universe()
    cur = str(pack.currency).upper()
    own = [s.upper() for s in pack.executable_instruments if cur in s.upper()]
    other = [s for s in _reaction_set(pack, reg) if cur not in s.upper()][:3]
    if not own:
        own = [s.upper() for s in pack.executable_instruments]
    rows: list[dict[str, Any]] = []
    n = 0
    for rule in pack.settlement_conventions:
        if ctx.remaining_s() <= 0:
            break
        for sym in own[:4]:
            bars = ctx.bars(sym, "H1")
            if bars is None:
                ctx.note(f"bars:{sym}", "no H1 tape on this box")
                continue
            days = bar_days(bars)
            lo, hi = days.min(), days.max()
            conv = settlement_days(rule, pack, lo, hi)
            if conv.size == 0:
                ctx.note(f"settlement:{rule.name}",
                         f"the rule produced no day inside {lo}..{hi}")
                continue
            win = parse_hhmm(rule.window_utc[0]), parse_hhmm(rule.window_utc[1])
            hours = ((win[0][0] * 60 + win[0][1], win[1][0] * 60 + win[1][1])
                     if win[0] is not None and win[1] is not None else None)
            res = event_effect(bars, conv, horizon=1, hours=hours,
                               rng=ctx.rng(f"{rule.name}:{sym}"), eras=_eras_for(pack, bars))
            res.update({"convention": rule.name, "symbol": sym,
                        "n_convention_days": int(conv.size)})
            placebos: dict[str, Any] = {}
            for alt in other:
                ab = ctx.bars(alt, "H1")
                if ab is None:
                    continue
                pl = event_effect(ab, conv, horizon=1, hours=hours,
                                  rng=ctx.rng(f"{rule.name}:{alt}"),
                                  n_perm=max(50, N_PERM // 4))
                placebos[alt] = {"diff": pl.get("diff"), "p_perm": pl.get("p_perm"),
                                 "verdict": pl.get("verdict")}
            res["other_currency_placebo"] = placebos
            res["controls"] = ["non-convention matched days", "randomised dates",
                               "adjacent days", "other currencies"]
            rows.append(res)
            if res.get("significant"):
                did, created = ctx.record(
                    mechanism=f"{pack.code}_{_tok(rule.name)}_settlement_flow",
                    source_id=f"settlement:{_tok(rule.name)}", source_type="calendar",
                    actor=f"{pack.name} corporates and their settlement banks",
                    constraint=f"the {rule.name} convention forces the transaction on a dated "
                               f"calendar ({rule.kind}), rolled {rule.roll} off closures",
                    economic_rationale=f"a dated settlement convention concentrates {cur} demand "
                                       f"into {rule.window_utc[0] or 'the day'}",
                    assets=[sym], horizons=["intraday"], sessions=["all"],
                    regimes=["unconditional"],
                    required_data=["the national holiday table", "the convention's roll rule"],
                    pit_requirements=["the calendar is knowable in advance"],
                    novelty=0.55, confidence=0.5,
                    falsifier=f"the {rule.name} effect survives on an instrument carrying no "
                              f"{cur} leg, which would make it a time-of-day effect",
                    payload={"reading": res, "convention": rule.name, "kind": rule.kind})
                n += int(created or did != "dry-run")
    for fx in pack.fixing_conventions:
        if ctx.remaining_s() <= 0:
            break
        hhmm = parse_hhmm(fx.time_utc)
        if hhmm is None:
            ctx.note(f"fixing:{fx.name}", f"time_utc {fx.time_utc!r} is not HH:MM")
            continue
        for sym in (list(fx.instruments) or own)[:3]:
            bars = ctx.bars(str(sym).upper(), "M15") or ctx.bars(str(sym).upper(), "H1")
            if bars is None:
                ctx.note(f"bars:{sym}", "no M15 or H1 tape on this box")
                continue
            end_m = (hhmm[0] * 60 + hhmm[1] + max(5, int(fx.window_minutes))) % (24 * 60)
            res = window_effect(bars, fx.time_utc, f"{end_m // 60:02d}:{end_m % 60:02d}",
                                eras=_eras_for(pack, bars))
            res.update({"fixing": fx.name, "symbol": str(sym).upper(), "dst_rule": fx.dst_rule})
            rows.append(res)
    measured = [r for r in rows if r.get("verdict") == "MEASURED"]
    return {"outcome": OK if measured else UNMEASURED, "discoveries": n,
            "conventions": len(pack.settlement_conventions),
            "fixings": len(pack.fixing_conventions), "measured": len(measured),
            "why": "" if measured else "no convention produced a measurable window",
            "readings": measured[:12]}


def generic_holiday_liquidity(pack: CountryPack, ctx: LabCtx) -> dict[str, Any]:
    """What the country's OWN closure does to instruments that stay open.

    MECHANISM REQUIRED, and this one has it: when the local market is shut, the participants who
    normally absorb local flow are absent, so the same order meets a thinner book. The claim is
    therefore about ABSOLUTE MOVE and spread, not about direction -- a signed holiday effect is
    almost always a calendar artefact, and this miner does not record one.
    """
    closed = pack.holidays_rule
    if not closed.dates and not closed.fixed_md:
        ctx.note("holidays_rule", "the pack declares no holiday table or recurring rule")
        return {"outcome": UNMEASURED, "why": "no holiday table"}
    rows: list[dict[str, Any]] = []
    n = 0
    for sym in [s.upper() for s in pack.executable_instruments][:6]:
        if ctx.remaining_s() <= 0:
            break
        bars = ctx.bars(sym, "H1")
        if bars is None:
            ctx.note(f"bars:{sym}", "no H1 tape on this box")
            continue
        days = bar_days(bars)
        hol = holiday_days(closed, days.min(), days.max())
        weekly = set(closed.weekly_closed)
        hol = hol[~np.isin(weekday_of(hol), np.array(list(weekly) or [-1], dtype="int64"))]
        if hol.size == 0:
            ctx.note(f"holidays:{sym}", "no non-weekend closure inside the tape's span")
            continue
        res = event_effect(bars, hol, horizon=1, rng=ctx.rng(sym), eras=_eras_for(pack, bars))
        res["symbol"] = sym
        res["mechanism_claim"] = ("the local absorbers are absent, so the same order meets a "
                                  "thinner book: the claim is on |move| and spread, not direction")
        rows.append(res)
        ratio = res.get("abs_ratio")
        if res.get("verdict") == "MEASURED" and isinstance(ratio, float) and ratio > 1.0:
            did, created = ctx.record(
                mechanism=f"{pack.code}_domestic_holiday_thin_book",
                source_id="holidays", source_type="calendar",
                actor=f"{pack.name} domestic market makers and banks, absent on national closures",
                constraint="a national closure removes the local absorbers while the instrument "
                           "keeps trading offshore",
                economic_rationale="fewer absorbers means a larger price impact per unit of "
                                   "order flow; the observable is the absolute move, not a sign",
                assets=[sym], horizons=["intraday"], sessions=["all"], regimes=["unconditional"],
                required_data=["the national holiday table"],
                pit_requirements=["the holiday calendar is knowable in advance"],
                novelty=0.5, confidence=0.45,
                falsifier="the absolute-move ratio on closures is not above 1 against the "
                          "matched weekday+hour control",
                payload={"reading": res, "n_holidays": int(hol.size)})
            n += int(created or did != "dry-run")
    measured = [r for r in rows if r.get("verdict") == "MEASURED"]
    return {"outcome": OK if measured else UNMEASURED, "discoveries": n,
            "measured": len(measured),
            "why": "" if measured else "no instrument carried a measurable closure study",
            "readings": measured[:8]}


def generic_session_microstructure(pack: CountryPack, ctx: LabCtx) -> dict[str, Any]:
    """The country's own session windows, in UTC, on the tape the desk already holds."""
    windows = list(pack.session_windows)
    if not windows:
        for ex in pack.exchanges:
            if parse_hhmm(ex.open_utc) and parse_hhmm(ex.close_utc):
                windows.append(SessionWindow(name=f"{ex.name}_cash", start_utc=ex.open_utc,
                                             end_utc=ex.close_utc))
    if not windows:
        ctx.note("session_windows", "the pack declares no session window and no exchange hours")
        return {"outcome": UNMEASURED, "why": "no session windows"}
    rows: list[dict[str, Any]] = []
    n = 0
    for win in windows:
        if ctx.remaining_s() <= 0:
            break
        for sym in [s.upper() for s in pack.executable_instruments][:5]:
            bars = ctx.bars(sym, "H1")
            if bars is None:
                ctx.note(f"bars:{sym}", "no H1 tape on this box")
                continue
            res = window_effect(bars, win.start_utc, win.end_utc, eras=_eras_for(pack, bars))
            res.update({"session": win.name, "symbol": sym})
            rows.append(res)
            ratio = res.get("abs_ratio")
            if res.get("verdict") == "MEASURED" and isinstance(ratio, float) and ratio > 1.2:
                did, created = ctx.record(
                    mechanism=f"{pack.code}_{_tok(win.name)}_session_concentration",
                    source_id=f"session:{_tok(win.name)}", source_type="microstructure",
                    actor=f"{pack.name} onshore participants, active only in their own session",
                    constraint="an onshore book can only transact while its own market is open",
                    economic_rationale=f"the {win.name} window carries a disproportionate share "
                                       f"of {sym}'s daily absolute move",
                    assets=[sym], horizons=["intraday"], sessions=[_tok(win.name)],
                    regimes=["unconditional"], required_data=["H1 bars"],
                    pit_requirements=["bar timestamps in UTC"],
                    novelty=0.4, confidence=0.5,
                    falsifier=f"the {win.name} window's absolute move is not above the same "
                              f"days' other bars",
                    payload={"reading": res, "window_utc": [win.start_utc, win.end_utc]})
                n += int(created or did != "dry-run")
    measured = [r for r in rows if r.get("verdict") == "MEASURED"]
    return {"outcome": OK if measured else UNMEASURED, "discoveries": n,
            "windows": len(windows), "measured": len(measured),
            "why": "" if measured else "no window produced a measurable reading",
            "readings": measured[:12]}


def generic_positioning(pack: CountryPack, ctx: LabCtx) -> dict[str, Any]:
    """Speculative positioning against the country's own instruments.

    COT when the CFTC publishes this currency, and the pack says under which symbol. When it does
    not, the answer is UNMEASURED plus a DATASET DISCOVERY naming the local positioning source
    the pack declares -- an absent series is a thing to acquire, not a question to drop.
    """
    key = str(pack.cot_currency or "").upper()
    series = cot_series(key) if key else None
    if series is None:
        ctx.note("positioning",
                 f"cot_currency {key or 'not declared'}: no row in {COT_JSON.name}; the local "
                 f"sources the pack names are {list(pack.positioning_sources) or 'none'}")
        n = 0
        for src in pack.positioning_sources:
            did, created = ctx.record(
                mechanism=f"{pack.code}_positioning_dataset_gap",
                source_id=f"dataset:{_tok(src)}", source_type="dataset",
                actor=f"{pack.name} leveraged and commercial participants",
                constraint="crowded positioning must be unwound into the same liquidity that "
                           "absorbed it",
                economic_rationale=f"{src} publishes the country's own positioning; it is not on "
                                   f"this box, so the mechanism is unaskable until it is",
                assets=list(pack.executable_instruments[:3]), horizons=["multi_day"],
                sessions=["all"], regimes=["unconditional"], required_data=[src],
                pit_requirements=["publication date, not reference date"],
                novelty=0.6, confidence=0.3,
                falsifier="once acquired, positioning extremes do not precede reversals",
                payload={"acquire": src, "why": "the country has no CFTC row"})
            n += int(created or did != "dry-run")
        return {"outcome": UNMEASURED, "discoveries": n,
                "why": f"no COT row for {key or 'an undeclared currency'}",
                "dataset_discoveries": n}
    rows: list[dict[str, Any]] = []
    n = 0
    for sym in [s.upper() for s in pack.executable_instruments][:5]:
        if ctx.remaining_s() <= 0:
            break
        bars = ctx.bars(sym, "D1") or ctx.bars(sym, "H1")
        if bars is None:
            ctx.note(f"bars:{sym}", "no D1 or H1 tape on this box")
            continue
        x, y = align_daily(series, bars, horizon=5)
        res = corr_with_null(x, y, rng=ctx.rng(sym))
        res.update({"symbol": sym, "series": series.name})
        rows.append(res)
        if res.get("significant"):
            did, created = ctx.record(
                mechanism=f"{pack.code}_positioning_extreme_reversal",
                source_id=f"positioning:{_tok(series.name)}", source_type="positioning",
                actor=f"{pack.name} leveraged speculative accounts",
                constraint="a crowded book must be unwound into the liquidity that absorbed it",
                economic_rationale=f"net speculative positioning in {sym} predicts its forward "
                                   f"return",
                assets=[sym], horizons=["multi_day"], sessions=["all"],
                regimes=["unconditional"], required_data=[series.name],
                pit_requirements=["knowable_at, never as_of"], novelty=0.45, confidence=0.5,
                falsifier=f"the positioning-forward-return correlation on {sym} does not clear "
                          f"a circular-block null",
                payload={"reading": res})
            n += int(created or did != "dry-run")
    measured = [r for r in rows if r.get("verdict") == "MEASURED"]
    return {"outcome": OK if measured else UNMEASURED, "discoveries": n,
            "series": series.name, "measured": len(measured),
            "why": "" if measured else "the COT series aligned with no instrument's tape",
            "readings": measured[:8]}


def generic_carry_funding(pack: CountryPack, ctx: LabCtx) -> dict[str, Any]:
    """The rate differential, when the pack names both legs and this box holds them."""
    dom = str(pack.series.get("policy_rate") or pack.central_bank.policy_rate_series or "")
    foreign = str(pack.series.get("foreign_policy_rate") or "")
    a = ctx.series(dom) if dom else None
    b = ctx.series(foreign) if foreign else None
    if a is None or b is None:
        ctx.note("carry", f"rate differential needs both legs: domestic "
                          f"{dom or 'not declared'} "
                          f"({'present' if a is not None else 'absent'}), foreign "
                          f"{foreign or 'not declared'} "
                          f"({'present' if b is not None else 'absent'})")
        return {"outcome": UNMEASURED, "why": "one or both rate legs absent"}
    common = np.intersect1d(a.dates, b.dates)
    if common.size < 60:
        ctx.note("carry", f"only {int(common.size)} common dated observations across the two legs")
        return {"outcome": UNMEASURED, "why": "too few common observations"}
    diff = DataSeries(
        name=f"carry:{dom}-{foreign}", dates=common,
        values=(a.values[np.searchsorted(a.dates, common)]
                - b.values[np.searchsorted(b.dates, common)]))
    rows: list[dict[str, Any]] = []
    n = 0
    for sym in [s.upper() for s in pack.executable_instruments][:5]:
        bars = ctx.bars(sym, "D1") or ctx.bars(sym, "H1")
        if bars is None:
            ctx.note(f"bars:{sym}", "no D1 or H1 tape on this box")
            continue
        x, y = align_daily(diff, bars, horizon=20)
        res = corr_with_null(x, y, rng=ctx.rng(sym))
        res.update({"symbol": sym, "series": diff.name})
        rows.append(res)
        if res.get("significant"):
            did, created = ctx.record(
                mechanism=f"{pack.code}_rate_differential_carry",
                source_id=f"carry:{_tok(dom)}", source_type="macro",
                actor=f"{pack.name} hedged foreign investors and the banks funding them",
                constraint="a hedged position pays the differential every roll, whatever the "
                           "spot view",
                economic_rationale=f"the {dom} - {foreign} differential prices the forward and "
                                   f"therefore the hedged return on {sym}",
                assets=[sym], horizons=["multi_day"], sessions=["all"],
                regimes=["unconditional"], required_data=[dom, foreign],
                pit_requirements=["series publication dates"], novelty=0.4, confidence=0.5,
                falsifier=f"the differential's correlation with {sym}'s forward return does not "
                          f"clear a circular-block null",
                payload={"reading": res})
            n += int(created or did != "dry-run")
    measured = [r for r in rows if r.get("verdict") == "MEASURED"]
    return {"outcome": OK if measured else UNMEASURED, "discoveries": n,
            "series": diff.name, "measured": len(measured),
            "why": "" if measured else "the differential aligned with no instrument's tape",
            "readings": measured[:8]}


_FLOW_KEYS: tuple[str, ...] = ("trade_balance", "exports", "imports", "current_account", "pmi",
                               "industrial_production")


def generic_corporate_flow(pack: CountryPack, ctx: LabCtx) -> dict[str, Any]:
    """The export/import cycle against the currency, with a CAUSAL CARD per reading.

    The card is not decoration: a trade-balance correlation with no actor, no constraint and no
    counterparty is a statistic, and the desk's compiler refuses a discovery that cannot say who
    was forced to do what. Every row here names the exporter, the invoice, and the bank.
    """
    loaded = {k: ctx.series(str(pack.series.get(k) or "")) for k in _FLOW_KEYS
              if pack.series.get(k)}
    have: dict[str, DataSeries] = {k: v for k, v in loaded.items() if v is not None}
    missing = [k for k in _FLOW_KEYS if k not in have]
    if not have:
        ctx.note("corporate_flow",
                 f"none of {list(_FLOW_KEYS)} is declared on the pack's `series` and present on "
                 f"this box")
        return {"outcome": UNMEASURED, "why": "no trade or export series"}
    for k in missing:
        ctx.note("corporate_flow", f"{k}: not declared or not on this box")
    cur = str(pack.currency).upper()
    syms = [s.upper() for s in pack.executable_instruments if cur in s.upper()][:4] or \
           [s.upper() for s in pack.executable_instruments][:4]
    rows: list[dict[str, Any]] = []
    n = 0
    for key, series in have.items():
        if ctx.remaining_s() <= 0:
            break
        for sym in syms:
            bars = ctx.bars(sym, "D1") or ctx.bars(sym, "H1")
            if bars is None:
                ctx.note(f"bars:{sym}", "no D1 or H1 tape on this box")
                continue
            x, y = align_daily(series, bars, horizon=20)
            res = corr_with_null(x, y, rng=ctx.rng(f"{key}:{sym}"))
            res.update({"symbol": sym, "series": series.name, "flow": key})
            rows.append(res)
            if res.get("significant"):
                did, created = ctx.record(
                    mechanism=f"{pack.code}_{_tok(key)}_repatriation_flow",
                    source_id=f"flow:{_tok(key)}", source_type="macro",
                    actor=f"{pack.name} exporters and importers, and the banks that settle their "
                          f"invoices",
                    constraint="an invoice denominated in a foreign currency must be converted; "
                               "the conversion is not discretionary and follows the shipment",
                    counterparty=f"the {pack.name} banking system's corporate desks",
                    economic_rationale=f"the {key} cycle is the size of the conversion that must "
                                       f"pass through {sym}",
                    assets=[sym], horizons=["multi_day"], sessions=["all"],
                    regimes=["unconditional"], required_data=[series.name],
                    pit_requirements=["publication lag of the national statistic"],
                    novelty=0.5, confidence=0.5,
                    falsifier=f"the {key} correlation with {sym} does not clear a circular-block "
                              f"null, or reverses in another era",
                    payload={"reading": res, "causal_card": {
                        "actor": "exporters and importers", "constraint": "invoice conversion",
                        "observable": series.name, "flow": key, "asset": sym}})
                n += int(created or did != "dry-run")
    measured = [r for r in rows if r.get("verdict") == "MEASURED"]
    return {"outcome": OK if measured else UNMEASURED, "discoveries": n,
            "series": sorted(have), "missing": missing, "measured": len(measured),
            "why": "" if measured else "no flow series aligned with an instrument's tape",
            "readings": measured[:8]}


def generic_institutional_flow(pack: CountryPack, ctx: LabCtx) -> dict[str, Any]:
    """Public allocation evidence: the country's own reserve, pension and insurance managers.

    Nothing here is measured from a price. A sovereign fund's rebalancing band is PUBLISHED, and
    the discovery this miner records is the SOURCE plus the constraint it documents -- a lead for
    the deepening worker and the acquisition lane, honestly marked as unmeasured until the series
    lands, rather than a correlation invented to fill the slot.
    """
    if not pack.institutional_flow_sources:
        ctx.note("institutional_flow",
                 "the pack declares no public allocation source (reserve manager, pension fund, "
                 "insurer)")
        return {"outcome": UNMEASURED, "why": "no institutional sources declared"}
    n = 0
    for src in pack.institutional_flow_sources:
        did, created = ctx.record(
            mechanism=f"{pack.code}_institutional_allocation_band",
            source_id=f"institution:{_tok(src)}", source_type="institutional",
            actor=f"{src}, a {pack.name} public allocator with a published mandate",
            constraint="a published allocation band forces a rebalance when a market move takes "
                       "the portfolio outside it, on the fund's own calendar and not on a view",
            counterparty="the dealers who must warehouse the rebalance",
            economic_rationale=f"{src}'s band and reporting calendar are public, so the DATE of "
                               f"the forced transaction is knowable in advance",
            assets=list(pack.executable_instruments[:3]), horizons=["multi_day"],
            sessions=["all"], regimes=["unconditional"],
            required_data=[f"{src} holdings or allocation disclosures"],
            pit_requirements=["disclosure date, never the reference quarter"],
            novelty=0.6, confidence=0.4,
            falsifier="the fund's disclosures show no band and no calendar, so nothing is forced",
            payload={"source": src, "status": "lead: the series is not on this box"})
        n += int(created or did != "dry-run")
        ctx.note("institutional_flow", f"{src}: holdings series not on this box; recorded as a "
                                       f"lead for acquisition")
    return {"outcome": OK, "discoveries": n, "sources": list(pack.institutional_flow_sources),
            "why": "recorded as acquisition leads; no holdings series is on this box"}


def generic_equity_mechanics(pack: CountryPack, ctx: LabCtx) -> dict[str, Any]:
    """The country's index: its open, its close, its gap, and what it inherits from abroad.

    The inheritance half is a TRANSMISSION SEED as well as a domestic reading -- the overnight
    gap of an Asian index is largely the US session it slept through, and saying so out loud is
    how the transmission engine gets a channel to measure instead of a correlation to admire.
    """
    idx = [s.upper() for ex in pack.exchanges for s in ex.index_symbols]
    if not idx:
        ctx.note("equity_mechanics", "the pack declares no exchange index symbol")
        return {"outcome": UNMEASURED, "why": "no index symbol"}
    reg = universe()
    rows: list[dict[str, Any]] = []
    n = 0
    for sym in idx[:3]:
        if ctx.remaining_s() <= 0:
            break
        bars = ctx.bars(sym, "H1")
        if bars is None:
            ctx.note(f"bars:{sym}", "no H1 tape on this box")
            continue
        eras = _eras_for(pack, bars)
        for ex in pack.exchanges:
            if sym not in {s.upper() for s in ex.index_symbols}:
                continue
            if parse_hhmm(ex.open_utc) and parse_hhmm(ex.close_utc):
                res = window_effect(bars, ex.open_utc, ex.close_utc, eras=eras)
                res.update({"symbol": sym, "leg": "cash_session", "exchange": ex.name})
                rows.append(res)
        for lead in ("US500", "GER40"):
            if reg and lead not in reg:
                continue
            lb = ctx.bars(lead, "H1")
            if lb is None:
                ctx.note(f"bars:{lead}", "no H1 tape for the offshore lead")
                continue
            res = _lead_reading(lb, bars, ctx.rng(f"{lead}:{sym}"))
            res.update({"symbol": sym, "lead": lead, "leg": "offshore_inheritance"})
            rows.append(res)
            if res.get("significant"):
                ctx.seed_transmission(to_country=pack.code, asset=sym, source_symbol=lead,
                                      actor="offshore index investors and the local open auction",
                                      constraint="the local cash market cannot trade while it is "
                                                 "shut, so the offshore session arrives at once "
                                                 "in the open",
                                      flow="overnight inheritance", lag_days=1.0,
                                      evidence=res)
                did, created = ctx.record(
                    mechanism=f"{pack.code}_index_offshore_inheritance",
                    source_id=f"equity:{sym}", source_type="cross_asset",
                    actor=f"{pack.name} index participants at the open auction",
                    constraint="the local cash market is shut while the offshore session trades; "
                               "everything it missed arrives in one auction",
                    economic_rationale=f"{lead}'s session predicts {sym}'s next local session",
                    assets=[sym], horizons=["overnight"], sessions=["all"],
                    regimes=["unconditional"], required_data=[f"{lead} H1", f"{sym} H1"],
                    pit_requirements=["bar timestamps in UTC"], novelty=0.35, confidence=0.55,
                    falsifier=f"{lead}'s session carries no predictive content for {sym} once "
                              f"{sym}'s own lags are held fixed",
                    payload={"reading": res, "lead": lead})
                n += int(created or did != "dry-run")
    measured = [r for r in rows if r.get("verdict") == "MEASURED"]
    return {"outcome": OK if measured else UNMEASURED, "discoveries": n,
            "indices": idx, "measured": len(measured),
            "why": "" if measured else "no index carried a measurable reading",
            "readings": measured[:8]}


def _lead_reading(lead: Bars, target: Bars, rng: np.random.Generator) -> dict[str, Any]:
    """One offshore lead against one local target on a shared daily grid."""
    ld, td = bar_days(lead), bar_days(target)
    lr, tr = log_returns(lead.close), forward_returns(target.close, 1)
    uniq = np.intersect1d(np.unique(ld), np.unique(td))
    if uniq.size < 60:
        return {"verdict": "POORLY_MEASURED", "n": int(uniq.size),
                "why": "fewer than 60 common days"}
    lead_daily = np.array([float(np.nansum(lr[ld == d])) for d in uniq], dtype="float64")
    tgt_daily = np.array([float(np.nansum(tr[td == d])) for d in uniq], dtype="float64")
    return corr_with_null(lead_daily[:-1], tgt_daily[1:], rng=rng)


def generic_derivatives_expiry(pack: CountryPack, ctx: LabCtx) -> dict[str, Any]:
    """Expiry days as an event study, from the exchange's declared rule or its date list."""
    rules = [ex for ex in pack.exchanges if ex.expiry_dates or ex.expiry_rule]
    if not rules:
        ctx.note("derivatives_expiry", "no exchange declares an expiry rule or date list")
        return {"outcome": UNMEASURED, "why": "no expiry rule"}
    rows: list[dict[str, Any]] = []
    n = 0
    for ex in rules:
        dates = parse_days(ex.expiry_dates)
        if dates.size == 0:
            ctx.note(f"expiry:{ex.name}",
                     f"rule {ex.expiry_rule!r} declared with no dates; the rule is not yet "
                     f"expanded into a calendar on this pack")
            continue
        for sym in [s.upper() for s in ex.index_symbols][:2]:
            bars = ctx.bars(sym, "H1")
            if bars is None:
                ctx.note(f"bars:{sym}", "no H1 tape on this box")
                continue
            res = event_effect(bars, dates, horizon=1, rng=ctx.rng(f"{ex.name}:{sym}"),
                               eras=_eras_for(pack, bars))
            res.update({"exchange": ex.name, "symbol": sym, "rule": ex.expiry_rule})
            rows.append(res)
            if res.get("significant"):
                did, created = ctx.record(
                    mechanism=f"{pack.code}_{_tok(ex.name)}_expiry_pin",
                    source_id=f"expiry:{_tok(ex.name)}", source_type="calendar",
                    actor="option and futures books that must settle against the expiry print",
                    constraint=f"{ex.expiry_rule or 'the expiry rule'} fixes the settlement "
                               f"moment; a hedge must be unwound into it",
                    economic_rationale=f"expiry concentrates hedging flow into {sym}",
                    assets=[sym], horizons=["intraday"], sessions=["all"],
                    regimes=["unconditional"], required_data=["the exchange expiry calendar"],
                    pit_requirements=["the expiry calendar is knowable in advance"],
                    novelty=0.5, confidence=0.5,
                    falsifier="the expiry effect does not clear the matched weekday+hour control",
                    payload={"reading": res})
                n += int(created or did != "dry-run")
    measured = [r for r in rows if r.get("verdict") == "MEASURED"]
    return {"outcome": OK if measured else UNMEASURED, "discoveries": n,
            "measured": len(measured),
            "why": "" if measured else "no expiry calendar produced a measurable study",
            "readings": measured[:8]}


def generic_failure(pack: CountryPack, ctx: LabCtx) -> dict[str, Any]:
    """This country's own deaths, routed into the descendant the death JUSTIFIES.

    A death is exploited, not filed: WRONG_DIRECTION justifies an inverse, COST_KILLED an
    execution variant, REGIME_SPECIFIC a conditioned child. NO_EDGE and REDUNDANT justify
    nothing, and inventing a descendant for them is search waste wearing a lineage -- so they are
    counted and left alone. `graveyard_resurrection` is asked first when it is on this box.
    """
    if ctx.conn is None:
        return {"outcome": UNMEASURED, "why": "no registry connection"}
    route = {"wrong_direction": "INVERSE", "cost_killed": "EXECUTION_VARIANT",
             "regime_specific": "REGIME_CONDITION", "wrong_horizon": "HORIZON_TRANSFER",
             "wrong_asset": "ASSET_TRANSFER", "execution_killed": "EXECUTION_VARIANT",
             "unstable": "RESIDUALIZATION"}
    tag = ctx.tag
    rows = [r for r in R.candidates(status="judged", limit=400, conn=ctx.conn)
            if str(r.get("generator") or "").lower().startswith(tag)
            or str(r.get("symbol") or "").upper() in {s.upper()
                                                      for s in pack.executable_instruments}]
    barren = 0
    n = 0
    for r in rows[:40]:
        cls = str(r.get("failure_class") or "").lower()
        op = route.get(cls)
        if op is None:
            barren += 1
            continue
        did, created = ctx.record(
            mechanism=f"{pack.code}_descendant_{_tok(op)}",
            source_id=f"failure:{r.get('id')}", source_type="failure",
            parent_ids=[str(r.get("discovery_id") or r.get("id") or "")],
            actor=str(r.get("economic_actor") or f"{pack.name} participants"),
            constraint=str(r.get("constraint_text") or "the parent's constraint, unchanged"),
            economic_rationale=f"the parent died {cls}, which JUSTIFIES {op} and nothing else",
            assets=[str(r.get("symbol") or "")], horizons=[str(r.get("horizon") or "intraday")],
            sessions=[str(r.get("session") or "all")],
            regimes=[str(r.get("regime") or "unconditional")],
            required_data=["the parent's own inputs"], pit_requirements=["unchanged"],
            novelty=0.4, confidence=0.4,
            falsifier=f"the {op} descendant dies of the same cause as its parent",
            payload={"parent": r.get("id"), "failure_class": cls, "operator": op})
        n += int(created or did != "dry-run")
    mod = desk_module("graveyard_resurrection")
    if mod is None:
        ctx.note("graveyard_resurrection", "the organ is not on this box; only the registry's own "
                                           "judged rows were routed")
    return {"outcome": OK if rows else UNMEASURED, "discoveries": n, "judged_rows": len(rows),
            "barren": barren, "graveyard_organ": mod is not None,
            "why": "" if rows else "the registry holds no judged row for this country"}


def generic_residual(pack: CountryPack, ctx: LabCtx) -> dict[str, Any]:
    """What the desk's model does not explain, for this country's instruments.

    Delegated to `shadow_discovery` when it is on this box -- actual minus model is its question
    and two answers to one question is how two organs come to disagree. Absent, the miner says
    so; it does NOT substitute a home-grown residual that nothing else would recognise.
    """
    mod = desk_module("shadow_discovery")
    if mod is None:
        ctx.note("shadow_discovery", "the organ is not on this box; the country's residual is "
                                     "unmeasured rather than re-derived here")
        return {"outcome": UNMEASURED, "why": "shadow_discovery is not on this box"}
    fn = getattr(mod, "residual_inputs", None)
    if not callable(fn):
        ctx.note("shadow_discovery", "residual_inputs is absent from the organ's surface")
        return {"outcome": UNMEASURED, "why": "no residual_inputs entry point"}
    try:
        doc = fn()
    except Exception as exc:
        ctx.note("shadow_discovery", f"{type(exc).__name__}: {exc}")
        return {"outcome": UNMEASURED, "why": f"{type(exc).__name__}"}
    syms = {s.upper() for s in pack.executable_instruments}
    rows = [r for v in (doc or {}).values() if isinstance(v, list) for r in v
            if isinstance(r, dict) and str(r.get("sym") or r.get("symbol") or "").upper() in syms]
    n = 0
    for r in rows[:20]:
        did, created = ctx.record(
            mechanism=f"{pack.code}_unexplained_residual",
            source_id="residual:shadow_discovery", source_type="residual",
            actor=f"{pack.name} participants the desk's factor model does not represent",
            constraint="a recurring residual means a real constraint the model has no term for",
            economic_rationale="actual minus model is the research target",
            assets=[str(r.get("sym") or r.get("symbol") or "")], horizons=["intraday"],
            sessions=["all"], regimes=["unconditional"],
            required_data=["the shadow ledger"], pit_requirements=["trade timestamps"],
            novelty=0.55, confidence=0.4,
            falsifier="the residual does not recur in a second window",
            payload={"row": r})
        n += int(created or did != "dry-run")
    return {"outcome": OK if rows else UNMEASURED, "discoveries": n, "rows": len(rows),
            "why": "" if rows else "the residual engine holds no row for this country's symbols"}


def generic_transfer(pack: CountryPack, ctx: LabCtx) -> dict[str, Any]:
    """The twelve transformation miners applied to this country's own discoveries."""
    mod = desk_module("transformation_miners")
    if mod is None:
        ctx.note("transformation_miners", "the twelve are not on this box; the country's closure "
                                          "is unexpanded this pass")
        return {"outcome": UNMEASURED, "why": "transformation_miners is not on this box"}
    if ctx.conn is None:
        return {"outcome": UNMEASURED, "why": "no registry connection"}
    parents = [r for r in R.discoveries(state="INTERPRETED", limit=200, conn=ctx.conn)
               if str(r.get("generator") or "").lower().startswith(ctx.tag)]
    if not parents:
        return {"outcome": UNMEASURED, "why": "no INTERPRETED discovery for this country"}
    reg = universe()
    instruments: dict[str, list[str]] = {}
    for sym in pack.executable_instruments:
        klass = str((reg.get(sym) or {}).get("asset_class") or "unknown")
        instruments.setdefault(klass, []).append(sym.upper())
    try:
        tctx = mod.Context(instruments=instruments, conn=ctx.conn,
                           bars_available=lambda s, c: ctx.bars(s, c) is not None)
    except Exception as exc:
        ctx.note("transformation_miners", f"Context: {type(exc).__name__}: {exc}")
        return {"outcome": UNMEASURED, "why": f"Context {type(exc).__name__}"}
    children = 0
    for parent in parents[:20]:
        if ctx.remaining_s() <= 0:
            break
        try:
            out = mod.run_all(parent, tctx)
        except Exception as exc:
            ctx.note("transformation_miners", f"run_all: {type(exc).__name__}: {exc}")
            continue
        children += sum(len(v) for v in out.values())
    return {"outcome": OK, "parents": len(parents), "children": children, "discoveries": 0,
            "why": "children are compiled by the discovery compiler, not enqueued here"}


def generic_scouts(pack: CountryPack, ctx: LabCtx) -> dict[str, Any]:
    """THE TEN SOURCE LAYERS, one scout each, and the country's coverage measured rather than
    asserted.

    NATIVE-LANGUAGE MINING IS REAL HERE, and the order is the point: NATIVE QUERIES built from
    the pack's own terminology, pointed at NATIVE SOURCE ROOTS, so what comes back is written by
    NATIVE AUTHORS in native terms -- translation happens AFTER retrieval, never before. An
    English query against an English index cannot reach the forum where a local desk explains its
    own settlement convention, and that is exactly the ground worth mining.

    AND A LAYER NOBODY HAS MAPPED IS A DISCOVERY OF ITS OWN. The ten layers are asked of every
    country whether or not anybody has thought about that country yet, so an UNMAPPED layer is
    recorded as an acquisition lead naming what is missing -- which is how coverage rises through
    the two conditions (`coverage_state`) rather than through five obvious sources being added.

    This miner STEERS; it does not crawl. `deep_forest_miner --region <cc>` when the forest knows
    this country, `world_frontier` otherwise, and the steer is recorded so the next pass can see
    whether it was taken.
    """
    if not pack.native_languages or not pack.terminology:
        ctx.note("scouts", "the pack declares no native language or no terminology; a native "
                           "query cannot be built from an empty dictionary")
        return {"outcome": UNMEASURED, "why": "no native terminology"}
    forest = desk_module("deep_forest_miner")
    supported = bool(forest is not None
                     and str(pack.code) in getattr(forest, "REGION_CLUSTER", {}))
    steer = (f"deep_forest_miner.py --region {pack.code}" if supported
             else "world_frontier (the forest does not know this country)")
    if forest is None:
        ctx.note("deep_forest_miner", "the organ is not on this box; the steer is recorded and "
                                      "not executed")
    coverage = coverage_state(pack.code, ctx.conn, pack=pack)
    inventory = layer_inventory(pack.code, pack=pack)
    n = 0
    queries = 0
    for layer in SOURCE_LAYERS:
        if ctx.remaining_s() <= 0:
            ctx.note("scouts", f"the miner's budget was spent before the {layer} layer")
            break
        rows = inventory[layer]
        state = coverage["layers"][layer]["state"]
        seeds = native_query_seeds(pack.code, layer, pack=pack)
        queries += len(seeds)
        if state == "ABSENT_DECLARED":
            ctx.note(f"scout:{layer}", f"declared ABSENT for {pack.name}: "
                                       f"{coverage['layers'][layer]['why']}")
            continue
        if state == "UNMAPPED":
            ctx.note(f"scout:{layer}", "no source and no declared absence; the layer is UNMAPPED "
                                       "and the country cannot be covered while it is")
        roots = [r for row in rows for r in (row.get("roots") or [])]
        did, created = ctx.record(
            mechanism=f"{pack.code}_scout_{layer}",
            source_id=f"scout:{layer}", source_type="scout",
            actor=f"the {pack.name} {layer.replace('_', ' ')} layer and the people who write it",
            constraint="a claim written in the native language of the market it describes is not "
                       "reachable by an English query against an English index",
            economic_rationale=f"native {layer} ground for {pack.name}: {len(rows)} declared "
                               f"source(s), state {state}, steered by {steer}",
            assets=list(pack.executable_instruments[:3]), horizons=["multi_day"],
            sessions=["all"], regimes=["unconditional"],
            required_data=[f"{layer} roots: {roots[:4] or 'none declared'}"],
            pit_requirements=["retrieval time and publication time of every document"],
            novelty=0.6, confidence=0.35,
            falsifier=f"the {layer} layer yields no claim naming a testable mechanism after a "
                      f"full crawl of its declared roots",
            payload={"layer": layer, "state": state, "roots": roots[:12], "steer": steer,
                     "languages": list(pack.native_languages),
                     "queries": [q["query"] for q in seeds[:20]],
                     "site_scoped": [q for row in seeds[:6] for q in row["site_scoped"]][:12],
                     "translate": "after retrieval only",
                     "expansion": "register every followed link as a source with its language"})
        n += int(created or did != "dry-run")
    untagged = inventory["UNTAGGED"]
    if untagged:
        ctx.note("scouts", f"{len(untagged)} declared source(s) carry no layer tag; they are "
                           f"UNTAGGED and count toward no layer")
    sf = desk_module("source_frontier")
    registered = 0
    if sf is not None and hasattr(sf, "register_source") and not ctx.dry_run:
        for layer in SOURCE_LAYERS:
            for row in inventory[layer][:4]:
                try:
                    sf.register_source(f"{ctx.tag}{layer}:{_tok(row['id'])}",
                                       url=(row.get("roots") or [""])[0], kind=layer,
                                       language=(pack.native_languages or ("",))[0],
                                       country=pack.code, conn=ctx.conn)
                    registered += 1
                except Exception as exc:
                    ctx.note("source_frontier", f"{type(exc).__name__}: {exc}")
                    break
    elif sf is None:
        ctx.note("source_frontier", "the organ is not on this box; sources are recorded as "
                                    "discoveries only")
    return {"outcome": OK, "discoveries": n, "steer": steer, "queries": queries,
            "layers": {k: coverage["layers"][k]["state"] for k in SOURCE_LAYERS},
            "coverage_state": coverage["state"], "coverage_why": coverage["why"],
            "layers_mapped": coverage["layers_mapped"], "untagged_sources": len(untagged),
            "sources_registered": registered, "forest_supports_country": supported}


#: Every generic miner, by name. A country pack is DATA PLUS OPTIONAL CUSTOM MINERS; this table
#: is what "the same depth as Japan" means operationally -- fifteen questions asked of every
#: country, whether or not anybody has thought about that country yet.
GENERIC_MINERS: dict[str, Callable[[CountryPack, LabCtx], dict[str, Any]]] = {
    "central_bank_surprise": generic_central_bank_surprise,
    "release_surprise": generic_release_surprise,
    "calendar_settlement": generic_calendar_settlement,
    "holiday_liquidity": generic_holiday_liquidity,
    "session_microstructure": generic_session_microstructure,
    "positioning": generic_positioning,
    "carry_funding": generic_carry_funding,
    "corporate_flow": generic_corporate_flow,
    "institutional_flow": generic_institutional_flow,
    "equity_mechanics": generic_equity_mechanics,
    "derivatives_expiry": generic_derivatives_expiry,
    "failure": generic_failure,
    "residual": generic_residual,
    "transfer": generic_transfer,
    "scouts": generic_scouts,
}

_ACTOR_FIELDS = tuple(ActorRow.__dataclass_fields__.values())
_DOMAIN_FIELDS = tuple(DomainRow.__dataclass_fields__.values())
_DATASET_FIELDS = tuple(DatasetRow.__dataclass_fields__.values())


# --------------------------------------------------------------------------- budgets and the run
def miner_budgets(names: Sequence[str], pool_s: float, yields: Sequence[Mapping[str, Any]],
                  tag: str, fixed: Sequence[str] = ()) -> dict[str, dict[str, Any]]:
    """Seconds per miner by MEASURED downstream yield, under two floors.

    Jeffreys rather than a raw ratio -- (independent_survivors + 0.5) / (generated + 1) -- so a
    miner that has produced nothing is not assumed useless and one lucky survivor does not crown
    a miner. Then the floors, and the order between them matters: every miner keeps at least
    MINER_FLOOR, and the miners with NO success ever keep COLD_SHARE *as a class*. A warm miner
    pushed below its floor still ran last pass; cold ground defunded to zero is never measured
    again, and therefore never stops looking worthless.
    """
    out: dict[str, dict[str, Any]] = {}
    if not names:
        return out
    by_gen = {str(r.get("generator") or "").lower(): r for r in yields}
    fixed_set = {n for n in fixed if n in names}
    steer = [n for n in names if n not in fixed_set]
    fixed_share = min(1.0, len(fixed_set) / float(len(names)))
    share_left = max(0.0, 1.0 - fixed_share)
    prior: dict[str, float] = {}
    cold: list[str] = []
    for name in names:
        row = by_gen.get(f"{tag}{name}".lower(), {})
        gen = float(row.get("generated") or 0.0)
        indep = float(row.get("independent_survivors") or 0.0)
        prior[name] = (indep + 0.5) / (gen + 1.0)
        if indep <= 0:
            cold.append(name)
    weight: dict[str, float] = ({n: fixed_share / len(fixed_set) for n in fixed_set}
                                if fixed_set else {})
    if steer:
        floor = min(MINER_FLOOR, share_left / len(steer))
        free = max(0.0, share_left - floor * len(steer))
        total = sum(prior[n] for n in steer)
        for n in steer:
            frac = (prior[n] / total) if total > 0 else (1.0 / len(steer))
            weight[n] = floor + free * frac
    cold_steer = [n for n in cold if n in weight and n not in fixed_set]
    warm = [n for n in weight if n not in cold_steer]
    have = sum(weight[n] for n in cold_steer)
    want = COLD_SHARE * sum(weight.values())
    if cold_steer and have < want:
        for n in cold_steer:
            weight[n] = (weight[n] * want / have) if have > 0 else want / len(cold_steer)
        rest = max(0.0, sum(weight.values()) - want)
        warm_have = sum(weight[n] for n in warm)
        for n in warm:
            weight[n] = (rest * weight[n] / warm_have) if warm_have > 0 else (
                rest / len(warm) if warm else 0.0)
    total_w = sum(weight.values()) or 1.0
    for name in names:
        w = weight.get(name, 0.0) / total_w
        out[name] = {"weight": round(w, 6),
                     "budget_s": round(max(MINER_FLOOR_S, pool_s * w), 3),
                     "prior": round(prior[name], 6), "cold": name in cold,
                     "fixed": name in fixed_set,
                     "why": (f"jeffreys prior {prior[name]:.3f} on generator_yield[{tag}{name}]"
                             + ("; COLD (no independent survivor ever), protected by the "
                                f"{COLD_SHARE:.0%} cold share" if name in cold else "")
                             + ("; fixed cost, not steerable" if name in fixed_set else ""))}
    return out


def load_custom_miners(pack: CountryPack) -> tuple[dict[str, Callable[[CountryPack, LabCtx],
                                                                     dict[str, Any]]], list[str]]:
    """The pack's `module:function` entries, resolved. An entry that does not resolve is NAMED
    and counted, never skipped: a custom miner that silently never runs is a country the desk
    believes it is mining and is not."""
    out: dict[str, Callable[[CountryPack, LabCtx], dict[str, Any]]] = {}
    problems: list[str] = []
    for entry in pack.custom_miners:
        mod_name, _, fn_name = str(entry).partition(":")
        if not mod_name or not fn_name:
            problems.append(f"custom miner {entry!r}: not a 'module:function' entry")
            continue
        try:
            mod = importlib.import_module(mod_name)
        except Exception as exc:
            problems.append(f"custom miner {entry!r}: import failed "
                            f"({type(exc).__name__}: {exc})")
            continue
        fn = getattr(mod, fn_name, None)
        if not callable(fn):
            problems.append(f"custom miner {entry!r}: {fn_name} is absent or not callable")
            continue
        out[f"custom:{fn_name}"] = fn
    return out, problems


def run_lab(pack: CountryPack, ctx: LabCtx, budget_s: float = 300.0,
            extra: Mapping[str, Callable[[CountryPack, LabCtx], dict[str, Any]]] | None = None
            ) -> dict[str, Any]:
    """One country's pass: the fifteen generic miners, then its own, inside `budget_s`.

    The generic set runs FIRST and always. That is what "every country gets the same depth" means
    in code: a country nobody has written a custom miner for still has its central bank, its
    settlement conventions, its holidays, its sessions, its positioning, its carry, its trade
    cycle, its index and its native-language ground asked about on every pass. Custom miners are
    the country's own additions on top, budgeted by the same measured ROI as the generic ones.
    """
    started = time.monotonic()
    ctx.deadline = started + float(budget_s)
    ctx.region_command = ctx.region_command or pack.region_command
    custom, custom_problems = load_custom_miners(pack)
    for row in custom_problems:
        ctx.note("custom_miners", row)
    # `extra` is the pack directory's own `miners.py MINERS`, handed in by the global OS. It is
    # merged UNDER the dotted entries so a pack that names the same miner both ways gets one.
    for name, fn in dict(extra or {}).items():
        custom.setdefault(f"custom:{name}", fn)
    names = [*GENERIC_MINERS, *custom]
    yields: Sequence[Mapping[str, Any]] = []
    if ctx.conn is not None:
        try:
            yields = R.generator_yields(conn=ctx.conn)
        except Exception as exc:
            ctx.note("generator_yields", f"{type(exc).__name__}: {exc}")
    budgets = miner_budgets(names, float(budget_s) * 0.95, yields, ctx.tag,
                            fixed=("central_bank_surprise", "calendar_settlement"))
    rows: list[dict[str, Any]] = []
    before = len(ctx.recorded)
    for name in names:
        chosen: Callable[[CountryPack, LabCtx], dict[str, Any]] | None = (
            GENERIC_MINERS.get(name) or custom.get(name))
        if chosen is None:
            continue
        fn = chosen
        share = float(budgets.get(name, {}).get("budget_s") or MINER_FLOOR_S)
        left = max(0.0, ctx.deadline - time.monotonic())
        rec: dict[str, Any] = {"miner": name, "budget_s": round(share, 3),
                               "why": str(budgets.get(name, {}).get("why") or ""),
                               "cold": bool(budgets.get(name, {}).get("cold"))}
        if left <= 0.0:
            rec.update({"outcome": SKIPPED, "seconds": 0.0, "discoveries": 0,
                        "note": f"the pass budget of {budget_s:.0f}s was spent first"})
            rows.append(rec)
            continue
        box = max(MINER_FLOOR_S, min(share, left))
        saved_deadline, saved_miner = ctx.deadline, ctx.miner
        ctx.miner = name
        ctx.deadline = time.monotonic() + box
        mark = len(ctx.recorded)
        t0 = time.monotonic()
        try:
            result = fn(pack, ctx)
            rec.update({k: v for k, v in dict(result).items() if k != "readings"})
            rec.setdefault("outcome", OK)
            rec["readings"] = list(dict(result).get("readings") or [])[:4]
        except Exception as exc:
            rec.update({"outcome": FAILED, "why": f"{type(exc).__name__}: {str(exc)[:300]}"})
            ctx.note(name, f"{type(exc).__name__}: {str(exc)[:200]}")
        rec["seconds"] = round(time.monotonic() - t0, 3)
        rec["recorded"] = len(ctx.recorded) - mark
        rec["overran_s"] = round(max(0.0, rec["seconds"] - box), 3)
        ctx.deadline, ctx.miner = saved_deadline, saved_miner
        rows.append(rec)
    seeds = list(ctx.transmission_seeds) + [
        {"from_country": pack.code, "to_country": s.to_country, "asset": s.asset,
         "actor": s.actor, "constraint": s.constraint, "flow": s.flow, "lag_days": s.lag_days,
         "source_series": s.source_series, "source_symbol": s.source_symbol, "era": s.era,
         "declared": True, "notes": s.notes}
        for s in pack.transmission_edges_seed]
    return {
        "at": _now(), "country": pack.code, "name": pack.name,
        "region_command": pack.region_command,
        "domestic": len(ctx.recorded) - before,
        "transmission_seeds": seeds,
        "unmeasured": list(ctx.unmeasured),
        "axis_proposals": list(ctx.axis_proposals),
        "miners": rows,
        "budgets": budgets,
        "seconds": round(time.monotonic() - started, 3),
        "budget_s": float(budget_s),
        "custom_miners": sorted(custom),
        "generic_miners": list(GENERIC_MINERS),
        "rule": RULE,
    }

```

### libs\research\dedup_chain.py
```python
"""THE DEDUP CHAIN -- ten agents finding one strategy on ten repost sites produce ONE mechanism.

THE FAILURE IT EXISTS TO PREVENT. The forest federation runs eleven agents in each of seventeen
civilizations, and the deep forest is largely a REPOST ECOLOGY: one 七禾网 interview is quoted on
four aggregators, summarised on two blogs, screenshotted into a forum thread and mirrored by an
archive. Without a chain, that is nine extra mechanisms, nine extra cells, nine extra trials --
and the deflated-Sharpe charge and the program-level SPA/PBO tests divide ONE family-wise error
budget across every hypothesis the desk tests. Duplicate discovery is not untidy; it is a tax
every genuine hypothesis pays.

THE FIVE STAGES, IN THIS ORDER, AND THE VERDICT NAMES THE ONE THAT DECIDED:

  1. CANONICAL SOURCE   scheme/host lowercased, tracking parameters stripped, known mirrors
                        folded onto their origin, trailing slash and default ports removed. Two
                        rows that are the same page with different campaign tags are one row,
                        and this stage costs nothing.
  2. CONTENT HASH       sha256 of the NORMALISED text (whitespace folded, case folded, boilerplate
                        punctuation dropped). A verbatim repost on another host lands here.
  3. SEMANTIC SIMILARITY  cosine over k-shingles. A paraphrase, a translation-with-edits or a
                        quote-plus-commentary lands here. It fires only when the two rows do not
                        name DIFFERENT mechanisms -- high token overlap between two genuinely
                        different claims about the same instrument is common, and letting prose
                        similarity overrule a stated mechanism is how a real descendant gets
                        erased as a duplicate.
  4. MECHANISM IDENTITY the key the desk already reasons in (`lead_schema` / `hypothesis_graph`
                        conventions): family, instruments, condition, direction, horizon. Two
                        rows with no textual overlap at all that state the same edge are ONE
                        mechanism, which is the stage the other four cannot reach.
  5. GENEALOGY          what is left: a row that names an ancestor, or sits in the descendant
                        similarity band while stating a DIFFERENT mechanism, is a DESCENDANT --
                        it branches, with a provenance edge to its canonical ancestor, and is
                        tested on its own.

Pure and typed. It opens nothing, writes nothing and decides nothing about capital: it returns a
`Verdict` carrying the deciding stage, the score, the mechanism key and the provenance edges the
caller should write. `RegistryView` is the in-memory index the caller maintains -- one process,
one view -- so the chain never queries a database inside a scoring loop.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

__all__ = [
    "DESCENDANT_OF",
    "DESCENDANT_THRESHOLD",
    "DUPLICATE_OF",
    "MIRRORS",
    "NEW",
    "SEMANTIC_DUPLICATE_THRESHOLD",
    "SHINGLE_K",
    "STAGES",
    "TRACKING_PARAMS",
    "Item",
    "RegistryView",
    "Verdict",
    "canonical_url",
    "content_hash",
    "dedup",
    "fold",
    "mechanism_key",
    "normalise_text",
    "shingles",
    "similarity",
]

# --------------------------------------------------------------------------- vocabulary
NEW = "NEW"
DUPLICATE_OF = "DUPLICATE_OF"
DESCENDANT_OF = "DESCENDANT_OF"

#: The five stages, in the order they run. A verdict always names exactly one of them.
STAGES: tuple[str, ...] = ("canonical_source", "content_hash", "semantic_similarity",
                           "mechanism_identity", "genealogy")

#: Cosine over k-shingles at or above which two texts are THE SAME TELLING. Measured against the
#: repost ecology this desk actually mines: a verbatim repost scores 1.0 (and is caught one stage
#: earlier anyway), an aggregator's quote-plus-headline 0.85-0.95, a genuine follow-up study on
#: the same instrument 0.3-0.6. 0.82 sits in the empty band between the second and the third.
SEMANTIC_DUPLICATE_THRESHOLD = 0.82
#: At or above this -- but below the duplicate bar -- two rows are RELATED. With a different
#: mechanism key that is a descendant (it branches and is tested); below it, unrelated.
DESCENDANT_THRESHOLD = 0.55
#: Shingle width. 3 for space-delimited scripts; single CJK glyphs are shingled at 3 too, which
#: is roughly a word and a half in Chinese, Japanese and Korean -- the forests this desk is
#: under standing orders to mine to exhaustion, and where a token-level model finds nothing.
SHINGLE_K = 3

#: Query parameters that identify a VISIT rather than a PAGE. Stripped before hashing a url.
TRACKING_PARAMS: frozenset[str] = frozenset({
    "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content", "utm_id",
    "gclid", "fbclid", "yclid", "msclkid", "dclid", "igshid", "mc_cid", "mc_eid",
    "spm", "scm", "from", "share_source", "share_medium", "share_plat", "share_token",
    "vd_source", "ref", "referrer", "refer", "source", "src", "s", "sid", "session_id",
    "_hsenc", "_hsmi", "trk", "trkCampaign", "at_medium", "at_campaign", "wt_mc",
})

#: Hosts that SERVE ANOTHER HOST'S PAGES. Folding a mirror onto its origin is the cheapest real
#: dedup on this desk's ground: the Wayback Machine, the CJK and RU text mirrors, the nitter and
#: reddit front ends. The mapping is one-way and deliberately small -- a wrong entry MERGES two
#: different sources, which is worse than missing a duplicate.
MIRRORS: dict[str, str] = {
    "web.archive.org": "",            # "" means: unwrap the embedded original url
    "webcache.googleusercontent.com": "",
    "archive.ph": "", "archive.today": "", "archive.is": "",
    "r.jina.ai": "",
    "old.reddit.com": "reddit.com", "np.reddit.com": "reddit.com",
    "m.weibo.cn": "weibo.com", "xueqiu.com": "xueqiu.com",
    "zhuanlan.zhihu.com": "zhihu.com",
    "m.bilibili.com": "bilibili.com",
    "nitter.net": "twitter.com", "nitter.poast.org": "twitter.com", "x.com": "twitter.com",
    "mobile.twitter.com": "twitter.com",
    "m.habr.com": "habr.com", "translated.turbopages.org": "",
}

_DEFAULT_PORTS = {"http": "80", "https": "443"}
_INDEX_FILES = re.compile(r"/(index|default)\.(html?|php|aspx?|jsp)$", re.IGNORECASE)
_WS = re.compile(r"\s+")
#: The punctuation a repost REFLOWS, in forty scripts. RUF001 calls these characters
#: ambiguous; here they are the data, not a typo waiting to be found.
_PUNCT = re.compile(r"[\s　]*[\"'`´“”‘’«»(){}\[\]<>|/\\,;:!?.…、。，；：！？·—–\-_*#]+[\s　]*")  # noqa: RUF001
_URL_IN = re.compile(r"https?%3A%2F%2F[^\s&]+|https?://[^\s\"'<>]+", re.IGNORECASE)
_CJK = re.compile(r"[぀-ヿ㐀-鿿가-힯]")
_TOKEN = re.compile(r"[a-z0-9]+|[぀-ヿ㐀-鿿가-힯]")


# --------------------------------------------------------------------------- stage 1: the url
def _unquote(text: str) -> str:
    """Percent-decoding without importing urllib: the mirrors embed an encoded original url."""
    out: list[str] = []
    i = 0
    while i < len(text):
        ch = text[i]
        if ch == "%" and i + 2 < len(text):
            try:
                out.append(chr(int(text[i + 1:i + 3], 16)))
                i += 3
                continue
            except ValueError:
                pass
        out.append(ch)
        i += 1
    return "".join(out)


def _split(url: str) -> tuple[str, str, str, str, str]:
    """(scheme, host, port, path, query) -- a small, total parser; a malformed url is data."""
    raw = str(url or "").strip()
    scheme = ""
    if "://" in raw:
        scheme, raw = raw.split("://", 1)
    raw = raw.split("#", 1)[0]
    query = ""
    if "?" in raw:
        raw, query = raw.split("?", 1)
    hostport, _, path = raw.partition("/")
    host, _, port = hostport.partition(":")
    return scheme.lower(), host.lower(), port, ("/" + path if path else "/"), query


def canonical_url(url: str, *, mirrors: Mapping[str, str] | None = None) -> str:
    """STAGE 1. One page, one string: scheme and host lowered, tracking parameters stripped,
    known mirrors folded (or unwrapped back to the original url they are serving), default port
    and trailing slash and index file removed, query parameters sorted.

    An empty or unparseable url returns "" -- which the chain reads as "this row names no page",
    never as "this row is the same page as the other row that names none".
    """
    table = dict(MIRRORS if mirrors is None else mirrors)
    seen: set[str] = set()
    current = str(url or "").strip()
    for _hop in range(4):                    # a mirror of a mirror; bounded, never a cycle
        scheme, host, port, path, query = _split(current)
        if not host:
            return ""
        target = table.get(host)
        if target == "":
            inner = _URL_IN.search(_unquote(f"{path}?{query}" if query else path))
            if inner and inner.group(0) not in seen:
                seen.add(inner.group(0))
                current = inner.group(0)
                continue
            target = None
        if target:
            host = target
        # `www.` IS NOT PART OF A SITE'S IDENTITY. Every host serves both spellings and the
        # aggregators pick whichever their crawler saw first, so keeping them apart would leave
        # the cheapest duplicate in the whole chain uncaught.
        if host.startswith("www.") and host.count(".") > 1:
            host = host[4:]
        if " " in host or ("." not in host and host != "localhost"):
            return ""              # not a host: a malformed row names no page, and no two
        #                            rows that name no page are therefore the same page
        port = "" if port in ("", _DEFAULT_PORTS.get(scheme or "https", "")) else port
        # NOR IS THE SCHEME. http and https serve the same page, and an aggregator linking the
        # plain-http spelling of a claim is not a second telling of it.
        scheme = "https"
        path = _INDEX_FILES.sub("/", path)
        if len(path) > 1 and path.endswith("/"):
            path = path[:-1]
        params = []
        for part in query.split("&"):
            if not part:
                continue
            name = part.split("=", 1)[0]
            if name.lower() in TRACKING_PARAMS:
                continue
            params.append(part)
        params.sort()
        netloc = f"{host}:{port}" if port else host
        tail = ("?" + "&".join(params)) if params else ""
        return f"{scheme}://{netloc}{path}{tail}"
    return ""


# --------------------------------------------------------------------------- stage 2: the text
def normalise_text(text: str) -> str:
    """The text with everything that is not the CLAIM removed: case, whitespace runs and the
    punctuation a repost reflows. Two tellings that differ only by formatting normalise equal."""
    body = _WS.sub(" ", str(text or "")).strip().lower()
    body = _PUNCT.sub(" ", body)
    return _WS.sub(" ", body).strip()


def content_hash(text: str) -> str:
    """STAGE 2. sha256 of the normalised text, truncated. "" for an empty body, which the chain
    reads as "nothing to hash" -- never as a hash two empty rows share."""
    norm = normalise_text(text)
    return hashlib.sha256(norm.encode("utf-8")).hexdigest()[:32] if norm else ""


# --------------------------------------------------------------------------- stage 3: shingles
def shingles(text: str, k: int = SHINGLE_K) -> frozenset[str]:
    """k-shingles over the normalised token stream: the unit stage 3 compares.

    Tokens are alphanumeric runs plus SINGLE CJK glyphs, so a Japanese or Chinese claim shingles
    into overlapping character triples -- roughly a word and a half -- rather than into one token
    per sentence, which is what a space-delimited tokeniser does to those scripts and why a
    similarity model built on words silently scores every CJK pair at zero.
    """
    tokens = _TOKEN.findall(normalise_text(text))
    if not tokens:
        return frozenset()
    width = max(1, int(k))
    if len(tokens) <= width:
        return frozenset({" ".join(tokens)})
    return frozenset(" ".join(tokens[i:i + width]) for i in range(len(tokens) - width + 1))


def similarity(a: Iterable[str], b: Iterable[str]) -> float:
    """Set cosine |A and B| / sqrt(|A| |B|): 1.0 is the same shingle bag in any order."""
    sa, sb = frozenset(a), frozenset(b)
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / math.sqrt(len(sa) * len(sb))


# --------------------------------------------------------------------------- stage 4: mechanism
_DIR_UP = ("long", "buy", "bull", "rise", "rising", "higher", "up", "positive", "outperform",
           "appreciat", "gain", "上涨", "做多", "买入", "看涨", "상승", "매수", "買い", "上昇")
_DIR_DOWN = ("short", "sell", "bear", "fall", "falling", "lower", "down", "negative",
             "underperform", "depreciat", "decline", "下跌", "做空", "卖出", "看跌", "하락",
             "매도", "売り", "下落")
#: Horizon vocabulary folded onto the desk's own three-value ladder. An unstated horizon is
#: `unknown` and NOT a default: two claims that differ only in an unstated horizon are the same
#: claim until one of them states one.
_HORIZON: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("intraday", ("intraday", "m1", "m5", "m15", "m30", "h1", "h4", "session", "minute", "hour",
                  "日内", "장중", "デイ")),
    ("overnight", ("overnight", "gap", "close to open", "翌日", "隔夜", "오버나이트")),
    ("multi_day", ("multi_day", "d1", "w1", "daily", "weekly", "monthly", "swing", "day",
                   "week", "month", "隔天", "数日", "周", "월간")),
)


def _direction(*texts: Any) -> int:
    """+1, -1 or 0 -- MAJORITY, not presence. "buy the dip and sell the rip" is not directional,
    and manufacturing a direction out of balanced prose manufactures contradictions."""
    low = " " + " ".join(str(t or "") for t in texts).lower() + " "
    up = sum(1 for w in _DIR_UP if w in low)
    down = sum(1 for w in _DIR_DOWN if w in low)
    if up == down:
        return 0
    return 1 if up > down else -1


def _horizon(value: Any, fallback: Any = "") -> str:
    low = " ".join((str(value or ""), str(fallback or ""))).lower()
    for name, needles in _HORIZON:
        if any(n in low for n in needles):
            return name
    return "unknown"


def _condition(value: Any) -> str:
    """The conditioning clause reduced to its significant tokens, order kept, bounded.

    "after the Tokyo fix on the 5th and 10th" and "on 五十日 after the Tokyo fixing" are the same
    condition wearing two sentences; eight tokens is enough to tell them from "after CPI".
    """
    toks = [t for t in _TOKEN.findall(normalise_text(value)) if len(t) > 1 or _CJK.match(t)]
    return " ".join(toks[:12])


def mechanism_key(*, family: str = "", instruments: Sequence[str] = (), condition: str = "",
                  direction: Any = None, horizon: str = "", text: str = "") -> str:
    """STAGE 4's identity: family x instruments x condition x direction x horizon.

    The five fields the desk already reasons in -- `lead_schema.SPEC_FIELDS` names the same edge
    and `hypothesis_graph.node_id` hashes the same shape -- so a mechanism minted here joins the
    hypothesis graph rather than starting a second vocabulary about the same claim.
    """
    insts = sorted({str(s).strip().upper() for s in instruments if str(s).strip()})
    dirn = _direction(text, condition, family) if direction is None else int(direction)
    payload = json.dumps({"f": str(family or "").strip().lower(), "i": insts,
                          "c": _condition(condition), "d": dirn,
                          "h": _horizon(horizon, condition or text)},
                         sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


# --------------------------------------------------------------------------- the objects
@dataclass(frozen=True)
class Item:
    """One thing an agent found, in the only shape the chain reads."""

    item_id: str
    url: str = ""
    title: str = ""
    text: str = ""
    family: str = ""
    instruments: tuple[str, ...] = ()
    condition: str = ""
    direction: int | None = None
    horizon: str = ""
    source_id: str = ""
    forest: str = ""
    role: str = ""
    kind: str = "discovery"
    #: Ancestors this row NAMES. A claim, until the view resolves one -- an unresolvable parent
    #: is carried on the edge, never promoted into the verdict.
    parent_ids: tuple[str, ...] = ()
    payload: Mapping[str, Any] = field(default_factory=dict)

    def mechanism_key(self) -> str:
        return mechanism_key(family=self.family, instruments=self.instruments,
                             condition=self.condition or self.title, direction=self.direction,
                             horizon=self.horizon,
                             text=" ".join((self.title, self.text, self.condition)))


@dataclass(frozen=True)
class Verdict:
    """What the chain decided, WHICH STAGE decided it, and the edges the caller should write."""

    verdict: str
    stage: str
    of: str = ""
    score: float | None = None
    mechanism_key: str = ""
    canonical: str = ""
    content: str = ""
    why: str = ""
    edges: tuple[tuple[str, str, str, str], ...] = field(default_factory=tuple)

    @property
    def is_new(self) -> bool:
        return self.verdict == NEW

    @property
    def is_duplicate(self) -> bool:
        return self.verdict == DUPLICATE_OF

    @property
    def is_descendant(self) -> bool:
        return self.verdict == DESCENDANT_OF

    def as_row(self) -> dict[str, Any]:
        return {"verdict": self.verdict, "stage": self.stage, "of": self.of, "score": self.score,
                "mechanism_key": self.mechanism_key, "canonical_url": self.canonical,
                "content_hash": self.content, "why": self.why,
                "edges": [list(e) for e in self.edges]}


class RegistryView:
    """The in-process index the chain reads: one view per run, fed by what the run admits.

    NOT A DATABASE QUERY IN A LOOP. Eleven roles in seventeen forests times a few hundred rows is
    tens of thousands of comparisons per pass; a view built once and mutated as rows are admitted
    keeps the chain O(n) against the admitted population instead of O(n) round trips.
    """

    def __init__(self) -> None:
        self.by_url: dict[str, str] = {}
        self.by_hash: dict[str, str] = {}
        self.by_mechanism: dict[str, str] = {}
        self.shingles: dict[str, frozenset[str]] = {}
        self.mechanism_of: dict[str, str] = {}
        self.ids: list[str] = []

    def __len__(self) -> int:
        return len(self.ids)

    def add(self, item: Item, item_id: str | None = None, *, mech: str | None = None) -> str:
        """Admit one row as canonical. Idempotent per id; first writer of a key keeps it."""
        iid = str(item_id or item.item_id)
        key = mech if mech is not None else item.mechanism_key()
        url = canonical_url(item.url)
        digest = content_hash(" ".join((item.title, item.text)))
        if url:
            self.by_url.setdefault(url, iid)
        if digest:
            self.by_hash.setdefault(digest, iid)
        if key:
            self.by_mechanism.setdefault(key, iid)
        sh = shingles(" ".join((item.title, item.text, item.condition)))
        if sh:
            self.shingles[iid] = sh
        self.mechanism_of[iid] = key
        if iid not in self.ids:
            self.ids.append(iid)
        return iid

    def knows(self, item_id: str) -> bool:
        return item_id in self.mechanism_of

    @classmethod
    def from_rows(cls, rows: Iterable[Mapping[str, Any]]) -> RegistryView:
        """A view over rows already in the registry (discoveries, claims): the caller's shape,
        read tolerantly, because six producers spell these fields six ways."""
        view = cls()
        for row in rows:
            iid = str(row.get("discovery_id") or row.get("id") or row.get("item_id") or "")
            if not iid:
                continue
            insts = row.get("instruments") or row.get("assets") or row.get("symbols") or ()
            if isinstance(insts, str):
                insts = [insts]
            view.add(Item(item_id=iid, url=str(row.get("url") or row.get("url_or_ref") or ""),
                          title=str(row.get("title") or "")[:400],
                          text=str(row.get("text") or row.get("claim") or
                                   row.get("mechanism") or "")[:4000],
                          family=str(row.get("family") or ""),
                          instruments=tuple(str(s) for s in insts),
                          condition=str(row.get("condition") or row.get("exact_rule") or ""),
                          horizon=str(row.get("horizon") or row.get("chart") or ""),
                          source_id=str(row.get("source_id") or "")))
        return view


# --------------------------------------------------------------------------- the chain
def _edge(src_kind: str, src_id: str, dst_id: str, relation: str) -> tuple[str, str, str, str]:
    return (src_kind, src_id, dst_id, relation)


def dedup(item: Item, registry_view: RegistryView) -> Verdict:
    """The five stages, in order, on one row. NEW | DUPLICATE_OF <id> | DESCENDANT_OF <id>.

    The verdict always names the DECIDING STAGE, because "duplicate" is not a fact on its own:
    a url collision and a mechanism collision are different findings about a forest -- the first
    says an agent walked the same page twice, the second says two independent grounds agree, and
    an audit that cannot tell them apart cannot tell a repost ecology from a consensus.
    """
    key = item.mechanism_key()
    url = canonical_url(item.url)
    digest = content_hash(" ".join((item.title, item.text)))
    src = item.source_id or item.forest or item.role or "forest"

    def dup(stage: str, of: str, why: str, score: float | None = None) -> Verdict:
        return Verdict(verdict=DUPLICATE_OF, stage=stage, of=of, score=score, mechanism_key=key,
                       canonical=url, content=digest, why=why,
                       edges=(_edge("source", src, of, "retold"),))

    # 1 -- CANONICAL SOURCE
    known = registry_view.by_url.get(url) if url else None
    if known and known != item.item_id:
        return dup("canonical_source", known,
                   f"the same page after canonicalisation ({url}): one visit, not one finding")

    # 2 -- CONTENT HASH
    known = registry_view.by_hash.get(digest) if digest else None
    if known and known != item.item_id:
        return dup("content_hash", known,
                   "byte-identical after normalisation: a verbatim repost on another host")

    # 3 -- SEMANTIC SIMILARITY
    mine = shingles(" ".join((item.title, item.text, item.condition)))
    best_id, best = "", 0.0
    for other_id, other in registry_view.shingles.items():
        if other_id == item.item_id:
            continue
        score = similarity(mine, other)
        if score > best:
            best_id, best = other_id, score
    other_key = registry_view.mechanism_of.get(best_id, "")
    same_mechanism = not (key and other_key) or key == other_key
    if best >= SEMANTIC_DUPLICATE_THRESHOLD and same_mechanism:
        return dup("semantic_similarity", best_id, score=round(best, 6),
                   why=f"cosine {best:.3f} over {SHINGLE_K}-shingles is at or above "
                       f"{SEMANTIC_DUPLICATE_THRESHOLD}: the same telling, reworded")

    # 4 -- MECHANISM IDENTITY
    known = registry_view.by_mechanism.get(key) if key else None
    if known and known != item.item_id:
        return dup("mechanism_identity", known,
                   "the same (family, instruments, condition, direction, horizon): two grounds "
                   "telling one mechanism is ONE mechanism with two provenance edges",
                   score=round(best, 6) if best else None)

    # 5 -- GENEALOGY
    ancestor = next((p for p in item.parent_ids if registry_view.knows(p)), "")
    if not ancestor and best >= DESCENDANT_THRESHOLD and best_id and not same_mechanism:
        ancestor = best_id
    if ancestor:
        return Verdict(verdict=DESCENDANT_OF, stage="genealogy", of=ancestor,
                       score=round(best, 6) if best else None, mechanism_key=key, canonical=url,
                       content=digest,
                       why=("states a DIFFERENT mechanism from its ancestor: it branches and is "
                            "tested on its own, with a provenance edge to where it came from"),
                       edges=(_edge("discovery", ancestor, item.item_id, "descendant"),
                              _edge("source", src, item.item_id, "produced")))
    return Verdict(verdict=NEW, stage="genealogy", of="", score=round(best, 6) if best else None,
                   mechanism_key=key, canonical=url, content=digest,
                   why="no canonical page, content, telling, mechanism or ancestor matches: new",
                   edges=(_edge("source", src, item.item_id, "produced"),))


def fold(items: Sequence[Item], view: RegistryView | None = None
         ) -> tuple[list[Verdict], RegistryView]:
    """Run the chain over a sequence IN ORDER, admitting each NEW or DESCENDANT row as it goes.

    This is the property the federation needs stated once: ten agents handing in ten tellings of
    one strategy produce ONE admitted mechanism and NINE provenance edges, whichever order they
    arrive in and whichever stage catches each one.
    """
    v = view if view is not None else RegistryView()
    out: list[Verdict] = []
    for item in items:
        verdict = dedup(item, v)
        if verdict.verdict in (NEW, DESCENDANT_OF):
            v.add(item, mech=verdict.mechanism_key)
        out.append(verdict)
    return out, v


def census(verdicts: Sequence[Verdict]) -> dict[str, Any]:
    """What a pass's chain did, by stage -- the audit that tells reposts from agreement."""
    by_stage: dict[str, int] = {}
    for v in verdicts:
        if v.verdict != NEW:
            by_stage[v.stage] = by_stage.get(v.stage, 0) + 1
    return {
        "n": len(verdicts),
        "new": sum(1 for v in verdicts if v.is_new),
        "duplicates": sum(1 for v in verdicts if v.is_duplicate),
        "descendants": sum(1 for v in verdicts if v.is_descendant),
        "by_deciding_stage": by_stage,
        "edges": sum(len(v.edges) for v in verdicts),
        "thresholds": {"semantic_duplicate": SEMANTIC_DUPLICATE_THRESHOLD,
                       "descendant": DESCENDANT_THRESHOLD, "shingle_k": SHINGLE_K},
        "rule": ("canonical source -> content hash -> semantic similarity -> mechanism identity "
                 "-> genealogy; ten reposts are one mechanism and nine provenance edges, and a "
                 "genuinely different descendant branches"),
    }

```

### libs\research\information_decay.py
```python
"""INFORMATION DECAY -- every input to the state vector carries its true age, and a weight
that says how much of it is still information.

THE ORDER THIS ANSWERS (principal, 2026-09-05): "every minute X_t = {market, macro, flows,
positioning, cross-asset, news, liquidity, execution, tail, regime}, but every input carries its
true age. Don't pretend weekly COT becomes new every minute. Information_j(t) = Value_j x
Decay_j(age_j) ... Then the allocator sees the freshest valid state every cycle."

WHAT WAS WRONG BEFORE. `state_vector_build` writes one `at` stamp for the whole vector, and
`pf_allocator` refuses the vector when THAT stamp is older than two hours. Inside the vector a
COT z-score read on Friday evening, a daily regime fit and a spread read from a tape that stopped
an hour ago all wear the same age -- the age of the file. The consumer cannot tell a fresh state
from a stale one because nothing on the input says when it was last true.

THE REGISTRY. One `InformationClass` per kind of input, each with the age at which half its
information is gone, the fastest interval at which recomputing it could see anything NEW, the
structural lag between the thing happening and the desk being able to know it, and the reason
those numbers are what they are. The reasons are the point: a half-life nobody can argue with is
a half-life nobody can correct.

THE SHAPES. Most classes decay exponentially in age (`0.5 ** (age / half_life)`): a bar's close
is half as informative one span later because a new bar has arrived and told the desk what the
old one could only forecast. Two classes are EPISODIC: a central-bank decision is fully in force
until the next meeting supersedes it, and a macro print is the state of that series until the
next print, after which it is a vintage rather than a reading. Those step to zero when superseded
and only fade between.

AGE IS MEASURED FROM AVAILABILITY, NEVER FROM THE EVENT. A COT report dated Tuesday is public on
Friday evening; its age on Saturday is one day, not four, and its age on Wednesday afternoon is
NEGATIVE -- it does not exist yet. A negative age is refused as a point-in-time violation rather
than clipped to zero, because clipping is exactly how a backtest reads Friday's report on
Wednesday and reports an edge. The convention is `libs.data.feature_store`'s: report_date +
`COT_RELEASE_LAG`, unless the row carries its own `available_time`.

TRUTHFUL CADENCE. `truthful_cadence(cls)` is the fastest interval at which a recompute can see
new information of that class. A minute solve over hourly bars is a minute solve over the SAME
HOUR, and this module says so rather than letting a 60-second timer look like 60 fresh readings.

Pure stdlib except for one constant borrowed from the feature store. No I/O, no network.
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from typing import Any

from libs.data.feature_store import COT_RELEASE_LAG
from libs.data.pit import revise as _pit_revise
from libs.data.pit import stamp as _pit_stamp

__all__ = [
    "REGISTRY",
    "STALE_WEIGHT",
    "InformationClass",
    "PITViolation",
    "age_of",
    "available_time_of",
    "decay",
    "information",
    "is_new_information",
    "stamp",
    "state_freshness",
    "truthful_cadence",
]

_MIN = 60.0
_HOUR = 3_600.0
_DAY = 86_400.0

#: Below this weight an input is STALE for the consumer's purposes: two half-lives gone for an
#: exponential class, or superseded for an episodic one. A quarter, because a state built from
#: inputs that are three-quarters forgotten is describing the past, and the consumer should be
#: told that rather than left to infer it from a file mtime.
STALE_WEIGHT = 0.25

EXPONENTIAL = "exponential"
#: A bar's information is dated from its CLOSE -- an open bar is a forecast, not a reading -- and
#: halves every span because the next close supersedes it. Same formula as exponential; the
#: separate name records the convention.
BAR = "bar"
#: In force until the next episode, then superseded: weight 1 before the expiry, 0 after.
STEP = "step"
#: The current reading of a series until the next print; fades in between (a month-old CPI is
#: half as informative because the next print will say whether it was the start of something),
#: and goes to zero once the next print exists -- at which point the old one is a vintage.
RELEASE = "release"


class PITViolation(ValueError):
    """Information dated after the moment it is being used at. Never clipped, always refused."""


@dataclass(frozen=True)
class InformationClass:
    """One kind of input and the honest arithmetic of its ageing."""

    name: str
    #: EXPONENTIAL/BAR: the age at which weight = 0.5. STEP/RELEASE: the typical interval to
    #: the next episode, used as the expiry when the caller does not know the real one.
    half_life_s: float
    #: The fastest interval at which recomputing could see NEW information of this class.
    cadence_s: float
    shape: str
    #: Structural lag between the thing happening (event_time) and the desk being able to know
    #: it. Zero for anything published at its own stamp.
    publication_lag_s: float
    #: WHY the half-life is what it is. Required, because a number without a reason is a number
    #: nobody can correct.
    why: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _cls(name: str, half_life_s: float, cadence_s: float, shape: str, why: str,
         publication_lag_s: float = 0.0) -> InformationClass:
    return InformationClass(name, float(half_life_s), float(cadence_s), shape,
                            float(publication_lag_s), why)


#: THE REGISTRY. Every class states why. Ordered fastest to slowest so a reader sees the clock.
REGISTRY: dict[str, InformationClass] = {c.name: c for c in (
    _cls("tick", 10.0, 1.0, EXPONENTIAL,
         "a tick is the market's last word until the next one, and on a liquid Fusion feed the "
         "next one is seconds away; ten seconds without a print is already a thin market"),
    _cls("quote_spread", 60.0, 1.0, EXPONENTIAL,
         "the quoted spread is an execution condition; the venue re-quotes within seconds and a "
         "minute-old spread is the previous liquidity state, not this one"),
    _cls("tick_flow", 5.0 * _MIN, 60.0, EXPONENTIAL,
         "signed tick-volume imbalance is a flow READ over a window; what the last five minutes "
         "showed is half-gone five minutes later because the window has rolled past it"),
    _cls("bar_M1", 60.0, 60.0, BAR, "one span: the next close supersedes this one"),
    _cls("bar_M5", 5.0 * _MIN, 5.0 * _MIN, BAR, "one span: the next close supersedes this one"),
    _cls("bar_M15", 15.0 * _MIN, 15.0 * _MIN, BAR, "one span: the next close supersedes it"),
    _cls("bar_H1", _HOUR, _HOUR, BAR,
         "one span: the desk's own lake is hourly, so an hourly close is the finest reading it "
         "has and the next hour's close is the only thing that can replace it"),
    _cls("bar_H4", 4.0 * _HOUR, 4.0 * _HOUR, BAR, "one span: the next close supersedes it"),
    _cls("bar_D1", _DAY, _DAY, BAR, "one span: a daily regime fit is a daily object"),
    _cls("bar_W1", 7.0 * _DAY, 7.0 * _DAY, BAR, "one span: the next weekly close supersedes it"),
    _cls("yield", 15.0 * _MIN, 60.0, EXPONENTIAL,
         "a yield quote moves in seconds on the print and drifts in minutes between; the desk "
         "reads it as a level that feeds the dollar and gold, and fifteen minutes is how long a "
         "rates-driven move takes to be fully reflected in the FX and metals it drives"),
    _cls("liquidity_tape", 15.0 * _MIN, 60.0, EXPONENTIAL,
         "spread and activity percentiles from the tape describe the current session's "
         "execution conditions; rollover, news windows and session opens change them on a "
         "quarter-hour clock"),
    _cls("regime_fit", _HOUR, _HOUR, EXPONENTIAL,
         "the state-vector fits are refreshed on the hourly cycle and see one new bar an hour; "
         "a fit older than that is describing the previous bar's world"),
    _cls("news", 4.0 * _HOUR, 5.0 * _MIN, EXPONENTIAL,
         "a headline's surprise is priced within the session it lands in; four hours on, half "
         "of what it told the desk is already in the price and the rest is a narrative"),
    _cls("calendar_event", 6.0 * _HOUR, _HOUR, EXPONENTIAL,
         "where an instrument sits in a release's life (PRE_EVENT, SHOCK, DRIFT ...) is an "
         "hourly question; the phases themselves last hours"),
    _cls("swap", _DAY, _DAY, EXPONENTIAL,
         "the broker's overnight financing is re-quoted once a day at rollover, and the desk "
         "pays exactly one day of it per day held"),
    _cls("etf_flow", _DAY, _DAY, EXPONENTIAL,
         "GLD and its peers publish holdings once a day after the close; the flow the desk sees "
         "is yesterday's and tomorrow's file replaces it"),
    _cls("cot", 7.0 * _DAY, 7.0 * _DAY, EXPONENTIAL,
         "the CFTC reports positioning weekly; a report dated Tuesday is public Friday evening "
         "(the feature store's COT_RELEASE_LAG) and the next report is the only thing that can "
         "tell the desk whether the positioning it read has since unwound",
         publication_lag_s=COT_RELEASE_LAG.total_seconds()),
    _cls("macro_monthly", 30.0 * _DAY, 30.0 * _DAY, RELEASE,
         "a monthly print (CPI, NFP, PMI) is the state of its series until the next print; the "
         "value used at any moment is the VINTAGE available then -- a revision is a new row with "
         "its own available_time (libs.data.pit.revise), never an edit of the row the desk "
         "decided on"),
    _cls("macro_quarterly", 91.0 * _DAY, 91.0 * _DAY, RELEASE,
         "GDP and the quarterly national accounts print once a quarter and are revised for "
         "years; the same vintage rule as the monthly class, on a quarterly clock"),
    _cls("cb_decision", 42.0 * _DAY, 42.0 * _DAY, STEP,
         "a policy decision is fully in force until the next scheduled meeting supersedes it; "
         "six weeks is the modal FOMC/ECB/BoE interval, and the caller passes the real next "
         "meeting when the calendar knows it"),
)}


# ---------------------------------------------------------------------------- time handling
def _as_utc(t: datetime | str | float | int) -> datetime:
    """An aware UTC datetime from a datetime, an ISO string or epoch seconds. Naive is UTC, the
    parquet convention the rest of the desk follows."""
    if isinstance(t, datetime):
        dt = t
    elif isinstance(t, int | float):
        dt = datetime.fromtimestamp(float(t), tz=UTC)
    else:
        try:
            dt = datetime.fromisoformat(str(t))
        except (TypeError, ValueError) as exc:
            raise ValueError(f"not a time: {t!r}") from exc
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=UTC)


def age_of(when: datetime | str | float | int, now: datetime | str | float | int | None = None
           ) -> float:
    """Seconds between `when` -- the AVAILABLE time of the information, or its publication time
    when nothing better is known -- and `now`. Refuses a negative age.

    Refused rather than clipped because a clipped negative age is the quiet form of lookahead:
    the row exists, it is dated in the future, and a consumer that reads it at weight 1.0 has
    used Friday's report on Wednesday.
    """
    t0 = _as_utc(when)
    t1 = _as_utc(now) if now is not None else datetime.now(tz=UTC)
    age = (t1 - t0).total_seconds()
    if age < 0:
        raise PITViolation(f"information available at {t0.isoformat()} used at "
                           f"{t1.isoformat()}: {-age:.0f}s before it existed")
    return age


def available_time_of(cls: str, event_time: datetime | str | float | int) -> datetime:
    """When information of this class about `event_time` became knowable, by the class's
    structural publication lag. COT: report date + Friday-evening release lag."""
    return datetime.fromtimestamp(
        _as_utc(event_time).timestamp() + _class(cls).publication_lag_s, tz=UTC)


def _class(cls: str) -> InformationClass:
    try:
        return REGISTRY[cls]
    except KeyError:
        raise KeyError(f"unknown information class {cls!r}; known: {sorted(REGISTRY)}") from None


# ----------------------------------------------------------------------------------- decay
def decay(cls: str, age_s: float, *, expiry_s: float | None = None) -> float:
    """Weight in [0, 1] of information of class `cls` at `age_s` seconds after it became
    available.

    `expiry_s` is the age at which the next episode arrived (the next meeting, the next print)
    for the STEP and RELEASE shapes; when the caller does not know it the class's typical
    interval stands in. Negative age is a PIT violation and is refused.
    """
    c = _class(cls)
    age = float(age_s)
    if age != age:                                             # NaN: no stamp, no weight
        return 0.0
    if age < 0:
        raise PITViolation(f"{cls}: age {age:.0f}s is negative -- information from the future")
    if c.shape in (EXPONENTIAL, BAR):
        return float(0.5 ** (age / c.half_life_s))
    expiry = float(expiry_s) if expiry_s is not None else c.half_life_s
    if age >= expiry:
        return 0.0                                             # superseded by the next episode
    if c.shape == STEP:
        return 1.0
    return float(0.5 ** (age / c.half_life_s))                 # RELEASE: fades, then vintage


def information(value: float, cls: str, age_s: float, *, expiry_s: float | None = None) -> float:
    """Information_j(t) = Value_j x Decay_j(age_j). A NaN value stays NaN: no reading is not a
    reading of zero."""
    v = float(value)
    if v != v:
        return v
    return v * decay(cls, age_s, expiry_s=expiry_s)


def truthful_cadence(cls: str) -> float:
    """The fastest interval, in seconds, at which recomputing this class can see anything new.

    A minute solve over hourly bars is a minute solve over the SAME HOUR: the bars class answers
    3600 here, so a consumer solving every 60s knows that 59 of its 60 solves read the same
    information, and the report says so instead of counting them as fresh.
    """
    return _class(cls).cadence_s


def is_new_information(cls: str, age_s: float, last_solve_age_s: float) -> bool:
    """Could a recompute now see information of this class that the previous solve could not?

    True when the two ages fall in different cadence intervals -- a new bar closed, a new
    report was published -- and False when both solves are reading the same interval.
    """
    cad = _class(cls).cadence_s
    return int(float(age_s) // cad) != int(float(last_solve_age_s) // cad)


def state_freshness(entries: Mapping[str, float | tuple[str, float]],
                    *, expiry_s: Mapping[str, float] | None = None) -> dict[str, dict[str, Any]]:
    """Per input: its class, age, weight, whether it is stale, and the cadence at which it can
    honestly be re-read.

    `entries` maps a name to `(class, age_s)`, or a class name straight to an age when the name
    IS the class. An age of NaN (an input with no stamp) is reported at weight 0 and stale --
    absence is not freshness.
    """
    out: dict[str, dict[str, Any]] = {}
    for name, ent in entries.items():
        if isinstance(ent, tuple):
            cls, age = str(ent[0]), float(ent[1])
        else:
            cls, age = str(name), float(ent)
        c = _class(cls)
        exp = float(expiry_s[name]) if expiry_s and name in expiry_s else None
        w = decay(cls, age, expiry_s=exp)
        out[str(name)] = {
            "cls": cls, "age_s": age, "weight": round(w, 6), "stale": bool(w < STALE_WEIGHT),
            "half_life_s": c.half_life_s, "cadence_s": c.cadence_s, "shape": c.shape,
        }
    return out


# ----------------------------------------------------------------------------------- stamp
def stamp(row: Mapping[str, Any], cls: str, *, event_time: datetime | str | float | int | None,
          published_time: datetime | str | float | int | None,
          available_time: datetime | str | float | int | None = None,
          ingested_time: datetime | str | float | int | None = None,
          source: str | None = None, revision_of: str | None = None,
          revision_reason: str = "") -> dict[str, Any]:
    """A point-in-time-complete COPY of `row` for information class `cls`.

        event_time      when the thing happened (the class's clock: the report date, the print)
        published_time  when the producer made it public (None when the producer has no stamp)
        available_time  when THIS DESK could know it -- defaults to `ingested_time`, and is
                        REFUSED when earlier than `published_time`: nothing is knowable before
                        it is published, and a row that says otherwise is a backfill wearing a
                        live stamp
        ingested_time   when the desk took it in (now, by default)

    Delegates the base fields (source_version, payload_hash) to `libs.data.pit.stamp` so the
    census in `scripts/check_pit.py` counts these rows as stamped, and to `libs.data.pit.revise`
    when `revision_of` names the payload hash of the row this corrects -- the vintage rule: a
    revision is a new row whose availability is floored at the revision time.
    """
    c = _class(cls)
    now = _as_utc(ingested_time) if ingested_time is not None else datetime.now(tz=UTC)
    pub = _as_utc(published_time) if published_time is not None else None
    avail = _as_utc(available_time) if available_time is not None else now
    if pub is not None and avail < pub:
        raise PITViolation(f"{cls}: available_time {avail.isoformat()} is before published_time "
                           f"{pub.isoformat()} -- nothing is knowable before it is published")
    ev = _as_utc(event_time) if event_time is not None else None
    if ev is not None and pub is not None and pub < ev and c.publication_lag_s > 0:
        raise PITViolation(f"{cls}: published_time {pub.isoformat()} precedes event_time "
                           f"{ev.isoformat()} for a class with a publication lag")
    body: dict[str, Any] = {k: v for k, v in row.items()
                            if k not in ("available_time", "ingested_time", "source_version",
                                         "payload_hash")}
    body["information_class"] = cls
    body["half_life_s"] = c.half_life_s
    body["cadence_s"] = c.cadence_s
    body["event_time"] = ev.isoformat() if ev is not None else body.get("event_time")
    body["published_time"] = pub.isoformat() if pub is not None else None
    body["available_time"] = avail.isoformat()
    body["ingested_time"] = now.isoformat()
    src = source or str(row.get("source") or cls)
    if revision_of:
        return _pit_revise(body, revision_of=revision_of, reason=revision_reason or "revised",
                           source=src, now=now)
    return _pit_stamp(body, src, now=now)

```

### libs\research\orphan_scan.py
```python
"""ORPHANS BEYOND MODULES — every producer whose output nothing consumes.

`dormancy` answers this for CODE: which module does nothing import, which script does nothing
schedule. That is one producer class out of many, and it is not the expensive one. The expensive
orphans are further down the chain, where the desk has already paid for the discovery:

    a dataset collected and turned into no feature
    a feature computed and used in no hypothesis
    a hypothesis written and never tested
    a recommendation accepted and never implemented
    a survivor validated and never portfolio-tested
    a failure recorded and never mined
    a near-survivor banked and never revisited

Each of those is value that reached the desk and stopped. NONE of them is visible to an importer
count, a scheduler check, or a test suite -- the code all works, the artifacts all exist, and the
chain is broken at a join nobody is watching. This is L1.54(a)'s CONVERSION_FAILURE state applied
to research objects rather than to Python modules.

WHY THIS IS A SCAN AND NOT A LEDGER. A ledger would require every producer to register its output,
which is a change to every producer and would be half-adopted forever. The scan reads the artifacts
the desk ALREADY writes and asks whether each stage's population appears downstream. It is
therefore approximate, and it is honest about that: a stage whose artifact is absent reports
UNMEASURED, never zero, because "nobody looked" and "nothing was stranded" are opposite facts and
only one of them is good news.

IT PUBLISHES RATHER THAN PRINTS. Rows go to the `gap_contract` channel, so the max-push queue ranks
them beside every other gap without anyone editing the ranker. Detection that cannot reach a
priority is half a control -- the exact defect that produced this module's sibling this morning.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from libs.research.gap_contract import Gap

__all__ = ["STAGES", "Stage", "StageCount", "scan", "to_gaps"]

_ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class Stage:
    """One join in the conversion chain and the canonical schemas on both sides."""

    name: str
    produced_artifact: str
    consumed_artifact: str
    #: Why a stranded object here is expensive, in the desk's own terms.
    why: str
    #: What to do about it -- required, because a row nobody can act on is a complaint.
    action: str
    source: str = "conversion_debt"
    produced_schema: str = "auto"
    consumed_schema: str = "auto"


#: The joins, ordered along the chain. Each names the artifact that holds the PRODUCED population
#: and the artifact that would show it was CONSUMED. Where the desk writes no such artifact yet,
#: the stage still appears and reports UNMEASURED -- an unwatched join is the finding.
STAGES: tuple[Stage, ...] = (
    Stage("data_to_feature", "data/data_universe_map.json", "data/feature_library.json",
          "a dataset collected and turned into no feature is storage cost with no research "
          "output, and it is the stage where the desk's own measurement showed the largest "
          "leak (catalog breadth ~8.5/10 against ingested-and-tested ~4.5/10)",
          "run the Stage-A screen on the unconverted axes -- SCREEN-ON-DISCOVERY makes this the "
          "same run as the discovery, not a later one",
          produced_schema="data_sources", consumed_schema="feature_sources"),
    Stage("feature_to_hypothesis", "data/feature_library.json", "data/hypothesis_queue.jsonl",
          "a feature computed and used in no hypothesis is compute already spent that bought no "
          "test; the combination engine can enumerate over it for free",
          "enumerate the unused features into the candidate space -- generation is not a trial "
          "(L1.52), so this costs no multiplicity budget",
          produced_schema="features", consumed_schema="hypothesis_references"),
    Stage("hypothesis_to_test", "data/hypothesis_queue.jsonl", "data/full_sweep.json",
          "a hypothesis written and never executed is the queue-backlog state L1.52 names "
          "explicitly: with ideas queued and none tested, the next priority is THROUGHPUT",
          "execute the untested backlog; if experiment capacity binds, that is the engineering "
          "target -- never a reason to generate fewer (L1.54)",
          produced_schema="hypotheses", consumed_schema="full_sweep_survivors"),
    Stage("recommendation_to_change", "docs/research/recommendation_ledger.json",
          "docs/research/recommendation_ledger.json",
          "an accepted recommendation that never became a change is advice the desk paid for and "
          "declined to collect; §41 already requires every row to reach implemented or rejected",
          "close each open row to implemented (with commit) or rejected (with a substantive "
          "reason) -- 'still open' past 14 days is a defect to name, not a backlog",
          produced_schema="recommendations_all", consumed_schema="recommendations_terminal"),
    Stage("survivor_to_portfolio", "data/full_sweep.json", "data/portfolio_admission.json",
          "a validated survivor never tested for INCREMENTAL portfolio value may be the "
          "fiftieth expression of an alpha already deployed; standalone Sharpe cannot tell",
          "run marginal-contribution and independence clustering on each survivor before it is "
          "counted as a discovery",
          produced_schema="full_sweep_survivors", consumed_schema="portfolio_rows"),
    Stage("failure_to_mining", "docs/graveyard.md", "data/graveyard_resurrection_queue.json",
          "a failure recorded and never mined discards the most specific information the desk "
          "owns about where an effect is NOT -- which is also information about where it is",
          "extract failure mode, regime, horizon and cost for each killed hypothesis, then "
          "generate the mutations those fields license",
          produced_schema="graveyard", consumed_schema="resurrection_entries"),
    Stage("near_survivor_to_experiment", "data/research_review.json",
          "data/hypothesis_queue.jsonl",
          "a banked near-survivor never revisited is the cheapest experiment the desk has, "
          "already located and already costed",
          "run the next_experiments the bank licenses, at the ancestry-deflated hurdle -- a "
          "descendant inherits the whole search that produced it",
          produced_schema="near_survivors", consumed_schema="hypothesis_references"),
)


@dataclass(frozen=True)
class StageCount:
    """Both sides of one join, including exact producer identities when measurable.

    `consumed` is deliberately the number of PRODUCED identities found downstream, not the raw
    size of the downstream population. Population subtraction can say that every producer was
    consumed merely because an unrelated downstream artifact happens to contain enough rows.
    """

    stage: Stage
    produced: int | None
    consumed: int | None
    produced_ids: frozenset[str] | None = None
    consumed_ids: frozenset[str] | None = None

    @property
    def measured(self) -> bool:
        return self.produced is not None and self.consumed is not None

    @property
    def stranded_ids(self) -> tuple[str, ...] | None:
        if self.produced_ids is None or self.consumed_ids is None:
            return None
        return tuple(sorted(self.produced_ids - self.consumed_ids))

    @property
    def stranded(self) -> int | None:
        identities = self.stranded_ids
        if identities is not None:
            return len(identities)
        if self.produced is None or self.consumed is None:
            return None
        return max(0, self.produced - self.consumed)

    @property
    def conversion(self) -> float | None:
        """Matched producer identities / produced identities, capped at 1.0."""
        if self.produced is None or self.consumed is None:
            return None
        if self.produced <= 0:
            # Nothing produced is not a conversion failure. It is an upstream problem, and the
            # stage above this one is where it will show up as a real gap.
            return 1.0
        return min(1.0, self.consumed / self.produced)


IdentityRows = dict[str, frozenset[str]]
_NON_ID = re.compile(r"[^\w]+", re.UNICODE)
_TERMINAL_RECOMMENDATION_STATES = frozenset({
    "implemented", "rejected", "retired", "done", "screened",
})


def _normalise(value: object) -> str:
    """Conservative exact-match form; prose is never split into convenient keyword hits."""
    return _NON_ID.sub("_", str(value).strip().casefold()).strip("_")


def _identity_values(value: object) -> set[str]:
    """Flatten explicit identity/reference fields without mining substrings from prose."""
    if isinstance(value, Mapping):
        out: set[str] = set()
        for nested in value.values():
            out.update(_identity_values(nested))
        return out
    if isinstance(value, (list, tuple, set, frozenset)):
        out = set()
        for nested in value:
            out.update(_identity_values(nested))
        return out
    if value is None or isinstance(value, bool):
        return set()
    norm = _normalise(value)
    return {norm} if norm else set()


def _field_values(row: Mapping[str, Any], fields: Iterable[str]) -> set[str]:
    out: set[str] = set()
    for field in fields:
        if field in row:
            out.update(_identity_values(row[field]))
    return out


def _first(row: Mapping[str, Any], fields: Iterable[str], fallback: str = "") -> str:
    for field in fields:
        value = row.get(field)
        if value is not None and str(value).strip():
            return str(value).strip()
    return fallback


def _add(records: dict[str, set[str]], primary: object, aliases: Iterable[str] = ()) -> None:
    display = str(primary).strip()
    norm = _normalise(display)
    if not display or not norm:
        return
    records.setdefault(display, set()).update({norm, *(a for a in aliases if a)})


def _freeze(records: dict[str, set[str]]) -> IdentityRows:
    return {name: frozenset(aliases) for name, aliases in records.items()}


def _read_artifact(path: Path) -> object | None:
    """Load one complete artifact. Corrupt/partial input is UNMEASURED, never an empty set."""
    if not path.exists():
        return None
    try:
        text = path.read_text("utf-8")
    except (OSError, UnicodeError):
        return None
    if path.suffix == ".md":
        return text
    if path.suffix == ".jsonl":
        rows: list[object] = []
        try:
            for line in text.splitlines():
                if line.strip():
                    rows.append(json.loads(line))
        except (TypeError, ValueError):
            return None
        return rows
    try:
        loaded: object = json.loads(text)
        return loaded
    except (TypeError, ValueError):
        return None


def _mapping_rows(doc: object, key: str) -> list[Mapping[str, Any]] | None:
    if not isinstance(doc, Mapping):
        return None
    value = doc.get(key)
    if not isinstance(value, list) or not all(isinstance(row, Mapping) for row in value):
        return None
    return list(value)


def _data_sources(doc: object) -> IdentityRows | None:
    """The live catalog is intentionally mixed: category lists plus ID-keyed source rows."""
    if not isinstance(doc, Mapping) or not isinstance(doc.get("sources"), Mapping):
        return None
    records: dict[str, set[str]] = {}
    for category, value in doc["sources"].items():
        if isinstance(value, list):
            if not all(isinstance(row, Mapping) for row in value):
                return None
            rows = [(f"{category}:{index}", row) for index, row in enumerate(value)]
        elif isinstance(value, Mapping):
            rows = [(str(category), value)]
        else:
            return None
        for fallback, row in rows:
            primary = _first(row, ("id", "name", "source", "url"), fallback)
            aliases = _field_values(row, ("id", "name", "source", "url"))
            aliases.update(_identity_values(category))
            _add(records, primary, aliases)
    return _freeze(records)


def _features(doc: object, *, references_only: bool = False) -> IdentityRows | None:
    rows = _mapping_rows(doc, "features")
    if rows is None:
        return None
    records: dict[str, set[str]] = {}
    for index, row in enumerate(rows):
        primary = _first(row, ("id", "name"), f"feature:{index}")
        fields = ("id", "name", "source", "source_id", "dataset", "data_source") \
            if references_only else ("id", "name")
        _add(records, primary, _field_values(row, fields))
    return _freeze(records)


def _hypotheses(doc: object, *, references_only: bool = False) -> IdentityRows | None:
    if not isinstance(doc, list) or not all(isinstance(row, Mapping) for row in doc):
        return None
    records: dict[str, set[str]] = {}
    for index, row in enumerate(doc):
        primary = _first(row, ("id", "name", "title"), f"hypothesis:{index}")
        fields = (
            "id", "name", "title", "feature", "feature_id", "features", "feature_ids",
            "source_feature", "data", "parent", "parent_id", "ancestor",
            "near_survivor", "killed_by", "mechanism",
        ) if references_only else ("id", "name", "title")
        _add(records, primary, _field_values(row, fields))
    return _freeze(records)


def _full_sweep_survivors(doc: object) -> IdentityRows | None:
    if isinstance(doc, Mapping) and doc.get("survivors_truncated"):
        # The JSON omits identities beyond max_detail; claiming complete conversion would be false.
        return None
    rows = _mapping_rows(doc, "survivors")
    if rows is None:
        return None
    records: dict[str, set[str]] = {}
    for index, row in enumerate(rows):
        key = row.get("key")
        joined = "|".join(str(part) for part in key) if isinstance(key, list) else ""
        primary = joined or _first(row, ("id", "name", "trial"), f"survivor:{index}")
        aliases = _field_values(row, ("id", "name", "trial"))
        aliases.update(_identity_values(joined))
        _add(records, primary, aliases)
    return _freeze(records)


def _recommendations(doc: object, *, terminal_only: bool = False) -> IdentityRows | None:
    rows = _mapping_rows(doc, "recommendations")
    if rows is None:
        return None
    records: dict[str, set[str]] = {}
    for index, row in enumerate(rows):
        status = str(row.get("status", "")).strip().casefold()
        if terminal_only and status not in _TERMINAL_RECOMMENDATION_STATES:
            continue
        primary = _first(row, ("id", "recommendation_id", "summary"),
                         f"recommendation:{index}")
        _add(records, primary, _field_values(row, ("id", "recommendation_id", "summary")))
    return _freeze(records)


def _portfolio_rows(doc: object) -> IdentityRows | None:
    rows = _mapping_rows(doc, "rows")
    if rows is None:
        return None
    records: dict[str, set[str]] = {}
    for index, row in enumerate(rows):
        primary = _first(row, ("survivor", "id", "name"), f"portfolio:{index}")
        _add(records, primary, _field_values(row, ("survivor", "id", "name")))
    return _freeze(records)


def _graveyard(doc: object) -> IdentityRows | None:
    if not isinstance(doc, str):
        return None
    records: dict[str, set[str]] = {}
    for line in doc.splitlines():
        if not line.lstrip().startswith("|"):
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if not cells:
            continue
        primary = cells[0].strip("` ")
        if (not primary or _normalise(primary) in {"name", "signal", "strategy"}
                or not _normalise(primary).strip("_")):
            continue
        # Markdown separator rows contain only punctuation in their first cell.
        if not any(ch.isalnum() for ch in primary):
            continue
        _add(records, primary)
    return _freeze(records)


def _named_rows(doc: object, key: str, *, prefix: str) -> IdentityRows | None:
    rows = _mapping_rows(doc, key)
    if rows is None:
        return None
    records: dict[str, set[str]] = {}
    for index, row in enumerate(rows):
        primary = _first(row, ("name", "id", "key", "trial"), f"{prefix}:{index}")
        _add(records, primary, _field_values(row, ("name", "id", "key", "trial", "axis")))
    return _freeze(records)


def _near_survivors(doc: object) -> IdentityRows | None:
    rows = _mapping_rows(doc, "near_survivor_bank")
    if rows is None:
        return None
    records: dict[str, set[str]] = {}
    for index, row in enumerate(rows):
        primary = _first(row, ("id", "killed_by", "mechanism", "name"),
                         f"near-survivor:{index}")
        _add(records, primary, _field_values(
            row, ("id", "killed_by", "mechanism", "name")))
    return _freeze(records)


def _extract(path: Path, schema: str) -> IdentityRows | None:
    doc = _read_artifact(path)
    if doc is None:
        return None
    if schema == "data_sources":
        return _data_sources(doc)
    if schema == "feature_sources":
        return _features(doc, references_only=True)
    if schema == "features":
        return _features(doc)
    if schema == "hypothesis_references":
        return _hypotheses(doc, references_only=True)
    if schema == "hypotheses":
        return _hypotheses(doc)
    if schema == "full_sweep_survivors":
        return _full_sweep_survivors(doc)
    if schema == "recommendations_all":
        return _recommendations(doc)
    if schema == "recommendations_terminal":
        return _recommendations(doc, terminal_only=True)
    if schema == "portfolio_rows":
        return _portfolio_rows(doc)
    if schema == "graveyard":
        return _graveyard(doc)
    if schema == "resurrection_entries":
        return _named_rows(doc, "entries", prefix="resurrection")
    if schema == "near_survivors":
        return _near_survivors(doc)

    return None


def _count(path: Path) -> int | None:
    """Legacy population counter retained for injected-counter callers and focused tests."""
    doc = _read_artifact(path)
    if doc is None:
        return None
    if isinstance(doc, list):
        return len(doc)
    if isinstance(doc, Mapping):
        for key in ("entries", "rows", "items", "records", "survivors", "candidates",
                    "hypotheses", "features", "gaps", "runs", "recommendations"):
            value = doc.get(key)
            if isinstance(value, list):
                return len(value)
        if doc and all(isinstance(value, Mapping) for value in doc.values()):
            return len(doc)
    if isinstance(doc, str):
        rows = _graveyard(doc)
        return None if rows is None else len(rows)
    return None


def scan(*, root: Path | None = None, counter: Callable[[Path], int | None] | None = None,
         ) -> list[StageCount]:
    """Measure exact producer identities at every join.

    `counter` remains as a compatibility/test seam. Production scans use schema-aware identity
    extraction; a downstream row only counts when it names an actual upstream identity.
    """
    r = root or _ROOT
    if counter is not None:
        return [StageCount(stage, counter(r / stage.produced_artifact),
                           counter(r / stage.consumed_artifact)) for stage in STAGES]

    out: list[StageCount] = []
    for stage in STAGES:
        produced_rows = _extract(r / stage.produced_artifact, stage.produced_schema)
        downstream_rows = _extract(r / stage.consumed_artifact, stage.consumed_schema)
        if produced_rows is None or downstream_rows is None:
            out.append(StageCount(
                stage,
                None if produced_rows is None else len(produced_rows),
                None if downstream_rows is None else 0,
                None if produced_rows is None else frozenset(produced_rows),
                None,
            ))
            continue
        downstream_aliases = set().union(*downstream_rows.values()) if downstream_rows else set()
        matched = frozenset(
            identity for identity, aliases in produced_rows.items()
            if aliases & downstream_aliases
        )
        out.append(StageCount(stage, len(produced_rows), len(matched),
                              frozenset(produced_rows), matched))
    return out


def to_gaps(counts: list[StageCount]) -> list[Gap]:
    """Published rows. AN UNWATCHED JOIN IS THE FINDING, not an omission from the report.

    A stage whose artifact is missing publishes `current=None`, which the queue ranks ABOVE a
    partially-converted stage. That ordering is deliberate and it is the whole reason this scan is
    worth running: the desk knows roughly how bad its measured conversion is, and does not know
    which joins nobody is watching at all.
    """
    out: list[Gap] = []
    for sc in counts:
        s = sc.stage
        if sc.measured:
            stranded_ids = sc.stranded_ids
            sample = ""
            if stranded_ids:
                sample = f"; stranded identity sample: {', '.join(stranded_ids[:5])}"
            evidence = "identity-matched" if stranded_ids is not None else "population-only"
            detail = (f"{sc.consumed} of {sc.produced} converted ({evidence}); "
                      f"{sc.stranded} stranded at {s.name}{sample}")
            action = s.action
        else:
            missing = [a for a, n in ((s.produced_artifact, sc.produced),
                                      (s.consumed_artifact, sc.consumed)) if n is None]
            detail = (f"UNMEASURED -- {', '.join(missing)} absent or unrecognised, so this join "
                      "is unwatched. Nobody-looked and nothing-stranded are opposite facts")
            action = (f"emit the missing artifact so the join can be counted, THEN {s.action}. "
                      "An unwatched join outranks a measured one because an unknown quantity is "
                      "being ignored rather than worked (L1.28a)")
        out.append(Gap(
            aspect=f"conversion::{s.name}", source=s.source,
            current=sc.conversion, ceiling=1.0, detail=detail, action=action,
            artifact=s.consumed_artifact, evidence=s.why,
            dependency=s.produced_artifact, tags=("conversion-chain",)))
    return out


def summarise(counts: list[StageCount]) -> dict[str, Any]:
    """Report shape: the WORST-CONVERTING measured join first, and the unwatched ones named.

    The bottleneck stage is the work (L1.53). A report ordered by stage name would bury it.
    """
    measured = [c for c in counts if c.measured]
    unwatched = [c.stage.name for c in counts if not c.measured]
    ranked = sorted(measured, key=lambda c: (c.conversion or 0.0))
    return {
        "joins": len(counts), "measured": len(measured), "unwatched": unwatched,
        "bottleneck": ranked[0].stage.name if ranked else None,
        "chain": [{
            "stage": c.stage.name,
            "produced": c.produced,
            "consumed": c.consumed,
            "stranded": c.stranded,
            "conversion": None if c.conversion is None else round(c.conversion, 4),
            "identity_matched": c.stranded_ids is not None,
            "consumed_id_sample": (
                sorted(c.consumed_ids)[:5] if c.consumed_ids is not None else None),
            "stranded_id_sample": (
                list(c.stranded_ids[:5]) if c.stranded_ids is not None else None),
        } for c in counts],
        "note": ("UNMEASURED joins outrank measured ones. The desk knows roughly how bad its "
                 "measured conversion is; it does not know which joins nobody watches at all."),
    }

```

### libs\validation\brain_calibration.py
```python
"""AN INDEPENDENT WITNESS ON THE ONE NUMBER THIS DESK MEASURED ITSELF GETTING WRONG.

WHY THIS FILE EXISTS. On 2026-08-01 the desk audited its own gauntlet end to end
(docs/research/gate_power_audit.md). The sensitivity floor -- the true Sharpe at which the gate
finally admits a real candidate with usable probability -- sits at TRUE SHARPE 5.0 (85.42% power;
23.75% at 3.0, 5.83% at 2.0, 1.67% at 1.5). The same desk records
`REAL_EDGE_OOS_SHARPE_BAND = (0.5, 1.5)` in libs/validation/robustness_filters.py as the band where
verified edge is empirically observed to live, from a 131,441-backtest external sweep. The gate is
therefore calibrated 3.3-10x above the ENTIRE range its own evidence says it is hunting in, and the
audit closes by recording that as a job explicitly not finished (§9).

A miss that large wants a witness that has never seen this repo. This module is that witness.

THE WITNESS. A WorldQuant BRAIN webinar transcript (2026-08-01, principal-supplied) states the
operational thresholds of a LIVE institutional alpha pipeline -- one that pays research consultants
on its output, so its thresholds are not a teaching example or a paper's suggestion but numbers
somebody's money passes through daily. It is calibrating the same quantity: "how good must a
candidate be before we act on it". It arrives at a Sharpe bar of 1.0 and a target of ~1.25.

THE HEADLINE, and it is the entire reason to read this file:

    desk sensitivity floor   5.00 true Sharpe   (measured, gate_power_audit §1)
    BRAIN submission target  1.25 Sharpe        (stated, transcript)
    ratio                    4.0x

    desk real-edge band      (0.50, 1.50) OOS Sharpe   (external 131k sweep)
    BRAIN recent-period floor 0.50 Sharpe               (stated, transcript)
    ratio                    1.0x  -- EXACT AGREEMENT at the bottom of the band

Two independent sources -- a 131,441-backtest sweep and a live institutional pipeline -- put the
lower edge of actionable edge at 0.5 Sharpe, from completely different data. The desk's gate is
positioned an order of magnitude above the point where both of them agree real alpha begins. That
is a far stronger statement than either source alone, and it is what this module exists to make
countable.

ANNUALISATION AND ASSET-CLASS CAVEAT -- READ BEFORE USING ANY NUMBER HERE.
BRAIN alphas are US EQUITY, daily rebalanced, dollar-neutral, and their "Sharpe" is computed on
their own platform convention (their own PnL definition, their own annualisation, their own cost
model). This desk trades CRYPTO PERPS continuously, funds every eight hours, and annualises on 365
days. Neither the periodicity, the cost base, the return definition, nor the survivorship
properties of the two universes match. These numbers are COMPARABLE IN ORDER OF MAGNITUDE ONLY and
must NEVER be pasted into a gate as-is.
A READER WHO TAKES 1.25 AS A THRESHOLD HAS MISUSED THIS MODULE.
The comparison that is legitimate is "is this desk's bar 1x or 10x off?", and the answer to that
survives every convention difference above. The comparison that is not legitimate is "therefore set
the threshold to 1.25".

STATUS -- stated plainly because this desk's own rule says a module with tests and no production
importer is DRAFTED, not built. This one is deliberately DRAFTED. It is a CALIBRATION REFERENCE and
it is wired into no decision path on purpose: an external number that quietly becomes a threshold
is precisely the failure the caveat above exists to prevent. `gap_report()` is shaped for a
reporting script to dump as JSON; nothing here may be imported by a gate, a screen, or a sizer.

CONFIDENCE MARKING. Several of the transcript's numbers are spoken asides rather than slides, and
an aside quoted to two decimal places is how a soft number becomes a hard threshold six months
later. Every constant below therefore carries its verbatim quote and one of three markers, and
`SOURCE_NOTES` exposes the same thing machine-readably:
    STATED      -- said as a definite threshold
    APPROXIMATE -- hedged, rounded, or spoken as an aside ("about", "at least 0.5 or 1.0")
    DERIVED     -- computed here from a stated number, never spoken (e.g. the OOS score weight)
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Literal

from libs.validation.robustness_filters import REAL_EDGE_OOS_SHARPE_BAND

__all__ = [
    "BRAIN",
    "BRAIN_FITNESS_SUBMISSION_BAR",
    "BRAIN_IS_SCORE_WEIGHT",
    "BRAIN_NEAR_SUBMITTABLE_FITNESS_SHORTFALL",
    "BRAIN_NEAR_SUBMITTABLE_FRACTION",
    "BRAIN_OOS_SCORE_WEIGHT",
    "BRAIN_RECENT_SHARPE_FLOOR",
    "BRAIN_RECENT_SHARPE_FLOOR_UPPER",
    "BRAIN_SELF_CORRELATION_CAP",
    "BRAIN_SHARPE_BAR",
    "BRAIN_SHARPE_TARGET",
    "BRAIN_STAGE2_ACCEPTANCE_FRACTION",
    "BRAIN_TRUNCATION_BAND",
    "BRAIN_TRUNCATION_DEFAULT",
    "BRAIN_TS_BACKFILL_FITNESS_AFTER",
    "BRAIN_TS_BACKFILL_FITNESS_BEFORE",
    "DESK_CAMPAIGN_N",
    "DESK_CORRELATION_CLUSTER_THRESHOLD",
    "DESK_FORWARD_SLOTS",
    "DESK_MAX_SINGLE_NAME_WEIGHT",
    "DESK_REAL_EDGE_BAND",
    "DESK_SENSITIVITY_FLOOR_SHARPE",
    "SOURCE_NOTES",
    "Calibration",
    "Comparison",
    "annualisation_caveat",
    "compare",
    "gap_report",
]

Confidence = Literal["STATED", "APPROXIMATE", "DERIVED"]

SOURCE = "WorldQuant BRAIN webinar transcript, 2026-08-01 (principal-supplied)"

# ---------------------------------------------------------------------------------------------
# BRAIN thresholds. Transcribed verbatim; see SOURCE_NOTES for the quote behind each one.
# ---------------------------------------------------------------------------------------------

#: STATED. The alpha submission bar, on BRAIN's own composite `fitness` statistic. NOT a Sharpe and
#: NOT convertible to one here: fitness folds returns, turnover and drawdown together on a formula
#: the transcript never states, so any conversion would be this desk inventing the missing half.
#: Kept because the ratio between a candidate's fitness and this bar is meaningful even when the
#: absolute number is not portable.
BRAIN_FITNESS_SUBMISSION_BAR = 1.0

#: STATED, as the bar being missed in "you're only getting 0.7 sharpe instead of one, or instead of
#: 1.25", and again in the near-submittable example ("Sharpe 0.9 vs a 1.0 bar").
BRAIN_SHARPE_BAR = 1.0

#: APPROXIMATE. Same breath as the line above -- two numbers quoted together, so both are kept
#: rather than one being picked. 1.0 is the bar an alpha must clear; 1.25 is what a submitter is
#: actually aiming at. The gap between them is the transcript's own margin of safety, and this
#: desk keeping both is the difference between reading a threshold and reading a practice.
BRAIN_SHARPE_TARGET = 1.25

#: APPROXIMATE. "Near-submittable" = roughly 80% of the submission metrics -- e.g. Sharpe 0.9
#: against a 1.0 bar. The operationally important half is what it MEANS: near-submittable alphas
#: are worth IMPROVING, not discarding. That is a triage policy this desk does not have; its
#: gauntlet emits PASS/FAIL and a near-miss dies silently.
BRAIN_NEAR_SUBMITTABLE_FRACTION = 0.80

#: APPROXIMATE. The same near-miss band expressed on fitness: "fitness ~30% below threshold" still
#: counts as worth working on. Not the exact complement of the 80% figure above (that would be 20%),
#: and the discrepancy is left standing rather than reconciled -- reconciling two spoken asides into
#: one tidy number is how a transcript becomes a fabrication.
BRAIN_NEAR_SUBMITTABLE_FITNESS_SHORTFALL = 0.30

#: STATED, and the single most transferable number in the transcript: "25% weightage is only for
#: IS". A live pipeline that pays people gives in-sample performance a QUARTER of the score.
BRAIN_IS_SCORE_WEIGHT = 0.25

#: DERIVED -- the complement, never spoken. Out-of-sample carries ~75% of the score.
BRAIN_OOS_SCORE_WEIGHT = 1.0 - BRAIN_IS_SCORE_WEIGHT

#: APPROXIMATE ("around 0.7"). Cap on a new alpha's correlation to the SUBMITTER'S OWN existing
#: pool -- not to the market, and not the cohort-average correlation that
#: libs/research/cohort_independence.py benchmarks at 0.159. It is a per-candidate admission cap
#: against an already-live book, which is a check this desk does not run at all.
BRAIN_SELF_CORRELATION_CAP = 0.7

#: STATED. Position truncation = the maximum weight any single name may carry. Ideal band 5-10%.
BRAIN_TRUNCATION_BAND = (0.05, 0.10)
#: STATED. The platform default inside that band.
BRAIN_TRUNCATION_DEFAULT = 0.08

#: APPROXIMATE ("at least 0.5 or 1.0"). The recent-period floor: the last few years must be
#: POSITIVE on their own, and a negative recent Sharpe is unacceptable however good the full
#: history looks. The LOWER of the two spoken figures is taken as the floor, because taking the
#: higher would be this desk inventing strictness the source did not state.
#:
#: If this ever were ported into a gate -- which the module docstring forbids -- note that the
#: operative encoding is `>= 0.5`, NOT `> 0`. A bare `> 0` on a Sharpe is exactly the guard that
#: shipped a 1.4e31 fake signal here on 2026-08-01: floating-point dust clears it, and a frozen or
#: pegged series produces dust rather than zero.
BRAIN_RECENT_SHARPE_FLOOR = 0.5
BRAIN_RECENT_SHARPE_FLOOR_UPPER = 1.0

#: APPROXIMATE ("approximately top 20%"). Stage-1 -> stage-2 competition acceptance rate.
BRAIN_STAGE2_ACCEPTANCE_FRACTION = 0.20

#: STATED, as a worked example: fitness 1.28 -> 1.42 from adding `ts_backfill` alone. Recorded
#: because it sizes what a single engineering fix is worth on a real pipeline -- +10.9%, from
#: handling missing data properly rather than from a new mechanism. This desk's own audit found the
#: same shape of result (53% of its refutations were measurement failures, not absent alpha).
BRAIN_TS_BACKFILL_FITNESS_BEFORE = 1.28
BRAIN_TS_BACKFILL_FITNESS_AFTER = 1.42

# ---------------------------------------------------------------------------------------------
# This desk's counterpart numbers. Every one is imported or cited, never retyped from memory.
# ---------------------------------------------------------------------------------------------

#: MEASURED, docs/research/gate_power_audit.md §1: the true annualised Sharpe at which the fixed
#: gauntlet first reaches usable power (85.42%; 23.75% at 3.0, 5.83% at 2.0, 1.67% at 1.5). This is
#: the quantity BRAIN's submission bar is the external calibration OF.
DESK_SENSITIVITY_FLOOR_SHARPE = 5.0

#: Imported rather than copied so it cannot silently drift out of agreement with the filter module
#: that owns it. (0.5, 1.5) OOS Sharpe, from a 131,441-backtest external sweep.
DESK_REAL_EDGE_BAND = REAL_EDGE_OOS_SHARPE_BAND

#: libs/portfolio/models.py :: PortfolioConstraints.max_weight default -- the desk's counterpart to
#: BRAIN's position truncation, and the one comparison in this file that runs the OTHER way.
DESK_MAX_SINGLE_NAME_WEIGHT = 0.25

#: libs/portfolio/diversification.py :: apply_correlation_controls(cluster_threshold=0.8). A LOOSE
#: analogue of BRAIN's self-correlation cap: it is a clustering linkage threshold over the existing
#: book, not a per-candidate admission cap, so the two numbers are the same shape but not the same
#: measurement. Reported with that caveat attached rather than dropped.
DESK_CORRELATION_CLUSTER_THRESHOLD = 0.8

#: libs/research/slot_registry.py :: MAX_FORWARD_SLOTS, and the campaign size the gate audit ran.
#: 12/420 = 2.9% is the desk's CAPACITY ceiling on advancement; the measured gate promoted 0.00 of
#: 20 genuine alphas at true SR 2.0-3.0 (audit §6), so the realised rate is lower still.
DESK_FORWARD_SLOTS = 12
DESK_CAMPAIGN_N = 420

#: Below this a Sharpe is not a small Sharpe, it is zero wearing a decimal point, and using it as
#: the denominator of a ratio manufactures an arbitrarily large "gap". Same defect class as the
#: `> 0` variance guard that produced a 1.4e31 prediction premium here on 2026-08-01: the fix is a
#: MEANINGFUL floor, not a tighter comparison against zero. 1e-3 annualised Sharpe is far below any
#: measurable edge and far above float dust.
_SHARPE_FLOOR = 1e-3

#: Ratios inside [1/1.25, 1.25] are reported as COMPARABLE rather than as one side being stricter.
#: The module docstring says these numbers agree to an order of magnitude and no further; declaring
#: a winner on a 6% difference would be reading precision that provably is not there.
_COMPARABLE_RATIO = 1.25

#: Verbatim quotes and confidence markers, machine-readable so a report can carry the provenance
#: alongside the number instead of stripping it. Keyed by constant name.
SOURCE_NOTES: dict[str, tuple[Confidence, str]] = {
    "BRAIN_FITNESS_SUBMISSION_BAR": ("STATED", "alpha submission bar: fitness > 1.0"),
    "BRAIN_SHARPE_BAR": (
        "STATED", "you're only getting 0.7 sharpe instead of one, or instead of 1.25"),
    "BRAIN_SHARPE_TARGET": (
        "APPROXIMATE", "you're only getting 0.7 sharpe instead of one, or instead of 1.25"),
    "BRAIN_NEAR_SUBMITTABLE_FRACTION": (
        "APPROXIMATE", "near-submittable = ~80% of the submission metrics (Sharpe 0.9 vs a 1.0 "
                       "bar) -- worth improving rather than discarding"),
    "BRAIN_NEAR_SUBMITTABLE_FITNESS_SHORTFALL": (
        "APPROXIMATE", "fitness ~30% below threshold is still near-submittable"),
    "BRAIN_IS_SCORE_WEIGHT": ("STATED", "25% weightage is only for IS"),
    "BRAIN_OOS_SCORE_WEIGHT": ("DERIVED", "complement of the stated 25% IS weight; never spoken"),
    "BRAIN_SELF_CORRELATION_CAP": (
        "APPROXIMATE", "self-correlation against your own existing alpha pool capped around 0.7"),
    "BRAIN_TRUNCATION_BAND": ("STATED", "truncation ideal band 5-10%"),
    "BRAIN_TRUNCATION_DEFAULT": ("STATED", "truncation default 8%"),
    "BRAIN_RECENT_SHARPE_FLOOR": (
        "APPROXIMATE", "the last few years must be positive, at least 0.5 or 1.0 sharpe; a "
                       "negative recent sharpe is not acceptable even if the full history looks "
                       "fine"),
    "BRAIN_RECENT_SHARPE_FLOOR_UPPER": ("APPROXIMATE", "at least 0.5 or 1.0"),
    "BRAIN_STAGE2_ACCEPTANCE_FRACTION": (
        "APPROXIMATE", "stage-1 to stage-2 acceptance is approximately the top 20%"),
    "BRAIN_TS_BACKFILL_FITNESS_BEFORE": ("STATED", "fitness 1.28 -> 1.42 from ts_backfill alone"),
    "BRAIN_TS_BACKFILL_FITNESS_AFTER": ("STATED", "fitness 1.28 -> 1.42 from ts_backfill alone"),
}


@dataclass(frozen=True)
class Calibration:
    """One external pipeline's operating thresholds, as a bundle.

    A dataclass rather than loose constants so a SECOND external calibration can be written down
    later and compared on the same axes. One outside number is an anecdote; two that disagree
    would be the more informative result, and there is nowhere to put the second one otherwise.
    """

    source: str
    fitness_bar: float
    sharpe_bar: float
    sharpe_target: float
    near_submittable_fraction: float
    is_score_weight: float
    self_correlation_cap: float
    truncation_default: float
    truncation_band: tuple[float, float]
    recent_sharpe_floor: float
    stage2_acceptance_fraction: float

    @property
    def oos_score_weight(self) -> float:
        """DERIVED, not stated: whatever is not weighted in-sample is weighted out-of-sample."""
        return 1.0 - self.is_score_weight

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "fitness_bar": self.fitness_bar,
            "sharpe_bar": self.sharpe_bar,
            "sharpe_target": self.sharpe_target,
            "near_submittable_fraction": self.near_submittable_fraction,
            "is_score_weight": self.is_score_weight,
            "oos_score_weight": self.oos_score_weight,
            "self_correlation_cap": self.self_correlation_cap,
            "truncation_default": self.truncation_default,
            "truncation_band": list(self.truncation_band),
            "recent_sharpe_floor": self.recent_sharpe_floor,
            "stage2_acceptance_fraction": self.stage2_acceptance_fraction,
        }


BRAIN = Calibration(
    source=SOURCE,
    fitness_bar=BRAIN_FITNESS_SUBMISSION_BAR,
    sharpe_bar=BRAIN_SHARPE_BAR,
    sharpe_target=BRAIN_SHARPE_TARGET,
    near_submittable_fraction=BRAIN_NEAR_SUBMITTABLE_FRACTION,
    is_score_weight=BRAIN_IS_SCORE_WEIGHT,
    self_correlation_cap=BRAIN_SELF_CORRELATION_CAP,
    truncation_default=BRAIN_TRUNCATION_DEFAULT,
    truncation_band=BRAIN_TRUNCATION_BAND,
    recent_sharpe_floor=BRAIN_RECENT_SHARPE_FLOOR,
    stage2_acceptance_fraction=BRAIN_STAGE2_ACCEPTANCE_FRACTION,
)


@dataclass(frozen=True)
class Comparison:
    """The desk's gate position measured against an external pipeline's, in ratios.

    `stricter` is one of DESK / BRAIN / COMPARABLE / UNKNOWN. UNKNOWN is returned for any input
    that cannot be compared and it is deliberately NOT a synonym for COMPARABLE -- an unreadable
    input must produce a verdict a reader stops at, never one that reads as agreement.
    """

    desk_floor_sharpe: float
    desk_band: tuple[float, float]
    brain_sharpe_bar: float
    brain_sharpe_target: float
    ratio_floor_to_bar: float
    ratio_floor_to_target: float
    ratio_floor_to_band_top: float
    stricter: str
    verdict: str

    def summary(self) -> str:
        return (f"desk floor {self.desk_floor_sharpe:.2f} SR vs BRAIN target "
                f"{self.brain_sharpe_target:.2f} SR = {self.ratio_floor_to_target:.2f}x "
                f":: {self.stricter} :: {self.verdict}")


def annualisation_caveat() -> str:
    """The comparability caveat, as text a report can print next to the numbers.

    Duplicated from the module docstring ON PURPOSE. A caveat that lives only in a docstring is
    read once by the author and never again by the person pasting a number into a config; this
    version travels with `gap_report()` into whatever JSON or dashboard consumes it. The test
    suite asserts BOTH copies still contain every load-bearing phrase, because a calibration module
    whose caveat quietly got deleted is more dangerous than no calibration module at all.
    """
    return (
        "COMPARABILITY CAVEAT. BRAIN alphas are US equity, daily rebalanced, dollar-neutral, and "
        "their Sharpe is computed on their own platform convention -- their PnL definition, their "
        "annualisation, their cost model. This desk trades crypto perps continuously, funds every "
        "eight hours, and annualises on 365 days. Periodicity, cost base, return definition and "
        "universe survivorship all differ. These numbers are COMPARABLE IN ORDER OF MAGNITUDE "
        "ONLY and must never be pasted into a gate as-is. A reader who takes 1.25 as a threshold "
        "has misused this module. The legitimate question is 'is this desk's bar 1x or 10x off?', "
        "whose answer survives every convention difference above; the illegitimate one is "
        "'therefore set the threshold to 1.25'."
    )


def _ratio(desk: float, external: float) -> float:
    """desk / external, with a MEANINGFUL floor on the denominator rather than a `> 0` guard."""
    if not math.isfinite(desk) or not math.isfinite(external):
        return math.nan
    if abs(external) < _SHARPE_FLOOR:
        return math.nan
    return desk / external


def compare(desk_floor_sharpe: float, desk_band: tuple[float, float]) -> Comparison:
    """This desk's sensitivity floor against BRAIN's submission bar.

    Direction convention: for a FLOOR, higher means stricter, so a ratio above 1 means this desk
    demands more than the external pipeline does before it will act.

    Every unreadable input lands in the UNKNOWN branch and reports no ratio. That is the house rule
    about ambiguous branches applied to a reference module: the tempting behaviour here is to fall
    back on defaults and print a reassuring number, and a fabricated 4.0x is indistinguishable from
    a measured one once it is in a report.
    """
    floor = float(desk_floor_sharpe)
    lo, hi = float(desk_band[0]), float(desk_band[1])
    bar, target = BRAIN.sharpe_bar, BRAIN.sharpe_target
    nan = math.nan

    if not all(math.isfinite(v) for v in (floor, lo, hi)):
        return Comparison(floor, (lo, hi), bar, target, nan, nan, nan, "UNKNOWN",
                          "UNCOMPARABLE: non-finite desk input, so no ratio is reported. A "
                          "missing measurement is not a passing one")
    if floor < _SHARPE_FLOOR:
        return Comparison(floor, (lo, hi), bar, target, nan, nan, nan, "UNKNOWN",
                          f"UNCOMPARABLE: a sensitivity floor of {floor:.3g} Sharpe is at or "
                          f"below the {_SHARPE_FLOOR:g} noise floor -- that is not a low bar, it "
                          "is an unmeasured one")
    if hi < lo or hi < _SHARPE_FLOOR:
        return Comparison(floor, (lo, hi), bar, target, nan, nan, nan, "UNKNOWN",
                          f"UNCOMPARABLE: desk band ({lo:.3g}, {hi:.3g}) is inverted or "
                          "degenerate")

    r_bar = _ratio(floor, bar)
    r_target = _ratio(floor, target)
    r_band = _ratio(floor, hi)

    if r_target > _COMPARABLE_RATIO:
        stricter = "DESK"
        verdict = (
            f"DESK STRICTER BY {r_target:.1f}x. This desk admits candidates only from true Sharpe "
            f"{floor:.2f}, against a live institutional pipeline that submits at {bar:.2f} and "
            f"targets {target:.2f}. It also sits {r_band:.1f}x above {hi:.2f}, the TOP of the "
            f"band where this desk's own evidence says real edge lives -- so the gate is not "
            f"merely conservative, it is positioned outside the range it is hunting in. BRAIN "
            f"pays consultants for alphas this gauntlet would never show anyone.")
    elif r_target < 1.0 / _COMPARABLE_RATIO:
        stricter = "BRAIN"
        verdict = (
            f"BRAIN STRICTER BY {1.0 / r_target:.1f}x. This desk's floor of {floor:.2f} Sharpe "
            f"sits BELOW the external submission target of {target:.2f}, which reverses the "
            f"2026-08-01 finding and should be checked against docs/research/gate_power_audit.md "
            f"before anything is concluded from it.")
    else:
        stricter = "COMPARABLE"
        verdict = (
            f"COMPARABLE. Desk floor {floor:.2f} and BRAIN target {target:.2f} agree within "
            f"{_COMPARABLE_RATIO:.2f}x, which is as close as two conventions this different can "
            f"meaningfully be read.")

    return Comparison(floor, (lo, hi), bar, target, r_bar, r_target, r_band, stricter, verdict)


def _jsonable(x: float) -> float | None:
    """NaN is not valid JSON. An unmeasurable ratio is emitted as null, never as 0.0 or a guess."""
    return None if not math.isfinite(x) else float(x)


def _direction(ratio: float | None, *, higher_is_stricter: bool, desk_present: bool) -> str:
    """Which side is tighter, given that some of these quantities invert.

    A FLOOR is stricter when it is higher; a position CAP is stricter when it is LOWER. Reporting
    both as 'ratio > 1 means stricter' would flip the sign of the most interesting row in the
    report -- the desk's 25% single-name cap against BRAIN's 8% -- and turn a finding that this
    desk is three times more concentrated into a claim that it is three times safer.

    Three ways to have no ratio, kept DISTINCT because collapsing them loses the finding: the desk
    has no such check at all (ABSENT), the desk has one but the value handed in is unreadable
    (UNMEASURED), or the external number is too small to divide by. Only the first is a statement
    about the desk's process; reporting the other two the same way would invent a missing gate.
    """
    if not desk_present:
        return "NO DESK COUNTERPART -- recorded as ABSENT, not as satisfied"
    if ratio is None:
        return "UNMEASURED -- the desk value handed in is not a finite number, so no ratio"
    if 1.0 / _COMPARABLE_RATIO <= ratio <= _COMPARABLE_RATIO:
        return "COMPARABLE"
    tighter = ratio > 1.0 if higher_is_stricter else ratio < 1.0
    factor = ratio if ratio > 1.0 else 1.0 / ratio
    return f"DESK {'STRICTER' if tighter else 'LOOSER'} by {factor:.1f}x"


def _row(quantity: str, desk_value: float | None, desk_source: str, brain_key: str,
         brain_value: float, *, higher_is_stricter: bool, note: str) -> dict[str, Any]:
    ratio = None if desk_value is None else _jsonable(_ratio(desk_value, brain_value))
    confidence, quote = SOURCE_NOTES.get(brain_key, ("STATED", ""))
    return {
        "quantity": quantity,
        # _jsonable, not float(): a non-finite desk value would otherwise emit a bare NaN, which
        # json.dumps writes happily and no JSON parser downstream accepts.
        "desk_value": None if desk_value is None else _jsonable(float(desk_value)),
        "desk_source": desk_source,
        "brain_constant": brain_key,
        "brain_value": float(brain_value),
        "brain_confidence": confidence,
        "brain_quote": quote,
        "ratio_desk_over_brain": ratio,
        "higher_is_stricter": higher_is_stricter,
        "direction": _direction(ratio, higher_is_stricter=higher_is_stricter,
                                desk_present=desk_value is not None),
        "note": note,
    }


def gap_report(desk_floor_sharpe: float = DESK_SENSITIVITY_FLOOR_SHARPE,
               desk_band: tuple[float, float] = DESK_REAL_EDGE_BAND) -> dict[str, Any]:
    """Every desk threshold beside its BRAIN counterpart and the ratio, JSON-serialisable.

    Rows whose desk counterpart DOES NOT EXIST are emitted with a null ratio and the direction
    "NO DESK COUNTERPART", never omitted. An absent check that vanishes from a comparison table
    reads as a passed one, which is the same defect the `asset_drift` filter exists to avoid: a
    gate that appears to guard and guards nothing is worse than no gate, because it is counted.
    """
    cmp_ = compare(desk_floor_sharpe, desk_band)
    lo, hi = float(desk_band[0]), float(desk_band[1])
    slot_rate = DESK_FORWARD_SLOTS / DESK_CAMPAIGN_N

    rows = [
        _row("gate sensitivity floor vs submission target (Sharpe)",
             float(desk_floor_sharpe), "gate_power_audit.md §1 -- 85.42% power at true SR 5.0",
             "BRAIN_SHARPE_TARGET", BRAIN.sharpe_target, higher_is_stricter=True,
             note="THE HEADLINE. The desk's own audit records this gap as unfinished business."),
        _row("gate sensitivity floor vs submission bar (Sharpe)",
             float(desk_floor_sharpe), "gate_power_audit.md §1",
             "BRAIN_SHARPE_BAR", BRAIN.sharpe_bar, higher_is_stricter=True,
             note="Same floor against the hard bar rather than the target."),
        _row("real-edge band, upper (OOS Sharpe)", hi,
             "robustness_filters.REAL_EDGE_OOS_SHARPE_BAND (131,441-backtest sweep)",
             "BRAIN_SHARPE_BAR", BRAIN.sharpe_bar, higher_is_stricter=True,
             note="Neither side is a gate here: an observed band against a live bar. That two "
                  "unrelated sources land within 1.5x is what makes the headline row credible."),
        _row("real-edge band, lower (OOS Sharpe)", lo,
             "robustness_filters.REAL_EDGE_OOS_SHARPE_BAND (131,441-backtest sweep)",
             "BRAIN_RECENT_SHARPE_FLOOR", BRAIN.recent_sharpe_floor, higher_is_stricter=True,
             note="EXACT AGREEMENT. A 131k-backtest sweep and a live institutional pipeline put "
                  "the bottom of actionable edge at the same 0.5 Sharpe from unrelated data."),
        _row("max single-name weight", DESK_MAX_SINGLE_NAME_WEIGHT,
             "libs/portfolio/models.py :: PortfolioConstraints.max_weight",
             "BRAIN_TRUNCATION_DEFAULT", BRAIN.truncation_default, higher_is_stricter=False,
             note="THE ROW THAT RUNS THE OTHER WAY. On concentration this desk is the loose one, "
                  "which is worth more than the rows confirming what the audit already said."),
        _row("correlation control", DESK_CORRELATION_CLUSTER_THRESHOLD,
             "libs/portfolio/diversification.py :: cluster_threshold",
             "BRAIN_SELF_CORRELATION_CAP", BRAIN.self_correlation_cap, higher_is_stricter=False,
             note="LOOSE ANALOGUE, not a like-for-like: a clustering linkage threshold over the "
                  "existing book versus a per-candidate admission cap against a live pool. The "
                  "numbers are the same shape; the measurements are not."),
        _row("stage advancement rate", slot_rate,
             f"MAX_FORWARD_SLOTS={DESK_FORWARD_SLOTS} over an N={DESK_CAMPAIGN_N} campaign",
             "BRAIN_STAGE2_ACCEPTANCE_FRACTION", BRAIN.stage2_acceptance_fraction,
             higher_is_stricter=False,
             note="Capacity ceiling only. The measured gate promoted 0.00 of 20 genuine alphas at "
                  "true SR 2.0-3.0 (audit §6), so the realised rate is lower than this row."),
        _row("out-of-sample share of the candidate score", None,
             "ABSENT -- the gauntlet emits PASS/FAIL, so nothing is weighted",
             "BRAIN_OOS_SCORE_WEIGHT", BRAIN.oos_score_weight, higher_is_stricter=True,
             note="No counterpart exists because this desk SCREENS where BRAIN RANKS. Audit §6 "
                  "names the top-K ranked screen as the largest remaining lever (R0262); this is "
                  "the same finding arriving from outside."),
        _row("near-miss triage", None,
             "ABSENT -- a near-miss is FAILED and dies silently",
             "BRAIN_NEAR_SUBMITTABLE_FRACTION", BRAIN.near_submittable_fraction,
             higher_is_stricter=True,
             note="BRAIN keeps candidates at ~80% of the bar and IMPROVES them. On a desk whose "
                  "own measurement blames 53% of refutations on measurement failure rather than "
                  "absent alpha, discarding near-misses discards mostly fixable ones."),
    ]

    return {
        "module": "libs/validation/brain_calibration.py",
        "status": "CALIBRATION REFERENCE -- wired into no decision path, by design",
        "source": SOURCE,
        "caveat": annualisation_caveat(),
        "headline": cmp_.verdict,
        "comparison": {
            # _jsonable throughout: an UNKNOWN comparison must still produce a report a parser can
            # read, with nulls where the numbers are, rather than a NaN that dies downstream.
            "desk_floor_sharpe": _jsonable(cmp_.desk_floor_sharpe),
            "desk_band": [lo, hi],
            "brain_sharpe_bar": float(cmp_.brain_sharpe_bar),
            "brain_sharpe_target": float(cmp_.brain_sharpe_target),
            "ratio_floor_to_bar": _jsonable(cmp_.ratio_floor_to_bar),
            "ratio_floor_to_target": _jsonable(cmp_.ratio_floor_to_target),
            "ratio_floor_to_band_top": _jsonable(cmp_.ratio_floor_to_band_top),
            "stricter": cmp_.stricter,
        },
        "brain": BRAIN.to_dict(),
        "rows": rows,
    }

```

### libs\validation\shift_leak.py
```python
"""SHIFT-LAG LEAK DETECTION -- does a signal only "predict" because it contains the answer?

REHOMED 2026-09-05, and the reason matters more than the move. `shift_ic` lived inside
`scripts/revalidate_clocks.py`, a crypto-era script deleted in the MT5 purge. It is not a crypto
function: it is a LEAK DETECTOR, and its output is read as evidence that a signal's timestamps
are honest. Deleting the script would have deleted a gate, which is the one thing a cleanup may
never do. `tests/research/test_shift_leak_detector.py` was already pointing at it.

THE MATHS IS UNCHANGED, BYTE FOR BYTE, deliberately. This function has a history: an earlier
version shifted only the numerator leg, which for a ratio signal whose denominator is the
target's own price does not shift the signal at all -- it rebuilds the forward return and reports
an IC near +0.93 on pure noise. That false positive produced the "kimchi is a ~73% timestamp
artifact" verdict on 2026-07-29, which justified a keying change that then 24h-mispaired three
days of live collection and put a refuted mechanism in the graveyard (R0067). A leak detector
that fires on clean data is worse than none: it makes good data look broken and gets "fixed" in
the direction of the damage. Re-deriving it during a file move would risk exactly that, so the
body below is copied, not rewritten. The only post-move edits are annotations and two accumulator
RENAMES (`sig`/`rr` -> `sig_acc`/`rr_acc`, because the originals were rebound from list to array
in place and strict mypy reads that as a type error); every arithmetic line is untouched.

WHAT THE ARGUMENTS MEAN, since the names came from the venue it was written for:
  ``signal``  date -> raw signal level.
  ``gb``      date -> the TARGET instrument's price. Forward returns are computed from this.
  ``shift``   days to lag the finished signal by before scoring it.
  ``fx``      optional date -> divisor, when the signal is a ratio expressed in another currency.
              When given, the signal is built as ``signal/fx/gb - 1``, which is why the
              denominator leg has to move with the numerator.

Returns the IC, or NaN when fewer than 60 aligned dates exist -- too short to score is reported
as unmeasured, never as zero.
"""
from __future__ import annotations

from typing import Any

import numpy as np

#: date key -> value. The keys were `datetime.date` at the venue this was written for and are
#: strings in the MT5 daily panels, and the body only ever intersects and sorts them, so the key
#: type is left open rather than narrowed to whichever caller arrives first.
DateSeries = dict[Any, float]


def shift_ic(signal: DateSeries, gb: DateSeries, shift: int,
             fx: DateSeries | None = None) -> float:
    """IC of z(signal shifted by `shift` days) vs NEXT-day return.

    THE SIGNAL IS BUILT SAME-INSTANT FIRST, THEN THE FINISHED SERIES IS SHIFTED. This used to
    shift only the numerator leg -- signal[i+shift] over fx[i]/gb[i] -- which for a ratio signal
    whose DENOMINATOR is the target's own price does not shift the signal at all: it rebuilds it
    as roughly gb[i+1]/gb[i], i.e. the forward return itself. Measured on an i.i.d.-noise premium
    with zero predictive content by construction, the old form reported a +1d cell of +0.931.

    That false positive is not hypothetical: it is what produced the "kimchi is a ~73% timestamp
    artifact" verdict on 2026-07-29, which justified a +1d keying change that then 24h-mispaired
    three days of live collection and put a refuted mechanism in the graveyard (R0067). A leak
    detector that fires on clean data is worse than none -- it makes good data look broken and
    gets "fixed" in the direction of the damage.
    """
    dates = sorted(set(signal) & set(gb) & (set(fx) if fx else set(gb)))
    if len(dates) < 60:
        return float("nan")
    btc = np.array([gb[d] for d in dates])
    ret = np.zeros(len(btc))
    ret[1:] = btc[1:] / btc[:-1] - 1.0
    fwd = np.roll(ret, -1)
    series = np.array([signal[d] / fx[d] / gb[d] - 1.0 for d in dates]) if fx else \
        np.array([signal[d] for d in dates], dtype=float)
    sig_acc: list[float] = []
    rr_acc: list[float] = []
    for i in range(len(dates)):
        j = i + shift
        if 0 <= j < len(dates):
            sig_acc.append(series[j])
            rr_acc.append(fwd[i])
    sig, rr = np.array(sig_acc, float), np.array(rr_acc, float)
    z = np.zeros(len(sig))
    for t in range(20, len(sig)):
        w = sig[t - 20:t]
        sd = w.std()
        z[t] = (sig[t] - w.mean()) / sd if sd > 0 else 0.0
    zv, fv = z[20:-1], rr[20:-1]
    return float(np.corrcoef(zv, fv)[0, 1]) if zv.std() and fv.std() else 0.0


```

### scripts\check_sizing_derivation.py
```python
#!/usr/bin/env python3
"""SIZING DERIVATION (R0135) -- no number that moves money may be chosen by feel.

WHY THIS FENCE EXISTS, stated as the pattern that produced it rather than as a principle someone
liked. Four constants in the money path were found defective in a single session, ALL of the same
shape -- a round number picked by analogy or by taste, never computed:

  MAX_LEVERAGE = 10        picked as "aggressive but not crazy". It was ANTI-aggression: it made a
                           0.9pct structural stop deploy 9pct of a 20pct risk budget while a lazy
                           2pct stop deployed the full 20pct, penalising the exact behaviour the
                           calculated stop exists to produce.
  MIN_STOP_PCT = 0.5       one number for gold and for SOL. Measured, the median adverse excursion
                           over a 24h hold is 0.64pct on PAXG and 1.28pct on SOL -- the flat floor
                           was ~2.5x too loose on one and about right on the other.
  trail = 1R               a trailed stop one R behind price sits AT the noise floor, because the
                           entry stop is permitted to sit at the noise floor. It failed the same
                           test the entry stop has to pass.
  MAX_RISK_PER_TRADE=0.20  chosen by analogy to the leverage in a screenshot. Simulated, it meets a
                           -90pct drawdown with ~certainty EVEN WHEN THE STRATEGY IS PROFITABLE,
                           and past full Kelly more size makes growth NEGATIVE.

Every one was caught by hand, late, and only because someone happened to look. Four of four is not
bad luck, it is a missing mechanism -- and this desk's own standard is that a defect caught by hand
is not caught (L1.41). A money-path constant is exactly where a comfortable-looking number does the
most damage, because it never errors; it just quietly sets the growth rate.

THE RULE: every module-level numeric constant in a sizing/risk module must either be DERIVED at
runtime (computed from a measurement) or carry, in the comment attached to it, the derivation that
set it -- a simulation, a measurement, a cited law, or an explicit "this is a hard external limit".
"I picked it" is not a derivation. The fence reads the comments because that is where the
justification has to live for the next reader anyway.

DELIBERATELY NOT AUTOMATED FURTHER: this cannot check that the cited derivation is CORRECT, only
that one exists and is specific. That is still most of the value -- three of the four defects above
would have been caught at the moment of writing, because none of them had anything to cite.

    python scripts/check_sizing_derivation.py [--report-only] [--json]
"""
from __future__ import annotations

import argparse
import ast
import json
import re
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

#: Modules whose module-level numbers decide position size, leverage or risk. Kept to the money
#: path on purpose -- a fence that flags every constant in the repo is a fence nobody reads.
#:
#: RE-POINTED AT THE LIVE MONEY PATH, 2026-09-05. This scope was emptied earlier the same day when
#: the retired book's three modules (run_conviction_trader, run_llm_trader, resolve_paper_book)
#: were deleted, and the note left behind called re-pointing "a wiring decision, not a cleanup's to
#: make". It was owed, and the cost of leaving it owed was measured: with an empty scope the fence
#: graded ZERO modules, reported UNMEASURED, and held `run_law_gate --laws-only` RED -- which in
#: turn skipped the CI seal job, which is why release identity could not reach ok=true.
#:
#: The modules below are where a number becomes a position on THIS desk. Pointing at them found 33
#: constants with no machine-readable derivation, including LOT, MIN_LOT, BASE_HEAT, RR,
#: TURNOVER_COST_R and BOOK_WORST_DD_R -- every number that sizes a real trade. The fence had been
#: blind to the entire live money path, which is a strictly worse state than the empty scope it
#: honestly reported.
_SIZING_MODULES: tuple[str, ...] = (
    "desks/mt5/mt5desk/gateway.py",                  # LOT, and the order path itself
    "desks/mt5/mt5desk/decision_core.py",            # stop distance, R:R, per-trade risk
    "desks/mt5/mt5desk/risk_units.py",               # the R unit every other number is quoted in
    "desks/mt5/mt5desk/gateway_config_fallback.py",  # what sizes the book when config is absent
    "desks/mt5/research/book_sizing.py",             # base heat and the minimum-capital question
    "desks/mt5/research/heat_policy.py",             # the floor, the measured ceiling, the target
    "desks/mt5/research/pf_allocator.py",            # per-sleeve heat, turnover, the no-trade band
)

#: The count of undocumented money-path constants this scope may carry. A RATCHET, in the shape
#: `check_read_without_writer.MAX_DANGLING` already uses: it may fall and may never rise.
#:
#: WHY A RATCHET RATHER THAN A GREEN FENCE. Thirty-three constants were found the moment the scope
#: was pointed correctly. Most carry a real justification in prose that this fence's vocabulary
#: simply does not match -- `MIN_STATE_WORLDS` explains itself with "at cvar_alpha 0.20 a 24-world
#: bucket puts ~5 worlds in the CVaR tail", which is a derivation by any reading. The fence's own
#: standing instruction for that case is to widen `_DERIVATION_WORDS`, and five earlier classes
#: were widened exactly so. But widening it by twenty words in one sitting to clear thirty-three
#: constants at once is how a check stops asking anything, and writing thirty-three derivations
#: from guesswork would be worse -- inventing a justification is the defect this fence exists to
#: catch, committed by the fence's own maintainer.
#:
#: So the honest state is recorded rather than resolved: the money path is IN SCOPE and fenced
#: from today, no NEW undocumented constant can be added, and the residue is a named debt that
#: falls as each number's real derivation is written down. Lower this line, never raise it.
#:
#: 33 at the moment of re-pointing; 25 after eight unambiguous plumbing exemptions (an MT5 order
#: magic number, two in-process caches, two venue retcode tables, the session window definitions,
#: and two session clock times). The ratchet is set to the count that actually stands, not to the
#: count before the exemptions -- a ceiling with slack in it is not a ratchet.
MAX_UNJUSTIFIED = 17

#: Words that mark a real derivation. A comment must contain at least one AND a digit, so
#: "measured" alone does not pass -- the number itself has to appear in the justification.
#: EXTERNAL FACTS are a legitimate derivation category and were missing on the first run: a
#: published venue fee schedule is not a number anyone chose, and rewording the comment to hit the
#: vocabulary would be gaming the fence. Widen the list on a false positive; never reword an organ
#: to satisfy a check -- the same rule the build standard learned.
_DERIVATION_WORDS = (
    "simulat", "measur", "derived", "computed", "observed", "median", "backtest", "kelly",
    "exchange limit", "venue limit", "hard limit", "protocol", "law l1", "law l2", "l1.", "l2.",
    "empirical", "calibrat", "estimated from", "fitted", "per the", "found by",
    "published", "fee schedule", "venue schedule", "quoted", "top-of-book", "spread on",
    "exchange minimum", "venue minimum", "minimum notional", "rejects orders", "tier",
    "documented",
    # STATISTICAL derivations -- the third false-positive class this fence produced. A threshold
    # placed a standard error below a breakeven IS derived; the vocabulary simply lacked the words.
    "standard error", "binomial", "sigma", "power", "breakeven", "posterior", "variance",
    # SCHEDULE derivations -- the fourth false-positive class (2026-08-05). A staleness threshold
    # set from a producer's known firing rate is derived from a fact you can look up in the
    # manifest, exactly as a fee schedule is: CHART_STALE_H=2.0 because the builder's cron cadence
    # is 20 minutes, so 2h is five consecutive missed builds -- the organ has STOPPED, not
    # hiccuped. Widening is the sanctioned response here (this list's own rule, three classes
    # above); rewording run_conviction_trader to hit the vocabulary would be gaming the fence.
    "cadence", "cron", "consecutive", "schedule",
    # PAIRED-DESIGN / SIGNIFICANCE-LEVEL derivations -- the fifth false-positive class
    # (2026-08-29). `resolve_paper_book.py` derives TRAIL_FWD_T=1.7 as the one-sided ~0.05
    # critical value, TRAIL_FWD_DECIDE_N=25 as the earliest read of a PAIRED design, and
    # TRAIL_FWD_HARD_N=50 by alignment with the sleeve's own KILL_AFTER_N -- all three stated
    # plainly in one preregistration block, none of them reachable by the vocabulary above.
    # Widening is this list's own sanctioned response ("Widen the list on a false positive;
    # never reword an organ to satisfy a check"), and the alternative was worse than cosmetic:
    # four false breaches held `run_law_gate --laws-only` RED, and a gate red on correct code
    # is how a gate red on a real breach stops being read.
    # `alpha` is deliberately ABSENT: this desk uses it to mean edge on nearly every line, so it
    # would match everything and the fence would stop asking anything.
    "one-sided", "two-sided", "paired", "|t|", "t-stat", "p-value", "significance",
    "critical value", "aligned with",
    # MEASURED-BOOK derivations -- the sixth false-positive class, found 2026-09-05 when the scope
    # was re-pointed at the live MT5 money path. Every earlier class was a statistical procedure;
    # this one is a number read off the desk's OWN BOOK or its own solver, which is the most
    # defensible kind of derivation there is and had no word in the list.
    #
    # `BOOK_WORST_DD_R = 33.7` carries eleven lines explaining that it is the worst peak-to-trough
    # drawdown the armed book produced at the sweep that validated it, that it is in-sample, and
    # that a safety haircut beyond 1.22x would drop the heat budget below the 3.12% the book
    # already runs -- and it was reported "no derivation cited" because none of those words was
    # in the vocabulary. `MIN_STATE_WORLDS = 24` explains itself as "at cvar_alpha 0.20 a 24-world
    # bucket puts ~5 worlds in the CVaR tail". `ADMISSION_ITERATIONS` cites a solver that
    # "converged in 104 iterations, so this is headroom".
    #
    # Widening is this list's own standing instruction for exactly this case ("Widen the list on a
    # false positive; never reword an organ to satisfy a check"), and rewording eleven lines of
    # correct reasoning to contain the token "measured" would have been the gaming it forbids.
    # Each word is specific enough not to match prose generally: no bare "book", no bare "risk".
    "peak-to-trough", "worst drawdown", "own worst", "the armed book", "cvar",
    "converged", "iterations", "headroom", "the sweep that", "solver",
)

#: Constants that are pure plumbing, not sizing. Naming them is a DECISION, same as the schedule
#: exemptions in the build standard -- "it's obviously fine" has to be written down to count.
_EXEMPT: dict[str, str] = {
    "MAX_PAGES": "http paging bound, touches no size",
    "BAR": "bar interval string, not a number",
    "PIVOT_K": "chart-reading parameter, not a sizing input",
    "MAX_LEVELS": "display/brief truncation, not a sizing input",
    "LEVEL_TOL_PCT": "chart-reading parameter, not a sizing input",
    "NOISE_LOOKBACK_HOURS": "measurement window length; the MEASUREMENT is the derived thing",
    "TRADEABLE_MAX_AGE_MIN": "staleness gate on news, not a sizing input",
    "MIN_PROB": "domain bound on a probability (below 0.5 is the other side of the trade)",
    "MAX_PROB": "domain bound on a probability (over-confidence tell, see L1.29)",
    "STOP_MISMATCH_TOL": "consistency tolerance between two stated numbers, not a size",
    "MAX_CHARS": "prompt truncation, not a sizing input",
    "_BAR_MS": "milliseconds in the bar interval -- a unit conversion, not a decision",
    "_INTERVALS": "venue interval-name mapping table, no sizing content",
    "_TFS": "which timeframes to chart, not a sizing input",
    # ------------------------------------------------------------------ the MT5 money path, 2026-09-05
    # Named when the scope was re-pointed at desks/mt5. Deliberately CONSERVATIVE: anything that
    # could plausibly reach a lot size was left IN, including ATR_N (it sets the stop distance, and
    # the stop distance sets the size) and SIZING_FROM_YEAR (it selects the data the capital
    # requirement is computed from). Exempting those would be the fence excusing itself.
    "MAGIC": "MT5 order identifier -- how the desk recognises its own orders, not a quantity",
    "_SV_CACHE": "in-process cache, not a decision",
    "_EXTRA_DIMS_CACHE": "in-process cache, not a decision",
    "RETCODE_MEANING": "venue retcode -> English lookup; the numbers are the venue's, not ours",
    "ACCEPTED_RETCODES": "the venue's own success codes -- an external fact, not a chosen number",
    "GOLD_WINDOWS": "session window definitions (names and clock bounds), not a sizing input",
    "CANCEL_HOUR": "session clock time, not a size -- the per-bracket TTL is the real limit",
    "CLOSE_HOUR": "session clock time (force-close), not a size",
}


#: A module-level CONSTANT assignment, e.g. `TRAIL_FWD_T = 1.7` or `MAX: int = 5`. Used only to
#: decide whether a line above a constant is a SIBLING in the same declaration group -- so it is
#: deliberately strict: no indentation (module level), an ALL-CAPS name, one `=`.
_RE_CONST_ASSIGN = re.compile(r"^[A-Z][A-Z0-9_]*\s*(?::[^=]+)?=")


def _comment_block(lines: list[str], lineno: int) -> str:
    """The comment attached to a constant: the `#:` block above it plus any trailing comment.

    `#:` above and `#` trailing are both idiomatic here, and the justification legitimately lives
    in either -- so both are read rather than mandating a style nobody would follow."""
    out = []
    i = lineno - 2                                   # line above the assignment (0-indexed)
    # A `#:` BLOCK DOCUMENTS ITS WHOLE GROUP (gap-fixer 2026-08-29). This walk used to stop at
    # the first non-comment line, so a block covering several related constants was credited to
    # exactly one of them -- whichever happened to sit directly beneath it -- and its siblings
    # were reported as undocumented. MEASURED: `scripts/resolve_paper_book.py` carries one
    # preregistration block explaining TRAIL_FWD_DECIDE_N=25, TRAIL_FWD_HARD_N=50 and
    # TRAIL_FWD_T=1.7 together ("25 paired differences at |t|>=1.7 (one-sided ~0.05) is the
    # earliest read; 50 is the hard stop"), and this fence reported three of them plus
    # TRAIL_FWD_CHALLENGER as `no derivation cited`. Those four false breaches held
    # `run_law_gate --laws-only` RED, and a gate that is red on correct code is how a gate that
    # is red on a REAL breach stops being read (L1.43, gate-optimality).
    #
    # The rule is deliberately narrow: skip only CONTIGUOUS sibling constant assignments, never
    # a blank line and never any other statement. A group is a block of adjacent constants under
    # one comment; the moment anything separates them they are no longer one declaration and the
    # comment no longer speaks for them. Both directions are pinned by test.
    while i >= 0:
        stripped = lines[i].strip()
        if stripped.startswith("#"):
            out.append(lines[i])
            i -= 1
            continue
        if out:
            break                                    # the block ended; do not reach past it
        if _RE_CONST_ASSIGN.match(lines[i]):
            i -= 1                                   # a sibling in the same group -- keep walking
            continue
        break
    if lineno - 1 < len(lines) and "#" in lines[lineno - 1]:
        out.append(lines[lineno - 1].split("#", 1)[1])
    return " ".join(out).lower()


def audit_module(root: Path, rel: str) -> dict[str, Any]:
    p = root / rel
    try:
        src = p.read_text("utf-8")
    except OSError as exc:
        return {"module": rel, "state": "UNREADABLE", "why": str(exc), "undocumented": []}
    lines = src.splitlines()
    try:
        tree = ast.parse(src)
    except SyntaxError as exc:
        return {"module": rel, "state": "UNPARSEABLE", "why": str(exc), "undocumented": []}

    checked, bad = [], []
    for node in tree.body:                            # module level only
        if not isinstance(node, (ast.Assign, ast.AnnAssign)):
            continue
        targets = node.targets if isinstance(node, ast.Assign) else [node.target]
        for t in targets:
            if not isinstance(t, ast.Name) or not t.id.isupper():
                continue
            val = node.value
            nums = [n for n in ast.walk(val) if isinstance(n, ast.Constant)
                    and isinstance(n.value, (int, float)) and not isinstance(n.value, bool)] if val else []
            if not nums:
                continue
            if t.id in _EXEMPT:
                checked.append({"name": t.id, "state": "EXEMPT", "why": _EXEMPT[t.id]})
                continue
            blob = _comment_block(lines, node.lineno)
            has_word = any(w in blob for w in _DERIVATION_WORDS)
            has_digit = any(c.isdigit() for c in blob)
            if has_word and has_digit:
                checked.append({"name": t.id, "state": "DERIVED"})
            else:
                bad.append({"name": t.id, "line": node.lineno,
                            "why": ("no derivation cited" if not has_word else
                                    "derivation words present but no numbers -- cite the "
                                    "measurement or simulation that produced this value")})
                checked.append({"name": t.id, "state": "UNJUSTIFIED", "line": node.lineno})
    return {"module": rel, "state": "OK" if not bad else "UNJUSTIFIED-CONSTANTS",
            "n_constants": len(checked), "n_bad": len(bad),
            "undocumented": bad, "constants": checked}


def build_report(root: Path | None = None) -> dict[str, Any]:
    root = root or _ROOT
    mods = [audit_module(root, m) for m in _SIZING_MODULES]
    bad = [m for m in mods if m["state"] != "OK"]
    n_bad = sum(m.get("n_bad", 0) for m in mods)
    return {
        "generated": datetime.now(tz=UTC).isoformat(),
        "law": "L1.41/L2.4 -- a number that moves money is a decision, and an undocumented "
               "decision cannot be reviewed, disputed or improved. Four money-path constants were "
               "found defective in one session, all of them round numbers picked by analogy.",
        # AN EMPTY SCOPE IS "UNMEASURED", NEVER "OK" (L1.28a). `_SIZING_MODULES` emptied on
        # 2026-09-05 when the retired book's three sizing modules were deleted, and a fence that
        # grades zero modules and prints OK is indistinguishable from one that looked and found
        # nothing wrong -- the exact conflation this desk fences everywhere else. Reported as its
        # own state so the day someone re-points this scope, the gap is visible in the artifact.
        # RATCHETED is deliberately NOT called OK. The artifact must never say the money path is
        # fully derived while a named debt stands -- that is the conflation this fence spent its
        # empty-scope note refusing. It says instead: in scope, fenced, and N still owed.
        "status": ("UNMEASURED" if not mods
                   else "OK" if not bad
                   else "RATCHETED" if n_bad <= MAX_UNJUSTIFIED
                   else "UNJUSTIFIED-CONSTANTS"),
        "n_modules": len(mods), "n_unjustified": n_bad, "ratchet": MAX_UNJUSTIFIED,
        "detail": ("no module is in scope -- the money path this fence was built for was deleted "
                   "with the retired universe (2026-09-05) and no replacement scope has been "
                   "wired, so NOTHING was graded. This is a wiring gap, not a clean bill of health"
                   if not mods else
                   f"{sum(m.get('n_constants', 0) for m in mods)} money-path constants across "
                   f"{len(mods)} modules, {n_bad} without a cited derivation"
                   + ("" if not n_bad else ": " + ", ".join(
                       f"{m['module'].split('/')[-1]}:{b['name']}"
                       for m in mods for b in m["undocumented"]))),
        "modules": mods,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--report-only", action="store_true")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    rep = build_report()
    out = _ROOT / "data/sizing_derivation.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(rep, indent=2), "utf-8")
    if args.json:
        print(json.dumps(rep, indent=2))
    else:
        print(f"sizing derivation (L1.41): {rep['status']} -- {rep['detail']}")
        for m in rep["modules"]:
            for b in m.get("undocumented", []):
                print(f"  {m['module']}:{b['line']} {b['name']}: {b['why']}")
    if rep["status"] == "RATCHETED":
        print(f"  RATCHET: {rep['n_unjustified']} owed, ceiling {rep['ratchet']}. "
              f"Lower this line as each derivation is written; it may never rise.")
    return 0 if args.report_only or rep["status"] in {"OK", "RATCHETED"} else 2


if __name__ == "__main__":
    sys.exit(main())

```
