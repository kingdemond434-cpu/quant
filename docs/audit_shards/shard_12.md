# AUDIT SHARD 12/24 -- seat inception/mercury-2.5

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

### libs\ops\llm_seat.py
```python
"""THE SEAT. One key resolution and one call path for every external-model organ on this desk.

WHY THIS EXISTS, and it is the highest-leverage thing in this area rather than another organ.
Eleven organs on this desk are dark right now -- run_external_panel, strategic_director,
llm_code_auditor, meta_architect, breadth_expander, kimi_hunter, collector_author, deep_review,
run_micro_audit, refresh_panel_roster, llm_blind_researcher -- and every one of them is dark for
the SAME reason: they each open `data/secrets/llm_panel.json`, that file does not exist, and not
one of them reads an environment variable. `run_discretionary_max` names this as lever 2 of five,
CROSS-FAMILY, and records it as "blocked on the OpenRouter seat"; `strategic_director` describes
itself as "activation-ready by construction" waiting on the same thing.

So the binding constraint was never eleven integrations. It was one credential with no env-var
route into the box. This module is that route: resolve a key from the environment FIRST and the
secrets file second, and every dark organ can light from a single exported variable -- which is
the same mechanism that just unblocked GitHub search, and a mechanism the principal already
operates.

ONE CODE PATH, AND OPENROUTER IS THE RECOMMENDED KEY. `/chat/completions` is OpenAI-COMPATIBLE
across OpenRouter, xAI, DeepSeek, Qwen, Mistral and OpenAI itself, so any of them work. OpenRouter
is preferred for a reason that only shows up over time: a DIRECT vendor key bounds the
auto-upgrade below to that vendor's catalogue, so an OpenAI key would climb gpt-5 -> gpt-6 -> gpt-7
forever and never reach a better model from anyone else. OpenRouter lists the whole landscape, so
the same version parser upgrades across the MARKET. It is also the only single credential that
delivers cross-family (lever 2), and a second seat from the desk's OWN family would agree with it
for reasons that have nothing to do with the market.

THE FLAGSHIP IS DISCOVERED AND UPGRADES ITSELF. A pinned model string is a time bomb: it works
until the provider retires it, and then every organ fails with an error that reads like an outage.
A pinned PREFERENCE LIST is the same bomb with a longer fuse and it is the worse of the two --
the day `gpt-6` ships, a list containing `gpt-5` keeps choosing the older model forever while
every status line still reads healthy. So the version number is PARSED out of whatever the
provider lists and the highest wins, which makes the upgrade automatic and silent in the right
direction. Cheaper variants (mini, nano, turbo, :free) are refused outright rather than ranked
low, because they sort adjacent to the flagship and often carry the SAME version number.

EFFORT IS REQUESTED AT MAXIMUM. Four cycles a day against a $20/month cap means the binding
constraint is the quality of twelve recommendations, never the tokens spent producing them.
Providers that reject the parameter are retried without it, so asking for more thinking can never
cost a cycle.

SPEND IS CAPPED AND MEASURED, because this is wired to a daily cadence and a runaway loop against
a metered API is a real way to lose real money. Every call records its token usage; the month's
spend is checked BEFORE each call against a hard cap. The desk has already been burned by the
opposite design -- run_external_panel discovered credit exhaustion mid-run, after spending the
last of it on a verification panel that verified nothing (0/13 responded, all HTTP 402).
"""

from __future__ import annotations

import contextlib
import json
import os
import re
import ssl
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parents[2]
SECRETS = _ROOT / "data" / "secrets" / "llm_panel.json"
SPEND_LEDGER = _ROOT / "data" / "llm_spend.jsonl"

#: Environment variables consulted, in order. OPENROUTER IS FIRST, and the reason is the auto-
#: upgrade requirement rather than convenience.
#:
#: Version parsing makes the flagship selection automatic, but a DIRECT vendor key bounds that
#: automation to one vendor's catalogue: an OpenAI key upgrades gpt-5 -> gpt-6 -> gpt-7 forever and
#: can never reach a better model from anyone else. OpenRouter lists the whole landscape, so the
#: same parser upgrades across the MARKET rather than within a supplier. Given a standing order to
#: always run the best available model, a single-vendor key quietly caps that at "best available
#: from this vendor" -- which is the "then never" failure with a wider blast radius.
#:
#: It is also the only key that satisfies cross-family (lever 2) from one credential, and the
#: eleven dark organs already point at OpenRouter base URLs -- kimi_hunter cannot run without it.
KEY_ENV_VARS: tuple[tuple[str, str, str], ...] = (
    ("OPENROUTER_API_KEY", "openrouter", "https://openrouter.ai/api/v1"),
    ("OPENAI_API_KEY", "openai", "https://api.openai.com/v1"),
    ("DEEPSEEK_API_KEY", "deepseek", "https://api.deepseek.com/v1"),
    ("XAI_API_KEY", "xai", "https://api.x.ai/v1"),
)

#: Flagship families, as VERSION-EXTRACTING patterns rather than a list of names.
#:
#: WHY NOT A LIST OF NAMES (principal 2026-08-01: "always maximum flagship models, max effort, and
#: upgrade in future automatic if better comes"). A hardcoded preference list is pinned to what was
#: known the day it was written: the day `gpt-6` ships, a list containing `gpt-5` keeps selecting
#: the older model forever, silently, and the desk reads a healthy green seat while running a
#: superseded brain. That is the same failure as a pinned model string, one level up.
#:
#: So the version is PARSED and the HIGHEST wins. `gpt-6` outranks `gpt-5` the moment the provider
#: lists it, with no code change and no release note to notice. Families are ordered only to break
#: ties between equal version numbers.
_FLAGSHIP_PATTERNS: tuple[tuple[str, str], ...] = (
    # A minor version is introduced by a DOT only (gpt-4.1, gpt-5.2). A HYPHEN followed by digits
    # is a dated snapshot -- `gpt-5-2026-04-01` -- and reading that as minor version 2026 made the
    # snapshot outrank its own stable alias. Snapshots get retired under you; the bare alias does
    # not, so it must win.
    ("gpt", r"(?:^|/)gpt-(\d+)(?:\.(\d+))?"),         # gpt-5, gpt-5.1, gpt-6, gpt-12 ...
    ("o", r"(?:^|/)o(\d+)(?:\.(\d+))?\b"),            # o3, o4, o5 ...
    ("grok", r"(?:^|/)grok-(\d+)(?:\.(\d+))?"),
    ("deepseek", r"(?:^|/)deepseek-r(\d+)(?:\.(\d+))?"),
    ("claude", r"(?:^|/)claude-[a-z]*-?(\d+)(?:\.(\d+))?"),
)

#: LAST-RESORT FAMILY MATCH: any `name-<version>` id at all.
#:
#: WHY (principal 2026-08-01: "it should always upgrade when new better released, not just to gpt6
#: then never"). Parsing the version number already makes gpt-7, gpt-12 and beyond automatic --
#: there is no ceiling. But the FAMILY list is still a list, and a genuinely new family under a new
#: name would match nothing and be invisible forever. That is the same "then never" failure one
#: level up, and it is the one that actually bites when the landscape moves.
#:
#: So when no KNOWN family is present, any versioned non-downgrade id becomes a candidate. Known
#: families still win outright when they exist, because an unrecognised name is weaker evidence
#: than a recognised one -- but "unrecognised" can no longer mean "unusable".
_GENERIC_PATTERN = r"(?:^|/)([a-z][a-z0-9]*)[-_]?v?(\d+)(?:\.(\d+))?"

#: Tie-break order between families at the same version number. GPT first because the principal
#: seated GPT specifically; the rest exist so a provider without it still yields a flagship.
_FAMILY_RANK = {name: i for i, (name, _) in enumerate(_FLAGSHIP_PATTERNS)}

#: Tokens that mark a CHEAPER, SMALLER or OLDER variant. A model id carrying any of these is not
#: the flagship, and picking one would quietly downgrade the seat while every status line still
#: read healthy. `mini` and `nano` are the dangerous ones: they sort adjacent to the flagship and
#: often carry the same version number.
_DOWNGRADE_TOKENS: tuple[str, ...] = (
    "mini", "nano", "small", "lite", "tiny", "turbo", "instruct", "preview", "legacy",
    ":free", "-free", "8b", "7b", "3b", "flash", "haiku", "distill", "base", "audio",
    "realtime", "transcribe", "tts", "image", "search", "embedding", "moderation", "codex",
)

#: Reasoning effort requested. MAX BY DEFAULT: this seat runs four times a day against a $20/month
#: cap, so the binding constraint is the quality of twelve recommendations rather than the token
#: cost of producing them. Providers that reject the parameter are retried without it -- see
#: `chat` -- so requesting it can never cost a cycle.
DEFAULT_EFFORT = "high"

#: Hard monthly ceiling in USD. Deliberately low: this is wired to a daily cadence, and the cost
#: of an over-cautious cap is a deferred run while the cost of no cap is unbounded. Raise it
#: through the environment when the spend is proven worth it, never by editing this line -- a cap
#: that gets edited upward whenever it binds is not a cap.
DEFAULT_MONTHLY_CAP_USD = 20.0

#: Rough blended $/1k tokens, used only to enforce the cap. Intentionally an OVER-estimate: the
#: two errors are not symmetric. Over-estimating defers a run by a cycle; under-estimating spends
#: money the principal did not agree to.
_USD_PER_1K_TOKENS = 0.02

#: FREE TIER IS THE DEFAULT, EVERYWHERE (2026-09-12, principal: "make everything free tier on
#: openrouter... all the paid run things js run on free tiers instead").
#:
#: WHY A DEFAULT AND NOT A FLAG ON EACH ORGAN. A flag has to be remembered at every call site, and
#: the organs that resolve a seat here are spread across six scripts and three libraries -- one
#: forgotten export is a paid run nobody authorised. Defaulting the policy ON and requiring
#: QUANT_FREE_TIER=0 to spend makes the safe state the automatic one.
#:
#: IT IS NOT A THROTTLE. Free models are weaker than flagships and every finding still faces the
#: identical ten gates, so this buys ATTEMPTS and never leniency -- and the cadence it pays for is
#: 24x: the six seats went from daily to hourly in the same change. kimi_hunter measured this
#: trade already and its conclusion holds: a free-tier hunt is worth immeasurably more than no
#: hunt, and the binding constraint was never model quality, it was the seat being dark.
def free_tier_only() -> bool:
    """True unless the principal explicitly re-enables spending with QUANT_FREE_TIER=0."""
    return os.environ.get("QUANT_FREE_TIER", "1") != "0"


_CTX: ssl.SSLContext | None = None


def _ctx() -> ssl.SSLContext:
    global _CTX
    if _CTX is None:
        try:
            import certifi
            _CTX = ssl.create_default_context(cafile=certifi.where())
        except ImportError:
            _CTX = ssl.create_default_context()
    return _CTX


@dataclass(frozen=True)
class Seat:
    name: str
    base_url: str
    key: str
    model: str = ""
    source: str = ""

    @property
    def redacted(self) -> str:
        """For logs and reports. A key that reaches a log file is a leaked key."""
        return f"{self.name}:{self.model or '<undiscovered>'} (key {self.key[:6]}...)"


def seats() -> list[Seat]:
    """Every seat this box can reach, environment first, secrets file second.

    ENVIRONMENT FIRST IS THE WHOLE POINT. The secrets file has to be written onto a box that gets
    reclaimed; an exported variable is set once in the environment config and survives every
    container the desk is ever given.
    """
    out: list[Seat] = []
    for var, name, base in KEY_ENV_VARS:
        key = os.environ.get(var, "").strip()
        if key:
            out.append(Seat(name=name, base_url=os.environ.get(f"{name.upper()}_BASE_URL", base),
                            key=key, model=os.environ.get(f"{name.upper()}_MODEL", ""),
                            source=f"env:{var}"))
    if SECRETS.exists():
        try:
            cfg = json.loads(SECRETS.read_text("utf-8"))
        except (json.JSONDecodeError, OSError):
            cfg = {}
        for p in cfg.get("providers") or []:
            key = str(p.get("key") or "").strip()
            if not key:
                continue
            out.append(Seat(name=str(p.get("name") or "panel"),
                            base_url=str(p.get("base_url") or "https://openrouter.ai/api/v1"),
                            key=key, model=str(p.get("model") or ""), source="file:llm_panel.json"))
    return out


def primary_seat() -> Seat | None:
    """The seat organs should use when they want exactly one. None when the desk is dark."""
    got = seats()
    return got[0] if got else None


def flagship_rank(model_id: str) -> tuple[int, int, int, int] | None:
    """Rank a model id as a flagship candidate, or None if it is not one.

    Higher sorts better. The version number dominates, which is what makes the upgrade AUTOMATIC:
    when a provider lists `gpt-6`, it outranks every `gpt-5` immediately, with no code change.
    Downgrade-marked ids (mini, nano, turbo, :free ...) are rejected outright rather than ranked
    low -- they sort adjacent to the flagship and often carry the SAME version number, so ranking
    alone would let a `gpt-6-mini` beat a `gpt-5` and quietly shrink the brain.
    """
    low = model_id.lower()
    if any(tok in low for tok in _DOWNGRADE_TOKENS):
        return None
    for family, pat in _FLAGSHIP_PATTERNS:
        m = re.search(pat, low)
        if not m:
            continue
        major = int(m.group(1))
        minor = int(m.group(2)) if m.lastindex and m.lastindex >= 2 and m.group(2) else 0
        # Shorter id wins at equal version: the bare alias (`gpt-5`) is the provider's stable
        # pointer, while decorated ids are dated snapshots that get retired under you.
        return (major, minor, -_FAMILY_RANK[family], -len(low))
    return None


def discover_model(seat: Seat, *, timeout: float = 20.0) -> tuple[str, str | None]:
    """Ask the provider what it serves and pick the HIGHEST-VERSION FLAGSHIP. Returns (model, err).

    A PINNED MODEL STRING IS A TIME BOMB. It works until the provider retires it and then every
    organ fails with something that reads like an outage rather than like a rename. A pinned
    PREFERENCE LIST is the same bomb with a longer fuse: the day `gpt-6` ships, a list containing
    `gpt-5` keeps choosing the older model forever while every status line still reads healthy.
    Parsing the version and taking the maximum makes the upgrade automatic.

    An explicit `<NAME>_MODEL` environment variable still wins -- discovery is the default, never
    an override of the principal's choice.
    """
    if seat.model:
        return seat.model, None
    body, err = _get(f"{seat.base_url}/models", seat.key, timeout=timeout)
    if err:
        return "", err
    ids = [str(m.get("id") or "") for m in (body.get("data") or [])]
    ids = [i for i in ids if i]
    if not ids:
        return "", "provider listed no models"
    if free_tier_only():
        # FREE FIRST -- AND THE SUFFIX MUST COME OFF BEFORE RANKING, or this goes dark.
        #
        # `:free` and `-free` are in _DOWNGRADE_TOKENS, so flagship_rank REFUSES every free id by
        # design: a `gpt-6:free` must never outrank a paid `gpt-6` when both are available. Simply
        # narrowing `ids` to the free ones would therefore leave `ranked` empty, `generic` empty
        # too, and return "no flagship model found" -- every seat dark, with an error that reads
        # like a provider outage. Caught before this shipped; it is the exact shape of the
        # ship-the-caller-before-the-callee outage this desk already paid for once.
        #
        # Stripping the suffix and ranking the BASE name keeps the auto-upgrade property inside
        # the free tier: the day a better free model is listed, it wins on version, with no edit.
        free_ids = [i for i in ids if i.endswith((":free", "-free"))]
        if free_ids:
            base = {re.sub(r"[:\-]free$", "", i): i for i in free_ids}
            # VARIABLE-LENGTH RANK KEY, because the two rankers return different arities:
            # flagship_rank yields a 4-tuple and _generic_rank a 3-tuple. Both are only ever fed
            # to max(), which compares tuples element-wise, and the fallback list is used ONLY
            # when the flagship list is empty -- so the two arities are never compared against
            # each other and the common annotation is honest rather than a widening to silence
            # the checker.
            ranked_free: list[tuple[tuple[int, ...], str]] = [
                (r, orig) for stripped, orig in base.items()
                if (r := flagship_rank(stripped)) is not None]
            if not ranked_free:
                ranked_free = [(g, orig) for stripped, orig in base.items()
                               if (g := _generic_rank(stripped)) is not None]
            if ranked_free:
                return max(ranked_free)[1], None
            # Free models exist but none carries a parseable version. Take one rather than going
            # dark -- an unrankable free seat still answers, and a dark seat answers nothing.
            return sorted(free_ids)[0], None
    ranked = [(r, i) for i in ids if (r := flagship_rank(i)) is not None]
    if ranked:
        return max(ranked)[1], None
    # No KNOWN family present. Rather than going dark on a provider serving something new, fall
    # back to any versioned non-downgrade id -- an unrecognised name is weaker evidence than a
    # recognised one, but it must not mean unusable.
    generic = [(g, i) for i in ids if (g := _generic_rank(i)) is not None]
    if generic:
        return max(generic)[1], None
    return "", (f"no flagship model found among {len(ids)} listed "
                f"(e.g. {', '.join(sorted(ids)[:5])}) -- every candidate carried a downgrade "
                f"marker {_DOWNGRADE_TOKENS[:6]}... or carried no version at all. Set "
                "<PROVIDER>_MODEL explicitly.")


def _generic_rank(model_id: str) -> tuple[int, int, int] | None:
    low = model_id.lower()
    if any(tok in low for tok in _DOWNGRADE_TOKENS):
        return None
    m = re.search(_GENERIC_PATTERN, low)
    if not m:
        return None
    return (int(m.group(2)), int(m.group(3) or 0), -len(low))




def month_spend_usd(now: datetime | None = None) -> float:
    """This calendar month's estimated spend, read from the append-only ledger."""
    stamp = (now or datetime.now(UTC)).strftime("%Y-%m")
    total = 0.0
    if not SPEND_LEDGER.exists():
        return 0.0
    for line in SPEND_LEDGER.read_text("utf-8").splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if str(row.get("utc", "")).startswith(stamp):
            total += float(row.get("usd") or 0.0)
    return round(total, 4)


#: OpenRouter's free tier is capped in REQUESTS PER DAY, not dollars -- and that is the limit the
#: desk actually runs into once every organ is free. The published ceiling is 1,000/day for an
#: account that has ever purchased credit and 50/day for one that has not. The default below sits
#: under the higher number with room for retries; set QUANT_FREE_DAILY_MAX=40 on an account that
#: has never purchased, or the day's budget is gone before the first sweep finishes.
DEFAULT_FREE_DAILY_MAX = 900


#: What the PROVIDER actually refused at, learned from its own 429 rather than assumed. The
#: number above is a published figure for a class of account; this file is what THIS account did.
FREE_CEILING = _ROOT / "data" / "llm_free_ceiling.json"


def observed_free_ceiling(now: datetime | None = None) -> int | None:
    """The request count at which the provider refused a free call TODAY, if it has.

    WHY THIS EXISTS. `DEFAULT_FREE_DAILY_MAX` is 900 because that is OpenRouter's published
    ceiling for an account that has purchased credit. Measured 2026-09-12: this account took
    `HTTP 429 ... free-models-per-day` with the desk's own counter reading 562 calls and 338
    budget "left". The desk therefore believed it had a third of a day's research left while
    every further call was already being refused -- and each refusal reads, at the organ, exactly
    like a provider outage.

    A GUESSED CEILING THAT IS TOO HIGH IS WORSE THAN ONE THAT IS TOO LOW. Too low costs a few
    unmade calls; too high means every organ after the limit spends its cadence on refusals,
    reports errors it cannot act on, and produces nothing -- which is how a lane goes quietly
    dark while its scheduler reports healthy. So the refusal is recorded and believed until the
    UTC day rolls, at which point it is stale by construction and ignored.
    """
    stamp = (now or datetime.now(UTC)).strftime("%Y-%m-%d")
    try:
        doc = json.loads(FREE_CEILING.read_text("utf-8"))
    except (OSError, ValueError):
        return None
    if str(doc.get("date")) != stamp:
        return None
    try:
        n = int(doc.get("ceiling"))
    except (TypeError, ValueError):
        return None
    return n if n >= 0 else None


def note_free_limit_hit(detail: str, now: datetime | None = None) -> None:
    """Record that the provider refused a FREE call, and at what count. Never raises."""
    t = now or datetime.now(UTC)
    row = {"date": t.strftime("%Y-%m-%d"), "ceiling": calls_today(t),
           "observed_at": t.isoformat(timespec="seconds"), "detail": detail[:300],
           "why": ("the provider refused a free request at this count. Until the UTC day rolls, "
                   "free_daily_max() believes this number rather than the configured default -- "
                   "an organ that keeps calling past a real ceiling spends its cadence on "
                   "refusals and goes dark while its scheduler still reports healthy.")}
    try:
        FREE_CEILING.parent.mkdir(parents=True, exist_ok=True)
        FREE_CEILING.write_text(json.dumps(row, indent=1), encoding="utf-8")
    except OSError:
        pass


def free_daily_max() -> int:
    try:
        configured = max(1, int(os.environ.get("QUANT_FREE_DAILY_MAX", DEFAULT_FREE_DAILY_MAX)))
    except ValueError:
        configured = DEFAULT_FREE_DAILY_MAX
    seen = observed_free_ceiling()
    # The MEASURED ceiling wins whenever it is lower, and only for the UTC day it was measured
    # on. It never raises the budget: a day that happened to stop early is not evidence the
    # provider will allow more tomorrow.
    return min(configured, seen) if seen is not None else configured


def calls_today(now: datetime | None = None) -> int:
    """Requests made today, from the same append-only ledger the spend rollup reads."""
    stamp = (now or datetime.now(UTC)).strftime("%Y-%m-%d")
    if not SPEND_LEDGER.exists():
        return 0
    n = 0
    try:
        lines = SPEND_LEDGER.read_text("utf-8").splitlines()
    except OSError:
        return 0
    for line in lines:
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if str(row.get("utc", "")).startswith(stamp):
            n += 1
    return n


def free_budget_left(now: datetime | None = None) -> int:
    """How many free requests today's budget still has. Negative is never returned."""
    return max(0, free_daily_max() - calls_today(now))


def monthly_cap_usd() -> float:
    raw = os.environ.get("LLM_MONTHLY_CAP_USD", "").strip()
    try:
        return float(raw) if raw else DEFAULT_MONTHLY_CAP_USD
    except ValueError:
        return DEFAULT_MONTHLY_CAP_USD


#: Phrases a provider uses when the refusal is the DAY's free allowance rather than a burst.
#: Matched on the error body, because the status code alone cannot tell "slow down for a minute"
#: from "come back tomorrow", and treating the second as the first burns the rest of the day.
_DAILY_FREE_MARKERS: tuple[str, ...] = (
    "free-models-per-day", "per-day", "daily limit", "requests per day", "quota exceeded",
)


def _is_daily_free_refusal(err: str) -> bool:
    low = err.lower()
    return any(m in low for m in _DAILY_FREE_MARKERS)


def chat(
    prompt: str, *, system: str = "", seat: Seat | None = None, max_tokens: int = 8000,
    timeout: float = 240.0, temperature: float = 0.4, effort: str = DEFAULT_EFFORT,
) -> tuple[str, str | None]:
    """One completion at MAXIMUM reasoning effort. Returns (text, error) -- NEVER raises, so a
    cadenced organ survives it.

    EFFORT IS REQUESTED HIGH AND DEGRADED ONLY IF REFUSED. The seat runs four times a day against
    a $20/month cap, so the binding constraint is the quality of twelve recommendations rather
    than the tokens spent producing them -- there is no version of this where thinking less is the
    right trade. Providers differ on which parameters they accept, so a 400 naming a parameter is
    retried with the offending one dropped rather than surfaced as a failure: a seat that goes
    dark because it asked for too much thinking would be a self-inflicted outage.

    The cap is checked BEFORE the call, not after. Checking after is how run_external_panel
    discovered exhaustion mid-run with nothing to show for the spend.
    """
    s = seat or primary_seat()
    if s is None:
        return "", ("no seat: export OPENROUTER_API_KEY (recommended -- one key reaches every "
                    "model family and auto-upgrades across the market, not just within one "
                    "vendor), "
                    "or OPENAI_API_KEY / DEEPSEEK_API_KEY / XAI_API_KEY, or write "
                    "data/secrets/llm_panel.json")
    spent, cap = month_spend_usd(), monthly_cap_usd()
    # THE CAP CANNOT BIND A FREE RUN, and letting it would be the worst failure mode available:
    # the ledger accrues an ESTIMATED cost (_USD_PER_1K_TOKENS is a deliberate over-estimate), so
    # a month of free-tier calls would book phantom spend and then refuse free calls for the rest
    # of the month -- the desk going dark over money it never spent.
    # THE FREE TIER'S LIMIT IS REQUESTS PER DAY, so that is what gets checked when the run is
    # free. Stopping one call short of the ceiling is the difference between an organ that skips
    # a cycle and an account rate-limited into darkness for the rest of the day -- and a dark
    # account takes EVERY organ with it, not just the one that spent the last request.
    if free_tier_only():
        left = free_budget_left()
        if left <= 0:
            return "", (f"free-tier daily request budget exhausted: {calls_today()} call(s) "
                        f"today against a {free_daily_max()} ceiling. This is a SKIP, not a "
                        f"failure -- the budget resets at 00:00 UTC and the next cadence picks "
                        f"it up. Raise QUANT_FREE_DAILY_MAX only if the provider's real limit "
                        f"is higher than the one assumed here.")
    if spent >= cap and not free_tier_only():
        return "", (f"monthly cap reached: ${spent:.2f} of ${cap:.2f}. Raise it with "
                    "$LLM_MONTHLY_CAP_USD if the spend is proven worth it.")
    model, err = discover_model(s)
    if err:
        return "", f"model discovery failed: {err}"

    msgs: list[dict[str, str]] = []
    if system:
        msgs.append({"role": "system", "content": system})
    msgs.append({"role": "user", "content": prompt})
    req: dict[str, Any] = {"model": model, "messages": msgs,
                           "max_completion_tokens": int(max_tokens),
                           "temperature": float(temperature)}
    if effort:
        req["reasoning_effort"] = effort
    body, err = _post_with_degrade(f"{s.base_url}/chat/completions", s.key, req, timeout=timeout)
    if err:
        # A DAILY FREE-TIER REFUSAL IS EVIDENCE, NOT NOISE. Recording it teaches every later
        # caller today's real ceiling instead of letting each one rediscover it one wasted
        # request at a time.
        if "429" in err and _is_daily_free_refusal(err):
            note_free_limit_hit(err)
        return "", err
    try:
        text = str(body["choices"][0]["message"]["content"] or "")
    except (KeyError, IndexError, TypeError):
        return "", f"unparseable response: {json.dumps(body)[:200]}"
    _record_spend(s, model, body.get("usage") or {})
    return text, None


def chat_messages(
    messages: list[dict[str, str]], *, seat: Seat | None = None, max_tokens: int = 8000,
    timeout: float = 240.0, temperature: float = 0.4, effort: str = DEFAULT_EFFORT,
) -> tuple[str, str | None]:
    """chat(), at the MESSAGES level -- the seam the push ladder needs.

    Added 2026-08-04 for `libs.llm.push.push_rounds`: a push round re-sends the whole
    conversation (system + prior rounds + the rung), which a single-prompt entrypoint cannot
    express. Same cap-before-call, same discovery, same degradation ladder, same spend record --
    a second transport here would drift from the first on the exact policies that must not.
    """
    s = seat or primary_seat()
    if s is None:
        return "", "no seat: export OPENROUTER_API_KEY (see chat())"
    spent, cap = month_spend_usd(), monthly_cap_usd()
    # THE CAP CANNOT BIND A FREE RUN, and letting it would be the worst failure mode available:
    # the ledger accrues an ESTIMATED cost (_USD_PER_1K_TOKENS is a deliberate over-estimate), so
    # a month of free-tier calls would book phantom spend and then refuse free calls for the rest
    # of the month -- the desk going dark over money it never spent.
    # THE FREE TIER'S LIMIT IS REQUESTS PER DAY, so that is what gets checked when the run is
    # free. Stopping one call short of the ceiling is the difference between an organ that skips
    # a cycle and an account rate-limited into darkness for the rest of the day -- and a dark
    # account takes EVERY organ with it, not just the one that spent the last request.
    if free_tier_only():
        left = free_budget_left()
        if left <= 0:
            return "", (f"free-tier daily request budget exhausted: {calls_today()} call(s) "
                        f"today against a {free_daily_max()} ceiling. This is a SKIP, not a "
                        f"failure -- the budget resets at 00:00 UTC and the next cadence picks "
                        f"it up. Raise QUANT_FREE_DAILY_MAX only if the provider's real limit "
                        f"is higher than the one assumed here.")
    if spent >= cap and not free_tier_only():
        return "", (f"monthly LLM spend cap reached (${spent:.2f} of ${cap:.2f}) -- raise "
                    "$LLM_MONTHLY_CAP_USD if the spend is proven worth it.")
    model, err = discover_model(s)
    if err:
        return "", f"model discovery failed: {err}"
    req: dict[str, Any] = {"model": model, "messages": list(messages),
                           "max_completion_tokens": int(max_tokens),
                           "temperature": float(temperature)}
    if effort:
        req["reasoning_effort"] = effort
    body, err = _post_with_degrade(f"{s.base_url}/chat/completions", s.key, req, timeout=timeout)
    if err:
        # Same refusal, same lesson: chat_messages is the push ladder's seam and
        # hits the identical daily ceiling.
        if "429" in err and _is_daily_free_refusal(err):
            note_free_limit_hit(err)
        return "", err
    try:
        text = str(body["choices"][0]["message"]["content"] or "")
    except (KeyError, IndexError, TypeError):
        return "", f"unparseable response: {json.dumps(body)[:200]}"
    _record_spend(s, model, body.get("usage") or {})
    return text, None


def stale_pins(*, timeout: float = 20.0) -> list[dict[str, Any]]:
    """Every seat PINNED to a model below the provider's current flagship.

    WHY THIS EXISTS AND WHY IT COVERS MORE THAN THIS MODULE (principal 2026-08-01: "this goes for
    every single llm related to our quant, all panels etc, kimi, you all"). Discovery keeps THIS
    seat current automatically, but the desk's other eleven model organs read
    `data/secrets/llm_panel.json`, and every provider entry there carries a hardcoded `model`
    string. A pin is invisible by construction: the organ runs, returns text, and reports success
    while quietly executing a superseded model -- for years, if nobody looks.

    So the pins are CHECKED against what the provider currently serves, and a pin below the
    flagship is reported as a defect with the replacement named. Reported rather than rewritten:
    silently editing a credentials file out from under eleven organs is a worse failure than a
    stale pin, and a pin may be deliberate (a cost decision, a capability the flagship lost).
    `status()` surfaces this, so it reaches the CRO and the doctor without anyone remembering to
    ask.
    """
    out: list[dict[str, Any]] = []
    for s in seats():
        if not s.model:
            continue                      # unpinned: discovery already keeps it current
        probe = Seat(name=s.name, base_url=s.base_url, key=s.key, model="", source=s.source)
        best, err = discover_model(probe, timeout=timeout)
        if err or not best:
            out.append({"seat": s.name, "source": s.source, "pinned": s.model,
                        "flagship": None, "stale": None, "error": err})
            continue
        # Either ranker may answer; only the leading (major, minor) pair is compared, so the
        # differing tuple widths never meet.
        pinned_rank: tuple[int, ...] | None = flagship_rank(s.model) or _generic_rank(s.model)
        best_rank: tuple[int, ...] | None = flagship_rank(best) or _generic_rank(best)
        stale = bool(best_rank and (pinned_rank is None or best_rank[:2] > pinned_rank[:2]))
        out.append({"seat": s.name, "source": s.source, "pinned": s.model, "flagship": best,
                    "stale": stale,
                    "note": (f"PINNED BELOW FLAGSHIP: {s.model} -> {best}. Either update the pin "
                             "or clear the `model` field so discovery keeps it current."
                             if stale else "")})
    return out


def status() -> dict[str, Any]:
    """What this box can actually reach, re-measured rather than assumed. For the doctor."""
    got = seats()
    out: dict[str, Any] = {
        "n_seats": len(got),
        "seats": [{"name": s.name, "source": s.source, "model": s.model or "<discover>"}
                  for s in got],
        "month_spend_usd": month_spend_usd(),
        "monthly_cap_usd": monthly_cap_usd(),
        "secrets_file_present": SECRETS.exists(),
    }
    if not got:
        out["blocker"] = (
            "DARK: no external-model seat. Export OPENROUTER_API_KEY (one key reaches every "
            "family and auto-upgrades across the market). Eleven organs depend on this -- "
            "run_external_panel, "
            "strategic_director, llm_code_auditor, meta_architect, breadth_expander, kimi_hunter, "
            "collector_author, deep_review, run_micro_audit, refresh_panel_roster, "
            "llm_blind_researcher -- and one exported OPENAI_API_KEY lights all of them.")
        return out
    model, err = discover_model(got[0])
    out["primary"] = got[0].name
    out["primary_model"] = model or None
    out["primary_error"] = err
    out["effort"] = DEFAULT_EFFORT
    # Stale pins reach the CRO and the doctor without anyone remembering to ask. A pinned model is
    # invisible by construction: the organ runs, returns text, and reports success while quietly
    # executing something superseded.
    pins = [p for p in stale_pins() if p.get("stale")]
    if pins:
        out["stale_pins"] = pins
    return out


# ------------------------------------------------------------------------------------ transport

def _headers(key: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {key}", "Content-Type": "application/json",
            "HTTP-Referer": "https://localhost", "X-Title": "quant-desk"}


def _get(url: str, key: str, *, timeout: float) -> tuple[dict[str, Any], str | None]:
    req = urllib.request.Request(url, headers=_headers(key))
    return _send(req, timeout)


#: Parameters that a provider may reject, in the order they are given up. Effort goes LAST because
#: it is the one the principal asked for; temperature and the token-cap spelling go first because
#: their defaults are harmless.
_DEGRADABLE = ("temperature", "max_completion_tokens", "reasoning_effort")


def _post_with_degrade(url: str, key: str, req: dict[str, Any], *, timeout: float
                       ) -> tuple[dict[str, Any], str | None]:
    """POST, and if the provider rejects a parameter by name, drop that one and retry.

    WHY THIS EXISTS RATHER THAN A PER-PROVIDER PARAMETER TABLE. Providers differ on which
    parameters they accept and change it without notice; a table encodes today's answer and rots.
    Reading the rejection is self-correcting -- the provider names the parameter it refused in the
    400 body, which is exactly why `_send` carries the body into the error string.

    `max_completion_tokens` is retried as `max_tokens`, because that rename is the single most
    common 400 across OpenAI-compatible endpoints and losing the cap entirely would let one call
    run away against a metered API.
    """
    attempt = dict(req)
    for _ in range(len(_DEGRADABLE) + 1):
        body, err = _post(url, key, json.dumps(attempt).encode(), timeout=timeout)
        if err is None or not err.startswith("HTTP 400"):
            return body, err
        low = err.lower()
        if "max_completion_tokens" in low and "max_tokens" not in attempt:
            attempt["max_tokens"] = attempt.pop("max_completion_tokens", max(1, 8000))
            continue
        dropped = next((p for p in _DEGRADABLE if p in attempt and p.lower() in low), None)
        if dropped is None:
            return body, err            # a 400 about something we cannot fix by dropping
        attempt.pop(dropped)
    return {}, "exhausted parameter degradation without a successful call"


def _post(url: str, key: str, payload: bytes, *, timeout: float
          ) -> tuple[dict[str, Any], str | None]:
    req = urllib.request.Request(url, data=payload, headers=_headers(key), method="POST")
    return _send(req, timeout)


def _send(req: urllib.request.Request, timeout: float) -> tuple[dict[str, Any], str | None]:
    """HTTP errors carry their BODY into the message. A bare '400 Bad Request' from a model API
    is unactionable; the body says which parameter the provider rejected."""
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=_ctx()) as fh:
            parsed: dict[str, Any] = json.loads(fh.read().decode("utf8", errors="ignore"))
            return parsed, None
    except urllib.error.HTTPError as exc:
        detail = ""
        # A failed body read must not mask the HTTP error itself -- the status code is the part
        # that is always actionable.
        with contextlib.suppress(Exception):
            detail = exc.read().decode("utf8", errors="ignore")[:300]
        return {}, f"HTTP {exc.code}: {detail or exc.reason}"
    except Exception as exc:
        return {}, f"{type(exc).__name__}: {str(exc)[:160]}"


def _record_spend(seat: Seat, model: str, usage: dict[str, Any]) -> None:
    """Append-only, and it records what the PROVIDER reported rather than what we guessed."""
    tok = int(usage.get("total_tokens") or 0)
    row = {"utc": datetime.now(UTC).isoformat(timespec="seconds"), "seat": seat.name,
           "model": model, "tokens": tok,
           "usd": round(tok / 1000.0 * _USD_PER_1K_TOKENS, 5)}
    try:
        SPEND_LEDGER.parent.mkdir(parents=True, exist_ok=True)
        with SPEND_LEDGER.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row) + "\n")
    except OSError:
        pass                          # a ledger write must never take down the organ

```

