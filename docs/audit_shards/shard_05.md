# AUDIT SHARD 5/24 -- seat qwen/qwen3.8-max-0902

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

### libs\ops\control_plane\reconciler.py
```python
"""THE RECONCILER -- the only organ allowed to say a component is HEALTHY.

    DESIRED STATE - OBSERVED STATE = RECONCILIATION WORK

Everything else in this package is a noun. This is the verb. Each pass:

    1. reads DESIRED state from the component registry (`desks/mt5/ops/components.py`),
    2. OBSERVES reality per component -- is it scheduled, is its process/lock there, has its
       watermark moved inside its SLA, are its outputs inside valid leases, did the consumers
       acknowledge them,
    3. assigns a state from the one model
       DECLARED -> STARTING -> HEALTHY -> DEGRADED -> STALE -> STALLED -> BROKEN -> REPAIRING
       -> HEALTHY, or -> QUARANTINED -> RETIRED,
    4. PLANS the repair work, and under --apply runs each actuator and proves its postcondition,
    5. publishes the twelve invariants and the one bit: DESK_CLOSED_AND_HEALTHY.

A COMPONENT CANNOT CERTIFY ITSELF. HEALTHY is assigned here, from observation, and nowhere else.
That is the whole reason this file exists rather than a `self_check()` on each organ: every
self-check this desk ever wrote reported the thing its author was thinking about, and the outages
came from the thing they were not.

FAIL-CLOSED. A required repair that times out makes the pass red and the process exit non-zero. A
parent never returns success while a required child failed. `complete: true` is impossible with
any required observation missing -- UNMEASURED is a verdict, never a pass (L1.28a).

THE OBJECTIVES, published per component rather than asserted:
    P(failure exists and the desk does not know) -> 0
    detection time + repair time <= the component's own SLA (spec.detection_sla_s + repair_sla_s)
"""
from __future__ import annotations

import hashlib
import json
import sys
import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from libs.ops.control_plane import actuators as act
from libs.ops.control_plane import edges as edg
from libs.ops.control_plane import fingerprints as fp
from libs.ops.control_plane import lease
from libs.ops.control_plane import watermarks as wm
from libs.ops.control_plane.specs import UNMEASURED, ComponentSpec, Registry

ROOT = Path(__file__).resolve().parents[3]
DESK = ROOT / "desks" / "mt5"
REPORT = DESK / "reports" / "CONTROL_PLANE.json"
QUARANTINE = DESK / "data" / "control_plane_quarantine.json"

#: The twelve invariants, in the order the report prints them. The first one that is not True is
#: the desk's first broken invariant, and it is named under the top-level bit.
INVARIANTS: tuple[str, ...] = (
    "component_coverage", "schedule_coverage", "runtime_coverage", "progress_coverage",
    "freshness", "wiring", "candidate_conservation", "forward", "release", "controller",
    "resource_loop", "closed_loop_proof",
)


def now_utc() -> datetime:
    return datetime.now(tz=UTC)


def epoch_id(at: datetime | str | None = None, salt: str = "") -> str:
    """The immutable id of one controller cycle.

    IMMUTABLE MEANS DERIVED FROM THE CYCLE, NOT FROM THE CLOCK AT READ TIME. Two organs certifying
    the same cycle must compute the same id from the same `at`, and a later pass must compute a
    different one -- which is what makes "a stale WIRING_CEO.json can never make a later pass
    green" enforceable instead of aspirational.
    """
    stamp = at.astimezone(UTC).isoformat(timespec="seconds") if isinstance(at, datetime) \
        else str(at or now_utc().isoformat(timespec="seconds"))
    digest = hashlib.sha256(f"{stamp}|{salt}".encode()).hexdigest()[:10]
    return f"E{stamp.replace('-', '').replace(':', '').replace('+0000', 'Z')[:15]}-{digest}"


def epoch_compatible(envelope: Mapping[str, Any] | None, epoch: str | None,
                     epoch_started_at: str | None = None) -> tuple[bool | None, str]:
    """May this artifact certify THIS epoch?

    Two ways to qualify, and only two: the envelope names the epoch, or it was created after the
    epoch began (an explicitly compatible watermark). Anything else is an older pass's report,
    and an older pass's report cannot make a later one green -- which is exactly how a green
    WIRING_CEO.json from the top of the hour certified a pass that had failed at :45.
    """
    if not envelope:
        return None, "no envelope: the artifact claims no epoch and no producer run"
    if not epoch:
        return None, "no epoch declared for this pass"
    if str(envelope.get("epoch_id")) == str(epoch):
        return True, f"stamped with epoch {epoch}"
    created = str(envelope.get("created_at") or "")
    if epoch_started_at and created:
        try:
            c = datetime.fromisoformat(created)
            s = datetime.fromisoformat(epoch_started_at)
        except ValueError:
            return False, f"unparseable timestamps ({created!r} vs {epoch_started_at!r})"
        if c.tzinfo is None:
            c = c.replace(tzinfo=UTC)
        if s.tzinfo is None:
            s = s.replace(tzinfo=UTC)
        if c >= s:
            return True, f"created {created} inside the epoch that began {epoch_started_at}"
        return False, (f"created {created}, BEFORE this epoch began at {epoch_started_at}: an "
                       f"earlier pass's report cannot certify a later one")
    return False, f"stamped with epoch {envelope.get('epoch_id')!r}, not {epoch}"


# ------------------------------------------------------------------------------- observation
@dataclass
class Observation:
    component_id: str
    state: str
    why: str
    details: dict[str, Any]
    criticality: str = "optional"

    def to_dict(self) -> dict[str, Any]:
        return {"component_id": self.component_id, "state": self.state,
                "criticality": self.criticality, "why": self.why, **self.details}


def _quarantined(root: Path | None = None) -> dict[str, str]:
    p = (root or ROOT) / "desks" / "mt5" / "data" / "control_plane_quarantine.json"
    try:
        doc = json.loads(p.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return {}
    rows = doc.get("quarantined") if isinstance(doc, dict) else None
    if isinstance(rows, dict):
        return {str(k): str(v) for k, v in rows.items()}
    return {}


def _lock_state(spec: ComponentSpec, locks: Path | None = None) -> dict[str, Any]:
    """Resident liveness, with the desk's own lock semantics.

    AN UNREADABLE LOCK IS A HELD LOCK. The residents hold a Windows byte-range lock on byte 0 of
    their own lock file, so reading it raises PermissionError WHILE THE PROCESS IS ALIVE. Reading
    that as death reported twenty-two healthy residents DEAD and "restarted" every fifteen
    minutes (measured 2026-09-17) -- the strongest evidence of life this desk has, read as the
    opposite.
    """
    stem = spec.component_id.split(":", 1)[1] if ":" in spec.component_id else spec.component_id
    base = locks or (DESK / "data" / "locks")
    p = base / f"{stem}.lock"
    if not p.exists():
        return {"lock": "FREE", "pid": None, "alive": False}
    try:
        first = p.read_text(encoding="utf-8", errors="replace").split()
    except OSError:
        return {"lock": "HELD", "pid": None, "alive": True}
    if first and first[0].isdigit():
        pid = int(first[0])
        return {"lock": "PID", "pid": pid, "alive": act.pid_alive(pid)}
    return {"lock": "STALE", "pid": None, "alive": False}


def observe(spec: ComponentSpec, *, now: datetime | None = None, root: Path | None = None,
            locks: Path | None = None, watermark_root: Path | None = None,
            quarantine: Mapping[str, str] | None = None,
            lineage: Path | None = None) -> Observation:
    """One component's state, from observation only. The ONLY place HEALTHY is assigned."""
    t = now or now_utc()
    base = root or ROOT
    q = dict(quarantine or {})
    details: dict[str, Any] = {"schedule": spec.schedule, "cadence_s": spec.cadence_s,
                               "max_silence_s": spec.max_silence_s,
                               "detection_sla_s": spec.detection_sla_s,
                               "repair_sla_s": spec.repair_sla_s, "sla_s": spec.sla_s}

    if spec.component_id in q:
        return Observation(spec.component_id, "QUARANTINED", q[spec.component_id], details,
                           spec.criticality)
    if not spec.scheduled:
        return Observation(
            spec.component_id, "DECLARED",
            f"{spec.component_id} exists and nothing in this repository schedules it",
            details, spec.criticality)

    if spec.kind == "resident":
        lk = _lock_state(spec, locks)
        details.update(lk)
        if not lk["alive"]:
            return Observation(spec.component_id, "BROKEN",
                               f"{spec.component_id} holds no live singleton lock "
                               f"({lk['lock']})", details, spec.criticality)

    prog = wm.advancing(spec.component_id, spec.max_silence_s, t, watermark_root)
    details["progress"] = prog
    if prog["state"] == "STALLED":
        return Observation(spec.component_id, "STALLED", prog["why"], details, spec.criticality)

    outs = [base / o for o in spec.outputs if o and not str(o).endswith("/")]
    fresh = lease.staleness(outs, t, base) if outs else {}
    details["outputs"] = fresh
    stale = [k for k, v in fresh.items() if v["verdict"] == "STALE"]
    if stale:
        return Observation(spec.component_id, "STALE",
                           f"{spec.component_id} owns {len(stale)} expired artifact(s): "
                           f"{stale[:3]}", details, spec.criticality)

    my_edges = edg.edges_for(producer=spec.component_id)
    if my_edges:
        rows = [edg.observe(e, t, lineage) for e in my_edges]
        details["edges"] = rows
        unobserved = [r for r in rows if not r["observed"]]
        if unobserved:
            return Observation(spec.component_id, "DEGRADED", unobserved[0]["why"], details,
                               spec.criticality)

    if prog["state"] == "UNMEASURED":
        return Observation(spec.component_id, "DEGRADED", prog["why"], details, spec.criticality)
    return Observation(spec.component_id, "HEALTHY", "", details, spec.criticality)


#: Which states are a defect the reconciler must plan work for.
BROKEN_STATES: frozenset[str] = frozenset({"BROKEN", "STALLED", "STALE"})


# ------------------------------------------------------------------------------------ plan
def plan(observations: Sequence[Observation],
         registry: Registry) -> list[dict[str, Any]]:
    """The reconciliation work: one row per component that is not where desired state says.

    DEGRADED IS NOT REPAIRED BY RESTARTING. A component whose watermark is UNMEASURED or whose
    consumer never acked is not sick -- it is UNWIRED, and the repair is a code or registry
    change, not a process kick. Planning a restart for it would be the old behaviour: a fixer
    firing forever at something a restart cannot fix.
    """
    rows: list[dict[str, Any]] = []
    for o in observations:
        if o.state not in BROKEN_STATES:
            continue
        spec = registry.get(o.component_id)
        if spec is None:
            continue
        rows.append({
            "component_id": o.component_id, "state": o.state, "why": o.why,
            "actuator": spec.restart_action,
            "criticality": o.criticality,
            "detection_sla_s": spec.detection_sla_s, "repair_sla_s": spec.repair_sla_s,
        })
    rows.sort(key=lambda r: (r["criticality"] != "required", r["component_id"]))
    return rows


def _actuator_for(spec: ComponentSpec) -> act.Actuator | None:
    """Turn a spec's declared `restart_action` into a real actuator. None when the action is not
    one this plane knows how to perform -- named in the record rather than silently skipped."""
    action = str(spec.restart_action or "")
    if action.startswith("restart:task:"):
        task = action.split("restart:task:", 1)[1]
        stem = (spec.component_id.split(":", 1)[1] if spec.kind == "resident"
                else spec.component_id)
        return act.restart_resident(spec.component_id, task, stem)
    if action.startswith("restart:resident:"):
        stem = action.split("restart:resident:", 1)[1]
        from desks.mt5.ops import components as comp  # pragma: no cover - box-side only
        task = comp.residents().get(stem, (UNMEASURED,))[0]
        return act.restart_resident(spec.component_id, task, stem)
    return None


def apply_plan(rows: Sequence[Mapping[str, Any]], registry: Registry, *, budget_s: float,
               runner: Any = None, sleeper: Any = None, clock: Any = None,
               locks: Path | None = None,
               watermark_root: Path | None = None) -> list[dict[str, Any]]:
    """Run each planned repair and PROVE it. Returns one record per attempt.

    A repair whose postcondition does not hold is recorded FAILED or UNPROVEN whatever the return
    code said -- the whole point of `actuators.run_actuator`.
    """
    tick = clock or time.monotonic
    t0 = tick()
    out: list[dict[str, Any]] = []
    for row in rows:
        spec = registry.get(str(row.get("component_id")))
        if spec is None:
            continue
        if tick() - t0 >= budget_s:
            out.append({"component_id": spec.component_id, "result": "SKIPPED",
                        "repaired": False, "why": "reconciliation budget exhausted"})
            continue
        a = _actuator_for(spec)
        if a is None:
            out.append({"component_id": spec.component_id, "result": "SKIPPED",
                        "repaired": False,
                        "why": (f"{spec.component_id} declares restart_action "
                                f"{spec.restart_action!r}, which this plane cannot perform")})
            continue
        ctx: dict[str, Any] = {"component_id": spec.component_id}
        if locks is not None:
            ctx["locks"] = locks
        if watermark_root is not None:
            ctx["watermark_root"] = watermark_root
        rec = act.run_actuator(a, ctx, apply=True, runner=runner, sleeper=sleeper, clock=clock)
        rec["component_id"] = spec.component_id
        rec["criticality"] = spec.criticality
        if not rec.get("repaired"):
            fp.record(f"{spec.component_id} repair {rec.get('result')}: {rec.get('why')}",
                      spec.component_id)
        out.append(rec)
    return out


# ------------------------------------------------------------------------------ invariants
def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return None


def _inv(ok: bool | None, measured: Any, why: str) -> dict[str, Any]:
    return {"ok": ok, "measured": measured, "why": why}


def invariants(observations: Sequence[Observation], registry: Registry, *,
               root: Path | None = None, census: Mapping[str, Any] | None = None,
               epoch: str | None = None, lineage: Path | None = None,
               now: datetime | None = None) -> dict[str, dict[str, Any]]:
    """The twelve, measured. `None` is UNMEASURED and never a pass."""
    base = root or ROOT
    desk = base / "desks" / "mt5"
    t = now or now_utc()
    by_id = {o.component_id: o for o in observations}
    required = list(registry.required())

    cov = dict(census or {})
    unclaimed = cov.get("executables_unclaimed")
    coverage = cov.get("coverage")
    inv_component = _inv(
        None if coverage is None else bool(coverage >= 1.0),
        {"executables": cov.get("executables"), "unregistered": len(unclaimed or []),
         "components": len(registry)},
        "" if coverage == 1.0 else
        f"{len(unclaimed or [])} executable(s) carry no ComponentSpec: {list(unclaimed or [])[:5]}"
        if unclaimed else "component census UNMEASURED")

    desired = [s for s in registry.all() if s.cadence_s is not None]
    unsched = [s.component_id for s in desired if not s.scheduled]
    inv_schedule = _inv(not unsched if desired else None,
                        {"desired": len(desired), "scheduled": len(desired) - len(unsched)},
                        "" if not unsched else
                        f"{len(unsched)} component(s) declare a cadence and no schedule: "
                        f"{unsched[:5]}")

    res = [s for s in registry.by_kind("resident") if s.criticality == "required"]
    dead = [s.component_id for s in res
            if by_id.get(s.component_id) and by_id[s.component_id].state == "BROKEN"]
    inv_runtime = _inv(not dead if res else None,
                       {"required_residents": len(res), "alive": len(res) - len(dead)},
                       "" if not dead else f"{len(dead)} required resident(s) hold no live lock: "
                                           f"{dead[:5]}")

    prog_rows = [(s, by_id.get(s.component_id)) for s in required]
    not_advancing = [s.component_id for s, o in prog_rows
                     if o is None or (o.details.get("progress") or {}).get("state")
                     != "ADVANCING"]
    inv_progress = _inv(not not_advancing if required else None,
                        {"required": len(required),
                         "advancing": len(required) - len(not_advancing)},
                        "" if not not_advancing else
                        f"{len(not_advancing)} required component(s) have no advancing watermark: "
                        f"{not_advancing[:5]}")

    stale_arts: list[str] = []
    unleased: list[str] = []
    missing_arts: list[str] = []
    for s in required:
        o = by_id.get(s.component_id)
        if o is None:
            continue
        for k, v in (o.details.get("outputs") or {}).items():
            if v.get("verdict") == "STALE":
                stale_arts.append(k)
            elif v.get("verdict") == "UNLEASED":
                unleased.append(k)
            elif v.get("verdict") == "MISSING":
                missing_arts.append(k)
    inv_fresh = _inv(not stale_arts if required else None,
                     {"expired_required_artifacts": len(stale_arts),
                      "unleased": len(unleased), "missing": len(missing_arts)},
                     "" if not stale_arts else
                     f"{len(stale_arts)} required artifact(s) outside their lease: "
                     f"{stale_arts[:5]}")

    loop = edg.closed_loop(edg.REQUIRED_EDGES, t, lineage)
    unconsumed = [r["edge"] for r in loop["edges"]
                  if r["state"] in ("UNACKED", "ACK_WEAK")]
    unproduced = [r["edge"] for r in loop["edges"] if r["state"] == "UNPRODUCED"]
    #: AN OUTPUT NOBODY PRODUCED IS NOT A CONSUMED OUTPUT, and it is not a clean one either. When
    #: every required edge is UNPRODUCED the consumption question has no subject, so the verdict
    #: is UNMEASURED -- reporting `0 unconsumed` there would be the denominator trick the laws
    #: forbid: perfect wiring because nothing was ever wired.
    inv_wiring = _inv(None if len(unproduced) == len(loop["edges"]) else not unconsumed,
                      {"unconsumed_required_outputs": len(unconsumed),
                       "unproduced_required_outputs": len(unproduced)},
                      (f"no required edge has a produced artifact yet: {len(unproduced)} "
                       f"producer(s) stamp no envelope, so consumption is UNMEASURED"
                       if len(unproduced) == len(loop["edges"]) else
                       "" if not unconsumed else
                       f"{len(unconsumed)} required output(s) nothing acknowledges: "
                       f"{unconsumed[:5]}"))

    cc = _read_json(desk / "reports" / "CANDIDATE_CONSERVATION.json")
    n_lost = (cc or {}).get("n_lost") if isinstance(cc, dict) else None
    inv_cand = _inv(None if n_lost is None else bool(int(n_lost) == 0),
                    {"n_lost": n_lost, "n_verdicts": (cc or {}).get("n_verdicts")
                     if isinstance(cc, dict) else None},
                    "CANDIDATE_CONSERVATION.json absent or unreadable: discovered vs accounted is "
                    "UNMEASURED" if n_lost is None else
                    ("" if int(n_lost) == 0 else f"{n_lost} discovered candidate(s) unaccounted"))

    wc = _read_json(desk / "reports" / "WIRING_CEO.json")
    cert = (wc or {}).get("certificates_without_clocks") if isinstance(wc, dict) else None
    n_cert = cert.get("n") if isinstance(cert, dict) else cert
    cert_env = lease.read_envelope(desk / "reports" / "WIRING_CEO.json")
    compat, compat_why = epoch_compatible(cert_env, epoch,
                                          None if epoch is None else cov.get("epoch_started_at"))
    inv_forward = _inv(
        None if n_cert is None or compat is False else bool(int(n_cert) == 0),
        {"certificates_without_clocks": n_cert, "epoch_compatible": compat},
        (f"the certificate census cannot certify this pass: {compat_why}" if compat is False else
         "WIRING_CEO.json absent or unreadable: certified-but-unclocked is UNMEASURED"
         if n_cert is None else
         ("" if int(n_cert) == 0 else f"{n_cert} certificate(s) hold no forward clock")))

    rel = _read_json(desk / "data" / "release_identity.json")
    rel_ok = rel.get("ok") if isinstance(rel, dict) else None
    inv_release = _inv(None if rel_ok is None else bool(rel_ok),
                       {"running_sha": (rel or {}).get("running_sha") if rel else None,
                        "release_sha": (rel or {}).get("release_sha") if rel else None,
                        "tested_sha": (rel or {}).get("tested_sha") if rel else None},
                       "release_identity.json absent: running = sealed = tested is UNMEASURED"
                       if rel_ok is None else
                       ("" if rel_ok else str((rel or {}).get("reason") or "")[:300]))

    mc = _read_json(desk / "reports" / "META_CONTROLLER.json")
    ep = (mc or {}).get("epoch") if isinstance(mc, dict) else None
    complete = ep.get("complete") if isinstance(ep, dict) else (mc or {}).get("epoch_complete") \
        if isinstance(mc, dict) else None
    inv_controller = _inv(None if complete is None else bool(complete),
                          {"epoch_id": (mc or {}).get("epoch_id") if isinstance(mc, dict)
                           else None,
                           "missing_kinds": ep.get("missing") if isinstance(ep, dict) else None},
                          "META_CONTROLLER.json absent or its epoch UNMEASURED"
                          if complete is None else
                          ("" if complete else
                           f"epoch incomplete: {ep.get('why') if isinstance(ep, dict) else ''}"))

    alloc_paths = ("desks/mt5/data/research_allocation.json",
                   "desks/mt5/data/forest_allocation.json")
    written = {p: (base / p).exists() for p in alloc_paths}
    acked = {p: len(lease.acks_for(p)) for p in alloc_paths}
    unobserved = [p for p in alloc_paths if not written[p] or acked[p] == 0]
    inv_resource = _inv(not unobserved,
                        {"written": written, "acknowledgements": acked},
                        "" if not unobserved else
                        f"{len(unobserved)} resource decision(s) written but unobserved "
                        f"downstream: {unobserved}")

    inv_closed = _inv(loop["closed"],
                      {"required_edges": loop["required"], "observed": loop["observed"],
                       "open": loop["open"][:6]},
                      "" if loop["closed"] else
                      f"{len(loop['open'])} mandatory edge(s) not observed inside valid leases")

    return {
        "component_coverage": inv_component,
        "schedule_coverage": inv_schedule,
        "runtime_coverage": inv_runtime,
        "progress_coverage": inv_progress,
        "freshness": inv_fresh,
        "wiring": inv_wiring,
        "candidate_conservation": inv_cand,
        "forward": inv_forward,
        "release": inv_release,
        "controller": inv_controller,
        "resource_loop": inv_resource,
        "closed_loop_proof": inv_closed,
    }


def first_broken(inv: Mapping[str, Mapping[str, Any]]) -> dict[str, Any] | None:
    for name in INVARIANTS:
        row = inv.get(name)
        if row is None:
            return {"invariant": name, "ok": None, "why": "not measured by this pass"}
        if row.get("ok") is not True:
            return {"invariant": name, "ok": row.get("ok"), "why": row.get("why"),
                    "measured": row.get("measured")}
    return None


# ----------------------------------------------------------------------------- the pass
def reconcile(*, registry: Registry | None = None, root: Path | None = None,
              apply: bool = False, budget_s: float = 600.0, epoch: str | None = None,
              now: datetime | None = None, locks: Path | None = None,
              watermark_root: Path | None = None, lineage: Path | None = None,
              runner: Any = None, sleeper: Any = None, clock: Any = None,
              census: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """One full reconciliation pass. Returns the document written to CONTROL_PLANE.json."""
    t = now or now_utc()
    base = root or ROOT
    reg = registry
    cen = dict(census or {})
    if reg is None:
        reg, cen = _desk_registry(base)
    ep = epoch or epoch_id(t)
    q = _quarantined(base)
    obs = [observe(s, now=t, root=base, locks=locks, watermark_root=watermark_root,
                   quarantine=q, lineage=lineage) for s in reg.all()]
    work = plan(obs, reg)
    repairs: list[dict[str, Any]] = []
    if apply and work:
        repairs = apply_plan(work, reg, budget_s=budget_s, runner=runner, sleeper=sleeper,
                             clock=clock, locks=locks, watermark_root=watermark_root)
    inv = invariants(obs, reg, root=base, census=cen, epoch=ep, lineage=lineage, now=t)
    broken = first_broken(inv)
    failed_required = [r for r in repairs
                       if r.get("criticality") == "required" and not r.get("repaired")]
    by_state: dict[str, int] = {}
    for o in obs:
        by_state[o.state] = by_state.get(o.state, 0) + 1
    doc: dict[str, Any] = {
        "at": t.isoformat(timespec="seconds"),
        "epoch_id": ep,
        "mode": "apply" if apply else "observe",
        "DESK_CLOSED_AND_HEALTHY": broken is None and not failed_required,
        "first_broken_invariant": broken,
        "invariants": inv,
        "components": len(reg),
        "states": by_state,
        "unhealthy": [o.to_dict() for o in obs if o.state not in ("HEALTHY", "DECLARED")][:200],
        "plan": work[:200],
        "repairs": repairs,
        "failed_required_repairs": [r.get("component_id") for r in failed_required],
        "registry_census": cen,
        "fingerprints": fp.summary(),
        "slas": _sla_table(reg),
        "state_model": ("DECLARED -> STARTING -> HEALTHY -> DEGRADED -> STALE -> STALLED -> "
                        "BROKEN -> REPAIRING -> HEALTHY, or -> QUARANTINED -> RETIRED; only the "
                        "reconciler assigns HEALTHY"),
        "rule": ("WIRED = scheduled AND executed AND progressed AND produced owned output AND "
                 "consumer acknowledged it; CLOSED LOOP = every required edge observed inside "
                 "valid freshness leases"),
    }
    return doc


def _sla_table(reg: Registry) -> dict[str, Any]:
    """detection + repair, published per component -- the objective, not an assertion."""
    rows = [{"component_id": s.component_id, "criticality": s.criticality,
             "detection_sla_s": s.detection_sla_s, "repair_sla_s": s.repair_sla_s,
             "sla_s": s.sla_s}
            for s in reg.required()]
    known = [r["sla_s"] for r in rows if r["sla_s"] is not None]
    return {"required": len(rows), "with_sla": len(known),
            "max_sla_s": max(known) if known else None,
            "unmeasured": [r["component_id"] for r in rows if r["sla_s"] is None][:20],
            "rows": rows[:200]}


def _desk_registry(root: Path) -> tuple[Registry, dict[str, Any]]:
    """The desk's registry, imported by path so this module works from the repo root and the box.

    A failure here is FATAL to the pass and says so: a reconciler that cannot read desired state
    has nothing to reconcile against, and returning an empty registry would publish a green
    report about a desk it never looked at.
    """
    import importlib.util
    path = root / "desks" / "mt5" / "ops" / "components.py"
    spec_ = importlib.util.spec_from_file_location("_cp_components", path)
    if spec_ is None or spec_.loader is None:
        raise RuntimeError(f"cannot load the component registry from {path}")
    mod = importlib.util.module_from_spec(spec_)
    sys.modules.setdefault("_cp_components", mod)
    spec_.loader.exec_module(mod)
    return mod.registry(root), mod.census(root)


def write(doc: Mapping[str, Any], path: Path | None = None,
          root: Path | None = None) -> dict[str, Any]:
    """Publish the report WITH its own lease, so the control plane is held to its own law."""
    target = path or REPORT
    reg, _ = _desk_registry(root or ROOT)
    spec_ = reg.get("component:control_plane")
    return lease.write_report(target, dict(doc), spec_ or "component:control_plane",
                              inputs=(), ttl="fifteen_minute",
                              epoch_id=str(doc.get("epoch_id") or UNMEASURED), root=root or ROOT)

```

### libs\research\lineage_dag.py
```python
"""Descent as a DAG, credit assigned to the step that failed, and the same idea refused twice.

WHY THIS EXISTS (principal blueprint, 2026-08-29)

Three separate ideas from the frontier collapse into one data structure, because all three need
the same thing: the full ancestry of a candidate, not just its parent.

  ALPHAPROBE -- ancestors are chosen by GLOBAL lineage information, not by parent performance.
      A branch whose parent looks mediocre can be the most fertile ground on the desk if its
      descendants keep surviving; a branch with a brilliant parent and forty dead children is
      exhausted. `retrieve_seeds` samples ancestors by posterior FERTILITY -- descendant survival
      per attempt -- so the search stops re-mining the one lucky parent.

  QUANTAALPHA -- credit assignment to the STEP, not the strategy. When a candidate fails, the
      useful question is not "was this strategy bad" but WHICH LINK broke: mechanism, observable,
      proxy, timing, implementation, parameterisation, or market transfer. Mutating the whole
      strategy after a timing failure throws away a sound mechanism. `assign_credit` records the
      failing step so `mutate_target` can name what to change.

  ALPHA JUNGLE -- frequent-subtree avoidance. If a thousand failed candidates all contain
      {momentum + volume acceleration + short horizon}, the desk should downweight that
      CONCEPTUAL SUBGRAPH rather than the exact formulas, which is the only version of the rule
      that generalises. `subtree_penalty` counts conceptual triples across the graveyard.

WHY THIS DESK NEEDS IT SPECIFICALLY. `discovered` produced 10,624 candidates for 7 certificates.
That is not a mechanism failing; it is one mechanism being re-parameterised ten thousand times
because nothing recorded that the previous 10,623 attempts explored the same ground. n_eff ~5.5
across 23 certificates is the same fact seen from the other end.

FAILURE CLASS DECIDES WHAT IS LEARNED, and this is the part that is easy to get backwards. An
`insufficient_power` failure teaches NOTHING about the mechanism -- the sample was small, which
is a fact about the test. Only validity failures reduce a branch's posterior. Getting this wrong
would abandon good mechanisms for having been tested too little, which is precisely how seven
families were labelled "confidently barren" on evidence from a validator later found broken in
four independent ways.
"""
from __future__ import annotations

import random
from collections import Counter, defaultdict, deque
from dataclasses import dataclass
from typing import Any

from libs.research.artifacts import POWER_FAILURES, VALIDITY_FAILURES

#: Research steps, in the order a candidate is built. `assign_credit` names ONE of these as the
#: failing link, and `mutate_target` changes only that one.
STEPS = ("mechanism", "observable", "proxy", "timing", "implementation",
         "parameterisation", "market_transfer")

#: Failure class -> the step it indicts. A mapping rather than a heuristic because the whole
#: value of credit assignment is that it is auditable: a reader must be able to check that a
#: `leakage` failure blamed the implementation and not the mechanism.
_CREDIT: dict[str, str] = {
    "invalid_mechanism": "mechanism",
    "no_effect": "mechanism",
    "leakage": "implementation",
    "execution_failure": "implementation",
    "cost_failure": "market_transfer",
    "redundant_alpha": "mechanism",
    "unstable_parameters": "parameterisation",
    "regime_instability": "timing",
    "insufficient_power": "",          # indicts NOTHING -- the test was small, not the idea
    "pbo": "parameterisation",
    "multiplicity": "parameterisation",
    "live_decay": "market_transfer",
}

#: A conceptual triple seen this many times among FAILURES is a rut, not a coincidence.
SUBTREE_RUT_AT = 25

#: Beta prior for branch fertility. Uniform is wrong here for the same reason it was wrong in the
#: funnel census -- an untried branch most likely resembles the desk's average branch, not a coin
#: flip -- but the prior is kept weak so a branch with real evidence dominates it quickly.
_PRIOR_STRENGTH = 3.0


@dataclass
class Node:
    """One artifact in the descent graph."""

    artifact_id: str
    hypothesis_id: str = ""
    parents: tuple[str, ...] = ()
    generation: int = 0
    mechanism: str = ""
    coordinate: str = ""
    concepts: tuple[str, ...] = ()          # conceptual components, for subtree avoidance
    mutation_operation: str = ""
    furthest_stage: str = "IDEA"
    survived: bool = False
    failure_class: str = ""
    failing_step: str = ""
    #: Live outcome, folded back when the sleeve retires or decays. THIS is what closes the loop:
    #: a family that certifies easily and then decays forward must lose future budget, and
    #: nothing else in the desk records that connection.
    live_decay_r: float | None = None


class LineageDAG:
    """The whole descent graph. Cycles are refused: descent is a DAG by definition."""

    def __init__(self) -> None:
        self.nodes: dict[str, Node] = {}
        self._children: dict[str, list[str]] = defaultdict(list)

    def add(self, node: Node) -> None:
        for p in node.parents:
            if p not in self.nodes:
                raise KeyError(
                    f"{node.artifact_id}: parent {p!r} is not in the graph. A node whose ancestry "
                    f"cannot be walked defeats the entire purpose -- global lineage retrieval, "
                    f"branch fertility and credit assignment all need the full path to the root.")
        if node.artifact_id in self.nodes:
            raise ValueError(f"{node.artifact_id} already present; artifacts are immutable")
        if self._would_cycle(node):
            raise ValueError(f"{node.artifact_id} would create a cycle; descent is a DAG")
        self.nodes[node.artifact_id] = node
        for p in node.parents:
            self._children[p].append(node.artifact_id)

    def _would_cycle(self, node: Node) -> bool:
        seen, q = set(), deque(node.parents)
        while q:
            cur = q.popleft()
            if cur == node.artifact_id:
                return True
            if cur in seen:
                continue
            seen.add(cur)
            q.extend(self.nodes[cur].parents if cur in self.nodes else ())
        return False

    def descendants(self, artifact_id: str) -> list[str]:
        out, q = [], deque(self._children.get(artifact_id, ()))
        seen = set()
        while q:
            cur = q.popleft()
            if cur in seen:
                continue
            seen.add(cur)
            out.append(cur)
            q.extend(self._children.get(cur, ()))
        return out

    def branch_stats(self, artifact_id: str) -> dict[str, Any]:
        """Fertility of a branch, counting only failures that actually indict it.

        `attempts_that_count` excludes power failures: a descendant that ran out of sample says
        nothing about whether this branch is fertile, and counting it would penalise exactly the
        branches the desk has explored least.
        """
        kids = self.descendants(artifact_id)
        survived = sum(1 for k in kids if self.nodes[k].survived)
        counted = [k for k in kids
                   if self.nodes[k].survived
                   or self.nodes[k].failure_class in VALIDITY_FAILURES]
        power_only = [k for k in kids if self.nodes[k].failure_class in POWER_FAILURES]
        decayed: list[float] = [d for k in kids
                                if (d := self.nodes[k].live_decay_r) is not None]
        return {
            "artifact_id": artifact_id,
            "descendants": len(kids),
            "survived": survived,
            "attempts_that_count": len(counted),
            "excluded_power_failures": len(power_only),
            "fertility": (survived / len(counted)) if counted else None,
            "mean_live_decay_r": (sum(decayed) / len(decayed)) if decayed else None,
            "n_live_observations": len(decayed),
        }


def assign_credit(failure_class: str) -> tuple[str, str]:
    """Which research STEP does this failure indict? Returns (step, why).

    An empty step means the failure indicts nothing -- and that is a real answer, not a gap.
    """
    if failure_class not in _CREDIT:
        return "", (f"failure class {failure_class!r} is unmapped; it indicts no step until "
                    f"someone decides which one it means. Guessing would attribute a failure to "
                    f"a component that was never at fault.")
    step = _CREDIT[failure_class]
    if not step:
        return "", (f"{failure_class} is a POWER failure: the sample was too small, which is a "
                    f"fact about the test and not about any research step. Nothing is mutated "
                    f"and no branch posterior moves (LAWS L1.49).")
    return step, (f"{failure_class} indicts the {step} step; mutate that and leave the rest of "
                  f"the trajectory intact")


def mutate_target(node: Node) -> tuple[str, str]:
    """What should change in the next descendant of this node?

    QuantaAlpha's surgical evolution: after a timing failure, change the timing and KEEP the
    mechanism. Randomly re-rolling the whole candidate discards the parts that worked and is why
    a parameter sweep produces ten thousand cousins of one idea.
    """
    step, why = assign_credit(node.failure_class)
    if not step:
        return "", why
    if step == "mechanism":
        return "mechanism", ("the mechanism itself is indicted -- do not mutate within this "
                             "branch, EXPLORE a different region of the semantic space")
    return step, why


def subtree_penalty(failed: list[Node]) -> dict[tuple[str, ...], dict[str, Any]]:
    """Conceptual triples that recur across failures -- ruts to downweight, not formulas to ban.

    Alpha Jungle's frequent-subtree avoidance, lifted from formula subtrees to CONCEPT triples so
    it generalises. Banning the exact expressions would be trivially evaded by renaming; the
    thing worth avoiding is the idea, and the idea is the combination of concepts.
    """
    counts: Counter[tuple[str, ...]] = Counter()
    for n in failed:
        # Power failures are not evidence that the CONCEPT is bad -- see the module docstring.
        if n.failure_class in POWER_FAILURES:
            continue
        cs = sorted(set(n.concepts))
        for i in range(len(cs)):
            for j in range(i + 1, len(cs)):
                for k in range(j + 1, len(cs)):
                    counts[(cs[i], cs[j], cs[k])] += 1
    return {t: {"failures": n, "penalty": round(1.0 / (1.0 + n / SUBTREE_RUT_AT), 4),
                "why": (f"this conceptual triple appears in {n} validity failures; the desk is "
                        f"re-exploring a rut, and the penalty applies to the IDEA rather than to "
                        f"any formula that expresses it")}
            for t, n in counts.items() if n >= SUBTREE_RUT_AT}


def crossover_candidates(dag: LineageDAG, *, seed: int, k: int = 5,
                         min_fertility: float = 0.2) -> list[dict[str, Any]]:
    """Pairs of lineages whose SEGMENTS are worth recombining. QuantaAlpha's trajectory crossover.

    THE UNIT IS A SEGMENT, NOT A STRATEGY. QuantaAlpha's contribution is that a research run is a
    trajectory -- mechanism, observable, timing, implementation -- and the useful recombination is
    "take THIS lineage's timing and THAT one's conditioning", not "average two strategies".
    Averaging two strategies produces a third strategy that inherits both parents' weaknesses;
    recombining segments produces one that inherits the two segments each parent got right.

    WHAT MAKES A PAIR ELIGIBLE, and each condition blocks a specific way this goes wrong:

      DIFFERENT MECHANISMS   two lineages of the same mechanism recombine into a third variant of
                             it. That is the parameter-sweep failure wearing an evolutionary
                             costume -- `discovered` produced 10,624 candidates that way.
      BOTH FERTILE           a barren parent contributes a segment with no evidence behind it, so
                             the child inherits a guess and a credential.
      DIFFERENT FAILING STEPS  this is the actual signal. If A fails on timing and B fails on
                             implementation, then A's implementation and B's timing are the parts
                             that were never indicted, and the child is built from two segments
                             each parent's own failure exonerated.

    A CHILD INHERITS NO CREDIBILITY. The returned spec carries `starts_at: IDEA` and the full
    validation bar. Evolutionary search that lets children inherit parental standing is how one
    mediocre strategy becomes five hundred "discoveries".
    """
    rng = random.Random(seed)  # noqa: S311 -- research sampling, not crypto
    fertile = []
    for aid, node in dag.nodes.items():
        st = dag.branch_stats(aid)
        f = st["fertility"]
        if f is not None and f >= min_fertility and node.mechanism:
            fertile.append((aid, node, f, st))
    if len(fertile) < 2:
        return []

    pairs: list[dict[str, Any]] = []
    for i in range(len(fertile)):
        for j in range(i + 1, len(fertile)):
            a_id, a, a_f, _ = fertile[i]
            b_id, b, b_f, _ = fertile[j]
            if a.mechanism == b.mechanism:
                continue
            a_step = a.failing_step or assign_credit(a.failure_class)[0]
            b_step = b.failing_step or assign_credit(b.failure_class)[0]
            if a_step and b_step and a_step == b_step:
                # Both broke at the same link; neither exonerates a segment the other needs.
                continue
            donate_a = b_step or "conditioning"
            donate_b = a_step or "timing"
            pairs.append({
                "parents": (a_id, b_id),
                "mechanisms": (a.mechanism, b.mechanism),
                "fertility": (round(a_f, 3), round(b_f, 3)),
                "take_from_a": donate_a,
                "take_from_b": donate_b,
                "starts_at": "IDEA",
                "why": (f"{a.mechanism} failed at {a_step or 'nothing recorded'} and "
                        f"{b.mechanism} at {b_step or 'nothing recorded'}; each parent's failure "
                        f"exonerates the segment the other needs. The child inherits ZERO "
                        f"credibility and faces the full bar."),
                "score": (a_f + b_f) / 2.0 * (1.0 + rng.random() * 0.1),
            })
    pairs.sort(key=lambda p: -p["score"])
    return pairs[:k]


def diversified_init(coordinates: list[str], k: int, *, seed: int) -> list[str]:
    """Seed a search with coordinates spread across REGIONS, not clustered in one.

    QuantaAlpha's "diversified planning initialization". A search seeded from k nearby starting
    points converges to one answer regardless of how good its evolution is -- the diversity has
    to be present at initialisation because no later operator creates it. Picks at most one
    coordinate per (event, direction) region before allowing a second anywhere.
    """
    rng = random.Random(seed)  # noqa: S311
    by_region: dict[tuple[str, str], list[str]] = defaultdict(list)
    for c in coordinates:
        parts = c.split("|")
        if len(parts) == 5:
            by_region[(parts[0], parts[3])].append(c)
    regions = sorted(by_region)
    rng.shuffle(regions)
    out: list[str] = []
    round_no = 0
    while len(out) < k and regions:
        progressed = False
        for r in regions:
            pool = by_region[r]
            if round_no < len(pool):
                out.append(pool[round_no])
                progressed = True
                if len(out) >= k:
                    break
        if not progressed:
            break
        round_no += 1
    return out


def retrieve_seeds(dag: LineageDAG, k: int, *, seed: int,
                   candidates: list[str] | None = None) -> list[tuple[str, float]]:
    """Sample `k` ancestors worth revisiting, by posterior fertility. AlphaPROBE's retriever.

    THOMPSON, NOT ARGMAX. Taking the top-k fertile branches would re-mine the same ground the
    moment one branch got lucky -- exactly the concentration that produced n_eff 5.5. Sampling
    from each branch's Beta posterior lets a barely-explored branch win sometimes and lose
    usually, which is what its uncertainty should buy it.

    `seed` is REQUIRED: an ancestor selection nobody can reproduce cannot be audited, and this
    decides where research effort goes.
    """
    rng = random.Random(seed)  # noqa: S311 -- Thompson sampling, not crypto
    pool = candidates if candidates is not None else list(dag.nodes)
    if not pool:
        return []

    # Empirical prior from the whole graph, for the same reason the funnel census uses one: an
    # unexplored branch most likely resembles the desk's average branch, not a coin flip.
    all_stats = [dag.branch_stats(a) for a in dag.nodes]
    tot_s = sum(s["survived"] for s in all_stats)
    tot_n = sum(s["attempts_that_count"] for s in all_stats)
    base = (tot_s / tot_n) if tot_n else 0.05
    base = min(max(base, 1e-3), 0.5)

    draws: list[tuple[str, float]] = []
    for aid in pool:
        s = dag.branch_stats(aid)
        a = _PRIOR_STRENGTH * base + s["survived"]
        b = _PRIOR_STRENGTH * (1 - base) + max(0, s["attempts_that_count"] - s["survived"])
        score = rng.betavariate(a, b)
        # LIVE DECAY IS THE LOOP CLOSING. A branch whose descendants certified and then decayed
        # forward has been telling the gauntlet something untrue; certification yield alone would
        # keep rewarding it forever.
        decay = s["mean_live_decay_r"]
        if decay is not None and decay < 0:
            score *= 1.0 / (1.0 + abs(decay))
        draws.append((aid, score))
    draws.sort(key=lambda t: -t[1])
    return draws[:k]


def branch_report(dag: LineageDAG) -> dict[str, Any]:
    """What the graph has learned. Fertility, ruts, and where the live loop has closed."""
    stats = [dag.branch_stats(a) for a in dag.nodes]
    measured = [s for s in stats if s["fertility"] is not None]
    failed = [n for n in dag.nodes.values() if not n.survived and n.failure_class]
    ruts = subtree_penalty(failed)
    with_live = [s for s in stats if s["n_live_observations"]]
    return {
        "nodes": len(dag.nodes),
        "branches_with_measurable_fertility": len(measured),
        "most_fertile": sorted(measured, key=lambda s: -(s["fertility"] or 0))[:5],
        "conceptual_ruts": len(ruts),
        "ruts": [{"concepts": list(t), **v} for t, v in
                 sorted(ruts.items(), key=lambda kv: -kv[1]["failures"])[:5]],
        "branches_with_live_evidence": len(with_live),
        "credit_assignment": dict(Counter(n.failing_step or "unattributed"
                                          for n in dag.nodes.values())),
        "note": ("power failures are excluded from every fertility denominator: an underpowered "
                 "descendant is evidence about the test, never about the branch (LAWS L1.49)"),
    }

```

