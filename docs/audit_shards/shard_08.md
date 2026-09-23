# AUDIT SHARD 8/24 -- seat nvidia/nemotron-3.5-lightning

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

### libs\ops\module_rent.py
```python
"""MODULE RENT -- Elog_with - Elog_without for EVERY component, and a RETIRE list a person reads.

    "Module Rent = Elog_with - Elog_without for every component; if persistently <= 0, retire it.
     This includes AI. No sacred modules."                          -- the principal, 2026-09-05

WHY A SECOND LEDGER WHEN MISSED_GROWTH EXISTS. `research/missed_growth.py` bills the RAILS -- every
veto, cap, shrinkage and gate registered in `libs.portfolio.rails` -- and nothing else. Measured on
this tree 2026-09-05: no miner, proposer arm, state dimension, execution algorithm, allocator
component, data source or AI organ carried an Elog_with / Elog_without line anywhere, and nothing
on the desk retires at <= 0. A component nothing bills is a component nothing can retire, which is
how a desk accumulates organs that compute and cost and are never asked what they are for.

THE REGISTRY declares, per module, WHICH ledger measures it and BY WHAT RULE. Nothing here is
recomputed from raw evidence when the desk already keeps the number:

    rail                  MISSED_GROWTH.json, reused verbatim (the rail's own daily ledger line)
    proposer              RESEARCH_PNL.json per bandit arm: the growth its certificates carry in
                          the funded book, spend in DECLARED cost units beside it
    state_dimension       STATE_ADMISSION.json (out-of-sample gain of conditioning on the
                          dimension) and the conditioning ledger (heat the modifier moved x what
                          that heat then earned: with vs without the modifier, realised daily)
    execution_algo        execution_algo_outcomes.jsonl through `execution_registry.scoreboard`:
                          each algorithm's realised cost against the market baseline's, per fill
    allocator_component   pf_allocation.json: the dynamic weights against the best baseline the
                          proof scored, the posterior book against the funded one, the Kelly
                          surface's tail bound against the unbounded book
    data_source           the dimension a source feeds (admission + conditioning ledger) or the
                          RESEARCH_PNL source row its hypotheses land on
    ai_organ              the AI capital modifier's conditioning ledger, and the LLM-driven miners'
                          RESEARCH_PNL rows. "This includes AI."

UNITS ARE NAMED, NEVER ASSUMED. `rent_logw_per_day` is filled only where the ledger prices the
module in log-wealth per day; where the ledger's unit is something else (an out-of-sample MSE
gain, a fraction of price per fill) `rent` and `unit` carry the number and `rent_logw_per_day`
is None. A verdict is still owed in every unit -- the principal's question is the sign.

VERDICTS
    EARNS        rent > 0, with n >= MIN_N and (where the ledger gives daily samples) t > T_LINE
    COSTS        rent < 0 on the same terms
    NOT_BINDING  the module did not fire, had no trials, or IS the baseline it would be measured
                 against (the market algorithm)
    UNMEASURED   the ledger is absent on this host, thin, or the sign is not distinguishable from
                 zero. Said, with the path and the count -- never folded into a pass (L1.28a)

THE RETIRE LIST NAMES; IT DOES NOT RETIRE. A module is listed when it has read COSTS with
n >= MIN_N in K_WINDOWS consecutive weekly windows of its own history (`data/module_rent.jsonl`,
one row per module per day, appended once). Retirement is a person's decision or the capability
graph's check; this report is the evidence, and the evidence carries the ledger it came from so
the decision can be audited against the number rather than the verdict.
"""

from __future__ import annotations

import json
import math
import statistics
import sys
from collections import defaultdict
from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from libs.portfolio.rails import RAILS
from libs.research.bandit import ARMS, SOURCE_ARM

ROOT = Path(__file__).resolve().parents[2]

#: RESEARCH_ALLOCATOR was registered without being declared here (commit 7f894766, 2026-09-06),
#: so `frontier_roi` -- the ranker that decides which external capability gets replication effort
#: -- failed the registry's own arity check from the moment it was priced. A module whose KIND is
#: unknown cannot be billed, and the fence that exists to catch unbilled modules was the thing
#: refusing it. It is a real kind: the blueprint's allocator hierarchy has research sitting beside
#: capital and compute, and it decides where effort goes rather than where money does.
KINDS: tuple[str, ...] = ("rail", "proposer", "state_dimension", "execution_algo",
                          "allocator_component", "research_allocator", "data_source",
                          "ai_organ", "organ")
EARNS, COSTS, NOT_BINDING, UNMEASURED = "EARNS", "COSTS", "NOT_BINDING", "UNMEASURED"

#: Samples (days, trials, fills, test trades) before a verdict is a verdict.
MIN_N = 10
#: |t| a daily ledger must clear before its mean is called a sign rather than noise.
T_LINE = 2.0
#: Consecutive weekly windows of COSTS (each with n >= MIN_N) before a module is NAMED for
#: retirement.
K_WINDOWS = 3
#: A conditioning multiplier below this has no finite "without" heat under the linearisation
#: (heat proportional to the posterior mean); the row is priced at the floor rather than skipped.
MULT_FLOOR = 0.05

# Every ledger this reads, repo-relative, so `measure(root)` can be pointed at a fixture tree.
MISSED_GROWTH = "desks/mt5/reports/MISSED_GROWTH.json"
RESEARCH_PNL = "desks/mt5/reports/RESEARCH_PNL.json"
STATE_ADMISSION = "desks/mt5/reports/STATE_ADMISSION.json"
CAPITAL_MODIFIERS = "desks/mt5/reports/CAPITAL_MODIFIERS.json"
ALLOCATION = "desks/mt5/reports/pf_allocation.json"
MODIFIER_LEDGER = "desks/mt5/data/capital_modifier_ledger.jsonl"
ALGO_OUTCOMES = "desks/mt5/data/execution_algo_outcomes.jsonl"
SHADOW_DIR = "desks/mt5/reports/shadow/"          # trailing slash: the graph names dirs so
LIVE_LEDGER = "desks/mt5/data/live_ledger.jsonl"
HISTORY = "desks/mt5/data/module_rent.jsonl"
REPORT = "desks/mt5/reports/MODULE_RENT.json"
#: THE EXECUTION-LEARNING LINE (2026-09-05). The fill corpus and the two models built on it.
ALPHA_CAPTURE = "desks/mt5/reports/ALPHA_CAPTURE.json"
CAPTURE_HISTORY = "desks/mt5/data/alpha_capture_history.jsonl"
EXECUTION_TWIN = "desks/mt5/reports/EXECUTION_TWIN.json"
#: THE FRESHNESS LINE (2026-09-08). `scripts/check_job_manifest.py` already counts every SLO
#: breach against a per-artifact age limit and names the consumer; it publishes a SNAPSHOT
#: (data/job_manifest.json), and the day-keyed history a with/without split needs is its
#: append-only companion. Neither is recomputed here: the fence owns the breach definition.
JOB_MANIFEST = "data/job_manifest.json"
FRESHNESS_HISTORY = "data/freshness_breaches.jsonl"
#: The JOBS rows whose staleness means the desk acted on a STALE VIEW OF THE MARKET rather than
#: on a late report: the three forward-book states, each rebuilt from bars every cycle, and the
#: published desk state the dashboard and the operator read. A JOBS row not listed here is not
#: counted, so the denominator of this rent line is explicit rather than "whatever was red".
FRESHNESS_ARTIFACTS: tuple[str, ...] = (
    "desks/mt5/reports/shadow/shadow_state.json",
    "desks/mt5/reports/shadow/scalp_shadow_state.json",
    "desks/mt5/reports/shadow/qquant_shadow_state.json",
    "web/desk_state.json",
)
#: A breach is the fence's own verdict: too old, never produced, or produced with nothing in it.
#: FROZEN and IDLE are NOT breaches -- identical bytes can be the correct output (L1.37).
BREACH_STATUSES: frozenset[str] = frozenset({"STALE", "MISSING", "EMPTY"})

#: The execution algorithms the registry competes (mt5desk.execution_registry). `market` is the
#: baseline every other one is measured against, so its own rent is zero by definition.
EXECUTION_ALGOS: tuple[str, ...] = ("market", "twap", "iceberg", "sniper", "pullback")
BASELINE_ALGO = "market"
#: State dimensions the admission gauntlet judges on this desk, and the data source each one is
#: read from. A dimension the report judges that is not listed here is discovered at measure time.
DIMENSION_SOURCE: dict[str, str] = {"session": "broker_clock", "event": "event_calendar",
                                    "weekday": "weekday_calendar"}
#: LLM-driven organs, by the RESEARCH_PNL source prefixes their hypotheses carry.
AI_ORGANS: dict[str, tuple[str, ...]] = {
    "deepening_worker": ("deepening", "mutation"),
    "deep_forest_miner": ("deep_forest",),
    "repo_miner": ("repo_miner",),
    "world_crawler": ("world_crawler", "crawler"),
}
#: Hypothesis sources that ARE data sources (a prospector row names data the desk lacks).
DATA_HYPOTHESIS_SOURCES: tuple[str, ...] = ("data_prospector", "world")


@dataclass(frozen=True)
class Module:
    """One billable component: what it is, where its ledger is, and the with/without rule."""

    name: str
    kind: str
    ledger: str
    rule: str
    measure: str
    where: str = ""
    #: The row this module is looked up under in its ledger (rail name, arm, algo, dimension...).
    key: str = ""
    #: Prefixes of RESEARCH_PNL source names that roll up to this module.
    sources: tuple[str, ...] = ()


def _rail_modules() -> tuple[Module, ...]:
    return tuple(Module(r.name, "rail", MISSED_GROWTH,
                        "E[log W without the rail] - E[log W with it], billed daily by "
                        "missed_growth; reused verbatim, never recomputed",
                        "measure_rail", r.where, key=r.name) for r in RAILS)


def _proposer_modules() -> tuple[Module, ...]:
    return tuple(Module(a, "proposer", RESEARCH_PNL,
                        "expected log-wealth per day the arm's certificates carry in the funded "
                        "book (the allocator's own claim), spend in declared cost units beside; "
                        "no exchange rate from cost units to log-wealth exists, so the verdict is "
                        "on gross survivor growth and the spend is reported, not netted",
                        "measure_proposer", "libs.research.bandit.ARMS -> research_pnl arms",
                        key=a) for a in ARMS)


# ------------------------------------------------------------------- the organs, billed by use
#
# THE RULE, AND IT IS THE ONE THAT MAKES THE REST OF THIS FILE FINITE. A module's rent is measured
# WHERE IT CHANGES A DECISION. A rail changes the size of a trade, so `missed_growth` prices it; a
# proposer changes what is in the book, so `research_pnl` prices it. But 27 decision-affecting
# organs on this desk -- the gauntlets, the forward clock, the promoter, the execution twin, the
# tape recorder, the counterfactual ledgers, the macro layer -- produce a REPORT, and a report has
# no price of its own. Billing them by their own output would price effort, not value.
#
# So an organ is billed through its CONSUMER, and the chain is read off the capability graph
# rather than restated here: organ -> artifact -> the node that reads the artifact -> that node's
# own rent. Three outcomes, and the middle one is the reason this is worth building:
#
#   NOTHING READS IT   NOT_BINDING, with the artifact named. An organ whose output changes no
#                      decision has zero rent BY CONSTRUCTION, and that is the retire signal the
#                      principal asked for -- "if persistently <= 0, retire it". This is the only
#                      verdict here that can be reached without any live evidence at all, which
#                      is exactly right: it is a wiring fact, not a market fact.
#   READ, PRICED       the consumer carries its own rent line, so the organ inherits the verdict
#                      and the number, with the consumer named. No new arithmetic: two modules in
#                      one chain must never produce two different answers about the same value.
#   READ, UNPRICED     UNMEASURED, naming the consumer AND the ledger that would price it. Never
#                      folded into a pass (L1.28a): "something reads it" is not "it earns".
#
# WHY THE GRAPH RATHER THAN A TABLE HERE. The reader/writer relation already exists, is already
# fenced (`check_read_without_writer`, `check_reachability`), and is already how the desk decides
# whether a producer reaches a decision. A second hand-maintained copy of it in this file would
# drift the moment an organ gained a consumer, and the drift would show up as an organ billed for
# work nobody uses -- the precise failure this whole ledger exists to catch.

#: Organs whose rent is inherited from a consumer, and the artifact the chain runs through. The
#: artifact is named here (rather than taken as "the node's first write") because an organ often
#: writes several and only one of them is the thing a decision is made from.
ORGAN_OUTPUT: dict[str, str] = {
    # -- admission: what reaches the book at all
    "external_gauntlet": "desks/mt5/reports/UNIVERSAL_SURVIVORS.json",
    "universal_gate": "desks/mt5/data/UNIVERSAL_SURVIVORS.canon.json",
    "scalp_gauntlet": "desks/mt5/reports/SCALP_GAUNTLET.json",
    "recertify_canon": "desks/mt5/reports/recertification_audit.json",
    "shadow_forward": "desks/mt5/reports/shadow/",
    "promoter": "desks/mt5/data/sleeves.json",
    "miner_candidate_compiler": "desks/mt5/data/hypotheses/miner_candidates.json",
    # -- execution: what a filled order costs
    "markout": "desks/mt5/reports/markout.json",
    "fill_surface": "desks/mt5/reports/FILL_SURFACE.json",
    "execution_intelligence": "desks/mt5/reports/NETTING.json",
    "execution_twin": "desks/mt5/reports/EXECUTION_TWIN.json",
    "counterfactual_markout": "desks/mt5/reports/FILTER_VALUE.json",
    "counterfactual_replay": "desks/mt5/reports/COUNTERFACTUAL_WORLD.json",
    "action_counterfactuals": "desks/mt5/reports/ACTION_COUNTERFACTUALS.json",
    # -- the tape and the features built on it
    "tick_recorder": "desks/mt5/reports/TAPE_RECORDER.json",
    "tick_integrity": "desks/mt5/reports/TICK_INTEGRITY.json",
    "tape_features": "desks/mt5/data/tape/ticks/",
    "state_vector_build": "desks/mt5/data/state_vector.json",
    # -- learning about the desk itself
    "alpha_genome": "desks/mt5/reports/ALPHA_GENOME.json",
    "feature_roi": "desks/mt5/reports/FEATURE_ROI.json",
    "drift_monitor": "desks/mt5/reports/DRIFT.json",
    "allocator_attribution": "desks/mt5/reports/GROWTH_ATTRIBUTION_WEEKLY.json",
    "research_pnl": "desks/mt5/reports/RESEARCH_PNL.json",
    "macro_intel": "desks/mt5/data/macro/allocator_interrupt.json",
}

#: Organs that ARE the money path or the release gate rather than an input to it. Their rent is
#: not separable and pretending otherwise would be theatre: without `gateway` there are no orders
#: to price, without `release` and `immutable_evaluator` there is no authority to place one, so
#: "E[logW] without it" is not a smaller number -- it is a desk that does not trade. Declared here
#: so they are BILLED AND ANSWERED rather than silently unbillable, which is the state this ledger
#: exists to end. They are not retire candidates and the verdict says why.
INFRASTRUCTURE: dict[str, str] = {
    "gateway": "the order path itself: without it no intent becomes a fill, so there is no "
               "counterfactual book to compare against -- only no book",
    "release": "the release identity that authorises a live order; without it the deadman "
               "refuses to arm and the desk is flat by construction",
    "immutable_evaluator": "the signature that makes a judge's verdict admissible; without it "
                           "no certificate carries authority, so nothing reaches capital to bill",
}


MODULES: tuple[Module, ...] = (
    *_rail_modules(),
    *_proposer_modules(),
    Module("state_posterior", "state_dimension", MODIFIER_LEDGER,
           "heat the state modifier moved x what that heat then earned, realised per day: "
           "sum_s h_s (1 - 1/mult_s) r_s, i.e. E[log W with the modifier] - E[log W without it] "
           "under heat proportional to the posterior mean",
           "measure_conditioning", "libs/portfolio/robust_elog._posterior_mu (state level)"),
    *(Module(f"state_dimension:{d}", "state_dimension", STATE_ADMISSION,
             "walk-forward gain from conditioning on the dimension against not conditioning "
             "(unit: out-of-sample MSE gain, t deflated for the dimensions tried)",
             "measure_admission", "libs/regime/state_admission", key=d)
      for d in DIMENSION_SOURCE),
    *(Module(f"execution_algo:{a}", "execution_algo", ALGO_OUTCOMES,
             "market baseline's mean realised cost minus the algorithm's, per filled plan, as a "
             "fraction of price against the reference quote (execution_registry.scoreboard)",
             "measure_execution_algo", "mt5desk.execution_registry.scoreboard", key=a)
      for a in EXECUTION_ALGOS),
    Module("pf_allocator:dynamic_weights", "allocator_component", ALLOCATION,
           "proof scores: mean log growth per day of the dynamic book minus the best baseline "
           "book at the same total heat on the same sampled worlds",
           "measure_dynamic_weights", "libs/portfolio/allocator_proof.contest"),
    Module("pf_allocator:posterior_growth", "allocator_component", ALLOCATION,
           "posterior multi-period book minus the funded book on identical sampled paths, "
           "bootstrap CI (posterior_growth.compare)",
           "measure_posterior_growth", "libs/portfolio/posterior_growth"),
    Module("pf_allocator:kelly_surface", "allocator_component", ALLOCATION,
           "mean growth at the tail-bounded fraction minus at the book's own fraction, when the "
           "tail bound binds (f_tail < 1)", "measure_kelly_surface",
           "libs/portfolio/kelly_surface.surface"),
    Module("pf_allocator:marginal_admission", "allocator_component", ALLOCATION,
           "dE[log W] of the candidates the criterion ADMITTED, each re-solved into the held book "
           "at the same total heat on the same sampled worlds: E[logW | book + i] - E[logW | book]"
           " summed over the admitted set (pf_allocator.marginal_admission)",
           "measure_marginal_admission", "desks/mt5/research/pf_allocator.marginal_admission"),
    Module("hunt12", "allocator_component", ALLOCATION,
           "E[log W] of the solved book with the hypothesis-lane survivors against the same book "
           "without them, at the same total heat on the same sampled worlds. This sweep is the "
           "allocator's FIRST input -- portfolio_projection refuses without its artifact -- so an "
           "absent one is the growth sizer declining to solve, not a missing research report",
           "measure_hunt12_survivors", "desks/mt5/research/run_hunt12.py"),
    Module("pf_allocator:regime_conditioning", "allocator_component", ALLOCATION,
           "needs the book scored on unconditioned worlds beside the conditioned ones; the "
           "artifact carries regime.conditioned but no with/without score",
           "measure_regime_conditioning", "libs/portfolio/robust_elog regime tilt"),
    *(Module(f"data_source:{src}", "data_source", STATE_ADMISSION,
             "the dimension this source feeds: admission gain (with vs without conditioning on "
             "it, out of sample) and its share of the conditioning ledger",
             "measure_admission", f"state dimension {d}", key=d)
      for d, src in DIMENSION_SOURCE.items()),
    *(Module(f"data_source:{src}", "data_source", RESEARCH_PNL,
             "expected log-wealth per day the source's certificates carry in the funded book, "
             "trials beside; <= 0 over the window with trials is dead information",
             "measure_research_source", "research_pnl sources", key=src, sources=(src,))
      for src in DATA_HYPOTHESIS_SOURCES),
    # THE BREADTH LANE'S RENT LINES (2026-09-05). Three producers whose entire output is research
    # instructions, so the only honest ledger is the growth their instructions eventually carry in
    # the funded book -- RESEARCH_PNL, by the source name each one stamps on the tasks it queues
    # (`libs.research.bandit.SOURCE_ARM` maps the same three names to arms). Like the vol archive
    # above, these read UNMEASURED until a queued task becomes a certificate and that certificate
    # carries heat: a research organ cannot be billed for growth before its first hypothesis has
    # been through the gauntlet, and an UNMEASURED row here is the rule working rather than a gap.
    # The measurement is FORWARD by construction, and it arrives without anyone remembering to add
    # a line later.
    Module("alpha_breadth", "proposer", RESEARCH_PNL,
           "expected log-wealth per day carried in the funded book by certificates whose "
           "hypothesis came from an EMPTY-CLUSTER task -- the first sleeve of a phenomenon the "
           "book did not occupy. 'Without' is genuinely nothing: nothing else on the desk names "
           "an unoccupied cluster, so a certificate traced to this source would not exist",
           "measure_research_source", "desks/mt5/research/alpha_breadth.py",
           key="alpha_breadth", sources=("alpha_breadth",)),
    Module("drawdown_alpha", "proposer", RESEARCH_PNL,
           "expected log-wealth per day carried by certificates whose hypothesis came from a "
           "drawdown-state task. THE RENT IS UNDERSTATED BY THIS LEDGER AND THAT IS DELIBERATE: "
           "a tail-positive sleeve's real contribution is the leverage the whole book can then "
           "carry, which shows up as everyone else's growth, not its own. Billing it on its own "
           "growth is the conservative reading and cannot flatter it",
           "measure_research_source", "desks/mt5/research/drawdown_alpha.py",
           key="drawdown_alpha", sources=("drawdown_alpha",)),
    Module("survivor_neighbourhood", "proposer", RESEARCH_PNL,
           "expected log-wealth per day carried by certificates whose hypothesis came from a "
           "survivor-state task -- a state where an existing edge is stronger, or one where it "
           "pays nothing and the heat should go elsewhere",
           "measure_research_source", "desks/mt5/research/survivor_neighbourhood.py",
           key="survivor_neighbourhood", sources=("survivor_neighbourhood",)),
    # THE DATA MOAT'S OWN RENT LINES. A recorder is a component like any other and the principal's
    # rule admits no exception: E[log W] with it minus E[log W] without it, measured forward, or
    # it is retired. That is deliberately an uncomfortable line to write for an asset whose whole
    # argument is that it cannot be re-acquired later -- but "unbuyable" is a reason to start
    # capture TODAY, not a licence to skip the billing. If the tape's certificates carry no
    # growth after a fair window, the correct response is to stop mining it harder, not to keep
    # paying for a disk because the bytes felt precious.
    Module("data_source:tick_tape", "data_source", RESEARCH_PNL,
           "expected log-wealth per day carried in the funded book by certificates whose "
           "mechanism needs the tick tape -- the liquidity_regime and orderflow_imbalance "
           "families, which read data/tape/ticks through orthogonal_sweep._tape_series, plus any "
           "moat-mined candidate. Without the tape those families produce nothing at all, so "
           "'without' is genuinely zero rather than a counterfactual that has to be modelled",
           "measure_research_source", "desks/mt5/recorders/tick_recorder.py",
           key="tick_tape", sources=("liquidity_regime", "orderflow_imbalance", "tape", "moat")),
    # DATA FRESHNESS AS A PRICED COMPONENT (2026-09-08). Measured that day: MODULE_RENT's
    # data_source rows priced the SOURCE (tick_tape, fill_corpus, broker_clock) and NOTHING
    # priced its FRESHNESS -- a tape that arrives late is a different asset from a tape that
    # does not arrive, and only the second had a line. Freshness had a red/green flag
    # (check_job_manifest) with no log-wealth number anywhere, so "the feed lagged six hours"
    # and "the feed lagged six hours and it cost this much growth" were the same sentence.
    #
    # THE COUNTERFACTUAL IS A DAY, NOT A FILL, and that is what makes it billable at all: the
    # fence already labels each day's artifacts breached or clean, so E[log W | fresh] -
    # E[log W | breached] is a two-sample comparison over the desk's own realised days. It reads
    # UNMEASURED until the breach history has rows -- the fence publishes a snapshot today --
    # and that is the module working, not a gap: a freshness line cannot be billed before the
    # desk has recorded a day on which freshness failed AND a day on which it did not.
    Module("data_source:freshness", "data_source", FRESHNESS_HISTORY,
           "mean realised R per day on days when no tape/bar artifact breached its own SLO, "
           "minus the same on days when one did: E[log W with fresh data] - E[log W without it], "
           "over the four artifacts whose staleness means the desk acted on a stale view of the "
           "market. The breach definition and the age limits are check_job_manifest's own and "
           "are never recomputed here",
           "measure_freshness", "scripts/check_job_manifest.py JOBS -> data/job_manifest.json",
           key="freshness"),
    Module("data_source:vol_archive", "data_source", RESEARCH_PNL,
           "expected log-wealth per day carried by certificates conditioned on the implied-vol / "
           "term-structure archive. READS UNMEASURED BY CONSTRUCTION UNTIL IT HAS VINTAGES: the "
           "archive is forward-only, holds no promotion authority in any lane, and cannot have "
           "produced a certificate before its own series is long enough (vol_archive.MIN_VINTAGES"
           "). An UNMEASURED row here is the module working, not a gap -- and it becomes a real "
           "verdict on its own, without anyone having to remember to add the line later",
           "measure_research_source", "desks/mt5/recorders/vol_archive.py",
           key="vol_archive", sources=("vol_archive", "vol_term", "variance_premium",
                                       "implied_vol")),
    # THE FRONTIER RANKER, which decides what gets BUILT rather than what gets traded (P64).
    #
    # It was the last capability holding decision authority with no rent line -- measured
    # 2026-09-06 by blueprint/rent, the single entry in `owing`. That matters more here than for
    # most organs, because this one's whole job is to REFUSE: `roi.py` exists to stop the desk
    # replicating sophisticated capabilities that measurably do nothing, and a refuser nobody
    # prices is a refuser nobody can check. If its rankings are noise, the desk has been
    # allocating engineering by a number it never audited.
    #
    # BILLED ON GROSS SURVIVOR GROWTH, SPEND REPORTED BESIDE, NEVER NETTED -- the same rule
    # `_proposer_modules` uses, and for the same reason: the honest counterfactual is "what those
    # engineering hours would have produced elsewhere", no exchange rate exists between cost
    # units and log-wealth, and inventing one would let this module price its own success. So the
    # verdict is on what frontier-sourced mechanisms actually carry in the funded book, which is
    # the conservative reading and cannot flatter it.
    #
    # UNMEASURED IS THE EXPECTED STATE TODAY AND IS NOT A GAP. No replication this ranked has
    # reached a certificate yet, so the ledger has nothing to bill; that is the module working
    # under §135's rule that an upstream organ cannot be charged in E[log W] before its output
    # reaches capital. It becomes a real number the first time a frontier-sourced mechanism
    # certifies, and a NEGATIVE one is the signal §158 wants: retire the ranker, not the desk.
    Module("frontier_roi", "research_allocator", RESEARCH_PNL,
           "expected log-wealth per day carried in the funded book by certificates whose "
           "mechanism came from a replication this ranker prioritised, against the same census "
           "for mechanisms it ranked out; engineering spend reported alongside in its own units "
           "and never subtracted, because no exchange rate from engineering hours to log-wealth "
           "exists and inventing one would let the ranker price its own success",
           "measure_research_source", "desks/mt5/frontier_intel/roi.py",
           key="frontier_roi", sources=("frontier", "frontier_intel", "frontier_replication",
                                        "repo_miner", "deep_forest", "world_crawler")),
    # ------------------------------------------------------------------------------------------
    # NINE DISCOVERY ORGANS THE RENT LEDGER COULD NOT NAME (2026-09-05).
    #
    # Measured that day: of 62 rent modules and 71 capability-graph nodes, exactly SIX names
    # coincided. The ledger bills MECHANISMS; the graph names ORGANS. So 51 decision-affecting
    # organs were unpriceable BY CONSTRUCTION -- the MEASURED rung was unreachable for them however
    # long the desk ran, and that read in every report as "not enough evidence yet" rather than as
    # the wiring defect it was.
    #
    # These nine are added because each one's source string was CONFIRMED in the producers rather
    # than guessed: a grep for `source[:=]"<name>"` finds 5 sites for excursions, 8 for
    # regime_coverage, 5 for opportunity_curve, 3 for alpha_evolution, and 2 each for the rest, so
    # RESEARCH_PNL will key on exactly these names when the hypotheses land. The remaining organs
    # (alpha_genome, anomaly_factory, microstructure_miner, tail_alpha_search, transition_alpha,
    # style_premia_sweep, cross_asset_graph, weak_signal_compiler, survivor_distiller,
    # world_causal_graph, macro_intel, mutation_yield, factor_model_coevolution) stamp NO source
    # string, so a line here would name a row that never appears. That is worse than the honest
    # gap: it would make the node read `billable` while nothing could ever price it, which is the
    # measurement theatre this whole ledger exists to prevent. Their fix is a change to each
    # PRODUCER -- stamp a source -- and it is tracked as the remaining ratchet, not faked here.
    *(Module(name, "proposer", RESEARCH_PNL,
             "expected log-wealth per day carried in the funded book by certificates whose "
             "hypotheses this organ sourced, against the declared cost of running it; the "
             "allocator's own claim, never recomputed here",
             "measure_research_source", where, key=key, sources=(key,))
      for name, key, where in (
          ("excursions", "excursions", "desks/mt5/research/excursions.py"),
          ("exit_accounts", "exit_accounts", "desks/mt5/research/exit_accounts.py"),
          ("factor_residual_engine", "factor_residual",
           "desks/mt5/research/factor_residual_engine.py"),
          ("missed_growth", "missed_growth", "desks/mt5/research/missed_growth.py"),
          ("opportunity_curve", "opportunity_curve", "desks/mt5/research/opportunity_curve.py"),
          ("regime_coverage", "regime_coverage", "desks/mt5/research/regime_coverage.py"),
          ("revival_engine", "revival_engine", "desks/mt5/research/revival_engine.py"),
          ("plumbing_miner", "plumbing_miner", "desks/mt5/research/plumbing_miner.py"),
          ("alpha_evolution", "alpha_evolution", "desks/mt5/research/alpha_evolution.py"),
          # TWELVE MORE, FOUND BY READING THE SOURCE CONSTANT RATHER THAN GREPPING FOR A LITERAL.
          # The first pass looked for `source[:=]"<organ name>"` and missed every organ that
          # stamps its source through a module-level `SOURCE = "..."`, which is the more common
          # idiom here -- so twelve organs were filed as "stamps no source" when they stamp one on
          # every row they write. The lesson is the same one the dead-wire fence learned: a
          # vocabulary search finds the phrasing you thought of, and the thing you are looking for
          # is a CAPABILITY. Re-run as an AST-anchored regex over each node's declared module, it
          # is twelve for twelve.
          #
          # FOUR OF THEM BILL UNDER A NAME THAT IS NOT THE NODE'S, which is precisely why the
          # graph needed `billed_as`: microstructure_miner stamps "microstructure",
          # style_premia_sweep stamps "style_premia", tail_alpha_search stamps "tail_alpha", and
          # weak_signal_compiler stamps "weak_signal_ensemble". Keying these on the node name
          # would have produced four lines that never match a row -- billable in appearance,
          # unpriceable in fact.
          ("anomaly_factory", "anomaly_factory", "desks/mt5/research/anomaly_factory.py"),
          ("cross_asset_graph", "cross_asset_graph", "desks/mt5/research/cross_asset_graph.py"),
          ("factor_model_coevolution", "factor_model_coevolution",
           "desks/mt5/research/factor_model_coevolution.py"),
          ("fund_playbook", "fund_playbook", "desks/mt5/research/fund_playbook.py"),
          ("microstructure_miner", "microstructure",
           "desks/mt5/research/microstructure_miner.py"),
          ("mutation_yield", "mutation_yield", "desks/mt5/research/mutation_yield.py"),
          ("style_premia_sweep", "style_premia", "desks/mt5/research/style_premia_sweep.py"),
          ("survivor_distiller", "survivor_distiller",
           "desks/mt5/research/survivor_distiller.py"),
          ("tail_alpha_search", "tail_alpha", "desks/mt5/research/tail_alpha_search.py"),
          ("transition_alpha", "transition_alpha", "desks/mt5/research/transition_alpha.py"),
          ("weak_signal_compiler", "weak_signal_ensemble",
           "desks/mt5/research/weak_signal_compiler.py"),
          ("world_causal_graph", "world_causal_graph",
           "desks/mt5/research/world_causal_graph.py"),
      )),
    # THE EXECUTION-LEARNING LINES (2026-09-05, the principal's order). One billable quantity --
    # R per filled trade recovered from execution leakage -- and three claimants. The corpus
    # bills the leakage trend because it is what made leakage decomposable at all; the two models
    # bill nothing until they are MEASURED on their own power gate AND wired to something that
    # changes an order. Both currently read UNMEASURED WITH THE SHORTFALL, which is the rule
    # working: a model that cannot yet be fitted must not be billed for what a measurement bought.
    Module("data_source:fill_corpus", "data_source", CAPTURE_HISTORY,
           "leakage per fill in the FIRST half of the alpha-capture history minus the SECOND: "
           "E[R kept with the corpus] - E[R kept without it], where 'without' is genuinely "
           "nothing because leakage could not be decomposed before a joined fill record existed",
           "measure_execution_learning", "libs/execution/fill_corpus.py", key="fill_corpus"),
    Module("execution_choice_model", "execution_algo", ALPHA_CAPTURE,
           "R per fill saved by routing to the style the conditional surface names instead of "
           "the market baseline; unbillable until the surface is MEASURED on its own power gate "
           "and a consumer that changes an order is declared",
           "measure_execution_learning", "libs/execution/execution_choice_model.py",
           key="execution_choice_model"),
    Module("meta_labeler", "allocator_component", ALPHA_CAPTURE,
           "R per fill of the meta-sized book minus the 1x book on the same signals; unbillable "
           "until the labeler is MEASURED and wired. It can never re-admit a signal a gate "
           "refused, so its downside is bounded at SKIP and its upside is zero while UNMEASURED",
           "measure_execution_learning", "libs/execution/meta_label.py", key="meta_labeler"),
    Module("ai_capital_modifier", "ai_organ", MODIFIER_LEDGER,
           "the AI capital modifier's own conditioning ledger: heat its categories moved x what "
           "that heat earned, realised per day (the same rows as state_posterior, read as the "
           "modifier's rent; CAPITAL_MODIFIERS.json category verdicts beside)",
           "measure_conditioning", "libs/portfolio/capital_modifiers"),
    *(Module(organ, "ai_organ", RESEARCH_PNL,
             "expected log-wealth per day the organ's certificates carry in the funded book, "
             "trials and declared spend beside", "measure_research_source",
             f"desks/mt5/research/{organ}.py", key=organ, sources=prefixes)
      for organ, prefixes in AI_ORGANS.items()),
    # THE 27 DECISION-AFFECTING ORGANS THAT CARRIED NO RENT LINE AT ALL (2026-09-05). Measured on
    # the capability ladder that day: 71 nodes, 57 of them DECISION_AFFECTING, 1 MEASURED, 0
    # LIVE_LEARNING -- and 27 of the decision-affecting ones were not billable, meaning nothing
    # could ever retire them however long they cost. A component nothing bills is a component
    # nothing can retire, which is precisely how a desk accumulates organs that compute forever.
    #
    # They are billed THROUGH WHAT THEY CHANGE (see `measure_organ`), so this list adds no new
    # arithmetic to the desk -- only the chain from an organ to a priced decision, and a NAMED
    # verdict where that chain is not closed.
    *(Module(organ, "organ", "capability graph -> the consumer's own ledger",
             "rent of the decision this organ's output changes, inherited from the consumer that "
             "reads it; NOT_BINDING with the artifact named when nothing reads it at all",
             "measure_organ", f"writes {artifact}", key=artifact)
      for organ, artifact in ORGAN_OUTPUT.items()),
    *(Module(organ, "organ", "n/a -- the money path itself", why, "measure_organ",
             "libs.ops.module_rent.INFRASTRUCTURE", key=organ)
      for organ, why in INFRASTRUCTURE.items()),
)

#: Name -> Module, for `measure_organ`'s inheritance lookup. Built once from the registry rather
#: than passed around, because the chain is organ -> artifact -> consumer NAME and the consumer's
#: own line has to be found by that name.
MODULES_BY_NAME: dict[str, Module] = {m.name: m for m in MODULES}


# --------------------------------------------------------------------------- ledgers
class Ledgers:
    """Every ledger under one root, read once and lazily. A missing file reads as an empty
    document and the measure says so; nothing here invents a row."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self._json: dict[str, dict[str, Any]] = {}
        self._rows: dict[str, list[dict[str, Any]]] = {}
        self._realised: dict[tuple[str, str], float] | None = None

    def exists(self, rel: str) -> bool:
        return (self.root / rel).exists()

    def json(self, rel: str) -> dict[str, Any]:
        if rel not in self._json:
            try:
                doc = json.loads((self.root / rel).read_text("utf-8"))
            except (OSError, ValueError):
                doc = {}
            self._json[rel] = doc if isinstance(doc, dict) else {}
        return self._json[rel]

    def rows(self, rel: str) -> list[dict[str, Any]]:
        if rel not in self._rows:
            out: list[dict[str, Any]] = []
            try:
                for ln in (self.root / rel).read_text("utf-8").splitlines():
                    if not ln.strip():
                        continue
                    try:
                        r = json.loads(ln)
                    except ValueError:
                        continue
                    if isinstance(r, dict):
                        out.append(r)
            except OSError:
                pass
            self._rows[rel] = out
        return self._rows[rel]

    def realised(self) -> dict[tuple[str, str], float]:
        """Realised R per (sleeve, day): live fills first, forward-phase shadow rows beside.

        Both are read because the conditioning ledger is written for whichever book the
        allocator funded, and off-box the only realised evidence is shadow. A row is attributed
        to the day its trade was ENTERED (shadow) or CLOSED (live) -- the ledger's own keys.
        """
        if self._realised is not None:
            return self._realised
        out: dict[tuple[str, str], float] = defaultdict(float)
        for r in self.rows(LIVE_LEDGER):
            day = str(r.get("close_time") or r.get("time") or "")[:10]
            v = _num(r.get("r_multiple"))
            if r.get("sleeve") and day and v is not None:
                out[(str(r["sleeve"]), day)] += v
        shadow = self.root / SHADOW_DIR
        if shadow.is_dir():
            for f in sorted(shadow.glob("ledger_*.json")):
                try:
                    rows = json.loads(f.read_text("utf-8"))
                except (OSError, ValueError):
                    continue
                if not isinstance(rows, list):
                    continue
                name = f.stem.removeprefix("ledger_")
                for row in rows:
                    if not isinstance(row, dict) or str(row.get("phase") or "") != "forward":
                        continue
                    day = str(row.get("entry_time") or "")[:10]
                    v = _num(row.get("r_multiple"))
                    if day and v is not None:
                        out[(name, day)] += v
        self._realised = dict(out)
        return self._realised


def _num(v: Any) -> float | None:
    if isinstance(v, bool) or v is None:
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return f if math.isfinite(f) else None


def _row(m: Module, verdict: str, *, rent: float | None = None, unit: str = "log-wealth/day",
         n: int = 0, ci: list[float] | None = None, window: str = "", why: str = "",
         **extra: Any) -> dict[str, Any]:
    logw = rent if unit == "log-wealth/day" else None
    return {"kind": m.kind, "ledger": m.ledger, "rule": m.rule, "where": m.where,
            "rent_logw_per_day": (round(logw, 10) if logw is not None else None),
            "rent": (round(rent, 10) if rent is not None else None), "unit": unit,
            "n": int(n), "ci": ci, "verdict": verdict, "window": window, "why": why, **extra}


def verdict_from_samples(samples: list[float]) -> tuple[str, dict[str, Any]]:
    """Daily with/without samples -> a sign the desk can act on, or an honest refusal.

    Same line as missed_growth (t = mean / se against T_LINE) so a rail read here and a rail
    read there cannot disagree; the CI is reported so a reader can see how far from the line
    the evidence sits rather than just which side.
    """
    n = len(samples)
    if n < MIN_N:
        return UNMEASURED, {"n": n, "why": f"{n} daily sample(s), need {MIN_N}"}
    if all(abs(x) < 1e-15 for x in samples):
        return NOT_BINDING, {"n": n, "rent": 0.0, "why": "every sample is zero: did not bind"}
    mean = statistics.fmean(samples)
    sd = statistics.stdev(samples) if n > 1 else 0.0
    se = sd / math.sqrt(n)
    t = (mean / se) if se > 0 else (math.inf if mean > 0 else -math.inf)
    ci = [mean - 1.96 * se, mean + 1.96 * se]
    v = EARNS if t > T_LINE else (COSTS if t < -T_LINE else UNMEASURED)
    why = ("" if v != UNMEASURED else
           f"|t| = {abs(t):.2f} < {T_LINE}: the sign is not distinguishable from zero on {n} days")
    return v, {"n": n, "rent": mean, "t": round(t, 3) if math.isfinite(t) else None,
               "ci": [round(ci[0], 10), round(ci[1], 10)], "why": why}


def _sign_verdict(value: float | None, n: int, *, min_n: int = MIN_N) -> tuple[str, str]:
    """For ledgers that carry one number rather than samples: the sign, once n clears the bar."""
    if value is None:
        return UNMEASURED, "no number on the ledger"
    if n < min_n:
        return UNMEASURED, f"n = {n} < {min_n}"
    if value > 0:
        return EARNS, ""
    if value < 0:
        return COSTS, ""
    return NOT_BINDING, "exactly zero"


# --------------------------------------------------------------------------- measures
def measure_rail(m: Module, led: Ledgers) -> dict[str, Any]:
    doc = led.json(MISSED_GROWTH)
    if not doc:
        return _row(m, UNMEASURED, why=f"{MISSED_GROWTH} absent on this host")
    rail = (doc.get("rails") or {}).get(m.key)
    if not isinstance(rail, dict):
        return _row(m, UNMEASURED, why=f"rail {m.key} not on {MISSED_GROWTH}")
    v_raw = str(rail.get("verdict") or UNMEASURED)
    verdict = {"EARNS_ITS_PLACE": EARNS, "COSTS_GROWTH": COSTS, "NOT_BINDING": NOT_BINDING,
               "SAMPLE": UNMEASURED}.get(v_raw, UNMEASURED)
    n = int(_num(rail.get("n")) or 0)
    rent = _num(rail.get("mean_logw_per_day"))
    unit = "log-wealth/day"
    if rent is None:
        rent = _num(rail.get("value_logw_per_day"))
    if rent is None and _num(rail.get("value_logw_per_veto")) is not None:
        rent, unit = _num(rail.get("value_logw_per_veto")), "log-wealth/veto"
    t = _num(rail.get("t"))
    ci = None
    if rent is not None and t not in (None, 0.0) and n > 1 and t is not None:
        se = abs(rent / t)
        ci = [round(rent - 1.96 * se, 10), round(rent + 1.96 * se, 10)]
    return _row(m, verdict, rent=rent, unit=unit, n=n, ci=ci,
                window=f"{n} daily sample(s) on missed_growth's ledger",
                why=str(rail.get("why") or ""), missed_growth_verdict=v_raw,
                rail_kind=rail.get("kind"))


def _pnl_sources(led: Ledgers, prefixes: tuple[str, ...]) -> dict[str, Any] | None:
    """Roll every RESEARCH_PNL source row whose name starts with one of `prefixes` into one
    module. Prefix matching, not equality, because the world forest splits one organ across a
    source per region cluster and the organ is the thing being billed."""
    doc = led.json(RESEARCH_PNL)
    if not doc:
        return None
    growth, cost = 0.0, 0.0
    trials, certified = 0, 0
    names: list[str] = []
    for src, c in (doc.get("sources") or {}).items():
        if not isinstance(c, dict) or not any(str(src).startswith(p) for p in prefixes):
            continue
        growth += _num(c.get("growth_per_day")) or 0.0
        trials += int(_num(c.get("trials")) or 0)
        certified += int(_num(c.get("certified")) or 0)
        cost += _num(c.get("cost_units")) or 0.0
        names.append(str(src))
    return {"growth_per_day": growth, "trials": trials, "certified": certified,
            "cost_units": cost, "sources": names}


def _pnl_row(m: Module, led: Ledgers, agg: dict[str, Any] | None, basis: str) -> dict[str, Any]:
    if agg is None:
        return _row(m, UNMEASURED, why=f"{RESEARCH_PNL} absent on this host")
    trials, growth = int(agg["trials"]), float(agg["growth_per_day"])
    if trials == 0 and growth == 0.0:
        return _row(m, NOT_BINDING, rent=0.0, n=0, window="whole research history",
                    why=f"no trials and no funded certificate from {basis}",
                    spend_cost_units=0.0, certified=0, sources=agg.get("sources", []))
    verdict, why = _sign_verdict(growth, trials)
    if verdict == COSTS or (growth <= 0.0 and trials >= MIN_N):
        verdict, why = COSTS, (f"{trials} trial(s) and the funded book carries no growth from "
                               f"{basis}: dead information on this ledger")
    return _row(m, verdict, rent=growth, n=trials, window="whole research history",
                why=why, spend_cost_units=round(float(agg["cost_units"]), 2),
                certified=int(agg["certified"]),
                roi_growth_per_cost_unit=(round(growth / float(agg["cost_units"]), 12)
                                          if agg["cost_units"] else None),
                sources=agg.get("sources", []),
                note="growth is the allocator's EXPECTED log-wealth per day for the funded "
                     "certificates, not realised; spend is in the bandit's declared cost units")


def measure_proposer(m: Module, led: Ledgers) -> dict[str, Any]:
    doc = led.json(RESEARCH_PNL)
    if not doc:
        return _row(m, UNMEASURED, why=f"{RESEARCH_PNL} absent on this host")
    arm = (doc.get("arms") or {}).get(m.key)
    if not isinstance(arm, dict):
        return _row(m, UNMEASURED, why=f"arm {m.key} not on {RESEARCH_PNL}")
    agg = {"growth_per_day": float(_num(arm.get("growth_per_day")) or 0.0),
           "trials": int(_num(arm.get("trials")) or 0),
           "certified": int(_num(arm.get("certified")) or 0),
           "cost_units": float(_num(arm.get("cost_units")) or 0.0),
           "sources": list(arm.get("sources") or [])}
    return _pnl_row(m, led, agg, f"arm {m.key}")


def measure_research_source(m: Module, led: Ledgers) -> dict[str, Any]:
    return _pnl_row(m, led, _pnl_sources(led, m.sources or (m.key,)), f"source(s) {m.sources}")


def conditioning_samples(led: Ledgers) -> tuple[list[float], dict[str, Any]]:
    """Per day: sum over ledger rows of h x (1 - 1/mult) x realised R -- the growth the modifier's
    heat move earned or lost against the un-modified book. Linearised: heat proportional to the
    posterior mean, so 'without' heat is h / mult, floored at MULT_FLOOR for vetoes."""
    rows = led.rows(MODIFIER_LEDGER)
    if not rows:
        return [], {"why": f"{MODIFIER_LEDGER} absent or empty on this host", "ledger_rows": 0}
    realised = led.realised()
    by_day: dict[str, float] = defaultdict(float)
    joined = 0
    for r in rows:
        day = str(r.get("t") or "")[:10]
        h, mult = _num(r.get("heat")), _num(r.get("multiplier"))
        key = (str(r.get("sleeve")), day)
        if h is None or mult is None or key not in realised:
            continue
        joined += 1
        by_day[day] += h * (1.0 - 1.0 / max(mult, MULT_FLOOR)) * realised[key]
    return [by_day[d] for d in sorted(by_day)], {"ledger_rows": len(rows), "joined_rows": joined,
                                                 "why": ("" if joined else
                                                         "no ledger row joins a realised R")}


def measure_conditioning(m: Module, led: Ledgers) -> dict[str, Any]:
    samples, meta = conditioning_samples(led)
    cats = (led.json(CAPITAL_MODIFIERS).get("categories") or {})
    extra = {"categories": {c: v.get("verdict") for c, v in cats.items() if isinstance(v, dict)},
             **{k: v for k, v in meta.items() if k != "why"}}
    if not samples:
        return _row(m, UNMEASURED, why=str(meta.get("why") or "no samples"), **extra)
    v, st = verdict_from_samples(samples)
    return _row(m, v, rent=st.get("rent"), n=int(st["n"]), ci=st.get("ci"),
                window=f"{len(samples)} ledger day(s)", why=str(st.get("why") or ""),
                t=st.get("t"), **extra)


def measure_admission(m: Module, led: Ledgers) -> dict[str, Any]:
    adm = led.json(STATE_ADMISSION)
    if not adm:
        return _row(m, UNMEASURED, unit="oos_mse_gain",
                    why=f"{STATE_ADMISSION} absent on this host")
    gap = (adm.get("gaps") or {}).get(m.key)
    row = (adm.get("verdicts") or {}).get(m.key)
    if not isinstance(row, dict):
        return _row(m, UNMEASURED, unit="oos_mse_gain",
                    why=str(gap or f"dimension {m.key} not judged on {STATE_ADMISSION}"))
    v_raw = str(row.get("verdict") or "")
    gain, t = _num(row.get("mse_gain")), _num(row.get("t_deflated", row.get("t_paired")))
    n = int(_num(row.get("n_test")) or 0)
    if v_raw == "GRAVEYARD" or (t is not None and t < -T_LINE and n >= MIN_N):
        verdict, why = COSTS, "measurably worse out of sample: conditioning on it adds noise"
    elif v_raw.startswith("ADMIT") or (t is not None and t > T_LINE and n >= MIN_N):
        verdict, why = EARNS, "improved out-of-sample prediction of unseen trades"
    elif v_raw == "UNJUDGED":
        verdict, why = UNMEASURED, str(row.get("why") or "unjudged")
    else:
        verdict, why = UNMEASURED, (f"{v_raw}: {row.get('why') or 'kept by shrinkage only'}"
                                    if v_raw else "no verdict")
    joint, _ = conditioning_samples(led)
    return _row(m, verdict, rent=gain, unit="oos_mse_gain", n=n, window=f"{n} test trade(s)",
                why=why, t=t, admission_verdict=v_raw, dimension=m.key,
                conditioning_logw_per_day=(round(statistics.fmean(joint), 10) if joint else None),
                conditioning_days=len(joint))


def _scoreboard(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """`execution_registry.scoreboard(rows=...)` when the desk is importable, else the same
    aggregation in place -- the numbers must not depend on which host runs this."""
    desk = ROOT / "desks" / "mt5"
    if str(desk) not in sys.path:
        sys.path.insert(0, str(desk))
    try:
        from mt5desk.execution_registry import scoreboard
        out = scoreboard(rows=rows)
        return dict(out) if isinstance(out, dict) else {}
    except Exception:
        pass
    by: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for r in rows:
        if r.get("algo"):
            by[str(r["algo"])].append(r)
    algos: dict[str, Any] = {}
    for algo, rs in sorted(by.items()):
        real = [float(r["realised_cost"]) for r in rs if r.get("realised_cost") is not None]
        algos[algo] = {"n": len(rs), "n_filled": len(real),
                       "mean_realised_cost": (statistics.fmean(real) if real else None),
                       "mean_filled_frac": statistics.fmean(
                           float(r.get("filled_frac") or 0.0) for r in rs)}
    return {"n": len(rows), "algos": algos}


def measure_execution_algo(m: Module, led: Ledgers) -> dict[str, Any]:
    rows = led.rows(ALGO_OUTCOMES)
    if not rows:
        return _row(m, UNMEASURED, unit="price_frac/fill",
                    why=f"{ALGO_OUTCOMES} absent or empty on this host")
    board = _scoreboard(rows).get("algos") or {}
    mine, base = board.get(m.key), board.get(BASELINE_ALGO)
    if m.key == BASELINE_ALGO:
        return _row(m, NOT_BINDING, rent=0.0, unit="price_frac/fill",
                    n=int((mine or {}).get("n_filled") or 0),
                    why="the market algorithm IS the baseline every other one is measured "
                        "against; its rent against itself is zero by definition")
    if not mine:
        return _row(m, NOT_BINDING, rent=0.0, unit="price_frac/fill", n=0,
                    why=f"{m.key} executed no plan in the ledger")
    if not base or base.get("mean_realised_cost") is None:
        return _row(m, UNMEASURED, unit="price_frac/fill", n=int(mine.get("n_filled") or 0),
                    why="no filled market-baseline plan to measure against")

    def costs(algo: str) -> list[float]:
        return [float(r["realised_cost"]) for r in rows
                if r.get("algo") == algo and r.get("realised_cost") is not None]

    a, b = costs(m.key), costs(BASELINE_ALGO)
    n = len(a)
    if n < MIN_N or len(b) < MIN_N:
        return _row(m, UNMEASURED, unit="price_frac/fill", n=n,
                    why=f"{n} filled plan(s) against {len(b)} baseline fill(s); need {MIN_N} each")
    ff_mine, ff_base = float(mine.get("mean_filled_frac") or 0.0), float(
        base.get("mean_filled_frac") or 0.0)
    if ff_mine < ff_base - 0.2:
        return _row(m, UNMEASURED, unit="price_frac/fill", n=n,
                    why=(f"fills {ff_mine:.0%} of its lots against the baseline's {ff_base:.0%}: "
                         "a cost advantage on the subset that filled is not comparable"),
                    mean_filled_frac=ff_mine, baseline_filled_frac=ff_base)
    rent = statistics.fmean(b) - statistics.fmean(a)
    se = math.sqrt(statistics.variance(a) / n + statistics.variance(b) / len(b))
    t = rent / se if se > 0 else (math.inf if rent > 0 else (-math.inf if rent < 0 else 0.0))
    verdict = EARNS if t > T_LINE else (COSTS if t < -T_LINE else UNMEASURED)
    ci = [round(rent - 1.96 * se, 12), round(rent + 1.96 * se, 12)]
    return _row(m, verdict, rent=rent, unit="price_frac/fill", n=n, ci=ci,
                window=f"{n} filled plan(s) vs {len(b)} baseline fill(s)",
                why=("" if verdict != UNMEASURED else f"|t| = {abs(t):.2f} < {T_LINE}"),
                t=(round(t, 3) if math.isfinite(t) else None),
                mean_realised_cost=round(statistics.fmean(a), 10),
                baseline_mean_realised_cost=round(statistics.fmean(b), 10),
                mean_filled_frac=ff_mine, baseline_filled_frac=ff_base)


def measure_execution_learning(m: Module, led: Ledgers) -> dict[str, Any]:
    """Rent for the fill corpus and the two models built on it. Unit: R per filled trade.

    ONE BILLABLE QUANTITY, THREE CLAIMANTS. All three exist to recover execution leakage -- the
    gap between the predicted frictionless edge and the realised one -- so all three bill on the
    SAME number: the R per fill the desk stopped losing, measured FORWARD across the alpha
    capture ledger's own history. `with` is the second half of that history, `without` the first.

    THE CORPUS BILLS FIRST BECAUSE IT IS WHAT MAKES THE OTHERS MEASURABLE AT ALL. Its "without"
    is genuinely nothing: before a joined fill record existed, leakage could not be decomposed
    into spread, slippage, commission and residual, so no execution decision could be aimed. The
    two MODELS bill only once they are (a) MEASURED on their own power gate and (b) declared as
    the consumer of an order-changing decision. Until both hold, this returns UNMEASURED WITH THE
    SHORTFALL -- which is the module working, not a gap. Attributing the corpus's leakage
    improvement to an unwired model would be billing a model for what a measurement bought.

    THIS IS DELIBERATELY AN UNCOMFORTABLE LINE for an asset whose whole argument is that it
    cannot be re-acquired later. "Unbuyable" is a reason to start capture TODAY, not a licence to
    skip the billing: if the corpus's leakage line does not improve after a fair window, the
    right response is to stop building models on it, not to keep paying because the rows felt
    precious.
    """
    cap = led.json(ALPHA_CAPTURE)
    hist = led.rows(CAPTURE_HISTORY)
    twin = led.json(EXECUTION_TWIN)
    n_exec = int(_num((cap.get("corpus") or {}).get("unique_executions")) or 0)
    if m.key in ("execution_choice_model", "meta_labeler"):
        block = (twin.get("execution_choice") if m.key == "execution_choice_model"
                 else twin.get("meta_label")) or {}
        status = str(block.get("status") or UNMEASURED)
        raw_power = block.get("power")
        power: dict[str, Any] = raw_power if isinstance(raw_power, dict) else {}
        raw_gate = power.get("gate")
        gate: dict[str, Any] = raw_gate if isinstance(raw_gate, dict) else power
        short = _num(gate.get("shortfall_per_arm"))
        need = _num(gate.get("n_required_per_arm")) or _num(
            power.get("n_required_per_bucket"))
        return _row(m, UNMEASURED, unit="R/fill", n=n_exec,
                    why=(f"{m.key} is {status} and wired to nothing that sends an order; it "
                         "cannot bill a leakage improvement a measurement bought. "
                         f"corpus holds {n_exec} execution(s)"
                         + (f"; needs {need:.0f} per arm" if need else "")
                         + (f", short {short:.0f}" if short else "")),
                    model_status=status,
                    n_required_per_arm=(int(need) if need else None),
                    shortfall_per_arm=(int(short) if short else None))
    leaks = [v for v in (_num(r.get("leakage_r")) for r in hist) if v is not None]
    if len(leaks) < 2 * MIN_N:
        return _row(m, UNMEASURED, unit="R/fill", n=n_exec,
                    why=(f"{len(leaks)} alpha-capture point(s) on {CAPTURE_HISTORY}; a forward "
                         f"with/without split needs {2 * MIN_N}. The corpus holds {n_exec} "
                         "execution(s); a point is only written when the capture ratio is "
                         "MEASURED, so this reads UNMEASURED until the desk has fills"),
                    capture_points=len(leaks))
    half = len(leaks) // 2
    before, after = leaks[:half], leaks[half:]
    rent = statistics.fmean(before) - statistics.fmean(after)   # leakage FELL => positive rent
    se = math.sqrt(statistics.variance(before) / len(before)
                   + statistics.variance(after) / len(after))
    t = rent / se if se > 0 else (math.inf if rent > 0 else (-math.inf if rent < 0 else 0.0))
    verdict = EARNS if t > T_LINE else (COSTS if t < -T_LINE else UNMEASURED)
    return _row(m, verdict, rent=rent, unit="R/fill", n=n_exec,
                ci=[round(rent - 1.96 * se, 12), round(rent + 1.96 * se, 12)],
                window=f"{len(before)} point(s) before vs {len(after)} after",
                why=("" if verdict != UNMEASURED else f"|t| = {abs(t):.2f} < {T_LINE}"),
                t=(round(t, 3) if math.isfinite(t) else None), capture_points=len(leaks))


def _breach_days(rows: list[dict[str, Any]]) -> tuple[dict[str, bool], int]:
    """day -> did any watched artifact breach, from the fence's own history rows.

    A row is `{day, breaches: [artifact, ...]}` (or `{day, artifact, status}`); only the
    artifacts this module watches count, and only the fence's breach statuses. The LAST word
    about a day stands, so a re-run of the fence on the same day supersedes rather than
    accumulates. Returns (flags, rows the module could read).
    """
    flags: dict[str, bool] = {}
    used = 0
    for r in rows:
        day = str(r.get("day") or r.get("at") or "")[:10]
        if not day:
            continue
        listed = r.get("breaches")
        if isinstance(listed, list):
            hit = any(str(x) in FRESHNESS_ARTIFACTS for x in listed)
        elif r.get("artifact") is not None:
            hit = (str(r.get("artifact")) in FRESHNESS_ARTIFACTS
                   and str(r.get("status") or "") in BREACH_STATUSES)
        else:
            continue
        used += 1
        flags[day] = bool(flags.get(day)) or hit
    return flags, used


def measure_freshness(m: Module, led: Ledgers) -> dict[str, Any]:
    """What tape/bar freshness is worth in log-wealth per day, on the fence's own breaches.

    UNMEASURED IS THE EXPECTED READING TODAY AND IS NOT A GAP. `check_job_manifest` publishes a
    SNAPSHOT of which artifacts are breaching right now; the day-keyed history this needs is its
    append-only companion, and until it holds both a breached day and a clean day with realised
    trades on them there is no with/without to take. The snapshot is still reported -- which
    artifacts are red at this moment, out of the four watched -- so the row says what it knows
    rather than only what it cannot say.
    """
    state = led.json(JOB_MANIFEST)
    jobs = state.get("jobs") if isinstance(state.get("jobs"), dict) else {}
    watched = {rel: row for rel, row in (jobs or {}).items() if rel in FRESHNESS_ARTIFACTS}
    breaching = sorted(rel for rel, row in watched.items()
                       if isinstance(row, dict) and str(row.get("status") or "") in
                       BREACH_STATUSES)
    snapshot: dict[str, Any] = {
        "watched": list(FRESHNESS_ARTIFACTS), "on_manifest": sorted(watched),
        "breaching_now": breaching,
        "manifest_checked_at": str(state.get("checked_at") or "") or None}
    if not state:
        return _row(m, UNMEASURED, why=f"{JOB_MANIFEST} absent on this host: the freshness fence "
                                       f"has not run here, so no breach is counted", **snapshot)
    flags, used = _breach_days(led.rows(FRESHNESS_HISTORY))
    if not flags:
        return _row(m, UNMEASURED, n=0,
                    why=(f"{FRESHNESS_HISTORY} holds no readable day for the watched artifacts "
                         f"({used} row(s) parsed): the fence publishes a snapshot, and a "
                         f"with/without split needs a day-keyed history. "
                         f"{len(breaching)} of {len(FRESHNESS_ARTIFACTS)} artifact(s) breaching "
                         f"at the last check"), **snapshot)
    realised = led.realised()
    by_day: dict[str, float] = defaultdict(float)
    for (_sleeve, day), v in realised.items():
        by_day[day] += v
    clean = [v for d, v in by_day.items() if d in flags and not flags[d]]
    dirty = [v for d, v in by_day.items() if flags.get(d)]
    joined = len(clean) + len(dirty)
    if len(clean) < MIN_N or len(dirty) < MIN_N:
        return _row(m, UNMEASURED, n=joined,
                    why=(f"{len(clean)} clean day(s) and {len(dirty)} breached day(s) join a "
                         f"realised R; need {MIN_N} of each. {len(flags)} day(s) in "
                         f"{FRESHNESS_HISTORY}, {len(by_day)} realised day(s)"),
                    clean_days=len(clean), breached_days=len(dirty), **snapshot)
    rent = statistics.fmean(clean) - statistics.fmean(dirty)
    se = math.sqrt(statistics.variance(clean) / len(clean)
                   + statistics.variance(dirty) / len(dirty))
    t = rent / se if se > 0 else (math.inf if rent > 0 else (-math.inf if rent < 0 else 0.0))
    verdict = EARNS if t > T_LINE else (COSTS if t < -T_LINE else UNMEASURED)
    return _row(m, verdict, rent=rent, n=joined,
                ci=[round(rent - 1.96 * se, 12), round(rent + 1.96 * se, 12)],
                window=f"{len(clean)} clean day(s) vs {len(dirty)} breached day(s)",
                why=("" if verdict != UNMEASURED else f"|t| = {abs(t):.2f} < {T_LINE}"),
                t=(round(t, 3) if math.isfinite(t) else None),
                clean_days=len(clean), breached_days=len(dirty),
                mean_clean_r=round(statistics.fmean(clean), 10),
                mean_breached_r=round(statistics.fmean(dirty), 10), **snapshot)


def measure_dynamic_weights(m: Module, led: Ledgers) -> dict[str, Any]:
    alloc = led.json(ALLOCATION)
    if not alloc:
        return _row(m, UNMEASURED, why=f"{ALLOCATION} absent: no allocator pass on this host")
    proof = alloc.get("proof") or {}
    scores = proof.get("scores") or {}
    dyn = _num(scores.get("dynamic"))
    best_name = str(proof.get("best_baseline") or "")
    best = _num(scores.get(best_name)) if best_name else None
    if dyn is None or best is None:
        return _row(m, UNMEASURED, why="proof scores (dynamic, best_baseline) not on the artifact")
    n = int(_num((alloc.get("evidence") or {}).get("worlds")) or 0)
    rent = dyn - best
    verdict = (EARNS if proof.get("passed") else
               (COSTS if rent < 0 else UNMEASURED))
    return _row(m, verdict, rent=rent, n=n, window=f"{n} sampled world(s), one pass",
                why=("" if proof.get("passed") else str(proof.get("why") or "")),
                best_baseline=best_name, proof_passed=bool(proof.get("passed")))


def measure_posterior_growth(m: Module, led: Ledgers) -> dict[str, Any]:
    alloc = led.json(ALLOCATION)
    if not alloc:
        return _row(m, UNMEASURED, why=f"{ALLOCATION} absent: no allocator pass on this host")
    cmp_ = (alloc.get("posterior_growth") or {}).get("vs_funded") or {}
    delta = _num(cmp_.get("delta_elogw_per_day"))
    if delta is None:
        return _row(m, UNMEASURED, why="no posterior_growth.vs_funded on the artifact")
    lo, hi = _num(cmp_.get("ci_lo")), _num(cmp_.get("ci_hi"))
    ci = [lo, hi] if lo is not None and hi is not None else None
    verdict = (EARNS if cmp_.get("beats") else
               (COSTS if hi is not None and hi < 0 else UNMEASURED))
    return _row(m, verdict, rent=delta, n=int(_num(cmp_.get("n_paths")) or 0) or MIN_N, ci=ci,
                window="one pass, bootstrap over sampled paths",
                why=("" if verdict != UNMEASURED else "the CI straddles zero"),
                adopted=bool((alloc.get("posterior_growth") or {}).get("adopted")))


def measure_kelly_surface(m: Module, led: Ledgers) -> dict[str, Any]:
    alloc = led.json(ALLOCATION)
    if not alloc:
        return _row(m, UNMEASURED, why=f"{ALLOCATION} absent: no allocator pass on this host")
    ks = alloc.get("kelly_surface") or {}
    rows = ks.get("rows") or []
    f_tail = _num(ks.get("f_tail"))
    if f_tail is None or not rows:
        return _row(m, UNMEASURED, why="no kelly_surface rows on the artifact")
    if f_tail >= 1.0 - 1e-9:
        return _row(m, NOT_BINDING, rent=0.0, window="one pass",
                    why="the tail bound sits at or above the book's own fraction")
    growth = {float(r["f"]): _num(r.get("mean_growth")) for r in rows
              if isinstance(r, dict) and _num(r.get("f")) is not None}
    g_tail, g_book = growth.get(f_tail), growth.get(1.0)
    if g_tail is None or g_book is None:
        return _row(m, UNMEASURED, why="surface rows do not cover f_tail and f = 1")
    rent = g_tail - g_book
    verdict = EARNS if rent > 0 else (COSTS if rent < 0 else NOT_BINDING)
    return _row(m, verdict, rent=rent, n=MIN_N, window="one pass over the sampled worlds",
                why="", f_tail=f_tail,
                note="binding this pass: the bound's growth against the unbounded book; a "
                     "negative number is growth the tail bound declined and must be weighed "
                     "against the ruin it refused")


def measure_marginal_admission(m: Module, led: Ledgers) -> dict[str, Any]:
    """What the dE[log W] admission criterion is worth: the growth its admitted set adds.

    THE UNIT IS THE OBJECTIVE ITSELF, which is the whole reason this criterion replaced a Sharpe
    ranking: each admitted candidate's rent IS `E[logW | book + i] - E[logW | book]`, measured on
    one world population at one total heat. A scan that admits nothing is NOT_BINDING (it changed
    no allocation and cost no growth), not a failure -- a book that already holds everything worth
    holding is the criterion working.
    """
    alloc = led.json(ALLOCATION)
    if not alloc:
        return _row(m, UNMEASURED, why=f"{ALLOCATION} absent: no allocator pass on this host")
    adm = alloc.get("admission") or {}
    if str(adm.get("status") or "") != "MEASURED":
        return _row(m, UNMEASURED,
                    why=f"no measured admission scan on the artifact (status "
                        f"{adm.get('status', 'ABSENT')!r})")
    rent = _num((adm.get("rent") or {}).get("sum_admitted_delta_elogw_per_day"))
    n_scored = int(_num(adm.get("n_scored")) or 0)
    n_admitted = int(_num(adm.get("n_admitted")) or 0)
    if rent is None:
        return _row(m, UNMEASURED, why="the scan carries no rent line")
    if not n_admitted:
        return _row(m, NOT_BINDING, rent=0.0, n=n_scored,
                    window=f"one pass, {n_scored} candidate(s) scored",
                    why="the criterion admitted nothing this pass: it changed no allocation")
    verdict = EARNS if rent > 0 else (COSTS if rent < 0 else NOT_BINDING)
    return _row(m, verdict, rent=rent, n=max(n_scored, MIN_N),
                window=f"one pass, {n_admitted}/{n_scored} candidate(s) admitted",
                why="", n_admitted=n_admitted, n_scored=n_scored,
                unscored=len(adm.get("unscored") or {}), basis=str(adm.get("basis") or ""),
                note=("a sum of separately-measured marginals against the same held book; the "
                      "joint delta of admitting all of them at once is smaller"))


def measure_hunt12_survivors(m: Module, led: Ledgers) -> dict[str, Any]:
    """What the hypothesis-lane sweep is worth to the book it feeds.

    IT IS DECISION-AFFECTING BY A ROUTE THAT IS EASY TO MISS. `pf_allocator` assembles its evidence
    through `portfolio_projection`, which REFUSES outright without `reports/hunt12_partial.json`
    -- so this sweep is not a research report, it is the allocator's first input, and an absent
    one is the growth sizer declining to solve at all. Measured 2026-09-10, `pf_allocation.json`
    had never existed for exactly this reason.

    THE RENT IS THEREFORE THE BOOK'S, NOT THE SWEEP'S OWN STATISTICS. A survivor count says
    nothing about growth; what this component is worth is E[log W] of the solved book WITH the
    hunt12 survivors against the same book WITHOUT them, on one world population at one total
    heat -- the same shape `measure_marginal_admission` uses. Nothing computes that pair yet, so
    this reports the gap precisely rather than dressing a count as a rent (L1.28a).
    """
    alloc = led.json(ALLOCATION)
    if not alloc:
        return _row(m, UNMEASURED, why=f"{ALLOCATION} absent: no allocator pass on this host")
    _book = alloc.get("book")
    book: dict[str, Any] = _book if isinstance(_book, dict) else {}
    return _row(m, UNMEASURED, n=len(book),
                why=("the allocator solved a book this pass, and the artifact carries no score of "
                     "the same book with the hunt12 survivors withheld; needs a second solve at "
                     "the same heat on the same sampled worlds, as marginal_admission does"))


def measure_regime_conditioning(m: Module, led: Ledgers) -> dict[str, Any]:
    alloc = led.json(ALLOCATION)
    if not alloc:
        return _row(m, UNMEASURED, why=f"{ALLOCATION} absent: no allocator pass on this host")
    reg = alloc.get("regime") or {}
    if not reg.get("conditioned"):
        return _row(m, NOT_BINDING, rent=0.0, why="regime conditioning INACTIVE this pass")
    return _row(m, UNMEASURED, why=("conditioned, but the artifact carries no score of the "
                                    "same book on unconditioned worlds; needs "
                                    "growth.mean_log_per_day_unconditioned beside "
                                    "growth.mean_log_per_day"))


def _graph_consumers(artifact: str) -> tuple[list[str], str, str]:
    """(node readers, external reader, terminal state) for `artifact`, from the capability graph.

    THE GRAPH KNOWS THREE WAYS AN ARTIFACT IS CONSUMED and this reads all three, because reading
    only the first gets the answer confidently wrong:

      NODES[].reads     a graph node consumes it -- the chain continues to that node's rent
      EXTERNAL_READERS  a consumer that is not a graph node (`research_supervisor` is a process
                        manager, not a node), declared with its reason. Missing this reported
                        `macro_intel` as reading NOT_BINDING when its interrupt is in fact the one
                        artifact of that whole layer which reaches a decision.
      HUMAN_READ        advisory BY DESIGN: a person reads it and no automated decision turns on
                        it. That is a legitimate terminal state the desk has already reasoned
                        about, not an unwired defect, and calling it one would put correct
                        designs on a retire list.

    Imported LAZILY: `capability_graph` reads this module's registry to decide what is billable,
    so a module-level import here is a cycle. Prefix matching runs both ways -- the graph's own
    convention, since a node may declare a directory where the writer names a file inside it.
    """
    try:
        from libs.ops.capability_graph import EXTERNAL_READERS, HUMAN_READ, NODES
    except Exception:
        return [], "", ""
    nodes = sorted(n.name for n in NODES
                   if any(r.startswith(artifact) or artifact.startswith(r) for r in n.reads))
    external = ""
    for path, who in EXTERNAL_READERS.items():
        if path.startswith(artifact) or artifact.startswith(path):
            external = str(who)
            break
    human = "HUMAN_READ" if any(h.startswith(artifact) or artifact.startswith(h)
                                for h in HUMAN_READ) else ""
    return nodes, external, human


def measure_organ(m: Module, led: Ledgers, _chain: tuple[str, ...] = ()) -> dict[str, Any]:
    """An organ's rent, inherited from whatever its output actually changes.

    `_chain` carries the organs already visited on this inheritance walk. The desk's artifact
    graph has genuine cycles -- `miner_candidate_compiler` writes the candidates the gauntlet
    reads and reads the gate report the gauntlet writes -- so a walk without it recurses until
    the stack ends. A cycle is not an error either: it is a research LOOP, and the honest verdict
    names it rather than crashing on it or silently picking one arbitrary direction.
    """
    if m.name in INFRASTRUCTURE:
        return _row(m, NOT_BINDING, rent=0.0, unit="log-wealth/day",
                    why=f"MONEY PATH, not an input to it -- {INFRASTRUCTURE[m.name]}",
                    infrastructure=True)
    artifact = ORGAN_OUTPUT.get(m.name, m.key)
    nodes, external, human = _graph_consumers(artifact)
    readers = [r for r in nodes if r != m.name]
    if human and not readers and not external:
        return _row(m, NOT_BINDING, rent=0.0,
                    why=(f"{artifact} is declared HUMAN_READ: advisory by design, a person reads "
                         f"it and no automated decision turns on it. Rent is zero because it "
                         f"changes no sizing -- that is the intended terminal state here, NOT an "
                         f"unwired organ, and it becomes billable the day a consumer is declared"),
                    artifact=artifact, readers=[], terminal="HUMAN_READ")
    if external and not readers:
        return _row(m, UNMEASURED,
                    why=(f"{artifact} is consumed OUTSIDE the graph -- {external[:180]} -- so the "
                         f"consumer carries no rent line to inherit. What would price it is the "
                         f"decision that consumer changes, measured against the same decision "
                         f"taken on its own clock"),
                    artifact=artifact, readers=[], external_reader=external)
    if not readers:
        return _row(m, NOT_BINDING, rent=0.0,
                    why=(f"nothing on this tree reads {artifact}: this organ's output changes no "
                         f"decision, so its rent is zero by construction. Either wire a consumer "
                         f"or retire it -- the one thing it must not stay is unbilled"),
                    artifact=artifact, readers=[])
    # THE MONEY PATH IS NOT AN INHERITABLE PRICE. An organ feeding `gateway`, `release` or the
    # evaluator feeds something whose own rent is NOT_BINDING by construction, and inheriting that
    # would report "this organ does not bind" about an organ that decides what the desk holds.
    # What prices it is the realised growth of what it put there.
    infra = [r for r in readers if r in INFRASTRUCTURE]
    priced = {r: MODULES_BY_NAME[r] for r in readers
              if r in MODULES_BY_NAME and r not in INFRASTRUCTURE and r not in _chain}
    if not priced and infra:
        return _row(m, UNMEASURED,
                    why=(f"{artifact} feeds the money path directly ({', '.join(infra)}), whose "
                         f"own rent is not separable. What prices this organ is the realised "
                         f"growth of what it put in the book -- {LIVE_LEDGER} joined to the "
                         f"sleeves it admitted -- not an inherited NOT_BINDING"),
                    artifact=artifact, readers=readers, feeds_money_path=infra)
    if not priced:
        looped = [r for r in readers if r in _chain]
        return _row(m, UNMEASURED,
                    why=((f"{artifact} is read by {', '.join(readers)}, which is already on this "
                          f"inheritance chain ({' -> '.join(_chain)}): a research LOOP, so no "
                          f"consumer outside it prices this organ yet")
                         if looped else
                         (f"{artifact} is read by {', '.join(readers)}, and none of those carries "
                          f"a rent line either -- so the chain from this organ to a priced "
                          f"decision is not closed. 'Something reads it' is not 'it earns'")),
                    artifact=artifact, readers=readers)
    # INHERITED, NEVER RECOMPUTED. Two modules in one chain must not produce two different
    # answers about the same value; the consumer owns the arithmetic and this reports its verdict.
    rows: dict[str, dict[str, Any]] = {}
    for name, mod in priced.items():
        fn = MEASURES[mod.measure]
        rows[name] = (fn(mod, led, (*_chain, m.name)) if fn is measure_organ
                      else fn(mod, led))
    earns = [n for n, r in rows.items() if r["verdict"] == EARNS]
    costs = [n for n, r in rows.items() if r["verdict"] == COSTS]
    best = (earns or costs or sorted(rows))[0]
    row = rows[best]
    verdict = row["verdict"] if (earns or costs) else UNMEASURED
    return _row(m, verdict, rent=row.get("rent"), unit=str(row.get("unit") or "log-wealth/day"),
                n=int(row.get("n") or 0), ci=row.get("ci"), window=str(row.get("window") or ""),
                why=(f"inherited from {best}, which this organ's {artifact} feeds"
                     + (f": {row['why']}" if row.get("why") else "")),
                artifact=artifact, readers=readers, priced_through=best)


MEASURES = {name: fn for name, fn in globals().items() if name.startswith("measure_")}


def discover(led: Ledgers, modules: tuple[Module, ...] = MODULES) -> tuple[Module, ...]:
    """Ledger rows the registry does not name yet: judged dimensions, executed algorithms and
    alt-data sources present on this host. Reported under the registry's rules rather than left
    unbilled, and listed so the registry can be extended by name."""
    have = {m.name for m in modules}
    extra: list[Module] = []
    adm = led.json(STATE_ADMISSION)
    for d in sorted((adm.get("verdicts") or {}).keys()):
        name = f"state_dimension:{d}"
        if name not in have:
            extra.append(Module(name, "state_dimension", STATE_ADMISSION,
                                "walk-forward gain from conditioning on the dimension (unit: "
                                "out-of-sample MSE gain)", "measure_admission",
                                "discovered on STATE_ADMISSION.json", key=str(d)))
    for r in led.rows(ALGO_OUTCOMES):
        algo = str(r.get("algo") or "")
        name = f"execution_algo:{algo}"
        if algo and name not in have and all(e.name != name for e in extra):
            extra.append(Module(name, "execution_algo", ALGO_OUTCOMES,
                                "market baseline's mean realised cost minus the algorithm's",
                                "measure_execution_algo", "discovered on the outcomes ledger",
                                key=algo))
    pnl = led.json(RESEARCH_PNL)
    covered = tuple(p for m in modules for p in m.sources)
    for src in sorted((pnl.get("sources") or {}).keys()):
        base = str(src).split(":")[0]
        if SOURCE_ARM.get(base) != "alt_data_hypothesis" or any(
                str(src).startswith(p) for p in covered):
            continue
        name = f"data_source:{src}"
        if name not in have:
            extra.append(Module(name, "data_source", RESEARCH_PNL,
                                "growth the source's certificates carry in the funded book",
                                "measure_research_source", "discovered on RESEARCH_PNL.json",
                                key=str(src), sources=(str(src),)))
    return (*modules, *extra)


def measure(root: Path | None = None,
            modules: tuple[Module, ...] | None = None) -> dict[str, dict[str, Any]]:
    """Every module's rent from the desk's own ledgers under `root`. Reads only."""
    led = Ledgers(ROOT if root is None else Path(root))
    mods = discover(led) if modules is None else modules
    out: dict[str, dict[str, Any]] = {}
    for m in mods:
        fn = MEASURES[m.measure]
        try:
            out[m.name] = fn(m, led)
        except Exception as exc:                     # a broken ledger is a reading, not a crash
            out[m.name] = _row(m, UNMEASURED, why=f"{type(exc).__name__}: {exc}")
    return out


# --------------------------------------------------------------------------- history and RETIRE
def _window_id(day: str) -> str:
    """The Monday of the ISO week the day falls in: one window per week, whatever the cadence."""
    d = date.fromisoformat(day)
    return d.fromordinal(d.toordinal() - d.weekday()).isoformat()


def retire_list(history: list[dict[str, Any]], *, k: int = K_WINDOWS,
                min_n: int = MIN_N) -> dict[str, dict[str, Any]]:
    """Modules that read COSTS with n >= min_n in the last k consecutive weekly windows.

    The LAST reading in a window speaks for it (a rerun on the same day supersedes, never
    accumulates). A window without a reading breaks the run: silence is not a COSTS verdict.
    """
    by_mod: dict[str, dict[str, dict[str, Any]]] = defaultdict(dict)
    for r in history:
        name, day = str(r.get("module") or ""), str(r.get("day") or "")
        if not name or not day:
            continue
        try:
            wid = _window_id(day)
        except ValueError:
            continue
        cur = by_mod[name].get(wid)
        if cur is None or str(cur.get("day")) <= day:
            by_mod[name][wid] = r
    out: dict[str, dict[str, Any]] = {}
    for name, wins in by_mod.items():
        ordered = sorted(wins.items(), reverse=True)
        run = 0
        for i, (wid, r) in enumerate(ordered):
            if i > 0:
                prev_w = date.fromisoformat(ordered[i - 1][0])
                if (prev_w - date.fromisoformat(wid)).days != 7:
                    break                                    # a gap in the record ends the run
            if r.get("verdict") == COSTS and int(_num(r.get("n")) or 0) >= min_n:
                run += 1
            else:
                break
        if run >= k:
            out[name] = {"kind": ordered[0][1].get("kind"), "windows_costs": run,
                         "since_window": ordered[run - 1][0],
                         "latest": {key: ordered[0][1].get(key)
                                    for key in ("day", "rent", "unit", "n", "ci")},
                         "ledger": ordered[0][1].get("ledger")}
    return out


def run(root: Path | None = None, write: bool = True, today: str | None = None) -> dict[str, Any]:
    """Measure, remember today's readings once, name what has cost growth for K windows."""
    base = ROOT if root is None else Path(root)
    day = today or datetime.now(tz=UTC).date().isoformat()
    modules = measure(base)
    led = Ledgers(base)
    history = led.rows(HISTORY)
    have = {(str(r.get("module")), str(r.get("day"))) for r in history}
    new: list[dict[str, Any]] = []
    for name, row in modules.items():
        if (name, day) in have:
            continue
        new.append({"day": day, "module": name, "kind": row["kind"], "verdict": row["verdict"],
                    "rent": row["rent"], "unit": row["unit"], "n": row["n"], "ci": row["ci"],
                    "ledger": row["ledger"], "at": datetime.now(tz=UTC).isoformat()})
    if write and new:
        p = base / HISTORY
        p.parent.mkdir(parents=True, exist_ok=True)
        with p.open("a", encoding="utf-8") as fh:
            for r in new:
                fh.write(json.dumps(r) + "\n")
    history = history + new
    retire = retire_list(history)
    by_verdict: dict[str, list[str]] = defaultdict(list)
    for name, row in modules.items():
        by_verdict[str(row["verdict"])].append(name)
    doc: dict[str, Any] = {
        "generated_utc": datetime.now(tz=UTC).isoformat(), "day": day,
        "n_modules": len(modules),
        "modules": modules,
        "retire": retire,
        "costs": sorted(by_verdict[COSTS]), "earns": sorted(by_verdict[EARNS]),
        "not_binding": sorted(by_verdict[NOT_BINDING]),
        "unmeasured": sorted(by_verdict[UNMEASURED]),
        "by_kind": {k: {v: sum(1 for r in modules.values() if r["kind"] == k and r["verdict"] == v)
                        for v in (EARNS, COSTS, NOT_BINDING, UNMEASURED)} for k in KINDS},
        "registry": [asdict(m) for m in MODULES],
        "history_rows": len(history), "new_rows": len(new),
        "lines": {"min_n": MIN_N, "t_line": T_LINE, "k_windows": K_WINDOWS},
        "rule": ("rent = Elog_with - Elog_without on the module's own ledger; a module that reads "
                 f"COSTS with n >= {MIN_N} in {K_WINDOWS} consecutive weekly windows is NAMED "
                 "under `retire`. This report names; a person or the capability-graph check "
                 "retires. No sacred modules -- the AI organs are on the same list."),
        "consumers": ("libs/ops/capability_graph.stages (MEASURED evidence), "
                      "scripts/check_reachability (warns on a node whose rent is COSTS), "
                      "the principal"),
    }
    if write:
        p = base / REPORT
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(doc, indent=1, default=str), "utf-8")
    return doc


def main() -> int:
    d = run()
    print(f"MODULE RENT  {d['n_modules']} modules  costs={d['costs']}  earns={d['earns']}  "
          f"retire={sorted(d['retire'])}")
    for name, r in d["modules"].items():
        rent = "" if r["rent"] is None else f" rent={r['rent']:+.3e} {r['unit']}"
        print(f"  {name:36s} {r['kind']:20s} {r['verdict']:12s} n={r['n']:<5d}{rent}")
        if r["verdict"] == UNMEASURED and r.get("why"):
            print(f"      {r['why']}")
    print(f"written: {ROOT / REPORT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

```