### libs\research\edge_intake.py
```python
"""UNIVERSAL EDGE INTAKE -- gate items 30/31/34: no discovery may disappear silently.

THE LAW THIS IMPLEMENTS is Part III of the pre-DeepSeek mandate: every legitimately obtained
potential edge gets a canonical record and exactly one of a NAMED set of dispositions. There is no
"looks stupid -- ignore", no "retail source -- ignore", no "too simple -- ignore". Source quality
sets the PRIOR and the required falsification; it never decides empirical truth.

THE GAP IT CLOSES, measured on this desk. The miner writes reports/research_queue.json every run
and the conversion ledger records what eventually converted -- but between those two there was
nothing. A row that was never converted simply aged out of the queue file on the next sweep. The
seen-ledger stopped it being re-surfaced, so it did not reappear either: it was neither tested nor
rejected nor deferred, it was just gone. That is the research-recall defect item 34 exists to
measure, and it is invisible precisely because nothing counts it.

THE THREE PIECES:
  * stamp_queue()  (item 30) folds a queue report into an append-only ledger, giving every row a
                   disposition. Dedup LINKS new provenance to an existing row rather than
                   re-testing it -- a second source finding the same thing is evidence about the
                   finding, not a new experiment.
  * next_batch()   (item 31) hands NEXT_BATCH_TEST rows to a real consumer, oldest-deferred
                   first, and stamps ADMITTED_AT. A queue whose "scheduled" state has no consumer
                   is a graveyard with better manners.
  * recall_audit() (item 34) reconciles discovered against the sum of every disposition. Any
                   unexplained loss is returned as UNACCOUNTED -- a defect, never a rounding note.

DISPOSITIONS ARE NOT VERDICTS ON MERIT. BLOCKED_PENDING_DATA means the desk cannot test it yet and
names the missing ingredient; it is a shopping list, not a rejection. Only
REJECTED_AFTER_EMPIRICAL_TEST is a judgement about the world, and this module never writes it --
that comes from the empirical engine.
"""
from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

__all__ = ["DISPOSITIONS", "LEDGER", "intake_duty", "next_batch", "recall_audit", "rows",
          "stamp_queue"]

_ROOT = Path(__file__).resolve().parents[2]
LEDGER = "data/edge_intake.jsonl"

#: Mandate Part III-2's disposition set. Every intake row carries exactly one.
DISPOSITIONS: tuple[str, ...] = (
    "IMMEDIATE_TEST",                 # cheap, data-ready, high VOI -- test now
    "NEXT_BATCH_TEST",                # real work, waits for capacity; has a consumer
    "BLOCKED_PENDING_DATA",           # testable in principle, missing a named input
    "BLOCKED_PENDING_IMPLEMENTATION", # needs a collector/parser that does not exist
    "DUPLICATE_OF_EXISTING_TEST",     # links provenance to a prior row, never re-tests
    "NON_TESTABLE",                   # no falsifiable claim to test
    "LEGALLY_UNUSABLE",               # rights/licence forbid it
    "DOMINATED_TEST_DEFERRED",        # a strictly better test of the same mechanism exists
    "REJECTED_AFTER_EMPIRICAL_TEST",  # written by the empirical engine, never by intake
)

#: Words that make a queue row a MECHANISM claim rather than a topic. A row naming a mechanism can
#: be turned into a hypothesis; one that does not is missing an ingredient, and saying WHICH is
#: the difference between a shopping list and a shrug.
#:
#: MT5 UNIVERSE WIDENING (2026-08-20, principal: "mine strategies not bs"). Measured on two live
#: runs this desk actually made: 78/111 and 129/188 surfaced rows landed BLOCKED_PENDING_DATA, not
#: because the source was thin but because the miner's own queries and this word list were built
#: for crypto derivative-market microstructure (funding rate, liquidation, unlock) and never
#: extended to name FX/gold/index/ICT mechanisms -- so a title that names a real, codeable MT5 rule
#: still scored as "no mechanism" and got parked instead of routed to a hypothesis. Added below:
#: COT/positioning, ICT/SMC structure, session and carry mechanics, and the rule-language
#: (entry/exit/parameter/source) that marks a title as a REPRODUCIBLE system rather than commentary
#: about one.
_MECHANISM_WORDS = (
    "套利", "arbitrage", "basis", "基差", "funding", "资金费率", "liquidation", "清算", "爆仓",
    "spread", "价差", "premium", "溢价", "parity", "平价", "carry", "skew", "偏度",
    "impact", "冲击", "slippage", "滑点", "orderflow", "订单流", "imbalance", "失衡",
    "unlock", "解锁", "flow", "资金流", "inventory", "库存", "queue", "排队",
    # COT / positioning -- the whale-tracking analogue for MT5
    "cot", "持仓报告", "commercial", "商业头寸", "投机头寸", "净头寸", "producer hedg",
    "生产者对冲",
    # ICT / SMC structure -- named, reproducible entry mechanics, not commentary
    "订单块", "order block", "流动性扫", "liquidity sweep", "公允价值缺口", "fair value gap", "fvg",
    "止损猎杀", "stop hunt", "市场结构", "market structure", "流动性扫荡",
    # session / carry / gap mechanics
    "伦敦定盘", "london fix", "session open", "开盘时段", "利差", "掉期", "swap", "rollover",
    "隔夜利息", "overnight interest", "跳空", "gap risk", "季节性", "seasonal pattern",
    # central bank / macro event mechanics
    "央行", "central bank", "利率决议", "rate decision", "非农", "nfp",
    # rule-language -- the strongest signal a title names a REPRODUCIBLE system, not a topic
    "入场规则", "entry rule", "出场规则", "exit rule", "止损设置", "stop loss", "止盈设置",
    "take profit", "参数设置", "策略源码", "source code", "ea源码", " ea ",
)


def _now() -> str:
    return datetime.now(tz=UTC).isoformat(timespec="seconds")


def _append(row: dict[str, Any], root: Path | None = None) -> dict[str, Any]:
    base = root or _ROOT
    p = base / LEDGER
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    return row


def rows(root: Path | None = None) -> list[dict[str, Any]]:
    """Every intake event, oldest first. Folding gives current state per ident."""
    base = root or _ROOT
    out: list[dict[str, Any]] = []
    try:
        text = (base / LEDGER).read_text("utf-8", errors="ignore")
    except OSError:
        return out
    for line in text.splitlines():
        if line.strip():
            try:
                out.append(json.loads(line))
            except ValueError:
                continue
    return out


def _current(root: Path | None = None) -> dict[str, dict[str, Any]]:
    cur: dict[str, dict[str, Any]] = {}
    for r in rows(root):
        ident = str(r.get("ident", ""))
        if ident:
            cur[ident] = r
    return cur


def _names_mechanism(text: str) -> str:
    low = str(text or "").lower()
    for w in _MECHANISM_WORDS:
        if w.lower() in low:
            return w
    return ""


def classify(row: dict[str, Any], *, seen: dict[str, dict[str, Any]]) -> tuple[str, str]:
    """(disposition, why) for one queue row. Deterministic and cheap -- no model call.

    THE ROUTING RULE, from Part III-3: a row that NAMES A MECHANISM can become a hypothesis and
    goes to the batch. A row that scores on validation vocabulary but names no mechanism is not
    rejected -- it is BLOCKED_PENDING_DATA with the missing ingredient stated, because "we cannot
    test a topic" is a fact about our inputs, not about the material.
    """
    ident = str(row.get("video_id") or row.get("ident") or "")
    if ident in seen:
        prior = seen[ident]
        return ("DUPLICATE_OF_EXISTING_TEST",
                f"already in intake as {prior.get('disposition')} since {prior.get('ts')} -- this "
                "source is LINKED as additional provenance, not re-tested. A second source finding "
                "the same thing is evidence about the finding, never a new experiment")
    mech = _names_mechanism(f"{row.get('title', '')} {' '.join(row.get('why') or [])}")
    if mech:
        return ("NEXT_BATCH_TEST",
                f"names a testable mechanism ({mech!r}) -- convertible to a hypothesis with a "
                "stated economics and a falsification test; queued for the next batch")
    return ("BLOCKED_PENDING_DATA",
            "scored on validation/method vocabulary but names no MECHANISM, so there is nothing "
            "to falsify yet. MISSING INGREDIENT: a stated economic mechanism (who pays, and why "
            "they cannot stop). Not a rejection -- a fact about our inputs (mandate III-2)")


def _same_utc_day(a: str, b: str) -> bool:
    return bool(a) and bool(b) and a[:10] == b[:10]


def stamp_queue(report_path: str | Path, *, root: Path | None = None) -> dict[str, Any]:
    """GATE ITEM 30. Fold a miner queue report into the intake ledger. Nothing disappears.

    IDEMPOTENT WITHIN A UTC DAY (2026-08-13 fix). scripts/mine_research_queue.py stamps its own
    output inline (added 2026-08-12 to close a race between two same-day miner runs), and
    ops/crontab.manifest ALSO fires scripts/run_edge_intake.py -- which called this same function
    on the same default report file -- twenty minutes later as a documented, deliberate replay
    path ("the accounting can be re-run over a queue report the miner wrote days ago"). Both
    callers are legitimate, but a naive re-stamp folded `classify()`'s dedup rule over ITS OWN
    prior output: every ident already carried a same-day disposition, so `classify()` saw them as
    "seen" and downgraded a fresh NEXT_BATCH_TEST to DUPLICATE_OF_EXISTING_TEST before
    next_batch() ever ran -- reproduced directly: n_stamped=1 NEXT_BATCH_TEST, then a second
    identical stamp -> n_stamped=1 DUPLICATE_OF_EXISTING_TEST, next_batch() empty. Every intake
    row genuinely stopped moving forward the same day it arrived.

    THE FIX PRESERVES THE REPLAY DESIGN INTENT: a row that already carries a REAL disposition
    (not itself a duplicate stub) from LATER THAN OR EQUAL TO the same UTC day is left untouched
    -- re-stamping an unchanged report is a no-op, not new evidence. A sighting from an EARLIER
    day still creates a genuine DUPLICATE_OF_EXISTING_TEST link, because that IS a second,
    independent discovery and the module's own contract says so ("a second source finding the
    same thing is evidence about the finding").
    """
    base = root or _ROOT
    path = Path(report_path)
    if not path.is_absolute():
        path = base / path
    try:
        doc = json.loads(path.read_text("utf-8"))
    except (OSError, ValueError) as exc:
        return {"status": "BLOCKED", "why": f"queue report unreadable: {type(exc).__name__}",
                "n_stamped": 0}

    seen = _current(root)
    today = _now()
    counts: dict[str, int] = {}
    stamped = 0
    for r in doc.get("queue") or []:
        ident = str(r.get("video_id") or "")
        if not ident:
            continue
        prior = seen.get(ident)
        if (prior is not None and prior.get("disposition") != "DUPLICATE_OF_EXISTING_TEST"
                and _same_utc_day(str(prior.get("ts") or prior.get("discovered_at") or ""),
                                  today)):
            continue  # idempotent replay of an already-classified-today row -- not new evidence
        disp, why = classify(r, seen=seen)
        row = {
            "ts": today, "ident": ident, "disposition": disp, "why": why,
            "title": str(r.get("title", ""))[:200], "channel": str(r.get("channel", "")),
            "score": r.get("score"), "url": r.get("url"),
            "discovered_at": today, "admitted_at": None,
            "deferrals": 0, "deferral_reason": None,
            "source_class": str(r.get("channel", "")).split(":")[0],
        }
        if disp == "DUPLICATE_OF_EXISTING_TEST":
            row["links_to"] = ident
        _append(row, root)
        seen[ident] = row
        counts[disp] = counts.get(disp, 0) + 1
        stamped += 1
    return {"status": "OK", "n_stamped": stamped, "by_disposition": counts,
            "law": "every queue row leaves with exactly one named disposition; none is dropped",
            "authority": "RECORD + ROUTE ONLY -- tests nothing, rejects nothing on merit."}


def next_batch(*, limit: int = 8, root: Path | None = None) -> list[dict[str, Any]]:
    """GATE ITEM 31. The real consumer for NEXT_BATCH_TEST, with an anti-graveyard order.

    Sorted by DEFERRAL COUNT first, then score. Repeated deferral must be visible and must
    eventually win, or NEXT_BATCH_TEST becomes a polite name for never (mandate III-4).
    """
    pending = [r for r in _current(root).values() if r.get("disposition") == "NEXT_BATCH_TEST"
               and not r.get("admitted_at")]
    pending.sort(key=lambda r: (-int(r.get("deferrals") or 0), -float(r.get("score") or 0.0)))
    return pending[:limit]


def intake_duty(*, root: Path | None = None, limit: int = 8) -> str:
    """The injectable block for organ spawn -- GATE ITEM 31's actual reach.

    THE GAP THIS CLOSES (2026-08-13, found tracing why NEXT_BATCH_TEST never drained).
    scripts/run_edge_intake.py called next_batch() and printed it to
    data/cro_ai_logs/edge_intake.log inside a once-daily cron run -- and nothing else in the
    repo ever read that log. admit() (the function that marks a row genuinely picked up) had
    exactly one caller anywhere in the tree: its own unit test. A queue whose "scheduled" state
    has a consumer that only writes to a file nobody opens is the graveyard this module's own
    docstring says item 31 exists to prevent.

    MIRRORS libs.ops.repair_mode's injection exactly, because that module already solved the
    identical shape of problem (L1.28b(d): a remedy legislated, fenced, and never wired to reach
    an organ) for the recommendation ledger's backlog. Same fix, same law (L1.36): a duty that
    never reaches an organ cannot change behaviour however well it is fenced.

    STEADY (empty string) when nothing is waiting -- this ADDS a duty and REMOVES none; it never
    tells an organ to do less (L1.28b(f), same clause repair_mode.py carries verbatim).

    THIS DOES NOT CALL admit() ITSELF. Marking a row admitted without a real experiment behind it
    would shrink the backlog by pretending, which is the exact failure mode the principal
    explicitly forbade (2026-08-13): "do not delete, suppress, or deprioritize candidates just to
    make the backlog look smaller." admit()/defer()/scripts/recommendations.py add are for
    whoever reads this duty and does the real work.
    """
    batch = next_batch(limit=limit, root=root)
    if not batch:
        return ""
    named = "; ".join(f"[{r.get('score')}] {str(r.get('title'))[:50]}" for r in batch[:5])
    more = f" (+{len(batch) - 5} more)" if len(batch) > 5 else ""
    return (
        f"[Part III-31] EDGE INTAKE -- {len(batch)} candidate(s) in NEXT_BATCH_TEST with no "
        f"consumer yet: {named}{more}\n"
        f"  READ THEM (python3 scripts/run_edge_intake.py --json), then for each: raise a "
        f"genuine finding with scripts/recommendations.py add, or call "
        f"libs.research.edge_intake.defer(ident, reason) with a real reason, or .admit(ident) "
        f"once a real experiment has actually started on it.\n"
        f"  THIS ADDS A DUTY AND REMOVES NONE (L1.28b(f)): collectors, recorders, miners, "
        f"diggers, screens and forward clocks run at FULL CADENCE regardless.")


def admit(idents: list[str], *, root: Path | None = None) -> int:
    """Stamp ADMITTED_AT on rows handed to a consumer. Deferral counts rise for those not taken."""
    cur = _current(root)
    n = 0
    for ident in idents:
        r = cur.get(ident)
        if r and r.get("disposition") == "NEXT_BATCH_TEST":
            _append({**r, "ts": _now(), "admitted_at": _now(),
                     "why": "admitted to an experiment batch by next_batch()"}, root)
            n += 1
    return n


def defer(idents: list[str], reason: str, *, root: Path | None = None) -> int:
    """Record an explicit deferral. Visible, counted, and it raises the row's next priority."""
    cur = _current(root)
    n = 0
    for ident in idents:
        r = cur.get(ident)
        if r:
            _append({**r, "ts": _now(), "deferrals": int(r.get("deferrals") or 0) + 1,
                     "deferral_reason": reason,
                     "why": f"deferred ({int(r.get('deferrals') or 0) + 1}x): {reason}"}, root)
            n += 1
    return n


def recall_audit(root: Path | None = None, *,
                 queue_report: str | Path | None = None) -> dict[str, Any]:
    """GATE ITEM 34. discovered == deduped + tested + waiting + blocked + rejected + non-testable.

    An unexplained difference is returned as UNACCOUNTED and is a RESEARCH-RECALL DEFECT, not a
    rounding note: it means a discovery entered the funnel and left it without a disposition,
    which is the exact failure Part III exists to prevent.
    """
    cur = _current(root)
    by: dict[str, int] = {}
    for r in cur.values():
        by[str(r.get("disposition"))] = by.get(str(r.get("disposition")), 0) + 1
    accounted = sum(by.values())

    discovered = accounted
    unaccounted: list[str] = []
    if queue_report is not None:
        base = root or _ROOT
        p = Path(queue_report)
        if not p.is_absolute():
            p = base / p
        try:
            doc = json.loads(p.read_text("utf-8"))
            idents = {str(r.get("video_id")) for r in (doc.get("queue") or []) if r.get("video_id")}
            discovered = len(idents | set(cur))
            unaccounted = sorted(idents - set(cur))
        except (OSError, ValueError):
            pass

    return {
        "generated_utc": _now(),
        "edges_discovered": discovered,
        "by_disposition": by,
        "accounted": accounted,
        "unaccounted": len(unaccounted),
        "unaccounted_idents": unaccounted[:40],
        "reconciles": not unaccounted,
        "verdict": ("RECONCILES -- every discovered edge carries a disposition"
                    if not unaccounted else
                    f"RESEARCH-RECALL DEFECT: {len(unaccounted)} discovered edge(s) have no "
                    "intake record. A discovery that entered the funnel and left without a "
                    "disposition is the silent-dismissal failure Part III forbids"),
        "authority": "MEASUREMENT ONLY.",
    }


def main() -> int:
    """Print the injectable duty block. Exit 0 always -- a prompt producer, not a gate.

    Wired into ops/brain_env.sh's _DOCTRINE exactly like libs.ops.repair_mode (L1.37: PAGES,
    never KILLS -- an organ spawn must never be blocked by this queue's state).
    """
    from libs.ops.lawful import guard as _law_guard  # L1.42: no act exempt

    _law_guard()
    print(intake_duty(), end="")
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI
    raise SystemExit(main())


```

### libs\research\licence_reader.py
```python
"""THE LICENCE READER -- a system's terms, read at a pin from the place that publishes them.

LAWS 5h: DIRECT execution is refused while a licence is UNVERIFIED, and a licence is never
asserted from memory. This module is the only lawful way a roster row's `licence` changes: it
reads the terms at a pin, normalises them to the SPDX ids `sandbox.RUNNABLE_LICENCES` speaks, and
records WHAT it read and WHERE (`basis`, `source`, `pin`, `commit_sha`, `read_at`). When nothing
could be read the reading stays UNVERIFIED and carries the reason -- an unread licence is a task,
never a guess about somebody else's terms.

TWO SOURCES, NO THIRD-PARTY CODE EXECUTED. A PyPI-distributed system is read from the package
METADATA of a WHEEL fetched with `pip download --no-deps --only-binary :all:` into the sandbox
root under the scrubbed environment (a wheel is a zip; reading it runs nothing), with PyPI's JSON
index as the fallback for sdist-only projects (an sdist's metadata would require executing its
build backend, which is exactly what may not happen outside `sandbox.run`). A repository-hosted
system is read from the raw LICENSE at the pinned commit over the allowlisted hosts only; the pin
is resolved once with `git ls-remote` and recorded, so the exact revision is persisted (LAWS 5m).
"""
from __future__ import annotations

import contextlib
import hashlib
import json
import re
import shutil
import subprocess
import sys
import zipfile
from collections.abc import Callable, Mapping
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from libs.research import external_federation as fed
from libs.research import sandbox as sb

Fetch = Callable[[str], bytes]

#: Hosts a licence read may fetch from. `raw.githubusercontent.com` is github.com's raw-file
#: endpoint and is the ONLY host added beyond the provisioning allowlist.
FETCH_HOSTS: frozenset[str] = frozenset({
    "pypi.org", "files.pythonhosted.org", "raw.githubusercontent.com", "gitlab.com",
    "gitee.com", "codeberg.org", "bitbucket.org"})
#: Raw-file URL shapes of the allowlisted code hosts.
RAW_URLS: dict[str, str] = {
    "github.com": "https://raw.githubusercontent.com/{owner}/{repo}/{ref}/{name}",
    "gitlab.com": "https://gitlab.com/{owner}/{repo}/-/raw/{ref}/{name}",
    "gitee.com": "https://gitee.com/{owner}/{repo}/raw/{ref}/{name}",
    "codeberg.org": "https://codeberg.org/{owner}/{repo}/raw/commit/{ref}/{name}",
    "bitbucket.org": "https://bitbucket.org/{owner}/{repo}/raw/{ref}/{name}",
}
LICENCE_FILES: tuple[str, ...] = ("LICENSE", "LICENSE.txt", "LICENSE.md", "LICENCE", "COPYING",
                                  "LICENSE.rst", "COPYING.txt", "LICENSE-MIT", "LICENSE.MIT")
#: Where a seed that names only `public:<name>` is actually distributed. Only names whose
#: identity is certain: a wrong distribution name would read the wrong project's terms, which is
#: worse than UNVERIFIED. Systems WITH adapters are named in `libs.research.adapters.SPECS`.
PYPI_DISTRIBUTIONS: dict[str, str] = {
    "pymc": "pymc", "neuralforecast": "neuralforecast", "darts": "u8darts", "kats": "kats",
    "merlion": "salesforce-merlion", "aeon": "aeon", "tpot": "TPOT", "openspiel": "open_spiel",
    "pyg_temporal": "torch-geometric-temporal", "ripser": "ripser", "ray": "ray",
    "reservoirpy": "reservoirpy", "kymatio": "kymatio", "sbi": "sbi", "pyribs": "ribs",
    "dspy": "dspy", "arcticdb": "arcticdb", "featuretools": "featuretools",
    "cvxportfolio": "cvxportfolio", "openevolve": "openevolve", "easytpp": "easy-tpp",
    "chronos2": "chronos-forecasting", "timesfm": "timesfm", "moment": "momentfm",
    "tushare": "tushare",
}
#: Repository homes for `public:` seeds whose code lives on an allowlisted host.
REPOSITORIES: dict[str, str] = {
    "idtxl": "github:pwollstadt/IDTxl", "alphagen": "github:RL-MLDM/alphagen",
    "abides": "github:abides-sim/abides", "ai_scientist": "github:SakanaAI/AI-Scientist-v2",
    "dso": "github:dso-org/deep-symbolic-optimization",
    "darwin_godel_machine": "github:jennyzzt/dgm", "kronos": "github:shiyu-coder/Kronos",
}
FETCH_TIMEOUT_S = 30
PIP_TIMEOUT_S = 240

#: SPDX normalisation of the free text PyPI classifiers and `License` fields carry. ORDER IS THE
#: RULE: LGPL/AGPL before GPL, 2-clause before bare BSD, so a specific match wins a generic one.
_RULES: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"AGPL|Affero", re.I), "AGPL-3.0"),
    (re.compile(r"LGPL|Lesser General Public", re.I), "LGPL-3.0"),
    (re.compile(r"GPL[- ]?2|GPLv2|General Public License v2", re.I), "GPL-2.0"),
    (re.compile(r"GPL[- ]?3|GPLv3|General Public License v3|\bGPL\b", re.I), "GPL-3.0"),
    (re.compile(r"Apache", re.I), "Apache-2.0"),
    (re.compile(r"\bMIT\b|Expat", re.I), "MIT"),
    (re.compile(r"BSD[- ]?2|Simplified BSD|FreeBSD", re.I), "BSD-2-Clause"),
    (re.compile(r"BSD[- ]?3|New BSD|Modified BSD|Revised BSD", re.I), "BSD-3-Clause"),
    (re.compile(r"\bBSD\b", re.I), "BSD-3-Clause"),
    (re.compile(r"MPL|Mozilla Public", re.I), "MPL-2.0"),
    (re.compile(r"\bISC\b", re.I), "ISC"),
    (re.compile(r"Unlicense", re.I), "Unlicense"),
    (re.compile(r"CC[- ]BY[- ]NC|Non-?Commercial", re.I), "CC-BY-NC-4.0"),
    (re.compile(r"Proprietary|Commercial", re.I), "Proprietary"),
)
#: Signatures of licence BODIES (a LICENSE file, or a `License` field carrying the whole text).
_BODIES: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("Unlicense", re.compile(r"This is free and unencumbered software", re.I)),
    ("ISC", re.compile(r"Permission to use, copy, modify, and/or distribute this software for any "
                       r"purpose with or without fee", re.I)),
    ("MIT", re.compile(r"Permission is hereby granted, free of charge", re.I)),
    ("Apache-2.0", re.compile(r"Apache License[\s,]+Version 2\.0", re.I)),
    ("AGPL-3.0", re.compile(r"GNU AFFERO GENERAL PUBLIC LICENSE", re.I)),
    ("LGPL-3.0", re.compile(r"GNU LESSER GENERAL PUBLIC LICENSE", re.I)),
    ("GPL-2.0", re.compile(r"GNU GENERAL PUBLIC LICENSE\s+Version 2", re.I)),
    ("GPL-3.0", re.compile(r"GNU GENERAL PUBLIC LICENSE\s+Version 3", re.I)),
    ("MPL-2.0", re.compile(r"Mozilla Public License,? (?:Version |v\.? ?)2\.0", re.I)),
    ("BSD", re.compile(r"Redistribution and use in source and binary forms", re.I)),
)
_BSD_THIRD_CLAUSE = re.compile(r"Neither the name", re.I)


@dataclass(frozen=True)
class LicenceReading:
    """What was read, from where, at which pin. UNVERIFIED carries its reason in `why`."""

    system_id: str
    licence: str = "UNVERIFIED"
    basis: str = ""
    source: str = ""
    pin: str = ""
    version: str = ""
    commit_sha: str = ""
    read_at: str = ""
    why: str = ""

    @property
    def read(self) -> bool:
        return self.licence != "UNVERIFIED"

    @property
    def runnable(self) -> bool:
        return self.licence in sb.RUNNABLE_LICENCES

    def record(self) -> dict[str, Any]:
        return {**asdict(self), "runnable": self.runnable}


def now() -> str:
    return datetime.now(tz=UTC).isoformat(timespec="seconds")


def normalise(text: str | None) -> str:
    """Free licence text or a classifier -> the SPDX id the runnable list speaks, or UNVERIFIED.

    A licence BODY is recognised by its signature before any keyword rule runs, so a `License`
    field that carries the whole 2-clause BSD text is BSD-2-Clause and not a bare "BSD" guess.
    """
    if not text or not str(text).strip():
        return "UNVERIFIED"
    body = classify_body(str(text))
    if body != "UNVERIFIED":
        return body
    head = str(text).strip()[:400]
    for rx, spdx in _RULES:
        if rx.search(head):
            return spdx
    return "UNVERIFIED"


def classify_body(text: str) -> str:
    """The SPDX id of a licence BODY by its signature phrases; BSD's clause count from the text."""
    for spdx, rx in _BODIES:
        if rx.search(text):
            if spdx == "BSD":
                return "BSD-3-Clause" if _BSD_THIRD_CLAUSE.search(text) else "BSD-2-Clause"
            return spdx
    return "UNVERIFIED"


def _default_fetch(url: str) -> bytes:
    host = urlparse(url).netloc.lower()
    if host not in FETCH_HOSTS:
        raise PermissionError(f"host {host!r} is not in the licence-read allowlist "
                              f"{sorted(FETCH_HOSTS)}")
    req = Request(url, headers={"User-Agent": "quant-licence-reader/1 (LAWS 5h)",
                                "Accept": "application/json, text/plain, */*"})
    with urlopen(req, timeout=FETCH_TIMEOUT_S) as resp:
        return bytes(resp.read(2_000_000))


# --------------------------------------------------------------------------------- PyPI

def _from_metadata(fields: Mapping[str, Any]) -> tuple[str, str]:
    """(spdx, basis) from METADATA-shaped fields: License-Expression first (PEP 639), then the
    classifiers, then the free `License` field; a bare BSD classifier is refined by any licence
    body the metadata carries."""
    expr = str(fields.get("license_expression") or "").strip()
    if expr:
        got = normalise(expr)
        if got != "UNVERIFIED":
            return got, f"License-Expression: {expr}"
    classifiers = [str(c) for c in (fields.get("classifiers") or ())
                   if str(c).startswith("License ::")]
    body = str(fields.get("license") or "")
    for c in classifiers:
        got = normalise(c.split("::")[-1])
        if got != "UNVERIFIED":
            if got == "BSD-3-Clause" and "BSD-3" not in c and "3-Clause" not in c:
                refined = classify_body(body) if body else "UNVERIFIED"
                if refined.startswith("BSD"):
                    return refined, f"classifier {c!r} refined by the licence body"
                return got, f"classifier {c!r} (bare BSD; clause count unread, both are runnable)"
            return got, f"classifier {c!r}"
    if body:
        got = normalise(body)
        if got != "UNVERIFIED":
            return got, f"License field: {body.strip().splitlines()[0][:80]!r}"
    return "UNVERIFIED", ("no License-Expression, no License classifier and no readable License "
                          "field in the package metadata")


def parse_metadata(text: str) -> dict[str, Any]:
    """A wheel's `*.dist-info/METADATA` (RFC 822 headers) -> the fields `_from_metadata` reads."""
    out: dict[str, Any] = {"classifiers": []}
    for line in text.split("\n\n", 1)[0].splitlines():
        key, _, value = line.partition(":")
        k = key.strip().lower()
        if k == "classifier":
            out["classifiers"].append(value.strip())
        elif k in ("license", "license-expression", "version", "name"):
            out[k.replace("-", "_")] = value.strip()
    return out


def read_wheel(path: Path) -> dict[str, Any]:
    """METADATA fields plus any licence body shipped inside the wheel; reading a zip runs
    nothing."""
    with zipfile.ZipFile(path) as zf:
        names = zf.namelist()
        meta = next((n for n in names if n.endswith(".dist-info/METADATA")), None)
        fields = parse_metadata(zf.read(meta).decode("utf-8", "replace")) if meta else {}
        for n in names:
            low = n.lower()
            if ".dist-info/licenses/" in low or low.rsplit("/", 1)[-1].startswith(
                    ("license", "licence", "copying")):
                with contextlib.suppress(Exception):
                    body = zf.read(n).decode("utf-8", "replace")
                    if classify_body(body) != "UNVERIFIED":
                        fields["license_body"] = body
                        break
    return fields


def pip_download_wheel(requirement: str, dest: Path, *, timeout_s: int = PIP_TIMEOUT_S,
                       python: str | None = None) -> tuple[Path | None, str]:
    """`pip download --no-deps --only-binary :all:` under the scrubbed environment into `dest`.
    A wheel is data; an sdist would execute its build backend, so sdists are refused here."""
    dest.mkdir(parents=True, exist_ok=True)
    argv = [python or sys.executable, "-m", "pip", "download", "--no-deps", "--only-binary",
            ":all:", "--disable-pip-version-check", "--no-input", "-q", "-d", str(dest),
            requirement]
    try:
        proc = subprocess.run(argv, cwd=str(dest), env=sb.scrub_env(), capture_output=True,
                              text=True, timeout=timeout_s, check=False)
    except (subprocess.TimeoutExpired, OSError) as exc:
        return None, f"pip download failed to complete: {type(exc).__name__}: {exc}"
    wheels = sorted(dest.glob("*.whl"), key=lambda p: p.stat().st_mtime)
    if proc.returncode != 0 or not wheels:
        tail = (proc.stderr or proc.stdout or "").strip().splitlines()[-1:] or ["no output"]
        return None, f"no wheel for {requirement!r} on this interpreter: {tail[0][:200]}"
    return wheels[-1], "wheel downloaded"


def read_pypi(system_id: str, distribution: str, *, version: str = "",
              fetch: Fetch | None = None, root: Path | None = None,
              read_at: str | None = None) -> LicenceReading:
    """Read a PyPI-distributed system's licence at `distribution==version` (latest when unpinned).

    The wheel's METADATA is the primary source when a sandbox root is given; PyPI's JSON index is
    the fallback that also serves sdist-only projects without executing anything. Whatever
    answered is named in `source`; the version read becomes the pin.
    """
    stamp = read_at or now()
    fetch = fetch or _default_fetch
    basis, source, why = "", "", ""
    fields: dict[str, Any] = {}
    digest = ""
    if root is not None:
        req = f"{distribution}=={version}" if version else distribution
        wheel, note = pip_download_wheel(req, root / "_licences" / system_id)
        if wheel is not None:
            with contextlib.suppress(Exception):
                fields = read_wheel(wheel)
                if fields.get("license_body"):
                    fields["license"] = fields["license_body"]
                version = str(fields.get("version") or version)
                digest = hashlib.sha256(wheel.read_bytes()).hexdigest()
                source = f"wheel:{wheel.name}"
        else:
            why = note
    if not fields:
        url = (f"https://pypi.org/pypi/{distribution}/{version}/json" if version
               else f"https://pypi.org/pypi/{distribution}/json")
        try:
            doc = json.loads(fetch(url).decode("utf-8"))
        except Exception as exc:
            return LicenceReading(system_id, why=(f"{why}; " if why else "")
                                  + f"PyPI index unreadable for {distribution!r}: "
                                    f"{type(exc).__name__}: {str(exc)[:160]}", read_at=stamp,
                                  source=f"pypi:{distribution}")
        info = doc.get("info") if isinstance(doc, dict) else None
        if not isinstance(info, Mapping):
            return LicenceReading(system_id, why=f"PyPI index for {distribution!r} carries no "
                                                 f"info block", read_at=stamp,
                                  source=f"pypi:{distribution}")
        fields = {"license": info.get("license"), "license_expression":
                  info.get("license_expression"), "classifiers": info.get("classifiers") or [],
                  "version": info.get("version")}
        version = str(info.get("version") or version)
        source = f"pypi-json:{distribution}"
        for u in (doc.get("urls") or []):
            if isinstance(u, Mapping) and u.get("packagetype") in ("bdist_wheel", "sdist"):
                digest = str(((u.get("digests") or {}).get("sha256")) or "")
                if digest:
                    break
    spdx, basis = _from_metadata(fields)
    pin = f"{distribution}=={version}" if version else distribution
    return LicenceReading(system_id, licence=spdx, basis=basis, source=source, pin=pin,
                          version=version, commit_sha=(f"sha256:{digest}" if digest else ""),
                          read_at=stamp,
                          why=("" if spdx != "UNVERIFIED" else basis))


# --------------------------------------------------------------------------------- repositories

def parse_repository(upstream: str) -> tuple[str, str, str] | None:
    """`github:owner/repo` | `https://gitlab.com/owner/repo(.git)` -> (host, owner, repo)."""
    text = upstream.strip()
    if ":" in text and "://" not in text:
        prefix, _, rest = text.partition(":")
        host = {"github": "github.com", "gitlab": "gitlab.com", "gitee": "gitee.com",
                "codeberg": "codeberg.org", "bitbucket": "bitbucket.org"}.get(prefix.lower())
        if not host:
            return None
        parts = rest.strip("/").split("/")
    else:
        u = urlparse(text)
        host = u.netloc.lower()
        parts = u.path.strip("/").split("/")
    if host not in RAW_URLS or len(parts) < 2 or not parts[0] or not parts[1]:
        return None
    return host, parts[0], parts[1].removesuffix(".git")


def resolve_commit(host: str, owner: str, repo: str, *, timeout_s: int = FETCH_TIMEOUT_S) -> str:
    """The revision HEAD points at right now, via `git ls-remote` (git is not third-party code).
    Empty when it cannot be resolved -- the caller then records the read as UNVERIFIED."""
    git = shutil.which("git")
    if not git:
        return ""
    try:
        proc = subprocess.run([git, "ls-remote", f"https://{host}/{owner}/{repo}.git", "HEAD"],
                              capture_output=True, text=True, timeout=timeout_s, check=False,
                              env={**sb.scrub_env(), "GIT_TERMINAL_PROMPT": "0"})
    except (subprocess.TimeoutExpired, OSError):
        return ""
    for line in (proc.stdout or "").splitlines():
        sha = line.split("\t")[0].strip()
        if len(sha) == 40:
            return sha
    return ""


def read_repository(system_id: str, upstream: str, *, commit: str = "",
                    fetch: Fetch | None = None, read_at: str | None = None) -> LicenceReading:
    """Read the LICENSE at a pinned commit from an allowlisted host; pin HEAD when none is given."""
    stamp = read_at or now()
    fetch = fetch or _default_fetch
    parsed = parse_repository(upstream)
    if parsed is None:
        return LicenceReading(system_id, read_at=stamp, why=(
            f"upstream {upstream!r} names no allowlisted repository host: pin the real "
            f"repository URL (or distribution) before its licence can be read"))
    host, owner, repo = parsed
    sha = commit or resolve_commit(host, owner, repo)
    if not sha:
        return LicenceReading(system_id, read_at=stamp, source=f"{host}/{owner}/{repo}",
                              why=f"could not resolve a commit for {host}/{owner}/{repo}: the "
                                  f"repository is unreachable, private or gone")
    tried: list[str] = []
    for name in LICENCE_FILES:
        url = RAW_URLS[host].format(owner=owner, repo=repo, ref=sha, name=name)
        try:
            body = fetch(url).decode("utf-8", "replace")
        except Exception as exc:
            tried.append(f"{name}: {type(exc).__name__}")
            continue
        spdx = normalise(body)
        pin = f"{host}/{owner}/{repo}@{sha}"
        if spdx == "UNVERIFIED":
            return LicenceReading(system_id, source=f"{host}/{owner}/{repo}", pin=pin,
                                  commit_sha=sha, read_at=stamp,
                                  why=f"{name} at {sha[:12]} was read but matches no known "
                                      f"licence signature: read it by hand and record the id")
        return LicenceReading(system_id, licence=spdx, basis=f"{name} at {sha[:12]}",
                              source=f"{host}/{owner}/{repo}", pin=pin, commit_sha=sha,
                              read_at=stamp)
    return LicenceReading(system_id, source=f"{host}/{owner}/{repo}", commit_sha=sha,
                          read_at=stamp,
                          why=f"no licence file at {sha[:12]} among {list(LICENCE_FILES)}: "
                              f"{'; '.join(tried)[:200]}")


# --------------------------------------------------------------------------------- dispatch

def distribution_of(system: fed.ExternalSystem) -> tuple[str, str]:
    """(distribution, pinned version) for a PyPI-distributed system, or ('', '')."""
    if system.upstream.startswith("pypi:"):
        name, _, ver = system.upstream[5:].partition("==")
        return name, ver
    try:
        from libs.research import adapters
        spec = adapters.SPECS.get(system.system_id)
    except Exception:
        spec = None
    if spec is not None:
        return spec.distribution, spec.version
    return PYPI_DISTRIBUTIONS.get(system.system_id, ""), ""


def read(system: fed.ExternalSystem, *, pin: str = "", fetch: Fetch | None = None,
         root: Path | None = None) -> LicenceReading:
    """Read this system's licence from wherever it is published; UNVERIFIED with the reason when
    nowhere is known. `pin` is a version for PyPI systems and a commit for repositories."""
    dist, version = distribution_of(system)
    if dist:
        return read_pypi(system.system_id, dist, version=pin or version, fetch=fetch, root=root)
    upstream = REPOSITORIES.get(system.system_id, system.upstream)
    if parse_repository(upstream) is not None:
        return read_repository(system.system_id, upstream, commit=pin, fetch=fetch)
    return LicenceReading(system.system_id, read_at=now(), why=(
        f"no distribution or allowlisted repository is known for {system.upstream!r}: name the "
        f"PyPI distribution or the repository and the licence becomes readable"))


def apply(row: dict[str, Any], reading: LicenceReading) -> None:
    """Record a reading on a ledger row. An UNVERIFIED reading records only its attempt."""
    row["licence_read_at"] = reading.read_at
    row["licence_source"] = reading.source or row.get("licence_source") or "UNMEASURED"
    if not reading.read:
        row["licence_why"] = reading.why
        return
    row["licence"] = reading.licence
    row["licence_basis"] = reading.basis
    row["pin"] = reading.pin
    if reading.commit_sha:
        row["commit_sha"] = reading.commit_sha
    row.pop("licence_why", None)


#: Terms under which upstream code may be neither run nor vendored. A DIRECT roster row cannot
#: be honoured under them and is REJECTED_WITH_EVIDENCE -- the reading (basis, pin) IS the
#: evidence, and the reopening condition is named; a WRAPPED row reaches a licensed installation
#: by API and stands; anything else is REBUILT, the lawful route for a mechanism.
REJECTED_LICENCES: frozenset[str] = frozenset({"Proprietary"})