### libs\research\mechanism_census.py
```python
"""MECHANISM SUPPLY CENSUS -- how many distinct ECONOMIC mechanisms has this desk actually tested?

THE DISTINCTION THIS MODULE EXISTS TO ENFORCE, and the only reason it is not a fourth family
counter. A FEATURE FAMILY is a way of writing a number down. An ECONOMIC MECHANISM is a claim
about WHO is on the other side of the trade and WHY THEY CANNOT STOP PAYING.

    "20-day breakout" and "50-day breakout" are ONE mechanism at two parameters. Both say: a
    trader under-reacted to information and must complete the same adjustment later at a worse
    price. Moving the window does not change the payer, so it does not change the mechanism --
    and a desk that counts it twice believes it has run two experiments when it has run one.

    "carry", "order-flow imbalance" and "capital-control barrier rent" are THREE mechanisms.
    The first is paid by a leveraged long who must post funding every eight hours; the second by
    an uninformed counterparty who fills an informed order and learns its information only after
    the price has moved; the third by a local saver who cannot move capital across a border and
    pays whoever holds the rail. No amount of evidence about one is evidence about another.

THE MEASUREMENT THAT MOTIVATED THIS. The desk ran its highest-power campaign to date -- 21
symbols x 5.6 years, pooled by mechanism so power at a true annualised Sharpe of 1.0 is ~70%
rather than ~5% -- and got 0 survivors from 44 pooled candidates (``reports/real_campaign.json``).
Power was not the binding constraint in that run. The HYPOTHESIS SET was: read this census's
own output and those 44 "mechanisms" resolve to a handful of economic classes, every one of them
derived from the same OHLCV tape. More price transformations cannot fix that, because a hundred
price transformations are one economic mechanism wearing a hundred hats. Nothing on the desk
measured this before, so the funnel looked BLOCKED AT THE GATE when it is STARVED AT THE TOP.

WHAT IT REPORTS. Per economic class: candidates tested, distinct constructions, distinct
parameterisations, best out-of-sample result, verdict distribution. Then the number that matters,
MECHANISM COVERAGE -- classes tested to adequate depth vs named-but-untested vs no candidate at
all -- and a DIVERSITY reading that stays LOW when volume rises inside classes the desk already
owns. Then the deliverable: the ranked list of highest-value untested classes and the specific
data each one needs.

HOW THE MERGE/SPLIT CALLS WERE MADE, since they set every number here. Two constructions are the
SAME class when they answer "who pays, and why can they not stop?" identically. That is why
`zscore_fade`, `vwap_reversion`, `shock_fade`, `wyckoff_spring`, `ict_sweep_reversal` and
`supply_demand_retest` are ONE class: every one of them says a trader was forced to transact NOW
-- by a stop, a margin call, an inventory limit -- and pays whoever warehouses the other side.
They differ only in where they claim the forced flow sits. Conversely `network_usage_demand` and
`holder_cost_basis_capitulation` are SPLIT despite sharing on-chain data, because adoption demand
and underwater-holder capitulation are different payers with different clocks. The taxonomy errs
toward SPLITTING wherever the payer is arguably different, which biases the diversity reading UP:
a low reading here is therefore conservative.

HONESTY RAILS, all three enforced mechanically and all three visible in the output.
  * A class with no evidence on disk is UNTESTED. It is never reported as failed, its verdict
    distribution is empty, and its best OOS is ``None`` rather than 0.0 -- because "we looked and
    found nothing" and "nobody has looked" are different states and only one of them is a result.
  * A runtime-only artifact that is absent from this checkout is NOT-READABLE-HERE. It is never
    counted as zero evidence, and the class it would have informed says so on its own row.
  * Nothing is classified that cannot be read. Every classification records the signature tokens
    that produced it, and any record matching no signature lands in ``unclassified`` where it is
    reported -- never silently dropped, never assigned to the nearest plausible class.

WHERE THIS SITS AMONG THE MACHINERY THAT ALREADY EXISTS, since none of it is duplicated here.
``libs/hypmax/invention.py`` refuses an interaction when both primitives share an INFORMATION
CLASS -- "same observation read twice" -- and that veto is the same idea one level down: this
module applies it to whole hypotheses instead of feature pairs, and asks about the PAYER rather
than the observation. ``libs/research/mechanism_fingerprint.py`` buckets an idea as
family/transform/horizon to catch trivial reparameterisation, and ``collapse_detector.py`` takes
entropy over those fingerprints per BATCH; both are correct and both are blind to the question
here, because a fingerprint's family axis is a FEATURE family -- ``trend`` and ``breakout``
fingerprint apart while being one economic mechanism. ``hypothesis_novelty`` answers "is this a
near-duplicate of a prior?", which is a different question from "which mechanism is it?", so it
is not imported: a candidate can be perfectly novel against every prior and still be the four
hundredth member of a class the desk has exhausted. The graveyard table parse is the same one
``scripts/screen_idle_axes.py`` uses for its novelty priors, hardened for the rows that grew in
after it.

ZERO AUTHORITY. This is a measurement instrument. It promotes nothing, blocks nothing, and
changes no gate, threshold or bar anywhere in the desk. Its own depth and scoring constants
(``DEPTH_MIN_*``, per-class plausibility/orthogonality, the availability ladder) are REPORTING
parameters of this census and confer no standing on any candidate whatsoever.

Pure stdlib -- no numpy, no pandas, no repo imports. The census must be readable on a box where
the research stack does not install.
"""

from __future__ import annotations

import json
import math
import re
from collections import Counter
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any

__all__ = [
    "CLASS_BY_ID",
    "DEPTH_MIN_CONSTRUCTIONS",
    "SCHEMA_VERSION",
    "TAXONOMY",
    "CandidateEvidence",
    "CensusReport",
    "ClassCensus",
    "Coverage",
    "DataAvailability",
    "DataRequirement",
    "Diversity",
    "GapRow",
    "MechanismClass",
    "SourceStatus",
    "Verdict",
    "census",
    "classify",
    "collect_evidence",
    "measure_diversity",
    "rank_gaps",
]

ROOT = Path(__file__).resolve().parents[2]

SCHEMA_VERSION = "1.0.0"

#: Distinct CONSTRUCTIONS that must each carry a CONCLUSIVE verdict before a class reads as
#: tested to adequate depth.
#:
#: DENOMINATED IN CONSTRUCTIONS, NEVER IN CANDIDATES, and that is the whole design. A bar written
#: as "n candidates" is satisfied by reparameterising one construction four times, which is
#: precisely the accounting error this module exists to remove -- the bar would certify depth the
#: desk does not have, using the exact mechanism that produced the illusion. Four rather than two
#: because construction variance in this asset class is measured LARGER than sampling variance
#: (GAP_REGISTER #71), so two constructions cannot separate "the mechanism is absent" from "both
#: of these ways of writing it down were wrong".
DEPTH_MIN_CONSTRUCTIONS = 4


# ------------------------------------------------------------------------------- vocabulary ----
class Verdict(StrEnum):
    """What actually happened to a candidate. The first four are TESTS; the rest are not."""

    SURVIVED = "SURVIVED"            # cleared every gate it was put through
    REFUTED = "REFUTED"              # tested on desk data, the mechanism did not pay
    ARTIFACT = "ARTIFACT"            # tested, and the apparent edge was contamination/look-ahead
    UNDERPOWERED = "UNDERPOWERED"    # tested, and the sample could not resolve the question
    NOT_MEASURED = "NOT-MEASURED"    # the run was blocked: no data, no tape, no licence
    EV_REJECTED = "EV-REJECTED"      # refused before compute by the EV gate -- never tested
    NAMED_ONLY = "NAMED-ONLY"        # written down in a queue or pre-registration -- never tested
    EXTERNAL_PRIOR = "EXTERNAL-PRIOR"  # killed by somebody else's evidence, not re-run here
    UNKNOWN = "UNKNOWN"              # a readable record whose status this census cannot normalise


#: Verdicts that mean a test was actually run against data.
TESTED_VERDICTS = frozenset({Verdict.SURVIVED, Verdict.REFUTED, Verdict.ARTIFACT,
                             Verdict.UNDERPOWERED})
#: Verdicts that mean the question was answered rather than merely attempted.
CONCLUSIVE_VERDICTS = frozenset({Verdict.SURVIVED, Verdict.REFUTED, Verdict.ARTIFACT})
#: Strength order, used when several records describe the same construction.
_VERDICT_STRENGTH: dict[Verdict, int] = {
    Verdict.SURVIVED: 6, Verdict.REFUTED: 5, Verdict.ARTIFACT: 4, Verdict.UNDERPOWERED: 3,
    Verdict.EXTERNAL_PRIOR: 2, Verdict.NOT_MEASURED: 1, Verdict.EV_REJECTED: 1,
    Verdict.NAMED_ONLY: 0, Verdict.UNKNOWN: 0,
}


class Coverage(StrEnum):
    """How well a class has been covered. UNTESTED states are never failure states."""

    TESTED_DEEP = "TESTED-DEEP"
    TESTED_SHALLOW = "TESTED-SHALLOW"
    NAMED_UNTESTED = "NAMED-UNTESTED"
    NO_CANDIDATE = "NO-CANDIDATE"
    NOT_READABLE_HERE = "NOT-READABLE-HERE"


class DataAvailability(StrEnum):
    ON_DISK = "ON-DISK"
    FREE_ACQUIRABLE = "FREE-ACQUIRABLE"
    RECORD_FORWARD = "RECORD-FORWARD"      # obtainable at zero cost, but only going forward
    PAID = "PAID"
    LICENCE_BLOCKED = "LICENCE-BLOCKED"
    UNAVAILABLE = "UNAVAILABLE"


#: How much a class's data situation discounts its value as a next target. Declared, not fitted.
_FEASIBILITY: dict[DataAvailability, float] = {
    DataAvailability.ON_DISK: 1.00,
    DataAvailability.FREE_ACQUIRABLE: 0.80,
    DataAvailability.RECORD_FORWARD: 0.55,
    DataAvailability.PAID: 0.30,
    DataAvailability.LICENCE_BLOCKED: 0.05,
    DataAvailability.UNAVAILABLE: 0.00,
}

#: How much room a class still has. A class already tested to depth is not a gap.
_DEPTH_DEFICIT: dict[Coverage, float] = {
    Coverage.NO_CANDIDATE: 1.00,
    Coverage.NAMED_UNTESTED: 1.00,
    Coverage.TESTED_SHALLOW: 0.60,
    Coverage.TESTED_DEEP: 0.00,
    Coverage.NOT_READABLE_HERE: 0.00,      # ranked separately; see rank_gaps
}


@dataclass(frozen=True)
class DataRequirement:
    """What testing this class would actually take."""

    datasets: tuple[str, ...]
    availability: DataAvailability
    note: str

    def to_dict(self) -> dict[str, Any]:
        return {"datasets": list(self.datasets), "availability": str(self.availability),
                "feasibility": _FEASIBILITY[self.availability], "note": self.note}


@dataclass(frozen=True)
class MechanismClass:
    """One economic mechanism: a named payer and the reason they cannot stop paying."""

    id: str
    name: str
    payer: str                     # who pays, and why they are compelled
    economic_definition: str       # the claim, stated so it could be wrong
    signatures: tuple[str, ...]    # tokens that identify this class in a candidate's own text
    plausibility: float            # 0..1, strength of the payer story BEFORE any desk evidence
    orthogonality: float           # 0..1, independence of its driver from what the desk already has
    data: DataRequirement
    priority: int = 0              # tie-break order; specific classes before generic price ones

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.id, "name": self.name, "payer": self.payer,
                "economic_definition": self.economic_definition,
                "plausibility": self.plausibility, "orthogonality": self.orthogonality,
                "data": self.data.to_dict()}


# --------------------------------------------------------------------------------- taxonomy ----
# ORDER IS PRIORITY ORDER and it is load-bearing. Data-specific classes come first so that a
# generic price word never outbids a specific economic one: "funding_momentum" is a carry idea
# that happens to contain the word "momentum", not a momentum idea that happens to mention
# funding. The two price-only classes sit last precisely because their vocabulary is the most
# promiscuous on the desk.
TAXONOMY: tuple[MechanismClass, ...] = (
    MechanismClass(
        id="capital_control_barrier_rent",
        name="capital-control / barrier rent",
        payer="a local holder who cannot move capital across a barrier -- capital controls, a "
              "frozen withdrawal rail, KYC tiers, sanctions -- and pays whoever holds the rail",
        economic_definition="A cross-venue or cross-border price gap that PERSISTS is rent on "
                            "whatever barrier is currently binding, not an inefficiency. Its "
                            "magnitude tracks barrier height; it is information about local "
                            "flow, and it is only harvestable by whoever owns the specific rail.",
        signatures=("kimchi", "capital control", "capital flight", "venue premium",
                    "fiat premium", "regional premium", "coinbase premium", "kr premium",
                    "try premium", "crossvenue", "cross venue", "withdrawal", "banzhuan",
                    "bithumb", "upbit", "coinone", "bitbank", "mercado", "barrier", "rail",
                    "jurisdiction", "stablecoin rent"),
        plausibility=0.75, orthogonality=0.70,
        data=DataRequirement(
            datasets=("per-venue local-currency quotes (Upbit/Bithumb/Binance TRY/BRL/CNY OTC)",
                      "the matching official FX fixing on the same instant"),
            availability=DataAvailability.FREE_ACQUIRABLE,
            note="Already screened across KR/JP/BR/TR/US venues and five documented eras; the "
                 "class is well covered rather than data-starved."),
        priority=0),
    MechanismClass(
        id="venue_subsidy_rent",
        name="venue subsidy / rebate rent",
        payer="the venue itself, paying a maker rebate or listing incentive to buy liquidity it "
              "cannot otherwise attract",
        economic_definition="When a venue pays negative maker fees, passive provision earns the "
                            "subsidy independent of any forecast. The edge is the rebate, it is "
                            "sized on the rebate, and it dies the day the schedule changes.",
        signatures=("rebate", "maker fee", "negative maker", "subsidy", "incentive programme",
                    "market maker program", "fee schedule", "liquidity mining"),
        plausibility=0.50, orthogonality=0.85,
        data=DataRequirement(
            datasets=("per-venue fee schedules with maker-rebate tiers and effective dates",
                      "own-fill records proving the rebate tier is reachable at the desk's size"),
            availability=DataAvailability.FREE_ACQUIRABLE,
            note="Fee schedules are public; the load-bearing missing input is evidence the desk "
                 "can reach the rebate tier, which only its own fills can supply."),
        priority=1),
    MechanismClass(
        id="orderbook_microstructure_state",
        name="order-book microstructure state",
        payer="an impatient taker who pays a spread the book's state had already widened, and a "
              "resting order that is picked off because it did not withdraw in time",
        economic_definition="The shape, replenishment and withdrawal dynamics of resting depth "
                            "reveal the intent behind the next print before the print happens. "
                            "It cannot be reconstructed after the fact at any price, which is "
                            "why it is the desk's only genuinely non-replicable data asset.",
        signatures=("order book", "orderbook", "book slope", "book depth", "microprice",
                    "replenish", "withdrawal rate", "resting stability", "effective spread",
                    "quote", "level 2", "l2 tick", "moat"),
        plausibility=0.80, orthogonality=0.90,
        data=DataRequirement(
            datasets=("L2 book snapshots recorded forward under data/moat/ (the recorder exists; "
                      "reports/moat_campaign.json reports the tape EMPTY)",
                      "Tardis.dev historical book snapshots as the paid substitute"),
            availability=DataAvailability.RECORD_FORWARD,
            note="Zero acquisition cost and unbounded replication cost, but it only accrues in "
                 "calendar time -- every day not recording is a day permanently unrecoverable."),
        priority=2),
    MechanismClass(
        id="volatility_risk_premium",
        name="volatility risk premium",
        payer="the option buyer, who pays for insurance systematically above the realised cost "
              "of the risk because he cannot bear the tail himself",
        economic_definition="Implied variance exceeds subsequent realised variance on average "
                            "because someone is paying to transfer tail risk. The premium is "
                            "compensation for bearing that tail, not a forecast.",
        signatures=("vrp", "variance risk premium", "volatility risk premium", "implied vol",
                    "option", "options", "skew", "risk reversal", "straddle", "gamma",
                    "deribit"),
        plausibility=0.85, orthogonality=0.80,
        data=DataRequirement(
            datasets=("Deribit public options chains (keyless): implied surface by expiry",
                      "realised variance on the identical clock",
                      "MORE VOL MARKETS -- the binding constraint named by the existing kill"),
            availability=DataAvailability.FREE_ACQUIRABLE,
            note="The graveyard's `options VRP` row is the campaign's BEST measured IC (+0.06) "
                 "and it died on BREADTH (2 markets), not on sign. The missing input is more "
                 "vol markets, not a better estimator."),
        priority=3),
    MechanismClass(
        id="mechanical_supply_release",
        name="mechanical supply release",
        payer="a vesting insider or a miner with near-zero cost basis who receives coins on a "
              "contractually fixed, publicly known date and whose fund lifecycle forces sale",
        economic_definition="A seller who cannot sell before receipt and must distribute after "
                            "it faces a demand curve that is not waiting for him. Forced seller, "
                            "immutable schedule -- the same shape as funding/carry.",
        signatures=("unlock", "vesting", "insider release", "emission", "halving", "miner sell",
                    "miner distribution", "supply schedule", "float", "cliff"),
        plausibility=0.80, orthogonality=0.75,
        data=DataRequirement(
            datasets=("data/unlock_events.json (ON DISK, already screened at one construction)",
                      "the vesting SCHEDULE as a time series, not a current snapshot -- the "
                      "screen artifact names 'snapshot not series' as its own defect",
                      "circulating-supply history to compute pct-of-float AT the event date"),
            availability=DataAvailability.ON_DISK,
            note="The one screen run reads NULL where powered and UNTESTABLE at the "
                 "mechanism-relevant float threshold, which is a depth problem, not a kill."),
        priority=4),
    MechanismClass(
        id="primary_market_creation_flow",
        name="primary-market creation flow",
        payer="an ETF authorised participant or stablecoin issuer who must buy spot to satisfy a "
              "creation, into whatever float exists on the day",
        economic_definition="Primary-market issuance is REALISED demand that has to be sourced "
                            "in the secondary market. The buyer is contractually committed and "
                            "cannot wait for a better price.",
        signatures=("etf", "creation", "redemption", "authorised participant", "stablecoin",
                    "mint", "issuance", "primary market", "net creations", "flow pressure"),
        plausibility=0.70, orthogonality=0.65,
        data=DataRequirement(
            datasets=("daily spot-ETF creation/redemption flows per issuer",
                      "on-chain stablecoin mint/burn events with issuer attribution",
                      "float/free-supply estimates to scale the flow"),
            availability=DataAvailability.FREE_ACQUIRABLE,
            note="EV-gated at 0.0191 and REOPENED on the 2026-07-31 gate recalibration, but no "
                 "screen artifact for it exists anywhere in this tree: it is named, not tested."),
        priority=5),
    MechanismClass(
        id="scheduled_event_diffusion",
        name="scheduled-event information diffusion",
        payer="a holder who learns of a listing, delisting or exchange announcement at a fixed "
              "public instant and cannot act before it",
        economic_definition="Information released at a known instant is absorbed over a window "
                            "rather than instantly, so the path after the instant is not a "
                            "martingale. The claim is about the ABSORPTION window, not the news.",
        signatures=("listing", "delisting", "announcement", "event study", "scheduled event",
                    "calendar event", "index inclusion"),
        plausibility=0.45, orthogonality=0.70,
        data=DataRequirement(
            datasets=("data/exchange_announcements.jsonl (ON DISK)",
                      "the announcement INSTANT, not the date -- a same-bar artifact otherwise",
                      "price at sub-daily resolution around the instant"),
            availability=DataAvailability.ON_DISK,
            note="Plausibility is held DOWN on purpose: this is the most latency-contested "
                 "event class in crypto and the desk is not a millisecond participant."),
        priority=6),
    MechanismClass(
        id="manager_skill_persistence",
        name="manager skill persistence",
        payer="nobody is compelled -- the claim is that some agents are persistently skilled and "
              "following them transfers their edge",
        economic_definition="Past risk-adjusted performance predicts future performance strongly "
                            "enough to pay for the copy latency. Selecting past winners must beat "
                            "selecting at random after the winner's-curse correction.",
        signatures=("copytrad", "copy trading", "leaderboard", "trader skill",
                    "skill persistence", "hyperliquid", "elite trader", "lead trader",
                    "top trader", "follow a lead"),
        plausibility=0.10, orthogonality=0.60,
        data=DataRequirement(
            datasets=("gapped formation/holding panels of verified on-chain trader records",),
            availability=DataAvailability.FREE_ACQUIRABLE,
            note="Tested four independent ways including the strongest available evidence class "
                 "(multi-year cryptographically verifiable records). Plausibility is set at the "
                 "floor BY that evidence -- this is a covered class, not a gap."),
        priority=7),
    MechanismClass(
        id="holder_cost_basis_capitulation",
        name="holder cost-basis capitulation",
        payer="a holder sitting on an unrealised loss who capitulates into whatever bid exists, "
              "or moves coins to the only venue where they can be sold",
        economic_definition="Aggregate cost basis relative to price is a state variable for "
                            "forced-ish selling. Coins arriving at exchanges are revealed "
                            "selling intent and should lead weaker returns.",
        signatures=("mvrv", "realized cap", "realised cap", "realized price", "cost basis",
                    "sopr", "exchange netflow", "netflow", "exchange inflow", "exchange outflow",
                    "nvt", "mayer multiple", "capitulation"),
        plausibility=0.55, orthogonality=0.60,
        data=DataRequirement(
            datasets=("Coin Metrics community daily (netflow_ntv, CapMVRVCur) -- 16y depth",
                      "PER-EXCHANGE decomposition rather than the aggregate, and/or intraday "
                      "granularity: the exact two escalations the exchange-netflow kill names"),
            availability=DataAvailability.FREE_ACQUIRABLE,
            note="Two constructions tested, both dead at daily aggregate frequency, and both "
                 "kills name the same unexplored escalation. Licence for production use of the "
                 "CM community CSV (CC BY-NC) is an open ruling, not a settled permission."),
        priority=8),
    MechanismClass(
        id="positioning_crowding_unwind",
        name="positioning / crowding unwind",
        payer="a leveraged trader whose position is liquidated by the venue at whatever price "
              "the book offers, having lost the choice of when to trade",
        economic_definition="Crowded leverage is an inventory that must be unwound on somebody "
                            "else's schedule. Observable positioning should therefore predict "
                            "the direction of the forced flow that follows.",
        signatures=("open interest", "oi", "oi divergence", "long short ratio", "ls contrarian",
                    "liquidation", "positioning", "crowding", "cot", "commitments of traders",
                    "hedging pressure", "leverage stress", "funding stress", "account ratio",
                    "position ratio", "smart money", "dumb money"),
        plausibility=0.65, orthogonality=0.50,
        data=DataRequirement(
            datasets=("Binance derivative-metrics archive (OI, long/short ratios) -- ON DISK",
                      "liquidation prints at trade granularity"),
            availability=DataAvailability.ON_DISK,
            note="Broadly covered: six-plus constructions across crypto positioning and 26 years "
                 "of CFTC COT, whose lagged-form test was pre-committed as a class-level gate."),
        priority=9),
    MechanismClass(
        id="informed_order_flow",
        name="informed order flow",
        payer="the uninformed counterparty who fills an informed order and learns its "
              "information only after the price has already moved",
        economic_definition="Signed aggressive flow carries information beyond its own price "
                            "impact. The test that matters is whether flow LEADS the return or "
                            "is merely CONCURRENT with it -- buying moves price by construction.",
        signatures=("order flow", "orderflow", "taker", "taker buy", "ofi", "vpin",
                    "aggressive buying", "absorption", "signed flow", "trade imbalance",
                    "block trade", "large print", "directional order flow"),
        plausibility=0.70, orthogonality=0.55,
        data=DataRequirement(
            datasets=("trade-level signed flow (Binance aggTrades / Hyperliquid fills)",
                      "data/idle_axis_screen.json -- the one screen carrying the "
                      "return-residualised absorption construction -- is NOT READABLE in this "
                      "checkout, so its cells cannot be counted here"),
            availability=DataAvailability.FREE_ACQUIRABLE,
            note="Every kill so far dies on the same defect: flow is concurrent with price and "
                 "fails de-contamination. The untested form is flow that is residualised against "
                 "the same-period return BEFORE it is asked to predict anything."),
        priority=10),
    MechanismClass(
        id="network_usage_demand",
        name="network usage / adoption demand",
        payer="nobody is compelled -- the claim is that real settlement demand for a "
              "supply-inelastic asset is absorbed slowly enough to be tradeable",
        economic_definition="Blockspace, fee and application usage is economic activity that "
                            "cannot be manufactured with leverage. Adoption-driven demand should "
                            "therefore lead returns at the horizon at which adoption operates.",
        signatures=("on chain", "onchain", "blockspace", "throughput", "transaction volume",
                    "tvl", "defi", "dex", "gas", "mempool", "active address", "hashrate",
                    "difficulty", "commit velocity", "developer", "github", "adoption"),
        plausibility=0.35, orthogonality=0.55,
        data=DataRequirement(
            datasets=("blockchain.info / DefiLlama / Coin Metrics activity aggregates",
                      "a WEEKLY-or-slower target clock: every kill in this class was run daily"),
            availability=DataAvailability.FREE_ACQUIRABLE,
            note="Well covered at the daily horizon and dead there. The residual question is "
                 "horizon, not data."),
        priority=11),
    MechanismClass(
        id="derivative_carry_basis",
        name="derivative carry / basis",
        payer="the leveraged long, who pays funding or a basis premium every interval to hold "
              "exposure he cannot or will not fund with cash",
        economic_definition="Perpetual funding and dated-future basis are a recurring payment "
                            "from levered longs to whoever supplies the spot leg. The payment is "
                            "observable in advance and the convergence is contractual.",
        signatures=("funding", "carry", "basis", "cash and carry", "cashcarry", "perp premium",
                    "roll yield", "contango", "backwardation", "term structure", "cme basis"),
        plausibility=0.85, orthogonality=0.30,
        data=DataRequirement(
            datasets=("Binance/BitMEX funding history and perp-spot basis -- ON DISK",),
            availability=DataAvailability.ON_DISK,
            note="The desk's only repeat-surviving family and its live book. Depth is real; the "
                 "open questions here are execution and capacity, not mechanism supply."),
        priority=12),
    MechanismClass(
        id="macro_liquidity_transmission",
        name="macro / liquidity transmission",
        payer="nobody is compelled -- the claim is that global liquidity and risk appetite reach "
              "a risk asset with a lag long enough to trade",
        economic_definition="Dollar, policy-liquidity and cross-asset risk states propagate into "
                            "the traded instrument (FX, gold, indices, energy) with a delay. The "
                            "tradeable form must be a standalone directional claim, not a "
                            "conditioning overlay on an existing book.",
        signatures=("macro", "dxy", "dollar strength", "fed", "walcl", "net liquidity",
                    "treasury", "rates", "spx", "ndx", "equity", "gold", "digital gold",
                    "risk regime", "crossasset", "cross asset", "risk off", "rotation"),
        plausibility=0.40, orthogonality=0.40,
        data=DataRequirement(
            datasets=("FRED public-domain series (WALCL/TGA/RRP, DXY, rates)",
                      "equity and metal index closes on a declared session clock"),
            availability=DataAvailability.FREE_ACQUIRABLE,
            note="The OVERLAY form of this class is dead three separate ways. Only the "
                 "standalone directional form is live, and it has been EV-gated rather than run."),
        priority=13),
    MechanismClass(
        id="attention_sentiment_overreaction",
        name="attention / sentiment overreaction",
        payer="the late retail buyer whose attention arrives after the move and who marks local "
              "crowding by arriving",
        economic_definition="Attention proxies peak at crowding rather than leading it, so the "
                            "tradeable claim is a FADE of attention spikes -- and it must beat "
                            "the fact that attention co-moves with the return it would predict.",
        signatures=("attention", "wikipedia", "pageview", "google trends", "search trends",
                    "sentiment", "fear", "greed", "social", "nlp", "twitter", "reddit"),
        plausibility=0.25, orthogonality=0.50,
        data=DataRequirement(
            datasets=("Wikipedia pageviews API (free)", "Fear&Greed index history"),
            availability=DataAvailability.FREE_ACQUIRABLE,
            note="Killed across five languages at daily horizon, which the kill note generalises "
                 "to the whole search-trends category. Weekly conditioning is the only residual."),
        priority=14),
    MechanismClass(
        id="cross_sectional_risk_premium",
        name="cross-sectional risk premium",
        payer="the investor who declines to hold a priced characteristic -- smallness, "
              "illiquidity, high idiosyncratic risk -- and pays whoever will",
        economic_definition="A characteristic commands a return spread in the cross-section "
                            "because holding it carries a risk somebody wants to avoid. The "
                            "spread must survive value-weighting and a liquid universe.",
        signatures=("xsec", "cross sectional", "cross section", "size effect", "low vol",
                    "lowvol", "illiquidity", "value factor", "anomaly", "factor model",
                    "characteristic sort", "ratio mining", "trading frictions"),
        plausibility=0.30, orthogonality=0.25,
        data=DataRequirement(
            datasets=("the existing perp panel -- ON DISK, no new data required",),
            availability=DataAvailability.ON_DISK,
            note="Two independent published crypto teams and one 452-anomaly equity replication "
                 "put this class's survival rate near zero once micro-caps and equal-weighting "
                 "are removed. Low plausibility is EARNED, not assumed."),
        priority=15),
    MechanismClass(
        id="relative_value_convergence",
        name="relative-value convergence",
        payer="whoever demanded immediacy in one leg of a pair whose legs are tied by a common "
              "factor, and pays the trader willing to hold the residual until it closes",
        economic_definition="Two instruments linked by a shared factor diverge on flow rather "
                            "than information, and the residual re-converges. The claim is about "
                            "the RESIDUAL; the shared factor is differenced away, not traded.",
        signatures=("intermarket", "relative value", "pairs trad", "pair trade", "cointegrat",
                    "statarb", "statistical arbitrage", "kalman", "hedge ratio", "leadlag",
                    "lead lag", "inverse reference", "spread convergence", "residual"),
        plausibility=0.55, orthogonality=0.45,
        data=DataRequirement(
            datasets=("the existing panel plus each reference leg's RANGE, not only its close",
                      "borrow/short cost per leg -- the RU evidence says this class dies on "
                      "costs and capacity, never on the estimator"),
            availability=DataAvailability.ON_DISK,
            note="The graveyard kills the Kalman REFINEMENT and states explicitly that pairs "
                 "trading itself is UNTESTED here. Two thin constructions exist in the campaign."),
        priority=16),
    MechanismClass(
        id="market_risk_premium",
        name="market risk premium",
        payer="the investor who will not hold undiversifiable market risk and pays whoever does",
        economic_definition="Holding the asset earns compensation for its non-diversifiable "
                            "risk. This is the benchmark every other mechanism must beat, and "
                            "harvesting it is an allocation decision rather than an edge.",
        signatures=("persistent long", "buy and hold", "risk premia", "risk premium harvest",
                    "beta exposure", "long run premium"),
        plausibility=0.90, orthogonality=0.05,
        data=DataRequirement(
            datasets=("the price panel already on disk",),
            availability=DataAvailability.ON_DISK,
            note="Real and already available to anyone. Orthogonality ~0 by definition: it is "
                 "the benchmark, so testing it more cannot widen the hypothesis set."),
        priority=29),
    MechanismClass(
        id="liquidity_provision_immediacy",
        name="liquidity provision / immediacy",
        payer="a trader forced to transact NOW -- a stop, a margin call, an index rebalance, an "
              "inventory limit -- who pays whoever will warehouse the other side",
        economic_definition="Price dislocates from value when immediacy demand exceeds the "
                            "inventory the market will hold, and reverts as inventory is laid "
                            "off. Every variant differs only in WHERE it claims the forced flow "
                            "sits: a z-score band, a VWAP stretch, a range extreme, a swept "
                            "swing high, or an unfilled institutional base.",
        signatures=("mean revers", "mean revert", "reversal", "fade", "zscore fade",
                    "vwap reversion", "shock fade", "wyckoff", "spring", "upthrust",
                    "liquidity sweep", "sweep reversal", "supply demand", "supply and demand",
                    "contrarian", "short term reversal", "olmar", "olps", "follow the loser",
                    "grid", "ladder", "liquidity provision", "market making", "inventory"),
        plausibility=0.55, orthogonality=0.10,
        data=DataRequirement(
            datasets=("the price panel already on disk",),
            availability=DataAvailability.ON_DISK,
            note="Tested to exhaustion on price alone. The only untested escalation needs the "
                 "book, which is a different class (orderbook_microstructure_state)."),
        priority=30),
    MechanismClass(
        id="price_continuation",
        name="price continuation / underreaction",
        payer="a trader who under-reacted to information and must complete the same adjustment "
              "later, at a worse price",
        economic_definition="Information diffuses into price slowly, so the sign of a past move "
                            "predicts the sign of the next one. Every window, every smoother and "
                            "every breakout definition is one parameterisation of that sentence.",
        signatures=("trend", "momentum", "breakout", "donchian", "ma cross", "moving average",
                    "continuation", "tsmom", "time series mom", "vwap trend", "displacement",
                    "market structure shift", "mss", "fair value gap", "fvg", "squeeze",
                    "vol trend", "drift", "ichimoku", "macd", "adx", "ema", "kama",
                    "ta indicator", "channel"),
        plausibility=0.35, orthogonality=0.03,
        data=DataRequirement(
            datasets=("the price panel already on disk",),
            availability=DataAvailability.ON_DISK,
            note="The desk's most-tested class by an order of magnitude and the one an "
                 "independent 2013-14 pre-registered natural experiment killed as well. Adding "
                 "candidates here cannot widen the hypothesis set."),
        priority=31),
    # ================================================================================ 2026-08-05
    # SIX CLASSES THE TAXONOMY HAD NEVER NAMED. The census can only rank what it has named, so an
    # absent class is not low-ranked -- it is INVISIBLE, and every coverage number the desk quotes
    # is computed against a denominator that silently excludes it. With the binding constraint
    # measured as DISTINCT MECHANISM SUPPLY (44 candidates covering 2.787 effective classes,
    # cross-mechanism N_eff 4.08 against the ~100 a weak-edge portfolio needs), widening what can
    # be ranked is worth more than another candidate inside an existing class.
    #
    # ADMISSION TEST APPLIED TO EACH, and it is the same one the charter uses: name a participant
    # compelled by a BALANCE SHEET, A COURT OR A RULE -- never by an opinion -- and say why they
    # cannot stop. A class whose "payer" is someone being wrong is a pattern, not a mechanism, and
    # does not belong here however well it would backtest.
    #
    # Each was checked against all twenty existing classes for genuine distinctness rather than
    # vocabulary overlap; the distinction is recorded in each entry because "isn't that just
    # X?" is the first question any of these will face.
    MechanismClass(
        id="index_reconstitution_flow",
        name="index reconstitution / rebalance flow",
        payer="a tracking fund, ETP or structured product whose MANDATE forces it to hold the "
              "index as published -- it must trade the reconstitution on the effective date at "
              "whatever price clears, and a manager who declines is running tracking error they "
              "are contractually not permitted to run",
        economic_definition="An index change is a dated, pre-announced, price-insensitive order "
                            "of known direction and approximately known size. Whoever supplies "
                            "that liquidity is paid for immediacy by a buyer who cannot wait and "
                            "cannot negotiate. The edge lives between announcement and effective "
                            "date and dies with the flow -- it is compensation for absorbing a "
                            "mandate, not a forecast of value.",
        signatures=("index inclusion", "index exclusion", "reconstitution", "rebalance date",
                    "index add", "index delete", "effective date", "tracking fund", "etp basket",
                    "index methodology", "quarterly review", "free float adjustment"),
        plausibility=0.80, orthogonality=0.75,
        data=DataRequirement(
            datasets=("index methodology documents with announcement and effective dates",
                      "constituent lists before and after each review",
                      "daily bars around the two dates for members and non-members"),
            availability=DataAvailability.FREE_ACQUIRABLE,
            note="NOT primary_market_creation_flow: that class is creation/redemption of wrapper "
                 "SHARES (flow into the vehicle). This is the vehicle's INTERNAL rebalance, on a "
                 "different date, with a different observable and an opposite sign convention. "
                 "The canonical forced-participant mechanism in equities, with a direct crypto "
                 "analogue in index products and exchange index composition; never screened."),
        priority=17),
    MechanismClass(
        id="treasury_cost_base_liquidation",
        name="producer treasury / fixed-cost-base liquidation",
        payer="a miner or validator carrying a FIAT cost base -- power, hosting, leased hardware, "
              "debt service -- against a coin-denominated revenue. Fiat obligations do not "
              "reschedule for a drawdown, so coin must be sold on the operator's calendar rather "
              "than on the market's, and hardest exactly when price is weakest",
        economic_definition="A structurally price-INSENSITIVE seller whose supply rises as margin "
                            "compresses. The flow is forced by a balance sheet, is observable "
                            "on-chain before it reaches an exchange, and is uncorrelated with any "
                            "view about value -- the seller would prefer not to sell.",
        signatures=("miner outflow", "miner treasury", "hashprice", "hash price", "difficulty "
                    "adjustment", "validator treasury", "staking reward sale", "producer "
                    "selling", "mining pool payout", "coinbase output", "cost of production"),
        plausibility=0.75, orthogonality=0.70,
        data=DataRequirement(
            datasets=("on-chain mining-pool payout addresses and their exchange-bound transfers",
                      "network difficulty and block subsidy for a cost-of-production proxy",
                      "public hashprice series"),
            availability=DataAvailability.FREE_ACQUIRABLE,
            note="NOT mechanical_supply_release: that is a SCHEDULE (vesting, emissions) known in "
                 "advance. This is a BALANCE-SHEET constraint whose timing is driven by the "
                 "operator's fiat obligations and margin, not by a calendar. NOT "
                 "network_usage_demand, which is adoption. The desk's own VRP pre-registration "
                 "already named this payer type -- 'a miner with a fixed fiat cost base' -- while "
                 "the taxonomy had no class to file it under."),
        priority=18),
    MechanismClass(
        id="estate_liquidation_distribution",
        name="estate / court-ordered liquidation and distribution",
        payer="a bankruptcy estate, receiver or liquidator under a COURT ORDER, and the creditors "
              "who receive an in-kind distribution they did not choose the timing of. A trustee "
              "sells because a court told them to and on the court's schedule; a creditor "
              "receiving coin after years of illiquidity is a highly motivated seller",
        economic_definition="A legally compelled, publicly docketed supply event with a knowable "
                            "size and an approximately knowable date. The compulsion is judicial "
                            "rather than economic, which is why it does not respond to price and "
                            "why the schedule survives changes in market conditions.",
        signatures=("estate", "bankruptcy", "trustee", "receiver", "liquidator", "creditor "
                    "distribution", "in-kind distribution", "court order", "chapter 11",
                    "civil rehabilitation", "mt gox", "ftx estate", "claims process"),
        plausibility=0.70, orthogonality=0.80,
        data=DataRequirement(
            datasets=("court dockets and trustee announcements with distribution dates",
                      "on-chain estate wallet balances and their outbound transfers",
                      "daily bars around each announced and executed tranche"),
            availability=DataAvailability.FREE_ACQUIRABLE,
            note="Distinct from mechanical_supply_release (protocol emissions) and from "
                 "holder_cost_basis_capitulation (a price-triggered decision). Here the trigger "
                 "is a filing. Rare events, so the honest expectation is a SMALL n -- which makes "
                 "it a class where the desk must state power before testing rather than after."),
        priority=19),
    MechanismClass(
        id="collateral_rule_deleveraging",
        name="collateral rule change / forced deleveraging",
        payer="a levered borrower whose position is closed by a RULE rather than by their own "
              "decision -- a raised haircut, a lowered LTV ceiling, a collateral-eligibility "
              "removal, an oracle re-mark or a liquidation-engine parameter change. The borrower "
              "cannot opt out: the venue closes the position for them",
        economic_definition="A supply or demand shock whose timing is set by a published "
                            "governance or risk-parameter change, not by price. Because the "
                            "parameter change is announced and the affected positions are visible "
                            "on-chain, the flow is forecastable in direction and approximate size "
                            "BEFORE it executes -- which is what distinguishes it from watching a "
                            "cascade after the fact.",
        signatures=("haircut", "loan to value", "ltv", "collateral factor", "liquidation "
                    "threshold", "collateral eligibility", "risk parameter", "oracle update",
                    "margin requirement change", "isolated mode", "debt ceiling"),
        plausibility=0.70, orthogonality=0.65,
        data=DataRequirement(
            datasets=("lending-protocol governance logs with parameter values and effective "
                      "blocks (Aave/Compound/Maker event logs via free RPC)",
                      "position-level collateral and debt snapshots around each change"),
            availability=DataAvailability.FREE_ACQUIRABLE,
            note="NOT positioning_crowding_unwind: that class is crowding measured from "
                 "positioning data and unwinding under its own weight. This one is RULE-DRIVEN "
                 "and typically PRE-ANNOUNCED, so it is forecastable ex ante rather than "
                 "diagnosable ex post -- the difference between a scheduled eviction and a fire."),
        priority=20),
    MechanismClass(
        id="settlement_expiry_mechanics",
        name="settlement / expiry hedging mechanics",
        payer="a dealer or market maker who is short optionality into a DATED settlement and must "
              "hedge to a fixing they do not control, plus every holder whose contract "
              "cash-settles against that same print. Neither chooses the timing: the contract "
              "specifies it",
        economic_definition="Delta and gamma hedging demand concentrates mechanically as a dated "
                            "expiry approaches, and its sign flips with strike placement. The "
                            "flow is a function of open interest and time, both public, rather "
                            "than of any view -- so it is predictable from the contract "
                            "specification alone.",
        signatures=("expiry", "expiration", "settlement fixing", "pin risk", "max pain",
                    "gamma exposure", "dealer gamma", "open interest at strike", "quarterly "
                    "settlement", "roll date", "final settlement price"),
        plausibility=0.60, orthogonality=0.60,
        data=DataRequirement(
            datasets=("option open interest by strike and expiry (Deribit public API)",
                      "settlement/fixing methodology and timestamps per venue",
                      "sub-daily bars spanning the settlement window"),
            availability=DataAvailability.FREE_ACQUIRABLE,
            note="NOT volatility_risk_premium: that class prices the PREMIUM paid for insurance. "
                 "This one is the mechanical HEDGING FLOW around a dated settlement, which exists "
                 "whether the premium is rich or cheap. The desk already collects the Deribit "
                 "chain for VRP, so the input largely exists and is unread for this purpose."),
        priority=21),
    MechanismClass(
        id="fiscal_calendar_flow",
        name="fiscal / tax calendar forced flow",
        payer="a holder compelled by a TAX OR ACCOUNTING deadline -- loss harvesting before a "
              "fiscal year end, a wash-sale window, a fund's reporting-date window dressing, a "
              "corporate treasury marking to a quarter end. The deadline is set by a statute or "
              "an accounting standard, so it does not move because the market did",
        economic_definition="A recurring, date-anchored flow whose direction is predictable from "
                            "the holder's prior-period P&L rather than from any forecast. It "
                            "reverses after the deadline passes, which is the falsifiable part: "
                            "no reversal means the flow was a preference, not a compulsion.",
        signatures=("tax loss harvesting", "wash sale", "fiscal year end", "financial year end",
                    "window dressing", "quarter end", "reporting date", "turn of the year",
                    "january effect", "capital gains deadline"),
        plausibility=0.55, orthogonality=0.70,
        data=DataRequirement(
            datasets=("jurisdiction fiscal-year-end and wash-sale rule dates",
                      "daily bars with prior-period return to sign the expected flow",
                      "a control cohort not subject to the same deadline"),
            availability=DataAvailability.FREE_ACQUIRABLE,
            note="The weakest payer story of the six and priced accordingly -- crypto's holder "
                 "base is jurisdictionally mixed, so the compelled fraction is unknown and may be "
                 "small. Recorded anyway: L1.49 says a weak mechanism is not a dead one, and an "
                 "UNNAMED class cannot even be ranked as weak."),
        priority=22),
    # ================================================================================ 2026-08-18
    # SIX MT5-NATIVE CLASSES THE TAXONOMY HAD NEVER NAMED. The desk's universe is now the full
    # MT5/Fusion market (FX, gold, metals, indices, energy, share CFDs), and every forced-flow
    # mechanism below was INVISIBLE to a census whose vocabulary was crypto: FX carry is a sovereign
    # rate differential, not perp funding; COT producer hedging is a physical short, not a miner
    # dump; a benchmark fix is a mandated order, not an inferred sweep. Each is data-specific, so it
    # sorts before the generic price tail (priorities 29-31, bumped up to open this band). All are
    # testable on FREE data the desk already reaches or can pull keyless: FRED rate curves, the
    # CFTC COT weekly file, EIA inventories, and the desk's own MT5 session bars.
    MechanismClass(
        id="fx_carry_rate_differential",
        name="FX carry / interest-rate differential",
        payer="the holder short the higher-yielding currency, who is contractually debited the "
              "overnight interest-rate differential every day the position is held -- a swap / "
              "rollover charge the broker MUST apply and that the position cannot avoid without "
              "closing -- and pays it to whoever is long the carry and warehouses the crash risk",
        economic_definition="Two sovereign short rates differ, and a position spanning them earns "
                            "or pays that differential as a daily rollover independent of any "
                            "price forecast. The excess return is compensation for bearing the "
                            "crash risk that periodically unwinds the carry trade violently, so "
                            "the payoff is negatively skewed by construction rather than by luck.",
        signatures=("carry", "carry trade", "interest rate differential", "rate differential",
                    "rollover", "swap points", "swap long", "swap short", "forward points",
                    "covered interest parity", "cip", "funding currency", "yield differential"),
        plausibility=0.80, orthogonality=0.75,
        data=DataRequirement(
            datasets=("FRED sovereign policy / short rates per currency (keyless, free)",
                      "the desk's FX spot bars for the two legs on the same clock",
                      "broker swap_long/swap_short for the realised (not theoretical) daily cost"),
            availability=DataAvailability.FREE_ACQUIRABLE,
            note="NOT derivative_carry_basis: that class's payer is a crypto perpetual long paying "
                 "an 8-hour funding rate to a shorter; this payer is short a sovereign yield and "
                 "pays a rollover set by two central banks' policy rates -- a different balance "
                 "sheet, a different clock, and an unwind driven by rate-regime shifts."),
        priority=23),
    MechanismClass(
        id="central_bank_event_surprise",
        name="central-bank / macro event surprise",
        payer="every holder forced to reprice at a scheduled, known-instant policy decision or "
              "top-tier data print (FOMC, ECB, BoE, NFP, CPI): the surprise -- actual minus what "
              "the futures curve had priced -- lands on whoever was mandated to hold through the "
              "release and cannot pre-position past their risk limit; it moves in one clock tick",
        economic_definition="The market prices a consensus before a scheduled release; the gap "
                            "between outcome and that priced consensus drives an immediate jump "
                            "plus a documented multi-hour drift as slower participants complete "
                            "the adjustment. The tradeable object is the SURPRISE, constructed "
                            "point-in-time, not the announced level.",
        signatures=("nfp", "non-farm", "non farm payrolls", "cpi", "fomc", "ecb", "boe", "boj",
                    "rate decision", "central bank", "economic calendar", "surprise", "consensus",
                    "data release", "post-announcement drift", "eco surprise", "macro print"),
        plausibility=0.75, orthogonality=0.70,
        data=DataRequirement(
            datasets=("FRED releases plus a free economic-calendar consensus (keyless)",
                      "fed-funds / STIR futures-implied probabilities to build the surprise",
                      "the desk's FX / metal / index bars stamped around each release"),
            availability=DataAvailability.FREE_ACQUIRABLE,
            note="NOT macro_liquidity_transmission: that class is a slow, ambient drift of "
                 "dollar and rates liquidity into a risk asset with NO event; this one is an "
                 "instantaneous, scheduled, known-clock repricing whose signal is the surprise "
                 "around a single timestamp, not a lagged spillover."),
        priority=24),
    MechanismClass(
        id="session_fix_liquidity",
        name="session structure / benchmark-fix liquidity",
        payer="the passive fund and the corporate hedger mandated to execute at a published "
              "benchmark fixing they do not control -- the 4pm WMR London FX fix, the LBMA gold "
              "fix -- who MUST submit a price-insensitive, time-concentrated order at the window "
              "regardless of level, and pays the warehouser who takes the other side of that flow",
        economic_definition="A benchmark fix concentrates mandated, price-insensitive order flow "
                            "into a fixed daily window, so the flow imbalance predicts a "
                            "systematic pre-fix drift and post-fix reversal; and the session-open "
                            "and -close handoffs (Tokyo to London to New York) carry their own "
                            "liquidity-regime transitions that a 24-hour tape would smear out.",
        signatures=("session", "london fix", "wmr", "4pm fix", "lbma", "gold fix", "asian session",
                    "london open", "new york session", "tokyo session", "session open",
                    "fixing", "benchmark fix", "rollover time", "session close"),
        plausibility=0.65, orthogonality=0.75,
        data=DataRequirement(
            datasets=("the desk's own intraday FX / metal bars stamped to session and fix windows",
                      "published fix times and methodology (free)"),
            availability=DataAvailability.FREE_ACQUIRABLE,
            note="NOT liquidity_provision_immediacy: that class fades a generic forced flow "
                 "wherever a price band says it sits; this one is anchored to a CALENDARED, "
                 "published fixing whose participants and clock are known in advance, so the "
                 "forced flow is scheduled rather than inferred from price."),
        priority=25),
    MechanismClass(
        id="commodity_inventory_supply",
        name="commodity inventory / convenience yield",
        payer="the physically-short consumer or the long forced to finance storage when "
              "inventories swing -- a refiner, a utility, a merchant -- whose hedging book MUST "
              "rebalance to a published inventory print (EIA petroleum status, LME/COMEX "
              "warehouse stocks) and pays whoever holds the convenience-yield term structure",
        economic_definition="Physical inventory levels and their surprises drive the convenience "
                            "yield and the front-of-curve spread; a consumer short the physical "
                            "must pay up when stocks draw and the curve backwardates. The signal "
                            "is the inventory surprise, and it is orthogonal to every "
                            "financial-flow mechanism the desk already names.",
        signatures=("inventory", "eia", "petroleum status", "warehouse stocks", "convenience yield",
                    "contango", "backwardation", "storage", "wasde", "crop report", "lme stocks",
                    "comex warehouse", "physical supply", "stock draw", "stock build"),
        plausibility=0.65, orthogonality=0.85,
        data=DataRequirement(
            datasets=("EIA weekly petroleum status (free public file)",
                      "USDA/WASDE and LME/COMEX warehouse stocks (free)",
                      "the desk's energy / metal bars on the release clock"),
            availability=DataAvailability.FREE_ACQUIRABLE,
            note="NOT mechanical_supply_release: that class is a crypto insider or miner dumping "
                 "vested coins with a near-zero cost basis on a fixed unlock date; this is a "
                 "physical-commodity inventory surprise repricing a convenience yield -- a storage "
                 "economy, not a vesting schedule."),
        priority=26),
    MechanismClass(
        id="overnight_gap_risk_premium",
        name="overnight / weekend gap-risk premium",
        payer="the holder who cannot flatten across a market closure -- an FX book into the "
              "weekend, an index or share CFD overnight -- who either pays for gap insurance or is "
              "compensated for warehousing the jump risk a closed market cannot price "
              "continuously; the closure is a hard calendar fact the position cannot trade around",
        economic_definition="Instruments with defined session closes accumulate information while "
                            "shut and re-open at a gap, so the close-to-open jump carries a risk "
                            "premium distinct from intraday realised variance, fat-tailed around "
                            "weekends, holidays and scheduled closures.",
        signatures=("gap", "overnight", "weekend gap", "holiday gap", "close to open",
                    "opening gap", "session close", "gap risk", "jump risk", "overnight hold",
                    "carry across weekend", "monday gap", "gap fill"),
        plausibility=0.60, orthogonality=0.70,
        data=DataRequirement(
            datasets=("the desk's own bars split into close-to-open jumps versus intraday range",
                      "the session / holiday calendar per instrument (free)"),
            availability=DataAvailability.FREE_ACQUIRABLE,
            note="NOT volatility_risk_premium: that class sells implied-minus-realised variance "
                 "through options; this one prices the discrete close-to-open JUMP of an "
                 "instrument that literally stops trading -- a gap risk 24/7 crypto does not have "
                 "and that needs no options market to measure."),
        priority=27),
    MechanismClass(
        id="producer_hedging_flow",
        name="commodity producer hedging flow (COT commercial)",
        payer="the commodity producer contractually forward-selling output to lock a fiat margin "
              "-- a gold miner, an oil driller, a farmer -- whose hedge is a mandated, "
              "price-insensitive supply visible in the CFTC commercial category, and who MUST "
              "roll and add to it on the operator's calendar regardless of where price sits",
        economic_definition="Commercial hedgers carry a structural short driven by production "
                            "schedules, not by a forecast; the extremes and changes of their COT "
                            "position mark where price-insensitive supply is entering, which "
                            "predicts the speculative side's forced accommodation.",
        signatures=("producer hedging", "commercial hedger", "cot commercial", "cot",
                    "commitments of traders", "forward selling", "producer short",
                    "hedging pressure", "commercial net", "swap dealer", "merchant hedge",
                    "gold miner hedge", "disaggregated cot"),
        plausibility=0.65, orthogonality=0.80,
        data=DataRequirement(
            datasets=("CFTC COT commercial / hedger category (free weekly file, already parsed "
                      "for the desk's positioning work)",
                      "the desk's futures / CFD bars for gold, silver, energy and indices"),
            availability=DataAvailability.FREE_ACQUIRABLE,
            note="NOT treasury_cost_base_liquidation: that class is a crypto miner selling block "
                 "rewards to cover a fiat electricity bill, read on-chain; this is a TradFi "
                 "commodity producer forward-hedging output, read in the CFTC commercial COT "
                 "category -- a hedging programme, not an on-chain payout."),
        priority=28),
)

CLASS_BY_ID: dict[str, MechanismClass] = {c.id: c for c in TAXONOMY}


# ------------------------------------------------------------------- construction ground truth --
# READ FACTS, not guesses. Each key is a construction name that appears verbatim in
# reports/real_campaign.json; each value is the class its IMPLEMENTATION in
# libs/autodiscovery/generators.py places it in. This map exists because the campaign's declared
# FAMILY label is occasionally not the economic mechanism: `drift_proxy` is filed under the
# `carry` family and is implemented as `momentum_positions(lookback=200)` -- generators.py labels
# it "PROXY: no swap/rate data" in its own edge_source string. Classifying it as carry would
# credit the desk with a carry test it never ran, which is exactly the error this census exists
# to remove. Anything absent from this map falls through to signature classification.
CONSTRUCTION_CLASS: dict[str, str] = {
    "ma_cross": "price_continuation",
    "time_series_mom": "price_continuation",
    "donchian": "price_continuation",
    "squeeze_breakout": "price_continuation",
    "vol_trend": "price_continuation",
    "vol_onset_trend": "price_continuation",
    # Hawkes intensity gates WHEN to be positioned; the DIRECTION is still the trend's, so this is
    # price_continuation however sophisticated the gate. Filing a self-exciting model under a
    # higher-orthogonality class would credit the desk with breadth it has not bought.
    "hawkes_vol_expansion": "price_continuation",
    "vwap_trend": "price_continuation",
    "ict_mss_follow": "price_continuation",
    "ict_fvg_follow": "price_continuation",
    "session_open_mom": "price_continuation",
    "drift_proxy": "price_continuation",
    "zscore_fade": "liquidity_provision_immediacy",
    "vwap_reversion": "liquidity_provision_immediacy",
    "shock_fade": "liquidity_provision_immediacy",
    "wyckoff_spring": "liquidity_provision_immediacy",
    "ict_sweep_reversal": "liquidity_provision_immediacy",
    "supply_demand_retest": "liquidity_provision_immediacy",
    "intermarket_difference": "relative_value_convergence",
    "inverse_reference": "relative_value_convergence",
    "persistent_long": "market_risk_premium",
    "funding_stress_reversal": "positioning_crowding_unwind",
    # Same payer as funding_stress_reversal -- the crowded levered book -- measured from the
    # CFTC COT weekly positioning print rather than the venue funding print. Two meters of one
    # mechanism, not two mechanisms; the census says so and the divergence register agrees.
    "cot_positioning_reversal": "positioning_crowding_unwind",
    # The library's FIRST spec whose family label and census class agree on carry. Distinct from
    # `funding_stress_reversal` on the same input: that one FADES extreme funding (its payer is a
    # trader liquidated on the venue's schedule), this one COLLECTS ordinary funding (its payer is
    # a levered long buying convenience). Same series, opposite sign, different payer -- which is
    # the sharpest available test of whether "different mechanism" means anything on this desk.
    "funding_carry": "derivative_carry_basis",
    # THE ELEVEN DISCRETIONARY RULES, declared by construction rather than left to keyword luck.
    # Measured 2026-08-15: `classify()` returned None for H4, H5, H9 and H10 -- the desk's own
    # taxonomy could not place four of the rules it was trading, so they fell to UNCLASSIFIED and
    # the breadth report counted them as an undeclared mechanism. Declaring the map is cheaper and
    # far safer than broadening signature regexes, which would silently re-file other candidates.
    "H1_structural_fade": "liquidity_provision_immediacy",
    "H2_volume_breakout": "price_continuation",
    "H3_ict": "price_continuation",
    # H4 is volume-at-price reversion from TRADE PRINTS -- "unaccepted prices revert to where
    # volume traded" is an immediacy claim, not an information one. It reads the tape, but reading
    # the tape is not the same as trading its information, and filing it beside H5 would credit
    # the desk with two informed-flow tests when it has one.
    "H4_auction_value": "liquidity_provision_immediacy",
    # H5 IS the informed-flow test: signed aggressive volume diverging from price. The class's own
    # note says every kill so far died because flow was CONCURRENT with price -- a divergence is
    # precisely the non-concurrent form, which makes this the untested construction, not a repeat.
    "H5_cvd_divergence": "informed_order_flow",
    "H6_wyckoff": "liquidity_provision_immediacy",
    "H7_vwap_reversion": "liquidity_provision_immediacy",
    "H8_supply_demand": "liquidity_provision_immediacy",
    "H9_opening_range": "price_continuation",
    "H10_vol_compression": "price_continuation",
    "H11_band_fade": "liquidity_provision_immediacy",
    # forward clocks whose names carry no census vocabulary
    "cny_premium": "capital_control_barrier_rent",
    "oi_divergence": "positioning_crowding_unwind",
    "ls_contrarian": "positioning_crowding_unwind",
    "producer_margin_stress": "treasury_cost_base_liquidation",
    "walcl_reserve_impulse": "macro_liquidity_transmission",
    "defi_utilisation": "network_usage_demand",
    "stablecoin_supply_momentum": "primary_market_creation_flow",
}


# --------------------------------------------------------------------------- classification ----
_WS = re.compile(r"\s+")


def _hay(text: str) -> str:
    """Normalise a candidate's text so `ma_cross`, `ma-cross` and `MA cross` all read alike."""
    low = (text or "").lower()
    low = re.sub(r"[^a-z0-9]+", " ", low)
    return _WS.sub(" ", low).strip()


_SIG_RE: dict[str, tuple[tuple[str, re.Pattern[str]], ...]] = {
    c.id: tuple((s, re.compile(r"(?<![a-z0-9])" + re.escape(s) + r"(?![a-z0-9])"))
                for s in c.signatures)
    for c in TAXONOMY
}


def classify(text: str, *, construction: str | None = None) -> tuple[str | None, tuple[str, ...]]:
    """Return ``(class_id, matched_signatures)``; ``(None, ())`` when nothing matches.

    A construction present in ``CONSTRUCTION_CLASS`` short-circuits: that map is read from the
    implementation, and an implementation beats a keyword every time. Otherwise the class with
    the MOST matched signatures wins, ties broken by taxonomy priority so that a specific
    economic vocabulary always outbids the promiscuous price-only one.

    Returning ``None`` is a first-class outcome. A record this function cannot place is reported
    as unclassified rather than pushed into the nearest plausible class -- a fabricated
    classification would show up as coverage the desk does not have.
    """
    if construction is not None:
        declared = CONSTRUCTION_CLASS.get(construction)
        if declared is not None:
            return declared, ("construction:" + construction,)
    hay = _hay(text)
    if not hay:
        return None, ()
    best: tuple[int, int, str] | None = None
    matched: dict[str, tuple[str, ...]] = {}
    for cls in TAXONOMY:
        hits = tuple(sig for sig, rx in _SIG_RE[cls.id] if rx.search(hay) is not None)
        if not hits:
            continue
        matched[cls.id] = hits
        key = (-len(hits), cls.priority, cls.id)
        if best is None or key < best:
            best = key
    if best is None:
        return None, ()
    return best[2], matched[best[2]]


# ------------------------------------------------------------------------- verdict normalising --
#: Phrases that say the kill came from SOMEBODY ELSE'S evidence rather than a desk test: a
#: published paper, an era forum thread, a community attribution study. Checked before anything
#: else, because those write-ups are full of ordinary kill vocabulary and would otherwise read as
#: desk results -- inflating tested depth with experiments this desk never ran.
_EXTERNAL_BASIS_MARKERS: tuple[str, ...] = (
    "external literature", "pre emptive kill", "pre emptively killed", "pre emptive",
    "era evidence", "era instance", "era provenance", "killed at source", "refuted at source",
    "not by us", "not a desk backtest", "killed by the replies", "external prior",
)

#: Phrases that must beat the un-negated token they contain. "NOT REFUTED, NOT SUPPORTED --
#: UNMEASURED at the threshold that carries the mechanism" contains the substring "refuted" and
#: means the opposite of it; reading that row as a kill is the exact failure this census forbids.
_NEGATIONS: tuple[tuple[str, Verdict], ...] = (
    ("not refuted", Verdict.UNDERPOWERED),
    ("not supported", Verdict.UNDERPOWERED),
    ("licence forbids", Verdict.NOT_MEASURED),
    ("not a technical failure", Verdict.NOT_MEASURED),
)

#: Longest-token-first so `no_edge_daily` is not swallowed by `no_edge`.
#:
#: `survived` IS DELIBERATELY ABSENT. SURVIVED is only ever set structurally -- every gate on the
#: record cleared -- and never inferred from prose, so no write-up can talk a dead candidate into
#: the survivor column by containing the word. (It nearly did: a kill note reporting that "4 of
#: 15,256 arbitrage signals survived manual review" read as a surviving hypothesis.)
_VERDICT_TOKENS: tuple[tuple[str, Verdict], ...] = (
    ("screen underpowered", Verdict.UNDERPOWERED),
    ("underpowered", Verdict.UNDERPOWERED),
    ("untestable", Verdict.UNDERPOWERED),
    ("could not tell", Verdict.UNDERPOWERED),
    ("insignificant", Verdict.REFUTED),
    ("lookahead artifact", Verdict.ARTIFACT),
    ("look ahead", Verdict.ARTIFACT),
    ("timing artifact", Verdict.ARTIFACT),
    ("position overlap artifact", Verdict.ARTIFACT),
    ("unstable artifact", Verdict.ARTIFACT),
    ("regime artifact", Verdict.ARTIFACT),
    ("contaminated", Verdict.ARTIFACT),
    ("screen weak", Verdict.REFUTED),
    ("no edge daily", Verdict.REFUTED),
    ("no edge", Verdict.REFUTED),
    ("no economics", Verdict.REFUTED),
    ("no predictive power", Verdict.REFUTED),
    ("mechanism refuted", Verdict.REFUTED),
    ("wrong sign", Verdict.REFUTED),
    ("wrong orthogonality", Verdict.REFUTED),
    ("costs killed edge", Verdict.REFUTED),
    ("no breadth", Verdict.REFUTED),
    ("narrow breadth", Verdict.REFUTED),
    ("overfit", Verdict.REFUTED),
    ("crowded", Verdict.REFUTED),
    ("redundant", Verdict.REFUTED),
    ("null", Verdict.REFUTED),
    ("refuted", Verdict.REFUTED),
    ("no data", Verdict.NOT_MEASURED),
    ("unmeasured", Verdict.NOT_MEASURED),
    ("blocked", Verdict.NOT_MEASURED),
    ("forward clock", Verdict.NOT_MEASURED),
    ("screen interesting", Verdict.UNDERPOWERED),
)


def _external_basis(text: str) -> bool:
    """True when the write-up says the kill came from outside this desk."""
    hay = _hay(text)
    return any(marker in hay for marker in _EXTERNAL_BASIS_MARKERS)


def _verdict_from_text(text: str, *, default: Verdict = Verdict.UNKNOWN) -> Verdict:
    hay = _hay(text)
    if not hay:
        return default
    if _external_basis(hay):
        return Verdict.EXTERNAL_PRIOR
    for phrase, verdict in _NEGATIONS:
        if phrase in hay:
            return verdict
    for token, tok_verdict in _VERDICT_TOKENS:
        if token in hay:
            return tok_verdict
    return default


def _strongest(a: Verdict, b: Verdict) -> Verdict:
    return a if _VERDICT_STRENGTH[a] >= _VERDICT_STRENGTH[b] else b


# -------------------------------------------------------------------------------- evidence -----
@dataclass(frozen=True)
class CandidateEvidence:
    """One readable record of one hypothesis. ``construction`` is the idea; ``params`` the knob."""

    candidate_id: str
    class_id: str | None
    construction: str
    params: str
    verdict: Verdict
    source: str
    matched_on: tuple[str, ...] = ()
    oos_sharpe: float | None = None
    note: str = ""
    #: Parameter settings this ONE record covers. A campaign row is one setting; a screen
    #: artifact that swept 27 cells is 27 -- and 27 settings of one construction is still one
    #: construction, which is why the depth bar never reads this field.
    n_parameterisations: int = 1

    @property
    def tested(self) -> bool:
        return self.verdict in TESTED_VERDICTS

    def to_dict(self) -> dict[str, Any]:
        return {"candidate_id": self.candidate_id, "class_id": self.class_id,
                "construction": self.construction, "params": self.params,
                "verdict": str(self.verdict), "source": self.source,
                "matched_on": list(self.matched_on), "oos_sharpe": self.oos_sharpe,
                "n_parameterisations": self.n_parameterisations, "note": self.note}


@dataclass(frozen=True)
class SourceStatus:
    """Whether an evidence source could be read HERE, and how much it carried."""

    path: str
    readable: bool
    n_records: int
    detail: str

    def to_dict(self) -> dict[str, Any]:
        return {"path": self.path,
                "status": "READABLE" if self.readable else "NOT-READABLE-HERE",
                "n_records": self.n_records, "detail": self.detail}


def _slug(text: str) -> str:
    head = re.split(r"\s*[(—\-]{1,2}\s", text.strip(), maxsplit=1)[0]
    return re.sub(r"[^a-z0-9]+", "_", head.lower()).strip("_")[:70] or "unnamed"


def _load_json(path: Path) -> Any | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text("utf-8"))
    except (OSError, ValueError):
        return None


# -- reader 1: the pooled campaign -----------------------------------------------------------
CAMPAIGN_PATH = "reports/real_campaign.json"


def read_campaign(root: Path) -> tuple[list[CandidateEvidence], SourceStatus]:
    """Read the pooled-by-mechanism rows: the desk's maximum-power evidence, one row per idea.

    The POOLED view is used rather than the per-symbol one on purpose. Forty symbols running one
    mechanism is one hypothesis with forty symbols of evidence, not forty hypotheses -- counting
    it the other way is the same error at the symbol axis that this module removes at the
    parameter axis.
    """
    path = root / CAMPAIGN_PATH
    doc = _load_json(path)
    if not isinstance(doc, dict):
        return [], SourceStatus(CAMPAIGN_PATH, False, 0,
                                "absent or unparseable in this checkout")
    pooled = doc.get("pooled_by_mechanism")
    rows = pooled.get("rows") if isinstance(pooled, dict) else None
    if not isinstance(rows, list):
        return [], SourceStatus(CAMPAIGN_PATH, True, 0,
                                "readable, but carries no pooled_by_mechanism.rows")
    out: list[CandidateEvidence] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        name = str(row.get("name", ""))
        parts = name.split(":")
        construction = parts[1] if len(parts) > 2 else _slug(name)
        params = parts[2] if len(parts) > 2 else ""
        family = str(row.get("family", ""))
        cid, matched = classify(f"{construction} {family}", construction=construction)
        failed = row.get("failed_gates")
        n_failed = len(failed) if isinstance(failed, list) else 0
        oos = row.get("oos_sharpe")
        out.append(CandidateEvidence(
            candidate_id=name or construction,
            class_id=cid, construction=construction, params=params,
            verdict=Verdict.REFUTED if n_failed else Verdict.SURVIVED,
            source=CAMPAIGN_PATH, matched_on=matched,
            oos_sharpe=float(oos) if isinstance(oos, int | float) else None,
            note=f"declared family '{family}'; failed {n_failed} gate(s)"))
    return out, SourceStatus(CAMPAIGN_PATH, True, len(out),
                             f"{len(out)} pooled mechanisms at maximum campaign power")


# -- reader 2: the graveyard -------------------------------------------------------------------
GRAVEYARD_PATH = "docs/graveyard.md"
#: A graveyard verdict cell that is nothing but an expected-value number.
_EV_CELL = re.compile(r"ev \d")
#: Prose sections that are NOT hypothesis kills and must not be counted as candidates.
_GRAVEYARD_NON_KILL = ("cross-era synthesis", "code / capability retirements",
                       "external-literature priors")


def _graveyard_verdict(verdict_text: str, tag: str) -> Verdict:
    """Read a graveyard row's disposition, TAG FIRST.

    Three rules, in this order, and the order is the whole point:

      1. AN EXTERNAL BASIS ANYWHERE IN THE ROW WINS. The desk's own graveyard declares two
         non-desk kill bases -- `external-literature` and era-provenance -- and rows carrying
         them describe somebody else's experiment in ordinary kill vocabulary.
      2. A VERDICT CELL THAT IS AN EV NUMBER ("EV 0.0005") is an EV-GATE disposition taken before
         a single research hour was spent. Those rows still carry ordinary kill tags, and reading
         them as tests would credit the desk with experiments it explicitly declined to run.
      3. THE TAG BEATS THE PROSE. The tag is the desk's own one-word classification of the death;
         the verdict cell is a narrative that routinely mentions several failure modes. Reading
         the prose first mislabelled `unstable_artifact` as merely underpowered, because its
         write-up happens to say "underpowered" about one cohort of the experiment.
    """
    if _external_basis(f"{tag} {verdict_text}"):
        return Verdict.EXTERNAL_PRIOR
    if _EV_CELL.match(_hay(verdict_text)) is not None:
        return Verdict.EV_REJECTED
    by_tag = _verdict_from_text(tag, default=Verdict.UNKNOWN)
    if by_tag is not Verdict.UNKNOWN:
        return by_tag
    return _verdict_from_text(verdict_text, default=Verdict.REFUTED)


def read_graveyard(root: Path) -> tuple[list[CandidateEvidence], SourceStatus]:
    """Every killed row, plus the prose sections that carry a mechanism-of-death.

    Table rows are taken only from tables whose header names Hypothesis, plus rows appended after
    prose with no header of their own (the file grows that way). The cross-era synthesis table is
    excluded by that rule -- it is a summary of one existing kill, not five new candidates.
    """
    path = root / GRAVEYARD_PATH
    if not path.exists():
        return [], SourceStatus(GRAVEYARD_PATH, False, 0, "absent in this checkout")
    lines = path.read_text("utf-8").splitlines()
    out: list[CandidateEvidence] = []
    header: list[str] | None = None
    for i, raw in enumerate(lines):
        line = raw.strip()
        if not line.startswith("|"):
            if not line:
                header = None
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        nxt = lines[i + 1].strip() if i + 1 < len(lines) else ""
        if nxt.startswith("|--") or nxt.startswith("|:-"):
            header = cells
            continue
        if all(re.fullmatch(r":?-{2,}:?", c) is not None for c in cells):
            continue      # a `|---|---|` rule that is not the row after a header
        if header is not None and not header[0].lower().startswith("hypothesis"):
            continue
        if len(cells) < 3:
            continue
        name, verdict_text, tag = cells[0], cells[1], cells[2]
        lesson = cells[3] if len(cells) > 3 else ""
        blob = f"{name} {verdict_text} {tag} {lesson}"
        cid, matched = classify(blob)
        verdict = _graveyard_verdict(verdict_text, tag)
        out.append(CandidateEvidence(
            candidate_id=_slug(name), class_id=cid, construction=_slug(name), params="",
            verdict=verdict, source=GRAVEYARD_PATH, matched_on=matched, note=tag[:120]))

    # prose kills: a heading whose own section states a kill, excluding the summary sections
    body: list[str] = []
    head = ""
    sections: list[tuple[str, str]] = []
    for raw in lines:
        if re.match(r"^#{2,4} ", raw):
            if head:
                sections.append((head, "\n".join(body)))
            head, body = raw.lstrip("# ").strip(), []
        else:
            body.append(raw)
    if head:
        sections.append((head, "\n".join(body)))
    for title, text in sections:
        low = title.lower()
        if any(marker in low for marker in _GRAVEYARD_NON_KILL):
            continue
        if "KILLED" not in title and "KILLED" not in text[:900]:
            continue
        cid, matched = classify(f"{title} {text[:2500]}")
        out.append(CandidateEvidence(
            candidate_id=_slug(title), class_id=cid, construction=_slug(title), params="",
            verdict=_verdict_from_text(f"{title} {text[:900]}", default=Verdict.REFUTED),
            source=GRAVEYARD_PATH, matched_on=matched, note="prose kill section"))
    return out, SourceStatus(GRAVEYARD_PATH, True, len(out),
                             f"{len(out)} killed rows and prose kill sections parsed")


# -- reader 3: axis pre-registrations (EV-gated, NEVER tested) ---------------------------------
PREREG_PATH = "docs/research/AXIS_PREREGISTRATIONS.md"


def read_preregistrations(root: Path) -> tuple[list[CandidateEvidence], SourceStatus]:
    """EV-gate dispositions. These are REFUSALS TO TEST and are never counted as tests."""
    path = root / PREREG_PATH
    if not path.exists():
        return [], SourceStatus(PREREG_PATH, False, 0, "absent in this checkout")
    out: list[CandidateEvidence] = []
    for raw in path.read_text("utf-8").splitlines():
        line = raw.strip()
        if not line.startswith("|") or line.startswith("|--"):
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if len(cells) < 5 or cells[0].lower() == "axis":
            continue
        axis, hypothesis, verdict_text = cells[0], cells[1], cells[4]
        cid, matched = classify(f"{hypothesis} {axis}")
        out.append(CandidateEvidence(
            candidate_id=_slug(hypothesis), class_id=cid, construction=_slug(hypothesis),
            params="", verdict=Verdict.EV_REJECTED if "reject" in verdict_text.lower()
            else Verdict.NAMED_ONLY,
            source=PREREG_PATH, matched_on=matched, note=f"axis={axis}; {verdict_text}"[:120]))
    return out, SourceStatus(PREREG_PATH, True, len(out),
                             f"{len(out)} pre-registered axes, EV-gated before any compute")


# -- reader 4: the research agenda (named, queued, untested) -----------------------------------
AGENDA_PATH = "research_agenda.json"


def read_agenda(root: Path) -> tuple[list[CandidateEvidence], SourceStatus]:
    """The queue. A queued idea is NAMED-ONLY: it is supply the desk has written down, not run."""
    path = root / AGENDA_PATH
    doc = _load_json(path)
    if not isinstance(doc, dict):
        return [], SourceStatus(AGENDA_PATH, False, 0, "absent or unparseable in this checkout")
    queue = doc.get("queue_ranked_by_expected_research_roi")
    if not isinstance(queue, list):
        return [], SourceStatus(AGENDA_PATH, True, 0, "readable, but carries no ranked queue")
    out: list[CandidateEvidence] = []
    for item in queue:
        if not isinstance(item, dict):
            continue
        ident = str(item.get("id", ""))
        if not ident:
            continue
        blob = f"{ident} {item.get('mechanism', '')} {item.get('pre_registration', '')}"
        cid, matched = classify(blob)
        status = str(item.get("status") or "")
        out.append(CandidateEvidence(
            candidate_id=_slug(ident), class_id=cid, construction=_slug(ident), params="",
            verdict=Verdict.REFUTED if "KILLED" in status else Verdict.NAMED_ONLY,
            source=AGENDA_PATH, matched_on=matched, note=status[:120]))
    return out, SourceStatus(AGENDA_PATH, True, len(out), f"{len(out)} queued research ideas")


# -- reader 5: declared screen artifacts -------------------------------------------------------
@dataclass(frozen=True)
class ScreenSource:
    """A named Stage-A screen artifact and the class its own ``mechanism`` text places it in."""

    path: str
    candidate_id: str
    class_id: str
    basis: str


#: Each entry's class is taken from the artifact's OWN declared mechanism string, quoted in
#: `basis`. The census still opens the file: an entry here asserts nothing about a file that is
#: not on disk, and a missing file is reported NOT-READABLE-HERE rather than counted as zero.
SCREEN_SOURCES: tuple[ScreenSource, ...] = (
    ScreenSource("reports/screen_exchange_netflow.json", "exchange_netflow",
                 "holder_cost_basis_capitulation",
                 "coins moving ONTO exchanges are supply arriving at the only venue where it "
                 "can be sold -- revealed selling intent"),
    ScreenSource("reports/carry_basis_path.json", "carry_entry_shorts_widening_basis",
                 "derivative_carry_basis",
                 "does ranking perps by funding select into a WIDENING basis?"),
    ScreenSource("data/unlock_event_screen.json", "token_unlock_forced_supply",
                 "mechanical_supply_release",
                 "vesting releases tokens to a holder with ~zero cost basis on a contractually "
                 "fixed PUBLIC date; fund lifecycle forces distribution"),
    ScreenSource("data/cot_screen_summary.json", "cot_lagged_positioning",
                 "positioning_crowding_unwind",
                 "hedging-pressure / speculator positioning, lagged form only. The artifact "
                 "carries per-asset t-statistics and NO verdict string, so this census records "
                 "UNKNOWN rather than synthesising a conclusion the file does not state"),
    ScreenSource("data/funding_spread_screen.json", "cross_exchange_funding_spread",
                 "derivative_carry_basis",
                 "segmented participants per venue -> leverage imbalances do not equalise -> a "
                 "funding spread persists beyond its trading cost"),
    ScreenSource("data/copytrading_screen.json", "copytrading_leader_follow",
                 "manager_skill_persistence",
                 "does following a lead trader transfer their edge?"),
    ScreenSource("data/idle_axis_screen.json", "taker_flow_absorption", "informed_order_flow",
                 "aggressive taker buying absorbed WITHOUT the price response that flow should "
                 "have produced marks a large passive distributor"),
    ScreenSource("reports/moat_campaign.json", "moat_book_reconstruction",
                 "orderbook_microstructure_state",
                 "the desk's own recorded books -- the only dataset it owns that the crowd "
                 "does not"),
)

_CELL_KEYS = ("cells", "rows", "trials")
_STATUS_KEYS = ("verdict", "result", "overall", "status", "blocker")


def _screen_cells(doc: dict[str, Any]) -> list[dict[str, Any]]:
    for key in _CELL_KEYS:
        value = doc.get(key)
        if isinstance(value, list) and value and all(isinstance(v, dict) for v in value):
            return [v for v in value if isinstance(v, dict)]
    for value in doc.values():
        if isinstance(value, dict):
            inner = value.get("rows")
            if isinstance(inner, list) and inner and all(isinstance(v, dict) for v in inner):
                return [v for v in inner if isinstance(v, dict)]
    return []


def read_screens(root: Path) -> tuple[list[CandidateEvidence], list[SourceStatus]]:
    """Read each declared screen artifact, or record it NOT-READABLE-HERE."""
    out: list[CandidateEvidence] = []
    statuses: list[SourceStatus] = []
    for src in SCREEN_SOURCES:
        doc = _load_json(root / src.path)
        if not isinstance(doc, dict):
            statuses.append(SourceStatus(
                src.path, False, 0,
                f"runtime-only artifact absent from this checkout; the "
                f"'{src.candidate_id}' evidence for class '{src.class_id}' cannot be counted "
                f"here and is NOT zero"))
            continue
        cells = _screen_cells(doc)
        verdicts = [_verdict_from_text(str(c.get("verdict", "")), default=Verdict.UNKNOWN)
                    for c in cells if c.get("verdict") is not None]
        top = ""
        for key in _STATUS_KEYS:
            value = doc.get(key)
            if isinstance(value, str) and value:
                top = value
                break
        verdict = _verdict_from_text(top, default=Verdict.UNKNOWN)
        for v in verdicts:
            verdict = _strongest(verdict, v)
        out.append(CandidateEvidence(
            candidate_id=src.candidate_id, class_id=src.class_id,
            construction=src.candidate_id, params=f"{len(cells)} cells" if cells else "",
            verdict=verdict, source=src.path, matched_on=("declared:" + src.class_id,),
            note=src.basis[:160], n_parameterisations=max(1, len(cells))))
        statuses.append(SourceStatus(src.path, True, len(cells) or 1,
                                     f"{len(cells)} screened cells" if cells
                                     else "single-record screen artifact"))
    return out, statuses


# ------------------------------------------------------------------------------ aggregation ----
def collect_evidence(root: Path = ROOT) -> tuple[list[CandidateEvidence], list[SourceStatus]]:
    """Every readable record in the tree, de-duplicated by (class, construction, params).

    De-duplication matters because the same idea is frequently recorded twice -- once as a screen
    artifact and once as a graveyard row. Counting both would inflate exactly the number this
    census exists to deflate. The surviving record keeps the STRONGEST verdict and the best OOS.
    """
    evidence: list[CandidateEvidence] = []
    sources: list[SourceStatus] = []
    for reader in (read_campaign, read_graveyard, read_preregistrations, read_agenda):
        rows, status = reader(root)
        evidence.extend(rows)
        sources.append(status)
    screen_rows, screen_status = read_screens(root)
    evidence.extend(screen_rows)
    sources.extend(screen_status)

    def _fuse(a: CandidateEvidence, b: CandidateEvidence) -> CandidateEvidence:
        oos_values = [v for v in (a.oos_sharpe, b.oos_sharpe) if v is not None]
        return CandidateEvidence(
            candidate_id=a.candidate_id, class_id=a.class_id, construction=a.construction,
            params=a.params, verdict=_strongest(a.verdict, b.verdict),
            source=a.source if b.source in a.source else f"{a.source}+{b.source}",
            matched_on=a.matched_on or b.matched_on,
            oos_sharpe=max(oos_values) if oos_values else None, note=a.note,
            n_parameterisations=max(a.n_parameterisations, b.n_parameterisations))

    merged: dict[tuple[str, str, str], CandidateEvidence] = {}
    order: list[tuple[str, str, str]] = []
    for row in evidence:
        key = (row.class_id or "?", row.construction, row.params)
        prior = merged.get(key)
        if prior is None:
            merged[key] = row
            order.append(key)
        else:
            merged[key] = _fuse(prior, row)

    # SECOND PASS -- fold the prose record into the parameterised one. The same idea is routinely
    # recorded twice: once as a screen artifact carrying its cells, once as a graveyard row
    # carrying its mechanism-of-death and no parameters. They are one candidate, and counting
    # both would inflate exactly the number this census exists to deflate.
    parameterised: dict[tuple[str, str], tuple[str, str, str]] = {}
    for key in order:
        if key[2]:
            parameterised.setdefault((key[0], key[1]), key)
    kept: list[tuple[str, str, str]] = []
    for key in order:
        target = parameterised.get((key[0], key[1]))
        if not key[2] and target is not None:
            merged[target] = _fuse(merged[target], merged[key])
            continue
        kept.append(key)
    return [merged[k] for k in kept], sources


@dataclass(frozen=True)
class ClassCensus:
    """What the tree can evidence about one economic class."""

    class_id: str
    name: str
    coverage: Coverage
    n_candidates: int
    n_tested: int
    n_constructions: int
    n_parameterisations: int
    n_external_priors: int
    best_oos_sharpe: float | None
    verdicts: dict[str, int]
    constructions: tuple[str, ...]
    unreadable_sources: tuple[str, ...]
    note: str

    def to_dict(self) -> dict[str, Any]:
        cls = CLASS_BY_ID[self.class_id]
        return {"class_id": self.class_id, "name": self.name, "payer": cls.payer,
                "coverage": str(self.coverage), "n_candidates": self.n_candidates,
                "n_tested": self.n_tested, "n_constructions": self.n_constructions,
                "n_parameterisations": self.n_parameterisations,
                "n_external_priors": self.n_external_priors,
                "best_oos_sharpe": self.best_oos_sharpe, "verdicts": dict(self.verdicts),
                "constructions": list(self.constructions),
                "unreadable_sources": list(self.unreadable_sources), "note": self.note}


def _class_census(cls: MechanismClass, rows: list[CandidateEvidence],
                  unreadable: tuple[str, ...]) -> ClassCensus:
    tested = [r for r in rows if r.tested]
    constructions = tuple(sorted({r.construction for r in rows}))
    n_params = sum(r.n_parameterisations for r in rows)
    oos = [r.oos_sharpe for r in tested if r.oos_sharpe is not None]
    externals = sum(1 for r in rows if r.verdict is Verdict.EXTERNAL_PRIOR)
    conclusive_constructions = len({r.construction for r in rows
                                    if r.verdict in CONCLUSIVE_VERDICTS})

    if not tested and unreadable:
        coverage = Coverage.NOT_READABLE_HERE
        note = ("no readable test evidence, and this class's screen artifact is absent from this "
                "checkout -- UNKNOWN here, never zero")
    elif not rows:
        coverage = Coverage.NO_CANDIDATE
        note = "no candidate anywhere in this tree -- untested, not failed"
    elif not tested:
        coverage = Coverage.NAMED_UNTESTED
        note = ("written down but never tested on desk data"
                + (f"; {externals} external-literature/era prior(s) only" if externals else ""))
    elif conclusive_constructions >= DEPTH_MIN_CONSTRUCTIONS:
        coverage = Coverage.TESTED_DEEP
        note = (f"{conclusive_constructions} distinct constructions each carrying a conclusive "
                f"verdict, across {n_params} parameterisations")
    else:
        coverage = Coverage.TESTED_SHALLOW
        note = (f"only {conclusive_constructions} construction(s) reached a conclusive verdict "
                f"-- below the census depth bar of {DEPTH_MIN_CONSTRUCTIONS}; "
                f"{n_params} parameterisations do not substitute for constructions")
    return ClassCensus(
        class_id=cls.id, name=cls.name, coverage=coverage, n_candidates=len(rows),
        n_tested=len(tested), n_constructions=len(constructions),
        n_parameterisations=n_params, n_external_priors=externals,
        best_oos_sharpe=max(oos) if oos else None,
        verdicts=dict(sorted(Counter(str(r.verdict) for r in rows).items())),
        constructions=constructions, unreadable_sources=unreadable, note=note)


# ------------------------------------------------------------------------------- diversity -----
@dataclass(frozen=True)
class Diversity:
    """How wide the tested supply actually is, independent of how much of it there is."""

    n_candidates: int
    n_classes_occupied: int
    n_classes_in_taxonomy: int
    shannon_entropy: float
    effective_classes: float     # exp(H): the Hill number -- classes' worth of real spread
    diversity: float             # effective_classes / taxonomy size, in (0, 1]
    hhi: float
    top_class: str
    top_class_share: float

    def to_dict(self) -> dict[str, Any]:
        return dict(self.__dict__)


def measure_diversity(rows: list[CandidateEvidence],
                      *, n_classes: int = len(TAXONOMY)) -> Diversity:
    """Effective number of economic classes in a candidate set, as a fraction of the taxonomy.

    WHY exp(H) OVER THE TAXONOMY, and not entropy over the item count. The question this census
    answers is "what fraction of the KNOWN mechanism space is the desk actually exploring", so
    the denominator has to be the opportunity set, not the batch size. The Hill number exp(H) is
    the number of equally-weighted classes that would produce the observed spread, which makes
    the reading directly legible: 400 candidates evenly split across 3 of 20 classes score 3/20 =
    0.15 no matter whether there are 400 of them or 40. That volume-invariance is the property
    that matters here -- it is exactly why generating another hundred price transformations does
    not move this number, and why a count of candidates could never have shown that.
    """
    counts = Counter(r.class_id for r in rows if r.class_id is not None)
    total = sum(counts.values())
    if total == 0 or n_classes <= 0:
        return Diversity(0, 0, n_classes, 0.0, 0.0, 0.0, 0.0, "", 0.0)
    shares = [c / total for c in counts.values()]
    entropy = -sum(p * math.log(p) for p in shares if p > 0)
    effective = math.exp(entropy)
    top, top_n = counts.most_common(1)[0]
    return Diversity(
        n_candidates=total, n_classes_occupied=len(counts), n_classes_in_taxonomy=n_classes,
        shannon_entropy=round(entropy, 4), effective_classes=round(effective, 3),
        diversity=round(min(1.0, effective / n_classes), 4),
        hhi=round(sum(p * p for p in shares), 4), top_class=top,
        top_class_share=round(top_n / total, 4))


# ------------------------------------------------------------------------------ the gap list ---
@dataclass(frozen=True)
class GapRow:
    """One untested or under-tested class, scored as a next target."""

    rank: int
    class_id: str
    name: str
    coverage: Coverage
    gap_score: float
    plausibility: float
    orthogonality: float
    feasibility: float
    depth_deficit: float
    payer: str
    data_required: DataRequirement
    prior_kills: tuple[str, ...]
    why: str

    def to_dict(self) -> dict[str, Any]:
        return {"rank": self.rank, "class_id": self.class_id, "name": self.name,
                "coverage": str(self.coverage), "gap_score": self.gap_score,
                "plausibility": self.plausibility, "orthogonality": self.orthogonality,
                "feasibility": self.feasibility, "depth_deficit": self.depth_deficit,
                "payer": self.payer, "data_required": self.data_required.to_dict(),
                "prior_kills": list(self.prior_kills), "why": self.why}


def rank_gaps(classes: list[ClassCensus],
              evidence: list[CandidateEvidence]) -> tuple[list[GapRow], list[GapRow]]:
    """Rank the classes worth testing next, and separately those that cannot be ranked here.

    ``gap_score = plausibility x orthogonality x data_feasibility x depth_deficit``. Multiplicative
    on purpose: a class with an unimpeachable payer story and no obtainable data is not a target,
    and neither is one with perfect data and no reason anybody should pay. Every factor is a
    DECLARED constant of this census, never fitted to an outcome, and the score confers no
    standing on anything -- it orders a reading list.

    A class whose evidence is NOT-READABLE-HERE is returned in the second list, unscored. Ranking
    it would mean pricing a gap whose size this checkout cannot see.
    """
    kills: dict[str, list[str]] = {}
    for row in evidence:
        if row.class_id is not None and row.verdict in CONCLUSIVE_VERDICTS:
            kills.setdefault(row.class_id, []).append(row.construction)

    scored: list[tuple[float, ClassCensus]] = []
    blind: list[ClassCensus] = []
    for cen in classes:
        if cen.coverage is Coverage.NOT_READABLE_HERE:
            blind.append(cen)
            continue
        cls = CLASS_BY_ID[cen.class_id]
        score = (cls.plausibility * cls.orthogonality
                 * _FEASIBILITY[cls.data.availability] * _DEPTH_DEFICIT[cen.coverage])
        if score > 0.0:
            scored.append((score, cen))
    scored.sort(key=lambda kv: (-kv[0], kv[1].class_id))

    def _row(rank: int, score: float, cen: ClassCensus) -> GapRow:
        cls = CLASS_BY_ID[cen.class_id]
        prior = tuple(sorted(set(kills.get(cen.class_id, ()))))[:6]
        why = (f"{cen.coverage}: {cen.n_tested} tested candidate(s) across "
               f"{cen.n_constructions} construction(s); payer story {cls.plausibility:.2f}, "
               f"orthogonality {cls.orthogonality:.2f}, data "
               f"{cls.data.availability}")
        if prior:
            why += (f". NOT virgin ground -- {len(prior)} conclusive prior verdict(s) already "
                    f"sit in this class")
        if cen.unreadable_sources:
            why += (". Partly blind here: " + ", ".join(cen.unreadable_sources)
                    + " is absent from this checkout, so the tested count is a LOWER bound")
        return GapRow(rank=rank, class_id=cen.class_id, name=cen.name, coverage=cen.coverage,
                      gap_score=round(score, 4), plausibility=cls.plausibility,
                      orthogonality=cls.orthogonality,
                      feasibility=_FEASIBILITY[cls.data.availability],
                      depth_deficit=_DEPTH_DEFICIT[cen.coverage], payer=cls.payer,
                      data_required=cls.data, prior_kills=prior, why=why)

    ranked = [_row(i + 1, score, cen) for i, (score, cen) in enumerate(scored)]
    unrankable = [
        GapRow(rank=0, class_id=c.class_id, name=c.name, coverage=c.coverage, gap_score=0.0,
               plausibility=CLASS_BY_ID[c.class_id].plausibility,
               orthogonality=CLASS_BY_ID[c.class_id].orthogonality,
               feasibility=_FEASIBILITY[CLASS_BY_ID[c.class_id].data.availability],
               depth_deficit=0.0, payer=CLASS_BY_ID[c.class_id].payer,
               data_required=CLASS_BY_ID[c.class_id].data, prior_kills=(),
               why="cannot be ranked from this checkout: "
                   + "; ".join(c.unreadable_sources))
        for c in blind]
    return ranked, unrankable


# ---------------------------------------------------------------------------------- report -----
@dataclass(frozen=True)
class CensusReport:
    generated_utc: str
    classes: list[ClassCensus]
    diversity: Diversity
    campaign_diversity: Diversity
    gaps: list[GapRow]
    unrankable: list[GapRow]
    sources: list[SourceStatus]
    unclassified: list[CandidateEvidence]
    evidence: list[CandidateEvidence] = field(default_factory=list)

    def coverage_counts(self) -> dict[str, int]:
        return dict(sorted(Counter(str(c.coverage) for c in self.classes).items()))

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": SCHEMA_VERSION,
            "generated_utc": self.generated_utc,
            "authority": ("MEASUREMENT ONLY. This census promotes nothing, blocks nothing, and "
                          "changes no gate, threshold or bar. Its depth and scoring constants "
                          "are reporting parameters and confer no standing."),
            "taxonomy_size": len(TAXONOMY),
            "depth_bar": {"min_conclusive_constructions": DEPTH_MIN_CONSTRUCTIONS,
                          "note": "a reporting bar for this census only, denominated in "
                                  "constructions -- never in candidates, which reparameterising "
                                  "one construction would satisfy"},
            "totals": {
                "n_records": len(self.evidence),
                "n_tested": sum(1 for r in self.evidence if r.tested),
                "n_classified": sum(1 for r in self.evidence if r.class_id is not None),
                "n_unclassified": len(self.unclassified),
            },
            "coverage_counts": self.coverage_counts(),
            "diversity": self.diversity.to_dict(),
            "campaign_diversity": self.campaign_diversity.to_dict(),
            "classes": [c.to_dict() for c in self.classes],
            "gaps": [g.to_dict() for g in self.gaps],
            "unrankable_gaps": [g.to_dict() for g in self.unrankable],
            "sources": [s.to_dict() for s in self.sources],
            "unclassified": [r.to_dict() for r in self.unclassified],
            "taxonomy": [c.to_dict() for c in TAXONOMY],
            "honesty_rails": [
                "a class with no evidence on disk is UNTESTED, never failed: its verdict "
                "distribution is empty and its best OOS is null, not 0.0",
                "a runtime-only artifact absent from this checkout is NOT-READABLE-HERE and is "
                "never counted as zero evidence",
                "EV-REJECTED and NAMED-ONLY are refusals to test, not test results, and are "
                "excluded from every tested count and from the depth bar",
                "EXTERNAL-PRIOR records are somebody else's evidence, not re-run here, and do "
                "not count toward depth",
                "records matching no signature are reported in `unclassified`, never assigned "
                "to the nearest plausible class",
            ],
        }


def census(root: Path = ROOT) -> CensusReport:
    """Read the tree and report the mechanism supply. Never writes anything."""
    evidence, sources = collect_evidence(root)
    unreadable_by_class: dict[str, list[str]] = {}
    readable_paths = {s.path for s in sources if s.readable}
    for src in SCREEN_SOURCES:
        if src.path not in readable_paths:
            unreadable_by_class.setdefault(src.class_id, []).append(src.path)

    by_class: dict[str, list[CandidateEvidence]] = {c.id: [] for c in TAXONOMY}
    unclassified: list[CandidateEvidence] = []
    for row in evidence:
        if row.class_id is None:
            unclassified.append(row)
        else:
            by_class[row.class_id].append(row)

    classes = [_class_census(c, by_class[c.id],
                             tuple(sorted(unreadable_by_class.get(c.id, ()))))
               for c in TAXONOMY]
    gaps, unrankable = rank_gaps(classes, evidence)
    campaign_rows = [r for r in evidence if CAMPAIGN_PATH in r.source]
    return CensusReport(
        generated_utc=datetime.now(tz=UTC).isoformat(timespec="seconds"),
        classes=classes,
        diversity=measure_diversity([r for r in evidence if r.tested]),
        campaign_diversity=measure_diversity(campaign_rows),
        gaps=gaps, unrankable=unrankable, sources=sources, unclassified=unclassified,
        evidence=evidence)

```

