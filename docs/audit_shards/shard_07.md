# AUDIT SHARD 7/24 -- seat moonshotai/kimi-k3

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

### libs\research\__init__.py
```python
"""Research strategy cores (shared by backtest + forward-shadow so they are provably identical)."""

```

### libs\research\bar_span.py
```python
"""A BAR COVERING A FRACTION OF THE SPAN ITS LABEL CLAIMS IS AN ESTIMATE WEARING A DAY'S CLOTHES
(L1.68).

L1.46 established that a TIMESTAMP whose clock is undeclared is an assumption, and fenced the
stamping clock for every market-data record. It asks WHEN a bar is stamped. It has no vocabulary
for the other half of the same claim -- HOW MUCH MARKET TIME THE BAR CONTAINS -- and a "D1" label
asserts both. Measured on this desk's own primary universe, the second half is false for half of it.

THE MEASURED STATE, 2026-08-20, over the MT5 D1 lake (the full mandate: fx/metal/index/energy/
equity/soft/bond): 88 series, 43 carrying bars on days the trading calendar declares CLOSED,
7,048 such bars -- 6,902 Sunday, 131 Saturday, 15 on an equity name. Worst: EURILS 366/3,996 =
9.16%, CHFNOK 9.11%, GBPPLN 9.11%, EURTRY 9.09%, AUDNZD 391/7,254 = 5.39%. Clean: 45.

THE DENOMINATOR IS THE FENCE'S OWN, NOT THE PROPOSAL'S, AND THE DIFFERENCE IS THE POINT (L1.57).
The hand measurement that prompted this module scanned four asset classes and reported 68 series /
42 dirty / 7,033 bars. Scanning the mandate's SEVEN classes finds 88 / 43 / 7,048 -- and the extra
symbol is SKYY, whose defect is a different class entirely (see ``SeriesSpan.kind``). A count of
what the author chose to look at is not a denominator; only a count of what the RUN found is.

THEY ARE NOT CORRUPTION, AND THAT IS THE WHOLE REPAIR DIRECTION. 100% of the Sunday bars are
followed by a Monday bar (366/366 EURILS, 370/370 AUDNZD, 220/220 CADJPY, 15/15 EURUSD), so the
week carries SIX D1 bars rather than five; their median volume is ~0.5% of a weekday bar (118 vs
23,110 on EURILS) and their median range 15-49% of one. That is the real one-to-three-hour stub
between the Sunday Asia-Pacific session open and Monday 00:00 UTC -- genuine market time, labelled
as a day. The Saturday bars are the same class from the broker's older session definition (all
2002-2005, volume ~0.05% of a weekday bar, 100% also carrying a Friday bar).

SO THE BARS ARE NEVER DELETED. They are real observations and L1.65 is unconditional: destroying
span is the one loss that cannot be re-earned by working harder. The repair is to DECLARE the
contamination per symbol and EXCLUDE it at the point of consumption -- ``session_filtered`` below
-- never to rewrite the lake.

WHY NOTHING COULD SEE IT, AND THE BLINDNESS IS ONE-DIRECTIONAL. ``libs/data/quality.py`` holds the
desk's completeness check and it computes exactly one direction::

    return expected.difference(present)     # bars MISSING from the calendar

The inverse -- ``present.difference(expected)``, bars EXISTING when the calendar says closed --
appears nowhere in the tree. ``libs/data/calendar.is_open`` declares the rule ("FX, metals and
indices are closed Saturday and Sunday") and has ZERO callers outside its own re-export and one
test; ``InstrumentSpec.trades_weekends`` encodes the same rule and has zero non-test readers. The
rule was written down twice and enforced never.

AND THE GAUGE MOVES THE WRONG WAY, which is why no report could have raised it::

    n_expected   = n_bars + n_missing
    completeness = (n_expected - n_missing) / n_expected     # == n_bars / (n_bars + n_missing)

An out-of-calendar bar increments ``n_bars``, so it RAISES completeness and raises the quality
score. This is the L1.65 shape one domain over: a gauge that improves when the data gets worse.
(It has never fired here in any case -- ``compute_quality_score`` is reachable only through
``build_silver``, which has no production caller, and the lake holds only ``bronze/``.)

WHAT IT COSTS, MEASURED RATHER THAN ASSERTED. A stub bar splits one day's move into two, which is
mechanically negative autocorrelation:

  * ANNUALISED VOLATILITY understated by up to 4.95% (EURTRY 0.1633 vs 0.1718 clean; GBPPLN
    -4.14%, AUDNZD -2.87%, NZDJPY -2.50%). Vol drives inverse-vol sizing, so the understatement
    OVERSIZES precisely the contaminated symbols.
  * LAG-1 AUTOCORRELATION inflated 34% on EURILS (-0.1353 dirty vs -0.1006 clean). Any
    mean-reversion screen reading these series sees an edge that is one third instrument
    artifact -- the L1.25 420/0 class, arriving through the bar rather than through the gate.

THE CROSS-SECTIONAL CLAIM WAS REFUTED ON RE-DERIVATION, AND THE REFUTATION IS KEPT (L1.17). The
proposal that produced this law argued the damage lands on the measured ``narrow_breadth`` N_eff
of 13.37. It does not: ``measure_cross_section_breadth`` aligns on an INNER JOIN across 76
symbols, 26 of which are clean, so a weekend timestamp is never common to all -- measured, ZERO
weekend rows survive into the panel (1,764 rows, weekday counts {0:310, 1:370, 2:366, 3:358,
4:360}). The breadth statistic is protected. It is protected BY ACCIDENT: the protection is
undeclared, and it evaporates the moment a panel is restricted to a contaminated subset, built by
outer join, or forward-filled. ``session_filtered`` is wired there to convert an accidental
protection into a declared one -- and it must move no number today, which its test pins.

THE SAME REASONING ALREADY EXISTS IN THAT FILE, FOR THE OTHER UNIVERSE. ``fetch_okx`` keeps only
``confirm=="1"`` rows because "OKX's newest daily row is the IN-PROGRESS bar ... keeping it would
put a partial bar at the panel's edge for every symbol SIMULTANEOUSLY -- one extra row of pure
synchronised common factor, biasing correlation up and breadth down." The desk reasoned this
through for crypto, where the VENUE SUPPLIES A FLAG, and never for MT5, where no flag exists and
the same defect must be derived from the calendar. The MT5 case is the harder one: contamination
is RAGGED (0% to 9.16% across the panel) rather than synchronised, so it cannot be spotted as a
common factor at all.

THE VERDICTS:
  OK                (exit 0) -- every measured series lies inside its declared session calendar.
  DECLARED          (exit 0) -- out-of-calendar bars exist, every one is at or below its recorded
                                floor, and the artifact publishes the per-symbol share so a
                                consumer can exclude or weight instead of silently averaging.
  CONTAMINATED      (exit 2) -- a share ROSE above its floor, or a series is contaminated with no
                                floor recorded. This is the only growth path and it is the point.
  UNMEASURED        (exit 2) -- no series scanned. Never OK (L1.28a).
  NOT-READABLE-HERE (exit 0) -- ``data/`` is gitignored and VPS-only; this host cannot see the
                                lake. Distinct from 0%, and never OK-by-default (L1.65 precedent).

THE FLOOR RATCHETS DOWNWARD ONLY (L1.0/L2.0). A share may fall -- that is a repair, and the floor
follows it down permanently. A share may never rise. So this gate CAN fail (L1.63: a certificate
whose partition cannot return False is welded open), and the gap between today's floors and zero
is the work queue rather than an accepted state.

ANTI-TIMIDITY READING, THE ENTIRE PURPOSE (L1.28/L1.21a): a MEASUREMENT duty and a SCOPE
EXPANSION. It lifts nothing, sizes nothing, promotes nothing, opens no gate, loosens no
statistical bar, deletes not one bar of data, and has no vocabulary for turning a failing verdict
into a passing one. Its whole effect is to make "this series' days are days" distinguishable from
"9% of this series' days are ninety-minute stubs nobody declared" -- byte-identical on this desk
until now, and only one of them is evidence.
"""

from __future__ import annotations

import json
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from pathlib import Path

_MS_PER_DAY = 86_400_000
#: 1970-01-01 was a Thursday, which is weekday 3 in Python's Monday==0 convention. Deriving the
#: weekday by arithmetic rather than through pandas keeps the load-bearing rule importable on a
#: box with no scientific stack -- the fence must still RUN, and still BLOCK, where the lake was
#: never built.
_EPOCH_WEEKDAY = 3

OK = "OK"
DECLARED = "DECLARED"
CONTAMINATED = "CONTAMINATED"
UNMEASURED = "UNMEASURED"
NOT_READABLE_HERE = "NOT-READABLE-HERE"

#: NOT-READABLE-HERE passes because a checkout genuinely cannot see a gitignored lake, and a fence
#: red on every developer box is a fence that gets switched off (L1.43). It is a DISTINCT status,
#: never folded into OK, so "we did not look" can never be read as "we looked and it was clean".
PASSING = frozenset({OK, DECLARED, NOT_READABLE_HERE})

#: The MT5 UNIVERSE MANDATE (CLAUDE.md, principal 2026-08-18). `crypto` is deliberately absent:
#: it trades 24/7, so out-of-calendar has no meaning there, and the mandate forbids hunting it.
MT5_CLASSES: tuple[str, ...] = ("fx", "metal", "index", "energy", "equity", "soft", "bond")

#: Asset classes that genuinely trade every day. Mirrors `InstrumentSpec.trades_weekends`, which
#: encodes the identical rule and has zero non-test readers -- this module is what wires it.
WEEKEND_TRADING_CLASSES: frozenset[str] = frozenset({"crypto"})


def weekday_of_ms(ts_ms: int) -> int:
    """Return the UTC weekday (Monday==0 .. Sunday==6) of an epoch-millisecond timestamp."""
    return (ts_ms // _MS_PER_DAY + _EPOCH_WEEKDAY) % 7


def is_out_of_calendar(ts_ms: int, *, trades_weekends: bool) -> bool:
    """Return whether a bar at ``ts_ms`` sits on a day its market declares CLOSED.

    This is the direction ``libs/data/quality.detect_missing_bars`` does not compute. That
    function asks which EXPECTED timestamps are absent; this asks which PRESENT timestamps were
    never expected. A series can score 100% complete on the first question while 9% of its rows
    fail the second, which is exactly the state the MT5 lake was in when this was written.
    """
    if trades_weekends:
        return False
    return weekday_of_ms(int(ts_ms)) >= 5


def session_filtered(
    timestamps: Sequence[int], *values: Sequence[float], trades_weekends: bool = False
) -> tuple[list[int], list[list[float]]]:
    """THE REPAIR. Drop out-of-calendar rows at the point of CONSUMPTION, never from disk.

    Returns the kept timestamps and each value series filtered to match. The bars stay on disk
    because they are real market observations (L1.65: destroyed span is the one loss that cannot
    be re-earned); what they may not do is enter a daily statistic weighted as a full day.

    Every value sequence must be the same length as ``timestamps``; a mismatch raises rather than
    truncating, because a silently shortened price series is the defect this module exists to end
    arriving one layer down.
    """
    ts = [int(t) for t in timestamps]
    for i, series in enumerate(values):
        if len(series) != len(ts):
            raise ValueError(
                f"series {i} has {len(series)} rows against {len(ts)} timestamps -- "
                "refusing to align by truncation"
            )
    keep = [
        i for i, t in enumerate(ts)
        if not is_out_of_calendar(t, trades_weekends=trades_weekends)
    ]
    return ([ts[i] for i in keep], [[float(s[i]) for i in keep] for s in values])


#: A session stub is a FRACTION of a normal bar; the measured FX cases run ~0.005 of weekday
#: median volume (118 vs 23,110 on EURILS). Anything at or above a quarter of a normal bar is not
#: a stub, whatever day it sits on, and it must not be handed the stub's repair.
_STUB_VOLUME_RATIO = 0.25

#: Decimal places the floors artifact stores, and therefore the precision at which a share may be
#: compared to it. A comparison whose two sides carry different precision is a verdict decided by
#: rounding rather than by measurement.
_FLOOR_PRECISION = 6

SESSION_STUB = "SESSION-STUB"
ANOMALOUS = "ANOMALOUS"
UNKNOWN_KIND = "UNKNOWN"


@dataclass(frozen=True)
class SeriesSpan:
    """One symbol's out-of-calendar measurement.

    ``kind`` separates two defects that a bare weekend-bar count renders identical while they
    demand OPPOSITE repairs -- the distinction L1.55 draws between ABSENT and UNREADABLE, and
    L1.61 between its three contradiction classes, arriving on the time axis:

      SESSION-STUB  the bar is a genuine sliver of market time (Sunday Asia-Pacific open). Real
                    data, wrongly weighted as a day. Repair: declare it and exclude at read.
      ANOMALOUS     the bar is FULL SIZE on a day the market was shut, so it cannot be a session
                    stub and excluding it would hide rather than fix. Repair: the INGEST.
      UNKNOWN       no volume column, so the desk cannot tell them apart. Never resolved to
                    either by default (L1.28a).

    The proving instance is SKYY, found by this fence's first run and missed by the proposal that
    prompted it: 15 out-of-calendar bars carrying 149k-919k volume against a weekday median of
    10,098 -- 15x to 90x a normal bar, with internally inconsistent price levels (2024-03-09 spans
    64.33 to 98.35 inside one bar). Telling it to "declare and exclude" would have been wrong.
    """

    symbol: str
    asset_class: str
    n_bars: int
    n_out_of_calendar: int
    n_saturday: int
    n_sunday: int
    floor: float | None = None
    #: Median volume of out-of-calendar bars over median volume of in-calendar bars; None when
    #: the series carries no volume column or no out-of-calendar bars.
    volume_ratio: float | None = None

    @property
    def share(self) -> float:
        """Out-of-calendar bars as a fraction of all bars; 0.0 for an empty series."""
        return (self.n_out_of_calendar / self.n_bars) if self.n_bars else 0.0

    @property
    def kind(self) -> str | None:
        """Which defect this is: a real session stub, a full-size anomaly, or undecidable."""
        if self.n_out_of_calendar == 0:
            return None
        if self.volume_ratio is None:
            return UNKNOWN_KIND
        return SESSION_STUB if self.volume_ratio < _STUB_VOLUME_RATIO else ANOMALOUS

    @property
    def status(self) -> str:
        """OK when clean; DECLARED when at or below floor; CONTAMINATED when above or unrecorded."""
        if self.n_out_of_calendar == 0:
            return OK
        # AN ANOMALY IS NEVER DISCHARGED BY A FLOOR. A full-size bar on a shut market is repaired
        # in the INGEST; letting it be floored would buy a green board with the one class the
        # read-side filter cannot fix, which is a gate welded open by its own escape hatch
        # (L1.63). It stays red, named, with a specific repair -- which is a work item rather
        # than the diffuse red that gets a fence switched off (L1.43).
        if self.kind == ANOMALOUS:
            return CONTAMINATED
        if self.floor is None:
            return CONTAMINATED
        # BOTH SIDES ARE COMPARED AT THE PRECISION THE FLOOR IS STORED AT, and getting this wrong
        # is not cosmetic. The floors file writes round(share, 6); comparing that against the
        # FULL-precision share makes any symbol whose seventh decimal is non-zero fail against a
        # floor recorded from its own unchanged measurement -- CHFNOK (362/3,974 = 0.09110216 vs a
        # stored 0.091102) and EURTRY read CONTAMINATED the moment the baseline was written, with
        # share and floor rendering as the identical 9.1092% in the report. A fence inexplicably
        # red on half its scope is a fence that gets switched off (L1.43).
        return (
            DECLARED
            if round(self.share, _FLOOR_PRECISION) <= self.floor + 1e-9
            else CONTAMINATED
        )

    def as_row(self) -> dict[str, object]:
        return {
            "symbol": self.symbol,
            "asset_class": self.asset_class,
            "n_bars": self.n_bars,
            "n_out_of_calendar": self.n_out_of_calendar,
            "n_saturday": self.n_saturday,
            "n_sunday": self.n_sunday,
            "share": round(self.share, 6),
            "floor": None if self.floor is None else round(self.floor, 6),
            "kind": self.kind,
            "volume_ratio": None if self.volume_ratio is None else round(self.volume_ratio, 6),
            "status": self.status,
        }


@dataclass
class ScanReport:
    """The whole run: what was measured, what was SKIPPED, and the verdict over both."""

    series: list[SeriesSpan] = field(default_factory=list)
    #: L1.60 -- how many symbol directories the loop ATTEMPTED, so a series the scan could not
    #: read is distinguishable from one that was never in scope. A denominator honest about what
    #: it counted and silent about what it lost is what a reader scores as coverage.
    n_attempted: int = 0
    skips: list[dict[str, str]] = field(default_factory=list)
    readable: bool = True

    @property
    def n_scanned(self) -> int:
        return len(self.series)

    @property
    def status(self) -> str:
        if not self.readable:
            return NOT_READABLE_HERE
        if not self.series:
            return UNMEASURED
        if any(s.status == CONTAMINATED for s in self.series):
            return CONTAMINATED
        return DECLARED if any(s.n_out_of_calendar for s in self.series) else OK

    def as_dict(self) -> dict[str, object]:
        dirty = [s for s in self.series if s.n_out_of_calendar]
        worst = sorted(dirty, key=lambda s: -s.share)[:10]
        return {
            "law": "L1.68",
            "status": self.status,
            "n_series": self.n_scanned,
            "n_attempted": self.n_attempted,
            "n_skipped": len(self.skips),
            "skips": self.skips,
            "n_contaminated": len(dirty),
            "n_clean": self.n_scanned - len(dirty),
            "n_out_of_calendar_bars": sum(s.n_out_of_calendar for s in self.series),
            "n_bars": sum(s.n_bars for s in self.series),
            # Two defects, two repairs, counted separately so a reader is never told to
            # "declare and exclude" a broken ingest.
            "by_kind": {
                kind: sum(1 for s in dirty if s.kind == kind)
                for kind in (SESSION_STUB, ANOMALOUS, UNKNOWN_KIND)
            },
            "anomalous": [s.symbol for s in dirty if s.kind == ANOMALOUS],
            "worst": [s.symbol for s in worst],
            "series": [s.as_row() for s in sorted(self.series, key=lambda s: -s.share)],
        }


def _median(values: list[float]) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    mid = len(ordered) // 2
    return ordered[mid] if len(ordered) % 2 else (ordered[mid - 1] + ordered[mid]) / 2.0


def measure_series(
    symbol: str,
    asset_class: str,
    timestamps: Iterable[int],
    *,
    volumes: Sequence[float] | None = None,
    floor: float | None = None,
) -> SeriesSpan:
    """Measure one symbol's out-of-calendar bars against its own asset class's calendar.

    ``volumes`` is optional and its absence resolves the kind to UNKNOWN rather than to either
    real class -- "we could not tell" and "it is a harmless stub" are different claims and only
    one of them is evidence (L1.28a).
    """
    trades_weekends = asset_class in WEEKEND_TRADING_CLASSES
    stamps = [int(t) for t in timestamps]
    vols = list(volumes) if volumes is not None else None
    if vols is not None and len(vols) != len(stamps):
        raise ValueError(
            f"{symbol}: {len(vols)} volumes against {len(stamps)} timestamps -- "
            "refusing to align by truncation"
        )
    sat = sun = 0
    in_vol: list[float] = []
    out_vol: list[float] = []
    for i, t in enumerate(stamps):
        out = not trades_weekends and weekday_of_ms(t) >= 5
        if out:
            wd = weekday_of_ms(t)
            sat += wd == 5
            sun += wd == 6
        if vols is not None:
            (out_vol if out else in_vol).append(float(vols[i]))
    ratio: float | None = None
    if sat + sun:
        med_in, med_out = _median(in_vol), _median(out_vol)
        # A zero or absent in-calendar median cannot form a ratio; leaving it None reports
        # UNKNOWN rather than dividing by zero into a fabricated class.
        if med_in and med_out is not None:
            ratio = med_out / med_in
    return SeriesSpan(
        symbol=symbol,
        asset_class=asset_class,
        n_bars=len(stamps),
        n_out_of_calendar=sat + sun,
        n_saturday=sat,
        n_sunday=sun,
        floor=floor,
        volume_ratio=ratio,
    )


def scan_lake(
    lake_root: Path,
    *,
    classes: tuple[str, ...] = MT5_CLASSES,
    floors: dict[str, float] | None = None,
) -> ScanReport:
    """Walk ``<lake_root>/bronze/<class>/<symbol>/D1`` and measure every series it can read.

    EVERY SYMBOL DIRECTORY ATTEMPTED IS COUNTED (L1.60), and one it cannot read becomes a SKIP
    ROW rather than leaving the denominator in silence. This deliberately does not route through
    ``libs.data.lake.read_bars``: that calls ``instruments.get_spec``, whose built-in catalogue
    holds EIGHT symbols against the lake's 88, so 80 of 88 would raise inside an except and
    vanish -- the measured defect ``measure_cross_section_breadth`` documents at its own loader.
    The asset class comes from the lake's own directory layout, which is the thing that actually
    knows.

    A missing lake returns ``readable=False`` -> NOT-READABLE-HERE. That is not a clean verdict
    and it is not zero; it is this host saying it cannot see the evidence.
    """
    floors = floors or {}
    base = Path(lake_root) / "bronze"
    if not base.exists():
        return ScanReport(readable=False)
    try:
        import pyarrow.dataset as pads
    except ImportError:
        return ScanReport(readable=False)

    report = ScanReport()
    for cls in classes:
        root = base / cls
        if not root.exists():
            continue
        for sym_dir in sorted(p for p in root.iterdir() if p.is_dir()):
            d1 = sym_dir / "D1"
            if not d1.exists():
                continue
            report.n_attempted += 1
            try:
                # PYARROW VERSION STRADDLE -- see libs/data/lake.py and the pyproject override.
                # This ignore is REQUIRED on the pinned pyarrow (>=24,<25) and reads as UNUSED on
                # 25.x, so the two environments would otherwise disagree about whether this file
                # is clean. Deleting it as "unused" from an off-pin box is how that disagreement
                # last reached the deploy gate.
                dataset = pads.dataset(  # type: ignore[no-untyped-call]
                    str(d1), format="parquet", partitioning="hive"
                )
                cols = ["timestamp"]
                # Volume is what separates a session stub from a full-size anomaly. Its absence
                # is recorded (kind=UNKNOWN), never silently treated as either.
                if "volume" in dataset.schema.names:
                    cols.append("volume")
                table = dataset.to_table(columns=cols)
                stamps = [int(v.value // 1_000_000) for v in table.column("timestamp")]
                vols = (
                    [float(v.as_py() or 0.0) for v in table.column("volume")]
                    if "volume" in cols
                    else None
                )
            except Exception as exc:  # the ROW is what matters here, never the type
                report.skips.append(
                    {"symbol": sym_dir.name, "asset_class": cls, "reason": type(exc).__name__}
                )
                continue
            if not stamps:
                report.skips.append(
                    {"symbol": sym_dir.name, "asset_class": cls, "reason": "empty"}
                )
                continue
            report.series.append(
                measure_series(
                    sym_dir.name, cls, stamps, volumes=vols, floor=floors.get(sym_dir.name)
                )
            )
    return report


def load_floors(path: Path) -> dict[str, float]:
    """Read the recorded per-symbol contamination floors; a missing file is an empty mapping.

    An unreadable or malformed file returns EMPTY rather than raising, and empty means every
    contaminated series reads CONTAMINATED -- the fence fails loud. Defaulting the other way
    would let a deleted floor file manufacture a clean verdict, which is the L1.55 fabrication
    this desk has already paid for once.
    """
    try:
        raw = json.loads(path.read_text("utf-8"))
    except (OSError, ValueError):
        return {}
    floors = raw.get("floors") if isinstance(raw, dict) else None
    if not isinstance(floors, dict):
        return {}
    out: dict[str, float] = {}
    for k, v in floors.items():
        if isinstance(v, (int, float)) and not isinstance(v, bool):
            out[str(k)] = float(v)
    return out


def ratchet_floors(existing: dict[str, float], report: ScanReport) -> dict[str, float]:
    """Return floors moved DOWNWARD only (L1.0): a repair is permanent, a regression is not kept.

    A symbol whose share FELL takes the new lower value -- the desk has proved it can hold that
    level and may never quietly give it back. A symbol whose share ROSE keeps its old floor, so
    the fence stays red until the regression is actually repaired rather than being re-baselined
    into acceptance. THE REPAIR IS UPWARD, NEVER DOWNWARD (L1.49): a fall in quality is never
    fixed by lowering the mark.
    """
    out = dict(existing)
    for s in report.series:
        if s.n_out_of_calendar == 0:
            out[s.symbol] = 0.0
            continue
        # ANOMALOUS series are deliberately never floored: recording one would write the desk's
        # acceptance of a broken ingest into the artifact that governs the verdict.
        if s.kind == ANOMALOUS:
            continue
        prior = out.get(s.symbol)
        out[s.symbol] = s.share if prior is None else min(prior, s.share)
    return out

```

### libs\research\conversion_max.py
```python
"""CONVERSION, ACROSS EVERY FAMILY AT ONCE -- and the fences that stop the pressure corrupting it.

PRINCIPAL ORDER (2026-08-01): maximise every part of conversion, aggressively and exhaustively,
across defects, data and recommendations alike -- *"its one big family to always maximise"* --
*"without letting the factor its trying to utilise or convert get reduced or affected cuz of it"*.

That second clause is the hard half and it is what most of this file is about.

============================== WHY ONE FAMILY, MEASURED TOGETHER ==============================

This desk already has a conversion law -- §33 in `mine_conversion`, with dispositions, quality
backing, value weighting, latency and a ratchet. It is good, and it governs ONE family: mined
research cards. Meanwhile the recommendation ledger sits at 123 open and 67 scheduled out of 283
(67% never reaching implementation), the research-conversion ledger tracks video and paper items
separately, the mined queue holds hundreds of unread candidates, and the GAP register holds
defects. Four backlogs, four separate measurements, and NOTHING that reads them together or shows
any of them to the organ whose job is to prioritise.

So the desk could truthfully report each family as tended while the aggregate rotted. Unconverted
inventory is not neutral: it consumed a cycle to acquire, it inflates every downstream audit's
picture of the desk's capability, and it makes the map read richer than the territory. Mining is
not the product; CONVERSION is. A perfect dig with zero conversions is a failed cycle.

========================= THE HARD PART: PRESSURE MUST NOT DILUTE =========================

Turning conversion pressure up has exactly two failure modes, and both LOOK like success:

  PADDING          -- propose more, weaker items so the throughput number rises. The reject rate
                      rises with volume; the desk reads "lots of recommendations" and converts a
                      smaller fraction of a worse pool.
  CHEAP DISPOSITION -- clear the backlog by marking things done. `mine_conversion` names this
                      exactly: without a quality layer, "kill everything" is the cheapest legal
                      way to unblock mining. The same applies to "implemented" as a status.

The naive fix -- push harder and hope -- makes both worse. So the fences here get STRONGER as the
pressure rises rather than staying fixed:

  1. RE-PROPOSING AN OPEN ITEM IS NOT CONVERSION, it is noise, and under pressure it is the
     single most likely thing to happen: the model is asked for twelve recommendations, has ten
     good ones, and fills the last two by restating what is already in the ledger. `duplicate_of`
     catches that on a normalised title and the contract rejects it.
  2. THE EVIDENCE BAR DOES NOT MOVE. Conversion pressure must never buy a weaker claim, so the
     `evidence` class still requires a cited number. Volume is negotiable; the bar is not.
  3. PADDING IS MEASURED AND REPORTED. `dilution_report` compares the reject rate of the recent
     window against the prior one. If pushing harder raised the reject rate, that is padding and
     it says so -- rather than the desk reading a higher raw count as more output.
  4. A CONVERSION IS A SHIPPED THING. The definition is inherited from `conversion_ledger` and is
     deliberately strict: shipped, tested code, or a measurement that changed a constant. Not
     "was interesting". Not "confirmed something".

NOTHING HERE DISPOSES OF ANYTHING. This measures and it pressures; a human or an implementation
agent still does the work. An organ that could both demand conversions and record them would
record them.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parents[2]

#: Statuses that count as CONVERTED, per family. Deliberately narrow -- `scheduled` is NOT a
#: conversion, it is a promise, and counting promises is how a backlog reads as worked while
#: nothing ships.
_CONVERTED = {"implemented", "done", "wired", "converted", "screened"}
_DEAD = {"rejected", "killed", "read_no_value", "retired"}


@dataclass(frozen=True)
class Family:
    """One conversion family: what was acquired, what became something, what is rotting."""
    name: str
    total: int
    converted: int
    dead: int
    open: int
    oldest_open_days: float | None = None
    note: str = ""

    @property
    def settled_rate(self) -> float | None:
        """Of the items that reached a VERDICT, what fraction converted. Answers "when this desk
        decides, does it decide to build?" -- and NOTHING about the backlog."""
        decided = self.converted + self.dead
        return round(self.converted / decided, 3) if decided else None

    @property
    def throughput_rate(self) -> float | None:
        """Of everything ACQUIRED, what fraction converted. The honest backlog number.

        BOTH RATES ARE REPORTED AND THIS ONE LEADS, because reporting only the settled rate is the
        denominator trick this desk forbids everywhere else. The recommendation ledger settles at
        95% -- 88 converted against 5 closed dead -- while 190 of 283 items sit open. A CRO reading
        "conversion rate 95%" concludes conversion is solved; the same family at 31% throughput
        says two-thirds of everything ever raised is still rotting, which is the truth and the
        whole reason this file exists. A metric that flatters the thing it measures is worse than
        no metric, because it ends the investigation.
        """
        return round(self.converted / self.total, 3) if self.total else None

    def line(self) -> str:
        age = f", oldest {self.oldest_open_days:.0f}d" if self.oldest_open_days else ""
        thru = f"{self.throughput_rate:.0%}" if self.throughput_rate is not None else "UNMEASURED"
        settled = f"{self.settled_rate:.0%}" if self.settled_rate is not None else "n/a"
        pct_open = f" ({self.open / self.total:.0%} of everything acquired)" if self.total else ""
        return (f"{self.name}: {self.open} OPEN{pct_open}{age} -- {self.converted} converted and "
                f"{self.dead} closed dead out of {self.total} acquired. THROUGHPUT {thru} "
                f"(settled rate {settled}, which excludes the open and must not be read as health)"
                + (f" [{self.note}]" if self.note else ""))


@dataclass(frozen=True)
class ConversionState:
    families: list[Family] = field(default_factory=list)
    generated_utc: str = ""

    @property
    def total_open(self) -> int:
        return sum(f.open for f in self.families)

    @property
    def total_acquired(self) -> int:
        return sum(f.total for f in self.families)

    def worst(self) -> Family | None:
        """The family with the most rotting inventory. Named explicitly because a board listing
        four backlogs produces none of them; naming the binding one produces work."""
        live = [f for f in self.families if f.open]
        return max(live, key=lambda f: f.open) if live else None

    def summary(self) -> str:
        return (f"{self.total_acquired} items acquired across {len(self.families)} families, "
                f"{self.total_open} still OPEN")


# ------------------------------------------------------------------------------ reading families

def assemble(root: Path | None = None) -> ConversionState:
    """Every conversion family the desk keeps, read together for the first time.

    A family whose ledger is absent or unreadable is reported with a note, never silently omitted
    -- a missing backlog reads as an empty one, and an empty backlog reads as a tended one.
    """
    base = root or _ROOT
    fams = [
        _recommendations(base),
        _research_conversions(base),
        _mined_queue(base),
        _cro(base),
    ]
    return ConversionState(families=[f for f in fams if f is not None],
                           generated_utc=datetime.now(UTC).isoformat(timespec="seconds"))


def _recommendations(base: Path) -> Family | None:
    p = base / "docs" / "research" / "recommendation_ledger.json"
    rows, note = _json_rows(p, "recommendations")
    if rows is None:
        return Family("recommendations", 0, 0, 0, 0, note=note)
    conv = sum(1 for r in rows if str(r.get("status", "")).lower() in _CONVERTED)
    dead = sum(1 for r in rows if str(r.get("status", "")).lower() in _DEAD)
    open_ = len(rows) - conv - dead
    # `scheduled` is counted OPEN, deliberately. A schedule is a promise, and a family that counts
    # promises as conversions reads as worked while nothing ships.
    sched = sum(1 for r in rows if str(r.get("status", "")).lower() == "scheduled")
    return Family("recommendations", len(rows), conv, dead, open_,
                  _oldest_days(rows, "raised"),
                  note=f"{sched} of the open are 'scheduled' -- a promise, not a conversion"
                  if sched else "")


def _research_conversions(base: Path) -> Family | None:
    rows, note = _jsonl_rows(base / "docs" / "research_conversions.jsonl")
    if rows is None:
        return Family("mined_research", 0, 0, 0, 0, note=note)
    conv = sum(1 for r in rows if r.get("outcome") == "converted")
    dead = sum(1 for r in rows if r.get("outcome") == "read_no_value")
    open_ = sum(1 for r in rows if r.get("outcome") == "queued_unread")
    return Family("mined_research", len(rows), conv, dead, open_,
                  _oldest_days(rows, "recorded_utc"))


def _mined_queue(base: Path) -> Family | None:
    """The miner's live queue. EVERY row here is unread by definition -- it is the raw acquisition
    rate, and the gap between it and `mined_research` is how much mining outruns reading."""
    p = base / "reports" / "research_queue.json"
    if not p.exists():
        return Family("mine_queue", 0, 0, 0, 0, note="queue artifact absent -- miner has not run")
    try:
        q = json.loads(p.read_text("utf-8")).get("queue") or []
    except (OSError, json.JSONDecodeError) as exc:
        return Family("mine_queue", 0, 0, 0, 0, note=f"unreadable: {type(exc).__name__}")
    return Family("mine_queue", len(q), 0, 0, len(q),
                  note="every row is unread by construction; this is the ACQUISITION rate, and "
                       "the gap to mined_research is how far mining outruns reading")


def _cro(base: Path) -> Family | None:
    rows, note = _jsonl_rows(base / "docs" / "research" / "cro_recommendations.jsonl")
    if rows is None:
        return Family("cro", 0, 0, 0, 0, note=note)
    conv = sum(1 for r in rows if str(r.get("disposition", "")).lower() in _CONVERTED)
    dead = sum(1 for r in rows if r.get("rejected_reason")
               or str(r.get("disposition", "")).lower() in _DEAD)
    return Family("cro", len(rows), conv, dead, len(rows) - conv - dead,
                  _oldest_days(rows, "utc"))


def _json_rows(p: Path, key: str) -> tuple[list[dict[str, Any]] | None, str]:
    if not p.exists():
        return None, f"{p.name} absent"
    try:
        obj = json.loads(p.read_text("utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return None, f"{p.name} unreadable: {type(exc).__name__}"
    rows = obj.get(key) if isinstance(obj, dict) else obj
    return (rows, "") if isinstance(rows, list) else (None, f"{p.name}: no '{key}' list")


def _jsonl_rows(p: Path) -> tuple[list[dict[str, Any]] | None, str]:
    if not p.exists():
        return None, f"{p.name} absent -- nothing recorded yet"
    out: list[dict[str, Any]] = []
    for line in p.read_text("utf-8").splitlines():
        if line.strip():
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return out, ""


def _oldest_days(rows: list[dict[str, Any]], key: str) -> float | None:
    now = datetime.now(UTC)
    best: float | None = None
    for r in rows:
        raw = str(r.get(key) or "")[:19]
        if not raw:
            continue
        for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
            try:
                d = datetime.strptime(raw[:len(datetime.now(UTC).strftime(fmt))], fmt).replace(
                    tzinfo=UTC)
            except ValueError:
                continue
            age = (now - d).total_seconds() / 86400.0
            best = age if best is None else max(best, age)
            break
    return best


# ------------------------------------------------------------------------------- the pressure

def pressure_block(state: ConversionState) -> str:
    """The aggressive conversion demand, built from measured backlogs rather than exhortation.

    'Convert more' is exhortation and produces padding. 'The recommendation ledger holds 123 open
    items, the oldest 47 days old, and 67 more are merely scheduled' is a fact that produces work,
    and it is the same distinction the whole contract rests on.
    """
    lines = "\n".join(f"  - {f.line()}" for f in state.families)
    worst = state.worst()
    focus = (f"\nTHE BINDING BACKLOG THIS CYCLE is {worst.name} at {worst.open} open items. "
             "A board that lists four backlogs produces none of them; this is the one to attack."
             if worst else "")
    return f"""
========================= CONVERSION: ONE FAMILY, MAXIMISED =========================
Mining is not the product. CONVERSION is. Un-converted inventory is not neutral -- it consumed a
cycle to acquire, it inflates every downstream audit's picture of this desk's capability, and it
makes the map read richer than the territory. A perfect cycle with zero conversions is a FAILED
cycle.

Measured right now, across every family at once:

{lines}
{focus}

EVERY CYCLE YOU MUST, and these are not optional:
  - Name what is ROTTING: the specific open items whose age or value makes them the most
    expensive things on this list, by name, not by category.
  - Say WHY each is stuck. "Not prioritised" is not a reason; a reason is a missing dependency, a
    blocked credential, an unanswered question, or an item that should be KILLED and is not.
  - Recommend KILLS as readily as builds. An item that will never be converted should be closed
    dead, and refusing to kill it is how a backlog becomes permanent. `retire` is a full
    recommendation with the same required fields as any other.
  - Attack the ACQUISITION/READING gap where one exists. Mining faster than the desk reads
    manufactures inventory and calls it progress.

=========================== AND THE PRESSURE MUST NOT DILUTE ===========================
Turning conversion pressure up has exactly two failure modes and BOTH LOOK LIKE SUCCESS. You are
being asked for maximum aggression on conversion, so you are the one most exposed to them:

  PADDING -- filling your quota with weaker items so the count rises. If you have eight strong
    recommendations, RETURN EIGHT and say why the rest of the quota was not worth spending. A
    short list of falsifiable items beats a full list padded with the unfalsifiable, and the
    reject rate is measured across cycles, so padding is visible.
  RE-PROPOSING WHAT IS ALREADY OPEN -- the single most likely thing to happen under quota
    pressure. It is NOT conversion, it is noise that inflates the very backlog you are attacking,
    and a code check rejects it on a normalised title.

The evidence bar does NOT move because the pressure went up. `evidence` still requires a cited
number. Volume is negotiable; the bar is not.
"""


# -------------------------------------------------------------------- the anti-dilution fences

_NORM = re.compile(r"[^a-z0-9 ]+")


def normalise_title(title: str) -> str:
    """Lowercase, strip punctuation, collapse space, drop filler. Enough to catch a restatement
    without collapsing two genuinely different recommendations onto one key."""
    t = _NORM.sub(" ", str(title).lower())
    drop = {"the", "a", "an", "to", "for", "of", "and", "on", "in", "by", "with", "at"}
    return " ".join(w for w in t.split() if w not in drop)


def open_titles(path: Path | None = None) -> set[str]:
    """Normalised titles of everything currently OPEN, across families. What a new recommendation
    must not merely restate."""
    state_paths = [
        (path or _ROOT / "docs" / "research" / "cro_recommendations.jsonl", "title", "disposition"),
    ]
    out: set[str] = set()
    for p, tkey, dkey in state_paths:
        rows, _ = _jsonl_rows(p)
        for r in rows or []:
            if str(r.get(dkey, "")).lower() in _CONVERTED or r.get("rejected_reason"):
                continue
            if r.get(tkey):
                out.add(normalise_title(str(r[tkey])))
    ledger, _ = _json_rows(_ROOT / "docs" / "research" / "recommendation_ledger.json",
                           "recommendations")
    for r in ledger or []:
        if str(r.get("status", "")).lower() in _CONVERTED | _DEAD:
            continue
        if r.get("summary"):
            out.add(normalise_title(str(r["summary"])))
    return out


def duplicate_of(title: str, known: set[str]) -> bool:
    """Is this a restatement of something already open?

    Exact normalised match, plus a containment check for the common padding shape where a known
    item is restated with extra qualifiers bolted on. Deliberately NOT fuzzy beyond that: a false
    positive here silently discards a real recommendation, which is worse than letting one
    near-duplicate through.
    """
    n = normalise_title(title)
    if not n:
        return False
    if n in known:
        return True
    return any(k and (k in n or n in k) and min(len(k), len(n)) >= 20 for k in known)


def dilution_report(rows: list[dict[str, Any]], *, window: int = 24) -> dict[str, Any]:
    """Did the pressure buy volume at the cost of quality? Measured across cycles.

    THE NUMBER THAT KEEPS THIS HONEST. Aggression is supposed to raise conversions, not raise
    output. If the recent window's reject rate is materially above the prior window's, the extra
    output is padding and the desk should read the raw count as smaller, not larger.
    """
    if len(rows) < 2 * window:
        return {"verdict": f"UNMEASURED: need {2 * window} recorded rows to compare windows, "
                           f"have {len(rows)}", "n": len(rows)}
    recent, prior = rows[-window:], rows[-2 * window:-window]

    def rej(batch: list[dict[str, Any]]) -> float:
        return sum(1 for r in batch if r.get("rejected_reason")) / len(batch)

    r_now, r_before = rej(recent), rej(prior)
    out: dict[str, Any] = {
        "n": len(rows), "window": window, "reject_rate_recent": round(r_now, 3),
        "reject_rate_prior": round(r_before, 3), "delta": round(r_now - r_before, 3)}
    if r_now - r_before > 0.15:
        out["verdict"] = (f"PADDING: the reject rate rose from {r_before:.0%} to {r_now:.0%}. The "
                          "extra output is not extra value -- read the raw count as smaller, not "
                          "larger, and tighten the ask rather than raising the quota.")
    elif r_now > 0.5:
        out["verdict"] = (f"LOW YIELD: {r_now:.0%} of the recent window was rejected by the "
                          "contract, regardless of trend. The seat is mostly producing what the "
                          "fences catch.")
    else:
        out["verdict"] = (f"HOLDING: reject rate {r_now:.0%} against {r_before:.0%} prior -- "
                          "the pressure is not buying volume at the cost of quality.")
    return out

```

### libs\research\label_factory.py
```python
"""PROPRIETARY LABEL FACTORY -- event labels as versioned research assets (RANK 6).

WHAT A LABEL IS, AND THE TRAP THIS IS BUILT AROUND. A label marks that something HAPPENED
(liquidity stress, forced deleveraging, accumulation, a regime turn). It is not an alpha and it is
not a signal, and the single most dangerous thing about labels is that the most natural way to
define one uses the very window it describes. "Forced deleveraging happened here" is usually
recognised FROM the cascade -- so if you then test whether the label predicts the cascade's returns,
you have measured your own definition and it will look spectacular.

So every label declares KNOWN_AT_LAG: how many bars after ``t`` before ``label[t]`` could actually
have been known. Three of the four families below are knowable at the close of ``t`` (lag 0). The
fourth, ``regime_transition``, genuinely is NOT -- a regime turn is only a turn once it persists, so
it carries an honest confirmation lag. Encoding that as a field rather than a comment is the whole
point: this is the class that produced the bithumb KST/UTC IC-0.72 fake and the kimchi
construction bug, and both were arithmetic that looked fine and was aligned wrong.

VALIDATION IS ABOUT THE LABEL, NOT ABOUT PROFIT. ``validate`` asks whether the label is a
well-formed event marker: does it fire at a testable rate, is it an EVENT rather than a state
wearing an event's name, and is it free of lookahead at its declared lag. Whether a label predicts
returns is a separate hypothesis, screened through ``libs.research.axis_screen`` with every
multiplicity cost that implies. Keeping those two questions apart matters: "my label is well
formed" is a data-quality claim, "my label predicts returns" is a trial, and a factory that blurs
them manufactures trials nobody counted.

THE CAUSALITY TEST IS TRUNCATION, and arriving there took two wrong turns worth recording, because
both LOOKED like working guards. The obvious approach is `libs/features/validation.py`'s
future-invariance mechanism -- mutate future bars, require past values unchanged -- generalised to
allow a declared lag. It does not work here:

  * mutating by a CONSTANT multiple (what that module does, correctly, for level-based features)
    leaves every future ``pct_change`` identical except at one boundary bar, so it is nearly blind
    to return-based labels -- which is most of them;
  * per-bar RANDOM mutation compared at sampled ``t`` fails differently: event labels are sparse, so
    a sampled point almost always compares 0 against 0, and scrambling a whole tail makes everything
    uniformly "stepped", which an onset rule (``fires & ~fired_before``) then absorbs.

A deliberately mislabelled lag-0 ``regime_transition`` -- openly reading five bars ahead -- passed
BOTH. What works is the definition itself: recompute the label on ``bars[:t + lag + 1]``, the data
that existed when the label claims to be knowable, and require ``label[t]`` unchanged. Sampling is
weighted to FIRING positions for the same sparsity reason. That version rejects the mislabelled
label at 20 of 31 checked positions and passes the honest lag-5 one cleanly.

VERSIONING IS BY CONTENT, NOT BY HAND. ``LabelSpec.version`` is a hash of the family plus its
parameters, so retuning a threshold produces a new version automatically and an old validation
record can never silently describe a redefined label. Lineage (``inputs``) names the RANK 4
registry asset ids the label was built from, so a label whose source panel is 17 days long cannot
be mistaken for one built on the 267-symbol 2019-09 panel.

numpy + pandas. Import from ``libs.research.label_factory``; CLI is ``scripts/build_labels.py``.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Mapping, Sequence
from dataclasses import asdict, dataclass, field
from typing import Any

import numpy as np
import pandas as pd

#: A label firing this rarely cannot be tested -- there is no power at any horizon.
MIN_BASE_RATE = 0.005
#: A label firing this often is describing a STATE, not an event. "Stressed 40% of the time" is a
#: regime variable; calling it an event invites event-study machinery that assumes rarity.
MAX_BASE_RATE = 0.35
#: Longest allowed consecutive run, as a fraction of all firings. A label that fires in one
#: contiguous blob is a period flag (one 2022 blob = "the year 2022"), not a repeatable event.
MAX_RUN_FRACTION = 0.5

VERDICT_VALID = "VALID"
VERDICT_RARE = "DEGENERATE-RARE"
VERDICT_COMMON = "DEGENERATE-COMMON"
VERDICT_BLOB = "BLOB-NOT-EVENT"
VERDICT_LEAKING = "LEAKING"
VERDICT_INERT = "INERT"


@dataclass(frozen=True)
class LabelSpec:
    """A label DEFINITION. Immutable; retuning a parameter yields a different ``version``."""

    id: str
    family: str
    params: Mapping[str, float] = field(default_factory=dict)
    inputs: tuple[str, ...] = ()          #: RANK 4 registry asset ids -- lineage, not decoration
    known_at_lag: int = 0                 #: bars after t before label[t] is knowable
    rationale: str = ""

    @property
    def version(self) -> str:
        """Content hash: family + sorted params. A retuned threshold is a NEW label, not an edit."""
        payload = json.dumps({"family": self.family,
                              "params": {k: float(v) for k, v in sorted(self.params.items())},
                              "known_at_lag": self.known_at_lag}, sort_keys=True)
        return hashlib.sha256(payload.encode()).hexdigest()[:12]

    @property
    def qualified_id(self) -> str:
        return f"{self.id}@{self.version}"


@dataclass
class LabelValidation:
    """Whether the label is a well-formed EVENT marker. Says nothing about profitability."""

    verdict: str
    base_rate: float
    n_events: int
    n_firings: int
    max_run: int
    leak_checked: int = 0
    leak_failures: int = 0
    responds_to_inputs: bool = True
    notes: list[str] = field(default_factory=list)

    @property
    def usable(self) -> bool:
        return self.verdict == VERDICT_VALID


# ------------------------------------------------------------------ helpers on the bronze panel


def _mask(cond: pd.Series) -> pd.Series:
    """A boolean event MASK, where a missing observation means "no event".

    `cond.fillna(False)` on an object-dtype comparison silently DOWNCASTS. pandas 2.x deprecates
    that and this repo runs `filterwarnings = error`, so eight label-factory tests were RED on a
    warning -- a suite failing for a pandas-version reason teaches the desk to ignore it.

    `.where(notna, False)` rather than the `infer_objects(copy=False)` the warning suggests:
    measured on pandas 2.x, the deprecation fires INSIDE `fillna` itself, so chaining
    infer_objects afterwards is too late and still errors. `where` never downcasts, so the mask
    is built without the deprecated path at all. Applied ONCE so the intent -- "absent data is
    not an event" -- lives in one place instead of ten call sites.
    """
    return cond.where(cond.notna(), False).astype(bool)

def _need(bars: pd.DataFrame, *cols: str) -> bool:
    return all(c in bars.columns for c in cols)


def _roll_q(s: pd.Series, win: int, q: float) -> pd.Series:
    """Rolling quantile with a CAUSAL window (closed on the left of t+1, includes t)."""
    return s.rolling(win, min_periods=max(5, win // 4)).quantile(q)


def _true_range(bars: pd.DataFrame) -> pd.Series:
    hi, lo, cl = bars["high"], bars["low"], bars["close"]
    prev = cl.shift(1)
    return pd.concat([hi - lo, (hi - prev).abs(), (lo - prev).abs()], axis=1).max(axis=1)


# ------------------------------------------------------------------ the four label families

def liquidity_stress(bars: pd.DataFrame, *, atr_win: int = 20, range_mult: float = 2.0,
                     vol_q: float = 0.9, vol_win: int = 60) -> np.ndarray:
    """Range blows out relative to its own recent ATR **and** volume confirms.

    Mechanism: stress is not a big move, it is a big move that needed unusual volume to clear --
    depth was thin. Requiring both is what separates stress from a clean repricing on normal flow.
    Knowable at the close of t (lag 0): every input is same-bar or earlier.
    """
    atr_win, vol_win = int(atr_win), int(vol_win)
    if not _need(bars, "high", "low", "close"):
        return np.zeros(len(bars), dtype=np.int8)
    tr = _true_range(bars)
    atr = tr.rolling(atr_win, min_periods=max(5, atr_win // 4)).mean().shift(1)  # prior ATR only
    wide = _mask(tr > range_mult * atr)
    if _need(bars, "volume"):
        heavy = _mask(bars["volume"] > _roll_q(bars["volume"], vol_win, vol_q).shift(1))
    else:
        heavy = pd.Series(True, index=bars.index)
    return np.asarray((wide & heavy).to_numpy(), dtype=np.int8)


def forced_deleveraging(bars: pd.DataFrame, *, ret_q: float = 0.05, win: int = 60,
                        oi_drop: float = 0.02) -> np.ndarray:
    """Adverse move while OPEN INTEREST FALLS -- positions closing, not new ones opening.

    This is the actual signature of a liquidation cascade and it is why OI is load-bearing: a sharp
    drop on RISING OI is new shorts (a directional bet), the same drop on FALLING OI is existing
    longs being removed. Without OI the two are indistinguishable, so this family refuses to emit
    rather than guess -- an all-zero label is honest, a lookalike built from price alone is not.
    Knowable at the close of t (lag 0).
    """
    win = int(win)
    if not _need(bars, "close", "open_interest"):
        return np.zeros(len(bars), dtype=np.int8)
    ret = bars["close"].pct_change()
    thresh = _roll_q(ret, win, ret_q).shift(1)           # prior distribution only
    sharp_down = _mask(ret < thresh)
    oi_falling = _mask(bars["open_interest"].pct_change() < -abs(oi_drop))
    return np.asarray((sharp_down & oi_falling).to_numpy(), dtype=np.int8)


def accumulation_window(bars: pd.DataFrame, *, win: int = 20, vol_q: float = 0.3,
                        drift_max: float = 0.02, oi_rise: float = 0.05) -> np.ndarray:
    """Quiet price, compressed realised vol, and OI BUILDING -- positioning without repricing.

    Mechanism: someone is taking size without moving the market. Requires all three, because low
    vol alone is just a quiet market and rising OI alone is just growth.
    Knowable at the close of t (lag 0): the window looks BACKWARD from t.
    """
    win = int(win)
    if not _need(bars, "close"):
        return np.zeros(len(bars), dtype=np.int8)
    ret = bars["close"].pct_change()
    rv = ret.rolling(win, min_periods=max(5, win // 4)).std()
    calm = _mask(rv < _roll_q(rv, win * 5, vol_q).shift(1))
    drift = (bars["close"] / bars["close"].shift(win) - 1.0).abs()
    flat = _mask(drift < abs(drift_max))
    if _need(bars, "open_interest"):
        oi = bars["open_interest"]
        building = _mask(oi / oi.shift(win) - 1.0 > abs(oi_rise))
    else:
        building = pd.Series(True, index=bars.index)
    return np.asarray((calm & flat & building).to_numpy(), dtype=np.int8)


#: ``regime_transition``'s honest confirmation lag. A vol-regime turn is only a turn once it holds.
REGIME_CONFIRM_BARS = 5


def regime_transition(bars: pd.DataFrame, *, win: int = 20, ratio: float = 1.8,
                      confirm: int = REGIME_CONFIRM_BARS) -> np.ndarray:
    """Realised vol steps to a new level **and stays there** for ``confirm`` bars.

    THE LAGGED FAMILY, and the reason ``known_at_lag`` exists at all. Persistence is what separates
    a regime change from a single loud bar, and persistence can only be observed after the fact. So
    ``label[t]`` marks that a transition began at ``t`` and is only KNOWABLE at ``t + confirm``.
    Using it as a same-bar predictor is lookahead; ``validate`` allows exactly this lag and no more.
    """
    win, confirm = int(win), int(confirm)
    if not _need(bars, "close"):
        return np.zeros(len(bars), dtype=np.int8)
    ret = bars["close"].pct_change()
    rv = ret.rolling(win, min_periods=max(5, win // 4)).std()
    prior = rv.shift(win)
    stepped = _mask(rv > ratio * prior)

    # THE CONFIRMATION WINDOW MUST NOT CONTAIN THE BAR IT IS CONFIRMING, and the first version of
    # this did. It tested `rv.shift(-k) > ratio * prior` for k in 1..confirm -- but `rv` is a
    # `win`-bar rolling std, so with confirm=5 and win=20 every one of those five windows STILL
    # CONTAINS the initiating bar. A single enormous return keeps `rv` elevated for a full `win`
    # bars on its own, so the persistence test passed on exactly the input it existed to reject:
    # one loud bar, measured five times.
    #
    # That made the family a volatility-outlier detector wearing a regime label's name -- and the
    # damage is downstream, because an event label is a research ASSET here: studies keyed on
    # "regime transition" would have been keyed on spikes, and the lag this family pays for
    # (`known_at_lag=5`, the only non-zero one on the desk) bought nothing.
    #
    # The fix is to estimate the post-step volatility on the confirmation window ALONE -- bars
    # t+1..t+confirm, excluding t. Noisier than a 20-bar estimate, and that is the correct trade:
    # a short honest window beats a long one contaminated by the event it is judging. The declared
    # knowability lag is unchanged at `confirm`, because that is still exactly how far ahead this
    # reads.
    post = ret.rolling(max(1, confirm), min_periods=max(1, confirm)).std().shift(-confirm)
    held = stepped & _mask(post > ratio * prior)
    fresh = held & ~_mask(held.shift(1))          # mark the ONSET, not every held bar
    return np.asarray(fresh.to_numpy(), dtype=np.int8)


#: family -> (generator, honest knowability lag)
FAMILIES: dict[str, tuple[Callable[..., np.ndarray], int]] = {
    "liquidity_stress": (liquidity_stress, 0),
    "forced_deleveraging": (forced_deleveraging, 0),
    "accumulation_window": (accumulation_window, 0),
    "regime_transition": (regime_transition, REGIME_CONFIRM_BARS),
}


def generate(spec: LabelSpec, bars: pd.DataFrame) -> np.ndarray:
    fn, _lag = FAMILIES[spec.family]
    return fn(bars, **dict(spec.params))


# ------------------------------------------------------------------ validation

def _runs(y: np.ndarray) -> list[int]:
    out: list[int] = []
    run = 0
    for v in y:
        if v:
            run += 1
        elif run:
            out.append(run)
            run = 0
    if run:
        out.append(run)
    return out


def _mutate_from(bars: pd.DataFrame, cols: list[str], start: int, seed: int = 0) -> pd.DataFrame:
    """Scramble bars from ``start`` onward. Used for the RESPONSIVENESS check only.

    Causality is tested by truncation (see ``leakage_check``), not by this. Mutation survives here
    for the opposite question -- does the label react to its inputs at all? -- and the factors are
    independent PER BAR rather than a constant multiple, because a constant multiple leaves every
    pct_change unchanged and so is invisible to any return-based label.
    """
    rng = np.random.default_rng(seed)
    out = bars.copy()
    idx = out.index[start:]
    if not len(idx):
        return out
    factors = rng.lognormal(0.0, 1.5, size=len(idx))       # wildly different returns AND levels
    for c in cols:
        out.loc[idx, c] = out.loc[idx, c].to_numpy() * factors
    return out


def leakage_check(spec: LabelSpec, bars: pd.DataFrame, *,
                  sample: int = 24) -> tuple[int, int, bool]:
    """(checked, failures, responds_to_inputs): is ``label[t]`` computable at ``t + known_at_lag``?

    TRUNCATION, NOT MUTATION -- this is the definition of knowability rather than a proxy for it.
    Recompute the label on ``bars[:t + lag + 1]``, i.e. exactly the data that existed at the moment
    the label claims to be knowable, and require the value at ``t`` to be unchanged. Two earlier
    designs were tried here and BOTH passed a label that openly read five bars ahead:

      * ``libs/features/validation.py``'s mutate-the-future-by-*1000. A constant multiple leaves
        every future pct_change identical except at one boundary bar, so it is nearly blind to any
        return-based label -- which is most of them.
      * Per-bar random mutation, compared at sampled ``t``. Event labels are SPARSE, so a sampled
        point almost always compares 0 against 0; and mutating a whole tail makes everything
        uniformly "stepped", which an onset rule (``fires & ~fired_before``) then absorbs.

    Truncation has neither weakness, and SAMPLING IS WEIGHTED TO FIRING POSITIONS for the same
    sparsity reason: a violation shows up where the label actually fires, so those are the positions
    that must be checked, plus a spread of quiet ones to catch the reverse error.

    The third return value guards the OPPOSITE failure: a label that ignores its inputs passes any
    causality test perfectly -- an all-zero array is maximally causal and entirely useless.
    """
    cols = [c for c in ("open", "high", "low", "close", "volume", "open_interest")
            if c in bars.columns]
    n = len(bars)
    if not cols or n < 60:
        return 0, 0, True
    base = generate(spec, bars)
    lag = max(0, spec.known_at_lag)
    warmup = int(n * 0.25)                     # below this, rolling windows are still filling
    hi = n - lag - 2

    firing = [int(t) for t in np.flatnonzero(base) if warmup < t < hi]
    quiet = [int(t) for t in np.linspace(warmup + 1, hi, num=max(3, sample // 2)) if t < hi]
    points = sorted(set(firing[:sample] + quiet))
    if not points:
        return 0, 0, bool(base.sum())

    failures = 0
    for t in points:
        knowable_at = generate(spec, bars.iloc[:t + lag + 1])
        if len(knowable_at) > t and int(knowable_at[t]) != int(base[t]):
            failures += 1

    responds = bool(np.any(generate(spec, _mutate_from(bars, cols, 0, seed=99)) != base)
                    or base.sum())
    return len(points), failures, responds


def validate(spec: LabelSpec, bars: pd.DataFrame, *, sample: int = 24) -> LabelValidation:
    """Is this a well-formed EVENT marker?

    Profitability is a separate, multiplicity-counted test through axis_screen.
    """
    y = generate(spec, bars)
    n = max(1, len(y))
    firings = int(y.sum())
    runs = _runs(y)
    max_run = max(runs) if runs else 0
    base_rate = firings / n
    checked, failures, responds = leakage_check(spec, bars, sample=sample)

    v = LabelValidation(verdict=VERDICT_VALID, base_rate=round(base_rate, 5),
                        n_events=len(runs), n_firings=firings, max_run=max_run,
                        leak_checked=checked, leak_failures=failures,
                        responds_to_inputs=responds)

    # ORDER MATTERS: leakage is fatal and must not be masked by a base-rate complaint.
    if failures:
        v.verdict = VERDICT_LEAKING
        v.notes.append(f"label[t] changed when bars after t+{spec.known_at_lag} were mutated at "
                       f"{failures}/{checked} sampled points -- it reads the future it claims to "
                       "predate; fix the construction or raise known_at_lag with a reason")
        return v
    if not responds:
        v.verdict = VERDICT_INERT
        v.notes.append("the label never fires and never changes under a drastic input mutation -- "
                       "it is not measuring anything (missing input column, or a threshold no real "
                       "data reaches)")
        return v
    if base_rate < MIN_BASE_RATE:
        v.verdict = VERDICT_RARE
        v.notes.append(f"fires {base_rate:.4%} of bars (<{MIN_BASE_RATE:.1%}) -- too rare to carry "
                       "power at any horizon; loosen the threshold or accept it is untestable")
    elif base_rate > MAX_BASE_RATE:
        v.verdict = VERDICT_COMMON
        v.notes.append(f"fires {base_rate:.1%} of bars (>{MAX_BASE_RATE:.0%}) -- this is a STATE, "
                       "not an event. Event-study machinery assumes rarity; use it as a regime "
                       "variable or tighten it")
    elif firings and max_run > MAX_RUN_FRACTION * firings:
        v.verdict = VERDICT_BLOB
        v.notes.append(f"{max_run} of {firings} firings are one contiguous run -- that is a PERIOD "
                       "flag (one blob = 'that year'), not a repeatable event, and n_events is "
                       "effectively 1 however many bars it covers")
    return v


# ------------------------------------------------------------------ the default catalogue

def default_specs(inputs: Sequence[str] = ()) -> list[LabelSpec]:
    """The four families the queue names, at their default parameters, with lineage attached."""
    src = tuple(inputs)
    return [
        LabelSpec("liquidity_stress", "liquidity_stress",
                  {"atr_win": 20, "range_mult": 2.0, "vol_q": 0.9, "vol_win": 60},
                  src, 0,
                  "range blowout confirmed by unusual volume: a big move that needed unusual "
                  "volume to clear means depth was thin, which a clean repricing does not"),
        LabelSpec("forced_deleveraging", "forced_deleveraging",
                  {"ret_q": 0.05, "win": 60, "oi_drop": 0.02}, src, 0,
                  "adverse move with OI FALLING -- existing positions removed, not new shorts "
                  "opened; the distinction is invisible without open interest"),
        LabelSpec("accumulation_window", "accumulation_window",
                  {"win": 20, "vol_q": 0.3, "drift_max": 0.02, "oi_rise": 0.05}, src, 0,
                  "compressed vol + flat price + OI building: size being taken without repricing"),
        LabelSpec("regime_transition", "regime_transition",
                  {"win": 20, "ratio": 1.8, "confirm": float(REGIME_CONFIRM_BARS)},
                  src, REGIME_CONFIRM_BARS,
                  "realised-vol step that HOLDS; persistence is what distinguishes a regime turn "
                  "from a loud bar, and it can only be observed after the fact -- hence the lag"),
    ]


def build_catalogue(bars: pd.DataFrame, specs: Sequence[LabelSpec] | None = None,
                    inputs: Sequence[str] = ()) -> list[dict[str, Any]]:
    """Generate + validate every spec, returning one research-asset record each."""
    out = []
    for spec in (specs if specs is not None else default_specs(inputs)):
        v = validate(spec, bars)
        out.append({
            "id": spec.id, "version": spec.version, "qualified_id": spec.qualified_id,
            "family": spec.family, "params": dict(spec.params),
            "known_at_lag": spec.known_at_lag, "inputs": list(spec.inputs),
            "rationale": spec.rationale, "validation": asdict(v), "usable": v.usable,
        })
    return out

```

### libs\research\regional_parity.py
```python
"""REGIONAL PARITY -- no region absent, every region at the same DEPTH, compute by coverage debt.

THE LAW (docs/LAWS.md 5n, principal 2026-09-19, permanent). Every world region receives the same
depth of civilization -- the ten source layers in the native language, own mechanics, own
calendars, own rule states, own transmission map -- and compute is NOT equal: it follows

    Priority = P(useful) x Orthogonality x InformationGain x CoverageDebt
               / (Compute + DataCost + TrialBurden)

where the coverage-debt bonus keeps neglected regions discovering and the expected-value terms
keep low-information areas from wasting resources. The parity fence turns the desk red when a
region the packs name has no resident, no discovery in its trailing window, or no candidate in
its lattice.

WHAT THIS MODULE IS. The PURE half of that law: it opens no socket, writes no file and imports
no desk organ. It reads four things and names what it cannot read:

  * the forest federation (`libs.research.forests`) -- WHICH regions exist and which packs and
    countries each one draws on;
  * the country packs through `libs.research.country_lab` -- how DEEP each region's packs are,
    measured by the framework's own layer inventory and row counts, never by a pack's claim;
  * the moat registry, through a connection the CALLER hands it -- whether a resident is alive
    (`workers`), whether anything was discovered in the trailing window (`sources`,
    `discoveries`) and whether any candidate reached the lattice (`discoveries` cell counters,
    `research_candidates`);
  * the forest reports directory -- a resident's last completed pass.

`desks/mt5/research/research_roi.py` folds `priority` into `forest_allocation.json` (two-sided,
scout floor kept) and `scripts/check_regional_parity.py` is the fence. Both are consumers; this
module decides nothing about compute on its own.

UNMEASURED IS A VALUE (L1.28a). A registry that cannot be opened, a pack that does not resolve,
a region whose ground is a LAYER of the world rather than a place (the five global forests) --
each reads UNMEASURED by name and holds the MIDDLE of every term it feeds, never zero and never
the best. A region is flagged only on a MEASURED absence.

DEPTH IS THE FRAMEWORK'S VERDICT, NOT THE PACK'S. `pack_depth` counts what
`country_lab.CountryPack` actually carries after coercion and what `layer_inventory` actually
tags. A pack whose sources reach the framework untagged reads as UNMAPPED here, and
`untagged_sources` says so -- that is work for the pack's author, and hiding it behind the pack's
own module-level tables would make the parity number a description of this module's charity
rather than of the country.
"""
from __future__ import annotations

import json
import math
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from libs.research import country_lab as CL
from libs.research import forests as F

__all__ = [
    "DEBT_WEIGHTS",
    "DEPTH_TARGETS",
    "DISCOVERY_WINDOW_DAYS",
    "FLAGS",
    "LATTICE_TARGET",
    "RESIDENT_STALE_HOURS",
    "RULE",
    "UNMEASURED",
    "PackDepth",
    "RegionDepth",
    "clip",
    "coverage_debt",
    "depth_score",
    "flags_for",
    "median",
    "pack_depth",
    "parity_report",
    "priority_of",
    "region_depth",
    "region_signals",
    "region_tokens",
    "regional_ids",
]

ROOT = Path(__file__).resolve().parents[2]
DESK = ROOT / "desks" / "mt5"
#: Where a forest resident writes `FOREST_<ID>.json` after every pass.
REPORTS_DIR: Path = DESK / "reports"

UNMEASURED = "UNMEASURED"
#: The trailing window of the discovery half of coverage -- the country lab's own constant.
DISCOVERY_WINDOW_DAYS = CL.DISCOVERY_WINDOW_DAYS
#: A resident that has neither heartbeated nor written a report inside this many hours is not
#: present. A forest pass is budgeted at 3000 s and heartbeats at start and end; three hours
#: catches a dead resident inside the fence's own cadence without flagging a long pass.
RESIDENT_STALE_HOURS = 3.0
#: Lattice candidates at which the lattice term of the debt reaches zero.
LATTICE_TARGET = 20
#: Two-sided clip on the factors derived here, symmetric about 1.0 (GROWTH_GOVERNANCE Rule 2).
FACTOR_CLIP = (0.5, 2.0)

#: THE STANDING DEPTH RULE, as targets. A pack at or above every one of them scores 1.0; the
#: score is the mean of the eight capped ratios so no single table can buy the rest.
DEPTH_TARGETS: dict[str, float] = {
    "actors": 12.0, "domains": 10.0, "edges": 8.0, "layers": 10.0, "terms": 40.0,
    "datasets": 8.0, "eras": 4.0, "instruments": 6.0,
}
#: How the four debt terms are weighed. Layers carry the most because they are the half of the
#: depth rule a scout cannot fake by typing; the resident carries the least because a resident
#: with nothing to read produces nothing anyway.
DEBT_WEIGHTS: dict[str, float] = {"layers": 0.35, "discovery": 0.25, "lattice": 0.25,
                                  "resident": 0.15}
#: The four things the fence turns red on, exactly as the law names them, plus the one the
#: portable half can measure with no state at all.
FLAGS: tuple[str, ...] = ("NO_PACK", "NO_RESIDENT", "NO_DISCOVERY", "NO_LATTICE_CANDIDATE",
                          "DEPTH_BELOW_HALF_MEDIAN")

RULE = ("no region absent, every region at the same depth; compute follows Priority = "
        "P(useful) x Orthogonality x InformationGain x CoverageDebt / (Compute + DataCost + "
        "TrialBurden); a region with no resident, no discovery in its trailing window or no "
        "candidate in its lattice is a defect, and UNMEASURED holds the middle, never zero")


# --------------------------------------------------------------------------- small helpers
def clip(x: float, lo: float = FACTOR_CLIP[0], hi: float = FACTOR_CLIP[1]) -> float:
    return max(lo, min(hi, float(x)))


def median(values: Iterable[float]) -> float | None:
    got = sorted(float(v) for v in values)
    if not got:
        return None
    n = len(got)
    mid = n // 2
    return got[mid] if n % 2 else 0.5 * (got[mid - 1] + got[mid])


def _mean(values: Iterable[float]) -> float | None:
    got = [float(v) for v in values]
    return (sum(got) / len(got)) if got else None


def _parse_stamp(text: Any) -> datetime | None:
    s = str(text or "").strip()
    if not s:
        return None
    try:
        got = datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        return None
    return got if got.tzinfo is not None else got.replace(tzinfo=UTC)


def _age_hours(stamp: Any, now: datetime) -> float | None:
    got = _parse_stamp(stamp)
    if got is None:
        return None
    return (now - got).total_seconds() / 3600.0


def regional_ids() -> tuple[str, ...]:
    """The regional forests, in registry order -- the regions the packs name."""
    return tuple(f.id for f in F.REGIONAL_FORESTS)


def region_tokens(forest_id: str) -> frozenset[str]:
    """Every lower-case token the registry may stamp on a row that belongs to this forest: the
    forest id, its ISO-2 countries, its pack directory codes and its deep-forest grounds."""
    f = F.forest(forest_id)
    toks = {f.id.lower(), f.name.lower()}
    toks |= {c.lower() for c in f.countries}
    toks |= {p.lower() for p in f.packs}
    toks |= {g.lower() for g in f.grounds}
    return frozenset(t for t in toks if t)


# --------------------------------------------------------------------------- depth
@dataclass(frozen=True)
class PackDepth:
    """One pack, measured by what the framework can read out of it."""

    code: str
    resolved: bool = False
    actors: int = 0
    domains: int = 0
    edges: int = 0
    terms: int = 0
    datasets: int = 0
    eras: int = 0
    instruments: int = 0
    languages: int = 0
    layers_mapped: int = 0            # MAPPED or ABSENT_DECLARED
    layers_unverified: int = 0        # declared, nothing fetched yet
    layers_unmapped: int = 0          # no source and no declared absence
    untagged_sources: int = 0
    pit_feasible_share: float | None = None
    fatal: tuple[str, ...] = ()
    score: float | None = None
    why: str = ""

    @property
    def layers_declared(self) -> int:
        return self.layers_mapped + self.layers_unverified

    def as_row(self) -> dict[str, Any]:
        return {"code": self.code, "resolved": self.resolved, "actors": self.actors,
                "domains": self.domains, "edges": self.edges, "terms": self.terms,
                "datasets": self.datasets, "eras": self.eras, "instruments": self.instruments,
                "languages": self.languages, "layers_mapped": self.layers_mapped,
                "layers_unverified": self.layers_unverified,
                "layers_unmapped": self.layers_unmapped,
                "layers_declared": self.layers_declared,
                "untagged_sources": self.untagged_sources,
                "pit_feasible_share": self.pit_feasible_share, "fatal": list(self.fatal),
                "score": self.score, "why": self.why}


def depth_score(d: PackDepth) -> float:
    """The mean of the eight capped ratios against `DEPTH_TARGETS`, in [0, 1]."""
    have = {"actors": d.actors, "domains": d.domains, "edges": d.edges,
            "layers": d.layers_declared, "terms": d.terms, "datasets": d.datasets,
            "eras": d.eras, "instruments": d.instruments}
    ratios = [min(1.0, float(have[k]) / t) for k, t in DEPTH_TARGETS.items() if t > 0]
    return round(sum(ratios) / len(ratios), 6) if ratios else 0.0


def pack_depth(pack: CL.CountryPack | None, code: str = "",
               reg: Mapping[str, Mapping[str, Any]] | None = None) -> PackDepth:
    """Measure one pack. A pack that does not resolve is UNMEASURED by name, never a zero row."""
    if pack is None:
        return PackDepth(code=code or "?", resolved=False,
                         why=f"{UNMEASURED}: no country pack resolves for {code!r}")
    inventory = CL.layer_inventory(pack.code, pack=pack)
    mapped = unverified = unmapped = 0
    for layer in CL.SOURCE_LAYERS:
        rows = inventory[layer]
        if any(r.get("absent_reason") for r in rows) or any(r.get("verified") for r in rows):
            mapped += 1
        elif rows:
            unverified += 1
        else:
            unmapped += 1
    terms = {t for words in dict(pack.terminology).values() for t in words}
    pit = [bool(ds.pit_feasible) for ds in pack.datasets]
    try:
        problems = CL.validate_pack(pack, reg)
    except Exception as exc:                    # a pack that breaks the validator is a defect
        problems = [f"pack row: FAILED validate_pack raised {type(exc).__name__}: {exc}"]
    fatal = tuple(CL.fatal_problems(problems))
    d = PackDepth(code=pack.code, resolved=True, actors=len(pack.actors),
                  domains=len(pack.domains), edges=len(pack.transmission_edges_seed),
                  terms=len(terms), datasets=len(pack.datasets), eras=len(pack.policy_eras),
                  instruments=len(pack.executable_instruments),
                  languages=len(pack.native_languages), layers_mapped=mapped,
                  layers_unverified=unverified, layers_unmapped=unmapped,
                  untagged_sources=len(inventory["UNTAGGED"]),
                  pit_feasible_share=(round(sum(pit) / len(pit), 4) if pit else None),
                  fatal=fatal)
    score = depth_score(d)
    why = (f"{score:.3f}: {mapped} mapped + {unverified} declared-unverified + {unmapped} "
           f"unmapped layers; {len(pack.actors)} actors, {len(pack.domains)} domains, "
           f"{len(pack.transmission_edges_seed)} edges, {len(terms)} terms")
    if inventory["UNTAGGED"]:
        why += (f"; {len(inventory['UNTAGGED'])} source(s) reach the framework UNTAGGED -- "
                f"work for the pack's author, not coverage")
    if fatal:
        why += f"; FATAL: {fatal[0]}"
    return PackDepth(**{**d.__dict__, "score": score, "why": why})


@dataclass(frozen=True)
class RegionDepth:
    """One forest's depth: its packs measured, its missing packs named."""

    forest: str
    kind: str = "regional"
    packs: tuple[PackDepth, ...] = ()
    missing: tuple[str, ...] = ()
    package: str = ""
    score_mean: float | None = None
    score_max: float | None = None
    why: str = ""

    @property
    def measured(self) -> bool:
        return self.score_mean is not None

    def as_row(self) -> dict[str, Any]:
        return {"forest": self.forest, "kind": self.kind,
                "packs": [p.as_row() for p in self.packs], "missing": list(self.missing),
                "package": self.package, "score_mean": self.score_mean,
                "score_max": self.score_max, "why": self.why}


def region_depth(forest_id: str, *,
                 resolver: Callable[[str], CL.CountryPack | None] | None = None,
                 reg: Mapping[str, Mapping[str, Any]] | None = None) -> RegionDepth:
    """Depth of one forest = its resolvable packs measured; the ones that do not resolve named.

    A forest with a dedicated region PACKAGE and no packs (Japan) is UNMEASURED here rather than
    zero: the package is a department the country lab does not read, and pricing it at zero
    would defund the deepest civilization on the desk for the crime of predating the packs.
    """
    f = F.forest(forest_id)
    resolve = resolver or CL.resolve_pack
    rows: list[PackDepth] = []
    missing: list[str] = []
    for code in f.packs:
        try:
            got = resolve(code)
        except Exception:
            got = None
        d = pack_depth(got, code, reg)
        if d.resolved:
            rows.append(d)
        else:
            missing.append(code)
    scores = [p.score for p in rows if p.score is not None]
    if f.kind != "regional":
        why = f"{UNMEASURED}: a global forest's ground is a layer of the world, not a place"
        return RegionDepth(forest=f.id, kind=f.kind, package=f.package, why=why)
    if not rows:
        why = (f"{UNMEASURED}: no country pack resolves for {f.id}"
               + (f" (declared but absent: {missing})" if missing else "")
               + (f"; the region runs as the package {f.package}" if f.package else
                  "; NO PACK AND NO PACKAGE"))
        return RegionDepth(forest=f.id, kind=f.kind, missing=tuple(missing),
                           package=f.package, why=why)
    mean = _mean(scores)
    why = (f"{len(rows)} pack(s) measured, mean depth {mean:.3f}, max {max(scores):.3f}"
           + (f"; declared but absent: {missing}" if missing else ""))
    return RegionDepth(forest=f.id, kind=f.kind, packs=tuple(rows), missing=tuple(missing),
                       package=f.package, score_mean=round(float(mean or 0.0), 6),
                       score_max=round(max(scores), 6), why=why)


# --------------------------------------------------------------------------- live signals
def _worker_ids(forest_id: str) -> tuple[str, ...]:
    """The heartbeat ids a resident for this forest may write under: its own forest id, and the
    department id of the task it rides (`RIDES`), read from the task name rather than typed."""
    fid = F.forest(forest_id).id
    task = F.resident_task(fid)
    suffix = task.rsplit("-", 1)[-1].lower()
    ids = [f"forest:{fid}", f"dept:{fid}", f"dept:{suffix}"]
    return tuple(dict.fromkeys(ids))


def _count(conn: Any, sql: str, params: Sequence[Any]) -> int | None:
    try:
        row = conn.execute(sql, tuple(params)).fetchone()
    except Exception:
        return None
    if row is None:
        return 0
    try:
        return int(row[0] or 0)
    except (TypeError, ValueError, IndexError):
        return None


def region_signals(forest_id: str, conn: Any = None, *, now: datetime | None = None,
                   window_days: int = DISCOVERY_WINDOW_DAYS,
                   reports_dir: Path | None = None,
                   stale_hours: float = RESIDENT_STALE_HOURS) -> dict[str, Any]:
    """Resident present? Discovery in the trailing window? Candidates in the lattice?

    Every answer is an int or bool when the instrument could be read and None (UNMEASURED) with
    a reason when it could not. A readable table that holds nothing is a MEASURED zero.
    """
    fid = F.forest(forest_id).id
    at = now or datetime.now(tz=UTC)
    cutoff = (at - timedelta(days=int(window_days))).isoformat()
    toks = sorted(region_tokens(fid))
    out: dict[str, Any] = {"forest": fid, "window_days": int(window_days), "tokens": toks,
                           "resident": None, "resident_why": "", "heartbeat_age_h": None,
                           "report_age_h": None, "sources_window": None,
                           "discoveries_window": None, "discoveries_total": None,
                           "lattice_candidates": None, "unmeasured": []}
    # ---- the resident: a heartbeat in the registry, or a fresh report on disk ----------------
    rdir = reports_dir if reports_dir is not None else REPORTS_DIR
    report = rdir / F.forest(fid).report_name
    report_age: float | None = None
    report_readable = False
    try:
        doc = json.loads(report.read_text(encoding="utf-8-sig"))
        report_readable = True
        report_age = _age_hours(doc.get("at") if isinstance(doc, Mapping) else None, at)
    except (OSError, ValueError):
        report_readable = False
    out["report_age_h"] = None if report_age is None else round(report_age, 2)
    hb_age: float | None = None
    hb_readable = False
    if conn is not None:
        ids = _worker_ids(fid)
        marks = ",".join("?" for _ in ids)
        try:                     # only the "?" placeholder list is interpolated, never a value
            rows = conn.execute(f"SELECT worker_id, status, last_seen FROM workers WHERE "  # noqa: S608
                                f"worker_id IN ({marks})", ids).fetchall()
            hb_readable = True
        except Exception:
            rows = []
        for r in rows:
            try:
                status, seen = str(r["status"]), r["last_seen"]
            except (TypeError, KeyError, IndexError):
                status, seen = str(r[1]), r[2]
            age = _age_hours(seen, at)
            if age is not None and status == "running" and (hb_age is None or age < hb_age):
                hb_age = age
    out["heartbeat_age_h"] = None if hb_age is None else round(hb_age, 2)
    fresh_hb = hb_age is not None and hb_age <= float(stale_hours)
    fresh_report = report_age is not None and report_age <= float(stale_hours)
    if fresh_hb or fresh_report:
        out["resident"] = True
        out["resident_why"] = ("heartbeat" if fresh_hb else "report") + " inside the window"
    elif hb_readable or rdir.exists():
        out["resident"] = False
        out["resident_why"] = (
            f"no running heartbeat under {list(_worker_ids(fid))} "
            f"{'' if hb_readable else '(workers table unreadable) '}and "
            + (f"{report.name} is {report_age:.1f}h old" if report_age is not None else
               (f"{report.name} carries no readable stamp" if report_readable else
                f"{report.name} is absent")))
    else:
        out["resident_why"] = (f"{UNMEASURED}: neither the registry nor {rdir} is readable")
        out["unmeasured"].append("resident")
    # ---- discovery: scouts adding sources, and forest-generated discoveries -----------------
    if conn is None:
        out["unmeasured"].extend(["discovery", "lattice"])
        out["why"] = f"{UNMEASURED}: no registry connection; discovery and lattice unread"
        return out
    # Only "?" placeholder lists and the OR-joined `generator LIKE ?` clause are interpolated
    # below; every value travels as a bound parameter, which is what S608 cannot see.
    marks = ",".join("?" for _ in toks)
    out["sources_window"] = _count(
        conn, f"SELECT COUNT(*) FROM sources WHERE lower(COALESCE(country,'')) IN ({marks}) "  # noqa: S608
              f"AND first_seen >= ?", [*toks, cutoff])
    pats = [f"{fid}:%", f"%:{fid}:%", f"%:{fid}"]
    gen = " OR ".join("generator LIKE ?" for _ in pats)
    out["discoveries_window"] = _count(
        conn, f"SELECT COUNT(*) FROM discoveries WHERE ({gen}) AND created_at >= ?",  # noqa: S608
        [*pats, cutoff])
    out["discoveries_total"] = _count(
        conn, f"SELECT COUNT(*) FROM discoveries WHERE ({gen})", pats)  # noqa: S608
    # ---- the lattice: discoveries that produced cells, plus candidates the forest generated ---
    cells = _count(
        conn, f"SELECT COUNT(*) FROM discoveries WHERE ({gen}) AND (COALESCE(generated_cells,0)"  # noqa: S608
              f" + COALESCE(compiled_cells,0) + COALESCE(queued_cells,0) + "
              f"COALESCE(tested_cells,0)) > 0", pats)
    cands = _count(conn, f"SELECT COUNT(*) FROM research_candidates WHERE ({gen})", pats)  # noqa: S608
    if cells is None and cands is None:
        out["unmeasured"].append("lattice")
    else:
        out["lattice_candidates"] = int(cells or 0) + int(cands or 0)
    if out["sources_window"] is None and out["discoveries_window"] is None:
        out["unmeasured"].append("discovery")
    return out


# --------------------------------------------------------------------------- the debt
def _term_or_middle(value: float | None, name: str, unmeasured: list[str]) -> float:
    if value is None:
        unmeasured.append(name)
        return 0.5
    return max(0.0, min(1.0, float(value)))


def coverage_debt(region: str, *, depth: RegionDepth | None = None,
                  signals: Mapping[str, Any] | None = None, conn: Any = None,
                  now: datetime | None = None, window_days: int = DISCOVERY_WINDOW_DAYS,
                  resolver: Callable[[str], CL.CountryPack | None] | None = None,
                  reports_dir: Path | None = None) -> dict[str, Any]:
    """How much of the standing depth rule this region still owes, in [0, 1], term by term.

    `layers` rises with every UNMAPPED layer (a declared-but-unverified layer counts half);
    `discovery` is 1 when nothing was added in the trailing window and falls with the rate;
    `lattice` is 1 when no candidate reached the lattice and falls toward `LATTICE_TARGET`;
    `resident` is 1 when nobody is running the forest. An UNMEASURED term holds 0.5 by name.
    """
    fid = F.forest(region).id
    d = depth if depth is not None else region_depth(fid, resolver=resolver)
    s = dict(signals) if signals is not None else region_signals(
        fid, conn, now=now, window_days=window_days, reports_dir=reports_dir)
    unmeasured: list[str] = []
    layers_term: float | None
    if d.packs:
        per = [1.0 - (p.layers_mapped + 0.5 * p.layers_unverified) / len(CL.SOURCE_LAYERS)
               for p in d.packs]
        layers_term = sum(per) / len(per)
    elif d.kind == "regional" and not d.package:
        layers_term = 1.0                      # nothing mapped because nothing exists
    else:
        layers_term = None
    n_disc = None
    if s.get("sources_window") is not None or s.get("discoveries_window") is not None:
        n_disc = int(s.get("sources_window") or 0) + int(s.get("discoveries_window") or 0)
    disc_term = None if n_disc is None else (
        1.0 if n_disc == 0 else max(0.0, 1.0 - (n_disc / max(1, int(window_days)))))
    lattice = s.get("lattice_candidates")
    lattice_term = None if lattice is None else (
        1.0 if int(lattice) == 0 else max(0.0, 1.0 - int(lattice) / float(LATTICE_TARGET)))
    resident = s.get("resident")
    resident_term = None if resident is None else (0.0 if resident else 1.0)
    terms = {"layers": _term_or_middle(layers_term, "layers", unmeasured),
             "discovery": _term_or_middle(disc_term, "discovery", unmeasured),
             "lattice": _term_or_middle(lattice_term, "lattice", unmeasured),
             "resident": _term_or_middle(resident_term, "resident", unmeasured)}
    debt = sum(DEBT_WEIGHTS[k] * v for k, v in terms.items())
    return {"region": fid, "debt": round(debt, 6), "terms": {k: round(v, 6) for k, v in
                                                            terms.items()},
            "weights": dict(DEBT_WEIGHTS), "unmeasured": unmeasured,
            "why": (f"debt {debt:.3f} = " + " + ".join(f"{DEBT_WEIGHTS[k]:.2f}x{v:.2f} {k}"
                                                        for k, v in terms.items())
                    + (f"; UNMEASURED held at the middle: {unmeasured}" if unmeasured else ""))}


# --------------------------------------------------------------------------- the priority
def priority_of(*, p_useful: float, orthogonality: float, information_gain: float,
                coverage_debt: float, compute: float = 0.0, data_cost: float = 0.0,
                trial_burden: float = 0.0) -> float:
    """The law's formula, with the debt entering as a BONUS (1 + debt) and every cost entering
    against a unit floor so an unpriced region is neither infinite nor zero."""
    num = (max(0.0, p_useful) * max(0.0, orthogonality) * max(0.0, information_gain)
           * (1.0 + max(0.0, coverage_debt)))
    den = 1.0 + max(0.0, compute) + max(0.0, data_cost) + max(0.0, trial_burden)
    return round(num / den, 6)


def _norm(value: float | None, mean: float | None) -> float | None:
    if value is None:
        return None
    if mean is None or mean <= 0:
        return 0.0
    return float(value) / float(mean)


def flags_for(row: Mapping[str, Any], median_depth: float | None) -> list[str]:
    """The law's four red conditions plus NO_PACK, on MEASURED absences only."""
    out: list[str] = []
    if row.get("kind") != "regional":
        return out
    depth = row.get("depth") or {}
    sig = row.get("signals") or {}
    if not depth.get("packs") and not depth.get("package"):
        out.append("NO_PACK")
    if sig.get("resident") is False:
        out.append("NO_RESIDENT")
    n_disc = None
    if sig.get("sources_window") is not None or sig.get("discoveries_window") is not None:
        n_disc = int(sig.get("sources_window") or 0) + int(sig.get("discoveries_window") or 0)
    if n_disc == 0:
        out.append("NO_DISCOVERY")
    if sig.get("lattice_candidates") == 0:
        out.append("NO_LATTICE_CANDIDATE")
    score = depth.get("score_mean")
    if score is not None and median_depth is not None and float(score) < 0.5 * median_depth:
        out.append("DEPTH_BELOW_HALF_MEDIAN")
    return out


@dataclass(frozen=True)
class _Costs:
    compute: float | None = None
    api: float | None = None
    trials: float | None = None
    extra: dict[str, Any] = field(default_factory=dict)


def _costs_of(costs: Mapping[str, Mapping[str, Any]] | None, fid: str) -> _Costs:
    row = (costs or {}).get(fid)
    if not isinstance(row, Mapping):
        return _Costs()

    def num(key: str) -> float | None:
        v = row.get(key)
        try:
            return None if v is None else float(v)
        except (TypeError, ValueError):
            return None

    return _Costs(compute=num("compute_hours"), api=num("api_calls"), trials=num("trials"))


def parity_report(regions: Sequence[str] | None = None, *, conn: Any = None,
                  now: datetime | None = None, window_days: int = DISCOVERY_WINDOW_DAYS,
                  region_roi: Mapping[str, float | None] | None = None,
                  costs: Mapping[str, Mapping[str, Any]] | None = None,
                  resolver: Callable[[str], CL.CountryPack | None] | None = None,
                  reports_dir: Path | None = None,
                  reg: Mapping[str, Mapping[str, Any]] | None = None,
                  stale_hours: float = RESIDENT_STALE_HOURS) -> dict[str, Any]:
    """For every FOREST region: resident present? discovery in the window? candidates in the
    lattice? layers mapped? depth vs the median region? -- and the priority each earns.

    `region_roi` and `costs` are the research-ROI organ's own per-region numbers when it is the
    caller (P(useful) and the denominator); absent, both hold the middle by name. The report is
    a plain mapping so the allocator can fold it into its file and the fence can write it.
    """
    at = now or datetime.now(tz=UTC)
    ids = tuple(F.forest(r).id for r in regions) if regions else tuple(F.FORESTS)
    depths = {fid: region_depth(fid, resolver=resolver, reg=reg) for fid in ids}
    signals = {fid: region_signals(fid, conn, now=at, window_days=window_days,
                                   reports_dir=reports_dir, stale_hours=stale_hours)
               for fid in ids}
    debts = {fid: coverage_debt(fid, depth=depths[fid], signals=signals[fid]) for fid in ids}
    med = median(d.score_mean for d in depths.values()
                 if d.kind == "regional" and d.score_mean is not None)
    # P(useful): the measured ROI against the mean of the measured ROIs, halved into [0.25, 1].
    rois = {fid: (region_roi or {}).get(fid) for fid in ids}
    measured_roi = [float(v) for v in rois.values() if isinstance(v, (int, float))]
    mean_roi = _mean(measured_roi)
    totals_disc = sum(int(s["discoveries_total"] or 0) for s in signals.values()
                      if s.get("discoveries_total") is not None)
    cost_rows = {fid: _costs_of(costs, fid) for fid in ids}
    mean_compute = _mean(c.compute for c in cost_rows.values() if c.compute is not None)
    mean_trials = _mean(c.trials for c in cost_rows.values() if c.trials is not None)
    rows: dict[str, dict[str, Any]] = {}
    for fid in ids:
        d, s, debt, c = depths[fid], signals[fid], debts[fid], cost_rows[fid]
        unmeasured: list[str] = list(debt["unmeasured"])
        roi = rois[fid]
        if isinstance(roi, (int, float)) and mean_roi is not None and mean_roi > 0:
            p_useful = clip(float(roi) / mean_roi) / 2.0
        else:
            p_useful = 0.5
            unmeasured.append("p_useful")
        n_total = s.get("discoveries_total")
        if n_total is None:
            orth, ig = 1.0, 1.0
            unmeasured.append("orthogonality")
        else:
            share = (int(n_total) / totals_disc) if totals_disc > 0 else 0.0
            orth = 1.0 - min(0.9, share)
            lat = s.get("lattice_candidates")
            ig = 1.0 / (1.0 + math.log1p(int(lat))) if lat is not None else 1.0
        compute_n = _norm(c.compute, mean_compute)
        trials_n = _norm(c.trials, mean_trials)
        pit = [p.pit_feasible_share for p in d.packs if p.pit_feasible_share is not None]
        data_cost = (1.0 - sum(pit) / len(pit)) if pit else None
        if compute_n is None:
            unmeasured.append("compute")
        if trials_n is None:
            unmeasured.append("trial_burden")
        if data_cost is None:
            unmeasured.append("data_cost")
        terms = {"p_useful": round(p_useful, 6), "orthogonality": round(orth, 6),
                 "information_gain": round(ig, 6), "coverage_debt": debt["debt"],
                 "compute": round(compute_n if compute_n is not None else 0.0, 6),
                 "data_cost": round(data_cost if data_cost is not None else 0.5, 6),
                 "trial_burden": round(trials_n if trials_n is not None else 0.0, 6)}
        prio = priority_of(**terms)
        row: dict[str, Any] = {
            "forest": fid, "kind": d.kind, "depth": d.as_row(), "signals": s,
            "coverage_debt": debt, "priority": prio, "priority_terms": terms,
            "layers_mapped": (sum(p.layers_mapped for p in d.packs) / len(d.packs)
                              if d.packs else None),
            "layers_declared": (sum(p.layers_declared for p in d.packs) / len(d.packs)
                                if d.packs else None),
            "depth_score": d.score_mean, "depth_vs_median": (
                None if d.score_mean is None or not med else round(d.score_mean / med, 6)),
            "unmeasured": sorted(set(unmeasured)),
        }
        row["flags"] = flags_for(row, med)
        rows[fid] = row
    prios = [r["priority"] for r in rows.values()]
    mean_p = _mean(prios)
    for r in rows.values():
        r["priority_factor"] = (round(clip(r["priority"] / mean_p), 6)
                                if mean_p and mean_p > 0 else 1.0)
    counts = {flag: sum(1 for r in rows.values() if flag in r["flags"]) for flag in FLAGS}
    return {"at": at.isoformat(timespec="seconds"), "window_days": int(window_days),
            "median_depth": med, "n_regions": len(rows),
            "n_regional": sum(1 for r in rows.values() if r["kind"] == "regional"),
            "regions": rows, "flag_counts": counts,
            "flagged": sorted(fid for fid, r in rows.items() if r["flags"]),
            "mean_priority": (round(mean_p, 6) if mean_p is not None else None),
            "law": "docs/LAWS.md 5n", "rule": RULE}

```

### libs\research\slot_registry.py
```python
"""Single source of truth for the CONCURRENT forward-confirmation slot cohort (the Holm `m`).

Under the TWO-STAGE DISCOVERY LAW the backtest gauntlet has ZERO promotion authority; promotion to
capital comes only from pre-registered FORWARD evidence, and the only multiplicity that applies
there is the number of CONCURRENTLY ACCRUING clocks -- Holm-corrected, capped at
MAX_FORWARD_SLOTS=12. That cohort size is therefore the single most load-bearing integer on the
desk's only path from research to capital.

It was being counted three different ways by three different files:
  * scripts/run_axis_shadows.py -- holm_bar(len(_AXES)) => m=4, the AXIS clocks only
  * scripts/run_alerts.py       -- len(registry) + a hardcoded `_standing = 6` + the axis count
  * data/shadow_sleeves.json    -- [], and it is a RUN-ROSTER of derivative sleeve names
                                   (scripts/run_derivative_shadow.py:77-81), never a cohort registry
Measured 2026-07-30: the axis clocks applied holm_bar(4)=2.24 while the true cohort was 12-13
(bar 2.64-2.67) -- alpha 0.0125 per clock against an intended 0.05/13=0.0038, a realized
family-wise error rate ~3.2x the design. Understating m LOOSENS the bar, so the error ran in the
PHANTOM-EDGE direction. Three deep sweeps (2026-07-26/28/29) each found this and each carried it.

FAIL-SAFE DIRECTION (deliberate, and the reason this is not a plain `len()`): a missing or
unreadable source silently SHRINKS m and loosens every bar, so unknown sources never count as
zero -- they mark the cohort `complete=False`, which run_alerts surfaces. Likewise a dormant clock
is counted until it is RETIRED by an explicit ledgered decision: over-counting only tightens the
bar (the safe error), under-counting admits noise as edge.

Stdlib plus TWO in-repo imports, and each is the price of not guessing something that cannot be
guessed safely. `libs.ops.desk_host` answers whether this box owns the runtime state under
`data/`: that cannot be settled from the artifacts themselves -- on a clone the evidence and its
absence look identical -- and guessing it wrong publishes a small cohort as MEASURED, a LOOSER
bar. `libs.research.clock_retirement` carries the tracked ledger of clocks that have LEFT the
cohort by explicit decision, which is the only sanctioned way `m` may ever fall.

import from libs.research.slot_registry.
"""
from __future__ import annotations

import contextlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from libs.ops.desk_host import is_owning_host
from libs.research.clock_retirement import multiplicity_high_water, retired_names

_ROOT = Path(__file__).resolve().parents[2]

#: Law cap -- the fixed-for-life forward bar is only fixed while the cohort stays at/below this.
MAX_FORWARD_SLOTS = 12

#: Standing sleeve clocks, each proven by its own on-disk state file carrying a `shadow_start`.
#: Named explicitly (not globbed) so that ADDING a clock is a visible code change and REMOVING one
#: cannot happen by a file quietly disappearing -- a vanished source becomes `unknown`, not absent.
_STANDING_STATES: dict[str, str] = {
    "cashcarry": "data/cashcarry_shadow_state.json",
    "crossasset": "data/crossasset_shadow_state.json",
    "crypto_combined": "data/crypto_shadow_state.json",
    "trend_30d": "data/trend_shadow_state.json",
    "trend_regime": "data/trend_regime_shadow_state.json",
    "legacy_shadow": "data/shadow_state.json",
}

#: Built-in derivative-shadow sleeves (scripts/run_derivative_shadow.py:77). Extras registered in
#: data/shadow_sleeves.json are added on top -- that file is the RUN roster, and every sleeve it
#: schedules is also a live clock, so it feeds the cohort even though it does not define it.
_DERIVATIVE_BUILTIN: tuple[str, ...] = ("oi_divergence", "ls_contrarian")

_AXIS_STATE = "data/axis_shadow_state.json"
_SLEEVE_ROSTER = "data/shadow_sleeves.json"
_OUT = "data/forward_slots.json"

#: Slot -> (evidence artifact, day-count field). The STATE files above prove a clock was BORN;
#: these prove it is still BREATHING, and the two are not the same question. Measured 2026-08-01:
#: the standing states are birth-certificate stubs carrying nothing but `shadow_start` and are
#: never rewritten, while the derivative slots' state was the hardcoded string literal "ACCRUING"
#: -- so `derive_slots()` ASSERTED that 12 of 12 clocks were accruing without reading a single day
#: count. Five were not: crossasset frozen 41 days at day 1 with NO scheduler line anywhere,
#: cny_premium pinned at 0/40 for 9 days (every z20 null, skipped at run_axis_shadows.py:131),
#: walcl re-stamping one 07-29 observation daily, defi_utilisation 4 days of exactly-zero returns,
#: and cashcarry silently missing its 08-01 run. `idle_slots: 0` then suppressed every idleness
#: alert. This is the L1.28a rule turned on the desk's own evidence pipeline: UNMEASURED
#: UTILISATION COUNTS AS ZERO, and a capability is proven by its ARTIFACT, never by a flag.
_EVIDENCE: dict[str, tuple[str, str]] = {
    "cashcarry": ("web/cashcarry_shadow.json", "forward_days"),
    "crossasset": ("web/crossasset_shadow.json", "forward_days"),
    "crypto_combined": ("web/crypto_shadow.json", "forward_days"),
    "trend_30d": ("web/trend_shadow.json", "forward_days"),
    "trend_regime": ("web/trend_regime_shadow.json", "forward_days"),
    "legacy_shadow": ("web/shadow.json", "forward_days"),
    "oi_divergence": ("web/derivative_shadow.json", "days_accumulated"),
    "ls_contrarian": ("web/derivative_shadow.json", "days_accumulated"),
}

#: A forward clock advances once per day. Past this its artifact is not evidence, it is a fossil.
STALE_AFTER_H = 36.0


def _parse_ts(raw: object) -> datetime | None:
    if not isinstance(raw, str) or not raw:
        return None
    try:
        ts = datetime.fromisoformat(raw)
    except ValueError:
        return None
    return ts if ts.tzinfo else ts.replace(tzinfo=UTC)


def _sleeve_verdict(name: str) -> str:
    """The Stage-B verdict a sleeve's own runner published, or "" when it publishes none.

    THE FIVE `FAILING FORWARD -> kill` VERDICTS WERE INERT BECAUSE THEY NEVER REACHED A SLOT ROW.
    `forward_verdict()` (libs/research/event_density.py) is shared by five shadow runners and each
    writes its string into `web/<sleeve>_shadow.json`. `derive_slots` read those artifacts for
    `forward_days` and `updated` and dropped the verdict on the floor, so every sleeve slot
    reached `slot_displacement.classify_slot` carrying `state="since <date>"` -- a birth date,
    never an outcome. The classifier could not see a kill because a kill was never in the row.

    Axis rows already carry their verdict (the axis branch reads `row["verdict"]`), which is why
    the axis half of the cohort could be reclaimed and the sleeve half could not.
    """
    ref = _EVIDENCE.get(name)
    if ref is None:
        return ""
    doc = _read_json(ref[0])
    return str(doc.get("verdict", "")) if isinstance(doc, dict) else ""


def _evidence(name: str, now: datetime, *, days: object = None,
              updated: object = None) -> dict[str, Any]:
    """Is this clock BREATHING? Never asserts -- reports UNMEASURED when it cannot tell.

    Axis slots pass their own row's `days`/`updated`; everything else is looked up in _EVIDENCE.
    NO-EVIDENCE (day count 0) is kept DISTINCT from STALLED (artifact not rewritten): a clock can
    run perfectly on schedule and still accrue nothing, which is exactly how cny_premium sat at
    0/40 for nine days while its collector reported green every morning.
    """
    src = "(axis row)"
    if days is None and updated is None:
        ref = _EVIDENCE.get(name)
        if ref is None:
            # NOT A DEAD END, and treating it as one is what left every auto-spawned clock at
            # UNMEASURED forever. `_EVIDENCE` is a fixed eight-name map written when eight clocks
            # existed; a sleeve spawned afterwards appears in none of it, so it could never
            # publish a day count, never accrue, and never resolve -- born, registered, charged
            # its multiplicity, and structurally unable to finish. Paper sleeves publish through
            # ONE artifact keyed by name, so a sleeve spawned tomorrow is covered with no map to
            # edit (nothing hardcoded).
            return _paper_sleeve_evidence(name, now)
        src = ref[0]
        doc = _read_json(src)
        if not isinstance(doc, dict):
            return {"evidence": "UNMEASURED", "why": f"{src} missing or unreadable", "source": src}
        days, updated = doc.get(ref[1]), doc.get("updated")
    ts = _parse_ts(updated)
    if ts is None:
        return {"evidence": "UNMEASURED", "why": f"{src} carries no parseable `updated`",
                "source": src}
    age_h = round((now - ts).total_seconds() / 3600.0, 1)
    try:
        # `days` is object-typed off a JSON dict, so narrow before converting rather than
        # silencing. The old `# type: ignore[arg-type]` had stopped matching the real error
        # (call-overload) and mypy then flagged the ignore itself as unused -- two errors from
        # one stale suppression, and CI red on master until it was removed.
        n_days = int(days) if isinstance(days, (int, float, str)) else int(str(days))
    except (TypeError, ValueError):
        return {"evidence": "UNMEASURED", "why": f"{src} carries no day count",
                "source": src, "age_h": age_h}
    state = ("NO-EVIDENCE" if n_days <= 0 else
             "STALLED" if age_h > STALE_AFTER_H else "ACCRUING")
    return {"evidence": state, "days": n_days, "age_h": age_h, "source": src}


#: Where scripts/run_paper_sleeve_forward.py publishes every paper sleeve's accrual, keyed by name.
_PAPER_FORWARD = "web/paper_sleeve_forward.json"


def _paper_sleeve_evidence(name: str, now: datetime) -> dict[str, Any]:
    """Accrual for an auto-spawned paper sleeve, read from the one artifact that carries them all.

    ROWS ARE THE CLOCK, not calendar days. A sleeve can sit alive for a week while its source
    artifact is never regenerated, and counting those days as forward evidence would credit the
    clock for observations that do not exist -- the fossil problem, one level in. So `days` here
    is rows added since baseline, and a sleeve with none reads NO-EVIDENCE (distinct from STALLED,
    which is about the artifact ageing).
    """
    # A SCREEN-SPAWNED CLOCK PUBLISHES SOMEWHERE ELSE, and reading only the paper-sleeve artifact
    # is what starved one (2026-08-14). `perpdex_funding::aster_BTCUSDT_level_rate::8h` was
    # reported NO-EVIDENCE with zero observations while SEVEN rows sat in
    # data/perpdex_funding_clock.jsonl -- its collector cronned, run all week, 184,753 rows. The
    # cohort read that zero as a MEASUREMENT, the sweep called the seat reclaimable, and the
    # unattended path retired a clock that had evidence.
    #
    # `stage_a_screen(clock=...)` announces every clock it starts into the axis clock registry, so
    # the registry is the one place that knows where a screen-spawned clock's rows actually live.
    # Checked FIRST, because a name present there is definitionally not a paper sleeve.
    reg_ev = _registered_clock_evidence(name, now)
    if reg_ev is not None:
        return reg_ev

    doc = _read_json(_PAPER_FORWARD)
    if not isinstance(doc, dict):
        return {"evidence": "UNMEASURED",
                "why": (f"{_PAPER_FORWARD} missing or unreadable -- no runner has published "
                        f"accrual for {name}. A spawned clock nothing runs can never resolve."),
                "source": _PAPER_FORWARD}
    sleeves = doc.get("sleeves")
    row = sleeves.get(name) if isinstance(sleeves, dict) else None
    if not isinstance(row, dict):
        return {"evidence": "UNMEASURED",
                "why": f"{_PAPER_FORWARD} carries no row for {name}", "source": _PAPER_FORWARD}
    ts = _parse_ts(row.get("observed_utc") or doc.get("updated"))
    age_h = round((now - ts).total_seconds() / 3600.0, 1) if ts else None
    state = str(row.get("evidence", "UNMEASURED"))
    if state == "ACCRUING" and age_h is not None and age_h > STALE_AFTER_H:
        state = "STALLED"                     # the runner stopped; a fossil is not evidence
    return {"evidence": state, "days": row.get("rows_added"), "age_h": age_h,
            "source": _PAPER_FORWARD,
            "progress_to_resolution": row.get("progress_to_resolution"),
            "why": row.get("why", "")}



#: Where stage_a_screen announces every clock it starts. A screen-spawned clock is NOT a paper
#: sleeve and does not publish through the paper-sleeve runner; this is the map from its name to
#: the JSONL its rows are actually written to.
_CLOCK_REGISTRY = "data/axis_clock_registry.json"


def _registered_clock_evidence(name: str, now: datetime) -> dict[str, Any] | None:
    """Accrual for a clock announced by `stage_a_screen`, or None when this name is not one.

    RETURNS None RATHER THAN A ZERO when the name is unregistered: None means "not my kind of
    clock, ask the next reader", and a zero would mean "measured, and it has nothing" -- which is
    exactly the substitution that retired a clock holding seven observations.
    """
    doc = _read_json(_CLOCK_REGISTRY)
    axes = doc.get("axes") if isinstance(doc, dict) else None
    rec = axes.get(name) if isinstance(axes, dict) else None
    if not isinstance(rec, dict) or not rec.get("clock"):
        return None
    rel = str(rec["clock"])
    p = _ROOT / rel
    if not p.exists():
        return {"evidence": "UNMEASURED", "source": rel,
                "why": (f"{name} is registered against {rel}, which does not exist on this host. "
                        "Registered-but-absent is UNKNOWN, never a measured zero -- a clock whose "
                        "rows cannot be found has not been shown to have none")}
    try:
        lines = [ln for ln in p.read_text("utf-8", errors="ignore").splitlines() if ln.strip()]
    except OSError:
        return {"evidence": "UNMEASURED", "source": rel, "why": f"{rel} unreadable"}
    age_h = None
    with contextlib.suppress(OSError):
        age_h = round((now.timestamp() - p.stat().st_mtime) / 3600.0, 1)
    state = ("NO-EVIDENCE" if not lines else
             "STALLED" if (age_h is not None and age_h > STALE_AFTER_H) else "ACCRUING")
    return {"evidence": state, "days": len(lines), "age_h": age_h, "source": rel,
            "why": f"{len(lines)} clock row(s) in {rel} (screen-spawned clock, not a paper sleeve)"}

def _read_json(rel: str) -> Any | None:
    """Return parsed JSON, or None when the source cannot be trusted (missing/unreadable)."""
    doc, _ = _read_source(rel)
    return doc


def _read_source(rel: str) -> tuple[Any | None, str]:
    """(document, state) where state is OK / ABSENT / UNREADABLE.

    THE DISTINCTION THIS DRAWS, and it was collapsed for the module's whole life. A file that does
    NOT EXIST has never been written, so the clocks it would record were never born -- that is a
    MEASURED ZERO. A file that exists and does not parse could hold anything -- that is genuinely
    UNKNOWN. Treating both as unknown looks conservative and is not: it is what froze slot
    admission permanently. On 2026-08-05 all eight "unknown" sources were simply ABSENT (no clock
    had ever been started on this box), `complete` was therefore False forever, and
    `paper_sleeves.free_slots` collapses to zero on an incomplete cohort -- so ten idle slots could
    never be filled, no forward clock could ever start, and nothing could ever survive. An unknown
    that can be RESOLVED must be resolved, not surrendered to (L1.54).
    """
    path = _ROOT / rel
    if not path.exists():
        return None, "ABSENT"
    try:
        return json.loads(path.read_text("utf-8")), "OK"
    except (OSError, json.JSONDecodeError):
        return None, "UNREADABLE"


def derive_slots() -> dict[str, Any]:
    """Enumerate every concurrently-accruing forward clock from the artifacts on disk.

    Returns a payload carrying the slots, the cohort size `m_concurrent`, and `complete` -- False
    whenever any source was unreadable, meaning m is a LOWER BOUND and the true bar may be higher.
    """
    now = datetime.now(tz=UTC)
    slots: list[dict[str, Any]] = []
    unknown: list[str] = []
    absent: list[str] = []
    #: Per-source UPPER BOUND on clocks an unreadable source could be hiding. A single named
    #: clock's state file can hide at most one; a CONTAINER (axis roster, sleeve roster) can hide
    #: any number, so it saturates the cap. Summed into `m_upper` below.
    bounds: dict[str, int] = {}

    axis_doc, axis_state = _read_source(_AXIS_STATE)
    if axis_state == "ABSENT":
        absent.append(_AXIS_STATE)
    elif axis_doc is None:
        unknown.append(_AXIS_STATE)
        bounds[_AXIS_STATE] = MAX_FORWARD_SLOTS      # container: unbounded, so saturate
    else:
        rows = axis_doc.get("axes", axis_doc) if isinstance(axis_doc, dict) else axis_doc
        for row in rows if isinstance(rows, list) else []:
            if not isinstance(row, dict):
                continue
            if str(row.get("verdict", "")).upper() == "RETIRED":
                continue
            slots.append({"name": str(row.get("axis", "?")), "kind": "axis",
                          "source": _AXIS_STATE, "state": str(row.get("verdict", "ACCRUING")),
                          # `started` is the clock's DECLARED birth date, carried as a first-class
                          # field so libs.research.promotion_history never has to parse it back out
                          # of the `state` prose. None where the artifact does not declare one --
                          # an absent start is UNKNOWN, never today (L1.30 phantom-birth rule).
                          "started": row.get("shadow_start") or row.get("start"),
                          # `decision_at_obs` is the clock's PRE-REGISTERED decision point in
                          # OBSERVATIONS (R0430), carried first-class for the same reason
                          # `started` is: a consumer must never have to re-derive it, because
                          # re-deriving it from today's data is precisely what makes it stop
                          # being pre-registered. None where the artifact declares none -- an
                          # undeclared decision point is UNKNOWN, and a horizon nobody wrote
                          # down can never be reported as reached.
                          "decision_at_obs": row.get("decision_at_obs"),
                          # DEFLATOR INPUTS, carried through so `information_rate` can compute a
                          # real rate rather than charging every clock the unmeasured penalty.
                          # PASSED THROUGH VERBATIM, including absence: a missing field must stay
                          # missing here, because the value each of them defaults to downstream is
                          # exactly the flattering one, and inventing it in the registry would put
                          # the substitution one layer further from where anyone would look.
                          "distinct_regimes": row.get("distinct_regimes"),
                          "autocorrelation": row.get("autocorrelation"),
                          **_evidence(str(row.get("axis", "?")), now,
                                      days=row.get("forward_days", row.get("n", 0)),
                                      updated=row.get("updated")
                                      or (axis_doc.get("updated")
                                          if isinstance(axis_doc, dict) else None))})

    for name, rel in _STANDING_STATES.items():
        doc, state = _read_source(rel)
        if state == "ABSENT":
            absent.append(rel)                       # this clock was never born on this box
            continue
        if doc is None:
            unknown.append(rel)
            bounds[rel] = 1                          # one named clock: at most one hidden
            continue
        if isinstance(doc, dict) and doc.get("shadow_start"):
            slots.append({"name": name, "kind": "standing", "source": rel,
                          # `state` stays the birth date: promotion_history and the dashboard
                          # parse it. The OUTCOME travels in its own field so neither has to
                          # change and neither can confuse a start with a verdict.
                          "state": f"since {doc['shadow_start']}",
                          "verdict": _sleeve_verdict(name),
                          "started": str(doc["shadow_start"]), **_evidence(name, now)})

    roster, roster_state = _read_source(_SLEEVE_ROSTER)
    if roster_state == "ABSENT":
        # The spawner's own convention, and the file it writes: `_spawn_one` reads an absent
        # roster as `[]`. A registry that called the same absence unknown disagreed with the organ
        # that owns the file.
        absent.append(_SLEEVE_ROSTER)
        names: list[str] = list(_DERIVATIVE_BUILTIN)
    elif roster is None:
        unknown.append(_SLEEVE_ROSTER)
        bounds[_SLEEVE_ROSTER] = MAX_FORWARD_SLOTS   # container: unbounded, so saturate
        names = list(_DERIVATIVE_BUILTIN)
    else:
        extras = [str(x) for x in roster if str(x).strip()] if isinstance(roster, list) else []
        names = sorted({*_DERIVATIVE_BUILTIN, *extras})
    for name in names:
        # A SPAWNED SLEEVE DOES DECLARE ITS BIRTH, and this loop could not see it. The spawner
        # writes data/<name>_shadow_state.json carrying `shadow_start` -- the same birth
        # certificate every standing clock uses -- but `started` was read only from the fixed
        # _STANDING_STATES map, so every auto-spawned clock reported started=None forever. A clock
        # with no birth date can never have its forward days counted, so it could never accrue and
        # never resolve: born, registered, paying multiplicity, and structurally unable to finish.
        #
        # Where no such file exists the answer stays None, and deliberately: the built-in
        # derivative sleeves publish only `days_accumulated`, and a start back-derived from an
        # accrual counter is an UPPER bound on the birth date (a stalled clock accrues nothing
        # while ageing), so it would make births look EARLIER and over-count forward evidence.
        started: str | None = None
        state_label = "roster"
        spawned_doc, spawned_state = _read_source(f"data/{name}_shadow_state.json")
        if spawned_state == "OK" and isinstance(spawned_doc, dict) and spawned_doc.get(
                "shadow_start"):
            started = str(spawned_doc["shadow_start"])
            state_label = f"since {started}"
        slots.append({"name": name, "kind": "derivative", "source": _SLEEVE_ROSTER,
                      "state": state_label, "verdict": _sleeve_verdict(name),
                      "started": started, **_evidence(name, now)})

    # m is deliberately UNCHANGED by any of this: a stalled clock stays in the cohort until it is
    # RETIRED by an explicit ledgered decision, because dropping it would SHRINK m and loosen every
    # bar -- the phantom-edge direction this module exists to prevent. What the measurement buys is
    # that a dead clock can no longer report itself as accruing, and that the desk can see it is
    # paying multiplicity for slots returning nothing.
    # THE ONE SANCTIONED EXIT, AND IT IS THE ONLY ONE (2026-08-14). Everything above deliberately
    # keeps a dormant clock counted; this is the single place a name may leave, and it leaves only
    # because `docs/research/CLOCK_RETIREMENTS.json` -- TRACKED, attributed, evidenced, and
    # writable only by an explicit human evidence decision (a live sweep proposal, or a recorded
    # principal account/jurisdiction ineligibility) -- says so.
    #
    # Applied HERE, after all three sources are assembled, so retirement means the same thing for
    # an axis clock, a standing sleeve and a derivative. The pre-existing `verdict: RETIRED` string
    # in the axis artifact covered ONE source and lived in gitignored state, which made it a
    # decision no clone could see and no audit could cite.
    #
    # A MALFORMED OR ABSENT LEDGER RETIRES NOTHING: the cohort stays larger and every bar stays
    # tighter, so the failure mode is seats that will not free rather than bars that quietly
    # loosened.
    #
    # THE DISTINCTION THAT LICENSES LEAVING AT ALL (F0011/R0049, institutional_knowledge
    # 2026-07-30). "slot_registry drops retired clocks" and "attrition must never lower the bar"
    # (ADAPTIVE VALIDATION WINDOWS v2) are both right, about different things:
    # REFUTED-AS-INVALID-MEASUREMENT (artifact, lookahead, DEGENERATE instrument, SOURCE-GONE --
    # the trial was VOID) may leave, because an invalid trial is not a trial; FAILED-ON-ITS-MERITS
    # (legitimately accrued and lost) must keep counting, or the desk can kill losers to make
    # winners promotable -- garden-of-forking-paths with extra steps. The reconciliation is
    # mechanical, not procedural: `multiplicity_high_water` can NEVER fall, so even a
    # merits-failure retirement frees only the SEAT while every surviving bar keeps pricing the
    # trial it lost. Each ledger row must therefore carry its MECHANISM (verdict + why) so the
    # two classes stay distinguishable forever -- enforced by max_audit's
    # clock-retirement-mechanism check; a timestamp is a date, not a mechanism.
    _retired_names = retired_names(_ROOT)
    retired = [s for s in slots if str(s.get("name")) in _retired_names]
    slots = [s for s in slots if str(s.get("name")) not in _retired_names]

    dead = [s for s in slots if s.get("evidence") in ("STALLED", "NO-EVIDENCE")]
    unmeasured = [s for s in slots if s.get("evidence") == "UNMEASURED"]

    # ABSENT MEANS "NEVER BORN" ONLY ON THE HOST THAT OWNS THE ARTIFACTS (L1.28a / WS-005).
    #
    # A file never written records a clock never born -- true, and the reasoning the ABSENT/UNKNOWN
    # split is built on. It is false on every OTHER host: `data/` is gitignored, so a fresh clone
    # or a CI runner sees all six standing state files absent and derives `complete=True` with six
    # clocks "never born". Measured on a clone 2026-08-13: m=6, MEASURED, complete=True, with 7
    # absent sources, while the live desk cohort is ~12. The L1.6 fence then reports OK at bar 2.39
    # where the desk requires 2.64 -- absence resolving to the CLEAN verdict, on the single most
    # load-bearing integer, in the LOOSER direction.
    #
    # A host cannot distinguish "never written" from "not shipped here" file by file. It CAN
    # distinguish it in aggregate: a desk that has run has written at least one of these. Zero of
    # N present is not N independent measured zeros, it is a host with no desk state -- so the
    # whole set converts to UNKNOWN and each bounds itself, which floors m at the cap rather than
    # publishing a small number as measured.
    #
    # COSTS NOTHING WHERE IT MATTERS: on the VPS the files exist, no branch is taken, m is
    # unchanged. What it removes is a false green in CI, and a `MEASURED` provenance on a cohort
    # nobody measured.
    #
    # RESIDUAL, NAMED RATHER THAN PAPERED OVER: this catches the ALL-absent host, not the mixed
    # one. A clone where a single organ has run (writing, say, axis state and nothing else) still
    # reads the six missing sleeve births as measured zeros and publishes MEASURED at m=6 against
    # a live cohort near 12. Distinguishing that case needs a host-identity marker the registry
    # does not have, and GUESSING one would be worse than the gap -- a wrong "this is the owning
    # host" would restore exactly the false MEASURED this block removes. Tracked as a gap row;
    # the all-absent case is the one that is provable from here.
    # THE QUESTION IS NOW READ RATHER THAN INFERRED (GAP 111 closed). `desk_host` carries a marker
    # the running cycle stamps, so "absent" can mean a measured zero HERE and a fact about the
    # host everywhere else. The all-sources-unreadable test below is kept as a second, independent
    # trigger: it catches a box whose marker is missing AND whose state is gone, which is the
    # bare-clone case the marker was introduced to cover, so neither mechanism depends on the
    # other being correct.
    #
    # This closes the residual the first version named honestly and could not fix: a clone where
    # ONE organ has run used to read the six missing sleeve births as measured zeros and publish
    # MEASURED at m=6 against a live cohort near 12. That host now fails the marker check and
    # floors at the cap like any other non-owning box.
    _owns, _owns_why = is_owning_host(_ROOT)
    _all_sources = {_AXIS_STATE, *_STANDING_STATES.values(), _SLEEVE_ROSTER}
    if absent and (not _owns or not (_all_sources - set(absent) - set(unknown))):
        for rel in absent:
            bounds.setdefault(rel, MAX_FORWARD_SLOTS if rel in (_AXIS_STATE, _SLEEVE_ROSTER) else 1)
        unknown.extend(absent)
        absent = []

    # CAPACITY AND MULTIPLICITY ARE TWO NUMBERS, AND THIS FILE HAD ONLY EVER STORED ONE.
    #
    # `seats_upper` is a RESOURCE bound: how many concurrent forward clocks the box, the data and
    # the attention budget support. Retiring a dead clock frees one and that is pure gain.
    #
    # `m_upper` is how many times the desk LOOKED, and it is a HIGH-WATER MARK. A clock that ran
    # and failed consumed a trial; retiring it afterwards does not un-look, for the same reason a
    # p-value cannot be improved by forgetting an experiment. So it takes the max of the live
    # bound and every cohort size the retirement ledger has ever recorded, and it CANNOT FALL.
    #
    # This is what makes automatic seat reclamation safe. The standing objection to it -- that
    # dropping a row loosens every survivor's bar in the phantom-edge direction -- was an
    # objection to the BAR MOVING, not to the seat being freed, and the two only ever moved
    # together because they shared a variable.
    seats_upper = len(slots) + sum(bounds.values())
    m_upper = max(seats_upper, multiplicity_high_water(_ROOT))
    return {
        "updated": now.isoformat(),
        "m_concurrent": len(slots),
        "seats_used": len(slots),
        "seats_upper": seats_upper,
        "seats_free": max(0, MAX_FORWARD_SLOTS - seats_upper),
        "multiplicity_high_water": m_upper,
        # THE NUMBER EVERY BAR MUST BE COMPUTED FROM. `m_concurrent` counts only what was READ, so
        # it is a LOWER bound whenever a source is unreadable -- and understating m LOOSENS every
        # Holm bar, the phantom-edge direction this module exists to prevent. `complete=False` was
        # published next to the loose number rather than instead of it, and every caller of
        # concurrent_m() kept using the loose one. m_upper adds each unreadable source's own
        # maximum, so the bar is computed from the worst case and can only ever be too TIGHT.
        "m_upper": m_upper,
        "m_bounds": bounds,
        "complete": not unknown,
        "cap": MAX_FORWARD_SLOTS,
        # CAPACITY QUESTIONS ANSWER FROM SEATS, never from multiplicity. Asking "may another clock
        # start?" against a high-water mark would keep the desk permanently over cap on the
        # strength of clocks that have already been retired -- idleness bought with a number that
        # exists to protect the bar, which protects nothing and costs every candidate its clock.
        "over_cap": seats_upper > MAX_FORWARD_SLOTS,
        "idle_slots": max(0, MAX_FORWARD_SLOTS - seats_upper),
        "unknown_sources": unknown,
        # Published so a reader can tell a measured zero from a host without state, which is
        # the whole distinction the ABSENT/UNKNOWN split turns on (L1.28a).
        "owning_host": _owns, "owning_host_why": _owns_why,
        # ABSENT IS A MEASUREMENT, NOT AN UNKNOWN: the file was never written, so the clock it
        # would record was never born. Kept in its own list so the two can never be re-merged.
        "absent_sources": absent,
        "accruing": len(slots) - len(dead) - len(unmeasured),
        "not_accruing": [{"name": s["name"], "evidence": s.get("evidence"),
                          "days": s.get("days"), "age_h": s.get("age_h")} for s in dead],
        "unmeasured_slots": [s["name"] for s in unmeasured],
        # PUBLISHED, NEVER MERELY SUBTRACTED. A seat that vanished and a seat that was retired look
        # identical in a count, and only one of them is a decision somebody made and signed.
        "retired_slots": [s["name"] for s in retired],
        "evidence_stale_after_h": STALE_AFTER_H,
        "slots": slots,
        "note": ("Holm cohort for every Stage-B forward clock. UNREADABLE sources are bounded "
                 "into `m_upper` (never counted as zero: understating m loosens every bar); "
                 "ABSENT sources are a measured zero, because a file never written records a "
                 "clock never born, and calling that unknown is what froze slot admission. "
                 "Dormant clocks stay counted until RETIRED by an explicit ledgered decision -- "
                 "`not_accruing` names the slots paying multiplicity while returning no evidence, "
                 "which is a cost to fix upstream, never by shrinking m. `retired_slots` names "
                 "the ones that HAVE left, each by an attributed row in "
                 "docs/research/CLOCK_RETIREMENTS.json taken against a live sweep proposal or an "
                 "explicit principal account/jurisdiction ineligibility; that "
                 "tracked ledger is the only mechanism by which m may fall."),
    }


@dataclass(frozen=True)
class CohortM:
    """The cohort size a Holm bar must be computed against, with WHY attached.

    `m` is what you pass to holm_bar. `provenance` says how it was arrived at, because a bar
    computed from a degraded cohort is still a bar and the caller has to be able to say so in its
    own artifact.
    """
    m: int
    provenance: str          # MEASURED | INCOMPLETE-FLOORED | REFUSED-FLOORED
    detail: str

    @property
    def measured(self) -> bool:
        return self.provenance == "MEASURED"


def cohort_m_for_bar() -> CohortM:
    """THE cohort size for every Stage-B Holm bar on this desk. Call this, never `len(anything)`.

    EVERY FAILURE PATH TIGHTENS. This is the whole point of the function and the reason it is not
    `len(derive_slots()["slots"])`. Understating m LOOSENS the bar, which is the phantom-edge
    direction: at the measured 2026-08-05 values, judging the axis clocks at len(_AXES)=3 applies
    holm_bar(3)=2.13 where the true cohort of 11 requires 2.61 -- alpha 0.0167 per clock against a
    designed 0.0045, a family-wise error rate 3.67x the design, on the desk's only path from
    research to capital.

    So the degraded paths floor at the LAW CAP rather than falling back to a smaller number:
      * cohort incomplete (a source unreadable => m is a LOWER bound) -> max(m, m_upper, CAP)
      * registry unusable entirely                                    -> MAX_FORWARD_SLOTS
    Over-counting only costs us a real edge's promotion by a few days of clock; under-counting
    admits noise as edge and sizes capital on it. Those are not symmetric, and this function
    resolves every ambiguity toward the one that cannot manufacture an edge.
    """
    try:
        snap = derive_slots()
        derived = int(snap["m_concurrent"])
        complete = bool(snap["complete"])
        unknown = list(snap.get("unknown_sources") or [])
        upper = snap.get("m_upper")
    except (OSError, ValueError, KeyError, TypeError) as exc:
        return CohortM(
            MAX_FORWARD_SLOTS, "REFUSED-FLOORED",
            f"slot registry unusable ({type(exc).__name__}: {exc}) -- floored at the law cap "
            f"{MAX_FORWARD_SLOTS} because an unknown cohort must never produce a LOOSER bar than "
            "a known one")
    if not complete:
        # m_upper bounds each unreadable source at its own maximum, so where it is published it is
        # the TIGHTER honest floor; the law cap remains the minimum either way. Both directions
        # can only ever RAISE m above the loose lower bound, never lower it.
        floor = max(derived, int(upper) if isinstance(upper, int) else 0, MAX_FORWARD_SLOTS)
        return CohortM(
            floor, "INCOMPLETE-FLOORED",
            f"{derived} clocks counted but {len(unknown)} source(s) unreadable "
            f"({', '.join(unknown[:3])}) -- m is a LOWER bound, so it is floored at "
            f"{floor}; the true bar can only be higher, never lower")
    return CohortM(max(derived, 1), "MEASURED",
                   f"{derived} concurrently-accruing forward clocks, every source readable")


def concurrent_m() -> int:
    """The Holm cohort size. Never returns 0 -- a cohort of nothing would zero out multiplicity.

    Delegates to `cohort_m_for_bar()` so that the fail-safe flooring applies to EVERY caller by
    default. This function had zero callers for the whole period the axis clocks ran at a 3.67x
    inflated error rate; a bare `len()` here would have been a footgun waiting for its first user.
    """
    return cohort_m_for_bar().m


def write_snapshot() -> dict[str, Any]:
    """Persist the derived cohort to data/forward_slots.json and return it."""
    payload = derive_slots()
    (_ROOT / _OUT).write_text(json.dumps(payload, indent=1) + "\n", "utf-8")
    return payload


if __name__ == "__main__":  # pragma: no cover -- operator entry point
    snap = write_snapshot()
    print(f"m_concurrent={snap['m_concurrent']} complete={snap['complete']} "
          f"idle={snap['idle_slots']} over_cap={snap['over_cap']}")
    for s in snap["slots"]:
        print(f"  {s['kind']:11s} {s['name']:28s} {s['source']}")
    if snap["unknown_sources"]:
        print("  UNKNOWN:", ", ".join(snap["unknown_sources"]))

```

### libs\research_os\adapters\owned_data.py
```python
"""Adapters for the three mechanisms this desk could already measure and was not.

WHY THESE THREE FIRST (measured 2026-08-29)

Of the five mechanisms `family_generic` could not honestly measure, three were blocked by WIRING
rather than by missing data. The observables were sitting on disk, unused, while a price proxy
stood in for them:

    positioning_extreme   COT parquets present     -> used distance from a 60-bar mean
    carry_change          carry_state.json, 388KB  -> used a 24-bar price return
    cross_market_move     251 instruments with bars -> used ONE instrument's own return

That is the highest-return work available on this desk: no data to acquire, no model to call, no
threshold to argue about. Each one turns a mechanism the search had to skip into one it can
measure directly.

POINT-IN-TIME IS THE HARD PART, and it is where a careless version of this file would
manufacture a spectacular backtest. COT is published on a lag -- a report dated Tuesday is not
public until the following Friday -- so a naive merge on report_date leaks three days of future
positioning into every bar. `CotPositioningAdapter` lags explicitly and says by how much.

WHAT AN ADAPTER REFUSES TO DO. If its file is missing, it reports UNAVAILABLE with the path it
wanted. It never falls back to a price feature: the fallback is the defect this whole package
exists to remove.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from libs.research_os.adapters.base import MeasurementResult, ResearchAdapter

ROOT = Path(__file__).resolve().parents[3]
DESK = ROOT / "desks" / "mt5"

#: COT is released Friday for the preceding Tuesday. Anything less than this leaks.
#: Deliberately generous -- an extra day of lag costs a little power; a day too few costs the
#: entire result and looks like a discovery while it does it.
_COT_PUBLICATION_LAG_DAYS = 4

#: Currency code -> the COT file that carries its positioning.
_COT_FILES = {
    "AUD": "aud", "CAD": "cad", "CHF": "chf", "EUR": "eur", "GBP": "gbp",
    "JPY": "jpy", "NZD": "nzd", "USD": "usd", "MXN": "mxn", "BRL": "brl",
    "XAU": "gold", "XAG": "silver",
}


def _as_utc_index(idx: pd.Index) -> pd.DatetimeIndex:
    """A tz-AWARE UTC index. Naive stamps are assumed UTC, which is what this desk stores."""
    di = pd.DatetimeIndex(idx)
    return di.tz_localize("UTC") if di.tz is None else di.tz_convert("UTC")


def _as_utc(s: pd.Series) -> pd.Series:
    out = s.copy()
    out.index = _as_utc_index(out.index)
    return out


def _currencies(symbol: str) -> tuple[str, str]:
    s = symbol.upper()
    if len(s) >= 6:
        return s[:3], s[3:6]
    return s, ""


class CotPositioningAdapter(ResearchAdapter):
    """Real COT/TFF net positioning, lagged to publication. Replaces a price-extension proxy."""

    mechanism = "positioning_extreme"
    requires = ("desks/mt5/data/cot/<ccy>.parquet",)

    def compatibility(self, spec: dict[str, Any]) -> float:
        sym = str(spec.get("symbol") or "")
        base, quote = _currencies(sym)
        have = [c for c in (base, quote) if _COT_FILES.get(c)
                and (DESK / "data" / "cot" / f"{_COT_FILES[c]}.parquet").exists()]
        if not have:
            return 0.0
        # Both legs measurable is a genuine differential; one leg is still a real positioning
        # measure for that currency, which is more than a price proxy ever was.
        return 1.0 if len(have) == 2 else 0.7

    def measure(self, spec: dict[str, Any], bars: pd.DataFrame) -> MeasurementResult:
        sym = str(spec.get("symbol") or "")
        base, quote = _currencies(sym)
        legs: dict[str, pd.Series] = {}
        missing: list[str] = []

        for ccy in (base, quote):
            key = _COT_FILES.get(ccy)
            if not key:
                continue
            path = DESK / "data" / "cot" / f"{key}.parquet"
            if not path.exists():
                missing.append(str(path.relative_to(ROOT)))
                continue
            try:
                df = pd.read_parquet(path)
            except Exception as exc:
                missing.append(f"{path.name} unreadable: {type(exc).__name__}")
                continue
            if "report_date" not in df.columns:
                missing.append(f"{path.name} has no report_date")
                continue
            d = df.copy()
            d["report_date"] = pd.to_datetime(d["report_date"], utc=True, errors="coerce")
            d = d.dropna(subset=["report_date"]).sort_values("report_date")
            longs = pd.to_numeric(d.get("noncomm_positions_long_all"), errors="coerce")
            shorts = pd.to_numeric(d.get("noncomm_positions_short_all"), errors="coerce")
            oi = pd.to_numeric(d.get("open_interest_all"), errors="coerce")
            # NET AS A FRACTION OF OPEN INTEREST, so the number means the same thing across
            # currencies and across years as contract sizes drift.
            net = (longs - shorts) / oi.replace(0, np.nan)
            # PUBLICATION LAG: the value becomes knowable only days after its report date.
            d["_available_at"] = d["report_date"] + pd.Timedelta(days=_COT_PUBLICATION_LAG_DAYS)
            leg = pd.Series(net.to_numpy(), index=d["_available_at"]).dropna()
            if not leg.empty:
                legs[ccy] = leg

        if not legs:
            return MeasurementResult(
                status="UNAVAILABLE", adapter="CotPositioningAdapter",
                notes=(f"no COT series for {sym}; wanted {missing or list(_COT_FILES)}. This is a "
                       f"data-acquisition task -- substituting price extension would test "
                       f"momentum and call it positioning."))

        idx = bars.index
        combined: pd.Series | None = None
        for ccy, leg in legs.items():
            leg = _as_utc(leg)
            uidx = _as_utc_index(idx)
            aligned = leg.reindex(leg.index.union(uidx)).sort_index().ffill().reindex(uidx)
            aligned.index = idx
            sign = 1.0 if ccy == base else -1.0
            combined = aligned * sign if combined is None else combined + aligned * sign

        assert combined is not None
        # The CLAIM is "positioning extreme", so the observable is the z-score of net positioning
        # against its own history, not the raw level.
        z = (combined - combined.rolling(52, min_periods=8).mean()) / \
            combined.rolling(52, min_periods=8).std()
        both = len(legs) == 2
        return MeasurementResult(
            status="DIRECT" if both else "VALIDATED_PROXY",
            adapter="CotPositioningAdapter",
            feature_ids=[f"cot_net_z:{c}" for c in legs],
            confidence=1.0 if both else 0.7,
            pit_safe=True,
            series=z,
            notes=(f"net non-commercial positioning as a share of open interest, z-scored over 52 "
                   f"weeks, for {'/'.join(legs)}; lagged {_COT_PUBLICATION_LAG_DAYS} days to "
                   f"publication so no bar sees a report before it was public"
                   + ("" if both else ". Only one leg available, so this is the currency's "
                                      "positioning rather than the pair's differential.")))

    def pit_check(self, series: pd.Series, bars: pd.DataFrame) -> tuple[bool, str]:
        return True, (f"COT values are stamped at report_date + {_COT_PUBLICATION_LAG_DAYS}d and "
                      f"forward-filled, so a bar can only see a report already published")


class CarryAdapter(ResearchAdapter):
    """The swap actually paid, from recorded contract terms. Replaces a 24-bar price return."""

    mechanism = "carry_change"
    requires = ("desks/mt5/data/carry_state.json",)

    def _state(self) -> dict[str, Any]:
        p = DESK / "data" / "carry_state.json"
        try:
            loaded = json.loads(p.read_text("utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}
        return loaded if isinstance(loaded, dict) else {}

    def compatibility(self, spec: dict[str, Any]) -> float:
        st = self._state()
        syms = (st.get("symbols") or {})
        sym = str(spec.get("symbol") or "")
        if not syms:
            return 0.0
        row = syms.get(sym) or {}
        # Both sides recorded means a real differential; one side is still the financing actually
        # paid on that side.
        have = sum(1 for side in ("long", "short") if isinstance(row.get(side), dict))
        return {0: 0.0, 1: 0.7, 2: 1.0}[have]

    def measure(self, spec: dict[str, Any], bars: pd.DataFrame) -> MeasurementResult:
        sym = str(spec.get("symbol") or "")
        st = self._state()
        row = (st.get("symbols") or {}).get(sym)
        if not isinstance(row, dict):
            return MeasurementResult(
                status="UNAVAILABLE", adapter="CarryAdapter",
                notes=(f"{sym} has no recorded contract terms in carry_state.json. Using a price "
                       f"return instead would measure momentum and call it carry."))

        def _side(name: str) -> float | None:
            side = row.get(name)
            if not isinstance(side, dict):
                return None
            # FIELD NAMES READ FROM THE FILE, not guessed. A first version tried
            # money_per_lot_night/carry_per_lot_night/swap and found none of them, reporting
            # UNAVAILABLE on a symbol whose financing was recorded all along -- a guessed schema
            # produces a data gap that does not exist and sends the desk hunting for data it has.
            # `swap_money_per_lot_night` is the CREDIT (positive = broker pays the desk);
            # `swap_cost_per_lot_night` is the same figure as a cost.
            for key in ("swap_money_per_lot_night", "money_per_lot_night",
                        "carry_per_lot_night", "swap"):
                v = side.get(key)
                if isinstance(v, (int, float)):
                    return float(v)
            return None

        long_c, short_c = _side("long"), _side("short")
        if long_c is None and short_c is None:
            return MeasurementResult(
                status="UNAVAILABLE", adapter="CarryAdapter",
                notes=(f"{sym} terms recorded but no financing figure among "
                       f"money_per_lot_night/carry_per_lot_night/swap"))

        # THE CARRY DIFFERENTIAL is what the mechanism is about: what you are paid to be long
        # minus what you are paid to be short.
        # Narrow explicitly rather than with a ternary mypy cannot follow: the differential is
        # the mechanism when both sides are known, and one side alone is still the financing
        # actually paid on that side.
        if long_c is not None and short_c is not None:
            both = True
            level = (long_c - short_c) / 2.0
        else:
            both = False
            level = float(long_c) if long_c is not None else -float(short_c or 0.0)
        # carry_state is a SNAPSHOT, not a time series: the honest observable is a constant level
        # per symbol, and that is exactly what it is -- a cross-sectional carry, not a change.
        series = pd.Series(level, index=bars.index, dtype=float)
        return MeasurementResult(
            status="VALIDATED_PROXY",
            adapter="CarryAdapter",
            feature_ids=[f"carry_diff:{sym}"],
            confidence=1.0 if both else 0.7,
            pit_safe=True,
            series=series,
            notes=(f"financing actually paid per lot per night from recorded terms "
                   f"({'both sides' if both else 'one side'}). VALIDATED_PROXY rather than "
                   f"DIRECT because carry_state is a SNAPSHOT: it gives the current level, not "
                   f"its history, so a cell using it measures a cross-sectional carry rather "
                   f"than a carry CHANGE. Recording a time series would make this DIRECT."))


class CrossAssetAdapter(ResearchAdapter):
    """A genuine second instrument's lead. Replaces one instrument's own return."""

    mechanism = "cross_market_move"
    requires = ("desks/mt5/data/universe/<peer>_H1.parquet",)

    def compatibility(self, spec: dict[str, Any]) -> float:
        peer = spec.get("peer_symbol") or spec.get("peer")
        if peer:
            return 1.0 if (DESK / "data" / "universe" / f"{peer}_H1.parquet").exists() else 0.0
        # No peer named: the adapter can still pick a defensible one from the same asset class,
        # but a chosen peer is weaker evidence than a named one.
        return 0.6

    def _default_peer(self, symbol: str) -> str | None:
        """A defensible lead instrument when the hypothesis did not name one.

        Chosen by SHARED CURRENCY or asset class, never by correlation -- picking the
        highest-correlated peer from the same data the test then runs on is selection on the
        outcome, and would manufacture a lead-lag that is not there.
        """
        base, quote = _currencies(symbol)
        uni = DESK / "data" / "universe"
        for cand in (f"{base}USD", f"USD{quote}", "XAUUSD", "US500"):
            if cand != symbol and (uni / f"{cand}_H1.parquet").exists():
                return cand
        return None

    def measure(self, spec: dict[str, Any], bars: pd.DataFrame) -> MeasurementResult:
        sym = str(spec.get("symbol") or "")
        peer = spec.get("peer_symbol") or spec.get("peer") or self._default_peer(sym)
        if not peer:
            return MeasurementResult(
                status="UNAVAILABLE", adapter="CrossAssetAdapter",
                notes=(f"no peer instrument for {sym}. A single-instrument feature contains no "
                       f"cross-market information at all -- this is not a weaker measure of the "
                       f"mechanism, it is a measure of something else."))
        path = DESK / "data" / "universe" / f"{peer}_H1.parquet"
        if not path.exists():
            return MeasurementResult(
                status="UNAVAILABLE", adapter="CrossAssetAdapter",
                notes=f"peer {peer} has no bars at {path.relative_to(ROOT)}")
        try:
            pdf = pd.read_parquet(path).rename(columns=str.lower)
        except Exception as exc:
            return MeasurementResult(
                status="UNAVAILABLE", adapter="CrossAssetAdapter",
                notes=f"peer {peer} unreadable: {type(exc).__name__}")

        lag = int(spec.get("lead_bars", 1))
        # THE PEER'S PAST MOVE, shifted so the bar cannot see the peer's current bar. `lag>=1` is
        # the non-anticipation guarantee, and it is asserted rather than assumed.
        if lag < 1:
            return MeasurementResult(
                status="UNAVAILABLE", adapter="CrossAssetAdapter",
                notes=(f"lead_bars={lag} would let this bar see the peer's contemporaneous move; "
                       f"a lead-lag claim needs a strictly positive lag"))
        peer_ret = pdf["close"].pct_change().shift(lag)
        # NORMALISE BOTH INDICES TO UTC BEFORE ANY UNION. Some universe parquets are tz-aware and
        # some are tz-naive; unioning them raises "Cannot compare tz-naive and tz-aware", and the
        # tempting fix -- dropping the tz -- would silently shift a peer by the broker offset and
        # invent a lead-lag that is purely a timezone error.
        peer_ret = _as_utc(peer_ret)
        target_index = _as_utc_index(bars.index)
        aligned = peer_ret.reindex(peer_ret.index.union(target_index)).sort_index() \
            .ffill().reindex(target_index)
        aligned.index = bars.index
        named = bool(spec.get("peer_symbol") or spec.get("peer"))
        return MeasurementResult(
            status="DIRECT" if named else "VALIDATED_PROXY",
            adapter="CrossAssetAdapter",
            feature_ids=[f"peer_ret:{peer}:lag{lag}"],
            confidence=1.0 if named else 0.6,
            pit_safe=True,
            series=aligned,
            notes=(f"{peer}'s return lagged {lag} bar(s), aligned to {sym}'s index"
                   + ("" if named else f". The hypothesis named no peer, so {peer} was chosen by "
                                       f"shared currency/asset class -- NEVER by correlation, "
                                       f"which would select on the outcome being tested.")))

```

### scripts\build_enforcement_matrix.py
```python
"""CONSTITUTION -> ENFORCEMENT MATRIX -- makes every principle auditable (EXECUTION_QUEUE rank 2).

THE GAP THIS CLOSES. The desk carries 42 constitutional principles (L1.x/L2.x) and 57 mechanical
fences in `scripts/max_audit.py`, and NOTHING mapped one to the other. So two failure directions
were both invisible:

  UNENFORCED PRINCIPLE  -- a law with no fence is prose. It cannot fire, cannot fail a cycle, and
                           degrades silently into decoration. Every defect found on 2026-07-30 was
                           of exactly this shape: a principle everyone agreed with, enforced by
                           nobody (capacity parity was written in L1.18 while a $100k floor ran in
                           the gauntlet; L2.9 activate-the-unused was written while 171 capabilities
                           sat dormant).
  UNJUSTIFIED FENCE     -- a check with no governing principle is complexity nobody voted for. It
                           consumes cycle time and its failures have no authority behind them.

This emits `data/enforcement_matrix.json`:
    principle -> requirement -> fences -> code_paths -> scheduler -> tests -> evidence -> status

STATUS is deliberately blunt: ENFORCED (>=1 fence or a named runtime mechanism) / UNENFORCED /
HUMAN-ONLY (a law only a person can satisfy -- key custody, licence rulings; a fence would be
theatre) / STANDING (a review cadence rather than a check).

IT FAILS THE BUILD on an unenforced principle, because a matrix that merely REPORTS gaps is the
same category of decoration it exists to detect.

Pure stdlib. Run from repo root.
    python scripts/build_enforcement_matrix.py [--json] [--report-only]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parent.parent
_CONST = _ROOT / "docs/CONSTITUTION.md"
_MASTER = _ROOT / "docs/MASTER_QUANT_CONSTITUTION.md"
_AUDIT = _ROOT / "scripts/max_audit.py"
_MANIFEST = _ROOT / "ops/crontab.manifest"
_OUT = _ROOT / "data/enforcement_matrix.json"

# principle -> the fences / runtime mechanisms that enforce it. Hand-mapped ONCE because the link
# is semantic (a fence name does not contain its principle id), then kept honest by this script:
# any principle absent from this map with no keyword hit is reported UNENFORCED and fails the run.
_MAP: dict[str, list[str]] = {
    "L1.1": ["check_production", "check_gate_optimality"],
    "L1.2": ["check_directives"],
    "L1.3": ["check_data_utilization", "check_generation"],
    "L1.4": ["run_reality_gap.py", "check_forensics_fresh", "check_carry_funding_measured"],
    # R0276 adds the scheduled-event deferral. L1.5 is EXECUTION PHYSICS: a stop is priced as the
    # loss it caps, and across a scheduled repricing it is not -- the gap jumps straight through
    # the level the whole size was derived from. build_event_calendar.py supplies the windows the
    # conviction sleeve defers entries across. It DEFERS, never kills, so it costs no statistical
    # power and is not a bar.
    # L1.5 is "no alpha is valid until it survives REALISTIC costs". Every fence here asks
    # whether a cost was charged; `check_cost_surface` asks whether the cost charged is the one
    # the cell's own fill bars recorded, which is the half nothing measured -- and it is
    # deliberately NOT a new law number. An hour-conditioned cost model is an INSTRUMENT for
    # L1.5, not a new duty, and minting a law for it would be the governance inflation LAWS
    # section 0 forbids.
    "L1.5": ["check_carry_funding_measured", "run_execution_intel.py",
             "scripts/build_event_calendar.py", "libs/execution/event_guard.py",
             # BY PATH, not by bare name. A bare `check_foo` ref is resolved as a max_audit
             # FUNCTION; this fence is a standalone script, so the bare form lands in
             # `broken_references` -- which is exactly what this generator's own output warns
             # about and exactly what it caught when this line was first written.
             "scripts/check_cost_surface.py", "desks/mt5/research/cost_surface.py",
             "tests/costs/test_cost_surface.py",
             # THE THIRD COST. Spread and commission were modelled; overnight financing was
             # charged at exactly 0.00 on every backtest, gate, certificate and forward clock
             # (`grep -i swap desks/mt5/mt5desk/engine.py` -> zero hits). Same reasoning as
             # cost_surface above: this is an INSTRUMENT for L1.5, not a new duty, so it takes
             # no law number of its own.
             "scripts/check_carry_state.py", "desks/mt5/research/carry_state.py",
             "tests/costs/test_carry_state.py"],
    "L1.6": ["libs/autodiscovery/validation.py", "check_welded_gates", "check_gate_optimality",
             "run_mutation.py"],
    "L1.7": ["check_rubberstamp_detector", "check_rubberstamp_enforcement", "deep_review.py"],
    # R0270 adds the EXTRACTION-side non-regression fence beside the acquisition-side ones. L1.8
    # ends "idle ingested data is a defect", and a campaign that truncates its history to the
    # shortest candidate leaves observations already on disk untested -- idle data manufactured by
    # the validator rather than by a lazy collector. check_campaign_retention.py floors the share
    # a campaign actually tests on, so the 82.9% min-length discard cannot come back in silence.
    # THE `scripts/` PREFIX IS THE HOUSE STYLE AND IS NO LONGER LOAD-BEARING (R0436, fixed).
    # `_exists` used to short-circuit any ref starting with `check_` into max_audit's FUNCTION
    # table, so the bare `check_campaign_retention.py` form resolved against a registry a
    # standalone script can never be in and reported BROKEN-REF without saying why. It now
    # discriminates on the `.py` suffix -- which a function name cannot carry -- so both forms
    # resolve. Path-first is kept everywhere here because it says WHERE the fence lives at a
    # glance; the suffixless `check_campaign_retention` form is still a function-table request
    # and still fails, now with a hint that names the suffix.
    "L1.8": ["check_no_mining_throttle", "check_mining_nonregression", "check_mine_flow",
             "scripts/check_campaign_retention.py", "libs/research/campaign_retention.py"],
    "L1.9": ["check_blind_trigger", "check_interrogation", "check_dig_depth"],
    "L1.10": ["check_mine_conversion", "check_mine_gate"],
    # R0316 adds HISTORICAL MONOPOLISATION, which L1.11 names outright and nothing implemented.
    # A point-in-time history is the cheapest proprietary state available: everyone can fetch M2SL,
    # almost nobody keeps what it SAID last month. FRED serves only the current vintage, so the
    # archive was overwritten AND truncated to a rolling window on every run -- each day destroying
    # a vintage that cannot be re-earned at any price, which is the one currency the desk cannot
    # buy back. Measured on the RFB Brazil panel: 42/42 months revised between vintages, worst
    # +40.9%, systematically upward. The store makes the daily overwrite lossless and turns "this
    # source is revised" from a disqualification into a dataset.
    "L1.11": ["check_vendor_replacement",
              "libs/research/vintage.py", "scripts/collect_fred_macro.py",
              "scripts/harvest_rfb_vintages.py",
              "tests/research/test_vintage.py"],
    # L1.11a ranks ground by REVERSE-ENGINEERING COST PER UNIT OF EFFORT, and delisted rosters are
    # the cheapest high-cost ground the desk had never asked for: R0239's own docstring routed the
    # backward half of survivorship to "a reconstruction from binance.vision archives, a separate
    # and much larger job", while three venues publish their dead instruments outright. One call
    # each returned 4455 names (bitmex 3077 vs 32 live, bybit 936 vs 808, coinbase 315 vs 517) --
    # accessibility was the barrier, and L1.11a says a barrier is a search dimension.
    # The same argument one format across (R0317): a legacy `.xls` is an ACCESSIBILITY barrier, and
    # government, regulator and central-bank publications are disproportionately served as one
    # PRECISELY because they are old institutional pipelines -- which is the same reason they stay
    # under-mined. The desk had recorded "this box cannot read .xls" (no xlrd/openpyxl/olefile,
    # installs frozen) as a fact about the world; it was a fact about a missing library. OLE2+BIFF8
    # are two documented byte-level layers and the stdlib ships `struct`, so the moat here is made
    # of tedium rather than secrecy -- maximum reverse-engineering cost per unit of effort.
    "L1.11a": ["ops/run_frontier_rotation.sh", "kimi_hunter.py",

               "scripts/read_xls.py", "libs/data/xls_reader.py",
               "tests/data/test_xls_reader.py"],
    "L1.12": ["check_orphan_code", "check_idle_capability", "libs/self_improvement/dormancy.py"],
    "L1.13": ["check_gap_register_health", "run_execution_intel.py"],
    "L1.14": ["check_directives", "research_erv.py"],
    "L1.15": ["check_self_application"],
    # L1.16: every edge understood -- mechanism, regime, failure modes -- or it is not durable.
    # screen_carry_basis_path is the attribution instrument for the ONLY deployed sleeve: it
    # measures whether the funding-rank entry selects into a widening or converging basis, which
    # is what decides whether the carry harvest is a cashflow or compensation for a basis loss.
    "L1.16": ["mechanism_board.py", "check_gate_optimality",
              ],
    "L1.17": ["negative_knowledge.py", "check_findings_ratchet", "docs/graveyard.md"],
    "L1.18": ["tests/validation/test_capacity_parity.py"],
    "L1.18a": ["tests/validation/test_capacity_parity.py",
               "libs/autodiscovery/validation.py:capacity_status",
               "scripts/run_promotion_queue.py", "libs/research/promotion_latency.py"],
    "L1.16a": ["negative_knowledge.py", "check_findings_ratchet"],
    # L1.19 is "hunt replacements BEFORE advantages die". probe_bybit_archive is that rule applied
    # to an advantage the desk has not yet TAKEN: a free 349-day first-party L2 archive that may
    # or may not be on rolling retention. Whether free history is expiring is a decay question,
    # and it was answered by INFERENCE in a sweep doc until the probe measured it (FIXED, boundary
    # 2025-08-21 unmoved 08-01 -> 08-05 while the span grew 345 -> 349 days).
    "L1.19": ["libs/research/dist_shift.py",

              ],
    "L1.20": ["check_post_gate0_activation", "check_production"],
    "L1.21": ["check_depth_parity", "check_coverage"],
    "L1.22": ["run_intelligence_cycle.py", "check_self_application", "check_self_sufficiency"],
    "L1.23": ["run_deadman_switch.py (Tier-3)", "libs/risk/gate.py", "check_production",
              "libs/risk/capital_events.py",
              # the moat is capital in information form: replicas drilled on every run, disk
              # fuse fails loud ~14 days before the 80% guard would start eating the moat
              "scripts/run_moat_backup.py"],
    "L1.24": ["run_intelligence_cycle.py", "check_idle_capability", "check_data_utilization"],
    "L1.25": ["check_welded_gates", "check_gate_optimality", "check_rejection_shadow"],
    "L1.26": ["research_erv.py", "check_directives"],
    "L1.27": ["check_verify_lag", "check_carryover_skipped"],
    "L2.1": ["check_prompt_layer", "ops/principal_doctrine.txt"],
    "L2.2": ["scripts/max_audit.py (all 57 fences)"],
    "L2.3": ["recommendations.py", "check_directives"],
    "L2.4": ["check_rubberstamp_detector", "check_rubberstamp_enforcement"],
    "L2.5": ["blind_spot.py", "check_self_sufficiency",
             # R0093: the principal's order channel feeds the origin gauge mechanically --
             # a doctrine edit IS a principal-found gap, logged the day it lands.
             "scripts/check_doctrine_diff.py"],
    "L2.6": ["run_trade_forensics.py", "check_forensics_fresh", "research_autopsy.py"],
    "L2.7": ["recommendations.py", "check_directives"],
    "L2.9": ["libs/self_improvement/dormancy.py", "run_intelligence_cycle.py",
             "check_idle_capability", "check_orphan_code"],
    "L2.10": ["run_reality_gap.py", "libs/research/dist_shift.py"],
    "L2.8a": ["scripts/check_constitution_core.py", "tests/governance/test_constitution_core.py",
              "data/constitution_core.lock"],
    # L1.21a is a bar on the ORGANS' reasoning, not on an artifact, so its enforcement is the
    # injection path: it is in principal_doctrine.txt, which check_prompt_layer proves reaches
    # every claude invocation and check_universal_doctrine proves no organ omits.
    "L1.21a": ["ops/principal_doctrine.txt", "check_prompt_layer", "check_universal_doctrine"],
    # L1.28 fences the CONSTITUTION's own language: every scope restraint must state its non-timid
    # reading, or an organ reading it defaults to doing less.
    "L1.28": ["scripts/check_timidity_language.py", "tests/governance/test_timidity_fence.py",
              "ops/principal_doctrine.txt"],
    # L1.28a is measured, not asserted: every ceiling reports utilisation or counts as zero.
    # R0318 adds the extractor case, where the absence-reads-as-health failure is at its sharpest:
    # `all([])` is True, so a hand-rolled parse that returned nothing but headers scores "0
    # violations" and the report reads as a clean bill. check_identities refuses that -- zero
    # usable rows is UNMEASURED, and the count of rows the law actually closed over is a
    # first-class output rather than a footnote.
    "L1.28a": ["scripts/check_utilisation.py", "check_idle_capability", "check_clock_saturation",
               "check_capacity_runway", "libs/research/conservation.py",
               "tests/research/test_conservation.py",
               "scripts/check_extractor_invariants.py",
               "libs/research/extractor_invariants.py"],
    # L1.28b: conversion hunts 100% daily -- FLATLINE (7d of silence on a non-empty queue) fails.
    # The fence DETECTS the debt; the actuator is what makes the law's own remedy -- (d) "flips
    # the next audit/brain window from finding to fixing" -- actually reach an organ (L1.36).
    # Both are listed because a law enforced only by a detector is half-enforced: the flag was
    # published for weeks with no consumer that changed any behaviour.
    # ship_restart is the REPAIR half of the desk's most expensive detection. max_audit's
    # check_stale_daemons has fired correctly on all three stale-code instances (2026-07-10,
    # 07-26, 08-05) and every one shipped only when a human happened to look, because the
    # restart needs a systemctl this box denies. Detection without an actuator IS the L1.28b
    # defect; this is the actuator.
    "L1.28b": ["scripts/check_conversion.py", "libs/ops/repair_mode.py", "ops/brain_env.sh",
               # run_stale_daemon_repair closes the remaining half-gap: ship_restart was an
               # actuator a HUMAN still had to invoke; this invokes it on the detector's own
               # verdict (cron 2x/day), with TIER_RUIN and the L1.38 sterile window as the two
               # hard skips. Detection -> repair now needs nobody awake.
               "scripts/ship_restart.py", "scripts/run_stale_daemon_repair.py",
               # R0330: check_conversion measures the QUEUE, this measures the CAPACITY that
               # drains it. A long queue is equally consistent with fast repair under heavy
               # arrival and slow repair under light arrival, so queue length alone cannot say
               # whether repair capacity is improving -- which is the comparison L1.28b is
               # written from. MTTR is censoring-aware; P(fix) excludes rejections on purpose.
               "scripts/check_repair_capacity.py", "libs/research/repair_capacity.py"],
    # L1.28c: every cadence hunts its own ceiling. The manifest fence requires a decided cadence
    # with evidence per line; brain_seat_throughput measures the resource they all compete for,
    # so "raise the cron" vs "buy a second seat" is settled by measurement.
    # run_cadence.py IS the cadence engine this law governs, and it was mapped by NOTHING -- so
    # the one organ that decides what fires and enforces the never-sleepier floors was also the
    # one organ outside the build standard and the L1.42 law boundary (R0425).
    "L1.28c": ["scripts/check_scheduler_manifest.py", "scripts/check_utilisation.py",
               "scripts/run_cadence.py"],
    # L1.29: the desk scores its own confidence or its confidence is fiction. The fence fails
    # on ungraded predictions; the shrinkage closes the loop back into sizing/promotion.
    "L1.29": ["scripts/check_calibration.py",
              "libs/self_improvement/forecast_calibration.py"],
    # L1.30: births vs deaths of validated edges -- the number that sets terminal wealth.
    "L1.30": ["scripts/check_replacement_rate.py"],
    # L1.31: two model families hunt the missing capability daily AND one builds it. The organ
    # is the fence: check_organs catches it going quiet, and its artifacts are dated evidence.
    "L1.31": ["scripts/run_capability_hunt.py", "ops/run_capability_hunt.sh", "check_organs"],
    # L1.32: the unknown-unknown organs measured as ONE family -- DARK when any has never
    # produced. L1.33: the GPT seat as standing partner on every one of them.
    "L1.32": ["scripts/check_exploration.py"],
    "L1.33": ["libs/research/second_family.py", "scripts/run_capability_hunt.py"],
    # L1.34: source-class universality reaches the seats through their PROMPTS, so the fence is
    # the prompt-layer wire that proves every brief carries it (same shape as L1.21a).
    "L1.34": ["ops/frontier_en_prompt.txt", "scripts/kimi_hunter.py", "check_prompt_layer",
              "tests/governance/test_source_universality.py"],
    # L1.35: the hunters are the never-finished organ. Fenced by the mandate's presence in every
    # brief, the family-level exploration fence, and the productivity ratchet that catches an
    # organ going quiet whatever reason it gives.
    "L1.35": ["tests/governance/test_source_universality.py", "scripts/check_exploration.py",
              "check_organs", "scripts/check_ratchets.py"],
    # L1.36: families enforced AS families -- complete, fenced per member, reaching every organ
    # via the doctrine, and guarded by a family-level check. A gate, not a report.
    "L1.36": ["scripts/check_law_families.py"],
    # L1.37: the gate itself -- four boundaries (organ spawn, pre-push, CI, hourly cron).
    # L1.37 carries the BOUNDARIES themselves, and check_birth_properties is the §36/L2.9
    # birth-property predicates moved onto them. They ran at 07:00 on cron and nowhere else, so
    # four defect keys (artifact-ungoverned 6x, orphan-scripts 4x, mine-conversion-unbacked 3x,
    # decision-ledger-undated 2x) recurred by construction: the object was authored, committed and
    # pushed, and the question "why does this file exist?" reached a session that had to
    # reconstruct the answer from cold hours later. Same predicates, one source of truth
    # (max_audit's tables are imported, never copied) -- only the boundary is new.
    "L1.37": ["scripts/run_law_gate.py", "deploy/git_hooks/pre-push", "ops/brain_env.sh",
              ".github/workflows/ci.yml", "scripts/check_birth_properties.py",
              "tests/ops/test_birth_properties.py"],
    # L1.38: the money path freezes to IMPROVEMENTS (never repairs) inside launch/first-fills/
    # rail-breach windows. Part of the survival family in spirit; fenced standalone.
    "L1.38": ["scripts/check_change_window.py"],
    # L1.39: zero idle findings -- every finding routes to its next stage immediately. The
    # principle unifies the two existing enforcers (cross-session + same-run); no new fence.
    "L1.39": ["scripts/check_conversion.py", "ops/principal_doctrine.txt",
              "scripts/check_law_families.py"],
    # L1.40: endless generation + defect lenses on the same 6x/day rotation, fixed in-run.
    "L1.40": ["scripts/run_capability_hunt.py", "scripts/check_exploration.py",
              "scripts/run_mutation.py"],
    # L1.41: nothing enters below the build standard -- prevention at the build boundary rather
    # than detection days later. The two Stage-A screens are its first governed non-fence organs.
    "L1.41": ["scripts/check_build_standard.py",
              ],
    # L1.42: the boundary for the 60 python entry points that sourced no shell gate.
    # scripts/run_cashcarry_executor.py was the proving entry point here until the MT5 mandate
    # (2026-08-18) retired the crypto-venue executor outright; a citation to a deleted file is a
    # BROKEN-REF, and the law is carried by the boundary itself plus the fence that audits it.
    "L1.42": ["libs/ops/lawful.py", "scripts/check_build_standard.py"],
    # L1.43: governance measured like everything else -- has each fence ever caught anything?
    # check_free_roster is the same logic pointed at a governance CAPABILITY rather than a fence:
    # the degraded free-seat fallback is only ever exercised while unfunded, so its health was
    # invisible by construction and 2026-08-01 found all four seats dead during the outage they
    # exist for. NEVER-RUN is the status L1.43 already names; this makes it observable on a
    # cadence, for free, because the seats cost nothing to ask.
    "L1.43": ["scripts/check_fence_yield.py", "scripts/check_enforcement_execution.py",
              "scripts/check_free_roster.py"],
    # L1.44: consumption-time freshness -- every decision-path read declares its max tolerated
    # age at the read site; the fence fails on STALE-CONSUMED (a live decision steered by a
    # frozen input) and on UNWIRED (a bootstrap contract deleted from the executor/alerts).
    # L1.44's own class, found four more times on 2026-08-05 and all in the same direction: a
    # state artifact whose AGE nobody checked, where staleness therefore read as health. The CI
    # marker (a wedged run_ci holds the lock, every later run exits 0 "skipping", the marker
    # freezes at ok=true and max_audit only ever raised on ok=false); the alert canary (a canary
    # that dies after a clean run leaves no silence flag, so the pager scored 10/10 for ever);
    # and source_health (a lane probed once successfully and never again read HEALTHY, so the
    # alternatives hunter never hunted it). Every one is a producer-side "did it run?" question
    # that no CONSUMER was asking -- which is precisely what this law was written for.
    "L1.44": ["scripts/check_freshness.py", "libs/ops/fresh.py", "check_ci_gate",
              "libs/research/source_health.py:stale_verdict"],
    # L1.45: execution excitation. Every other fence walks NODES and EDGES; this one looks for a
    # CYCLE (traded -> recorded -> measured -> cheap -> traded) and for exclusions with no path
    # back. It also owns the producer for the three ramp_gate step-up conditions that had none.
    # R0267 joins L1.45 rather than getting its own key: it is the FUNCTIONAL FORM the excitation
    # design has no vocabulary for, and its own-fill half refuses for exactly the reason L1.45
    # names -- an operating point the desk never visits, so go buy the observation.
    # fit_print_impact is the THIRD basis: the counterfactual half is the book walk, the own-fills
    # half is excitation, and neither reads the ~2,500 prints/symbol/hour of OTHER PEOPLE's
    # completed executions sitting on the same tape. It serves L1.45 by refusing above its
    # identified range -- the same "operating point never visited" discipline, applied to its own
    # output -- and it explicitly does NOT claim the causal slope excitation exists to identify.
    "L1.45": ["scripts/check_excitation.py", "scripts/run_cost_identification.py",
              "libs/execution/excitation.py", "scripts/fit_passive_impact.py",
              "libs/execution/passive_impact.py", "scripts/fit_print_impact.py",
              "libs/research/print_impact.py"],
    # L1.46: clock provenance. Every other data fence asks whether the COLLECTOR RAN -- gapless
    # collection was verified GOOD on the same corpus that is not monotonic in its own `t` field.
    # This one asks whether the TIMESTAMPS MEAN WHAT THE SCHEMA IMPLIES, which is the defect class
    # behind kimchi_premium, coinbase_premium_timing and R0060 alike.
    "L1.46": ["scripts/check_clock_provenance.py", "libs/research/clock_provenance.py"],
    # L1.47 IS MAPPED AGAIN, 2026-09-05, AND THE NOTE THAT UNMAPPED IT WAS FACTUALLY WRONG.
    #
    # That note (written hours earlier, same day) said funding settlement stamps are "a
    # crypto-exchange mechanic with no MT5 analogue that this map could point at today". The
    # universe registry disagrees: `swap_long` and `swap_short` are recorded for all 251 symbols,
    # and MT5 swap is a DISCRETE charge applied at the daily rollover, TRIPLED one night a week --
    # on Wednesday for 98 symbols and Friday for 150, per the broker's own `swap_rollover3days`.
    # "Discrete payments booked as continuous accruals are expectation errors" is L1.47 verbatim,
    # and it describes MT5 swap exactly as it described perp funding. The law never lost its
    # subject; the desk changed venue and nobody re-pointed the map.
    #
    # It is not a theoretical exposure either. `families_orthogonal.py` sizes a live carry family
    # off `swap_long - swap_short`, so an accrual error here is a mispriced position rather than a
    # doctrine footnote. The enforcer below is real, scheduled (06:40/06:50 daily in
    # ops/crontab.manifest) and refuses rather than reports: `check_carry_state.py` asks whether
    # any position is carried overnight whose financing the engine charges at zero, exits 2 on
    # CARRY-UNCHARGED / CARRY-FLIP / UNMEASURED / STALE, and explicitly refuses to call an empty
    # population OK. `carry_state.py` counts discrete rollover NIGHTS using the broker's per-symbol
    # triple weekday instead of smearing an annual rate, and reports UNMEASURED rather than
    # substituting 0.0 for a rate it cannot resolve.
    "L1.47": ["scripts/check_carry_state.py", "desks/mt5/research/carry_state.py"],
    #
    # L1.64 MARGIN TOPOLOGY is NOT mapped, and is classified SUBJECT-RETIRED below rather than
    # given a fence it does not have. Its law compares "spot wallet + separately-margined USDT-M
    # perp" -- two wallets on one crypto venue -- and its fence, its library
    # (libs/portfolio/margin_topology) and its consumer (run_capital_plan.py) are all deleted;
    # `tests/governance/test_margin_topology_fence.py` already skips for exactly that reason.
    # Unlike L1.47 there is no MT5 artifact this map could point at, because the desk has never
    # measured Fusion's own margin construction. Claiming enforcement this map cannot demonstrate
    # is the failure L2.0 was written to catch, so the classification says what is true and
    # carries the condition that ends it.
    # L1.47: funding capture. Funding is a DISCRETE payment booked as a CONTINUOUS accrual, and
    # the accrual is UNBIASED IN EXPECTATION -- which is why it survived every review while being
    # wrong on 41.5% of individual closes. The fence differences the two models, measures the
    # PHASE coordinate the desk has never used, and refuses to call an undifferenced estimate OK.
    # R0119 crowding: the desk's capacity assumption is that its carry names are too small for
    # funds to bother with, and that assumption had never been INSTRUMENTED. The incumbent organ
    # (run_carry_crowding.py) measures the top-20 AVERAGE, which contains our own names -- so a
    # competitor compressing exactly our book is diluted and partly subtracted as its own
    # benchmark, and a regime is indistinguishable from an adversary. This measures the RESIDUAL.
    # The collector ships with the fence because premiumIndex serves no history: an uncollected
    # hour of cross-section is permanently unbuyable (L1.28b(f)).
    "L1.19-r0119": ["libs/research/crowding.py",
                    ],
    # R0118 event-density promotion clock: L1.48 says evidence is the clock, and evidence_clock
    # reached exactly ONE promotion-path file while a `fwd_days >= 30` gate scaled DEPLOYABLE
    # CAPITAL on a bare positive Sharpe (measured 2026-08-05: validated=True at t=0.105). The
    # module counts EFFECTIVE observations -- raw event counts discounted for serial dependence,
    # clamped so the arithmetic can remove evidence and never invent it.
    "L1.48": ["libs/research/evidence_clock.py", "libs/research/event_density.py",
              "scripts/check_calendar_gates.py"],
    # L1.49 and L1.50 were BOTH already enforced and NEITHER was mapped -- not an oversight by
    # whoever wrote them, but a consequence of the parser defect fixed in `_principles()` this
    # commit: laws written as `## L1.49` headings were invisible to this file, so there was
    # nothing here to notice was missing. Their enforcement is the change-detector suite the
    # author shipped alongside each law, which pins the constitutional clauses phrase-by-phrase
    # so a silent deletion fails while a sharper rewrite passes. L1.50's utilisation and queue
    # clauses additionally have live measuring fences, named here because they genuinely measure
    # those clauses rather than merely relating to them.
    "L1.49": ["tests/validation/test_weak_is_not_dead.py",
              "libs/research/cohort_independence.py"],
    "L1.50": ["tests/validation/test_weak_is_not_dead.py", "scripts/check_utilisation.py",
              "scripts/check_conversion.py"],
    # L1.51: a clamp without a price. Every risk breach is priced to the cent and NOT ONE CLAMP
    # ever carried a dollar figure, so the doctrine's "timidity is a REAL COMPOUNDING COST" and
    # L1.27's "protecting capital, or avoiding uncertainty?" were rhetorical every time. It is
    # fenced separately from L1.28a because that fence publishes a RATIO, and a ratio cannot be
    # weighed against a ruin probability -- dollars can. Its own proving instance was L1.28a's
    # gate reporting SATURATED at utilisation 1.0 on a book holding zero positions, because
    # `_capital()`'s numerator was the first rung inside its own denominator.
    "L1.51": ["scripts/check_idle_cost.py", "libs/research/idle_yield.py",
              "scripts/check_utilisation.py"],
    # L1.52: the unknown-unknown hunt reports its OWN health. check_self_sufficiency is the fence
    # AND was the proving instance -- it returned silently on an absent ledger, so skipping the
    # L2.5 logging duty switched off the check on that duty. blind_spot.py is the writer that
    # makes the metric exist at all; the alternatives hunter is the arm that acts on a lane going
    # dark, including one that merely stopped being probed rather than failing outright.
    "L1.52": ["check_self_sufficiency", "scripts/blind_spot.py",
              "scripts/hunt_source_alternatives.py",
              "libs/research/source_health.py:unproven_sources",
              "scripts/blindspot_max.py", "scripts/blindspot_prober.py"],
    # L1.53: conversion measured against ARRIVALS, and the denominator fenced separately so the
    # ratio cannot be improved by finding less. Both halves live in the one fence, deliberately
    # as two statuses -- DEBT-GROWING (convert faster) and ARRIVALS-COLLAPSED (find harder).
    "L1.53": ["scripts/check_conversion.py",
              "tests/governance/test_conversion_fence.py"],
    # L1.54: a shut door is a routing problem. kimi_hunter is both the fence and the proving
    # instance -- its MODEL_CHAIN, per-wave failure isolation and BLOCKED artifact are the law in
    # code. source_alternatives + the hunter are the same rule for data sources: a registered
    # substitute BEFORE the outage, and source_health's unproven_sources is what notices a lane
    # that went quiet without ever failing.
    "L1.54": ["scripts/kimi_hunter.py", "libs/research/source_alternatives.py",
              "scripts/hunt_source_alternatives.py",
              "libs/research/source_health.py:unproven_sources",
              "tests/scripts/test_kimi_hunter_no_giving_up.py",
              "scripts/check_llm_routing.py", "libs/ops/llm_route.py"],
    # L1.44 asks "is the file I am reading current?" -- one hop, age only. It cannot ask whether
    # the PRODUCER of that file could read ITS inputs, so run_live_guard published a ladder
    # constant and six never-evaluated conditions as a measurement, from a path that has never
    # existed, and every gate in the chain reported green. Freshness does not compose.
    "L1.55": ["scripts/check_input_provenance.py", "libs/ops/input_provenance.py",
              ],
    # L1.56: a screen may not gate its own promotion. The proving instance is the whole point --
    # 120 scored cells, 12 forward slots, ZERO clocks ever started, four breaks each failing
    # CLOSED and each silent, and the accumulated silence read as "no edges exist". The fence is
    # a max_audit check rather than a standalone script, so it ALSO needs its _FENCE_OWNERS row
    # below; the law arrived mapped in neither and the matrix correctly called it UNENFORCED.
    "L1.56": ["check_survivor_pipeline", "tests/research/test_survivor_pipeline.py",
              "scripts/finalize_axis_screens.py", "scripts/run_paper_sleeve_spawner.py"],
    # L1.57: fence_exit fixed the map from status to exit code; it cannot see a status that is
    # honestly OK because the fence examined NOTHING. 18 of 40 fences passed vacuously and 10
    # more published len(<hardcoded literal>) as a denominator. The refusal lives in fence_exit
    # (scanned=), the registry self-builds, and the meta-fence is subject to its own law.
    "L1.57": ["scripts/check_denominators.py", "libs/ops/denominator.py",
              "libs/ops/fence_exit.py", "tests/governance/test_denominators.py",
              "scripts/check_exploration.py", "scripts/check_calendar_gates.py"],
    # L1.58 is the executable edge/P&L waterfall and loss investigation loop.
    "L1.58": ["scripts/run_trade_forensics.py",
              "libs/execution/execution_tape.py", "check_forensics_fresh",
              # R0334 (principal 2026-08-01): the sleeve's only scoreboard was a blended win_rate
              # and mean_R, which cannot separate a good thesis exited badly from a bad thesis
              # rescued by the ladder. Six components, each with its own denominator and its own
              # refusal -- target quality is UNMEASURABLE-BY-DESIGN on a sleeve that forbids
              # take-profits, and the stop check reports itself as a constant-pass gate (L1.49).
              "libs/research/execution_quality.py"],
    # L1.59 freezes doctrine growth and makes the mandate answerable to measured value.
    "L1.59": ["scripts/build_enforcement_matrix.py", "scripts/module_justification.py",
              "scripts/check_denominators.py", "scripts/check_ratchets.py",
              "scripts/run_max_push.py", "scripts/check_doctrine_diff.py"],
    # L1.60: L1.57 asks whether the denominator is an int >= 1; nothing asked what it LOST. A
    # fence that reads 1000 files, drops 991 in `except OSError: continue` and declares
    # scanned=9 is recorded DECLARED, non-vacuous and CLEAN. The proving instance is L1.57's own
    # supplier -- check_calendar_gates' `n += 1` sat one line BELOW its handler. Both existing
    # swallow detectors require a Pass body, so the whole `continue`/`return <default>` class was
    # invisible (R0166, prose-only for twelve days). The three repaired fences are listed: each
    # is a regression site, and reverting an `attempted` counter turns the tests red.
    "L1.60": ["scripts/check_denominator_attrition.py", "libs/ops/attrition.py",
              "scripts/check_coverage_floors.py", "scripts/check_calendar_gates.py",
              "scripts/check_llm_routing.py"],
    # L1.61: the desk reconciles its book against the VENUE every cycle and had never once
    # reconciled its own artifacts against EACH OTHER. Every instrument is single-artifact BY
    # CONSTRUCTION -- phantoms asks "does a writer exist", fresh asks "is it old",
    # input_provenance asks "were MY inputs present" -- so contradiction, which exists only in
    # the RELATION between two artifacts, was invisible to all of them. Proving instance was
    # live on the only path to capital: gate0_readiness and live_guard evaluate the same five
    # Gate-0 criteria through the same function and FOUR disagreed. The general index was
    # REFUTED by its own falsifier (418 disagreements, ~0 genuine), so the registry is
    # hand-built and money-path only.
    "L1.61": ["scripts/check_claim_consistency.py", "libs/ops/claim_registry.py"],
    # L1.62: the Stage-A screen's cross-sectional power denominator was an ASSUMPTION at both
    # endpoints, one change apart, and neither was ever measured. Pre-08-11 panel_width was not
    # passed (K symbols = K observations, t inflated sqrt(K)); the fix passed the full width
    # (K symbols = ONE observation). Measured on the desk's own 139-symbol panel the answer is
    # ~93, so the divisor is 1.50 not 139 and the detection floor ran 9.6x high. Invisible
    # because the error ran CONSERVATIVE and its only symptom is SCREEN-UNDERPOWERED -- "could
    # not tell", which writes no graveyard entry, no clock and no alert, and holds 380 of 711
    # verdicts on disk. Both copies of the expression are listed: type2_cost.correlation_n_eff
    # documents itself as a deliberate copy "so the two cannot disagree", so a fix in one file
    # leaves the other authoritative. The screen caller is a regression site -- removing its
    # measure_panel_breadth call turns the tests red.
    # The CROSS-SECTION FLOOR joins this family rather than minting a law of its own (L1.59
    # freezes doctrine expansion; L2.9 says upgrade before building). It is the SAME defect one
    # axis over: L1.62 caught a denominator that ASSUMED how many independent bets a date carries,
    # this catches one that counts the panel's DECLARED WIDTH (`shape[1]`) instead of the finite
    # symbols a date actually has. A 373-column panel clears `shape[1] >= 8` on a date carrying
    # six names. Measured 2026-08-13: 12 of 311 dates carried 98.1% of a lag-1 statistic, reading
    # rho=+0.856 against a floored truth of -0.06. run_derivative_shadow is a regression site --
    # it is the declared locked mirror of backfill_oi_ls_oos and was the unfloored half.
    "L1.63": ["libs/validation/partition_power.py",
              "libs/autodiscovery/regime.py", "libs/risk/sleeve_allocation.py",
              "scripts/check_promotion_gate.py",
              ],
    "L1.62": ["scripts/check_panel_breadth.py", "libs/research/panel_breadth.py",
              "libs/research/axis_screen.py", "libs/validation/type2_cost.py",

              "scripts/check_cross_section_floor.py", "libs/research/cross_section_floor.py",
              ],
    # L1.64: the only deployed sleeve's margin construction (spot wallet + separately-margined
    # USDT-M short) was INHERITED from connector order, never decided. The one place capital
    # efficiency was modelled hardcoded _PM_EFFICIENCY=1.8 and applied it at every equity level
    # including the PM-ineligible seed, while the constructions usable TODAY (Multi-Assets;
    # COIN-M 1x self-collateralised, liq unreachable -- the desk's own mined 8btc card-31
    # evidence) were modelled nowhere. The comparator measures notional_per_equity per
    # construction (inherited: 0.75 at the executor's venue leverage 3; self-collateralised:
    # ~1.0, +33% capacity with liquidation risk FALLING); the fence fails INHERITED /
    # DIVERGED / DECIDED-STALE / UNMEASURED, and a decision against zero measured alternatives
    # is refused as paperwork (L1.28a). run_capital_plan is a regression site -- it now imports
    # CAPITAL_LEVELS + split_wallet_npe from the comparator, and the AST test that pins the
    # deleted constant turns red if the fork returns.
    # L1.67: every sizing function on the MT5 money path priced a stop as `dist * CONTRACT_OZ *
    # FX_EUR` -- gold's contract size times a frozen EUR/USD rate, 92.00 -- for whatever symbol
    # the sleeve named. The venue's own tick economics say 0.86 EUR per price unit per lot on
    # BTCUSD, 86.41 on XAUUSD, 542.40 on every JPY cross and 86,414 on EURUSD. Live, not latent:
    # sleeve_set rewrites every promoted sleeve's lot to "auto_ramp", so promoted_lot -> auto_lot
    # is always taken. Measured at EUR 1,683.89 -- a CADJPY sleeve sized 0.46 lot, logged 1.26%
    # risk and ran 7.41%, while cap_by_heat billed it gold's 0.98% and admitted three for a
    # believed 2.94% book against a true 22.2%. gateway.py is the regression site; the positive
    # control (the pre-fix gateway must read CONSTANT-ON-SIZING-PATH) is committed as a test.
    "L1.67": ["scripts/check_risk_units.py", "desks/mt5/mt5desk/risk_units.py",
              "desks/mt5/mt5desk/gateway.py"],
    # R0369 (under L2.3/§42): an implemented row's --commit is the ledger's whole proof mechanism,
    # and it was enforced only at WRITE time -- `dispose` refuses an empty field and asks nothing
    # else. A rebase rewrites SHAs and the citation quietly names an object no other clone can
    # resolve. Measured over 227 citing rows: 14 INVALID (10 the literal `HEAD`, 4 `pending`) and
    # 1 ORPHANED. `HEAD` is the half no existence check could ever catch: it resolves everywhere,
    # to a different commit for every reader. The repair is UPWARD and wired -- `repoint` moves a
    # pointer without disturbing the disposition and refuses an unresolvable replacement.
    "L2.3-r0369": ["scripts/check_citation_integrity.py", "libs/research/citation_integrity.py",
                   "scripts/recommendations.py"],
    # R0287 capital-basis invariant (under L1.58's waterfall discipline): a return without its
    # declared denominator is the Quantopian-2019 shape (190% headline, 58% on capital actually
    # drawn) and this desk's own thrice-repeated class (R0234 ~25x equity undercount, R0235
    # testnet-sizing-live, the 13,155/4,500 split). The fence holds the line on NEW artifacts and
    # carries the dated 2026-08-11 bootstrap debt shrink-only.
    "L1.58-r0287": ["scripts/check_capital_basis.py", "libs/research/capital_basis.py",
                    "tests/research/test_capital_basis.py"],
    # R0288 unlock-calendar conversion (L1.8 data-to-alpha): data/unlock_events.json sat with
    # ZERO python readers and an expiring forward window; the collector accrues first-seen events
    # with POINT-IN-TIME pct-of-float (the snapshot's pct_circ_now was a look-ahead in the
    # conditioning variable), the reader gives the snapshot its first consumer, and forward
    # events route through the event-study gate once enough accrue.
    "L1.8-r0288": ["libs/research/unlock_calendar.py",
                   "tests/research/test_unlock_calendar.py",
                   ],
    # R0371 fee attribution (L1.58 edge preservation / P&L forensics): futures commission is
    # 88.7% of the sleeve's non-funding loss and 0 of 500 trade-tape rows carry a fee field, so
    # the desk could see the dominant loss and not attribute it. binance_testnet.commission_events
    # already answered it and had zero callers; this is the consumer. Per-symbol truth reconciles
    # to the cent ($1,750.878 vs the dashboard's $1,750.88) and four names carry 85.9% of it.
    # Per-round-trip attribution stays REFUSED and the spot leg UNMEASURED -- both are published
    # as refusals rather than zeros, and the 7.1% tape coverage is the defect the surface reports.
    "L1.58-r0371": ["libs/research/fee_attribution.py",
                    "tests/test_fee_attribution.py", "scripts/run_execution_intel.py"],
    # R0303 RETIRED 2026-09-05 (universe mandate). The row read:
    #
    #   "L1.46-r0303": ["tests/research/test_upbit_snapshot.py"]
    #
    # R0303 was the Upbit purge-proof snapshot -- the venue erases a market's candle history at
    # delisting (~11.4 KRW markets/yr; AQT/AERGO lost 2026-08-03), so the collector held full
    # daily history for every market plus flagged-market 1m and its manifest's delist ledger was
    # the treatment group the purge erases. Upbit is a crypto exchange the desk may never hunt
    # again; the collector and its test went with that desk in c242249b, leaving this row citing
    # a path that does not exist -- which check_enforcement_execution.py correctly reported as
    # "LAWS ENFORCED BY NOTHING: L1.46-r0303", taking a LAW fence red.
    #
    # THE LAW IS NOT RETIRED, ONLY THIS ROW. L1.46 (unrecoverable-series duty) keeps its own
    # enforcement two hundred lines above -- scripts/check_clock_provenance.py plus
    # libs/research/clock_provenance.py, both present and both run by the law gate. What is
    # deliberately NOT done is a fake repoint at an MT5 series: a broker does not erase an
    # instrument's bar history at delisting, so pointing this row at the MT5 universe would
    # register a duty against a hazard that venue does not have.
    # R0123 decline grading: L1.29 says an ungraded prediction is a BELIEF that inflates the
    # apparent hit-rate by never counting its misses -- and a sleeve scored only on the trades it
    # CHOOSES to be graded on is that defect with a dominant strategy attached. Nine consecutive
    # PASSes, zero scoreable forecasts. The grader ships with the logging because check_calibration
    # fails on any forecast past its deadline: logging without grading would turn a green survival
    # fence permanently red.
    "L1.29-r0123": ["libs/research/decline_value.py",
                    "scripts/check_calibration.py"],
    # R0121 settlement-calendar screen (§42 capacity lens, L1.6 zero promotion authority). Tests
    # the PREMISE before the economics: nested grids make the trade geometrically impossible at
    # any funding level, and only a genuine phase offset creates a capture window.
    # R0207 the desk's first CAUSAL study. L1.16 (an edge is durable only when its MECHANISM is
    # understood) is the law this serves: every prior hypothesis was observational, and
    # de-contamination plus multiplicity control establish that a relationship is not an ARTIFACT,
    # never that it is CAUSAL. L1.6 governs its authority -- Stage A, zero promotion, a refusal is
    # a first-class result. The rails (parallel trends, placebo, SUTVA) are what separate
    # identification from a correlation with better vocabulary.
    "L1.16-r0207": ["libs/research/natural_experiment.py",
                    ],
    # R0100 axis collectors (2026-08-05): three free, keyless raw-information axes the desk did
    # not hold. Under L1.11 (the moat is the transformation pipeline, never the purchased dataset)
    # and L1.8 (acquisition runs at maximum). collect_perpdex_funding carries the screen-on-
    # discovery duty in-organ -- it screens what it ingests in the SAME run, so an axis cannot be
    # catalogued and abandoned, and it declares clock provenance per L1.46 (venue stamp + receipt).
    # R0291 (2026-08-12): wallet-resolved signed DEX flow, the one axis where waiting IS the
    # loss -- venue retention ~300 trades/pool, so capture is forward-only-unrecoverable
    # (L1.28b(f): acquisition never throttled). Dual clocks per L1.46 (chain stamp + receipt),
    # per-pool window-overflow flagged so sampling truncation is measured, never silent.
    # R0299 (2026-08-12, KR-s1 B): the KR venue flag surface -- Upbit warning + 5 caution flags
    # and Bithumb market_warning + per-asset deposit/withdrawal rails. All three surfaces are
    # SNAPSHOT-ONLY with no history endpoint, so this recorder is the only source of the series
    # (L1.46: recv_only clock declared, unrecorded transitions permanently lost). Bithumb rail
    # state is the independent barrier-height regressor that breaks the KR-premium circularity.
    # A failed fetch is never diffed -- absence must not read as 'all flags cleared' (L1.51).
    # R0375 (2026-08-12): the haircut that decides whether idle dollars may earn was
    # `DEFAULT_HAIRCUT_BPS = 300.0` with no derivation anywhere in the repo, against a measured
    # 5.5bps breakeven -- L1.51's own defect class (a clamp nobody could argue with because
    # nobody had computed it) sitting on the desk's only idle-capital decision. Now derived from
    # net-of-returned-funds exploit losses over integrated TVL-years at a 95% Poisson frequency
    # bound, plus the measured depeg shortfall: 41.7bps. The refusal value is still 300, so an
    # unreadable input keeps the band SHUT rather than opening it on a fabricated small number
    # (L1.55). Risks measured but deliberately unpriced are named, never inferred as zero.
    # CITATION REPAIRED 2026-09-05. `tests/research/test_lending_haircut.py` was deleted with the
    # fifteen other orphan tests whose `scripts.<module>` imports the purge had removed -- in its
    # case `scripts.collect_lending_risk_base_rates`, the crypto lending-risk collector. Deleting
    # it was right (a missing import is a collection error, not a skip, and one interrupts the
    # whole suite) but it left this citation naming a path that no longer exists, which this
    # generator correctly reports as a BROKEN REFERENCE rather than quietly dropping.
    #
    # The LAW still executes: `libs/research/lending_haircut.py` is live, consumed by
    # `libs/research/idle_yield.py`, and exercised by `tests/research/test_idle_yield.py`. So the
    # dead path is removed and the live enforcer stays -- the derivation R0375 replaced a
    # 300bps constant with, and the 300bps refusal value that keeps the band SHUT on an unreadable
    # input, are both still fenced. Only the collector that fed one of its inputs is gone.
    "L1.51-r0375": ["libs/research/lending_haircut.py"],
    # R0102 paper-sleeve auto-spawn: converts corrected Stage-A survivors into costless paper
    # sleeves. L1.6 bounds it (zero promotion authority, zero capital) and L1.18a orders its queue
    # (deployment race -- shortest capacity runway first). It NEVER spawns over the Holm cap: a
    # concurrent clock tightens every standing candidate's bar, so it queues behind retirements.
    "L1.6-r0102": ["scripts/run_paper_sleeve_spawner.py", "libs/research/paper_sleeves.py"],
    # §42 capacity retirement (2026-08-05): 1051 of 1799 scored candidates could not be filled by
    # a $13,151 book at all. Retirement banks the full mechanism (L1.17 research debt, with a
    # named L1.16a resurrection condition) and archives the row; the factory boundary in
    # AutoDiscoveryLab._record_scored stops the backlog re-forming.
    "L1.18a-capacity": ["scripts/retire_unfillable_candidates.py",
                        "libs/autodiscovery/capacity_screen.py"],
    # R0122 LLM discretionary sleeve: paper-only candidate generator whose calls are scored
    # forecasts. Governed by L1.6 (zero promotion authority) and L1.29 (it grades itself).
    # R0122b: the unstructured feed the sleeve trades. Under L1.11a (information asymmetry as a
    # search dimension) -- its latency measurement IS the asymmetry test.
    # R0125 conviction sleeve: aggression is L1.28 (uncapped conviction), the rail is L1.23
    # (stop on every trade, leverage cap, inside the ruin rail).
    # R0133: the marker. Both paper sleeves wrote books nobody ever read -- the purest L1.28a
    # defect, since an unmarked book accumulates confident rows and reports no failure. This organ
    # walks the recorded ladder against real bars, benchmarks against buy-and-hold (L1.6) and
    # feeds the outcome to calibration (L1.29), which is what makes over-confidence self-shrinking.
    # R0134: the discretionary sleeve was asked to read charts it had never been shown -- an
    # unused information source sitting under a strategy that needs it (L2.9), and a ceiling
    # reported as fine while unmeasured (L1.28a). Multi-timeframe structure, per instrument.
    # R0135: four money-path constants were found defective in one session, all round numbers
    # picked by analogy rather than computed. Four of four is a missing mechanism, not bad luck.
    "L1.41-sizing": ["scripts/check_sizing_derivation.py"],
    # R0137: the dashboard showed carry as a SURVIVOR on P&L whose funding term was 3% of it. The
    # desk's own two-sided bleed fence already said "naked leg" -- and gated nothing.
    "L1.6-attribution": ["scripts/check_mechanism_attribution.py",
                         "libs/execution/carry_accounting.py"],
    # R0139: the discretionary desk's learning loop. Lessons climb an evidence ladder before they
    # reach the trader and are retired by their own falsifier -- the same standard L1.6 applies to
    # alpha, applied to the desk's beliefs about its own method.
    "L1.6-playbook": ["docs/DISCRETIONARY_DESK.md"],
    # R0140: copytrading, screened. The naive read (copy the leaderboard's best) is the 420/0
    # selection failure in a new costume; the screen computes the tempting number AND disqualifies
    # it, archives the only unbiased design (a forward panel counting exits as failures), and
    # measures the derivative that does not require picking a winner.
    # R0141: more sleeves multiply growth only if INDEPENDENT. Correlated sleeves draw down
    # together -- risk scales with N, growth with 1, and the desk pays N sets of costs for one bet.
    # R0142: the load-bearing assumption under the whole sizer -- that a stated probability means
    # anything. Zero resolved forecasts existed when this was checked. L1.29 scores it; this poses
    # the questions that give L1.29 something to score without needing capital or venue keys.
    "L1.29-probe": ["scripts/run_calibration_probe.py"],
    # R0143: the desk ruled against CAGR targeting on 2026-07-12, again on 2026-07-16, and a
    # decision-ledger success metric says "no CAGR targeting" -- and a 300% target section still
    # landed on 2026-07-31, caught by the principal rather than by any check.
    "L1.23-no-target": ["scripts/check_return_targeting.py", "docs/PROJECT_HANDOFF.md"],
    # R0144: installed, running and PRODUCING are three different facts. The manifest check proved
    # the LINE existed; nothing proved the organ emitted anything, which is how a miner goes dark
    # with the board still green.
    "L1.28c-liveness": ["scripts/check_organ_liveness.py"],
    # R0150: the symmetric half of the kill condition. The sleeve had a defined way to DIE and no
    # defined way to GROW, which makes expansion an improvised decision taken in the mood of a
    # good week -- the exact moment that decision is worst.
    "L1.6-promotion": ["scripts/check_promotion_gate.py"],
    # R0151: the constitution's ceiling-pushing family applied to the discretionary desk. A HIT
    # RATE is a legal target where a return figure is not -- it cannot be reached by sizing, only
    # by selection, information and filtering, which are exactly the levers to push.
    # R0152: the desk had an optimiser and a learner for ONE discretionary edge and nothing that
    # hunted for a SECOND. A single hypothesis is one regime change away from none, and the
    # allocator's own arithmetic says an independent second edge beats improving the first.
    # R0198: costs are the one growth lever available before any edge is proven -- known BEFORE
    # the trade, and near breakeven a third of the cost stack is worth more than a point of hit
    # rate. Funding is SIGNED and public; the sleeve was blind to which sides get PAID to hold.
    # Selection uses the sign; marking stays always-adverse -- different jobs, different signs.
    # R0200: every coverage organ mapped WHERE the miners look (source families, regions,
    # languages) and none mapped WHAT KIND of edge came back. 42 buried strategies cluster into
    # families, and twelve candidates from one family are correlated by construction -- they die
    # together and the desk learns one thing while reporting twelve tests.
    "L1.32-strategy-coverage": ["scripts/run_strategy_coverage.py"],
    # R0211: the coverage MAP reports and the widened prompts request; neither fails when a miner
    # drifts back to the family it knows, which is how breadth actually dies -- one comfortable
    # session at a time with the volume never dropping. This is the clock behind the rule.
    "L1.32-strategy-breadth": ["scripts/check_strategy_breadth.py"],
    # R0213: "surpass me" is only an instruction if something measures it. The desk already
    # benchmarks every sleeve against buy-and-hold (a levered sleeve that merely tracks the index
    # takes risk for nothing); the human method this sleeve was built to copy is the second
    # benchmark, computed the same way and equally non-optional.
    "L1.6-principal-benchmark": ["scripts/run_principal_benchmark.py"],
    # R0215: the desk DETECTED coma well and TREATED nothing -- three organs reported dark for
    # days, every report correct, no treatment attempted. Detection without treatment is a
    # monitor, not a hospital, and a ward whose alarms nobody answers gets its alarms switched off.
    "L1.32-organ-er": ["scripts/run_organ_er.py"],
    # L1.25a: null streaks throttle nothing -- an organ going quiet is caught by the freshness/
    # productivity wires REGARDLESS of its reason, so "stopped because nothing was working" trips
    # the same fence as "stopped because broken". The pessimism-freeze cannot hide.
    "L1.25a": ["check_organs", "check_stub_deaths", "check_idle_capability",
               "scripts/check_ratchets.py",
               # (b) forward slots fed daily: the WALCL clock (R0031) fills the slot kimchi's
               # retirement freed and accrues via the daily chain's walcl_clock step
               "scripts/derive_walcl_clock.py"],
}

# ---------------------------------------------------------------------------------------------
# SECOND DIRECTION: every FENCE claimed by a law (2026-07-30).
#
# The first pass mapped principles -> fences and left 39 of 71 fences governed by nothing. That is
# the failure mode this script's own docstring names -- "a check with no governing principle is
# complexity nobody voted for" -- and it was sitting in the script's own output, unactioned, which
# is precisely the decoration pattern L2.9 exists to kill. So the reverse index is now explicit.
#
# These are appended into _MAP rather than written inline above so the read direction stays clean:
# above answers "what enforces this law", below answers "why does this check exist at all".
_FENCE_OWNERS: dict[str, str] = {
    # --- RESTORED 2026-08-13, and three of these four had NEVER been mapped even before the
    # merge dropped them. The 8b981a5 resolution took the other branch's max_audit.py wholesale,
    # so all four check_* functions AND their dispatch entries vanished together: no import broke,
    # no test named three of them, and four audits simply stopped running while the auditor kept
    # reporting green. An audit that vanishes is strictly worse than one that fails -- a failure
    # is a signal, an absence is a silence that reads exactly like a pass. The orphan fence caught
    # them the moment they came back, which is the fence doing precisely its job.
    #
    # L1.49 (a gate that never ran is a claim the desk cannot cash) owns two of them, because both
    # assert EXECUTION rather than configuration: one proves the scheduled organ's file exists to
    # be run at all, the other proves the CIO review actually ran rather than being a directive
    # that lives in prose. That is L1.49's exact shape.
    "check_scheduled_scripts": "L1.49",
    # F0011/R0049: a clock may leave the Holm cohort only with a recorded, classifiable
    # mechanism -- the REFUTED-vs-merits distinction is L1.17's structured-knowledge duty
    # applied to the multiplicity denominator.
    "check_clock_retirement_mechanism": "L1.17",
    "check_meta_research": "L1.49",
    # L1.28a: the §35 exclusion for self-disposing dig logs is a CLAIM ABOUT A DOCUMENT, and an
    # unchecked claim is how absence resolves to a clean verdict -- the next session adds an item,
    # forgets the tag, and the item is governed by nothing while the exclusion still says
    # otherwise. The check is what makes the exclusion honest rather than trusted.
    "check_dig_log_disposition": "L1.28a",
    # L1.23, carried from its original mapping: a page is half a channel. The desk verified
    # DELIVERY for weeks and never verified the principal could ANSWER, so when a fork deleted
    # _poll_replies the pager went one-way and four decisions gating the book sat unanswerable.
    "check_principal_page_unanswerable": "L1.23",
    # --- READ-WITHOUT-WRITER (L1.40): the defect lens L1.40 names FIRST and calls this desk's most
    # prolific class -- "the capital-event equity bug was exactly this". check_phantom_paths is its
    # detector: a path read by code, absent from disk, written by nothing. Such a reader does not
    # crash; it takes the empty branch and returns a plausible zero, so the organ reports HEALTHY on
    # data that does not exist. Live instances were all found BY HAND before it existed
    # (research_memory.db with four readers and no writer; cost_ratio, slippage_ks_p and
    # calibration_mae_falling_months as ramp step-up conditions with no producer while the ramp sat
    # pinned at its floor), which is exactly the hand-is-not-a-mechanism gap L1.41 exists to close.
    "check_phantom_paths": "L1.40",
    # --- L1.54 (a shut door is a routing problem, not a verdict). Both fences landed unmapped and
    # therefore REFUSED EVERY PUSH on this branch -- the same failure my own check_paywalls_
    # registered hit at c8983b1, which makes it a class rather than an accident: a max_audit fence
    # is wired by adding the FUNCTION here, and adding the script to `_MAP` does not do it.
    # Mapped from each fence's own docstring, which names L1.54 explicitly, not from a guess:
    # "A blocked route the desk stopped chasing is an accepted loss. L1.54 forbids accepting it."
    # and "the enumerated exhaustion L1.54 demands rather than silence."
    "check_blocked_routes_hunted": "L1.54",
    "check_verified_alternatives_promoted": "L1.54",
    # --- SAME LENS, ONE TURN LATER (L1.40): check_phantom_paths catches a reader whose source was
    # NEVER written; check_dormancy_disarm catches a reader whose source WENT EMPTY. Both take the
    # empty branch and return a plausible healthy answer, but the second is harder to see because
    # the file exists, parses, and carries a young mtime -- only the list inside is empty, so every
    # staleness fence on this desk reads it as fresh. Live instance 2026-08-05: the carry book's
    # structural-bleed denylist read `worst_symbols`, a 14-day rolling window over the book's own
    # closes; the book paused on a drawdown, the window emptied, and the gate began allowing the
    # two incident-#6 symbols its own comment calls "currently-blocked". A pause is CAUSED by
    # losses, so the guard was guaranteed to be disarmed exactly when it was needed.
    "check_dormancy_disarm": "L1.40",
    # --- conversion parity (L1.28b): the repair wire's two halves. check_conversion measures the
    # daily flow (arrival vs disposition, FLATLINE on silence); check_recommendation_rows (§42 X1,
    # built independently by the box the same day) applies per-row carry-over pressure so old
    # rows are seen again. Same law, complementary directions.
    "check_recommendation_rows": "L1.28b",
    # --- capacity (§42 / L1.18a): six fences, one law. Small edges are hunted, filled and RETIRED
    # on arithmetic, never ranked down for being small.
    "check_capacity_hunt": "L1.18a",
    "check_capacity_knobs_are_wired": "L1.18a",
    "check_capacity_governor_reachable": "L1.18a",
    "check_capacity_allocation_honesty": "L1.18a",
    "check_capacity_runway": "L1.18a",
    "check_capacity_single_source": "L1.18a",
    # --- artifact-over-claim (L2.4): a capability exists only if something it wrote is FRESH.
    "check_organs": "L2.4",              # organ never fired / always dies
    "check_stub_deaths": "L2.4",         # runs that died at birth on quota/auth still "ran"
    "check_stale_daemons": "L2.4",       # daemon older than its source = a fix that never shipped
    "check_producer_cadence": "L2.4",    # an inventory-accumulating artifact declares a cadence
    "check_deploy_path": "L2.4",         # code that never reaches the box was never deployed
    # --- forced disposition (L2.3): every finding gets a ruling, and rulings are not allowed to rot.
    "check_findings": "L2.3",
    "check_findings_tracked": "L2.3",
    "check_findings_scope": "L2.3",
    "check_review_risks_tracked": "L2.3",
    "check_decision_ledger_matures": "L2.3",
    # --- execution physics (L1.5): the costs that quietly eat a carry.
    # RETIRED 2026-09-05 with their checks (universe mandate): `check_bnb_funded` (Binance
    # BNB fee-burn funding) and `check_fee_carry_ratio` (the §40 commission-over-perp-funding
    # ratchet). Both were L1.5 execution-physics rows whose subject was a crypto-exchange
    # account setting and a perp revenue line. L1.5 itself stands and keeps its other fences.
    "check_close_retry_loop": "L1.5",    # a carry that cannot close is a churn engine
    # --- survival rails (L1.23): states that read HEALTHY while being terminal.
    "check_book_collapse": "L1.23",
    "check_book_absorbing_state": "L1.23",   # a rail that can never release the book is not safety
    # L1.44 is the freshness law, and this is its sharpest case: the published rail verdict is a
    # produced artifact whose consumers (dashboard, pager, check_idle_cost) cannot see its age,
    # because `_emit` copies `rb['risk']` forward onto a file whose mtime keeps advancing. The
    # feed's own freshness is a heartbeat, and a heartbeat proves the loop is alive, never that
    # the pipe is. Compares the recomputed decision against the published one rather than asking
    # its age -- a fresh-and-wrong verdict passes every age bound there is.
    "check_rail_verdict_published": "L1.44",
    # --- injection + fence integrity (L2.1 / L2.2): the enforcement layer auditing itself.
    "check_constitution": "L2.1",
    "check_universal_doctrine": "L2.1",
    "check_registry_complete": "L2.2",   # an unregistered check is a law believed-but-not-enforced
    "check_artifact_governance": "L2.2",
    "check_ci_scope": "L2.2",            # a CI gate on a hardcoded subset is a map, not a territory
    "check_law_numbers_unique": "L2.8",  # a law number naming two laws breaks amendment itself
    # --- dormancy / reachability (L2.9): built-but-unwired, in three shapes.
    "check_orphan_scripts": "L2.9",
    "check_orphan_modules": "L2.9",
    "check_money_path_wired": "L2.9",    # a money-path module with only a test caller
    # --- discovery duties (L1.8 / L1.9 / L1.11a / L1.24).
    "check_clock_saturation": "L1.8",    # objective-#2 duty: the clock is the scarce resource
    "check_mine_scope": "L1.8",          # a find written somewhere unscanned is outside the law
    "check_mine_scope_vacuous": "L1.57",  # the INWARD leak: a doc IN scope the parser cannot see,
                                          # so §33 reads a clean backlog off an empty set
    "check_feed_inbox_backlog": "L1.8",  # a queue nobody counts becomes an archive (R0269)
    "check_source_backlog": "L1.9",      # a catalogue that grows faster than it is verified
    "check_dig_uncommitted": "L1.9",     # VPS disk is not institutional memory
    "check_paid_target_registry": "L1.11a",
    # Same duty from the other end: the registry fence above asks whether a KNOWN paid target is
    # tracked, this one whether a paywall the desk actually WALKED INTO ever reached the registry.
    "check_paywalls_registered": "L1.11a",
    "check_holdings_never_shrink": "L1.24",  # information advantage measured as a holding, not act
    # --- remaining singletons.
    "check_panel": "L1.7",               # adversarial review capability being DOWN is a defect
    "check_memory_hygiene": "L1.17",     # research debt is only debt if it is written and findable
    "check_mine_evidence_base": "L1.6",  # a ratchet calibrated on n=2 is superstition with a JSON
    # --- THE ECONOMIC OBJECTIVE (L1.57-L1.59, 2026-08-08). These three laws are about WEALTH
    # rather than about process, so their fences are behavioural tests and one report rather than
    # a `check_*` script: there is no pass/fail condition on "the objective is retained log
    # wealth", only a scoreboard that must exist, must refuse to invent numbers, and must rank
    # above the architecture counts.
    "tests/portfolio/test_return_engines.py": "L1.57",
    "tests/scripts/test_wealth_report.py": "L1.57",
    "tests/portfolio/test_wealth_retention.py": "L1.58",
    "tests/research/test_conversion_velocity.py": "L1.59",
    "tests/validation/test_state_conditional.py": "L1.59",
    # --- claimed at the 2026-08-04 merge: both branches' new fences, each under the law it serves.
    "check_asymmetry_ratchet": "L1.24",       # owned-data advantage is a holding that must not shrink
    "check_coexistence": "L1.23",             # sleeves sharing a book must not defeat its rails
    "check_constitution_review": "L2.8",      # the quarterly review is amendment law's own cadence
    "check_data_decay": "L1.19",              # decay is measured on the revalidation clock, not assumed
    "check_dependency_drift": "L2.2",         # a suite green on the wrong pins is not evidence
    "check_evig_ranking": "L1.26",            # research capital is priced by ERV/EVIG, not by recency
    "check_fixers_not_watchers": "L1.13",     # a watcher with no remediation loop is a stale register
    "check_governing_layer_live": "L2.2",     # the enforcement layer auditing that it itself runs
    "check_law_coverage": "L2.2",             # a law with no fence is believed-but-not-enforced
    "check_llm_exhaustion": "L1.28a",         # a seat asked once is paid-for capacity left idle
    "check_moat_screened": "L1.11",           # unscreened moat candidates are vendor data with extra steps
    "check_model_freshness": "L1.12",         # a verified better model unadopted is idle capability
    "check_naive_datetime": "L1.41",          # tz-naive stamps are the build standard's silent-corruption class
    "check_no_ceiling": "L1.28",              # anti-timidity: nothing capped below its measured maximum
    "check_silent_swallows_on_the_rails": "L1.41",  # a bare except on the money path is a refusal-path hole
    "check_survivor_pipeline": "L1.56",       # zero results is a claim about the INSTRUMENT until it is shown to work
    "check_test_suite_collectable": "L2.2",   # a suite that cannot collect enforces nothing
    # Same family as the line above, one cause upstream (R0407a): an OOM-killed probe reports as a
    # broken suite, so the box running out of memory is a condition under which the desk's evidence
    # stops being evidence -- exactly what check_dependency_drift and check_test_suite_collectable
    # each say about their own precondition. Not L1.28a: that law is about running a ceiling AT its
    # limit, and RAM at 100% is the failure, not the goal.
    "check_host_memory_headroom": "L2.2",     # a verdict the box had no memory to produce is not one
    "check_triage_disposition": "L1.17",      # self-dispositioning registers stay honest or lose the exclusion
    "check_under_exploration": "L1.32",       # under-exploration is a breach, not a preference
    "check_unwired_modules": "L2.9",          # built-but-unreachable, the third shape of dormancy
    # --- claimed 2026-09-05: eleven max_audit fences born 2026-08-26..28 (the cron-death and
    # consolidation repairs) landed without a row here, so the matrix reported them as complexity
    # nobody voted for and the law gate was red on every push. Each is keyed by the law its own
    # docstring describes; none needed a new principle.
    "check_unit_deaths": "L1.28c",            # an organ that died abnormally is not producing
    "check_manifest_backlog": "L1.28c",       # a schedule nobody is checking is not a cadence
    "check_authority_writers_scheduled": "L1.49",  # an authority artifact nobody writes is uncashable
    "check_launcher_seal": "L1.41",           # a launcher bash can rewrite mid-run is below standard
    "check_sync_launder": "L1.38",            # a sync reverting money-path code is an uncaught change
    "check_verifier_reads_injection": "L2.1", # the verifier reads what the injection actually carries
    "check_route_shaped_identity": "L1.25",   # an identity that breaks on every outage is a welded gate
    "check_one_way_flags": "L1.45",           # a flag nothing clears is an absorbing state
    "check_worktree_on_tmpfs": "L2.2",        # a checkout in RAM is a verdict the box cannot afford
    "check_page_before_spawn": "L2.2",        # a suppressed page must not cost an interpreter
    "check_recursion_rule_applied": "L2.2",   # a FIXED row without a fence is a lesson paid twice
}
for _fence, _pid in _FENCE_OWNERS.items():
    _MAP.setdefault(_pid, []).append(_fence)

# Laws a fence cannot satisfy, each with the reason. Being explicit is the point: an unfenceable law
# recorded as HUMAN-ONLY is a decision; one silently absent from the map is a hole.
_HUMAN_ONLY: dict[str, str] = {
    "L2.8": "the REVIEW is a human judgement (default outcome STABILITY); a fence would either "
            "block legitimate change or rubber-stamp it. Its BOUNDARY is not human-only: L2.8a "
            "hashes the five clauses evolution may never touch (check_constitution_core.py), so "
            "what is unfenced here is the judgement, not the safety margin",
}
#: A law whose SUBJECT left the desk with the retired universe -- not upheld, not violated, not
#: enforceable, because the thing it governs is not here. Its own status so it can never be read
#: as ENFORCED, and every entry carries the CONDITION THAT ENDS IT: an exclusion with no path back
#: is how a law gets quietly dropped, and "ask of any exclusion: what is the path back?" is the
#: same rule the source backlog's dated deferrals answer with a date.
#:
#: This category is narrow ON PURPOSE and is not a home for inconvenient laws. L1.47 was a
#: candidate for it earlier the same day and does NOT belong here: MT5 swap is a discrete,
#: weekly-tripled charge recorded for all 251 symbols, so its subject is alive and it is mapped to
#: a real scheduled fence above. The test for entry is whether an artifact exists that could be
#: pointed at, not whether pointing at one would be work.
_SUBJECT_RETIRED: dict[str, str] = {
    "L1.64": "MARGIN TOPOLOGY. The law compares capital structures that were specific to the "
             "retired crypto-exchange desk -- long spot in a spot wallet against a short USDT-M "
             "perp in a separately-margined futures wallet, a construction that 'fell out of "
             "which connectors were built first'. Its fence, its library "
             "(libs/portfolio/margin_topology) and its consumer (run_capital_plan.py) were "
             "deleted in the purge, and tests/governance/test_margin_topology_fence.py already "
             "skips because the fence cannot import. PATH BACK: the law's QUESTION -- was the "
             "book's capital structure decided or inherited? -- applies to Fusion with equal "
             "force, because the account's leverage tier, its margin model and whether it is in "
             "hedging or netting mode were likewise never chosen by this desk. The moment the "
             "desk records those from the live account (an MT5 AccountInfo snapshot names all "
             "three), L1.64 is rewritten against them and leaves this category for a fence.",
}
_STANDING: dict[str, str] = {
    "L1.0": "ratchet meta-law -- check_ratchets.py enforces the FLOORS across every measured "
            "property, and run_max_push.py enforces the DIRECTION: one ranked queue of everything "
            "not yet at 100%, which never reports done (all-green escalates to "
            "MEASUREMENT-SET-TOO-SMALL). STANDING rather than ENFORCED because the law is a "
            "standing duty on every cycle, not a single pass/fail condition",
    "L2.0": "enforcement meta-law -- satisfied by the existence of this matrix",
}


def _principles() -> dict[str, str]:
    """principle id -> its first sentence (the requirement), read from the constitution.

    TWO HEADING FORMS EXIST AND ONLY ONE WAS PARSED, which made this fence blind to the four
    newest laws on the desk. Everything up to L1.47 is written `**L1.47 TITLE**`; every law from
    L1.48 onward is written `## L1.48 TITLE`. The bold-only pattern silently skipped L1.48, L1.49,
    L1.50 and L1.51 -- so the matrix published `n_principles: 68` and `fences with no governing
    principle: 0` over a set that EXCLUDED them, and a fence could name one of those laws as its
    owner and be counted as governed by a principle this function had never seen.

    That is the L1.43 welded-gate shape one level up: the tally was not wrong about what it
    counted, it was wrong about what it looked at, and a check that reports a clean 0 is exactly
    the one nobody re-reads. Found 2026-08-05 while wiring L1.51 -- the law being added was itself
    invisible to the fence that certifies laws are enforced.
    """
    text = _CONST.read_text("utf-8")
    out: dict[str, str] = {}
    for m in re.finditer(r"^\*\*(L\d+\.\d+[a-z]?)\s+([^*]+)\*\*(.*)$", text, re.MULTILINE):
        pid, title, rest = m.group(1), m.group(2).strip(), m.group(3).strip()
        first = re.split(r"(?<=[.!])\s", rest, maxsplit=1)[0] if rest else ""
        out[pid] = f"{title.rstrip('.')} — {first}".strip(" —")[:400]
    # `## L1.xx TITLE` -- the form every law since L1.48 uses. The requirement sentence lives in
    # the paragraph BELOW the heading rather than on the same line, so it is read from there.
    # The bold form wins on collision: it is the older, denser one and carries the rest inline.
    for m in re.finditer(r"^#{2,}\s*(L\d+\.\d+[a-z]?)\s+(.+?)\s*$", text, re.MULTILINE):
        pid, title = m.group(1), m.group(2).strip()
        if pid in out:
            continue
        para = next((p.strip() for p in text[m.end():].split("\n\n") if p.strip()), "")
        para = re.sub(r"\s+", " ", para)
        first = re.split(r"(?<=[.!])\s", para, maxsplit=1)[0] if para else ""
        out[pid] = f"{title.rstrip('.')} — {first}".strip(" —")[:400]
    return out


def _fence_names() -> set[str]:
    return set(re.findall(r"^def (check_[a-z_0-9]+)", _AUDIT.read_text("utf-8"), re.MULTILINE))


def _exists(ref: str) -> bool:
    """Does the enforcing artifact actually exist? A mapping to a deleted file is worse than none.

    TWO REGISTRIES, AND THE `.py` SUFFIX IS THE ONLY THING THAT SEPARATES THEM (R0436). A ref
    beginning `check_` can mean either of two entirely different objects: a FUNCTION inside
    scripts/max_audit.py, or a standalone fence SCRIPT on disk. This used to short-circuit ANY
    `check_`-prefixed ref into the function table, so `check_denominators.py`, `check_freshness.py`
    and every other standalone fence written in the bare form was resolved against a registry it
    can never appear in -- reported BROKEN-REF, which exits 1 and hard-blocks every push (L1.37),
    with a message naming the ref and nothing about why.

    `_fence_names()` regexes `^def (check_[a-z_0-9]+)`, and `.` is not in that character class, so
    a max_audit function name can NEVER end in `.py`. That makes the suffix an exact discriminator
    rather than a heuristic: with it, the ref means the script; without it, the function. Both
    forms are now askable, which is what the old code had no way to express.

    THE ACCEPT DIRECTION IS THE SAFE ONE and it loosens nothing: the file branch still requires the
    path to EXIST on disk, so a mapping to a deleted or misspelled fence fails exactly as before. A
    max_audit function mistakenly written `check_foo.py` has no `scripts/check_foo.py` behind it
    and still reports BROKEN-REF. What changes is only that a real fence, mapped by its real
    filename, stops being unmappable -- and an unmappable fence is one a future author is cheapest
    to leave unmapped, which is the outcome this matrix exists to prevent (L2.0).
    """
    bare = ref.split(":")[0].split(" ")[0]
    if bare.startswith("check_") and not bare.endswith(".py"):
        return bare in _fence_names()
    return any(cand.exists() for cand in (_ROOT / bare, _ROOT / "scripts" / bare))


def _scheduled(refs: list[str]) -> list[str]:
    man = _MANIFEST.read_text("utf-8") if _MANIFEST.exists() else ""
    return [r for r in refs if Path(r.split(":")[0].split(" ")[0]).name in man]


def _master_authority() -> dict[str, Any]:
    """Expose the limit of this matrix instead of Goodharting its clean companion score."""
    text = _MASTER.read_text("utf-8")
    canonical = text.replace("\r\n", "\n").replace("\r", "\n").encode("utf-8")
    sections = len(re.findall(r"^# \d+\.", text, re.MULTILINE))
    return {
        "master_path": _MASTER.relative_to(_ROOT).as_posix(),
        "master_sha256": hashlib.sha256(canonical).hexdigest(),
        "master_sections": sections,
        "master_to_code_crosswalk": {
            "status": "UNMEASURED",
            "covered_sections": None,
            "total_sections": sections,
            "owed": True,
            "scope_note": (
                "The executable matrix below covers docs/CONSTITUTION.md companion laws; it is "
                "not yet a section-by-section enforcement crosswalk for the sealed master."
            ),
        },
    }


def build() -> dict[str, Any]:
    principles, fences = _principles(), _fence_names()
    rows: list[dict[str, Any]] = []
    for pid, requirement in sorted(principles.items()):
        refs = _MAP.get(pid, [])
        live = [r for r in refs if _exists(r)]
        broken = [r for r in refs if r not in live]
        if pid in _SUBJECT_RETIRED:
            status, note = "SUBJECT-RETIRED", _SUBJECT_RETIRED[pid]
        elif pid in _HUMAN_ONLY:
            status, note = "HUMAN-ONLY", _HUMAN_ONLY[pid]
        elif pid in _STANDING:
            status, note = "STANDING", _STANDING[pid]
        elif live:
            status, note = "ENFORCED", ""
        else:
            status, note = "UNENFORCED", "no fence or runtime mechanism maps to this principle"
        rows.append({"principle": pid, "requirement": requirement, "status": status,
                     "enforced_by": live, "broken_references": broken,
                     "scheduled": _scheduled(live), "note": note})

    # ORPHANS ARE COMPUTED OVER FUNCTION REFS ONLY. `fences` holds max_audit FUNCTION names, which
    # never carry a `.py` suffix, so a script ref could never have cancelled an orphan anyway --
    # but leaving `check_foo.py` in this set would quietly claim it might, and a set whose members
    # cannot match its counterpart is the kind of near-miss that reads as coverage (R0436).
    mapped_fences = {r.split(":")[0] for refs in _MAP.values() for r in refs
                     if r.startswith("check_") and not r.split(":")[0].endswith(".py")}
    orphan_fences = sorted(fences - mapped_fences)
    counts: dict[str, int] = {}
    for r in rows:
        counts[str(r["status"])] = counts.get(str(r["status"]), 0) + 1
    return {
        "generated": datetime.now(tz=UTC).isoformat(),
        "law": "L2.0/L2.2 -- a principle with no enforcement is prose; a fence with no principle "
               "is unvoted complexity. Both directions are engineering gaps.",
        "authority": _master_authority(),
        "counts": counts, "n_principles": len(principles), "n_fences": len(fences),
        "unenforced": [r["principle"] for r in rows if r["status"] == "UNENFORCED"],
        "broken_references": {r["principle"]: r["broken_references"] for r in rows
                              if r["broken_references"]},
        "fences_without_a_principle": orphan_fences,
        "matrix": rows,
    }


#: Where a `check_*` FUNCTION inside scripts/max_audit.py is claimed by a law. Named here as a
#: constant so the failure message and the registry can never drift apart in a rename.
_OWNERS_REGISTRY = "_FENCE_OWNERS in scripts/build_enforcement_matrix.py"


def _orphan_remediation(orphans: list[str]) -> str:
    """The exact line to add, for the exact fence that failed. R0427.

    THE GATE KNEW THE ANSWER AND PRINTED THE QUESTION. This refusal has blocked pushes for
    everyone on a shared branch twice in four commits (c8983b1 check_paywalls_registered;
    cc28734 check_blocked_routes_hunted + check_verified_alternatives_promoted) -- different
    authors, three commits apart, which makes it a class rather than an accident. Both times the
    fix was one line in a registry the message never named, while the trap it is mistaken for
    (adding the SCRIPT PATH to `_MAP`) reads as equivalent in review and does nothing, because
    there is no script path for a function.

    The remediation is emitted as copy-pasteable source rather than prose. An instruction the
    reader has to translate is an instruction they can translate wrongly, and the wrong
    translation here is the exact edit that looks correct and fails.
    """
    lines = [
        f"  HOW TO FIX -- add each fence to {_OWNERS_REGISTRY}, keyed by the law its own",
        "  docstring already names (map from the docstring, never from a guess):",
        "",
    ]
    lines += [f'      "{name}": "L1.x",   # <- replace L1.x with the law this fence enforces'
              for name in orphans]
    lines += [
        "",
        "  A max_audit fence is a FUNCTION, so it is wired by FUNCTION NAME. Adding the script",
        "  path to `_MAP` looks equivalent, reads equivalent in review, and does nothing -- the",
        "  orphan set is computed over refs starting with `check_`, and no script path is one.",
        "  If no existing law covers the fence, THAT is the finding: either the fence is unvoted",
        "  complexity (retire it), or the constitution is missing a principle the fence already",
        "  assumes (raise it). Both need a decision; neither is silence.",
    ]
    return "\n".join(lines)


def _broken_ref_hints(refs: list[str]) -> list[str]:
    """Explain a BROKEN-REF whose artifact is sitting right there on disk (R0427/R0436).

    `_exists` resolves a `check_`-prefixed ref against max_audit's FUNCTION table unless it carries
    a `.py` suffix. That is now an exact rule rather than a short-circuit, but it is still a rule
    the author cannot see from the failure, and the surviving failure mode is the SUFFIXLESS one:
    `check_foo` when the fence is a standalone `scripts/check_foo.py`. The status is correct and
    the reason is invisible, which sends the author hunting a file that already exists.

    The `.py` case is kept because a fence at the REPO ROOT rather than under `scripts/` still
    fails, and because a repo that reverts `_exists` must not silently lose the explanation.
    """
    hints = []
    for ref in refs:
        bare = ref.split(":")[0].split(" ")[0]
        if not bare.startswith("check_"):
            continue
        if bare.endswith(".py"):
            if (_ROOT / "scripts" / bare).exists():
                hints.append(
                    f"{bare} EXISTS at scripts/{bare} -- write it path-first as `scripts/{bare}`. "
                    f"A ref starting with `check_` and carrying no `.py` suffix is resolved "
                    f"against max_audit's FUNCTION table, which a standalone script can never "
                    f"appear in.")
        elif (_ROOT / "scripts" / f"{bare}.py").exists():
            # THE AMBIGUITY R0436 NAMES, from the other side: a bare `check_foo` is a request for
            # the FUNCTION registry, and max_audit has no such function -- but a fence SCRIPT of
            # that name is on disk. Two registries, one spelling, and the author gets a refusal
            # about a fence they can see. Name the suffix that asks for the other one.
            hints.append(
                f"{bare} is not a function in scripts/max_audit.py, but scripts/{bare}.py EXISTS. "
                f"A suffixless `check_` ref asks for max_audit's FUNCTION table; add the suffix "
                f"(`scripts/{bare}.py`) to ask for the standalone fence script instead.")
    return hints


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--report-only", action="store_true", help="always exit 0")
    args = ap.parse_args()
    m = build()
    _OUT.parent.mkdir(parents=True, exist_ok=True)
    _OUT.write_text(json.dumps(m, indent=2), "utf-8")
    if args.json:
        print(json.dumps(m, indent=2))
    else:
        print(f"enforcement matrix: {m['counts']} over {m['n_principles']} principles / "
              f"{m['n_fences']} fences")
        crosswalk = m["authority"]["master_to_code_crosswalk"]
        print(f"  sealed master: {m['authority']['master_sections']} sections; "
              f"master-to-code crosswalk={crosswalk['status']} (owed={crosswalk['owed']})")
        for pid in m["unenforced"]:
            print(f"  UNENFORCED {pid}")
        for pid, refs in m["broken_references"].items():
            print(f"  BROKEN-REF {pid} -> {refs}")
            for hint in _broken_ref_hints(refs):
                print(f"      {hint}")
        n_orph = len(m["fences_without_a_principle"])
        print(f"  fences with no governing principle: {n_orph}"
              + (f": {m['fences_without_a_principle']}" if n_orph else ""))
        if n_orph:
            print(_orphan_remediation(m["fences_without_a_principle"]))
        print(f"-> {_OUT.relative_to(_ROOT)}")
    if args.report_only:
        return 0
    # Fail on an unenforced principle, a mapping to a missing artifact, OR an unclaimed fence.
    #
    # That last one is a RATCHET (L1.0), turned on the day the backlog hit zero (2026-07-30). While
    # 39 fences predating this map were unclaimed, failing on them would only have taught the desk
    # to run --report-only. Now that every fence is claimed, a NEW unclaimed fence is a real defect
    # and it is exactly one line of work to fix: name the law it serves in _FENCE_OWNERS. If no law
    # covers it, that is the finding -- either the fence is unvoted complexity, or the constitution
    # is missing a principle the fence already assumes. Both need a decision, not silence.
    return 1 if (m["unenforced"] or m["broken_references"]
                 or m["fences_without_a_principle"]) else 0


if __name__ == "__main__":
    raise SystemExit(main())

```

### scripts\check_miner_runway.py
```python
"""MINER RUNWAY DOCTOR -- why a seat has never produced, not just that it hasn't.

MEASURED STATE 2026-07-29: 6 of 7 frontier regions have ZERO runs EVER. `max_audit`'s ORGANS
table already checks log FRESHNESS, but a never-run organ and a stale organ look identical to it,
and neither answer says WHY -- so the condition persisted while being technically monitored. Worse,
a never-run duty is deliberately exempt from the cadence floor (so brand-new cadence items do not
page), which is exactly how "never executed since being wired" survived from 07-18 (register #29).

This checks the RUNWAY -- everything that must be true BEFORE a seat can produce:
  prompt   the mission prompt file exists and is non-empty
  runner   the shell runner exists
  unit     a committed systemd unit/timer names that runner (or the manifest schedules it)
  creds    an auth credential is present on the box (existence ONLY -- never a value, never a
           prefix; a doctor that prints secrets is a worse defect than the one it diagnoses)
  ran      evidence of ANY run ever, from the organ's own log glob, with its age

STATUS is the diagnosis, and the distinction is the whole point:
  unobservable     THIS HOST CANNOT SEE THE LOGS -- says nothing about the seats (see below)
  ok               produced a REAL log inside its max age
  stub             fired on time and died at birth -> quota/auth/mutex, NOT a cadence problem
  superseded       another seat does this work now -> forgiven ONLY while that seat is healthy
  superseder-broken the seat that absorbed this one is itself failing -> ONE repair, N grounds
  stale            produced before, not recently  -> a runtime failure, look at the log
  never-ran        runway complete, zero output   -> scheduling/quota, not configuration
  creds-missing    cannot possibly run            -> a HUMAN step, and the real blocker today
  not-scheduled    nothing would ever invoke it   -> a wiring defect in the repo
  missing-prompt   configuration incomplete

OBSERVABILITY IS CHECKED FIRST (2026-08-01). data/cro_ai_logs is gitignored and VPS-local, so
running this from a dev clone or an agent container finds no logs AND no credential -- and the
old ladder then reported "creds-missing" for all eleven seats. That is a verdict about the HOST
wearing the costume of a verdict about the DESK. It cost real confusion: a reader concluded the
miners had never run, while docs/research/deep_sweep/20260801_*.md sat in the same repo as proof
that they had. Config facts (prompt/runner/unit) come from the repo and are true anywhere; every
RUN fact needs the logs, and when they are absent this now says so instead of guessing.

Exit code is nonzero when any seat is creds-missing / never-ran / not-scheduled / unobservable,
so this is cron-able as a pager check on the box. --report-only always exits 0.

    python scripts/check_miner_runway.py [--json] [--report-only]
"""

from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parent.parent
_LOGDIR = _ROOT / "data/cro_ai_logs"
_OUT = _ROOT / "data/miner_runway.json"

# Credentials: EITHER path arms every claude organ (brain_env walks the chain), so this is an
# any-of check. Values are never read -- existence only.
_CRED_ANY = ("data/secrets/claude_oauth_token", "data/secrets/anthropic_api_key")
_CRED_HOME = Path.home() / ".claude/.credentials.json"

# seat -> (prompt, runner, log glob, max_age_h).
#
# THE MAX AGE HERE IS VESTIGIAL AND KEPT ONLY AS A FALLBACK. Both this column and the byte
# floor live in `max_audit.ORGANS`, and the previous version of this comment said the max ages
# "mirror" that table -- which is exactly the restate-instead-of-import defect the promotion
# protocol names. Mirroring copied ONE of the two columns: `ORGANS` carries
# `(glob, min_bytes_for_success, max_age_h)` and this table took only the age, so a seat that
# fired on schedule and produced a 118-byte stub graded `ok` on freshness alone.
#
# MEASURED 2026-08-26, and it is the arrivals collapse in one row: frontier-ru read
# `status: ok` on `frontier_ru_20260825T1603.log`, whose ENTIRE content is an "attempt" line
# and a "start" line. The dig never produced. Five frontier regions had been in that state for
# days while this fence, `seats_productive` and the capability ratchet all read survivable, and
# arrivals fell to 24/week against a 160/week baseline with no liveness gauge going red.
# `ops/run_frontier_rotation.sh` has enforced the same 1500-byte bar the whole time (its resume
# rule is `-size +1500c`, "a stub does not count, per the outcome-not-config law") -- the number
# was never in doubt, it just was not imported.
#
# The join key is the GLOB, not the seat name: the two tables name the same organs differently
# (`dataaxis` here, `dataaxis-dig` there) but agree exactly on the log pattern. A glob that
# stops matching does not silently fall back to a default -- it is recorded in `table_drift`
# and the seat cannot be graded on size (L1.28a: UNMEASURED is a real answer).
_SEATS: dict[str, tuple[str, str, str, float]] = {
    "frontier-en": ("ops/frontier_en_prompt.txt", "ops/run_frontier_miner.sh",
                    "frontier_en_*.log", 36.0),
    "frontier-cn": ("ops/frontier_cn_prompt.txt", "ops/run_frontier_miner.sh",
                    "frontier_cn_*.log", 36.0),
    "frontier-ru": ("ops/frontier_ru_prompt.txt", "ops/run_frontier_miner.sh",
                    "frontier_ru_*.log", 36.0),
    "frontier-kr": ("ops/frontier_kr_prompt.txt", "ops/run_frontier_miner.sh",
                    "frontier_kr_*.log", 36.0),
    "frontier-jp": ("ops/frontier_jp_prompt.txt", "ops/run_frontier_miner.sh",
                    "frontier_jp_*.log", 36.0),
    "frontier-ar": ("ops/frontier_ar_prompt.txt", "ops/run_frontier_miner.sh",
                    "frontier_ar_*.log", 36.0),
    "frontier-br": ("ops/frontier_br_prompt.txt", "ops/run_frontier_miner.sh",
                    "frontier_br_*.log", 36.0),
    # THE SEAT THAT REPLACED THE SEVEN ABOVE. 53c55b8e deleted the REGIONS loop from
    # ops/run_frontier_rotation.sh on 2026-08-25; since then this is the only frontier dig any
    # scheduler invokes, and until now it appeared in no liveness table anywhere.
    "frontier-unified": ("ops/frontier_unified_prompt.txt", "ops/run_frontier_miner.sh",
                         "frontier_unified_*.log", 36.0),
    "prospector": ("ops/prospector_dig_prompt.txt", "ops/run_prospector_dig.sh",
                   "prospector_*.log", 216.0),
    "litminer": ("ops/litminer_dig_prompt.txt", "ops/run_litminer_dig.sh",
                 "litminer_*.log", 216.0),
    "dataaxis": ("ops/dataaxis_dig_prompt.txt", "ops/run_dataaxis_dig.sh",
                 "dataaxis_*.log", 96.0),
    "blindrediscovery": ("ops/blindrediscovery_dig_prompt.txt",
                         "ops/run_blindrediscovery_dig.sh",
                         "blindrediscovery_*.log", 840.0),
}

#: THE ONE PLACE THE BAR IS DEFINED. Imported, never restated -- `max_audit.ORGANS` is the
#: table both fences already agree is authoritative, and importing it makes drift impossible
#: rather than merely discouraged. Import failure is not a licence to default: the seats are
#: then ungradeable on size and say so.
#:
#: ARTIFACT PARITY COMES WITH IT, and leaving it out was a defect this fence nearly shipped.
#: A claude organ writes its deliverables through FILE TOOLS, so a completely successful run can
#: leave nothing in the shell log but a start line -- litminer's 686-byte log on 2026-08-25 was
#: a real dig that minted two cards and four ledger rows. Grading on bytes alone called it a
#: stub. A fence that is wrongly red gets switched off, which is the exact failure this fence
#: exists to prevent, so the byte floor is only consulted when the organ's own EXCLUSIVE declared
#: artifact has ALSO gone quiet past its cadence. `_artifact_age_h` is imported rather than
#: reimplemented for the same reason the byte floor is: max_audit already computes exclusivity
#: (a `prospector_coverage.md` that eight organs write is not evidence any ONE of them ran), and
#: a second copy of that logic is a second thing to drift.
try:
    from scripts.max_audit import ORGANS as _ORGANS
    from scripts.max_audit import SUPERSEDED_BY as _SUPERSEDED_SRC
    from scripts.max_audit import _artifact_age_h as _organ_artifact_age_h
except ImportError:  # pragma: no cover - defensive; the artifact records the blindness
    _ORGANS = {}
    _SUPERSEDED_SRC = {}
    _organ_artifact_age_h = None  # type: ignore[assignment]

#: glob -> min bytes that count as a REAL run, joined from the shared table.
_MIN_BYTES: dict[str, int] = {glob: int(mb) for glob, mb, _age in _ORGANS.values()}
#: glob -> max_audit's name for the same organ, so the artifact escape resolves too. The two
#: tables disagree on names (`litminer` here, `litminer-dig` there) and agree on globs.
_ORGAN_BY_GLOB: dict[str, str] = {glob: name for name, (glob, _mb, _a) in _ORGANS.items()}


#: seat -> the seat that now does its work. NOT a deletion, and the difference is the whole
#: point. Removing these five rows would shrink the denominator until the fence went green,
#: which is the trick LAWS §2a forbids by name; leaving them as daily reds trains every reader
#: to ignore this fence, which is how the desk lost six days to a cron outage nobody escalated.
#:
#: A superseded seat therefore KEEPS ITS ROW AND INHERITS ITS OBLIGATION: it is only forgiven
#: while the seat that absorbed it is itself healthy. If `frontier-unified` breaks, all seven
#: regional grounds go bad WITH it, in one place, naming the one repair that fixes all of them
#: -- which is the report the desk actually wants and could not previously produce.
#:
#: MEASURED 2026-08-26: nothing has invoked `run_frontier_miner.sh <region>` since 08-25, so
#: these globs will never receive another byte. The unified dig's own log blamed the silence on
#: "the seat auth has been down since 08-21" and called it the single largest suppressor of the
#: desk's arrival rate -- but auth pings OPEN (PING-OK on claude-opus-5), and prospector,
#: dataaxis and the unified dig all produced real logs today. The organ diagnosed an
#: infrastructure outage from log ages without reading its own launcher.
#: IMPORTED, not restated -- the same rule as the byte floor and the artifact age. It lives in
#: max_audit beside ORGANS so both fences retire an organ on the same evidence on the same day.
_SUPERSEDED_BY: dict[str, str] = dict(_SUPERSEDED_SRC)

_BAD = ("creds-missing", "never-ran", "not-scheduled", "missing-prompt", "unobservable",
        "stub", "superseder-broken")
#: "stub" is BAD, and it is the rung this ladder was missing. A seat dying at birth every day is
#: strictly worse than a stale one: it is consuming its slot, its quota and its mutex turn while
#: producing nothing, and it renews its own freshness stamp each time it does so.
#: "unobservable" is BAD on purpose. A run that cannot see the logs has not verified anything, and
#: exiting 0 would let a green check stand in for a check that never happened.


def _creds_present() -> bool:
    if _CRED_HOME.exists():
        return True
    if any((_ROOT / p).exists() for p in _CRED_ANY):
        return True
    return bool(os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("CLAUDE_CODE_OAUTH_TOKEN"))


def _scheduled(runner: str) -> bool:
    """A runner is scheduled if a committed systemd unit invokes it, or the crontab manifest does.
    Both are in-repo evidence -- the point of gap #58 was that live-only scheduling is invisible."""
    name = Path(runner).name
    for unit in (_ROOT / "ops").glob("*.service"):
        if name in unit.read_text("utf-8", errors="ignore"):
            return True
    # The frontier rotation wrapper invokes the per-region runner; treat that as scheduling too.
    for wrapper in (_ROOT / "ops").glob("run_*rotation*.sh"):
        if name in wrapper.read_text("utf-8", errors="ignore"):
            for unit in (_ROOT / "ops").glob("*.service"):
                if wrapper.name in unit.read_text("utf-8", errors="ignore"):
                    return True
    manifest = _ROOT / "ops/crontab.manifest"
    return manifest.exists() and name in manifest.read_text("utf-8", errors="ignore")


def _last_run(glob: str) -> tuple[str | None, float | None, int | None]:
    try:
        logs = sorted(_LOGDIR.glob(glob), key=lambda p: p.stat().st_mtime)
    except OSError:
        return None, None, None
    if not logs:
        return None, None, None
    last = logs[-1]
    return last.name, (time.time() - last.stat().st_mtime) / 3600.0, last.stat().st_size


def audit() -> dict[str, Any]:
    # OBSERVABILITY FIRST -- this check is worthless, and worse than worthless, when it cannot see
    # the run history. data/cro_ai_logs is VPS-local and gitignored, so running this anywhere else
    # (a dev clone, a CI box, an agent container) finds no logs AND no credentials, and the old
    # ladder then reported "creds-missing" for all eleven seats. That is a verdict about the
    # MACHINE masquerading as a verdict about the DESK, and on 2026-08-01 it convinced a reader
    # that eleven working seats had never run -- while docs/research/deep_sweep/20260801_*.md sat
    # in the same repo as proof they had.
    observable = _LOGDIR.is_dir()
    creds = _creds_present()
    seats: dict[str, Any] = {}
    drift: list[str] = []
    for seat, (prompt, runner, glob, max_age_h) in _SEATS.items():
        p, r = _ROOT / prompt, _ROOT / runner
        prompt_ok = p.exists() and p.stat().st_size > 0
        runner_ok = r.exists()
        sched = _scheduled(runner)
        name, age_h, size = _last_run(glob)
        min_bytes = _MIN_BYTES.get(glob)
        organ = _ORGAN_BY_GLOB.get(glob)
        art_h = (_organ_artifact_age_h(organ)
                 if organ and _organ_artifact_age_h is not None else float("inf"))
        if min_bytes is None:
            drift.append(f"{seat}: glob {glob!r} is absent from max_audit.ORGANS -- this seat "
                         "cannot be graded on output size")

        if not observable:
            # BEFORE every other verdict. Config facts (prompt/runner/unit) are read from the repo
            # and stay true anywhere; RUN facts are not knowable without the log directory. Saying
            # anything about whether a seat ran, from a box that cannot see its logs, is a guess.
            status = "unobservable"
        elif not prompt_ok:
            status = "missing-prompt"
        elif not runner_ok or not sched:
            status = "not-scheduled"
        elif not creds:
            # Ordered deliberately BEFORE never-ran: with no credentials the seat CANNOT run, so
            # reporting "never-ran" would name the symptom and hide the cause (register #89's
            # lesson -- group by blocker, report the cause with its blast radius).
            status = "creds-missing"
        elif name is None:
            status = "never-ran"
        elif (min_bytes is not None and size is not None and size < min_bytes
              and art_h > max_age_h):
            # BEFORE the age check, deliberately. A FRESH stub is the worse condition: the seat
            # is firing exactly on schedule and dying every time, so grading it on age would
            # report `ok` on the day it is failing hardest -- which is what it did.
            #
            # AND the artifact clause, because a tiny log is ambiguous on its own: it is the
            # signature of a dead run AND of a healthy claude organ that wrote its deliverable
            # through file tools. Only when BOTH the log and the organ's exclusive artifact have
            # gone quiet is "it produced nothing" a measurement rather than a guess. Organs with
            # no exclusive artifact (every frontier seat -- they all write the shared
            # prospector_coverage.md) fall back to bytes: weaker, but honest.
            status = "stub"
        elif age_h is not None and age_h > max_age_h:
            status = "stale"
        else:
            status = "ok"
        seats[seat] = {"prompt": prompt_ok, "runner": runner_ok, "unit": sched, "creds": creds,
                       "last_run": name, "age_h": round(age_h, 1) if age_h is not None else None,
                       "last_bytes": size, "min_bytes": min_bytes,
                       "artifact_age_h": (None if art_h == float("inf") else round(art_h, 1)),
                       "max_age_h": max_age_h, "status": status}

    # THE SUPERSEDE PASS, and it runs AFTER every seat has its own verdict so the superseder's
    # real state is known. A superseded seat is forgiven only while its superseder is healthy;
    # the moment the superseder goes bad, every ground it absorbed goes bad with it and names
    # the single repair that fixes all of them.
    for seat, sup_name in _SUPERSEDED_BY.items():
        row = seats.get(seat)
        if row is None:
            continue
        sup_row = seats.get(sup_name)
        if sup_row is None:
            # The superseder is not even in the table: the retirement pointed at nothing, which
            # is strictly worse than no retirement. Never silently forgiven.
            row["status"] = "superseder-broken"
            row["covered_by"] = f"{sup_name} (ABSENT from this table)"
            continue
        row["covered_by"] = sup_name
        if sup_row["status"] in _BAD:
            row["status"] = "superseder-broken"
        else:
            row["status"] = "superseded"

    by_status: dict[str, list[str]] = {}
    for seat, row in seats.items():
        by_status.setdefault(str(row["status"]), []).append(seat)
    blockers = []
    if not observable:
        blockers.append({
            "blocker": f"log directory {_LOGDIR} is absent -- run history is UNREADABLE here",
            "human_step": "run this ON the box that owns the logs; it is gitignored and local",
            "blast_radius": len(seats),
            "note": "this report says NOTHING about whether the seats ran. Config facts below "
                    "(prompt/runner/unit) are read from the repo and remain true anywhere; every "
                    "RUN fact is unknown. On 2026-08-01 the previous version reported "
                    "'creds-missing' for all eleven seats from a box that simply could not see "
                    "them, and a reader concluded the miners had never run while that same repo "
                    "held today's dig output."})
    if not creds:
        blockers.append({"blocker": "no claude credential on this host",
                         "human_step": "bash ops/setup_brain_token.sh (or setup_brain_api_key.sh)",
                         "blast_radius": len([s for s, r in seats.items()
                                              if r["status"] == "creds-missing"]),
                         "note": "ONE human step unblocks every seat counted here -- reported as "
                                 "a cause, not as N unrelated dead organs"})
    if drift:
        # A join that stops joining must be LOUD. Silently defaulting the byte floor would
        # restore exactly the blindness this change removed, and it would do it invisibly.
        blockers.append({"blocker": "the shared organ table no longer covers every seat",
                         "human_step": "reconcile scripts/max_audit.py ORGANS with _SEATS",
                         "blast_radius": len(drift),
                         "note": "; ".join(drift)})
    return {"checked": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "observable": observable, "log_dir": str(_LOGDIR),
            "creds_present": creds, "seats": seats, "by_status": by_status,
            "blockers": blockers, "table_drift": drift,
            "n_bad": sum(1 for r in seats.values() if r["status"] in _BAD)}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--report-only", action="store_true",
                    help="always exit 0 (record the state without failing a cron)")
    args = ap.parse_args()
    rep = audit()
    _OUT.parent.mkdir(parents=True, exist_ok=True)
    _OUT.write_text(json.dumps(rep, indent=2), "utf-8")
    if args.json:
        print(json.dumps(rep, indent=2))
    else:
        print(f"miner runway | creds={'present' if rep['creds_present'] else 'MISSING'} "
              f"| {rep['n_bad']} of {len(rep['seats'])} seats cannot produce")
        for seat, row in rep["seats"].items():
            age = f"{row['age_h']}h" if row["age_h"] is not None else "never"
            print(f"  {row['status']:14} {seat:18} prompt={int(bool(row['prompt']))} "
                  f"runner={int(bool(row['runner']))} sched={int(bool(row['unit']))} "
                  f"last={age}")
        for b in rep["blockers"]:
            print(f"  BLOCKER: {b['blocker']} -> {b['human_step']} "
                  f"(unblocks {b['blast_radius']} seats)")
    return 0 if args.report_only else (1 if rep["n_bad"] else 0)


if __name__ == "__main__":
    raise SystemExit(main())

```

### scripts\mine_research_queue.py
```python
"""Daily research miner: discover candidate quant sources, rank them, queue what to read.

WHAT IT DOES AND WHAT IT CANNOT, both measured from this box on 2026-08-01 rather than assumed.

    YouTube channel listings   REACHABLE -- video ids + titles parse out of the page (23/23 for
                               one channel)
    YouTube captions           BLOCKED -- no `captionTracks` in the watch page, api/timedtext
                               returns 0 bytes, youtube-transcript-api raises RequestBlocked.
                               Datacenter-IP block; retrying does not fix it.
    Xueqiu (雪球)              REACHABLE -- 110KB of real content with an embedded JSON payload
    Baidu                      BLOCKED -- returns a 1.5KB anti-bot shell, not results
    Zhihu (知乎)               BLOCKED -- HTTP 403
    Bilibili search API        BLOCKED -- HTTP 412 (WBI request signing required)
    JoinQuant / BigQuant /     REACHABLE but JS-rendered shells; the listings need a browser.
    RiceQuant / MyQuant        Chromium is available in this environment for that.

So this miner does NOT fetch transcripts and does not pretend to. It solves the part that is
actually expensive for a human: deciding WHICH of several hundred videos is worth reading. One
channel in this batch had 559 videos and the desk's own record shows most of them would convert
nothing.

EVERY SOURCE RECORDS ITS OWN STATUS. A source that fails is written into the report as BLOCKED
with the reason, never skipped silently -- the 2026-08-01 batch produced a report saying "OKX
BLOCKED, HTTP 403" that turned out to be a User-Agent bot-filter, and an honestly recorded WRONG
diagnosis outlives the outage it describes (lesson L0052).

THE LEDGER MAKES IT DAILY. Seen video ids are appended, so each run surfaces only what is NEW.
Without it a daily job re-reports the same backlog forever and gets ignored within a week.
"""

from __future__ import annotations

import argparse
import json
import re
import time
import urllib.error
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from libs.data import bilibili, cn_sources, foreign_sources, papers
from libs.research import conversion_ledger, source_health
from libs.research.video_triage import SURFACE_THRESHOLD, score_title, triage

_ROOT = Path(__file__).resolve().parent.parent
_OUT = _ROOT / "reports" / "research_queue.json"
_LEDGER = _ROOT / "data" / "research_queue_seen.json"

_UA = {"User-Agent": ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                      "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"),
       "Accept-Language": "en-US,en;q=0.9,zh-CN;q=0.8"}

#: Channels whose output has actually converted on this desk, plus near neighbours. Ordered by
#: measured conversion: neurotrader and Algovibes produced essentially everything that shipped
#: from the 2026-08-01 batch.
YOUTUBE_CHANNELS = (
    "@neurotrader888",
    "@Algovibes",
    "@quantprogram",
    "@TheTransparentTrader",
    "@PartTimeLarry",
    "@quantopian",
)

#: Chinese-language sources. Only the ones measured reachable are enabled; the rest are declared
#: here WITH their block reason so the next reader does not re-diagnose them.
CN_SOURCES: tuple[dict[str, str], ...] = (
    {"name": "xueqiu", "url": "https://xueqiu.com/", "status": "enabled"},
    {"name": "baidu", "url": "https://www.baidu.com/s?wd=%E9%87%8F%E5%8C%96%E4%BA%A4%E6%98%93",
     "status": "blocked", "reason": "returns a ~1.5KB anti-bot shell rather than results"},
    {"name": "zhihu", "url": "https://www.zhihu.com/search?q=%E9%87%8F%E5%8C%96",
     "status": "blocked", "reason": "HTTP 403 to unauthenticated requests"},
    {"name": "bilibili", "url": "https://api.bilibili.com/x/web-interface/search/type",
     "status": "blocked", "reason": "HTTP 412 -- search API requires WBI request signing"},
    {"name": "joinquant", "url": "https://www.joinquant.com/", "status": "needs_browser",
     "reason": "reachable but JS-rendered; listings require Chromium"},
    {"name": "bigquant", "url": "https://bigquant.com/", "status": "needs_browser",
     "reason": "reachable but JS-rendered; listings require Chromium"},
    {"name": "ricequant", "url": "https://www.ricequant.com/", "status": "needs_browser",
     "reason": "reachable but JS-rendered; listings require Chromium"},
)


def _get(url: str, *, timeout: float = 30.0) -> str:
    req = urllib.request.Request(url, headers=_UA)
    with urllib.request.urlopen(req, timeout=timeout) as fh:
        body: str = fh.read().decode("utf8", errors="ignore")
    return body


def fetch_channel(handle: str) -> tuple[list[tuple[str, str]], str | None]:
    """(video_id, title) pairs from a channel's /videos page, or (…, error).

    IDS AND TITLES COME FROM THE SAME BLOCK, never from two independent lists. A misaligned
    pairing would attach the wrong title to every id and the queue would rank nonsense while
    looking perfectly healthy -- the worst class of bug this miner could have, because the output
    stays plausible.

    PARSES `lockupViewModel`, which is the CURRENT layout. YouTube previously emitted
    `videoRenderer` blocks and this parser was written against those; on 2026-08-01 the page
    served zero of them and 24 lockupViewModels, so an earlier version reported every channel as
    blocked. Both shapes are tried, newest first, and a page that yields neither is reported as a
    LAYOUT CHANGE rather than a network failure -- they need completely different fixes and
    conflating them wastes the next reader's time.
    """
    try:
        html = _get(f"https://www.youtube.com/{handle}/videos", timeout=40)
    except Exception as exc:
        return [], f"{type(exc).__name__}: {str(exc)[:140]}"
    return _parse_listing(html)


def _parse_listing(html: str) -> tuple[list[tuple[str, str]], str | None]:
    out: list[tuple[str, str]] = []
    seen: set[str] = set()

    # Current layout: {"lockupViewModel":{"contentId":"<id>", ... "title":{"content":"<title>"}}}
    for block in re.split(r'"lockupViewModel":', html)[1:]:
        # NO WINDOW. An earlier version searched only the first 4,000 chars of each block and
        # found nothing: a lockup carries several thumbnail URLs before it reaches contentId, so
        # the id routinely sits past that. The split already bounds each block to one video.
        vid = re.search(r'"contentId":"([\w-]{11})"', block)
        title = re.search(r'"title":\{"content":"((?:[^"\\]|\\.)*)"', block)
        if vid and title and vid.group(1) not in seen:
            seen.add(vid.group(1))
            out.append((vid.group(1), _unescape(title.group(1))))

    if not out:  # Legacy layout, kept so an older cached page still parses.
        for block in re.findall(r'"videoRenderer":\{(.*?)"navigationEndpoint"', html, flags=re.S):
            vid = re.search(r'"videoId":"([\w-]{11})"', block)
            title = re.search(r'"title":\{"runs":\[\{"text":"((?:[^"\\]|\\.)*)"\}\]', block)
            if vid and title and vid.group(1) not in seen:
                seen.add(vid.group(1))
                out.append((vid.group(1), _unescape(title.group(1))))

    if not out:
        return [], ("LAYOUT CHANGE: page fetched but neither lockupViewModel nor videoRenderer "
                    "blocks parsed. This is a parser fix, not a network problem.")
    return out, None


def _unescape(raw: str) -> str:
    try:
        decoded: str = json.loads(f'"{raw}"')
        return decoded
    except json.JSONDecodeError:
        return raw


#: Search queries run EVERY day so the miner is not limited to a hand-picked channel list. The
#: desk's whole problem with a fixed list is that it can only ever re-find what someone already
#: knew about; search is what makes the miner exploratory. Multilingual on purpose -- the
#: Chinese-language quant scene publishes to YouTube too, and those results never surface from
#: English queries.
#: WIDENED 6 -> 24 on 2026-08-05. Bilibili is the ONLY mined source clearing its weight: on the
#: 2026-08-05 sweep it produced 15 of the 31 new above-threshold rows, while Juejin returned 0 new
#: from 80 fetched. So depth and breadth go HERE rather than into more frequency everywhere -- the
#: other sources are publication-rate-limited (arXiv announces once a weekday; polling it four
#: times cannot mint papers), whereas B站 has a genuinely deep back-catalogue that query breadth,
#: not poll rate, is what reaches.
#: The terms are deliberately spread across STRATEGY CLASS (arb/HFT/market-making/CTA/
#: trend/mean-reversion/options), VALIDATION vocabulary (out-of-sample, walk-forward, overfit),
#: FACTOR work, the MT5 UNIVERSE (gold/XAU, FX, metals, indices, energy), the MT5-NATIVE
#: MECHANISM register (COT positioning, carry/swap, session structure, SMC/ICT liquidity), and
#: PRACTITIONER framing (live-traded, fund-side) -- because a query set clustered in one register
#: returns one corpus repeatedly, which is the same redundancy trap L1.49 names for candidates:
#: breadth of SEARCH, not volume of fetching, is what finds something new.
#:
#: MT5 UNIVERSE MANDATE (2026-08-18). The desk's market is the full MT5/Fusion universe, and NO
#: crypto-exchange universe (Binance/Bybit/OKX/Hyperliquid) is hunted any longer. Every
#: crypto-exchange-native query (perpetual funding, on-chain, cross-exchange arb, liquidation
#: cascades, miner sell-pressure) was removed here on that date; what stayed is universe-neutral
#: (validation, microstructure, factor work transfer to any market) and what replaced them targets
#: gold, FX, metals, indices, energy and the MT5-native mechanisms.
BILIBILI_QUERIES = (
    "量化交易 策略",
    "量化 回测 python",
    "量化投资 因子",
    "程序化交易 策略",
    "期货 量化 策略",
    # validation vocabulary -- the desk's highest-converting register (L0038)
    "量化 样本外 测试",
    "量化 过拟合",
    "策略 回测 陷阱",
    "walk forward 量化",
    # strategy classes (universe-neutral -- these transfer to any market)
    "网格交易 策略",
    "统计套利 策略",
    "高频交易 策略",
    "做市 策略",
    "CTA 趋势跟踪",
    "均值回归 策略",
    "期权 波动率 策略",
    # factor / alpha work
    "多因子模型 选股",
    "因子 有效性 检验",
    # practitioner framing
    "量化 实盘 复盘",
    "私募 量化 研究",
    # microstructure and execution, where cost decides the verdict
    "订单簿 深度 分析",            # order-book depth -- the desk records L2 and never searched it
    "滑点 冲击成本 实测",          # measured slippage / impact cost
    "波动率 择时 模型",            # vol timing
    "回测 幸存者偏差",             # survivorship bias -- VALIDATION register
    # MT5 UNIVERSE (2026-08-18). Replaces the crypto-exchange-native block (perp funding, cross-
    # exchange arb, liquidation cascades, on-chain, miner sell-pressure) removed on that date.
    # Territory, not synonyms: gold, FX, metals, indices, energy, and the MT5-native mechanisms.
    "黄金 交易 策略 回测",          # gold strategy, backtested
    "黄金 xauusd 分析",            # gold / XAUUSD
    "外汇 交易 策略 回测",          # forex strategy, backtested
    "外汇 ea 智能交易系统",         # forex expert advisors
    "mt5 智能交易 编写",           # writing MT5 EAs
    "贵金属 白银 交易 策略",        # silver / precious metals
    "股指期货 交易 策略",          # equity-index futures
    "原油 期货 交易 策略",          # crude / energy
    "ict 流动性 交易 结构",         # ICT liquidity / market structure
    "订单块 公允价值缺口 交易",     # order block / FVG
    "cot 持仓 报告 分析",          # COT positioning -- the whale-tracking analogue for MT5
    "套息 交易 利差 策略",          # carry trade / rate differential -- the funding analogue
    "外汇 隔夜利息 掉期 策略",      # swap / rollover carry
    "期货 基差 收敛 交易",          # futures basis convergence (gold/index futures, generic)
    "外汇 时段 伦敦 纽约 策略",     # session structure -- first-class in a non-24/7 universe
    "非农 数据 外汇 交易",          # NFP / macro-event reaction
    "美元指数 交易 策略",          # DXY
    # SECRET-SAUCE REVEALS (2026-08-20, principal: "mine strategies not bs"). Validation-vocabulary
    # queries above convert on volume but mostly BLOCKED_PENDING_DATA in practice -- they surface
    # commentary ABOUT testing, not a reproducible rule to test. This block targets titles that name
    # a specific, codeable system: parameters, entry/exit rules, source code, or a named trader's
    # disclosed method -- the highest-value class edge_intake.classify() can actually convert.
    "ea 参数 设置 详解",            # EA parameter settings, explained in detail
    "策略 源码 公开",              # strategy source code, made public
    "交易系统 完整 规则",           # complete trading system rules
    "跟单 高手 策略 拆解",          # top copy-trader's strategy, broken down
    "顶级 交易员 策略 揭秘",        # top trader's strategy, revealed
    "ea 回测 参数 优化",            # EA backtest, parameter optimisation
    "黄金 ea 参数 公开",            # gold EA, parameters disclosed
    "mql5 信号源 策略 分析",        # MQL5 Signals -- a public copy-trading leaderboard
)

# 4 -> 22 (2026-08-05). THE HIGHEST-YIELDING FAMILY HAD THE NARROWEST SWEEP, which is exactly
# backwards. Bilibili carried 24 queries while the ARTICLE sources carried 4 -- and on 2026-08-05
# WeChat/Juejin supplied 3 of the 5 new rows INCLUDING THE TOP THREE BY SCORE (18.0/13.0/9.0).
# Article sources also carry what video cannot: a procedure written down, which is the form the
# desk's own conversion record says actually converts.
#
# WIDTH HERE IS TERRITORY, NOT SYNONYMS. Four rephrasings of "quant backtest" return one forest
# four times; each line below is a DIFFERENT economic or operational subject, chosen so a single
# platform's SEO cluster cannot satisfy several at once. The order runs from the desk's confirmed
# edge outward toward material it has never indexed.
#
# PACED, because breadth that kills a lane is not breadth. Sogou rate-limits hard and answers an
# anti-bot page when pushed; cn_sources.sogou_weixin already reports that verdict rather than
# mistaking it for an empty result, and the loop's inter-query sleep is raised alongside this so
# 22 queries do not arrive faster than 4 did. L1.54: the point is to keep the door open, not to
# prove it can be slammed.
CN_ARTICLE_QUERIES = (
    # -- validation and self-deception: the class the desk's own record says converts
    "量化 回测 陷阱",
    "量化策略 过拟合",
    "样本外 检验 失效",
    "幸存者偏差 回测",
    "未来函数 前视偏差",
    # -- factor work
    "因子 挖掘 回测",
    "因子 失效 衰减",
    "多因子 组合 优化",
    # -- MT5 universe (2026-08-18): replaces the crypto-exchange-native edge block (funding-rate
    # arb, perp mechanics, cross-exchange arb) with the desk's real market and its analogues.
    "黄金 交易 策略 实盘",          # gold, live-traded
    "外汇 套息 利差 交易",          # FX carry -- the funding-rate analogue
    "期货 基差 收敛 套利",          # futures basis (gold/index), generic
    "cot 持仓 报告 交易 信号",      # COT positioning as a signal
    # -- microstructure and execution, where cost decides the verdict
    "做市 策略 库存 风险",
    "高频 交易 撮合 机制",
    "滑点 冲击成本 测算",
    "限价单 排队 优先级",
    # -- mechanisms the taxonomy names and the miner never asked about
    "止损 猎杀 流动性 扫单",        # stop-hunt / liquidity sweep -- the MT5 forced-flow analogue
    "期权 波动率 曲面 套利",
    "外汇 时段 波动 结构",          # session-structured volatility
    "央行 利率 决议 交易",          # central-bank rate decisions -- the macro-event desk
    # -- the honest failure literature, which is where the graveyard entries live
    "网格 马丁 爆仓 复盘",
    "实盘 与 回测 差异",
    # -- SECRET-SAUCE REVEALS (2026-08-20): named, reproducible systems, not validation commentary
    "ea 源码 策略 详解",
    "交易系统 入场 出场 规则",
    "跟单 策略 拆解 分析",
)

SEARCH_QUERIES = (
    # universe-neutral methodology -- the desk's highest-converting register, transfers to any market
    "quantitative trading backtest python",
    "algorithmic trading strategy tested",
    "backtested trading strategies statistical",
    "walk forward analysis trading",
    "monte carlo permutation test trading",
    "overfitting trading strategy validation",
    # MT5 universe (2026-08-18): "crypto quant strategy research" removed -- the desk hunts FX,
    # gold, metals, indices, energy now, and crypto-exchange research is no longer a target.
    "XAUUSD gold trading strategy backtest",
    "forex algorithmic trading walk forward",
    "MT5 expert advisor strategy backtest",
    "COT report positioning trading strategy",
    "gold silver trading strategy statistical",
    # multilingual, MT5 universe
    "黄金 外汇 量化 策略 回测",
    "外汇 ea 智能交易 策略",
    "ゴールド 為替 バックテスト 検証",
    "форекс золото стратегия бэктест",
)


def search_youtube(query: str) -> tuple[list[tuple[str, str]], str | None]:
    """(video_id, title) pairs from a YouTube search, using the same parser as a channel page.

    THE SAME PARSER ON PURPOSE. Search results and channel listings share the lockupViewModel
    layout, so one parser fix repairs both -- and if they ever diverge, the channel path fails
    loudly rather than the search path failing silently.
    """
    from urllib.parse import quote
    try:
        html = _get(f"https://www.youtube.com/results?search_query={quote(query)}", timeout=40)
    except Exception as exc:
        return [], f"{type(exc).__name__}: {str(exc)[:140]}"
    return _parse_listing(html)


def probe_cn() -> list[dict[str, Any]]:
    """Reachability of each Chinese source, re-measured every run.

    RE-MEASURED RATHER THAN TRUSTED because a block is a fact about today. The desk has already
    been burned once by treating a recorded HTTP failure as permanent when it was a header
    problem, so the declared status is the PRIOR and the probe is the evidence.
    """
    rows: list[dict[str, Any]] = []
    for src in CN_SOURCES:
        row: dict[str, Any] = {"name": src["name"], "declared": src["status"],
                               "reason": src.get("reason")}
        try:
            body = _get(src["url"], timeout=25)
            row["reachable"] = True
            row["bytes"] = len(body)
            # A tiny body from a search endpoint is an anti-bot shell, not content.
            row["looks_like_content"] = len(body) > 20_000
        except urllib.error.HTTPError as exc:
            row["reachable"] = False
            row["http_status"] = exc.code
        except Exception as exc:
            row["reachable"] = False
            row["error"] = f"{type(exc).__name__}: {str(exc)[:120]}"
        rows.append(row)
        time.sleep(0.4)
    return rows


def _load_seen() -> set[str]:
    if not _LEDGER.exists():
        return set()
    try:
        return set(json.loads(_LEDGER.read_text("utf-8")).get("seen", []))
    except Exception:
        return set()


def _save_seen(seen: set[str]) -> None:
    _LEDGER.parent.mkdir(parents=True, exist_ok=True)
    _LEDGER.write_text(json.dumps({"seen": sorted(seen)}, indent=0), "utf-8")


#: R0088's missing instrument. "Should this miner run more often?" was an OPINION for as long as
#: nobody logged what a run actually returned, and opinions default to "more" because more feels
#: like effort. One run measured by hand on 2026-08-05 settled it instantly: Juejin fetched 80 rows
#: across four queries and produced ZERO new candidates (108 already in the seen-ledger) while
#: Bilibili produced 15 of the 31 new rows. Six-times-a-day was re-reading the same corpus six
#: times. This makes that arithmetic automatic and per-source, so cadence is READ rather than
#: argued -- and so a source that quietly saturates shows up as a falling new/fetched ratio instead
#: of as a full-looking report.
_YIELD_LOG = _ROOT / "data" / "miner_yield.jsonl"

#: Which report key holds the per-query fetch counts for each source group.
#: source GROUP -> the queue-channel prefixes its producers actually write. A group whose name is
#: not itself a producer needs an entry here or its `new_above_threshold` is structurally ZERO
#: forever: the count matches on channel prefix, and "foreign" never appears in a channel because
#: the producers are qiita/zenn/hatena/dcinside/habr. `cn` was special-cased for exactly this and
#: `foreign` was not, so its first three surfaced rows logged as 0 new against 1,601 fetched --
#: a yield of 0.0 on a source that had just produced. This is the instrument CADENCE is read off,
#: so a producing lane reporting zero would argue for cutting the one sweep worth keeping.
def _foreign_producers() -> tuple[str, ...]:
    """The foreign group's producers, READ FROM THE SOURCE REGISTRY rather than restated here.

    This list was hardcoded, and that is precisely how the yield instrument reported a structural
    ZERO for the whole foreign lane once: `foreign` is a GROUP whose queue rows carry per-source
    channels, so a producer missing from the list is a producer whose rows are never counted. The
    lane logged 1,601 fetched / 0 new on a run that had just surfaced three rows, and a producing
    lane reporting nothing forever is an argument to cut the one sweep worth keeping.

    Restating the list was the fix LAST time and it did not survive contact with growth: the moment
    seven more forests were added the copy went stale again. Deriving it means a forest added
    tomorrow is counted the day it is added, with nothing to remember.
    """
    try:
        from libs.data.foreign_sources import SOURCES as _FS
        return tuple(sorted(_FS))
    except Exception:
        return ("qiita", "zenn", "hatena", "dcinside", "habr")


_GROUP_PRODUCERS: dict[str, tuple[str, ...]] = {
    "cn": ("juejin", "wechat"),
    "foreign": _foreign_producers(),
}

_FETCH_KEYS = {"bilibili": "bilibili_discovered", "cn": "cn_article_discovered",
               "search": "search_discovered", "academic": "academic_discovered",
               "youtube": "channels_scanned", "foreign": "foreign_discovered"}


#: Channel-label prefix -> the host a route hunt would actually target. Derived where possible and
#: stated where not: a hunt aimed at "hatena:some query" is aimed at nothing, while one aimed at
#: hatena.ne.jp has named routes (render path, RSS, mirrors, regional hosts).
_CHANNEL_HOSTS: dict[str, str] = {
    "bilibili": "bilibili.com", "juejin": "juejin.cn", "wechat": "weixin.qq.com",
    "qiita": "qiita.com", "zenn": "zenn.dev", "hatena": "hatena.ne.jp",
    "dcinside": "dcinside.com", "habr": "habr.com", "note": "note.com",
    "velog": "velog.io", "coinpan": "coinpan.com", "smartlab": "smart-lab.ru",
    "tinhte": "tinhte.vn", "eksisozluk": "eksisozluk.com", "vcru": "vc.ru",
    "search": "duckduckgo.com",
}


def _open_route_hunts(blocked: dict[str, str]) -> list[dict[str, Any]]:
    """One route-hunt row per blocked HOST. Never raises -- a sweep must survive its bookkeeping."""
    try:
        from libs.data.paywall import record as _record
    except Exception:
        return []
    by_host: dict[str, str] = {}
    for label, reason in (blocked or {}).items():
        host = _CHANNEL_HOSTS.get(str(label).split(":")[0], "")
        if not host:
            continue
        by_host.setdefault(host, str(reason))            # first reason per host is enough
    opened: list[dict[str, Any]] = []
    for host, reason in sorted(by_host.items()):
        # `declared=False` on purpose: a miner block is a ROUTING problem by default, and calling
        # it a paywall would put a WAF into the paid-vendor registry -- the exact pollution the
        # 402/403 split exists to prevent.
        row = _record(f"https://{host}/", status=403,
                      unlocks=f"mined research rows from {host} (blocked: {reason[:90]})")
        opened.append({"host": host, "verdict": row["verdict"], "reason": reason[:120]})
    return opened


def _yield_row(doc: dict[str, Any], *, seen: set[str], only: list[str]) -> dict[str, Any]:
    """Per-source fetched / new-above-threshold for THIS run.

    `new` counts queue rows whose channel carries the source prefix, so it is the number that
    matters -- rows that survived BOTH the seen-ledger and the score threshold. A source can look
    busy on `fetched` and still be worth nothing, which is exactly Juejin's shape and exactly what
    a fetch-count-only report would hide.
    """
    per: dict[str, dict[str, Any]] = {}
    for src, key in _FETCH_KEYS.items():
        counts = doc.get(key) or {}
        if not isinstance(counts, dict):
            continue
        fetched = sum(int(v) for v in counts.values() if isinstance(v, int | float))
        # A GROUP is not a producer. Queue channels are prefixed by whoever wrote the row, so a
        # multi-producer group must name its members or it counts none of them (see
        # _GROUP_PRODUCERS). Falls back to the source's own name, which is correct for the
        # single-producer groups (bilibili, search, academic, youtube).
        prefixes = _GROUP_PRODUCERS.get(src, (src,))
        new = sum(1 for r in doc.get("queue", [])
                  if str(r.get("channel", "")).split(":")[0] in prefixes)
        if fetched == 0 and new == 0 and src not in only and only != ["all"]:
            continue                 # not run this invocation -- absent, not zero (L1.41)
        per[src] = {"fetched": fetched, "new_above_threshold": new,
                    "yield": round(new / fetched, 4) if fetched else None}
    return {"ts": datetime.now(tz=UTC).isoformat(), "only": only,
            "threshold": doc.get("threshold"), "seen_ledger_size": len(seen),
            "n_new_total": len(doc.get("queue", [])), "per_source": per}


def _append_yield(row: dict[str, Any], path: Path | None = None) -> None:
    """Append-only; a reporting failure must never take down the miner that produced the data."""
    p = path if path is not None else _YIELD_LOG
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        with p.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    except OSError:
        pass


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--channels", default=",".join(YOUTUBE_CHANNELS))
    ap.add_argument("--threshold", type=float, default=SURFACE_THRESHOLD)
    ap.add_argument("--all", action="store_true", help="ignore the seen-ledger (full backlog)")
    ap.add_argument("--out", default=str(_OUT))
    # SOURCE SELECTOR (2026-08-05). Sources do NOT deserve equal cadence, because they do not
    # publish at equal rates. arXiv announces once a weekday, so polling it four times cannot
    # mint papers; B站 has a deep back-catalogue that query breadth reaches. Without this flag a
    # dedicated Bilibili run would drag every other source along at Bilibili's cadence, which is
    # exactly the over-polling that took Juejin to 0 new from 80 fetched.
    ap.add_argument("--only", default="", metavar="SRC[,SRC...]",
                    help="restrict to sources: bilibili, cn, foreign, youtube, "
                         "academic, search (default: all)")
    # 3 -> 1, and the number is READ off a like-for-like measurement rather than argued.
    #
    # Bilibili throttles on REQUEST COUNT, and depth is what spends the budget. Measured 2026-08-06
    # on two runs of the same 34 queries, an hour apart:
    #
    #   4 pages/query  ->  ~136 requests, 17 queries productive, 17 SILENTLY REFUSED,   7 new
    #   1 page/query   ->   ~34 requests, 34 queries productive,  0 refused,           43 new
    #
    # The 1-page run went SECOND, against a seen-ledger the 4-page run had already fed, so it faced
    # the strictly harder job -- and still returned 25x more new candidates per request. Three of
    # its queries (因子 有效性 检验, 私募 量化 研究, 回测 幸存者偏差) were among the ones the deep
    # run had refused, and they produced candidates the desk would otherwise never have seen.
    #
    # WHY DEPTH LOSES, and it is not close. Pages 2-4 are the deep tail of ONE query's ranking --
    # mostly the same corpus the seen-ledger already holds, since the ledger is fed by that same
    # query every run. Page 1 of a query the sweep has NOT run is unindexed territory. This is the
    # identical argument BILIBILI_QUERIES already makes for its own width ("breadth of SEARCH, not
    # volume of fetching"), and the depth setting was quietly contradicting it.
    #
    # FALSIFIER: if a 1-page sweep's new-per-request falls below a 2-page sweep's on a like-for-
    # like pair, raise it. Depth is not forbidden, it is currently just the worse buy.
    ap.add_argument("--bili-pages", type=int, default=1, metavar="N",
                    help="Bilibili search pages per query (20 rows/page). Default 1: measured "
                         "25x more new candidates per request than 4, because the source "
                         "throttles on request count and breadth outbuys depth")
    args = ap.parse_args(argv)

    _valid = {"bilibili", "cn", "youtube", "academic", "search", "foreign"}
    only = {s.strip().lower() for s in str(args.only).split(",") if s.strip()}
    unknown = only - _valid
    if unknown:                      # fail loud: a typo'd source must not silently mine nothing
        ap.error(f"unknown --only source(s): {sorted(unknown)}; valid: {sorted(_valid)}")

    def _runs(src: str) -> bool:
        return not only or src in only

    seen = set() if args.all else _load_seen()
    channels = [c.strip() for c in str(args.channels).split(",") if c.strip()]

    queue: list[dict[str, Any]] = []
    blocked: dict[str, str] = {}
    counts: dict[str, int] = {}
    all_ids: set[str] = set()

    # --- Bilibili (B站): WBI-signed search. Scores title+description+tags, which is several
    # times more signal per candidate than a YouTube title alone.
    bili: dict[str, int] = {}
    # BACK OFF FOR THE REST OF THE RUN once the source refuses, exactly as the foreign lane already
    # does for hatena's 429. The 2026-08-06 06:33 sweep pushed 17 further queries into a source
    # that had already started declining -- 68 more signed requests that returned nothing and could
    # only deepen the throttle. Continuing to push a rate limit is how a temporary refusal becomes
    # a durable block (source_health says so in its own threshold comment), and the queries lost
    # here are the TAIL of the list, which is where the newest territory sits.
    bili_refused = ""
    for kw in BILIBILI_QUERIES if _runs("bilibili") else ():
        if bili_refused:
            blocked[f"bilibili:{kw}"] = (
                "bilibili soft-refused earlier in this run -- backed off for the rest of it rather "
                f"than hammering a source that declined ({bili_refused[:90]})")
            continue
        # PAGED. Search returns 20 rows a page and its ranking rotates, so one page re-sampled
        # often is mostly the same corpus seen again; three pages is depth rather than repetition.
        vids: list = []
        err = None
        for pg in range(1, max(1, int(args.bili_pages)) + 1):
            got, e = bilibili.search(kw, page=pg)
            if e:
                # A refusal on page 1 costs the whole query and must be recorded. A refusal on a
                # LATER page keeps the rows already in hand -- but it is still the source declining,
                # so it still arms the backoff. Treating "I got page 1 then it stopped" as a clean
                # run is how the silent-zero defect survived: partial success is not consent.
                err = e if not vids else None
                if "SOFT REFUSAL" in e or "code=" in e:
                    bili_refused = e
                break
            vids.extend(got)
            time.sleep(0.4)
        if err:
            blocked[f"bilibili:{kw}"] = err
            continue
        bili[kw] = len(vids)
        all_ids.update(v.bvid for v in vids)
        for v in vids:
            if v.bvid in seen:
                continue
            s, hits = score_title(v.searchable)
            if s >= args.threshold:
                queue.append({"channel": f"bilibili:{kw}", "video_id": v.bvid,
                              "title": v.title[:160], "score": round(s, 1), "url": v.url,
                              "author": v.author, "views": v.views, "why": hits})
        time.sleep(0.5)

    # --- Chinese article sources: Juejin (掘金) and WeChat via Sogou.
    cn_hits: dict[str, int] = {}
    for kw in CN_ARTICLE_QUERIES if _runs("cn") else ():
        for name, fn in (("juejin", cn_sources.juejin), ("wechat", cn_sources.sogou_weixin)):
            arts, e = fn(kw)
            if e:
                blocked[f"{name}:{kw}"] = e
                continue
            cn_hits[f"{name}:{kw}"] = len(arts)
            for a in arts:
                key = f"{a.source}:{a.ident}"
                all_ids.add(key)
                if key in seen:
                    continue
                s, hits = score_title(a.searchable)
                if s >= args.threshold:
                    queue.append({"channel": f"{a.source}:{kw}", "video_id": key,
                                  "title": a.title[:160], "score": round(s, 1), "url": a.url,
                                  "author": a.author, "why": hits})
            # 1.2s, raised from 0.5 when CN_ARTICLE_QUERIES went 4 -> 22. Sogou rate-limits hard
            # and serves an anti-bot page when pushed, so widening the sweep without slowing it
            # would trade the desk's best-scoring lane for coverage of it.
            time.sleep(1.2)

    # --- NON-CHINESE FOREIGN FORESTS: Japanese, Korean, Russian.
    #
    # A SIBLING OF THE CHINESE LOOP, NOT A SPECIAL CASE. The argument for a Chinese lane -- large,
    # practitioner-authored, invisible to English search -- is language-agnostic, and it was being
    # made for exactly one language while three other crypto-native communities went unindexed.
    # Korean is the sharpest omission: this desk MEASURES the Upbit/Bithumb premium as a mechanism
    # class and had never read a word written by the people creating it.
    #
    # Driven by foreign_sources.SOURCES and .LANGUAGES rather than a hardcoded list, so a fourth
    # language is a table entry and its queries -- never a new branch here.
    foreign_hits: dict[str, int] = {}
    for name, (fn, lang) in (foreign_sources.SOURCES.items() if _runs("foreign") else ()):
        for kw in foreign_sources.LANGUAGES[lang]:
            arts, e = fn(kw)
            if e:
                blocked[f"{name}:{kw}"] = e
                continue
            foreign_hits[f"{name}:{kw}"] = len(arts)
            for a in arts:
                key = f"{a.source}:{a.ident}"
                all_ids.add(key)
                if key in seen:
                    continue
                s_, hits = score_title(a.searchable)
                if s_ >= args.threshold:
                    queue.append({"channel": f"{a.source}:{kw}", "video_id": key,
                                  "title": a.title[:160], "score": round(s_, 1), "url": a.url,
                                  "author": a.author, "why": hits})
            # 1.2s, matching the CN loop. Five sources x ~17 queries is ~85 requests; paced so
            # breadth does not cost the desk a lane it just opened.
            time.sleep(1.2)

    # --- Academic + code. The only sources whose CONTENT is readable: abstracts come back in the
    # API response, so these can produce a finding rather than only a queue entry.
    acad: dict[str, int] = {}
    paper_calls = ([(f"arxiv:{c}", (lambda c=c: papers.arxiv("", category=c, limit=25)))
                    for c in papers.ARXIV_CATEGORIES]
                   + [("ssrn:fin-econ", lambda: papers.ssrn(count=40)),
                      ("openreview", lambda: papers.openreview("quantitative trading")),
                      ("hn", lambda: papers.hackernews("quant trading backtest"))])
    for label, call in paper_calls if _runs("academic") else ():
        items, e = call()
        if e:
            blocked[label] = e
            continue
        acad[label] = len(items)
        for a in items:
            key = f"{a.source}:{a.ident}"
            all_ids.add(key)
            if key in seen:
                continue
            s, hits = score_title(a.searchable)
            if s >= args.threshold:
                queue.append({"channel": label, "video_id": key, "title": a.title[:180],
                              "score": round(s, 1), "url": a.url, "why": hits,
                              "abstract": a.abstract[:400]})
        time.sleep(0.4)

    discovered: dict[str, int] = {}
    for q in SEARCH_QUERIES if _runs("search") else ():
        vids, err = search_youtube(q)
        if err:
            blocked[f"search:{q}"] = err
            continue
        discovered[q] = len(vids)
        all_ids.update(v for v, _ in vids)
        fresh = [(v, t2) for v, t2 in vids if v not in seen]
        for c in triage(fresh, channel=f"search:{q}", threshold=args.threshold):
            queue.append({"channel": f"search:{q}", "video_id": c.video_id, "title": c.title,
                          "score": round(c.score, 1), "url": c.url, "why": list(c.hits)})
        time.sleep(0.8)

    for handle in channels if _runs("youtube") else ():
        vids, err = fetch_channel(handle)
        if err:
            blocked[handle] = err
            continue
        counts[handle] = len(vids)
        all_ids.update(v for v, _ in vids)
        fresh = [(v, t) for v, t in vids if v not in seen]
        for c in triage(fresh, channel=handle, threshold=args.threshold):
            queue.append({"channel": handle, "video_id": c.video_id, "title": c.title,
                          "score": round(c.score, 1), "url": c.url, "why": list(c.hits)})
        time.sleep(0.6)

    # A video can surface from several queries; keep its best-scoring row only.
    best: dict[str, dict[str, Any]] = {}
    for row in queue:
        vid = str(row["video_id"])
        if vid not in best or float(row["score"]) > float(best[vid]["score"]):
            best[vid] = row
    queue = sorted(best.values(), key=lambda r: -float(r["score"]))
    doc = {
        "generated_utc": datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "status": "MEASURED" if counts else "BLOCKED",
        "captions": {
            "available": False,
            "reason": ("every caption path is blocked from this IP: no captionTracks in the watch "
                       "page, api/timedtext returns 0 bytes, youtube-transcript-api raises "
                       "RequestBlocked. Discovery and ranking work; reading does not."),
            "implication": "the queue names what to paste in; it cannot read it",
        },
        "channels_scanned": counts,
        "search_discovered": discovered,
        "bilibili_discovered": bili,
        "cn_article_discovered": cn_hits,
        "foreign_discovered": foreign_hits,
        "foreign_source_probe": foreign_sources.probe_all() if _runs("foreign") else [],
        "cn_source_probe": cn_sources.probe_all(),
        "academic_discovered": acad,
        "academic_probe": papers.probe_all(),
        "github_token_present": papers.github_token() is not None,
        "ranker_calibration": conversion_ledger.calibration(),
        "channels_blocked": blocked,
        # EVERY BLOCK IS ROUTED TO THE ROUTE-HUNT LEDGER, not just printed. A blocked channel that
        # only ever appears in this run's report is a source the desk wanted, could not reach, and
        # then forgot -- which is how a temporary block quietly becomes an accepted loss (L1.54).
        # `unresolved_blocks()` turns each into owed work and max_audit's `blocked-routes` fence
        # escalates it once it outlives a miner cycle. Recorded per HOST, so seventeen blocked
        # queries against one site are one routing problem rather than seventeen.
        "route_hunts_opened": _open_route_hunts(blocked),
        "threshold": args.threshold,
        "n_new_surfaced": len(queue),
        "queue": queue,   # NOT capped: a cap silently hides the tail of a daily backlog
        "cn_sources": probe_cn(),
    }
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=2, ensure_ascii=False), "utf-8")

    yield_row = _yield_row(doc, seen=seen, only=sorted(only) or ["all"])
    _append_yield(yield_row)

    # SOURCE HEALTH. This report already knows which sources worked and which did not; until
    # 2026-08-05 that knowledge died with the file it was written into, so a source could be
    # blocked for weeks, be re-probed every run, report the same failure every run, and never
    # accumulate into anything the desk could act on. One call folds this run's blocked/ok status
    # into an append-only per-source ledger; scripts/hunt_source_alternatives.py reads it and goes
    # looking for in-class substitutes for whatever has been dead N runs running. Purely additive
    # -- it reads the finished report and changes nothing about what was mined.
    source_health.record_from_report(doc)

    # EDGE INTAKE (2026-08-20 port from claude/wonderful-darwin-7uiobi -- was built there and never
    # reached this branch, so this branch's runs produced NEXT_BATCH_TEST/BLOCKED_PENDING_DATA
    # dispositions nowhere: every discovered row aged out of the queue file on the next sweep with
    # no record it had ever existed, gate items 30/34's exact failure mode). NEVER FATAL -- the
    # queue file and seen ledger are already written by this point, and losing the sweep to a
    # ledger error would cost far more than the missing stamps it is complaining about.
    try:
        from libs.research import edge_intake
        stamped = edge_intake.stamp_queue(out)
        print(f"edge intake: {stamped.get('status')} n={stamped.get('n_stamped')} "
              f"{stamped.get('by_disposition') or ''}")
    except Exception as exc:                     # reported, never fatal
        print(f"edge intake FAILED (non-fatal, queue already written): "
              f"{type(exc).__name__}: {exc}")

    if not args.all:
        _save_seen(seen | all_ids)

    print(f"scanned {sum(counts.values())} videos across {len(counts)} channel(s); "
          f"{len(queue)} new above threshold {args.threshold}")
    for r in queue[:12]:
        print(f"  {r['score']:>5.1f}  {r['channel']:<18} {r['title'][:64]}")
    if blocked:
        print(f"BLOCKED channels: {blocked}")
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

```

### scripts\study_promotion_selection_bias.py
```python
#!/usr/bin/env python3
"""R0574 -- does the estimation shrink already absorb the best-of-m PROMOTION winner's curse?

THE QUESTION, AND WHY IT IS THE ONE THAT SURVIVED R0432. R0432 asked whether the screen's
420-trial count should tighten `libs/risk/kelly_shrink.shrink_fraction`. It must not, and that is
decided in that function's own docstring (commit e56c6d95): the shrink is fed `fwd_sharpe` /
`fwd_days` off the pre-registered FORWARD clock (`dynamic_leverage.py:112`), data that took no part
in the screen's selection, so charging the screen's winner's curse there prices one selection twice.

BUT A SMALLER SELECTION IS REAL AND WAS UNPRICED. Promotion picks winners from at most
`MAX_FORWARD_SLOTS = 12` concurrent forward clocks. Holm corrects the p-value of that DECISION
(`run_axis_shadows.py:449`, `auto_promotion.py:147`); nothing de-biases the effect SIZE that
`auto_promotion.py:172` and the sizer then use. A candidate that just cleared the bar therefore
carries an upward-biased forward Sharpe, and that Sharpe is exactly what sizes the book.

THE FIRST VERSION OF THIS STUDY WAS WRONG AND ITS OWN NULL CONTROL CAUGHT IT -- recorded here
because the correction is the reusable part. It compared the desk's sizing against an
empirical-Bayes posterior mean and read the (large) gap as the winner's curse. But promoting a
cohort member AT RANDOM, with no bar and no max-taking and therefore no selection whatever, showed
the same gap: 0.98 of oracle growth. The posterior mean was winning on a second effect entirely --
the desk's prior has a SPIKE AT ZERO (420 screened, 0 survivors) and `S^2/(S^2+SE^2)` shrinks
toward zero using SE alone, never toward that prior. That gain is real but it is NOT selection, and
a study that reported it as selection would have charged one effect for another's sins. The design
below isolates the selection term by construction.

METHOD (one cell = one (m, n_days, prior) triple, all arms on COMMON RANDOM NUMBERS):
  1. m candidates enter a cohort of concurrent forward clocks. Each draws a TRUE annualized Sharpe
     from the desk's prior: with probability `pi` a real edge ~ Exponential(mean `s_edge`),
     otherwise exactly zero.
  2. Each accumulates `n_days` of forward evidence, so the observed Sharpe is
     S_hat ~ Normal(S_true, SE(S_true, n_days)) with Lo's SE -- the same SE the sizer uses.
  3. t = S_hat * sqrt(n_days / 365), the desk's own `forward_stats` convention, is compared against
     `holm_bar(m, rank=1)`. The MAX-t candidate is promoted if it clears. That is the selection.
  4. The promoted sleeve is sized FIVE ways and then earns at its TRUE Sharpe:
       naive     L = S_hat                                   <- no shrink at all, the floor
       desk      L = shrink_fraction(S_hat, n) * S_hat       <- what runs today
       eb_blind  L = E[S_true | S_hat]                       <- posterior mean, SELECTION-BLIND:
                                                                calibrated on ALL candidates
       eb_aware  L = E[S_true | S_hat, promoted]             <- posterior mean, SELECTION-AWARE:
                                                                calibrated on WINNERS only
       oracle    L = S_true                                  <- the ceiling, unreachable
     Realized annualized log-growth at unit vol is L*S_true - L^2/2 (Kelly optimum L = S_true).
     A round promoting nobody earns 0 in every arm: growth per PROMOTION ROUND is the quantity the
     desk cares about, not growth per promoted sleeve.
  5. THE SELECTION TERM IS `eb_aware - eb_blind`. Both arms know the prior; they differ ONLY in
     whether the map conditions on having been selected. Their difference is therefore the
     winner's curse and nothing else. `desk - eb_blind` is the separate prior term, reported
     alongside so the two are never again read as one number.
  6. Both maps are calibrated on an INDEPENDENT draw (different seed) and applied out-of-sample.

PRE-REGISTERED, BEFORE THE RUN:
  * NULL CONTROL -- promote a RANDOM cohort member, no bar, no max-taking. Winners are then an iid
    sample of candidates, so the aware and blind maps are calibrated on the SAME distribution and
    the selection term must vanish: |selection gain| < 1% of oracle growth. This is the control the
    first version failed.
  * POSITIVE CONTROL -- m = 420, the screen's own intensity, where the selection term MUST be large
    and detectable. A method never shown to find a known-present bias has not been validated; only
    its silences would have been observed.
  * VERDICT at the live m = 12, on the SELECTION term:
      paired t < 3.0                      -> ABSORBED (retires the question)
      t >= 3.0 and gain < 1% of oracle    -> ABSORBED-MATERIALLY (detectable, not economic)
      t >= 3.0 and gain >= 1% of oracle   -> CORRECTION-REAL (and the direction is TIGHTER)

SCOPE -- TWO SIZING PATHS EXIST AND THIS STUDY IS ABOUT ONE OF THEM. Checked at the source rather
than assumed, because they carry different constants and reading them as one pipeline is the
same-name-different-question error (L1.61):
  * `dynamic_leverage.optimize_sleeve` -> `shrink_fraction(fwd_sharpe, fwd_days)` (line 112), fed
    for named sleeves by `run_leverage_opt.py`. THIS is the path R0574 asks about and the one the
    `desk` arm models.
  * `auto_promotion.decide` -> `clip` sized from `margin = t / holm_bar` (line 172). Also consumes
    the selected, un-de-biased forward t, but through a capped clip fraction rather than through
    `shrink_fraction`. NOT modelled here; it inherits the same bias by the same mechanism and is
    rowed separately.
`_PLAUSIBLE_SHARPE = 4.0` (`run_leverage_opt.py:36`) is a rail on the FIRST path only, applied to
the cash-and-carry shadow series, and it is NOT a gate on cohort promotion. It appears in the
artifact purely as a REFERENCE CEILING -- `frac_winners_above_desk_plausibility_ceiling` counts how
many of this study's promoted winners carry a forward Sharpe above the level the desk elsewhere
calls a measurement defect. It is context for reading the leverage numbers, never a claim that
anything zeroes these candidates today.

WHAT THIS DOES NOT DO. Nothing here is wired. No sizer, rail, gate or bar is changed by this file
(`"wired": false` in the artifact). `_ruin_cap` and `first_inversion_cap` bind from the constraint
side and are deliberately absent from the arms -- this measures the SHRINK in isolation.
"""
from __future__ import annotations

import json
import math
import sys
from datetime import UTC, datetime
from pathlib import Path

import numpy as np

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from libs.research.slot_registry import MAX_FORWARD_SLOTS  # noqa: E402
from libs.risk.kelly_shrink import sharpe_se, shrink_fraction  # noqa: E402
from libs.validation.forward_stats import holm_bar  # noqa: E402

_OUT = _ROOT / "docs/research/promotion_selection_bias_study.json"
_PPY = 365.0
_ROUNDS = 200_000          # promotion rounds per arm per cell
_N_BINS = 40               # quantile bins for the empirical-Bayes calibration maps
_CAL_POOL = 400_000        # candidates retained for the SELECTION-BLIND map
_SCREEN_M = 420            # the screen's own intensity -- the positive control
_PLAUSIBLE_SHARPE = 4.0    # run_leverage_opt.py:36 -- a rail on the OTHER path; reference only
# Bound the (rounds x m) intermediates. The positive control is 200k x 420 = 84M elements per
# array and several exist at once; unchunked, the first run of this script was OOM-killed at
# exit 137. Only the per-round WINNERS survive a chunk, and those are `rounds` long whatever m is.
#
# A CONSTANT NUMBER OF ROUNDS, NOT A CONSTANT NUMBER OF ELEMENTS. Deriving the chunk from `m`
# (elements // m) made the boundaries -- and therefore the order in which the generator is consumed
# -- a function of a STUDY PARAMETER, so the m=4 and m=12 cells drew differently for reasons that
# had nothing to do with the question. Fixed rounds keep the draw identical across cells and bound
# memory at _CHUNK_ROUNDS * m, which is 4.2M elements at the m=420 control.
_CHUNK_ROUNDS = 10_000


def _se_vec(s_true: np.ndarray, n_days: float) -> np.ndarray:
    """Lo (2002) SE of the annualized Sharpe, vectorized.

    Pinned against `libs.risk.kelly_shrink.sharpe_se` by `_instrument_checks` so this copy can
    never drift from the SE the sizer actually uses -- a study whose arithmetic has quietly
    diverged from the code it is judging measures nothing.
    """
    s_daily = s_true / math.sqrt(_PPY)
    return np.sqrt((1.0 + 0.5 * s_daily * s_daily) / n_days) * math.sqrt(_PPY)


def _shrink_vec(s_hat: np.ndarray, n_days: float) -> np.ndarray:
    """`shrink_fraction` vectorized, including its S<=0 and n_eff<5 zero branches (vif=1)."""
    out = np.zeros_like(s_hat)
    if n_days < 5:
        return out
    pos = s_hat > 0.0
    if not pos.any():
        return out
    s = s_hat[pos]
    se = _se_vec(s, n_days)
    s2 = s * s
    out[pos] = s2 / (s2 + se * se)
    return out


def _growth(lev: np.ndarray, s_true: np.ndarray) -> np.ndarray:
    """Annualized log-growth rate at unit vol: L*mu - L^2 sigma^2/2 with sigma = 1, mu = S_true.

    Full Kelly is L = S_true, which is what makes the oracle arm a genuine ceiling.
    """
    return lev * s_true - 0.5 * lev * lev


def _draw(rng: np.random.Generator, rounds: int, m: int, pi: float, s_edge: float,
          n_days: float) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """One cohort draw: (S_true, S_hat, t) each shaped (rounds, m)."""
    real = rng.random((rounds, m)) < pi
    s_true = np.where(real, rng.exponential(s_edge, (rounds, m)), 0.0)
    s_hat = s_true + rng.normal(0.0, 1.0, (rounds, m)) * _se_vec(s_true, n_days)
    return s_true, s_hat, s_hat * math.sqrt(n_days / _PPY)


def _select(t: np.ndarray, bar: float,
            rng: np.random.Generator | None) -> tuple[np.ndarray, np.ndarray]:
    """Return (index of the chosen candidate, promoted mask).

    `rng` is None for the real regime -- take the MAX t and require it to clear the Holm bar, which
    is the selection this study exists to price. Passing an rng switches to the NULL CONTROL:
    choose a cohort member at random and promote unconditionally, so winners are an iid sample of
    candidates and a correct selection term must vanish.
    """
    if rng is None:
        win = np.argmax(t, axis=1)
        return win, np.take_along_axis(t, win[:, None], 1).ravel() >= bar
    win = rng.integers(0, t.shape[1], size=t.shape[0])
    return win, np.ones(t.shape[0], dtype=bool)


def _harvest(rng: np.random.Generator, rounds: int, m: int, pi: float, s_edge: float,
             n_days: float, bar: float, sel_rng: np.random.Generator | None
             ) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Draw `rounds` cohorts in memory-bounded chunks.

    Returns (S_hat_winner, S_true_winner, promoted, pool_hat, pool_true). The first three are one
    entry per round; the last two are an iid pool of ALL candidates -- selection-blind by
    construction -- capped at `_CAL_POOL`. The cohort is never materialized whole (`_CHUNK_ROUNDS`).
    """
    chunk = max(1, min(rounds, _CHUNK_ROUNDS))
    hat_w, true_w, prom, p_hat, p_true = [], [], [], [], []
    pooled = 0
    done = 0
    while done < rounds:
        n = min(chunk, rounds - done)
        s_true, s_hat, t = _draw(rng, n, m, pi, s_edge, n_days)
        win, ok = _select(t, bar, sel_rng)
        hat_w.append(np.take_along_axis(s_hat, win[:, None], 1).ravel())
        true_w.append(np.take_along_axis(s_true, win[:, None], 1).ravel())
        prom.append(ok)
        if pooled < _CAL_POOL:
            # every candidate is iid, so a prefix of the flattened chunk is an unbiased sample
            take = min(_CAL_POOL - pooled, s_hat.size)
            p_hat.append(s_hat.ravel()[:take])
            p_true.append(s_true.ravel()[:take])
            pooled += take
        done += n
    return (np.concatenate(hat_w), np.concatenate(true_w), np.concatenate(prom),
            np.concatenate(p_hat), np.concatenate(p_true))


def _calibrate(s_hat: np.ndarray, s_true: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Empirical-Bayes map E[S_true | S_hat] over quantile bins.

    Quantile bins rather than fixed-width: the promoted region is a thin upper tail and fixed-width
    bins there are mostly empty, which turns the map into noise exactly where it has to be right.
    """
    if s_hat.size < _N_BINS * 10:
        return np.array([]), np.array([])
    edges = np.unique(np.quantile(s_hat, np.linspace(0.0, 1.0, _N_BINS + 1)))
    if edges.size < 3:
        return np.array([]), np.array([])
    idx = np.clip(np.digitize(s_hat, edges[1:-1]), 0, edges.size - 2)
    centre = np.full(edges.size - 1, np.nan)
    target = np.full(edges.size - 1, np.nan)
    for b in range(edges.size - 1):
        sel = idx == b
        if sel.any():
            centre[b] = float(s_hat[sel].mean())
            target[b] = float(s_true[sel].mean())
    ok = ~np.isnan(centre)
    return centre[ok], target[ok]


def _apply(centre: np.ndarray, target: np.ndarray, s_hat: np.ndarray) -> np.ndarray:
    """Apply a calibrated map, clipped at the ends rather than extrapolated."""
    if centre.size < 2:
        return s_hat.copy()
    return np.maximum(np.interp(s_hat, centre, target), 0.0)


def _paired_t(a: np.ndarray, b: np.ndarray) -> float:
    """t-stat of mean(a - b) over paired rounds. Common random numbers make the pairing exact."""
    d = a - b
    sd = float(d.std(ddof=1))
    if sd <= 0.0 or d.size < 2:
        return 0.0
    return float(d.mean() / (sd / math.sqrt(d.size)))


def _instrument_checks() -> dict[str, object]:
    """Run BEFORE any adjudication -- a verdict from a blunt instrument is the false-null direction
    no other gate on this desk catches. Pins the vectorized copies against the live library."""
    grid_s = np.array([0.2, 0.5, 0.75, 1.0, 1.5, 2.3, 4.0])
    worst_se, worst_shrink = 0.0, 0.0
    for n in (40.0, 90.0, 180.0, 365.0):
        worst_se = max(worst_se, float(np.max(np.abs(
            _se_vec(grid_s, n) - np.array([sharpe_se(float(s), n) for s in grid_s])))))
        # the library rounds to 4dp; compare against the unrounded formula at that tolerance
        worst_shrink = max(worst_shrink, float(np.max(np.abs(
            _shrink_vec(grid_s, n) - np.array([shrink_fraction(float(s), n) for s in grid_s])))))
    rng = np.random.default_rng(20260820)
    emax = {k: float(np.mean(np.max(rng.standard_normal((200_000, k)), axis=1)))
            for k in (MAX_FORWARD_SLOTS, _SCREEN_M)}
    return {
        "se_matches_library_max_abs_err": round(worst_se, 12),
        "shrink_matches_library_max_abs_err": round(worst_shrink, 6),
        "instrument_ok": bool(worst_se < 1e-9 and worst_shrink < 1e-4),
        "e_max_of_k_standard_normals": {str(k): round(v, 3) for k, v in emax.items()},
        "e_max_note": (
            f"selection intensity is best-of-{MAX_FORWARD_SLOTS} at promotion "
            f"({emax[MAX_FORWARD_SLOTS]:.2f} SEs) against best-of-{_SCREEN_M} at the screen "
            f"({emax[_SCREEN_M]:.2f} SEs) -- roughly half, which is why R0432's answer does not "
            "carry over to this question"),
    }


def cell(m: int, n_days: float, pi: float, s_edge: float, *, null_control: bool = False,
         seed: int = 0, rounds: int = _ROUNDS) -> dict[str, object]:
    """One measured cell. All five sizing arms share the same draws (common random numbers)."""
    bar = float(holm_bar(m, 1))
    sel_cal = np.random.default_rng(seed + 8_000_000) if null_control else None
    sel_ev = np.random.default_rng(seed + 9_000_000) if null_control else None

    # --- calibration draw (independent seed; never scored) ---
    c_hat_w, c_true_w, c_prom, c_pool_h, c_pool_t = _harvest(
        np.random.default_rng(seed + 7_000_000), rounds, m, pi, s_edge, n_days, bar, sel_cal)
    aware = _calibrate(c_hat_w[c_prom], c_true_w[c_prom])   # winners only  -> selection-AWARE
    blind = _calibrate(c_pool_h, c_pool_t)                  # all candidates -> selection-BLIND

    # --- evaluation draw (scored, out-of-sample w.r.t. both maps) ---
    hat_w, true_w, prom, _, _ = _harvest(
        np.random.default_rng(seed), rounds, m, pi, s_edge, n_days, bar, sel_ev)

    arms = {
        "naive": np.maximum(hat_w, 0.0),
        "desk": _shrink_vec(hat_w, n_days) * hat_w,
        "eb_blind": _apply(*blind, hat_w),
        "eb_aware": _apply(*aware, hat_w),
        "oracle": true_w.copy(),
    }
    growth = {k: np.where(prom, _growth(lev, true_w), 0.0) for k, lev in arms.items()}
    means = {k: float(v.mean()) for k, v in growth.items()}
    orc = means["oracle"]

    # THE SELECTION TERM: both maps know the prior, they differ only in conditioning on selection.
    sel_gain = means["eb_aware"] - means["eb_blind"]
    sel_t = _paired_t(growth["eb_aware"], growth["eb_blind"])
    sel_rel = sel_gain / orc if orc > 0 else float("nan")
    # the separate PRIOR term, reported so the two are never read as one number again
    prior_gain = means["eb_blind"] - means["desk"]
    prior_rel = prior_gain / orc if orc > 0 else float("nan")

    n_prom = int(prom.sum())
    bias = float((hat_w[prom] - true_w[prom]).mean()) if n_prom else float("nan")
    bias_ses = (bias / float(_se_vec(true_w[prom], n_days).mean())) if n_prom else float("nan")
    railed = (float((hat_w[prom] > _PLAUSIBLE_SHARPE).mean()) if n_prom else float("nan"))

    if not math.isfinite(sel_rel):
        verdict = "UNMEASURED (oracle growth non-positive -- no edge exists in this prior)"
    elif null_control:
        verdict = ("NULL-CONTROL-PASSED" if abs(sel_rel) < 0.01 else
                   "NULL-CONTROL-FAILED (selection term non-zero where there is no selection)")
    elif abs(sel_t) < 3.0:
        verdict = "ABSORBED (selection term not measurable)"
    elif sel_rel < 0.01:
        verdict = "ABSORBED-MATERIALLY (selection term detectable but under 1% of oracle growth)"
    else:
        verdict = "CORRECTION-REAL (selection term buys growth; direction is TIGHTER)"

    return {
        "m": m, "n_days": n_days, "pi": pi, "s_edge": s_edge,
        "null_control": null_control, "holm_bar": bar, "rounds": rounds,
        "n_promoted": n_prom,
        "promotion_rate": round(n_prom / rounds, 5),
        "selected_sharpe_bias": round(bias, 4),
        "selected_sharpe_bias_in_ses": round(bias_ses, 3),
        "frac_winners_above_desk_plausibility_ceiling": round(railed, 4),
        "mean_growth": {k: round(v, 6) for k, v in means.items()},
        "selection_gain": round(sel_gain, 8),
        "selection_gain_t": round(sel_t, 2),
        "selection_gain_as_frac_of_oracle": round(sel_rel, 5) if math.isfinite(sel_rel) else None,
        "prior_gain": round(prior_gain, 8),
        "prior_gain_as_frac_of_oracle": round(prior_rel, 5) if math.isfinite(prior_rel) else None,
        "ceiling_holds": bool(all(orc >= means[k] - 1e-12 for k in arms)),
        "shrink_beats_naive": bool(means["desk"] > means["naive"]),
        "verdict": verdict,
    }


def main() -> int:
    instr = _instrument_checks()
    cells: list[dict[str, object]] = []
    seed = 4242

    # NULL CONTROL first -- if the selection term is non-zero with no selection present,
    # nothing downstream in this file means anything.
    for n_days in (90.0, 180.0):
        cells.append(cell(MAX_FORWARD_SLOTS, n_days, 0.15, 1.0, null_control=True, seed=seed))
        seed += 1
    # POSITIVE CONTROL -- the screen's own intensity, where the selection term must be large.
    cells.append(cell(_SCREEN_M, 180.0, 0.15, 1.0, seed=seed))
    seed += 1
    # THE LIVE REGIME.
    for m in (4, MAX_FORWARD_SLOTS):
        for n_days in (90.0, 180.0):
            for pi, s_edge in ((0.05, 1.0), (0.15, 1.0), (0.30, 0.5)):
                cells.append(cell(m, n_days, pi, s_edge, seed=seed))
                seed += 1

    nulls = [c for c in cells if c["null_control"]]
    pos = next(c for c in cells if c["m"] == _SCREEN_M and not c["null_control"])
    live = [c for c in cells if c["m"] == MAX_FORWARD_SLOTS and not c["null_control"]]

    n_null_ok = sum(1 for c in nulls if str(c["verdict"]).startswith("NULL-CONTROL-PASSED"))
    pos_ok = bool(str(pos["verdict"]).startswith("CORRECTION-REAL"))
    ceilings_ok = sum(1 for c in cells if c["ceiling_holds"])

    if not instr["instrument_ok"]:
        answer = "UNUSABLE (the study's arithmetic no longer matches libs/risk/kelly_shrink)"
    elif n_null_ok < len(nulls):
        answer = "UNUSABLE (null control failed -- the selection term is measuring something else)"
    elif not pos_ok:
        answer = ("UNMEASURED (positive control did not detect the known best-of-420 selection "
                  "bias, so a null at m=12 is a statement about the instrument, not the desk)")
    elif all(str(c["verdict"]).startswith("ABSORBED") for c in live):
        answer = ("ABSORBED -- at the desk's live selection intensity, conditioning the effect-size "
                  "estimate on having been selected buys no material growth over an equally "
                  "prior-aware estimator that ignores selection. R0574's specific question is "
                  "retired: best-of-12 does not warrant a change to shrink_fraction.")
    else:
        answer = ("CORRECTION-REAL -- conditioning on selection buys measurable growth at the live "
                  "intensity, so the promoted effect size IS upward-biased in a way the estimation "
                  "shrink does not absorb. Any change is TIGHTER, never looser.")

    worst_prior = max((c["prior_gain_as_frac_of_oracle"] or 0.0) for c in live)
    # Derived, not simulated: what forward Sharpe a candidate MUST show to clear the Holm bar at a
    # given horizon, since t = S * sqrt(n/365). Surfaced because the study's promoted winners sit
    # far above the level the desk calls implausible elsewhere, and that turned out to be
    # arithmetic rather than a simulation artifact.
    bar_vs_plaus = {}
    for mm in (4, MAX_FORWARD_SLOTS, _SCREEN_M):
        b = float(holm_bar(mm, 1))
        bar_vs_plaus[str(mm)] = {
            "holm_bar": b,
            "min_forward_sharpe_to_clear": {str(int(nn)): round(b / math.sqrt(nn / _PPY), 2)
                                            for nn in (90, 180, 365)},
            "days_until_requirement_falls_to_plausibility_ceiling":
                round(_PPY * (b / _PLAUSIBLE_SHARPE) ** 2),
        }
    doc = {
        "row": "R0574",
        "parent_row": "R0432",
        "question": ("promotion selects the best of MAX_FORWARD_SLOTS concurrent forward clocks and "
                     "Holm corrects the p-value of that decision, not the effect SIZE the sizer "
                     "then uses -- does S^2/(S^2+SE^2) already absorb the best-of-12 winner's "
                     "curse?"),
        "status": "MEASURED",
        "ran": datetime.now(UTC).isoformat(),
        "max_forward_slots": MAX_FORWARD_SLOTS,
        "screen_intensity_for_positive_control": _SCREEN_M,
        "rounds_per_cell": _ROUNDS,
        "instrument_checks": instr,
        "null_control_passed": f"{n_null_ok}/{len(nulls)}",
        "null_control_note": (
            "promote a RANDOM cohort member with no bar: winners are then an iid sample of "
            "candidates, both maps see the same distribution, and the selection term must vanish. "
            "The FIRST version of this study had no such control and read the prior term as the "
            "selection term -- it measured 0.98 of oracle growth where there was no selection at "
            "all."),
        "positive_control_passed": f"{1 if pos_ok else 0}/1",
        "positive_control_note": (
            "at m=420 the selection bias MUST be large and the aware map MUST find it. A method "
            "never shown to detect a known-present bias has not been validated -- only its "
            "silences have been observed."),
        "ceiling_holds": f"{ceilings_ok}/{len(cells)}",
        "ceiling_note": ("the oracle arm sizes on S_true and is an upper bound on every other arm "
                         "by construction; a cell where it is beaten is a broken simulator"),
        "n_cells": len(cells),
        "answer": answer,
        "the_larger_finding": (
            "THE SELECTION TERM IS NOT WHERE THE MONEY IS. Across the live cells the PRIOR term -- "
            f"an estimator that knows the desk's spike-at-zero prior, versus S^2/(S^2+SE^2) which "
            f"knows only SE -- is worth up to {worst_prior:.2f} of oracle growth, an order of "
            "magnitude more than conditioning on selection. shrink_fraction shrinks toward zero "
            "using the standard error alone and never toward the desk's own base rate, and that "
            "omission dominates the one R0574 asked about. Rowed separately rather than acted on "
            "here: it is a different question from the one this study pre-registered, and the "
            "prior is an input this desk would have to estimate and defend before any sizer read "
            "it."),
        "bar_vs_plausibility": bar_vs_plaus,
        "bar_vs_plausibility_note": (
            "PURE ARITHMETIC, NOT A SIMULATION RESULT, and it is a tension between two constants "
            "this desk holds in two different pipelines rather than a proven live weld. Because "
            f"t = S*sqrt(n/365), a cohort of {MAX_FORWARD_SLOTS} cannot clear its Holm bar of "
            f"{holm_bar(MAX_FORWARD_SLOTS, 1):.2f} on fewer than "
            f"{round(_PPY * (holm_bar(MAX_FORWARD_SLOTS, 1) / _PLAUSIBLE_SHARPE) ** 2)} forward "
            f"days unless the candidate shows a forward Sharpe above {_PLAUSIBLE_SHARPE} -- the "
            "level run_leverage_opt treats as a measurement defect rather than evidence of edge. "
            "The two constants govern different paths (see SCOPE in the module docstring), so "
            "nothing is currently blocked by this; it is flagged because any future wiring that "
            "put a short-horizon promotion through the cash-and-carry rail would deadlock, and "
            "because a bar only clearable by an implausible reading is worth knowing about."),
        "wired": False,
        "wired_note": ("STUDY ONLY. No sizer, rail, gate or bar is changed by this file. "
                       "libs/risk/kelly_shrink.py is untouched."),
        "cells": cells,
    }
    _OUT.parent.mkdir(parents=True, exist_ok=True)
    _OUT.write_text(json.dumps(doc, indent=1), "utf-8")

    print(f"instrument: {'OK' if instr['instrument_ok'] else 'BROKEN'}   "
          f"E[max] {MAX_FORWARD_SLOTS}={instr['e_max_of_k_standard_normals'][str(MAX_FORWARD_SLOTS)]}"
          f" SEs  {_SCREEN_M}={instr['e_max_of_k_standard_normals'][str(_SCREEN_M)]} SEs")
    print(f"{'m':>7} {'n_d':>5} {'pi':>5} {'edge':>5} {'prom':>7} {'bias/SE':>8} {'railed':>7} "
          f"{'g_desk':>9} {'g_blind':>9} {'g_aware':>9} {'sel_t':>7} {'sel/orc':>8} {'pri/orc':>8}  verdict")
    for c in cells:
        tag = "NULL" if c["null_control"] else ""
        sr = c["selection_gain_as_frac_of_oracle"]
        pr = c["prior_gain_as_frac_of_oracle"]
        print(f"{tag:>4}{c['m']:>3} {c['n_days']:>5.0f} {c['pi']:>5.2f} {c['s_edge']:>5.2f} "
              f"{c['promotion_rate']:>7.3f} {c['selected_sharpe_bias_in_ses']:>8.2f} "
              f"{c['frac_winners_above_desk_plausibility_ceiling']:>7.3f} "
              f"{c['mean_growth']['desk']:>9.5f} {c['mean_growth']['eb_blind']:>9.5f} "
              f"{c['mean_growth']['eb_aware']:>9.5f} {c['selection_gain_t']:>7.1f} "
              f"{(sr if sr is not None else float('nan')):>8.4f} "
              f"{(pr if pr is not None else float('nan')):>8.4f}  {c['verdict']}")
    print(f"\nANSWER: {answer}")
    print(f"written -> {_OUT.relative_to(_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

```