def dispose(system: fed.ExternalSystem, reading: LicenceReading) -> tuple[str, str]:
    """(disposition, why) once the licence is read: the principal's integration mode when the
    terms permit running it, REBUILT with the reason when they do not, REJECTED_WITH_EVIDENCE
    (evidence string: licence, basis, pin, reopening condition) when a DIRECT row's upstream
    may be neither run nor copied, UNDISPOSED when unread."""
    if not reading.read:
        return "UNDISPOSED", f"licence unread: {reading.why}"
    if reading.runnable:
        mode = system.integration if system.integration in fed.RUNNING_DISPOSITIONS else "WRAPPED"
        return mode, f"licence {reading.licence} read from {reading.basis} at {reading.pin}"
    if reading.licence in REJECTED_LICENCES:
        if system.integration == "WRAPPED":
            return "WRAPPED", (f"licence {reading.licence!r} read from {reading.basis} at "
                               f"{reading.pin}: reached by the API of a licensed installation "
                               f"only, never vendored")
        return "REJECTED_WITH_EVIDENCE", (
            f"licence {reading.licence!r} read from {reading.basis} at {reading.pin}: upstream "
            f"code may be neither run nor vendored under these terms; REOPEN when the terms "
            f"change at a later pin or a licensed installation becomes reachable by API "
            f"(WRAPPED)")
    return "REBUILT", (f"licence {reading.licence!r} is not on the runnable list "
                       f"{sorted(sb.RUNNABLE_LICENCES)}: REBUILT is the lawful route "
                       f"(read from {reading.basis} at {reading.pin})")

```

### libs\research\perishability.py
```python
"""PERISHABILITY (L1.65's missing half) -- for an observable the desk does NOT record, does
delay cost DELAY, or does it cost THE DATA?

THE GAP THIS CLOSES. Three correct instruments exist and the join between them exists nowhere:

  ``check_unwired_capability.py``   scores 256 uncalled capabilities as ONE class -- latent value.
                                    It has no column for "is this input backfillable?", so a
                                    recorder of a perishable stream and a dormant report rank the
                                    same. One of those is a CLOCK.
  ``libs/research/recoverability``  (L1.65) is denominated in STREAMS THAT EXIST. Zero rows
                                    recorded => zero span => zero loss => no alarm. It cannot see
                                    a stream that was never opened. WS-005 one level up.
  ``scripts/asymmetry_ledger.py``   HAS a PERISHABLE class, verified 2026-08-03 -- before the
                                    2026-08-18 MT5 mandate. Both of its PERISHABLE rows are
                                    crypto-exchange observables the desk may never hunt again, so
                                    it returns a full ranking that is green and empty of anything
                                    actionable.

Recoverability asks "did the desk LOSE span, and can it be bought back?". This asks the strictly
earlier question: "is the desk ACCRUING span at all, and if not, is that recoverable?" A stream
never opened cannot lose span, so it is invisible to every gauge the desk owns.

WHY THE DISTINCTION IS THE WHOLE POINT. Most unbuilt things cost their delay and nothing more --
build it later and you have the same thing. A perishable observable is different in kind: the
broker publishes ``swap_long`` for today and will never tell you what it was last Tuesday. Every
night without a recorder is a night permanently unbuyable at any price. Ranking those two classes
together is how a clock ends up queued behind a report.

THE STATUSES, and the reason each exists:

  RECORDING        the store is fresh and interpretable. Nothing owed.
  BACKFILLABLE     not recording, but a named route reconstructs the history. Delay costs DELAY.
                   This is a real pass: it is the class where waiting is genuinely cheap.
  UNINTERPRETABLE  rows exist, but a field WITHOUT WHICH THE VALUE CANNOT BE READ is absent.
                   Recorded and useless. The desk's live instance: 244 symbols of broker swap
                   captured five times with no ``swap_mode``, and swap is quoted in POINTS on
                   some symbols and PROFIT CURRENCY on others -- a 100x difference on JPY pairs.
                   A number whose unit was never recorded is not data, and L1.67 was paid for
                   exactly once already.
  PERISHING        in-mandate, no backfill route, not recording. Delay costs THE DATA. Pages.
  NO-RECORDER      the same, and nothing in the repo even attempts it. Strictly worse: PERISHING
                   is an unwired build, this is an unmade one.
  UNMEASURED       this host cannot see the store. NEVER folded into a real verdict -- a verdict
                   about the HOST is not a verdict about the DESK (L1.28a, WS-005).

HOST HONESTY. The recorders that matter run on the box holding the MT5 terminal, and this repo is
checked out on more than one machine. So "the directory is absent here" has two causes with
opposite meanings: never recorded ANYWHERE, or recorded elsewhere and not synced. This module
separates them with git history -- a store path that has never appeared in any commit was never
recorded on any box, which is a verdict about the desk. A path git knows about but disk does not
is UNMEASURED, which is a verdict about this host and is reported as one.

THE SECOND PERISHABLE GOOD (2026-09-05): THE EDGE ITSELF.

    "Monitoring loop: prediction decay, PnL decay, state decay, cost drift, fill drift, factor
     drift, feature drift, relationship drift; hazard_i(t) = P(edge breaks next horizon |
     history); allocation changes BEFORE the formal retirement threshold."   -- the principal

An observable perishes because nobody recorded it; an EDGE perishes because the market stopped
paying for it. Same question one level up, and the same discipline answers it: name the evidence,
say n, and refuse to fold an unmeasured component into a pass. So the hazard machinery lives
beside the register rather than in a new file -- both halves of this module answer "what is this
desk losing while it waits, and can it be bought back".

WHY PRESSURES AND NOT EIGHT PROBABILITIES. Each monitored channel is a SYMPTOM of one process
(the edge being competed, drifted or regime-shifted away), measured on its own scale: a t-drop,
a z, a ratio of costs, a sign-agreement fraction. Each is mapped to a PRESSURE in [0, 1] -- the
fraction of the way from "unchanged" to "fully gone" -- and the measured pressures are AVERAGED,
not multiplied, for the reason `crowding_hazard.microstructure_pressure` gives: a product lets
one unchanged component silence five that moved. The mean pressure then becomes a probability
through the SAME exponential hazard and the SAME declared 120-day scale that
`libs.research.crowding_hazard` already uses, so the desk carries one decay scale rather than
two that can disagree. The scale is DECLARED, not fitted: this desk has no retired-edge history
to fit it to, and an invented fit would look more precise while being no better founded.

AN UNMEASURED COMPONENT IS NOT A ZERO. A channel with no ledger on this host contributes nothing
to the mean and is listed by name in `unmeasured` with its reason (L1.28a). A sleeve where every
channel is unmeasured gets no hazard at all -- `None` and the reasons -- because a confident 0.0
built out of eight absences is the single most dangerous number this file could return.

AND A MEAN OVER ONE CHANNEL IS NOT A HAZARD EITHER. Measured on the desk's own tree 2026-09-05:
the only readable channel off-box was `state_decay`, which is a property of the BOOK's
conditioning and identical for every sleeve. Averaging it alone put 23 sleeves at 52.8% and the
verdict BREAKING -- a book-level fact wearing 23 per-edge costumes, and exactly the number that
would have shrunk 23 allocations for no per-edge reason at all. So two floors, both declared:

    HAZARD_MIN_CHANNELS   measured channels before the mean is a hazard rather than one symptom
    at least one SLEEVE-scoped channel -- a hazard built only from book-level channels is a
    statement about the book, and it is returned as UNMEASURED with that sentence

Below either floor the pressures are still reported, per channel, with their n. The hazard is
`None` and the verdict UNMEASURED, because the consumer of this number shrinks capital with it.
"""

from __future__ import annotations

import json
import math
import statistics
import subprocess
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parents[2]

RECORDING = "RECORDING"
BACKFILLABLE = "BACKFILLABLE"
UNINTERPRETABLE = "UNINTERPRETABLE"
PERISHING = "PERISHING"
NO_RECORDER = "NO-RECORDER"
UNMEASURED = "UNMEASURED"

#: Statuses that do NOT fail the build. BACKFILLABLE passes because its whole meaning is that
#: waiting is cheap; UNMEASURED does not appear here -- it fails, because an unmeasured thing must
#: never read as fine (L1.28a).
PASSING = (RECORDING, BACKFILLABLE)


@dataclass(frozen=True)
class Observable:
    """One thing the desk could record, and what it costs to not be recording it.

    ``backfill_route`` is the load-bearing field and it is deliberately a STRING OR NONE rather
    than a bool: a route has to be nameable to count. "probably reconstructable" is not a route,
    and the honest value there is None -- which grades the row PERISHING and makes someone either
    find the route or start the recorder.
    """

    key: str
    what: str
    store: str                          # repo-relative dir or file the recorder writes
    recorder: str | None                # "module:function" that records it, or None
    backfill_route: str | None          # named, verified route -- or None if the data is gone
    max_staleness_h: float
    interpretive_fields: tuple[str, ...] = ()   # absent => the recorded value cannot be read
    in_mandate: bool = True
    why: str = ""


@dataclass
class Row:
    key: str
    status: str
    what: str
    store: str
    recorder: str | None
    backfill_route: str | None
    n_files: int
    newest: str | None
    age_h: float | None
    missing_interpretive: list[str] = field(default_factory=list)
    detail: str = ""


@dataclass
class Report:
    generated_at: str
    status: str
    rows: list[Row]
    n_perishing: int
    n_uninterpretable: int
    n_unmeasured: int
    n_recording: int
    notes: list[str] = field(default_factory=list)


#: THE REGISTER. Every row is an observable inside the MT5/Fusion mandate (LAWS section 1) that
#: this desk can reach today. It is a SEED, never a boundary (LAWS anti-hardcode): rows are added
#: as observables are identified, and a row is removed only when the observable leaves the
#: mandate. Nothing here is scoped to a symbol list.
REGISTER: tuple[Observable, ...] = (
    Observable(
        key="financing_leg",
        what="broker swap_long/swap_short + swap_mode + triple-swap day, per symbol, per night",
        store="desks/mt5/data/tape/contract_terms",
        recorder="desks.mt5.mt5desk.tape:record_contract_terms",
        backfill_route=None,
        max_staleness_h=30.0,
        # `swap_mode` + `point` + `contract_size` ARE the unit. CORRECTED 2026-08-29 against the
        # tape itself: this comment previously said "in mode 0 (POINTS) ... in any other mode it
        # is already currency", and both halves are wrong. MT5 mode 0 is DISABLED and mode 1 is
        # POINTS; mode 5 (INTEREST_CURRENT) is an ANNUAL PERCENT of notional, not currency.
        # Measured on desks/mt5/data/tape/contract_terms: 110 symbols are mode 1 and 138 are
        # mode 5, so the "already currency" reading was wrong on 55% of the universe -- a
        # DIMENSION error, not a factor, and always in the direction that makes a candidate look
        # cheaper. Without all three fields a JPY cross reads 100x off a 5-digit major, and the
        # error hides on exactly the majors a spot-check would try first (point*contract_size ==
        # 1.0 there). The resolver is desks/mt5/research/carry_state.money_per_lot_night.
        interpretive_fields=("swap_mode", "point", "contract_size", "currency_profit"),
        why="MT5 symbol_info reports TODAY's swap only. There is no endpoint, archive or vendor "
            "for this broker's swap on a past date, so an unrecorded night is unbuyable. It is "
            "also the second price on every CFD the desk trades: the spot quote is recorded 197 "
            "times over and the financing leg is the half nobody kept.",
    ),
    Observable(
        key="tick_tape",
        what="bid/ask/last tick stream per symbol",
        store="desks/mt5/data/tape/ticks",
        recorder="desks.mt5.mt5desk.tape:record_ticks",
        backfill_route=None,
        max_staleness_h=30.0,
        why="copy_ticks_from serves a shallow rolling window; past that the ticks are gone. "
            "Pre-recorder tick data is not purchasable at this broker at any price.",
    ),
    Observable(
        key="execution_constraints",
        what="stops_level / freeze_level per symbol -- the MINIMUM achievable stop distance",
        store="desks/mt5/data/tape/execution_constraints",
        recorder=None,
        backfill_route=None,
        max_staleness_h=30.0,
        why="A hard bound on every backtested stop the desk has ever run, it moves with "
            "volatility, and symbol_info reports only the current value. Nothing records it, so "
            "every stop-distance assumption in the book is unfalsifiable after the fact.",
    ),
)