### libs\ops\wiring_audit.py
```python
"""What was built and is unreachable, and what to do about each one -- mechanically.

THE DESK'S DOMINANT FAILURE MODE, MEASURED 2026-09-10: 121 library modules that nothing imports,
plus 11 scripts that are the SOLE importer of a libs module and are themselves never invoked. That
second class is the nastier one -- the orphan check goes green because a caller exists, and the
caller is as unreachable as the module.

Seven instances were found by hand in a single session (account_profile written for the prop/live
split with the money path never reading it; analyst_rank's cross-section never registered as a
family; task_queue durable and event-triggered with nothing claiming from it; alpha_rl with no
consumer; release_identity's verdict written every pass and never carried to the dashboard;
stall_watch reporting failing tasks with nothing ranking them; a ledger next_step instructing a
reader to build what was already registered). Seven by hand, 132 by machine. That ratio is the
argument for this file.

WHY A FOCUSED MODULE RATHER THAN scripts/max_audit.check_unwired_modules. That check is the CI
gate and stays exactly where it is; it is one function inside an 8,000-line script that exits on
import, so nothing can consume its findings. This produces the same evidence as DATA -- typed
records with a verdict and the reason for it -- so a queue can carry it, a worker can act on it,
and a test can assert on it.

THE VERDICT IS DERIVED, NOT JUDGED, because a classifier that needed an opinion could not run
unattended:

    EXEMPT   declared, with a reason, in `_EXEMPT`. The list is the argument.
    WIRE     nothing imports it AND it has tests. Someone invested enough to prove it works and
             then nothing called it -- the exact "built, tested, unreachable" class, and the one
             where the value is already paid for and merely unclaimed.
    RETIRE   nothing imports it and NOTHING TESTS IT either. No caller and no proof; wiring it
             would place unverified code on a clock, which is worse than deleting it.

TESTS DO NOT COUNT AS WIRING, and the distinction is the whole point: a test importing a module
proves it works, not that anything uses it. Counting tests as callers would make every orphan look
connected, which is precisely the failure being detected. They are read here only to tell WIRE
from RETIRE.

A MODULE THIS FILE CANNOT SEE A CALLER FOR MAY STILL HAVE ONE. `python -m libs.x.y` in a shell or
a crontab is a real caller that no AST scan of .py files can see, so the shell surface is scanned
for `-m` targets. That can only ever ADD callers, never hide an orphan.
"""
from __future__ import annotations

import ast
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

#: Directories whose .py files are searched for imports. `tests` is deliberately absent -- see the
#: header: a test is proof of correctness, never evidence of use.
_CALLER_AREAS: tuple[str, ...] = ("libs", "scripts", "desks", "api", "app", "ops", "deploy")

#: Where a `python -m libs.x.y` invocation can hide. Shell, cron and unit files are read as text.
_SHELL_AREAS: tuple[str, ...] = ("scripts", "ops", "deploy")
_SHELL_SUFFIXES: tuple[str, ...] = (".sh", ".ps1", ".service", ".timer", ".manifest", ".env", "")

_MODULE_M = re.compile(r"-m\s+(libs(?:\.[A-Za-z_][A-Za-z0-9_]*)+)")

#: A leg that runs a module BY PATH is a caller too, and neither an import nor a `-m` target.
#: `hourly_cycle` dispatches its subprocess legs as `_producer("name", "libs/ops/x.py")`, which
#: resolves the string against the repo root and runs it -- so the module is invoked hourly and
#: an AST import scan sees nothing. Found by wiring this file's own leg and watching the auditor
#: go on listing itself: the same blind spot the `-m` scan was added to close, in the other
#: spelling. Like that one, this can only ADD callers, never hide an orphan.
_MODULE_PATH = re.compile(
    r"['\"](libs/(?:[A-Za-z_][A-Za-z0-9_]*/)*[A-Za-z_][A-Za-z0-9_]*\.py)['\"]")

#: Modules that are unreachable ON PURPOSE, each with the reason. This list is the argument for
#: leaving them alone, so an entry without a reason is not an entry.
_EXEMPT: dict[str, str] = {
    "libs": "package root",
}

#: Trees whose modules can reach live capital if wired wrongly. A finding here is not treated
#: differently by the CLASSIFIER -- the evidence is the same -- but the applier gates it on the
#: full desk suite rather than the module's own tests.
_MONEY_TREES: tuple[str, ...] = ("libs.portfolio", "libs.risk", "libs.execution", "libs.ops")


@dataclass(frozen=True)
class Finding:
    """One unreachable module and the verdict derived from its own evidence."""

    module: str
    kind: str                      # no_importer | sole_importer_unreachable
    verdict: str                   # WIRE | RETIRE | EXEMPT
    why: str
    lines: int = 0
    has_tests: bool = False
    public: tuple[str, ...] = ()
    money_path: bool = False
    detail: str = ""

    def to_dict(self) -> dict[str, Any]:
        return dict(vars(self)) | {"public": list(self.public)}


@dataclass
class Graph:
    """The import graph, kept so callers can ask questions this module does not answer."""

    modules: dict[str, Path] = field(default_factory=dict)
    importers: dict[str, set[str]] = field(default_factory=dict)
    shell_targets: set[str] = field(default_factory=set)
    tested: set[str] = field(default_factory=set)


def _dotted(root: Path, path: Path) -> str:
    rel = path.relative_to(root).with_suffix("")
    name = ".".join(rel.parts)
    return name[: -len(".__init__")] if name.endswith(".__init__") else name


def _imports_of(path: Path) -> set[str]:
    """Every `libs.*` module a file imports, absolute form only.

    RELATIVE IMPORTS ARE RESOLVED AGAINST NOTHING and are skipped deliberately: inside `libs` they
    connect siblings, and a sibling importing a sibling does not make either reachable from
    outside. Counting them would let a cluster of orphans vouch for each other.
    """
    try:
        tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
    except (OSError, SyntaxError):
        return set()
    out: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            out |= {a.name for a in node.names if a.name.startswith("libs.")}
        elif (isinstance(node, ast.ImportFrom) and node.level == 0 and node.module
              and node.module.startswith("libs")):
            out.add(node.module)
            out |= {f"{node.module}.{a.name}" for a in node.names}
    return out


def build_graph(root: Path) -> Graph:
    """The whole picture in one pass: what exists, who imports it, what a shell runs, what tests."""
    g = Graph()
    lib_root = root / "libs"
    if lib_root.is_dir():
        for p in sorted(lib_root.rglob("*.py")):
            if "__pycache__" in p.parts:
                continue
            g.modules[_dotted(root, p)] = p

    for area in _CALLER_AREAS:
        base = root / area
        if not base.is_dir():
            continue
        for p in sorted(base.rglob("*.py")):
            if "__pycache__" in p.parts or "tests" in p.parts:
                continue
            self_name = _dotted(root, p) if area == "libs" else ""
            # A MODULE RUN BY PATH IS RUN. See `_MODULE_PATH`.
            try:
                for rel in _MODULE_PATH.findall(p.read_text(encoding="utf-8", errors="replace")):
                    named = rel[: -len(".py")].replace("/", ".")
                    if named != self_name:
                        g.shell_targets.add(named)
            except OSError:
                pass
            for target in _imports_of(p):
                # SELF IS EXCLUDED PER FILE, NEVER GLOBALLY. Removing the name from a shared set
                # is the bug that made an earlier walker report 241 of 244 modules as orphans:
                # each file erased the record that anything else had imported it.
                if target == self_name:
                    continue
                g.importers.setdefault(target, set()).add(self_name or str(p.relative_to(root)))

    for area in _SHELL_AREAS:
        base = root / area
        if not base.is_dir():
            continue
        for p in base.rglob("*"):
            if not p.is_file() or p.suffix not in _SHELL_SUFFIXES:
                continue
            try:
                g.shell_targets |= set(_MODULE_M.findall(p.read_text(encoding="utf-8",
                                                                     errors="replace")))
            except OSError:
                continue

    tests = root / "tests"
    if tests.is_dir():
        for p in sorted(tests.rglob("*.py")):
            if "__pycache__" not in p.parts:
                g.tested |= _imports_of(p)
    for p in sorted(root.glob("desks/*/tests/*.py")):
        g.tested |= _imports_of(p)
    return g


def _public(path: Path) -> tuple[str, ...]:
    """Top-level names a caller could use. What a wiring proposal has to work with."""
    try:
        tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
    except (OSError, SyntaxError):
        return ()
    out = [n.name for n in tree.body
           if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
           and not n.name.startswith("_")]
    return tuple(sorted(out))


def findings(root: Path, graph: Graph | None = None) -> list[Finding]:
    """Every unreachable module, worst first, each carrying the evidence for its verdict."""
    g = graph or build_graph(root)
    # A PACKAGE IS REACHED THROUGH ITS CONTENTS. `libs/regime/__init__.py` is never imported by
    # name, but `from libs.regime.asset_state import ...` executes it -- so flagging it as an
    # orphan is a false positive, and one that would send a wirer to write a caller for a file
    # that already runs. Measured on this tree: libs.models, libs.regime, libs.alpha_factory,
    # libs.autodiscovery and libs.ict were all reported this way.
    reached = set(g.importers) | g.shell_targets
    packages = {n for n in g.modules if any(m.startswith(f"{n}.") for m in reached)}
    out: list[Finding] = []
    for name, path in sorted(g.modules.items()):
        if name in _EXEMPT or name in packages:
            continue
        if g.importers.get(name) or name in g.shell_targets:
            continue
        tested = name in g.tested
        try:
            lines = len(path.read_text(encoding="utf-8", errors="replace").splitlines())
        except OSError:
            lines = 0
        verdict = "WIRE" if tested else "RETIRE"
        why = ("nothing imports it and it HAS tests: the value is already paid for and merely "
               "unclaimed" if tested else
               "nothing imports it and nothing tests it: no caller and no proof, so wiring it "
               "would put unverified code on a clock")
        out.append(Finding(module=name, kind="no_importer", verdict=verdict, why=why,
                           lines=lines, has_tests=tested, public=_public(path),
                           money_path=name.startswith(_MONEY_TREES)))
    out.extend(_one_link_short(root, g))
    order = {"WIRE": 0, "RETIRE": 1, "EXEMPT": 2}
    out.sort(key=lambda f: (order.get(f.verdict, 3), -f.lines, f.module))
    return out


def _one_link_short(root: Path, g: Graph) -> list[Finding]:
    """A module whose only importer is a script nothing ever runs.

    THE HOLE IN THE ORPHAN CHECK. A libs module counts as wired the moment ANY file imports it --
    including an entrypoint nothing invokes. So the honest fix for an orphan ("write it a caller")
    is satisfied by a file that is itself an orphan: the check goes green and the module is
    exactly as unreachable as before. A wiring fix one link short reports success, which is worse
    than no fix, because it also removes the alarm.
    """
    runnable = set(g.shell_targets)
    for area in _SHELL_AREAS:
        base = root / area
        if not base.is_dir():
            continue
        for p in base.rglob("*"):
            if p.is_file() and p.suffix in _SHELL_SUFFIXES:
                try:
                    text = p.read_text(encoding="utf-8", errors="replace")
                except OSError:
                    continue
                runnable |= set(re.findall(r"scripts/[A-Za-z0-9_./-]+\.py", text))
    out: list[Finding] = []
    for name, importers in sorted(g.importers.items()):
        if name not in g.modules or name in _EXEMPT:
            continue
        script_only = [i for i in importers if i.startswith("scripts/")]
        if len(importers) != len(script_only) or not script_only:
            continue
        if any(s in runnable for s in script_only):
            continue
        # SAME EVIDENCE AS AN ORPHAN, because it is one. The first draft left lines/public empty
        # here, which made every one-link-short finding render as a 0-line module -- so the
        # report sorted the largest of them last and read as though they were stubs.
        path = g.modules[name]
        try:
            lines = len(path.read_text(encoding="utf-8", errors="replace").splitlines())
        except OSError:
            lines = 0
        out.append(Finding(
            module=name, kind="sole_importer_unreachable", verdict="WIRE",
            why=("its only importer is a script nothing invokes, so the orphan check is green "
                 "and the module is exactly as unreachable as an orphan"),
            lines=lines, has_tests=name in g.tested, public=_public(path),
            money_path=name.startswith(_MONEY_TREES),
            detail="; ".join(sorted(script_only))))
    return out


#: Where the census lands so the dashboard and the wirer can both read it. Relative to the repo
#: root, beside the desk's other reports -- `libs.ops.release` already spells a desk path this way.
REPORT_REL = "desks/mt5/reports/WIRING_AUDIT.json"


def census(root: Path) -> dict[str, Any]:
    """The counts an operator reads, and the list a queue consumes."""
    found = findings(root)
    by = {v: [f.module for f in found if f.verdict == v] for v in ("WIRE", "RETIRE", "EXEMPT")}
    return {"total": len(found),
            "wire": len(by["WIRE"]), "retire": len(by["RETIRE"]),
            "money_path": sum(1 for f in found if f.money_path),
            "one_link_short": sum(1 for f in found
                                  if f.kind == "sole_importer_unreachable"),
            "by_verdict": by,
            "findings": [f.to_dict() for f in found]}


def main(argv: list[str] | None = None) -> int:
    """Write the census and say what it found. The leg that makes this module its own first fix.

    THE AUDITOR WAS IN ITS OWN REPORT, which is the only honest way to start a wiring campaign:
    on the run that produced the first census, `libs.ops.wiring_audit` appeared under RETIRE --
    no caller, no tests. This function and the hourly leg that calls it are what took it off its
    own list, and the shape is the one every other fix on that list has to take.

    EXIT 0 WHATEVER IT FINDS. A cycle leg that fails the pass when the repo has orphans would be
    removed within a week, correctly -- the census is evidence for the wirer to act on, not a gate.
    The gate this desk already has for that is scripts/max_audit.check_unwired_modules, and it
    stays exactly where it is.
    """
    import argparse
    import json

    ap = argparse.ArgumentParser(description="census the modules nothing calls")
    ap.add_argument("--root", default=None, help="repository root (default: this file's repo)")
    ap.add_argument("--json", action="store_true", help="print the census instead of a summary")
    args = ap.parse_args(argv)

    root = Path(args.root) if args.root else Path(__file__).resolve().parents[2]
    c = census(root)
    out = root / Path(*REPORT_REL.split("/"))
    try:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(c, indent=1), encoding="utf-8")
    except OSError as exc:
        print(f"wiring audit: could not write {REPORT_REL} ({exc.__class__.__name__})")

    if args.json:
        print(json.dumps(c, indent=1))
    else:
        print(f"wiring audit: {c['total']} unreachable -- {c['wire']} WIRE, {c['retire']} RETIRE, "
              f"{c['money_path']} in money-path trees, {c['one_link_short']} one link short")
        for f in c["findings"][:10]:
            print(f"  {f['verdict']:7s} {f['module']:46s} {f['lines']:>4}L  {f['kind']}")
    return 0


if __name__ == "__main__":       # pragma: no cover - entrypoint
    raise SystemExit(main())

```