### libs\research\screen_conversion.py
```python
"""SCREEN CONVERSION -- every scored cell on disk becomes a Stage-A candidate, or says why not.

THE DEFECT THIS CLOSES, measured 2026-08-05. The desk had 135 scored screen cells sitting on disk
and exactly SIX of them could reach a forward slot:

    data/primary_market_flow_screen.json   `rows`     30 cells   unreachable
    data/vol_risk_premium_screen.json      `rows`     66 cells   unreachable
    data/unlock_event_screen.json          `cells`    27 cells   unreachable
    reports/screen_exchange_netflow.json   `cells`    12 cells   unreachable
    reports/axis_screens/liquidation_*.json `trials`    6 cells   reachable

Not one of the 129 was refuted, retired, or judged. They were UNREADABLE -- `finalize_axis_screens`
speaks one schema (a `trials` list under reports/axis_screens/) and every newer screen writes its
own. So the desk kept generating measurements it could not consume, and then reported the silence
as "no survivors". That is the conversion defect in its purest form: output produced, never
converted, never utilised, and the shortfall invisible because the missing rows never appeared
anywhere to be missed (L1.50 -- an unexploited asset is a defect; L1.53 -- conversion must CATCH UP
to what is being produced, never be caught up to by shrinking it).

WHAT THIS DOES. It reads every JSON artifact under data/ and reports/, finds any list of rows
carrying the harness's scoring signature, and rewrites them into the canonical `trials` shape so
the existing correction layer and the existing spawner can consume them unchanged. No screen is
edited, no verdict is softened, no threshold is touched -- this is a TRANSLATOR.

NOTHING IS HARDCODED. The artifact list is DISCOVERED by walking the tree and testing each row for
the scoring signature, and the field names are resolved through alias tables. A screen written
tomorrow under a name nobody here anticipated is picked up by the same walk, and a field this
module cannot map is RECORDED in `unmapped` rather than dropped -- because a converter that
silently skips what it does not understand reproduces the exact defect it exists to fix, one level
further down.

WHAT IS DISQUALIFIED, AND WHY THAT IS NOT A BAR. Two classes never become candidates:

  * CONTROLS AND DIAGNOSTICS -- `form == "lookahead_control"`, `alignment.is_lookahead_control`,
    the naive contaminated builds. These are run to MEASURE a leak; promoting one is the rule-8
    artifact-as-edge failure.
  * BROKEN MEASUREMENTS -- TIMING-ARTIFACT, SUSPECT-LOOKAHEAD. A cell whose alignment gate fired
    is not a weak edge, it is a number that does not mean what it says.

Everything else is a candidate, INCLUDING SCREEN-WEAK and SCREEN-UNDERPOWERED. That is deliberate
and it is the law: under the two-stage rule Stage A is a RANKING DEVICE WITH ZERO PROMOTION
AUTHORITY, so a Stage-A significance verdict cannot be an admission gate -- using it as one is
letting the ranking device promote, which is precisely what the law forbids. "Underpowered" means
the screen could not see, not that it looked and found nothing (L1.49): of the desk's 228 recorded
negatives only 50 were POWERED. Refusing a forward clock to a cell the screen could not resolve is
how a desk guarantees it never resolves anything.

Pure stdlib. The organ is scripts/finalize_axis_screens.py, which runs this first.
"""
from __future__ import annotations

import json
import math
import re
from pathlib import Path
from typing import Any

__all__ = [
    "CONVERTED_PREFIX",
    "canonical_row",
    "convert_all",
    "discover",
    "is_scored_row",
    "write_converted",
]

_ROOT = Path(__file__).resolve().parents[2]

#: Every file this module writes carries it. Nothing without this prefix is ever overwritten, so a
#: hand-written screen report can never be clobbered by a conversion pass.
CONVERTED_PREFIX = "conv_"

#: Where the correction layer and the spawner both look.
_AXIS_DIR = "reports/axis_screens"

#: Trees walked for scored cells. Directories, not files -- a screen added tomorrow under a name
#: nobody anticipated is found by the same walk.
_SEARCH_ROOTS: tuple[str, ...] = ("data", "reports", "web")

#: Field aliases, canonical name -> the spellings seen in the wild, IN PREFERENCE ORDER. Extending
#: this is how a new screen's vocabulary is taught; an unrecognised spelling is reported in
#: `unmapped`, never silently defaulted -- a defaulted zero is a fabricated measurement.
_ALIASES: dict[str, tuple[str, ...]] = {
    "ic": ("ic", "ic_mean", "information_coefficient"),
    "residual_ic": ("residual_ic", "ic_residual"),
    "n": ("n", "n_paired", "n_events", "n_obs", "n_rows"),
    "n_eff": ("n_eff", "n_effective", "neff"),
    "horizon_days": ("horizon_days", "horizon_d", "horizon_calendar_days"),
    "sharpe_momentum": ("sharpe_momentum", "sharpe"),
    "sharpe_reversal": ("sharpe_reversal",),
    "verdict": ("verdict", "label"),
    "t_stat": ("t_stat", "ic_t_stat", "tstat", "current_z"),
    "decontam_passed": ("decontam_passed",),
    "implausible_leak": ("implausible_leak",),
    "min_detectable_ic": ("min_detectable_ic", "detection_floor_ic_unadjusted"),
}

#: HORIZON UNITS, converted to DAYS. Everything downstream prices a forward clock as
#: `rows_needed * bar_length_days`, so a horizon in the wrong unit is not a cosmetic problem -- it
#: silently makes the cell UNRANKABLE and drops it behind every candidate whose wait is known.
#:
#: This bit off the moat, which is the desk's ONLY proprietary dataset and the one it calls its
#: largest unexploited asset. `screen_moat` reports `horizon_s` in SECONDS: a 30-second cell at
#: |ic| 0.02 needs ~17,400 bars, which is SIX DAYS of tape -- by far the fastest resolution
#: anything on this desk can offer, and it was arriving with no readable clock at all.
_HORIZON_UNITS: dict[str, float] = {
    "horizon_days": 1.0, "horizon_d": 1.0, "horizon_calendar_days": 1.0, "window_days": 1.0,
    "horizon_h": 1.0 / 24.0,
    "horizon_min": 1.0 / 1440.0, "interval_min": 1.0 / 1440.0, "horizon_m": 1.0 / 1440.0,
    "horizon_s": 1.0 / 86400.0, "horizon_sec": 1.0 / 86400.0, "horizon_seconds": 1.0 / 86400.0,
    "horizon_ms": 1.0 / 86_400_000.0, "bar_ms": 1.0 / 86_400_000.0,
}

#: A row is a SCORED CELL when it carries an effect estimate and a sample size. Deliberately
#: narrow: a config block or a coverage table must never be mistaken for a screened hypothesis.
_EFFECT_KEYS = frozenset({"ic", "ic_mean", "residual_ic", "t_stat", "ic_t_stat"})
_SIZE_KEYS = frozenset({"n", "n_eff", "n_effective", "n_paired", "n_events", "n_obs"})

#: Verdicts naming a BROKEN measurement rather than a weak one. These can never be candidates: the
#: alignment gate fired, so the number does not mean what it says. This is not a strength bar --
#: SCREEN-WEAK and SCREEN-UNDERPOWERED are absent from this set on purpose.
BROKEN_VERDICTS: frozenset[str] = frozenset({
    "TIMING-ARTIFACT", "SUSPECT-LOOKAHEAD", "NOT-A-CANDIDATE", "NOT-READABLE-HERE",
})

#: Row markers that make a cell a control or diagnostic, however it scored.
_CONTROL_FORMS = frozenset({"lookahead_control", "naive", "control", "shift_control"})


def _first(row: dict[str, Any], canonical: str) -> tuple[Any, str | None]:
    """(value, spelling used). (None, None) when no alias is present -- never a default."""
    for key in _ALIASES.get(canonical, (canonical,)):
        if key in row and row[key] is not None:
            return row[key], key
    return None, None


def _num(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float, str)):
        return None
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if math.isfinite(out) else None


def is_scored_row(row: object) -> bool:
    """Does this dict look like a screened hypothesis rather than a config or coverage block?"""
    if not isinstance(row, dict):
        return False
    keys = set(row)
    return bool(keys & _EFFECT_KEYS) and bool(keys & _SIZE_KEYS)


def discover(root: Path | None = None) -> list[dict[str, Any]]:
    """Every (file, key) holding a list of scored cells. Walks the tree -- no artifact list.

    Files already living in the canonical directory are skipped: a `trials` list there is already
    readable, and re-converting it would mint a duplicate hypothesis paying a second Holm slot.
    """
    base = root or _ROOT
    axis_dir = (base / _AXIS_DIR).resolve()
    found: list[dict[str, Any]] = []
    for rel in _SEARCH_ROOTS:
        tree = base / rel
        if not tree.is_dir():
            continue
        for path in sorted(tree.rglob("*.json")):
            if path.resolve().parent == axis_dir:
                continue                       # already canonical, or already converted
            try:
                doc = json.loads(path.read_text("utf-8"))
            except (OSError, ValueError, RecursionError):
                continue                       # unreadable cannot qualify anything
            if not isinstance(doc, dict):
                continue
            for key, value in doc.items():
                if not isinstance(value, list) or not value:
                    continue
                scored = [r for r in value if is_scored_row(r)]
                unscored = [r for r in value if isinstance(r, dict) and not is_scored_row(r)]
                if not _is_screen_list(scored, unscored, len(value)):
                    continue
                found.append({"path": str(path.relative_to(base)), "key": key,
                              "n_rows": len(scored), "n_unscored": len(unscored),
                              "unscored": unscored, "doc": doc, "rows": scored})
    return found


#: Minimum scored cells before a list is treated as a screen. Below this a field-name coincidence
#: is more likely than a screened family.
_MIN_SCORED = 3


def _is_screen_list(scored: list[Any], unscored: list[Any], total: int) -> bool:
    """Is this list a screened family, or a config block whose field names happen to collide?

    A PLAIN MAJORITY TEST WAS WRONG AND COST A WHOLE ARTIFACT. `data/unlock_event_screen.json`
    holds 27 cells, of which the screen itself DECLINED TO SCORE 15 ("UNDERPOWERED: <20 events",
    no t-stat emitted). A majority rule then read 12 < 15 and discarded the entire file -- so the
    12 cells the screen DID score became invisible because of the 15 it had already judged
    unscoreable. That is the L1.41 confusion in a new place: 'not scored' and 'not a screen' are
    different facts, and collapsing them let an honest declaration of low power delete the
    measurements next to it.

    The real discriminator is VOCABULARY, not headcount. Unscored siblings of a screened family
    carry the family's own identifying fields (category, window_days, verdict...); a config block
    that merely happens to contain an `n` does not. So a list qualifies when it has enough scored
    cells to be a family, and its unscored rows either are few or LOOK LIKE the scored ones.
    """
    # A HOMOGENEOUS LIST NEEDS NO HEADCOUNT EVIDENCE. When every row carries the scoring
    # signature there is nothing to disambiguate, so a small screen is still a screen -- and a
    # two-cell screen going invisible for failing a size floor is the same unexploited-asset
    # defect this module exists to fix, one level down. Two is the floor only because a SINGLE
    # dict with an `ic` and an `n` is more plausibly a coincidence than a screened family.
    if not unscored and len(scored) >= 2:
        return True
    if len(scored) < _MIN_SCORED:
        return False
    if len(scored) * 2 >= total:
        return True
    scored_keys: set[str] = set()
    for row in scored:
        if isinstance(row, dict):
            scored_keys |= set(row)
    if not scored_keys:
        return False
    kin = sum(1 for r in unscored
              if isinstance(r, dict) and len(set(r) & scored_keys) * 2 >= len(set(r)))
    return kin * 2 >= len(unscored)          # the unscored rows are siblings, not strangers


#: Scalar fields that identify WHICH hypothesis a row is, as opposed to what it scored. Order is
#: the name's field order. `target` is here because leaving it out collided every VRP row: 66 cells
#: reduced to 33 names, so a forward clock resolved to whichever of two hypotheses came first in
#: the file -- one testing short-vol carry, the other the underlying's return.
_IDENTITY_FIELDS: tuple[str, ...] = (
    "market", "underlying", "asset", "category", "construction", "target", "form", "build",
    "bucket", "level", "side_mapping",
)
_IDENTITY_NUMERIC: tuple[str, ...] = (
    "horizon_days", "horizon_d", "window_days", "bar", "interval_min", "horizon_min",
    "pct_circ_now_min",
)


def _declared_name(row: dict[str, Any]) -> str | None:
    """The screen's OWN identity for this cell, if it declared one.

    Preferred over anything reconstructed: a screen that names its cells (VRP writes
    `type2.name = per_market|AVAX:t90|iv_level|short_vol_carry`) has already solved the identity
    problem for its own vocabulary, and second-guessing it is how a converter invents collisions.
    """
    explicit = row.get("name")
    if isinstance(explicit, str) and explicit.strip():
        return explicit.strip()
    for value in row.values():
        if isinstance(value, dict):
            nested = value.get("name")
            if isinstance(nested, str) and nested.strip():
                return nested.strip()
    return None


def _row_name(row: dict[str, Any], index: int) -> str:
    """A stable identity. Built from whatever identifying fields the row carries, because an
    index-only name would renumber whenever the screen's row order changed and silently re-point
    every downstream dedupe key at a different hypothesis. Uniqueness is enforced separately by
    `_disambiguate`, which can see the whole family and this function cannot."""
    declared = _declared_name(row)
    if declared:
        return declared
    parts = [str(row[k]) for k in _IDENTITY_FIELDS
             if isinstance(row.get(k), (str, int, float)) and str(row[k]).strip()]
    for k in _IDENTITY_NUMERIC:
        v = row.get(k)
        if isinstance(v, (int, float)) and not isinstance(v, bool):
            parts.append(f"{k}{v:g}")
    return "|".join(parts) if parts else f"cell{index}"


def _disambiguate(trials: list[dict[str, Any]], rows: list[dict[str, Any]]) -> None:
    """Make every name in one artifact unique, using the fields that ACTUALLY differ.

    A NAME THAT IS NOT UNIQUE IS NOT AN IDENTITY, and downstream everything keys on it: dedupe
    decides which hypotheses share a Holm slot, and the forward runner re-finds its cell by name
    every day. With 66 VRP rows collapsing to 33 names, half the forward clocks would have been
    accruing evidence about a hypothesis they were not spawned for -- and nothing would have said
    so, because both rows are real cells that parse cleanly.

    The discriminator is DISCOVERED, never listed: for each colliding group, find the keys whose
    values differ across the group and append them. So the next screen's private vocabulary is
    handled without teaching this module a thing about it, and a group that genuinely cannot be
    told apart is marked rather than silently renumbered.
    """
    groups: dict[str, list[int]] = {}
    for i, t in enumerate(trials):
        groups.setdefault(str(t.get("name", "")), []).append(i)
    for name, idxs in groups.items():
        if len(idxs) < 2:
            continue
        keys: set[str] = set()
        for i in idxs:
            keys |= set(rows[i])
        # Only SCALAR keys, and only ones that vary across the group: a differing float like `ic`
        # is a score, not an identity, so identity fields are preferred and scores are the
        # fallback that at least keeps two real cells apart.
        varying = sorted(
            k for k in keys
            if len({json.dumps(rows[i].get(k), sort_keys=True, default=str) for i in idxs}) > 1
            and all(isinstance(rows[i].get(k), (str, int, float, type(None))) for i in idxs))
        preferred = [k for k in varying if k in _IDENTITY_FIELDS + _IDENTITY_NUMERIC] or varying
        if not preferred:
            for rank, i in enumerate(idxs):
                trials[i]["name"] = f"{name}#{rank}"
                trials[i]["name_collision"] = (
                    "INDISTINGUISHABLE from its siblings on every scalar field -- suffixed by "
                    "position, which is NOT stable across a reordering of the source. Treat this "
                    "cell's identity as unreliable until the screen names its own rows.")
            continue
        for i in idxs:
            suffix = "|".join(f"{k}={rows[i].get(k)}" for k in preferred[:3])
            trials[i]["name"] = f"{name}|{suffix}"
            trials[i]["name_disambiguated_by"] = preferred[:3]


def canonical_row(row: dict[str, Any], index: int, *,
                  mechanism: str = "") -> dict[str, Any]:
    """One scored cell in the shape `finalize_axis_screens` and `paper_sleeves` already read.

    DERIVATIONS ARE FLAGGED, never laundered. Where a screen reports a t-stat but no IC (the
    unlock-event shape), IC is recovered as t/sqrt(n_eff) and the row carries
    `ic_derived_from`, so a reader can always tell a measured number from a reconstructed one.
    NOTHING IS INVENTED: a cell with neither an IC nor a t-stat is returned with `unmapped`
    naming what was missing, and it can qualify nothing.
    """
    out: dict[str, Any] = {}
    unmapped: list[str] = []
    used: dict[str, str] = {}

    for canon in ("ic", "residual_ic", "n", "n_eff", "horizon_days", "sharpe_momentum",
                  "sharpe_reversal", "verdict", "t_stat", "decontam_passed",
                  "implausible_leak", "min_detectable_ic"):
        value, spelling = _first(row, canon)
        if spelling is None:
            continue
        used[canon] = spelling
        out[canon] = value

    out["name"] = _row_name(row, index)

    # HORIZON IN DAYS, whatever unit the screen chose to report it in. Resolved here rather than
    # left to the ranker, because the ranker cannot tell "no horizon" from "a horizon in seconds"
    # and both would land in the same UNRANKED bucket -- which is where the moat's fastest cells
    # were sitting. The unit ACTUALLY USED is recorded so a reader can audit the conversion.
    if _num(out.get("horizon_days")) is None:
        for field, scale in _HORIZON_UNITS.items():
            raw = _num(row.get(field))
            if raw is not None and raw > 0:
                out["horizon_days"] = raw * scale
                used["horizon_days"] = field
                if scale != 1.0:
                    out["horizon_converted_from"] = f"{field}={raw:g} x {scale:g} days/unit"
                break

    n_eff = _num(out.get("n_eff"))
    n_raw = _num(out.get("n"))
    if n_eff is None and n_raw is not None:
        n_eff = n_raw
    if n_raw is None and n_eff is not None:
        n_raw = n_eff

    ic = _num(out.get("ic"))
    if ic is None:
        t = _num(out.get("t_stat"))
        if t is not None and n_eff and n_eff > 2:
            ic = t / math.sqrt(n_eff)
            out["ic_derived_from"] = (f"t_stat={t:g} / sqrt(n_eff={n_eff:g}) -- this screen "
                                      "reports a t-statistic and no IC; the recovery is exact "
                                      "under the same normalisation and is flagged so a reader "
                                      "never mistakes it for a directly measured IC")
        else:
            unmapped.append("ic (no `ic` alias and no t_stat/n_eff to recover one from)")
    if ic is not None:
        out["ic"] = round(ic, 6)
    if n_raw is None:
        unmapped.append("n (no sample-size alias present)")
    else:
        out["n"] = int(n_raw)
    if n_eff is not None:
        out["n_eff"] = float(n_eff)

    # Sharpe: the correction layer takes max(|momentum|, |reversal|). A screen reporting neither
    # gets ZERO rather than a guess -- and zero fails the 0.5 floor, so an unmeasured Sharpe can
    # never manufacture a SCREEN-INTERESTING. Fail-closed on the promotion-relevant side.
    if "sharpe_momentum" not in out and "sharpe_reversal" not in out:
        out["sharpe_momentum"] = 0.0
        out["sharpe_reversal"] = 0.0
        unmapped.append("sharpe (neither momentum nor reversal reported; recorded as 0.0, which "
                        "fails the 0.5 floor -- an unmeasured Sharpe must never promote)")

    if "verdict" not in out:
        # NEVER invented as a pass. An unrated cell is still EV-rankable for a forward clock, and
        # saying so is different from claiming the screen rated it.
        out["verdict"] = "SCREEN-UNRATED"
        out["verdict_source"] = ("assigned by conversion -- the source screen carried no verdict "
                                 "field; the cell is rankable but was never rated by its screen")

    verdict = str(out.get("verdict", "")).strip().upper()
    _align = row.get("alignment")
    align: dict[str, Any] = _align if isinstance(_align, dict) else {}
    form = str(row.get("form", "")).strip().lower()
    control_reason = ""
    if align.get("is_lookahead_control") is True:
        control_reason = "declared look-ahead control (alignment.is_lookahead_control)"
    elif form in _CONTROL_FORMS:
        control_reason = f"diagnostic build form={form!r}"
    elif any(verdict.startswith(b) for b in BROKEN_VERDICTS):
        control_reason = (f"verdict {verdict} names a BROKEN measurement -- the alignment gate "
                          "fired, so the number does not mean what it says. This is not a "
                          "strength bar: SCREEN-WEAK and SCREEN-UNDERPOWERED stay candidates.")
    if control_reason:
        out["is_candidate"] = False
        out["conversion_disqualified"] = control_reason

    if mechanism:
        out["mechanism_class"] = mechanism
    for keep in ("alignment", "construction", "market", "underlying", "asset", "bucket", "form",
                 "level", "powered", "excess_resolved", "ic_lag1", "same_period_corr"):
        if keep in row and keep not in out:
            out[keep] = row[keep]
    out["converted_from_fields"] = used
    if unmapped:
        out["unmapped"] = unmapped
    return out


def _axis_name(rel_path: str, key: str) -> str:
    """conv_<file stem>__<row key>. Deterministic: re-running overwrites, never duplicates."""
    stem = re.sub(r"[^a-z0-9]+", "_", Path(rel_path).stem.lower()).strip("_")
    keyslug = re.sub(r"[^a-z0-9]+", "_", str(key).lower()).strip("_")
    return f"{CONVERTED_PREFIX}{stem}__{keyslug}"


def convert_all(root: Path | None = None) -> dict[str, Any]:
    """Discover every scored artifact and build its canonical payload. No writes."""
    base = root or _ROOT
    payloads: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    for hit in discover(base):
        doc, rows = hit["doc"], hit["rows"]
        mechanism = str(doc.get("mechanism_class") or doc.get("mechanism") or "")
        trials = [canonical_row(r, i, mechanism=mechanism) for i, r in enumerate(rows)]
        _disambiguate(trials, rows)
        usable = [t for t in trials if "unmapped" not in t or "n (" not in " ".join(t["unmapped"])]
        if not usable:
            skipped.append({"path": hit["path"], "key": hit["key"], "n_rows": hit["n_rows"],
                            "why": "no row carried a usable sample size"})
            continue
        axis = _axis_name(hit["path"], hit["key"])
        payloads.append({
            "axis": axis,
            "converted_from": hit["path"],
            "converted_key": hit["key"],
            "mechanism_class": mechanism,
            "screen": str(doc.get("screen") or doc.get("mechanism_class")
                          or Path(hit["path"]).stem),
            "law": ("Stage-A only (two-stage law): ZERO promotion authority. Admission to a "
                    "forward slot is by EV-rank, never by a Stage-A significance verdict -- "
                    "letting the ranking device gate promotion is what the law forbids."),
            "conversion_note": ("Translated into the canonical trials shape by "
                                "libs/research/screen_conversion.py. No verdict was softened and "
                                "no threshold was moved: the source rows are reproduced with "
                                "their field names resolved, and anything unmappable is named in "
                                "each row's `unmapped` rather than dropped."),
            "trials": trials,
            "n_disqualified": sum(1 for t in trials if t.get("is_candidate") is False),
            # NAMED, never silent. These are rows the SOURCE SCREEN declined to score (no effect
            # estimate emitted at all). Recording the count keeps the shortfall visible instead of
            # letting a converted artifact read as full coverage of its source.
            "n_unscored_in_source": int(hit.get("n_unscored", 0)),
            "unscored_note": ("rows the source screen emitted without an effect estimate -- it "
                              "declined to score them, so there is nothing here to convert. They "
                              "are counted rather than dropped silently: 'the screen could not "
                              "score this' is a finding, not an absence."),
        })
    return {"payloads": payloads, "skipped": skipped,
            "n_artifacts": len(payloads), "n_cells": sum(len(p["trials"]) for p in payloads)}


def write_converted(root: Path | None = None) -> dict[str, Any]:
    """Write every converted payload into the canonical directory. Overwrites only `conv_` files."""
    base = root or _ROOT
    out_dir = base / _AXIS_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    result = convert_all(base)
    written: list[str] = []
    for payload in result["payloads"]:
        path = out_dir / f"{payload['axis']}.json"
        if path.exists() and not path.name.startswith(CONVERTED_PREFIX):  # pragma: no cover
            continue                           # never clobber a hand-written screen
        path.write_text(json.dumps(payload, indent=1, ensure_ascii=False) + "\n", "utf-8")
        written.append(path.name)
    # A conversion that used to produce a file and no longer does leaves a STALE artifact behind,
    # and a stale screen keeps admitting a hypothesis whose source was deleted. Sweep them.
    live = {f"{p['axis']}.json" for p in result["payloads"]}
    removed = []
    for path in sorted(out_dir.glob(f"{CONVERTED_PREFIX}*.json")):
        if path.name not in live:
            path.unlink()
            removed.append(path.name)
    result["written"] = written
    result["removed_stale"] = removed
    return result

```