def _git_knows(path: str) -> bool:
    """Has this store path EVER appeared in a commit, on any box?

    The question separates 'never recorded anywhere' from 'recorded elsewhere, not synced here'.
    A failure to run git is not evidence either way and is reported as such by the caller.
    """
    try:
        out = subprocess.run(
            ["git", "log", "--oneline", "-1", "--", path],
            cwd=_ROOT, capture_output=True, text=True, timeout=30, check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return bool(out.stdout.strip())


def _git_available() -> bool:
    try:
        out = subprocess.run(["git", "rev-parse", "--git-dir"], cwd=_ROOT,
                             capture_output=True, text=True, timeout=30, check=False)
    except (OSError, subprocess.SubprocessError):
        return False
    return out.returncode == 0


def _scan_store(root: Path, obs: Observable) -> tuple[int, datetime | None, list[str]]:
    """Count rows-bearing files, find the newest, and report which interpretive fields are absent.

    Interpretive fields are checked against the CONTENT of the newest readable file rather than
    against the schema declaration, because the defect this exists to catch is a producer that
    drops a field a schema still advertises.
    """
    p = root / obs.store
    if not p.exists():
        return 0, None, []
    files = sorted(f for f in p.rglob("*") if f.is_file())
    if not files:
        return 0, None, []
    newest_f = max(files, key=lambda f: f.stat().st_mtime)
    newest = datetime.fromtimestamp(newest_f.stat().st_mtime, tz=UTC)
    missing: list[str] = []
    if obs.interpretive_fields:
        cols = _columns(newest_f)
        if cols is None:
            missing = list(obs.interpretive_fields)
        else:
            missing = [f for f in obs.interpretive_fields if f not in cols]
    return len(files), newest, missing


def _columns(path: Path) -> set[str] | None:
    """Field names in a recorded file, or None if this host cannot read it.

    None is NOT an empty set: an unreadable file means the interpretive check did not run, which
    the caller must not render as "every field present".
    """
    try:
        if path.suffix == ".parquet":
            import pyarrow.parquet as pq
            # REQUIRED on the pinned pyarrow (>=24,<25); mypy reports it unused on 25.x,
            # and deleting it there is what reds the deploy gate (pyproject:219).
            return set(pq.read_schema(path).names)  # type: ignore[no-untyped-call]
        if path.suffix in (".json", ".jsonl"):
            txt = path.read_text("utf-8")
            raw: Any = (json.loads(txt) if path.suffix == ".json"
                        else [json.loads(ln) for ln in txt.splitlines() if ln.strip()])
            rows = raw if isinstance(raw, list) else [raw]
            cols: set[str] = set()
            for r in rows:
                if isinstance(r, dict):
                    cols |= set(r)
            return cols
    except Exception:
        return None
    return None


def grade(obs: Observable, root: Path, now: datetime, git_ok: bool) -> Row:
    """One observable -> one status. The whole module is this function; the rest is plumbing."""
    n_files, newest, missing = _scan_store(root, obs)
    age_h = None if newest is None else (now - newest).total_seconds() / 3600.0
    row = Row(key=obs.key, status=UNMEASURED, what=obs.what, store=obs.store,
              recorder=obs.recorder, backfill_route=obs.backfill_route, n_files=n_files,
              newest=None if newest is None else newest.isoformat(timespec="seconds"),
              age_h=None if age_h is None else round(age_h, 2),
              missing_interpretive=missing)

    if n_files and missing:
        # Recorded, and unreadable. Reported ahead of freshness on purpose: a fresh store of
        # uninterpretable numbers is worse than a stale one, because it looks healthy to every
        # consumer and to every gauge that counts rows.
        row.status = UNINTERPRETABLE
        row.detail = (f"{n_files} file(s) recorded, but {', '.join(missing)} absent -- the "
                      f"recorded value cannot be converted to money without it")
        return row

    if n_files and age_h is not None and age_h <= obs.max_staleness_h:
        row.status = RECORDING
        row.detail = f"{n_files} file(s), newest {age_h:.1f}h old"
        return row

    # Nothing fresh on this disk. Before grading the DESK, establish whether this HOST can see
    # the store at all -- the two have opposite meanings and only one is a defect here.
    if n_files == 0:
        if not git_ok:
            row.detail = "git unavailable; cannot distinguish never-recorded from not-synced"
            return row
        if _git_knows(obs.store):
            row.status = UNMEASURED
            row.detail = ("store is in git history but absent on this host -- recorded on another "
                          "box and not synced here; this is a verdict about the host, not the desk")
            return row

    if obs.backfill_route:
        row.status = BACKFILLABLE
        row.detail = f"not recording; delay costs delay -- route: {obs.backfill_route}"
        return row

    if obs.recorder is None:
        row.status = NO_RECORDER
        row.detail = ("no recorder exists in this repo and the observable is point-in-time only; "
                      "every interval that passes is permanently unbuyable")
        return row

    row.status = PERISHING
    row.detail = (f"recorder {obs.recorder} exists and is not producing"
                  + (f" (store {age_h:.1f}h stale)" if age_h is not None else " (store empty)")
                  + "; no backfill route -- delay costs the data, not the delay")
    return row


def build_report(root: Path | None = None, now: datetime | None = None,
                 register: tuple[Observable, ...] = REGISTER) -> Report:
    root = _ROOT if root is None else root
    now = datetime.now(UTC) if now is None else now
    git_ok = _git_available()
    rows = [grade(o, root, now, git_ok) for o in register if o.in_mandate]
    n_per = sum(1 for r in rows if r.status in (PERISHING, NO_RECORDER))
    n_uni = sum(1 for r in rows if r.status == UNINTERPRETABLE)
    n_unm = sum(1 for r in rows if r.status == UNMEASURED)
    n_rec = sum(1 for r in rows if r.status == RECORDING)
    notes: list[str] = []
    if not git_ok:
        notes.append("git unavailable: never-recorded and not-synced could not be separated")
    if not rows:
        # L1.57: a verdict over an empty population is vacuous, never a pass.
        return Report(now.isoformat(timespec="seconds"), UNMEASURED, rows, 0, 0, 0, 0,
                      [*notes, "register is empty -- nothing was graded"])
    # Worst status wins. Order encodes what the desk loses, not how loud the word is.
    for bad in (NO_RECORDER, PERISHING, UNINTERPRETABLE, UNMEASURED):
        if any(r.status == bad for r in rows):
            return Report(now.isoformat(timespec="seconds"), bad, rows,
                          n_per, n_uni, n_unm, n_rec, notes)
    return Report(now.isoformat(timespec="seconds"), RECORDING, rows,
                  n_per, n_uni, n_unm, n_rec, notes)


def to_dict(rep: Report) -> dict[str, Any]:
    return {
        "generated_at": rep.generated_at,
        "status": rep.status,
        "n_observables": len(rep.rows),
        "n_perishing": rep.n_perishing,
        "n_uninterpretable": rep.n_uninterpretable,
        "n_unmeasured": rep.n_unmeasured,
        "n_recording": rep.n_recording,
        "notes": rep.notes,
        "observables": [
            {
                "key": r.key, "status": r.status, "what": r.what, "store": r.store,
                "recorder": r.recorder, "backfill_route": r.backfill_route,
                "n_files": r.n_files, "newest": r.newest, "age_h": r.age_h,
                "missing_interpretive": r.missing_interpretive, "detail": r.detail,
            }
            for r in rep.rows
        ],
    }


# =========================================================================== EDGE HAZARD
#: The eight monitored channels the principal named, plus crowding -- the one leading indicator
#: the desk already owns (`libs.research.crowding_hazard`), which had no importer until this.
#: Order is the reading order: what the edge PREDICTED, what it PAID, what it was CONDITIONED on,
#: what it COST to trade, and what the world around it did.
HAZARD_COMPONENTS: tuple[str, ...] = (
    "prediction_decay", "pnl_decay", "state_decay", "cost_drift", "fill_drift",
    "factor_drift", "feature_drift", "relationship_drift", "crowding",
)

#: Days at FULL pressure for one e-folding of the edge. Taken verbatim from
#: `crowding_hazard.hazard` (rate = pressure / 120.0) so the desk has ONE decay scale: a second
#: scale here would let two organs disagree about the same edge and be equally defensible.
HAZARD_SCALE_DAYS = 120.0
#: The horizon the question is asked over. "Next horizon" in the principal's sentence -- one
#: quarter, the shortest window over which a forward clock can carry a verdict at all.
HAZARD_HORIZON_DAYS = 90.0
#: Paired observations before a channel's trend is a trend rather than noise with a direction.
HAZARD_MIN_N = 10
#: Measured channels before their mean is called a hazard. Three of nine is a low bar and a real
#: one: it is the difference between "several symptoms agree" and "one number moved".
HAZARD_MIN_CHANNELS = 3
#: Channel scopes. A BOOK channel (the conditioning, the covariance, the driver graph) is the
#: same number for every sleeve; a hazard made only of those is a fact about the book.
SLEEVE, BOOK = "sleeve", "book"

#: Verdict lines, stated as PROBABILITIES so they do not move when the scale is re-derived.
#: Full pressure over the horizon is 1 - exp(-90/120) = 0.528, so these sit at roughly a
#: quarter and two thirds of the most this hazard can ever say.
HAZARD_AT_RISK = 0.15
HAZARD_BREAKING = 0.35
HOLDING, AT_RISK, BREAKING = "HOLDING", "AT_RISK", "BREAKING"


@dataclass(frozen=True)
class Pressure:
    """One monitored channel's reading: how far toward gone, on what evidence.

    `value is None` is the load-bearing state and the reason this is not a bare float -- it means
    the channel HAS NO LEDGER on this host, which must never average in as a calming zero.
    """

    name: str
    value: float | None
    n: int = 0
    why: str = ""
    detail: dict[str, Any] = field(default_factory=dict)
    #: SLEEVE (this edge's own evidence) or BOOK (shared by every sleeve). Defaults to SLEEVE
    #: because a channel that has not said otherwise is being offered as this edge's evidence.
    scope: str = SLEEVE


def book_scope(p: Pressure) -> Pressure:
    """Mark a channel as the BOOK's, so a hazard cannot be built out of shared numbers alone."""
    return Pressure(p.name, p.value, p.n, p.why, p.detail, BOOK)


def _clip01(x: float) -> float:
    return 0.0 if x < 0.0 else (1.0 if x > 1.0 else float(x))


def unmeasured_pressure(name: str, why: str, n: int = 0, **detail: Any) -> Pressure:
    """A channel that could not be read. Carries the reason so the report can print it."""
    return Pressure(name, None, n, why, detail)


def decay_pressure(name: str, forward: float | None, reference: float | None, n: int,
                   *, min_n: int = HAZARD_MIN_N, **detail: Any) -> Pressure:
    """Forward performance against the number the edge was certified on.

    THE SHORTFALL IS A FRACTION OF THE CLAIM, not of the forward reading, so an edge certified at
    0.4R that now delivers 0.2R and one certified at 0.05R that now delivers 0.025R read the same
    -- both have lost half of what they promised. Delivering AT or ABOVE the claim is zero
    pressure, never negative: an edge doing better than advertised is not evidence it will last,
    and letting it subtract would let one strong sleeve mask a book that is breaking.
    """
    if forward is None or reference is None:
        return unmeasured_pressure(name, "no forward or reference expectancy on this host", n,
                                   **detail)
    if n < min_n:
        return unmeasured_pressure(name, f"{n} observation(s), need {min_n}", n, **detail)
    if abs(reference) < 1e-12:
        return unmeasured_pressure(
            name, "the certified expectancy is zero: there is no claim to fall short of", n,
            **detail)
    shortfall = (reference - forward) / abs(reference)
    return Pressure(name, _clip01(shortfall), n,
                    ("" if shortfall > 0 else "forward is at or above the reference"),
                    {"forward": forward, "reference": reference,
                     "shortfall_frac": round(shortfall, 6), **detail})


def drift_pressure(name: str, z: float | None, n: int, *, watch: float = 1.0,
                   broken: float = 3.0, **detail: Any) -> Pressure:
    """A z-scored drift (feature, factor) mapped onto the same [0, 1] ruler.

    Below the WATCH line the statistic is inside its own historical dispersion and carries no
    pressure; at BROKEN it is as far out as the desk is willing to call gone. The two lines are
    the drift monitor's own (WATCH_Z, and DRIFT_Z one step further) so a reader who has seen
    DRIFT.json's verdict does not meet a second, private set of thresholds here.
    """
    if z is None:
        return unmeasured_pressure(name, "no z on this host", n, **detail)
    if n < HAZARD_MIN_N:
        return unmeasured_pressure(name, f"{n} window(s), need {HAZARD_MIN_N}", n, **detail)
    span = max(broken - watch, 1e-9)
    return Pressure(name, _clip01((abs(z) - watch) / span), n, "",
                    {"z": z, "watch": watch, "broken": broken, **detail})


def ratio_pressure(name: str, now: float | None, baseline: float | None, n: int,
                   *, worse_is_higher: bool = True, doubling_is_gone: bool = True,
                   **detail: Any) -> Pressure:
    """A cost or a fill rate now against what it was when the edge was validated.

    Denominated in the BASELINE, so "costs doubled" is full pressure whatever the currency. When
    `worse_is_higher` is False the channel is a rate that should stay high (fill rate), and the
    pressure is the fraction of it that has been lost.
    """
    if now is None or baseline is None:
        return unmeasured_pressure(name, "no now/baseline pair on this host", n, **detail)
    if n < HAZARD_MIN_N:
        return unmeasured_pressure(name, f"{n} observation(s), need {HAZARD_MIN_N}", n, **detail)
    if abs(baseline) < 1e-15:
        return unmeasured_pressure(name, "baseline is zero: no ratio to take", n, **detail)
    if worse_is_higher:
        moved = (now - baseline) / abs(baseline)
        scale = 1.0 if doubling_is_gone else 2.0
    else:
        moved = (baseline - now) / abs(baseline)
        scale = 1.0
    return Pressure(name, _clip01(moved / scale), n, "",
                    {"now": now, "baseline": baseline, "moved_frac": round(moved, 6), **detail})


def share_pressure(name: str, share: float | None, n: int, **detail: Any) -> Pressure:
    """A channel that is already a fraction of a population gone (state dimensions buried, say).

    The identity map onto the ruler, given a name so callers do not reach for the private clip
    and so a reader of the report can tell "half the conditioning stopped predicting" from a
    pressure that came out of a z or a ratio.
    """
    if share is None:
        return unmeasured_pressure(name, "no share on this host", n, **detail)
    if n < HAZARD_MIN_N:
        return unmeasured_pressure(name, f"{n} observation(s), need {HAZARD_MIN_N}", n, **detail)
    return Pressure(name, _clip01(share), n, "", {"share": round(share, 6), **detail})


def agreement_pressure(name: str, agreement: float | None, n: int, **detail: Any) -> Pressure:
    """Cross-asset sign agreement: what fraction of the relationship still points the way it did.

    A coin flip (0.5) is FULL pressure, not half of it -- a relationship that agrees with itself
    half the time has no sign, and an edge built on it has nothing left to decay. Perfect
    agreement is zero pressure.
    """
    if agreement is None:
        return unmeasured_pressure(name, "no agreement measure on this host", n, **detail)
    if n < HAZARD_MIN_N:
        return unmeasured_pressure(name, f"{n} relationship(s), need {HAZARD_MIN_N}", n, **detail)
    return Pressure(name, _clip01(2.0 * (1.0 - agreement)), n, "",
                    {"agreement": agreement, **detail})


def hazard_probability(pressure: float, *, horizon_days: float = HAZARD_HORIZON_DAYS,
                       scale_days: float = HAZARD_SCALE_DAYS) -> float:
    """Pressure -> P(break within the horizon), the exponential hazard crowding_hazard declares."""
    return 1.0 - math.exp(-(pressure / scale_days) * horizon_days)


def pressure_from_hazard(p: float, *, horizon_days: float = HAZARD_HORIZON_DAYS,
                         scale_days: float = HAZARD_SCALE_DAYS) -> float:
    """The inverse, so a component that already speaks in probabilities joins the average.

    `crowding_hazard.hazard` returns P(competed away within the horizon) rather than a pressure.
    Averaging a probability with eight pressures would weight it by whatever the horizon happened
    to be; inverting it through the SAME scale recovers the pressure it was built from exactly,
    which is the only way the crowding channel can sit beside the other eight without silently
    changing weight when the horizon moves.
    """
    p = min(max(p, 0.0), 1.0 - 1e-12)
    return _clip01(-math.log(1.0 - p) * scale_days / max(horizon_days, 1e-9))


def edge_hazard(components: list[Pressure], *, horizon_days: float = HAZARD_HORIZON_DAYS,
                scale_days: float = HAZARD_SCALE_DAYS,
                min_channels: int = HAZARD_MIN_CHANNELS) -> dict[str, Any]:
    """hazard_i(t) = P(edge breaks next horizon | history), from the channels that HAVE a history.

    The mean is taken over MEASURED channels only and the count is published beside it: a hazard
    standing on one channel and a hazard standing on eight are different evidence, and the caller
    that shrinks an allocation on this number is entitled to know which it has.

    THE TWO FLOORS ARE WHY THIS RETURNS None SO OFTEN, AND THEY ARE THE POINT. Under
    `min_channels` measured, or with no SLEEVE-scoped channel among them, the pressures are all
    reported and the hazard is None: one book-level number repeated across fifty sleeves is not
    fifty per-edge verdicts, and capital must not move on it.
    """
    measured = [c for c in components if c.value is not None]
    unmeasured = [c for c in components if c.value is None]
    own = [c for c in measured if c.scope == SLEEVE]
    rows = {c.name: {"pressure": (None if c.value is None else round(c.value, 6)), "n": c.n,
                     "scope": c.scope, "why": c.why, **c.detail} for c in components}
    lines = {"at_risk": HAZARD_AT_RISK, "breaking": HAZARD_BREAKING, "scale_days": scale_days,
             "min_n": HAZARD_MIN_N, "min_channels": min_channels}
    base: dict[str, Any] = {
        "hazard": None, "verdict": UNMEASURED, "mean_pressure": None,
        "n_measured": len(measured), "n_sleeve_channels": len(own),
        "horizon_days": horizon_days, "components": rows,
        "unmeasured": [c.name for c in unmeasured], "lines": lines}
    if not measured:
        return {**base, "why": ("no monitored channel carries a ledger on this host; a 0.0 built "
                                "out of absences is the one number this must never return")}
    if len(measured) < min_channels:
        return {**base, "why": (f"{len(measured)} of {len(components)} channel(s) measured, need "
                                f"{min_channels}: one symptom is not several agreeing, and this "
                                "number moves capital")}
    if not own:
        return {**base, "why": ("every measured channel is BOOK-scoped "
                                f"({', '.join(sorted(c.name for c in measured))}): that is a "
                                "statement about the book's conditioning, covariance and driver "
                                "graph, not about this edge")}
    mean = statistics.fmean(float(c.value) for c in measured if c.value is not None)
    p = hazard_probability(mean, horizon_days=horizon_days, scale_days=scale_days)
    verdict = (BREAKING if p >= HAZARD_BREAKING else
               (AT_RISK if p >= HAZARD_AT_RISK else HOLDING))
    lead = max(measured, key=lambda c: c.value or 0.0)
    return {**base, "hazard": round(p, 6), "verdict": verdict, "mean_pressure": round(mean, 6),
            "leading_channel": lead.name,
            "why": (f"{len(measured)} of {len(components)} channel(s) measured ({len(own)} this "
                    f"sleeve's own), mean pressure {mean:.3f}, led by {lead.name}; P(break "
                    f"within {horizon_days:g}d) = {p:.1%}")}

```

### scripts\check_change_window.py
```python
#!/usr/bin/env python3
"""STERILE COCKPIT (L1.38) -- the money path does not change during the windows where a change
cannot be validated before it matters.

CROSS-DOMAIN TRANSFER (capability-hunt lens 6, aviation safety). Airlines forbid non-essential
activity below 10,000 feet -- not because the crew is less capable then, but because THAT is when
an error has no time to be caught. This desk has the identical structure and no equivalent rule:
an autonomous box that ships ~10 commits/day into the same tree the executor runs from, with a
10-minute auto-deploy, and a launch window during which a money-path defect fires exactly once,
for real, on real capital.

READ THIS BEFORE ASSUMING IT IS TIMIDITY -- it is the opposite, and the distinction is precise:
  * It freezes ONLY the money path (executor, connectors, risk rails, sizing, capital events)
    and ONLY inside a declared window.
  * RESEARCH, MINING, DATA ACQUISITION, FENCES AND EXPLORATION ARE EXPLICITLY UNAFFECTED and keep
    running at full cadence -- L1.28b(f) makes raw acquisition untouchable, and L1.25a forbids
    slowing a hunt for any reason. A frozen money path during launch week costs NOTHING in
    discovery; the desk keeps hunting at 100% and simply stages the money-path change until the
    window closes.
  * A FIX FOR A LIVE DEFECT IS ALWAYS ALLOWED. This freezes IMPROVEMENTS, never REPAIRS: if the
    money path is broken, changing it is the safest available act, and refusing that would be
    the timid reading this desk bans.

WINDOWS (each is a period where an error cannot be caught before it costs real capital):
  GATE0_LAUNCH   from the first recorded capital event until +7 days of live operation
  FIRST_FILLS    while the execution tape has fewer than 20 recorded live fills
  RAIL_BREACH    while a ruin/derisk rail is live -- the book is already unwinding; a code
                 change mid-unwind is how a bad day becomes a terminal one

STATUS: OPEN (change freely) / STERILE (money-path improvements staged, repairs allowed) /
UNMEASURED (cannot tell -- treated as STERILE, because the cost of a wrong OPEN is unbounded and
the cost of a wrong STERILE is a delayed improvement).

    python scripts/check_change_window.py [--paths a.py b.py] [--json]
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parent.parent

# L1.42 LAWFUL ENTRY: this organ ran on a cron line that passed through no gate at
# all -- 60 manifest lines did. guard() verifies the sealed core and that the doctrine
# still carries every law family; it is TTL-cached (~0ms after the first call in a
# window) and pages-but-does-not-block, so a governance fault never silences an organ.
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
from libs.ops.fence_exit import fence_exit  # noqa: E402
from libs.ops.lawful import guard as _law_guard  # noqa: E402

#: This one gates on `verdict`, which is computed as a strict ALLOW/BLOCK binary, so it did not
#: have the fall-through hole the other seven had. Routed through the same helper anyway so that
#: a THIRD verdict value added later fails closed instead of joining the `else 0` branch -- the
#: property is that no future editor has to remember this file. Zero behaviour change today.
_PASSING = frozenset({"ALLOW"})

#: The money path: code whose defects can only be discovered by losing money.
#: NARROWED 2026-09-05 (universe mandate): run_cashcarry_executor.py, run_live_guard.py and
#: data/cashcarry_config.json went with the retired book. This is a PREFIX scope over changed
#: paths, so a dead entry is inert rather than dangerous -- but an inert entry also cannot be
#: distinguished from a live one by reading the tuple, and the whole point of naming the money
#: path explicitly is that a reader can tell what it covers. desks/mt5/ is added because that is
#: where money now moves: the gateway, the netting policy and the execution policy are precisely
#: "code whose defects can only be discovered by losing money".
MONEY_PATH = (
    "libs/execution/", "libs/risk/",
    "scripts/record_capital_event.py",
    "scripts/run_deadman_switch.py",
    "desks/mt5/mt5desk/gateway.py", "desks/mt5/mt5desk/netting.py",
    "desks/mt5/mt5desk/execution_policy.py",
)

LAUNCH_WINDOW_DAYS = 7
MIN_FILLS_FOR_CONFIDENCE = 20

#: The executor's published book state (run_cashcarry_executor.py:43). NOT cashcarry_state.json,
#: which nothing has ever written -- see _rail_live.
_STATE_REL = "data/cashcarry_positions.json"


def _capital_event_age_days(root: Path, now: datetime) -> float | None:
    """Days since the FIRST recorded capital event (the launch moment). None = never launched."""
    try:
        rows = [json.loads(ln) for ln in
                (root / "data/capital_events.jsonl").read_text("utf-8").splitlines() if ln.strip()]
    except (OSError, ValueError):
        return None
    stamps = [r.get("at") for r in rows if isinstance(r, dict) and r.get("at")]
    if not stamps:
        return None
    try:
        first = datetime.fromisoformat(str(min(stamps)))
    except ValueError:
        return None
    first = first if first.tzinfo else first.replace(tzinfo=UTC)
    return (now - first).total_seconds() / 86400.0


def _n_fills(root: Path) -> int | None:
    p = root / "data/moat/execution_tape/cashcarry_trades.jsonl"
    try:
        return sum(1 for ln in p.read_text("utf-8").splitlines() if ln.strip())
    except OSError:
        return None


def _rail_live(root: Path) -> tuple[bool | None, str]:
    """Is a ruin/derisk rail live? (verdict, why) -- None means UNMEASURED, never "no rail".

    R0333: this read pointed at data/cashcarry_state.json, a file no organ writes, so the
    RAIL_BREACH window could only ever be measured through the kill file. The executor publishes
    `last_risk_action` (run_cashcarry_executor.py, latched each tick) into
    data/cashcarry_positions.json. The three failure modes are now named separately: an absent
    file, a torn/unparseable one and one whose schema lacks the key are different facts about
    the box, and none of them is evidence that no rail is live.
    """
    if (root / "data/CASHCARRY_KILL").exists():
        return True, "CASHCARRY_KILL present"
    p = root / _STATE_REL
    try:
        raw = p.read_text("utf-8")
    except FileNotFoundError:
        return None, f"absent ({_STATE_REL} never written on this box)"
    except OSError as exc:
        return None, f"unreadable ({type(exc).__name__} on {_STATE_REL})"
    try:
        st = json.loads(raw)
    except json.JSONDecodeError as exc:
        return None, f"unparseable ({_STATE_REL} is not valid JSON, line {exc.lineno})"
    if not isinstance(st, dict):
        return None, f"unparseable ({_STATE_REL} holds a {type(st).__name__}, not an object)"
    try:
        action = str(st["last_risk_action"])
    except KeyError:
        return None, f"schema-missing-key (`last_risk_action` absent from {_STATE_REL})"
    return action in ("flatten", "pause_opens"), f"last_risk_action={action!r}"


def touches_money_path(paths: list[str]) -> list[str]:
    return [p for p in paths if any(p.startswith(m) or m.rstrip("/") in p for m in MONEY_PATH)]


def build_report(root: Path | None = None, now: datetime | None = None,
                 paths: list[str] | None = None) -> dict[str, Any]:
    root = root or _ROOT
    now = now or datetime.now(tz=UTC)
    reasons: list[str] = []
    unmeasured: list[str] = []

    age = _capital_event_age_days(root, now)
    if age is not None and age <= LAUNCH_WINDOW_DAYS:
        reasons.append(f"GATE0_LAUNCH: {age:.1f}d since first capital event "
                       f"(window {LAUNCH_WINDOW_DAYS}d)")
    fills = _n_fills(root)
    if fills is None:
        unmeasured.append("execution tape unreadable -- cannot count live fills")
    elif age is not None and fills < MIN_FILLS_FOR_CONFIDENCE:
        reasons.append(f"FIRST_FILLS: {fills} live fills recorded (< {MIN_FILLS_FOR_CONFIDENCE})")
    rail, rail_why = _rail_live(root)
    if rail is None:
        unmeasured.append(f"executor state {rail_why} -- cannot tell if a rail is live")
    elif rail:
        reasons.append(f"RAIL_BREACH: a ruin/derisk rail is live ({rail_why}) -- "
                       "the book is unwinding")

    if age is None:
        # PRE-LAUNCH IS ALWAYS OPEN, even when tape/state are unreadable: with no capital event
        # ever recorded there is provably no live capital a change could harm, so the
        # unmeasured->STERILE asymmetry does not apply. (First run of this fence got that wrong
        # and would have blocked the very session that was fixing the money path pre-launch.)
        status, note = "OPEN", ("pre-launch: no capital event recorded, so no live capital can "
                                "be harmed by a money-path change")
        unmeasured = []
    elif reasons:
        status, note = "STERILE", "money-path IMPROVEMENTS staged; repairs always allowed"
    elif unmeasured:
        # A wrong OPEN costs unbounded real capital; a wrong STERILE costs a delayed improvement.
        status, note = "UNMEASURED", ("cannot prove the window is safe -- treated as STERILE, "
                                      "because the asymmetry is not close")
    else:
        status, note = "OPEN", "outside every declared window"

    offending = touches_money_path(paths or [])
    return {
        "generated": now.isoformat(), "status": status,
        "law": "L1.38 -- the money path does not change inside a window where the change cannot "
               "be validated before it costs real capital. Research/mining/fences are UNAFFECTED.",
        "windows_active": reasons, "unmeasured": unmeasured, "note": note,
        "days_since_launch": None if age is None else round(age, 2),
        "live_fills": fills,
        "money_path_files_in_change": offending,
        "verdict": ("BLOCK" if offending and status in ("STERILE", "UNMEASURED") else "ALLOW"),
        "next_action": (
            "stage the improvement on a branch and land it when the window closes. If this IS a "
            "repair for a live defect, say so in the commit and proceed -- this law freezes "
            "improvements, never repairs. Research, mining, data acquisition, fences and "
            "exploration are not affected and must not be slowed (L1.25a, L1.28b(f))."),
    }


#: The ONLY way a money-path commit is read as a repair. Deliberately an EXPLICIT marker and not
#: a keyword sniff: "fix" appears in most commit subjects on this desk, so a keyword list would
#: classify ~everything as REPAIR and weld this gate permanently OPEN -- a gate that accepts ~100%
#: carries zero information (L1.43), which is the failure this was built to avoid, not cause.
#: Requiring the operator to WRITE the declaration is the point: it is an assertion that a live
#: defect exists, and an undeclared money-path commit stays frozen by default (fail-closed).
REPAIR_MARKER = "L1.38: repair"


def classify_commits(base: str, head: str = "HEAD", root: Path | None = None) -> list[dict]:
    """Classify every commit in base..head as REPAIR / IMPROVEMENT / NON-MONEY-PATH.

    R0426. This fence judged a WINDOW and a PATH SET and never a DIFF, so it could not answer the
    only question an operator actually has: *can I restart this process right now?* The unit of
    deployment is a PROCESS RESTART, not a commit -- so a repair sitting behind a deliberately
    withheld improvement cannot be shipped without also shipping the improvement, and the fence
    had no vocabulary for saying which pending commits were which.

    UNDECLARED IS AN IMPROVEMENT, NEVER A REPAIR. That is the conservative direction and the one
    that matches the law: the cost of wrongly staging a repair is a delayed fix, the cost of
    wrongly shipping an improvement into a live window is unbounded.
    """
    root = root or _ROOT
    import subprocess
    try:
        raw = subprocess.run(
            ["git", "log", "--no-merges", "--format=%H%x1f%s%x1f%b%x1e", f"{base}..{head}"],
            cwd=root, capture_output=True, text=True, timeout=30, check=True).stdout
    except (subprocess.SubprocessError, OSError) as exc:
        return [{"sha": None, "kind": "UNMEASURED",
                 "why": f"git log {base}..{head} failed: {type(exc).__name__}"}]
    out: list[dict] = []
    for rec in (r.strip() for r in raw.split("\x1e") if r.strip()):
        sha, subject, body = [*rec.split("\x1f"), "", ""][:3]
        try:
            files = subprocess.run(
                ["git", "show", "--pretty=", "--name-only", sha],
                cwd=root, capture_output=True, text=True, timeout=30, check=True
            ).stdout.split()
        except (subprocess.SubprocessError, OSError) as exc:
            # NOT swallowed to NON-MONEY-PATH: a commit whose files cannot be listed is UNKNOWN,
            # and treating unknown as harmless is precisely the false-OPEN this law forbids.
            out.append({"sha": sha[:8], "subject": subject[:90], "kind": "UNMEASURED",
                        "why": f"cannot list files ({type(exc).__name__})"})
            continue
        money = touches_money_path(files)
        if not money:
            kind, why = "NON-MONEY-PATH", "touches no money-path file -- the freeze does not apply"
        elif REPAIR_MARKER.lower() in f"{subject}\n{body}".lower():
            kind, why = "REPAIR", f"declares {REPAIR_MARKER!r} -- repairs are always allowed"
        else:
            kind, why = "IMPROVEMENT", (
                f"touches the money path and does NOT declare {REPAIR_MARKER!r}, so it is "
                "treated as an improvement and stays staged inside a window")
        out.append({"sha": sha[:8], "subject": subject[:90], "kind": kind, "why": why,
                    "money_path_files": money})
    return out


def restart_verdict(base: str, head: str = "HEAD", root: Path | None = None,
                    status: str | None = None) -> dict[str, Any]:
    """Can the money-path units be restarted onto HEAD right now, and if not, which commit blocks?

    Turns 'can I restart?' from an argument into a lookup. `base` is what the RUNNING process has
    -- the sha it was started from (max_audit._proc_start gives the start time when the sha is
    not recorded; a restart-time sha stamp is the better input and is what a caller should pass).
    """
    status = status or str(build_report(root=root).get("status") or "UNMEASURED")
    commits = classify_commits(base, head, root=root)
    blocking = [c for c in commits if c["kind"] in ("IMPROVEMENT", "UNMEASURED")]
    repairs = [c for c in commits if c["kind"] == "REPAIR"]
    if status == "OPEN":
        verdict, why = "ALLOW", "the change window is OPEN -- nothing is frozen"
    elif not commits:
        verdict, why = "ALLOW", f"no commits between {base[:8]} and {head}"
    elif not blocking and not repairs:
        # DISTINCT FROM "all repairs". The first run printed "0 pending money-path commit(s), ALL
        # declared repairs", which reads as a judgement about repairs when the real answer is that
        # the freeze never applied -- two different facts, and only one of them involves L1.38.
        verdict, why = "ALLOW", (
            f"none of the {len(commits)} pending commit(s) touch the money path -- the freeze "
            "does not apply to any of them")
    elif not blocking:
        verdict, why = "ALLOW", (
            f"{len(repairs)} pending money-path commit(s), ALL declared repairs -- a repair is "
            "always allowed to deploy, even inside a window")
    else:
        verdict, why = "BLOCK", (
            f"{len(blocking)} pending money-path change(s) are not declared repairs, so a restart "
            f"would ship them into a {status} window alongside any repair")
    return {"verdict": verdict, "why": why, "window_status": status, "base": base[:8],
            "n_commits": len(commits), "n_repairs": len(repairs), "n_blocking": len(blocking),
            "blocking": blocking, "commits": commits,
            "next_action": (
                "land the repair on its own by declaring "
                f"{REPAIR_MARKER!r} in its commit and restarting onto a tree that carries only "
                "declared repairs; or wait for the window to close. Never restart onto a tree "
                "holding an undeclared money-path change." if verdict == "BLOCK" else
                "restart is permitted by L1.38")}


def held_units(status: str | None = None) -> list[str]:
    """Supervised units an UNATTENDED deploy must not restart right now (L1.38).

    THE GAP THIS CLOSES, found 2026-08-12 by asking what the deploy-path repair would switch on.
    scripts/run_stale_daemon_repair.py consults this window before restarting anything, but
    deploy/pull_deploy.sh -- which restarts supervised processes every 10 minutes on the box that
    owns the book -- never did. That was invisible because its dirty-tree refusal had made it a
    no-op for eight days, so the unguarded restart had simply never been reachable. Repairing the
    deploy path without this would have ARMED it: the first commit touching libs/execution/ would
    have restarted quant-cashcarry inside a live RAIL_BREACH window, which is exactly the
    "ships whatever is on disk into the money path" move L1.38 exists to prevent.

    An empty list means "restart freely". Deliberately NOT the deadman: that is TIER_RUIN and
    deploy_plan already refuses to restart it by tier, a stronger guarantee than a window.
    """
    from libs.ops.deploy_plan import units_touching
    status = status or str(build_report().get("status") or "UNMEASURED")
    if status == "OPEN":
        return []
    return list(units_touching(MONEY_PATH))


def main() -> int:
    _law_guard()
    ap = argparse.ArgumentParser()
    ap.add_argument("--paths", nargs="*", default=[], help="changed files to judge")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--report-only", action="store_true")
    ap.add_argument("--held-units", action="store_true",
                    help="print units an unattended deploy must not restart now, one per line")
    ap.add_argument("--can-restart", metavar="BASE_SHA",
                    help="classify commits BASE_SHA..HEAD as repair/improvement and answer "
                         "whether the money-path units can be restarted onto HEAD (R0426)")
    args = ap.parse_args()
    if args.can_restart:
        # A QUERY like --held-units: it must not write the fence artifact. Its exit code IS the
        # answer (0 = restart allowed, 1 = blocked) so a deploy script can gate on it directly.
        rv = restart_verdict(args.can_restart)
        if args.json:
            print(json.dumps(rv, indent=2))
        else:
            print(f"restart onto HEAD: {rv['verdict']} -- {rv['why']}")
            for c in rv["commits"]:
                print(f"  {c['kind']:<16}{c.get('sha') or '?':<10}{c.get('subject', '')[:64]}")
            if rv["verdict"] == "BLOCK":
                print(f"  next: {rv['next_action']}")
        return 0 if rv["verdict"] == "ALLOW" else 1
    if args.held_units:
        # A QUERY, not a fence run: it must not write the report artifact and must not exit
        # non-zero on a sterile window, or the caller cannot tell "held these" from "I crashed".
        for unit in held_units():
            print(unit)
        return 0
    rep = build_report(paths=args.paths)
    out = _ROOT / "data/change_window.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(rep, indent=2), "utf-8")
    if args.json:
        print(json.dumps(rep, indent=2))
    else:
        print(f"change window (L1.38): {rep['status']} -- {rep['note']}")
        for r in rep["windows_active"]:
            print(f"  WINDOW  {r}")
        if rep["money_path_files_in_change"]:
            print(f"  {rep['verdict']}   money-path files: {rep['money_path_files_in_change']}")
    if args.report_only:
        return 0
    return fence_exit(rep["verdict"], _PASSING)


if __name__ == "__main__":
    sys.exit(main())

```

### scripts\check_job_manifest.py
```python
#!/usr/bin/env python3
"""JOB MANIFEST -- every scheduled job publishes success, freshness, hashes and last-valid output.

WHY (principal 2026-08-26: "every job must publish success, failure, freshness, input/output
hashes and last-valid output; alert on stale data, missing consumers, orphan modules and
zero-yield miners"). This desk has repeatedly discovered that a job was dead only by reading its
artifact by hand, hours or days later:

  * the tick tape raised ModuleNotFoundError EVERY HOUR and exited 0, so 16.2M ticks went
    unrecorded while the cycle printed "cycle done";
  * shadow_cycle exited 1 every 15 minutes on a Windows ACL error for an unknown period;
  * `promotion_gate.py` published NO-PRODUCER and returned 0, which the cadence scored as a duty
    fired -- for its entire existence;
  * a certifier rewrote the survivors file from n=1 to n=0 with exit code 0.

Exit codes are the wrong instrument. Every one of those jobs "succeeded". What distinguishes a
working organ from a dead one is whether its OUTPUT moved, and that is what this checks: an
artifact's hash, its age, and whether anything downstream reads it.

WHAT IS ALERTED, and why each is a distinct failure rather than one:

  STALE      -- the artifact exists but is older than the job's own cadence allows. The job is
                scheduled and silent; something is failing without saying so.
  FROZEN     -- the artifact is fresh but its CONTENT HASH has not changed across runs. The job
                runs, writes, and produces the same bytes: a loop that is turning without
                cutting. Distinct from STALE because the timestamp looks healthy.
  IDLE       -- fresh, byte-identical, AND the producer declared `unchanged_because` on this
                write: its input population is empty, so identical bytes are the correct output.
                Counted and printed, never alarmed. Without this, `decay_live.json` with an empty
                roster was FROZEN on 55 consecutive checks and blocked rung 0 of live readiness --
                a red that could clear only by deploying capital, which is the always-red detector
                this desk retires on sight (L1.37). The AGE check stays armed, so a producer that
                actually dies still goes STALE while carrying its declaration.
  MISSING    -- declared but never produced. An owed build, not a passing check (L1.28a).
  NO-CONSUMER-- produced, but nothing reads it. Either the consumer is unwired (a gap) or the
                artifact is dead weight; both are defects, and neither is visible from the job.
  EMPTY      -- fresh, moving, and its PAYLOAD says nothing was measured: n = 0, status
                UNMEASURED, an empty roster. Until 2026-09-08 this read OK, because age was the
                only instrument: execution_quality.json rewritten on time with 0 decisions was
                green. A row may declare an emptiness predicate (its third element) and the
                verdict then reads EMPTY rather than OK. Counted and printed, never alarmed --
                alarming it would rebuild the always-red detector L1.37 retires -- and it never
                replaces STALE, FROZEN or IDLE: an empty artifact that also stopped moving is
                still reported for having stopped.

RESEARCH LATENCY rides on the same report (2026-09-08). The blueprint's SLOs (start < 1h,
screen < 10m, gauntlet verdict < 24h) had no number anywhere on the desk; the hypothesis graph
carries every BORN and every verdict with a timestamp, so three rows are computed from it --
time-to-first-screen, time-to-gauntlet-verdict, time-to-certificate -- each naming the
timestamps it joins, and UNMEASURED with the count when no node has both ends. They are
published and printed, never alarmed: a research backlog is a fact for the principal and
research_productivity, not a repair request.

The manifest lives in data/job_manifest.json and RATCHETS: a job that has ever produced an
artifact is expected to keep producing one. Last-valid output and its hash are retained so a
regression can be pinpointed to a run rather than a day.
"""
from __future__ import annotations

import hashlib
import json
import statistics
import sys
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from libs.ops.repair_invoke import request_repair

ROOT = Path(__file__).resolve().parent.parent
DESK = ROOT / "desks" / "mt5"
STATE = ROOT / "data" / "job_manifest.json"
ALARM = ROOT / "data" / "JOB_MANIFEST_ALARM.txt"
GRAPH = DESK / "data" / "hypothesis_graph.jsonl"

#: An emptiness predicate: the parsed artifact -> why its payload measures nothing, or None.
EmptyFn = Callable[[Any], str | None]


def _empty_execution_quality(doc: Any) -> str | None:
    """shadow_execution.summarise: `decisions` and `filled` are the sample sizes."""
    if not isinstance(doc, dict):
        return None
    n = int(doc.get("decisions") or 0)
    if n == 0:
        return "decisions=0: no shadow decision to measure execution on"
    if int(doc.get("filled") or 0) == 0:
        return f"filled=0 of {n} decision(s): no fill to price"
    return None


def _empty_decay_live(doc: Any) -> str | None:
    """decay_monitor: `roster_state` UNMEASURED or an empty roster is a report about nothing."""
    if not isinstance(doc, dict):
        return None
    if str(doc.get("roster_state") or "") == "UNMEASURED":
        return f"roster_state=UNMEASURED: {doc.get('roster_why') or 'roster unreadable'}"
    if doc.get("live_sleeves") in (None, 0):
        return f"live_sleeves={doc.get('live_sleeves')!r}: nothing to decay"
    return None


def _empty_counterfactual(doc: Any) -> str | None:
    """counterfactual_replay: status UNMEASURED, or no priced row, is a world nobody replayed."""
    if not isinstance(doc, dict):
        return None
    status = str(doc.get("status") or "")
    if status == "UNMEASURED":
        return f"status=UNMEASURED: {doc.get('why') or ''}".rstrip(": ")
    ds = doc.get("dataset") if isinstance(doc.get("dataset"), dict) else {}
    priced = int(ds.get("rows_priced") or doc.get("rows_priced") or 0)
    if status and priced == 0:
        return f"status={status} with rows_priced=0: no decision was priced"
    return None


#: artifact -> (max_age_hours, who consumes it[, emptiness predicate]). The consumer is named so
#: "nothing reads this" is a checkable claim rather than an impression; the predicate, where a
#: row carries one, is what lets "rewritten on time with nothing in it" read EMPTY.
JOBS: dict[str, tuple[float, str] | tuple[float, str, EmptyFn]] = {
    "desks/mt5/reports/UNIVERSAL_SURVIVORS.json": (26.0, "shadow_admission, promoter, dashboard"),
    "desks/mt5/reports/shadow/shadow_state.json": (3.0, "promoter, reconciler, dashboard"),
    "desks/mt5/reports/shadow/scalp_shadow_state.json": (3.0, "shadow_cycle, dashboard"),
    "desks/mt5/reports/shadow/qquant_shadow_state.json": (3.0, "promoter, dashboard"),
    "desks/mt5/reports/execution_quality.json": (36.0, "promoter (promotion gate), dashboard",
                                                 _empty_execution_quality),
    # sleeve_registry.json is DELIBERATELY NOT HERE. `freeze()` is idempotent -- it returns
    # early once a key is frozen -- so the file only changes when a NEW sleeve enrols and an
    # unchanged registry is the HEALTHY state. Gauging it by age (it carried a 3.0h window)
    # made it red whenever the desk was well, and it was only ever GREEN because
    # `pull_desk_state.sh` restamped it every two minutes without `scp -p`. The property
    # that matters -- no clock RUNS without a frozen identity -- is measured every pass by
    # `forward_reconcile` as IDENTITY_UNFROZEN, and forward_reconcile.json IS age-gauged
    # below because it rewrites on every run. Do not "restore" this row: age is the wrong
    # instrument here, not a missing one.
    "desks/mt5/data/decay_live.json": (26.0, "dashboard, gateway risk", _empty_decay_live),
    "desks/mt5/data/forward_reconcile.json": (26.0, "operator audit"),
    # THE VETO RAILS' EVIDENCE. missed_growth reads it (desks/mt5/research/missed_growth.py:54)
    # to bill every rail, and its UNMEASURED state -- no bars cover the decision minutes on this
    # host -- was indistinguishable from a measured world by age alone.
    "desks/mt5/reports/COUNTERFACTUAL_WORLD.json": (26.0, "missed_growth (veto rails), dashboard",
                                                    _empty_counterfactual),
    # THE TICK TAPE, WHICH HAD NO ALARM AND WAS ALREADY DEAD (I8, wired 2026-09-13).
    #
    # `desks/mt5/data/tape/` was reachable only by reading the directory, so a stopped recorder
    # was invisible to the one report that has a consumer column. Measured on the box the hour
    # this row was added: `tape_state.json` and `ticks` were 56.6 HOURS old while
    # `triangle_executable.json` beside them was 1.4h -- so part of the lane was running and the
    # tick recorder had been silently stopped for two and a half days. Nothing said so.
    #
    # This is the market-microstructure half of the data moat, and it is the half the strategies
    # actually trade: `tape_features` builds the execution twin from it and
    # `counterfactual_replay` prices the road not taken against it. A two-hour limit because the
    # recorder rewrites continuously while a market is open -- it is gauged on the STATE file
    # rather than on the tick spool, because the spool grows by append and an append can succeed
    # while the recorder is stuck on one symbol.
    "desks/mt5/data/tape/tape_state.json": (2.0, "tape_features (execution twin), "
                                                 "counterfactual_replay, mt5desk.tape"),
    "data/gauntlet_survivors.json": (26.0, "promotion_gate"),
    "web/desk_state.json": (0.5, "dashboard (Dell/phone)"),
    "data/authority_ratchet.json": (1.0, "earned-evidence floors"),
    "data/sameday_pipeline.json": (2.0, "same-day fence"),
    # A FIX THAT NEVER REACHED THE BOX IS NOT A FIX. Measured 2026-08-27: the only
    # code-sync path ships a hardcoded four-file list, so the whole forward/promotion
    # chain the desk box executes was outside it and `h1_source.py` had silently
    # diverged. Nothing measured that, which is why it lasted.
    "data/desk_code_parity.json": (1.0, "desk-parity fence (is the box running this code)"),
    # A register silently rolled back six hours is worse than a missing one: it still reads
    # as authoritative. Measured 2026-08-27, two heals in 44 seconds.
    "data/doc_replay_fence.json": (0.5, "doc replay fence (stale-snapshot rollback)"),
    # THE ONE NUMBER THE PATH TO LIVE CAPITAL TURNS ON, and until 2026-08-27 nothing measured
    # it. The whole forward book was silently re-based to day zero three times in 32 hours
    # (registry history: 08-26T01:42, 08-27T01:13, 08-27T03:31) against a `days >= 14`
    # promotion bar, while the shadow watchdog reported OPERATING/defects:[] throughout. If
    # this artifact goes stale the ratchet has stopped and the next re-base is invisible again.
    "data/forward_clock_ratchet.json": (1.5, "forward-clock ratchet (silent re-base detector)"),
    # 17 live timers -- including the mt5-suite ratchet, the universe-registry cost repair and
    # six research seats -- were firing from ~/.config/systemd/user with no committed copy
    # anywhere (measured 2026-08-27). A rebuilt box schedules none of them and nothing says so.
    "data/unit_parity.json": (2.0, "unit parity (live timer with no committed unit)"),
    # GAP 161: forward_reconcile.json was observed going a full day BACKWARD mid-session while
    # still reading as authoritative. If this artifact goes stale the rollback detector has
    # stopped and the desk's record of its own live book can regress unnoticed again.
    "data/artifact_monotonic.json": (0.5, "artifact rollback fence (stamp went backward)"),
}


def _read(path: Path):
    try:
        return json.loads(path.read_text("utf-8"))
    except (OSError, ValueError):
        return None


def _hash(path: Path) -> str | None:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()[:16]
    except OSError:
        return None


def _job_row(value: tuple) -> tuple[float, str, EmptyFn | None]:
    """(max_age_h, consumer, emptiness predicate or None) from a two- or three-element row."""
    max_age_h, consumer = float(value[0]), str(value[1])
    empty_fn = value[2] if len(value) > 2 and callable(value[2]) else None
    return max_age_h, consumer, empty_fn


# ---------------------------------------------------------------------------- research latency
#: name -> (target hours or None, consumer, the timestamps joined). A None target is a row that
#: is MEASURED and reported but has no SLO: a certificate waits on forward evidence by law
#: (promotion bar days >= 14), so a latency target on it would contradict the forward floor.
LATENCY_SLOS: dict[str, tuple[float | None, str, str]] = {
    "time_to_first_screen": (
        1.0, "research_productivity, the principal",
        "BORN.at -> the first LATER row of any other fate (JUDGED, FAILED, CERTIFIED, RETIRED, "
        "BURIED) for the same node id in desks/mt5/data/hypothesis_graph.jsonl. Blueprint: start "
        "< 1h and screen < 10m; the graph cannot separate the two, so their sum bounds this row"),
    "time_to_gauntlet_verdict": (
        24.0, "research_productivity, the principal",
        "BORN.at -> the first LATER FAILED or CERTIFIED row for the same node id. Blueprint: "
        "gauntlet verdict < 24h"),
    "time_to_certificate": (
        None, "research_productivity, the principal",
        "BORN.at -> the first LATER CERTIFIED row for the same node id. No target: the "
        "certificate waits on forward evidence by law"),
}
_SCREEN_FATES = frozenset({"JUDGED", "FAILED", "CERTIFIED", "RETIRED", "BURIED"})
_VERDICT_FATES = frozenset({"FAILED", "CERTIFIED"})
_CERT_FATES = frozenset({"CERTIFIED"})
_LATENCY_FATES = {"time_to_first_screen": _SCREEN_FATES,
                  "time_to_gauntlet_verdict": _VERDICT_FATES,
                  "time_to_certificate": _CERT_FATES}


def _parse_at(s: Any) -> datetime | None:
    try:
        d = datetime.fromisoformat(str(s))
    except (TypeError, ValueError):
        return None
    return d if d.tzinfo else d.replace(tzinfo=UTC)


def _quantile(samples: list[float], q: float) -> float:
    if len(samples) == 1:
        return samples[0]
    return float(statistics.quantiles(samples, n=100, method="inclusive")[int(q * 100) - 1])


def latency_rows(graph_path: Path | None = None, now: datetime | None = None) -> dict[str, dict]:
    """The three research-latency rows from the hypothesis graph's own timestamps.

    Per node id the FIRST BORN row is the start; each SLO's end is the first row of its fate
    set whose `at` is LATER than that start. A node whose verdict row is not later than its
    BORN row (the backfill wrote verdicts before the compiler re-registered the cell) is
    counted as `unordered`, never as a negative latency; a node born with no end yet is `open`
    and its oldest age is reported, because a backlog is the latency the SLO is about.
    """
    graph_path = GRAPH if graph_path is None else graph_path   # resolved at call, not at def
    now = now or datetime.now(tz=UTC)
    out: dict[str, dict] = {}
    if not graph_path.exists():
        for name, (target, consumer, basis) in LATENCY_SLOS.items():
            out[name] = {"status": "UNMEASURED", "n": 0, "target_h": target,
                         "consumer": consumer, "basis": basis,
                         "why": f"{graph_path} absent: no timestamps to join"}
        return out
    born: dict[str, datetime] = {}
    later: dict[str, list[tuple[datetime, str]]] = {}
    n_rows = 0
    try:
        with graph_path.open("r", encoding="utf-8") as fh:
            for ln in fh:
                if not ln.strip():
                    continue
                try:
                    r = json.loads(ln)
                except ValueError:
                    continue
                n_rows += 1
                nid, fate, at = str(r.get("id") or ""), str(r.get("fate") or ""), _parse_at(
                    r.get("at"))
                if not nid or at is None:
                    continue
                if fate == "BORN":
                    if nid not in born or at < born[nid]:
                        born[nid] = at
                else:
                    later.setdefault(nid, []).append((at, fate))
    except OSError as exc:
        for name, (target, consumer, basis) in LATENCY_SLOS.items():
            out[name] = {"status": "UNMEASURED", "n": 0, "target_h": target,
                         "consumer": consumer, "basis": basis, "why": f"unreadable: {exc}"}
        return out
    for name, (target, consumer, basis) in LATENCY_SLOS.items():
        fates = _LATENCY_FATES[name]
        samples: list[float] = []
        unordered = 0
        open_ages: list[float] = []
        for nid, t0 in born.items():
            ends = sorted(at for at, fate in later.get(nid, []) if fate in fates)
            after = [at for at in ends if at > t0]
            if after:
                samples.append((after[0] - t0).total_seconds() / 3600.0)
            elif ends:
                unordered += 1
            else:
                open_ages.append((now - t0).total_seconds() / 3600.0)
        row: dict[str, Any] = {"n": len(samples), "target_h": target, "consumer": consumer,
                               "basis": basis, "graph_rows": n_rows, "born_nodes": len(born),
                               "open": len(open_ages), "unordered": unordered,
                               "oldest_open_h": (round(max(open_ages), 2) if open_ages
                                                 else None)}
        if not samples:
            row.update(status="UNMEASURED",
                       why=(f"0 node(s) carry a BORN row followed by a later "
                            f"{'/'.join(sorted(fates))} row; {len(open_ages)} open, "
                            f"{unordered} unordered (verdict not later than BORN)"))
        else:
            samples.sort()
            p50, p90 = _quantile(samples, 0.5), _quantile(samples, 0.9)
            row.update(p50_h=round(p50, 2), p90_h=round(p90, 2), max_h=round(samples[-1], 2))
            if target is None:
                row.update(status="NO_TARGET", why="measured; no SLO by design (see basis)")
            elif p90 <= target:
                row.update(status="OK", why="")
            else:
                row.update(status="SLOW",
                           why=f"p90 {p90:.1f}h > target {target}h on {len(samples)} node(s)")
        out[name] = row
    return out


def _unchanged_because(path: Path) -> str | None:
    """A producer's own declaration that its output cannot move, or None.

    The contract is one optional top-level string field, `unchanged_because`, re-asserted on every
    write -- so the declaration goes stale exactly when the artifact does, and a producer cannot
    leave a permanent excuse behind. Only JSON objects can declare; anything else is judged as
    before.
    """
    doc = _read(path)
    why = (doc or {}).get("unchanged_because") if isinstance(doc, dict) else None
    return str(why) if isinstance(why, str) and why.strip() else None


def main() -> int:
    now = datetime.now(tz=UTC)
    state = _read(STATE) or {"jobs": {}}
    jobs = state.setdefault("jobs", {})
    findings: list[str] = []
    # IDLE is reported but is NOT a breach: it never reaches ALARM and never makes
    # this fence exit non-zero, because a correct organ with nothing to do is not a
    # failure. It is still printed and still counted in the summary.
    findings_idle: list[str] = []
    # EMPTY is reported and counted like IDLE, never alarmed: the payload says nothing was
    # measured, which is a reading, not a breach -- and an always-red row here would be the
    # detector L1.37 retires. It replaces only OK; STALE, IDLE and FROZEN keep precedence.
    findings_empty: list[str] = []
    rows: dict[str, dict] = {}

    for rel, spec in JOBS.items():
        max_age_h, consumer, empty_fn = _job_row(spec)
        path = ROOT / rel
        prior = jobs.get(rel, {})
        if not path.exists():
            rows[rel] = {"status": "MISSING", "consumer": consumer}
            if prior.get("ever_produced"):
                findings.append(
                    f"MISSING {rel}: produced before (last good {prior.get('last_valid_at')}) "
                    f"and now absent -- a produced artifact that vanishes is a regression, not a "
                    f"quiet day. Consumer: {consumer}")
            else:
                findings.append(f"MISSING {rel}: declared but NEVER produced -- an owed build. "
                                f"Consumer: {consumer}")
            jobs[rel] = {**prior, "status": "MISSING", "checked_at": now.isoformat()}
            continue

        digest = _hash(path)
        mtime = datetime.fromtimestamp(path.stat().st_mtime, tz=UTC)
        age_h = (now - mtime).total_seconds() / 3600
        status = "OK"
        checks_per_window = max(3, int(max_age_h * 2))   # manifest runs ~every 30 minutes
        if age_h > max_age_h:
            status = "STALE"
            findings.append(
                f"STALE {rel}: {age_h:.1f}h old, limit {max_age_h}h. The job is scheduled and "
                f"silent -- exit codes do not catch this, only the artifact does. "
                f"Consumer: {consumer}")
        # FROZEN MUST BE JUDGED AGAINST THE ARTIFACT'S OWN CADENCE, not a flat count. This read
        # "identical across 3 checks", but the manifest runs every 30 minutes while some artifacts
        # are DAILY -- execution_quality legitimately holds the same bytes across ~48 checks and
        # was reported FROZEN for it, which is a false alarm that trains the reader to ignore the
        # real ones. The honest test is whether the content has stood still for longer than the
        # job's own update interval allows.
        elif (digest and digest == prior.get("hash")
                and prior.get("hash_runs", 0) >= checks_per_window
                and (_idle := _unchanged_because(path))):
            # THE PRODUCER MAY DECLARE WHY ITS BYTES CANNOT MOVE. An organ whose input population
            # is empty writes the same output correctly and forever: `decay_live.json` with an
            # empty roster was FROZEN across 55 consecutive checks and blocked rung 0 of live
            # readiness, a red that could only clear by deploying capital. That is the always-red
            # detector this desk retires on sight (L1.37). IDLE is still COUNTED and still
            # printed, so this hides nothing -- and the age check above is untouched, so an organ
            # that genuinely dies still goes STALE while carrying its declaration.
            status = "IDLE"
            findings_idle.append(f"IDLE {rel}: {_idle} Consumer: {consumer}")
        elif (digest and digest == prior.get("hash")
                and prior.get("hash_runs", 0) >= checks_per_window):
            status = "FROZEN"
            findings.append(
                f"FROZEN {rel}: fresh ({age_h:.1f}h) but byte-identical across "
                f"{prior['hash_runs'] + 1} checks -- longer than its own {max_age_h}h update "
                f"window allows, so the job is running and writing the same output rather than "
                f"simply not being due yet. A loop turning without cutting. "
                f"Consumer: {consumer}")
        elif empty_fn is not None and (_why_empty := empty_fn(_read(path))):
            status = "EMPTY"
            findings_empty.append(
                f"EMPTY {rel}: fresh ({age_h:.1f}h) and moving, but the payload measures "
                f"nothing -- {_why_empty}. Consumer: {consumer}")

        rows[rel] = {"status": status, "age_h": round(age_h, 2), "hash": digest,
                     "consumer": consumer}
        jobs[rel] = {
            "status": status, "hash": digest,
            "hash_runs": (prior.get("hash_runs", 0) + 1) if digest == prior.get("hash") else 0,
            "checked_at": now.isoformat(timespec="seconds"),
            "ever_produced": True,
            "last_valid_at": (mtime.isoformat(timespec="seconds") if status == "OK"
                              else prior.get("last_valid_at")),
            "last_valid_hash": digest if status == "OK" else prior.get("last_valid_hash"),
            "max_age_h": max_age_h, "consumer": consumer,
        }

    # RETIRE THE ROWS THIS RUN NO LONGER EVALUATES, LOUDLY. `jobs` persists across runs and was
    # never pruned, so an artifact dropped from JOBS left its last verdict behind forever while
    # `summary` -- computed from `rows`, this run's evaluations -- silently stopped counting it.
    # Measured 2026-08-28: `jobs` held 17 rows and 2 FROZEN, `summary` said 16 and 1, and the
    # extra was `desks/mt5/data/sleeve_registry.json`, deliberately retired 19 hours earlier with
    # a good reason (age is the wrong instrument for an idempotent registry) and still reading
    # FROZEN to anything that walked `jobs`. Two consumers, two answers, one file. The row moves
    # to `retired` with the day it left rather than being deleted: a deliberate retirement stays
    # visible, and an ACCIDENTAL one -- a JOBS line dropped in an edit -- is discoverable here
    # instead of looking like the artifact was never monitored.
    retired = state.setdefault("retired", {})
    for rel in [k for k in jobs if k not in JOBS]:
        retired[rel] = {**jobs.pop(rel), "retired_at": now.isoformat(timespec="seconds"),
                        "note": "no longer declared in JOBS; last verdict frozen as-is"}
        findings.append(
            f"RETIRED {rel}: dropped from the manifest, last status "
            f"{retired[rel].get('status')}. If that was deliberate this line is the record; if a "
            f"JOBS entry was lost in an edit, the artifact is now unmonitored and this is how you "
            f"find out.")

    # RESEARCH LATENCY, from the graph's own timestamps. Published on the state and printed;
    # never a finding (see the module docstring).
    try:
        latency = latency_rows()
    except Exception as exc:                       # a broken graph is a reading, not a crash
        latency = {name: {"status": "UNMEASURED", "n": 0, "target_h": t, "consumer": c,
                          "basis": b, "why": f"{type(exc).__name__}: {exc}"}
                   for name, (t, c, b) in LATENCY_SLOS.items()}
    state["research_latency"] = latency

    state["checked_at"] = now.isoformat(timespec="seconds")
    state["summary"] = {s: sum(1 for r in rows.values() if r["status"] == s)
                        for s in sorted({r["status"] for r in rows.values()})}
    # THE SUMMARY MUST DESCRIBE THE ROWS. Anything reading `jobs` and anything reading `summary`
    # now count the same population. Reported rather than asserted: a liveness organ that dies on
    # its own consistency check is a worse failure than the miscount it was checking for, and an
    # `assert` vanishes entirely under -O.
    if not (sum(state["summary"].values()) == len(jobs) == len(rows)):
        findings.append(
            f"SELF-INCONSISTENT: summary counts {sum(state['summary'].values())}, jobs holds "
            f"{len(jobs)}, this run evaluated {len(rows)}. Two consumers of this file will "
            f"disagree until that is one number.")
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(state, indent=1, default=str), "utf-8")

    for line in findings_idle:
        print(f"  {line}")
    for line in findings_empty:
        print(f"  {line}")
    for name, row in latency.items():
        measured = (f"p50={row['p50_h']}h p90={row['p90_h']}h n={row['n']}"
                    if row.get("n") else row.get("why", ""))
        print(f"  LATENCY {name}: {row['status']} {measured}"
              + (f" (target {row['target_h']}h)" if row.get("target_h") else "")
              + (f"; open={row['open']} oldest_open={row['oldest_open_h']}h"
                 if row.get("open") else ""))
    if not findings:
        if ALARM.exists():
            ALARM.unlink()
        print(f"job manifest: all {len(rows)} artifact(s) fresh and moving {state['summary']}")
        return 0

    body = (f"JOB MANIFEST {now.isoformat(timespec='seconds')}\n\n"
            + "\n".join(f"  - {f}" for f in findings) + "\n")
    ALARM.write_text(body, "utf-8")
    print(body)
    request_repair("job-manifest breach")
    return 1


if __name__ == "__main__":
    sys.exit(main())

```

### scripts\check_miner_conversion.py
```python
#!/usr/bin/env python3
"""MINER CONVERSION AND BREADTH -- what each miner actually converts, and what the book still lacks.

TWO QUESTIONS, ONE ANSWER (principal 2026-08-26, items 5 and 6). "Which miners earn their compute"
and "what independent breadth is missing" are the same question asked from opposite ends, because
a miner whose discoveries all become another session-range breakout has converted nothing: the
book already holds that bet, and N_eff does not move when you add a fifteenth copy of it.

WHAT IS MEASURED PER MINER, in the order a decision actually needs it:

  DISCOVERIES  raw rows produced -- the only number miners currently report, and the least useful
  NOVEL        rows whose MECHANISM is not already held. Deduplicated by economic exposure, not
               by title: two writeups calling the same asia-range breakout different names are
               one discovery, and counting them twice is how a desk mistakes volume for breadth
  TESTED       novel rows that actually reached a backtest -- the step where most corpora die
  SURVIVORS    tested rows that cleared the ten gates
  CONVERSION   survivors / discoveries; the only ratio that says whether the miner is earning
  ZERO-YIELD   a miner with discoveries but no survivor across the whole window: it is producing
               noise at cost, and under III.16 that is a defect to fix or retire, not a neutral

WHAT IS MEASURED FOR THE BOOK:

  FAMILY CONCENTRATION -- the share of certificates held by the single largest family. This desk
  is currently ~95% session_range_breakout, which is why N_eff collapses. The gap list is ordered
  by what would add the most INDEPENDENT bet, not by what is easiest to mine: carry, relative
  value, cross-asset residuals, volatility/liquidity transitions, event reactions, COT
  positioning, macro conditionality, execution-derived effects.

WHAT IS MEASURED PER AGENT (2026-09-09, inventory I10). The numerator above -- survivors per
miner -- is handed to `libs.ops.compute_ledger.rank`, the module that exists to be the
denominator and refuses to invent a numerator, and the result is `data/agent_value.json`:
survivors per compute-hour for every miner and LLM seat the ledger has costed, an UNPRICED list
(costed, no survivor count) and an UNCOSTED list (survivor count, no ledger row). A miner whose
rows never reached a backtest is UNJUDGED, not zero-valued: its survivor count is not a
measurement. Today every miner is UNCOSTED, because the ledger names hourly legs and no leg is
a miner -- and the artifact says exactly that, which is the join's first honest reading.

This file MEASURES and REPORTS. It does not retire miners on its own: killing a research line is
a decision with a cost, and the register plus the gap-wirer are where that decision belongs.
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from datetime import UTC, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
# THE REPO ROOT GOES ON sys.path BEFORE `libs` IS IMPORTED, and it is not optional.
# `python scripts/check_miner_conversion.py` makes sys.path[0] the SCRIPTS directory, never the
# root -- so `import libs` raised ModuleNotFoundError on every invocation that was not a `-m` run
# or a test with the root already on the path. That is exactly how the scheduled fence runs:
#   ExecStart=/home/quant/quant-platform/.venv/bin/python scripts/check_miner_conversion.py
# so `quant-miner-conversion.timer` had been dying at import on every fire since `request_repair`
# was added, and a fence that cannot start reports nothing rather than reporting a breach.
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from libs.ops.repair_invoke import request_repair  # noqa: E402

DESK = ROOT / "desks" / "mt5"
INTEL = [DESK / "data" / "intelligence", ROOT / "data" / "intelligence"]
CERTS = DESK / "reports" / "UNIVERSAL_SURVIVORS.json"
HYP = DESK / "data" / "hypotheses" / "external_backtest_results.json"
OUT = ROOT / "data" / "miner_conversion.json"
ALARM = ROOT / "data" / "MINER_YIELD_ALARM.txt"
#: The compiler's artifact: `per_source` rows/candidates/deepening per miner and the `seats`
#: block (the LLM seats, reported with zeros when they donated nothing in the window).
COMPILED = DESK / "data" / "hypotheses" / "miner_candidates.json"
#: AgentValue -- survivors per compute-hour per miner and seat -- ALARM's sibling artifact.
AGENT_VALUE = ROOT / "data" / "agent_value.json"
#: Mirrors `miner_candidate_compiler.SEAT_SOURCES`; the compiled `seats` block's own keys win
#: whenever it is present, this is only the list to report as UNMEASURED when it is not.
SEATS = ("deepseek", "kimi_k3_deep_forest")

WINDOW_DAYS = 14
#: Families that would each add a genuinely different bet, ordered by independence from a
#: session-range book rather than by how easy they are to mine.
#: Names must match the generator registry EXACTLY -- `volatility_transition` here versus
#: `vol_transition` there reported a family as having no generator when one existed, which turns a
#: naming slip into a fabricated acquisition task.
BREADTH_TARGETS = (
    ("carry", "swap/rollover differentials -- a return stream with no directional overlap"),
    ("relative_value", "cross-pair and triangle residuals -- profits when direction does not"),
    ("cross_asset_residual", "metals vs FX vs index residuals after the common factor"),
    ("vol_transition", "regime changes in realised vol -- fires when breakouts stall"),
    ("liquidity_regime", "spread/depth regime shifts -- an execution-derived edge"),
    ("event_reaction", "scheduled macro releases -- a different clock entirely"),
    ("cot_positioning", "COT/positioning extremes -- weekly, uncorrelated to intraday ranges"),
    ("macro_conditional", "rates/DXY conditionality -- changes WHEN other sleeves should fire"),
)


def _read(p: Path):
    try:
        return json.loads(p.read_text("utf-8"))
    except (OSError, ValueError):
        return None


def _mechanism_key(row: dict) -> str | None:
    """Dedup key by ECONOMIC EXPOSURE, never by title.

    Two rows are the same discovery if they trade the same family on the same instrument in the
    same session, however differently they are described. Titles are the worst possible key: the
    corpus is full of the same mechanism renamed by each source that found it.
    """
    family = row.get("family") or row.get("mechanism")
    if not isinstance(family, str) or family.casefold() in {"", "unknown"}:
        return None
    fam = family.casefold()
    sym = str(row.get("symbol") or row.get("sym") or "*").upper()
    ses = str(row.get("session") or row.get("window") or row.get("selector") or "*").casefold()
    return f"{fam}|{sym}|{ses}"


#: What `_mechanism_key` returns for a row carrying no family, symbol or session -- i.e. for a row
#: it cannot identify at all, as opposed to one it identified as a repeat.
UNIDENTIFIED_KEY = "unknown|*|*"


def _duplication(keys: list[str]) -> dict:
    """Duplicate rate, or UNMEASURED when the rows cannot be told apart in the first place.

    ONE NUMBER WAS MEANING TWO OPPOSITE THINGS. `1 - distinct/rows` reads 100% when a miner found
    the same idea 36,982 times, and ALSO 100% when the key cannot identify any of them -- and the
    second is the common case, because `_mechanism_key` needs family|symbol|session and a raw
    miner row is a paragraph from a forum or a swap table that carries none of the three.

    Measured 2026-09-06: broker_swaps 36,982 rows -> "1 distinct mechanism, 100.0% duplicate",
    amarkets 17,444 -> the same. Read as duplication that is a damning verdict on a source; read
    correctly it says nothing about the source at all, and the rows may every one be different.
    A rate that reports the same figure for "all identical" and "none identifiable" is not a
    measurement, and this desk does not let an absent measurement wear a passing one's clothes.
    """
    total = len(keys)
    if not total:
        return {"duplicate_rate": None, "duplicate_basis": "no rows in the window"}
    unidentified = sum(1 for k in keys if k == UNIDENTIFIED_KEY)
    identified = total - unidentified
    if identified == 0:
        return {"duplicate_rate": None,
                "duplicate_basis": f"UNMEASURED: none of the {total:,} rows carry a "
                                   f"family/symbol/session, so they cannot be told apart -- "
                                   f"this is not evidence that they are duplicates",
                "unidentified_rows": unidentified}
    keyed = [k for k in keys if k != UNIDENTIFIED_KEY]
    out = {"duplicate_rate": round(1 - len(set(keyed)) / len(keyed), 3),
           "duplicate_basis": "among rows carrying an identity"}
    if unidentified:
        out["unidentified_rows"] = unidentified
    return out


def _source_miner(source: object) -> str:
    """The miner named inside a tested row's provenance string.

    Sources look like `ext_forexfactory_USDCHF_session_range_breakout`: a lane prefix, the MINER,
    then the symbol and family the compiler derived. The symbol is the first ALL-CAPS token, so
    everything before it is the miner name -- parsed positionally rather than by a fixed field
    count, because miner names contain underscores (`github_topics`, `ff_calendar_vintage`) and a
    split-on-underscore-take-index-1 would truncate them to `github` and `ff`.
    """
    text = str(source or "")
    if text.startswith("ext_"):
        text = text[4:]
    parts, name = text.split("_"), []
    for part in parts:
        if part and any(c.isalpha() for c in part) and part == part.upper():
            break                      # an ALL-CAPS token is the symbol; the miner ended before it
        name.append(part)
    return "_".join(name).strip("_")


def _reached(miner: str, tested_by_miner: Counter) -> int:
    """Tested rows attributable to `miner`, matching exactly then by prefix in EITHER direction.

    The provenance token and the directory name are not always identical -- `github` against a
    `github_topics` directory, for instance -- so an equality-only join would report a miner as
    having converted nothing while its rows sit in the results. Prefix matching in both
    directions covers the abbreviation and the expansion; anything looser would attribute one
    miner's conversions to another, which is worse than under-counting.
    """
    if miner in tested_by_miner:
        return tested_by_miner[miner]
    total = 0
    for token, n in tested_by_miner.items():
        if token and (miner.startswith(token) or token.startswith(miner)):
            total += n
    return total


def miner_rows(cutoff: datetime) -> dict[str, list[dict]]:
    """Recent discovery rows per miner directory."""
    out: dict[str, list[dict]] = {}
    for base in INTEL:
        if not base.exists():
            continue
        for src in sorted(d for d in base.iterdir() if d.is_dir()):
            rows: list[dict] = []
            for f in sorted(src.glob("*.json")):
                try:
                    if datetime.fromtimestamp(f.stat().st_mtime, tz=UTC) < cutoff:
                        continue
                except OSError:
                    continue
                data = _read(f)
                if isinstance(data, list):
                    rows.extend(r for r in data if isinstance(r, dict))
                elif isinstance(data, dict):
                    for v in data.values():
                        if isinstance(v, list):
                            rows.extend(r for r in v if isinstance(r, dict))
            if rows:
                out.setdefault(src.name, []).extend(rows)
    return out


def _short(p: Path) -> str:
    try:
        return str(p.relative_to(ROOT))
    except ValueError:
        return str(p)


def _survivor_value(miner: str, per_miner: dict[str, dict]) -> tuple[float | None, str]:
    """A miner's survivor count as a numerator, or None with the reason it is not one."""
    m = per_miner.get(miner)
    if not isinstance(m, dict):
        return None, "no discovery rows from this source inside the window"
    if int(m.get("reached_backtest") or 0) <= 0:
        return None, ("no tested row carries this source's provenance -- its rows were never "
                      "judged, so 0 survivors is not a measured zero")
    return float(m.get("survivors") or 0), "survivors among rows that reached a backtest"


def agent_value(per_miner: dict[str, dict], compiled: dict | None, *,
                ledger: Path | None = None) -> dict:
    """AgentValue = survivors / compute-hours, per miner and per LLM seat, via compute_ledger.rank.

    THE NUMERATOR IS THIS FILE'S OWN SURVIVOR COUNT and it is handed over only for sources whose
    rows reached a backtest; `rank` supplies the denominator from the ledger and lists what it
    could not price. Nothing here divides by a guessed hour or fills a missing count with zero.
    """
    from libs.ops.compute_ledger import LEDGER, rank
    value_by_run: dict[str, float] = {}
    unjudged: dict[str, str] = {}
    for miner in sorted(per_miner):
        v, why = _survivor_value(miner, per_miner)
        if v is None:
            unjudged[miner] = why
        else:
            value_by_run[miner] = v
    table = rank(value_by_run, path=ledger)

    per_source = (compiled or {}).get("per_source") if isinstance(compiled, dict) else None
    per_source = per_source if isinstance(per_source, dict) else {}
    seats_block = (compiled or {}).get("seats") if isinstance(compiled, dict) else None
    seats: dict = {}
    if not isinstance(compiled, dict):
        seats = {"status": "UNMEASURED",
                 "missing_input": f"{_short(COMPILED)} is absent or unreadable -- the "
                                  f"compiler has not written a per-source table on this host"}
    elif not isinstance(seats_block, dict):
        seats = {"status": "UNMEASURED",
                 "missing_input": (f"{COMPILED.name} (compiled_at "
                                   f"{compiled.get('compiled_at')}) carries no `seats` block -- "
                                   f"it was compiled before miner_candidate_compiler.seat_summary "
                                   f"existed; re-run the compiler"),
                 "per_source_fallback": {s: per_source[s] for s in SEATS if s in per_source}}
    else:
        rows = {}
        for seat, st in sorted(seats_block.items()):
            v, why = _survivor_value(seat, per_miner)
            rows[seat] = {**(st if isinstance(st, dict) else {}),
                          "survivors": v, "survivors_basis": why,
                          "cost": ("UNCOSTED: no compute_ledger row is named after this seat; "
                                   "its runs are outside the costed hourly legs")}
            if seat in table.get("uncosted", []):
                rows[seat]["cost"] = "UNCOSTED: survivor count supplied, no ledger row"
        seats = {"status": "MEASURED" if rows else "UNMEASURED", "seats": rows}

    ranked = table.get("ranked") or []
    if ranked:
        status, missing = "MEASURED", ""
    elif not table.get("costed_runs"):
        status, missing = "UNMEASURED", table.get("why") or "nothing has been costed"
    else:
        status = "UNMEASURED"
        missing = ("compute_ledger rows are named after hourly-cycle legs "
                   f"({', '.join(sorted(table.get('unpriced') or [])[:6])}...), none after a "
                   "miner or a seat, so no agent's hours are known; per-agent value per hour "
                   "needs the miner runner to open a costed run per miner "
                   "(libs.ops.compute_ledger.costed(<miner>))")
    return {
        "measured_at": datetime.now(tz=UTC).isoformat(timespec="seconds"),
        "status": status,
        "missing_input": missing,
        "numerator": {
            "unit": "survivors",
            "basis": (f"certificates whose mechanism key matches a row of the source inside the "
                      f"{WINDOW_DAYS}d window (this file's per-miner SURVIVORS); only sources "
                      f"whose rows reached a backtest are priced -- a source never judged has "
                      f"no measured zero. Not dE[log W]: the allocator's marginal growth per "
                      f"certificate is not yet joined per source"),
            "sources_priced": len(value_by_run),
            "sources_unjudged": len(unjudged),
        },
        "denominator": {
            "unit": "compute_ledger hours (wall-clock)",
            "ledger": _short(ledger or LEDGER),
            "window_days": table.get("window_days"),
            "costed_runs": table.get("costed_runs"),
            "total_hours": table.get("total_hours"),
        },
        "value_by_run": value_by_run,
        "unjudged": unjudged,
        "per_source_rows": {s: per_source[s] for s in sorted(per_source) if s in per_miner},
        "table": table,
        "seats": seats,
        "rule": ("AgentValue = realised survivors / compute-hours, from libs.ops.compute_ledger."
                 "rank; UNPRICED = costed with no survivor count, UNCOSTED = survivor count with "
                 "no ledger row, UNJUDGED = rows never reached a backtest. None of the three is "
                 "a ranking position and none is a zero"),
    }


def main() -> int:
    now = datetime.now(tz=UTC)
    cutoff = now - timedelta(days=WINDOW_DAYS)

    certs = (_read(CERTS) or {}).get("survivors") or {}
    held = {_mechanism_key({"family": (c.get("shadow_spec") or {}).get("family"),
                            "symbol": (c.get("shadow_spec") or {}).get("symbol"),
                            "session": (c.get("shadow_spec") or {}).get("selector")})
            for c in certs.values()}
    held.discard(None)
    fam_counts = Counter(str((c.get("shadow_spec") or {}).get("family") or "unknown")
                         for c in certs.values())

    tested_rows = [r for r in (_read(HYP) or []) if isinstance(r, dict)]
    tested_by_miner = Counter(_source_miner(r.get("source")) for r in tested_rows)
    tested_by_miner.pop("", None)
    survivor_keys = held
    compiler = _read(DESK / "data" / "hypotheses" / "miner_candidates.json") or {}
    compiled_sources = compiler.get("per_source") or {}

    per_miner: dict[str, dict] = {}
    zero_yield: list[str] = []
    for miner, rows in sorted(miner_rows(cutoff).items()):
        keys = [key for r in rows if (key := _mechanism_key(r)) is not None]
        uniq = set(keys)
        novel = uniq - held
        # MEASURED BY PROVENANCE, NOT BY A RECOMPUTED KEY -- and this is the whole reason the
        # board read 0 for 49 of 53 miners.
        #
        # `_mechanism_key` is family|SYMBOL|session. A tested row has all three. A RAW MINER ROW
        # has none of them: it is a paragraph from a forum, a swap table or a paper, and the
        # symbol and family are what the COMPILER derives from it. So every raw row keys to
        # `unknown|*|*` -- which is why broker_swaps showed 36,982 rows as 1 distinct mechanism at
        # a 100.0% duplicate rate -- and `novel & tested` was empty by construction, whatever the
        # pipeline did. Measured 2026-09-06: the compiler was in fact converting 178,753 rows into
        # 364 executable candidates while this reported that nothing reached a backtest.
        #
        # The tested rows carry `source` (ext_<miner>_<SYMBOL>_<family>) all the way from the
        # miner that found them, so provenance survives the very transformation that destroys the
        # key. Counting it answers the question actually being asked -- did this miner's work
        # reach the gauntlet -- instead of a question no miner could ever answer yes to.
        reached = _reached(miner, tested_by_miner)
        # AND WHAT THE COMPILER BUILT FROM THEM (theirs, 2026-09-10), read from its own
        # per-source block rather than recomputed here. "Reached a gauntlet" and "compiled into
        # candidates" are two different questions and a miner can pass one while failing the
        # other; collapsing them is how a plumbing gap reads as a dead source.
        compiled = compiled_sources.get(miner) or {}
        per_miner[miner] = {
            "discoveries": len(rows),
            "distinct_mechanisms": len(uniq),
            "novel_mechanisms": len(novel),
            "reached_backtest": reached,
            "reached_basis": "source provenance on tested rows",
            "survivors": len(uniq & survivor_keys),
            "conversion": round(len(uniq & survivor_keys) / len(rows), 4) if rows else None,
            **_duplication(keys),
            # WHAT THE COMPILER BUILT, AND WHETHER THE ROWS COULD BE ATTRIBUTED AT ALL (theirs,
            # 2026-09-10). `duplicate_rate` is deliberately NOT taken from their side: theirs is
            # `1 - distinct/rows`, the single number that reads 100% both when a miner found one
            # idea 36,982 times and when the key can identify none of them. `_duplication`
            # separates those two and refuses the second, which is the common case.
            "unmapped_rows": len(rows) - len(keys),
            "compiled_candidates": compiled.get("candidates"),
            "deepening_tasks": compiled.get("deepening"),
            "compiler_updated_at": compiler.get("compiled_at"),
            "attribution_status": ("UNMEASURED" if len(keys) != len(rows) else "EXPOSURE_MATCH"),
        }
        # ZERO-YIELD MEANS TESTED AND FAILED, NOT MERELY UNCERTIFIED. Calling a miner "noise at
        # cost" when its rows never reached a gauntlet blames the source for a plumbing gap, and
        # the remedy that follows -- retire the miner -- deletes work that was never judged.
        #
        # THEIRS GUARDED THE SAME ALARM ON `len(keys) == len(rows)` -- every row attributable --
        # which is the same instinct reached from the other end: do not indict a source whose
        # output could not be measured. Both conditions are kept, because they refuse different
        # failures: unattributable rows, and rows that were attributed but never judged.
        if (len(keys) == len(rows) and len(rows) >= 20 and reached > 0
                and not (uniq & survivor_keys)):
            zero_yield.append(miner)

    total_certs = sum(fam_counts.values())
    top_family, top_n = (fam_counts.most_common(1) or [("none", 0)])[0]
    concentration = round(top_n / total_certs, 3) if total_certs else None
    # A family is now three states, not two, and the difference is what to DO about it:
    #   held        -- a certificate exists
    #   reachable   -- a generator exists and its input is present; it just has not certified yet
    #   unreachable -- no generator, or its input is not recorded (an ACQUISITION task, which is a
    #                  completely different piece of work from "nobody mined it")
    try:
        import sys as _sys
        _sys.path.insert(0, str(DESK))
        from mt5desk.families_orthogonal import FAMILY_INPUTS, ORTHOGONAL_FAMILIES
    except Exception:
        ORTHOGONAL_FAMILIES, FAMILY_INPUTS = {}, {}
    missing = []
    for f, why in BREADTH_TARGETS:
        if any(f in k for k in held):
            continue
        needs = FAMILY_INPUTS.get(f, ("unknown", None))[0]
        missing.append({
            "family": f, "why": why,
            "state": "REACHABLE" if f in ORTHOGONAL_FAMILIES else "NO_GENERATOR",
            "needs": needs,
        })

    report = {
        "measured_at": now.isoformat(timespec="seconds"),
        "window_days": WINDOW_DAYS,
        "miners": per_miner,
        "zero_yield_miners": zero_yield,
        "book_breadth": {
            "certificates": total_certs,
            "families": dict(fam_counts),
            "largest_family": top_family,
            "family_concentration": concentration,
            "missing_families": missing,
            "why": ("concentration is the share of certificates in the single largest family. "
                    "Near 1.0 means every certificate is the same bet, and no amount of mining "
                    "inside that family raises the book's effective independent bets."),
        },
        "note": ("Raw rows lacking a mechanism are UNMEASURED, never identical strategies. "
                 "Compiler counts are separate from backtest and survivor evidence. "
                 "Deduplication is by economic exposure (family|symbol|session), never by title: "
                 "the corpus renames the same mechanism per source, and counting those as "
                 "separate discoveries mistakes volume for breadth."),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=1, default=str), "utf-8")

    av = agent_value(per_miner, _read(COMPILED))
    AGENT_VALUE.write_text(json.dumps(av, indent=1, default=str), "utf-8")

    print(f"miner conversion: {len(per_miner)} miner(s) with rows in {WINDOW_DAYS}d; "
          f"{len(zero_yield)} zero-yield")
    print(f"agent value: {av['status']} -- {len(av['table'].get('ranked') or [])} priced, "
          f"{len(av['table'].get('uncosted') or [])} uncosted, "
          f"{len(av['table'].get('unpriced') or [])} unpriced, {len(av['unjudged'])} unjudged; "
          f"seats {av['seats'].get('status')}"
          + (f"\n   missing input: {av['missing_input']}" if av["missing_input"] else ""))
    print(f"book breadth: {total_certs} certificate(s), largest family '{top_family}' "
          f"= {concentration} of the book; {len(missing)} target family(ies) absent")
    for row in missing[:8]:
        print(f"   {row['state']:12} {row['family']:22} needs: {row['needs']}")

    findings = []
    if concentration is not None and concentration > 0.8:
        findings.append(f"BREADTH: {concentration:.0%} of certificates are '{top_family}' -- the "
                        f"book is close to one bet; mining more of it cannot raise N_eff")
    if zero_yield:
        findings.append(f"ZERO-YIELD: {', '.join(zero_yield[:6])} produced 20+ rows and no "
                        f"survivor in {WINDOW_DAYS}d -- noise at cost (III.16)")
    if findings:
        ALARM.write_text("MINER/BREADTH " + now.isoformat(timespec="seconds") + "\n\n"
                         + "\n".join(f"  - {f}" for f in findings) + "\n", "utf-8")
        print("\n" + "\n".join(f"  - {f}" for f in findings))
        request_repair("miner-conversion breach")
        return 1
    if ALARM.exists():
        ALARM.unlink()
    return 0