### libs\research\anomaly_miner.py
```python
"""Data-first discovery: find the anomaly IN THE DATA, then ask what could explain it.

WHY THIS IS THE MISSING HALF. This desk's validation side is strong and its discovery side is not
even in the same discipline, and the numbers say so plainly. Measured 2026-09-03 from
`miner_candidates.per_source`: broker_swaps turned 248 evidence rows into 248 executable
candidates, forexfactory 44 into 107, cot 11 into 7 -- while reddit, github, quant_se,
bis_speeches, amarkets and the world crawler produced 0 from 341. Every candidate the desk owns
came from STRUCTURED DATA. Every prose source converts at exactly zero, and it is not a tuning
gap: the compiler's rule is "exact recipe or structured causal data only", so an article
structurally cannot supply a family with exact params.

So the desk had one generator class that works, and it is fed by whatever tables happen to be
lying around. Everything else -- crawlers, LLM seats, forums -- is aimed at the class that cannot
pay. The bound on discovery is not the gauntlet's strictness; it is that almost nothing reaches it.

THE INVERSION. Prose generation asks a model to imagine an edge and then looks for it. This scans
the bars the desk ALREADY OWNS for conditional structure that is unlikely under a null, and only
then asks what could explain it. The imagination of a language model stops bounding the search;
the data does. That is the one generator whose supply scales with the universe (237 tradeable
symbols x sessions x horizons) rather than with how many articles were published this week.

WHAT IT EMITS AND WHAT IT REFUSES. It emits ANOMALIES -- (symbol, condition, horizon, effect,
n, t-like statistic) -- never candidates. An anomaly is an observation; a candidate needs a named
mechanism, and naming one from a correlation is precisely the prose-to-family guessing the
compiler exists to refuse. Anomalies go to the mechanism-naming queue, where a brain must name a
cause WITH EVIDENCE or the row dies. Nothing here sets a threshold that competes with the ten
gates: every survivor still walks the same pipeline, carrying an honest trial count so deflation
charges the full width of this search.

TRIALS ARE COUNTED AND CARRIED. A scan this wide is a multiplicity machine, and hiding that would
make every downstream deflated Sharpe a lie. `trials` on the report is the real number of
(symbol, condition, horizon) cells evaluated, not the number that survived.
"""
from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

_ROOT = Path(__file__).resolve().parents[2]
_DESK = _ROOT / "desks" / "mt5"
_BARS = _DESK / "data" / "universe"
_OUT = _DESK / "data" / "intelligence" / "anomalies"

#: Minimum observations in a conditional cell. Below this the statistic is noise wearing a number,
#: and the desk has been burned by cells that "fired" a handful of times.
MIN_N = 60

#: |t|-like screen. NOT a verdict and NOT a gate -- purely a reporting floor so the queue receives
#: structure rather than every cell ever evaluated. The ten gates remain the only arbiter, and
#: they will deflate against `trials` below, which counts everything looked at.
REPORT_T = 3.0

#: Horizons in bars. H1 data, so 1/3/6/12/24 spans an hour to a day.
HORIZONS = (1, 2, 3, 6, 12, 24, 48, 72)


@dataclass(frozen=True)
class Anomaly:
    """One conditional regularity, stated so a brain can try to explain or kill it."""

    symbol: str
    condition: str
    horizon: int
    n: int
    mean_bp: float
    t_stat: float
    hit_rate: float
    baseline_bp: float
    question: str

    def as_row(self) -> dict[str, Any]:
        d = asdict(self)
        d["kind"] = "anomaly"
        d["mechanism_status"] = "UNNAMED"
        d["note"] = ("data-first anomaly: an OBSERVATION, not a candidate. A mechanism must be "
                     "named with evidence before this can become executable.")
        return d


#: THE DESK'S OWN PRIMITIVE LIBRARY IS THE VOCABULARY. Not a list written here.
#:
#: This file previously defined its own 21 primitives -- skew, accel, streak, dist_high and the
#: rest -- and generated conditions from them. They were reasonable primitives and they were
#: USELESS, because `family_discovered` resolves a feature name through
#: `edge_search.build_primitives`, and only 5 of the 21 existed there. The other 16 would have
#: resolved to None at execution time, so every candidate this miner produced would have been
#: unexecutable: thousands of anomalies, each carrying a mechanism and a falsifier, that the
#: gauntlet could never have evaluated. Conversion would have been exactly zero, and the reason
#: would have looked like "the gates are strict" rather than "the producer and the executor speak
#: different languages" -- which is this desk's single most expensive defect shape and had already
#: happened four times today.
#:
#: So the vocabulary is IMPORTED. build_primitives supplies 106 features, already windowed
#: (dd_12, dd_24, kurt_96, path_efficiency_12 ...), and every one of them is by construction a
#: name the executor can resolve. It also removes the last hardcoded list from this file: the
#: search space is now whatever the desk can actually compute, which widens the moment a
#: primitive is added there and needs no change here.
_BANDS: tuple[tuple[float, float], ...] = (
    (0.0, 0.05), (0.0, 0.1), (0.1, 0.25), (0.25, 0.4), (0.4, 0.6),
    (0.6, 0.75), (0.75, 0.9), (0.9, 1.0), (0.95, 1.0),
)


def _conditions(df: pd.DataFrame, symbol: str = "") -> dict[str, np.ndarray]:
    """Every (canonical primitive x band) mask. The vocabulary is the executor's, not ours.

    Each mask says "this primitive sits in this part of its own trailing distribution", ranked
    over a rolling window so the condition is point-in-time and comparable across instruments.
    The KEY is `<feature>_q<lo>-<hi>`, and `<feature>` is a name `build_primitives` supplies --
    which is what makes the resulting anomaly directly compilable into
    `family_discovered(feature=..., band=..., horizon=..., side=...)`.
    """
    try:
        import sys as _sys
        _d = str(_DESK)
        if _d not in _sys.path:
            _sys.path.insert(0, _d)
        _r = str(_DESK / "research")
        if _r not in _sys.path:
            _sys.path.insert(0, _r)
        from research.edge_search import build_primitives  # type: ignore[import-not-found]
    except ImportError:
        try:
            from edge_search import build_primitives  # type: ignore[import-not-found]
        except ImportError:
            return {}                    # UNMEASURED: no vocabulary, so no conditions at all
    # THE ACQUIRED VOCABULARY IS PART OF THE SEARCH, not a separate one. Everything price-native
    # is derived from the same OHLCV, so conditions built only on it produce edges that share a
    # driver -- which is exactly why the allocator's family cap binds at 40% on five mechanisms.
    # Positioning, rate differentials and cross-currency reference rates are a DIFFERENT driver,
    # and they are the raw material for the uncorrelated mechanisms the book is starved of.
    # Passed as `extra`, so they arrive as `ext_<name>` -- names `family_discovered` resolves
    # through this same function, which is what makes an anomaly found here executable there.
    extra: dict[str, Any] = {}
    try:
        from research.acquire_datasets import acquired_series  # type: ignore[import-not-found]
        extra = acquired_series(df.index)
    except Exception:
        extra = {}                       # no acquired data is fewer conditions, never a failure
    try:
        prim = build_primitives(df, symbol, extra)
    except Exception:
        return {}

    out: dict[str, np.ndarray] = {}
    for name, series in prim.items():
        try:
            ser = pd.Series(series, index=df.index).astype(float)
        except Exception:
            continue
        if not np.isfinite(ser.to_numpy()).any():
            continue
        rank = ser.rolling(500, min_periods=200).rank(pct=True)
        for lo, hi in _BANDS:
            mask = ((rank > lo) & (rank <= hi)).to_numpy()
            if mask.sum() < MIN_N:
                continue
            out[f"{name}_q{lo:g}-{hi:g}"] = mask
    return out


def scan_symbol(symbol: str, df: pd.DataFrame) -> tuple[list[Anomaly], int]:
    """Every (condition x horizon) cell for one symbol. Returns (reportable, trials_evaluated)."""
    if df is None or len(df) < 1200:
        return [], 0
    close = df["close"].astype(float)
    conds = _conditions(df, symbol)
    found: list[Anomaly] = []
    trials = 0
    for h in HORIZONS:
        fwd = (close.shift(-h) / close - 1.0).to_numpy()
        base = float(np.nanmean(fwd)) * 1e4
        for name, mask in conds.items():
            trials += 1
            m = np.asarray(mask, dtype=bool) & np.isfinite(fwd)
            n = int(m.sum())
            if n < MIN_N:
                continue
            vals = fwd[m]
            mu, sd = float(np.nanmean(vals)), float(np.nanstd(vals, ddof=1))
            if not (sd > 0 and math.isfinite(mu)):
                continue
            # OVERLAPPING FORWARD RETURNS DESTROY THE SAMPLE SIZE, and using raw n inflated
            # every statistic this miner produced. A horizon-h forward return shares h-1 bars
            # with its neighbour, so consecutive observations are not independent draws: the
            # effective count is ~n/h, and t computed on n is too large by sqrt(h). At h=24 that
            # is a factor of 4.9, which is exactly why the top hits were reading |t|=38.
            #
            # MEASURED 2026-09-03: 68,899 of 315,982 cells cleared |t|>=3 -- a 21.8% hit rate
            # against a null expectation near 0.3%. Seventy times the null is not structure, it
            # is a broken denominator, and every one of those rows would have carried its
            # inflated statistic into the compiler, the naming queue and the trial accounting.
            #
            # The condition mask is also persistent (a quantile band holds for runs of bars), so
            # n/h remains OPTIMISTIC. It is the floor of the correction, not the whole of it --
            # the gates still do the real work, and this only stops the miner lying to them.
            n_eff = max(2.0, n / float(max(1, h)))
            t = mu / (sd / math.sqrt(n_eff))
            if abs(t) < REPORT_T:
                continue
            found.append(Anomaly(
                symbol=symbol, condition=name, horizon=h, n=int(n_eff),
                mean_bp=round(mu * 1e4, 3), t_stat=round(t, 3),
                hit_rate=round(float((vals > 0).mean()), 4), baseline_bp=round(base, 3),
                question=(f"{symbol} returns over {h}h are {mu * 1e4:.1f}bp when "
                          f"{name} (n={n}, |t|={abs(t):.1f}) against a {base:.1f}bp baseline. "
                          f"WHAT MECHANISM would do that, and what would falsify it? "
                          f"Unnamed, this is a correlation and may never be traded.")))
    return found, trials


def scan_cross_section(frames: dict[str, pd.DataFrame], *, max_pairs: int = 400
                       ) -> tuple[list[dict[str, Any]], int]:
    """Anomalies that live BETWEEN instruments, which single-symbol scanning cannot see.

    WHY THIS IS THE HIGHEST-ROI GROUND LEFT, MEASURED. The allocator is not short of heat, it is
    short of MECHANISMS: only six are funded, MAX_FAMILY_HEAT_SHARE binds at 40%, and the sweep
    on 2026-09-03 showed relaxing that concentration is worth roughly four times what raising
    heat is (20%->30% heat: +38% growth; family cap 40%->101% at fixed heat: +151%). Heat is
    capped by a wipeout path at 35%; concentration is capped by having nothing uncorrelated to
    put money into. So the binding constraint on this book is the SUPPLY OF INDEPENDENT EDGES,
    and every generator the desk owns scans one symbol at a time -- which by construction
    produces edges that share a driver.

    A relationship is a different object. Lead-lag, residual dispersion and relative strength are
    not the same trade as "momentum on EURUSD" wearing a different symbol, which is exactly what
    the redundancy term keeps rejecting.

    POINT-IN-TIME AND ALIGNED. Both legs are reindexed onto a shared clock and every statistic is
    computed on bars at or before the decision bar, with the forward return taken strictly after.
    Misaligned frames silently produce spectacular lead-lag artefacts, so alignment is done here
    rather than assumed.
    """
    import itertools

    syms = sorted(frames)
    rows: list[dict[str, Any]] = []
    trials = 0
    pairs = list(itertools.combinations(syms, 2))[:max_pairs]
    for a, b in pairs:
        fa, fb = frames[a], frames[b]
        idx = fa.index.intersection(fb.index)
        if len(idx) < 1500:
            continue
        ca = fa.loc[idx, "close"].astype(float)
        cb = fb.loc[idx, "close"].astype(float)
        ra, rb = ca.pct_change(), cb.pct_change()

        # LEAD-LAG: does b's move predict a's NEXT move, beyond a's own autocorrelation?
        for lag in (1, 2, 3):
            trials += 1
            x = rb.shift(lag)
            y = ra
            m = np.isfinite(x) & np.isfinite(y)
            n = int(m.sum())
            if n < 500:
                continue
            xv, yv = x[m].to_numpy(), y[m].to_numpy()
            if xv.std() <= 0 or yv.std() <= 0:
                continue
            r = float(np.corrcoef(xv, yv)[0, 1])
            t = r * math.sqrt(max(n - 2, 1) / max(1e-12, 1 - r * r))
            if abs(t) < REPORT_T or abs(r) < 0.03:
                continue
            rows.append({
                "kind": "anomaly", "family_hint": "lead_lag",
                "symbol": a, "against": b, "condition": f"lead_lag_{b}_lag{lag}",
                "horizon": 1, "n": n, "corr": round(r, 4), "t_stat": round(t, 3),
                "mechanism_status": "UNNAMED",
                "question": (f"{b} at lag {lag}h correlates {r:+.3f} with {a}'s next hour "
                             f"(n={n}, |t|={abs(t):.1f}). WHAT MECHANISM transmits that -- shared "
                             f"factor, quote latency, a common venue -- and what would falsify "
                             f"it? Unnamed, this is a correlation and may never be traded."),
            })

        # RESIDUAL DISPERSION: when b-relative valuation stretches, does a revert?
        trials += 1
        win = 240
        beta = ra.rolling(win).cov(rb) / rb.rolling(win).var()
        resid = (ca / ca.shift(win) - 1.0) - beta * (cb / cb.shift(win) - 1.0)
        z = (resid - resid.rolling(win).mean()) / resid.rolling(win).std()
        fwd = (ca.shift(-6) / ca - 1.0)
        for label, mask in (("resid_rich", (z >= 2.0)), ("resid_cheap", (z <= -2.0))):
            trials += 1
            m = mask.to_numpy() & np.isfinite(fwd).to_numpy()
            n = int(m.sum())
            if n < MIN_N:
                continue
            vals = fwd.to_numpy()[m]
            mu, sd = float(np.nanmean(vals)), float(np.nanstd(vals, ddof=1))
            if not (sd > 0 and math.isfinite(mu)):
                continue
            # OVERLAPPING FORWARD RETURNS DESTROY THE SAMPLE SIZE, and using raw n inflated
            # every statistic this miner produced. A horizon-h forward return shares h-1 bars
            # with its neighbour, so consecutive observations are not independent draws: the
            # effective count is ~n/h, and t computed on n is too large by sqrt(h). At h=24 that
            # is a factor of 4.9, which is exactly why the top hits were reading |t|=38.
            #
            # MEASURED 2026-09-03: 68,899 of 315,982 cells cleared |t|>=3 -- a 21.8% hit rate
            # against a null expectation near 0.3%. Seventy times the null is not structure, it
            # is a broken denominator, and every one of those rows would have carried its
            # inflated statistic into the compiler, the naming queue and the trial accounting.
            #
            # The condition mask is also persistent (a quantile band holds for runs of bars), so
            # n/h remains OPTIMISTIC. It is the floor of the correction, not the whole of it --
            # the gates still do the real work, and this only stops the miner lying to them.
            n_eff = max(2.0, n / 6.0)  # h=6: fwd is ca.shift(-6)
            t = mu / (sd / math.sqrt(n_eff))
            if abs(t) < REPORT_T:
                continue
            rows.append({
                "kind": "anomaly", "family_hint": "cross_asset_residual",
                "symbol": a, "against": b, "condition": f"{label}_vs_{b}",
                "horizon": 6, "n": n, "mean_bp": round(mu * 1e4, 3), "t_stat": round(t, 3),
                "mechanism_status": "UNNAMED",
                "question": (f"{a} returns {mu * 1e4:+.1f}bp over 6h when its {win}h return is "
                             f"2sd {'rich' if 'rich' in label else 'cheap'} against {b} "
                             f"(n={n}, |t|={abs(t):.1f}). WHAT MECHANISM reverts it, and what "
                             f"would falsify that? Unnamed, this may never be traded."),
            })
    return rows, trials


#: Where the rotation cursor lives. The scan covers the WHOLE universe every run; this only
#: rotates which symbols are retained for the pairwise pass, whose cost is quadratic.
_CURSOR = _DESK / "data" / "intelligence" / "anomaly_cursor.json"

#: Symbols given the FULL widened space per run. The space is 9,288 cells per symbol and the
#: universe is 251, so an all-symbols run is 2.3M cells and hours of wall clock -- far past the
#: cycle it is scheduled on. Rotating means no symbol is excluded, only deferred: the cursor
#: advances every run, so the whole universe is covered across a day rather than the first 40
#: names alphabetically being covered forever. Deferred is a schedule; excluded is a bias.
_SCAN_PER_RUN = 30

#: Symbols kept in memory for the cross-sectional pass per run. Not a limit on what is SCANNED --
#: every symbol is scanned every run -- but on how many frames are held at once, because pairs
#: grow as n^2 and this box has 3.8GB and no swap. The cursor advances so every symbol enters the
#: pairwise pass in turn; over a day's runs the pair space is covered without a single run that
#: cannot fit.
_CROSS_FRAMES = 60


def _cursor_take(all_syms: list[str], k: int) -> list[str]:
    """The next k symbols for the pairwise pass, rotating. Never the same slice twice running."""
    try:
        pos = int(json.loads(_CURSOR.read_text("utf-8")).get("pos") or 0)
    except (OSError, ValueError, AttributeError):
        pos = 0
    n = len(all_syms)
    if n == 0:
        return []
    take = [all_syms[(pos + i) % n] for i in range(min(k, n))]
    try:
        _CURSOR.parent.mkdir(parents=True, exist_ok=True)
        _CURSOR.write_text(json.dumps({"pos": (pos + len(take)) % n,
                                       "of": n, "at": datetime.now(UTC).isoformat()}), "utf-8")
    except OSError:
        pass
    return take


def scan(symbols: list[str] | None = None, *, limit: int | None = None) -> dict[str, Any]:
    """Scan the tradeable universe for conditional structure. Emits anomalies, never candidates.

    EVERY SYMBOL, EVERY RUN. This took `files[:40]` on an alphabetically sorted list, so it
    scanned 40 of 251 symbols -- 3M, Accenture, ADAUSD, Adobe ... AUDCAD, AUDCHF, AUDHUF -- and
    never touched the other 211. Every result it produced was dominated by AUD crosses, and that
    was not the market's structure, it was the slice's: exotic crosses with strong session effects
    happen to sort early. A discovery engine that only ever looks at the front of the alphabet
    reports the alphabet, and every downstream count -- trials, mechanism mix, family yield --
    inherits that bias while looking like a measurement of the universe.

    `limit` is now None by default and exists only for tests. The pairwise pass, whose cost is
    quadratic, rotates through the universe on a cursor instead.
    """
    files = sorted(_BARS.glob("*.parquet"))
    if symbols:
        want = {s.upper() for s in symbols}
        files = [f for f in files
                 if (f.stem.rpartition("_")[0] or f.stem).upper() in want]
    if limit is not None:
        files = files[:limit]

    rows: list[dict[str, Any]] = []
    frames: dict[str, pd.DataFrame] = {}
    trials = 0
    scanned, skipped = [], []
    all_syms = [f.stem.replace("_H1", "") for f in files]
    scan_want = _cursor_take(all_syms, _SCAN_PER_RUN)
    if symbols is None and limit is None:
        want = set(scan_want)
        files = [f for f in files if f.stem.replace("_H1", "") in want]
    cross_want = set(scan_want[:_CROSS_FRAMES])
    for f in files:
        sym = f.stem.replace("_H1", "")
        try:
            df = pd.read_parquet(f, columns=["open", "high", "low", "close"])
        except Exception as exc:
            skipped.append({"symbol": sym, "why": f"{type(exc).__name__}: {exc}"})
            continue
        found, t = scan_symbol(sym, df)
        trials += t
        scanned.append(sym)
        # TRIALS ARE PER-SYMBOL, NOT GLOBAL, AND THE DIFFERENCE IS NOT COSMETIC. Deflation charges
        # a candidate for the width of the search THAT COULD HAVE PRODUCED IT. Every cell here is
        # evaluated independently and reported on its own merits -- there is no global tournament
        # picking one winner -- so a EURUSD anomaly competed against EURUSD's own 9,288 cells, not
        # against all 2.3M in the universe. Charging the global total would over-deflate by two
        # orders of magnitude and no honest candidate would ever clear gate 3, which is as wrong
        # as under-counting and fails in the direction that looks rigorous.
        for a in found:
            row = a.as_row()
            row["selection_trials"] = t
            rows.append(row)
        # HOLD ONLY WHAT THE PAIRWISE PASS WILL USE. Retaining all 251 frames would hold several
        # GB on a 3.8GB swapless box; the single-symbol scan above already ran on every one.
        if sym in cross_want:
            frames[sym] = df

    # CROSS-SECTIONAL PASS. The single-symbol scan above finds edges that share a driver; this
    # finds edges that live between instruments, which is the class the family cap is starved of.
    cross_rows, cross_trials = scan_cross_section(frames)
    rows.extend(cross_rows)
    trials += cross_trials

    rows.sort(key=lambda r: -abs(float(r["t_stat"])))
    report = {
        "scanned_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "symbols_scanned": len(scanned), "symbols_skipped": skipped,
        "cross_sectional_anomalies": len(cross_rows), "cross_sectional_trials": cross_trials,
        "cross_sectional_symbols": sorted(cross_want),
        "universe_coverage": {
            "symbols_with_bars": len(all_syms), "scanned": len(scanned),
            "rotating_per_run": _SCAN_PER_RUN,
            "note": ("the cursor advances every run so the whole universe is covered across a "
                     "day. No symbol is excluded -- only deferred. The previous behaviour took "
                     "the first 40 names ALPHABETICALLY and never touched the other 211."),
        },
        "trials": trials,
        "anomalies": rows,
        "min_n": MIN_N, "report_t": REPORT_T,
        "honesty": {
            "trials_counted": trials,
            "why": ("every (symbol, condition, horizon) cell evaluated is counted and carried, so "
                    "deflation downstream charges the real width of this search rather than the "
                    "flattering subset that survived the reporting floor"),
            "report_t_is_not_a_gate": ("REPORT_T only decides what reaches the naming queue. It "
                                       "sets no bar: the canonical ten gates remain the only "
                                       "arbiter and nothing here competes with them"),
            "unnamed": ("every row is mechanism_status=UNNAMED. An anomaly is an observation; "
                        "turning one into a candidate without a named, falsifiable cause is the "
                        "prose-to-family guessing the compiler refuses"),
        },
    }
    _OUT.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%d_%H%M")
    (_OUT / f"anomalies_{stamp}.json").write_text(
        json.dumps(report, indent=1, default=str), encoding="utf-8")
    return report


if __name__ == "__main__":
    r = scan()
    print(f"anomaly miner: {r['symbols_scanned']} symbol(s), {r['trials']:,} cells evaluated, "
          f"{len(r['anomalies'])} reportable")
    for row in r["anomalies"][:12]:
        # Two row shapes: single-symbol rows carry mean_bp, lead-lag rows carry corr. Printing
        # one shape's key on the other is how a KeyError ends a run that had already done the work.
        effect = (f"{row['mean_bp']:+8.1f}bp" if "mean_bp" in row
                  else f"corr {row.get('corr', 0):+7.3f}")
        against = f" vs {row['against']}" if row.get("against") else ""
        print(f"   |t|={abs(row['t_stat']):5.1f}  {row['symbol']:9s}{against:11s} "
              f"{row['condition']:26s} h={row['horizon']:2d} n={row['n']:6d}  {effect}")

```

