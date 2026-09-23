# AUDIT SHARD 2/24 -- seat openai/gpt-6-astra

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

### libs\data\xls_reader.py
```python
"""Stdlib-only reader for legacy ``.xls`` -- OLE2 compound file + BIFF8 records (OP-046, R0317).

THE BLOCKER THIS REMOVES IS FALSE. ``pandas.read_excel`` cannot open a legacy ``.xls`` without
``xlrd``, and this box has no ``xlrd``, no ``openpyxl`` and no ``olefile`` -- installs are frozen.
Read literally, that reduces every government, regulator and central-bank publication served as
``.xls`` to a screenshot-grade citation. Those publications are disproportionately legacy ``.xls``
precisely BECAUSE they are old institutional pipelines, which is the same reason they stay
under-mined: the format is a moat made of tedium, not of secrecy. A ``.xls`` is two documented
byte-level layers and neither needs a dependency.

WHAT THIS IS NOT. It is not a spreadsheet engine. Formulas are not evaluated -- only the cached
result Excel stored beside them is read. Formatting, dates-as-serials, charts and macros are
ignored by construction: a research extractor wants the numbers, and every additional decoded
feature is another surface that can be plausibly wrong.

THE TWO BUGS THAT PRODUCE PLAUSIBLE-BUT-WRONG OUTPUT, both hit live in the run that produced
OP-046, and both are the reason ``tests/data/test_xls_reader.py`` builds a fixture with TWO sheets
and a deliberately split shared-string table rather than the smallest file that parses:

  (a) SHEET COLLISION. Cell records carry NO sheet id. Keying them on ``(row, col)`` merges every
      sheet in the workbook into one grid. It does not crash and it does not look wrong -- it
      produced a row reading ``CRIPTOATIVO | MES/ANO | ... | 899.79 | 990.46``, one report's
      header spliced onto another report's numbers. The ONLY attribution available is the
      record's absolute stream OFFSET compared against the BOUNDSHEET positions, which is why
      :func:`_parse_biff` tracks ``pos`` and never trusts record order alone.

  (b) SST CONTINUE BOUNDARIES. The shared-string table spans ``CONTINUE`` records and the 1-byte
      compressed/wide flag REPEATS at every continuation boundary, MID-STRING. Ignore it and the
      strings silently become mojibake from the first boundary onward -- silently, because the
      byte count still works out. :class:`_SstReader` exists solely to hold that boundary.

AND THE VALIDATION IS THE TRANSFERABLE HALF. An extractor validated by "it looks right" is a
phantom-evidence factory (OP-025). Pair every parse that feeds a research artifact with a
conservation law taken from INSIDE the data -- :mod:`libs.research.conservation`, which is what
caught bug (a) in the original run when the totals stopped adding up.

    from libs.data.xls_reader import read_xls
    sheets = read_xls(Path("criptoativos_dados_abertos_20250131.xls"))
    {s.name: len(s.cells) for s in sheets}
"""

from __future__ import annotations

import struct
from dataclasses import dataclass
from pathlib import Path
from typing import Final

#: R0318. The structural invariants this parse enforces on ITSELF, all of them refusals rather
#: than repairs: the stream must end exactly on a record boundary (a 1-3 byte tail is a silent
#: truncation), no record may run past the stream, no sector chain may cycle, and the BIFF version
#: must be one this decoder actually implements. They bound the SHAPE of the parse; they cannot
#: tell you the NUMBERS are right -- for that a caller pairs this with an arithmetic identity from
#: inside the data (libs.research.conservation), which is what scripts/read_xls.py requires.
EXTRACTOR_INVARIANT = (
    "stream ends on a record boundary; no record overruns the stream; no sector chain cycles; "
    "BIFF version is 0x0600 -- structural only, so callers add a conservation law for the values"
)

_OLE_SIG: Final = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"

# Sector chain sentinels (MS-CFB 2.2). Anything >= _MAXREGSECT is a marker, never an index.
_MAXREGSECT: Final = 0xFFFFFFFA
_ENDOFCHAIN: Final = 0xFFFFFFFE

_DIR_ENTRY_SIZE: Final = 128
_DIR_TYPE_STREAM: Final = 2
_DIR_TYPE_ROOT: Final = 5

# BIFF8 record opcodes actually decoded here. Everything else is skipped by length, which is why
# an unknown record can never corrupt the walk -- the length prefix is authoritative.
_BOF: Final = 0x0809
_EOF: Final = 0x000A
_BOUNDSHEET: Final = 0x0085
_SST: Final = 0x00FC
_CONTINUE: Final = 0x003C
_LABELSST: Final = 0x00FD
_LABEL: Final = 0x0204
_NUMBER: Final = 0x0203
_RK: Final = 0x027E
_MULRK: Final = 0x00BD
_FORMULA: Final = 0x0006
_BOOLERR: Final = 0x0205
_FILEPASS: Final = 0x002F

#: BIFF8's hard column limit. A column past this is not a wide spreadsheet, it is a misread record
#: -- and left unchecked it is the expensive kind: ``Sheet.rows()`` densifies to
#: ``n_rows x n_cols``, so one junk cell at column 65535 asks for billions of slots and takes the
#: box down rather than raising. Bounding it refuses the corrupt file AND caps the allocation.
#: Only the column is checked: rows arrive as a u16 and BIFF8 allows all 65536 of them, so that
#: bound is structural and a row guard would be a branch that can never fire.
_MAX_COLS: Final = 256

_BIFF8_VERSION: Final = 0x0600

#: A chain longer than this is a cycle, not a file. Bounded so a corrupt FAT refuses rather than
#: hangs -- an extractor that spins on bad input is indistinguishable from a dead one.
_MAX_CHAIN: Final = 1_000_000


class XlsError(ValueError):
    """The input is not a readable BIFF8 ``.xls``.

    Always raised rather than returning a partial grid: a truncated parse that returns SOME cells
    is the single most dangerous outcome here, because the caller's conservation law may still
    pass over whatever survived.
    """


@dataclass(frozen=True)
class Sheet:
    """One worksheet: its name and its sparse cell map, keyed ``(row, col)``, both 0-based."""

    name: str
    cells: dict[tuple[int, int], object]

    @property
    def n_rows(self) -> int:
        return max((r for r, _ in self.cells), default=-1) + 1

    @property
    def n_cols(self) -> int:
        return max((c for _, c in self.cells), default=-1) + 1

    def rows(self) -> list[list[object]]:
        """Dense rectangular grid, ``None`` in every cell the file did not store."""
        width = self.n_cols
        grid: list[list[object]] = [[None] * width for _ in range(self.n_rows)]
        for (r, c), value in self.cells.items():
            grid[r][c] = value
        return grid

    def column(self, col: int, *, skip: int = 0) -> list[object]:
        """One column top-to-bottom, ``skip`` leading rows dropped (header rows)."""
        return [row[col] if col < len(row) else None for row in self.rows()[skip:]]


# --------------------------------------------------------------------------- OLE2 / compound ---
def _u16(buf: bytes, off: int) -> int:
    return int(struct.unpack_from("<H", buf, off)[0])


def _u32(buf: bytes, off: int) -> int:
    return int(struct.unpack_from("<I", buf, off)[0])


def _chain(fat: list[int], start: int) -> list[int]:
    """Follow a sector chain to its end, refusing cycles rather than looping forever."""
    out: list[int] = []
    sector = start
    while sector < _MAXREGSECT:
        if sector >= len(fat):
            raise XlsError(f"sector {sector} past the end of the FAT ({len(fat)} entries)")
        out.append(sector)
        if len(out) > _MAX_CHAIN:
            raise XlsError("sector chain exceeds the cycle bound -- corrupt FAT")
        sector = fat[sector]
    return out


def read_ole2_streams(data: bytes) -> dict[str, bytes]:
    """Split an OLE2 compound file into ``{stream name: bytes}``.

    Streams SMALLER than the header's mini-stream cutoff (normally 4096 B) do not live in ordinary
    sectors at all -- they live in the miniFAT, inside the root entry's own stream. Miss that and
    small sheets vanish SILENTLY, with no error and no empty-file signal.
    """
    if len(data) < 512 or not data.startswith(_OLE_SIG):
        raise XlsError("not an OLE2 compound file (bad signature)")

    # VALIDATE THE EXPONENT, NOT THE SHIFTED VALUE. These fields are log2 sizes, so a corrupt
    # header turns `1 << n` into an integer with thousands of digits -- and the refusal below then
    # raised ValueError while FORMATTING it into its own error message ("Exceeds the limit (4300
    # digits) for integer string conversion"), escaping as a non-XlsError from a module whose
    # contract is that it raises XlsError on anything it cannot decode. Found by fuzzing: 9 escapes
    # in 4000 corrupted files, all of them this. The check has to happen before the shift.
    log_sector = _u16(data, 0x1E)
    log_mini = _u16(data, 0x20)
    if not 7 <= log_sector <= 20 or not 4 <= log_mini <= 20:
        raise XlsError(f"implausible sector size exponents: 2^{log_sector}/2^{log_mini}")
    sector_size = 1 << log_sector
    mini_size = 1 << log_mini
    n_fat = _u32(data, 0x2C)
    dir_start = _u32(data, 0x30)
    mini_cutoff = _u32(data, 0x38)
    minifat_start = _u32(data, 0x3C)
    difat_start = _u32(data, 0x44)
    n_difat = _u32(data, 0x48)
    if sector_size < 128 or mini_size < 16:
        raise XlsError(f"implausible sector sizes: {sector_size}/{mini_size}")

    def sector_bytes(index: int) -> bytes:
        off = (index + 1) * sector_size
        chunk = data[off : off + sector_size]
        if len(chunk) != sector_size:
            raise XlsError(f"sector {index} is truncated ({len(chunk)}/{sector_size} B)")
        return chunk

    # DIFAT: the first 109 FAT-sector pointers live in the header; the rest chain through
    # dedicated DIFAT sectors, each spending its LAST slot on the next DIFAT pointer.
    difat: list[int] = [_u32(data, 0x4C + 4 * i) for i in range(109)]
    per_difat = sector_size // 4 - 1
    sector = difat_start
    for _ in range(n_difat):
        if sector >= _MAXREGSECT:
            break
        block = sector_bytes(sector)
        difat.extend(_u32(block, 4 * i) for i in range(per_difat))
        sector = _u32(block, 4 * per_difat)

    fat: list[int] = []
    for fat_sector in difat[:n_fat]:
        if fat_sector >= _MAXREGSECT:
            continue
        block = sector_bytes(fat_sector)
        fat.extend(_u32(block, 4 * i) for i in range(sector_size // 4))
    if not fat:
        raise XlsError("compound file declares no FAT sectors")

    def read_chain(start: int, size: int) -> bytes:
        raw = b"".join(sector_bytes(s) for s in _chain(fat, start))
        if size and len(raw) < size:
            raise XlsError(f"stream chain is short ({len(raw)}/{size} B) -- truncated container")
        return raw[:size] if size else raw

    directory = read_chain(dir_start, 0)
    entries: list[tuple[str, int, int, int]] = []
    for off in range(0, len(directory) - _DIR_ENTRY_SIZE + 1, _DIR_ENTRY_SIZE):
        entry = directory[off : off + _DIR_ENTRY_SIZE]
        kind = entry[0x42]
        if kind not in (_DIR_TYPE_STREAM, _DIR_TYPE_ROOT):
            continue
        name_len = _u16(entry, 0x40)
        name = entry[: max(name_len - 2, 0)].decode("utf-16-le", "replace")
        entries.append((name, kind, _u32(entry, 0x74), _u32(entry, 0x78)))

    root = next((e for e in entries if e[1] == _DIR_TYPE_ROOT), None)
    if root is None:
        raise XlsError("compound file has no root directory entry")

    mini_stream = read_chain(root[2], root[3]) if root[3] else b""
    minifat: list[int] = []
    if minifat_start < _MAXREGSECT:
        raw = b"".join(sector_bytes(s) for s in _chain(fat, minifat_start))
        minifat = [_u32(raw, 4 * i) for i in range(len(raw) // 4)]

    def read_mini(start: int, size: int) -> bytes:
        """The mini path needs the SAME truncation refusal as ``sector_bytes``, and needs it more.

        Slicing past the end of the mini stream yields a SHORT bytes object rather than an error,
        so ``out[:size]`` quietly returned fewer bytes than the directory promised and the workbook
        lost its trailing rows with nothing raised anywhere. The conservation checks this module
        prescribes cannot catch it either: the rows that survive still balance perfectly, so a
        truncated sheet passes every in-data identity it is asked to satisfy. Granularity is what
        makes this the more exposed path -- 64-byte mini sectors against 512-byte big ones.
        """
        out = bytearray()
        for index in _chain(minifat, start):
            off = index * mini_size
            chunk = mini_stream[off : off + mini_size]
            if len(chunk) != mini_size:
                raise XlsError(
                    f"mini sector {index} is truncated ({len(chunk)}/{mini_size} B)"
                )
            out += chunk
        if len(out) < size:
            raise XlsError(f"mini stream is short ({len(out)}/{size} B) -- truncated container")
        return bytes(out[:size])

    streams: dict[str, bytes] = {}
    for name, kind, start, size in entries:
        if kind != _DIR_TYPE_STREAM or not size:
            continue
        streams[name] = read_mini(start, size) if size < mini_cutoff else read_chain(start, size)
    return streams


# ------------------------------------------------------------------------------ BIFF8 records ---
def _rk_to_number(raw: int) -> float:
    """Decode an RK-packed number.

    Bit 0 means "divide by 100"; bit 1 selects a signed 30-bit integer over the TOP HALF of an
    IEEE double. The integer branch must sign-extend -- reading it as unsigned turns every
    negative revision into a number near 2^30 that still looks like data.
    """
    if raw & 0x02:
        signed = int(struct.unpack("<i", struct.pack("<I", raw & 0xFFFFFFFC))[0]) >> 2
        value = float(signed)
    else:
        value = float(struct.unpack("<d", struct.pack("<Q", (raw & 0xFFFFFFFC) << 32))[0])
    return value / 100.0 if raw & 0x01 else value


class _SstReader:
    """Reads the shared-string table across ``CONTINUE`` boundaries -- bug (b) lives here.

    The table is one logical byte stream cut into records. A string may be split at any character
    boundary, and when it is, the continuation restarts with a FRESH 1-byte option flag whose
    compressed/wide bit may DIFFER from the one the string started with. So width is a property of
    the current segment, never of the string.
    """

    def __init__(self, chunks: list[bytes]) -> None:
        self._chunks = chunks
        self._i = 0
        self._pos = 0

    def _advance(self) -> bool:
        """Move to the next chunk holding bytes -- correct BETWEEN strings, never WITHIN one.

        A fresh string that happens to start in a new record carries no repeated flag byte, so
        skipping transparently is right here. Character data is the opposite case and is handled
        in :meth:`read_string`, which must consume that byte instead of reading it as text.
        """
        while self._i < len(self._chunks) and self._pos >= len(self._chunks[self._i]):
            self._i += 1
            self._pos = 0
        return self._i < len(self._chunks)

    def _exhausted(self) -> bool:
        return self._pos >= len(self._chunks[self._i])

    def _take(self, n: int) -> bytes:
        if not self._advance():
            raise XlsError("shared-string table ended mid-record")
        chunk = self._chunks[self._i]
        if self._pos + n > len(chunk):
            raise XlsError("shared-string header split across a CONTINUE boundary")
        out = chunk[self._pos : self._pos + n]
        self._pos += n
        return out

    def _remaining(self) -> int:
        return len(self._chunks[self._i]) - self._pos if self._advance() else 0

    def read_string(self) -> str:
        n_chars = int(struct.unpack("<H", self._take(2))[0])
        flags = self._take(1)[0]
        wide = bool(flags & 0x01)
        n_runs = int(struct.unpack("<H", self._take(2))[0]) if flags & 0x08 else 0
        ext_len = int(struct.unpack("<I", self._take(4))[0]) if flags & 0x04 else 0

        out: list[str] = []
        left = n_chars
        while left > 0:
            if self._i >= len(self._chunks):
                raise XlsError("shared-string table ended mid-string")
            if self._exhausted():
                # THE BOUNDARY, AND THE WHOLE REASON THIS CLASS EXISTS. Crossing a CONTINUE
                # record mid-string means the next byte is a REPEATED option flag, not text --
                # and its width bit may differ from the one this string started with. Advancing
                # transparently here reads that byte as a character: the count still works out,
                # so every following character shifts by one byte and the string silently
                # becomes mojibake with no error raised anywhere.
                self._i += 1
                self._pos = 0
                if self._i >= len(self._chunks):
                    raise XlsError("shared-string table ended mid-string")
                wide = bool(self._take(1)[0] & 0x01)
                continue
            width = 2 if wide else 1
            take = min(left, self._remaining() // width)
            if take <= 0:
                # A wide segment with one dangling byte cannot hold a character: it is a
                # boundary, so fall through to the branch above rather than reading half of one.
                self._pos = len(self._chunks[self._i])
                continue
            raw = self._take(take * width)
            out.append(raw.decode("utf-16-le" if wide else "latin-1"))
            left -= take

        for _ in range(n_runs):
            self._take(4)
        if ext_len:
            self._take(ext_len)
        return "".join(out)


def _unicode_string(payload: bytes, off: int) -> str:
    """Decode an inline BIFF8 ``XLUnicodeRichExtendedString`` (LABEL).

    THE RICH-TEXT AND PHONETIC FIELDS SIT BETWEEN THE FLAGS AND THE CHARACTERS. ``cRun`` (2 bytes,
    when fRichSt is set) and ``cbExtRst`` (4 bytes, when fExtSt is set) are counted here, exactly
    as :meth:`_SstReader.read_string` counts them for the shared-string table. Jumping straight
    from the flag byte to the text reads those headers AS text: the character count still works
    out, so the string comes back shortened and prefixed with binary and nothing raises -- the
    same silence signature as the CONTINUE bug. Excel itself prefers LABELSST, so a bare LABEL
    tends to come from a third-party writer, which is precisely the kind that sets these bits.
    """
    if off + 3 > len(payload):
        raise XlsError("inline string header runs past the end of its record")
    n_chars = _u16(payload, off)
    flags = payload[off + 2]
    cursor = off + 3 + (2 if flags & 0x08 else 0) + (4 if flags & 0x04 else 0)
    body = payload[cursor:]
    if flags & 0x01:
        return body[: n_chars * 2].decode("utf-16-le", "replace")
    return body[:n_chars].decode("latin-1")


def _short_string(payload: bytes, off: int) -> str:
    """BOUNDSHEET carries an 8-bit length, not the 16-bit one every other record uses."""
    n_chars = payload[off]
    flags = payload[off + 1]
    body = payload[off + 2 :]
    if flags & 0x01:
        return body[: n_chars * 2].decode("utf-16-le", "replace")
    return body[:n_chars].decode("latin-1")


def _coord(row: int, col: int) -> tuple[int, int]:
    """Refuse a cell coordinate outside the BIFF8 grid rather than densifying it later."""
    if col >= _MAX_COLS:
        raise XlsError(
            f"cell column {col} is outside the BIFF8 grid (max {_MAX_COLS - 1}) -- misread record"
        )
    return row, col


def _records(stream: bytes) -> list[tuple[int, int, bytes]]:
    """Walk the record stream, yielding ``(absolute offset, opcode, payload)``.

    The offset is not decoration: it is the ONLY thing that attributes a cell to a sheet.
    """
    out: list[tuple[int, int, bytes]] = []
    pos = 0
    while pos + 4 <= len(stream):
        opcode = _u16(stream, pos)
        length = _u16(stream, pos + 2)
        if pos + 4 + length > len(stream):
            raise XlsError(f"record 0x{opcode:04X} at {pos} runs past the end of the stream")
        out.append((pos, opcode, stream[pos + 4 : pos + 4 + length]))
        pos += 4 + length
    if pos != len(stream):
        # A BIFF stream is records end to end and the directory records its exact length, so
        # leftover bytes mean the stream was truncated -- and 1-3 of them are the dangerous
        # amount, because they are too short to be a header and a `pos + 4 <= len` walk simply
        # stops on them. That drops a record with no error at all, which is the truncation
        # failure mode that never throws: every number already read still looks right.
        raise XlsError(
            f"stream does not end on a record boundary: {len(stream) - pos} trailing byte(s) "
            f"after the last complete record -- truncated or not a BIFF stream"
        )
    return out


def _parse_biff(stream: bytes) -> list[Sheet]:
    records = _records(stream)
    if not records or records[0][1] != _BOF:
        raise XlsError("workbook stream does not start with a BOF record")
    version = _u16(records[0][2], 0) if len(records[0][2]) >= 2 else 0
    if version != _BIFF8_VERSION:
        raise XlsError(
            f"unsupported BIFF version 0x{version:04X} -- only BIFF8 (0x0600) is decoded; "
            "a 'Book' stream from Excel 5/95 needs a different record layout"
        )

    # ENCRYPTION IS INVISIBLE FROM THE PAYLOADS. BIFF8 RC4 leaves every record HEADER in plaintext
    # and encrypts only the bodies, so the record walk above succeeds perfectly and each payload
    # decodes into a number that is pure ciphertext -- measured on a scrambled fixture, the reader
    # returned {(23130, 23130): 1.779e+127} with the sheet name intact and refused nothing. This
    # includes the write-protected files Excel opens transparently with the standard password, so
    # it is not an exotic input. Every mainstream BIFF reader refuses here, and so does this one.
    if any(opcode == _FILEPASS for _, opcode, _ in records):
        raise XlsError(
            "workbook is encrypted (FILEPASS record) -- BIFF8 leaves record headers in plaintext, "
            "so decoding would return ciphertext as plausible numbers rather than failing"
        )

    # Pass 1: sheet directory and the shared-string table, both of which live in the globals
    # substream and must be complete before any cell record can be interpreted.
    boundsheets: list[tuple[int, str]] = []
    sst: list[str] = []
    sst_chunks: list[bytes] = []
    collecting = False
    for _, opcode, payload in records:
        if opcode == _BOUNDSHEET:
            boundsheets.append((_u32(payload, 0), _short_string(payload, 6)))
            collecting = False
        elif opcode == _SST:
            if len(payload) < 8:
                raise XlsError("SST record is too short to carry its own header")
            sst_chunks = [payload[8:]]
            collecting = True
        elif opcode == _CONTINUE and collecting:
            sst_chunks.append(payload)
        elif opcode != _CONTINUE:
            collecting = False
    if sst_chunks:
        reader = _SstReader(sst_chunks)
        n_unique = _u32(records[[r[1] for r in records].index(_SST)][2], 4)
        for _ in range(n_unique):
            sst.append(reader.read_string())

    if not boundsheets:
        raise XlsError("workbook declares no sheets (no BOUNDSHEET record)")
    # TWO DIFFERENT ORDERS, AND CONFLATING THEM SILENTLY RENUMBERS THE TABS. Excel's tab order is
    # BOUNDSHEET DECLARATION order; the order the substreams happen to be laid out in the stream is
    # not required to match it. `sheet_of` genuinely needs offsets ascending to attribute a record,
    # but sorting the list that is also RETURNED means `--sheet 0` hands back whichever sheet was
    # written first rather than the one Excel shows first. Names travel with their grids, so
    # selection BY NAME was always safe and only index selection was wrong -- which is the quiet
    # kind: a caller asking for sheet 0 gets a real sheet full of real numbers, just not that one.
    by_offset = sorted(range(len(boundsheets)), key=lambda i: boundsheets[i][0])
    starts = [boundsheets[i][0] for i in by_offset]
    cells: list[dict[tuple[int, int], object]] = [{} for _ in boundsheets]

    def sheet_of(offset: int) -> int:
        """Attribute a record to a sheet by absolute offset -- never by record order (bug a).

        Returns an index into ``boundsheets`` (declaration order), not into the offset-sorted scan.
        """
        index = -1
        for rank, start in enumerate(starts):
            if offset >= start:
                index = by_offset[rank]
            else:
                break
        return index

    # Pass 2: cells. A record before the first sheet's BOF belongs to the globals substream and is
    # deliberately dropped rather than folded into sheet 0.
    for offset, opcode, payload in records:
        index = sheet_of(offset)
        if index < 0 or opcode in (_BOF, _EOF):
            continue
        grid = cells[index]
        if opcode == _NUMBER and len(payload) >= 14:
            grid[_coord(_u16(payload, 0), _u16(payload, 2))] = float(
                struct.unpack_from("<d", payload, 6)[0]
            )
        elif opcode == _RK and len(payload) >= 10:
            grid[_coord(_u16(payload, 0), _u16(payload, 2))] = _rk_to_number(_u32(payload, 6))
        elif opcode == _MULRK and len(payload) >= 6:
            row = _u16(payload, 0)
            first = _u16(payload, 2)
            for n in range((len(payload) - 6) // 6):
                grid[_coord(row, first + n)] = _rk_to_number(_u32(payload, 4 + 6 * n + 2))
        elif opcode == _LABELSST and len(payload) >= 10:
            index_sst = _u32(payload, 6)
            if index_sst >= len(sst):
                # Storing None here would hand back a grid with a hole in it, from a module whose
                # contract is that it never returns a partial workbook. An index past the table is
                # a misread SST, not a blank cell.
                raise XlsError(
                    f"LABELSST references string {index_sst} of {len(sst)} -- shared-string table "
                    f"is short or was misread"
                )
            grid[_coord(_u16(payload, 0), _u16(payload, 2))] = sst[index_sst]
        elif opcode == _LABEL and len(payload) >= 9:
            grid[_coord(_u16(payload, 0), _u16(payload, 2))] = _unicode_string(payload, 6)
        elif opcode == _FORMULA and len(payload) >= 20:
            # Only the CACHED result is read. 0xFFFF in the high word marks a non-numeric result
            # (string/bool/error) whose value lives in a following record -- refused, not guessed.
            if _u16(payload, 12) != 0xFFFF:
                grid[_coord(_u16(payload, 0), _u16(payload, 2))] = float(
                    struct.unpack_from("<d", payload, 6)[0]
                )
        elif opcode == _BOOLERR and len(payload) >= 8 and payload[7] == 0:
            grid[_coord(_u16(payload, 0), _u16(payload, 2))] = bool(payload[6])

    paired = zip(boundsheets, cells, strict=True)
    return [Sheet(name=name, cells=grid) for (_, name), grid in paired]


def read_xls(src: Path | bytes) -> list[Sheet]:
    """Read a legacy ``.xls`` into sheets, in workbook order.

    Raises :class:`XlsError` on anything it cannot decode faithfully. It never returns a partial
    workbook: a half-parsed grid is the outcome most likely to pass a downstream sanity check
    while being wrong, which is the failure mode this whole module exists to avoid.
    """
    data = src.read_bytes() if isinstance(src, Path) else src
    streams = read_ole2_streams(data)
    for name in ("Workbook", "Book"):
        if name in streams:
            return _parse_biff(streams[name])
    raise XlsError(f"no Workbook stream; found {sorted(streams) or 'no streams'}")

```

### libs\regime\state_admission.py
```python
"""Which state dimensions have earned the right to condition capital, and which have not.

THE RULE THIS ENFORCES (principal, 2026-09-04): "no new regime variable gets capital authority
merely because it sounds sensible. It enters as information, gets PIT-tested, must improve
forecast calibration or marginal E[log W], and otherwise goes to the graveyard."

Without this, a state vector is an invitation to overfit. Session phase, event phase, liquidity
state, per-asset regime, global regime, regime age -- every one of them sounds sensible, every one
of them slices the same finite evidence thinner, and the desk has no way to tell which of them is
carrying information from which of them is carrying noise that happens to be labelled.

HOW A DIMENSION IS JUDGED. Walk-forward, on the desk's own realised trades. For each block:

    fit    on the training trades, the per-bucket mean, shrunk toward the pooled mean by n/(n+k)
    score  each TEST trade twice -- once predicted by the pooled mean, once by its bucket's
    keep   the difference in squared error, per trade

A dimension is only better if it predicts trades it has never seen. Fitting bucket means and
admiring the in-sample fit is how every one of these dimensions would pass.

SLEEVE EFFECTS ARE REMOVED FIRST. Pooling raw returns across sleeves would let a dimension look
informative purely because one profitable sleeve trades mostly in one bucket. Each sleeve's
returns are centred on its own training mean, so what is measured is whether the STATE explains
variation the sleeve identity does not.

THREE VERDICTS, and the middle one is not a pass:

    ADMIT           measurably better out of sample, after deflation for how many dimensions
                    were tried. May condition the posterior.
    RETAIN_SHRUNK   too little evidence to say. The dimension keeps whatever access it already
                    has, and the ONLY reason that is safe is `robust_elog`'s k_state = 40: a
                    bucket needs forty observations to outweigh the unconditional posterior, so
                    an unproven dimension moves the estimate barely at all. This is a stay of
                    execution granted by the shrinkage, not a verdict in the dimension's favour,
                    and it should be revisited as the ledgers fill.
    GRAVEYARD       measurably WORSE out of sample. Removed from conditioning.

DEFLATION, because this is itself a search. Testing eight dimensions and reporting the best one's
t-statistic is the same error the gauntlet's deflated Sharpe exists to correct, so the paired t on
the per-trade error difference is deflated by E[max_N Z] over the dimensions tried.
"""
from __future__ import annotations

import math
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, cast

import numpy as np

#: The bar store the `rvol` labeller reads a trade's OWN symbol history from. Module-level so a
#: test can point it at a synthetic universe rather than the desk's.
UNIVERSE = Path(__file__).resolve().parents[2] / "desks" / "mt5" / "data" / "universe"
#: Trailing bars of log return one realised-vol reading is measured over: a broker day on H1.
RVOL_WINDOW = 24
#: Realised-vol readings a symbol must have BEFORE a trade for its quintile to be a quintile
#: rather than a rank among a handful. Ten days of hourly readings.
RVOL_MIN_HISTORY = 240
RVOL_QUINTILES: tuple[str, ...] = ("Q1_LOW", "Q2", "Q3", "Q4", "Q5_HIGH")

#: Shrinkage of a bucket mean toward the pooled mean, matching `robust_elog`'s k_state so the
#: test measures the estimator the allocator would actually use rather than a sharper one.
K_BUCKET = 40.0
#: Test-fold trades needed before a verdict is possible at all.
MIN_TEST_TRADES = 150
#: Trades a bucket needs in training before it may be used to predict anything.
MIN_BUCKET_TRAIN = 15
#: Deflated t a dimension must clear to be ADMITted, and to be sent to the GRAVEYARD.
ADMIT_T = 2.0
GRAVEYARD_T = -2.0
#: Walk-forward blocks. Three is the fewest that has both a fit and more than one score.
N_BLOCKS = 4

ADMIT = "ADMIT"
RETAIN_SHRUNK = "RETAIN_SHRUNK"
GRAVEYARD = "GRAVEYARD"
UNJUDGED = "UNJUDGED"


@dataclass(frozen=True)
class Trade:
    """One realised trade, with the state it was taken in."""

    sleeve: str
    when: str
    r: float
    #: dimension name -> bucket label for this trade.
    buckets: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class Verdict:
    dimension: str
    verdict: str
    #: Mean reduction in squared error from conditioning. Positive is better.
    mse_gain: float
    t_paired: float
    t_deflated: float
    n_test: int
    n_buckets: int
    dimensions_tried: int
    why: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {"dimension": self.dimension, "verdict": self.verdict,
                "mse_gain": round(self.mse_gain, 10), "t_paired": round(self.t_paired, 4),
                "t_deflated": round(self.t_deflated, 4), "n_test": self.n_test,
                "n_buckets": self.n_buckets, "dimensions_tried": self.dimensions_tried,
                "why": self.why}


def _expected_max_z(n: int) -> float:
    if n <= 1:
        return 0.0
    ln = math.log(n)
    if ln <= 0:
        return 0.0
    return math.sqrt(2 * ln) - (math.log(ln) + math.log(4 * math.pi)) / (2 * math.sqrt(2 * ln))


def _blocks(n: int, k: int) -> list[tuple[int, int]]:
    """Expanding-window folds: train on everything before, score the next slice."""
    if n < k * 2:
        return []
    edges = [round(n * i / k) for i in range(k + 1)]
    return [(edges[i], edges[i + 1]) for i in range(1, k)]


def judge(trades: Sequence[Trade], dimension: str, dimensions_tried: int = 1,
          k_bucket: float = K_BUCKET) -> Verdict:
    """Walk-forward: does conditioning on `dimension` predict unseen trades better?"""
    rows = [t for t in sorted(trades, key=lambda x: x.when) if dimension in t.buckets]
    n = len(rows)
    folds = _blocks(n, N_BLOCKS)
    if not folds:
        return Verdict(dimension, UNJUDGED, 0.0, 0.0, 0.0, 0, 0, dimensions_tried,
                       why=f"{n} trades carry this dimension; too few for {N_BLOCKS} folds")

    diffs: list[float] = []
    buckets_seen: set[str] = set()
    for start, stop in folds:
        train, test = rows[:start], rows[start:stop]
        if not train or not test:
            continue
        # SLEEVE EFFECTS OUT FIRST. A dimension must explain variation the sleeve identity does
        # not, or a single profitable sleeve concentrated in one bucket makes it look informative.
        by_sleeve: dict[str, list[float]] = {}
        for t in train:
            by_sleeve.setdefault(t.sleeve, []).append(t.r)
        sleeve_mean = {k: float(np.mean(v)) for k, v in by_sleeve.items()}
        centred = [t.r - sleeve_mean.get(t.sleeve, 0.0) for t in train]
        pooled = float(np.mean(centred)) if centred else 0.0

        agg: dict[str, list[float]] = {}
        for t, c in zip(train, centred, strict=True):
            agg.setdefault(t.buckets[dimension], []).append(c)
        shrunk = {}
        for b, vals in agg.items():
            if len(vals) < MIN_BUCKET_TRAIN:
                continue
            lam = len(vals) / (len(vals) + k_bucket)
            shrunk[b] = lam * float(np.mean(vals)) + (1.0 - lam) * pooled
            buckets_seen.add(b)

        for t in test:
            if t.sleeve not in sleeve_mean:
                continue                     # a sleeve never seen in training explains nothing
            y = t.r - sleeve_mean[t.sleeve]
            b = t.buckets[dimension]
            if b not in shrunk:
                continue                     # an unseen bucket is not a prediction
            diffs.append((y - pooled) ** 2 - (y - shrunk[b]) ** 2)

    n_test = len(diffs)
    # A DIMENSION THAT NEVER VARIES IS NOT A DIMENSION. If every trade in training fell into one
    # bucket, the "conditional" mean IS the pooled mean and the test returns t = 0.00 -- which
    # reads as "measured, no effect" when the truth is "nothing was measured". Seen live: `event`
    # scored t=+0.00 on 336 predictions with buckets=1, because the calendar vintages the miner
    # keeps span days while the ledgers span months, so every trade was labelled NORMAL.
    if len(buckets_seen) < 2:
        return Verdict(dimension, UNJUDGED, 0.0, 0.0, 0.0, n_test, len(buckets_seen),
                       dimensions_tried,
                       why=(f"only {len(buckets_seen)} bucket ever had "
                            f"{MIN_BUCKET_TRAIN} training trades, so conditioning on this is "
                            "arithmetically identical to not conditioning. NOT a null result -- "
                            "the dimension's history does not cover the trades."))
    if n_test < MIN_TEST_TRADES:
        return Verdict(dimension, RETAIN_SHRUNK, float(np.mean(diffs)) if diffs else 0.0,
                       0.0, 0.0, n_test, len(buckets_seen), dimensions_tried,
                       why=(f"{n_test} out-of-sample predictions, needs {MIN_TEST_TRADES}. "
                            "UNDERPOWERED, not passed -- what makes keeping it safe is the "
                            f"k_state={k_bucket:.0f} shrinkage, which leaves an unproven bucket "
                            "barely able to move the posterior."))

    arr = np.asarray(diffs, dtype=float)
    sd = float(arr.std(ddof=1))
    gain = float(arr.mean())
    tstat = gain / (sd / math.sqrt(arr.size)) if sd > 0 else 0.0
    t_def = tstat - _expected_max_z(max(1, dimensions_tried)) if tstat > 0 else tstat
    if t_def >= ADMIT_T:
        verdict, why = ADMIT, "predicts unseen trades better, after deflation for the search"
    elif tstat <= GRAVEYARD_T:
        verdict, why = GRAVEYARD, "measurably worse out of sample; conditioning on it adds noise"
    else:
        verdict, why = RETAIN_SHRUNK, "no measurable improvement; kept only by the shrinkage"
    return Verdict(dimension, verdict, gain, tstat, t_def, n_test, len(buckets_seen),
                   dimensions_tried, why=why)


def judge_all(trades: Sequence[Trade], dimensions: Sequence[str],
              k_bucket: float = K_BUCKET) -> dict[str, Verdict]:
    """Judge every dimension against the same trades, each charged for the whole search."""
    tried = len(dimensions)
    return {d: judge(trades, d, dimensions_tried=tried, k_bucket=k_bucket) for d in dimensions}


def admitted(verdicts: dict[str, Verdict]) -> tuple[str, ...]:
    """Dimensions that may condition the posterior: everything not sent to the graveyard.

    RETAIN_SHRUNK is included on purpose and it is the conservative choice, not the permissive
    one: those dimensions already condition today, and removing a dimension on the strength of a
    test that reports it has no power would be substituting one unmeasured decision for another.
    Only a MEASURED failure removes access.
    """
    return tuple(sorted(d for d, v in verdicts.items() if v.verdict != GRAVEYARD))


def build_labeller(name: str) -> Callable[[Trade], str] | None:
    """A function from a trade to this dimension's bucket, or None when it cannot be rebuilt.

    ONLY DIMENSIONS RECONSTRUCTIBLE AT THE TRADE'S OWN MOMENT LIVE HERE. Labelling a trade from
    January with today's regime fit, today's spread percentile or today's calendar would test
    whether the PRESENT predicts the past, which every dimension would pass. An asset's regime
    needs the walk-forward decode `family_regime_transition` builds; the liquidity state needs the
    historical tape; both are recorded as gaps until their history is joined rather than faked
    from a current reading.

    `rvol` (Tier-1 audit G6, 2026-09-08) is the fourth dimension and the first built from the
    trade's own SYMBOL BARS: the quintile of the trailing `RVOL_WINDOW`-bar realised vol, ranked
    among every reading that symbol had produced BEFORE the trade -- an expanding percentile, so
    the rank at a January trade is January's rank, never the full sample's. The bar used is the
    last one stamped strictly before the trade's timestamp: a trade entered at the open of the
    13:00 bar reads the 12:00 bar's close and nothing later.
    """
    if name == "session":
        try:
            from research.session_phase import (  # type: ignore[import-not-found]
                broker_utc_offset_h,
                phase_at,
            )
        except ImportError:
            return None
        off, _src = broker_utc_offset_h()
        if off is None:
            return None

        def _session(t: Trade) -> str:
            from datetime import datetime
            try:
                return str(phase_at(datetime.fromisoformat(t.when), broker_utc_offset_h=off))
            except (TypeError, ValueError):
                return ""
        return _session

    if name == "weekday":
        def _weekday(t: Trade) -> str:
            from datetime import datetime
            try:
                return datetime.fromisoformat(t.when).strftime("%a")
            except (TypeError, ValueError):
                return ""
        return _weekday

    if name in ("dollar", "risk", "rates", "real_rates", "curve", "liquidity"):
        # THE MACRO STATE, POINT-IN-TIME (2026-09-16). Each is the trailing-year percentile rank
        # of a FRED level as of the day BEFORE the trade, bucketed into terciles, so a print
        # released the evening of the trade cannot label it. The allocator already conditions
        # its posterior on the same state through a kernel (`libs.portfolio.macro_state`); this
        # is the walk-forward judgement of whether that conditioning predicts trades it has never
        # seen, on the desk's own realised record -- the same graveyard every other dimension
        # faces, and the only thing that can bury it.
        try:
            from libs.portfolio.macro_state import labeller as _macro_labeller
        except ImportError:
            return None
        fn = _macro_labeller(name)
        if fn is None:
            return None

        def _macro(t: Trade) -> str:
            return fn(t.when)
        return _macro

    if name == "event":
        # POINT-IN-TIME BY CONSTRUCTION. The calendar rows carry the SCHEDULED stamp of each
        # release, so a trade from January is classified against the releases around January.
        # This is the one new state dimension whose history the desk already holds.
        try:
            from libs.regime.event_state import classify, parse_rows, relevant
        except ImportError:
            return None
        rows = _calendar()
        if not rows:
            return None
        meta = _universe_meta()
        parsed = parse_rows(rows)
        if not parsed:
            return None

        def _event(t: Trade) -> str:
            from datetime import datetime
            try:
                when = datetime.fromisoformat(t.when)
            except (TypeError, ValueError):
                return ""
            scoped = relevant(parsed, _symbol_of(t.sleeve), meta)
            if not scoped:
                return ""
            return classify(when, [r["_stamp"] for r in scoped],
                            symbol=_symbol_of(t.sleeve), rows=scoped).phase
        return _event

    if name == "rvol":
        try:
            import pandas as pd
        except ImportError:
            return None
        if not UNIVERSE.is_dir():
            return None
        cache: dict[str, Any] = {}

        def _pct(sym: str) -> Any:
            """The symbol's point-in-time realised-vol percentile series, loaded once."""
            if sym in cache:
                return cache[sym]
            out = None
            path = UNIVERSE / f"{sym}_H1.parquet"
            if path.exists():
                try:
                    df = pd.read_parquet(path, columns=["close"])
                    idx = pd.DatetimeIndex(pd.to_datetime(df.index, utc=True, errors="coerce"))
                    s = pd.Series(df["close"].to_numpy(dtype=float), index=idx).dropna()
                    s = s[~s.index.isna()].sort_index()
                    s = s[~s.index.duplicated(keep="last")]
                    if len(s) > RVOL_MIN_HISTORY + RVOL_WINDOW:
                        out = rvol_percentiles(s)
                except (OSError, ValueError, KeyError, ImportError):
                    out = None
            cache[sym] = out
            return out

        def _rvol(t: Trade) -> str:
            sym = _symbol_of(t.sleeve)
            pct = _pct(sym) if sym else None
            if pct is None:
                return ""
            try:
                when = pd.Timestamp(t.when)
            except (TypeError, ValueError):
                return ""
            when = when.tz_localize("UTC") if when.tzinfo is None else when.tz_convert("UTC")
            pos = int(pct.index.searchsorted(when, side="left")) - 1   # strictly before
            if pos < 0:
                return ""
            return rvol_bucket(float(pct.iloc[pos]))
        return _rvol
    return None


def rvol_percentiles(close: Any, window: int = RVOL_WINDOW,
                     min_history: int = RVOL_MIN_HISTORY) -> Any:
    """Per bar: the trailing `window`-bar realised vol's percentile among every reading up to
    and including that bar. Expanding, never full-sample: the rank at bar t cannot see t+1."""
    r = np.log(close.astype(float)).diff()
    rv = r.rolling(int(window), min_periods=int(window)).std(ddof=1)
    return rv.expanding(min_periods=int(min_history)).rank(pct=True)


def rvol_bucket(pct: float) -> str:
    """A percentile in (0, 1] to its quintile name; NaN (too little history) is no label."""
    if not math.isfinite(pct):
        return ""
    return RVOL_QUINTILES[min(len(RVOL_QUINTILES) - 1, max(0, int(pct * len(RVOL_QUINTILES))))]


def _symbol_of(sleeve: str) -> str:
    """The instrument a sleeve name is about. Ledgers are `<SYM>_<family>_<window>`."""
    head = str(sleeve or "").split("_")[0]
    return head.upper() if head else ""


def _calendar() -> list[dict[str, Any]]:
    import json
    from pathlib import Path

    root = Path(__file__).resolve().parents[2] / "desks" / "mt5" / "data" / "intelligence" \
        / "ff_calendar_vintage"
    if not root.exists():
        return []
    out, seen = [], set()
    for path in sorted(root.glob("*.json"))[-60:]:
        try:
            doc = json.loads(path.read_text("utf-8"))
        except (OSError, ValueError):
            continue
        rows = doc if isinstance(doc, list) else (doc.get("rows") or doc.get("discoveries") or [])
        for row in rows if isinstance(rows, list) else []:
            if not isinstance(row, dict):
                continue
            key = f"{row.get('event_date')}|{row.get('title')}"
            if key not in seen:
                seen.add(key)
                out.append(row)
    return out


def _universe_meta() -> dict[str, Any]:
    import json
    from pathlib import Path

    p = (Path(__file__).resolve().parents[2] / "desks" / "mt5" / "data" / "universe"
         / "universe.json")
    try:
        return cast("dict[str, Any]", json.loads(p.read_text("utf-8")))
    except (OSError, ValueError):
        return {}

```

### libs\research\capacity_policy.py
```python
"""THE desk's capacity policy: one leaf module, one definition of what capacity is worth.

Capacity is judged as SUFFICIENCY for the book actually deployed, never as magnitude. That single
rule has to hold in the survival gate, in both rank scorers, in acceptance and in the audit --
which is exactly why they now all call in here instead of each carrying their own dollar constant.

WHY A LEAF. Five copies of this policy existed and they disagreed; fixing the gate in isolation on
2026-07-26 left the other four intact, so the exclusion simply moved to where it was harder to
see. This module therefore imports NOTHING from libs beyond a lazy, exception-guarded read of the
ThresholdBook -- so nothing can ever be "too circular to import the real policy" and be tempted to
re-inline its own copy. That constraint is load-bearing, not stylistic; keep it.

The survival gate was fixed on 2026-07-26 to stop hard-rejecting sub-$100k edges (capacity is a
ratio to deployed equity, not a dollar figure). That removed a categorical EXCLUSION. It did not
give the niche PARITY, because four separate scorers still rewarded bigger capacity monotonically:

    libs/discovery/objective.py     capacity_term = min(1, cap/1e6)          -> 1.9x rank penalty
    libs/research/alpha_economics.py capacity_f   = min(cap/1e6, 5)**0.25    -> 3.2x EV penalty
    libs/discovery/factory.py       capacity_pass = cap >= 1e5          -> the flat floor, again
    libs/alpha_factory/capacity_intelligence.py  scalability = cap/reference -> monotone in size

So a $50k-capacity listing dislocation could pass the gate and still lose every ranking to a
fund-shaped idea it beats on every dimension that pays. Being ALLOWED into the niche while being
SCORED out of it is not parity -- it is the same exclusion moved one layer down, where it is
harder to see. This module is the single scorer all four now share.

THE ECONOMICS. Capacity is worth exactly what it lets you deploy and not one dollar more. Once an
edge absorbs several multiples of the equity you have, additional capacity buys you NOTHING you
can spend -- a $200k edge and a $200M edge are identical to a $50k book. Rewarding the $200M edge
is not caution, it is preferring an option you cannot exercise. The score is therefore:

    ramp to sufficiency  ->  FLAT (parity)  ->  bounded crowding discount

The flat region IS the parity: above the headroom requirement, size stops being a tiebreaker and
the edge is judged on Sharpe, orthogonality and persistence like everything else.

NO TILT IN EITHER DIRECTION (principal 2026-07-26). A first pass discounted fund-scale capacity as
a crowding prior. The principal struck it, and the reasoning is better than mine: the objective is
the MAXIMUM NUMBER OF SIMULTANEOUS UNCORRELATED ALPHAS, because that is what compounds -- not a
preferred size of alpha. Discounting large edges is being picky about the shape of an edge rather
than about whether it pays, and every sleeve declined for its size is geometric growth foregone. It
was also DOUBLE-COUNTING: crowding is already priced by the ``crowded_known`` prior in
alpha_economics and re-tested by DSR, PBO and persistence, so charging it again in the capacity
term punished big edges twice for one fact.

The score is therefore FLAT for everything fillable, full stop. The mechanism survives, defaulted
to neutral and bounded in the ThresholdBook, so that MEASURED decay-versus-capacity evidence could
reintroduce a discount later -- evidence may move it, preference may not.

WHAT REPLACES THE TILT. Not a preference but an EXPIRY: an edge is deployed while it is fillable
and retired when the book genuinely outgrows it (``outgrown_at`` / ``growth_runway``). Small edges
are not favoured, they are simply first to expire -- and the expiry is a date on a calendar rather
than a thumb on a scale. Both bands are hunted, both are run, and the only thing that ever stops a
sleeve is the arithmetic of the book passing its capacity.
"""

from __future__ import annotations

import json
import math
from datetime import UTC, datetime
from pathlib import Path

__all__ = [
    "DEFAULT_BOOK_USD",
    "DEFAULT_SLEEVES",
    "capacity_band",
    "capacity_fit",
    "capacity_required",
    "declared_allocation",
    "growth_runway",
    "live_book_usd",
    "live_sleeves",
    "max_allocation",
    "niche_share",
    "outgrown_at",
    "sleeve_equity",
    "venue_book_usd",
    "venue_min_notional_usd",
]

#: CAPACITY IS A RATIO, NOT A DOLLAR FIGURE (2026-07-26). The gate was a flat $100,000 floor, which
#: hard-rejected every edge too small to absorb six figures -- i.e. exactly the capacity-bound
#: niche `docs/research/PROSPECTOR_SPEC.md` calls "this desk's ONE structural advantage" (the edges
#: a fund abandoned for being too small). A perfect $20k-capacity listing dislocation failed the
#: gate on capacity alone, whatever its DSR. The gate's real job is to stop the desk being a large
#: share of its OWN edge's capacity -- a ratio to deployed equity, which protects a $5k book and a
#: $5M book alike. Both bounds live in the ThresholdBook: bounded and evidence-adjustable, never
#: hand-edited.
_CAPACITY_FALLBACK_MULT = 4.0        # need 4x headroom over what is actually deployed
_CAPACITY_FALLBACK_FLOOR = 2_000.0   # below this it is a rounding error at any book size
#: ABSOLUTE capacity above which institutional competition would be assumed, IF a discount were
#: applied. Absolute rather than a multiple of our book, because whether an edge is crowded is a
#: fact about the market. Retained only as the band boundary for reporting -- see _CROWD_FLOOR.
_CROWD_START_USD = 10_000_000.0
#: Crowding discount floor. DEFAULT 1.0 = NO DISCOUNT (principal 2026-07-26): every fillable edge
#: scores the same, because the objective is the maximum number of simultaneous uncorrelated
#: alphas, and a sleeve declined for its size is compounding foregone. Kept as a live, bounded
#: knob so MEASURED decay-vs-capacity evidence could reintroduce a discount -- never a preference.
_CROWD_FLOOR = 1.0
#: Book size assumed when the caller does not say. NOT a fund's number -- see §42.
DEFAULT_BOOK_USD = 50_000.0
#: NO SINGLE EDGE GETS THE WHOLE BOOK. Judging every candidate against the full $50k silently
#: assumes an all-in one-strategy desk -- the opposite of how this one runs -- and inflates the
#: requirement by the sleeve count, pushing genuinely tradeable small edges back into "unfillable".
#: That is the flat-$100k-floor bug in miniature, so the divisor is explicit rather than implied.
DEFAULT_SLEEVES = 8

_STORE = Path(__file__).resolve().parents[2] / "data/adaptive_thresholds.json"


def _tunable(name: str, fallback: float) -> float:
    """Bounded, evidence-adjustable value -- falls back to the constant if anything is wrong.

    Deliberately lazy and exception-guarded: this module must stay importable from anywhere in the
    dependency graph, so a broken or missing store degrades to the documented default instead of
    taking the capacity policy (and therefore every gate that reads it) down with it.
    """
    try:
        from libs.self_improvement.adaptive_thresholds import ThresholdBook
        return ThresholdBook(_STORE).get(name)
    except Exception:
        return fallback


def sleeve_equity(book_usd: float, n_sleeves: int = 1) -> float:
    """Equity a SINGLE edge is actually filled with -- the book split across concurrent sleeves."""
    return max(0.0, float(book_usd)) / max(1, int(n_sleeves))


def declared_allocation(sleeve: str | None) -> float | None:
    """This sleeve's DECLARED funding, if it committed to one -- else None (equal weight applies).

    Lazy and exception-guarded because `sleeve_allocations` imports THIS module; a top-level import
    would be a cycle. Same discipline as `_tunable`: the policy module stays a leaf, and a missing
    or broken store degrades to "no declaration" rather than taking every scorer down with it.

    A None here is the SAFE direction: no declaration means the caller falls back to equal weight,
    which is the stricter assumption. The unsafe direction -- a declaration that lets an edge
    through -- is the one the audit reconciles against real funding.
    """
    if not sleeve:
        return None
    try:
        from libs.research.sleeve_allocations import load
        for a in load(Path(__file__).resolve().parents[2] / "data/sleeve_allocations.json"):
            if a.sleeve == sleeve:
                return a.declared_usd if a.self_consistent else None
    except Exception:
        return None
    return None


def max_allocation(capacity_usd: float) -> float:
    """Most the desk may EVER put into this edge -- the requirement, read the other way round.

    ``capacity_required`` answers "how big must an edge be for my allocation?"; this answers "how
    big may my allocation be for this edge?". Same rule, same headroom multiple, one inverse -- and
    it is a separate function only because the sizer needs the second form and re-deriving it there
    is precisely how five disagreeing copies of this policy appeared last time.

    NOTE THE FACTOR. At 4x headroom this is 25% of capacity, NOT 100%. You never fill an edge to
    its stated capacity: capacity is where impact has already eaten the edge, so trading up to it
    means arriving exactly when there is nothing left to collect.
    """
    mult = max(1e-9, _tunable("capacity_headroom_mult", _CAPACITY_FALLBACK_MULT))
    return max(0.0, float(capacity_usd)) / mult


def capacity_required(deployed_equity_usd: float, n_sleeves: int = 1) -> float:
    """Minimum absorbable capacity for a candidate, given what the desk actually deploys.

    ``n_sleeves`` defaults to 1, which reads ``deployed_equity_usd`` as the equity going into THIS
    one edge -- correct for the per-candidate gates, which already know their own allocation. Pass
    the sleeve count when handing it a whole-book figure instead.
    """
    equity = sleeve_equity(deployed_equity_usd, n_sleeves)
    mult = _tunable("capacity_headroom_mult", _CAPACITY_FALLBACK_MULT)
    floor = _tunable("capacity_abs_floor_usd", _CAPACITY_FALLBACK_FLOOR)
    return max(floor, mult * equity)


def capacity_fit(capacity_usd: float, deployed_equity_usd: float = DEFAULT_BOOK_USD,
                 n_sleeves: int = 1, allocation_usd: float | None = None,
                 sleeve: str | None = None) -> float:
    """Score capacity in [0, 1] by SUFFICIENCY for this book -- flat above the requirement.

    Below the §42 headroom requirement the score ramps linearly: an edge you would be half of is
    worth roughly half as much as one you would be a comfortable slice of. At the requirement it
    reaches 1.0 and STAYS there -- that flat region is the parity the niche was missing. Nothing
    above it is discounted; size is not a tiebreaker in either direction.

    ``allocation_usd`` is the amount this sleeve will ACTUALLY be funded with. Without it the
    requirement assumes EQUAL WEIGHT (book / sleeves), which is stricter than reality whenever a
    sleeve is deliberately sized small -- and sizing a sleeve small is exactly what you do for a
    small edge. A $5k edge funded with $1k is 5x headroom and perfectly safe, but equal weight on a
    $14.8k book reads $1,477 into it and fails. That gap silently excluded the edges §42 exists to
    keep, so a DECLARED allocation is honoured here -- and reconciled against what the sleeve is
    really funded with by `max_audit.check_capacity_allocation_honesty`, because a declared number
    with nothing checking it is just a way to pass any capacity gate by writing a small number.
    """
    cap = max(0.0, float(capacity_usd))
    alloc = allocation_usd if allocation_usd is not None else declared_allocation(sleeve)
    if alloc is not None:
        required = capacity_required(max(0.0, float(alloc)), 1)
    else:
        required = capacity_required(max(0.0, float(deployed_equity_usd)), n_sleeves)
    if required <= 0.0:
        return 1.0
    ratio = cap / required
    if ratio < 1.0:
        return round(max(0.0, ratio), 6)
    crowd_start = max(1.0, _tunable("capacity_crowd_start_usd", _CROWD_START_USD))
    floor = min(1.0, max(0.0, _tunable("capacity_crowd_floor", _CROWD_FLOOR)))
    if cap <= crowd_start:
        return 1.0
    # Log-scaled so the discount deepens slowly with each order of magnitude past fund-scale,
    # rather than falling off a cliff at an arbitrary dollar line.
    decades = math.log10(cap / crowd_start)
    return round(max(floor, 1.0 - (1.0 - floor) * min(1.0, decades / 2.0)), 6)


def capacity_band(capacity_usd: float, deployed_equity_usd: float = DEFAULT_BOOK_USD,
                  n_sleeves: int = 1, allocation_usd: float | None = None,
                  sleeve: str | None = None) -> str:
    """Human-readable bucket, for audit output and dossiers rather than for arithmetic.

    Honours ``allocation_usd`` for the same reason `capacity_fit` does: if the score says an edge
    is fillable at a declared allocation, the band must not simultaneously call it UNFILLABLE.
    """
    cap = max(0.0, float(capacity_usd))
    alloc = allocation_usd if allocation_usd is not None else declared_allocation(sleeve)
    if alloc is not None:
        required = capacity_required(max(0.0, float(alloc)), 1)
    else:
        required = capacity_required(max(0.0, float(deployed_equity_usd)), n_sleeves)
    if required > 0 and cap < required:
        return "UNFILLABLE"          # you would be too large a share of your own edge
    if cap <= _CROWD_START_USD:
        return "NICHE"               # the desk's structural advantage: too small to interest funds
    if cap <= 10.0 * _CROWD_START_USD:
        return "SCALABLE"
    return "FUND-SCALE"              # a fund can trade this too -- assume it already does


#: Days after which the NAV ledger is too old to steer a gate. Beyond this we do NOT know the book.
#: TIGHTENED 7.0 -> 2.0 on 2026-08-05 (R0163). Seven days let every capacity ratio be steered by
#: a book a full week out of date, on a desk whose equity can move materially in one funding day;
#: 48h is the shortest window that still spans a weekend gap in the attestation chain. The
#: FALLBACK is deliberately unchanged -- this only moves the line at which the reading is called
#: unknown, and unknown already routes to the conservative constant below.
_NAV_STALE_DAYS = 2.0
_NAV_LEDGER = Path(__file__).resolve().parents[2] / "data/nav_attestation.jsonl"


#: VENUE TRUTH, written by the dead-man rail from the exchange's own account endpoints. Preferred
#: over the NAV chain because `equity_marked` there is the last point of the MOLDED CURVE -- its
#: own docstring says "venue-truth lives in the deadman's file" -- and the testnet spot wallet
#: carries ~$300k of faucet coins the molded feed does not fully exclude.
_DEADMAN_STATE = Path(__file__).resolve().parents[2] / "data/deadman_state.json"


def venue_book_usd() -> float | None:
    """Book equity from the venue's own numbers, or None when the rail has not run here.

    NOT WIRED INTO `live_book_usd` -- deliberately. `high_water` is a HIGH-WATER MARK, not spot
    equity, so on a live VPS it would raise `capacity_required` during any drawdown and start
    rejecting exactly the small edges §42 spent the day admitting. Tightening a gate on an
    untestable number is a regression dressed as a correctness fix. Exposed so the principal can
    compare it against the molded curve and decide; switching the default needs that comparison
    on real data first.

    Reads the dead-man's `high_water`, which is a HIGH-WATER MARK rather than spot equity. That
    OVERSTATES the book during a drawdown, and overstating is the safe direction for a capacity
    requirement: it demands MORE headroom, never less. The alternative -- the molded curve -- can
    understate and would loosen every gate at exactly the wrong moment.

    Read-only. Never writes the dead-man's file: two writers on that rail caused the 07-11 false
    fire, and it is TIER-3 NEVER-TOUCH.
    """
    try:
        hw = float(json.loads(_DEADMAN_STATE.read_text("utf-8"))["high_water"])
    except Exception:
        return None
    return hw if hw > 0.0 else None


#: MEASURED venue floor truth, written by scripts/capacity_simulator.py off the live exchangeInfo
#: endpoints: per live-universe symbol, the venue's real MIN_NOTIONAL/NOTIONAL order filter for
#: both legs plus the lot-rounding floor. THE canonical venue-notional source (R0218) -- consumers
#: read it here instead of restating a "Binance-class 10.0" literal next to their own gates, which
#: is the one-policy-many-copies defect this whole module exists to prevent.
_CAPACITY_FLOOR_ARTIFACT = Path(__file__).resolve().parents[2] / "data/capacity_floor.json"


def venue_min_notional_usd() -> float | None:
    """Venue minimum order notional in USD from MEASURED truth, or None when unmeasured here.

    The binding value across the live universe: the largest of each symbol's spot/futures
    MIN_NOTIONAL filters, so an order sized to it clears every symbol the desk actually trades
    (recorded truth 2026-07-27: spot_min 5.0, fut_min 5.0).

    Returns None -- never a constant -- when the artifact is absent, unreadable or carries no
    usable rows. Same contract as ``venue_book_usd``: this rung reports only genuine venue truth,
    and each consumer owns its own fallback, because the honest direction DIFFERS by consumer
    (stranded recovery adopts the measured value outright; the autodiscovery SUB-VIABLE floor is
    tighten-only and may never drop below its historical constant -- see
    libs/autodiscovery/validation.py).
    """
    try:
        rows = json.loads(_CAPACITY_FLOOR_ARTIFACT.read_text("utf-8")).get("symbols", [])
        measured = max((max(float(r.get("spot_min") or 0.0), float(r.get("fut_min") or 0.0))
                        for r in rows), default=0.0)
    except Exception:
        return None
    return measured if measured > 0.0 else None


def live_book_usd(fallback: float = DEFAULT_BOOK_USD, ledger: Path | None = None) -> float:
    """The book the desk ACTUALLY has: venue truth first, NAV chain second, constant last.

    ORDER MATTERS AND WAS WRONG. This originally read `equity_marked` straight from the NAV chain,
    which is the last point of a MOLDED CURVE, not an account balance -- so every capacity gate in
    the desk was sized against a simulated number. Venue truth now wins; the NAV chain is a
    fallback for machines where the rail has not run.

    THE POINT OF THIS FUNCTION. Every capacity threshold in the desk is a ratio to deployed equity,
    which is only self-scaling if something feeds it the real number. Pinned to a constant, the
    requirement never moves: the desk would still be sizing edges for a $50k book at $500k, and
    would keep admitting edges it had long outgrown. "Capacity is a ratio" and "the ratio is
    evaluated against a hardcoded literal" are the same bug one step apart.

    FAILS TO THE CONSTANT, NEVER TO ZERO. A missing, stale or corrupt ledger returns ``fallback``.
    Returning 0.0 would collapse the requirement to the absolute floor and quietly pass everything
    -- an unreadable file must never be the loosest possible gate.
    """
    path = ledger if ledger is not None else _NAV_LEDGER
    try:
        lines = [ln for ln in path.read_text("utf-8").splitlines() if ln.strip()]
        row = json.loads(lines[-1])
        # accept either name: the field was renamed to say what it is, and the chain is append-only
        equity = float(row.get("molded_curve_usd", row.get("equity_marked")))
        age_d = (datetime.now(tz=UTC) - datetime.fromisoformat(str(row["ts"]))).total_seconds()
        if equity <= 0.0 or age_d / 86_400.0 > _NAV_STALE_DAYS:
            return fallback              # stale means UNKNOWN, and unknown is not "anything goes"
    except Exception:
        return fallback
    return equity


def live_sleeves(fallback: int = DEFAULT_SLEEVES, ledger: Path | None = None) -> int:
    """Concurrent sleeves actually running, from the same ledger. Never below 1."""
    path = ledger if ledger is not None else _NAV_LEDGER
    try:
        lines = [ln for ln in path.read_text("utf-8").splitlines() if ln.strip()]
        n = int(json.loads(lines[-1])["n_carries"])
    except Exception:
        return max(1, fallback)
    # Floored at the planned count: running 1 sleeve today does not mean one edge may swallow the
    # whole book, it means the desk has not diversified YET. Taking the live number literally would
    # let a single-sleeve day hand 100% of equity to one edge and call it sized.
    return max(1, fallback, n)


def outgrown_at(capacity_usd: float, n_sleeves: int | None = None) -> float:
    """Book size at which this edge stops being fillable -- its EXPIRY, in dollars of equity.

    §42(3) says the decay of a small edge as the desk grows into it is DEFINITIONAL, not a risk to
    be mitigated: the sequence is edge -> size -> next edge. That only compounds if the desk can
    SEE the expiry coming, so it is a number rather than a surprise. Inverting the requirement:
    an edge is fillable while ``capacity >= headroom_mult * book / sleeves``.
    """
    sleeves = max(1, n_sleeves if n_sleeves is not None else DEFAULT_SLEEVES)
    mult = max(1e-9, _tunable("capacity_headroom_mult", _CAPACITY_FALLBACK_MULT))
    return max(0.0, float(capacity_usd)) * sleeves / mult


def growth_runway(capacity_usd: float, book_usd: float | None = None,
                  n_sleeves: int | None = None) -> float:
    """How many TIMES the current book this edge survives. <1 means already outgrown."""
    book = book_usd if book_usd is not None else live_book_usd()
    if book <= 0.0:
        return float("inf")
    return round(outgrown_at(capacity_usd, n_sleeves) / book, 3)


def niche_share(capacities: list[float], deployed_equity_usd: float = DEFAULT_BOOK_USD,
                n_sleeves: int = DEFAULT_SLEEVES) -> float:
    """Share of a candidate population sitting in the NICHE band -- the §42 hunt measurement.

    Defaults to the sleeve count because this one takes a whole-BOOK figure: it judges a funnel,
    not a single allocation.
    """
    caps = [c for c in capacities if c > 0]
    if not caps:
        return 0.0
    n = sum(1 for c in caps if capacity_band(c, deployed_equity_usd, n_sleeves) == "NICHE")
    return round(n / len(caps), 4)

```

### libs\research\layers.py
```python
"""THE SEVEN LAYERS, DECLARED: which organ does information, prediction, timing, sizing,
portfolio, execution or exit -- and what each layer costs.

MEASURED 2026-09-08 (Tier-1 programme item G14): six of the seven layers have a dedicated,
scheduled engine, so the separation exists de facto -- but nowhere is it declared. A new leg
lands in `hourly_cycle.py` under whatever name its author chose and joins no layer, so nobody
can ask "how many trials did the TIMING layer run this week, and what did they cost?", and the
one layer with no engine at all (EXIT: the exit study runs, nothing sizes or times an exit from
it) is invisible precisely because the taxonomy it is missing from does not exist.

THE REGISTRY IS THE DECLARATION, and the test enforces it: every `_costed("name", ...)` leg in
the hourly and daily cycles must appear here. A leg nobody assigned a layer to fails the suite
-- the taxonomy stays complete by construction rather than by memory.

`census` joins the registry onto the compute ledger (libs/ops/compute_ledger.cost_by_run), so
per-layer hours, runs and failure rates are the ledger's numbers grouped, never re-measured.
The EXIT layer's census reads zero hours against one leg; that zero is the finding.
"""
from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
DESK = ROOT / "desks" / "mt5"
REPORT = DESK / "reports" / "layer_census.json"

LAYERS = ("information", "prediction", "timing", "sizing", "portfolio", "execution", "exit",
          "meta")

#: leg name -> layer. `meta` is the machine that runs the machine: health, publishing, the
#: compute ledger itself. It is a layer of the desk, not of a strategy, and is listed so its
#: cost is visible next to the seven it serves.
LEG_LAYER: dict[str, str] = {
    # information: what the desk knows before it predicts anything
    "mine": "information", "moat_miner": "information", "world_crawler": "information",
    "deep_forest": "information", "market_intel": "information", "record_tape": "information",
    "archive_tape": "information", "refresh_bars": "information",
    "timeframe_coverage": "information", "frontier": "information",
    "frontier_ontology": "information", "frontier_unknowns": "information",
    "frontier_implementer": "information", "frontier_report": "information",
    "state_vector": "information", "causal_graph": "information",
    "input_identity": "information",
    # FIFTEEN LEGS LANDED WITHOUT A LAYER AND THIS TEST HAD BEEN RED FOR IT (2026-09-10). Nine
    # of them were added on 2026-09-10 itself and mapped nowhere: exactly the failure the
    # registry exists to prevent, committed by the session that wrote the registry's own fence.
    # A leg with no layer is an hour of compute that `opportunity_cost` cannot attribute, so
    # "what did the desk NOT test this hour" silently omits it.
    "futures_lead_lag": "information", "tape_features": "information",
    # prediction: turning information into a claim about returns
    "compile_candidates": "prediction", "merge_docket": "prediction", "search": "prediction",
    "sweep": "prediction", "hunt12": "prediction",
    "backtest": "prediction", "external_gauntlet": "prediction",
    "deepen": "prediction", "experiment_design": "prediction",
    "experiment_cache": "prediction", "ml_layer": "prediction", "model_league": "prediction",
    "model_skill": "prediction", "forecast_contract": "prediction",
    "graveyard_model": "prediction", "counterfactual_world": "prediction",
    "edge_confidence": "prediction", "adversaries": "prediction",
    "recertify_canon": "prediction", "publish_survivors": "prediction",
    "miner_conversion": "prediction", "opportunity_gap": "prediction",
    "research_org": "prediction", "queue_compact": "prediction",
    "requeue_unrunnable": "prediction", "falsifier_run": "prediction",
    "opportunity_forecast": "prediction", "edge_reliability": "prediction",
    "edges_macro_fusion_sweep": "prediction", "alpha_breadth": "prediction",
    "alpha_periodic_table": "prediction", "regime_coverage": "prediction",
    "arena": "meta", "prosecutor": "meta", "scaling_laws": "meta", "dead_architecture": "meta",
    # timing: when a claim becomes a trade
    "enrol_clocks": "timing", "heal_clocks": "timing", "promoter": "timing",
    "rebalance_trigger": "timing", "entry_timing": "timing",
    # WHICH HOURS the desk has an edge in is a TIMING question, not a sizing one -- this leg
    # measures and allocates nothing, and stacking it on pf_allocator would shrink twice.
    "session_allocation": "timing",
    # Generating a mechanism's other-session and other-chart equivalents is asking WHEN it works,
    # which is a timing question even though the output is a research candidate.
    "session_chart_expansion": "timing",
    # Whether an artifact's own stamp advances is a MEASUREMENT property of the desk, not a
    # property of any strategy -- it belongs with the other self-measurement legs.
    "stamp_freshness": "information",
    # Why an order filled or did not is an EXECUTION measurement, and it is the binding stage.
    "fill_attribution": "execution",
    # What a sleeve pays to trade belongs with execution too: it is a cost, not a signal.
    "cost_to_edge": "execution",
    "swap_rejudge": "execution",
    "asia_plane": "information",
    "sge_premium": "information",
    "asia_collector": "information",
    "asia_parser": "information",
    "index_discovery": "information",
    "empty_cluster_forcer": "prediction",
    "asia_transmission": "information",
    # Whether a data endpoint still serves what it claims is an INFORMATION property -- it decides
    # whether any input exists at all, before any signal is derived from it.
    "source_routes": "information",
    # Per-sleeve return paths are what a PORTFOLIO view is computed from -- n_eff, covariance,
    # joint drawdown. Not a signal and not an execution fact.
    "strategy_paths": "portfolio",
    # THE FOUR ACTIVATION LEGS (2026-09-14). All four organs existed and NOTHING ran them, which
    # is III.16 exactly: built is not a status. `weak_signals` and `residual_factors` mint claims
    # about returns, so they are prediction. `markout` asks what the desk's own fills cost it
    # after the fact -- execution. `exogenous_search` is undirected hunting for inputs nobody has
    # a story for, which is information, and is only affordable because the trial count is sealed.
    "weak_signals": "prediction",
    "residual_factors": "prediction",
    "markout": "execution",
    # THE MARKET DIGITAL TWIN (2026-09-22) is billed to execution: it is calibrated to spreads,
    # depth, cancellations and impact on the desk's own tape, and what it adds to a claim about
    # returns is the counterfactual execution cost of the rule under the posterior worlds. The
    # robustness number it writes routes research; it sizes nothing and predicts no return.
    "digital_twin": "execution",
    "exogenous_search": "information",
    # `stop_reverse` asks what the desk's own orders did to it at the venue -- execution.
    "stop_reverse": "execution",
    # `forward_reconcile` keeps the forward lane's roster true -- which clock may accrue
    # evidence and which is an orphan. That is portfolio bookkeeping, not prediction.
    "forward_reconcile": "portfolio",
    # AND FIVE LEGS WERE STILL UNMAPPED WHEN THOSE FOUR LANDED (2026-09-14). The registry's own
    # comment records fifteen of these in 2026-09-10 and the same drift had recurred, so the test
    # this file exists to satisfy was red before this session touched it. Mapped by what each
    # actually does rather than by its name: `refresh_regime` (costed as `regime_monitor`)
    # conditions on a latent state, which is prediction; `orthogonality` measures tail dependence
    # BETWEEN sleeves, which only the portfolio layer can act on; `lake_promote` asks what share
    # of stored intelligence survives a point-in-time question, which is information about the
    # desk's own inputs; `research_exchange_score` scores which external source converts, likewise;
    # `alpha_rl` searches sequentially against the allocator's marginals, which is prediction.
    "alpha_rl": "prediction",
    "regime_monitor": "prediction",
    "orthogonality": "portfolio",
    "lake_promote": "information",
    "research_exchange_score": "information",
    # The FRED archive and the macro view it feeds are inputs about the world, refreshed hourly
    # when older than six hours: information, and the state the allocator conditions on.
    "fred_macro": "information",
    # Route repair for dead sources and bars-file integrity are both about whether the desk's
    # inputs can be read at all: information.
    "source_fixer": "information",
    # THE FEATURE COMPILER and THE DATA-ACQUISITION SCIENTIST (LAWS 5m): typing what the desk
    # holds, and deciding which dataset to hold next, are both about what the desk knows before
    # it predicts anything: information.
    "feature_compiler": "information",
    "data_acquisition_scientist": "information",
    "universe_integrity": "information",
    # Formulaic alpha generation is a predictor search; the closed-loop attestation is meta.
    "alpha_evolution": "prediction",
    "closed_loop": "meta",
    # The breadth sweep mints cells for every unbanned family on every chart the desk holds bars
    # for -- a predictor search, scheduled hourly since the discovery hunt was banned (2026-09-16).
    "breadth_sweep": "prediction",
    # Whether the allocator's book reaches the sleeves it funds is a measurement of the desk's
    # own wiring, like `wiring_audit`: meta.
    "allocator_join": "meta",
    # Whether every docket candidate is still accounted for is a measurement of the desk's own
    # bookkeeping: meta.
    "candidate_conservation": "meta",
    # Planted point-in-time canaries measure whether the desk can read the future: meta.
    "pit_canaries": "meta",
    # Certification fate joined back to the generators that proposed each cell reweights the
    # predictor search itself: prediction.
    "mutation_yield": "prediction",
    # Realised R credited back to the scientist and lane that proposed each cell: the delayed
    # truth that reweights the predictor search (bandit worth, generator weights): prediction.
    "credit_assignment": "prediction",
    # THE 2026-09-16 BLUEPRINT ORGANS (Tier-1 phases C/D).
    "axis_registry": "information", "forced_flow_calendar": "information",
    "standing_questions": "information",
    "novelty_gate": "prediction",
    "posterior_alpha": "sizing", "exposure_decomposition": "portfolio",
    "hazard_engine": "exit",
    "breadth_ladder": "meta", "tier1_scorecard": "meta", "wiring_ceo": "meta",
    "probation": "meta", "live_system_state": "meta", "semantic_memory": "meta",
    "model_role_benchmark": "meta", "research_departments": "meta",
    "qd_frontier": "information", "blind_reviewer": "meta",
    "evaluator_lab": "meta", "value_of_data": "information", "research_api_status": "meta",
    "artifact_chain": "meta", "residual_queue": "information", "unseen_frontier": "information",
    "source_registry": "information", "synthetic_regimes": "meta",
    "event_response_atlas": "information", "causal_lab": "information", "world_lab": "prediction",
    # THE MARKET CONSTITUTION: which rule the price was formed under, as a PIT column, and
    # whether a rule change moved anything -- what the desk knows before it predicts.
    "market_constitution": "information",
    # THE 2026-09-17 WORLD-MODEL TRIAD. `world_model` turns every PIT series into a conditional
    # distribution over forward returns -- prediction, and the only one of the three that makes a
    # claim about returns at all. `residual_hunt` asks what dataset, participant, region,
    # representation, mechanism or interaction the model is MISSING, which is a question about
    # what the desk knows before it predicts: information. `representation_forge` mints the
    # features themselves from ingested series -- also information, and for the same reason
    # `unused_information` is: it decides what inputs exist, not what they imply.
    "world_model": "prediction", "residual_hunt": "information",
    "representation_forge": "information",
    # THE MATHEMATICS CIVILIZATION (2026-09-17): every object it invents is a claim about the
    # residual -- E[eps | f(x)] -- which is a claim about returns, so the hour is billed to
    # prediction like `world_model` and `discovery_compiler`. The representations it mints are a
    # by-product of that claim, not a separate information hour.
    "math_lab": "prediction",
    # THE EXPRESSION FACTORY (2026-09-22): every cell it screens is a claim about returns from
    # a formula on the desk's own bars -- prediction, beside math_lab whose department it shares.
    "expression_factory": "prediction",
    # THE PHYSICS LAB (2026-09-22): the institution around the mathematics + physics scientists --
    # every card it judges is a claim about the residual, so the hour is prediction like math_lab.
    "physics_lab": "prediction",
    "news_event_stream": "information", "event_sleeves": "prediction",
    "registry_sync": "meta", "axis_proposer": "information", "program_alpha_lane": "prediction",
    "trajectory_evolution": "prediction", "research_os_archive": "meta", "regime_router": "sizing",
    "moat_series": "information", "scout_roster": "information",
    "descendants": "prediction", "forward_slot_ranker": "portfolio",
    "analyst_pipeline": "information", "knowledge_graph": "information",
    "card_explosion": "prediction", "alpha_lineage": "prediction",
    "graveyard_resurrection": "prediction", "shadow_discovery": "information",
    "forward_exploitation": "information", "alpha_recombination": "prediction",
    "unused_information": "information", "discovery_compiler": "prediction",
    # WHICH SOURCES THE DESK MAY LAWFULLY CONSUME is a property of its INPUTS, decided before any
    # signal is derived from them -- the same reading that puts `source_routes` and `data_scout`
    # in information. The ROI reallocator is the machine spending on itself: meta.
    "evidence_router": "information", "research_roi": "meta",
    "research_debt": "meta", "mining_objective": "meta", "research_gap_map": "meta",
    # WHAT THE DESK KNOWS AND COULD KNOW ABOUT THE WORLD, per country x sector x information type
    # x mechanism x representation x asset x session x regime x horizon x execution, plus the deep
    # forest's own tensor. It decides WHICH INPUTS EXIST before any signal is derived from them --
    # the same question `source_routes`, `value_of_data` and `unseen_frontier` are information for
    # -- even though the frontier rows it writes become research work downstream. LAWS 5f.
    "coverage_tensor": "information",
    "gauntlet_backpressure": "meta", "miner_specialisation": "meta",
    # THE TIER-5 RESIDUALS (mandate 90, 110, 131/132, 133, 134, 136, 97/98, 162). The bounty
    # board and the drawdown-alpha miner are PORTFOLIO: both ask what the BOOK lacks -- a payoff
    # shape, a regime, something that pays while the book bleeds -- which is a question about the
    # combination and not about any one cell's forecast. The autopsy splits a CLOSED deal into
    # signal, cost and slippage against the price the decision intended, which is execution. The
    # auction, the bottleneck law, the latency clock, the replenishment target and the dashboard
    # are the machine measuring and re-funding the machine: meta.
    "portfolio_bounty": "portfolio", "drawdown_alpha_miner": "portfolio",
    "trade_autopsy": "execution",
    "research_auction": "meta", "bottleneck_law": "meta", "research_latency": "meta",
    "alpha_replenishment": "meta", "research_dashboard": "meta",
    "moat_collectors": "information", "source_frontier": "information",
    "scout_swarm": "information", "actor_atlas": "information",
    # INFORMATION, not meta: the understanding seat turns bytes the desk collected but could not
    # READ into claims it can. An hour spent there buys information the desk already paid to
    # fetch and had been throwing away by reading it with the wrong language's rules.
    "understanding_seat": "information",
    "netting_report": "execution", "execution_alpha": "execution",
    "paradigm_router": "meta", "meta_controller": "meta", "lead_replication": "information",
    # THE META-EVOLUTION LAYER, THE COMPUTE-ECONOMICS SCIENTIST AND THE MISSED-TRADE
    # ARCHAEOLOGIST (LAWS 5m, 2026-09-22). The first two are the machine measuring and
    # rewriting the machine: meta. The archaeologist asks which INPUT was absent at a
    # decision -- what the desk knew before it predicted -- which is information, exactly as
    # `residual_hunt` is.
    "research_evolution": "meta", "compute_economics": "meta",
    "missed_trade_archaeologist": "information",
    # THE ANYTIME-VALID SCIENCE CONTROLLER (LAWS 5k/5m): online-FDR wealth per lineage, the
    # effective-trial census and the genome archive. It predicts, sizes and times nothing; it
    # measures whether the machine's evidence is still evidence after an unbounded stream of
    # launches, and refuses the launches that would make it not so: meta.
    "science_controller": "meta",
    # THE CROSS-MARKET EVENT GRAPH (LAWS 5m). It assembles what the desk knows about how events
    # reach assets and adjudicates each mechanism's evidence; it predicts nothing itself, so like
    # `knowledge_graph` and `causal_graph` it is information. THE REPLICATION CIVILIZATION judges
    # the desk's own implementations against a written spec, never the market: it is the
    # machine measuring the machine, beside `evaluator_lab` and `blind_reviewer` -- meta, which
    # is this vocabulary's word for the validation layer.
    "event_graph_lab": "information", "replication_civilization": "meta",
    "data_scout": "information", "japan_department": "information",
    "global_research_os": "information", "macro_department": "information",
    # THE FOREST FEDERATION (2026-09-17). Seventeen research civilizations, each running eleven
    # agent roles in parallel on its own resident. They are INFORMATION legs for the same reason
    # `japan_department` is: what a forest produces is a registry of sources, claims, mechanisms
    # and PIT-safe series -- what the desk KNOWS before it predicts anything. The candidate
    # compiler inside each one donates through `proposer_common`, whose own legs are already
    # billed to prediction, so counting a forest as prediction would bill the same trial twice.
    "forest_korea": "information", "forest_china": "information",
    "forest_russia_cis": "information", "forest_south_asia": "information",
    "forest_asean": "information", "forest_oceania": "information",
    "forest_europe": "information", "forest_north_america": "information",
    "forest_latam": "information", "forest_mena": "information",
    "forest_africa": "information",
    "forest_global_web": "information", "forest_global_academic_code": "information",
    "forest_global_physical_data": "information", "forest_global_market_data": "information",
    "external_federation": "information", "federation_ops": "information",
    # THE SANDBOX RUNNER executes federated engines and rebuilt cells over the desk's bars and
    # donates hypotheses and representations: what the desk can know, so information.
    "sandbox_runner": "information",
    "source_civilizations": "information", "evidence_watchtower": "information",
    "prediction_markets": "information",
    "archaeology": "information",
    "sares": "information",
    # ONE CERTIFICATE TRUTH: the audit of every certificate/clock store against the one lane is a
    # fence over the machine's own bookkeeping -- meta, like every other fence.
    "certificate_truth": "meta",
    "shadow_institutional": "information",
    "latent_actors": "information",
    "latency_lab": "execution",
    # THE FEED/CLOCK OBSERVATORY and THE IMPACT LAB (LAWS 5m): what the desk's picture of the
    # market is worth at the instant it decides, and what its own orders do to the price. Both
    # are about how an order reaches the venue and what it meets there -- execution.
    "feed_clock_lab": "execution", "impact_lab": "execution",
    # THE INGESTION-EXPLOITATION CONTRACT (LAWS 5c, 2026-09-17). The ledger inventories the
    # desk's information estate and gives every ingested datum a downstream state: information.
    # The fusion turns that estate into regime posteriors and nowcasts: prediction. The gate
    # that ratchets both is meta, like every other fence.
    "ingestion_ledger": "information", "macro_intelligence": "prediction",
    # THE DISLOCATION LAB (RESEARCH 11) turns six engines' claims into a calibrated ensemble
    # against the instrument's own market-implied state: a claim about returns, prediction.
    "dislocation_lab": "prediction",
    "ingestion_exploitation": "meta",
    # sizing: how much
    "capacity": "sizing", "ensemble_optimizer": "sizing",
    # portfolio: how the book is composed
    "pf_allocator": "portfolio",
    # The balance-sheet layer and the Allocator-V2 evidence: what the book costs to carry and
    # what each sleeve is worth to it -- a question about the book's composition, not about
    # how an order reaches the venue.
    "financing_lab": "portfolio",
    # execution: how the order reaches the venue
    "execution_resolver": "execution", "execution_twin": "execution",
    # What the venue charges and where that number came from is execution arithmetic, not
    # research: these three decide what every backtest is billed at the fill.
    "fusion_cost": "execution", "cost_construction": "execution",
    "spread_provenance": "execution", "microstructure_census": "execution",
    # exit: how a position ends
    "exit_study": "exit",
    # meta
    "health": "meta", "issue_board": "meta", "publish_dashboard": "meta",
    "publish_state": "meta", "release_identity": "meta", "smoke_release": "meta",
    "burn_in": "meta", "maintain_miners": "meta", "reclaim_disk": "meta", "daily": "meta",
    "layer_census": "meta", "opportunity_cost": "meta", "acceptance": "meta",
    "wiring_audit": "meta", "queue_cycle": "meta", "time_joins": "meta", "brain_ab": "meta",
    # THE CONTROL PLANE is meta by construction: it measures whether the machine that runs the
    # machine is doing what desired state says, and it predicts, sizes and times nothing.
    "control_plane": "meta",
    "session_capital": "portfolio",
}

_LEG_RE = re.compile(r'_costed\("([^"]+)"')


def scheduled_legs(root: Path = ROOT) -> set[str]:
    """Every costed leg the two cycles declare, read from the source."""
    legs: set[str] = set()
    for name in ("hourly_cycle.py", "daily_cycle.py"):
        src = root / "desks" / "mt5" / "research" / name
        if src.exists():
            legs |= set(_LEG_RE.findall(src.read_text("utf-8")))
    return legs


def unassigned(root: Path = ROOT) -> list[str]:
    """Legs that run but belong to no layer. The test pins this to []."""
    return sorted(scheduled_legs(root) - set(LEG_LAYER))


def census(cost_by_run: dict[str, dict[str, Any]], root: Path = ROOT) -> dict[str, Any]:
    """Per-layer hours/runs/failures from the compute ledger's per-run aggregate."""
    by_layer: dict[str, dict[str, Any]] = {
        L: {"legs": sorted(k for k, v in LEG_LAYER.items() if v == L),
            "runs": 0, "hours": 0.0, "failures": 0, "costed_legs": []} for L in LAYERS}
    for run, c in cost_by_run.items():
        layer = LEG_LAYER.get(run)
        if layer is None:
            continue
        b = by_layer[layer]
        b["runs"] += int(c.get("runs") or 0)
        b["hours"] += float(c.get("hours") or 0.0)
        b["failures"] += int(c.get("failures") or 0)
        b["costed_legs"].append(run)
    for b in by_layer.values():
        b["hours"] = round(b["hours"], 4)
        b["failure_rate"] = round(b["failures"] / b["runs"], 4) if b["runs"] else None
        b["dark_legs"] = sorted(set(b["legs"]) - set(b["costed_legs"]))
        b["costed_legs"].sort()
    total_h = sum(b["hours"] for b in by_layer.values())
    for b in by_layer.values():
        b["share_of_hours"] = round(b["hours"] / total_h, 4) if total_h else None
    starved = [L for L in LAYERS[:-1] if by_layer[L]["hours"] == 0.0]
    return {
        "at": datetime.now(tz=UTC).isoformat(timespec="seconds"),
        "layers": by_layer, "total_hours": round(total_h, 4),
        "unassigned_legs": unassigned(root),
        "starved_layers": starved,
        "why": ("a layer with declared legs and zero costed hours is either never scheduled or "
                "its cost is unrecorded; either way the desk spends nothing on it"),
    }


def main(argv: list[str] | None = None) -> int:
    from libs.ops.compute_ledger import cost_by_run
    doc = census(cost_by_run())
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(doc, indent=1), "utf-8")
    print(f"layer census: {doc['total_hours']}h over {len(LEG_LAYER)} legs; starved "
          f"{doc['starved_layers'] or 'none'}; unassigned {doc['unassigned_legs'] or 'none'}")
    return 0


if __name__ == "__main__":
    import sys
    sys.path.insert(0, str(ROOT))
    raise SystemExit(main())

```

### libs\research\polyglot.py
```python
"""POLYGLOT -- the desk's maximum multilingual understanding layer.

THE PRINCIPAL'S ORDER (2026-09-17, permanent): maximum multilingual and slang intelligence, so
the desk NEVER has an issue understanding anything and exploits every piece of information in
every global language. **NOTHING IS DROPPED FOR BEING UNREADABLE.**

WHAT WAS ACTUALLY WRONG. Two detectors existed and neither could carry that order.
`moat_collectors.detect_script` answers with four buckets -- cjk, cyrillic, arabic, latin -- and
says so honestly: it is a SCRIPT, not a language, and it cannot tell Japanese from Chinese or
Bulgarian from Russian. `mechanism_claims.language_of` is a real language detector and stops at
the twenty-six languages whose CLAIM VOCABULARY that module carries; every other language on
earth falls through to `en`, and a Georgian competition write-up, a Tamil options board or a
romanised-Russian Telegram post is filed as English and then read with English rules, which finds
nothing and reports an empty forest. That is the L1.28a failure in its purest form: absence
indistinguishable from emptiness, and it is why a `needs_seat` flag exists here at all.

FOUR THINGS THIS MODULE IS DELIBERATE ABOUT.

**SCRIPT IS A MEASUREMENT; LANGUAGE IS AN INFERENCE, AND THEY ARE REPORTED SEPARATELY.** A
Hangul run IS Korean and a Gurmukhi run IS Punjabi -- those are facts about Unicode. A Latin run
is not English, and this module never pretends otherwise: Latin, Cyrillic, Arabic and Devanagari
runs are SCORED against compact function-word/letter/trigram profiles, and the score is published
as `confidence` rather than swallowed. Low confidence is a verdict, not a failure.

**A DOCUMENT IS NOT ONE LANGUAGE.** The forests this desk is under standing orders to mine write
"BOJが仲値でドル円を..." next to an English chart caption and a Russian one-liner. `segments`
cuts a document into script runs and then into stopword-majority spans, so a three-language post
is three measurements instead of one wrong one.

**TRANSLATION HAPPENS AFTER RETRIEVAL, THROUGH A SEAT, AND NEVER HERE.** `TRANSLATE_AFTER_RETRIEVAL`
states the policy as an object so it can be asserted on. Retrieval is NATIVE -- a query written in
translated English finds translated English content, which is the corpus everybody already read.
This module opens no socket, downloads no model and ships no dependency: every table below is
data in this file, and `understand` is pure.

**WHAT CANNOT BE UNDERSTOOD IS NAMED, NEVER DISCARDED.** `Understanding.needs_seat` is True when
the confidence is under `SEAT_CONFIDENCE`, when the language is unknown, or when the language has
no terminology map -- each with the reason in `needs_seat_reason`. The understanding seat
(`desks/mt5/research/understanding_seat.py`) picks those up, asks the LLM seats, and feeds the
answers back. A document nobody can read is a queue entry, not a deletion.

WHAT IT REUSES AND NEVER REWRITES. `mechanism_claims` already owns the desk's instrument
aliases in twenty-six languages (`resolve_instruments`), its mechanism-class vocabulary
(`MECHANISM_CLASSES`), and its crypto-exchange fence (`forbidden_venue`). Those are IMPORTED.
`EXTRA_ALIASES` here holds only the gaps measured against it on 2026-09-17 (bare 金, 브렌트,
Кабель, swissy ...), so the alias table stays in one place and this module stays a layer.

    from libs.research.polyglot import understand
    u = understand("仲値でドル円が上がりやすい")     # ja, XAUUSD/USDJPY, fx_fixing concept
"""
# ruff: noqa: RUF001, RUF002 -- a lexicon in forty scripts is MADE of the characters
# these rules call ambiguous. Here they are the data, not a typo waiting to be found.
from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from libs.research import mechanism_claims as mc

__all__ = [
    "CONCEPTS",
    "COVERAGE",
    "EXTRA_ALIASES",
    "GROUND_KIND_LAYER",
    "LANGUAGES",
    "MAX_DATES",
    "MAX_NUMBERS",
    "NATIVE_INSTRUMENT",
    "NATIVE_TERMS",
    "PRESERVE_FRINGE",
    "PRIOR",
    "PROBE_TERMS",
    "PROFILES",
    "RULE",
    "SCRIPTS",
    "SCRIPT_LANG",
    "SEAT_CONFIDENCE",
    "SLANG",
    "SOURCE_LAYERS",
    "TERMINOLOGY_LANGS",
    "TRANSLATE_AFTER_RETRIEVAL",
    "TRANSLITERATIONS",
    "Concept",
    "EvidencePolicy",
    "LangGuess",
    "ParsedDate",
    "ParsedNumber",
    "Profile",
    "Segment",
    "TranslationPolicy",
    "Understanding",
    "canonicalise",
    "dates_in",
    "has_terminology",
    "identify",
    "instruments_named",
    "languages_without_terminology",
    "layers_unmeasured",
    "native_instrument",
    "native_queries",
    "normalise",
    "numbers_in",
    "query_coverage",
    "query_languages",
    "script_of",
    "segments",
    "transliterated",
    "understand",
    "understand_rows",
]

RULE = ("nothing is dropped for being unreadable: native understanding first, a seat second, "
        "and every remaining item is named until understood")

#: Below this, `understand` sets `needs_seat`. 0.5 is deliberately generous -- a coin flip
#: between two languages is not understanding, and the cost of one seat call is a fraction of the
#: cost of reading a Bulgarian forum with Russian rules and reporting it empty.
SEAT_CONFIDENCE = 0.5
#: Identification needs some text. Below this many script-bearing characters the answer is a
#: guess, and a guess is published with a low confidence rather than as an answer.
MIN_IDENT_CHARS = 8
#: Bounds. A page that names more than this many numbers or dates is a table, and parsing a table
#: one regex at a time is the wrong tool -- the count is reported, the excess is not invented.
MAX_NUMBERS = 24
MAX_DATES = 12
#: Segments carried from one document. Beyond this the document is a multilingual index page.
MAX_SEGMENTS = 64
#: Characters identified per call. Identification is a profile count; a whole PDF adds noise, not
#: signal, and the first 20k characters of any document settle its language.
MAX_IDENT_CHARS = 20_000


# ============================================================================ the policy object
@dataclass(frozen=True)
class TranslationPolicy:
    """WHERE translation is allowed to happen, as an object a test can assert on.

    The order matters and is not stylistic. Retrieval in translated English finds the corpus that
    was already translated into English -- which is the corpus everybody has already read, and
    therefore the one with no edge left in it. Native retrieval reaches the 七禾网 interview, the
    Velog post and the smart-lab thread that nobody has mined. Translation is then a READING step,
    performed by a seat that can be audited, on text the desk has already captured verbatim.
    """

    retrieval: str = "native"
    translation: str = "after retrieval, through an LLM seat, never inside this module"
    network_calls: bool = False
    model_downloads: bool = False
    verbatim_kept: bool = True
    why: str = ("a query in translated English finds translated English content -- the corpus "
                "everyone has already read; and a silently machine-translated claim cannot be "
                "audited back to its ground")

    def allows(self, stage: str) -> bool:
        """True when translation may happen at this stage. Only `seat` may translate."""
        return stage.strip().lower() in ("seat", "understanding_seat", "after_retrieval")


TRANSLATE_AFTER_RETRIEVAL = TranslationPolicy()


# ============================================================================ script ranges
#: Unicode BLOCKS per script, written as (lo, hi) codepoint pairs so no reviewer has to trust a
#: glyph that renders like its neighbour. Counted, not first-match: a Japanese sentence contains
#: Han AND Kana, and whichever appears more is not the answer -- the presence of Kana is.
SCRIPTS: dict[str, tuple[tuple[int, int], ...]] = {
    "Latin": ((0x41, 0x5A), (0x61, 0x7A), (0xC0, 0x24F), (0x1E00, 0x1EFF), (0x2C60, 0x2C7F),
              (0xA720, 0xA7FF)),
    "Greek": ((0x370, 0x3FF), (0x1F00, 0x1FFF)),
    "Cyrillic": ((0x400, 0x52F), (0x2DE0, 0x2DFF), (0xA640, 0xA69F)),
    "Armenian": ((0x530, 0x58F), (0xFB13, 0xFB17)),
    "Hebrew": ((0x590, 0x5FF), (0xFB1D, 0xFB4F)),
    "Arabic": ((0x600, 0x6FF), (0x750, 0x77F), (0x870, 0x8FF), (0xFB50, 0xFDFF),
               (0xFE70, 0xFEFF)),
    "Syriac": ((0x700, 0x74F),),
    "Thaana": ((0x780, 0x7BF),),
    "NKo": ((0x7C0, 0x7FF),),
    "Devanagari": ((0x900, 0x97F), (0xA8E0, 0xA8FF)),
    "Bengali": ((0x980, 0x9FF),),
    "Gurmukhi": ((0xA00, 0xA7F),),
    "Gujarati": ((0xA80, 0xAFF),),
    "Oriya": ((0xB00, 0xB7F),),
    "Tamil": ((0xB80, 0xBFF),),
    "Telugu": ((0xC00, 0xC7F),),
    "Kannada": ((0xC80, 0xCFF),),
    "Malayalam": ((0xD00, 0xD7F),),
    "Sinhala": ((0xD80, 0xDFF),),
    "Thai": ((0xE00, 0xE7F),),
    "Lao": ((0xE80, 0xEFF),),
    "Tibetan": ((0xF00, 0xFFF),),
    "Myanmar": ((0x1000, 0x109F), (0xAA60, 0xAA7F)),
    "Georgian": ((0x10A0, 0x10FF), (0x1C90, 0x1CBF), (0x2D00, 0x2D2F)),
    "Ethiopic": ((0x1200, 0x139F), (0x2D80, 0x2DDF)),
    "Cherokee": ((0x13A0, 0x13FF),),
    "Khmer": ((0x1780, 0x17FF), (0x19E0, 0x19FF)),
    "Mongolian": ((0x1800, 0x18AF),),
    "Hangul": ((0x1100, 0x11FF), (0x3130, 0x318F), (0xA960, 0xA97F), (0xAC00, 0xD7AF)),
    "Hiragana": ((0x3041, 0x309F),),
    "Katakana": ((0x30A0, 0x30FF), (0x31F0, 0x31FF), (0xFF66, 0xFF9D)),
    "Bopomofo": ((0x3100, 0x312F),),
    "Han": ((0x3400, 0x4DBF), (0x4E00, 0x9FFF), (0xF900, 0xFAFF)),
    "Yi": ((0xA000, 0xA48F),),
    "Vai": ((0xA500, 0xA63F),),
    "Javanese": ((0xA980, 0xA9DF),),
    "Balinese": ((0x1B00, 0x1B7F),),
    "Tifinagh": ((0x2D30, 0x2D7F),),
    "Coptic": ((0x2C80, 0x2CFF),),
    "Runic": ((0x16A0, 0x16FF),),
    "Adlam": ((0x1E900, 0x1E95F),),
}

#: Scripts that name ONE language on their own. This is the honest half of identification: no
#: profile, no score, no argument -- a Sinhala run is Sinhala. `Hebrew` is here with `yi` as its
#: alternative (see `_YIDDISH`), and `Han` is deliberately ABSENT because it names three.
SCRIPT_LANG: dict[str, str] = {
    "Hangul": "ko", "Hiragana": "ja", "Katakana": "ja", "Thai": "th", "Lao": "lo",
    "Khmer": "km", "Myanmar": "my", "Georgian": "ka", "Armenian": "hy", "Ethiopic": "am",
    "Sinhala": "si", "Tamil": "ta", "Telugu": "te", "Kannada": "kn", "Malayalam": "ml",
    "Gujarati": "gu", "Gurmukhi": "pa", "Oriya": "or", "Thaana": "dv", "Tibetan": "bo",
    "Mongolian": "mn-Mong", "Greek": "el", "Cherokee": "chr", "Syriac": "syr", "NKo": "nqo",
    "Yi": "ii", "Vai": "vai", "Javanese": "jv", "Balinese": "ban", "Tifinagh": "ber",
    "Coptic": "cop", "Runic": "non", "Adlam": "ff", "Bopomofo": "zh-Hant", "Hebrew": "he",
}
#: Scripts several languages share, which is where the profiles below earn their place.
AMBIGUOUS_SCRIPTS: frozenset[str] = frozenset({"Latin", "Cyrillic", "Arabic", "Devanagari",
                                               "Bengali", "Han"})

_RANGES: tuple[tuple[str, int, int], ...] = tuple(
    (name, lo, hi) for name, blocks in SCRIPTS.items() for lo, hi in blocks)
#: Scripts that travel together inside ONE language, folded for segmentation only. Japanese is
#: Han + Kana in the same sentence, and cutting between them would make every Japanese document a
#: code-switch that it is not.
_SEGMENT_FOLD: dict[str, str] = {"Hiragana": "Han", "Katakana": "Han", "Bopomofo": "Han"}


def _script_at(ch: str) -> str:
    """The script of ONE character, or "" for digits, punctuation, whitespace and emoji."""
    cp = ord(ch)
    for name, lo, hi in _RANGES:
        if lo <= cp <= hi:
            return name
    return ""


def script_of(text: str) -> str:
    """The dominant script of a document, or UNMEASURED-shaped "" for text with none.

    Kana beats Han whenever Kana is present at all, because Kana is Japanese and Han is not
    evidence of anything more specific than "CJK". Everything else is a straight count.
    """
    body = (text or "")[:MAX_IDENT_CHARS]
    counts: dict[str, int] = {}
    for ch in body:
        name = _script_at(ch)
        if name:
            counts[name] = counts.get(name, 0) + 1
    if not counts:
        return ""
    if counts.get("Hiragana", 0) or counts.get("Katakana", 0):
        return "Hiragana" if counts.get("Hiragana", 0) >= counts.get("Katakana", 0) else "Katakana"
    return max(counts, key=lambda k: counts[k])


# ============================================================================ Han disambiguation
#: Characters that exist in the TRADITIONAL set only, paired with their simplified twin so a
#: reader can check them. The count decides, so one simplified quotation inside a Hong Kong post
#: does not flip it.
_TRAD_SIMP: str = (
    "漲涨報报週周價价買买賣卖點点幣币匯汇證证現现貨货選选權权開开關关時时間间動动轉转趨趋勢势"
    "頭头態态線线續续隨随場场盤盘億亿萬万數数據据個个們们這这說说會会來来對对後后過过還还"
    "從从電电機机議议業业產产運运經经濟济資资訊讯網网際际國国學学讀读寫写聽听問问題题幾几"
    "發发變变麼么樣样強强預预測测隻只兩两極极舉举黃黄銀银銅铜歐欧鎊镑圓圆恆恒達达標标壓压"
    "撐撑檔档彈弹單单進进當当結结擇择籌筹碼码勝胜離离內内戶户賺赚虧亏損损險险風风獲获調调"
)
_TRAD_CHARS = frozenset(_TRAD_SIMP[0::2])
_SIMP_CHARS = frozenset(_TRAD_SIMP[1::2])
#: Kanji-only Japanese terms that settle a Han run with no Kana in it. Script cannot answer here
#: and TERMINOLOGY can: 仲値 is a Tokyo fixing and nothing else, in any corpus.
_JA_HAN_MARKERS: tuple[str, ...] = ("仲値", "五十日", "日銀", "東証", "為替", "円安", "円高",
                                    "先物", "買建", "売建", "取引時間", "株価", "日経平均")
_YIDDISH: tuple[str, ...] = ("וו", "יי", "אַ", "אָ", "ױ", "ײ", "בֿ", "כּ")


# ============================================================================ language profiles
@dataclass(frozen=True)
class Profile:
    """One language's compact fingerprint inside a script it shares with others.

    THREE SIGNALS, WEIGHTED BY HOW MUCH THEY PROVE. `chars` are letters only this language uses
    (ß, ł, ə, ў, ے) and are worth the most -- one of them settles the question. `stop` are
    function words, word-bounded, and are the workhorse. `tri` are character trigrams for the
    pairs no function word separates (cs/sk, id/ms, no/da, hr/sr-Latn), and are worth the least
    because a trigram appears by accident.
    """

    script: str
    stop: tuple[str, ...] = ()
    chars: tuple[str, ...] = ()
    tri: tuple[str, ...] = ()


#: Weights. A unique letter is near-proof, a function word is evidence, a trigram is a hint.
_W_CHAR, _W_STOP, _W_TRI = 4.0, 3.0, 1.0

#: TIE-BREAK PRIOR, and it is here because the alternative was worse. "Python для алготрейдинга"
#: scores 3.0 for Russian and 3.0 for Belarusian (both list "для"), and a plain `(-score, lang)`
#: sort then picks BELARUSIAN -- because "be" sorts before "ru". Measured on this box's
#: intelligence roots on 2026-09-17, that alphabetical accident filed 99 Russian MQL5 thread
#: titles as Belarusian and 48 as Macedonian, and both languages then appeared on the
#: no-terminology-map GAP LIST -- sending the source scouts after two forests that were not
#: there. A tie is broken by which language the world actually writes more of, stated as data.
#: It NEVER overturns a score; it only decides between equals.
PRIOR: dict[str, float] = {
    "en": 9, "es": 8, "de": 7, "fr": 7, "pt": 7, "it": 6, "id": 6, "nl": 5, "pl": 5, "tr": 5,
    "vi": 5, "ms": 4, "ro": 4, "sv": 4, "cs": 4, "hu": 4, "tl": 4, "da": 3, "no": 3, "fi": 3,
    "sk": 3, "hr": 3, "sw": 3, "af": 2, "sl": 2, "lt": 2, "lv": 2, "et": 2, "sq": 2, "ca": 2,
    "az": 2, "uz": 2, "bs": 1, "sr-Latn": 1, "is": 1, "ga": 1, "cy": 1, "mt": 1, "eu": 1,
    "gl": 1, "ha": 1, "yo": 1, "so": 1,
    "ru": 9, "uk": 6, "bg": 4, "sr": 4, "kk": 3, "be": 2, "mk": 2, "ky": 1, "tg": 1, "mn": 1,
    "ar": 9, "fa": 7, "ur": 5, "ps": 2, "ckb": 2, "sd": 1, "ug": 1,
    "hi": 9, "mr": 4, "ne": 3, "sa": 1, "bn": 9, "as": 1,
}

PROFILES: dict[str, Profile] = {
    # ------------------------------------------------------------------ Latin: Germanic
    "en": Profile("Latin", stop=("the", "and", "of", "to", "in", "is", "that", "for", "with",
                                 "when", "after", "usually", "tends", "are", "was", "been",
                                 "this", "from", "which", "into", "than", "should")),
    "de": Profile("Latin", chars=("ß",),
                  stop=("und", "der", "die", "das", "nicht", "ist", "wird", "wenn", "nach",
                        "bei", "mit", "auf", "eine", "einer", "dem", "den", "sich", "auch",
                        "oder", "aber", "über", "für", "meist", "dann"),
                  tri=("sch", "ung", "cht", "ein")),
    "nl": Profile("Latin", stop=("het", "een", "niet", "wordt", "zijn", "ook", "als", "vaak",
                                 "meestal", "naar", "dan", "bij", "van", "voor", "op", "dat",
                                 "wanneer", "maar", "zoals"),
                  tri=("ijn", "sch", "aar", "oor")),
    "af": Profile("Latin", stop=("die", "en", "nie", "van", "wat", "met", "vir", "word", "gaan",
                                 "hulle", "ons", "maar", "ook", "soos"),
                  tri=("aan", "eer", "oor", "kke")),
    "sv": Profile("Latin", stop=("och", "att", "är", "inte", "som", "för", "på", "med", "det",
                                 "ett", "efter", "när", "brukar", "ofta", "av", "till", "från",
                                 "sedan", "eller"),
                  tri=("ade", "ning", "att")),
    "da": Profile("Latin", stop=("og", "at", "er", "ikke", "som", "for", "på", "med", "det",
                                 "et", "efter", "når", "plejer", "ofte", "af", "til", "fra",
                                 "meget", "kun"),
                  tri=("ede", "øre", "ige")),
    "no": Profile("Latin", stop=("og", "at", "er", "ikke", "som", "for", "på", "med", "det",
                                 "et", "etter", "når", "pleier", "ofte", "av", "til", "fra",
                                 "mye", "bare", "jeg"),
                  tri=("ette", "ikke", "ngen")),
    "is": Profile("Latin", chars=("þ", "ð"),
                  stop=("og", "að", "er", "ekki", "sem", "fyrir", "með", "það", "eftir",
                        "þegar", "til", "frá")),
    # ------------------------------------------------------------------ Latin: Romance
    "fr": Profile("Latin", chars=("œ",),
                  stop=("le", "la", "les", "des", "est", "une", "dans", "après", "pour", "sur",
                        "avec", "pas", "sont", "qui", "du", "au", "aux", "cette", "souvent",
                        "quand", "être", "plus"),
                  tri=("eux", "ait", "ent", "tion")),
    "es": Profile("Latin", chars=("ñ", "¿", "¡"),
                  stop=("el", "los", "las", "una", "después", "para", "con", "que", "del", "se",
                        "por", "al", "cuando", "suele", "también", "hacia", "desde", "más",
                        "sobre", "entre"),
                  tri=("ción", "ado", "mente")),
    "pt": Profile("Latin", chars=("ã", "õ"),
                  stop=("os", "não", "uma", "após", "para", "com", "que", "do", "da", "dos",
                        "das", "na", "quando", "costuma", "também", "são", "no", "mais",
                        "pelo", "pela"),
                  tri=("ção", "ões", "ment")),
    "it": Profile("Latin", stop=("il", "lo", "della", "del", "che", "non", "gli", "sono",
                                 "dopo", "una", "per", "nel", "nella", "degli", "delle",
                                 "alla", "questo", "spesso", "quando", "più"),
                  tri=("zion", "ella", "ggi")),
    "ro": Profile("Latin", chars=("ș", "ț", "ă"),
                  stop=("și", "de", "la", "în", "care", "este", "pentru", "nu", "cu", "pe",
                        "din", "sunt", "după", "când", "mai"),
                  tri=("ție", "ului", "ează")),
    "ca": Profile("Latin", chars=("·",),
                  stop=("els", "les", "amb", "per", "que", "una", "aquest", "però", "més",
                        "després", "quan", "són", "això"),
                  tri=("ció", "ment", "nys")),
    "gl": Profile("Latin", stop=("da", "das", "dos", "unha", "para", "que", "non", "coa",
                                 "despois", "cando", "tamén", "máis", "onde"),
                  tri=("ción", "ente")),
    # ------------------------------------------------------------------ Latin: Slavic / Baltic
    "pl": Profile("Latin", chars=("ł", "ż", "ę", "ą", "ś", "ź", "ć", "ń"),
                  stop=("nie", "się", "jest", "na", "do", "że", "po", "przy", "oraz", "zwykle",
                        "często", "ale", "lub", "od", "gdy", "kiedy", "przez", "tylko"),
                  tri=("nie", "czy", "dzie")),
    "cs": Profile("Latin", chars=("ř", "ě", "ů"),
                  stop=("a", "je", "na", "se", "že", "ale", "nebo", "pro", "jsou", "když",
                        "obvykle", "také", "však", "který", "této"),
                  tri=("ost", "ení", "ých")),
    "sk": Profile("Latin", chars=("ĺ", "ŕ", "ô", "ľ", "ä"),
                  stop=("a", "je", "na", "sa", "že", "ale", "alebo", "pre", "sú", "keď",
                        "zvyčajne", "tiež", "však", "ktorý", "tejto"),
                  tri=("osť", "ení", "ých", "ova")),
    "sl": Profile("Latin", stop=("in", "je", "na", "se", "za", "ki", "pa", "ne", "tudi",
                                 "lahko", "kot", "po", "pri", "ali", "bo"),
                  tri=("ost", "jem", "nje")),
    "hr": Profile("Latin", chars=("đ",),
                  stop=("i", "je", "na", "se", "za", "da", "su", "koji", "nije", "ali",
                        "kako", "ovo", "kada", "više", "prema"),
                  tri=("nje", "ije", "cij")),
    "sr-Latn": Profile("Latin", stop=("i", "je", "na", "se", "za", "da", "su", "koji", "nije",
                                      "ali", "kako", "ovo", "kada", "vise", "posle"),
                       tri=("nje", "ost", "ova")),
    "bs": Profile("Latin", stop=("i", "je", "na", "se", "za", "da", "su", "koji", "nije",
                                 "ali", "kako", "ovo", "kada", "takoder"),
                  tri=("nje", "ije", "sti")),
    "lt": Profile("Latin", chars=("ė", "ų", "ū", "į"),
                  stop=("ir", "yra", "su", "bet", "kad", "kaip", "arba", "nes", "tik",
                        "labai", "pagal"),
                  tri=("ias", "imo", "ant")),
    "lv": Profile("Latin", chars=("ā", "ē", "ī", "ķ", "ļ", "ņ", "ģ"),
                  stop=("un", "ir", "ar", "bet", "ka", "kā", "vai", "tikai", "pēc", "pie",
                        "par", "no"),
                  tri=("ība", "anas", "ots")),
    "et": Profile("Latin", chars=("õ",),
                  stop=("ja", "on", "ei", "et", "kui", "ka", "või", "aga", "see", "pärast",
                        "tavaliselt", "ning"),
                  tri=("use", "ise", "mine")),
    "fi": Profile("Latin", stop=("ja", "on", "ei", "että", "kun", "jälkeen", "yleensä",
                                 "usein", "mutta", "myös", "tai", "kanssa", "ovat", "tämä",
                                 "jos", "niin", "sitten"),
                  tri=("inen", "ksen", "ttä")),
    "hu": Profile("Latin", chars=("ő", "ű"),
                  stop=("és", "az", "egy", "nem", "hogy", "van", "meg", "után", "amikor",
                        "vagy", "csak", "mint", "ezt", "már"),
                  tri=("ság", "nak", "ben")),
    "sq": Profile("Latin", stop=("dhe", "të", "në", "për", "është", "me", "nga", "një",
                                 "por", "kur", "shumë", "pas"),
                  tri=("ësh", "imi", "jes")),
    # ------------------------------------------------------------------ Latin: Turkic / other
    "tr": Profile("Latin", chars=("ı", "ğ", "ş"),
                  stop=("ve", "bir", "için", "ile", "bu", "sonra", "genellikle", "olarak",
                        "kadar", "ise", "gibi", "daha", "çok", "ama", "değil", "zaman"),
                  tri=("lar", "ler", "dır")),
    "az": Profile("Latin", chars=("ə",),
                  stop=("və", "bir", "üçün", "ilə", "bu", "sonra", "kimi", "daha", "çox",
                        "amma", "deyil", "zaman"),
                  tri=("lar", "lər", "dır")),
    "uz": Profile("Latin", chars=("oʻ", "gʻ", "o‘", "g‘"),
                  stop=("va", "bu", "uchun", "bilan", "keyin", "juda", "emas", "lekin",
                        "ham", "bo'ladi"),
                  tri=("lar", "ning", "ida")),
    "id": Profile("Latin", stop=("yang", "dan", "dengan", "untuk", "akan", "tidak", "ini",
                                 "itu", "dari", "pada", "ke", "di", "adalah", "saat",
                                 "setelah", "biasanya", "bisa", "sudah", "karena"),
                  tri=("kan", "nya", "men")),
    "ms": Profile("Latin", stop=("yang", "dan", "dengan", "untuk", "akan", "tidak", "ini",
                                 "itu", "dari", "pada", "ke", "di", "ialah", "selepas",
                                 "boleh", "kerana", "telah", "sahaja"),
                  tri=("kan", "nya", "ber")),
    "tl": Profile("Latin", stop=("ang", "ng", "sa", "mga", "ay", "na", "at", "para", "hindi",
                                 "kung", "pero", "kapag", "din", "rin"),
                  tri=("ang", "ing", "pag")),
    "vi": Profile("Latin", chars=("ă", "đ", "ơ", "ư", "ạ", "ộ", "ế", "ị", "ủ", "ề"),
                  stop=("và", "của", "là", "có", "khi", "sau", "thì", "được", "trong",
                        "không", "này", "cho", "với", "thường"),
                  tri=("ngh", "uyê", "iềm")),
    "sw": Profile("Latin", stop=("na", "ya", "wa", "kwa", "ni", "za", "la", "katika", "baada",
                                 "kawaida", "bei", "soko", "huwa", "mara", "nyingi", "wakati"),
                  tri=("ika", "ani", "kwa")),
    "ha": Profile("Latin", stop=("da", "na", "ya", "ba", "don", "kuma", "wannan", "yana",
                                 "sun", "ne", "ko"),
                  tri=("iya", "awa", "nsa")),
    "yo": Profile("Latin", chars=("ọ", "ẹ", "ṣ"),
                  stop=("ati", "ni", "ti", "fun", "pe", "lati", "awon", "yii", "won"),
                  tri=("owo", "ire", "ola")),
    "so": Profile("Latin", stop=("iyo", "oo", "ku", "ka", "waa", "ayaa", "uu", "in", "lagu",
                                 "sida", "laakiin"),
                  tri=("aha", "ada", "yaa")),
    "eu": Profile("Latin", stop=("eta", "du", "da", "bat", "ez", "hau", "dira", "baina",
                                 "gehiago", "batzuk"),
                  tri=("tze", "aren", "iko")),
    "cy": Profile("Latin", stop=("yn", "ac", "mae", "ar", "gyda", "wedi", "hefyd", "ond",
                                 "bod", "ei"),
                  tri=("dd", "wyd", "aeth")),
    "ga": Profile("Latin", stop=("agus", "an", "na", "ar", "le", "tá", "sa", "go", "nach",
                                 "seo", "ach"),
                  tri=("adh", "ach", "eal")),
    "mt": Profile("Latin", chars=("ħ", "ġ", "ż", "ċ"),
                  stop=("il", "li", "ta", "ma", "biex", "kif", "imma", "kull", "wara"),
                  tri=("jiet", "ijn")),
    # ------------------------------------------------------------------ Cyrillic
    "ru": Profile("Cyrillic", chars=("ы", "э", "ё", "ъ"),
                  stop=("и", "в", "не", "на", "что", "это", "как", "для", "по", "при", "или",
                        "после", "обычно", "часто", "если", "рынок", "цена"),
                  tri=("ого", "ени", "ств")),
    "uk": Profile("Cyrillic", chars=("і", "ї", "є", "ґ"),
                  stop=("та", "не", "на", "що", "це", "як", "для", "по", "при", "або",
                        "після", "зазвичай", "часто", "якщо", "ринок", "ціна"),
                  tri=("ння", "ого", "ість")),
    "be": Profile("Cyrillic", chars=("ў",),
                  stop=("не", "на", "што", "гэта", "як", "для", "пры", "або", "пасля",
                        "звычайна", "рынак"),
                  tri=("ння", "ага")),
    "bg": Profile("Cyrillic", stop=("на", "се", "за", "да", "от", "че", "като", "това",
                                    "който", "но", "или", "след", "обикновено", "пазар"),
                  tri=("ият", "ане", "ето")),
    "mk": Profile("Cyrillic", chars=("ѓ", "ќ", "ѕ"),
                  stop=("на", "се", "за", "да", "со", "што", "или", "по", "како", "пазар"),
                  tri=("ата", "ите", "ење")),
    "sr": Profile("Cyrillic", chars=("ђ", "ћ", "џ", "љ", "њ", "ј"),
                  stop=("на", "се", "за", "да", "су", "који", "али", "како", "ово", "после",
                        "тржиште"),
                  tri=("ња", "ост", "ова")),
    "kk": Profile("Cyrillic", chars=("ә", "ғ", "қ", "ң", "ө", "ұ", "ү", "һ"),
                  stop=("және", "бұл", "үшін", "бар", "жоқ", "кейін", "нарық"),
                  tri=("дың", "мен", "ған")),
    "ky": Profile("Cyrillic", chars=("ң", "ө", "ү"),
                  stop=("жана", "бул", "үчүн", "бар", "жок", "кийин", "рынок"),
                  tri=("дын", "лар", "ган")),
    "tg": Profile("Cyrillic", chars=("ғ", "ӣ", "қ", "ӯ", "ҳ", "ҷ"),
                  stop=("ва", "ин", "барои", "аст", "бо", "аз", "бозор"),
                  tri=("ҳои", "анд")),
    "mn": Profile("Cyrillic", chars=("ө", "ү"),
                  stop=("байна", "бол", "нь", "энэ", "болон", "зах", "зээл", "дараа"),
                  tri=("ийн", "ууд", "сан")),
    # ------------------------------------------------------------------ Arabic script
    "ar": Profile("Arabic", chars=("ة", "أ", "إ", "ى"),
                  stop=("من", "في", "على", "إلى", "عن", "أن", "هذا", "التي", "مع", "بعد",
                        "الذهب", "السوق", "سعر"),
                  tri=("ال", "ية", "ون")),
    "fa": Profile("Arabic", chars=("پ", "چ", "ژ", "گ", "ک"),
                  stop=("که", "این", "برای", "است", "را", "با", "از", "می", "بازار",
                        "قیمت", "طلا"),
                  tri=("های", "ترین", "می‌")),
    "ur": Profile("Arabic", chars=("ٹ", "ڈ", "ڑ", "ں", "ھ", "ے"),
                  stop=("کے", "ہے", "کی", "میں", "سے", "نے", "اور", "پر", "کو", "بازار",
                        "سونا"),
                  tri=("یاں", "ہوں")),
    "ps": Profile("Arabic", chars=("ټ", "ډ", "ړ", "ږ", "ښ", "ګ", "ڼ"),
                  stop=("او", "دا", "چې", "په", "له", "دی", "بازار")),
    "ckb": Profile("Arabic", chars=("ڕ", "ڵ", "ۆ", "ێ"),
                   stop=("و", "بۆ", "لە", "ئەم", "بازاڕ")),
    "sd": Profile("Arabic", chars=("ڀ", "ٺ", "ٽ", "ٿ", "ڦ", "ڪ"),
                  stop=("۽", "جي", "آهي", "۾")),
    "ug": Profile("Arabic", chars=("ې", "ۈ", "ۆ", "ۋ", "ھ"),
                  stop=("ۋە", "بۇ", "ئۈچۈن", "بار", "بازار")),
    # ------------------------------------------------------------------ Devanagari / Bengali
    "hi": Profile("Devanagari", stop=("है", "में", "के", "की", "का", "और", "से", "को",
                                      "नहीं", "पर", "यह", "बाजार", "सोना", "कीमत"),
                  tri=("ों", "ाने", "कर")),
    "mr": Profile("Devanagari", stop=("आहे", "आणि", "च्या", "ला", "मध्ये", "नाही", "हे",
                                      "बाजार"),
                  tri=("ांच", "ला", "तून")),
    "ne": Profile("Devanagari", stop=("छ", "गर्न", "को", "मा", "र", "छैन", "पनि", "बजार"),
                  tri=("हरू", "ेको")),
    "sa": Profile("Devanagari", stop=("च", "एव", "इति", "तत्", "यत्", "अस्ति"),
                  tri=("स्य", "ानि")),
    "bn": Profile("Bengali", stop=("এবং", "এই", "করে", "থেকে", "হয়", "না", "বাজার", "সোনা"),
                  tri=("ের", "ায়")),
    "as": Profile("Bengali", chars=("ৰ", "ৱ"),
                  stop=("আৰু", "কৰে", "হয়", "নহয়")),
    # ------------------------------------------------------------------ Han family
    "zh-Hans": Profile("Han", stop=("的", "是", "在", "和", "了", "有", "不", "这", "会",
                                    "黄金", "市场", "价格", "上涨", "下跌")),
    "zh-Hant": Profile("Han", stop=("的", "是", "在", "和", "了", "有", "不", "這", "會",
                                    "黃金", "市場", "價格", "上漲", "下跌")),
    "ja": Profile("Han", stop=("仲値", "為替", "日銀", "円安", "円高", "先物", "取引")),
}

LANGUAGES: tuple[str, ...] = tuple(sorted(set(PROFILES) | set(SCRIPT_LANG.values())))

_STOP_RE: dict[str, re.Pattern[str]] = {}
for _lang, _p in PROFILES.items():
    if _p.script in ("Latin", "Cyrillic"):
        _STOP_RE[_lang] = re.compile(
            r"(?<!\w)(?:" + "|".join(re.escape(w) for w in _p.stop) + r")(?!\w)")


def _profile_score(low: str, lang: str) -> float:
    """One language's score on one lowercased span. Chars, then stopwords, then trigrams."""
    prof = PROFILES[lang]
    score = 0.0
    for ch in prof.chars:
        if ch in low:
            score += _W_CHAR
    rx = _STOP_RE.get(lang)
    if rx is not None:
        score += _W_STOP * len(rx.findall(low))
    else:
        for word in prof.stop:
            score += _W_STOP * low.count(word)
    for tri in prof.tri:
        if tri in low:
            score += _W_TRI
    return score


# ============================================================================ identification
@dataclass(frozen=True)
class LangGuess:
    """What language this is, how sure, and what else it could be. `und` means unknown, which is
    a verdict the seat acts on -- never a silent fallback to English."""

    lang: str
    script: str
    confidence: float
    alternatives: tuple[tuple[str, float], ...] = ()
    rule: str = ""


def _han_language(body: str) -> tuple[str, float, tuple[tuple[str, float], ...]]:
    """ja / zh-Hant / zh-Hans off a Han run. Kana already decided ja before this is reached."""
    for marker in _JA_HAN_MARKERS:
        if marker in body:
            return "ja", 0.85, (("zh-Hans", 0.1),)
    trad = sum(1 for ch in body if ch in _TRAD_CHARS)
    simp = sum(1 for ch in body if ch in _SIMP_CHARS)
    if trad > simp:
        margin = (trad - simp) / max(trad + simp, 1)
        return "zh-Hant", min(0.95, 0.6 + 0.35 * margin), (("zh-Hans", 0.2),)
    if simp > trad:
        margin = (simp - trad) / max(trad + simp, 1)
        return "zh-Hans", min(0.95, 0.6 + 0.35 * margin), (("zh-Hant", 0.2),)
    # NO DISTINCTIVE CHARACTER EITHER WAY. Most short Han strings are written identically in
    # both scripts; saying zh-Hans at 0.45 is the honest read and routes the item to a seat.
    return "zh-Hans", 0.45, (("zh-Hant", 0.4), ("ja", 0.2))


def identify(text: str) -> LangGuess:
    """The language of a document: script first, profiles second, `und` when neither answers.

    SCRIPT IS NEVER OVERRULED BY A PROFILE. A Hangul run is Korean whatever the function words
    around it say, because Unicode is a measurement and a word list is a fingerprint. Only the
    scripts several languages SHARE -- Latin, Cyrillic, Arabic, Devanagari, Bengali, Han -- reach
    the scoring path, and their confidence is the margin between the best two, published.
    """
    body = (text or "")[:MAX_IDENT_CHARS]
    if not body.strip():
        return LangGuess("und", "", 0.0, (), "empty text")
    translit = transliterated(body)
    script = script_of(body)
    if script and script not in AMBIGUOUS_SCRIPTS:
        lang = SCRIPT_LANG.get(script, "und")
        letters = sum(1 for ch in body if _script_at(ch) == script)
        conf = 0.95 if letters >= 2 else 0.6
        alts: tuple[tuple[str, float], ...] = ()
        if script == "Hebrew" and any(m in body for m in _YIDDISH):
            alts = (("yi", 0.4),)
        return LangGuess(lang, script, conf, alts, f"script {script} names one language")
    if script == "Han":
        lang, conf, alts = _han_language(body)
        return LangGuess(lang, "Han", conf, alts, "Han: kana absent, simplified/traditional count")
    if not script:
        return LangGuess("und", "", 0.0, (), "no script-bearing characters (digits/punctuation)")

    # ------------------------------------------------- a shared script: score the profiles
    low = body.lower()
    scores = {lang: _profile_score(low, lang)
              for lang, prof in PROFILES.items() if prof.script == script}
    ranked = sorted(scores.items(), key=lambda kv: (-kv[1], -PRIOR.get(kv[0], 0.0), kv[0]))
    best, best_score = ranked[0]
    second_score = ranked[1][1] if len(ranked) > 1 else 0.0
    alts = tuple((lang, round(s, 2)) for lang, s in ranked[1:4] if s > 0)
    letters = sum(1 for ch in body if _script_at(ch) == script)

    if translit and script == "Latin":
        # ROMANISED NON-LATIN TEXT. "privet, kak dela" scores nothing on any Latin profile and is
        # not English; the romanisation table is the only thing that can see it.
        return LangGuess(translit, "Latin", 0.6, ((best, round(best_score, 2)),) if best_score
                         else (), "romanisation markers")
    if best_score >= 6.0:
        margin = (best_score - second_score) / max(best_score, 1.0)
        return LangGuess(best, script, min(0.95, 0.45 + 0.5 * margin), alts,
                         "function-word / letter / trigram profile")
    if best_score >= 3.0 and letters >= MIN_IDENT_CHARS:
        return LangGuess(best, script, 0.45, alts, "weak profile match: seat confirms")
    fallback = mc.language_of(body)
    if fallback in PROFILES and PROFILES[fallback].script == script and fallback != "en":
        return LangGuess(fallback, script, 0.5, alts, "mechanism_claims.language_of")
    if script == "Latin" and body.isascii():
        # ASCII WITH NO PROFILE HIT. Probably English, and "probably" is 0.45 -- below the seat
        # threshold on purpose, so a ticker soup or a gibberish string still reaches a reader.
        return LangGuess("en", "Latin", 0.45, alts, "ascii latin, no profile hit")
    return LangGuess("und", script, 0.2 if letters else 0.0, alts,
                     f"{script} script, no profile scored")


# ============================================================================ code-switching
@dataclass(frozen=True)
class Segment:
    """One span of one language inside a document that mixes several."""

    start: int
    end: int
    text: str
    lang: str
    script: str


_SENT_SPLIT = re.compile(r"(?<=[.!?;。！？；।؟])\s*|[\n\r]+")


def _script_runs(text: str) -> list[tuple[int, int, str]]:
    """(start, end, script) runs. Digits, punctuation, whitespace and emoji join the run they
    are inside, so "BOJ 仲値 fix" is three runs and not seven."""
    runs: list[tuple[int, int, str]] = []
    start = 0
    current = ""
    for i, ch in enumerate(text):
        name = _SEGMENT_FOLD.get(_script_at(ch), _script_at(ch))
        if not name:
            continue
        if not current:
            current = name
            continue
        if name != current:
            runs.append((start, i, current))
            start, current = i, name
    if current:
        runs.append((start, len(text), current))
    elif text:
        runs.append((0, len(text), ""))
    return runs


def segments(text: str, max_segments: int = MAX_SEGMENTS) -> list[Segment]:
    """A document cut into (span, language) pairs: script runs first, stopword majority second.

    WHY BOTH CUTS. Script alone cannot separate an English caption from a Spanish one, and
    sentence splitting alone cannot separate 仲値 from the English word next to it. Adjacent
    spans of the same language are merged back, so a normal single-language document returns ONE
    segment and the caller does not have to special-case it.
    """
    body = text or ""
    if not body.strip():
        return []
    raw: list[Segment] = []
    for start, end, script in _script_runs(body):
        span = body[start:end]
        if script in ("Latin", "Cyrillic") and len(span) > 80:
            offset = start
            for piece in _SENT_SPLIT.split(span):
                if not piece:
                    continue
                at = body.find(piece, offset)
                at = offset if at < 0 else at
                guess = identify(piece)
                raw.append(Segment(at, at + len(piece), piece, guess.lang, guess.script))
                offset = at + len(piece)
        else:
            guess = identify(span)
            raw.append(Segment(start, end, span, guess.lang, guess.script))
    merged: list[Segment] = []
    for seg in raw:
        if merged and merged[-1].lang == seg.lang and merged[-1].script == seg.script:
            prev = merged[-1]
            merged[-1] = Segment(prev.start, seg.end, body[prev.start:seg.end], prev.lang,
                                 prev.script)
        else:
            merged.append(seg)
        if len(merged) >= max_segments:
            break
    return merged


# ============================================================================ transliteration
#: Romanisation markers: words that appear in Latin script and belong to another language.
#: SMALL AND HIGH-PRECISION on purpose -- a long list of romanised words collides with English
#: ("nani", "mono", "sono", "kore" are all English-adjacent noise), and a false ja on an English
#: post costs more than a missed romanisation, which the seat still catches.
TRANSLITERATIONS: dict[str, tuple[str, ...]] = {
    "ru": ("privet", "spasibo", "pozhaluysta", "khorosho", "ochen", "nichego", "davai",
           "davay", "ponyatno", "normalno", "rabotaet", "dengi", "rynok", "tsena", "prodavat",
           "pokupat", "shortit", "loshara", "kak dela", "chto delat", "bolshoy", "malenkiy"),
    "ar": ("yalla", "habibi", "inshallah", "mashallah", "wallah", "shukran", "marhaba",
           "khalas", "mabrouk", "alhamdulillah", "salam alaikum", "ya akhi", "fulus", "souq",
           "sooq", "bikam", "kaifa haluk"),
    "hi": ("kya hai", "kaise ho", "accha", "acha hai", "bhai", "paisa", "bahut", "nahin",
           "nahi hai", "karo", "kyun", "thoda", "matlab", "bazaar", "sona", "chalo", "yaar",
           "theek hai", "kitna", "samajh"),
    "ja": ("ohayo", "arigato", "sumimasen", "konnichiwa", "kudasai", "yoroshiku", "ganbatte",
           "wakaranai", "nakane", "gotobi", "watanabe", "sonkiri", "rikaku", "shiozuke",
           "kabushiki", "kawase", "desu ne", "naruhodo"),
    "ko": ("annyeong", "kamsahamnida", "hajima", "daebak", "jinjja", "gaemi", "gimchi premium",
           "kimchi premium", "jonber", "sonjeol", "mulddagi", "mul tagi", "oein", "nego dae",
           "hwanyul"),
    "zh": ("nihao", "ni hao", "xiexie", "zaijian", "jiucai", "chaodi", "ge rou", "zhuang jia",
           "san hu", "bei xiang", "you zi", "jia you", "laoshi"),
    "tr": ("merhaba", "tesekkur", "nasilsin", "kardesim", "borsa", "dolar kuru", "gunaydin"),
    "el": ("kalimera", "efharisto", "yasou", "malaka", "ti kaneis"),
}
#: Markers containing a space are PHRASES and settle it alone; single words need two.
_TRANSLIT_RE: dict[str, re.Pattern[str]] = {
    lang: re.compile(r"(?<!\w)(?:" + "|".join(re.escape(w) for w in words) + r")(?!\w)")
    for lang, words in TRANSLITERATIONS.items()
}


def transliterated(text: str) -> str | None:
    """The language a Latin-script text is a ROMANISATION of, or None.

    Romanised Russian, Arabic, Hindi, Japanese and Korean are how a large share of the world's
    trading chat is actually written, and every script-based detector reads all of it as English.
    """
    low = (text or "").lower()
    if not low.strip():
        return None
    best, best_hits = "", 0.0
    for lang, rx in _TRANSLIT_RE.items():
        hits = rx.findall(low)
        weight = sum(2.0 if " " in h else 1.0 for h in hits)
        if weight > best_hits:
            best, best_hits = lang, weight
    return best if best_hits >= 2.0 else None

#: Written as escapes on purpose: a combining mark is INVISIBLE in a source file, and a reviewer
#: cannot check a character class made of things that do not render.
_TATWEEL = "ـ"
_ARABIC_MARKS = re.compile("[ً-ٰٟۖ-ۭ]")
_HEBREW_MARKS = re.compile("[֑-ׇֽֿׁׂׅׄ]")
#: Tokens carried through normalisation UNTOUCHED: a cashtag, a hashtag and a handle are names,
#: and folding $XAU into "xau" or collapsing @traaader's letters would destroy the join key a
#: social miner needs. They are held behind PRIVATE-USE sentinels while the rest of the pass
#: runs: an earlier draft used a bare index as the placeholder, which any text containing that
#: digit would have silently corrupted.
_TAGS = re.compile(r"[#$@][\wÀ-ɏЀ-ӿ؀-ۿ぀-鿿]{1,40}")
_HOLD = "{}"
_WS = re.compile("[ 	  　]+")
#: leetspeak. Applied ONLY to a token with a digit BETWEEN two letters, which is what protects
#: `us500`, `nas100` and `xau2400` -- their digits are a trailing run, and a rule that mapped
#: them would rename every index the desk trades.
_LEET = {"4": "a", "3": "e", "1": "i", "0": "o", "5": "s", "7": "t", "@": "a", "$": "s",
         "8": "b", "9": "g", "|": "l"}
_LEET_WORDS = {"1337": "leet", "h4x": "hack", "n00b": "noob"}
_LEET_TOKEN = re.compile(r"[A-Za-z][A-Za-z0-9@$|]{1,14}")
_REPEAT = re.compile(r"([A-Za-zÀ-ɏЀ-ӿㄱ-ㆎ])\1{2,}")
_LATIN_SCRIPTS = frozenset({"Latin", ""})


def _leet_token(token: str) -> str:
    if token.lower() in _LEET_WORDS:
        return _LEET_WORDS[token.lower()]
    chars = list(token)
    interior = any(chars[i] in _LEET and chars[i - 1].isalpha() and chars[i + 1].isalpha()
                   for i in range(1, len(chars) - 1))
    if not interior:
        return token
    return "".join(_LEET.get(ch, ch) if not ch.isalpha() else ch for ch in chars)


def normalise(text: str, lang: str = "") -> str:
    """One document, folded to a comparable form WITHOUT losing what carries meaning.

    NFKC first (which is what folds fullwidth ＵＳＤ and halfwidth ｶﾅ into their normal forms),
    then Arabic tatweel and harakat, then Hebrew niqqud -- three scripts where the marks are
    optional ornament and their presence or absence must not make two identical claims different
    strings. VIETNAMESE DIACRITICS ARE KEPT, and that is not an inconsistency: in Vietnamese the
    tone mark IS the word ("má", "mà", "mã", "mạ"), so folding it would destroy the text rather
    than tidy it. Emoji are kept as tokens (they carry sentiment and are load-bearing on the
    forums this desk mines), hashtags/cashtags/handles are carried verbatim, leetspeak is mapped
    back for Latin script, and a letter repeated three or more times collapses to two.
    """
    body = unicodedata.normalize("NFKC", str(text or ""))
    held: list[str] = []

    def _hold(m: re.Match[str]) -> str:
        held.append(m.group(0))
        return _HOLD.format(len(held) - 1)

    body = _TAGS.sub(_hold, body)
    body = body.replace(_TATWEEL, "")
    body = _ARABIC_MARKS.sub("", body)
    body = _HEBREW_MARKS.sub("", body)
    script = PROFILES[lang].script if lang in PROFILES else script_of(body)
    if script in _LATIN_SCRIPTS:
        body = _LEET_TOKEN.sub(lambda m: _leet_token(m.group(0)), body)
    body = _REPEAT.sub(lambda m: m.group(1) * 2, body)
    body = _WS.sub(" ", body).strip()
    for i, original in enumerate(held):
        body = body.replace(_HOLD.format(i), original)
    return body


# ============================================================================ concepts
@dataclass(frozen=True)
class Concept:
    """One slang or jargon term, resolved to the desk's own mechanism vocabulary.

    `unmapped` is not a failure. A community term with no mechanism class is still recorded, with
    its gloss, because the unmapped population is exactly where a mechanism nobody here has
    thought of shows up -- and a table that silently drops what it cannot classify can never
    report that.
    """

    concept_id: str
    term: str
    lang: str
    gloss: str
    mechanism_class: str = ""
    axis_mechanism: str = ""
    ontology_id: str = ""
    unmapped: bool = False
    fenced: str = ""


@dataclass(frozen=True)
class ConceptSpec:
    """What a concept id MEANS, once, for every language that has a word for it."""

    gloss: str
    #: One of `mechanism_claims.MECHANISM_CLASSES`, or "" when nothing there fits.
    mechanism_class: str = ""
    #: An `axis_registry.MECHANISM_ACTOR` key -- the desk's finer mechanism vocabulary. Held as a
    #: string rather than imported: `axis_registry` lives under `desks/mt5`, off this package's
    #: import path. `desks/mt5/tests/test_understanding_seat.py` asserts every name here is a key
    #: that module really has, so the two can never drift apart silently.
    axis_mechanism: str = ""
    #: A `mechanism_ontology.CORE_MECHANISMS` id where one exists (there are five).
    ontology_id: str = ""
    #: Non-empty when the standing order fences the GROUND this term comes from. The term is
    #: still understood -- understanding is not hunting -- and nothing may hunt it.
    fenced: str = ""


_FENCE_CRYPTO = ("crypto-exchange ground is never hunted (principal 2026-08-18); the concept is "
                 "usable only where it informs an MT5 instrument")

CONCEPTS: dict[str, ConceptSpec] = {
    "retail_crowd": ConceptSpec("the retail crowd as a counterparty", "positioning",
                                "positioning_crowding"),
    "institutional_flow": ConceptSpec("the large/institutional participant driving the tape",
                                      "flow", "inventory_shock"),
    "foreign_investor_flow": ConceptSpec("non-resident investor flow", "flow",
                                         "cross_market_lead"),
    "hot_money": ConceptSpec("short-horizon speculative capital rotating between names", "flow",
                             "positioning_crowding"),
    "northbound_flow": ConceptSpec("cross-border connect flow into the mainland tape",
                                   "cross_asset", "cross_market_lead"),
    "averaging_down": ConceptSpec("adding to a losing position", "positioning",
                                  "positioning_crowding"),
    "stuck_position": ConceptSpec("a losing position held rather than cut", "positioning",
                                  "positioning_crowding"),
    "conviction_hold": ConceptSpec("holding through drawdown as a stated stance", "positioning",
                                   "positioning_crowding"),
    "cut_loss": ConceptSpec("stop-out / realising a loss", "flow", "forced_flow",
                            ontology_id="FORCED_LIQUIDATION"),
    "take_profit": ConceptSpec("closing a winner", "flow", "forced_flow"),
    "forced_liquidation": ConceptSpec("margin-driven forced exit", "flow", "forced_liquidation",
                                      ontology_id="FORCED_LIQUIDATION"),
    "stop_hunt": ConceptSpec("price driven to where stops rest, then reversed",
                             "microstructure", "breakout_liquidity"),
    "liquidity_grab": ConceptSpec("a sweep of resting liquidity before the real move",
                                  "microstructure", "breakout_liquidity",
                                  ontology_id="ORDER_FLOW_IMBALANCE"),
    "fat_finger": ConceptSpec("an erroneous order that dislocates the book", "microstructure",
                              "execution_microstructure"),
    "fx_fixing": ConceptSpec("a benchmark fixing window that forces customer flow", "calendar",
                             "fx_fixing_flow"),
    "gotobi_calendar": ConceptSpec("Japanese settlement days (5th/10th multiples) concentrating "
                                   "importer demand at the Tokyo fix", "calendar",
                                   "fx_fixing_flow"),
    "exporter_hedging": ConceptSpec("exporter/importer hedging flow around a fixing", "flow",
                                    "fx_fixing_flow"),
    "retail_carry_japan": ConceptSpec("Japanese retail FX carry (Mrs Watanabe)", "carry",
                                      "carry_rollover"),
    "carry_trade": ConceptSpec("holding for the rate differential", "carry", "carry_rollover"),
    "leverage": ConceptSpec("borrowed size, which is what makes a flow forced", "positioning",
                            "forced_flow"),
    "short_selling": ConceptSpec("selling borrowed/unowned exposure", "positioning",
                                 "positioning_crowding"),
    "dip_buying": ConceptSpec("buying an extended fall", "reversion", "range_reversion"),
    "chasing": ConceptSpec("buying strength and selling weakness late", "momentum",
                           "trend_persistence"),
    "capitulation": ConceptSpec("a disorderly exit by the losing side", "flow",
                                "forced_liquidation"),
    "venue_premium": ConceptSpec("the same asset priced differently on two venues",
                                 "cross_asset", "relative_value_dislocation",
                                 ontology_id="CROSS_VENUE_PRICE_DISCOVERY"),
    "central_bank_action": ConceptSpec("policy or intervention by the monetary authority",
                                       "policy", "macro_release"),
    "bagholder": ConceptSpec("a holder of a position nobody else wants", "positioning",
                             "positioning_crowding"),
    "pump_crowd": ConceptSpec("a coordinated retail surge into one name", "positioning",
                              "positioning_crowding"),
    "session_handover": ConceptSpec("one session's close setting the next session's open",
                                    "calendar", "session_handover"),
    "kimchi_premium": ConceptSpec("the Korean venue premium", "cross_asset",
                                  "relative_value_dislocation",
                                  ontology_id="CROSS_VENUE_PRICE_DISCOVERY",
                                  fenced=_FENCE_CRYPTO),
    "hodl": ConceptSpec("holding regardless of price, as a stated retail stance", "positioning",
                        "positioning_crowding", fenced=_FENCE_CRYPTO),
}

#: SLANG AND JARGON PER LANGUAGE: the words the community actually types, mapped to a concept id.
#: These are FINANCE terms. General-purpose slang is not here and must not be -- it would make
#: every forum post a mechanism claim, which is the noise this desk already spends its
#: multiple-testing budget on.
SLANG: dict[str, dict[str, str]] = {
    "en": {
        "bagholder": "bagholder", "bag holder": "bagholder", "hodl": "hodl",
        "diamond hands": "conviction_hold", "paper hands": "capitulation",
        "the fix": "fx_fixing", "london fix": "fx_fixing", "4pm fix": "fx_fixing",
        "wmr fix": "fx_fixing", "ecb fix": "fx_fixing",
        "cable": "", "loonie": "", "kiwi": "", "aussie": "", "swissy": "", "fiber": "",
        "gold bugs": "conviction_hold", "goldbugs": "conviction_hold",
        "fat finger": "fat_finger", "stop hunt": "stop_hunt", "stop-hunt": "stop_hunt",
        "stop run": "stop_hunt", "liquidity grab": "liquidity_grab",
        "liquidity sweep": "liquidity_grab", "sweep the lows": "liquidity_grab",
        "buy the dip": "dip_buying", "btfd": "dip_buying", "catching a falling knife":
            "dip_buying", "chasing": "chasing", "fomo": "chasing",
        "margin call": "forced_liquidation", "blown up": "forced_liquidation",
        "capitulation": "capitulation", "puke": "capitulation",
        "averaging down": "averaging_down", "dollar cost averaging down": "averaging_down",
        "smart money": "institutional_flow", "dumb money": "retail_crowd",
        "retail": "retail_crowd", "the herd": "retail_crowd",
        "real money": "institutional_flow", "fast money": "hot_money",
        "carry trade": "carry_trade", "yen carry": "retail_carry_japan",
        "mrs watanabe": "retail_carry_japan", "widow maker": "carry_trade",
        "cut the loss": "cut_loss", "stopped out": "cut_loss", "take profit": "take_profit",
        "tp out": "take_profit", "short squeeze": "capitulation",
        "overnight gap": "session_handover", "gap fill": "session_handover",
        "asia open": "session_handover", "london open": "session_handover",
        "intervention": "central_bank_action", "verbal intervention": "central_bank_action",
        "leverage": "leverage", "gearing": "leverage", "shorting": "short_selling",
    },
    "ja": {
        "仲値": "fx_fixing", "なかね": "fx_fixing", "仲値決定": "fx_fixing",
        "ゴトー日": "gotobi_calendar", "五十日": "gotobi_calendar", "ごとおび": "gotobi_calendar",
        "ミセス・ワタナベ": "retail_carry_japan", "ミセスワタナベ": "retail_carry_japan",
        "塩漬け": "stuck_position", "含み損": "stuck_position",
        "損切り": "cut_loss", "損切": "cut_loss", "利確": "take_profit", "利食い": "take_profit",
        "握力": "conviction_hold", "ガチホ": "conviction_hold",
        "イナゴ": "pump_crowd", "提灯": "pump_crowd",
        "ナンピン": "averaging_down", "難平": "averaging_down",
        "追証": "forced_liquidation", "強制ロスカット": "forced_liquidation",
        "ロスカット": "cut_loss", "踏み上げ": "capitulation", "投げ売り": "capitulation",
        "押し目買い": "dip_buying", "順張り": "chasing", "逆張り": "dip_buying",
        "個人投資家": "retail_crowd", "機関投資家": "institutional_flow",
        "外国人投資家": "foreign_investor_flow", "実需": "exporter_hedging",
        "レバレッジ": "leverage", "空売り": "short_selling", "日銀介入": "central_bank_action",
        "スワップ狙い": "carry_trade", "ストップ狩り": "stop_hunt",
    },
    "ko": {
        "개미": "retail_crowd", "개미들": "retail_crowd", "동학개미": "retail_crowd",
        "외인": "foreign_investor_flow", "외국인": "foreign_investor_flow",
        "기관": "institutional_flow", "세력": "institutional_flow",
        "네고": "exporter_hedging", "네고물량": "exporter_hedging",
        "김프": "kimchi_premium", "역프": "kimchi_premium",
        "물타기": "averaging_down", "존버": "conviction_hold",
        "손절": "cut_loss", "익절": "take_profit", "물렸다": "stuck_position",
        "반대매매": "forced_liquidation", "미수": "leverage", "빚투": "leverage",
        "공매도": "short_selling", "저가매수": "dip_buying", "추격매수": "chasing",
        "패닉셀": "capitulation", "환율방어": "central_bank_action",
        "구두개입": "central_bank_action", "스탑헌팅": "stop_hunt",
    },
    "zh": {
        "韭菜": "retail_crowd", "散户": "retail_crowd", "小散": "retail_crowd",
        "割肉": "cut_loss", "止损": "cut_loss", "止盈": "take_profit",
        "抄底": "dip_buying", "追涨杀跌": "chasing", "追高": "chasing",
        "主力": "institutional_flow", "庄家": "institutional_flow", "机构": "institutional_flow",
        "游资": "hot_money", "热钱": "hot_money",
        "北向资金": "northbound_flow", "北上资金": "northbound_flow",
        "南向资金": "northbound_flow", "外资": "foreign_investor_flow",
        "补仓": "averaging_down", "摊平": "averaging_down", "被套": "stuck_position",
        "套牢": "stuck_position", "死扛": "conviction_hold",
        "爆仓": "forced_liquidation", "强平": "forced_liquidation", "杠杆": "leverage",
        "做空": "short_selling", "砸盘": "capitulation", "恐慌盘": "capitulation",
        "插针": "stop_hunt", "扫止损": "stop_hunt", "央行干预": "central_bank_action",
        "结汇": "exporter_hedging", "中间价": "fx_fixing", "隔夜跳空": "session_handover",
    },
    "zh-Hant": {
        "韭菜": "retail_crowd", "散戶": "retail_crowd", "割肉": "cut_loss",
        "停損": "cut_loss", "停利": "take_profit", "抄底": "dip_buying",
        "追漲殺跌": "chasing", "主力": "institutional_flow", "莊家": "institutional_flow",
        "外資": "foreign_investor_flow", "套牢": "stuck_position", "斷頭": "forced_liquidation",
        "槓桿": "leverage", "放空": "short_selling", "央行干預": "central_bank_action",
    },
    "ru": {
        "физики": "retail_crowd", "хомяки": "retail_crowd", "толпа": "retail_crowd",
        "юрики": "institutional_flow", "крупняк": "institutional_flow",
        "шорт": "short_selling", "лонг": "carry_trade", "слив": "capitulation",
        "усреднение": "averaging_down", "усредняться": "averaging_down",
        "стоп": "cut_loss", "стоп-лосс": "cut_loss", "тейк": "take_profit",
        "маржин колл": "forced_liquidation", "маржинколл": "forced_liquidation",
        "плечо": "leverage", "вынос стопов": "stop_hunt", "сбор стопов": "stop_hunt",
        "интервенция": "central_bank_action", "фиксинг": "fx_fixing",
        "откуп": "dip_buying", "разгон": "pump_crowd",
    },
    "uk": {
        "фізики": "retail_crowd", "шорт": "short_selling", "усереднення": "averaging_down",
        "стоп-лос": "cut_loss", "плече": "leverage", "інтервенція": "central_bank_action",
    },
    "de": {
        "zocker": "retail_crowd", "hebel": "leverage", "kleinanleger": "retail_crowd",
        "leerverkauf": "short_selling", "nachkaufen": "averaging_down",
        "verbilligen": "averaging_down", "gewinnmitnahme": "take_profit",
        "stopp-loss": "cut_loss", "nachschusspflicht": "forced_liquidation",
        "fixing": "fx_fixing", "intervention": "central_bank_action",
        "zinsdifferenzgeschäft": "carry_trade",
    },
    "es": {
        "apalancamiento": "leverage", "vender a descubierto": "short_selling",
        "minoristas": "retail_crowd", "manos fuertes": "institutional_flow",
        "promediar a la baja": "averaging_down", "atrapado": "stuck_position",
        "comprar la caída": "dip_buying", "toma de beneficios": "take_profit",
        "stop loss": "cut_loss", "liquidación forzosa": "forced_liquidation",
        "intervención": "central_bank_action", "caza de stops": "stop_hunt",
    },
    "pt": {
        "alavancagem": "leverage", "vender a descoberto": "short_selling",
        "pessoa física": "retail_crowd", "mão forte": "institutional_flow",
        "preço médio": "averaging_down", "estou comprado": "carry_trade",
        "realização de lucro": "take_profit", "stop": "cut_loss",
        "chamada de margem": "forced_liquidation", "intervenção": "central_bank_action",
        "caça stop": "stop_hunt",
    },
    "fr": {
        "effet de levier": "leverage", "vente à découvert": "short_selling",
        "particuliers": "retail_crowd", "moyenner à la baisse": "averaging_down",
        "prise de bénéfices": "take_profit", "appel de marge": "forced_liquidation",
        "intervention": "central_bank_action", "chasse aux stops": "stop_hunt",
        "fixing": "fx_fixing",
    },
    "it": {
        "leva": "leverage", "vendita allo scoperto": "short_selling",
        "mediare al ribasso": "averaging_down", "presa di profitto": "take_profit",
        "richiamo di margine": "forced_liquidation", "intervento": "central_bank_action",
    },
    "pl": {
        "dźwignia": "leverage", "krótka sprzedaż": "short_selling",
        "uśrednianie": "averaging_down", "realizacja zysku": "take_profit",
        "wezwanie do uzupełnienia": "forced_liquidation", "interwencja":
            "central_bank_action", "polowanie na stopy": "stop_hunt",
    },
    "tr": {
        "kaldıraç": "leverage", "açığa satış": "short_selling", "maliyet düşürme":
            "averaging_down", "kar al": "take_profit", "zarar kes": "cut_loss",
        "margin call": "forced_liquidation", "müdahale": "central_bank_action",
        "stop avı": "stop_hunt", "balık tutmak": "dip_buying",
    },
    "ar": {
        "الرافعة المالية": "leverage", "البيع على المكشوف": "short_selling",
        "متوسط التكلفة": "averaging_down", "جني الأرباح": "take_profit",
        "وقف الخسارة": "cut_loss", "نداء الهامش": "forced_liquidation",
        "تدخل": "central_bank_action", "صيد وقف الخسارة": "stop_hunt",
        "صغار المستثمرين": "retail_crowd",
    },
    "fa": {
        "اهرم": "leverage", "فروش استقراضی": "short_selling", "میانگین کم کردن":
            "averaging_down", "ذخیره سود": "take_profit", "حد ضرر": "cut_loss",
        "کال مارجین": "forced_liquidation", "مداخله": "central_bank_action",
    },
    "hi": {
        "लीवरेज": "leverage", "शॉर्ट सेलिंग": "short_selling", "औसत करना": "averaging_down",
        "मुनाफा वसूली": "take_profit", "स्टॉप लॉस": "cut_loss",
        "मार्जिन कॉल": "forced_liquidation", "खुदरा निवेशक": "retail_crowd",
        "हस्तक्षेप": "central_bank_action",
    },
    "id": {
        "leverage": "leverage", "jual kosong": "short_selling", "average down":
            "averaging_down", "ambil untung": "take_profit", "cut loss": "cut_loss",
        "nyangkut": "stuck_position", "ritel": "retail_crowd", "bandar":
            "institutional_flow", "intervensi": "central_bank_action",
    },
    "vi": {
        "đòn bẩy": "leverage", "bán khống": "short_selling", "trung bình giá":
            "averaging_down", "chốt lời": "take_profit", "cắt lỗ": "cut_loss",
        "cháy tài khoản": "forced_liquidation", "nhà đầu tư nhỏ lẻ": "retail_crowd",
        "đội lái": "institutional_flow", "can thiệp": "central_bank_action",
        "bắt đáy": "dip_buying", "đu đỉnh": "chasing",
    },
    "th": {
        "เลเวอเรจ": "leverage", "ขายชอร์ต": "short_selling", "ถัวเฉลี่ย": "averaging_down",
        "ทำกำไร": "take_profit", "ตัดขาดทุน": "cut_loss", "ล้างพอร์ต": "forced_liquidation",
        "รายย่อย": "retail_crowd", "เจ้ามือ": "institutional_flow",
        "แทรกแซง": "central_bank_action",
    },
    "he": {
        "מינוף": "leverage", "מכירה בחסר": "short_selling", "מיצוע כלפי מטה":
            "averaging_down", "מימוש רווחים": "take_profit", "סטופ לוס": "cut_loss",
        "התערבות": "central_bank_action", "משקיעים קטנים": "retail_crowd",
    },
    "nl": {
        "hefboom": "leverage", "shorten": "short_selling", "bijkopen": "averaging_down",
        "winst nemen": "take_profit", "uitstoppen": "cut_loss", "particuliere belegger":
            "retail_crowd", "interventie": "central_bank_action", "fixing": "fx_fixing",
    },
    "sv": {
        "hävstång": "leverage", "blankning": "short_selling", "snitta ner": "averaging_down",
        "hemta vinst": "take_profit", "stoppa ut": "cut_loss", "småsparare": "retail_crowd",
        "intervention": "central_bank_action",
    },
    "da": {
        "gearing": "leverage", "shortsalg": "short_selling", "udligne": "averaging_down",
        "tage gevinst": "take_profit", "smaainvestorer": "retail_crowd",
        "intervention": "central_bank_action",
    },
    "no": {
        "giring": "leverage", "shortsalg": "short_selling", "snitte ned": "averaging_down",
        "ta gevinst": "take_profit", "smaasparere": "retail_crowd",
        "intervensjon": "central_bank_action",
    },
    "fi": {
        "vipu": "leverage", "lyhyeksimyynti": "short_selling", "keskihinnan lasku":
            "averaging_down", "voiton kotiutus": "take_profit", "piensijoittaja":
            "retail_crowd", "interventio": "central_bank_action",
    },
    "ro": {
        "levier": "leverage", "vanzare in lipsa": "short_selling", "mediere in scadere":
            "averaging_down", "marcarea profitului": "take_profit", "investitori mici":
            "retail_crowd", "interventie": "central_bank_action",
    },
    "hu": {
        "tőkeáttétel": "leverage", "shortolás": "short_selling", "átlagár lehúzás":
            "averaging_down", "profitrealizálás": "take_profit", "kisbefektető":
            "retail_crowd", "intervenció": "central_bank_action",
    },
    "cs": {
        "páka": "leverage", "shortování": "short_selling", "průměrování dolů":
            "averaging_down", "vybrat zisk": "take_profit", "drobní investoři":
            "retail_crowd", "intervence": "central_bank_action",
    },
    "ms": {
        "leveraj": "leverage", "jualan pendek": "short_selling", "purata turun":
            "averaging_down", "ambil untung": "take_profit", "pelabur runcit": "retail_crowd",
        "campur tangan": "central_bank_action",
    },
    "tl": {
        "palakas": "leverage", "shorting": "short_selling", "average down": "averaging_down",
        "kumita": "take_profit", "maliit na mamumuhunan": "retail_crowd",
        "panghihimasok": "central_bank_action",
    },
    "sw": {
        "mkopo wa biashara": "leverage", "kuuza bila kumiliki": "short_selling",
        "wawekezaji wadogo": "retail_crowd", "kuingilia soko": "central_bank_action",
    },
    "ur": {
        "لیوریج": "leverage", "شارٹ سیلنگ": "short_selling", "اوسط کم کرنا":
            "averaging_down", "منافع لینا": "take_profit", "چھوٹے سرمایہ کار": "retail_crowd",
        "مداخلت": "central_bank_action",
    },
    "bn": {
        "লিভারেজ": "leverage", "শর্ট সেলিং": "short_selling", "গড় করা": "averaging_down",
        "মুনাফা তোলা": "take_profit", "খুচরা বিনিয়োগকারী": "retail_crowd",
        "হস্তক্ষেপ": "central_bank_action",
    },
    "el": {
        "μόχλευση": "leverage", "ανοιχτή πώληση": "short_selling", "μέσος όρος προς τα κάτω":
            "averaging_down", "κατοχύρωση κέρδους": "take_profit", "μικροεπενδυτές":
            "retail_crowd", "παρέμβαση": "central_bank_action", "φίξινγκ": "fx_fixing",
    },
    "sr": {
        "полуга": "leverage", "кратка продаја": "short_selling", "усредњавање":
            "averaging_down", "узимање профита": "take_profit", "мали улагачи": "retail_crowd",
        "интервенција": "central_bank_action",
    },
    "kk": {
        "иінтірек": "leverage", "қысқа сату": "short_selling", "орташалау": "averaging_down",
        "пайда алу": "take_profit", "ұсақ инвесторлар": "retail_crowd",
        "интервенция": "central_bank_action",
    },
    "az": {
        "kredit çiyini": "leverage", "açıq satış": "short_selling", "ortalama aşağı":
            "averaging_down", "mənfəət götürmək": "take_profit", "kiçik investorlar":
            "retail_crowd", "müdaxilə": "central_bank_action",
    },
    "uz": {
        "leverij": "leverage", "qisqa sotuv": "short_selling", "oʻrtacha pasaytirish":
            "averaging_down", "foyda olish": "take_profit", "mayda investorlar":
            "retail_crowd", "aralashuv": "central_bank_action",
    },
}

#: Which languages the desk has a TERMINOLOGY MAP for. A language outside this set is understood
#: at the script/profile level and nothing more -- its slang, its jargon and its instrument names
#: are unknown, which is why `understand` marks it for the seat and why the understanding seat
#: publishes the gap list for the source scouts to fill.
TERMINOLOGY_LANGS: frozenset[str] = frozenset(set(SLANG) | set(mc.LANGUAGES))


def has_terminology(lang: str) -> bool:
    """True when this desk can read the language's own trading vocabulary, not just its script."""
    code = (lang or "").strip()
    return code in TERMINOLOGY_LANGS or code.split("-")[0] in TERMINOLOGY_LANGS


def languages_without_terminology(seen: Iterable[str]) -> list[str]:
    """Of the languages actually seen, the ones with no terminology map. THE GAP LIST."""
    return sorted({str(x) for x in seen if x and x != "und" and not has_terminology(str(x))})


#: Languages whose words are separated by spaces AND do not glue particles onto the front of a
#: word, so a slang term may be matched WORD-BOUNDED. Japanese, Chinese, Korean and Thai are
#: absent because they do not delimit words at all and `\w` matches their characters, so a
#: lookaround would make every term fail inside real prose. Arabic, Persian, Urdu, Hebrew and
#: Bengali are absent for the opposite reason: they PREFIX -- "البيع" becomes "والبيع" with a
#: conjunction glued on, and a leading `(?<!\w)` then refuses a term that is plainly there.
_SPACE_DELIMITED: frozenset[str] = frozenset({
    "en", "de", "es", "pt", "fr", "it", "pl", "tr", "id", "ms", "nl", "sv", "da", "no", "fi",
    "ro", "hu", "cs", "sw", "tl", "vi", "ru", "uk", "sr", "kk", "az", "uz", "el",
})


def _slang_key(lang: str) -> str:
    """A language code as the SLANG table spells it (zh-Hans and zh-CN are both `zh`)."""
    code = (lang or "").strip()
    if code in SLANG:
        return code
    base = code.split("-")[0]
    return base if base in SLANG else ""


def _slang_pattern(lang: str) -> re.Pattern[str]:
    """One alternation per language, LONGEST TERM FIRST so "stop hunt" is never eaten by "stop"
    -- Python's `|` takes the first branch that matches, so the order in the pattern IS the
    precedence rule."""
    bounded = lang in _SPACE_DELIMITED
    parts: list[str] = []
    for term in sorted(SLANG[lang], key=lambda t: (-len(t), t)):
        body = re.escape(term.lower())
        parts.append(rf"(?<!\w){body}(?!\w)" if bounded else body)
    return re.compile("|".join(parts))


_SLANG_RX: dict[str, re.Pattern[str]] = {lang: _slang_pattern(lang) for lang in SLANG}
#: Languages whose slang is checked on EVERY text regardless of the identified language, because
#: their terms cannot collide with another language's words: they are written in their own script.
_ALWAYS_SCAN: tuple[str, ...] = ("ja", "ko", "zh", "zh-Hant", "ru", "uk", "sr", "kk", "ar", "fa",
                                 "ur", "hi", "bn", "th", "he", "el", "vi")


def canonicalise(text: str, lang: str = "") -> list[Concept]:
    """Every slang/jargon term the text uses, as desk concepts, in document order.

    The identified language is scanned first; the non-Latin languages are ALWAYS scanned, because
    a Japanese term inside an English sentence is still a Japanese term and the whole point of a
    code-switching desk is that it does not need to be told twice. A term whose concept id is
    empty (`cable`, `loonie`) is an INSTRUMENT nickname, not a mechanism, and is left to
    `instruments_named`.
    """
    low = str(text or "").lower()
    langs: list[str] = []
    for code in (_slang_key(lang), *_ALWAYS_SCAN, "en"):
        if code in SLANG and code not in langs:
            langs.append(code)
    found: list[tuple[int, Concept]] = []
    claimed: list[tuple[int, int]] = []
    for code in langs:
        for m in _SLANG_RX[code].finditer(low):
            term = m.group(0)
            concept_id = SLANG[code].get(term) or SLANG[code].get(term.lower()) or ""
            if not concept_id:
                continue
            at = m.start()
            if any(a <= at < b for a, b in claimed):
                continue
            claimed.append((at, m.end()))
            spec = CONCEPTS.get(concept_id)
            if spec is None:
                found.append((at, Concept(concept_id, term, code, "", unmapped=True)))
                continue
            found.append((at, Concept(
                concept_id=concept_id, term=term, lang=code, gloss=spec.gloss,
                mechanism_class=spec.mechanism_class, axis_mechanism=spec.axis_mechanism,
                ontology_id=spec.ontology_id,
                unmapped=not (spec.mechanism_class or spec.axis_mechanism or spec.ontology_id),
                fenced=spec.fenced)))
    found.sort(key=lambda pair: pair[0])
    out: list[Concept] = []
    seen: set[str] = set()
    for _at, concept in found:
        if concept.concept_id in seen:
            continue
        seen.add(concept.concept_id)
        out.append(concept)
    return out


# ============================================================================ instruments
#: Aliases `mechanism_claims.INSTRUMENT_ALIASES` does NOT resolve, measured against it on
#: 2026-09-17. Kept SHORT and here rather than merged into that table, so there is still exactly
#: one instrument-alias table on the desk and this module stays a layer over it.
EXTRA_ALIASES: tuple[tuple[tuple[str, ...], tuple[str, ...]], ...] = (
    (("swissy", "swissie", "スイスフラン", "스위스프랑", "франк"), ("USDCHF",)),
    (("кабель", "кабел"), ("GBPUSD",)),
    (("브렌트", "브렌트유", "ブレント", "برنت"), ("XBRUSD", "UKOIL")),
    (("서부텍사스유", "두바이유", "ウエスト・テキサス"), ("XTIUSD", "USOIL")),
    (("золотник", "金(きん)", "きん相場"), ("XAUUSD",)),
    (("루니", "ルーニー", "луни"), ("USDCAD",)),
    (("키위", "キウイ", "киви"), ("NZDUSD",)),
    (("오시", "オージー", "осси"), ("AUDUSD",)),
    (("유로엔", "ユーロ円", "евройена"), ("EURJPY",)),
    (("파운드엔", "ポンド円", "фунт иена"), ("GBPJPY",)),
)
#: Bare single-character instrument names, matched ONLY inside their own script. 金 is gold in
#: Japanese and Chinese and is one character, so a substring rule would fire inside 資金, 現金,
#: 税金 and every other compound -- it is matched with a boundary check instead.
_BARE_CJK: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("金", ("XAUUSD",)), ("銀", ("XAGUSD",)), ("銅", ("XCUUSD",)),
)
#: HAN ONLY, and that is the whole trick. A neighbouring HAN character means a compound (資金,
#: 現金, 税金, 金曜) and the glyph is not the metal; a neighbouring KANA is a particle (金が, 金は)
#: and the glyph IS the metal. Including kana in this class -- which the first draft did -- made
#: every Japanese sentence about gold resolve to no instrument at all.
_HAN_ONLY = re.compile(r"[㐀-鿿]")


def _bare_cjk_hits(text: str) -> list[str]:
    out: list[str] = []
    for glyph, symbols in _BARE_CJK:
        for m in re.finditer(re.escape(glyph), text):
            before = text[m.start() - 1] if m.start() else ""
            after = text[m.end()] if m.end() < len(text) else ""
            if _HAN_ONLY.match(before or " ") or _HAN_ONLY.match(after or " "):
                continue          # part of a compound (資金, 金曜), not the metal
            out.extend(s for s in symbols if s not in out)
            break
    return out


def instruments_named(text: str, universe: set[str] | None = None) -> dict[str, Any]:
    """MT5 instruments a text names, in any language. `mechanism_claims.resolve_instruments`
    does the work; this adds the aliases measured missing from it and the bare CJK metals."""
    resolved = mc.resolve_instruments(text or "", universe)
    analogues: list[str] = list(resolved.get("analogues") or [])
    mentioned: list[str] = list(resolved.get("mentioned") or [])
    low = (text or "").lower()
    for aliases, symbols in EXTRA_ALIASES:
        hit = next((a for a in aliases if a.lower() in low), None)
        if hit is None:
            continue
        mentioned.append(hit)
        for sym in symbols:
            if sym not in analogues and (universe is None or sym.upper() in
                                         {u.upper() for u in universe}):
                analogues.append(sym)
                break
    for sym in _bare_cjk_hits(text or ""):
        if sym not in analogues:
            analogues.append(sym)
            mentioned.append(sym)
    return {"analogues": analogues, "mentioned": mentioned,
            "transfer_only": list(resolved.get("transfer_only") or []),
            "indirect": list(resolved.get("indirect") or []),
            "channels": list(resolved.get("channels") or [])}


# ============================================================================ numbers
@dataclass(frozen=True)
class ParsedNumber:
    """One quantity, with the LOCALE RULE that decided its decimal separator stated."""

    text: str
    value: float
    kind: str
    rule: str


#: Languages that write 1,5 for one and a half. The separator is a LOCALE fact, not a guess, and
#: reading "1,5" as fifteen in a German post is a 10x error in a claim about a spread.
DECIMAL_COMMA: frozenset[str] = frozenset({
    "de", "fr", "es", "pt", "it", "nl", "pl", "cs", "sk", "sl", "hr", "sr", "sr-Latn", "bs",
    "ro", "hu", "tr", "ru", "uk", "be", "bg", "mk", "lv", "lt", "et", "fi", "sv", "da", "no",
    "is", "sq", "el", "ca", "gl", "eu", "af", "id", "vi", "uz", "az", "kk", "ky", "mn", "tg",
})
_NUM = re.compile(r"[-+]?\d{1,3}(?:[., ' ]\d{3})+(?:[.,]\d+)?|[-+]?\d+(?:[.,]\d+)?")
#: Suffix multipliers, longest first. CJK 万/億, Korean 만/억/조 and Indian lakh/crore are how
#: those communities state size; reading 3億 as 3 is not a rounding error, it is 1e8 of one.
_MULTIPLIERS: tuple[tuple[str, float], ...] = (
    ("兆", 1e12), ("조", 1e12), ("億", 1e8), ("亿", 1e8), ("억", 1e8), ("萬", 1e4), ("万", 1e4),
    ("만", 1e4), ("千", 1e3), ("천", 1e3), ("百", 1e2), ("백", 1e2),
    ("crore", 1e7), ("करोड़", 1e7), ("lakh", 1e5), ("लाख", 1e5),
    ("trillion", 1e12), ("billion", 1e9), ("million", 1e6), ("thousand", 1e3),
    ("mrd", 1e9), ("mln", 1e6), ("tys", 1e3),
    ("trn", 1e12), ("tn", 1e12), ("bn", 1e9), ("mn", 1e6), ("k", 1e3), ("m", 1e6), ("b", 1e9),
)
_PERCENT = ("%", "％", "パーセント", "퍼센트", "百分", "процент", "بالمئة", "prozent", "por ciento",
            "pour cent", "फीसदी", "درصد")
#: THE LATIN MULTIPLIERS NEED A RIGHT BOUNDARY and the CJK ones do not. Without `(?![A-Za-z])`,
#: "2 bars" is two BILLION and "1.5 metres" is a million and a half -- a suffix rule that reads
#: the first letter of the next word is not a unit parser, it is a random multiplier.
_MULT_RE = re.compile(
    r"^[  ]?(" + "|".join(re.escape(s) for s, _ in sorted(
        _MULTIPLIERS, key=lambda kv: -len(kv[0]))) + r")(?![A-Za-z])")
_MULT_BY: dict[str, float] = dict(_MULTIPLIERS)


def _decide_value(raw: str, lang: str) -> tuple[float, str] | None:
    """(value, rule) for one matched number, or None when it cannot be read honestly."""
    token = raw.replace(" ", " ").replace("'", " ").strip()
    sign = -1.0 if token.startswith("-") else 1.0
    token = token.lstrip("+-")
    has_dot, has_comma = "." in token, "," in token
    rule: str
    if has_dot and has_comma:
        decimal = "." if token.rindex(".") > token.rindex(",") else ","
        rule = f"both separators present; the last one ({decimal}) is the decimal"
    elif has_dot or has_comma:
        sep = "." if has_dot else ","
        tail = token.split(sep)[-1]
        if token.count(sep) > 1:
            decimal, rule = "", f"{sep} repeats: thousands grouping"
        elif len(tail) == 3:
            # THREE TRAILING DIGITS IS THE AMBIGUOUS CASE and the locale is the only thing that
            # can settle it: "1,500" is fifteen hundred in English and one-point-five in German.
            # Guessing one convention for both is a 1000x error in a claim about a level.
            comma_lang = lang in DECIMAL_COMMA or lang.split("-")[0] in DECIMAL_COMMA
            if sep == "," and comma_lang:
                decimal, rule = sep, f"locale {lang!r} writes , as the decimal"
            elif sep == "." and comma_lang:
                decimal, rule = "", f"locale {lang!r} writes . as thousands grouping"
            else:
                decimal, rule = "", f"three trailing digits: {sep} is thousands grouping"
        else:
            decimal, rule = sep, f"{len(tail)} trailing digit(s): {sep} is the decimal"
    else:
        decimal, rule = "", "no separator"
    body = token
    for ch in (".", ",", " "):
        if ch != decimal:
            body = body.replace(ch, "")
    if decimal:
        body = body.replace(decimal, ".")
    try:
        return sign * float(body), rule
    except ValueError:
        return None


def numbers_in(text: str, lang: str = "", limit: int = MAX_NUMBERS) -> list[ParsedNumber]:
    """Quantities a text states, across locales, with their multipliers and percent applied."""
    body = str(text or "")
    out: list[ParsedNumber] = []
    for m in _NUM.finditer(body):
        # A DATE IS NOT THREE NUMBERS. "2026-09-17" would otherwise yield 2026, MINUS NINE and
        # MINUS SEVENTEEN, and a claim summarised as "mentions -9" is worse than one that
        # mentions nothing. The sign is part of the match, so the digit to look at is the one
        # before the sign -- checking the character before the match start alone misses it.
        token = m.group(0)
        prev = body[m.start() - 1] if m.start() else ""
        if token[:1] in ("-", "+") and prev.isdigit():
            continue
        if prev in ("-", "/", ":") and m.start() >= 2 and body[m.start() - 2].isdigit():
            continue
        parsed = _decide_value(m.group(0), lang)
        if parsed is None:
            continue
        value, rule = parsed
        tail = body[m.end():m.end() + 16]
        kind = "decimal"
        hit = _MULT_RE.match(tail.lower())
        if hit is not None:
            factor = _MULT_BY[hit.group(1)]
            value *= factor
            kind = "scaled"
            rule = f"{rule}; multiplier {hit.group(1)} = {factor:g}"
        stripped = tail.lstrip("  ")
        if any(stripped.lower().startswith(p) for p in _PERCENT):
            kind = "percent"
        out.append(ParsedNumber(m.group(0), value, kind, rule))
        if len(out) >= limit:
            break
    return out


# ============================================================================ dates
@dataclass(frozen=True)
class ParsedDate:
    """One date, with the CALENDAR it was written in. `iso` is empty when the calendar cannot be
    converted exactly -- a Hijri date needs a lunar calendar this module does not ship, and
    inventing one would put a wrong `knowable_at` on a claim."""

    text: str
    calendar: str
    year: int | None = None
    month: int | None = None
    day: int | None = None
    iso: str = ""
    rule: str = ""
    unmeasured: str = ""


#: Era name -> the Gregorian year its year 1 falls in, minus one (so year N = base + N). Exact
#: arithmetic, not an approximation: 令和8年 IS 2026.
_ERAS: dict[str, int] = {"令和": 2018, "平成": 1988, "昭和": 1925, "大正": 1911, "明治": 1867}
_ERA_RE = re.compile(r"(令和|平成|昭和|大正|明治)\s*(元|\d{1,2})\s*年"
                     r"(?:\s*(\d{1,2})\s*月)?(?:\s*(\d{1,2})\s*日)?")
_ROC_RE = re.compile(r"民國\s*(\d{1,3})\s*年(?:\s*(\d{1,2})\s*月)?(?:\s*(\d{1,2})\s*日)?")
_BUDDHIST_RE = re.compile(r"(?:พ\.?ศ\.?|B\.?E\.?)\s*(\d{4})")
_CJK_DATE = re.compile(r"(\d{4})\s*年\s*(\d{1,2})\s*月(?:\s*(\d{1,2})\s*日)?")
_KO_DATE = re.compile(r"(\d{4})\s*년\s*(\d{1,2})\s*월(?:\s*(\d{1,2})\s*일)?")
_ISO_DATE = re.compile(r"(?<!\d)(\d{4})-(\d{2})-(\d{2})(?!\d)")
_NUM_DATE = re.compile(r"(?<!\d)(\d{1,2})[./](\d{1,2})[./](\d{2,4})(?!\d)")
_HIJRI_MONTHS: tuple[str, ...] = (
    "محرم", "صفر", "ربيع الأول", "ربيع الآخر", "جمادى الأولى", "جمادى الآخرة", "رجب", "شعبان",
    "رمضان", "شوال", "ذو القعدة", "ذو الحجة",
    "muharram", "safar", "rabi al-awwal", "rabi al-thani", "jumada al-awwal", "jumada al-thani",
    "rajab", "shaaban", "sha'ban", "ramadan", "shawwal", "dhu al-qadah", "dhu al-hijjah",
)
_HIJRI_RE = re.compile("(" + "|".join(re.escape(m) for m in _HIJRI_MONTHS) + r")\s*(\d{1,4})?",
                       re.IGNORECASE)
#: Locales that write month first. Everywhere else on earth writes the day first, and getting
#: 03/04 backwards moves a claim's knowable_at by a month.
_MONTH_FIRST: frozenset[str] = frozenset({"en", "en-US", "tl"})


def _iso(y: int | None, m: int | None, d: int | None) -> str:
    if y is None:
        return ""
    if m is None:
        return f"{y:04d}"
    return f"{y:04d}-{m:02d}" if d is None else f"{y:04d}-{m:02d}-{d:02d}"


def dates_in(text: str, lang: str = "", limit: int = MAX_DATES) -> list[ParsedDate]:
    """Dates a text states, in any calendar it states them in.

    Japanese and ROC eras convert EXACTLY (they are fixed offsets) and Thai Buddhist years are
    year - 543. Hijri is recorded and NOT converted: the lunar calendar needs a table this module
    does not carry, and a guessed Gregorian date on a claim is a lookahead waiting to happen.
    """
    body = str(text or "")
    out: list[ParsedDate] = []

    def add(d: ParsedDate) -> bool:
        out.append(d)
        return len(out) >= limit

    y: int
    mo: int | None
    day: int | None
    for m in _ISO_DATE.finditer(body):
        y, mo, day = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if add(ParsedDate(m.group(0), "gregorian", y, mo, day, _iso(y, mo, day), "ISO 8601")):
            return out
    for m in _ERA_RE.finditer(body):
        era = m.group(1)
        n = 1 if m.group(2) == "元" else int(m.group(2))
        y = _ERAS[era] + n
        mo = int(m.group(3)) if m.group(3) else None
        day = int(m.group(4)) if m.group(4) else None
        if add(ParsedDate(m.group(0), "japanese_era", y, mo, day, _iso(y, mo, day),
                          f"{era} year {n} = {_ERAS[era]} + {n}")):
            return out
    for m in _ROC_RE.finditer(body):
        y = 1911 + int(m.group(1))
        mo = int(m.group(2)) if m.group(2) else None
        day = int(m.group(3)) if m.group(3) else None
        if add(ParsedDate(m.group(0), "roc", y, mo, day, _iso(y, mo, day),
                          f"民國 {m.group(1)} = 1911 + {m.group(1)}")):
            return out
    for m in _BUDDHIST_RE.finditer(body):
        y = int(m.group(1)) - 543
        if add(ParsedDate(m.group(0), "buddhist", y, None, None, _iso(y, None, None),
                          f"{m.group(1)} BE - 543")):
            return out
    for rx, cal in ((_CJK_DATE, "gregorian"), (_KO_DATE, "gregorian")):
        for m in rx.finditer(body):
            y, mo = int(m.group(1)), int(m.group(2))
            day = int(m.group(3)) if m.group(3) else None
            if add(ParsedDate(m.group(0), cal, y, mo, day, _iso(y, mo, day),
                              "CJK year/month/day markers")):
                return out
    for m in _HIJRI_RE.finditer(body):
        year = int(m.group(2)) if m.group(2) else None
        if add(ParsedDate(m.group(0), "hijri", year, None, None, "",
                          "Hijri month named",
                          "the Gregorian date is UNMEASURED: converting a lunar calendar needs "
                          "a table this module does not ship, and a guessed date is a lookahead")):
            return out
    month_first = lang in _MONTH_FIRST or (not lang and False)
    for m in _NUM_DATE.finditer(body):
        a, b = int(m.group(1)), int(m.group(2))
        raw_year = int(m.group(3))
        y = raw_year + 2000 if raw_year < 100 else raw_year
        if a > 12:
            day, mo, rule = a, b, "first field > 12: day first"
        elif b > 12:
            mo, day, rule = a, b, "second field > 12: month first"
        elif month_first:
            mo, day, rule = a, b, f"locale {lang} writes month first"
        else:
            day, mo, rule = a, b, f"locale {lang or 'unknown'} writes day first"
        if add(ParsedDate(m.group(0), "gregorian", y, mo, day, _iso(y, mo, day), rule)):
            return out
    return out


# ============================================================================ understanding
@dataclass(frozen=True)
class Understanding:
    """Everything this desk can read off one piece of text WITHOUT calling anything.

    `needs_seat` is the load-bearing field and the principal's order in one boolean: a document
    this layer cannot read is not dropped, it is HANDED ON, with the reason attached.
    """

    text: str
    normalised: str
    lang: str
    script: str
    confidence: float
    alternatives: tuple[tuple[str, float], ...] = ()
    segments: tuple[Segment, ...] = ()
    languages: tuple[str, ...] = ()
    transliteration: str = ""
    concepts: tuple[Concept, ...] = ()
    instruments: tuple[str, ...] = ()
    instruments_mentioned: tuple[str, ...] = ()
    transfer_only: tuple[str, ...] = ()
    numbers: tuple[ParsedNumber, ...] = ()
    dates: tuple[ParsedDate, ...] = ()
    has_terminology: bool = False
    fenced: tuple[str, ...] = ()
    needs_seat: bool = False
    needs_seat_reason: str = ""
    rule: str = RULE

    @property
    def slang_hits(self) -> int:
        return len(self.concepts)

    def to_row(self) -> dict[str, Any]:
        """A JSON-safe dict. Used by the understanding seat's report and its task rows."""
        return {
            "lang": self.lang, "script": self.script, "confidence": round(self.confidence, 3),
            "alternatives": [[a, b] for a, b in self.alternatives],
            "languages": list(self.languages), "transliteration": self.transliteration,
            "concepts": [{"concept_id": c.concept_id, "term": c.term, "lang": c.lang,
                          "mechanism_class": c.mechanism_class,
                          "axis_mechanism": c.axis_mechanism, "ontology_id": c.ontology_id,
                          "unmapped": c.unmapped, "fenced": c.fenced} for c in self.concepts],
            "instruments": list(self.instruments),
            "instruments_mentioned": list(self.instruments_mentioned),
            "transfer_only": list(self.transfer_only),
            "numbers": [{"text": n.text, "value": n.value, "kind": n.kind, "rule": n.rule}
                        for n in self.numbers],
            "dates": [{"text": d.text, "calendar": d.calendar, "iso": d.iso, "rule": d.rule,
                       "unmeasured": d.unmeasured} for d in self.dates],
            "has_terminology": self.has_terminology, "fenced": list(self.fenced),
            "needs_seat": self.needs_seat, "needs_seat_reason": self.needs_seat_reason,
            "rule": self.rule,
        }


def understand(text: str, *, universe: set[str] | None = None) -> Understanding:
    """The whole pipeline on one piece of text: identify, segment, normalise, canonicalise, name.

    THE LAST THREE LINES ARE THE ORDER. `needs_seat` is set when the confidence is below
    `SEAT_CONFIDENCE`, when the language is `und`, or when the language has no terminology map --
    and the REASON is carried, because "we could not read it" and "we could read the script but
    not the vocabulary" send the seat two different questions and the second one also tells the
    source scouts which forest has no map yet.
    """
    body = str(text or "")
    guess = identify(body)
    parts = tuple(segments(body))
    langs = tuple(dict.fromkeys(s.lang for s in parts if s.lang))
    normalised = normalise(body, guess.lang)
    concepts = tuple(canonicalise(body, guess.lang))
    resolved = instruments_named(body, universe)
    terminology = has_terminology(guess.lang)

    reasons: list[str] = []
    if guess.lang == "und":
        reasons.append(f"language unknown ({guess.rule or 'no profile matched'})")
    if guess.confidence < SEAT_CONFIDENCE:
        reasons.append(f"confidence {guess.confidence:.2f} < {SEAT_CONFIDENCE}")
    if not terminology and guess.lang != "und":
        reasons.append(f"no terminology map for {guess.lang!r}: script read, vocabulary unknown")
    unmapped = [c.concept_id for c in concepts if c.unmapped]
    if unmapped:
        reasons.append(f"concepts with no mechanism mapping: {', '.join(sorted(set(unmapped)))}")

    return Understanding(
        text=body,
        normalised=normalised,
        lang=guess.lang,
        script=guess.script,
        confidence=guess.confidence,
        alternatives=guess.alternatives,
        segments=parts,
        languages=langs,
        transliteration=transliterated(body) or "",
        concepts=concepts,
        instruments=tuple(resolved["analogues"]),
        instruments_mentioned=tuple(resolved["mentioned"]),
        transfer_only=tuple(resolved["transfer_only"]),
        numbers=tuple(numbers_in(body, guess.lang)),
        dates=tuple(dates_in(body, guess.lang)),
        has_terminology=terminology,
        fenced=tuple(dict.fromkeys(c.fenced for c in concepts if c.fenced)),
        needs_seat=bool(reasons),
        needs_seat_reason="; ".join(reasons),
    )


def understand_rows(rows: Sequence[Mapping[str, Any]], field_chain: Sequence[str] = ("text",),
                    ) -> list[Understanding]:
    """`understand` over a batch of rows, reading the first non-empty field in `field_chain`.

    A convenience for the understanding seat and the dashboards; it holds no policy of its own.
    """
    out: list[Understanding] = []
    for row in rows:
        body = ""
        for key in field_chain:
            value = row.get(key)
            if isinstance(value, str) and value.strip():
                body = value
                break
        out.append(understand(body))
    return out


# ======================================================= native semantic search (query gen)
#: THE TEN SOURCE LAYERS a forest is mined at. A language is not one corpus: a central bank
#: circular, a sell-side note, a thesis, a quant blog, a message board, an EA marketplace, a
#: newspaper, a dead forum's archive, a customs table and a link directory are ten different
#: populations with ten different vocabularies, and a query that works on one finds nothing on
#: the others.
SOURCE_LAYERS: tuple[str, ...] = (
    "official", "institutional", "academic", "practitioner", "retail_ecology",
    "app_ecosystem", "media", "archive", "physical_economy", "source_graph",
)

#: `deep_forest_sources.json` ground `kind` -> layer, so the 500 declared grounds and the term
#: tables below JOIN instead of being two vocabularies about the same world. The grounds file
#: stays the registry of WHERE to look; this module is the vocabulary of WHAT to ask.
GROUND_KIND_LAYER: dict[str, str] = {
    "macro": "official", "official": "official", "dataset": "official",
    "research": "institutional", "column": "institutional",
    "academic": "academic",
    "code": "practitioner", "notebook": "practitioner", "blog": "practitioner",
    "competition": "practitioner", "interview": "practitioner",
    "forum": "retail_ecology", "community": "retail_ecology", "qa": "retail_ecology",
    "social": "retail_ecology",
    "video": "media", "news": "media",
    "archive": "archive",
    "web": "source_graph",
}


@dataclass(frozen=True)
class EvidencePolicy:
    """FRINGE, CONTRADICTORY AND LOW-CONFIDENCE MATERIAL IS EVIDENCE (principal, 2026-09-17).

    A retail board insisting on something false is not noise about the world; it is a
    measurement of what a crowd believes, and a crowd that believes something is positioned for
    it. Crowding and narrative are features. Nothing in this module or the understanding seat
    may drop a document for being unreliable -- reliability is a PROPERTY RECORDED ON the
    document, never a filter applied before anybody has read it.
    """

    keep_fringe: bool = True
    keep_contradictory: bool = True
    keep_low_confidence: bool = True
    why: str = ("a crowd that believes something is positioned for it: fringe and contradictory "
                "public material is a crowding/narrative feature, not noise")

    def may_drop(self, reason: str) -> bool:
        """False for every reliability-shaped reason. There is no flag that turns this off."""
        return False


PRESERVE_FRINGE = EvidencePolicy()

#: The second half of a native query: what is being ASKED FOR, in the language's own words.
#: Rotated against the layer terms, so one layer term produces several genuinely different
#: searches rather than one phrase repeated.
PROBE_TERMS: dict[str, tuple[str, ...]] = {
    "ja": ("手法", "検証", "実績", "ルール", "解説", "統計", "アノマリー", "勝率"),
    "ko": ("기법", "검증", "실적", "매매법", "분석", "통계", "아노말리", "승률"),
    "zh": ("方法", "实盘", "复盘", "规则", "逻辑", "统计", "胜率", "回测"),
    "zh-Hant": ("方法", "實盤", "覆盤", "規則", "邏輯", "統計", "勝率", "回測"),
    "ru": ("метод", "тест", "результаты", "правила", "логика", "статистика", "бэктест"),
    "uk": ("метод", "тест", "результати", "правила", "логіка", "статистика"),
    "pt": ("método", "backtest", "resultados", "regras", "estatística", "estudo"),
    "es": ("método", "backtest", "resultados", "reglas", "estadística", "estudio"),
    "tr": ("yöntem", "backtest", "sonuçlar", "kurallar", "istatistik", "çalışma"),
    "vi": ("phương pháp", "backtest", "kết quả", "quy tắc", "thống kê", "nghiên cứu"),
    "id": ("metode", "backtest", "hasil", "aturan", "statistik", "riset"),
    "ar": ("طريقة", "اختبار", "نتائج", "قواعد", "إحصاء", "دراسة"),
    "hi": ("तरीका", "बैकटेस्ट", "नतीजे", "नियम", "आंकड़े", "अध्ययन"),
    "th": ("วิธี", "แบ็คเทสต์", "ผลลัพธ์", "กฎ", "สถิติ", "งานวิจัย"),
    "de": ("Methode", "Backtest", "Ergebnisse", "Regeln", "Statistik", "Studie"),
    "fr": ("méthode", "backtest", "résultats", "règles", "statistique", "étude"),
    "it": ("metodo", "backtest", "risultati", "regole", "statistica", "studio"),
    "pl": ("metoda", "backtest", "wyniki", "zasady", "statystyka", "badanie"),
    "en": ("method", "backtest", "results", "rules", "statistics", "study"),
}

#: NATIVE TERMINOLOGY PER LANGUAGE PER LAYER. Every entry is a phrase that community actually
#: types -- an institution's own name, a board's own slang, a platform's own product name -- and
#: NOT an English phrase run through a translator once. That distinction is the whole point: a
#: translated query finds the already-translated corpus, which is the corpus everybody has read
#: and therefore the one with no edge left in it.
#:
#: A LANGUAGE/LAYER THAT IS ABSENT IS UNMEASURED, NEVER FILLED. `query_coverage` names every
#: hole and the understanding seat publishes the list, because inventing a plausible-looking
#: translated phrase would convert a known gap into a silent wrong answer.
NATIVE_TERMS: dict[str, dict[str, tuple[str, ...]]] = {
    "ja": {
        "official": ("日本銀行", "日銀 金融政策決定会合", "財務省 為替介入", "金融庁",
                     "東京証券取引所", "大阪取引所 先物", "日銀短観", "国際収支 統計",
                     "実需 フロー"),
        "institutional": ("為替見通し レポート", "野村證券 調査部", "大和証券 リサーチ",
                          "三菱UFJ 為替", "みずほ マーケット", "ストラテジスト 見通し",
                          "機関投資家 フロー"),
        "academic": ("証券アナリストジャーナル", "日本ファイナンス学会", "紀要 実証分析",
                     "博士論文 ボラティリティ", "計量 金融 論文"),
        "practitioner": ("システムトレード", "自動売買 EA", "MT4 EA 検証", "MT5 自動売買",
                         "バックテスト 結果", "裁量トレード 手法", "アルゴリズム取引",
                         "Qiita 株価 予測", "Zenn 金融 データ", "はてなブログ 投資 検証",
                         "note 手法 公開", "フォワードテスト 実績"),
        "retail_ecology": ("為替板", "5ch FX スレ", "2ch 為替 まとめ", "掲示板 専業トレーダー",
                           "塩漬け 含み損", "損切り できない", "握力 ガチホ", "イナゴ 投資家",
                           "ナンピン 地獄", "追証 体験", "億トレーダー 手法", "低レバ 運用"),
        "app_ecosystem": ("GogoJungle EA", "MQL5 マーケット EA", "インジケーター 販売",
                          "自動売買ツール 比較", "TradingView インジケーター 日本語",
                          "国内FX 海外FX スプレッド", "ゼロカット 追証なし",
                          "約定力 スリッページ", "くりっく365"),
        "media": ("日本経済新聞 為替", "ロイター 東京 市場", "ブルームバーグ 円",
                  "東洋経済 相場", "ザイFX 実践", "みんかぶ FX", "株探 材料"),
        "archive": ("2ch 過去ログ 為替", "過去ログ 倉庫", "旧掲示板 アーカイブ", "ミラー 保存"),
        "physical_economy": ("輸出企業 為替 予約", "輸入企業 ドル 買い", "実需筋 フロー",
                             "商社 原油 調達", "液化天然ガス 輸入", "貿易統計 通関",
                             "金 現物 地金"),
        "source_graph": ("FX ブログ まとめ", "投資 リンク集", "トレーダー 一覧",
                         "検証 サイト 比較"),
        "_extra": ("キャリートレード", "円キャリー", "スワップ狙い", "スワップポイント 生活",
                   "高金利通貨 長期保有", "仲値 五十日", "ゴトー日 アノマリー"),
    },
    "ko": {
        "official": ("한국은행 기준금리", "기획재정부 외환", "금융위원회", "금융감독원",
                     "한국거래소 파생", "외환보유액", "국제수지 통계", "외환시장 개입"),
        "institutional": ("증권사 리포트", "리서치센터 전망", "애널리스트 보고서",
                          "미래에셋 리서치", "삼성증권 전망", "키움증권 데일리",
                          "NH투자증권 전략", "하우스뷰 환율"),
        "academic": ("한국금융학회 논문", "학술지 실증분석", "석사학위논문 변동성",
                     "금융연구 논문"),
        "practitioner": ("시스템트레이딩", "자동매매 프로그램", "알고리즘 매매", "퀀트 백테스트",
                         "전략 검증 결과", "파이썬 퀀트 투자", "예스트레이더 전략",
                         "트레이딩뷰 전략 한국"),
        "retail_ecology": ("디시인사이드 주식 갤러리", "선물옵션 갤러리", "네이버 카페 주식",
                           "종목토론방", "개미 필패", "존버 후기", "물타기 실패",
                           "반대매매 경험", "빚투 후기", "리딩방 후기"),
        "app_ecosystem": ("HTS 지표", "MTS 자동매매", "영웅문 수식", "자동매매 프로그램 판매",
                          "지표 개발 의뢰"),
        "media": ("한국경제 환율", "매일경제 시황", "연합인포맥스 외환", "이데일리 마켓",
                  "머니투데이 증권"),
        "archive": ("과거 게시글 아카이브", "옛날 종토방 글", "웹 아카이브 게시판"),
        "physical_economy": ("수출입 무역수지", "조선 수주", "반도체 수출 통계", "정유 마진",
                             "네고 물량 환율", "수출업체 달러 매도"),
        "source_graph": ("투자 블로그 모음", "퀀트 자료 정리", "링크 추천 주식"),
        "_extra": ("옵션 만기일 효과", "선물 베이시스", "프로그램 매매 차익", "외인 선물 순매수",
                   "미결제약정 분석", "변동성 장세 대응", "시황 데일리"),
    },
    "zh": {
        "official": ("中国人民银行 公告", "国家外汇管理局 数据", "外管局 结售汇", "统计局 数据",
                     "海关总署 进出口", "上期所 持仓", "大商所 数据", "郑商所 仓单",
                     "中金所 股指期货", "人民币 中间价", "外汇储备 数据"),
        "institutional": ("券商研报 策略", "研究所 深度报告", "首席经济学家 观点",
                          "中信证券 研报", "中金公司 策略", "私募排排网 排名",
                          "私募基金 业绩", "资管 产品 净值"),
        "academic": ("知网 硕士论文 期货", "博士论文 波动率", "金融研究 实证",
                     "管理世界 论文", "实证研究 套利"),
        "practitioner": ("期货日报实盘大赛", "蓝海密剑 冠军", "七禾网 访谈", "聚宽 策略",
                         "JoinQuant 因子", "优矿 研究", "米筐 RiceQuant 策略",
                         "BigQuant 量化", "CTA策略 回测", "程序化交易 规则",
                         "因子挖掘 开源", "Gitee 量化 策略"),
        "retail_ecology": ("知乎 期货 经验", "雪球 讨论 黄金", "股吧 主力", "贴吧 交易",
                           "韭菜 割肉 经历", "抄底 失败", "追涨杀跌 反思", "游资 打板",
                           "散户 亏损 复盘"),
        "app_ecosystem": ("文华财经 公式", "博易大师 指标", "交易开拓者 TB 策略",
                          "通达信 选股公式", "同花顺 指标", "策略商城 CTA"),
        "media": ("财新 报道", "第一财经 市场", "证券时报 数据", "期货日报 分析",
                  "华尔街见闻 快讯", "搜狗微信 期货", "微信公众号 量化"),
        "archive": ("历史帖子 存档", "网页快照 论坛", "老帖 回顾", "论坛 备份"),
        "physical_economy": ("现货升水 贴水", "库存 数据 保税区", "进口利润 测算",
                             "内外盘价差", "上海金 溢价", "点价 套保", "螺纹钢 库存"),
        "source_graph": ("量化 资料 汇总", "策略 合集 整理", "榜单 排名", "导航 目录"),
    },
    "zh-Hant": {
        "official": ("中央銀行 理監事會", "金管會 公告", "台灣期貨交易所 數據",
                     "期交所 三大法人", "證交所 融資融券", "外匯存底"),
        "institutional": ("券商 研究報告", "投顧 分析", "外資 報告", "法人 觀點"),
        "academic": ("碩士論文 期貨", "實證研究 波動", "學術期刊 金融"),
        "practitioner": ("程式交易 策略", "多因子 回測", "量化 台指期", "XQ 全球贏家 選股",
                         "海期 交易 紀錄"),
        "retail_ecology": ("PTT 股票板", "PTT 期貨板", "韭菜 停損", "散戶 追漲殺跌",
                           "當沖 心得", "籌碼面 分析"),
        "app_ecosystem": ("XQ 指標", "MultiCharts 策略", "券商 API 下單", "選擇權 報價軟體"),
        "media": ("鉅亨網 分析", "MoneyDJ 理財", "工商時報 市場", "財訊 專題"),
        "archive": ("PTT 舊文 備份", "網頁 快照 論壇"),
        "physical_economy": ("出口訂單 統計", "半導體 出口", "航運 運價", "貿易順差"),
        "source_graph": ("整理 懶人包", "資源 彙整", "排行 榜單"),
    },
    "ru": {
        "official": ("Банк России решение", "ЦБ РФ ключевая ставка",
                     "Минфин валютные операции", "Мосбиржа объёмы торгов",
                     "валютные интервенции", "платёжный баланс", "Росстат инфляция"),
        "institutional": ("аналитический отчёт рубль", "прогноз по рублю", "стратег ВТБ",
                          "Сбер аналитика", "БКС инвестиции обзор", "Финам прогноз",
                          "брокерская аналитика нефть"),
        "academic": ("Высшая школа экономики диссертация", "эмпирический анализ волатильности",
                     "эконометрика финансовые рынки", "научная статья арбитраж"),
        "practitioner": ("алготрейдинг Python", "торговый робот тест", "советник MQL",
                         "автоследование результаты", "стакан анализ объёмов",
                         "арбитраж между биржами", "скальпинг стратегия",
                         "Habr алготрейдинг", "хабр торговый робот", "QUIK Lua робот",
                         "TSLab стратегия", "Wealth-Lab тест", "оптимизация советника"),
        "retail_ecology": ("смартлаб топик", "smart-lab блог трейдера", "форум трейдеров",
                           "физики против юриков", "слив депозита история",
                           "усреднение убытков", "вынос стопов", "MMGP форекс",
                           "плечо margin call"),
        "app_ecosystem": ("маркет советников MQL5", "индикаторы MT4 скачать",
                          "продажа роботов форекс", "мониторинг счетов", "ПАММ рейтинг",
                          "копирование сделок сигналы"),
        "media": ("РБК рынки", "Ведомости экономика", "Коммерсант валюта", "Интерфакс нефть",
                  "Прайм новости", "Финам новости рынок"),
        "archive": ("старый форум архив", "архив темы трейдеров", "веб-архив форума",
                    "зеркало форума"),
        "physical_economy": ("экспорт нефти Urals", "трубопровод поставки", "зерновой экспорт",
                             "металлургия экспорт", "налоговый период экспортёры",
                             "продажа валютной выручки"),
        "source_graph": ("подборка стратегий", "список брокеров", "обзор роботов",
                         "рейтинг советников", "каталог ресурсов"),
    },
}
NATIVE_TERMS.update({
    "pt": {
        "official": ("Banco Central do Brasil ata", "Copom decisão", "Tesouro Nacional leilão",
                     "B3 posições em aberto", "CVM ofício", "IBGE indicadores",
                     "balança comercial mensal"),
        "institutional": ("relatório de análise câmbio", "casa de análise",
                          "XP Investimentos research", "BTG Pactual relatório",
                          "Itaú BBA macro", "carta ao cotista fundo"),
        "academic": ("dissertação mercado financeiro", "tese volatilidade",
                     "análise empírica câmbio", "artigo acadêmico FGV"),
        "practitioner": ("robô de investimento backtest", "setup day trade",
                         "tape reading dólar", "análise quantitativa B3",
                         "MetaTrader estratégia", "Profit Chart automação",
                         "estratégia automatizada mini índice"),
        "retail_ecology": ("fórum de traders", "pessoa física mercado", "mão forte tape",
                           "alavancagem estouro", "comunidade de traders telegram",
                           "relato prejuízo day trade"),
        "app_ecosystem": ("Nelogica robô", "Profit indicador", "loja de robôs B3",
                          "sinais MetaTrader", "copytrading brasil"),
        "media": ("Valor Econômico câmbio", "InfoMoney mercado", "Exame investimentos",
                  "Money Times análise", "Suno research"),
        "archive": ("fórum antigo arquivo", "tópicos antigos traders"),
        "physical_economy": ("exportação de soja safra", "minério de ferro embarque",
                             "frete porto de Santos", "balança comercial commodities"),
        "source_graph": ("lista de estratégias", "compilado de estudos", "ranking de robôs"),
    },
    "es": {
        "official": ("Banco Central comunicado", "Banxico decisión de política",
                     "BCRA circular", "banco central de Chile informe",
                     "balanza comercial mensual", "intervención cambiaria"),
        "institutional": ("informe de análisis divisas", "casa de bolsa reporte",
                          "perspectiva cambiaria", "research renta fija"),
        "academic": ("tesis mercados financieros", "análisis empírico volatilidad",
                     "artículo académico arbitraje"),
        "practitioner": ("trading algorítmico backtest", "robot de trading resultados",
                         "sistema de trading reglas", "estrategia cuantitativa",
                         "MetaTrader estrategia probada"),
        "retail_ecology": ("foro de trading", "minoristas apalancamiento",
                           "caza de stops experiencia", "comunidad de traders telegram",
                           "relato pérdida cuenta"),
        "app_ecosystem": ("tienda de robots MT4", "indicadores MetaTrader",
                          "señales de trading", "copytrading broker"),
        "media": ("El Cronista mercados", "Ámbito Financiero dólar",
                  "El Economista divisas", "Expansión mercados", "Infobae economía"),
        "archive": ("foro antiguo archivo", "hilos antiguos trading"),
        "physical_economy": ("exportación de cobre embarque", "soja exportación",
                             "remesas mensuales", "balanza comercial energía"),
        "source_graph": ("recopilación de estrategias", "listado de brokers",
                         "ranking de sistemas"),
    },
    "tr": {
        "official": ("TCMB faiz kararı", "Merkez Bankası rezervler", "Hazine ihale",
                     "BDDK veri", "SPK bülten", "Borsa İstanbul veri", "cari açık verisi"),
        "institutional": ("aracı kurum raporu", "araştırma strateji raporu",
                          "İş Yatırım analiz", "Garanti BBVA Yatırım rapor"),
        "academic": ("tez finansal piyasalar", "ampirik analiz oynaklık",
                     "akademik makale kur"),
        "practitioner": ("algoritmik işlem backtest", "otomatik alım satım robot",
                         "Matriks strateji testi", "MetaTrader stratejisi",
                         "sistem testi sonuçları"),
        "retail_ecology": ("yatırımcı forumu", "ekşi sözlük borsa", "kaldıraç hikaye",
                           "stop avı deneyim", "telegram grubu sinyal",
                           "küçük yatırımcı zarar"),
        "app_ecosystem": ("Matriks indikatör", "İdeal Veri formül", "robot satışı forex",
                          "sinyal aboneliği"),
        "media": ("Bloomberg HT piyasa", "Dünya gazetesi ekonomi", "Ekonomim analiz",
                  "Anadolu Ajansı ekonomi"),
        "archive": ("eski forum arşiv", "eski başlıklar borsa"),
        "physical_economy": ("ihracat verisi", "turizm geliri", "doğal gaz ithalatı",
                             "altın ithalatı veri", "cari denge enerji"),
        "source_graph": ("derleme strateji", "liste aracı kurum", "sıralama robot"),
    },
    "vi": {
        "official": ("Ngân hàng Nhà nước thông tư", "NHNN tỷ giá trung tâm",
                     "Bộ Tài chính thông báo", "HOSE dữ liệu", "HNX thống kê",
                     "dự trữ ngoại hối", "lãi suất điều hành"),
        "institutional": ("báo cáo phân tích", "công ty chứng khoán báo cáo",
                          "SSI research", "VNDirect phân tích", "HSC chiến lược"),
        "academic": ("luận văn thị trường tài chính", "phân tích thực nghiệm biến động",
                     "bài báo khoa học chứng khoán"),
        "practitioner": ("giao dịch thuật toán", "robot giao dịch kết quả",
                         "backtest chiến lược", "hệ thống giao dịch quy tắc",
                         "Amibroker công thức", "MetaTrader chiến lược"),
        "retail_ecology": ("diễn đàn f319", "nhà đầu tư nhỏ lẻ", "đội lái cổ phiếu",
                           "cháy tài khoản kinh nghiệm", "nhóm telegram tín hiệu",
                           "bắt đáy thất bại"),
        "app_ecosystem": ("phần mềm giao dịch bảng giá", "chỉ báo tùy chỉnh",
                          "robot forex việt nam", "tín hiệu giao dịch"),
        "media": ("CafeF thị trường", "VnEconomy vĩ mô", "Vietstock phân tích",
                  "Đầu tư Chứng khoán"),
        "archive": ("diễn đàn cũ lưu trữ", "bài cũ chứng khoán"),
        "physical_economy": ("xuất khẩu gạo", "cà phê xuất khẩu", "dệt may đơn hàng",
                             "kiều hối", "cán cân thương mại"),
        "source_graph": ("tổng hợp chiến lược", "danh sách môi giới", "xếp hạng robot"),
    },
    "id": {
        "official": ("Bank Indonesia siaran pers", "BI rate keputusan", "OJK peraturan",
                     "Kementerian Keuangan lelang", "IDX data", "cadangan devisa",
                     "neraca perdagangan bulanan"),
        "institutional": ("laporan riset sekuritas", "analis rupiah",
                          "Mandiri Sekuritas riset", "riset harian saham"),
        "academic": ("skripsi pasar modal", "tesis volatilitas", "analisis empiris kurs",
                     "jurnal keuangan"),
        "practitioner": ("trading algoritmik backtest", "robot trading hasil",
                         "sistem trading aturan", "Amibroker rumus",
                         "MetaTrader strategi teruji"),
        "retail_ecology": ("forum trader", "Kaskus saham", "bandar saham",
                           "nyangkut pengalaman", "grup telegram sinyal",
                           "ritel rugi cerita"),
        "app_ecosystem": ("aplikasi trading indikator", "robot forex jual",
                          "sinyal trading berlangganan", "EA MT4 indonesia"),
        "media": ("Kontan pasar", "Bisnis Indonesia rupiah", "CNBC Indonesia market",
                  "Katadata ekonomi"),
        "archive": ("forum lama arsip", "thread lama trader"),
        "physical_economy": ("ekspor batu bara", "minyak sawit CPO ekspor",
                             "nikel ekspor", "neraca dagang komoditas"),
        "source_graph": ("kumpulan strategi", "daftar broker", "peringkat robot"),
    },
    "ar": {
        "official": ("البنك المركزي قرار", "مؤسسة النقد بيان", "ساما تقرير",
                     "هيئة السوق المالية", "تداول بيانات", "الاحتياطي الأجنبي",
                     "الميزان التجاري"),
        "institutional": ("تقرير تحليلي عملات", "شركة وساطة أبحاث", "توقعات الدولار",
                          "تقرير استراتيجي"),
        "academic": ("رسالة ماجستير أسواق مالية", "تحليل تجريبي التقلب",
                     "ورقة بحثية مراجحة"),
        "practitioner": ("التداول الآلي اختبار", "روبوت تداول نتائج",
                         "استراتيجية تداول قواعد", "ميتاتريدر إكسبيرت",
                         "مؤشر فني برمجة"),
        "retail_ecology": ("منتدى المتداولين", "هوامير البورصة", "صغار المستثمرين خسائر",
                           "الرافعة المالية تجربة", "مجموعة تيليجرام توصيات"),
        "app_ecosystem": ("متجر الروبوتات ميتاتريدر", "مؤشرات مدفوعة",
                          "نسخ الصفقات", "توصيات مدفوعة"),
        "media": ("العربية اقتصاد", "الاقتصادية تحليل", "مباشر أسواق",
                  "الشرق الأوسط اقتصاد"),
        "archive": ("أرشيف المنتدى", "مواضيع قديمة تداول"),
        "physical_economy": ("صادرات النفط", "أوبك حصص", "الغاز المسال شحنات",
                             "التحويلات المالية", "الميزان التجاري النفطي"),
        "source_graph": ("تجميع استراتيجيات", "قائمة الوسطاء", "تصنيف الروبوتات"),
    },
    "hi": {
        "official": ("भारतीय रिज़र्व बैंक नीति", "आरबीआई रेपो दर", "सेबी परिपत्र",
                     "एनएसई आंकड़े", "बीएसई डेटा", "विदेशी मुद्रा भंडार", "व्यापार घाटा"),
        "institutional": ("रिसर्च रिपोर्ट", "ब्रोकरेज रिपोर्ट", "विश्लेषक राय",
                          "निवेश रणनीति रिपोर्ट"),
        "academic": ("शोध प्रबंध वित्तीय बाजार", "अनुभवजन्य विश्लेषण अस्थिरता",
                     "शोध पत्र मुद्रा"),
        "practitioner": ("एल्गो ट्रेडिंग बैकटेस्ट", "ट्रेडिंग रोबोट नतीजे",
                         "ऑप्शन रणनीति नियम", "ज़ेरोधा स्ट्रीक रणनीति"),
        "retail_ecology": ("ट्रेडर फोरम", "खुदरा निवेशक नुकसान", "लीवरेज अनुभव",
                           "टेलीग्राम ग्रुप कॉल"),
        "app_ecosystem": ("ट्रेडिंग ऐप इंडिकेटर", "सिग्नल सब्सक्रिप्शन",
                          "अपस्टॉक्स एपीआई"),
        "media": ("मनीकंट्रोल बाजार", "इकोनॉमिक टाइम्स मुद्रा",
                  "बिजनेस स्टैंडर्ड विश्लेषण"),
        "archive": ("पुरालेख फोरम", "पुराना फोरम धागे"),
        "physical_economy": ("सोने का आयात आंकड़े", "कच्चा तेल आयात",
                             "निर्यात आंकड़े", "रेमिटेंस डेटा"),
        "source_graph": ("सूची ब्रोकर", "संकलन रणनीति", "रैंकिंग रोबोट"),
    },
    "th": {
        "official": ("ธนาคารแห่งประเทศไทย แถลง", "ธปท อัตราดอกเบี้ยนโยบาย",
                     "ก.ล.ต. ประกาศ", "ตลาดหลักทรัพย์ ข้อมูล",
                     "ทุนสำรองระหว่างประเทศ", "ดุลการค้า"),
        "institutional": ("บทวิเคราะห์ ค่าเงิน", "บริษัทหลักทรัพย์ รายงาน",
                          "นักวิเคราะห์ มุมมอง", "กลยุทธ์การลงทุน รายงาน"),
        "academic": ("วิทยานิพนธ์ ตลาดการเงิน", "การวิเคราะห์เชิงประจักษ์ ความผันผวน",
                     "บทความวิจัย อัตราแลกเปลี่ยน"),
        "practitioner": ("เทรดอัตโนมัติ แบ็คเทสต์", "ระบบเทรด กฎ", "อีเอ ผลทดสอบ",
                         "MetaTrader กลยุทธ์"),
        "retail_ecology": ("พันทิป หุ้น", "เว็บบอร์ดเทรดเดอร์", "รายย่อย ขาดทุน",
                           "เจ้ามือ ลาก", "กลุ่มไลน์ สัญญาณ"),
        "app_ecosystem": ("แอปเทรด อินดิเคเตอร์", "ขายอีเอ", "สัญญาณเทรด สมัคร"),
        "media": ("กรุงเทพธุรกิจ ตลาด", "ประชาชาติธุรกิจ ค่าเงิน",
                  "ฐานเศรษฐกิจ วิเคราะห์"),
        "archive": ("กระทู้เก่า คลัง", "เว็บบอร์ดเก่า สำรอง"),
        "physical_economy": ("ส่งออกข้าว", "ยางพารา ส่งออก", "ท่องเที่ยว รายได้",
                             "ดุลบัญชีเดินสะพัด"),
        "source_graph": ("รวม กลยุทธ์", "รายการ โบรกเกอร์", "จัดอันดับ ระบบเทรด"),
    },
    "de": {
        "official": ("Bundesbank Monatsbericht", "EZB Zinsentscheid", "BaFin Mitteilung",
                     "Deutsche Börse Daten", "Statistisches Bundesamt Handelsbilanz"),
        "institutional": ("Analystenbericht Währungen", "Researchabteilung Ausblick",
                          "Commerzbank Research Devisen", "Marktausblick Gold"),
        "academic": ("Dissertation Finanzmärkte", "empirische Analyse Volatilität",
                     "Fachaufsatz Arbitrage"),
        "practitioner": ("algorithmischer Handel Backtest", "Handelsroboter Ergebnisse",
                         "Expert Advisor Test", "Handelssystem Regeln",
                         "MetaTrader Strategie geprüft"),
        "retail_ecology": ("Traderforum Erfahrungen", "Kleinanleger Verluste",
                           "Zocker Hebel Erfahrung", "Wallstreet Online Forum",
                           "Telegram Gruppe Signale"),
        "app_ecosystem": ("Indikatoren kaufen MetaTrader", "Robotershop Forex",
                          "Tradingview Skript deutsch", "Signaldienst"),
        "media": ("Handelsblatt Märkte", "Börsen-Zeitung Devisen",
                  "Finanzen.net Analyse", "Wirtschaftswoche Rohstoffe"),
        "archive": ("Archiv altes Forum", "alte Threads Trading"),
        "physical_economy": ("Exportüberschuss Daten", "Gasimporte Statistik",
                             "Automobilexport Zahlen", "Auftragseingang Industrie"),
        "source_graph": ("Übersicht Strategien", "Liste Broker", "Sammlung Studien"),
    },
    "fr": {
        "official": ("Banque de France bulletin", "BCE décision de taux", "AMF communiqué",
                     "Euronext données", "INSEE balance commerciale"),
        "institutional": ("note de recherche devises", "analyste perspectives marché",
                          "société de gestion étude"),
        "academic": ("thèse marchés financiers", "analyse empirique volatilité",
                     "article de recherche arbitrage"),
        "practitioner": ("trading algorithmique backtest", "robot de trading résultats",
                         "système de trading règles", "ProRealTime code stratégie",
                         "MetaTrader stratégie testée"),
        "retail_ecology": ("forum de traders", "particuliers pertes",
                           "effet de levier témoignage", "chasse aux stops",
                           "groupe telegram signaux"),
        "app_ecosystem": ("ProRealTime indicateurs", "boutique de robots",
                          "signaux de trading abonnement"),
        "media": ("Les Échos marchés", "La Tribune devises", "BFM Business bourse",
                  "Boursorama analyse"),
        "archive": ("archives ancien forum", "anciens sujets trading"),
        "physical_economy": ("exportations agricoles", "aéronautique commandes",
                             "énergie nucléaire production", "balance commerciale"),
        "source_graph": ("liste de courtiers", "compilation de stratégies",
                         "classement robots"),
    },
    "it": {
        "official": ("Banca d'Italia bollettino", "BCE decisione tassi", "Consob comunicato",
                     "Borsa Italiana dati", "ISTAT bilancia commerciale"),
        "institutional": ("report di analisi valute", "ufficio studi previsioni",
                          "Intesa Sanpaolo research"),
        "academic": ("tesi mercati finanziari", "analisi empirica volatilità",
                     "articolo scientifico arbitraggio"),
        "practitioner": ("trading algoritmico backtest", "robot di trading risultati",
                         "sistema di trading regole", "MetaTrader strategia testata",
                         "MultiCharts strategia"),
        "retail_ecology": ("forum trader", "FinanzaOnline discussione",
                           "piccoli risparmiatori perdite", "leva esperienza",
                           "gruppo telegram segnali"),
        "app_ecosystem": ("indicatori a pagamento", "negozio di robot",
                          "Tradingview script italiano"),
        "media": ("Il Sole 24 Ore mercati", "MilanoFinanza valute",
                  "Corriere Economia analisi"),
        "archive": ("archivio vecchio forum", "vecchi thread trading"),
        "physical_economy": ("export manifatturiero dati", "energia importazioni",
                             "meccanica ordini", "bilancia commerciale"),
        "source_graph": ("elenco broker", "raccolta strategie", "classifica robot"),
    },
    "pl": {
        "official": ("Narodowy Bank Polski komunikat", "NBP stopa referencyjna",
                     "KNF komunikat", "GPW dane", "GUS bilans handlowy"),
        "institutional": ("raport analityczny waluty", "dom maklerski rekomendacja",
                          "analityk prognoza złoty"),
        "academic": ("praca magisterska rynki finansowe", "analiza empiryczna zmienność",
                     "artykuł naukowy arbitraż"),
        "practitioner": ("handel algorytmiczny backtest", "robot handlowy wyniki",
                         "system transakcyjny zasady", "MetaTrader strategia test"),
        "retail_ecology": ("forum traderów", "Bankier forum dyskusja",
                           "inwestorzy indywidualni straty", "dźwignia doświadczenie",
                           "grupa telegram sygnały"),
        "app_ecosystem": ("wskaźniki płatne MetaTrader", "sklep z robotami",
                          "sygnały abonament"),
        "media": ("Parkiet rynki", "Puls Biznesu waluty", "Bankier analiza",
                  "Business Insider Polska giełda"),
        "archive": ("archiwum stare forum", "stare wątki trading"),
        "physical_economy": ("eksport dane", "przemysł produkcja", "węgiel import",
                             "bilans handlowy"),
        "source_graph": ("lista brokerów", "zestawienie strategii", "ranking robotów"),
    },
    "en": {
        "official": ("Federal Reserve statement", "ECB monetary policy decision",
                     "CFTC commitments of traders", "LBMA price", "CME open interest",
                     "BIS quarterly review", "trade balance release"),
        "institutional": ("sell-side FX strategy note", "research desk outlook",
                          "prime broker positioning survey", "buy-side letter"),
        "academic": ("SSRN working paper anomaly", "arXiv q-fin empirical",
                     "journal of finance replication", "thesis volatility"),
        "practitioner": ("quant blog backtest", "systematic strategy rules",
                         "expert advisor forward test", "GitHub trading strategy",
                         "walk forward analysis"),
        "retail_ecology": ("forexfactory thread", "reddit algotrading",
                           "retail blown account", "prop firm challenge experience",
                           "telegram signal group review"),
        "app_ecosystem": ("MQL5 market expert advisor", "TradingView indicator script",
                          "signal subscription myfxbook", "copy trading leaderboard"),
        "media": ("Reuters FX report", "Bloomberg commodities", "FT markets",
                  "Kitco gold analysis"),
        "archive": ("wayback forum thread", "archived trading board"),
        "physical_economy": ("warehouse stocks LME", "tanker tracking crude",
                             "customs import data", "physical premium gold"),
        "source_graph": ("awesome quant list", "curated research index",
                         "broker comparison table"),
    },
})

#: THE NAME AN INSTRUMENT IS SEARCHED BY, per language, for the few instruments a query is
#: usually ABOUT. `mechanism_claims.INSTRUMENT_ALIASES` is the fallback and it is a RECOGNITION
#: table, ordered for matching rather than for searching: its gold tuple leads with 黄金, which
#: is correct Chinese and wrong Japanese, and its Russian entry is the stem "золот" rather than
#: a word anybody types. Recognition wants a stem; a query wants the word. An instrument/language
#: pair absent from both yields "" -- the query is then built from layer and probe terms alone,
#: never from an English word standing in for a native one.
NATIVE_INSTRUMENT: dict[str, dict[str, str]] = {
    "ja": {"XAUUSD": "金 相場", "XAGUSD": "銀 相場", "XTIUSD": "原油 価格",
           "XBRUSD": "ブレント 原油", "USDJPY": "ドル円", "EURUSD": "ユーロドル",
           "GBPUSD": "ポンドドル", "JPN225": "日経225"},
    "ko": {"XAUUSD": "금값", "XAGUSD": "은값", "XTIUSD": "유가", "XBRUSD": "브렌트유",
           "USDKRW": "원달러", "USDJPY": "엔달러", "EURUSD": "유로달러"},
    "zh": {"XAUUSD": "黄金", "XAGUSD": "白银", "XTIUSD": "原油", "XBRUSD": "布伦特原油",
           "USDCNH": "人民币 汇率", "USDJPY": "美日", "EURUSD": "欧美"},
    "zh-Hant": {"XAUUSD": "黃金", "XAGUSD": "白銀", "XTIUSD": "原油", "USDJPY": "美日"},
    "ru": {"XAUUSD": "золото", "XAGUSD": "серебро", "XTIUSD": "нефть WTI",
           "XBRUSD": "нефть Brent", "USDRUB": "курс доллара", "EURUSD": "евродоллар"},
    "ar": {"XAUUSD": "الذهب", "XAGUSD": "الفضة", "XTIUSD": "النفط الخام",
           "XBRUSD": "خام برنت"},
    "hi": {"XAUUSD": "सोना", "XAGUSD": "चांदी", "XTIUSD": "कच्चा तेल"},
    "th": {"XAUUSD": "ทองคำ", "XAGUSD": "โลหะเงิน", "XTIUSD": "น้ำมันดิบ"},
    "de": {"XAUUSD": "Gold", "XAGUSD": "Silber", "XTIUSD": "Rohöl", "EURUSD": "Euro Dollar",
           "USDJPY": "Dollar Yen"},
    "fr": {"XAUUSD": "or", "XAGUSD": "argent", "XTIUSD": "pétrole", "EURUSD": "euro dollar"},
    "es": {"XAUUSD": "oro", "XAGUSD": "plata", "XTIUSD": "petróleo", "EURUSD": "euro dólar"},
    "pt": {"XAUUSD": "ouro", "XAGUSD": "prata", "XTIUSD": "petróleo", "EURUSD": "euro dólar"},
    "it": {"XAUUSD": "oro", "XAGUSD": "argento", "XTIUSD": "petrolio"},
    "pl": {"XAUUSD": "złoto", "XAGUSD": "srebro", "XTIUSD": "ropa"},
    "tr": {"XAUUSD": "altın", "XAGUSD": "gümüş", "XTIUSD": "petrol", "USDTRY": "dolar kuru"},
    "vi": {"XAUUSD": "vàng", "XAGUSD": "bạc", "XTIUSD": "dầu thô"},
    "id": {"XAUUSD": "emas", "XAGUSD": "perak", "XTIUSD": "minyak mentah"},
    "en": {"XAUUSD": "gold", "XAGUSD": "silver", "XTIUSD": "WTI crude", "EURUSD": "EURUSD"},
}

#: Language -> its script. The script-determined half is inverted out of `SCRIPT_LANG`; the Han
#: family is stated because three languages share it.
SCRIPT_OF_LANG: dict[str, str] = {lang: script for script, lang in SCRIPT_LANG.items()}
SCRIPT_OF_LANG.update({"ja": "Han", "zh": "Han", "zh-Hans": "Han", "zh-Hant": "Han"})


def _terms_key(lang: str) -> str:
    """A language code as `NATIVE_TERMS` spells it, or "" when there is no table."""
    code = (lang or "").strip()
    if code in NATIVE_TERMS:
        return code
    if code == "zh-Hans":
        return "zh"
    base = code.split("-")[0]
    return base if base in NATIVE_TERMS else ""


def native_instrument(symbol: str, lang: str) -> str:
    """An instrument's name IN THIS LANGUAGE, or "" when the desk has not measured one.

    For a non-Latin language the answer comes free out of `mechanism_claims.INSTRUMENT_ALIASES`:
    find the alias tuple that yields this symbol and take the first alias written in the
    language's own script. "" is a verdict -- the caller then builds a query without an
    instrument rather than dropping an English word into a native search.
    """
    code = (lang or "").strip()
    table = NATIVE_INSTRUMENT.get(code) or NATIVE_INSTRUMENT.get(code.split("-")[0]) or {}
    if symbol.upper() in table:
        return table[symbol.upper()]
    want = SCRIPT_OF_LANG.get(code) or (PROFILES[code].script if code in PROFILES else "")
    if not want or want == "Latin":
        return ""
    for aliases, candidates, _cls in mc.INSTRUMENT_ALIASES:
        if symbol.upper() not in {c.upper() for c in candidates}:
            continue
        for alias in aliases:
            got = script_of(alias)
            if got == want or (want == "Han" and got in ("Hiragana", "Katakana", "Han")):
                return alias
    return ""


def native_queries(lang: str, layer: str = "", *, instrument: str = "",
                   limit: int = 24) -> list[str]:
    """Native-script search queries for one language and one source layer.

    BUILT FROM LOCAL TERMINOLOGY, NEVER FROM A TRANSLATED ENGLISH PHRASE. Each query pairs a
    term the community itself uses -- an institution's own name, a board's own slang, a
    platform's own product name -- with a native PROBE term saying what is wanted, and
    optionally with the instrument's name in that language.

    A language with no table returns `[]`, which `query_coverage` reports as UNMEASURED. That is
    the deliberate half: a plausible-looking translated phrase would convert a known gap into a
    silent wrong answer, and the desk would never learn which forests it cannot search.
    """
    code = _terms_key(lang)
    if not code:
        return []
    table = NATIVE_TERMS[code]
    layers = [layer] if layer else [x for x in SOURCE_LAYERS if x in table]
    probes = PROBE_TERMS.get(code) or PROBE_TERMS.get(code.split("-")[0]) or ()
    symbol = native_instrument(instrument, code) if instrument else ""
    out: list[str] = []
    for name in layers:
        for i, term in enumerate(table.get(name, ())):
            probe = probes[i % len(probes)] if probes else ""
            parts = [term, symbol, probe] if symbol else [term, probe]
            query = " ".join(p for p in parts if p).strip()
            if query and query not in out:
                out.append(query)
            if len(out) >= limit:
                return out
    # THE SLANG IS A QUERY TOO, and it reaches a different half of the forest: a board's own word
    # for a mechanism finds the thread where it is argued about, while the institutional word for
    # the same thing finds the press release. Both are wanted; only one of them is searchable
    # from a translated phrase.
    if (not layer or layer == "retail_ecology") and code in SLANG:
        for term in sorted(SLANG[code], key=lambda t: (-len(t), t))[:6]:
            query = f"{term} {probes[0]}" if probes else term
            if query not in out:
                out.append(query)
            if len(out) >= limit:
                break
    for term in table.get("_extra", ()):
        if len(out) >= limit:
            break
        query = f"{term} {probes[0]}" if probes else term
        if query not in out:
            out.append(query)
    return out[:limit]


def query_coverage() -> dict[str, dict[str, Any]]:
    """Per language, per layer: how many native terms are declared, or UNMEASURED.

    THIS IS A GAP LIST, not a score. Every UNMEASURED cell is one forest layer the desk cannot
    currently search in its own words, and naming it is what lets a source scout fill it --
    whereas filling it here with a translated phrase would hide it forever (L1.28a).
    """
    out: dict[str, dict[str, Any]] = {}
    for code, table in NATIVE_TERMS.items():
        row: dict[str, Any] = {}
        for name in SOURCE_LAYERS:
            terms = table.get(name)
            row[name] = len(terms) if terms else "UNMEASURED"
        row["_extra_terms"] = len(table.get("_extra", ()))
        row["_total"] = sum(v for v in row.values() if isinstance(v, int))
        out[code] = row
    return out


def layers_unmeasured(lang: str) -> list[str]:
    """The source layers this language has no native vocabulary for. Empty means all ten."""
    code = _terms_key(lang)
    if not code:
        return list(SOURCE_LAYERS)
    table = NATIVE_TERMS[code]
    return [name for name in SOURCE_LAYERS if not table.get(name)]


def query_languages() -> tuple[str, ...]:
    """The languages a native query can be generated in at all."""
    return tuple(sorted(NATIVE_TERMS))


#: Declared so a reader can count what this module covers without reading every table.
COVERAGE: dict[str, Any] = {
    "scripts": len(SCRIPTS),
    "script_determined_languages": len(set(SCRIPT_LANG.values())),
    "profiled_languages": len(PROFILES),
    "languages": len(LANGUAGES),
    "slang_languages": len(SLANG),
    "slang_terms": sum(len(v) for v in SLANG.values()),
    "concepts": len(CONCEPTS),
    "transliterated_languages": len(TRANSLITERATIONS),
    "terminology_languages": len(TERMINOLOGY_LANGS),
    "source_layers": len(SOURCE_LAYERS),
    "query_languages": len(NATIVE_TERMS),
    "native_query_terms": sum(len(t) for table in NATIVE_TERMS.values()
                              for t in table.values()),
    "query_layers_measured": sum(1 for table in NATIVE_TERMS.values()
                                 for name in SOURCE_LAYERS if table.get(name)),
    "query_layers_unmeasured": sum(1 for table in NATIVE_TERMS.values()
                                   for name in SOURCE_LAYERS if not table.get(name)),
    "rule": RULE,
}


```

### libs\research\representations.py
```python
"""THE REPRESENTATION LIBRARY -- what a raw series can BECOME, as pure typed transforms.

THE PRINCIPAL, 2026-09-17: *representation invention mints new features from ingested series and
tracks their ROI*. A dataset is never one feature. A monthly print is a level, a surprise against
what was expected, a pace against the period elapsed, a z against its own prior dispersion, a
revision between two vintages, and -- crossed with a second dataset -- a ratio or a product that
neither series carries alone. The desk had ingestion and it had families; it had no vocabulary
for the step between them, so every ingested series reached the docket as at most its own level.

WHAT THIS MODULE IS. Pure functions over PIT-stamped points, and nothing else: no I/O, no clock,
no registry, no randomness. `desks/mt5/research/representation_forge.py` is the organ that reads
the desk's series, applies these, stores them and scores their ROI. Keeping the transforms here
means they are testable without a desk, type-checked under `strict`, and callable from the world
model, the forge and any later organ on identical terms.

THE ONE INVARIANT, AND EVERY TRANSFORM IS WRITTEN TO IT: a representation's value stamped
`available_time = t` is computed from input points whose own `available_time <= t`. Never a
trailing window centred on t, never a mean over the whole sample, never a z-score against a
dispersion that includes the future. Expanding statistics are computed on the STRICT prefix, so
the point being transformed never helps decide its own normalisation. That is not a style
preference: a z-score against full-sample dispersion is the single most common way a leak enters
a conditioning variable, and the return series stays spotless while it happens (R0316's class).

THE GRAMMAR. `compose(outer, inner)` makes one transform out of two, which is where invention
actually happens -- `zscore(surprise(x))` is a different claim from either half, and the space of
compositions is far larger than the space of hand-written features. It is budgeted rather than
enumerated: `rank_proposals` orders by novelty (distance to the representation ids that already
exist) times expected value (how often the transform family has produced candidates before), so
the forge spends its hour on the corner of the grammar that has paid and is still unexplored.

IDS ARE THE MEMORY. `repr:<dataset>:<transform>:<params>` is stable across passes, so the same
representation proposed twice is one representation with a second use, and a composition is
`repr:<dataset>:<inner>|<outer>:<params>`. An id nobody can reconstruct is a feature nobody can
credit, and ROI accounting is exactly the act of crediting a feature months later.
"""
from __future__ import annotations

import hashlib
import json
import math
from bisect import bisect_left, bisect_right, insort
from collections import deque
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from typing import Any, Final

__all__ = [
    "FAMILIES",
    "TRANSFORMS",
    "Point",
    "Series",
    "Transform",
    "TransformSpec",
    "apply",
    "as_of",
    "compose",
    "expected_value",
    "novelty",
    "parse_time",
    "rank_proposals",
    "representation_id",
]

#: Points with fewer than this many strict predecessors cannot carry an expanding statistic.
#: Not a tuning knob: below it the "prior dispersion" is one or two numbers and the z-score is
#: noise wearing a statistic's clothes.
MIN_PRIOR: Final[int] = 8
#: Parameter renderings longer than this collapse to a hash, so an id stays a filename.
MAX_PARAM_CHARS: Final[int] = 48
EPS: Final[float] = 1e-12


# ------------------------------------------------------------------------------- the PIT point
@dataclass(frozen=True)
class Point:
    """One observation, carrying BOTH clocks (L1.46).

    `period_time` is what the value describes -- the source's clock. `available_time` is the
    first instant this desk could have read it -- ours. Every transform reads the second and
    every join uses the second; the first exists so a seasonal or pace transform can ask which
    month a number is ABOUT without asking when it arrived.
    """

    available_time: str
    period_time: str
    value: float
    vintage_id: str | None = None

    def with_value(self, value: float) -> Point:
        return replace(self, value=float(value))


@dataclass(frozen=True)
class Series:
    """A PIT series plus the labels the world model attributes explained variance BY.

    `dataset`, `region` and `information_type` are DECLARED by whoever built the series and
    carried through every transform unchanged. A derived feature belongs to the dataset it came
    from -- that is what makes "which dataset explained this residual" answerable at all.
    """

    series_id: str
    points: tuple[Point, ...] = ()
    dataset: str = ""
    region: str = ""
    information_type: str = ""

    def __len__(self) -> int:
        return len(self.points)

    @property
    def values(self) -> tuple[float, ...]:
        return tuple(p.value for p in self.points)

    def sorted(self) -> Series:
        """Points in the order the desk could have learned them; ties keep input order."""
        ordered = sorted(self.points, key=lambda p: (p.available_time, p.period_time))
        return replace(self, points=tuple(ordered))

    def relabel(self, series_id: str) -> Series:
        return replace(self, series_id=series_id)


def parse_time(value: str | None) -> datetime | None:
    """A tolerant ISO reader: full stamps, dates, and the `1999-01` month the BIS axis writes.

    Returns None rather than guessing. A stamp nobody can parse is an UNSTAMPED observation and
    the caller must treat it as unusable, not as the epoch.
    """
    raw = str(value or "").strip()
    if not raw:
        return None
    text = raw.replace("Z", "+00:00")
    for attempt in (text, text[:19], text[:10]):
        try:
            parsed = datetime.fromisoformat(attempt)
        except ValueError:
            continue
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)
    if len(raw) == 7 and raw[4] == "-":
        try:
            return datetime(int(raw[:4]), int(raw[5:7]), 1, tzinfo=UTC)
        except ValueError:
            return None
    return None


def _finite(value: float) -> bool:
    return isinstance(value, (int, float)) and math.isfinite(float(value))


def _mean(values: Sequence[float]) -> float:
    return sum(values) / len(values) if values else float("nan")


def _sd(values: Sequence[float]) -> float:
    if len(values) < 2:
        return float("nan")
    mu = _mean(values)
    var = sum((v - mu) ** 2 for v in values) / (len(values) - 1)
    return math.sqrt(var) if var > 0 else 0.0


def as_of(series: Series, when: str) -> float | None:
    """The newest value of `series` KNOWABLE at `when` -- the join every consumer makes.

    A later vintage of the same period does not exist yet at `when` and is not returned; this is
    the whole of the anti-lookahead contract in one function, and the world model routes every
    external input through it.
    """
    best: tuple[str, float] | None = None
    for point in series.points:
        if point.available_time > when:
            continue
        if best is None or point.available_time >= best[0]:
            best = (point.available_time, point.value)
    return None if best is None else best[1]


# ------------------------------------------------------------------------------- ids and keys
def _render_params(params: Mapping[str, Any]) -> str:
    if not params:
        return "default"
    parts = [f"{k}={params[k]}" for k in sorted(params)]
    text = ",".join(parts)
    if len(text) <= MAX_PARAM_CHARS:
        return text
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]
    return f"h{digest}"


def representation_id(dataset: str, transform: str, params: Mapping[str, Any]) -> str:
    """`repr:<dataset>:<transform>:<params>` -- stable across passes and safe as a filename."""
    safe_dataset = "".join(c if c.isalnum() or c in "-_.@" else "_" for c in (dataset or "any"))
    return f"repr:{safe_dataset}:{transform}:{_render_params(params)}"


def _seasonal_key(point: Point, cycle: str) -> str:
    stamp = parse_time(point.period_time) or parse_time(point.available_time)
    if stamp is None:
        return "unknown"
    if cycle == "month":
        return f"m{stamp.month:02d}"
    if cycle == "weekday":
        return f"d{stamp.weekday()}"
    if cycle == "hour":
        return f"h{stamp.hour:02d}"
    if cycle == "monthday":
        return f"md{stamp.day:02d}"
    if cycle == "quarter":
        return f"q{(stamp.month - 1) // 3 + 1}"
    return "all"


# ------------------------------------------------------------------------------- the transforms
def diff(series: Series, *, lag: int = 1) -> Series:
    """Change over `lag` observations. The first `lag` points have no predecessor and are gone."""
    points = series.sorted().points
    out = [points[i].with_value(points[i].value - points[i - lag].value)
           for i in range(lag, len(points))
           if _finite(points[i].value) and _finite(points[i - lag].value)]
    return replace(series, points=tuple(out),
                   series_id=representation_id(series.dataset, "diff", {"lag": lag}))


def acceleration(series: Series, *, lag: int = 1) -> Series:
    """The second difference: whether the change itself is speeding up."""
    inner = diff(series, lag=lag)
    out = diff(inner, lag=lag)
    return replace(out, series_id=representation_id(series.dataset, "acceleration", {"lag": lag}))


def zscore(series: Series, *, window: int = 0, min_prior: int = MIN_PRIOR) -> Series:
    """(value - prior mean) / prior sd, against the STRICT prefix only.

    `window = 0` is expanding; a positive window is the trailing window ending one observation
    before the point. Either way the point never enters its own normalisation, which is the
    difference between a z-score and a leak.

    STREAMED, NOT SLICED. The obvious implementation takes `points[:i]` and averages it, which is
    O(n^2): on the desk's real axes (14,000 points per symbol on the BIS series) that is 196
    million steps for one transform and the organ never finishes its hour. Running sums give the
    identical numbers in one pass, and the accumulator is updated AFTER the point is emitted, so
    the causality is exactly as before.
    """
    points = series.sorted().points
    out: list[Point] = []
    values: list[float] = []
    total = total_sq = 0.0
    for point in points:
        count = len(values)
        lo = max(0, count - window) if window > 0 else 0
        n = count - lo
        if window > 0 and lo > 0:
            run = sum(values[lo:count])
            run_sq = sum(v * v for v in values[lo:count])
        else:
            run, run_sq = total, total_sq
        if n >= min_prior and _finite(point.value):
            mean = run / n
            var = (run_sq - n * mean * mean) / (n - 1) if n > 1 else 0.0
            sd = math.sqrt(var) if var > 0 else 0.0
            if sd > EPS:
                out.append(point.with_value((point.value - mean) / sd))
        if _finite(point.value):
            values.append(point.value)
            total += point.value
            total_sq += point.value * point.value
    return replace(series, points=tuple(out),
                   series_id=representation_id(series.dataset, "zscore",
                                               {"window": window, "min_prior": min_prior}))


def rank_percentile(series: Series, *, window: int = 0, min_prior: int = MIN_PRIOR) -> Series:
    """Where the value sits in its own prior distribution, in [0, 1]. Robust to a fat tail.

    A sorted insert per point (`bisect`) rather than a scan of the whole prefix: the same numbers
    in n log n, for the reason `zscore` records.
    """
    points = series.sorted().points
    out: list[Point] = []
    values: list[float] = []
    order: list[float] = []
    for point in points:
        prior = values[-window:] if window > 0 else values
        if len(prior) >= min_prior and _finite(point.value):
            if window > 0:
                below = sum(1 for v in prior if v < point.value)
                ties = sum(1 for v in prior if v == point.value)
            else:
                left = bisect_left(order, point.value)
                right = bisect_right(order, point.value)
                below, ties = left, right - left
            out.append(point.with_value((below + 0.5 * ties) / len(prior)))
        if _finite(point.value):
            values.append(point.value)
            if window <= 0:
                insort(order, point.value)
    return replace(series, points=tuple(out),
                   series_id=representation_id(series.dataset, "rank_percentile",
                                               {"window": window, "min_prior": min_prior}))


def surprise(series: Series, *, control: str = "weekday", min_prior: int = 3) -> Series:
    """Actual minus expectation, where the expectation is MATCHED on a control key.

    The control is the point of it. A raw month-on-month change confounds the calendar with the
    news; the mean of prior observations sharing the same weekday (or month, or hour) removes the
    part of the number that was a property of the date rather than of the world. Matched strictly
    on the prefix -- one running sum per control key, so the expectation for point i is built from
    points before i only.
    """
    points = series.sorted().points
    history: dict[str, tuple[float, int]] = {}
    out: list[Point] = []
    for point in points:
        key = _seasonal_key(point, control)
        total, count = history.get(key, (0.0, 0))
        if _finite(point.value) and count >= min_prior:
            out.append(point.with_value(point.value - total / count))
        if _finite(point.value):
            history[key] = (total + point.value, count + 1)
    return replace(series, points=tuple(out),
                   series_id=representation_id(series.dataset, "surprise",
                                               {"control": control, "min_prior": min_prior}))


def seasonal_expectation(series: Series, *, cycle: str = "month", min_prior: int = 3) -> Series:
    """What the calendar alone predicts: the prior mean of the matching seasonal cell.

    The expectation itself is a representation, not only a subtrahend -- a carry family wants the
    level the season implies, while a surprise family wants what it failed to imply.
    """
    points = series.sorted().points
    history: dict[str, tuple[float, int]] = {}
    out: list[Point] = []
    for point in points:
        key = _seasonal_key(point, cycle)
        total, count = history.get(key, (0.0, 0))
        if count >= min_prior:
            out.append(point.with_value(total / count))
        if _finite(point.value):
            history[key] = (total + point.value, count + 1)
    return replace(series, points=tuple(out),
                   series_id=representation_id(series.dataset, "seasonal_expectation",
                                               {"cycle": cycle, "min_prior": min_prior}))


def pace(series: Series, *, cycle: str = "month") -> Series:
    """Value per unit of the period ELAPSED -- a run-rate, not a level.

    A cumulative print three days into a month and the same number three weeks in are opposite
    news, and the level cannot tell them apart. The elapsed fraction comes from the point's own
    period stamp, so nothing about the future enters.
    """
    points = series.sorted().points
    out: list[Point] = []
    for point in points:
        stamp = parse_time(point.period_time) or parse_time(point.available_time)
        if stamp is None or not _finite(point.value):
            continue
        if cycle == "month":
            fraction = stamp.day / 31.0
        elif cycle == "year":
            fraction = stamp.timetuple().tm_yday / 366.0
        elif cycle == "quarter":
            fraction = (((stamp.month - 1) % 3) * 31 + stamp.day) / 93.0
        else:
            fraction = 1.0
        out.append(point.with_value(point.value / max(fraction, 1.0 / 366.0)))
    return replace(series, points=tuple(out),
                   series_id=representation_id(series.dataset, "pace", {"cycle": cycle}))


def lead_lag(series: Series, *, lag: int = 1) -> Series:
    """The value from `lag` observations ago, stamped NOW.

    A LAG only. A lead would stamp a future value at the present instant, which is the leak this
    library exists to make impossible, so a negative lag is refused rather than quietly flipped.
    """
    if lag < 0:
        raise ValueError("lead_lag takes a non-negative lag: a lead is a look-ahead")
    points = series.sorted().points
    out = [replace(points[i], value=points[i - lag].value)
           for i in range(lag, len(points)) if _finite(points[i - lag].value)]
    return replace(series, points=tuple(out),
                   series_id=representation_id(series.dataset, "lead_lag", {"lag": lag}))


def rolling_volatility(series: Series, *, window: int = 20) -> Series:
    """The sd of prior changes: the state every vol-conditioned family asks about.

    A rolling accumulator over the trailing `window` changes, so the cost is O(n) rather than the
    O(n*window) of rebuilding the window at every point.
    """
    points = series.sorted().points
    out: list[Point] = []
    changes: deque[float] = deque(maxlen=max(2, window))
    total = total_sq = 0.0
    previous: float | None = None
    floor = max(2, MIN_PRIOR // 2)
    for point in points:
        n = len(changes)
        if n >= floor:
            mean = total / n
            var = (total_sq - n * mean * mean) / (n - 1)
            if var >= 0:
                out.append(point.with_value(math.sqrt(var)))
        if _finite(point.value):
            if previous is not None:
                change = point.value - previous
                if len(changes) == changes.maxlen:
                    dropped = changes[0]
                    total -= dropped
                    total_sq -= dropped * dropped
                changes.append(change)
                total += change
                total_sq += change * change
            previous = point.value
    return replace(series, points=tuple(out),
                   series_id=representation_id(series.dataset, "rolling_volatility",
                                               {"window": window}))


def spectral_state(series: Series, *, window: int = 32) -> Series:
    """How much of the trailing variance is HIGH-frequency: var(differences) / var(levels).

    The cheap spectral statistic, and deliberately the cheap one. A full periodogram over every
    axis every hour is not affordable on this box, and the quantity a regime actually turns on is
    whether the series is currently choppy or smooth -- which this ratio measures with running
    sums and no transform. Near zero the series is trending; large, it is oscillating.
    """
    points = series.sorted().points
    out: list[Point] = []
    levels: deque[float] = deque(maxlen=max(4, window))
    floor = max(4, MIN_PRIOR // 2)
    for point in points:
        n = len(levels)
        if n >= floor:
            prior = list(levels)
            var_levels = _sd(prior) ** 2
            changes = [prior[j] - prior[j - 1] for j in range(1, n)]
            var_changes = _sd(changes) ** 2 if len(changes) >= 2 else float("nan")
            if _finite(var_levels) and _finite(var_changes) and var_levels > EPS:
                out.append(point.with_value(var_changes / var_levels))
        if _finite(point.value):
            levels.append(point.value)
    return replace(series, points=tuple(out),
                   series_id=representation_id(series.dataset, "spectral_state",
                                               {"window": window}))


def vintage_revision(series: Series) -> Series:
    """Final minus flash, per period, stamped at the instant the REVISION became knowable.

    A revision is news about the world and news about the statistician, and it is the one
    representation only a desk that stored its vintages can build at all. A period seen once has
    no revision and produces nothing -- absence, not a zero.
    """
    points = series.sorted().points
    first: dict[str, float] = {}
    out: list[Point] = []
    for point in points:
        if not _finite(point.value):
            continue
        period = point.period_time
        if period in first:
            out.append(point.with_value(point.value - first[period]))
        else:
            first[period] = point.value
    return replace(series, points=tuple(out),
                   series_id=representation_id(series.dataset, "vintage_revision", {}))


#: Points between refits of the regime bucket cuts. Refitting at every point re-sorts the whole
#: prefix -- O(n^2 log n) -- and the cuts move by nothing between neighbours; the block is still
#: labelled by the cut fitted on everything BEFORE the block began, so causality is unchanged.
REGIME_RECUT = 64


def regime_conditioned(series: Series, regime: Series, *, buckets: int = 3,
                       min_prior: int = MIN_PRIOR) -> Series:
    """The value minus what it usually is IN THE STATE the desk is currently in.

    The regime series is joined point-in-time by a merge scan, bucketed against its own prior
    quantiles, and the subtrahend is the prior mean of the SAME bucket. A value that is ordinary
    for a high-vol world and extraordinary for a calm one reads as extraordinary only in the calm
    one, which is the whole claim of a state-dependent feature.
    """
    points = series.sorted().points
    other = regime.sorted().points
    history: dict[int, tuple[float, int]] = {}
    regime_prior: list[float] = []
    cuts: list[float] = []
    since_recut = 0
    pointer = 0
    state: float | None = None
    out: list[Point] = []
    for point in points:
        while pointer < len(other) and other[pointer].available_time <= point.available_time:
            if _finite(other[pointer].value):
                state = other[pointer].value
            pointer += 1
        if state is None or not _finite(point.value):
            continue
        if len(regime_prior) >= min_prior:
            if not cuts or since_recut >= REGIME_RECUT:
                ordered = sorted(regime_prior)
                cuts = [ordered[int(len(ordered) * k / buckets)] for k in range(1, buckets)]
                since_recut = 0
            since_recut += 1
            bucket = sum(1 for c in cuts if state >= c)
            total, count = history.get(bucket, (0.0, 0))
            if count >= min_prior:
                out.append(point.with_value(point.value - total / count))
            history[bucket] = (total + point.value, count + 1)
        regime_prior.append(state)
    return replace(series, points=tuple(out),
                   series_id=representation_id(series.dataset, "regime_conditioned",
                                               {"buckets": buckets, "on": regime.dataset or "x"}))


def _pairwise(left: Series, right: Series, op: Callable[[float, float], float | None],
              name: str) -> Series:
    """A MERGE SCAN, not a lookup per point. `as_of` walks the whole right-hand series for every
    left-hand point, so the pair cost was O(n*m) -- on two 14,000-point axes, 196 million steps
    for one interaction. Both series are already sorted by availability; one pointer is enough,
    and the join it produces is identical."""
    lhs = left.sorted()
    rhs = right.sorted()
    out: list[Point] = []
    pointer = 0
    latest: float | None = None
    for point in lhs.points:
        while pointer < len(rhs.points) and rhs.points[pointer].available_time \
                <= point.available_time:
            if _finite(rhs.points[pointer].value):
                latest = rhs.points[pointer].value
            pointer += 1
        if latest is None or not _finite(point.value):
            continue
        value = op(point.value, latest)
        if value is not None and _finite(value):
            out.append(point.with_value(value))
    dataset = f"{left.dataset}x{right.dataset}" if left.dataset and right.dataset else "cross"
    region = left.region if left.region == right.region else f"{left.region}|{right.region}"
    return Series(series_id=representation_id(dataset, name, {"b": right.series_id[-16:]}),
                  points=tuple(out), dataset=dataset, region=region,
                  information_type=left.information_type or right.information_type)


def ratio(left: Series, right: Series) -> Series:
    """A cross-dataset ratio, joined point-in-time. Division by ~0 is dropped, never clipped."""
    return _pairwise(left, right,
                     lambda a, b: None if abs(b) <= EPS else a / b, "ratio")


def product(left: Series, right: Series) -> Series:
    """THE INTERACTION. Two datasets whose product says what neither says alone -- a positioning
    extreme times a funding-stress state is a forced-flow claim; either one alone is not."""
    return _pairwise(left, right, lambda a, b: a * b, "product")


def event_window_aggregate(series: Series, events: Sequence[str], *, window_days: float = 3.0,
                           how: str = "mean") -> Series:
    """One value per EVENT: the series aggregated over the window BEFORE that event.

    Anchored on the event's own instant and reaching backwards only, so the aggregate published
    at the event is computable at the event. An event with nothing in its window produces no
    point: an empty window is UNMEASURED and is not an aggregate of zero.
    """
    ordered = series.sorted().points
    stamps: list[float] = []
    values: list[float] = []
    for point in ordered:
        at = parse_time(point.available_time)
        if at is None or not _finite(point.value):
            continue
        stamps.append(at.timestamp())
        values.append(point.value)
    out: list[Point] = []
    for raw_event in events:
        stamp = parse_time(raw_event)
        if stamp is None:
            continue
        hi = stamp.timestamp()
        lo = hi - window_days * 86400.0
        # Bisect rather than a scan per event: an event calendar and a daily axis are both long,
        # and the product of the two is what makes a "cheap" aggregate cost an hour.
        inside = values[bisect_left(stamps, lo):bisect_right(stamps, hi)]
        if not inside:
            continue
        if how == "sum":
            value = sum(inside)
        elif how == "max":
            value = max(inside)
        elif how == "last":
            value = inside[-1]
        else:
            value = _mean(inside)
        out.append(Point(available_time=stamp.isoformat(), period_time=stamp.isoformat(),
                         value=float(value)))
    return replace(series, points=tuple(out),
                   series_id=representation_id(series.dataset, "event_window_aggregate",
                                               {"days": window_days, "how": how}))


# ------------------------------------------------------------------------------- the registry
@dataclass(frozen=True)
class TransformSpec:
    """One transform: how many series it eats, what family it belongs to, and its defaults."""

    name: str
    family: str
    arity: int
    fn: Callable[..., Series]
    defaults: Mapping[str, Any]
    needs_events: bool = False


#: The FAMILY is the unit ROI is tracked by. Two parameterisations of `zscore` are one bet about
#: what normalisation buys; `zscore` and `vintage_revision` are not.
FAMILIES: Final[tuple[str, ...]] = ("normalisation", "surprise", "seasonal", "dynamics",
                                    "interaction", "event", "vintage", "state")

TRANSFORMS: Final[dict[str, TransformSpec]] = {
    "diff": TransformSpec("diff", "dynamics", 1, diff, {"lag": 1}),
    "acceleration": TransformSpec("acceleration", "dynamics", 1, acceleration, {"lag": 1}),
    "lead_lag": TransformSpec("lead_lag", "dynamics", 1, lead_lag, {"lag": 1}),
    "zscore": TransformSpec("zscore", "normalisation", 1, zscore, {"window": 0}),
    "rank_percentile": TransformSpec("rank_percentile", "normalisation", 1, rank_percentile,
                                     {"window": 0}),
    "surprise": TransformSpec("surprise", "surprise", 1, surprise, {"control": "weekday"}),
    "seasonal_expectation": TransformSpec("seasonal_expectation", "seasonal", 1,
                                          seasonal_expectation, {"cycle": "month"}),
    "pace": TransformSpec("pace", "seasonal", 1, pace, {"cycle": "month"}),
    "rolling_volatility": TransformSpec("rolling_volatility", "state", 1, rolling_volatility,
                                        {"window": 20}),
    "spectral_state": TransformSpec("spectral_state", "state", 1, spectral_state, {"window": 32}),
    "vintage_revision": TransformSpec("vintage_revision", "vintage", 1, vintage_revision, {}),
    "regime_conditioned": TransformSpec("regime_conditioned", "state", 2, regime_conditioned,
                                        {"buckets": 3}),
    "ratio": TransformSpec("ratio", "interaction", 2, ratio, {}),
    "product": TransformSpec("product", "interaction", 2, product, {}),
    "event_window_aggregate": TransformSpec("event_window_aggregate", "event", 1,
                                            event_window_aggregate,
                                            {"window_days": 3.0, "how": "mean"},
                                            needs_events=True),
}


@dataclass(frozen=True)
class Transform:
    """A named transform with its parameters, and optionally an inner transform composed under it.

    The composition is the INVENTION step: `Transform("zscore", inner=Transform("surprise"))` is
    a feature nobody wrote down, minted from two that were.
    """

    name: str
    params: Mapping[str, Any] = ()  # type: ignore[assignment]
    inner: Transform | None = None

    @property
    def chain(self) -> tuple[str, ...]:
        return (*(self.inner.chain if self.inner is not None else ()), self.name)

    @property
    def family(self) -> str:
        spec = TRANSFORMS.get(self.name)
        return spec.family if spec is not None else "unknown"

    @property
    def label(self) -> str:
        return "|".join(self.chain)


def compose(outer: Transform, inner: Transform) -> Transform:
    """`inner` then `outer`, as one transform. Composing onto a two-input transform is refused:
    the second input is a different series, not a stage, and pretending otherwise would silently
    drop it."""
    spec = TRANSFORMS.get(outer.name)
    if spec is None:
        raise KeyError(f"unknown transform {outer.name!r}")
    if spec.arity != 1:
        raise ValueError(f"{outer.name} takes {spec.arity} series: it cannot wrap a chain")
    return Transform(name=outer.name, params=dict(outer.params or {}), inner=inner)


def apply(transform: Transform, *inputs: Series, events: Sequence[str] = ()) -> Series:
    """Run a (possibly composed) transform and stamp the result with its full id.

    The id names the WHOLE chain, so `repr:fred:surprise|zscore:window=0` is recognisably one
    representation built from two steps rather than an anonymous number.
    """
    if not inputs:
        raise ValueError("a transform needs at least one series")
    spec = TRANSFORMS.get(transform.name)
    if spec is None:
        raise KeyError(f"unknown transform {transform.name!r}")
    primary = inputs[0]
    if transform.inner is not None:
        primary = apply(transform.inner, primary, *inputs[1:], events=events)
    params = {**dict(spec.defaults), **dict(transform.params or {})}
    if spec.arity == 2:
        if len(inputs) < 2:
            raise ValueError(f"{transform.name} needs two series")
        out = spec.fn(primary, inputs[1], **params)
    elif spec.needs_events:
        out = spec.fn(primary, events, **params)
    else:
        out = spec.fn(primary, **params)
    # A TWO-INPUT TRANSFORM KEEPS THE PAIR'S OWN LABELS. Rewriting them to the left operand's
    # would name `a x b` and `a x c` identically, which is not a naming quibble: the store is
    # keyed by id, so the second interaction would overwrite the first and the desk would hold
    # one cross-dataset feature where it had built two.
    if spec.arity == 2:
        return replace(out, series_id=representation_id(out.dataset, transform.label, params))
    dataset = inputs[0].dataset
    return replace(out, dataset=dataset, region=inputs[0].region,
                   information_type=inputs[0].information_type,
                   series_id=representation_id(dataset, transform.label, params))


# ------------------------------------------------------------------------------- the budget
def _id_tokens(rid: str) -> set[str]:
    return {t for t in rid.replace(":", " ").replace(",", " ").replace("|", " ").split() if t}


#: How many existing representations a novelty score is compared against. The grammar offers
#: thousands of proposals a pass and the store grows without bound, so an exhaustive comparison
#: is quadratic in two growing numbers -- measured on the real tree, 3,700 proposals against
#: 3,000 stored ids is eleven million set intersections for a SCORE, which is not what the hour
#: is for. An exact re-proposal is always caught (the id is matched directly); beyond that a
#: deterministic sample of the store is enough to rank, and the sample is the OLDEST-first slice
#: so it is stable across passes rather than drifting with whatever was minted last.
NOVELTY_SAMPLE: Final[int] = 256


def novelty(candidate_id: str, existing: Iterable[str]) -> float:
    """1 - the highest Jaccard similarity to anything that already exists, in [0, 1].

    An id nothing resembles scores 1.0; an exact re-proposal scores 0.0. This is the cheap
    distance, and cheap is the requirement: it is evaluated over the whole grammar every pass.
    """
    mine = _id_tokens(candidate_id)
    if not mine:
        return 0.0
    return round(1.0 - _closest(mine, _token_sets(existing), candidate_id), 6)


def _token_sets(existing: Iterable[str]) -> tuple[tuple[str, frozenset[str]], ...]:
    rows = [(rid, frozenset(_id_tokens(rid))) for rid in existing]
    if len(rows) > NOVELTY_SAMPLE:
        step = len(rows) / NOVELTY_SAMPLE
        rows = [rows[int(i * step)] for i in range(NOVELTY_SAMPLE)]
    return tuple(rows)


def _closest(mine: set[str], rows: tuple[tuple[str, frozenset[str]], ...],
             candidate_id: str) -> float:
    best = 0.0
    for rid, theirs in rows:
        if rid == candidate_id:
            return 1.0
        if not theirs:
            continue
        union = mine | theirs
        best = max(best, len(mine & theirs) / len(union) if union else 0.0)
    return best


def expected_value(family: str, history: Mapping[str, Mapping[str, float]],
                   *, prior_rate: float = 0.25, prior_weight: float = 4.0) -> float:
    """Laplace-smoothed candidates-per-use for a transform family.

    A family nobody has run yet takes the PRIOR, never 1.0 and never 0.0 -- an unmeasured family
    must neither outrank a family measured to convert nor be extinguished before its first trial.
    """
    row = history.get(family) or {}
    uses = float(row.get("used_by_candidates", 0.0)) + float(row.get("uses", 0.0))
    produced = float(row.get("candidates", 0.0)) + float(row.get("survivors", 0.0))
    return round((produced + prior_rate * prior_weight) / (uses + prior_weight), 6)


def rank_proposals(proposals: Sequence[tuple[str, str]], existing: Iterable[str],
                   history: Mapping[str, Mapping[str, float]], *, budget: int = 50
                   ) -> list[dict[str, Any]]:
    """Order `(representation_id, family)` proposals by novelty x expected value, take `budget`.

    Ties break on the id so a pass is reproducible: the same tree and the same history select the
    same representations, which is what makes a ROI series comparable across hours.
    """
    known = list(existing)
    exact = set(known)
    rows = _token_sets(known)
    cache: dict[str, float] = {}
    scored: list[dict[str, Any]] = []
    for rid, family in proposals:
        if rid in exact:
            nov = 0.0
        else:
            tokens = _id_tokens(rid)
            nov = round(1.0 - _closest(tokens, rows, rid), 6) if tokens else 0.0
        if family not in cache:
            cache[family] = expected_value(family, history)
        ev = cache[family]
        scored.append({"id": rid, "family": family, "novelty": nov, "expected_value": ev,
                       "score": round(nov * ev, 6)})
    scored.sort(key=lambda r: (-float(r["score"]), str(r["id"])))
    return scored[:budget]


def to_json(series: Series) -> str:
    """The stored form: the id, the labels, and every point with both clocks."""
    return json.dumps({
        "id": series.series_id, "dataset": series.dataset, "region": series.region,
        "information_type": series.information_type, "n": len(series.points),
        "points": [{"available_time": p.available_time, "period_time": p.period_time,
                    "value": p.value, "vintage_id": p.vintage_id} for p in series.points],
    }, indent=1, default=str)

```

### scripts\check_mt5_coverage_floor.py
```python
#!/usr/bin/env python3
"""Ratcheting branch-coverage floor for the MT5 MONEY PATH -- the files that move capital.

    pytest desks/mt5/tests -q -p no:randomly --timeout=600 \\
           --cov=desks/mt5/mt5desk --cov=desks/mt5/research --cov-branch \\
           --cov-report=term:skip-covered --cov-report=json:mt5cov.json
    python scripts/check_mt5_coverage_floor.py --report mt5cov.json          # the gate
    python scripts/check_mt5_coverage_floor.py --report mt5cov.json --init   # seal the baseline, once

WHY A SEPARATE FLOOR. The repo's headline coverage measures `libs`, and its "money path" list
names the retired crypto executor. The MT5 gateway, sizing, promoter and allocator bridge --
the code that actually places orders -- were outside every coverage number the CI reported. A
green gate that measures the wrong heart is worse than no gate, because it is believed.

THE FLOOR RATCHETS. Per money-path file, the highest branch coverage ever recorded is stored and
a run may not fall more than TOLERANCE below it. Nothing here sets a target by fiat; the target
is what the desk has already achieved, and the only direction allowed is up.

THE BASELINE IS COMMITTED, OR THERE IS NO RATCHET (audit 2026-09-05). Until this date the
high-water file was never committed and a missing file was read as `{}` -- so every fresh CI
runner compared the measurement against ZERO, wrote a high-water mark that evaporated with the
runner, and reported green. A ratchet whose memory lives on a disposable host starts from nothing
every time, which is to say it is not a ratchet. Now a missing or unreadable baseline is a FAILURE
that names the file and the one command that creates it, and creating it is an explicit `--init`
that refuses to overwrite: the first measurement is a deliberate act with a date, a report hash
and the suite command on it, and every later rise is recorded on top of that.

ABSENT IS A FAILURE, NOT A LINE OF OUTPUT. The same audit found that a money-path module missing
from the report printed `absent` and moved on. A module leaves the report when its test file is
deleted, when it is renamed, or when the run dies before importing it -- exactly the cases a
coverage floor exists to catch -- and the capital-moving code needs the strongest proof, not the
weakest. The one honest exception is declared in UNMEASURABLE_HERE with its reason, and that
allowlist is itself ratcheted: the first time an allowlisted module DOES appear in the report its
number is recorded in the baseline, its absence is never again excused, and the now-dead entry is
reported on every run until somebody deletes it.

MEASURED AT SEALING, 2026-09-05 (1352 passed, 3 skipped, coverage.py 7.16.0, branch mode). The
gateway was expected to be the excused absence -- it imports MetaTrader5 at module scope and that
package is Windows-only. It was NOT absent: coverage.py lists every file under a `--cov` source
directory whether or not anything imported it, so `gateway.py` is in the report at 0.60% -- ten
prelude lines (21-33, up to the `import MetaTrader5 as mt5` that raises), 0 of 438 branches. The
excuse was written for an absence the report did not have, so the seal retired it and floored the
file at 0.6%, and the reason it was written for is kept beside that number in the baseline. That
is the truer statement: the order-placing file is effectively unexecuted on this host and the
floor says so in a number rather than behind an excuse. The exit is unchanged -- split the
portable decision core out of the terminal-bound shell so it can be executed here.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
HIGH_WATER = ROOT / "desks" / "mt5" / "data" / "coverage_high_water.json"
#: Slack below the high-water mark, as a fraction of 1. Branch coverage moves a little with test
#: ordering and optional-dependency skips; a floor that fires on noise gets deleted, which is
#: worse than a floor two points low. A fall past this is a regression and fails the run.
TOLERANCE = 0.02

#: The invocation the baseline is sealed from -- verbatim from ci.yml's mt5-money-path job, so
#: the number in the committed file and the number CI measures come from the same command.
SUITE_COMMAND = (
    "pytest desks/mt5/tests -q -p no:randomly --timeout=600 "
    "--cov=desks/mt5/mt5desk --cov=desks/mt5/research --cov-branch "
    "--cov-report=term:skip-covered --cov-report=json:mt5cov.json"
)
INIT_COMMAND = "python scripts/check_mt5_coverage_floor.py --report mt5cov.json --init"

#: The MT5 money path, by file. Every one either places an order, sizes one, decides what may
#: trade, or feeds a number the sizer trusts.
MONEY_PATH = (
    "desks/mt5/mt5desk/gateway.py",
    # THE DECISIONS THEMSELVES (added 2026-09-05, the split this file's docstring names as the
    # exit). `gateway.py` is the venue adapter and is measured at ~0.6% here for a structural
    # reason -- MetaTrader5 is Windows-only, so the runner executes ten prelude lines and stops.
    # Every decision it used to hold -- the sizing laws, the heat cap, the allocator readers,
    # roster admission, the state gate, the bracket arithmetic, the retcode diagnosis, the
    # session deadline, the execution context, the release gate, both lanes' steps -- now lives
    # in `decision_core.py`, which imports on any host and IS executed by the desk's suite. This
    # entry is what makes that a measurement rather than a claim: the money path's proof is now
    # a number that can fall, and this file is where it is caught when it does.
    "desks/mt5/mt5desk/decision_core.py",
    "desks/mt5/mt5desk/engine.py",
    "desks/mt5/mt5desk/independence.py",
    "desks/mt5/mt5desk/markout.py",
    "desks/mt5/research/pf_allocator.py",
    "desks/mt5/research/promoter.py",
    "desks/mt5/research/state_admission_run.py",
    "desks/mt5/research/session_phase.py",
    "desks/mt5/research/allocator_attribution.py",
)

#: Money-path modules whose ABSENCE from the report is excused, path -> the structural reason.
#:
#: This is the only way a money-path file may be missing from the report without failing the
#: gate, and an entry is an interim, not a settlement: it is written with its reason so that
#: absent-and-known and absent-and-broken cannot render alike (L1.28a), and it is expected to be
#: outgrown.
#:
#: RATCHETED. An entry here is honoured only while the baseline has never measured the file. The
#: first run that finds the file in the report records its number, stamps `allowlist_retired` in
#: the baseline (reason kept), and from then on the file is held to its floor like every other --
#: this constant no longer excuses it. The stale entry is reported on every run until it is
#: deleted, and tests/scripts/test_check_mt5_coverage_floor.py fences the committed baseline
#: against carrying a retired entry that is still listed here.
#:
#: EMPTY SINCE THE SEAL. The one entry this was written for --
#:     "desks/mt5/mt5desk/gateway.py":
#:         "MetaTrader5 not importable on Linux; portable decision core pending split"
#: -- was retired by the seal on 2026-09-05: the report covered the gateway (0.6%, the import
#: prelude), so the ratchet floored it and the entry became dead code. The reason lives on in the
#: baseline's `allowlist_retired`. The next money-path file the host genuinely cannot measure goes
#: here with its reason, and leaves the same way.
UNMEASURABLE_HERE: dict[str, str] = {}


def _norm(path: str) -> str:
    return path.replace("\\", "/")


def _branch_pct(entry: dict[str, Any]) -> float | None:
    s = entry.get("summary") or {}
    if "percent_covered" in s:
        return float(s["percent_covered"]) / 100.0
    return None


def measure(report: dict[str, Any]) -> dict[str, float | None]:
    """Per money-path file, the covered fraction from a coverage.py JSON report, or None when the
    file is not in the report at all (or is there without a summary, which is the same absence).

    Keys are matched by suffix so the Windows box's backslashed absolute paths and the runner's
    relative ones both resolve to the same money-path entry.
    """
    raw = report.get("files") or {}
    files = {_norm(str(k)): v for k, v in raw.items()} if isinstance(raw, dict) else {}
    out: dict[str, float | None] = {}
    for rel in MONEY_PATH:
        entry = next((v for k, v in files.items() if k.endswith(rel)), None)
        out[rel] = _branch_pct(entry) if isinstance(entry, dict) else None
    return out


def report_meta(report: dict[str, Any]) -> dict[str, Any]:
    meta = report.get("meta")
    return dict(meta) if isinstance(meta, dict) else {}


def is_branch_report(report: dict[str, Any]) -> bool:
    """A branch floor sealed from, or checked against, a line-only report is an inflated number:
    line coverage is always at least branch coverage. coverage.py stamps the report with the mode
    it ran in, and this refuses to read a report that does not say `branch_coverage: true`."""
    return bool(report_meta(report).get("branch_coverage"))


def read_baseline(path: Path) -> dict[str, Any]:
    """The committed high-water record. Raises rather than defaulting: FileNotFoundError when it
    is absent, ValueError when it is not a JSON object with a `high_water` mapping. Neither is
    ever read as `{}` again -- that was the audit's finding (a)."""
    doc = json.loads(path.read_text("utf-8"))
    if not isinstance(doc, dict) or not isinstance(doc.get("high_water"), dict):
        raise ValueError(f"{path} is not a high-water record (no `high_water` mapping)")
    return doc


def evaluate(
    now: dict[str, float | None],
    baseline: dict[str, Any],
    tolerance: float = TOLERANCE,
    *,
    stamp: str | None = None,
) -> dict[str, Any]:
    """The verdict, pure so the tests can drive it.

    Returns `lines` (the per-file table), `notices` (reported, never fatal), `failures` (fatal),
    `high_water` (the marks to persist; only ever higher than the input) and `allowlist_retired`
    (allowlisted files the report has now measured, with when and at what).
    """
    hw: dict[str, float] = {k: float(v) for k, v in baseline["high_water"].items()}
    retired: dict[str, dict[str, Any]] = {
        k: dict(v) for k, v in (baseline.get("allowlist_retired") or {}).items()
    }
    when = stamp or datetime.now(tz=UTC).isoformat()
    new_hw = dict(hw)
    lines: list[str] = []
    notices: list[str] = []
    failures: list[str] = []

    for rel in MONEY_PATH:
        pct = now.get(rel)
        prev = hw.get(rel)
        excused = rel in UNMEASURABLE_HERE and prev is None and rel not in retired
        if pct is None:
            if excused:
                lines.append(f"{rel:52s} {'absent':>7s} {'-':>7s}   excused: "
                             f"{UNMEASURABLE_HERE[rel]}")
                continue
            if prev is not None or rel in retired:
                seen = retired.get(rel, {})
                known = prev if prev is not None else float(seen.get("pct") or 0.0)
                since = f" on {seen['measured_at']}" if seen.get("measured_at") else ""
                failures.append(
                    f"{rel}: ABSENT from the coverage report. Its absence is not excused -- it "
                    f"has been measured before (high-water {known:.1%}{since}), so a report "
                    "without it is a report with a hole where the money path was."
                )
            else:
                failures.append(
                    f"{rel}: ABSENT from the coverage report and not declared in "
                    "UNMEASURABLE_HERE. A money-path module that stops being measured has lost "
                    "its test file, moved, or never imported -- name the reason in the allowlist "
                    "or restore the measurement; the gate does not score silence."
                )
            lines.append(f"{rel:52s} {'absent':>7s} {'-':>7s}   <-- FAIL")
            continue

        if rel in UNMEASURABLE_HERE:
            if rel not in retired:
                retired[rel] = {"measured_at": when, "pct": round(pct, 4),
                                "was_excused_as": UNMEASURABLE_HERE[rel]}
                notices.append(
                    f"ALLOWLIST RATCHETED: {rel} appeared in the report at {pct:.1%}. Its "
                    "absence is no longer excused; the baseline now holds it to a floor. Delete "
                    "its UNMEASURABLE_HERE entry -- the ratchet has retired it."
                )
            else:
                notices.append(
                    f"STALE ALLOWLIST ENTRY: {rel} was measured on "
                    f"{retired[rel].get('measured_at', '?')} and is floored; the "
                    "UNMEASURABLE_HERE entry is dead code and should be deleted."
                )

        flag = ""
        mark = round(pct, 4)
        if prev is None:
            new_hw[rel] = mark
            flag = "   first measurement -- floored here"
            shown_prev = "-"
        else:
            shown_prev = f"{prev:7.1%}"
            if pct + 1e-9 < prev - tolerance:
                failures.append(
                    f"{rel}: {pct:.1%} fell more than {tolerance:.0%} below its high-water "
                    f"{prev:.1%}"
                )
                flag = "   <-- REGRESSION"
            elif mark > prev:
                new_hw[rel] = mark
                flag = "   raised"
        lines.append(f"{rel:52s} {pct:7.1%} {shown_prev:>7s}{flag}")

    for rel in sorted(set(hw) - set(MONEY_PATH)):
        notices.append(
            f"baseline carries {rel} at {hw[rel]:.1%} but it is no longer in MONEY_PATH; the "
            "number is kept (deleting a mark is the denominator trick) and not compared."
        )
    return {
        "lines": lines,
        "notices": notices,
        "failures": failures,
        "high_water": new_hw,
        "allowlist_retired": retired,
    }


def seal(
    now: dict[str, float | None],
    *,
    report_path: str,
    report_sha256: str,
    meta: dict[str, Any],
    stamp: str | None = None,
) -> dict[str, Any]:
    """The first baseline: every measured money-path file at its measured value, every excused
    file with its reason, and the provenance of the report the numbers came from.

    An allowlisted file that the sealing report DOES cover is retired at the seal, reason kept:
    the excuse was never needed on this host and the record says so from day one."""
    when = stamp or datetime.now(tz=UTC).isoformat()
    return {
        "_": (
            "HIGH-WATER MARKS for MT5 money-path branch coverage, per file, as fractions of 1. "
            "Sealed once by --init, raised by the gate whenever a run measures higher, NEVER "
            "lowered by code: nothing lowers a mark but a human editing this file with a reason. "
            "A missing file is a CI failure, not a zero -- a ratchet with no memory is not one."
        ),
        "sealed_at": when,
        "measured_at": when,
        "suite_command": SUITE_COMMAND,
        "report": report_path,
        "report_sha256": report_sha256,
        "report_meta": meta,
        "tolerance": TOLERANCE,
        "money_path_files": list(MONEY_PATH),
        "high_water": {rel: round(pct, 4) for rel, pct in now.items() if pct is not None},
        "unmeasurable_here": {
            rel: UNMEASURABLE_HERE[rel]
            for rel, pct in now.items()
            if pct is None and rel in UNMEASURABLE_HERE
        },
        "allowlist_retired": {
            rel: {"measured_at": when, "pct": round(pct, 4),
                  "was_excused_as": UNMEASURABLE_HERE[rel]}
            for rel, pct in now.items()
            if pct is not None and rel in UNMEASURABLE_HERE
        },
    }


def _write(path: Path, doc: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, indent=1, sort_keys=False) + "\n", "utf-8")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--report", default="mt5cov.json", help="coverage.py JSON report")
    ap.add_argument("--tolerance", type=float, default=TOLERANCE)
    ap.add_argument("--baseline", default=None,
                    help=f"high-water record (default {HIGH_WATER.relative_to(ROOT)})")
    ap.add_argument("--init", action="store_true",
                    help="SEAL the baseline from this report. Refuses if one exists.")
    a = ap.parse_args(argv)
    baseline_path = Path(a.baseline) if a.baseline else HIGH_WATER

    report_file = Path(a.report)
    try:
        raw = report_file.read_bytes()
        report = json.loads(raw.decode("utf-8"))
    except (OSError, ValueError) as exc:
        print(f"coverage report unreadable: {a.report} ({exc}). Produce it first:\n"
              f"  {SUITE_COMMAND}")
        return 1
    if not isinstance(report, dict) or not is_branch_report(report):
        print(f"{a.report} was not produced with --cov-branch (meta.branch_coverage is not true). "
              "This is a BRANCH floor; a line-only report would inflate every number in it.")
        return 1
    sha = hashlib.sha256(raw).hexdigest()
    now = measure(report)

    if a.init:
        if baseline_path.exists():
            print(f"REFUSING --init: {baseline_path} already exists. The gate raises it by itself "
                  "on every higher measurement; the only way down is a human editing the file "
                  "with a reason, never a re-seal.")
            return 1
        unexcused = [rel for rel, pct in now.items()
                     if pct is None and rel not in UNMEASURABLE_HERE]
        if unexcused:
            print("REFUSING --init: the report does not cover every money-path module, and a "
                  "baseline sealed over a partial population is a permanent error. Absent and not "
                  f"in UNMEASURABLE_HERE: {', '.join(unexcused)}")
            return 1
        doc = seal(now, report_path=a.report, report_sha256=sha, meta=report_meta(report))
        _write(baseline_path, doc)
        print(f"sealed {baseline_path} from {a.report} (sha256 {sha[:12]}...):")
        for rel, pct in doc["high_water"].items():
            print(f"  {rel:52s} {pct:7.1%}")
        for rel, why in doc["unmeasurable_here"].items():
            print(f"  {rel:52s} {'absent':>7s}   excused: {why}")
        print("  commit this file: it is the ratchet's memory and a runner has none.")
        return 0

    try:
        baseline = read_baseline(baseline_path)
    except FileNotFoundError:
        print(f"NO BASELINE: {baseline_path} is absent. A ratchet with nothing to ratchet against "
              "is not a ratchet, and a zero floor is not a floor -- this used to pass silently. "
              f"Seal one deliberately from a measured report and commit it:\n  {SUITE_COMMAND}\n"
              f"  {INIT_COMMAND}")
        return 1
    except (OSError, ValueError) as exc:
        print(f"BASELINE UNREADABLE: {baseline_path} ({exc}). Not defaulting to zero; repair the "
              "file by hand from git history rather than re-sealing.")
        return 1

    verdict = evaluate(now, baseline, a.tolerance)
    print(f"{'file':52s} {'now':>7s} {'high':>7s}   "
          f"(baseline sealed {baseline.get('sealed_at', '?')})")
    for line in verdict["lines"]:
        print(line)
    for note in verdict["notices"]:
        print(f"  {note}")

    changed = (verdict["high_water"] != baseline["high_water"]
               or verdict["allowlist_retired"] != (baseline.get("allowlist_retired") or {}))
    if changed:
        # THE MARK ONLY RISES. `evaluate` never returns a lower value, so this write is monotone by
        # construction; the provenance fields move with it so the file always names the report
        # that earned its numbers.
        doc = dict(baseline)
        doc["high_water"] = verdict["high_water"]
        doc["allowlist_retired"] = verdict["allowlist_retired"]
        doc["measured_at"] = datetime.now(tz=UTC).isoformat()
        doc["report"] = a.report
        doc["report_sha256"] = sha
        doc["report_meta"] = report_meta(report)
        doc["money_path_files"] = list(MONEY_PATH)
        _write(baseline_path, doc)
        print(f"  high-water raised -> {baseline_path} (commit it; a runner's copy evaporates)")

    if verdict["failures"]:
        for f in verdict["failures"]:
            print(f"  FAIL: {f}")
        print(f"{len(verdict['failures'])} money-path failure(s). Floors ratchet: restore the "
              "coverage, or edit the record by hand with a reason.")
        return 1
    print("money-path floor held")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

```

### scripts\run_completion_program.py
```python
#!/usr/bin/env python3
"""Run the integrated completion capabilities against current desk evidence.

No synthetic success values are inserted.  A missing input produces ``UNMEASURED`` and names the
input contract; the report is then consumed by max-push so absence becomes ranked work.
"""

from __future__ import annotations

import contextlib
import json
import sys
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from libs.data.asymmetry import (  # noqa: E402
    information_advantage_frontier,
    self_footprint_coverage,
)
from libs.ops.production_contract import (  # noqa: E402
    accounting_from_execution_tape,
    autonomous_recovery_plan,
    counterfactual_reality_gap,
    decision_record,
    deterministic_hot_path,
    latency_metrics,
    preflight_contract,
    reality_gap,
    strategy_manifest,
    venue_eligibility,
)
from libs.portfolio.decision_intelligence import (  # noqa: E402
    alpha_retention,
    capital_inventory_policy,
    capital_topology,
    dependence_preserving_monte_carlo,
    effective_breadth,
    execution_opportunity,
    exit_reallocation_decision,
    momentum_rebound_surface,
    monetisation_latency,
    path_drawdown_state,
    regime_conditional_allocation,
    regime_model_selection,
    return_attribution,
    transition_posterior,
    transition_surprise,
    trigger_collision_control,
    venue_stress_state,
    volatility_manifold_state,
    xsec_momentum_book,
)
from libs.research.funnel import meaningful_research_throughput  # noqa: E402
from libs.research.research_control import (  # noqa: E402
    actor_graph,
    causal_structure,
    compile_public_strategy,
    completion_supervisor,
    concurrency_economics,
    context_packet,
    creator_change_intelligence,
    dependency_aware_evidence,
    distill_doctrine,
    distill_workflow,
    ephemeral_specialist,
    frontier_health,
    lawful_disclosure_record,
    missed_opportunity_tests,
    model_router,
    open_world_coverage,
    operator_surface,
    prequential_score,
    research_dag_schedule,
    resolve_instruction_conflict,
    source_information_economics,
)
from libs.validation.research_diagnostics import (  # noqa: E402
    ConditionalClaim,
    ablate_gates,
    cluster_failures,
    conditional_validation,
    semantic_label_integrity,
    sequential_experiment_design,
    threshold_sensitivity,
)

OUT = ROOT / "data" / "completion_program.json"


def _read(rel: str, default: Any = None) -> Any:
    try:
        return json.loads((ROOT / rel).read_text("utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


def _rows(doc: Any, *keys: str) -> list[dict[str, Any]]:
    value = doc
    for key in keys:
        value = value.get(key) if isinstance(value, dict) else None
    return [r for r in value if isinstance(r, dict)] if isinstance(value, list) else []


def _jsonl(rel: str) -> list[dict[str, Any]]:
    try:
        return [
            row
            for line in (ROOT / rel).read_text("utf-8").splitlines()
            if line.strip()
            for row in [json.loads(line)]
            if isinstance(row, dict)
        ]
    except (OSError, json.JSONDecodeError):
        return []


def _numeric_series(doc: Any, *keys: str) -> list[float]:
    if not isinstance(doc, dict):
        return []
    for key in keys:
        value = doc.get(key)
        if isinstance(value, list):
            clean = [float(x) for x in value if isinstance(x, (int, float)) and np.isfinite(x)]
            if len(clean) >= 2:
                return clean
    return []


def _validation() -> dict[str, Any]:
    review = _read("data/research_review.json", {})
    sweep = _read("data/full_sweep_report.json", {})
    killed = _rows(sweep, "killed_cells") or _rows(review, "kill_audit", "rows")
    statistics = [
        float(r["statistic"]) for r in killed if isinstance(r.get("statistic"), (int, float))
    ]
    threshold = (
        review.get("gate_power", {}).get("f3_threshold") if isinstance(review, dict) else None
    )
    sensitivity = (
        threshold_sensitivity(statistics, float(threshold))
        if isinstance(threshold, (int, float))
        else {"status": "UNMEASURED", "reason": "F3 threshold/statistics absent"}
    )
    gate_vectors: dict[str, list[bool]] = {}
    for row in killed:
        results = row.get("gate_results")
        if isinstance(results, dict):
            for gate, verdict in results.items():
                gate_vectors.setdefault(str(gate), []).append(bool(verdict))
    ablation = (
        ablate_gates(gate_vectors)
        if gate_vectors
        else {"status": "UNMEASURED", "reason": "per-cell gate vectors absent"}
    )
    conditional_rows = _rows(_read("data/conditional_claims.json", {}), "claims")
    conditional = []
    for row in conditional_rows:
        try:
            conditional.append(
                conditional_validation(
                    ConditionalClaim(
                        claim_id=str(row["claim_id"]),
                        state_name=str(row["state_name"]),
                        state_declared_before_results=bool(
                            row.get("state_declared_before_results")
                        ),
                        state_observable_at_decision=bool(row.get("state_observable_at_decision")),
                        untouched_oos=bool(row.get("untouched_oos")),
                        ancestry_trials=int(row.get("ancestry_trials", 1)),
                        returns=tuple(float(x) for x in row.get("returns", [])),
                        state_mask=tuple(bool(x) for x in row.get("state_mask", [])),
                    )
                )
            )
        except (KeyError, TypeError, ValueError) as exc:
            conditional.append({"status": "INVALID_INPUT", "reason": str(exc)})
    design_rows = _rows(_read("data/experiment_designs.json", {}), "experiments")
    sequential = []
    for row in design_rows:
        try:
            sequential.append(
                sequential_experiment_design(
                    minimum_effect=float(row["minimum_effect"]),
                    noise_sd=float(row["noise_sd"]),
                    available_n=int(row.get("available_n", 0)),
                    alpha=float(row.get("alpha", 0.05)),
                    power=float(row.get("power", 0.8)),
                    planned_looks=int(row.get("planned_looks", 1)),
                    observed_effect=(
                        float(row["observed_effect"])
                        if isinstance(row.get("observed_effect"), (int, float))
                        else None
                    ),
                    standard_error=(
                        float(row["standard_error"])
                        if isinstance(row.get("standard_error"), (int, float))
                        else None
                    ),
                    additional_information_value=(
                        float(row["additional_information_value"])
                        if isinstance(row.get("additional_information_value"), (int, float))
                        else None
                    ),
                    additional_cost=(
                        float(row["additional_cost"])
                        if isinstance(row.get("additional_cost"), (int, float))
                        else None
                    ),
                )
            )
        except (KeyError, TypeError, ValueError) as exc:
            sequential.append({"status": "INVALID_INPUT", "reason": str(exc)})
    semantic_rows = _rows(_read("data/semantic_label_audits.json", {}), "audits")
    semantic = []
    for row in semantic_rows:
        records = row.get("records", [])
        try:
            semantic.append(
                semantic_label_integrity(
                    records if isinstance(records, list) else [],
                    inferred_field=str(row.get("inferred_field", "inferred")),
                    authoritative_field=str(row.get("authoritative_field", "authoritative")),
                    authoritative_source=str(row.get("authoritative_source", "")),
                    outcome_field=(str(row["outcome_field"]) if row.get("outcome_field") else None),
                    min_ground_truth=int(row.get("min_ground_truth", 30)),
                    min_preregistered_kappa=(
                        float(row["min_preregistered_kappa"])
                        if isinstance(row.get("min_preregistered_kappa"), (int, float))
                        else None
                    ),
                )
            )
        except (TypeError, ValueError) as exc:
            semantic.append({"status": "INVALID_INPUT", "reason": str(exc)})
    return {
        "threshold_sensitivity": sensitivity,
        "gate_ablation": ablation,
        "failure_clustering": cluster_failures(killed),
        "conditional_validation": conditional or [{"status": "UNMEASURED"}],
        "sequential_experiment_design": sequential or [{"status": "UNMEASURED"}],
        "semantic_label_integrity": semantic or [{"status": "UNMEASURED"}],
    }


def _portfolio() -> dict[str, Any]:
    live = _read("web/cashcarry_live.json", {})
    shadow = _read("web/cashcarry_shadow.json", {})
    portfolio = _read("data/portfolio_admission.json", {})
    series = _numeric_series(shadow, "returns", "daily_returns", "pnl_series")
    sleeve_map = shadow.get("sleeve_returns", {}) if isinstance(shadow, dict) else {}
    sleeve_series = (
        [v for v in sleeve_map.values() if isinstance(v, list)]
        if isinstance(sleeve_map, dict)
        else []
    )
    matrix = None
    if sleeve_series and len({len(v) for v in sleeve_series}) == 1 and len(sleeve_series[0]) >= 2:
        matrix = np.asarray(sleeve_series, dtype="float64").T
    elif len(series) >= 2:
        matrix = np.asarray(series, dtype="float64")[:, None]
    weights = portfolio.get("weights") if isinstance(portfolio, dict) else None
    if isinstance(weights, dict) and matrix is not None:
        w = [float(weights.get(name, 0.0)) for name in sleeve_map] if sleeve_map else [1.0]
    else:
        w = [1.0] if matrix is not None else []

    regime = _read("web/regime.json", {})
    states = regime.get("history", []) if isinstance(regime, dict) else []
    states = [str(x.get("state", x)) if isinstance(x, dict) else str(x) for x in states]
    transitions = transition_posterior(states)
    surprise = (
        {"status": "UNMEASURED"}
        if transitions.get("status") != "MEASURED"
        else transition_surprise(str(states[-2]), str(states[-1]), transitions["posterior"])
    )
    trigger_history = _read("data/trigger_history.json", {}).get("matrix", [])
    prices = _read("data/xsec_prices.json", {}).get("prices", [])
    intended = float(live.get("intended_pnl", 0.0)) if isinstance(live, dict) else 0.0
    realised = (
        float(live.get("realised_pnl", live.get("pnl", 0.0))) if isinstance(live, dict) else 0.0
    )
    stage_times = live.get("stage_times", {}) if isinstance(live, dict) else {}
    half_life = float(live.get("half_life_seconds", 0.0)) if isinstance(live, dict) else 0.0
    edge_bps = float(live.get("edge_bps", 0.0)) if isinstance(live, dict) else 0.0
    topology_doc = _read("data/capital_topology.json", {})
    topology_rows = _rows(topology_doc, "accounts")
    topology_limits = topology_doc.get("limits", {}) if isinstance(topology_doc, dict) else {}
    volatility_doc = _read("data/volatility_surfaces.json", {})
    surfaces = volatility_doc.get("surfaces", []) if isinstance(volatility_doc, dict) else []
    manifold = {"status": "UNMEASURED"}
    if isinstance(surfaces, list) and surfaces:
        try:
            manifold = volatility_manifold_state(
                surfaces,
                train_rows=int(volatility_doc.get("train_rows", 0)),
                rank=int(volatility_doc.get("rank", 0)),
                anomaly_quantile=float(volatility_doc.get("anomaly_quantile", 0.99)),
                asset_labels=(
                    volatility_doc.get("asset_labels")
                    if isinstance(volatility_doc.get("asset_labels"), list)
                    else None
                ),
            )
        except (TypeError, ValueError, np.linalg.LinAlgError) as exc:
            manifold = {"status": "INVALID_INPUT", "reason": str(exc)}
    venue_doc = _read("data/venue_stress_history.json", {})
    venue_history = _rows(venue_doc, "history")
    venue_state = venue_stress_state(
        venue_history,
        components=(
            venue_doc.get("components")
            if isinstance(venue_doc, dict) and isinstance(venue_doc.get("components"), list)
            else (
                "liquidations",
                "open_interest_change_abs",
                "funding_abs",
                "basis_abs",
                "depth_drop",
                "insurance_fund_drawdown",
                "collateral_haircut",
                "adl_level",
                "withdrawal_constraint",
            )
        ),
        alert_z=(
            float(venue_doc["alert_z"])
            if isinstance(venue_doc, dict) and isinstance(venue_doc.get("alert_z"), (int, float))
            else None
        ),
    )
    return {
        "volatility_manifold": manifold,
        "venue_stress_state": venue_state,
        "capital_topology": capital_topology(
            topology_rows,
            max_venue_fraction=float(topology_limits.get("max_venue_fraction", 1.0)),
            max_collateral_fraction=float(topology_limits.get("max_collateral_fraction", 1.0)),
        ),
        "portfolio_monte_carlo": (
            dependence_preserving_monte_carlo(matrix, w, n_paths=500)
            if matrix is not None
            else {"status": "UNMEASURED"}
        ),
        "effective_breadth": (
            effective_breadth(matrix) if matrix is not None else {"status": "UNMEASURED"}
        ),
        "regime_transition_posterior": transitions,
        "transition_surprise": surprise,
        "path_drawdown": path_drawdown_state(series),
        "capital_inventory": capital_inventory_policy(
            deployable=max(0.0, float(live.get("deployable", 0.0))),
            dry_powder=max(0.0, float(live.get("dry_powder", 0.0))),
            opportunity_score=float(live.get("opportunity_score", 0.0)),
            future_option_score=float(live.get("future_option_score", 0.0)),
        ),
        "trigger_collision": (
            trigger_collision_control(trigger_history)
            if isinstance(trigger_history, list) and len(trigger_history) >= 2
            else {"status": "UNMEASURED"}
        ),
        "xsec_momentum": (
            xsec_momentum_book(prices)
            if isinstance(prices, list) and len(prices) >= 2
            else {"status": "UNMEASURED"}
        ),
        "momentum_rebound": momentum_rebound_surface([], [], []),
        "exit_engine": exit_reallocation_decision(
            live.get("hold_scenarios", []), live.get("alternative_scenarios", [])
        ),
        "execution_surface": (
            execution_opportunity(
                gross_edge_bps=edge_bps,
                order_size=float(live["order_size"]),
                queue_ahead=float(live["queue_ahead"]),
                through_volume=float(live["through_volume"]),
                taker_cost_bps=float(live.get("taker_cost_bps", 0.0)),
                adverse_selection_bps=float(live.get("adverse_selection_bps", 0.0)),
            )
            if isinstance(live, dict)
            and all(k in live for k in ("order_size", "queue_ahead", "through_volume"))
            else {"status": "UNMEASURED"}
        ),
        "alpha_retention": alpha_retention(
            intended_pnl=intended, realised_pnl=realised, leaks=live.get("leaks", {})
        ),
        "return_attribution": return_attribution(series, _numeric_series(live, "market_returns")),
        "monetisation_latency": monetisation_latency(
            stage_times, edge_bps=edge_bps, half_life_seconds=half_life
        ),
        "regime_allocation": regime_conditional_allocation(
            regime.get("posterior", {}), portfolio.get("state_elog", {})
        ),
        "regime_model_selection": regime_model_selection(
            regime.get("model_oos", {}) if isinstance(regime, dict) else {}
        ),
    }


def _research() -> dict[str, Any]:
    ledger = _read("data/decision_ledger.json", {})
    decisions = _rows(ledger, "decisions")
    source = _read("data/source_production.json", {})
    sources = _rows(source, "sources")
    claims = _rows(_read("data/public_claims.json", {}), "claims")
    evidence = _read("data/evidence_fusion.json", {})
    values, corr = evidence.get("values", []), evidence.get("correlation", [])
    tasks = _rows(_read("data/research_tasks.json", {}), "tasks")
    model_history = _rows(_read("data/model_attribution.json", {}), "events")
    traces = _read("data/workflow_traces.json", {}).get("traces", [])
    lessons = _rows(_read("data/lessons.json", {}), "lessons")
    forecasts = _rows(_read("data/forecasts.json", {}), "forecasts")
    completion = _rows(_read("data/completion_ledger_status.json", {}), "rows")
    queue = _rows(_read("data/max_push_queue.json", {}), "queue")
    live_ladder = _read("data/live_ladder.json", {})
    live = _rows(live_ladder, "rows")
    intelligence_cycle = _read("web/intelligence_cycle.json", {})
    study_status = _read("data/study_status.json", {})
    research_review = _read("data/research_review.json", {})
    completion_status = _read("data/completion_ledger_status.json", {})
    blocked = [r for r in completion if r.get("status") == "EXTERNALLY_BLOCKED"]
    status_counts = Counter(str(r.get("status")) for r in decisions)
    discovered = sum(int(r.get("found", 0) or 0) for r in sources)
    distinct = sum(int(r.get("novel", 0) or 0) for r in sources)
    tested = sum(int(r.get("tested", 0) or 0) for r in sources)
    survivors = sum(int(r.get("independent", r.get("survivors", 0)) or 0) for r in sources)
    workers = _read("data/concurrency_benchmarks.json", {})
    worker_rows = _rows(workers, "samples")
    disclosures = _rows(_read("data/disclosure_events.json", {}), "events")
    disclosure_rows = []
    for row in disclosures:
        try:
            disclosure_rows.append(
                lawful_disclosure_record(
                    source=str(row["source"]),
                    published_at=row["published_at"],
                    first_seen_at=row["first_seen_at"],
                    parsed_at=row["parsed_at"],
                    content_hash=str(row["content_hash"]),
                    claim=str(row["claim"]),
                )
            )
        except (KeyError, TypeError, ValueError) as exc:
            disclosure_rows.append({"status": "INVALID_INPUT", "reason": str(exc)})
    specialist_events = _rows(_read("data/specialist_history.json", {}), "events")
    causal_rows = _rows(_read("data/causal_mechanisms.json", {}), "mechanisms")
    source_economics_rows = _rows(_read("data/source_economics.json", {}), "sources")
    conflict_rows = _rows(_read("data/instruction_conflicts.json", {}), "conflicts")
    context_doc = _read("data/context_tasks.json", {})
    context_tasks = _rows(context_doc, "tasks")
    context_core = context_doc.get("core", []) if isinstance(context_doc, dict) else []
    doctrine_modules = (
        context_doc.get("doctrine_modules", {}) if isinstance(context_doc, dict) else {}
    )
    method_optimizer = _read("data/research_alpha_optimizer.json", {})
    external_frontier = _read("data/intelligence/external_frontier.json", {})
    proprietary_candidates = _rows(_read("data/proprietary_information.json", {}), "candidates")
    throughput_events = _jsonl("data/research_throughput_events.jsonl")
    coverage_cells = _rows(_read("data/open_world_coverage.json", {}), "cells")
    taxonomy_challenges = _rows(_read("data/coverage_taxonomy_challenges.json", {}), "challenges")
    return {
        "disclosure_intelligence": disclosure_rows or [{"status": "UNMEASURED"}],
        "proprietary_information_frontier": information_advantage_frontier(proprietary_candidates),
        "meaningful_research_throughput": meaningful_research_throughput(throughput_events),
        "open_world_coverage": open_world_coverage(coverage_cells, taxonomy_challenges),
        "external_intelligence": (
            external_frontier
            if isinstance(external_frontier, dict) and external_frontier
            else {"status": "UNMEASURED"}
        ),
        "search_strategy_evolution": (
            method_optimizer.get("search_strategy_evolution", {"status": "UNMEASURED"})
            if isinstance(method_optimizer, dict)
            else {"status": "UNMEASURED"}
        ),
        "causal_structures": [
            causal_structure(row.get("nodes", {}), row.get("links", []))
            for row in causal_rows
            if isinstance(row.get("nodes", {}), dict) and isinstance(row.get("links", []), list)
        ]
        or [{"status": "UNMEASURED"}],
        "source_information_economics": source_information_economics(source_economics_rows),
        "instruction_conflicts": [
            resolve_instruction_conflict(row.get("rules", []))
            for row in conflict_rows
            if isinstance(row.get("rules", []), list)
        ]
        or [{"status": "UNMEASURED"}],
        "context_packets": [
            context_packet(
                core=context_core if isinstance(context_core, list) else [],
                doctrine_modules=doctrine_modules if isinstance(doctrine_modules, dict) else {},
                domain=str(row.get("domain", "")),
                dynamic_state=row.get("dynamic_state", row),
            )
            for row in context_tasks
        ]
        or [{"status": "UNMEASURED"}],
        "ephemeral_specialists": [
            ephemeral_specialist(
                specialist_id=str(row.get("specialist_id", "UNKNOWN")),
                task_id=str(row.get("task_id", "UNKNOWN")),
                artifact=str(row.get("artifact", "")),
                useful_value=float(row.get("useful_value", 0.0)),
                cost=float(row.get("cost", 0.0)),
                completed=bool(row.get("completed")),
            )
            for row in specialist_events
        ],
        "input_health": {
            "study_status": study_status or {"status": "UNMEASURED"},
            "intelligence_cycle": intelligence_cycle or {"status": "UNMEASURED"},
            "research_review": research_review or {"status": "UNMEASURED"},
            "live_ladder": live_ladder or {"status": "UNMEASURED"},
            "completion_ledger": completion_status or {"status": "UNMEASURED"},
        },
        "actor_graph": actor_graph(_rows(_read("data/actor_events.json", {}), "events")),
        "evidence_fusion": (
            dependency_aware_evidence(values, corr) if values and corr else {"status": "UNMEASURED"}
        ),
        "creator_changes": creator_change_intelligence(claims),
        "semantic_compiler": (
            compile_public_strategy(claims[0].get("strategy", {}))
            if claims
            else {"status": "UNMEASURED"}
        ),
        "research_dag": research_dag_schedule(tasks),
        "concurrency_economics": concurrency_economics(
            worker_rows,
            work_waiting=len(tasks),
            available_slots=int(workers.get("available_slots", 0) or 0),
        ),
        "model_router": model_router(model_history, "research"),
        "workflow_distillation": distill_workflow(traces if isinstance(traces, list) else []),
        "doctrine_distillation": distill_doctrine(lessons),
        "missed_opportunity": missed_opportunity_tests(decisions),
        "prequential": prequential_score(forecasts),
        "operator_surface": operator_surface(live=live, blocked=blocked, queue=queue),
        "completion_supervisor": completion_supervisor(completion),
        "frontier_health": frontier_health(
            discovered=discovered,
            distinct_mechanisms=distinct,
            tested=tested,
            dispositioned=sum(status_counts.values()),
            survivors=survivors,
            portfolio_tested=sum(int(r.get("portfolio_positive", 0) or 0) for r in sources),
            deployed=sum(int(r.get("live_descendants", 0) or 0) for r in sources),
            queue_waiting=len(queue),
            eligible_capacity_idle=int(workers.get("eligible_idle", 0) or 0),
            blind_spots_open=sum(r.get("status") != "VERIFIED_COMPLETE" for r in completion),
            blind_spots_new=int(source.get("blind_spots_new", 0) or 0),
        ),
    }


def _production() -> dict[str, Any]:
    decisions = []
    execution_decisions = ROOT / "data" / "execution_decisions.jsonl"
    try:
        decisions = [
            json.loads(line)
            for line in execution_decisions.read_text("utf-8").splitlines()
            if line.strip()
        ]
    except (OSError, json.JSONDecodeError):
        decisions = []
    if not decisions:
        decisions = _rows(_read("data/decision_ledger.json", {}), "decisions")
    tape = []
    tape_path = ROOT / "data" / "moat" / "execution_tape" / "cashcarry_trades.jsonl"
    with contextlib.suppress(OSError, json.JSONDecodeError):
        tape = [
            json.loads(line) for line in tape_path.read_text("utf-8").splitlines() if line.strip()
        ]
    replay = _read("data/hot_path_replay.json", {})
    raw_manifest = _read("data/strategy_manifest.json", {}) or (
        replay.get("manifest", {}) if isinstance(replay, dict) else {}
    )
    manifest_spec = (
        raw_manifest.get("specification", raw_manifest) if isinstance(raw_manifest, dict) else {}
    )
    required = {"strategy_id", "signal", "allocator", "risk_policy", "execution_policy"}
    manifest = (
        strategy_manifest(
            manifest_spec,
            version=str(raw_manifest.get("version", "1")),
            parent_hash=raw_manifest.get("parent_hash"),
        )
        if required <= set(manifest_spec)
        else {"status": "UNMEASURED"}
    )
    venue = _read("data/venue_capabilities.json", {})
    requirements = (
        manifest_spec.get("venue_requirements", {}) if isinstance(manifest_spec, dict) else {}
    )
    preflight = _read("data/preflight_checks.json", {})
    modes = _read("data/reality_parity.json", {})
    timestamps = decisions[-1].get("timestamps", {}) if decisions else {}
    known_decisions = {
        "EXECUTED",
        "SIGNAL_REJECTED",
        "RISK_REJECTED",
        "COST_REJECTED",
        "CAPACITY_REJECTED",
        "EXECUTION_REJECTED",
        "VENUE_UNAVAILABLE",
        "MISSED_LATENCY",
    }
    latest_decision = str(decisions[-1].get("decision", "")) if decisions else ""
    hot_path = {"status": "UNMEASURED"}
    if isinstance(replay, dict) and replay.get("manifest") and replay.get("observation"):
        try:
            hot_path = deterministic_hot_path(
                replay["manifest"],
                replay["observation"],
                lambda observation, manifest: replay.get("signal", {}),
                lambda signal, manifest: replay.get("desired_order", {}),
                lambda desired, manifest: replay.get("risk_output", {}),
                lambda approved, manifest: replay.get("adapter_order", {}),
            )
            hot_path["status"] = "MEASURED"
        except (TypeError, ValueError) as exc:
            hot_path = {"status": "INVALID_INPUT", "reason": str(exc)}
    sample_decision = (
        decision_record(
            decision_id=str(decisions[-1].get("id", decisions[-1].get("decision_id", "unknown"))),
            decision=latest_decision,
            strategy_version=str(decisions[-1].get("strategy_version", "unknown")),
            state_snapshot=decisions[-1].get("state_snapshot") or {"legacy_record": True},
            rationale=str(decisions[-1].get("rationale", decisions[-1].get("reason", "legacy"))),
            desired_order=decisions[-1].get("desired_order"),
        )
        if decisions and latest_decision in known_decisions
        else {"status": "UNMEASURED"}
    )
    counterfactual_doc = _read("data/counterfactual_worlds.json", {})
    counterfactual = counterfactual_reality_gap(
        _rows(counterfactual_doc, "real"),
        _rows(counterfactual_doc, "synthetic"),
        features=(
            counterfactual_doc.get("features", [])
            if isinstance(counterfactual_doc, dict)
            and isinstance(counterfactual_doc.get("features"), list)
            else []
        ),
        max_preregistered_gap=(
            float(counterfactual_doc["max_preregistered_gap"])
            if isinstance(counterfactual_doc, dict)
            and isinstance(counterfactual_doc.get("max_preregistered_gap"), (int, float))
            else None
        ),
    )
    return {
        "deterministic_hot_path": hot_path,
        "decision_ledger": sample_decision,
        "strategy_manifest": manifest,
        "counterfactual_reality_gap": counterfactual,
        "self_footprint_moat": self_footprint_coverage([*decisions, *tape]),
        "controller_continuity": _read("data/controller_lease.json", {"status": "UNMEASURED"}),
        "reality_gap": reality_gap(
            modes.get("paper", []), modes.get("canary", []), modes.get("live", [])
        ),
        "preflight": preflight_contract(
            preflight.get("checks", preflight) if isinstance(preflight, dict) else {}
        ),
        "venue_capability": venue_eligibility(venue.get("capabilities", venue), requirements),
        "execution_tape_accounting": accounting_from_execution_tape(tape),
        "latency_metrics": latency_metrics(
            timestamps,
            half_life_seconds=float(decisions[-1].get("half_life_seconds", 0.0))
            if decisions
            else 0.0,
            edge_bps=float(decisions[-1].get("edge_bps", 0.0)) if decisions else 0.0,
        ),
        "autonomous_recovery": autonomous_recovery_plan(
            component="completion_program",
            failure_class="input_missing",
            capital_critical=False,
            legal_fallback="emit UNMEASURED and continue",
            attempts=0,
        ),
    }


def build() -> dict[str, Any]:
    return {
        "generated": datetime.now(tz=UTC).isoformat(),
        "authority": "MEASUREMENT_ONLY -- no orders, promotions or threshold changes",
        "validation": _validation(),
        "portfolio": _portfolio(),
        "research": _research(),
        "production": _production(),
    }


def main() -> int:
    report = build()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=1, default=str), "utf-8")
    print(f"completion-program: wrote {OUT.relative_to(ROOT)}; missing inputs remain UNMEASURED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

```

### scripts\vault_mcp_server.py
```python
#!/usr/bin/env python3
"""MCP stdio server exposing the vault to Claude -- layer 3 of the memory stack.

  layer 1  CLAUDE.md              the map        (always loaded, never changes)
  layer 2  .claude/desk-state.sh  the odometer   (live numbers, read at session start)
  layer 3  THIS                   the library    (208k lines, searched on demand)

WHY HAND-ROLLED JSON-RPC AND NOT THE MCP SDK. The SDK is not installed and cannot be: this clone is
network-policy-denied at the gateway (GAP row 91), so `pip install mcp` fails. The protocol needed
here is three methods over stdio, and implementing them in stdlib is smaller than the dependency
would be -- the same argument libs/execution/idempotency.py makes for staying stdlib on the order
path. It also means this server starts with no venv and no install step, which is what makes it
usable from a fresh clone.

PROTOCOL DISCIPLINE THAT IS EASY TO GET WRONG AND BREAKS THE TRANSPORT SILENTLY:
  * stdout carries JSON-RPC and NOTHING ELSE. One stray print corrupts the stream and the client
    reports a mysterious parse error rather than pointing at the print. All diagnostics go to
    stderr, which the client shows as server logs.
  * a NOTIFICATION (no `id`) MUST NOT get a response. Replying to `notifications/initialized` is
    the classic way to hang a handshake.
  * an unknown method returns a JSON-RPC error, never a crash -- a server that dies on an
    unrecognised method takes the whole connection with it.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from libs.research.vault_index import build, format_hits  # noqa: E402

PROTOCOL = "2024-11-05"
_INDEX: Any = None


def _index() -> Any:
    """Built once, lazily -- ~1,200 chunks parse in well under a second, but paying it on import
    would delay the handshake and a client that times out looks like a broken server."""
    global _INDEX
    if _INDEX is None:
        _INDEX = build()
        print(f"vault index: {len(_INDEX)} chunks", file=sys.stderr)
    return _INDEX


_TOOL = {
    "name": "vault_search",
    "description": (
        "Search this desk's institutional vault (docs/, ops/memory/ -- 208k lines of standing law, "
        "pre-registrations, gap register, playbooks, graveyard, deep sweeps). Use it BEFORE "
        "deciding anything the desk may already have decided, and before proposing research that "
        "may already be in the graveyard. LEXICAL (BM25), not semantic: an empty result means "
        "these TOKENS are absent, NOT that the question was never settled -- re-query with the "
        "vocabulary the document itself would use."),
    "inputSchema": {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "terms to search for"},
            "limit": {"type": "integer", "default": 8},
            "path": {"type": "string",
                     "description": "optional path substring filter, e.g. CONSTITUTION"},
        },
        "required": ["query"],
    },
}


def _handle(req: dict[str, Any]) -> dict[str, Any] | None:
    method, rid = req.get("method"), req.get("id")
    if rid is None:                      # notification -- answering one hangs the handshake
        return None
    if method == "initialize":
        return {"jsonrpc": "2.0", "id": rid, "result": {
            "protocolVersion": PROTOCOL,
            "capabilities": {"tools": {}},
            "serverInfo": {"name": "quant-vault", "version": "1.0.0"}}}
    if method == "tools/list":
        return {"jsonrpc": "2.0", "id": rid, "result": {"tools": [_TOOL]}}
    if method == "tools/call":
        args = (req.get("params") or {}).get("arguments") or {}
        try:
            hits = _index().search(str(args.get("query", "")),
                                   limit=int(args.get("limit", 8)),
                                   path_filter=str(args.get("path", "")))
            body = format_hits(hits)
        except Exception as exc:         # a tool error is reported IN BAND, never as a crash
            return {"jsonrpc": "2.0", "id": rid, "result": {
                "content": [{"type": "text", "text": f"vault_search failed: {exc!r}"}],
                "isError": True}}
        return {"jsonrpc": "2.0", "id": rid, "result": {
            "content": [{"type": "text", "text": body}]}}
    return {"jsonrpc": "2.0", "id": rid,
            "error": {"code": -32601, "message": f"method not found: {method}"}}


def main() -> int:
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
        except json.JSONDecodeError:
            continue                     # never die on one malformed frame
        resp = _handle(req)
        if resp is not None:
            sys.stdout.write(json.dumps(resp) + "\n")
            sys.stdout.flush()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

```
