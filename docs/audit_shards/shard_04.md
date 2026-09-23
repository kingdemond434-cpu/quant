# AUDIT SHARD 4/24 -- seat deepseek/deepseek-v4-pro-0813

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

### libs\research\effective_breadth.py
```python
"""HOW MANY INDEPENDENT BETS THE BOOK IS, measured from EXPOSURES rather than waited for.

    "You need approximately twice as many genuinely independent sources of P&L. Five
     Gold/JPY/session-breakout variants are not five independent edges if they all make money
     from approximately the same market phenomenon."               -- the principal, 2026-09-05

THE MEASUREMENT THAT ALREADY EXISTS AND THE HOLE IN IT. `mt5desk/independence.py` computes k_eff
from REALISED daily sleeve returns and floors it with `libs/risk/fx_factors.effective_bets`, which
counts currency legs. Both are right and neither can answer today: the return estimator needs
MIN_PAIR_OVERLAP = 20 overlapping trading days per pair, and on this desk's shadow history the
best pair has TEN. The leg counter needs no history at all but answers a coarser question -- how
many distinct legs -- and treats EUR, CHF, NOK, SEK and DKK as five legs when they are close to
one bet. So the desk's headline breadth number is either UNMEASURED or optimistic, and the
`n_effective 1.019 across 17 sleeves` finding that motivated all of this came from the coarse one.

WHAT THIS ADDS. The book's DIRECTIONAL EXPOSURE has years of price history behind it even when
the sleeves have weeks. A sleeve that is long CADJPY carries CADJPY's covariance whether or not
it has traded twenty days, so:

    N_eff = (sum_s |w_s|)^2 / (x' C x)

where w_s is each sleeve's standalone risk, x is those risks aggregated onto the instruments they
are expressed in and signed by direction, and C is the correlation of vol-normalised instrument
returns. Independent and equal-sized sleeves give N_eff = N; N copies of one trade give 1. This is
the diversification ratio squared, and it is measured on the desk's own H1 bars.

THREE WAYS IT IS DELIBERATELY CONSERVATIVE, because every one of them could have gone the other
way and flattered the book:

1. TWO SLEEVES ON ONE INSTRUMENT COUNT AS ONE BET. A London breakout and an Asia reversion on
   GBPJPY differ in timing and mechanism, and that difference is real breadth -- which this does
   not claim, because only realised returns can measure it. So the number is a LOWER BOUND on the
   book's P&L breadth and an EXACT reading of its exposure breadth. Timing can only add.
2. AN UNDIRECTIONAL SLEEVE IS DROPPED, NOT DILUTED. A sleeve that went long half the time nets a
   small directional loading while still carrying a full unit of variance; crediting the small
   loading would understate book risk and overstate breadth. It is excluded and counted in
   `dropped` instead.
3. AN INSTRUMENT WITH NO BARS ADDS NO BREADTH. ZAR, MXN, NOK, SEK and DKK crosses are in the book
   and not in the local universe. They are excluded and their share of nominal risk is reported,
   rather than being assumed independent of what is measured.

THE COLLIDER THIS MODULE REFUSES TO WALK INTO, and the reason `conditional_breadth` takes a LAGGED
conditioner and nothing else. "Correlation on the book's worst days" is the natural thing to ask
and the answer is worthless: selecting days by the book's own return selects on a SUM of the
series being correlated, which mechanically decorrelates them. Measured here on this desk's own
panel, breadth conditioned on the book's worst 5% of days reads 8.9 against a full-sample 1.3 --
a book that looks SEVEN TIMES more diversified precisely when it is losing, which is the exact
opposite of what happens and would raise leverage into a crisis. Conditioning on same-day
magnitude has the same defect from the other side (-0.00 mean pairwise correlation on the top-vol
5%). Conditioning on a PRIOR-window statistic has neither: it is known before the returns being
correlated, so it selects a regime rather than a realisation. On the same panel the JPY block
reads 0.93 in a high prior-vol regime against 0.49 in a calm one -- correlations rise in stress,
which is what everyone assumes and nothing here had measured.

NOTHING HERE SIZES ANYTHING. Sizing stays in the gateway. This measures, names its refusals, and
returns None wherever it cannot measure -- None never widens a budget.
"""
from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

import numpy as np

from libs.research.cohort_independence import effective_bets

__all__ = [
    "MEASURED",
    "MIN_PAIR_OVERLAP",
    "MIN_PANEL_OBS",
    "MIN_REGIME_OBS",
    "MIN_SCALE_OBS",
    "UNMEASURED",
    "Reading",
    "conditional_breadth",
    "exposure_breadth",
    "exposure_neff",
    "factor_breadth",
    "headline",
    "lagged_vol_regime",
    "realised_breadth",
]

MEASURED, UNMEASURED = "MEASURED", "UNMEASURED"

#: Overlapping days a PAIR of sleeves needs before its realised correlation is used. Identical to
#: `mt5desk.independence.MIN_PAIR_OVERLAP` and mirrored rather than imported so that libs does not
#: depend on the desk package; a noisy correlation near zero is indistinguishable from genuine
#: independence, which is the error that raises leverage.
MIN_PAIR_OVERLAP = 20

#: Observations a price panel needs before its correlation matrix is read as a measurement. Below
#: this the off-diagonals are dominated by estimation noise in BOTH directions and the resulting
#: N_eff is not a number anyone should size on.
MIN_PANEL_OBS = 250

#: Observations an expanding scale needs before it is used to normalise anything. Below this the
#: scale is noise and the regime label it produces is noise divided by noise.
MIN_SCALE_OBS = 20

#: Observations inside a conditioned regime before the conditional correlation is a measurement.
#: Lower than MIN_PANEL_OBS because a regime is a subsample by construction, and high enough that
#: a 12-symbol correlation matrix is not being read off a quarter of a year.
MIN_REGIME_OBS = 60


@dataclass(frozen=True)
class Reading:
    """One way of counting the book's independent bets, with its own refusal path."""

    name: str
    status: str                 # MEASURED | UNMEASURED
    n_eff: float | None
    n_nominal: int
    n_obs: int
    why: str
    detail: dict[str, Any] | None = None

    @property
    def measured(self) -> bool:
        return self.status == MEASURED and self.n_eff is not None

    def as_dict(self) -> dict[str, Any]:
        return {"name": self.name, "status": self.status,
                "n_eff": None if self.n_eff is None else round(float(self.n_eff), 3),
                "n_nominal": self.n_nominal, "n_obs": self.n_obs, "why": self.why,
                **({"detail": self.detail} if self.detail else {})}


def _unmeasured(name: str, why: str, *, n_nominal: int = 0, n_obs: int = 0) -> Reading:
    return Reading(name, UNMEASURED, None, int(n_nominal), int(n_obs), why)


def exposure_neff(nominal_risk: float, exposure: np.ndarray, corr: np.ndarray) -> float:
    """(sum of standalone risks)^2 / (portfolio variance in the same units) -- the bet count.

    ``nominal_risk`` is the sum of the sleeves' standalone risks, which on this desk is simply
    the sleeve count when every sleeve risks the same fraction at stop. ``exposure`` is those
    risks aggregated onto instruments and SIGNED by direction, and ``corr`` is the correlation of
    those instruments' vol-normalised returns.

    Equal to N for N independent equal-risk sleeves and to 1 for N copies of one trade. The
    variance term is refused rather than floored when it is non-positive: a non-PSD correlation
    matrix would produce an enormous bet count out of a measurement error, and an enormous number
    that looks like an answer is worse than an exception.
    """
    x = np.asarray(exposure, dtype="float64").reshape(-1)
    c = np.asarray(corr, dtype="float64")
    if c.shape != (x.size, x.size):
        raise ValueError(f"exposure of {x.size} does not match a {c.shape} correlation matrix")
    var = float(x @ c @ x)
    if not math.isfinite(var) or var <= 0.0:
        raise ValueError(
            "book variance from the supplied exposures and correlations is not positive -- the "
            "correlation matrix is not positive semi-definite; fix the measurement, never size "
            "on it")
    nom = float(nominal_risk)
    return (nom * nom) / var


def _panel_corr(panel: np.ndarray) -> np.ndarray:
    """Pearson correlation of vol-normalised columns. Degenerate columns are the caller's job."""
    m = np.asarray(panel, dtype="float64")
    sd = m.std(axis=0)
    z = m / np.where(sd > 0, sd, 1.0)
    return np.asarray(np.corrcoef(z, rowvar=False), dtype="float64")


def exposure_breadth(nominal_risk: float, exposure: Mapping[str, float],
                     panel: Mapping[str, Sequence[float]], *,
                     name: str = "exposure_full_sample",
                     min_obs: int = MIN_PANEL_OBS) -> Reading:
    """Independent bets implied by what the book is directionally long and short of.

    ``exposure`` maps instrument -> signed risk. ``panel`` maps the same instruments to aligned
    return series. Instruments present in ``exposure`` and absent from ``panel`` are NOT silently
    dropped: they raise, because a caller that quietly loses half its book from the denominator
    gets a flattering number and no warning. Filter before calling, and report what was filtered.
    """
    names = sorted(exposure)
    if len(names) < 2:
        return _unmeasured(name, "a correlation needs at least two instruments",
                           n_obs=0)
    missing = [s for s in names if s not in panel]
    if missing:
        raise KeyError(f"no return series for {missing} -- drop them from the exposure and report "
                       "the risk share they carry, never measure breadth on a silent subset")
    cols = [np.asarray(panel[s], dtype="float64") for s in names]
    n_obs = min(int(c.size) for c in cols)
    if n_obs < int(min_obs):
        return _unmeasured(name, f"{n_obs} aligned observations, below the {min_obs} floor: a "
                                 "correlation matrix this thin is estimation noise",
                           n_obs=n_obs)
    m = np.stack([c[-n_obs:] for c in cols], axis=1)
    if not np.all(np.isfinite(m)) or not np.all(m.std(axis=0) > 0):
        return _unmeasured(name, "a return column is constant or non-finite over the window",
                           n_obs=n_obs)
    x = np.array([float(exposure[s]) for s in names], dtype="float64")
    corr = _panel_corr(m)
    try:
        k = exposure_neff(nominal_risk, x, corr)
    except ValueError as exc:
        return _unmeasured(name, str(exc), n_obs=n_obs)
    iu = np.triu_indices(len(names), 1)
    return Reading(name, MEASURED, k, round(nominal_risk), n_obs,
                   f"(sum|w|)^2 / x'Cx on {len(names)} instruments over {n_obs} observations",
                   {"instruments": names, "mean_pairwise_corr": round(float(corr[iu].mean()), 4),
                    "max_pairwise_corr": round(float(corr[iu].max()), 4)})


def factor_breadth(nominal_risk: float, exposure: Mapping[str, float],
                   panel: Mapping[str, Sequence[float]], *, k_factors: int = 3,
                   min_obs: int = MIN_PANEL_OBS) -> Reading:
    """Independent bets against the SYSTEMATIC part of the correlation only.

    The full-sample reading counts idiosyncratic instrument moves as diversification. They are,
    on an average day; they are not what decides how much leverage the book can carry, because
    idiosyncratic moves do not arrive together and factor moves do. Truncating the correlation to
    its leading ``k_factors`` principal components answers the narrower question: how many bets is
    the book making ON THE THINGS THAT MOVE EVERYTHING AT ONCE.

    Reported BESIDE the full-sample number, never instead of it. Where the two disagree the
    disagreement is the finding: a factor breadth far below the full-sample one says the book's
    apparent diversification lives in idiosyncratic risk and will not be there in a shock.
    """
    base = exposure_breadth(nominal_risk, exposure, panel, name="exposure_systematic",
                            min_obs=min_obs)
    if not base.measured:
        return base
    names = sorted(exposure)
    cols = [np.asarray(panel[s], dtype="float64") for s in names]
    n_obs = min(int(c.size) for c in cols)
    m = np.stack([c[-n_obs:] for c in cols], axis=1)
    kf = int(max(1, min(int(k_factors), len(names) - 1)))
    corr = _panel_corr(m)
    vals, vecs = np.linalg.eigh(corr)
    order = np.argsort(vals)[::-1][:kf]
    load = vecs[:, order] * np.sqrt(np.clip(vals[order], 0.0, None))
    sys_cov = load @ load.T
    # The systematic correlation keeps a unit diagonal: the idiosyncratic remainder is what makes
    # each instrument's own variance up to 1, and dropping it would make the matrix non-PSD.
    idio = np.clip(1.0 - np.diag(sys_cov), 1e-9, None)
    rho_factor = sys_cov + np.diag(idio)
    explained = float(np.sum(vals[order]) / max(float(np.sum(vals)), 1e-12))
    x = np.array([float(exposure[s]) for s in names], dtype="float64")
    try:
        kk = exposure_neff(nominal_risk, x, rho_factor)
    except ValueError as exc:
        return _unmeasured("exposure_systematic", str(exc), n_obs=n_obs)
    return Reading("exposure_systematic", MEASURED, kk, round(nominal_risk), n_obs,
                   f"{kf}-factor systematic correlation explaining {explained:.1%} of panel "
                   "variance; idiosyncratic risk excluded from the diversification claim",
                   {"k_factors": kf, "variance_explained": round(explained, 4)})


def lagged_vol_regime(panel: Mapping[str, Sequence[float]], *, window: int = 20) -> np.ndarray:
    """A regime series that is KNOWN BEFORE the returns it will be used to condition.

    The mean absolute move across the panel, each column scaled by ITS OWN EXPANDING standard
    deviation through t-1, averaged over the previous ``window`` observations. Index t carries
    information from observations strictly before t and from nothing else, so selecting on it
    selects a REGIME and never a realisation. The leading `MIN_SCALE_OBS + window` entries are NaN
    and the caller must treat them as unavailable.

    THE EXPANDING SCALE IS NOT FASTIDIOUSNESS, AND THE FIRST VERSION OF THIS FUNCTION GOT IT
    WRONG. It normalised each column by its FULL-SAMPLE standard deviation before taking the
    rolling window, so a single observation at the end of the panel changed the scale and with it
    every label in the series, including the ones years earlier. The lag was in the window and not
    in the normaliser, which is exactly the kind of leak that survives review: the shift is
    visible in the code and the sd is not. A test that perturbs the last observation and demands
    every earlier label be unchanged catches it, and `test_alpha_breadth_factory.py` carries one.

    THE SHIFT ITSELF IS THE OTHER HALF. Without it every conditional correlation in this module is
    a collider: conditioning on same-period magnitude or on the book's own return decorrelates the
    series by construction and reports a book that diversifies itself precisely when it is losing.
    """
    names = sorted(panel)
    cols = [np.asarray(panel[s], dtype="float64") for s in names]
    n = min(int(c.size) for c in cols)
    m = np.stack([c[-n:] for c in cols], axis=1)
    w = int(window)
    out = np.full(n, np.nan, dtype="float64")
    if w < 1 or n <= MIN_SCALE_OBS + w:
        return out
    # Expanding population std over observations 0..t-1, per column. Strictly prior by index.
    idx = np.arange(1, n + 1, dtype="float64")[:, None]
    c1 = np.cumsum(m, axis=0)
    c2 = np.cumsum(m * m, axis=0)
    mean_prior = c1 / idx
    var_prior = np.clip(c2 / idx - mean_prior * mean_prior, 0.0, None)
    scale = np.full_like(m, np.nan)
    scale[1:] = np.sqrt(var_prior[:-1])              # scale[t] uses 0..t-1 only
    with np.errstate(invalid="ignore", divide="ignore"):
        z = np.abs(m) / np.where(scale > 0, scale, np.nan)
    # Counted mean rather than nanmean: the leading rows have no scale at all, and nanmean warns
    # on an empty slice instead of simply saying "no value here", which is what NaN already says.
    finite = np.isfinite(z)
    cnt = finite.sum(axis=1)
    tot = np.where(finite, z, 0.0).sum(axis=1)
    zbar = np.where(cnt > 0, tot / np.where(cnt > 0, cnt, 1), np.nan)
    zbar[:MIN_SCALE_OBS] = np.nan
    # out[t] = mean(zbar[t-w : t]) -- the window ENDS at t-1, so nothing at t enters its own label.
    for t in range(MIN_SCALE_OBS + w, n):
        seg = zbar[t - w:t]
        good = seg[np.isfinite(seg)]
        if good.size:
            out[t] = float(good.mean())
    return out


def conditional_breadth(nominal_risk: float, exposure: Mapping[str, float],
                        panel: Mapping[str, Sequence[float]], conditioner: Sequence[float], *,
                        quantile: float = 0.2, high: bool = True,
                        name: str = "exposure_stress",
                        min_obs: int = MIN_REGIME_OBS) -> Reading:
    """Independent bets inside a regime picked out by a LAGGED conditioner.

    ``conditioner`` must be known before the observation it labels -- `lagged_vol_regime` builds
    one. There is no way for this function to verify that from the array alone, so the contract is
    stated and the caller carries it; passing a contemporaneous statistic (the book's own return,
    same-day realised vol) turns this into the collider described in the module docstring and the
    answer will be confidently wrong in the direction that raises leverage.
    """
    names = sorted(exposure)
    if len(names) < 2:
        return _unmeasured(name, "a correlation needs at least two instruments")
    missing = [s for s in names if s not in panel]
    if missing:
        raise KeyError(f"no return series for {missing}")
    cols = [np.asarray(panel[s], dtype="float64") for s in names]
    n_obs = min(int(c.size) for c in cols)
    cond = np.asarray(conditioner, dtype="float64")
    if cond.size != n_obs:
        return _unmeasured(name, f"conditioner has {cond.size} entries against {n_obs} aligned "
                                 "observations; an unaligned regime label is not a regime",
                           n_obs=n_obs)
    ok = np.isfinite(cond)
    if int(ok.sum()) < int(min_obs):
        return _unmeasured(name, f"{int(ok.sum())} observations carry a finite regime label, "
                                 f"below the {min_obs} floor", n_obs=int(ok.sum()))
    q = float(np.quantile(cond[ok], 1.0 - quantile if high else quantile))
    sel = ok & ((cond >= q) if high else (cond <= q))
    n_sel = int(sel.sum())
    if n_sel < int(min_obs):
        return _unmeasured(name, f"{n_sel} observations inside the regime, below the {min_obs} "
                                 "floor: a conditional correlation this thin is noise",
                           n_obs=n_sel)
    m = np.stack([c[-n_obs:] for c in cols], axis=1)[sel]
    if not np.all(np.isfinite(m)) or not np.all(m.std(axis=0) > 0):
        return _unmeasured(name, "a return column is constant or non-finite inside the regime",
                           n_obs=n_sel)
    x = np.array([float(exposure[s]) for s in names], dtype="float64")
    corr = _panel_corr(m)
    try:
        k = exposure_neff(nominal_risk, x, corr)
    except ValueError as exc:
        return _unmeasured(name, str(exc), n_obs=n_sel)
    iu = np.triu_indices(len(names), 1)
    return Reading(name, MEASURED, k, round(nominal_risk), n_sel,
                   f"correlation inside the {'top' if high else 'bottom'} "
                   f"{quantile:.0%} of a LAGGED regime conditioner ({n_sel} observations); the "
                   "conditioner is known before the returns it labels, so this selects a regime "
                   "and not a realisation",
                   {"quantile": quantile, "high": high,
                    "mean_pairwise_corr": round(float(corr[iu].mean()), 4)})


def realised_breadth(series: Mapping[str, Mapping[str, float]], *,
                     min_overlap: int = MIN_PAIR_OVERLAP,
                     name: str = "realised_returns") -> Reading:
    """Independent bets from the sleeves' OWN realised P&L, on overlapping days only.

    The measurement the exposure readings cannot make, and the one that captures timing and
    mechanism differences the exposure view refuses to claim. It needs history: a pair with fewer
    than ``min_overlap`` common trading days contributes nothing, and a book where NO pair reaches
    the floor is UNMEASURED. The floor is not lowered to produce an answer -- a correlation
    estimated from eight days is indistinguishable from independence, and reading it as
    independence is exactly how a correlated book comes to size like a diversified one.

    Averaging is in Fisher-z space and the UPPER 95% bound is returned, not the point estimate:
    correlations are estimated on whatever regime happened to be sampled, and the desk takes the
    breadth its evidence supports at the pessimistic end.
    """
    names = sorted(series)
    n = len(names)
    if n < 2:
        return _unmeasured(name, f"{n} sleeve(s) with realised returns; correlation needs two",
                           n_nominal=n)
    zs: list[float] = []
    smallest = 0
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            common = sorted(set(series[a]) & set(series[b]))
            if len(common) < int(min_overlap):
                continue
            xa = np.array([float(series[a][d]) for d in common], dtype="float64")
            xb = np.array([float(series[b][d]) for d in common], dtype="float64")
            if xa.std() <= 0 or xb.std() <= 0:
                continue
            r = float(np.corrcoef(xa, xb)[0, 1])
            if not math.isfinite(r):
                continue
            r = max(min(r, 0.999999), -0.999999)
            zs.append(math.atanh(r))
            smallest = len(common) if smallest == 0 else min(smallest, len(common))
    if not zs:
        return _unmeasured(
            name, f"no sleeve pair has {min_overlap} overlapping trading days ({n} sleeves); the "
                  "floor is not lowered to produce a number", n_nominal=n)
    z_bar = sum(zs) / len(zs)
    se = 1.0 / math.sqrt(max(smallest - 3, 1))
    rho_upper = math.tanh(z_bar + 1.645 * se)
    return Reading(name, MEASURED, effective_bets(n, rho_upper), n, smallest,
                   f"{len(zs)} pair(s) cleared the {min_overlap}-day overlap floor, thinnest "
                   f"overlap {smallest}d; rho <= {rho_upper:.3f} at the 95% upper bound, not the "
                   "point estimate",
                   {"n_pairs": len(zs), "rho_upper": round(rho_upper, 4)})


def headline(readings: Sequence[Reading], n_nominal: int) -> dict[str, Any]:
    """The number to publish: nominal against the SMALLEST measured breadth, and why.

    THE MINIMUM, NEVER THE MEAN AND NEVER THE BEST. Each reading answers a different question --
    what the exposures imply, what the systematic part implies, what a stress regime implies, what
    the realised returns imply -- and a book is only as diversified as its worst true answer.
    Averaging them would let one optimistic reading buy leverage the others say is not there, and
    taking the best is the same error with less arithmetic.

    Every UNMEASURED reading is listed by name with its reason. Absence is never folded into the
    verdict: a book with one measured reading has one measured reading, and saying so is the point.
    """
    measured = [r for r in readings if r.measured]
    unmeasured = [r for r in readings if not r.measured]
    best: Reading | None = None
    for r in measured:
        if best is None or (r.n_eff is not None and best.n_eff is not None
                            and r.n_eff < best.n_eff):
            best = r
    k = None if best is None else float(best.n_eff or 0.0)
    ratio = None if (k is None or n_nominal <= 0) else k / float(n_nominal)
    return {
        "n_nominal": int(n_nominal),
        "effective_breadth": None if k is None else round(k, 3),
        "binding_reading": None if best is None else best.name,
        "breadth_ratio": None if ratio is None else round(ratio, 4),
        "sharpe_multiplier_vs_one_bet": None if k is None else round(math.sqrt(max(k, 0.0)), 3),
        "status": MEASURED if k is not None else UNMEASURED,
        "readings": [r.as_dict() for r in readings],
        "unmeasured": [{"name": r.name, "why": r.why} for r in unmeasured],
        "rule": (
            "effective breadth is the MINIMUM over the measured readings, because a book is only "
            "as diversified as its worst true answer; combined Sharpe scales as sqrt(k_eff), so "
            f"{n_nominal} nominal sleeves at k_eff "
            + ("UNMEASURED" if k is None else f"{k:.2f}")
            + " compound like "
            + ("an unmeasured number of" if k is None else f"{k:.2f}")
            + " bets, not like "
            + f"{n_nominal}"),
    }

```

### libs\research\mechanism_claims.py
```python
"""Mechanism claims out of text in every language the desk mines -- the whole world, one grammar.

    a CLAIM  =  a sentence that names a market QUANTITY, a DIRECTION and a HORIZON

That is the whole grammar, and it is deliberately shallow. A trader's interview, a competition
write-up, a forum reply or a README does not state a family and parameters; it states that
"gold usually reverses after the night-session open when the day range is already wide", and
the value of the sentence is that it is FALSIFIABLE on bars the desk already holds. Everything
richer than this -- the exact rule, the parameters, the instrument mapping -- is the deepening
worker's job, through the compiler's existing contract, so nothing here can invent a family.

WHY EVERY LANGUAGE IS FIRST-CLASS (principal, 2026-09-05: "deep forests in ALL major languages
... widen deep-forest to full global, 100 percent"). The Chinese forest was the proof: a large
practitioner literature the English-speaking crowd never reads, and even a dubious trading story
names a testable mechanism. The same argument holds for Japanese botters, Korean futures boards,
Taiwanese option writers, Vietnamese derivatives forums, Brazilian B3 traders, Polish GPW boards,
Turkish lira desks and Russian smart-lab -- and a claim extractor that speaks only English and
Chinese reports every other forest as empty, which is the L1.28a failure: absence
indistinguishable from emptiness. Vocabulary here is per language, SEEDS NEVER BOUNDARIES; a
region's frontier seat extends its own list (docs/research/search_operator_library.md OP-041).

INSTRUMENTS ARE MAPPED, NEVER INVENTED. A story about 沪金 is a story about gold; the desk trades
XAUUSD. Every candidate symbol in `INSTRUMENT_ALIASES` is a name Fusion actually quotes
(desks/mt5/data/universe/universe.json, first candidate first); instruments with no Fusion
analogue (螺纹钢, KOSPI, Nifty, IHSG, WIG20 ...) are kept as MECHANISM-CLASS transfers -- the
mechanism is the fuel, the instrument is whatever the desk can actually quote -- and the row says
so. A claim with NO analogue AND no transfer note is dropped and COUNTED (`dropped_unmappable`):
a summary nobody can test is not a hypothesis.

INDIRECT EDGES ARE THE POINT. "Brazilian soy exports" is a claim about USDBRL, "the CBRT hiked"
is a claim about USDTRY, "the Shanghai gold premium" is a claim about XAUUSD -- a foreign dataset
or event, an information shock, an MT5 instrument. `INDIRECT_CHANNELS` maps such triggers to the
pair they move, and every claim records its `channel` ("direct" when the source names the MT5
instrument, "indirect" otherwise) so the funnel can measure whether indirect channels convert.

DEDUPLICATE FIRST. The same story told on ten sites is ONE mechanism: `mechanism_key` folds
instrument, mechanism class, direction bucket and horizon bucket into a stable key, so the miner
queues one deepening task with ten provenance rows rather than ten tasks.

Crypto-EXCHANGE claims are dropped at the door (standing order 2026-08-18); Fusion's crypto CFDs
remain reachable through their own aliases.
"""
# ruff: noqa: RUF001 -- a lexicon in twenty-six scripts is made of the
# "ambiguous" characters this rule guards against; here they are the data, not typos.
from __future__ import annotations

import hashlib
import re
from typing import Any

# ============================================================================== vocabulary
# One (QUANTITY, DIRECTION, HORIZON) triple per language. Chinese and English first because they
# were first; the rest at the same depth, in the vocabulary each community actually uses (a
# translated English phrase finds translated English content, which is the corpus already read).
# Non-ASCII words are written as literals on purpose: they are data, and an escape would hide
# what the lexicon says from the next reader.

QUANTITY_EN: tuple[str, ...] = (
    "momentum", "reversal", "mean reversion", "carry", "swap", "breakout", "range",
    "volatility", "spread", "order flow", "imbalance", "positioning", "cot", "seasonal",
    "session", "open", "close", "fix", "rollover", "gap", "correlation", "cointegration",
    "pairs", "lead", "lag", "surprise", "cpi", "nfp", "rate", "yield", "factor", "residual",
    "skew", "kurtosis", "liquidity", "flow", "inventory", "basis", "term structure", "premium",
    "drawdown", "trend", "pullback", "stop hunt", "sweep", "vwap", "volume", "open interest",
    "expiry", "auction", "intervention", "rate decision", "hike", "cut", "curve", "spot",
    "futures", "stocks", "inventories", "exports", "imports", "shipping", "freight", "harvest",
    "weather", "etf flows", "fund flows", "options", "gamma", "vix", "risk reversal", "fixing",
)
QUANTITY_ZH: tuple[str, ...] = (
    "动量", "反转", "均值回归", "均值回复", "趋势", "突破", "假突破", "套利", "基差", "价差",
    "持仓",
    "成交量", "量能", "波动率", "跳空", "缺口", "隔夜", "夜盘", "开盘", "收盘", "换月", "展期",
    "升水", "贴水", "利差", "掉期", "隔夜利息", "季节性", "时段", "资金流", "主力", "库存",
    "期限结构", "相关性", "协整", "领先", "滞后", "非农", "通胀", "加息", "降息", "利率",
    "美元指数", "流动性", "订单流", "盘口", "委托", "止损", "日内", "波段", "高频", "做市",
    "滑点", "冲击成本", "量价", "放量", "缩量", "振幅", "均线", "布林", "回撤", "回调", "反弹",
    "跨期", "跨品种", "跨市", "内外盘", "沪伦比", "金银比", "金油比", "持仓量", "多空比",
    "黄金", "白银", "原油", "铜", "股指", "外汇", "美元", "欧元", "英镑", "日元", "澳元", "恒指",
    "纳指", "标普", "道指", "德指", "日经", "汇率", "点差", "atr", "rsi", "macd", "kdj",
    "溢价", "央行", "干预", "结算", "交割", "到期", "出口", "进口", "运费", "天气", "产量",
)
DIRECTION_EN: tuple[str, ...] = (
    "long", "short", "buy", "sell", "fade", "follow", "revert", "continue", "increase",
    "decrease", "predict", "forecast", "outperform", "underperform", "positive", "negative",
    "rally", "sell-off", "selloff", "bounce", "reverse", "expand", "contract", "widen", "narrow",
    "rise", "rises", "fall", "falls", "drop", "drops", "strengthen", "weaken", "appreciate",
    "depreciate", "bullish", "bearish", "higher", "lower", "steepen", "flatten", "rebound",
    "rebounds", "fell", "rose", "dropped", "rallied", "gained", "gains", "weakened",
    "strengthened", "bounced", "reversed", "fade", "fades", "bounces", "reverts", "continues",
    "rallies", "widens", "narrows", "steepens", "flattens", "strengthens", "weakens",
    "appreciates", "depreciates", "reverses", "expands", "contracts", "climbs", "climb", "slides",
    "slide", "sinks", "surges", "surge", "tumbles", "jumps", "dips", "dip",
)
DIRECTION_ZH: tuple[str, ...] = (
    "做多", "做空", "买入", "卖出", "反向", "顺势", "逆势", "回归", "延续", "上涨", "下跌", "预测",
    "跑赢", "跑输", "正相关", "负相关", "追涨", "杀跌", "抄底", "摸顶", "止盈", "加仓", "减仓",
    "多头", "空头", "看多", "看空", "走强", "走弱", "收敛", "扩大", "反弹", "回落", "冲高", "跳水",
    "涨", "跌", "收窄", "拉升", "砸盘", "平仓", "开仓", "入场", "出场", "升值", "贬值",
)
HORIZON_EN: tuple[str, ...] = (
    "minute", "minutes", "hour", "hours", "hourly", "daily", "day", "days", "week", "weekly",
    "month", "monthly", "intraday", "overnight", "bar", "bars", "h1", "h4", "d1", "m5", "m15",
    "session", "open", "close", "tick", "quarter", "quarterly", "expiry", "next day",
)
HORIZON_ZH: tuple[str, ...] = (
    "分钟", "小时", "日内", "隔夜", "当日", "次日", "每日", "日线", "周线", "月线", "开盘后",
    "收盘前", "夜盘", "早盘", "尾盘", "根k线", "交易日", "一周", "一个月", "tick", "秒级",
    "分钟级", "小时级", "日级", "周", "月", "季度",
)

# ---- Traditional Chinese (Taiwan / Hong Kong): the same grammar in the other script. Shared
# characters (突破, 原油) are covered by the simplified table, which is searched as well.
QUANTITY_ZHT: tuple[str, ...] = (
    "動量", "反轉", "均值回歸", "趨勢", "假突破", "套利", "基差", "價差", "持倉", "成交量",
    "量能", "波動率", "跳空", "缺口", "隔夜", "夜盤", "開盤", "收盤", "換月", "轉倉", "升水",
    "貼水", "利差", "掉期", "隔夜利息", "季節性", "時段", "資金流", "主力", "庫存", "期限結構",
    "相關性", "協整", "領先", "滯後", "非農", "通膨", "升息", "降息", "利率", "美元指數",
    "流動性", "訂單流", "盤口", "委託", "停損", "日內", "波段", "高頻", "造市", "滑價", "量價",
    "爆量", "縮量", "振幅", "均線", "布林", "回撤", "回檔", "反彈", "跨期", "跨市", "內外盤",
    "金銀比", "金油比", "未平倉", "多空比", "黃金", "白銀", "銅", "股指", "外匯", "歐元",
    "英鎊", "日圓", "澳幣", "恆指", "恆生", "那斯達克", "納斯達克", "標普", "道瓊", "德指",
    "日經", "匯率", "點差", "台指", "加權", "選擇權", "期貨", "法人", "外資", "投信", "自營商",
    "融資", "融券", "借券", "籌碼", "當沖", "報酬", "乖離", "支撐", "壓力", "前高", "前低",
    "台股", "港股", "美股", "台幣", "港幣", "國企", "北水", "港股通", "南下資金", "牛熊證",
    "窩輪", "權證", "溢價", "結算", "央行", "干預", "運費", "產量", "出口",
)
DIRECTION_ZHT: tuple[str, ...] = (
    "做多", "做空", "買入", "賣出", "反向", "順勢", "逆勢", "回歸", "延續", "上漲", "下跌", "預測",
    "跑贏", "跑輸", "正相關", "負相關", "追漲", "殺跌", "抄底", "摸頭", "停利", "加碼", "減碼",
    "多頭", "空頭", "看多", "看空", "走強", "走弱", "收斂", "擴大", "反彈", "回落", "衝高",
    "跳水", "漲", "跌", "收窄", "拉抬", "殺盤", "平倉", "開倉", "進場", "出場", "多單", "空單",
    "站上", "跌破", "拉回", "上攻", "翻多", "翻空", "升值", "貶值",
)
HORIZON_ZHT: tuple[str, ...] = (
    "分鐘", "小時", "日內", "隔夜", "當日", "次日", "每日", "日線", "週線", "月線", "開盤後",
    "收盤前", "夜盤", "早盤", "尾盤", "根k線", "交易日", "一週", "一個月", "秒級", "分鐘級",
    "小時級", "日級", "週", "月", "盤中", "盤後", "盤前", "當沖", "隔日沖", "結算日", "週選",
    "月選", "除息", "季底", "年底",
)

# ---- Japanese: the botter / FX-blog register (note.com, Qiita, みんかぶ, 株探, 5ch 株板).
QUANTITY_JA: tuple[str, ...] = (
    "モメンタム", "逆張り", "順張り", "トレンド", "トレンドフォロー", "ブレイク", "ブレイクアウト",
    "裁定", "スプレッド", "ボラティリティ", "窓", "ギャップ", "スワップ", "キャリー", "出来高",
    "建玉", "季節", "季節性", "アノマリー", "時間帯", "仲値", "ゴールド", "金", "原油", "ドル円",
    "ユーロドル", "日経", "ロンドン", "ニューヨーク", "東京時間", "指標", "雇用統計", "平均回帰",
    "押し目", "戻り", "レンジ", "板", "歩み値", "気配", "スリッページ", "移動平均", "ボリンジャー",
    "一目", "サポート", "レジスタンス", "高値", "安値", "前日高値", "前日安値", "窓埋め",
    "ゴトー日",
    "五十日", "月末", "期末", "実需", "輸出企業", "リバランス", "決算", "配当", "先物",
    "オプション",
    "ベーシス", "限月", "ロールオーバー", "スワップポイント", "金利差", "政策金利", "日銀",
    "fomc", "cpi", "指標発表", "相関", "逆相関", "乖離", "乖離率", "atr", "rsi", "macd",
    "騰落", "空売り", "信用", "貸借", "需給", "買い戻し", "踏み上げ", "投げ", "介入", "為替介入",
    "国債", "利回り", "銀", "プラチナ", "銅", "天然ガス", "ダウ", "ナスダック", "s&p", "dax",
    "ポンド円", "ユーロ円", "豪ドル", "ドルインデックス", "在庫", "出荷", "天候", "運賃",
)
DIRECTION_JA: tuple[str, ...] = (
    "買い", "売り", "ロング", "ショート", "上昇", "下落", "反発", "反落", "続伸", "続落", "戻る",
    "上抜け", "下抜け", "利確", "損切り", "上がる", "下がる", "上がりやすい", "下がりやすい",
    "押し目買い", "戻り売り", "買い増し", "手仕舞い", "エントリー", "イグジット", "決済", "強含",
    "弱含", "円高", "円安", "ドル高", "ドル安", "上振れ", "下振れ", "急騰", "急落", "反転",
)
HORIZON_JA: tuple[str, ...] = (
    "分", "時間", "日", "週", "月", "デイトレ", "スイング", "足", "寄り", "引け", "オーバーナイト",
    "日中", "翌日", "当日", "前場", "後場", "大引け", "寄り付き", "分足", "時間足", "日足",
    "週足", "月足", "秒", "ザラ場", "夜間", "ナイトセッション", "週末", "月初", "年末", "四半期",
)

# ---- Korean: 해외선물 / 주식 boards (Naver, 팍스넷, DC, tistory).
QUANTITY_KO: tuple[str, ...] = (
    "모멘텀", "추세", "돌파", "역추세", "평균회귀", "차익", "스프레드", "변동성", "갭", "스왑",
    "캐리", "거래량", "포지션", "계절", "계절성", "세션", "금", "골드", "원유", "달러", "엔",
    "지수", "고용", "이동평균", "볼린저", "지지", "저항", "고점", "저점", "전일", "눌림목",
    "되돌림", "박스권", "횡보", "거래대금", "미결제약정", "호가", "체결", "슬리피지", "베이시스",
    "만기", "롤오버", "금리차", "기준금리", "한은", "연준", "고용지표", "물가", "지표발표",
    "아시아장", "런던장", "뉴욕장", "시간대", "상관관계", "이격도", "공매도", "수급", "외국인",
    "기관", "개인", "프로그램매매", "선물", "옵션", "차익거래", "괴리율", "환율", "달러원",
    "원달러", "엔화", "유가", "금값", "은", "구리", "나스닥", "다우", "s&p", "코스피", "코스닥",
    "국채", "재고", "수출", "운임", "개입", "외환당국", "atr", "rsi", "macd",
)
DIRECTION_KO: tuple[str, ...] = (
    "매수", "매도", "롱", "숏", "상승", "하락", "반등", "급락", "급등", "돌파", "이탈", "익절",
    "손절", "오른다", "내린다", "오르는", "내리는", "강세", "약세", "추격매수", "저점매수",
    "고점매도", "진입", "청산", "절상", "절하", "강해", "약해",
)
HORIZON_KO: tuple[str, ...] = (
    "분", "시간", "일", "주", "월", "데이", "스윙", "봉", "장초", "장마감", "오버나잇", "장중",
    "분봉", "시간봉", "일봉", "주봉", "월봉", "당일", "익일", "전일", "장초반", "장후반", "종가",
    "시가", "야간", "주말", "월말", "월초", "초", "틱", "단타", "스캘핑", "분기",
)

# ---- Russian and Ukrainian (stems: Cyrillic inflects, a stem catches every case).
QUANTITY_RU: tuple[str, ...] = (
    "моментум", "импульс", "разворот", "возврат к среднему", "тренд", "пробой", "арбитраж",
    "спред", "волатильност", "гэп", "своп", "кэрри", "объем", "объём", "позици", "сезонн",
    "сесси", "золот", "нефт", "доллар", "евро", "индекс", "фиксинг", "ставк", "нонфарм",
    "скользящ", "боллиндж", "поддержк", "сопротивлен", "максимум", "минимум", "откат", "флэт",
    "боковик", "открыт интерес", "стакан", "проскальзыван", "базис", "экспирац", "ролл",
    "инфляц", "корреляц", "дивергенц", "шорт-сквиз", "ликвидн", "азиатск", "лондон", "нью-йорк",
    "паттерн", "уровен", "rsi", "macd", "atr", "серебр", "медь", "газ", "рубл", "насдак", "dax",
    "ртс", "ммвб", "мосбирж", "фьючерс", "опцион", "цб", "фрс", "интервенц", "офз", "доходност",
    "запас", "экспорт", "фрахт", "урожа",
)
DIRECTION_RU: tuple[str, ...] = (
    "лонг", "шорт", "покуп", "прода", "рост", "падени", "отскок", "продолж", "пробит", "фиксац",
    "стоп", "растет", "растёт", "падает", "снижен", "вход", "выход", "откуп", "слив", "усилен",
    "ослаблен", "бычий", "медвеж", "вверх", "вниз", "укреплен", "девальвац",
)
HORIZON_RU: tuple[str, ...] = (
    "минут", "час", "дне", "день", "недел", "месяц", "интрадей", "свинг", "свеч", "открыти",
    "закрыти", "овернайт", "таймфрейм", "тик", "скальп", "дневн", "недельн", "месячн", "утр",
    "вечер", "ночн", "внутри дня", "квартал",
)
QUANTITY_UK: tuple[str, ...] = (
    "моментум", "імпульс", "розворот", "повернення до середнього", "тренд", "пробій", "арбітраж",
    "спред", "волатильн", "геп", "своп", "керрі", "обсяг", "позиці", "сезонн", "сесі", "золот",
    "нафт", "долар", "євро", "індекс", "фіксинг", "ставк", "ковзн", "підтримк", "опір",
    "максимум", "мінімум", "відкат", "бічн", "ліквідн", "кореляц", "гривн", "нбу", "інтервенц",
    "запас", "експорт", "фрахт", "урожа", "ф'ючерс", "опціон", "дохідн", "інфляц",
)
DIRECTION_UK: tuple[str, ...] = (
    "лонг", "шорт", "купівл", "купу", "прода", "зростан", "зроста", "падінн", "падає", "відскок",
    "продовж", "пробит", "фіксац", "стоп", "вхід", "вихід", "зниж", "посилен", "послаблен",
    "бичач", "ведмеж", "вгору", "вниз", "зміцн", "девальвац",
)
HORIZON_UK: tuple[str, ...] = (
    "хвилин", "годин", "дня", "день", "тижн", "місяц", "інтрадей", "свінг", "свічк", "відкритт",
    "закритт", "овернайт", "таймфрейм", "тік", "скальп", "денн", "тижнев", "місячн", "ранк",
    "вечір", "нічн", "квартал",
)

# ---- Vietnamese: F319 / CafeF / VnDirect derivatives forums.
QUANTITY_VI: tuple[str, ...] = (
    "xu hướng", "động lượng", "đảo chiều", "hồi quy", "phá vỡ", "breakout", "biên độ",
    "biến động", "khối lượng", "thanh khoản", "dòng tiền", "khối ngoại", "tự doanh", "chênh lệch",
    "spread", "cơ sở", "phái sinh", "hợp đồng tương lai", "đáo hạn", "kỳ hạn", "lãi suất",
    "tỷ giá", "mùa vụ", "tính mùa vụ", "tương quan", "hỗ trợ", "kháng cự", "đỉnh", "đáy",
    "đường trung bình", "rsi", "macd", "bollinger", "nến", "gap", "khoảng trống", "vàng", "dầu",
    "bạc", "chỉ số", "vn-index", "vn30", "chứng khoán", "cổ phiếu", "ato", "atc", "giá đóng cửa",
    "giá mở cửa", "margin", "ký quỹ", "call margin", "giải chấp", "bán tháo", "sóng", "nhịp",
    "tồn kho", "xuất khẩu", "nhập khẩu", "cước", "thời tiết", "ngân hàng nhà nước", "can thiệp",
    "trái phiếu", "lợi suất", "usd", "đô la",
)
DIRECTION_VI: tuple[str, ...] = (
    "mua", "bán", "long", "short", "tăng", "giảm", "bật tăng", "hồi phục", "điều chỉnh",
    "phá đỉnh", "thủng đáy", "đảo chiều", "tiếp diễn", "chốt lời", "cắt lỗ", "bắt đáy", "đu đỉnh",
    "tăng giá", "giảm giá", "đi lên", "đi xuống", "vượt", "xuyên thủng", "gom", "xả", "vào lệnh",
    "thoát lệnh", "mở vị thế", "đóng vị thế", "mất giá", "lên giá",
)
HORIZON_VI: tuple[str, ...] = (
    "phút", "giờ", "ngày", "tuần", "tháng", "phiên", "trong phiên", "cuối phiên", "đầu phiên",
    "qua đêm", "phiên sau", "hôm sau", "ngắn hạn", "trung hạn", "dài hạn", "khung", "nến ngày",
    "nến tuần", "nến giờ", "intraday", "t+2", "t+3", "lướt sóng", "scalp", "quý",
)

# ---- Thai: Pantip Sinthorn / stock2morrow / SET research.
QUANTITY_TH: tuple[str, ...] = (
    "โมเมนตัม", "แนวโน้ม", "กลับตัว", "ทะลุ", "เบรคเอาท์", "กรอบ", "ไซด์เวย์", "ความผันผวน",
    "วอลุ่ม", "ปริมาณการซื้อขาย", "สภาพคล่อง", "ฟันด์โฟลว์", "ต่างชาติ", "สเปรด", "เบสิส",
    "ฟิวเจอร์ส", "ออปชั่น", "หมดอายุ", "ดอกเบี้ย", "ค่าเงิน", "บาท", "ฤดูกาล", "ความสัมพันธ์",
    "แนวรับ", "แนวต้าน", "จุดสูงสุด", "จุดต่ำสุด", "เส้นค่าเฉลี่ย", "ema", "rsi", "macd",
    "แท่งเทียน", "แก๊ป", "ทองคำ", "ทอง", "น้ำมัน", "ดัชนี", "set50", "หุ้น", "ราคาปิด",
    "ราคาเปิด", "มาร์จิ้น", "ฟอร์ซเซล", "เทขาย", "สต็อก", "ส่งออก", "ค่าระวาง", "แบงก์ชาติ",
    "ธปท", "แทรกแซง", "พันธบัตร", "ผลตอบแทน", "ดอลลาร์",
)
DIRECTION_TH: tuple[str, ...] = (
    "ซื้อ", "ขาย", "ลอง", "ชอร์ต", "ขึ้น", "ลง", "เด้ง", "รีบาวด์", "ปรับฐาน", "ย่อ", "ทะลุ",
    "หลุด", "กลับตัว", "ต่อเนื่อง", "ทำกำไร", "ตัดขาดทุน", "คัทลอส", "ช้อน", "ดอย", "บวก",
    "ลบ", "แรง", "อ่อน", "เข้า", "ออก", "เปิดสถานะ", "ปิดสถานะ", "ไล่ราคา", "แข็งค่า", "อ่อนค่า",
)
HORIZON_TH: tuple[str, ...] = (
    "นาที", "ชั่วโมง", "วัน", "สัปดาห์", "เดือน", "รายวัน", "รายสัปดาห์", "ระหว่างวัน", "ข้ามคืน",
    "ปิดตลาด", "เปิดตลาด", "ช่วงเช้า", "ช่วงบ่าย", "ท้ายตลาด", "เดย์เทรด", "สวิง", "ไทม์เฟรม",
    "แท่ง", "ไตรมาส",
)

# ---- Indonesian / Malay: Stockbit, Kaskus, i3investor, Lowyat (one lexicon, shared roots).
QUANTITY_ID: tuple[str, ...] = (
    "momentum", "tren", "trend", "pembalikan", "reversal", "breakout", "penembusan", "sideways",
    "volatilitas", "volume", "likuiditas", "aliran dana", "asing", "spread", "basis", "berjangka",
    "futures", "kedaluwarsa", "suku bunga", "bunga", "kurs", "rupiah", "ringgit", "musiman",
    "korelasi", "support", "resistance", "resisten", "puncak", "dasar", "moving average",
    "rata-rata bergerak", "rsi", "macd", "candle", "gap", "emas", "minyak", "perak", "tembaga",
    "indeks", "ihsg", "klci", "saham", "harga penutupan", "harga pembukaan", "margin", "bandar",
    "akumulasi", "distribusi", "stok", "persediaan", "ekspor", "impor", "ongkos kirim", "cuaca",
    "bank indonesia", "bank negara", "intervensi", "obligasi", "imbal hasil", "dolar",
)
DIRECTION_ID: tuple[str, ...] = (
    "beli", "jual", "long", "short", "naik", "turun", "rebound", "pantul", "koreksi", "menembus",
    "jebol", "berbalik", "berlanjut", "ambil untung", "taking profit", "cut loss", "potong rugi",
    "serok", "nyangkut", "menguat", "melemah", "masuk", "keluar", "buka posisi", "tutup posisi",
    "bullish", "bearish", "terdepresiasi", "terapresiasi",
)
HORIZON_ID: tuple[str, ...] = (
    "menit", "jam", "hari", "minggu", "pekan", "bulan", "harian", "mingguan", "intraday",
    "semalam", "penutupan", "pembukaan", "sesi", "sesi pagi", "sesi siang", "akhir sesi",
    "scalping", "swing", "jangka pendek", "jangka panjang", "time frame", "kuartal",
)

# ---- Hindi: Moneycontrol boards, Hindi finance YouTube descriptions, Hindi blogs.
QUANTITY_HI: tuple[str, ...] = (
    "मोमेंटम", "ट्रेंड", "रुझान", "रिवर्सल", "पलटाव", "ब्रेकआउट", "रेंज", "वोलैटिलिटी",
    "उतार-चढ़ाव", "वॉल्यूम", "लिक्विडिटी", "तरलता", "स्प्रेड", "बेसिस", "फ्यूचर्स", "वायदा",
    "ऑप्शन", "एक्सपायरी", "ब्याज दर", "रुपया", "डॉलर", "सीज़नल", "मौसमी", "सहसंबंध", "सपोर्ट",
    "रेजिस्टेंस", "प्रतिरोध", "समर्थन", "मूविंग एवरेज", "rsi", "macd", "कैंडल", "गैप", "सोना",
    "चांदी", "कच्चा तेल", "तांबा", "इंडेक्स", "निफ्टी", "बैंक निफ्टी", "सेंसेक्स", "शेयर",
    "बंद भाव", "खुला भाव", "fii", "dii", "ओपन इंटरेस्ट", "pcr", "vix", "आरबीआई", "रिज़र्व बैंक",
    "हस्तक्षेप", "बॉन्ड", "यील्ड", "निर्यात", "आयात", "भंडार", "मानसून", "एमसीएक्स",
)
DIRECTION_HI: tuple[str, ...] = (
    "खरीद", "बेच", "लॉन्ग", "शॉर्ट", "तेजी", "मंदी", "बढ़", "गिर", "उछाल", "रिकवरी", "करेक्शन",
    "गिरावट", "तोड़", "टूट", "पलट", "जारी", "मुनाफा", "प्रॉफिट बुक", "स्टॉप लॉस", "मजबूत",
    "कमजोर", "एंट्री", "एग्जिट", "ऊपर", "नीचे", "चढ़",
)
HORIZON_HI: tuple[str, ...] = (
    "मिनट", "घंटा", "घंटे", "दिन", "हफ्ता", "सप्ताह", "महीना", "महीने", "इंट्राडे", "ओवरनाइट",
    "बंद", "खुलने", "सुबह", "दोपहर", "शाम", "स्कैल्पिंग", "स्विंग", "शॉर्ट टर्म", "लॉन्ग टर्म",
    "टाइमफ्रेम", "साप्ताहिक", "मासिक", "दैनिक", "एक्सपायरी", "तिमाही",
)

# ---- German: wallstreet-online, finanzen.net, stock3, Bundesbank.
QUANTITY_DE: tuple[str, ...] = (
    "momentum", "trend", "umkehr", "rückkehr zum mittelwert", "mean reversion", "ausbruch",
    "seitwärts", "range", "volatilität", "volumen", "umsatz", "liquidität", "orderfluss", "spread",
    "basis", "terminkurs", "futures", "verfall", "verfallstag", "hexensabbat", "zins", "zinsen",
    "zinsdifferenz", "wechselkurs", "saison", "korrelation", "unterstützung", "widerstand",
    "gleitend", "durchschnitt", "rsi", "macd", "kerze", "gap", "kurslücke", "gold", "silber",
    "rohöl", "kupfer", "index", "dax", "mdax", "euro stoxx", "aktie", "schlusskurs",
    "eröffnungskurs", "positionierung", "cot", "stimmung", "sentiment", "überkauft", "überverkauft",
    "dollar", "euro", "lagerbestand", "lagerbestände", "export", "fracht", "ernte", "ezb",
    "bundesbank", "intervention", "anleihe", "rendite", "bund",
)
DIRECTION_DE: tuple[str, ...] = (
    "kaufen", "kauf", "verkaufen", "verkauf", "long", "short", "steig", "fall", "fällt", "erhol",
    "korrektur", "durchbr", "bricht", "dreht", "umkehr", "fortsetz", "gewinnmitnahme", "stopp",
    "stärk", "schwäch", "einstieg", "ausstieg", "aufwärts", "abwärts", "hausse", "baisse",
    "bullisch", "bärisch", "nachkauf", "glattstell", "aufwert", "abwert",
)
HORIZON_DE: tuple[str, ...] = (
    "minute", "stunde", "stündlich", "tag", "täglich", "woche", "wöchentlich", "monat",
    "monatlich", "intraday", "übernacht", "schluss", "handelsschluss", "tagesschluss", "eröffnung",
    "handelstag", "sitzung",
    "session", "vormittag", "nachmittag", "scalp", "swing", "kurzfristig", "langfristig",
    "zeitebene", "tageskerze", "wochenkerze", "quartal",
)

# ---- French: Boursorama, ABC Bourse, Banque de France.
QUANTITY_FR: tuple[str, ...] = (
    "momentum", "tendance", "retournement", "retour à la moyenne", "cassure", "breakout", "range",
    "latéral", "volatilité", "volume", "liquidité", "flux", "spread", "contango", "backwardation",
    "échéance", "taux", "différentiel", "change", "saisonnalité", "saisonnier", "corrélation",
    "support", "résistance", "plus haut", "plus bas", "moyenne mobile", "rsi", "macd", "bougie",
    "gap", "l'or", "once", "pétrole", "brut", "cuivre", "indice", "cac", "dax", "action", "clôture",
    "ouverture", "positionnement", "cot", "sentiment", "suracheté", "survendu", "dollar", "euro",
    "carry", "stocks", "exportations", "fret", "récolte", "bce", "intervention", "obligation",
    "rendement", "oat",
)
DIRECTION_FR: tuple[str, ...] = (
    "achat", "achet", "vente", "vend", "long", "short", "hausse", "baisse", "monte", "rebond",
    "correction", "casse", "franchit", "retourne", "continue", "prise de bénéfice", "stop",
    "renforce", "faiblit", "entrée", "sortie", "haussier", "baissier", "repli", "décroch",
    "s'envole", "s'apprécie", "se déprécie", "grimpe", "chute",
)
HORIZON_FR: tuple[str, ...] = (
    "minute", "heure", "horaire", "jour", "journalier", "quotidien", "semaine", "hebdomadaire",
    "mois", "mensuel", "intraday", "overnight", "clôture", "ouverture", "séance", "session",
    "matin", "après-midi", "scalping", "swing", "court terme", "long terme", "unité de temps",
    "bougie", "trimestre",
)

# ---- Italian: FinanzaOnline, Banca d'Italia.
QUANTITY_IT: tuple[str, ...] = (
    "momentum", "trend", "tendenza", "inversione", "ritorno alla media", "rottura", "breakout",
    "laterale", "range", "volatilità", "volume", "liquidità", "flusso", "spread", "base",
    "scadenza", "tasso", "tassi", "differenziale", "cambio", "stagionalità", "stagionale",
    "correlazione", "supporto", "resistenza", "massimo", "minimo", "media mobile", "rsi", "macd",
    "candela", "gap", "oro", "argento", "petrolio", "greggio", "rame", "indice", "ftse mib", "dax",
    "azione", "chiusura", "apertura", "posizionamento", "cot", "sentiment", "ipercomprato",
    "ipervenduto", "dollaro", "euro", "carry", "scorte", "export", "noli", "raccolto", "bce",
    "intervento", "btp", "rendimento",
)
DIRECTION_IT: tuple[str, ...] = (
    "compra", "acquist", "vend", "long", "short", "rialzo", "ribasso", "sale", "scende", "rimbalz",
    "correzione", "rompe", "supera", "inverte", "prosegue", "presa di profitto", "stop", "rafforz",
    "indebol", "ingresso", "uscita", "rialzista", "ribassista", "storno", "si apprezza",
    "si deprezza", "crolla",
)
HORIZON_IT: tuple[str, ...] = (
    "minut", "ora", "orari", "giorn", "settiman", "mese", "mensil", "intraday", "overnight",
    "chiusura", "apertura", "seduta", "sessione", "mattina", "pomeriggio", "scalping", "swing",
    "breve termine", "lungo termine", "time frame", "candela", "trimestre",
)

# ---- Spanish (Spain and Latin America): Rankia, X-Trader, Rava, El Economista.
QUANTITY_ES: tuple[str, ...] = (
    "momentum", "impulso", "tendencia", "reversión", "retorno a la media", "ruptura", "breakout",
    "rango", "lateral", "volatilidad", "volumen", "liquidez", "flujo", "spread", "diferencial",
    "base", "vencimiento", "tasa", "tipos", "tipo de interés", "cambio", "estacionalidad",
    "estacional", "correlación", "soporte", "resistencia", "máximo", "mínimo", "media móvil", "rsi",
    "macd", "vela", "gap", "hueco", "oro", "plata", "petróleo", "crudo", "cobre", "índice", "ibex",
    "dax", "sp500", "acción", "cierre", "apertura", "posicionamiento", "cot", "sentimiento",
    "sobrecompra", "sobreventa", "dólar", "euro", "peso", "carry", "inventario", "existencias",
    "exportaciones", "flete", "cosecha", "banxico", "banco central", "intervención", "bono",
    "rendimiento", "cepo", "merval", "brecha",
)
DIRECTION_ES: tuple[str, ...] = (
    "compra", "compr", "vend", "venta", "largo", "corto", "long", "short", "alza", "sube", "baja",
    "cae", "rebote", "rebota", "corrección", "rompe", "supera", "gira", "revierte", "continúa",
    "toma de beneficios", "stop", "fortalece", "debilita", "entrada", "salida", "alcista",
    "bajista", "retroceso", "desplome", "se aprecia", "se deprecia", "devalúa",
)
HORIZON_ES: tuple[str, ...] = (
    "minuto", "hora", "horario", "día", "diario", "semana", "semanal", "mes", "mensual",
    "intradía", "intradia", "overnight", "cierre", "apertura", "sesión", "sesion", "mañana",
    "tarde", "scalping", "swing", "corto plazo", "largo plazo", "marco temporal", "temporalidad",
    "vela diaria", "trimestre",
)

# ---- Portuguese (Brazil): InfoMoney, Clube do Valor, Suno, Quantbrasil, Bastter.
QUANTITY_PT: tuple[str, ...] = (
    "momentum", "tendência", "reversão", "retorno à média", "rompimento", "breakout", "lateral",
    "range", "volatilidade", "volume", "liquidez", "fluxo", "estrangeiro", "spread", "base",
    "vencimento", "taxa", "juros", "selic", "diferencial", "câmbio", "sazonalidade", "sazonal",
    "correlação", "suporte", "resistência", "topo", "fundo", "máxima", "mínima", "média móvel",
    "rsi", "macd", "candle", "gap", "ouro", "prata", "petróleo", "cobre", "índice", "ibovespa",
    "ibov", "ação", "fechamento", "abertura", "posicionamento", "cot", "sentimento",
    "sobrecomprado", "sobrevendido", "dólar", "real", "carry", "ajuste", "leilão", "estoque",
    "safra", "exportação", "exportações", "frete", "copom", "bacen", "banco central", "intervenção",
    "swap cambial", "tesouro", "cupom cambial",
)
DIRECTION_PT: tuple[str, ...] = (
    "compra", "compr", "vend", "venda", "comprado", "vendido", "long", "short", "alta", "sobe",
    "baixa", "cai", "queda", "repique", "correção", "rompe", "supera", "vira", "reverte",
    "continua", "realização", "stop", "fortalece", "enfraquece", "entrada", "saída", "altista",
    "baixista", "pullback", "tombo", "dispara", "desvaloriza", "valoriza",
)
HORIZON_PT: tuple[str, ...] = (
    "minuto", "hora", "dia", "diário", "semana", "semanal", "mês", "mensal", "intraday",
    "intradiário", "overnight", "fechamento", "abertura", "pregão", "sessão", "manhã", "tarde",
    "scalping", "swing", "curto prazo", "longo prazo", "tempo gráfico", "candle diário", "after",
    "trimestre",
)

# ---- Arabic: Argaam, Mubasher, ArabicTrader, Gulf exchange research.
QUANTITY_AR: tuple[str, ...] = (
    "زخم", "اتجاه", "انعكاس", "اختراق", "نطاق", "تذبذب", "تقلب", "حجم", "سيولة", "فارق",
    "أساس", "عقود آجلة", "فائدة", "سعر الصرف", "موسمي", "ارتباط", "دعم", "مقاومة", "قمة", "قاع",
    "متوسط متحرك", "شمعة", "فجوة", "ذهب", "فضة", "نفط", "نحاس", "مؤشر", "تاسي", "دولار", "ريال",
    "درهم", "جنيه", "مخزون", "صادرات", "شحن", "البنك المركزي", "ساما", "تدخل", "سندات", "عائد",
    "أوبك", "خام",
)
DIRECTION_AR: tuple[str, ...] = (
    "شراء", "بيع", "صعود", "هبوط", "ارتفاع", "انخفاض", "ارتداد", "تصحيح", "كسر", "اختراق",
    "انعكاس", "استمرار", "جني أرباح", "وقف خسارة", "دخول", "خروج", "يرتفع", "ينخفض", "تراجع",
)
HORIZON_AR: tuple[str, ...] = (
    "دقيقة", "ساعة", "يوم", "يومي", "أسبوع", "أسبوعي", "شهر", "شهري", "خلال اليوم", "ليلي",
    "إغلاق", "افتتاح", "جلسة", "صباح", "مساء", "مضاربة", "إطار زمني", "ربع",
)

# ---- Turkish: Borsa Istanbul boards, Bloomberg HT, KAP.
QUANTITY_TR: tuple[str, ...] = (
    "momentum", "trend", "dönüş", "kırılım", "yatay", "volatilite", "oynaklık", "hacim",
    "likidite", "spread", "baz", "vade", "faiz", "kur", "mevsimsel", "korelasyon", "destek",
    "direnç", "zirve", "dip", "hareketli ortalama", "rsi", "macd", "mum", "gap", "boşluk", "altın",
    "ons", "gümüş", "petrol", "bakır", "endeks", "bist", "dolar", "euro", "lira", "swap", "taşıma",
    "stok", "ihracat", "navlun", "hasat", "merkez bankası", "tcmb", "müdahale", "tahvil", "getiri",
    "enflasyon", "rezerv", "kkm",
)
DIRECTION_TR: tuple[str, ...] = (
    "alım", "satış", "long", "short", "yüksel", "düş", "toparlan", "tepki", "düzeltme", "kır",
    "aş", "dön", "devam", "kâr al", "stop", "güçlen", "zayıfla", "giriş", "çıkış", "yukarı",
    "aşağı", "boğa", "ayı", "değer kazan", "değer kaybet", "al ", "sat ",
)
HORIZON_TR: tuple[str, ...] = (
    "dakika", "saat", "gün", "günlük", "hafta", "haftalık", "ay", "aylık", "gün içi", "gece",
    "kapanış", "açılış", "seans", "sabah", "öğleden", "scalp", "swing", "kısa vade", "uzun vade",
    "zaman dilimi", "mum", "çeyrek",
)

# ---- Hebrew: Globes, TASE research, Bizportal boards.
QUANTITY_HE: tuple[str, ...] = (
    "מומנטום", "מגמה", "היפוך", "פריצה", "טווח", "תנודתיות", "מחזור", "נזילות", "מרווח",
    "בסיס", "חוזים", "ריבית", "שער חליפין", "עונתי", "מתאם", "תמיכה", "התנגדות", "שיא", "שפל",
    "ממוצע נע", "נר", "פער", "זהב", "כסף", "נפט", "נחושת", "מדד", "דולר", "שקל", "מלאי",
    "יצוא", "בנק ישראל", "התערבות", "אג\"ח", "תשואה", "אינפלציה",
)
DIRECTION_HE: tuple[str, ...] = (
    "קנייה", "מכירה", "לונג", "שורט", "עלייה", "ירידה", "עולה", "יורד", "תיקון", "שובר", "פורץ",
    "היפוך", "המשך", "מימוש", "סטופ", "כניסה", "יציאה", "מתחזק", "נחלש", "ייסוף", "פיחות",
)
HORIZON_HE: tuple[str, ...] = (
    "דקה", "דקות", "שעה", "שעות", "יום", "יומי", "שבוע", "שבועי", "חודש", "חודשי", "תוך יומי",
    "לילה", "סגירה", "פתיחה", "מסחר", "בוקר", "ערב", "סווינג", "רבעון",
)

# ---- Polish: Bankier, StockWatch, GPW.
QUANTITY_PL: tuple[str, ...] = (
    "momentum", "trend", "odwrócen", "powrót do średniej", "wybicie", "konsolidac", "zmienność",
    "wolumen", "obrót", "płynność", "spread", "baza", "kontrakt", "wygaśnięci", "stopa", "stóp",
    "kurs", "sezonow", "korelac", "wsparci", "opór", "szczyt", "dołek", "średnia krocząc", "rsi",
    "macd", "świec", "luka", "złoto", "srebro", "ropa", "miedź", "indeks", "wig20", "wig",
    "akcje", "zamknięci", "otwarci", "pozycjonowan", "cot", "nastroj", "dolar", "euro", "złoty",
    "zapas", "eksport", "fracht", "zbior", "nbp", "rpp", "interwenc", "obligac", "rentowność",
    "inflacj",
)
DIRECTION_PL: tuple[str, ...] = (
    "kupn", "kupuj", "sprzeda", "long", "short", "wzrost", "rośnie", "spadek", "spada", "odbici",
    "korekt", "przebij", "przełam", "odwrac", "kontynu", "realizac", "stop", "umacnia", "słabnie",
    "wejści", "wyjści", "byczy", "niedźwiedz", "w górę", "w dół", "aprecjac", "deprecjac",
)
HORIZON_PL: tuple[str, ...] = (
    "minut", "godzin", "dzień", "dni", "dzienn", "tydzień", "tygodni", "miesiąc", "miesięczn",
    "intraday", "overnight", "zamknięci", "otwarci", "sesj", "rano", "popołudni", "scalp",
    "swing", "krótkoterminow", "długoterminow", "interwał", "świec", "kwartał",
)

# ---- Dutch: IEX.nl, Belegger.nl, DNB.
QUANTITY_NL: tuple[str, ...] = (
    "momentum", "trend", "omkeer", "terugkeer naar het gemiddelde", "uitbraak", "zijwaarts",
    "volatiliteit", "volume", "liquiditeit", "spread", "basis", "termijn", "expiratie", "rente",
    "wisselkoers", "seizoen", "correlatie", "steun", "weerstand", "hoogtepunt", "dieptepunt",
    "voortschrijdend gemiddelde", "rsi", "macd", "candle", "gap", "goud", "zilver", "olie",
    "koper", "index", "aex", "aandeel", "slotkoers", "openingskoers", "positionering", "cot",
    "sentiment", "dollar", "euro", "voorraad", "voorraden", "export", "vracht", "oogst", "ecb",
    "dnb", "interventie", "obligatie", "rendement", "inflatie",
)
DIRECTION_NL: tuple[str, ...] = (
    "koop", "kopen", "verkoop", "verkopen", "long", "short", "stijg", "daal", "herstel",
    "correctie",
    "doorbr", "breekt", "draait", "omkeer", "vervolg", "winst nemen", "stop", "sterker", "zwakker",
    "instap", "uitstap", "opwaarts", "neerwaarts", "bullish", "bearish", "apprecieer", "deprecieer",
)
HORIZON_NL: tuple[str, ...] = (
    "minuut", "minuten", "uur", "dag", "dagelijks", "week", "wekelijks", "maand", "maandelijks",
    "intraday", "overnight", "slot", "opening", "handelsdag", "sessie", "ochtend", "middag",
    "scalp", "swing", "korte termijn", "lange termijn", "tijdframe", "kwartaal",
)

# ---- Swedish, Danish, Norwegian, Finnish: Avanza, Nordnet, Shareville, Kauppalehti.
QUANTITY_SV: tuple[str, ...] = (
    "momentum", "trend", "vändning", "återgång till medelvärdet", "utbrott", "sidledes",
    "volatilitet", "volym", "likviditet", "spread", "bas", "termin", "förfall", "ränta",
    "räntor", "växelkurs", "säsong", "korrelation", "stöd", "motstånd", "topp", "botten",
    "glidande medelvärde", "rsi", "macd", "candle", "gap", "guld", "silver", "olja", "koppar",
    "index", "omx", "aktie", "stängningskurs", "öppningskurs", "positionering", "cot",
    "sentiment", "dollar", "euro", "krona", "kronan", "lager", "export", "frakt", "skörd",
    "riksbanken", "intervention", "obligation", "avkastning", "inflation",
)
DIRECTION_SV: tuple[str, ...] = (
    "köp", "sälj", "long", "short", "stig", "steg", "fall", "föll", "sjunk", "rekyl", "studs",
    "korrigering", "bryter", "vänder", "fortsätter", "vinsthemtagning", "stopp", "stärk",
    "försvag", "ingång", "utgång", "uppåt", "nedåt", "bullish", "bearish",
)
HORIZON_SV: tuple[str, ...] = (
    "minut", "timme", "timmar", "dag", "daglig", "vecka", "veckovis", "månad", "månatlig",
    "intradag", "intraday", "övernatt", "stängning", "öppning", "handelsdag", "session",
    "morgon", "eftermiddag", "scalp", "swing", "kort sikt", "lång sikt", "tidsram", "kvartal",
)
QUANTITY_DA: tuple[str, ...] = (
    "momentum", "trend", "vending", "tilbagevenden til gennemsnittet", "udbrud", "sidelæns",
    "volatilitet", "volumen", "likviditet", "spread", "basis", "termin", "udløb", "rente",
    "renter", "valutakurs", "sæson", "korrelation", "støtte", "modstand", "top", "bund",
    "glidende gennemsnit", "rsi", "macd", "candle", "gap", "guld", "sølv", "olie", "kobber",
    "indeks", "omxc", "aktie", "lukkekurs", "åbningskurs", "positionering", "cot", "stemning",
    "dollar", "euro", "krone", "kronen", "lager", "eksport", "fragt", "høst", "nationalbanken",
    "intervention", "obligation", "afkast", "inflation",
)
DIRECTION_DA: tuple[str, ...] = (
    "køb", "sælg", "long", "short", "stig", "steg", "fald", "faldt", "rekyl", "korrektion",
    "bryder", "vender", "fortsætter", "gevinsthjemtagning", "stop", "styrk", "svæk", "indgang",
    "udgang", "opad", "nedad", "bullish", "bearish",
)
HORIZON_DA: tuple[str, ...] = (
    "minut", "time", "timer", "dag", "daglig", "uge", "ugentlig", "måned", "månedlig",
    "intradag", "intraday", "overnight", "lukning", "åbning", "handelsdag", "session", "morgen",
    "eftermiddag", "scalp", "swing", "kort sigt", "lang sigt", "tidsramme", "kvartal",
)
QUANTITY_NO: tuple[str, ...] = (
    "momentum", "trend", "vending", "tilbake til gjennomsnittet", "utbrudd", "sidelengs",
    "volatilitet", "volum", "likviditet", "spread", "basis", "termin", "forfall", "rente",
    "renter", "valutakurs", "sesong", "korrelasjon", "støtte", "motstand", "topp", "bunn",
    "glidende gjennomsnitt", "rsi", "macd", "candle", "gap", "gull", "sølv", "olje", "kobber",
    "indeks", "obx", "aksje", "sluttkurs", "åpningskurs", "posisjonering", "cot", "stemning",
    "dollar", "euro", "krone", "kronen", "lager", "eksport", "frakt", "avling", "norges bank",
    "intervensjon", "obligasjon", "avkastning", "inflasjon", "oljefondet",
)
DIRECTION_NO: tuple[str, ...] = (
    "kjøp", "selg", "long", "short", "stig", "steg", "fall", "falt", "rekyl", "korreksjon",
    "bryter", "snur", "fortsetter", "gevinstsikring", "stopp", "styrk", "svekk", "inngang",
    "utgang", "oppover", "nedover", "bullish", "bearish",
)
HORIZON_NO: tuple[str, ...] = (
    "minutt", "time", "timer", "dag", "daglig", "uke", "ukentlig", "måned", "månedlig",
    "intradag", "intraday", "overnight", "stenging", "åpning", "handelsdag", "sesjon", "morgen",
    "ettermiddag", "scalp", "swing", "kort sikt", "lang sikt", "tidsramme", "kvartal",
)
QUANTITY_FI: tuple[str, ...] = (
    "momentum", "trendi", "käänne", "paluu keskiarvoon", "läpimurto", "sivuttais", "volatiliteetti",
    "volyymi", "vaihto", "likviditeetti", "spread", "basis", "futuuri", "erääntymi", "korko",
    "korot", "valuuttakurssi", "kausi", "korrelaatio", "tuki", "vastus", "huippu", "pohja",
    "liukuva keskiarvo", "rsi", "macd", "kynttilä", "gap", "kulta", "hopea", "öljy", "kupari",
    "indeksi", "omxh", "osake", "päätöskurssi", "avauskurssi", "positiointi", "cot", "sentimentti",
    "dollari", "euro", "varasto", "vienti", "rahti", "sato", "ekp", "interventio",
    "joukkovelkakirja",
    "tuotto", "inflaatio",
)
DIRECTION_FI: tuple[str, ...] = (
    "osta", "osto", "myy", "myynti", "long", "short", "nous", "lask", "elpy", "korjaus", "rikko",
    "kääntyy", "jatkuu", "voittojen kotiutus", "stop", "vahvist", "heikke", "sisään", "ulos",
    "ylös", "alas", "bullish", "bearish",
)
HORIZON_FI: tuple[str, ...] = (
    "minuutti", "tunti", "tuntia", "päivä", "päivittäin", "viikko", "viikoittain", "kuukausi",
    "kuukausittain", "intraday", "yön yli", "päätös", "avaus", "kaupankäyntipäivä", "sessio",
    "aamu", "iltapäivä", "scalp", "swing", "lyhyellä", "pitkällä", "aikaväli", "kynttilä",
    "vuosineljännes",
)

# ---- Swahili: East African markets press (NSE Kenya, DSE Tanzania).
QUANTITY_SW: tuple[str, ...] = (
    "mwelekeo", "kasi", "mabadiliko", "kuvunja", "kiwango", "mtetemo", "kiasi", "ukwasi",
    "tofauti", "riba", "kiwango cha ubadilishaji", "msimu", "uhusiano", "msaada", "upinzani",
    "kilele", "chini", "wastani", "dhahabu", "fedha", "mafuta", "shaba", "faharasa", "hisa", "bei",
    "dola", "shilingi", "hifadhi", "mauzo ya nje", "usafirishaji", "mavuno", "benki kuu",
    "uingiliaji", "hati fungani", "mapato", "mfumuko wa bei", "soko",
)
DIRECTION_SW: tuple[str, ...] = (
    "nunua", "uza", "kununua", "kuuza", "kupanda", "kushuka", "panda", "shuka", "inapanda",
    "inashuka", "kurudi", "kuendelea", "imara", "dhaifu", "kuingia", "kutoka", "juu", "chini",
    "kuimarika", "kudhoofika",
)
HORIZON_SW: tuple[str, ...] = (
    "dakika", "saa", "siku", "kila siku", "wiki", "kila wiki", "mwezi", "kila mwezi", "usiku",
    "kufunga", "kufungua", "kikao", "asubuhi", "mchana", "muda mfupi", "muda mrefu", "robo",
)

#: Per-language (quantity, direction, horizon) seeds; English is always searched as well.
_VOCAB: dict[str, tuple[tuple[str, ...], tuple[str, ...], tuple[str, ...]]] = {
    "zh": (QUANTITY_ZH, DIRECTION_ZH, HORIZON_ZH),
    "zh-Hant": (QUANTITY_ZHT + QUANTITY_ZH, DIRECTION_ZHT + DIRECTION_ZH,
                HORIZON_ZHT + HORIZON_ZH),
    "ja": (QUANTITY_JA + QUANTITY_ZH, DIRECTION_JA + DIRECTION_ZH, HORIZON_JA + HORIZON_ZH),
    "ko": (QUANTITY_KO, DIRECTION_KO, HORIZON_KO),
    "ru": (QUANTITY_RU, DIRECTION_RU, HORIZON_RU),
    "uk": (QUANTITY_UK + QUANTITY_RU, DIRECTION_UK + DIRECTION_RU, HORIZON_UK + HORIZON_RU),
    "vi": (QUANTITY_VI, DIRECTION_VI, HORIZON_VI),
    "th": (QUANTITY_TH, DIRECTION_TH, HORIZON_TH),
    "id": (QUANTITY_ID, DIRECTION_ID, HORIZON_ID),
    "hi": (QUANTITY_HI, DIRECTION_HI, HORIZON_HI),
    "de": (QUANTITY_DE, DIRECTION_DE, HORIZON_DE),
    "fr": (QUANTITY_FR, DIRECTION_FR, HORIZON_FR),
    "it": (QUANTITY_IT, DIRECTION_IT, HORIZON_IT),
    "es": (QUANTITY_ES, DIRECTION_ES, HORIZON_ES),
    "pt": (QUANTITY_PT, DIRECTION_PT, HORIZON_PT),
    "ar": (QUANTITY_AR, DIRECTION_AR, HORIZON_AR),
    "tr": (QUANTITY_TR, DIRECTION_TR, HORIZON_TR),
    "he": (QUANTITY_HE, DIRECTION_HE, HORIZON_HE),
    "pl": (QUANTITY_PL, DIRECTION_PL, HORIZON_PL),
    "nl": (QUANTITY_NL, DIRECTION_NL, HORIZON_NL),
    "sv": (QUANTITY_SV, DIRECTION_SV, HORIZON_SV),
    "da": (QUANTITY_DA, DIRECTION_DA, HORIZON_DA),
    "no": (QUANTITY_NO, DIRECTION_NO, HORIZON_NO),
    "fi": (QUANTITY_FI, DIRECTION_FI, HORIZON_FI),
    "sw": (QUANTITY_SW, DIRECTION_SW, HORIZON_SW),
    "en": (QUANTITY_EN, DIRECTION_EN, HORIZON_EN),
}
LANGUAGES: tuple[str, ...] = tuple(_VOCAB)

#: How a language's vocabulary is matched. "sub": plain substring (scripts without spaces);
#: "stem": the word must START at a word boundary and may continue (inflecting languages).
_SUBSTRING_LANGS: frozenset[str] = frozenset({"zh", "zh-Hant", "ja", "ko", "th"})

# ============================================================================== detection
_CJK = re.compile(r"[一-鿿]")
_KANA = re.compile(r"[぀-ヿ]")
_HANGUL = re.compile(r"[가-힯]")
_CYRILLIC = re.compile(r"[Ѐ-ӿ]")
_UKR_ONLY = re.compile(r"[іїєґІЇЄҐ]")
_THAI = re.compile(r"[฀-๿]")
_DEVANAGARI = re.compile(r"[ऀ-ॿ]")
_HEBREW = re.compile(r"[֐-׿]")
_ARABIC = re.compile(r"[؀-ۿ]")
#: Vietnamese-only letters: the horn/breve vowels and every dotted-below tone vowel. Portuguese
#: and French share the circumflex and tilde, so those are deliberately NOT in this class.
_VIET = re.compile(r"[ăđơưĂĐƠƯạảấầẩẫậắằẳẵặẹẻẽếềểễệỉịọỏốồổỗộớờởỡợụủứừửữựỳỵỷỹ]")

# Traditional-vs-simplified: characters that exist in only ONE script, paired so a reader can
# check them. The count decides, so a Hong Kong post quoting one simplified word stays zh-Hant.
_TRAD_SIMP_PAIRS = (
    "漲涨", "報报", "週周", "價价", "買买", "賣卖", "點点", "幣币", "匯汇", "證证", "現现", "貨货",
    "選选", "權权", "開开", "關关", "時时", "間间", "動动", "轉转", "趨趋", "勢势", "頭头", "態态",
    "線线", "續续", "隨随", "場场", "盤盘", "億亿", "萬万", "數数", "據据", "個个", "們们", "這这",
    "說说", "會会", "來来", "對对", "後后", "過过", "還还", "從从", "電电", "機机", "議议", "業业",
    "產产", "運运", "經经", "濟济", "資资", "訊讯", "網网", "際际", "國国", "學学", "讀读", "寫写",
    "聽听", "問问", "題题", "幾几", "發发", "變变", "麼么", "樣样", "強强", "預预", "測测", "隻只",
    "兩两", "極极", "舉举", "黃黄", "銀银", "銅铜", "歐欧", "鎊镑", "圓圆", "恆恒", "達达", "標标",
    "瓊琼", "壓压", "撐撑", "檔档", "彈弹", "單单", "進进", "當当", "沖冲", "結结", "擇择", "籌筹",
    "碼码", "勝胜", "離离", "內内", "戶户", "賺赚", "虧亏", "損损", "險险", "風风", "獲获", "調调",
    "節节", "與与", "於于", "為为", "無无", "沒没", "長长", "較较", "給给", "讓让", "見见", "觀观",
    "顯显", "響响", "觸触", "擊击", "縮缩", "擴扩",
)
_TRAD_CHARS = frozenset(p[0] for p in _TRAD_SIMP_PAIRS)
_SIMP_CHARS = frozenset(p[1] for p in _TRAD_SIMP_PAIRS)

#: Function words that separate the Latin-script languages. Word-bounded on lowercased text;
#: the language with the most hits wins when it beats English and has at least two. Words that
#: three languages share ("de", "en", "a") are left out on purpose -- they separate nothing.
_STOPWORDS: dict[str, tuple[str, ...]] = {
    "de": ("und", "der", "die", "das", "nicht", "ist", "wird", "wenn", "nach", "bei", "mit",
           "auf", "eine", "einer", "dem", "den", "sich", "auch", "oder", "aber", "über", "für",
           "meist", "oft", "dann", "steigt", "fällt"),
    "fr": ("le", "la", "les", "des", "est", "une", "dans", "après", "pour", "sur", "avec", "pas",
           "sont", "qui", "du", "au", "aux", "cette", "ce", "souvent", "généralement", "quand"),
    "it": ("il", "lo", "della", "del", "che", "non", "gli", "sono", "dopo", "una", "per", "nel",
           "nella", "degli", "delle", "alla", "questo", "spesso", "solitamente", "quando"),
    "es": ("el", "los", "las", "es", "una", "después", "para", "con", "que", "del", "se", "por",
           "al", "cuando", "suele", "también", "suelen", "hacia", "desde"),
    "pt": ("os", "não", "uma", "após", "para", "com", "que", "do", "da", "dos", "das", "na",
           "quando", "costuma", "também", "é", "são", "no", "mais", "pelo", "pela"),
    "id": ("yang", "dan", "dengan", "untuk", "akan", "tidak", "ini", "itu", "dari", "pada", "ke",
           "di", "adalah", "saat", "setelah", "biasanya", "harga", "cenderung", "sering"),
    "tr": ("ve", "bir", "için", "ile", "bu", "sonra", "genellikle", "olarak", "kadar", "ise",
           "gibi", "daha", "çok", "ama", "değil", "zaman", "sonrasında"),
    "pl": ("nie", "się", "jest", "na", "w", "z", "do", "że", "po", "przy", "oraz", "zwykle",
           "często", "ale", "lub", "od", "gdy", "kiedy"),
    "nl": ("het", "een", "niet", "wordt", "zijn", "ook", "als", "vaak", "meestal", "naar", "dan",
           "bij", "van", "voor", "na", "op", "dat", "wanneer"),
    "sv": ("och", "att", "är", "inte", "som", "för", "på", "med", "det", "ett", "efter", "när",
           "brukar", "ofta", "av", "till", "från", "sedan"),
    "da": ("og", "at", "er", "ikke", "som", "for", "på", "med", "det", "et", "efter", "når",
           "plejer", "ofte", "af", "til", "fra", "hvad", "meget", "kun"),
    "no": ("og", "at", "er", "ikke", "som", "for", "på", "med", "det", "et", "etter", "når",
           "pleier", "ofte", "av", "til", "fra", "hva", "mye", "bare"),
    "fi": ("ja", "on", "ei", "että", "kun", "jälkeen", "yleensä", "usein", "mutta", "myös", "tai",
           "kanssa", "ovat", "tämä", "jos", "niin", "sitten"),
    "sw": ("na", "ya", "wa", "kwa", "ni", "za", "la", "katika", "baada", "kawaida", "bei", "soko",
           "hisa", "huwa", "mara", "nyingi", "ambayo", "wakati"),
    "en": ("the", "and", "is", "of", "to", "in", "when", "after", "usually", "tends", "with",
           "that", "this", "for", "on", "are", "it", "be", "than", "into"),
}
#: Letters that belong to one Latin-script language alone; each counts as two function words.
_LETTER_HINTS: tuple[tuple[str, str], ...] = (
    ("ß", "de"), ("ł", "pl"), ("ż", "pl"), ("ę", "pl"), ("ą", "pl"), ("ś", "pl"), ("ź", "pl"),
    ("ã", "pt"), ("õ", "pt"), ("ñ", "es"), ("¿", "es"), ("ı", "tr"), ("ğ", "tr"), ("ş", "tr"),
)
_STOP_RE: dict[str, re.Pattern[str]] = {
    lang: re.compile(r"(?<!\w)(?:" + "|".join(re.escape(w) for w in words) + r")(?!\w)")
    for lang, words in _STOPWORDS.items()
}


def language_of(text: str) -> str:
    """Language code by script, then by function words for the Latin-script languages.

    Script decides where it can (kana -> ja, hangul -> ko, Thai, Devanagari, Hebrew, Arabic;
    Cyrillic -> uk when a Ukrainian-only letter is present, else ru; CJK -> zh-Hant when
    traditional-only characters outnumber simplified-only ones). The Latin languages are scored
    on function words and one-language letters; English is the fallback, never a winner by
    default, so a Spanish sentence with two Spanish function words is Spanish.
    """
    t = text or ""
    if _KANA.search(t):
        return "ja"
    if _HANGUL.search(t):
        return "ko"
    if _CJK.search(t):
        trad = sum(1 for ch in t if ch in _TRAD_CHARS)
        simp = sum(1 for ch in t if ch in _SIMP_CHARS)
        return "zh-Hant" if trad > simp else "zh"
    if _THAI.search(t):
        return "th"
    if _DEVANAGARI.search(t):
        return "hi"
    if _HEBREW.search(t):
        return "he"
    if _ARABIC.search(t):
        return "ar"
    if _CYRILLIC.search(t):
        return "uk" if _UKR_ONLY.search(t) else "ru"
    if len(_VIET.findall(t)) >= 2:
        return "vi"
    low = t.lower()
    score: dict[str, int] = {lang: len(rx.findall(low)) for lang, rx in _STOP_RE.items()}
    for ch, lang in _LETTER_HINTS:
        if ch in low:
            score[lang] = score.get(lang, 0) + 2
    en = score.pop("en", 0)
    best = max(score, key=lambda k: score[k]) if score else "en"
    return best if score.get(best, 0) >= 2 and score[best] > en else "en"


def is_cjk(text: str) -> bool:
    return bool(_CJK.search(text or ""))


# ============================================================================== the fence
#: Crypto-exchange-native ground is never hunted (principal, 2026-08-18). Any claim naming one of
#: these is dropped and COUNTED; the count is on the report so the fence is visible, not silent.
#: Widened 2026-09-05 with every region's exchanges and the funding/perpetual vocabulary in each
#: script, because a world forest has a crypto-exchange corner in every language.
FORBIDDEN_VENUES: tuple[str, ...] = (
    "binance", "bybit", "okx", "okex", "huobi", "htx", "hyperliquid", "bitget", "gate.io",
    "kucoin", "deribit", "coinbase", "kraken", "币安", "欧易", "火币", "抹茶", "资金费率",
    "funding rate", "永续合约", "perpetual", "perp ", "合约爆仓", "现货杠杆", "u本位", "币本位",
    # regional exchanges and forums
    "upbit", "bithumb", "coinone", "업비트", "빗썸", "코인원", "코인판", "coinpan", "bitflyer",
    "coincheck", "ビットフライヤー", "コインチェック", "gmoコイン", "wazirx", "coindcx",
    "coinswitch", "zebpay", "indodax", "tokocrypto", "bitkub", "luno", "bitso", "mercado bitcoin",
    "mexc", "bitmex", "bitfinex", "bitstamp", "dydx", "phemex", "crypto.com", "paribu", "btcturk",
    "exmo", "garantex", "whitebit", "zonda", "bitpanda",
    # funding / perpetual vocabulary in the other scripts
    "永續合約", "資金費率", "無期限先物", "資金調達率", "무기한 선물", "펀딩비", "펀딩 수수료",
    "фандинг", "бессрочн", "hợp đồng vĩnh cửu", "phí funding", "ฟันดิ้ง", "สัญญาถาวร",
    "funding-rate", "taxa de funding", "tasa de funding", "funding fee",
)


def forbidden_venue(text: str) -> str | None:
    """The first crypto-exchange token the text names, or None."""
    low = (text or "").lower()
    for v in FORBIDDEN_VENUES:
        if v in low:
            return v
    return None


# ============================================================================== instruments
#: Aliases -> Fusion symbols, most likely broker name FIRST. Every first candidate is a symbol in
#: desks/mt5/data/universe/universe.json (a test pins this); later candidates are other brokers'
#: names for the same contract, kept so the resolver still lands when the universe is unknown.
#: An empty tuple means "no MT5 analogue -- mechanism-class transfer only", and the third field
#: says which class the mechanism transfers to.
INSTRUMENT_ALIASES: tuple[tuple[tuple[str, ...], tuple[str, ...], str], ...] = (
    # ---- metals
    (("黄金", "沪金", "au9999", "au(t+d)", "伦敦金", "金价", "gold", "xauusd", "comex黄金", "黃金",
      "ゴールド", "金相場", "골드", "금값", "золот", "vàng", "ทองคำ", "ทอง", "emas", "सोना",
      "गोल्ड", "ذهب", "الذهب", "altın", "ons altın", "זהב", "złoto", "goud", "guld", "gull",
      "kulta", "dhahabu", "oro", "ouro", "l'or", "once d'or", "xau", "gc="), ("XAUUSD",), "metals"),
    (("白银", "沪银", "伦敦银", "银价", "silver", "xagusd", "白銀", "シルバー", "은값", "серебр",
      "bạc", "โลหะเงิน", "perak", "चांदी", "فضة", "الفضة", "gümüş", "srebro", "zilver", "silber",
      "sølv", "hopea", "plata", "prata", "argento", "xag"), ("XAGUSD",), "metals"),
    (("铂金", "platinum", "xptusd", "白金", "プラチナ", "백금", "платин", "platino", "platina",
      "platin"), ("XPTUSD",), "metals"),
    (("钯金", "palladium", "xpdusd", "パラジウム", "팔라듐", "паллад", "paladio", "paládio"),
     ("XPDUSD",), "metals"),
    (("铜", "沪铜", "伦铜", "copper", "xcuusd", "銅", "구리", "медь", "ทองแดง", "tembaga",
      "तांबा", "نحاس", "bakır", "miedź", "koper", "kupfer", "cuivre", "cobre", "rame", "koppar",
      "kobber", "kupari", "shaba"), ("XCUUSD", "COPPER", "HG"), "metals"),
    (("沪铝", "铝", "aluminium", "aluminum", "xalusd", "アルミ", "алюмин", "aluminio", "alumínio"),
     ("XALUSD",), "metals"),
    (("沪镍", "镍", "nickel", "xniusd", "ニッケル", "никел", "níquel"), ("XNIUSD",), "metals"),
    (("沪锌", "锌", "zinc", "xznusd", "亜鉛", "цинк"), ("XZNUSD",), "metals"),
    (("沪铅", "铅", "lead futures", "xpbusd", "свинец", "plomo", "chumbo"), ("XPBUSD",), "metals"),
    # ---- energy
    (("原油", "布油", "美原油", "sc原油", "wti", "brent", "crude", "石油", "原油価格", "유가",
      "нефт",
      "dầu thô", "น้ำมันดิบ", "minyak mentah", "कच्चा तेल", "نفط", "خام برنت", "petrol", "ropa",
      "olie", "rohöl", "pétrole", "petróleo", "petrolio", "olja", "olje", "öljy", "mafuta",
      "brent crude", "ホルムズ", "opec", "أوبك"),
     ("XTIUSD", "XBRUSD", "USOIL", "UKOIL"), "energy"),
    (("天然气", "natural gas", "natgas", "xngusd", "天然ガス", "천연가스", "газ", "khí đốt",
      "gas alam", "erdgas", "gaz naturel", "gás natural", "gas natural", "henry hub", "ttf"),
     ("XNGUSD", "NATGAS"), "energy"),
    # ---- indices with a Fusion symbol
    (("恒指", "恒生", "港股", "hsi", "恆指", "恆生", "hang seng", "hangseng", "hk50", "ハンセン",
      "항셍"), ("HK50", "HSI"), "indices"),
    (("国企指数", "國企指數", "h股", "hscei", "chinah", "china h-shares"), ("CHINAH",), "indices"),
    (("纳指", "纳斯达克", "nasdaq", "nas100", "ustec", "那斯達克", "納斯達克", "ナスダック",
      "나스닥",
      "насдак", "ndx"), ("NAS100", "USTEC"), "indices"),
    (("标普", "s&p", "spx", "us500", "美股", "標普", "sp500", "s&p 500", "s&p500", "美国股市",
      "spy"), ("US500", "SPX500"), "indices"),
    (("道指", "dow", "us30", "道瓊", "ダウ", "다우", "dow jones", "djia"), ("US30", "DJ30"),
     "indices"),
    (("罗素", "russell 2000", "russell", "us2000", "rty"), ("US2000",), "indices"),
    (("德指", "dax", "ger40", "de40", "德國dax", "дакс"), ("GER40", "DE40"), "indices"),
    (("日经", "nikkei", "jp225", "日股", "日経", "日経225", "日経平均", "닛케이", "日經", "jpn225",
      "никкей", "nikkei 225"), ("JPN225", "JP225"), "indices"),
    (("富时", "ftse", "uk100", "富時", "footsie", "ftse 100"), ("UK100",), "indices"),
    (("cac", "cac 40", "cac40", "fra40", "法国股指"), ("FRA40",), "indices"),
    (("euro stoxx", "eurostoxx", "sx5e", "eustx50", "stoxx 50", "斯托克"), ("EUSTX50",),
     "indices"),
    (("aex", "neth25", "amsterdam index"), ("NETH25",), "indices"),
    (("ibex", "ibex 35", "ibex35", "e35"), ("E35",), "indices"),
    (("tsx", "s&p/tsx", "ca60", "toronto index"), ("CA60",), "indices"),
    (("asx 200", "asx200", "aus200", "xjo", "spi futures", "s&p/asx"), ("AUS200",), "indices"),
    (("美元指数", "dxy", "dollar index", "usdx", "ドルインデックス", "달러인덱스", "индекс доллара",
      "美元指數"), ("USDX", "DXY", "USDOLLAR"), "fx"),
    # ---- indices WITHOUT a Fusion symbol: the mechanism transfers to the index class
    (("沪深300", "if合约", "股指期货", "a股", "上证", "中证500", "ic合约", "ih合约", "im合约",
      "a50", "富时中国", "china a50", "csi 300", "上證", "滬深"), (), "indices (China A-share)"),
    (("코스피", "kospi", "코스닥", "kosdaq", "코스피200"), (), "indices (KRX)"),
    (("topix", "東証", "マザーズ", "グロース250"), (), "indices (TSE)"),
    (("台指", "加權指數", "台股", "taiex", "twse", "台指期", "小台"), (), "indices (TWSE)"),
    (("nifty", "bank nifty", "sensex", "निफ्टी", "बैंक निफ्टी", "सेंसेक्स", "finnifty"), (),
     "indices (NSE/BSE)"),
    (("straits times", "sti index", "海峽時報", "msci singapore"), (), "indices (SGX)"),
    (("set50", "set index", "ตลาดหุ้นไทย", "ดัชนี set"), (), "indices (SET)"),
    (("ihsg", "idx composite", "lq45", "jakarta composite"), (), "indices (IDX)"),
    (("klci", "fbm klci", "bursa malaysia", "fkli"), (), "indices (Bursa)"),
    (("psei", "pse index", "philippine stock"), (), "indices (PSE)"),
    (("vn-index", "vnindex", "vn30", "hnx"), (), "indices (HOSE)"),
    (("tadawul", "tasi", "تاسي", "adx index", "dfm index", "qe index"), (),
     "indices (Gulf exchanges)"),
    (("jse", "top40", "alsi", "jse all share"), (), "indices (JSE)"),
    (("ibovespa", "bovespa", "ibov", "índice bovespa", "b3 index"), (), "indices (B3)"),
    (("merval", "s&p merval", "ipc mexico", "bmv ipc", "ipsa", "colcap", "s&p/bvl"), (),
     "indices (LatAm exchanges)"),
    (("wig20", "wig 20", "mwig40", "swig80"), (), "indices (GPW)"),
    (("omxs30", "omxc25", "obx", "omxh25", "omx stockholm"), (), "indices (Nordic exchanges)"),
    (("bist 100", "bist100", "xu100", "borsa istanbul"), (), "indices (BIST)"),
    (("ta-35", "ta35", "ta-125", "tase"), (), "indices (TASE)"),
    (("moex index", "индекс мосбиржи", "ртс", "rts index", "imoex", "ммвб"), (), "indices (MOEX)"),
    (("psx", "kse-100", "kse 100", "dse index", "dsex", "cse all share", "aspi"), (),
     "indices (South Asian exchanges)"),
    (("ngx", "nse all share", "egx30", "egx 30", "nse 20", "masi"), (),
      "indices (African exchanges)"),
    # ---- FX majors
    (("欧元", "欧美", "eurusd", "eur/usd", "ユーロドル", "유로달러", "евродоллар", "euro-dollar",
      "歐元", "euro dollar", "eurodólar", "eurodollaro"), ("EURUSD",), "fx"),
    (("英镑", "镑美", "gbpusd", "gbp/usd", "ポンドドル", "파운드", "фунт", "英鎊", "cable",
      "sterling", "pound"), ("GBPUSD",), "fx"),
    (("日元", "美日", "usdjpy", "usd/jpy", "ドル円", "달러엔", "доллар иена", "日圓", "엔화",
      "円相場", "yen"), ("USDJPY",), "fx"),
    (("澳元", "澳美", "audusd", "aud/usd", "豪ドル", "호주달러", "澳幣", "aussie"), ("AUDUSD",),
     "fx"),
    (("加元", "美加", "usdcad", "usd/cad", "カナダドル", "loonie", "加拿大元"), ("USDCAD",), "fx"),
    (("瑞郎", "美瑞", "usdchf", "usd/chf", "スイスフラン", "swissie", "瑞士法郎"), ("USDCHF",),
      "fx"),
    (("纽元", "nzdusd", "nzd/usd", "kiwi", "紐元", "ニュージーランドドル"), ("NZDUSD",), "fx"),
    (("ユーロ円", "eurjpy", "eur/jpy"), ("EURJPY",), "fx"),
    (("ポンド円", "gbpjpy", "gbp/jpy"), ("GBPJPY",), "fx"),
    (("豪ドル円", "audjpy", "aud/jpy"), ("AUDJPY",), "fx"),
    (("eurgbp", "eur/gbp", "ユーロポンド"), ("EURGBP",), "fx"),
    # ---- FX exotics Fusion quotes: each region's own currency
    (("人民币", "离岸人民币", "usdcnh", "cnh", "人民幣", "usd/cnh", "usd/cny", "人民元"),
     ("USDCNH",), "fx"),
    (("港币", "港幣", "usdhkd", "usd/hkd", "港元", "hkd peg", "聯繫匯率", "联系汇率", "hkma"),
     ("USDHKD",), "fx"),
    (("원달러", "달러원", "usdkrw", "usd/krw", "원화", "won", "韓元", "韩元"), ("USDKRW",), "fx"),
    (("rupee", "usdinr", "usd/inr", "रुपया", "रुपये", "inr"), ("USDINR",), "fx"),
    (("บาท", "usdthb", "usd/thb", "baht", "thai baht"), ("USDTHB",), "fx"),
    (("rupiah", "usdidr", "usd/idr", "idr"), ("USDIDR",), "fx"),
    (("usdsgd", "usd/sgd", "sing dollar", "singapore dollar", "新元", "sgd"), ("USDSGD",), "fx"),
    (("usdbrl", "usd/brl", "dólar/real", "dolar/real", "real brasileiro", "brl"), ("USDBRL",),
     "fx"),
    (("usdmxn", "usd/mxn", "peso mexicano", "mxn", "superpeso"), ("USDMXN",), "fx"),
    (("usdtry", "usd/try", "dolar/tl", "dolar tl", "dolar kuru", "lira", "türk lirası", "try"),
     ("USDTRY",), "fx"),
    (("usdzar", "usd/zar", "rand", "zar"), ("USDZAR",), "fx"),
    (("usdils", "usd/ils", "shekel", "שקל", "דולר שקל", "ils"), ("USDILS",), "fx"),
    (("usdpln", "usd/pln", "złoty", "zloty", "pln", "eurpln", "eur/pln"), ("USDPLN",), "fx"),
    (("usdhuf", "usd/huf", "forint", "huf", "eurhuf", "eur/huf"), ("USDHUF",), "fx"),
    (("usdczk", "usd/czk", "koruna", "czk", "eurczk", "eur/czk"), ("USDCZK",), "fx"),
    (("usdsek", "usd/sek", "svenska kronan", "kronan", "sek", "eursek", "eur/sek"), ("USDSEK",),
     "fx"),
    (("usdnok", "usd/nok", "norske kronen", "nok", "eurnok", "eur/nok"), ("USDNOK",), "fx"),
    (("usddkk", "usd/dkk", "danske kronen", "dkk", "eurdkk", "eur/dkk"), ("USDDKK",), "fx"),
    (("usdrub", "usd/rub", "рубл", "курс доллара", "rub", "eurrub"), ("USDRUB",), "fx"),
    # currencies with no Fusion pair: the mechanism transfers to the FX class
    (("đồng việt nam", "tỷ giá usd/vnd", "usd/vnd", "vnd"), (), "fx (VND not quoted)"),
    (("ringgit", "usd/myr", "myr"), (), "fx (MYR not quoted)"),
    (("philippine peso", "usd/php", "php"), (), "fx (PHP not quoted)"),
    (("naira", "usd/ngn", "ngn"), (), "fx (NGN not quoted)"),
    (("egyptian pound", "usd/egp", "egp", "الجنيه"), (), "fx (EGP not quoted)"),
    (("kenyan shilling", "usd/kes", "shilingi", "kes"), (), "fx (KES not quoted)"),
    (("dirham", "usd/aed", "riyal", "usd/sar", "الريال", "الدرهم"), (), "fx (Gulf pegs)"),
    (("peso argentino", "usd/ars", "dólar blue", "dolar blue", "ars", "peso chileno", "usd/clp",
      "peso colombiano", "usd/cop", "sol peruano", "usd/pen"), (), "fx (LatAm not quoted)"),
    (("hryvnia", "гривн", "usd/uah", "uah"), (), "fx (UAH not quoted)"),
    (("pakistani rupee", "usd/pkr", "pkr", "taka", "usd/bdt", "usd/lkr"), (),
     "fx (South Asian not quoted)"),
    # ---- crypto CFDs Fusion quotes (the asset, never the exchange)
    (("比特币", "bitcoin", "btcusd", "ビットコイン", "비트코인", "биткоин"), ("BTCUSD",),
      "crypto_cfd"),
    (("以太坊", "ethereum", "ethusd", "イーサリアム", "이더리움", "эфир"), ("ETHUSD",),
      "crypto_cfd"),
    # ---- softs and grains
    (("大豆", "soybean", "soybeans", "soja", "soya", "đậu tương", "大豆先物"),
     ("SOYBEAN", "SOYBEANS", "ZS"), "softs"),
    (("玉米", "corn", "maize", "milho", "maíz", "トウモロコシ", "кукуруз"), ("CORN", "ZC"),
      "softs"),
    (("白糖", "sugar", "açúcar", "azúcar", "砂糖", "сахар", "gula"), ("SUGAR", "SUGARRAW", "SB"),
     "softs"),
    (("棉花", "cotton", "algodão", "algodón", "綿花", "хлопок"), ("COTTON", "CT"), "softs"),
    (("咖啡", "coffee", "arabica", "café", "kahve", "コーヒー", "кофе", "cà phê"),
     ("COFARA", "COFROB", "COFFEE", "KC"), "softs"),
    (("robusta", "robusta coffee"), ("COFROB", "COFARA"), "softs"),
    (("小麦", "wheat", "trigo", "blé", "小麦先物", "пшениц", "weizen"), ("WHEAT", "ZW"), "softs"),
    (("可可", "cocoa", "cacao", "kakao", "ココア", "какао", "cocoa board", "ghana cocoa",
      "ivory coast cocoa"), ("USCOCOA", "UKCOCOA", "COCOA"), "softs"),
    (("orange juice", "fcoj", "suco de laranja"), ("OJ",), "softs"),
    # ---- rates the desk can quote
    (("美国国债", "美债", "treasuries", "10-year treasury", "10y treasury", "ust10y", "10年債",
      "米国債", "10-year yield", "10y yield", "tnote", "t-note"), ("UST10Y", "UST05Y"),
     "rates"),
    (("gilt", "gilts", "ukgilt", "英国国债"), ("UKGILT",), "rates"),
    # ---- share CFDs Fusion quotes, where a region's own press names them
    (("台積電", "台积电", "tsmc", "taiwan semiconductor", "2330"), ("TSMC",), "equities"),
    (("トヨタ", "toyota", "7203"), ("Toyota",), "equities"),
    (("阿里巴巴", "alibaba", "baba", "9988"), ("AlibabaGroup",), "equities"),
    (("百度", "baidu"), ("Baidu",), "equities"),
    (("蔚来", "蔚來", "nio inc"), ("NIO",), "equities"),
    (("特斯拉", "テスラ", "테슬라", "tesla", "tsla"), ("Tesla",), "equities"),
    (("英伟达", "輝達", "エヌビディア", "엔비디아", "nvidia", "nvda"), ("NVIDIA",), "equities"),
    # ---- NO MT5 ANALOGUE: the mechanism transfers to the class, the instrument does not.
    (("螺纹钢", "螺纹", "热卷", "铁矿石", "铁矿", "焦炭", "焦煤", "动力煤", "iron ore", "鉄鉱石"),
     (), "metals/energy"),
    (("甲醇", "pta", "乙二醇", "纯碱", "玻璃", "尿素", "沥青", "橡胶", "pvc", "pp", "塑料"),
     (), "energy"),
    (("豆粕", "菜油", "菜粕", "棕榈油", "豆油", "鸡蛋", "生猪", "苹果", "红枣", "花生", "palm oil",
      "cpo", "minyak sawit"), (), "softs"),
    (("碳酸锂", "工业硅", "氧化铝", "沪锡", "lithium", "tin futures"), (), "metals"),
    (("国债期货", "十债", "五债", "二债", "bund futures", "jgb", "btp futures", "oat futures",
      "ofz", "офз", "selic futures", "di futures", "cetes", "kkm"), (), "rates->fx carry"),
    (("可转债", "转债", "打新", "涨停", "跌停", "龙虎榜", "北向资金"), (), "cn-equities-only"),
    (("baltic dry", "bdi", "freight index", "運賃指数", "drewry", "world container index",
      "scfi", "fbx"), (), "shipping/freight -> commodity currencies"),
)

#: INDIRECT CHANNELS: a foreign dataset, event or institution that moves an MT5 instrument
#: through an information shock rather than by naming it. The claim is recorded with
#: `channel="indirect"` and the instrument the shock lands on, so the funnel can measure whether
#: indirect channels convert (principal 2026-09-05: "indirect edges are the point").
INDIRECT_CHANNELS: tuple[tuple[tuple[str, ...], tuple[str, ...], str], ...] = (
    # central banks -> the pair they set
    (("fomc", "federal reserve", "the fed", "美联储", "fed funds", "连准会", "聯準會", "фрс",
      "パウエル"), ("USDX", "US500"), "policy: Fed -> dollar and US equities"),
    (("ecb", "european central bank", "欧洲央行", "歐洲央行", "bce", "ezb", "ецб", "lagarde"),
     ("EURUSD",), "policy: ECB -> EUR"),
    (("bank of england", "boe", "英国央行", "英國央行", "mpc minutes"), ("GBPUSD",),
      "policy: BoE -> GBP"),
    (("bank of japan", "boj", "日銀", "日本央行", "日本銀行", "為替介入", "介入警戒", "神田財務官",
      "yen intervention", "円買い介入"), ("USDJPY",), "policy: BoJ / MoF intervention -> JPY"),
    (("rba", "reserve bank of australia", "澳洲联储", "澳洲央行"), ("AUDUSD",),
      "policy: RBA -> AUD"),
    (("rbnz", "reserve bank of new zealand"), ("NZDUSD",), "policy: RBNZ -> NZD"),
    (("bank of canada", "boc", "加拿大央行", "macklem"), ("USDCAD",), "policy: BoC -> CAD"),
    (("snb", "swiss national bank", "瑞士央行", "nationalbank"), ("USDCHF",), "policy: SNB -> CHF"),
    (("pboc", "people's bank of china", "人民银行", "中国人民银行", "中间价", "中間價",
      "逆周期因子",
      "cfets"), ("USDCNH",), "policy: PBoC fixing -> CNH"),
    (("hong kong monetary authority", "金管局", "弱方兌換保證", "强方兑换保证"), ("USDHKD",),
     "policy: HKMA peg defence -> HKD"),
    (("bank of korea", "bok", "한국은행", "한은", "외환당국", "구두개입", "smoothing operation"),
     ("USDKRW",), "policy: BoK / MoEF -> KRW"),
    (("reserve bank of india", "rbi", "आरबीआई", "रिज़र्व बैंक", "भारतीय रिज़र्व"), ("USDINR",),
     "policy: RBI -> INR"),
    (("bank of thailand", "bot ", "แบงก์ชาติ", "ธปท", "กนง"), ("USDTHB",), "policy: BoT -> THB"),
    (("bank indonesia", "bi rate", "bi-rate", "bi 7-day", "sri mulyani"), ("USDIDR",),
     "policy: BI -> IDR"),
    (("monetary authority of singapore", "mas ", "s$neer", "sgd neer"), ("USDSGD",),
     "policy: MAS band -> SGD"),
    (("banco central do brasil", "bacen", "copom", "selic", "galípolo", "swap cambial",
      "leilão de swap", "cupom cambial", "conab", "safra de soja", "exportações de soja",
      "soy exports", "brazil soy", "iron ore exports", "minério de ferro"), ("USDBRL",),
     "flow/policy: Brazil (BCB, soy, iron ore) -> BRL"),
    (("banxico", "banco de méxico", "banco de mexico", "remesas", "remittances", "nearshoring"),
     ("USDMXN",), "policy/flow: Banxico, remittances -> MXN"),
    (("cbrt", "tcmb", "merkez bankası", "merkez bankasi", "türkiye cumhuriyet merkez", "kkm",
      "karahan", "şimşek", "simsek"), ("USDTRY",), "policy: CBRT -> TRY"),
    (("sarb", "south african reserve bank", "reserve bank of south africa", "eskom",
      "load shedding", "platinum exports", "rand exports"), ("USDZAR",),
     "policy/flow: SARB, mining exports, power -> ZAR"),
    (("bank of israel", "boi ", "בנק ישראל"), ("USDILS",), "policy: BoI -> ILS"),
    (("nbp", "narodowy bank polski", "rpp", "rada polityki pieniężnej", "glapiński"), ("USDPLN",),
     "policy: NBP -> PLN"),
    (("mnb", "magyar nemzeti bank", "hungarian central bank"), ("USDHUF",), "policy: MNB -> HUF"),
    (("cnb", "czech national bank", "česká národní banka"), ("USDCZK",), "policy: CNB -> CZK"),
    (("riksbank", "riksbanken"), ("USDSEK",), "policy: Riksbank -> SEK"),
    (("norges bank", "oljefondet", "government pension fund global", "nbim"), ("USDNOK",),
     "policy/flow: Norges Bank and the oil fund -> NOK"),
    (("danmarks nationalbank", "nationalbanken"), ("USDDKK",), "policy: DN peg -> DKK"),
    (("bank of russia", "цб рф", "центробанк", "набиуллина", "ключевая ставка", "минфин",
      "бюджетное правило", "urals"), ("USDRUB",), "policy: CBR / MinFin -> RUB"),
    # commodity shocks -> commodity and the currency that exports it
    (("opec+", "opec", "أوبك", "saudi output", "saudi aramco", "eia inventories", "api inventories",
      "cushing", "strait of hormuz", "hormuz", "red sea", "houthi", "ホルムズ海峡"),
     ("XTIUSD", "XBRUSD", "USDCAD", "USDNOK"),
      "energy flow: OPEC / inventories / chokepoints -> oil, CAD, NOK"),
    (("shanghai gold premium", "sge premium", "上海金溢价", "上海黄金交易所", "上海金", "水贝",
      "india gold imports", "gold import duty", "central bank gold buying", "央行购金",
      "pboc gold"), ("XAUUSD",), "physical premia / official buying -> gold"),
    (("chilean copper", "codelco", "escondida", "ilo copper", "lme stocks", "lme inventories",
      "上期所库存"), ("XCUUSD", "AUDUSD"), "inventory: copper supply and stocks -> copper, AUD"),
    (("iron ore price", "pilbara", "port hedland", "铁矿石价格", "australian exports", "abares"),
     ("AUDUSD",), "flow: Australian bulk exports -> AUD"),
    (("dairy auction", "gdt auction", "fonterra", "global dairy trade"), ("NZDUSD",),
     "auction: dairy prices -> NZD"),
    (("wasde", "usda crop", "usda export sales", "crop progress", "la niña", "el niño", "el nino",
      "la nina", "monsoon"), ("SOYBEAN", "CORN", "WHEAT", "USDBRL"),
     "weather/agri report -> grains and BRL"),
    (("ghana cocoa board", "cocobod", "ivory coast harvest", "côte d'ivoire cocoa"),
     ("USCOCOA", "UKCOCOA"), "harvest: West African cocoa -> cocoa"),
    (("vietnam coffee exports", "vietnam robusta", "brazil coffee crop", "minas gerais frost"),
     ("COFROB", "COFARA"), "harvest: coffee origins -> coffee"),
    (("baltic dry", "freight rates", "container rates", "運賃", "运费", "shipping index",
      "drewry", "xeneta"), ("AUDUSD", "USDZAR", "USDBRL"),
      "shipping: freight indices -> commodity FX"),
    # positioning and flows
    (("cot report", "commitments of traders", "cftc positioning", "spec positioning", "tff report"),
     ("XAUUSD", "EURUSD", "USDJPY"), "positioning: CFTC -> FX and gold"),
    (("gold etf flows", "gld flows", "spdr gold holdings", "etf holdings", "金etf"),
     ("XAUUSD",), "fund flows: gold ETFs -> gold"),
    (("northbound flows", "southbound flows", "北向资金", "南下资金", "港股通", "陆股通", "北水"),
     ("HK50", "CHINAH", "USDCNH"), "flow: Stock Connect -> HK indices and CNH"),
    (("toshin", "投信", "nisa flows", "japanese investors", "lifers", "生保"), ("USDJPY",),
     "flow: Japanese outbound investment -> JPY"),
    (("fii flows", "fpi flows", "dii flows", "foreign portfolio"), ("USDINR",),
     "flow: India portfolio flows -> INR"),
    (("外資", "外资买卖超", "外資買賣超"), ("TSMC",), "flow: Taiwan foreign investors -> TSMC"),
    # sovereign auctions and fiscal
    (("treasury auction", "bond auction", "auction tail", "国债拍卖", "国債入札", "入札結果",
      "leilão do tesouro", "subasta del tesoro", "аукцион офз"), ("UST10Y", "USDX"),
     "auction: sovereign debt -> rates and dollar"),
    (("capital controls", "资本管制", "資本管制", "cepo cambiario", "capital flow measures",
      "外汇管制", "controle de capitais", "sermaye kontrolü"), ("USDCNH", "USDTRY", "USDINR"),
     "policy: capital controls -> the pair they fence"),
)


_LATIN = "a-z0-9À-ɏ"


def _alias_pattern(alias: str) -> str:
    """Substring for CJK/Thai/Arabic aliases; word-bounded for Latin ones, so `gold` does not
    match `golden` and `dow` does not match `download`."""
    starts = re.match(rf"[{_LATIN}]", alias) is not None
    ends = re.search(rf"[{_LATIN}]$", alias) is not None
    return ((rf"(?<![{_LATIN}])" if starts else "") + re.escape(alias)
            + (rf"(?![{_LATIN}])" if ends else ""))


_ALIAS_RE: dict[tuple[str, ...], re.Pattern[str]] = {}


def _alias_rx(aliases: tuple[str, ...]) -> re.Pattern[str]:
    """ONE compiled alternation per alias tuple, longest alias first. Compiling per alias per
    call thrashed `re`'s 512-entry cache once the table passed a thousand aliases and made a
    page take seconds instead of milliseconds -- measured on the whole-grounds offline test."""
    rx = _ALIAS_RE.get(aliases)
    if rx is None:
        alts = "|".join(_alias_pattern(a) for a in sorted(set(aliases), key=len, reverse=True)
                        if a)
        rx = _ALIAS_RE[aliases] = re.compile(alts or r"(?!x)x")
    return rx


def _alias_hit(alias: str, low: str) -> bool:
    return _alias_rx((alias,)).search(low) is not None


def _first_alias(aliases: tuple[str, ...], low: str) -> str | None:
    m = _alias_rx(aliases).search(low)
    return m.group(0) if m else None


def resolve_instruments(text: str, universe: set[str] | None = None) -> dict[str, Any]:
    """MT5 analogues for every instrument the text names, the transfer-only classes, and the
    indirect channels (dataset/event -> instrument) it triggers."""
    low = (text or "").lower()
    analogues: list[str] = []
    mentioned: list[str] = []
    transfer: list[str] = []
    indirect: list[str] = []
    channels: list[str] = []
    uni = {u.upper() for u in (universe or set())}

    def pick(cands: tuple[str, ...]) -> str | None:
        if not uni:
            return cands[0]
        return next((c for c in cands if c.upper() in uni), None)

    for aliases, cands, cls in INSTRUMENT_ALIASES:
        hit = _first_alias(aliases, low)
        if hit is None:
            continue
        mentioned.append(hit)
        if not cands:
            transfer.append(f"{hit}->{cls}")
            continue
        chosen = pick(cands)
        if chosen and chosen not in analogues:
            analogues.append(chosen)
        elif chosen is None:
            transfer.append(f"{hit}->{cls} (not quoted here)")
    for aliases, cands, note in INDIRECT_CHANNELS:
        hit = _first_alias(aliases, low)
        if hit is None:
            continue
        channels.append(f"{hit}: {note}")
        for c in cands:
            chosen = c if not uni else (c if c.upper() in uni else None)
            if chosen and chosen not in analogues and chosen not in indirect:
                indirect.append(chosen)
    return {"analogues": analogues, "mentioned": mentioned, "transfer_only": transfer,
            "indirect": indirect, "channels": channels}


# ============================================================================== mechanism class
#: The orthogonality vocabulary (principal 2026-09-05): every claim is tagged with ONE class so a
#: later scorer can prefer classes the portfolio lacks, and a ground that yields only momentum
#: says so on the report. First class whose term appears wins; the order is deliberate --
#: specific structural classes before the two generic price-pattern classes.
MECHANISM_CLASSES: tuple[str, ...] = (
    "policy", "calendar", "positioning", "inventory", "flow", "carry", "cross_asset",
    "microstructure", "reversion", "momentum",
)
_CLASS_TERMS: dict[str, tuple[str, ...]] = {
    "policy": ("central bank", "rate decision", "rate hike", "rate cut", "intervention", "fomc",
               "ecb", "boj", "rbi", "cbrt", "banxico", "copom", "selic", "policy rate",
               "capital control",
               "央行", "加息", "降息", "升息", "干预", "干預", "介入", "政策金利", "日銀",
               "기준금리",
               "한은", "개입", "ставк", "интервенц", "цб", "lãi suất", "ngân hàng nhà nước",
               "ดอกเบี้ย",
               "แทรกแซง", "suku bunga", "intervensi", "ब्याज दर", "आरबीआई", "zins", "leitzins",
               "taux directeur", "tasso", "tipos de interés", "tasa de interés", "juros", "faiz",
               "merkez", "ריבית", "stóp procentow", "rente", "ränta", "korko", "riba", "فائدة",
               "البنك المركزي", "auction", "入札", "leilão", "subasta", "аукцион", "інтервенц",
               "нбу", "rpp", "korkopäätö", "räntebesked", "rentebeslut", "rentemøde", "benki kuu",
               "kuingili", "決定利率", "利率決議"),
    "calendar": ("seasonal", "seasonality", "turn of month", "day of week", "expiry", "witching",
                 "fix", "fixing", "roll", "rollover", "季节", "季節", "月末", "换月", "換月",
                 "结算",
                 "結算", "交割", "到期", "ゴトー日", "五十日", "仲値", "sq", "満期", "만기",
                 "롤오버",
                 "계절", "сезонн", "экспирац", "фиксинг", "đáo hạn", "mùa vụ", "หมดอายุ", "ฤดูกาล",
                 "kedaluwarsa", "musiman", "एक्सपायरी", "मौसमी", "verfall", "hexensabbat", "saison",
                 "échéance", "saisonnal", "scadenza", "stagional", "vencimiento", "estacional",
                 "sazonal", "vade", "mevsimsel", "wygaśnięci", "sezonow", "expiratie", "seizoen",
                 "förfall", "säsong", "udløb", "sæson", "forfall", "sesong", "erääntymi", "kausi",
                 "msimu", "موسمي", "quarter-end", "year-end", "options expiry", "opex", "фіксинг",
                 "експірац"),
    "positioning": ("cot", "commitments of traders", "positioning", "open interest", "net long",
                    "net short", "speculators", "crowded", "short squeeze", "持仓量", "持仓",
                    "多空比",
                    "主力", "净持仓", "建玉", "미결제약정", "포지션", "수급", "외국인",
                    "открыт интерес",
                    "позици", "шорт-сквиз", "khối ngoại", "tự doanh", "ต่างชาติ", "asing", "fii",
                    "dii",
                    "ओपन इंटरेस्ट", "pcr", "positionierung", "positionnement", "posizionamento",
                    "posicionamiento", "posicionamento", "estrangeiro", "外資", "法人", "籌碼",
                    "pozycjonowan", "positionering", "positiointi", "gamma", "dealer"),
    "inventory": ("inventory", "inventories", "stocks", "stockpile", "warehouse", "eia",
    "api report",
                  "lme stocks", "harvest", "crop", "wasde", "库存", "庫存", "产量", "產量", "在庫",
                  "재고",
                  "запас", "урожа", "tồn kho", "สต็อก", "stok", "persediaan", "भंडार", "मानसून",
                  "lagerbestand", "lagerbestände", "ernte", "récolte", "scorte", "raccolto",
                  "inventario", "existencias", "cosecha", "estoque", "safra", "hasat", "mavuno",
                  "hifadhi", "zapas", "zbior", "voorraad", "oogst", "lager", "skörd", "høst",
                  "avling", "varasto", "sato", "مخزون", "weather", "天气", "天候", "cuaca",
                  "monsoon",
                  "el niño", "la niña", "frost", "drought"),
    "flow": ("flow", "flows", "etf", "fund flows", "exports", "imports", "shipping", "freight",
             "remittances", "northbound", "southbound", "资金流", "資金流", "北向", "南下",
             "港股通",
             "出口", "进口", "运费", "運費", "実需", "輸出", "投信", "환율", "수출", "운임",
             "экспорт",
             "фрахт", "dòng tiền", "xuất khẩu", "cước", "ฟันด์โฟลว์", "ส่งออก", "ค่าระวาง",
             "aliran dana", "ekspor", "निर्यात", "आयात", "fracht", "export", "fret", "flux",
             "exportations", "noli", "flusso", "flujo", "flete", "exportaciones", "fluxo", "frete",
             "exportação", "ihracat", "navlun", "eksport", "vracht", "frakt", "vienti", "rahti",
             "usafirishaji", "صادرات", "شحن", "baltic", "container", "cargo", "auction"),
    "carry": ("carry", "swap", "interest differential", "rate differential", "yield differential",
              "funding", "套息", "利差", "掉期", "隔夜利息", "スワップ", "キャリー", "金利差",
              "캐리",
              "스왑", "금리차", "кэрри", "своп", "chênh lệch lãi suất", "ส่วนต่างดอกเบี้ย",
              "selisih bunga",
              "zinsdifferenz", "différentiel", "differenziale", "diferencial", "cupom cambial",
              "taşıma", "swap", "ränte", "korkoero", "carry trade"),
    "cross_asset": ("correlation", "cointegration", "lead-lag", "lead lag", "spread between",
    "ratio",
                    "pairs", "relative value", "basis", "term structure", "curve", "相关", "相關",
                    "协整",
                    "領先", "领先", "滞后", "金银比", "金油比", "沪伦比", "内外盘", "跨市",
                    "跨品种",
                    "基差", "期限结构", "相関", "乖離", "裁定", "상관관계", "괴리율", "차익거래",
                    "корреляц", "арбитраж", "базис", "tương quan", "chênh lệch", "ความสัมพันธ์",
                    "korelasi", "सहसंबंध", "korrelation", "arbitrage", "corrélation",
                    "correlazione",
                    "correlación", "correlação", "korelasyon", "מתאם", "korelac", "correlatie",
                    "korrelasjon", "korrelaatio", "uhusiano", "ارتباط", "contango",
                    "backwardation"),
    "microstructure": ("order flow", "orderflow", "liquidity", "spread", "slippage", "imbalance",
                       "book", "tick", "vwap", "auction", "stop hunt", "sweep", "market maker",
                       "盘口", "订单流", "滑点", "冲击成本", "做市", "流动性", "盤口", "滑價",
                       "造市",
                       "板", "歩み値", "スリッページ", "気配", "호가", "체결", "슬리피지", "стакан",
                       "проскальзыван", "ликвидн", "thanh khoản", "สภาพคล่อง", "likuiditas",
                       "लिक्विडिटी", "orderfluss", "liquidität", "liquidité", "liquidità",
                       "liquidez",
                       "likidite", "נזילות", "płynność", "liquiditeit", "likviditet",
                       "likviditeetti",
                       "ukwasi", "سيولة", "session", "夜盘", "夜盤", "早盘", "尾盘",
                       "开盘", "收盘", "寄り", "引け", "장초", "장마감", "открыти", "закрыти"),
    "reversion": ("mean reversion", "revert", "reversal", "fade", "bounce", "pullback",
    "overbought",
                  "oversold", "range", "均值回归", "均值回复", "反转", "反弹", "回调", "逆势",
                  "抄底",
                  "均值回歸", "反轉", "反彈", "回檔", "逆張り", "平均回帰", "反発", "反落",
                  "押し目",
                  "戻り", "역추세", "평균회귀", "반등", "되돌림", "눌림목", "разворот", "возврат",
                  "откат", "отскок", "đảo chiều", "hồi quy", "hồi phục", "điều chỉnh", "กลับตัว",
                  "รีบาวด์", "ปรับฐาน", "pembalikan", "rebound", "koreksi", "रिवर्सल", "पलटाव",
                  "उछाल", "umkehr", "rückkehr", "erhol", "retournement", "rebond", "inversione",
                  "rimbalz", "reversión", "rebote", "reversão", "repique", "dönüş", "toparlan",
                  "היפוך", "odwrócen", "odbici", "omkeer", "herstel", "vändning", "rekyl",
                  "vending",
                  "käänne", "انعكاس", "ارتداد", "contrarian", "відскок", "розворот", "kurudi"),
    "momentum": ("momentum", "trend", "breakout", "continuation", "follow", "动量", "趋势", "突破",
                 "顺势", "延续", "追涨", "動量", "趨勢", "順勢", "モメンタム", "順張り", "ブレイク",
                 "続伸", "続落", "모멘텀", "추세", "돌파", "моментум", "импульс", "пробой",
                 "xu hướng",
                 "động lượng", "phá vỡ", "โมเมนตัม", "แนวโน้ม", "ทะลุ", "tren", "penembusan",
                 "मोमेंटम", "ट्रेंड", "ब्रेकआउट", "ausbruch", "tendance", "cassure", "tendenza",
                 "rottura", "tendencia", "ruptura", "tendência", "rompimento", "kırılım", "מגמה",
                 "פריצה", "wybicie", "uitbraak", "utbrott", "udbrud", "utbrudd", "läpimurto",
                 "mwelekeo", "kuvunja", "kasi", "زخم", "اتجاه", "اختراق", "wybici", "läpimur",
                 "пробій", "імпульс"),
}
#: Direction buckets for the dedupe key. Not exhaustive: a word outside the buckets is "other",
#: and two tellings of one story still fold together on instrument, class and horizon.
_DIR_BUCKET_TERMS: dict[str, tuple[str, ...]] = {
    "long": ("rallies", "rises", "rose", "rallied", "gained", "gains", "strengthens",
    "strengthened", "appreciates", "climb", "climbs", "surge", "surges", "jumps",
            "long", "buy", "rally", "rise", "bullish", "higher", "strengthen", "appreciate",
    "做多",
             "买入", "看多", "上涨", "涨", "走强", "拉升", "買入", "上漲", "漲", "走強", "買い",
             "ロング",
             "上昇", "続伸", "上がる", "매수", "롱", "상승", "급등", "лонг", "покуп", "рост",
             "растет",
             "растёт", "mua", "tăng", "ซื้อ", "ขึ้น", "beli", "naik", "खरीद", "तेजी", "बढ़", "kauf",
             "steig", "achat", "hausse", "compra", "rialzo", "alza", "sube", "alta", "sobe", "alım",
             "yüksel", "קנייה", "עלייה", "kupn", "wzrost", "koop", "stijg", "köp", "stig", "køb",
             "kjøp", "osta", "nous", "nunua", "kupanda", "شراء", "صعود", "ارتفاع"),
    "short": ("short", "sell", "sell-off", "selloff", "fall", "falls", "fell", "drop", "drops",
              "dropped", "bearish", "lower", "weaken", "weakens", "weakened", "depreciate",
              "depreciates", "slide", "slides", "sinks", "tumbles", "dip", "dips",
              "depreciate", "做空", "卖出", "看空", "下跌", "跌", "走弱", "砸盘", "賣出", "殺盤",
              "売り",
              "ショート", "下落", "続落", "下がる", "매도", "숏", "하락", "급락", "шорт", "прода",
              "падени", "падает", "снижен", "bán", "giảm", "ขาย", "ลง", "jual", "turun", "बेच",
              "मंदी", "गिर", "verkauf", "fall", "fällt", "vente", "baisse", "vend", "ribasso",
              "venta", "baja", "cae", "queda", "satış", "düş", "מכירה", "ירידה", "sprzeda",
              "spadek", "verkoop", "daal", "sälj", "sjunk", "sælg", "fald", "selg", "myy", "lask",
              "uza", "kushuka", "بيع", "هبوط", "انخفاض"),
    "revert": ("fade", "fades", "revert", "reverts", "reverse", "reverses", "reversed", "bounce",
               "bounces", "bounced", "rebound", "rebounds", "pullback", "反向", "回归", "反弹",
               "回落",
               "回调", "抄底", "反轉", "反彈", "回檔", "反発", "反落", "戻る", "押し目買い",
               "戻り売り",
               "반등", "되돌림", "отскок", "разворот", "đảo chiều", "hồi phục", "điều chỉnh",
               "เด้ง",
               "กลับตัว", "ปรับฐาน", "rebound", "koreksi", "berbalik", "पलट", "उछाल", "erhol",
               "dreht", "rebond", "retourne", "rimbalz", "inverte", "rebote", "revierte", "repique",
               "reverte", "tepki", "dön", "korekt", "odwrac", "herstel", "draait", "rekyl",
               "vänder",
               "vender", "snur", "elpy", "kääntyy", "kurudi", "ارتداد", "تصحيح"),
    "continue": ("continues",
                "continue", "continues", "follow", "trend", "顺势", "延续", "順勢", "延續",
    "続伸", "続落",
                 "продолж", "tiếp diễn", "ต่อเนื่อง", "berlanjut", "जारी", "fortsetz", "continue",
                 "prosegue", "continúa", "continua", "devam", "המשך", "kontynu", "vervolg",
                 "fortsätter", "fortsætter", "fortsetter", "jatkuu", "kuendelea", "استمرار"),
    "widen": ("widens", "expands", "steepens",
             "widen", "widens", "expand", "expands", "steepen", "steepens", "扩大", "擴大",
    "拡大", "확대", "расшир", "mở rộng",
              "ขยาย", "melebar", "ausweit", "s'élargit", "si allarga", "se amplía", "amplia",
              "genişle"),
    "narrow": ("narrows", "contracts", "flattens",
              "narrow", "narrows", "contract", "contracts", "flatten", "flattens", "收窄", "收敛",
    "收斂", "縮小", "축소", "сужен",
               "thu hẹp", "แคบลง", "menyempit", "verengt", "se resserre", "si restringe",
               "se estrecha", "estreita", "daral"),
}
_HOR_BUCKET_TERMS: dict[str, tuple[str, ...]] = {
    "tick": ("tick", "秒级", "秒", "틱", "тик", "scalp", "スキャルピング", "스캘핑", "скальп"),
    "intraday": ("minute", "minutes", "hour", "hours", "hourly", "intraday", "session", "open",
                 "close", "m5", "m15", "h1", "h4", "分钟", "小时", "日内", "夜盘", "早盘", "尾盘",
                 "开盘后", "收盘前", "分鐘", "小時", "日內", "夜盤", "盤中", "分", "時間",
                 "デイトレ",
                 "寄り", "引け", "日中", "分足", "時間足", "ザラ場", "분", "시간", "장중", "분봉",
                 "시간봉", "단타", "минут", "час", "интрадей", "внутри дня", "phút", "giờ",
                 "trong phiên", "cuối phiên", "đầu phiên", "นาที", "ชั่วโมง", "ระหว่างวัน", "menit",
                 "jam", "sesi", "मिनट", "घंटा", "घंटे", "इंट्राडे", "minute", "stunde", "heure",
                 "séance", "minut", "ora", "seduta", "minuto", "hora", "sesión", "sesion", "pregão",
                 "dakika", "saat", "seans", "דקה", "דקות", "שעה", "שעות", "godzin", "sesj",
                 "minuut",
                 "uur", "timme", "timmar", "time", "timer", "tunti", "tuntia", "saa", "دقيقة",
                 "ساعة", "جلسة", "خلال اليوم"),
    "daily": ("daily", "day", "days", "overnight", "next day", "d1", "当日", "次日", "每日", "日线",
              "隔夜", "交易日", "當日", "日線", "隔日沖", "日", "翌日", "日足", "オーバーナイト",
              "일",
              "당일", "익일", "일봉", "오버나잇", "дне", "день", "дневн", "овернайт", "свеч",
              "ngày",
              "qua đêm", "hôm sau", "nến ngày", "วัน", "รายวัน", "ข้ามคืน", "hari", "harian",
              "semalam", "दिन", "दैनिक", "ओवरनाइट", "tag", "täglich", "übernacht", "jour",
              "journalier", "quotidien", "giorn", "día", "diario", "dia", "diário", "gün", "günlük",
              "יום", "יומי", "dzień", "dzienn", "dag", "dagelijks", "daglig", "päivä", "siku",
              "يوم", "يومي"),
    "weekly": ("week", "weekly", "一周", "周线", "周", "一週", "週線", "週", "週足", "주", "주봉",
               "недел", "tuần", "สัปดาห์", "minggu", "pekan", "हफ्ता", "सप्ताह", "woche", "semaine",
               "settiman", "semana", "hafta", "שבוע", "tydzień", "tygodni", "week", "vecka", "uge",
               "uke", "viikko", "wiki", "أسبوع"),
    "monthly": ("month", "monthly", "quarter", "quarterly", "一个月", "月线", "月", "季度",
    "一個月",
                "月線", "月足", "四半期", "월", "월봉", "분기", "месяц", "квартал", "tháng", "quý",
                "เดือน", "ไตรมาส", "bulan", "kuartal", "महीना", "महीने", "मासिक", "तिमाही", "monat",
                "quartal", "mois", "trimestre", "mese", "mensil", "mes", "mês", "ay", "aylık",
                "çeyrek", "חודש", "רבעון", "miesiąc", "kwartał", "maand", "kwartaal", "månad",
                "kvartal", "måned", "kuukausi", "mwezi", "robo", "شهر", "ربع"),
}


def mechanism_class(text: str) -> str:
    """The first orthogonality class whose vocabulary the sentence uses, else "other"."""
    low = (text or "").lower()
    for cls in MECHANISM_CLASSES:
        if _alias_rx(_CLASS_TERMS[cls]).search(low):
            return cls
    return "other"


def _bucket(terms: dict[str, tuple[str, ...]], words: list[str]) -> str:
    for w in words:
        wl = w.lower()
        for name, vocab in terms.items():
            if wl in vocab:
                return name
    return "other"


def mechanism_key(inst: dict[str, Any], cls: str, direction: list[str], horizon: list[str]) -> str:
    """The stable identity of a MECHANISM, independent of who told it and in which language:
    instrument (analogues, else indirect targets, else transfer classes), mechanism class,
    direction bucket and horizon bucket. Ten tellings fold to one key."""
    target = (sorted(inst.get("analogues") or []) or sorted(inst.get("indirect") or [])
              or sorted(t.split("->",
                                1)[-1].split(" (")[0] for t in (inst.get("transfer_only") or [])))
    key = "|".join([",".join(target), cls, _bucket(_DIR_BUCKET_TERMS, direction),
                    _bucket(_HOR_BUCKET_TERMS, horizon)])
    return hashlib.sha256(key.encode("utf-8")).hexdigest()[:16]


# ============================================================================== stated numbers
# Sentence enders: ASCII plus the full-width ideographic stop, bang, question and semicolon
# (U+3002, U+FF01, U+FF1F, U+FF1B), the Devanagari danda (U+0964) and the Arabic question mark
# (U+061F), written as escapes so the linter does not read them as typos.
_SPLIT = re.compile("(?<=[.!?\u3002\uff01\uff1f\uff1b;\u0964\u061f])\\s*|\\n+")
_PERF: tuple[tuple[str, str], ...] = (
    ("return_pct",
     r"(?:收益率?|報酬率?|年化(?:收益|報酬)?|盈利|利回り|リターン|수익률|доходност[ьи]?|"
                   r"дохідн[іи]сть|lợi nhuận|ผลตอบแทน|imbal hasil|रिटर्न|rendite|rendement|"
                   r"rendimiento|rentabilidad|retorno|rentabilidade|getiri|תשואה|stopa zwrotu|"
                   r"rendement|avkastning|afkast|tuotto|mapato|عائد|return(?:s)?|"
                   r"annual(?:ised|ized)?|cagr)\D{0,12}?(-?\d+(?:\.\d+)?)\s*%"),
    ("drawdown_pct", r"(?:最大回撤|回撤|最大ドローダウン|ドローダウン|최대낙폭|낙폭|просадк[аи]|"
                     r"drawdown|rebaixamento|sụt giảm tối đa|डीडी)\D{0,12}?(-?\d+(?:\.\d+)?)\s*%"),
    ("sharpe", r"(?:夏普(?:比率)?|シャープ(?:レシオ)?|샤프(?:지수|비율)?|шарп[а]?|sharpe)"
               r"\D{0,12}?(-?\d+(?:\.\d+)?)"),
    ("win_rate_pct", r"(?:胜率|勝率|승률|винрейт|процент прибыльных|win ?rate|trefferquote|"
                     r"taux de réussite|tasa de acierto|taxa de acerto|tỷ lệ thắng|"
                     r"อัตราชนะ|win ratio)\D{0,12}?(\d+(?:\.\d+)?)\s*%"),
    ("profit_factor", r"(?:盈亏比|プロフィットファクター|손익비|профит-?фактор|profit factor|"
                      r"fator de lucro|factor de beneficio|(?<![a-z])pf)\D{0,12}?(\d+(?:\.\d+)?)"),
)
_PERF_RE: tuple[tuple[str, re.Pattern[str]], ...] = tuple((n, re.compile(r)) for n, r in _PERF)
#: A date the sentence itself states -- the EVENT time of the claim, when there is one.
_DATE = re.compile(r"(20\d{2})[-/年.](\d{1,2})[-/月.](\d{1,2})日?"
                   r"|(\d{1,2})[./](\d{1,2})[./](20\d{2})")


def performance(text: str) -> dict[str, float]:
    """Stated performance numbers. A STORY'S NUMBERS ARE EVIDENCE ABOUT THE STORY, NOT ABOUT THE
    MECHANISM -- they are kept so the reader can weigh the claim, never used as a prior."""
    out: dict[str, float] = {}
    low = (text or "").lower()
    for name, rx in _PERF_RE:
        m = rx.search(low)
        if m:
            try:
                out[name] = float(m.group(1))
            except ValueError:
                continue
    return out


def stated_date(text: str) -> str | None:
    """YYYY-MM-DD when the sentence names a date, else None. Never guessed."""
    m = _DATE.search(text or "")
    if not m:
        return None
    y, mo, d = (m.group(1), m.group(2), m.group(3)) if m.group(1) else (m.group(6), m.group(5),
                                                                      m.group(4))
    try:
        if not (1 <= int(mo) <= 12 and 1 <= int(d) <= 31):
            return None
    except ValueError:
        return None
    return f"{int(y):04d}-{int(mo):02d}-{int(d):02d}"


# ============================================================================== extraction
_STEM_RE: dict[tuple[str, ...], re.Pattern[str]] = {}


_EN_RE: dict[tuple[str, ...], re.Pattern[str]] = {}


def _hits_en(words: tuple[str, ...], low: str) -> list[str]:
    """English words, whole-word only (`fix` is not `fixture`, `follow` is not `following`)."""
    rx = _EN_RE.get(words)
    if rx is None:
        alts = "|".join(re.escape(w) for w in sorted(set(words), key=len, reverse=True))
        rx = _EN_RE[words] = re.compile(r"(?<![a-z])(?:" + alts + r")(?![a-z])")
    out: list[str] = []
    for m in rx.finditer(low):
        if m.group(0) not in out:
            out.append(m.group(0))
    return out


def _hits_zh(words: tuple[str, ...], low: str) -> list[str]:
    return [w for w in words if w in low]


def _hits_stem(words: tuple[str, ...], low: str) -> list[str]:
    """Words that START at a word boundary and may continue -- one compiled alternation per
    vocabulary, longest first, so `steig` finds `steigt` and `steigen` in one pass."""
    key = words
    rx = _STEM_RE.get(key)
    if rx is None:
        alts = "|".join(re.escape(w) for w in sorted(set(words), key=len, reverse=True))
        rx = _STEM_RE[key] = re.compile(r"(?<!\w)(?:" + alts + ")")
        if len(_STEM_RE) > 256:
            _STEM_RE.clear()
            _STEM_RE[key] = rx
    out: list[str] = []
    for m in rx.finditer(low):
        w = m.group(0)
        if w not in out:
            out.append(w)
    return out


def _hits(lang: str, words: tuple[str, ...], low: str) -> list[str]:
    return _hits_zh(words, low) if lang in _SUBSTRING_LANGS else _hits_stem(words, low)


def _dedupe(words: list[str]) -> list[str]:
    out: list[str] = []
    for w in words:
        if w not in out:
            out.append(w)
    return out


def extract_claims(text: str, *, max_claims: int = 40,
                   universe: set[str] | None = None) -> list[dict[str, Any]]:
    """Sentences naming a quantity, a direction and a horizon -- verbatim, never paraphrased.

    Returns the claims and nothing else; the drops are available through `extract` for a
    report that must show the fences working.
    """
    claims: list[dict[str, Any]] = extract(text, max_claims=max_claims,
                                           universe=universe)["claims"]
    return claims


def extract_claims_with_drops(text: str, *, max_claims: int = 40,
                              universe: set[str] | None = None
                              ) -> tuple[list[dict[str, Any]], int]:
    """(claims, crypto-venue drops) -- the older two-value shape, kept for its callers."""
    r = extract(text, max_claims=max_claims, universe=universe)
    return r["claims"], int(r["dropped_venue"])


def extract(text: str, *, max_claims: int = 40,
            universe: set[str] | None = None) -> dict[str, Any]:
    """Claims plus the counted fences: `dropped_venue` (crypto exchange named),
    `dropped_unmappable` (no MT5 analogue, no indirect target, no transfer note -- a summary
    nobody can test), and `duplicate_mechanisms` (a second sentence with the same key)."""
    out: list[dict[str, Any]] = []
    dropped_venue = dropped_unmappable = duplicates = 0
    seen: set[str] = set()
    keys: set[str] = set()
    # THE DOCUMENT NAMES THE INSTRUMENT ONCE. "I have traded Shanghai gold for seven years" is
    # sentence one; the mechanism is sentence three and says "it". A claim that names no
    # instrument inherits the document's, marked as context so the reader knows it was inherited.
    doc_inst = resolve_instruments((text or "").lower(), universe)
    for raw in _SPLIT.split(text or ""):
        s = re.sub(r"\s+", " ", raw).strip()
        if not s:
            continue
        lang = language_of(s)
        dense = lang in _SUBSTRING_LANGS
        lo, hi = (10, 400) if dense else (20, 400)
        if not (lo <= len(s) <= hi):
            continue
        low = s.lower()
        if forbidden_venue(low):
            dropped_venue += 1
            continue
        qv, dv, hv = _VOCAB.get(lang, (QUANTITY_EN, DIRECTION_EN, HORIZON_EN))
        # The ground's own vocabulary first, then English whole-word (RSI, breakout, COT ...
        # travel into every language); English itself is never stem-matched.
        q = _dedupe(_hits(lang, qv, low) + _hits_en(QUANTITY_EN, low)) if lang != "en" \
            else _hits_en(QUANTITY_EN, low)
        d = _dedupe(_hits(lang, dv, low) + _hits_en(DIRECTION_EN, low)) if lang != "en" \
            else _hits_en(DIRECTION_EN, low)
        h = _dedupe(_hits(lang, hv, low) + _hits_en(HORIZON_EN, low)) if lang != "en" \
            else _hits_en(HORIZON_EN, low)
        if not (q and d and h):
            continue
        digest = hashlib.sha256(s.encode("utf-8")).hexdigest()[:12]
        if digest in seen:
            continue
        seen.add(digest)
        inst = resolve_instruments(low, universe)
        inherited = False
        if not (inst["analogues"] or inst["transfer_only"] or inst["indirect"]) and (
                doc_inst["analogues"] or doc_inst["transfer_only"] or doc_inst["indirect"]):
            inst = {**doc_inst, "from_context": True}
            inherited = True
        if not (inst["analogues"] or inst["transfer_only"] or inst["indirect"]):
            dropped_unmappable += 1                     # a summary nobody can test
            continue
        channel = "direct" if inst["analogues"] else "indirect"
        cls = mechanism_class(low)
        key = mechanism_key(inst, cls, d[:2], h[:2])
        if key in keys:
            duplicates += 1
            continue
        keys.add(key)
        out.append({"claim": s, "lang": lang, "quantities": q[:4],
                    "direction": d[:2], "horizon": h[:2], "instruments": inst,
                    "instrument_from_context": inherited, "channel": channel,
                    "mechanism_class": cls, "mechanism_key": key,
                    "event_time": stated_date(s),
                    "claimed_performance": performance(s), "claim_hash": digest})
        if len(out) >= max_claims:
            break
    return {"claims": out, "dropped_venue": dropped_venue,
            "dropped_unmappable": dropped_unmappable, "duplicate_mechanisms": duplicates}


def claim_score(c: dict[str, Any]) -> float:
    """How much a claim is worth reading FIRST. Resolved instrument and a stated horizon beat a
    vague story; stated numbers add a little, because they at least make the story checkable;
    a structural class (policy, flow, inventory ...) edges out the four-hundredth momentum
    variant, which is the orthogonality target stated as a tie-break."""
    s = 1.0
    if c.get("instruments", {}).get("analogues"):
        s += 1.0
    if c.get("instruments", {}).get("transfer_only") or c.get("instruments", {}).get("indirect"):
        s += 0.25
    if len(c.get("quantities") or []) >= 2:
        s += 0.5
    if c.get("claimed_performance"):
        s += 0.25
    if c.get("mechanism_class") not in ("momentum", "other", None):
        s += 0.1
    return s

```

### libs\research\program_ir.py
```python
"""A restricted PROGRAM algebra: candidates that branch, remember, and watch a clock.

WHY THIS EXISTS (ledger item D4, principal 2026-09-16)

`libs/research_os/dsl.py` already refuses to be an interpreter, and that refusal is the reason
this module exists rather than a reason it does not: the desk may search PROGRAMS, but it may
never execute model-written source on the box that holds the live terminal. So the DSL's idea is
extended here, not duplicated -- a JSON tree, an operator allowlist, validation before any data
is touched, evaluation by walking the tree into vetted pandas calls. There is no eval, no exec,
no attribute access, no import and no user-supplied callable anywhere in this path either.

WHAT IS NEW, and it is exactly what D4 measured as missing. `alpha_grammar` and `research_os.dsl`
both search a typed EXPRESSION: one formula evaluated identically on every bar. An expression
cannot say "while we are inside the Asia range do nothing; once it breaks, ride it until the
London close", cannot count the bars to the next month-end fixing, cannot widen its own lookback
when volatility rises, and cannot hold a threshold that re-estimates itself -- control flow,
state, an event clock, a dynamic lookback, an adaptive threshold. This IR adds them as NODES, so
the search space grows without the executor growing a way to run arbitrary code.

THE NODES ARE THE SECURITY BOUNDARY, exactly as `dsl.OPS` is: eleven frozen dataclasses with
typed fields, and anything else refused by name. A program is JSON in and JSON out, so a program
IS its recipe and `fingerprint` hashes two spellings of one hypothesis the same.

LOOK-AHEAD IS STRUCTURALLY IMPOSSIBLE. Every rolling window is trailing (pandas `rolling` at bar
i spans i-w+1..i), the state machine is a forward scan that sees each bar once, the cross-asset
reference is reindex-then-forward-fill (the other instrument's last KNOWN bar), and the event
clock is measured in ELAPSED TIME against a calendar published in advance rather than in bar
positions -- which is what makes "bars to the next event" point-in-time rather than a peek at the
end of the sample. The property is asserted, not asserted-about: `tests/research/
test_program_ir.py` re-evaluates every node on a truncated frame and on a frame whose FUTURE bars
were replaced, and requires the past outputs to be identical.

THE MONEY PATH NEVER SEES A TREE. `compile_program` returns a callable producing the desk's own
`mt5desk.engine.Signal` objects -- the contract every registered family produces -- so a program
reaching the forward engine is indistinguishable from a family, and one that cannot be compiled
reaches nothing at all.
"""
from __future__ import annotations

import hashlib
import json
import sys
from collections.abc import Callable, Iterator, Mapping, Sequence
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
DESK = ROOT / "desks" / "mt5"
#: The forced-flow calendar the EventClock node reads. Tolerant: an unreadable or absent file is
#: UNMEASURED (every clock series is NaN), never a substituted calendar.
CALENDAR_PATH = DESK / "data" / "forced_flow_calendar.json"

#: Terminals a Series node may name. `hour` and `dow` are the bar's own BROKER stamp (Fusion runs
#: UTC+3, and the bars are on that clock -- see `dsl.SESSIONS`), which is how a program says
#: "inside the Asia window" without a session operator. `tr` is the true range and `atr` its
#: 14-bar mean, the desk's `families._atr` default -- imported, never re-spelled.
FIELDS: tuple[str, ...] = ("open", "high", "low", "close", "ret", "range", "body", "tr", "atr",
                           "typical", "activity", "spread", "hour", "dow")
ROLLING_OPS: tuple[str, ...] = ("mean", "std", "max", "min", "sum", "zscore", "rank")
BINARY_OPS: tuple[str, ...] = ("add", "sub", "mul", "div", "min2", "max2")
COMPARE_OPS: tuple[str, ...] = ("gt", "ge", "lt", "le")
CLOCK_MODES: tuple[str, ...] = ("since", "to")
#: The kinds `forced_flow_calendar.json` publishes. An allowlist for the same reason `dsl.OPS` is
#: one: adding a kind is a reviewable act, and a typo is refused by name instead of silently
#: producing an all-NaN clock that reads like a mechanism with no signal.
CALENDAR_KINDS: tuple[str, ...] = ("month_end", "quarter_end", "index_rebalance", "futures_roll",
                                   "option_expiry", "bond_auction", "central_bank", "fixing",
                                   "inventory", "usda", "holiday_liquidity")

MAX_DEPTH = 10
MAX_NODES = 80
MIN_WINDOW = 2
MAX_WINDOW = 1000
MAX_STATES = 6
MAX_TRANSITIONS = 4
MAX_SLOTS = 12
#: Execution slots every compiled program carries whether or not its logic mentions them. They
#: are RESERVED: a tree may not declare a Slot by these names, because two meanings for one name
#: is how an optimiser ends up tuning a stop it thinks is a lookback.
RESERVED = ("stop_atr", "rr", "ttl_bars", "atr_n")

#: The meta-evolution layer's active variants (LAWS 5m). A `program_ir` variant narrows the
#: operator vocabulary `mutate_logic` draws from; it can never widen it past the module's own.
ACTIVE_VARIANTS = DESK / "data" / "research_evolution" / "active_variants.json"


@dataclass(frozen=True)
class Grammar:
    """The vocabulary a structural mutation may draw from -- a representation grammar variant.

    Every field is a SUBSET of the module's vocabulary: `active_grammar` intersects a variant's
    lists with `ROLLING_OPS`, `BINARY_OPS` and `COMPARE_OPS`, so an evolved grammar can focus the
    search and can never introduce an operator `validate` would refuse.
    """

    rolling_ops: tuple[str, ...] = ROLLING_OPS
    binary_ops: tuple[str, ...] = BINARY_OPS
    compare_ops: tuple[str, ...] = COMPARE_OPS
    max_depth: int = MAX_DEPTH
    state_machines: bool = True
    variant: str | None = None


def active_grammar(path: Path | None = None) -> Grammar:
    """The grammar the meta-evolution layer activated, or the module defaults when none is
    published, unreadable, or empty after intersection."""
    try:
        doc = json.loads((path or ACTIVE_VARIANTS).read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return Grammar()
    var = (doc.get("variants") or {}).get("program_ir") if isinstance(doc, dict) else None
    if not isinstance(var, dict) or not isinstance(var.get("config"), dict):
        return Grammar()
    cfg = var["config"]

    def _sub(key: str, base: tuple[str, ...]) -> tuple[str, ...]:
        raw = cfg.get(key)
        if not isinstance(raw, list):
            return base
        kept = tuple(op for op in base if op in {str(x) for x in raw})
        return kept or base

    depth = cfg.get("max_depth")
    return Grammar(rolling_ops=_sub("rolling_ops", ROLLING_OPS),
                   binary_ops=_sub("binary_ops", BINARY_OPS),
                   compare_ops=_sub("compare_ops", COMPARE_OPS),
                   max_depth=(int(min(MAX_DEPTH, max(2, depth)))
                              if isinstance(depth, (int, float)) else MAX_DEPTH),
                   state_machines=bool(cfg.get("state_machines", True)),
                   variant=str(var.get("id")) if var.get("id") else None)


class ProgramError(ValueError):
    """A tree this module refuses, with the reason a reviewer needs."""


# --------------------------------------------------------------------------- the node algebra
@dataclass(frozen=True)
class Const:
    """A scalar, broadcast over the bar index."""
    value: float


@dataclass(frozen=True)
class Series:
    """One terminal of the primary instrument's bars. `field` must be in `FIELDS`."""
    field: str


@dataclass(frozen=True)
class Slot:
    """A numeric the optimiser tunes, bounded by construction.

    A Slot evaluates to whatever value is bound for its name (clamped into [lo, hi]) and to
    `default` when nothing is bound -- so a program is runnable before it is ever tuned, and a
    tuning run can never push a window past `MAX_WINDOW` by handing in a larger number.
    """
    name: str
    lo: float
    hi: float
    default: float


@dataclass(frozen=True)
class Rolling:
    """A trailing statistic. `window` is a Slot (a DYNAMIC lookback) or a fixed int.

    `lag` ENDS the window that many bars ago, and it is not a convenience. `close > max(high, w)`
    is FALSE ON EVERY BAR -- the window contains this bar's own high, which is never below its
    close -- so a breakout written without it is a rule that cannot fire, and a search would read
    the resulting silence as "no edge here" rather than as "this question was never asked".
    """
    op: str
    child: Node
    window: Slot | int
    lag: Slot | int = 0


@dataclass(frozen=True)
class Binary:
    """Arithmetic on two series."""
    op: str
    left: Node
    right: Node


@dataclass(frozen=True)
class Compare:
    """A predicate as 1.0 / 0.0, so a condition is a series like everything else."""
    op: str
    left: Node
    right: Node


@dataclass(frozen=True)
class Cond:
    """CONTROL FLOW: `when` > 0 takes `then`, otherwise `otherwise`. Bar by bar, no lookahead."""
    when: Node
    then: Node
    otherwise: Node


@dataclass(frozen=True)
class Transition:
    """Leave for state `to` on the first bar `when` holds. Order inside a state is priority."""
    to: str
    when: Compare


@dataclass(frozen=True)
class StateDef:
    name: str
    value: int
    transitions: tuple[Transition, ...] = ()


@dataclass(frozen=True)
class State:
    """A STATE MACHINE, emitting the current state's `value` as a series.

    `states[0]` is the initial state. The emitted value at bar i is the state AFTER that bar's
    transitions have been tested, so it uses bar i and no later one. Encode a short as a NEGATIVE
    state value: `compile_program` reads the root's SIGN as the direction.
    """
    states: tuple[StateDef, ...]


@dataclass(frozen=True)
class EventClock:
    """Bars since the last / to the next calendar event of `kind`.

    MEASURED IN ELAPSED TIME divided by the frame's own bar span, not in bar positions. That is
    what makes "to the next event" point-in-time: the calendar is published in advance, so the
    distance to a scheduled fixing is knowable at the bar, while a bar-position count would need
    to know how many bars the market has yet to print. Weekends therefore count as bars, because
    the forced actor's deadline does not pause for them.
    """
    kind: str
    mode: str = "since"


@dataclass(frozen=True)
class Adaptive:
    """An ADAPTIVE THRESHOLD: the trailing `q`-quantile of `child` over `window`.

    A fixed threshold is a claim about a level; this is a claim about a POSITION in the recent
    distribution, which is the same claim re-estimated as the instrument's regime moves.
    """
    child: Node
    window: Slot | int
    q: Slot | float = 0.8


@dataclass(frozen=True)
class CrossRef:
    """Another instrument's field, supplied by the caller and joined causally.

    Reindexed onto the primary's bars and forward-filled: the reference's last KNOWN value. A
    symbol the caller did not supply evaluates to NaN -- UNMEASURED, never a substituted peer.
    """
    symbol: str
    field: str


Node = (Const | Series | Slot | Rolling | Binary | Compare | Cond | State | EventClock
        | Adaptive | CrossRef)

_NODE_NAMES: dict[type, str] = {
    Const: "const", Series: "series", Slot: "slot", Rolling: "rolling", Binary: "binary",
    Compare: "compare", Cond: "cond", State: "state", EventClock: "event_clock",
    Adaptive: "adaptive", CrossRef: "cross_ref",
}


@dataclass
class Extras:
    """Everything evaluation may touch beyond the primary bars. Nothing else is reachable."""
    slots: Mapping[str, float] = field(default_factory=dict)
    cross: Mapping[str, pd.DataFrame] = field(default_factory=dict)
    calendar: Sequence[Mapping[str, Any]] = ()
    symbol: str = ""


# --------------------------------------------------------------------------- JSON codec
def _win_json(w: Slot | int | float) -> Any:
    return to_json(w) if isinstance(w, Slot) else w


def to_json(tree: Node) -> dict[str, Any]:
    """The tree as plain JSON. Canonical: field order is this function's, not the caller's."""
    name = _NODE_NAMES.get(type(tree))
    if name is None:
        raise ProgramError(f"{type(tree).__name__} is not a program node")
    if isinstance(tree, Const):
        return {"node": name, "value": float(tree.value)}
    if isinstance(tree, Series):
        return {"node": name, "field": tree.field}
    if isinstance(tree, Slot):
        return {"node": name, "name": tree.name, "lo": float(tree.lo), "hi": float(tree.hi),
                "default": float(tree.default)}
    if isinstance(tree, Rolling):
        return {"node": name, "op": tree.op, "child": to_json(tree.child),
                "window": _win_json(tree.window), "lag": _win_json(tree.lag)}
    if isinstance(tree, Binary | Compare):
        return {"node": name, "op": tree.op, "left": to_json(tree.left),
                "right": to_json(tree.right)}
    if isinstance(tree, Cond):
        return {"node": name, "when": to_json(tree.when), "then": to_json(tree.then),
                "otherwise": to_json(tree.otherwise)}
    if isinstance(tree, State):
        return {"node": name, "states": [
            {"name": s.name, "value": int(s.value),
             "transitions": [{"to": t.to, "when": to_json(t.when)} for t in s.transitions]}
            for s in tree.states]}
    if isinstance(tree, EventClock):
        return {"node": name, "kind": tree.kind, "mode": tree.mode}
    if isinstance(tree, Adaptive):
        return {"node": name, "child": to_json(tree.child), "window": _win_json(tree.window),
                "q": _win_json(tree.q)}
    return {"node": name, "symbol": tree.symbol, "field": tree.field}


def _win_from(obj: Any) -> Slot | int:
    if isinstance(obj, Mapping):
        got = from_json(obj)
        if not isinstance(got, Slot):
            raise ProgramError("a window may only be a Slot or an int")
        return got
    if isinstance(obj, bool) or not isinstance(obj, (int, float)):
        raise ProgramError(f"window {obj!r} is not numeric")
    return int(obj)


def from_json(obj: Any) -> Node:
    """Rebuild a tree from JSON. An unknown node name is refused, never approximated."""
    if not isinstance(obj, Mapping):
        raise ProgramError(f"a node must be an object, got {type(obj).__name__}")
    kind = obj.get("node")
    if kind == "const":
        return Const(float(obj["value"]))
    if kind == "series":
        return Series(str(obj["field"]))
    if kind == "slot":
        return Slot(str(obj["name"]), float(obj["lo"]), float(obj["hi"]), float(obj["default"]))
    if kind == "rolling":
        return Rolling(str(obj["op"]), from_json(obj["child"]), _win_from(obj["window"]),
                       _win_from(obj.get("lag", 0)) if obj.get("lag") else 0)
    if kind in ("binary", "compare"):
        cls = Binary if kind == "binary" else Compare
        return cls(str(obj["op"]), from_json(obj["left"]), from_json(obj["right"]))
    if kind == "cond":
        return Cond(from_json(obj["when"]), from_json(obj["then"]), from_json(obj["otherwise"]))
    if kind == "state":
        states: list[StateDef] = []
        for s in obj["states"]:
            trs: list[Transition] = []
            for t in s.get("transitions", ()):
                when = from_json(t["when"])
                if not isinstance(when, Compare):
                    raise ProgramError("a transition fires on a Compare and nothing else")
                trs.append(Transition(str(t["to"]), when))
            states.append(StateDef(str(s["name"]), int(s["value"]), tuple(trs)))
        return State(tuple(states))
    if kind == "event_clock":
        return EventClock(str(obj["kind"]), str(obj.get("mode", "since")))
    if kind == "adaptive":
        q = obj.get("q", 0.8)
        qq: Slot | float = _win_from(q) if isinstance(q, Mapping) else float(q)
        return Adaptive(from_json(obj["child"]), _win_from(obj["window"]), qq)
    if kind == "cross_ref":
        return CrossRef(str(obj["symbol"]), str(obj["field"]))
    raise ProgramError(f"unknown node {kind!r}; the allowlist is {sorted(_NODE_NAMES.values())}")


def fingerprint(tree: Node) -> str:
    """A canonical hash of the LOGIC. Two trees that hash the same are one hypothesis."""
    blob = json.dumps(to_json(tree), sort_keys=True, separators=(",", ":"))
    return hashlib.blake2b(blob.encode("utf-8"), digest_size=8).hexdigest()


# --------------------------------------------------------------------------- structure
def _children(n: Node) -> tuple[Node, ...]:
    """The REPLACEABLE structural children -- what a mutation may swap out."""
    if isinstance(n, Rolling | Adaptive):
        return (n.child,)
    if isinstance(n, Binary | Compare):
        return (n.left, n.right)
    if isinstance(n, Cond):
        return (n.when, n.then, n.otherwise)
    if isinstance(n, State):
        return tuple(t.when for s in n.states for t in s.transitions)
    return ()


def _rebuild(n: Node, kids: Sequence[Node]) -> Node:
    if isinstance(n, Rolling | Adaptive):
        return replace(n, child=kids[0])
    if isinstance(n, Binary | Compare):
        return replace(n, left=kids[0], right=kids[1])
    if isinstance(n, Cond):
        return replace(n, when=kids[0], then=kids[1], otherwise=kids[2])
    if isinstance(n, State):
        it = iter(kids)
        out: list[StateDef] = []
        for s in n.states:
            trs = tuple(replace(t, when=k) if isinstance(k := next(it), Compare) else t
                        for t in s.transitions)
            out.append(replace(s, transitions=trs))
        return replace(n, states=tuple(out))
    return n


def walk(tree: Node) -> Iterator[Node]:
    """Every node, including the Slots hiding inside windows and quantiles."""
    yield tree
    for k in _children(tree):
        yield from walk(k)
    if isinstance(tree, Rolling | Adaptive) and isinstance(tree.window, Slot):
        yield tree.window
    if isinstance(tree, Rolling) and isinstance(tree.lag, Slot):
        yield tree.lag
    if isinstance(tree, Adaptive) and isinstance(tree.q, Slot):
        yield tree.q


def size(tree: Node) -> int:
    return sum(1 for _ in walk(tree))


def depth(tree: Node) -> int:
    kids = _children(tree)
    return 1 + (max(depth(k) for k in kids) if kids else 0)


def slots(tree: Node) -> list[Slot]:
    """The tuneable numerics of this tree, deduped by name. Execution slots are not here."""
    out: dict[str, Slot] = {}
    for n in walk(tree):
        if isinstance(n, Slot):
            out.setdefault(n.name, n)
    return [out[k] for k in sorted(out)]


def exec_slots() -> list[Slot]:
    """The four slots every compiled program carries: how it stops, targets, times out, sizes."""
    return [Slot("stop_atr", 0.4, 3.0, 1.2), Slot("rr", 0.8, 4.0, 1.5),
            Slot("ttl_bars", 2.0, 72.0, 8.0), Slot("atr_n", 7.0, 48.0, 14.0)]


# --------------------------------------------------------------------------- validation
def validate(tree: Any) -> list[str]:
    """Every reason this tree is not a program. Empty means it is one.

    Runs BEFORE any data is touched, exactly as `dsl.validate` does, and reports ALL the reasons
    rather than the first -- a generator that gets one refusal per attempt learns one thing per
    attempt.
    """
    errs: list[str] = []
    seen: dict[str, Slot] = {}
    _check(tree, 0, errs, seen)
    if len(seen) > MAX_SLOTS:
        errs.append(f"{len(seen)} slots; the cap is {MAX_SLOTS} -- a wider box is a longer search")
    try:
        if size(tree) > MAX_NODES:
            errs.append(f"tree larger than {MAX_NODES} nodes")
        if depth(tree) > MAX_DEPTH:
            errs.append(f"tree deeper than {MAX_DEPTH}; complexity is a redundancy risk")
    except (AttributeError, TypeError, RecursionError):
        pass
    return errs


def _check_window(w: Any, where: str, errs: list[str], seen: dict[str, Slot]) -> None:
    if isinstance(w, Slot):
        _check(w, 0, errs, seen)
        if w.lo < MIN_WINDOW or w.hi > MAX_WINDOW:
            errs.append(f"{where} slot {w.name} spans [{w.lo}, {w.hi}]; windows live in "
                        f"[{MIN_WINDOW}, {MAX_WINDOW}]")
        return
    if isinstance(w, bool) or not isinstance(w, int):
        errs.append(f"{where} must be a Slot or an int, got {type(w).__name__}")
        return
    if not MIN_WINDOW <= w <= MAX_WINDOW:
        errs.append(f"{where} {w} is outside [{MIN_WINDOW}, {MAX_WINDOW}]")


def _check(n: Any, d: int, errs: list[str], seen: dict[str, Slot]) -> None:
    if type(n) not in _NODE_NAMES:
        errs.append(f"unknown node {type(n).__name__}; the allowlist is "
                    f"{sorted(_NODE_NAMES.values())}")
        return
    if d > MAX_DEPTH:
        errs.append(f"tree deeper than {MAX_DEPTH}")
        return
    if isinstance(n, Const) and not np.isfinite(n.value):
        errs.append("a Const must be finite")
    elif isinstance(n, Series) and n.field not in FIELDS:
        errs.append(f"unknown field {n.field!r}; the terminals are {list(FIELDS)}")
    elif isinstance(n, CrossRef) and n.field not in FIELDS:
        errs.append(f"cross reference to unknown field {n.field!r}")
    elif isinstance(n, Slot):
        if n.name in RESERVED:
            errs.append(f"slot {n.name!r} is a RESERVED execution slot; a tree may not redefine it")
        if not (n.lo <= n.default <= n.hi) or not np.isfinite([n.lo, n.hi, n.default]).all():
            errs.append(f"slot {n.name}: default {n.default} outside [{n.lo}, {n.hi}]")
        prior = seen.get(n.name)
        if prior is not None and prior != n:
            errs.append(f"slot {n.name} declared twice with different bounds")
        seen.setdefault(n.name, n)
    elif isinstance(n, Rolling):
        if n.op not in ROLLING_OPS:
            errs.append(f"unknown rolling op {n.op!r}; the allowlist is {list(ROLLING_OPS)}")
        _check_window(n.window, "Rolling.window", errs, seen)
        lag = n.lag
        if isinstance(lag, Slot):
            _check(lag, d + 1, errs, seen)
            if lag.lo < 0 or lag.hi > MAX_WINDOW:
                errs.append(f"Rolling.lag slot {lag.name} must stay in [0, {MAX_WINDOW}]")
        elif isinstance(lag, bool) or not isinstance(lag, int) or not 0 <= lag <= MAX_WINDOW:
            errs.append(f"Rolling.lag {lag!r} must be an int in [0, {MAX_WINDOW}]")
    elif isinstance(n, Binary) and n.op not in BINARY_OPS:
        errs.append(f"unknown binary op {n.op!r}; the allowlist is {list(BINARY_OPS)}")
    elif isinstance(n, Compare) and n.op not in COMPARE_OPS:
        errs.append(f"unknown compare op {n.op!r}; the allowlist is {list(COMPARE_OPS)}")
    elif isinstance(n, EventClock):
        if n.kind not in CALENDAR_KINDS:
            errs.append(f"unknown calendar kind {n.kind!r}; the allowlist is "
                        f"{list(CALENDAR_KINDS)}")
        if n.mode not in CLOCK_MODES:
            errs.append(f"unknown clock mode {n.mode!r}; use one of {list(CLOCK_MODES)}")
    elif isinstance(n, Adaptive):
        _check_window(n.window, "Adaptive.window", errs, seen)
        if isinstance(n.q, Slot):
            _check(n.q, d + 1, errs, seen)
            if not (n.q.lo > 0.0 and n.q.hi < 1.0):
                errs.append(f"quantile slot {n.q.name} must stay strictly inside (0, 1)")
        elif not 0.0 < float(n.q) < 1.0:
            errs.append(f"quantile {n.q} must be strictly inside (0, 1)")
    elif isinstance(n, State):
        names = [s.name for s in n.states]
        if not 2 <= len(n.states) <= MAX_STATES:
            errs.append(f"a state machine has 2..{MAX_STATES} states, got {len(n.states)}")
        if len(set(names)) != len(names):
            errs.append("two states share a name")
        for s in n.states:
            if len(s.transitions) > MAX_TRANSITIONS:
                errs.append(f"state {s.name} has more than {MAX_TRANSITIONS} transitions")
            for t in s.transitions:
                if t.to not in names:
                    errs.append(f"state {s.name} transitions to unknown state {t.to!r}")
                if not isinstance(t.when, Compare):
                    errs.append(f"state {s.name}: a transition fires on a Compare only")
    for k in _children(n):
        _check(k, d + 1, errs, seen)


# --------------------------------------------------------------------------- evaluation
_DESK: Any = None


def _desk() -> Any:
    """The desk package, for the ONE spelling of ATR and the ONE Signal contract."""
    global _DESK
    if _DESK is None:
        # APPENDED, never inserted. `desks/mt5` carries top-level `research` and `scripts`
        # packages whose names also exist at the repository root, and putting it first would
        # silently re-point every OTHER importer in the process at the desk's copies.
        if str(DESK) not in sys.path:
            sys.path.append(str(DESK))
        try:
            from mt5desk import families
        except Exception as exc:                                 # pragma: no cover - install
            raise ProgramError(f"mt5desk is unreachable ({type(exc).__name__}: {exc}); a program "
                               "may not carry a second spelling of the desk's ATR or Signal") \
                from exc
        _DESK = families
    return _DESK


def _signal() -> Any:
    """The desk's OWN Signal class. One contract; a local re-spelling would diverge silently."""
    _desk()
    from mt5desk.engine import Signal
    return Signal


def _nan(idx: pd.Index) -> pd.Series:
    return pd.Series(np.nan, index=idx, dtype=float)


def _value(x: Slot | int | float, ex: Extras) -> float:
    if isinstance(x, Slot):
        v = float(ex.slots.get(x.name, x.default))
        return float(min(max(v, x.lo), x.hi))
    return float(x)


def _window(x: Slot | int | float, ex: Extras) -> int:
    return int(min(max(round(_value(x, ex)), MIN_WINDOW), MAX_WINDOW))


def _terminal(bars: pd.DataFrame, name: str) -> pd.Series:
    idx = bars.index
    if name in ("open", "high", "low", "close"):
        return bars[name].astype(float) if name in bars.columns else _nan(idx)
    if name in ("activity", "spread"):
        col = "tick_volume" if name == "activity" else "spread"
        return bars[col].astype(float) if col in bars.columns else _nan(idx)
    if name in ("hour", "dow"):
        if not isinstance(idx, pd.DatetimeIndex):
            return _nan(idx)
        vals = idx.hour if name == "hour" else idx.dayofweek
        return pd.Series(np.asarray(vals, dtype=float), index=idx)
    if any(c not in bars.columns for c in ("open", "high", "low", "close")):
        return _nan(idx)
    h, lo, c, o = (bars["high"].astype(float), bars["low"].astype(float),
                   bars["close"].astype(float), bars["open"].astype(float))
    if name == "ret":
        with np.errstate(all="ignore"):
            return pd.Series(np.log(c.to_numpy(dtype=float)), index=idx).diff()
    if name == "range":
        return h - lo
    if name == "body":
        return c - o
    if name == "typical":
        return (h + lo + c) / 3.0
    prev = c.shift(1)
    tr = pd.concat([h - lo, (h - prev).abs(), (lo - prev).abs()], axis=1).max(axis=1)
    if name == "tr":
        return tr
    atr: pd.Series = _desk()._atr(bars, 14)
    return atr.astype(float)


def _event_clock(node: EventClock, bars: pd.DataFrame, ex: Extras) -> pd.Series:
    idx = bars.index
    if not isinstance(idx, pd.DatetimeIndex) or not len(idx):
        return _nan(idx)
    sym = str(ex.symbol or "").upper()
    times: list[pd.Timestamp] = []
    for row in ex.calendar:
        if str(row.get("kind", "")) != node.kind:
            continue
        inst = row.get("instruments")
        if sym and isinstance(inst, (list, tuple)) and inst and sym not in {
                str(i).upper() for i in inst}:
            continue
        ts = pd.to_datetime(row.get("window_start_utc") or row.get("date"), utc=True,
                            errors="coerce")
        if ts is not pd.NaT and not pd.isna(ts):
            times.append(ts)
    if not times:
        return _nan(idx)
    span = pd.Series(idx).diff().dt.total_seconds().mode()
    step = float(span.iloc[0]) if len(span) and float(span.iloc[0]) > 0 else 3600.0
    ev = np.sort(np.asarray(pd.DatetimeIndex(times).view("int64"), dtype=np.float64)) / 1e9
    now = np.asarray(idx.view("int64"), dtype=np.float64) / 1e9
    if node.mode == "since":
        pos = np.searchsorted(ev, now, side="right") - 1
        out = np.where(pos >= 0, (now - ev[np.clip(pos, 0, ev.size - 1)]) / step, np.nan)
    else:
        pos = np.searchsorted(ev, now, side="left")
        out = np.where(pos < ev.size, (ev[np.clip(pos, 0, ev.size - 1)] - now) / step, np.nan)
    return pd.Series(out, index=idx, dtype=float)


def _state(node: State, bars: pd.DataFrame, ex: Extras) -> pd.Series:
    idx = bars.index
    n = len(idx)
    order = {s.name: i for i, s in enumerate(node.states)}
    values = np.asarray([s.value for s in node.states], dtype=float)
    masks: list[list[tuple[int, np.ndarray]]] = []
    for s in node.states:
        row: list[tuple[int, np.ndarray]] = []
        for t in s.transitions:
            m = _eval(t.when, bars, ex).to_numpy(dtype=float)
            row.append((order[t.to], np.nan_to_num(m, nan=0.0) > 0.5))
        masks.append(row)
    out = np.empty(n, dtype=float)
    cur = 0
    for i in range(n):
        for tgt, m in masks[cur]:
            if m[i]:
                cur = tgt
                break
        out[i] = values[cur]
    return pd.Series(out, index=idx, dtype=float)


def _rolling(op: str, s: pd.Series, w: int, lag: int = 0) -> pd.Series:
    if lag:
        s = s.shift(lag)
    r = s.rolling(w)
    if op == "zscore":
        sd = r.std()
        return (s - r.mean()) / sd.where(sd.abs() > 1e-12)
    if op == "rank":
        return r.rank(pct=True)
    out: pd.Series = getattr(r, op)()
    return out


def _eval(n: Node, bars: pd.DataFrame, ex: Extras) -> pd.Series:
    idx = bars.index
    if isinstance(n, Const):
        return pd.Series(float(n.value), index=idx, dtype=float)
    if isinstance(n, Slot):
        return pd.Series(_value(n, ex), index=idx, dtype=float)
    if isinstance(n, Series):
        return _terminal(bars, n.field)
    if isinstance(n, CrossRef):
        other = ex.cross.get(n.symbol)
        if other is None or not len(other):
            return _nan(idx)
        s = _terminal(other, n.field)
        return s.reindex(s.index.union(idx)).ffill().reindex(idx).astype(float)
    if isinstance(n, EventClock):
        return _event_clock(n, bars, ex)
    if isinstance(n, State):
        return _state(n, bars, ex)
    if isinstance(n, Rolling):
        lag = int(min(max(round(_value(n.lag, ex)), 0), MAX_WINDOW))
        return _rolling(n.op, _eval(n.child, bars, ex), _window(n.window, ex), lag)
    if isinstance(n, Adaptive):
        q = float(min(max(_value(n.q, ex), 0.001), 0.999))
        return _eval(n.child, bars, ex).rolling(_window(n.window, ex)).quantile(q)
    if isinstance(n, Cond):
        when = _eval(n.when, bars, ex)
        return _eval(n.then, bars, ex).where(when > 0, _eval(n.otherwise, bars, ex))
    a, b = _eval(n.left, bars, ex), _eval(n.right, bars, ex)
    if isinstance(n, Compare):
        cmps: dict[str, pd.Series] = {"gt": a > b, "ge": a >= b, "lt": a < b, "le": a <= b}
        return cmps[n.op].astype(float).where(a.notna() & b.notna())
    if n.op == "add":
        return a + b
    if n.op == "sub":
        return a - b
    if n.op == "mul":
        return a * b
    if n.op == "div":
        return a / b.where(b.abs() > 1e-12)
    frame = pd.concat([a, b], axis=1)
    return frame.max(axis=1) if n.op == "max2" else frame.min(axis=1)


def evaluate(tree: Node, bars: pd.DataFrame, extras: Extras | None = None) -> pd.Series:
    """Validate, then walk. Only the operations named above are ever called.

    The result is a float series on `bars.index`; NaN means "not computable here", which every
    consumer reads as no signal rather than as a zero.
    """
    errs = validate(tree)
    if errs:
        raise ProgramError("; ".join(errs))
    out = _eval(tree, bars, extras if extras is not None else Extras())
    return out.astype(float).replace([np.inf, -np.inf], np.nan)


def load_calendar(path: Path | None = None) -> list[dict[str, Any]]:
    """The forced-flow calendar's events, or [] with nothing claimed (L1.28a)."""
    try:
        raw = json.loads((path or CALENDAR_PATH).read_text("utf-8"))
    except (OSError, ValueError):
        return []
    events = raw.get("events") if isinstance(raw, dict) else raw
    return [e for e in events if isinstance(e, dict)] if isinstance(events, list) else []


# --------------------------------------------------------------------------- compilation
def compile_program(tree: Node, extras: Extras | None = None, tag: str = "program",
                    ) -> Callable[..., list[Any]]:
    """The tree as a family: `fn(bars, side=1, **slot_values) -> list[Signal]`.

    ENTRY IS THE NEXT OPEN, as the engine fills it, and only on an EDGE -- the bar where the
    program's sign changes into +1 or -1. A state machine that stays long for 300 bars is one
    trade, not 300 signals; emitting a signal per bar would hand the screen 300 overlapping
    copies of one decision and call the last 299 of them independent evidence.

    `side` is the POLARITY the program is traded at, exactly as `family_generic`'s DIRECTION axis
    is: +1 takes the program's own sign, -1 takes the opposite. Stops and targets are ATR
    multiples from the reserved execution slots, so the same threshold means the same thing on
    gold and on EURCHF.
    """
    errs = validate(tree)
    if errs:
        raise ProgramError("; ".join(errs))
    ex_base = extras if extras is not None else Extras()
    defaults = {s.name: s.default for s in exec_slots()}
    bounds = {s.name: (s.lo, s.hi) for s in exec_slots()}
    fp = fingerprint(tree)

    signal_cls = _signal()

    def run(bars: pd.DataFrame, side: int = 1, **slot_values: float) -> list[Any]:
        if bars is None or not len(bars) or "close" not in bars.columns:
            return []
        ex = Extras(slots={**dict(ex_base.slots), **{k: float(v) for k, v in slot_values.items()}},
                    cross=ex_base.cross, calendar=ex_base.calendar, symbol=ex_base.symbol)
        vals: dict[str, float] = {}
        for k, dflt in defaults.items():
            lo, hi = bounds[k]
            vals[k] = float(min(max(float(ex.slots.get(k, dflt)), lo), hi))
        raw = evaluate(tree, bars, ex).to_numpy(dtype=float)
        sgn = np.clip(np.sign(np.nan_to_num(raw, nan=0.0)), -1.0, 1.0)
        atr = _desk()._atr(bars, round(vals["atr_n"])).to_numpy(dtype=float)
        close = bars["close"].astype(float).to_numpy(dtype=float)
        idx = bars.index
        ttl = round(vals["ttl_bars"])
        out: list[Any] = []
        for i in range(1, len(idx) - 1):
            d = sgn[i]
            if d == 0.0 or d == sgn[i - 1]:
                continue
            a, px = atr[i], close[i]
            if not (np.isfinite(a) and a > 0 and np.isfinite(px)):
                continue
            s = int(d) * int(np.sign(side) or 1)
            stop_d = vals["stop_atr"] * a
            out.append(signal_cls(time=idx[i], side=s, stop=px - s * stop_d,
                              target=px + s * stop_d * vals["rr"], ttl_bars=ttl,
                              tag=f"{tag}:{fp}", trigger=None, wait_bars=1))
        return out

    return run


# --------------------------------------------------------------------------- description
def _win_str(w: Slot | int | float) -> str:
    return f"{w.name}[{w.lo:g}..{w.hi:g}]" if isinstance(w, Slot) else f"{w:g}"


_CMP = {"gt": ">", "ge": ">=", "lt": "<", "le": "<="}
_BIN = {"add": "+", "sub": "-", "mul": "*", "div": "/"}


def describe(tree: Node) -> str:
    """The rule in one line of English-ish arithmetic. What a reviewer reads instead of JSON."""
    if isinstance(tree, Const):
        return f"{tree.value:g}"
    if isinstance(tree, Series):
        return tree.field
    if isinstance(tree, Slot):
        return _win_str(tree)
    if isinstance(tree, CrossRef):
        return f"{tree.symbol}.{tree.field}"
    if isinstance(tree, EventClock):
        return f"bars_{tree.mode}({tree.kind})"
    if isinstance(tree, Rolling):
        tail = "" if tree.lag == 0 else f", lag={_win_str(tree.lag)}"
        return f"{tree.op}({describe(tree.child)}, {_win_str(tree.window)}{tail})"
    if isinstance(tree, Adaptive):
        return f"quantile({describe(tree.child)}, {_win_str(tree.window)}, q={_win_str(tree.q)})"
    if isinstance(tree, Compare):
        return f"({describe(tree.left)} {_CMP[tree.op]} {describe(tree.right)})"
    if isinstance(tree, Binary):
        if tree.op in _BIN:
            return f"({describe(tree.left)} {_BIN[tree.op]} {describe(tree.right)})"
        return f"{tree.op}({describe(tree.left)}, {describe(tree.right)})"
    if isinstance(tree, Cond):
        return (f"if {describe(tree.when)} then {describe(tree.then)} "
                f"else {describe(tree.otherwise)}")
    parts = []
    for s in tree.states:
        arcs = ", ".join(f"-{describe(t.when)}-> {t.to}" for t in s.transitions) or "terminal"
        parts.append(f"{s.name}={s.value}: {arcs}")
    return "state{" + "; ".join(parts) + "}"


# --------------------------------------------------------------------------- logic revision
def _count(tree: Node) -> int:
    return 1 + sum(_count(k) for k in _children(tree))


def _map_nth(n: Node, target: int, new: Node, ctr: list[int]) -> Node:
    here = ctr[0]
    ctr[0] += 1
    if here == target:
        return new
    kids = _children(n)
    return _rebuild(n, [_map_nth(k, target, new, ctr) for k in kids]) if kids else n


def _nth(n: Node, target: int, ctr: list[int]) -> Node | None:
    here = ctr[0]
    ctr[0] += 1
    if here == target:
        return n
    for k in _children(n):
        got = _nth(k, target, ctr)
        if got is not None:
            return got
    return None


def _rand_compare(rng: np.random.Generator) -> Compare:
    f = str(rng.choice(np.asarray(["close", "ret", "range", "tr", "body"])))
    w = int(rng.choice(np.asarray([8, 12, 24, 48, 120])))
    op = str(rng.choice(np.asarray(list(COMPARE_OPS))))
    return Compare(op, Series(f), Rolling("mean", Series(f), w))


def mutate_logic(tree: Node, rng: np.random.Generator, tries: int = 12,
                 grammar: Grammar | None = None) -> Node:
    """One STRUCTURAL edit: the mechanical half of what a seat's logic revision does by hand.

    D4 asks for logic revision to be SEPARATE from numeric tuning, and this is the separation
    made concrete: nothing here moves a slot's value -- it swaps a comparison, wraps a subtree in
    a branch, turns a rule into a state machine, changes an operator or re-aims a terminal. The
    optimiser tunes; this changes what is being tuned. A mutation that does not validate is
    discarded and the original returned, so a caller never receives an unrunnable program.
    """
    g = grammar if grammar is not None else active_grammar()
    n = _count(tree)
    for _ in range(max(1, tries)):
        k = int(rng.integers(0, n))
        node = _nth(tree, k, [0])
        if node is None:
            continue
        choice = str(rng.choice(np.asarray(["op", "compare", "wrap", "state", "field", "roll"])))
        new: Node | None = None
        if choice == "compare" and isinstance(node, Compare):
            new = replace(node, op=str(rng.choice(np.asarray(list(g.compare_ops)))))
        elif choice == "op" and isinstance(node, Binary):
            new = replace(node, op=str(rng.choice(np.asarray(list(g.binary_ops)))))
        elif choice == "roll" and isinstance(node, Rolling):
            new = replace(node, op=str(rng.choice(np.asarray(list(g.rolling_ops)))))
        elif choice == "field" and isinstance(node, Series):
            new = replace(node, field=str(rng.choice(np.asarray(list(FIELDS[:8])))))
        elif choice == "wrap":
            new = Cond(_rand_compare(rng), node, Const(0.0))
        elif choice == "state" and g.state_machines:
            c1, c2 = _rand_compare(rng), _rand_compare(rng)
            new = State((StateDef("flat", 0, (Transition("engaged", c1),)),
                         StateDef("engaged", 1, (Transition("flat", c2),))))
        if new is None:
            continue
        cand = _map_nth(tree, k, new, [0])
        if not validate(cand):
            return cand
    return tree

```

### scripts\backfill_live_ledger_r.py
```python
"""Backfill the R multiple on live-ledger rows written while the writer floored it at zero.

THE ZERO THAT JUDGED EVERY SLEEVE (measured 2026-09-16). `mt5desk.decision_core.closed_trade_r`
took `is_buy` from the CLOSING deal, whose type is the opposite of the position's, so the signed
stop distance came out negative, was floored at zero, and every row the desk had ever written
carried `r_multiple: 0.0` -- 141 of 151 rows on the trading box -- with entry, stop, volume and
contract size all present on the row. The writer is fixed (the distance is |entry - stop|); the
rows it wrote before the fix still read zero, and every organ that learns from realised R
(credit_assignment, posterior_alpha, hazard_engine, standing_questions Q5, the scorecard's
attribution row) reads them as evidence of no edge. This recomputes R for exactly those rows
from the numbers already on them, marks each one `r_backfilled` with its basis, and touches
nothing else.

THE BASIS IS STATED, NOT HIDDEN. The row carries the contract size but not the venue's tick
value, so risk is distance x contract_size x volume in the QUOTE currency while P&L is in the
account currency; the ratio is exact when the two coincide (EUR-quoted symbols on this EUR
account) and off by the quote/account rate otherwise -- a few percent, labelled, against a zero
that was wrong by everything. A row without entry, stop or volume stays unreconstructible.

    python scripts/backfill_live_ledger_r.py [--ledger PATH] [--apply]
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
LEDGER = ROOT / "desks" / "mt5" / "data" / "live_ledger.jsonl"


def recompute(row: dict[str, Any]) -> tuple[float | None, str]:
    """(r_multiple, basis) for a row whose R was floored, or (None, why) when it cannot be."""
    try:
        entry = float(row.get("entry_price") or 0.0)
        sl = float(row.get("sl") or 0.0)
        vol = float(row.get("volume") or 0.0)
        contract = float(row.get("contract_size") or 0.0)
        pl = float(row.get("pl_quote") or 0.0)
    except (TypeError, ValueError):
        return None, "non-numeric fields"
    if entry <= 0 or sl <= 0:
        return None, "entry or stop absent: unreconstructible"
    dist = abs(entry - sl)
    if dist <= 0 or vol <= 0 or contract <= 0:
        return None, "zero distance, volume or contract size"
    risk = dist * contract * vol
    return pl / risk, "backfill: |entry-stop| x contract_size x volume (quote ccy) vs account P&L"


def backfill(rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, int]]:
    out: list[dict[str, Any]] = []
    counts = {"rows": len(rows), "backfilled": 0, "kept": 0, "unreconstructible": 0}
    for r in rows:
        if not isinstance(r, dict):
            out.append(r)
            continue
        rm = r.get("r_multiple")
        floored = isinstance(rm, (int, float)) and float(rm) == 0.0 and not r.get("r_backfilled")
        if not floored or r.get("r_unreconstructible"):
            counts["kept"] += 1
            out.append(r)
            continue
        val, basis = recompute(r)
        if val is None:
            counts["unreconstructible"] += 1
            out.append({**r, "r_unreconstructible": True, "r_backfill_why": basis})
            continue
        counts["backfilled"] += 1
        out.append({**r, "r_multiple": round(val, 4), "r_backfilled": True, "r_basis": basis,
                    "r_multiple_before": rm})
    return out, counts


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--ledger", default=str(LEDGER))
    ap.add_argument("--apply", action="store_true", help="rewrite the ledger in place (atomic)")
    a = ap.parse_args(argv)
    p = Path(a.ledger)
    if not p.exists():
        print(f"backfill: {p} absent; nothing to do")
        return 0
    rows: list[Any] = []
    for ln in p.read_text(encoding="utf-8", errors="replace").splitlines():
        if not ln.strip():
            continue
        try:
            rows.append(json.loads(ln))
        except ValueError:
            rows.append({"_unparsed": ln})
    new, counts = backfill([r for r in rows if isinstance(r, dict) and "_unparsed" not in r])
    print(f"backfill: {counts['rows']} row(s): {counts['backfilled']} backfilled, "
          f"{counts['kept']} kept, {counts['unreconstructible']} unreconstructible"
          f"{'' if a.apply else ' (dry run -- pass --apply)'}")
    if a.apply and counts["backfilled"]:
        tmp = p.with_suffix(".jsonl.tmp")
        with tmp.open("w", encoding="utf-8") as f:
            for r in rows:
                if isinstance(r, dict) and "_unparsed" in r:
                    f.write(r["_unparsed"] + "\n")
            for r in new:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
        os.replace(tmp, p)
        print(f"-> {p}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

```

### scripts\build_audit_coverage.py
```python
#!/usr/bin/env python3
"""FULL-COVERAGE AUDIT FEED (principal exception to the doctrine freeze, 2026-07-20).

PROBLEM THIS SOLVES: the external panel used to see ONLY docs/EXTERNAL_PANEL_DOSSIER.md --
11KB of prose curated by the very system being audited, against ~44k lines of real code.
The auditee chose the auditor's evidence, so nothing outside the dossier could ever be
flagged, and most of the codebase had never been examined by anyone but its author.

WHAT THIS DOES: every panel run now also carries
  (A) the RAW, UNFILTERED git diff since the previous panel run -- curation-proof, and
  (B) a rotating slice of the LEAST-RECENTLY-AUDITED source files, in full, and
  (C) the coverage manifest itself, so models can see what is stale or never-audited and
      call out the blind spots directly.
A per-file ledger (data/audit_coverage.json) records who saw what and when, so "full
coverage" becomes a measurable property with staleness floors rather than an aspiration.

SAFETY: data/secrets/** and anything key/credential-shaped is excluded by path BEFORE
reading, and the assembled payload is run through the desk's own sanitize() before it is
ever returned. stdlib-only.
"""
from __future__ import annotations

import json
import subprocess
from collections.abc import Iterable
from datetime import UTC, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MANIFEST = ROOT / "data/audit_coverage.json"

# what the sweep covers -- code + operator contracts (the brain's prompt lives in ops/*.sh)
INCLUDE_GLOBS = ("scripts/*.py", "libs/**/*.py", "ops/*.sh", "ops/*.txt",
                 "tests/**/*.py", "docs/*.md", "docs/research/*.md", "docs/playbooks/*.md")
# never read, never send
EXCLUDE_PARTS = ("secrets", "__pycache__", ".venv", ".git", "node_modules")
EXCLUDE_SUFFIX = (".bak", ".pyc", ".log")

# RISK-class (money path) files are audited on a tighter clock than everything else
# `scripts/run_cashcarry` and `scripts/run_recorder.py` were dropped 2026-09-05: those scripts
# were deleted with the retired universe, and this is a PREFIX list whose job is to say which code
# gets the tighter clock -- a prefix matching nothing quietly overstates the money path's size.
# desks/mt5/mt5desk/ replaces them: that is where an execution defect now costs real money.
RISK_PREFIXES = ("libs/execution/", "scripts/run_deadman_switch.py",
                 "scripts/run_alerts.py", "scripts/run_ci.py",
                 "desks/mt5/mt5desk/")
RISK_MAX_AGE_D = 14.0
ROTATE_MAX_AGE_D = 30.0

# CLASS 'ALWAYS' = the DECISION surface: what a reviewer must see to give SPECIFIC advice rather
# than generic advice ("add these 3 grounds to the JP miner" vs "consider more breadth").
# Ships IN FULL on every run, exempt from the rotating budget, re-audited every run.
ALWAYS_PREFIXES = (
    "ops/frontier_", "ops/prospector_dig_prompt", "ops/litminer_dig_prompt",
    "ops/dataaxis_dig_prompt", "ops/blindrediscovery_dig_prompt",
    "docs/research/data_axis_watchlist.md", "docs/research/prospector_coverage.md",
    "docs/research/improvement_inbox.md", "docs/research/search_operator_library.md",
    "docs/research/weak_signal_registry.md", "docs/research/discovery_hypotheses.md",
    "docs/research/negative_knowledge.md", "docs/research/canary_searches.md",
    "docs/research/prospector_watchlist.md", "docs/research/generation_due.md",
    "docs/research/HYPOTHESIS_MAX_SPEC.md", "docs/research/video_locked_log.md",
    "docs/GAP_REGISTER.md", "docs/DIGGING_CHARTER.md",
)

# how much source to ship per run. ~200k chars ~= 50k tokens; x13 seats ~= <$1/run.
CODE_BUDGET_CHARS = 2_400_000    # TOTAL payload ceiling = the WHOLE system
                                 # (2.29MB); adaptation still finds the safe level
                                 # empirically, so this is a ceiling not a target
CODE_BUDGET_MIN = 40_000         # floor for the ROTATING part; tier-0 always ships
DIFF_BUDGET_CHARS = 60_000
QUORUM_FRAC = 0.6                # >=60% of seats must answer substantively to count
SUBSTANTIVE_CHARS = 400          # shorter than this is not a real review


def _review_class(rel: str) -> int:
    if any(rel.startswith(p) for p in ALWAYS_PREFIXES):
        return 0                                   # decision surface: always sent
    return 1 if any(rel.startswith(p) for p in RISK_PREFIXES) else 2


def _eligible() -> list[Path]:
    out: list[Path] = []
    for g in INCLUDE_GLOBS:
        for p in ROOT.glob(g):
            if not p.is_file():
                continue
            rel = p.relative_to(ROOT).as_posix()
            if any(x in rel for x in EXCLUDE_PARTS):
                continue
            if p.suffix in EXCLUDE_SUFFIX or ".bak-" in rel:
                continue
            out.append(p)
    return sorted(set(out))


def load() -> dict:
    if MANIFEST.exists():
        try:
            return json.loads(MANIFEST.read_text("utf-8"))
        except Exception:
            pass
    return {"files": {}, "last_panel_sha": None, "runs": 0}


def save(m: dict) -> None:
    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST.write_text(json.dumps(m, indent=1), "utf-8")


def refresh(m: dict) -> dict:
    """Sync the manifest with what actually exists on disk (new files appear as never-audited)."""
    files = m.setdefault("files", {})
    seen = set()
    for p in _eligible():
        rel = p.relative_to(ROOT).as_posix()
        seen.add(rel)
        rec = files.setdefault(rel, {"last_audited": None, "audit_count": 0})
        try:
            # CLOSE THE HANDLE (2026-08-12). `sum(1 for _ in p.open(...))` never closed the file:
            # CPython's refcount reaps it, but it emits a ResourceWarning first, and this repo
            # sets filterwarnings = error. So EVERY test that transitively reached refresh() --
            # i.e. every test of record_blank, tune_budget or audit_payload, and therefore every
            # test of the panel's own failure path, which calls record_blank per dead seat --
            # failed on the warning rather than on the behaviour. The R0343 total-failure fixture
            # was the first thing to need that path and the first thing to hit this. A leak that
            # makes a code path untestable costs more than the descriptors.
            with p.open("r", encoding="utf-8", errors="ignore") as fh:
                rec["loc"] = sum(1 for _ in fh)
        except Exception:
            rec["loc"] = 0
        rec["review_class"] = _review_class(rel)
    for gone in [k for k in files if k not in seen]:
        files.pop(gone)          # deleted files leave the ledger; git keeps the history
    return m


def _age_days(iso: str | None) -> float:
    if not iso:
        return 1e9                                    # never audited = infinitely stale
    try:
        return (datetime.now(tz=UTC) - datetime.fromisoformat(iso)).total_seconds() / 86400
    except Exception:
        return 1e9


def _git(*args: str) -> str:
    try:
        return subprocess.run(["git", *args], cwd=ROOT, capture_output=True,
                              text=True, timeout=30).stdout
    except Exception:
        return ""


def status(m: dict) -> dict:
    files = m["files"]
    never = [f for f, r in files.items() if not r.get("last_audited")]
    stale1 = [f for f, r in files.items()
              if r.get("review_class") == 1 and _age_days(r.get("last_audited")) > RISK_MAX_AGE_D]
    stale2 = [f for f, r in files.items()
              if r.get("review_class") == 2 and _age_days(r.get("last_audited")) > ROTATE_MAX_AGE_D]
    t0 = [f for f, r in files.items() if r.get("review_class") == 0]
    return {"total": len(files), "never": never, "stale_risk": stale1, "stale_rotate": stale2,
            "always_class": len(t0),
            "covered": len(files) - len(never),
            "pct": round(100.0 * (len(files) - len(never)) / max(1, len(files)), 1)}


def current_budget(m: dict) -> int:
    """Largest payload every seat has survived recently (learned, not guessed)."""
    return int(m.get("code_budget_chars", CODE_BUDGET_CHARS))


def tune_budget(blanked: int, total: int) -> int:
    """Shrink hard on any blank, grow gently on a clean run. Called after every panel.

    THE WELD THIS NOW REPORTS (measured 2026-08-12). The budget sat at exactly CODE_BUDGET_MIN
    while the last eight recorded firings carried 2-4 blanks of 4 -- `max(40_000, int(40_000 *
    0.6))` is 40_000, so the shrink arm moved NOTHING, eight times, and the history rendered
    `from 40000 to 40000` with no hint that a bound had been hit. A control that fires and
    changes nothing is a welded gate (L1.43), and this one is the mechanistic reason the same
    free seats blank forever: they fail on a 40k payload, the adaptive response that exists to
    shrink it cannot, and the tally records the blanks while the budget records success.

    NOTHING IS LOOSENED HERE. The floor is not lowered and neither arm is re-rated -- lowering a
    floor to clear the violation it caught is the failure this desk has paid for repeatedly. The
    fix is that "the budget adapted" and "the budget COULD NOT adapt" stop being byte-identical
    in the record, which is the only way anyone can argue about whether the floor is right.
    Whether these seats need a smaller tier or the floor needs re-deriving is a payload-design
    decision with an owner; this makes it visible, it does not take it.
    """
    m = refresh(load())
    cur = current_budget(m)
    if blanked:
        new = max(CODE_BUDGET_MIN, int(cur * 0.6))   # a blank is a real failure: cut deep
        bound = "floor" if new >= cur else None
    else:
        new = min(CODE_BUDGET_CHARS, int(cur * 1.15))  # earn size back slowly
        bound = "ceiling" if new <= cur else None
    m["code_budget_chars"] = new
    m.setdefault("budget_history", []).append(
        {"blanked": blanked, "of": total, "from": cur, "to": new,
         # Present ONLY when the arm was inert, so a reader scanning the history sees the weld
         # rather than having to re-derive it from two equal numbers.
         **({"welded_at": bound, "wanted": int(cur * 0.6) if blanked else int(cur * 1.15)}
            if bound else {})})
    m["budget_history"] = m["budget_history"][-30:]
    save(m)
    return new


#: Timestamped blanks kept beside the lifetime tally. Bounded so the ledger cannot grow without
#: limit; 400 covers months of panel runs at this desk's cadence and the window queries only ever
#: look back days.
_BLANK_EVENT_CAP = 400


def recent_blanks(m: dict[str, object], *, window_days: int) -> dict[str, int] | None:
    """Blanks per seat inside `window_days`, or ``None`` when recency cannot be measured.

    ``None`` IS THE LOAD-BEARING RETURN AND MUST NOT COLLAPSE INTO AN EMPTY DICT. Until the
    event log has been written to, a seat with a lifetime tally has NO recency evidence at all,
    and `{}` would read as "zero recent blanks -- the seat is fine", quietly clearing a fence on
    a box where nothing has been measured. That is absence resolving to a clean verdict, this
    desk's most-repeated defect class. A caller that gets ``None`` must say UNMEASURED.
    """
    events = m.get("seat_blank_events")
    if not isinstance(events, list) or not events:
        return None
    cutoff = datetime.now(tz=UTC) - timedelta(days=window_days)
    out: dict[str, int] = {}
    for e in events:
        if not isinstance(e, dict):
            continue  # attrition-ok: a malformed row carries no timestamp to place in a window
        try:
            when = datetime.fromisoformat(str(e.get("ts", "")))
        except ValueError:
            continue  # attrition-ok: same -- an unparseable stamp is not evidence of recency
        if when >= cutoff:
            model = str(e.get("model", "?"))
            out[model] = out.get(model, 0) + 1
    return out


#: Attempts are kept as a per-seat, per-DAY tally rather than one event per call: attempts
#: outnumber blanks by ~2 orders of magnitude, and a capped event list would evict the oldest
#: attempts first -- shrinking exactly the denominator this exists to protect. Days retained; the
#: window queries only ever look back `SEAT_BLANK_WINDOW_DAYS`.
_ATTEMPT_DAY_CAP = 30


def record_blanks(models: Iterable[str]) -> None:
    """Every blank from ONE panel run, in ONE read-modify-write. NEVER call this per-thread.

    WHAT THE TALLY IS FOR, AND WHY THE EVENTS SIT BESIDE IT. `seat_blanks` is a LIFETIME counter
    that nothing anywhere resets or decays, so a seat that blanked three times months ago and has
    answered every call since is permanently indistinguishable from one dying right now. The fence
    keyed on it (`seat-chronic-*`) therefore fired forever once a seat crossed the threshold, and
    its recommendation is to SWAP -- which costs a live seat off an under-driven roster. The tally
    is KEPT and keeps incrementing (`check_free_roster` and `model_upgrade` read it, and it is
    honest as history); the timestamped events are what let a reader ask "is this seat failing
    NOW" instead of only "has it ever failed".

    THE RACE THIS CLOSES, AND IT HAD ALREADY EATEN 87% OF THE TALLY. `record_blank` was called
    from inside `run_external_panel._one`, which runs under a ThreadPoolExecutor(max_workers=5),
    and every call does load() -> mutate -> save() on one shared JSON. Concurrent seats therefore
    read the same state and overwrite each other, and with 3-4 of 4 seats blanking together the
    losses are not occasional -- they are the common case.

    MEASURED 2026-08-13, and the two counters settle it because they shipped in the SAME commit
    (14131c33, 2026-07-20) and have watched the SAME 28 runs: `tune_budget` runs ONCE, AFTER the
    fan-out, and recorded 70 blanks of 148 seat-calls. `seat_blanks`, incremented inside the
    threads, sums to 9. Same events, same window, 87% lost. Age cannot explain it; only the race
    can. The old path also double-counted the retry branch (record_blank, then raise, then
    record_blank again in the handler), so the surviving 9 were not even a clean sample.

    The blanked set is derivable SERIALLY from the results the executor returns -- a result
    without a "response" key is a lost seat -- so nothing is gained by writing from the threads.
    """
    m = refresh(load())
    tally = m.setdefault("seat_blanks", {})
    events = m.setdefault("seat_blank_events", [])
    now = datetime.now(tz=UTC).isoformat()
    for model in models:
        tally[model] = int(tally.get(model, 0)) + 1
        events.append({"model": model, "ts": now})
    m["seat_blank_events"] = events[-_BLANK_EVENT_CAP:]
    save(m)


def record_blank(model: str) -> None:
    """One blank. Kept as the single-seat spelling of `record_blanks`."""
    record_blanks([model])


def record_attempts(models: Iterable[str]) -> None:
    """Every seat asked in ONE panel run, in ONE read-modify-write. THE DENOMINATOR (R0570).

    "Blanked 4x" is not a measurement. Four failures out of four calls is a dead seat; four out of
    four hundred is a 1% flake on a free tier, and until now nothing counted the calls, so the two
    were byte-identical to every reader -- L1.57's missing denominator, one subsystem over from
    where it was written.

    IT ALSO UN-WELDS THE FENCE, which is the half that bites today. `seat-chronic-*-unmeasured`
    can currently only clear when a seat BLANKS AGAIN: with no events, recency is unmeasured and
    the defect fires forever, so the fence is lit precisely while the seats are healthy and goes
    quiet only on new failure. That is the inverted-gate class R0492 named, reappearing one level
    up in the instrument built to fix it. An attempt is recorded whether the seat succeeds or
    fails, so health becomes measurable from success -- the only direction that can honestly
    clear it.

    ATTEMPTS ARE THEIR OWN EPOCH, which is why no separate "instrumented since" stamp is needed:
    an attempt recorded at T proves the instrumentation was live at T, so attempts inside the
    window with no blank events inside the window means zero blanks, MEASURED -- not unknown.
    """
    m = refresh(load())
    today = datetime.now(tz=UTC).date()
    att = m.setdefault("seat_attempts", {})
    if not isinstance(att, dict):
        att = m["seat_attempts"] = {}
    for model in models:
        per = att.setdefault(model, {})
        per[today.isoformat()] = int(per.get(today.isoformat(), 0)) + 1
    cutoff = (today - timedelta(days=_ATTEMPT_DAY_CAP)).isoformat()
    for mdl in list(att):
        kept = {d: c for d, c in (att[mdl] or {}).items() if d >= cutoff}
        if kept:
            att[mdl] = kept
        else:
            del att[mdl]
    save(m)


def recent_attempts(m: dict[str, object], *, window_days: int) -> dict[str, int] | None:
    """Calls per seat inside `window_days`, or ``None`` when nothing has been recorded.

    ``None`` rather than ``{}`` for the same reason `recent_blanks` returns it: a box that has
    never counted an attempt has no rate evidence, and zero-attempts would read as a 0/0 rate that
    a caller could round to "fine".
    """
    att = m.get("seat_attempts")
    if not isinstance(att, dict) or not att:
        return None
    cutoff = (datetime.now(tz=UTC).date() - timedelta(days=window_days)).isoformat()
    out: dict[str, int] = {}
    for model, days in att.items():
        if not isinstance(days, dict):
            continue  # attrition-ok: a malformed seat block carries no dated counts to window
        n = sum(int(c) for d, c in days.items() if str(d) >= cutoff)
        if n:
            out[str(model)] = n
    return out or None


def blank_rate(m: dict[str, object], *, window_days: int) -> dict[str, tuple[int, int]] | None:
    """{seat: (blanks, attempts)} inside the window, or ``None`` when attempts are unrecorded.

    Keyed on ATTEMPTS, never on blanks: a seat that answered every call in the window has no blank
    events at all, and that is the healthy case the caller most needs to be able to see.
    """
    attempts = recent_attempts(m, window_days=window_days)
    if attempts is None:
        return None
    blanks = recent_blanks(m, window_days=window_days) or {}
    return {seat: (blanks.get(seat, 0), n) for seat, n in attempts.items()}


def audit_payload() -> tuple[str, list[str]]:
    """Return (text_to_append_to_dossier, files_included). Sanitized, budget-bounded."""
    m = refresh(load())
    files = m["files"]
    st = status(m)

    # (A) raw diff since the previous panel run -- the curation-proof part
    sha = m.get("last_panel_sha")
    diff = _git("diff", f"{sha}..HEAD") if sha else _git("log", "-p", "--since=3.days")
    if len(diff) > DIFF_BUDGET_CHARS:
        diff = diff[:DIFF_BUDGET_CHARS] + "\n... [diff truncated at budget -- ask for the rest]"

    # (B0) ALWAYS-class decision surface -- ALWAYS, IN FULL, budget-exempt. This is what lets a
    # reviewer say "add these grounds to the KR miner" instead of "consider more breadth".
    t0_chunks, t0_files, t0_used = [], [], 0
    for rel, _rec in sorted(files.items()):
        if _rec.get("review_class") != 0:
            continue
        fp = ROOT / rel
        if not fp.exists():
            continue
        try:
            body = fp.read_text("utf-8", errors="ignore")
        except Exception:
            continue
        t0_chunks.append(f"\n----- [DECISION SURFACE] {rel} "
                         f"({len(body.splitlines())} lines) -----\n{body}")
        t0_files.append(rel)
        t0_used += len(body)

    # (B) rotating slice: risk-path staleness first, then oldest-audited, then largest
    order = sorted(((k, v) for k, v in files.items() if v.get("review_class") != 0),
                   key=lambda kv: (kv[1].get("review_class", 2),
                                   -_age_days(kv[1].get("last_audited")),
                                   -kv[1].get("loc", 0)))
    chunks, included, used = [], [], 0
    for rel, _rec in order:
        p = ROOT / rel
        if not p.exists():
            continue
        try:
            body = p.read_text("utf-8", errors="ignore")
        except Exception:
            continue
        if used + len(body) > max(0, current_budget(m) - t0_used) and included:
            break
        _la = _rec.get('last_audited') or 'NEVER'
        chunks.append(f"\n----- FILE: {rel} ({len(body.splitlines())} lines, "
                      f"class={_review_class(rel)}, last audited: {_la}) "
                      f"-----\n{body}")
        included.append(rel)
        used += len(body)

    txt = [
        "\n\n" + "=" * 70,
        "## FULL-COVERAGE AUDIT FEED (raw system access -- judge ALL of it)",
        "=" * 70,
        "The prose dossier above is written BY the system being audited. Everything below is "
        "raw and uncurated, so you can flag what the dossier omits. You are explicitly asked "
        "to judge the CODE, not just the narrative: correctness, risk-path safety, silent-"
        "failure modes, dead code, unsafe defaults, and anything the author would not have "
        "thought to summarize.",
        f"\n### COVERAGE STATE: {st['covered']}/{st['total']} files ever audited "
        f"({st['pct']}%). NEVER audited: {len(st['never'])}. "
        f"Stale risk-path (>{RISK_MAX_AGE_D:.0f}d): {len(st['stale_risk'])}. "
        f"Stale other (>{ROTATE_MAX_AGE_D:.0f}d): {len(st['stale_rotate'])}.",
        "If a file you would need to judge a claim is NOT included below, say so explicitly -- "
        "'I could not verify X because file Y was not provided' is a first-class finding here.",
        f"\n### (A) RAW DIFF SINCE LAST PANEL ({'since ' + sha[:8] if sha else 'last 3 days'})\n",
        "```diff\n" + (diff.strip() or "(no changes)") + "\n```",
        f"\n### (B0) DECISION SURFACE [review class: ALWAYS] -- ALWAYS SENT IN FULL "
        f"({len(t0_files)} files, "
        f"{t0_used:,} chars): every miner/digger prompt, every watchlist, coverage map, "
        "operator library, hypothesis + weak-signal + negative-knowledge registries, gap "
        "register and digging charter. You are seeing 100% of what the desk uses to DECIDE. "
        "Your recommendations here must be SPECIFIC (name the prompt, name the ground, name "
        "the operator) -- generic advice is a failed review.\n",
        "```\n" + "".join(t0_chunks) + "\n```",
        f"\n### (B) ROTATING SOURCE REVIEW ({len(included)} files, {used:,} chars, "
        "least-recently-audited first; the rest is under staleness floors)\n",
        "```\n" + "".join(chunks) + "\n```",
    ]
    payload = "\n".join(txt)

    try:                                              # desk sanitizer is the last gate
        from scripts.generate_external_review_doc import sanitize
        clean = sanitize(payload)
        if clean != payload:
            print("coverage: sanitizer redacted secret-shaped content before send")
        payload = clean
    except Exception as e:
        print(f"coverage: sanitize unavailable ({e!r}) -- sending nothing rather than risk it")
        return "", []
    return payload, t0_files + included


def mark_audited(files: list[str], ts: str, mission: str,
                 substantive: int = 0, total_seats: int = 0) -> None:
    """Mark files reviewed ONLY on quorum. Coverage must reflect what was actually READ,
    not what was sent -- a run where seats blanked must not inflate the coverage figure."""
    if total_seats and substantive < max(1, int(QUORUM_FRAC * total_seats)):
        m = refresh(load())
        m.setdefault("failed_runs", []).append(
            {"ts": ts, "mission": mission, "substantive": substantive,
             "of": total_seats, "files_not_credited": len(files)})
        m["failed_runs"] = m["failed_runs"][-20:]
        save(m)
        print(f"coverage: QUORUM FAILED ({substantive}/{total_seats} substantive) -- "
              f"{len(files)} files NOT credited as audited")
        return
    m = refresh(load())
    for rel in files:
        rec = m["files"].get(rel)
        if rec is not None:
            rec["last_audited"] = ts
            rec["audit_count"] = int(rec.get("audit_count", 0)) + 1
            rec["last_mission"] = mission
    m["last_panel_sha"] = (_git("rev-parse", "HEAD").strip() or m.get("last_panel_sha"))
    m["runs"] = int(m.get("runs", 0)) + 1
    save(m)


def main() -> None:
    import sys
    m = refresh(load())
    save(m)
    st = status(m)
    if len(sys.argv) > 1 and sys.argv[1] == "verify":
        print(f"adaptive payload budget : {current_budget(m):,} chars "
              f"(ceiling {CODE_BUDGET_CHARS:,}, floor {CODE_BUDGET_MIN:,})")
        print(f"seat blanks recorded    : {m.get('seat_blanks', {}) or 'none'}")
        print(f"quorum-failed runs      : {len(m.get('failed_runs', []))}")
        for h in m.get("budget_history", [])[-5:]:
            print(f"  budget {h['from']:,} -> {h['to']:,} (blanked {h['blanked']}/{h['of']})")

    print(f"AUDIT COVERAGE: {st['covered']}/{st['total']} files ever audited ({st['pct']}%)")
    print(f"  never audited      : {len(st['never'])}")
    print(f"  stale RISK (money path): {len(st['stale_risk'])} (floor {RISK_MAX_AGE_D:.0f}d)")
    print(f"  stale ROTATE (long tail): {len(st['stale_rotate'])} (floor {ROTATE_MAX_AGE_D:.0f}d)")
    print(f"  TIER-0 always-sent : {st['always_class']} decision-surface files (100% every run)")
    total_loc = sum(r.get("loc", 0) for r in m["files"].values())
    runs_needed = max(1, round(total_loc * 40 / CODE_BUDGET_CHARS))
    print(f"  total LOC in sweep : {total_loc:,}  (~{runs_needed} panel runs per full sweep)")
    for f in sorted(st["never"])[:10]:
        print(f"    NEVER: {f}")


if __name__ == "__main__":
    main()

```

### scripts\check_campaign_retention.py
```python
#!/usr/bin/env python3
"""CAMPAIGN RETENTION FENCE (R0270; L1.0 ratchet, L2.0 fence, L1.28a unmeasured-is-not-OK).

THE GAP THIS CLOSES. `libs/autodiscovery/orchestrator.py` writes a `campaign_strata` audit row
every campaign carrying how much of the desk's data the campaign actually tested on. Until now the
sole repo reference to `campaign_strata` was that writer: NOTHING READ IT. History length is the
binding constraint on discovery power here, so a silent return to min-length truncation would
restore an 82.9% discard of the observations on disk with no alarm anywhere.

WHAT IT FIRES ON, and the second one is the sharp one:
  * REGRESSED  -- retained observation share fell below its recorded floor (L1.0: floors only rise)
  * FALLBACK   -- `plan_strata` truncated to min-length because nothing cleared its floors. It is
                  CORRECT behaviour that must never become the steady state, and it degrades
                  QUIETLY by design. Note the direction: the fallback drives n_untested DOWN to
                  zero, so a fence watching only for untested RISING would read this regression as
                  the campaign becoming more inclusive.
  * STALE      -- the newest row is older than two campaign cadences (the factory is daily)
  * ABSENT     -- no campaign has ever recorded a plan. NOT the same defect as STALE or REGRESSED
                  (L1.55): they send you to different organs.
  * UNMEASURED -- no audit store could be discovered at all. Never a pass (L1.28a).

TWO CAMPAIGN POPULATIONS WRITE `campaign_strata`, AND THIS FENCE WAS READING THE WRONG ONE (R0435).
It judged the newest row across EVERY audit store. The daily crypto factory writes to
`sor_crypto` (k=32, 85.8% retention, 36.7% untested); the research lake writes ~90 rows a day to
`sor_research` (k=1, 100% retention, 0% untested by construction). The lake therefore won every
`ORDER BY created_at DESC LIMIT 1`, so the quantity R0270 built this fence to floor became
structurally unreadable, and the factory's SEVEN-DAY silence was reported as a 23h-old healthy
plan at 100% retention. Every individual read was honest; the SUBJECT changed underneath them
(L1.61). The subject is now named in code (`SUBJECT_DB`) and each population is reported
separately.

UNTESTED SHARE IS MEASURED AND PUBLISHED BUT STILL NOT FENCED, and the reason got sharper rather
than weaker. R0270 asked for a fire on "n_untested rises materially". First the direction: the
fallback drives untested to ZERO, so a rising-only check would miss the sharp failure entirely and
read it as the campaign becoming more inclusive. Second the band, where R0435 recorded "one
campaign shape on record" and the count has since gone to 95 -- which looks like the blocker
clearing and is not. 92 of those 95 are lake plans whose untested share is 0.0 BY CONSTRUCTION, so
a POOLED standard deviation measures the mix of two campaign types and not the drift of either: a
constant wearing a measurement's clothes (L1.55), welded in both directions at once (L1.43). The
stats are therefore computed PER POPULATION and published every run with an explicit
CALIBRATABLE / UNMEASURED-BAND / DEGENERATE verdict, so the band gets wired from evidence the day
the evidence exists. Measured 2026-08-13: subject 3/10 campaigns, lake degenerate at 92.

WHAT IT DOES NOT DO. It judges no candidate, promotes nothing, sizes nothing and touches no
statistical bar. Retention is a MEASUREMENT of how much data the campaign used; this fence only
asserts that the number never falls and is never fabricated. Anti-timidity reading (L1.28): it can
only ever push the desk to test on MORE of its own data, never less.

    python scripts/check_campaign_retention.py [--report-only] [--json]
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
from libs.ops.fence_exit import fence_exit  # noqa: E402
from libs.ops.lawful import guard as _law_guard  # noqa: E402
from libs.research.campaign_retention import (  # noqa: E402
    MIN_CAMPAIGNS_FOR_BAND,
    SUBJECT_DB,
    Reading,
    audit_dbs,
    series_by_db,
    untested_stats,
)

_OUT = _ROOT / "data" / "campaign_retention.json"
_FLOORS = _ROOT / "data" / "ratchet_floors.json"
#: The crypto factory runs daily (01:30). Two cadences of grace, so one missed night is not a
#: page and two consecutive misses are -- the same convention the other daily ratchets use.
MAX_AGE_H = 48.0
_METRIC = "campaign_obs_retained"
_PASSING = frozenset({"OK", "NO-FLOOR"})


def _floor(root: Path | None = None) -> float | None:
    """The recorded retention floor, or None if this metric has never been floored.

    Read from the committed ratchet artifact rather than kept here, so there is ONE floor with one
    provenance and `check_ratchets --ratchet` remains the only thing that can move it -- upward.
    """
    path = (root or _ROOT) / "data" / "ratchet_floors.json"
    try:
        doc = json.loads(path.read_text("utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    entry = doc.get(_METRIC) if isinstance(doc, dict) else None
    if isinstance(entry, dict) and isinstance(entry.get("value"), (int, float)):
        return float(entry["value"])
    return None


def _age_h(created_at: str) -> float | None:
    try:
        t = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return None
    if t.tzinfo is None:
        t = t.replace(tzinfo=UTC)
    return (datetime.now(tz=UTC) - t).total_seconds() / 3600.0


def _verdict(rd: Reading | None, n_dbs: int, n_rows: int, floor: float | None,
             *, subject_best: float | None = None, n_malformed: int = 0) -> tuple[str, str, str]:
    """(status, why, next_action) -- the whole judgement, in one place, from arguments in hand.

    `rd` IS THE SUBJECT'S NEWEST PLAN, NOT THE DESK'S (R0435). It used to be whatever store wrote
    last, and the desk runs two campaign populations under one event name, so the research lake's
    ~90 rows a day permanently outbid the daily crypto factory this fence was built to floor.
    `subject_best` is the highest retention the subject population has EVER recorded; a floor above
    it cannot have been measured on this subject and therefore cannot judge it.
    """
    if n_dbs == 0:
        return ("UNMEASURED",
                "no sqlite store carrying an audit_log table was found under data/ -- this fence "
                "examined NOTHING, which is not evidence that campaigns are healthy",
                "repair scope discovery in libs.research.campaign_retention.audit_dbs")
    if rd is None:
        # THREE DIFFERENT CAUSES, KEPT APART (L1.55) -- they send you to three different organs:
        # the subject wrote rows this fence cannot parse; the subject wrote nothing while another
        # population did; nobody wrote anything at all. Collapsing them is how a reader debugs a
        # schema change when the real event is that a cron stopped.
        if n_malformed:
            detail = (f"{n_malformed} of {n_rows} campaign_strata row(s) carried none of the "
                      "fields this fence judges -- a malformed row is never read past to a "
                      "greener one underneath")
        elif n_rows:
            detail = (f"{n_rows} campaign_strata row(s) found across {n_dbs} store(s) but none in "
                      f"{SUBJECT_DB}, the store this fence floors. Another population's campaigns "
                      "are not evidence about this one -- the subject's plan is unrecorded, so "
                      "its retention is unknowable, which is not healthy")
        else:
            detail = (f"no campaign has ever written a campaign_strata row across {n_dbs} audit "
                      "store(s). The plan is unrecorded, so retention is unknowable -- not "
                      "healthy")
        return ("ABSENT", detail,
                "run the campaign (ops/run_crypto_factory.sh) and confirm the orchestrator's "
                "audit append fires")

    frac = rd.retained_fraction
    untested = rd.untested_fraction
    age = _age_h(rd.created_at)
    head = (f"campaign {rd.campaign_id[:16]} in {rd.db}: {rd.obs_retained:,}/"
            f"{rd.obs_available:,} observations "
            f"({'n/a' if frac is None else f'{frac:.1%}'}) across k={rd.k_strata} strata, "
            f"{rd.n_tested}/{rd.n_candidates} candidates tested")

    # FALLBACK FIRST. It is a statement about the planner's own state, so it outranks the numeric
    # comparisons -- and its retention collapse would otherwise be reported as a plain regression,
    # sending the reader to look for a data problem instead of a floors problem.
    if rd.is_fallback:
        return ("FALLBACK",
                f"{head} -- plan_strata TRUNCATED TO MIN-LENGTH: nothing cleared its floors, so "
                "the campaign is a single underpowered stratum over every candidate. Correct "
                "behaviour, never a steady state; a null result from this campaign is not "
                "evidence about the space. Note n_untested went to 0, which reads as inclusive",
                "find why no stratum cleared MIN_COHORT=12/MIN_OBS=250 -- generation shape or a "
                "collapsed length distribution upstream")
    if frac is None:
        return ("ABSENT",
                f"{head} -- obs_available is 0, so retention has no denominator and any "
                "percentage computed from it would be an opinion (L1.57)",
                "check the campaign's series preparation: zero available observations means the "
                "data provider returned nothing")
    # STALE MOVED AHEAD OF THE NUMERIC COMPARISONS (R0435). A subject that has not run cannot have
    # regressed, and reporting its last plan's number as the finding sends the reader to audit a
    # length distribution when the actual event is that no campaign happened. Measured 2026-08-13:
    # the crypto factory's newest plan was 7.1 DAYS old while this fence read a 23h-old research
    # lake row and reported OK -- the one condition STALE exists to catch, invisible to it.
    if age is not None and age > MAX_AGE_H:
        return ("STALE",
                f"{head} -- newest plan for {SUBJECT_DB} is {age:.1f}h old, past {MAX_AGE_H:.0f}h "
                "(two daily cadences). A frozen artifact steers decisions exactly as a live one "
                "does, and no campaign means no discovery, not a healthy campaign",
                "check the crypto factory cron (01:30 daily) and its lock file")
    if rd.structurally_single_stratum and floor is not None and frac + 1e-9 < floor:
        return ("FALLBACK",
                f"{head} -- one stratum holding every candidate AND retention {frac:.1%} below "
                f"the {floor:.1%} floor. The planner did not label it, but that is the shape and "
                "the cost of the min-length fallback",
                "confirm against plan_strata's floors; if this is a legitimate single stratum, "
                "the retention regression still stands on its own")
    if floor is None:
        return ("NO-FLOOR",
                f"{head} -- measured, but no floor is recorded for {_METRIC}. A number without a "
                "floor cannot regress, so it is not yet fenced",
                "python scripts/check_ratchets.py --ratchet   (records the floor; never lowers)")
    # A FLOOR THE SUBJECT HAS NEVER REACHED WAS NOT MEASURED ON THE SUBJECT (R0435, L1.55). This is
    # a MEASUREMENT, not an opinion: the floor is compared against the best retention this
    # population has EVER recorded, so it fires only when the recorded value is unreachable here.
    # Measured 2026-08-13: floor 100.0% recorded 2026-08-06T07:07Z from a research-lake k=1 plan
    # that retains everything by construction, against a subject whose best run is 99.96%. Without
    # this, re-pointing the fence at its real subject would publish REGRESSED -- a true-sounding
    # verdict with the wrong cause, sending the reader to audit a length distribution that is fine.
    # THE REPAIR IS UPWARD AND IS NOT TAKEN HERE: the floor is not lowered, it is re-recorded
    # against a declared subject by the one command allowed to move it.
    if subject_best is not None and floor > subject_best + 1e-9:
        return ("FLOOR-MIS-SUBJECTED",
                f"{head} -- the recorded {_METRIC} floor {floor:.1%} is above the BEST retention "
                f"{SUBJECT_DB} has ever recorded ({subject_best:.1%}), so it cannot have been "
                "measured on this subject and cannot judge it. Two campaign populations write "
                "campaign_strata; the floor came from the other one",
                "re-record the floor against the declared subject: "
                "python scripts/check_ratchets.py --ratchet   (never lower it by hand)")
    if frac + 1e-9 < floor:
        return ("REGRESSED",
                f"{head} -- retention {frac:.1%} is BELOW the recorded floor {floor:.1%}. "
                "Observations on disk that no test ran on are edge already paid for and declined",
                "compare this campaign's length distribution against the floored run; floors only "
                "rise, so this is repaired upstream and never by lowering the floor")
    unt = "" if untested is None else f", {untested:.1%} of candidates untested (measured, "
    unt += "" if untested is None else "not fenced -- see the module docstring and R0435)"
    return ("OK",
            f"{head}; retention {frac:.1%} at or above the {floor:.1%} floor"
            + (f", plan {age:.1f}h old" if age is not None else "") + unt,
            "none")


def _population(name: str, readings: list[Reading]) -> dict[str, Any]:
    """One campaign population, with the untested-share calibration inputs R0435 asked for."""
    st = untested_stats(readings)
    newest = readings[-1] if readings else None
    return {
        "db": name,
        "is_subject": name == SUBJECT_DB,
        "n_campaigns": len(readings),
        "newest_at": None if newest is None else newest.created_at,
        "newest_retained_fraction": None if newest is None else newest.retained_fraction,
        "newest_k_strata": None if newest is None else newest.k_strata,
        "best_retained_fraction": max(
            (r.retained_fraction for r in readings if r.retained_fraction is not None),
            default=None),
        "untested_n": st.n,
        "untested_mean": None if st.mean is None else round(st.mean, 6),
        "untested_sd": None if st.sd is None else round(st.sd, 6),
        "untested_band_verdict": st.verdict,
        "untested_band_wired": False,
    }


def build(root: Path | None = None) -> dict[str, Any]:
    by_db, n_dbs, n_rows, n_malformed = series_by_db(root)
    pops = [_population(name, by_db[name]) for name in sorted(by_db)]
    subject = by_db.get(SUBJECT_DB, [])
    rd = subject[-1] if subject else None
    subject_best = max((r.retained_fraction for r in subject
                        if r.retained_fraction is not None), default=None)
    floor = _floor(root)
    status, why, nxt = _verdict(rd, n_dbs, n_rows, floor, subject_best=subject_best,
                                n_malformed=n_malformed)
    calibratable = [p for p in pops if p["untested_band_verdict"].startswith("CALIBRATABLE")]
    return {
        "generated": datetime.now(tz=UTC).isoformat(),
        "law": "L1.0 universal ratchet / L2.0 fence -- campaign observation-retention is a "
               "measured metric whose floor only rises; R0270. Judged per POPULATION (R0435).",
        "status": status,
        "subject_db": SUBJECT_DB,
        "subject_best_retained_fraction": subject_best,
        # PUBLISHED INDEPENDENTLY OF THE STATUS LADDER, because a ladder reports the FIRST true
        # thing and this fence now has two at once (L1.60): the subject is 7 days silent AND its
        # floor was recorded from the other population. STALE outranks -- a subject that has not
        # run cannot have regressed -- and if that were the only place the mis-subjecting appeared,
        # resolving the staleness would surface it as a surprise REGRESSED on a healthy campaign.
        "floor_mis_subjected": bool(
            floor is not None and subject_best is not None and floor > subject_best + 1e-9),
        # R0435: the band is NOT wired, and the artifact says why in the same breath it publishes
        # the inputs. Pooling the two populations would set a tolerance from a mix of campaign
        # TYPES rather than the drift of either -- a fabricated constant (L1.55) welded in both
        # directions (L1.43). Per population, the bar is R0435's own: >=10 campaigns AND real
        # variance. Stated in OBSERVATIONS, never in days (L1.48).
        "untested_band": {
            "wired": False,
            "min_campaigns": MIN_CAMPAIGNS_FOR_BAND,
            "pooling_refused": "92 of 95 recorded campaigns are research-lake plans whose "
                               "untested share is 0.0 BY CONSTRUCTION (k=1 over everyone); a "
                               "pooled sd measures the population mix, not campaign drift",
            "n_populations_calibratable": len(calibratable),
            "next_action": "when a population reads CALIBRATABLE, set a TWO-SIDED band at a "
                           "multiple of its own sd and wire it as a status in _verdict. Two-sided "
                           "because the min-length fallback drives untested DOWN to zero, so a "
                           "rising-only check reads the sharp regression as inclusiveness",
        },
        "n_malformed_rows": n_malformed,
        "populations": pops,
        "n_audit_dbs": n_dbs,
        "n_rows_seen": n_rows,
        "floor": floor,
        "max_age_h": MAX_AGE_H,
        "retained_fraction": None if rd is None else rd.retained_fraction,
        "untested_fraction": None if rd is None else rd.untested_fraction,
        "k_strata": None if rd is None else rd.k_strata,
        "campaign": None if rd is None else {
            "db": rd.db, "campaign_id": rd.campaign_id, "created_at": rd.created_at,
            "age_h": None if _age_h(rd.created_at) is None else round(_age_h(rd.created_at), 1),
            "n_candidates": rd.n_candidates, "n_tested": rd.n_tested,
            "n_untested": rd.n_untested, "obs_retained": rd.obs_retained,
            "obs_available": rd.obs_available, "strata_alpha": rd.strata_alpha,
            "outcome": rd.outcome,
        },
        "detail": why,
        "next_action": nxt,
        "proving_command": "python scripts/check_campaign_retention.py",
    }


def main() -> int:
    _law_guard()
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--report-only", action="store_true",
                    help="write the artifact and always exit 0")
    ap.add_argument("--json", action="store_true", help="print the artifact")
    args = ap.parse_args()

    rep = build()
    _OUT.parent.mkdir(parents=True, exist_ok=True)
    _OUT.write_text(json.dumps(rep, indent=2), "utf-8")

    if args.json:
        print(json.dumps(rep, indent=2))
    else:
        frac = rep["retained_fraction"]
        flr = rep["floor"]
        print(f"campaign retention (R0270): {rep['status']} -- "
              f"{'n/a' if frac is None else f'{frac:.1%}'} retained "
              f"(floor {'none' if flr is None else f'{flr:.1%}'}), "
              f"{rep['n_rows_seen']} row(s) across {rep['n_audit_dbs']} audit store(s)")
        print(f"  {rep['detail']}")
        print(f"  next: {rep['next_action']}")

    if args.report_only:
        return 0
    # Subject to L1.57: the denominator is how many audit stores this run actually discovered, so
    # a scope discovery that finds nothing refuses its own pass instead of reporting a clean board.
    return fence_exit(rep["status"], _PASSING, scanned=len(audit_dbs()),
                      of="data/*.sqlite audit stores", fence="check_campaign_retention.py")


if __name__ == "__main__":
    raise SystemExit(main())

```

### scripts\check_coverage_floors.py
```python
#!/usr/bin/env python3
"""COVERAGE FLOORS, RATCHETED -- and the money path carries its own.

WHY THIS EXISTS. `pytest-cov` has been a declared dev dependency and `[tool.coverage.run]` has
carried `branch = true` for as long as either has existed, and NOTHING EVER RAN THEM. CI invoked
bare `pytest`. The only `.coverage` file on disk was from a single hand-run six days earlier. So
the desk had coverage tooling installed, configured, and unmeasured -- the same built-but-never-
runs class as an order book recorded for weeks and never screened.

Measured for the first time on 2026-08-04: 88.1% repo-wide. That number is not the finding.

THE SHAPE IS THE FINDING, AND IT INVERTS THE RISK. The least-covered substantial code in the
repository is the code that can place orders and move funds:

    binance_live.py          29.9%   <- the LIVE order path, worst in the repo
    binance_spot_testnet.py  22.1%
    binance_spot_live.py     40.9%
    binance_testnet.py       40.5%
    ------------------------------
    money path combined      41.6%   against 88.1% everywhere else

That is backwards from where the care should be. A bug in a research script costs a wasted cycle;
a bug on the order path walks a short through zero into a +916,772 long, which is not hypothetical
-- it is in `_market_max_qty`'s docstring, and a defect in that exact function was found on
2026-08-04 sitting in the seventy percent nobody tests.

TWO FLOORS, NOT ONE. A single repo-wide number lets money-path coverage fall while a wave of
research tests keeps the aggregate up -- the average hides precisely the thing worth watching. So
the money path is measured separately and ratcheted separately.

RATCHET, NEVER A TARGET. Floors only rise. `--update` raises them to what was just measured;
nothing lowers them but a human editing the record with a reason, which is the same discipline
docs/research/LAW_COVERAGE.json applies to constitutional enforcement.

Reads a coverage JSON report. Writes the ratchet record. Exits 1 if a floor is breached.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

RECORD = ROOT / "docs/research/COVERAGE_RATCHET.json"

#: The files that can PLACE ORDERS or MOVE FUNDS. Kept explicit rather than globbed: a new venue
#: adapter must be added here deliberately, because the alternative is a money-path file that
#: silently escapes the floor by not matching a pattern.
#:
#: POINTED AT THE LIVE UNIVERSE 2026-08-29 (gap-fixer). Until this edit all five entries were
#: `libs/execution/binance_*` -- the RETIRED crypto adapters, which LAWS §1 forbids ever running
#: again. So the number every session read at the top of its context, "money path 89.44%", was
#: measured entirely over code that can never execute, while `desks/mt5/mt5desk/gateway.py`
#: (1510 lines, FOUR `mt5.order_send` call sites, `close_positions`, `manage_open_positions`)
#: and `libs/execution/broker.py` (`place_order`/`cancel_order`) were in no floor at all.
#: The explicit-not-globbed reasoning above was right and still is; what nobody did was update
#: the list when the principal changed the universe on 2026-08-18. A guard aimed at retired
#: ground reads healthy forever -- the WS-005 class, on the money path.
MONEY_PATH = (
    "libs/execution/broker.py",
    "libs/execution/staging.py",
)

#: LIVE money path that CANNOT BE EXECUTED ON THIS HOST, path -> the structural reason.
#:
#: These are reported as UNMEASURABLE by name every run and are NEVER folded into the
#: percentage (L1.28a: unmeasured is a real answer, and it must not render as either a pass or
#: a zero). They are also not a breach: a fence that is red from day one with no action that
#: could ever clear it gets ignored and then deleted (L1.43), and an unclosable red is how a
#: real one stops being read. The verdict is "unmeasurable HERE", which names the host where it
#: could be measured -- that is a build request, not a failure.
MONEY_PATH_UNMEASURABLE_HERE = {
    "desks/mt5/mt5desk/gateway.py": (
        "imports MetaTrader5 at module scope and that package is Windows-only, so no line of it "
        "executes on this Linux box. The desk's own tests know: desks/mt5/tests/test_risk_units.py "
        "does `_SRC = (_DESK / 'mt5desk' / 'gateway.py').read_text()` and AST-extracts the pure "
        "helpers, commenting 'gateway.py imports MetaTrader5'. That is a sound adaptation and the "
        "tests are real, but it means STATEMENT coverage of the live order path is 0% here and "
        "structurally so. Measurable only on the Windows terminal host."
    ),
}

#: RETIRED universe (LAWS §1, principal 2026-08-18/2026-08-25). Kept, never deleted: its
#: high-water mark is a real ratchet the desk earned and deleting the population would be the
#: denominator trick. Measured and reported SEPARATELY so a healthy retired number can never
#: stand in for the live one again -- which is exactly what it had been doing.
MONEY_PATH_RETIRED = (
    "libs/execution/binance_live.py",
    "libs/execution/binance_testnet.py",
    "libs/execution/binance_spot_live.py",
    "libs/execution/binance_spot_testnet.py",
)

#: Slack below the measured high-water mark, in percentage points. Coverage moves a little with
#: test ordering and optional-dependency skips, and a floor that fires on noise gets deleted --
#: which is worse than a floor set one point low.
SLACK = 1.0

#: L1.50. Past this many days with no floor RAISED, the ratchet is reported as STALLED.
#:
#: Not an evidence gate, so L1.48 does not apply: this measures ELAPSED NEGLECT, not accumulated
#: proof, and there is no observation whose arrival would make a stalled ratchet acceptable. 14 days
#: is two full weekly cycles -- long enough that one busy week reads as normal, short enough that a
#: quarter cannot pass unremarked.
STALL_DAYS = 14.0


def days_since(iso: str | None) -> float | None:
    """Days since an ISO timestamp, or None if absent/unparseable.

    None means NOT MEASURED and must never be rendered as 0.0 (L1.28a). A record written before
    L1.50 has no `last_raised`, and a missing timestamp that read as "raised today" would give the
    oldest, most-stalled records the healthiest possible reading -- the exact inversion GAP #83
    found in `register_health`, where a register never driven once scored perfect.
    """
    if not iso:
        return None
    try:
        then = datetime.fromisoformat(str(iso))
    except (TypeError, ValueError):
        return None
    if then.tzinfo is None:  # naive compares wrong against every aware stamp
        return None
    return max(0.0, (datetime.now(tz=UTC) - then).total_seconds() / 86400.0)


def stall_report(rec: dict[str, Any]) -> str:
    """L1.50: a floor that has not risen is a ratchet that has stopped.

    REPORTS, NEVER FAILS. A check that exits non-zero on a quiet day gets deleted, and a deleted
    check enforces nothing -- the same reasoning behind SLACK. Regression is CI's business;
    stagnation is the auditor's. A desk that cannot tell "you regressed" from "you stopped
    improving" ends up told neither.
    """
    age = days_since(rec.get("last_raised"))
    if age is None:
        return (
            "  L1.50 STALL: this record has never recorded a raise. That is not a clean "
            "reading -- it is an absent one, and the two must not look alike."
        )
    if age >= STALL_DAYS:
        return (
            f"  L1.50 STALL: no floor has RISEN in {age:.0f} days. The floors are holding, "
            "which is the minimum, not the target. 100% is the target; the gap below is the "
            "distance to it."
        )
    return f"  L1.50: last raise {age:.1f}d ago -- ratchet moving."


def gap_to_target(now: dict[str, Any]) -> str:
    """Distance to 100%, printed every run. A floor is a MINIMUM; the target is the ceiling, and
    reporting only the floor lets a permanently-green desk read as a finished one."""
    # NEVER CLAIM COMPLETENESS OVER A PARTIAL POPULATION (gap-fixer 2026-08-29). At 100% of the
    # measurable files this printed "~0 uncovered statements on the code that can move funds"
    # while `desks/mt5/mt5desk/gateway.py` -- 1510 lines and four `mt5.order_send` call sites --
    # sat in MONEY_PATH_UNMEASURABLE_HERE, executed by nothing. A gap-to-target that silently
    # omits the biggest order-placing file in the repo is the same false green this whole
    # module was just repointed to stop telling.
    unmeasurable = sorted(MONEY_PATH_UNMEASURABLE_HERE)
    tail = (
        f" -- and {len(unmeasurable)} live money-path file(s) are NOT in that count at all "
        f"({', '.join(unmeasurable)}): unmeasurable on this host, so the true remaining gap is "
        "strictly larger than the number above and is UNKNOWN, not zero"
        if unmeasurable
        else ""
    )
    return (
        f"  to 100%: repo needs +{100.0 - now['repo_pct']:.2f}pp, "
        f"money path +{100.0 - now['money_path_pct']:.2f}pp "
        f"(~{round((100.0 - now['money_path_pct']) / 100.0 * now['money_path_statements'])} "
        f"uncovered statements on the measurable part of the code that can move funds){tail}"
    )


def measure(report: dict[str, Any]) -> dict[str, Any]:
    """(repo %, money-path %) from a coverage.py JSON report."""
    raw_files = report.get("files", {})
    files = (
        {str(path).replace("\\", "/"): details for path, details in raw_files.items()}
        if isinstance(raw_files, dict)
        else {}
    )
    stmts = covered = 0
    attempted = 0
    missing: list[str] = []
    for rel in MONEY_PATH:
        # EVERY DISCARD IS COUNTED (L2.4/L1.60). `attempted` is incremented BEFORE the guard, and
        # an absent module is NAMED rather than skipped. The bug this closes: a money-path file
        # that stops appearing in the report -- renamed, its test file deleted, or the run dying
        # before it imports -- used to leave the numerator AND the denominator, so money_path_pct
        # ROSE while a fifth of the order path went dark, and the L1.50 ratchet then locked that
        # inflated floor in permanently. The denominator has to say how many it lost.
        attempted += 1
        s = files.get(rel, {}).get("summary")
        if not s:
            missing.append(rel)
            continue
        stmts += int(s["num_statements"])
        covered += int(s["covered_lines"])
    # The RETIRED population, measured on its own so its (earned, real) number can never be
    # printed as though it described the live order path.
    r_stmts = r_covered = 0
    r_missing: list[str] = []
    for rel in MONEY_PATH_RETIRED:
        s = files.get(rel, {}).get("summary")
        if not s:
            r_missing.append(rel)
            continue
        r_stmts += int(s["num_statements"])
        r_covered += int(s["covered_lines"])

    return {
        "repo_pct": round(float(report["totals"]["percent_covered"]), 2),
        "money_path_pct": round(100.0 * covered / stmts, 2) if stmts else 0.0,
        "money_path_statements": stmts,
        "money_path_attempted": attempted,
        "money_path_measured": attempted - len(missing),
        "money_path_missing": missing,
        "money_path_unmeasurable_here": sorted(MONEY_PATH_UNMEASURABLE_HERE),
        "money_path_retired_pct": (
            round(100.0 * r_covered / r_stmts, 2) if r_stmts else None
        ),
        "money_path_retired_statements": r_stmts,
        "money_path_retired_missing": r_missing,
    }


def load_record() -> dict[str, Any]:
    try:
        return dict(json.loads(RECORD.read_text("utf-8")))
    except (OSError, json.JSONDecodeError):
        return {}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--report", default="coverage.json", help="coverage.py JSON report")
    ap.add_argument(
        "--update",
        action="store_true",
        help="RAISE the floors to what was just measured (never lowers)",
    )
    a = ap.parse_args()

    p = Path(a.report)
    if not p.is_absolute():
        p = ROOT / p
    try:
        report = json.loads(p.read_text("utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        print(
            f"coverage-floors: cannot read {a.report} ({type(e).__name__}). Run pytest with "
            "--cov=libs --cov-branch --cov-report=json:coverage.json first."
        )
        return 1

    now = measure(report)
    rec = load_record()
    floors = dict(rec.get("high_water", {}))
    repo_floor = float(floors.get("repo_pct", 0.0))
    money_floor = float(floors.get("money_path_pct", 0.0))

    print(
        f"coverage-floors: repo {now['repo_pct']}% (floor {repo_floor}%) | "
        f"money path {now['money_path_pct']}% over {now['money_path_statements']} stmts "
        f"(floor {money_floor}%)"
    )
    # SAID EVERY RUN, NEVER FOLDED INTO THE PERCENTAGE. A live money-path file the host cannot
    # execute is UNMEASURED, and unmeasured must not render as a pass or as a zero (L1.28a).
    for rel in now["money_path_unmeasurable_here"]:
        print(f"  UNMEASURABLE HERE: {rel} -- {MONEY_PATH_UNMEASURABLE_HERE[rel]}")
    if now["money_path_retired_pct"] is not None:
        print(
            f"  retired (LAWS §1, cannot execute): {now['money_path_retired_pct']}% over "
            f"{now['money_path_retired_statements']} stmts -- reported apart from the live "
            "figure on purpose; until 2026-08-29 this WAS the figure"
        )
    print(gap_to_target(now))
    print(stall_report(rec))

    # A FLOOR IS ONLY COMPARABLE AGAINST THE POPULATION THAT EARNED IT (gap-fixer 2026-08-29).
    # This is the general form of the bug found today: MONEY_PATH was changed by the principal's
    # universe order on 2026-08-18 in every sense except the list, and nothing anywhere compared
    # the list the floor was earned over against the list being measured. Silently comparing a
    # NEW population to an OLD floor is meaningless in both directions -- it invents a breach if
    # the new set is younger, and it certifies a pass if the new set is easier. Neither is a
    # measurement. So: detect the change, refuse to treat the inherited floor as binding, and
    # make the migration an explicit act with the old population recorded beside its number.
    recorded_pop = list(rec.get("money_path_files", []))
    population_changed = bool(recorded_pop) and recorded_pop != list(MONEY_PATH)
    if population_changed:
        gone = [f for f in recorded_pop if f not in MONEY_PATH]
        added = [f for f in MONEY_PATH if f not in recorded_pop]
        print(
            f"  POPULATION CHANGED: the {money_floor}% floor was earned over "
            f"{len(recorded_pop)} file(s), this run measured {len(MONEY_PATH)}. "
            f"Left: {', '.join(gone) or 'none'}. Joined: {', '.join(added) or 'none'}. "
            "The inherited floor is NOT binding on a different population and is not being "
            "compared; --update migrates it, preserving the old number with the files that "
            "earned it. Nothing is lowered -- the old floor keeps its own key."
        )

    breaches = []
    if now["money_path_missing"]:
        # A SHRINKING DENOMINATOR IS NOT AN IMPROVEMENT (L1.60). Absent modules leave both sides
        # of the ratio, so the percentage RISES as the money path goes dark. Refuse the reading
        # outright rather than compare a subset against a floor earned by the whole set.
        breaches.append(
            f"MONEY PATH UNMEASURED: {len(now['money_path_missing'])} of "
            f"{now['money_path_attempted']} module(s) absent from the coverage report "
            f"({', '.join(now['money_path_missing'])}). The {now['money_path_pct']}% above is "
            "over the SURVIVORS only -- an absent module leaves numerator and denominator "
            "together, so this number rises as the order path goes dark. Run pytest over the "
            "whole tree, or fix the path in MONEY_PATH if a module moved."
        )
    if now["repo_pct"] < repo_floor - SLACK:
        breaches.append(f"repo coverage {now['repo_pct']}% fell below its {repo_floor}% mark")
    if not population_changed and now["money_path_pct"] < money_floor - SLACK:
        breaches.append(
            f"MONEY PATH coverage {now['money_path_pct']}% fell below its {money_floor}% mark -- "
            "this is the code that places orders, and it is the one number a repo-wide average "
            "would have hidden"
        )

    if a.update and now["money_path_missing"]:
        # The ratchet is permanent, so a floor raised from a partial measurement is a permanent
        # error. Refuse to write rather than lock in a number earned by a smaller money path.
        print("  REFUSING --update: the money-path measurement is missing "
              f"{len(now['money_path_missing'])} module(s); a floor raised from a shrinking "
              "denominator can never be lowered again (L1.50/L1.60)")
        return 1

    if a.update:
        floors["repo_pct"] = max(repo_floor, now["repo_pct"])
        if population_changed:
            # PRESERVE, THEN ESTABLISH. The old number is archived beside the exact files that
            # earned it -- deleting it would be the denominator trick -- and the new population
            # is floored on its FIRST measurement (L2.0), which is what a first measurement is
            # for. `max()` across populations is the one thing that must not happen: it would
            # pin an unrelated set to a bar it never ran against.
            floors["superseded_money_path"] = {
                "pct": money_floor,
                "files": recorded_pop,
                "retired_on": datetime.now(tz=UTC).isoformat(),
                "why": (
                    "LAWS §1 (principal 2026-08-18/25) retired this universe; these files cannot "
                    "execute again, so their coverage cannot describe the live order path."
                ),
            }
            floors["money_path_pct"] = now["money_path_pct"]
        else:
            floors["money_path_pct"] = max(money_floor, now["money_path_pct"])
        # L1.50: `last_raised` moves ONLY when a floor actually rose. Stamping it on every
        # --update would make running the updater look identical to improving coverage, which is
        # GAP #85's error exactly -- an `n` that counts READINGS OF THE WORLD rather than events
        # in it, so diligence in running the audit becomes the mechanism by which it goes wrong.
        # A MIGRATION IS NOT A RAISE. Stamping `last_raised` because a new population happened
        # to measure higher than the old one would restart the L1.50 stall clock on an
        # accounting change -- the ratchet would read as "moving" while nothing improved.
        rose = (floors["repo_pct"] > repo_floor) or (
            not population_changed and floors["money_path_pct"] > money_floor
        )
        last_raised = datetime.now(tz=UTC).isoformat() if rose else rec.get("last_raised")
        RECORD.write_text(
            json.dumps(
                {
                    "_": (
                        "HIGH-WATER MARKS for test coverage. Raised by --update, NEVER lowered by code. "
                        "The money path is tracked separately because a repo-wide average lets order-"
                        "path coverage fall while research tests keep the aggregate up -- the average "
                        "hides exactly the number worth watching."
                    ),
                    "updated": datetime.now(tz=UTC).isoformat(),
                    "last_raised": last_raised,
                    "high_water": floors,
                    "measured": now,
                    "money_path_files": list(MONEY_PATH),
                    "slack_pp": SLACK,
                    "next_ceiling": (
                        "STILL money-path parity, and the gap is still the point. 41.6% -> 70.45% "
                        "(2026-08-06) against 92.46% repo-wide: the direction is right and the inversion "
                        "is not fixed. ~221 uncovered statements remain on the code that can place orders "
                        "and move funds, and the three defects found writing those tests -- a flatten leg "
                        "that could sell through zero, and GAP #49 wired into only one leg of a two-leg "
                        "trade -- were all in the untested part, which is the whole argument. Parity is "
                        "not the end either: the ceiling after it is the FAILURE branches specifically, "
                        "since every incident this desk has had came from an error path, not a happy one. "
                        "Per L1.50 the floor is the minimum and 100% is the target; the residue above is "
                        "named so it cannot be mistaken for work already done."
                    ),
                },
                indent=1,
            ),
            "utf-8",
        )
        print(
            f"  floors updated -> repo {floors['repo_pct']}% | "
            f"money path {floors['money_path_pct']}%"
            + ("  (RAISED)" if rose else "  (no raise -- last_raised unchanged)")
        )
        return 0

    if breaches:
        for b in breaches:
            print(f"  BREACH: {b}")
        print("  Floors ratchet. Restore the coverage, or edit the record by hand with a reason.")
        return 1
    print("  both floors held")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

```

### scripts\check_utilisation.py
```python
"""UTILISATION FENCE (L1.28a) -- every ceiling this desk owns, measured against its limit.

THE LAW: unused headroom is not safety, it is an unbooked loss. Capital, forward-confirmation
slots, model quota, data already paid for, built capability, scheduler cadence -- each is utilised
to its limit at all times, and idle headroom anywhere is a defect of the same class as a missed
edge.

WHY IDLENESS IS THE MOST EXPENSIVE FAILURE AVAILABLE, and why it needs a fence rather than an
intention: a wrong trade costs a bounded amount and announces itself. Idle capacity costs its
ENTIRE forward output stream and announces nothing. An unfilled forward slot is evidence that will
never be accrued. An unread dataset is a hypothesis never tested. A dormant module is engineering
already paid for returning zero forever. An idle dollar is compounding that never starts. None of
it appears in any P&L, and none of it generates an error -- which is exactly why it persists.

THE RULE THIS ENFORCES: every ceiling declares a LIMIT, carries a MEASURED utilisation, and where
utilisation is short of the limit, names the BINDING CONSTRAINT with a resolution path. Two design
choices follow from the law and both are deliberate:

  * UNMEASURED COUNTS AS ZERO. A ceiling nobody measures is idle by default and nobody would know.
    Treating "no measurement" as "probably fine" is how every one of these gaps survived.
  * A BINDING CONSTRAINT MUST BE NAMED, not implied. "Running at 60% and that seems fine" is a
    defect; "60%, bound by an unfunded OpenRouter key, re-test on funding" is a decision. The
    difference is whether anyone can act on it.

THE ONLY LEGITIMATE IDLE HEADROOM is a survival rail (L1.23 -- drawdown buffer, ruin margin,
Tier-3 reserve) or a named external blocker on the register with a re-test date.

    python scripts/check_utilisation.py [--json] [--report-only]
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
from libs.ops.fence_exit import fence_exit  # noqa: E402

_OUT = _ROOT / "data/utilisation.json"
_LOGS = _ROOT / "data/cro_ai_logs"

#: Below this fraction of the limit, idle headroom must be explained by a named binding constraint.
_EXPECT = 0.90


@dataclass
class Ceiling:
    name: str
    limit: float
    used: float
    unit: str
    measured: bool
    binding_constraint: str      # "" = none named; required when utilisation < _EXPECT
    why_it_matters: str
    #: Live composition of the reading -- the numbers behind `used`, not a static explanation.
    #: Separate from `binding_constraint` ON PURPOSE: writing the diagnosis there would name a
    #: constraint, which flips IDLE-UNEXPLAINED to IDLE-EXPLAINED and silences the fence. A
    #: shortfall the desk caused itself is exactly what must stay UNEXPLAINED (L1.28a: the only
    #: legitimate idle headroom is a survival rail or an EXTERNAL blocker on the register).
    detail: str = ""

    @property
    def utilisation(self) -> float:
        if not self.measured:
            return 0.0           # unmeasured counts as zero -- see module docstring
        return 0.0 if self.limit <= 0 else min(self.used / self.limit, 1.0)

    @property
    def status(self) -> str:
        if not self.measured:
            return "UNMEASURED"
        # OVER-LIMIT IS A MEASUREMENT DEFECT, NOT SATURATION, and clamping it to 100% is how it
        # hides. First run of this fence read deployed capital at $13,155 against $4,500 equity
        # and displayed a comfortable "SATURATED 100%". Either the two numbers come from different
        # sources, or the book is levered and the ceiling is wrong. Both need a human, and neither
        # is the healthy state the clamp implied. A ceiling you cannot trust is worse than one you
        # know is idle: it reports success while measuring nothing.
        if self.limit > 0 and self.used > self.limit * 1.02:
            return "OVER-LIMIT"
        if self.utilisation >= _EXPECT:
            return "SATURATED"
        return "IDLE-EXPLAINED" if self.binding_constraint else "IDLE-UNEXPLAINED"


def _forward_slots() -> Ceiling:
    """The single most load-bearing ceiling on the desk's only path from research to capital.

    OCCUPANCY IS NOT UTILISATION, and this counted the wrong thing. `used` was
    `len(snap["slots"])` -- a head-count of slots that are TAKEN. But a forward slot exists to
    accrue evidence, and `derive_slots()` already publishes which of them actually are:
    `accruing` against `not_accruing`, the latter documented in the registry's own note as "the
    slots paying multiplicity while returning no evidence". A dormant clock is the worst reading
    available -- it consumes cohort capacity, charges every other candidate's Holm bar, and
    returns nothing -- and counting it as utilised capacity made it indistinguishable from a
    healthy one. Measured when this was fixed: 12 slots occupied, 11 accruing, `cny_premium` at
    NO-EVIDENCE, and the fence read a clean 100% SATURATED.

    The head-count remains the fallback for snapshots written before `accruing` existed; it is
    never the preferred numerator.
    """
    dormant: list[str] = []
    try:
        from libs.research.slot_registry import MAX_FORWARD_SLOTS, derive_slots
        snap = derive_slots()
        occupied = len(snap.get("slots", []) or [])
        accruing = snap.get("accruing")
        used = float(accruing if isinstance(accruing, int) else occupied)
        dormant = [str(d.get("name", "?")) for d in (snap.get("not_accruing") or [])
                   if isinstance(d, dict)]
        cap, measured = float(MAX_FORWARD_SLOTS), True
        detail = f"{occupied}/{int(cap)} slots occupied, {used:.0f} accruing evidence" + (
            f"; dormant: {', '.join(dormant[:4])}" if dormant else "")
    except (ImportError, OSError, ValueError, KeyError, TypeError) as exc:
        used, cap, measured = 0.0, 12.0, False
        detail = f"cohort unreadable: {type(exc).__name__}"
    # THE CONSTRAINT MUST MATCH THE SHORTFALL. "Candidate supply" is the right diagnosis for an
    # EMPTY slot and the wrong one for an occupied slot that has gone quiet -- those are fixed at
    # opposite ends of the pipeline, and naming the wrong one sends the next reader upstream to
    # generate candidates for a cohort that has no room.
    if used >= cap * _EXPECT:
        binding = ""
    elif dormant:
        binding = (f"{len(dormant)} occupied slot(s) accruing NO evidence ({', '.join(dormant[:4])})"
                   " -- retire or repair the clock; the slot is held either way")
    else:
        binding = "candidate supply into the forward queue -- see scripts/run_promotion_queue.py"
    return Ceiling(
        "forward_confirmation_slots", cap, float(used), "accruing clocks", measured, binding,
        "An empty slot accrues NO evidence while every candidate's capacity decays against a "
        "growing book. Idle slots are the direct mechanism by which an edge arrives already "
        "outgrown (L1.18a runway).", detail)


def _forward_queue_depth() -> Ceiling:
    """WHAT IS STAGED BEHIND THE COHORT -- the ceiling nothing on this desk was measuring (R0205).

    THE BLIND SPOT, EXACTLY. Slot OCCUPANCY and pipeline DEPTH are two different ceilings, and
    the desk owned a fence for one and nothing for the other. At 12/12 occupied with ZERO
    candidates staged, `_forward_slots` above returned SATURATED with no binding constraint, and
    `capability_ratchet._alpha_output` scored the same state 10/10 "AT CEILING ... the work is
    now HOLDING it". Both are true statements about occupancy and both are the wrong question:
    the desk's throughput through this pipeline is slots x (1 / clock duration), and when nothing
    is staged, a slot that frees idles for a FULL pipeline latency before it can restart --
    measured on the live artifact at 181 days (90 clock + 90 queue + 1 decision).

    So the healthiest-looking reading on the artifact was the one describing a pipeline with zero
    throughput staged. That is the L1.28a failure in its purest form: idle capacity costs its
    entire forward output stream and announces nothing, and here it announced SATURATED.

    THE LIMIT IS ONE FULL COHORT, and it is not a hand-set number: a queue stocked to
    MAX_FORWARD_SLOTS can refill every slot the moment it frees, which is the only depth at which
    queue wait contributes zero to promotion latency. It self-scales with the cap.

    NO BINDING CONSTRAINT IS NAMED WHEN THE QUEUE IS EMPTY, and that is deliberate rather than an
    omission. An empty queue is not an external blocker and not a survival rail -- the two things
    L1.28a admits as legitimate idle headroom. It is the desk's own screening throughput, so it
    reads IDLE-UNEXPLAINED and this fence exits non-zero, which is what L1.25a means by a null
    streak triggering escalation rather than rest. The live composition goes in `detail` instead,
    so the reading is diagnostic without being self-excused.
    """
    n_promo, n_paper, sources, why = 0, 0, [], ""
    try:
        from libs.research.slot_registry import MAX_FORWARD_SLOTS
        cap = float(MAX_FORWARD_SLOTS)
    except (ImportError, ValueError):
        cap = 12.0
    # Two independent staging registers feed the cohort and BOTH count. run_promotion_queue reads
    # gauntlet survivors out of the candidate store; run_paper_sleeve_spawner queues corrected
    # Stage-A verdicts behind a full cohort. Reading only one would understate the depth.
    try:
        q = json.loads((_ROOT / "data/promotion_queue.json").read_text("utf-8"))
        n_promo = int(q.get("n_candidates") or 0)
        sources.append("promotion_queue")
    except (OSError, ValueError, TypeError):
        pass
    try:
        p = json.loads((_ROOT / "data/paper_sleeve_queue.json").read_text("utf-8"))
        n_paper = len(p.get("queued") or [])
        why = str(p.get("why") or "")
        sources.append("paper_sleeve_queue")
    except (OSError, ValueError, TypeError):
        pass
    measured = bool(sources)
    used = float(n_promo + n_paper)
    detail = (f"{n_promo} gauntlet survivor(s) + {n_paper} paper-sleeve candidate(s) staged "
              f"[{', '.join(sources)}]" + (f"; upstream says: {why[:120]}" if why else "")
              ) if measured else "neither queue artifact is readable"
    return Ceiling(
        "forward_queue_depth", cap, used, "candidates staged", measured, "",
        "A full cohort with an empty queue is not saturation, it is a stall waiting to happen: "
        "when a slot frees, the desk waits a FULL pipeline latency (measured 181d) before "
        "evidence can start accruing in it again. Occupancy measures what is running; this "
        "measures whether anything can replace it (L1.28a idleness, L1.30 replacement rate).",
        detail)


def _capital() -> Ceiling:
    """Capital ACTUALLY deployed against capital available -- and they must be two sources.

    THE WELD, found and fixed 2026-08-05. This read `live_book_usd()` as the numerator and
    `_desk_equity_usd()` as the denominator. `live_book_usd()` IS THE FIRST RUNG INSIDE
    `_desk_equity_usd()` (validation.py:129), so on any box where the NAV chain is readable the
    two calls return the same float and the ratio is IDENTICALLY 1.0 -- not usually, not by
    coincidence, but by construction. Measured on the day it was found: both returned 13151.52
    and this ceiling printed `utilisation 1.0, SATURATED` while `web/cashcarry_live.json` held
    `n_carries: 0, deployed_notional: 0.0`. A book with ZERO POSITIONS reported as fully deployed,
    on the one fence the desk's only idleness law has.

    The comment above in `status` records the previous repair going the WRONG WAY: the two sources
    disagreed ($13,155 vs $4,500), and unifying them removed the disagreement by removing the
    measurement. A ceiling and its own numerator must never share a source -- that is not a
    tightened definition, it is the deletion of the ratio.

    NOW: deployment comes from the executed book, equity from the attestation chain, and a PAPER
    attestation reports UNMEASURED rather than a number -- `molded_curve_usd` is a MOLDED/SIMULATED
    curve by its own `_note`, and utilisation computed from a simulated denominator is exactly the
    "could not measure, counted as satisfied" failure this file exists to refuse. One definition,
    owned by `libs/research/idle_yield.py`; no private copy here (the capacity_policy pattern).
    `check_idle_cost.py` prices the same gap in dollars per day (L1.51).
    """
    try:
        from libs.research.idle_yield import book_state
        bs = book_state()
        eq, book, measured, why = bs.equity_usd, bs.deployed_usd, bs.measurable, bs.why
    except (ImportError, OSError, ValueError, AttributeError, TypeError):
        eq, book, measured, why = 0.0, 0.0, False, "libs.research.idle_yield unavailable"
    return Ceiling(
        "deployed_capital", eq, book, "USD", measured,
        "" if (measured and eq > 0 and book >= eq * _EXPECT) else
        f"{why} -- priced per day by scripts/check_idle_cost.py (L1.51)",
        "An idle dollar is compounding that never starts. Under-deployment is a REAL cost "
        "reported as loudly as a risk breach (L1.20, doctrine).")


def _organs() -> Ceiling:
    """Scheduler saturation: manifest entries that actually produced a log in the last 48h."""
    if not _LOGS.exists():
        return Ceiling("scheduler_cadence", 1.0, 0.0, "organs fresh", False,
                       "log directory absent", "A scheduled organ that never runs is a cadence "
                       "declared and not kept -- the capability is paid for and returns zero.")
    manifest = _ROOT / "ops/crontab.manifest"
    scripts = set()
    if manifest.exists():
        for line in manifest.read_text("utf-8").splitlines():
            if line.strip().startswith("#") or "python" not in line:
                continue
            for tok in line.split():
                if tok.endswith(".py"):
                    scripts.add(Path(tok).stem)
    cutoff = (datetime.now(tz=UTC) - timedelta(hours=48)).timestamp()
    fresh = {p.stem.split("_20")[0] for p in _LOGS.glob("*.log") if p.stat().st_mtime >= cutoff}
    hit = sum(1 for s in scripts if any(s in f or f in s for f in fresh))
    return Ceiling(
        "scheduler_cadence", float(len(scripts)), float(hit), "organs run in 48h",
        bool(scripts),
        "" if scripts and hit >= len(scripts) * _EXPECT else
        "organs silent in 48h -- check_organs/check_stale_daemons name which; a fresh container "
        "shows zero because no cron has fired yet",
        "A scheduled organ that never runs is a cadence declared and not kept -- capability "
        "already paid for, returning zero.")


def _capability() -> Ceiling:
    """Built code that nothing imports and nothing schedules: engineering paid for, unused."""
    try:
        from libs.self_improvement.dormancy import scan
        rep = scan()
        total = float(rep.n_scripts_scanned + getattr(rep, "n_modules_scanned", 0))
        dormant = float(len(rep.dormant))
        measured = total > 0
    except (ImportError, OSError, ValueError, AttributeError, TypeError):
        total, dormant, measured = 0.0, 0.0, False
    return Ceiling(
        "capability_wired", total, max(total - dormant, 0.0), "reachable units", measured,
        "" if measured and total > 0 and (total - dormant) >= total * _EXPECT else
        "wiring backlog -- scripts/run_wiring_agent.py --apply auto-wires the provably-inert "
        "ones daily; the remainder are money-path/spend-capable and need a human cadence call",
        "A dormant capability is engineering already paid for that returns zero forever, and it "
        "compounds: nobody maintains it, so it rots into a liability (L2.9).")


def _data_assets() -> Ceiling:
    """Datasets acquired vs datasets actually READ by something. Paid-for and unread is the
    purest form of the defect: the cost is already sunk and the return is exactly zero."""
    reg = _ROOT / "data/data_assets.json"
    try:
        rows = json.loads(reg.read_text("utf-8"))
        rows = rows.get("assets", rows) if isinstance(rows, dict) else rows
        # PRESENT assets only. An asset absent from this box is a COLLECTION question ("is the
        # collector scheduled, is this even the collecting box"), not an idle-capacity one --
        # scoring the two together would blame the desk for not reading a file it never had, and
        # the number would stop meaning anything actionable.
        present = [r for r in rows if (r.get("rows") or r.get("bytes") or r.get("span"))]
        total = float(len(present))
        # THE COLLECTOR IS NOT A CONSUMER. Counting it read 97.8% -- a comfortable number meaning
        # "almost every dataset is used" -- when many of those sole "consumers" were the very
        # script that WRITES the file. A dataset read only by its own collector is precisely the
        # idle asset L1.28a is about: paid for, collected on a cadence, and feeding no research.
        used = float(sum(1 for r in present
                         if [c for c in (r.get("consumers") or [])
                             if Path(str(c)).name != Path(str(r.get("collector") or "")).name]))
        measured = total > 0
    except (OSError, ValueError, AttributeError, TypeError):
        total, used, measured = 0.0, 0.0, False
    return Ceiling(
        "data_assets_read", total, used, "present datasets with a consumer", measured,
        "" if measured and total > 0 and used >= total * _EXPECT else
        "assets present on this box with no consumer -- run scripts/build_data_registry.py and "
        "read the `consumers` column; an absent asset is a collection gap, not an idle one",
        "An unread dataset is a hypothesis never tested against evidence already bought. The "
        "26-year CFTC COT panel sat unread for weeks -- that is the proving instance (L1.3).")


def _mutation() -> Ceiling:
    """Test STRENGTH, not coverage: the fraction of injected faults the suite actually kills."""
    f = _ROOT / "data/mutation_score.json"
    try:
        d = json.loads(f.read_text("utf-8"))
        # The artifact is PER-TARGET (run_mutation.py writes a `targets` list), so a top-level
        # `kill_rate` lookup silently returned 0.0 and this ceiling read UNMEASURED while a real
        # measurement sat in the file. The aggregate is mutants-weighted, not a mean of rates:
        # a 10-mutant file at 100% must not cancel a 200-mutant file at 80%.
        # AN UNRUN SITE COUNTS AS SURVIVED (2026-08-05). run_mutation.py walks mutation sites in
        # SOURCE ORDER, so a budget-truncated target has tested a PREFIX of a file, not a sample
        # of it. Summing `killed` and `total` across targets therefore let truncation SHRINK the
        # denominator: running less of a hard file raised this score. The harness had recorded
        # `budget_truncated` and `n_sites` per target all along; this consumer read neither. That
        # is L1.53's denominator trap sitting inside the desk's own test-strength gauge -- and the
        # same mistake as reading a 14-of-137 prefix as a 35.7% result: a prefix is not a sample.
        #
        # DROPPING truncated targets was the obvious repair and it is WRONG -- it merely moves the
        # exploit. Truncate a hard file entirely and it leaves the denominator altogether, so the
        # score rises even faster. (A test asserts exactly this, because the fix looked right.)
        #
        # The honest treatment is fail-closed and uses the site count the harness already writes:
        # every site that was NOT run is charged to the denominator as un-killed. Truncation can
        # then only ever LOWER the score, which is the only incentive gradient that cannot be
        # gamed -- you buy points by killing mutants, never by declining to inject them.
        targets = [t for t in (d.get("targets") or []) if isinstance(t, dict)]
        killed = float(sum(float(t.get("killed", 0)) for t in targets))
        total = 0.0
        skipped = 0
        for t in targets:
            run = float(t.get("total", 0))
            sites = float(t.get("n_sites", 0) or 0)
            if t.get("budget_truncated"):
                skipped += 1
                # n_sites is the honest denominator; fall back to what ran only if the harness
                # did not record it, which under-counts rather than inventing a number.
                total += max(run, sites)
            else:
                total += run
        # No fallback to a top-level `kill_rate`: that key IS NEVER WRITTEN (the artifact is
        # per-target, which the comment above already records as the original bug), so the old
        # `else float(d.get("kill_rate", 0.0))` was a dead branch that turned "nothing ran" into
        # a confident 0.0 -- and then `measured = score > 0` relabelled that 0.0 as UNMEASURED,
        # so a run of zero mutants and a suite that kills nothing produced identical output.
        score = killed / total if total > 0 else 0.0
        score = score / 100.0 if score > 1.0 else score
        # MEASURED means the measurement HAPPENED, never that it came out well. `score > 0` made
        # the single worst real result -- a suite that kills no mutants at all -- unreportable,
        # because it read as "we did not look". Those are opposite facts and the desk acts on
        # them differently: one is a catastrophe, the other is a chore.
        measured = total > 0
    except (OSError, ValueError, TypeError, AttributeError):
        score, measured, skipped, total = 0.0, False, 0, 0.0
    return Ceiling(
        "test_kill_rate", 1.0, score,
        f"mutants killed (fraction of {total:.0f} scored"
        + (f"; {skipped} truncated target(s) EXCLUDED -- a prefix is not a sample)"
           if skipped else ")"),
        measured,
        "" if score >= _EXPECT else
        (f"{skipped} target(s) were budget-truncated and are unscored: raise the budget or "
         "narrow the target, because running less must never read as killing more. "
         if skipped else "") +
        "surviving mutants in libs/execution/staging.py and libs/risk/gate.py -- the survivor "
        "list IS the work queue (L1.0c)",
        "An unkilled mutant is a real code change the suite cannot see. On the money path that "
        "is a silent correctness ceiling under every other guarantee.")


def _test_suites_runnable() -> Ceiling:
    """Test modules that can actually EXECUTE here, vs modules that skip on a missing dependency.

    A `pytest.importorskip` skip prints one grey line and exits 0, so a suite covering the
    backtest cross-engine, GARCH stationarity, or any other optional-dep path reads as GREEN while
    testing nothing. Measured 2026-07-30: arch, backtrader and vectorbt are all DECLARED in
    pyproject and all absent, so five test modules have been silently inert.

    That is L1.28a exactly -- capability paid for (the tests are written, the deps are chosen) and
    returning zero, with no error to notice. Unmeasured counts as zero, so it belongs on this
    board rather than in a skip line nobody reads.
    """
    import importlib.util
    declared = ("arch", "backtrader", "vectorbt")
    have = [m for m in declared if importlib.util.find_spec(m) is not None]
    return Ceiling(
        "optional_test_deps", float(len(declared)), float(len(have)), "declared deps importable",
        True,
        "" if len(have) >= len(declared) * _EXPECT else
        f"missing {sorted(set(declared) - set(have))} -- their test modules skip silently and "
        "read as green; `pip install -e '.[research]'` on the box that runs CI",
        "A test that skips on a missing dependency prints one grey line and exits 0. The suite "
        "reports green while those paths are untested -- the same 'could not measure counted as "
        "satisfied' failure the Gate 0 board refuses.")


def _brain_seat() -> Ceiling:
    """THE SEAT: how much of the day the desk's ONE serial brain is actually working.

    THE UNMEASURED CEILING (found 2026-07-31 answering "is anything still below max
    frequency"): every claude-invoking organ takes /tmp/quant_brain.lock, and every LOSER
    appends a DEFERRED line to brain_mutex.log -- a complete, free record of contention that
    NOTHING had ever read. So the desk raised and lowered LLM cadences for weeks with no
    measurement of the resource they all compete for: the exact "we are running at 60% and
    that seems fine" defect L1.28a exists to kill, sitting on the desk's scarcest input.

    THE METRIC, and why it is deferrals rather than wall-clock: a deferral is a run the desk
    WANTED and did not get, which is precisely the thing extra cadence is supposed to buy. Two
    readings, both actionable:
      deferral rate LOW  -> the seat has idle windows: RAISE cadences (headroom exists).
      deferral rate HIGH -> the seat is the binding constraint: raising cron changes nothing;
                            only a second seat (the research twin) or shorter runs do.
    Utilisation is reported as attempts-that-ran / attempts-made over the trailing 24h, so
    100% means nothing was ever turned away and lower means real contention. UNMEASURED (no
    log yet, e.g. this container) counts as ZERO by law -- never as healthy."""
    log = _LOGS / "brain_mutex.log"
    since = datetime.now(tz=UTC) - timedelta(hours=24)
    deferred = 0
    try:
        for line in log.read_text("utf-8", errors="ignore").splitlines():
            stamp = line.split(" ", 1)[0]
            try:
                if datetime.fromisoformat(stamp.replace("Z", "+00:00")) >= since:
                    deferred += 1
            except ValueError:
                continue
        measured = True
    except OSError:
        measured = False
    # Attempts = organ fires that reached the mutex. Runs = attempts - deferrals. The daily
    # scheduled claude-organ fire count is the denominator's floor; deferrals add the rest.
    scheduled_fires = 34.0                                  # claude-invoking cron lines/day
    attempts = scheduled_fires + deferred
    ran = attempts - deferred
    return Ceiling(
        "brain_seat_throughput", attempts if measured else scheduled_fires,
        ran if measured else 0.0, "organ runs/24h (vs attempted)", measured,
        "" if (measured and deferred == 0) else
        ("ONE serial brain seat: every deferred organ is a run the desk wanted and did not "
         "get. The resolution path is a SECOND SEAT (research twin, ops/role=research) -- "
         "raising cron cadence cannot add throughput to a saturated mutex"
         if measured else
         "brain_mutex.log absent on this host -- measurable only where organs actually run"),
        "This is the resource EVERY llm cadence competes for. Unmeasured, the desk cannot tell "
        "'raise the cadence' (headroom) from 'buy a second seat' (contention) -- and it has "
        "been raising cadences blind. Deferrals are the only honest signal of which is true.")


def _book_vol() -> Ceiling:
    """RISK-TAKING ITSELF: realized book volatility against the Kelly-implied ceiling (R0107).

    THE CEILING THAT WAS MISSING, and it is the one closest to the objective. Every other
    ceiling here measures an INPUT -- slots, capital, organs, data. None measured the thing
    those inputs exist to produce: risk actually carried. The desk could run at a third of the
    volatility its own rails permit for a month and no artifact would have said so.

    The limit is not a hand-set number. At fraction ``f`` of full Kelly on an edge of annualized
    Sharpe ``S``, book volatility is exactly ``f * S`` -- so the ceiling falls out of the rails
    (KellyLimits.hard_max, half-Kelly, the absolute maximum ever) and the demonstrated Sharpe.
    It self-scales in the direction the objective wants: the permitted volatility RISES as
    validated edges accrue, automatically, with no rail touched and no bar loosened.

    BOTH DIRECTIONS ARE DEFECTS, which is why this is a ceiling and not a limit. Below it with
    no named constraint is L1.28a idleness -- risk the evidence supports and the desk declined.
    Above it is an over-Kelly breach, where expected log-growth FALLS while ruin rises: worse on
    both axes at once, and the only reading here whose honest answer is to cut.

    UNMEASURED TODAY, AND CORRECTLY SO. Every row in the NAV chain is paper/testnet and the
    recent ones are an explicitly MOLDED curve. Deriving a risk ceiling from a simulated
    equity series would publish a number the desk then sizes against -- the L1.45 failure of
    stepping the book up on fiction, which is strictly worse than leaving it pinned. It reads
    ZERO with the blocker named, and it starts measuring the moment real fills exist.
    """
    try:
        from libs.risk.vol_headroom import from_nav_chain
        h = from_nav_chain(_ROOT / "data/nav_attestation.jsonl")
        used, limit, measured, why = (h.realized_vol_ann, h.ceiling_vol_ann, h.measured, h.reason)
    except (ImportError, OSError, ValueError) as exc:
        used, limit, measured, why = 0.0, 0.0, False, f"vol headroom unavailable: {exc}"
    return Ceiling(
        "book_vol_vs_kelly_ceiling", limit, used, "annualized vol", measured,
        "" if (measured and limit > 0 and used >= limit * _EXPECT) else why,
        "The risk budget is the ceiling nearest the objective: under-risking a demonstrated "
        "edge forfeits compounding exactly as idle capital does, and over-risking it lowers "
        "E[log W] while raising ruin. Unmeasured, the desk cannot tell the two apart.")


def collect() -> list[Ceiling]:
    return [_capital(), _forward_slots(), _forward_queue_depth(), _capability(), _data_assets(),
            _organs(), _mutation(), _test_suites_runnable(), _brain_seat(), _book_vol()]


def build() -> dict[str, Any]:
    ceilings = collect()
    rows = [{**asdict(c), "utilisation": round(c.utilisation, 3), "status": c.status}
            for c in ceilings]
    unexplained = [r["name"] for r in rows if r["status"] == "IDLE-UNEXPLAINED"]
    unmeasured = [r["name"] for r in rows if r["status"] == "UNMEASURED"]
    return {
        "generated": datetime.now(tz=UTC).isoformat(),
        "law": "L1.28a -- unused headroom is not safety, it is an unbooked loss. Unmeasured "
               "utilisation counts as ZERO: a ceiling nobody measures is idle by default.",
        "expect_fraction": _EXPECT,
        "mean_utilisation": round(sum(c.utilisation for c in ceilings) / max(len(ceilings), 1), 3),
        "idle_unexplained": unexplained, "unmeasured": unmeasured, "ceilings": rows,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--report-only", action="store_true")
    args = ap.parse_args()
    rep = build()
    _OUT.parent.mkdir(parents=True, exist_ok=True)
    _OUT.write_text(json.dumps(rep, indent=2), "utf-8")
    if args.json:
        print(json.dumps(rep, indent=2))
    else:
        print(f"utilisation (L1.28a): mean {rep['mean_utilisation']:.0%} across "
              f"{len(rep['ceilings'])} ceilings")
        for r in rep["ceilings"]:
            bar = f"{r['used']:,.0f}/{r['limit']:,.0f} {r['unit']}"
            print(f"  {r['status']:17} {r['name']:26} {r['utilisation']:6.1%}  {bar}")
            if r.get("detail"):
                print(f"  {'':17} └─ {r['detail'][:140]}")
            if r["binding_constraint"]:
                print(f"  {'':17} └─ bound by: {r['binding_constraint'][:100]}")
        print(f"-> {_OUT.relative_to(_ROOT)}")

    # THE DENOMINATOR IS THE *MEASURED* CEILINGS, NEVER `len(rows)` (L1.57, R0417). This fence's
    # verdict is "no ceiling is idle without a named constraint", and an UNMEASURED ceiling
    # cannot contribute to `idle_unexplained` -- `status` returns UNMEASURED before any of the
    # idle branches are reached. So a board on which EVERY reading failed publishes an empty
    # `idle_unexplained` and exits 0: a fully dark board renders as a clean one, which is the
    # exact arithmetic L1.57 exists to refuse and the exact inversion of this fence's own law
    # (L1.28a: unmeasured utilisation counts as ZERO, so a dark board is maximally idle).
    #
    # `len(rows)` would be the OTHER half of the same defect -- `collect()` is a hardcoded list
    # of ten builder calls, so it counts what the author wrote down and can never fall when a
    # reading dies. It must count what the RUN found, and what the run found is the readings
    # that came back live.
    if args.report_only:          # the explicit "do not gate" switch -- no verdict to refuse
        return 0
    n_measured = sum(1 for r in rep["ceilings"] if r["status"] != "UNMEASURED")
    status = "OK" if not rep["idle_unexplained"] else "IDLE-UNEXPLAINED"
    # `fence=` explicitly: caller_name() reads `__main__.__file__`, which is correct for the cron
    # invocation and WRONG for any in-process call (under pytest it resolves to pytest's own
    # __main__.py). A misattributed row is not counted against the L1.57 coverage ratchet at all,
    # so the declaration would silently not exist for exactly the callers that are easiest to add.
    return fence_exit(status, {"OK"}, scanned=n_measured, of="ceilings with a live reading",
                      fence="check_utilisation.py")


if __name__ == "__main__":
    raise SystemExit(main())

```

### scripts\fit_print_impact.py
```python
"""Fit an execution-cost curve from OTHER TRADERS' PRINTS -- the third cost basis (L1.11b).

WHAT WAS MISSING. `data/cost_model.json` decides which names the book may hold, and it is
produced by walking DISPLAYED DEPTH only (`scripts/run_cost_model.py` reads no trade row at all).
L1.45 states why that cannot be the whole answer -- "a book-walk measures DISPLAYED depth in a
book that existed WITHOUT OUR ORDER IN IT" -- and the desk's answer was excitation, bounded to its
own 531 fills because L1.11(b) says an Execution Reality Model comes from "our own fills". That
scope word was written to stop the desk trusting a vendor's coefficient. It was read as "only our
own fills count", and it left unread the largest execution dataset on the box: every print on the
tape is a completed execution experiment at a known size with a published aggressor side, against
the same book we snapshot, paid for by somebody else.

This script fits that third basis and publishes it ALONGSIDE the book walk, labelled by basis.

WHAT IT DOES NOT DO, AND WHY THAT IS NOT TIMIDITY. It does not feed `_rt_bps`, size anything, or
admit anything. The print basis reads CHEAPER than the book walk on thin books (it sees liquidity
the snapshot does not), so wiring it into `_entry_gate` today would LOOSEN the gate on exactly the
books that produced COOKIEUSDT's 130bps round-trip -- on an estimator whose out-of-sample check
currently has 12 usable rows. That is EVIDENCE restraint, the kind L1.28 protects, not scope
restraint: the build is complete and the consumer is blocked on a falsifier reaching power, which
is rowed rather than left implicit. The executor's tighten-only `max(modelled, realised)` rule is
untouched by this file.

STATUS (rollup, and per (venue,symbol)):
    MEASURED      lambda separated from zero on n_eff independent intervals
    UNDERPOWERED  too few independent intervals, or |t| below the bar
    UNIDENTIFIED  net flow carries no usable variance, or the fitted slope is non-positive
    NO-DATA       no usable depth/print pairing
    UNMEASURED    rollup only: nothing measured anywhere -- never reads as OK (L1.28a)

    python scripts/fit_print_impact.py [--json] [--hours N] [--venue fut] [--symbol SYM]
"""
from __future__ import annotations

import argparse
import itertools
import json
import statistics
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

# L1.42 LAWFUL ENTRY: pages, does not block -- a governance fault must never silently stop an
# organ that only reads the tape and writes one advisory artifact.
from libs.ops.input_provenance import Inputs  # noqa: E402
from libs.ops.lawful import guard as _law_guard  # noqa: E402
from libs.research import moat_microstructure as mm  # noqa: E402
from libs.research import print_impact as pi  # noqa: E402

_MOAT = _ROOT / "data/moat"
_OUT = _ROOT / "data/print_impact.json"
_COST_MODEL = "data/cost_model.json"

#: Hours of tape per (venue, symbol). One partition is one hour. 24 keeps a full pass near a
#: minute of I/O while giving every liquid name several thousand intervals; --hours raises it.
_DEFAULT_HOURS = 24
#: The size the book actually trades. run_cost_model.py prices the pair at $500/leg for the same
#: reason; keeping the two comparable is the entire point of publishing a second basis.
_DESK_NOTIONAL = 450.0
#: Venues carrying both a depth and a print stream. Bybit is included: its prints additionally
#: carry isBlockTrade/isRPITrade, which no feature code on this desk reads yet.
_VENUES = ("fut", "spot", "bybit")


def _symbols(venue: str) -> list[str]:
    d = _MOAT / venue
    return sorted(p.name for p in d.iterdir() if p.is_dir()) if d.is_dir() else []


def _fit_one(venue: str, symbol: str, hours: int) -> pi.ImpactFit:
    parts = sorted((_MOAT / venue / symbol).glob("*.jsonl.gz"))[-hours:]
    if not parts:
        return pi.fit([], symbol=symbol, venue=venue)
    recs = itertools.chain.from_iterable(mm.read_partition(p) for p in parts)
    return pi.fit(pi.intervals(recs, venue), symbol=symbol, venue=venue)


def _as_row(f: pi.ImpactFit, notional: float) -> dict[str, Any]:
    return {
        "status": f.status,
        "n_intervals": f.n,
        "n_eff": f.n_eff,
        "lambda_bps_per_1k": f.lam_controlled_bps_per_1k,
        "lambda_raw_bps_per_1k": f.lam_bps_per_1k,
        "momentum_share": f.momentum_share,
        "t_stat": f.t_stat,
        "r2": f.r2,
        "half_spread_bps": f.half_spread_bps,
        "median_print_usd": f.median_print_usd,
        "prints_in_desk_range": f.prints_in_desk_range,
        "flow_p50_usd": f.flow_p50_usd,
        "identified_to_usd": f.identified_to_usd,
        f"cost_bps_at_{int(notional)}": f.cost_bps(notional),
        "detail": f.detail,
    }


def _pair_compare(fits: dict[tuple[str, str], pi.ImpactFit], cost_model: Any,
                  notional: float) -> list[dict[str, Any]]:
    """Print-basis pair cost vs the book-walk pair cost, per symbol.

    Both bases price the same thing -- spot BUY + perp SELL for one open -- so they are directly
    comparable, and the DISAGREEMENT is the deliverable. Agreement corroborates the desk's
    most-consumed derivative from an independent direction; divergence names a book where one of
    the two is wrong and research has somewhere to go.
    """
    out: list[dict[str, Any]] = []
    symbols = {s for (v, s) in fits if v in ("fut", "spot")}
    cm_syms = cost_model.get("symbols", {}) if isinstance(cost_model, dict) else {}
    for sym in sorted(symbols):
        spot, fut = fits.get(("spot", sym)), fits.get(("fut", sym))
        if spot is None or fut is None:
            continue
        s_cost = spot.cost_bps(notional)
        f_cost = fut.cost_bps(notional)
        if s_cost is None or f_cost is None:
            # One leg unmeasured means the PAIR is unmeasured. Substituting the measured leg and
            # calling it a pair would publish half a cost as a whole one.
            out.append({"symbol": sym, "print_pair_open_bps": None,
                        "spot_status": spot.status, "fut_status": fut.status,
                        "book_walk_pair_open_bps": None, "ratio": None,
                        "detail": "one or both legs unmeasured"})
            continue
        pair = s_cost + f_cost
        bw = None
        entry = cm_syms.get(sym, {}).get("pair", {}) if isinstance(cm_syms, dict) else {}
        for key in ("500", "250"):
            v = entry.get(key, {}).get("pair_open_bps") if isinstance(entry, dict) else None
            if v is not None:
                bw = float(v)
                break
        out.append({
            "symbol": sym,
            "print_pair_open_bps": round(pair, 4),
            "spot_status": spot.status, "fut_status": fut.status,
            "spot_half_spread_bps": spot.half_spread_bps,
            "fut_half_spread_bps": fut.half_spread_bps,
            # Impact's share of the print-basis cost. Near zero means the desk is a SPREAD taker
            # at this size and trading smaller buys nothing -- an operational answer the blended
            # book-walk number cannot give.
            "impact_share_of_cost": round(
                1.0 - ((spot.half_spread_bps or 0.0) + (fut.half_spread_bps or 0.0)) / pair, 4)
            if pair > 0 else None,
            "book_walk_pair_open_bps": bw,
            "ratio": round(pair / bw, 3) if bw else None,
        })
    return out


def _falsifier(pairs: list[dict[str, Any]]) -> dict[str, Any]:
    """Does the print basis rank OUR OWN realised slippage? The estimator's own kill criterion.

    Pre-registered before the fit was run: if predicted cost has ~zero rank correlation with
    realised slippage across the symbols where both exist, the estimator is confounded (large
    prints arrive BECAUSE the book is already moving) and adds nothing over the book walk.

    The honest answer today is UNDERPOWERED and it is reported as such rather than skipped: only
    12 of 531 execution_tape rows carry spot_slip_bps/fut_slip_bps at all -- the proposal that
    motivated this build asserted all 531 did. A rank correlation on a handful of symbols is not
    evidence either way, and calling it one would be the phantom-validation this desk kills.
    """
    tape = _ROOT / "data/moat/execution_tape/cashcarry_trades.jsonl"
    realised: dict[str, list[float]] = {}
    n_rows = 0
    try:
        for line in tape.read_text("utf-8").splitlines():
            if not line.strip():
                continue
            try:
                r = json.loads(line)
            except json.JSONDecodeError:
                continue
            n_rows += 1
            sp, ft = r.get("spot_slip_bps"), r.get("fut_slip_bps")
            if sp is None:
                continue
            try:
                realised.setdefault(str(r.get("symbol")), []).append(
                    abs(float(sp)) + abs(float(ft or 0.0)))
            except (TypeError, ValueError):
                continue
    except OSError:
        return {"status": "NO-DATA", "detail": "execution_tape unreadable",
                "n_tape_rows": 0, "n_with_slippage": 0, "n_paired": 0, "spearman": None}

    pred = {p["symbol"]: p["print_pair_open_bps"] for p in pairs
            if p.get("print_pair_open_bps") is not None}
    paired = [(pred[s], statistics.median(v)) for s, v in realised.items() if s in pred]
    n_slip = sum(len(v) for v in realised.values())

    if len(paired) < 8:
        return {
            "status": "UNDERPOWERED",
            "detail": (f"{len(paired)} symbols carry both a print-basis prediction and a realised "
                       f"slippage reading ({n_slip} slipped rows of {n_rows} tape rows). A rank "
                       "correlation here would be noise reported as validation."),
            "n_tape_rows": n_rows, "n_with_slippage": n_slip, "n_paired": len(paired),
            "spearman": None,
            "unblock": ("instrument every close with spot_slip_bps/fut_slip_bps -- the executor "
                        "already computes both and writes them on only 12 of 531 rows"),
        }
    import numpy as np
    a = np.array([p for p, _ in paired], dtype=float)
    b = np.array([r for _, r in paired], dtype=float)
    ra, rb = np.argsort(np.argsort(a)), np.argsort(np.argsort(b))
    rho = float(np.corrcoef(ra, rb)[0, 1])
    return {
        "status": "MEASURED" if abs(rho) >= 0.3 else "REFUTED",
        "detail": f"Spearman {rho:.3f} over {len(paired)} symbols",
        "n_tape_rows": n_rows, "n_with_slippage": n_slip, "n_paired": len(paired),
        "spearman": round(rho, 4),
    }


def build_report(hours: int, venues: tuple[str, ...], only: str | None,
                 notional: float) -> dict[str, Any]:
    inp = Inputs("fit_print_impact.build_report")
    # required=False is the honest declaration: the FIT depends only on the tape, so an absent
    # cost_model costs the desk the comparison, not the measurement. Marking it required would
    # publish `measured: false` over numbers that were in fact measured -- an honest-gap flag
    # pointed at the wrong organ (L1.55).
    cost_model = inp.read_json(_COST_MODEL, default={}, max_age_h=72.0, required=False)

    fits: dict[tuple[str, str], pi.ImpactFit] = {}
    per_venue: dict[str, dict[str, Any]] = {}
    for venue in venues:
        syms = [s for s in _symbols(venue) if (only is None or s == only)]
        rows: dict[str, Any] = {}
        for sym in syms:
            f = _fit_one(venue, sym, hours)
            fits[(venue, sym)] = f
            rows[sym] = _as_row(f, notional)
        per_venue[venue] = rows

    all_fits = list(fits.values())
    n_scanned = len(all_fits)
    by_status: dict[str, int] = {}
    for f in all_fits:
        by_status[f.status] = by_status.get(f.status, 0) + 1
    n_measured = by_status.get(pi.MEASURED, 0)

    pairs = _pair_compare(fits, cost_model, notional)
    priced = [p for p in pairs if p.get("print_pair_open_bps") is not None]
    ratios = [p["ratio"] for p in priced if p.get("ratio") is not None]
    shares = [p["impact_share_of_cost"] for p in priced
              if p.get("impact_share_of_cost") is not None]

    # ROLLUP. An empty measurement set must never read as OK (L1.28a), and the denominator here is
    # a COUNT OF WHAT THIS RUN FOUND rather than of a hardcoded symbol list (L1.57) -- if the
    # recorder universe shrinks to nothing, n_scanned goes to 0 and the status goes UNMEASURED
    # rather than reporting a clean pass over an empty set.
    if n_scanned == 0:
        status, detail = "UNMEASURED", "no (venue, symbol) pairs scanned -- is data/moat present?"
    elif n_measured == 0:
        status = "UNMEASURED"
        detail = f"0 of {n_scanned} (venue,symbol) fits measured: {by_status}"
    else:
        status = "MEASURED"
        detail = (f"{n_measured} of {n_scanned} fits measured; {len(priced)} symbols priced on "
                  f"both legs at ${int(notional)}")

    return {
        "generated": datetime.now(UTC).isoformat(),
        "law": "L1.11b third basis -- execution cost from third-party prints",
        "status": status,
        "detail": detail,
        "basis": "third_party_prints",
        "promotion_authority": "NONE -- advisory second basis, published alongside the book walk",
        "hours_per_symbol": hours,
        "desk_notional_usd": notional,
        "n_scanned": n_scanned,
        "n_measured": n_measured,
        "by_status": by_status,
        "convention": ("cost_bps(N) = half_spread_bps + 0.5 * lambda * N; lambda is the CONTROLLED "
                       "slope of mid return (bps) on net signed interval flow, per $1,000. Pair = "
                       "spot BUY + perp SELL, matching run_cost_model.py so the two are "
                       "comparable. Intervals are assigned by FILE ORDER (receipt), never by "
                       "mixing the venue-stamped trade clock with the receipt-stamped depth "
                       "clock (L1.46)."),
        "agreement_with_book_walk": {
            "n_compared": len(ratios),
            "median_ratio_print_over_bookwalk": round(statistics.median(ratios), 3)
            if ratios else None,
            "median_impact_share_of_cost": round(statistics.median(shares), 4) if shares else None,
            # THE RATIO IS NOT THE HEADLINE AND MUST NOT BE READ AS ONE. Measured 2026-08-12:
            # impact is 0.25%-8.6% of the print-basis cost at $450, so 91-99.75% of BOTH bases is
            # the same quoted half-spread, read off the same depth snapshots. A ratio near 1 is
            # therefore very largely TAUTOLOGICAL rather than independent corroboration, and
            # publishing it without this line would manufacture a validation the data does not
            # support. The bases are only genuinely independent where impact_share_of_cost is
            # large -- which is where they diverge.
            "independence": ("LIMITED -- both bases read the same quoted spread, which is "
                             "91-99.75% of the number at this size. Agreement is mostly shared "
                             "input, not confirmation. Weight the DIVERGENCES, not the median."),
            "note": ("ratio << 1 names a book whose DISPLAYED depth is thin relative to the "
                     "liquidity that actually trades -- the book walk charges a full level walk "
                     "the print tape does not see paid."),
        },
        # The operationally useful answer, and the one the blended book-walk number cannot give:
        # at the desk's size, is execution cost a SPREAD problem or a SIZE problem?
        "spread_vs_impact": {
            "median_impact_share_of_cost": round(statistics.median(shares), 4) if shares else None,
            "reading": ("At $450 the desk is a SPREAD TAKER, not an impact maker: trading in "
                        "smaller clips cannot recover a cost that is ~97% half-spread. Cost "
                        "reduction on this book comes from PASSIVE placement and from symbol "
                        "selection, never from slicing.") if shares and
            statistics.median(shares) < 0.2 else
                       ("Impact is a material share of cost -- order slicing and size discipline "
                        "are live levers here."),
        },
        "falsifier": _falsifier(pairs),
        "pairs": sorted(priced, key=lambda p: -(p.get("ratio") or 0.0)),
        "per_venue": per_venue,
        "inputs": inp.block(),
        "measured": inp.measured() and status == "MEASURED",
    }


def main() -> int:
    _law_guard()
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--hours", type=int, default=_DEFAULT_HOURS,
                    help="partitions (hours) of tape per symbol")
    ap.add_argument("--venue", action="append", choices=_VENUES,
                    help="restrict to one venue (repeatable)")
    ap.add_argument("--symbol", help="restrict to one symbol")
    ap.add_argument("--notional", type=float, default=_DESK_NOTIONAL)
    args = ap.parse_args()

    rep = build_report(args.hours, tuple(args.venue) if args.venue else _VENUES,
                       args.symbol, args.notional)
    _OUT.parent.mkdir(parents=True, exist_ok=True)
    _OUT.write_text(json.dumps(rep, indent=1, default=str) + "\n", "utf-8")

    if args.json:
        print(json.dumps(rep, indent=1, default=str))
    else:
        print(f"print impact (L1.11b third basis): {rep['status']} -- {rep['detail']}")
        agr = rep["agreement_with_book_walk"]
        sv = rep["spread_vs_impact"]
        print(f"  spread vs impact: impact is {sv['median_impact_share_of_cost']} of cost at "
              f"${int(rep['desk_notional_usd'])} -- {sv['reading'].split('.')[0]}.")
        print(f"  vs book walk: n={agr['n_compared']} median ratio "
              f"{agr['median_ratio_print_over_bookwalk']} "
              f"(independence: {agr['independence'].split('--')[0].strip()})")
        fal = rep["falsifier"]
        print(f"  falsifier: {fal['status']} -- {fal['detail']}")
        # The DIVERGENCES are the deliverable, so print both tails rather than one.
        rated = [p for p in rep["pairs"] if p.get("ratio") is not None]
        for label, rows in (("book-walk DEARER", rated[-4:][::-1]), ("book-walk cheaper",
                                                                     rated[:2])):
            for p in rows:
                print(f"    [{label:17s}] {p['symbol']:12s} print "
                      f"{p['print_pair_open_bps']:8.3f}  book-walk "
                      f"{p['book_walk_pair_open_bps']:8.3f}  ratio {p['ratio']}")
        print(f"  wrote {_OUT.relative_to(_ROOT)}")
    # A starved fit is a REPORT, not a gate failure -- this organ cannot conjure prints that were
    # never recorded. Exit 1 only when NOTHING measured, so a silent total failure cannot pass.
    return 0 if rep["status"] == "MEASURED" else 1


if __name__ == "__main__":
    sys.exit(main())

```

### scripts\run_desk_integrity.py
```python
"""Hunt the wiring regressions that cost this desk more than any research question.

WHY THIS EXISTS (principal, 2026-09-04: "the machinery doesn't execute, and the desk spends its
time repairing regressions")

In ONE session the desk lost hours to eight separate infrastructure failures, none of them
research:

    1. the certificate canon rolled back to a 12-day-old sweep holding ONE survivor, which
       unenrolled the forward book -- 48 clocks orphaned, 207 trades frozen
    2. universe.json replaced by a 23-symbol stump, so the gauntlet swept a tenth of the universe
    3. currency_profit lost on 248 of 251 symbols, blinding gate 8 (stress_costs) entirely
    4. four code fixes silently reverted by the ssh-context pre-commit guard
    5. the gauntlet -- the job that MINTS certificates -- running daily, not hourly
    6. the VPS bar cache eight days stale while the box held current bars
    7. NOTHING scheduled the forward engine on either machine
    8. sleeve_registry.py stale on the trading box, so every clock broke terminally

EVERY ONE WAS INVISIBLE TO THE DESK'S OWN CHECKS, and each was invisible for the same reason: the
check that would have caught it read a DIFFERENT record than the one that broke. Freshness checks
read mtime, and a rollback writes ancient content with a current mtime. Healers read the registry,
and the state file was the stale one. The parity checker read the manifest, and the installer read
a committed timer that disagreed with it.

SO THIS READS THE PAIRS. Not "is X fresh" but "do X and Y still agree", which is the question that
actually catches a rollback. It repairs what is mechanical and refuses to touch what is a
judgement, and it never reports health it did not measure: an unreadable input is UNKNOWN, never a
pass.
"""
from __future__ import annotations

import argparse
import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
DESK = ROOT / "desks" / "mt5"
OUT = ROOT / "data" / "desk_integrity.json"

#: Sub-checks that can repair themselves, run before the read-only audit so the audit sees the
#: repaired state rather than reporting a defect this pass already fixed.
_REPAIRERS: tuple[tuple[str, list[str]], ...] = (
    ("universe floor", ["scripts/check_universe_floor.py"]),
    ("artifact rollback", ["scripts/check_artifact_monotonic.py"]),
    ("schedule parity", ["scripts/check_scheduler_manifest.py", "--fix-schedules"]),
)


def _run(args: list[str], timeout: int = 600) -> tuple[int, str]:
    try:
        p = subprocess.run([str(ROOT / ".venv/bin/python"), *args], cwd=ROOT, timeout=timeout,
                           capture_output=True, text=True)
        return p.returncode, (p.stdout or "") + (p.stderr or "")
    except subprocess.TimeoutExpired:
        return 124, "TIMEOUT"
    except OSError as exc:
        return 125, f"{type(exc).__name__}: {exc}"


def _json(p: Path) -> Any:
    try:
        return json.loads(p.read_text("utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def check_uncommitted_code() -> dict[str, Any]:
    """Code edits sitting uncommitted are one revert away from gone.

    Measured 2026-09-04: four separate fixes to shadow_forward.py, run_deep_audit.py and
    desk_modules.py were reverted before they were ever committed -- the last of them AFTER being
    shipped to the trading box and "hash-verified", because both copies had been reverted and
    matched each other. On this tree, uncommitted code is not work in progress; it is work about
    to be lost.
    """
    try:
        out = subprocess.run(["git", "status", "--porcelain"], cwd=ROOT,
                             capture_output=True, text=True, timeout=60).stdout
    except (subprocess.SubprocessError, OSError) as exc:
        return {"status": "UNKNOWN", "why": f"{type(exc).__name__}"}
    py = [ln[3:] for ln in out.splitlines()
          if ln[3:].endswith(".py") and not ln.startswith("??")]
    return {"status": "DEFECT" if py else "OK",
            "uncommitted_py": py[:12], "count": len(py),
            "why": ("uncommitted .py changes are reverted by the ssh-context guard; commit with "
                    "QUANT_ALLOW_SSH_PY=1" if py else "no uncommitted code")}


def check_record_pairs() -> dict[str, Any]:
    """Records that MUST agree. A rollback shows up here and nowhere else."""
    findings = []
    canon = _json(DESK / "data" / "UNIVERSAL_SURVIVORS.canon.json")
    report = _json(DESK / "reports" / "UNIVERSAL_SURVIVORS.json")
    if canon is None or report is None:
        findings.append({"pair": "canon/report", "status": "UNKNOWN",
                         "why": "one side unreadable -- never a clean pass"})
    else:
        cs, rs = canon.get("swept_at") or "", report.get("swept_at") or ""
        cn, rn = len(canon.get("survivors") or {}), len(report.get("survivors") or {})
        if cs != rs or abs(cn - rn) > 0:
            findings.append({
                "pair": "canon/report", "status": "DEFECT",
                "canon": f"{cn} survivors @ {cs}", "report": f"{rn} survivors @ {rs}",
                "why": ("the canon IS enrolment: if it is the older of the two, the forward book "
                        "is running on certificates that no longer represent the latest sweep")})

    reg = _json(DESK / "data" / "sleeve_registry.json") or {}
    st = _json(DESK / "reports" / "shadow" / "shadow_state.json") or {}
    sl = st.get("sleeves") or st
    rows = reg.get("sleeves") or {}
    if rows and isinstance(sl, dict):
        dis = [k for k in rows
               if isinstance(sl.get(k), dict)
               and str(rows[k].get("status") or "") != str(sl[k].get("status") or "")]
        if len(dis) > len(rows) * 0.5:
            findings.append({
                "pair": "registry/state", "status": "DEFECT",
                "disagreeing": len(dis), "of": len(rows),
                "why": ("recovery paths key off whichever record says there is nothing to do; "
                        "when these disagree at scale, clocks deadlock and accrue nothing")})
    return {"status": "DEFECT" if any(f["status"] == "DEFECT" for f in findings)
            else ("UNKNOWN" if findings else "OK"), "findings": findings}


def check_forward_lane() -> dict[str, Any]:
    """Clocks that are terminal, and evidence frozen inside them."""
    st = _json(DESK / "reports" / "shadow" / "shadow_state.json")
    if st is None:
        return {"status": "UNKNOWN", "why": "shadow_state unreadable"}
    sl = st.get("sleeves") or st
    rows = [v for v in sl.values() if isinstance(v, dict)]
    broken = [v for v in rows if str(v.get("status") or "") == "IDENTITY_BROKEN"]
    frozen = sum(v.get("n", 0) or 0 for v in broken)
    active = [v for v in rows if str(v.get("status") or "") == "ACTIVE"]
    return {"status": "DEFECT" if frozen else "OK",
            "active": len(active), "active_trades": sum(v.get("n", 0) or 0 for v in active),
            "identity_broken": len(broken), "trades_frozen": frozen,
            "why": ("trades sitting in terminal rows are evidence the desk already earned and is "
                    "discarding" if frozen else "no evidence frozen")}


def check_bar_freshness(max_hours: float = 48.0) -> dict[str, Any]:
    """The research plane silently reading a stale market is the worst failure mode here."""
    try:
        import pandas as pd
    except ImportError:
        return {"status": "UNKNOWN", "why": "pandas unavailable"}
    uni = DESK / "data" / "universe"
    now = pd.Timestamp.now(tz="UTC")
    ages = []
    for p in sorted(uni.glob("*_H1.parquet")):
        try:
            df = pd.read_parquet(p)
            idx = pd.DatetimeIndex(df.index if df.index.name else df.iloc[:, 0])
            last = idx.max()
            last = last.tz_localize("UTC") if last.tz is None else last
            ages.append((now - last).total_seconds() / 3600.0)
        except Exception:
            continue
    if not ages:
        return {"status": "UNKNOWN", "why": "no readable H1 parquet"}
    ages.sort()
    med = ages[len(ages) // 2]
    fresh = sum(1 for a in ages if a < 24)
    return {"status": "DEFECT" if med > max_hours else "OK",
            "symbols": len(ages), "median_staleness_h": round(med, 1), "fresher_than_24h": fresh,
            "why": ("bars this old mean every adapter, measurement and research pass is answering "
                    "about a market that has moved on" if med > max_hours else "bars current")}


def check_dashboard() -> dict[str, Any]:
    """What the principal actually looks at. A dashboard reporting stale numbers is a lie at rest.

    It reads `web/desk_state.json`, which is pulled from the trading box every two minutes -- so a
    stamp older than an hour means the pull is dead and every figure on the page is describing a
    desk that has moved on, while looking perfectly current.
    """
    d = _json(ROOT / "web" / "desk_state.json")
    if d is None:
        return {"status": "UNKNOWN", "why": "desk_state.json unreadable -- the dashboard is blind"}
    acct = d.get("account") or {}
    age = acct.get("source_age_seconds")
    stamp = d.get("generated_at") or acct.get("source_updated_at") or ""
    stale = isinstance(age, (int, float)) and age > 3600
    res = d.get("research") or {}
    return {"status": "DEFECT" if stale else "OK",
            "generated_at": str(stamp)[:19], "source_age_s": age,
            "equity": acct.get("equity"), "canonical_survivors": res.get("canonical_survivors"),
            "why": ("the dashboard is serving figures older than an hour -- the desk pull is dead "
                    "and every number on the page is stale while looking current"
                    if stale else "dashboard current")}


def heal_forward_clocks() -> dict[str, Any]:
    """Clocks terminal on a drift that no longer exists are healed by RUNNING the engine.

    Not by rewriting a status. `shadow_forward` clears IDENTITY_BROKEN itself once `verify()`
    returns no drift, so the repair is to give it a pass -- on the box, where the live bars are.
    Rewriting the status here would empty this report and change nothing underneath, which is the
    failure mode a fixer that can hide its own failure always has.
    """
    st = _json(DESK / "reports" / "shadow" / "shadow_state.json")
    if st is None:
        return {"acted": False, "why": "shadow_state unreadable"}
    sl = st.get("sleeves") or st
    broken = [k for k, v in sl.items()
              if isinstance(v, dict) and str(v.get("status") or "") == "IDENTITY_BROKEN"]
    if not broken:
        return {"acted": False, "why": "no clock is terminal on identity"}
    try:
        subprocess.run(["systemctl", "--user", "start", "--no-block",
                        "quant-forward-box.service"], timeout=60, check=False)
    except (subprocess.SubprocessError, OSError) as exc:
        return {"acted": False, "why": f"could not trigger the engine: {type(exc).__name__}"}
    return {"acted": True, "identity_broken": len(broken),
            "why": ("triggered the forward engine on the trading box; it clears the status itself "
                    "when verify() finds no drift, so nothing here rewrites a verdict")}


def check_conversion() -> dict[str, Any]:
    """Every funnel stage's yield, and whether it is getting better or quietly rotting.

    THE DESK'S FAILURE MODE IS A LEGITIMATE-LOOKING ZERO. A crawler with 75 sources and 474MB of
    corpus that converts NOTHING reports exactly like a crawler that is switched off, and the
    deep audit returned 0/0/0/1 findings for days while running on schedule. So this measures the
    RATIO at each hop rather than whether the job ran.
    """
    out: dict[str, Any] = {}
    comp = _json(ROOT / "data" / "proposal_compiler.json") or {}
    ok, ref = comp.get("compiled"), comp.get("refused")
    if isinstance(ok, int) and isinstance(ref, int) and (ok + ref):
        rate = ok / (ok + ref)
        out["compile"] = {"compiled": ok, "refused": ref, "rate": round(rate, 3)}

    audit = _json(ROOT / "data" / "deep_audit.json") or {}
    lenses = audit.get("results") or {}
    found = sum(len(v.get("findings") or []) for v in lenses.values() if isinstance(v, dict))
    out["deep_audit"] = {"lenses": len(lenses), "findings": found, "ran_at": audit.get("ran_at")}

    free = _json(ROOT / "data" / "free_research.json") or {}
    props = sum(len(r.get("proposals") or []) for r in (free.get("results") or []))
    out["free_research"] = {"proposals": props, "ran_at": free.get("ran_at")}

    mc = _json(ROOT / "data" / "miner_conversion.json") or {}
    miners = mc.get("miners") or {}
    zero = len(mc.get("zero_yield_miners") or [])
    out["miners"] = {"total": len(miners), "zero_yield": zero}

    # A LENS THAT RETURNS NOTHING IS A DEFECT, not a clean audit. Measured 2026-09-04: all four
    # lenses read 0 for days because the parser scored the model's own instructions and the token
    # cap truncated the answer -- the job ran perfectly on schedule the whole time.
    bad = (found == 0 and len(lenses) > 0) or props == 0 or (
        "compile" in out and out["compile"]["rate"] < 0.10)
    out["status"] = "DEFECT" if bad else "OK"
    out["why"] = ("a funnel stage is yielding nothing while running on schedule -- the shape of a "
                  "silent zero, not of an honest negative result" if bad else "every stage yielding")
    return out


def check_funnel() -> dict[str, Any]:
    """Every hop from discovery to a running clock, and WHICH hop is dead.

    A funnel reported only at its ends cannot say where it broke. Measured this session: the
    crawler held 6,251 documents, the queue held 2,050 hypotheses, 94 compiled, 58 certified and
    0 clocks were accruing -- and each stage looked healthy from inside itself. The dead hop was
    the last one, and nothing named it because nothing compared the hops.

    STAGE-TO-STAGE, therefore. A hop whose input is large and whose output is zero is the defect,
    and it is reported with the repair that belongs to THAT hop rather than a generic alarm.
    """
    stages: dict[str, Any] = {}
    q = ROOT / "data" / "hypothesis_queue.jsonl"
    try:
        stages["queued"] = sum(1 for _ in q.open(encoding="utf-8")) if q.exists() else 0
    except OSError:
        stages["queued"] = None

    comp = _json(DESK / "data" / "hypotheses" / "compiled_proposals.json") or {}
    stages["compiled"] = len(comp.get("cells") or [])

    bt = _json(DESK / "data" / "hypotheses" / "external_backtest_results.json")
    stages["backtested"] = (len(bt) if isinstance(bt, list)
                            else len(bt.get("results") or bt.get("cells") or {})
                            if isinstance(bt, dict) else None)

    canon = _json(DESK / "data" / "UNIVERSAL_SURVIVORS.canon.json") or {}
    stages["certified"] = len(canon.get("survivors") or {})

    st = _json(DESK / "reports" / "shadow" / "shadow_state.json") or {}
    sl = st.get("sleeves") or st
    rows = [v for v in sl.values() if isinstance(v, dict)]
    stages["clocked"] = sum(1 for v in rows if str(v.get("status") or "") == "ACTIVE")
    stages["trades"] = sum(v.get("n", 0) or 0 for v in rows
                           if str(v.get("status") or "") == "ACTIVE")

    #: hop -> (input stage, output stage, what repairs THAT hop)
    hops = (("compile", "queued", "compiled", "scripts/compile_proposals.py"),
            ("backtest", "compiled", "backtested", "ops/run_external_pipeline.sh"),
            ("certify", "backtested", "certified", "scripts/certify_gauntlet.py"),
            ("enrol", "certified", "clocked", "ops/run_forward_on_box.sh"))
    dead = []
    for name, src, dst, repair in hops:
        a, b = stages.get(src), stages.get(dst)
        if a is None or b is None:
            continue
        if a > 0 and b == 0:
            dead.append({"hop": name, "in": a, "out": b, "repair": repair,
                         "why": f"{a} in, ZERO out -- this hop is where the desk stops"})
    return {"status": "DEFECT" if dead else "OK", "stages": stages, "dead_hops": dead,
            "why": ("a hop with input and no output is the defect; the stage before it is healthy "
                    "and the stage after it is starved" if dead else "every hop passing volume")}


def check_unit_log_dirs() -> dict:
    """A unit whose StandardOutput directory is missing dies BEFORE its process starts.

    systemd reports status=209/STDOUT and the journal says "Failed to set up standard output",
    which reads like a permissions problem and is nothing of the kind. Measured 2026-09-04: the
    migration to the 8GB box left /home/quant/logs uncreated and 118 launches died that way in 24
    hours -- among them hourly-controller, so edge_search_results.json went 15 hours stale while
    every health check reported the timer as firing on schedule. It was.

    This both CHECKS and REPAIRS, because a missing directory has exactly one correct response.
    """
    import re
    units = Path.home() / ".config" / "systemd" / "user"
    if not units.is_dir():
        return {"status": "OK", "why": "no user unit directory"}
    wanted: set[Path] = set()
    for unit in units.glob("*.service"):
        try:
            text = unit.read_text("utf-8")
        except OSError:
            continue
        for m in re.finditer(r"Standard(?:Output|Error)\s*=\s*[a-z]+:(\S+)", text):
            wanted.add(Path(m.group(1)).parent)
    created = []
    for d in sorted(wanted):
        if not d.is_dir():
            try:
                d.mkdir(parents=True, exist_ok=True)
                created.append(str(d))
            except OSError as exc:
                return {"status": "DEFECT", "missing": str(d),
                        "why": f"cannot create {d}: {type(exc).__name__}"}
    # REPAIRED, not merely reported: the directory is created, so the next launch survives.
    return {"status": "OK", "repaired": created, "checked": len(wanted),
            "why": (f"created {len(created)} missing unit log dir(s): {created}" if created
                    else f"all {len(wanted)} unit log dirs present")}


def next_growth_lever() -> dict[str, Any]:
    """The next lever for E[log W], ranked by MEASURED deficit rather than by opinion.

    Only the mechanical ones are acted on here. A lever with a trade-off -- lowering a gate,
    resizing live risk, changing what a certificate asserts -- is named and left for the principal,
    because an autonomous fixer that can relax its own bar will eventually relax it.
    """
    levers: list[dict[str, Any]] = []
    st = _json(DESK / "reports" / "shadow" / "shadow_state.json") or {}
    sl = st.get("sleeves") or st
    act = [v for v in sl.values() if isinstance(v, dict) and v.get("status") == "ACTIVE"]
    if act:
        days = max(1.0, max((v.get("days_active") or 0) for v in act))
        rate = sum(v.get("n", 0) or 0 for v in act) / len(act) / days
        need = 50.0 / 14.0
        if rate < need:
            levers.append({
                "lever": "forward throughput", "measured": f"{rate:.2f} trades/sleeve/day",
                "needed": f"{need:.2f}", "shortfall": f"{need / max(rate, 1e-9):.1f}x",
                "act": "AUTOMATIC: none -- breadth is the fix and adding sleeves is a research act",
                "why": "n>=50 within a 14-day window is unreachable at this rate"})

    canon = _json(DESK / "data" / "UNIVERSAL_SURVIVORS.canon.json") or {}
    survivors = canon.get("survivors") or {}
    fams: dict[str, int] = {}
    for v in survivors.values():
        f = str((v.get("shadow_spec") or {}).get("family") or "?")
        fams[f] = fams.get(f, 0) + 1
    if survivors:
        top = max(fams.values()) / len(survivors)
        if top > 0.30:
            levers.append({
                "lever": "book independence", "measured": f"{top:.1%} in one family",
                "needed": "<30%", "act": "AUTOMATIC: none -- needs absent families to certify",
                "why": ("concentration caps n_eff: fifty variants of one bet is one bet, and "
                        "E[log W] pays for INDEPENDENT bets")})

    comp = _json(ROOT / "data" / "proposal_compiler.json") or {}
    if isinstance(comp.get("refused"), int) and comp.get("refused"):
        levers.append({
            "lever": "proposal conversion",
            "measured": f"{comp.get('compiled')} compiled / {comp.get('refused')} refused",
            "act": "AUTOMATIC: the axis contract is enforced at generation; refusals re-measured "
                   "each pass",
            "why": "a refusal for an unresolved axis is fixable at the prompt; a duplicate is not"})
    return {"levers": levers, "n": len(levers),
            "note": ("ranked by measured deficit. Levers with a TRADE-OFF (lowering a gate, "
                     "resizing live risk, changing what a certificate asserts) are named and left "
                     "for the principal -- a fixer that may relax its own bar eventually will.")}


#: The modules the desk box RUNS. Drift here is silent and total: the box keeps executing the old
#: code while every log says the sync verified.
REMOTE_CRITICAL = (
    "desks/mt5/research/job_lock.py",
    "desks/mt5/research/sleeve_registry.py",
    "desks/mt5/research/shadow_forward.py",
    "desks/mt5/research/forward_reconcile.py",
    "desks/mt5/research/h1_source.py",
    "desks/mt5/research/orthogonal_sweep.py",
    "desks/mt5/research/edge_search.py",
    "desks/mt5/scripts/external_gauntlet.py",
    "desks/mt5/mt5desk/families.py",
    "desks/mt5/mt5desk/family_inputs.py",
)


def check_box_code_drift(repair: bool = True) -> dict[str, Any]:
    """Hash the modules the trading box RUNS against this repo, and re-ship what drifted.

    WHY, MEASURED 2026-09-04. The hourly pipeline reported `code sync verified: 14 module(s)
    byte-identical` at 09:05, 10:10 and 11:08 -- and at 13:20 the box was running a job_lock.py
    that predated the `need_mb` argument. external_gauntlet called
    `exclusive_job(..., need_mb=1200)`, threw TypeError on every single hourly run, and the
    pipeline logged `ten-gate gauntlet FAILED rc=255` and carried on. The desk produced 372
    executable candidates an hour that nothing could ever judge, while every sync log said the
    code was identical.

    A sync that verifies ONCE AN HOUR cannot see a writer that reverts a file between syncs. This
    checks the state that matters -- what is on the box RIGHT NOW -- and repairs it, because a
    stale module on the box that runs the gauntlet is worth more attention than a stale one here.
    """
    import subprocess as _sp
    try:
        # The probe is BUILT, not formatted: it runs on the box's Python 3.14 and must hash
        # git-blob-style so the digests compare directly with `git hash-object` here.
        probe = "\n".join([
            "import hashlib, os",
            "for rel in " + repr(list(REMOTE_CRITICAL)) + ":",
            "    p = rel.replace('/', os.sep)",
            "    try:",
            "        d = open(p, 'rb').read()",
            "    except OSError:",
            "        print(rel, 'ABSENT'); continue",
            "    h = hashlib.sha1(b'blob ' + str(len(d)).encode() + b'\\0' + d).hexdigest()",
            "    print(rel, h)",
        ])
        out = _sp.run(["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=15", "contabo-mt5",
                       "cd C:\\opt\\quant && py -3 -"],
                      input=probe, capture_output=True, text=True, timeout=180).stdout
    except (_sp.SubprocessError, OSError) as exc:
        return {"status": "UNKNOWN", "why": f"box unreachable ({type(exc).__name__})"}

    remote = {}
    for line in out.splitlines():
        parts = line.split()
        if len(parts) == 2 and parts[0] in REMOTE_CRITICAL:
            remote[parts[0]] = parts[1]
    if not remote:
        return {"status": "UNKNOWN", "why": "no hashes returned -- never a clean pass"}

    drifted, reshipped = [], []
    for rel, rh in remote.items():
        local = _sp.run(["git", "hash-object", rel], cwd=ROOT,
                        capture_output=True, text=True).stdout.strip()
        if local and local != rh:
            drifted.append(rel)
            if repair:
                r = _sp.run(["scp", "-q", "-o", "BatchMode=yes", rel,
                             f"contabo-mt5:C:/opt/quant/{rel}"], cwd=ROOT, timeout=120)
                if r.returncode == 0:
                    reshipped.append(rel)
    return {"status": "DEFECT" if drifted else "OK", "checked": len(remote),
            "drifted": drifted, "reshipped": reshipped,
            "why": ("the box was running code this repo does not have; a module stale THERE is "
                    "invisible to every check that reads only HERE" if drifted
                    else "every critical module on the box matches this repo")}


#: Proprietary inputs the box's families read, and the age past which each is a defect. These
#: are the desk's OWN data -- self-recorded tape, its broker's swap terms, its own cost surface --
#: which is the part no competitor has and the part nothing was watching.
PROP_INPUTS: tuple[tuple[str, float], ...] = (
    ("desks/mt5/data/carry_state.json", 48.0),
    ("desks/mt5/data/cost_surface.json", 72.0),
    ("desks/mt5/data/cot", 240.0),
    ("data/fred_macro.json", 72.0),
)


def check_proprietary_data() -> dict[str, Any]:
    """Freshness of the desk's OWN data, here and on the box that mines it.

    MEASURED 2026-09-04: carry_state.json was ABSENT on the trading box while 380KB of swap terms
    sat on the VPS; COT was 13 days old; cost_surface 6 days. Meanwhile `carry` sent 343
    candidates to the gauntlet and `cot_positioning` 10 -- families reading inputs that were stale
    or missing, and producing candidates anyway. Nothing errored, because a stale JSON loads
    perfectly. This is the fred_macro defect repeated three times, and it is invisible to any
    check that looks only at the machine the collector runs on.
    """
    import time as _t
    stale = []
    for rel, max_h in PROP_INPUTS:
        path = ROOT / rel
        if not path.exists():
            stale.append({"input": rel, "state": "ABSENT_LOCALLY"})
            continue
        newest = path.stat().st_mtime if path.is_file() else max(
            (f.stat().st_mtime for f in path.rglob("*") if f.is_file()), default=0.0)
        age_h = (_t.time() - newest) / 3600.0 if newest else 1e9
        if age_h > max_h:
            stale.append({"input": rel, "age_h": round(age_h, 1), "limit_h": max_h})
    return {"status": "DEFECT" if stale else "OK", "checked": len(PROP_INPUTS), "stale": stale,
            "why": ("the desk's own data is the part no competitor has; a family reading a stale "
                    "copy still emits candidates, and nothing errors"
                    if stale else "every proprietary input within its freshness budget")}


def check_failed_units() -> dict[str, Any]:
    try:
        out = subprocess.run(["systemctl", "--user", "list-units", "--state=failed",
                              "--no-legend", "--plain"],
                             capture_output=True, text=True, timeout=60).stdout
    except (subprocess.SubprocessError, OSError):
        return {"status": "UNKNOWN", "why": "systemctl unavailable"}
    units = [ln.split()[0] for ln in out.splitlines() if ln.strip()]
    return {"status": "DEFECT" if units else "OK", "failed": units[:12], "count": len(units)}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--report", action="store_true", help="audit only; run no repairer")
    a = ap.parse_args()
    now = datetime.now(tz=UTC)
    print(f"DESK INTEGRITY {now.isoformat(timespec='seconds')}")

    repairs: list[dict[str, Any]] = []
    if not a.report:
        for name, args in _REPAIRERS:
            rc, out = _run(args)
            acted = [ln.strip() for ln in out.splitlines()
                     if any(w in ln for w in ("RESTORED", "REPAIRED", "restored", "repaired"))]
            repairs.append({"check": name, "exit": rc, "acted": acted[:4]})
            print(f"  repair {name:20s} exit={rc}" + (f"  {acted[0][:80]}" if acted else ""))

    if not a.report:
        healed = heal_forward_clocks()
        repairs.append({"check": "forward clocks", "exit": 0,
                        "acted": [healed.get("why", "")] if healed.get("acted") else []})
        if healed.get("acted"):
            print(f"  repair forward clocks      {healed['identity_broken']} terminal clock(s) "
                  f"-- engine triggered on the box")

    checks = {
        "dashboard": check_dashboard(),
        # Runs FIRST among the repairs in spirit: a missing log directory kills units
        # before their process starts, so every other check downstream reports a healthy
        # timer firing into a job that never ran.
        "unit_log_dirs": check_unit_log_dirs(),
        "conversion": check_conversion(),
        "funnel": check_funnel(),
        "box_code_drift": check_box_code_drift(repair=not a.report),
        "proprietary_data": check_proprietary_data(),
        "uncommitted_code": check_uncommitted_code(),
        "record_pairs": check_record_pairs(),
        "forward_lane": check_forward_lane(),
        "bar_freshness": check_bar_freshness(),
        "failed_units": check_failed_units(),
    }
    for name, r in checks.items():
        extra = {k: v for k, v in r.items() if k not in ("status", "why")}
        print(f"  {r['status']:8s} {name:18s} {json.dumps(extra)[:110]}")
        if r["status"] != "OK" and r.get("why"):
            print(f"           -> {str(r['why'])[:150]}")

    lever = next_growth_lever()
    if lever["levers"]:
        print("\n  NEXT GROWTH LEVERS (measured deficit, largest first):")
        for lv in lever["levers"]:
            print(f"    {lv['lever']:22s} {str(lv.get('measured'))[:34]:34s} {lv['act'][:64]}")

    bad = [k for k, v in checks.items() if v["status"] == "DEFECT"]
    unknown = [k for k, v in checks.items() if v["status"] == "UNKNOWN"]
    OUT.write_text(json.dumps({"ran_at": now.isoformat(timespec="seconds"), "repairs": repairs,
                               "checks": checks, "defects": bad, "unknown": unknown,
                               "growth_levers": lever}, indent=1,
                              default=str), "utf-8")
    if not bad and not unknown:
        # A QUIET RUN IS THE POINT. On a healthy desk this says so in one line and does nothing --
        # a sweep that always finds something to do trains its reader to stop looking.
        print("\n  ALL CLEAR -- every pair agrees, no evidence frozen, nothing repaired")
    else:
        print(f"\n  {len(bad)} defect(s), {len(unknown)} unmeasured -> {OUT}")
    return 1 if (bad or unknown) else 0


if __name__ == "__main__":
    raise SystemExit(main())

```