### libs\research\experiment_graph.py
```python
"""THE EXPERIMENT MEMORY GRAPH -- not result storage. What has never been tried, as a query.

THE PRINCIPAL (RD-Agent closure, item 16): an experiment memory graph holding parents, children,
failed assumptions, model, data, representation, regime and verdict per experiment, answering
*"what has never been tried from this surviving mechanism?"* as a FIRST-CLASS QUERY that the
proposers read.

WHY A GRAPH AND NOT A RESULTS TABLE. The desk already stores results: `research_candidates` carries
verdicts, `trials_ledger` carries the charged trials, the shadow states carry forward evidence.
What none of them can answer is the question above, because a result table is indexed by what WAS
run. The interesting quantity is the COMPLEMENT: from a mechanism that survived on EURUSD at H1 in
a high-volatility regime, the desk has never tried it at M15, never on AUDJPY, never with a rank
representation, never under a trending regime -- and the proposer that would have suggested those
has no way to know which of them are new. An adjacent-possible query needs the graph.

IT LIVES IN THE REGISTRY, NEVER BESIDE IT. The node table is `experiments` (declared in
`libs.moat.registry.MOAT_TABLES`, created by the registry's own `_evolve`); the edges are the
registry's `provenance` DAG with the node kind `experiment`; the verdicts are read back from
`research_candidates` and `trials_ledger`. This module adds no store of its own -- if it needs a
column it is added to the registry's table through the EXTENSIONS mechanism.

THE AXIS DOMAINS ARE MEASURED, NOT INVENTED. `never_tried` enumerates over the axis values THIS
DESK HAS ACTUALLY USED somewhere in the graph (every model it has run, every representation it has
built, every chart, regime, session and horizon it has tested), because an untried combination of
values the desk cannot produce is not an opportunity, it is a typo. An axis with no observed values
reports UNMEASURED and is dropped from the product rather than silently contributing one blank.

    from libs.research import experiment_graph as G
    G.upsert(spec)                                  # a node, and its lineage edges
    G.record_verdict(exp_id, "SURVIVED", ...)       # verdict + failed assumptions
    G.never_tried(mechanism="carry_unwind", axes=("model", "chart"))   # the frontier query
    G.refresh()                                     # statuses and forward/live numbers, from the
                                                    # registry's own rows -- never re-measured
"""
from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterable, Mapping, Sequence
from datetime import UTC, datetime
from itertools import product
from typing import Any

from libs.moat import registry
from libs.research.experiment_spec import ExperimentSpec

#: The axes an experiment is placed on. These are the columns `never_tried` takes its product
#: over; each one is a real column of the `experiments` table so the query is a GROUP BY.
AXES: tuple[str, ...] = ("model", "representation", "chart", "horizon", "regime", "session",
                         "symbol", "target")

#: Which column answers an axis. `symbol` is the first symbol of the spec's instrument list,
#: stored denormalised in `symbols_json`, so it is handled by the reader rather than SQL.
_AXIS_COLUMN: dict[str, str] = {a: a for a in AXES if a != "symbol"}

#: A verdict is one of these. UNJUDGED is a state, not an absence: an experiment that has never
#: been judged is a different thing from one judged and rejected, and the frontier query counts
#: only JUDGED work as "tried" when asked to.
VERDICTS: tuple[str, ...] = ("UNJUDGED", "SURVIVED", "REJECTED", "BLOCKED", "UNMEASURED")


def _now() -> str:
    return datetime.now(tz=UTC).isoformat(timespec="seconds")


def _j(obj: Any) -> str | None:
    return None if obj is None else json.dumps(obj, sort_keys=True, default=str)


def _loads(value: Any) -> Any:
    if value in (None, "", "None"):
        return None
    if isinstance(value, (list, dict)):
        return value
    try:
        return json.loads(str(value))
    except ValueError:
        return value


def _rows(cur: sqlite3.Cursor) -> list[dict[str, Any]]:
    return [dict(r) for r in cur.fetchall()]


# ------------------------------------------------------------------------------------ writers
def upsert(spec: ExperimentSpec, *, candidate_id: str = "", mechanism_id: str = "",
           conn: sqlite3.Connection | None = None) -> tuple[str, bool]:
    """Write one experiment node and its lineage edges. Returns `(experiment_id, created)`.

    An experiment already present is UPDATED in place (the spec may have been enriched with a
    representation or a snapshot since), never duplicated: identity is `experiment_id`, and the
    content identity `spec_hash` rides beside it so two ids carrying the same content can be
    found by the never-tried query without either being deleted.
    """
    c = conn or registry.connect()
    try:
        snap = spec.data_snapshot.resolved()
        rec: dict[str, Any] = {
            "experiment_id": spec.experiment_id, "updated_at": _now(), "kind": spec.kind,
            "spec_hash": spec.spec_hash(), "family": spec.family,
            "symbols_json": _j(list(spec.symbols)), "model": spec.model,
            "representation": spec.representation, "features_json": _j(list(spec.features)),
            "target": spec.target, "horizon": spec.horizon, "chart": spec.chart,
            "regime": spec.regime, "session": spec.session, "mechanism": spec.mechanism,
            "mechanism_id": mechanism_id or _mechanism_key(spec), "method": spec.method,
            "source_id": spec.source, "generator": spec.generator, "origin": spec.origin,
            "discovery_id": spec.discovery_id, "candidate_id": candidate_id,
            "parents_json": _j(list(spec.parents)), "snapshot_hash": snap.snapshot_hash,
            "snapshot_vintage": snap.vintage, "pit_status": snap.pit_status,
            "falsifier": spec.falsifier, "trial_family": spec.trial_family,
            "costs_json": _j(dict(spec.costs)), "novelty_json": _j(dict(spec.novelty_axes)),
            "status": spec.status, "spec_json": _j(spec.to_dict()),
        }
        existing = c.execute("SELECT experiment_id FROM experiments WHERE experiment_id=?",
                             (spec.experiment_id,)).fetchone()
        if existing is not None:
            c.execute("UPDATE experiments SET " + ", ".join(f"{k}=?" for k in rec)
                      + " WHERE experiment_id=?",                          # noqa: S608
                      [*rec.values(), spec.experiment_id])
            created = False
        else:
            rec["created_at"] = _now()
            rec["verdict"] = "UNJUDGED"
            keys = list(rec)
            c.execute(f'INSERT INTO experiments({",".join(keys)}) '
                      f'VALUES({",".join("?" * len(keys))})', [rec[k] for k in keys])
            created = True
        for p in spec.parents:
            registry.link("experiment", p, "experiment", spec.experiment_id, "derived", conn=c)
        if spec.discovery_id:
            registry.link("discovery", spec.discovery_id, "experiment", spec.experiment_id,
                          "compiled", conn=c)
        if spec.source:
            registry.link("source", spec.source, "experiment", spec.experiment_id, "suggested",
                          conn=c)
        if candidate_id:
            registry.link("experiment", spec.experiment_id, "cell", candidate_id, "compiled",
                          conn=c)
        c.commit()
        return spec.experiment_id, created
    finally:
        if conn is None:
            c.close()


def record_verdict(experiment_id: str, verdict: str, *, failed_assumptions: Sequence[str] = (),
                   forward_r: float | None = None, live_delta_elogw: float | None = None,
                   compute_s: float | None = None, status: str = "",
                   conn: sqlite3.Connection | None = None) -> bool:
    """A completed experiment's verdict, and the ASSUMPTIONS that failed with it.

    The failed assumptions are the part no result table holds and the part the next proposer most
    needs: "this mechanism does not survive costs at M15" is a different lesson from "this
    mechanism does not exist", and only the first one leaves H1 worth trying.
    """
    if verdict not in VERDICTS:
        raise ValueError(f"verdict {verdict!r} is not one of {VERDICTS}")
    c = conn or registry.connect()
    try:
        sets: dict[str, Any] = {"verdict": verdict, "verdict_at": _now(), "updated_at": _now(),
                                "failed_assumptions_json": _j(list(failed_assumptions))}
        if status:
            sets["status"] = status
        for k, v in (("forward_r", forward_r), ("live_delta_elogw", live_delta_elogw),
                     ("compute_s", compute_s)):
            if v is not None:
                sets[k] = float(v)
        cur = c.execute("UPDATE experiments SET " + ", ".join(f"{k}=?" for k in sets)
                        + " WHERE experiment_id=?", [*sets.values(), experiment_id])  # noqa: S608
        c.commit()
        return cur.rowcount > 0
    finally:
        if conn is None:
            c.close()


def _mechanism_key(spec: ExperimentSpec) -> str:
    """The grouping key for "this mechanism". The mechanism sentence when there is one, else the
    family: the question "what has never been tried from this surviving mechanism" must still be
    answerable for a row whose mechanism was never written in prose."""
    return (spec.mechanism or spec.family or spec.kind).strip()[:160]


# ------------------------------------------------------------------------------------ readers
def node(experiment_id: str, *, conn: sqlite3.Connection | None = None) -> dict[str, Any] | None:
    c = conn or registry.connect()
    try:
        row = c.execute("SELECT * FROM experiments WHERE experiment_id=?",
                        (experiment_id,)).fetchone()
        return None if row is None else dict(row)
    finally:
        if conn is None:
            c.close()


def experiments(*, mechanism: str = "", status: str = "", verdict: str = "", kind: str = "",
                limit: int = 5000,
                conn: sqlite3.Connection | None = None) -> list[dict[str, Any]]:
    c = conn or registry.connect()
    try:
        q = "SELECT * FROM experiments WHERE 1=1"
        args: list[Any] = []
        for col, val in (("mechanism_id", mechanism), ("status", status),
                         ("verdict", verdict), ("kind", kind)):
            if val:
                q += f" AND {col}=?"
                args.append(val)
        q += " ORDER BY created_at DESC LIMIT ?"
        args.append(limit)
        return _rows(c.execute(q, args))
    finally:
        if conn is None:
            c.close()


def parents_of(experiment_id: str, *,
               conn: sqlite3.Connection | None = None) -> list[dict[str, Any]]:
    return registry.provenance_of("experiment", experiment_id, depth=6, conn=conn)


def children_of(experiment_id: str, *,
                conn: sqlite3.Connection | None = None) -> list[dict[str, Any]]:
    return registry.descendants_of("experiment", experiment_id, depth=6, conn=conn)


def _axis_values(rows: Iterable[Mapping[str, Any]], axis: str) -> list[str]:
    seen: dict[str, int] = {}
    for r in rows:
        if axis == "symbol":
            for s in (_loads(r.get("symbols_json")) or []):
                if str(s):
                    seen[str(s)] = seen.get(str(s), 0) + 1
            continue
        v = r.get(_AXIS_COLUMN.get(axis, axis))
        if v not in (None, "", "None"):
            seen[str(v)] = seen.get(str(v), 0) + 1
    return sorted(seen, key=lambda k: (-seen[k], k))


def _tried_key(row: Mapping[str, Any], axes: Sequence[str]) -> list[tuple[str, ...]]:
    """The axis tuples this row occupies. A row with several symbols occupies several cells."""
    per_axis: list[list[str]] = []
    for a in axes:
        if a == "symbol":
            syms = [str(s) for s in (_loads(row.get("symbols_json")) or []) if str(s)]
            per_axis.append(syms or [""])
        else:
            per_axis.append([str(row.get(_AXIS_COLUMN.get(a, a)) or "")])
    return [tuple(t) for t in product(*per_axis)]


def never_tried(*, mechanism: str = "", axes: Sequence[str] = ("model", "chart", "regime"),
                only_judged: bool = False, limit: int = 200,
                domain_from: str = "graph",
                conn: sqlite3.Connection | None = None) -> dict[str, Any]:
    """THE FIRST-CLASS QUERY: what has this desk never tried from this mechanism?

    `mechanism` is a mechanism key (`mechanism_id` on the node, which is the mechanism sentence or
    the family). `axes` names the product to enumerate. `domain_from` says where the axis values
    come from: `graph` (every value the desk has used anywhere -- the adjacent possible) or
    `mechanism` (only values this mechanism itself has used -- a narrower, cheaper frontier).

    Returns the untried cells with the tried ones counted beside them, plus an `unmeasured` list
    naming any axis with no observed values -- which is a finding, not a zero: an axis the desk
    has never recorded a single value for cannot be enumerated and is DROPPED from the product
    rather than contributing a blank that would make every cell look untried.
    """
    bad = [a for a in axes if a not in AXES]
    if bad:
        raise ValueError(f"unknown axes {bad}; known axes are {AXES}")
    c = conn or registry.connect()
    try:
        all_rows = _rows(c.execute("SELECT * FROM experiments LIMIT 20000"))
        mine = [r for r in all_rows if not mechanism or str(r.get("mechanism_id")) == mechanism]
        if only_judged:
            mine = [r for r in mine if str(r.get("verdict") or "UNJUDGED") != "UNJUDGED"]
        domain_rows = mine if domain_from == "mechanism" else all_rows
        domains: dict[str, list[str]] = {}
        unmeasured: list[str] = []
        for a in axes:
            vals = _axis_values(domain_rows, a)
            if vals:
                domains[a] = vals
            else:
                unmeasured.append(a)
        live_axes = [a for a in axes if a in domains]
        tried: dict[tuple[str, ...], int] = {}
        for r in mine:
            for key in _tried_key(r, live_axes):
                tried[key] = tried.get(key, 0) + 1
        untried: list[dict[str, str]] = []
        n_cells = 0
        for combo in product(*(domains[a] for a in live_axes)) if live_axes else ():
            n_cells += 1
            if combo not in tried:
                if len(untried) < limit:
                    untried.append(dict(zip(live_axes, combo, strict=True)))
        survivors = sum(1 for r in mine if str(r.get("verdict")) == "SURVIVED")
        return {
            "mechanism": mechanism or "(every mechanism)",
            "axes": list(live_axes),
            "unmeasured_axes": unmeasured,
            "domain_from": domain_from,
            "n_experiments": len(mine), "n_survivors": survivors,
            "n_cells": n_cells, "n_tried": len(tried),
            "n_untried": max(0, n_cells - len(tried)),
            "coverage": None if n_cells == 0 else round(len(tried) / n_cells, 6),
            "untried": untried,
            "truncated": max(0, (n_cells - len(tried)) - len(untried)),
            "basis": ("axis domains are the values this desk has ACTUALLY used; an axis with no "
                      "observed value is reported unmeasured and dropped from the product"),
        }
    finally:
        if conn is None:
            c.close()


def surviving_mechanisms(*, limit: int = 50,
                         conn: sqlite3.Connection | None = None) -> list[dict[str, Any]]:
    """Mechanisms with at least one SURVIVED experiment, newest evidence first. This is what a
    proposer iterates over before calling `never_tried` on each."""
    c = conn or registry.connect()
    try:
        return _rows(c.execute(
            "SELECT mechanism_id, COUNT(*) AS n, "
            " SUM(CASE WHEN verdict='SURVIVED' THEN 1 ELSE 0 END) AS survivors, "
            " MAX(verdict_at) AS last_verdict_at "
            "FROM experiments WHERE mechanism_id IS NOT NULL AND mechanism_id<>'' "
            "GROUP BY mechanism_id HAVING survivors > 0 "
            "ORDER BY survivors DESC, last_verdict_at DESC LIMIT ?", (limit,)))
    finally:
        if conn is None:
            c.close()


def failed_assumptions(*, mechanism: str = "", limit: int = 200,
                       conn: sqlite3.Connection | None = None) -> dict[str, int]:
    """What has failed, and how often -- the negative knowledge the proposers must not re-spend."""
    out: dict[str, int] = {}
    for r in experiments(mechanism=mechanism, limit=limit, conn=conn):
        for a in (_loads(r.get("failed_assumptions_json")) or []):
            out[str(a)] = out.get(str(a), 0) + 1
    return dict(sorted(out.items(), key=lambda kv: -kv[1]))


# ------------------------------------------------------------------------------------ refresh
#: How a registry candidate status maps onto an experiment verdict. `donated` and `queued` are
#: not verdicts: an experiment waiting in the queue is UNJUDGED, which is what makes the
#: never-tried query honest.
_VERDICT_OF_STATUS: dict[str, str] = {
    "survived": "SURVIVED", "rejected": "REJECTED", "judged": "JUDGED",
    "blocked": "BLOCKED", "live": "SURVIVED", "forward": "SURVIVED",
}


def refresh(*, limit: int = 20000, conn: sqlite3.Connection | None = None) -> dict[str, Any]:
    """Pull each experiment's status and verdict from the registry rows that OWN them.

    Nothing is re-measured here: `research_candidates.status`, `survived` and `rejection_reason`
    are the gauntlet's own record, and the graph copies them onto the node so the frontier query
    does not need a join per cell. An experiment whose candidate has vanished keeps its last
    verdict and is counted in `orphans` -- a node with no cell is a real defect, not a zero.
    """
    c = conn or registry.connect()
    try:
        nodes = _rows(c.execute("SELECT experiment_id, candidate_id, verdict, status FROM "
                                "experiments LIMIT ?", (limit,)))
        updated = orphans = judged = survived = 0
        for n in nodes:
            cid = str(n.get("candidate_id") or "")
            if not cid:
                orphans += 1
                continue
            row = c.execute("SELECT status, survived, rejection_reason, terminal_gate, "
                            "failure_class FROM research_candidates WHERE id=? OR donated_cell=?",
                            (cid, cid)).fetchone()
            if row is None:
                orphans += 1
                continue
            status = str(row["status"] or "")
            verdict = _VERDICT_OF_STATUS.get(status.lower(), "UNJUDGED")
            if int(row["survived"] or 0) == 1:
                verdict = "SURVIVED"
            elif row["rejection_reason"]:
                verdict = "REJECTED"
            if verdict == "JUDGED":
                verdict = "REJECTED" if row["rejection_reason"] else "UNJUDGED"
            fails: list[str] = []
            for key in ("rejection_reason", "terminal_gate", "failure_class"):
                v = row[key]
                if v:
                    fails.append(f"{key}:{v}")
            if verdict != str(n.get("verdict") or "UNJUDGED") or status != str(n.get("status")):
                c.execute("UPDATE experiments SET verdict=?, status=?, verdict_at=?, "
                          "failed_assumptions_json=?, updated_at=? WHERE experiment_id=?",
                          (verdict, status.upper() or str(n.get("status") or "PROPOSED"),
                           _now(), _j(fails), _now(), n["experiment_id"]))
                updated += 1
            judged += int(verdict != "UNJUDGED")
            survived += int(verdict == "SURVIVED")
        c.commit()
        return {"nodes": len(nodes), "updated": updated, "orphans": orphans,
                "judged": judged, "survived": survived}
    finally:
        if conn is None:
            c.close()


def census(*, conn: sqlite3.Connection | None = None) -> dict[str, Any]:
    """The graph in one dict: nodes, kinds, verdicts, edges and the axis domains it can search."""
    c = conn or registry.connect()
    try:
        n = int(c.execute("SELECT COUNT(*) AS n FROM experiments").fetchone()["n"])
        by_kind = {str(r["kind"] or "?"): int(r["n"]) for r in c.execute(
            "SELECT kind, COUNT(*) AS n FROM experiments GROUP BY kind")}
        by_verdict = {str(r["verdict"] or "UNJUDGED"): int(r["n"]) for r in c.execute(
            "SELECT verdict, COUNT(*) AS n FROM experiments GROUP BY verdict")}
        edges = int(c.execute("SELECT COUNT(*) AS n FROM provenance WHERE from_kind='experiment'"
                              " OR to_kind='experiment'").fetchone()["n"])
        rows = _rows(c.execute("SELECT * FROM experiments LIMIT 20000"))
        domains = {a: len(_axis_values(rows, a)) for a in AXES}
        return {"nodes": n, "by_kind": by_kind, "by_verdict": by_verdict, "edges": edges,
                "axis_domain_sizes": domains,
                "mechanisms": int(c.execute(
                    "SELECT COUNT(DISTINCT mechanism_id) AS n FROM experiments").fetchone()["n"])}
    finally:
        if conn is None:
            c.close()

```

