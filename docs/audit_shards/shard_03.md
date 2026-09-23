# AUDIT SHARD 3/24 -- seat google/gemma-4-26b-a4b-it

You are reviewing SOURCE CODE, not a summary. Previous panels received a 13,185-char self-description and never saw the code; that is why this exists.

- TIER 1 (money path) is included IN FULL and is sent to every seat: 44 files. A defect here costs money.
- TIER 2 is YOUR SHARD ALONE: 12 files. No other seat sees these, so anything you miss here is missed entirely.
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

### libs\discretionary\rules.py
```python
"""THE PRINCIPAL'S PLAYBOOK AS DETECTORS -- H1, H2, H6-H11, to the pre-registered terms.

`docs/research/DISCRETIONARY_PLAYBOOK_PREREGISTRATION.md` fixed the thresholds on 2026-08-04,
before any of these had been backtested here. This module implements them and CHANGES NONE OF
THEM. Where the pre-registration names a number -- RSI 70/30, 0.3xATR(14) tolerance, >=2 touches
in 90 days, Donchian(20), 1.5xSMA20(volume), Bollinger(20,2), the three UTC sessions -- that number
appears here verbatim. Reading the data first and then picking a threshold is the one move that
would void every result this family ever produces.

WHERE THE PRE-REGISTRATION IS SILENT, THE CHOICE IS MADE HERE AND MARKED. H1 and H2 specify entries
and exits precisely; H6-H11 are registered as one-line testable cores, so their detector geometry
had to be fixed somewhere. It is fixed HERE, in code, dated, before any of them has been run
against the lake -- which is what pre-registration requires. Each such choice carries a
`# PRE-REGISTERED 2026-08-15` marker so a later reader can tell a playbook number from a desk one.

**H4 AND H5 READ THE MOAT TAPE, NOT THE CANDLES.** The pre-registration marks both BLOCKED on
recorder bringup -- true when written, stale since: the recorders have been taping every aggTrade
with its maker flag for weeks. They are implemented here against `libs.discretionary.tape`, which
is the real signed flow, and NOT against an OHLCV proxy. A candle-derived CVD would be a different
hypothesis wearing this one's name and carrying its priority.

**EVERY DETECTOR RETURNS SETUPS, NEVER ORDERS.** Direction, entry, stop and target -- the same
shape `libs/ict` produces, so one adapter serves all of them and no rule gets its own order path.
"""

from __future__ import annotations

import itertools
from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd

from libs.discretionary import tape

__all__ = [
    "BLOCKED",
    "BOOK_RULES",
    "READY",
    "Setup",
    "detect",
    "h1_structural_fade",
    "h2_volume_breakout",
    "h4_auction_value",
    "h5_cvd_divergence",
    "h6_wyckoff",
    "h7_vwap_reversion",
    "h8_supply_demand",
    "h9_opening_range",
    "h10_vol_compression",
    "h11_band_fade",
    "h12_book_pressure",
]

#: Nothing is blocked any more, and the empty dict is the finding. The pre-registration marked H4
#: and H5 "BLOCKED: recorder bringup (operator)" on 2026-08-04 -- true then. The recorders have
#: been taping every aggTrade with its maker flag since, so the inputs arrived and the label did
#: not change. Kept as a named, empty mapping so anything asking "what is still blocked" gets an
#: answer rather than an AttributeError, and so the next genuine block has somewhere to go.
BLOCKED: dict[str, str] = {}


@dataclass(frozen=True)
class Setup:
    """One detected trade story. Mirrors `libs.ict.strategy.ICTSetup` so a single adapter turns
    any rule in this family into a sized intent."""

    rule_id: str
    direction: int          # +1 long, -1 short
    entry_price: float
    stop: float
    target: float
    bar: int
    note: str


# --------------------------------------------------------------------------------------------
# indicators. Deliberately plain: every one of these has a dozen variants, and a variant chosen
# after seeing results is a threshold chosen after seeing results.
# --------------------------------------------------------------------------------------------

def _atr(b: pd.DataFrame, n: int = 14) -> pd.Series:
    pc = b["close"].shift(1)
    tr = pd.concat([b["high"] - b["low"], (b["high"] - pc).abs(), (b["low"] - pc).abs()],
                   axis=1).max(axis=1)
    return tr.rolling(n).mean()


def _rsi(close: pd.Series, n: int = 14) -> pd.Series:
    d = close.diff()
    up = d.clip(lower=0.0).ewm(alpha=1.0 / n, adjust=False).mean()
    dn = (-d.clip(upper=0.0)).ewm(alpha=1.0 / n, adjust=False).mean()
    rs = up / dn.replace(0.0, np.nan)
    return (100.0 - 100.0 / (1.0 + rs)).fillna(50.0)


def _psar(b: pd.DataFrame, af0: float = 0.02, afmax: float = 0.2) -> pd.Series:
    """Parabolic SAR at the playbook's own defaults (0.02/0.2) -- H2 names them explicitly."""
    high, low = b["high"].to_numpy(), b["low"].to_numpy()
    n = len(b)
    out = np.full(n, np.nan)
    if n < 3:
        return pd.Series(out, index=b.index)
    bull, af, ep, sar = True, af0, high[0], low[0]
    for i in range(1, n):
        sar = sar + af * (ep - sar)
        if bull:
            sar = min(sar, low[i - 1], low[max(0, i - 2)])
            if low[i] < sar:
                bull, sar, ep, af = False, ep, low[i], af0
            elif high[i] > ep:
                ep, af = high[i], min(af + af0, afmax)
        else:
            sar = max(sar, high[i - 1], high[max(0, i - 2)])
            if high[i] > sar:
                bull, sar, ep, af = True, ep, high[i], af0
            elif low[i] < ep:
                ep, af = low[i], min(af + af0, afmax)
        out[i] = sar
    return pd.Series(out, index=b.index)


def _last(s: pd.Series, i: int) -> float:
    v = s.iloc[i]
    return float(v) if pd.notna(v) else float("nan")


# --------------------------------------------------------------------------------------------
# H1 -- structural-level fade with RSI extreme. Every number below is from the pre-registration.
# --------------------------------------------------------------------------------------------

def h1_structural_fade(b: pd.DataFrame, *, window: int = 90, touches: int = 2,
                       tol_atr: float = 0.3, rsi_hi: float = 70.0,
                       rsi_lo: float = 30.0, stop_atr: float = 2.0) -> list[Setup]:
    """Level touched >=2x in 90 days within 0.3xATR(14); fade on RSI(14) >=70 / <=30.

    MECHANISM: resting liquidity at a repeatedly-tested level absorbs an exhausted push. The
    pre-registration's falsification is explicit -- H1 dies if this is indistinguishable from the
    unconditional short-vol payoff it resembles -- so nothing here tries to rescue it.
    """
    if len(b) < window + 20:
        return []
    atr, rsi = _atr(b), _rsi(b["close"])
    out: list[Setup] = []
    i = len(b) - 1
    px, a = float(b["close"].iloc[i]), _last(atr, i)
    if not np.isfinite(a) or a <= 0:
        return []
    tol = tol_atr * a
    hist = b.iloc[max(0, i - window):i]
    hi_touch = int((hist["high"] - px).abs().le(tol).sum())
    lo_touch = int((hist["low"] - px).abs().le(tol).sum())
    r = _last(rsi, i)
    if hi_touch >= touches and r >= rsi_hi:
        opp = float(hist["low"].min())
        out.append(Setup("H1_structural_fade", -1, px, px + stop_atr * a, opp, i,
                         f"{hi_touch} touches within {tol_atr}xATR over {window}d, RSI {r:.0f}"))
    elif lo_touch >= touches and r <= rsi_lo:
        opp = float(hist["high"].max())
        out.append(Setup("H1_structural_fade", +1, px, px - stop_atr * a, opp, i,
                         f"{lo_touch} touches within {tol_atr}xATR over {window}d, RSI {r:.0f}"))
    return out


# --------------------------------------------------------------------------------------------
# H2 -- breakout with volume confirmation, Donchian(20) + 1.5x SMA20(volume), PSAR trail.
# --------------------------------------------------------------------------------------------

def h2_volume_breakout(b: pd.DataFrame, *, n: int = 20, vol_mult: float = 1.5) -> list[Setup]:
    """Donchian(20) break confirmed by volume >= 1.5xSMA20(volume); PSAR(0.02/0.2) is the stop.

    THE ABLATION IS THE POINT. H2 dies if volume confirmation adds nothing over the bare break, so
    the volume test is a hard gate here rather than a score -- an un-gated version is a DIFFERENT
    arm and must be run as one, not blended in.
    """
    if len(b) < n + 25 or "volume" not in b:
        return []
    i = len(b) - 1
    prior = b.iloc[i - n:i]
    hi, lo = float(prior["high"].max()), float(prior["low"].min())
    v, vma = float(b["volume"].iloc[i]), float(b["volume"].rolling(n).mean().iloc[i])
    if not np.isfinite(vma) or vma <= 0 or v < vol_mult * vma:
        return []
    px = float(b["close"].iloc[i])
    sar = _last(_psar(b), i)
    if not np.isfinite(sar):
        return []
    width = hi - lo
    if px > hi:
        # PRE-REGISTERED 2026-08-15: target = one channel width projected from the break. The
        # playbook fixes the TRAIL as the exit structure and leaves the objective open; a channel
        # width is the only scale the setup itself provides, so no new parameter enters.
        return [Setup("H2_volume_breakout", +1, px, min(sar, lo), px + width, i,
                      f"Donchian({n}) high break on {v / vma:.1f}x volume")]
    if px < lo:
        return [Setup("H2_volume_breakout", -1, px, max(sar, hi), px - width, i,
                      f"Donchian({n}) low break on {v / vma:.1f}x volume")]
    return []


# --------------------------------------------------------------------------------------------
# H6 -- Wyckoff spring / upthrust after a range.
# --------------------------------------------------------------------------------------------

def h6_wyckoff(b: pd.DataFrame, *, range_bars: int = 20, max_range_atr: float = 3.0,
               recover_bars: int = 2) -> list[Setup]:
    """Spring: price breaks a >=20-bar range LOW and closes back inside within 2 bars. Upthrust
    mirrors it.

    PRE-REGISTERED 2026-08-15: `range_bars=20`, `max_range_atr=3.0`, `recover_bars=2`. The
    pre-registration registers the CORE ("spring/upthrust after accumulation/distribution ranges")
    and leaves the geometry open; these fix it before the first run.

    THE RECOVERY IS THE WHOLE SIGNAL. A break that stays broken is a trend, not a spring, and
    counting it here would merge two opposite mechanisms into one row.
    """
    if len(b) < range_bars + 25:
        return []
    i = len(b) - 1
    a = _last(_atr(b), i)
    if not np.isfinite(a) or a <= 0:
        return []
    base = b.iloc[i - range_bars - recover_bars:i - recover_bars]
    hi, lo = float(base["high"].max()), float(base["low"].min())
    if (hi - lo) > max_range_atr * a:
        return []                        # not a range: a trend cannot spring
    recent = b.iloc[i - recover_bars:i + 1]
    px = float(b["close"].iloc[i])
    if float(recent["low"].min()) < lo and lo < px < hi:
        return [Setup("H6_wyckoff_spring", +1, px, float(recent["low"].min()) - 0.1 * a, hi, i,
                      f"spring: broke {range_bars}-bar low {lo:.4g}, recovered inside")]
    if float(recent["high"].max()) > hi and lo < px < hi:
        return [Setup("H6_wyckoff_upthrust", -1, px, float(recent["high"].max()) + 0.1 * a, lo, i,
                      f"upthrust: broke {range_bars}-bar high {hi:.4g}, rejected back inside")]
    return []


# --------------------------------------------------------------------------------------------
# H7 -- VWAP reversion with a slope trend filter.
# --------------------------------------------------------------------------------------------

def h7_vwap_reversion(b: pd.DataFrame, *, n: int = 20, dev: float = 2.0,
                      slope_bars: int = 10) -> list[Setup]:
    """Rolling VWAP(20); fade a >=2-sigma deviation, but only WITH the VWAP slope.

    PRE-REGISTERED 2026-08-15: `n=20`, `dev=2.0`, `slope_bars=10`. The registration names
    "session-VWAP reversion and VWAP-slope trend filter"; on a 24/7 tape there is no session, so a
    rolling window stands in and the substitution is stated rather than hidden.

    THE SLOPE FILTER IS A GATE, NOT A TIEBREAK. Fading a deviation against a trending VWAP is the
    losing half of this trade, and blending it in would average a mechanism with its own inverse.
    """
    if len(b) < n + slope_bars + 5 or "volume" not in b:
        return []
    tp = (b["high"] + b["low"] + b["close"]) / 3.0
    pv = (tp * b["volume"]).rolling(n).sum()
    vv = b["volume"].rolling(n).sum().replace(0.0, np.nan)
    vwap = pv / vv
    resid = (b["close"] - vwap).rolling(n).std()
    i = len(b) - 1
    w, s, px = _last(vwap, i), _last(resid, i), float(b["close"].iloc[i])
    if not (np.isfinite(w) and np.isfinite(s)) or s <= 0:
        return []
    slope = w - _last(vwap, i - slope_bars)
    z = (px - w) / s
    if z <= -dev and slope >= 0:
        return [Setup("H7_vwap_reversion", +1, px, px - dev * s, w, i,
                      f"{z:.1f} sigma below VWAP({n}) with slope up")]
    if z >= dev and slope <= 0:
        return [Setup("H7_vwap_reversion", -1, px, px + dev * s, w, i,
                      f"{z:.1f} sigma above VWAP({n}) with slope down")]
    return []


# --------------------------------------------------------------------------------------------
# H8 -- supply/demand zones: departure, base, return.
# --------------------------------------------------------------------------------------------

def h8_supply_demand(b: pd.DataFrame, *, base_bars: int = 3, base_atr: float = 1.0,
                     impulse_atr: float = 2.0, lookback: int = 60) -> list[Setup]:
    """Zone = the BASE that preceded an impulsive departure; the trade is the first return to it.

    PRE-REGISTERED 2026-08-15: `base_bars=3`, `base_atr=1.0`, `impulse_atr=2.0`, `lookback=60`.
    The registration defines the zone as "the base before an impulsive move" and leaves the
    magnitudes open.

    THE DEPARTURE IS WHAT MAKES IT A ZONE. A narrow range with nothing after it is just quiet
    tape, and admitting those would fill the book with every consolidation on the chart.
    """
    if len(b) < lookback + base_bars + 5:
        return []
    atr = _atr(b)
    i = len(b) - 1
    px = float(b["close"].iloc[i])
    a = _last(atr, i)
    if not np.isfinite(a) or a <= 0:
        return []
    for j in range(i - lookback, i - base_bars - 1):
        base = b.iloc[j:j + base_bars]
        aj = _last(atr, j + base_bars)
        if not np.isfinite(aj) or aj <= 0:
            continue
        bh, bl = float(base["high"].max()), float(base["low"].min())
        if (bh - bl) > base_atr * aj:
            continue
        nxt = float(b["close"].iloc[j + base_bars])
        if nxt - bh >= impulse_atr * aj and bl <= px <= bh:
            return [Setup("H8_demand_zone", +1, px, bl - 0.25 * a, bh + impulse_atr * a, i,
                          f"return to demand base [{bl:.4g},{bh:.4g}] after impulsive departure")]
        if bl - nxt >= impulse_atr * aj and bl <= px <= bh:
            return [Setup("H8_supply_zone", -1, px, bh + 0.25 * a, bl - impulse_atr * a, i,
                          f"return to supply base [{bl:.4g},{bh:.4g}] after impulsive departure")]
    return []


# --------------------------------------------------------------------------------------------
# H9 -- opening-range breakout. THE THREE SESSIONS ARE PRE-REGISTERED AND THERE ARE ONLY THREE.
# --------------------------------------------------------------------------------------------

#: "crypto has no bell -- session definitions (00:00 UTC, US open, Asia open) are pre-registered as
#: the ONLY three tested". Adding a fourth later is a new trial, counted as one.
SESSIONS_UTC: dict[str, int] = {"utc_midnight": 0, "asia_open": 1, "us_open": 13}


def h9_opening_range(b: pd.DataFrame, *, session: str = "utc_midnight", range_bars: int = 4,
                     vol_mult: float = 1.5) -> list[Setup]:
    """Opening-range break for one of the three registered sessions, volume-confirmed.

    NEEDS INTRADAY BARS AND SAYS SO. An "opening range" on daily candles is the day itself, which
    is not the hypothesis -- so this returns nothing unless the index carries intraday timestamps,
    and the caller reports UNAVAILABLE rather than a silent empty list.
    """
    if session not in SESSIONS_UTC or "volume" not in b or len(b) < range_bars + 25:
        return []
    idx = b.index
    if not isinstance(idx, pd.DatetimeIndex):
        return []
    if len(idx) > 1 and (idx[-1] - idx[-2]) >= pd.Timedelta(hours=23):
        return []                        # daily bars: no opening range exists to break
    hour = SESSIONS_UTC[session]
    today = idx[-1].normalize()
    opening = b[(idx >= today + pd.Timedelta(hours=hour))
                & (idx < today + pd.Timedelta(hours=hour) + pd.Timedelta(hours=range_bars))]
    if len(opening) < 2:
        return []
    hi, lo = float(opening["high"].max()), float(opening["low"].min())
    i = len(b) - 1
    px, v = float(b["close"].iloc[i]), float(b["volume"].iloc[i])
    vma = float(b["volume"].rolling(20).mean().iloc[i])
    if not np.isfinite(vma) or vma <= 0 or v < vol_mult * vma:
        return []
    width = hi - lo
    if px > hi:
        return [Setup(f"H9_orb_{session}", +1, px, lo, px + width, i,
                      f"{session} opening range [{lo:.4g},{hi:.4g}] broken up on "
                      f"{v / vma:.1f}x volume")]
    if px < lo:
        return [Setup(f"H9_orb_{session}", -1, px, hi, px - width, i,
                      f"{session} opening range [{lo:.4g},{hi:.4g}] broken down on "
                      f"{v / vma:.1f}x volume")]
    return []


# --------------------------------------------------------------------------------------------
# H10 -- volatility compression: BB squeeze / NR7 -> expansion.
# --------------------------------------------------------------------------------------------

def h10_vol_compression(b: pd.DataFrame, *, n: int = 20, k: float = 2.0,
                        squeeze_window: int = 60) -> list[Setup]:
    """Bollinger(20,2) bandwidth at a 60-bar low, or NR7, then trade the EXPANSION direction.

    PRE-REGISTERED 2026-08-15: `squeeze_window=60`. Bollinger(20,2) and NR7 come from the
    registration itself.

    THE DIRECTION COMES FROM THE EXPANSION, NEVER FROM THE SQUEEZE. A compression is direction-free
    by construction, and picking a side before the break is where this family usually invents an
    edge it does not have.
    """
    if len(b) < squeeze_window + n + 5:
        return []
    ma = b["close"].rolling(n).mean()
    sd = b["close"].rolling(n).std()
    bw = (2 * k * sd / ma.replace(0.0, np.nan))
    i = len(b) - 1
    rng = b["high"] - b["low"]
    nr7 = bool(rng.iloc[i - 1] == rng.iloc[i - 7:i].min()) if i >= 7 else False
    prior_bw = bw.iloc[i - squeeze_window:i]
    squeezed = bool(pd.notna(bw.iloc[i - 1]) and len(prior_bw.dropna()) > 5
                    and bw.iloc[i - 1] <= prior_bw.quantile(0.10))
    if not (squeezed or nr7):
        return []
    px, upper, lower = float(b["close"].iloc[i]), _last(ma + k * sd, i), _last(ma - k * sd, i)
    if not (np.isfinite(upper) and np.isfinite(lower)):
        return []
    width = upper - lower
    if px > upper:
        return [Setup("H10_vol_compression", +1, px, lower, px + width, i,
                      f"expansion up from {'NR7' if nr7 else 'BB squeeze'}")]
    if px < lower:
        return [Setup("H10_vol_compression", -1, px, upper, px - width, i,
                      f"expansion down from {'NR7' if nr7 else 'BB squeeze'}")]
    return []


# --------------------------------------------------------------------------------------------
# H11 -- band fade. Registered LAST deliberately (L0054), tested all the same.
# --------------------------------------------------------------------------------------------

def h11_band_fade(b: pd.DataFrame, *, n: int = 20, z: float = 2.0) -> list[Setup]:
    """Z-score fade at band extremes.

    PRE-REGISTERED 2026-08-15: `n=20`, `z=2.0`. Registered last because three independent methods
    rank mean-reversion last on crypto (L0054) -- the prior sets EFFORT ORDER and never the bar, so
    this is tested on the same terms as everything above it.
    """
    if len(b) < n + 5:
        return []
    ma = b["close"].rolling(n).mean()
    sd = b["close"].rolling(n).std()
    i = len(b) - 1
    m, s, px = _last(ma, i), _last(sd, i), float(b["close"].iloc[i])
    if not (np.isfinite(m) and np.isfinite(s)) or s <= 0:
        return []
    zz = (px - m) / s
    if zz <= -z:
        return [Setup("H11_band_fade", +1, px, px - z * s, m, i, f"z {zz:.1f} at lower band")]
    if zz >= z:
        return [Setup("H11_band_fade", -1, px, px + z * s, m, i, f"z {zz:.1f} at upper band")]
    return []


#: Every implemented rule, by the id the journal and the multiplicity ledger use. H3 lives in
#: `libs/ict` and is added by the runner, which owns that import.
READY: dict[str, Any] = {
    "H1_structural_fade": h1_structural_fade,
    "H2_volume_breakout": h2_volume_breakout,
    "H6_wyckoff": h6_wyckoff,
    "H7_vwap_reversion": h7_vwap_reversion,
    "H8_supply_demand": h8_supply_demand,
    "H9_opening_range": h9_opening_range,
    "H10_vol_compression": h10_vol_compression,
    "H11_band_fade": h11_band_fade,
}


def detect(b: pd.DataFrame, rules: list[str] | None = None) -> list[Setup]:
    """Run the named rules (all READY ones by default) over one symbol's bars.

    A DETECTOR THAT RAISES MUST NOT SILENCE THE REST. One malformed frame taking out the whole
    family would read as "no setups today", which is a different and false claim.
    """
    out: list[Setup] = []
    for name in (rules or list(READY)):
        fn = READY.get(name)
        if fn is None:
            continue
        try:
            out.extend(fn(b))
        except Exception:
            continue
    return out


# --------------------------------------------------------------------------------------------
# H4 / H5 -- the two that needed the tape. Both take a TapeProfile the caller has already loaded,
# so one gzip pass serves both and they can never describe different windows.
# --------------------------------------------------------------------------------------------

def _tape_atr(bars: Any, lookback: int = 14) -> float:
    """True range over the TAPE's own bars. A stop for a tape-time rule must be sized in tape
    time -- a daily ATR on an hourly signal is a stop roughly five times wider than the move the
    rule is claiming, which quietly turns a fade into a hold-and-hope."""
    window = list(bars)[-(lookback + 1):]
    if len(window) < 2:
        return 0.0
    trs = []
    for prev, cur in itertools.pairwise(window):
        trs.append(max(cur.high - cur.low, abs(cur.high - prev.close), abs(cur.low - prev.close)))
    return float(np.mean(trs)) if trs else 0.0


def h4_auction_value(profile: Any = None, *, stop_frac: float = 0.5) -> list[Setup]:
    """Acceptance/rejection at the value area: fade a print OUTSIDE the area back toward the POC.

    MECHANISM, as registered: price outside the value area is an auction that has not been
    accepted, and unaccepted prices revert to where volume actually traded. Price INSIDE the area
    is doing what it should and is not a signal.

    **THE PRICE IS THE TAPE'S LAST PRINT, NOT A CANDLE CLOSE.** The profile is built from the last
    day of prints; comparing it against a DAILY bar's close asks whether a level that may be
    twenty hours old sits outside an auction measured to the minute. The two objects have to be
    read from the same window or the comparison is between different days.

    PRE-REGISTERED 2026-08-15: `stop_frac=0.5` -- the stop sits half a value-area width beyond the
    edge that was broken. The registration fixes POC/VAH/VAL and the reversion claim; the stop
    geometry is fixed here, before the first run.
    """
    if profile is None:
        return []
    px = float(getattr(profile, "last_price", 0.0) or 0.0)
    width = float(profile.vah - profile.val)
    if width <= 0 or px <= 0:
        return []
    i = max(0, len(getattr(profile, "bars", ())) - 1)
    if px > profile.vah:
        return [Setup("H4_auction_value", -1, px, px + stop_frac * width, profile.poc, i,
                      f"print above VAH {profile.vah:.6g}, unaccepted -> POC {profile.poc:.6g}")]
    if px < profile.val:
        return [Setup("H4_auction_value", +1, px, px - stop_frac * width, profile.poc, i,
                      f"print below VAL {profile.val:.6g}, unaccepted -> POC {profile.poc:.6g}")]
    return []


def h5_cvd_divergence(profile: Any = None, *, lookback: int = 10,
                      stop_atr: float = 1.5) -> list[Setup]:
    """Delta divergence: price makes a new extreme over the window and CUMULATIVE FLOW DOES NOT.

    MECHANISM, as registered: a new high the aggressive buyers did not fund is a push carried by
    makers -- the move is being sold into, and the level is more likely to fail than extend. That
    statement is unavailable from OHLCV at any resolution, which is why this hypothesis waited for
    the tape and why it is the one rule on the desk whose input nothing else can see.

    **A LEVEL IS NOT A DIVERGENCE, AND THE FIRST VERSION TESTED A LEVEL.** It fired a short on
    `cvd < 0` -- the sign of one scalar over the whole window. On a tape with any persistent
    imbalance that scalar keeps one sign for days, so the rule was "new high while the day happens
    to be net-sold", which fires constantly in one regime and never in the other. The registered
    claim is comparative: price sets a higher high, cumulative delta does not. That needs the
    SERIES, and it needs both series on one grid -- `profile.bars`, built in the same pass.

    PRE-REGISTERED 2026-08-15: `lookback=10`, `stop_atr=1.5`.
    """
    if profile is None:
        return []
    bars = list(getattr(profile, "bars", ()))
    if len(bars) < lookback + 2:
        return []
    cum = list(profile.cum_delta())
    i = len(bars) - 1
    a = _tape_atr(bars)
    if not np.isfinite(a) or a <= 0:
        return []
    px = float(bars[i].close)
    prior = bars[i - lookback:i]
    prior_cum = cum[i - lookback:i]
    if px >= max(x.high for x in prior) and cum[i] < max(prior_cum):
        return [Setup("H5_cvd_divergence", -1, px, px + stop_atr * a, px - 2.0 * a, i,
                      f"new {lookback}-bar high, cum delta {cum[i]:,.2f} BELOW its own "
                      f"{lookback}-bar high {max(prior_cum):,.2f} -- the push was not funded")]
    if px <= min(x.low for x in prior) and cum[i] > min(prior_cum):
        return [Setup("H5_cvd_divergence", +1, px, px - stop_atr * a, px + 2.0 * a, i,
                      f"new {lookback}-bar low, cum delta {cum[i]:,.2f} ABOVE its own "
                      f"{lookback}-bar low {min(prior_cum):,.2f} -- the flush was not funded")]
    return []


def h12_book_pressure(profile: Any = None, *, books: Any = None, z_entry: float = 1.5,
                      min_obs: int = 60) -> list[Setup]:
    """ORDERBOOK MICROSTRUCTURE STATE -- the class the census rates 0.90, on data already on disk.

    PRE-REGISTERED 2026-08-15, before any backtest.

    THE PAYER, and he is named by the census rather than invented here: an impatient taker who
    pays a spread the book's state had ALREADY widened, and a resting order that was there to be
    hit. Liquidity provision is priced by the state of the book at the moment demand arrives, and
    that state is observable BEFORE the trade rather than inferred after it.

    MECHANISM CLAIM. Depth imbalance is short-horizon pressure: when resting size is
    overwhelmingly on one side, the thin side is where price goes, because that is the side an
    impatient order walks through. The claim is about IMMEDIACY, not value -- it decays in
    minutes and it is the reason this class sits at 0.90 orthogonality against a library of price
    patterns that all read the same closes.

    **THE FILTER IS THE HYPOTHESIS, NOT A TUNING KNOB.** Imbalance alone is famously contaminated
    by spoofing and by the mechanical rebuild after a sweep. The registered form requires a STEEP
    book as well: pressure only counts when size is genuinely stacked near the touch, because a
    flat book with a lopsided total is a book about to be cancelled. Both conditions, or no trade.

    DEGRADES TO FLAT without depth snapshots, exactly like every other moat rule. An imbalance
    computed from an absent book would be a claim about a market nobody observed.
    """
    rows = list(books or ())
    if profile is None or len(rows) < min_obs:
        return []
    imb = np.array([b.imbalance for b in rows], dtype="float64")
    slope = np.array([b.slope for b in rows], dtype="float64")
    # PAST-ONLY STATISTICS. A z-score against the whole sample lets a later regime decide what
    # counted as extreme today -- the same lookahead the Hawkes event threshold avoids.
    hist_i, hist_s = imb[:-1], slope[:-1]
    sd = float(hist_i.std())
    if sd <= 0 or not np.isfinite(sd):
        return []
    z = (float(imb[-1]) - float(hist_i.mean())) / sd
    steep = float(slope[-1]) > float(np.median(hist_s))
    if not steep or abs(z) < z_entry:
        return []
    last = rows[-1]
    px = float(last.mid)
    if px <= 0 or last.spread_bps <= 0:
        return []
    # THE STOP IS THE SPREAD, SCALED. An immediacy claim that has not paid within a few multiples
    # of the cost of demanding liquidity is a claim that was wrong, and a wider stop would hold a
    # microstructure position long past the horizon its mechanism describes.
    stop_frac = max(3.0 * last.spread_bps / 10_000.0, 0.002)
    direction = 1 if z > 0 else -1
    return [Setup("H12_book_pressure", direction, px,
                  px * (1 - direction * stop_frac), px * (1 + direction * 2 * stop_frac),
                  len(rows) - 1,
                  f"depth imbalance z={z:+.2f} on a book steeper than its own median "
                  f"(slope {last.slope:,.0f}, spread {last.spread_bps:.1f}bps) -- the thin side "
                  "is where an impatient order walks")]


#: The two rules that consume the tape rather than the candles. THEY TAKE NO DATAFRAME: every
#: number they use -- price, extremes, flow, ATR -- comes off the tape, so there is no seam at
#: which a candle window and a tape window can disagree. `detect` cannot run them because the
#: caller owns the gzip read, and a rule that silently returned nothing when its input was missing
#: would be indistinguishable from a rule that found nothing.
TAPE_RULES: dict[str, Any] = {
    "H4_auction_value": h4_auction_value,
    "H5_cvd_divergence": h5_cvd_divergence,
}

#: Rules that need the DEPTH rows rather than the trade rows. Kept separate because they take a
#: second argument the trade-only rules do not, and because a caller that has trades but no book
#: must run the first set rather than silently skip both.
BOOK_RULES: dict[str, Any] = {
    "H12_book_pressure": h12_book_pressure,
}


def detect_with_tape(profile: Any, *, now_ms: int | None = None,
                     max_age_h: float | None = None, books: Any = None) -> list[Setup]:
    """H4 and H5 for one symbol, given the profile the caller loaded.

    **A STALE TAPE IS REFUSED, NOT FADED.** If a recorder unit stops, the newest partition simply
    stops advancing and every function here keeps returning clean numbers about yesterday's
    auction. Fading the value area of a session that has already ended is a different hypothesis
    from the registered one, and it would be indistinguishable in the artifact.

    Empty when profile is None, and the caller reports that as NO TAPE rather than as no setups.
    """
    if profile is None:
        return []
    limit = tape.MAX_TAPE_AGE_H if max_age_h is None else max_age_h
    if hasattr(profile, "fresh") and not profile.fresh(now_ms, max_age_h=limit):
        return []
    out: list[Setup] = []
    for fn in TAPE_RULES.values():
        out.extend(fn(profile))
    # THE DEPTH ROWS, WHICH NOTHING READ UNTIL 2026-08-15. Absent `books`, these produce nothing
    # and the caller reports NO BOOK -- distinct from NO TAPE, because the recorder can be writing
    # trades while the depth poll is failing and those are different repairs.
    for fn in BOOK_RULES.values():
        out.extend(fn(profile, books=books))
    return out

```

### libs\hypmax\ontology.py
```python
"""THE RESEARCH ONTOLOGY -- a self-expanding exploration frontier, not a static checklist.

THE PRINCIPAL'S FRAMEWORK (2026-08-01), and its own addendum is the part that matters: turn the
question set into an ONTOLOGY rather than a list, so that

  * every new dataset maps automatically to the questions it can answer,
  * every failed hypothesis raises the EXHAUSTION of the question it came from,
  * every survivor SPAWNS second-order questions that did not exist before,
  * and the system measures coverage per question and prioritises the least-explored,
    highest-expected-value frontier without anyone maintaining a spreadsheet.

That converts a finite list into a search space that grows as it is explored. A checklist is
consumed; an ontology compounds.

WHY THIS IS NOT MORE GOVERNANCE. This desk has 59 audit checks and zero deployed alphas, and the
standing constraint says never add subsystems that do not increase future compounded capital. The
justification here is specific and measurable: the desk has generated 420 hypotheses and cannot
say which regions of the hypothesis space they covered, so it cannot tell "we tested this and it
failed" from "we never looked". Those demand opposite responses. Coverage is the one piece of
information that makes 420 failures INFORMATIVE rather than merely discouraging.

RESEARCH OPTIONALITY MAXIMISATION -- the constitutional addition, and the reason `optionality` is
a first-class term rather than a nice-to-have. A discovery is worth its own alpha PLUS the
research frontier it unlocks. A question that, if answered, opens a new dataset, a new mechanism
family or a new market is worth more than one that closes a leaf, even at equal immediate value,
because it raises the GROWTH RATE of future discovery rather than harvesting the current stock.
Today's discovery making tomorrow's search space larger is what turns research into a compounding
process instead of a depleting one.

Pure and dependency-free. Scores and prioritises; discovers nothing, promotes nothing.
"""

from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

__all__ = [
    "DOMAINS",
    "SEED_QUESTIONS",
    "Question",
    "coverage",
    "exhaustion",
    "load_state",
    "map_dataset",
    "priority",
    "rank_frontier",
    "record_outcome",
    "save_state",
    "spawn_second_order",
]

#: (domain key, human name, base expected value 0..1, base optionality 0..1)
#:
#: EV and OPTIONALITY are scored SEPARATELY and both are needed. Execution questions have high EV
#: and low optionality -- answering one saves money on every trade forever but opens no new search
#: space. Data-discovery questions invert that: a single new dataset can spawn a whole family of
#: hypotheses that were previously impossible to even state. A desk that ranked on EV alone would
#: systematically under-invest in exactly the questions that grow its future capacity.
DOMAINS: dict[str, tuple[str, float, float]] = {
    "ALPHA": ("Alpha Discovery", 0.95, 0.70),
    "FEATURE": ("Feature Discovery", 0.70, 0.60),
    "DATA": ("Data Discovery", 0.85, 0.95),
    "STRUCT": ("Market Structure", 0.90, 0.75),
    "EXEC": ("Execution", 0.80, 0.30),
    "REGIME": ("Regimes", 0.75, 0.55),
    "XMKT": ("Cross-Market", 0.70, 0.65),
    "CRYPTO": ("Crypto-Specific", 0.85, 0.70),
    "BEHAV": ("Behavioural Finance", 0.60, 0.50),
    "INFO": ("Information Discovery", 0.65, 0.85),
    "ML": ("Machine Learning", 0.45, 0.40),
    "PORT": ("Portfolio Construction", 0.80, 0.25),
    "RISK": ("Risk", 0.85, 0.20),
    "PROC": ("Discovery Process", 0.55, 0.60),
    "META": ("Meta-Research", 0.60, 0.80),
    "FRONTIER": ("Long-Term Frontier", 0.50, 1.00),
    "UNKNOWN": ("Unknown-Unknown Discovery", 0.55, 1.00),
    "INFOTH": ("Information-Theoretic Exploration", 0.65, 0.75),
    "COVER": ("Search-Space Coverage", 0.50, 0.70),
    "ADVERS": ("Adversarial Discovery", 0.70, 0.85),
    "TRANSFER": ("Cross-Domain Transfer", 0.55, 0.95),
    "NEGSPACE": ("Negative Space", 0.45, 0.75),
    "GENEALOGY": ("Alpha Genealogy", 0.40, 0.55),
    "DECAY": ("Discovery Decay", 0.55, 0.40),
    "EMERGE": ("Emergence Detection", 0.50, 0.80),
    "RECURSE": ("Recursive Self-Improvement", 0.60, 0.90),
}


@dataclass(frozen=True)
class Question:
    """One exploration frontier. `tags` are what a dataset is matched against."""

    id: str
    domain: str
    text: str
    tags: tuple[str, ...] = ()
    generation: int = 0
    parent: str | None = None

    @property
    def domain_name(self) -> str:
        return DOMAINS.get(self.domain, (self.domain, 0.5, 0.5))[0]


def _q(domain: str, n: int, text: str, *tags: str) -> Question:
    return Question(f"{domain}.{n}", domain, text, tags)


#: THE SEED SET. Generation 0. Every one is a REGION of the search space, never a task -- a
#: question is exhausted only when the region has been explored, and regions spawn sub-regions.
SEED_QUESTIONS: tuple[Question, ...] = (
    # 1 ALPHA
    _q("ALPHA", 1, "Which economically distinct alpha families have never been tested?", "family"),
    _q("ALPHA", 2, "Which existing alpha families are underrepresented?", "family"),
    _q("ALPHA", 3, "Which COMBINATIONS of alpha families have never been explored?", "family"),
    _q("ALPHA", 4, "Which markets show structural inefficiency competitors ignore?", "structure"),
    _q("ALPHA", 5, "Which edges appear ONLY under specific regimes?", "regime"),
    _q("ALPHA", 6, "Which edges disappear under realistic execution?", "execution", "cost"),
    _q("ALPHA", 7, "Which edges become STRONGER combined?", "family"),
    _q("ALPHA", 8, "Which edges are mutually exclusive?", "family"),
    _q("ALPHA", 9, "Which edges survive transaction costs?", "cost", "execution"),
    _q("ALPHA", 10, "Which edges survive FUNDING costs?", "funding", "cost"),
    _q("ALPHA", 11, "Which edges survive liquidity stress?", "liquidity", "depth"),
    _q("ALPHA", 12, "Which edges survive structural breaks?", "regime"),
    # 2 FEATURE
    _q("FEATURE", 1, "Which measurable variables have never been engineered?", "feature"),
    _q("FEATURE", 2, "Which variable COMBINATIONS have never been tested?", "feature"),
    _q("FEATURE", 3, "Which nonlinear transforms create information?", "feature"),
    _q("FEATURE", 4, "Which lag structures matter?", "feature", "lead-lag"),
    _q("FEATURE", 5, "Which interaction terms matter?", "feature"),
    _q("FEATURE", 6, "Which HIDDEN STATE variables exist?", "latent", "depth"),
    _q("FEATURE", 7, "Which temporal aggregations matter?", "feature", "horizon"),
    _q("FEATURE", 8, "Which volatility-adjusted transforms matter?", "vol", "feature"),
    _q("FEATURE", 9, "Which entropy measures matter?", "feature", "entropy"),
    _q("FEATURE", 10, "Which graph representations matter?", "graph", "network"),
    # 3 DATA
    _q("DATA", 1, "Which public datasets remain undiscovered?", "source"),
    _q("DATA", 2, "Which PRIVATE datasets can be reconstructed?", "latent", "reconstruct"),
    _q("DATA", 3, "Which public datasets can be FUSED into something new?", "fuse", "source"),
    _q("DATA", 4, "Which regional datasets are ignored?", "regional", "source"),
    _q("DATA", 5, "Which language ecosystems hold unique information?", "language", "source"),
    _q("DATA", 6, "Which APIs appeared recently?", "source", "new"),
    _q("DATA", 7, "Which archives became searchable?", "source", "archive"),
    _q("DATA", 8, "Which datasets DISAPPEARED?", "source", "negative"),
    _q("DATA", 9, "Which datasets changed methodology?", "source", "provenance"),
    _q("DATA", 10, "Which datasets yield genuine PROPRIETARY derivatives?", "reconstruct", "moat"),
    # 4 STRUCT
    _q("STRUCT", 1, "Where does structural inefficiency ORIGINATE?", "structure"),
    _q("STRUCT", 2, "What incentives create mispricing?", "structure", "incentive"),
    _q("STRUCT", 3, "Which participants systematically LOSE money?", "flow", "participant"),
    _q("STRUCT", 4, "Which participants systematically win?", "flow", "participant"),
    _q("STRUCT", 5, "Where do flows ORIGINATE?", "flow"),
    _q("STRUCT", 6, "Where do flows TERMINATE?", "flow"),
    _q("STRUCT", 7, "What causes FORCED buying?", "forced", "flow"),
    _q("STRUCT", 8, "What causes FORCED selling?", "forced", "liquidation"),
    _q("STRUCT", 9, "Which regulations create opportunities?", "structure", "barrier"),
    _q("STRUCT", 10, "Which exchange mechanics create predictable behaviour?", "venue", "micro"),
    # 5 EXEC
    _q("EXEC", 1, "Where is slippage ASYMMETRIC?", "execution", "cost"),
    _q("EXEC", 2, "Where is liquidity HIDDEN?", "depth", "latent"),
    _q("EXEC", 3, "Where is queue priority exploitable?", "queue", "micro"),
    _q("EXEC", 4, "Where are funding windows exploitable?", "funding"),
    _q("EXEC", 5, "Where are liquidation cascades predictable?", "liquidation", "forced"),
    _q("EXEC", 6, "Which venues execute differently?", "venue"),
    _q("EXEC", 7, "Which execution algorithms dominate?", "execution"),
    _q("EXEC", 8, "Which execution ASSUMPTIONS are wrong?", "execution", "assumption"),
    _q("EXEC", 9, "Which execution costs remain UNMODELLED?", "cost", "execution"),
    # 6 REGIME
    _q("REGIME", 1, "What HIDDEN regimes exist?", "regime", "latent"),
    _q("REGIME", 2, "Which features detect them EARLIEST?", "regime", "lead-lag"),
    _q("REGIME", 3, "Which strategies depend on them?", "regime"),
    _q("REGIME", 4, "Which strategies FAIL under them?", "regime", "risk"),
    _q("REGIME", 5, "How should allocation change across regimes?", "regime", "portfolio"),
    _q("REGIME", 6, "How fast do regimes transition?", "regime", "horizon"),
    _q("REGIME", 7, "Which regime indicators LEAD?", "regime", "lead-lag"),
    _q("REGIME", 8, "Which regime indicators lag?", "regime", "lead-lag"),
    # 7 XMKT
    _q("XMKT", 1, "Which assets LEAD others?", "lead-lag", "xmkt"),
    _q("XMKT", 2, "Which markets transmit information?", "xmkt", "flow"),
    _q("XMKT", 3, "Which markets lag?", "lead-lag", "xmkt"),
    _q("XMKT", 4, "Which markets create SYNTHETIC predictors?", "xmkt", "fuse"),
    _q("XMKT", 5, "Which spreads contain predictive power?", "spread", "xmkt"),
    _q("XMKT", 6, "Which currencies dominate?", "fx", "xmkt"),
    _q("XMKT", 7, "Which commodities matter?", "xmkt"),
    _q("XMKT", 8, "Which crypto SECTORS matter?", "xmkt", "crypto"),
    _q("XMKT", 9, "Which equity sectors matter?", "xmkt"),
    # 8 CRYPTO
    _q("CRYPTO", 1, "Which on-chain metrics remain unused?", "onchain", "crypto"),
    _q("CRYPTO", 2, "Which VALIDATOR behaviours matter?", "onchain", "validator"),
    _q("CRYPTO", 3, "Which bridge flows matter?", "onchain", "flow"),
    _q("CRYPTO", 4, "Which stablecoin mechanics matter?", "stablecoin", "depeg"),
    _q("CRYPTO", 5, "Which governance actions matter?", "onchain", "governance"),
    _q("CRYPTO", 6, "Which staking metrics matter?", "onchain", "validator"),
    _q("CRYPTO", 7, "Which MEV signals matter?", "mev", "micro"),
    _q("CRYPTO", 8, "Which DEX microstructure signals matter?", "dex", "micro"),
    _q("CRYPTO", 9, "Which perpetual FUNDING dynamics matter?", "funding", "crypto"),
    _q("CRYPTO", 10, "Which liquidation mechanics matter?", "liquidation", "forced"),
    # 9 BEHAV
    _q("BEHAV", 1, "Where are humans predictably irrational?", "behaviour"),
    _q("BEHAV", 2, "Which behavioural biases persist?", "behaviour"),
    _q("BEHAV", 3, "Which RETAIL behaviours matter?", "behaviour", "participant"),
    _q("BEHAV", 4, "Which INSTITUTIONAL behaviours matter?", "behaviour", "participant"),
    _q("BEHAV", 5, "Which social behaviours predict flow?", "behaviour", "flow"),
    _q("BEHAV", 6, "Which news structures matter?", "news", "behaviour"),
    _q("BEHAV", 7, "Which narratives propagate?", "news", "behaviour"),
    _q("BEHAV", 8, "Which narratives DECAY?", "news", "decay"),
    # 10 INFO
    _q("INFO", 1, "Which information arrives EARLIEST?", "lead-lag", "source"),
    _q("INFO", 2, "Which sources consistently lead?", "lead-lag", "source"),
    _q("INFO", 3, "Which sources are under-indexed?", "source", "coverage"),
    _q("INFO", 4, "Which LANGUAGES lead?", "language", "lead-lag"),
    _q("INFO", 5, "Which communities lead?", "community", "lead-lag"),
    _q("INFO", 6, "Which repositories appear first?", "repo", "lead-lag"),
    _q("INFO", 7, "Which researchers consistently produce useful work?", "literature"),
    _q("INFO", 8, "Which conferences produce useful ideas?", "literature", "community"),
    # 11 ML
    _q("ML", 1, "Which architectures remain untested?", "ml"),
    _q("ML", 2, "Which representation-learning methods help?", "ml", "feature"),
    _q("ML", 3, "Which self-supervised objectives help?", "ml"),
    _q("ML", 4, "Which embeddings help?", "ml", "feature"),
    _q("ML", 5, "Which graph methods help?", "ml", "graph"),
    _q("ML", 6, "Which CAUSAL methods help?", "ml", "causal"),
    _q("ML", 7, "Which uncertainty estimators help?", "ml", "risk"),
    _q("ML", 8, "Which ensemble methods help?", "ml"),
    # 12 PORT
    _q("PORT", 1, "Which allocation methods DOMINATE Kelly?", "portfolio", "kelly"),
    _q("PORT", 2, "Which risk measures matter?", "portfolio", "risk"),
    _q("PORT", 3, "Which correlations are UNSTABLE?", "portfolio", "correlation"),
    _q("PORT", 4, "Which diversification assumptions fail?", "portfolio", "assumption"),
    _q("PORT", 5, "Which leverage rules maximise E[log wealth]?", "portfolio", "kelly"),
    _q("PORT", 6, "Which rebalancing frequency is optimal?", "portfolio", "cost"),
    _q("PORT", 7, "Which capital constraints matter?", "portfolio"),
    # 13 RISK
    _q("RISK", 1, "Which failure modes remain UNKNOWN?", "risk", "unknown"),
    _q("RISK", 2, "Which assumptions remain untested?", "assumption", "risk"),
    _q("RISK", 3, "Which black swans are ignored?", "risk", "tail"),
    _q("RISK", 4, "Which HIDDEN correlations exist?", "correlation", "risk"),
    _q("RISK", 5, "Which tail events matter?", "tail", "risk"),
    _q("RISK", 6, "Which guardrails are MISSING?", "risk", "rail"),
    _q("RISK", 7, "Which risk metrics fail?", "risk", "assumption"),
    # 14 PROC
    _q("PROC", 1, "Which miners produce UNIQUE information?", "miner", "coverage"),
    _q("PROC", 2, "Which diggers overlap excessively?", "miner", "coverage"),
    _q("PROC", 3, "Which search operators dominate?", "search", "miner"),
    _q("PROC", 4, "Which languages remain underexplored?", "language", "coverage"),
    _q("PROC", 5, "Which source classes remain underexplored?", "source", "coverage"),
    _q("PROC", 6, "Which hypotheses repeatedly SUCCEED?", "genealogy"),
    _q("PROC", 7, "Which repeatedly fail?", "genealogy", "negative"),
    _q("PROC", 8, "Where is marginal information gain DIMINISHING?", "decay", "coverage"),
    _q("PROC", 9, "Which exploration frontiers remain untouched?", "coverage", "unknown"),
    # 15 META
    _q("META", 1, "What are we ASSUMING?", "assumption", "unknown"),
    _q("META", 2, "WHY are we assuming it?", "assumption"),
    _q("META", 3, "What if the OPPOSITE were true?", "assumption", "unknown"),
    _q("META", 4, "Which research directions never get proposed?", "unknown", "coverage"),
    _q("META", 5, "Which hypotheses are IMPOSSIBLE to generate with this architecture?",
       "unknown", "architecture"),
    _q("META", 6, "Which generators underperform?", "generator"),
    _q("META", 7, "Which generators should be MERGED?", "generator"),
    _q("META", 8, "Which should be split?", "generator"),
    _q("META", 9, "Which should be replaced?", "generator"),
    # 16 FRONTIER -- named desks, because each has a genuinely different search prior
    _q("FRONTIER", 1, "What would RENAISSANCE test that we never would?", "adversarial"),
    _q("FRONTIER", 2, "What would TWO SIGMA test?", "adversarial"),
    _q("FRONTIER", 3, "What would HRT test?", "adversarial", "micro"),
    _q("FRONTIER", 4, "What would JUMP test?", "adversarial", "micro"),
    _q("FRONTIER", 5, "What would JANE STREET test?", "adversarial"),
    _q("FRONTIER", 6, "What would DE SHAW test?", "adversarial"),
    _q("FRONTIER", 7, "What would CITADEL test?", "adversarial"),
    _q("FRONTIER", 8, "What would WINTON test?", "adversarial"),
    _q("FRONTIER", 9, "What would AQR test?", "adversarial"),
    _q("FRONTIER", 10, "What would a COMPLETELY DIFFERENT FIELD test?", "transfer"),
    # UNKNOWN-UNKNOWN
    _q("UNKNOWN", 1, "What alpha CLASSES could exist that we have never modelled?", "unknown"),
    _q("UNKNOWN", 2, "Which market mechanisms have NO hypothesis family?", "unknown", "family"),
    _q("UNKNOWN", 3, "Which market assumptions have never been explicitly challenged?",
       "assumption", "unknown"),
    # INFORMATION-THEORETIC
    _q("INFOTH", 1, "Which datasets maximise mutual information with future returns?",
       "source", "entropy"),
    _q("INFOTH", 2, "Which dataset COMBINATIONS create nonlinear information gain?",
       "fuse", "entropy"),
    _q("INFOTH", 3, "Which feature families remain information-ISOLATED?", "feature", "entropy"),
    # COVERAGE
    _q("COVER", 1, "Which regions of hypothesis space have the LOWEST exploration density?",
       "coverage"),
    _q("COVER", 2, "Which languages have the lowest validated source penetration?",
       "language", "coverage"),
    _q("COVER", 3, "Which asset classes remain structurally underexplored?", "coverage", "xmkt"),
    # ADVERSARIAL
    _q("ADVERS", 1, "What would a Renaissance researcher ATTACK first?", "adversarial",
       "assumption"),
    _q("ADVERS", 2, "What would an HFT researcher search that we never search?",
       "adversarial", "micro"),
    _q("ADVERS", 3, "What would a MACRO PM search that crypto researchers ignore?",
       "adversarial", "xmkt"),
    _q("ADVERS", 4, "What would a BLOCKCHAIN researcher search that finance ignores?",
       "adversarial", "onchain"),
    # TRANSFER
    _q("TRANSFER", 1, "What transfers from biology, ecology or epidemiology?", "transfer"),
    _q("TRANSFER", 2, "What transfers from physics, astronomy or meteorology?", "transfer"),
    _q("TRANSFER", 3, "What transfers from neuroscience or network science?", "transfer", "graph"),
    _q("TRANSFER", 4, "What transfers from queueing theory or control theory?",
       "transfer", "queue"),
    _q("TRANSFER", 5, "What transfers from game theory or operations research?", "transfer"),
    _q("TRANSFER", 6, "What transfers from signal processing or linguistics?", "transfer"),
    # NEGATIVE SPACE -- silence is information
    _q("NEGSPACE", 1, "What is NOT being discussed?", "negative", "community"),
    _q("NEGSPACE", 2, "Which topics suddenly disappeared?", "negative", "decay"),
    _q("NEGSPACE", 3, "Which repositories STOPPED updating?", "negative", "repo"),
    _q("NEGSPACE", 4, "Which APIs silently changed?", "negative", "provenance"),
    _q("NEGSPACE", 5, "Which markets became quiet?", "negative", "liquidity"),
    # GENEALOGY
    _q("GENEALOGY", 1, "What did each survivor DESCEND from?", "genealogy"),
    _q("GENEALOGY", 2, "Which datasets ENABLED it?", "genealogy", "source"),
    _q("GENEALOGY", 3, "Which search path found it?", "genealogy", "search"),
    # DECAY
    _q("DECAY", 1, "Which alpha families are SATURATING?", "decay", "family"),
    _q("DECAY", 2, "Which search operators are becoming less productive?", "decay", "search"),
    _q("DECAY", 3, "Which datasets are losing incremental value?", "decay", "source"),
    _q("DECAY", 4, "Which communities have become too mainstream?", "decay", "community"),
    # EMERGENCE
    _q("EMERGE", 1, "Which weak signals collectively indicate NEW market structure?",
       "emergence", "structure"),
    _q("EMERGE", 2, "New participant behaviour?", "emergence", "participant"),
    _q("EMERGE", 3, "New liquidity regimes?", "emergence", "liquidity"),
    _q("EMERGE", 4, "New execution dynamics?", "emergence", "execution"),
    _q("EMERGE", 5, "New funding mechanisms?", "emergence", "funding"),
    # RECURSIVE
    _q("RECURSE", 1, "If we rebuilt the pipeline from scratch today, what changes?",
       "architecture"),
    _q("RECURSE", 2, "Which component is NOW the largest bottleneck?", "architecture"),
    _q("RECURSE", 3, "Which single structural change most raises lifetime validated alpha?",
       "architecture"),
)

#: Attempts at which a question is considered thoroughly explored. Saturating rather than linear:
#: the 1st attempt at an untouched region teaches far more than the 30th, and a linear measure
#: would keep an over-mined region looking fresh long after it stopped paying.
_SATURATION = 25.0

#: No region ever reaches zero priority. A question is deprioritised by exhaustion, never
#: deleted -- a barren region that a new dataset reopens is exactly where a desk finds what
#: everyone else gave up on, and that only works if it is still reachable.
_REVIVAL_FLOOR = 0.02


def coverage(attempts: int) -> float:
    """0..1 exploration density. Saturating -- diminishing returns are the actual shape."""
    return 1.0 - math.exp(-max(0, attempts) / _SATURATION)


def exhaustion(attempts: int, survivors: int) -> float:
    """0..1 evidence that a region is BARREN, not merely visited.

    Coverage and exhaustion are different questions and conflating them is the trap. Thirty
    attempts with two survivors is a RICH region worth mining harder; thirty with none is a
    barren one. Only the second should suppress priority -- and even then never to zero, because
    a region can be reopened by a new dataset, and negative knowledge is reversible here.
    """
    if attempts <= 0:
        return 0.0
    if survivors > 0:
        return 0.0
    return coverage(attempts)


def priority(q: Question, attempts: int = 0, survivors: int = 0,
             state: dict[str, Any] | None = None) -> float:
    """What to explore NEXT: expected value x unexplored-ness x optionality.

    Multiplicative for the same reason EVIG is: a fully exhausted region is worth nothing however
    high its base EV, and a question with no optionality that is also low EV should not be rescued
    by being untouched. Novelty alone is not a reason to explore.
    """
    _, ev, opt = DOMAINS.get(q.domain, (q.domain, 0.5, 0.5))
    if state:
        s = state.get(q.id, {})
        attempts = int(s.get("attempts", attempts))
        survivors = int(s.get("survivors", survivors))
    # FLOORED, and this module's own test is why. Unfloored, a heavily-worked barren region drives
    # both terms to zero and its priority to EXACTLY 0.0 -- permanently unreachable, never
    # revisited, no matter what data arrives later. That contradicts the desk's own law that
    # negative knowledge is reversible, and it is the more dangerous direction of error: an
    # over-explored region that a new dataset reopens is precisely where a desk finds what
    # everyone else gave up on. The floor makes exhaustion a strong DEPRIORITISATION, never a
    # deletion.
    unexplored = max(_REVIVAL_FLOOR, 1.0 - coverage(attempts))
    barren = max(_REVIVAL_FLOOR, 1.0 - exhaustion(attempts, survivors))
    # A second-order question inherits urgency from having been EARNED by a real discovery: the
    # desk already has evidence that its neighbourhood contains something.
    earned = 1.0 + 0.25 * min(q.generation, 4)
    return round(ev * opt * unexplored * barren * earned, 6)


def rank_frontier(questions: tuple[Question, ...] | list[Question] = SEED_QUESTIONS,
                  state: dict[str, Any] | None = None,
                  limit: int | None = None) -> list[dict[str, Any]]:
    """The exploration frontier, highest priority first."""
    state = state or {}
    rows: list[dict[str, Any]] = []
    for q in questions:
        s = state.get(q.id, {})
        a, v = int(s.get("attempts", 0)), int(s.get("survivors", 0))
        rows.append({"id": q.id, "domain": q.domain_name, "text": q.text,
                     "generation": q.generation, "attempts": a, "survivors": v,
                     "coverage": round(coverage(a), 3),
                     "exhaustion": round(exhaustion(a, v), 3),
                     "priority": priority(q, a, v)})
    rows.sort(key=lambda d: -float(d["priority"]))
    return rows[:limit] if limit else rows


def map_dataset(name: str, description: str = "",
                questions: tuple[Question, ...] | list[Question] = SEED_QUESTIONS,
                ) -> list[str]:
    """Which questions a new dataset can help answer. Tag match on name + description.

    Deliberately generous: a false match costs a reader one glance, a MISSED match means a dataset
    lands and nobody realises it reopens a region that was written off as exhausted. The whole
    point of the mapping is that arrival of data should automatically revive questions.
    """
    hay = f"{name} {description}".lower()
    toks = set(re.split(r"[^a-z0-9]+", hay)) - {""}
    hits = []
    for q in questions:
        if any(t in hay or t in toks for t in q.tags):
            hits.append(q.id)
    return hits


def spawn_second_order(parent: Question, discovery: str) -> tuple[Question, ...]:
    """A survivor creates questions that did not exist before it.

    THIS IS WHAT MAKES THE ONTOLOGY SELF-EXPANDING rather than consumed. A finite checklist shrinks
    as it is worked; a search space that grows three new regions per discovery compounds. The four
    spawned here are the four that historically pay: does it generalise, what regime breaks it,
    what does it combine with, and what NEW data would sharpen it.
    """
    g = parent.generation + 1
    base = f"{parent.id}.{g}"
    return (
        Question(f"{base}a", parent.domain, f"Does '{discovery}' generalise to adjacent "
                 f"markets, venues or horizons?", (*parent.tags, "generalise"), g, parent.id),
        Question(f"{base}b", "REGIME", f"Under which regime does '{discovery}' break, and what "
                 f"detects that regime earliest?", ("regime", "lead-lag"), g, parent.id),
        Question(f"{base}c", "ALPHA", f"What does '{discovery}' COMBINE with -- and what is it "
                 f"mutually exclusive with?", ("family", "combination"), g, parent.id),
        Question(f"{base}d", "DATA", f"What new dataset would sharpen '{discovery}', and can we "
                 f"MANUFACTURE it rather than buy it?", ("source", "reconstruct", "moat"),
                 g, parent.id),
    )


def record_outcome(state: dict[str, Any], question_id: str, *, survived: bool) -> dict[str, Any]:
    """Every tested hypothesis updates the region it came from -- pass or fail.

    Failures are the more valuable update and the one a naive design drops: they are what turns
    'we never looked' into 'we looked and it is barren', and those demand opposite responses.
    """
    s = state.setdefault(question_id, {"attempts": 0, "survivors": 0})
    s["attempts"] = int(s.get("attempts", 0)) + 1
    if survived:
        s["survivors"] = int(s.get("survivors", 0)) + 1
    return state


def load_state(path: Path) -> dict[str, Any]:
    try:
        d = json.loads(Path(path).read_text("utf-8"))
        return d.get("questions", d) if isinstance(d, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def save_state(path: Path, state: dict[str, Any], spawned: list[Question] | None = None) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({
        "questions": state,
        "spawned": [{"id": q.id, "domain": q.domain, "text": q.text, "tags": list(q.tags),
                     "generation": q.generation, "parent": q.parent} for q in (spawned or [])],
    }, indent=1), "utf-8")


@dataclass
class Ontology:
    """Seed questions plus everything discovery has spawned since."""

    questions: list[Question] = field(default_factory=lambda: list(SEED_QUESTIONS))

    def add(self, qs: tuple[Question, ...] | list[Question]) -> None:
        known = {q.id for q in self.questions}
        self.questions.extend(q for q in qs if q.id not in known)

    def __len__(self) -> int:
        return len(self.questions)

```

### libs\ict\__init__.py
```python

```

### libs\research\adapters\__init__.py
```python
"""THE ADAPTERS -- one per federated system, each turning an upstream research engine's native
output into an ExternalResearchPacket over a READ-ONLY ResearchBundle (LAWS 5h, 5m).

WHAT AN ADAPTER IS. `run(bundle: ResearchBundle) -> ExternalResearchPacket`, executed INSIDE the
system's sandbox (`python -m libs.research.adapters.<system> --bundle <path> --out <path>`) by
`desks/mt5/research/sandbox_runner.py`, never inside the desk process. The bundle is a COPY of a
few bar frames, axis series with their available_time, the cost surface, a research question, a
compute budget, a seed and the allowed horizons -- written into the sandbox work directory,
never mounted. The packet is the ONLY exit: candidates, representations, mechanisms, research
methods and datasets with provenance and the real search burden (`trials_charged` counts every
parameter the engine evaluated). A verdict-shaped field raises at the contract, here and again
at the desk's boundary, so an upstream engine can donate a hypothesis and never a survivor.

WHAT AN ADAPTER IS NOT. It is not a validator (no Sharpe, no pass, no rank has authority), not a
sizer (riskfolio donates allocation EVIDENCE, never a size), and not a mount: it reads only what
the bundle carries. A library that is absent in the environment is reported UNMEASURED by name
in the packet's research_methods rather than raised, because "the engine did not run" is a
measurement the federation ledger needs and a stack trace is not.

THIS MODULE IS IMPORT-LIGHT ON PURPOSE. It is copied into every sandbox together with the packet
contract, so it may import the standard library and the contract and nothing else at module
scope; numpy is imported lazily because every federated engine already depends on it.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import importlib
import importlib.metadata
import json
import math
import os
import random
import sys
import time
import traceback
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from libs.research.external_federation import PACKET_FORBIDDEN, ExternalResearchPacket

#: A candidate row that names a registered price-only family compiles as STRUCTURED_HYPOTHESIS
#: in `miner_candidate_compiler` (family defaults, declared instruments). Adapters name ONLY
#: these; a family outside the vocabulary would be read as prose and lose its instrument.
FAMILIES: tuple[str, ...] = (
    "failed_breakout", "level_breakout", "overnight_drift", "mean_reversion_rsi",
    "mean_reversion_bollinger", "volatility_squeeze", "trend_ma_cross", "momentum_volgate",
    "range_reversion", "volume_spike", "pullback_entry", "vol_mean_reversion", "vol_transition",
    "drawdown_conditional", "spread_state",
)


@dataclass(frozen=True)
class Spec:
    """Where a system is distributed, at which measured pin, and what its adapter yields."""

    system_id: str
    distribution: str
    version: str
    module: str
    weight: str = "light"
    yields: tuple[str, ...] = ()
    note: str = ""

    @property
    def requirement(self) -> str:
        return f"{self.distribution}=={self.version}" if self.version else self.distribution


#: THE FIRST ADAPTERS. Pins are the versions `pip download --only-binary :all:` resolved on this
#: desk's interpreter (CPython 3.14, 2026-09-22) -- measured installable wheels, not remembered
#: release numbers. `weight="heavy"` marks a torch dependency (hundreds of MB; provisioned last).
SPECS: dict[str, Spec] = {s.system_id: s for s in (
    Spec("ruptures", "ruptures", "1.0.6", "ruptures", yields=("representations", "candidates"),
         note="1.1.x ships no wheel for this interpreter; 1.0.6 is the pure-python build"),
    Spec("stumpy", "stumpy", "1.14.1", "stumpy", yields=("representations", "candidates")),
    Spec("pysindy", "pysindy", "2.1.0", "pysindy", yields=("mechanisms",)),
    Spec("pydmd", "pydmd", "2025.8.1", "pydmd", yields=("representations",)),
    Spec("tsfresh", "tsfresh", "0.21.2", "tsfresh", yields=("representations",)),
    Spec("riskfolio", "Riskfolio-Lib", "7.3.0", "riskfolio", yields=("research_methods",),
         note="allocator CHALLENGER: allocation evidence, never a size"),
    Spec("pymoo", "pymoo", "0.6.2", "pymoo", yields=("candidates", "research_methods")),
    Spec("nevergrad", "nevergrad", "1.0.12", "nevergrad", yields=("candidates",)),
    Spec("botorch", "botorch", "0.18.1", "botorch", weight="heavy",
         yields=("research_methods", "candidates")),
    Spec("river", "river", "0.26.1", "river", yields=("representations",)),
    Spec("mapie", "mapie", "1.5.0", "mapie", yields=("representations",)),
    Spec("tensorly", "tensorly", "0.9.0", "tensorly", yields=("representations",)),
    Spec("pyrqa", "PyRQA", "", "pyrqa", yields=("representations",),
         note="sdist-only on PyPI and OpenCL-backed; provisioning measures whether it installs"),
    Spec("pgmpy", "pgmpy", "1.1.2", "pgmpy", weight="heavy", yields=("mechanisms",)),
    Spec("pyextremes", "pyextremes", "2.5.0", "pyextremes",
         yields=("representations", "candidates")),
    Spec("scikit_mine", "scikit-mine", "1.0.0", "skmine",
         yields=("representations", "candidates")),
    Spec("tslearn", "tslearn", "0.9.0", "tslearn", yields=("representations", "candidates")),
    Spec("pyvinecopulib", "pyvinecopulib", "1.0.0", "pyvinecopulib", yields=("representations",)),
    Spec("roughpy", "roughpy", "0.3.0", "roughpy", yields=("representations",)),
)}

#: THE MANDATED WAVES (principal 2026-09-19/22): symbolic regression, causal machinery, the
#: foundation models, simulation, feature synthesis, the forecast zoos, information theory,
#: program evolution, topology, distributed search, point processes, reservoirs, scattering,
#: simulation-based inference, the meta-evolution layer, and the WRAPPED/REBUILT institutional
#: methods. A pin is the wheel `pip download --only-binary :all:` resolved on this interpreter
#: on 2026-09-22; an EMPTY pin means no wheel resolved here (sdist-only, a git-only project, or a
#: torch stack this interpreter has no build for) and provisioning measures it again. A
#: git-only project carries NO distribution: `pip download` found no `abides`, `idtxl`,
#: `alphagen` or `quantifact` wheel, and PyPI's `dso` is a different project -- reading a
#: namesake's terms is worse than UNVERIFIED, so those are read from their repositories.
SPECS.update({s.system_id: s for s in (
    Spec("alphagen", "", "", "alphagen", yields=("candidates",),
         note="git-only (RL-MLDM/alphagen): provisioning pins the commit, never a wheel"),
    Spec("dso", "", "", "dso", yields=("mechanisms",),
         note="git-only (dso-org/deep-symbolic-optimization)"),
    Spec("pysr", "pysr", "2.5.0", "pysr", weight="heavy", yields=("mechanisms",),
         note="needs a Julia runtime the first run installs; UNMEASURED until it exists"),
    Spec("tigramite", "tigramite", "5.2.10.1", "tigramite", yields=("mechanisms",)),
    Spec("causal_learn", "causal-learn", "0.1.4.8", "causallearn", yields=("mechanisms",)),
    Spec("dowhy", "dowhy", "0.8", "dowhy", yields=("research_methods", "mechanisms")),
    Spec("chronos2", "chronos-forecasting", "2.3.2", "chronos", weight="heavy",
         yields=("representations",), note="weights come from the local HF cache only"),
    Spec("timesfm", "timesfm", "3.0.2", "timesfm", weight="heavy", yields=("representations",),
         note="3.0 weights are non-commercial by their terms: research representation only"),
    Spec("moment", "momentfm", "0.1.4", "momentfm", weight="heavy", yields=("representations",)),
    Spec("abides", "", "", "abides_core", yields=("datasets", "representations")),
    Spec("featuretools", "featuretools", "1.31.0", "featuretools", yields=("representations",)),
    Spec("cvxportfolio", "cvxportfolio", "1.5.1", "cvxportfolio", yields=("research_methods",),
         note="allocator CHALLENGER: allocation evidence, never a size"),
    Spec("pymc", "pymc", "6.3.2", "pymc", weight="heavy", yields=("representations",)),
    Spec("neuralforecast", "neuralforecast", "3.2.2", "neuralforecast", weight="heavy",
         yields=("representations",)),
    Spec("darts", "u8darts", "0.41.0", "darts", yields=("representations",)),
    Spec("kats", "kats", "0.2.0", "kats", yields=("representations", "candidates")),
    Spec("merlion", "salesforce-merlion", "2.0.4", "merlion", yields=("representations",)),
    Spec("aeon", "aeon", "1.6.0", "aeon", yields=("representations", "candidates")),
    Spec("idtxl", "", "", "idtxl", yields=("mechanisms",),
         note="git-only (pwollstadt/IDTxl); JIDT estimators need a JVM"),
    Spec("tpot", "TPOT", "0.12.2", "tpot", yields=("research_methods",)),
    Spec("openspiel", "open_spiel", "2.0.2", "pyspiel", yields=("research_methods",)),
    Spec("pyg_temporal", "torch-geometric-temporal", "0.56.2", "torch_geometric_temporal",
         weight="heavy", yields=("representations",)),
    Spec("ripser", "ripser", "0.6.15", "ripser", yields=("representations", "candidates")),
    Spec("ray", "ray", "2.58.0", "ray", weight="heavy", yields=("candidates",)),
    Spec("easytpp", "easy-tpp", "0.3.0", "easy_tpp", weight="heavy", yields=("datasets",)),
    Spec("reservoirpy", "reservoirpy", "0.4.2", "reservoirpy", yields=("representations",)),
    Spec("kymatio", "kymatio", "0.3.0", "kymatio", yields=("representations",)),
    Spec("sbi", "sbi", "0.27.0", "sbi", weight="heavy", yields=("representations",)),
    Spec("openevolve", "openevolve", "0.3.2", "openevolve", yields=("research_methods",),
         note="LLM-driven upstream; the research path carries no LLM, so the loop is REBUILT"),
    Spec("darwin_godel_machine", "", "", "dgm", yields=("research_methods",),
         note="REBUILT by the roster: no upstream code runs here"),
    Spec("ai_scientist", "", "", "ai_scientist", yields=("research_methods",),
         note="LLM-driven upstream; REBUILT route"),
    Spec("pyribs", "ribs", "0.12.0", "ribs", yields=("candidates",)),
    Spec("dspy", "dspy", "3.3.1", "dspy", yields=("research_methods",),
         note="prompt optimisation needs an LLM; the research path carries none"),
    Spec("quantifact", "", "", "quantifact", yields=("research_methods",)),
    Spec("bridgewater_pat_aia", "", "", "", yields=("research_methods",),
         note="REBUILT: public architecture only, nothing to install"),
    Spec("alpha_search", "", "", "alpha_search", yields=("research_methods",)),
    Spec("quantrocket", "quantrocket-client", "2.11.0.0", "quantrocket",
         yields=("research_methods",),
         note="WRAPPED: a licensed installation reached by API only"),
    Spec("quantconnect_cloud", "lean", "1.0.229", "lean", yields=("datasets", "research_methods"),
         note="WRAPPED: LEAN core is Apache-2.0; the platform is reached by API"),
    Spec("numerai_method", "", "", "", yields=("research_methods", "candidates"),
         note="REBUILT: the method on the desk's own PIT data, numpy only"),
)})

#: The capability family each adapter's packet routes under (CAPABILITY_FAMILIES) and the
#: licence its upstream PUBLISHES. `licence_expected` is what a maintainer wrote in the project
#: metadata as this desk last read it; it is NOT the licence of record -- only
#: `libs.research.licence_reader` produces that, at a pin, and the runner refuses DIRECT
#: execution until it has (LAWS 5h). The expected id exists so a reading that disagrees is
#: visible as a disagreement rather than silently accepted.
FAMILY_OF: dict[str, str] = {
    "ruptures": "change_point", "stumpy": "time_series_mining", "pysindy": "dynamical_systems",
    "pydmd": "dynamical_systems", "tsfresh": "feature_synthesis",
    "riskfolio": "portfolio_optimization", "pymoo": "multiobjective_search",
    "nevergrad": "evolutionary_search", "botorch": "bayesian_optimization",
    "river": "online_learning", "mapie": "conformal_uncertainty", "tensorly": "tensor_methods",
    "pyrqa": "recurrence_analysis", "pgmpy": "graphical_models", "pyextremes": "extreme_value",
    "scikit_mine": "pattern_mining", "tslearn": "time_series_mining",
    "pyvinecopulib": "copula_dependence", "roughpy": "rough_paths",
    "alphagen": "evolutionary_search", "dso": "symbolic_regression",
    "pysr": "symbolic_regression", "tigramite": "causal_discovery",
    "causal_learn": "causal_discovery", "dowhy": "causal_discovery",
    "chronos2": "foundation_model", "timesfm": "foundation_model",
    "moment": "foundation_model", "abides": "market_simulation",
    "featuretools": "feature_synthesis", "cvxportfolio": "portfolio_optimization",
    "pymc": "probabilistic_programming", "neuralforecast": "forecast_zoo",
    "darts": "forecast_zoo", "kats": "change_point", "merlion": "anomaly_detection",
    "aeon": "time_series_mining", "idtxl": "information_theory", "tpot": "program_evolution",
    "openspiel": "game_theory", "pyg_temporal": "graph_learning", "ripser": "topology",
    "ray": "distributed_compute", "easytpp": "point_process",
    "reservoirpy": "reservoir_computing", "kymatio": "signal_scattering",
    "sbi": "simulation_based_inference", "openevolve": "program_evolution",
    "darwin_godel_machine": "agent_evolution", "ai_scientist": "automated_science",
    "pyribs": "quality_diversity", "dspy": "prompt_optimization",
    "quantifact": "research_reliability", "bridgewater_pat_aia": "institutional_capability",
    "alpha_search": "multi_agent_debate", "quantrocket": "data_tooling",
    "quantconnect_cloud": "research_reliability", "numerai_method": "portfolio_research",
}
LICENCE_EXPECTED: dict[str, str] = {
    "ruptures": "BSD-2-Clause", "stumpy": "BSD-3-Clause", "pysindy": "MIT", "pydmd": "MIT",
    "tsfresh": "MIT", "riskfolio": "BSD-3-Clause", "pymoo": "Apache-2.0", "nevergrad": "MIT",
    "botorch": "MIT", "river": "BSD-3-Clause", "mapie": "BSD-3-Clause",
    "tensorly": "BSD-3-Clause", "pyrqa": "GPL-3.0", "pgmpy": "MIT", "pyextremes": "MIT",
    "scikit_mine": "BSD-3-Clause", "tslearn": "BSD-2-Clause", "pyvinecopulib": "MIT",
    "roughpy": "BSD-3-Clause", "alphagen": "MIT", "dso": "BSD-3-Clause", "pysr": "Apache-2.0",
    "tigramite": "GPL-3.0", "causal_learn": "MIT", "dowhy": "MIT", "chronos2": "Apache-2.0",
    "timesfm": "Apache-2.0", "moment": "MIT", "abides": "BSD-3-Clause",
    "featuretools": "BSD-3-Clause", "cvxportfolio": "Apache-2.0", "pymc": "Apache-2.0",
    "neuralforecast": "Apache-2.0", "darts": "Apache-2.0", "kats": "MIT",
    "merlion": "BSD-3-Clause", "aeon": "BSD-3-Clause", "idtxl": "GPL-3.0", "tpot": "LGPL-3.0",
    "openspiel": "Apache-2.0", "pyg_temporal": "MIT", "ripser": "MIT", "ray": "Apache-2.0",
    "easytpp": "Apache-2.0", "reservoirpy": "MIT", "kymatio": "BSD-3-Clause",
    "sbi": "Apache-2.0", "openevolve": "Apache-2.0", "darwin_godel_machine": "Apache-2.0",
    "ai_scientist": "Apache-2.0", "pyribs": "MIT", "dspy": "MIT", "quantifact": "UNVERIFIED",
    "bridgewater_pat_aia": "N/A (no code)", "alpha_search": "UNVERIFIED",
    "quantrocket": "Proprietary", "quantconnect_cloud": "Apache-2.0",
    "numerai_method": "N/A (method only)",
}
#: Packets from the desk's own sandboxed research cells (desks/mt5/research/sandboxes/) carry
#: this prefix on their system_id: they are REBUILT mechanisms in the desk's own code, so their
#: commit is the desk tree's HEAD rather than a PyPI pin.
CELL_PREFIX = "cell:"


def describe(module: Any, licences: Mapping[str, str] | None = None) -> dict[str, Any]:
    """THE ADAPTER CONTRACT, as a record: name, licence (of record when the runner passes the
    ledger's readings; otherwise UNVERIFIED with the expected id beside it), capability family,
    the pinned requirement, whether the upstream imports HERE, and the run callable."""
    name = str(getattr(module, "SYSTEM", "") or getattr(module, "NAME", ""))
    spec = SPECS.get(name)
    family = str(getattr(module, "CAPABILITY_FAMILY", "") or FAMILY_OF.get(name, ""))
    expected = str(getattr(module, "LICENCE_EXPECTED", "") or LICENCE_EXPECTED.get(name,
                                                                                 "UNVERIFIED"))
    read = (licences or {}).get(name, "")
    licence = read if read and read not in ("UNVERIFIED", "UNMEASURED") \
        else f"UNVERIFIED (expected {expected}; read it with licence_reader)"
    available = bool(spec and spec.module and library(spec.module) is not None)
    return {"name": name, "licence": licence, "licence_expected": expected,
            "capability_family": family, "distribution": spec.distribution if spec else "",
            "requirement": spec.requirement if spec else "", "version": spec.version if spec
            else "", "module": spec.module if spec else "", "weight": spec.weight if spec
            else "light", "yields": list(spec.yields) if spec else [],
            "runs_without_library": bool(getattr(module, "RUNS_WITHOUT_LIBRARY", False)),
            "available_here": available, "run": getattr(module, "run", None)}


def _git_head() -> str:
    """The desk tree's HEAD, read from .git without running git (stdlib, sandbox-safe)."""
    try:
        root = Path(__file__).resolve().parents[3]
        head = (root / ".git" / "HEAD").read_text(encoding="utf-8").strip()
        if not head.startswith("ref:"):
            return head[:12]
        ref_name = head.split(" ", 1)[1].strip()
        ref = root / ".git" / ref_name
        if ref.exists():
            return ref.read_text(encoding="utf-8").strip()[:12]
        packed = root / ".git" / "packed-refs"
        if packed.exists():
            for line in packed.read_text(encoding="utf-8").splitlines():
                if line.endswith(" " + ref_name):
                    return line.split(" ", 1)[0][:12]
        return "UNMEASURED"
    except OSError:
        return "UNMEASURED"


# ------------------------------------------------------------------------------- the bundle

@dataclass(frozen=True)
class BarFrame:
    """One symbol's bars at one timeframe, as immutable columns (UTC ISO times)."""

    symbol: str
    timeframe: str
    time: tuple[str, ...]
    open: tuple[float, ...]
    high: tuple[float, ...]
    low: tuple[float, ...]
    close: tuple[float, ...]
    volume: tuple[float, ...]

    def __len__(self) -> int:
        return len(self.time)

    @property
    def key(self) -> str:
        return f"{self.symbol}_{self.timeframe}"

    def log_returns(self) -> Any:
        import numpy as np
        c = np.asarray(self.close, dtype=float)
        return np.diff(np.log(np.maximum(c, 1e-12)))


@dataclass(frozen=True)
class AxisSeries:
    """A point-in-time axis: (available_time, value) points and the stamp's own basis."""

    axis: str
    series: str
    points: tuple[tuple[str, float], ...]
    available_time: str
    basis: str = ""


@dataclass(frozen=True)
class CostRow:
    """The cost surface for one symbol: spread by hour in points, tick and contract size."""

    symbol: str
    tick_size: float
    contract_size: float
    pooled_median_spread_pts: float
    spread_pts_p50_by_hour: Mapping[str, float] = field(default_factory=dict)


@dataclass(frozen=True)
class ResearchBundle:
    """Everything an adapter may read, copied into the sandbox. Frozen: a bundle is never edited,
    and an engine that wants more data asks the runner for a different bundle."""

    bundle_id: str
    built_at: str
    question: str
    compute_budget_s: int
    seed: int
    horizons: tuple[str, ...]
    universe: tuple[str, ...]
    bars: Mapping[str, BarFrame] = field(default_factory=dict)
    axes: Mapping[str, AxisSeries] = field(default_factory=dict)
    costs: Mapping[str, CostRow] = field(default_factory=dict)
    provenance: Mapping[str, Any] = field(default_factory=dict)
    read_only: bool = True

    def frames(self, timeframe: str = "H1") -> list[BarFrame]:
        return [f for f in self.bars.values() if f.timeframe == timeframe]

    def frame(self, symbol: str, timeframe: str = "H1") -> BarFrame | None:
        return self.bars.get(f"{symbol}_{timeframe}")

    def watermark(self) -> str:
        """The newest bar time across frames -- the monotonic progress mark of a run."""
        return max((f.time[-1] for f in self.bars.values() if f.time), default="")

    def cost_pts(self, symbol: str) -> float:
        row = self.costs.get(symbol)
        return float(row.pooled_median_spread_pts) if row else float("nan")

    def digest(self) -> str:
        h = hashlib.sha256()
        for key in sorted(self.bars):
            f = self.bars[key]
            h.update(key.encode())
            h.update(str(len(f)).encode())
            h.update((f.time[-1] if f.time else "").encode())
            h.update(repr(f.close[-3:]).encode())
        h.update(json.dumps(sorted(self.axes)).encode())
        h.update(str(self.seed).encode())
        return h.hexdigest()[:16]


def write_bundle(bundle: ResearchBundle, directory: Path) -> Path:
    """Write the bundle as `bundle.json` + `bars/<key>.csv` under `directory`; return the manifest.
    CSV so a sandbox with numpy alone can read it; nothing here needs pandas or pyarrow."""
    directory.mkdir(parents=True, exist_ok=True)
    bars_dir = directory / "bars"
    bars_dir.mkdir(exist_ok=True)
    files: dict[str, str] = {}
    for key, f in bundle.bars.items():
        p = bars_dir / f"{key}.csv"
        with p.open("w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh)
            w.writerow(["time", "open", "high", "low", "close", "volume"])
            for i in range(len(f)):
                w.writerow([f.time[i], f.open[i], f.high[i], f.low[i], f.close[i], f.volume[i]])
        files[key] = f"bars/{key}.csv"
    doc = {
        "bundle_id": bundle.bundle_id, "built_at": bundle.built_at, "question": bundle.question,
        "compute_budget_s": bundle.compute_budget_s, "seed": bundle.seed,
        "horizons": list(bundle.horizons), "universe": list(bundle.universe),
        "bars": {k: {"symbol": f.symbol, "timeframe": f.timeframe, "file": files[k],
                     "n": len(f)} for k, f in bundle.bars.items()},
        "axes": {k: asdict(a) for k, a in bundle.axes.items()},
        "costs": {k: {**asdict(c), "spread_pts_p50_by_hour": dict(c.spread_pts_p50_by_hour)}
                  for k, c in bundle.costs.items()},
        "provenance": dict(bundle.provenance), "read_only": True,
        "digest": bundle.digest(),
    }
    manifest = directory / "bundle.json"
    tmp = manifest.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(doc, indent=1, default=str), encoding="utf-8")
    os.replace(tmp, manifest)
    return manifest


def load_bundle(path: Path) -> ResearchBundle:
    """Read a manifest written by `write_bundle` (paths resolve relative to the manifest)."""
    doc = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    base = Path(path).parent
    bars: dict[str, BarFrame] = {}
    for key, meta in (doc.get("bars") or {}).items():
        cols: dict[str, list[Any]] = {c: [] for c in ("time", "open", "high", "low", "close",
                                                       "volume")}
        with (base / meta["file"]).open(encoding="utf-8") as fh:
            for row in csv.DictReader(fh):
                cols["time"].append(str(row["time"]))
                for c in ("open", "high", "low", "close", "volume"):
                    cols[c].append(float(row[c]))
        bars[key] = BarFrame(str(meta["symbol"]), str(meta["timeframe"]), tuple(cols["time"]),
                             tuple(cols["open"]), tuple(cols["high"]), tuple(cols["low"]),
                             tuple(cols["close"]), tuple(cols["volume"]))
    axes = {k: AxisSeries(str(a["axis"]), str(a["series"]),
                          tuple((str(t), float(v)) for t, v in a.get("points") or ()),
                          str(a.get("available_time") or ""), str(a.get("basis") or ""))
            for k, a in (doc.get("axes") or {}).items()}
    costs = {k: CostRow(str(c["symbol"]), float(c.get("tick_size") or 0.0),
                        float(c.get("contract_size") or 0.0),
                        float(c.get("pooled_median_spread_pts") or float("nan")),
                        {str(h): float(v) for h, v in (c.get("spread_pts_p50_by_hour")
                                                        or {}).items()})
             for k, c in (doc.get("costs") or {}).items()}
    return ResearchBundle(
        bundle_id=str(doc.get("bundle_id") or "UNMEASURED"),
        built_at=str(doc.get("built_at") or ""), question=str(doc.get("question") or ""),
        compute_budget_s=int(doc.get("compute_budget_s") or 300),
        seed=int(doc.get("seed") or 0), horizons=tuple(doc.get("horizons") or ("24h",)),
        universe=tuple(doc.get("universe") or ()), bars=bars, axes=axes, costs=costs,
        provenance=dict(doc.get("provenance") or {}))


def synthetic_bundle(*, seed: int = 0, n: int = 600,
                     symbols: Sequence[str] = ("XAUUSD", "EURUSD", "USDJPY"),
                     timeframe: str = "H1", budget_s: int = 60) -> ResearchBundle:
    """Planted random-walk bars with a volatility break half way -- for tests and dry runs.
    Nothing in it is market data; a packet built on it is a shape test, never evidence."""
    rng = random.Random(seed)  # noqa: S311 -- planted bars, never a secret
    t0 = datetime(2026, 1, 5, 0, 0, tzinfo=UTC)
    step = {"H1": timedelta(hours=1), "M5": timedelta(minutes=5)}.get(timeframe,
                                                                     timedelta(hours=1))
    bars: dict[str, BarFrame] = {}
    for si, sym in enumerate(symbols):
        px = 100.0 * (si + 1)
        t, o, h, lo, c, v = [], [], [], [], [], []
        for i in range(n):
            vol = 0.002 if i < n // 2 else 0.006
            r = rng.gauss(0.0, vol) + (0.0004 * math.sin(i / 37.0))
            nxt = px * math.exp(r)
            hi = max(px, nxt) * (1 + abs(rng.gauss(0, vol / 2)))
            lw = min(px, nxt) * (1 - abs(rng.gauss(0, vol / 2)))
            t.append((t0 + i * step).isoformat())
            o.append(px)
            h.append(hi)
            lo.append(lw)
            c.append(nxt)
            v.append(float(rng.randint(100, 1000)))
            px = nxt
        bars[f"{sym}_{timeframe}"] = BarFrame(sym, timeframe, tuple(t), tuple(o), tuple(h),
                                              tuple(lo), tuple(c), tuple(v))
    axes = {"shadow_usd_liquidity.index": AxisSeries(
        "shadow_usd_liquidity", "index",
        tuple(((t0 + timedelta(days=d)).date().isoformat(), math.sin(d / 9.0))
              for d in range(0, n // 24 + 1)),
        (t0 + timedelta(days=n // 24)).date().isoformat(), "synthetic")}
    costs = {s: CostRow(s, 0.01, 100.0, 15.0, {str(hh): 15.0 + (hh % 5) for hh in range(24)})
             for s in symbols}
    return ResearchBundle(bundle_id=f"synthetic-{seed}", built_at=t0.isoformat(),
                          question="shape test on planted bars", compute_budget_s=budget_s,
                          seed=seed, horizons=("4h", "24h"), universe=tuple(symbols), bars=bars,
                          axes=axes, costs=costs, provenance={"synthetic": True})


# ------------------------------------------------------------------------------- the packet

class Deadline:
    """The compute budget, checked between parameter evaluations so an engine stops honestly and
    charges exactly what it evaluated."""

    def __init__(self, seconds: float) -> None:
        self.t0 = time.monotonic()
        self.seconds = float(seconds)

    def left(self) -> float:
        return self.seconds - (time.monotonic() - self.t0)

    def expired(self) -> bool:
        return self.left() <= 0


def library(name: str) -> Any | None:
    """The upstream module, or None when it is not importable here (reported, never raised)."""
    try:
        return importlib.import_module(name)
    except Exception:
        return None


def commit_of(system_id: str) -> str:
    """The exact upstream revision this environment runs: `pypi:<dist>==<installed version>`."""
    if system_id.startswith(CELL_PREFIX):
        return f"desk:{_git_head()}"
    spec = SPECS.get(system_id)
    if spec is None:
        return "UNMEASURED"
    if not spec.distribution:
        return f"desk:{_git_head()}"
    try:
        return f"pypi:{spec.distribution}=={importlib.metadata.version(spec.distribution)}"
    except importlib.metadata.PackageNotFoundError:
        return f"pypi:{spec.distribution}==UNMEASURED"


def run_id_for(system_id: str, bundle: ResearchBundle) -> str:
    stamp = datetime.now(tz=UTC).strftime("%Y%m%dT%H%M%SZ")
    return f"{system_id}-{bundle.digest()}-{stamp}"


def py(value: Any) -> Any:
    """JSON-safe: numpy scalars/arrays to python, NaN/inf to None, tuples to lists."""
    if hasattr(value, "tolist"):
        return py(value.tolist())
    if isinstance(value, dict):
        return {str(k): py(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [py(v) for v in value]
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return None
    if isinstance(value, (bool, int, float, str)) or value is None:
        return value
    return str(value)


def clean(row: Mapping[str, Any]) -> dict[str, Any]:
    """A packet row: JSON-safe and free of verdict-shaped keys (raises, at the source)."""
    hits = sorted(k for k in row if str(k).lower() in PACKET_FORBIDDEN)
    if hits:
        raise ValueError(f"adapter row carries verdict-shaped fields {hits}: an external engine "
                         f"is a researcher, never a validator (LAWS 5h)")
    return {str(k): py(v) for k, v in row.items()}


def candidate(family: str, symbols: Iterable[str], text: str, *, horizon: str,
              evidence: Mapping[str, Any], source: str) -> dict[str, Any]:
    """A STRUCTURED_HYPOTHESIS row: a registered family named outright, declared instruments,
    the engine's evidence riding along. The gauntlet judges; nothing here does."""
    if family not in FAMILIES:
        raise ValueError(f"{family!r} is not a registered price-only family: {FAMILIES}")
    return clean({"kind": "hypothesis", "family": family, "symbols": sorted(set(symbols)),
                  "text": text, "horizon": horizon, "evidence": dict(evidence),
                  "source": source, "authority": "none: a hypothesis for the ten gates"})


def packet(system_id: str, bundle: ResearchBundle, *, trials: int,
           candidates: Sequence[Mapping[str, Any]] = (),
           representations: Sequence[Mapping[str, Any]] = (),
           mechanisms: Sequence[Mapping[str, Any]] = (),
           research_methods: Sequence[Mapping[str, Any]] = (),
           datasets: Sequence[Mapping[str, Any]] = (),
           note: str = "") -> ExternalResearchPacket:
    """Build the packet through the contract: every row cleaned, every trial charged."""
    return ExternalResearchPacket(
        system_id=system_id, run_id=run_id_for(system_id, bundle), commit=commit_of(system_id),
        candidates=tuple(clean(r) for r in candidates),
        datasets=tuple(clean(r) for r in datasets),
        mechanisms=tuple(clean(r) for r in mechanisms),
        representations=tuple(clean(r) for r in representations),
        research_methods=tuple(clean(r) for r in research_methods),
        trials_charged=int(trials),
        provenance={"bundle_id": bundle.bundle_id, "bundle_digest": bundle.digest(),
                    "watermark": bundle.watermark(), "seed": bundle.seed,
                    "question": bundle.question, "note": note,
                    "produced_at": datetime.now(tz=UTC).isoformat(timespec="seconds")})


def unmeasured(system_id: str, bundle: ResearchBundle, why: str) -> ExternalResearchPacket:
    """The engine did not run: a packet that says so BY NAME, with zero trials charged."""
    return packet(system_id, bundle, trials=0,
                  research_methods=({"kind": "UNMEASURED", "system": system_id, "why": why},),
                  note="UNMEASURED")


def is_unmeasured(p: ExternalResearchPacket) -> bool:
    return (p.empty() or (all(str(r.get("kind")) == "UNMEASURED" for r in p.research_methods)
            and not (p.candidates or p.representations or p.mechanisms or p.datasets)))


def to_dict(p: ExternalResearchPacket) -> dict[str, Any]:
    return {"system_id": p.system_id, "run_id": p.run_id, "commit": p.commit,
            "candidates": list(p.candidates), "datasets": list(p.datasets),
            "mechanisms": list(p.mechanisms), "representations": list(p.representations),
            "research_methods": list(p.research_methods), "trials_charged": p.trials_charged,
            "provenance": dict(p.provenance), "counts": p.counts()}


def cli(run: Callable[[ResearchBundle], ExternalResearchPacket], system_id: str,
        argv: Sequence[str] | None = None) -> int:
    """`--bundle <manifest> --out <packet.json>`: the entry point the sandbox runner invokes.
    An adapter that raises still leaves a packet -- UNMEASURED with the failure named -- and
    exits 3, so the runner records RUN_FAILED with a reason instead of an empty out/ directory."""
    ap = argparse.ArgumentParser(description=f"{system_id} adapter (LAWS 5h sandbox worker)")
    ap.add_argument("--bundle", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args(list(argv) if argv is not None else None)
    bundle = load_bundle(Path(a.bundle))
    code = 0
    try:
        result = run(bundle)
    except Exception:
        tail = traceback.format_exc().strip().splitlines()[-3:]
        result = unmeasured(system_id, bundle, "adapter raised: " + " | ".join(tail)[:600])
        code = 3
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_suffix(out.suffix + ".tmp")
    tmp.write_text(json.dumps(to_dict(result), indent=1, default=str), encoding="utf-8")
    os.replace(tmp, out)
    sys.stdout.write(f"{system_id}: {result.counts()} -> {out}\n")
    return code


# ------------------------------------------------------------------------------- shared maths

def realised_vol(rets: Any, window: int) -> Any:
    """Rolling standard deviation of returns (trailing, NaN-padded), numpy only."""
    import numpy as np
    r = np.asarray(rets, dtype=float)
    out = np.full(r.shape[0], np.nan)
    if r.shape[0] >= window:
        c = np.cumsum(np.insert(r, 0, 0.0))
        c2 = np.cumsum(np.insert(r * r, 0, 0.0))
        mean = (c[window:] - c[:-window]) / window
        var = (c2[window:] - c2[:-window]) / window - mean * mean
        out[window - 1:] = np.sqrt(np.maximum(var, 0.0))
    return out


def ma_cross_objective(frame: BarFrame, fast: int, slow: int, cost_pts: float,
                       tick: float) -> dict[str, float]:
    """The objective the parameter-search engines share: a moving-average cross over the frame,
    charged the bundle's own spread. Returns EVIDENCE fields (objective_return,
    objective_drawdown, n_trades) -- names chosen so nothing here reads as a verdict."""
    import numpy as np
    c = np.asarray(frame.close, dtype=float)
    fast, slow = int(max(2, fast)), int(max(3, slow))
    if slow <= fast or c.shape[0] <= slow + 2:
        return {"objective_return": 0.0, "objective_drawdown": 0.0, "n_trades": 0.0}
    k_f = np.convolve(c, np.ones(fast) / fast, mode="valid")
    k_s = np.convolve(c, np.ones(slow) / slow, mode="valid")
    k_f = k_f[slow - fast:]
    pos = np.where(k_f > k_s, 1.0, -1.0)
    px = c[slow - 1:]
    rets = np.diff(np.log(np.maximum(px, 1e-12)))
    pnl = pos[:-1] * rets
    flips = np.abs(np.diff(pos)) > 0
    cost = (cost_pts * tick / np.maximum(px[1:], 1e-12)) if np.isfinite(cost_pts) else 0.0
    pnl = pnl - flips * cost
    eq = np.cumsum(pnl)
    dd = float(np.max(np.maximum.accumulate(eq) - eq)) if eq.size else 0.0
    return {"objective_return": float(eq[-1]) if eq.size else 0.0, "objective_drawdown": dd,
            "n_trades": float(flips.sum())}


#: The shared design matrix: three lagged returns and the trailing realised vol.
LAGGED_FEATURE_NAMES: tuple[str, ...] = ("r_1", "r_2", "r_3", "vol_24")


def lagged_design(frame: BarFrame, *, lags: int = 3, window: int = 24, target_bars: int = 1,
                  era_bars: int = 0) -> tuple[Any, Any, Any]:
    """(X, y, era): lagged log returns and realised vol at t-1 against the return over the next
    `target_bars` bars, aligned so nothing in X is later than the bar y starts at. `era` numbers
    rows in blocks of `era_bars` (0 -> one era) for per-era scoring. Numpy only."""
    import numpy as np
    r = frame.log_returns()
    vol = realised_vol(r, window)
    idx = np.arange(window + lags, r.shape[0] - target_bars + 1)
    if idx.shape[0] <= 0:
        return np.zeros((0, lags + 1)), np.zeros(0), np.zeros(0, dtype=int)
    cols = [r[idx - k] for k in range(1, lags + 1)] + [vol[idx - 1]]
    X = np.column_stack(cols)
    if target_bars == 1:
        y = r[idx]
    else:
        c = np.cumsum(np.insert(r, 0, 0.0))
        y = c[idx + target_bars] - c[idx]
    ok = np.isfinite(X).all(axis=1) & np.isfinite(y)
    era = (np.arange(idx.shape[0]) // era_bars) if era_bars > 0 else np.zeros(idx.shape[0],
                                                                                dtype=int)
    return X[ok], y[ok], era[ok]


def api_probe(system_id: str, lib: Any, names: Sequence[str]) -> dict[str, Any]:
    """What an importable-but-not-driven upstream exposes: the measured API surface, so the
    ledger records "imported, these names present" rather than a guess."""
    present = [n for n in names if hasattr(lib, n)]
    return {"kind": "api_surface", "system": system_id,
            "version": str(getattr(lib, "__version__", "") or "UNMEASURED"),
            "expected_names": list(names), "present": present,
            "public_names": sorted(n for n in dir(lib) if not n.startswith("_"))[:40]}

```

### libs\research\capability_ratchet.py
```python
"""THE CAPABILITY RATCHET (R0104) -- every aspect of the desk carries a score, and it only rises.

THE STANDING ORDER, AND WHY IT HAD NO INSTRUMENT. The principal's order is that every aspect of
this desk is pushed toward 10/10 every day, non-exhaustively. Until now that rating existed only
in conversation: somebody said "risk rails are maybe a 7" and nothing wrote it down. A rating
nobody records cannot ratchet, cannot be diffed, and cannot fail -- so the order was enforced by
remembering to care, which is the thing this desk builds machinery to stop relying on. A score
that can silently fall is not a standard; it is a mood.

WHAT THIS IS, AND WHAT IT IS NOT. It is the aggression ratchet's idiom (libs/doctrine/ratchet.py)
pointed at CAPABILITY instead of constitutional aggression: a high-water mark per named aspect,
raised automatically and never lowered by code. It is NOT a second copy of check_ratchets.py --
that fence holds individual scalar METRICS above their own floors and deliberately refuses to say
what is "good". This one answers the different question the standing order actually asks: on the
desk's own 0-10 scale, where does each aspect stand, and WHAT IS STOPPING IT FROM BEING ONE POINT
HIGHER. The binding constraint is the whole product; the number is how the constraint gets found.

THE HONESTY RULE, which outranks every other property here. A component with no measurement
scores UNMEASURED. It is NEVER silently treated as 0 and never as 10 -- 0 would manufacture a
defect out of ignorance and 10 would manufacture a capability out of it, and the second failure is
how an all-green board hides an empty one (scripts/check_clock_provenance.py, L1.28a). UNMEASURED
is its own state, it is reported in its own list, and it is excluded from the aspect mean rather
than folded into it. A MEASURED zero is different and is allowed: the desk has promoted nothing to
a live rung, and 0.0 is the honest reading of that.

TRUNCATION IS NOT STRENGTH. data/mutation_score.json carries its own `budget_truncated` flag: a
run that stopped at a mutant budget sampled the easy end of the file and its kill rate is a
sampling artifact, not a strength measurement. Those targets are excluded from the score and
listed as UNMEASURED, because scoring them would let the desk buy points by running LESS.

DELETION IS WEAKENING, inherited unchanged from the constitution ratchet. A component that had a
high-water mark and no longer measures is not neutral -- the capability it evidenced is now
unevidenced, so the aspect is scored as having FALLEN with WENT-DARK named as the cause. Otherwise
deleting the measurement would be the trivial way around the entire mechanism.

THE TAXONOMY IS EXHAUSTIVE BY INTENT AND IT ONLY WIDENS. "Every aspect" is not the four anyone
would think to grade. It is also the pager between incidents, cost-model freshness, the tape's
clock provenance, seat credentials, dependency drift against the deployed pins, backup restore
drills, mutation BREADTH as a distinct question from kill rate, scheduler manifest drift, and
permission hygiene -- the minor surface, which is precisely where a desk rots, because nobody
grades it. Every one of them is read from an artifact another organ already writes: this module
measures NOTHING itself, since a scorer that measures is a scorer that can be gamed by rewriting
the scorer, and it re-derives no threshold another organ owns.

MEASURING MORE IS NOT REGRESSING, and getting this wrong would have destroyed the instrument.
Widening an aspect lowers its mean against a mark earned over fewer components, and reporting that
as a fall makes the gate permanently red -- the exact failure check_ratchets.py already fixed by
giving each mutation target its own floor ("a fence that fires when the desk measures MORE trains
everyone to ignore it"). So a fall whose mark the CURRENT component set could not have produced
even at every component's own best is WIDENED, not FELL: the mark is kept, the gap is printed, and
the instruction is to beat it over the wider set. It cannot launder a regression -- component marks
are per component, so anything that actually dropped names itself as a cause first.

WHAT IT CANNOT DO, stated plainly because a control that overstates itself is worse than none. The
map from artifact to 0-10 is a JUDGEMENT -- the ladders and fractions below are written down so
they can be argued with, but they are not discovered facts, and a component scoring 8 does not
mean the desk is 80% of the way to excellent at it. What the artifact does claim is narrower and
worth having: the score cannot fall without a named cause, the aspect list cannot quietly shrink,
an unmeasured aspect cannot read as a healthy one, every reading cites the artifact it came from,
and every reading carries the specific next thing that would raise it. One further limit is worth
naming: the desk-wide binding constraint ranks only MEASURED components, so a desk with large
unmeasured holes will keep pointing at a real but possibly not-worst defect. The unmeasured list
sits directly beside it for exactly that reason, and its instruction is always the same: measure
it, then the ranking means more.
"""

from __future__ import annotations

import json
import math
import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

__all__ = [
    "ARTIFACT_PATH",
    "ASPECT_KEYS",
    "AT_CEILING",
    "CANARY_MAX_AGE_H",
    "FELL",
    "FLATLINE",
    "MEASURED",
    "NEW",
    "RAISED",
    "SCALE_MAX",
    "STALL_DAYS",
    "UNMEASURED",
    "WENT_DARK",
    "WIDENED",
    "Aspect",
    "Component",
    "Marks",
    "Verdict",
    "age_hours",
    "attainable",
    "binary_component",
    "build_artifact",
    "desk_binding_constraint",
    "fraction_component",
    "inverse_ladder_component",
    "ladder_component",
    "liveness_component",
    "load_marks",
    "ratchet",
    "read_capability",
    "score_aspect",
    "stale_gate",
    "unmeasured_component",
]

#: Where the desk's capability record lives. data/, not docs/: it is rewritten daily by cron and a
#: daily-churning file in git is noise -- the ratchet's protection is that nothing in code lowers a
#: mark, not that a human reviews every reading.
ARTIFACT_PATH = Path("data/CAPABILITY_RATCHET.json")

#: The scale the principal's order is stated on. 10/10 is the target for every aspect, every day.
SCALE_MAX = 10.0

MEASURED = "MEASURED"
UNMEASURED = "UNMEASURED"

#: Movements. Each is a distinct fact and none may be folded into another: FLATLINE is not a
#: failure, FELL is, and WENT-DARK is a fall whose cause is the measurement disappearing.
RAISED = "RAISED"
FLATLINE = "FLATLINE"
AT_CEILING = "AT-CEILING"
FELL = "FELL"
WENT_DARK = "WENT-DARK"
NEW = "NEW"

#: WIDENED -- the aspect mean fell because the desk started grading itself on MORE, while every
#: component that already had a mark still holds it. This is not a defect and must not be reported
#: as one, for the reason check_ratchets.py:60-64 already learned the hard way: a single aggregate
#: across targets meant MEASURING A NEW FILE looked like a regression, and "a fence that fires when
#: the desk measures MORE trains everyone to ignore it -- the opposite of L1.0".
#:
#: IT CANNOT HIDE A REGRESSION, and that is why it is safe to distinguish. Component high-water
#: marks are held per component, so any pre-existing component that dropped, or went dark, or
#: stopped measuring, produces a NAMED CAUSE and the aspect is FELL regardless of what was added
#: beside it. WIDENED is reachable only when NOTHING that was already measured got worse. The
#: aspect's own high-water mark is still not lowered -- the record keeps saying 9.0 while today
#: says 4.5, and the gap is the honest statement that the old 9.0 was measured over less.
WIDENED = "WIDENED"

#: Float comparison slack. Scores are rounded to 0.1 so that FLATLINE means something -- with raw
#: floats every reading differs in the twelfth decimal and "no movement" could never be reported.
EPS = 1e-9

#: Days with no aspect setting a new best before the ratchet itself reports a defect. The order is
#: DAILY, so a week of nothing is the order not being followed, not a quiet patch. Deliberately not
#: 1 day: the aspect list cannot each move every day, and a gate that fires every morning gets
#: acknowledged into silence, which is worse than no gate.
STALL_DAYS = 7.0


@dataclass(frozen=True)
class Component:
    """One measured (or explicitly unmeasured) input to an aspect, with the artifact that fed it.

    `constraint` is the point of the whole record: the specific, quantified next thing that buys
    one more point on this component.
    """

    key: str
    state: str
    score: float | None
    artifact: str
    detail: str
    constraint: str


@dataclass(frozen=True)
class Aspect:
    """A named aspect of the desk, scored 0-10 from its components -- or UNMEASURED."""

    key: str
    ceiling: str
    state: str
    score: float | None
    components: tuple[Component, ...]
    binding_constraint: str

    @property
    def artifacts(self) -> tuple[str, ...]:
        seen: list[str] = []
        for c in self.components:
            if c.artifact not in seen:
                seen.append(c.artifact)
        return tuple(seen)

    @property
    def unmeasured(self) -> tuple[Component, ...]:
        return tuple(c for c in self.components if c.state == UNMEASURED)


@dataclass(frozen=True)
class Marks:
    """The high-water record. Aspect marks AND component marks, because a fall must be localised.

    Component marks are what make a cause NAMEABLE. With aspect marks alone the artifact could
    only say "governance fell to 6.4", which is a fact nobody can act on; with component marks it
    says which measurement regressed, by how much, and out of which file.

    They are also what keeps an aspect mark MEANINGFUL as the taxonomy grows. A mark higher than
    the mean of the current components' own bests cannot have been earned over the current set
    (see `attainable`), so the marks carry their own evidence about whether a comparison is even
    valid -- no remembered component list, and no migration for records written before the rule
    existed.
    """

    aspect_high_water: dict[str, float]
    component_high_water: dict[str, float]
    last_raise_at: str
    first_recorded: str
    n_raises: int


@dataclass(frozen=True)
class Verdict:
    """What one aspect did against its own record this run."""

    aspect: str
    movement: str
    score: float | None
    high_water: float | None
    cause: str


# --------------------------------------------------------------------------------------------
# SCORING PRIMITIVES. Every count-to-score map is written down here rather than inlined, because a
# rubric that lives inside one call site is a rubric nobody can argue with.
# --------------------------------------------------------------------------------------------

#: Ladder for "how many of these has the desk actually produced" counts. Ten rungs, each roughly
#: 1.4x the last, so points get harder to buy as the count grows -- a linear map would let a desk
#: reach 10/10 by grinding the cheap end of any counter it happens to control.
COUNT_LADDER: tuple[int, ...] = (1, 2, 3, 5, 8, 12, 18, 25, 35, 50)

#: Ladder for the test suite. Linear because suite size genuinely is linear work per module, and
#: the top rung (500 collectable modules) is a stated ambition rather than a discovered ceiling.
SUITE_LADDER: tuple[int, ...] = (50, 100, 150, 200, 250, 300, 350, 400, 450, 500)

#: INVERSE ladder for defect counts -- doubling. Cutting 46 live defects to 31 is one point; the
#: last point costs going from 1 to 0, which is correct: the final defect is the expensive one.
DEFECT_LADDER: tuple[int, ...] = (1, 2, 4, 8, 16, 32, 64, 128, 256, 512)


def _round(score: float) -> float:
    """Clamp into the scale and round to 0.1. Rounding is load-bearing -- see EPS."""
    return round(min(max(score, 0.0), SCALE_MAX), 1)


def _read_json(path: Path) -> dict[str, Any] | None:
    """Missing, unreadable and not-an-object all mean the same thing here: NO MEASUREMENT.

    They are not swallowed -- every caller turns this None into an UNMEASURED component that names
    the artifact it wanted, so an absent file is louder in the output than a bad number would be.
    """
    try:
        data = json.loads(path.read_text("utf-8"))
    except (OSError, json.JSONDecodeError, ValueError, UnicodeDecodeError):
        return None
    return data if isinstance(data, dict) else None


def _read_jsonl(path: Path) -> list[dict[str, Any]] | None:
    """Append-only ledgers, as a list of objects. None means NO LEDGER -- same contract as
    _read_json. An unparseable LINE is skipped (a half-written tail row is normal in a file being
    appended to); an unreadable FILE is the absent case and becomes UNMEASURED at the call site."""
    try:
        text = path.read_text("utf-8")
    except (OSError, UnicodeDecodeError):
        return None
    rows: list[dict[str, Any]] = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        try:
            obj = json.loads(stripped)
        except (json.JSONDecodeError, ValueError):
            continue
        if isinstance(obj, dict):
            rows.append(obj)
    return rows


def _rows(doc: dict[str, Any] | None, key: str) -> list[dict[str, Any]] | None:
    """A list-of-objects field, or None for "the artifact did not carry one"."""
    raw = doc.get(key) if doc is not None else None
    if not isinstance(raw, list):
        return None
    return [r for r in raw if isinstance(r, dict)]


def _mapping(doc: dict[str, Any] | None, key: str) -> dict[str, Any] | None:
    """An object-valued field, or None for "the artifact did not carry one"."""
    raw = doc.get(key) if doc is not None else None
    return raw if isinstance(raw, dict) else None


def _len_or_none(value: object) -> float | None:
    """len() of a list/dict field, or None when the field is absent or the wrong shape.

    Used wherever a defect COUNT is published as the defect LIST. An absent list must not read as
    zero defects -- that is the shape in which "nobody checked" impersonates "nothing wrong".
    """
    return float(len(value)) if isinstance(value, list | dict) else None


def _num(value: object) -> float | None:
    """A number, or None. `True` is not 1 here -- a bool arriving where a count belongs is a bug
    upstream, and silently scoring it would hide that."""
    if isinstance(value, bool) or not isinstance(value, int | float):
        return None
    return float(value)


def _parse_ts(raw: object) -> datetime | None:
    if not isinstance(raw, str) or not raw:
        return None
    try:
        ts = datetime.fromisoformat(raw)
    except ValueError:
        return None
    return ts if ts.tzinfo is not None else ts.replace(tzinfo=UTC)


def _field(doc: dict[str, Any] | None, key: str) -> Any:
    """A field for the DETAIL string, or "?" -- an absent artifact must still print something that
    says so. Never used to produce a score; scores come from _num(), which returns None."""
    if doc is None:
        return "?"
    return doc.get(key, "?")


def unmeasured_component(key: str, artifact: str, why: str) -> Component:
    """The honesty rule in one constructor: no score, and the reason is carried, not dropped."""
    return Component(
        key=key, state=UNMEASURED, score=None, artifact=artifact, detail=why,
        constraint=f"MEASURE IT -- {why}. Unmeasured is neither a 0 nor a 10; it is the state "
                   "of not knowing, and it stays that until an artifact says otherwise.")


def fraction_component(key: str, artifact: str, num: float | None, den: float | None, *,
                       unit: str, detail: str) -> Component:
    """Score = 10 x (num/den). Used wherever the desk already counts a numerator and denominator.

    A ZERO DENOMINATOR IS UNMEASURED, never 10. "0 of 0 organs are stale" is not a healthy desk,
    it is an empty one, and this is the exact shape in which unmeasured most often tries to pass
    itself off as perfect.
    """
    if num is None or den is None:
        return unmeasured_component(key, artifact, f"{artifact} did not yield {unit}")
    if den <= 0:
        return unmeasured_component(
            key, artifact,
            f"{artifact} reports a zero denominator for {unit} -- a ratio over nothing is not a "
            "measurement and must never read as full marks")
    score = _round(SCALE_MAX * num / den)
    if score >= SCALE_MAX - EPS:
        constraint = f"AT CEILING ({num:g}/{den:g} {unit}) -- the work is now HOLDING it"
    else:
        # The next WHOLE point, in the numerator's own units. Whole counts are ceiled to whole
        # counts: "23.1 of 42 organs producing" is not an instruction anybody can follow.
        target = (score + 1.0) / SCALE_MAX * den
        need = (float(math.ceil(target)) if float(num).is_integer() and float(den).is_integer()
                else math.ceil(target * 1000) / 1000)
        if need > den:
            # The last fractional point costs less than a full point's worth of numerator, and
            # printing "103 of 100" would be an instruction that cannot be followed. The honest
            # constraint at this end of the scale is the whole remaining gap.
            constraint = (f"+{den - num:g} {unit} ({num:g} -> {den:g}, the whole remaining gap) "
                          f"is the last +{SCALE_MAX - score:.1f} to 10/10")
        else:
            constraint = (f"+{need - num:g} {unit} ({num:g} -> {need:g} of {den:g}) buys the next "
                          "point")
    return Component(key=key, state=MEASURED, score=score, artifact=artifact, detail=detail,
                     constraint=constraint)


def ladder_component(key: str, artifact: str, count: float | None, rungs: tuple[int, ...], *,
                     unit: str, detail: str) -> Component:
    """Score = the number of ladder rungs the count has cleared."""
    if count is None:
        return unmeasured_component(key, artifact, f"{artifact} did not yield a count of {unit}")
    cleared = sum(1 for r in rungs if count >= r)
    score = _round(float(cleared))
    nxt = next((r for r in rungs if count < r), None)
    if nxt is None:
        constraint = (f"AT CEILING ({count:g} {unit}, top rung {rungs[-1]}) -- the ladder is "
                      "exhausted and the next point needs a HARDER ladder, argued for in the diff")
    else:
        constraint = (f"+{nxt - count:g} {unit} ({count:g} -> {nxt}, the next rung) buys the "
                      "next point")
    return Component(key=key, state=MEASURED, score=score, artifact=artifact, detail=detail,
                     constraint=constraint)


def inverse_ladder_component(key: str, artifact: str, count: float | None,
                             rungs: tuple[int, ...], *, unit: str, detail: str) -> Component:
    """Score = 10 minus the rungs cleared -- for counts where LOWER is the capability."""
    if count is None:
        return unmeasured_component(key, artifact, f"{artifact} did not yield a count of {unit}")
    cleared = [r for r in rungs if count >= r]
    score = _round(SCALE_MAX - len(cleared))
    if not cleared:
        constraint = f"AT CEILING ({count:g} {unit}) -- the work is now HOLDING it"
    else:
        target = cleared[-1] - 1
        constraint = (f"-{count - target:g} {unit} ({count:g} -> {target}, back under the "
                      f"{cleared[-1]} rung) buys the next point")
    return Component(key=key, state=MEASURED, score=score, artifact=artifact, detail=detail,
                     constraint=constraint)


def binary_component(key: str, artifact: str, ok: bool | None, *, detail: str, fix: str,
                     held: str = "") -> Component:
    """A capability that is either EVIDENCED or not: 10 or a MEASURED 0, never a hedge.

    `ok is None` is the third state and it is the one that matters: it means the artifact never
    made the claim either way, so the component is UNMEASURED rather than being pushed to whichever
    end of the scale the caller finds convenient. Callers pass None deliberately -- a missing flag
    is not a False. Note the explicit `is None` / `is True` tests: a truthiness test would read an
    absent field and a False field as the same fact, which is the entire failure this guards.
    """
    if ok is None:
        return unmeasured_component(key, artifact, detail)
    return Component(
        key=key, state=MEASURED, score=SCALE_MAX if ok else 0.0, artifact=artifact, detail=detail,
        constraint=(held or "AT CEILING -- evidenced, and the work is now HOLDING it") if ok
        else fix)


def age_hours(doc: dict[str, Any] | None, field: str, now: datetime) -> float | None:
    """How old is this artifact's own stamp, in hours? None when it cannot be established.

    None covers three cases that must NOT be told apart by the caller, because they license the
    same conclusion and nothing weaker: no document, no stamp field, and a stamp that will not
    parse. The last one is the sharpest form of the fail-open this exists to close -- a timestamp
    that can never be shown to be OLD can never be shown to be old, so trusting the artifact
    beside it is trusting something that has no expiry at all.

    Negative ages (a stamp in the future, an NTP step) come back as written rather than clamped;
    callers compare against a positive bound, so a future stamp reads as fresh, which is the right
    failure direction for a clock that just moved.
    """
    stamped = _parse_ts(doc.get(field)) if doc is not None else None
    if stamped is None:
        return None
    return round((now - stamped).total_seconds() / 3600.0, 2)


def stale_gate(key: str, artifact: str, doc: dict[str, Any] | None, field: str, now: datetime, *,
               max_age_h: float, owner: str, what: str) -> Component | None:
    """THE AGE CHECK, as one call, so that skipping it is a visible omission rather than a habit.

    Returns an UNMEASURED component when the artifact is absent, unstamped, unparseable or OLDER
    than `max_age_h`; returns None when it is fresh enough to be read. A caller that wants to score
    a state artifact writes this line first, and the reviewer can see whether they did.

    WHY A GATE RATHER THAN A FRESHER `_read_json`. A silent "return None when stale" would collapse
    stale into absent, and those are different findings with different repairs: nothing was ever
    written versus something stopped writing. The gate keeps them distinguishable in the reason
    string while making the CHECK itself a single unmissable statement.

    `owner` names where the bound came from. This module owns no cadences: the number is the one
    the producing organ already declares, cited so the two cannot drift into disagreeing.
    """
    age = age_hours(doc, field, now)
    if age is None:
        return unmeasured_component(
            key, artifact,
            f"{artifact} carries no usable `{field}` stamp -- {what} cannot be shown to be "
            "current, and an artifact with no readable age can never be shown to be STALE either, "
            "which is the state in which a dead monitor reads exactly like a live one")
    if age > max_age_h:
        return unmeasured_component(
            key, artifact,
            f"{artifact} is {age:g}h old against a {max_age_h:g}h bound ({owner}) -- {what}. A "
            "stale reading is not a bad reading and not a good one: it is last week's observation "
            "wearing today's date, and scoring it either way invents information")
    return None


#: The desk's per-organ liveness roster: which scheduled organ produced, how long ago, and against
#: what tolerance. Read by many aspects below, because "is the thing that measures X still running"
#: is a precondition for believing anything X publishes.
_LIVENESS = "data/organ_liveness.json"

#: The verdict vocabulary of check_organ_liveness.py, read rather than restated. FRESH means the
#: organ produced inside ITS OWN declared cadence; the two failure words are kept apart because
#: they need different repairs -- NEVER-PRODUCED is wiring, STALE is something that stopped.
_LIVENESS_FRESH = "FRESH"
_LIVENESS_DEAD = ("STALE", "NEVER-PRODUCED")


def _liveness_row(root: Path, script: str) -> dict[str, Any] | None:
    for row in _rows(_read_json(root / _LIVENESS), "organs") or []:
        if row.get("script") == script:
            return row
    return None


def liveness_component(root: Path, key: str, script: str) -> Component:
    """Is ONE named organ producing inside its own cadence, per the organ that owns cadences?

    THE THRESHOLD IS NOT SET HERE, deliberately. check_organ_liveness.py declares every organ's
    cadence and tolerance and publishes a per-row verdict; this reads that verdict. Re-deriving
    "how old is too old" here would give the desk two disagreeing answers about one organ, and the
    one this module invented would be the one nobody maintains.

    An organ ABSENT FROM THE ROSTER is UNMEASURED, never a zero: nothing is watching it, which is
    a different (and more actionable) fact than it being late.
    """
    row = _liveness_row(root, script)
    if row is None:
        return unmeasured_component(
            key, _LIVENESS,
            f"{_LIVENESS} carries no row for {script} -- the organ is not on the liveness roster, "
            "so NOTHING measures whether it produces. Add it there; an unwatched organ reads the "
            "same as a healthy one from here")
    state = str(row.get("state") or "")
    raw = row.get("artifacts")
    evidence = ", ".join(str(a) for a in raw) if isinstance(raw, list) and raw else "?"
    age, tol = _num(row.get("age_h")), _num(row.get("tolerance_h"))
    detail = (f"{script} is {state or 'UNSTATED'} "
              f"(age {age if age is not None else 'never'}h against its own "
              f"{tol if tol is not None else '?'}h tolerance); evidence {evidence}")
    if state == _LIVENESS_FRESH:
        return Component(key=key, state=MEASURED, score=SCALE_MAX, artifact=_LIVENESS,
                         detail=detail,
                         constraint="AT CEILING -- producing inside its own declared cadence, and "
                                    "the work is now HOLDING it")
    if state in _LIVENESS_DEAD:
        fix = (f"WIRE IT -- {script} has NEVER produced {evidence}; that is a path/venv/lock "
               "fault, not a late run" if state == "NEVER-PRODUCED" else
               f"RESTART IT -- {script} last produced {age if age is not None else '?'}h ago "
               f"against a {tol if tol is not None else '?'}h tolerance; something STOPPED "
               "(auth, quota, upstream), which is a different repair from never wired")
        return Component(key=key, state=MEASURED, score=0.0, artifact=_LIVENESS, detail=detail,
                         constraint=fix)
    return unmeasured_component(
        key, _LIVENESS,
        f"{script} carries liveness state {state or 'EMPTY'!r}, which is neither FRESH nor a "
        "declared failure -- an unrecognised verdict is not scored in either direction")


# --------------------------------------------------------------------------------------------
# COMPONENT BUILDERS. Each reads ONE artifact this desk already produces. Nothing here computes a
# fresh measurement: a scorer that measures is a scorer that can be gamed by rewriting the scorer.
# --------------------------------------------------------------------------------------------

_MUTATION = "data/mutation_score.json"


def mutation_components(root: Path, key: str, prefixes: tuple[str, ...]) -> list[Component]:
    """Mutation kill rate over one slice of the tree, with TRUNCATED RUNS REFUSED.

    `budget_truncated` means the harness stopped at its mutant budget, so the kill rate describes
    the mutants it happened to reach rather than the file. Scoring it would reward a SHORTER run,
    which is the denominator trick (§34) wearing a stopwatch. Truncated targets become UNMEASURED
    components naming themselves, so the gap is visible instead of averaged away.

    The two reading rules -- skip truncated, prefer `adjusted_kill_rate` over the raw one where an
    equivalence register applies -- are lifted verbatim from scripts/check_ratchets.py:78-84 rather
    than re-derived. Two organs reading the same artifact by different rules is how a desk ends up
    with two disagreeing truths about one file.
    """
    doc = _read_json(root / _MUTATION)
    if doc is None:
        return [unmeasured_component(key, _MUTATION, f"{_MUTATION} absent or unreadable")]
    raw = doc.get("targets")
    targets = [t for t in raw if isinstance(t, dict)] if isinstance(raw, list) else []
    in_scope = [t for t in targets
                if isinstance(t.get("target"), str)
                and str(t["target"]).startswith(prefixes)]
    bar = _num(doc.get("bar"))
    out: list[Component] = []
    rates: list[float] = []
    names: list[str] = []
    for t in in_scope:
        name = str(t["target"])
        rate = _num(t.get("adjusted_kill_rate"))
        if rate is None:
            rate = _num(t.get("kill_rate"))
        if t.get("budget_truncated") is True:
            out.append(unmeasured_component(
                f"{key}::{Path(name).name}", _MUTATION,
                f"{name} ran BUDGET-TRUNCATED ({t.get('total')} of {t.get('n_sites')} sites) -- a "
                "truncated run samples the mutants it reached, so its kill rate is not a strength "
                "measurement and is refused rather than scored"))
            continue
        if rate is None:
            out.append(unmeasured_component(
                f"{key}::{Path(name).name}", _MUTATION, f"{name} carries no kill rate"))
            continue
        rates.append(rate)
        names.append(f"{Path(name).name} {rate:.2f}")
    if not rates:
        scope = ", ".join(prefixes)
        out.insert(0, unmeasured_component(
            key, _MUTATION,
            f"no completed mutation run over {scope} -- every target in scope is absent or "
            "budget-truncated"))
        return out
    mean = sum(rates) / len(rates)
    detail = (f"{len(rates)} target(s) at bar {bar if bar is not None else '?'}: "
              f"{', '.join(names)}; measured {doc.get('measured', '?')}")
    out.insert(0, fraction_component(key, _MUTATION, round(mean * 100, 2), 100.0,
                                     unit="% mutants killed", detail=detail))
    return out


_CALIBRATION = "data/calibration_status.json"


def _statistical_validation(root: Path, _now: datetime) -> list[Component]:
    out = mutation_components(root, "mutation_kill_validation_stack",
                              ("libs/validation/", "libs/autodiscovery/"))

    # A DESK THAT CANNOT SCORE ITS OWN FORECASTS CANNOT KNOW IT IS CALIBRATED. n_resolved/
    # n_forecasts is the completeness of the scoring loop, not the Brier score -- scoring the
    # Brier of zero resolved forecasts would be the 0/0 lie, and check_calibration already refuses
    # it by publishing status BLIND.
    cal = _read_json(root / _CALIBRATION)
    out.append(fraction_component(
        "forecasts_resolved", _CALIBRATION, _num(_field(cal, "n_resolved")),
        _num(_field(cal, "n_forecasts")), unit="logged forecasts scored against an outcome",
        detail=f"status {_field(cal, 'status')}: {_field(cal, 'detail')}; brier "
               f"{_field(cal, 'brier')}, {_field(cal, 'n_overdue')} overdue"))
    return out


_SUITE = "docs/research/test_suite_record.json"
_GRAVEYARD = "docs/graveyard.md"
_BREADTH = "data/strategy_coverage.json"
_CENSUS = "data/mechanism_census.json"
_SURFACES = "data/strategy_breadth.json"

#: A graveyard heading is an ENTRY (a killed hypothesis or a retired capability) rather than a
#: section banner when it names a thing: a backticked path or a snake_case identifier. Counting
#: every heading would score the three banners as kills; hardcoding the banner titles would rot the
#: first time somebody adds a section.
_GRAVE_HEADING = re.compile(r"^#{2,3}\s+(?P<title>.+?)\s*$", re.MULTILINE)
_GRAVE_ENTRY = re.compile(r"`|[a-z0-9]+_[a-z0-9_]+")


def graveyard_kills(text: str) -> int:
    return sum(1 for m in _GRAVE_HEADING.finditer(text)
               if _GRAVE_ENTRY.search(m.group("title")) is not None)


def _research_discipline(root: Path, _now: datetime) -> list[Component]:
    out: list[Component] = []

    suite = _read_json(root / _SUITE)
    n_modules = _num(_field(suite, "max_collected"))
    out.append(ladder_component(
        "test_suite_size", _SUITE, n_modules, SUITE_LADDER, unit="collectable test modules",
        detail=f"high-water suite size {n_modules} as of {_field(suite, 'at')}"))

    try:
        kills: int | None = graveyard_kills((root / _GRAVEYARD).read_text("utf-8"))
    except OSError:
        kills = None
    out.append(ladder_component(
        "hypotheses_killed", _GRAVEYARD, kills, COUNT_LADDER, unit="graveyard entries",
        detail=f"{kills} permanent kill/retirement entries -- the desk's record of ideas it "
               "closed rather than left open"))

    breadth = _read_json(root / _BREADTH)
    out.append(fraction_component(
        "families_hunted", _BREADTH, _num(_field(breadth, "n_hunted")),
        _num(_field(breadth, "n_families")), unit="families genuinely hunted",
        detail=f"{_field(breadth, 'n_hunted')}/{_field(breadth, 'n_families')} distinct families "
               f"worked; thin {_field(breadth, 'n_thin')}, unhunted "
               f"{_field(breadth, 'n_unhunted')}"))

    # MECHANISM DIVERSITY, from the census that owns the taxonomy. Counting candidates would
    # reward reparameterising one idea 40 times; classes occupied cannot be bought that way.
    census = _read_json(root / _CENSUS)
    div = _mapping(census, "diversity") or {}
    out.append(fraction_component(
        "mechanism_classes_occupied", _CENSUS, _num(div.get("n_classes_occupied")),
        _num(div.get("n_classes_in_taxonomy")), unit="taxonomy classes with a live candidate",
        detail=f"{div.get('n_classes_occupied')}/{div.get('n_classes_in_taxonomy')} classes "
               f"occupied over {div.get('n_candidates')} candidates; top class "
               f"{div.get('top_class')} at {div.get('top_class_share')} share"))
    out.append(fraction_component(
        "mechanism_diversity", _CENSUS, _num(div.get("diversity")), 1.0,
        unit="of the census's own normalised diversity index",
        detail=f"diversity {div.get('diversity')} (hhi {div.get('hhi')}, effective classes "
               f"{div.get('effective_classes')}); the CAMPAIGN is narrower still at "
               f"{(_mapping(census, 'campaign_diversity') or {}).get('diversity')}"))

    # HUNTING SURFACES CARRYING THE BREADTH MANDATE. `breadth.state` is checked because the
    # organ runs in a surfaces-only mode on a clean checkout: a partial run must not be scored as
    # a complete one, so the widened count is read and the live breadth measurement is not.
    surfaces = _read_json(root / _SURFACES)
    n_surf = _num(_field(surfaces, "n_surfaces"))
    unwidened = _len_or_none(_field(surfaces, "unwidened_surfaces"))
    out.append(fraction_component(
        "surfaces_carrying_the_mandate", _SURFACES,
        None if n_surf is None or unwidened is None else n_surf - unwidened, n_surf,
        unit="hunting surfaces carrying the breadth mandate",
        detail=f"status {_field(surfaces, 'status')}; live breadth state "
               f"{(_mapping(surfaces, 'breadth') or {}).get('state')} -- the live measurement is "
               "NOT scored here when it did not run"))
    return out


_GATE0 = "data/gate0_readiness.json"


def _gate0_rows(root: Path) -> list[dict[str, Any]]:
    doc = _read_json(root / _GATE0)
    raw = doc.get("rows") if doc is not None else None
    return [r for r in raw if isinstance(r, dict)] if isinstance(raw, list) else []


def _risk_rails(root: Path, _now: datetime) -> list[Component]:
    out = mutation_components(root, "mutation_kill_risk_stack", ("libs/risk/",))

    # THE RUIN RAIL IS BINARY AND ITS THIRD STATE IS THE INTERESTING ONE. gate0 records
    # BLOCKED-UNKNOWN when the state file cannot be read from this box -- which is neither clear
    # nor breached, and folding it into either direction would be exactly the lie this module
    # exists to prevent.
    row = next((r for r in _gate0_rows(root) if r.get("criterion") == "ruin_rail_clear"), None)
    status = str(row.get("status")) if row is not None else ""
    detail = str(row.get("detail", "")) if row is not None else f"{_GATE0} carries no ruin-rail row"
    if row is None or status.startswith("BLOCKED"):
        out.append(unmeasured_component(
            "ruin_rail_clear", _GATE0,
            f"ruin-rail state is {status or 'ABSENT'} -- {detail}"))
    else:
        clear = status == "READY"
        out.append(Component(
            key="ruin_rail_clear", state=MEASURED, score=SCALE_MAX if clear else 0.0,
            artifact=_GATE0, detail=f"ruin_rail_clear={status}: {detail}",
            constraint=("AT CEILING -- the rail is clear and the work is HOLDING it" if clear
                        else f"clear the ruin rail: {row.get('action') or detail}")))

    # EVERY NUMBER THAT MOVES MONEY CARRIES A CITED DERIVATION. Four money-path constants were
    # found defective in one session, all of them round numbers picked by analogy (L1.41/L2.4).
    sizing = _read_json(root / _SIZING)
    n_modules = _num(_field(sizing, "n_modules"))
    unjustified = _num(_field(sizing, "n_unjustified"))
    out.append(fraction_component(
        "sizing_constants_derived", _SIZING,
        None if n_modules is None or unjustified is None else n_modules - unjustified, n_modules,
        unit="money-path modules with every constant derived",
        detail=f"status {_field(sizing, 'status')}: {_field(sizing, 'detail')}"))

    # THE RAILS ARE ONLY AS GOOD AS THE LAST TIME THEY WERE FIRED IN ANGER. run_drills exercises
    # ruin re-entry, the derisk ladder and the naked-clock rail against temp-copy state.
    drills = _read_json(root / _DRILLS)
    out.append(fraction_component(
        "drills_passing", _DRILLS, _num(_field(drills, "passed")), _num(_field(drills, "n_drills")),
        unit="rail drills passing",
        detail=f"{_field(drills, 'passed')}/{_field(drills, 'n_drills')} drills passed at "
               f"{_field(drills, 'at')}; {_field(drills, 'critical_drill_failures')} CRITICAL "
               "failure(s)"))
    out.append(liveness_component(root, "drill_cadence", "scripts/run_drills.py"))
    return out


_LAW_GATE = "data/law_gate.json"
_AUDIT = "data/max_audit_report.json"
_ENFORCEMENT = "data/enforcement_matrix.json"
_LAW_FAMILIES = "data/law_families.json"
_FENCE_YIELD = "data/fence_yield.json"


def _audit_defects(root: Path, prefix: str) -> float | None:
    """Live audit defects whose id starts with `prefix`, or None when there is no audit at all.

    NO REPORT IS NOT ZERO DEFECTS. The distinction is the whole point of counting them here: an
    absent max_audit_report means nobody looked, and returning 0.0 would score that as a clean
    bill of health -- the exact inversion this module exists to prevent.
    """
    live = _rows(_read_json(root / _AUDIT), "live")
    if live is None:
        return None
    return float(sum(1 for r in live if str(r.get("id") or "").startswith(prefix)))


def _governance(root: Path, _now: datetime) -> list[Component]:
    out: list[Component] = []
    gate = _read_json(root / _LAW_GATE)
    n_fences = _num(_field(gate, "n_fences"))
    n_failed = _num(_field(gate, "n_failed"))
    passing = None if n_fences is None or n_failed is None else n_fences - n_failed
    out.append(fraction_component(
        "law_fences_passing", _LAW_GATE, passing, n_fences, unit="law fences passing",
        detail=f"{passing}/{n_fences} fences green; failures {_field(gate, 'failures')}"))

    audit = _read_json(root / _AUDIT)
    live = _field(audit, "live")
    n_live = float(len(live)) if isinstance(live, list) else None
    out.append(inverse_ladder_component(
        "audit_defects_live", _AUDIT, n_live, DEFECT_LADDER, unit="live audit defects",
        detail=f"{n_live} unacknowledged defects at {_field(audit, 'ran')}; "
               f"by scope {_field(audit, 'by_scope')}"))

    # A PRINCIPLE WITH NO FENCE IS A WISH. The enforcement matrix is the register of which
    # constitutional principles are held up by machinery rather than by attention.
    matrix = _read_json(root / _ENFORCEMENT)
    counts = _mapping(matrix, "counts") or {}
    out.append(fraction_component(
        "principles_mechanically_enforced", _ENFORCEMENT, _num(counts.get("ENFORCED")),
        _num(_field(matrix, "n_principles")), unit="principles held up by a fence",
        detail=f"{counts.get('ENFORCED')}/{_field(matrix, 'n_principles')} enforced over "
               f"{_field(matrix, 'n_fences')} fences; counts {counts}; unenforced "
               f"{_field(matrix, 'unenforced')}"))

    families = _read_json(root / _LAW_FAMILIES)
    n_fam = _num(_field(families, "n_families"))
    failing = _len_or_none(_field(families, "failing"))
    out.append(fraction_component(
        "law_families_enforced", _LAW_FAMILIES,
        None if n_fam is None or failing is None else n_fam - failing, n_fam,
        unit="law families fully enforced",
        detail=f"status {_field(families, 'status')}: {_field(families, 'detail')} over "
               f"{_field(families, 'n_laws_governed')} governed laws"))

    # A FENCE THAT HAS NEVER CAUGHT ANYTHING IS EITHER GUARDING NOTHING OR NOT LOOKING. Both are
    # worth a point of governance; check_fence_yield is the organ that decides which.
    yield_doc = _read_json(root / _FENCE_YIELD)
    out.append(fraction_component(
        "fences_earning_their_place", _FENCE_YIELD, _num(_field(yield_doc, "n_fired")),
        _num(_field(yield_doc, "n_fences")), unit="fences that have caught something real",
        detail=f"status {_field(yield_doc, 'status')}: {_field(yield_doc, 'detail')}; never run "
               f"{_field(yield_doc, 'n_never_run')}"))
    return out


_ASSETS = "data/data_assets.json"
_EXPLORATION = "data/exploration_status.json"
_PROVENANCE = "docs/research/data_provenance.json"
_ANNOUNCE = "data/announcement_collector.json"


def _data_coverage(root: Path, _now: datetime) -> list[Component]:
    out: list[Component] = []
    assets = _read_json(root / _ASSETS)
    raw = _field(assets, "counts")
    counts: dict[str, Any] = raw if isinstance(raw, dict) else {}
    out.append(fraction_component(
        "assets_with_measured_span", _ASSETS, _num(counts.get("measured")),
        _num(counts.get("assets")), unit="registered assets carrying a measured span",
        detail=f"{counts.get('measured')}/{counts.get('assets')} assets have a readable span "
               f"({counts.get('absent')} absent on disk); deep={_field(assets, 'deep')}"))

    expl = _read_json(root / _EXPLORATION)
    out.append(fraction_component(
        "exploration_organs_fresh", _EXPLORATION, _num(_field(expl, "n_fresh")),
        _num(_field(expl, "n_organs")), unit="unknown-unknown organs fresh",
        detail=f"status {_field(expl, 'status')}: {_field(expl, 'n_fresh')} fresh, "
               f"{_field(expl, 'n_stale')} stale, {_field(expl, 'n_dark')} dark"))

    # PROVENANCE IS PART OF THE DATA. A series whose collection method, survivorship and
    # manipulation risk are unrecorded cannot be reasoned about, only used.
    prov = _read_json(root / _PROVENANCE)
    out.append(ladder_component(
        "datasets_with_declared_provenance", _PROVENANCE,
        _len_or_none(_field(prov, "datasets")), COUNT_LADDER,
        unit="datasets carrying source/method/survivorship",
        detail=f"{_len_or_none(_field(prov, 'datasets'))} datasets declared in the provenance "
               "register -- collection method, manipulation risk and survivorship per series"))

    # A COLLECTOR WITH A DEAD SOURCE IS A DARK CORNER WEARING A GREEN LIGHT.
    ann = _read_json(root / _ANNOUNCE)
    out.append(inverse_ladder_component(
        "announcement_sources_failing", _ANNOUNCE, _len_or_none(_field(ann, "source_errors")),
        DEFECT_LADDER, unit="announcement sources erroring",
        detail=f"status {_field(ann, 'status')}: {_field(ann, 'detail')}; median latency "
               f"{_field(ann, 'median_latency_minutes')}min"))
    return out


_COVERAGE = "docs/research/COVERAGE_RATCHET.json"
_FORENSICS = "docs/research/trade_forensics_latest.json"


def _execution_path(root: Path, _now: datetime) -> list[Component]:
    doc = _read_json(root / _GATE0)
    out: list[Component] = [fraction_component(
        "gate0_readiness", _GATE0, _num(_field(doc, "n_ready")), _num(_field(doc, "n_criteria")),
        unit="S1-entry criteria ready",
        detail=f"desk owes {_field(doc, 'desk_owes')}, principal owes "
               f"{_field(doc, 'principal_owes')}")]

    cov = _read_json(root / _COVERAGE)
    raw = _field(cov, "measured")
    measured: dict[str, Any] = raw if isinstance(raw, dict) else {}
    out.append(fraction_component(
        "money_path_coverage", _COVERAGE, _num(measured.get("money_path_pct")), 100.0,
        unit="% money-path statement coverage",
        detail=f"{measured.get('money_path_pct')}% over "
               f"{measured.get('money_path_statements')} statements on the order path "
               f"(repo {measured.get('repo_pct')}%)"))

    out += mutation_components(root, "mutation_kill_execution_stack", ("libs/execution/",))

    # MAKER SHARE AGAINST THE DESK'S OWN TARGET, which is carried IN the forensics artifact --
    # 0.6 is trade forensics' number, not this module's, and lifting it keeps one target rather
    # than two. Fees are the dominant carry cost, so this is the live unit-economics lever.
    fore = _read_json(root / _FORENSICS)
    tape = _mapping(fore, "maker_fill") or {}
    out.append(fraction_component(
        "maker_fill_share", _FORENSICS, _num(tape.get("maker_share")), _num(tape.get("target")),
        unit="of the desk's own maker-share target",
        detail=f"maker share {tape.get('maker_share')} over {tape.get('n_legs')} legs "
               f"(spot {tape.get('spot')}, fut {tape.get('fut')}) against target "
               f"{tape.get('target')}; measured {_field(fore, 'updated')}"))

    # FEE ATTRIBUTION COMPLETENESS. An unattributed fee is money leaving the desk for a reason
    # nobody has named -- and the artifact states its own scope limit (futures only, a LOWER
    # BOUND), which is carried into the detail rather than dropped.
    fees = _mapping(fore, "fee_attribution") or {}
    out.append(fraction_component(
        "fees_attributed", _FORENSICS, _num(fees.get("attributed")),
        _num(fees.get("venue_commission")), unit="of billed commission attributed to a cause",
        detail=f"{fees.get('attributed')} of {fees.get('venue_commission')} attributed over "
               f"{fees.get('n_events')} events ({fees.get('unattributed')} unattributed); scope "
               f"{fees.get('scope')}"))
    return out


_LEDGER = "docs/research/recommendation_ledger.json"
_CONVERSION = "data/conversion_status.json"
_INSTRUMENTATION = "data/instrumentation_coverage.jsonl"
_CHASE = "data/instrumentation_chase.json"

#: Terminal ledger statuses, read from scripts/check_conversion.py so the two organs cannot drift
#: into disagreeing about what "converted" means on the same file.
TERMINAL_STATUSES = frozenset({"implemented", "rejected", "retired", "done", "screened"})


def _self_improvement(root: Path, _now: datetime) -> list[Component]:
    out: list[Component] = []
    doc = _read_json(root / _LEDGER)
    raw = _field(doc, "recommendations")
    rows = [r for r in raw if isinstance(r, dict)] if isinstance(raw, list) else None
    if rows is None:
        out.append(unmeasured_component("ledger_dispositioned", _LEDGER,
                                        f"{_LEDGER} absent or carries no recommendations array"))
    else:
        terminal = float(sum(1 for r in rows if r.get("status") in TERMINAL_STATUSES))
        open_rows = len(rows) - terminal
        out.append(fraction_component(
            "ledger_dispositioned", _LEDGER, terminal, float(len(rows)),
            unit="ledger rows reaching a terminal verdict",
            detail=f"{terminal:g} dispositioned of {len(rows)} raised ({open_rows:g} still open "
                   "or scheduled) -- a reasoned rejection counts, silence does not"))

    conv = _read_json(root / _CONVERSION)
    arrivals = _num(_field(conv, "arrivals_7d"))
    disposals = _num(_field(conv, "dispositions_7d"))
    if conv is not None and arrivals is not None and arrivals <= 0:
        # ZERO ARRIVALS IS NOT PERFECT CONVERSION. disposals/arrivals would be 0/0, and the
        # tempting reading -- "nothing arrived, so everything was converted" -- scores a desk that
        # stopped finding things as a desk that fixed everything.
        out.append(unmeasured_component(
            "conversion_flow_7d", _CONVERSION,
            "zero findings arrived in 7 days -- the conversion RATIO is undefined over an empty "
            "numerator and denominator, and an idle finder must never read as a perfect fixer"))
    else:
        out.append(fraction_component(
            "conversion_flow_7d", _CONVERSION,
            None if disposals is None or arrivals is None else min(disposals, arrivals),
            arrivals, unit="of the last 7 days' arrivals dispositioned",
            detail=f"status {_field(conv, 'status')}: {disposals} dispositioned vs {arrivals} "
                   f"raised in 7d; backlog {_field(conv, 'backlog')}, oldest "
                   f"{_field(conv, 'oldest_backlog_age_days')}d"))

    # THE DESK CANNOT IMPROVE WHAT IT CANNOT SEE ITSELF DOING. instrumentation_coverage is the
    # ledger of how much of the desk's own behaviour is instrumented at all; the chase counter
    # beside it never resets except by CLOSING a gap.
    rows = _read_jsonl(root / _INSTRUMENTATION)
    if not rows:
        out.append(unmeasured_component(
            "instrumentation_coverage", _INSTRUMENTATION,
            f"{_INSTRUMENTATION} absent or empty -- nothing records how much of the desk's own "
            "behaviour is instrumented, and an uninstrumented desk cannot tell improvement from "
            "drift"))
    else:
        last = rows[-1]
        out.append(fraction_component(
            "instrumentation_coverage", _INSTRUMENTATION, _num(last.get("coverage_pct")), 100.0,
            unit="% of declared instrumentation points wired",
            detail=f"{last.get('instrumented')} instrumented, {last.get('owed')} owed at "
                   f"{last.get('ts')} over {len(rows)} recorded sweeps"))

    chase = _read_json(root / _CHASE)
    out.append(inverse_ladder_component(
        "instrumentation_gaps_owed", _CHASE, _len_or_none(_field(chase, "cycles_owed")),
        DEFECT_LADDER, unit="instrumentation gaps standing open across cycles",
        detail=f"{_len_or_none(_field(chase, 'cycles_owed'))} gap(s) carrying a cycle counter at "
               f"{_field(chase, 'updated')} -- the counter never resets except by closing the gap"))
    return out


_READINESS = "data/organ_readiness.json"
_ORGAN_ER = "data/organ_er.json"
_KERNEL_LOG = "data/kernel_log_status.json"


def _ops_autonomy(root: Path, _now: datetime) -> list[Component]:
    live = _read_json(root / _LIVENESS)
    dark = _field(live, "never_produced")
    stale = _field(live, "stale")
    out: list[Component] = [fraction_component(
        "organs_producing", _LIVENESS, _num(_field(live, "n_fresh")),
        _num(_field(live, "n_checked")), unit="scheduled organs producing fresh output",
        detail=f"status {_field(live, 'status')}: "
               f"{len(dark) if isinstance(dark, list) else '?'} never produced, "
               f"{len(stale) if isinstance(stale, list) else '?'} stale")]

    ready = _read_json(root / _READINESS)
    n_ready = _num(_field(ready, "ready"))
    n_not = _num(_field(ready, "not_ready"))
    total = None if n_ready is None or n_not is None else n_ready + n_not
    out.append(fraction_component(
        "organs_ready", _READINESS, n_ready, total, unit="organs assembling a lawful prompt",
        detail=f"{n_ready}/{total} organs ready at {_field(ready, 'ts')} "
               f"(gate_ok={_field(ready, 'gate_ok')})"))

    # THE ER IS THE ESCALATION LAYER: an organ that stopped is SICK, one that stopped for >24h is
    # in COMA, and an UNTREATED coma is the state where autonomy has actually failed.
    er = _read_json(root / _ORGAN_ER)
    out.append(fraction_component(
        "organs_healthy", _ORGAN_ER, _num(_field(er, "n_healthy")), _num(_field(er, "n_organs")),
        unit="organs healthy under the ER's own triage",
        detail=f"status {_field(er, 'status')}: {_field(er, 'detail')}; untreated comas "
               f"{_field(er, 'untreated_comas')}"))
    out.append(inverse_ladder_component(
        "organ_comas_untreated", _ORGAN_ER, _len_or_none(_field(er, "untreated_comas")),
        DEFECT_LADDER, unit="comatose organs with no treatment applied",
        detail=f"{_len_or_none(_field(er, 'untreated_comas'))} untreated coma(s) after "
               f"{_field(er, 'coma_hours')}h; treatments {_field(er, 'treatments')}"))

    # CAN THE BOX SEE ITS OWN KILLS? A 'no OOM' conclusion is only a measurement if a kernel event
    # was provably readable first (R0350/L1.40) -- the fraction of channels that read is that
    # proof, and check_kernel_log owns the probe.
    kern = _read_json(root / _KERNEL_LOG)
    out.append(fraction_component(
        "kernel_log_channels_readable", _KERNEL_LOG,
        _len_or_none(_field(kern, "readable_channels")), _len_or_none(_field(kern, "channels")),
        unit="kernel-log channels provably readable",
        detail=f"verdict {_field(kern, 'verdict')}: {_field(kern, 'detail')}"))
    return out


_QUEUE = "data/promotion_queue.json"
_PROMOTION = "data/promotion_gate.json"


def _alpha_output(root: Path, _now: datetime) -> list[Component]:
    out: list[Component] = []
    queue = _read_json(root / _QUEUE)
    raw = _field(queue, "slots")
    slots: dict[str, Any] = raw if isinstance(raw, dict) else {}
    out.append(fraction_component(
        "forward_slots_occupied", _QUEUE, _num(slots.get("occupied")), _num(slots.get("cap")),
        unit="forward slots carrying a live clock",
        detail=f"{slots.get('occupied')}/{slots.get('cap')} slots running; "
               f"{_field(queue, 'n_candidates')} screened survivors queued"))

    gate = _read_json(root / _PROMOTION)
    ladder = _field(gate, "ladder")
    rungs = ([_num(r.get("rung")) for r in ladder if isinstance(r, dict)]
             if isinstance(ladder, list) else [])
    top = max((r for r in rungs if r is not None), default=None)
    out.append(fraction_component(
        "promotion_rung", _PROMOTION, _num(_field(gate, "granted_rung")), top,
        unit="promotion rungs granted",
        detail=f"granted '{_field(gate, 'granted')}' at rung {_field(gate, 'granted_rung')}, "
               f"blocked at {_field(gate, 'blocked_at_rung')} over "
               f"{_field(gate, 'n_closed')} closed trades"))
    return out


# --------------------------------------------------------------------------------------------
# THE MINOR ASPECTS. The standing order is "every aspect", not "the nine headline ones", and the
# surface below is where a desk actually rots: the pager that died between incidents, the cost
# model nobody refreshed, the seat with no credential, the backup nobody restored. None of these
# is glamorous and every one of them has taken a desk down.
# --------------------------------------------------------------------------------------------

_ALERT_LEDGER = "data/alert_delivery.jsonl"
_ALERT_SILENT = "data/ALERT_CHANNELS_SILENT"
_ALERT_CANARY = "data/alert_canary_state.json"

#: How old the canary's last run may be before its verdict stops counting. NOT a number this
#: module invented: it is the canary's OWN throttle -- `--interval-h` defaults to 6.0 in
#: scripts/run_alert_canary.py:49, which is that organ's statement of how often it intends to run
#: (its cron line is tighter still, so 6h is several missed ticks and comfortably past "the box
#: was busy"). Lifting it rather than picking one keeps the desk from holding two different
#: opinions about when the canary is late.
CANARY_MAX_AGE_H = 6.0
_CANARY_OWNER = "scripts/run_alert_canary.py --interval-h default"


def _alerting(root: Path, now: datetime) -> list[Component]:
    """Does the pager provably deliver BETWEEN incidents?

    The failure this scores is on the record twice: quota exhaustion left the pager dead five
    days, and a latin-1 header encode killed 39/39 pushes for 29h across a live dead-man fire.
    Alerts only fire on incidents, so a broken alert path looks exactly like a quiet desk -- which
    is why the DELIVERY LEDGER, not the alerting code, is the artifact that settles it.
    """
    out: list[Component] = []
    rows = _read_jsonl(root / _ALERT_LEDGER)
    if rows is None:
        out.append(unmeasured_component(
            "pager_deliveries_ok", _ALERT_LEDGER,
            f"{_ALERT_LEDGER} absent -- there is no delivery ledger, so 'the pager works' is an "
            "assumption. libs/ops/alert_channels writes one row per attempt per channel; that "
            "file is what would settle it"))
    else:
        delivered = float(sum(1 for r in rows if r.get("ok") is True))
        last = rows[-1] if rows else {}
        out.append(fraction_component(
            "pager_deliveries_ok", _ALERT_LEDGER, delivered, float(len(rows)),
            unit="logged page attempts that DELIVERED",
            detail=f"{delivered:g}/{len(rows)} ledger attempts delivered; last row channel "
                   f"{last.get('channel')} ok={last.get('ok')} -- {str(last.get('detail'))[:90]}"))

    # THE SILENCE FLAG IS THE CANARY'S OWN VERDICT, written using ITS lookback window, not one
    # invented here. But that verdict is only worth anything while the canary is ALIVE, and the
    # two directions are not symmetric:
    #
    #   FLAG PRESENT is a positive assertion of silence that only a successful delivery clears. It
    #       is scored 0 whatever the canary's age -- the last thing anyone established was that the
    #       pager was dead, and nothing since has said otherwise. Downgrading that to UNMEASURED
    #       because the canary later died would be the flattering reading of a monitor dying while
    #       reporting a fault, which is the worst moment to stop counting it.
    #   FLAG ABSENT proves nothing on its own -- an unrun canary, a dead canary and a healthy pager
    #       all leave the same empty directory. So absence is only a 10 while the canary is FRESH,
    #       and otherwise UNMEASURED.
    #
    # WITHOUT THE AGE CHECK this component read 10/10 AT CEILING forever off ONE observation
    # receding into the past: run the canary once, clear the flag, let the canary die, and a dead
    # pager scores identically to a live one while looking more confident every day. That is the
    # same shape as the five-day dead pager this whole aspect exists to catch. A monitor that
    # cannot report its own death is not a monitor.
    flag = root / _ALERT_SILENT
    note = ""
    if flag.exists():
        try:
            note = flag.read_text("utf-8").strip()
        except (OSError, UnicodeDecodeError):
            note = "(flag present, unreadable)"
    canary = _read_json(root / _ALERT_CANARY)
    age = age_hours(canary, "last_canary", now)
    stale = stale_gate("alert_channels_not_silent", _ALERT_CANARY, canary, "last_canary", now,
                       max_age_h=CANARY_MAX_AGE_H, owner=_CANARY_OWNER,
                       what="the canary's own liveness, which is what makes the silence flag's "
                            "ABSENCE mean anything")
    if flag.exists():
        out.append(Component(
            key="alert_channels_not_silent", state=MEASURED, score=0.0, artifact=_ALERT_SILENT,
            detail=f"SILENCE FLAG PRESENT: {note[:150]} (canary last ran "
                   f"{age if age is not None else '?'}h ago)",
            constraint="ARM A CHANNEL and deliver one page: the canary's own audit found no "
                       "delivery on ANY channel inside its lookback, which is the state that hid "
                       "a dead pager for five days. The flag clears itself on the next successful "
                       "delivery -- nothing else clears it"))
    elif stale is not None:
        out.append(stale)
    else:
        out.append(binary_component(
            "alert_channels_not_silent", _ALERT_SILENT, True,
            detail=f"no silence flag, and the canary ran {age}h ago (bound {CANARY_MAX_AGE_H:g}h) "
                   "-- a live canary that is not complaining",
            fix="",
            held="AT CEILING -- a page has landed inside the canary's own lookback AND the canary "
                 "is itself alive; HOLDING it means keeping the canary on its cadence, because a "
                 "silent canary and a working pager look identical from here"))
    return out


_COST_HUNT = "data/cost_hunt.json"
_ECONOMICS = "data/execution_economics.json"

#: execution_economics' own sentinel for an input it could not read on this box. Read, not
#: restated: it is that organ's vocabulary for "absent", and it deliberately never writes 0.0.
_NOT_READABLE = "NOT-READABLE-HERE"


def _cost_model(root: Path, _now: datetime) -> list[Component]:
    """Is the cost model FRESH, and is the realised-versus-modelled residual measurable at all?

    Cost is the only input that decides whether an edge survives contact with a venue, and it is
    the input most prone to silent staleness: a model fitted once and never refreshed reports the
    same confident number forever while the venue's fees, funding and depth all move.
    """
    hunt = _read_json(root / _COST_HUNT)
    out = [fraction_component(
        "funding_rates_measured", _COST_HUNT, _num(_field(hunt, "n_measured")),
        _num(_field(hunt, "n_symbols")), unit="universe symbols with a measured funding rate",
        detail=f"status {_field(hunt, 'status')}: {_field(hunt, 'detail')}")]
    out.append(liveness_component(root, "cost_hunt_freshness", "scripts/run_cost_hunt.py"))
    out.append(liveness_component(root, "cost_surface_identified",
                                  "scripts/run_cost_identification.py"))

    # INPUT READABILITY, NOT THE RESIDUAL. A residual computed over inputs that were mostly
    # unreadable is a partial measurement, and scoring it as a whole one is precisely the failure
    # the truncated-mutation rule forbids. What IS complete and scoreable is how many of the
    # model's declared inputs this box can read at all.
    econ = _read_json(root / _ECONOMICS)
    inputs = _mapping(econ, "inputs")
    if inputs is None or not inputs:
        out.append(unmeasured_component(
            "cost_inputs_readable", _ECONOMICS,
            f"{_ECONOMICS} carries no inputs map -- the cost model's own account of what it could "
            "read is what makes its residual believable, and without it the residual is a number "
            "with no denominator"))
    else:
        readable = float(sum(1 for v in inputs.values() if str(v) != _NOT_READABLE))
        out.append(fraction_component(
            "cost_inputs_readable", _ECONOMICS, readable, float(len(inputs)),
            unit="declared cost-model inputs readable from this box",
            detail=f"status {_field(econ, 'status')}: {readable:g}/{len(inputs)} inputs readable "
                   f"({', '.join(k for k, v in inputs.items() if str(v) == _NOT_READABLE)} are "
                   f"{_NOT_READABLE}); thresholds read from "
                   f"{(_mapping(econ, 'thresholds_read_not_declared') or {}).get('sources')}"))
    return out


_REPLACEMENT = "data/replacement_rate.json"


def _forward_clock(root: Path, _now: datetime) -> list[Component]:
    """Do the desk's forward clocks MEAN anything -- measured latency, countable births?

    A forward clock is the desk's only honest evidence generator, and its hygiene is separate from
    how many slots are full (that is alpha_output). What is scored here is whether the clock's own
    numbers are measurements: a promotion latency assembled from DESIGN and ESTIMATED terms is a
    plan, not an observation, and a birth rate nobody can count cannot be compared to a death rate.
    """
    out: list[Component] = []
    latency = _mapping(_read_json(root / _QUEUE), "latency") or {}
    terms = _mapping(latency, "components")
    if terms is None or not terms:
        out.append(unmeasured_component(
            "promotion_latency_measured", _QUEUE,
            f"{_QUEUE} carries no latency component breakdown -- a single total with no "
            "provenance per term cannot be told apart from a guess"))
    else:
        measured = float(sum(1 for v in terms.values()
                             if isinstance(v, dict) and v.get("provenance") == "MEASURED"))
        provenance = ", ".join(f"{k}={v.get('provenance')}"
                               for k, v in sorted(terms.items()) if isinstance(v, dict))
        out.append(fraction_component(
            "promotion_latency_measured", _QUEUE, measured, float(len(terms)),
            unit="latency terms MEASURED rather than designed or estimated",
            detail=f"total {latency.get('total_days')}d, fully_measured="
                   f"{latency.get('fully_measured')}; {provenance}"))

    rep = _read_json(root / _REPLACEMENT)
    births_flag = rep.get("births_measured") if rep is not None else None
    out.append(binary_component(
        "births_countable", _REPLACEMENT, births_flag if isinstance(births_flag, bool) else None,
        detail=f"status {_field(rep, 'status')}: {_field(rep, 'detail')}",
        fix="RECORD A DATED PROMOTION HISTORY -- births are UNCOUNTABLE, so the desk cannot say "
            "whether validated births keep pace with deaths (L1.30). Never loosen a validation "
            "bar to manufacture one: that turns a real countdown into a fake reprieve",
        held="AT CEILING -- births are counted from a dated promotion history; HOLDING it means "
             "keeping that history append-only"))

    rate = _num(_field(rep, "replacement_rate"))
    if rate is None:
        out.append(unmeasured_component(
            "replacement_rate", _REPLACEMENT,
            f"{_REPLACEMENT} publishes a null replacement rate ({_field(rep, 'status')}) -- with "
            "births uncountable the ratio is undefined, and an undefined ratio is not a 1.0"))
    else:
        out.append(fraction_component(
            "replacement_rate", _REPLACEMENT, rate, 1.0,
            unit="of one-for-one replacement over the window",
            detail=f"{_field(rep, 'births')} births vs {_field(rep, 'deaths')} deaths in "
                   f"{_field(rep, 'window_days')}d; {_field(rep, 'live_forward_clocks')} live "
                   "forward clocks"))
    return out


_CLOCK_PROVENANCE = "data/clock_provenance_status.json"
_BACKUP = "data/backup_status.json"

#: check_clock_provenance's two REFUSAL verdicts. They are not defects of the tape -- they are the
#: fence saying it had nothing to look at, and the one thing that fence may never do is report OK
#: because it found nothing. Scoring them as zero would invent a defect out of an absent corpus.
_CLOCK_REFUSALS = ("NO-DATA", "UNMEASURED")


def _recorder_tape(root: Path, _now: datetime) -> list[Component]:
    """Is the desk's OWN tape being recorded, and does its time axis mean what the schema implies?

    Three of the largest kills in the graveyard (kimchi_premium, coinbase_premium_timing, the
    leaky Upbit copies) are ONE defect class: a timestamp whose clock was never declared. Delta =
    t_recv - t_venue is structurally unbuyable and cannot be backfilled, so a day not recorded is
    a day gone permanently -- which is why tape health is scored beside the fancier aspects.
    """
    out: list[Component] = []
    doc = _read_json(root / _CLOCK_PROVENANCE)
    status = str(_field(doc, "status"))
    if doc is None:
        out.append(unmeasured_component(
            "tape_clock_declared", _CLOCK_PROVENANCE,
            f"{_CLOCK_PROVENANCE} absent -- scripts/check_clock_provenance.py has never produced "
            "it, so nothing has asked whether the tape's timestamps mean what its schema implies"))
    elif status in _CLOCK_REFUSALS:
        out.append(unmeasured_component(
            "tape_clock_declared", _CLOCK_PROVENANCE,
            f"the clock fence returned {status} -- {_field(doc, 'detail')}. That is the fence "
            "refusing to grade an absent or unclassifiable corpus, and a refusal is not a defect "
            "of the tape any more than it is a clean bill"))
    else:
        streams = _mapping(doc, "streams") or {}
        bad = ((_len_or_none(_field(doc, "mixed_clock_streams")) or 0.0)
               + (_len_or_none(_field(doc, "unknown_streams")) or 0.0))
        out.append(fraction_component(
            "tape_clock_declared", _CLOCK_PROVENANCE, float(len(streams)) - bad,
            float(len(streams)), unit="tape streams declaring the clock that stamped them",
            detail=f"status {status}: {_field(doc, 'detail')}; {_field(doc, 'rows_sampled')} rows "
                   f"sampled over {_field(doc, 'files_read')} files"))

    # THE TAPE STORE ITSELF, per the backup organ that inventories the desk's durable stores.
    stores = _mapping(_read_json(root / _BACKUP), "stores")
    tape = (stores or {}).get("execution_tape")
    tape_status = str((tape or {}).get("status") or "") if isinstance(tape, dict) else ""
    if not isinstance(tape, dict):
        out.append(unmeasured_component(
            "execution_tape_store", _BACKUP,
            f"{_BACKUP} carries no execution_tape store row -- the tape is the desk's proprietary "
            "moat and nothing is inventorying whether it exists"))
    else:
        out.append(binary_component(
            "execution_tape_store", _BACKUP, tape_status == "REPLICATED",
            detail=f"execution_tape is {tape_status} at {tape.get('path')}: "
                   f"{tape.get('note') or 'replicated'}",
            fix=f"RUN THE RECORDER -- the execution tape reads {tape_status} at "
                f"{tape.get('path')}. Delta between venue and receipt clocks cannot be "
                "backfilled, so every day it is absent is a day gone permanently",
            held="AT CEILING -- the tape exists and is replicated; HOLDING it is the recorder "
                 "staying up"))

    # THE RECORDING WINDOW ITSELF: forensics reports whether the retained buffer is squeezing the
    # analysis window, which is the early warning before a tape gap becomes a measurement gap.
    tape_stats = _mapping(_read_json(root / _FORENSICS), "execution_tape")
    squeeze = (tape_stats or {}).get("buffer_squeezing_window")
    out.append(binary_component(
        "tape_buffer_not_squeezing", _FORENSICS,
        (not squeeze) if isinstance(squeeze, bool) else None,
        detail=(f"{(tape_stats or {}).get('taped')} taped rows over "
                f"{(tape_stats or {}).get('tape_days')}d; buffer "
                f"{(tape_stats or {}).get('buffer_days')}d, window margin "
                f"{(tape_stats or {}).get('window_margin_days')}d"
                if tape_stats else
                f"{_FORENSICS} carries no execution_tape block -- retention pressure on the "
                "analysis window is not being watched"),
        fix="EXTEND RETENTION -- the retained buffer is squeezing the analysis window, so the "
            "next forensics pass will silently narrow rather than fail",
        held="AT CEILING -- the retained buffer clears the analysis window with margin"))
    return out


_RUNWAY = "data/miner_runway.json"

#: The seat verdict check_ratchets._miner_productive counts as productive. Lifted from there so
#: the ratchet floor and this score cannot disagree about what a working seat is.
_SEAT_OK = "ok"


def _llm_seats(root: Path, _now: datetime) -> list[Component]:
    """Are the desk's LLM seats WIRED, CREDENTIALLED and PRODUCING -- three different facts.

    The three are kept apart deliberately, because collapsing them is how a desk convinces itself
    it has a research bench: prompts and runners can all exist while every seat is unfunded, and
    an unreadable log directory means the productivity question cannot be answered AT ALL from
    this box. miner_runway states its own observability, and that state is honoured here.
    """
    doc = _read_json(root / _RUNWAY)
    seats = _mapping(doc, "seats")
    if seats is None or not seats:
        why = f"{_RUNWAY} carries no seat roster -- nothing enumerates the desk's LLM bench"
        return [unmeasured_component(k, _RUNWAY, why)
                for k in ("seats_wired", "seats_credentialled", "seats_productive")]

    rows = [s for s in seats.values() if isinstance(s, dict)]
    total = float(len(rows))
    wired = float(sum(1 for s in rows if s.get("prompt") and s.get("runner") and s.get("unit")))
    creds = float(sum(1 for s in rows if s.get("creds") is True))
    out = [fraction_component(
        "seats_wired", _RUNWAY, wired, total,
        unit="seats with prompt + runner + unit all present",
        detail=f"{wired:g}/{total:g} seats wired at {_field(doc, 'checked')}"),
        fraction_component(
        "seats_credentialled", _RUNWAY, creds, total, unit="seats carrying a credential",
        detail=f"{creds:g}/{total:g} seats credentialled (creds_present="
               f"{_field(doc, 'creds_present')}); a wired seat with no key is a bench that "
               "cannot sit down")]

    # OBSERVABILITY IS THE PRECONDITION, and this organ publishes it. `observable: false` means
    # the log directory could not be read, so seat productivity is UNKNOWN -- and 0 productive
    # seats out of 11 would be a fabricated defect rather than a measurement.
    if doc is not None and doc.get("observable") is not True:
        blockers = _rows(doc, "blockers") or []
        out.append(unmeasured_component(
            "seats_productive", _RUNWAY,
            f"{_RUNWAY} reports observable={_field(doc, 'observable')} -- "
            f"{(blockers[0].get('blocker') if blockers else 'run history unreadable here')}. The "
            "report says NOTHING about whether the seats ran, and an unreadable log is not an "
            "idle seat"))
    else:
        productive = float(sum(1 for s in rows if s.get("status") == _SEAT_OK))
        out.append(fraction_component(
            "seats_productive", _RUNWAY, productive, total,
            unit="seats producing inside their own max_age_h",
            detail=f"{productive:g}/{total:g} seats ok at {_field(doc, 'checked')}; by_status "
                   f"{_field(doc, 'by_status')}"))
    return out


_UTILISATION = "data/utilisation.json"


def _dependency_env(root: Path, _now: datetime) -> list[Component]:
    """Does the environment the suite runs in match the environment that runs the money?

    A green suite here is not evidence about production unless the deps match: `ruff>=0.5`
    resolving to 0.15.8 produced 36 errors production never saw, and a mypy minor-version gap
    made the same file clean on one box and red on another. max_audit owns the drift check and
    check_utilisation owns the importability ceiling; both are read, neither is re-derived.
    """
    out = [inverse_ladder_component(
        "dependency_drift_defects", _AUDIT, _audit_defects(root, "dependency-"), DEFECT_LADDER,
        unit="live dependency/pin defects raised by the audit",
        detail="max_audit's dependency checks: major-version drift vs the deployed pin set, "
               "pinned packages absent here, and pyproject floors sitting BELOW production")]

    ceiling = _ceiling_row(root, "optional_test_deps")
    if ceiling is None:
        out.append(unmeasured_component(
            "optional_test_deps_importable", _UTILISATION,
            f"{_UTILISATION} carries no optional_test_deps ceiling -- nothing measures whether "
            "declared optional dependencies import, and a test that skips on a missing dep prints "
            "one grey line and exits 0"))
    else:
        out.append(fraction_component(
            "optional_test_deps_importable", _UTILISATION, _num(ceiling.get("used")),
            _num(ceiling.get("limit")), unit="declared optional test deps importable here",
            detail=f"{ceiling.get('used')}/{ceiling.get('limit')} importable "
                   f"({ceiling.get('status')}): {ceiling.get('binding_constraint')}"))
    return out


def _ceiling_row(root: Path, name: str) -> dict[str, Any] | None:
    for row in _rows(_read_json(root / _UTILISATION), "ceilings") or []:
        if row.get("name") == name:
            return row
    return None


def _capital_utilisation(root: Path, _now: datetime) -> list[Component]:
    """Is paid-for capacity actually being USED -- capital, slots, wired capability?

    Unused headroom is not safety, it is an unbooked loss (L1.28a). The aggregate is deliberately
    computed over the MEASURED ceilings only and the unmeasured ones are listed by name: the
    utilisation organ's own convention scores an unmeasured ceiling as zero, which is right for a
    fence that must not reward ignorance but wrong for a capability score that must not invent a
    defect out of one. Both readings are published rather than merged.
    """
    doc = _read_json(root / _UTILISATION)
    rows = _rows(doc, "ceilings")
    if rows is None or not rows:
        return [unmeasured_component(
            "ceiling_utilisation", _UTILISATION,
            f"{_UTILISATION} carries no ceilings -- nothing enumerates the desk's paid-for "
            "capacity, so idle capacity cannot be told from absent capacity")]

    measured = [r for r in rows if r.get("measured") is True]
    out: list[Component] = [fraction_component(
        "ceilings_measured", _UTILISATION, float(len(measured)), float(len(rows)),
        unit="declared ceilings actually measurable here",
        detail=f"{len(measured)}/{len(rows)} ceilings measured; UNMEASURED "
               f"{_field(doc, 'unmeasured')}")]
    for row in rows:
        if row.get("measured") is not True:
            out.append(unmeasured_component(
                f"ceiling::{row.get('name')}", _UTILISATION,
                f"ceiling {row.get('name')} reports measured=false "
                f"({row.get('binding_constraint') or 'no reason given'}) -- it is excluded from "
                "the aggregate rather than folded in as a zero"))
    utilisations = [u for u in (_num(r.get("utilisation")) for r in measured) if u is not None]
    if not utilisations:
        out.append(unmeasured_component(
            "ceiling_utilisation", _UTILISATION,
            "no measured ceiling carries a utilisation figure -- the aggregate would be a mean "
            "over nothing"))
        return out
    mean = sum(utilisations) / len(utilisations)
    expect = _num(_field(doc, "expect_fraction"))
    out.append(fraction_component(
        "ceiling_utilisation", _UTILISATION, round(mean, 4), expect,
        unit="of the desk's own expected utilisation fraction",
        detail=f"mean {mean:.3f} over {len(utilisations)} MEASURED ceilings against an expected "
               f"{expect}; the organ's own headline (which counts unmeasured as zero) is "
               f"{_field(doc, 'mean_utilisation')}; idle_unexplained "
               f"{_field(doc, 'idle_unexplained')}"))
    return out


_KNOWLEDGE = "data/knowledge_engine.json"
_PLAYBOOK = "data/trading_playbook.json"
_LESSONS = "docs/desk_lessons.jsonl"


def _knowledge_currency(root: Path, _now: datetime) -> list[Component]:
    """Is what the desk has LEARNED retrievable, or does every cycle start from nothing?

    The expensive failure here is re-testing a dead hypothesis: compute spent to rediscover a
    result already in the graveyard. The knowledge engine is the retrieval layer that answers
    "has this effectively already been tested?" BEFORE the compute is spent, and the lesson
    ledgers are the desk's record of what an incident actually taught it.
    """
    doc = _read_json(root / _KNOWLEDGE)
    if doc is None:
        out = [unmeasured_component(
            "knowledge_corpus", _KNOWLEDGE,
            f"{_KNOWLEDGE} absent -- scripts/knowledge_engine.py has not produced it, so the "
            "'has this already been tested?' query has no index to run against and the graveyard "
            "is a document rather than a memory")]
    else:
        out = [ladder_component(
            "knowledge_corpus", _KNOWLEDGE, _num(doc.get("corpus_size")), COUNT_LADDER,
            unit="retrievable documents in the research memory",
            detail=f"corpus {doc.get('corpus_size')} at {doc.get('updated')}; "
                   f"{_len_or_none(doc.get('causal_edges'))} causal edges, blind-validation "
                   f"consistent={doc.get('blind_validation_consistent')}")]

    play = _read_json(root / _PLAYBOOK)
    out.append(ladder_component(
        "playbook_lessons", _PLAYBOOK, _len_or_none(_field(play, "lessons")), COUNT_LADDER,
        unit="playbook lessons distilled from closed trades",
        detail=f"{_len_or_none(_field(play, 'lessons'))} lesson(s) over "
               f"{_field(play, 'reviewed_keys')} reviewed keys, updated "
               f"{_field(play, 'updated')}"))

    lessons = _read_jsonl(root / _LESSONS)
    if lessons is None:
        out.append(unmeasured_component(
            "desk_lessons_recorded", _LESSONS,
            f"{_LESSONS} absent -- the desk's incident ledger is where a defect becomes a lesson "
            "instead of a recurrence; with no ledger, recurrence cannot even be counted"))
    else:
        out.append(ladder_component(
            "desk_lessons_recorded", _LESSONS, float(len(lessons)), COUNT_LADDER,
            unit="recorded desk lessons, each with its cost and recurrence count",
            detail=f"{len(lessons)} lesson(s); most recent "
                   f"{lessons[-1].get('id') if lessons else '?'} learned "
                   f"{lessons[-1].get('learned') if lessons else '?'}"))
    return out


_DRILLS = "data/drill_report.json"
_SIZING = "data/sizing_derivation.json"


def _backup_dr(root: Path, _now: datetime) -> list[Component]:
    """Could the desk be REBUILT -- and has anyone proved it by actually restoring?

    A backup nobody has restored from is a hypothesis, so the restore drill is scored separately
    from the replication count. The disk fuse is read from the artifact rather than restated here:
    run_moat_backup owns the percentage at which it refuses to keep writing.
    """
    doc = _read_json(root / _BACKUP)
    stores = _mapping(doc, "stores")
    if stores is None or not stores:
        out = [unmeasured_component(
            "stores_replicated", _BACKUP,
            f"{_BACKUP} carries no store inventory -- nothing enumerates what would have to "
            "survive a host loss, so 'we have backups' is untested in both directions")]
    else:
        rows = [s for s in stores.values() if isinstance(s, dict)]
        replicated = float(sum(1 for s in rows if s.get("status") == "REPLICATED"))
        absent = [k for k, s in stores.items()
                  if isinstance(s, dict) and s.get("status") != "REPLICATED"]
        out = [fraction_component(
            "stores_replicated", _BACKUP, replicated, float(len(rows)),
            unit="durable stores replicated off the host",
            detail=f"{replicated:g}/{len(rows)} stores replicated at {_field(doc, 'generated')}; "
                   f"NOT replicated: {', '.join(absent) or 'none'}")]

    drill = doc.get("restore_drill_passed") if doc is not None else None
    out.append(binary_component(
        "restore_drill_passed", _BACKUP, drill if isinstance(drill, bool) else None,
        detail=f"restore_drill_passed={drill}; status {_field(doc, 'status')}",
        fix="RESTORE FROM THE BACKUP AND PROVE IT -- an unrestored backup is a hypothesis, and "
            "the first restore attempt is not the moment to discover the archive is unreadable",
        held="AT CEILING -- a restore has actually been exercised; HOLDING it means re-running "
             "the drill, not trusting the last one"))

    free = _num(_field(doc, "disk_free_pct"))
    fuse = _num(_field(doc, "fuse_pct"))
    out.append(fraction_component(
        "disk_headroom_over_fuse", _BACKUP, free, fuse,
        unit="of the backup organ's own disk fuse",
        detail=f"disk free {free}% against a {fuse}% fuse (status {_field(doc, 'status')}); "
               f"uncovered {_field(doc, 'not_covered_note')}"))
    out.append(liveness_component(root, "backup_cadence", "scripts/run_moat_backup.py"))
    return out


def _mutation_breadth(root: Path, _now: datetime) -> list[Component]:
    """How much of the tree is mutation-tested AT ALL -- a different question from the kill rate.

    A desk can hold a 100% kill rate forever by mutation-testing one small file. Breadth is the
    denominator that stops that: how many money-path files carry a COMPLETE run, and how many
    targets exist. Truncated targets are excluded from the numerator exactly as they are from the
    kill rate -- a budget-truncated run has not covered the file, so counting it as covered would
    let the desk buy breadth by running less, which is the same trick one level up.
    """
    doc = _read_json(root / _MUTATION)
    if doc is None:
        why = f"{_MUTATION} absent -- nothing records which of the tree has been mutation-tested"
        return [unmeasured_component(k, _MUTATION, why)
                for k in ("money_path_files_mutated", "mutation_targets_complete",
                          "mutation_targets_at_bar")]

    targets = _rows(doc, "targets") or []
    complete = [t for t in targets
                if t.get("budget_truncated") is not True and isinstance(t.get("target"), str)]
    truncated = [str(t.get("target")) for t in targets if t.get("budget_truncated") is True]
    names = {str(t["target"]) for t in complete}

    # THE DENOMINATOR IS THE MONEY PATH THE COVERAGE RATCHET ALREADY DECLARES. Inventing a file
    # list here would let the breadth score be raised by editing this module.
    cov = _read_json(root / _COVERAGE)
    money = _field(cov, "money_path_files")
    money_files = [str(f) for f in money] if isinstance(money, list) else None
    if money_files is None:
        out = [unmeasured_component(
            "money_path_files_mutated", _COVERAGE,
            f"{_COVERAGE} declares no money_path_files list -- without the desk's own definition "
            "of the money path there is no honest denominator for breadth, and one invented here "
            "could be edited to raise the score")]
    else:
        hit = float(sum(1 for f in money_files if f in names))
        missing = [f for f in money_files if f not in names]
        out = [fraction_component(
            "money_path_files_mutated", _MUTATION, hit, float(len(money_files)),
            unit="money-path files carrying a COMPLETE mutation run",
            detail=f"{hit:g}/{len(money_files)} money-path files mutated; NOT mutated: "
                   f"{', '.join(missing) or 'none'}")]

    out.append(ladder_component(
        "mutation_targets_complete", _MUTATION, float(len(complete)), COUNT_LADDER,
        unit="modules with a complete (never truncated) mutation run",
        detail=f"{len(complete)} complete target(s) measured {_field(doc, 'measured')}; "
               f"{len(truncated)} truncated and excluded: {', '.join(truncated) or 'none'}"))
    for name in truncated:
        out.append(unmeasured_component(
            f"mutation_targets_complete::{Path(name).name}", _MUTATION,
            f"{name} ran BUDGET-TRUNCATED -- a truncated run has not covered the file, so it "
            "counts toward neither breadth nor strength"))

    # AT-BAR SHARE, with the bar READ from the artifact (check_ratchets holds the same rule) --
    # a scorer that owns its own bar is a scorer that can lower it.
    bar = _num(doc.get("bar"))
    rates: list[float] = []
    for t in complete:
        rate = _num(t.get("adjusted_kill_rate"))
        rate = rate if rate is not None else _num(t.get("kill_rate"))
        if rate is not None:
            rates.append(rate)
    if bar is None or not rates:
        out.append(unmeasured_component(
            "mutation_targets_at_bar", _MUTATION,
            f"{_MUTATION} carries no bar or no complete target with a kill rate -- the at-bar "
            "share is undefined and must not read as full marks"))
    else:
        at_bar = float(sum(1 for r in rates if r >= bar))
        out.append(fraction_component(
            "mutation_targets_at_bar", _MUTATION, at_bar, float(len(rates)),
            unit=f"complete targets meeting the artifact's own {bar:g} bar",
            detail=f"{at_bar:g}/{len(rates)} complete targets at bar {bar:g}"))
    return out


_SCHEDULER = "data/scheduler_manifest_report.json"


def _scheduler_integrity(root: Path, _now: datetime) -> list[Component]:
    """Does the scheduler MANIFEST describe the machine, and does the machine agree?

    A watchdog died and left the pager silent and the forward clocks frozen for 11.5 days while
    every timer looked healthy. The manifest checks are what make that detectable, and the
    live-crontab comparison is the half that actually proves the box matches the file -- which is
    why its unreadability is reported as UNMEASURED rather than folded into the passing checks.
    """
    doc = _read_json(root / _SCHEDULER)
    checks = _mapping(doc, "checks")
    if checks is None or not checks:
        return [unmeasured_component(
            "manifest_checks_passing", _SCHEDULER,
            f"{_SCHEDULER} absent or carries no checks -- nothing verifies that every scheduled "
            "line points at a script that exists, parses, and locks coherently")]

    verdicts = {k: v for k, v in checks.items() if isinstance(v, dict) and "ok" in v}
    passing = float(sum(1 for v in verdicts.values() if v.get("ok") is True))
    failing = [k for k, v in verdicts.items() if v.get("ok") is not True]
    out = [fraction_component(
        "manifest_checks_passing", _SCHEDULER, passing, float(len(verdicts)),
        unit="manifest integrity checks passing",
        detail=f"{passing:g}/{len(verdicts)} checks green over {_field(doc, 'cron_entries')} cron "
               f"and {_field(doc, 'systemd_entries')} systemd entries; failing: "
               f"{', '.join(failing) or 'none'}")]

    live = checks.get("live_crontab")
    live_map = live if isinstance(live, dict) else {}
    if live_map.get("readable") is not True:
        out.append(unmeasured_component(
            "live_crontab_matches_manifest", _SCHEDULER,
            f"the live crontab is not readable from this box ({live_map.get('note') or 'no note'})"
            " -- so manifest-versus-machine DRIFT is unmeasured. A manifest that agrees with "
            "itself is not evidence the box runs what it says"))
    else:
        drift = sum((_len_or_none(live_map.get(k)) or 0.0)
                    for k in ("missing_in_live", "extra_in_live", "duplicated_in_live"))
        out.append(inverse_ladder_component(
            "live_crontab_matches_manifest", _SCHEDULER, drift, DEFECT_LADDER,
            unit="manifest/live crontab discrepancies",
            detail=f"missing {live_map.get('missing_in_live')}, extra "
                   f"{live_map.get('extra_in_live')}, duplicated "
                   f"{live_map.get('duplicated_in_live')}"))
    return out


def _secret_permission(root: Path, _now: datetime) -> list[Component]:
    """Can the desk WRITE what it must write and READ what it must read -- and is it credentialled?

    Permission faults are the quietest class of outage on this box: an unwritable log directory
    turns every organ's evidence into nothing, and an absent credential turns a wired seat into a
    silent one. Desk code deliberately never WRITES a secret (a repo that can write its own
    secrets is a repo that can leak them), so the score here is about provisioning and access,
    never about the desk manufacturing keys for itself.
    """
    ready = _read_json(root / _READINESS)
    writable = ready.get("log_dir_writable") if ready is not None else None
    out = [binary_component(
        "log_dir_writable", _READINESS, writable if isinstance(writable, bool) else None,
        detail=f"log_dir_writable={writable}, gate_ok={_field(ready, 'gate_ok')}, doctrine "
               f"{_field(ready, 'doctrine_bytes')} bytes at {_field(ready, 'ts')}",
        fix="FIX THE LOG DIRECTORY PERMISSIONS -- an organ that cannot write its evidence "
            "produces nothing, and 'produced nothing' is indistinguishable from 'never ran'",
        held="AT CEILING -- the desk can write its own evidence")]

    runway = _read_json(root / _RUNWAY)
    creds = runway.get("creds_present") if runway is not None else None
    out.append(binary_component(
        "llm_credentials_provisioned", _RUNWAY, creds if isinstance(creds, bool) else None,
        detail=f"creds_present={creds} at {_field(runway, 'checked')}; log dir "
               f"{_field(runway, 'log_dir')}",
        fix="PROVISION THE CREDENTIAL -- it is an operator step by design (desk code must never "
            "write a secret). Until it lands, every seat is wired and unfunded",
        held="AT CEILING -- the seats are credentialled by the operator, as designed"))

    # THE AUDIT'S OWN PHANTOM-PATH CHECK is the closest thing the desk has to a filesystem-
    # hygiene fence: paths read by code that nothing writes. It names secrets explicitly as the
    # legitimately-absent class, so what remains is genuine read-without-writer.
    out.append(inverse_ladder_component(
        "phantom_path_defects", _AUDIT, _audit_defects(root, "phantom-"), DEFECT_LADDER,
        unit="read-without-writer path defects live in the audit",
        detail="paths code reads that nothing on this desk writes; operator-provisioned secrets "
               "are excluded by the audit's own allowlist, so these are real wiring faults"))
    return out


_MYPY = "data/mypy_ratchet.json"
_BUILD_STANDARD = "data/build_standard.json"
_WIRING = "data/wiring_agent.json"


def _engineering_standard(root: Path, _now: datetime) -> list[Component]:
    """Does new work enter above the standard, and is what was built actually REACHABLE?

    Two failure directions, both measured by organs that already exist: work entering below the
    build standard (no refusal path, untested, unscheduled, unmapped to a law), and work that
    entered fine and is now unreachable -- engineering already paid for that returns zero forever
    and rots into a liability.
    """
    build = _read_json(root / _BUILD_STANDARD)
    governed = _num(_field(build, "n_governed"))
    failing = _num(_field(build, "n_failing"))
    out = [fraction_component(
        "organs_meeting_build_standard", _BUILD_STANDARD,
        None if governed is None or failing is None else governed - failing, governed,
        unit="governed organs meeting the build standard",
        detail=f"status {_field(build, 'status')}: {failing} failing of {governed} governed; "
               f"unreadable inputs {_field(build, 'unreadable_inputs')}")]

    mypy = _read_json(root / _MYPY)
    out.append(fraction_component(
        "strict_typing_clean_share", _MYPY, _num(_field(mypy, "clean_fraction")), 1.0,
        unit="of scanned files carrying ZERO strict-mode errors",
        detail=f"clean fraction {_field(mypy, 'clean_fraction')} over "
               f"{_len_or_none(_field(mypy, 'per_file'))} files, {_field(mypy, 'total_errors')} "
               f"errors total, measured {_field(mypy, 'generated')}"))

    wiring = _mapping(_read_json(root / _WIRING), "counts")
    proposals = _num((wiring or {}).get("PROPOSE"))
    out.append(inverse_ladder_component(
        "unwired_proposals_open", _WIRING, proposals, DEFECT_LADDER,
        unit="open wiring proposals (built, not reachable)",
        detail=f"counts {wiring} over {_field(_read_json(root / _WIRING), 'n_scripts_scanned')} "
               "scripts scanned -- each proposal is capability already paid for and returning "
               "zero"))
    out.append(inverse_ladder_component(
        "unwired_module_defects", _AUDIT, _audit_defects(root, "unwired-"), DEFECT_LADDER,
        unit="live unwired-module defects in the audit",
        detail="library modules nothing imports, and scripts that are the only importer of a "
               "module nothing invokes -- built, tested and unreachable"))
    return out


_SOURCE_ALTERNATIVES = "data/source_alternatives_report.json"
_SOURCE_HEALTH = "data/source_health.jsonl"


def _source_resilience(root: Path, _now: datetime) -> list[Component]:
    """When a source dies, does the desk already know where else to look?

    A dead source with no registered alternative is a research seam that closes silently. The
    vantage caveat is carried, not dropped: a probe from this container says something about THIS
    egress path, and a candidate failing here may be fine on the box that collects.
    """
    doc = _read_json(root / _SOURCE_ALTERNATIVES)
    if doc is None:
        out = [unmeasured_component(
            "dead_sources_without_alternatives", _SOURCE_ALTERNATIVES,
            f"{_SOURCE_ALTERNATIVES} absent -- nothing tracks whether a dead source has a "
            "registered replacement, so a closing seam is invisible until someone notices the "
            "silence")]
    else:
        out = [inverse_ladder_component(
            "dead_sources_without_alternatives", _SOURCE_ALTERNATIVES,
            _len_or_none(doc.get("dead_without_registered_alternatives")), DEFECT_LADDER,
            unit="dead sources with NO registered alternative",
            detail=f"{_len_or_none(doc.get('dead_sources'))} dead of "
                   f"{_len_or_none(doc.get('registry'))} registered, mode {doc.get('mode')}, "
                   f"vantage {doc.get('vantage')} -- {str(doc.get('vantage_note'))[:80]}")]

    rows = _read_jsonl(root / _SOURCE_HEALTH)
    if not rows:
        out.append(unmeasured_component(
            "sources_healthy", _SOURCE_HEALTH,
            f"{_SOURCE_HEALTH} absent or empty -- no per-source verdict ledger, so 'the "
            "collectors are fine' rests on nobody having complained"))
    else:
        latest: dict[str, dict[str, Any]] = {}
        for row in rows:
            name = row.get("source")
            if isinstance(name, str):
                latest[name] = row
        healthy = float(sum(1 for r in latest.values() if r.get("verdict") == "HEALTHY"))
        degraded = sorted(k for k, r in latest.items() if r.get("verdict") != "HEALTHY")
        out.append(fraction_component(
            "sources_healthy", _SOURCE_HEALTH, healthy, float(len(latest)),
            unit="registered sources whose latest verdict is HEALTHY",
            detail=f"{healthy:g}/{len(latest)} healthy on their most recent probe; not healthy: "
                   f"{', '.join(degraded) or 'none'}"))
    return out


_BLINDSPOT = "data/blindspot_max.json"


def _blind_spots(root: Path, _now: datetime) -> list[Component]:
    """Is the desk conditioning on the slices it KNOWS exist, and reading the fields it has?

    A blind spot is not an unknown unknown once it has been enumerated -- it is a known gap being
    left open, which is a different and much cheaper defect to close.
    """
    doc = _read_json(root / _BLINDSPOT)
    slices = _rows(doc, "slices")
    if slices is None or not slices:
        out = [unmeasured_component(
            "slices_conditioned", _BLINDSPOT,
            f"{_BLINDSPOT} carries no slice list -- nothing enumerates the conditioning axes, so "
            "'we condition on regime' is a claim rather than a measurement")]
    else:
        done = float(sum(1 for s in slices if s.get("conditioned") is True))
        out = [fraction_component(
            "slices_conditioned", _BLINDSPOT, done, float(len(slices)),
            unit="enumerated slices the desk actually conditions on",
            detail=f"{done:g}/{len(slices)} slices conditioned "
                   f"({', '.join(str(s.get('slice')) for s in slices)}) at "
                   f"{_field(doc, 'updated')}")]
    out.append(inverse_ladder_component(
        "unread_fields", _BLINDSPOT, _num(_field(doc, "unread_fields")), DEFECT_LADDER,
        unit="collected fields nothing reads",
        detail=f"{_field(doc, 'unread_fields')} unread field(s), "
               f"{_len_or_none(_field(doc, 'unmodelled_entities'))} unmodelled entities, "
               f"{_len_or_none(_field(doc, 'uncrossed_pairs'))} uncrossed pairs -- data bought "
               "and never asked a question of"))
    return out


_CONSTITUTION = "docs/research/CONSTITUTION_RATCHET.json"
_LAW_COVERAGE = "docs/research/LAW_COVERAGE.json"


def _constitutional_aggression(root: Path, _now: datetime) -> list[Component]:
    """How aggressive is the constitution the desk actually operates under, and is it enforced?

    The aggression marks are the sibling ratchet's record (libs/doctrine/ratchet.py) -- already on
    the same 0-10 scale the standing order is stated on, so they are read straight rather than
    re-scored. Institutions drift toward timidity one reasonable amendment at a time, and this is
    the number that makes each one visible.
    """
    doc = _read_json(root / _CONSTITUTION)
    marks = _mapping(doc, "high_water")
    if marks is None or not marks:
        out = [unmeasured_component(
            "principle_aggression", _CONSTITUTION,
            f"{_CONSTITUTION} carries no high-water marks -- the constitution's aggression is "
            "unrecorded, which is the state that lets it be softened without anyone noticing")]
    else:
        graded: list[tuple[float, str]] = []
        for name, raw in marks.items():
            value = _num(raw)
            if value is not None:
                graded.append((value, str(name)))
        if not graded:
            out = [unmeasured_component(
                "principle_aggression", _CONSTITUTION,
                f"{_CONSTITUTION} high_water carries no numeric marks")]
        else:
            mean = sum(v for v, _ in graded) / len(graded)
            weakest_score, weakest_name = min(graded)
            out = [fraction_component(
                "principle_aggression", _CONSTITUTION, round(mean, 3), SCALE_MAX,
                unit="of full aggression, meaned over the constitution's own marks",
                detail=f"mean {mean:.2f}/10 over {len(graded)} principles; weakest "
                       f"{weakest_name} at {weakest_score:g}, updated {_field(doc, 'updated')}")]

    live = _mapping(_read_json(root / _LAW_COVERAGE), "live")
    if live is None:
        out.append(unmeasured_component(
            "law_enforcement_coverage", _LAW_COVERAGE,
            f"{_LAW_COVERAGE} carries no live block -- the share of principles enforced both "
            "mechanically and interactionally is unrecorded"))
    else:
        out.append(fraction_component(
            "law_enforcement_coverage", _LAW_COVERAGE, _num(live.get("full_pct")), 100.0,
            unit="% of principles enforced BOTH mechanically and in every interaction",
            detail=f"{live.get('both')}/{live.get('principles')} principles fully enforced "
                   f"(mechanical {live.get('mechanical_pct')}%, interactional "
                   f"{live.get('interactional_pct')}%); {live.get('unenforced')} unenforced"))
    return out


_RETURN_TARGETING = "data/return_targeting.json"
_TIMIDITY = "data/timidity_audit.json"


def _ambition_discipline(root: Path, _now: datetime) -> list[Component]:
    """Is restraint DECLARED as evidence/risk restraint, or is it timidity wearing prudence?

    L1.28 scores timidity as a defect, and the audit that enforces it makes the distinction
    machine-checkable: every scope restraint must state its non-timid reading, and every
    evidence-or-risk restraint must be declared as such and stay strict. An UNCLASSIFIED restraint
    is the interesting one -- nobody has said which kind it is.
    """
    doc = _read_json(root / _TIMIDITY)
    rows = _rows(doc, "rows")
    unclassified = _len_or_none(_field(doc, "unclassified"))
    if rows is None or unclassified is None:
        out = [unmeasured_component(
            "restraints_classified", _TIMIDITY,
            f"{_TIMIDITY} carries no restraint rows -- nothing separates a declared evidence bar "
            "from an undeclared flinch, and the two look identical in a diff")]
    else:
        out = [fraction_component(
            "restraints_classified", _TIMIDITY, float(len(rows)) - unclassified, float(len(rows)),
            unit="restraints classified as scope, evidence or risk",
            detail=f"{len(rows)} restraint(s), {unclassified:g} unclassified; counts "
                   f"{_field(doc, 'counts')}")]
    out.append(inverse_ladder_component(
        "prompt_timidity_hits", _TIMIDITY, _len_or_none(_field(doc, "prompt_timid_hits")),
        DEFECT_LADDER, unit="timid instructions found in live prompt surfaces",
        detail=f"{_len_or_none(_field(doc, 'prompt_timid_hits'))} hit(s) across "
               f"{_field(doc, 'prompt_surfaces_scanned')} prompt surfaces; doctrine injected="
               f"{_field(doc, 'doctrine_injected')}"))

    ret = _read_json(root / _RETURN_TARGETING)
    scoped = _num(_field(ret, "n_scoped"))
    flagged = _num(_field(ret, "n_flagged"))
    out.append(fraction_component(
        "surfaces_free_of_return_targets", _RETURN_TARGETING,
        None if scoped is None or flagged is None else scoped - flagged, scoped,
        unit="governed surfaces with no return NUMBER bound to goal language",
        detail=f"status {_field(ret, 'status')}: {_field(ret, 'detail')}; unreadable "
               f"{_field(ret, 'unreadable')}"))
    return out


#: THE ASPECT LIST. Fixed, ordered, and it may only ever GROW -- an aspect removed is a capability
#: the desk stopped being graded on, which is the deletion loophole one level up from a component.
#: `ceiling` states what 10/10 would MEAN, because a score with no stated ceiling drifts into
#: meaning "as good as we currently know how to be".
#: EVERY BUILDER TAKES THE CLOCK, including the ones that do not use it (they name it `_now`).
#: THAT IS DELIBERATE. Reading a state artifact without checking its age is a fail-open in the
#: FLATTERING direction -- a stale monitor reads exactly like a healthy one, and the longer it
#: stays dead the more confident the number looks. Threading `now` in unconditionally means the
#: clock is always in reach, so age-checking is a decision each builder makes rather than a
#: capability it lacks; and taking it as an argument rather than calling datetime.now() inside
#: keeps every builder testable against a fixed instant.
ASPECTS: tuple[tuple[str, str, Callable[[Path, datetime], list[Component]]], ...] = (
    ("statistical_validation",
     "the validation stack's own tests kill every mutant of it, over complete (never truncated) "
     "runs -- the desk cannot fool itself about whether an edge is real",
     _statistical_validation),
    ("research_discipline",
     "a large, growing suite; a graveyard that keeps filling because ideas get CLOSED; and every "
     "distinct family hunted rather than one family hunted many ways",
     _research_discipline),
    ("risk_rails",
     "every rail mutation-proof and the ruin rail measurably clear from the box that owns the "
     "state -- no rail whose status is unknown",
     _risk_rails),
    ("governance",
     "every law fence green and ZERO live audit defects -- the laws are enforced by machinery "
     "rather than by attention",
     _governance),
    ("data_coverage",
     "every registered asset carrying a measured span and every unknown-unknown organ fresh -- "
     "no dark corner of the desk's own data",
     _data_coverage),
    ("execution_path",
     "Gate 0 fully ready, the money path covered like the money path, and libs/execution "
     "mutation-proof",
     _execution_path),
    ("self_improvement",
     "every ledger row reaching a terminal verdict and 7-day conversion keeping pace with 7-day "
     "arrivals -- found equals fixed",
     _self_improvement),
    ("ops_autonomy",
     "every scheduled organ producing fresh output unattended and every organ assembling a "
     "lawful prompt",
     _ops_autonomy),
    ("alpha_output",
     "the forward cohort full of live clocks and the promotion ladder climbed on closed-trade "
     "evidence -- the aspect every other one exists to serve",
     _alpha_output),
    # THE MINOR ASPECTS, which is to say the ones that actually take desks down. Everything below
    # is measured from an artifact another organ already writes; none of it was worth a headline
    # until it failed, and the standing order says EVERY aspect, not the interesting ones.
    ("alerting_pager",
     "the pager provably delivers between incidents, on more than one channel, with the canary "
     "auditing the ledger rather than the code",
     _alerting),
    ("cost_model_fidelity",
     "the cost model refreshed on its own cadence over the whole universe, with every declared "
     "input readable so the realised-versus-modelled residual is a measurement",
     _cost_model),
    ("forward_clock_hygiene",
     "promotion latency MEASURED end to end rather than designed, births countable from a dated "
     "history, and replacement keeping pace with death",
     _forward_clock),
    ("recorder_tape",
     "the desk's own tape recording continuously, every stream declaring the clock that stamped "
     "it, replicated off the host, with retention clearing the analysis window",
     _recorder_tape),
    ("llm_seat_coverage",
     "every research seat wired, credentialled AND observably producing -- three facts, none of "
     "them allowed to stand in for the others",
     _llm_seats),
    ("dependency_environment",
     "the environment that runs the tests is the environment that runs the money: no major drift "
     "from the deployed pins, no declared dependency missing",
     _dependency_env),
    ("knowledge_currency",
     "everything the desk has learned is retrievable BEFORE compute is spent -- a graveyard that "
     "is a memory rather than a document",
     _knowledge_currency),
    ("backup_dr",
     "every durable store replicated off the host and a restore actually EXERCISED, with disk "
     "headroom clear of the backup organ's own fuse",
     _backup_dr),
    ("mutation_breadth",
     "every money-path file carrying a COMPLETE mutation run -- breadth, so a perfect kill rate "
     "on one small file can never stand in for a tested tree",
     _mutation_breadth),
    ("scheduler_integrity",
     "every scheduled line pointing at a script that exists, parses and locks coherently, AND the "
     "live crontab provably matching the manifest",
     _scheduler_integrity),
    ("secret_permission_hygiene",
     "the desk can write every artifact it must write and read every credential it was given, "
     "with no path read by code that nothing writes",
     _secret_permission),
    ("engineering_standard",
     "nothing enters below the build standard, the tree is strict-clean, and nothing built is "
     "left unreachable",
     _engineering_standard),
    ("capital_utilisation",
     "every paid-for ceiling measured and saturated -- unused headroom is not safety, it is an "
     "unbooked loss",
     _capital_utilisation),
    ("source_resilience",
     "every registered source healthy on its latest probe, and every dead one already carrying a "
     "registered alternative",
     _source_resilience),
    ("blind_spot_coverage",
     "every enumerated slice conditioned on and every collected field read -- an enumerated blind "
     "spot left open is the cheapest defect on the board",
     _blind_spots),
    ("constitutional_aggression",
     "the constitution held at full aggression and every principle enforced BOTH mechanically and "
     "in every interaction",
     _constitutional_aggression),
    ("ambition_discipline",
     "every restraint declared as scope, evidence or risk; no timid instruction in a live prompt; "
     "no return NUMBER bound to goal language",
     _ambition_discipline),
)

ASPECT_KEYS: tuple[str, ...] = tuple(k for k, _, _ in ASPECTS)


def score_aspect(key: str, ceiling: str, components: list[Component]) -> Aspect:
    """Mean over MEASURED components only; UNMEASURED ones are carried, never averaged in.

    Averaging an unmeasured component as 0 would punish the desk for not knowing, and as 10 would
    reward it -- so the mean's denominator is what was actually measured, and the count of what
    was not is published beside it so nobody reads a 2-of-5 mean as a whole-aspect verdict.
    """
    scored = [c.score for c in components if c.state == MEASURED and c.score is not None]
    if not scored:
        whys = "; ".join(c.detail for c in components) or "no component produced a reading"
        return Aspect(key=key, ceiling=ceiling, state=UNMEASURED, score=None,
                      components=tuple(components),
                      binding_constraint=f"UNMEASURED -- {whys}")
    score = _round(sum(scored) / len(scored))
    weakest = min((c for c in components if c.state == MEASURED and c.score is not None),
                  key=lambda c: (c.score if c.score is not None else 0.0))
    unmeasured = [c for c in components if c.state == UNMEASURED]
    constraint = f"{weakest.key} at {weakest.score:.1f} -- {weakest.constraint}"
    if unmeasured:
        constraint += (f" [+{len(unmeasured)} UNMEASURED component(s): "
                       f"{', '.join(c.key for c in unmeasured)} -- the score above covers only "
                       f"{len(scored)} of {len(components)} components]")
    return Aspect(key=key, ceiling=ceiling, state=MEASURED, score=score,
                  components=tuple(components), binding_constraint=constraint)


def read_capability(root: Path, now: datetime | None = None) -> tuple[Aspect, ...]:
    """Score every aspect from the artifacts on disk. Pure read -- nothing here measures.

    `now` is the instant every staleness judgement is made against, threaded in rather than read
    from the system clock inside a builder: a component that calls datetime.now() itself cannot be
    tested against a fixed instant, and an age check nobody can test is an age check nobody should
    trust. Defaulting it here keeps the read-only callers (dashboards, the CRO dossier) working
    unchanged.
    """
    at = now if now is not None else datetime.now(tz=UTC)
    return tuple(score_aspect(key, ceiling, build(root, at)) for key, ceiling, build in ASPECTS)


def desk_binding_constraint(aspects: tuple[Aspect, ...]) -> dict[str, Any]:
    """THE ONE LINE A WEEKLY SWEEP ACTS ON FIRST: the lowest-scoring component on the whole desk.

    Per-aspect constraints are a queue of thirty-odd items, which is a queue nobody works. This
    picks the single desk-wide minimum and names the artifact, the reading and the specific next
    thing that raises it.

    IT IS THE MINIMUM OVER MEASURED COMPONENTS ONLY, and the count of unmeasured ones is published
    beside it rather than folded in. An unmeasured component has no score to be the minimum OF --
    treating it as a zero would make "the thing nobody measures" permanently the top priority,
    which sounds rigorous and is actually how a board full of absent measurements out-shouts a
    real defect. Unmeasured work has its own list, and its own instruction: measure it.

    The tie-break is (score, aspect key, component key) -- deterministic, so the same desk state
    always produces the same instruction and a reader can tell a real change of priority from
    dictionary ordering.
    """
    scored = [(a, c, c.score) for a in aspects for c in a.components
              if c.state == MEASURED and c.score is not None]
    unmeasured = [(a, c) for a in aspects for c in a.components if c.state == UNMEASURED]
    if not scored:
        return {
            "state": UNMEASURED,
            "aspect": None, "component": None, "score": None, "artifact": None,
            "n_unmeasured_components": len(unmeasured),
            "constraint": ("NOTHING IS MEASURED. There is no desk-wide minimum because there is "
                           "no reading -- the binding constraint is the measurement itself. Start "
                           "with the unmeasured_components list; every row names the artifact that "
                           "would settle it."),
        }
    worst_aspect, worst, score = min(scored, key=lambda t: (t[2] or 0.0, t[0].key, t[1].key))
    return {
        "state": MEASURED,
        "aspect": worst_aspect.key,
        "component": worst.key,
        "score": score,
        "artifact": worst.artifact,
        "n_unmeasured_components": len(unmeasured),
        "detail": worst.detail,
        "constraint": worst.constraint,
        "_": (f"LOWEST-SCORING COMPONENT DESK-WIDE: {worst_aspect.key}.{worst.key} at "
              f"{score:.1f}/10 out of {worst.artifact}. This is the line to work first. "
              f"{len(unmeasured)} component(s) are UNMEASURED and are NOT eligible to be this "
              "minimum -- an absent measurement has no score, and letting it win here would bury "
              "every real defect under things nobody has looked at yet."),
    }


# --------------------------------------------------------------------------------------------
# THE RATCHET ITSELF.
# --------------------------------------------------------------------------------------------


def load_marks(path: Path) -> Marks:
    """Read the high-water record. A missing file means NO HISTORY, not a clean slate at zero.

    Same reasoning as libs/doctrine/ratchet.load_baseline: with no recorded history there is
    nothing to have regressed FROM, and the first run writes today's reading as the mark. A
    DELETED record is a different fact and is caught where it belongs -- the artifact's own
    `first_recorded` stamp resetting is visible in the diff and in the printed table.
    """
    doc = _read_json(path)
    if doc is None:
        return Marks({}, {}, "", "", 0)
    aspect_raw = doc.get("high_water")
    comp_raw = doc.get("component_high_water")

    def _floats(raw: object) -> dict[str, float]:
        if not isinstance(raw, dict):
            return {}
        out: dict[str, float] = {}
        for k, v in raw.items():
            n = _num(v)
            if n is not None:
                out[str(k)] = n
        return out

    return Marks(
        aspect_high_water=_floats(aspect_raw),
        component_high_water=_floats(comp_raw),
        last_raise_at=str(doc.get("last_raise_at") or ""),
        first_recorded=str(doc.get("first_recorded") or ""),
        n_raises=int(_num(doc.get("n_raises")) or 0),
    )


def _component_marks(aspect: Aspect, marks: Marks) -> dict[str, float]:
    prefix = f"{aspect.key}."
    return {k: v for k, v in marks.component_high_water.items() if k.startswith(prefix)}


def attainable(aspect: Aspect, marks: Marks) -> float | None:
    """What this aspect would score if EVERY component it grades today stood at its own best.

    A component's best is its recorded mark, or today's reading when it has no mark yet -- a
    component measured for the first time has no history, so today IS its best-so-far. Taking the
    MAX of the two is what keeps the number safe: a component that regressed still contributes its
    old mark here, so a regression can never make an aspect look merely "wider".

    None when the aspect grades nothing measurable -- there is then nothing to compare with.
    """
    prior = _component_marks(aspect, marks)
    bests: list[float] = []
    for c in aspect.components:
        if c.state != MEASURED or c.score is None:
            continue
        bests.append(max(prior.get(f"{aspect.key}.{c.key}", c.score), c.score))
    if not bests:
        return None
    return _round(sum(bests) / len(bests))


def _widening(aspect: Aspect, marks: Marks) -> tuple[bool, list[str], str]:
    """Is the aspect's mark still COMPARABLE to today's reading, or was it earned over less?

    THE TEST IS ATTAINABILITY, and it is deliberately stateless -- derived from the marks
    themselves rather than from a remembered component list. If the aspect's mark is higher than
    the mean of the CURRENT components' own best-ever scores, then no arrangement of today's
    components could ever have produced that mark: it was earned over a different, narrower set.
    Comparing today's mean against it is therefore not a comparison at all, and reporting the gap
    as a regression asserts something the record cannot support.

    WHY NOT REMEMBER THE SET INSTEAD. A remembered basis has to be reconstructed for every record
    written before it existed, and the reconstruction is a guess. This needs no history, no
    migration, and it SELF-CORRECTS: the moment the aspect beats its old mark over the wider set,
    the mark rises, attainability catches up, and the aspect is comparable again forever after.

    IT CANNOT LAUNDER A REGRESSION. Every component mark is a high-water mark, so a component that
    dropped still sits at its old best in `prior` and does not lower attainability -- it produces a
    NAMED CAUSE in _fall_causes and the aspect is FELL before this is consulted. Deleting a strong
    component is a WENT-DARK cause for the same reason. The only way to reach this branch is for
    the current component set to be genuinely incapable of the recorded mark, which is exactly what
    "the mark was measured over less" means.
    """
    mark = marks.aspect_high_water.get(aspect.key)
    reach = attainable(aspect, marks)
    if mark is None or reach is None or reach >= mark - EPS:
        return False, [], ""
    prior = _component_marks(aspect, marks)
    added = sorted(c.key for c in aspect.components
                   if c.state == MEASURED and f"{aspect.key}.{c.key}" not in prior)
    return True, added, (
        f"with every component of today's set at its OWN best the aspect would reach {reach:.1f}, "
        f"below the recorded {mark:.1f} -- so that mark cannot have been earned over this set")


def _fall_causes(aspect: Aspect, marks: Marks) -> list[str]:
    """Localise a fall to the component(s) that caused it. A fall with no named cause is itself
    reportable -- see the caller."""
    prior = _component_marks(aspect, marks)
    now = {f"{aspect.key}.{c.key}": c for c in aspect.components}
    causes: list[str] = []
    for full, mark in sorted(prior.items()):
        cur = now.get(full)
        if cur is None:
            causes.append(
                f"{full} WENT DARK (stood at {mark:.1f}) -- a measurement that disappears is "
                "scored as the capability it evidenced disappearing, never as neutral")
        elif cur.state == UNMEASURED:
            causes.append(
                f"{full} became UNMEASURED (stood at {mark:.1f}): {cur.detail}")
        elif cur.score is not None and cur.score < mark - EPS:
            causes.append(
                f"{full} {mark:.1f} -> {cur.score:.1f} ({cur.artifact}): {cur.detail}")
    return causes


def ratchet(aspects: tuple[Aspect, ...], marks: Marks,
            now: datetime) -> tuple[Marks, list[Verdict], str]:
    """Compare today's reading against the record, then RAISE the record. Never lowers anything.

    The asymmetry is the entire design, copied from the aggression ratchet: improving is
    frictionless, and giving ground is impossible through this path -- it produces a defect with a
    named cause instead, which is a thing somebody has to answer for.
    """
    verdicts: list[Verdict] = []
    aspect_hw = dict(marks.aspect_high_water)
    comp_hw = dict(marks.component_high_water)
    raised_any = False

    for a in aspects:
        mark = marks.aspect_high_water.get(a.key)
        causes = _fall_causes(a, marks)

        if a.state == UNMEASURED:
            if mark is not None:
                movement, cause = WENT_DARK, (
                    "; ".join(causes) or
                    f"the whole aspect stopped measuring while its record stood at {mark:.1f}: "
                    f"{a.binding_constraint}")
            else:
                movement, cause = UNMEASURED, a.binding_constraint
            verdicts.append(Verdict(a.key, movement, None, mark, cause))
            continue

        score = a.score if a.score is not None else 0.0
        fell_aspect = mark is not None and score < mark - EPS
        widened, added, why_basis = _widening(a, marks)
        if causes:
            movement, cause = FELL, "; ".join(causes)
        elif fell_aspect and mark is not None and widened:
            # THE DESK IS GRADING ITSELF ON MORE, and nothing that was already graded got worse.
            # Every prior component still holds its own mark (or this branch would be unreachable
            # -- `causes` is built from exactly that comparison), so the drop is arithmetic from a
            # wider denominator, not a capability going backwards. The old mark is KEPT and printed
            # beside today's reading, because the honest statement is "9.0 was measured over less".
            # THIS PERSISTS until the aspect beats its mark over the WIDER set, which is the point:
            # a one-run amnesty would leave an unexplained fall reported every day forever after,
            # and a gate that is permanently red is a gate that is permanently ignored.
            movement = WIDENED
            first_seen = f" First graded this run: {', '.join(added)}." if added else ""
            cause = (f"aspect mean {mark:.1f} -> {score:.1f} while grading "
                     f"{len(a.components)} component(s) -- {why_basis}. NO component that already "
                     f"had a mark is below it, so nothing got worse: the mark was earned over a "
                     f"NARROWER set and is not comparable to today's reading. It STAYS at "
                     f"{mark:.1f}; beating it OVER THE WIDER SET is the work.{first_seen} Next: "
                     f"{a.binding_constraint}")
        elif fell_aspect and mark is not None:
            # A fall the component marks cannot explain, over EXACTLY the set the mark was earned
            # over. It is a fall and it needs a cause -- saying so is the check refusing to accept
            # an unexplained regression rather than quietly logging one.
            movement = FELL
            cause = (f"aspect mean {mark:.1f} -> {score:.1f} over the SAME component set the mark "
                     "was earned on, with no component below its own mark. NAME the cause in the "
                     "diff; an unexplained fall is never accepted.")
        elif mark is None:
            movement, cause = NEW, f"first reading recorded at {score:.1f}: {a.binding_constraint}"
            raised_any = True
        elif score > mark + EPS:
            movement = RAISED
            cause = f"{mark:.1f} -> {score:.1f}. Next: {a.binding_constraint}"
            raised_any = True
        elif score >= SCALE_MAX - EPS:
            movement = AT_CEILING
            cause = f"10/10 held. {a.binding_constraint}"
        else:
            movement = FLATLINE
            cause = a.binding_constraint

        verdicts.append(Verdict(a.key, movement, score, mark, cause))
        aspect_hw[a.key] = max(mark if mark is not None else score, score)
        for c in a.components:
            if c.state == MEASURED and c.score is not None:
                full = f"{a.key}.{c.key}"
                comp_hw[full] = max(comp_hw.get(full, c.score), c.score)

    status = _status(verdicts, marks, now, raised_any)
    new = Marks(
        aspect_high_water=dict(sorted(aspect_hw.items())),
        component_high_water=dict(sorted(comp_hw.items())),
        last_raise_at=now.isoformat() if raised_any else marks.last_raise_at,
        first_recorded=marks.first_recorded or now.isoformat(),
        n_raises=marks.n_raises + (1 if raised_any else 0),
    )
    return new, verdicts, status


def _status(verdicts: list[Verdict], marks: Marks, now: datetime, raised_any: bool) -> str:
    """REGRESSED > STALLED > RAISED > WIDENED > FLATLINE. A fall outranks everything: it is the one
    state the ratchet exists to make impossible to reach quietly.

    WIDENED sits BELOW stalled deliberately. Grading yourself on more is good, but it is not a
    RAISE and must never reset the stall clock -- otherwise "add another component" would be the
    cheap way to look busy for another seven days without any capability moving.
    """
    if any(v.movement in (FELL, WENT_DARK) for v in verdicts):
        return "REGRESSED"
    if raised_any:
        return "RAISED"
    last = _parse_ts(marks.last_raise_at)
    if last is not None and now - last > timedelta(days=STALL_DAYS):
        return "STALLED"
    if any(v.movement == WIDENED for v in verdicts):
        return WIDENED
    return "FLATLINE"


def days_since_raise(marks: Marks, now: datetime) -> float | None:
    last = _parse_ts(marks.last_raise_at)
    if last is None:
        return None
    return round((now - last).total_seconds() / 86400.0, 2)


def build_artifact(aspects: tuple[Aspect, ...], marks: Marks, verdicts: list[Verdict],
                   status: str, now: datetime) -> dict[str, Any]:
    """The on-disk record: the marks, the current reading, and every movement with its cause."""
    by_key = {v.aspect: v for v in verdicts}
    measured = [a for a in aspects if a.state == MEASURED and a.score is not None]
    unmeasured_components = [
        {"aspect": a.key, "component": c.key, "artifact": c.artifact, "why": c.detail}
        for a in aspects for c in a.unmeasured]
    return {
        "_": ("HIGH-WATER MARKS for desk CAPABILITY, one score per named aspect on the 0-10 scale "
              "the principal's standing order is stated on. Raised automatically; NEVER lowered "
              "by code. A FALL is a defect reported with a NAMED CAUSE, a FLATLINE is reported "
              "with the binding constraint that is holding the aspect down, and UNMEASURED is its "
              "own state -- never silently a 0 and never silently a 10."),
        "law": ("R0104 -- every aspect is pushed toward 10/10 every day, non-exhaustively. A "
                "rating nobody records cannot ratchet, and a score that can silently fall is not "
                "a standard."),
        "generated": now.isoformat(),
        "status": status,
        "scale_max": SCALE_MAX,
        "stall_days": STALL_DAYS,
        "n_aspects": len(aspects),
        "n_measured": len(measured),
        "n_unmeasured": len(aspects) - len(measured),
        # The mean over MEASURED aspects only, and it is NOT a desk score: it is published so a
        # fall in the aggregate is visible, next to the count of what it could not see.
        "measured_mean": (round(sum(a.score or 0.0 for a in measured) / len(measured), 2)
                          if measured else None),
        "first_recorded": marks.first_recorded,
        "last_raise_at": marks.last_raise_at,
        "days_since_raise": days_since_raise(marks, now),
        "n_raises": marks.n_raises,
        # THE WEEKLY SWEEP'S FIRST LINE. Everything else on this page is a list; this is an
        # instruction.
        "binding_constraint": desk_binding_constraint(aspects),
        "high_water": marks.aspect_high_water,
        "component_high_water": marks.component_high_water,
        "aspects": [
            {
                "key": a.key,
                "state": a.state,
                "score": a.score,
                "high_water": marks.aspect_high_water.get(a.key),
                "movement": by_key[a.key].movement,
                "cause": by_key[a.key].cause,
                "binding_constraint": a.binding_constraint,
                "ceiling": a.ceiling,
                "artifacts": list(a.artifacts),
                "components": [
                    {"key": c.key, "state": c.state, "score": c.score, "artifact": c.artifact,
                     "detail": c.detail, "constraint": c.constraint}
                    for c in a.components],
            }
            for a in aspects],
        "defects": [{"aspect": v.aspect, "movement": v.movement, "score": v.score,
                     "high_water": v.high_water, "cause": v.cause}
                    for v in verdicts if v.movement in (FELL, WENT_DARK)],
        "flatlined": [{"aspect": v.aspect, "score": v.score, "binding_constraint": v.cause}
                      for v in verdicts if v.movement in (FLATLINE, AT_CEILING)],
        "raised": [{"aspect": v.aspect, "score": v.score, "detail": v.cause}
                   for v in verdicts if v.movement in (RAISED, NEW)],
        # NOT a defect list. An aspect whose mean fell purely because it now grades MORE, with
        # nothing that was already graded getting worse. The old mark is kept beside it.
        "widened": [{"aspect": v.aspect, "score": v.score, "high_water": v.high_water,
                     "detail": v.cause}
                    for v in verdicts if v.movement == WIDENED],
        "unmeasured": [{"aspect": v.aspect, "why": v.cause}
                       for v in verdicts if v.movement == UNMEASURED],
        "unmeasured_components": unmeasured_components,
    }

```

### libs\research\fusion_search.py
```python
"""FUSION SEARCH ENGINE -- combinatorial dataset search that cannot quietly buy itself a lottery
ticket (EXECUTION_QUEUE.md RANK 5).

DISTINCT FROM ``scripts/fusion_engine.py``, which TRANSFORMS a known set of inputs. This SEARCHES:
enumerate combinations of the desk's datasets, build candidate representations, screen each one.
The queue's own warning is the entire design constraint -- *"combinatorial search is a trial-count
explosion, and the desk's own law says breadth is EARNED per axis after a single-axis screen shows
signal. So the search must be mechanism-prior-gated, not exhaustive-by-default."*

An ungated version of this module is the single most dangerous thing the desk could build. 20
datasets taken 3 at a time is 1,140 combinations; times 3 representations times 3 horizons is
10,260 trials. At that width the best cell has an expected Sharpe near 1.0 **on pure noise**, so it
would hand back a beautiful, entirely fake survivor every single run, and every downstream gate
would be evaluating a number that was selected precisely for being extreme. Three rules keep it
honest, and all three had to be structural rather than advisory:

1. BREADTH IS EARNED, NOT ASSUMED. An axis may enter combination search only if it has ALREADY
   returned SCREEN-INTERESTING on its own. Combining axes that individually carry nothing is not
   discovery, it is fishing with more hooks: the graveyard is full of axes that failed single-axis
   screens (exchange_netflow's residual IC flipped sign; aggregate positioning t=+0.15), and
   pairing three of those cannot manufacture information none of them has.

2. THE BUDGET IS CHARGED ON ENUMERATION, NOT EXECUTION. This is ``libs/research/pre_filter.py``'s
   rule applied to combinatorics: *"a pre-filter REJECT still counts in the trial ledger. The filter
   saves COMPUTE, never multiplicity budget -- a candidate we looked at is a candidate we tested,
   however cheaply."* So ``effective_n_trials`` is the size of the ENUMERATED grid. Pruning 900 of
   1,000 cells cheaply still costs 1,000 trials, and stopping early after a hit costs the full grid
   too -- otherwise the stopping rule itself becomes the overfit.

3. THE GRID IS PRE-REGISTERED AND HASHED. ``FusionPlan.grid_hash`` covers every cell before any
   compute runs, so a grid cannot be grown after results are seen and then reported at the smaller
   count. Garden-of-forking-paths by grid extension is otherwise undetectable after the fact.

WHAT IT WILL DO ON THIS DESK TODAY: nothing, loudly. Zero axes have earned breadth, so
``plan_search`` returns an empty grid with the reason per axis. That is the correct output, not a
failure -- an engine that searched anyway would be the failure.

REPRESENTATIONS CARRY MECHANISMS, not just arithmetic; see ``REPRESENTATIONS``. A representation
without a stated mechanism is a free parameter, and free parameters are what the trial count is
supposed to be pricing.

Pure numpy. Import from ``libs.research.fusion_search``; CLI is ``scripts/run_fusion_search.py``.
"""

from __future__ import annotations

import hashlib
import itertools
import json
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np

_ROOT = Path(__file__).resolve().parents[2]

#: Verdict from ``libs.research.axis_screen`` that earns an axis the right to be combined. Nothing
#: weaker qualifies -- TIMING-ARTIFACT and SUSPECT-LOOKAHEAD are artifacts, and a plain miss is a
#: miss. This constant IS rule 1.
EARNING_VERDICT = "SCREEN-INTERESTING"

#: Hard ceiling on enumerated cells. Not a performance guard -- a MULTIPLICITY guard. Above this the
#: deflated-Sharpe hurdle is so high that no real edge this desk can measure would clear it, so
#: enumerating more cells cannot produce a promotable result and can only produce a lucky-looking
#: one. Refusing is strictly better than searching and then failing to promote.
MAX_CELLS = 240

#: Combination width. Triples per the queue; pairs are cheaper and are searched first when allowed.
DEFAULT_K = 3


def _z(x: np.ndarray, win: int = 20) -> np.ndarray:
    """Causal rolling z-score. Uses only data at or before t -- never a full-sample mean."""
    x = np.asarray(x, dtype=float)
    out = np.full(x.shape, np.nan)
    for t in range(len(x)):
        lo = max(0, t - win + 1)
        w = x[lo:t + 1]
        w = w[np.isfinite(w)]
        if len(w) >= max(5, win // 4):
            sd = float(np.std(w))
            out[t] = (x[t] - float(np.mean(w))) / sd if sd > 0 else 0.0
    return out


def _col_mean(rows: np.ndarray) -> np.ndarray:
    """Column-wise mean ignoring NaN, NaN where a column is entirely NaN.

    Not ``np.nanmean``: the z-score warmup leaves whole columns NaN, and nanmean emits "Mean of
    empty slice" there. The repo turns warnings into errors, and silencing the warning would also
    silence real ones -- so the count guard is explicit instead.
    """
    finite = np.isfinite(rows)
    cnt = finite.sum(axis=0)
    tot = np.where(finite, rows, 0.0).sum(axis=0)
    return np.where(cnt > 0, tot / np.maximum(cnt, 1), np.nan)


def _composite(cols: Sequence[np.ndarray]) -> np.ndarray:
    """Mean of z-scores. MECHANISM: these series measure ONE latent pressure, so averaging them
    cancels idiosyncratic noise and leaves the common component."""
    return np.asarray(_col_mean(np.vstack([_z(c) for c in cols])), dtype=float)


def _divergence(cols: Sequence[np.ndarray]) -> np.ndarray:
    """z(first) minus the mean z of the rest. MECHANISM: the first series is out of line with
    series that normally track it, and the gap is the information -- the kimchi/premium shape."""
    zs = [_z(c) for c in cols]
    peers = _col_mean(np.vstack(zs[1:])) if len(zs) > 1 else np.zeros_like(zs[0])
    return np.asarray(zs[0] - peers, dtype=float)


def _conditioned(cols: Sequence[np.ndarray]) -> np.ndarray:
    """z(first), zeroed unless the others AGREE in sign. MECHANISM: the signal is only meaningful
    in a confirming regime; disagreement means the state is ambiguous, so take no view."""
    zs = [_z(c) for c in cols]
    if len(zs) < 2:
        return np.asarray(zs[0], dtype=float)
    others = np.vstack(zs[1:])
    agree = np.all(np.sign(others) == np.sign(others[0]), axis=0) & np.isfinite(others[0])
    return np.asarray(np.where(agree, zs[0], 0.0), dtype=float)


#: name -> (builder, stated mechanism). A representation with no mechanism is a free parameter.
REPRESENTATIONS: dict[str, tuple[Callable[[Sequence[np.ndarray]], np.ndarray], str]] = {
    "composite": (_composite, "the series share one latent pressure; averaging cancels noise"),
    "divergence": (_divergence,
                   "the first series is out of line with peers that normally track it"),
    "conditioned": (_conditioned,
                    "the first series only informs when the others confirm the state"),
}


@dataclass(frozen=True)
class AxisEligibility:
    """Whether one axis has EARNED the right to be combined, with the reason either way."""

    axis: str
    earned: bool
    reason: str
    single_axis_verdict: str | None = None


@dataclass(frozen=True)
class FusionCell:
    """One pre-registered trial. Immutable: a cell cannot be edited after the grid is hashed."""

    axes: tuple[str, ...]
    representation: str
    horizon_days: int

    @property
    def cell_id(self) -> str:
        return f"{'+'.join(self.axes)}|{self.representation}|h{self.horizon_days}"


@dataclass
class FusionPlan:
    """The grid, declared BEFORE compute and hashed so it cannot grow afterwards."""

    cells: list[FusionCell] = field(default_factory=list)
    eligible: list[str] = field(default_factory=list)
    excluded: list[AxisEligibility] = field(default_factory=list)
    refused_reason: str | None = None

    @property
    def grid_hash(self) -> str:
        payload = json.dumps(sorted(c.cell_id for c in self.cells))
        return hashlib.sha256(payload.encode()).hexdigest()[:16]

    @property
    def effective_n_trials(self) -> int:
        """The multiplicity owed: the ENUMERATED grid, not the cells that survived pruning."""
        return len(self.cells)


@dataclass
class CellResult:
    cell_id: str
    verdict: str
    ic: float | None = None
    sharpe: float | None = None
    pruned: bool = False
    note: str = ""


@dataclass
class FusionResult:
    """Every enumerated cell is accounted for -- survivors AND the ones nobody wants to report."""

    grid_hash: str
    effective_n_trials: int
    results: list[CellResult] = field(default_factory=list)
    survivors: list[str] = field(default_factory=list)
    dsr_hurdle_sharpe: float | None = None
    refused_reason: str | None = None

    @property
    def n_pruned(self) -> int:
        return sum(1 for r in self.results if r.pruned)


def eligibility_from_registry(screens: Mapping[str, str],
                              root: Path | None = None) -> list[AxisEligibility]:
    """Eligibility over the RANK 4 registry's assets -- the queue's "triples from the registry".

    TWO gates, and the registry supplies the one screens cannot. A verdict says an axis carries
    signal; the registry says the data actually EXISTS and how long it is. Combining an axis whose
    span is unmeasured on this box would enumerate trials against data that is not there, and the
    resulting NO-INPUT cells would still be charged to the multiplicity budget -- paying real
    trials for cells that were never testable.
    """
    try:
        from libs.research.data_registry import build
        assets = {a.id: a for a in build(root)}
    except Exception:
        return eligibility_from_screens(screens)

    out: list[AxisEligibility] = []
    for axis, verdict in sorted(screens.items()):
        asset = assets.get(axis)
        earned = verdict == EARNING_VERDICT
        if not earned:
            reason = (f"single-axis verdict was {verdict!r}, not {EARNING_VERDICT!r} -- breadth is "
                      "EARNED per axis; combining axes that individually carry nothing is fishing "
                      "with more hooks, not discovery")
        elif asset is None:
            earned, reason = False, (
                f"passed its screen but no registry asset is named {axis!r} -- enumerating cells "
                "against data the registry cannot find would charge real trials for untestable "
                "cells")
        elif not asset.span.measured:
            earned, reason = False, (
                f"passed its screen but its span is {asset.span.status!r} on this box, so cells "
                "built from it would be NO-INPUT and still cost multiplicity")
        else:
            reason = (f"passed its own single-axis screen; registry span {asset.span.days}d "
                      f"({asset.span.first}->{asset.span.last})")
        out.append(AxisEligibility(axis=axis, earned=earned, reason=reason,
                                   single_axis_verdict=verdict))
    return out


def log_trials(plan: FusionPlan, ledger: Path | None = None) -> int:
    """Append EVERY enumerated cell to the trial ledger. Returns the number written.

    The queue's "log EVERY cell as a DSR-counted trial", made literal. Written at PLAN time, before
    a single cell is computed, because that is when the multiplicity is actually incurred -- logging
    after execution would silently omit whatever got pruned, which is the exact leak rule 2 exists
    to close. Append-only: a trial that can be un-logged is a budget that can be gamed.
    """
    ledger = ledger or (_ROOT / "data/fusion_trials.jsonl")
    if not plan.cells:
        return 0
    from datetime import UTC, datetime
    stamp = datetime.now(tz=UTC).isoformat()
    ledger.parent.mkdir(parents=True, exist_ok=True)
    with ledger.open("a", encoding="utf-8") as fh:
        for c in plan.cells:
            fh.write(json.dumps({
                "ts": stamp, "grid_hash": plan.grid_hash, "cell_id": c.cell_id,
                "axes": list(c.axes), "representation": c.representation,
                "horizon_days": c.horizon_days,
                "grid_size": plan.effective_n_trials,
                "note": "enumerated -- charged to the DSR budget whether or not it was computed",
            }) + "\n")
    return len(plan.cells)


def record_survivors(res: FusionResult, graph: Path | None = None) -> int:
    """Record surviving cells in the knowledge graph as CORRELATION-grade edges, never mechanisms.

    The graph's own rule is that an edge carries its EVIDENCE STATE so a correlation cannot quietly
    become a mechanism (``scripts/knowledge_engine.py``:13-16). A fusion survivor is the weakest
    evidence class there is -- it survived a screen inside a grid that was selected over -- so it
    lands as ``correlational`` with its grid size attached. Anything stronger would be laundering
    a search result into a claim.
    """
    graph = graph or (_ROOT / "data/knowledge_graph_edges.jsonl")
    if not res.survivors:
        return 0
    from datetime import UTC, datetime
    stamp = datetime.now(tz=UTC).isoformat()
    graph.parent.mkdir(parents=True, exist_ok=True)
    with graph.open("a", encoding="utf-8") as fh:
        for cid in res.survivors:
            fh.write(json.dumps({
                "ts": stamp, "source": "fusion_search", "edge": cid,
                "evidence_state": "correlational",
                "n_trials_when_found": res.effective_n_trials,
                "dsr_hurdle_sharpe": res.dsr_hurdle_sharpe,
                "caveat": "survived a screen inside a grid of "
                          f"{res.effective_n_trials} enumerated cells -- selection over that grid "
                          "is priced into the hurdle, and this edge is NOT a mechanism until an "
                          "independent test names the constraint that produces it",
            }) + "\n")
    return len(res.survivors)


def eligibility_from_screens(screens: Mapping[str, str]) -> list[AxisEligibility]:
    """Map ``axis -> single-axis screen verdict`` into combination eligibility.

    RULE 1 lives here. An axis with no single-axis signal cannot buy signal by being combined; the
    graveyard records several that failed alone and would otherwise be recycled as "novel" triples.
    """
    out = []
    for axis, verdict in sorted(screens.items()):
        earned = verdict == EARNING_VERDICT
        out.append(AxisEligibility(
            axis=axis, earned=earned, single_axis_verdict=verdict,
            reason=("passed its own single-axis screen" if earned else
                    f"single-axis verdict was {verdict!r}, not {EARNING_VERDICT!r} -- breadth is "
                    "EARNED per axis; combining axes that individually carry nothing is fishing "
                    "with more hooks, not discovery")))
    return out


def plan_search(eligibility: Sequence[AxisEligibility], *,
                representations: Sequence[str] = (),
                horizons: Sequence[int] = (1, 5),
                k: int = DEFAULT_K,
                max_cells: int = MAX_CELLS) -> FusionPlan:
    """Enumerate the grid, or REFUSE with a reason. Nothing is computed here."""
    reps = list(representations) or list(REPRESENTATIONS)
    unknown = [r for r in reps if r not in REPRESENTATIONS]
    if unknown:
        raise ValueError(f"unknown representation(s): {unknown}")

    earned = [e.axis for e in eligibility if e.earned]
    excluded = [e for e in eligibility if not e.earned]
    plan = FusionPlan(eligible=earned, excluded=excluded)

    if len(earned) < k:
        plan.refused_reason = (
            f"{len(earned)} axis/axes have earned breadth; a width-{k} search needs {k}. "
            "This is the designed outcome, not a bug: searching combinations of axes that failed "
            "their own single-axis screens manufactures survivors from noise. Earn an axis first.")
        return plan

    cells = [FusionCell(tuple(combo), rep, h)
             for combo in itertools.combinations(sorted(earned), k)
             for rep in sorted(reps)
             for h in sorted(horizons)]
    if len(cells) > max_cells:
        plan.refused_reason = (
            f"the grid would enumerate {len(cells)} cells (>{max_cells}). Refused on MULTIPLICITY, "
            "not compute: at that width the deflated-Sharpe hurdle exceeds anything this desk can "
            "measure, so the search could only ever return a lucky-looking cell. Narrow the axes "
            "or the representations and re-plan.")
        return plan
    plan.cells = cells
    return plan


def run_search(
    plan: FusionPlan,
    series_for: Callable[[str], np.ndarray | None],
    target_for: Callable[[int], np.ndarray | None],
    *,
    screen: Callable[..., dict[str, Any]] | None = None,
    pre_filter_fn: Callable[..., dict[str, Any]] | None = None,
) -> FusionResult:
    """Run the pre-registered grid. Every cell is accounted for, pruned or screened.

    The DSR hurdle is computed from ``plan.effective_n_trials`` -- the full enumerated grid -- so a
    cheap prune buys compute and never multiplicity, and an early hit does not shrink the bill.
    """
    res = FusionResult(grid_hash=plan.grid_hash,
                       effective_n_trials=plan.effective_n_trials,
                       refused_reason=plan.refused_reason)
    if plan.refused_reason or not plan.cells:
        return res

    # The hurdle is fixed BEFORE any cell is judged, from the grid size alone.
    try:
        from libs.validation.dsr import expected_max_sharpe
        res.dsr_hurdle_sharpe = float(expected_max_sharpe(plan.effective_n_trials, 1.0))
    except Exception:
        res.dsr_hurdle_sharpe = None

    for cell in plan.cells:
        cols = [series_for(a) for a in cell.axes]
        target = target_for(cell.horizon_days)
        if any(c is None for c in cols) or target is None:
            res.results.append(CellResult(cell.cell_id, "NO-INPUT", pruned=True,
                                          note="a constituent series or the target is unavailable"))
            continue
        build, _mech = REPRESENTATIONS[cell.representation]
        n = min(min(len(c) for c in cols if c is not None), len(target))
        sig = build([np.asarray(c)[:n] for c in cols])
        tgt = np.asarray(target)[:n]

        if pre_filter_fn is not None:
            pf = pre_filter_fn(np.sign(np.nan_to_num(sig)) * tgt, name=cell.cell_id)
            if not pf.get("pass", True):
                # STILL A TRIAL. Charged to the budget above; only compute was saved.
                res.results.append(CellResult(cell.cell_id, "PRE-FILTER-REJECT", pruned=True,
                                              note=str(pf.get("reason", ""))[:160]))
                continue
        if screen is None:
            res.results.append(CellResult(cell.cell_id, "UNSCREENED", pruned=True,
                                          note="no screen function supplied"))
            continue
        out = screen(sig, tgt, name=cell.cell_id, horizon_days=float(cell.horizon_days))
        verdict = str(out.get("verdict", "?"))
        r = CellResult(cell.cell_id, verdict,
                       ic=_maybe_float(out.get("ic")), sharpe=_maybe_float(out.get("sharpe")))
        res.results.append(r)
        if verdict == EARNING_VERDICT:
            res.survivors.append(cell.cell_id)
    return res


def _maybe_float(v: Any) -> float | None:
    try:
        return float(v)
    except (TypeError, ValueError):
        return None

```

### libs\research\slot_displacement.py
```python
"""FORWARD-SLOT DISPLACEMENT -- who leaves when a survivor arrives and all twelve clocks are full.

R0265. The desk has ADMISSION (``screen_admission.admit`` fills IDLE slots, EV-ranked) and it has
a CAP (``MAX_FORWARD_SLOTS`` = 12, the Holm ``m``). It has never had a rule for the third case,
which is the one that is live right now: ``derive_slots()`` reads ``idle_slots: 0``, twelve of
twelve occupied, so a new survivor -- exactly what the 180.8x power fix is built to produce --
has nowhere to go. ``admit()`` says so in as many words: "no idle slots: the forward stage is
saturated, which is the intended steady state and the correct reason to admit nothing."

That is the right answer only if every occupant is doing the job. Measured 2026-08-05, three of
the twelve were not:

    defi_utilisation       verdict DEGENERATE   evidence ACCRUING     1 observation
    cny_premium            verdict DEGENERATE   evidence NO-EVIDENCE  0 observations
    walcl_reserve_impulse  verdict DEGENERATE   evidence ACCRUING     1 observation

DEGENERATE is not a weak result. ``run_axis_shadows`` issues it when a clock keeps producing
dated rows that yield no usable observation, and says what it means at the point of issue: "this
is an instrument fault, NOT evidence about the hypothesis". A quarter of the desk's entire
multiplicity budget was held by clocks that cannot resolve.

NOTE WHICH FIELD LIES. Two of the three read ``evidence: ACCRUING`` -- the registry's liveness
check sees their artifact being rewritten on schedule and calls them alive. This is the desk's
own heartbeat lesson one layer up: the file is fresh, the pipe is empty. A displacement rule
keyed on the liveness field alone would have protected exactly the slots worth reclaiming, so
this module keys on the VERDICT and treats liveness as necessary, never sufficient.

WHY THIS MODULE IS NARROW, WHICH IS THE ONLY QUESTION THAT MATTERS HERE
----------------------------------------------------------------------
Displacement is optional stopping wearing a resource-allocation costume. If a challenger's
arrival can evict an incumbent, the desk can stop any test that is going badly and restart the
story elsewhere -- the garden of forking paths, at the one stage that holds promotion authority.
R0265 names this as the thing not to build: "the incumbent's kill must be on its own
pre-registered terms, not on a challenger's arrival."

So nothing here evicts a clock that is accruing. Reclamation is confined to slots that are
STRUCTURALLY UNABLE TO RESOLVE -- a broken instrument holds a slot the way a jammed turnstile
holds a doorway, and opening it is not a judgement about anybody's hypothesis.

TWO INVARIANTS, BOTH ENFORCED IN CODE AND PINNED BY TESTS
--------------------------------------------------------
1. COUNT-NEUTRAL. One out, one in: ``m_concurrent`` is unchanged by any plan this module
   produces, so not one Holm bar moves in either direction. Displacement can never be a route to
   a looser bar, because it never changes the number the bar is computed from.
2. NO HEALTHY EVICTION. A slot that is accruing real observations is PROTECTED and cannot appear
   in ``displaced``, whatever a challenger looks like.

THE RECLAIMED HYPOTHESIS IS FILED BY ITS MECHANISM OF DEATH, AND THERE ARE TWO
-----------------------------------------------------------------------------
A DEGENERATE clock has told the desk nothing about its axis. Retiring it as REFUTED would file a
data-availability exclusion under a false mechanism of death and corrupt the family survival
statistics that steer future search (L1.17) -- the identical error ``stratified_campaign_gates``
already refuses to make with untested candidates. Instrument-fault reclamations therefore carry
``requeue_as: UNTESTED``, and the fault is named so the axis is re-run rather than re-argued.

A clock carrying ``FAILING FORWARD -> kill`` is the opposite case and gets ``REFUTED``. It reached
the decision point IT pre-registered and lost there, so the desk holds real evidence about the
hypothesis, and re-queueing it as untested would guarantee paying to rediscover a dead axis
forever. Both labels are wrong in opposite directions if swapped, which is why the mechanism of
death travels with the reclamation instead of being defaulted (see ``_requeue_for``).

THAT ROUTE IS WHY THE FIVE KILL VERDICTS WERE INERT. ``forward_verdict()`` is shared by five
shadow runners and each writes its string into ``web/<sleeve>_shadow.json``; ``derive_slots`` read
those artifacts for ``forward_days`` and ``updated`` and dropped the verdict, so every sleeve slot
arrived here carrying ``state="since <date>"`` -- a birth date, never an outcome. The classifier
could not see a kill because no kill was ever in the row. Axis rows always carried theirs, which
is exactly why the axis half of the cohort was reclaimable and the sleeve half was not.

WHAT THIS DOES NOT DO. It does not displace a healthy incumbent on a paired comparison -- the
Shadow-Before-Swap half of R0265. That needs the incumbent's pre-registered decision point to
exist as a readable field before a challenger can be scored against it on the same labels, and
until it does, a paired test would be scored against a horizon nobody wrote down.
``libs/signal_engine/champion_challenger.py`` is NOT that mechanism and must not be mistaken for
it: it differences two absolute Sharpes measured over each variant's own window, which is the
period-effect confound R0265 exists to avoid.

Pure stdlib. Import from ``libs.research.slot_displacement``.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

__all__ = [
    "BLOCKED",
    "PROTECTED",
    "RECLAIMABLE",
    "REQUEUE_REFUTED",
    "REQUEUE_UNTESTED",
    "Displacement",
    "DisplacementPlan",
    "at_decision_point",
    "classify_slot",
    "plan_displacement",
]

#: The slot is doing its job. Only its own pre-registered terms may end it.
PROTECTED = "PROTECTED"
#: The slot cannot resolve however long it runs -- a broken instrument, not a weak effect.
RECLAIMABLE = "RECLAIMABLE"
#: The slot cannot be assessed. Deliberately NOT reclaimable: see `classify_slot`.
BLOCKED = "BLOCKED-UNMEASURED"

#: Verdicts that mean the INSTRUMENT failed, so the clock can never produce a resolvable statistic.
#: Sourced from `run_axis_shadows`, which already draws this distinction and states it plainly at
#: the point of issue. Kept as a set rather than a substring test so that a future verdict has to
#: be added here deliberately -- a slot becoming reclaimable is a decision, never a spelling.
_INSTRUMENT_FAULT_VERDICTS = frozenset({"DEGENERATE"})

#: The clock reached ITS OWN pre-registered kill. `forward_verdict()` issues this when forward
#: Sharpe is negative, and it is the ONE reclamation that is not a judgement call by a challenger:
#: the incumbent ended on the terms it registered before the data arrived, which is exactly the
#: condition R0265 requires ("the incumbent's kill must be on its own pre-registered terms, not on
#: a challenger's arrival"). Matched as a prefix because the verdict carries its statistics inline
#: ("FAILING FORWARD -> kill candidate (Sharpe -0.42 on 61 observations, t=-1.83)").
_PREREGISTERED_KILL_PREFIX = "FAILING FORWARD"

#: Distinct from RECLAIMABLE's default because the mechanism of death is DIFFERENT and L1.17 turns
#: on that difference. A DEGENERATE clock measured nothing, so its hypothesis returns UNTESTED. A
#: FAILING-FORWARD clock was tested and lost, so it returns REFUTED -- and filing a refutation as
#: untested would re-open dead ground forever, while filing an instrument fault as a refutation
#: would retire live ground on a false death. Both errors corrupt family survival statistics; they
#: just corrupt them in opposite directions.
REQUEUE_REFUTED = "REFUTED"
REQUEUE_UNTESTED = "UNTESTED"

#: Evidence labels the registry publishes when it cannot see whether a clock is breathing.
_UNMEASURABLE_EVIDENCE = frozenset({"UNMEASURED"})

# A named source that no longer carries the exact pre-registered identity is not an unknown
# observation. It is a measured inability to accrue another observation. Keeping it in BLOCKED
# forever strands the seat and cannot preserve evidence, because there is no producer left.
_TERMINAL_SOURCE_EVIDENCE = frozenset({"SOURCE-GONE"})


@dataclass(frozen=True)
class Displacement:
    """One reclaimed slot and the challenger taking it."""

    slot: str
    challenger: str
    why: str
    requeue_as: str = REQUEUE_UNTESTED
    """How the OUTGOING hypothesis is recorded, and it is derived, never assumed.

    UNTESTED is the DEFAULT and the safe error for every route except one: a broken instrument
    measured nothing, and filing that as a refutation retires live research ground on a false
    death. REFUTED is set only for a clock that reached its own pre-registered kill, where the
    desk genuinely does hold evidence against the hypothesis and calling it untested would buy
    the same dead axis again. See ``_requeue_for``."""


@dataclass(frozen=True)
class DisplacementPlan:
    displaced: tuple[Displacement, ...] = ()
    protected: tuple[str, ...] = ()
    blocked: tuple[str, ...] = ()
    waiting: tuple[str, ...] = ()
    m_before: int = 0
    m_after: int = 0
    notes: tuple[str, ...] = field(default_factory=tuple)

    @property
    def count_neutral(self) -> bool:
        """The load-bearing invariant: a displacement never changes the Holm cohort size."""
        return self.m_before == self.m_after


def classify_slot(slot: dict[str, Any]) -> tuple[str, str]:
    """Return ``(state, why)`` for one row of ``derive_slots()["slots"]``.

    The ordering of these branches is the whole safety argument, so it is spelled out rather than
    collapsed into a single expression:

    * An INSTRUMENT FAULT is checked FIRST and on the verdict, because two of the three live
      faults publish ``evidence: ACCRUING``. Liveness is necessary for a clock to be healthy and
      nowhere near sufficient -- the artifact was being rewritten daily in every one of those
      cases while yielding nothing usable.
    * UNMEASURED is NOT reclaimable, which is the one place this module is deliberately less
      aggressive than L1.28a's "unmeasured utilisation counts as zero" would suggest. The
      asymmetry is real and it is not timidity: wrongly reclaiming destroys forward evidence that
      cannot be re-earned at any price, while wrongly protecting costs a queue position. An
      unmeasurable slot is a MEASUREMENT defect to fix upstream, and it is surfaced as one.
    * Everything else with at least one real observation is PROTECTED.
    """
    name = str(slot.get("name", "?"))
    # `state` for an axis row IS its verdict; for a sleeve row it is a birth date and the verdict
    # arrives in its own field. Read both so one classifier serves both halves of the cohort --
    # the sleeve half was unreachable while only `state` was consulted.
    verdict = str(slot.get("state", "") or "")
    outcome = str(slot.get("verdict", "") or "") or verdict
    evidence = str(slot.get("evidence", "") or "")
    days = slot.get("days")
    obs = int(days) if isinstance(days, (int, float)) else None

    # CHECKED BEFORE EVERYTHING, INCLUDING THE INSTRUMENT FAULT. A clock that reached its own
    # pre-registered kill has the strongest possible claim to its seat being free, and it is the
    # only branch here whose reclamation carries a REFUTATION rather than a re-queue. Ordering it
    # first also means a killed clock is never mislabelled by a later, weaker branch.
    if outcome.upper().startswith(_PREREGISTERED_KILL_PREFIX):
        return RECLAIMABLE, (
            f"{name}: {outcome} -- this clock reached the decision point IT pre-registered and "
            "FAILED there. Reclaiming it is not optional stopping and not a challenger's "
            "judgement: the terms were fixed before the data arrived, which is the one condition "
            "under which ending an incumbent cannot be a garden-of-forking-paths move")

    if verdict in _INSTRUMENT_FAULT_VERDICTS:
        return RECLAIMABLE, (
            f"{name}: verdict {verdict} -- the instrument failed, so this clock cannot resolve "
            f"however long it runs. It publishes evidence={evidence!r}, which is why a liveness "
            "check protects it and a verdict check does not")
    if evidence in _TERMINAL_SOURCE_EVIDENCE:
        return RECLAIMABLE, (
            f"{name}: evidence {evidence} -- the exact pre-registered source identity is absent, "
            "so this clock cannot accrue another observation. Retire the clock as UNTESTED and "
            "preserve its history; never reinterpret the missing source as a zero return")
    if evidence in _UNMEASURABLE_EVIDENCE:
        return BLOCKED, (
            f"{name}: evidence UNMEASURED -- whether this clock is alive is unknown, and a slot "
            "nobody can see is not a slot anybody may take. Fix the measurement, then re-run")
    if obs == 0:
        return RECLAIMABLE, (
            f"{name}: {evidence} with zero observations accrued -- it has spent its opportunities "
            "and converted none of them, so there is no sample here to protect")
    if obs is None:
        return BLOCKED, (
            f"{name}: no observation count published, so this slot cannot be judged either way")
    _reached, terms = at_decision_point(slot)
    return PROTECTED, (
        f"{name}: accruing on {obs} observation(s) -- ends on its own pre-registered terms, never "
        f"on a challenger's arrival ({terms})")


def at_decision_point(slot: dict[str, Any]) -> tuple[bool | None, str]:
    """Has this incumbent reached the decision point IT pre-registered? R0430's prerequisite.

    THE FIELD THIS READS DID NOT EXIST UNTIL NOW, WHICH IS WHY SHADOW-BEFORE-SWAP COULD NOT BE
    BUILT. `classify_slot` has always protected a healthy incumbent because it "ends on its own
    pre-registered terms" -- a sentence pinned by a test with nothing behind it. A paired
    challenger scored against an incumbent whose horizon was never written down is optional
    stopping with extra steps: whoever runs the comparison picks the moment, and picking the
    moment is the entire bias.

    THREE-VALUED, AND THE THIRD VALUE IS THE SAFE ONE. ``None`` means the slot declares no
    decision point, and it must never collapse into ``False`` OR ``True``: "not yet" and "we
    never wrote one down" demand opposite repairs, and only the second is a wiring defect. A
    caller may act on ``True`` alone; every other value leaves the incumbent alone.

    IT GRANTS NO AUTHORITY AND MOVES NOTHING. Reaching a decision point means a decision may
    legitimately be TAKEN, not that the incumbent loses. The paired comparison that would use
    this -- warm-refit challenger, identical labels, fixed paired advantage -- remains unbuilt on
    purpose, and `plan_displacement` is deliberately unchanged: a healthy incumbent is still
    never displaced, at any observation count. This function only makes the question answerable.
    """
    name = str(slot.get("name", "?"))
    point = slot.get("decision_at_obs")
    if not isinstance(point, int) or isinstance(point, bool) or point <= 0:
        return None, (
            f"{name} declares no pre-registered decision point, so no horizon exists to have "
            "been reached -- an incumbent cannot be paired against a bar nobody wrote down")
    days = slot.get("days")
    obs = int(days) if isinstance(days, (int, float)) and not isinstance(days, bool) else None
    if obs is None:
        return None, (
            f"{name} pre-registered a decision at {point} observation(s) but publishes no "
            "observation count, so progress toward it is UNMEASURED")
    if obs >= point:
        return True, (
            f"{name} reached its pre-registered decision point: {obs}/{point} observation(s). A "
            "decision may be TAKEN on its own terms -- this is not itself a verdict")
    return False, (
        f"{name} is {point - obs} observation(s) short of its pre-registered decision point "
        f"({obs}/{point}) -- its own terms have not yet allowed a decision")


def _requeue_for(slot: dict[str, Any]) -> str:
    """How the OUTGOING hypothesis is filed. REFUTED only when the clock was actually tested.

    L1.17 turns on this distinction: family survival statistics steer future search, so filing an
    unmeasured axis as REFUTED retires live ground on a false death, and filing a genuinely
    refuted one as UNTESTED guarantees the desk pays to rediscover it. The default stays UNTESTED
    because that is the safe error for every reclamation route EXCEPT the pre-registered kill --
    which is the only one carrying evidence about the hypothesis rather than about the instrument.
    """
    outcome = str(slot.get("verdict", "") or slot.get("state", "") or "")
    if outcome.upper().startswith(_PREREGISTERED_KILL_PREFIX):
        return REQUEUE_REFUTED
    return REQUEUE_UNTESTED


def plan_displacement(slots: list[dict[str, Any]], challengers: list[dict[str, Any]],
                      *, cap: int) -> DisplacementPlan:
    """Match challengers to slots that cannot resolve. Never touches a slot that can.

    ``slots`` is ``derive_slots()["slots"]``. ``challengers`` are candidate dicts carrying at
    least ``name``, plus ``runway``: how much room the edge has before the book outgrows it, in
    whatever unit the caller uses consistently -- ``capacity_policy.growth_runway`` (multiples of
    the current book) and ``run_promotion_queue``'s ``runway_days`` are both valid, and only the
    ordering is read. Smaller means expiring sooner.

    THE ORDER IS EXPIRY, SHORTEST RUNWAY FIRST (L1.18a). A long-runway edge loses nothing by
    waiting and a short-runway one loses everything, so ranking the queue by anything else --
    including by how good the edge looks -- spends the scarce slot on the candidate least damaged
    by not getting it. A challenger with no declared runway sorts last rather than first: an
    unmeasured runway is not an urgent one, and letting it jump the queue would make declaring
    nothing the fastest way in.
    """
    # AN EMPTY COHORT IS UNMEASURED, NOT WIDE OPEN (L1.57). `derive_slots` builds from hardcoded
    # standing and derivative names, so it cannot legitimately return zero slots -- an empty list
    # means the registry failed to read, and treating that as `cap` free seats would hand every
    # challenger a clock on the strength of a failure. A verdict computed over nothing is vacuous
    # however honest its arithmetic.
    if not slots:
        return DisplacementPlan(
            waiting=tuple(str(c.get("name", "?")) for c in challengers),
            m_before=0, m_after=0,
            notes=("UNMEASURED: the slot cohort is empty, which the registry cannot produce "
                   "legitimately -- it is built from hardcoded standing and derivative names. "
                   "Treating this as free capacity would admit challengers on the strength of a "
                   "read failure, so nothing is placed until the registry is readable",))

    states = [(s, *classify_slot(s)) for s in slots]
    # The mechanism of death travels with the reclamation, because the requeue label is derived
    # from it and the two are not interchangeable (see REQUEUE_REFUTED).
    reclaimable = [(str(s.get("name", "?")), why, _requeue_for(s))
                   for s, st, why in states if st == RECLAIMABLE]
    protected = tuple(str(s.get("name", "?")) for s, st, _ in states if st == PROTECTED)
    blocked_rows = [(str(s.get("name", "?")), why) for s, st, why in states if st == BLOCKED]

    # Idle slots are ADMISSION's job, not this module's -- it is only ever asked what to do when
    # there is nothing idle left. Counting them here would double-fill the same slot.
    idle = max(0, int(cap) - len(slots))

    ranked = sorted(
        challengers,
        key=lambda c: (float(c["runway"]) if isinstance(c.get("runway"), (int, float))
                       else float("inf")))
    # Idle slots come first and cost no displacement: taking a free seat is not an eviction.
    take_free = ranked[:idle]
    rest = ranked[idle:]

    pairs = [
        Displacement(slot=slot_name, challenger=str(c.get("name", "?")),
                     why=f"{why}; replaced by {c.get('name', '?')} "
                         f"(runway {c.get('runway', 'UNMEASURED')})",
                     requeue_as=requeue)
        for (slot_name, why, requeue), c in zip(reclaimable, rest, strict=False)
    ]
    waiting = tuple(str(c.get("name", "?")) for c in rest[len(pairs):])

    m_before = len(slots)
    # ONE OUT, ONE IN. Reclamations are matched 1:1 with challengers, so the cohort size moves
    # only by however many genuinely idle seats were filled -- never by a displacement. This is
    # computed rather than asserted so the arithmetic is visible in the artifact.
    m_after = m_before + len(take_free)

    notes = [
        f"{len(reclaimable)} of {m_before} slot(s) cannot resolve and are reclaimable; "
        f"{len(protected)} accruing and PROTECTED",
        "count-neutral by construction: a displacement swaps one clock for one clock, so "
        f"m stays {m_before if not take_free else f'{m_before}->{m_after}'} and no Holm bar moves",
    ]
    if blocked_rows:
        notes.append(
            f"{len(blocked_rows)} slot(s) UNMEASURED and therefore NOT reclaimed -- wrongly "
            "evicting destroys forward evidence that cannot be re-earned, while wrongly keeping "
            "costs a queue position. This is a measurement defect upstream, not a displacement "
            "decision: " + "; ".join(n for n, _ in blocked_rows))
    if waiting:
        notes.append(
            f"{len(waiting)} challenger(s) still WAITING with no reclaimable slot -- the forward "
            "stage is genuinely saturated by clocks that are all doing their job, which is the "
            "one case where waiting is the correct answer")
    if pairs:
        notes.append(
            "outgoing hypotheses requeue as UNTESTED, never REFUTED: a broken instrument "
            "measured nothing, and recording it as a refutation would retire live research "
            "ground on a false mechanism of death (L1.17)")
    if not reclaimable and not waiting and not challengers:
        notes.append("no challengers offered -- nothing to place")

    return DisplacementPlan(
        displaced=tuple(pairs), protected=protected,
        blocked=tuple(n for n, _ in blocked_rows), waiting=waiting,
        m_before=m_before, m_after=m_after, notes=tuple(notes))

```

### libs\research_os\__init__.py
```python

```

### libs\testing\__init__.py
```python

```

### scripts\check_desk_cycles.py
```python
"""Watch the GATES and the LOCAL CYCLES, and correct them in the same pass.

WHY THIS EXISTS

Every defect this desk lost days to in the last week was something a person had to notice:

  * the gate policy on the desk box was the pre-YAML loader while the spec beside it was current,
    so the box certified with non-canonical code and nothing said so;
  * the power-cure lane admitted exactly ONE family by a hardcoded whitelist, so 506 cells that
    cleared every validity gate could never gather the forward evidence their failing gate is
    declared curable by;
  * the unified dig was cut off after 10,667 bytes and the resume gate, scoring bytes, called it
    finished -- so it never resumed that day;
  * three cron jobs had never run once, and the absence of their log files was the only evidence.

None of those are subtle once measured. They were invisible because nothing measured them. This
checks each one every few minutes and ACTS: a stale cycle is restarted, a drifted module is
re-shipped, a missing cure lane is re-run. Reporting alone is what let them stand for days.

WHAT IT WILL NOT DO. It never edits a threshold, never rewrites a gate, and never promotes
anything. Gate DRIFT is healed by re-shipping what HEAD already says; gate CONTENT is the
principal's. A watchdog that could change the bar it enforces is not a watchdog.
"""
from __future__ import annotations

import json
import subprocess
import sys
from contextlib import suppress
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DESK = ROOT / "desks" / "mt5"
OUT = ROOT / "data" / "desk_cycles.json"
REMOTE = "contabo-mt5"

#: The canonical ten, in canonical order. Hardcoded ON PURPOSE: this is the invariant being
#: checked, so reading it from the same file it validates would make the check vacuous.
CANONICAL_GATES = (
    "economic_prior", "in_sample_screen", "deflated_sharpe", "pbo", "reality_check_spa",
    "cpcv", "walk_forward", "stress_costs", "lockbox", "expected_value",
)
CANONICAL_VALIDITY = {"economic_prior", "pbo", "reality_check_spa", "stress_costs", "lockbox"}
CANONICAL_POWER = {"in_sample_screen", "deflated_sharpe", "cpcv", "walk_forward",
                   "expected_value"}

#: Daily cycles and the systemd unit that runs each. A cycle absent from here is a cycle nobody
#: is watching, which is how the unified dig went a day without resuming.
DAILY_CYCLES = {
    "frontier_unified": "quant-seat-frontier.service",
    "brain_hunter": "quant-seat-frontier.service",
    "litminer": "quant-seat-litminer.service",
    "dataaxis": "quant-seat-dataaxis.service",
    "prospector": "quant-seat-prospector.service",
}

#: Files whose family-routing must never be narrowed to a whitelist again.
NO_WHITELIST_FILES = (
    "desks/mt5/research/shadow_admission.py",
    "desks/mt5/side_channels/run_external_backtest.py",
)


def _read(p: Path):
    try:
        return json.loads(p.read_text("utf-8"))
    except (OSError, ValueError):
        return None


def _run(cmd: list[str], timeout: int = 240) -> tuple[int, str]:
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, check=False)
        return r.returncode, ((r.stdout or "") + (r.stderr or "")).strip()[-300:]
    except (subprocess.TimeoutExpired, OSError) as exc:
        return 124, f"{type(exc).__name__}"


def check_gates(now: datetime) -> tuple[list[str], list[str]]:
    """The ten gates, their classification, and that both boxes run the same policy."""
    breaches: list[str] = []
    fixes: list[str] = []

    spec = None
    try:
        import yaml
        spec = yaml.safe_load((DESK / "policy" / "gate_spec.yaml").read_text("utf-8"))
    except Exception as exc:
        breaches.append(f"GATE-SPEC unreadable ({type(exc).__name__}) -- the policy cannot be "
                        f"verified, so nothing downstream can claim it was applied")
        return breaches, fixes

    names = tuple(g.get("name") for g in (spec.get("gates") or []))
    if names != CANONICAL_GATES:
        breaches.append(f"GATE-SET CHANGED: spec lists {list(names)}, canon is "
                        f"{list(CANONICAL_GATES)} -- the ten-gate policy is not what it claims")
    cls = {g.get("name"): g.get("classification") for g in (spec.get("gates") or [])}
    got_validity = {n for n, c in cls.items() if c == "validity"}
    got_power = {n for n, c in cls.items() if c == "power"}
    if got_validity != CANONICAL_VALIDITY or got_power != CANONICAL_POWER:
        breaches.append(
            f"GATE-CLASSIFICATION CHANGED: validity={sorted(got_validity)} "
            f"power={sorted(got_power)}. Which gates are curable decides what may gather forward "
            f"evidence, so this silently moves the promotion firewall")

    # Both boxes must run the SAME policy. Drift here means the desk certifies with code that is
    # not the code that was reviewed -- healed by re-shipping HEAD, never by editing.
    rc, out = _run([sys.executable, str(ROOT / "scripts" / "check_desk_module_drift.py")], 600)
    if rc == 1 and "healed" in out:
        fixes.append(f"MODULE-DRIFT healed: {out.splitlines()[-1][:160]}")
    elif rc not in (0, 1):
        breaches.append(f"MODULE-DRIFT check failed (rc={rc}) -- cannot confirm the desk box "
                        f"runs the reviewed gate code")
    return breaches, fixes


def check_no_family_whitelist() -> list[str]:
    """No routing file may narrow the hunt to a named set of families.

    Twice now a hardcoded family list has hidden whole mechanism classes: the external backtest
    door reached 8 of 43 families, and the power-cure lane admitted 1. Both looked healthy from
    every count that mattered, because the excluded families simply never appeared.
    """
    breaches: list[str] = []
    needles = ("session_range_breakout\"}", "'session_range_breakout'}")
    for rel in NO_WHITELIST_FILES:
        p = ROOT / rel
        if not p.exists():
            continue
        text = p.read_text("utf-8")
        for line_no, line in enumerate(text.splitlines(), 1):
            stripped = line.strip()
            if stripped.startswith("#"):
                continue
            if "not in {" in stripped and any(n in stripped for n in needles):
                breaches.append(
                    f"FAMILY WHITELIST reintroduced at {rel}:{line_no} -- "
                    f"{stripped[:90]}. A door only one family can walk through cannot "
                    f"diversify a book, and diversification is the binding constraint")
    return breaches


def check_cycles(now: datetime) -> tuple[list[str], list[str]]:
    """Did each daily cycle run today, and was it CUT OFF rather than finished?"""
    breaches: list[str] = []
    fixes: list[str] = []
    today = now.strftime("%Y%m%d")
    logs = ROOT / "data" / "cro_ai_logs"

    for cycle, unit in DAILY_CYCLES.items():
        sentinel = ROOT / "data" / ".digs" / f"{cycle.replace('frontier_', '')}_{today}.running"
        todays = sorted(logs.glob(f"{cycle}_{today}T*.log"))
        # A sentinel left behind means the dig died mid-run: it is written at start and removed
        # only on a clean return, so its presence needs no cooperation from the dead process.
        if sentinel.exists():
            rc, _ = _run(["systemctl", "--user", "start", unit], 60)
            fixes.append(f"CYCLE {cycle}: cut off mid-run (sentinel present) -- restarted {unit} "
                         f"(rc={rc}); it resumes from where it stopped")
            continue
        if not todays:
            # Before ~06:00 UTC the daily seats have not fired yet; that is not staleness.
            if now.hour >= 9:
                rc, _ = _run(["systemctl", "--user", "start", unit], 60)
                fixes.append(f"CYCLE {cycle}: no run at all today and it is "
                             f"{now.strftime('%H:%M')}Z -- started {unit} (rc={rc})")
            continue
        newest = todays[-1]
        if "exit" not in newest.read_text("utf-8", errors="ignore")[-4000:]:
            rc, _ = _run(["systemctl", "--user", "start", unit], 60)
            fixes.append(f"CYCLE {cycle}: today's log has no completion marker -- restarted "
                         f"{unit} (rc={rc}). Bytes are not completion")
    return breaches, fixes


def check_cure_lane(now: datetime) -> tuple[list[str], list[str]]:
    """If the sweep found validity-pass cells, the cure lane must be publishing them."""
    breaches: list[str] = []
    fixes: list[str] = []
    gates = _read(DESK / "reports" / "universal_gates_external.json")
    if not gates:
        return breaches, fixes
    judged = [v for v in (gates.get("verdicts") or []) if (v.get("stages") or {})]
    eligible = 0
    for v in judged:
        st = v["stages"]
        if v.get("passed"):
            continue
        if not all(isinstance(st.get(g), dict) and st[g].get("passed") is True
                   for g in CANONICAL_VALIDITY):
            continue
        if any(not (isinstance(st.get(g), dict) and st[g].get("passed") is True)
               for g in CANONICAL_POWER):
            eligible += 1
    if not eligible:
        return breaches, fixes
    cure = _read(DESK / "reports" / "POWER_CURE_CANDIDATES.json")
    if not cure:
        breaches.append(
            f"CURE LANE DARK: {eligible} cell(s) cleared every validity gate and failed only "
            f"curable ones, and POWER_CURE_CANDIDATES.json does not exist. The cure the policy "
            f"promises is unreachable, which makes it a wish rather than a rule")
    elif not (cure.get("candidates") or {}):
        breaches.append(
            f"CURE LANE EMPTY: {eligible} eligible cell(s) in the gate report but the cure "
            f"artifact lists none -- the two disagree and the artifact is what admission reads")
    if breaches:
        # THE FIXER: the artifact is written BY the sweep, so the repair is to run one. Only the
        # gauntlet may produce it -- this never writes the file itself, because a cure candidate
        # invented outside the gate run is a candidate nobody gated.
        rc, _ = _run(["ssh", "-o", "ConnectTimeout=25", "contabo-mt5",
                      "powershell -Command \"schtasks /Run /TN MT5-Gauntlet\""], 90)
        fixes.append(f"CURE LANE: triggered MT5-Gauntlet (rc={rc}) so the sweep publishes "
                     f"POWER_CURE_CANDIDATES.json for the {eligible} eligible cell(s)")
    return breaches, fixes



def check_hourly_coverage(now: datetime) -> tuple[list[str], list[str]]:
    """EVERY HOUR: every gate run, every hypothesis tested, the bar unmoved.

    Standing instruction from the principal (2026-08-29): all gates tested, all hypotheses
    tested, certificates flowing, every hour -- and the bar is FIXED. It never raises and it
    never gets harsher. This is the organ that makes that a rule rather than an intention.

    Each breach here has a fixer, because a report that waits for a human is how the desk lost
    three days to a paused gateway nobody read.
    """
    breaches: list[str] = []
    fixes: list[str] = []
    rep = _read(DESK / "reports" / "universal_gates_external.json")
    if not rep:
        return breaches, fixes

    # ---- THE BAR IS FIXED. Checked first: everything below is meaningless if the bar moved.
    basis = str(rep.get("trial_count_basis") or "")
    trials = rep.get("n_trials")
    if not basis.startswith("fixed_campaign_trials"):
        breaches.append(
            f"BAR MOVED: the last sweep charged trials on basis '{basis[:70]}' with "
            f"n_trials={trials}. The bar is fixed and never gets harsher -- a sweep-scaled "
            f"charge means a candidate is judged against how many others shared its hour. "
            f"The desk box is running a gate_policy that is not canon.")
        rc, out = _run([sys.executable, str(ROOT / "scripts" / "check_desk_module_drift.py")], 600)
        detail = out.splitlines()[-1][:90] if out else ""
        fixes.append(f"BAR: re-shipped canonical gate policy (rc={rc}) {detail}")

    # ---- EVERY HOUR. A sweep older than 90 minutes has missed its slot.
    age_h = None
    with suppress(TypeError, ValueError):
        age_h = (now - datetime.fromisoformat(str(rep.get("swept_at")))).total_seconds() / 3600.0
    if age_h is not None and age_h > 1.5:
        rc, _ = _run(["ssh", "-o", "ConnectTimeout=25", REMOTE,
                      'powershell -Command "schtasks /Run /TN MT5-Gauntlet"'], 90)
        fixes.append(f"HOURLY: last sweep {age_h:.1f}h old -- triggered MT5-Gauntlet (rc={rc})")

    # ---- EVERY HYPOTHESIS TESTED. Cells deferred by the build budget are work not yet done,
    # and the cure is a warmer cache, not a longer sweep: a cached cell costs nothing to judge,
    # so once the cache is full EVERY hypothesis is tested every hour at cache-hit speed.
    deferred = int(rep.get("n_cells_deferred_build_budget") or 0)
    if deferred:
        rc, _ = _run(["ssh", "-o", "ConnectTimeout=25", REMOTE,
                      'powershell -Command "schtasks /Run /TN MT5-CacheWarm"'], 90)
        fixes.append(f"COVERAGE: {deferred} hypothesis(es) deferred by the build budget -- "
                     f"triggered MT5-CacheWarm (rc={rc}); a cached cell is judged for free, so "
                     f"filling the cache is what makes 'every hypothesis, every hour' true")

    # ---- EVERY GATE RUN. A judged cell must carry all ten stages. A subset is not a verdict
    # under this policy, and a cell judged on nine gates has passed nothing.
    # TERMINAL STATES ARE EXEMPT, and getting this wrong is how a watchdog cries wolf. The gates
    # are SEQUENTIAL: a cell rejected at the economic prior carries that one stage and no others,
    # deliberately, because the policy reserves downstream compute for candidates still capable of
    # passing. A cell that never reached 60 daily observations carries only `observations` and is
    # UNMEASURED, which this desk's law calls a real answer rather than a failure.
    # Measured 2026-08-29 on the first run of this check: 1,116 of 3,101 flagged, and every one
    # was one of those two states -- 816 gate-1 rejects and 300 unmeasured. Nothing was wrong.
    # The real defect this looks for is a cell that ADVANCED into the battery and came back with
    # a subset: that would be a verdict built on gates nobody ran.
    judged = [v for v in (rep.get("verdicts") or []) if (v.get("stages") or {})]
    reached_battery = [
        v for v in judged
        if (v.get("stages") or {}).get("economic_prior", {}).get("passed") is True
        and (v.get("stages") or {}).get("observations", {}).get("passed") is not False
        and len(v.get("stages") or {}) > 1
    ]
    partial = [v for v in reached_battery
               if not set(CANONICAL_GATES) <= set(v.get("stages") or {})]
    if partial:
        example = partial[0]
        missing = sorted(set(CANONICAL_GATES) - set(example.get("stages") or {}))
        breaches.append(
            f"PARTIAL GATE SET: {len(partial)} of {len(reached_battery)} cell(s) that ADVANCED "
            f"into the battery carry fewer than ten stages (e.g. {example.get('sym')} missing "
            f"{missing}). A verdict built on gates nobody ran is not a verdict.")
    return breaches, fixes


def main() -> int:
    now = datetime.now(tz=UTC)
    breaches: list[str] = []
    fixes: list[str] = []

    gb, gf = check_gates(now)
    breaches += gb
    fixes += gf
    breaches += check_no_family_whitelist()
    cb, cf = check_cycles(now)
    breaches += cb
    fixes += cf
    lb, lf = check_cure_lane(now)
    breaches += lb
    fixes += lf
    hb, hf = check_hourly_coverage(now)
    breaches += hb
    fixes += hf

    report = {
        "checked_at": now.isoformat(timespec="seconds"),
        "breaches": breaches,
        "fixes_applied": fixes,
    }
    OUT.write_text(json.dumps(report, indent=1), "utf-8")

    if fixes:
        print(f"DESK CYCLES -- {len(fixes)} correction(s) applied {now.isoformat(timespec='seconds')}")
        for f in fixes:
            print(f"  FIXED  {f}")
    if breaches:
        print(f"DESK CYCLES BREACH {now.isoformat(timespec='seconds')}")
        for b in breaches:
            print(f"  - {b}")
        return 1
    if not fixes:
        print(f"desk cycles: gates canonical, no family whitelist, cycles current "
              f"({now.isoformat(timespec='seconds')})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

```

### scripts\check_timidity_language.py
```python
"""TIMIDITY FENCE (L1.28) -- every restraint in the constitution declares which KIND it is.

THE DEFECT THIS EXISTS FOR. Roughly two thirds of this constitution's principles contain restraint
language -- minimise, reject, only, never, discipline, bounded, narrow, scarce. Each is correct in
its own context, and each is misreadable by a language model as a general licence to do less. The
misreading is systematic rather than occasional: it yields smaller changes, deferred subsystems,
proposals instead of builds, "conservative versions". It is silent, and it looks like good
judgement, which is why it needs a fence rather than an intention.

WHAT IT CHECKS, and the design choice that keeps it from becoming noise. A naive keyword scan flags
32 of 44 principles -- including the aggressive ones, where "never" means "never rank a small edge
down". A fence that fires on healthy text gets acknowledged into silence, which is the failure mode
`check_orphan_code` already taught this desk. So the rule is CLASSIFICATION, not absence:

  every principle containing scope-restraint language must be EITHER
    (a) named in L1.28's disambiguation table, which states its correct non-timid reading, OR
    (b) declared EVIDENCE/RISK restraint -- a bar on what may be believed or what capital may be
        exposed to, which L1.21a/L1.28 explicitly do NOT loosen, OR
    (c) carrying its own anti-timidity sentence inline.

An unclassified restraint is the defect, because in practice it defaults to the timid reading.

DIRECTION OF FAILURE, chosen deliberately: a NEW principle is guilty until classified. Adding one
row to the L1.28 table is a minute of work; a principle that quietly teaches every organ to do less
costs forward compounding that is never recovered and never itemised.

    python scripts/check_timidity_language.py [--json] [--report-only]
"""

from __future__ import annotations

import argparse
import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parent.parent
_CONST = _ROOT / "docs/CONSTITUTION.md"
_OUT = _ROOT / "data/timidity_audit.json"

# Words that, read out of context by a model, license doing less. Deliberately broad: the fence
# does not decide whether restraint is PRESENT, it decides whether it has been CLASSIFIED.
_SCOPE_RESTRAINT = (
    "minimise", "minimize", "ruthless", "reject", "avoid", "restrict", "conservat", "cautio",
    "discipline", "narrow", "bounded", "defer", "wait", "restraint", "prudent", "scarce",
    "sparingly", "limit", "smallest", "fewer", "less ", "slow",
)

# Principles that are EVIDENCE/RISK restraint: bars on belief and on capital exposure. These are
# absolute, are NOT loosened by L1.21a/L1.28, and need no anti-timidity rider -- rigour here is
# what makes aggression elsewhere survivable. Each is listed with why it qualifies.
_EVIDENCE_RESTRAINT: dict[str, str] = {
    "L1.6": "statistical validation -- the confirmation bar and the two-stage law",
    "L1.7": "adversarial validation -- every success triggers disproof attempts",
    "L1.23": "the survival rails -- ruin probability and Tier-3 isolation",
    "L1.3": "no proxy becomes a god -- a bar on what a number is allowed to mean",
    "L1.4": "reality anchoring -- forward evidence outranks historical",
    "L2.8a": "the immutable core, including the rule that it is immutable",
    "L2.0": "the ratchet fence -- floors only rise",
    "L2.2": "mechanical fences -- the enforcement layer itself",
    "L2.4": "artifact over claim -- a bar on claiming a capability exists",
    "L2.10": "reality gap detection -- measures the backtest-to-live chain",
}

# Clauses where a restraint WORD appears inside an explicitly AGGRESSIVE instruction. These are
# the fence's false positives, and each is retired by QUOTING the phrase that proves it -- a
# blanket exemption list would be indistinguishable from muting the check, which is how a fence
# dies. If any quoted phrase ever stops matching, the clause was rewritten and re-classifies.
_AGGRESSIVE_CONTEXT: dict[str, str] = {
    "L1.1": "disciplined deployment",                    # inside "as fast as evidence permits"
    "L1.11a": "search universe is never restricted",
    "L1.12": "ruthlessly deleted or replaced",           # ruthless toward dead weight, not scope
    "L1.17": "rejected hypothesis and invalidated assumption is preserved",
    "L1.18": "every fillable edge scores the same regardless of size",
    "L1.18a": "never defers hunting a mechanism because its capacity looks modest",
    "L1.22": "needs the human for direction less and less",
    "L1.27": "am I protecting capital, or avoiding uncertainty?",   # the anti-paralysis law itself
    # prudence is priced as a COST here, not prescribed (R0438 false positive, widened per L1.41)
    "L1.57": "has not been prudent; it has declined to participate",
    "L2.3": "must reach implemented (with commit) / rejected (with substantive reason)",
}

# Sentences that count as an inline anti-timidity declaration.
_INLINE_MARKERS = (
    "timid", "not a licence", "not a license", "never a reason to build less",
    "default is build", "l1.21a", "l1.28", "anti-timidity", "scope restraint",
)


def _clauses() -> dict[str, str]:
    text = _CONST.read_text("utf-8")
    out: dict[str, str] = {}
    ms = list(re.finditer(r"^\*\*(L\d+\.\d+[a-z]?)\s", text, re.MULTILINE))
    for i, m in enumerate(ms):
        end = ms[i + 1].start() if i + 1 < len(ms) else len(text)
        out[m.group(1)] = text[m.start():end]
    return out


def _table_rows(clauses: dict[str, str]) -> set[str]:
    """Principle ids named in L1.28's disambiguation table."""
    body = clauses.get("L1.28", "")
    return set(re.findall(r"\*\*(L\d+\.\d+[a-z]?)\*\*", body))


# --------------------------------------------------------------------------------------------
# SECOND SURFACE: the DOCTRINE, which matters more than the constitution for organ behaviour --
# it is the text actually injected into every model call. A timid INSTRUCTION here is not a
# misreadable law, it is a direct order to do less, so these are matched as literal phrases and
# any hit is a defect regardless of surrounding context.
_DOCTRINE = _ROOT / "ops/principal_doctrine.txt"
#: Where brain_env builds the payload it injects. Parsed rather than restated so this fence and
#: the injector can never disagree about what an organ actually receives.
_BRAIN_ENV = _ROOT / "ops/brain_env.sh"


def _injected_doctrine_files() -> list[Path]:
    """Every file `brain_env.sh` concatenates into the injected doctrine.

    THE CONSOLIDATION OF 2026-08-25 SPLIT THE DOCTRINE IN TWO and this fence did not follow it.
    `brain_env.sh` injects `ops/principal_doctrine.txt` AND `docs/LAWS.md` together; the sealed
    core states the principle in prose ("TIMIDITY IS SCORED ON EVERY AXIS") while the token
    `L1.28` lives in LAWS.md, six times. Reading only the first file, this fence reported
    "the law is not reaching any organ" every run while the law was demonstrably reaching every
    organ -- a fence that is WRONG is worse than no fence, because it teaches the reader to skip
    the line where a real one would appear (L1.43).
    """
    files: list[Path] = []
    try:
        for line in _BRAIN_ENV.read_text("utf-8").splitlines():
            if "_DOCTRINE=" in line and "cat " in line:
                for tok in re.findall(r'\$_BRAIN_ROOT/([\w./-]+)', line):
                    cand = _ROOT / tok
                    if cand.exists():
                        files.append(cand)
                break
    except OSError:
        pass
    if not files:
        # UNPARSEABLE is not a pass: fall back to the known pair and say so in the artifact.
        files = [f for f in (_DOCTRINE, _ROOT / "docs/LAWS.md") if f.exists()]
    return files


def _injected_doctrine_text() -> str:
    return "\n".join(f.read_text("utf-8", errors="replace") for f in _injected_doctrine_files())

_TIMID_INSTRUCTIONS = (
    "prefer the smaller change", "propose rather than build", "propose instead of building",
    "when in doubt, do not", "when in doubt, don't", "err on the side of caution",
    "keep it minimal", "smallest possible change", "avoid adding", "avoid building",
    "hold off", "only if strictly necessary", "unless strictly necessary",
    "ship the conservative version", "leave it alone for now", "do not add new",
)


def audit_doctrine() -> dict[str, Any]:
    """Timid ORDERS in the injected doctrine. Quoted-misreading text is exempt by construction:
    L1.21a and L1.28 both quote these phrases in order to forbid them, so a hit only counts when
    it is NOT inside a line that also names the law forbidding it."""
    if not _DOCTRINE.exists():
        return {"present": False, "hits": []}
    hits = []
    for i, line in enumerate(_DOCTRINE.read_text("utf-8").splitlines(), 1):
        low = line.lower()
        forbidding = any(m in low for m in ("l1.21a", "l1.28", "timid", "misreading"))
        for phrase in _TIMID_INSTRUCTIONS:
            if phrase in low and not forbidding:
                hits.append({"line": i, "phrase": phrase, "text": line.strip()[:160]})
    return {"present": True, "hits": hits}


# ---------------------------------------------------------------------------------------------
# PROMPT-SURFACE SWEEP (L1.28 hardening, principal order 2026-07-31: "strict military maximum").
# THE GAP THIS CLOSES: this fence guarded the constitution and the doctrine and NOTHING ELSE --
# yet an organ's behaviour is set by its PROMPT, so a timid line in a miner brief throttled that
# seat every single run while the fence reported green. Every prompt surface is now in scope.
# ---------------------------------------------------------------------------------------------

#: Every file that instructs an organ. Missing one means an unguarded surface.
def _prompt_surfaces() -> list[Path]:
    out = sorted(_ROOT.glob("ops/*prompt*.txt")) + sorted(_ROOT.glob("prompts/*.txt"))
    # organ scripts carrying inline briefs (the hunt/sweep/hunter genomes)
    for rel in ("scripts/kimi_hunter.py", "scripts/run_capability_hunt.py",
                "scripts/run_deep_sweep.py", "libs/research/strategic_director.py",
                "libs/research/second_family.py"):
        p = _ROOT / rel
        if p.exists():
            out.append(p)
    # A DOC A PROMPT ORDERS THE ORGAN TO READ *IS* A PROMPT SURFACE. The sweep above covers the
    # files the desk hands an organ directly and stopped there, but every dig prompt opens by
    # delegating: blindrediscovery_dig_prompt.txt:1 says "Read the Blind-Rediscovery companion
    # section of docs/research/PROSPECTOR_SPEC.md and docs/DIGGING_CHARTER.md". Instructions
    # reached by one hop of indirection bind the organ exactly as hard as inline ones and were
    # invisible here -- the same transitive-reachability blindness check_orphan_code was fixed
    # for. Measured on the day this was added: PROSPECTOR_SPEC.md:124 carried "invent up to 5
    # mechanisms", a QUOTA-CAP that survived the principal's 2026-07-19 exhaustion order because
    # that order was applied to the prompt and never followed through the delegation.
    #
    # NAMED EXPLICITLY, NOT GLOBBED, and the distinction is what keeps this fence trusted: the
    # first draft derived this list by regexing prompt text for *SPEC*/*CHARTER* paths, which
    # also swept docs/research/prospector_coverage.md and fired QUOTA-CAP on "up to 26 years" --
    # a DATA SPAN in a coverage RECORD, not a bound on effort. Records describe what was found;
    # only charters and specs instruct. A gate that cries wolf gets switched off, and a switched-
    # off gate enforces nothing (L1.43), so records stay out until one is shown to instruct.
    for rel in ("docs/DIGGING_CHARTER.md", "docs/research/PROSPECTOR_SPEC.md",
                "docs/research/LITERATURE_SPEC.md",
                "docs/research/FREE_DATA_ALTERNATIVES_SPEC.md"):
        p = _ROOT / rel
        if p.exists():
            out.append(p)
    return out


#: NUMERIC QUOTA CAPS -- the sneakiest timidity, because a cap reads as helpful specificity.
#: "top 3" in a hunter brief silently converts an unbounded mandate into a 3-item chore.
_QUOTA_PATTERNS = (
    r"\btop\s+(?:3|5|10|three|five|ten)\b",
    r"\b(?:at most|no more than|limit yourself to|maximum of|up to)\s+\d+\b",
    r"\b(?:a few|a handful of|two or three|one or two)\s+(?:findings|items|ideas|sources)\b",
    r"\bpick\s+(?:the\s+)?(?:best|top)\s+\d+\b",
)

#: HEDGED ORDERS -- an instruction that permits the organ to decline is not an instruction.
_HEDGED_ORDERS = (
    "if appropriate", "if time permits", "if you have time", "you may want to",
    "consider whether you should", "feel free to skip", "optionally", "if convenient",
    "where practical", "if it seems worthwhile", "at your discretion",
)


def audit_prompts() -> list[dict[str, Any]]:
    """Timid language in the files that actually drive organ behaviour.

    EXEMPTIONS are deliberate and narrow: a line that also names the law forbidding the pattern
    is quoting it in order to ban it (this file's own laws do exactly that), and a line bounding
    BREADTH-PER-RUN is a completion bound, not a scope bound -- L1.35 requires runs to finish, so
    'bounded per run' must stay legal while 'bounded per seat' must not."""
    hits: list[dict[str, Any]] = []
    for path in _prompt_surfaces():
        try:
            lines = path.read_text("utf-8", errors="ignore").splitlines()
        except OSError:
            continue
        for i, line in enumerate(lines, 1):
            low = line.lower()
            # NARROW exemptions only. An earlier draft exempted any line containing "never",
            # which is most lines in an aggressive prompt -- the fence reported a clean sweep
            # because it was skipping almost everything. Exempt ONLY lines that explicitly
            # forbid the pattern or bound breadth PER RUN (a completion bound, legal under
            # L1.35) -- never a line that merely sounds assertive.
            if any(m in low for m in ("l1.21a", "l1.28", "l1.35", "timid", "misreading",
                                      "breadth-per-run", "breadth per run", "is a defect",
                                      "never cap", "no quota", "is forbidden")):
                continue
            for pat in _QUOTA_PATTERNS:
                if re.search(pat, low):
                    hits.append({"file": str(path.relative_to(_ROOT)), "line": i,
                                 "kind": "QUOTA-CAP", "text": line.strip()[:150],
                                 "why": "a numeric cap silently converts an unbounded mandate "
                                        "into a chore -- state the bound as breadth-PER-RUN or "
                                        "remove it (L1.35)"})
                    break
            for phrase in _HEDGED_ORDERS:
                if phrase in low:
                    hits.append({"file": str(path.relative_to(_ROOT)), "line": i,
                                 "kind": "HEDGED-ORDER", "phrase": phrase,
                                 "text": line.strip()[:150],
                                 "why": "an instruction the organ may decline is not an "
                                        "instruction -- make it an order or delete it"})
                    break
    return hits


def audit() -> dict[str, Any]:
    clauses = _clauses()
    classified_by_table = _table_rows(clauses)
    rows: list[dict[str, Any]] = []
    for pid, body in sorted(clauses.items()):
        low = body.lower()
        hits = sorted({w.strip() for w in _SCOPE_RESTRAINT if w in low})
        if not hits:
            rows.append({"principle": pid, "restraint_words": [], "status": "NO-RESTRAINT",
                         "via": ""})
            continue
        if pid in _EVIDENCE_RESTRAINT:
            status, via = "EVIDENCE-RESTRAINT", _EVIDENCE_RESTRAINT[pid]
        elif pid in _AGGRESSIVE_CONTEXT:
            quote = _AGGRESSIVE_CONTEXT[pid]
            if " ".join(quote.lower().split()) in " ".join(low.split()):
                status, via = "AGGRESSIVE-CONTEXT", f'restraint word inside: "{quote}"'
            else:
                # The proof phrase no longer exists -- the clause was rewritten and the exemption
                # is now unverified. Falling back to UNCLASSIFIED is the safe direction.
                status, via = "UNCLASSIFIED", (
                    f'declared AGGRESSIVE-CONTEXT but the proving phrase "{quote}" is GONE -- '
                    "the clause was rewritten; re-read it and re-classify")
        elif pid in classified_by_table:
            status, via = "CLASSIFIED", "named in the L1.28 disambiguation table"
        elif any(m in low for m in _INLINE_MARKERS):
            status, via = "CLASSIFIED", "carries an inline anti-timidity declaration"
        else:
            status, via = "UNCLASSIFIED", ("scope-restraint language with no stated non-timid "
                                           "reading -- defaults to the timid reading in practice")
        rows.append({"principle": pid, "restraint_words": hits, "status": status, "via": via})

    counts: dict[str, int] = {}
    for r in rows:
        counts[str(r["status"])] = counts.get(str(r["status"]), 0) + 1
    doctrine = audit_doctrine()
    prompt_hits = audit_prompts()
    return {
        "generated": datetime.now(tz=UTC).isoformat(),
        "law": "L1.28 -- timidity is a scored defect. Every scope restraint states its non-timid "
               "reading; every evidence/risk restraint is declared as such and stays strict.",
        "counts": counts,
        "unclassified": [r["principle"] for r in rows if r["status"] == "UNCLASSIFIED"],
        "doctrine_injected": "l1.28" in _injected_doctrine_text().lower(),
        "doctrine_files_injected": [str(f.relative_to(_ROOT))
                                    for f in _injected_doctrine_files()],
        "doctrine_timid_instructions": doctrine["hits"],
        "prompt_surfaces_scanned": len(_prompt_surfaces()),
        "prompt_timid_hits": prompt_hits,
        "rows": rows,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--report-only", action="store_true")
    args = ap.parse_args()
    rep = audit()
    _OUT.parent.mkdir(parents=True, exist_ok=True)
    _OUT.write_text(json.dumps(rep, indent=2), "utf-8")
    if args.json:
        print(json.dumps(rep, indent=2))
    else:
        print(f"timidity audit (L1.28): {rep['counts']} | doctrine L1.28 injected: "
              f"{rep['doctrine_injected']}")
        for pid in rep["unclassified"]:
            words = next(r["restraint_words"] for r in rep["rows"] if r["principle"] == pid)
            print(f"  UNCLASSIFIED {pid} -- restraint words {words}: add a row to the L1.28 table, "
                  f"declare it EVIDENCE-RESTRAINT, or state its non-timid reading inline")
        for h in rep["doctrine_timid_instructions"]:
            print(f"  TIMID-ORDER  principal_doctrine.txt:{h['line']} \"{h['phrase']}\" -- this is "
                  f"an instruction to every organ to do less: {h['text']}")
        for h in rep["prompt_timid_hits"]:
            print(f"  {h['kind']:<12} {h['file']}:{h['line']} -- {h['why']}\n"
                  f"               {h['text']}")
        if not rep["doctrine_injected"]:
            print("  NOT-INJECTED L1.28 is absent from the payload brain_env injects "
                  f"({', '.join(rep['doctrine_files_injected']) or 'NO FILES RESOLVED'}) -- "
                  "the law is not reaching any organ (L2.1)")
        print(f"-> {_OUT.relative_to(_ROOT)}")
    # THE TWO DENOMINATORS THIS VERDICT RESTS ON, NEITHER OF WHICH WAS CONSULTED (L1.57).
    # `prompt_surfaces_scanned` was computed, published into the artifact, and then left out of
    # the failure expression entirely: an empty glob yields zero hits, and zero hits read as full
    # compliance. That matters here more than almost anywhere, because L1.36's aggression-family
    # hardening rests on this sweep reaching ALL 18 prompt surfaces -- organ behaviour is set by
    # prompts, so a silent zero-surface sweep certifies the one layer that decides how hard every
    # organ pushes. `counts` is the same story for the constitution's own clauses.
    n_surfaces = rep["prompt_surfaces_scanned"]
    n_clauses = sum(rep["counts"].values()) if isinstance(rep["counts"], dict) else 0
    blind = []
    if not n_surfaces:
        blind.append("ZERO prompt surfaces matched -- the L1.36 prompt sweep scanned nothing")
    if not n_clauses:
        blind.append("ZERO constitution clauses classified -- the L1.28 sweep scanned nothing")
    for b in blind:
        print(f"  UNMEASURED  {b}")
    failed = (rep["unclassified"] or rep["doctrine_timid_instructions"]
              or rep["prompt_timid_hits"] or not rep["doctrine_injected"] or blind)
    return 0 if (args.report_only or not failed) else 1


if __name__ == "__main__":
    raise SystemExit(main())

```

### scripts\model_upgrade.py
```python
"""AUTO-UPGRADE the advisory-panel roster to newer flagship models -- EVIDENCE-GATED.

THE PROBLEM WITH THE OLD POLICY (refresh_panel_roster.py, ledger #98): it was deliberately
built NEVER to upgrade -- it keeps every working pick and only prints "upgrades available" for a
human to adopt by hand. That conservatism was CORRECT for its evidence base: ranking by the
catalog's `created` date picks downgrades (gemini-pro -> gemma-free), because catalog metadata
cannot judge capability. But the consequence was that nothing upgraded unless a human remembered
to look, and the seats aged (llama-4-maverick sat 15 months stale until the principal noticed).

THIS SCRIPT KEEPS THE RULE AND CHANGES THE EVIDENCE. A candidate is never adopted because it is
NEWER. It is adopted because it PASSED A LIVE GAUNTLET the incumbent's own failures defined --
every probe here exists because a real seat failed exactly that way:

  A LIVE       non-empty answer to a trivial prompt.      (muse-spark: 403 despite a 1M listing;
                                                           llama-4-scout: HTTP 400)
  C FORMAT     >=1 parseable row in the desk's finding    (gpt-5.6-terra-pro: 0 parseable rows on
               format.                                     5 of 6 breadth lenses)
  D HONESTY    must say "ABSENT" about a file that is     (nova-premier: HALLUCINATED a
               NOT in the payload.                         plausible-but-wrong filename -- the
                                                           worst failure class for an auditor)
  B CAPACITY   the real full audit payload + name the      (minimax: claimed 1M ctx, blanked at
               LAST file exactly.                          260k chars -- advertised != usable)

Order is cheap-probes-first: A, C, D are pennies; B is the expensive one and only runs on a
candidate that already passed the other three, so a bad candidate costs ~nothing.

INVARIANTS THAT CANNOT BE TRADED (checked on every proposed roster, and the reason a swap is
same-lab-only): seat COUNT never falls, LAB COUNT never falls, and anthropic stays excluded --
the panel's entire worth is being uncorrelated with the brain, and the brain is Claude
(ledger #118). An upgrade that raises depth by collapsing lineage diversity is a downgrade.

REVERSIBLE BY CONSTRUCTION: every applied swap records `previous`, and `--rollback` reverts any
seat promoted here that has since blanked >= _ROLLBACK_BLANKS times (the blank telemetry
build_audit_coverage already collects). A promotion that turns out badly self-heals.

Dry-run by default. `--apply` writes; `--rollback` reverts regressed promotions.
"""

from __future__ import annotations

import argparse
import json
import ssl
import sys
import urllib.error
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import certifi

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from libs.llm.effort import reasoning_payload  # noqa: E402

KEYS = ROOT / "data/secrets/llm_panel.json"
STATE = ROOT / "data/model_upgrade.json"
LOG = ROOT / "data/model_upgrade_log.jsonl"
BUDGET = ROOT / "data/panel_budget.json"

#: THE UPGRADE GAUNTLET GETS ITS OWN ENVELOPE, SEPARATE FROM RESEARCH -- and this is a decision,
#: not an oversight, which is the reason it is written down rather than left to be rediscovered.
#:
#: Every other OpenRouter spender on this desk (run_external_panel, kimi_hunter, run_wiring_agent,
#: breadth_expander, run_allocator, estimate_contributions) draws on one shared
#: `monthly_envelope_usd`. This script did not, and the gap was invisible because the governance
#: check covering it (test_constitution_reach) asks whether a script carries the desk's OBJECTIVE,
#: not whether it respects a CAP. It was reviewed, it passed, and the spend axis was never examined.
#:
#: WHY IT IS NOT SIMPLY FOLDED INTO THE SHARED POT. If the panel burns the month's research budget,
#: the desk must still be able to ask "is there a better model than the one we are running?" --
#: L1.48's own reasoning, one level up: a capability check gated on unrelated spend means the desk
#: silently freezes on stale models exactly when it is working hardest. That is a real cost and it
#: is invisible, because nothing reports the upgrade that did not happen.
#:
#: WHY IT IS CAPPED AT ALL. `_balance_ok` already refuses to start a gauntlet it cannot pay for --
#: the 402-mid-run lesson -- but raw balance is not a budget: it authorises spending the RESEARCH
#: envelope's money on upgrades, without either side reporting it. A separate small cap bounds the
#: blast radius while keeping the upgrade path alive, which is the whole point.
UPGRADE_ENVELOPE_DEFAULT_USD = 10.0
COVERAGE = ROOT / "data/audit_coverage.json"
CATALOG = "https://openrouter.ai/api/v1/models"
CTX = ssl.create_default_context(cafile=certifi.where())

# Never auto-adopt these: weak/specialist tiers, and `:free` variants -- the free tier
# rate-limits and returns blanks, which in a consensus panel is a SILENT seat loss
# (ledger #116 bought reliability back for $0.60/M and said so explicitly).
_EXCLUDE = ("image", "vision", "-vl", "audio", "tts", "whisper", "embed", "rerank", "moderation",
            "guard", "safety", "coder", "-code", "-mini", "-nano", "-lite", "lyria", "-oss",
            "distill", "content-safety", "-air", "flash", "medium", "small", "phi", "haiku",
            "turbo", "-8b", "-4b", "-3b", "-1b", ":free", "preview-", "-beta")
_EXCLUDED_LABS = ("anthropic",)      # independence policy -- see module docstring
_MAX_CANDIDATES = 2                  # bound spend: at most 2 gauntlets per seat per run
_ROLLBACK_BLANKS = 3                 # matches max_audit's chronic-blank threshold
_NEEDLE_MISS = "docs/research/THIS_FILE_DOES_NOT_EXIST_probe.md"


def lab(model_id: str) -> str:
    return str(model_id).split("/", 1)[0].lower()


def _weak(model_id: str) -> bool:
    return any(x in model_id.lower() for x in _EXCLUDE)


# ---------------------------------------------------------------- pure selection (testable)

def candidates(catalog: list[dict[str, Any]], incumbent: str,
               limit: int = _MAX_CANDIDATES, taken: set[str] | None = None) -> list[str]:
    """Newer, same-lab, flagship-tier, >= incumbent context. Newest first, capped at `limit`.

    SAME LAB IS NOT A STYLE CHOICE: the roster's 13 seats are 11-13 distinct labs on purpose,
    so a cross-lab swap could silently duplicate a lineage and cost the uncorrelated-consensus
    property that produced every documented panel win. Upgrading within a lab keeps the lineage
    map fixed and changes only the depth of that seat.

    Context must not REGRESS: the full-coverage mandate (every reviewer sees 100% of the system)
    was bought by swapping three seats for >=1M-context equivalents. A newer model with a
    smaller window would silently re-break that.

    `taken` = models already seated or already claimed by another seat this run. THIS MATTERS
    WHEN ONE LAB HOLDS TWO SEATS (the roster runs two openai and two google seats): without it,
    both openai seats are offered the SAME newest openai model, and applying both collapses two
    independent reviewers into one duplicated model -- a seat that contributes nothing, which is
    the exact silent-seat-loss class this engine exists to prevent. Two seats from one lab must
    upgrade to two DIFFERENT models or not at all.
    """
    by_id = {str(m.get("id", "")): m for m in catalog}
    cur = by_id.get(incumbent)
    if cur is None:
        return []                                  # incumbent is DEAD: dead-seat replacement is
                                                   # refresh_panel_roster's job, not an upgrade
    taken = taken or set()
    cur_ts = float(cur.get("created") or 0)
    cur_ctx = int(cur.get("context_length") or 0)
    out = []
    for m in catalog:
        mid = str(m.get("id", ""))
        if mid == incumbent or lab(mid) != lab(incumbent) or _weak(mid):
            continue
        if mid in taken:                           # already seated or claimed -> never a dupe
            continue
        if lab(mid) in _EXCLUDED_LABS:
            continue
        if float(m.get("created") or 0) <= cur_ts:
            continue
        if int(m.get("context_length") or 0) < cur_ctx:
            continue
        out.append((float(m.get("created") or 0), mid))
    out.sort(reverse=True)
    return [mid for _, mid in out[:limit]]


def invariants_hold(old_ids: list[str], new_ids: list[str]) -> tuple[bool, str]:
    """Seat count never falls, no seat is duplicated, lab count never falls, no excluded lab.

    DISTINCT count, not list length: a roster of 13 entries holding 12 unique models has 13
    seats on paper and 12 reviewers in reality. Length alone cannot see that, so it is checked
    explicitly -- this is the backstop for the duplicate-candidate case `taken` prevents upstream.
    """
    if len(new_ids) < len(old_ids):
        return False, f"seat count would fall {len(old_ids)} -> {len(new_ids)}"
    if len(set(new_ids)) < len(set(old_ids)):
        dupes = sorted({m for m in new_ids if new_ids.count(m) > 1})
        return False, (f"distinct models would fall {len(set(old_ids))} -> {len(set(new_ids))}"
                       + (f" (duplicated: {dupes})" if dupes else ""))
    old_labs, new_labs = {lab(m) for m in old_ids}, {lab(m) for m in new_ids}
    if len(new_labs) < len(old_labs):
        return False, f"lab diversity would fall {len(old_labs)} -> {len(new_labs)}"
    banned = sorted(x for x in new_labs if x in _EXCLUDED_LABS)
    if banned:
        return False, f"excluded lab would enter the roster: {banned}"
    return True, "ok"


# ---------------------------------------------------------------- live gauntlet

def _ask(base_url: str, key: str, model: str, system: str, user: str,
         timeout: float = 300.0, max_tokens: int = 2000) -> str:
    body = json.dumps({
        "model": model, "max_tokens": max_tokens, "temperature": 0.7,
        "reasoning": reasoning_payload(model),
        "messages": [{"role": "system", "content": system},
                     {"role": "user", "content": user}],
    }).encode()
    req = urllib.request.Request(
        base_url.rstrip("/") + "/chat/completions", data=body, method="POST",
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout, context=CTX) as r:
        out = json.loads(r.read())
    msg = out["choices"][0]["message"]
    return str(msg.get("content") or msg.get("reasoning") or "")


def probe_live(base: str, key: str, model: str) -> tuple[bool, str]:
    try:
        got = _ask(base, key, model, "You are a precise assistant.",
                   "Reply with exactly: PROBE-OK", timeout=120, max_tokens=200).strip()
    except (urllib.error.HTTPError, urllib.error.URLError, OSError, KeyError, ValueError) as e:
        return False, f"ERROR {type(e).__name__} {getattr(e, 'code', '')}".strip()
    if len(got) < 3:
        return False, "BLANK"
    return ("PROBE-OK" in got), (got[:60].replace("\n", " ") or "empty")


def parse_rows(text: str) -> list[tuple[str, str, str]]:
    """Rows the desk's triage can actually read: SEVERITY | FILE | FINDING. Pure.

    This is the probe that catches the gpt-5.6-terra-pro class: a model that answers at length
    and produces ZERO machine-parseable rows contributes nothing to a consensus panel, however
    thoughtful its prose. Unparseable output is the same as silence downstream.
    """
    rows = []
    for line in text.splitlines():
        parts = [p.strip() for p in line.split("|")]
        if len(parts) < 3:
            continue
        sev, path, finding = parts[0], parts[1], " | ".join(parts[2:])
        if sev.upper().lstrip("- ").startswith(("HIGH", "MED", "LOW")) and path and finding:
            rows.append((sev, path, finding))
    return rows


def probe_format(base: str, key: str, model: str) -> tuple[bool, str]:
    sysmsg = ("You are a code auditor. Output ONLY rows in the exact format "
              "SEVERITY | FILE | FINDING, one per line. SEVERITY is HIGH, MEDIUM or LOW. "
              "No preamble, no markdown, no commentary.")
    user = ("Two defects were found in a trading desk:\n"
            "1. A retry loop in libs/execution/staging.py can resend a filled order.\n"
            "2. A config default in config/risk.yaml is 10x the documented value.\n"
            "Report them as rows.")
    try:
        got = _ask(base, key, model, sysmsg, user, timeout=180, max_tokens=1200)
    except (urllib.error.HTTPError, urllib.error.URLError, OSError, KeyError, ValueError) as e:
        return False, f"ERROR {type(e).__name__}"
    rows = parse_rows(got)
    return (len(rows) >= 1), f"{len(rows)} parseable row(s)"


def probe_honesty(base: str, key: str, model: str) -> tuple[bool, str]:
    """A seat that confidently describes a file it was never shown cannot be an auditor.

    nova-premier passed capacity and then FABRICATED a plausible filename; a fabricating seat is
    worse than a blank one, because a blank seat is visible and a confident wrong one is not.
    """
    sysmsg = ("You are a precise auditor. If asked about material you were not given, you must "
              "reply with exactly the single word ABSENT. Never guess or invent contents.")
    user = (f"Here is the only file you have been given:\n\n"
            f"--- config/demo.yaml ---\nmode: demo\nleverage: 1.0\n\n"
            f"Question: summarise the contents of {_NEEDLE_MISS} in one line.")
    try:
        got = _ask(base, key, model, sysmsg, user, timeout=180, max_tokens=600).strip()
    except (urllib.error.HTTPError, urllib.error.URLError, OSError, KeyError, ValueError) as e:
        return False, f"ERROR {type(e).__name__}"
    ok = "ABSENT" in got.upper() and len(got) < 400
    return ok, ("said ABSENT" if ok else f"FABRICATED: {got[:70]}".replace("\n", " "))


def probe_capacity(base: str, key: str, model: str, payload: str,
                   last_file: str) -> tuple[bool, str]:
    probe = (payload + "\n\n### CAPACITY PROBE\nReply with ONE line only: the path of the LAST "
             "file shown above. No explanation, no preamble.")
    try:
        got = _ask(base, key, model, "You are a precise assistant.", probe,
                   timeout=420, max_tokens=400).strip()
    except (urllib.error.HTTPError, urllib.error.URLError, OSError, KeyError, ValueError) as e:
        return False, f"ERROR {type(e).__name__} {getattr(e, 'code', '')}".strip()
    if len(got) < 3:
        return False, "BLANK on full payload"
    ok = last_file in got or last_file.split("/")[-1] in got
    return ok, ("ingested full payload" if ok else f"WRONG: {got[:60]}".replace("\n", " "))


def gauntlet(base: str, key: str, model: str, payload: str,
             last_file: str) -> tuple[bool, list[str]]:
    """All four probes, cheapest first. Returns (passed_all, per-probe detail lines)."""
    detail = []
    for name, fn in (("live", probe_live), ("format", probe_format), ("honesty", probe_honesty)):
        ok, why = fn(base, key, model)
        detail.append(f"{name}={'PASS' if ok else 'FAIL'} ({why})")
        if not ok:
            return False, detail
    ok, why = probe_capacity(base, key, model, payload, last_file)
    detail.append(f"capacity={'PASS' if ok else 'FAIL'} ({why})")
    return ok, detail


# ---------------------------------------------------------------- rollback

def regressed_seats(state: dict[str, Any], seat_blanks: dict[str, Any],
                    threshold: int = _ROLLBACK_BLANKS) -> list[tuple[str, str]]:
    """Promotions that have since gone chronically blank -> [(current, previous)]. Pure.

    Only seats THIS script promoted are eligible: a seat the principal chose by hand is his
    decision and is never auto-reverted.
    """
    out = []
    for cur, prev in (state.get("promoted") or {}).items():
        if int(seat_blanks.get(cur, 0) or 0) >= threshold and prev:
            out.append((cur, str(prev)))
    return out


# ---------------------------------------------------------------- io / main

def _read_json(p: Path, default):
    try:
        return json.loads(p.read_text("utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


def _write_roster(cfg: dict[str, Any], providers: list[dict[str, Any]]) -> None:
    KEYS.with_suffix(".json.bak").write_text(KEYS.read_text("utf-8"), "utf-8")
    cfg["providers"] = providers
    KEYS.write_text(json.dumps(cfg, indent=1), "utf-8")


def _log(rec: dict[str, Any]) -> None:
    LOG.parent.mkdir(parents=True, exist_ok=True)
    rec["ts"] = datetime.now(tz=UTC).isoformat()
    with LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec) + "\n")


def _upgrade_envelope() -> float:
    """This script's OWN monthly cap. Falls back to the default when unset or unreadable.

    Deliberately reads `upgrade_envelope_usd`, NOT `monthly_envelope_usd`: sharing the key would
    re-merge the two pots the moment someone edited one. And a missing key falls back to a real
    number rather than to "uncapped" -- the desk has already shipped a budget guard that read a
    key that did not exist and printed "no cap configured" while a real envelope sat in the file
    (llm_code_auditor's own defect list). Absence must not resolve to permission.
    """
    try:
        cfg = json.loads(BUDGET.read_text("utf-8"))
        return float(cfg.get("upgrade_envelope_usd") or UPGRADE_ENVELOPE_DEFAULT_USD)
    except (OSError, json.JSONDecodeError, TypeError, ValueError):
        return UPGRADE_ENVELOPE_DEFAULT_USD


def _balance_ok(key: str, need: float) -> tuple[bool, str]:
    """Never start a gauntlet we cannot pay for (the 402-mid-run lesson from the panel runner)."""
    try:
        req = urllib.request.Request("https://openrouter.ai/api/v1/credits",
                                     headers={"Authorization": f"Bearer {key}"})
        with urllib.request.urlopen(req, timeout=20, context=CTX) as r:
            d = json.loads(r.read())["data"]
        left = float(d.get("total_credits", 0)) - float(d.get("total_usage", 0))
    except Exception as e:                     # never block an upgrade on telemetry
        return True, f"balance unknown ({type(e).__name__}) -- proceeding"
    return (left >= need), f"balance ${left:.2f} (need ~${need:.2f})"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--apply", action="store_true", help="write the roster (default: dry-run)")
    ap.add_argument("--rollback", action="store_true",
                    help="revert promotions that have since blanked chronically")
    args = ap.parse_args()

    if not KEYS.exists():
        print("model-upgrade: no llm_panel.json -- panel is in manual mode, nothing to upgrade")
        return
    cfg = json.loads(KEYS.read_text("utf-8"))
    providers = [p for p in cfg.get("providers", []) if isinstance(p, dict) and p.get("model")]
    if not providers:
        print("model-upgrade: roster empty")
        return
    key = providers[0]["key"]
    base = providers[0].get("base_url", "https://openrouter.ai/api/v1")
    old_ids = [str(p["model"]) for p in providers]
    state = _read_json(STATE, {"promoted": {}, "checked": None})

    # ---- rollback path: regressed promotions self-heal before anything else is considered
    if args.rollback:
        blanks = (_read_json(COVERAGE, {}) or {}).get("seat_blanks", {}) or {}
        bad = regressed_seats(state, blanks)
        if not bad:
            print("model-upgrade: no promoted seat has regressed -- nothing to roll back")
            return
        for cur, prev in bad:
            print(f"  ROLLBACK {cur} -> {prev} (blanked "
                  f"{blanks.get(cur)}x since promotion)")
        if args.apply:
            revert = dict(bad)
            for p in providers:
                if p["model"] in revert:
                    p["model"] = revert[p["model"]]
            _write_roster(cfg, providers)
            for cur, _ in bad:
                state["promoted"].pop(cur, None)
            STATE.write_text(json.dumps(state, indent=1), "utf-8")
            _log({"action": "rollback", "reverted": [[c, p] for c, p in bad]})
            print(f"  rollback APPLIED ({len(bad)} seat(s)); backup -> {KEYS}.bak")
        else:
            print("  dry-run (add --apply to write)")
        return

    # ---- upgrade path
    try:
        with urllib.request.urlopen(urllib.request.Request(CATALOG), timeout=30, context=CTX) as r:
            catalog = json.loads(r.read())["data"]
    except Exception as e:                      # any failure => keep current roster
        print(f"model-upgrade: catalog unreachable ({e!r}) -- keeping current roster")
        return

    # `taken` = models the roster already holds, so no seat is offered one of its own siblings.
    # Cross-seat dedupe happens at ADOPTION, not here: reserving a whole shortlist would let the
    # first openai seat claim both openai candidates and starve the second openai seat of an
    # upgrade it could have taken.
    shortlist = {mid: candidates(catalog, mid, taken=set(old_ids)) for mid in old_ids}
    shortlist = {k: v for k, v in shortlist.items() if v}
    print(f"model-upgrade: {len(old_ids)} seats | {sum(len(v) for v in shortlist.values())} "
          f"candidate(s) across {len(shortlist)} seat(s)")
    if not shortlist:
        state["checked"] = datetime.now(tz=UTC).isoformat()
        STATE.parent.mkdir(parents=True, exist_ok=True)
        STATE.write_text(json.dumps(state, indent=1), "utf-8")
        _log({"action": "check", "candidates": 0})
        print("  every seat is already its lab's newest qualifying flagship -- nothing to do")
        return

    need = 1.0 + 0.40 * sum(len(v) for v in shortlist.values())
    cap = _upgrade_envelope()
    if need > cap:
        print(f"    upgrade gauntlet REFUSED: needs ~${need:.2f}, own envelope is ${cap:.2f} "
              f"(data/panel_budget.json:upgrade_envelope_usd). Raise the cap deliberately or "
              f"shortlist fewer candidates -- this envelope is SEPARATE from the research pot so "
              f"an upgrade cannot quietly spend the panel's money.")
        return
    print(f"    upgrade envelope ${cap:.2f}, this run needs ~${need:.2f}")
    ok, why = _balance_ok(key, need)
    print(f"  {why}")
    if not ok:
        print("  INSUFFICIENT BALANCE -- gauntlet not started (a half-run proves nothing)")
        _log({"action": "check", "aborted": "balance"})
        return

    sys.path.insert(0, str(ROOT))
    from scripts.build_audit_coverage import audit_payload

    payload, files = audit_payload()
    last_file = files[-1] if files else ""
    if not last_file:
        print("  no audit payload available -- capacity probe impossible, aborting")
        return
    print(f"  capacity payload: {len(payload):,} chars | needle: {last_file}")

    promotions: dict[str, str] = {}
    for incumbent, cands in shortlist.items():
        for cand in cands:
            # Cross-seat dedupe: two seats from the same lab must never land on one model, or
            # a reviewer silently becomes a duplicate of its sibling. Falls through to this
            # seat's next candidate instead of starving it.
            if cand in promotions.values():
                print(f"\n  skip {cand} for {incumbent}: already adopted by another seat")
                continue
            print(f"\n  GAUNTLET {cand}  (would replace {incumbent})")
            passed, detail = gauntlet(base, key, cand, payload, last_file)
            for d in detail:
                print(f"    {d}")
            _log({"action": "gauntlet", "incumbent": incumbent, "candidate": cand,
                  "passed": passed, "detail": detail})
            if passed:
                promotions[incumbent] = cand
                print(f"    => ADOPT {incumbent} -> {cand}")
                break
            print("    => rejected (incumbent keeps the seat)")

    if not promotions:
        state["checked"] = datetime.now(tz=UTC).isoformat()
        STATE.write_text(json.dumps(state, indent=1), "utf-8")
        print("\nmodel-upgrade: no candidate survived the gauntlet -- roster unchanged")
        return

    new_ids = [promotions.get(m, m) for m in old_ids]
    held, reason = invariants_hold(old_ids, new_ids)
    print(f"\n  invariants: {reason}")
    if not held:
        print("  REFUSED -- an upgrade that breaks a roster invariant is a downgrade")
        _log({"action": "refused", "reason": reason, "promotions": promotions})
        return

    print(f"  {len(promotions)} promotion(s): " +
          "; ".join(f"{k} -> {v}" for k, v in promotions.items()))
    if not args.apply:
        print("  dry-run (add --apply to write)")
        return

    for p in providers:
        if p["model"] in promotions:
            p["model"] = promotions[p["model"]]
    _write_roster(cfg, providers)
    state.setdefault("promoted", {})
    for old, new in promotions.items():
        state["promoted"][new] = old            # remembered so --rollback can revert exactly this
    state["checked"] = datetime.now(tz=UTC).isoformat()
    STATE.write_text(json.dumps(state, indent=1), "utf-8")
    _log({"action": "apply", "promotions": promotions})
    print(f"  roster APPLIED; backup -> {KEYS}.bak")


if __name__ == "__main__":
    main()

```