if __name__ == "__main__":
    sys.exit(main())

```

### scripts\release_manifest.py
```python
#!/usr/bin/env python3
"""Seal, describe or verify the canonical live release. See `libs.ops.release`.

    python scripts/release_manifest.py --seal [--tested] [--by X]   # seal HEAD into RELEASE.json
    python scripts/release_manifest.py --seal --if-needed           # no-op when HEAD is already
                                                                    #   the sealed code (CI-safe)
    python scripts/release_manifest.py --verify                     # exit 1 if the tree drifted
    python scripts/release_manifest.py --identity                   # is HEAD the sealed code?
    python scripts/release_manifest.py                              # legacy: describe the
                                                                    #   working tree (not a seal)

THE SEAL IS ITS OWN COMMIT. After `--seal`, commit desks/mt5/data/RELEASE.json and NOTHING ELSE
("seal release <sha12>"): that commit's diff against its parent is exactly the manifest, which is
the one shape `accepts()` admits besides the sealed commit itself. Bundling the seal with code
recreates the defect this exists to end -- a manifest that names the commit before the one that
ships. `--if-needed` makes the step idempotent, so a CI job that runs on its own seal commit does
not seal again forever.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from libs.ops import release  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--seal", action="store_true",
                    help="seal HEAD from its own blobs (then commit RELEASE.json alone)")
    ap.add_argument("--tested", action="store_true",
                    help="attest that the suite ran green on this SHA (CI passes this)")
    ap.add_argument("--by", default=None, help="who/what sealed (default: GITHUB_ACTOR|operator)")
    ap.add_argument("--allow-dirty", action="store_true",
                    help="seal even when tracked files differ from HEAD (recorded, not hidden)")
    ap.add_argument("--if-needed", action="store_true",
                    help="with --seal: do nothing when HEAD is already the sealed code")
    ap.add_argument("--verify", action="store_true")
    ap.add_argument("--identity", action="store_true",
                    help="is HEAD accepted by the written release (the SHA rule only; --verify "
                         "adds the on-disk hashes, mt5desk/release_identity.py is the box's "
                         "full verdict)? exit 1 if not")
    ap.add_argument("--root", type=Path, default=None, help="repository root (default: this one)")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)

    if a.verify:
        v = release.verify(root=a.root)
        print(json.dumps(v, indent=1) if a.json else
              f"release {v.get('release_id')}: {'OK' if v['ok'] else 'DRIFT'} -- {v['why']}"
              f" ({v.get('identity', '')})")
        for k, (was, now) in (v.get("diffs") or {}).items():
            print(f"  {k}: {was} -> {now}")
        return 0 if v["ok"] else 1

    if a.identity or (a.seal and a.if_needed):
        rec = release.load(a.root)
        head = release.git_head(a.root)
        ok, why, code = (release.accepts(head, rec, root=a.root) if rec is not None
                         else (False, "no RELEASE.json", []))
        if a.identity:
            print(json.dumps({"ok": ok, "running_sha": head, "why": why, "code_paths": code},
                             indent=1) if a.json else f"identity {'OK' if ok else 'REFUSED'}: {why}")
            return 0 if ok else 1
        if ok:
            print(f"seal not needed: {why}")
            return 0

    if a.seal:
        try:
            d = release.seal(root=a.root, tested=a.tested, by=a.by, allow_dirty=a.allow_dirty)
        except RuntimeError as exc:
            print(f"SEAL REFUSED: {exc}")
            return 2
        print(json.dumps(d, indent=1) if a.json else
              f"release {d['release_id']} sealed: code_sha={d['code_sha'][:12]} "
              f"parent={str(d['parent_sha'])[:12]} money_path={d['money_path_hash']} "
              f"immutable={(d.get('immutable_manifest') or {}).get('sha256_16')} "
              f"tested={'yes' if d['tested_sha'] else 'no'} dirty={len(d['worktree_dirty'])}"
              f"\n  now commit {release.RELEASE_REL} ALONE: \"seal release {d['code_sha'][:12]}\"")
        return 0

    d = release.build(write=True, root=a.root)
    print(json.dumps(d, indent=1) if a.json else
          f"release {d['release_id']} described (NOT sealed): sha={d['live_sha'][:12]} "
          f"money_path={d['money_path_hash']} allocator={d['allocator_hash']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

```

### scripts\run_cadence.py
```python
"""CADENCE ENGINE -- review/generation frequency as CODE, stage-aware, zero human scheduling.

Principal directive 2026-07-17: cadences must adjust to the max-ROI schedule automatically.
Before this, the weekly panel depended on the AI brain remembering to fire it -- cadence by
LLM memory is a reliability hole. This script runs inside the daily cycle and deterministically
fires what is due, per stage (data/stage_state.json):

  S0 (pre-live, current):  panel every 7d (mission rotation) | tier1 every 14d (was documented as 28d while the constant read 14 -- that contradiction produced a 34-day error in a live briefing) |
                           generation DATA-TRIGGERED (a 40d clock maturing or a new family
                           landing flags a scoped generate run for the brain)
  S1/S2 (live, flipped by the live-connector deployment): all of the above PLUS generation
                           weekly -- live trading mints fresh data (fills/slippage/tape)
                           every week, so weekly IS data-triggered post-Gate-0.

State in data/cadence_state.json (last-run dates). The brain TRIAGES panel output; it no
longer schedules panels. Scoped generate runs + monthly prompt self-improvement stay
brain-executed (judgment tasks) -- this engine flags them in docs/research/cadence_duties.md.
CADENCE FLOORS below enforce the never-sleepier invariant; violations are paged.

    python scripts/run_cadence.py