### libs\research\feed_observatory.py
```python
"""THE FEED / CLOCK / INFORMATION-PROPAGATION OBSERVATORY -- market data as a sensor network.

WHY. Every organ on this desk reads a price as if it were the market. It is not: it is the last
message a chain of clocks let through, and the chain has five clocks that are never the same
instant -- the SOURCE event (the instant the world changed), the EXCHANGE stamp (the venue's own
`time_msc`), the VENDOR receipt (the terminal's), the LOCAL receipt (this box's `recv_utc`) and,
for anything reconstructed across venues, an IMPLIED time that is only as fresh as its stalest
leg. `latency_lab` measures what the desk's OWN order takes to travel; this module measures what
the desk's PICTURE of the market is worth at the instant it decides -- and which instrument's
move can be said to precede which, given that the clocks cannot resolve every lag.

WHAT IS MEASURED, and from what:

    latency_distribution     local - exchange, per feed; negatives KEPT and counted (a broker
                             clock ahead of this box is a fact about the clocks, not noise)
    sequence_continuity      inversions / duplicates / dropped numbers where a sequence exists;
                             MT5 ticks carry none, so drops there are a PROXY and say so
    staleness_probability    P(the quote is older than its age) from the feed's own in-session
                             inter-arrival gaps -- a survival function, never a threshold
    reference_consistency    two views of one instrument (tape mid vs bar close) at every
                             candidate lag: the best lag IS the clock offset, the residual is
                             the disagreement in bps
    feed_health              P(observed market is trustworthy | all feeds): per feed a PRODUCT
                             of component probabilities, across feeds a geometric mean over the
                             feeds that are in session -- a closed market is EXCLUDED, never 0
    propagation_graph        which instrument's move can precede which at what lag: an edge at
                             lag L is causally ADMISSIBLE only when L exceeds what the two
                             clocks can jointly resolve (|offset_a - offset_b| + jitter_a +
                             jitter_b); below that the ordering is not identifiable and the
                             graph REFUSES the edge rather than ranking it
    timing_fragility         a signal re-measured under realistic timing corruption (jitter,
                             dropped messages, stale quotes, sequence inversions) at the
                             MEASURED noise level and at 10x and 100x; a candidate whose edge
                             halves at the measured level is TIMING_FRAGILE

EVERYTHING HERE IS PURE. No file, no clock, no desk path: the organ (`desks/mt5/research/
feed_clock_lab.py`) reads the tape and the bars and hands arrays in, so every function can be
tested on a planted feed. UNMEASURED is a value in every return (L1.28a): a feed with too few
ticks to establish a gap distribution has no staleness probability, and saying so is the
measurement.

IT ROUTES AND INFORMS; IT NEVER SIZES. Feed health is an INPUT to entry timing and to research
routing (GROWTH_GOVERNANCE Rule 1: nothing here is a cap, a veto or a shrink).
"""
from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

import numpy as np
from numpy.typing import NDArray

FloatArray = NDArray[np.float64]

UNMEASURED = "UNMEASURED"
MEASURED = "MEASURED"
#: The five clocks, in the order a message travels. `implied` is not on the path: it is a
#: reconstruction and is carried apart so it can never be mistaken for a receipt.
CLOCKS: tuple[str, ...] = ("source_event", "exchange", "vendor_receipt", "local_receipt",
                           "implied")
#: Below this many observations a distribution is a sample, and a probability is not one.
MIN_OBS = 30
#: A feed whose age exceeds this multiple of its own p99 in-session gap is not stale, it is
#: CLOSED (or the recorder is down) -- excluded from health by name rather than scored 0.
CLOSED_GAP_MULTIPLE = 3.0
#: Floor on the closed threshold so a thin feed is not declared closed by one quiet minute.
CLOSED_FLOOR_MS = 300_000.0
#: A silence burst this many times the median gap is the drop PROXY on a feed without sequence
#: numbers: it is where dropped messages would hide, and it is named a proxy in every output.
BURST_MULTIPLE = 10.0
#: An edge keeps this share of its clean value or it is fragile.
SURVIVAL_FRACTION = 0.5
#: The corruption ladder: measured noise, then an order of magnitude and two above it.
MULTIPLIERS: tuple[float, ...] = (1.0, 10.0, 100.0)
HEALTH_RULE = ("per feed: product of component probabilities (freshness, continuity, "
               "completeness, latency, reference); across feeds: geometric mean over the feeds "
               "in session; a closed feed is EXCLUDED, an unmeasured one is COUNTED and named")
GRAPH_RULE = ("an edge a->b at lag L is admissible only when L >= |offset_a - offset_b| + "
              "jitter_a + jitter_b, and both feeds are in session; below the clocks' joint "
              "resolution the ordering is not identifiable and the edge is REFUSED")


# ------------------------------------------------------------------------------------- stamps
@dataclass(frozen=True)
class FeedStamp:
    """One message's five clocks, in epoch milliseconds; None is UNMEASURED, never zero."""

    exchange_ms: float | None = None
    local_ms: float | None = None
    source_ms: float | None = None
    vendor_ms: float | None = None
    implied_ms: float | None = None
    seq: int | None = None


def stamp_coverage(stamps: Sequence[FeedStamp]) -> dict[str, dict[str, Any]]:
    """Which clocks a feed actually carries. A clock no message carries is UNMEASURED by name."""
    fields = {"source_event": "source_ms", "exchange": "exchange_ms",
              "vendor_receipt": "vendor_ms", "local_receipt": "local_ms", "implied": "implied_ms"}
    total = len(stamps)
    out: dict[str, dict[str, Any]] = {}
    for clock, attr in fields.items():
        n = sum(1 for s in stamps if getattr(s, attr) is not None)
        out[clock] = {"n": n, "of": total, "status": MEASURED if n else UNMEASURED}
    return out


def implied_time(leg_times: Sequence[float | None]) -> float | None:
    """A cross-venue reconstruction is as fresh as its STALEST leg; any missing leg makes it
    UNMEASURED. It is returned for the `implied` clock and must never be merged into a receipt."""
    if not leg_times or any(t is None for t in leg_times):
        return None
    return float(max(float(t) for t in leg_times if t is not None))


def _finite(values: Sequence[float] | FloatArray) -> FloatArray:
    arr = np.asarray(values, dtype=float).ravel()
    out: FloatArray = arr[np.isfinite(arr)]
    return out


def quantiles(values: Sequence[float] | FloatArray) -> dict[str, Any]:
    arr = _finite(values)
    if arr.size == 0:
        return {"status": UNMEASURED, "n": 0}
    p50, p90, p99 = (float(np.percentile(arr, q)) for q in (50, 90, 99))
    return {"status": MEASURED if arr.size >= 3 else "SAMPLE", "n": int(arr.size),
            "p50": round(p50, 3), "p90": round(p90, 3), "p99": round(p99, 3),
            "mean": round(float(arr.mean()), 3), "max": round(float(arr.max()), 3)}


# ------------------------------------------------------------------------------ measurements
def latency_distribution(exchange_ms: Sequence[float] | FloatArray,
                         local_ms: Sequence[float] | FloatArray) -> dict[str, Any]:
    """local - exchange per message. Negatives are kept and counted: dropping them would turn a
    clock offset into a flattering delay made of the positive tail."""
    a, b = np.asarray(exchange_ms, dtype=float), np.asarray(local_ms, dtype=float)
    if a.shape != b.shape or a.size == 0:
        return {"status": UNMEASURED, "n": 0, "why": "no paired stamps"}
    delta = b - a
    delta = delta[np.isfinite(delta)]
    if delta.size == 0:
        return {"status": UNMEASURED, "n": 0, "why": "no finite pair"}
    q = quantiles(delta)
    q.update({"n_negative": int((delta < 0).sum()),
              "offset_ms": round(float(np.median(delta)), 3),
              "jitter_ms": round(float(np.percentile(delta, 90) - np.median(delta)), 3)})
    return q


def sequence_continuity(seq: Sequence[float] | FloatArray, *,
                        integer_sequence: bool = False) -> dict[str, Any]:
    """Inversions and duplicates in arrival order; dropped numbers only where a true integer
    sequence exists. Time stamps are NOT sequence numbers: two ticks in one millisecond are a
    duplicate stamp, not a duplicate message, and a feed without numbers cannot count drops."""
    arr = np.asarray(seq, dtype=float).ravel()
    arr = arr[np.isfinite(arr)]
    n = int(arr.size)
    if n < 2:
        return {"status": UNMEASURED, "n": n, "why": "fewer than two messages"}
    d = np.diff(arr)
    inversions, duplicates = int((d < 0).sum()), int((d == 0).sum())
    out: dict[str, Any] = {"status": MEASURED, "n": n, "inversions": inversions,
                           "duplicates": duplicates,
                           "inversion_rate": round(inversions / (n - 1), 6)}
    if integer_sequence:
        dropped = int(np.clip(d - 1, 0, None).sum())
        out.update({"dropped": dropped, "drop_rate": round(dropped / (dropped + n), 6)})
    else:
        out.update({"dropped": None, "drop_rate": None,
                    "drop_basis": "no sequence numbers on this feed: drops are UNMEASURED here"
                                  " and proxied by silence bursts (see burst_rate)"})
    return out


def burst_rate(gaps_ms: Sequence[float] | FloatArray, *, multiple: float = BURST_MULTIPLE
               ) -> dict[str, Any]:
    """Share of inter-arrival gaps above `multiple` x the median gap: the drop PROXY."""
    g = _finite(gaps_ms)
    g = g[g >= 0]
    if g.size < MIN_OBS:
        return {"status": UNMEASURED, "n": int(g.size), "why": f"fewer than {MIN_OBS} gaps"}
    med = float(np.median(g))
    if med <= 0:
        return {"status": UNMEASURED, "n": int(g.size), "why": "median gap is zero"}
    bursts = int((g > multiple * med).sum())
    return {"status": MEASURED, "n": int(g.size), "median_gap_ms": round(med, 3),
            "bursts": bursts, "rate": round(bursts / g.size, 6), "multiple": multiple,
            "basis": "PROXY for dropped messages on a feed without sequence numbers"}


def staleness_probability(gaps_ms: Sequence[float] | FloatArray, age_ms: float
                          ) -> float | None:
    """P(a fresher quote was DUE by now) = P(in-session gap <= age), the empirical CDF of the
    feed's own inter-arrival gaps at the quote's current age. A one-second-old quote on a feed
    that ticks every two seconds is not stale (0.0); a five-second-old one is (1.0). None
    below MIN_OBS."""
    g = _finite(gaps_ms)
    g = g[g >= 0]
    if g.size < MIN_OBS or not math.isfinite(age_ms) or age_ms < 0:
        return None
    return float(np.mean(g <= age_ms))


def closed_threshold_ms(gaps_ms: Sequence[float] | FloatArray) -> float | None:
    """The silence beyond which a feed is CLOSED rather than stale: a multiple of its own p99 gap,
    floored. None when the gaps cannot establish it."""
    g = _finite(gaps_ms)
    g = g[g >= 0]
    if g.size < MIN_OBS:
        return None
    return max(CLOSED_FLOOR_MS, CLOSED_GAP_MULTIPLE * float(np.percentile(g, 99)))


def reference_consistency(a_times: Sequence[float] | FloatArray,
                          a_values: Sequence[float] | FloatArray,
                          b_times: Sequence[float] | FloatArray,
                          b_values: Sequence[float] | FloatArray, *,
                          lags_ms: Sequence[float] = (0.0,), min_pairs: int = 10
                          ) -> dict[str, Any]:
    """Two views of one instrument. For each candidate lag, every `a` observation is matched to
    the LAST `b` observation at or before `t_a + lag`; the lag with the smallest median |bps|
    is the measured clock offset between the views and its residual is their disagreement."""
    at, av = np.asarray(a_times, dtype=float), np.asarray(a_values, dtype=float)
    bt, bv = np.asarray(b_times, dtype=float), np.asarray(b_values, dtype=float)
    if at.size == 0 or bt.size == 0 or at.shape != av.shape or bt.shape != bv.shape:
        return {"status": UNMEASURED, "n": 0, "why": "one view is empty"}
    order = np.argsort(bt, kind="stable")
    bt, bv = bt[order], bv[order]
    rows: list[dict[str, Any]] = []
    for lag in lags_ms:
        shifted = at + float(lag)
        idx = np.searchsorted(bt, shifted, side="right") - 1
        # ONLY INSIDE THE REFERENCE'S OWN SPAN. A shifted time past the last `b` observation
        # would silently match that last (stale) value, and a lag that moved more `a` points
        # into the window would win on COUNT rather than agreement -- measured on the box
        # 2026-09-22, where +3 h "won" against a truncated tape day with 16.8 bps residual.
        keep = (idx >= 0) & (shifted <= bt[-1])
        if int(keep.sum()) < min_pairs:
            rows.append({"lag_ms": float(lag), "status": UNMEASURED, "n": int(keep.sum())})
            continue
        ref = bv[idx[keep]]
        own = av[keep]
        ok = np.isfinite(ref) & np.isfinite(own) & (ref != 0)
        if int(ok.sum()) < min_pairs:
            rows.append({"lag_ms": float(lag), "status": UNMEASURED, "n": int(ok.sum())})
            continue
        bps = (own[ok] - ref[ok]) / ref[ok] * 1e4
        rows.append({"lag_ms": float(lag), "status": MEASURED, "n": int(ok.sum()),
                     "median_abs_bps": round(float(np.median(np.abs(bps))), 4),
                     "p90_abs_bps": round(float(np.percentile(np.abs(bps), 90)), 4),
                     "median_bps": round(float(np.median(bps)), 4)})
    measured = [r for r in rows if r["status"] == MEASURED]
    if not measured:
        return {"status": UNMEASURED, "n": 0, "lags": rows, "why": "no lag pairs enough rows"}
    best = min(measured, key=lambda r: float(r["median_abs_bps"]))
    at0 = next((r for r in measured if r["lag_ms"] == 0.0), None)
    return {"status": MEASURED, "n": int(best["n"]), "best_lag_ms": float(best["lag_ms"]),
            "median_abs_bps_at_best": float(best["median_abs_bps"]),
            "median_abs_bps_at_zero": None if at0 is None else float(at0["median_abs_bps"]),
            "lags": rows}


# ---------------------------------------------------------------------------------- health
@dataclass(frozen=True)
class FeedClock:
    """One feed's measured clock. Every probability is in [0, 1]; None is UNMEASURED."""

    instrument: str
    n: int
    offset_ms: float | None = None        # median(local - exchange)
    jitter_ms: float | None = None        # p90 - p50 of that delay
    inversion_rate: float | None = None
    drop_prob: float | None = None        # burst proxy on MT5; true drops where a sequence exists
    stale_prob: float | None = None       # P(a fresher quote was due by now)
    repeat_rate: float | None = None      # share of messages repeating the previous value
    p_latency_ok: float | None = None     # P(delay <= the caller's tolerance)
    reference_ok: float | None = None     # 1 - clipped(median |bps| / tolerance)
    in_session: bool = True
    status: str = MEASURED
    why: str = ""


def _p(value: float | None) -> float | None:
    if value is None or not math.isfinite(value):
        return None
    return float(min(1.0, max(0.0, value)))


def feed_component_health(clock: FeedClock) -> dict[str, float | None]:
    """The five components of one feed's trustworthiness, each a probability or None."""
    return {"freshness": None if clock.stale_prob is None else _p(1.0 - clock.stale_prob),
            "continuity": (None if clock.inversion_rate is None
                           else _p(1.0 - clock.inversion_rate)),
            "completeness": None if clock.drop_prob is None else _p(1.0 - clock.drop_prob),
            "latency": _p(clock.p_latency_ok),
            "reference": _p(clock.reference_ok)}


def feed_trust(clock: FeedClock) -> dict[str, Any]:
    """P(this feed is trustworthy) = product of its MEASURED components; the unmeasured ones are
    listed rather than imputed as 1. A feed with no measured component is UNMEASURED."""
    comps = feed_component_health(clock)
    have = {k: v for k, v in comps.items() if v is not None}
    missing = sorted(k for k, v in comps.items() if v is None)
    if not clock.in_session:
        return {"status": "CLOSED", "p_trustworthy": None, "components": comps,
                "unmeasured_components": missing, "why": clock.why or "feed is out of session"}
    if not have:
        return {"status": UNMEASURED, "p_trustworthy": None, "components": comps,
                "unmeasured_components": missing, "why": clock.why or "no measured component"}
    p = 1.0
    for v in have.values():
        p *= v
    return {"status": MEASURED if not missing else "PARTIAL", "p_trustworthy": round(p, 6),
            "components": comps, "unmeasured_components": missing,
            "why": clock.why or ("every component measured" if not missing
                                 else f"unmeasured: {', '.join(missing)} (not imputed)")}


def feed_health(now_ms: float, clocks: Mapping[str, FeedClock]) -> dict[str, Any]:
    """P(observed market is trustworthy | all feeds), with the rule that produced it.

    The market-level number is the GEOMETRIC MEAN over feeds in session with a measured or
    partial trust -- a product would punish breadth (200 good feeds multiply to nothing) and an
    arithmetic mean would hide one dead feed among them. The minimum is published beside it so
    the worst feed is never averaged away.
    """
    per: dict[str, dict[str, Any]] = {}
    logs: list[float] = []
    for name in sorted(clocks):
        row = feed_trust(clocks[name])
        per[name] = row
        p = row.get("p_trustworthy")
        if p is not None and p > 0:
            logs.append(math.log(p))
    measured = {k: v for k, v in per.items() if v.get("p_trustworthy") is not None}
    zeros = sum(1 for v in per.values() if v.get("p_trustworthy") == 0.0)
    market: float | None = None
    if measured:
        market = 0.0 if zeros else float(math.exp(sum(logs) / len(logs)))
    worst = min(((v["p_trustworthy"], k) for k, v in measured.items()), default=None)
    return {"at_ms": float(now_ms), "rule": HEALTH_RULE,
            "status": MEASURED if measured else UNMEASURED,
            "p_market_trustworthy": None if market is None else round(market, 6),
            "worst_feed": None if worst is None else {"instrument": worst[1],
                                                     "p_trustworthy": worst[0]},
            "n_feeds": len(per), "n_in_session": sum(1 for v in per.values()
                                                     if v["status"] != "CLOSED"),
            "n_closed": sum(1 for v in per.values() if v["status"] == "CLOSED"),
            "n_unmeasured": sum(1 for v in per.values() if v["status"] == UNMEASURED),
            "feeds": per}


# ----------------------------------------------------------------------------- propagation
def min_admissible_lag_ms(a: FeedClock, b: FeedClock) -> float | None:
    """The smallest lag at which a->b ordering is identifiable from these two clocks. None when
    either clock's offset or jitter is unmeasured: an unknown clock admits no lag, which is the
    conservative reading and is named as such by `admissible`."""
    if None in (a.offset_ms, a.jitter_ms, b.offset_ms, b.jitter_ms):
        return None
    assert a.offset_ms is not None and b.offset_ms is not None
    assert a.jitter_ms is not None and b.jitter_ms is not None
    return abs(a.offset_ms - b.offset_ms) + abs(a.jitter_ms) + abs(b.jitter_ms)


def admissible(a: FeedClock, b: FeedClock, lag_ms: float) -> tuple[bool, str]:
    """Is 'a moved, then b moved `lag_ms` later' a causally admissible statement?"""
    if not a.in_session or not b.in_session:
        closed = a.instrument if not a.in_session else b.instrument
        return False, f"{closed} is out of session: nothing it did not quote can lead or lag"
    floor = min_admissible_lag_ms(a, b)
    if floor is None:
        return False, ("a clock is UNMEASURED (offset or jitter): an unknown clock admits no"
                       " ordering, which is a verdict and not a permission")
    if lag_ms < floor:
        return False, (f"lag {lag_ms:.0f} ms is below the clocks' joint resolution of"
                       f" {floor:.0f} ms: the ordering is not identifiable, REFUSED")
    return True, f"lag {lag_ms:.0f} ms >= resolution {floor:.0f} ms"


def propagation_graph(clocks: Mapping[str, FeedClock], lags_ms: Sequence[float]
                      ) -> dict[str, Any]:
    """Every ordered pair at every candidate lag, with its admissibility and the reason.

    The graph is a STATEMENT ABOUT THE CLOCKS, not about the instruments: it says which lead-lag
    claims the desk's feeds could even support, so a lead-lag miner reads it BEFORE it fits
    anything. A pair whose smallest admissible lag exceeds every candidate is listed under
    `unresolvable_pairs` -- a finding, not an absence.
    """
    names = sorted(clocks)
    edges: list[dict[str, Any]] = []
    refused = 0
    unresolvable: list[dict[str, Any]] = []
    for src in names:
        for dst in names:
            if src == dst:
                continue
            a, b = clocks[src], clocks[dst]
            floor = min_admissible_lag_ms(a, b)
            any_ok = False
            for lag in lags_ms:
                ok, why = admissible(a, b, float(lag))
                any_ok = any_ok or ok
                refused += int(not ok)
                # The clock-only verdict rides beside the full one, so a closed market (every
                # edge refused for session) still shows which lags the clocks COULD resolve.
                by_clock = floor is not None and float(lag) >= floor
                edges.append({"from": src, "to": dst, "lag_ms": float(lag), "admissible": ok,
                              "resolution_admissible": by_clock,
                              "min_admissible_lag_ms": None if floor is None
                              else round(floor, 3), "why": why})
            if not any_ok:
                unresolvable.append({"from": src, "to": dst,
                                     "min_admissible_lag_ms": None if floor is None
                                     else round(floor, 3)})
    return {"rule": GRAPH_RULE, "n_nodes": len(names), "lags_ms": [float(x) for x in lags_ms],
            "n_edges": len(edges), "n_admissible": sum(1 for e in edges if e["admissible"]),
            "n_resolution_admissible": sum(1 for e in edges if e["resolution_admissible"]),
            "n_refused": refused, "unresolvable_pairs": unresolvable, "edges": edges}


# ------------------------------------------------------------------------ timing fragility
@dataclass(frozen=True)
class TimingNoise:
    """A realistic timing-corruption model, in the units the feed was measured in."""

    jitter_ms: float = 0.0
    drop_prob: float = 0.0
    stale_prob: float = 0.0
    inversion_prob: float = 0.0

    def scaled(self, k: float) -> TimingNoise:
        return TimingNoise(jitter_ms=self.jitter_ms * k,
                           drop_prob=min(0.95, self.drop_prob * k),
                           stale_prob=min(0.95, self.stale_prob * k),
                           inversion_prob=min(0.95, self.inversion_prob * k))

    def row(self) -> dict[str, float]:
        return {"jitter_ms": round(self.jitter_ms, 3), "drop_prob": round(self.drop_prob, 6),
                "stale_prob": round(self.stale_prob, 6),
                "inversion_prob": round(self.inversion_prob, 6)}


def noise_from_clock(clock: FeedClock, *, age_ms: float | None = None) -> TimingNoise:
    """The corruption model a MEASURED clock implies; an unmeasured term contributes nothing and
    the caller is expected to say so (the verdict then carries `noise_basis`)."""
    # The per-message stale term is the REPEAT rate (a message carrying the previous value),
    # not `stale_prob`, which is the feed's freshness NOW and belongs to health.
    return TimingNoise(jitter_ms=float(clock.jitter_ms or 0.0),
                       drop_prob=float(clock.drop_prob or 0.0),
                       stale_prob=float(clock.repeat_rate or 0.0),
                       inversion_prob=float(clock.inversion_rate or 0.0))


def corrupt_timing(times: FloatArray, values: FloatArray, noise: TimingNoise,
                   rng: np.random.Generator) -> tuple[FloatArray, FloatArray]:
    """Apply the four corruptions a real feed inflicts, in the order they happen on the wire.

    jitter     each message arrives LATE by |N(0, jitter)| -- receipt is never early
    drop       a message is lost with probability drop_prob
    stale      a message repeats the previous VALUE with probability stale_prob (the frozen
               quote that looks exactly like a calm market)
    inversion  adjacent messages swap order with probability inversion_prob
    """
    t = np.asarray(times, dtype=float).copy()
    v = np.asarray(values, dtype=float).copy()
    n = t.size
    if n == 0:
        return t, v
    if noise.jitter_ms > 0:
        t = t + np.abs(rng.normal(0.0, noise.jitter_ms, size=n))
    if noise.stale_prob > 0 and n > 1:
        stale = rng.random(n) < noise.stale_prob
        stale[0] = False
        idx = np.where(stale, np.arange(n) - 1, np.arange(n))
        v = v[idx]
    if noise.inversion_prob > 0 and n > 1:
        swap = np.where(rng.random(n - 1) < noise.inversion_prob)[0]
        for i in swap:
            t[i], t[i + 1] = t[i + 1], t[i]
    if noise.drop_prob > 0:
        keep = rng.random(n) >= noise.drop_prob
        if int(keep.sum()) == 0:
            keep[rng.integers(0, n)] = True
        t, v = t[keep], v[keep]
    return t, v


def edge(signal: FloatArray, returns: FloatArray, *, min_pairs: int = MIN_OBS) -> float:
    """Mean return in the signal's direction per unit of return sd. NaN below `min_pairs`."""
    s, r = np.asarray(signal, dtype=float), np.asarray(returns, dtype=float)
    keep = np.isfinite(s) & np.isfinite(r) & (s != 0)
    if int(keep.sum()) < min_pairs:
        return float("nan")
    sd = float(np.std(r[keep]))
    if sd <= 0:
        return float("nan")
    return float(np.mean(np.sign(s[keep]) * r[keep]) / sd)


def matched_edge(sig_t: FloatArray, sig_v: FloatArray, tgt_t: FloatArray, tgt_v: FloatArray,
                 *, min_pairs: int = MIN_OBS) -> float:
    """The edge when each signal is matched to the target interval CONTAINING its (corrupted)
    time: a target stamped at t_k covers [t_k, t_k+1), so a message that arrives late inside
    the same interval still acts on that interval's return, and one that arrives after the
    interval closed acts on the next -- exactly what a late message costs at the target's own
    resolution (a bar-level target cannot express a 30 s delay; a tick-level one can)."""
    idx = np.searchsorted(tgt_t, sig_t, side="right") - 1
    keep = idx >= 0
    if int(keep.sum()) < min_pairs:
        return float("nan")
    return edge(sig_v[keep], tgt_v[idx[keep]], min_pairs=min_pairs)


def timing_fragility(signal: Sequence[tuple[float, float]],
                     target: Sequence[tuple[float, float]], noise: TimingNoise, *,
                     draws: int = 64, multipliers: Sequence[float] = MULTIPLIERS,
                     survival_fraction: float = SURVIVAL_FRACTION, min_pairs: int = MIN_OBS,
                     rng_seed: int = 20260922) -> dict[str, Any]:
    """Does the edge survive the timing uncertainty the desk's feeds actually carry?

    The clean edge is the signal matched to the first target at or after its stamp. Each draw
    corrupts the signal stream (jitter, drops, stale values, inversions) at `noise` scaled by a
    multiplier and re-measures. The verdict is taken at multiplier 1 -- the MEASURED noise --
    and the ladder above it is the margin: the largest multiplier at which the edge still keeps
    `survival_fraction` of its clean value. UNMEASURED below `min_pairs`, never a verdict.
    """
    sig = sorted((float(t), float(v)) for t, v in signal if math.isfinite(float(v)))
    tgt = sorted((float(t), float(v)) for t, v in target if math.isfinite(float(v)))
    if len(sig) < min_pairs or len(tgt) < min_pairs:
        return {"verdict": UNMEASURED, "n_signal": len(sig), "n_target": len(tgt),
                "why": f"fewer than {min_pairs} usable pair(s): a fragility curve needs a sample"}
    st, sv = (np.asarray([t for t, _ in sig]), np.asarray([v for _, v in sig]))
    tt, tv = (np.asarray([t for t, _ in tgt]), np.asarray([v for _, v in tgt]))
    base = matched_edge(st, sv, tt, tv, min_pairs=min_pairs)
    if not math.isfinite(base) or base == 0.0:
        return {"verdict": UNMEASURED, "n_signal": len(sig), "n_target": len(tgt),
                "base_edge": None if not math.isfinite(base) else 0.0,
                "why": "the clean edge is zero or unmeasurable, so nothing can decay"}
    rng = np.random.default_rng(rng_seed)
    ladder: list[dict[str, Any]] = []
    for k in multipliers:
        scaled = noise.scaled(float(k))
        got = np.asarray([matched_edge(*corrupt_timing(st, sv, scaled, rng), tt, tv,
                                       min_pairs=min_pairs) for _ in range(max(1, draws))])
        got = got[np.isfinite(got)]
        if got.size == 0:
            ladder.append({"multiplier": float(k), "status": UNMEASURED, "noise": scaled.row()})
            continue
        med = float(np.median(got))
        ladder.append({"multiplier": float(k), "status": MEASURED, "noise": scaled.row(),
                       "edge_median": round(med, 6), "edge_p10": round(float(np.percentile(
                           got, 10)), 6), "retained": round(med / base, 4),
                       "draws": int(got.size)})
    at1 = next((r for r in ladder if r["multiplier"] == 1.0 and r["status"] == MEASURED), None)
    if at1 is None:
        return {"verdict": UNMEASURED, "n_signal": len(sig), "n_target": len(tgt),
                "base_edge": round(base, 6), "ladder": ladder,
                "why": "no draw at the measured noise level produced a measurable edge"}
    fragile = float(at1["retained"]) < survival_fraction
    alive = [float(r["multiplier"]) for r in ladder
             if r["status"] == MEASURED and float(r["retained"]) >= survival_fraction]
    return {"verdict": "TIMING_FRAGILE" if fragile else "TIMING_ROBUST",
            "n_signal": len(sig), "n_target": len(tgt), "base_edge": round(base, 6),
            "retained_at_measured_noise": float(at1["retained"]),
            "survival_fraction": survival_fraction,
            "margin_multiplier": max(alive, default=0.0), "noise": noise.row(),
            "ladder": ladder,
            "reason": (f"the edge keeps only {float(at1['retained']):.0%} of its clean value"
                       " under the desk's own MEASURED timing noise: TIMING_FRAGILE, set aside"
                       " for research (never a size)") if fragile else
                      (f"the edge keeps {float(at1['retained']):.0%} under measured noise and"
                       f" survives to {max(alive, default=0.0):g}x of it")}

```

### libs\research\funnel.py
```python
"""SURVIVOR THROUGHPUT, AND WHERE THE FUNNEL IS ACTUALLY BLOCKED.

THE OPTIMISATION TARGET (principal 2026-08-07): *maximise the expected number of independent,
executable, out-of-sample survivors discovered per month, subject to FIXED statistical and
execution gates.* The subordinate clause is the whole thing. A survivor count is trivially
maximised by weakening the gates, so the target is only meaningful while the gates are constants --
which is why nothing in this module can read, set or reference a threshold.

THE DIAGNOSIS THIS EXISTS FOR. When the desk produces zero survivors, there are eight candidate
explanations and they imply OPPOSITE actions::

    too few hypotheses     -> generate            |  poor hypotheses    -> mine better sources
    insufficient data      -> acquire             |  poor testing       -> fix the harness
    overfitting            -> tighten             |  weak validation    -> tighten
    wrong market           -> look elsewhere      |  excessive costs    -> different horizon

Picking the wrong one is not a small error. "Generate more" is the default failure -- it is the
cheapest action, it always feels productive, and it is exactly wrong when the blockage is
downstream. This desk has the archetypal case in its own register: ~900k enumerated candidates,
20,052 pre-registered trials, ZERO executed. The correct diagnosis there is EXECUTION, and a
diagnostic that reported "poor hypotheses" would send the desk to build a bigger generator.

**SO THE FIRST RULE IS THAT A STAGE WITH NO THROUGHPUT DIAGNOSES ITSELF, NOT ITS SUCCESSORS.** If
zero hypotheses were ever TESTED, the desk knows nothing whatever about hypothesis quality,
overfitting, validation or costs -- those stages have no observations. Reporting on them would be
inventing a verdict for a stage that never ran (L1.49), and the flattering direction is always to
blame the stage you can most cheaply act on.

**AND THE SECOND: A RATE OVER A PERIOD WITH NO COMPLETED EXPERIMENTS IS NOT ZERO, IT IS
UNDEFINED.** 0 survivors / 0 experiments is not a 0% survivor rate; it is no measurement. Rendering
it as 0% would make an idle month look like a failing method, and the two call for opposite
responses.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime

from libs.core.coerce import finite_float, integer

__all__ = [
    "CASCADE_STAGES",
    "DISPOSITIONS",
    "DIVERSITY_FIELDS",
    "MEANINGFUL_CHANGE_FIELDS",
    "STAGES",
    "Funnel",
    "FunnelDiagnosis",
    "diagnose",
    "meaningful_research_throughput",
    "throughput",
]

#: The pipeline, in order. Each stage's count is the number that REACHED it. A stage cannot exceed
#: its predecessor, and `Funnel.inconsistencies` reports it when one does rather than quietly
#: clipping -- a funnel that widens downstream is a counting bug, and counting bugs in this
#: direction manufacture throughput.
STAGES: tuple[str, ...] = (
    "mined",  # raw ore returned by the miners
    "hypotheses",  # ore translated into falsifiable statements
    "novel_families",  # after semantic de-duplication: distinct ideas, not formulas
    "tested",  # experiments actually COMPLETED against data
    "net_positive",  # cleared costs
    "deflated",  # cleared the multiple-testing hurdle
    "out_of_sample",  # held up on data not used to select them
    "independent",  # distinct MECHANISMS after correlation clustering
    "portfolio_positive",  # improved geometric growth after correlation, cost and capacity
)

#: Which stage each diagnosis blames, and what to do. Ordered EARLIEST-FIRST: the earliest empty
#: stage is the binding one, because every later stage is starved by construction and says nothing
#: about itself.
_BLOCKAGE: dict[str, tuple[str, str]] = {
    "mined": ("INFORMATION", "no ore is arriving -- the miners are the constraint, not the tests"),
    "hypotheses": (
        "TRANSLATION",
        "ore is arriving and nothing is being turned into a falsifiable "
        "statement. This is a refinery problem, not a mining one",
    ),
    "novel_families": (
        "NOVELTY",
        "hypotheses exist but collapse to almost no distinct ideas -- "
        "the generator is re-searching one neighbourhood",
    ),
    "tested": (
        "EXECUTION",
        "hypotheses are queued and nothing is being RUN. Generating more is "
        "the cheapest action and the wrong one: it grows the queue that is "
        "already the bottleneck (L1.52(a): queue backlogged -> EXECUTE)",
    ),
    "net_positive": (
        "COSTS",
        "candidates test but nothing clears costs. Look at horizon and "
        "turnover before signal quality -- and check the liquidity "
        "distribution, since an edge that survives only in the tightest "
        "names is a liquidity finding (WS-006)",
    ),
    "deflated": (
        "SEARCH WIDTH or SIGNAL",
        "things clear costs but not the multiple-testing bar. "
        "Either the search is too wide for the evidence, or the "
        "effects are real but small -- those need different "
        "responses, and more trials worsens both",
    ),
    "out_of_sample": (
        "OVERFITTING",
        "candidates clear in-sample and die out-of-sample. The "
        "harness is selecting on noise; widening the search makes it "
        "worse, not better",
    ),
    "independent": (
        "REDUNDANCY",
        "survivors exist but collapse to one mechanism. The count is "
        "inventory, not discovery -- hunt orthogonal mechanisms",
    ),
    "portfolio_positive": (
        "PORTFOLIO",
        "independent mechanisms exist but none improves geometric "
        "growth after correlation, cost and capacity",
    ),
}


@dataclass(frozen=True)
class Funnel:
    """Counts reaching each stage over one period. Absent stages are UNMEASURED, not zero."""

    counts: dict[str, int | None] = field(default_factory=dict)
    period_days: float = 30.0

    def get(self, stage: str) -> int | None:
        return self.counts.get(stage)

    @property
    def inconsistencies(self) -> list[str]:
        """Stages that exceed their predecessor -- a counting bug that inflates throughput."""
        out, prev_name, prev = [], "", None
        for s in STAGES:
            v = self.counts.get(s)
            if v is not None and prev is not None and v > prev:
                out.append(f"{s}={v} exceeds {prev_name}={prev}: a funnel cannot widen downstream")
            if v is not None:
                prev_name, prev = s, v
        return out


@dataclass(frozen=True)
class FunnelDiagnosis:
    """Where the pipeline is blocked, and what the blockage licenses."""

    blocked_at: str | None
    blockage: str
    action: str
    survivor_rate: float | None
    survivors_per_month: float | None
    unmeasured_downstream: tuple[str, ...] = field(default_factory=tuple)
    warnings: tuple[str, ...] = field(default_factory=tuple)

    @property
    def headline(self) -> str:
        if self.blocked_at is None:
            return "no blockage detected -- every stage has throughput"
        return f"BLOCKED AT {self.blocked_at.upper()} ({self.blockage})"


def throughput(f: Funnel) -> tuple[float | None, float | None]:
    """(survivor rate, survivors per 30 days). None where the denominator does not exist.

    0 survivors / 0 experiments IS NOT A 0% SURVIVOR RATE. It is no measurement, and rendering it
    as 0% makes an idle month look like a failing method -- opposite problems with opposite fixes.
    """
    tested, indep = f.get("tested"), f.get("independent")
    rate = (indep / tested) if (tested and indep is not None) else None
    per_month = (
        (indep / f.period_days) * 30.0 if (indep is not None and f.period_days > 0) else None
    )
    return rate, per_month


def diagnose(f: Funnel) -> FunnelDiagnosis:
    """Find the EARLIEST stage with no throughput and blame that one.

    EARLIEST, because every later stage is starved by construction. A funnel with 20,000 queued
    hypotheses and zero executed tests says NOTHING about overfitting, costs or validation -- those
    stages have no observations, and reporting a verdict for them would be inventing one for a gate
    that never ran (L1.49). The stages downstream of the blockage are returned as explicitly
    UNMEASURED so the reader cannot mistake silence for health.
    """
    rate, per_month = throughput(f)
    warnings = list(f.inconsistencies)

    blocked_at = None
    for stage in STAGES:
        v = f.get(stage)
        if v is None:
            warnings.append(
                f"{stage} was never counted -- UNMEASURED, which is not zero and not "
                "fine; a stage nobody instrumented cannot be diagnosed"
            )
            continue
        if v <= 0:
            blocked_at = stage
            break

    if blocked_at is None:
        return FunnelDiagnosis(
            None,
            "none",
            "every stage has throughput; optimise the narrowest ratio",
            rate,
            per_month,
            (),
            tuple(warnings),
        )

    idx = STAGES.index(blocked_at)
    downstream = STAGES[idx + 1 :]
    blockage, action = _BLOCKAGE[blocked_at]
    return FunnelDiagnosis(
        blocked_at,
        blockage,
        action,
        rate,
        per_month,
        downstream,
        (
            *warnings,
            f"the {len(downstream)} stage(s) after {blocked_at} are starved by "
            "construction and say "
            "NOTHING about themselves -- do not read their zeros as findings",
        ),
    )


def render(f: Funnel) -> str:
    """The block a human or an organ reads. Rates print as UNMEASURED where undefined."""
    d = diagnose(f)
    rate = (
        "UNMEASURED (no completed experiments)"
        if d.survivor_rate is None
        else f"{d.survivor_rate:.2%}"
    )
    per_month = "UNMEASURED" if d.survivors_per_month is None else f"{d.survivors_per_month:.2f}"
    lines = [
        d.headline,
        f"  survivor rate {rate} | independent survivors / 30d {per_month}",
        "  " + " -> ".join(f"{s}:{f.get(s) if f.get(s) is not None else '?'}" for s in STAGES),
        f"  ACTION: {d.action}",
    ]
    lines += [f"  ! {w}" for w in d.warnings]
    lines.append(
        "  THE TARGET IS SURVIVOR THROUGHPUT AT FIXED GATES. A survivor count is "
        "trivially maximised by weakening a threshold, so a rise that coincides with a "
        "gate change is not a rise."
    )
    return "\n".join(lines)


CASCADE_STAGES = (
    "semantic_mechanism_deduplication",
    "data_timestamp_feasibility",
    "cheapest_informative_falsification",
    "basic_empirical_test",
    "robustness_and_cost_realism",
    "true_oos_walk_forward",
    "portfolio_independence",
    "shadow_live",
)

DISPOSITIONS = ("TEST_NOW", "TEST_LATER_WITH_BLOCKER", "REJECT_BEFORE_TEST")

MEANINGFUL_CHANGE_FIELDS = (
    "economic_mechanism",
    "information_source",
    "participant_behavior",
    "market_state",
    "causal_structure",
    "data_modality",
    "cross_market_relationship",
    "execution_mechanism",
    "regime_dependency",
    "new_information_transformation",
    "distinct_source_interaction",
)

DIVERSITY_FIELDS = (
    "mechanism",
    "asset",
    "venue",
    "horizon",
    "regime",
    "participant",
    "data_source",
    "data_modality",
    "research_methodology",
)


def meaningful_research_throughput(
    candidates: Sequence[Mapping[str, object]],
    *,
    now: str | datetime | None = None,
    window_hours: float = 24.0,
) -> dict[str, object]:
    """Daily ledger for meaningful generation, cascade testing and explicit disposition."""
    if window_hours <= 0:
        raise ValueError("window_hours must be positive")
    current = (
        now
        if isinstance(now, datetime)
        else datetime.fromisoformat(now)
        if now
        else datetime.now(tz=UTC)
    )
    if current.tzinfo is None:
        current = current.replace(tzinfo=UTC)

    def parse(value: object) -> datetime | None:
        if not value:
            return None
        try:
            stamp = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except ValueError:
            return None
        return stamp if stamp.tzinfo else stamp.replace(tzinfo=UTC)

    recent = []
    for candidate in candidates:
        generated = parse(candidate.get("generated_at"))
        if generated is None or (current - generated).total_seconds() <= window_hours * 3600:
            recent.append(candidate)
    meaningful = []
    parameter_variants = []
    for candidate in recent:
        declared = candidate.get("substantive_changes", [])
        changes = {str(value) for value in declared} if isinstance(declared, list) else set()
        changes.update(name for name in MEANINGFUL_CHANGE_FIELDS if candidate.get(name))
        if changes and not bool(candidate.get("pure_parameter_variant")):
            meaningful.append(candidate)
        else:
            parameter_variants.append(candidate)

    stage_counts = dict.fromkeys(CASCADE_STAGES, 0)
    disposition_counts = dict.fromkeys(DISPOSITIONS, 0)
    un_dispositioned = []
    tests_started = completed = valid = oos = near = survivors = independent = recycled = 0
    blocked_missing_data = infrastructure_failures = automatically_testable = 0
    compute_seconds = data_loading_seconds = information_gain = 0.0
    valuable_waiting = []
    mechanism_ids = set()
    diversity: dict[str, Counter[str]] = {name: Counter() for name in DIVERSITY_FIELDS}
    for candidate in meaningful:
        mechanism = candidate.get("mechanism_id", candidate.get("mechanism"))
        if mechanism:
            mechanism_ids.add(str(mechanism))
        disposition = str(candidate.get("disposition", ""))
        if disposition in disposition_counts:
            disposition_counts[disposition] += 1
        else:
            un_dispositioned.append(candidate.get("id", mechanism))
        blocker = str(candidate.get("blocker", ""))
        if disposition == "TEST_LATER_WITH_BLOCKER" and "data" in blocker.casefold():
            blocked_missing_data += 1
        if bool(candidate.get("infrastructure_failure")):
            infrastructure_failures += 1
        if bool(candidate.get("automatically_testable")):
            automatically_testable += 1
        stages = candidate.get("stages", {})
        stages = stages if isinstance(stages, Mapping) else {}
        for stage in CASCADE_STAGES:
            stage_counts[stage] += int(bool(stages.get(stage)))
        started = bool(candidate.get("test_started_at")) or bool(stages.get(CASCADE_STAGES[3]))
        done = bool(candidate.get("test_completed_at"))
        is_valid = done and bool(candidate.get("valid_empirical_test"))
        tests_started += int(started)
        completed += int(done)
        valid += int(is_valid)
        oos += int(bool(stages.get(CASCADE_STAGES[5])) or bool(candidate.get("oos_tested")))
        near += int(bool(candidate.get("near_survivor")))
        survivors += int(bool(candidate.get("survivor")))
        independent += int(bool(candidate.get("independent_survivor")))
        recycled += integer(candidate.get("failure_descendants"))
        compute_seconds += finite_float(candidate.get("compute_seconds"))
        data_loading_seconds += finite_float(candidate.get("data_loading_seconds"))
        information_gain += finite_float(candidate.get("information_gain"))
        if disposition == "TEST_NOW" and not started:
            generated = parse(candidate.get("generated_at"))
            valuable_waiting.append((generated, candidate.get("id", mechanism)))
        for dimension in DIVERSITY_FIELDS:
            if candidate.get(dimension) is not None:
                diversity[dimension][str(candidate[dimension])] += 1

    diversity_rows = {}
    for dimension, counts in diversity.items():
        total = sum(counts.values())
        hhi = sum((count / total) ** 2 for count in counts.values()) if total else None
        diversity_rows[dimension] = {
            "represented": len(counts),
            "hhi": hhi,
            "effective_categories": 1 / hhi if hhi else None,
            "counts": dict(counts),
        }
    oldest = min((stamp for stamp, _ in valuable_waiting if stamp is not None), default=None)
    oldest_id = next(
        (identifier for stamp, identifier in valuable_waiting if stamp == oldest), None
    )
    waiting = len(valuable_waiting)
    if waiting:
        bottleneck = "TEST_EXECUTION"
    elif un_dispositioned:
        bottleneck = "DISPOSITION"
    elif blocked_missing_data:
        bottleneck = "MISSING_DATA"
    elif infrastructure_failures:
        bottleneck = "INFRASTRUCTURE"
    elif meaningful and not valid:
        bottleneck = "VALID_TEST_COMPLETION"
    elif not meaningful:
        bottleneck = "MEANINGFUL_GENERATION_UNMEASURED"
    else:
        bottleneck = "NO_BINDING_BOTTLENECK_OBSERVED"
    hours = window_hours
    return {
        "status": "MEASURED" if candidates else "UNMEASURED",
        "window_hours": hours,
        "raw_generated_specifications": len(recent),
        "deduplicated_meaningful_candidates": len(meaningful),
        "parameter_variants": len(parameter_variants),
        "unique_mechanisms": len(mechanism_ids),
        "candidates_submitted_to_testing": tests_started,
        "tests_executed": tests_started,
        "tests_completed": completed,
        "valid_empirical_tests": valid,
        "oos_tested_candidates": oos,
        "near_survivors": near,
        "survivors": survivors,
        "independent_survivors": independent,
        "failed_candidates_converted_to_hypotheses": recycled,
        "dispositions": disposition_counts,
        "undispositioned_candidates": un_dispositioned,
        "cascade_stage_counts": stage_counts,
        "candidates_generated_per_hour": len(meaningful) / hours,
        "tests_per_hour": tests_started / hours,
        "cpu_seconds_per_completed_test": compute_seconds / completed if completed else None,
        "data_loading_seconds": data_loading_seconds,
        "percentage_automatically_testable": (
            automatically_testable / len(meaningful) if meaningful else None
        ),
        "percentage_blocked_by_missing_data": (
            blocked_missing_data / len(meaningful) if meaningful else None
        ),
        "percentage_infrastructure_failure": (
            infrastructure_failures / len(meaningful) if meaningful else None
        ),
        "survivor_yield_per_1000_meaningful_tests": (independent * 1000 / valid if valid else None),
        "information_gain": information_gain,
        "information_gain_per_compute_hour": (
            information_gain / (compute_seconds / 3600) if compute_seconds > 0 else None
        ),
        "oldest_valuable_untested_candidate": oldest_id,
        "oldest_valuable_untested_age_hours": (
            (current - oldest).total_seconds() / 3600 if oldest else None
        ),
        "dominant_bottleneck": bottleneck,
        "diversity": diversity_rows,
        "generated_is_not_tested": True,
        "authority": "THROUGHPUT DIAGNOSTIC ONLY -- fixed statistical and survival gates",
    }

```