### libs\validation\near_miss.py
```python
"""KEEP THE NEAR-MISSES. A candidate at 80% of the bar is a WORK ITEM, not a corpse.

THE GAP THIS CLOSES, quoted from the desk's own comparison table. `brain_calibration.gap_report()`
emits a row for "near-miss triage" whose desk value is `None` and whose direction reads
**"NO DESK COUNTERPART -- recorded as ABSENT, not as satisfied"**. The external pipeline's practice
is that an alpha at roughly 80% of the submission metrics -- Sharpe 0.9 against a 1.0 bar -- is
"near-submittable", and near-submittable alphas are IMPROVED rather than discarded. This desk emits
PASS/FAIL, so a candidate that came within a hair of the bar is marked FAILED, dies silently, and
leaves no record that it was ever close.

WHY THAT IS EXPENSIVE ON THIS DESK SPECIFICALLY, AND NOT MERELY UNTIDY:

  1. This desk's own accounting says 107 of 201 refutations -- 53% -- were MEASUREMENT failures
     (data quality plus wrong construction), not absent alpha (docs/DESK_BRIEF.md). So the
     near-misses being discarded are disproportionately the FIXABLE ones. Discarding them is not
     pruning a dead branch, it is throwing away the half of the pile the desk already knows is
     mostly repairable.
  2. Lesson L0042: a candidate dropped before scoring is not a small loss, it is an UNMEASURED one.
     A near-miss with no ledger entry cannot be counted, cannot be ranked, and cannot be re-run
     when the data that would have settled it finally arrives.
  3. The scale is not hypothetical. The 2026-08-01 campaign screened 129 candidates and produced
     ZERO survivors; data/forward_slots.json has never existed. Whatever fraction of those 129 sat
     just under a bar, the desk cannot say -- because nothing wrote it down. That is the current
     state this module changes.

WHAT THIS MODULE IS NOT, and this is the load-bearing sentence in the file:

    IT CHANGES NO VERDICT. Every candidate that reaches `triage()` has ALREADY FAILED. Nothing here
    exposes a pass, a promotion, a slot, or a size; `NearMissVerdict.__bool__` is hard-wired to
    False precisely so that `if triage(...)` can never be misread as an approval. NEAR_MISS is a
    label on a corpse's file, not a resurrection. The candidate is still failed when this module is
    done with it; the only thing that changed is that the desk now has a record.

THE THREE CLASSES, and why the split is the same one screen_admission already uses:

  STRUCTURAL_DEAD  it failed a gate that NO amount of re-measurement repairs. The gate list is
                   IMPORTED from libs/validation/screen_admission (`STRUCTURAL_GATES`) and never
                   restated here -- two copies of that list would drift, and the copy that drifted
                   loose would be the one quietly reclassifying a dead mechanism as fixable.
  NEAR_MISS        every failure is statistical AND the worst shortfall is inside
                   MAX_NEAR_MISS_SHORTFALL. Worth re-measuring or re-engineering.
  FAR_MISS         it failed only statistical gates but missed by more than that -- and, equally,
                   anything the module could not SCORE. See the unknown-input rule below.

THE UNKNOWN-INPUT RULE. A failed gate whose metric or threshold was not supplied cannot be scored,
and the tempting behaviour -- treat the missing number as a zero shortfall -- would classify the
least-measured candidates as the closest to passing. That is the `beats_baselines` defect exactly:
it returned True for every candidate for months because no caller ever supplied its input.
UNMEASURED IS NOT NEAR. So an unscoreable failure yields a NaN shortfall, is named in
`unmeasured_gates`, and BLOCKS the NEAR_MISS label. It still lands in the ledger with a hint saying
which input to supply, so nothing is killed silently -- the record is the point.

THE ONE PLACE THE IMPORTED LIST IS UNCOMFORTABLE, stated rather than papered over. `sample_adequacy`
is carried in STRUCTURAL_GATES, yet it is the one structural failure that MORE DATA genuinely does
repair. This module does not fork the list to fix that -- a divergent copy is the worse defect -- so
such a candidate is still classified STRUCTURAL_DEAD and can never be a NEAR_MISS. What it does
instead is set `re_runnable`, a LEDGER flag and not a verdict, so the candidate is re-queued when
the sample grows. The classification is unchanged; only the re-run queue knows the difference.

STATUS. DRAFTED, in this desk's sense: it has tests and no production importer yet, exactly like
`screen_admission` alongside which it is meant to run. The call site it is shaped for is the
screen's REJECT path -- everything `admit()` returns as `blocked` or `ranked_out` -- and it is
deliberately a pure function of already-computed gate results so that wiring it there cannot
perturb anything upstream of it.
"""

from __future__ import annotations

import json
import math
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from libs.core.time import to_iso8601, utcnow
from libs.validation.screen_admission import STATISTICAL_GATES, STRUCTURAL_GATES

__all__ = [
    "CLASSIFICATIONS",
    "DATA_REPAIRABLE_STRUCTURAL",
    "FAR_MISS",
    "GATE_HINTS",
    "MAX_NEAR_MISS_SHORTFALL",
    "NEAR_MISS",
    "NEAR_MISS_FRACTION",
    "NO_FAILURE_RECORDED",
    "STRUCTURAL_DEAD",
    "GateShortfall",
    "NearMissVerdict",
    "Threshold",
    "all_hints",
    "improvement_hint",
    "log_near_misses",
    "read_near_miss_ledger",
    "relative_shortfall",
    "triage",
]

#: THE PROVENANCE, verbatim: "near-submittable = maybe 80% of the submission metrics ... it's very
#: much possible to make it submittable" -- WorldQuant BRAIN webinar transcript, 2026-08-01
#: (principal-supplied), the same source as `BRAIN_NEAR_SUBMITTABLE_FRACTION`. Marked APPROXIMATE
#: there: it is a spoken aside ("maybe 80%"), not a slide, and it is used here as a TRIAGE BOUNDARY
#: -- which candidate gets a second look -- never as a threshold on evidence. Nothing passes or
#: fails because of this number.
#:
#: WHY IT IS RESTATED HERE RATHER THAN IMPORTED. brain_calibration's own docstring forbids any
#: decision path from importing it, so that an external number cannot quietly become a threshold.
#: This module is not a decision path, but the rule is honoured literally and drift is prevented
#: the other way: tests/validation/test_near_miss.py asserts this constant EQUALS
#: brain_calibration.BRAIN_NEAR_SUBMITTABLE_FRACTION, so the two cannot separate silently. A single
#: fenced scalar can be handled that way; a LIST (see STRUCTURAL_GATES, imported above) cannot,
#: which is why the two are treated differently.
NEAR_MISS_FRACTION = 0.80

#: DERIVED, never spoken: a candidate at 80% of the bar has missed it by 20% OF THE BAR. Expressed
#: as a shortfall because that is the quantity `triage` actually computes and ranks on, and it is
#: symmetric across gate direction, which the raw "fraction attained" is not (see
#: `relative_shortfall`).
MAX_NEAR_MISS_SHORTFALL = 1.0 - NEAR_MISS_FRACTION

NEAR_MISS = "NEAR_MISS"
FAR_MISS = "FAR_MISS"
STRUCTURAL_DEAD = "STRUCTURAL_DEAD"

#: Returned when the caller hands in a candidate with no failed gate at all. This is NOT a pass and
#: must never be read as one -- this module has no pass verdict and cannot issue one. It exists so a
#: caller bug (triaging a candidate that never failed) surfaces as its own label instead of being
#: folded into FAR_MISS, where it would be invisible.
NO_FAILURE_RECORDED = "NO_FAILURE_RECORDED"

CLASSIFICATIONS: tuple[str, ...] = (NEAR_MISS, FAR_MISS, STRUCTURAL_DEAD, NO_FAILURE_RECORDED)

#: Structural gates that MORE DATA repairs. See the module docstring: this does not reclassify
#: anything -- a candidate failing one of these is still STRUCTURAL_DEAD and still cannot be a
#: NEAR_MISS -- it only marks the ledger entry as worth re-running when the sample grows.
DATA_REPAIRABLE_STRUCTURAL: tuple[str, ...] = ("sample_adequacy",)

#: A threshold whose magnitude is below this cannot serve as the denominator of a relative
#: shortfall: dividing by ~0 manufactures an arbitrarily large "miss" from an arbitrarily small
#: absolute gap, which is the same defect class as the `> 0` variance guard that shipped a 1.4e31
#: prediction premium here on 2026-08-01. The fix is a MEANINGFUL magnitude floor, not a tighter
#: comparison against zero. Gates thresholded at exactly zero (an "expected value > 0" shape) are
#: therefore reported UNMEASURABLE rather than scored -- and an unmeasurable shortfall blocks
#: NEAR_MISS.
_THRESHOLD_MAGNITUDE_FLOOR = 1e-6

#: The 0.80/0.20 boundary is hit exactly by realistic inputs -- Sharpe 0.9 against a 1.0 bar, or a
#: reality-check p of 0.06 against 0.05 -- and both compute to 0.19999999999999998 in binary
#: floating point. Without this tolerance the canonical BRAIN example would classify FAR_MISS.
_BOUNDARY_TOLERANCE = 1e-12


@dataclass(frozen=True)
class Threshold:
    """The bar a gate had to clear, plus WHICH WAY the gate points.

    `higher_is_better` is mandatory in spirit even though it carries a default, because getting it
    wrong silently inverts every number downstream: a PBO of 0.60 against a 0.20 bar would be
    scored as a 67% overshoot in the candidate's favour rather than a 200% miss. The same sign
    error is the one `brain_calibration._direction` exists to prevent on the reporting side, where
    it would have turned "this desk is 3x more concentrated" into "3x safer".
    """

    value: float
    higher_is_better: bool = True
    label: str = ""


@dataclass(frozen=True)
class GateShortfall:
    """How far one FAILED gate was from its bar, in units of the bar.

    `shortfall` is NaN, and `measured` is False, whenever the gap could not be computed honestly --
    a missing metric, a missing threshold, a non-finite value, or a threshold too close to zero to
    divide by. NaN is used rather than a large sentinel so that any arithmetic performed on it
    stays NaN instead of silently becoming a plausible-looking number.
    """

    gate: str
    metric: float
    threshold: float
    higher_is_better: bool
    shortfall: float
    structural: bool
    measured: bool
    note: str = ""

    def summary(self) -> str:
        direction = "needed >=" if self.higher_is_better else "needed <="
        if not self.measured:
            return f"{self.gate}: UNMEASURED ({self.note})"
        return (f"{self.gate}: {self.metric:.4g} vs {direction} {self.threshold:.4g} "
                f"-- short by {self.shortfall * 100:.1f}% of the bar")


def relative_shortfall(metric: float, threshold: Threshold) -> float:
    """How far `metric` fell short of `threshold`, as a fraction of the threshold's magnitude.

        higher-is-better:  (threshold - metric) / |threshold|
        lower-is-better:   (metric - threshold) / |threshold|

    Zero when the gate was actually cleared; negative is never returned, because a cleared gate is
    not this module's business and reporting a negative shortfall would let a passing gate drag a
    "worst shortfall" downwards and manufacture a NEAR_MISS out of one bad gate plus several good
    ones. Callers only ever pass FAILED gates here; the clamp makes the misuse harmless rather than
    subtly wrong.

    WHY BOTH DIRECTIONS ARE MEASURED IN UNITS OF THE THRESHOLD, rather than as "fraction of the bar
    attained". The attained-fraction reading is natural for a higher-is-better gate (Sharpe 0.9 of
    a 1.0 bar = 80%) but inverts awkwardly for a lower-is-better one, where the symmetric-looking
    `threshold / metric` compresses large overshoots -- a PBO of 1.0 against a 0.20 bar would read
    as "20% attained", i.e. bounded, when the true miss is unbounded. Distance from the bar in
    units of the bar is the same scale in both directions, is unbounded in both directions, and
    makes 0.9-vs-1.0 and 0.055-vs-0.05 directly comparable, which is what the ranking needs.

    Returns NaN when the arithmetic would be meaningless: a non-finite input, or a threshold whose
    magnitude is below `_THRESHOLD_MAGNITUDE_FLOOR`. NaN is a refusal to answer, not a big number.
    """
    m, t = float(metric), float(threshold.value)
    if not math.isfinite(m) or not math.isfinite(t):
        return math.nan
    if abs(t) < _THRESHOLD_MAGNITUDE_FLOOR:
        return math.nan
    gap = (t - m) if threshold.higher_is_better else (m - t)
    return max(0.0, gap / abs(t))


@dataclass(frozen=True)
class NearMissVerdict:
    """The triage of ONE already-failed candidate. Carries no authority to change its fate.

    `shortfalls` is ranked CLOSEST FIRST, so `shortfalls[0]` (equivalently `closest_gate`) is the
    single gate a re-measurement should attack first. Unmeasurable gates sort last regardless of
    anything else: an un-scored gate must never present itself as the closest one.
    """

    name: str
    classification: str
    failed_gates: tuple[str, ...]
    structural_failures: tuple[str, ...]
    statistical_failures: tuple[str, ...]
    unknown_gates: tuple[str, ...]
    unmeasured_gates: tuple[str, ...]
    shortfalls: tuple[GateShortfall, ...]
    worst_shortfall: float
    reason: str

    def __bool__(self) -> bool:
        """ALWAYS FALSE. Every candidate reaching this module has already failed.

        Hard-wired rather than left to Python's default object truthiness because the default is
        True, and `if triage(...):` is a one-character-plausible way for a caller to turn a triage
        label into an approval. There is no input to this module that produces a truthy result.
        """
        return False

    @property
    def closest_gate(self) -> str | None:
        """The single measured gate nearest to passing, or None if none could be scored."""
        for s in self.shortfalls:
            if s.measured:
                return s.gate
        return None

    @property
    def re_runnable(self) -> bool:
        """Whether re-measurement could plausibly change this candidate's fate.

        True when nothing structural blocks it, and ALSO true when the only structural blocks are
        in DATA_REPAIRABLE_STRUCTURAL -- `sample_adequacy` fails today and passes in six months
        with no change to the mechanism. This is a re-run QUEUE flag on a ledger row. It is not a
        verdict, it does not appear in `classification`, and a STRUCTURAL_DEAD candidate stays
        STRUCTURAL_DEAD whatever this says.
        """
        return all(g in DATA_REPAIRABLE_STRUCTURAL for g in self.structural_failures)

    def summary(self) -> str:
        worst = ("unmeasurable" if not math.isfinite(self.worst_shortfall)
                 else f"{self.worst_shortfall * 100:.1f}% of the bar")
        return (f"{self.name}: {self.classification} -- {len(self.failed_gates)} failed gate(s), "
                f"worst miss {worst}, closest {self.closest_gate or 'n/a'}")

    def to_record(self, *, as_of: str) -> dict[str, Any]:
        """One JSONL row. NaN is emitted as null -- `json.dumps` writes a bare NaN happily and no
        conforming parser downstream will read it back."""
        return {
            "as_of": as_of,
            "name": self.name,
            "classification": self.classification,
            "re_runnable": self.re_runnable,
            "failed_gates": list(self.failed_gates),
            "structural_failures": list(self.structural_failures),
            "statistical_failures": list(self.statistical_failures),
            "unknown_gates": list(self.unknown_gates),
            "unmeasured_gates": list(self.unmeasured_gates),
            "worst_shortfall": _jsonable(self.worst_shortfall),
            "closest_gate": self.closest_gate,
            "shortfalls": [
                {
                    "gate": s.gate,
                    "metric": _jsonable(s.metric),
                    "threshold": _jsonable(s.threshold),
                    "higher_is_better": s.higher_is_better,
                    "shortfall": _jsonable(s.shortfall),
                    "structural": s.structural,
                    "measured": s.measured,
                    "note": s.note,
                }
                for s in self.shortfalls
            ],
            "improvement_hint": improvement_hint(self),
            "near_miss_fraction": NEAR_MISS_FRACTION,
            "reason": self.reason,
        }


def _jsonable(x: float) -> float | None:
    return None if not math.isfinite(x) else float(x)


def _rank_key(s: GateShortfall) -> tuple[int, float, str]:
    """Closest first; unmeasured last. `not s.measured` leads the key so no NaN ever reaches the
    float comparison -- NaN sorts unpredictably and would scatter unmeasured gates through the
    ranking rather than parking them at the end."""
    return (0 if s.measured else 1, s.shortfall if s.measured else math.inf, s.gate)


def triage(gates: Mapping[str, bool], metrics: Mapping[str, float],
           thresholds: Mapping[str, Threshold], *, name: str = "?") -> NearMissVerdict:
    """Classify an ALREADY-FAILED candidate as NEAR_MISS / FAR_MISS / STRUCTURAL_DEAD.

    `gates` maps gate name -> cleared?; only the False entries are examined. `metrics` and
    `thresholds` supply, per failed gate, the value measured and the bar it had to clear.

    THE ORDER OF THE BRANCHES IS THE SAFETY PROPERTY, and each one is locked by a test:

      1. ANY structural failure -> STRUCTURAL_DEAD, first, before a single shortfall is compared.
         A mechanism with no story for who is forced to trade against you does not become fixable
         by missing narrowly; there is nothing to fix. This ordering is why "however small its
         shortfall" is testable as an invariant rather than an accident of the numbers.
      2. No failed gate at all -> NO_FAILURE_RECORDED, which is a caller bug, not a pass.
      3. An unrecognised gate name, or a failure that could not be SCORED -> FAR_MISS. Unknown must
         not land in the favourable class. It is deliberately not STRUCTURAL_DEAD either: calling a
         thing structurally dead on no evidence tells the desk to stop working on it, and on a desk
         where 53% of refutations are measurement failures that is the expensive direction to err.
      4. Everything else: NEAR_MISS iff the WORST measured shortfall is within
         MAX_NEAR_MISS_SHORTFALL. Worst, not mean -- a candidate that missed one gate by 2% and
         another by 300% is not 151% away from submittable, it is 300% away, and averaging would
         let a pile of nearly-passed gates hide a catastrophic one.

    Returns a verdict that is always falsy. It classifies; it never promotes.
    """
    failed = tuple(g for g, ok in gates.items() if not ok)
    structural = tuple(g for g in failed if g in STRUCTURAL_GATES)
    statistical = tuple(g for g in failed if g in STATISTICAL_GATES)
    unknown = tuple(g for g in failed
                    if g not in STRUCTURAL_GATES and g not in STATISTICAL_GATES)

    scored: list[GateShortfall] = []
    for g in failed:
        thr = thresholds.get(g)
        raw = metrics.get(g)
        if thr is None or raw is None:
            missing = "no threshold supplied" if thr is None else "no metric supplied"
            scored.append(GateShortfall(
                gate=g, metric=math.nan, threshold=math.nan,
                higher_is_better=True if thr is None else thr.higher_is_better,
                shortfall=math.nan, structural=g in STRUCTURAL_GATES, measured=False,
                note=f"{missing}; UNMEASURED is not NEAR"))
            continue
        sf = relative_shortfall(raw, thr)
        measured = math.isfinite(sf)
        note = "" if measured else (
            f"threshold {thr.value:.3g} is below the {_THRESHOLD_MAGNITUDE_FLOOR:g} magnitude "
            "floor or an input is non-finite, so a relative shortfall would be meaningless")
        scored.append(GateShortfall(
            gate=g, metric=float(raw), threshold=float(thr.value),
            higher_is_better=thr.higher_is_better, shortfall=sf,
            structural=g in STRUCTURAL_GATES, measured=measured, note=note))

    ranked = tuple(sorted(scored, key=_rank_key))
    unmeasured = tuple(s.gate for s in ranked if not s.measured)
    measured_gaps = [s.shortfall for s in ranked if s.measured]
    worst = max(measured_gaps) if measured_gaps else math.nan

    if structural:
        cls = STRUCTURAL_DEAD
        reason = (
            f"STRUCTURAL_DEAD: failed {', '.join(structural)}. A structural gate asks whether the "
            "thing can be traded at all and whether there is any reason it should work -- no "
            "amount of re-measurement repairs that, so the size of the miss is irrelevant and is "
            "not consulted.")
        if all(g in DATA_REPAIRABLE_STRUCTURAL for g in structural):
            reason += (" Flagged re-runnable: every structural failure here is one that a LARGER "
                       "SAMPLE repairs, so the ledger re-queues it when the data exists. The "
                       "classification is unchanged.")
    elif not failed:
        cls = NO_FAILURE_RECORDED
        reason = ("NO_FAILURE_RECORDED: no gate is marked failed. This module triages candidates "
                  "that ALREADY FAILED and has no pass verdict to give -- this label is a caller "
                  "bug surfacing, not an approval.")
    elif unknown:
        cls = FAR_MISS
        reason = (
            f"FAR_MISS: {', '.join(unknown)} is not a recognised gate, so it cannot be shown to be "
            "statistical. An unrecognised failure must not buy the favourable label; add the gate "
            "to screen_admission's STRUCTURAL_GATES or STATISTICAL_GATES to make it triageable.")
    elif unmeasured:
        cls = FAR_MISS
        reason = (
            f"FAR_MISS: {', '.join(unmeasured)} failed but could not be scored, so the candidate "
            "is not DEMONSTRATED to be close. Treating a missing input as a zero shortfall is the "
            "beats_baselines defect -- it returned True for every candidate for months because no "
            "caller supplied its input. Supply the metric and threshold and re-triage.")
    elif worst <= MAX_NEAR_MISS_SHORTFALL + _BOUNDARY_TOLERANCE:
        cls = NEAR_MISS
        reason = (
            f"NEAR_MISS: every failure is statistical and the worst is {worst * 100:.1f}% of its "
            f"bar, inside the {MAX_NEAR_MISS_SHORTFALL * 100:.0f}% band. The candidate is still "
            "FAILED; it is recorded as worth re-measuring or re-engineering rather than discarded.")
    else:
        cls = FAR_MISS
        reason = (
            f"FAR_MISS: worst statistical shortfall is {worst * 100:.1f}% of its bar, outside the "
            f"{MAX_NEAR_MISS_SHORTFALL * 100:.0f}% band. Recorded so the distance is countable, "
            "but it is not a near-term work item.")

    return NearMissVerdict(
        name=name, classification=cls, failed_gates=failed, structural_failures=structural,
        statistical_failures=statistical, unknown_gates=unknown, unmeasured_gates=unmeasured,
        shortfalls=ranked, worst_shortfall=worst, reason=reason)


# -------------------------------------------------------------------------------------------
# Hints. EVERY string this module can emit as advice lives in this section, and every one of them
# is checked by tests/validation/test_near_miss.py against a banned vocabulary. A hint that says
# "consider a lower bar" is not a mild wording problem on this desk -- it is the exact mechanism by
# which a gate gets relaxed to manufacture survivors, arriving as helpful-sounding prose. The rule
# these are written to: a hint may ask for MORE MEASUREMENT (more data, a longer sample, an honest
# trial count, a real cost model, correct alignment) or a BETTER MECHANISM. It may never ask for a
# different bar. The banned vocabulary lives in the TEST, not here, so that a hint cannot be
# legalised by editing the guard alongside the violation.
# -------------------------------------------------------------------------------------------

GATE_HINTS: dict[str, str] = {
    # ---- statistical: re-measurement or re-engineering can genuinely move these -------------
    "dsr": (
        "Deflated Sharpe is a function of sample length AND the number of trials it is deflated "
        "for. Extend the sample, and check the trial count being charged is the number of "
        "hypotheses actually tested rather than every variant ever fitted -- an inflated trial "
        "count deflates a Sharpe the candidate genuinely earned."),
    "pbo": (
        "Probability of backtest overfitting is driven by how much the parameter set is tuned per "
        "split. Re-fit with fewer free parameters, or with parameters chosen once and held fixed "
        "across splits, and confirm the splits are purged and embargoed so the same trade is not "
        "in both halves."),
    "reality_check": (
        "White's reality check compares the candidate against the best of the null over the FULL "
        "set of strategies searched. Supply the complete competing set and more bootstrap "
        "resamples; a truncated set and a short bootstrap both make the null look stronger than "
        "it is."),
    "walk_forward": (
        "Walk-forward efficiency measures whether the fit survives being re-fitted forward. Add "
        "history so there are more folds, and make the refit cadence match how the desk would "
        "actually re-parameterise in production rather than an idealised schedule."),
    "cpcv": (
        "Combinatorial purged cross-validation fails when leakage crosses the fold boundary. "
        "Verify the purge window covers the full holding period and the embargo covers the "
        "signal's lookback, then re-run on more history."),
    "not_too_lucky": (
        "The luck check flags a result carried by a handful of observations. Re-measure with the "
        "outlier bars retained but the position sized as it would really have been, and confirm "
        "the fills are executable rather than a mid-price fantasy -- an honest cost model usually "
        "moves this more than any parameter does."),
    "beats_baselines": (
        "THE MEASURED CASE ON THIS DESK: beats_baselines returned True for every candidate for "
        "months because no caller ever supplied its input. Supply the baseline series -- buy-and- "
        "hold, the cohort's own median, and the naive momentum variant -- and re-run. An "
        "unsupplied comparison is unmeasured, never satisfied."),
    # ---- structural: measurement does not repair these; the mechanism has to change ---------
    "economic_mechanism": (
        "There is no story for WHO is forced to trade against this and WHAT forces them. That is "
        "not a measurement shortfall, it is the absence of a reason for the edge to exist, and it "
        "makes the result a data artifact by default. Name the constrained counterparty and the "
        "constraint, or work on a different mechanism."),
    "expected_value": (
        "Expectancy is negative. Re-measure once with the desk's real cost model -- funding every "
        "eight hours, fees, and slippage applied per fill rather than post-hoc -- because a "
        "mis-applied cost model has flipped this sign before. If expectancy is still negative net "
        "of honest costs, the mechanism must change; forward-testing it is a paid way to lose."),
    "capacity": (
        "The mechanism cannot absorb the desk's size. Re-measure capacity against real book depth "
        "and the participation rate actually used, then either find the edge in a deeper part of "
        "the universe or accept that it is untradeable here at any confidence level."),
    "fragility": (
        "Tail behaviour that would damage the book. This is a safety property, not a p-value, so "
        "no sample size settles it. Change the mechanism -- cap the exposure that produces the "
        "tail, or hedge it explicitly -- and re-measure the stressed path afterwards."),
    "break_even_win_rate": (
        "The per-trade arithmetic does not close: p* = |avg_loss| / (avg_win + |avg_loss|) sits "
        "above the realised win rate. The desk's own worked case is p* = 35.4% against a realised "
        "41.3%, and that 5.9-point gap over 758 trades WAS the entire 24.9x return. Grow the "
        "average winner or cut the average loser -- the exit logic is the lever here, not the "
        "entry signal."),
    "sample_adequacy": (
        "There is not enough data to measure this candidate yet. The one structural failure that "
        "time alone repairs: re-queue it and re-run when the sample has grown. Nothing about the "
        "mechanism has been refuted."),
}

_UNMEASURED_HINT = (
    "FIRST, SUPPLY THE MISSING INPUT: {gates} failed with no metric or no usable threshold to "
    "score against, so how close this came is unknown rather than known-to-be-far. An unsupplied "
    "input is unmeasured, never passed.")

_UNKNOWN_GATE_HINT = (
    "FIRST, NAME THE GATE: {gates} is not in screen_admission's STRUCTURAL_GATES or "
    "STATISTICAL_GATES, so this module cannot tell whether re-measurement could help. Register it "
    "in the correct list and re-triage.")

_NO_FAILURE_HINT = (
    "Nothing to triage: no gate is marked failed. This module classifies candidates that already "
    "failed and issues no pass verdict; check what the caller handed in.")

_NO_HINT = (
    "No gate-specific guidance is registered for the failing gate. Add one to GATE_HINTS keyed to "
    "that gate rather than acting on a guess.")

_NEAR_MISS_PREFIX = (
    "NEAR-MISS at {pct:.1f}% of the bar on '{gate}', which is the single closest gate and "
    "therefore where re-measurement buys the most. This candidate remains FAILED; it is queued "
    "for improvement, not admitted.")

_FAR_MISS_PREFIX = (
    "FAR MISS: '{gate}' is the closest gate and still {pct:.1f}% of the bar away. Recorded so the "
    "distance is countable and re-checkable, but the work below is a bigger job than a re-run.")

_STRUCTURAL_PREFIX = (
    "STRUCTURALLY DEAD on '{gate}'. No sample size and no re-measurement changes this verdict; "
    "what follows is what would have to be TRUE of the mechanism instead.")


def improvement_hint(verdict: NearMissVerdict) -> str:
    """What would have to CHANGE for this candidate to clear the bar it missed.

    Keyed to the specific gate: the closest measured statistical gate when there is one, the
    blocking structural gate when the candidate is structurally dead, and an explicit
    supply-the-input instruction when the failure could not be scored at all.

    THE INVARIANT, asserted over every hint this module can emit: no hint ever suggests moving a
    threshold. Every one asks for more or better MEASUREMENT (data, sample length, honest trial
    count, real cost model, correct alignment) or a better MECHANISM. Relaxing a statistical gate
    to manufacture survivors is the failure this desk has been burned by and forbids outright, and
    it would arrive here disguised as a helpful suggestion, which is why the ban is enforced by a
    keyword test over `all_hints()` rather than by intention.
    """
    if verdict.classification == NO_FAILURE_RECORDED:
        return _NO_FAILURE_HINT

    if verdict.structural_failures:
        gate = next((s.gate for s in verdict.shortfalls if s.structural),
                    verdict.structural_failures[0])
        return f"{_STRUCTURAL_PREFIX.format(gate=gate)} {GATE_HINTS.get(gate, _NO_HINT)}"

    if verdict.unknown_gates:
        return _UNKNOWN_GATE_HINT.format(gates=", ".join(verdict.unknown_gates))

    if verdict.unmeasured_gates:
        head = _UNMEASURED_HINT.format(gates=", ".join(verdict.unmeasured_gates))
        # Still append the gate-specific guidance when SOMETHING was scoreable: the missing input
        # is the first job, but naming the second one costs nothing and is what makes the ledger
        # row actionable in one pass.
        near = verdict.closest_gate
        return head if near is None else f"{head} {GATE_HINTS.get(near, _NO_HINT)}"

    closest = verdict.closest_gate
    if closest is None:
        return _NO_HINT
    pct = next(s.shortfall for s in verdict.shortfalls if s.gate == closest) * 100.0
    prefix = (_NEAR_MISS_PREFIX if verdict.classification == NEAR_MISS else _FAR_MISS_PREFIX)
    return f"{prefix.format(gate=closest, pct=pct)} {GATE_HINTS.get(closest, _NO_HINT)}"


def all_hints() -> tuple[str, ...]:
    """Every advice string this module can emit, for exhaustive checking by the test suite.

    Enumerated rather than sampled ON PURPOSE. A banned-vocabulary test that only inspects the
    hints a handful of constructed verdicts happen to reach would pass while an unreachable-today
    hint sat in the table saying "consider a lower bar", waiting for the branch that emits it. The
    test also asserts this covers every gate in STRUCTURAL_GATES + STATISTICAL_GATES, so adding a
    gate without a hint fails CI rather than silently degrading to _NO_HINT.
    """
    return (*GATE_HINTS.values(), _UNMEASURED_HINT, _UNKNOWN_GATE_HINT, _NO_FAILURE_HINT, _NO_HINT,
            _NEAR_MISS_PREFIX, _FAR_MISS_PREFIX, _STRUCTURAL_PREFIX)


# -------------------------------------------------------------------------------------------
# The ledger. The whole point of the module: a near-miss that leaves no record is the status quo.
# -------------------------------------------------------------------------------------------


def log_near_misses(verdicts: Iterable[NearMissVerdict], path: Path | str,
                    *, as_of: str | None = None) -> int:
    """APPEND triage rows to a JSONL ledger. Returns how many rows were written.

    APPEND, never rewrite. The value of this file is that it ACCUMULATES: a near-miss recorded in
    March is re-runnable in September when the sample that would have settled it exists, and a
    ledger that is overwritten each campaign has exactly the memory the desk already lacks.

    EVERY verdict handed in is written, including FAR_MISS and STRUCTURAL_DEAD, with its
    classification and `re_runnable` flag on the row. Filtering at WRITE time is how the current
    silent death happens -- the defect being fixed is that no record was written at all -- and a
    reader wanting only the work queue filters on `re_runnable`, which costs nothing and keeps the
    denominator. Without the denominator "we had 8 near-misses" is unreadable; with it, the ratio
    of near to far to dead is itself a measurement of where the campaign died.

    THE TRAILING-NEWLINE REPAIR IS NOT COSMETIC. If a previous writer was killed mid-line, the file
    ends without a newline, and appending would splice a new record onto the tail of the truncated
    one -- corrupting a good row with a bad one and losing BOTH. A separator is written first when
    the existing file does not end in a newline, which leaves the truncated line corrupt (it
    already was) and the new row intact.
    """
    stamp = as_of if as_of is not None else to_iso8601(utcnow())
    rows = [v.to_record(as_of=stamp) for v in verdicts]
    if not rows:
        return 0
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    needs_separator = False
    if p.exists():
        try:
            with p.open("rb") as fh:
                if fh.seek(0, 2) > 0:
                    fh.seek(-1, 2)
                    needs_separator = fh.read(1) != b"\n"
        except OSError:
            needs_separator = False
    with p.open("a", encoding="utf-8") as fh:
        if needs_separator:
            fh.write("\n")
        for row in rows:
            fh.write(json.dumps(row, sort_keys=True) + "\n")
    return len(rows)


def read_near_miss_ledger(path: Path | str) -> tuple[dict[str, Any], ...]:
    """Read the ledger back, SKIPPING lines that will not parse.

    A ledger that raises on one bad line is a ledger that loses every good line after it, and the
    bad line is usually the half-written tail of a process that was killed -- i.e. exactly the
    moment the surviving history matters most. Corrupt lines are dropped silently here rather than
    repaired or guessed at; the count of parsed rows is the honest output, and a caller comparing
    it against the file's line count can see the loss.

    A missing file returns an empty tuple: the ledger not existing yet is the desk's CURRENT state
    (data/forward_slots.json has never existed either) and is not an error.
    """
    p = Path(path)
    if not p.exists():
        return ()
    try:
        text = p.read_text("utf-8")
    except OSError:
        return ()
    out: list[dict[str, Any]] = []
    for line in text.splitlines():
        s = line.strip()
        if not s:
            continue
        try:
            obj = json.loads(s)
        except json.JSONDecodeError:
            continue
        # A parsed non-object is as unusable as an unparseable line -- a bare number or list has no
        # classification to read -- so it is dropped on the same terms rather than crashing later.
        if isinstance(obj, dict):
            out.append(obj)
    return tuple(out)

```