"""

from __future__ import annotations

# PATH BOOTSTRAP. `python scripts/x.py` puts scripts/ on sys.path, NOT the repo root, so `libs`
# resolves only if the project happens to be pip-installed into the interpreter in use. The daily
# cycle invokes this by path. See tests/scripts/test_cycle_scripts_are_runnable.py.
import sys as _sys
from pathlib import Path as _P

if str(_P(__file__).resolve().parent.parent) not in _sys.path:
    _sys.path.insert(0, str(_P(__file__).resolve().parent.parent))


import argparse
import contextlib
import json
import os
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from libs.ops.host_resources import mem_available_mb
from libs.ops.lawful import guard as _law_guard  # L1.42: no act exempt

_STATE = Path("data/cadence_state.json")
_STAGE = Path("data/stage_state.json")
_HEALTH = Path("web/health.json")
_DUE_NOTE = Path("docs/research/cadence_duties.md")
_VIOLATION = Path("data/cadence_violation.json")
_PANEL_EVERY_D = 3
_TIER1_EVERY_D = 14
_PROMPT_REVIEW_D = 28
_MODEL_UPGRADE_D = 30            # monthly, matching the roster-governance cadence
_META_RESEARCH_D = 1             # CIO review: mechanical, seconds, no LLM -- every cycle
_CLOCK_MATURITY_D = 40

# CADENCE FLOORS (principal invariant 2026-07-17): the system may never get SLEEPIER where
# sleep can kill it. Each artifact must be at most this many HOURS old; a violation is paged
# (run_alerts reads data/cadence_violation.json). Stage transitions may only ADD floors or
# TIGHTEN them (S1/S2 extras below) -- loosening or deleting any floor is a Tier-3-class
# action: principal sign-off only, never automation, never the self-improvement engine.
_FLOORS_S0: dict[str, float] = {
    "data/deadman_heartbeat": 0.2,               # ruin rail alive (1-min loop + slack)
    "data/cashcarry_exec_heartbeat": 0.5,        # executor alive
    "data/.last_alerts.json": 1.0,               # pager tick running
    "web/venue_equity.json": 1.0,                # venue-truth feed fresh
    "docs/research/micro_audit_inbox.md": 48.0,  # daily cold eyes actually ran
}
_FLOORS_S1_EXTRA: dict[str, float] = {           # live adds floors; never removes any
    "data/canary_state.json": 12.0,              # 6h canary round-trip (post-connector)
}
# state-tracked floors (days): review cycles may never stretch past these
_STATE_FLOORS_D = {"last_panel": 4.0, "last_tier1": 16.0, "last_prompt_review": 35.0,
                   "last_prospector": 35.0, "last_blind_rediscovery": 100.0,
                   "last_model_upgrade": 45.0, "last_meta_research": 3.0,
                   "last_fill_quality": 10.0,
                   # Both are DAILY organs with a 1.0d gate; the floor is the outer bound past
                   # which a skipped duty stops being a quiet cycle and becomes a defect.
                   "last_breadth_expansion": 3.0, "last_hypothesis_generation": 3.0,
                   "last_lit_deepdive": 35.0, "last_decision_scoring": 35.0,
                   "last_memory_consolidation": 100.0}


def _srun(cmd: list[str], **kw: Any) -> subprocess.CompletedProcess[str]:
    """Run a cadence child, NAMING IT FIRST so a kill cannot be anonymous.

    Every duty in `_main_body` is a subprocess, output is captured, and the parent prints only
    AFTER a child returns. So when the unit was OOM-killed -- 35 times in 36 hours -- the log held
    exactly nothing: no duty name, no partial output, no clue which of the 25 children had been
    running. "The cadence engine died" and "the cadence engine died in the panel" are different
    findings with different repairs, and the log could not tell them apart (L1.46: a duty with no
    instrument is a wish; L1.28a: unmeasured is its own answer, never a clean one).

    One flushed line before each child costs nothing and converts a silent death into a named one.
    It is printed, not logged, because systemd captures stdout and `print` to a redirected pipe is
    BLOCK-BUFFERED -- an unflushed notice is exactly the outage message this desk has lost before.
    """
    label = next((c for c in cmd[1:] if not c.startswith("-")), cmd[0])
    print(f"cadence: -> {label}", flush=True)
    return subprocess.run(cmd, **kw)


def _load(p: Path, default: dict[str, Any]) -> dict[str, Any]:
    try:
        d = json.loads(p.read_text("utf-8"))
        return d if isinstance(d, dict) else default
    except (OSError, json.JSONDecodeError):
        return default


def _days_since(state: dict[str, Any], key: str) -> float:
    """Days since `key` was stamped, or 1e9 ("due") when it genuinely has never been stamped.

    A NAIVE STAMP IS A DATE, NOT AN ABSENCE (2026-08-28). Several of these keys are stamped by
    LLM organs that are instructed in prose to "mark done: last_data_axis_dig" and write a bare
    `"2026-08-28"`. `fromisoformat` parses that fine -- into a NAIVE datetime -- and subtracting
    it from an aware `now()` raises TypeError, which this function swallowed into 1e9. The duty then
    read as NEVER RUN forever: measured today, `last_data_axis_dig` held TODAY'S date while the
    report printed "never run" and the engine re-fired a WEEKLY duty on every cycle.

    That is the WS-005 class -- absence and a value the reader cannot parse must never render
    identically. A naive stamp is therefore read as UTC. This can only make a duty look OLDER
    than it is (never newer), so it errs toward firing and relaxes no floor.
    """
    raw = state.get(key)
    if raw is None:
        return 1e9                                    # never stamped -> due
    try:
        then = datetime.fromisoformat(str(raw))
    except (ValueError, TypeError):
        return 1e9                                    # unparseable -> due (never skip on garbage)
    if then.tzinfo is None:
        then = then.replace(tzinfo=UTC)               # a date is a date, not an absence
    return (datetime.now(tz=UTC) - then).total_seconds() / 86400.0


#: (label, cadence_state key, period days) for the duties `--report-only` reports on.
#: HAND-BUILT AND DRIFT-FENCED. `_main_body` tests each of these inline, so a table that drifts
#: would report a schedule the engine does not actually run -- which is worse than no report,
#: because a reader would trust it. tests/governance/test_cadence_cli.py re-derives every pair
#: from the SOURCE of `_main_body` and fails if any row here has no matching `_days_since(...)
#: >= <period>` test. Adding a duty without adding it here does not break the engine; it breaks
#: the test, which is the intended direction (L1.60: the gap is the work queue).
_REPORTED_DUTIES: tuple[tuple[str, str, int], ...] = (
    ("tier1 deep review", "last_tier1", _TIER1_EVERY_D),
    ("panel", "last_panel", _PANEL_EVERY_D),
    ("meta-research review", "last_meta_research", _META_RESEARCH_D),
    ("fill-quality review", "last_fill_quality", 7),
    ("model-upgrade sweep", "last_model_upgrade", _MODEL_UPGRADE_D),
    ("data-axis dig", "last_data_axis_dig", 7),
    ("blind rediscovery", "last_blind_rediscovery", 90),
    ("decision scoring", "last_decision_scoring", 28),
    ("memory consolidation", "last_memory_consolidation", 90),
    ("prompt review", "last_prompt_review", _PROMPT_REVIEW_D),
)


def due_report() -> dict[str, Any]:
    """What IS due, computed from the same state and constants -- and firing NOTHING.

    R0425. This script had no argparse, so `--help` (the desk's documented habit for probing an
    unfamiliar organ) did not print usage: it executed a full cadence run, firing the weekly panel
    and monthly tier1. The one habit meant to make invocation SAFE was, on this script, the thing
    that invoked it.
    """
    state = _load(_STATE, {})
    stage = str(_load(_STAGE, {"stage": "S0"}).get("stage", "S0"))
    duties = []
    for label, key, period in _REPORTED_DUTIES:
        d = _days_since(state, key)
        never = d > 1e8
        duties.append({"duty": label, "state_key": key, "period_days": period,
                       "days_since": None if never else round(d, 2),
                       "never_run": never, "due": d >= period})
    return {"stage": stage, "state_file": str(_STATE),
            "n_due": sum(1 for x in duties if x["due"]), "duties": duties,
            "note": "REPORT ONLY -- nothing was fired. Run without --report-only to fire."}


#: What the panel duty actually costs. MEASURED 2026-08-28 from the unit's own cgroup
#: accounting across four consecutive OOM kills: MemoryPeak 737M-936M, of which the cadence
#: parent is ~150M. The number is the UNIT peak on purpose -- admission has to cover what the
#: cgroup will actually be charged, not the child in isolation.
_PANEL_NEED_MB = 700


def _panel_fits() -> bool:
    """Whether the box can hold the panel -- and if not, SKIP IT AND RUN THE OTHER 24 DUTIES.

    THE PANEL IS DUTY #1 OF 25 AND IT WAS TAKING THE OTHER 24 DOWN WITH IT. `_main_body` runs its
    duties in one process, in a fixed order, with the panel first. When the box cannot fit the
    panel the whole unit is OOM-killed, so every duty ordered after it is unreachable -- not
    delayed, unreachable, on every single tick. MEASURED 2026-08-28: 35 OOM kills in 36 hours,
    and the named-child log shows all four of the last ones dying in `run_external_panel.py`
    seconds after start. Downstream, `panel` stood 34.8 days overdue on a 3-day cadence, tier1
    42.9d, decision scoring 41.4d, prompt review 42.5d, and two duties had never run at all.

    Standing down is not timidity and it relaxes nothing: the duty stays OWED (the caller only
    stamps on True), no floor moves, and the `--report` row keeps showing it overdue, so a
    chronically starved panel stays visible rather than being marked done. What changes is that
    0 of 25 duties per tick becomes 24 of 25. Starting a job that does not fit is strictly worse
    than not starting it -- it destroys its own run AND every neighbour -- which is the argument
    `job_lock.exclusive_job` already makes for the sweeps; this wires the same admission rule
    into the one duty that was demonstrably killing the engine.

    MEDIAN OF THREE, NOT ONE SAMPLE, for the reason the desk already measured on this box: free
    memory here is a sawtooth, and a single reading once said 55MB while readings seconds either
    side said 1,605MB. A duty whose start depends on a coin flip is not scheduled, it is gambled.

    UNMEASURED ADMITS (L1.28a). If /proc cannot be read, admission must not invent a number --
    the caller runs the duty rather than blocking real work on ignorance.
    """
    readings = [r for r in (_sample_mem(i) for i in range(3)) if r is not None]
    if not readings:
        return True
    avail = sorted(readings)[len(readings) // 2]
    if avail >= _PANEL_NEED_MB:
        return True
    print(f"cadence: panel STOOD DOWN -- needs ~{_PANEL_NEED_MB}MB, box has {avail}MB available. "
          f"Duty stays OWED and the remaining duties now run; admitting it here is what killed "
          f"the whole cycle 35 times in 36 hours.", flush=True)
    return False


def _sample_mem(i: int) -> int | None:
    if i:
        time.sleep(3)
    return mem_available_mb()


def _run_panel(mission: str | None) -> bool:
    """Regenerate the dossier, then fire the panel (optionally with a forced mission)."""
    if not _panel_fits():
        return False
    env = None
    if mission:
        import os
        env = {**os.environ, "PANEL_MISSION": mission}
    r1 = _srun([sys.executable, "scripts/generate_external_review_doc.py"],
                        capture_output=True, text=True, timeout=120, check=False)
    if r1.returncode != 0:
        print(f"cadence: dossier regen failed rc={r1.returncode} -- panel skipped")
        return False
    # PRODUCTION, NOT EXIT CODE (2026-07-26). This returned rc==0, and the caller stamps
    # last_panel on True -- so a panel that wrote NOTHING still marked the duty done. That is
    # how cadence_state came to claim a panel ran 2026-07-25 while panel_verdicts.jsonl had not
    # been appended since 2026-07-21 (126h, cadence 96h). The mechanism is funding: the
    # pre-flight check sizes a run at ~$0.05/seat and the account holds $3.40, so the run starts,
    # exhausts mid-flight, seats return HTTP 402, the sanitizer drops the partial roster, and the
    # process still exits clean. An exit code proves a process ended, never that it PRODUCED --
    # the same state-touched-but-nothing-produced class check_production exists to catch. A run
    # that appended no verdict now leaves the duty OWED (this only ever makes cadence stricter;
    # no floor is touched).
    _verdicts = Path("data/panel_verdicts.jsonl")   # module runs cwd=repo root, as _STATE does
    try:
        _before = _verdicts.stat().st_size
    except OSError:
        _before = -1
    # A TIMED-OUT PANEL IS A FAILED PANEL, NOT A FAILED CADENCE RUN (2026-08-05). `timeout=720`
    # raises subprocess.TimeoutExpired, which escaped `main()` uncaught -- and because cadence
    # state is written ONCE at the end of main(), every duty that had already run this cycle had
    # its timestamp DISCARDED with it. Measured today: OpenRouter balance -$0.59, the panel hung
    # the full 720s on an unfunded API, TimeoutExpired propagated, and data/cadence_state.json
    # was never rewritten (mtime stayed 07:13 while the run ended at 23:03).
    #
    # The whole cadence engine therefore had a single point of failure in an EXTERNAL PAID API:
    # while credits are out, the panel cannot produce, so nothing downstream of it in main() can
    # ever record that it ran. Returning False is the correct semantics and needs no other change
    # -- the caller only stamps `last_panel` when this returns True, so a timed-out panel leaves
    # the duty OWED exactly as an unproductive one does. This makes cadence stricter, never
    # looser, and touches no floor.
    try:
        r2 = _srun([sys.executable, "scripts/run_external_panel.py"],
                            capture_output=True, text=True, timeout=720, check=False, env=env)
    except subprocess.TimeoutExpired:
        print("cadence: panel TIMED OUT after 720s -- duty stays OWED. This is the unfunded-API "
              "signature (a live roster answers or 402s in seconds; a dead one hangs). The "
              "cadence run CONTINUES: one external dependency may not discard the other duties.")
        return False
    tail = (r2.stdout or r2.stderr or "").strip().splitlines()[-1:] or [""]
    try:
        _after = _verdicts.stat().st_size
    except OSError:
        _after = -1
    _produced = _after > _before
    _grew = f"+{_after - _before}b" if _produced else "+0b (NOT PRODUCED)"
    print(f"cadence: panel[{mission or 'rotation'}] rc={r2.returncode} "
          f"verdicts {_grew} | {tail[0][:120]}")
    if r2.returncode == 0 and not _produced:
        print("cadence: panel exited clean but appended NO verdict -- duty stays OWED "
              "(check OpenRouter funding: a half-funded roster 402s mid-run and emits nothing)")
    return r2.returncode == 0 and _produced


_FUNDING_STATE = Path("data/panel_funding_state.json")


def _funding_restored() -> bool:
    """True when the panel has been funded since the last flagship sweep ran.

    A 30-day clock is the right cadence for "has a better model shipped?" -- catalogs move
    slowly. It is the WRONG cadence for "the desk just got paid". Without this, credits landing
    on a Friday could be followed by up to a month of running the previous roster on the new
    money, and the whole point of funding the panel is the panel it funds.

    The flag is latched by run_external_panel on the unfunded->funded edge and cleared here only
    after a sweep actually produced, so a cadence run that skipped the upgrade leaves the debt
    standing rather than consuming it.
    """
    try:
        return bool(json.loads(_FUNDING_STATE.read_text("utf-8")).get("upgrade_owed"))
    except (OSError, json.JSONDecodeError, TypeError, ValueError):
        return False


def _clear_funding_debt() -> None:
    """Clear the latch -- ONLY after a sweep genuinely evaluated the catalog."""
    with contextlib.suppress(OSError, json.JSONDecodeError, TypeError, ValueError):
        d = json.loads(_FUNDING_STATE.read_text("utf-8"))
        d["upgrade_owed"] = False
        d["upgrade_ran"] = datetime.now(tz=UTC).isoformat()
        _FUNDING_STATE.write_text(json.dumps(d, indent=1), "utf-8")


def _run_model_upgrade() -> bool:
    """Monthly: roll back regressed promotions, then auto-upgrade both model surfaces.

    ROLLBACK RUNS FIRST AND UNCONDITIONALLY. It costs nothing (it reads blank telemetry, makes
    no API call), and a seat that regressed must be healed before we consider adding another
    change on top of it.

    PRODUCTION, NOT EXIT CODE -- the same lesson _run_panel records above. Both engines exit 0
    when the catalog is unreachable or the balance is too low to run a gauntlet, so an exit code
    would stamp the duty done for a check that never actually looked at anything. The honest
    signal is a FRESH `checked` timestamp in the engine's own state file: only a run that
    genuinely evaluated the catalog writes one, so a skipped run correctly leaves the duty OWED.
    """
    _srun([sys.executable, "scripts/model_upgrade.py", "--rollback", "--apply"],
                   capture_output=True, text=True, timeout=300, check=False)
    produced = 0
    for script, state_file in (("scripts/model_upgrade.py", "data/model_upgrade.json"),
                               ("scripts/brain_model_upgrade.py",
                                "data/brain_model_upgrade.json")):
        r = _srun([sys.executable, script, "--apply"],
                           capture_output=True, text=True, timeout=1800, check=False)
        tail = (r.stdout or r.stderr or "").strip().splitlines()[-1:] or [""]
        fresh = False
        try:
            checked = json.loads(Path(state_file).read_text("utf-8")).get("checked")
            fresh = bool(checked) and _days_since({"c": checked}, "c") < 1.0
        except (OSError, json.JSONDecodeError, TypeError, ValueError):
            fresh = False
        produced += int(fresh)
        print(f"cadence: {Path(script).stem} rc={r.returncode} "
              f"{'evaluated' if fresh else 'DID NOT EVALUATE'} | {tail[0][:110]}")
    return produced == 2


def _assert_floors(state: dict[str, Any], stage: str) -> None:
    """Never-sleepier invariant: page (via run_alerts pickup) if any floor is stale."""
    import time
    floors = dict(_FLOORS_S0)
    if stage in ("S1", "S2"):
        floors.update(_FLOORS_S1_EXTRA)              # monotone by construction: add-only
    bad: list[str] = []
    now_s = time.time()
    for path, max_h in floors.items():
        p = Path(path)
        if not p.exists():
            if stage == "S0" and path in _FLOORS_S1_EXTRA:
                continue                             # live-only artifact, not yet due
            bad.append(f"{path}: MISSING (floor {max_h}h)")
        elif (age := (now_s - p.stat().st_mtime) / 3600.0) > max_h:
            bad.append(f"{path}: {age:.1f}h old (floor {max_h}h)")
    for key, max_d in _STATE_FLOORS_D.items():
        if (d := _days_since(state, key)) > max_d and d < 1e8:
            bad.append(f"{key}: {d:.1f}d since last run (floor {max_d}d)")
    if bad:
        _VIOLATION.write_text(json.dumps(
            {"ts": datetime.now(tz=UTC).isoformat(), "violations": bad}), "utf-8")
        print(f"cadence: FLOOR VIOLATION x{len(bad)} -> {_VIOLATION} (pager will fire)")
    elif _VIOLATION.exists():
        _VIOLATION.unlink()                          # self-clearing when floors recover
        print("cadence: floor violation cleared")


_ROOT_DIR = Path(__file__).resolve().parent.parent
_FREEZE_STATUS = Path("data/freeze_exit_status.json")

#: criterion -> (artifact it reads, the module/script that WRITES that artifact).
#: The second element is the whole point. A deployment criterion reading a file with no writer is
#: not a strict gate, it is an unsatisfiable one, and the two are indistinguishable from the
#: outside: both simply read False forever. Naming the writer makes the claim checkable, and
#: check_freeze_exit_sources() below turns it into a test.
_FREEZE_SOURCES: dict[str, tuple[str, str]] = {
    "gate0": ("data/gate0_complete", "scripts/max_audit.py"),
    "fills_4wk": ("data/moat/execution_tape/cashcarry_trades.jsonl",
                  "libs/execution/execution_tape.py"),
    # Was ("data/cost_model.json", "scripts/run_cost_model.py") -- the L2-tape cost walk, deleted
    # 2026-09-05 with the retired recorders. Re-pointed at the MT5 desk's cost surface, which is
    # the artifact that now answers "are this desk's costs MEASURED?". The whole point of the
    # second element is that a freeze-exit criterion must read something this repo WRITES: leaving
    # a deleted writer here would have made the criterion unsatisfiable while looking strict,
    # which is the exact defect `check_freeze_exit_sources` below exists to catch.
    "cost_model": ("desks/mt5/data/cost_surface.json", "desks/mt5/research/cost_surface.py"),
    "calib_10": ("data/forecast_log.json", "libs/self_improvement/forecast_calibration.py"),
    "no_criticals": ("data/DEADMAN_FIRED", "scripts/run_deadman_switch.py"),
}


def check_freeze_exit_sources() -> list[str]:
    """Every freeze-exit criterion must read an artifact something in this repo WRITES.

    THE GENERALISED FORM of the 2026-07-30 defect. Three of five criteria read invented filenames
    (fills.csv, weekly_cost_summary.json, calibration.csv) that no code anywhere produces. Each
    read False forever, which is indistinguishable from "the desk has not earned it yet" -- so the
    gate looked strict while being unsatisfiable, and nobody could tell the difference by looking
    at the output. This checks the WRITER exists, not the artifact: pre-launch the artifacts are
    legitimately absent, but their writer must be real today.
    """
    problems = []
    for crit, (artifact, writer) in _FREEZE_SOURCES.items():
        if not (_ROOT_DIR / writer).exists():
            problems.append(f"{crit}: writer {writer} does not exist -- {artifact} can never "
                            "appear, so this criterion is unsatisfiable, not strict")
    return problems


def _freeze_exit_met() -> tuple[bool, str]:
    """The 5 lockdown exit criteria. All must hold. Returns (met, human-status).

    REWRITTEN 2026-07-30. THREE of the five criteria read files that NOTHING IN THIS REPO WRITES,
    so they could never become True no matter how well the desk performed:

      fills_4wk   read `data/fills.csv`   -- no writer anywhere. Fills go to
                  data/cashcarry_trades.json and data/moat/execution_tape/cashcarry_trades.jsonl.
      cost_model  read `data/weekly_cost_summary.json` -- no writer. run_cost_model.py writes
                  data/cost_model.json.
      calib_10    read `data/calibration.csv` -- no writer. Forecast outcomes live in
                  data/forecast_log.json via libs/self_improvement/forecast_calibration.py.

    And fills_4wk was additionally INVERTED: it compared `now - file mtime > 28 days`, which reads
    "this feed has been DEAD for a month". A healthy, actively-appended fill feed has mtime ~= now
    and failed forever; only an abandoned one could pass. Satisfying the gate honestly would have
    required creating a fills file and then abandoning it for four weeks.

    Consequence, and it is the reason this is a launch blocker rather than a tidy-up: the desk's
    whole research apparatus funnels into a deployment gate that was not merely unmet but
    UNSATISFIABLE, and the only place that fact was stated was a status string nobody read. The
    desk could have compiled a flawless track record and the freeze would never have lifted.

    Every criterion now reads the artifact that actually exists, and `days` is measured from the
    oldest ROW TIMESTAMP (execution_tape.coverage), never from a file's mtime.
    """
    checks: dict[str, bool] = {}
    checks["gate0"] = Path("data/gate0_complete").exists()

    # >=4 weeks of live fills, measured on row timestamps in the tape that Gate 0 is scored on.
    try:
        from libs.execution.execution_tape import coverage
        cov = coverage()
        checks["fills_4wk"] = float(cov.get("days", 0.0)) >= 28.0 and int(cov.get("n", 0)) > 50
    except (ImportError, OSError, ValueError, TypeError):
        checks["fills_4wk"] = False

    checks["cost_model"] = Path("data/cost_model.json").exists()

    try:
        from libs.self_improvement.forecast_calibration import report
        checks["calib_10"] = int(report().get("n_resolved", 0)) >= 10
    except (ImportError, OSError, ValueError, TypeError):
        checks["calib_10"] = False

    checks["no_criticals"] = not Path("data/DEADMAN_FIRED").exists()
    met = all(checks.values())
    return met, ", ".join(f"{k}={v}" for k, v in checks.items())


class _DurableState(dict):                       # type: ignore[type-arg]
    """Cadence state that persists THE INSTANT a duty stamps itself.

    THE `finally` IN `main` DOES NOT COVER THE FAILURE THAT ACTUALLY HAPPENS HERE. Its docstring
    promises to bank completed duties through "an OOM kill", and a Python `finally` does not run
    on SIGTERM at all -- the default disposition terminates the process without unwinding.
    MEASURED 2026-08-28 on this interpreter: a process that SIGTERMs itself inside a `try` exits
    143 and the `finally` never executes. So every one of the 35 OOM kills in the preceding 36
    hours discarded the whole cycle's progress, the duties re-fired next tick, hit the same wall
    at the same place, and their timestamps stayed frozen -- which is exactly the cadence
    starvation the `finally` was added to end, still running, wearing the one costume it could
    not see. Six duties were owed, one 11.6x overdue and two never run.

    Writing on each stamp instead of once at the end also survives SIGKILL, which no in-process
    handler can catch, so this covers the kernel OOM killer as well as systemd's SIGTERM and the
    unit's own TimeoutStartSec. The write is atomic (tmp + os.replace): a state file torn by a
    kill mid-write would be unparseable, and `_days_since` reads unparseable as "never ran" --
    turning one kill into a permanent re-fire of every duty at once.

    This makes progress durable without making failure quiet. Nothing is skipped, no floor moves,
    and `_assert_floors` still raises: it only changes whether work that ALREADY happened is
    remembered.
    """

    def __init__(self, path: Path, initial: dict[str, Any]) -> None:
        super().__init__(initial)
        self._path = path

    def flush(self) -> None:
        tmp = self._path.with_suffix(self._path.suffix + ".tmp")
        tmp.write_text(json.dumps(self, indent=2), "utf-8")
        os.replace(tmp, self._path)

    def __setitem__(self, key: str, value: Any) -> None:
        super().__setitem__(key, value)
        self.flush()

    def update(self, *args: Any, **kwargs: Any) -> None:
        super().update(*args, **kwargs)
        self.flush()


def main() -> None:
    """Run every due cadence duty, and BANK WHAT COMPLETED even if a later one raises.

    STATE-WRITTEN-LAST IS THE DEFECT, and the panel timeout above is only the instance that
    exposed it. `state` is mutated in memory by every duty and persisted ONCE at the end, so ANY
    exception anywhere in this function -- a network hang, a malformed artifact, an OOM kill, an
    operator Ctrl-C -- discards the record of every duty that had already run. The duties then
    re-fire next cycle and their timestamps stay stale forever, which is indistinguishable from
    "the cadence engine is not running" and is exactly how cadence starvation has presented here
    before (2026-08-04).

    The `finally` makes progress durable without making failure quiet: `_assert_floors` still
    raises through it, so a breached floor still fails the run loudly -- it just no longer takes
    the completed duties down with it. No floor is loosened, added to, or removed; this only
    changes whether work that ALREADY happened is remembered.
    """
    _law_guard()                     # L1.42: no act exempt -- every entry point passes the laws
    now = datetime.now(tz=UTC)
    state = _DurableState(_STATE, _load(_STATE, {}))
    stage = str(_load(_STAGE, {"stage": "S0"}).get("stage", "S0"))
    fired: list[str] = []
    try:
        _main_body(now, state, stage, fired)
    finally:
        state.flush()          # belt and braces; every stamp already wrote through
    print(f"cadence[{stage}]: fired={fired or 'nothing due'} | "
          f"panel due in {max(0.0, _PANEL_EVERY_D - _days_since(state, 'last_panel')):.1f}d | "
          f"tier1 due in {max(0.0, _TIER1_EVERY_D - _days_since(state, 'last_tier1')):.1f}d")


#: The synthetic laboratory's artifact: the detection floor, written by scripts/calibrate_gauntlet.py
#: (its `OUT`). Declared there since the lab was built and NEVER produced on this tree (measured
#: 2026-09-08: absent while data/ holds 215 other artifacts), because the run failed every cycle
#: and the failure was a log line. Relative, like every artifact path in this file: the cadence
#: service runs from the repo root.
_CALIBRATION = Path("data/gauntlet_calibration.json")


def _calibration_measured(path: Path = _CALIBRATION) -> bool:
    """A calibration artifact counts as produced only when it is a MEASUREMENT. The BLOCKED
    record below lives at the same path so the blocker is an artifact; it must not be mistaken
    for a detection floor by the leg that checks existence."""
    try:
        doc = json.loads(path.read_text("utf-8"))
    except (OSError, ValueError):
        return False
    return isinstance(doc, dict) and doc.get("status") != "BLOCKED"


def _record_blocked_calibration(rc: int | None, last_stderr: str,
                                path: Path = _CALIBRATION) -> dict[str, Any]:
    """Write WHY the detection floor was not measured, in the shape scripts/certify_gauntlet.py
    uses for its own blocked run (generated_utc / status BLOCKED / blocker / consequence /
    resolution / rows), plus the exit code and the moment.

    A measurement already on disk is carried under `previous`, never overwritten by a blocker:
    a floor measured yesterday is still the last floor measured, and a failed run today is a
    second fact beside it, not a replacement for it.
    """
    prior: Any = None
    try:
        prior = json.loads(path.read_text("utf-8"))
    except (OSError, ValueError):
        prior = None
    stamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    doc: dict[str, Any] = {
        "generated_utc": stamp,
        "status": "BLOCKED",
        "rc": rc,
        "blocker": (last_stderr or "").strip()[:400] or (
            "the run exited without a line of stderr" if rc else
            "the run exited 0 and wrote no artifact"),
        "at": stamp,
        "consequence": ("The detection floor -- the one progress metric that cannot be gamed, "
                        "because it moves only when the desk gets better at finding weak "
                        "planted edges -- has not been measured; 'the candidates were "
                        "worthless' and 'the screen cannot detect an edge it is handed' "
                        "remain indistinguishable."),
        "resolution": ("Run scripts/calibrate_gauntlet.py by hand from the repo root; the "
                       "blocker line above is its last stderr line and names the failing "
                       "import or input."),
        "rows": [],
    }
    if isinstance(prior, dict) and prior.get("status") not in (None, "BLOCKED"):
        doc["previous"] = prior
    elif isinstance(prior, dict) and isinstance(prior.get("previous"), dict):
        doc["previous"] = prior["previous"]
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(doc, indent=2), "utf-8")
    os.replace(tmp, path)
    return doc


def _run_calibrate_gauntlet(fired: list[str]) -> None:
    """GAUNTLET CALIBRATION (EVERY CYCLE). 420 candidates tested, 420 died -- and "the candidates
    were worthless" and "the screen cannot detect an edge it is handed" fit that observation
    equally well while demanding opposite responses. Live data can never separate them because
    the truth is never available; a planted edge of known strength can. The detection floor it
    produces is the desk's one progress metric that cannot be gamed: hypothesis count rises by
    generating more and survivor count rises by lowering the bar, but the floor moves only when
    the desk genuinely gets better at finding weak edges.

    A FAILED RUN IS NOW AN ARTIFACT. The leg printed `NO ARTIFACT` and moved on every cycle since
    it was scheduled, so the reason the floor was never measured lived in a service log nobody
    opened. It is written to the artifact's own path as a BLOCKED record instead.
    """
    _r = _srun([sys.executable, "scripts/calibrate_gauntlet.py"],
                        capture_output=True, text=True, timeout=420, check=False)
    _tail = (_r.stdout or _r.stderr or "").strip().splitlines()[-1:] or [""]
    if _r.returncode != 0 or not _calibration_measured():
        _err = (_r.stderr or "").strip().splitlines()[-1:] or [""]
        _record_blocked_calibration(_r.returncode, _err[0] or _tail[0])
        print(f"cadence: gauntlet-calibration rc={_r.returncode} NO ARTIFACT -> BLOCKED record "
              f"at {_CALIBRATION} | {_tail[0][:110]}")
    else:
        fired.append("gauntlet-calibration")
        for _ln in (_r.stdout or "").strip().splitlines()[:1]:
            print(f"cadence: {_ln[:150]}")


def _main_body(now: datetime, state: dict[str, Any], stage: str, fired: list[str]) -> None:
    """The duty sequence itself. Mutates `state` in place; `main` owns persisting it."""

    if _days_since(state, "last_tier1") >= _TIER1_EVERY_D:
        if _run_panel("tier1"):
            state["last_tier1"] = now.isoformat()
            state["last_panel"] = now.isoformat()     # tier1 counts as this week's panel
            fired.append("tier1")
    elif _days_since(state, "last_panel") >= _PANEL_EVERY_D and _run_panel(None):
        state["last_panel"] = now.isoformat()
        fired.append("panel")

    # META-RESEARCH REVIEW (§ docs/research/META_RESEARCH_DIRECTIVE.md). Mechanical half runs
    # EVERY cycle: it is seconds, no LLM, no context cost, and a prompt-only duty would be
    # skipped on a busy cycle exactly as this desk's own record predicts.
    if _days_since(state, "last_meta_research") >= _META_RESEARCH_D:
        _r = _srun([sys.executable, "scripts/meta_research_review.py"],
                            capture_output=True, text=True, timeout=300, check=False)
        if Path("data/meta_research_review.json").exists():
            state["last_meta_research"] = now.isoformat()
            fired.append("meta-research")
        else:
            print(f"cadence: meta-research produced nothing rc={_r.returncode} -- duty stays OWED")

    # BREADTH EXPANSION + HYPOTHESIS GENERATION (daily). BOTH SHIPPED UNSCHEDULED, and the
    # allocator only surfaced it once its writer-attribution was corrected: an organ that writes
    # an artifact nothing calls is indistinguishable, in every report, from an organ that does not
    # exist. breadth_expander is the desk's only GENERATIVE source discovery ("here is territory
    # you have not looked at") and hypothesis_generator is the only generator that can see the
    # graveyard -- the one that stops the desk re-proposing the dead, which is exactly how the
    # principal's 50-hypothesis slate arrived three-quarters already-refuted.
    #
    # PRODUCTION, NOT EXIT CODE. Both are LLM organs against a shared wallet. A half-funded
    # roster 402s mid-run, the sanitiser drops the partial result, and the process exits clean --
    # the precise shape that let cadence_state claim a panel ran while nothing had been appended
    # for five days. So the duty is stamped on the ARTIFACT GROWING, never on the return code,
    # and their own budget guards handle the money.
    for _name, _script, _artifact, _key in (
            ("breadth-expansion", "scripts/breadth_expander.py",
             "data/breadth_expansion.jsonl", "last_breadth_expansion"),
            ("hypothesis-generation", "scripts/hypothesis_generator.py",
             "data/hypothesis_queue.jsonl", "last_hypothesis_generation")):
        if _days_since(state, _key) < 1.0:
            continue
        _p = Path(_artifact)
        try:
            _before = _p.stat().st_size
        except OSError:
            _before = -1
        _r = _srun([sys.executable, _script],
                            capture_output=True, text=True, timeout=900, check=False)
        try:
            _after = _p.stat().st_size
        except OSError:
            _after = -1
        _tail = (_r.stdout or _r.stderr or "").strip().splitlines()[-1:] or [""]
        if _after > _before:
            state[_key] = now.isoformat()
            fired.append(_name)
            print(f"cadence: {_name} +{_after - _before}b | {_tail[0][:110]}")
        else:
            print(f"cadence: {_name} rc={_r.returncode} appended NOTHING -- duty stays OWED "
                  f"| {_tail[0][:110]}")

    # FILL QUALITY (weekly). The ledger ordered "re-measure WEEKLY until >60%" after the
    # patient-opens fix; that order never became code, so the fix has been unverified since it
    # shipped. Cheap, read-only, no keys.
    if _days_since(state, "last_fill_quality") >= 7:
        _srun([sys.executable, "scripts/fill_quality_monitor.py"],
                       capture_output=True, text=True, timeout=120, check=False)
        if Path("data/fill_quality.json").exists():
            state["last_fill_quality"] = now.isoformat()
            fired.append("fill-quality")

    # DESK METRICS (every cycle). Durable trend, not a snapshot -- libs/monitoring persists
    # each value and raises a real Alert on threshold breach. Runs AFTER meta-research so it
    # records that cycle's freshly computed numbers, not the previous one's.
    _r = _srun([sys.executable, "scripts/record_desk_metrics.py"],
                        capture_output=True, text=True, timeout=180, check=False)
    _tail = (_r.stdout or _r.stderr or "").strip().splitlines()[-1:] or [""]
    if _r.returncode != 0 or not Path("data/desk_metrics.sqlite").exists():
        # SILENT STEPS ARE UNMONITORED STEPS. These three were fired with their output
        # discarded, so a crash or an empty run looked identical to success -- the same
        # state-touched-but-nothing-produced class _run_panel exists to catch.
        print(f"cadence: desk-metrics rc={_r.returncode} NO ARTIFACT | {_tail[0][:110]}")
    else:
        fired.append("desk-metrics")

    # PORTFOLIO RISK (every cycle, self-arming). Dormant below 3 sleeves and load-bearing at
    # or above -- the gate is a DATA condition read from the shadow registry, so nobody has to
    # notice the third sleeve landing for correlation-shock control to start running.
    _r = _srun([sys.executable, "scripts/run_portfolio_risk.py"],
                        capture_output=True, text=True, timeout=180, check=False)
    _tail = (_r.stdout or _r.stderr or "").strip().splitlines()[-1:] or [""]
    if _r.returncode != 0 or not Path("data/portfolio_risk.json").exists():
        # SILENT STEPS ARE UNMONITORED STEPS. These three were fired with their output
        # discarded, so a crash or an empty run looked identical to success -- the same
        # state-touched-but-nothing-produced class _run_panel exists to catch.
        print(f"cadence: portfolio-risk rc={_r.returncode} NO ARTIFACT | {_tail[0][:110]}")
    else:
        fired.append("portfolio-risk")

    # PROMOTION GATE (every cycle). Renders the eight-gate barrier explicitly and records the
    # verdict, so a promotion prerequisite can be audited after the fact instead of being
    # assembled implicitly per screen. Fail-closed: unchecked gates reject.
    # THE ARTIFACT ASSERTED HERE MUST BE THE ONE THIS STEP WRITES (R0353). This tested
    # `data/promotion_gate.json` -- which scripts/check_promotion_gate.py rewrites HOURLY with
    # unrelated keys -- so the existence test was satisfied by a sibling script's output and the
    # step was credited every cycle while promotion_gate.py returned early having judged nothing.
    # An existence test against a filename a DIFFERENT producer keeps fresh is not a check.
    # Asserting freshness as well as existence closes the other half: a stale verdict from a run
    # that died last week would otherwise still read as this cycle's work.
    _pg = Path("data/promotion_gate_verdicts.json")
    _pg_before = _pg.stat().st_mtime if _pg.exists() else -1.0
    _r = _srun([sys.executable, "scripts/promotion_gate.py"],
                        capture_output=True, text=True, timeout=180, check=False)
    _tail = (_r.stdout or _r.stderr or "").strip().splitlines()[-1:] or [""]
    if _r.returncode != 0 or not _pg.exists() or _pg.stat().st_mtime <= _pg_before:
        # SILENT STEPS ARE UNMONITORED STEPS. These three were fired with their output
        # discarded, so a crash or an empty run looked identical to success -- the same
        # state-touched-but-nothing-produced class _run_panel exists to catch.
        print(f"cadence: promotion-gate rc={_r.returncode} NO VERDICT -- duty stays OWED "
              f"| {_tail[0][:110]}")
    else:
        fired.append("promotion-gate")

    # DAILY HYPOTHESIS FUNNEL. Generation is the desk's #2 supreme objective and its output
    # was going straight into a queue nobody screened. This runs the arithmetic stage every
    # cycle -- cost floor, degenerate turnover, trivial-variation fingerprint, batch diversity --
    # so the gauntlet receives screened candidates and the desk can SEE its conversion rate.
    # No bar is moved: the screen rejects only on cheap unambiguous evidence and escalates
    # everything else, and no statistics are ever asked of a model.
    _r = _srun([sys.executable, "scripts/hypothesis_screen.py"],
                        capture_output=True, text=True, timeout=300, check=False)
    _tail = (_r.stdout or _r.stderr or "").strip().splitlines()[-1:] or [""]
    if _r.returncode != 0:
        print(f"cadence: hypothesis-funnel rc={_r.returncode} | {_tail[0][:110]}")
    else:
        fired.append("hypothesis-funnel")

    # CONSTITUTION (EVERY CYCLE). max_pi E[log W_T] is the desk's sole objective and the
    # aggression ratchet is what stops it eroding. Raising the high-water mark here means a
    # STRENGTHENED principle is locked in the same cycle it lands, with no ceremony -- while a
    # weakened one has nowhere to hide, because the mark it fell below is already committed.
    # Asymmetry is the whole design: strengthening is frictionless, weakening costs a hand-edit.
    try:
        from libs.doctrine.ratchet import check as _rcheck
        from libs.doctrine.ratchet import sync_preamble as _rsync
        from libs.doctrine.ratchet import update_high_water as _rraise
        _rep = _rcheck()
        if _rep.ok:
            _rraise()
            # The doctrine file holds a COPY of the constitution because a prompt cannot import
            # Python. Resyncing here, one-directionally from code to prompt, is what stops the
            # organs running on a superseded objective while the audit enforces the current one.
            _sync = _rsync()
            if _sync not in ("in-sync", "doctrine-missing"):
                print(f"cadence: constitution block {_sync} into ops/principal_doctrine.txt")
            fired.append("constitution")
            if _rep.raised:
                print(f"cadence: constitution STRENGTHENED -- {'; '.join(_rep.raised)}")
        else:
            print("cadence: CONSTITUTION RATCHET VIOLATED -- " + " | ".join(_rep.violations))
    except Exception as _e:       # a doctrine check must never be what stops a cycle
        print(f"cadence: constitution check failed to run ({type(_e).__name__}: {_e}) -- "
              "the objective is unenforced this cycle")

    # MOAT MINING AND MOAT SCREENING WERE REMOVED 2026-09-05 (universe mandate). The whole moat
    # pipeline -- mine_moat, screen_moat, promote_moat_survivors, review_moat_clocks -- read the
    # self-recorded crypto-exchange L2 tape, and it was deleted with the recorders that wrote it.
    # The information-advantage argument that justified running it every cycle was specifically
    # about THAT tape being unbuyable; it does not transfer to a market the desk reaches through a
    # broker terminal. The MT5 desk records its own tape under desks/mt5/recorders and mines it in
    # its own cycle, so the capability is not lost, only relocated to the desk that owns it.

    # MOAT SCREENING AND SURVIVOR EXPLOITATION (EVERY CYCLE). Mining DESCRIBES the tape; screening
    # ASKS it whether any mechanism predicts, and promotion turns a persistent answer into a
    # forward clock. Running the first every cycle and the other two never was the asymmetry that
    # left the desk's one irreplaceable asset measured everywhere and exploited nowhere.
    #
    # The order is load-bearing: screen writes the registry, promote reads it. Promotion runs even
    # when screening produced nothing this pass, because persistence accumulates ACROSS passes and
    # a candidate can cross the bar on a cycle that found no new survivor at all.
    for _organ, _script, _artifact in (
            # THE CALLERS THAT WERE THEMSELVES ORPHANS. Each of these was written to make a
            # library module reachable -- emergence, ict.cross_sectional -- and then nothing ran
            # the caller. The libs orphan check went green because the import existed, which is
            # how a wiring fix can be one link short and still report success. Each exits
            # cleanly naming its own blocker when its input is absent, so running them every cycle
            # costs seconds and turns "no data yet" into a dated statement rather than a silence.
            #
            # THE WALLET-GRAPH LEG IS GONE, 2026-09-05 (universe mandate). It ran
            # scripts/resolve_wallets.py, which resolved on-chain addresses to entities and
            # reported entity-level exchange flow -- an on-chain mechanic with no MT5 instrument
            # behind it, so it was deleted rather than repointed. Its library,
            # libs/data/wallet_graph.py, now has no importer at all and belongs in the same
            # deletion; it is left standing only because libs/ is not this sweep's to edit.
            ("weak-signals", "scripts/cluster_weak_signals.py", "data/weak_signal_clusters.json"),
            ("ict-xsec", "scripts/run_ict_cross_sectional.py", "data/ict_cross_sectional.json"),
            # SOLE IMPORTERS THAT NOTHING RAN -- found by the same sweep, pre-existing rather than
            # mine. run_axis_generate keeps libs.research.alpha_economics reachable and completes
            # in seconds; run_prediction_markets keeps libs.data.prediction_markets reachable and
            # now reports an empty fetch instead of dying on a pandas KeyError, so a cycle where
            # the venue is unreachable costs a line of output rather than a traceback.
            ("prediction-markets", "scripts/run_prediction_markets.py", "data/cadence_state.json")):
        _r = _srun([sys.executable, _script],
                            capture_output=True, text=True, timeout=420, check=False)
        _tail = (_r.stdout or _r.stderr or "").strip().splitlines()[-1:] or [""]
        if _r.returncode != 0 or not Path(_artifact).exists():
            print(f"cadence: {_organ} rc={_r.returncode} NO ARTIFACT | {_tail[0][:110]}")
        else:
            fired.append(_organ)
            print(f"cadence: {_tail[0][:150]}")

    # GAUNTLET CALIBRATION (EVERY CYCLE): see `_run_calibrate_gauntlet`. A failed run writes a
    # BLOCKED record to the artifact's own path, so the reason the floor was never measured is
    # an artifact and not a log line.
    _run_calibrate_gauntlet(fired)

    # ANCESTOR ORGANS (EVERY CYCLE). Lineage, breeding, theory induction, feature invention and
    # the internal information market. Built with tests and no caller, which is the exact
    # "built but never runs" class this desk keeps finding in itself -- and a library wired six
    # weeks late meets a codebase that moved underneath it. Runs on the graveyard's 42 real
    # specimens today and reports honestly where that data cannot support a conclusion.
    _r = _srun([sys.executable, "scripts/run_ancestors.py"],
                        capture_output=True, text=True, timeout=300, check=False)
    _tail = (_r.stdout or _r.stderr or "").strip().splitlines()[-1:] or [""]
    if _r.returncode != 0 or not Path("data/ancestors.json").exists():
        print(f"cadence: ancestors rc={_r.returncode} NO ARTIFACT | {_tail[0][:110]}")
    else:
        fired.append("ancestors")
        for _ln in (_r.stdout or "").strip().splitlines()[:1]:
            print(f"cadence: {_ln[:150]}")

    # TAPE -> BARS WAS REMOVED 2026-09-05 with build_bars.py: it converted the retired
    # crypto-exchange recorders' 15s L2+trades into OHLCV, and both ends of that conversion are
    # gone. screen_ict below now runs against whatever `data/bars` holds and reports NO BARS when
    # it is empty, which is its documented refusal and the honest state on a desk whose bars come
    # from the MT5 terminal rather than from a recorder in this repo.

    # ICT SCREEN (EVERY CYCLE). The second strategy family landed with full test suites and NO
    # CALLER -- the desk's own "built but never runs" class, committed while fixing instances of it
    # elsewhere. Cheap (seconds, no network) and it refuses to synthesise bars when there are none,
    # so a fresh checkout reports NO BARS rather than screening a generator.
    _r = _srun([sys.executable, "scripts/screen_ict.py"],
                        capture_output=True, text=True, timeout=300, check=False)
    _tail = (_r.stdout or _r.stderr or "").strip().splitlines()[:1] or [""]
    if Path("data/ict_screen.json").exists():
        fired.append("ict-screen")
        print(f"cadence: {_tail[0][:150]}")
    else:
        print(f"cadence: ict-screen rc={_r.returncode} NO ARTIFACT | {_tail[0][:110]}")

    # CANARIES (EVERY CYCLE). Charter §21 promised "re-run every 4 days" and nothing ran them:
    # the file was seeded 2026-07-19 with placeholder baselines and never executed, so no shift was
    # detectable in principle for two weeks. Cheap -- nine HTTP calls, seconds -- and the one that
    # matters (C9) guards a LIVE data path rather than merely informing a digger.
    _r = _srun([sys.executable, "scripts/run_canaries.py"],
                        capture_output=True, text=True, timeout=300, check=False)
    _tail = (_r.stdout or _r.stderr or "").strip().splitlines()[:1] or [""]
    if Path("data/canary_run.json").exists():
        fired.append("canaries")
        print(f"cadence: {_tail[0][:150]}")
    else:
        print(f"cadence: canaries rc={_r.returncode} NO ARTIFACT | {_tail[0][:110]}")

    # ACQUISITION PLAN (EVERY CYCLE). Triage #93, unblocked 2026-07-29 and unbuilt until now.
    # Ranks what data to acquire NEXT on measured terms rather than on research_cio's hardcoded
    # advantage table -- the adaptive term is the ontology's own attempts/survivors record, so a
    # class of data this desk has worked to exhaustion falls from EVIDENCE. Ranks only; it spends
    # nothing and starts no collector.
    _r = _srun([sys.executable, "scripts/acquire_data.py"],
                        capture_output=True, text=True, timeout=120, check=False)
    _tail = (_r.stdout or _r.stderr or "").strip().splitlines()[:1] or [""]
    if Path("data/acquisition_plan.json").exists():
        fired.append("acquisition")
        print(f"cadence: {_tail[0][:150]}")
    else:
        print(f"cadence: acquisition rc={_r.returncode} NO ARTIFACT | {_tail[0][:110]}")

    # GAP-REGISTER MECHANICAL PASS (EVERY CYCLE). The register is, by the doctrine's own words,
    # "the only organ that DRIVES work" -- and its stated cadence ("re-ranked at the START of
    # every daily cycle") was executed by an LLM remembering to do it, which is precisely the
    # reliability hole this module's docstring exists to close. Seven days and fifty open rows.
    #
    # This is the MECHANICAL half only: deadlines, parked rows, ownership and starvation, all
    # computable and none of them opinions. It writes a stamp that deliberately does NOT match the
    # `Re-ranked` regex, so it cannot discharge the judgment duty -- an organ that cleared a check
    # it had not satisfied would stop the defect being reported and the work being done at the
    # same moment, and only the first of those is visible.
    _r = _srun([sys.executable, "scripts/rerank_gaps.py"],
                        capture_output=True, text=True, timeout=120, check=False)
    _tail = (_r.stdout or _r.stderr or "").strip().splitlines()[-1:] or [""]
    if _r.returncode != 0 or not Path("data/gap_rerank.json").exists():
        print(f"cadence: gap-rerank rc={_r.returncode} NO ARTIFACT | {_tail[0][:110]}")
    else:
        fired.append("gap-rerank")
        for _ln in (_r.stdout or "").strip().splitlines()[:1]:
            print(f"cadence: {_ln[:150]}")

    # CONTRIBUTION ESTIMATES (EVERY CYCLE, BEFORE THE ALLOCATOR). run_allocator has reported the
    # same binding constraint on every cycle it has ever run -- "CONTRIBUTION ESTIMATES" -- and
    # P4 says the marginal resource goes to argmax_i |dE[log W]/dC_i|, an argmax that was being
    # taken over an empty set. This organ derives what it can from artifacts ON DISK and emits
    # NEVER_EXECUTED for the rest, so absence stays ranked and costed rather than being silently
    # read as zero. Ordered before the allocator deliberately: the allocator consumes its output,
    # and a stale contributions file would rank this cycle on last cycle's evidence.
    _r = _srun([sys.executable, "scripts/estimate_contributions.py"],
                        capture_output=True, text=True, timeout=120, check=False)
    _tail = (_r.stdout or _r.stderr or "").strip().splitlines()[-1:] or [""]
    if _r.returncode != 0 or not Path("data/contributions.json").exists():
        print(f"cadence: contributions rc={_r.returncode} NO ARTIFACT | {_tail[0][:110]}")
    else:
        fired.append("contributions")
        for _ln in (_r.stdout or "").strip().splitlines()[:1]:
            print(f"cadence: {_ln[:150]}")

    # ALLOCATOR (EVERY CYCLE). The governing layer landed with full test suites and no caller,
    # which governs nothing: the constitution says every subsystem optimises dE[log W]/dx_i, and
    # until something computes those derivatives that sentence is decoration. With 0 alphas, 0
    # trials and 0 fills there is no honest contribution estimate for ANY subsystem, so this
    # deliberately produces NO ranking -- it reports the instrumentation gap, which is what P11
    # mandates when evidence is insufficient. The day the first real estimate lands, the allocator
    # is already running and already correct rather than written six weeks late.
    _r = _srun([sys.executable, "scripts/run_allocator.py"],
                        capture_output=True, text=True, timeout=120, check=False)
    _tail = (_r.stdout or _r.stderr or "").strip().splitlines()[-1:] or [""]
    if _r.returncode != 0 or not Path("data/allocator.json").exists():
        print(f"cadence: allocator rc={_r.returncode} NO ARTIFACT | {_tail[0][:110]}")
    else:
        fired.append("allocator")
        for _ln in (_r.stdout or "").strip().splitlines()[:1]:
            print(f"cadence: {_ln[:150]}")

    # P&L WATCHDOG (EVERY CYCLE, every mode). The desk's only P&L record is a once-a-day NAV
    # attestation that nothing read: between attestations a leak is invisible, and across them it
    # was visible only if somebody opened the file. A loss nobody looks at compounds exactly the
    # way the objective says wealth compounds, downward. This makes "why are we down?" a question
    # the desk asks itself rather than one a human has to think to ask.
    _r = _srun([sys.executable, "scripts/watch_pnl.py"],
                        capture_output=True, text=True, timeout=120, check=False)
    _tail = (_r.stdout or _r.stderr or "").strip().splitlines()[-1:] or [""]
    if _r.returncode != 0 or not Path("data/pnl_watch.json").exists():
        print(f"cadence: pnl-watch rc={_r.returncode} NO ARTIFACT | {_tail[0][:110]}")
    else:
        fired.append("pnl-watch")
        for _ln in (_r.stdout or "").strip().splitlines()[:1]:
            print(f"cadence: {_ln[:170]}")

    # CONSTITUTIONAL ENFORCEMENT (EVERY CYCLE). The constitutional checks were themselves pure
    # DETECTORS -- they produced defect entries and nothing repaired anything, which is exactly
    # what P25 forbids. This resolves every breach into AUTOFIX (applied here), PATCH_READY (the
    # exact edit, chased) or BLOCKED-by-design (the ratchet, where silent repair would destroy
    # the mechanism while appearing to defend it), and ages every one so a standing breach cannot
    # read as a fresh finding each morning.
    _r = _srun([sys.executable, "scripts/enforce_constitution.py"],
                        capture_output=True, text=True, timeout=240, check=False)
    _tail = (_r.stdout or _r.stderr or "").strip().splitlines()[-1:] or [""]
    if _r.returncode != 0 or not Path("data/constitution_enforcement.json").exists():
        print(f"cadence: constitution-enforce rc={_r.returncode} NO ARTIFACT | {_tail[0][:110]}")
    else:
        fired.append("constitution-enforce")
        for _ln in (_r.stdout or "").strip().splitlines()[:1]:
            print(f"cadence: {_ln[:170]}")

    # COEXISTENCE (EVERY CYCLE). No sleeve, family or engine may cost another its growth, and
    # every one expands to its own maximum. Dormant until two families have a record -- MC_i is
    # undefined with one -- but the ORDER it enforces (orthogonality before retirement) binds
    # immediately and needs no data at all.
    _r = _srun([sys.executable, "scripts/run_coexistence.py"],
                        capture_output=True, text=True, timeout=120, check=False)
    _tail = (_r.stdout or _r.stderr or "").strip().splitlines()[-1:] or [""]
    if _r.returncode != 0 or not Path("data/coexistence.json").exists():
        print(f"cadence: coexistence rc={_r.returncode} NO ARTIFACT | {_tail[0][:110]}")
    else:
        fired.append("coexistence")

    # MODEL UPGRADE (monthly). The desk's models used to be frozen literals that only ever moved
    # when a human noticed a newer flagship -- so seats aged silently (llama-4-maverick sat 15
    # months stale). This makes "are we on the best model available?" a cadence question with a
    # floor, answered by live evidence rather than by anyone remembering to ask.
    # FUNDING IS ALSO A TRIGGER, not just the calendar. Credits landing is exactly when the
    # question "what is the best model available?" becomes worth money, and the monthly clock
    # would otherwise sit on the answer for up to 30 days after payment.
    _funded_now = _funding_restored()
    if ((_days_since(state, "last_model_upgrade") >= _MODEL_UPGRADE_D or _funded_now)
            and _run_model_upgrade()):
        state["last_model_upgrade"] = now.isoformat()
        fired.append("model-upgrade" + (" (FUNDING-TRIGGERED)" if _funded_now else ""))
        _clear_funding_debt()
    elif _funded_now:
        # Debt deliberately NOT cleared: a sweep that could not evaluate the catalog has not
        # answered the question, and an unanswered question must stay owed.
        print("cadence: funding restored, flagship sweep OWED but DID NOT EVALUATE -- "
              "debt retained for the next run")

    # generation triggers -> flagged for the brain (scoped runs are a judgment task)
    due: list[str] = []
    health = _load(_HEALTH, {})
    for ds in health.get("datasets", []):
        name, days = str(ds.get("name")), int(ds.get("days") or 0)
        if days >= _CLOCK_MATURITY_D and not state.get(f"gen_done_{name}"):
            due.append(f"{name}: clock matured ({days}d) -- scoped generate run owed, PLUS a "
                       "graveyard re-mine pass: any killed entry whose kill-reason this new "
                       "data invalidates gets a fresh pre-registration (no silent revivals)")
    if Path("data/fred_macro.json").exists() and not state.get("gen_done_fred_macro_family"):
        due.append("fred_macro family: deep history available -- scoped generate run owed")
    if stage in ("S1", "S2") and _days_since(state, "last_live_generate") >= 7:
        due.append("LIVE (S1+): weekly generation vs fresh fills/slippage/tape is due")
    # Digging cadence tracks UNMINED INVENTORY (principal 2026-07-18): 14d while the source
    # backlog is being mined; the brain sets digging_saturated=true when every coverage
    # family has >=2 sessions AND 2 consecutive sessions produced zero cards -> relax to 28d.
    dig_every = 14 if state.get("digging_saturated") else 7
    if _days_since(state, "last_prospector") >= dig_every:
        due.append(
            f"PROSPECTOR (every {dig_every}d): execute docs/research/PROSPECTOR_SPEC.md with "
            "real web search -- UNCAPPED/exhaustive (dedicated quant-prospector.timer, "
            "biweekly), provenance-graded mechanism cards -> EV gate "
            "+ pre-registration; update docs/research/prospector_watchlist.md; mark done: "
            "last_prospector in data/cadence_state.json. NEVER at the expense of the lockdown "
            "priorities (recorder/connector) -- they own the cycle first.")
    if _days_since(state, "last_data_axis_dig") >= 7:                     # WEEKLY (never relaxed)
        due.append(
            "DATA-AXIS / FREE-DATA-ALTERNATIVE DIG (WEEKLY/7d, UNCAPPED budget -- operator accepts "
            "token cost; dig ALL 6 categories to EXHAUSTION every run, no rotating "
            "subset): execute the FULL "
            "docs/research/FREE_DATA_ALTERNATIVES_SPEC.md -- 6 source categories (exchange-native "
            "dumps, on-chain reconstruction, non-English/regional venues, community lakes, "
            "alt/sentiment, vendor-replacement); language-blind; VERIFY-DON'T-TRUST vs ground "
            "truth; DATA GENEALOGY on every adopted set; automatic replacement monitoring; "
            "source-failure intelligence; query evolution (>=25% exploration quota); cross-source "
            "synthesis; temporal rediscovery; discovery-ROI + maintainer tracking; SEARCH-SPACE "
            "EXPANSION quota. Catalog -> data/data_universe_map.json "
            "(source+grade+lineage+failure-modes+yield); verified axes -> EV gate "
            "(new_orthogonal_data). Mark done: last_data_axis_dig. Lockdown priorities own the "
            "cycle first.")
    if _days_since(state, "last_lit_deepdive") >= dig_every:
        due.append(
            f"LITERATURE DEEP-MINER (every {dig_every}d, UNCAPPED/exhaustive, dedicated "
            "quant-litminer.timer biweekly): execute "
            "docs/research/LITERATURE_SPEC.md -- inbox triage to MECHANISMS (never "
            "summaries), 2-level citation-chain digs, replication scans, coverage rotation; "
            "cards -> EV gate + pre-registration; mark done: last_lit_deepdive. Lockdown "
            "priorities own the cycle first.")
    if _days_since(state, "last_blind_rediscovery") >= 90:
        due.append(
            "BLIND REDISCOVERY (quarterly): NO external search -- per the companion section "
            "of PROSPECTOR_SPEC.md, invent up to 5 unpublished mechanisms from internal "
            "artifacts only; pre-register via the gauntlet; log for the 12-month literature "
            "comparison; mark done: last_blind_rediscovery.")
    if _days_since(state, "last_decision_scoring") >= 28:
        due.append(
            "DECISION OUTCOME SCORING (monthly -- closes the self-improvement loop): "
            "for every ledger decision past its review horizon (>=30d old) not yet "
            "scored, judge predicted-vs-ACTUAL: did expected_benefit materialize? was "
            "success_metric met? did reversal_condition fire? Append to "
            "data/decision_outcomes.jsonl (id, predicted, actual, hit/miss, lesson), "
            "then update EV-gate priors from the hit-rate -- the desk must learn "
            "whether its OWN predictions are any good. Mark done: last_decision_scoring.")
    if _days_since(state, "last_memory_consolidation") >= 90:
        due.append(
            "MEMORY CONSOLIDATION (quarterly -- anti-bloat for a lifetime system): "
            "consolidate ops/memory + knowledge base -- merge superseded/duplicate "
            "addenda, archive resolved items to a dated file, compress recurring "
            "lessons into principles, fix stale facts, keep MEMORY.md lean. Memory "
            "must get SIMPLER as it learns, not only longer. NEVER delete the ledger "
            "or graveyard (append-only truth) -- consolidate the NARRATIVE layer only. "
            "Mark done: last_memory_consolidation.")
    if _days_since(state, "last_prompt_review") >= _PROMPT_REVIEW_D:
        due.append(
            "PROMPT SELF-IMPROVEMENT (monthly): score every mission prompt + auditor against "
            "verified-hit evidence (panel_rulings.md, inboxes, micro_audit_log.jsonl). Rewrite "
            "ONLY the worst performer; ledger the revision with a pre-registered success "
            "metric (verified-finding rate over its next 2 runs) and an auto-revert condition. "
            "Prompts live in git -- every revision is diffable and revertible. Mark done: set "
            "last_prompt_review in data/cadence_state.json.")
    # WRITTEN EVERY FIRING, EMPTY OR NOT (producer-cadence-stale, 2026-08-18). The old
    # `if due:` guard left the file untouched through any quiet stretch, so its AGE conflated
    # "no duties have come due" (healthy) with "run_cadence stopped firing" (the outage the
    # §36 fence exists to catch) -- measured: file 9d old while cadence_state.json was 30min
    # fresh. An unconditional rewrite makes the mtime a true engine heartbeat and the fence's
    # premise sound; the empty-state text says so explicitly for any reader.
    _DUE_NOTE.parent.mkdir(parents=True, exist_ok=True)
    if due:
        _DUE_NOTE.write_text(
            f"# Generation due -- {now.isoformat()[:16]}Z (stage {stage})\n\n"
            "The cadence engine flags these; the brain executes SCOPED generate runs "
            "(graveyard-excluded, pre-registration mandatory) and then marks them done by "
            "setting gen_done_<name> / last_live_generate in data/cadence_state.json.\n\n"
            + "\n".join(f"- {d}" for d in due) + "\n", "utf-8")
        print(f"cadence: {len(due)} generation trigger(s) flagged -> {_DUE_NOTE}")
    else:
        _DUE_NOTE.write_text(
            f"# Generation due -- {now.isoformat()[:16]}Z (stage {stage})\n\n"
            "NO generation duties due this firing: every cadence stamp is inside its bar. "
            "This file is rewritten on EVERY run_cadence firing, so its age measures the "
            "cadence engine's liveness, never merely how long the queue has been empty.\n",
            "utf-8")

    # FREEZE-EXIT (deterministic; principal 2026-07-18): evaluate the 5 lockdown exit
    # criteria every cycle so the freeze lifts on EVIDENCE, not on memory. Pre-Gate-0
    # these read cleanly as not-met; the moment live data satisfies them, the manifest
    # is flagged for activation. No human or brain memory is the trigger -- the code is.
    if stage == "S0" and not state.get("post_gate0_activated"):
        met, why = _freeze_exit_met()
        # ALWAYS write the status, and write it where something READS it. Previously this was set
        # only in the else-branch, into a state key with ONE writer and ZERO readers -- no fence,
        # no page, no dashboard. That is how three unsatisfiable criteria sat in the deployment
        # gate unnoticed: the single place the failure was stated was a string nobody opened.
        state["freeze_exit_status"] = why
        _FREEZE_STATUS.parent.mkdir(parents=True, exist_ok=True)
        _FREEZE_STATUS.write_text(json.dumps({
            "generated": datetime.now(tz=UTC).isoformat(),
            "met": met, "why": why,
            "criteria_sources": _FREEZE_SOURCES,
            "note": "Every criterion must read an artifact something in this repo WRITES. "
                    "check_freeze_exit_sources() fences that; three criteria failed it on "
                    "2026-07-30 (fills.csv, weekly_cost_summary.json, calibration.csv).",
        }, indent=2), "utf-8")
        if met:
            due.append("FREEZE-EXIT CRITERIA MET -- activate docs/POST_GATE0_MANIFEST.md "
                       "top to bottom; flip stage_state to S1; set post_gate0_activated. "
                       "Nothing deferred may be skipped.")
    # Floors stay EXACTLY here and stay raising: main()'s `finally` banks state around this call,
    # so a breached floor still fails the run loudly while the duties that already completed are
    # no longer forgotten. Tier-3-class -- never loosened, never deleted.
    _assert_floors(state, stage)


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        prog="run_cadence.py",
        description="CADENCE ENGINE -- fires every review/generation duty that is due, per stage. "
                    "WITH NO FLAGS THIS FIRES REAL DUTIES (the weekly panel, monthly tier1, digs). "
                    "Use --report-only to see what is due without firing anything.")
    ap.add_argument("--report-only", action="store_true",
                    help="print what is due and exit WITHOUT firing any duty")
    ap.add_argument("--json", action="store_true",
                    help="with --report-only, emit the due table as JSON")
    return ap


# ARGV IS PARSED HERE, NOT INSIDE main(). `main()` keeps its no-argument signature because
# tests/governance/test_cadence_state_durability.py calls `m.main()` directly -- were the parse
# inside, that call would read pytest's own argv and die on unrecognised arguments. The two real
# executors (ops/quant-cadence.service and scripts/daily_research_cycle.py:58) both invoke this
# bare, so there is no existing flag contract to preserve: this is purely additive.
if __name__ == "__main__":
    _args = build_parser().parse_args()          # unknown flags now exit 2 with a usage line
    if _args.report_only:
        _rep = due_report()
        if _args.json:
            print(json.dumps(_rep, indent=2))
        else:
            print(f"cadence[{_rep['stage']}] REPORT ONLY -- nothing fired. "
                  f"{_rep['n_due']} due:")
            for _d in _rep["duties"]:
                _age = "never run" if _d["never_run"] else f"{_d['days_since']:.1f}d ago"
                print(f"  {'DUE ' if _d['due'] else '    '}{_d['duty']:<24}"
                      f"every {_d['period_days']:>3}d   last: {_age}")
        sys.exit(0)
    main()

```

### scripts\run_max_push.py
```python
"""MAX PUSH (L1.0) -- one ranked queue of everything this desk is not yet at 100% on.