### libs\research\orderbook_state.py
```python
"""ORDER-BOOK MICROSTRUCTURE STATE -- the alignment and de-contamination primitives for any
depth-of-market tape.

VENUE-NEUTRAL BY CONSTRUCTION, AND REPOINTED AT THE MT5 TAPE (2026-09-05). This module was first
written against a crypto-exchange order-book recorder, and that recorder is gone. Nothing here
went with it, because nothing here was ever about that venue: every function takes ARRAYS and
PLAIN ROWS and returns numbers. The subject is resting-depth STATE at a bar boundary and whether
it predicts the NEXT bar's return -- a question the MT5/Fusion universe asks in exactly the same
form, because MT5 publishes depth-of-market (`MarketBookGet`) and a tick tape with volume. When
the desk's MT5 tick/DOM recorder lands, it feeds this module directly: hand `depth_snapshots` rows
carrying a millisecond stamp and bid/ask level arrays and every construction below works unchanged.

WHAT THIS MODULE REFUSES TO DO. Every prior attempt on this mechanism class died the same death --
book state is CONCURRENT with price, so a raw correlation is a restatement of the move that just
happened wearing the vocabulary of a forecast. This module holds the two things that decide
whether that death is avoided:

  (1) THE ALIGNMENT. Fixed, wall-clock-anchored, half-open bars, and a target priced only from
      prints AT OR AFTER the bar's right edge, so the signal can never touch the window it is
      asked to predict. `Alignment` carries the rule as data and every artifact echoes it --
      charter section 26 clause 4: unstated alignment voids the screen.
  (2) THE RESIDUALISATION. `residualise` orthogonalises the state against the SAME-BAR return
      using a beta fitted on STRICTLY PRIOR bars only. A full-sample beta would leak: the residual
      at bar k would depend on returns that had not happened yet, and it would be invisible,
      because it looks like preprocessing rather than like a decision.

WHAT THE RESIDUAL IS AND WHY IT IS TRADEABLE. resid[k] = state[k] - (a_k + b_k * r[k]), where r[k]
is the return realised OVER bar k and (a_k, b_k) come from bars strictly before k. Every input is
in the information set at the bar's right edge, so the residual is computable at the moment the
decision is taken. That is the whole point: subtracting the concurrent return is only legitimate
because the concurrent return is already known when the bet is placed. Subtracting the NEXT bar's
return would not be, and nothing here can do it -- `residualise` never indexes forward.

NO I/O. `depth_snapshots` parses already-loaded rows; it opens nothing and fetches nothing. Trade
PRICES are passed in as arrays by the caller, so this module stays pure numeric and testable
without a tape.

Pure numpy. Zero promotion authority.
"""

from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import numpy as np

__all__ = [
    "CONSTRUCTIONS",
    "FORMS",
    "MIN_RESID_OBS",
    "STATE_NAMES",
    "Alignment",
    "bar_close_states",
    "boundary_prices",
    "contiguous_mask",
    "depth_snapshots",
    "period_returns",
    "residualise",
    "snapshot_states",
    "withdrawal_asymmetry",
]

#: Prior bars an expanding orthogonalisation needs before its beta means anything. A residual taken
#: against a beta fitted on ten points is a statement about ten points, and it would be handed to
#: the screen wearing the same name as a converged one.
MIN_RESID_OBS = 60

#: Per-snapshot primitives every construction is built from. Named here so the caller cannot
#: silently screen a state this module never computed.
STATE_NAMES = ("obi_touch", "obi_deep", "slope_asym", "spread_bps", "depth_bid", "depth_ask")

#: The two forms every construction is screened in. BOTH are reported, always: reporting only the
#: residualised form would hide the contamination measurement, and reporting only the raw form is
#: the mistake that killed every cross-venue premium axis this desk has ever screened: each one
#: read as a forecast and was a restatement of the concurrent move.
FORMS = ("raw", "residualised")

#: Levels summed for the "deep" primitives. The touch is public everywhere; the shape behind it is
#: what the recorded tape actually owns.
_DEEP_LEVELS = 20

#: Points needed per side before a depth-decay slope is fitted. Three levels through a straight
#: line is not a slope, it is an interpolation.
_MIN_SLOPE_POINTS = 4


@dataclass(frozen=True)
class Alignment:
    """THE TIMESTAMP RULE, AS DATA -- so it is echoed into every artifact rather than described.

    Bars are FIXED, WALL-CLOCK-ANCHORED and HALF-OPEN in UTC milliseconds:

        bar k  = [ k * bar_ms, (k + 1) * bar_ms )        right edge b_k = (k + 1) * bar_ms

    SIGNAL. state[k] is read from the LAST depth snapshot whose timestamp lies strictly inside
    bar k, i.e. t < b_k. Its decision time is b_k.

    TARGET. p[k] is the first trade print at or after (b_k + decision_lag_ms); the return realised
    OVER bar k is r[k] = p[k] / p[k-1] - 1. That is exactly `axis_screen`'s contract --
    "target_ret[t] = return realised over period t" -- and the harness performs the forward shift
    itself, pairing state[k] with r[k+1]. Handing it an already-shifted target makes it shift
    twice, which is the misalignment signature its own lookahead rail fires on -- the retired
    order-book screen lost fourteen of nineteen hypotheses to precisely that.

    SO THE PREDICTED WINDOW IS [b_k, b_{k+1}) AND THE BAR CONTAINING THE SNAPSHOT IS NOT IN IT.
    The snapshot at t sits in [b_k - bar_ms, b_k); the return it is asked to predict starts at the
    first print at or after b_k. No print inside the snapshot's own bar can enter the forward
    return, and no snapshot at or after b_k can enter the signal.

    DECLARED LOOK-AHEAD RISK, and it is the one this construction cannot design away.
    r[k] closes on the same print p[k] that opens r[k+1]. The residualised form therefore assumes
    the desk observes p[k] and transacts at p[k], which is a ZERO-LATENCY fill and an upper bound
    on anything achievable. `decision_lag_ms` exists to price that away: set it to the desk's
    measured round trip and the target is taken from the first print at or after b_k + lag, which
    can only ever WEAKEN the reading. It defaults to 0 so the primary screen reports the optimistic
    bound explicitly rather than burying a latency assumption in a comment; a cell that survives at
    0 and dies at a realistic lag was never an edge, and the artifact must be able to say so.
    """

    bar_ms: int
    decision_lag_ms: int = 0

    def __post_init__(self) -> None:
        if self.bar_ms <= 0:
            raise ValueError("bar_ms must be positive")
        if self.decision_lag_ms < 0:
            raise ValueError("decision_lag_ms must not be negative")

    @property
    def horizon_days(self) -> float:
        """Bar width in days -- what `axis_screen` needs to annualise and to deflate n_eff."""
        return float(self.bar_ms) / 86_400_000.0

    def as_dict(self) -> dict[str, Any]:
        return {
            "bar_ms": int(self.bar_ms),
            "decision_lag_ms": int(self.decision_lag_ms),
            "horizon_days": self.horizon_days,
            "bar_boundary": "half-open [k*bar_ms, (k+1)*bar_ms) in UTC ms, wall-clock anchored",
            "signal_at": "last depth snapshot with t strictly < the bar right edge b_k",
            "target_priced_at": "first trade print with t >= b_k + decision_lag_ms",
            "same_period_return": "r[k] = p[k]/p[k-1] - 1, the return realised OVER bar k",
            "forward_pairing": "the harness pairs state[k] with r[k+1]; window [b_k, b_{k+1})",
            "excludes_current_bar": True,
            "lookahead_risk": (
                "r[k] closes on the same print that opens r[k+1], so decision_lag_ms=0 assumes a "
                "zero-latency fill and is an UPPER BOUND; re-run at the measured round trip "
                "before believing any survivor"
            ),
        }


def _levels(side: Any) -> tuple[np.ndarray, np.ndarray]:
    """One side of a book as (prices, sizes), dropping rows that cannot be read.

    BAD ROWS ARE DROPPED, NEVER COERCED TO ZERO. A zero size is a real and meaningful book state
    -- the level is quoted and empty -- so inventing one manufactures a withdrawal event that never
    happened, and `withdrawal_asymmetry` would then read it as liquidity leaving.
    """
    px: list[float] = []
    sz: list[float] = []
    for lv in side or ():
        try:
            p, s = float(lv[0]), float(lv[1])
        except (TypeError, ValueError, IndexError, KeyError):
            continue
        if math.isfinite(p) and math.isfinite(s) and p > 0 and s >= 0:
            px.append(p)
            sz.append(s)
    return np.asarray(px, dtype="float64"), np.asarray(sz, dtype="float64")


def depth_snapshots(
    rows: list[dict[str, Any]],
) -> list[tuple[int, np.ndarray, np.ndarray, np.ndarray, np.ndarray]]:
    """Parse depth rows into (stamp_ms, bid_px, bid_sz, ask_px, ask_sz), ascending by stamp.

    THE ROW SCHEMA IS THE LOWEST COMMON DENOMINATOR OF A DEPTH FEED, so a recorder can satisfy it
    without negotiating: a millisecond stamp under ``t`` or ``ts_ms``, and two sides of
    ``[[price, size], ...]`` under ``b``/``bids`` and ``a``/``asks``. Strings are accepted --
    MT5's `MarketBookGet` hands back typed floats, most JSON tapes hand back strings, and refusing
    one of those is how a reader silently returns an empty book.

    ORDER IS NOT GUARANTEED BY THE FEED, and every construction below indexes ``[0]`` as the touch.
    Sorting here rather than trusting the source costs nothing and removes a whole class of finding
    that would look like microstructure and be a parse bug.

    CROSSED BOOKS ARE DROPPED, NOT USED. bid >= ask is physically impossible and means a torn or
    interleaved snapshot. Feeding one to a spread calculation yields a NEGATIVE cost -- "the venue
    pays us to trade" -- and that is precisely the kind of artifact that survives review because it
    is exciting. Dropping is silent by design at this layer; the CALLER counts what it lost, since
    only the caller knows what fraction is tolerable for its screen.
    """
    out: list[tuple[int, np.ndarray, np.ndarray, np.ndarray, np.ndarray]] = []
    for r in rows:
        if not isinstance(r, dict):
            continue
        bp, bs = _levels(r.get("b") if r.get("b") is not None else r.get("bids"))
        ap, asz = _levels(r.get("a") if r.get("a") is not None else r.get("asks"))
        if not len(bp) or not len(ap):
            continue
        bo, ao = np.argsort(-bp), np.argsort(ap)
        bp, bs, ap, asz = bp[bo], bs[bo], ap[ao], asz[ao]
        if bp[0] >= ap[0]:
            continue
        stamp: Any = r.get("t")
        if stamp is None:
            stamp = r.get("ts_ms", 0)
        try:
            ms = int(stamp)
        except (TypeError, ValueError):
            continue
        out.append((ms, bp, bs, ap, asz))
    out.sort(key=lambda x: x[0])
    return out


def snapshot_states(rows: list[dict[str, Any]]) -> tuple[np.ndarray, dict[str, np.ndarray]]:
    """Per-snapshot book-STATE primitives from raw depth rows.

    Delegates parsing to `depth_snapshots`, which sorts levels and drops crossed books. Returns
    (snapshot ms ascending, {name: values}) over `STATE_NAMES`; an unmeasurable primitive is NaN,
    never zero -- a zero imbalance is a real and balanced book, which is the opposite of "this
    snapshot could not be read".
    """
    snaps = depth_snapshots(rows)
    n = len(snaps)
    ms = np.zeros(n, dtype="int64")
    out = {k: np.full(n, np.nan) for k in STATE_NAMES}
    for i, (t_ms, bp, bs, ap, asz) in enumerate(snaps):
        ms[i] = t_ms
        b0, a0 = float(bs[0]), float(asz[0])
        if b0 + a0 > 0:
            out["obi_touch"][i] = (b0 - a0) / (b0 + a0)
        bd = float(bs[:_DEEP_LEVELS].sum())
        ad = float(asz[:_DEEP_LEVELS].sum())
        out["depth_bid"][i] = bd
        out["depth_ask"][i] = ad
        if bd + ad > 0:
            out["obi_deep"][i] = (bd - ad) / (bd + ad)
        mid = (float(bp[0]) + float(ap[0])) / 2.0
        if mid > 0:
            out["spread_bps"][i] = (float(ap[0]) - float(bp[0])) / mid * 1e4
            sb = _side_slope(bp[:_DEEP_LEVELS], bs[:_DEEP_LEVELS], mid)
            sa = _side_slope(ap[:_DEEP_LEVELS], asz[:_DEEP_LEVELS], mid)
            out["slope_asym"][i] = sb - sa
    return ms, out


def _side_slope(px: np.ndarray, size: np.ndarray, mid: float) -> float:
    """log(size) regressed on distance-from-mid in bps, one side only. NaN when unfittable.

    ONE SIDE, NOT BOTH TOGETHER. A pooled fit over both sides answers "is depth concentrated at
    the touch"; the ASYMMETRY of the two sides is a different question -- which side is thin BEHIND
    the quote -- and pooling averages away exactly the difference being asked about.
    """
    d = np.abs(np.asarray(px, dtype="float64") - mid) / mid * 1e4
    s = np.asarray(size, dtype="float64")
    ok = (d > 0) & (s > 0) & np.isfinite(d) & np.isfinite(s)
    if int(ok.sum()) < _MIN_SLOPE_POINTS:
        return float("nan")
    x = d[ok]
    y = np.log(s[ok])
    xv = float(((x - x.mean()) ** 2).sum())
    if xv <= 0:
        return float("nan")
    return float(((x - x.mean()) * (y - y.mean())).sum() / xv)


def bar_close_states(
    snap_ms: np.ndarray, states: dict[str, np.ndarray], *, alignment: Alignment
) -> tuple[np.ndarray, dict[str, np.ndarray]]:
    """Collapse per-snapshot states to ONE observation per bar, taken at the bar's right edge.

    Returns (right edges b_k in UTC ms, {name: state at the last snapshot inside bar k}).

    THE LAST SNAPSHOT, NOT THE MEAN OF THE BAR. An average over the bar is a summary of a window
    that ENDS at b_k, so it is still causal -- but it is not the state a decision taken at b_k
    would see, and the mechanism under test is about the book's condition at the moment of the
    bet. Averaging is the right choice for a different question (the quantity with the most
    signal in it, rather than the quantity a trader observes); this screen needs the OBSERVABLE
    one, because a survivor here has to be actionable at b_k.

    Bars with no snapshot simply do not appear -- the edges array is not guaranteed contiguous, and
    `contiguous_mask` is what turns that into a dropped period rather than a mispriced one.
    """
    ms = np.asarray(snap_ms, dtype="int64")
    if ms.size == 0:
        return np.zeros(0, dtype="int64"), {k: np.zeros(0) for k in states}
    idx = ms // int(alignment.bar_ms)
    last = np.ones(idx.size, dtype=bool)
    last[:-1] = idx[:-1] != idx[1:]
    edges = (idx[last] + 1) * int(alignment.bar_ms)
    return edges.astype("int64"), {k: np.asarray(v, dtype="float64")[last] for k, v in
                                   states.items()}


def contiguous_mask(edges_ms: np.ndarray, *, alignment: Alignment) -> np.ndarray:
    """True where the period ENDING at this bar really spanned one bar width.

    A recorder outage -- or two non-adjacent days screened together -- puts a gap in the edge
    series. Without this, one "60-second period" can be twelve hours and carry twelve hours of
    return into a sample whose every other observation carries a minute; that single point
    dominates an IC computed over hundreds, in whichever direction the overnight move happened to
    go. The first bar has no preceding period and is always False, matching `period_returns`, which
    leaves it NaN for the same reason.
    """
    e = np.asarray(edges_ms, dtype="int64")
    m = np.zeros(e.size, dtype=bool)
    if e.size < 2:
        return m
    m[1:] = np.diff(e) == int(alignment.bar_ms)
    return m


def boundary_prices(
    trade_ms: np.ndarray, trade_px: np.ndarray, edges_ms: np.ndarray, *, alignment: Alignment
) -> np.ndarray:
    """The first print AT OR AFTER each bar's right edge (plus any declared decision lag).

    NaN where no print exists after the edge: no trade means no obtainable price, and a carried
    forward last price would report a fill the desk could not have had.

    `side="left"` is the load-bearing argument. It selects the first print with t >= target; the
    bar is half-open, so a print landing exactly on b_k belongs to the NEXT bar and is a price
    obtainable strictly after the state was observed. Using the last print at or BEFORE the edge --
    which an earlier version of this screen did -- lands seconds BEFORE the signal on a
    4-second-cadence tape and prices the very move the feature was measured during.
    """
    t = np.asarray(trade_ms, dtype="int64")
    p = np.asarray(trade_px, dtype="float64")
    e = np.asarray(edges_ms, dtype="int64")
    if t.size == 0 or e.size == 0:
        return np.full(e.size, np.nan)
    i = np.searchsorted(t, e + int(alignment.decision_lag_ms), side="left")
    have = i < t.size
    return np.where(have, p[np.clip(i, 0, p.size - 1)], np.nan)


def period_returns(prices: np.ndarray) -> np.ndarray:
    """r[k] = p[k]/p[k-1] - 1, the return realised OVER bar k. NaN at k=0 and on missing prints.

    CONTEMPORANEOUS BY CONSTRUCTION, and it must stay that way: `axis_screen` does its own forward
    shift, so a target that is already forward gets shifted twice and the harness reads the result
    as misalignment rather than as edge.
    """
    p = np.asarray(prices, dtype="float64")
    out = np.full(p.size, np.nan)
    if p.size < 2:
        return out
    prev = np.where(p[:-1] > 0, p[:-1], np.nan)
    out[1:] = p[1:] / prev - 1.0
    return out


def residualise(
    signal: np.ndarray, same_period_ret: np.ndarray, *, min_obs: int = MIN_RESID_OBS
) -> np.ndarray:
    """Orthogonalise a state series against the SAME-BAR return, with a STRICTLY PRIOR beta.

    THE ENTIRE CONTAMINATION DEFENCE OF THIS SCREEN. Book state is concurrent with price -- the
    side that just got hit is the thin one -- so a raw forward IC is very largely a restatement of
    the bar that just finished. This subtracts that restatement BEFORE the series is asked to
    predict anything, which is the escalation the desk's own graveyard prescribes for exactly this
    failure mode: orthogonalise FIRST, or screen at the mechanism's native horizon.

    resid[k] = signal[k] - (a_k + b_k * ret[k]), with (a_k, b_k) the ordinary least squares fit
    over bars j < k on which both series are finite. STRICTLY PRIOR: bar k never contributes to
    its own beta. A full-sample beta -- one line of numpy, and what `axis_screen` necessarily uses
    for its own internal diagnostic because it is handed only the finished arrays -- makes resid[k]
    a function of returns that had not happened yet. That is the same leak class as full-sample
    normalisation, and the reason it survives review is that it looks like preprocessing.

    NaN until `min_obs` prior finite pairs exist, wherever either input is NaN, and wherever the
    prior returns had zero dispersion (no beta is identified against a constant).

    THIS FUNCTION CANNOT LOOK FORWARD. Every cumulative sum below is shifted by one before use, so
    index k reads strictly from indices < k. That is the property the tests pin by perturbing a
    future observation and asserting the earlier residuals are bit-identical.
    """
    s = np.asarray(signal, dtype="float64")
    r = np.asarray(same_period_ret, dtype="float64")
    if s.size != r.size:
        raise ValueError(f"signal/return length mismatch: {s.size} vs {r.size}")
    out = np.full(s.size, np.nan)
    if s.size == 0:
        return out
    ok = np.isfinite(s) & np.isfinite(r)
    sv = np.where(ok, s, 0.0)
    rv = np.where(ok, r, 0.0)

    def _prior(a: np.ndarray) -> np.ndarray:
        return np.concatenate(([0.0], a[:-1]))

    n = _prior(np.cumsum(ok.astype("float64")))
    s_s = _prior(np.cumsum(sv))
    s_r = _prior(np.cumsum(rv))
    s_rr = _prior(np.cumsum(rv * rv))
    s_sr = _prior(np.cumsum(sv * rv))

    den = n * s_rr - s_r * s_r
    with np.errstate(invalid="ignore", divide="ignore"):
        beta = np.where(den > 0.0, (n * s_sr - s_s * s_r) / np.where(den > 0.0, den, 1.0), np.nan)
        alpha = np.where(n > 0.0, (s_s - beta * s_r) / np.where(n > 0.0, n, 1.0), np.nan)
        resid = s - alpha - beta * r
    usable = ok & (n >= float(min_obs)) & np.isfinite(resid)
    out[usable] = resid[usable]
    return out


def withdrawal_asymmetry(depth_bid: np.ndarray, depth_ask: np.ndarray) -> np.ndarray:
    """Fractional drop in bid-side resting depth MINUS the same on the ask side, bar to bar.

    Positive = the bid side pulled harder than the offer. This is the one construction in the set
    that is a DYNAMIC rather than a level, and it is here because the class's own economic
    definition names withdrawal explicitly: a resting order that does not withdraw in time is
    picked off, so the side that withdraws first is the side that believes it is about to be.

    NaN at index 0 (no previous bar) and wherever the previous depth was zero. Drops are NOT netted
    against additions on the same side; netting would average the exact event of interest into
    invisibility -- size vanishing just before a move is not cancelled out by size arriving
    after it, and treating them as one number is how this signal gets averaged into nothing.
    """
    b = np.asarray(depth_bid, dtype="float64")
    a = np.asarray(depth_ask, dtype="float64")
    if b.size != a.size:
        raise ValueError(f"depth length mismatch: {b.size} vs {a.size}")
    out = np.full(b.size, np.nan)
    if b.size < 2:
        return out
    with np.errstate(invalid="ignore", divide="ignore"):
        db = (b[:-1] - b[1:]) / np.where(b[:-1] > 0, b[:-1], np.nan)
        da = (a[:-1] - a[1:]) / np.where(a[:-1] > 0, a[:-1], np.nan)
    out[1:] = db - da
    return out


#: THE PRE-REGISTERED CONSTRUCTION SET. Five, fixed, named before any result -- the family the
#: multiplicity charge is computed over. Adding a sixth after seeing the first five is the
#: garden-of-forking-paths the charter's clause 3 forbids, and it would silently deflate the
#: correction every other cell was judged against.
CONSTRUCTIONS: dict[str, Callable[[dict[str, np.ndarray]], np.ndarray]] = {
    # STATE -- where resting size is, at the moment of the decision.
    "obi_touch": lambda s: s["obi_touch"],
    "obi_deep": lambda s: s["obi_deep"],
    # SHAPE -- which side is thin BEHIND the quote, which no public feed publishes.
    "book_slope_asymmetry": lambda s: s["slope_asym"],
    # COST STATE -- what the book is charging to be crossed.
    "spread_state": lambda s: s["spread_bps"],
    # DYNAMIC -- which side is getting out of the way.
    "withdrawal_asymmetry": lambda s: withdrawal_asymmetry(s["depth_bid"], s["depth_ask"]),
}

```

### scripts\check_scheduler_manifest.py
```python
"""Scheduler-manifest checker (gap #58) -- can this repo still reconstitute the desk?

2026-07-29: 119/162 scripts had no in-repo scheduler reference and the live VPS crontab was
uncommitted (docs/GAP_REGISTER.md:272), so a GitHub restore yielded a desk that ran NOTHING.
ops/crontab.manifest is the reconstructed DR floor; this checker keeps it honest five ways:

  (a) every script the manifest references must exist in the repo -- a deleted-but-still-
      scheduled script is a silent nightly failure (the DEAD CRON class, scripts/wiring_audit.py:8);
  (b) every committed ops/*.timer's service ExecStart script must exist AND appear in the
      manifest, and every OnCalendar value must exactly match the manifest schedule -- the
      committed units are the one part the manifest CAN be sure of, so a unit or schedule
      missing from it means the manifest has rotted, not the box;
  (c) where `crontab -l` succeeds (the live VPS), live-vs-manifest drift is reported in BOTH
      directions: an extra live line is tomorrow's un-reconstitutable job, a missing one is a
      job the DR floor promises but the box does not run. Root paths are normalized so
      "$QUANT_ROOT" here and /home/quant/quant-platform there compare equal.
  (d) a script scheduled on several cron lines must use ONE lock path or none -- flock cannot
      serialize across distinct lock files, so two `flock -n` lines LOOK mutually exclusive and
      are not (R0326);
  (e) every scheduled .py must be able to IMPORT: its first-party imports have to resolve to a
      file in this tree. (a) catches the organ that dies on ENOENT; (e) catches the strictly
      nastier one that dies on ImportError, which is indistinguishable downstream because it
      still fires on time and still touches its log (R0359).

  (f) DUPLICATE ORGANS across ALL FOUR PLANES (2026-09-08): every live row -- cron lines,
      SYSTEMD units, the box's desks/mt5/ops/box_tasks.manifest and hourly_cycle's `_costed`
      legs -- is grouped by the script it executes, and a script with more than one live
      schedule that does not share ONE lock (one flock path on every line, or a job lock
      inside the script itself) is REPORTED. Never disabled, never an exit code: (d) already
      fails the same shape on cron alone, and the cross-plane case is the one nobody could
      see -- run_frontier_rotation.sh carried four schedules on two planes and external_gauntlet
      runs as a box task and an hourly leg at once. The report is data/duplicate_organs.json.

In this sandbox / on a fresh restore `crontab -l` fails; that path reports 'no live crontab
readable' gracefully and still runs (a)+(b) -- the repo-only checks are exactly the ones a
dead box needs. deploy/reconstitute_cron.sh refuses to install while (a) fails.

Exit: 2 on any (a)/(b) failure; 1 on live drift (suppressed by --report-only); 0 clean.
stdlib-only. --json writes data/scheduler_manifest_report.json (mkdir -p, never crashes the
check itself -- a reporting failure must not mask a scheduling truth).

    python scripts/check_scheduler_manifest.py [--json] [--report-only]
"""

from __future__ import annotations

import argparse
import ast
import json
import re
import subprocess
import sys
from collections import Counter
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
_MANIFEST_REL = "ops/crontab.manifest"
_REPORT_REL = "data/scheduler_manifest_report.json"
# the live box's repo root, hardcoded in its unit files (ops/quant-litminer.service etc.) --
# stripped when mapping ExecStart paths and when normalizing live crontab lines for the diff.
_VPS_ROOT = "/home/quant/quant-platform"
# one cron field: numerics, ranges, steps, lists, or * (day/month names unused on this desk)
_CRON_FIELD = re.compile(r"^[\d*,/-]+$")
_SCRIPT_REF = re.compile(r"(?:scripts|ops|deploy)/[A-Za-z0-9_.\-]+\.(?:py|sh)")
_KV = re.compile(r'(\w+)="([^"]*)"')
_ENV_LINE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")


@dataclass(frozen=True)
class CronEntry:
    schedule: str
    command: str
    line_no: int


@dataclass(frozen=True)
class SystemdEntry:
    unit: str
    on: str
    exec_path: str
    line_no: int


@dataclass
class Manifest:
    path: Path
    root_default: str = _VPS_ROOT
    cron: list[CronEntry] = field(default_factory=list)
    systemd: list[SystemdEntry] = field(default_factory=list)
    raw: str = ""
    parse_problems: list[str] = field(default_factory=list)


def parse_manifest(path: Path) -> Manifest:
    """Parse ops/crontab.manifest. Comments carry the evidence; only three line shapes are
    machine-active: `NAME=value` env lines, `SYSTEMD key="v" ...` unit lines, and real
    5-field cron lines. Anything else non-comment is a parse problem, reported not ignored --
    a silently skipped line would be a scheduled job the DR floor silently dropped."""
    man = Manifest(path=path)
    try:
        man.raw = path.read_text("utf-8")
    except OSError as e:
        man.parse_problems.append(f"manifest unreadable: {e}")
        return man
    for i, line in enumerate(man.raw.splitlines(), start=1):
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        if s.startswith("SYSTEMD"):
            kv = dict(_KV.findall(s))
            unit = kv.get("unit", "")
            if not unit:
                man.parse_problems.append(f"line {i}: SYSTEMD entry without unit=")
                continue
            man.systemd.append(SystemdEntry(unit=unit, on=kv.get("on", ""),
                                            exec_path=kv.get("exec", ""), line_no=i))
            continue
        if _ENV_LINE.match(s):
            name, _, value = s.partition("=")
            if name == "QUANT_ROOT" and value:
                man.root_default = value
            continue
        fields = s.split(None, 5)
        if len(fields) >= 6 and all(_CRON_FIELD.match(f) for f in fields[:5]):
            man.cron.append(CronEntry(schedule=" ".join(fields[:5]), command=fields[5],
                                      line_no=i))
        else:
            man.parse_problems.append(f"line {i}: not a comment, env, SYSTEMD or cron line: "
                                      f"{s[:80]}")
    return man


def referenced_paths(man: Manifest) -> list[str]:
    """Every repo-relative script the manifest schedules, cron and systemd planes both."""
    refs: set[str] = set()
    for c in man.cron:
        refs.update(_SCRIPT_REF.findall(c.command))
    for u in man.systemd:
        if u.exec_path:
            refs.add(u.exec_path)
    return sorted(refs)


def check_scripts_exist(root: Path, man: Manifest) -> list[str]:
    """(a) DEAD-CRON fence: a manifest that references a deleted script would reconstitute a
    desk that fails silently every tick. This is the load-bearing regression check."""
    return [p for p in referenced_paths(man) if not (root / p).is_file()]


_FLOCK_PATH = re.compile(r"\bflock\s+(?:-[a-zA-Z]+\s+)*(\S+)")


def check_lock_coherence(man: Manifest) -> list[str]:
    """(d) SAME-SCRIPT-DIFFERENT-LOCK fence (R0326). Until 2026-08-05 the manifest scheduled
    ops/run_crypto_factory.sh twice -- 30 1 under data/.cron_crypto_factory.lock and an adopted
    live twin at 30 3 under /tmp/crypto_factory.lock. Both lines LOOKED serialized because both
    said `flock -n`, but flock only excludes holders of the SAME lock file, so the two runs
    could overlap freely: mutual exclusion that reads as present and is not. A script scheduled
    on multiple cron lines must either share ONE lock path on every line or carry no flock at
    all anywhere (in which case the duplication is at least visible for what it is)."""
    locks_by_script: dict[str, set[str | None]] = {}
    lines_by_script: dict[str, list[int]] = {}
    for c in man.cron:
        m = _FLOCK_PATH.search(c.command)
        lock = m.group(1) if m is not None else None
        for script in _SCRIPT_REF.findall(c.command):
            locks_by_script.setdefault(script, set()).add(lock)
            lines_by_script.setdefault(script, []).append(c.line_no)
    problems: list[str] = []
    for script, locks in sorted(locks_by_script.items()):
        if len(lines_by_script[script]) < 2 or len(locks) < 2:
            continue
        named = ", ".join(sorted(str(x) for x in locks))
        lines = ", ".join(str(n) for n in lines_by_script[script])
        problems.append(f"{script} scheduled on lines {lines} under different locks "
                        f"({named}) -- flock cannot serialize across distinct lock files")
    return problems


#: Top-level packages that live in THIS repo. A third-party import cannot be resolved from disk
#: and is deliberately NOT checked -- but it is COUNTED, so "0 problems" can never be read as
#: "everything was checked" when the truth is "almost nothing was" (the guard-scope lesson).
_FIRST_PARTY = ("libs", "scripts", "app", "api")


def _module_on_disk(root: Path, dotted: str) -> bool:
    """Does `libs.discovery.cagr_optimizer` correspond to a file or package in this tree?

    Pure PATH resolution, never an import: this fence runs on every push, and importing 184
    organ entry points to find out whether they import would execute module-level code in all
    of them. find_spec is not an option either -- it imports parent packages.
    """
    p = root.joinpath(*dotted.split("."))
    return p.with_suffix(".py").is_file() or (p / "__init__.py").is_file()


def check_imports_resolve(root: Path, man: Manifest) -> tuple[list[str], int, int]:
    """(e) THE SILENT-IMPORTERROR FENCE. Returns (problems, n_checks, n_thirdparty_skipped).

    WHY EXISTENCE IS NOT ENOUGH, and why this is a different failure from check (a). Check (a)
    catches a manifest entry whose FILE is gone -- the organ dies on ENOENT. This catches the
    strictly nastier case where the file is present and dies on ImportError, because the two are
    indistinguishable downstream: the organ fires on time, writes a log, and every
    freshness-shaped check reads a minutes-old log and reports it healthy. "A heartbeat proves
    the loop is alive, NEVER that the pipe is."

    THE MEASURED INSTANCE (R0359). scripts/run_geometric_review.py -- the one entry point wiring
    the desk's SUPREME OBJECTIVE, E[log wealth], to something runnable -- was dead from
    2026-07-30 to 2026-08-05 importing two modules that did not exist.

    AND NOTE THE ACTUAL MECHANISM, because the row that asked for this misdiagnosed it: the
    dormancy scan was NOT blind to scripts/. It already grepped scripts/ at 3be2e3e, and
    scripts/run_geometric_review.py DID NOT EXIST in the tree that retirement was computed
    against -- it was added by fee1214a on the OTHER lineage, which is not an ancestor of
    3be2e3e. The retirement's "zero external importers" claim was TRUE of its own tree. The
    breakage was born in the MERGE that later united the two lineages: the caller arrived from
    master and the callees stayed deleted. No reachability scan on either side could have seen
    that, because neither tree was ever wrong -- only their union was. That is precisely why the
    check belongs HERE, at the schedule boundary, rather than in the dormancy hunter.
    """
    problems: list[str] = []
    n_checks = 0
    n_skipped = 0
    for rel in referenced_paths(man):
        if not rel.endswith(".py"):
            continue
        f = root / rel
        if not f.is_file():
            continue                      # already reported by check (a); not double-counted
        try:
            tree = ast.parse(f.read_text("utf-8", errors="ignore"))
        except (SyntaxError, ValueError) as e:
            problems.append(f"{rel}: does not parse ({e}) -- it cannot start at all")
            continue
        for node in ast.walk(tree):       # ast.walk, so a function-local import counts too
            if isinstance(node, ast.Import):
                for a in node.names:
                    if a.name.split(".")[0] not in _FIRST_PARTY:
                        n_skipped += 1
                        continue
                    n_checks += 1
                    if not _module_on_disk(root, a.name):
                        problems.append(f"{rel}: `import {a.name}` -- no such module in the repo")
            elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
                if node.module.split(".")[0] not in _FIRST_PARTY:
                    n_skipped += 1
                    continue
                n_checks += 1
                if not _module_on_disk(root, node.module):
                    problems.append(f"{rel}: `from {node.module} import ...` -- no such module")
                    continue
                pkg = root.joinpath(*node.module.split("."))
                init = pkg / "__init__.py"
                if not init.is_file():
                    continue
                src = init.read_text("utf-8", errors="ignore")
                for a in node.names:
                    # `import *` names nothing checkable; a re-export is matched by NAME in the
                    # package __init__ rather than by parsing it, which keeps this cheap and
                    # errs toward silence -- a false MISSING here would block every push.
                    if a.name == "*":
                        continue
                    n_checks += 1
                    if (pkg / f"{a.name}.py").is_file() or (pkg / a.name / "__init__.py").is_file():
                        continue
                    if not re.search(rf"\b{re.escape(a.name)}\b", src):
                        problems.append(f"{rel}: `from {node.module} import {a.name}` -- "
                                        f"neither a submodule nor named in {node.module}.__init__")
    return problems, n_checks, n_skipped


def _exec_script_of(service_text: str) -> str | None:
    """Last .py/.sh token of the service's ExecStart line, or None when there is none."""
    for line in service_text.splitlines():
        if line.strip().startswith("ExecStart="):
            # A unit written as `/bin/bash -c './ops/gates.sh --full ...'` hands whitespace
            # tokenisation the QUOTE as part of the path, and `./ops/gates.sh` then failed both
            # the exists check and the manifest lookup for a script that is right there --
            # the same stripping _unit_scripts already does for installed units.
            tokens = [t.strip("'\"") for t in line.strip().removeprefix("ExecStart=").split()]
            hits = [t for t in tokens if t.endswith((".py", ".sh"))]
            if hits:
                return hits[-1].removeprefix("./")
    return None


def _working_dir_of(service_text: str) -> str | None:
    """The unit's WorkingDirectory, mapped onto this repo, or None when it declares none.

    SYSTEMD RESOLVES A RELATIVE ExecStart AGAINST WorkingDirectory, and ignoring that produced a
    false BREACH that blocked the trading box's push. `quant-nightly-catchup.service` declares
    WorkingDirectory=<root>/desks/mt5 and runs `research/nightly_catchup.py`, which is correct and
    on disk -- but resolved against the REPO ROOT it looks absent, so the fence reported a dead
    unit for an organ that runs fine. Worse, that organ is the one whose `enrol_clocks` step puts
    certified sleeves on forward clocks, so the false report pointed away from working machinery.

    This file's own standing rule for a false positive is to fix the CHECK, never to reword the
    organ to satisfy it.
    """
    for line in service_text.splitlines():
        stripped = line.strip()
        if stripped.startswith("WorkingDirectory=") and not stripped.startswith("#"):
            wd = stripped.removeprefix("WorkingDirectory=").strip().strip("'\"")
            if wd.startswith(_VPS_ROOT + "/"):
                return wd[len(_VPS_ROOT) + 1:]
            if wd == _VPS_ROOT:
                return ""
            return None if wd.startswith("/") else wd
    return None


def _to_repo_rel(root: Path, path_str: str, work_dir: str | None = None) -> str:
    """Map a unit-file ExecStart path (VPS-absolute) onto this repo. Strip the known VPS
    prefix first; fall back to basename search under ops/ then scripts/ so a moved checkout
    still resolves; return the raw string when unmappable (it will fail the exists check,
    which is the honest outcome)."""
    if path_str.startswith(_VPS_ROOT + "/"):
        return path_str[len(_VPS_ROOT) + 1:]
    if not path_str.startswith("/"):
        # RELATIVE TO THE UNIT'S WorkingDirectory, exactly as systemd resolves it.
        if work_dir:
            joined = f"{work_dir.rstrip('/')}/{path_str}"
            if (root / joined).is_file():
                return joined
        return path_str
    base = Path(path_str).name
    for cand in (f"ops/{base}", f"scripts/{base}"):
        if (root / cand).is_file():
            return cand
    return path_str


def _on_calendar_values(timer_text: str) -> list[str]:
    """Return active OnCalendar expressions exactly as systemd will parse them."""
    values: list[str] = []
    for line in timer_text.splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith("#") and stripped.startswith("OnCalendar="):
            values.append(stripped.removeprefix("OnCalendar=").strip())
    return values


def check_committed_timers(root: Path, man: Manifest) -> list[str]:
    """Fence committed timer wiring and exact calendar agreement with the manifest.

    The unit files are executable ground truth. A manifest that names the right script but a
    different time is not reconstitutable: it certifies one cadence and deploys another.
    """
    problems: list[str] = []
    for timer in sorted((root / "ops").glob("*.timer")):
        service = timer.with_suffix(".service")
        rel_timer = timer.relative_to(root).as_posix()
        if not service.is_file():
            problems.append(f"{rel_timer}: no companion {service.name} committed")
            continue
        service_text = service.read_text("utf-8")
        exec_raw = _exec_script_of(service_text)
        if exec_raw is None:
            problems.append(f"{service.relative_to(root).as_posix()}: no ExecStart script")
            continue
        rel = _to_repo_rel(root, exec_raw, _working_dir_of(service_text))
        if not (root / rel).is_file():
            problems.append(f"{rel_timer}: ExecStart script {rel} does not exist in repo")
        if rel not in man.raw:
            problems.append(
                f"{rel_timer}: ExecStart script {rel} is absent from the manifest"
                " -- the manifest has rotted behind the committed units"
            )

        calendars = _on_calendar_values(timer.read_text("utf-8"))
        if not calendars:
            continue
        entries = [entry for entry in man.systemd if entry.unit == timer.name]
        if len(entries) != 1:
            problems.append(
                f"{rel_timer}: expected exactly one matching SYSTEMD entry, found {len(entries)}"
            )
            continue
        if len(calendars) != 1:
            problems.append(
                f"{rel_timer}: expected exactly one OnCalendar value, found {len(calendars)}"
            )
            continue
        actual = calendars[0]
        declared = entries[0].on
        if actual != declared:
            problems.append(
                f"{rel_timer}: OnCalendar={actual!r} does not exactly match manifest "
                f"on={declared!r}"
            )
    return problems


def read_live_crontab() -> str | None:
    """`crontab -l`, or None wherever that is impossible (no binary, no crontab for user --
    the sandbox and any fresh restore land here; that is a report line, never a crash)."""
    try:
        r = subprocess.run(["crontab", "-l"], capture_output=True, text=True, timeout=10,
                           check=False)
    except (OSError, subprocess.SubprocessError):
        return None
    return r.stdout if r.returncode == 0 else None


def _norm(line: str, roots: list[str]) -> str:
    """Whitespace-collapse + root-path normalization so the same job compares equal whether
    it is written against $QUANT_ROOT, the VPS path, or this checkout's path."""
    s = " ".join(line.split())
    for r in roots:
        if r:
            s = s.replace(r, "<ROOT>")
    return s.replace('"<ROOT>"', "<ROOT>")


def diff_live(root: Path, man: Manifest, live: str) -> tuple[list[str], list[str], list[str]]:
    """(c) both-direction drift: (missing_in_live, extra_in_live, duplicated_in_live), normalized.

    COMPARED AS A MULTISET, AND THAT IS THE WHOLE POINT. This compared `set`s until 2026-08-01, so
    a job scheduled TWICE was invisible: set subtraction collapses the copies and both differences
    come back empty. Measured on this box the day it was fixed -- 154 live job lines against 137
    manifest entries, and the fence printed "matches manifest (normalized)" and exited OK while 17
    jobs ran twice. The legacy pre-marker block was an exact duplicate of the managed block, which
    is precisely the shape a set cannot see; 14 of the 17 were saved from real concurrency only by
    `flock -n`, and the other 3 genuinely double-ran.

    A fence that reports OK on a real breach is worse than no fence: it is the breach plus a
    certificate saying there isn't one.
    """
    roots = ["${QUANT_ROOT}", "$QUANT_ROOT", _VPS_ROOT, man.root_default, str(root)]
    want = Counter(_norm(f"{c.schedule} {c.command}", roots) for c in man.cron)
    have: Counter[str] = Counter()
    for line in live.splitlines():
        s = line.strip()
        if not s or s.startswith("#") or _ENV_LINE.match(s):
            continue
        have[_norm(s, roots)] += 1
    missing_in_live = sorted(want - have)          # in manifest, not (enough) on the box
    extra_in_live = sorted(set(have) - set(want))  # on the box, unknown to the manifest
    # Scheduled more times than the manifest declares -- the case set-difference erased.
    duplicated = sorted(f"{k} (live x{have[k]}, manifest x{want[k]})"
                        for k in want if have[k] > want[k])
    return missing_in_live, extra_in_live, duplicated


# ---------------------------------------------------------------------------------------------
# THE SECOND AND THIRD SCHEDULER PLANES (added 2026-08-29)
#
# This fence compared the manifest against `crontab -l` ALONE. That was true when it was written
# and stopped being true on 2026-08-20, when root `cron.service` OOM-died and the desk migrated
# its live jobs onto systemd USER timers plus scripts/run_manifest_dispatch.py. From that day the
# fence printed 232 identical `DRIFT manifest-only (box does not run it)` lines -- including one
# for every row that WAS running perfectly well under a timer -- and a fence whose every line is
# noise cannot signal the one line that matters. The 08-20 death itself hid inside this output
# for six days.
#
# A row is COVERED when some executor demonstrably runs it, and the three planes are asked in
# order of evidence strength: the dispatcher's state file records that a row ACTUALLY FIRED and
# when; a unit's ExecStart records that something is CONFIGURED to run it. Neither is a claim
# from the manifest about itself, which is the only kind of evidence this fence must not accept.
# ---------------------------------------------------------------------------------------------

_UNIT_DIRS = (Path.home() / ".config/systemd/user", Path("/etc/systemd/system"))
_SCRIPT_TOKEN = re.compile(r"[\w/.\-]+\.(?:py|sh)")
_DISPATCH_STATE_REL = "data/manifest_dispatch_state.json"
#: A dispatcher row counts as covering the manifest only if it fired inside this window. A row
#: that fired once a fortnight ago is a dead row with a memory, not a live executor.
_DISPATCH_FRESH_H = 26.0 * 7


def _unit_scripts() -> set[str]:
    """Every script basename named by an installed unit's ExecStart, both planes.

    Basename and not full path on purpose: units invoke scripts through wrappers, `flock`,
    `/bin/bash -c '...'` and quoted forms, and a path-exact match would report a running organ as
    dead. The failure direction of a basename match is a false COVERED, which this fence reports
    as a count rather than silence so the looseness stays visible.
    """
    found: set[str] = set()
    for d in _UNIT_DIRS:
        try:
            units = list(d.glob("*.service"))
        except OSError:
            continue
        for u in units:
            try:
                txt = u.read_text("utf-8", errors="replace")
            except OSError:
                continue
            for line in txt.splitlines():
                if line.strip().startswith("ExecStart"):
                    for m in _SCRIPT_TOKEN.finditer(line):
                        found.add(m.group(0).strip("'\"").split("/")[-1])
    return found


def _dispatched_scripts(root: Path, now: datetime | None = None) -> set[str]:
    """Script basenames the manifest dispatcher has actually fired inside the freshness window."""
    now = now or datetime.now(UTC)
    try:
        state = json.loads((root / _DISPATCH_STATE_REL).read_text("utf-8"))
    except (OSError, json.JSONDecodeError):
        return set()
    live: set[str] = set()
    for token, row in (state.get("rows") or {}).items():
        try:
            fired = datetime.fromisoformat(str(row.get("last_fired", "")))
        except ValueError:
            continue
        if (now - fired).total_seconds() / 3600.0 <= _DISPATCH_FRESH_H:
            live.add(str(token).split("/")[-1])
    return live


def split_by_plane(root: Path, drift_missing: list[str]) -> tuple[list[str], dict[str, int]]:
    """Rows the crontab does not run, split into GENUINELY uncovered and covered-elsewhere.

    Returns the uncovered rows (the real drift) and a per-plane count of what was absorbed, so
    the coverage claim carries its own denominator instead of quietly shrinking the number.
    """
    units, dispatched = _unit_scripts(), _dispatched_scripts(root)
    uncovered: list[str] = []
    absorbed = {"systemd_unit": 0, "manifest_dispatcher": 0}
    for row in drift_missing:
        names = {m.group(0).split("/")[-1] for m in _SCRIPT_TOKEN.finditer(row)}
        if names & dispatched:
            absorbed["manifest_dispatcher"] += 1
        elif names & units:
            absorbed["systemd_unit"] += 1
        else:
            uncovered.append(row)
    return uncovered, absorbed


# ---------------------------------------------------------------------------------------------
# (f) DUPLICATE ORGANS -- one script, several live schedules, no shared lock
# ---------------------------------------------------------------------------------------------

_BOX_TASKS_REL = "desks/mt5/ops/box_tasks.manifest"
_HOURLY_REL = "desks/mt5/research/hourly_cycle.py"
_DUP_REPORT_REL = "data/duplicate_organs.json"
_TASK_LINE = re.compile(r"^TASK\s+(.*)$")
_COSTED = re.compile(r'_costed\(\s*"([A-Za-z0-9_]+)"\s*,\s*([A-Za-z0-9_.]+)')
_PRODUCER = re.compile(r'_producer\(\s*"([A-Za-z0-9_]+)"\s*,\s*"([^"]+)"')
_DEF = re.compile(r"^def ([A-Za-z0-9_]+)\(", re.M)
#: A script that serialises ITSELF: the desk's own job lock (research.job_lock.exclusive_job),
#: a flock in a shell wrapper, or a raw file lock. Any of these makes every schedule of the
#: script wait on the same lock, whichever plane fired it.
_SELF_LOCK = re.compile(r"exclusive_job\(|job_lock|\bflock\b|fcntl\.(?:flock|lockf)|"
                        r"msvcrt\.locking|single_instance")
SERIALISED, UNSERIALISED = "SERIALISED", "UNSERIALISED"


@dataclass(frozen=True)
class ScheduleRow:
    plane: str        # cron | systemd | box_task | hourly_leg
    script: str       # repo-relative path, or `hourly_cycle:<leg>` for an in-process leg
    schedule: str
    lock: str | None
    where: str        # manifest line, unit, task name or leg -- for the report


def _box_rows(root: Path) -> tuple[list[ScheduleRow], str]:
    p = root / _BOX_TASKS_REL
    try:
        text = p.read_text("utf-8")
    except OSError:
        return [], f"{_BOX_TASKS_REL}: absent"
    rows: list[ScheduleRow] = []
    for i, line in enumerate(text.splitlines(), start=1):
        m = _TASK_LINE.match(line.strip())
        if not m:
            continue
        kv = dict(_KV.findall(m.group(1)))
        runs = kv.get("runs", "")
        if not runs or runs == "UNKNOWN" or not runs.endswith((".py", ".sh", ".ps1", ".cmd")):
            continue
        rows.append(ScheduleRow("box_task", runs, kv.get("trigger", "UNDECLARED"), None,
                                f"{kv.get('name', '?')} (line {i})"))
    return rows, f"{_BOX_TASKS_REL}: {len(rows)} task row(s) naming a script"


def _hourly_rows(root: Path) -> tuple[list[ScheduleRow], str]:
    p = root / _HOURLY_REL
    try:
        src = p.read_text("utf-8", errors="ignore")
    except OSError:
        return [], f"{_HOURLY_REL}: absent"
    # The body of every top-level def, so a leg's callee can be searched for the script it
    # runs: `_costed("deep_forest", deep_forest)` wraps `_producer("deep_forest_miner",
    # "research/deep_forest_miner.py")`, and the leg name is not the file's name.
    defs = list(_DEF.finditer(src))
    bodies = {m.group(1): src[m.end():(defs[i + 1].start() if i + 1 < len(defs) else len(src))]
              for i, m in enumerate(defs)}
    rows: list[ScheduleRow] = []
    seen: set[str] = set()
    for m in _COSTED.finditer(src):
        leg, callee = m.group(1), m.group(2)
        if leg in seen:
            continue
        seen.add(leg)
        line = src[src.rfind("\n", 0, m.start()) + 1:src.find("\n", m.end())]
        pm = _PRODUCER.search(line) or _PRODUCER.search(bodies.get(callee, ""))
        path = pm.group(2) if pm else None
        script = f"hourly_cycle:{leg}"
        cands = ([path, f"desks/mt5/{path}"] if path else []) + [
            f"desks/mt5/research/{leg}.py", f"desks/mt5/scripts/{leg}.py", f"scripts/{leg}.py"]
        for c in cands:
            if (root / c).is_file():
                script = c
                break
        rows.append(ScheduleRow("hourly_leg", script, "hourly_cycle leg (every hour)", None,
                                f"_costed({leg!r})"))
    return rows, f"{_HOURLY_REL}: {len(rows)} _costed leg(s)"


def schedule_rows(root: Path, man: Manifest) -> tuple[list[ScheduleRow], dict[str, str]]:
    """Every live schedule on the four planes, one row per (plane, script)."""
    rows: list[ScheduleRow] = []
    for c in man.cron:
        m = _FLOCK_PATH.search(c.command)
        lock = m.group(1) if m is not None else None
        for script in _SCRIPT_REF.findall(c.command):
            rows.append(ScheduleRow("cron", script, c.schedule, lock, f"line {c.line_no}"))
    for u in man.systemd:
        if u.exec_path:
            rows.append(ScheduleRow("systemd", u.exec_path, u.on, None, u.unit))
    box, box_note = _box_rows(root)
    hourly, hourly_note = _hourly_rows(root)
    rows.extend(box)
    rows.extend(hourly)
    return rows, {"cron": f"{_MANIFEST_REL}: {len(man.cron)} live cron line(s)",
                  "systemd": f"{_MANIFEST_REL}: {len(man.systemd)} SYSTEMD row(s)",
                  "box_tasks": box_note, "hourly_cycle": hourly_note}


def _organ_key(script: str) -> str:
    """Group by the executed file's stem: `ops/run_x.sh`, `/home/quant/.../run_x.sh` and a
    box task naming `desks/mt5/scripts/x.py` beside an hourly leg `x` are one organ."""
    return Path(script.split(":", 1)[1] if script.startswith("hourly_cycle:") else script).stem


def _self_lock_evidence(root: Path, scripts: set[str]) -> str:
    for s in sorted(scripts):
        if s.startswith("hourly_cycle:"):
            continue
        try:
            src = (root / _to_repo_rel(root, s)).read_text("utf-8", errors="ignore")
        except OSError:
            continue
        m = _SELF_LOCK.search(src)
        if m:
            return f"{s}: {m.group(0)}"
    return ""


def check_duplicate_organs(root: Path, man: Manifest) -> dict:
    """(f) Report every organ with more than one live schedule and whether one lock covers
    them all. REPORT ONLY: nothing here changes an exit code or a schedule."""
    rows, planes = schedule_rows(root, man)
    by_key: dict[str, list[ScheduleRow]] = {}
    for r in rows:
        by_key.setdefault(_organ_key(r.script), []).append(r)
    groups: dict[str, dict] = {}
    for key, rs in sorted(by_key.items()):
        if len(rs) < 2:
            continue
        locks = sorted({r.lock for r in rs if r.lock})
        one_lock_everywhere = len(locks) == 1 and all(r.lock for r in rs)
        evidence = _self_lock_evidence(root, {r.script for r in rs})
        serialised = one_lock_everywhere or bool(evidence)
        why = ("every schedule takes the same flock path" if one_lock_everywhere else
               f"the script serialises itself ({evidence})" if evidence else
               (f"{len(locks)} distinct flock path(s) across {len(rs)} schedules and no lock "
                f"inside the script: the runs can overlap" if locks else
                f"{len(rs)} schedules, no flock on any line and no lock inside the script"))
        groups[key] = {"n_schedules": len(rs), "planes": sorted({r.plane for r in rs}),
                       "scripts": sorted({r.script for r in rs}), "locks": locks,
                       "self_lock": evidence or None,
                       "verdict": SERIALISED if serialised else UNSERIALISED, "why": why,
                       "rows": [asdict(r) for r in rs]}
    unser = sorted(k for k, g in groups.items() if g["verdict"] == UNSERIALISED)
    return {"n_rows": len(rows),
            "by_plane": {p: sum(1 for r in rows if r.plane == p)
                         for p in ("cron", "systemd", "box_task", "hourly_leg")},
            "planes_read": planes, "n_duplicated": len(groups), "unserialised": unser,
            "serialised": sorted(k for k in groups if k not in unser), "groups": groups,
            "note": ("REPORT ONLY. A script on more than one live schedule is SERIALISED when "
                     "every line takes one flock path or the script holds its own job lock, "
                     "else UNSERIALISED -- the runs can overlap. Nothing here disables a "
                     "schedule or fails the check; a person decides which schedule to keep.")}


def write_duplicate_report(root: Path, report: dict) -> Path | None:
    out = root / _DUP_REPORT_REL
    try:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps({"generated_utc": datetime.now(UTC).isoformat(
            timespec="seconds"), **report}, indent=1) + "\n", "utf-8")
        return out
    except OSError as e:                              # reporting must never mask the check
        print(f"  duplicate-organ report unwritable ({e}) -- check result stands",
              file=sys.stderr)
        return None