### libs\validation\state_conditional.py
```python
"""F3's SECOND BRANCH — validating a mechanism that is only supposed to work in some states.

WHY A BRANCH AND NOT A LOOSENING. `libs/validation/gate_power.py` measured what F3 actually does
to a planted conditional edge, and the number is not a tuning problem::

    planted effect      0.0    0.01   0.02   0.05   0.10   0.20   0.40
    STABLE edge kept   0.23   0.37   0.45   0.78   1.00   1.00   1.00
    CONDITIONAL kept   0.24   0.32   0.35   0.44   0.50   0.55   0.51

A stable edge saturates: make it big enough and F3 always keeps it. A CONDITIONAL edge asymptotes
at about one half, and it does so for a structural reason that no amount of effect size fixes. F3
requires both walk-forward arms net-positive. When the mechanism is genuinely inactive in one arm,
that arm is noise, and noise is positive by chance roughly half the time REGARDLESS of how strong
the edge is in the arm where it does fire. The gate is not underpowered against conditional alpha;
it is measuring the wrong thing about it, and its ~50% ceiling is a coin flip dressed as a test.

**THE WRONG FIX IS TO LOWER F3, AND IT IS WRONG FOR A REASON WORTH WRITING DOWN.** F3's both-arms
rule is exactly what stops a global claim being made on one lucky half of the sample. Relaxing it
globally to rescue conditional mechanisms would open that hole for every candidate, including the
overwhelming majority that are noise. So global F3 is untouched. Conditional mechanisms take a
DIFFERENT and in most respects HARDER path, and they must declare which path they are on BEFORE
untouched data is opened.

**THE ONE THING THIS MODULE EXISTS TO MAKE IMPOSSIBLE.** The sequence::

    candidate fails
        -> search its results for a slice where it worked
        -> declare that slice a "regime"
        -> call the candidate rescued

is not validation, it is the multiple-testing problem with a narrative attached, and it is the
most attractive defect on this desk because the story is always available after the fact. A state
declared after the failure was observed is a POST-HOC RESCUE and this module returns
`POST_HOC_RESCUE` for it every time, no matter how good the conditional numbers are. The legitimate
move is to emit a NEW preregistered hypothesis and test it on data nobody has touched, and
`rescue_to_new_hypothesis` builds exactly that object.

Classifies and reports. Promotes nothing. The gauntlet keeps its promotion authority; a conditional
mechanism that passes here has earned the RIGHT TO BE TESTED, not the right to be traded.
"""

from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass, field

__all__ = [
    "MIN_STATE_OCCURRENCES",
    "MIN_STATE_SHARE",
    "REQUIREMENTS",
    "ConditionalEvidence",
    "Preregistration",
    "adjudicate",
    "requirement_status",
    "rescue_to_new_hypothesis",
    "state_recurrence_ok",
    "summarise",
]

#: Distinct, non-overlapping occurrences of the state required before any conditional claim.
#: NOT a count of bars: a state that occurred once and lasted six months is one observation of one
#: episode, and a conditional mechanism validated on it is a claim about that episode.
MIN_STATE_OCCURRENCES: int = 8

#: The state must also be a real slice rather than a hand-picked window. Below this share of the
#: sample the "regime" is more plausibly a selected subset than a recurring market condition.
MIN_STATE_SHARE: float = 0.05

#: The eight things a conditional mechanism owes, from the specification. Each maps to a field on
#: `ConditionalEvidence`, so a missing requirement is a missing MEASUREMENT rather than a missing
#: paragraph -- prose cannot satisfy any of these.
REQUIREMENTS: tuple[str, ...] = (
    "EX_ANTE_STATE_DEFINITION",
    "AS_OF_OBSERVABILITY",
    "MECHANISM_FOR_CONDITIONALITY",
    "STATE_RECURRENCE",
    "CLASSIFIER_STABILITY",
    "CONDITIONAL_COSTS",
    "TRANSITION_ANALYSIS",
    "UNTOUCHED_OOS",
)


@dataclass(frozen=True)
class Preregistration:
    """The declaration that must exist BEFORE untouched data is opened.

    `sequence` is the ordering device and it is the whole mechanism. It is a monotone counter of
    evaluation events on this desk -- a preregistration whose sequence is greater than the sequence
    at which the candidate was first evaluated was written AFTER the results were seen, and no
    amount of good faith changes what that does to the error rate.
    """

    hypothesis_id: str
    #: GLOBAL_MECHANISM or STATE_CONDITIONAL_MECHANISM. Declared, not inferred from results.
    mechanism_class: str
    #: Machine-readable state predicate, e.g. "funding_8h_annualised > 0.35 and oi_change_24h < 0".
    #: Empty for a global mechanism.
    state_definition: str = ""
    #: Why the mechanism should be inactive outside the state. "It only worked there" is NOT a
    #: mechanism and the adjudication rejects it by name.
    conditionality_mechanism: str = ""
    #: Desk evaluation counter at the moment this was written.
    sequence: int = 0

    @property
    def is_conditional(self) -> bool:
        return self.mechanism_class == "STATE_CONDITIONAL_MECHANISM"

    @property
    def digest(self) -> str:
        """Content hash. Two preregistrations that differ in the state predicate are not the same
        preregistration, however similar their prose."""
        blob = "|".join((self.hypothesis_id, self.mechanism_class, self.state_definition,
                         self.conditionality_mechanism))
        return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:16]


@dataclass(frozen=True)
class ConditionalEvidence:
    """What was measured. Every field defaults to the UNMEASURED value, never to the passing one."""

    hypothesis_id: str
    #: Desk evaluation counter at the candidate's FIRST evaluation. Compared against the
    #: preregistration's sequence to detect a rescue.
    first_evaluated_sequence: int = 0
    #: Distinct entries into the state across the sample.
    state_occurrences: int = 0
    #: Fraction of sample bars inside the state.
    state_share: float = 0.0
    #: Can the state be computed from information available AT the decision timestamp?
    as_of_observable: bool = False
    #: Agreement of the state classifier across bootstrap/refit. 0 = unmeasured.
    classifier_stability: float = 0.0
    #: Net bps inside the state, AFTER conditional costs (a state is often a state because
    #: liquidity is different in it, and using pooled costs there is a leak).
    in_state_net_bps: float = 0.0
    #: Net bps outside the state. Expected to be ~0 for a true conditional mechanism.
    out_state_net_bps: float = 0.0
    #: Observations inside the state. Thin arms are the reason F3's second arm is a coin flip.
    in_state_n: int = 0
    out_state_n: int = 0
    #: Net bps during state TRANSITIONS. The mechanism may reverse while the state is changing,
    #: and a book that trades through transitions eats that without ever seeing it.
    transition_net_bps: float | None = None
    #: Whether conditional cost curves were used rather than pooled ones.
    conditional_costs_measured: bool = False
    #: Untouched out-of-sample net bps inside the state. None = the lockbox was never opened.
    untouched_oos_net_bps: float | None = None
    untouched_oos_n: int = 0
    notes: tuple[str, ...] = field(default_factory=tuple)


def state_recurrence_ok(ev: ConditionalEvidence) -> tuple[bool, str]:
    """Is the state a RECURRING market condition or a selected window?"""
    if ev.state_occurrences <= 0:
        return False, "state occurrences UNMEASURED -- cannot distinguish a regime from a window"
    if ev.state_occurrences < MIN_STATE_OCCURRENCES:
        return False, (
            f"{ev.state_occurrences} distinct occurrence(s) against a floor of "
            f"{MIN_STATE_OCCURRENCES}. A state that happened rarely and lasted a long time is ONE "
            "observation of one episode however many bars it contains")
    if ev.state_share < MIN_STATE_SHARE:
        return False, (
            f"the state covers {ev.state_share:.1%} of the sample, below {MIN_STATE_SHARE:.0%}. "
            "At this share a 'regime' is more plausibly a selected subset than a condition")
    return True, (f"{ev.state_occurrences} distinct occurrences over {ev.state_share:.1%} of the "
                  "sample")


def requirement_status(prereg: Preregistration,
                       ev: ConditionalEvidence) -> dict[str, tuple[bool, str]]:
    """Each of the eight requirements, measured. Order is the specification's order."""
    rec_ok, rec_why = state_recurrence_ok(ev)
    weak = ("it only worked there", "worked in that regime", "the numbers were better",
            "post hoc", "post-hoc")
    mech = prereg.conditionality_mechanism.strip()
    mech_ok = bool(mech) and not any(w in mech.lower() for w in weak)
    return {
        "EX_ANTE_STATE_DEFINITION": (
            bool(prereg.state_definition.strip()),
            "machine-readable state predicate declared" if prereg.state_definition.strip()
            else "no state predicate: a state described in prose cannot be applied as-of, and "
                 "cannot be shown to have been the same state at every occurrence"),
        "AS_OF_OBSERVABILITY": (
            ev.as_of_observable,
            "state computable at the decision timestamp" if ev.as_of_observable
            else "the state is NOT computable from information available at the decision "
                 "timestamp. A conditional edge whose condition is known only afterwards is a "
                 "description of the past, and it will backtest beautifully"),
        "MECHANISM_FOR_CONDITIONALITY": (
            mech_ok,
            f"conditionality explained: {mech[:120]}" if mech_ok
            else "no mechanism for WHY the edge should be inactive outside the state. 'It only "
                 "worked there' is the observation that needs explaining, not the explanation"),
        "STATE_RECURRENCE": (rec_ok, rec_why),
        "CLASSIFIER_STABILITY": (
            ev.classifier_stability >= 0.7,
            f"classifier agreement {ev.classifier_stability:.2f}" if ev.classifier_stability > 0
            else "state-classifier stability UNMEASURED. If the classifier relabels the same bars "
                 "differently on a refit, the 'state' is a property of the fit"),
        "CONDITIONAL_COSTS": (
            ev.conditional_costs_measured,
            "conditional cost curves applied" if ev.conditional_costs_measured
            else "pooled costs used inside a state that likely HAS different liquidity -- the "
                 "commonest way a conditional edge is manufactured out of a cost assumption"),
        "TRANSITION_ANALYSIS": (
            ev.transition_net_bps is not None,
            f"transition net {ev.transition_net_bps:+.3f}bp" if ev.transition_net_bps is not None
            else "transition periods UNMEASURED. The book trades through every entry and exit of "
                 "the state, and pays whatever happens there whether or not it was measured"),
        "UNTOUCHED_OOS": (
            ev.untouched_oos_net_bps is not None and ev.untouched_oos_n > 0,
            f"untouched OOS {ev.untouched_oos_net_bps:+.3f}bp over {ev.untouched_oos_n} obs"
            if ev.untouched_oos_net_bps is not None
            else "the lockbox was never opened. Everything above was measured on data the "
                 "hypothesis has already seen"),
    }


def adjudicate(prereg: Preregistration, ev: ConditionalEvidence) -> tuple[str, str]:
    """(verdict, why).

    POST_HOC_RESCUE | NOT_CONDITIONAL | INSUFFICIENT_STATE_EVIDENCE | CONDITIONAL_UNPROVEN |
    CONDITIONAL_VALIDATED

    The order of the checks is load-bearing: the rescue check runs FIRST and cannot be reached
    past by strong evidence, because strong evidence is precisely what a post-hoc slice search
    produces.
    """
    if prereg.hypothesis_id != ev.hypothesis_id:
        return "POST_HOC_RESCUE", (
            f"preregistration is for {prereg.hypothesis_id!r} and the evidence is for "
            f"{ev.hypothesis_id!r}. Borrowing another hypothesis's declaration is the rescue "
            "pattern with an extra step")
    if not prereg.is_conditional:
        return "NOT_CONDITIONAL", (
            f"declared {prereg.mechanism_class!r}, so global F3 applies unchanged. This branch is "
            "not available to a candidate that declared a global mechanism and then failed one")
    if prereg.sequence > ev.first_evaluated_sequence:
        return "POST_HOC_RESCUE", (
            f"the state was declared at sequence {prereg.sequence}, AFTER the candidate was first "
            f"evaluated at {ev.first_evaluated_sequence}. The slice was chosen with the results "
            "visible, so its significance is unbounded and no conditional number here can be "
            "trusted. The legitimate move is a NEW preregistered hypothesis on untouched data -- "
            "see rescue_to_new_hypothesis()")
    reqs = requirement_status(prereg, ev)
    failed = [k for k, (ok, _) in reqs.items() if not ok]
    hard = [k for k in failed if k in ("EX_ANTE_STATE_DEFINITION", "AS_OF_OBSERVABILITY",
                                       "MECHANISM_FOR_CONDITIONALITY", "STATE_RECURRENCE")]
    if hard:
        return "INSUFFICIENT_STATE_EVIDENCE", (
            f"{len(hard)} structural requirement(s) unmet: {hard}. "
            + reqs[hard[0]][1])
    if failed:
        return "CONDITIONAL_UNPROVEN", (
            f"the state is real and declared in advance, but {len(failed)} requirement(s) remain "
            f"UNMEASURED: {failed}. " + reqs[failed[0]][1] + ". This is not a kill -- it is the "
            "list of what must be measured before the claim can be cashed")
    # Every requirement measured. The economics still have to be there, and the SHAPE has to
    # match a conditional mechanism rather than a global one hiding behind a state.
    if ev.in_state_net_bps <= 0:
        return "CONDITIONAL_UNPROVEN", (
            f"in-state net {ev.in_state_net_bps:+.3f}bp is not positive. The mechanism does not "
            "fire even where it was declared to fire")
    if ev.untouched_oos_net_bps is not None and ev.untouched_oos_net_bps <= 0:
        return "CONDITIONAL_UNPROVEN", (
            f"in-state edge {ev.in_state_net_bps:+.3f}bp did not survive untouched OOS "
            f"({ev.untouched_oos_net_bps:+.3f}bp). This is the branch working as intended")
    if abs(ev.out_state_net_bps) > abs(ev.in_state_net_bps):
        return "NOT_CONDITIONAL", (
            f"out-of-state |{ev.out_state_net_bps:+.3f}|bp exceeds in-state "
            f"|{ev.in_state_net_bps:+.3f}|bp. Whatever this is, the declared state is not the "
            "condition -- send it back to global F3, which is the correct gate for it")
    return "CONDITIONAL_VALIDATED", (
        f"all eight requirements measured; in-state {ev.in_state_net_bps:+.3f}bp over "
        f"{ev.in_state_n} obs, out-of-state {ev.out_state_net_bps:+.3f}bp, untouched OOS "
        f"{ev.untouched_oos_net_bps:+.3f}bp over {ev.untouched_oos_n} obs. Earns the right to be "
        "TESTED further and sized as a conditional exposure -- not a promotion, which the "
        "gauntlet still owns")


def rescue_to_new_hypothesis(prereg: Preregistration, ev: ConditionalEvidence,
                             *, sequence_now: int) -> Preregistration:
    """Turn a post-hoc observation into a legitimate FORWARD hypothesis. §16's escape hatch.

    The observation "it worked in state X" is genuine information and throwing it away would be
    its own waste. What it is NOT is evidence about state X, because the state was chosen by
    looking. So it becomes a new preregistration, stamped at the CURRENT sequence, which can only
    ever be tested against data that arrives from here on.

    The returned object deliberately carries a different `hypothesis_id`: reusing the old one is
    how a rescued slice quietly inherits the parent's history.
    """
    return Preregistration(
        hypothesis_id=f"{prereg.hypothesis_id}__cond_{prereg.digest[:8]}",
        mechanism_class="STATE_CONDITIONAL_MECHANISM",
        state_definition=prereg.state_definition,
        conditionality_mechanism=(
            prereg.conditionality_mechanism
            or f"DERIVED FROM A POST-HOC OBSERVATION on {ev.hypothesis_id}: the mechanism for the "
               "conditionality is NOT yet stated and must be before this is tested"),
        sequence=sequence_now,
    )


def summarise(pairs: list[tuple[Preregistration, ConditionalEvidence]]) -> dict[str, object]:
    """Report shape for `data/state_conditional.json`."""
    if not pairs:
        return {"candidates": 0, "headline": (
            "no conditional candidates declared. F3's measured ~50% ceiling on conditional "
            "mechanisms is therefore UNEXERCISED, not absent -- the branch exists and nothing "
            "has used it")}
    rows = []
    for p, e in pairs:
        v, why = adjudicate(p, e)
        reqs = requirement_status(p, e)
        rows.append({
            "hypothesis_id": e.hypothesis_id,
            "verdict": v,
            "why": why,
            "prereg_digest": p.digest,
            "prereg_sequence": p.sequence,
            "first_evaluated_sequence": e.first_evaluated_sequence,
            "requirements": {k: {"met": ok, "detail": d} for k, (ok, d) in reqs.items()},
            "requirements_met": sum(1 for ok, _ in reqs.values() if ok),
            "in_state_net_bps": e.in_state_net_bps,
            "out_state_net_bps": e.out_state_net_bps,
            "untouched_oos_net_bps": e.untouched_oos_net_bps,
        })
    order = {"CONDITIONAL_VALIDATED": 0, "CONDITIONAL_UNPROVEN": 1,
             "INSUFFICIENT_STATE_EVIDENCE": 2, "NOT_CONDITIONAL": 3, "POST_HOC_RESCUE": 4}
    rows.sort(key=lambda r: order[str(r["verdict"])])
    counts: dict[str, int] = {}
    for r in rows:
        counts[str(r["verdict"])] = counts.get(str(r["verdict"]), 0) + 1
    rescues = counts.get("POST_HOC_RESCUE", 0)
    return {
        "candidates": len(pairs),
        "counts": counts,
        "rows": rows,
        "headline": (
            f"{counts.get('CONDITIONAL_VALIDATED', 0)} conditional mechanism(s) validated on "
            f"untouched data, {counts.get('CONDITIONAL_UNPROVEN', 0)} unproven, {rescues} refused "
            "as POST-HOC RESCUES" + (
                " -- a rescue is a slice chosen with the results visible, and its significance is "
                "unbounded no matter how good the numbers look" if rescues else "")),
        "note": ("Global F3 is UNCHANGED by this branch. gate_power measured F3 keeping only "
                 "~50% of planted conditional edges at every effect size, because a both-arms "
                 "rule tests noise in the arm where the mechanism is inactive. The answer is a "
                 "harder separate path for declared conditional mechanisms, never a lower bar "
                 "for everyone."),
    }


def power_gain_note(planted_kept_global: float, planted_kept_conditional: float) -> str:
    """One line quantifying what the branch is worth, for the review report.

    Deliberately a NOTE rather than a claim: the gain is only realised for candidates that declare
    conditional in advance, and nothing here estimates how many of those exist.
    """
    if planted_kept_conditional <= 0:
        return "conditional retention UNMEASURED -- run libs/validation/gate_power.py controls"
    ratio = planted_kept_global / planted_kept_conditional if planted_kept_conditional else math.inf
    return (f"F3 keeps {planted_kept_global:.0%} of planted STABLE edges and "
            f"{planted_kept_conditional:.0%} of planted CONDITIONAL ones ({ratio:.1f}x). The "
            "branch recovers that gap only for candidates that DECLARED conditional before the "
            "untouched data was opened; a candidate that declared global and then failed cannot "
            "reach it.")

```