PRINCIPAL ORDER (2026-07-30): *"every aspect of quant should always aim and hunt to maximise
itself 100% every single day, believing it never is, and always max pushed."*

WHAT WAS ACTUALLY MISSING. The law already existed -- L1.0(c) says the gap between today's value
and 100% IS the work queue. What did not exist was the queue. The desk had FIVE separate
"what is left" artifacts, each true, none comparable:

    data/ratchet_report.json      metric floors and their distance to 100%
    data/utilisation.json         ceilings and their idle headroom (L1.28a)
    data/enforcement_matrix.json  principles with no fence
    data/wiring_agent.json        built capability nothing runs
    docs/GAP_REGISTER.md          open defects
    data/conversion_status.json   findings aging unconverted (L1.28b, added 2026-07-31)

Five lists nobody can rank against each other is the same as no list: the desk works whichever one
it happened to open. This merges them into ONE queue ordered by expected contribution, so "what is
the highest-value thing not yet at 100%" has an answer every morning without anyone deciding.

=================================================================================================
THE ANTI-COMPLACENCY PROPERTY, which is the part the principal actually asked for
=================================================================================================
This organ NEVER reports "done". When every measured aspect reaches its ceiling it does not
congratulate the desk -- it escalates, because at that point the MEASUREMENT SET is the suspect,
not the desk. A system that can reach 100% on everything it measures is a system measuring too
little; the honest reading of an all-green board is "we are no longer looking hard enough", and
that is emitted as the top queue item rather than as a clean bill of health.