def repair_schedules(root: Path, man: object) -> list[str]:
    """Rewrite a committed timer's OnCalendar to the manifest's, and say so.

    WHY REPAIR AND NOT ONLY REPORT (2026-09-04). The schedule is declared TWICE -- once in
    `ops/crontab.manifest` and once in a committed `ops/*.timer` -- and two sources of truth drift.
    Measured today: the manifest was corrected to run certify_gauntlet HOURLY and committed, while
    `ops/quant-certify-gauntlet.timer` still said `05:10:00`. An installer copies the ops/ timer
    over the live unit, so every hand-edit to ~/.config was silently undone within the hour, three
    times, and the gauntlet -- the job that MINTS certificates -- kept falling back to daily while
    the desk was asked to grow hourly.

    THE MANIFEST WINS, because it is the file the desk already calls its single source of truth and
    the one a reviewer reads. This only ever rewrites the timer TO the manifest, never the reverse:
    a schedule change is a manifest edit, reviewed and committed, and this closes the gap that let
    an unreviewed copy override it.
    """
    out: list[str] = []
    for timer in sorted((root / "ops").glob("*.timer")):
        try:
            text = timer.read_text("utf-8")
        except OSError:
            continue
        cals = [ln.strip().removeprefix("OnCalendar=").strip()
                for ln in text.splitlines()
                if ln.strip().startswith("OnCalendar=")]
        if len(cals) != 1:
            continue
        entries = [e for e in getattr(man, "systemd_entries", []) or []
                   if getattr(e, "timer", "") == timer.name]
        if len(entries) != 1:
            continue
        declared = getattr(entries[0], "on", "")
        if not declared or declared == cals[0]:
            continue
        timer.write_text(text.replace(f"OnCalendar={cals[0]}", f"OnCalendar={declared}", 1),
                         "utf-8")
        out.append(f"  REPAIRED {timer.name}: OnCalendar {cals[0]!r} -> {declared!r} "
                   f"(manifest is the source of truth)")
    return out or ["  schedules: every committed timer already matches the manifest"]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--json", action="store_true",
                    help=f"also write {_REPORT_REL} (machine-readable)")
    ap.add_argument("--report-only", action="store_true",
                    help="report live-crontab drift without failing on it "
                         "(missing scripts / rotted timers still exit 2)")
    ap.add_argument("--root", type=Path, default=_ROOT,
                    help="repo root (tests point this at fixture trees)")
    ap.add_argument("--fix-schedules", action="store_true",
                    help="repair a committed timer whose OnCalendar disagrees with the manifest")
    args = ap.parse_args(argv)
    root: Path = args.root.resolve()

    man = parse_manifest(root / _MANIFEST_REL)
    missing = check_scripts_exist(root, man)
    if args.fix_schedules:
        for line in repair_schedules(root, man):
            print(line)
    timer_problems = check_committed_timers(root, man)
    lock_problems = check_lock_coherence(man)
    import_problems, n_import_checks, n_thirdparty = check_imports_resolve(root, man)
    structural = list(man.parse_problems) + timer_problems + lock_problems + import_problems

    live = read_live_crontab()
    drift_missing: list[str] = []
    drift_extra: list[str] = []
    drift_dupes: list[str] = []
    if live is not None:
        drift_missing, drift_extra, drift_dupes = diff_live(root, man, live)

    print(f"scheduler-manifest check | {len(man.cron)} cron entries, "
          f"{len(man.systemd)} systemd entries, {len(referenced_paths(man))} scripts referenced")
    for p in man.parse_problems:
        print(f"  PARSE   {p}")
    for m in missing:
        print(f"  MISSING {m} -- scheduled by the manifest but absent from the repo (dead cron)")
    for p in timer_problems:
        print(f"  TIMER   {p}")
    for p in lock_problems:
        print(f"  LOCK    {p}")
    for p in import_problems:
        print(f"  IMPORT  {p}")
    # L1.57: the denominator is what this RUN resolved, not a roster length. `0 problems` over 0
    # checks is VACUOUS, and printing the count is what makes the difference legible.
    print(f"  imports: {n_import_checks} first-party resolved, "
          f"{n_thirdparty} third-party NOT CHECKED (unresolvable from disk)")
    # (f) duplicate organs, across all four planes. Reported, never an exit code.
    dup = check_duplicate_organs(root, man)
    for key in dup["unserialised"]:
        g = dup["groups"][key]
        print(f"  DUPLICATE {key}: {g['n_schedules']} live schedules on "
              f"{'+'.join(g['planes'])} -- {UNSERIALISED}: {g['why']}")
    dup_out = write_duplicate_report(root, dup)
    print(f"  duplicate organs: {dup['n_rows']} live rows on 4 planes "
          f"({', '.join(f'{k}={v}' for k, v in dup['by_plane'].items())}), "
          f"{dup['n_duplicated']} organ(s) on >1 schedule, {len(dup['unserialised'])} "
          f"unserialised (reported, never disabled)" + (f" -> {dup_out}" if dup_out else ""))
    if live is None:
        print("  live crontab: no live crontab readable (sandbox/fresh restore) -- "
              "repo-only checks (a)+(b) still ran")
    else:
        uncovered, absorbed = split_by_plane(root, drift_missing)
        for d in uncovered:
            print(f"  DRIFT   run by NOTHING on any plane: {d}")
        if absorbed["systemd_unit"] or absorbed["manifest_dispatcher"]:
            print(f"  PLANE   {absorbed['manifest_dispatcher']} manifest row(s) covered by the "
                  f"dispatcher (fired within {_DISPATCH_FRESH_H / 24:.0f}d), "
                  f"{absorbed['systemd_unit']} by an installed systemd unit -- "
                  "not cron drift, and not counted as such")
        for d in drift_extra:
            print(f"  DRIFT   live-only (repo cannot reconstitute it): {d}")
        for d in drift_dupes:
            print(f"  DUPE    scheduled more often than declared: {d}")
        if not (uncovered or drift_extra or drift_dupes):
            print("  live crontab: matches manifest (normalized, multiset)")

    exit_code = 0
    if missing or structural:
        exit_code = 2
    elif (drift_missing or drift_extra or drift_dupes) and not args.report_only:
        exit_code = 1

    if args.json:
        report = {
            "generated_utc": datetime.now(tz=UTC).isoformat(timespec="seconds"),
            "manifest": _MANIFEST_REL,
            "cron_entries": len(man.cron),
            "systemd_entries": len(man.systemd),
            "referenced_scripts": referenced_paths(man),
            "checks": {
                "scripts_exist": {"ok": not missing, "missing": missing},
                "committed_timers": {"ok": not timer_problems, "problems": timer_problems},
                "lock_coherence": {"ok": not lock_problems, "problems": lock_problems},
                "imports_resolve": {"ok": not import_problems, "problems": import_problems,
                                    "n_first_party_checked": n_import_checks,
                                    "n_third_party_unchecked": n_thirdparty},
                "parse": {"ok": not man.parse_problems, "problems": man.parse_problems},
                # (f) never affects exit_code; `ok` here means "nothing unserialised", and
                # the full groups live in data/duplicate_organs.json.
                "duplicate_organs": {"ok": not dup["unserialised"],
                                     "n_duplicated": dup["n_duplicated"],
                                     "unserialised": dup["unserialised"],
                                     "serialised": dup["serialised"],
                                     "report": _DUP_REPORT_REL},
                "live_crontab": {
                    "readable": live is not None,
                    "note": None if live is not None else "no live crontab readable",
                    "missing_in_live": drift_missing,
                    "extra_in_live": drift_extra,
                    "duplicated_in_live": drift_dupes,
                },
            },
            "exit_code": exit_code,
        }
        out = root / _REPORT_REL
        try:
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(json.dumps(report, indent=1) + "\n", "utf-8")
            print(f"  -> {out}")
        except OSError as e:  # reporting must never mask the check result
            print(f"  json report unwritable ({e}) -- check result stands", file=sys.stderr)

    verdict = {0: "OK", 1: "DRIFT", 2: "BROKEN"}[exit_code]
    print(f"scheduler-manifest: {verdict}")
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())

```

### scripts\run_type2_report.py
```python
#!/usr/bin/env python3
"""TYPE-II COST REPORT -- label every recorded negative on this checkout with its own power.

    python -u scripts/run_type2_report.py [--json data/type2_cost.json] [--root .]

WHAT THIS ANSWERS. The desk has produced zero survivors across every screen it runs, and each zero
is written down as "no edge found". This walks the negatives that are ACTUALLY ON DISK and asks one
question of each: could this rejection have SEEN an edge of the size the desk is looking for? A
rejection that could not is absence of evidence and must never be read as evidence of absence.

READS ONLY, WRITES ONE ARTIFACT. It changes no verdict, no threshold and no gate; alpha stays 0.05.
An UNDERPOWERED label is a statement about what the desk KNOWS, never a licence to re-open a
graveyard row -- the graveyard is permanent by construction.

WHAT IT REFUSES TO DO. Artifacts named in the docs but absent from this checkout (runtime-only
files that live on the VPS) are reported as NOT-READABLE-HERE with the reason, never reconstructed
from the prose that cites them. And graveyard rows are labelled INDETERMINATE rather than parsed
for a sample size: the rows contain digits, but "n=5 majors" is a symbol count and "180 bars" is a
per-symbol length, and a regex that cannot tell those apart would MANUFACTURE the evidence whose
absence is the finding. Every row here is computed from a machine-readable field an artifact
actually records.

THE MULTIPLICITY EACH ROW IS CHARGED is the one its own gate applied, taken from the artifact:
the campaign's candidate count for campaign rows, the mechanism count for pooled rows, the
deflation config count for the intraday runs, and N=1 for the Stage-A screens -- whose `powered`
flag is itself computed at N=1, so this module reproduces the screen rather than re-judging it.
Where an artifact records no multiplicity, N=1 is used: the smallest it can be, and therefore the
reading most favourable to the desk's claim of knowledge.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import sys
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_ROOT = Path("/home/quant/quant-platform")
if not _ROOT.exists():
    _ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from libs.validation.type2_cost import (  # noqa: E402
    CROSS_SYMBOL_STRATEGY_CORR,
    DECLARED_CORRELATION_EFFECTS,
    DECLARED_SHARPES,
    DEFAULT_ALPHA,
    POWERED,
    PPY,
    REFERENCE_CORRELATION_EFFECT,
    REFERENCE_SHARPE,
    UNDERPOWERED,
    Type2Cost,
    correlation_negative,
    headline,
    indeterminate,
    sharpe_negative,
)

_DEFAULT_OUT = Path("data/type2_cost.json")

#: The measured-context documents this instrument is built on. Their EXISTENCE is verified and
#: reported; their contents are cited, never re-derived here.
#: The measured context this report cites, each declared TRACKED or RUNTIME.
#:
#: THE DISTINCTION IS LOAD-BEARING AND WAS MISSING. A tracked citation that is absent is a
#: DANGLING REFERENCE -- a doc deleted or renamed, and this report now cites nothing. A runtime
#: citation that is absent is the ordinary state of any clean checkout, because reports/ is
#: gitignored wholesale (.gitignore:51). Collapsing the two made "is this artifact present" a
#: question about the BOX rather than the repo, and the walker's end-to-end test asserted all four
#: present -- so it went red on every checkout that had not happened to run that producer. A
#: verdict about the HOST is not a verdict about the DESK.
_CITATIONS: tuple[tuple[str, bool], ...] = (
    ("docs/research/gate_power_audit.md", False),
    ("docs/research/REALITY_CHECK_POWER.md", False),
    ("libs/research/axis_screen.py", False),
    # reports/ is gitignored: produced by run_reality_check_audit on whichever box ran it.
    ("reports/reality_check_audit.json", True),
)

#: Bars per year by artifact interval. The intraday runs differ ONLY in bar size and cover the same
#: 61 out-of-sample days, so converting each with its own clock is what stops the 5-minute run from
#: reading as twelve times the evidence of the hourly one. t = SR_ann * sqrt(YEARS): bar count is
#: not evidence.
_BARS_PER_YEAR = {"5m": 365.0 * 24 * 12, "15m": 365.0 * 24 * 4, "1h": 365.0 * 24}

#: Declared effect sizes for the token-unlock event study, which is on a standardised-mean scale
#: rather than an IC scale. DECLARED IN THIS FILE, in advance, and stated in the artifact: a 0.2
#: standardised abnormal return is a small-but-real event effect. Power at a declared effect is the
#: question; power at the OBSERVED effect would be a restatement of the p-value.
_UNLOCK_EFFECTS = (0.1, 0.2, 0.3)
_UNLOCK_REFERENCE = 0.2


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text("utf-8"))
    except (OSError, ValueError):
        return None


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


# ------------------------------------------------------------------------------ docs/graveyard.md


def _graveyard_rows(text: str) -> list[tuple[str, str]]:
    """(hypothesis, verdict) for every kill row in a table whose first header cell is 'Hypothesis'.

    Scoped by header on purpose: docs/graveyard.md also carries an era/venue table that is
    narrative, not a list of rejections, and counting its rows as negatives would inflate the
    denominator with things that were never tested.

    A table is opened by a `|---|` separator and identified by the pipe row immediately above it,
    and it stays open across intervening PROSE. The first draft closed the table on any non-pipe
    line and silently lost 26 of 44 kills to the "Standing conclusion" paragraph sitting in the
    middle of one -- an undercount that would have flattered the headline by dropping unlabellable
    rows from the denominator, which is the exact defect this instrument names.
    """
    rows: list[tuple[str, str]] = []
    in_kill_table = False
    pending: list[str] | None = None

    def commit() -> None:
        if pending is not None and in_kill_table and len(pending) >= 2:
            rows.append((pending[0], pending[1]))

    for line in text.splitlines():
        s = line.strip()
        if not s.startswith("|"):
            continue
        cells = [c.strip() for c in s.strip("|").split("|")]
        if not cells:
            continue
        if all(c and set(c) <= {"-", ":"} for c in cells):
            # A separator identifies the row above it as a HEADER, so that row is discarded rather
            # than committed and the table's kind is decided from it.
            in_kill_table = pending is not None and pending[0].lower().startswith("hypothesis")
            pending = None
            continue
        commit()
        pending = cells
    commit()
    return rows


def read_graveyard(root: Path) -> tuple[list[Type2Cost], list[dict[str, Any]]]:
    p = root / "docs/graveyard.md"
    if not p.exists():
        return [], [{"artifact": str(p), "status": "NOT-READABLE-HERE", "why": "file absent"}]
    out: list[Type2Cost] = []
    for name, verdict in _graveyard_rows(p.read_text("utf-8")):
        clean = re.sub(r"\s+", " ", re.sub(r"[`*]", "", name)).strip()
        mentions = bool(re.search(r"\bn\s*=|\bbars\b|\bdays\b|\bobs\b|\bd\b", verdict))
        out.append(
            indeterminate(
                clean[:110],
                "permanent kill recorded with a verdict but NO machine-readable sample size, so "
                "whether it is 'looked and it is not there' or 'could not have seen it' cannot be "
                "determined from the row"
                + (
                    " (the prose mentions a sample quantity; it is NOT parsed here because the "
                    "same tokens denote symbol counts and per-symbol lengths in adjacent rows)"
                    if mentions
                    else ""
                ),
                source="docs/graveyard.md",
            )
        )
    return out, []


# ------------------------------------------------------------ reports/real_campaign*.json


def read_real_campaigns(root: Path) -> tuple[list[Type2Cost], list[dict[str, Any]]]:
    out: list[Type2Cost] = []
    unread: list[dict[str, Any]] = []
    seen: dict[str, str] = {}
    for p in sorted((root / "reports").glob("real_campaign*.json")):
        d = _read_json(p)
        if not isinstance(d, dict):
            unread.append(
                {"artifact": str(p), "status": "NOT-READABLE-HERE", "why": "unparseable JSON"}
            )
            continue
        dig = _digest(p)
        if dig in seen:
            unread.append(
                {
                    "artifact": str(p),
                    "status": "DUPLICATE",
                    "why": f"byte-identical to {seen[dig]}; counted once",
                }
            )
            continue
        seen[dig] = p.name
        out.extend(_campaign_costs(p.name, d))
    return out, unread


def _campaign_costs(stem: str, d: dict[str, Any]) -> list[Type2Cost]:
    bars: dict[str, float] = {str(k): float(v) for k, v in (d.get("bars_per_symbol") or {}).items()}
    shortest = min(bars.values()) if bars else 0.0
    n_cand = int(d.get("n_candidates") or 0)
    out: list[Type2Cost] = []

    out.append(
        sharpe_negative(
            f"CAMPAIGN {stem}: 0 of {n_cand} candidates clear every gate",
            source=f"reports/{stem}",
            n_bars=shortest,
            ppy=PPY,
            n_tests=max(1, n_cand),
            note=(
                "per-symbol daily campaign; multiplicity charged at the recorded candidate count, "
                "elapsed time at the SHORTEST symbol history in the panel"
            ),
        )
    )

    pooled = d.get("pooled_by_mechanism") or {}
    n_mech = int(pooled.get("n_mechanisms") or 0)
    for row in pooled.get("rows") or []:
        syms = [str(s) for s in row.get("symbols") or []]
        n_units = int(row.get("n_symbols") or len(syms) or 1)
        # THE SHORTEST CONSTITUENT HISTORY, because the artifact does not record the length of the
        # pooled series itself. Taking the shortest is a LOWER bound on the elapsed evidence, so it
        # can only under-state power and over-state how blind the test was -- the direction that
        # claims less. Taking the longest would credit the pooled series with history that only
        # some of its symbols have.
        n_bars = min((bars[s] for s in syms if s in bars), default=shortest)
        out.append(
            sharpe_negative(
                str(row.get("name") or "pooled"),
                source=f"reports/{stem}#pooled",
                n_bars=n_bars,
                ppy=PPY,
                n_tests=max(1, n_mech),
                n_units=n_units,
                cross_corr=CROSS_SYMBOL_STRATEGY_CORR,
                note=(
                    f"pooled across {n_units} symbols at the measured same-mechanism cross-symbol "
                    f"strategy correlation {CROSS_SYMBOL_STRATEGY_CORR}; failed "
                    f"{','.join(str(g) for g in row.get('failed_gates') or []) or 'nothing'}"
                ),
            )
        )

    for row in d.get("top_by_oos") or []:
        failed = [str(g) for g in row.get("failed_gates") or []]
        if not failed:
            continue
        out.append(
            sharpe_negative(
                str(row.get("name") or "candidate"),
                source=f"reports/{stem}#per_symbol",
                n_bars=float(row.get("n_bars") or 0.0),
                ppy=PPY,
                n_tests=max(1, n_cand),
                note=(
                    "one of the artifact's published per-symbol rows (the artifact records only "
                    f"the top {len(d.get('top_by_oos') or [])} of {n_cand} individually); failed "
                    + ",".join(failed)
                ),
            )
        )
    return out


# ------------------------------------------------------- reports/gauntlet_certification.json


def read_gauntlet_certification(root: Path) -> tuple[list[Type2Cost], list[dict[str, Any]]]:
    p = root / "reports/gauntlet_certification.json"
    d = _read_json(p)
    if not isinstance(d, dict):
        return [], [
            {"artifact": str(p), "status": "NOT-READABLE-HERE", "why": "absent or unparseable"}
        ]
    camp = d.get("campaign") or {}
    design = d.get("design") or {}
    t = float(camp.get("T") or 0.0)
    n = int(camp.get("N") or 0)
    return [
        sharpe_negative(
            f"GAUNTLET CERTIFICATION: N={n} candidates over T={t:g} bars, 0 survivors",
            source="reports/gauntlet_certification.json",
            n_bars=t,
            ppy=PPY,
            n_tests=max(1, n),
            note=(
                # This artifact is the MODEL for what the rest should look like: it already records
                # its own blindness rather than reporting a bare zero.
                "the certification records its own hurdle_annual_sharpe "
                f"{design.get('hurdle_annual_sharpe')} and underpowered_below_annual_sharpe "
                f"{design.get('underpowered_below_annual_sharpe')}"
            ),
        )
    ], []


# ------------------------------------------------------------------ Stage-A correlation screens


def _screen_cell(
    cell: dict[str, Any], *, name: str, source: str, n_tests: int, declared_trials: int = 1
) -> Type2Cost:
    """Label one axis-screen-shaped cell, reproducing the screen's own n_eff and power convention.

    The screen's `powered` flag is `1.96/sqrt(n_eff) <= ic_min` -- a 50%-power detectability floor
    at alpha=.05 two-sided, N=1 -- so `n_tests` is 1 and `power_target` is 0.5 here, and the
    agreement with the recorded flag is asserted in the note. Re-judging the cell under a different
    multiplicity OR a different power target would REPLACE the screen's verdict instead of
    labelling it, which this instrument is forbidden from doing. (Left at the 80% default, every
    honest cell whose mde sat between the two floors read as a contradiction -- a false fire
    manufactured by this instrument's own convention, not by the screen.)

    THE CELL'S OWN RECORDED n_eff IS THE INPUT when it carries one. Recomputing from (n,
    horizon_days, panel_width) silently re-judges any cell whose deflation inputs were lost in
    conversion -- measured on conv_idle_axis_screen__trials.json, whose source screen deflated
    136,931 raw rows to an honest n_eff of 1,711 that a recompute-from-n read as 136,931 and
    branded POWERED. The recompute survives only as the fallback for cells that recorded no n_eff,
    and it honours `overlap_periods` (non-overlapping grids, recorded by the harness) over the
    annualisation horizon.

    `declared_trials` is therefore reported and never applied. When a cell clears its own power
    floor at N=1 but would not clear it at the trial count the artifact itself declares, the note
    says so -- the reader gets the fact, the screen keeps its verdict.
    """
    rec_n_eff = cell.get("n_eff")
    if isinstance(rec_n_eff, (int, float)) and float(rec_n_eff) > 0.0:
        cost = correlation_negative(
            name,
            source=source,
            n_obs=float(rec_n_eff),
            n_tests=n_tests,
            power_target=0.5,
            note="",
        )
    else:
        cost = correlation_negative(
            name,
            source=source,
            n_obs=float(cell.get("n") or 0.0),
            horizon_periods=float(
                cell.get("overlap_periods") or cell.get("horizon_days") or 1.0
            ),
            panel_width=int(cell.get("panel_width") or 1),
            # L1.62: carry the cell's MEASURED cross-sectional breadth, or this recompute uses a
            # divisor the screen did not use and manufactures a DISAGREES on every measured panel
            # cell -- an L1.61 contradiction created by the reader rather than found by it. The
            # key is absent on every pre-L1.62 cell, which correctly keeps the conservative
            # full-panel_width divisor those cells were actually scored with.
            xs_neff=cell.get("xs_neff"),
            n_tests=n_tests,
            power_target=0.5,
            note="",
        )
    rec_powered = cell.get("powered")
    rec_mdi = cell.get("min_detectable_ic")
    # THREE STATES, NOT TWO. A screen that recorded NO `powered` flag has not disagreed with
    # anything -- there is nothing to disagree with. Collapsing "no flag" into DISAGREES manufactures
    # a finding out of a silence, and it fires on exactly the cells least able to defend themselves:
    # the converted screens, whose sources report a verdict and a detection floor but never a
    # boolean. Once every converted cell reads DISAGREES the label stops discriminating, and a REAL
    # disagreement -- the thing this note exists to surface -- is buried among them.
    if not isinstance(rec_powered, bool):
        agree = ("screen recorded NO powered flag -- nothing to agree or disagree with; this "
                 "instrument's own label stands alone for this cell")
    elif rec_powered == (cost.label == POWERED):
        agree = "screen agrees"
    else:
        agree = "DISAGREES WITH THE SCREEN'S OWN FLAG -- inspect"
    fragile = ""
    if cost.label == POWERED and declared_trials > 1:
        at_declared = correlation_negative(
            name, n_obs=cost.n_eff, n_tests=declared_trials, source=source, power_target=0.5
        )
        if at_declared.label != POWERED:
            fragile = (
                f". FRAGILE: powered only because the screen charges N=1; at the "
                f"{declared_trials} trials this artifact itself declares the floor moves to "
                f"{at_declared.min_detectable_effect:.4f} and the cell would not clear it. "
                "Reported, NOT applied -- the screen's verdict is unchanged"
            )
    return replace(
        cost,
        note=(
            f"screen verdict {cell.get('verdict')}; recorded powered={rec_powered}, "
            f"recorded min_detectable_ic={rec_mdi}; {agree}{fragile}"
        ),
    )


def read_axis_screens(root: Path) -> tuple[list[Type2Cost], list[dict[str, Any]]]:
    out: list[Type2Cost] = []
    unread: list[dict[str, Any]] = []
    d_dir = root / "reports/axis_screens"
    if not d_dir.exists():
        return [], [
            {
                "artifact": str(d_dir),
                "status": "NOT-READABLE-HERE",
                "why": "no axis-screen artifacts in this checkout",
            }
        ]
    for p in sorted(d_dir.glob("*.json")):
        d = _read_json(p)
        if not isinstance(d, dict):
            unread.append(
                {"artifact": str(p), "status": "NOT-READABLE-HERE", "why": "unparseable JSON"}
            )
            continue
        declared = int(d.get("trials_declared") or len(d.get("trials") or []) or 1)
        for cell in d.get("trials") or []:
            if not isinstance(cell, dict) or cell.get("verdict") == "SCREEN-INTERESTING":
                continue
            out.append(
                _screen_cell(
                    cell,
                    name=str(cell.get("name") or p.stem),
                    source=f"reports/axis_screens/{p.name}",
                    n_tests=1,
                    declared_trials=declared,
                )
            )
    return out, unread


def read_exchange_netflow(root: Path) -> tuple[list[Type2Cost], list[dict[str, Any]]]:
    p = root / "reports/screen_exchange_netflow.json"
    d = _read_json(p)
    if not isinstance(d, dict):
        return [], [
            {"artifact": str(p), "status": "NOT-READABLE-HERE", "why": "absent or unparseable"}
        ]
    declared = int(d.get("n_trials") or len(d.get("cells") or []) or 1)
    out = [
        _screen_cell(
            cell,
            name=str(cell.get("name") or "netflow_cell"),
            source="reports/screen_exchange_netflow.json",
            n_tests=1,
            declared_trials=declared,
        )
        for cell in d.get("cells") or []
        if isinstance(cell, dict) and cell.get("verdict") != "SCREEN-INTERESTING"
    ]
    return out, []


# ------------------------------------------------------------------ reports/intraday_rotation*


def read_intraday(root: Path) -> tuple[list[Type2Cost], list[dict[str, Any]]]:
    out: list[Type2Cost] = []
    unread: list[dict[str, Any]] = []
    for p in sorted((root / "reports").glob("intraday_rotation*.json")):
        d = _read_json(p)
        if not isinstance(d, dict):
            unread.append(
                {"artifact": str(p), "status": "NOT-READABLE-HERE", "why": "unparseable JSON"}
            )
            continue
        interval = str(d.get("interval") or "5m")
        ppy = _BARS_PER_YEAR.get(interval)
        if ppy is None:
            unread.append(
                {
                    "artifact": str(p),
                    "status": "NOT-READABLE-HERE",
                    "why": f"unknown bar interval {interval!r}; bars cannot be converted to years",
                }
            )
            continue
        proto = d.get("protocol") or {}
        test_bars = float(proto.get("test_bars") or 0.0)
        n_cfg = int(proto.get("n_configs_deflation") or 1)
        for leg in ("rotation", "continuation"):
            gate = (d.get("deployment_gate") or {}).get(leg) or {}
            if not gate:
                continue
            obs = gate.get("oos_annualised_sharpe")
            out.append(
                sharpe_negative(
                    f"INTRADAY {interval} {leg}: {gate.get('verdict')}",
                    source=f"reports/{p.name}",
                    n_bars=test_bars,
                    ppy=ppy,
                    n_tests=max(1, n_cfg),
                    note=(
                        f"{test_bars:g} out-of-sample {interval} bars = the same 61 elapsed days "
                        f"every interval in this family covers; observed OOS ann. Sharpe {obs}. "
                        "A decisively NEGATIVE observed Sharpe is a valid statement that THIS "
                        "configuration loses money; the label below speaks only to whether a "
                        "genuine POSITIVE edge of the reference size could have been detected."
                    ),
                )
            )
    return out, unread


# ------------------------------------------------------------------------- data/ screen outputs


def read_unlock_screen(root: Path) -> tuple[list[Type2Cost], list[dict[str, Any]]]:
    p = root / "data/unlock_event_screen.json"
    d = _read_json(p)
    if not isinstance(d, dict):
        return [], [
            {"artifact": str(p), "status": "NOT-READABLE-HERE", "why": "absent or unparseable"}
        ]
    n_trials = int(d.get("trials") or 1)
    out: list[Type2Cost] = []
    for cell in d.get("cells") or []:
        if not isinstance(cell, dict) or cell.get("passed"):
            continue
        out.append(
            correlation_negative(
                f"unlock {cell.get('category')} pct>={cell.get('pct_circ_now_min')} "
                f"N={cell.get('window_days')}d",
                source="data/unlock_event_screen.json",
                n_obs=float(cell.get("n_effective") or 0.0),
                n_tests=max(1, n_trials),
                effects=_UNLOCK_EFFECTS,
                reference_effect=_UNLOCK_REFERENCE,
                effect_unit="standardised_mean",
                note=(
                    f"event study, {cell.get('n_events')} events -> n_effective "
                    f"{cell.get('n_effective')} after overlap; declared reference effect "
                    f"{_UNLOCK_REFERENCE} standardised abnormal return (declared in "
                    "scripts/run_type2_report.py, not read off the observed statistic); "
                    f"observed t {cell.get('t_stat')} against the artifact's own bar "
                    f"{cell.get('bar')}"
                ),
            )
        )
    return out, []


def read_cot_screen(root: Path) -> tuple[list[Type2Cost], list[dict[str, Any]]]:
    p = root / "data/cot_screen_summary.json"
    d = _read_json(p)
    if not isinstance(d, dict):
        return [], [
            {"artifact": str(p), "status": "NOT-READABLE-HERE", "why": "absent or unparseable"}
        ]
    ghr = d.get("ghr") or {}
    n_trials = int(d.get("trials_charged") or 1)
    out: list[Type2Cost] = []
    for row in ghr.get("rows") or []:
        if not isinstance(row, dict):
            continue
        out.append(
            correlation_negative(
                f"COT {row.get('asset')}/{row.get('construction')} lagged predictability",
                source="data/cot_screen_summary.json",
                n_obs=float(row.get("n") or 0.0),
                n_tests=max(1, n_trials),
                effect_unit="lagged_beta_correlation",
                note=(
                    f"observed lagged t {row.get('t_lagged')}; the artifact's HEADLINE is the "
                    f"POOLED lagged t {ghr.get('pooled_lagged_t')} across all "
                    f"{len(ghr.get('rows') or [])} cells, which is NOT labelled here: the "
                    "artifact records no cross-asset correlation, so the pooled effective sample "
                    "cannot be computed without inventing one"
                ),
            )
        )
    return out, []


def read_moat(root: Path) -> tuple[list[Type2Cost], list[dict[str, Any]]]:
    """The moat screen's recorded negatives, labelled with the power they were taken at.

    WHEN THIS READER WAS WRITTEN the artifact was BLOCKED with zero rows and this function
    reported NOT-READABLE-HERE, correctly refusing to reconstruct rows from the prose in
    docs/research/VPS_STATE_20260805.md that cites them. The campaign has since RUN
    (2026-08-05T04:10, 48 candidates, 6 screen survivors), and the reader then reported
    UNHANDLED-SHAPE -- honest, and still zero of 48 negatives labelled. Detect-implies-repair:
    a reader that names the shape it cannot handle and stops is half a deliverable (L1.28b).

    THE CLOCK IS THE ONE THING THAT COULD MAKE THIS LIE. ``sharpe_negative`` demands that
    ``n_bars`` and ``ppy`` describe the SAME clock, and its docstring names that pair as the one
    way to overstate power. This campaign runs on ``bar_ms`` 60,000 -- ONE-MINUTE bars -- so ppy
    is 525,600, not the 365 every other reader here passes. Defaulting it would credit 4,980
    minutes of tape with 13.6 YEARS of evidence and turn the desk's blindest campaign into its
    best-powered one. ppy is therefore derived from the artifact's own declared interval and a
    missing/implausible ``bar_ms`` is refused rather than defaulted.

    PER-ROW ELAPSED TIME COMES FROM THE ROW'S OWN SYMBOL. Names are ``mechanism:SYMBOL`` and
    ``bars_per_symbol`` carries the length each symbol actually had, which ranges 4,981 to 25,791
    -- a 5.2x spread. Charging every row the campaign minimum would understate power for most of
    the panel; charging the maximum would credit history a symbol does not have. A row whose
    symbol is not in the map falls back to the campaign-wide ``n_obs``, and says so.
    """
    p = root / "reports/moat_campaign.json"
    d = _read_json(p)
    if not isinstance(d, dict):
        return [], [
            {"artifact": str(p), "status": "NOT-READABLE-HERE", "why": "absent or unparseable"}
        ]
    rows = [r for r in (d.get("rows") or []) if isinstance(r, dict)]
    if not rows:
        return [], [
            {
                "artifact": str(p),
                "status": "NOT-READABLE-HERE",
                "why": (
                    f"artifact status {d.get('status')!r}: {d.get('blocker')}. The 48-candidate / "
                    "n_obs 1,065 moat run cited by docs/research/VPS_STATE_20260805.md is VPS "
                    "runtime state and is not in this checkout; its rows are NOT reconstructed"
                ),
            }
        ]

    bar_ms = d.get("bar_ms")
    if not isinstance(bar_ms, int | float) or not 0 < float(bar_ms) <= 86_400_000:
        # REFUSED, NOT DEFAULTED. Without the interval there is no way to convert a bar count into
        # elapsed time, and guessing daily bars is the single assumption that would make every
        # label here wrong in the optimistic direction.
        return [], [
            {
                "artifact": str(p),
                "status": "NOT-READABLE-HERE",
                "why": (f"{len(rows)} rows present but bar_ms is {bar_ms!r}: without the bar "
                        "interval, n_bars cannot be converted to elapsed time and any power "
                        "label would be a guess"),
            }
        ]
    ppy = 365.0 * 24.0 * 3600.0 * 1000.0 / float(bar_ms)
    bars = {str(k): float(v) for k, v in (d.get("bars_per_symbol") or {}).items()
            if isinstance(v, int | float)}
    n_obs = float(d.get("n_obs") or 0.0)
    n_cand = int(d.get("n_candidates") or len(rows))
    bar_note = f"{float(bar_ms) / 1000.0:g}s bars (ppy {ppy:,.0f} derived from bar_ms)"

    out: list[Type2Cost] = []
    n_surv = sum(1 for r in rows if r.get("survived"))
    out.append(
        sharpe_negative(
            f"MOAT CAMPAIGN: {len(rows) - n_surv} of {len(rows)} candidates fail the screen",
            source="reports/moat_campaign.json",
            n_bars=min(bars.values()) if bars else n_obs,
            ppy=ppy,
            n_tests=max(1, n_cand),
            note=("campaign-level: multiplicity at the recorded candidate count, elapsed time at "
                  f"the SHORTEST symbol history in the panel; {bar_note}"),
        )
    )
    for r in rows:
        if r.get("survived"):
            continue        # a screen survivor is not a recorded negative
        name = str(r.get("name") or "moat")
        sym = name.split(":")[-1]
        n_bars = bars.get(sym, n_obs)
        out.append(
            sharpe_negative(
                name,
                source="reports/moat_campaign.json#rows",
                n_bars=n_bars,
                ppy=ppy,
                n_tests=max(1, n_cand),
                note=(f"failed {r.get('failed') or []}; oos_sharpe {r.get('oos_sharpe')}; "
                      + (f"elapsed at {sym}'s own {n_bars:,.0f} bars" if sym in bars else
                         f"symbol {sym!r} absent from bars_per_symbol -- campaign-wide n_obs used")
                      + f"; {bar_note}"),
            )
        )
    return out, []


_READERS = (
    ("docs/graveyard.md", read_graveyard),
    ("reports/real_campaign*.json", read_real_campaigns),
    ("reports/gauntlet_certification.json", read_gauntlet_certification),
    ("reports/axis_screens/*.json", read_axis_screens),
    ("reports/screen_exchange_netflow.json", read_exchange_netflow),
    ("reports/intraday_rotation*.json", read_intraday),
    ("data/unlock_event_screen.json", read_unlock_screen),
    ("data/cot_screen_summary.json", read_cot_screen),
    ("reports/moat_campaign.json", read_moat),
)


def collect(root: Path) -> tuple[list[Type2Cost], list[dict[str, Any]]]:
    costs: list[Type2Cost] = []
    unread: list[dict[str, Any]] = []
    for _label, reader in _READERS:
        got, missing = reader(root)
        costs.extend(got)
        unread.extend(missing)
    return costs, unread


# ------------------------------------------------------------------------------------- printing


def _trunc(s: str, n: int) -> str:
    return s if len(s) <= n else s[: n - 1] + "…"


def _fmt(x: float, nd: int = 3) -> str:
    """A number, or an explicit 'n/a'. An unmeasured quantity must never print as a measured one."""
    return f"{x:.{nd}f}" if math.isfinite(x) else "n/a"


def _cost_of_rejecting(c: Type2Cost) -> str:
    """P(this gate rejects | a true edge of the reference size exists) = 1 - power."""
    return _fmt(1.0 - c.power_at_reference) if math.isfinite(c.power_at_reference) else "n/a"


def print_report(costs: list[Type2Cost], unread: list[dict[str, Any]], root: Path) -> None:
    print("\nTYPE-II COST OF THE DESK'S RECORDED NEGATIVES")
    print("  POWERED-NEGATIVE = looked and it is not there   (negative knowledge)")
    print("  UNDERPOWERED     = could not have seen it       (no information either way)")
    print("  INDETERMINATE    = records no sample size       (unlabellable; counted as not powered)")
    print(f"  alpha {DEFAULT_ALPHA} -- unchanged. Reference effects: annualised Sharpe "
          f"{REFERENCE_SHARPE:g}, correlation {REFERENCE_CORRELATION_EFFECT:g}.")

    print("\nCITATIONS (existence verified, contents cited not re-derived)")
    for c, runtime in _CITATIONS:
        if (root / c).exists():
            mark = "OK          "
        else:
            # DANGLING is a repo defect; ABSENT-HERE is the ordinary state of a clean checkout.
            mark = "ABSENT-HERE " if runtime else "DANGLING    "
        print(f"  {mark} {c}{' (runtime-only)' if runtime else ''}")

    print(f"\n{'source':<40} {'negative':<52} {'label':<18} {'unit':<24} "
          f"{'min detect':>10} {'pow@ref':>8} {'P(rej|ref)':>10}")
    for c in sorted(costs, key=lambda z: (z.source, z.name)):
        print(
            f"{_trunc(c.source, 40):<40} {_trunc(c.name, 52):<52} {c.label:<18} "
            f"{_trunc(c.effect_unit, 24):<24} {_fmt(c.min_detectable_effect):>10} "
            f"{_fmt(c.power_at_reference):>8} {_cost_of_rejecting(c):>10}"
        )

    print(f"\n{'BY SOURCE':<44} {'n':>5} {'powered':>8} {'under':>8} {'indet':>8} {'% powered':>10}")
    for src in sorted({c.source for c in costs}):
        rows = [c for c in costs if c.source == src]
        h = headline(rows)
        print(f"{_trunc(src, 44):<44} {h.n_negatives:>5} {h.n_powered:>8} {h.n_underpowered:>8} "
              f"{h.n_indeterminate:>8} {h.fraction_powered:>9.1%}")

    if unread:
        print("\nNOT READABLE ON THIS CHECKOUT (reported, never reconstructed)")
        for u in unread:
            print(f"  [{u['status']}] {u['artifact']}\n      {u['why']}")

    h = headline(costs)
    print("\nDESK HEADLINE")
    print(f"  {h.summary()}")
    powered_rows = [c for c in costs if c.label == POWERED]
    if powered_rows:
        worst = max(powered_rows, key=lambda z: z.min_detectable_effect)
        print(f"  weakest powered negative: {_trunc(worst.name, 70)} "
              f"(min detectable {_fmt(worst.min_detectable_effect)} {worst.effect_unit})")
    under_rows = [c for c in costs if c.label == UNDERPOWERED]
    if under_rows:
        best = min(under_rows, key=lambda z: z.min_detectable_effect)
        print(f"  closest to powered but not there: {_trunc(best.name, 70)} "
              f"(min detectable {_fmt(best.min_detectable_effect)} {best.effect_unit}, "
              f"power {_fmt(best.power_at_reference)})")


def build_artifact(costs: list[Type2Cost], unread: list[dict[str, Any]], root: Path) -> dict[str, Any]:
    h = headline(costs)
    by_source: dict[str, Any] = {}
    for src in sorted({c.source for c in costs}):
        s = headline([c for c in costs if c.source == src])
        by_source[src] = {
            "n_negatives": s.n_negatives,
            "n_powered": s.n_powered,
            "n_underpowered": s.n_underpowered,
            "n_indeterminate": s.n_indeterminate,
            "fraction_powered": round(s.fraction_powered, 4)
            if s.fraction_powered == s.fraction_powered
            else None,
        }
    return {
        "generated_utc": datetime.now(tz=UTC).isoformat(),
        "instrument": "libs/validation/type2_cost.py",
        "authority": (
            "LABELS ONLY. This artifact changes no verdict, no threshold and no gate; alpha is "
            "0.05 and stays there. An UNDERPOWERED label says the desk knows less than it wrote "
            "down -- it is never a licence to re-open a permanent kill."
        ),
        "alpha": DEFAULT_ALPHA,
        "reference_effects": {
            "annualised_sharpe": REFERENCE_SHARPE,
            "correlation": REFERENCE_CORRELATION_EFFECT,
            "standardised_mean_unlock_screen": _UNLOCK_REFERENCE,
        },
        "declared_effects": {
            "annualised_sharpe": list(DECLARED_SHARPES),
            "correlation": list(DECLARED_CORRELATION_EFFECTS),
            "standardised_mean_unlock_screen": list(_UNLOCK_EFFECTS),
        },
        "citations": {c: (root / c).exists() for c, _ in _CITATIONS},
        # A citation that SHOULD be in every checkout and is not. Empty is the healthy state;
        # non-empty means this report cites something that no longer exists, which is a defect in
        # the repo rather than a fact about this box.
        "citations_dangling": sorted(
            c for c, runtime in _CITATIONS if not runtime and not (root / c).exists()),
        "citations_runtime_absent": sorted(
            c for c, runtime in _CITATIONS if runtime and not (root / c).exists()),
        "headline": {
            "n_negatives": h.n_negatives,
            "n_powered": h.n_powered,
            "n_underpowered": h.n_underpowered,
            "n_indeterminate": h.n_indeterminate,
            "fraction_powered": round(h.fraction_powered, 4)
            if h.fraction_powered == h.fraction_powered
            else None,
            "verdict": h.verdict,
            "summary": h.summary(),
        },
        "by_source": by_source,
        "not_readable_here": unread,
        "negatives": [c.as_dict() for c in costs],
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--json", type=Path, default=_DEFAULT_OUT, help="output artifact path")
    ap.add_argument("--root", type=Path, default=_ROOT, help="repo root to walk")
    ap.add_argument("--quiet", action="store_true", help="write the artifact without printing")
    args = ap.parse_args(argv)

    root = Path(args.root).resolve()
    costs, unread = collect(root)
    if not args.quiet:
        print_report(costs, unread, root)

    out = Path(args.json)
    if not out.is_absolute():
        out = root / out
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(build_artifact(costs, unread, root), indent=2) + "\n", "utf-8")
    if not args.quiet:
        print(f"\nwrote {out}")
    dangling = [c for c, runtime in _CITATIONS if not runtime and not (root / c).exists()]
    absent_here = [c for c, runtime in _CITATIONS if runtime and not (root / c).exists()]
    if dangling:
        print(f"WARNING: this report cites TRACKED files that no longer exist: {dangling}",
              file=sys.stderr)
    if absent_here:
        # Not a warning. reports/ is gitignored, so this is the ordinary state of a checkout that
        # has not run the producer -- saying it on stderr trains readers to ignore stderr.
        print(f"note: runtime-only citations not present on this host: {absent_here}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

```

### scripts\run_wealth_report.py
```python
#!/usr/bin/env python3
"""THE WEALTH REPORT — the economic scoreboard, above every architecture count.