### scripts\audit_gate_power.py
```python
#!/usr/bin/env python3
"""STATISTICAL AUDIT OF THE VALIDATION GAUNTLET -- Type I and Type II, per gate and jointly.

THE QUESTION, asked without assuming the answer: is this gate stack over-conservative,
under-conservative, or near-optimal for maximising long-run compounded return? A gate stack is not
free. Every gate buys a reduction in false positives and pays for it in false negatives, and only
the desk's own objective -- E[log wealth] -- prices that trade. Nobody had measured either side.

METHOD. One cohort is simulated per replication, ``n_true`` of its candidates carrying a genuine
edge and the rest pure noise, then scored through the REAL ``validate()`` with the REAL campaign
statistics. Auditing the live function rather than a reimplementation is the whole point: a
reimplementation would certify a model of the gauntlet, not the gauntlet. Because
``campaign_gate_stats`` is computed once and shared across the cohort's candidates, one expensive
replication yields N verdicts -- which is what makes a Monte Carlo of this size affordable at all.

Every candidate's per-gate booleans AND its continuous statistics are recorded, so Type I error,
power, leave-one-out marginal contributions, ROC curves and calibration all come from the same
pass rather than from separate runs that could disagree.

WHAT IS DELIBERATELY NOT DONE: no threshold is tuned to raise the pass rate. The output is a
measurement. Where it recommends a change, the change must improve expected OUT-OF-SAMPLE
performance -- a higher pass rate on its own is a cost, not a benefit.

    python -u scripts/audit_gate_power.py --n 420 --t 310 --reps 20
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

_ROOT = Path("/home/quant/quant-platform")
if not _ROOT.exists():
    _ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import numpy as np  # noqa: E402

from libs.autodiscovery.models import Family, Hypothesis  # noqa: E402
from libs.autodiscovery.validation import (  # noqa: E402
    CampaignGates,
    campaign_gate_stats,
    validate,
)
from libs.validation.dsr import sharpe_ratio  # noqa: E402
from libs.validation.economic_prior import MechanismType  # noqa: E402
from libs.validation.positive_control import PPY  # noqa: E402
from libs.validation.stepwise import cscv_candidate_pbo, romano_wolf_stepdown  # noqa: E402

_OUT = Path("reports/gate_power_audit.json")
_HYP = Hypothesis(
    family=Family.LIQUIDITY, subtype="audit", symbol="BTCUSDT", params={},
    mechanism=MechanismType.LIQUIDITY, edge_source="simulated",
    failure_modes=["simulated -- never tradeable"],
)
#: Every gate validate() reports, in the order it reports them.
GATES = ("economic_mechanism", "expected_value", "cpcv", "walk_forward", "dsr", "pbo",
         "reality_check", "capacity", "fragility", "beats_baselines")
#: Annualised vol of a simulated candidate. Sets the scale only -- Sharpe is scale-free -- but a
#: realistic figure keeps the capacity gate's dollar arithmetic in a plausible range.
_ANN_VOL = 0.60


def simulate_returns(
    true_ann_sharpe: float,
    n_obs: int,
    rng: np.random.Generator,
    *,
    common: np.ndarray | None = None,
    rho: float = 0.0,
    ar1: float = 0.0,
    df: float | None = None,
    regime: str = "none",
) -> np.ndarray:
    """A candidate's return stream, with the departures from textbook iid-normal that actually
    change a gate's verdict.

    ``rho``    loading on a shared factor -- this is what makes a cohort's effective number of
               independent tests smaller than its candidate count, and multiplicity corrections
               price the RAW count.
    ``ar1``    serial correlation. Inflates a naive Sharpe's precision and is precisely what the
               purge/embargo in CPCV and the stationary-block bootstrap exist to handle, so a gate
               stack must be audited under it rather than only under white noise.
    ``df``     Student-t degrees of freedom for fat tails; None means Gaussian.
    ``regime`` "none", "decay" (edge halves in the second half), "reverse" (edge flips sign), or
               "late" (edge only appears in the final third). A real alpha is not stationary, and
               a gate stack that only admits stationary alphas rejects most true ones.
    """
    sd = _ANN_VOL / np.sqrt(PPY)
    z = rng.standard_normal(n_obs) if df is None else (
        rng.standard_t(df, n_obs) / np.sqrt(df / (df - 2.0)))
    if ar1:
        # AR(1) with unit-variance innovations scaled so the marginal variance stays 1.
        e = z * np.sqrt(1.0 - ar1**2)
        for i in range(1, n_obs):
            e[i] += ar1 * e[i - 1]
        z = e
    if common is not None and rho:
        z = np.sqrt(rho) * common + np.sqrt(max(0.0, 1.0 - rho)) * z
    # per-period Sharpe is mu/sd, so annualised (mu/sd)*sqrt(PPY) == true_ann_sharpe
    mu = true_ann_sharpe * sd / np.sqrt(PPY)
    drift = np.full(n_obs, mu)
    if regime == "decay":
        drift[n_obs // 2:] *= 0.5
    elif regime == "reverse":
        drift[n_obs // 2:] *= -1.0
    elif regime == "late":
        drift[: 2 * n_obs // 3] = 0.0
        drift[2 * n_obs // 3:] *= 3.0        # same total alpha, concentrated late
    return np.asarray(drift + sd * z)


def simulate_cohort(
    n: int, n_obs: int, rng: np.random.Generator, *, n_true: int, true_ann_sharpe: float,
    rho: float = 0.0, ar1: float = 0.0, df: float | None = None, regime: str = "none",
) -> tuple[np.ndarray, np.ndarray]:
    """Returns ``(matrix[T,N], is_true[N])``. The true alphas are placed FIRST but that is
    irrelevant to every gate here -- none of them reads column order."""
    common = rng.standard_normal(n_obs) if rho else None
    cols, flags = [], np.zeros(n, dtype=bool)
    for k in range(n):
        is_true = k < n_true
        flags[k] = is_true
        cols.append(simulate_returns(
            true_ann_sharpe if is_true else 0.0, n_obs, rng,
            common=common, rho=rho, ar1=ar1, df=df, regime=(regime if is_true else "none")))
    return np.column_stack(cols), flags


def effective_n_tests(matrix: np.ndarray) -> dict[str, float]:
    """How many INDEPENDENT tests the cohort really represents.

    Multiplicity corrections deflate by the number of trials, and every one of them here is handed
    the RAW candidate count. When candidates are correlated -- and 420 variants over one universe
    in one era are heavily correlated -- the raw count overstates the true multiplicity, so the
    deflation is too harsh by a factor that nobody has ever measured on this desk.

    Two standard estimators, reported together because they disagree in informative ways:
    ``kaiser`` counts eigenvalues above 1 (components carrying more than one variable's worth of
    variance) and ``participation`` is the participation ratio (sum L)^2 / sum L^2, which is
    smooth and does not depend on a cutoff.
    """
    m = np.asarray(matrix, dtype="float64")
    if m.shape[1] < 2:
        return {"n_raw": float(m.shape[1]), "kaiser": 1.0, "participation": 1.0, "li_ji": 1.0}
    c = np.corrcoef(m, rowvar=False)
    c = np.nan_to_num(c, nan=0.0)
    lam = np.linalg.eigvalsh(c)
    lam = np.clip(lam, 0.0, None)
    n_raw = float(m.shape[1])
    part = float(lam.sum() ** 2 / np.sum(lam**2)) if np.sum(lam**2) > 0 else n_raw
    kaiser = float(np.sum(lam > 1.0))
    # Li & Ji (2005): sum over eigenvalues of [I(L>=1) + (L - floor(L))]
    li_ji = float(np.sum((lam >= 1.0).astype(float) + (lam - np.floor(lam))))
    return {"n_raw": n_raw, "kaiser": kaiser, "participation": part, "li_ji": min(li_ji, n_raw)}


def campaign_stats_fast(matrix: np.ndarray) -> CampaignGates:
    """The per-candidate campaign statistics WITHOUT the legacy campaign constants.

    Pure cost control, and it changes no verdict -- which is asserted, not assumed, by
    ``test_fast_campaign_path_is_verdict_identical``. ``campaign_gate_stats`` also computes
    ``campaign_pbo_rc``, whose classic PBO enumerates C(16,8)=12,870 splits unvectorised and costs
    >100s at N=420 -- roughly 25x everything else in this audit combined. The per-candidate path
    reads ``cscv`` and ``stepdown`` only; ``legacy_pbo``/``legacy_rc`` are consumed exclusively by
    the legacy branch of validate(), which is selected by passing pbo=/rc= instead of campaign=.

    Skipping it turns a ~2-minute replication into a ~5-second one, which is the difference
    between a Monte Carlo with usable confidence intervals and a handful of anecdotes.
    """
    return CampaignGates(cscv=cscv_candidate_pbo(matrix),
                         stepdown=romano_wolf_stepdown(matrix),
                         legacy_pbo=None, legacy_rc=None)


def score_cohort(matrix: np.ndarray, flags: np.ndarray, *, n_trials: int | None = None,
                 per_candidate: bool = True, fast: bool = True) -> list[dict[str, Any]]:
    """Every candidate's per-gate verdict AND continuous statistics, from the REAL validate().

    Campaign statistics are computed once for the whole cohort and shared, which is both what the
    live campaign does and what makes the replication affordable.
    """
    gates = campaign_stats_fast(matrix) if (fast and per_candidate) \
        else campaign_gate_stats(matrix)
    if gates is None:
        raise RuntimeError("campaign_gate_stats returned None")
    sh = np.array([sharpe_ratio(matrix[:, i]) for i in range(matrix.shape[1])])
    n_tr = int(n_trials if n_trials is not None else matrix.shape[1])
    rows: list[dict[str, Any]] = []
    for k in range(matrix.shape[1]):
        kw: dict[str, Any] = {"campaign": gates, "column": k} if per_candidate else {
            "pbo": gates.legacy_pbo, "rc": gates.legacy_rc}
        # PPY (365, D1 crypto) is the clock the cohort was SIMULATED on a few lines up --
        # `mu = true_ann_sharpe * sd / sqrt(PPY)` -- so the verdict must be annualised with it
        # too, or the audit's injected Sharpe and the measured one are on different scales.
        v = validate(matrix[:, k], hypothesis=_HYP, periods_per_year=PPY,
                     n_trials=n_tr, sharpe_estimates=sh,
                     returns_matrix=matrix, **kw)
        rows.append({
            "is_true": bool(flags[k]),
            "survived": bool(v.survived),
            "gates": {g: bool(v.gates.get(g, True)) for g in GATES},
            "dsr": float(v.metrics.dsr),
            "pbo": float(v.metrics.pbo),
            "reality_p": float(v.metrics.reality_p),
            "oos_sharpe": float(v.metrics.oos_sharpe),
            "realised_ann_sharpe": float(sharpe_ratio(matrix[:, k]) * np.sqrt(PPY)),
        })
    return rows


def _wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """Wilson score interval -- correct at the 0 and 1 boundaries, where this audit lives and
    where the normal approximation gives a zero-width interval and a false sense of precision."""
    if n == 0:
        return (0.0, 1.0)
    p = k / n
    d = 1.0 + z**2 / n
    c = (p + z**2 / (2 * n)) / d
    h = z * np.sqrt(max(0.0, p * (1 - p) / n + z**2 / (4 * n**2))) / d
    return (max(0.0, c - h), min(1.0, c + h))


def summarise(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Type I, power, per-gate blocking rates, and the leave-one-out marginals."""
    nulls = [r for r in rows if not r["is_true"]]
    trues = [r for r in rows if r["is_true"]]

    def rate(sub: list[dict[str, Any]], key: str) -> dict[str, Any]:
        k = sum(1 for r in sub if r[key])
        lo, hi = _wilson(k, len(sub))
        return {"k": k, "n": len(sub), "rate": (k / len(sub)) if sub else None,
                "ci95": [lo, hi]}

    per_gate = {}
    for g in GATES:
        # A gate's Type I contribution is how often it PASSES a null (lets noise through); its
        # Type II contribution is how often it BLOCKS a true alpha.
        per_gate[g] = {
            "passes_null": rate([{**r, "_": r["gates"][g]} for r in nulls], "_"),
            "blocks_true": {**rate([{**r, "_": not r["gates"][g]} for r in trues], "_")},
        }

    # LEAVE-ONE-OUT: what the pipeline would do without each gate. This is the marginal
    # contribution question -- a gate that costs power without buying false-positive reduction is
    # pure loss, and only this comparison can show it.
    loo = {}
    for g in GATES:
        others = [x for x in GATES if x != g]
        fp = sum(1 for r in nulls if all(r["gates"][o] for o in others))
        tp = sum(1 for r in trues if all(r["gates"][o] for o in others))
        base_fp = sum(1 for r in nulls if r["survived"])
        base_tp = sum(1 for r in trues if r["survived"])
        loo[g] = {
            "fpr_without": (fp / len(nulls)) if nulls else None,
            "power_without": (tp / len(trues)) if trues else None,
            "delta_fpr": ((fp - base_fp) / len(nulls)) if nulls else None,
            "delta_power": ((tp - base_tp) / len(trues)) if trues else None,
        }

    # SUBSET POWER: leave-one-out cannot see REDUNDANCY. When two gates block the same candidates,
    # removing either alone changes nothing and both look free -- the classic masking result. The
    # only way to price a pair is to remove it as a pair, so the multiplicity corrections (which
    # all deflate for the SAME family of N candidates and are therefore the prime suspects for
    # double-counting) are scored jointly here as well as singly.
    def _subset(keep: tuple[str, ...]) -> dict[str, Any]:
        fp = sum(1 for r in nulls if all(r["gates"][g] for g in keep))
        tp = sum(1 for r in trues if all(r["gates"][g] for g in keep))
        lo_f, hi_f = _wilson(fp, len(nulls))
        lo_t, hi_t = _wilson(tp, len(trues))
        return {"kept": list(keep),
                "fpr": (fp / len(nulls)) if nulls else None, "fpr_ci95": [lo_f, hi_f],
                "power": (tp / len(trues)) if trues else None, "power_ci95": [lo_t, hi_t]}

    _MULT = ("dsr", "reality_check", "pbo")
    _ECON = tuple(g for g in GATES if g not in _MULT)
    subsets = {
        "all_gates": _subset(GATES),
        "without_dsr": _subset(tuple(g for g in GATES if g != "dsr")),
        "without_reality_check": _subset(tuple(g for g in GATES if g != "reality_check")),
        "without_dsr_and_reality_check": _subset(
            tuple(g for g in GATES if g not in ("dsr", "reality_check"))),
        "without_all_three_multiplicity": _subset(_ECON),
        "only_dsr": _subset(("dsr",)),
        "only_reality_check": _subset(("reality_check",)),
        "only_pbo": _subset(("pbo",)),
    }

    # SOLE BLOCKER: among true alphas the pipeline killed, which single gate did it alone? A gate
    # that is never the sole blocker is redundant; one that usually is, is the binding constraint.
    sole: dict[str, int] = {}
    for r in trues:
        failed = [g for g in GATES if not r["gates"][g]]
        if len(failed) == 1:
            sole[failed[0]] = sole.get(failed[0], 0) + 1
    return {
        "n_null": len(nulls), "n_true": len(trues),
        "type_i_joint": rate(nulls, "survived"),
        "power_joint": rate(trues, "survived"),
        "per_gate": per_gate,
        "leave_one_out": loo,
        "gate_subsets": subsets,
        "sole_blocker_of_true_alpha": dict(sorted(sole.items(), key=lambda x: -x[1])),
    }


def calibration(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Are the corrections SIZED correctly? Under the null a p-value must be ~uniform and a
    posterior-style score like DSR must exceed 0.95 about 5% of the time. A correction that is
    far tighter than its nominal level is over-conservative BY CONSTRUCTION rather than by
    configuration, and no threshold change fixes that -- it is the wrong instrument."""
    nulls = [r for r in rows if not r["is_true"]]
    if not nulls:
        return {}
    dsr = np.array([r["dsr"] for r in nulls])
    rcp = np.array([r["reality_p"] for r in nulls])
    pbo = np.array([r["pbo"] for r in nulls])
    return {
        "dsr_nominal_fpr": 0.05,
        "dsr_realised_fpr": float(np.mean(dsr >= 0.95)),
        "dsr_quantiles": {q: float(np.quantile(dsr, q)) for q in (0.5, 0.9, 0.95, 0.99)},
        "reality_p_nominal_fpr": 0.05,
        "reality_p_realised_fpr": float(np.mean(rcp <= 0.05)),
        "reality_p_mean_should_be_0.5_if_uniform": float(np.mean(rcp)),
        "reality_p_quantiles": {q: float(np.quantile(rcp, q)) for q in (0.05, 0.1, 0.5, 0.9)},
        "pbo_realised_fpr_at_0.5": float(np.mean(pbo <= 0.5)),
        "pbo_mean": float(np.mean(pbo)),
    }


def roc(rows: list[dict[str, Any]], key: str, *, higher_is_better: bool) -> list[dict[str, float]]:
    """ROC for one continuous statistic, so a gate's DISCRIMINATION is separated from its
    THRESHOLD. A statistic with good AUC and a badly-placed threshold is a configuration problem;
    one with AUC ~0.5 is uninformative at every threshold and no re-tuning will save it."""
    nulls = np.array([r[key] for r in rows if not r["is_true"]])
    trues = np.array([r[key] for r in rows if r["is_true"]])
    if not len(nulls) or not len(trues):
        return []
    cuts = np.unique(np.concatenate([nulls, trues]))
    out = []
    for c in cuts:
        tpr = float(np.mean(trues >= c) if higher_is_better else np.mean(trues <= c))
        fpr = float(np.mean(nulls >= c) if higher_is_better else np.mean(nulls <= c))
        out.append({"cut": float(c), "tpr": tpr, "fpr": fpr})
    return out


def auc(rows: list[dict[str, Any]], key: str, *, higher_is_better: bool) -> float | None:
    """Mann-Whitney AUC: P(a true alpha scores better than a null one)."""
    nulls = np.array([r[key] for r in rows if not r["is_true"]])
    trues = np.array([r[key] for r in rows if r["is_true"]])
    if not len(nulls) or not len(trues):
        return None
    gt = float(np.mean(trues[:, None] > nulls[None, :]))
    eq = float(np.mean(trues[:, None] == nulls[None, :]))
    a = gt + 0.5 * eq
    return a if higher_is_better else 1.0 - a


def _merge(all_rows: list[list[dict[str, Any]]]) -> list[dict[str, Any]]:
    return [r for rep in all_rows for r in rep]


def run_condition(*, n: int, n_obs: int, true_sr: float, n_true: int, reps: int, seed0: int,
                  rho: float = 0.0, ar1: float = 0.0, df: float | None = None,
                  regime: str = "none", n_trials: int | None = None,
                  per_candidate: bool = True, verbose: bool = True) -> dict[str, Any]:
    reps_rows, neff = [], []
    for i in range(reps):
        rng = np.random.default_rng(seed0 + 7919 * i)
        m, flags = simulate_cohort(n, n_obs, rng, n_true=n_true, true_ann_sharpe=true_sr,
                                   rho=rho, ar1=ar1, df=df, regime=regime)
        t0 = time.time()
        reps_rows.append(score_cohort(m, flags, n_trials=n_trials, per_candidate=per_candidate))
        neff.append(effective_n_tests(m))
        if verbose:
            print(f"    rep {i + 1}/{reps} [{time.time() - t0:5.1f}s]", flush=True)
    rows = _merge(reps_rows)
    s = summarise(rows)
    s["condition"] = {"n": n, "t": n_obs, "true_sr": true_sr, "n_true": n_true, "reps": reps,
                      "rho": rho, "ar1": ar1, "df": df, "regime": regime,
                      "n_trials": n_trials or n, "path": "per_candidate" if per_candidate
                      else "legacy"}
    s["effective_n_tests"] = {k: float(np.mean([d[k] for d in neff])) for k in neff[0]}
    # THE ESTIMATOR'S OWN FLOOR, measured on an INDEPENDENT cohort of the same shape. When T < N
    # the sample correlation matrix has rank <= T, so every eigenvalue-based N_eff is biased below
    # N even with zero true dependence: at N=420, T=310 the participation ratio reads ~179 on
    # perfectly independent columns. Reporting the raw figure alone would manufacture a finding
    # ("only 179 independent tests!") out of an estimation artifact. The interpretable quantity is
    # the RATIO of the measured value to this baseline.
    rng_b = np.random.default_rng(seed0 + 104729)
    base_m, _ = simulate_cohort(n, n_obs, rng_b, n_true=0, true_ann_sharpe=0.0, rho=0.0)
    s["effective_n_tests_independent_baseline"] = effective_n_tests(base_m)
    s["effective_n_tests_ratio_vs_baseline"] = {
        k: (s["effective_n_tests"][k] / v if v else None)
        for k, v in s["effective_n_tests_independent_baseline"].items()}
    s["calibration"] = calibration(rows)
    s["auc"] = {"dsr": auc(rows, "dsr", higher_is_better=True),
                "reality_p": auc(rows, "reality_p", higher_is_better=False),
                "pbo": auc(rows, "pbo", higher_is_better=False),
                "oos_sharpe": auc(rows, "oos_sharpe", higher_is_better=True)}
    return s


#: The campaign the desk's 0-of-420 record was measured on -- every study is anchored to it.
_BASE_N, _BASE_T = 420, 310
_N_TRUE = 20                        # ~5% of the cohort genuinely has an edge; a realistic prior


def _studies(reps: int, n_true: int) -> dict[str, list[dict[str, Any]]]:
    """Every condition this audit runs, as data.

    Each study isolates ONE candidate explanation for the desk's 0-survivor record, so the
    bottleneck question is answered by comparison rather than by argument: if lengthening the
    sample moves power and widening the cohort does not, the bottleneck is history, not campaign
    size -- and the reverse is equally decidable.
    """
    base = {"reps": reps, "n_true": n_true}
    return {
        # A. the power curve at the campaign's OWN shape -- the headline number
        "power_curve": [{**base, "n": _BASE_N, "n_obs": _BASE_T, "true_sr": sr}
                        for sr in (0.0, 1.0, 2.0, 3.0, 4.0, 5.0, 7.0, 10.0)],
        # B. sample length, holding cohort size fixed
        "history_length": [{**base, "n": _BASE_N, "n_obs": t, "true_sr": 2.0}
                           for t in (310, 620, 1250, 2500)],
        # C. campaign size, holding history fixed
        "campaign_size": [{**base, "n": n, "n_obs": _BASE_T, "true_sr": 2.0,
                           "n_true": max(2, int(n * n_true / _BASE_N))}
                          for n in (30, 100, 420)],
        # D. correlation -- the effective-multiplicity question
        "correlation": [{**base, "n": _BASE_N, "n_obs": _BASE_T, "true_sr": 3.0, "rho": r}
                        for r in (0.0, 0.3, 0.6, 0.9)],
        # E. departures from iid-normal that a real alpha actually exhibits
        "realism": [
            {**base, "n": _BASE_N, "n_obs": _BASE_T, "true_sr": 3.0, "ar1": 0.2},
            {**base, "n": _BASE_N, "n_obs": _BASE_T, "true_sr": 3.0, "df": 4.0},
            {**base, "n": _BASE_N, "n_obs": _BASE_T, "true_sr": 3.0, "regime": "decay"},
            {**base, "n": _BASE_N, "n_obs": _BASE_T, "true_sr": 3.0, "regime": "reverse"},
            {**base, "n": _BASE_N, "n_obs": _BASE_T, "true_sr": 3.0, "regime": "late"},
        ],
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--study", default="power_curve",
                    help="power_curve|history_length|campaign_size|correlation|realism|all")
    ap.add_argument("--reps", type=int, default=12)
    ap.add_argument("--n-true", type=int, default=_N_TRUE)
    ap.add_argument("--seed0", type=int, default=90210)
    ap.add_argument("--out", default=str(_OUT))
    args = ap.parse_args()

    studies = _studies(args.reps, args.n_true)
    names = list(studies) if args.study == "all" else [args.study]
    out: dict[str, Any] = {"generated": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                           "base_shape": {"n": _BASE_N, "t": _BASE_T}, "studies": {}}
    p = Path(args.out)
    p.parent.mkdir(parents=True, exist_ok=True)
    for name in names:
        out["studies"][name] = []
        for spec in studies[name]:
            s = dict(spec)
            if s["true_sr"] <= 0:
                s["n_true"] = 0
            print(f"== {name}: {s} ==", flush=True)
            out["studies"][name].append(run_condition(seed0=args.seed0, **s))
            # CHECKPOINT per condition: a long sweep that dies at 90% must not discard the 90%.
            p.write_text(json.dumps(out, indent=2), "utf-8")
    print(f"wrote {p}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

```