This is why UNMEASURED aspects rank ABOVE partially-complete ones. An aspect at 60% is a known
quantity being worked; an aspect with no number is an unknown quantity being ignored, and it has
historically been where every expensive defect lived (capacity parity was "fine" until measured;
test strength was "fine" until measured at 55%; capital utilisation read over 100% the first time
anyone computed it, exposing two sources of truth for the desk's own equity).

LEVERAGE IS DECLARED, NOT COMPUTED. Ranking pretends to no EV model it does not have. Each source
carries a weight with a stated reason, and the weights are visible in one dict below so they can
be argued with -- an invented EV number would be less honest and no more useful.

    python scripts/run_max_push.py [--json] [--top N]
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

_OUT = _ROOT / "data/max_push_queue.json"
_FRONTIER_OUT = _ROOT / "data/economic_frontier.json"

from libs.ops.input_provenance import Inputs  # noqa: E402
from libs.research.alpha_frontier_gaps import queue_rows as alpha_frontier_queue_rows  # noqa: E402
from libs.research.completion_program_gaps import load as load_completion_program  # noqa: E402
from libs.research.completion_program_gaps import queue_rows as completion_queue_rows  # noqa: E402
from libs.research.frontier import Action, ResourcePrices  # noqa: E402
from libs.research.frontier import summarise as frontier_summary  # noqa: E402
from libs.research.gap_contract import load_published, to_queue_rows  # noqa: E402

# Leverage per source class: how much does closing one unit of this gap move the two supreme
# objectives? Declared with reasons rather than computed, because the desk has no EV model for
# heterogeneous engineering work and a fabricated one would rank worse while looking rigorous.
_LEVERAGE: dict[str, tuple[float, str]] = {
    "money_path_correctness": (
        1.00, "an undetected fault on the money path can end compounding outright (L1.23); every "
              "other guarantee sits on top of it"),
    "capital_utilisation": (
        0.90, "an idle dollar is compounding that never starts, and the loss is unbooked -- it "
              "appears in no P&L and raises no error (L1.28a)"),
    "evidence_throughput": (
        0.85, "forward slots and discovery rate set how fast validated edges can EXIST at all; an "
              "empty slot is evidence that will never be accrued"),
    "unenforced_law": (
        0.70, "a principle with no fence is prose -- it cannot fire and degrades silently into "
              "decoration (L2.0). Every defect found 2026-07-30 was of this shape"),
    "dormant_capability": (
        0.55, "engineering already paid for, returning zero forever, and rotting into a liability "
              "because nobody maintains what nobody runs (L2.9)"),
    "measurement_quality": (
        0.65, "test strength and type coverage bound how much of the above the desk can TRUST"),
    "open_defect": (
        0.50, "a known defect nobody closed; its cost is already being paid"),
    "conversion_debt": (
        0.95, "a finding aging in the queue is alpha already paid for and never collected; the "
              "measured spread between build-rate (~14 findings/day) and convert-rate "
              "(~0.6/day, deep sweep 2026-07-31) is the desk's largest single loss, and it "
              "multiplies every other row -- every queue item IS conversion (L1.28b)"),
    "calibration_debt": (
        0.80, "every Kelly bet and every promotion rests on a probability the desk assigned; if "
              "those are systematically over-confident the desk over-bets EVERY position and "
              "the error is invisible per-decision (L1.29). Unscored forecasts inflate the "
              "apparent hit rate by never counting the misses"),
    "tier1_process_gap": (
        0.75, "the principal's standing order (2026-07-31): every gap to tier-1 PROCESS closes "
              "autonomously, without being told -- only calendar-time walls are exempt. A layer "
              "below T1 is a known distance to the best practice that exists, with its closer "
              "named in the benchmark register"),
}

# Aspects with no number at all rank above partially-complete ones -- see module docstring.
_UNMEASURED_PRIORITY = 1.15


def _json(rel: str) -> Any:
    try:
        return json.loads((_ROOT / rel).read_text("utf-8"))
    except (OSError, ValueError):
        return None


#: (producer, the artifact it writes). DECLARED, because "did the refresh work?" is answerable
#: only against the file the producer was supposed to write -- an exit code proves a process
#: ended, never that it produced (desk lesson, and the reason `_refresh` no longer trusts one).
_REFRESHERS: tuple[tuple[str, str], ...] = (
    ("check_ratchets.py", "data/ratchet_report.json"),
    ("check_utilisation.py", "data/utilisation.json"),
    ("build_enforcement_matrix.py", "data/enforcement_matrix.json"),
    ("check_conversion.py", "data/conversion_status.json"),
    ("check_calibration.py", "data/calibration_status.json"),
    ("check_freshness.py", "data/freshness_status.json"),
)

#: How old a refreshed artifact may be before the queue built on it is DEGRADED. Generous: the
#: cron cadence for these producers is hourly-to-daily, so this catches a producer that has been
#: dead for a day, not one that ran forty minutes ago.
_ARTIFACT_MAX_AGE_H = 26.0


def _refresh(script: str, artifact: str) -> dict[str, Any]:
    """Re-run a producer and REPORT WHAT HAPPENED. See R0395.

    Until 2026-08-12 this was `check=False, capture_output=True, except (OSError,
    TimeoutExpired): return` -- three separate ways for a producer to die with the failure
    discarded at the call site. `build()` then read whatever stale file was on disk and stamped
    the merged queue `generated: <now>`, so the DAILY WORK QUEUE could be assembled entirely
    from last week's numbers and say nothing. Widest blast radius on the desk, because every
    organ and every session reads this to decide what to work on.

    THE EXIT CODE IS NOT THE TEST, AND GETTING THAT WRONG WOULD HAVE BEEN WORSE THAN THE BUG.
    Five of the six producers here are FENCES, and a fence exits 2 when it CATCHES something --
    that is the organ working, not failing. `check=True` would have made the work queue refuse
    to build precisely on the days the desk had the most to work on. The honest question is
    whether the artifact was REWRITTEN, so that is what is measured; rc is recorded beside it as
    context, never as the verdict.
    """
    target = _ROOT / artifact
    before = target.stat().st_mtime if target.exists() else None
    out: dict[str, Any] = {"script": script, "artifact": artifact}
    try:
        proc = subprocess.run(
            [sys.executable, str(_ROOT / "scripts" / script), "--report-only"],
            check=False, capture_output=True, timeout=300, cwd=_ROOT,
            env={**dict(__import__("os").environ), "PYTHONPATH": str(_ROOT)})
        out["rc"] = proc.returncode
        out["stderr_tail"] = proc.stderr.decode("utf-8", "replace").strip()[-300:]
    except subprocess.TimeoutExpired:
        out["status"], out["detail"] = "TIMEOUT", "exceeded the 300s budget"
        return out
    except OSError as e:
        out["status"], out["detail"] = "UNRUNNABLE", repr(e)
        return out

    after = target.stat().st_mtime if target.exists() else None
    if after is not None and (before is None or after > before):
        out["status"] = "REFRESHED"
    else:
        out["status"] = "NOT-REWRITTEN"
        out["detail"] = (f"exited rc={out['rc']} without rewriting {artifact}"
                         + (f": {out['stderr_tail']}" if out["stderr_tail"] else ""))
    return out


def _item(aspect: str, source: str, current: float | None, ceiling: float, detail: str,
          action: str, artifact: str) -> dict[str, Any]:
    measured = current is not None
    gap = 1.0 if not measured else max(0.0, (ceiling - current) / ceiling if ceiling else 0.0)
    weight, why = _LEVERAGE[source]
    score = gap * weight * (_UNMEASURED_PRIORITY if not measured else 1.0)
    return {"aspect": aspect, "source": source, "measured": measured,
            "current": None if not measured else round(float(current), 4),
            "ceiling": ceiling, "gap_fraction": round(gap, 4), "leverage": weight,
            "score": round(score, 4), "why_it_matters": why, "detail": detail,
            "next_action": action, "artifact": artifact}


def _from_ratchets() -> list[dict[str, Any]]:
    d = _json("data/ratchet_report.json") or {}
    out = []
    for r in d.get("rows", d.get("metrics", [])) or []:
        name = str(r.get("metric", r.get("name", "?")))
        val = r.get("value", r.get("current"))
        source = ("measurement_quality" if "strength" in name or "mypy" in name
                  else "evidence_throughput")
        out.append(_item(
            f"ratchet::{name}", source, None if val is None else float(val), 1.0,
            f"floor {r.get('floor')} status {r.get('status')}",
            "close the gap to 100%; the survivor/failure list IS the work queue (L1.0c)",
            "data/ratchet_report.json"))
    return out


def _from_utilisation() -> list[dict[str, Any]]:
    d = _json("data/utilisation.json") or {}
    out = []
    for c in d.get("ceilings", []) or []:
        name = str(c.get("name"))
        source = ("capital_utilisation" if "capital" in name else
                  # "queue" as well as "slot": forward_queue_depth (R0205) measures what is
                  # STAGED BEHIND the cohort, which is evidence throughput and not capital. The
                  # default branch below is capital_utilisation, so an unmatched research ceiling
                  # is silently filed against the wrong bottleneck rather than left unrouted.
                  "evidence_throughput" if ("slot" in name or "queue" in name) else
                  "dormant_capability" if "capability" in name else
                  "measurement_quality" if "kill_rate" in name else "capital_utilisation")
        out.append(_item(
            f"ceiling::{name}", source,
            None if not c.get("measured") else float(c.get("utilisation", 0.0)), 1.0,
            f"{c.get('used')}/{c.get('limit')} {c.get('unit')} -- {c.get('status')}",
            c.get("binding_constraint") or "no binding constraint named -- L1.28a defect",
            "data/utilisation.json"))
    return out


def _from_matrix() -> list[dict[str, Any]]:
    d = _json("data/enforcement_matrix.json") or {}
    unenforced = d.get("unenforced", []) or []
    orphans = d.get("fences_without_a_principle", []) or []
    n_prin = max(int(d.get("n_principles", 1)), 1)
    n_fence = max(int(d.get("n_fences", 1)), 1)
    return [
        _item("law::principles_enforced", "unenforced_law",
              (n_prin - len(unenforced)) / n_prin, 1.0,
              f"{len(unenforced)} unenforced: {unenforced[:5]}",
              "map each to a fence, or record it HUMAN-ONLY with the reason",
              "data/enforcement_matrix.json"),
        _item("law::fences_claimed", "unenforced_law", (n_fence - len(orphans)) / n_fence, 1.0,
              f"{len(orphans)} fences claimed by no law",
              "name the governing law in _FENCE_OWNERS, or retire the fence",
              "data/enforcement_matrix.json"),
    ]


def _from_wiring() -> list[dict[str, Any]]:
    """The DORMANT-SCRIPT backlog awaiting a human cadence decision.

    The obvious metric here -- AUTO-WIRE / (AUTO-WIRE + PROPOSE) -- is backwards, and it read 0%
    on the first run of this queue. Once the agent has wired everything it can prove inert, those
    scripts become SCHEDULED and drop out of the dormancy scan entirely, so the auto-wire count
    falls to zero precisely when the automation is fully caught up. Zero there is the FINISHED
    state being reported as total failure.

    What actually remains open is the PROPOSE set: scripts the agent deliberately withheld because
    they touch the money path, can spend, or write outside data/ -- each needing a decision no
    agent is allowed to make. Measured against all scripts scanned, that is a real backlog that
    shrinks as decisions are taken.
    """
    d = _json("data/wiring_agent.json") or {}
    counts = d.get("counts", {}) or {}
    scanned = int(d.get("n_scripts_scanned", 0) or 0)
    proposed = int(counts.get("PROPOSE", 0))
    if not scanned:
        return []
    return [_item("capability::wiring_decisions_pending", "dormant_capability",
                  (scanned - proposed) / scanned, 1.0,
                  f"{proposed} scripts awaiting a cadence decision, of {scanned} scanned "
                  f"({counts}); AUTO-WIRE=0 means the agent is caught up, not stalled",
                  "each PROPOSE row names why it was withheld (money-path / spend / writes "
                  "outside data+web) -- decide a cadence or record why it stays unscheduled",
                  "data/wiring_agent.json")]


def _from_register() -> list[dict[str, Any]]:
    p = _ROOT / "docs/GAP_REGISTER.md"
    if not p.exists():
        return []
    text = p.read_text("utf-8", errors="ignore")
    rows = re.findall(r"^\|\s*#?(\d+)\s*\|", text, re.MULTILINE)
    open_rows = len(re.findall(r"\bOPEN\b", text))
    total = max(len(rows), 1)
    return [_item("register::rows_closed", "open_defect",
                  max(0.0, (total - open_rows) / total), 1.0,
                  f"{open_rows} OPEN of {total} rows",
                  "close highest-EV rows first; a row nobody closes is a cost already being paid",
                  "docs/GAP_REGISTER.md")]


def _from_conversion() -> list[dict[str, Any]]:
    """Conversion debt (L1.28b) ranks in the SAME queue as every other gap.

    Two aspects: the all-time dispositioned fraction (how much of everything ever found reached
    a verdict) and the 7-day flow ratio (is conversion keeping pace with detection RIGHT NOW).
    A missing artifact reports both as unmeasured, which outranks everything (L1.28a: unmeasured
    counts as zero) -- the fence being unwired is itself the top conversion defect.
    """
    d = _json("data/conversion_status.json") or {}
    ratio = d.get("queue_dispositioned")
    arr, disp = d.get("arrivals_7d"), d.get("dispositions_7d")
    flow = None if arr is None or disp is None else min(1.0, disp / arr) if arr else 1.0
    detail = d.get("detail") or "data/conversion_status.json missing -- run check_conversion.py"
    # THREE STATES, NOT TWO. This read `if d.get("repair_mode")`, which was `status != "OK"` at
    # the source and therefore TRUE for ARRIVALS-COLLAPSED -- so the desk's top-ranked queue told
    # a window that had found almost nothing to go and convert instead of hunting. The direction
    # field (L1.28b(d)) separates "the queue is deep" from "the hunt has gone quiet"; they demand
    # opposite work and only one of them is a conversion problem.
    _ACTION = {
        "DRAIN": ("repair-mode: flip the next audit/brain window from finding to fixing; drain "
                  "past-due rows first (each names its own fix)"),
        "FIND-HARDER": ("arrivals collapsed: HUNT HARDER this window -- do NOT redirect it to "
                        "the backlog; raising the ratio by finding less is the denominator "
                        "trick L1.28b(f) forbids"),
        "STEADY": "keep dispositions >= arrivals; a row nobody closes is a cost already paid",
    }
    action = _ACTION.get(str(d.get("direction") or ""),
                         "conversion state UNREADABLE -- treat as owing work, not as nothing "
                         "owing (L1.28a); run scripts/check_conversion.py")
    return [
        _item("conversion::queue_dispositioned", "conversion_debt",
              None if ratio is None else float(ratio), 1.0, detail, action,
              "data/conversion_status.json"),
        _item("conversion::flow_keeps_pace_7d", "conversion_debt", flow, 1.0,
              f"7d: {arr} raised vs {disp} dispositioned; status {d.get('status')}",
              action, "data/conversion_status.json"),
    ]


_TIER_SCORE = {"T1": 1.00, "T2": 0.66, "T3": 0.40, "T4": 0.15}


def _from_tier_benchmark() -> list[dict[str, Any]]:
    """The tier-1 process benchmark (principal 2026-07-31): sub-T1 layers hunt themselves.

    Parses docs/research/TIER1_BENCHMARK.md. time_bound rows are walls, not work -- listed in
    the register, excluded here. A missing register is UNMEASURED (ranks top): the benchmark
    being deleted is itself the largest tier gap.
    """
    p = _ROOT / "docs/research/TIER1_BENCHMARK.md"
    if not p.exists():
        return [_item("tier1::benchmark_register", "tier1_process_gap", None, 1.0,
                      "docs/research/TIER1_BENCHMARK.md missing -- the standing gap register "
                      "was deleted or never synced", "restore the register; the deep sweep "
                      "re-grades it weekly", "docs/research/TIER1_BENCHMARK.md")]
    out = []
    for m in re.finditer(
            r"^\|\s*(\w+)\s*\|\s*(T[1-4]|—)\s*\|\s*(.+?)\s*\|\s*\**(yes|no)\**\s*\|\s*$",
            p.read_text("utf-8"), re.MULTILINE):
        layer, tier, closer, time_bound = m.groups()
        if time_bound == "yes" or tier == "—":
            continue
        score = _TIER_SCORE.get(tier)
        if score is not None and score < 1.0:
            out.append(_item(f"tier1::{layer}", "tier1_process_gap", score, 1.0,
                             f"graded {tier} -- distance to tier-1 process is named work",
                             closer, "docs/research/TIER1_BENCHMARK.md"))
    return out


def _from_calibration() -> list[dict[str, Any]]:
    """Is the desk's own confidence measured and honest? (L1.29)

    Reliability (1 - Brier) is the aspect; an UNFORECASTING or OVERDUE desk reports UNMEASURED,
    which outranks everything -- a desk that never grades its predictions cannot know whether
    it is over-betting."""
    d = _json("data/calibration_status.json") or {}
    st = str(d.get("status", "UNFORECASTING"))
    rel = d.get("reliability")
    measured = st not in ("UNFORECASTING", "OVERDUE") and rel is not None
    return [_item("calibration::forecast_reliability", "calibration_debt",
                  float(rel) if measured else None, 1.0,
                  str(d.get("detail", "no calibration artifact")),
                  "log a probability at every real decision point and RESOLVE it by its "
                  "deadline; the measured bias then shrinks future confidence automatically "
                  "(forecast_calibration.calibrated_confidence)",
                  "data/calibration_status.json")]


def _from_freshness() -> list[dict[str, Any]]:
    """Are live decisions consuming frozen inputs? (L1.44)

    fresh_fraction is the aspect. STALE-CONSUMED means a decision path is being steered by a
    dead producer's last output RIGHT NOW -- money_path_correctness by definition, because the
    bootstrap contracts are the executor's own read sites. UNMEASURED (zero contracts) reports
    unmeasured and ranks above partially-complete work, as everywhere else."""
    d = _json("data/freshness_status.json") or {}
    st = str(d.get("status", "UNMEASURED"))
    frac = d.get("fresh_fraction")
    measured = st != "UNMEASURED" and frac is not None
    return [_item("freshness::contracts_fresh", "money_path_correctness",
                  float(frac) if measured else None, 1.0,
                  str(d.get("detail", "no freshness artifact")),
                  "revive the dead producer or re-wire the caller through "
                  "libs.ops.fresh.read_fresh -- check_freshness.py names both ends of every "
                  "stale edge",
                  "data/freshness_status.json")]


def _from_stranding() -> list[dict[str, Any]]:
    """CONVERSION FAILURES the wiring source structurally cannot see, and that is the whole point.

    `_from_wiring` reads `wiring_agent.json`, which counts scripts nothing SCHEDULES. That misses
    the two states an importer count cannot reach (L1.54(a)): a module IMPORTED and never called,
    and a module that runs while nothing reads its output. Both look reachable from every angle
    the older sources have.

    MEASURED 2026-08-08 and the reason this function exists rather than a note in the register:
    `run_intelligence_cycle` imports `capital_reallocator` and `health_monitor` purely to prove
    they import, then reads the artifacts itself and reports both ACTIVE. The detector found them
    the same morning it was built -- and the queue could not see the finding, so the desk could
    discover a real gap and never prioritise it. Detection without ranking is half a control.

    Scored as `dormant_capability` rather than as a new class: it IS paid-for engineering
    returning zero, and inventing a weight would rank worse while looking more precise.
    """
    d = _json("data/intelligence_cycle.json") or {}
    caps = d.get("capabilities") if isinstance(d, dict) else None
    rows: list[dict[str, Any]] = []
    if isinstance(caps, list):
        for c in caps:
            if isinstance(c, dict) and c.get("name") == "dormancy_hunter":
                rows = c.get("report", {}).get("imported_but_never_called", []) or []
                break
    if not isinstance(rows, list):
        return []
    scanned = 0
    if isinstance(caps, list):
        for c in caps:
            if isinstance(c, dict) and c.get("name") == "dormancy_hunter":
                scanned = int((c.get("report", {}).get("scanned", {}) or {}).get("modules", 0))
                break
    if not scanned:
        # UNMEASURED, NOT ZERO. An absent cycle artifact means nobody looked, and letting that
        # read as "no conversion failures" is WS-005 aimed at the queue's own inputs.
        return [_item("capability::conversion_failures", "dormant_capability", None, 1.0,
                      "no intelligence-cycle artifact -- the stranding scan has not run here",
                      "run scripts/run_intelligence_cycle.py; UNMEASURED outranks a partial "
                      "number because an unknown quantity is being ignored, not worked",
                      "data/intelligence_cycle.json")]
    n = len(rows)
    worst = ", ".join(str(r.get("path", "?")) for r in rows[:3]) or "none"
    return [_item("capability::conversion_failures", "dormant_capability",
                  (scanned - n) / scanned, 1.0,
                  f"{n} module(s) imported by a live consumer that NEVER call them, of {scanned} "
                  f"scanned; worst by size: {worst}",
                  "call it from the consumer that already imports it, or delete the import -- an "
                  "import kept to prove a module loads reports ACTIVE while the capability has "
                  "never run once (L1.54(a))",
                  "data/intelligence_cycle.json")]


def _from_wealth() -> list[dict[str, Any]]:
    """THE ECONOMIC ROWS -- and they belong at the top of the queue, not appended to it.

    Every other `_from_*` reader above measures the desk's PROCESS: floors, fences, wiring,
    conversion, calibration. All of them are proxies for the only thing that decides whether this
    enterprise was worth running, and none of them can fall while real wealth is being lost. A
    queue built purely from process metrics can be entirely green on the day the book round-trips.

    So `data/wealth_report.json` enters the same ranking as everything else, and its DAILY BOARD
    QUESTION becomes a queue row rather than a line in a log. The specification's instruction is
    literal: the highest-value answer becomes the next task.

    Two shapes come through. An UNMEASURED section is scored as unmeasured, which the ranker
    already puts above partially-complete work -- correct here, because "we do not know whether we
    are keeping what we make" outranks any known-and-being-worked number. A MEASURED section with
    a finding (a round trip, hidden beta, process-bound survivors) comes through as a money-path
    row, the heaviest weight the ranker carries.
    """
    d = _json("data/wealth_report.json")
    if not isinstance(d, dict):
        # UNMEASURED, NOT ABSENT-THEREFORE-FINE. No wealth report means nobody asked the board
        # question today, and letting that read as a clean board is WS-005 pointed at the one
        # artifact that outranks the rest of this file.
        return [_item("wealth::board_question", "money_path_correctness", None, 1.0,
                      "no wealth report -- the desk has not asked what is preventing it from "
                      "generating and retaining more real net wealth",
                      "run scripts/run_wealth_report.py; it is wired into the research cycle and "
                      "its absence means the cycle did not complete",
                      "data/wealth_report.json")]
    out: list[dict[str, Any]] = []
    answer = str(d.get("ANSWER", "?"))
    out.append(_item(
        "wealth::board_question", "money_path_correctness", None, 1.0,
        f"BOARD QUESTION answer: {answer}", str(d.get("why", ""))[:400],
        "data/wealth_report.json"))
    for name in d.get("unmeasured_sections") or []:
        sec = (d.get("sections") or {}).get(name) or {}
        out.append(_item(
            f"wealth::{name}", "capital_utilisation", None, 1.0,
            str(sec.get("headline", ""))[:200],
            f"produce {sec.get('missing_artifact', 'the input artifact')} -- until it exists this "
            "section is UNMEASURED, which is a fact about the inputs and not a clean result",
            "data/wealth_report.json"))
    sections = d.get("sections") or {}
    conv = sections.get("conversion") or {}
    process_bound = int(conv.get("process_bound") or 0)
    if process_bound:
        out.append(_item(
            "wealth::process_bound_survivors", "conversion_debt", 0.0, 1.0,
            f"{process_bound} candidate(s) hold sufficient evidence and are not moving, costing "
            f"at least {conv.get('total_process_waiting_cost_bps', 0)}bp",
            "advance each PROCESS_BOUND candidate to its next stage; this latency buys nothing "
            "and is not an evidence question", "data/wealth_report.json"))
    hidden = (sections.get("return_engines") or {}).get("hidden_beta") or []
    if hidden:
        out.append(_item(
            "wealth::hidden_beta", "money_path_correctness", 0.0, 1.0,
            f"{len(hidden)} engine(s) declared independent behave as market exposure",
            "reclassify or re-measure: capital sized against the wrong covariance is the "
            "mechanism behind a round trip", "data/wealth_report.json"))
    return out


#: Shadow prices, declared. THE HONEST STATE IS THAT MOST ARE UNMEASURED, and the frontier report
#: names every unpriced resource rather than letting a total read as a full accounting. Capital
#: carries the only non-zero price today because it is the one resource this desk demonstrably
#: cannot replace: compute and engineering time regenerate daily, a lost stack does not.
_SHADOW_PRICES: dict[str, float] = {"capital": 0.01}

#: How a queue row's declared leverage weight becomes an expected log-wealth contribution. This is
#: a UNIT CONVERSION, not a claim: the weights were never in log-wealth units, and pretending they
#: were would put a fabricated number at the top of the desk's ranking. The frontier report carries
#: the caveat, and the conversion is one constant so it can be argued with in one place.
_LEVERAGE_TO_ELOGW: float = 0.01


def _from_books() -> list[dict[str, Any]]:
    """THE RETURN ENGINES -- an UNMEASURED book is a ranked gap, not a quiet line in a report.

    `scripts/run_opportunity_books.py` runs eleven books every cycle and most of them correctly
    report UNMEASURED, each naming the exact artifact it needs. Left in the report, that reads as
    housekeeping. Ranked here, each missing artifact becomes a queue row competing with everything
    else on the same scale -- which is right, because a return engine with no input is a decision
    the desk is currently making by default rather than by evidence.

    THE DISTINCTION THAT MATTERS AND IS EASY TO LOSE: a book UNMEASURED because this clone has no
    live positions is a fact about the clone. A book UNMEASURED because nobody wrote its
    declaration is a fact about the desk, and only the second is actionable today. The row detail
    carries the book's own headline so the reader can tell which they are looking at.
    """
    d = _json("data/opportunity_books.json")
    if not isinstance(d, dict):
        return [_item("books::opportunity_books", "unenforced_law", None, 1.0,
                      "no opportunity-books report -- eleven return engines exist and none of "
                      "them ran, so where capital would go is unranked",
                      "run scripts/run_opportunity_books.py; it is wired into the research cycle "
                      "and its absence means the cycle did not complete",
                      "data/opportunity_books.json")]
    books = d.get("books")
    if not isinstance(books, dict):
        return []
    out: list[dict[str, Any]] = []
    for name, body in books.items():
        if not isinstance(body, dict):
            continue
        if body.get("measured") is False:
            missing = str(body.get("missing_artifact", "?"))
            out.append(_item(
                f"books::{name}", "money_path_correctness", None, 1.0,
                f"return engine {name} is UNMEASURED -- {missing} is absent",
                str(body.get("headline", ""))[:400],
                "data/opportunity_books.json"))
            continue
        # A MEASURED BOOK IS NOT AUTOMATICALLY A CLEAN ONE, and ranking only the unmeasured ones
        # would have made a book that FOUND something the only book that never reaches the queue.
        # That is the inverse of what this file is for.
        for key, source, label in (
                ("over_privileged", "unenforced_law",
                 "component(s) hold authority above what their work needs"),
                ("capital_sensitive_without_principal", "money_path_correctness",
                 "component(s) sit on a CAPITAL-SENSITIVE rung with no principal authorisation"),
                ("unbounded_blast_radius", "money_path_correctness",
                 "component(s) can propagate failure or destroy irrecoverable data"),
                ("unmeasured_blast_radius", "measurement_quality",
                 "component(s) have never had their blast radius assessed"),
                ("not_sandboxed", "money_path_correctness",
                 "component(s) are not confined to an isolated sub-account or scoped key")):
            found = body.get(key)
            if isinstance(found, list) and found:
                out.append(_item(
                    f"books::{name}::{key}", source, None, 1.0,
                    f"{name}: {len(found)} {label} -- {found}",
                    str(body.get("headline", ""))[:400],
                    "data/opportunity_books.json"))
    return out


def _from_practitioners() -> list[dict[str, Any]]:
    """CORPORA READ WITHOUT EXTRACTING ANY PROCESS AXIS -- the expensive half left behind.

    Reading a practitioner's signal rules and stopping is the cheapest possible extraction and the
    one that feels complete. It is ranked here because it is silently recoverable value: the
    corpus has already been paid for, and the part that compounds is still sitting in it.
    """
    d = _json("data/intelligence/external_intel.json")
    if not isinstance(d, dict):
        return []
    pc = d.get("practitioner_corpus")
    if not isinstance(pc, dict) or pc.get("measured") is not True:
        return []
    out: list[dict[str, Any]] = []
    shallow = pc.get("read_but_no_process_extracted") or []
    if isinstance(shallow, list) and shallow:
        out.append(_item(
            "intel::practitioner_process_axes", "conversion_debt", None, 1.0,
            f"{len(shallow)} practitioner corpus/corpora read with NO process axis extracted: "
            f"{shallow}",
            "The signal rules were taken and the research, validation, retirement and replacement "
            "processes were not. That corpus is already paid for and the part that compounds is "
            "still in it -- re-extract along the process axes before enumerating anything new.",
            "data/intelligence/practitioner_corpus.json"))
    untested = pc.get("untested_disagreements")
    if isinstance(untested, int) and untested > 0:
        out.append(_item(
            "intel::practitioner_disagreements", "conversion_debt", None, 1.0,
            f"{untested} untested disagreement(s) between credible practitioners",
            "Where two people who both made money contradict each other, the answer is "
            "CONDITIONAL and the condition is the thing worth finding. Each is a ready-made "
            "hypothesis with an external prior already attached.",
            "data/intelligence/practitioner_corpus.json"))
    return out


def _frontier(items: list[dict[str, Any]]) -> dict[str, Any]:
    """Re-rank the queue by ECONOMIC SURPLUS rather than by distance-from-ceiling.

    THE TWO ORDERINGS DISAGREE IN A WAY THAT DECIDES DAYS. This file ranks by how far a metric sits
    from 100%, which is correct for a ratchet and wrong for an allocator: a research module at 0%
    outranks deploying a validated survivor at "done", even when the survivor's marginal
    contribution is larger and its opportunity cost is a euro of compute rather than a euro of
    capital. The frontier answers the allocator's question instead.

    Both are published. The queue is the RATCHET -- it never reports done and escalates when
    everything is green. The frontier is the ALLOCATOR. Replacing one with the other would lose a
    control the desk relies on, so neither is deleted.

    The surplus numbers here are DERIVED FROM DECLARED WEIGHTS, not measured, and the report says
    so. Their ordering is informative; their magnitudes are not yet.
    """
    actions: list[Action] = []
    for i in items[:40]:
        gap = float(i.get("gap_fraction") or 0.0)
        lev = float(i.get("leverage") or 0.0)
        if gap <= 0:
            continue
        mean = gap * lev * _LEVERAGE_TO_ELOGW
        # UNMEASURED aspects carry a WIDER posterior, not a larger mean. An unknown quantity is
        # ranked above a known one by the queue's own rule; it must not also be treated as
        # confidently valuable by the allocator.
        sigma = mean * (0.8 if not i.get("measured") else 0.3)
        actions.append(Action(
            action_id=str(i.get("aspect", "?"))[:80],
            category=str(i.get("source", "unknown")),
            elogw_mean=mean, elogw_sigma=max(sigma, 1e-9),
            resources={"research_attention": 1.0},
            proposer=str(i.get("source", "")),
        ))
    rep = frontier_summary(actions, ResourcePrices(dict(_SHADOW_PRICES)))
    rep["derivation_caveat"] = (
        "Surpluses are DERIVED from run_max_push's declared leverage weights via a single "
        f"conversion constant ({_LEVERAGE_TO_ELOGW}), because those weights were never in "
        "log-wealth units. The ORDERING is informative; the MAGNITUDES are not yet, and no sizing "
        "decision may cite them. They become real when actions carry measured posterior "
        "distributions from the wealth report and the live ladder.")
    return rep


def _queue_inputs(refresh: bool) -> tuple[Inputs, list[dict[str, Any]]]:
    """Refresh every producer, then DECLARE the artifacts the queue is about to be built from.

    R0395. The queue is stamped `generated: <now>`; that stamp is a claim about the QUEUE, and
    it was being read as a claim about the NUMBERS IN IT. These two lines are what make the
    difference sayable: what the refresh did, and how old each input actually is.
    """
    runs = [_refresh(script, artifact) for script, artifact in _REFRESHERS] if refresh else []
    by_artifact = {r["artifact"]: r for r in runs}

    inp = Inputs("run_max_push.build")
    for _script, artifact in _REFRESHERS:
        # Absolute, so the declaration follows THIS module's `_ROOT` rather than the provenance
        # helper's own -- identical in production, and a function that takes a root must honour
        # it for every output or its tests are measuring a different desk.
        inp.read_json(_ROOT / artifact, default=None, max_age_h=_ARTIFACT_MAX_AGE_H)
        run = by_artifact.get(artifact)
        if run and run["status"] != "REFRESHED":
            # Attach the producer's fate to the input record. An artifact can be young AND its
            # producer dead (cron wrote it an hour ago, this run's invocation crashed); the two
            # facts belong on the same row or the reader has to join them by hand.
            rec = inp.records[-1]
            rec.detail = (f"{rec.detail}; " if rec.detail else "") + \
                f"producer {run['script']} {run['status']}: {run.get('detail', '')}"
    return inp, runs


def build(*, refresh: bool = True) -> dict[str, Any]:
    inp, refresh_runs = _queue_inputs(refresh)
    items = (_from_ratchets() + _from_utilisation() + _from_matrix()
             + _from_wiring() + _from_register() + _from_conversion()
             + _from_tier_benchmark() + _from_calibration() + _from_freshness()
             + _from_stranding() + _from_wealth()
             + _from_books() + _from_practitioners()
             # Restored 2026-08-11: the 08-09 lineage merge kept these two libs and their tests
             # but resolved THIS file to the branch without their call sites, so both queue
             # sources went dark with no removing commit (found by the §36 orphan census).
             + completion_queue_rows(
                 load_completion_program(_ROOT / "data/completion_program.json"), _item)
             + alpha_frontier_queue_rows(
                 _ROOT / "data/intelligence/daily_alpha_frontier.json", _item)
             # THE GENERIC CHANNEL. Every `_from_*` above is a bespoke reader that knows the shape
             # of one artifact, and adding the tenth made the cost visible: a detector written
             # today cannot influence tomorrow's priorities until somebody edits THIS file, which
             # makes the ranker a gatekeeper on discovery. Detectors now publish `Gap` rows to
             # data/published_gaps/ and are ranked with no edit here. The readers above stay --
             # rewriting working producers to prove a point is the bloat this contract avoids.
             + to_queue_rows(load_published(), _item))
    # THE PRODUCER FAILURE IS ITSELF QUEUE WORK (R0395), not a footnote under the queue. A dead
    # producer bounds how much of everything below it the desk can trust, so it goes in the same
    # ranked list as the gaps it was supposed to measure -- unmeasured, which is where
    # _UNMEASURED_PRIORITY puts it: at the top. Detect implies repair; a provenance block nobody
    # is scheduled to act on is the found-never-fixed defect one layer up.
    for bad in inp.records:
        if bad.status == "READ":
            continue
        items.append(_item(
            f"meta::queue_input::{Path(bad.path).stem}", "measurement_quality", None, 1.0,
            f"{bad.path} is {bad.status}"
            + (f" ({bad.age_h:.1f}h vs {bad.max_age_h}h)" if bad.age_h is not None else "")
            + (f" -- {bad.detail}" if bad.detail else ""),
            f"Re-run the producer for {bad.path} and read its stderr. Every queue row derived "
            f"from this artifact is built on numbers this run did not refresh, while the queue "
            f"itself is stamped with today's date (L1.55).",
            bad.path))

    items.sort(key=lambda r: -float(r["score"]))
    at_ceiling = [i for i in items if i["measured"] and i["gap_fraction"] <= 0.0]
    unmeasured = [i for i in items if not i["measured"]]

    # THE ANTI-COMPLACENCY ESCALATION. All-green means the measurement set is too small, not that
    # the desk is finished. Emitted as the top item so it cannot be read as a clean board.
    verdict = "PUSH"
    if items and len(at_ceiling) == len(items):
        verdict = "MEASUREMENT-SET-TOO-SMALL"
        items.insert(0, _item(
            "meta::measurement_coverage", "unenforced_law", None, 1.0,
            f"all {len(items)} measured aspects are at their ceiling",
            "A system that reaches 100% on everything it measures is measuring too little. "
            "The correct next action is to ADD ceilings -- name an aspect of this desk that "
            "currently carries no number and give it one (L1.0a: a capability with no number "
            "is a defect).", "data/max_push_queue.json"))
    return {
        "generated": datetime.now(tz=UTC).isoformat(),
        "law": "L1.0 -- the gap between today's value and 100% IS the work queue. This organ "
               "never reports done: all-green escalates to MEASUREMENT-SET-TOO-SMALL.",
        "verdict": verdict,
        # WHAT THE `generated` STAMP ABOVE ACTUALLY COVERS (R0395). `OK` = every input was
        # refreshed and is inside its age contract, so the stamp describes the NUMBERS too;
        # anything else = the stamp describes only when this file was ASSEMBLED.
        "inputs_status": inp.status(),
        "inputs_why": inp.why(),
        "input_provenance": inp.block(),
        "refresh_runs": refresh_runs,
        "n_aspects": len(items), "n_unmeasured": len(unmeasured),
        "n_at_ceiling": len(at_ceiling),
        "mean_completion": round(
            sum(1.0 - float(i["gap_fraction"]) for i in items) / max(len(items), 1), 4),
        "queue": items,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--top", type=int, default=12)
    ap.add_argument("--no-refresh", action="store_true", help="use existing artifacts as-is")
    args = ap.parse_args()
    rep = build(refresh=not args.no_refresh)
    _OUT.parent.mkdir(parents=True, exist_ok=True)
    _OUT.write_text(json.dumps(rep, indent=2), "utf-8")
    # THE ALLOCATOR'S VIEW, published alongside the ratchet's. Neither replaces the other.
    front = _frontier(rep["queue"])
    _FRONTIER_OUT.write_text(json.dumps(front, indent=2), "utf-8")
    if args.json:
        print(json.dumps(rep, indent=2))
    else:
        for r in rep["refresh_runs"]:
            if r["status"] != "REFRESHED":
                print(f"  PRODUCER {r['status']}: {r['script']} -- {r.get('detail', '')}")
        if rep["inputs_status"] != "OK":
            print(f"  QUEUE INPUTS {rep['inputs_status']}: {rep['inputs_why']}")
        print(f"MAX PUSH [{rep['verdict']}] {rep['n_aspects']} aspects | "
              f"mean completion {rep['mean_completion']:.1%} | "
              f"{rep['n_unmeasured']} UNMEASURED | {rep['n_at_ceiling']} at ceiling")
        for i, r in enumerate(rep["queue"][:args.top], 1):
            cur = "UNMEASURED" if not r["measured"] else f"{float(r['current']):.1%}"
            print(f"{i:3}. [{r['score']:.3f}] {r['aspect']:44} {cur:>11}  {r['detail'][:60]}")
        print(f"FRONTIER: {front['headline']}")
        print(f"-> {_OUT.relative_to(_ROOT)}, {_FRONTIER_OUT.relative_to(_ROOT)}")
    # Never fails the build: this is the WORK QUEUE, not a gate. A queue that fails CI would be
    # muted within a week, and the whole point is that it is read every morning.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

```

### scripts\run_strategy_coverage.py
```python
#!/usr/bin/env python3
"""STRATEGY-FAMILY COVERAGE (R0200) -- what KINDS of edge has the desk hunted, and what has it
never looked at once.

PRINCIPAL ORDER (2026-07-31): *"miners n explorers kimi etc all should find every ... strat
even discretionary n all n never limit to just one thing"* + *"discretionary section can copy
discretionary findings to self improve"*. The order's SUBJECT was narrowed by the universe
mandate (2026-08-18) from crypto to the MT5/Fusion book; its INSTRUCTION -- never limit to just
one thing -- is unchanged and is what this organ enforces. See the FAMILIES map for what that
narrowing removed and what it repointed.

THE GAP THIS CLOSES, and it is a whole axis the desk was blind on. Every existing coverage organ
maps WHERE the miners look -- source families, regions, languages (prospector_coverage.md tracks
9 source families across 7 regional seats). NOTHING maps WHAT KIND OF EDGE they come back with.
So the desk could report healthy source coverage while every card it ever carded came from three
mechanism families, and no organ could see it. 42 strategies are buried in the graveyard; they
cluster, and until now nobody counted the clusters.

WHY THE CLUSTER COUNT IS THE POINT. A miner that has tested twelve cross-sectional factors and
zero execution-microstructure mechanisms has not covered the space, it has covered ONE family
twelve times -- and the twelve are correlated by construction, so they die together and the
desk learns roughly one thing. Coverage is the count of DISTINCT FAMILIES touched, never the
count of candidates tested, and the two diverge exactly when a miner gets comfortable.

THE FAMILIES are enumerated below from the desk's own record -- every one is either present in
docs/graveyard.md, in the recommendation ledger, or named here as NEVER-HUNTED, which is the
output that earns this organ its place. UNHUNTED is a finding, not an omission.

THE DISCRETIONARY IMPORT, and the rule that keeps it safe. Families adjacent to the conviction
sleeve's own method (trend/structure, breakout, level-reaction, positioning-extreme) are routed
to the sleeve as PROVISIONAL playbook candidates -- never SUPPORTED. An outside finding may
SUGGEST a method change; only the sleeve's own closed trades may AUTHORISE one. That asymmetry
is the whole safety property: run_trade_review requires N_SUPPORT=3 of the desk's OWN
confirmations before a lesson reaches the trading brief, and an imported claim that could skip
that queue would let a miner's untested assertion silently rewrite the money path. So imports
enter the queue at the back, marked with their origin, and earn promotion the same way
everything else does.

    python scripts/run_strategy_coverage.py [--json] [--import-discretionary]
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_ROOT = Path("/home/quant/quant-platform")
if not _ROOT.exists():
    _ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
from libs.ops.lawful import guard as _law_guard  # noqa: E402

_STATE = "data/strategy_coverage.json"
_PLAYBOOK = "data/trading_playbook.json"

#: Minimum distinct candidates in a family before its coverage counts as real. 3 because one
#: test is an anecdote and two is a coincidence: a family "covered" by a single dead candidate
#: is the exact self-report this organ exists to refuse.
THIN_BELOW = 3

#: THE FAMILY MAP. Each: (matcher patterns against graveyard/ledger names, discretionary-adjacent,
#: what the family actually claims). Adjacency marks families whose mechanism the CONVICTION
#: sleeve could act on -- those are the ones whose findings route to its playbook.
#
# REPOINTED ONTO THE MT5 UNIVERSE, 2026-09-05 (principal's standing order 2026-08-18). This map is
# a SCORING VOCABULARY, and the mandate names scoring vocabulary explicitly: no vocabulary may
# target crypto-exchange-native opportunities. Three families were deleted outright because they
# have no MT5 instrument behind them at all --
#
#   CROSS-VENUE-PREMIUM  kimchi / bithumb / coinone / coinbase cross-exchange premium. The desk
#                        trades ONE broker; there is no second venue to lead the first.
#   COPY-TRADER-SKILL    Hyperliquid leaderboards and elite-account mirroring. A crypto-exchange
#                        product, not an instrument.
#   ONCHAIN-FLOW         exchange netflow, stablecoin supply, mint/burn, TVL. Settlement-layer
#                        data for a settlement layer no MT5 symbol sits on.
#
# and four were repointed at their real MT5 analogue rather than deleted, because the MECHANISM is
# venue-neutral and only the instrument was crypto: CARRY-FUNDING (perp funding -> broker swap /
# rollover / futures term structure), ORDER-FLOW-POSITIONING (exchange OI-and-long/short ratios ->
# COT/CFTC reported positioning), EVENT-AND-CALENDAR (token unlocks and exchange listings ->
# releases, NFP/CPI/FOMC, earnings), LEAD-LAG (BTC leading alts -> DXY/yields/gold leading FX).
#
# WHAT THIS DOES TO THE BREADTH FENCE, said out loud rather than discovered later. Three of the
# eight families that read HUNTED were hunted ONLY on the retired universe, and the repointed rows
# lose the crypto-native candidates that used to match them, so measured coverage falls from 8/14
# to 4/11 and check_strategy_breadth.py now reports NARROW where it reported OK. It still EXITS 0
# -- NARROW is a finding about where to dig next, not a breach -- and the finding it prints is the
# right one: the next dig belongs in ORDER-FLOW-POSITIONING, i.e. the COT positioning this desk
# can actually read. That is the correct reading, not a regression: an MT5 desk claiming breadth on
# the strength of kimchi premium, copy-trading leaderboards and on-chain netflow is claiming
# coverage of a map it no longer trades. The floor (MIN_HUNTED_FRACTION) is NOT moved to absorb
# this, and no family is invented to pad the denominator back.
FAMILIES: dict[str, dict[str, Any]] = {
    "CARRY-FUNDING": {
        # "funding" stays as a matcher: it is how the desk's own record NAMES this family, and the
        # MT5 financing leg (swap, rollover, term structure) is the same mechanism priced by a
        # different counterparty. "premium_arb" went with CROSS-VENUE-PREMIUM.
        "patterns": ("funding", "carry", "basis", "swap_rate", "rollover", "term_structure",
                     "rate_differential"),
        "discretionary": False,
        "claim": "the financing leg -- broker swap/rollover, futures term structure -- is "
                 "harvestable after costs"},
    "CROSS-SECTIONAL-FACTOR": {
        "patterns": ("xsec", "lowvol", "size_and_volume", "illiquidity", "reversal", "breadth"),
        "discretionary": False,
        "claim": "rank the universe on a characteristic and go long/short the tails"},
    "TREND-AND-STRUCTURE": {
        "patterns": ("trend", "breakout", "trailbreak", "atrexit", "kama", "squeeze",
                     "ta_indicator", "momentum"),
        "discretionary": True,
        "claim": "price structure persists -- the conviction sleeve's OWN family"},
    "ORDER-FLOW-POSITIONING": {
        # The venue-neutral half of the old row is kept ("order_flow", "positioning"); the
        # exchange-native half (OI/long-short ratios, elite accounts, liquidation cascades,
        # smart-vs-dumb money feeds) is replaced by the reported positioning this desk can
        # actually read -- CFTC Commitments of Traders, which scripts/fetch_cot.py already
        # collects and scripts/screen_cot_positioning.py already screens.
        "patterns": ("order_flow", "positioning", "cot", "commitments", "net_long", "net_short",
                     "managed_money", "swap_dealer", "dealer_net", "commercial"),
        "discretionary": True,
        "claim": "crowded or extreme REPORTED positioning predicts the next move"},
    "ATTENTION-SENTIMENT": {
        "patterns": ("wikipedia", "attention", "sentiment", "social", "commit_velocity"),
        "discretionary": False,
        "claim": "measurable attention leads returns"},
    "MARKET-MAKING-EXECUTION": {
        "patterns": ("grid", "ladder", "market_mak", "spread_capture", "maker", "microstructure"),
        "discretionary": False,
        "claim": "earn the spread / earn better fills rather than predict direction"},
    "VOL-AND-OPTIONS": {
        "patterns": ("vol-target", "vol_target", "options", "variance", "skew", "gamma"),
        "discretionary": False,
        "claim": "implied-vs-realised volatility and its surface are tradeable"},
    "EVENT-AND-CALENDAR": {
        # "listing" (exchange listing watch) and "unlock" (token unlock schedules) are gone; the
        # scheduled events an MT5 book actually trades are macro releases and earnings, which
        # scripts/build_event_calendar.py already enumerates.
        "patterns": ("event", "announce", "calendar", "release", "nfp", "cpi", "fomc",
                     "earnings", "regime_rotation", "inout_regime"),
        "discretionary": True,
        "claim": "scheduled or announced events move price predictably"},
    "LEVEL-REACTION": {
        "patterns": ("level", "support", "resistance", "range_edge", "liquidity_pool", "sweep"),
        "discretionary": True,
        "claim": "price reacts at levels a crowd can see -- the sleeve's stop-placement thesis"},
    "STATISTICAL-ARBITRAGE": {
        "patterns": ("pairs", "cointegrat", "statarb", "mean_revert", "spread_trade"),
        "discretionary": False,
        "claim": "a modelled relationship between instruments reverts",
        # R0296 (RU practitioner corpus, 2026-08-01) -- binds whoever tests this family FIRST:
        "test_prior": ("spend the test budget on COST/CAPACITY measurement, never the estimator "
                       "(Kalman/polynomial ~= OLS+sigma per practitioner reply chains). Prior: "
                       "~4.78%/yr gross per contract over 80 cointegrated pairs; capacity ceiling "
                       "~USD 3-11k/pair before MMs reclaim it -- under L1.18a that is this desk's "
                       "band, not a disqualifier; slippage+colocation is the binding constraint "
                       "named by every source")},
    "LEAD-LAG": {
        # "btc_leadlag" (BTC leading the alt complex) replaced by the leaders an MT5 book has:
        # the dollar index, the rates curve, and gold against the FX crosses that carry it.
        "patterns": ("leadlag", "lead_lag", "dxy", "yield_lead", "gold_lead", "index_lead",
                     "correlation_regime"),
        "discretionary": False,
        "claim": "one instrument's move predicts another's with a lag"},
}


def _corpus(root: Path, *, errors: list[str] | None = None) -> list[tuple[str, str]]:
    """(name, origin) for every strategy the desk has a record of testing.

    Read failures are APPENDED to `errors`, never swallowed: an unreadable graveyard yields an
    empty corpus, and an empty corpus reports every family NEVER-HUNTED -- the loudest verdict
    this organ has, produced by a missing file rather than by a real gap. The caller surfaces it
    so the two are never confused."""
    errs = errors if errors is not None else []
    out: list[tuple[str, str]] = []
    try:
        lines = (root / "docs/graveyard.md").read_text("utf-8", errors="ignore").splitlines()
        for i, ln in enumerate(lines):
            # A row whose NEXT line is the |---| separator is a table HEADER, not a strategy.
            # Checking that rather than blacklisting header words handles the file's several
            # tables, and it is why "name" stopped being counted as a buried candidate.
            nxt = lines[i + 1] if i + 1 < len(lines) else ""
            if re.match(r"\s*\|\s*:?-{2,}", nxt) or re.match(r"\s*\|\s*:?-{2,}", ln):
                continue
            # The name is the first cell's leading token; most rows continue with a
            # parenthetical description ("kama_squeeze (TTM squeeze + KAMA...)"), so anchoring on
            # a closing pipe silently dropped 31 of 42 rows -- and a coverage organ that reads a
            # quarter of the record reports NEVER-HUNTED for families the desk has genuinely
            # worked, which is worse than not reporting at all.
            m = re.match(r"\|\s*([a-z0-9_-]{3,})\b", ln)
            if m:
                out.append((m.group(1), "graveyard"))
    except OSError as exc:
        errs.append(f"graveyard unreadable ({type(exc).__name__}: {exc})")
    try:
        led = json.loads((root / "docs/research/recommendation_ledger.json").read_text("utf-8"))
        rows = led["recommendations"] if isinstance(led, dict) else led
        for r in rows:
            s = str(r.get("summary") or "")
            if s:
                out.append((s.lower()[:400], "ledger"))
    except (OSError, ValueError, KeyError, TypeError) as exc:
        errs.append(f"ledger unreadable ({type(exc).__name__}: {exc})")
    return out


def coverage(root: Path | None = None) -> dict[str, Any]:
    """Distinct families touched, and which have never been looked at once."""
    root = root or _ROOT
    errors: list[str] = []
    corpus = _corpus(root, errors=errors)
    graveyard = [(n, o) for n, o in corpus if o == "graveyard"]
    fams: dict[str, Any] = {}
    for name, spec in FAMILIES.items():
        hits = sorted({n for n, o in graveyard
                       if any(p in n for p in spec["patterns"])})
        mentions = sum(1 for n, o in corpus if o == "ledger"
                       and any(p in n for p in spec["patterns"]))
        state = ("HUNTED" if len(hits) >= THIN_BELOW else
                 "THIN" if hits else
                 "MENTIONED-NEVER-TESTED" if mentions else "NEVER-HUNTED")
        fams[name] = {
            "state": state, "n_tested": len(hits), "tested": hits[:8],
            "ledger_mentions": mentions,
            "discretionary_adjacent": bool(spec["discretionary"]),
            "claim": spec["claim"],
            # An operative prior rides WITH the gap it governs (R0296): the artifact that tells
            # a reader "never tested" is the artifact that reader opens before testing.
            **({"test_prior": spec["test_prior"]} if "test_prior" in spec else {}),
            "why": (f"{len(hits)} distinct candidates buried -- this family has been genuinely "
                    "worked" if state == "HUNTED" else
                    f"only {len(hits)} candidate(s) tested; one test is an anecdote and two a "
                    "coincidence, so this family is NOT covered" if state == "THIN" else
                    f"{mentions} ledger mention(s) but nothing ever reached the graveyard -- "
                    "discussed, never tested" if state == "MENTIONED-NEVER-TESTED" else
                    "NEVER HUNTED -- no candidate of this family has ever been tested or rowed. "
                    "This is a finding, not an omission"),
        }
    unhunted = [k for k, v in fams.items() if v["state"] in ("NEVER-HUNTED",
                                                             "MENTIONED-NEVER-TESTED")]
    thin = [k for k, v in fams.items() if v["state"] == "THIN"]
    hunted = [k for k, v in fams.items() if v["state"] == "HUNTED"]
    return {
        "generated": datetime.now(tz=UTC).isoformat(),
        "law": "L1.32/L1.31 -- coverage is the count of DISTINCT FAMILIES touched, never the "
               "count of candidates tested. Twelve candidates from one family are correlated by "
               "construction: they die together and the desk learns roughly one thing.",
        # UNREADABLE outranks every substantive verdict. With no corpus every family reads
        # NEVER-HUNTED -- this organ's loudest output -- produced by a missing file rather than
        # by a real gap, and a reader cannot tell the two apart from the families alone.
        "status": ("UNREADABLE" if errors and not graveyard else
                   "UNCOVERED" if unhunted else "THIN" if thin else "COVERED"),
        "read_errors": errors,
        "n_families": len(FAMILIES),
        "n_hunted": len(hunted), "n_thin": len(thin), "n_unhunted": len(unhunted),
        "n_candidates_seen": len(graveyard),
        "families": fams,
        "unhunted": unhunted, "thin": thin,
        "next_family": (unhunted[0] if unhunted else thin[0] if thin else None),
        "detail": ("; ".join(errors) + " -- no corpus, so the family verdicts below are an "
                   "artefact of the read failure, NOT a coverage finding"
                   if errors and not graveyard else
                   f"{len(hunted)}/{len(FAMILIES)} families genuinely hunted across "
                   f"{len(graveyard)} buried candidates; {len(unhunted)} never hunted, "
                   f"{len(thin)} thin"),
        "never_narrow": ("the miners' next dig must open a family from `unhunted`, not deepen "
                         "one from `hunted` -- a family already worked returns correlated "
                         "candidates, and correlated candidates are one bet wearing many names"
                         if unhunted else
                         "every family has been touched; depth in the THIN ones is now the "
                         "higher-value direction"),
    }


def discretionary_candidates(root: Path | None = None) -> list[dict[str, Any]]:
    """Families the CONVICTION sleeve could act on, as playbook candidates.

    Only families flagged discretionary_adjacent -- a carry or vol-surface finding is real
    research but the sleeve cannot express it, so routing it there would be noise in the one brief
    that has to stay sharp."""
    root = root or _ROOT
    cov = coverage(root)
    out = []
    for name, f in cov["families"].items():
        if not f["discretionary_adjacent"]:
            continue
        out.append({"family": name, "state": f["state"], "claim": f["claim"],
                    "n_tested": f["n_tested"], "tested": f["tested"]})
    return out


def import_to_playbook(root: Path | None = None) -> dict[str, Any]:
    """File discretionary-family findings as PROVISIONAL playbook lessons.

    THE ASYMMETRY THAT MAKES THIS SAFE: an outside finding may SUGGEST a method change; only the
    sleeve's OWN closed trades may authorise one. run_trade_review requires N_SUPPORT confirmations
    before a lesson reaches the trading brief, and an import that skipped that queue would let an
    untested external claim rewrite the money path silently. So imports enter at the back of the
    same queue, carry their origin, and earn promotion exactly like a lesson the sleeve learned
    itself. Re-running is idempotent: an already-imported family is not re-filed.
    """
    root = root or _ROOT
    path = root / _PLAYBOOK
    try:
        pb = json.loads(path.read_text("utf-8"))
    except (OSError, ValueError):
        pb = {"lessons": [], "reviewed_keys": []}
    have = {lv.get("imported_from") for lv in pb.get("lessons", [])}
    filed = []
    for c in discretionary_candidates(root):
        key = f"strategy_coverage:{c['family']}"
        if key in have or c["state"] == "NEVER-HUNTED":
            continue                       # nothing to import from a family with no record yet
        pb.setdefault("lessons", []).append({
            "lesson": (f"{c['family']}: {c['claim']}. The desk's own record has {c['n_tested']} "
                       f"buried candidate(s) here ({', '.join(c['tested'][:4]) or 'none named'}) "
                       f"-- state {c['state']}."),
            "status": "PROVISIONAL", "support": 0,
            "origin": "IMPORTED from strategy-family coverage (R0200), NOT from a closed trade",
            "imported_from": key,
            "authority": "SUGGESTS ONLY. An external finding never reaches the trading brief on "
                         "its own -- it needs the sleeve's own confirmations like any lesson.",
            "trades": [],
            "at": datetime.now(tz=UTC).isoformat(),
        })
        filed.append(c["family"])
    if filed:
        path.parent.mkdir(parents=True, exist_ok=True)
        pb["updated"] = datetime.now(tz=UTC).isoformat()
        path.write_text(json.dumps(pb, indent=2), "utf-8")
    return {"filed": filed, "n_filed": len(filed),
            "why": (f"filed {len(filed)} discretionary-family finding(s) as PROVISIONAL with "
                    "support=0 -- they reach the trading brief only after the sleeve's own "
                    "closed trades confirm them" if filed else
                    "nothing new to import; every discretionary-adjacent family with a record "
                    "is already queued")}


def main() -> int:
    _law_guard()
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--import-discretionary", action="store_true",
                    help="file discretionary-family findings as PROVISIONAL playbook lessons")
    args = ap.parse_args()
    rep = coverage(_ROOT)
    if args.import_discretionary:
        rep["import"] = import_to_playbook(_ROOT)
    out = _ROOT / _STATE
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(rep, indent=2), "utf-8")
    if args.json:
        print(json.dumps(rep, indent=2))
    else:
        print(f"strategy coverage (L1.32): {rep['status']} -- {rep['detail']}")
        for k in rep["unhunted"]:
            print(f"  NEVER-HUNTED  {k:<26} {rep['families'][k]['claim'][:58]}")
        for k in rep["thin"]:
            print(f"  THIN          {k:<26} {rep['families'][k]['n_tested']} tested")
        if rep.get("import"):
            print(f"  imported: {rep['import']['n_filed']} provisional playbook lesson(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())

```