WHAT THIS ANSWERS, in the order the specification puts them::

    is the desk RETAINING what it makes, or round-tripping it?      wealth_retention
    where did the money actually come from?                          return_engines
    how many independent bets is the book really carrying?           return_engines §58
    how long does evidence take to become a position?                conversion_velocity
    what did we decline, and was the reason systematically wrong?    decision_ledger
    how do we stand against the external benchmark?                  external_benchmark
    which model should be selected -- by payoff, not by accuracy?     payoff_selection
    did any conditional mechanism survive its own harder branch?     state_conditional

**EVERY NUMBER HERE IS READ FROM AN ARTIFACT OR REPORTED AS UNMEASURED.** Nothing on this desk has
a NAV path yet, no engine has a realised P&L series, and no candidate has reached a live fill. A
report that filled those with plausible defaults would be the most dangerous file in the repo: it
would look exactly like a working scoreboard and would be describing a simulation of a desk. So
every section that has no input says so in the words the specification uses -- UNMEASURED -- and
names the artifact whose absence caused it.

THAT IS THE POINT OF RUNNING IT TODAY RATHER THAN WHEN THE DATA ARRIVES. The consumers exist, the
shapes are fixed, and the moment the live path produces a fill the numbers appear without anyone
remembering to wire anything. A capability wired only when its input exists is a capability that
gets wired late, and the specification's §66 calls that stranding.

Reads artifacts, writes one. Allocates nothing, trades nothing, promotes nothing.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from libs.portfolio.return_engines import EngineReturn  # noqa: E402
from libs.portfolio.return_engines import summarise as engines_summary  # noqa: E402
from libs.portfolio.wealth_retention import (  # noqa: E402
    NavPath,
    RiskyProposal,
    reserve_option_value,
)
from libs.portfolio.wealth_retention import summarise as retention_summary  # noqa: E402
from libs.research import capital_basis  # noqa: E402
from libs.research.alpha_retention import LossEvent, RetentionRecord  # noqa: E402
from libs.research.alpha_retention import summarise as retention_loss_summary  # noqa: E402
from libs.research.conversion_velocity import STAGES, ConversionRecord  # noqa: E402
from libs.research.conversion_velocity import summarise as velocity_summary  # noqa: E402
from libs.research.decision_ledger import Decision  # noqa: E402
from libs.research.decision_ledger import summarise as decision_summary  # noqa: E402
from libs.research.external_benchmark import BenchmarkClaim, OwnPerformance  # noqa: E402
from libs.research.external_benchmark import summarise as benchmark_summary  # noqa: E402
from libs.research.payoff_selection import ModelRecord  # noqa: E402
from libs.research.payoff_selection import summarise as payoff_summary  # noqa: E402
from libs.validation.effective_sample import SampleGeometry  # noqa: E402
from libs.validation.effective_sample import summarise as sample_summary  # noqa: E402
from libs.validation.state_conditional import ConditionalEvidence, Preregistration  # noqa: E402
from libs.validation.state_conditional import summarise as conditional_summary  # noqa: E402

DATA = ROOT / "data"
OUT = DATA / "wealth_report.json"

#: Inputs. Every one is optional and every absence is REPORTED rather than defaulted.
NAV_PATH = DATA / "nav_path.json"
ENGINE_PNL = DATA / "engine_pnl.json"
CONVERSION = DATA / "conversion_records.json"
DECISIONS = DATA / "decision_ledger.jsonl"
BENCHMARK = DATA / "external_benchmark_claims.json"
MODELS = DATA / "model_records.json"
CONDITIONAL = DATA / "state_conditional_candidates.json"
LADDER = DATA / "live_ladder.json"
RETENTION = DATA / "alpha_retention.json"
SAMPLE_GEOMETRY = DATA / "sample_geometry.json"


def _load(p: Path) -> object | None:
    try:
        return json.loads(p.read_text("utf-8"))
    except (OSError, ValueError):
        return None


def _load_lines(p: Path) -> list[dict]:
    out: list[dict] = []
    try:
        for line in p.read_text("utf-8").splitlines():
            line = line.strip()
            if line:
                try:
                    out.append(json.loads(line))
                except ValueError:
                    continue
    except OSError:
        return []
    return out


def _rel(p: Path) -> str:
    """Repo-relative when possible, absolute otherwise.

    `Path.relative_to` RAISES for anything outside the repo, and the first version of `_absent`
    called it unguarded. That turned a missing-input report -- the one code path that must survive
    every absence -- into a ValueError the moment the inputs were pointed anywhere else. The
    function whose whole job is to handle a file not being there must not itself depend on where
    the file would have been.
    """
    try:
        return str(p.relative_to(ROOT))
    except ValueError:
        return str(p)


def _absent(artifact: Path, what: str) -> dict[str, object]:
    """The shape used everywhere an input is missing. Names the file, refuses a verdict."""
    rel = _rel(artifact)
    return {
        "measured": False,
        "missing_artifact": rel,
        "headline": (
            f"UNMEASURED -- {rel} is absent. {what}. This is a fact "
            "about the inputs, not a clean result: absence must never resolve to a verdict"),
    }


# ------------------------------------------------------------------ section builders

def wealth_section() -> dict[str, object]:
    raw = _load(NAV_PATH)
    if not isinstance(raw, dict) or not raw.get("nav"):
        return _absent(NAV_PATH, "gain retention, round-trip ratio and realised log growth cannot "
                                 "be computed and the desk cannot say whether it keeps what it makes")
    path = NavPath(nav=tuple(float(v) for v in raw["nav"]),
                   flows=tuple(float(v) for v in raw.get("flows", ())))
    props = tuple(RiskyProposal(
        name=str(p.get("name", "?")), edge=float(p.get("edge", 0.0)),
        edge_sigma=float(p.get("edge_sigma", 0.0)), variance=float(p.get("variance", 0.0)),
        tail_loss=float(p.get("tail_loss", 0.0)),
        effective_n=float(p.get("effective_n", 0.0))) for p in raw.get("proposals", []))
    rv = reserve_option_value(
        opportunity_arrival_rate=float(raw.get("dislocation_rate_per_day", 0.0)),
        expected_dislocation_edge=float(raw.get("dislocation_edge", 0.0)),
        horizon_periods=float(raw.get("horizon_days", 0.0)))
    return retention_summary(path, proposals=props,
                             current_risky_fraction=float(raw.get("risky_fraction", 0.0)),
                             reserve_value=rv)


def engines_section() -> dict[str, object]:
    raw = _load(ENGINE_PNL)
    if not isinstance(raw, dict) or not raw.get("engines"):
        return _absent(ENGINE_PNL, "No euro of P&L is attributed to a return engine, so beta "
                                   "cannot be distinguished from alpha and the effective "
                                   "independent engine count is unknown")
    rows = []
    for e in raw["engines"]:
        try:
            rows.append(EngineReturn(
                engine=str(e["engine"]), pnl=float(e.get("pnl", 0.0)),
                returns=tuple(float(x) for x in e.get("returns", ())),
                market_beta=e.get("market_beta"), r2_market=e.get("r2_market")))
        except (KeyError, ValueError, TypeError):
            continue
    gross = raw.get("gross_pnl")
    return engines_summary(rows, gross_pnl=None if gross is None else float(gross))


def velocity_section() -> dict[str, object]:
    raw = _load(CONVERSION)
    records: list[ConversionRecord] = []
    if isinstance(raw, dict) and raw.get("records"):
        for r in raw["records"]:
            records.append(ConversionRecord(
                candidate_id=str(r.get("candidate_id", "?")),
                stage_days={k: (None if r.get("stage_days", {}).get(k) is None
                                else float(r["stage_days"][k])) for k in STAGES},
                half_life_days=float(r.get("half_life_days", 0.0)),
                expected_bps_per_day=float(r.get("expected_bps_per_day", 0.0)),
                effective_n=float(r.get("effective_n", 0.0)),
                required_effective_n=float(r.get("required_effective_n", 0.0)),
                age_days=float(r.get("age_days", 0.0))))
    if not records:
        records = _records_from_ladder()
    if not records:
        return _absent(CONVERSION, "ECONOMIC_CONVERSION_VELOCITY is unknown, so the one deficit "
                                   "the benchmark specification names as decisive -- the clock "
                                   "between evidence and exposure -- is unwatched")
    return velocity_summary(records)


def _records_from_ladder() -> list[ConversionRecord]:
    """Derive conversion records from the live ladder when no dedicated artifact exists yet.

    DERIVED, AND SAID SO IN THE REPORT. The ladder knows which candidates are owed a shadow start
    and how much forward evidence each carries; that is enough to answer EVIDENCE_BOUND vs
    PROCESS_BOUND, which is the distinction that decides whether a delay is waste. It does NOT
    know discovery timestamps, so the per-stage latencies stay None rather than being invented.
    """
    lad = _load(LADDER)
    if not isinstance(lad, dict):
        return []
    out: list[ConversionRecord] = []
    for row in (lad.get("rows") or []):
        if not isinstance(row, dict):
            continue
        name = str(row.get("alpha") or row.get("name") or row.get("id") or "?")
        eff = float(row.get("effective_n") or row.get("n_effective") or 0.0)
        req = float(row.get("required_effective_n") or row.get("required") or 0.0)
        out.append(ConversionRecord(
            candidate_id=name,
            stage_days={"discovered": 0.0, "survivor": 0.0},
            effective_n=eff, required_effective_n=req,
            age_days=float(row.get("age_days") or 0.0)))
    return out


def decisions_section() -> dict[str, object]:
    rows = _load_lines(DECISIONS)
    if not rows:
        return _absent(DECISIONS, "the desk's decision surface is legible only where it said yes, "
                                  "so no rejection rule can be shown to be systematically wrong")
    decisions = []
    for r in rows:
        try:
            decisions.append(Decision(
                decision_id=str(r["decision_id"]), strategy_id=str(r.get("strategy_id", "")),
                symbol=str(r.get("symbol", "")), decided_at=str(r.get("decided_at", "")),
                outcome=str(r["outcome"]), reason=str(r.get("reason", "")),
                regime=str(r.get("regime", "")),
                signal_bps=float(r.get("signal_bps", 0.0)),
                modelled_cost_bps=float(r.get("modelled_cost_bps", 0.0)),
                counterfactual_bps=(None if r.get("counterfactual_bps") is None
                                    else float(r["counterfactual_bps"])),
                intended_notional=float(r.get("intended_notional", 0.0))))
        except (KeyError, ValueError, TypeError):
            continue
    return decision_summary(decisions)


def benchmark_section() -> dict[str, object]:
    raw = _load(BENCHMARK)
    claims = []
    if isinstance(raw, dict):
        for c in raw.get("claims", []):
            try:
                claims.append(BenchmarkClaim(
                    claimant=str(c["claimant"]), source=str(c.get("source", "")),
                    observed_at=str(c.get("observed_at", "")),
                    evidence_class=str(c["evidence_class"]),
                    start_value=float(c.get("start_value", 0.0)),
                    end_value=float(c.get("end_value", 0.0)),
                    elapsed_days=float(c.get("elapsed_days", 0.0)),
                    strategy_type=str(c.get("strategy_type", "")),
                    estimated_beta_share=c.get("estimated_beta_share"),
                    leverage=c.get("leverage"), realised=bool(c.get("realised", False)),
                    flows_disclosed=bool(c.get("flows_disclosed", False)),
                    net_of_costs=bool(c.get("net_of_costs", False)),
                    verification_notes=str(c.get("verification_notes", ""))))
            except (KeyError, ValueError, TypeError):
                continue
    own = _own_performance()
    if not claims and own is None:
        return _absent(BENCHMARK, "no external claim is recorded and our own live performance is "
                                  "unmeasured, so PERFORMANCE_LEAD does not exist in either term")
    return benchmark_summary(claims, own)


def _own_performance() -> OwnPerformance | None:
    raw = _load(NAV_PATH)
    if not isinstance(raw, dict) or not raw.get("nav"):
        return None
    from libs.portfolio.wealth_retention import drawdown_series, realized_log_growth
    path = NavPath(nav=tuple(float(v) for v in raw["nav"]),
                   flows=tuple(float(v) for v in raw.get("flows", ())))
    g = realized_log_growth(path)
    dd = drawdown_series(path.nav)
    return OwnPerformance(
        realized_log_growth=0.0 if g is None or g == float("-inf") else g,
        elapsed_days=float(raw.get("elapsed_days", 0.0)),
        deployed_capital=float(raw.get("deployed_capital", 0.0)),
        total_capital=float(raw.get("total_capital", 0.0)),
        max_drawdown=max(dd) if dd else 0.0,
        real_fills=int(raw.get("real_fills", 0)),
        realised_pnl=float(raw.get("realised_pnl", 0.0)))


def payoff_section() -> dict[str, object]:
    raw = _load(MODELS)
    if not isinstance(raw, dict) or not raw.get("models"):
        return _absent(MODELS, "no model is economically ranked, so any model in use today was "
                               "selected on something other than expected log growth")
    models = []
    for m in raw["models"]:
        try:
            models.append(ModelRecord(
                name=str(m["name"]), n_predictions=int(m.get("n_predictions", 0)),
                hit_rate=float(m.get("hit_rate", 0.0)), win_bps=float(m.get("win_bps", 0.0)),
                loss_bps=float(m.get("loss_bps", 0.0)),
                trades_per_year=float(m.get("trades_per_year", 0.0)),
                capital_fraction=float(m.get("capital_fraction", 1.0)),
                tail_loss_bps=float(m.get("tail_loss_bps", 0.0)),
                mean_predicted=float(m.get("mean_predicted", 0.0)),
                mean_realised=float(m.get("mean_realised", 0.0)),
                mean_log_loss=float(m.get("mean_log_loss", 0.0)), auc=m.get("auc")))
        except (KeyError, ValueError, TypeError):
            continue
    return payoff_summary(models)


def conditional_section() -> dict[str, object]:
    raw = _load(CONDITIONAL)
    pairs = []
    if isinstance(raw, dict):
        for c in raw.get("candidates", []):
            try:
                p = c["preregistration"]
                e = c["evidence"]
                pairs.append((
                    Preregistration(
                        hypothesis_id=str(p["hypothesis_id"]),
                        mechanism_class=str(p.get("mechanism_class", "GLOBAL_MECHANISM")),
                        state_definition=str(p.get("state_definition", "")),
                        conditionality_mechanism=str(p.get("conditionality_mechanism", "")),
                        sequence=int(p.get("sequence", 0))),
                    ConditionalEvidence(
                        hypothesis_id=str(e["hypothesis_id"]),
                        first_evaluated_sequence=int(e.get("first_evaluated_sequence", 0)),
                        state_occurrences=int(e.get("state_occurrences", 0)),
                        state_share=float(e.get("state_share", 0.0)),
                        as_of_observable=bool(e.get("as_of_observable", False)),
                        classifier_stability=float(e.get("classifier_stability", 0.0)),
                        in_state_net_bps=float(e.get("in_state_net_bps", 0.0)),
                        out_state_net_bps=float(e.get("out_state_net_bps", 0.0)),
                        in_state_n=int(e.get("in_state_n", 0)),
                        out_state_n=int(e.get("out_state_n", 0)),
                        transition_net_bps=e.get("transition_net_bps"),
                        conditional_costs_measured=bool(
                            e.get("conditional_costs_measured", False)),
                        untouched_oos_net_bps=e.get("untouched_oos_net_bps"),
                        untouched_oos_n=int(e.get("untouched_oos_n", 0)))))
            except (KeyError, ValueError, TypeError):
                continue
    return conditional_summary(pairs)


def operational_section() -> dict[str, object]:
    """§45. How much VALIDATED edge never arrived, and what it would cost to recover it.

    The gap between what a strategy would have earned running exactly as validated and what it
    actually earned is invisible on every P&L: it presents as a weaker edge, which invites doubt
    about the research rather than about the plumbing. Recovering it is the one thing on this desk
    that competes with new alpha on identical units -- bps per engineering hour.
    """
    raw = _load(RETENTION)
    if not isinstance(raw, dict) or not raw.get("strategies"):
        return _absent(RETENTION, "ALPHA_RETENTION_RATIO is unknown, so every shortfall against a "
                                  "validated expectation currently reads as the research having "
                                  "been wrong rather than the plumbing having leaked")
    records = []
    for r in raw["strategies"]:
        losses = []
        for ev in r.get("losses", []):
            try:
                losses.append(LossEvent(
                    cause=str(ev["cause"]), lost_bps=float(ev.get("lost_bps", 0.0)),
                    duration_days=float(ev.get("duration_days", 0.0)),
                    recurring=bool(ev.get("recurring", True)),
                    fix_cost_hours=float(ev.get("fix_cost_hours", 0.0)),
                    detail=str(ev.get("detail", ""))))
            except (KeyError, ValueError, TypeError):
                continue
        records.append(RetentionRecord(
            strategy_id=str(r.get("strategy_id", "?")),
            live_days=float(r.get("live_days", 0.0)),
            expected_bps=float(r.get("expected_bps", 0.0)),
            realised_bps=float(r.get("realised_bps", 0.0)),
            losses=tuple(losses)))
    return retention_loss_summary(records)


def sample_section() -> dict[str, object]:
    """§15. How many of the rows behind each claim were actually independent observations.

    t scales as sqrt(n), so a tenfold inflation of the count is a threefold inflation of every
    t-statistic computed on it -- silently, on every candidate the sweep has ever produced.
    """
    raw = _load(SAMPLE_GEOMETRY)
    if not isinstance(raw, dict) or not raw.get("samples"):
        return _absent(SAMPLE_GEOMETRY, "every `n` this desk feeds into a significance test is a "
                                        "raw row count, and whether it overstates the evidence is "
                                        "UNMEASURED")
    samples = {}
    for name, g in raw["samples"].items():
        samples[str(name)] = SampleGeometry(
            rows=int(g.get("rows", 0)), window_length=int(g.get("window_length", 1)),
            step=int(g.get("step", 0)), autocorrelation=float(g.get("autocorrelation", 0.0)),
            distinct_events=int(g.get("distinct_events", 0)),
            distinct_regimes=int(g.get("distinct_regimes", 0)),
            n_assets=int(g.get("n_assets", 1)),
            mean_asset_rho=float(g.get("mean_asset_rho", 0.0)),
            n_venues=int(g.get("n_venues", 1)),
            mean_venue_rho=float(g.get("mean_venue_rho", 0.0)))
    return sample_summary(samples)


def board_question(sections: dict[str, dict]) -> tuple[str, str]:
    """§DAILY BOARD QUESTION -- what is currently preventing more retained net wealth?

    Answered from the sections in a fixed precedence, because the ordering IS the answer: an
    unmeasured scoreboard outranks a slow one, and a slow one outranks a thin one. The highest
    item that fires becomes the next task, which is what makes this a scheduler input rather
    than a rhetorical flourish.
    """
    w, e, v = sections["wealth_retention"], sections["return_engines"], sections["conversion"]
    b = sections["external_benchmark"]
    if not w.get("measured", True) and not e.get("measured", True):
        return ("NO REALISED P&L EXISTS TO RETAIN", (
            "Neither a NAV path nor an engine attribution is present, so wealth retention and "
            "return attribution are both UNMEASURED. Nothing on this desk has yet produced a "
            "realised euro, which makes every retention and benchmark number below undefined "
            "rather than good. The binding constraint is reaching a first real fill"))
    if int(v.get("process_bound", 0) or 0) > 0:
        return ("ALPHA IS NOT REACHING LIVE", (
            f"{v['process_bound']} candidate(s) hold sufficient evidence and are not moving, "
            f"costing at least {v.get('total_process_waiting_cost_bps', 0)}bp. This is the "
            "conversion deficit the benchmark spec names as the benchmarked operator's actual "
            "advantage, and it is the cheapest thing on this list to fix"))
    if e.get("hidden_beta"):
        return ("BETA IS BEING REPORTED AS ALPHA", (
            f"{len(e['hidden_beta'])} engine(s) declared independent behave as market exposure. "
            "Capital sized against the wrong covariance is the mechanism behind the round trip "
            "this desk is built to avoid"))
    rt = (w.get("ROUND_TRIP_RATIO") or 0.0) if w.get("measured") else 0.0
    if isinstance(rt, int | float) and rt >= 0.5:
        return ("WEALTH IS ROUND-TRIPPING", (
            f"{rt:.0%} of the peak gain has been surrendered. Return generation is not the "
            "constraint; retention is"))
    if b.get("own_win_conditions_unmet"):
        return ("THE COMPARISON IS NOT YET WINNABLE", (
            f"our side fails {b['own_win_conditions_unmet']}. A lead computed before these hold "
            "would be a comparison we chose the framing for"))
    return ("NOT ENOUGH INDEPENDENT ALPHA", (
        "no measured blockage in retention, attribution, conversion or benchmark comparability. "
        "The binding constraint is the supply of independent validated edge"))


def _safe(name: str, fn, artifact: Path) -> dict[str, object]:
    """Run one section, and turn a malformed input into UNMEASURED rather than into no report.

    THE FAILURE THIS PREVENTS IS TOTAL, NOT PARTIAL. Every section here is fed by an artifact
    written elsewhere, and a single bad value -- a string where a float belongs, a null in a list
    -- would otherwise raise out of `build` and produce NO scoreboard at all. The desk would then
    be blind to wealth retention, attribution and conversion because one unrelated file was
    malformed, and the only symptom would be a report that stopped appearing.

    So a section that cannot parse its own input reports exactly what a section with no input
    reports: UNMEASURED, naming the file. That is the honest description of both states, and it
    keeps the other six sections readable.
    """
    try:
        return fn()
    except (ValueError, TypeError, KeyError, AttributeError, OverflowError) as e:
        return {
            "measured": False,
            "missing_artifact": _rel(artifact),
            "headline": (
                f"UNMEASURED -- {name}: {_rel(artifact)} is present but MALFORMED "
                f"({type(e).__name__}: {e}). A section that cannot parse its input knows exactly "
                "as much as one with no input, and reporting anything else would be an invention"),
        }


def build() -> dict[str, object]:
    sections = {
        "wealth_retention": _safe("wealth_retention", wealth_section, NAV_PATH),
        "return_engines": _safe("return_engines", engines_section, ENGINE_PNL),
        "conversion": _safe("conversion", velocity_section, CONVERSION),
        "decisions": _safe("decisions", decisions_section, DECISIONS),
        "external_benchmark": _safe("external_benchmark", benchmark_section, BENCHMARK),
        "payoff_selection": _safe("payoff_selection", payoff_section, MODELS),
        "state_conditional": _safe("state_conditional", conditional_section, CONDITIONAL),
        "operational_retention": _safe("operational_retention", operational_section, RETENTION),
        "effective_sample": _safe("effective_sample", sample_section, SAMPLE_GEOMETRY),
    }
    q, why = board_question(sections)
    unmeasured = [k for k, s in sections.items() if s.get("measured") is False]
    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "DAILY_BOARD_QUESTION": "What is currently preventing this desk from generating and "
                                "retaining more real net wealth?",
        "ANSWER": q,
        "why": why,
        # THE DENOMINATOR IS DECLARED, NOT ASSUMED (L1.58-r0287). Every return this board reports
        # is a ratio, and a ratio whose denominator is unnamed is unfalsifiable: `+8%` on capital
        # actually drawn and `+8%` on total portfolio value are different claims that print
        # identically, and the second is the Quantopian trap -- legal to state, impossible to
        # audit, and flattering by exactly the amount of cash left idle.
        #
        # `libs.research.capital_basis` has carried the vocabulary and this helper since the law
        # was written, and `scripts/check_capital_basis.py` fails any web/ or reports/ artifact
        # reporting a return without one. NOTHING EVER CALLED IT: the fence named the helper in
        # its own message and no producer imported it, so L1.58-r0287 read as enforced while every
        # artifact it governs published undeclared denominators. Measured by
        # check_enforcement_execution 2026-08-14 as MENTIONED -- a fence that has never run.
        #
        # capital_utilized is the honest leveraged-book basis: PnL over the cash ACTUALLY drawn,
        # including margin. It is the denominator that cannot be inflated by holding cash idle.
        **capital_basis.declare("capital_utilized"),
        "unmeasured_sections": unmeasured,
        "sections": sections,
        "note": ("Architecture counts are deliberately absent from this report. Every section "
                 "with no input reports UNMEASURED and names the artifact whose absence caused "
                 "it -- an empty scoreboard filled with plausible defaults would be "
                 "indistinguishable from a working one."),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", type=Path, default=OUT)
    a = ap.parse_args()
    rep = build()
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(rep, indent=1, sort_keys=False), "utf-8")

    print("=== WEALTH REPORT ===")
    print(f"BOARD QUESTION: {rep['ANSWER']}")
    print(f"  {rep['why']}")
    for name, s in rep["sections"].items():          # type: ignore[union-attr]
        print(f"  [{name}] {s.get('headline', 'no headline')}")
    if rep["unmeasured_sections"]:
        print(f"  UNMEASURED sections: {rep['unmeasured_sections']}")
    print(f"wrote {a.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

```