### scripts\certify_gauntlet.py
```python
"""Certify the real gauntlet with known-GOOD / known-NULL controls (R0017).

Answers the question 434-tested/0-promoted cannot answer on its own: **can this funnel admit a
genuinely good candidate at all, and does it still reject noise?** Until that is answered, "0
survivors" is uninterpretable -- it is equally consistent with picked-clean price space and with a
gate welded shut, and the desk has been reasoning from the first reading without evidence for it.

Controls come from ``libs.validation.positive_control``, which pins a control's SAMPLE Sharpe by
construction. That matters more than it sounds: at T=310 the standard error of an annualised Sharpe
is 1.085, so the previous probe's fixed-seed "true SR +0.5" candidate actually realised -2.32 and
every gate rejected it correctly. See that module's docstring.

CONTROLLED A/B, and it is controlled on purpose. ``campaign_gate_stats`` returns the legacy campaign
constants (``legacy_pbo``/``legacy_rc``) alongside the per-candidate statistics, so ONE pass over the
injected matrix scores both the welded path and the per-candidate path for the SAME candidate on the
SAME window. The 2026-07-30 migration attempt was reverted partly because its before/after windows
differed and the deltas could not be attributed; this design removes that objection.

Writes reports/gauntlet_certification.json. Read-only with respect to every DB, ledger, and gate:
this script measures, it never promotes.

    .venv/bin/python scripts/certify_gauntlet.py [--seeds 3] [--targets 2,3,5,7,10,15]
"""

from __future__ import annotations

import argparse
import json
import pickle
import sys
import time
from pathlib import Path
from typing import Any

_ROOT = Path("/home/quant/quant-platform")
if not _ROOT.exists():
    _ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    # WITHOUT THIS the script dies on `ModuleNotFoundError: No module named 'libs'` when invoked
    # as `python scripts/certify_gauntlet.py` -- which is exactly how its manifest line calls it.
    # It only ever ran under `python -m`, so the daily organ produced a bare traceback and the
    # BLOCKED artifact it was carefully written to emit never got written either. Every other
    # organ on the desk carries this preamble; this one was missing it.
    sys.path.insert(0, str(_ROOT))

import numpy as np  # noqa: E402
from scipy.stats import norm as _norm  # noqa: E402

from libs.autodiscovery.models import Family, Hypothesis  # noqa: E402
from libs.autodiscovery.validation import (  # noqa: E402
    _DSR_THRESHOLD,
    campaign_gate_stats,
    validate,
)
from libs.validation.dsr import expected_max_sharpe, sharpe_ratio  # noqa: E402
from libs.validation.economic_prior import MechanismType  # noqa: E402
from libs.validation.positive_control import PPY, exact_sharpe_series, null_cohort  # noqa: E402

_PREPARED = Path("_audit_prepared.pkl")
#: The campaign SHAPE, committed, so a synthetic cohort can stand in at the right dimensions.
_HIST = Path("reports/gate_histogram.json")
#: Fixed seed for the SYNTHETIC peer cohort -- the peers must be identical across runs or the
#: certification moves for reasons that have nothing to do with the gate. The INJECTED controls
#: still vary their seed per row (--seeds/--seed0): R0017 closed on exactly that defect, a
#: reused seed=7 across all 13 sweep rows reading as signal when it was one draw repeated.
_SYNTH_SEED = 20260731
_OUT = Path("reports/gauntlet_certification.json")
_FAMILY_TRIAL_BUDGET = 120
_HYP = Hypothesis(
    family=Family.LIQUIDITY, subtype="control", symbol="BTCUSDT", params={},
    mechanism=MechanismType.LIQUIDITY, edge_source="synthetic control",
    failure_modes=["synthetic control -- never tradeable"],
)


class CampaignUnavailable(RuntimeError):
    """The campaign pickle is absent. Raised so the caller can record a BLOCKER, not a traceback."""


def _load_campaign() -> tuple[np.ndarray, np.ndarray, int, str]:
    """The reconstructed 420-candidate campaign the 0-survivor result was measured on.

    `_audit_prepared.pkl` is a gitignored 6MB scratch artifact with THREE READERS (this script,
    measure_gate_histogram.py, measure_matrix_window.py) and NO WRITER anywhere in the repo -- it
    was produced once by hand during the 2026-07-29 audit and never committed or regenerated.

    So this script, scheduled daily, has been dying on a bare FileNotFoundError every run, and
    reports/gauntlet_certification.json has never existed. The consequence is not cosmetic:
    libs/validation/positive_control.py is the instrument that distinguishes "price space is
    genuinely picked clean" from "the gate is welded shut", and until it produces an artifact the
    desk cannot tell those apart -- which is the single question the 420-tested/0-survivors record
    turns on. It is also why GAP_REGISTER R0040 and R0041 are both still gated.

    Raising a NAMED exception rather than crashing means the daily run leaves EVIDENCE of why it
    could not certify, in the artifact the max-push queue reads, instead of a stack trace at the
    bottom of a log nobody opens.
    """
    if _PREPARED.exists():
        prepared = pickle.loads(_PREPARED.read_bytes())  # noqa: S301 -- pickle of a corpus this desk wrote itself; never an untrusted input
        min_len = min(len(r) for *_x, r in prepared)
        matrix = np.column_stack([r[-min_len:] for *_x, r in prepared])
        sharpes = np.array([sharpe_ratio(r) for *_x, r in prepared])
        return matrix, sharpes, min_len, "CAMPAIGN"

    # FALLBACK: a SYNTHETIC null cohort at the campaign's RECORDED shape -- the resolution this
    # script named for itself, now taken. It splits the question the certifier was asked into the
    # half that is answerable without the pickle and the half that is not, and the split is the
    # whole point of doing it this way rather than waiting:
    #
    #   ANSWERABLE ON SYNTHETIC PEERS -- "can this gate stack EVER pass a genuinely good
    #   candidate?" That is a property of the GATE MACHINERY, not of the desk's price space. If
    #   an injected true Sharpe of 10 cannot survive against 420 zero-edge peers, the gate is
    #   welded shut and no amount of real data would have shown it more clearly.
    #
    #   NOT ANSWERABLE -- "is the desk's real 420-candidate campaign's 0-survivor result
    #   informative, or an artifact of its peers?" That needs the REAL peers, because PBO and the
    #   reality check are both computed AGAINST the cohort. A synthetic cohort answers a
    #   different question and must never be reported as if it answered this one.
    #
    # So the run is labelled SYNTHETIC end to end and the artifact says which question it settled.
    shape = json.loads(_HIST.read_text("utf-8"))["matrix_shape"] if _HIST.exists() else None
    if not shape:
        raise CampaignUnavailable(
            f"{_PREPARED} is absent (3 readers, 0 writers) AND {_HIST} carries no matrix_shape, "
            "so not even a synthetic cohort can be built at the campaign's dimensions. Commit a "
            "builder for the pickle, or restore the histogram.")
    n_obs, n_cand = int(shape[0]), int(shape[1])
    rng = np.random.default_rng(_SYNTH_SEED)
    matrix = null_cohort(n_cand, n_obs, rng=rng)
    sharpes = np.array([sharpe_ratio(matrix[:, i]) for i in range(n_cand)])
    return matrix, sharpes, n_obs, "SYNTHETIC"


def _score(rets: np.ndarray, matrix: np.ndarray,
           peer_sharpes: np.ndarray) -> dict[str, Any]:
    """Inject ``rets`` as a new campaign column and score it on BOTH gate paths."""
    m = np.column_stack([matrix, rets])
    gates = campaign_gate_stats(m)
    if gates is None:
        raise RuntimeError("campaign_gate_stats returned None on a >=2-column matrix")
    col = m.shape[1] - 1
    sh = np.append(peer_sharpes, sharpe_ratio(rets))
    n_trials = max(_FAMILY_TRIAL_BUDGET, m.shape[1])

    # PPY is libs.validation.positive_control's D1-crypto clock (365) -- the SAME number this
    # script already uses for its hurdle/SE tables. Passing it into validate() is what makes the
    # certification's hurdle and the verdict it certifies share one annualiser (R0086).
    common = {
        "hypothesis": _HYP, "periods_per_year": PPY, "n_trials": n_trials,
        "sharpe_estimates": sh, "returns_matrix": m,
    }
    legacy = validate(rets, pbo=gates.legacy_pbo, rc=gates.legacy_rc, **common)
    percand = validate(rets, campaign=gates, column=col, **common)

    def _v(res: Any) -> dict[str, Any]:
        return {
            "survived": bool(res.survived),
            "failed": [g for g, ok in res.gates.items() if not ok],
            "dsr": float(res.metrics.dsr), "pbo": float(res.metrics.pbo),
            "reality_p": float(res.metrics.reality_p),
            "oos_sharpe": float(res.metrics.oos_sharpe),
        }

    return {"legacy": _v(legacy), "per_candidate": _v(percand)}


#: Campaign shapes to price. Rows are observation counts, columns candidate counts -- the two
#: knobs the desk actually controls when it designs a sweep.
_DESIGN_T = (310, 620, 1250, 2500)
_DESIGN_N = (420, 100, 30, 10, 5)
#: True annualised Sharpes worth asking about. A world-class systematic book runs 2-3; anything
#: at 5+ is a once-a-decade find, so a gate that only resolves above 5 resolves nothing real.
_TRUE_SR_GRID = (1.0, 1.5, 2.0, 2.5, 3.0, 4.0, 5.0, 6.0)


def dsr_hurdle_annual(n_trials: int, n_obs: int, *, var_sharpes: float | None = None) -> float:
    """The observed ANNUALISED Sharpe a candidate must post to clear the DSR gate.

    Derived from the desk's OWN primitives rather than restated, so the number moves if the gate
    moves: ``expected_max_sharpe`` supplies the multiplicity deflator and ``_DSR_THRESHOLD`` the
    tolerance. Inlining either as a literal would let the table drift silently away from the gate
    it claims to describe, which is the whole failure mode this script exists to catch.

    ``var_sharpes`` defaults to the NULL dispersion 1/T -- the variance of sample Sharpes across
    zero-edge candidates. That makes the result a FLOOR: a real cohort disperses more than noise,
    ``expected_max_sharpe`` scales linearly in that dispersion, so the live hurdle is higher than
    this, never lower. Reporting the floor keeps the verdict conservative in the safe direction.
    """
    sr0 = expected_max_sharpe(n_trials, (1.0 / n_obs) if var_sharpes is None else var_sharpes)
    # dsr >= threshold  <=>  z >= Phi^-1(threshold), and z = (sr - sr0)*sqrt(T-1)/sqrt(denom)
    # with denom -> 1 for near-normal returns. Solve for sr, then annualise.
    z = float(_norm.ppf(_DSR_THRESHOLD))
    return float((sr0 + z / np.sqrt(max(1, n_obs - 1))) * np.sqrt(PPY))


def design_power(n_trials: int, n_obs: int) -> dict[str, Any]:
    """Why 0-of-420 is uninformative, priced instead of argued.

    The certification above answers "can a true edge pass"; the honest follow-up is "how big must
    it be", and that is arithmetic on the campaign's SHAPE, not on its thresholds. Two knobs set
    it: N widens the multiplicity deflator (E[max of N nulls]) and T shrinks the standard error
    (SE = sqrt(PPY/T)). Their product IS the hurdle.

    This matters because the two available responses to "nothing survived" are not equally
    legitimate. Lowering a threshold manufactures survivors and is forbidden. Re-shaping the
    experiment -- fewer, mechanism-motivated candidates over longer history -- buys the same
    resolution while every threshold stays exactly where it is. The table prices that trade so
    the choice is made on numbers.
    """
    se = float(np.sqrt(PPY / n_obs))
    hurdle = dsr_hurdle_annual(n_trials, n_obs)
    power = {f"{s:g}": float(1.0 - _norm.cdf((hurdle - s) / se)) for s in _TRUE_SR_GRID}
    # The largest true Sharpe the campaign still cannot find half the time. If this sits above
    # what real strategies achieve, a null result carries no information about the price space.
    blind_to = [s for s in _TRUE_SR_GRID if power[f"{s:g}"] < 0.5]
    return {
        "dsr_threshold": _DSR_THRESHOLD,
        "n_trials": n_trials,
        "n_obs": n_obs,
        "se_annual_sharpe": se,
        "hurdle_annual_sharpe": hurdle,
        "hurdle_is_a_floor": "null dispersion assumed; a real cohort disperses more, so the live "
                             "hurdle is >= this, never below it",
        "power_by_true_annual_sharpe": power,
        "underpowered_below_annual_sharpe": (max(blind_to) if blind_to else None),
        # N enters DIRECTLY here, with no floor, because that is what a redesigned campaign would
        # actually face: production callers pass the real candidate count (run_discovery
        # n_trials=len(lib), run_crypto_portfolio matrix.shape[1], orchestrator per-family counts).
        # The first draft of this table applied THIS SCRIPT's _FAMILY_TRIAL_BUDGET floor of 120 to
        # every cell, which collapsed N=100/30/10/5 to one number and said -- falsely -- that
        # narrowing a campaign below 120 buys nothing. The floor is the certifier's scoring
        # assumption, not the gate's; conflating the two would have argued the desk out of the one
        # lever that works.
        "alternative_shapes": {
            f"T={t}": {f"N={n}": dsr_hurdle_annual(n, t) for n in _DESIGN_N} for t in _DESIGN_T
        },
        "certifier_trial_floor": _FAMILY_TRIAL_BUDGET,
        "reading": ("Hurdle is set by campaign SHAPE, not by the 0.95 tolerance. Cutting N and "
                    "raising T lowers it without relaxing a single gate; lowering the tolerance "
                    "would manufacture survivors and is not on the table."),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", type=int, default=3)
    ap.add_argument("--targets", default="2,3,5,7,10,15")
    ap.add_argument("--seed0", type=int, default=1000)
    args = ap.parse_args()
    targets = [float(t) for t in args.targets.split(",")]

    try:
        matrix, peer_sharpes, n_obs, provenance = _load_campaign()
    except CampaignUnavailable as exc:
        # RECORD THE BLOCKER, do not crash. A daily organ that dies on a traceback produces
        # nothing an audit can read, so the gap stays invisible for as long as nobody opens the
        # log -- which for this script was every day since it was scheduled. Writing the artifact
        # with status BLOCKED means check_organs sees a fresh file, run_max_push sees a named
        # blocker, and the reason is one grep away instead of one archaeology session away.
        _OUT.parent.mkdir(parents=True, exist_ok=True)
        _OUT.write_text(json.dumps({
            "generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "status": "BLOCKED",
            "blocker": str(exc),
            "consequence": "The positive control has never run, so the desk cannot distinguish a "
                           "genuinely picked-clean price space from a welded-shut gate. "
                           "GAP_REGISTER R0040 and R0041 both depend on this answer.",
            "resolution": "Commit a builder for _audit_prepared.pkl, or give _load_campaign() a "
                          "fallback to positive_control.null_cohort at the shape recorded in "
                          "reports/gate_histogram.json.",
            "rows": [],
        }, indent=2), "utf-8")
        print(f"BLOCKED: {exc}")
        print(f"-> {_OUT} (status BLOCKED -- the blocker is now an artifact, not a traceback)")
        return 1
    se = float(np.sqrt(PPY / n_obs))
    print(f"campaign: T={n_obs} N={matrix.shape[1]}  SE(annual Sharpe)={se:.3f}  "
          f"peers={provenance}")
    if provenance == "SYNTHETIC":
        print("PEERS ARE SYNTHETIC -- this run certifies the GATE MACHINERY (can a true edge "
              "pass?), NOT whether the desk's real 0/420 result is informative. Different "
              "questions; only the first is answerable without _audit_prepared.pkl.")
    print("controls have their target SAMPLE Sharpe by construction (sampling error removed)\n")

    rows: list[dict[str, Any]] = []
    # target 0.0 is the NULL control -- the other half of certification.
    for target in [*targets, 0.0]:
        for k in range(args.seeds):
            rng = np.random.default_rng(args.seed0 + (500_000 if target == 0.0 else 0) + k)
            rets = exact_sharpe_series(target, n_obs, rng=rng)
            realised = float(sharpe_ratio(rets) * np.sqrt(PPY))
            t0 = time.time()
            scored = _score(rets, matrix, peer_sharpes)
            rows.append({"target": target, "seed": k, "realised_ann_sharpe": realised, **scored})
            # CHECKPOINT EVERY ROW (R0052): each row is ~50s of Romano-Wolf bootstrap on a
            # 2-core box, and the full run does not comfortably fit one wall-clock window --
            # a timeout or kill used to discard the WHOLE run (R0017 was disposed
            # 'implemented' against an artifact of 0 bytes). Every row is independently
            # meaningful, so a partial file with status RUNNING beats a perfect file that
            # never exists.
            _OUT.parent.mkdir(parents=True, exist_ok=True)
            _OUT.write_text(json.dumps({
                "generated": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "status": "RUNNING",
                "rows_done": len(rows),
                "rows_planned": (len(targets) + 1) * args.seeds,
                "campaign": {"T": n_obs, "N": matrix.shape[1], "se_annual_sharpe": se,
                             "peers": provenance},
                "rows": rows,
            }, indent=2), "utf-8")
            lg, pc = scored["legacy"], scored["per_candidate"]
            print(
                f"SR_true={target:5.1f} seed={k} realised={realised:6.2f} "
                f"[{time.time() - t0:5.1f}s]  "
                f"legacy={'PASS' if lg['survived'] else 'FAIL:' + ','.join(lg['failed'])}  "
                f"percand={'PASS' if pc['survived'] else 'FAIL:' + ','.join(pc['failed'])}"
            )

    def _summary(path: str) -> dict[str, Any]:
        good = [r for r in rows if r["target"] > 0.0]
        nulls = [r for r in rows if r["target"] == 0.0]
        by_t = {
            f"{t:g}": float(np.mean([r[path]["survived"] for r in good if r["target"] == t]))
            for t in targets
        }
        passing = [t for t in targets if by_t[f"{t:g}"] > 0.0]
        sole: dict[str, int] = {}
        for r in good:
            failed = r[path]["failed"]
            if not r[path]["survived"] and len(failed) == 1:
                sole[failed[0]] = sole.get(failed[0], 0) + 1
        blocked_all: dict[str, int] = {}
        for r in good:
            for g in r[path]["failed"]:
                blocked_all[g] = blocked_all.get(g, 0) + 1
        return {
            "pass_rate_by_true_sharpe": by_t,
            "min_passing_true_sharpe": (min(passing) if passing else None),
            "null_false_pass_rate": (
                float(np.mean([r[path]["survived"] for r in nulls])) if nulls else 0.0
            ),
            "sole_blocking_gate_counts": sole,
            "all_blocking_gate_counts": blocked_all,
            "certified_admits_good": bool(passing),
        }

    out: dict[str, Any] = {
        "generated": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        # COMPLETE-SYNTHETIC is deliberately a DIFFERENT status, not a footnote on COMPLETE. A
        # reader scanning for "COMPLETE" must not pick up a run whose peers were manufactured and
        # conclude the desk's real 0/420 campaign has been vindicated -- it answers the gate
        # question, not the price-space question, and the two get confused precisely because the
        # numbers look identical.
        "status": "COMPLETE" if provenance == "CAMPAIGN" else "COMPLETE-SYNTHETIC",
        "peers": provenance,
        "answers": ("both: can the gate pass a true edge, AND is the real 0/420 informative"
                    if provenance == "CAMPAIGN" else
                    "ONLY: can the gate stack pass a genuinely good candidate at all. The peers "
                    "here are manufactured zero-edge draws at the campaign's recorded shape, so "
                    "PBO and the reality check -- both computed AGAINST the cohort -- say nothing "
                    "about whether the desk's real price space is picked clean. That half stays "
                    "blocked on a builder for _audit_prepared.pkl (3 readers, 0 writers)."),
        "campaign": {"T": n_obs, "N": matrix.shape[1], "se_annual_sharpe": se,
                     "peers": provenance},
        "controls": {"targets": targets, "seeds": args.seeds,
                     "construction": "exact sample Sharpe (libs.validation.positive_control)"},
        # The other half of "can a true edge pass": HOW BIG must it be. Purely analytic, so it is
        # correct even on the rows this run did not sweep -- and it is what turns "0 of 420" from
        # a claim about the price space into a claim about the campaign's resolution.
        "design": design_power(max(_FAMILY_TRIAL_BUDGET, matrix.shape[1] + 1), n_obs),
        "legacy_welded_path": _summary("legacy"),
        "per_candidate_path": _summary("per_candidate"),
        "rows": rows,
    }
    _OUT.parent.mkdir(parents=True, exist_ok=True)
    _OUT.write_text(json.dumps(out, indent=2))

    print("\n" + "=" * 78)
    for name in ("legacy_welded_path", "per_candidate_path"):
        s = out[name]
        print(f"{name}: min passing true SR = {s['min_passing_true_sharpe']}  "
              f"null FPR = {s['null_false_pass_rate']:.0%}  "
              f"sole blockers = {s['sole_blocking_gate_counts']}")
    print(f"wrote {_OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

```

