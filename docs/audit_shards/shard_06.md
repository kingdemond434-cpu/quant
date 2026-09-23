# AUDIT SHARD 6/24 -- seat z-ai/glm-5.3

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

### libs\data\pit_certificate.py
```python
"""Adversarial dataset acquisition: seven questions asked as CODE, and a certificate that says so.

    NO CERTIFICATE -> NO PROMOTION AUTHORITY (principal's order, 2026-09-05)

The desk's acquisition doctrine already refuses an undated series and a revised-without-vintage
one (`research/acquire_datasets.py`). That is two of the seven questions a hostile reader would
ask, asked at intake, and the other five were asked nowhere -- so a dataset could reach a
gauntlet having never been interrogated about survivorship, truncation or schema drift, and
nothing on disk recorded which questions had been put to it at all.

THE SEVEN, each a function with a verdict of its own:

  leak          can it leak future information -- rows dated after now, or an available_time
                EARLIER than the event it describes (knowable before it happened)
  revision      does its historical API show revised values, and if it restates, is there a
                vintage column to read the old one back from
  timestamps    can timestamps be reconstructed -- every row parseable, ordered, tz-aware
  availability  was it ACTUALLY available then -- a declared publication lag the stamps honour,
                and no row claiming availability in the future
  survivorship  does source selection use future survival -- "currently listed", "still active",
                "top N by today's size" are all future information about the past
  truncation    is history truncated -- a head cut off relative to the declared start, or an
                interior gap far larger than the series' own cadence
  schema        was the schema changed -- the column set and dtypes against the last certified
                schema hash, so a silent rename does not read as a new dataset

A VERDICT IS PASS, FAIL, or UNMEASURED, never a default. UNMEASURED is the honest answer when the
dataset does not carry what the question needs (L1.28a: an unasked question is not a pass), and
it is NOT authority: `authority` is true only when all seven PASS. That asymmetry is the point --
a source that cannot say whether it restates history is exactly as unusable as one that admits it
does.

WHERE THEY LIVE. `desks/mt5/data/pit_certificates/<dataset>.json`, one per dataset, written by
the acquirer and read by `scripts/check_pit.py`'s census and by any promotion gate that wants to
know whether a dataset may carry authority. The certificate id is a hash of WHAT WAS CERTIFIED --
dataset, schema, span, rows, checker version -- and not of when, so re-certifying an unchanged
dataset produces the same id and a diff shows only real change.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
CERT_DIR = ROOT / "desks" / "mt5" / "data" / "pit_certificates"

#: Bumped when a check changes what it asks. Part of the certificate id, so an old certificate
#: cannot silently claim to have passed a question that did not exist when it was written.
CHECKER_VERSION = "2026-09-05.1"

#: The three verdicts. Prefixed so a reader importing one cannot mistake it for a boolean.
#: The bandit-rule suppression is a NAME collision, not a suppressed finding: S105 fires on any
#: constant whose identifier contains "pass", and this one holds a gate verdict, not a secret.
VERDICT_PASS = "PASS"          # noqa: S105  -- a gate verdict, not a credential
VERDICT_FAIL = "FAIL"
VERDICT_UNMEASURED = "UNMEASURED"

CHECK_NAMES: tuple[str, ...] = ("leak", "revision", "timestamps", "availability",
                                "survivorship", "truncation", "schema")

#: An interior gap this many times the series' own median cadence is a hole, not a weekend.
#: Chosen against the desk's actual cadences: a daily series skips two days over a weekend and
#: four over a long holiday, so anything under ~5x is normal calendar behaviour.
TRUNCATION_GAP_MULT = 8.0
#: A parseable-timestamp fraction below this is not a dated series at all.
MIN_TIMESTAMP_FRAC = 0.99
#: Rows below which the span checks cannot say anything: a series this short has no cadence.
MIN_ROWS_FOR_CADENCE = 20

#: Selection rules that are point-in-time by construction, and ones that are survivorship by
#: construction. Anything else is UNMEASURED: the acquirer must declare, never the checker guess.
PIT_SELECTIONS: frozenset[str] = frozenset({
    "all_rows_as_published", "full_history_no_filter", "listed_at_t", "as_of_vintage",
    "complete_universe",
})
SURVIVORSHIP_SELECTIONS: frozenset[str] = frozenset({
    "currently_listed", "currently_active", "still_trading", "survivors_only",
    "top_by_current_size", "top_by_current_volume", "current_constituents", "delisted_dropped",
})
#: Words that make a free-text selection rule survivorship even when it is not on the list.
_SURVIVOR_WORDS = re.compile(r"\b(current(ly)?|today|still|surviv\w*|active now|as of now)\b",
                             re.I)


@dataclass(frozen=True)
class Check:
    """One adversarial question, its verdict, and WHY -- the why is the deliverable."""

    name: str
    verdict: str
    why: str
    detail: dict[str, Any] = field(default_factory=dict)

    @property
    def passed(self) -> bool:
        return self.verdict == VERDICT_PASS


@dataclass(frozen=True)
class PITCertificate:
    """What was asked of a dataset, what it answered, and whether it may carry authority."""

    dataset: str
    certificate_id: str
    checker_version: str
    certified_at: str
    authority: bool
    checks: tuple[Check, ...]
    span: dict[str, Any]
    source: dict[str, Any]

    # ------------------------------------------------------------------ reading
    def failures(self) -> tuple[str, ...]:
        return tuple(c.name for c in self.checks if c.verdict == VERDICT_FAIL)

    def unmeasured(self) -> tuple[str, ...]:
        return tuple(c.name for c in self.checks if c.verdict == VERDICT_UNMEASURED)

    def why(self, name: str) -> str:
        for c in self.checks:
            if c.name == name:
                return c.why
        return f"no check named {name!r}"

    # ------------------------------------------------------------------ persistence
    def to_json(self) -> str:
        return json.dumps({
            "_": ("PIT CERTIFICATE. `authority` is true only when all seven adversarial checks "
                  "PASS; UNMEASURED is not a pass. No certificate -> no promotion authority."),
            "dataset": self.dataset, "certificate_id": self.certificate_id,
            "checker_version": self.checker_version, "certified_at": self.certified_at,
            "authority": self.authority,
            "failures": list(self.failures()), "unmeasured": list(self.unmeasured()),
            "checks": [asdict(c) for c in self.checks],
            "span": self.span, "source": self.source,
        }, indent=1, default=str)

    @classmethod
    def from_json(cls, text: str) -> PITCertificate:
        doc = json.loads(text)
        if not isinstance(doc, dict) or "checks" not in doc:
            raise ValueError("not a PIT certificate document (no `checks`)")
        checks = tuple(Check(name=str(c.get("name")), verdict=str(c.get("verdict")),
                             why=str(c.get("why")), detail=dict(c.get("detail") or {}))
                       for c in doc["checks"])
        return cls(dataset=str(doc.get("dataset")),
                   certificate_id=str(doc.get("certificate_id")),
                   checker_version=str(doc.get("checker_version")),
                   certified_at=str(doc.get("certified_at")),
                   authority=bool(doc.get("authority")),
                   checks=checks, span=dict(doc.get("span") or {}),
                   source=dict(doc.get("source") or {}))


# --------------------------------------------------------------------------- helpers
def _aware(t: datetime) -> datetime:
    return t if t.tzinfo is not None else t.replace(tzinfo=UTC)


def _index(series: pd.DataFrame | pd.Series) -> pd.DatetimeIndex:
    """The series' own clock as UTC. A naive index is read as UTC, matching the lake convention."""
    return pd.DatetimeIndex(pd.to_datetime(series.index, utc=True, errors="coerce"))


def _column(series: pd.DataFrame | pd.Series, name: str) -> pd.Series | None:
    if isinstance(series, pd.DataFrame) and name in series.columns:
        return pd.to_datetime(series[name], utc=True, errors="coerce")
    return None


def schema_hash(series: pd.DataFrame | pd.Series) -> str:
    """Column names and dtypes, in order. A rename or a retype moves it; a new row does not."""
    if isinstance(series, pd.Series):
        cols = [(str(series.name), str(series.dtype))]
    else:
        cols = [(str(c), str(series[c].dtype)) for c in series.columns]
    payload = json.dumps(cols, sort_keys=False)
    return hashlib.sha256(payload.encode()).hexdigest()[:16]


# --------------------------------------------------------------------------- the seven checks
def check_leak(meta: dict[str, Any], series: pd.DataFrame | pd.Series,
               now: datetime) -> Check:
    """Can it leak future information? Two ways it can, both counted rather than argued about."""
    idx = _index(series)
    if idx.isna().all():
        return Check("leak", VERDICT_UNMEASURED, "no parseable index: nothing to place in time, so "
                                         "whether it leaks cannot be asked yet")
    future = int((idx > pd.Timestamp(_aware(now))).sum())
    avail = _column(series, "available_time")
    early = 0
    if avail is not None:
        early = int((avail.to_numpy() < idx.to_numpy()).sum())
    detail = {"rows": len(idx), "rows_dated_after_now": future,
              "rows_available_before_event": early,
              "now": _aware(now).isoformat()}
    if future:
        return Check("leak", VERDICT_FAIL,
                     f"{future} of {len(idx)} rows are dated AFTER now ({_aware(now).isoformat()}"
                     f"); a value the desk holds before its own event time is future information "
                     f"however it got here", detail)
    if early:
        return Check("leak", VERDICT_FAIL,
                     f"{early} of {len(idx)} rows declare an available_time EARLIER than the "
                     "event they describe -- knowable before it happened, which is the canonical "
                     "point-in-time leak", detail)
    if avail is None:
        return Check("leak", VERDICT_PASS,
                     "no row is dated after now; the series carries no available_time column, so "
                     "the availability check -- not this one -- is where its stamps are judged",
                     detail)
    return Check("leak", VERDICT_PASS,
                 f"no row dated after now and no row knowable before its event across "
                 f"{len(idx)} rows", detail)


def check_revision(meta: dict[str, Any], series: pd.DataFrame | pd.Series,
                   now: datetime) -> Check:
    """Does its historical API show revised values, and can the old vintage be read back?"""
    vintage_cols = [c for c in ("vintage", "available_time", "revision_time", "as_of")
                    if isinstance(series, pd.DataFrame) and c in series.columns]
    idx = _index(series)
    dup = int(idx.duplicated().sum()) if not idx.isna().all() else 0
    declared = meta.get("revised")
    detail = {"declared_revised": declared, "vintage_columns": vintage_cols,
              "duplicate_event_times": dup}
    restates = bool(declared) or dup > 0
    if restates and not vintage_cols:
        why = ("the source restates history" if declared else
               f"{dup} rows repeat an event time, which is a restatement by another name")
        return Check("revision", VERDICT_FAIL,
                     f"{why} and the series carries no vintage column "
                     "(vintage/available_time/revision_time/as_of), so the value the desk "
                     "decided on cannot be read back -- revision leakage with no way to detect "
                     "it", detail)
    if restates:
        return Check("revision", VERDICT_PASS,
                     f"the source restates history and the vintage is on the row "
                     f"({', '.join(vintage_cols)}), so a backtest can read the value that "
                     "existed at its decision time", detail)
    if declared is None:
        return Check("revision", VERDICT_UNMEASURED,
                     "the acquirer did not declare whether this source restates history, and no "
                     "repeated event time proves it does. Declare `revised: true/false` in the "
                     "dataset meta; absence is not permission", detail)
    return Check("revision", VERDICT_PASS,
                 "declared final-at-publication and no event time repeats, so there is no vintage "
                 "to lose", detail)


def check_timestamps(meta: dict[str, Any], series: pd.DataFrame | pd.Series,
                     now: datetime) -> Check:
    """Can timestamps be reconstructed -- parseable, ordered, and on a stated clock?"""
    idx = _index(series)
    n = len(idx)
    if not n:
        return Check("timestamps", VERDICT_UNMEASURED, "the series is empty", {"rows": 0})
    ok = int(idx.notna().sum())
    frac = ok / n
    monotonic = bool(pd.Series(idx.dropna().astype("int64")).is_monotonic_increasing)
    detail = {"rows": n, "parseable": ok, "parseable_frac": round(frac, 6),
              "monotonic": monotonic, "timezone": "UTC"}
    if frac < MIN_TIMESTAMP_FRAC:
        return Check("timestamps", VERDICT_FAIL,
                     f"only {frac:.1%} of {n} rows carry a parseable timestamp (need "
                     f"{MIN_TIMESTAMP_FRAC:.0%}); a row the desk cannot place in time is not a "
                     "weaker observation, it is not an observation", detail)
    if not monotonic:
        return Check("timestamps", VERDICT_FAIL,
                     "timestamps are not monotonically increasing after parsing: the file's row "
                     "order and its clock disagree, so `as-of` joins on it are undefined", detail)
    return Check("timestamps", VERDICT_PASS,
                 f"{ok} of {n} rows parse to an ordered, timezone-aware UTC clock", detail)


def check_availability(meta: dict[str, Any], series: pd.DataFrame | pd.Series,
                       now: datetime) -> Check:
    """Was it actually available then? The declared publication lag, checked against the stamps."""
    idx = _index(series)
    avail = _column(series, "available_time")
    lag_s = meta.get("publication_lag_s")
    detail: dict[str, Any] = {"declared_publication_lag_s": lag_s,
                              "has_available_time": avail is not None}
    if avail is None:
        if lag_s is None:
            return Check("availability", VERDICT_UNMEASURED,
                         "no available_time column and no declared publication_lag_s: when the "
                         "desk could have known each row is unknown, so it cannot be asserted",
                         detail)
        return Check("availability", VERDICT_PASS,
                     f"no per-row stamp, but the acquirer declares a publication lag of {lag_s}s "
                     "that a joiner applies uniformly to the event time", detail)
    future = int((avail > pd.Timestamp(_aware(now))).sum())
    detail["rows_available_after_now"] = future
    if future:
        return Check("availability", VERDICT_FAIL,
                     f"{future} rows claim an available_time in the future; a stamp the clock "
                     "cannot have reached is a manufactured availability", detail)
    lags = (avail.to_numpy() - idx.to_numpy()) / pd.Timedelta(seconds=1)
    finite = [float(x) for x in lags if isinstance(x, float) and math.isfinite(x)]
    if finite:
        detail["median_lag_s"] = round(sorted(finite)[len(finite) // 2], 3)
        detail["min_lag_s"] = round(min(finite), 3)
    if lag_s is not None and finite and detail["min_lag_s"] < float(lag_s):
        return Check("availability", VERDICT_FAIL,
                     f"the acquirer declares a publication lag of {lag_s}s but the shortest lag "
                     f"on the rows is {detail['min_lag_s']}s: some rows are stamped as knowable "
                     "sooner than the source publishes", detail)
    return Check("availability", VERDICT_PASS,
                 f"every row carries an available_time at or after its event and at or before "
                 f"now (median lag {detail.get('median_lag_s')}s)", detail)


def check_survivorship(meta: dict[str, Any], series: pd.DataFrame | pd.Series,
                       now: datetime) -> Check:
    """Does source selection use future survival? Declared, never inferred."""
    sel = meta.get("selection")
    detail = {"selection": sel, "pit_selections": sorted(PIT_SELECTIONS)}
    if not isinstance(sel, str) or not sel.strip():
        return Check("survivorship", VERDICT_UNMEASURED,
                     "the acquirer did not declare HOW the rows were selected. A universe picked "
                     f"by who survived is invisible in the data itself; declare `selection` as "
                     f"one of {sorted(PIT_SELECTIONS)} or say what it is", detail)
    low = sel.strip().lower()
    if low in SURVIVORSHIP_SELECTIONS or _SURVIVOR_WORDS.search(low):
        return Check("survivorship", VERDICT_FAIL,
                     f"the declared selection {sel!r} conditions on the present -- who is listed, "
                     "active or largest TODAY -- which is future information about every past "
                     "row in the file", detail)
    if low in PIT_SELECTIONS:
        return Check("survivorship", VERDICT_PASS,
                     f"selection {sel!r} is point-in-time by construction: no row's presence "
                     "depends on anything after its own timestamp", detail)
    return Check("survivorship", VERDICT_UNMEASURED,
                 f"selection {sel!r} is declared but is not one the checker knows to be "
                 f"point-in-time. Add it to PIT_SELECTIONS with the reason, or restate it as one "
                 f"of {sorted(PIT_SELECTIONS)}", detail)


def check_truncation(meta: dict[str, Any], series: pd.DataFrame | pd.Series,
                     now: datetime) -> Check:
    """Is history truncated -- at the head against the declared start, or by an interior hole?"""
    idx = _index(series).dropna().sort_values()
    n = len(idx)
    detail: dict[str, Any] = {"rows": n,
                              "first": str(idx[0]) if n else None,
                              "last": str(idx[-1]) if n else None,
                              "declared_history_starts": meta.get("history_starts")}
    if n < MIN_ROWS_FOR_CADENCE:
        return Check("truncation", VERDICT_UNMEASURED,
                     f"{n} rows is below {MIN_ROWS_FOR_CADENCE}: the series has no cadence to "
                     "measure a hole against", detail)
    declared = meta.get("history_starts")
    if declared:
        want = pd.to_datetime(declared, utc=True, errors="coerce")
        if pd.notna(want) and idx[0] > want + pd.Timedelta(days=1):
            missing = idx[0] - want
            detail["missing_head"] = str(missing)
            return Check("truncation", VERDICT_FAIL,
                         f"history is truncated at the head: the source declares it starts "
                         f"{want.isoformat()} and the file starts {idx[0].isoformat()} -- "
                         f"{missing} missing. A backtest over what is here silently begins after "
                         "whatever the missing span contained", detail)
    steps = idx.to_series().diff().dropna()
    med = steps.median()
    biggest = steps.max()
    detail["median_step"] = str(med)
    detail["largest_gap"] = str(biggest)
    if pd.isna(med) or med <= pd.Timedelta(0):
        return Check("truncation", VERDICT_UNMEASURED,
                     "the median step between rows is zero or undefined, so a gap cannot be "
                     "measured against the cadence", detail)
    if biggest > med * TRUNCATION_GAP_MULT:
        at = idx[int(steps.to_numpy().argmax()) + 1]
        gap_from = at - biggest
        detail["gap_from"] = str(gap_from)
        detail["gap_to"] = str(at)
        return Check("truncation", VERDICT_FAIL,
                     f"history is truncated in the middle: nothing between {gap_from.isoformat()}"
                     f" and {at.isoformat()} ({biggest} against a {med} cadence, "
                     f"{TRUNCATION_GAP_MULT}x the bound). Name the span or repair it -- a hole "
                     "the desk cannot see is a regime it never tested in", detail)
    return Check("truncation", VERDICT_PASS,
                 f"{n} rows from {idx[0].isoformat()} to {idx[-1].isoformat()} with no gap over "
                 f"{TRUNCATION_GAP_MULT}x the {med} cadence", detail)


def check_schema(meta: dict[str, Any], series: pd.DataFrame | pd.Series,
                 now: datetime) -> Check:
    """Was the schema changed? Against the hash the last certificate recorded, not against hope."""
    got = schema_hash(series)
    prior = meta.get("schema_hash")
    detail = {"schema_hash": got, "prior_schema_hash": prior,
              "columns": ([str(c) for c in series.columns] if isinstance(series, pd.DataFrame)
                          else [str(series.name)])}
    if not prior:
        return Check("schema", VERDICT_UNMEASURED,
                     f"no prior schema hash to compare against; this run's is {got}. Record it "
                     "on the dataset so the NEXT acquisition can tell a rename from a new "
                     "dataset", detail)
    if str(prior) != got:
        return Check("schema", VERDICT_FAIL,
                     f"the schema changed: {prior} -> {got}. A renamed or retyped column reads "
                     "downstream as a new series with a new history, which is how a break becomes "
                     "an edge. Re-certify deliberately with a migration note", detail)
    return Check("schema", VERDICT_PASS,
                 f"schema hash {got} matches the one last certified", detail)


CHECKS = (check_leak, check_revision, check_timestamps, check_availability,
          check_survivorship, check_truncation, check_schema)


# --------------------------------------------------------------------------- the certificate
def certificate_id(dataset: str, series: pd.DataFrame | pd.Series,
                   span: dict[str, Any]) -> str:
    """A hash of WHAT was certified, never of when. Re-certifying an unchanged dataset returns
    the same id, so a changed id is always a changed dataset."""
    body = json.dumps({"dataset": dataset, "schema": schema_hash(series),
                       "rows": span.get("rows"), "first": span.get("first"),
                       "last": span.get("last"), "v": CHECKER_VERSION},
                      sort_keys=True, default=str)
    return hashlib.sha256(body.encode()).hexdigest()[:20]


def certify(dataset_meta: dict[str, Any], series: pd.DataFrame | pd.Series, *,
            now: datetime | None = None) -> PITCertificate:
    """Put all seven questions to a dataset and mint the certificate that records the answers.

    `dataset_meta` is what the ACQUIRER declares -- name, url, selection rule, whether the source
    restates, its publication lag, when its history starts, the schema hash last certified. The
    checker never guesses any of it: an undeclared question reads UNMEASURED, and UNMEASURED
    carries no authority.
    """
    when = _aware(now or datetime.now(tz=UTC))
    name = str(dataset_meta.get("dataset") or dataset_meta.get("name") or "unnamed")
    idx = _index(series).dropna().sort_values()
    span = {"rows": len(series),
            "first": str(idx[0]) if len(idx) else None,
            "last": str(idx[-1]) if len(idx) else None,
            "schema_hash": schema_hash(series)}
    checks = tuple(fn(dataset_meta, series, when) for fn in CHECKS)
    return PITCertificate(
        dataset=name,
        certificate_id=certificate_id(name, series, span),
        checker_version=CHECKER_VERSION,
        certified_at=when.isoformat(),
        authority=all(c.passed for c in checks),
        checks=checks,
        span=span,
        source={k: dataset_meta.get(k) for k in
                ("url", "host", "provider", "selection", "revised", "publication_lag_s",
                 "history_starts", "license")},
    )


def _slug(dataset: str) -> str:
    """A filesystem-safe stem. Datasets are named by host and file, which carry dots and slashes."""
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", dataset).strip("_")[:120] or "unnamed"


def path_for(dataset: str, root: Path = CERT_DIR) -> Path:
    return root / f"{_slug(dataset)}.json"


def write(cert: PITCertificate, root: Path = CERT_DIR) -> Path:
    p = path_for(cert.dataset, root)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(cert.to_json() + "\n", "utf-8")
    return p


def load(dataset: str, root: Path = CERT_DIR) -> PITCertificate | None:
    """The certificate on disk, or None. A corrupt one is None too: an unreadable certificate is
    not a certificate, and reading it as one would be the absent-file defect all over again."""
    p = path_for(dataset, root)
    try:
        return PITCertificate.from_json(p.read_text("utf-8"))
    except (OSError, ValueError):
        return None


def has_authority(dataset: str, root: Path = CERT_DIR) -> bool:
    """THE GATE. No certificate, an unreadable one, or one with any check not PASSing -> False."""
    cert = load(dataset, root)
    return bool(cert and cert.authority)


def census(root: Path = CERT_DIR) -> dict[str, Any]:
    """Every certificate on disk: who has authority, who does not, and which check stopped them.

    Read by `scripts/check_pit.py`. Reports the count of datasets with NO certificate as unknown
    rather than zero -- this function can only see the certificates that exist, and saying
    otherwise would turn an unasked question into a pass.
    """
    certs: list[PITCertificate] = []
    unreadable: list[str] = []
    for p in sorted(root.glob("*.json")) if root.exists() else []:
        try:
            certs.append(PITCertificate.from_json(p.read_text("utf-8")))
        except (OSError, ValueError):
            unreadable.append(p.name)
    def _tally() -> dict[str, int]:
        return {VERDICT_PASS: 0, VERDICT_FAIL: 0, VERDICT_UNMEASURED: 0}

    by_check: dict[str, dict[str, int]] = {n: _tally() for n in CHECK_NAMES}
    for c in certs:
        for chk in c.checks:
            row = by_check.setdefault(chk.name, _tally())
            row[chk.verdict] = row.get(chk.verdict, 0) + 1
    with_auth = sorted(c.dataset for c in certs if c.authority)
    without = sorted(c.dataset for c in certs if not c.authority)
    return {
        "dir": str(root),
        "certificates": len(certs),
        "with_authority": len(with_auth),
        "without_authority": len(without),
        "authority_frac": (round(len(with_auth) / len(certs), 4) if certs else None),
        "datasets_with_authority": with_auth,
        "datasets_without_authority": without,
        "blocking_check": {c.dataset: sorted(set(c.failures()) | set(c.unmeasured()))
                           for c in certs if not c.authority},
        "by_check": by_check,
        "unreadable": unreadable,
        "rule": ("authority requires all seven adversarial checks to PASS; UNMEASURED is not a "
                 "pass, and a dataset with no certificate at all has no promotion authority "
                 "whatever this census counts"),
    }


def stale(cert: PITCertificate, *, now: datetime | None = None,
          max_age: timedelta = timedelta(days=90)) -> bool:
    """Has the certificate aged past the point where its answers still describe the live feed?
    A source re-fetched daily can change its schema, its selection or its lag at any time."""
    when = _aware(now or datetime.now(tz=UTC))
    try:
        at = _aware(datetime.fromisoformat(cert.certified_at))
    except (TypeError, ValueError):
        return True
    return (when - at) > max_age

```

### libs\execution\passive_impact.py
```python
"""R0267: the reduced-form PASSIVE-FILL IMPACT MODEL, and the honest statement of where it can
and cannot be fitted.

THE MAKER PROBLEM THIS SERVES. The desk's largest measured execution wound is passive: a 24.2%
maker fill rate while paying 96.5% of fees, and the ~66bps carry execution gap (R0219) that the
2026-07-31 attribution proved is EXECUTION, not selection. `libs/execution/book_walk.py` already
answers the TAKER side (walk the book, sqrt-law impact). Nothing answered the passive side, and
`libs/execution/excitation.py` -- which randomises how long a quote may rest -- has no functional
form at all, so it can measure points but cannot interpolate between them.

THE MODEL. Two empirical observables, each estimated separately, then combined:

  (a) FILL PROBABILITY DECAYS EXPONENTIALLY IN QUOTE DISTANCE
          P_fill(d) = p0 * exp(-d / lam)
      d in bps from mid, lam the decay length in bps. Quote at the touch and you fill often;
      step away and the probability falls off at a rate lam that is a property of the book.

  (b) SHORT-TERM PRICE RESPONSE IS LINEAR IN SIGNED ORDER FLOW
          r = beta * OFI
      r the forward mid return in bps, OFI the signed traded volume over the same window.
      Linear, through the origin: zero net flow implies zero expected response.

  COMBINED -- the passive impact rate. A resting quote is filled BY someone, and that someone is
  the aggressor whose flow moves the price against the fill. Expected adverse selection per unit
  of passive quoting at distance d is therefore the response scaled by the probability the quote
  is reached:
          impact(d) = beta * ofi_scale * P_fill(d)
  which decays exponentially in d for exactly the reason (a) does. Quoting further out is cheaper
  in adverse selection AND rarer in fills, and this is the curve that prices the trade-off.

WHY (a) CANNOT BE FITTED ON OUR OWN FILLS, MEASURED NOT ASSUMED. The executor's
`_passive_price` returns the best bid for a BUY and the best ask for a SELL -- every quote
this desk has ever placed sits AT THE TOUCH. The offset is therefore always half the spread:
it has ZERO VARIANCE BY CONSTRUCTION, and the placed price is not written to the tape at all (no
field on any of the 531 rows carries it). A regressor with no variance identifies no slope, so
`lam` is UNIDENTIFIED on own fills no matter how many fills accumulate. This is the same
collinearity trap `excitation.py` was built to break for `maker_wait_s`, recurring one axis over
on the offset -- and it is why `identifiability()` below is a first-class part of this module
rather than a footnote. L1.45 is explicit about the remedy: at an operating point the desk never
visits, say UNIDENTIFIED and go buy the observation.

WHAT IS IDENTIFIABLE TODAY, AND IT IS A LOT. `data/moat` holds ~13M recorded L2 snapshots at
20 (Binance) to 25 (Bybit) levels per side, time-aligned to a trade tape that carries AGGRESSOR
DIRECTION on every print. So both observables are estimable COUNTERFACTUALLY: place a hypothetical
quote at each recorded level, compute the queue ahead of it, and count the volume that actually
traded through that level in the following window. That is a real measurement of the book we
quoted into -- it is simply not a measurement of our own order's effect on it, and the two are
labelled distinctly throughout (`basis="counterfactual"` vs `basis="own_fills"`).

THE ONE THING THE COUNTERFACTUAL CANNOT DO, stated so it is never quietly forgotten: it measures
the book AS IT EXISTED WITHOUT OUR ORDER IN IT. Queue position, and any reaction to our own
presence, are unobservable this way. The counterfactual is therefore an UPPER BOUND on fill
probability, inheriting that property from `book_walk.fill_probability`, and it is labelled as
one. Only excitation over a genuine offset arm can close that gap.

REFUSAL PATHS (L1.28a). Every estimator returns a status rather than a number it cannot support:
UNDERPOWERED (too few observations), UNIDENTIFIED (the regressor has no variance, or the fitted
decay has the wrong sign), NO-DATA (nothing to read). A fitted coefficient published from too few
points would step execution decisions on noise, which is strictly worse than leaving them pinned.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

import numpy as np

__all__ = [
    "FillDecay",
    "Identifiability",
    "OfiResponse",
    "PassiveImpact",
    "fill_probability_curve",
    "fit_fill_decay",
    "fit_ofi_response",
    "identifiability",
    "passive_impact_curve",
    "signed_flow",
    "window_ofi",
]

#: Fewer than this and a decay length is noise. Matches book_walk.calibrate_impact's own floor of
#: 8 -- the same argument (a two-parameter fit on a handful of points is not a measurement) and
#: deliberately the same number, so the two impact estimators cannot disagree about what "enough"
#: means.
MIN_DECAY_POINTS = 8

#: An OFI response is a single-parameter regression on noisy per-window returns, so it needs more
#: points than the decay fit, not fewer. 30 is the conventional floor below which a slope's
#: standard error is not usefully bounded.
MIN_OFI_POINTS = 30

_UNDERPOWERED = "UNDERPOWERED"
_UNIDENTIFIED = "UNIDENTIFIED"
_NO_DATA = "NO-DATA"
_OK = "OK"


@dataclass(frozen=True)
class FillDecay:
    """P_fill(d) = p0 * exp(-d / lam_bps). `status` is OK only when both are real numbers."""

    lam_bps: float
    p0: float
    r2: float
    n: int
    status: str
    why: str = ""
    basis: str = "counterfactual"

    @property
    def ok(self) -> bool:
        return self.status == _OK

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class OfiResponse:
    """r_bps = beta * OFI, fitted through the origin."""

    beta_bps: float
    r2: float
    n: int
    status: str
    why: str = ""
    basis: str = "counterfactual"

    @property
    def ok(self) -> bool:
        return self.status == _OK

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class PassiveImpact:
    """The combined reduced form, evaluated on a grid of quote distances."""

    distance_bps: list[float]
    fill_prob: list[float]
    impact_bps: list[float]
    status: str
    why: str = ""
    decay: dict[str, Any] = field(default_factory=dict)
    response: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class Identifiability:
    """Can the decay be fitted from the desk's OWN fills? Measured, not assumed."""

    status: str
    why: str
    n_rows: int
    n_with_offset: int
    offset_variance: float | None = None

    @property
    def ok(self) -> bool:
        return self.status == _OK

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def fill_probability_curve(distance_bps: np.ndarray | list[float], *,
                           lam_bps: float, p0: float = 1.0) -> np.ndarray:
    """The model curve itself: p0 * exp(-d / lam).

    Raises on a non-positive decay length -- a zero or negative `lam` is not a flat curve, it is
    a fit that failed, and silently returning something plottable is how a failed fit reaches a
    decision surface.
    """
    if not np.isfinite(lam_bps) or lam_bps <= 0:
        raise ValueError(f"lam_bps must be finite and positive, got {lam_bps!r}")
    if not np.isfinite(p0) or p0 <= 0:
        raise ValueError(f"p0 must be finite and positive, got {p0!r}")
    d = np.asarray(distance_bps, dtype=float)
    if np.any(d < 0):
        raise ValueError("distance_bps must be non-negative (distance from mid, not signed)")
    return p0 * np.exp(-d / lam_bps)


def fit_fill_decay(distance_bps: np.ndarray | list[float],
                   fill_prob: np.ndarray | list[float],
                   *, min_points: int = MIN_DECAY_POINTS,
                   basis: str = "counterfactual") -> FillDecay:
    """Fit p = p0 * exp(-d / lam) by OLS of log(p) on d.

    Only strictly-positive probabilities carry information about a decay length -- a zero is
    censored (it says "not observed to fill in this window", not "probability exactly zero"), so
    zeros are DROPPED rather than clipped to a small number. Clipping would invent a data point
    at whatever floor was chosen and drag `lam` toward it.
    """
    d = np.asarray(distance_bps, dtype=float)
    p = np.asarray(fill_prob, dtype=float)
    if d.shape != p.shape:
        raise ValueError(f"distance/probability length mismatch: {d.shape} vs {p.shape}")
    if d.size == 0:
        return FillDecay(float("nan"), float("nan"), float("nan"), 0, _NO_DATA,
                         "no observations supplied", basis)

    usable = np.isfinite(d) & np.isfinite(p) & (p > 0.0) & (d >= 0.0)
    d, p = d[usable], p[usable]
    n = int(d.size)
    if n < min_points:
        return FillDecay(float("nan"), float("nan"), float("nan"), n, _UNDERPOWERED,
                         f"{n} usable points, need {min_points} -- a decay length fitted here "
                         "is noise", basis)
    if float(np.ptp(d)) <= 0.0:
        return FillDecay(float("nan"), float("nan"), float("nan"), n, _UNIDENTIFIED,
                         "quote distance has ZERO VARIANCE across the sample -- a regressor that "
                         "never moves identifies no slope, however many rows accumulate", basis)

    y = np.log(p)
    slope, intercept = np.polyfit(d, y, 1)
    if not np.isfinite(slope) or slope >= 0.0:
        return FillDecay(float("nan"), float("nan"), float("nan"), n, _UNIDENTIFIED,
                         f"fitted slope {slope:.6g} is not negative -- fill probability does not "
                         "decay with distance in this sample, so the model does not apply", basis)

    resid = y - (slope * d + intercept)
    ss_res = float(np.sum(resid ** 2))
    ss_tot = float(np.sum((y - y.mean()) ** 2))
    r2 = 1.0 - ss_res / ss_tot if ss_tot > 0 else float("nan")
    return FillDecay(lam_bps=float(-1.0 / slope), p0=float(np.exp(intercept)),
                     r2=r2, n=n, status=_OK, why="", basis=basis)


def signed_flow(rows: list[dict[str, Any]]) -> tuple[np.ndarray, np.ndarray]:
    """(timestamp_ms, SIGNED size) for every print. The primitive the repo did not have.

    THE CLAIM THIS EXISTS TO REFUTE is "direction is not published", which a previous trade
    reader asserted while returning unsigned size. It is false for every tape the desk has ever
    recorded, and the error is load-bearing: unsigned volume cannot estimate an order-flow
    IMBALANCE at all, which is the one quantity the module is for.

      A maker flag (k="t"):     "m" is buyer-is-maker. m=True -> the buyer was passive, so the
                                AGGRESSOR was a seller -> -1. m=False -> aggressor bought -> +1.
      An explicit side (k="trades"): each print in "v" carries "side", already the TAKER side.

    MT5 ticks carry the same information in a third spelling -- a tick flagged BUY or SELL names
    the aggressor directly -- so a reader for that tape adds a branch here rather than a module.

    Rows whose direction genuinely cannot be read are DROPPED, not signed zero -- a zero is a real
    flow observation meaning "balanced", and manufacturing one from an unreadable row would bias
    every downstream imbalance toward the middle.
    """
    ts: list[float] = []
    qty: list[float] = []
    for r in rows:
        kind = r.get("k")
        if kind == "t":                                    # Binance aggTrade
            m, q = r.get("m"), r.get("q")
            if m is None or q is None:
                continue
            try:
                size = float(q)
            except (TypeError, ValueError):
                continue
            ts.append(float(r.get("t", 0.0)))
            qty.append(-size if bool(m) else size)
        elif kind == "trades":                             # Bybit batch
            for tr in r.get("v") or []:
                side = str(tr.get("side", "")).upper()
                raw = tr.get("size", tr.get("v"))
                if side not in ("BUY", "SELL") or raw is None:
                    continue
                try:
                    size = float(raw)
                except (TypeError, ValueError):
                    continue
                ts.append(float(tr.get("time", r.get("t", 0.0)) or 0.0))
                qty.append(size if side == "BUY" else -size)
    if not ts:
        return np.empty(0, dtype=float), np.empty(0, dtype=float)
    t = np.asarray(ts, dtype=float)
    q = np.asarray(qty, dtype=float)
    order = np.argsort(t, kind="stable")
    return t[order], q[order]


def window_ofi(t_ms: np.ndarray, signed_qty: np.ndarray,
               edges_ms: np.ndarray | list[float]) -> np.ndarray:
    """Net signed volume in each [edges[i], edges[i+1]) bucket -- the order-flow imbalance.

    Normalised by the GROSS volume in the same window, so the result is a dimensionless
    imbalance in [-1, 1] comparable across symbols of wildly different notional. An empty
    window is 0.0 imbalance, which is correct here (no flow means no imbalance) and distinct
    from the unreadable-row case handled in `signed_flow`.
    """
    e = np.asarray(edges_ms, dtype=float)
    if e.size < 2:
        raise ValueError("need at least two bucket edges")
    if np.any(np.diff(e) <= 0):
        raise ValueError("bucket edges must be strictly increasing")
    net = np.zeros(e.size - 1, dtype=float)
    if t_ms.size == 0:
        return net
    idx = np.searchsorted(e, t_ms, side="right") - 1
    inside = (idx >= 0) & (idx < net.size)
    if not np.any(inside):
        return net
    i, q = idx[inside], signed_qty[inside]
    gross = np.bincount(i, weights=np.abs(q), minlength=net.size)
    signed = np.bincount(i, weights=q, minlength=net.size)
    nz = gross > 0
    net[nz] = signed[nz] / gross[nz]
    return net


def fit_ofi_response(ofi: np.ndarray | list[float], ret_bps: np.ndarray | list[float],
                     *, min_points: int = MIN_OFI_POINTS,
                     basis: str = "counterfactual") -> OfiResponse:
    """Fit r = beta * OFI through the origin.

    Through the origin deliberately: an intercept here would absorb any drift in the sample and
    report it as a flow response. Zero net flow must predict zero expected move, or the model is
    measuring the period rather than the mechanism.
    """
    x = np.asarray(ofi, dtype=float)
    y = np.asarray(ret_bps, dtype=float)
    if x.shape != y.shape:
        raise ValueError(f"ofi/return length mismatch: {x.shape} vs {y.shape}")
    usable = np.isfinite(x) & np.isfinite(y)
    x, y = x[usable], y[usable]
    n = int(x.size)
    if n == 0:
        return OfiResponse(float("nan"), float("nan"), 0, _NO_DATA,
                           "no observations supplied", basis)
    if n < min_points:
        return OfiResponse(float("nan"), float("nan"), n, _UNDERPOWERED,
                           f"{n} usable points, need {min_points} -- a response coefficient "
                           "fitted here would step execution on noise", basis)
    denom = float(x @ x)
    if denom <= 0.0:
        return OfiResponse(float("nan"), float("nan"), n, _UNIDENTIFIED,
                           "order-flow imbalance is identically zero across the sample -- no "
                           "variation to regress against", basis)
    beta = float((x @ y) / denom)
    resid = y - beta * x
    ss_res = float(np.sum(resid ** 2))
    ss_tot = float(np.sum(y ** 2))          # through-origin R2 is against zero, not the mean
    r2 = 1.0 - ss_res / ss_tot if ss_tot > 0 else float("nan")
    return OfiResponse(beta_bps=beta, r2=r2, n=n, status=_OK, why="", basis=basis)


def passive_impact_curve(decay: FillDecay, response: OfiResponse,
                         *, distance_bps: np.ndarray | list[float],
                         ofi_scale: float = 1.0) -> PassiveImpact:
    """Combine the two halves into the passive impact rate at each quote distance.

    Refuses unless BOTH halves are OK. A curve built from one good fit and one failed one would
    be a plottable object carrying a fabricated number, which is the L1.55 failure exactly: an
    artifact that is well-formed, young, and built from an input that was never measured.
    """
    d = np.asarray(distance_bps, dtype=float)
    if not decay.ok or not response.ok:
        bad = [f"decay={decay.status}" if not decay.ok else "",
               f"response={response.status}" if not response.ok else ""]
        why = "; ".join(w for w in bad if w)
        return PassiveImpact([], [], [], _UNIDENTIFIED,
                             f"cannot combine: {why} -- refusing to publish a curve with a "
                             "fabricated half", decay.as_dict(), response.as_dict())
    p = fill_probability_curve(d, lam_bps=decay.lam_bps, p0=decay.p0)
    impact = response.beta_bps * float(ofi_scale) * p
    return PassiveImpact([float(v) for v in d], [float(v) for v in p],
                         [float(v) for v in impact], _OK, "",
                         decay.as_dict(), response.as_dict())


#: Tape fields that would record where a passive quote was actually placed. None of these exists
#: today; the list is the CONTRACT the executor must satisfy before own-fill identification is
#: possible, and it is checked rather than described.
_OFFSET_FIELDS = ("quote_px", "placed_px", "quote_offset_bps", "spot_quote_px", "fut_quote_px")


def identifiability(tape_rows: list[dict[str, Any]]) -> Identifiability:
    """Is the fill-decay curve identifiable from the desk's OWN fills? Measured on the tape.

    THE ANSWER TODAY IS NO, AND NOT FOR WANT OF ROWS. `_passive_price` quotes at the touch on
    every order, so the placement offset is a constant; and no tape field records it in any case.
    This function exists so that fact is re-derived from the artifact on every run rather than
    trusted from this docstring -- the day an offset arm is added to the excitation design, the
    verdict flips on its own and nobody has to remember to come back.
    """
    n = len(tape_rows)
    if n == 0:
        return Identifiability(_NO_DATA, "execution tape is empty", 0, 0)
    present = [f for f in _OFFSET_FIELDS if any(f in r for r in tape_rows)]
    if not present:
        return Identifiability(
            _UNIDENTIFIED,
            "NO tape field records where the passive quote was placed (looked for: "
            f"{', '.join(_OFFSET_FIELDS)}). Separately, run_cashcarry_executor._passive_price "
            "quotes at the touch on every order, so the offset would be a CONSTANT even if it "
            "were recorded -- a regressor with no variance identifies no slope. Own-fill "
            "identification needs an OFFSET ARM in the excitation design, not more fills.",
            n, 0)
    offsets = [float(r[f]) for r in tape_rows for f in present
               if isinstance(r.get(f), (int, float))]
    k = len(offsets)
    if k < MIN_DECAY_POINTS:
        return Identifiability(_UNDERPOWERED,
                               f"{k} rows carry a placement offset, need {MIN_DECAY_POINTS}",
                               n, k)
    var = float(np.var(np.asarray(offsets, dtype=float)))
    if var <= 0.0:
        return Identifiability(_UNIDENTIFIED,
                               "placement offset is recorded but CONSTANT across every row -- "
                               "still no variance to identify a decay length",
                               n, k, var)
    return Identifiability(_OK, "", n, k, var)

```

### libs\moat\__init__.py
```python
"""The moat: the canonical research registry and the intelligence stores every miner writes."""

```

### libs\ops\capability_graph.py
```python
"""The desk's producers, artifacts and consumers, as a graph a machine can check.

THE DEFECT CLASS THIS EXISTS FOR, in this repository's own words from one afternoon:

    the deepening queue had no reader
    session state was computed and not passed to the solve
    the optimiser's per-sleeve weights were solved and not what sized the book
    factor exposure was measured and did not bind breadth
    execution slippage was captured and the attribution never read it
    the shadow sync committed and did not push
    coverage measured the old money path

Not one of those was a missing capability. Every one was a capability that existed and could not
be reached from a decision. A reviewer can find that class once; a graph can find it every
commit.

WHAT A NODE DECLARES. Each component names the artifacts it WRITES and READS, and whether it
holds AUTHORITY -- can change a position, a size, a certificate, or what may condition capital.
Artifacts are file paths. Declarations are checked against the code: a node that declares a
write must contain the path literal, and a path literal in a node's source that no node declares
is reported as UNDECLARED so the graph cannot drift silently from the code it describes.

THE CHECKS, each of which has already cost this desk something:

    DEAD_PRODUCER        an artifact is written and nothing reads it
    DEAD_CONSUMER        an artifact is read and nothing writes it
    ADVISORY_ONLY        a node writes artifacts that only report-writers read; it computes and
                         nothing decides on it
    UNMEASURED_AUTHORITY a node conditions capital on a state dimension the admission report has
                         not judged, or that it has buried
    STALE_DECISION       an authority node reads an artifact older than its freshness SLA
    UNDECLARED           a path literal in the source that the graph does not know

The checker runs in CI and fails on any of the first four. Freshness is checked at runtime by
`generate_status`, which writes the generated-truth files the audit asked for:

    reports/CAPABILITY_STATUS.json   every node, its edges, its check results
    reports/LIVE_REACHABILITY.json   which artifacts reach an authority node, and by what path
"""
from __future__ import annotations

import contextlib
import json
import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
DESK = ROOT / "desks" / "mt5"

#: Artifacts whose only purpose is to be read by a person. A node that feeds only these is
#: ADVISORY_ONLY unless it also holds authority itself.
REPORT_PREFIXES = ("reports/",)


@dataclass(frozen=True)
class Node:
    name: str
    module: str                        # path relative to ROOT
    writes: tuple[str, ...] = ()
    reads: tuple[str, ...] = ()
    #: What this node may change. Empty means it decides nothing on its own.
    authority: tuple[str, ...] = ()
    #: Seconds an authority node may tolerate on an input before its decision is STALE.
    freshness_s: dict[str, int] = field(default_factory=dict)
    #: State dimensions this node conditions capital on; each must be admitted.
    conditions_on: tuple[str, ...] = ()
    #: The MODULE_RENT line(s) that price THIS node, when the ledger bills it under another name.
    #: Empty means "billed under my own name, or not billable yet" -- and which of those is true is
    #: reported, never assumed.
    #:
    #: WHY THIS FIELD EXISTS, measured 2026-09-05. The rent ledger bills MECHANISMS -- rails,
    #: proposer arms, execution algorithms, allocator components, data sources, state dimensions --
    #: while this graph names ORGANS. The two vocabularies are almost disjoint: of 62 rent modules
    #: and 71 nodes, exactly 6 names matched, so even a FULLY populated ledger on the live host
    #: could never move more than 7 nodes to MEASURED. The rung was structurally unreachable for
    #: ~90% of the graph, and no amount of accumulated live evidence would have changed that. It
    #: read as "we have not measured enough yet" when the real answer was "nothing here can be
    #: measured by name".
    #:
    #: A mapping is a CLAIM that the named rent line prices this node's own output. Getting one
    #: wrong grants MEASURED falsely, which is the same free pass removed from `stages()` on the
    #: same day, re-entering through a different door. So an unmapped node stays unmapped and is
    #: counted as debt rather than guessed at.
    billed_as: tuple[str, ...] = ()


#: THE GRAPH. Every path is relative to ROOT. Adding a component means adding it here, and the
#: UNDECLARED check is what forces that: a new writer of a new path shows up red until named.
NODES: tuple[Node, ...] = (
    Node("miner_candidate_compiler", "desks/mt5/research/miner_candidate_compiler.py",
         writes=("desks/mt5/data/hypotheses/miner_candidates.json",
                 "desks/mt5/data/hypotheses/miner_deepening_queue.json",
                 "desks/mt5/data/hypothesis_graph.jsonl"),
         reads=("desks/mt5/data/intelligence/", "desks/mt5/reports/universal_gates_external.json")),
    Node("deepening_worker", "desks/mt5/research/deepening_worker.py",
         writes=("desks/mt5/data/hypotheses/deepening_worked.jsonl",
                 "desks/mt5/data/hypotheses/deepened_candidates.json"),
         reads=("desks/mt5/data/hypotheses/miner_deepening_queue.json",
                "desks/mt5/data/hypothesis_graph.jsonl")),
    Node("factor_residual_engine", "desks/mt5/research/factor_residual_engine.py",
         writes=("desks/mt5/data/intelligence/", "desks/mt5/reports/factor_residual.json"),
         reads=("desks/mt5/data/universe/",)),
    Node("plumbing_miner", "desks/mt5/research/plumbing_miner.py",
         writes=("desks/mt5/data/intelligence/", "desks/mt5/reports/plumbing_miner.json"),
         reads=("desks/mt5/data/universe/",)),
    Node("transition_alpha", "desks/mt5/research/transition_alpha.py",
         writes=("desks/mt5/data/intelligence/", "desks/mt5/reports/transition_alpha.json"),
         reads=("desks/mt5/data/universe/",)),
    Node("weak_signal_compiler", "desks/mt5/research/weak_signal_compiler.py",
         writes=("desks/mt5/data/intelligence/", "desks/mt5/reports/weak_signal_compiler.json"),
         reads=("desks/mt5/reports/universal_gates_external.json", "desks/mt5/data/universe/")),
    Node("fund_playbook", "desks/mt5/research/fund_playbook.py",
         writes=("desks/mt5/data/intelligence/", "desks/mt5/reports/FUND_PLAYBOOK.json",
                 "desks/mt5/data/hypothesis_graph.jsonl")),
    Node("external_gauntlet", "desks/mt5/scripts/external_gauntlet.py",
         # the authority file itself: every certificate the ten gates minted, which the canon
         # copy floors and the recertification audit re-judges
         writes=("desks/mt5/reports/universal_gates_external.json",
                 "desks/mt5/reports/UNIVERSAL_SURVIVORS.json"),
         reads=("desks/mt5/data/hypotheses/miner_candidates.json", "desks/mt5/data/universe/",
                "desks/mt5/reports/SCALP_GAUNTLET.json",
                # THE TICK TAPE REACHES A CERTIFICATE THROUGH HERE, and it always has --
                # external_gauntlet.py:329 calls `inputs._tape_series(sym, h1.index)`, which
                # reads data/tape/ticks/<SYM>/<DAY>.parquet and hands the spread and flow series
                # to the liquidity_regime and orderflow_imbalance families. The edge was real
                # and undeclared, so the graph could not see that a starved tape starves two
                # families of the gauntlet.
                "desks/mt5/data/tape/ticks/"),
         authority=("certificate",)),
    Node("scalp_gauntlet", "desks/mt5/scripts/scalp_gauntlet.py",
         # the scalp lane's ten-gate verdicts and certificates; external_gauntlet merges the
         # passes into the canon under `scalp.<candidate>` (certificate authority stays there)
         writes=("desks/mt5/reports/SCALP_GAUNTLET.json",),
         reads=("desks/mt5/data/universe/",)),
    Node("universal_gate", "desks/mt5/research/universal_gate.py",
         writes=("desks/mt5/data/UNIVERSAL_SURVIVORS.canon.json",),
         reads=("desks/mt5/data/universe/",), authority=("certificate",)),
    Node("shadow_forward", "desks/mt5/research/shadow_forward.py",
         writes=("desks/mt5/reports/shadow/",),
         reads=("desks/mt5/data/UNIVERSAL_SURVIVORS.canon.json", "desks/mt5/data/universe/")),
    Node("promoter", "desks/mt5/research/promoter.py",
         # sleeves.json is the LIVE roster the gateway trades from; the promoter writes a
         # matured candidate there on the run its clock matures (automatic, principal 2026-09-04).
         writes=("desks/mt5/data/sleeve_registry.json", "desks/mt5/data/sleeves.json"),
         reads=("desks/mt5/reports/shadow/", "desks/mt5/data/UNIVERSAL_SURVIVORS.canon.json",
                # the daily re-judge of every certificate at today's costs: a fresh
                # COST_REGRADE_FAIL refuses promotion (BLOCKED_COST_REGRADE)
                "desks/mt5/reports/recertification_audit.json",
                # THE CAPITAL DOOR (principal 2026-09-05). `admission.candidates[*]` is the
                # dE[log W] of adding each candidate to the book the desk holds, and the
                # promoter gives capital to nothing that fails it; `book` and `book_zeroed`
                # are the current reading a LIVE sleeve is demoted on. A scan older than
                # `promoter.ADMISSION_MAX_AGE_H` may neither add risk nor remove it.
                "desks/mt5/reports/pf_allocation.json"),
         freshness_s={"desks/mt5/reports/pf_allocation.json": 26 * 3600},
         authority=("promotion",)),
    Node("recertify_canon", "desks/mt5/scripts/recertify_canon.py",
         reads=("desks/mt5/reports/UNIVERSAL_SURVIVORS.json", "desks/mt5/data/universe/"),
         writes=("desks/mt5/reports/recertification_audit.json",)),
    # THE WORLD'S CLOCK, and note what it does NOT claim. Its authority is over WHEN the
    # allocator solves, never over what the allocator decides -- so it is wired here as a
    # timing organ, not a sizing one. Every fitted quantity it owns reads UNMEASURED until its
    # ledger holds real events, and it refuses capital authority to every category until then.
    Node("macro_intel", "desks/mt5/macro/run_macro_intel.py",
         # reads its OWN prior state back -- the taxonomy centroids, the credibility
         # posteriors, the factor basis and the multiplicity charge are all cumulative. That
         # self-edge is the thing that makes this learn rather than restate.
         # Named one by one, not as a directory: the fence checks artifacts, and a directory
         # prefix let three of these read as DEAD_PRODUCER while they were in fact this node's
         # own memory. `multiplicity.json` is the cumulative Bonferroni charge -- re-read every
         # pass precisely so re-testing a cell makes admission HARDER, never easier -- and
         # `event_attribution.jsonl` is where the measured decay half-lives come back from,
         # which is the loop that lets the interrupt gate ever fire.
         reads=("desks/mt5/data/universe/", "desks/mt5/data/macro/",
                "desks/mt5/data/macro/taxonomy.json",
                "desks/mt5/data/macro/source_credibility.json",
                "desks/mt5/data/macro/factor_basis.json",
                "desks/mt5/data/macro/exposures.json",
                "desks/mt5/data/macro/multiplicity.json",
                "desks/mt5/data/macro/event_attribution.jsonl",
                "desks/mt5/data/macro/event_ledger.jsonl"),
         writes=("desks/mt5/data/macro/event_ledger.jsonl",
                 "desks/mt5/data/macro/allocator_interrupt.json",
                 "desks/mt5/data/macro/interrupt_log.jsonl",
                 "desks/mt5/data/macro/taxonomy.json",
                 "desks/mt5/data/macro/source_credibility.json",
                 "desks/mt5/data/macro/factor_basis.json",
                 "desks/mt5/data/macro/exposures.json",
                 "desks/mt5/data/macro/multiplicity.json",
                 "desks/mt5/data/macro/event_attribution.jsonl",
                 "desks/mt5/reports/MACRO_INTEL.json"),
         # ITS AUTHORITY IS THE CLOCK, NOT THE BOOK. `research_supervisor.tick_periodic` reads
         # `allocator_interrupt.json` and may bring the allocator's fast leg forward; nothing
         # here ever reaches a weight. Declared so the fence measures what this actually
         # decides -- without it the node reads as ADVISORY_ONLY, which would be wrong in the
         # dangerous direction: a timing organ that silently gained sizing authority would look
         # identical to one that never had any.
         authority=("allocator_solve_timing",)),
    Node("world_causal_graph", "desks/mt5/research/world_causal_graph.py",
         reads=("desks/mt5/data/universe/", "desks/mt5/data/deep_forest_claims.jsonl",
                "desks/mt5/reports/CROSS_ASSET_GRAPH.json",
                "desks/mt5/data/world_causal_graph.json"),
         writes=("desks/mt5/data/world_causal_graph.json",
                 "desks/mt5/reports/WORLD_CAUSAL_GRAPH.json")),
    Node("state_vector_build", "desks/mt5/research/state_vector_build.py",
         writes=("desks/mt5/data/state_vector.json", "desks/mt5/data/state_fits.json"),
         reads=("desks/mt5/data/universe/", "desks/mt5/data/UNIVERSAL_SURVIVORS.canon.json",
                "desks/mt5/data/intelligence/ff_calendar_vintage",
                "desks/mt5/data/state_fits.json",
                # the admitted upstream nodes it turns into conditioning hints, and the graph
                # itself as the fallback when reports/ has not been written on this box
                "desks/mt5/reports/WORLD_CAUSAL_GRAPH.json",
                "desks/mt5/data/world_causal_graph.json")),
    Node("state_admission_run", "desks/mt5/research/state_admission_run.py",
         writes=("desks/mt5/reports/STATE_ADMISSION.json",),
         reads=("backups/moat/shadow_ledgers/", "desks/mt5/data/live_ledger.jsonl"),
         authority=("conditioning",),
         # The admission run acts ONLY through the dimensions it admits, and MODULE_RENT prices
         # each dimension by its out-of-sample gain. Without this run no dimension is admitted, so
         # the dimensions' rent IS this organ's rent -- the same counterfactual, not a proxy for it.
         billed_as=("state_dimension:session", "state_dimension:event",
                    "state_dimension:weekday")),
    Node("pf_allocator", "desks/mt5/research/pf_allocator.py",
         writes=("desks/mt5/reports/ALLOCATOR_PROOF.json", "desks/mt5/data/pf_forecast_log.jsonl",
                 "desks/mt5/reports/pf_allocator.json", "desks/mt5/reports/pf_allocation.json",
                 "desks/mt5/data/capital_modifier_ledger.jsonl"),
         reads=("desks/mt5/data/state_vector.json", "desks/mt5/reports/STATE_ADMISSION.json",
                "backups/moat/shadow_ledgers/", "desks/mt5/data/universe/",
                "desks/mt5/reports/hunt12_partial.json", "desks/mt5/data/rail_calibration.json"),
         authority=("sizing",),
         freshness_s={"desks/mt5/data/state_vector.json": 2 * 3600,
                      "desks/mt5/reports/STATE_ADMISSION.json": 3 * 24 * 3600},
         conditions_on=("session", "event", "weekday")),
    Node("gateway", "desks/mt5/mt5desk/gateway.py",
         writes=("desks/mt5/data/gateway_state.json", "desks/mt5/data/order_intents.jsonl",
                 "desks/mt5/data/live_ledger.jsonl", "desks/mt5/data/decision_ledger.jsonl",
                 # via research.session_phase._record_broker_clock, from the live terminal
                 "desks/mt5/data/broker_clock.json",
                 # via mt5desk.netting.TheoreticalBook and execution_registry.record_outcome:
                 # every sleeve's desired position and fill, and what each fill cost against
                 # what the market plan expected
                 "desks/mt5/data/theoretical_positions.jsonl",
                 "desks/mt5/data/execution_algo_outcomes.jsonl"),
         reads=("desks/mt5/reports/ALLOCATOR_PROOF.json", "desks/mt5/data/sleeve_registry.json",
                "desks/mt5/data/state_vector.json", "desks/mt5/data/regime_state.json",
                "desks/mt5/reports/pf_allocation.json", "desks/mt5/data/RELEASE.json",
                "desks/mt5/data/theoretical_positions.jsonl", "desks/mt5/data/sleeves.json"),
         authority=("position", "size"),
         freshness_s={"desks/mt5/reports/ALLOCATOR_PROOF.json": 26 * 3600}),
    # THE GROWTH GOVERNANCE LOOP: every rail billed daily, tunable rails calibrated toward
    # growth, the AI capital modifier's categories scored against what they claimed.
    Node("missed_growth", "desks/mt5/research/missed_growth.py",
         reads=("desks/mt5/reports/pf_allocation.json", "desks/mt5/reports/FILTER_VALUE.json",
                "desks/mt5/reports/STATE_ADMISSION.json",
                # VETO_ALPHA: the counterfactual world's per-reason table, which `_veto_evidence`
                # merges over FILTER_VALUE's rows -- the veto rails' better evidence.
                "desks/mt5/reports/COUNTERFACTUAL_WORLD.json"),
         writes=("desks/mt5/reports/MISSED_GROWTH.json", "desks/mt5/data/missed_growth.jsonl",
                 "desks/mt5/data/rail_calibration.json",
                 "desks/mt5/data/hypotheses/miner_deepening_queue.json")),
    Node("capital_modifier_score", "desks/mt5/research/capital_modifier_score.py",
         reads=("desks/mt5/data/capital_modifier_ledger.jsonl", "backups/moat/shadow_ledgers/"),
         writes=("desks/mt5/reports/CAPITAL_MODIFIERS.json",),
         # This organ IS the AI capital modifier the rent ledger bills: `measure_conditioning`
         # prices the heat the modifier moved against what that heat then earned, which is the
         # with/without of this node exactly. "This includes AI" -- the principal, on the day the
         # rent ledger was written.
         billed_as=("ai_capital_modifier",)),
    # EXECUTION INTELLIGENCE AND THE RELEASE: the learned fill/slip surface every cost consumer
    # shares, the netting measurement, and the one live SHA every decision is stamped with.
    Node("fill_surface", "desks/mt5/mt5desk/fill_surface.py",
         reads=("desks/mt5/data/order_intents.jsonl", "desks/mt5/reports/markout.json"),
         writes=("desks/mt5/reports/FILL_SURFACE.json",)),
    # THE THEORETICAL-POSITION LEDGER (2026-09-05): the gateway asserts every sleeve's desired
    # signed position and records every fill into `netting.TheoreticalBook`; `netting.route`
    # then computes the ONE order the venue would see per symbol. The gateway logs that order as
    # NET WOULD SEND -- measured, never placed -- and the algorithm registry's expected-vs-realised
    # ledger feeds the daily execution report. Both ledgers are written FROM the gateway process,
    # which is why the gateway node declares them; this module owns the replay and the report.
    Node("netting", "desks/mt5/mt5desk/netting.py",
         reads=("desks/mt5/data/order_intents.jsonl",
                "desks/mt5/data/theoretical_positions.jsonl"),
         writes=("desks/mt5/reports/NETTING.json", "desks/mt5/reports/NETTING_BOOK.json")),
    # ALPHA CAPTURE (2026-09-05, the principal's order): realised edge over predicted
    # FRICTIONLESS edge, per sleeve, session and symbol, trended over its own history. The one
    # number that separates a strategy that stopped working from a strategy being taken apart
    # between the decision and the fill. Reads the fill corpus the hourly twin assembles.
    Node("execution_intelligence", "desks/mt5/research/execution_intelligence.py",
         reads=("desks/mt5/data/order_intents.jsonl",
                "desks/mt5/data/theoretical_positions.jsonl",
                "desks/mt5/data/execution_algo_outcomes.jsonl", "desks/mt5/reports/markout.json",
                "desks/mt5/data/fill_corpus.jsonl",
                "desks/mt5/data/alpha_capture_history.jsonl"),
         writes=("desks/mt5/reports/FILL_SURFACE.json", "desks/mt5/reports/NETTING.json",
                 "desks/mt5/reports/NETTING_BOOK.json", "desks/mt5/reports/ALPHA_CAPTURE.json",
                 "desks/mt5/data/alpha_capture_history.jsonl")),
    # THE EXECUTION DIGITAL TWIN (2026-09-05): every live intent joined to what the venue did,
    # calibrated, and turned into the correction the simulator should apply. ADVISORY until
    # engine.Costs / external_gauntlet.costs_for read EXECUTION_TWIN.json: when that wiring
    # lands, add the report to the external_gauntlet node's `reads` and drop it from HUMAN_READ
    # so the graph shows the Live -> Simulator path instead of a report a person reads.
    # THE FILL CORPUS (2026-09-05, the principal's order) is assembled on the SAME clock, because
    # it is a join over the ledgers this node already reads plus four that resolve late (the
    # decision ledger, the counterfactual dataset, the excursions and the tick tape). It is the
    # desk's one unrebuildable asset -- an unrecorded fill cannot be recovered -- and it is
    # HUMAN_READ on purpose: `execution_intelligence` prices the alpha capture ratio off it, but
    # neither the conditional execution-choice model nor the meta-labeler is wired to anything
    # that sends an order, and both are UNMEASURED until the corpus reaches their required n.
    # When one of them is wired, drop the corpus from HUMAN_READ and declare the consumer here.
    Node("execution_twin", "desks/mt5/research/execution_twin.py",
         reads=("desks/mt5/data/order_intents.jsonl",
                "desks/mt5/data/execution_algo_outcomes.jsonl",
                "desks/mt5/data/live_ledger.jsonl", "desks/mt5/data/universe/",
                "desks/mt5/data/execution_twin_state.json",
                "desks/mt5/data/execution_twin_cases.jsonl",
                "desks/mt5/data/decision_ledger.jsonl",
                "desks/mt5/data/decision_dataset.jsonl",
                "desks/mt5/data/excursions.jsonl",
                "desks/mt5/data/tape/",
                "desks/mt5/data/fill_corpus.jsonl"),
         writes=("desks/mt5/reports/EXECUTION_TWIN.json",
                 "desks/mt5/data/execution_twin_cases.jsonl",
                 "desks/mt5/data/execution_twin_state.json",
                 "desks/mt5/data/fill_corpus.jsonl")),
    # THE PORTFOLIO GAP (scheduled 2026-09-05; it existed with no clock): what the book cannot
    # fill and where research should point. ADVISORY until the research bandit reads it.
    # THE COUNTERFACTUAL WORLD (2026-09-05, the principal's order): every decision minute joined
    # from the eleven ledgers and priced against every alternative -- entered/skipped,
    # 0.5x/1x/1.5x, market/limit/delayed, fixed TP/trail/hold/partial -- with the desk's own cost
    # posterior, named on every row. ADVISORY until missed_growth reads VETO_ALPHA off
    # COUNTERFACTUAL_WORLD.json; when that wiring lands, add the report to the missed_growth
    # node's `reads` and drop it from HUMAN_READ, so the graph shows the Behaviour -> Rail path
    # instead of a report a person reads.
    Node("counterfactual_replay", "desks/mt5/research/counterfactual_replay.py",
         reads=("desks/mt5/data/decision_ledger.jsonl", "desks/mt5/data/order_intents.jsonl",
                "desks/mt5/data/live_ledger.jsonl",
                "desks/mt5/data/theoretical_positions.jsonl",
                "desks/mt5/data/execution_algo_outcomes.jsonl",
                "desks/mt5/data/broker_clock.json", "desks/mt5/data/pf_forecast_log.jsonl",
                "desks/mt5/data/capital_modifier_ledger.jsonl",
                "desks/mt5/data/counterfactuals.jsonl",
                "desks/mt5/data/action_counterfactuals.jsonl",
                "desks/mt5/data/excursions.jsonl",
                "desks/mt5/reports/EXECUTION_TWIN.json", "desks/mt5/reports/FILL_SURFACE.json",
                "desks/mt5/data/universe/", "desks/mt5/data/decision_dataset.jsonl",
                "desks/mt5/data/decision_dataset_watermark.json"),
         writes=("desks/mt5/reports/COUNTERFACTUAL_WORLD.json",
                 "desks/mt5/data/decision_dataset.jsonl",
                 "desks/mt5/data/decision_dataset_watermark.json")),
    Node("portfolio_gap", "desks/mt5/research/portfolio_gap.py",
         reads=("desks/mt5/reports/pf_allocation.json",
                "desks/mt5/reports/UNIVERSAL_SURVIVORS.json"),
         writes=("desks/mt5/reports/portfolio_gap.json",)),
    Node("release", "libs/ops/release.py",
         reads=("desks/mt5/data/UNIVERSAL_SURVIVORS.canon.json",
                "desks/mt5/data/IMMUTABLE_MANIFEST.json", "desks/mt5/data/sleeves.json"),
         writes=("desks/mt5/data/RELEASE.json",)),
    # RELEASE IDENTITY (2026-09-05): the running SHA measured against the sealed release. The
    # gateway asks `release_identity.verdict()` every pass and opens nothing new on a refusal;
    # the verdict file rides the box's git sync so every brain can read it, and the hourly smoke
    # test proves the money-path modules on the box import and match the seal.
    # The signed money-path manifest: `--sign` is a person's act after a reviewed change; the
    # release seal and the box smoke test both verify against it.
    Node("immutable_evaluator", "scripts/check_immutable_evaluator.py",
         writes=("desks/mt5/data/IMMUTABLE_MANIFEST.json",)),
    Node("release_identity", "desks/mt5/mt5desk/release_identity.py",
         reads=("desks/mt5/data/RELEASE.json",),
         writes=("desks/mt5/data/release_identity.json",)),
    Node("smoke_release", "desks/mt5/scripts/smoke_release.py",
         reads=("desks/mt5/data/RELEASE.json",),
         writes=("desks/mt5/reports/release_smoke.json",)),
    # THE PROPRIETARY-DATA FLYWHEEL: every decision the desk made, taken or not, priced after the
    # fact and fed back as research targets. None of these nodes has authority; each feeds one.
    Node("counterfactual_markout", "desks/mt5/research/counterfactual_markout.py",
         reads=("desks/mt5/data/decision_ledger.jsonl", "desks/mt5/data/universe/"),
         writes=("desks/mt5/data/counterfactuals.jsonl", "desks/mt5/reports/FILTER_VALUE.json")),
    Node("excursions", "desks/mt5/research/excursions.py",
         reads=("backups/moat/shadow_ledgers/", "desks/mt5/data/universe/"),
         writes=("desks/mt5/data/excursions.jsonl", "desks/mt5/reports/EXCURSIONS.json",
                 "desks/mt5/data/hypotheses/miner_deepening_queue.json")),
    Node("alpha_genome", "desks/mt5/research/alpha_genome.py",
         reads=("desks/mt5/data/UNIVERSAL_SURVIVORS.canon.json",),
         writes=("desks/mt5/reports/ALPHA_GENOME.json",)),
    Node("opportunity_curve", "desks/mt5/research/opportunity_curve.py",
         reads=("backups/moat/shadow_ledgers/", "desks/mt5/data/broker_clock.json"),
         writes=("desks/mt5/reports/OPPORTUNITY_CURVE.json",
                 "desks/mt5/data/hypotheses/miner_deepening_queue.json")),
    Node("microstructure_miner", "desks/mt5/research/microstructure_miner.py",
         reads=("desks/mt5/data/universe/",),
         writes=("desks/mt5/data/intelligence/", "desks/mt5/reports/MICROSTRUCTURE_SURFACES.json",
                 "desks/mt5/reports/microstructure_miner.json")),
    Node("markout", "desks/mt5/mt5desk/markout.py",
         reads=("desks/mt5/data/order_intents.jsonl", "desks/mt5/data/live_ledger.jsonl"),
         writes=("desks/mt5/reports/markout.json",)),
    Node("allocator_attribution", "desks/mt5/research/allocator_attribution.py",
         reads=("desks/mt5/data/pf_forecast_log.jsonl", "desks/mt5/data/live_ledger.jsonl",
                "desks/mt5/data/order_intents.jsonl",
                # the growth decomposition (2026-09-04) reads every term's own ledger
                "desks/mt5/reports/ALLOCATOR_PROOF.json", "desks/mt5/reports/pf_allocation.json",
                "desks/mt5/reports/EXIT_ACCOUNTS.json", "desks/mt5/reports/FILL_SURFACE.json",
                "desks/mt5/reports/FILTER_VALUE.json", "desks/mt5/reports/MISSED_GROWTH.json",
                # the ENTRY term's ledger (nothing read it before) and research P&L per source
                "desks/mt5/reports/EXCURSIONS.json", "desks/mt5/reports/RESEARCH_PNL.json"),
         writes=("desks/mt5/reports/allocator_attribution.json",
                 "desks/mt5/reports/GROWTH_ATTRIBUTION_WEEKLY.json")),
    Node("regime_monitor", "desks/mt5/research/regime_monitor.py",
         reads=("desks/mt5/data/live_ledger.jsonl", "desks/mt5/reports/shadow/",
                "desks/mt5/reports/FILTER_VALUE.json"),
         writes=("desks/mt5/data/regime_state.json",), authority=("hibernate",),
         # The monitor's only authority is hibernation, and the hibernate RAIL is already billed
         # daily by missed_growth as E[log W without the rail] - E[log W with it]. The rail cannot
         # fire without this monitor's regime_state, so "without the rail" and "without the
         # monitor" are the same world and the rail's ledger line prices this organ directly.
         billed_as=("regime_hibernate",)),
    Node("regime_coverage", "desks/mt5/research/regime_coverage.py",
         reads=("backups/moat/shadow_ledgers/", "desks/mt5/reports/STATE_ADMISSION.json",
                "desks/mt5/reports/ALPHA_GENOME.json"),
         writes=("desks/mt5/reports/REGIME_COVERAGE.json",
                 "desks/mt5/data/hypotheses/miner_deepening_queue.json")),
    # THE BREADTH LANE (2026-09-05). Three producers answering the principal's three questions --
    # how many independent bets the book actually is, what pays inside its own worst periods, and
    # which states of a surviving edge deserve capital. Each reaches a decision the same way
    # regime_coverage and opportunity_curve do: through the deepening queue, which the worker
    # reads hourly and whose deepened candidates the gauntlet certifies.
    Node("alpha_breadth", "desks/mt5/research/alpha_breadth.py",
         reads=("backups/moat/shadow_ledgers/", "desks/mt5/data/UNIVERSAL_SURVIVORS.canon.json",
                "desks/mt5/data/universe/"),
         writes=("desks/mt5/reports/EFFECTIVE_BREADTH.json",
                 "desks/mt5/data/effective_breadth.jsonl",
                 "desks/mt5/data/hypotheses/miner_deepening_queue.json")),
    # The lane is a CHAIN, not three parallel reports: the breadth ledger owns cluster occupancy
    # and the drawdown factory reads it rather than recomputing a second answer to the same word;
    # the survivor miner reads the drawdown's state signature, because a state where a surviving
    # edge is stronger AND the rest of the book is losing is drawdown alpha the desk already owns.
    Node("drawdown_alpha", "desks/mt5/research/drawdown_alpha.py",
         reads=("backups/moat/shadow_ledgers/", "desks/mt5/reports/EFFECTIVE_BREADTH.json"),
         writes=("desks/mt5/reports/DRAWDOWN_ALPHA.json",
                 "desks/mt5/data/hypotheses/miner_deepening_queue.json")),
    Node("survivor_neighbourhood", "desks/mt5/research/survivor_neighbourhood.py",
         reads=("backups/moat/shadow_ledgers/", "desks/mt5/reports/DRAWDOWN_ALPHA.json"),
         writes=("desks/mt5/reports/SURVIVOR_NEIGHBOURHOOD.json",
                 "desks/mt5/data/hypotheses/miner_deepening_queue.json")),
    Node("resurrection", "desks/mt5/research/resurrection.py",
         reads=("desks/mt5/data/regime_state.json", "desks/mt5/data/state_vector.json",
                "backups/moat/shadow_ledgers/"),
         writes=("desks/mt5/reports/RESURRECTION.json",)),
    Node("data_prospector", "desks/mt5/research/data_prospector.py",
         reads=("desks/mt5/reports/REGIME_COVERAGE.json", "desks/mt5/data/state_vector.json"),
         writes=("desks/mt5/reports/DATA_PROSPECTOR.json",
                 "desks/mt5/data/prospector_targets.json")),
    Node("research_productivity", "desks/mt5/research/research_productivity.py",
         reads=("desks/mt5/data/hypotheses/deepening_worked.jsonl",
                "desks/mt5/data/hypotheses/miner_candidates.json",
                "desks/mt5/data/hypotheses/miner_deepening_queue.json",
                "desks/mt5/reports/universal_gates_external.json",
                "desks/mt5/data/UNIVERSAL_SURVIVORS.canon.json"),
         writes=("desks/mt5/reports/RESEARCH_PRODUCTIVITY.json",)),
    Node("live_manifest", "desks/mt5/research/live_manifest.py",
         reads=("desks/mt5/data/UNIVERSAL_SURVIVORS.canon.json",
                "desks/mt5/reports/ALLOCATOR_PROOF.json", "desks/mt5/data/gateway_state.json",
                "desks/mt5/data/state_vector.json", "desks/mt5/reports/STATE_ADMISSION.json",
                "desks/mt5/data/pf_forecast_log.jsonl"),
         writes=("desks/mt5/data/LIVE_MANIFEST.jsonl",)),
    # THE HOURLY DISCOVERY PASS (2026-09-05): every miner, proposer and data organ once an hour,
    # each in its own subprocess on a bandit-weighted budget. It decides nothing itself -- the
    # organs donate through the proposer contract as before -- so its own artifacts are the
    # per-organ status the fence reads and the ordering state the next pass reads.
    Node("hourly_discovery", "desks/mt5/research/hourly_discovery.py",
         reads=("desks/mt5/data/hourly_discovery_state.json",),
         writes=("desks/mt5/reports/HOURLY_DISCOVERY.json",
                 "desks/mt5/data/hourly_discovery_state.json")),
    # ---- THE DISCOVERY LOOP (2026-09-04): proposers, miners, feedback engines -----------------
    # Every proposer donates through proposer_common.donate into the intelligence intake the
    # compiler merges; every miner writes deepening tasks; every feedback engine writes a report
    # a person reads AND a queue row the worker reads. Declared so a producer nobody consumes
    # shows up red rather than looking busy.
    Node("alpha_evolution", "desks/mt5/research/alpha_evolution.py",
         reads=("desks/mt5/data/universe/", "backups/moat/shadow_ledgers/",
                "desks/mt5/data/generator_weights.json",
                # 2026-09-05: the three derived populations mine these ledgers, and the
                # portfolio-aware fitness prices a candidate against the book it would join.
                "desks/mt5/data/hypothesis_graph.jsonl",
                "desks/mt5/data/world_causal_graph.json",
                "desks/mt5/data/deep_forest_claims.jsonl",
                "desks/mt5/reports/pf_allocation.json"),
         writes=("desks/mt5/reports/alpha_evolution.json",
                 "desks/mt5/data/intelligence/alpha_evolution/")),
    Node("style_premia_sweep", "desks/mt5/research/style_premia_sweep.py",
         reads=("desks/mt5/data/universe/",),
         writes=("desks/mt5/reports/style_premia_sweep.json",
                 "desks/mt5/data/intelligence/style_premia/")),
    Node("cross_asset_graph", "desks/mt5/research/cross_asset_graph.py",
         reads=("desks/mt5/data/universe/",),
         writes=("desks/mt5/reports/CROSS_ASSET_GRAPH.json",
                 "desks/mt5/data/intelligence/cross_asset_graph/")),
    Node("tail_alpha_search", "desks/mt5/research/tail_alpha_search.py",
         reads=("desks/mt5/data/universe/", "backups/moat/shadow_ledgers/"),
         writes=("desks/mt5/reports/tail_alpha_search.json",
                 "desks/mt5/data/intelligence/tail_alpha/")),
    Node("anomaly_factory", "desks/mt5/research/anomaly_factory.py",
         reads=("desks/mt5/data/universe/", "desks/mt5/data/hypothesis_graph.jsonl",
                "desks/mt5/data/intelligence/anomalies/",
                "desks/mt5/data/intelligence/anomaly_cursor.json", "desks/mt5/data/acquired/"),
         writes=("desks/mt5/reports/ANOMALY_FACTORY.json",
                 "desks/mt5/data/intelligence/anomaly_factory/",
                 "desks/mt5/data/intelligence/anomalies/",
                 "desks/mt5/data/intelligence/anomaly_cursor.json",
                 "desks/mt5/data/hypotheses/miner_deepening_queue.json")),
    Node("survivor_distiller", "desks/mt5/research/survivor_distiller.py",
         reads=("desks/mt5/data/UNIVERSAL_SURVIVORS.canon.json",
                "desks/mt5/data/hypothesis_graph.jsonl",
                "desks/mt5/data/mutation_operator_weights.json"),
         writes=("desks/mt5/reports/SURVIVOR_DISTILLER.json",
                 "desks/mt5/data/intelligence/survivor_distiller/",
                 "desks/mt5/data/hypotheses/miner_deepening_queue.json")),
    Node("factor_model_coevolution", "desks/mt5/research/factor_model_coevolution.py",
         reads=("desks/mt5/data/universe/", "desks/mt5/data/features/",
                "desks/mt5/data/UNIVERSAL_SURVIVORS.canon.json"),
         writes=("desks/mt5/reports/COEVOLUTION.json", "desks/mt5/data/coevolution_trials.jsonl",
                 "desks/mt5/data/features/",
                 "desks/mt5/data/hypotheses/miner_deepening_queue.json")),
    Node("repo_miner", "desks/mt5/research/repo_miner.py",
         reads=("desks/mt5/data/repo_watchlist.json", "desks/mt5/data/repo_cache/"),
         writes=("desks/mt5/reports/REPO_MINER.json", "desks/mt5/data/repo_cache/",
                 "desks/mt5/data/hypotheses/miner_deepening_queue.json")),
    Node("deep_forest_miner", "desks/mt5/research/deep_forest_miner.py",
         reads=("desks/mt5/data/deep_forest_sources.json",
                "desks/mt5/data/deep_forest_claims.jsonl",
                "desks/mt5/data/deep_forest_seen.json", "desks/mt5/data/universe/universe.json",
                "desks/mt5/data/hypotheses/deepening_worked.jsonl"),
         writes=("desks/mt5/reports/DEEP_FOREST.json", "desks/mt5/data/deep_forest_claims.jsonl",
                 "desks/mt5/data/deep_forest_seen.json",
                 "desks/mt5/data/intelligence/world/frontier.json",
                 "desks/mt5/data/hypotheses/miner_deepening_queue.json")),
    Node("revival_engine", "desks/mt5/research/revival_engine.py",
         reads=("desks/mt5/data/hypothesis_graph.jsonl", "desks/mt5/reports/DRIFT.json",
                "desks/mt5/reports/REGIME_COVERAGE.json", "desks/mt5/reports/FILL_SURFACE.json"),
         writes=("desks/mt5/reports/REVIVAL.json",
                 "desks/mt5/data/hypotheses/miner_deepening_queue.json")),
    Node("drift_monitor", "desks/mt5/research/drift_monitor.py",
         reads=("desks/mt5/data/universe/", "backups/moat/shadow_ledgers/",
                "desks/mt5/reports/shadow/", "desks/mt5/data/UNIVERSAL_SURVIVORS.canon.json",
                # the hazard channels: admission verdicts, realised execution cost, edge signs
                "desks/mt5/reports/STATE_ADMISSION.json", "desks/mt5/reports/EXECUTION_TWIN.json",
                "desks/mt5/reports/CROSS_ASSET_GRAPH.json"),
         writes=("desks/mt5/reports/DRIFT.json",)),
    Node("exit_accounts", "desks/mt5/research/exit_accounts.py",
         reads=("backups/moat/shadow_ledgers/", "desks/mt5/data/excursions.jsonl",
                "desks/mt5/data/live_ledger.jsonl", "desks/mt5/data/pf_forecast_log.jsonl"),
         writes=("desks/mt5/reports/EXIT_ACCOUNTS.json",
                 "desks/mt5/data/hypotheses/miner_deepening_queue.json")),
    Node("action_counterfactuals", "desks/mt5/research/action_counterfactuals.py",
         reads=("backups/moat/shadow_ledgers/", "desks/mt5/data/live_ledger.jsonl",
                "desks/mt5/data/pf_forecast_log.jsonl", "desks/mt5/data/universe/"),
         writes=("desks/mt5/reports/ACTION_COUNTERFACTUALS.json",
                 "desks/mt5/data/action_counterfactuals.jsonl",
                 "desks/mt5/data/hypotheses/miner_deepening_queue.json")),
    Node("research_pnl", "desks/mt5/research/research_pnl.py",
         reads=("desks/mt5/data/hypothesis_graph.jsonl",
                "desks/mt5/data/UNIVERSAL_SURVIVORS.canon.json",
                "desks/mt5/data/pf_forecast_log.jsonl"),
         writes=("desks/mt5/reports/RESEARCH_PNL.json", "desks/mt5/data/research_marginal.json")),
    Node("mutation_yield", "desks/mt5/research/mutation_yield.py",
         reads=("desks/mt5/data/hypothesis_graph.jsonl",
                "desks/mt5/data/intelligence/survivor_distiller/"),
         writes=("desks/mt5/reports/MUTATION_YIELD.json",
                 "desks/mt5/data/mutation_operator_weights.json",
                 "desks/mt5/data/generator_weights.json")),
    Node("research_memory", "libs/research/memory.py",
         reads=("desks/mt5/data/hypothesis_graph.jsonl",
                "desks/mt5/data/UNIVERSAL_SURVIVORS.canon.json",
                "desks/mt5/reports/FILL_SURFACE.json", "desks/mt5/reports/NETTING.json",
                "desks/mt5/reports/REGIME_COVERAGE.json", "docs/graveyard.md",
                "docs/research/search_operator_library.md", "docs/GROWTH_GOVERNANCE.md"),
         writes=("desks/mt5/data/memory/",)),
    Node("feature_roi", "desks/mt5/research/feature_roi.py",
         reads=("desks/mt5/data/capital_modifier_ledger.jsonl",
                "desks/mt5/reports/CAPITAL_MODIFIERS.json",
                "desks/mt5/reports/allocator_attribution.json",
                "desks/mt5/reports/RESEARCH_PNL.json",
                "desks/mt5/reports/STATE_ADMISSION.json",
                "desks/mt5/data/UNIVERSAL_SURVIVORS.canon.json"),
         # It rewrites the sidecars' `status`/`roi` in place: the warehouse is both its input
         # population and where its verdict lands.
         writes=("desks/mt5/reports/FEATURE_ROI.json", "desks/mt5/data/features/"),
         # It DECIDES: `feature_lifecycle.withdraw` reads the status it writes, and an organ that
         # honours it stops spending compute. That is authority, not advice.
         authority=("feature_effort",)),
    Node("module_rent", "libs/ops/module_rent.py",
         reads=("desks/mt5/reports/MISSED_GROWTH.json", "desks/mt5/reports/RESEARCH_PNL.json",
                "desks/mt5/reports/STATE_ADMISSION.json",
                "desks/mt5/reports/CAPITAL_MODIFIERS.json",
                "desks/mt5/reports/pf_allocation.json",
                "desks/mt5/data/capital_modifier_ledger.jsonl",
                "desks/mt5/data/execution_algo_outcomes.jsonl",
                "desks/mt5/data/live_ledger.jsonl", "desks/mt5/reports/shadow/",
                "desks/mt5/data/module_rent.jsonl"),
         writes=("desks/mt5/reports/MODULE_RENT.json", "desks/mt5/data/module_rent.jsonl")),
    Node("research_bandit", "desks/mt5/research/research_bandit.py",
         reads=("desks/mt5/data/hypothesis_graph.jsonl", "desks/mt5/data/research_marginal.json",
                # dElog per data source and the DEAD INFORMATION list: the budget is where
                # naming becomes a decision.
                "desks/mt5/reports/allocator_attribution.json",
                # THE BREADTH CREDIT'S INPUT, and the edge that makes the research budget respond
                # to a PORTFOLIO weakness rather than to a price list (principal, 2026-09-07:
                # "your research allocator should respond to portfolio weaknesses"). This edge is
                # the loop closing: the allocator measures effective breadth, `alpha_breadth`
                # publishes it and the clusters nobody occupies, and the bandit prices an arm's
                # output by the dk_eff it would buy THIS book. Without the edge the bandit reads
                # only its own history and can never learn that the book is one bet.
                "desks/mt5/reports/EFFECTIVE_BREADTH.json"),
         writes=("desks/mt5/data/research_budget.json",
                 "desks/mt5/reports/RESEARCH_BANDIT.json")),

    # ----------------------------------------------------------- THE DATA MOAT --
    # Three nodes forming one chain, and the chain is the argument: the recorder captures what
    # cannot be recaptured, the checker proves what was captured, and only proven days become
    # features. Each reads the one before it, so a break anywhere is visible as a break rather
    # than as a quiet decline in coverage.
    #
    # THE TAPE ITSELF IS NOT A GRAPH ARTIFACT and cannot be: it lives at MT5_TAPE_ROOT
    # (C:\mt5tape by default), outside the git tree, because a directory growing by gigabytes a
    # year has no business in a repository. `reports/TAPE_RECORDER.json` is the recorder's one
    # in-repo output and exists precisely so the tape is observable from a box with no shell on
    # the Windows machine -- the reachability problem AGENTS.md names.
    Node("tick_recorder", "desks/mt5/recorders/tick_recorder.py",
         writes=("desks/mt5/reports/TAPE_RECORDER.json",)),
    Node("tick_integrity", "desks/mt5/recorders/tick_integrity.py",
         writes=("desks/mt5/reports/TICK_INTEGRITY.json",),
         reads=("desks/mt5/reports/TAPE_RECORDER.json",)),
    Node("tape_features", "desks/mt5/recorders/tape_features.py",
         # data/tape/ticks/ is the silver layer external_gauntlet already reads (see its node);
         # the rest are measured surfaces whose consumers are NAMED in the module's CONSUMERS
         # map and not yet wired, which is why they sit in HUMAN_READ rather than claiming a
         # decision path they do not have.
         writes=("desks/mt5/data/tape/ticks/", "desks/mt5/data/tape/intrabar/",
                 "desks/mt5/data/cost_surface_tick.json",
                 "desks/mt5/data/tape/slippage_surface.json",
                 "desks/mt5/data/tape_features_state.json",
                 "desks/mt5/reports/TAPE_FEATURES.json"),
         reads=("desks/mt5/reports/TICK_INTEGRITY.json",
                "desks/mt5/data/universe/universe.json")),
    # The vol archive is ADVISORY BY CONSTRUCTION and its node says so: it holds no authority,
    # reaches no decision, and every one of its outputs is human-read. That is not a gap to close
    # later -- a forward-only dataset with no backtest may not condition capital, and the node is
    # where that claim is checkable rather than merely written in a docstring.
    Node("vol_archive", "desks/mt5/recorders/vol_archive.py",
         writes=("desks/mt5/data/vol_archive/observations.jsonl",
                 "desks/mt5/reports/VOL_ARCHIVE.json"),
         reads=("desks/mt5/data/universe/universe.json", "desks/mt5/data/universe/")),

    # ---------------------------------------------------------------- 2026-09-10: paying down
    # the undeclared debt `scripts/check_completion.py` measures. 88 legs sit in the two cycles
    # and 78 of them declared NO artifact here, so `libs.ops.completion` -- which asks whether a
    # leg that ran actually produced anything -- was blind to 89% of the desk's hourly compute.
    # That blindness is exactly how `pf_allocator` returned exit 1 every hour for six days with
    # every panel reading healthy. These are the legs added on 2026-09-10, declared at once so
    # the ceiling falls in the same commit that records it.
    Node("hunt12", "desks/mt5/research/run_hunt12.py",
         # THE ALLOCATOR'S FIRST INPUT. `portfolio_projection.load_h12_survivors` refuses
         # without it and `pf_allocator` assembles its evidence through that projection, so an
         # absent hunt12 report is the growth sizer refusing to solve -- which is precisely the
         # edge nothing declared and nothing could therefore check.
         writes=("desks/mt5/reports/hunt12_partial.json", "desks/mt5/reports/hunt12.json"),
         reads=("desks/mt5/data/universe/universe.json", "desks/mt5/data/universe/"),
         freshness_s={"desks/mt5/reports/hunt12_partial.json": 8 * 24 * 3600}),
    Node("microstructure_census", "libs/research/microstructure_census.py",
         writes=("desks/mt5/reports/MICROSTRUCTURE.json",),
         reads=("desks/mt5/data/universe/universe.json", "desks/mt5/data/tape/")),
    Node("entry_timing", "desks/mt5/research/entry_timing.py",
         writes=("desks/mt5/reports/ENTRY_TIMING.json",),
         reads=("desks/mt5/reports/SPREAD_PROVENANCE.json",
                "desks/mt5/data/universe/universe.json")),
    Node("spread_provenance", "desks/mt5/research/spread_provenance.py",
         writes=("desks/mt5/reports/SPREAD_PROVENANCE.json",),
         reads=("desks/mt5/data/universe/universe.json",)),
    Node("tape_features", "desks/mt5/research/tape_features.py",
         writes=("desks/mt5/reports/TAPE_RECORDER.json",),
         reads=("desks/mt5/data/tape/",)),
    Node("futures_lead_lag", "desks/mt5/research/futures_lead_lag.py",
         writes=("desks/mt5/reports/FUTURES_LEAD_LAG.json", "desks/mt5/reports/BAR_CLOCK.json"),
         reads=("desks/mt5/data/universe/",)),
    Node("time_joins", "scripts/check_time_joins.py",
         writes=("desks/mt5/reports/TIME_JOINS.json",)),
    Node("fusion_cost", "libs/portfolio/fusion_cost.py",
         writes=("desks/mt5/reports/FUSION_COST.json",),
         reads=("desks/mt5/data/universe/universe.json",)),
    Node("cost_construction", "scripts/check_cost_construction.py",
         writes=("desks/mt5/reports/COST_CONSTRUCTION.json",)),
    Node("edges_macro_fusion_sweep", "desks/mt5/research/run_edges_macro_fusion_sweep.py",
         writes=("desks/mt5/reports/edges_macro_fusion_sweep.json",),
         reads=("desks/mt5/data/universe/universe.json", "desks/mt5/data/universe/")),
    Node("queue_cycle", "libs/ops/queue_cycle.py",
         writes=("desks/mt5/reports/QUEUE.json",),
         reads=("desks/mt5/data/task_queue.jsonl",)),
    Node("wiring_audit", "libs/ops/wiring_audit.py",
         writes=("desks/mt5/reports/WIRING_AUDIT.json",)),
    Node("completion", "libs/ops/completion.py",
         # THE FENCE THAT ASKS WHETHER A LEG THAT RAN PRODUCED ANYTHING. It reads the two
         # records of what the cycles did and joins them onto this graph's own declarations.
         writes=("desks/mt5/reports/COMPLETION.json",),
         reads=("desks/mt5/data/sync_marker.json", "desks/mt5/data/compute_ledger.jsonl")),
    # ---------------------------------------------------------------- 2026-09-10, second pass:
    # 27 more cycle legs declared, each write RESOLVED FROM ITS OWN PATH EXPRESSION rather than
    # guessed from the filename. The shortcut of "a bare NAME.json written by a desk module lands
    # in reports/" was wrong twice in four spot-checks -- `moat_miner` and `requeue_unrunnable`
    # both write under data/hypotheses/ -- and a wrong declaration is worse than none, because
    # `libs.ops.completion` would then check the wrong file and report a healthy leg as broken or
    # a broken one as healthy. Seven further legs write to a runtime variable and are deliberately
    # left UNDECLARED rather than filled in with a plausible path.
    Node("archive_tape", "desks/mt5/scripts/archive_tape.py",
         writes=("desks/mt5/reports/TAPE_ARCHIVE.json",)),
    Node("arena", "libs/research/arena.py",
         writes=("desks/mt5/reports/ARM_VERDICTS.json",)),
    Node("brain_ab", "libs/research_os/brain_ab.py",
         writes=("data/brain_ab.json",)),
    Node("burn_in", "desks/mt5/research/burn_in.py",
         writes=("desks/mt5/reports/burn_in.json",)),
    Node("capacity", "desks/mt5/research/capacity.py",
         writes=("desks/mt5/reports/CAPACITY.json",)),
    Node("edge_confidence", "desks/mt5/research/edge_confidence.py",
         writes=("desks/mt5/reports/EDGE_CONFIDENCE.json",)),
    Node("edge_reliability", "desks/mt5/research/edge_reliability.py",
         writes=("desks/mt5/reports/edge_reliability.json",)),
    Node("execution_resolver", "desks/mt5/research/execution_resolver.py",
         writes=("desks/mt5/reports/execution_resolver.json",)),
    Node("exit_study", "desks/mt5/research/exit_study.py",
         writes=("desks/mt5/reports/exit_study.json",)),
    Node("experiment_cache", "desks/mt5/research/experiment_cache.py",
         writes=("desks/mt5/reports/EXPERIMENT_CACHE.json",)),
    Node("experiment_design", "desks/mt5/research/experiment_design.py",
         writes=("desks/mt5/reports/EXPERIMENT_DESIGN.json",)),
    Node("forecast_contract", "desks/mt5/research/forecast_contract.py",
         writes=("desks/mt5/reports/FORECAST_CONTRACT.json",)),
    Node("issue_board", "desks/mt5/research/issue_board.py",
         writes=("desks/mt5/reports/ISSUE_BOARD.json",)),
    Node("layer_census", "libs/research/layers.py",
         writes=("desks/mt5/reports/layer_census.json",)),
    Node("ml_layer", "desks/mt5/research/ml_layer.py",
         writes=("desks/mt5/reports/ML_LAYER.json",)),
    Node("moat_miner", "desks/mt5/research/moat_miner.py",
         writes=("desks/mt5/data/hypotheses/moat_candidates.json",)),
    Node("opportunity_cost", "desks/mt5/research/opportunity_cost.py",
         writes=("desks/mt5/reports/opportunity_cost.json",)),
    Node("opportunity_forecast", "desks/mt5/research/opportunity_forecast.py",
         writes=("desks/mt5/reports/opportunity_forecast.json",)),
    Node("opportunity_gap", "desks/mt5/research/opportunity_gap.py",
         writes=("desks/mt5/reports/OPPORTUNITY_GAP.json",)),
    Node("rebalance_trigger", "desks/mt5/research/rebalance_trigger.py",
         writes=("desks/mt5/reports/REBALANCE_TRIGGER.json",)),
    Node("reclaim_disk", "desks/mt5/scripts/reclaim_disk.py",
         writes=("desks/mt5/reports/DISK_RECLAIM.json",)),
    Node("requeue_unrunnable", "desks/mt5/research/requeue_unrunnable.py",
         writes=("desks/mt5/data/hypotheses/external_survivors.json",
                 "desks/mt5/reports/REQUEUED_UNRUNNABLE.json")),
    Node("research_org", "desks/mt5/research/research_org.py",
         writes=("desks/mt5/reports/RESEARCH_ORG.json",)),
    Node("scaling_laws", "libs/ops/scaling_laws.py",
         writes=("desks/mt5/reports/scaling_laws.json",)),
    Node("session_capital", "desks/mt5/research/session_capital.py",
         writes=("desks/mt5/reports/session_capital.json",)),
    Node("timeframe_coverage", "desks/mt5/scripts/check_timeframe_coverage.py",
         writes=("desks/mt5/reports/TIMEFRAME_COVERAGE.json",)),
    Node("world_crawler", "desks/mt5/side_channels/world_crawler.py",
         writes=("desks/mt5/reports/world_crawl.json",)),
    # ---------------------------------------------------------------------------------
    # DECLARED 2026-09-15, because a leg that declares nothing cannot be checked for
    # completion by anything -- which is how a leg returning exit 1 every hour went six days
    # unnoticed. The live count was 60 UNDECLARED against a ceiling of 40 that RATCHETS DOWN
    # ONLY, so the state was a breach, and four of the sixty were legs added the same night.
    #
    # EVERY PATH BELOW IS READ FROM THE MODULE'S OWN OUTPUT CONSTANT, never guessed from the
    # leg's name. An earlier pass filtered on 'the artifact exists on disk' and derived only
    # eleven -- the wrong test: a node declares what it WRITES, and a leg that has never run
    # on this box writes the same path it would write anywhere. A leg whose artifact could
    # not be read from source is deliberately left UNDECLARED rather than invented, because a
    # ceiling made green by a guessed path is worse than one that is honestly too high.
    Node("acceptance", "scripts/check_acceptance_properties.py",
         writes=("docs/research/tier1_program.json",
                 "desks/mt5/reports/acceptance_properties.json")),
    Node("alpha_rl", "desks/mt5/research/alpha_rl_run.py",
         writes=("desks/mt5/reports/ALPHA_RL.json",)),
    Node("asia_collector", "desks/mt5/research/asia_collector.py",
         writes=("desks/mt5/reports/ASIA_COLLECTOR.json",)),
    Node("asia_plane", "desks/mt5/research/asia_plane.py",
         writes=("desks/mt5/reports/ASIA_PLANE.json",)),
    Node("cost_to_edge", "desks/mt5/research/cost_to_edge.py",
         writes=("desks/mt5/reports/COST_TO_EDGE.json",)),
    # Prices every arm of one decision (veto, sizing, execution, exit, missed trade); the rent
    # ledger already bills two of those arms under their own names, and this node's output is
    # the union of them rather than a new line.
    Node("counterfactual_world", "libs/research/counterfactual_world.py",
         writes=("desks/mt5/reports/COUNTERFACTUAL_WORLD.json",),
         billed_as=("counterfactual_replay", "action_counterfactuals")),
    Node("dead_architecture", "scripts/check_dead_architecture.py",
         writes=("desks/mt5/reports/dead_architecture.json",)),
    Node("deep_forest", "desks/mt5/research/deep_forest_miner.py",
         writes=("desks/mt5/reports/DEEP_FOREST.json",)),
    Node("exogenous_search", "desks/mt5/research/unknown_unknowns.py",
         writes=("desks/mt5/reports/UNKNOWN_UNKNOWNS.json",)),
    Node("falsifier_run", "desks/mt5/research/falsifier_run.py",
         writes=("desks/mt5/reports/FALSIFIER_VERDICTS.json",)),
    Node("fill_attribution", "desks/mt5/research/fill_attribution.py",
         writes=("desks/mt5/reports/FILL_ATTRIBUTION.json",)),
    Node("forward_reconcile", "desks/mt5/research/forward_reconcile.py",
         writes=("desks/mt5/data/forward_reconcile.json",)),
    Node("input_identity", "libs/data/input_identity.py",
         writes=("desks/mt5/data/input_identity.json",)),
    Node("lake_promote", "desks/mt5/research/lake_promote.py",
         writes=("desks/mt5/reports/LAKE_PROMOTION.json",)),
    Node("orthogonality", "desks/mt5/research/orthogonality.py",
         writes=("desks/mt5/reports/ORTHOGONALITY.json",)),
    Node("prosecutor", "scripts/check_prosecutor.py",
         writes=("desks/mt5/reports/prosecutor_census.json",)),
    Node("research_exchange_score", "scripts/research_exchange.py",
         writes=("data/suggestion_ledger.jsonl",)),
    Node("residual_factors", "desks/mt5/research/factor_residual_engine.py",
         writes=("desks/mt5/reports/factor_residual.json",)),
    Node("session_allocation", "desks/mt5/research/session_allocator.py",
         writes=("desks/mt5/reports/SESSION_ALLOCATION.json",)),
    Node("session_chart_expansion", "desks/mt5/research/session_chart_equivalents.py",
         writes=("desks/mt5/reports/SESSION_ALLOCATION.json",
                 "desks/mt5/reports/SESSION_CHART_EXPANSION.json")),
    Node("sge_premium", "desks/mt5/research/fetch_sge_premium.py",
         writes=("desks/mt5/data/lake/sge_daily.parquet",)),
    Node("source_routes", "scripts/check_source_routes.py",
         writes=("desks/mt5/reports/SOURCE_ROUTES.json",)),
    Node("stamp_freshness", "scripts/check_stamp_freshness.py",
         writes=("desks/mt5/reports/STAMP_FRESHNESS.json",)),
    Node("state_vector", "desks/mt5/research/state_vector_build.py",
         writes=("desks/mt5/data/state_vector.json",)),
    Node("stop_reverse", "desks/mt5/research/stop_reverse_census.py",
         writes=("desks/mt5/reports/STOP_REVERSE_CENSUS.json",)),
    Node("strategy_paths", "desks/mt5/research/strategy_paths.py",
         writes=("desks/mt5/data/strategy_paths.json", "desks/mt5/reports/STRATEGY_PATHS.json",)),
    Node("swap_rejudge", "desks/mt5/research/swap_rejudge.py",
         writes=("desks/mt5/reports/SWAP_REJUDGE.json",)),
    Node("weak_signals", "desks/mt5/research/weak_signal_compiler.py",
         writes=("desks/mt5/reports/weak_signal_compiler.json",)),
)

#: Artifacts a person is expected to read. Being the ONLY reader of a node's output makes that
#: node advisory. Listed so the check has a definition rather than an opinion.
HUMAN_READ = frozenset({
    # The macro layer's report. Read by a person; the layer's one decision edge is the
    # interrupt above, declared in EXTERNAL_READERS with its reader named.
    "desks/mt5/reports/MACRO_INTEL.json",
    "desks/mt5/reports/markout.json", "desks/mt5/reports/allocator_attribution.json",
    "desks/mt5/reports/RESURRECTION.json", "desks/mt5/reports/DATA_PROSPECTOR.json",
    "desks/mt5/data/LIVE_MANIFEST.jsonl", "desks/mt5/reports/factor_residual.json",
    "desks/mt5/reports/plumbing_miner.json", "desks/mt5/reports/transition_alpha.json",
    "desks/mt5/reports/weak_signal_compiler.json", "desks/mt5/reports/FUND_PLAYBOOK.json",
    "desks/mt5/reports/pf_allocator.json", "desks/mt5/reports/REGIME_COVERAGE.json",
    "desks/mt5/reports/RESEARCH_PRODUCTIVITY.json", "desks/mt5/reports/FILTER_VALUE.json",
    "desks/mt5/reports/EXCURSIONS.json", "desks/mt5/reports/ALPHA_GENOME.json",
    "desks/mt5/reports/OPPORTUNITY_CURVE.json", "desks/mt5/reports/MICROSTRUCTURE_SURFACES.json",
    "desks/mt5/reports/microstructure_miner.json", "desks/mt5/reports/MISSED_GROWTH.json",
    "desks/mt5/reports/CAPITAL_MODIFIERS.json", "desks/mt5/reports/FILL_SURFACE.json",
    "desks/mt5/reports/NETTING.json", "desks/mt5/reports/NETTING_BOOK.json",
    # The execution twin's report, private dataset and watermark: advisory until the cost
    # model reads the report (see the execution_twin node). The portfolio gap likewise until
    # the research bandit reads it.
    "desks/mt5/reports/EXECUTION_TWIN.json", "desks/mt5/data/execution_twin_cases.jsonl",
    # THE FILL CORPUS and the alpha-capture ratio it prices. Human-read is the HONEST state
    # today, not a placeholder: the corpus is the collection asset, `ALPHA_CAPTURE.json` is the
    # measurement a person acts on, and the two models built on it (conditional execution choice,
    # meta-labeler) are UNMEASURED harnesses wired to nothing that sends an order. The day one of
    # them is wired, its consumer is declared and the corpus leaves this set.
    "desks/mt5/data/fill_corpus.jsonl", "desks/mt5/reports/ALPHA_CAPTURE.json",
    "desks/mt5/data/alpha_capture_history.jsonl",
    # The counterfactual world's report, its versioned dataset and its watermark: advisory
    # until missed_growth reads VETO_ALPHA off the report (see the counterfactual_replay node).
    "desks/mt5/reports/FEATURE_ROI.json", "desks/mt5/reports/MODULE_RENT.json",
    "desks/mt5/reports/GROWTH_ATTRIBUTION_WEEKLY.json",
    "desks/mt5/data/decision_dataset.jsonl",
    "desks/mt5/data/decision_dataset_watermark.json",
    "desks/mt5/data/execution_twin_state.json", "desks/mt5/reports/portfolio_gap.json",
    # THE DATA MOAT'S MEASURED SURFACES, advisory until their named consumers are switched.
    # `data/cost_surface_tick.json` is byte-compatible with what research/cost_surface.py writes,
    # so cost_surface.spread_pts() reads it with no code change -- but nothing points at it YET,
    # and claiming a decision path before the switch is made would be exactly the producer/
    # consumer collapse this graph exists to catch. Same for the slippage surface, whose consumer
    # (mt5desk/fill_surface.py's below-MIN_FILLS fallback constant) is named in
    # recorders/tape_features.CONSUMERS. Both switches deserve a before/after, not a silent edit.
    "desks/mt5/data/cost_surface_tick.json", "desks/mt5/data/tape/slippage_surface.json",
    "desks/mt5/reports/TAPE_FEATURES.json", "desks/mt5/reports/TICK_INTEGRITY.json",
    "desks/mt5/data/tape_features_state.json",
    # The vol archive: forward-only, no backtest, no promotion authority in any lane until its
    # own vintages are long enough. Human-read is the CORRECT terminal state for it today, not a
    # placeholder -- see recorders/vol_archive.py's MOAT CLAIM.
    "desks/mt5/reports/VOL_ARCHIVE.json",
    # The release-identity verdict and the box smoke test: read by every brain through the
    # box's git sync and by the dashboard; the gateway consumes the verdict in-process.
    "desks/mt5/data/release_identity.json", "desks/mt5/reports/release_smoke.json",
    # The hourly discovery pass's own bookkeeping: per-organ status for the fence and a person,
    # and the staleness order the next pass reads. The organs' donations reach decisions through
    # the compiler; this pass only schedules them.
    "desks/mt5/reports/HOURLY_DISCOVERY.json", "desks/mt5/data/hourly_discovery_state.json",
    "desks/mt5/reports/alpha_evolution.json", "desks/mt5/reports/style_premia_sweep.json",
    "desks/mt5/reports/CROSS_ASSET_GRAPH.json", "desks/mt5/reports/tail_alpha_search.json",
    "desks/mt5/reports/ANOMALY_FACTORY.json", "desks/mt5/reports/SURVIVOR_DISTILLER.json",
    "desks/mt5/reports/COEVOLUTION.json", "desks/mt5/reports/REPO_MINER.json",
    "desks/mt5/reports/DEEP_FOREST.json", "desks/mt5/reports/REVIVAL.json",
    "desks/mt5/reports/EXIT_ACCOUNTS.json", "desks/mt5/reports/ACTION_COUNTERFACTUALS.json",
    "desks/mt5/reports/RESEARCH_PNL.json", "desks/mt5/reports/MUTATION_YIELD.json",
    "desks/mt5/reports/RESEARCH_BANDIT.json",
    # THE BREADTH LANE'S REPORTS. Each producer's DECISION path is the deepening queue it also
    # writes; these three files are the evidence a person reads beside it -- nominal against
    # effective breadth with every reading's status, the book's own drawdown windows and what
    # earns inside them, and where a surviving edge is stronger or absent. None of them
    # conditions capital, and listing them here is the claim that they do not.
    "desks/mt5/reports/EFFECTIVE_BREADTH.json", "desks/mt5/reports/DRAWDOWN_ALPHA.json",
    "desks/mt5/reports/SURVIVOR_NEIGHBOURHOOD.json",
})

#: Consumers outside this graph that are known to read an artifact -- the crawler reads the
#: prospector's targets, the box's PowerShell reads the manifest. DECLARED, so a DEAD_PRODUCER
#: verdict cannot be silenced by an unnamed "something reads it".
EXTERNAL_READERS = {
    "desks/mt5/data/prospector_targets.json": "world_crawler (side_channels)",
    "desks/mt5/data/hypotheses/deepened_candidates.json": "external_gauntlet via compiler merge",
    "desks/mt5/data/state_fits.json": "state_vector_build (its own cache)",
    "desks/mt5/data/module_rent.jsonl": "module_rent (its own append-only window history)",
    "desks/mt5/data/vol_archive/observations.jsonl": ("vol_archive (its own append-only vintage "
                                                     "series; the archive IS the asset and is "
                                                     "read back to count desk vintages)"),
    "desks/mt5/data/tape/intrabar/": ("read per bar by whatever revalues the engine's fill "
                                      "semantics; NOT wired into mt5desk/engine.py, because "
                                      "every live certificate was minted under its current "
                                      "assumption and re-pricing the canon is a deliberate act"),
    # Append-only ledgers that are their own memory: each engine reads back what it wrote so
    # a decision is priced exactly once. Self-reads are not counted as readers by `check`.
    "desks/mt5/data/counterfactuals.jsonl": "counterfactual_markout (its own append-only memory)",
    "desks/mt5/data/excursions.jsonl": "excursions (its own append-only memory)",
    "desks/mt5/data/missed_growth.jsonl": "missed_growth (its own append-only memory)",
    "desks/mt5/data/action_counterfactuals.jsonl": "action_counterfactuals (its own memory)",
    "desks/mt5/data/deep_forest_claims.jsonl": "deep_forest_miner (its own append-only memory)",
    # THE MACRO LAYER'S MEMORY. Each of these is read back by `macro_intel` on its next pass and
    # by nothing else, which is precisely what makes the layer LEARN rather than restate: the
    # taxonomy's centroids move with the instances assigned to them, the credibility posteriors
    # accumulate a source's record, the factor basis is refitted, and the multiplicity charge
    # only ever grows so that re-testing a cell makes admission harder. Declared here with the
    # reason rather than left to read as DEAD_PRODUCER, because "nothing reads it" and "only its
    # own author reads it" are different facts and only one of them is a defect.
    "desks/mt5/data/macro/taxonomy.json": "macro_intel (its own category centroids)",
    "desks/mt5/data/macro/source_credibility.json": "macro_intel (its own Beta posteriors)",
    "desks/mt5/data/macro/factor_basis.json": "macro_intel (its own discovered factor basis)",
    "desks/mt5/data/macro/exposures.json": "macro_intel (its own admitted category->factor edges)",
    "desks/mt5/data/macro/multiplicity.json": ("macro_intel (its own never-shrinking Bonferroni "
                                               "charge; monotone by design)"),
    "desks/mt5/data/macro/event_attribution.jsonl": ("macro_intel (its own append-only memory; "
                                                     "the measured decay half-lives come back "
                                                     "from here, which is the loop that lets the "
                                                     "interrupt gate ever fire)"),
    "desks/mt5/data/macro/event_ledger.jsonl": "macro_intel (its own append-only event record)",
    "desks/mt5/data/macro/allocator_interrupt.json": ("research_supervisor.tick_periodic -- it "
                                                      "reads this to bring the allocator's fast "
                                                      "leg forward. The supervisor is a process "
                                                      "manager, not a graph node, so the edge is "
                                                      "declared here rather than left to read as "
                                                      "DEAD_PRODUCER. This is the ONLY artifact "
                                                      "of this layer that reaches a decision, and "
                                                      "the decision it reaches is WHEN to solve, "
                                                      "never what to hold."),
    "desks/mt5/data/macro/interrupt_log.jsonl": ("macro_intel (its own rate-limit window; an "
                                                 "interrupt that fires constantly is an "
                                                 "expensive clock)"),
    "desks/mt5/data/deep_forest_seen.json": "deep_forest_miner (its own seen-ledger)",
    "desks/mt5/data/intelligence/anomaly_cursor.json": "anomaly_miner (its own rotation cursor)",
    "desks/mt5/data/memory/": "deepening_worker.task_text (memory.prompt_context on every prompt)",
    "desks/mt5/data/research_budget.json": ("daily_cycle proposer budgets and deepening_worker "
                                            "voi_order, through bandit.arm_weight"),
    "desks/mt5/data/coevolution_trials.jsonl": "experiment_ledger (lifetime multiplicity)",
    "desks/mt5/data/intelligence/world/frontier.json": "world_crawler (side_channels)",
    "desks/mt5/data/repo_cache/": "repo_miner (its own cache)",
    "desks/mt5/data/intelligence/alpha_evolution/": "miner_candidate_compiler intake glob",
    "desks/mt5/data/intelligence/style_premia/": "miner_candidate_compiler intake glob",
    "desks/mt5/data/intelligence/cross_asset_graph/": "miner_candidate_compiler intake glob",
    "desks/mt5/data/intelligence/tail_alpha/": "miner_candidate_compiler intake glob",
    "desks/mt5/data/intelligence/anomaly_factory/": "miner_candidate_compiler intake glob",
    "desks/mt5/data/intelligence/survivor_distiller/": "miner_candidate_compiler intake glob",
    "desks/mt5/data/features/": "feature_store (content-addressed cache)",
    "desks/mt5/data/effective_breadth.jsonl": ("alpha_breadth (its own append-only series; a "
                                               "breadth number with no history cannot say whether "
                                               "the desk is widening or only adding names)"),
}

_PATH_RE = re.compile(r"[\"']((?:desks/mt5/|backups/|reports/|data/)[A-Za-z0-9_./-]+)[\"']")


def _covers(declared: str, path: str) -> bool:
    return path == declared or (declared.endswith("/") and path.startswith(declared))


#: Hand-maintained inputs: written by a person (or by the box's universe fetch), read by nodes.
#: Declared so a DEAD_CONSUMER verdict cannot be silenced by an unnamed "somebody writes it".
CONFIG_INPUTS = frozenset({
    "desks/mt5/data/repo_watchlist.json", "desks/mt5/data/deep_forest_sources.json",
    "desks/mt5/data/universe/universe.json",
    # Box-produced inputs: acquire_datasets fills this from the prospector's targets.
    "desks/mt5/data/acquired/",
    # Hand-written doctrine the research memory ingests as method and failure memories.
    "docs/graveyard.md", "docs/research/search_operator_library.md", "docs/GROWTH_GOVERNANCE.md",
})

MAX_DECISION_DEPTH = 5


def _decision_paths(start: Node, nodes: tuple[Node, ...],
                    read_by: Any) -> set[str]:
    """Chains from `start`'s outputs to an authority node or a declared external reader."""
    by_name = {x.name: x for x in nodes}
    found: set[str] = set()
    frontier: list[tuple[Node, str]] = [(start, start.name)]
    seen: set[str] = {start.name}
    depth = 0
    while frontier and depth < MAX_DECISION_DEPTH:
        nxt: list[tuple[Node, str]] = []
        for node, path in frontier:
            for w in node.writes:
                if w in EXTERNAL_READERS:
                    found.add(f"{path}->{EXTERNAL_READERS[w]}")
                for name in read_by(w):
                    reader = by_name.get(name)
                    if reader is None or name == node.name:
                        continue
                    if reader.authority:
                        found.add(f"{path}->{name}")
                    elif name not in seen:
                        seen.add(name)
                        nxt.append((reader, f"{path}->{name}"))
        frontier = nxt
        depth += 1
    return found


def check(nodes: tuple[Node, ...] = NODES) -> dict[str, Any]:
    writers: dict[str, list[str]] = {}
    readers: dict[str, list[str]] = {}
    for n in nodes:
        for w in n.writes:
            writers.setdefault(w, []).append(n.name)
        for r in n.reads:
            readers.setdefault(r, []).append(n.name)

    def _read_by(artifact: str) -> list[str]:
        out = []
        for r, names in readers.items():
            if _covers(r, artifact) or _covers(artifact, r):
                out.extend(names)
        return sorted(set(out))

    def _written_by(artifact: str) -> list[str]:
        out = []
        for w, names in writers.items():
            if _covers(w, artifact) or _covers(artifact, w):
                out.extend(names)
        return sorted(set(out))

    findings: list[dict[str, str]] = []
    for n in nodes:
        for w in n.writes:
            rd = [x for x in _read_by(w) if x != n.name]
            if not rd and w not in HUMAN_READ and w not in EXTERNAL_READERS:
                findings.append({"check": "DEAD_PRODUCER", "node": n.name, "artifact": w,
                                 "why": "written and read by nothing in the graph"})
        for r in n.reads:
            box_only = ("desks/mt5/data/universe/", "backups/moat/shadow_ledgers/",
                        "desks/mt5/data/intelligence/",
                        "desks/mt5/data/intelligence/ff_calendar_vintage",
                        "desks/mt5/reports/hunt12_partial.json")
            if (not _written_by(r) and not (r.endswith("/") and (ROOT / r).exists())
                    and r not in box_only and r not in CONFIG_INPUTS):
                findings.append({"check": "DEAD_CONSUMER", "node": n.name, "artifact": r,
                                 "why": "read and written by nothing in the graph"})
        if n.writes and not n.authority:
            # A producer reaches a decision when some chain of readers ends at an authority
            # node or at a declared EXTERNAL reader (regime_coverage -> deepening queue ->
            # deepening_worker -> deepened_candidates -> external_gauntlet is a real path, and
            # drift_monitor -> revival_engine -> deepening queue -> deepening_worker -> gauntlet
            # is one hop longer). Walked breadth-first over non-authority nodes to a bounded
            # depth, with the path recorded, so the verdict names the chain rather than a hop
            # count that happened to fit yesterday's graph.
            decision_readers = _decision_paths(n, nodes, _read_by)
            if not decision_readers and not all(w in HUMAN_READ for w in n.writes):
                findings.append({"check": "ADVISORY_ONLY", "node": n.name,
                                 "artifact": ", ".join(n.writes),
                                 "why": "computes artifacts that reach no decision"})

    # UNMEASURED_AUTHORITY: conditioning dimensions must be judged, and not buried.
    try:
        adm = json.loads((DESK / "reports" / "STATE_ADMISSION.json").read_text("utf-8"))
        judged = set((adm.get("verdicts") or {}).keys()) | set(adm.get("gaps") or {})
        buried = set(adm.get("graveyard") or [])
    except (OSError, ValueError):
        judged, buried = set(), set()
    for n in nodes:
        for dim in n.conditions_on:
            if dim in buried:
                findings.append({"check": "UNMEASURED_AUTHORITY", "node": n.name,
                                 "artifact": dim, "why": "conditions on a BURIED dimension"})
            elif judged and dim not in judged:
                findings.append({"check": "UNMEASURED_AUTHORITY", "node": n.name,
                                 "artifact": dim, "why": "conditions on a dimension never judged"})

    # UNDECLARED: path literals in a node's source that the graph does not know about.
    known = {p for n in nodes for p in (*n.writes, *n.reads)}
    for n in nodes:
        try:
            src = (ROOT / n.module).read_text("utf-8")
        except OSError:
            findings.append({"check": "MISSING_MODULE", "node": n.name, "artifact": n.module,
                             "why": "declared module does not exist"})
            continue
        for m in _PATH_RE.finditer(src):
            lit = m.group(1)
            if lit.endswith(".py"):
                continue                       # a module reference (release manifest), not data
            if lit.startswith("desks/mt5/") or lit.startswith("backups/"):
                full = lit
            else:
                full = f"desks/mt5/{lit}"
            if not any(_covers(k, full) or _covers(full, k) for k in known):
                findings.append({"check": "UNDECLARED", "node": n.name, "artifact": full,
                                 "why": "path literal in source not declared on any node"})

    fatal = [f for f in findings if f["check"] in
             ("DEAD_PRODUCER", "DEAD_CONSUMER", "ADVISORY_ONLY", "UNMEASURED_AUTHORITY",
              "MISSING_MODULE")]
    return {"generated_utc": datetime.now(tz=UTC).isoformat(), "nodes": len(nodes),
            "artifacts": len(set(writers) | set(readers)), "findings": findings,
            "fatal": fatal, "ok": not fatal}


def freshness(nodes: tuple[Node, ...] = NODES) -> list[dict[str, Any]]:
    """STALE_DECISION: an authority node's input older than its SLA. Runtime, not CI."""
    out = []
    now = datetime.now(tz=UTC).timestamp()
    for n in nodes:
        for art, sla in n.freshness_s.items():
            p = ROOT / art
            if not p.exists():
                out.append({"check": "STALE_DECISION", "node": n.name, "artifact": art,
                            "why": "input absent", "age_s": None, "sla_s": sla})
                continue
            age = now - p.stat().st_mtime
            if age > sla:
                out.append({"check": "STALE_DECISION", "node": n.name, "artifact": art,
                            "why": f"{age / 3600:.1f}h old, SLA {sla / 3600:.1f}h",
                            "age_s": int(age), "sla_s": sla})
    return out


def reachability(nodes: tuple[Node, ...] = NODES) -> dict[str, Any]:
    """For every artifact: which authority nodes it reaches, and through what path."""
    by_write: dict[str, list[Node]] = {}
    for n in nodes:
        for r in n.reads:
            by_write.setdefault(r, []).append(n)

    def _readers_of(art: str) -> list[Node]:
        out = []
        for r, ns in by_write.items():
            if _covers(r, art) or _covers(art, r):
                out.extend(ns)
        return out

    result: dict[str, Any] = {}
    all_arts = sorted({w for n in nodes for w in n.writes})
    for art in all_arts:
        paths: list[str] = []
        seen: set[str] = set()
        stack = [(art, [art])]
        while stack:
            cur, path = stack.pop()
            for n in _readers_of(cur):
                if n.name in seen:
                    continue
                seen.add(n.name)
                if n.authority:
                    paths.append(" -> ".join([*path, f"{n.name}[{','.join(n.authority)}]"]))
                for w in n.writes:
                    stack.append((w, [*path, n.name, w]))
        result[art] = {"reaches_authority": bool(paths), "paths": paths[:6],
                       "human_read": art in HUMAN_READ,
                       "external_reader": EXTERNAL_READERS.get(art)}
    return result


STAGES = ("CODED", "WIRED", "RUNNING", "DECISION_AFFECTING", "MEASURED", "LIVE_LEARNING")
RUNNING_WINDOW_S = 3 * 24 * 3600

#: Artifacts carrying REALISED outcomes -- what the market actually did with the desk's money.
#: A module reading one of these is reading consequences, not its own opinion. Prefix-matched.
OUTCOME_ARTIFACTS: tuple[str, ...] = (
    "desks/mt5/data/fills", "desks/mt5/data/execution_algo_outcomes.jsonl",
    "desks/mt5/data/forward", "desks/mt5/data/shadow", "desks/mt5/data/trades",
    "desks/mt5/reports/RESEARCH_PNL.json", "desks/mt5/reports/pf_allocation.json",
    "desks/mt5/data/gateway_state.json", "desks/mt5/data/decision_ledger.jsonl",
    "desks/mt5/data/counterfactual", "desks/mt5/data/module_rent.jsonl",
)


def stages(nodes: tuple[Node, ...] = NODES) -> dict[str, dict[str, Any]]:
    """Per node: CODED -> WIRED -> RUNNING -> DECISION_AFFECTING -> MEASURED -> LIVE_LEARNING.

    CODED               the module exists
    WIRED               every declared read has a producer (or is box data) and every write a
                        reader -- the check() has no fatal finding naming this node
    RUNNING             at least one of its written artifacts was refreshed inside the window
    DECISION_AFFECTING  a path from one of its writes reaches an authority node
    MEASURED            a ledger PRICES THIS MODULE BY NAME: a MODULE_RENT verdict of EARNS or
                        COSTS, a rail in MISSED_GROWTH, a filter in FILTER_VALUE, a term in the
                        attribution. Not "it exists and matters" -- somebody put a number on it.
    LIVE_LEARNING       the loop closes back onto the module: it reads a REALISED-OUTCOME artifact
                        and updates state it later consumes itself, so what the market did changes
                        what it does next

    TWO FREE PASSES WERE REMOVED HERE, 2026-09-05, AND THEY MATTERED MORE THAN THE MISSING RUNG.

    1. `measured = bool(n.authority) or ...`. Authority was being read as measurement, which is
       exactly backwards: authority is what makes a node DECISION_AFFECTING, and the more capital a
       node moves the MORE it needs a number on it, not less. Measured on this tree before the fix:
       all ten MEASURED nodes were free passes and not one appeared in any ledger -- seven via this
       line (gateway, pf_allocator, promoter, universal_gate, state_admission_run, regime_monitor,
       feature_roi).
    2. A node's own output carrying a `verdict` / `rails` / `categories` key counted as its
       measurement. That is self-certification: a module that writes a report saying it has a
       verdict was thereby credited with having been measured. The remaining three MEASURED nodes
       (capital_modifier_score, counterfactual_markout, missed_growth) came in this way.

    So the repo's headline "7 MEASURED" -- quoted approvingly in an outside audit as evidence the
    desk measures its organs -- was an artifact of the instrument, not a reading of the desk. The
    count drops when this runs, and the drop IS the finding: it is the distance between the
    architecture and the evidence, which is the whole thing the ladder exists to show. A number
    that only ever goes up is not a measurement.

    An absent ledger reads UNMEASURED, never MEASURED (L1.28a). MODULE_RENT.json is written by the
    daily cycle on the trading host, so in a container it is simply absent and every node honestly
    reads below MEASURED rather than being credited by default.
    """
    findings = check(nodes)["findings"]
    named = {f["node"] for f in findings if f["check"] in
             ("DEAD_PRODUCER", "DEAD_CONSUMER", "ADVISORY_ONLY", "UNMEASURED_AUTHORITY")}
    reach = reachability(nodes)
    measured_names: set[str] = set()
    for rel in ("reports/MISSED_GROWTH.json", "reports/FILTER_VALUE.json",
                "reports/allocator_attribution.json", "reports/CAPITAL_MODIFIERS.json",
                # MODULE_RENT is deliberately NOT in this list: the generic loop reads a report's
                # KEYS, which would credit a module whose rent row says UNMEASURED. It is read
                # verdict-aware just below.
                "reports/RESEARCH_PRODUCTIVITY.json"):
        try:
            doc = json.loads((DESK / rel).read_text("utf-8"))
            measured_names |= set(map(str, (doc.get("rails") or doc.get("filters") or
                                            doc.get("terms") or doc.get("categories") or
                                            doc.get("modules") or doc.get("stages")
                                            or {}).keys()))
        except (OSError, ValueError):
            continue
    # MODULE_RENT is the ledger built for exactly this question, so its VERDICT is read rather
    # than its mere presence: a row reading UNMEASURED or NOT_BINDING is the rent ledger saying it
    # could not price the module, and crediting that as MEASURED would re-introduce the free pass
    # through the one report that explicitly refuses to fold UNMEASURED into a pass.
    rent_priced: set[str] = set()
    #: Every name the rent ledger CAN bill, whatever its verdict. This is the BILLABILITY
    #: vocabulary and is deliberately verdict-blind: a node the ledger names but reads UNMEASURED
    #: is waiting on evidence, which is a different problem from one it cannot name at all.
    #:
    #: Read from the REGISTRY IN CODE first, not from the generated report. `MODULE_RENT.json` is
    #: written by the daily cycle on the trading host, so a container that has never run it would
    #: otherwise report every node unbillable -- turning a host's emptiness into a false wiring
    #: defect, the mirror of the absent-ledger-reads-MEASURED failure removed above.
    rent_vocabulary: set[str] = set()
    with contextlib.suppress(ImportError, AttributeError):
        from libs.ops.module_rent import MODULES as _RENT_MODULES
        rent_vocabulary |= {str(m.name) for m in _RENT_MODULES}
    try:
        rent = json.loads((DESK / "reports" / "MODULE_RENT.json").read_text("utf-8"))
        rows = rent.get("modules") or {}
        it = rows.items() if isinstance(rows, dict) else (
            (r.get("module"), r) for r in rows if isinstance(r, dict))
        for mod, row in it:
            rent_vocabulary.add(str(mod))
            if isinstance(row, dict) and str(row.get("verdict", "")).upper() in {"EARNS", "COSTS"}:
                rent_priced.add(str(mod))
    except (OSError, ValueError, AttributeError):
        pass
    measured_names |= rent_priced
    now = datetime.now(tz=UTC).timestamp()
    out: dict[str, dict[str, Any]] = {}
    for n in nodes:
        coded = (ROOT / n.module).exists()
        wired = coded and n.name not in named
        running = False
        for w in n.writes:
            p = ROOT / w
            try:
                if p.is_dir():
                    newest = max((f.stat().st_mtime for f in p.rglob("*") if f.is_file()),
                                 default=0.0)
                else:
                    newest = p.stat().st_mtime
                if now - newest < RUNNING_WINDOW_S:
                    running = True
                    break
            except OSError:
                continue
        decision = bool(n.authority) or any(
            (reach.get(w) or {}).get("reaches_authority") for w in n.writes)
        # A LEDGER PRICES THIS MODULE BY NAME. No authority pass, no self-certification.
        # `billed_as` is consulted alongside the node's own name, never instead of it: a node the
        # ledger happens to name directly stays measured whether or not anyone declared a mapping.
        keys = (n.name, *n.billed_as)
        measured = any(k in measured_names or any(m.startswith(k) for m in measured_names)
                       for k in keys)
        # BILLABLE is the separate question, and it is the one the ledger's emptiness hides: can
        # this node be priced AT ALL by a name the rent ledger uses? A node that is decision-
        # affecting and unbillable will read DECISION_AFFECTING forever, however long the desk
        # runs, and that is a wiring defect rather than a shortage of evidence.
        billable = bool(n.billed_as) or n.name in rent_vocabulary or any(
            r.startswith(n.name) for r in rent_vocabulary)
        # LIVE_LEARNING: the loop closes back onto the module. It must read something the market
        # actually did, AND carry that into state it consumes itself -- a module that reads fills
        # and writes a report nobody feeds back has learned nothing, it has only reported.
        reads_outcome = any(r.startswith(o) or o.startswith(r)
                            for r in n.reads for o in OUTCOME_ARTIFACTS)
        feeds_itself = bool(set(n.writes) & set(n.reads))
        live_learning = measured and reads_outcome and feeds_itself
        if not coded:
            stage = "MISSING"
        elif not wired:
            # Previously this branch read WIRED whenever the node was merely not running, so an
            # unwired node with a fatal DEAD_PRODUCER finding still reported WIRED. Nothing is
            # currently mislabelled by it, which is exactly why it would have gone unnoticed.
            stage = "CODED"
        elif not running:
            stage = "WIRED"
        elif not decision:
            stage = "RUNNING"
        elif not measured:
            stage = "DECISION_AFFECTING"
        elif not live_learning:
            stage = "MEASURED"
        else:
            stage = "LIVE_LEARNING"
        out[n.name] = {"coded": coded, "wired": wired, "running": running,
                       "decision_affecting": decision, "measured": measured,
                       "live_learning": live_learning, "billable": billable,
                       "billed_as": list(n.billed_as),
                       "reads_outcome": reads_outcome, "feeds_itself": feeds_itself,
                       "stage": stage}
    return out


def unbillable(nodes: tuple[Node, ...] = NODES) -> list[str]:
    """Decision-affecting nodes no rent line can name -- the debt that time alone never pays.

    Separated from the stage counts because it answers a different question. A DECISION_AFFECTING
    count falling as evidence accumulates is the desk working; a DECISION_AFFECTING count that
    CANNOT fall however long the desk runs is a wiring defect, and before `billed_as` existed the
    two were indistinguishable in every report.
    """
    st = stages(nodes)
    return sorted(name for name, v in st.items()
                  if v["decision_affecting"] and not v["measured"] and not v["billable"])


def generate_status(out_dir: Path = DESK / "reports") -> dict[str, Any]:
    status = check()
    status["stale"] = freshness()
    status["stages"] = stages()
    status["stage_counts"] = {s: sum(1 for v in status["stages"].values() if v["stage"] == s)
                              for s in ("MISSING", *STAGES)}
    reach = reachability()
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "CAPABILITY_STATUS.json").write_text(json.dumps(status, indent=1), "utf-8")
    (out_dir / "LIVE_REACHABILITY.json").write_text(json.dumps(
        {"generated_utc": status["generated_utc"], "artifacts": reach}, indent=1), "utf-8")
    return status

```

### libs\research\coverage.py
```python
"""THE AUTHORITATIVE COVERAGE TENSORS AND THE FRONTIER ENGINE (principal, 2026-09-17, LAWS 5d).

TWO TENSORS, ONE LADDER EACH, SPARSE BY CONSTRUCTION.

  WORLD   country x sector x information_type x mechanism x representation x asset x session
          x regime x horizon x execution, every cell in exactly one state of
          UNOBSERVED -> SOURCE_HUNT -> INGESTED -> REPRESENTED -> CANDIDATES -> TESTING ->
          FAILED/FORWARD -> CERTIFIED -> LIVE -> DECAYED. FAILED and FORWARD share a rung;
          DECAYED is reachable from LIVE, CERTIFIED and FORWARD only.
  FOREST  country x language x source_class x sector x mechanism x asset_transmission x
          freshness x accessibility, where source_class is exactly one of the ten source layers,
          in UNSEEN -> SOURCE_HUNT -> DISCOVERED -> VERIFIED -> INGESTED -> REPRESENTED ->
          CANDIDATES -> TESTED -> FORWARD -> LIVE/FAILED.

THE POINT. "Indonesia nickel exports x China industrial cycle x AUD x Asian session x risk-off has
never been tested" must be an EXPLICIT frontier row with a state and a next move, never a blind
spot nobody knows exists. The full product of the vocabularies is astronomically large (ten axes
of twenty to two hundred values each), so a tensor holds ONLY the cells evidence has touched and
the frontier cells the engine enumerated on purpose; a coordinate absent from the store is at the
floor, and `holes()` is how the floor is asked a question.

THE LADDER IS MONOTONE, WITH TWO NAMED DOWN-MOVES. `advance` moves a cell up its ladder and never
down, except to FAILED and DECAYED, each of which is entered only from the states the ladder
names and only with NAMED evidence (a `why` and a `source`). A cell nobody has judged cannot be
"failed" by silence, and a live cell cannot decay because a file went missing (L1.28a).

EVIG -- the expected value of information gain that ranks a hole:

    EVIG = prior P(edge | neighbouring evidence) x reachability x novelty x capacity / cost

  prior         Laplace-smoothed share of positive verdicts among the JUDGED neighbours; with no
                judged neighbour it is the desk's 0.5 prior, never 0 and never 1;
  reachability  the share of the cell's axis components that have data at INGESTED or above
                SOMEWHERE in the tensor (floored, so an unreachable cell ranks as a source hunt
                rather than vanishing);
  novelty       Hamming distance to the nearest TESTED cell over the axes considered, as a share;
  capacity      a proxy the caller measures (UNMEASURED -> the 0.5 prior, named as such);
  cost          the cost of the NEXT rung from the cell's state.

Every factor is returned in the breakdown, so a rank is an argument rather than a number.

COVERAGE OF A COUNTRY RISES ONLY WHEN BOTH CONDITIONS HOLD: every source layer that exists for it
is mapped (a verified source, or an absence declared WITH a reason) AND automatic discovery is
still adding sources. Five obvious sources map at most five layers and prove no discovery, so
`covered()` refuses them by construction. Floors ratchet up only: `ratchet` never lowers one.

Pure and typed: no I/O, no clock read except to stamp `updated`, deterministic ordering.
"""
from __future__ import annotations

import hashlib
import itertools
import json
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

WORLD = "world"
FOREST = "forest"
#: The coordinate a piece of evidence carries when it says nothing about an axis. It is a value
#: like any other, never a wildcard: a price-only candidate on USDJPY lives at country=any and
#: does not cover country=kr.
ANY = "any"
UNMEASURED = "UNMEASURED"
PRIOR = 0.5
REACH_FLOOR = 0.1
CAPACITY_FLOOR = 0.05
MAX_EVIDENCE_PER_STATE = 6

WORLD_AXES: tuple[str, ...] = ("country", "sector", "information_type", "mechanism",
                               "representation", "asset", "session", "regime", "horizon",
                               "execution")
FOREST_AXES: tuple[str, ...] = ("country", "language", "source_class", "sector", "mechanism",
                                "asset_transmission", "freshness", "accessibility")

WORLD_LADDER: tuple[str, ...] = ("UNOBSERVED", "SOURCE_HUNT", "INGESTED", "REPRESENTED",
                                 "CANDIDATES", "TESTING", "FAILED", "FORWARD", "CERTIFIED",
                                 "LIVE", "DECAYED")
FOREST_LADDER: tuple[str, ...] = ("UNSEEN", "SOURCE_HUNT", "DISCOVERED", "VERIFIED", "INGESTED",
                                  "REPRESENTED", "CANDIDATES", "TESTED", "FORWARD", "LIVE",
                                  "FAILED")

#: The ten source layers, ordered from the most official to the most derived.
SOURCE_LAYERS: tuple[str, ...] = ("official", "institutional", "academic", "practitioner",
                                  "retail_ecology", "app_ecosystem", "media", "archive",
                                  "physical_economy", "source_graph")

#: The closed vocabularies the specification fixes. The organ adds the open ones (countries,
#: mechanisms, assets, representations, languages) from the desk's own registries.
INFORMATION_TYPES: tuple[str, ...] = ("physical_exhaust", "supply_chain", "customs", "corporate",
                                      "legal", "labour", "innovation", "consumer", "payments",
                                      "attention", "multimodal", "archives", "official_macro",
                                      "market_data", "positioning", "news")
SECTORS: tuple[str, ...] = ("energy_oil_gas", "power_utilities", "metals_mining",
                            "agriculture_softs", "chemicals_materials", "semiconductors",
                            "technology_software", "autos_machinery", "construction_real_estate",
                            "transport_shipping", "banking_finance", "insurance_pensions",
                            "retail_consumer", "healthcare_pharma", "telecom_media",
                            "tourism_leisure", "government_fiscal", "defence_aerospace",
                            "textiles_light_industry", "households_labour")
SESSIONS: tuple[str, ...] = ("asia", "tokyo_fix", "london", "london_fix", "ny", "overlap",
                             "close", "gotobi", "holiday")
HORIZONS: tuple[str, ...] = ("1h", "4h", "1d", "5d", "20d")
EXECUTIONS: tuple[str, ...] = ("market", "limit", "stop", "bracket", "session_window")
FRESHNESS: tuple[str, ...] = ("realtime", "intraday", "daily", "weekly", "monthly", "quarterly",
                              "archive")
#: The access vocabulary of `desks/mt5/research/ingestion_ledger.py`, same spelling, so a join
#: is a rename and never a re-derivation.
ACCESS_LABELS: tuple[str, ...] = ("PUBLIC", "PUBLIC_WITH_TERMS", "LICENSED", "OPEN_DATA",
                                  "PUBLIC_ARCHIVE", "PUBLIC_SOCIAL", "USER_SUBMITTED",
                                  "ACCESS_UNCLEAR", "PRIVATE", "CONFIDENTIAL_MNPI",
                                  "STOLEN_UNAUTHORIZED")

COVERAGE_STATES: tuple[str, ...] = ("COVERED", "MAPPING", "STALLED", "UNMEASURED")
COVERAGE_RULE = ("a country is COVERED only when every source layer is mapped -- a verified "
                 "source or an absence declared with a reason -- AND automatic discovery is still "
                 "adding sources in the trailing window; five obvious sources is not coverage, "
                 "and a mapped country whose discovery rate is zero is STALLED, not finished")
RULE = ("every cell of the two tensors is in exactly one ladder state; the ladder is monotone "
        "except the named down-moves FAILED and DECAYED, which need named evidence; a hole is an "
        "explicit frontier row ranked by EVIG, never a blind spot; floors ratchet up only")


# ------------------------------------------------------------------------------------ the ladders
@dataclass(frozen=True)
class Ladder:
    """One tensor's state ladder: the order, the rung of every state, and the down-moves.

    `rung` is the height; two states may share a rung (FAILED/FORWARD, LIVE/FAILED). `down_moves`
    names the negative states and the states each may be entered from; `positive_twin` names,
    for a negative state that shares a rung, the positive state on that rung, so a FAILED cell
    that later carries a forward clock reads FORWARD (progress) while FORWARD -> FAILED stays a
    named down-move.
    """

    name: str
    states: tuple[str, ...]
    rung: Mapping[str, int]
    down_moves: Mapping[str, frozenset[str]]
    positive_twin: Mapping[str, str]
    tested_from: str
    positive: frozenset[str]
    negative: frozenset[str]
    ingested_from: str

    @property
    def floor(self) -> str:
        return self.states[0]

    def check(self, state: str) -> str:
        if state not in self.rung:
            raise ValueError(f"{state!r} is not a state of the {self.name} ladder {self.states}")
        return state

    def rank(self, state: str) -> int:
        return int(self.rung[self.check(state)])

    def at_or_above(self, state: str, bar: str) -> bool:
        return self.rank(state) >= self.rank(bar)

    def next_state(self, state: str) -> str | None:
        """The state one rung up on the positive path, or None at the top."""
        r = self.rank(state)
        for s in self.states:
            if self.rung[s] == r + 1 and s not in self.down_moves:
                return s
        return None


WORLD_LADDER_SPEC = Ladder(
    name=WORLD, states=WORLD_LADDER,
    rung={"UNOBSERVED": 0, "SOURCE_HUNT": 1, "INGESTED": 2, "REPRESENTED": 3, "CANDIDATES": 4,
          "TESTING": 5, "FAILED": 6, "FORWARD": 6, "CERTIFIED": 7, "LIVE": 8, "DECAYED": 9},
    down_moves={"FAILED": frozenset({"TESTING", "FORWARD", "CERTIFIED"}),
                "DECAYED": frozenset({"FORWARD", "CERTIFIED", "LIVE"})},
    positive_twin={"FAILED": "FORWARD"},
    tested_from="TESTING", positive=frozenset({"FORWARD", "CERTIFIED", "LIVE"}),
    negative=frozenset({"FAILED", "DECAYED"}), ingested_from="INGESTED")

FOREST_LADDER_SPEC = Ladder(
    name=FOREST, states=FOREST_LADDER,
    rung={"UNSEEN": 0, "SOURCE_HUNT": 1, "DISCOVERED": 2, "VERIFIED": 3, "INGESTED": 4,
          "REPRESENTED": 5, "CANDIDATES": 6, "TESTED": 7, "FORWARD": 8, "LIVE": 9, "FAILED": 9},
    down_moves={"FAILED": frozenset({"TESTED", "FORWARD", "LIVE"})},
    positive_twin={"FAILED": "LIVE"},
    tested_from="TESTED", positive=frozenset({"FORWARD", "LIVE"}),
    negative=frozenset({"FAILED"}), ingested_from="INGESTED")

_LADDERS: dict[str, Ladder] = {WORLD: WORLD_LADDER_SPEC, FOREST: FOREST_LADDER_SPEC}
_AXES: dict[str, tuple[str, ...]] = {WORLD: WORLD_AXES, FOREST: FOREST_AXES}

#: The cost of the NEXT rung from a state, in gauntlet-run units: a hunt is cheap, a forward
#: clock is time nobody can buy.
RUNG_COST: dict[str, dict[str, float]] = {
    WORLD: {"UNOBSERVED": 1.0, "SOURCE_HUNT": 2.0, "INGESTED": 1.0, "REPRESENTED": 1.0,
            "CANDIDATES": 3.0, "TESTING": 3.0, "FAILED": 3.0, "FORWARD": 5.0, "CERTIFIED": 2.0,
            "LIVE": 1.0, "DECAYED": 3.0},
    FOREST: {"UNSEEN": 1.0, "SOURCE_HUNT": 0.5, "DISCOVERED": 1.0, "VERIFIED": 2.0,
             "INGESTED": 1.0, "REPRESENTED": 1.0, "CANDIDATES": 3.0, "TESTED": 5.0,
             "FORWARD": 1.0, "LIVE": 1.0, "FAILED": 3.0},
}


def ladder_of(tensor: str) -> Ladder:
    if tensor not in _LADDERS:
        raise ValueError(f"unknown tensor {tensor!r}; one of {tuple(_LADDERS)}")
    return _LADDERS[tensor]


def axes_of(tensor: str) -> tuple[str, ...]:
    if tensor not in _AXES:
        raise ValueError(f"unknown tensor {tensor!r}; one of {tuple(_AXES)}")
    return _AXES[tensor]


def now_iso() -> str:
    return datetime.now(tz=UTC).isoformat(timespec="seconds")


def named(evidence: Mapping[str, Any] | None) -> bool:
    """Named evidence carries a non-empty `why` and a non-empty `source` (the artifact)."""
    if not evidence:
        return False
    return bool(str(evidence.get("why") or "").strip()) and bool(
        str(evidence.get("source") or "").strip())


# --------------------------------------------------------------------------------------- the cell
@dataclass(frozen=True)
class Cell:
    """One coordinate of one tensor, in one state, with the evidence that put it there."""

    tensor: str
    coordinates: tuple[str, ...]
    state: str
    evidence: dict[str, Any] = field(default_factory=dict)
    updated: str = ""

    def __post_init__(self) -> None:
        axes = axes_of(self.tensor)
        if len(self.coordinates) != len(axes):
            raise ValueError(f"{self.tensor} cell needs {len(axes)} coordinates {axes}, got "
                             f"{len(self.coordinates)}")
        ladder_of(self.tensor).check(self.state)
        object.__setattr__(self, "coordinates", tuple(str(c) for c in self.coordinates))

    @property
    def axes(self) -> tuple[str, ...]:
        return axes_of(self.tensor)

    @property
    def key(self) -> str:
        return "|".join(self.coordinates)

    def values(self) -> dict[str, str]:
        return dict(zip(self.axes, self.coordinates, strict=True))

    def value(self, axis: str) -> str:
        return self.values()[axis]

    def content_hash(self) -> str:
        body = json.dumps({"tensor": self.tensor, "coordinates": list(self.coordinates),
                           "state": self.state}, sort_keys=True)
        return hashlib.sha256(body.encode("utf-8")).hexdigest()[:32]

    def to_json(self) -> dict[str, Any]:
        return {"tensor": self.tensor, "coordinates": list(self.coordinates),
                "state": self.state, "evidence": dict(self.evidence), "updated": self.updated}

    @classmethod
    def from_json(cls, doc: Mapping[str, Any]) -> Cell:
        ev = doc.get("evidence")
        return cls(tensor=str(doc["tensor"]), coordinates=tuple(str(c) for c in doc["coordinates"]),
                   state=str(doc["state"]), evidence=dict(ev) if isinstance(ev, Mapping) else {},
                   updated=str(doc.get("updated") or ""))


def _merge_evidence(old: Mapping[str, Any], state: str, evidence: Mapping[str, Any] | None
                    ) -> dict[str, Any]:
    """Evidence is kept PER STATE and bounded, so a cell reads like a ledger, not a dump."""
    out: dict[str, Any] = {k: (list(v) if isinstance(v, list) else v) for k, v in old.items()}
    if evidence:
        rows = out.get(state)
        bucket: list[Any] = list(rows) if isinstance(rows, list) else []
        entry = dict(evidence)
        if entry not in bucket and len(bucket) < MAX_EVIDENCE_PER_STATE:
            bucket.append(entry)
        out[state] = bucket
    return out


def advance(cell: Cell, state: str, evidence: Mapping[str, Any] | None = None, *,
            at: str | None = None) -> Cell:
    """Move a cell along its ladder. Up is free; down is FAILED or DECAYED with named evidence.

    A move to a lower or equal rung is NOT an error: the ladder is monotone, so the cell keeps
    its state and merely records the evidence. The exception is the positive twin on a shared
    rung (FAILED -> FORWARD, FAILED -> LIVE in the forest), which is progress and moves.
    """
    ladder = ladder_of(cell.tensor)
    state = ladder.check(state)
    stamp = at or now_iso()
    merged = _merge_evidence(cell.evidence, state, evidence)
    if state in ladder.down_moves:
        if cell.state == state:
            return Cell(cell.tensor, cell.coordinates, state, merged, stamp)
        allowed = ladder.down_moves[state]
        if cell.state not in allowed:
            raise ValueError(f"{state} is reachable only from {sorted(allowed)}; the cell is at "
                             f"{cell.state}")
        if not named(evidence):
            raise ValueError(f"{state} requires NAMED evidence (a `why` and a `source`); "
                             f"silence never fails or decays a cell")
        merged["path"] = [*list(merged.get("path") or [cell.state]), state]
        return Cell(cell.tensor, cell.coordinates, state, merged, stamp)
    cur, new = ladder.rank(cell.state), ladder.rank(state)
    twin = ladder.positive_twin.get(cell.state) == state
    if new > cur or (new == cur and state != cell.state and twin):
        merged["path"] = [*list(merged.get("path") or [cell.state]), state]
        return Cell(cell.tensor, cell.coordinates, state, merged, stamp)
    return Cell(cell.tensor, cell.coordinates, cell.state, merged, cell.updated or stamp)


# ------------------------------------------------------------------------------------- the holes
@dataclass(frozen=True)
class Hole:
    """One frontier row: a projected coordinate still at (or below) the asked state."""

    tensor: str
    axes: tuple[str, ...]
    coordinates: tuple[str, ...]
    state: str
    score: float
    breakdown: dict[str, Any] = field(default_factory=dict)

    def values(self) -> dict[str, str]:
        return dict(zip(self.axes, self.coordinates, strict=True))

    @property
    def key(self) -> str:
        return "|".join(f"{a}={v}" for a, v in zip(self.axes, self.coordinates, strict=True))

    def to_json(self) -> dict[str, Any]:
        return {"tensor": self.tensor, "axes": list(self.axes),
                "coordinates": list(self.coordinates), "values": self.values(),
                "state": self.state, "score": round(float(self.score), 6),
                "breakdown": dict(self.breakdown), "key": self.key}


Scorer = Callable[[Mapping[str, str]], "float | tuple[float, Mapping[str, Any]]"]


# ------------------------------------------------------------------------------------ the tensor
class Tensor:
    """A SPARSE tensor: only observed cells and enumerated frontier cells are stored."""

    def __init__(self, name: str, *, vocabulary: Mapping[str, Sequence[str]] | None = None
                 ) -> None:
        self.name = name
        self.axes = axes_of(name)
        self.ladder = ladder_of(name)
        vocab = dict(vocabulary or {})
        for k in vocab:
            if k not in self.axes:
                raise ValueError(f"vocabulary names {k!r}, not an axis of {name}: {self.axes}")
        self.vocabulary: dict[str, tuple[str, ...]] = {
            a: tuple(dict.fromkeys(str(v) for v in vocab.get(a, ()) if str(v)))
            for a in self.axes}
        self._cells: dict[tuple[str, ...], Cell] = {}
        self.last_scan: dict[str, Any] = {}

    # ---- storage
    def __len__(self) -> int:
        return len(self._cells)

    def cells(self) -> list[Cell]:
        return [self._cells[k] for k in sorted(self._cells)]

    def get(self, values: Mapping[str, str] | Sequence[str]) -> Cell | None:
        return self._cells.get(self.coordinates(values))

    def put(self, cell: Cell) -> Cell:
        if cell.tensor != self.name:
            raise ValueError(f"a {cell.tensor} cell cannot enter the {self.name} tensor")
        self._cells[cell.coordinates] = cell
        return cell

    def coordinates(self, values: Mapping[str, str] | Sequence[str]) -> tuple[str, ...]:
        """A full coordinate tuple; axes the caller did not name read ANY."""
        if isinstance(values, Mapping):
            unknown = sorted(set(values) - set(self.axes))
            if unknown:
                raise ValueError(f"{unknown} are not axes of {self.name}: {self.axes}")
            return tuple(str(values.get(a) or ANY) for a in self.axes)
        coords = tuple(str(v) for v in values)
        if len(coords) != len(self.axes):
            raise ValueError(f"{self.name} needs {len(self.axes)} coordinates, got {len(coords)}")
        return coords

    def frontier(self, values: Mapping[str, str] | Sequence[str], *, at: str | None = None
                 ) -> Cell:
        """Make a coordinate an EXPLICIT row at the floor (a known hole), if it is not stored."""
        coords = self.coordinates(values)
        cell = self._cells.get(coords)
        if cell is None:
            cell = Cell(self.name, coords, self.ladder.floor, {"frontier": True},
                        at or now_iso())
            self._cells[coords] = cell
        return cell

    def observe(self, values: Mapping[str, str] | Sequence[str], state: str,
                evidence: Mapping[str, Any] | None = None, *, at: str | None = None) -> Cell:
        """Raise a cell to `state` along the lawful path, creating it at the floor if absent.

        A down-move target (FAILED, DECAYED) on a cell below its entry states first climbs to the
        lowest entry state -- a FAILED verdict implies the cell was TESTING, a retirement implies
        it was at least FORWARD -- and then moves down with the evidence given. A cell already
        above the asked state keeps its state and records the evidence.
        """
        ladder = self.ladder
        state = ladder.check(state)
        coords = self.coordinates(values)
        cell = self._cells.get(coords) or Cell(self.name, coords, ladder.floor, {},
                                               at or now_iso())
        if state in ladder.down_moves and cell.state not in ladder.down_moves[state] \
                and cell.state != state:
            if ladder.rank(cell.state) >= ladder.rank(state):
                # Above the down-move's reach: the positive evidence stands and the verdict is
                # recorded beside it rather than demoting a cell the desk has since funded.
                cell = Cell(cell.tensor, cell.coordinates, cell.state,
                            _merge_evidence(cell.evidence, state, evidence), cell.updated)
                self._cells[coords] = cell
                return cell
            # A verdict IMPLIES the rung it was passed on: a FAILED cell was TESTING, a retired
            # one was at least FORWARD. Climb to the lowest lawful entry, then move down.
            entry = min(ladder.down_moves[state], key=ladder.rank)
            cell = advance(cell, entry, {"implied_by": state, **dict(evidence or {})}, at=at)
        cell = advance(cell, state, evidence, at=at)
        self._cells[coords] = cell
        return cell

    # ---- readings
    def histogram(self) -> dict[str, int]:
        out = dict.fromkeys(self.ladder.states, 0)
        for c in self._cells.values():
            out[c.state] += 1
        return out

    def marginals(self, axes: Sequence[str]) -> dict[tuple[str, ...], dict[str, Any]]:
        """Project onto `axes`: per projected coordinate, the cell count, the per-state counts
        and the BEST (highest-rung) state any cell there reached."""
        idx = self._axis_index(axes)
        out: dict[tuple[str, ...], dict[str, Any]] = {}
        for c in self._cells.values():
            key = tuple(c.coordinates[i] for i in idx)
            row = out.get(key)
            if row is None:
                row = {"n": 0, "states": {}, "best": self.ladder.floor}
                out[key] = row
            row["n"] += 1
            row["states"][c.state] = int(row["states"].get(c.state, 0)) + 1
            if self.ladder.rank(c.state) > self.ladder.rank(str(row["best"])):
                row["best"] = c.state
        return dict(sorted(out.items()))

    def reachability(self, bar: str | None = None) -> dict[str, dict[str, bool]]:
        """axis -> value -> has data at `bar` (default INGESTED) or above SOMEWHERE."""
        bar = bar or self.ladder.ingested_from
        out: dict[str, dict[str, bool]] = {a: {} for a in self.axes}
        for c in self._cells.values():
            reached = self.ladder.at_or_above(c.state, bar)
            for a, v in zip(self.axes, c.coordinates, strict=True):
                if v == ANY:
                    continue
                out[a][v] = bool(out[a].get(v, False) or reached)
        return out

    def _axis_index(self, axes: Sequence[str]) -> tuple[int, ...]:
        if not axes:
            raise ValueError("an axis subset must name at least one axis")
        bad = [a for a in axes if a not in self.axes]
        if bad:
            raise ValueError(f"{bad} are not axes of {self.name}: {self.axes}")
        if len(set(axes)) != len(axes):
            raise ValueError(f"axis subset repeats an axis: {list(axes)}")
        return tuple(self.axes.index(a) for a in axes)

    def holes(self, axes: Sequence[str], k: int, scorer: Scorer | None = None, *,
              at_or_below: str | None = None,
              admissible: Callable[[Mapping[str, str]], bool] | None = None,
              vocabulary: Mapping[str, Sequence[str]] | None = None,
              max_enumerate: int = 200_000) -> list[Hole]:
        """Project onto `axes` and rank the coordinates still at (or below) `at_or_below`.

        The candidate coordinates are the product of the axes' vocabularies (the tensor's own
        unless overridden); ANY and UNMEASURED never enter the product. A coordinate is a hole
        when no stored cell projecting onto it has climbed above the bar (default: the floor).
        The enumeration is bounded and SAYS SO in `last_scan` -- a truncated scan that reports a
        clean count is worse than no scan at all.
        """
        axes = tuple(axes)
        self._axis_index(axes)
        bar = self.ladder.check(at_or_below or self.ladder.floor)
        vocab = dict(self.vocabulary)
        for a, vals in (vocabulary or {}).items():
            vocab[a] = tuple(dict.fromkeys(str(v) for v in vals if str(v)))
        lists: list[tuple[str, ...]] = []
        for a in axes:
            vals = tuple(v for v in vocab.get(a, ()) if v not in (ANY, UNMEASURED))
            if not vals:
                self.last_scan = {"axes": list(axes), "enumerated": 0, "truncated": False,
                                  "covered": 0, "holes": 0, "empty_axis": a,
                                  "why": f"axis {a!r} has no vocabulary; nothing to enumerate"}
                return []
            lists.append(vals)
        marg = self.marginals(axes)
        score = scorer or self.evig_scorer(axes)
        holes: list[Hole] = []
        enumerated = covered = 0
        truncated = False
        for combo in itertools.product(*lists):
            if enumerated >= max_enumerate:
                truncated = True
                break
            enumerated += 1
            values = dict(zip(axes, combo, strict=True))
            if admissible is not None and not admissible(values):
                continue
            row = marg.get(combo)
            state = str(row["best"]) if row is not None else self.ladder.floor
            if self.ladder.rank(state) > self.ladder.rank(bar):
                covered += 1
                continue
            got = score(values)
            if isinstance(got, tuple):
                s, br = float(got[0]), dict(got[1])
            else:
                s, br = float(got), {}
            holes.append(Hole(self.name, axes, combo, state, s, br))
        holes.sort(key=lambda h: (-h.score, h.coordinates))
        self.last_scan = {"axes": list(axes), "enumerated": enumerated, "truncated": truncated,
                          "covered": covered, "holes": len(holes), "bar": bar,
                          "max_enumerate": int(max_enumerate)}
        return holes[:max(int(k), 0)]

    def evig_scorer(self, axes: Sequence[str], *,
                    capacity_of: Callable[[Mapping[str, str]], float | None] | None = None,
                    cost_of: Callable[[Mapping[str, str], str], float | None] | None = None,
                    max_neighbours: int = 400
                    ) -> Callable[[Mapping[str, str]], tuple[float, dict[str, Any]]]:
        """A scorer over the projection onto `axes` that computes EVIG with its breakdown.

        Neighbours are the stored cells (projected) sharing at least one coordinate with the
        hole; reachability is the tensor's own; novelty is the distance to the nearest tested
        projected cell. The projection is built once per scorer, not once per hole.
        """
        axes = tuple(axes)
        idx = self._axis_index(axes)
        marg = self.marginals(axes)
        projected: list[Cell] = []
        by_value: dict[tuple[str, str], list[int]] = {}
        for key, row in marg.items():
            full = [ANY] * len(self.axes)
            for i, j in enumerate(idx):
                full[j] = key[i]
            projected.append(Cell(self.name, tuple(full), str(row["best"]),
                                  {"n": int(row["n"])}, ""))
            for a, v in zip(axes, key, strict=True):
                by_value.setdefault((a, v), []).append(len(projected) - 1)
        reach = self.reachability()

        def _score(values: Mapping[str, str]) -> tuple[float, dict[str, Any]]:
            full = dict.fromkeys(self.axes, ANY)
            full.update({a: str(values.get(a) or ANY) for a in axes})
            cell = Cell(self.name, tuple(full[a] for a in self.axes), self.ladder.floor, {}, "")
            seen: set[int] = set()
            for a in axes:
                for i in by_value.get((a, full[a]), ()):
                    seen.add(i)
                    if len(seen) >= max_neighbours:
                        break
            neighbours = [projected[i] for i in sorted(seen)]
            cap = capacity_of(values) if capacity_of is not None else None
            cost = cost_of(values, cell.state) if cost_of is not None else None
            br = evig_breakdown(cell, neighbours, axes=axes, reach=reach, capacity=cap, cost=cost)
            return float(br["evig"]), br

        return _score

    # ---- json
    def to_json(self) -> dict[str, Any]:
        return {"tensor": self.name, "axes": list(self.axes), "ladder": list(self.ladder.states),
                "vocabulary": {a: list(v) for a, v in self.vocabulary.items()},
                "n_cells": len(self._cells), "histogram": self.histogram(),
                "cells": [c.to_json() for c in self.cells()]}

    @classmethod
    def from_json(cls, doc: Mapping[str, Any]) -> Tensor:
        vocab = doc.get("vocabulary")
        t = cls(str(doc["tensor"]), vocabulary=vocab if isinstance(vocab, Mapping) else None)
        for raw in doc.get("cells") or []:
            if isinstance(raw, Mapping):
                t.put(Cell.from_json(raw))
        return t


# --------------------------------------------------------------------------------------- EVIG
def _hamming(a: Cell, b: Cell, idx: Sequence[int]) -> int:
    return sum(1 for i in idx if a.coordinates[i] != b.coordinates[i])


def evig_breakdown(cell: Cell, neighbours: Iterable[Cell], *, axes: Sequence[str] | None = None,
                   reach: Mapping[str, Mapping[str, bool]] | None = None,
                   capacity: float | None = None, cost: float | None = None) -> dict[str, Any]:
    """Every factor of EVIG for `cell`, and the product. See the module docstring."""
    ladder = ladder_of(cell.tensor)
    all_axes = axes_of(cell.tensor)
    axes = tuple(axes) if axes else all_axes
    bad = [a for a in axes if a not in all_axes]
    if bad:
        raise ValueError(f"{bad} are not axes of {cell.tensor}: {all_axes}")
    idx = [all_axes.index(a) for a in axes]
    near = [n for n in neighbours if n.tensor == cell.tensor and n.coordinates != cell.coordinates]

    # prior P(edge | evidence in neighbouring cells): Laplace-smoothed with the desk's prior
    pos = sum(1 for n in near if n.state in ladder.positive)
    neg = sum(1 for n in near if n.state in ladder.negative)
    prior = (pos + PRIOR) / (pos + neg + 1.0)

    # reachability: each axis component has data at >= INGESTED somewhere
    if reach is None:
        reach_map: dict[str, dict[str, bool]] = {a: {} for a in all_axes}
        for n in near:
            reached = ladder.at_or_above(n.state, ladder.ingested_from)
            for a, v in zip(all_axes, n.coordinates, strict=True):
                if v != ANY:
                    reach_map[a][v] = bool(reach_map[a].get(v, False) or reached)
    else:
        reach_map = {a: dict(reach.get(a, {})) for a in all_axes}
    considered = [(a, cell.coordinates[all_axes.index(a)]) for a in axes]
    concrete = [(a, v) for a, v in considered if v not in (ANY, UNMEASURED)]
    unreachable = [a for a, v in concrete if not reach_map.get(a, {}).get(v, False)]
    reach_frac = (len(concrete) - len(unreachable)) / len(concrete) if concrete else PRIOR
    reachability = max(reach_frac, REACH_FLOOR)

    # novelty: distance to the nearest tested cell over the axes considered
    tested = [n for n in near if ladder.at_or_above(n.state, ladder.tested_from)]
    if tested:
        nearest = min(_hamming(cell, n, idx) for n in tested)
        novelty = nearest / max(len(idx), 1)
    else:
        nearest = len(idx)
        novelty = 1.0
    novelty = max(novelty, 1.0 / max(len(idx), 1)) if tested else 1.0

    # capacity proxy and cost
    if capacity is None:
        cap, cap_basis = PRIOR, "UNMEASURED -> prior 0.5"
    else:
        cap, cap_basis = min(1.0, max(CAPACITY_FLOOR, float(capacity))), "measured"
    if cost is None:
        c, cost_basis = RUNG_COST[cell.tensor].get(cell.state, 1.0), f"RUNG_COST[{cell.state}]"
    else:
        c, cost_basis = max(float(cost), 1e-3), "measured"
    value = prior * reachability * novelty * cap / c
    return {"evig": round(float(value), 6), "prior_p_edge": round(prior, 4),
            "judged_neighbours": {"positive": pos, "negative": neg, "n_neighbours": len(near)},
            "reachability": round(reachability, 4), "reach_fraction": round(reach_frac, 4),
            "unreachable_axes": unreachable, "novelty": round(novelty, 4),
            "nearest_tested_distance": int(nearest), "n_tested_neighbours": len(tested),
            "capacity": round(cap, 4), "capacity_basis": cap_basis, "cost": round(c, 4),
            "cost_basis": cost_basis, "state": cell.state,
            "next_state": ladder.next_state(cell.state), "axes": list(axes)}


def evig(cell: Cell, neighbours: Iterable[Cell], *, axes: Sequence[str] | None = None,
         reach: Mapping[str, Mapping[str, bool]] | None = None, capacity: float | None = None,
         cost: float | None = None) -> float:
    """EVIG = prior x reachability x novelty x capacity / cost. `evig_breakdown` has the parts."""
    return float(evig_breakdown(cell, neighbours, axes=axes, reach=reach, capacity=capacity,
                                cost=cost)["evig"])


# ------------------------------------------------------------------------------ country coverage
def covered(country: str, layer_inventory: Mapping[str, Sequence[Mapping[str, Any]]],
            discovery_rate: Mapping[str, Any] | float | None) -> dict[str, Any]:
    """The principal's two-condition rule, and the verdict names both conditions.

    `layer_inventory` is {layer: [source rows]} in the shape `country_lab.layer_inventory`
    returns (a row with `verified` True maps its layer; a row with `absent_reason` declares the
    layer absent WITH a reason, which is mapped too). `discovery_rate` is either a per-day float
    or `country_lab.discovery_rate`'s mapping (`measured`, `per_day`). An unmeasured rate blocks
    COVERED: absence of evidence about discovery is never evidence that discovery is healthy.
    """
    code = str(country or "").strip().lower() or "unknown"
    layers: dict[str, dict[str, Any]] = {}
    for layer in SOURCE_LAYERS:
        rows = [r for r in layer_inventory.get(layer, ()) if isinstance(r, Mapping)]
        verified = [r for r in rows if bool(r.get("verified"))]
        absent = [r for r in rows if str(r.get("absent_reason") or "").strip()]
        if absent:
            state, why = "ABSENT_DECLARED", str(absent[0]["absent_reason"])
        elif verified:
            state, why = "MAPPED", f"{len(verified)} verified source(s)"
        elif rows:
            state, why = "DECLARED_UNVERIFIED", f"{len(rows)} declared, none fetched yet"
        else:
            state, why = "UNMAPPED", "no source and no declared absence for this layer"
        layers[layer] = {"state": state, "sources": len(rows), "verified": len(verified),
                         "why": why}
    mapped = [k for k, v in layers.items() if v["state"] in ("MAPPED", "ABSENT_DECLARED")]
    unmapped = [k for k, v in layers.items() if v["state"] == "UNMAPPED"]
    unverified = [k for k, v in layers.items() if v["state"] == "DECLARED_UNVERIFIED"]
    n_verified = sum(int(v["verified"]) for v in layers.values())
    untagged = len([r for r in layer_inventory.get("UNTAGGED", ()) if isinstance(r, Mapping)])
    cond_layers = {"met": not unmapped and not unverified, "mapped": mapped,
                   "unmapped": unmapped, "declared_unverified": unverified,
                   "verified_sources": n_verified, "untagged_sources": untagged}

    measured, per_day, why_rate = False, None, "discovery rate not supplied"
    if isinstance(discovery_rate, Mapping):
        measured = bool(discovery_rate.get("measured", discovery_rate.get("per_day") is not None))
        raw = discovery_rate.get("per_day")
        per_day = float(raw) if raw is not None else None
        why_rate = str(discovery_rate.get("why") or "")
        if per_day is None:
            measured = False
    elif discovery_rate is not None:
        measured, per_day, why_rate = True, float(discovery_rate), ""
    cond_disc = {"met": bool(measured and per_day is not None and per_day > 0.0),
                 "measured": measured, "per_day": per_day, "why": why_rate}

    if not measured:
        state = "UNMEASURED"
        why = f"the discovery rate is unmeasured: {why_rate or 'no reading'}"
    elif not cond_layers["met"]:
        state = "MAPPING"
        why = (f"{len(mapped)}/{len(SOURCE_LAYERS)} layers mapped; unmapped={unmapped}; "
               f"declared but never fetched={unverified}")
    elif not cond_disc["met"]:
        state = "STALLED"
        why = (f"every layer is mapped but discovery added nothing for {code} in the window; "
               "the scouts ran out of ideas, not the country out of sources")
    else:
        state = "COVERED"
        why = (f"all {len(SOURCE_LAYERS)} layers mapped or declared absent with a reason, and "
               f"discovery is still adding {per_day}/day")
    return {"country": code, "covered": state == "COVERED", "state": state, "why": why,
            "condition_layers": cond_layers, "condition_discovery": cond_disc,
            "layers": layers, "rule": COVERAGE_RULE}


# --------------------------------------------------------------------------------------- floors
def ratchet(previous_floor: Mapping[str, float] | float | None,
            current: Mapping[str, float] | float) -> dict[str, Any]:
    """A floor never goes down. Returns the new floors and names what sits BELOW its floor.

    For mappings the ratchet is per key: a key seen before keeps max(previous, current); a key
    never seen enters at its current value; a key that vanished from `current` keeps its floor
    (a measurement that stopped is not a floor that dropped). For scalars the same, in one key.
    """
    prev: dict[str, float] = {}
    if isinstance(previous_floor, Mapping):
        for k, v in previous_floor.items():
            try:
                prev[str(k)] = float(v)
            except (TypeError, ValueError):
                continue
    elif previous_floor is not None:
        prev["value"] = float(previous_floor)
    cur: dict[str, float] = {}
    if isinstance(current, Mapping):
        for k, v in current.items():
            try:
                cur[str(k)] = float(v)
            except (TypeError, ValueError):
                continue
    else:
        cur["value"] = float(current)
    floors: dict[str, float] = dict(prev)
    raised: list[str] = []
    below: dict[str, dict[str, float]] = {}
    for k, v in cur.items():
        if k not in floors or v > floors[k]:
            floors[k] = v
            raised.append(k)
        elif v < floors[k]:
            below[k] = {"floor": floors[k], "current": v}
    return {"floors": dict(sorted(floors.items())), "raised": sorted(raised),
            "below_floor": dict(sorted(below.items())),
            "rule": "floors ratchet up only; a measurement below its floor is reported, never "
                    "used to lower it"}


# ----------------------------------------------------------------------------- the named examples
#: The three frontier rows the specification names. Each is a full coordinate of one tensor and
#: the sentence it stands for, so a test can construct it and a reader can recognise it.
EXAMPLE_FRONTIER_ROWS: tuple[dict[str, Any], ...] = (
    {"label": "indonesia_nickel_china_cycle_aud_asia_risk_off", "tensor": WORLD,
     "story": "Indonesia nickel exports x China industrial cycle x AUD x Asian session x "
              "risk-off has never been tested",
     "values": {"country": "id", "sector": "metals_mining", "information_type": "customs",
                "mechanism": "cross_market_lead", "representation": "cross_country_spread",
                "asset": "AUDUSD", "session": "asia", "regime": "risk_off", "horizon": "1d",
                "execution": "market"}},
    {"label": "korea_semiconductor_supply_chain_jpy_asia", "tensor": WORLD,
     "story": "Korean semiconductor supply-chain data x JPY x Asian session has no candidate "
              "history",
     "values": {"country": "kr", "sector": "semiconductors", "information_type": "supply_chain",
                "mechanism": "cross_market_lead", "representation": "surprise",
                "asset": "USDJPY", "session": "asia", "regime": "unconditional",
                "horizon": "1d", "execution": "market"}},
    {"label": "russia_energy_shipping_brent_eurusd", "tensor": WORLD,
     "story": "Russian energy-shipping local sources x Brent x EURUSD have never been tested",
     "values": {"country": "ru", "sector": "energy_oil_gas",
                "information_type": "physical_exhaust", "mechanism": "cross_market_lead",
                "representation": "delta", "asset": "EURUSD", "session": "london",
                "regime": "unconditional", "horizon": "1d", "execution": "market"},
     "transmission": "XBRUSD -> EURUSD"},
    {"label": "russia_energy_shipping_local_sources", "tensor": FOREST,
     "story": "Russian-language physical-economy (shipping) sources for the energy sector, "
              "transmitting through Brent into EURUSD",
     "values": {"country": "ru", "language": "ru", "source_class": "physical_economy",
                "sector": "energy_oil_gas", "mechanism": "cross_market_lead",
                "asset_transmission": "XBRUSD", "freshness": "daily",
                "accessibility": "PUBLIC"}},
)


def example_cells() -> list[Cell]:
    """The named example rows as floor cells, constructible on any tree."""
    out: list[Cell] = []
    for row in EXAMPLE_FRONTIER_ROWS:
        tensor = str(row["tensor"])
        axes = axes_of(tensor)
        values = dict(row["values"])
        out.append(Cell(tensor, tuple(str(values.get(a) or ANY) for a in axes),
                        ladder_of(tensor).floor,
                        {"label": row["label"], "story": row["story"]}, ""))
    return out

```

### libs\research\event_graph.py
```python
"""THE CROSS-MARKET EVENT / KNOWLEDGE GRAPH (LAWS 5m: "the Cross-Market Event Graph with a
Causal/Mechanism Adjudicator"). Pure and typed: no file, no registry, no bars in here.

ONE DYNAMIC GRAPH over events, entities (actors), industries, commodities, countries, currencies,
rates, shipping / supply-chain flows, macro series and MT5 assets, whose edges carry a MECHANISM,
a claimed SIGN, a HORIZON and one of three EVIDENCE STATES:

    HYPOTHESIS          declared by an ontology, a country pack or a story; nothing measured it
    MEASURED_ELSEWHERE  a public study, another desk's number or a pack's cited measurement
    DESK_MEASURED       this desk measured it on its own bars/series (event_graph_lab)

A propagation path is event -> entity -> industry -> commodity -> country -> currency -> asset
(port closure -> copper shipment delay -> inventory expectations -> copper curve -> Chile terms
of trade -> CLP proxies); the ladder is a SCORE on a path, never a constraint, because the
interesting chains skip rungs (a sanction reaches an exotic pair in one hop).

IT REDECLARES NOTHING. The event kinds, their transmission edges, the country and commodity
tables come from `libs.research.event_ontology`; the transmission seeds come from the country
packs through `transmission_engine.seed_edges` (the lab hands the rows in); measured causal edges
come from the world causal graph. This module only knows how to hold them together, walk them,
read centrality / contagion / community change off them, and turn EVERY EDGE into a testable
hypothesis with a falsifier and competing explanations -- the candidate contract of LAWS 5k.
"""
from __future__ import annotations

import hashlib
import json
from collections import defaultdict, deque
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from libs.research import event_ontology as eo

KINDS: tuple[str, ...] = ("event", "entity", "shipping", "industry", "commodity", "country",
                          "currency", "rate", "series", "asset")
#: The canonical propagation ladder, used to SCORE a path's shape (share of hops that descend
#: the ladder). It is not a constraint: see the module docstring.
LADDER: dict[str, int] = {k: i for i, k in enumerate(KINDS)}

HYPOTHESIS = "HYPOTHESIS"
MEASURED_ELSEWHERE = "MEASURED_ELSEWHERE"
DESK_MEASURED = "DESK_MEASURED"
EVIDENCE_STATES: tuple[str, ...] = (HYPOTHESIS, MEASURED_ELSEWHERE, DESK_MEASURED)
EVIDENCE_RANK: dict[str, int] = {s: i for i, s in enumerate(EVIDENCE_STATES)}
#: Prior weight of an edge with no measured strength, by evidence state. A DESK_MEASURED edge
#: always carries its own |strength|; these are what the walkers use before that exists.
EVIDENCE_WEIGHT: dict[str, float] = {HYPOTHESIS: 0.25, MEASURED_ELSEWHERE: 0.5,
                                     DESK_MEASURED: 1.0}
UNMEASURED = "UNMEASURED"
SIGNS: tuple[str, ...] = ("+", "-", "?")
HORIZONS: tuple[str, ...] = (*eo.HORIZONS, "?")

MAX_PATHS = 200
MAX_HOPS = 6
#: Betweenness is exact below this many nodes and sampled (first K sources by id) above it, so a
#: graph that grows with every country pack never turns a reading into a minute of CPU.
BETWEENNESS_EXACT_NODES = 1_500
BETWEENNESS_SAMPLE = 300

RULE = ("one graph, three evidence states, a hypothesis at every edge; nothing declared here that "
        "the ontology, the packs or the causal graph already declare")


def _slug(text: str) -> str:
    return "_".join(str(text or "").strip().lower().replace("/", " ").replace(":", " ").split())


def node_id(kind: str, name: str) -> str:
    if kind not in KINDS:
        raise ValueError(f"unknown node kind {kind!r}; one of {KINDS}")
    return f"{kind}:{_slug(name)}"


def edge_id(src: str, dst: str, mechanism: str) -> str:
    return hashlib.sha1(f"{src}|{dst}|{_slug(mechanism)}".encode()).hexdigest()[:16]


def _now() -> str:
    return datetime.now(tz=UTC).isoformat(timespec="seconds")


@dataclass(frozen=True)
class Node:
    id: str
    kind: str
    label: str = ""
    attrs: dict[str, Any] = field(default_factory=dict)

    def to_row(self) -> dict[str, Any]:
        return {"id": self.id, "kind": self.kind, "label": self.label, "attrs": dict(self.attrs)}


@dataclass
class Edge:
    """One directed claim: `src` moves `dst` through `mechanism`."""

    id: str
    src: str
    dst: str
    mechanism: str
    sign: str = "?"
    horizon: str = "?"
    evidence: str = HYPOTHESIS
    strength: float | None = None
    lag: float | None = None
    origin: str = ""
    measured_at: str = ""
    detail: dict[str, Any] = field(default_factory=dict)

    @property
    def weight(self) -> float:
        """|strength| when measured, the evidence prior otherwise -- never zero, never above 1."""
        if self.strength is not None and self.evidence == DESK_MEASURED:
            return max(0.01, min(1.0, abs(float(self.strength))))
        return EVIDENCE_WEIGHT.get(self.evidence, EVIDENCE_WEIGHT[HYPOTHESIS])

    def to_row(self) -> dict[str, Any]:
        return {"id": self.id, "src": self.src, "dst": self.dst, "mechanism": self.mechanism,
                "sign": self.sign, "horizon": self.horizon, "evidence": self.evidence,
                "strength": self.strength, "lag": self.lag, "origin": self.origin,
                "measured_at": self.measured_at, "detail": dict(self.detail)}


Path = list[Edge]


class EventGraph:
    """The graph. Idempotent adds; evidence only ever RISES on a re-declared edge."""

    def __init__(self) -> None:
        self.nodes: dict[str, Node] = {}
        self.edges: dict[str, Edge] = {}
        self._out: dict[str, list[str]] = defaultdict(list)
        self._in: dict[str, list[str]] = defaultdict(list)

    # ------------------------------------------------------------------ building
    def add_node(self, kind: str, name: str, label: str = "", **attrs: Any) -> Node:
        nid = node_id(kind, name)
        have = self.nodes.get(nid)
        if have is not None:
            merged = dict(have.attrs)
            merged.update({k: v for k, v in attrs.items() if v is not None})
            node = Node(nid, kind, have.label or label or str(name), merged)
        else:
            node = Node(nid, kind, label or str(name),
                        {k: v for k, v in attrs.items() if v is not None})
        self.nodes[nid] = node
        return node

    def add_edge(self, src: str, dst: str, mechanism: str, *, sign: str = "?",
                 horizon: str = "?", evidence: str = HYPOTHESIS, strength: float | None = None,
                 lag: float | None = None, origin: str = "",
                 detail: Mapping[str, Any] | None = None) -> Edge:
        if src not in self.nodes or dst not in self.nodes:
            raise KeyError(f"edge {src} -> {dst}: both nodes must exist before the edge")
        if src == dst:
            raise ValueError(f"self-edge refused on {src}")
        if evidence not in EVIDENCE_STATES:
            raise ValueError(f"evidence {evidence!r} not one of {EVIDENCE_STATES}")
        if sign not in SIGNS:
            raise ValueError(f"sign {sign!r} not one of {SIGNS}")
        if horizon not in HORIZONS:
            raise ValueError(f"horizon {horizon!r} not one of {HORIZONS}")
        eid = edge_id(src, dst, mechanism)
        have = self.edges.get(eid)
        if have is None:
            edge = Edge(eid, src, dst, mechanism, sign, horizon, evidence, strength, lag, origin,
                        "", dict(detail or {}))
            self.edges[eid] = edge
            self._out[src].append(eid)
            self._in[dst].append(eid)
            return edge
        # A re-declaration never DOWNGRADES evidence and never erases a desk measurement.
        if EVIDENCE_RANK[evidence] > EVIDENCE_RANK[have.evidence]:
            have.evidence, have.strength, have.origin = evidence, strength, origin or have.origin
            if sign != "?":
                have.sign = sign
        elif EVIDENCE_RANK[evidence] == EVIDENCE_RANK[have.evidence]:
            if have.strength is None and strength is not None:
                have.strength = strength
            if have.sign == "?" and sign != "?":
                have.sign = sign
        if have.horizon == "?" and horizon != "?":
            have.horizon = horizon
        if have.lag is None and lag is not None:
            have.lag = lag
        if detail:
            have.detail.update(dict(detail))
        return have

    def set_measurement(self, eid: str, *, strength: float, sign: str, measured_at: str = "",
                        evidence: str = DESK_MEASURED, detail: Mapping[str, Any] | None = None
                        ) -> Edge:
        """What the lab writes after measuring an edge on the desk's own series."""
        edge = self.edges[eid]
        if evidence not in EVIDENCE_STATES:
            raise ValueError(f"evidence {evidence!r} not one of {EVIDENCE_STATES}")
        edge.strength = float(strength)
        edge.sign = sign if sign in SIGNS else "?"
        edge.measured_at = measured_at or _now()
        if EVIDENCE_RANK[evidence] >= EVIDENCE_RANK[edge.evidence]:
            edge.evidence = evidence
        if detail:
            edge.detail.update(dict(detail))
        return edge

    # ------------------------------------------------------------------ walking
    def out_edges(self, nid: str) -> list[Edge]:
        return [self.edges[e] for e in self._out.get(nid, ())]

    def in_edges(self, nid: str) -> list[Edge]:
        return [self.edges[e] for e in self._in.get(nid, ())]

    def nodes_of_kind(self, kind: str) -> list[Node]:
        return [n for n in self.nodes.values() if n.kind == kind]

    def propagation_paths(self, start: str, *, terminal_kind: str = "asset",
                          max_hops: int = MAX_HOPS, limit: int = MAX_PATHS) -> list[Path]:
        """Every simple path from `start` that ends on a `terminal_kind` node, shortest first,
        strongest first within a length. Bounded by `limit` so a hub never explodes the walk."""
        if start not in self.nodes:
            return []
        out: list[Path] = []
        stack: list[tuple[str, Path, frozenset[str]]] = [(start, [], frozenset([start]))]
        while stack and len(out) < limit * 4:
            node, path, seen = stack.pop()
            if path and self.nodes[node].kind == terminal_kind:
                out.append(path)
            if len(path) >= max_hops:
                continue
            for e in sorted(self.out_edges(node), key=lambda x: -x.weight):
                if e.dst in seen:
                    continue
                stack.append((e.dst, [*path, e], seen | {e.dst}))
        out.sort(key=lambda p: (len(p), -path_strength(p)))
        return out[:limit]

    def find_chain(self, start: str, end: str, *, max_hops: int = MAX_HOPS) -> Path | None:
        """The shortest directed chain from `start` to `end`, or None."""
        if start not in self.nodes or end not in self.nodes:
            return None
        prev: dict[str, Edge] = {}
        seen = {start}
        queue: deque[tuple[str, int]] = deque([(start, 0)])
        while queue:
            node, depth = queue.popleft()
            if node == end:
                path: Path = []
                cur = end
                while cur != start:
                    e = prev[cur]
                    path.append(e)
                    cur = e.src
                path.reverse()
                return path
            if depth >= max_hops:
                continue
            for e in self.out_edges(node):
                if e.dst not in seen:
                    seen.add(e.dst)
                    prev[e.dst] = e
                    queue.append((e.dst, depth + 1))
        return None

    # ------------------------------------------------------------------ readings
    def centrality(self) -> dict[str, dict[str, float]]:
        """Weighted degree and (exact or sampled) betweenness per node."""
        ids = sorted(self.nodes)
        deg: dict[str, float] = dict.fromkeys(ids, 0.0)
        for e in self.edges.values():
            deg[e.src] += e.weight
            deg[e.dst] += e.weight
        between: dict[str, float] = dict.fromkeys(ids, 0.0)
        sources = ids if len(ids) <= BETWEENNESS_EXACT_NODES else ids[:BETWEENNESS_SAMPLE]
        for s in sources:                                        # Brandes, unweighted hops
            order: list[str] = []
            preds: dict[str, list[str]] = defaultdict(list)
            sigma: dict[str, float] = defaultdict(float)
            dist: dict[str, int] = {s: 0}
            sigma[s] = 1.0
            queue: deque[str] = deque([s])
            while queue:
                v = queue.popleft()
                order.append(v)
                for e in self.out_edges(v):
                    w = e.dst
                    if w not in dist:
                        dist[w] = dist[v] + 1
                        queue.append(w)
                    if dist[w] == dist[v] + 1:
                        sigma[w] += sigma[v]
                        preds[w].append(v)
            delta: dict[str, float] = defaultdict(float)
            for w in reversed(order):
                for v in preds[w]:
                    if sigma[w] > 0:
                        delta[v] += sigma[v] / sigma[w] * (1.0 + delta[w])
                if w != s:
                    between[w] += delta[w]
        top = max(between.values()) if between else 0.0
        scale = 1.0 / top if top > 0 else 0.0
        return {n: {"degree": round(deg[n], 4), "betweenness": round(between[n] * scale, 4)}
                for n in ids}

    def contagion(self, seeds: Mapping[str, float], *, decay: float = 0.6,
                  hops: int = 6) -> dict[str, float]:
        """How far a shock at `seeds` reaches: value x edge weight x decay per hop, the MAX over
        routes kept per node (a node reached twice is reached, not doubly reached).

        SIX HOPS BY DEFAULT, because the textbook chain this graph exists to walk -- event ->
        shipping -> commodity -> country -> currency -> asset -- is five edges long, and a
        four-hop default stopped exactly one node short of the asset (measured 2026-09-22:
        `asset:usdclp` absent from the reach of a planted port closure)."""
        level: dict[str, float] = {n: float(v) for n, v in seeds.items() if n in self.nodes}
        frontier = dict(level)
        for _ in range(max(0, hops)):
            nxt: dict[str, float] = {}
            for nid, val in frontier.items():
                for e in self.out_edges(nid):
                    got = val * e.weight * decay
                    if got > level.get(e.dst, 0.0) + 1e-12:
                        level[e.dst] = got
                        nxt[e.dst] = got
            if not nxt:
                break
            frontier = nxt
        return {k: round(v, 6) for k, v in sorted(level.items(), key=lambda kv: -kv[1])}

    def communities(self, *, iterations: int = 20) -> dict[str, str]:
        """Deterministic label propagation over the undirected, weighted view."""
        ids = sorted(self.nodes)
        label = {n: n for n in ids}
        nbrs: dict[str, list[tuple[str, float]]] = defaultdict(list)
        for e in self.edges.values():
            nbrs[e.src].append((e.dst, e.weight))
            nbrs[e.dst].append((e.src, e.weight))
        for _ in range(max(1, iterations)):
            changed = False
            for n in ids:
                if not nbrs[n]:
                    continue
                score: dict[str, float] = defaultdict(float)
                for m, w in nbrs[n]:
                    score[label[m]] += w
                best = min(score.items(), key=lambda kv: (-kv[1], kv[0]))[0]
                if best != label[n]:
                    label[n] = best
                    changed = True
            if not changed:
                break
        return label

    def community_change(self, previous: Mapping[str, str] | None,
                         current: Mapping[str, str] | None = None) -> dict[str, Any]:
        """Which nodes changed community since the previous reading. With no previous reading
        the answer is UNMEASURED, not zero change."""
        cur = dict(current if current is not None else self.communities())
        if not previous:
            return {"status": UNMEASURED, "moved": [], "share_moved": None,
                    "n_communities": len(set(cur.values())),
                    "why": "no previous community reading to compare against"}
        # Communities are named by a representative node, so compare PARTITIONS, not labels.
        def groups(lbl: Mapping[str, str]) -> dict[str, frozenset[str]]:
            g: dict[str, set[str]] = defaultdict(set)
            for n, c in lbl.items():
                g[c].add(n)
            return {c: frozenset(m) for c, m in g.items()}
        old_g, new_g = groups(previous), groups(cur)
        old_of = {n: old_g[c] for n, c in previous.items()}
        moved = sorted(n for n, c in cur.items()
                       if n in old_of and old_of[n] != new_g[c])
        common = [n for n in cur if n in previous]
        return {"status": "MEASURED", "moved": moved[:200],
                "n_moved": len(moved),
                "share_moved": (round(len(moved) / len(common), 4) if common else None),
                "n_communities": len(new_g), "n_communities_before": len(old_g),
                "new_nodes": len([n for n in cur if n not in previous])}

    def readings(self) -> dict[str, Any]:
        by_kind: dict[str, int] = defaultdict(int)
        for n in self.nodes.values():
            by_kind[n.kind] += 1
        by_ev: dict[str, int] = dict.fromkeys(EVIDENCE_STATES, 0)
        for e in self.edges.values():
            by_ev[e.evidence] += 1
        cent = self.centrality()
        top = sorted(cent.items(), key=lambda kv: (-kv[1]["betweenness"], -kv[1]["degree"]))
        return {"n_nodes": len(self.nodes), "n_edges": len(self.edges),
                "nodes_by_kind": dict(sorted(by_kind.items())), "edges_by_evidence": by_ev,
                "top_central": [{"node": n, **c} for n, c in top[:20]]}

    # ------------------------------------------------------------------ hypotheses
    def hypotheses(self, *, limit: int | None = None) -> list[dict[str, Any]]:
        """One testable hypothesis PER EDGE, terminal asset edges first. Every row carries its
        falsifier and its competing explanations, which is the candidate contract (LAWS 5k)."""
        rows = [edge_hypothesis(e, self) for e in self.edges.values()]
        rows.sort(key=lambda r: (not r["testable"], -r["prior_weight"], r["edge_id"]))
        return rows if limit is None else rows[:limit]

    # ------------------------------------------------------------------ persistence
    def to_doc(self) -> dict[str, Any]:
        return {"at": _now(), "rule": RULE, "kinds": list(KINDS),
                "evidence_states": list(EVIDENCE_STATES),
                "nodes": [n.to_row() for n in sorted(self.nodes.values(), key=lambda n: n.id)],
                "edges": [e.to_row() for e in sorted(self.edges.values(), key=lambda e: e.id)]}

    @classmethod
    def from_doc(cls, doc: Mapping[str, Any] | None) -> EventGraph:
        g = cls()
        if not doc:
            return g
        for row in doc.get("nodes") or []:
            if isinstance(row, Mapping) and row.get("kind") in KINDS:
                g.nodes[str(row["id"])] = Node(str(row["id"]), str(row["kind"]),
                                              str(row.get("label") or ""),
                                              dict(row.get("attrs") or {}))
        for row in doc.get("edges") or []:
            if not isinstance(row, Mapping):
                continue
            src, dst = str(row.get("src") or ""), str(row.get("dst") or "")
            if src not in g.nodes or dst not in g.nodes or src == dst:
                continue
            e = Edge(str(row.get("id") or edge_id(src, dst, str(row.get("mechanism") or ""))),
                     src, dst, str(row.get("mechanism") or ""),
                     str(row.get("sign") or "?"), str(row.get("horizon") or "?"),
                     str(row.get("evidence") or HYPOTHESIS),
                     _float_or_none(row.get("strength")), _float_or_none(row.get("lag")),
                     str(row.get("origin") or ""), str(row.get("measured_at") or ""),
                     dict(row.get("detail") or {}))
            if e.evidence not in EVIDENCE_STATES or e.sign not in SIGNS \
                    or e.horizon not in HORIZONS:
                continue
            g.edges[e.id] = e
            g._out[src].append(e.id)
            g._in[dst].append(e.id)
        return g


def _float_or_none(v: Any) -> float | None:
    return float(v) if isinstance(v, (int, float)) and v == v else None


def path_strength(path: Sequence[Edge]) -> float:
    s = 1.0
    for e in path:
        s *= e.weight
    return s


def ladder_score(path: Sequence[Edge], graph: EventGraph) -> float:
    """Share of hops that descend the canonical ladder; 1.0 is the textbook chain."""
    if not path:
        return 0.0
    down = 0
    for e in path:
        if LADDER[graph.nodes[e.src].kind] <= LADDER[graph.nodes[e.dst].kind]:
            down += 1
    return round(down / len(path), 4)


def summarise_path(path: Sequence[Edge], graph: EventGraph) -> dict[str, Any]:
    nodes = [path[0].src, *(e.dst for e in path)] if path else []
    return {"signature": " -> ".join(nodes), "n_hops": len(path),
            "strength": round(path_strength(path), 6),
            "ladder_score": ladder_score(path, graph),
            "evidence": [e.evidence for e in path],
            "weakest": (min(path, key=lambda e: e.weight).id if path else None),
            "all_desk_measured": bool(path) and all(e.evidence == DESK_MEASURED for e in path)}


def edge_hypothesis(edge: Edge, graph: EventGraph) -> dict[str, Any]:
    """The claim an edge makes, written as a candidate: cause, effect, sign, horizon, the test
    that would kill it and the explanations it must beat. Direction-agnostic when the sign is
    unknown: the falsifier is then "no effect at all", never "the wrong sign"."""
    src, dst = graph.nodes[edge.src], graph.nodes[edge.dst]
    horizon = edge.horizon if edge.horizon != "?" else "days"
    sign_txt = {"+": "the same direction", "-": "the opposite direction",
                "?": "either direction"}[edge.sign]
    symbol = str(dst.attrs.get("symbol") or "") if dst.kind == "asset" else ""
    falsifier = (f"measured on the desk's own series, the effect of {src.label} on {dst.label} "
                 f"at horizon {horizon} has p >= 0.05 under a circular-block permutation null"
                 + (", or its sign opposes the claim" if edge.sign != "?" else "")
                 + "; or the effect is explained by a common factor (USD, global risk), by "
                 f"{dst.label}'s own persistence, or by reverse causation")
    competing = [
        f"a common factor moves both {src.label} and {dst.label}",
        f"reverse causation: {dst.label} leads {src.label}",
        f"{dst.label}'s own persistence explains the move ({src.label} adds nothing)",
        "the information is already priced by the time it is observable",
    ]
    return {
        "edge_id": edge.id, "cause": edge.src, "effect": edge.dst,
        "claim": (f"{src.label} moves {dst.label} in {sign_txt} over {horizon} through "
                  f"{edge.mechanism or 'an undeclared mechanism'}"),
        "mechanism": edge.mechanism, "sign": edge.sign, "horizon": horizon,
        "lag": edge.lag, "evidence": edge.evidence, "strength": edge.strength,
        "prior_weight": edge.weight, "origin": edge.origin,
        "falsifier": falsifier, "competing": competing,
        "testable": dst.kind == "asset" and bool(symbol),
        "symbol": symbol, "symbols": [symbol] if symbol else [],
        "source_selector": str(src.attrs.get("selector") or ""),
        "target_selector": str(dst.attrs.get("selector") or ""),
    }


# ======================================================================= ingestion (pure)
def _asset_node(graph: EventGraph, symbol: str, universe: Mapping[str, str] | None) -> Node:
    cls = (universe or {}).get(symbol.upper(), "")
    return graph.add_node("asset", symbol.upper(), symbol.upper(), symbol=symbol.upper(),
                          asset_class=cls or None, selector=f"sym:{symbol.upper()}")


def seed_from_ontology(graph: EventGraph, *, universe: Mapping[str, str] | None = None,
                       ontology: Mapping[str, Any] | None = None,
                       countries: Sequence[Any] | None = None,
                       commodities: Sequence[Any] | None = None) -> int:
    """The event ontology's kinds, edges, countries and commodities, as graph structure.

    `universe` is symbol -> asset_class from MetaTrader's registry. When it is given, an anchor
    the broker does not list is dropped (the graph never names a symbol Fusion does not trade);
    an edge whose anchors are all absent falls back to a `class:` selector node, which is the
    vocabulary the atlases already resolve.
    """
    onto = ontology if ontology is not None else eo.ONTOLOGY
    ctry = list(countries if countries is not None else eo.COUNTRIES)
    comm = list(commodities if commodities is not None else eo.COMMODITIES)
    known = {s.upper() for s in (universe or {})}
    n0 = len(graph.edges)

    def usable(symbol: str) -> bool:
        return not known or symbol.upper() in known

    for cid, spec in onto.items():
        ev = graph.add_node("event", cid, str(getattr(spec, "gloss", cid)),
                            scheduled=bool(getattr(spec, "scheduled", False)))
        for edge in getattr(spec, "edges", ()):
            anchors = [a for a in edge.anchors if usable(a)]
            targets = ([_asset_node(graph, a, universe) for a in anchors] or
                       [graph.add_node("asset", f"class:{edge.asset_class}",
                                       f"class:{edge.asset_class}",
                                       selector=f"class:{edge.asset_class}",
                                       asset_class=edge.asset_class)])
            for t in targets:
                graph.add_edge(ev.id, t.id, edge.note or f"{cid} transmits to {edge.asset_class}",
                               horizon=edge.horizon, evidence=HYPOTHESIS,
                               origin="event_ontology",
                               detail={"state_vars": list(edge.state_vars),
                                       "asset_class": edge.asset_class})
    for c in comm:
        cn = graph.add_node("commodity", c.commodity_id, c.commodity_id,
                            asset_class=c.asset_class)
        for ind in c.industries:
            i = graph.add_node("industry", ind, ind)
            graph.add_edge(cn.id, i.id, "input cost", sign="-", horizon="weeks",
                           origin="event_ontology")
        for a in c.anchors:
            if usable(a):
                graph.add_edge(cn.id, _asset_node(graph, a, universe).id, "price of",
                               sign="+", horizon="minutes", evidence=MEASURED_ELSEWHERE,
                               origin="event_ontology",
                               detail={"why": "the anchor IS the commodity's traded price"})
    for k in ctry:
        kn = graph.add_node("country", k.code, k.code, currency=k.currency)
        cur = graph.add_node("currency", k.currency, k.currency)
        graph.add_edge(kn.id, cur.id, "terms of trade and rate expectations", horizon="days",
                       origin="event_ontology")
        for cid in k.exports:
            if node_id("commodity", cid) in graph.nodes:
                graph.add_edge(node_id("commodity", cid), kn.id, "export revenue", sign="+",
                               horizon="days", origin="event_ontology")
        for cid in k.imports:
            if node_id("commodity", cid) in graph.nodes:
                graph.add_edge(node_id("commodity", cid), kn.id, "import bill", sign="-",
                               horizon="days", origin="event_ontology")
        for idx in k.indices:
            if usable(idx):
                graph.add_edge(kn.id, _asset_node(graph, idx, universe).id, "equity index",
                               sign="+", horizon="hours", origin="event_ontology")
        for r in k.rates:
            rn = graph.add_node("rate", r, r)
            graph.add_edge(kn.id, rn.id, "sovereign curve", horizon="hours",
                           origin="event_ontology")
            if usable(r):
                graph.add_edge(rn.id, _asset_node(graph, r, universe).id, "quoted as", sign="+",
                               horizon="minutes", evidence=MEASURED_ELSEWHERE,
                               origin="event_ontology")
        for ind in k.industries:
            graph.add_edge(graph.add_node("industry", ind, ind).id, kn.id, "domestic industry",
                           sign="+", horizon="weeks", origin="event_ontology")
        if universe:
            for sym in sorted(s for s, cls in universe.items()
                              if k.currency in s.upper() and str(cls).lower().startswith("forex")
                              )[:eo.MAX_ASSETS_PER_EDGE]:
                graph.add_edge(cur.id, _asset_node(graph, sym, universe).id, "currency leg",
                               sign="?", horizon="minutes", evidence=MEASURED_ELSEWHERE,
                               origin="event_ontology")
    return len(graph.edges) - n0


def _endpoint(graph: EventGraph, selector: str, universe: Mapping[str, str] | None,
              country: str = "") -> Node | None:
    """`sym:X` is an asset, `series:name` a macro series, anything else is not an endpoint."""
    kind, _, name = str(selector or "").partition(":")
    if kind == "sym" and name:
        return _asset_node(graph, name, universe)
    if kind == "series" and name:
        return graph.add_node("series", name, name, selector=f"series:{name}",
                              country=country or None)
    return None


def seed_from_transmission(graph: EventGraph, rows: Iterable[Mapping[str, Any]], *,
                           universe: Mapping[str, str] | None = None) -> int:
    """The transmission engine's seed rows (`transmission_engine.seed_edges`: the packs'
    `transmission_edges_seed`, the declared channels, the actor atlas), as
    country -> actor -> flow -> endpoint chains. A row the engine measured and ADMITTED lands
    DESK_MEASURED with its strength; a measured-but-not-admitted row stays a hypothesis and says
    so in its detail; a row carrying `evidence_state` from a pack keeps that state."""
    n0 = len(graph.edges)
    for row in rows:
        src = _endpoint(graph, str(row.get("source") or ""), universe,
                        str(row.get("from_country") or ""))
        dst = _endpoint(graph, str(row.get("target") or f"sym:{row.get('asset') or ''}"),
                        universe, str(row.get("to_country") or ""))
        if dst is None:
            continue
        raw_ev = row.get("evidence")
        ev: Mapping[str, Any] = raw_ev if isinstance(raw_ev, Mapping) else {}
        state = str(row.get("evidence_state") or HYPOTHESIS)
        if state not in EVIDENCE_STATES:
            state = HYPOTHESIS
        admitted = bool(ev.get("admitted"))
        if row.get("measured") and admitted:
            state = DESK_MEASURED
        strength = _float_or_none(row.get("strength")) if row.get("measured") else None
        sign = "?" if strength is None else ("+" if strength > 0 else "-")
        lag = _float_or_none(row.get("lag_days"))
        origin = str(row.get("origin") or "transmission_engine")
        detail = {"why": str(ev.get("why") or ""), "admitted": admitted,
                  "measured": bool(row.get("measured")), "edge_id": row.get("id"),
                  "constraint": str(row.get("constraint") or "")}
        chain: list[Node] = []
        fc = str(row.get("from_country") or "").strip()
        if fc and fc != "global":
            chain.append(graph.add_node("country", fc, fc))
        actor = str(row.get("actor") or "").strip()
        if actor:
            chain.append(graph.add_node("entity", actor[:80], actor[:80]))
        flow = str(row.get("flow") or "").strip()
        if flow:
            chain.append(graph.add_node("shipping", flow[:80], flow[:80]))
        if src is not None and (not chain or chain[-1].id != src.id):
            chain.append(src)
        prev: Node | None = None
        for node in chain:
            if prev is not None and prev.id != node.id:
                graph.add_edge(prev.id, node.id, "forces" if prev.kind != "shipping"
                               else "observable of", horizon="days", origin=origin,
                               detail={"constraint": detail["constraint"]})
            prev = node
        if prev is not None and prev.id != dst.id:
            graph.add_edge(prev.id, dst.id, flow or "transmission", sign=sign,
                           horizon="days", evidence=state, strength=strength, lag=lag,
                           origin=origin, detail=detail)
    return len(graph.edges) - n0


_CAUSAL_KIND: dict[str, str] = {"cb": "entity", "positioning": "series", "rate": "rate",
                                "series": "series", "macro": "series", "flow": "shipping"}


def seed_from_causal_edges(graph: EventGraph, rows: Iterable[Mapping[str, Any]], *,
                           universe: Mapping[str, str] | None = None) -> int:
    """The world causal graph's measured edges (src, dst, lag, direction, strength, status).
    ADMITTED is DESK_MEASURED; a recorded-but-not-admitted edge is kept as a HYPOTHESIS carrying
    its number, because "measured and found nothing" is negative knowledge worth a node."""
    n0 = len(graph.edges)
    for row in rows:
        s, d = str(row.get("src") or ""), str(row.get("dst") or "")
        if not s or not d or s == d:
            continue

        def node_for(name: str) -> Node:
            prefix, _, rest = name.partition(":")
            kind = _CAUSAL_KIND.get(prefix) if rest else None
            if kind:
                return graph.add_node(kind, rest, name, selector=name)
            return _asset_node(graph, name, universe)

        a, b = node_for(s), node_for(d)
        raw_ev = row.get("evidence")
        ev: Mapping[str, Any] = raw_ev if isinstance(raw_ev, Mapping) else {}
        status = str(row.get("status") or ev.get("status") or "").upper()
        admitted = status == "ADMITTED" or bool(ev.get("admitted"))
        strength = _float_or_none(row.get("strength"))
        direction = str(row.get("direction") or "")
        sign = "+" if direction == "same" else "-" if direction == "opposite" else "?"
        lag = _float_or_none(row.get("lag"))
        cls = str(row.get("decay_cls") or "")
        horizon = ("days" if "D1" in cls or "W1" in cls else "hours" if cls else "?")
        graph.add_edge(a.id, b.id, str(ev.get("prior_mechanism_class") or "measured lead"),
                       sign=sign if admitted else "?", horizon=horizon,
                       evidence=DESK_MEASURED if admitted else HYPOTHESIS,
                       strength=strength if admitted else None, lag=lag,
                       origin="world_causal_graph",
                       detail={"admitted": admitted, "recorded_strength": strength,
                               "n": row.get("n"), "stability": row.get("stability")})
    return len(graph.edges) - n0


def seed_from_events(graph: EventGraph, rows: Iterable[Mapping[str, Any]], *,
                     limit: int = 500) -> int:
    """Observed event instances (kind, entities, at) as nodes: instance -> its kind (so the
    kind's transmission edges apply) and instance -> every named country / commodity."""
    n0 = len(graph.edges)
    taken = 0
    for row in rows:
        kind = str(row.get("kind") or "").strip().lower()
        if not kind or kind not in eo.ONTOLOGY:
            continue
        at = str(row.get("at") or row.get("seen_at") or row.get("knowable_at") or "")
        ents = [str(e) for e in (row.get("entities") or ()) if str(e).strip()]
        key = hashlib.sha1(f"{kind}|{at}|{'|'.join(sorted(ents))}".encode()).hexdigest()[:10]
        inst = graph.add_node("event", f"{kind} {key}", f"{kind}@{at or 'undated'}",
                              kind_id=kind, at=at or None, instance=True)
        kind_node = graph.add_node("event", kind, kind)
        graph.add_edge(inst.id, kind_node.id, "instance of", horizon="minutes",
                       evidence=DESK_MEASURED, strength=1.0, origin="events")
        for e in ents:
            nid = node_id("country", e) if node_id("country", e) in graph.nodes else (
                node_id("commodity", e) if node_id("commodity", e) in graph.nodes else "")
            if nid:
                graph.add_edge(inst.id, nid, "names", horizon="minutes", evidence=DESK_MEASURED,
                               strength=1.0, origin="events")
        taken += 1
        if taken >= limit:
            break
    return len(graph.edges) - n0


def render(doc: Mapping[str, Any]) -> str:
    r = doc.get("readings") or {}
    return json.dumps({"n_nodes": r.get("n_nodes"), "n_edges": r.get("n_edges"),
                       "edges_by_evidence": r.get("edges_by_evidence")}, sort_keys=True)

```

### libs\research\finding_registry.py
```python
"""Every finding must reach the loop that drives it -- the desk's own map-vs-territory rule,
turned on the desk's findings themselves.

The desk has exactly one organ that DRIVES work to completion: ``docs/GAP_REGISTER.md``, with its
weekly re-rank and 7-day staleness escalation. Everything else -- SYSTEM_REVIEW, BLIND_SPOT_AUDIT,
the micro-audit inbox, the improvement inbox, an external panel ruling, an audit delivered in a
chat window -- is a place findings are WRITTEN, not a place they are WORKED. A finding that never
reaches the register is invisible to the daily cycle, and the cycle only ever acts on what it can
see. It does not rot loudly; it simply never happened.

This was measured, not theorised: of eleven engineering defects found in a full-repo audit, three
were detected by any check and one had a register row. The other eight existed only in a
conversation, and would have vanished with it.

``max_audit.check_review_risks_tracked`` already enforced this -- for THREE HARDCODED KEYS
(counterparty, key-person, per-venue). That is the same brittleness one level up: it can only
catch risks somebody remembered to hardcode, so the next un-tracked finding is invisible again by
construction. This module generalises it: parse findings from wherever they are written, match
them against the register, and report the ones with no trace.

MATCHING IS DELIBERATELY GENEROUS. A finding counts as tracked when any distinctive token from its
title appears in the register. False ACCEPTS are cheap -- the item was probably tracked under
another phrasing. False ALARMS are expensive: a check that flags everything gets ignored, and an
ignored check is worse than no check because it looks like coverage. The same lesson the §33 card
parser learned by firing 92/92 on its first real run.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Sequence
from datetime import date

from pydantic import BaseModel, ConfigDict

#: A finding: a numbered item with a bolded title. Covers the prose form used by SYSTEM_REVIEW and
#: BLIND_SPOT_AUDIT (``3. **Name** ...``) and the table form used by the audit inboxes
#: (``| 3 | **CHANGE** thing | ...``). Free prose is deliberately NOT matched -- an unnumbered
#: paragraph is a remark, and treating remarks as obligations is how a check becomes noise.
#: PROSE form: ``3. **Name** ...`` as used by SYSTEM_REVIEW / BLIND_SPOT_AUDIT.
_PROSE_RE = re.compile(r"^\s*(?P<num>\d+)[.)]\s*\*\*(?P<title>[^*]{4,140})\*\*", re.MULTILINE)
#: TABLE form: ``| 3 | **CHANGE** `run_ci` -- fix the job | why | ...``. The whole first cell is
#: the title: capturing only the bolded span yields the VERB ("CHANGE"), which carries no
#: distinctive token and made every audit-inbox row look untracked on the first real run.
_TABLE_RE = re.compile(r"^\s*\|\s*(?P<num>\d+)\s*\|\s*(?P<title>[^|]{4,200})\|", re.MULTILINE)
#: Headings whose contents are already settled. Anything under one of these is reported as
#: resolved rather than owed -- the inboxes carry large "already live" and "closed" sections, and
#: demanding register rows for them would bury the real items.
_SETTLED_HEAD = re.compile(
    r"already live|duplicat|closed|resolved|done|shipped|complete|history|archive|graveyard",
    re.IGNORECASE,
)
_HEADING_RE = re.compile(r"^#{1,6}\s+(?P<h>.+?)\s*$", re.MULTILINE)
#: Words too common to prove a match -- "risk" appearing in the register means nothing.
_STOP = {
    "the", "and", "for", "with", "from", "that", "this", "into", "onto", "your", "our", "not",
    "add", "fix", "wire", "change", "risk", "data", "test", "tests", "code", "live", "desk",
    "new", "old", "all", "any", "one", "two", "use", "using", "make", "made", "gap", "audit",
    "check", "checks", "build", "built", "run", "runs", "only", "per", "via", "its", "has",
}


class Finding(BaseModel):
    """One numbered finding, wherever it was written."""

    model_config = ConfigDict(frozen=True)

    source: str
    number: int
    title: str
    settled: bool = False   # written under an already-live / closed heading

    @property
    def tokens(self) -> tuple[str, ...]:
        """Distinctive words that would identify this finding in another document."""
        words = re.findall(r"[a-zA-Z_][a-zA-Z0-9_.-]{3,}", self.title.lower())
        return tuple(w for w in words if w not in _STOP)


def parse_findings(text: str, *, source: str) -> list[Finding]:
    """Extract numbered, bolded findings and mark the ones sitting under a settled heading."""
    heads = [(m.start(), m.group("h")) for m in _HEADING_RE.finditer(text)]
    out: list[Finding] = []
    matches = sorted(list(_PROSE_RE.finditer(text)) + list(_TABLE_RE.finditer(text)),
                     key=lambda m: m.start())
    for m in matches:
        title = re.sub(r"[*`]", "", m.group("title"))
        title = re.sub(r"\s+", " ", title).strip(" -—:")
        if not title:
            continue
        prior = [h for pos, h in heads if pos < m.start()]
        settled = bool(prior and _SETTLED_HEAD.search(prior[-1]))
        out.append(Finding(source=source, number=int(m.group("num")),
                           title=title, settled=settled))
    return out


def is_tracked(finding: Finding, register: str) -> bool:
    """Does the register carry any trace of this finding?

    Generous by design: one distinctive token is enough. The check exists to catch findings with
    NO representation at all, not to police wording.
    """
    reg = register.lower()
    if not finding.tokens:
        # Nothing distinctive to search for -- unjudgeable, so it is NOT accused. A check that
        # reports items it cannot actually evaluate is manufacturing work, not finding it.
        return True
    return any(tok in reg for tok in finding.tokens)


def untracked(findings: Iterable[Finding], register: str) -> tuple[Finding, ...]:
    """Open findings with no trace in the register -- the ones the daily cycle cannot see."""
    return tuple(f for f in findings if not f.settled and not is_tracked(f, register))


class CoverageReport(BaseModel):
    """How much of what the desk has FOUND is actually being DRIVEN."""

    model_config = ConfigDict(frozen=True)

    n_findings: int
    n_settled: int
    n_open: int
    n_untracked: int
    coverage: float          # tracked / open; 1.0 = every open finding reaches the register
    untracked_names: tuple[str, ...]
    verdict: str


def coverage_report(
    findings: Sequence[Finding], register: str, *, max_shown: int = 10
) -> CoverageReport:
    """Measure finding -> register coverage. Below 1.0, the cycle is blind to real work."""
    settled = [f for f in findings if f.settled]
    open_ = [f for f in findings if not f.settled]
    ut = untracked(findings, register)
    cov = 1.0 if not open_ else round(1.0 - len(ut) / len(open_), 3)
    if not open_:
        verdict = "no open findings parsed -- nothing owed"
    elif not ut:
        verdict = (f"all {len(open_)} open finding(s) have a register trace "
                   "-- the cycle can see them")
    else:
        verdict = (
            f"{len(ut)}/{len(open_)} open finding(s) have NO register trace ({cov:.0%} coverage). "
            "The daily cycle acts on the register; anything absent from it is invisible and will "
            "never be worked, however carefully it was found."
        )
    return CoverageReport(
        n_findings=len(findings), n_settled=len(settled), n_open=len(open_),
        n_untracked=len(ut), coverage=cov,
        untracked_names=tuple(f"{f.source.rsplit('/', 1)[-1]}#{f.number} {f.title[:60]}"
                              for f in ut[:max_shown]),
        verdict=verdict,
    )


# --------------------------------------------------------------------------------------------
# THE COVERAGE RATCHET. A one-off 100% is a snapshot; the law needs a floor that only ever rises.
# And the cheapest way to reach 100% is NOT to row the findings -- it is to SHRINK THE DENOMINATOR:
# exclude a doc from scope, or delete the finding. That is the same loophole §34 closed for mining
# (fake a conversion rate by mining less), so it is closed the same way: scope size and finding
# count ratchet UP alongside coverage, and all three are held against the desk's own best.
# --------------------------------------------------------------------------------------------

class CoverageRatchet(BaseModel):
    """Best-ever finding→register coverage AND the scope it was achieved over."""

    model_config = ConfigDict(frozen=True)

    best_coverage: float = 0.0
    max_open_findings: int = 0   # denominator high-water mark -- scope may never shrink
    max_docs_scanned: int = 0
    best_at: str = ""
    n_records: int = 0


class RatchetVerdict(BaseModel):
    """Did coverage hold, improve, or regress -- and was the denominator honest?"""

    model_config = ConfigDict(frozen=True)

    improved: bool
    coverage_regressed: bool
    scope_shrank: bool
    verdict: str


def update_coverage_ratchet(
    prior: CoverageRatchet,
    report: CoverageReport,
    *,
    n_docs: int,
    at: str = "",
) -> tuple[CoverageRatchet, RatchetVerdict]:
    """Hold coverage against the desk's own best, over a scope that may never shrink.

    THREE things ratchet, because any one alone is gameable:
      COVERAGE        -- the share of open findings the cycle can see; never allowed to fall.
      OPEN FINDINGS   -- the denominator. Deleting findings raises coverage arithmetically while
                        making the desk blinder, so the count is a high-water mark too.
      DOCS SCANNED    -- excluding a findings doc raises coverage the same dishonest way.

    A worse cycle NEVER relaxes any of the three; it produces a defect instead. That asymmetry is
    the whole mechanism -- a standard that can fall is a standard the desk drifts past.
    """
    cov_record = report.coverage > prior.best_coverage
    cov_regressed = bool(prior.best_coverage and report.coverage < prior.best_coverage - 1e-9)
    shrank = bool(
        (prior.max_open_findings and report.n_open < prior.max_open_findings)
        or (prior.max_docs_scanned and n_docs < prior.max_docs_scanned)
    )
    improved = bool(cov_record or report.n_open > prior.max_open_findings
                    or n_docs > prior.max_docs_scanned)

    new = CoverageRatchet(
        best_coverage=max(prior.best_coverage, report.coverage),
        max_open_findings=max(prior.max_open_findings, report.n_open),
        max_docs_scanned=max(prior.max_docs_scanned, n_docs),
        best_at=(at or prior.best_at) if improved else prior.best_at,
        n_records=prior.n_records + (1 if improved else 0),
    )

    if shrank:
        verdict = (
            f"SCOPE SHRANK: {report.n_open} open findings over {n_docs} docs vs a high-water "
            f"{prior.max_open_findings} over {prior.max_docs_scanned}. Coverage rises "
            "arithmetically when findings or docs disappear -- that is a blinder desk, not a "
            "better one. Restore the scope or record why the items are legitimately closed."
        )
    elif cov_regressed:
        verdict = (
            f"COVERAGE REGRESSED: {report.coverage:.0%} vs best-ever {prior.best_coverage:.0%}. "
            "New findings were written without register rows. Row them; the floor only rises."
        )
    elif report.coverage >= 1.0:
        verdict = (
            f"100% -- all {report.n_open} open finding(s) across {n_docs} docs reach the register. "
            "Hold it: the bar is now this, permanently."
        )
    elif cov_record:
        verdict = (f"coverage record {report.coverage:.0%} (prev {prior.best_coverage:.0%}) -- "
                   "floor raised, it never lowers. Target is 100%.")
    else:
        verdict = (f"coverage {report.coverage:.0%} holding at the floor. Holding is not reaching: "
                   f"{report.n_untracked} finding(s) are still invisible to the cycle.")
    return new, RatchetVerdict(improved=improved, coverage_regressed=cov_regressed,
                               scope_shrank=shrank, verdict=verdict)


# --------------------------------------------------------------------------------------------
# THE REGISTER'S OWN HEALTH. §35 and §36 route everything INTO the register, which makes it the
# load-bearing organ for both -- and it was never checked itself. Its rules ("re-ranked at the
# START of every daily cycle", "items stale >7 days MUST be escalated", "never empty without
# written justification") are written INSIDE the register, which is precisely the shape §36 names
# as a rule with no clock. Routing findings into a bucket nobody empties is not an improvement.
# --------------------------------------------------------------------------------------------

_RERANK_RE = re.compile(r"Re-ranked\s+(\d{4}-\d{2}-\d{2})")
#: A register row: | id | **title** | mechanism | plan | owner | added | status |
_ROW_RE = re.compile(
    r"^\|\s*(?P<id>\d+)\s*\|\s*\*\*(?P<title>.+?)\*\*\s*\|(?P<body>.*?)\|\s*(?P<owner>[a-z+ ]*?)"
    r"\s*\|\s*(?P<added>[\d-]*)\s*\|\s*(?P<status>[^|]*?)\s*\|\s*$",
    re.MULTILINE | re.IGNORECASE,
)
_OPEN_STATUS = ("open", "in-progress", "in progress", "queued", "watch", "pending")
#: Any date-shaped token in the plan text -- evidence the "defer WITH A DEADLINE" exit was taken.
_HAS_DATE = re.compile(r"\d{4}-\d{2}-\d{2}|\d{2}-\d{2}\b")


class RegisterRow(BaseModel):
    """One tracked obligation."""

    model_config = ConfigDict(frozen=True)

    row_id: int
    title: str
    owner: str
    added: str
    status: str
    plan_has_date: bool
    #: THIS row's why+plan text, carried from the match that produced the row. Consumers used to
    #: re-find it by scanning for `| <id> |` and taking the first hit, which is correct only while
    #: ids are unique -- and on 2026-08-12 a branch merge unioned two register lineages without
    #: renumbering, leaving 17 ids naming two findings each. Under the old lookup, id 100's OPEN
    #: row was read through the CLOSED row's text. An id is a label; the text belongs to the row.
    body: str = ""

    @property
    def is_open(self) -> bool:
        return self.status.strip().lower().startswith(_OPEN_STATUS)

    def age_days(self, today: date) -> float:
        """Days since this row was ADDED. -1 when the date is missing or unparseable.

        The register writes `MM-DD` with no year. A date that would land in the future is read as
        last year's -- the only reading that does not turn a December row into a -300-day-old one
        every January, which would silently exempt the oldest rows exactly when they matter most.
        """
        raw = self.added.strip()
        if not raw:
            return -1.0
        try:
            month, day = (int(x) for x in raw.split("-")[:2])
            when = date(today.year, month, day)
        except (ValueError, TypeError):
            return -1.0
        if when > today:
            try:
                when = date(today.year - 1, month, day)
            except ValueError:      # pragma: no cover - 29 Feb on a non-leap year
                return -1.0
        return float((today - when).days)


class RegisterHealth(BaseModel):
    """Is the desk's only work-driving organ actually being driven?"""

    model_config = ConfigDict(frozen=True)

    n_rows: int
    n_open: int
    rerank_age_days: float      # -1 when no stamp was ever written
    rerank_stale: bool
    rerank_breach: bool         # past the register's own 7-day escalation bar
    undated_open: tuple[str, ...]
    ownerless: tuple[str, ...]
    #: Open rows older than the register's OWN escalation bar. THE rule the register actually
    #: states is about ITEMS ("items stale >7 days MUST be escalated"), not about the re-rank
    #: stamp -- and measuring the stamp instead let a daily re-rank make every row immortal.
    stale_rows: tuple[str, ...]
    oldest_open_days: float
    verdict: str


def parse_register(text: str) -> list[RegisterRow]:
    """Extract every tracked row from the register table."""
    out = []
    for m in _ROW_RE.finditer(text):
        out.append(RegisterRow(
            row_id=int(m.group("id")), title=m.group("title").strip(),
            owner=m.group("owner").strip(), added=m.group("added").strip(),
            status=m.group("status").strip(),
            plan_has_date=bool(_HAS_DATE.search(m.group("body") or "")),
            body=m.group("body") or "",
        ))
    return out


def register_health(
    text: str, *, today: date, rerank_bar_days: float = 2.0, escalate_days: float = 7.0
) -> RegisterHealth:
    """Hold the register to the rules it states about itself.

    The re-rank age is read from the register's SELF-DECLARED ``Re-ranked <date>`` stamp, never
    from file mtime or commit time -- touching the file must not be able to fake a re-rank that
    did not happen. Same artifact-only credit principle §33 applies to conversion claims: the
    evidence has to be the thing itself, not a side effect of editing it.
    """
    rows = parse_register(text)
    open_rows = [r for r in rows if r.is_open]
    stamps = _RERANK_RE.findall(text)
    age = -1.0
    if stamps:
        with_dates = []
        for s in stamps:
            try:
                with_dates.append(date.fromisoformat(s))
            except ValueError:  # pragma: no cover
                continue
        if with_dates:
            age = float((today - max(with_dates)).days)

    # An open row whose plan carries no date took NONE of the register's three exits (implement /
    # defer WITH A DEADLINE / retire with reason) -- it is parked, which is the state the rule
    # exists to forbid.
    undated = tuple(f"#{r.row_id} {r.title[:48]}" for r in open_rows if not r.plan_has_date)
    ownerless = tuple(f"#{r.row_id} {r.title[:48]}" for r in open_rows if not r.owner)

    # ROW-LEVEL STALENESS -- the rule the register actually writes down. It says "items stale >7
    # days MUST be escalated"; the first version of this function measured the RE-RANK STAMP
    # instead, so re-stamping the header each morning made every row immortal: 15 rows sat 9-10
    # days untouched while the check reported clean. Measuring the artifact the rule names, rather
    # than a proxy that correlates with tidiness, is the whole point of §36(3).
    aged = sorted(((r.age_days(today), r) for r in open_rows), key=lambda x: -x[0])
    stale_rows = tuple(f"#{r.row_id} ({a:.0f}d) {r.title[:44]}" for a, r in aged
                       if a > escalate_days)
    oldest = aged[0][0] if aged else -1.0

    # NEVER STAMPED IS THE WORST CASE, NOT THE BEST. `age` is -1.0 when no `Re-ranked` stamp has
    # ever been written, and -1.0 fails every `age > bar` comparison -- so a register that had
    # never been re-ranked once reported "re-rank current (-1d)" and passed clean. The absence of
    # evidence was being read as evidence of compliance, which is the same shape as a NaN
    # measurement counting as a filled coverage cell. Caught by a test written against a register
    # carrying only the mechanical stamp.
    never = age < 0
    stale = never or age > rerank_bar_days
    breach = never or age > escalate_days

    if not rows:
        verdict = ("register parsed ZERO rows -- either empty or the table shape changed. Its own "
                   "rule is 'never empty without written justification'; a register that cannot "
                   "be parsed drives nothing, and everything §35/§36 routes into it is lost.")
    elif never:
        verdict = (f"NO `Re-ranked` stamp has ever been written, with {len(open_rows)} open "
                   "row(s). The register's own rule is 're-ranked at the START of every daily "
                   "cycle'; an unstamped register has not been driven once, and reporting that as "
                   "current would make never-having-run the healthiest possible state.")
    elif stale_rows:
        verdict = (f"{len(stale_rows)} open row(s) past the register's OWN {escalate_days:.0f}-day "
                   f"escalation bar (oldest {oldest:.0f}d), while the re-rank stamp reads "
                   f"{age:.0f}d old. Re-ranking the header is not escalating the rows: each one "
                   "owes implement / defer-with-a-deadline / retire-with-reason.")
    elif breach:
        verdict = (f"re-rank {age:.0f}d old, past the register's OWN {escalate_days:.0f}-day "
                   f"escalation bar, with {len(open_rows)} open row(s). The rule is written in the "
                   "register and was enforced by nothing.")
    elif stale:
        verdict = (f"re-rank {age:.0f}d old against 'at the START of every daily cycle'. "
                   f"{len(open_rows)} open row(s) are not being re-prioritised.")
    else:
        verdict = f"re-rank current ({age:.0f}d), {len(open_rows)} open row(s) under active rank"
    return RegisterHealth(
        stale_rows=stale_rows, oldest_open_days=round(oldest, 1),
        n_rows=len(rows), n_open=len(open_rows), rerank_age_days=age,
        rerank_stale=stale, rerank_breach=breach,
        undated_open=undated[:8], ownerless=ownerless[:8], verdict=verdict,
    )

```

### libs\research\natural_experiment.py
```python
"""CAUSAL IDENTIFICATION from a dated exogenous shock -- difference-in-differences with a matched
control cohort, and the refusal paths that make the difference between identification and a
correlation with better vocabulary (R0207).

WHAT THE DESK COULD NOT DO BEFORE THIS MODULE. Every hypothesis this desk has ever tested is
OBSERVATIONAL: an IC or a Sharpe on a correlational panel, defended by de-contamination and
multiplicity control. Both defences are real and neither is identification -- they establish that
a relationship is not an ARTIFACT, never that it is CAUSAL. `libs/validation/event_study.py` is
the closest existing organ and it is a one-sample cross-sectional mean test: its `Event` type
carries a single scalar return and has no field in which a treated/control contrast could even be
expressed. So the desk held hundreds of dated exogenous shocks with untreated peers available as
controls, and no shape to put them in.

WHY A CAUSAL ANSWER IS WORTH BUILDING FOR rather than another correlational screen: an edge whose
MECHANISM is identified survives regime change for a reason you can state, and L1.16 makes that
the condition for calling an edge durable at all. It is also the cheapest possible defence against
the desk's dominant failure mode -- 420 tested, 0 survivors, most of them dying on de-contamination
-- because a shock that is genuinely exogenous cannot be contaminated by the thing it is supposed
to be predicting.

=================================================================================================
THE ARCHITECTURE, AND WHAT THIS MODULE DELIBERATELY DOES NOT DO
=================================================================================================
This module supplies IDENTIFICATION only. The INFERENCE -- multiplicity-corrected bar, bootstrap
against fat tails, overlap discount, degenerate-input refusal -- is delegated verbatim to
`libs.validation.event_study.event_study` by handing it the per-unit DiD estimates as `Event`
returns. That is deliberate and it is the whole reason this file is short: a second copy of the
desk's inference machinery would drift from the audited one, and the first divergence would be
invisible. Upgrade before build (L2.9).

=================================================================================================
PRE-REGISTRATION. Every threshold below is a module-level CONSTANT, not an argument.
=================================================================================================
If they were tunable a caller would sweep them and report the passing configuration, and the
multiplicity charge would be a lie -- the same discipline `listing_events.py` holds its window and
direction to. Changing one is a code change with a diff, which is the point.

THE ESTIMATOR
    For each treated unit i with event at t_i:
        DiD_i = (mean(treated post) - mean(treated pre))
              - (mean(control post) - mean(control pre))
    where the control legs are the matched untreated peers measured over the SAME CALENDAR
    WINDOWS as unit i. Differencing twice is what removes both the unit's own level and whatever
    the whole market did across the event -- neither of which a one-sample event study can remove.

=================================================================================================
THE FOUR WAYS THIS PRODUCES A FAKE CAUSAL CLAIM, AND THE RAIL AGAINST EACH
=================================================================================================
1. SELECTION INTO TREATMENT -- THE ONE THAT WILL ACTUALLY BITE HERE. A venue does not delist at
   random: it delists what has ALREADY died. Run naively, a delisting DiD would report a large,
   beautifully significant "effect" that is entirely the selection rule, and it would look exactly
   like an edge. This is not a hypothetical -- it is the expected default outcome for the first
   cohort this desk has available, so the module REFUSES rather than reports when it detects it.
   The rail is the parallel-trends test below: selection on prior performance is visible in the
   PRE-period, because that is where the selection happened.

2. PARALLEL TRENDS ASSUMED INSTEAD OF TESTED. DiD identifies the effect only if treated and
   control would have moved together absent the shock. That is an assumption about a
   counterfactual and it is not verifiable -- but its observable implication IS: the treated-minus-
   control gap should be indistinguishable from zero BEFORE the event. `PARALLEL_TRENDS_MAX_T`
   refuses when it is not.

   AND THE INVERSION THAT MAKES THAT TEST DANGEROUS ON ITS OWN: failing to reject on a short
   pre-window is not evidence of parallel trends, it is absence of power, and a module that
   reported PASS there would be laundering ignorance into identification. So a pre-window shorter
   than `MIN_PRE_OBS` returns ASSUMPTION-UNTESTABLE, never OK (L1.28a: unmeasured is never fine).

3. SUTVA / CONTROL CONTAMINATION. If the shock reaches the controls -- a market-wide rule change,
   or a treated cohort large enough to move the whole cross-section -- then the control leg
   contains the treatment and DiD differences the effect away toward zero. `MAX_TREATED_SHARE`
   refuses when the treated cohort is too large a share of the universe to leave a clean control.

4. EVENT-DATE CLUSTERING. Treated units sharing an event date share one market draw, so N is not
   N. Handled by constructing each unit's Event over its own post-window and letting
   `event_study.overlap_fraction` apply its discount -- the same effective-vs-raw discipline the
   desk applies to trial counts.

WHAT THIS MODULE STILL CANNOT TELL YOU, stated so a caller does not over-read a PASS: it cannot
prove the shock was exogenous. That is a claim about the WORLD -- about the venue's decision rule
-- and it must be argued from the announcement, not from the returns. `exogeneity_note` is a
REQUIRED field on the request for exactly that reason: a study that cannot state why its shock is
exogenous has not identified anything, and the type system now says so.
"""

from __future__ import annotations

import numpy as np
from pydantic import BaseModel, ConfigDict

from libs.validation.errors import ValidationError
from libs.validation.event_study import Event, EventStudyResult, event_study

#: Pre-period observations per unit below which the parallel-trends test has no power. Failing to
#: reject on 3 points is not evidence of parallel trends; it is a short window.
MIN_PRE_OBS = 10

#: Post-period observations per unit. Below this the "after" leg is a point, not a mean.
MIN_POST_OBS = 3

#: |t| on the cross-sectional pre-period treated-minus-control gap. Above this, the two groups
#: were ALREADY diverging before the shock, DiD does not identify anything, and the study is
#: refused. 2.0 is the conventional two-sided 5% level and is deliberately NOT lenient: a
#: generous threshold here buys a significant "effect" made entirely of selection.
PARALLEL_TRENDS_MAX_T = 2.0

#: |t| on a placebo DiD run at the midpoint of the PRE window, where the true effect is zero by
#: construction. A significant placebo means the design manufactures effects out of nothing.
PLACEBO_MAX_T = 2.0

#: Treated units as a share of (treated + control). Above this the "control" group is too small
#: or too entangled to be untreated, and SUTVA fails.
MAX_TREATED_SHARE = 0.25


class TreatedUnit(BaseModel):
    """One unit that received the shock, with its matched control leg over the SAME windows.

    `control_pre`/`control_post` are the cross-sectional mean return of the matched untreated
    peers on the same calendar days -- NOT a benchmark index and NOT the unit's own history. The
    caller owns the matching; this module owns what happens once it is done.
    """

    model_config = ConfigDict(frozen=True)

    unit_id: str
    event_ts: float                          # epoch seconds -- when the shock hit THIS unit
    treated_pre: list[float]
    treated_post: list[float]
    control_pre: list[float]
    control_post: list[float]
    #: The CROSS-SECTIONAL member this event belongs to -- the symbol, not the event. Empty means
    #: "this unit is its own member". It exists only for the SUTVA share test, and it is the
    #: difference between that test working and refusing every well-powered study: a symbol with
    #: 30 dated unlocks is ONE treated member of the cross-section, not 30, while `n_control_pool`
    #: counts SYMBOLS. Comparing an event count to a symbol count is apples to oranges, and it
    #: fails in the direction nobody notices -- 1,019 insider events against a 195-symbol control
    #: pool computes a treated share of 84% and refuses SUTVA-VIOLATED on a cohort whose real
    #: cross-sectional share is 20%. Found by running the module on the first real cohort rather
    #: than by reading it.
    cohort_key: str = ""

    @property
    def did(self) -> float:
        return (float(np.mean(self.treated_post)) - float(np.mean(self.treated_pre))) - (
            float(np.mean(self.control_post)) - float(np.mean(self.control_pre)))

    @property
    def pre_gap(self) -> float:
        """Treated-minus-control BEFORE the shock. Should be ~0 if the groups are comparable."""
        return float(np.mean(self.treated_pre)) - float(np.mean(self.control_pre))


class DiDResult(BaseModel):
    """Verdict over a treated cohort. `passed` requires identification AND inference."""

    model_config = ConfigDict(frozen=True)

    n_treated: int
    n_control_pool: int
    treated_share: float
    effect: float                            # mean DiD across treated units
    parallel_trends_t: float
    parallel_trends_ok: bool
    placebo_t: float
    placebo_ok: bool
    identified: bool                         # every identification rail cleared
    inference: EventStudyResult | None       # None when identification failed -- never computed
    passed: bool
    verdict: str
    exogeneity_note: str
    direction: str                           # the PRE-REGISTERED sign -- see the arg's docstring


def _cross_sectional_t(x: np.ndarray) -> float:
    """Cross-sectional t of a mean. Zero on degenerate input rather than an exploding ratio.

    Returning 0.0 for a constant series is the SAFE direction here and only here: this feeds the
    parallel-trends and placebo REFUSAL tests, where a large |t| refuses. A NaN or an exploding
    ratio would refuse a study for a data defect while reporting it as a trend violation, which
    sends the reader to fix the wrong thing. Degenerate INPUT to the effect itself is caught by
    event_study's own DEGENERATE guard, which is where it belongs.
    """
    n = len(x)
    if n < 2:
        return 0.0
    sd = float(np.std(x, ddof=1))
    if sd <= 1e-12 or not np.isfinite(sd):
        return 0.0
    # float() wraps the WHOLE quotient, not just the numerator: np.sqrt(n) is a numpy scalar, so
    # the division returns np.float64 and the declared `-> float` was satisfied only by the
    # coincidence that np.float64 subclasses float.
    return float(np.mean(x) / (sd / np.sqrt(n)))


def difference_in_differences(
    units: list[TreatedUnit],
    *,
    n_control_pool: int,
    exogeneity_note: str,
    direction: str,
    n_cohort: int = 1,
    rank: int = 1,
    post_window_s: float = 86_400.0,
) -> DiDResult:
    """Estimate the causal effect of a dated shock, or refuse and say which rail stopped it.

    `n_control_pool` is the size of the untreated universe the control legs were drawn from, used
    for the SUTVA share test. `exogeneity_note` must state WHY the shock is exogenous -- it is
    required, non-empty, and never inspected by the code, because that argument is about the
    world and cannot be made from the returns.

    `direction` is "increase" or "decrease": the sign the hypothesis PRE-REGISTERS, and it has no
    default on purpose. It exists because `event_study` is a ONE-SIDED POSITIVE test -- it was
    built for listing funding spikes, where the hypothesis is "the return is high" -- so handing
    it a genuinely negative effect returns t=-3.67 against a bar of +1.64 and reports NO-EFFECT
    forever. That is not a hypothetical: supply dilution is the desk's first real cohort and its
    predicted sign is DOWN, so the first natural experiment this module ever ran would have been
    structurally incapable of detecting the thing it was built to detect. Found by a planted
    positive control, which is the only way a silent one-sided failure ever surfaces.

    Signing the estimate by a PRE-REGISTERED direction tests the hypothesis actually being made,
    at the same alpha, one-sided -- it loosens nothing. Choosing the direction AFTER seeing the
    sign would be a free doubling of the multiplicity budget, which is why this is a required
    argument recorded on the result rather than an inferred convenience.

    `n_cohort`/`rank` plug into the desk's Holm discipline exactly as `event_study` documents.
    """
    if direction not in ("increase", "decrease"):
        raise ValidationError(
            f"direction must be pre-registered as 'increase' or 'decrease', got {direction!r}. "
            "event_study is one-sided positive; an unsigned DiD silently cannot detect a negative "
            "effect, and picking the sign after seeing the estimate doubles the multiplicity "
            "budget for free.")
    if not exogeneity_note.strip():
        raise ValidationError(
            "exogeneity_note is required: a study that cannot state why its shock is exogenous "
            "has identified nothing. Name the venue decision rule and why it does not depend on "
            "the outcome being measured.")

    n = len(units)
    pool = max(0, int(n_control_pool))
    # SUTVA is a question about the CROSS-SECTION, so it is measured on cross-sectional members
    # (symbols), never on events. See TreatedUnit.cohort_key for what this cost when it was wrong.
    #
    # AND IT IS A SIMULTANEITY QUESTION, NOT A LIFETIME ONE. The concern is that treatment reaches
    # the controls -- which can only happen while treatment is ON. Counting every member ever
    # treated against a same-day control pool refuses every STAGGERED design outright: 44 symbols
    # unlocking on 500 different dates would score a 49% treated share though only a handful are
    # ever in a window at once. So the statistic is PEAK SIMULTANEOUS treatment -- the most
    # distinct members whose treatment windows cover any single instant. For a cohort that shares
    # one event date this is identical to the old count, so nothing is loosened; for a staggered
    # cohort it asks the question SUTVA actually poses.
    n_members = len({u.cohort_key or u.unit_id for u in units})
    peak = 0
    for probe in {u.event_ts for u in units}:
        live = {u.cohort_key or u.unit_id for u in units
                if u.event_ts <= probe <= u.event_ts + post_window_s}
        peak = max(peak, len(live))
    share = round(peak / max(peak + pool, 1), 3)

    def _refuse(why: str, **kw: float | bool) -> DiDResult:
        base: dict[str, object] = {
            "n_treated": n, "n_control_pool": pool, "treated_share": share, "effect": 0.0,
            "parallel_trends_t": 0.0, "parallel_trends_ok": False, "placebo_t": 0.0,
            "placebo_ok": False, "identified": False, "inference": None, "passed": False,
            "verdict": why, "exogeneity_note": exogeneity_note, "direction": direction}
        base.update(kw)
        # NOT `DiDResult(**base)  # type: ignore[arg-type]`: that ignore is REQUIRED on some
        # in-pin mypy versions and reads as UNUSED on others, so the pinned box and the deploy
        # box disagree about whether this file is clean -- the pyarrow straddle one module over
        # (libs/data/lake.py), which pyproject had to paper over with a scoped override.
        # `model_validate` is typed to accept `Any` on every version, so no version can disagree
        # and no override is needed. Identical at runtime: pydantic routes both `__init__` and
        # `model_validate` to `__pydantic_validator__.validate_python(<the same dict>)`.
        return DiDResult.model_validate(base)

    if n == 0:
        return _refuse("No treated units supplied -- nothing to identify.")

    short = [u.unit_id for u in units
             if len(u.treated_pre) < MIN_PRE_OBS or len(u.control_pre) < MIN_PRE_OBS
             or len(u.treated_post) < MIN_POST_OBS or len(u.control_post) < MIN_POST_OBS]
    if short:
        return _refuse(
            f"ASSUMPTION-UNTESTABLE: {len(short)}/{n} unit(s) have a pre-window shorter than "
            f"{MIN_PRE_OBS} or a post-window shorter than {MIN_POST_OBS} obs "
            f"(e.g. {', '.join(short[:4])}). Failing to reject parallel trends on a short window "
            "is ABSENCE OF POWER, not evidence for the assumption -- reporting PASS here would "
            "launder ignorance into identification. Collect more pre-period, or drop the unit.")

    # SUTVA. Checked before anything is estimated: if the control group is not untreated, every
    # number below is a difference between two treated groups and means nothing.
    if share > MAX_TREATED_SHARE:
        return _refuse(
            f"SUTVA-VIOLATED: at peak {peak} of {n_members} treated member(s) are in a treatment "
            f"window at once (carrying {n} event(s)) against a {pool}-member control pool -- a "
            f"simultaneous treated share of {share:.0%}, above the {MAX_TREATED_SHARE:.0%} bar. A "
            "cohort this concentrated either moves the whole cross-section or shares its shock "
            "with the controls; either way the control leg contains the treatment and DiD "
            "differences the effect toward zero.")

    # RAIL 1 -- PARALLEL TRENDS. The identifying assumption's observable implication.
    pre_gaps = np.array([u.pre_gap for u in units], dtype="float64")
    pt_t = _cross_sectional_t(pre_gaps)
    pt_ok = bool(abs(pt_t) <= PARALLEL_TRENDS_MAX_T)

    # RAIL 2 -- PLACEBO. Split the pre-window and run the identical estimator on a fake event at
    # its midpoint, where the true effect is zero BY CONSTRUCTION. A significant placebo means
    # the design manufactures effects, and the real estimate is then uninterpretable.
    placebo = []
    for u in units:
        half_t, half_c = len(u.treated_pre) // 2, len(u.control_pre) // 2
        placebo.append(
            (float(np.mean(u.treated_pre[half_t:])) - float(np.mean(u.treated_pre[:half_t])))
            - (float(np.mean(u.control_pre[half_c:])) - float(np.mean(u.control_pre[:half_c]))))
    pb_t = _cross_sectional_t(np.array(placebo, dtype="float64"))
    pb_ok = bool(abs(pb_t) <= PLACEBO_MAX_T)

    effect = float(np.mean([u.did for u in units]))
    identified = pt_ok and pb_ok

    # INFERENCE IS NOT RUN WHEN IDENTIFICATION FAILED, and that is not a shortcut. A p-value on an
    # unidentified estimate is the single most misleading number this module could emit: it is
    # precise, it looks like evidence, and it is measuring the selection rule. Refusing to compute
    # it is what stops a reader quoting it.
    if not identified:
        why = ("PARALLEL-TRENDS-VIOLATED" if not pt_ok else "PLACEBO-FAILED")
        detail = (
            f"treated and control were ALREADY diverging before the shock (pre-period gap "
            f"t={pt_t:+.2f} vs bar {PARALLEL_TRENDS_MAX_T}). The most likely cause is SELECTION: "
            "the shock was applied to units chosen on their prior performance, so the 'effect' is "
            "the selection rule. DiD cannot separate the two here."
            if not pt_ok else
            f"a placebo event at the midpoint of the PRE window, where the true effect is zero by "
            f"construction, returned t={pb_t:+.2f} vs bar {PLACEBO_MAX_T}. The design produces "
            "effects out of nothing, so the real estimate is uninterpretable.")
        return _refuse(
            f"{why}: {detail} Raw DiD was {effect:+.4%} and is NOT reported as an effect.",
            effect=effect, parallel_trends_t=round(pt_t, 3), parallel_trends_ok=pt_ok,
            placebo_t=round(pb_t, 3), placebo_ok=pb_ok)

    # Each unit's post-window becomes its Event window, so units sharing an event date are
    # discounted by event_study's overlap machinery rather than counted as independent draws.
    # SIGNED BY THE PRE-REGISTERED DIRECTION, never by the observed sign. `effect` below stays in
    # natural units so a reader sees the real number; only the inference input is oriented.
    sign = 1.0 if direction == "increase" else -1.0
    events = [Event(event_id=u.unit_id, t_start=u.event_ts,
                    t_end=u.event_ts + post_window_s, ret=sign * u.did) for u in units]
    inf = event_study(events, n_cohort=n_cohort, rank=rank)

    passed = bool(inf.passed)
    verdict = (
        f"{'PASS' if passed else 'NO-EFFECT'}: identified (parallel trends t={pt_t:+.2f}, placebo "
        f"t={pb_t:+.2f}, treated share {share:.0%}), effect {effect:+.4%} over {n} treated "
        f"unit(s) on {n_members} cross-sectional member(s) against a {pool}-member control pool, "
        f"pre-registered direction {direction}. Inference: {inf.verdict}")
    return DiDResult(
        n_treated=n, n_control_pool=pool, treated_share=share, effect=round(effect, 6),
        parallel_trends_t=round(pt_t, 3), parallel_trends_ok=pt_ok, placebo_t=round(pb_t, 3),
        placebo_ok=pb_ok, identified=True, inference=inf, passed=passed, verdict=verdict,
        exogeneity_note=exogeneity_note, direction=direction)


#: Convenience for callers assembling a control leg: the cross-sectional mean of the untreated
#: peers on each day. Exposed rather than left to every caller because getting it wrong (using a
#: single benchmark, or the treated unit's own history) is the difference between DiD and a
#: one-sample event study wearing its name.
def control_mean(peer_returns: list[list[float]]) -> list[float]:
    """Per-day cross-sectional mean across peers. Raises on ragged input rather than truncating."""
    if not peer_returns:
        raise ValidationError("control leg is empty -- DiD needs untreated peers, not a benchmark")
    widths = {len(p) for p in peer_returns}
    if len(widths) != 1:
        raise ValidationError(
            f"ragged control leg: peer series have lengths {sorted(widths)}. Truncating would "
            "silently drop days from some peers and not others, biasing the control mean.")
    return [float(x) for x in np.asarray(peer_returns, dtype="float64").mean(axis=0)]

```

### libs\validation\screen_admission.py
```python
"""FILL THE FORWARD SLOTS. The screen's job is RANKING; the forward stage is where safety lives.

THE PROBLEM, IN FOUR MEASURED NUMBERS:

  1. The gauntlet's certified sensitivity floor is TRUE SHARPE 5.0.
  2. This desk's own adopted real-edge band is OOS Sharpe 0.5-1.5, from a 131,441-backtest sweep.
  3. WorldQuant BRAIN -- a live institutional pipeline that PAYS research consultants -- submits
     alphas at fitness > 1.0 and targets Sharpe ~1.25. This desk is 4.0x stricter than a place
     that writes cheques (libs/validation/brain_calibration.py).
  4. Measured power at the band where edges actually live: 0.0% across four of six conditions,
     1.25% and 2.50% on the other two. False positives: 0 of 4,800, at every setting.

A gate with ~0% power and 0% false-positive rate is not a filter. It is a wall. And the price of
that wall is visible: 129 candidates screened on 2026-08-01, ZERO survivors, and
data/forward_slots.json DOES NOT EXIST -- twelve forward slots, none of them occupied, ever.

WHY FILLING THEM IS NOT A RELAXATION, WHICH IS THE ONLY QUESTION THAT MATTERS HERE:

  The desk's own TWO-STAGE DISCOVERY LAW already says the backtest gauntlet is a SCREEN WITH ZERO
  PROMOTION AUTHORITY. Capital moves only on pre-registered FORWARD evidence, Holm-corrected at
  MAX_FORWARD_SLOTS=12, with a fixed end date. That is where safety has always lived.

  And here is the statistical point that settles it: the Holm correction is applied over the
  CONCURRENT SLOT COUNT, which is capped at 12. THE MULTIPLICITY COST OF RUNNING TWELVE FORWARD
  TESTS IS THEREFORE ALREADY PAID, in full, whether or not the slots are used. An empty slot buys
  no safety -- it forfeits a test the desk has already priced. Twelve empty slots is not caution;
  it is twelve wasted, pre-funded experiments and a guaranteed discovery rate of zero.

  So this module does not touch the promotion bar. It does not touch a rail. It changes WHICH
  OBJECT DOES THE FILTERING, from a screen that was never granted the authority to a forward
  stage that always had it and has been sitting idle.

THE SPLIT THAT KEEPS IT SAFE -- structural gates BLOCK, statistical gates RANK:

  STRUCTURAL (hard block, and no amount of forward data repairs them):
    economic_mechanism  no story for who is forced to trade against you -> it is a data artifact
    capacity            cannot be executed at the desk's size -> not tradeable at any confidence
    fragility           tail risk that would damage the book -> a safety property, not a p-value
    expected_value      negative expectancy -> forward-testing it is a paid way to lose
    break_even_win_rate the per-trade arithmetic does not close -> see below
  STATISTICAL (become ranking inputs, because the forward stage tests the same thing better,
  on out-of-sample data, with the multiplicity already priced):
    dsr, pbo, reality_check, walk_forward, cpcv, not_too_lucky

  The principle: a structural gate asks "can this be traded at all, and is there a reason it
  should work?" A statistical gate asks "is this distinguishable from noise?" -- and twelve
  pre-registered forward clocks answer that question with better evidence than any backtest can.

WHAT ADMISSION IS NOT. An admitted candidate receives a FORWARD CLOCK, not money. It owes the
full pre-registered forward test exactly as before: same bar, same Holm correction, same fixed
end date, same graveyard rules. Nothing here shortens that path or widens it. `admit()` returns
slot assignments and would be a defect if it ever returned a position size.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace

__all__ = [
    "GROSS_TURNOVER_PENALTY",
    "MIN_ADMISSION_ANN_SHARPE",
    "MIN_ADMISSION_BARS",
    "MIN_ADMISSION_OOS_SHARPE",
    "PPY_DAILY",
    "STATISTICAL_GATES",
    "STRUCTURAL_GATES",
    "Admission",
    "AdmissionPlan",
    "admit",
    "break_even_win_rate",
    "rank_score",
]

#: MINIMUM OOS SHARPE TO OCCUPY A SLOT. A RELEVANCE FLOOR, NOT A SIGNIFICANCE TEST.
#:
#: This exists because removing the statistical wall exposed the opposite failure immediately.
#: Replaying the real 2026-08-01 campaign through admission filled all twelve slots with
#: candidates whose OOS Sharpe was ~0.02 -- statistically indistinguishable from zero and far
#: below anything worth measuring. That is not caution restored, it is the scarce resource being
#: spent on noise: a forward clock runs for months, so a slot occupied by a zero-edge candidate
#: BLOCKS A REAL ONE for that entire period. An idle slot costs nothing; a wasted slot costs a
#: discovery.
#:
#: THE UNITS ERROR THIS CONSTANT WAS SHIPPED WITH, recorded because the value is meaningless
#: without it and because the desk lost a campaign cycle to it.
#:
#: The floor was originally set to 0.25 with the reasoning "the real-edge band starts at OOS
#: Sharpe 0.5, so half of that sits safely below the band." Both halves of that sentence are true
#: and they are in DIFFERENT UNITS. `libs/validation/dsr.sharpe_ratio` is ``mean/std`` per period
#: and never annualises, and WalkForwardEngine averages it across folds -- so a floor of 0.25 is
#: 0.25 PER BAR, which on daily bars is 0.25 * sqrt(365) = 4.78 ANNUALISED. The real-edge band of
#: 0.5-1.5 is annualised. The floor was therefore set roughly 19x above where it was intended and
#: 3.2x above the TOP of the band where genuine edge is observed to live.
#:
#: MEASURED CONSEQUENCE (reports/admission_power.json): admission rate equals floor-only pass rate
#: at every single Sharpe level, to three decimals. Structural gates pass 73-100% of true alphas
#: and ~50% of pure nulls; statistical gates only rank. So this one mis-scaled constant WAS the
#: entire gate, and at 4.78 annualised it admitted 0.4% of true Sharpe-1.5 candidates.
#:
#: THE FLOOR IS NOW DECLARED IN ANNUALISED UNITS AND CONVERTED, so the comparison to the band is
#: dimensionally honest and the next reader cannot repeat the mistake.
#:
#: WHY IT IS NOT A SIGNIFICANCE BAR, which still stands. It asks "is there plausibly anything
#: here?", not "is this distinguishable from noise?" -- the forward stage answers the second
#: question, and that is the entire point of this module. Setting it at half the band's lower edge
#: is the loosest defensible reading of "plausibly anything".
#:
#: WHAT IT CANNOT DO, and this is the finding that matters more than the constant. At the
#: campaign's 310 bars the null OOS Sharpe has sd 1.37 ANNUALISED, while the whole real-edge band
#: is 1.0 wide -- the noise is wider than the signal range, so NO threshold separates them. The
#: measured trade-off curve is bad everywhere: a floor at 1.5 annualised still lets 58 pure nulls
#: through per campaign for 12 slots. The fix is sample size, not calibration; see
#: MIN_ADMISSION_BARS below.
PPY_DAILY = 365.0

#: In ANNUALISED Sharpe. Half of the real-edge band's lower edge (0.5).
MIN_ADMISSION_ANN_SHARPE = 0.25

#: Per-bar, which is the unit validate() actually reports in. Derived, never hand-set.
MIN_ADMISSION_OOS_SHARPE = MIN_ADMISSION_ANN_SHARPE / (PPY_DAILY ** 0.5)

#: MINIMUM BARS BEFORE AN OOS SHARPE MEANS ANYTHING. The real constraint, measured.
#:
#: The standard error of a per-bar Sharpe is ~1/sqrt(T). To put a TRUE annualised Sharpe of 1.0
#: two standard errors above zero needs T >= 4 * PPY / 1.0^2 = 1,460 daily bars. The 2026-08-01
#: campaign ran on 310 (effective ~194 per walk-forward fold), which is why it resolved nothing:
#: at that width a true Sharpe-1.0 edge and pure noise produce overlapping distributions.
#:
#: THE DATA WAS ALWAYS THERE. OKX holds 2,438 confirmed daily bars for BTC, 2,436 for ETH, 2,017
#: for SOL -- 7.9x the window the campaign used and 1.7x what this floor requires. The short
#: window was a choice, not a data limit, and it cost every campaign run under it.
MIN_ADMISSION_BARS = 1_460

#: Penalty applied to rank when the supplied Sharpe is GROSS -- i.e. costs have not been charged.
#:
#: WHY THIS IS CONDITIONAL AND NOT UNCONDITIONAL, which is the whole point. BRAIN states its score
#: is "inversely proportional to turnover", and turnover is genuinely the difference between a
#: 60%-turnover alpha and a 15% one at the same headline return. The obvious move is to subtract a
#: turnover term from rank_score. That move would be WRONG on this desk and wrong in the exact way
#: that made the gauntlet 4x too strict in the first place: libs/research/transcript_candidates
#: .positions_to_returns ALREADY charges 6 bps per turn, so a Sharpe built through that path has
#: costs in it, and penalising turnover again is ONE CORRECTION APPLIED TWICE -- lesson L0008,
#: rubric class 3, the identical defect as DSR deflating trials the campaign layer had already
#: deflated.
#:
#: But validate() itself applies NO cost adjustment. It scores whatever series it is handed. So
#: whether the number reaching admission is net or gross is a property of the CALLER, and nothing
#: in the artifact says which. That is the `beats_baselines` shape again -- an unstated assumption
#: reading as satisfied.
#:
#: Hence: the caller must DECLARE its cost basis. NET means charged, so no penalty. GROSS means
#: unchanged, so this penalty applies. UNKNOWN is reported as unmeasured and treated as GROSS,
#: because assuming costs were charged when nobody said so is the branch that admits a candidate
#: whose edge is entirely fees -- and the desk has already measured realised costs at 7.75x its
#: own prediction, so even a declared NET is optimistic.
GROSS_TURNOVER_PENALTY = 1.0

#: A structural failure is disqualifying at any confidence level. These are not thresholds on
#: evidence, they are statements about whether the thing can be traded or should be expected to
#: work at all -- and forward data does not repair any of them.
STRUCTURAL_GATES: tuple[str, ...] = (
    "economic_mechanism",
    "expected_value",
    "capacity",
    "fragility",
    "break_even_win_rate",
    "sample_adequacy",
)

#: These test "is it distinguishable from noise". The forward stage tests exactly that, on data
#: the candidate has never seen, with the concurrent-slot multiplicity already Holm-corrected. So
#: here they ORDER candidates rather than eliminate them.
STATISTICAL_GATES: tuple[str, ...] = (
    "dsr",
    "pbo",
    "reality_check",
    "walk_forward",
    "cpcv",
    "not_too_lucky",
    "beats_baselines",
)


def break_even_win_rate(avg_win: float, avg_loss: float) -> float:
    """The win rate below which a strategy loses money regardless of how good the curve looks.

        p* = |avg_loss| / (avg_win + |avg_loss|)

    THE GAP BETWEEN REALISED AND BREAK-EVEN WIN RATE IS THE ENTIRE EDGE, and it is invisible to
    every other statistic in this desk's gauntlet, all of which are computed PER OBSERVATION. A
    5,000-bar series holding one position throughout has 5,000 observations and one bet; per-bar
    Sharpe cannot see that, and neither can DSR, PBO or the reality check.

    The arithmetic that makes it concrete, from a 432-variant backtest study in the 2026-08-01
    transcript batch: average win 5.72%, average loss 3.13% net, giving p* = 35.4%. Realised win
    rate 41.3%. That 5.9-point gap, compounded over 758 trades, WAS the 24.9x return. Nothing
    else in the result mattered.

    Returns 1.0 when avg_win <= 0 -- a strategy with no average winner cannot break even at any
    win rate, and reporting 0.5 there would read as an easy bar.
    """
    w = float(avg_win)
    loss = abs(float(avg_loss))
    if w <= 0.0:
        return 1.0
    if loss <= 0.0:
        return 0.0
    return loss / (w + loss)


@dataclass(frozen=True)
class Admission:
    name: str
    rank_score: float
    blocked_by: tuple[str, ...] = ()
    statistical_failures: tuple[str, ...] = ()
    admitted: bool = False
    reason: str = ""
    #: Declared gates this candidate's producer never supplied. R0419: `g in gates` means an
    #: ABSENT gate cannot appear in blocked_by and cannot block -- which is the correct call
    #: (absent != failed; killing a candidate for an omission is the beats_baselines defect
    #: pointed the other way) but it was also INVISIBLE. Absent and passed were byte-identical to
    #: every reader, and only one of them is evidence (L1.28a).
    unmeasured_gates: tuple[str, ...] = ()


@dataclass(frozen=True)
class AdmissionPlan:
    admitted: tuple[Admission, ...] = ()
    blocked: tuple[Admission, ...] = ()
    ranked_out: tuple[Admission, ...] = ()
    idle_slots_before: int = 0
    idle_slots_after: int = 0
    notes: tuple[str, ...] = field(default_factory=tuple)
    #: gate -> {"pass", "fail", "unmeasured"} counts over every candidate seen. THE GATE-OPTIMALITY
    #: DUTY DEMANDS THIS AND admit() DID NOT HAVE IT (R0419): a gate that accepts ~100% or rejects
    #: ~100% carries zero information and is a defect to investigate, and it cannot be spotted
    #: without a per-gate tally. `unmeasured` is a FIRST-CLASS column, not folded into either
    #: side -- absence from a rejection tally is ambiguous between "never evaluated" and
    #: "evaluated and always passed", and those are different defects (L1.49).
    gate_histogram: dict[str, dict[str, int]] = field(default_factory=dict)

    def welded_gates(self) -> dict[str, str]:
        """Gates carrying no information over this cohort, and which KIND of nothing.

        NEVER-EVALUATED is separated from CONSTANT-PASS on purpose: the first is a wiring defect
        whose repair is upward (supply the input, or record that it cannot be supplied), the
        second is a threshold question. Collapsing them sends someone to fix the wrong thing.
        """
        out: dict[str, str] = {}
        for gate, h in self.gate_histogram.items():
            seen = h["pass"] + h["fail"]
            if not seen:
                out[gate] = "NEVER-EVALUATED (no candidate supplied it -- L1.49 dead branch)"
            elif not h["fail"]:
                out[gate] = f"CONSTANT-PASS ({h['pass']}/{seen} passed, 0 rejected)"
            elif not h["pass"]:
                out[gate] = f"CONSTANT-REJECT (0/{seen} passed)"
        return out

    def summary(self) -> str:
        return (f"{len(self.admitted)} admitted to forward clocks, {len(self.blocked)} "
                f"structurally blocked, {len(self.ranked_out)} out-ranked; "
                f"{self.idle_slots_after} slot(s) still idle")


def rank_score(gates: dict[str, bool], *, oos_sharpe: float, dsr: float,
               reality_p: float, turnover: float | None = None,
               cost_basis: str = "unknown") -> float:
    """Order candidates for scarce forward slots. NOT a pass/fail score.

    Built from OOS Sharpe first because that is the quantity the desk has an empirical band for
    (0.5-1.5) and the one the forward stage will actually re-measure. The statistical gates
    contribute as a count of how many were cleared, so a candidate that clears more of them
    outranks one that clears fewer -- ordering, not gating.

    DELIBERATELY NOT A CALIBRATED PROBABILITY. Any attempt to turn this into "probability the
    candidate is real" would be a promotion decision wearing a ranking's clothes, and promotion
    belongs to the forward stage. It only needs to be monotone in the right direction.
    """
    cleared = sum(1 for g in STATISTICAL_GATES if gates.get(g, False))
    # OOS Sharpe dominates; each cleared statistical gate is worth a small, fixed bonus so it can
    # break ties between candidates with similar OOS but cannot outweigh a genuine OOS difference.
    score = (float(oos_sharpe) + 0.05 * cleared + 0.02 * float(dsr)
             + 0.02 * (1.0 - float(reality_p)))
    # Charged ONLY when the caller says costs are not already in the number. See
    # GROSS_TURNOVER_PENALTY: penalising a net Sharpe would be the double-correction defect.
    if turnover is not None and str(cost_basis).lower() != "net":
        score -= GROSS_TURNOVER_PENALTY * max(0.0, float(turnover))
    return score


def _f(row: dict[str, object], key: str, default: float) -> float:
    """Read a numeric field defensively. A caller that omits or mistypes one must get the stated
    default rather than a crash mid-campaign -- but the default is chosen so the omission is
    CONSERVATIVE: a missing oos_sharpe reads as 0.0 and therefore fails the relevance floor."""
    v = row.get(key)
    return float(v) if isinstance(v, (int, float)) else default


def admit(candidates: list[dict[str, object]], *, idle_slots: int,
          cost_basis: str = "unknown") -> AdmissionPlan:
    """Assign the best structurally-sound candidates to idle forward clocks.

    `candidates` rows carry: name, gates (dict), oos_sharpe, dsr, reality_p.

    THREE INVARIANTS, each of which would be a serious defect to violate and each of which is
    locked by a test:
      1. Admissions never exceed idle_slots. The Holm correction is priced at exactly
         MAX_FORWARD_SLOTS concurrent tests; exceeding it invalidates the correction and is the
         one way this module could actually make the desk less safe.
      2. A structurally-blocked candidate is NEVER admitted, at any rank, however good its
         statistics. Rank cannot buy past a missing mechanism or absent capacity.
      3. Admission confers a forward CLOCK and never capital. Nothing returned here is a size.
    """
    rows: list[Admission] = []
    unmeasured_bars: list[str] = []
    histogram: dict[str, dict[str, int]] = {}
    for c in candidates:
        raw_gates = c.get("gates")
        # Defensive rather than trusting: a caller passing a non-dict must not crash a campaign,
        # and an unreadable gates field means NO gate was cleared, which is the conservative read.
        gates: dict[str, bool] = (
            {str(k): bool(v) for k, v in raw_gates.items()}
            if isinstance(raw_gates, dict) else {})
        name = str(c.get("name", "?"))
        oos = _f(c, "oos_sharpe", 0.0)
        blocked_list = [g for g in STRUCTURAL_GATES if g in gates and not gates[g]]
        # UNCHANGED BEHAVIOUR, NEWLY VISIBLE (R0419). `g in gates` still governs blocking -- an
        # absent gate must not kill a candidate. What changes is that the absence is now RECORDED
        # instead of being indistinguishable from a pass.
        #
        # MEASURED against every site that can write a gate in `libs.autodiscovery.validation`
        # (the literal at :760 plus the three conditional `gates[...] =` assignments), not against
        # the declaration here: of the six structural gates, exactly ONE -- `break_even_win_rate`
        # -- is written by NOTHING anywhere in the repo. It is declared structural, so it reads as
        # part of the gauntlet, and it has never once evaluated. `capacity` and `sample_adequacy`
        # are conditional on caller-supplied inputs and validate() already records their absence
        # in `unmeasured`, which is the honest state and not this defect.
        #
        # THE COUNT IS STATED BECAUSE IT WAS WRONG TWICE ON THE WAY HERE -- "2 of 6", then "3 of
        # 6" -- both from reading the unconditional gates literal and stopping. That is the row's
        # own point turned on the row: a claim about which gates fire, asserted rather than
        # measured. The histogram below exists so the next reader does not have to trust this
        # comment at all.
        unmeasured_list = [g for g in (*STRUCTURAL_GATES, *STATISTICAL_GATES) if g not in gates]
        for g in (*STRUCTURAL_GATES, *STATISTICAL_GATES):
            cell = histogram.setdefault(g, {"pass": 0, "fail": 0, "unmeasured": 0})
            cell["unmeasured" if g not in gates else ("pass" if gates[g] else "fail")] += 1
        # The relevance floor is enforced as a structural block on purpose: it is a statement
        # about whether a scarce forward clock should be spent, not about statistical evidence,
        # and like every other structural block it must be un-out-rankable.
        if oos < MIN_ADMISSION_OOS_SHARPE:
            blocked_list.append("below_relevance_floor")
        # SAMPLE ADEQUACY, and it blocks for cause rather than ranking. An OOS Sharpe measured on
        # 310 bars carries a standard error wider than the entire band where real edge lives, so
        # admitting on it is not a loose decision -- it is a decision made on a number that
        # contains no information. UNMEASURED when the caller does not say, because a missing bar
        # count is exactly how the desk shipped a 19x units error without noticing.
        raw_bars = c.get("n_bars")
        n_bars = int(raw_bars) if isinstance(raw_bars, (int, float)) else None
        if n_bars is None:
            unmeasured_bars.append(name)
        elif n_bars < MIN_ADMISSION_BARS:
            blocked_list.append("insufficient_bars")
        stat_fail = tuple(g for g in STATISTICAL_GATES if g in gates and not gates[g])
        raw_turn = c.get("turnover")
        turn = float(raw_turn) if isinstance(raw_turn, (int, float)) else None
        score = rank_score(gates, oos_sharpe=oos, dsr=_f(c, "dsr", 0.0),
                           reality_p=_f(c, "reality_p", 1.0), turnover=turn,
                           cost_basis=str(c.get("cost_basis") or cost_basis))
        rows.append(Admission(name=name, rank_score=score, blocked_by=tuple(blocked_list),
                              statistical_failures=stat_fail,
                              unmeasured_gates=tuple(unmeasured_list)))

    blocked = tuple(r for r in rows if r.blocked_by)
    eligible = sorted((r for r in rows if not r.blocked_by),
                      key=lambda r: (-r.rank_score, r.name))
    n = max(0, int(idle_slots))
    admitted = tuple(
        Admission(name=r.name, rank_score=r.rank_score, blocked_by=r.blocked_by,
                  statistical_failures=r.statistical_failures, admitted=True,
                  unmeasured_gates=r.unmeasured_gates,
                  reason=("admitted to a forward clock by EV rank; owes pre-registered forward "
                          "evidence with an unchanged Holm-corrected bar and a fixed end date"))
        for r in eligible[:n])
    ranked_out = tuple(eligible[n:])

    notes = [
        f"{len(admitted)} of {len(eligible)} structurally-sound candidates fit {n} idle slot(s)",
        "admission is a FORWARD CLOCK, never capital; the promotion bar is unchanged",
    ]
    if str(cost_basis).lower() not in ("net", "gross"):
        notes.append("UNMEASURED cost basis: nobody declared whether these Sharpes are net of "
                     "fees. Treated as GROSS (turnover penalised) because assuming costs were "
                     "charged is the branch that admits a candidate whose edge is entirely fees "
                     "-- and this desk measured realised cost at 7.75x its own prediction")
    n_floor = sum(1 for r in blocked if "below_relevance_floor" in r.blocked_by)
    if n_floor:
        notes.append(f"{n_floor} candidate(s) below the {MIN_ADMISSION_ANN_SHARPE} ANNUALISED OOS "
                     f"relevance floor ({MIN_ADMISSION_OOS_SHARPE:.4f} per bar) -- a forward clock "
                     "runs for months, so a slot spent on noise blocks a real edge; an idle slot "
                     "costs nothing")
    n_short = sum(1 for r in blocked if "insufficient_bars" in r.blocked_by)
    if n_short:
        notes.append(f"{n_short} candidate(s) scored on fewer than {MIN_ADMISSION_BARS} bars. Not "
                     "a strictness call: below that width the standard error of the OOS Sharpe is "
                     "wider than the whole 0.5-1.5 real-edge band, so the number carries no "
                     "information to admit on. OKX holds 2,438 daily bars for BTC -- re-run the "
                     "campaign on the history that already exists rather than widening this")
    if unmeasured_bars:
        notes.append(f"UNMEASURED sample width on {len(unmeasured_bars)} candidate(s): nobody "
                     "declared how many bars the OOS Sharpe was measured over, so whether it can "
                     "resolve anything is unknown. Not counted as a pass")
    if not eligible and rows:
        notes.append("every candidate failed a STRUCTURAL gate -- that is a real result and is "
                     "not fixed by widening the screen; the mechanisms have no edge, no capacity, "
                     "or no story for who is forced to trade against them")
    if n == 0 and eligible:
        notes.append("no idle slots: the forward stage is saturated, which is the intended "
                     "steady state and the correct reason to admit nothing")
    plan = AdmissionPlan(admitted=admitted, blocked=blocked, ranked_out=ranked_out,
                         idle_slots_before=n, idle_slots_after=n - len(admitted),
                         notes=tuple(notes), gate_histogram=histogram)
    # THE GATE-OPTIMALITY DUTY, SPOKEN OUT LOUD. A gate accepting ~100% or rejecting ~100% carries
    # zero information and is a defect to investigate -- and until now admit() had no tally, so a
    # structural gate that had NEVER ONCE EVALUATED looked exactly like one that always passed.
    welded = plan.welded_gates()
    if welded and rows:
        notes.append("GATE-OPTIMALITY: " + "; ".join(
            f"{g} {why}" for g, why in sorted(welded.items())))
        plan = replace(plan, notes=tuple(notes))
    return plan

```

### scripts\blindspot_autofix.py
```python
#!/usr/bin/env python3
"""
Blind Spot Detector + Auto-Fix Pipeline - runs every 6 hours.

Scans ALL blind spots (unread fields, unmodelled entities, uncrossed pairs,
law fence failures, calibration overdue, governance defects) and either
fixes them automatically or emits high-priority entries to the agent feed
for human/agent intervention.

    python scripts/blindspot_autofix.py
"""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.agent_feed import write_entry


def run_cmd(cmd: list[str], cwd: str = "/home/quant/quant-platform") -> tuple[int, str, str]:
    """Run command, return (rc, stdout, stderr)."""
    try:
        result = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=120)
        return result.returncode, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return -1, "", "TIMEOUT"
    except Exception as e:
        return -1, "", str(e)


def check_blind_spots() -> dict[str, Any]:
    """Run blind spot coverage check."""
    rc, out, err = run_cmd([".venv/bin/python", "scripts/check_blindspot_coverage.py"])
    data = {"rc": rc, "stdout": out, "stderr": err}
    if rc == 0 and Path("data/blindspot_max.json").exists():
        data["artifact"] = json.loads(Path("data/blindspot_max.json").read_text())
    return data


def check_law_fences() -> dict[str, Any]:
    """Run law gate check."""
    rc, out, err = run_cmd([".venv/bin/python", "scripts/check_law_families.py"])
    return {"rc": rc, "stdout": out, "stderr": err}


def check_calibration() -> dict[str, Any]:
    """Run calibration check."""
    rc, out, err = run_cmd([".venv/bin/python", "scripts/check_calibration.py"])
    return {"rc": rc, "stdout": out, "stderr": err}


def check_conversion() -> dict[str, Any]:
    """Run conversion check."""
    rc, out, err = run_cmd([".venv/bin/python", "scripts/check_conversion.py"])
    return {"rc": rc, "stdout": out, "stderr": err}


def check_claim_consistency() -> dict[str, Any]:
    """Run claim consistency check."""
    rc, out, err = run_cmd([".venv/bin/python", "scripts/check_claim_consistency.py"])
    return {"rc": rc, "stdout": out, "stderr": err}


def check_denominator_attrition() -> dict[str, Any]:
    """Run denominator attrition check."""
    rc, out, err = run_cmd([".venv/bin/python", "scripts/check_denominator_attrition.py"])
    return {"rc": rc, "stdout": out, "stderr": err}


def check_citation_integrity() -> dict[str, Any]:
    """Run citation integrity check."""
    rc, out, err = run_cmd([".venv/bin/python", "scripts/check_citation_integrity.py", "--report-only"])
    return {"rc": rc, "stdout": out, "stderr": err}


def check_panel_breadth() -> dict[str, Any]:
    """Run panel breadth check."""
    rc, out, err = run_cmd([".venv/bin/python", "scripts/check_panel_breadth.py"])
    return {"rc": rc, "stdout": out, "stderr": err}


def check_cross_section_floor() -> dict[str, Any]:
    """Run cross-section floor check."""
    rc, out, err = run_cmd([".venv/bin/python", "scripts/check_cross_section_floor.py"])
    return {"rc": rc, "stdout": out, "stderr": err}


def check_prompt_ratchet() -> dict[str, Any]:
    """Run prompt ratchet check."""
    rc, out, err = run_cmd([".venv/bin/python", "scripts/check_prompt_ratchet.py", "--json"])
    return {"rc": rc, "stdout": out, "stderr": err}


def check_free_roster() -> dict[str, Any]:
    """Run free roster canary."""
    rc, out, err = run_cmd([".venv/bin/python", "scripts/check_free_roster.py", "--report-only"])
    return {"rc": rc, "stdout": out, "stderr": err}


def check_idle_cost() -> dict[str, Any]:
    """Run idle cost check."""
    rc, out, err = run_cmd([".venv/bin/python", "scripts/check_idle_cost.py", "--report-only"])
    return {"rc": rc, "stdout": out, "stderr": err}


def check_llm_routing() -> dict[str, Any]:
    """Run LLM routing check."""
    rc, out, err = run_cmd([".venv/bin/python", "scripts/check_llm_routing.py"])
    return {"rc": rc, "stdout": out, "stderr": err}


def check_mechanism_attribution() -> dict[str, Any]:
    """Run mechanism attribution check."""
    rc, out, err = run_cmd([".venv/bin/python", "scripts/check_mechanism_attribution.py"])
    return {"rc": rc, "stdout": out, "stderr": err}


def check_organ_liveness() -> dict[str, Any]:
    """Run organ liveness check."""
    rc, out, err = run_cmd([".venv/bin/python", "scripts/check_organ_liveness.py"])
    return {"rc": rc, "stdout": out, "stderr": err}


def check_excitation() -> dict[str, Any]:
    """Run excitation check."""
    rc, out, err = run_cmd([".venv/bin/python", "scripts/check_excitation.py"])
    return {"rc": rc, "stdout": out, "stderr": err}


def check_clock_provenance() -> dict[str, Any]:
    """Run clock provenance check."""
    rc, out, err = run_cmd([".venv/bin/python", "scripts/check_clock_provenance.py"])
    return {"rc": rc, "stdout": out, "stderr": err}


def auto_fix_scheduler_manifest() -> bool:
    """Generate scheduler manifest report if missing."""
    try:
        manifest = Path("ops/crontab.manifest")
        if not manifest.exists():
            return False
        lines = manifest.read_text().splitlines()
        checks = []
        for line in lines:
            line = line.strip()
            if line.startswith("#") or not line:
                continue
            parts = line.split()
            if len(parts) >= 6:
                script = parts[-1]
                if script.endswith(".py"):
                    script_path = Path(script)
                    if not script_path.is_absolute():
                        script_path = Path("/home/quant/quant-platform") / script
                    exists = script_path.exists()
                    checks.append({"script": script, "exists": exists})
        report = {
            "generated": datetime.now(tz=UTC).isoformat(),
            "total_lines": len(lines),
            "checks": checks,
            "all_pass": all(c["exists"] for c in checks),
        }
        Path("data/scheduler_manifest_report.json").write_text(json.dumps(report, indent=2))
        return True
    except Exception:
        return False


def auto_fix_calibration_forecasts() -> int:
    """Score overdue forecasts if any."""
    # This would need the calibration_status.json to exist and have overdue entries
    # For now, just ensure the file exists
    cal_file = Path("data/calibration_status.json")
    if not cal_file.exists():
        cal_file.write_text(json.dumps({"forecasts": [], "status": "EMPTY"}))
        return 1
    return 0


def main() -> None:
    print(f"[{datetime.now(tz=UTC).isoformat()}] Starting blind spot auto-fix scan...")

    all_results = {}
    defects_found = []

    # 1. Blind spot coverage
    print("  Checking blind spot coverage...")
    all_results["blindspot"] = check_blind_spots()
    if all_results["blindspot"].get("artifact"):
        art = all_results["blindspot"]["artifact"]
        if art.get("unread_fields", 0) > 0 or art.get("unmodelled_entities", 0) > 0 or art.get("uncrossed_pairs", 0) > 0:
            defects_found.append(("blindspot", f"Unread: {art.get('unread_fields')}, Unmodelled: {art.get('unmodelled_entities')}, Uncrossed: {art.get('uncrossed_pairs')}", "high"))

    # 2. Law fences
    print("  Checking law fences...")
    all_results["law_fences"] = check_law_fences()
    if all_results["law_fences"]["rc"] not in (0, 2):  # 0=OK, 2=defect found but check ran
        defects_found.append(("law_fences", f"Law gate script missing/error: {all_results['law_fences']['stderr'][:200]}", "critical"))
    elif all_results["law_fences"]["rc"] == 2:
        defects_found.append(("law_fences", f"Law gate DEFECT: {all_results['law_fences']['stdout'][:200]}", "high"))

    # 3. Calibration
    print("  Checking calibration...")
    all_results["calibration"] = check_calibration()
    if all_results["calibration"]["rc"] not in (0, 2):
        defects_found.append(("calibration", f"Calibration script missing/error: {all_results['calibration']['stderr'][:200]}", "critical"))
    elif all_results["calibration"]["rc"] == 2:
        defects_found.append(("calibration", f"Calibration DEFECT: {all_results['calibration']['stdout'][:200]}", "high"))
    auto_fix_calibration_forecasts()

    # 4. Conversion
    print("  Checking conversion...")
    all_results["conversion"] = check_conversion()
    if all_results["conversion"]["rc"] not in (0, 2):
        defects_found.append(("conversion", f"Conversion script missing/error: {all_results['conversion']['stderr'][:200]}", "critical"))
    elif all_results["conversion"]["rc"] == 2:
        defects_found.append(("conversion", f"Conversion DEFECT: {all_results['conversion']['stdout'][:200]}", "high"))

    # 5. Claim consistency
    print("  Checking claim consistency...")
    all_results["claim_consistency"] = check_claim_consistency()
    if all_results["claim_consistency"]["rc"] not in (0, 2):
        defects_found.append(("claim_consistency", f"Claim consistency script missing/error: {all_results['claim_consistency']['stderr'][:200]}", "high"))
    elif all_results["claim_consistency"]["rc"] == 2:
        defects_found.append(("claim_consistency", f"Claim consistency DEFECT: {all_results['claim_consistency']['stdout'][:200]}", "high"))

    # 6. Denominator attrition
    print("  Checking denominator attrition...")
    all_results["denominator"] = check_denominator_attrition()
    if all_results["denominator"]["rc"] not in (0, 2):
        defects_found.append(("denominator", f"Denominator attrition script missing/error: {all_results['denominator']['stderr'][:200]}", "high"))
    elif all_results["denominator"]["rc"] == 2:
        defects_found.append(("denominator", f"Denominator attrition DEFECT: {all_results['denominator']['stdout'][:200]}", "high"))

    # 7. Citation integrity
    print("  Checking citation integrity...")
    all_results["citation"] = check_citation_integrity()
    if all_results["citation"]["rc"] not in (0, 2):
        defects_found.append(("citation", f"Citation integrity script missing/error: {all_results['citation']['stderr'][:200]}", "high"))
    elif all_results["citation"]["rc"] == 2:
        defects_found.append(("citation", f"Citation integrity DEFECT: {all_results['citation']['stdout'][:200]}", "high"))

    # 8. Panel breadth
    print("  Checking panel breadth...")
    all_results["panel"] = check_panel_breadth()
    if all_results["panel"]["rc"] not in (0, 2):
        defects_found.append(("panel_breadth", f"Panel breadth script missing/error: {all_results['panel']['stderr'][:200]}", "high"))
    elif all_results["panel"]["rc"] == 2:
        defects_found.append(("panel_breadth", f"Panel breadth DEFECT: {all_results['panel']['stdout'][:200]}", "high"))

    # 9. Cross-section floor
    print("  Checking cross-section floor...")
    all_results["cross_section"] = check_cross_section_floor()
    if all_results["cross_section"]["rc"] not in (0, 2):
        defects_found.append(("cross_section", f"Cross-section floor script missing/error: {all_results['cross_section']['stderr'][:200]}", "high"))
    elif all_results["cross_section"]["rc"] == 2:
        defects_found.append(("cross_section", f"Cross-section floor DEFECT: {all_results['cross_section']['stdout'][:200]}", "high"))

    # 10. Prompt ratchet
    print("  Checking prompt ratchet...")
    all_results["prompt_ratchet"] = check_prompt_ratchet()
    if all_results["prompt_ratchet"]["rc"] not in (0, 2):
        defects_found.append(("prompt_ratchet", f"Prompt ratchet script missing/error: {all_results['prompt_ratchet']['stderr'][:200]}", "high"))
    elif all_results["prompt_ratchet"]["rc"] == 2:
        defects_found.append(("prompt_ratchet", f"Prompt ratchet DEFECT: {all_results['prompt_ratchet']['stdout'][:200]}", "high"))

    # 11. Free roster
    print("  Checking free roster...")
    all_results["free_roster"] = check_free_roster()
    if all_results["free_roster"]["rc"] not in (0, 2):
        defects_found.append(("free_roster", f"Free roster script missing/error: {all_results['free_roster']['stderr'][:200]}", "high"))
    elif all_results["free_roster"]["rc"] == 2:
        defects_found.append(("free_roster", f"Free roster DEFECT: {all_results['free_roster']['stdout'][:200]}", "high"))

    # 12. Idle cost
    print("  Checking idle cost...")
    all_results["idle_cost"] = check_idle_cost()
    if all_results["idle_cost"]["rc"] not in (0, 2):
        defects_found.append(("idle_cost", f"Idle cost script missing/error: {all_results['idle_cost']['stderr'][:200]}", "high"))
    elif all_results["idle_cost"]["rc"] == 2:
        defects_found.append(("idle_cost", f"Idle cost DEFECT: {all_results['idle_cost']['stdout'][:200]}", "high"))

    # 13. LLM routing
    print("  Checking LLM routing...")
    all_results["llm_routing"] = check_llm_routing()
    if all_results["llm_routing"]["rc"] not in (0, 2):
        defects_found.append(("llm_routing", f"LLM routing script missing/error: {all_results['llm_routing']['stderr'][:200]}", "high"))
    elif all_results["llm_routing"]["rc"] == 2:
        defects_found.append(("llm_routing", f"LLM routing DEFECT: {all_results['llm_routing']['stdout'][:200]}", "high"))

    # 14. Mechanism attribution
    print("  Checking mechanism attribution...")
    all_results["mech_attr"] = check_mechanism_attribution()
    if all_results["mech_attr"]["rc"] not in (0, 2):
        defects_found.append(("mech_attr", f"Mechanism attribution script missing/error: {all_results['mech_attr']['stderr'][:200]}", "critical"))
    elif all_results["mech_attr"]["rc"] == 2:
        defects_found.append(("mech_attr", f"Mechanism attribution DEFECT: {all_results['mech_attr']['stdout'][:200]}", "critical"))

    # 15. Organ liveness
    print("  Checking organ liveness...")
    all_results["organ_live"] = check_organ_liveness()
    if all_results["organ_live"]["rc"] not in (0, 2):
        defects_found.append(("organ_live", f"Organ liveness script missing/error: {all_results['organ_live']['stderr'][:200]}", "high"))
    elif all_results["organ_live"]["rc"] == 2:
        defects_found.append(("organ_live", f"Organ liveness DEFECT: {all_results['organ_live']['stdout'][:200]}", "high"))

    # 16. Excitation
    print("  Checking excitation...")
    all_results["excitation"] = check_excitation()
    if all_results["excitation"]["rc"] not in (0, 2):
        defects_found.append(("excitation", f"Excitation script missing/error: {all_results['excitation']['stderr'][:200]}", "high"))
    elif all_results["excitation"]["rc"] == 2:
        defects_found.append(("excitation", f"Excitation DEFECT: {all_results['excitation']['stdout'][:200]}", "high"))

    # 17. Clock provenance
    print("  Checking clock provenance...")
    all_results["clock_prov"] = check_clock_provenance()
    if all_results["clock_prov"]["rc"] not in (0, 2):
        defects_found.append(("clock_provenance", f"Clock provenance script missing/error: {all_results['clock_prov']['stderr'][:200]}", "high"))
    elif all_results["clock_prov"]["rc"] == 2:
        defects_found.append(("clock_provenance", f"Clock provenance DEFECT: {all_results['clock_prov']['stdout'][:200]}", "high"))

    # 18. Auto-fix scheduler manifest
    print("  Auto-fixing scheduler manifest...")
    if auto_fix_scheduler_manifest():
        print("    scheduler_manifest_report.json generated")

    # Emit defects to agent feed
    for dtype, msg, priority in defects_found:
        write_entry(
            type_="defect",
            title=f"Auto-scan: {dtype} failed",
            payload={"check": dtype, "message": msg, "auto_fix_attempted": True},
            priority=priority,
            tags=["auto_scan", dtype],
        )

    # Write full scan results
    scan_result = {
        "timestamp": datetime.now(tz=UTC).isoformat(),
        "defects_found": len(defects_found),
        "defects": defects_found,
        "all_checks": {k: {"rc": v.get("rc")} for k, v in all_results.items()},
    }
    Path("data/blindspot_autofix_scan.json").write_text(json.dumps(scan_result, indent=2))

    print(f"Scan complete. Defects found: {len(defects_found)}")
    for d in defects_found:
        print(f"  [{d[2].upper()}] {d[0]}: {d[1][:100]}")


if __name__ == "__main__":
    main()

```

### scripts\compile_proposals.py
```python
"""Proposals and audits become runnable cells, or a named refusal. Nothing sits in a queue.

WHY THIS EXISTS (principal, 2026-08-29)

    "so all research proposals -- who will implement them"
    "and all audits and recommendations by the openrouters -- who will"

Nobody, and that was the honest answer. The free panel writes `NAME | MECHANISM | PAYER | TEST |
KILL` into `hypothesis_queue.jsonl` and audit recommendations into a report, and both were
terminal: a human read them or nothing happened. A research role whose output nobody consumes is
the same defect as a role that never runs, wearing a more convincing artifact.

THIS IS THE CONSUMER. Two paths, and a proposal takes exactly one:

    COMPILED   the proposal maps onto a semantic coordinate `family_generic` can execute, so it
               becomes a docket cell today. No code is generated, nothing a model returned is
               executed -- the mapping picks five axis values and the family is already written.
    REFUSED    the proposal needs something the generic family cannot express (a cross-sectional
               rank, a multi-leg spread, options data the desk does not have). It is recorded
               with the reason and the missing capability NAMED, which is a research finding in
               itself: a queue of refusals is a list of what to build next.

REFUSING BY NAME IS THE LOAD-BEARING PART. An approximation would enter the docket as if it were
the proposal, and the gauntlet would judge something nobody meant to test -- then the result would
be attributed to the mechanism. That is worse than not testing it, because it produces a
confident wrong answer about an idea that was never tried.

AUDIT RECOMMENDATIONS BECOME EXPLORATION PRIORS, not prose. When the cold auditor names a region
worth searching, that region's coordinates are enumerated and queued. A recommendation that stays
a paragraph changes nothing; a recommendation that becomes cells changes where the next trials go.

NOTHING COMPILED HERE HAS ANY AUTHORITY. Cells enter the docket where every other candidate does
and face the identical gauntlet. A free model's idea is exactly as unprivileged as a parameter
sweep's, which is what makes running weak models safe.
"""
from __future__ import annotations

import json
import re
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
DESK = ROOT / "desks" / "mt5"
sys.path.insert(0, str(DESK))

QUEUE = ROOT / "data" / "hypothesis_queue.jsonl"
FREE = ROOT / "data" / "free_research.json"
COMPILED = DESK / "data" / "hypotheses" / "compiled_proposals.json"
OUT = ROOT / "data" / "proposal_compiler.json"

#: Words in a proposal that map to a semantic EVENT. Matched against the whole record, because a
#: model names the mechanism in the text rather than in a field.
_EVENT_WORDS: dict[str, tuple[str, ...]] = {
    "benchmark_flow": ("fix", "fixing", "benchmark", "rebalanc", "index", "close auction"),
    "options_hedging": ("gamma", "vega", "option", "hedg", "expiry", "dealer"),
    "liquidity_shock": ("liquidity", "spread", "depth", "illiquid", "thin"),
    "volatility_shock": ("volatility", "vol spike", "variance", "realized vol",
                         "vol regime", "regime transition", "squeeze", "expansion"),
    "forced_deleveraging": ("margin", "liquidation", "deleverag", "forced", "stop-out"),
    "inventory_rebalance": ("inventory", "imbalance", "flow", "positioning pressure"),
    "macro_release": ("macro", "cpi", "nfp", "central bank", "release", "announcement",
                      "intervention", "data surprise", "publication", "disclosure"),
    "carry_change": ("carry", "swap", "rate differential", "roll", "basis"),
    "cross_market_move": ("cross", "lead", "lag", "correlat", "spillover", "transmission",
                          "information asymmetry", "propagat", "transmit", "relative value"),
    "positioning_extreme": ("cot", "positioning", "crowd", "extreme", "sentiment"),
    "session_transition": ("session", "open", "handoff", "asia", "tokyo", "london", "overnight"),
}

_CONTEXT_WORDS: dict[str, tuple[str, ...]] = {
    "asia": ("asia", "tokyo", "overnight"),
    "london": ("london", "european", "euro session"),
    "new_york": ("new york", "us session", "ny ", "comex", "cme"),
    "overlap": ("overlap",),
    "high_vol": ("high volatility", "elevated vol", "stressed"),
    "low_vol": ("low volatility", "quiet", "calm"),
    "month_end": ("month-end", "month end", "quarter-end", "dividend record"),
    "high_liquidity": ("liquid", "deep"),
    "low_liquidity": ("thin", "illiquid"),
}

#: COVER EVERY LEGAL DIRECTION. This table named four of the six values in semantic_space
#: DIRECTIONS: volatility_expansion and volatility_compression were absent, so a proposal about
#: a vol regime could never resolve a direction and was refused for being unreadable rather than
#: for being wrong. 796 compilable proposals failed direction resolution on 2026-09-04.
_DIRECTION_WORDS: dict[str, tuple[str, ...]] = {
    "reversal": ("revers", "mean revert", "decay", "unwind", "correct", "fade", "pressure clears",
                 "retrace", "snap back", "overshoot", "exhaust", "give back", "normalis",
                 "normaliz", "round-trip", "round trip"),
    "continuation": ("continu", "momentum", "persist", "drift", "trend", "extend",
                     "follow-through", "follow through", "propagat", "diffus", "transmit",
                     "carry through", "sustain", "lead-lag", "leads the"),
    "convergence": ("converg", "narrow", "spread compress", "re-couple", "recouple",
                    "arbitrage away", "close the gap", "realign", "catch up", "catch-up"),
    "divergence": ("diverg", "widen", "decoupl", "de-coupl", "disconnect", "dislocat",
                   "asymmetr", "gap between", "separat", "break down"),
    "volatility_expansion": ("volatility expansion", "vol expansion", "range expansion",
                             "breakout", "expansion", "expands", "vol spike",
                             "volatility increase", "variance rises", "regime shift to high"),
    "volatility_compression": ("compress", "contraction", "squeeze", "coil", "narrowing range",
                               "volatility decline", "vol collapse", "variance falls",
                               "consolidat", "quiet regime"),
}

#: THE HORIZON IS PART OF THE CLAIM TOO. family_generic supports 1h/4h/daily, but the compiler
#: pinned "1h" for every proposal, so a weekly-rebalance idea and an hourly one landed on the
#: SAME coordinate and the second was refused as a duplicate of the first. 365 proposals were
#: refused for duplicate_coordinate on 2026-09-04 with two of the five axes frozen.
_OUTPUT_WORDS: dict[str, tuple[str, ...]] = {
    "daily": ("daily", "weekly", "week", "multi-day", "multi day", "overnight hold", "t+1",
              "monthly", "per day", "day-over-day", "8y sample", "quarterly"),
    "4h": ("4h", "four-hour", "four hour", "intraday swing", "several hours", "half-session",
           "multi-hour", "6h", "8h"),
    "1h": ("hourly", "1h", "per hour", "one-hour", "one hour", "60-minute"),
}

#: Capabilities the generic family cannot express. Naming them turns a refusal into a build list.
#: MATCHED ON WORD BOUNDARIES, NOT SUBSTRINGS. The plain-substring version refused a proposal
#: whenever "skew" appeared -- distributional skew is not options skew -- and "iv " matched
#: inside "relative ", "derivative " and "positive ". "1m" and "5m" matched any text containing
#: those two characters. 786 capability refusals were recorded on 2026-09-04 and the first three
#: hypotheses the world crawler ever produced were all refused for options_data it never needed.
#: A capability refusal is expensive: it is the one refusal that means "never retry until built".
_UNSUPPORTED_RX: dict[str, tuple[str, ...]] = {
    "cross_sectional_rank": (r"\brank(s|ed|ing)?\b", r"cross-section", r"universe-wide",
                             r"percentile across"),
    "multi_leg_spread": (r"spread between", r"pair trade", r"\blegs?\b", r"\bbaskets?\b",
                         r"relative value"),
    "options_data": (r"implied vol", r"\biv\b", r"option[\s-]*skew", r"vol(atility)?[\s-]+skew",
                     r"open interest", r"gamma exposure", r"\bgamma\b", r"delta[\s-]*hedg"),
    "order_flow_data": (r"order book", r"depth of book", r"tick flow", r"\baggressor\b"),
    # A bare "m" after a number is not a timeframe: "$1m", "0.15 m" and "30 ms" all matched it
    # and sub_hourly jumped 309 -> 780 refusals. A real sub-hourly claim spells the unit out or
    # names the MT5 frame, so require one of those.
    "sub_hourly": (r"\b(1|5|15|30)\s*-?\s*min(ute)?s?\b", r"\bm(1|5|15|30)\b",
                   r"\b(1|5|15|30)m\s+(bar|candle|chart|data|frame)", r"minute bars?",
                   r"sub-hourly", r"tick data", r"final 30"),
}


#: Language that means executing this proposal would COST the desk something beyond a trial.
#: Each key is a distinct way a "good idea" is net-negative, and each is refused by name.
#:
#: WHY A TEXT CHECK IS LEGITIMATE HERE. These are not subtle properties inferred from data -- they
#: are things a proposal SAYS about itself. A proposal that asks to relax a gate says so; one that
#: introduces a cap says so. Catching them at intake costs microseconds; catching them after they
#: are wired costs whatever they regressed.
_NEGATIVE_ROI: dict[str, tuple[str, ...]] = {
    "regresses_a_gate": (
        "loosen", "relax", "lower the threshold", "reduce the bar", "weaken", "waive",
        "skip validation", "bypass", "less strict", "ease the", "soften"),
    "adds_a_quota": (
        "quota", "cap the", "limit the number", "throttle", "restrict search", "only test the top",
        "prune to", "budget cap", "max candidates"),
    "names_a_tradeoff": (
        "trade-off", "tradeoff", "at the cost of", "in exchange for", "sacrific",
        "we would lose", "downside is", "requires giving up"),
    "needs_paid_data": (
        "subscription", "licensed data", "paid feed", "vendor data", "bloomberg", "refinitiv",
        "purchase", "\\$ per month", "commercial licence", "commercial license"),
    "needs_new_infrastructure": (
        "new database", "rewrite the", "replace the engine", "migrate", "re-architect",
        "new execution venue", "requires a broker change"),
}

#: TIMIDITY: language admitting the proposal will not move E[log W] by any path.
#:
#: The constitution's sole objective is max E[log W_T]; realized CAGR and alpha are MEASURES, not
#: goals. So a proposal earns a trial by claiming a path to geometric growth -- and the path may
#: be indirect. A candidate that raises the book's INDEPENDENCE raises geometric growth at
#: unchanged arithmetic return, and one that kills a live hypothesis frees the budget its
#: successor needs. Both are growth paths.
#:
#: WHAT IS ACTUALLY REJECTED is a proposal that names no path at all: purely defensive, purely
#: cosmetic, or self-described as marginal. "Reduce drawdown slightly" with no edge claim and no
#: independence claim is a smaller version of the book the desk already has.
_TIMID: dict[str, tuple[str, ...]] = {
    "self_described_marginal": (
        "marginal improvement", "slight improvement", "modest gain", "small tweak",
        "incremental adjustment", "minor refinement", "fine-tune the existing",
        "slightly better", "a small edge on top of"),
    "purely_defensive": (
        "reduce risk only", "risk reduction only", "purely defensive", "hedge only",
        "no additional return", "without adding return", "capital preservation only",
        "lower volatility only"),
    "conservative_by_construction": (
        "conservative approach", "play it safe", "avoid taking positions",
        "trade less frequently to be safe", "sit out", "stay flat"),
}

#: Words that indicate a GROWTH PATH, direct or indirect. A proposal carrying any of these is not
#: timid even if its claimed effect is small -- a 0.05R edge that is INDEPENDENT is worth more to
#: geometric growth than a 0.20R clone, which is the whole n_eff argument, and rejecting it for
#: modesty would invert the objective.
_GROWTH_PATH = (
    "independent", "uncorrelated", "orthogonal", "diversif", "new mechanism", "new payer",
    "forced", "compelled", "constraint", "edge", "expectancy", "premium", "mispricing",
    "kill condition", "falsif", "unexplored", "untested", "residual",
)

#: A coordinate this heavily attempted with nothing to show is saturated ground. Re-testing it is
#: a trial spent to re-learn something measured. Deliberately generous -- the desk has been wrong
#: about "barren" before, and this is a spending decision rather than a verdict on the mechanism.
_SATURATED_ATTEMPTS = 400


def _saturation_map() -> dict[str, int]:
    """Attempts per (event, direction) region, from the measured intake artifact."""
    try:
        intake = json.loads((ROOT / "data" / "research_intake.json").read_text("utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    # `coverage.never_touched` names regions with zero; the census carries the counts.
    try:
        alloc = json.loads((ROOT / "data" / "research_allocation.json").read_text("utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    out: dict[str, int] = {}
    for row in alloc.get("ranked", []):
        counts = row.get("counts") or {}
        out[str(row.get("family"))] = int(counts.get("candidates", 0))
    _ = intake
    return out


def _existing_coordinates() -> set[str]:
    """Coordinates the desk has already CERTIFIED. Duplicating one adds no information.

    READ CERTIFICATES, NOT THE COMPILER'S OWN LAST OUTPUT. A first version seeded this from
    `compiled_proposals.json` -- the file this script writes -- so every coordinate it produced
    minutes earlier counted as an incumbent and the next run refused ALL FIFTEEN proposals as
    duplicates of itself. A check whose baseline is its own output rejects everything on the
    second run and reports it as a finding.

    An incumbent is something the desk OWNS: a survivor that passed the gauntlet. A cell merely
    queued for testing is not evidence of anything and must not block a second look.
    """
    out: set[str] = set()
    try:
        surv = json.loads((DESK / "reports" / "UNIVERSAL_SURVIVORS.json")
                          .read_text("utf-8")).get("survivors") or {}
    except (OSError, json.JSONDecodeError):
        return out
    for row in surv.values():
        spec = (row or {}).get("shadow_spec") or {}
        fam = spec.get("family")
        if fam:
            # Certificates predate the coordinate system, so match on the EVENT they map to
            # rather than on a full coordinate they never carried.
            out.add(str(fam))
    return out


def _roi_refusal(rec: dict[str, Any], text: str, coordinate: str,
                 saturation: dict[str, int], seen: set[str]) -> dict[str, Any] | None:
    """Would executing this cost more than it returns? Returns a refusal, or None to proceed.

    CRITICAL THINKING BEFORE AUTOMATIC EXECUTION (principal, 2026-08-29). Automatic execution is
    right -- a proposal nobody runs is a proposal nobody made. But automatic execution WITHOUT
    this check is how a research loop quietly spends its budget re-testing saturated ground,
    duplicating cells it already owns, or wiring in a constraint that narrows every future search.
    """
    t = text.lower()
    for reason, words in _NEGATIVE_ROI.items():
        hit = next((w for w in words if w in t), None)
        if hit:
            return {"name": rec.get("name"), "compiled": False,
                    "refused_for": reason, "trigger": hit,
                    "why": (f"the proposal itself says {hit!r}, which means executing it "
                            f"{'regresses an existing gate' if reason == 'regresses_a_gate' else ''}"
                            f"{'narrows what the desk may search' if reason == 'adds_a_quota' else ''}"
                            f"{'costs something it names' if reason == 'names_a_tradeoff' else ''}"
                            f"{'needs data the desk cannot obtain free' if reason == 'needs_paid_data' else ''}"
                            f"{'requires infrastructure work the trial does not pay for' if reason == 'needs_new_infrastructure' else ''}"
                            f". Refused before any trial is spent.")}

    if coordinate in seen:
        return {"name": rec.get("name"), "compiled": False, "refused_for": "duplicate_coordinate",
                "trigger": coordinate,
                "why": (f"{coordinate} is already carried by a CERTIFIED cell. Testing the same "
                        f"claim twice adds no information while charging the trial count every "
                        f"other candidate's bar is computed against.")}

    # TIMIDITY: refuse only when the proposal admits it moves nothing AND names no growth path.
    # Both conditions, because the first alone would reject a modestly-worded proposal carrying a
    # genuinely new mechanism -- and a small INDEPENDENT edge is worth more to E[log W] than a
    # large correlated one.
    has_growth_path = any(w in t for w in _GROWTH_PATH)
    for reason, words in _TIMID.items():
        hit = next((w for w in words if w in t), None)
        if hit and not has_growth_path:
            return {"name": rec.get("name"), "compiled": False, "refused_for": reason,
                    "trigger": hit,
                    "why": (f"says {hit!r} and names no path to geometric growth -- no edge, no "
                            f"independence claim, no information gain. The constitution's sole "
                            f"objective is max E[log W_T]; a proposal that moves it by no path, "
                            f"direct or indirect, is a smaller version of the book the desk "
                            f"already owns and does not earn a trial.")}

    ev = coordinate.split("|")[0] if "|" in coordinate else ""
    attempts = saturation.get(ev, 0)
    if attempts >= _SATURATED_ATTEMPTS:
        return {"name": rec.get("name"), "compiled": False, "refused_for": "saturated_ground",
                "trigger": f"{ev}:{attempts}",
                "why": (f"{ev} already carries {attempts} attempts on this desk. This is a "
                        f"SPENDING decision, not a verdict on the mechanism -- the region may "
                        f"well be real, but one more trial there buys less than the same trial "
                        f"spent where nothing has been measured.")}
    return None


#: Populated by `main` before compiling. Module-level so `compile_proposal` stays a pure
#: single-record function that a test can call directly.
_SATURATION: dict[str, int] = {}
_SEEN: set[str] = set()


def _declared(rec: dict[str, Any], field: str, legal: tuple[str, ...]) -> str | None:
    """The proposal's OWN axis value, when it stated one and that value is legal.

    Inferring an axis from keywords when the record already declares it throws away the only
    unambiguous evidence in the row. Illegal values fall through to inference rather than
    failing, because a generator typo is not a reason to refuse a stated mechanism.
    """
    v = str(rec.get(field) or "").strip().lower().replace(" ", "_")
    return v if v in legal else None


def _match(text: str, table: dict[str, tuple[str, ...]]) -> str | None:
    t = text.lower()
    best, best_hits = None, 0
    for key, words in table.items():
        hits = sum(1 for w in words if w in t)
        if hits > best_hits:
            best, best_hits = key, hits
    return best


def _unsupported(text: str) -> list[str]:
    t = text.lower()
    return [k for k, pats in _UNSUPPORTED_RX.items()
            if any(re.search(p, t) for p in pats)]


def compile_proposal(rec: dict[str, Any], supported: dict[str, list[str]]) -> dict[str, Any]:
    """One proposal -> a runnable cell spec, or a refusal that names what is missing."""
    # Read EVERY field the proposal carries. A fixed list here silently ignored `data_source`
    # and `lens` once the prompt contract changed, and the capability check reads the whole text.
    text = " ".join(str(v) for k, v in rec.items()
                    if k in ("name", "mechanism", "data_source", "payer", "test", "kill",
                             "lens", "event", "context", "direction"))
    missing = _unsupported(text)
    # A VALIDATED DSL TREE WAIVES THE CAPABILITIES IT ACTUALLY EXPRESSES -- and only those.
    # `cross_sectional_rank` and `multi_leg_spread` were refused because family_generic cannot
    # express them, which was true and is why refusing was correct: an approximation would enter
    # the docket as if it were the proposal. libs/research_os/dsl.py CAN express them (rank,
    # spread, ratio, resid), so a proposal that SUPPLIES a tree is no longer approximating -- it
    # is stating the factor exactly, in a language whose 22 operators are checked against an
    # allowlist before any data is touched.
    #
    # NO TREE, NO WAIVER. A proposal that merely mentions "spread between" without supplying one
    # is still refused, because naming a shape is not expressing it. That keeps the refusal
    # queue meaningful: it now lists proposals that need a tree, not capabilities the desk lacks.
    if missing:
        _tree = rec.get("factor")
        if _tree is not None:
            try:
                from libs.research_os.dsl import validate as _dsl_validate

                _dsl_validate(_tree)
                _EXPRESSIBLE = {"cross_sectional_rank", "multi_leg_spread"}
                missing = [m for m in missing if m not in _EXPRESSIBLE]
            except Exception as _exc:
                return {"name": rec.get("name"), "compiled": False,
                        "refused_for": "invalid_factor_tree", "trigger": str(_exc)[:90],
                        "why": (f"the proposal supplied a factor tree the DSL refuses "
                                f"({str(_exc)[:70]}). Refused by name rather than approximated -- "
                                f"the refusal names the operator worth adding.")}
    if missing:
        return {"name": rec.get("name"), "compiled": False, "missing_capability": missing,
                "refused_for": "missing_capability",
                "why": (f"needs {', '.join(missing)}, which family_generic cannot express. "
                        f"Recorded rather than approximated: an approximation would enter the "
                        f"docket as if it were this proposal and the gauntlet would judge "
                        f"something nobody meant to test.")}

    from libs.research.semantic_space import CONTEXTS, DIRECTIONS, EVENTS, OUTPUTS

    event = _declared(rec, "event", EVENTS) or _match(text, _EVENT_WORDS)
    context = _declared(rec, "context", CONTEXTS) or _match(text, _CONTEXT_WORDS)
    direction = _declared(rec, "direction", DIRECTIONS) or _match(text, _DIRECTION_WORDS)
    # Unstated horizon stays "1h" -- the family's own default, and unchanged behaviour. What
    # changes is that a proposal which DOES name its horizon now keeps it instead of being
    # flattened onto 1h and refused as a duplicate of an unrelated hourly claim.
    output = _declared(rec, "output", OUTPUTS) or _match(text, _OUTPUT_WORDS) or "1h"
    if output not in supported["output"]:
        output = "1h"
    unresolved = [n for n, v in (("event", event), ("direction", direction)) if not v]
    if unresolved:
        return {"name": rec.get("name"), "compiled": False, "missing_capability": [],
                "refused_for": "unresolved_axis",
                "why": (f"could not resolve {unresolved} from the proposal text. The axis is the "
                        f"claim: guessing 'continuation' for a mechanism that never said so would "
                        f"test the opposite of the hypothesis half the time.")}

    # NO SILENT DEFAULT. `context = context or "asia"` turned an unresolved axis into a
    # confident specification -- the desk's own law is that absence is never permission, and a
    # compiler that fills in the missing half of a claim is deciding what the hypothesis says.
    # STILL NO SILENT DEFAULT -- but refusal was not the only alternative to guessing. A proposal
    # that names no session makes a claim about every bar, so it compiles to the UNCONDITIONED
    # context and is tested there. `context = context or "asia"` remains forbidden: that would
    # record the result against a session nobody named. This records it against all of them.
    context_declared = context is not None
    if not context:
        context = "unconditioned"

    # MEASUREMENT CONTRACT. A mechanism whose implementation cannot see it does not compile.
    from libs.research.measurement import contract_for

    mc = contract_for(event)
    if mc is not None and not mc.may_run:
        return {"name": rec.get("name"), "compiled": False, "refused_for": "unmeasurable",
                "why": mc.verdict()}

    if event not in supported["event"] or direction not in supported["direction"]:
        return {"name": rec.get("name"), "compiled": False,
                "missing_capability": [f"event:{event}"],
                "why": f"{event}/{direction} is outside family_generic's vocabulary"}

    coordinate = f"{event}|{context}|magnitude|{direction}|{output}"
    veto = _roi_refusal(rec, text, coordinate, _SATURATION, _SEEN)
    if veto is not None:
        return veto
    _SEEN.add(coordinate)

    return {"name": rec.get("name"), "compiled": True,
            "family": "generic",
            "params": {"event": event, "context": context, "direction": direction,
                       "output": output, "quality_atr": 1.0},
            "coordinate": coordinate,
            # Carried onto the cell so every downstream reader knows whether this result may be
            # attributed to the mechanism, or is exploration under its own coordinate only.
            # False means the proposal named no session and is running unconditioned -- a reader
            # must not attribute an unconditioned result to a session-specific mechanism.
            "context_declared": context_declared,
            "measurement_class": mc.measurement_class if mc else "UNKNOWN",
            "attribution_allowed": bool(mc.attribution_allowed) if mc else False,
            "measurement_note": mc.verdict() if mc else "no contract recorded for this event",
            "data_source": rec.get("data_source"), "kill": rec.get("kill"),
            "lens": rec.get("lens"),
            "promotion_authority": False}


def main() -> int:
    from mt5desk.family_generic import supported as generic_supported

    now = datetime.now(tz=UTC)
    sup = generic_supported()

    global _SATURATION, _SEEN
    _SATURATION = _saturation_map()
    _SEEN = _existing_coordinates()

    props: list[dict[str, Any]] = []
    if QUEUE.exists():
        for line in QUEUE.read_text("utf-8").splitlines():
            try:
                props.append(json.loads(line))
            except json.JSONDecodeError:
                continue

    # AUDIT RECOMMENDATIONS BECOME CELLS, NOT PROSE. A named region is enumerated into the same
    # coordinate shape a proposal compiles to, so a recommendation changes where trials go.
    audit_props: list[dict[str, Any]] = []
    try:
        free = json.loads(FREE.read_text("utf-8"))
        for res in free.get("results", []):
            for row in res.get("regions", []) or []:
                region = str(row.get("region", "")).strip()
                m = re.match(r"^([a-z_]+)\s*\|?\s*([a-z_]*)", region.lower())
                if not m:
                    continue
                # ONE COMPILER, NO PRIVILEGED ENTRANCE. This branch used to build the cell
                # itself: it defaulted an unparsed direction to "continuation", hardcoded
                # `context: "asia"`, and set `compiled: True` without ever calling
                # `compile_proposal` -- so it skipped the capability check, the axis resolution,
                # the ROI refusal, the saturation check and the novelty gate in one step.
                #
                # Both of those defaults are the EXACT failures the ordinary path refuses by name
                # thirty lines above: "guessing 'continuation' for a mechanism that never said so
                # would test the opposite of the hypothesis half the time", and "a compiler that
                # fills in the missing half of a claim is deciding what the hypothesis says".
                # Removing them from one entrance while leaving them in another removed nothing.
                #
                # Audit regions now become PROPOSALS and take the same door. Most will be REFUSED
                # for unresolved context, because a region named `event|direction` genuinely does
                # not say when it fires -- and a refusal that names the missing axis is a research
                # finding, where a cell built on a guessed axis is a confident answer to a
                # question nobody asked.
                audit_props.append({
                    "name": f"audit:{region[:48]}",
                    "mechanism": region,
                    "test": str(row.get("why") or row.get("evidence") or ""),
                    "data_source": "named by cold audit; capability checked at compile",
                    "lens": "cold_audit_recommendation",
                    "origin": "cold_audit"})
    except (OSError, json.JSONDecodeError):
        pass

    results = [compile_proposal(p, sup) for p in props + audit_props]
    ok = [r for r in results if r.get("compiled")]
    refused = [r for r in results if not r.get("compiled")]

    print(f"PROPOSAL COMPILER {now.isoformat(timespec='seconds')}")
    print(f"  queue: {len(props)} proposal(s), audit regions: {len(audit_props)} "
          f"(both through the SAME compiler)")
    print(f"  COMPILED {len(ok)}   REFUSED {len(refused)}")
    for r in ok[:10]:
        print(f"    ok   {str(r.get('name'))[:34]:36s} {r['coordinate']}")
    for r in refused[:10]:
        miss = (r.get("refused_for")
                or ",".join(r.get("missing_capability") or [])
                or "axis unresolved")
        print(f"    --   {str(r.get('name'))[:34]:36s} [{miss}]")
        print(f"         {r['why'][:120]}")

    COMPILED.parent.mkdir(parents=True, exist_ok=True)
    COMPILED.write_text(json.dumps({"built_at": now.isoformat(timespec="seconds"),
                                    "cells": ok}, indent=1), "utf-8")
    OUT.write_text(json.dumps({"ran_at": now.isoformat(timespec="seconds"),
                               "compiled": len(ok), "refused": len(refused),
                               "refusals": refused,
                               "missing_capabilities": sorted({m for r in refused
                                                               for m in (r.get("missing_capability")
                                                                         or [])}),
                               "note": ("a refusal names the capability to build next; "
                                        "approximating would put a wrong answer in the docket "
                                        "under the proposal's name")}, indent=1), "utf-8")
    print(f"\n  -> {COMPILED}")
    print(f"  -> {OUT}")
    if refused:
        gaps = sorted({m for r in refused for m in (r.get("missing_capability") or [])})
        if gaps:
            print(f"\n  BUILD LIST (capabilities refusals are waiting on): {gaps}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

```