### scripts\check_absolute_ceiling.py
```python
#!/usr/bin/env python3
"""THE COMPLETION AUDITOR -- every capability the principal's ceiling mandate specifies, and the
stage each one has actually reached, COMPUTED from this tree rather than claimed by anybody.

    "Do not rely on humans remembering this mandate."   -- the ceiling mandate, 2026-09-05

WHY THIS FILE IS THE FIRST THING BUILT FROM AN 84-PHASE MANDATE, and not the last. A mandate that
long cannot be held in a head, a commit message or a session. Without a registry, "is the desk
finished?" is answered by whoever is asked, from memory, and the answer drifts optimistic --
because every phase has a module that could plausibly be its owner, and a module existing is the
single most common false positive on this desk. The auditor turns the mandate from prose somebody
remembers into a number CI can fail on.

STAGES ARE DERIVED, NEVER DECLARED. A capability may not tell this file what stage it is at. Each
rung is a separate question asked of the repository:

    MISSING             no owner module on disk
    CODED               the module exists                     <- where most things stop, silently
    WIRED               something other than its own tests imports it
    SCHEDULED           a scheduler surface names it
    RUNNING             its artifact exists on this host
    DECISION_AFFECTING  the capability graph routes it into a decision
    MEASURED            MODULE_RENT carries a verdict for it
    PROVEN              forward/live evidence, not backtest, has priced its rent

The ladder is strict and monotone: a capability cannot be SCHEDULED without being WIRED, because a
cron line pointing at a module nobody imports runs code that changes nothing.

WHAT `MEASURING` MEANS, AND WHY IT IS NOT A FAILURE. Some capabilities are correct, running and
deciding, and simply have not yet accumulated the forward observations that would let their rent be
priced. That is reality being slow, not the desk being incomplete, and the mandate says so
explicitly. They read MEASURING with the missing evidence NAMED. What is forbidden is the other
thing: reporting such a capability as complete, or as zero.

THIS HOST SEES NO LIVE ARTIFACTS. The lake and the reports live on the VPS and the box. Run here,
every RUNNING/PROVEN test that depends on an artifact answers honestly in the negative, and the
report says so rather than pretending. The registry, the wiring and the schedule are all readable
from the tree and are graded fully wherever this runs.

    python scripts/check_absolute_ceiling.py [--json] [--gaps] [--phase P17]
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

REPORT = ROOT / "desks" / "mt5" / "reports" / "ABSOLUTE_CEILING_STATUS.json"

STAGES = ("MISSING", "CODED", "WIRED", "SCHEDULED", "RUNNING", "DECISION_AFFECTING",
          "MEASURED", "PROVEN")

#: Every place on this tree that can make code run on a clock. Same list as
#: `scripts/check_producer_schedules.py` -- deliberately duplicated rather than imported, because
#: that fence grades the capability GRAPH and this one grades the MANDATE, and coupling them means
#: a change made for one silently re-grades the other.
SCHEDULER_SURFACES = (
    "ops/crontab.manifest",
    "desks/mt5/ops/box_tasks.manifest",
    "desks/mt5/research/research_supervisor.py",
    "desks/mt5/research/hourly_cycle.py",
    "desks/mt5/research/daily_cycle.py",
)


@dataclass(frozen=True)
class Capability:
    """One requirement from the mandate, and where its answer would have to live.

    `owner` EMPTY IS A LEGITIMATE AND IMPORTANT STATE. It means the mandate asks for something this
    desk has not built, and writing a speculative path here to make the row look populated would be
    the exact failure the mandate names: claiming a capability because a filename exists.
    """
    id: str
    requirement: str
    owner: str = ""
    artifact: str = ""
    rent_metric: str = ""
    depends_on: tuple[str, ...] = ()
    #: Set when a capability legitimately cannot reach PROVEN yet, naming what reality still owes.
    awaiting: str = ""
    tags: tuple[str, ...] = field(default_factory=tuple)


# ---------------------------------------------------------------- the registry
#
# ORDERED BY THE MANDATE'S OWN PHASE NUMBERS so a reader can hold the two side by side. The owner
# column is the desk's REAL module where one exists and empty where it does not; nothing here is
# aspirational, because an aspirational owner turns MISSING into CODED and hides the work.

REGISTRY: tuple[Capability, ...] = (
    # ---- Phase 0: one source of truth
    # OWNER IS THE MODULE, NOT THE ARTIFACT. This row named the .json as its own producer -- the
    # only capability of the 94 to do so -- and every downstream question about it was asked of a
    # data file. `scheduler_for` searches the schedulers for the OWNER's stem, so it looked for a
    # cron line running `release_identity.json`, found none, and returned an empty surface list
    # that read as "nothing schedules this" when the truth was "nothing was ever asked the right
    # question". Measured 2026-09-06: the artifact was 21h old with ok=false and 1,074 paths of
    # drift against the sealed release, and it was in fact unscheduled -- but the report could
    # not distinguish that from a lookup failure, so it proved nothing either way.
    Capability("P0.1", "release identity matches across research, validation, forward, allocator, "
                       "gateway and live; no match = no new capital authority",
               "desks/mt5/mt5desk/release_identity.py", "desks/mt5/data/release_identity.json",
               "capital authority is refused under ambiguous lineage", tags=("P0", "identity")),
    Capability("P0.2", "20% nominal heat floor, flat -- no readiness/evidence mechanism may "
                       "reduce it; above it stays evidence-determined through 45%",
               "desks/mt5/research/heat_policy.py", "desks/mt5/reports/HEAT_POLICY.json",
               "floor_binding + missed-growth attribution when unsatisfiable",
               tags=("P0", "policy", "FIXED")),
    Capability("P0.3", "capability status regenerated from the current SHA over the full ladder",
               "libs/ops/capability_graph.py", "desks/mt5/reports/CAPABILITY_STATUS.json",
               "unbillable count", tags=("P0",)),

    # ---- Phase 1-3: close the loops
    Capability("P1", "every organ proves producer -> artifact -> consumer -> decision -> "
                     "telemetry -> counterfactual -> rent",
               "libs/ops/module_rent.py", "desks/mt5/data/module_rent.jsonl",
               "EARNS/COSTS/NOT_BINDING per module", tags=("P1",)),
    Capability("P2", "macro event -> structured information -> forecast -> portfolio delta -> "
                     "dE[logW] -> interrupt -> rebalance, closed",
               "desks/mt5/research/macro_desk.py", "desks/mt5/reports/MACRO_DESK.json",
               "measured portfolio gain attributable to the interrupt", tags=("P2", "macro")),
    Capability("P3", "one-minute heartbeat and event triggers re-evaluate Elog optimality; "
                     "rebalance only when dElog > execution cost + uncertainty", "desks/mt5/research/rebalance_trigger.py",
               "desks/mt5/reports/REBALANCE_TRIGGER.json", "turnover cost vs realised gain", tags=("P3",)),

    # ---- Phase 4-5: forecast marketplace
    Capability("P4", "universal forecast contract; models publish beliefs, own no positions",
               "desks/mt5/research/forecast_contract.py",
               "desks/mt5/reports/FORECAST_CONTRACT.json",
               "belief weight earned per model", tags=("P4", "forecast")),
    Capability("P5", "forecast calibration marketplace: every model scored forecast -> realized, "
                     "biased predictors recalibrated automatically",
               "desks/mt5/research/model_self_improvement.py",
               "desks/mt5/reports/MODEL_SELF_IMPROVEMENT.json",
               "Brier/MAE skill vs a named baseline, per predictor",
               tags=("P5", "forecast", "self_improvement")),

    # ---- Phase 6-10: the AI layer
    Capability("P6", "learned multi-horizon representation layer, challenger-only", "desks/mt5/research/ml_layer.py", "desks/mt5/reports/ML_LAYER.json",
               "OOS dElog of representation-derived heads", tags=("P6", "ml")),
    Capability("P7", "model zoo benchmarked on dElog after cost and complexity rent",
               "desks/mt5/research/model_zoo.py", "desks/mt5/reports/MODEL_ZOO.json",
               "dElog per model per compute hour", tags=("P7", "ml")),
    Capability("P8", "self-supervised and contrastive learning on unlabelled history", "desks/mt5/research/ml_layer.py", "desks/mt5/reports/ML_LAYER.json",
               "downstream OOS improvement", tags=("P8", "ml")),
    Capability("P9", "financial mixture of experts with an OOS-admitted gate", "desks/mt5/research/ml_layer.py", "desks/mt5/reports/ML_LAYER.json",
               "gate-weighted OOS skill", tags=("P9", "ml")),
    Capability("P10", "live dynamic market graph with state-dependent edges",
               "desks/mt5/research/world_causal_graph.py",
               "desks/mt5/reports/CROSS_ASSET_GRAPH.json",
               "dElog of graph-conditioned forecasts", tags=("P10", "graph")),

    # ---- Phase 11-16: information
    Capability("P11", "information-first discovery: search incremental mutual information, "
                      "reward dN_eff and dElog rather than more transforms of one price",
               "desks/mt5/research/edge_search.py", "desks/mt5/reports/EDGE_SEARCH.json",
               "dN_eff and dElog per search hour", tags=("P11", "discovery")),
    Capability("P12", "data genome and Data ROI with with/without ablations",
               "desks/mt5/research/data_prospector.py", "desks/mt5/reports/DATA_PROSPECTOR.json",
               "dElog / total data cost", tags=("P12", "data")),
    Capability("P13", "residual -> missing information loop, repeated to noise",
               "desks/mt5/research/factor_residual_engine.py",
               "desks/mt5/reports/RESIDUAL_ALPHA.json",
               "dElog of information added by residual clustering", tags=("P13", "data")),
    Capability("P14", "options intelligence: surface, skew, term structure, implied tails", "desks/mt5/research/market_intelligence.py",
               "desks/mt5/reports/MARKET_INTELLIGENCE.json", "dElog of options-derived features", tags=("P14", "data")),
    Capability("P15", "exchange futures information -- never MT5 tick volume as a substitute",
               "desks/mt5/research/fetch_futures_curves.py", "",
               "dElog of exchange-flow features", tags=("P15", "data")),
    Capability("P16", "physical commodity intelligence, point-in-time only", "desks/mt5/research/market_intelligence.py",
               "desks/mt5/reports/MARKET_INTELLIGENCE.json",
               "dElog of physical features", tags=("P16", "data")),

    # ---- Phase 17-21: the creative organs
    Capability("P17", "market ecology brain: latent participant pressure inferred, never claimed",
               "desks/mt5/research/market_intelligence.py",
               "desks/mt5/reports/MARKET_INTELLIGENCE.json", "OOS predictive value of ecology state", tags=("P17", "ceiling")),
    Capability("P18", "active learning / EVSI drives dataset, experiment and probe choice", "desks/mt5/research/experiment_design.py",
               "desks/mt5/reports/EXPERIMENT_DESIGN.json", "EVSI realised vs predicted", tags=("P18", "ceiling")),
    Capability("P19", "measurement-design brain: cheapest falsifying experiment",
               "desks/mt5/research/experiment_design.py",
               "desks/mt5/reports/EXPERIMENT_DESIGN.json", "compute-hours per survivor", tags=("P19", "ceiling")),
    Capability("P20", "decision regret engine attributing regret to its cause",
               "desks/mt5/research/action_counterfactuals.py",
               "desks/mt5/reports/ACTION_COUNTERFACTUALS.json",
               "regret in Elog by source", tags=("P20", "ceiling")),
    Capability("P21", "distribution-shift sentinel over latent state; never lowers the 20% floor",
               "desks/mt5/research/drift_monitor.py", "desks/mt5/reports/DRIFT.json",
               "loss avoided under shift", tags=("P21", "ceiling")),

    # ---- Phase 22-27: mechanism and market memory
    Capability("P22", "mechanism transfer engine -- transfer mechanism, never configuration",
               "desks/mt5/research/alpha_genome.py", "desks/mt5/reports/ALPHA_GENOME.json",
               "survivors per transfer hypothesis", tags=("P22",)),
    Capability("P23", "market-memory retrieval of nearest historical worlds, PIT only", "desks/mt5/research/market_intelligence.py",
               "desks/mt5/reports/MARKET_INTELLIGENCE.json",
               "dElog of retrieval-conditioned decisions", tags=("P23",)),
    Capability("P24", "'what changed' engine ranking standardized cross-asset surprise", "desks/mt5/research/market_intelligence.py",
               "desks/mt5/reports/MARKET_INTELLIGENCE.json",
               "hit rate of anomaly -> interpretation", tags=("P24",)),
    Capability("P25", "expectations engine: actual vs market-implied as the primary surprise",
               "desks/mt5/research/news_desk.py", "desks/mt5/reports/NEWS_DESK.json",
               "dElog of surprise-conditioned forecasts", tags=("P25", "macro")),
    Capability("P26", "event response surfaces across horizons: shock, discovery, drift, reversal",
               "desks/mt5/research/market_intelligence.py",
               "desks/mt5/reports/MARKET_INTELLIGENCE.json", "dElog by horizon", tags=("P26", "macro")),
    Capability("P27", "expression optimizer: best market to express one information event",
               "desks/mt5/research/execution_resolver.py", "",
               "post-cost alpha per unit risk by expression", tags=("P27",)),

    # ---- Phase 28-33: capacity, scale and lifecycle
    Capability("P28", "capacity engine binding mu(q) and Cost(q) into the optimizer",
               "desks/mt5/research/cost_surface.py", "desks/mt5/reports/COST_SURFACE.json",
               "dElog lost to capacity", tags=("P28", "capital")),
    Capability("P29", "capital-scale morphing: strategy universe as a function of q", "desks/mt5/research/experiment_design.py",
               "desks/mt5/reports/EXPERIMENT_DESIGN.json",
               "dElog by operating tier", tags=("P29", "capital")),
    Capability("P30", "small-capacity alpha desk scored at OUR capital", "desks/mt5/research/experiment_design.py",
               "desks/mt5/reports/EXPERIMENT_DESIGN.json",
               "dElog of sub-scale edges", tags=("P30",)),
    Capability("P31", "tail-alpha desk: E[R | book stress] > 0",
               "desks/mt5/research/tail_alpha_search.py", "desks/mt5/reports/TAIL_ALPHA.json",
               "extra normal growth its diversification permits", tags=("P31",)),
    Capability("P32", "alpha mortality and crowding: shrink before realised alpha dies",
               "desks/mt5/research/decay_monitor.py", "desks/mt5/reports/DECAY.json",
               "loss avoided by early hibernation", tags=("P32",)),
    Capability("P33", "complete evidence-triggered alpha lifecycle",
               "desks/mt5/research/promoter.py", "desks/mt5/reports/PROMOTION.json",
               "live retention per promotion", tags=("P33",)),

    # ---- Phase 34-39: execution and compute
    Capability("P34", "execution intelligence predicting cost, fill probability, adverse selection",
               "desks/mt5/research/execution_intelligence.py",
               "desks/mt5/reports/EXECUTION_INTELLIGENCE.json",
               "alpha captured / alpha available", tags=("P34", "execution")),
    Capability("P35", "execution RL as a challenger, only after the twin is calibrated",
               "desks/mt5/research/rebalance_trigger.py",
               "desks/mt5/reports/REBALANCE_TRIGGER.json", "dElog vs champion execution policy",
               depends_on=("P34",), tags=("P35", "execution")),
    Capability("P36", "alpha capture OS decomposing leakage",
               "desks/mt5/research/missed_growth.py", "desks/mt5/reports/MISSED_GROWTH.json",
               "leakage in Elog by cause", tags=("P36", "execution")),
    Capability("P37", "multi-venue abstraction: forecast -> intent -> order -> venue adapter",
               "desks/mt5/research/execution_resolver.py", "",
               "cost of a venue change to alpha intelligence", tags=("P37", "execution")),
    Capability("P38", "compute allocator scheduling by marginal compute value",
               "libs/ops/compute_ledger.py", "data/compute_ledger.jsonl",
               "dElog per CPU/GPU hour", tags=("P38", "allocator")),
    Capability("P39", "distributed experiment cache keyed on data/feature/model/code/seed",
               "desks/mt5/research/experiment_cache.py",
               "desks/mt5/reports/EXPERIMENT_CACHE.json",
               "cache hit rate, hours saved", tags=("P39", "compute")),

    # ---- Phase 40-46: scaling and model governance
    Capability("P40", "financial scaling-law lab: OOS = f(data, model size, compute)",
               "desks/mt5/research/experiment_cache.py",
               "desks/mt5/reports/EXPERIMENT_CACHE.json",
               "marginal value of data vs model vs compute", tags=("P40", "ml")),
    Capability("P41", "model-size efficient frontier; smallest model at equal rent",
               "desks/mt5/research/model_zoo.py", "desks/mt5/reports/MODEL_ZOO.json",
               "rent per unit inference cost", tags=("P41", "ml")),
    Capability("P42", "distillation: student independently retains the required dElog", "desks/mt5/research/ml_layer.py", "desks/mt5/reports/ML_LAYER.json",
               "student dElog vs teacher", tags=("P42", "ml")),
    Capability("P43", "guarded online learning: champion authoritative, challenger updates, "
                      "promotion on measured evidence, no silent live mutation",
               "desks/mt5/research/model_self_improvement.py",
               "desks/mt5/data/model_skill_track.jsonl",
               "out-of-sample skill gain at promotion", tags=("P43", "self_improvement")),
    Capability("P44", "population-based training selected on hostile OOS evaluation",
               "desks/mt5/research/alpha_evolution.py", "desks/mt5/reports/ALPHA_EVOLUTION.json",
               "survivors per mutation generation", tags=("P44", "ml")),
    Capability("P45", "generative stress worlds -- risk falsification only, never alpha proof",
               "libs/research/counterfactual_world.py",
               "desks/mt5/reports/COUNTERFACTUAL_WORLD.json",
               "risk discovered per synthetic world", tags=("P45", "risk")),
    Capability("P46", "model uncertainty ensemble widening the posterior on disagreement",
               "libs/self_improvement/ensemble_optimizer.py", "",
               "calibration improvement from disagreement", tags=("P46", "ml")),

    # ---- Phase 47-50: adversaries
    Capability("P47", "independent validator/killer agents; research does not grade itself",
               "libs/validation/__init__.py", "desks/mt5/reports/VALIDATION.json",
               "false discoveries caught per validation hour", tags=("P47", "adversary")),
    Capability("P48", "internal bug-bounty / fraud agent rewarded for finding silent defects",
               "desks/mt5/research/adversary.py", "desks/mt5/reports/ADVERSARY.json", "defects found before capital", tags=("P48", "adversary", "ceiling")),
    Capability("P49", "permanent poison canaries continuously rejected by validation",
               "desks/mt5/research/adversary.py", "desks/mt5/reports/ADVERSARY.json", "canary rejection rate (must stay 100%)", tags=("P49", "adversary")),
    Capability("P50", "model of the desk: digital twin of the research organisation itself",
               "desks/mt5/research/opportunity_gap.py",
               "desks/mt5/reports/OPPORTUNITY_GAP.json", "dElog of an organisational change", tags=("P50", "ceiling")),

    # ---- Phase 51-55: research governance
    Capability("P51", "research capital governor allocating across all action types by RROI",
               "desks/mt5/research/research_bandit.py", "desks/mt5/reports/RESEARCH_BANDIT.json",
               "RROI realised vs predicted", tags=("P51", "allocator")),
    Capability("P52", "research program competition on survivors per unit research cost",
               "desks/mt5/research/research_productivity.py",
               "desks/mt5/reports/RESEARCH_PRODUCTIVITY.json",
               "forward survivors per research cost", tags=("P52", "research")),
    Capability("P53", "AI scientist organisation with tracked reputation per agent", "desks/mt5/research/research_org.py",
               "desks/mt5/reports/RESEARCH_ORG.json",
               "net dElog per agent", tags=("P53", "research")),
    Capability("P54", "advocate / skeptic / replicator / validator roles kept separate", "desks/mt5/research/research_org.py",
               "desks/mt5/reports/RESEARCH_ORG.json", "proposals overturned by independent review", tags=("P54", "adversary")),
    Capability("P55", "permanent unknown-unknown budget that expands the ontology",
               "desks/mt5/frontier_intel/unknowns.py", "desks/mt5/reports/FRONTIER_GAPS.json",
               "ontology terms added that later pay rent", tags=("P55", "frontier")),

    # ---- Phase 56-64: the frontier miner
    Capability("P56", "institutional frontier miner: hourly scan -> extract -> gap -> ROI -> "
                      "build -> test -> measure, separate from alpha miners",
               "desks/mt5/frontier_intel/frontier_supervisor.py",
               "desks/mt5/reports/FRONTIER_INTELLIGENCE.json",
               "capabilities replicated that pay rent", tags=("P56", "frontier")),
    Capability("P57", "maximally permissive discovery, strict authority: any public claim may "
                      "inspire a hypothesis, none may bypass independent validation",
               "desks/mt5/frontier_intel/roi.py", "",
               "hypotheses per source vs survivors per source", tags=("P57", "frontier")),
    Capability("P58", "claim genealogy and anti-echo: ten reposts are one lineage",
               "desks/mt5/research/adversary.py", "desks/mt5/reports/ADVERSARY.json",
               "corroboration count corrected for lineage", tags=("P58", "frontier")),
    Capability("P59", "multilingual regional scouts with native-context queries",
               "desks/mt5/frontier_intel/registry.py", "",
               "survivors per region per scout hour", tags=("P59", "frontier")),
    Capability("P60", "frontier-of-frontiers: transferable methods from adjacent sciences",
               "desks/mt5/research/research_org.py",
               "desks/mt5/reports/RESEARCH_ORG.json", "cross-domain hypotheses that survive", tags=("P60", "frontier")),
    Capability("P61", "institutional gap graph firm -> process -> capability -> gap -> rent",
               "desks/mt5/frontier_intel/ontology.py", "desks/mt5/reports/FRONTIER_GAPS.json",
               "gaps closed that pay rent", tags=("P61", "frontier")),
    Capability("P62", "frontier autonomous implementer: gap -> branch -> build -> tests -> "
                      "canaries -> zero-authority challenger -> rent -> promote or graveyard",
               "desks/mt5/research/research_org.py",
               "desks/mt5/reports/RESEARCH_ORG.json", "capabilities autonomously landed that pay rent",
               depends_on=("P56", "P61"), tags=("P62", "frontier")),
    Capability("P63", "complexity rent: net dElog = gross - compute - latency - maintenance",
               "libs/ops/module_rent.py", "desks/mt5/data/module_rent.jsonl",
               "net dElog after complexity rent", tags=("P63",)),
    Capability("P64", "frontier source / firm / agent ROI tracked separately from truth",
               "desks/mt5/frontier_intel/roi.py", "desks/mt5/reports/FRONTIER_INTELLIGENCE.json",
               "idea yield vs truth rate per source", tags=("P64", "frontier")),

    # ---- Phase 65-69: arbitration and portfolio
    Capability("P65", "theory vs empirics arbitrator over P(mechanism) and P(empirical edge)",
               "desks/mt5/research/experiment_design.py",
               "desks/mt5/reports/EXPERIMENT_DESIGN.json", "survival rate by quadrant", tags=("P65", "ceiling")),
    Capability("P66", "opportunity-gap monitor decomposing G by cause",
               "desks/mt5/research/opportunity_gap.py",
               "desks/mt5/reports/OPPORTUNITY_GAP.json",
               "largest G component, and its closure", tags=("P66", "ceiling")),
    Capability("P67", "missing-sleeve generator targeting uncovered states",
               "desks/mt5/research/portfolio_gap.py", "desks/mt5/reports/PORTFOLIO_GAP.json",
               "dElog of newly covered states", tags=("P67",)),
    Capability("P68", "effective breadth as a first-class KPI over covariance, factor and tail",
               "desks/mt5/research/alpha_breadth.py", "desks/mt5/reports/EFFECTIVE_BREADTH.json",
               "dN_eff per research unit", tags=("P68",)),
    Capability("P69", "portfolio alpha, not strategy alpha: score by dElog of the BOOK",
               "desks/mt5/research/pf_allocator.py", "desks/mt5/reports/ALLOCATOR_STACK.json",
               "dElog_book per candidate", tags=("P69", "allocator")),

    # ---- Phase 70-77: worlds, counterfactuals, reproducibility
    Capability("P70", "full world simulator jointly carrying edge, state, cost and broker risk",
               "libs/research/counterfactual_world.py",
               "desks/mt5/reports/COUNTERFACTUAL_WORLD.json",
               "E_{Theta,S,E,C}[log W]", tags=("P70", "risk")),
    Capability("P71", "structural counterfactuals: World|event vs World|not-event",
               "desks/mt5/research/counterfactual_replay.py", "",
               "event causal contribution separated from drift", tags=("P71", "macro")),
    Capability("P72", "full counterfactual decision ledger over every alternative action",
               "desks/mt5/research/action_counterfactuals.py",
               "desks/mt5/reports/ACTION_COUNTERFACTUALS.json",
               "regret by alternative", tags=("P72",)),
    Capability("P73", "exit / re-entry / pyramid researched as separate alpha domains",
               "desks/mt5/research/exit_study.py", "desks/mt5/reports/EXIT_STUDY.json",
               "incremental Elog of the exit rule", tags=("P73",)),
    Capability("P74", "research reproducibility: every experiment hashed and never overwritten",
               "desks/mt5/research/registry.py", "desks/mt5/reports/EXPERIMENT_LEDGER.json",
               "reproducible fraction of experiments", tags=("P74", "research")),
    Capability("P75", "graveyard meta-learning: P(pass | hypothesis DNA) from failures",
               "libs/research/graveyard_model.py", "docs/graveyard.md",
               "precision gain from learned taste", tags=("P75", "research")),
    Capability("P76", "alpha genome complete; multiplicity operates on mechanism ancestry",
               "desks/mt5/research/alpha_genome.py", "desks/mt5/reports/ALPHA_GENOME.json",
               "family-corrected discovery rate", tags=("P76",)),
    Capability("P77", "research throughput KPIs including cost per survivor",
               "desks/mt5/research/research_productivity.py",
               "desks/mt5/reports/RESEARCH_PRODUCTIVITY.json",
               "survivors per compute and engineering hour", tags=("P77", "research")),

    # ---- Phase 78-84: the closed flywheel
    Capability("P78", "daily autonomous retrospective feeding the governor",
               "desks/mt5/research/daily_cycle.py", "desks/mt5/reports/DAILY.json",
               "actions taken from the retrospective", tags=("P78",)),
    Capability("P79", "permanent challenge league on equal evidence, dates, costs, heat, worlds",
               "desks/mt5/research/model_zoo.py", "desks/mt5/reports/CHALLENGE_LEAGUE.json",
               "champion changes justified by measured gain", tags=("P79", "ceiling")),
    Capability("P80", "organisation KPIs: alpha/data/compute yield, live retention, capture",
               "desks/mt5/research/research_productivity.py",
               "desks/mt5/reports/RESEARCH_PRODUCTIVITY.json",
               "the KPI set itself", tags=("P80", "research")),
    Capability("P81", "quant intelligence score, reporting-only, never a capital input",
               "desks/mt5/research/opportunity_gap.py",
               "desks/mt5/reports/OPPORTUNITY_GAP.json",
               "reporting only -- must never route to capital", tags=("P81",)),
    Capability("P82", "information provenance graph from position back to raw observation",
               "libs/ops/input_provenance.py", "docs/research/data_provenance.json",
               "forecasts identified per broken feed", tags=("P82", "data")),
    Capability("P83", "P&L attribution back through forecast, model, feature, dataset",
               "desks/mt5/research/allocator_attribution.py",
               "desks/mt5/reports/ALLOCATOR_ATTRIBUTION.json",
               "wealth earned per dataset", tags=("P83", "data")),
    Capability("P84", "the complete discovery flywheel, closed continuously",
               "desks/mt5/research/hourly_cycle.py", "desks/mt5/reports/HOURLY_CYCLE.json",
               "cycle throughput and its dElog",
               depends_on=("P11", "P13", "P51"), tags=("P84",)),

    # ---- the seven allocators
    Capability("A1", "frontier allocator: which observable capability deserves replication",
               "desks/mt5/frontier_intel/queue.py", "desks/mt5/reports/FRONTIER_INTELLIGENCE.json",
               "dElog per replication effort", tags=("allocator",)),
    Capability("A2", "information allocator: which data deserves acquisition",
               "desks/mt5/research/data_prospector.py", "desks/mt5/reports/DATA_PROSPECTOR.json",
               "dElog per data cost", tags=("allocator",)),
    Capability("A3", "research allocator: which question deserves investigation",
               "desks/mt5/research/research_bandit.py", "desks/mt5/reports/RESEARCH_BANDIT.json",
               "survivors per research unit", tags=("allocator",)),
    Capability("A4", "compute allocator: which job deserves CPU/GPU",
               "libs/ops/compute_ledger.py", "data/compute_ledger.jsonl",
               "dElog per compute hour", tags=("allocator",)),
    Capability("A5", "forecast allocator: which model deserves belief weight",
               "desks/mt5/research/model_self_improvement.py",
               "desks/mt5/reports/MODEL_SELF_IMPROVEMENT.json",
               "skill-weighted belief", tags=("allocator",)),
    Capability("A6", "capital allocator: which opportunity deserves money",
               "desks/mt5/research/pf_allocator.py", "desks/mt5/reports/ALLOCATOR_STACK.json",
               "dElog per unit capital", tags=("allocator",)),
    Capability("A7", "execution allocator: how an intended position is implemented",
               "desks/mt5/research/execution_resolver.py",
               "desks/mt5/reports/EXECUTION_INTELLIGENCE.json",
               "alpha captured / alpha available", tags=("allocator",)),
)


# ---------------------------------------------------------------- stage derivation


def _read(rel: str) -> str:
    p = ROOT / rel
    try:
        return p.read_text("utf-8", errors="ignore") if p.is_file() else ""
    except OSError:
        return ""


_SURFACE_TEXT: str | None = None


def _surfaces() -> str:
    global _SURFACE_TEXT
    if _SURFACE_TEXT is None:
        _SURFACE_TEXT = "\n".join(_read(rel) for rel in SCHEDULER_SURFACES)
    return _SURFACE_TEXT


_IMPORTS: dict[str, int] | None = None


def _import_counts() -> dict[str, int]:
    """How many PRODUCTION files REACH each module. Tests deliberately excluded.

    A module reached only by its own tests is CODED, not WIRED, and conflating the two is how a
    package of twenty carefully-tested modules can sit in a repository changing nothing -- which
    is measurably what happened to libs/self_improvement.

    REACHED, NOT IMPORTED, and the distinction was a false negative worth 34 rows. The first
    version counted `import` statements only, and this desk runs its heavy producers as
    SUBPROCESSES -- `hourly_cycle._producer("world_causal_graph", "research/world_causal_graph.py")`
    launches a module it never imports. Grading those as unwired would have had the auditor
    reporting a third of the desk as dead code, and an auditor that cries wolf is one nobody
    reads, which is the failure mode it exists to prevent in everything else.
    """
    global _IMPORTS
    if _IMPORTS is not None:
        return _IMPORTS
    counts: dict[str, int] = {}
    skip = {".git", ".venv", "node_modules", "__pycache__", ".pytest_cache"}
    for parent, dirs, files in os.walk(ROOT):
        dirs[:] = [d for d in dirs if d not in skip]
        for name in files:
            if not name.endswith(".py"):
                continue
            p = Path(parent) / name
            rel = p.relative_to(ROOT).as_posix()
            if "/tests/" in f"/{rel}" or rel.startswith("tests/"):
                continue
            try:
                src = p.read_text("utf-8", errors="ignore")
            except OSError:
                continue
            for mod in re.findall(r"(?:from|import)\s+([a-zA-Z_][\w.]*)", src):
                leaf = mod.split(".")[-1]
                counts[leaf] = counts.get(leaf, 0) + 1
                counts[mod] = counts.get(mod, 0) + 1
            # Subprocess and CLI references: "research/world_causal_graph.py", 'scripts/x.py'.
            for ref in re.findall(r"['\"][\w/]*?([a-zA-Z_][\w]*)\.py['\"]", src):
                counts[ref] = counts.get(ref, 0) + 1
    _IMPORTS = counts
    return counts


_GRAPH_STAGES: dict[str, str] | None = None


def _graph_stages() -> dict[str, str]:
    """Capability-graph stage by module, computed once per audit process.

    ``stages()`` performs artifact and reachability checks. Calling it once for each of the 94
    blueprint rows made the completion fence take many minutes and regularly overrun its own
    schedule. The graph is immutable during one audit, so recomputation cannot add information.
    """
    global _GRAPH_STAGES
    if _GRAPH_STAGES is not None:
        return _GRAPH_STAGES
    try:
        from libs.ops.capability_graph import NODES, stages
        node_stages = stages()
    except Exception:
        _GRAPH_STAGES = {}
        return _GRAPH_STAGES
    out: dict[str, str] = {}
    for node in NODES:
        stem = Path(str(getattr(node, "module", "") or "")).stem
        if stem:
            out[stem] = str((node_stages.get(node.name) or {}).get("stage", "") or "")
    _GRAPH_STAGES = out
    return out


def _graph_stage(module_stem: str) -> str:
    """What the capability graph says about the node owning this module, if any."""
    return _graph_stages().get(module_stem, "") if module_stem else ""


def _rent_verdict(module_stem: str) -> str:
    try:
        from libs.ops import module_rent as mr
    except Exception:
        return ""
    for m in getattr(mr, "MODULES", ()):
        if module_stem and module_stem in str(getattr(m, "name", "")):
            return "MEASURED"
    return ""


def stage_of(cap: Capability) -> tuple[str, list[str]]:
    """The rung this capability has actually reached, and every rung it failed to clear.

    STRICT AND MONOTONE. Each test is only asked once its predecessor passed, because the rungs
    are not independent claims: a cron line naming a module nobody imports schedules code that
    changes nothing, and reporting that as SCHEDULED would be worse than reporting CODED.
    """
    gaps: list[str] = []
    if not cap.owner:
        return "MISSING", ["no owner module exists on this tree"]
    owner = ROOT / cap.owner
    if not owner.exists():
        return "MISSING", [f"owner {cap.owner} does not exist"]

    stem = Path(cap.owner).stem
    if owner.suffix != ".py":
        # A data artifact (release_identity.json, module_rent.jsonl) is its own producer's output;
        # its rungs are existence and being read, not import and schedule.
        return ("RUNNING" if owner.stat().st_size > 2 else "CODED"), []

    imports = _import_counts().get(stem, 0)
    if imports < 2:                      # its own definition counts once
        gaps.append(f"no production module imports {stem} -- CODED but unwired")
        return "CODED", gaps

    if stem not in _surfaces() and f"{stem}.py" not in _surfaces():
        gaps.append(f"no scheduler surface names {stem} -- it is wired but nothing runs it")
        return "WIRED", gaps

    art = (ROOT / cap.artifact) if cap.artifact else None
    if art is None or not art.exists():
        gaps.append(f"artifact {cap.artifact or '(undeclared)'} absent on this host -- "
                    f"scheduled, but no evidence it has produced anything here")
        return "SCHEDULED", gaps

    gstage = _graph_stage(stem)
    if gstage not in ("DECISION_AFFECTING", "MEASURED", "LIVE_LEARNING"):
        gaps.append(f"capability graph reports {gstage or 'no node'} -- running, but no proven "
                    f"route from this artifact into a decision")
        return "RUNNING", gaps

    if _rent_verdict(stem) != "MEASURED":
        gaps.append(f"no MODULE_RENT line prices {stem} -- decision-affecting but unpriced")
        return "DECISION_AFFECTING", gaps

    if cap.awaiting:
        gaps.append(f"MEASURING: {cap.awaiting}")
        return "MEASURED", gaps
    return "PROVEN", gaps


def audit() -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for cap in REGISTRY:
        stage, gaps = stage_of(cap)
        blocked = [d for d in cap.depends_on
                   if STAGES.index(stage_of(next(c for c in REGISTRY if c.id == d))[0])
                   < STAGES.index("SCHEDULED")]
        rows.append({
            "capability_id": cap.id,
            "requirement": cap.requirement,
            "owner_module": cap.owner or None,
            "artifact": cap.artifact or None,
            "rent_metric": cap.rent_metric,
            "current_stage": stage,
            "open_gap": gaps[0] if gaps else "",
            "all_gaps": gaps,
            "blocking_dependencies": blocked,
            "tags": list(cap.tags),
        })
    counts = {s: sum(1 for r in rows if r["current_stage"] == s) for s in STAGES}
    problems: list[str] = []

    # THE MANDATE'S OWN CI CONDITIONS, each one checked rather than described.
    floor = _read("desks/mt5/research/heat_policy.py")
    if "floor = target if mandate else 0.0" not in floor:
        problems.append(
            "the 20% nominal heat floor is no longer flat in heat_policy.resolve -- the "
            "principal's ONE fixed policy. Whatever mechanism now scales it must be removed.")
    if re.search(r"floor\s*=\s*[^\n]*readiness", floor):
        problems.append("readiness appears in the floor expression -- it may gate composition "
                        "and authority ABOVE the floor, never the floor itself")
    for r in rows:
        if r["current_stage"] == "MEASURED" and not r["rent_metric"]:
            problems.append(f"{r['capability_id']} reads MEASURED with no rent metric declared")

    return {
        "at": datetime.now(UTC).isoformat(),
        "total_capabilities": len(rows),
        **{s.lower(): counts[s] for s in STAGES},
        "blocked": sum(1 for r in rows if r["blocking_dependencies"]),
        "capabilities": rows,
        "problems": problems,
        "status": "BREACH" if problems else ("INCOMPLETE" if counts["MISSING"] or
                                             counts["CODED"] else "COMPLETE"),
        "host_note": ("artifact-dependent rungs (RUNNING and above) can only be graded where the "
                      "artifacts live. On a host without the lake every such rung answers in the "
                      "negative, which is honest rather than green."),
        "law": ("stages are DERIVED from this tree, never declared. A capability is not complete "
                "at CODED or WIRED; PROVEN requires forward evidence and a priced rent."),
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--gaps", action="store_true", help="only capabilities with an open gap")
    ap.add_argument("--phase", default="", help="one capability id, e.g. P17")
    args = ap.parse_args(argv)
    doc = audit()
    try:
        REPORT.parent.mkdir(parents=True, exist_ok=True)
        REPORT.write_text(json.dumps(doc, indent=1, default=str), "utf-8")
    except OSError:
        pass
    if args.json:
        print(json.dumps(doc, indent=1, default=str))
        return 2 if doc["problems"] else 0
    print(f"ABSOLUTE CEILING: {doc['total_capabilities']} capabilities -- {doc['status']}")
    print("  " + "  ".join(f"{s}={doc[s.lower()]}" for s in STAGES))
    rows = doc["capabilities"]
    if args.phase:
        rows = [r for r in rows if r["capability_id"] == args.phase]
    elif args.gaps:
        rows = [r for r in rows if r["open_gap"]]
    for r in rows:
        print(f"  {r['current_stage']:18s} {r['capability_id']:5s} {r['requirement'][:78]}")
        if r["open_gap"]:
            print(f"                     GAP: {r['open_gap']}")
        if r["blocking_dependencies"]:
            print(f"                     BLOCKED BY: {r['blocking_dependencies']}")
    for p in doc["problems"]:
        print(f"  BREACH {p}")
    return 2 if doc["problems"] else 0


if __name__ == "__main__":
    raise SystemExit(main())

```

### scripts\check_doctrine_diff.py
```python
#!/usr/bin/env python3
"""DOCTRINE-DIFF TRIGGER (R0093, deep-sweep SYNTH0731 P1-8c, meta X6/M6).

ops/principal_doctrine.txt is the principal's order channel: every edit to it is the
principal surfacing a gap the desk did not find itself -- the exact FAILURE SIGNAL the
blind-spot origin gauge (L2.5, blind_spot.py) exists to count. The gauge logged ZERO
principal rows across 6+ doctrine orders since 07-26 because nothing wired the channel
to it; a failure-signal gauge nothing feeds reads as success. This organ closes the wire:
it hashes the doctrine every run, and a changed hash auto-logs ONE blind-spot row
origin=principal carrying a real diff summary.

Design decisions that matter:
  * state = data/doctrine_hash.json plus a full previous copy (data/doctrine_prev.txt),
    so the row carries "+a/-r lines" and the first added line, not just "changed".
  * FIRST RUN BASELINES silently -- the gauge measures orders, not this wiring's birthday.
  * corrupt state re-baselines LOUDLY: the degrade direction is never-suppress-the-NEXT-
    detection, accepting one missed diff over a permanently welded gauge.
  * doctrine ABSENT or UNREADABLE exits 2 -- this organ cannot measure, and an unrunnable
    fence counts as FAILED, never skipped (L1.37).
  * the row is written through blind_spot.log (one writer, one schema); logging happens
    BEFORE the state update, so a crash between the two duplicates a row rather than
    silently dropping an order.

    python scripts/check_doctrine_diff.py
"""
from __future__ import annotations

import difflib
import hashlib
import json
import sys
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

DOCTRINE = _ROOT / "ops/principal_doctrine.txt"
STATE = _ROOT / "data/doctrine_hash.json"
PREV = _ROOT / "data/doctrine_prev.txt"


def _summary(prev_text: str, new_text: str) -> str:
    diff = list(difflib.unified_diff(prev_text.splitlines(), new_text.splitlines(),
                                     lineterm="", n=0))
    added = [ln[1:].strip() for ln in diff if ln.startswith("+") and not ln.startswith("+++")]
    removed = [ln for ln in diff if ln.startswith("-") and not ln.startswith("---")]
    first = next((a for a in added if a), "")
    return (f"principal_doctrine.txt changed: +{len(added)}/-{len(removed)} lines"
            + (f'; first added: "{first[:140]}"' if first else ""))


def check(doctrine: Path = DOCTRINE, state: Path = STATE, prev: Path = PREV,
          log_row: Callable[[SimpleNamespace], None] | None = None) -> tuple[str, int]:
    """Returns (verdict, exit_code). Verdicts: UNREADABLE / BASELINED / REBASELINED /
    UNCHANGED / ORDER-LOGGED."""
    try:
        text = doctrine.read_text("utf-8")
    except OSError as exc:
        print(f"DOCTRINE-UNREADABLE: {doctrine} ({exc}) -- cannot measure, refusing to pass")
        return "UNREADABLE", 2

    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    now = datetime.now(tz=UTC).isoformat()
    fresh_state = {"sha256": digest, "lines": len(text.splitlines()), "seen_at": now}

    old: dict | None = None
    rebaseline = False
    if state.exists():                       # absent state = first run, not a failure
        try:
            parsed = json.loads(state.read_text("utf-8"))
            if not isinstance(parsed, dict) or not parsed.get("sha256"):
                raise ValueError("state carries no hash")
            old = parsed
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            rebaseline = True
            print(f"STATE-CORRUPT ({exc!r}): re-baselining LOUDLY -- one diff may be lost, "
                  "the next one will not be")

    if old is None or rebaseline:
        state.parent.mkdir(parents=True, exist_ok=True)
        state.write_text(json.dumps(fresh_state, indent=1), "utf-8")
        prev.write_text(text, "utf-8")
        verdict = "REBASELINED" if rebaseline else "BASELINED"
        print(f"{verdict}: sha {digest[:12]} ({fresh_state['lines']} lines)")
        return verdict, 0

    if old["sha256"] == digest:
        print(f"UNCHANGED: sha {digest[:12]} (last change seen {old.get('seen_at', '?')[:19]})")
        return "UNCHANGED", 0

    prev_text = prev.read_text("utf-8") if prev.exists() else ""
    summary = _summary(prev_text, text)
    if log_row is None:
        from scripts.blind_spot import log as log_row  # one writer, one schema
    log_row(SimpleNamespace(origin="principal", summary=summary,
                            angle="doctrine-diff", severity="high"))
    state.write_text(json.dumps(fresh_state, indent=1), "utf-8")
    prev.write_text(text, "utf-8")
    print(f"ORDER-LOGGED: {summary[:160]}")
    return "ORDER-LOGGED", 0


def main() -> int:
    from libs.ops.lawful import guard
    guard()
    _, rc = check()
    return rc


if __name__ == "__main__":
    sys.exit(main())

```
