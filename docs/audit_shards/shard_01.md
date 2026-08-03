# AUDIT SHARD 1/13 -- seat x-ai/grok-4.3

You are reviewing SOURCE CODE, not a summary. Previous panels received a 13,185-char self-description and never saw the code; that is why this exists.

- TIER 1 (money path) is included IN FULL and is sent to every seat: 41 files. A defect here costs money.
- TIER 2 is YOUR SHARD ALONE: 29 files. No other seat sees these, so anything you miss here is missed entirely.
- WITHHELD: 86 modules classified INERT (nothing reads them; deleting breaks nothing). They are named below. **If you believe an exclusion is wrong, say so** -- a silent omission is how a blind spot survives an audit.

## Withheld (INERT) -- challenge these if the classification looks wrong

backfill_oi_ls_oos, backfill_onchain_oos, batch_premium, build_panel_rulings, build_scoreboard, bundle_all, capacity_simulator, capacity_test, check_readiness, check_spot_testnet, check_testnet, classify_regime, collect_binance_metrics, collect_bitmex_funding, collect_deribit_surface, collect_free_signals, collect_hyperliquid_funding, collect_market_breadth, compute_performance, dl_metrics_history, fetch_video_transcript, hl_breadth_flow, hl_dir_flow, hl_feature_factory, hl_filter_test, hl_oos_elite, ingest_crypto, ingest_crypto_enriched, ingest_etfs, ingest_history, ingest_multiasset, iros_batch, log_swaps, make_archive, measure_matrix_window, ops_server, publish_dashboard_url, publish_netlify, pull_cme, reconstruct_kaiko_reference_rate, record_capital_event, reflexivity_m5, run_alpha_registry, run_autodiscovery, run_campaign, run_capital_plan, run_capture_analysis, run_carry_crowding, run_cashcarry_backtest, run_combined_stats, run_crossasset_robust, run_crossexchange_backtest, run_crypto_portfolio, run_demo, run_derivative_backtest, run_edge_gated_leverage, run_factor_model, run_factory, run_factory_status, run_firm_alphas_backtest, run_freedata_backtest, run_funding_8h, run_lifecycle, run_mt5_funding_bridge, run_options_vrp_backtest, run_overlay_backtest, run_portfolio_live, run_regime_engine, run_research_lake, run_research_tick, run_sleeve_alloc, run_stress, run_tournament, run_worker, run_xsec_funding_max, score_panel, screen_cme_basis, screen_etf_flows, screen_mining, screen_oi_ls_axes, serve_dashboard, setup_netlify, setup_ngrok, setup_spot_testnet_keys, setup_testnet_keys, smoke_orchestration

## TIER 1 -- money path (every seat reviews this)

### libs/discovery/tail_risk.py
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

### libs/execution/binance_live.py
```python
"""Binance USD-M Futures LIVE connector -- execution hands only, no alpha, no keys in code.

Mirrors libs/execution/binance_testnet.py's interface EXACTLY (drop-in: callers that already
work against the testnet module work against this one unchanged) but is pinned to the LIVE
base URL. Per docs/LIVE_CONNECTOR_SPEC.md section 1 + engineering_backlog.json
``live_connector_prebuild``: this module is FULLY INERT -- every signed call raises -- unless
ALL THREE hold:
  1. ``data/secrets/binance_live.json`` exists with a trade-only, withdrawal-disabled key
     (placed by the PRINCIPAL via SSH -- never chat, never env var, never committed);
  2. ``data/LIVE_ENABLE`` flag file exists (explicit arm switch, separate from key placement so
     "keys exist" and "trading is armed" are never the same moment);
  3. ``data/LIVE_VPS_VERIFIED`` marker exists (VPS-stability precondition -- set only after the
     operator confirms the deployment host is the durable one, not a rebuild-in-progress box).
Unlike the testnet connector, credentials are read from the KEYFILE ONLY -- no environment-
variable path. A systemd unit's environment is visible via ``/proc/<pid>/environ`` to anyone
with host access; live trade-only keys stay in one file with explicit, auditable placement.

CAPABILITY WHITELIST (hard, by construction -- not a runtime check): this module defines ONLY
order-placement, order-cancellation, and read functions. It has no withdrawal, transfer,
sub-account, or key-management function and never will -- those Binance endpoints are simply
never wrapped here. Adding one would need a from-scratch review, not an edit to this file.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import time
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

from libs.core.logging import get_logger

# OBSERVABILITY (gap #56, 2026-07-29). The desk already OWNED a structured logger with
# correlation ids and secret redaction (libs/core/logging.py) and NOTHING below the script
# boundary used it -- 1 of 318 modules. That is an activation gap, not a missing capability, so
# nothing new was built: this is the money path adopting the convention the desk already has.
# The library NEVER configures handlers or levels (the owning script does, via
# configure_logging), so importing this cannot change any current output.
# NEVER LOG: api key, secret, signature, or the signed query string -- fenced by
# tests/execution/test_obs_logging.py, which scans this file's log calls.
_log = get_logger(__name__)

_BASE = "https://fapi.binance.com"              # PINNED live futures -- verified against docs
_KEYFILE = Path("data/secrets/binance_live.json")
_ENABLE_FLAG = Path("data/LIVE_ENABLE")
_VPS_MARKER = Path("data/LIVE_VPS_VERIFIED")


def _creds() -> tuple[str | None, str | None]:
    if not _KEYFILE.exists():
        return None, None
    try:
        d = json.loads(_KEYFILE.read_text("utf-8"))
        return d.get("key"), d.get("secret")
    except (json.JSONDecodeError, OSError):
        return None, None


def has_keys() -> bool:
    k, s = _creds()
    return bool(k and s)


def is_armed() -> tuple[bool, str]:
    """All three go-live preconditions, evaluated together (see module docstring)."""
    checks = {
        "keys_present": has_keys(),
        "live_enable_flag": _ENABLE_FLAG.exists(),
        "vps_verified": _VPS_MARKER.exists(),
    }
    return all(checks.values()), ", ".join(f"{k}={v}" for k, v in checks.items())


def _get(path: str, params: dict[str, Any] | None = None) -> Any:
    """Public market data -- no keys, no arming required (read-only, harmless)."""
    url = f"{_BASE}{path}"
    if params:
        url += "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": "quant-live/1.0"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read())


def _signed(path: str, params: dict[str, Any], *, method: str = "GET") -> Any:
    armed, why = is_armed()
    if not armed:
        # A refused signed call is a decision worth a trail: post-incident forensics needs to
        # distinguish "the desk never tried" from "the venue rejected it".
        _log.warning("signed call REFUSED, not armed: path=%s reason=%s", path, why)
        raise RuntimeError(f"binance_live not armed ({why}) -- refusing signed call {path}")
    key, secret = _creds()
    assert key is not None and secret is not None  # armed (checked above) => creds present
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
    """Per-symbol step size, min qty, and price/qty precision (for valid order sizing)."""
    info = _get("/fapi/v1/exchangeInfo")
    out: dict[str, dict[str, float]] = {}
    for s in info.get("symbols", []):
        f = {flt["filterType"]: flt for flt in s.get("filters", [])}
        lot = f.get("LOT_SIZE", {})
        pf = f.get("PRICE_FILTER", {})
        out[s["symbol"]] = {
            "step": float(lot.get("stepSize", 0.001)), "min_qty": float(lot.get("minQty", 0.0)),
            "qty_prec": int(s.get("quantityPrecision", 3)),
            "tick": float(pf.get("tickSize", 0.01)), "price_prec": int(s.get("pricePrecision", 2)),
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

    None when no fills are visible yet, the read fails, or the connector isn't armed --
    callers fall back to the mark rather than fabricate a price."""
    try:
        trades = _signed("/fapi/v1/userTrades", {"symbol": symbol, "startTime": start_ms,
                                                 "limit": 100})
        fills = [t for t in trades if t.get("side") == side]
        base = sum(float(t["qty"]) for t in fills)
        quote = sum(float(t["quoteQty"]) for t in fills)
        return quote / base if base > 0 and quote > 0 else None
    except Exception:
        return None


def mark_prices() -> dict[str, float]:
    """Latest price per symbol (public endpoint -- no keys needed, used for sizing)."""
    data = _get("/fapi/v1/ticker/price")
    return {d["symbol"]: float(d["price"]) for d in data} if isinstance(data, list) else {}


def account_balance() -> float:
    """USDT wallet balance on the live futures account."""
    for b in _signed("/fapi/v2/balance", {}):
        if b.get("asset") == "USDT":
            return float(b.get("balance", 0.0))
    return 0.0


def account_summary() -> dict[str, float]:
    """Equity, wallet, unrealized PnL, available, and margin used (the live P&L snapshot)."""
    a = _signed("/fapi/v2/account", {})
    return {
        "wallet": float(a.get("totalWalletBalance", 0.0)),
        "equity": float(a.get("totalMarginBalance", 0.0)),
        "unrealized_pnl": float(a.get("totalUnrealizedProfit", 0.0)),
        "available": float(a.get("availableBalance", 0.0)),
        "margin_used": float(a.get("totalInitialMargin", 0.0)),
    }


def _income_rows(since_ms: int, income_type: str = "",
                 fetch: Any = None) -> list[dict[str, Any]]:
    """ALL income rows since ``since_ms`` -- paginated past the venue's 1000-row page cap."""
    get = fetch or (lambda p: _signed("/fapi/v1/income", p))
    params: dict[str, Any] = {"limit": 1000}
    if income_type:
        params["incomeType"] = income_type
    if not since_ms:
        rows = get(params)
        return list(rows) if isinstance(rows, list) else []
    out: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str, str]] = set()
    cursor = since_ms
    for _ in range(50):
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
        cursor = last + 1 if last <= cursor else last
    return out


def income_summary(since_ms: int = 0, fetch: Any = None) -> dict[str, float]:
    """Realized PnL, funding earned/paid, and commission since ``since_ms`` (default: recent)."""
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
    squeeze that took it. Returns symbol -> count of force events; {} without arming or on error.
    """
    if not is_armed()[0]:
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
    """Venue MARKET_LOT_SIZE cap for ``symbol``, cached. inf when unknown (never invent a limit).

    Added 2026-07-27 after COOKIEUSDT (maxQty 150,000) rejected every 183,140 market order with
    -4005, pushing the executor onto its resting-limit fallback, whose accumulated fills walked a
    short through zero into a +916,772 long.
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
        pass                                  # unknown cap -> behave exactly as before
    _MKT_MAX_CACHE[symbol] = cap
    return cap


def place_market(symbol: str, side: str, qty: float,
                 reduce_only: bool = False) -> dict[str, Any]:
    """Place a market order, SPLIT to respect the venue MARKET_LOT_SIZE cap.

    ``reduce_only=True`` makes the order arithmetically incapable of passing through zero and
    opening the opposite position -- mandatory on any cover/close leg.
    """
    cap = _market_max_qty(symbol)
    _log.info("place_market symbol=%s side=%s qty=%s reduce_only=%s chunk_cap=%s",
              symbol, side, qty, reduce_only, cap)
    remaining, last, n = float(qty), None, 0
    while remaining > 0 and n < 50:
        chunk = min(cap, remaining) if cap != float("inf") else remaining
        params = {"symbol": symbol, "side": side, "type": "MARKET", "quantity": chunk}
        if reduce_only:
            params["reduceOnly"] = "true"
        last = _signed("/fapi/v1/order", params, method="POST")
        remaining -= chunk
        n += 1
    if n >= 50:
        # The split loop's own bound was silent: hitting it means the order did NOT fully place.
        _log.error("place_market symbol=%s hit the 50-chunk bound with %s remaining -- "
                   "order is INCOMPLETE", symbol, remaining)
    _log.info("place_market DONE symbol=%s chunks=%s order_id=%s",
              symbol, n, (last or {}).get("orderId") if isinstance(last, dict) else None)
    return dict(last) if isinstance(last, dict) else {"raw": last}


def place_post_only(symbol: str, side: str, qty: float, price: float) -> dict[str, Any]:
    """Post-only LIMIT order (timeInForce=GTX) -- guaranteed MAKER (rejected if it would cross)."""
    res = _signed("/fapi/v1/order", {
        "symbol": symbol, "side": side, "type": "LIMIT", "timeInForce": "GTX",
        "quantity": qty, "price": price,
    }, method="POST")
    _log.info("place_post_only symbol=%s side=%s qty=%s price=%s order_id=%s",
              symbol, side, qty, price,
              res.get("orderId") if isinstance(res, dict) else None)
    return dict(res) if isinstance(res, dict) else {"raw": res}


def place_stop_market(symbol: str, side: str, qty: float, stop_price: float) -> dict[str, Any]:
    """Reduce-only STOP_MARKET -- the venue-side protective stop required by spec section 3
    (survives total host death; every live position must carry one at the ruin-line distance)."""
    res = _signed("/fapi/v1/order", {
        "symbol": symbol, "side": side, "type": "STOP_MARKET", "quantity": qty,
        "stopPrice": stop_price, "reduceOnly": "true",
    }, method="POST")
    # The venue-side protective stop is the rail that survives host death: its placement is the
    # single most important line in any live-session log.
    _log.info("place_stop_market (RUIN RAIL) symbol=%s side=%s qty=%s stop=%s order_id=%s",
              symbol, side, qty, stop_price,
              res.get("orderId") if isinstance(res, dict) else None)
    return dict(res) if isinstance(res, dict) else {"raw": res}


def open_orders(symbol: str | None = None) -> list[dict[str, Any]]:
    """Resting (unfilled) orders, optionally for one symbol."""
    params = {"symbol": symbol} if symbol else {}
    res = _signed("/fapi/v1/openOrders", params)
    return list(res) if isinstance(res, list) else []


def cancel_all(symbol: str) -> dict[str, Any]:
    """Cancel all open orders for a symbol (clears stale maker quotes before re-pegging).

    CAUTION (R0071c, 2026-07-31): this also cancels a resting protective STOP_MARKET. Paths
    that must preserve the venue-side stop (the maker-pair fallback) cancel their own orders
    individually via cancel_order instead."""
    res = _signed("/fapi/v1/allOpenOrders", {"symbol": symbol}, method="DELETE")
    return dict(res) if isinstance(res, dict) else {"raw": res}


def cancel_order(symbol: str, order_id: int) -> dict[str, Any]:
    """Cancel ONE order by id -- surgical, so a maker-quote cleanup can never take the
    protective stop down with it."""
    res = _signed("/fapi/v1/order", {"symbol": symbol, "orderId": order_id}, method="DELETE")
    _log.info("cancel_order symbol=%s order_id=%s", symbol, order_id)
    return dict(res) if isinstance(res, dict) else {"raw": res}


def flatten_all() -> list[dict[str, Any]]:
    """Emergency: market-close every open position."""
    out = []
    for sym, amt in positions().items():
        side = "SELL" if amt > 0 else "BUY"
        out.append(place_market(sym, side, abs(amt)))
    return out

```

### libs/execution/binance_spot_live.py
```python
"""Binance SPOT LIVE connector -- the spot leg of cash-and-carry, real money, no alpha here.

Mirrors libs/execution/binance_spot_testnet.py's interface EXACTLY; pinned to the LIVE spot
base URL. Same arming contract as libs/execution/binance_live.py (the futures leg) -- see that
module's docstring for the full rationale. Every signed call is inert unless
``data/secrets/binance_live_spot.json`` exists, ``data/LIVE_ENABLE`` exists, and
``data/LIVE_VPS_VERIFIED`` exists. Keyfile-only credentials (no env var path -- see futures
module docstring for why). No withdrawal/transfer/sub-account function exists in this module and
never will; the capability surface is order-placement, order-cancellation, and reads only.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import time
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

_BASE = "https://api.binance.com"                # PINNED live spot -- verified against docs
_KEYFILE = Path("data/secrets/binance_live_spot.json")
_ENABLE_FLAG = Path("data/LIVE_ENABLE")
_VPS_MARKER = Path("data/LIVE_VPS_VERIFIED")


def _creds() -> tuple[str | None, str | None]:
    if not _KEYFILE.exists():
        return None, None
    try:
        d = json.loads(_KEYFILE.read_text("utf-8"))
        return d.get("key"), d.get("secret")
    except (json.JSONDecodeError, OSError):
        return None, None


def has_keys() -> bool:
    k, s = _creds()
    return bool(k and s)


def is_armed() -> tuple[bool, str]:
    checks = {
        "keys_present": has_keys(),
        "live_enable_flag": _ENABLE_FLAG.exists(),
        "vps_verified": _VPS_MARKER.exists(),
    }
    return all(checks.values()), ", ".join(f"{k}={v}" for k, v in checks.items())


def _get(path: str, params: dict[str, Any] | None = None) -> Any:
    url = f"{_BASE}{path}"
    if params:
        url += "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": "quant-live-spot/1.0"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read())


def _signed(path: str, params: dict[str, Any], *, method: str = "GET") -> Any:
    armed, why = is_armed()
    if not armed:
        raise RuntimeError(f"binance_spot_live not armed ({why}) -- refusing signed call {path}")
    key, secret = _creds()
    assert key is not None and secret is not None  # armed (checked above) => creds present
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
    s = f"{step:.10f}".rstrip("0")
    return len(s.split(".")[1]) if "." in s and step < 1 else 0


def exchange_filters() -> dict[str, dict[str, float]]:
    """Per-symbol step, min qty, base precision, price tick + precision (for valid spot sizing).

    ``min_notional`` is the venue's minimum ORDER VALUE -- a gate quantity filters cannot express:
    an order can satisfy stepSize AND minQty and still be rejected for being worth too little.
    Binance publishes it as NOTIONAL (current) or MIN_NOTIONAL (legacy); 0.0 means this symbol
    has no published minimum, so callers must keep their own conservative floor for that case.

    PARITY WARNING (2026-07-31): this is one of FOUR near-duplicate exchangeInfo parsers --
    binance_spot_live, binance_spot_testnet, binance_live, binance_testnet. The money path
    (run_cashcarry_executor, run_stranded_recovery) imports the TESTNET modules, so a field added
    only here reaches NOTHING. tests/execution/test_filter_parity.py pins the spot pair's key set
    so that divergence fails a test instead of shipping inert. Futures publishes the same filter
    under the key ``notional``, NOT ``minNotional`` -- copying this line there yields 0.0 for
    every symbol."""
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
    """Resting book liquidity: total QUOTE (USDT) value within ``pct`` of the touch on one side."""
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
    """Venue-truth average fill price of OUR trades since ``start_ms``. None if unarmed/no fills."""
    try:
        trades = _signed("/api/v3/myTrades", {"symbol": symbol, "startTime": start_ms,
                                              "limit": 100})
        fills = [t for t in trades if bool(t.get("isBuyer")) == (side == "BUY")]
        base = sum(float(t["qty"]) for t in fills)
        quote = sum(float(t["quoteQty"]) for t in fills)
        return quote / base if base > 0 and quote > 0 else None
    except Exception:
        return None


def balances() -> dict[str, float]:
    """Free balance per asset (non-zero only)."""
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


def place_market(symbol: str, side: str, qty: float) -> dict[str, Any]:
    """Spot MARKET order. side in {BUY, SELL}; qty in base asset units (e.g. BTC)."""
    res = _signed("/api/v3/order", {
        "symbol": symbol, "side": side, "type": "MARKET", "quantity": qty,
    }, method="POST")
    return dict(res) if isinstance(res, dict) else {"raw": res}


def place_market_quote(symbol: str, side: str, quote_usdt: float) -> dict[str, Any]:
    """Spot MARKET order sized in QUOTE (USDT) -- convenient for buying $X of an asset."""
    res = _signed("/api/v3/order", {
        "symbol": symbol, "side": side, "type": "MARKET", "quoteOrderQty": quote_usdt,
    }, method="POST")
    return dict(res) if isinstance(res, dict) else {"raw": res}


def place_post_only(symbol: str, side: str, qty: float, price: float) -> dict[str, Any]:
    """Post-only spot LIMIT order (type=LIMIT_MAKER) -- guaranteed MAKER."""
    res = _signed("/api/v3/order", {
        "symbol": symbol, "side": side, "type": "LIMIT_MAKER", "quantity": qty, "price": price,
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

### libs/execution/binance_spot_testnet.py
```python
"""Binance SPOT TESTNET connector -- the spot leg of cash-and-carry (paper money).

Pinned to the spot testnet (testnet.binance.vision); cannot touch a live account. Signed REST
(HMAC-SHA256), keys from env (BINANCE_SPOT_TESTNET_KEY / BINANCE_SPOT_TESTNET_SECRET) or a local
untracked file -- NEVER in code. Pairs with libs/execution/binance_testnet.py (the futures leg) so
the long-spot / short-perp cash-and-carry can be simulated end-to-end on paper. No alpha logic here.
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

_BASE = "https://testnet.binance.vision"        # PINNED spot testnet -- never live
_KEY_ENV = "BINANCE_SPOT_TESTNET_KEY"
_SECRET_ENV = "BINANCE_SPOT_TESTNET_SECRET"
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

    ``min_notional`` is the venue's minimum ORDER VALUE -- a gate quantity filters cannot express.
    THIS is the module the money path actually imports (run_cashcarry_executor,
    run_stranded_recovery), so the field has to live here to reach anything; adding it only to
    binance_spot_live ships it inert. run_stranded_recovery previously fell back to a hardcoded
    10.0 for every symbol because the key did not exist -- against the desk's own measured venue
    truth (data/capacity_floor.json: spot_min 5.0) that silently refused recoverable balances in
    the $5-10 band under the label "below venue min notional". 0.0 = no published minimum, which
    is why that caller keeps a conservative floor for the 0.0 case rather than treating it as
    "no minimum". Key parity with binance_spot_live is pinned by
    tests/execution/test_filter_parity.py."""
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


def place_market(symbol: str, side: str, qty: float) -> dict[str, Any]:
    """Spot MARKET order. side in {BUY, SELL}; qty in base asset units (e.g. BTC)."""
    res = _signed("/api/v3/order", {
        "symbol": symbol, "side": side, "type": "MARKET", "quantity": qty,
    }, method="POST")
    return dict(res) if isinstance(res, dict) else {"raw": res}


def place_market_quote(symbol: str, side: str, quote_usdt: float) -> dict[str, Any]:
    """Spot MARKET order sized in QUOTE (USDT) -- convenient for buying $X of an asset."""
    res = _signed("/api/v3/order", {
        "symbol": symbol, "side": side, "type": "MARKET", "quoteOrderQty": quote_usdt,
    }, method="POST")
    return dict(res) if isinstance(res, dict) else {"raw": res}


def place_post_only(symbol: str, side: str, qty: float, price: float) -> dict[str, Any]:
    """Post-only spot LIMIT order (type=LIMIT_MAKER) -- guaranteed MAKER (rejected if it crosses).

    Mirrors the futures GTX behaviour so the carry can be executed maker-first on both legs.
    """
    res = _signed("/api/v3/order", {
        "symbol": symbol, "side": side, "type": "LIMIT_MAKER", "quantity": qty, "price": price,
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

### libs/execution/binance_testnet.py
```python
"""Binance USD-M Futures TESTNET connector -- execution hands only, no alpha.

Hardened, testnet-ONLY REST client: signed requests (HMAC-SHA256), keys read from the environment
(BINANCE_TESTNET_KEY / BINANCE_TESTNET_SECRET) -- NEVER committed to code. The base URL is pinned to
the testnet, so this cannot touch a live account. It only does what the brain tells it: read account
/ positions / filters, set leverage, place market orders, flatten. No signal or sizing logic lives
here. Without keys it still serves public market data and reports ``has_keys() == False``.
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

_BASE = "https://testnet.binancefuture.com"   # PINNED testnet -- never live
_KEY_ENV = "BINANCE_TESTNET_KEY"
_SECRET_ENV = "BINANCE_TESTNET_SECRET"
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
    """Per-symbol step size, min qty, and price/qty precision (for valid order sizing)."""
    info = _get("/fapi/v1/exchangeInfo")
    out: dict[str, dict[str, float]] = {}
    for s in info.get("symbols", []):
        f = {flt["filterType"]: flt for flt in s.get("filters", [])}
        lot = f.get("LOT_SIZE", {})
        pf = f.get("PRICE_FILTER", {})
        out[s["symbol"]] = {
            "step": float(lot.get("stepSize", 0.001)), "min_qty": float(lot.get("minQty", 0.0)),
            "qty_prec": int(s.get("quantityPrecision", 3)),
            "tick": float(pf.get("tickSize", 0.01)), "price_prec": int(s.get("pricePrecision", 2)),
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


_STABLE_COLLATERAL = ("USDT", "USDC", "FDUSD", "TUSD", "BUSD", "DAI")


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
        pass                                  # unknown cap -> behave exactly as before
    _MKT_MAX_CACHE[symbol] = cap
    return cap


def place_market(symbol: str, side: str, qty: float,
                 reduce_only: bool = False) -> dict[str, Any]:
    """Market order, SPLIT to respect the venue MARKET_LOT_SIZE cap.

    ``reduce_only=True`` makes the order arithmetically incapable of crossing zero into the
    opposite position -- mandatory on any cover/close leg. Defaults False so opens are unchanged.
    """
    cap = _market_max_qty(symbol)
    remaining, last, n = float(qty), None, 0
    while remaining > 0 and n < 50:
        chunk = min(cap, remaining) if cap != float("inf") else remaining
        params = {"symbol": symbol, "side": side, "type": "MARKET", "quantity": chunk}
        if reduce_only:
            params["reduceOnly"] = "true"
        last = _signed("/fapi/v1/order", params, method="POST")
        remaining -= chunk
        n += 1
    return dict(last) if isinstance(last, dict) else {"raw": last}


def place_post_only(symbol: str, side: str, qty: float, price: float) -> dict[str, Any]:
    """Post-only LIMIT order (timeInForce=GTX) -- guaranteed MAKER (rejected if it would cross).

    Pays the maker fee (~half the taker fee on Binance futures) instead of crossing the spread.
    Returns the order dict (status NEW if it rests, or an error if it would have crossed).
    """
    res = _signed("/fapi/v1/order", {
        "symbol": symbol, "side": side, "type": "LIMIT", "timeInForce": "GTX",
        "quantity": qty, "price": price,
    }, method="POST")
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
    """Emergency: market-close every open position."""
    out = []
    for sym, amt in positions().items():
        side = "SELL" if amt > 0 else "BUY"
        out.append(place_market(sym, side, abs(amt)))
    return out

```

### libs/ops/derisk_ladder.py
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

### libs/portfolio/risk_parity.py
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

### libs/risk/__init__.py
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

### libs/risk/capital_events.py
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
    """
    h = history()
    return float(h[-1]["start_equity_after"]) if h else float(state_start_equity)

```

### libs/risk/config.py
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

### libs/risk/correlation.py
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

### libs/risk/crisis.py
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

### libs/risk/drawdown.py
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

### libs/risk/dynamic_leverage.py
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
        ror = risk_of_ruin(returns, float(lev), threshold=drawdown_ruin)
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

### libs/risk/edge_gate.py
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

### libs/risk/errors.py
```python
"""Risk-layer exceptions."""

from __future__ import annotations

from libs.core.errors import QuantPlatformError


class RiskError(QuantPlatformError):
    """Invalid risk inputs or configuration."""


class RiskGateError(RiskError):
    """The risk gate could not run; per fail-closed policy this means *do not trade*."""

```

### libs/risk/factor_caps.py
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

### libs/risk/gate.py
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

### libs/risk/growth_leverage.py
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
            "risk_of_ruin": round(risk_of_ruin(returns, lev), 4),
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

### libs/risk/heat.py
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

### libs/risk/instruments.py
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

### libs/risk/kelly.py
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

### libs/risk/kelly_shrink.py
```python
"""Estimation-error-shrunk Kelly -- the fraction that actually maximizes E[log wealth].

Full Kelly is growth-optimal only when the edge is known EXACTLY. Ours is estimated from
N forward days, so it carries standard error -- and Kelly's penalty for betting above the
true optimum is worse than for betting the same distance below it (growth falls off a
cliff on the overbet side). Betting naive full Kelly on an estimated edge therefore has
LOWER expected compounding than the shrunk fraction. This is not conservatism: it is the
max-E[log] bet under parameter uncertainty (2026-07-12 external-review upgrade, replacing
the discrete time-ladder rungs of policy v3).

    shrink = S^2 / (S^2 + SE(S)^2)        (Bayesian shrinkage toward zero edge)
    fraction_of_kelly = shrink            (ramps continuously as evidence accumulates)

with SE from Lo (2002): SE(S_daily) = sqrt((1 + S_daily^2 / 2) / N), annualized. Pooling
shadow + live forward days grows N daily, so size compounds with evidence automatically:
no rungs, no calendar, nothing to skip. Reference behaviour (S_ann ~ 2.3): ~0.17x Kelly
at day 15, ~0.36x at 40, ~0.55x at 90, ~0.71x at 180. A day-40 fast-track (needs S ~ 5)
starts at ~0.73x -- strong evidence self-authorizes size, weak evidence cannot.
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

### libs/risk/overlays.py
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

### libs/risk/preservation.py
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

### libs/risk/risk_budget.py
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

### libs/risk/risk_controls.py
```python
"""Growth-POSITIVE risk controls -- limits sized at the ruin boundary, never from fear.

Design axiom: geometric growth is g ~= mu - sigma^2/2, so cutting the LEFT TAIL cuts sigma^2 faster
than mu -> it RAISES compounding. Every control here is derived from the ruin / max-DD math
(growth_leverage + the dynamic-leverage ruin cap), NOT from arbitrary caution. A limit that
binds tighter than the ruin boundary would be false conservatism (a bug that lowers log-wealth); a
limit AT the boundary only ever fires when NOT firing would risk ruin -- which destroys all future
compounding. So in normal operation these controls do nothing, and in a tail event they preserve the
ability to keep compounding.

Three controls, in increasing severity:
  * exposure guard  -- gross notional may not exceed the ruin-boundary leverage x equity (a backstop
                       against a sizing bug; never binds while we deploy below the ruin cap).
  * DD circuit break -- above a stress drawdown, PAUSE new opens (keep existing carries earning
                       funding; never realises a loss). Kelly-consistent: uncertainty up -> less.
  * ruin kill-switch -- only a catastrophic equity loss (>= drawdown_ruin) forces a full flatten.
                       For a delta-neutral book this means an exchange/basis catastrophe -> survive.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class RiskDecision:
    action: str                       # "ok" | "pause_opens" | "flatten"
    reasons: list[str]
    max_notional: float               # ruin-boundary gross exposure (opens capped to this)
    dd_from_peak: float               # <= 0
    dd_from_start: float              # <= 0

    def to_dict(self) -> dict[str, Any]:
        return {"action": self.action, "reasons": self.reasons,
                "max_notional": round(self.max_notional, 2),
                "dd_from_peak_pct": round(self.dd_from_peak * 100, 2),
                "dd_from_start_pct": round(self.dd_from_start * 100, 2)}


def evaluate(
    equity: float,
    start_equity: float,
    peak_equity: float,
    gross_notional: float,
    *,
    ruin_cap_lev: float,              # ruin-boundary leverage (from dynamic_leverage)
    drawdown_ruin: float = 0.35,      # equity loss treated as ruin -> flatten (survival)
    dd_pause: float = 0.15,           # drawdown that pauses NEW opens (does NOT flatten)
) -> RiskDecision:
    """Evaluate the book against growth-positive, ruin-boundary limits. Pure function."""
    eq = max(0.0, float(equity))
    start = max(1e-9, float(start_equity))
    peak = max(start, float(peak_equity), eq)
    dd_peak = eq / peak - 1.0
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

    return RiskDecision(action, reasons or ["within growth-optimal risk bounds"],
                        max_notional, dd_peak, dd_start)

```

### libs/risk/scaling.py
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

### libs/risk/sizing.py
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

### libs/risk/stress.py
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

### libs/risk/tail.py
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

### libs/risk/vol_target.py
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

### libs/stage14_5/tail_risk.py
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

### scripts/carry_viability.py
```python
"""CARRY VIABILITY -- P0.2: replace cost DEFAULTS with MEASURED costs, per symbol.

THE QUESTION THIS SETTLES. execution_bottleneck.py found the whole book failing the entry gate and
posed two readings: (a) the gate is right and the carry has no edge, or (b) 39.5bps is too harsh
for symbols that are cheap but merely unmeasured. That was answerable and now is answered.

IT IS (a), AND MORE SPECIFICALLY IT IS A UNIVERSE-SELECTION DEFECT.

    COOKIEUSDT -- the desk's MOST-TRADED symbol, 21 opens, largest position in the book --
    has a MEASURED pair round-trip of 130.47 bps. It earns ~6.7 bps over a 24h hold.
    That is a ~19x loss on every rotation, and it was never a default: it was measured.

MY OWN ERROR, DISCLOSED. execution_bottleneck.py reported COOKIEUSDT as using the DEFAULT cost. It
does not. My _rt_bps helper looked for flat keys ("rt_bps"/"round_trip_bps") while the cost model
nests as symbols[SYM]["pair"]["500"]["pair_roundtrip_bps"]. The LIVE EXECUTOR parses it correctly;
only my audit script was wrong. I reported the desk as blind when the desk could see -- the exact
failure the measurement doctrine exists to prevent, committed by the tool auditing for it. This
script uses the executor's lookup verbatim so the audit and the live gate can never diverge again.

THE STRUCTURAL FINDING: funding-first universe selection is self-defeating. High funding is the
compensation for illiquidity, so ranking candidates by funding systematically selects the names
with catastrophic round-trips. The carry is not broken -- the universe is.

Read-only. Touches no orders, no config. Run from repo root.
"""
from __future__ import annotations

import json
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
COST = ROOT / "data/cost_model.json"
POS = ROOT / "data/cashcarry_positions.json"
TRADES = ROOT / "data/cashcarry_trades.json"
OUT = ROOT / "data/carry_viability.json"

DEFAULT_RT_BPS = 39.5
PERIODS_24H = 3.0
TYPICAL_FUNDING_BPS = 3.0     # generous upper end of ordinary per-8h funding


def rt_bps(cm, sym) -> tuple[float, bool]:
    """VERBATIM the executor's lookup (run_cashcarry_executor.py::_rt_bps)."""
    try:
        v = cm["symbols"][sym]["pair"]["500"].get("pair_roundtrip_bps")
        return (float(v), True) if v is not None else (DEFAULT_RT_BPS, False)
    except (KeyError, TypeError, ValueError):
        return (DEFAULT_RT_BPS, False)


def main() -> None:
    cm = json.loads(COST.read_text("utf-8"))
    syms = cm.get("symbols", {})
    print("=== CARRY VIABILITY -- measured costs, executor lookup verbatim ===\n")

    rows = []
    for s in syms:
        v, meas = rt_bps(cm, s)
        if meas:
            rows.append({"symbol": s, "rt_bps": round(v, 2),
                         "need_bps_per_period": round(v / PERIODS_24H, 2),
                         "viable": v / PERIODS_24H <= TYPICAL_FUNDING_BPS})
    rows.sort(key=lambda r: r["rt_bps"])
    viable = [r for r in rows if r["viable"]]
    print(f"  BREAK-EVEN FUNDING NEEDED at a {PERIODS_24H:g}-period (24h) hold:\n")
    print(f"  {'symbol':<14}{'rt_bps':>9}{'need/period':>13}   verdict")
    for r in rows:
        v = ("VIABLE" if r["viable"] else
             "MARGINAL" if r["need_bps_per_period"] <= 8 else "NEVER at normal funding")
        print(f"  {r['symbol']:<14}{r['rt_bps']:>9.2f}{r['need_bps_per_period']:>12.2f}bp   {v}")
    print(f"\n  {len(viable)}/{len(rows)} measured symbols can clear the gate at "
          f"<= {TYPICAL_FUNDING_BPS:g}bp funding.")
    print("  THE STRATEGY IS VIABLE. The universe is not.")

    # ------------------------------------------------ what the desk actually traded
    t = json.loads(TRADES.read_text("utf-8"))
    tr = t if isinstance(t, list) else t.get("trades", [])
    cnt = Counter(r["symbol"] for r in tr if r.get("event") == "open")
    vset = {r["symbol"] for r in viable}
    print("\n  WHAT THE DESK ACTUALLY TRADED (top 16 by opens):\n")
    print(f"  {'symbol':<14}{'opens':>6}{'rt_bps':>10}   status")
    n_unmeas = n_bad = tot = 0
    for s, n in cnt.most_common(16):
        v, meas = rt_bps(cm, s)
        tot += 1
        if not meas:
            st, n_unmeas = "UNMEASURED (prior: unmeasured = illiquid = expensive)", n_unmeas + 1
        elif s in vset:
            st = "viable"
        else:
            st, n_bad = "MEASURED AND UNVIABLE", n_bad + 1
        print(f"  {s:<14}{n:>6}{v:>10.2f}   {st}")
    print(f"\n  {n_unmeas}/{tot} most-traded names have NO measured cost; {n_bad}/{tot} are "
          f"measured AND unviable.")

    pos = json.loads(POS.read_text("utf-8")).get("positions", {})
    print("\n  OPEN BOOK:\n")
    for s, p in pos.items():
        f = float(p.get("funding", 0.0))
        earns = f * 1e4 * PERIODS_24H
        v, meas = rt_bps(cm, s)
        print(f"  {s:<14} earns {earns:>5.1f}bp   needs {v:>7.2f}bp   "
              f"{'MEASURED' if meas else 'default':<9} {'PASS' if earns > v else 'FAIL'}")

    print("\n=== CONCLUSION ===")
    print("  The entry gate is CORRECT and must not be relaxed. It is refusing names that are")
    print("  measurably unprofitable, COOKIEUSDT most of all at 130.47bps against ~6.7bps of")
    print("  funding. The desk halting new opens is the gate doing its job.")
    print("\n  THE FIX IS UNIVERSE SELECTION, NOT THE GATE. Candidates are ranked by FUNDING, but")
    print("  funding is the COMPENSATION FOR ILLIQUIDITY -- so funding-first ranking selects for")
    print("  exactly the round-trips that destroy the carry. Rank by NET (funding x periods minus")
    print("  measured round-trip) and restrict candidates to measured-viable names. On the numbers")
    print("  above that leaves 16 liquid symbols, several of which (BTC 0.02, ETH 0.11, BNB 0.35,")
    print("  XRP 1.81) clear the bar with room to spare at ordinary funding.")
    print("\n  This also RETIRES my own earlier flip-flop on universe choice. I argued for majors,")
    print("  then for micro-caps 'because that is where the funding is', then back. The measured")
    print("  answer: micro-cap funding is real and is smaller than micro-cap costs.")

    OUT.write_text(json.dumps({"updated": datetime.now(tz=UTC).isoformat(),
                               "measured": rows, "n_viable": len(viable), "n_measured": len(rows),
                               "traded_top": dict(cnt.most_common(16)),
                               "unmeasured_traded": n_unmeas}, indent=1), "utf-8")
    print(f"\n  -> {OUT}")


if __name__ == "__main__":
    main()

```

### scripts/execution_bottleneck.py
```python
"""EXECUTION BOTTLENECK -- apply the BOTTLENECK FIRST + REALITY FEEDBACK principles to live money.

THE DIRECTIVE SAYS THE MARKET IS THE FINAL JUDGE, so this reads the live book and the live trade
log rather than any research artifact. It answers three questions the desk cannot currently answer,
in descending order of how much money they are worth:

 Q1 WOULD THE CURRENT BOOK PASS THE CURRENT ENTRY GATE?
    The P0 fix (_DEFAULT_RT_BPS 4.5 -> 39.5) raised the bar ~8.8x this morning. Every open
    position was opened under the OLD bar. If the book fails the new gate, the desk is holding
    positions its own risk logic would now refuse to open -- and that is a decision, not a metric.

 Q2 HOW OFTEN DOES THE MAKER PATH FAIL?
    The trade log records spot_mode/fut_mode per leg. 'taker_fallback' means the patient-maker
    order did not fill and the executor crossed the spread. Every fallback converts a rebate into
    a spread payment. This is the single largest controllable cost on a delta-neutral carry and
    NOTHING on this desk currently counts it.

 Q3 WHAT IS ACTUALLY MEASURABLE, AND WHAT IS NOT?
    The 7.75x cost/funding figure is IMPLIED from a NAV residual. It has never been ATTRIBUTED to
    a leg, a symbol, or an execution mode. Under the measurement doctrine adopted today, an
    implied aggregate is not a measurement -- you cannot act on it because it does not say what
    to change. This script reports precisely which fields are missing to close that gap.

Read-only. Touches no orders, no keys, no config. Run from repo root.
"""
from __future__ import annotations

import json
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TRADES = ROOT / "data/cashcarry_trades.json"
POS = ROOT / "data/cashcarry_positions.json"
COST = ROOT / "data/cost_model.json"
CFG = ROOT / "data/cashcarry_config.json"
OUT = ROOT / "data/execution_bottleneck.json"

DEFAULT_RT_BPS = 39.5      # matches the live executor after the P0 fix
FUNDING_PERIOD_H = 8


def _load(p, d=None):
    try:
        return json.loads(p.read_text("utf-8"))
    except Exception:  # blind-except intentional (BLE001)
        return d


def _rt_bps(cm, sym) -> tuple[float, bool]:
    """Return (round-trip bps, measured?) mirroring the executor's lookup semantics."""
    if not isinstance(cm, dict):
        return DEFAULT_RT_BPS, False
    for key in ("pairs", "symbols", "round_trip_bps", "rt_bps"):
        d = cm.get(key)
        if isinstance(d, dict) and sym in d:
            v = d[sym]
            v = v.get("rt_bps", v.get("round_trip_bps")) if isinstance(v, dict) else v
            try:
                return float(v), True
            except (TypeError, ValueError):
                pass
    v = cm.get(sym)
    if isinstance(v, dict):
        for k in ("rt_bps", "round_trip_bps", "total_bps"):
            if k in v:
                try:
                    return float(v[k]), True
                except (TypeError, ValueError):
                    pass
    return DEFAULT_RT_BPS, False


def main() -> None:
    trades = _load(TRADES, []) or []
    if isinstance(trades, dict):
        trades = trades.get("trades", [])
    pos = _load(POS, {}) or {}
    if isinstance(pos, dict) and "positions" in pos:
        pos = pos["positions"]
    cm = _load(COST, {}) or {}
    cfg = _load(CFG, {}) or {}
    hold_h = float(cfg.get("min_hold_h", cfg.get("MIN_HOLD_H", 24)))

    print("=== EXECUTION BOTTLENECK -- live book vs live gate ===")
    print("    REALITY FEEDBACK: no backtest or model score overrides contradictory live evidence\n")

    # ---------------------------------------------------------------- Q1
    print("Q1  WOULD THE OPEN BOOK PASS THE CURRENT ENTRY GATE?")
    print(f"    gate: funding_bps_per_period x periods > round_trip_bps   "
          f"(hold {hold_h:.0f}h = {hold_h/FUNDING_PERIOD_H:.0f} periods)\n")
    periods = max(1.0, hold_h / FUNDING_PERIOD_H)
    rows, n_fail = [], 0
    print(f"    {'symbol':<16}{'funding/period':>15}{'earns':>9}{'needs':>9}{'cost src':>11}  verdict")
    for sym, p in (pos.items() if isinstance(pos, dict) else []):
        f = float(p.get("funding", 0.0))
        earns = f * 1e4 * periods
        rt, measured = _rt_bps(cm, sym)
        ok = earns > rt
        n_fail += (not ok)
        print(f"    {sym:<16}{f*1e4:>13.2f}bp{earns:>8.1f}{rt:>9.1f}"
              f"{'measured' if measured else 'DEFAULT':>11}  {'PASS' if ok else 'FAIL'}")
        rows.append({"symbol": sym, "funding_bps": round(f * 1e4, 3),
                     "earns_bps": round(earns, 2), "needs_bps": round(rt, 2),
                     "cost_measured": measured, "passes_gate": ok})
    if rows:
        print(f"\n    {n_fail}/{len(rows)} open positions FAIL the gate that is now live.")
        if n_fail == len(rows):
            print("    THE ENTIRE BOOK WOULD BE REFUSED BY THE DESK'S OWN CURRENT ENTRY LOGIC.")
            print("    Two readings, and they demand different actions:")
            print("      (a) the gate is right -> this carry has no edge at prevailing funding,")
            print("          and the book should be wound down rather than rolled;")
            print("      (b) 39.5bps (p90 of MEASURED round-trips) is too harsh for symbols whose")
            print("          true cost is cheap but simply unmeasured.")
            print("    (b) is TESTABLE and costs nothing: measure these symbols' round-trips.")
            print("    Until then the desk is holding positions it would refuse to open, which is")
            print("    an unowned position -- the gate protects entry but nothing re-tests carry.")

    # ---------------------------------------------------------------- Q2
    print(f"\nQ2  HOW OFTEN DOES THE PATIENT-MAKER PATH FAIL?  ({len(trades)} logged events)\n")
    spot = Counter(t.get("spot_mode") for t in trades if t.get("spot_mode"))
    fut = Counter(t.get("fut_mode") for t in trades if t.get("fut_mode"))
    ev = Counter(t.get("event") for t in trades)
    print(f"    events: {dict(ev)}")
    for label, c in (("SPOT leg", spot), ("FUT  leg", fut)):
        tot = sum(c.values())
        if not tot:
            continue
        fb = sum(v for k, v in c.items() if "taker" in str(k))
        print(f"    {label}: {dict(c)}")
        print(f"              taker_fallback {fb}/{tot} = {fb/tot*100:.1f}% of legs crossed "
              f"the spread")
    tot_s, fb_s = sum(spot.values()), sum(v for k, v in spot.items() if "taker" in str(k))
    if tot_s and fb_s / tot_s > 0.25:
        print("\n    THIS IS THE CONTROLLABLE COST. A delta-neutral carry earns a few bps per")
        print("    period; paying the spread on a large fraction of legs is the difference between")
        print("    a positive and a negative strategy. _MAKER=True is already the default -- the")
        print("    leak is that the fallback fires and nothing prices it.")

    # ---------------------------------------------------------------- Q3
    print("\nQ3  WHAT IS MISSING TO ATTRIBUTE COST?  (measurement doctrine, adopted today)\n")
    sample = trades[-1] if trades else {}
    have = set(sample)
    need = {"fill_price": "actual average fill price of the leg",
            "mid_at_decision": "mid quote when the order was sent -> slippage = fill - mid",
            "fee_usd": "fee actually charged (maker rebate vs taker fee)",
            "attempts": "how many maker re-quotes before fallback",
            "wait_s": "seconds waited before crossing"}
    print(f"    trade record currently has: {sorted(have)}")
    missing = [k for k in need if k not in have]
    for k in missing:
        print(f"    MISSING  {k:<18} {need[k]}")
    print("\n    Without these, cost is only ever an IMPLIED RESIDUAL (the 7.75x figure), and an")
    print("    implied residual cannot tell you WHICH leg, WHICH symbol or WHICH mode to change.")
    print("    Adding them is ~15 lines of additive logging in run_cashcarry_executor.py and is")
    print("    the highest-ROI engineering task on this desk: it converts the single largest")
    print("    measured loss (costs 7.75x funding) from unattributed to actionable.")
    print("\n    OPPORTUNITY COST: this replaces further research infrastructure. The research")
    print("    layer has 447 enumerated constructions awaiting test; the money layer is losing")
    print("    to costs on a signal already CONFIRMED (funding persistence IC +0.432). Fixing")
    print("    what converts a confirmed signal into negative PnL dominates finding a second one.")

    OUT.write_text(json.dumps({"updated": datetime.now(tz=UTC).isoformat(),
                               "hold_h": hold_h, "periods": periods,
                               "positions": rows, "n_fail_gate": n_fail,
                               "spot_modes": dict(spot), "fut_modes": dict(fut),
                               "events": dict(ev), "missing_fields": missing}, indent=1), "utf-8")
    print(f"\n  -> {OUT}")


if __name__ == "__main__":
    main()

```

### scripts/flatten_cookie.py
```python
"""PRINCIPAL-APPROVED: flatten the inverted COOKIEUSDT futures LONG. reduceOnly, nothing else.

INCIDENT: COOKIEUSDT futures held +916,772 (LONG) where the carry requires -183,140 (SHORT).
Unrealized -$482.19 -- essentially the desk's entire loss -- with free margin down to $110.23 and
a liquidation price of 0.00516943. Cause: futures cover orders are not reduceOnly, so close/topup
retries bought through zero and flipped the short into a growing long.

SCOPE, DELIBERATELY MINIMAL AND APPROVED AS SUCH:
  * COOKIEUSDT FUTURES ONLY. Spot COOKIE (183,029) untouched. 1000CAT and MOVE shorts are
    CORRECTLY hedged and are not touched. TST is untouched.
  * reduceOnly=true so this order can only ever REDUCE toward zero. It is arithmetically
    incapable of repeating the bug it is cleaning up -- if the position is already flat or
    smaller than expected, the venue rejects or trims rather than opening a short.
  * Quantity read LIVE from positionRisk at execution time, never from a desk-written file.
    The desk's own state file is what was wrong here; trusting it would be the same error again.

Verifies before and after. Aborts if the position is not a long, or is not COOKIEUSDT.
"""
from __future__ import annotations

import sys
import time

sys.path.insert(0, ".")
import scripts.run_deadman_switch as D

SYM = "COOKIEUSDT"


def _market_max_qty(sym: str) -> float:
    """Venue's MARKET_LOT_SIZE cap, read live. Falls back to a conservative 100k."""
    try:
        info = D._req(f"{D._FUT_BASE}/fapi/v1/exchangeInfo")
        for s in info["symbols"]:
            if s["symbol"] == sym:
                for f in s["filters"]:
                    if f["filterType"] == "MARKET_LOT_SIZE":
                        return float(f["maxQty"])
    except Exception:  # blind-except intentional (BLE001)
        pass
    return 100_000.0


def pos_amt(creds) -> float:
    for p in D._signed(D._FUT_BASE, "/fapi/v2/positionRisk", creds):
        if p.get("symbol") == SYM:
            return float(p.get("positionAmt", 0.0))
    return 0.0


def main() -> None:
    creds = D._creds(D._FUT_KEYS)
    if not creds:
        raise SystemExit("no futures credentials -- aborting")

    before = pos_amt(creds)
    print(f"BEFORE  {SYM} positionAmt = {before:+,.1f}")
    if before == 0:
        print("  already flat -- nothing to do")
        return
    if before < 0:
        raise SystemExit(f"position is SHORT ({before:+,.1f}) -- that is the CORRECT direction "
                         f"for a carry. Refusing to touch it; this script only unwinds the "
                         f"inverted LONG it was written for.")

    # MARKET_LOT_SIZE maxQty = 150,000 on COOKIEUSDT. A single 916,772 order is rejected -4005
    # "Quantity greater than max quantity" -- AND THAT IS THE ROOT CAUSE OF THE INCIDENT ITSELF:
    # the executor's oversized market orders were rejected, _mkt_or_limit fell back to RESTING
    # post-only limits, and repeated cycles accumulated fills that walked the short through zero
    # into a long. Chunking is therefore not a workaround, it is the correct behaviour.
    max_qty = _market_max_qty(SYM)
    print(f"  MARKET_LOT_SIZE maxQty = {max_qty:,.0f} -> chunking")
    remaining = abs(before)
    n = 0
    while remaining > 0 and n < 20:
        cur = pos_amt(creds)
        if cur <= 0:
            print(f"  position reached {cur:+,.1f} -- stopping (reduceOnly cannot go short)")
            break
        chunk = min(max_qty, abs(cur))
        n += 1
        print(f"  [{n}] reduceOnly MARKET SELL {chunk:,.0f}  (position now {cur:+,.1f})")
        try:
            D._signed(D._FUT_BASE, "/fapi/v1/order", creds,
                      {"symbol": SYM, "side": "SELL", "type": "MARKET",
                       "quantity": chunk, "reduceOnly": "true"}, method="POST")
        except Exception as e:  # blind-except intentional (BLE001)
            print(f"      CHUNK FAILED: {e!r} -- stopping. Position left at {pos_amt(creds):+,.1f}")
            print("      Not retrying blindly; blind retries created this incident.")
            break
        time.sleep(2)
        remaining = abs(pos_amt(creds))

    time.sleep(3)
    after = pos_amt(creds)
    print(f"AFTER   {SYM} positionAmt = {after:+,.1f}")
    acct = D._signed(D._FUT_BASE, "/fapi/v2/account", creds)
    print(f"  margin_balance={float(acct['totalMarginBalance']):.2f}  "
          f"available={float(acct['availableBalance']):.2f}  "
          f"unrealized={float(acct['totalUnrealizedProfit']):.2f}")
    print("\n  REMAINING venue futures positions:")
    for p in D._signed(D._FUT_BASE, "/fapi/v2/positionRisk", creds):
        a = float(p.get("positionAmt", 0.0))
        if a:
            print(f"    {p['symbol']:<14} {a:+15,.1f}  unrl {float(p['unRealizedProfit']):+9.2f}")
    print("\n  Spot COOKIE is deliberately still held; only the inverted futures leg was unwound.")


if __name__ == "__main__":
    main()

```

### scripts/hedge_integrity.py
```python
"""HEDGE INTEGRITY RAIL -- the detector that did not exist during incident #6.

On 2026-07-27 COOKIEUSDT futures sat at +916,772 LONG where the carry required -183,140 SHORT,
carrying -$482 with free margin at $110. It then recurred on 1000CATUSDT at +1,138,985. Both ran
UNDETECTED. Nothing on this desk asserted the one invariant that defines a cash-and-carry:

    for every tracked carry:  venue futures position MUST be SHORT and MUST match -spot_qty

The reconciler heals a MISSING short. It has no concept of an INVERTED one, so a long where a
short belongs looked like "no short to fix" and persisted while the loss accumulated.

This is a rail, not a subsystem: one invariant, three failure classes, no model and no judgement.

    INVERTED    futures position is LONG where a SHORT is required  -> the incident-#6 signature,
                the desk is DOUBLE LONG rather than delta-neutral
    MISSING     no futures position at all                          -> naked spot, directional
    MISMATCHED  short exists but size is off by more than tolerance  -> partial hedge

VENUE GROUND TRUTH ONLY. It compares the desk's tracked state AGAINST the exchange and trusts the
exchange. The desk's own state file said "4 delta-neutral carries" throughout the incident -- a
check built on that file would have reported everything healthy.

Read-only: places no orders, cancels nothing, and cannot move money.
"""
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, ".")
import scripts.run_deadman_switch as D

ROOT = Path(__file__).resolve().parent.parent
STATE = ROOT / "data/cashcarry_positions.json"
OUT = ROOT / "data/hedge_integrity.json"
PAGE = ROOT / "docs/PRINCIPAL_ACTION.md"
TOL = 0.02          # 2% size tolerance; below this is venue rounding, not a broken hedge


def main() -> None:
    creds = D._creds(D._FUT_KEYS)
    if not creds:
        raise SystemExit("no futures credentials")
    venue = {p["symbol"]: float(p.get("positionAmt", 0.0))
             for p in D._signed(D._FUT_BASE, "/fapi/v2/positionRisk", creds)}
    tracked = json.loads(STATE.read_text("utf-8")).get("positions", {})

    print("=== HEDGE INTEGRITY -- venue ground truth vs tracked carries ===")
    print("    invariant: every tracked carry's futures leg is SHORT and matches -spot_qty\n")
    viol = []
    for sym, p in tracked.items():
        spot_q = float(p.get("spot_qty", 0.0))
        want = -abs(spot_q)
        got = venue.get(sym, 0.0)
        if got > 0:
            cls = "INVERTED"
        elif got == 0:
            cls = "MISSING"
        elif abs(got - want) > abs(want) * TOL:
            cls = "MISMATCHED"
        else:
            cls = "OK"
        flag = "" if cls == "OK" else "  <== VIOLATION"
        print(f"  {sym:<14} spot {spot_q:>14,.0f}  want {want:>14,.0f}  got {got:>14,.0f}  "
              f"{cls}{flag}")
        if cls != "OK":
            viol.append({"symbol": sym, "class": cls, "spot_qty": spot_q,
                         "expected_fut": want, "actual_fut": got})

    # An UNTRACKED venue short is the mirror failure: exposure the desk does not know it has.
    for sym, amt in venue.items():
        if amt and sym not in tracked:
            print(f"  {sym:<14} {'(untracked)':>14}  {'':>14}  {amt:>14,.0f}  ORPHAN  <== VIOLATION")
            viol.append({"symbol": sym, "class": "ORPHAN", "spot_qty": 0.0,
                         "expected_fut": 0.0, "actual_fut": amt})

    if not tracked and not any(venue.values()):
        print("  book is FLAT -- no tracked carries, no venue positions. Invariant holds trivially.")

    inv = [v for v in viol if v["class"] == "INVERTED"]
    print(f"\n  {len(viol)} violation(s); {len(inv)} INVERTED")
    if inv:
        print("  INVERTED is the incident-#6 signature: the desk is DOUBLE LONG, not delta-neutral.")
        print("  It cannot be healed by the close path -- a close BUYS futures to cover a short,")
        print("  which on a long only makes it larger. It requires a reduceOnly SELL, chunked to")
        print("  the venue MARKET_LOT_SIZE cap.")
        try:
            with PAGE.open("a", encoding="utf-8") as fh:
                fh.write(f"\n## {datetime.now(tz=UTC).isoformat()} HEDGE INVERTED\n")
                for v in inv:
                    fh.write(f"- {v['symbol']}: futures {v['actual_fut']:+,.0f} where "
                             f"{v['expected_fut']:+,.0f} required (incident-#6 signature)\n")
            print(f"  -> paged {PAGE}")
        except OSError:
            pass

    OUT.write_text(json.dumps({"updated": datetime.now(tz=UTC).isoformat(),
                               "violations": viol, "n_violations": len(viol),
                               "n_inverted": len(inv),
                               "ok": not viol}, indent=1), "utf-8")
    print(f"  -> {OUT}")
    sys.exit(1 if inv else 0)


if __name__ == "__main__":
    main()

```

### scripts/measurement_gate.py
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
            d = datetime.fromisoformat(s) if fmt is None else datetime.strptime(s, fmt)
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
    results = {}
    for p in sorted((ROOT / "data").glob("*.jsonl")):
        rows = _load(p)
        if len(rows) < 25:
            # Reported, never omitted -- same reason as data_vitals. An absent row cannot be
            # distinguished from a passing row.
            results[p.name] = {"rows_sampled": len(rows), "kind": "UNKNOWN",
                               "verdict": "TOO_SMALL", "fails": [], "warns":
                               [f"only {len(rows)} rows -- below the 25-row scoring floor"],
                               "timestamps": {}, "correctness": {}, "features": {}, "repro": {}}
            continue
        tkey = next((k for k in _TIME_KEYS if k in rows[0]), None)
        kind = classify_kind(rows, tkey, p.name)
        f1, w1, m1 = check_timestamps(rows, kind)
        f2, w2, m2 = check_correctness(rows, kind)
        f3, w3, m3 = check_features(rows)
        f4, w4, m4 = check_reproducibility(p)
        fails = f1 + f2 + f3 + f4 + cost_f
        warns = w1 + w2 + w3 + w4
        results[p.name] = {
            "rows_sampled": len(rows), "kind": kind,
            "verdict": "FAILED" if fails else "VERIFIED",
            "fails": fails, "warns": warns,
            "timestamps": m1, "correctness": m2, "features": m3, "repro": m4}
    return {"updated": datetime.now(tz=UTC).isoformat(), "cost_realism": {
        "fails": cost_f, "warns": cost_w, **cost_m}, "datasets": results}


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

### scripts/run_alerts.py
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
                       "trade_class_bleeding": 24 * 3600, "auth_broken": 12 * 3600}
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
            if cmd == "REARM":
                out = subprocess.run(
                    [sys.executable, "scripts/run_live_guard.py", "--rearm",
                     "principal-ntfy"], capture_output=True, text=True, timeout=60,
                ).stdout.strip()
                kill = Path("data/CASHCARRY_KILL")
                lifted = ""
                if kill.exists() and kill.read_text("utf-8").startswith("live_guard freeze"):
                    kill.unlink()   # completes the human's order; other writers' kills stay
                    lifted = "; freeze lifted"
                with contextlib.suppress(Exception):
                    _push(topic, "Quant desk: REARM received",
                          f"{out or 'ladder re-armed'}{lifted} -- book resumes next tick")
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
    # check nothing paged on the file's age. Content `generated` over mtime (deploys lie fresh).
    try:
        lg = json.loads(Path("data/live_guard.json").read_text("utf-8"))
        lg_at = datetime.fromisoformat(str(lg.get("generated", "1970-01-01T00:00:00+00:00")))
        lg_age = (datetime.now(tz=UTC) - lg_at).total_seconds()
    except (OSError, ValueError, TypeError):
        lg_age = None
        out.append(("live_guard_missing", "data/live_guard.json missing/unreadable -- size "
                    "governor and stage tripwires UNEVALUATED; executor fail-opens to full "
                    "size; start: .venv/bin/python scripts/run_live_guard.py"))
    if lg_age is not None and lg_age > 900:
        out.append(("live_guard_dead", f"live guard stale {lg_age/60:.0f}min (cadence 5min) -- "
                    "executor fail-opens to FULL SIZE + takers and stage demotion is "
                    "unevaluated; a dead guard cannot write its own KILL file; restart: "
                    ".venv/bin/python scripts/run_live_guard.py"))
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
        pass
    print(f"alerts: {sent} page(s) sent "
          f"({datetime.now(tz=UTC).isoformat()[:16]}Z)")


if __name__ == "__main__":
    main()

```

### scripts/run_cashcarry_executor.py
```python
"""Cash-and-carry EXECUTOR -- the delta-neutral funding-harvest book, executed on the testnets.

Long spot (spot testnet) + short perp (futures testnet) on the top POSITIVE-funding perps that trade
on BOTH venues. Persistent loop with a BANDED rebalance (carry compounds -> hold, don't churn): it
only opens new carries and closes names that leave the positive-funding set, so turnover (and fees)
stay minimal. Tracks a real position state + marks the book, writes a heartbeat + kill-switch. This
is now the PROFIT-LEAD book; the perp L/S book drops to shadow. PAPER (testnet) -- it builds the
forward track record the edge-gate sizes leverage on. dry-run DEFAULT; --live to send paper orders.

    python scripts/run_cashcarry_executor.py --live --top 5 --capital 2000 --interval 600
"""

from __future__ import annotations

import argparse
import contextlib
import json
import os
import random
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from libs.data.crypto_source import current_funding
from libs.execution import binance_spot_testnet as spot
from libs.execution import binance_testnet as fut
from libs.execution import execution_tape
from libs.execution.carry_accounting import (
    attribute_non_funding,
    carry_bleed_report,
    dedup_basis,
    derive_spot_realized,
    read_income,
)
from libs.ops.fresh import read_fresh  # L1.44: decision-path reads carry freshness contracts
from libs.ops.lawful import guard as _law_guard  # L1.42: no act exempt
from libs.risk import capital_events, risk_controls

_STATE = Path("data/cashcarry_positions.json")
_TRADES = Path("data/cashcarry_trades.json")     # real open/close log -> winrate + trade history
_LEV_TGT = Path("data/leverage_target.json")     # dynamic-leverage sizing (honoured when validated)
_CONFIG = Path("data/cashcarry_config.json")     # LIVE-tunable params (top/hold_top/capital)
_WEB = Path("web/cashcarry_live.json")
_HB = Path("data/cashcarry_exec_heartbeat")
_KILL = Path("data/CASHCARRY_KILL")
_ERR = Path("data/cashcarry_error.log")          # visible cycle-error log (not swallowed to null)
_LAST_ARCHIVE = Path("data/.last_metrics_archive")  # once-per-day data-flywheel marker
_HB_TICK = 60                                    # heartbeat cadence (decoupled from rebalance work)
_MAKER = True                                     # maker-first execution (set via --no-maker)
_RSP_TOL = 5.0                                    # $ drift before realized_spot_pnl self-heals
_FLAT_EPS = 1e-9                                  # |qty| at or below this counts as flat
_DEPTH_MULT = 5.0                                # book depth within 1% of touch must cover an open
# ORPHAN-COVER BOUNDS (gap #37, panel consensus 8+/12 on the 2026-07-19 audit): the
# orphan cover is a live-ammo market-order path that previously fired on FIRST sight of
# any untracked position, unbounded. A transient REST desync or partial-fill lag then
# market-covers into a thin book, and repeated covers during a venue outage could
# themselves breach the ruin constraint. Two bounds, both safe-direction only:
_ORPHAN_CONFIRM = 2        # reconcile passes an orphan must PERSIST before live ammo
_ORPHAN_MAX_USD = 1500.0   # max notional force-covered per symbol per pass
# CASCADE GUARD (gap #37): the confirm-window and per-pass cap bound a SINGLE cover, but
# `seen.pop()` reset the symbol immediately, so a persistent desync (exactly what a venue
# outage looks like) could re-fire live ammo every pass with no rate limit. A cooldown
# bounds repeats per symbol; the hourly circuit stops the whole path when MANY symbols go
# orphan at once -- that pattern means "the venue is sick", not "we have N real orphans".
_ORPHAN_COOLDOWN_S = 1800.0   # per-symbol quiet period after a cover
_ORPHAN_MAX_PER_HOUR = 3      # covers/hour across all symbols before the path halts
                                                 # this many times, on BOTH legs, or the name is
                                                 # skipped (2026-07-13 thin-book incident)


def _daily_data_tasks() -> None:
    """Keep the DATA FLYWHEEL turning once per UTC day off the always-on cash-carry loop.

    Archives OI/LS/taker metrics, market breadth, and Deribit surface -- these grow the 40-day
    forward clocks that gate the derivative alpha column. Spawns the heavy research chain detached
    so a slow research run can never block trading. Process-isolated so any data hiccup is safe."""
    today = datetime.now(tz=UTC).date().isoformat()
    if _LAST_ARCHIVE.exists() and _LAST_ARCHIVE.read_text("utf-8").strip() == today:
        return
    root = Path(__file__).resolve().parent.parent
    for script in ("scripts/collect_binance_metrics.py", "scripts/collect_market_breadth.py",
                   "scripts/collect_deribit_surface.py", "scripts/classify_regime.py",
                   "scripts/run_regime_engine.py"):
        try:
            subprocess.run([sys.executable, script], cwd=root, timeout=600,
                           capture_output=True, text=True, check=False)
        except Exception as e:
            print(f"[daily-task] {script}: {e!r}"[:140])
    try:
        subprocess.Popen([sys.executable, "scripts/run_daily_research.py"], cwd=root,
                         stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL)
    except Exception as e:
        print(f"[daily-task] run_daily_research spawn: {e!r}"[:140])
    _LAST_ARCHIVE.write_text(today, "utf-8")


def _book_snapshot() -> dict[str, Any]:
    """Current book (state positions + live prices), NO orders -- for frequent marking."""
    state = json.loads(_STATE.read_text("utf-8")) if _STATE.exists() else {}
    return {"state": state, "pos": state.get("positions", {}), "actions": [], "cands": [],
            "spot_px": spot.prices(), "fut_px": fut.mark_prices()}


def _round(qty: float, step: float, prec: int) -> float:
    return round(round(qty / step) * step, prec) if step > 0 else round(qty, prec)


def _log_trade(rec: dict[str, Any]) -> None:
    """Append a real open/close event -> cashcarry_trades.json (source of winrate + history).

    The rolling file stays capped at 500 (every existing consumer depends on its shape), but the
    same record ALSO goes to the append-only execution tape -- the cap was destroying ~27 fills/day
    of own-fill history, which is both the data moat and the evidence Gate 0's ">=4 weeks of live
    fills" is measured against. The tape append is exception-safe and never blocks the executor.
    """
    try:
        log = json.loads(_TRADES.read_text("utf-8")) if _TRADES.exists() else []
    except (OSError, json.JSONDecodeError):
        log = []
    log.append(rec)
    _TRADES.parent.mkdir(parents=True, exist_ok=True)
    _TRADES.write_text(json.dumps(log[-500:], indent=2, default=str), "utf-8")
    execution_tape.append(rec)


def _held_hours(opened: object) -> float:
    try:
        dt = datetime.fromisoformat(str(opened))
        return round((datetime.now(tz=UTC) - dt).total_seconds() / 3600, 2)
    except (ValueError, TypeError):
        return 0.0


def _dynamic_capital(default: float) -> float:
    """Deployed notional from the dynamic-leverage optimizer -- but only once it has confidence.

    Until forward validation gives confidence>0 the optimizer's number is unproven, so we keep the
    operator's --capital. When validated, deployed size = growth-optimal notional (constitution:
    leverage is a continuously optimized control variable, sized to proven edge)."""
    # QUARANTINED (2026-07-18 deep audit): the leverage optimizer's confidence pipeline is
    # contaminated (gap #14, unroot-caused). Incident #2 (07-16) was it sizing UP to $40k on
    # bad confidence; the 07-18 audit found the SAME bad confidence (conf 0.92) sizing the book
    # DOWN to ~$1,250 (25% deployed) -- $3,250 of authorized capital idled, a real
    # under-deployment (the growth_defect alert was a TRUE positive). The 07-16 clamp only
    # capped the UPSIDE ("may de-risk below operator capital"), letting the contaminated signal
    # under-deploy. Until the confidence pipeline is root-caused AND a >=30-live-day re-enable
    # gate ships, the optimizer is IGNORED IN BOTH DIRECTIONS -- the executor deploys the
    # operator's authorized --capital. (Re-enabling honest dynamic sizing = the gap #14 duty.)
    return _compounded_capital(default)


# --- COMPOUNDING RE-ANCHOR (principal 2026-07-23; Gate-0 lever, built early on purpose) ------
# DEFECT IT FIXES: the executor deployed a FROZEN notional, so realised gains never enlarged the
# base. That is ARITHMETIC growth -- the same dollar profit on a growing account is a shrinking
# percentage, so measured CAGR decays toward zero. For a desk whose supreme objective is max
# E[log(wealth)], a frozen base disconnects the objective's own transmission mechanism.
#
# WHY THIS IS SAFE (each hazard named and closed):
#  * The QUARANTINED OPTIMIZER is never consulted (gap #14 stands). This reads only REALISED,
#    hash-chain-attested PnL -- never a confidence score. Incident #2 was optimizer confidence
#    sizing the book to $40k; that path stays dead.
#  * NEVER raw equity. Testnet equity marks ~$10.8k because of faucet bags, so anchoring to it
#    would balloon the book. Only realized_spot_pnl from the NAV attestation is used.
#  * FAIL-SAFE INERT: if the stage machine cannot PROVE S1+ (live), the operator capital is
#    returned unchanged. Missing/unreadable/S0 all read as NOT live. So this is fully built and
#    testable today and begins compounding on day 1 of Gate 0 -- ready since the beginning.
#  * CLAMPED BOTH WAYS: never below 0.5x nor above 4.0x authorised capital, so a corrupt
#    realised figure cannot run the book away in either direction.
_COMPOUND_FRACTION = 1.0      # redeploy 100% of realised gains into the base (log-optimal)
_COMPOUND_MAX_FACTOR = 4.0    # never exceed 4x authorised capital without a new authorisation
_COMPOUND_MIN_FACTOR = 0.5    # de-risk floor: losses shrink the base, but only to half
_STAGE = Path("data/stage_state.json")
_NAV = Path("data/nav_attestation.jsonl")


def _is_live() -> bool:
    """True ONLY when the stage machine proves S1+ (Gate 0 passed). Any error, missing file or
    S0/paper reads as NOT live, so compounding stays off. Fail-safe by construction.

    L1.44 state-kind contract: stage_state.json is valid-until-changed, so its own age proves
    nothing -- the read is trustworthy iff its GUARDIAN (run_live_guard, the tripwire/demotion
    evaluator) is alive. The decision below is unchanged either way (fail-safe already); the
    contract makes a dead guardian visible as a consumed-state event instead of silence."""
    try:
        fr = read_fresh(_STAGE, max_age_h=1.0, kind="state",
                        guardian="data/live_guard.json",
                        caller="run_cashcarry_executor._is_live")
        return str((fr.data or {}).get("stage", "S0")).upper() in ("S1", "S2")
    except Exception:
        return False


def _realised_pnl() -> float:
    """Cumulative REALISED PnL from the hash-chained NAV attestation (never marks or equity)."""
    try:
        lines = [ln for ln in _NAV.read_text("utf-8").splitlines() if ln.strip()]
        return float(json.loads(lines[-1]).get("realized_spot_pnl", 0.0))
    except Exception:
        return 0.0


def _compounded_capital(default: float) -> float:
    """Operator capital grown by REALISED PnL, hard-clamped, inert until live."""
    if not _is_live():
        return default                                   # pre-Gate-0: frozen base, unchanged
    grown = default + _realised_pnl() * _COMPOUND_FRACTION
    lo, hi = default * _COMPOUND_MIN_FACTOR, default * _COMPOUND_MAX_FACTOR
    return float(min(max(grown, lo), hi))


def _alloc(cands: list[tuple[str, float]], capital: float,
           *, cap_frac: float = 0.35) -> dict[str, float]:
    """Per-name notional weighted by funding rate (harvest more where it pays), capped so no single
    carry dominates (capacity / concentration guard). The cap is HARD: when it cannot be met
    (n * cap_frac < 1, i.e. fewer than 3 names) the remainder stays in cash rather than piling
    into one name -- relaxing it is how 2026-07-13 put $4.3k of a $4.5k book into a single
    micro-cap (NOMUSDT) and fired the dead-man rail."""
    n = len(cands)
    if n == 0:
        return {}
    fs = [max(0.0, f) for _, f in cands]
    tot = sum(fs)
    w = [x / tot for x in fs] if tot > 0 else [1.0 / n] * n
    # WATER-FILL: cap each weight at cap_frac and redistribute the excess to the uncapped names,
    # iterating to a fixed point. A plain min()+renormalise does NOT hold the cap (excess leaks
    # back into the max name); this does. When no under-cap name can absorb the excess, the
    # excess is simply NOT deployed (never scaled back up -- see docstring).
    for _ in range(n):
        over = [i for i, x in enumerate(w) if x > cap_frac + 1e-12]
        if not over:
            break
        excess = sum(w[i] - cap_frac for i in over)
        for i in over:
            w[i] = cap_frac
        pool = sum(w[i] for i in range(n) if w[i] < cap_frac - 1e-12)
        if pool <= 0:
            break                                        # nowhere to redistribute -> stays in cash
        for i in range(n):
            if w[i] < cap_frac - 1e-12:
                w[i] += excess * w[i] / pool
    s = sum(w)
    if s > 1.0 + 1e-9:                                   # defensive: weights may only scale DOWN
        w = [x / s for x in w]
    return {cands[i][0]: capital * w[i] for i in range(n)}


def _topup_plan(pos: dict[str, dict[str, Any]], capital: float, *, cap_frac: float = 0.35,
                min_frac: float = 0.02, min_usd: float = 20.0) -> dict[str, float]:
    """Extra notional to bring each HELD carry UP toward its funding-weighted share of the FULL
    capital -- never DOWN (closes are the target-set's job; this only fills idle authorized
    capital that held carries would otherwise leave frozen from a low-free-capital open window).

    Pure (no venue calls) so the risk-path sizing is unit-testable. Invariants that keep this in
    the SAFE direction only (operator-directed 2026-07-19, gap #32):
      * aggregate adds never exceed the free headroom (capital - deployed) -> the book can never
        lever past the operator's --capital (the quarantined leverage optimizer stays ignored);
      * each name is held under cap_frac*capital -> the 2026-07-13 single-name concentration rail;
      * only MATERIAL shortfalls (>= max(min_frac*capital, min_usd)) top up -> a book already near
        target does not churn on rounding noise.
    """
    if not pos:
        return {}
    funded = [(sym, max(float(p.get("funding", 0.0)), 0.0)) for sym, p in pos.items()]
    tgt = _alloc(funded, capital, cap_frac=cap_frac)
    deployed = sum(float(p["spot_qty"]) * float(p["spot_cost"]) for p in pos.values())
    room = max(0.0, capital - deployed)
    floor = max(min_frac * capital, min_usd)
    plan: dict[str, float] = {}
    for sym in sorted(pos, key=lambda k: max(float(pos[k].get("funding", 0.0)), 0.0), reverse=True):
        if room <= 0.0:
            break
        cur = float(pos[sym]["spot_qty"]) * float(pos[sym]["spot_cost"])
        add = min(min(tgt.get(sym, 0.0), cap_frac * capital) - cur, room)
        if add < floor:
            continue
        plan[sym] = add
        room -= add
    return plan


# --- CHURN GUARD (gap #42, 2026-07-22) -----------------------------------------------------
# Trade audit over 250 closes: carries held <8h (38% of all trades) LOSE money as a class
# (<2h -5.0 bps, 2-8h -4.1 bps) while 8-24h earns +6.5 and >24h earns +16.9. 42% of closes
# re-opened the SAME symbol within 24h -- a provably wasted round-trip. Realized drag -8.1%/yr.
# Cause is funding-sign flicker, not bad entries (funding at open is identical fast vs slow).
# ECONOMICS: adverse funding costs ~1 bp per 8h; a round-trip costs ~4.5 bps (measured by
# run_cost_model.py). So holding up to 24h risks <=3 bps to save 4.5 -- strictly dominant.
# Beyond ~32h the accumulated adverse funding would exceed the saved round-trip, so 24h is the
# profit-maximising floor, not an arbitrary constant.
_MIN_HOLD_H = 24.0        # rotation-driven closes blocked below this age
_FUNDING_PANIC = -0.0005  # per-8h rate: worse than this, holding costs more than the round-trip


def _churn_guard(held_h: float, funding: float, rail_forced: bool) -> bool:
    """True => HOLD the carry (block a rotation-driven close).

    Rails ALWAYS win (basis-stop / ADL / cooldown / risk-flatten / reconcile close instantly);
    strongly-negative funding escapes the floor; otherwise a carry younger than the minimum
    hold is kept so it can earn back the round-trip it already paid."""
    if rail_forced:
        return False
    if funding <= _FUNDING_PANIC:
        return False
    return held_h < _MIN_HOLD_H


# --- ENTRY GATE (gap #43, 2026-07-22) ------------------------------------------------------
# Trade audit over 250 closes, bucketed by funding rate AT OPEN:
#   0.000100 (Binance BASELINE, no real premium): n=50  net -$176.24  (-92.7 bps)  <-- disaster
#   0.000100-0.000144                           : n=50  net  +$14.71  (+12.8 bps)
#   0.000100-0.000144                           : n=50  net  +$60.87  (+42.7 bps)
#   0.000144-0.000219                           : n=50  net  -$22.43   (-7.5 bps)
#   0.000219-0.001517                           : n=50  net +$179.31  (+45.9 bps)
# `_ranked()` accepted ANY funding > 0, so the desk opened carries on symbols sitting at the
# exchange DEFAULT rate -- i.e. names with no funding premium whatsoever -- and paid a full
# round-trip for them. Those 50 trades ate ~80% of the desk's gross profit.
#
# _MIN_FUNDING DELETED 2026-07-31 (R0057). The absolute per-8h floor (0.00015, derived from the
# desk-MEDIAN round-trip when the cost gate still used the median default) became redundant the
# day the cost gate went per-symbol with a p90 fail-closed default: unmeasured names now need
# funding > 39.5/3e4 = 0.000132 anyway, and thin proven losers are on the bleed denylist. The
# floor's only remaining effect, measured 2026-07-30: vetoing the 4 net-positive MAJORS (tight
# measured books whose funding capture beats their own round-trip below 0.00015) -- 245/245
# candidates rejected with the floor on. Protection lives in the per-symbol check below.
# FAIL CLOSED (2026-07-27). Default was 4.5 = the desk MEDIAN, which sits at only the 43rd
# percentile of measured round-trips (median 5.7, p75 21.3, p90 39.5, max 130.5 across 30
# symbols). 'Unmeasured' is NOT a random subset: a symbol is missing from the cost model
# BECAUSE it is too illiquid to measure -- i.e. it is the expensive tail. Assigning it the
# median was a fail-open on exactly the worst books (this file already records NOM -149bps,
# KNC -211bps). p90 makes the unmeasured case pessimistic: a symbol must prove it is cheap
# (by being measured) before it can clear the bar. Raising it can only REFUSE NEW OPENS --
# _entry_gate is never applied to the hold/target set, so this cannot force-close anything.
_DEFAULT_RT_BPS = 39.5          # p90 of measured pair round-trip; pessimistic when unmeasured
_COST_MODEL = Path("data/cost_model.json")
_FORENSICS = Path("web/trade_forensics.json")
# STRUCTURAL-BLEED DENYLIST (2026-07-23). run_trade_forensics.py already PROVED which
# names lose money as a class (NOMUSDT -149bps/5 trades, PEOPLEUSDT -73/5, BNBUSDT
# -67/11, GTCUSDT -29/10) but nothing consumed its output, so the desk kept re-opening
# them. The funding+cost gate does not catch these: their funding clears the floor and
# their modelled cost looks fine -- the loss is realised execution, visible only in the
# closed-trade record. Evidence-driven, self-updating, and strictly RESTRICTIVE:
# NEW OPENS ONLY, so it can never force-close a held carry (that would be churn).
_BLEED_BPS = -20.0        # realised net bps at which a symbol is structurally bleeding
_BLEED_MIN_N = 5          # minimum closed trades before the verdict is trusted


def _structurally_bleeding(sym: str) -> bool:
    """True => this symbol has PROVEN it loses money for the desk; block new opens.

    L1.44 contract (48h: forensics is produced daily): deny-direction data never loosens with
    age, so a STALE denylist STILL DENIES -- the fence owns chasing the dead producer. Only an
    unreadable file falls back to allow, exactly as before, and that read is now recorded
    instead of silent."""
    fr = read_fresh(_FORENSICS, max_age_h=48.0,
                    caller="run_cashcarry_executor._structurally_bleeding")
    rows = fr.data.get("worst_symbols") if isinstance(fr.data, dict) else None
    if not isinstance(rows, list):
        return False
    for r in rows:
        try:
            if (r.get("symbol") == sym and int(r.get("n", 0)) >= _BLEED_MIN_N
                    and float(r.get("bps", 0.0)) <= _BLEED_BPS):
                return True
        except (TypeError, ValueError):
            continue
    return False


def _rt_bps(sym: str) -> float:
    """This symbol's MEASURED round-trip cost, else the desk median. Self-improving: as the
    recorder accrues the traded names, the gate automatically tightens on expensive books
    (NOMUSDT realised -149 bps, KNCUSDT -211 bps -- thin books where slippage dominates)."""
    fr = read_fresh(_COST_MODEL, max_age_h=48.0, caller="run_cashcarry_executor._rt_bps")
    try:
        m = fr.data["symbols"][sym]["pair"]["500"]
        v = m.get("pair_roundtrip_bps")
        if v is None:
            return _DEFAULT_RT_BPS
        # L1.44 stale degrade: a stale measured cost may only TIGHTEN this gate, never loosen
        # it. max() keeps a proven-expensive name (KNC -211bps) expensive when the model
        # freezes, and stops a stale "cheap" reading from admitting opens the current book
        # would refuse. New opens only, as ever -- this can never force-close a held carry.
        return float(v) if fr.fresh else max(float(v), _DEFAULT_RT_BPS)
    except (KeyError, TypeError, ValueError):
        return _DEFAULT_RT_BPS


def _entry_gate(sym: str, funding: float, min_hold_h: float = _MIN_HOLD_H) -> bool:
    """True => ALLOW opening this carry.

    Requires expected funding capture over the MINIMUM HOLD to beat this symbol's measured
    round-trip. Applied to NEW OPENS ONLY -- never to the hold/target set, so raising the bar
    can never force-close existing carries (that would itself be a churn event)."""
    if _structurally_bleeding(sym):
        return False                      # proven money-loser: never re-open it
    periods = max(1.0, min_hold_h / 8.0)
    return funding * 1e4 * periods > _rt_bps(sym)


def _mkt_or_limit(conn: Any, sym: str, side: str, qty: float) -> str:
    """Close/hedge ``qty``: MARKET first, LIMIT fallback. On a thin/broken book a market order is
    rejected by the venue PERCENT_PRICE filter (-4131) -- and a market-only cover can then NEVER
    clear the leg, so the hedge stays broken forever (this is the gap that stranded orphans on
    illiquid perps). Fall back to a post-only limit at the near touch (bid for BUY / ask for SELL):
    accepted within the price band, rests as maker, fills when liquidity returns. Cancels any stale
    order on the symbol first so repeated reconcile ticks don't stack duplicates. Returns
    'mkt' | 'limit' | '' (nothing placed)."""
    if qty <= 0:
        return ""
    try:
        conn.place_market(sym, side, qty)
        return "mkt"
    except Exception:
        pass                                          # thin book / PERCENT_PRICE -> limit fallback
    with _safe():
        conn.cancel_all(sym)                          # clear stale fallbacks (no dup stacking)
    try:
        bid, ask = conn.book_ticker().get(sym, (0.0, 0.0))
        px = bid if side == "BUY" else ask
        if px and px > 0:
            conn.place_post_only(sym, side, qty, px)
            return "limit"
    except Exception:
        pass
    return ""


def _reconcile(pos: dict[str, dict[str, Any]], *, dry: bool,
               cooldown: dict[str, float] | None = None,
               fail_counts: dict[str, int] | None = None,
               orphan_seen: dict[str, int] | None = None,
               orphan_cool: dict[str, float] | None = None,
               flatten_only: bool = False) -> list[str]:
    """Heal hedge drift every cycle -- survival is priority #1. Two invariants restored:

    ``flatten_only`` (2026-07-28 incident): when the book is under a KILL or risk-flatten order
    its target state is FLAT, so the two branches here that ADD exposure -- re-shorting a missing
    futures leg and re-buying a sold spot leg -- are rebuilding exactly what the close path is
    tearing down in the same tick. That loop round-tripped the entire book through market orders
    every 600s and never terminated. Branches that move TOWARD flat (orphan cover, trim-excess,
    adl-flatten) stay live: a flatten order never means "stop reducing risk".

      * ORPHAN futures short (a short with no tracked carry) -> cover it (close to flat).
      * UNHEDGED tracked carry (state expects a short but the futures leg is missing/short) ->
        re-short the deficit so spot_long and perp_short match again (delta-neutral).
        EXCEPTION (2026-07-12 external review): if the VENUE force-closed the short
        (liquidation/ADL during a squeeze), re-shorting walks back into the squeeze that
        just took the leg -- flatten the SPOT leg instead and stand down 24h.

    Idempotent: does nothing when the book is already consistent, and self-corrects the moment a
    transient venue outage (that caused the drift) clears. A failed leg is swallowed, retried next
    cycle -- but NOT silently: `fail_counts` (persisted in executor state, keyed by symbol) tracks
    consecutive `_mkt_or_limit` failures, and 3+ in a row surfaces a RECONCILE-FAIL action line +
    a visible error-log write (2026-07-17 gap-register #16 fix -- a broken pair silently sat
    unhedged for 75 minutes on 2026-07-16 because a rejected re-hedge order returned '' and logged
    nothing)."""
    if dry or not fut.has_keys():
        return []
    try:
        actual = fut.positions()
    except Exception:
        return []                                          # venue read down -> try again next cycle
    acts: list[str] = []
    fails = fail_counts if fail_counts is not None else {}

    def _do(conn: Any, sym: str, side: str, qty: float) -> str:
        how = _mkt_or_limit(conn, sym, side, qty)
        if how:
            fails.pop(sym, None)
        else:
            n = fails.get(sym, 0) + 1
            fails[sym] = n
            if n >= 3:
                with _safe():
                    _ERR.write_text(f"{datetime.now(tz=UTC).isoformat()} reconcile fail x{n} "
                                    f"{sym}: both market and post-only limit rejected\n")
                acts.append(f"RECONCILE-FAIL {sym} x{n} (both market+limit rejected, see "
                           f"{_ERR})")
        return how

    tracked = set(pos)
    seen = orphan_seen if orphan_seen is not None else {}
    live_orphans = {s2 for s2, q2 in actual.items()
                    if s2 not in tracked and abs(float(q2)) > 0}
    for s2 in list(seen):                                  # a transient desync disappears -> forget
        if s2 not in live_orphans:
            seen.pop(s2, None)
    _cool = orphan_cool if orphan_cool is not None else {}
    _now = time.time()
    _recent = sum(1 for t0 in _cool.values() if _now - t0 < 3600.0)
    for sym in sorted(live_orphans):
        if _recent >= _ORPHAN_MAX_PER_HOUR:        # cascade -> venue is sick, stand down
            acts.append(f"orphan-CIRCUIT: {_recent} covers in the last hour "
                        f">= {_ORPHAN_MAX_PER_HOUR} -- halting live-ammo cover, page")
            break
        if _now - _cool.get(sym, 0.0) < _ORPHAN_COOLDOWN_S:
            acts.append(f"orphan {sym} in cover-cooldown "
                        f"({(_ORPHAN_COOLDOWN_S - (_now - _cool[sym])) / 60:.0f}m left)")
            continue
        qty = float(actual[sym])
        n = seen.get(sym, 0) + 1
        seen[sym] = n
        if n < _ORPHAN_CONFIRM:                            # must PERSIST before firing live ammo
            acts.append(f"orphan {sym} seen {n}/{_ORPHAN_CONFIRM} -- awaiting confirmation "
                        f"(transient desync is not covered)")
            continue
        cover = abs(qty)
        px = 0.0
        with _safe():                    # priced only when a confirmed orphan exists
            px = float(fut.mark_prices().get(sym, 0.0) or 0.0)
        if px > 0 and cover * px > _ORPHAN_MAX_USD:        # bound each pass; remainder next pass
            acts.append(f"orphan {sym} ${cover * px:.0f} exceeds ${_ORPHAN_MAX_USD:.0f}/pass cap "
                        f"-- covering a capped slice")
            cover = _ORPHAN_MAX_USD / px
        how = _do(fut, sym, "BUY" if qty < 0 else "SELL", cover)
        if how:
            acts.append(f"cover-orphan {sym} {round(cover, 8)} ({how})")
            seen.pop(sym, None)
            _cool[sym] = _now                      # start the quiet period
            _recent += 1
    dead: list[str] = []
    forced: dict[str, int] = {}
    if any(abs(float(actual.get(s, 0.0))) + 1e-9 < abs(float(p["perp_qty"])) * 0.98
           for s, p in pos.items()):                       # query venue only when a leg is short
        with _safe():
            forced = fut.force_orders(2.0)
    for sym, p in pos.items():                             # re-hedge missing/short futures legs
        want = abs(float(p["perp_qty"]))
        have = abs(float(actual.get(sym, 0.0)))
        if have + 1e-9 < want * 0.98:                      # >2% of the short leg is missing
            if sym in forced:                              # ADL/liquidation took it -> flatten pair
                with _safe():
                    if have > 0:
                        _mkt_or_limit(fut, sym, "BUY", round(have, 8))
                    fl = spot.exchange_filters().get(sym, {})
                    q = _round(float(p["spot_qty"]), fl.get("step", 0.0),
                               int(fl.get("qty_prec", 6)))
                    if q > 0:
                        _mkt_or_limit(spot, sym, "SELL", q)
                    dead.append(sym)
                    if cooldown is not None:
                        cooldown[sym] = time.time() + 86400.0
                    acts.append(f"adl-flatten {sym} (venue force-closed short; spot sold, 24h out)")
                continue
            if flatten_only:      # book ordered flat -> re-shorting walks back into the position
                acts.append(f"flatten-mode: skip re-hedge {sym} (book ordered flat)")
                continue
            with _safe():
                fut.set_leverage(sym, 3)
            how = _do(fut, sym, "SELL", round(want - have, 8))
            if how:
                acts.append(f"re-hedge {sym} +{round(want - have, 4)} ({how})")
        elif have > want * 1.02:                           # EXCESS short beyond the tracked leg --
            # an orphan absorbed into a tracked symbol (or a failed partial close) is naked
            # directional short the spot leg does NOT cover -> trim back to the tracked size.
            how = _do(fut, sym, "BUY", round(have - want, 8))
            if how:
                acts.append(f"trim-excess {sym} -{round(have - want, 4)} ({how})")
    for sym in dead:
        pos.pop(sym, None)

    # SPOT leg: a tracked carry whose spot WALLET holds less than the tracked long qty is under-
    # hedged (net short the deficit) -> buy it back. We never SELL excess (untracked orphan longs
    # are harmless junk). This catches spot under-fills the futures-only check would miss.
    with _safe():
        bal = spot.balances()
        sfl = spot.exchange_filters()
        for sym, p in pos.items():
            want = float(p["spot_qty"])
            held = bal.get(sym.replace("USDT", ""), 0.0)
            if held + 1e-9 < want * 0.98:
                if flatten_only:  # re-buying the leg the close just sold is the churn loop itself
                    acts.append(f"flatten-mode: skip spot-rehedge {sym} (book ordered flat)")
                    continue
                fl = sfl.get(sym, {})
                deficit = _round(want - held, fl.get("step", 0.0), int(fl.get("qty_prec", 6)))
                if deficit > 0:
                    how = _do(spot, sym, "BUY", deficit)
                    if how:
                        acts.append(f"spot-rehedge {sym} +{deficit} ({how})")
            elif want > 0 and held > want * 1.02:
                # STRANDED SPOT EXCESS -- REPORT ONLY (2026-07-26). A half-filled pair
                # (`OPEN-FAIL ... spot_ok=True fut_ok=False`) leaves the BOUGHT spot leg orphaned:
                # untracked, unhedged, and invisible to `_mark`, so it is naked long the book does
                # not carry on its own P&L. Selling it is a money-path action -- never automatic --
                # but it must never sit UNSEEN again, which is how it accumulated to multiples of
                # the tracked size. Surfaced in last_actions + the dashboard feed.
                acts.append(f"SPOT-EXCESS {sym}: wallet {held:.6g} vs tracked {want:.6g} "
                            f"(+{held - want:.6g}) -- untracked naked long, verify/flatten by hand")
    return acts


def _net_bps(sym: str, funding: float, min_hold_h: float = _MIN_HOLD_H) -> float:
    """Expected NET bps over the minimum hold: funding captured MINUS measured round-trip.

    This is the quantity the desk actually earns, and ranking on it rather than on gross funding
    is the whole of the 2026-07-27 universe switch. Unmeasured symbols carry the pessimistic
    _DEFAULT_RT_BPS, so they sink on their own without a separate denylist.
    """
    return funding * 1e4 * (min_hold_h / 8.0) - _rt_bps(sym)


def _ranked() -> list[tuple[str, float]]:
    """All positive-funding USDT perps tradeable on BOTH testnets, ranked high->low funding."""
    f = current_funding()
    spot_syms, fut_syms = set(spot.exchange_filters()), set(fut.exchange_filters())
    cands = [(s, v) for s, v in f.items()
             if v > 0 and s.endswith("USDT") and s in spot_syms and s in fut_syms]
    return sorted(cands, key=lambda x: -x[1])


def _rebalance(top: int, hold_top: int, capital: float, *, dry: bool) -> dict[str, Any]:
    # Close-only mode (top=0, hold_top=0: the KILL/flatten path) needs no market ranks --
    # closing reads `pos`, not funding. Decoupled so the kill can execute during a public-
    # data outage or IP ban (2026-07-31: premiumIndex 418 crashed every close-all tick).
    ranked = _ranked() if (top > 0 or hold_top > 0) else []
    # UNIVERSE SWITCH (principal-approved 2026-07-27). Was `ranked[:top]` = top-N by RAW
    # FUNDING. Funding is the COMPENSATION FOR ILLIQUIDITY, so funding-first ranking
    # systematically selected the names whose round-trips destroy the carry: COOKIEUSDT was
    # the most-traded symbol at 21 opens with a MEASURED 130.47bps pair round-trip against
    # ~6.7bps of funding over a 24h hold -- a ~19x loss per rotation. 11 of the 16 most-
    # traded names had no measured cost at all. That single defect explains the 7.75x
    # cost/funding ratio with no residual mystery. Rank by NET instead; _entry_gate still
    # has the final veto. OPENS ONLY -- `target`/`hold_set` are untouched below, so this can
    # never force-close a held carry (whose entry cost is already sunk).
    cands = sorted(ranked, key=lambda c: -_net_bps(c[0], c[1]))[:top]
    # HYSTERESIS: a held carry is kept while it stays in the broad top-`hold_top` positive set;
    # only names that fall out of it (or go non-positive) are closed. Kills noise-driven churn.
    hold_set = {s for s, _ in ranked[:hold_top]}
    target = hold_set
    state = json.loads(_STATE.read_text("utf-8")) if _STATE.exists() else {}
    pos: dict[str, dict[str, Any]] = state.get("positions", {})
    if "start" not in state:
        state["start"] = datetime.now(tz=UTC).isoformat()
        state["start_futures_equity"] = (fut.account_summary()["equity"] if fut.has_keys() else 0.0)
        state["start_spot_value"] = spot.account_value_usdt() if spot.has_keys() else 0.0
    cool: dict[str, float] = {s: float(t) for s, t in state.get("cooldown", {}).items()
                              if float(t) > time.time()}   # ADL/basis-stop names: 24h no re-entry
    state["cooldown"] = cool
    fails: dict[str, int] = {s: int(n) for s, n in state.get("reconcile_fail_counts", {}).items()}
    state["reconcile_fail_counts"] = fails
    ocool: dict[str, float] = {s: float(t) for s, t in state.get("orphan_cooldown", {}).items()}
    state["orphan_cooldown"] = ocool
    orph: dict[str, int] = {s2: int(n2) for s2, n2 in state.get("orphan_seen_counts", {}).items()}
    state["orphan_seen_counts"] = orph
    # FLATTEN MODE: a KILL file is authoritative this tick; a risk-flatten is only known AFTER
    # prices are read, so it latches through state and binds the NEXT tick's reconcile. Both stop
    # the reconciler rebuilding a book the close path is unwinding (2026-07-28 churn incident).
    _flatten_only = _KILL.exists() or state.get("last_risk_action") == "flatten"
    # GUARD CONSUMPTION (R0071d): live_guard computed a graded response for weeks --
    # effective_size_fraction and limit_only -- and nothing read either. Its binary KILL half
    # was wired (above); the graded half now scales this tick's sizing capital and, in
    # limit_only, forbids taker chasing in the maker path. Stale artifact = neutral.
    _refresh_guard()
    _guard_note = ""
    if _GUARD["size_frac"] < 1.0 or _GUARD["limit_only"]:
        capital = capital * _GUARD["size_frac"]
        _guard_note = (f"live_guard: sizing scaled to {_GUARD['size_frac']:.0%}"
                       + (" + limit-only" if _GUARD["limit_only"] else ""))
    recon = _reconcile(pos, dry=dry, cooldown=cool,          # heal hedge drift FIRST (survival #1)
                       fail_counts=fails, orphan_seen=orph,
                       flatten_only=_flatten_only)
    if cool:
        target -= set(cool)
        cands = [c for c in cands if c[0] not in cool]
    # ENTRY GATE (gap #43): opens only -- never filters hold_set/target, so raising the
    # bar cannot force-close existing carries.
    _pre = len(cands)
    cands = [c for c in cands if _entry_gate(c[0], c[1])]
    if len(cands) < _pre:
        actions_gate = f"entry-gate: {_pre - len(cands)} cand(s) below funding/cost bar"
    else:
        actions_gate = ""
    spot_px, fut_px = spot.prices(), fut.mark_prices()
    # BASIS-BLOWOUT STOP (2026-07-12 external review): the pair is delta-neutral to PRICE, not
    # to BASIS -- it marks against us when the perp trades at a large PREMIUM to spot (short
    # squeeze), which is also the ADL/liquidation-risk state for the short leg. Normal carry
    # basis is a few bps; a >3% instantaneous premium is a dislocation, not harvest -> exit the
    # pair (existing close path) and stand down 24h. Never fires in calm markets: zero drag.
    for sym in list(pos):
        sp, fp = spot_px.get(sym), fut_px.get(sym)
        if sp and fp and (fp - sp) / sp > 0.03:
            target.discard(sym)
            # 6h cooldown (round-3 review: basis spikes are mean-reverting flash events --
            # a 24h stand-down overpays; ADL keeps 24h because a squeeze that force-closed
            # a leg is a different animal). Exit itself is maker-first like every close.
            cool[sym] = time.time() + 21600.0
            actions_pre = f"basis-stop {sym} premium {(fp - sp) / sp:.1%} -> exit pair, 6h out"
            recon = [*recon, actions_pre]
    spot_fl, fut_fl = spot.exchange_filters(), fut.exchange_filters()
    # Size opens from FREE capital only. Held carries are never resized, so their notional is
    # already deployed; allocating the FULL capital across the (often 1-2) fresh names is how
    # 2026-07-13 sized one micro-cap at ~the whole book. Names closing this same cycle still
    # count as deployed here -- one cycle of under-deploy is cheap, over-deploy is ruin.
    deployed = sum(float(p["spot_qty"]) * float(p["spot_cost"]) for p in pos.values())
    free = max(0.0, capital - deployed)
    alloc = _alloc(cands, free)                             # funding-weighted, concentration-capped
    per = free / max(1, len(cands))                        # equal-weight fallback
    actions: list[str] = list(recon)                       # surface reconcile actions in the feed
    if _guard_note:
        actions.append(_guard_note)
    if actions_gate:
        actions.append(actions_gate)

    # GROWTH-POSITIVE risk controls (ruin-boundary sized). Flatten ONLY at the 35% ruin threshold
    # the leverage optimizer uses; PAUSE (not flatten) new opens in stress so existing carries keep
    # harvesting funding. In normal operation this does nothing -> zero drag on compounding.
    risk = None
    if fut.has_keys():
        with _safe():
            # COMBINED book equity, not futures-only: the book is delta-neutral, so in a broad
            # rally the perp shorts drain the futures account while the spot longs gain the same
            # amount in the spot wallet. Judged on the futures account alone, a big enough rally
            # reads as "ruin" and would flatten a perfectly-hedged book at full cost.
            eq = float(fut.account_summary()["equity"])
            spot_side = (sum(float(p["spot_qty"])
                             * (spot_px.get(s, float(p["spot_cost"])) - float(p["spot_cost"]))
                             for s, p in pos.items())
                         + float(state.get("realized_spot_pnl", 0.0)))
            eq_c = eq + spot_side
            # VENUE-TRUTH PERSISTENCE (R0071a, 2026-07-31): this key had THREE readers and no
            # writer -- record_capital_event.py fell through to inception-or-zero, so the ONE
            # command that runs on launch day would have recorded equity $0.00 and re-based the
            # rail ~89% below truth. The executor is the only organ that computes combined
            # equity from venue truth; it now persists that number with its timestamp so the
            # capital-event reader can demand freshness instead of trusting a corpse.
            state["last_combined_equity"] = round(eq_c, 2)
            state["last_combined_equity_at"] = datetime.now(tz=UTC).isoformat()
            # INCEPTION, honouring any RECORDED capital event (libs/risk/capital_events.py).
            # `start_futures_equity` is written once at inception and never re-based, so after a
            # ruin-floor breach the book entered a provably closed loop -- flatten, no opens, no
            # funding, equity constant, flatten -- measured at 113 consecutive rebalances on
            # 2026-07-30, and it froze Gate 0's live-fills clock at 26.42 of 28 days.
            #
            # This does NOT loosen the rail. effective_start_equity is read-only and returns its
            # argument unchanged when no capital event has ever been recorded, so behaviour on an
            # un-deposited box is byte-identical. Only a signed, ledgered deposit or an explicit
            # principal restart moves the inception -- the desk cannot clear its own stop.
            start_eq = float(capital_events.effective_start_equity(
                float(state.get("start_futures_equity", eq))))
            peak = max(float(state.get("peak_combined_equity", start_eq)), eq_c)
            state["peak_combined_equity"] = peak
            gross = sum(float(p["spot_qty"]) * spot_px.get(s, float(p["spot_cost"]))
                        for s, p in pos.items())
            risk = risk_controls.evaluate(eq_c, start_eq, peak, gross, ruin_cap_lev=8.0)
            state["last_risk_action"] = risk.action   # latches flatten into next tick's reconcile
            if risk.action == "flatten":
                target, cands = set(), []                   # close all, open nothing (survival)
                actions.append("RISK-FLATTEN " + "; ".join(risk.reasons))
            elif risk.action == "pause_opens":
                cands = []                                  # hold + close, add no new risk
                actions.append("RISK-PAUSE-OPENS " + "; ".join(risk.reasons))

    # CLOSE carries that left the positive-funding set (sell spot, cover perp)
    # CHURN GUARD (gap #42): a rotation-driven close on a carry that has not yet earned its
    # round-trip is a measured -8.1%/yr drag. Rails are exempt and still close instantly.
    # KILL FORCES THE RAIL (2026-07-27, Tier 0). Without this the churn guard HELD carries
    # younger than _MIN_HOLD_H while DEADMAN_FIRED and CASHCARRY_KILL were both latched --
    # MOVEUSDT (07:21) and TSTUSDT (08:58) were both under 24h and survived a demanded full
    # unwind. A ruin rail a fee heuristic can veto is not a ruin rail. Opens are already
    # impossible at top=0, so widening the forced set can only ever CLOSE.
    _KILL_FORCES_RAIL = _KILL.exists()
    _rail_forced = set(cool) | (set(pos) if (_KILL_FORCES_RAIL or (
        risk is not None and risk.action == "flatten")) else set())
    for sym in list(pos):
        if sym not in target:
            p = pos[sym]
            if _churn_guard(_held_hours(p.get("opened")), float(p.get("funding", 0.0)),
                            sym in _rail_forced):
                actions.append(f"hold {sym}: churn-guard "
                               f"({_held_hours(p.get('opened')):.1f}h < {_MIN_HOLD_H:g}h)")
                continue
            # realized trade record: delta-neutral price legs (~cancel) + est funding harvested
            spx, fpx = spot_px.get(sym, p["spot_cost"]), fut_px.get(sym, p["perp_entry"])
            fill: dict[str, Any] = {}                    # dry places no orders -> no fill mode
            if not dry:
                t0 = int(time.time() * 1000) - 2000       # fill window (venue clock-skew slack)
                fill = _execute_pair(sym, float(p["spot_qty"]), "SELL", "BUY")  # close: sell/cover
                # VERIFY-BEFORE-DELETE (2026-07-19 incident, GAP row 34): a close that isn't
                # CONFIRMED filled on both legs must stay tracked, or its spot inventory strands
                # forever (deleted from `pos`, no longer visible to any reconciler pass, no error
                # anywhere). ~$2,150 of real spot inventory was lost this way before this fix.
                if not (fill.get("spot_ok") and fill.get("fut_ok")):
                    actions.append(f"CLOSE-FAIL {sym}: spot_ok={fill.get('spot_ok')} "
                                   f"fut_ok={fill.get('fut_ok')} -- kept tracked, retry next cycle")
                    continue
                # EXIT MARKS FROM ACTUAL FILLS (2026-07-13 incident): ticker marks are blind to
                # what a thin book actually paid us -- see the matching open-path fix below.
                spx = spot.avg_fill(sym, "SELL", t0) or spx
                fpx = fut.avg_fill(sym, "BUY", t0) or fpx
            held = _held_hours(p.get("opened"))
            notl = float(p["spot_qty"]) * float(p["spot_cost"])
            spot_real = float(p["spot_qty"]) * (spx - float(p["spot_cost"]))
            price_pnl = (spot_real
                         + abs(float(p["perp_qty"])) * (float(p["perp_entry"]) - fpx))
            # NOTE: realized_spot_pnl is NOT incremented here. It is re-derived from EXCHANGE GROUND
            # TRUTH at the end of every rebalance (_reconcile_spot_realized) -- a stale/crashed
            # executor or duplicate close-log can then never let it silently drift and fabricate a
            # dashboard loss (the 2026-07-10 phantom). price_pnl (logged below) is the basis input.
            est_funding = float(p.get("funding", 0.0)) * notl * (held / 8.0)
            _log_trade({"event": "close", "symbol": sym, "qty": p["spot_qty"],
                        "notional": round(notl, 2), "funding_rate": p.get("funding"),
                        "opened": p.get("opened"), "closed": datetime.now(tz=UTC).isoformat(),
                        "held_hours": held, "price_pnl": round(price_pnl, 2),
                        "est_funding": round(est_funding, 2),
                        "net": round(price_pnl + est_funding, 2),
                        "spot_mode": fill.get("spot"), "fut_mode": fill.get("fut"),
                        **_tca(fill, spx, fpx, "SELL")})
            actions.append(f"close {sym}")
            del pos[sym]

    # OPEN new carries only up to `top` total (hold existing -> never resize an open carry)
    for sym, fnd in cands:
        if len(pos) >= top:                               # book full -> don't over-open
            break
        if sym in pos:
            continue
        px, ffl, sfl = spot_px.get(sym), fut_fl.get(sym), spot_fl.get(sym)
        if not px or not ffl or not sfl:
            continue
        step = max(ffl["step"], sfl["step"])              # coarser step keeps both legs matched
        qty = _round(alloc.get(sym, per) / px, step, int(min(ffl["qty_prec"], sfl["qty_prec"])))
        if qty < max(ffl["min_qty"], sfl["min_qty"]) or qty <= 0:
            continue
        # THIN-BOOK GUARD: an open is optional -- never enter a book that cannot absorb the order.
        # The 2026-07-13 NOMUSDT open filled through a near-empty testnet spot book at a cost the
        # mark-based book never saw (~$4.7k of venue cash on a $4.3k "notional"). Require resting
        # liquidity within 1% of the touch on BOTH entry legs to cover the order several times.
        want = qty * px
        s_depth, f_depth = spot.quote_depth(sym, "BUY"), fut.quote_depth(sym, "SELL")
        if min(s_depth, f_depth) < want * _DEPTH_MULT:
            actions.append(f"skip {sym}: thin book (spot ${s_depth:.0f} / fut ${f_depth:.0f} "
                           f"< {_DEPTH_MULT:g}x ${want:.0f})")
            continue
        fpe = fut_px.get(sym, px)
        if not dry:
            t0 = int(time.time() * 1000) - 2000           # fill window (venue clock-skew slack)
            fill = _execute_pair(sym, qty, "BUY", "SELL")  # open: long spot, short perp
            # VERIFY-BEFORE-TRACK (2026-07-19 incident, GAP row 34): only track a position once
            # both legs are CONFIRMED filled -- an untracked failed/partial open is visible in the
            # error log for follow-up rather than silently absent from every future reconcile pass.
            if not (fill.get("spot_ok") and fill.get("fut_ok")):
                actions.append(f"OPEN-FAIL {sym}: spot_ok={fill.get('spot_ok')} "
                               f"fut_ok={fill.get('fut_ok')} -- not tracked, verify manually")
                continue
            # COST BASIS FROM ACTUAL FILLS (2026-07-13 incident): ticker-at-open recorded a
            # ~$4.7k thin-book fill cost as -$55 -- entry slippage must hit the book the moment
            # it happens. Ticker remains only the fallback when the venue read fails.
            px = spot.avg_fill(sym, "BUY", t0) or px
            fpe = fut.avg_fill(sym, "SELL", t0) or fpe
        pos[sym] = {"spot_qty": qty, "spot_cost": px, "perp_qty": -qty,
                    "perp_entry": fpe, "funding": round(fnd, 6),
                    "opened": datetime.now(tz=UTC).isoformat()}
        if not dry:
            _log_trade({"event": "open", "symbol": sym, "qty": qty,
                        "notional": round(qty * px, 2), "funding_rate": round(fnd, 6),
                        "opened": pos[sym]["opened"],
                        "spot_mode": fill.get("spot"), "fut_mode": fill.get("fut"),
                        **_tca(fill, px, fpe, "BUY")})
        actions.append(f"open {sym} {qty}")

    # TOP UP undersized held carries toward the FULL-capital target so authorized capital is not
    # left idle (operator-directed 2026-07-19; gap #32). Held carries are otherwise never resized,
    # so a carry opened in a low-free-capital window stayed frozen small. Runs ONLY in normal state
    # (never while a risk rail flattens/pauses), ADDS only (never sizes down), through the SAME
    # 0.35 cap + thin-book depth guard as opens; _topup_plan bounds the aggregate to the free
    # headroom so the book never levers past `capital`.
    if risk is None or risk.action not in ("flatten", "pause_opens"):
        for sym, add in _topup_plan(pos, capital).items():
            px, ffl, sfl = spot_px.get(sym), fut_fl.get(sym), spot_fl.get(sym)
            if not px or not ffl or not sfl:
                continue
            step = max(ffl["step"], sfl["step"])
            qty = _round(add / px, step, int(min(ffl["qty_prec"], sfl["qty_prec"])))
            if qty < max(ffl["min_qty"], sfl["min_qty"]) or qty <= 0:
                continue
            want = qty * px
            s_depth, f_depth = spot.quote_depth(sym, "BUY"), fut.quote_depth(sym, "SELL")
            if min(s_depth, f_depth) < want * _DEPTH_MULT:
                actions.append(f"skip topup {sym}: thin book")
                continue
            p = pos[sym]
            fpe = fut_px.get(sym, px)
            if not dry:
                t0 = int(time.time() * 1000) - 2000
                fill = _execute_pair(sym, qty, "BUY", "SELL")  # add matched legs (spot+perp)
                # VERIFY-BEFORE-TRACK (2026-07-19 incident, GAP row 34): the exact bug class that
                # stranded ~$2,150 -- a topup that isn't CONFIRMED filled on both legs must never
                # be added to the tracked spot_qty/perp_qty, or the excess buy becomes permanently
                # invisible the moment this symbol is later closed against the (unchanged) old qty.
                if not (fill.get("spot_ok") and fill.get("fut_ok")):
                    actions.append(f"TOPUP-FAIL {sym}: spot_ok={fill.get('spot_ok')} "
                                   f"fut_ok={fill.get('fut_ok')} -- not tracked, verify manually")
                    continue
                px = spot.avg_fill(sym, "BUY", t0) or px
                fpe = fut.avg_fill(sym, "SELL", t0) or fpe
            old_q = float(p["spot_qty"])
            new_q = old_q + qty
            p["spot_cost"] = (old_q * float(p["spot_cost"]) + qty * px) / new_q
            p["perp_entry"] = (old_q * float(p["perp_entry"]) + qty * fpe) / new_q
            p["spot_qty"] = new_q
            p["perp_qty"] = -new_q
            if not dry:
                _log_trade({"event": "topup", "symbol": sym, "qty": qty,
                            "notional": round(qty * px, 2), "funding_rate": p.get("funding"),
                            "opened": p.get("opened"),
                            "spot_mode": fill.get("spot"), "fut_mode": fill.get("fut"),
                            **_tca(fill, px, fpe, "BUY")})
            actions.append(f"topup {sym} +{qty}")

    state["positions"] = pos
    if not dry:
        # VENUE-SIDE PROTECTIVE STOPS (R0071c): reconciled every tick against the held book --
        # place missing, replace drifted, remove orphaned. Survives total host death, which the
        # in-process rail cannot.
        actions.extend(_reconcile_protective_stops(pos, state))
    if not dry:                                           # only persist REAL (executed) positions
        _reconcile_spot_realized(state)                   # self-heal accounting from exchange truth
        _STATE.parent.mkdir(parents=True, exist_ok=True)
        _STATE.write_text(json.dumps(state, indent=2), "utf-8")
    return {"state": state, "pos": pos, "cands": cands, "actions": actions,
            "spot_px": spot_px, "fut_px": fut_px,
            "risk": risk.to_dict() if risk else None}


def _reconcile_spot_realized(state: dict[str, Any]) -> None:
    """Re-anchor realized_spot_pnl to exchange ground truth each rebalance (+ on restart).

    Derives it from the venue's own futures REALIZED_PNL (exact) plus the deduped trade-log basis,
    overwriting the stored value only when it has drifted past _RSP_TOL. This makes the phantom-loss
    class impossible: a stale/crashed executor self-heals on its first rebalance after restart, and
    duplicate close-logs can never double-count (see libs/execution/carry_accounting)."""
    if not (fut.has_keys() and state.get("start")):
        return
    with _safe():
        start_ms = int(datetime.fromisoformat(str(state["start"])).timestamp() * 1000)
        venue_realized = float(fut.income_summary(start_ms).get("realized_pnl", 0.0))
        trades = json.loads(_TRADES.read_text("utf-8")) if _TRADES.exists() else []
        derived = derive_spot_realized(venue_realized, trades)
        stored = float(state.get("realized_spot_pnl", 0.0))
        if abs(stored - derived) > _RSP_TOL:
            state["realized_spot_pnl"] = derived
            print(f"[reconcile] realized_spot_pnl {stored:.2f} -> {derived:.2f} "
                  f"(exchange-anchored; drift {derived - stored:+.2f})")


class _safe:
    """Best-effort order context -- a single leg failing must not abort the whole rebalance."""
    def __enter__(self) -> _safe:
        return self

    def __exit__(self, *exc: object) -> bool:
        return True                                       # swallow leg errors (logged via web)


_MAKER_WAIT = 8.0                                          # seconds a post-only quote may rest
# OPENS are patient (2026-07-23 fee audit): measured 75.8% taker fills paying 96.5% of all
# commissions; resting them as maker saves ~86% of fees. A carry open has no urgency (funding
# accrues on 8h boundaries) so waiting minutes for the maker rebate is nearly free. CLOSES keep
# the 8s wait -- the rails must exit fast and this must never slow the risk path.
_MAKER_WAIT_OPEN = 240.0                                   # seconds a post-only OPEN may rest


def _passive_price(bk: dict[str, Any], fl: dict[str, Any], sym: str, side: str) -> float | None:
    """Tick-rounded passive maker price: BUY at best bid, SELL at best ask (won't cross)."""
    bid, ask = bk.get(sym, (0.0, 0.0))
    px = bid if side == "BUY" else ask
    if px <= 0:
        return None
    tick = float(fl.get("tick", 0.0) or 0.0)
    return (round(round(px / tick) * tick, int(fl.get("price_prec", 8)))
            if tick > 0 else float(px))


_STOP_FRAC = 0.35                                          # spec section 3: ruin-line distance


def _stop_plan(pos: dict[str, dict[str, Any]],
               *, frac: float = _STOP_FRAC) -> dict[str, dict[str, float]]:
    """Desired venue-side protective stop per held carry (R0071c; pure -- fully testable).

    Every carry is short the perp, so the protective side is BUY reduce-only at
    entry*(1+frac). frac is the ruin-line distance (spec section 3): far beyond any funding
    wick a carry should survive, comfortably inside the leverage-cap liquidation band, and it
    exists for the host-death case -- an executor that dies leaves a book the venue itself
    will de-hedge cleanly instead of liquidating."""
    out: dict[str, dict[str, float]] = {}
    for sym, p in pos.items():
        qty = abs(float(p.get("perp_qty") or p.get("spot_qty") or 0.0))
        entry = float(p.get("perp_entry") or p.get("spot_cost") or 0.0)
        if qty > 0 and entry > 0:
            out[sym] = {"qty": qty, "stop": round(entry * (1.0 + frac), 8)}
    return out


def _stop_matches(order: dict[str, Any], want: dict[str, float]) -> bool:
    """True when a resting stop is close enough to the plan to keep (5% qty / 2% price)."""
    try:
        return (abs(float(order.get("origQty", 0.0)) - want["qty"]) <= 0.05 * want["qty"]
                and abs(float(order.get("stopPrice", 0.0)) - want["stop"]) <= 0.02 * want["stop"])
    except (TypeError, ValueError):
        return False


def _reconcile_protective_stops(pos: dict[str, dict[str, Any]],
                                state: dict[str, Any]) -> list[str]:
    """Venue-side stop = the rail that survives host death. Reconciled, not fire-and-forget:
    place missing, replace drifted (>5% qty / >2% price), cancel orphans whose position
    closed. Per-id cancels only -- see _resting_quotes for why cancel_all is forbidden near
    stops. No-op on connectors without stop support (testnet parity gap, recorded)."""
    if not fut.has_keys() or not hasattr(fut, "place_stop_market"):
        return []
    canceler = getattr(fut, "cancel_order", None)
    plan = _stop_plan(pos)
    acts: list[str] = []
    tracked = set(state.get("protective_stops", {})) | set(plan)
    for sym in sorted(tracked):
        with _safe():
            stops = [o for o in fut.open_orders(sym) if o.get("type") == "STOP_MARKET"]
            want = plan.get(sym)
            if want is None:                               # position gone -> its stop goes too
                for o in stops:
                    if canceler is not None:
                        canceler(sym, int(o.get("orderId", 0)))
                        acts.append(f"stop-cancel {sym} (position closed)")
                continue
            keep = next((o for o in stops if _stop_matches(o, want)), None)
            for o in stops:                                # drifted/duplicate stops go
                if o is not keep and canceler is not None:
                    canceler(sym, int(o.get("orderId", 0)))
            if keep is None:
                fut.place_stop_market(sym, "BUY", want["qty"], want["stop"])
                acts.append(f"stop {sym} {want['qty']} @{want['stop']} (ruin-line backstop)")
    state["protective_stops"] = plan
    return acts


def _resting_quotes(mod: Any, sym: str) -> list[dict[str, Any]]:
    """Open orders EXCLUDING protective stops (R0071c).

    The maker-pair protocol infers 'my quote filled' from an emptying open-orders book. A
    resting STOP_MARKET breaks that inference permanently: the book never reads empty, the wait
    loop always times out, and the fallback branch cancels the stop and re-takers an
    already-filled leg -- a double fill AND a naked position, triggered by the safety order
    itself. This is why the stop had zero callers; the filter is what makes wiring it safe."""
    try:
        return [o for o in mod.open_orders(sym) if o.get("type") != "STOP_MARKET"]
    except Exception:
        return []


# live_guard consumption (R0071d): refreshed once per tick from data/live_guard.json; the guard
# computed these for weeks with no consumer. size_frac scales the tick's sizing capital;
# limit_only suppresses taker fallbacks. Stale/absent guard = neutral (full size, takers
# allowed) -- the guard's own freeze path is the KILL file, which is already authoritative.
_GUARD: dict[str, Any] = {"size_frac": 1.0, "limit_only": False}


def _refresh_guard() -> None:
    _GUARD.update({"size_frac": 1.0, "limit_only": False})
    # L1.44 contract (0.25h = the guard's own 900s inline rule, now recorded): the fail direction
    # stays OPEN by documented design ("stale guard is no guard" -- the KILL file is the freeze
    # authority), but a dead guard can never write its own KILL, so run_alerts now pages
    # live_guard_dead and this read leaves a stale_read record instead of degrading silently.
    try:
        fr = read_fresh("data/live_guard.json", max_age_h=0.25,
                        caller="run_cashcarry_executor._refresh_guard")
        if not fr.fresh or not isinstance(fr.data, dict):
            return                                          # stale guard is no guard
        _GUARD["size_frac"] = min(1.0, max(0.0, float(fr.data.get("effective_size_fraction", 1.0))))
        _GUARD["limit_only"] = str(fr.data.get("canary", {}).get("mode", "")) == "limit_only"
    except Exception:
        return


def _maker_pair(sym: str, qty: float, spot_side: str, fut_side: str,
                *, wait: float) -> dict[str, Any]:
    """Quote BOTH legs post-only (maker), wait, then taker-fill whatever didn't rest+fill.

    Same qty on both legs -> the pair ends delta-neutral; the wait bounds any transient exposure.
    Returns modes plus spot_ok/fut_ok -- a leg only counts as filled once EITHER it rested and
    left the open-orders book (maker fill) OR its taker fallback returns a confirmed FILLED
    order; a leg that never confirms either way is reported unfilled, never assumed."""
    sbk, fbk = spot.book_ticker(), fut.book_ticker()
    sfl = spot.exchange_filters().get(sym, {})
    ffl = fut.exchange_filters().get(sym, {})
    legs = [("spot", spot, spot_side, sbk, sfl), ("fut", fut, fut_side, fbk, ffl)]
    modes: dict[str, str] = {}
    ok: dict[str, bool] = {"spot": False, "fut": False}
    for name, mod, side, bk, fl in legs:
        px = _passive_price(bk, fl, sym, side)
        with _safe():
            o = mod.place_post_only(sym, side, qty, px) if px else {}
            modes[name] = "maker_pending" if o.get("orderId") else "taker"
    end = time.time() + wait
    while time.time() < end:                               # wait for the resting quotes to fill
        time.sleep(2.0)
        if not _resting_quotes(spot, sym) and not _resting_quotes(fut, sym):
            break
    for name, mod, side, _bk, _fl in legs:                 # cancel + taker any still-unfilled leg
        with _safe():
            resting = _resting_quotes(mod, sym)
            if resting:
                # Cancel OUR quotes by id, never the symbol's whole book (R0071c): cancel_all
                # here would take the protective STOP_MARKET down with the stale quote --
                # naked-stop removal as a side effect of a fill-timeout. Fall back to
                # cancel_all only on a connector without per-id cancel (testnet spot, where
                # no stops rest).
                canceler = getattr(mod, "cancel_order", None)
                if canceler is not None:
                    for o in resting:
                        canceler(sym, int(o.get("orderId", 0)))
                else:
                    mod.cancel_all(sym)
                if _GUARD["limit_only"]:
                    # live_guard degraded mode (R0071d): no taker chasing -- report the leg
                    # unfilled and let the next tick re-quote. The guard's whole point is that
                    # in a degraded venue state, paying taker to force a fill is the leak.
                    modes[name] = "limit_only_unfilled"
                else:
                    res = mod.place_market(sym, side, qty)
                    modes[name] = "taker_fallback"
                    ok[name] = _filled(res)
            elif modes.get(name) == "maker_pending":
                modes[name] = "maker"
                ok[name] = True                             # left the book with no cancel -> filled
    if not (ok["spot"] and ok["fut"]):
        with contextlib.suppress(Exception):
            _ERR.write_text(f"{datetime.now(tz=UTC).isoformat()} unfilled leg (maker path) {sym} "
                            f"ok={ok} modes={modes}\n")
    return {**modes, "spot_ok": ok["spot"], "fut_ok": ok["fut"]}


def _filled(res: object) -> bool:
    """True only for a CONFIRMED-filled order response (not merely 'no exception was thrown').

    2026-07-19 incident (GAP register row 34): `_safe()` swallows every exception with zero fill
    verification, so a rejected/partial order looked identical to a successful one to every
    caller -- three closes silently failed to sell their spot leg, stranding ~$2,150 of real
    inventory the position tracker had already deleted and would never revisit. A response is
    only trustworthy when the venue itself confirms FILLED."""
    return (isinstance(res, dict) and res.get("status") == "FILLED"
            and float(res.get("executedQty", 0.0)) > 0)


def _mid_of(conn: Any, sym: str) -> float | None:
    """Read-only mid quote. Returns None rather than 0.0 so a failed read is never mistaken for
    a real price and silently turned into a 100% slippage number."""
    try:
        bid, ask = conn.book_ticker().get(sym, (0.0, 0.0))
        bid, ask = float(bid), float(ask)
        return (bid + ask) / 2.0 if bid > 0 and ask > 0 else None
    except Exception:
        return None


def _tca(fill: dict[str, Any], spot_fill: float | None, fut_fill: float | None,
         spot_side: str) -> dict[str, Any]:
    """Per-leg transaction-cost attribution. POSITIVE bps ALWAYS MEANS WE PAID.

    On an open the carry buys spot and sells futures; on a close it is the reverse. Paying above
    mid when buying and receiving below mid when selling are both costs, so the sign is flipped
    per side to make the columns directly comparable and summable across opens and closes.
    """
    out: dict[str, Any] = {
        "spot_fill": spot_fill, "fut_fill": fut_fill,
        "spot_mid": fill.get("spot_mid"), "fut_mid": fill.get("fut_mid"),
        "wait_s": fill.get("wait_s"),
    }
    sm, fm = fill.get("spot_mid"), fill.get("fut_mid")
    if sm and spot_fill:
        s = (float(spot_fill) - sm) / sm * 1e4
        out["spot_slip_bps"] = round(s if spot_side == "BUY" else -s, 3)
    if fm and fut_fill:
        f = (float(fut_fill) - fm) / fm * 1e4          # futures leg is the opposite side of spot
        out["fut_slip_bps"] = round(-f if spot_side == "BUY" else f, 3)
    return out


def _execute_pair(sym: str, qty: float, spot_side: str, fut_side: str) -> dict[str, Any]:
    """TCA WRAPPER (2026-07-27). Captures the decision-time benchmark and elapsed time around the
    unchanged execution path, so realised slippage becomes measurable per leg, per symbol, per
    mode. Adds no order logic; the mid reads are read-only and failures degrade to None."""
    _t0 = time.time()
    _sm = _mid_of(spot, sym)
    _fm = _mid_of(fut, sym)
    res = _execute_pair_impl(sym, qty, spot_side, fut_side)
    if spot_side == "SELL":            # a CLOSE succeeds by reaching FLAT, not by filling an order
        res = _close_goal_state(sym, res)
    res["spot_mid"] = _sm
    res["fut_mid"] = _fm
    res["wait_s"] = round(time.time() - _t0, 3)
    return res


def _close_goal_state(sym: str, res: dict[str, Any]) -> dict[str, Any]:
    """Mark a CLOSE leg that is ALREADY at its goal state (flat) as done rather than failed.

    2026-07-28 incident: every futures hedge had been force-closed out from under the book, so
    the close path's reduceOnly cover had nothing to reduce. The venue rejects that order,
    `_filled` returns False, and `fut_ok=False` kept the pair tracked for a retry -- every tick,
    forever, while `_reconcile` rebuilt both legs in front of each attempt. 11,136 commission
    events against 251 logged round-trips; $1,456 of fees in 48h against $113 of LIFETIME funding
    harvest. The bug is definitional: `_ok` meant "an order filled" when a close only ever needed
    "the leg is flat".

    Checked PER LEG against the venue, so a leg that genuinely still holds inventory still fails
    and stays tracked -- the 2026-07-19 stranded-inventory fix (~$2,150 of real spot deleted from
    the tracker while still held) is preserved exactly, not loosened.
    """
    if not res.get("fut_ok"):
        with contextlib.suppress(Exception):
            if abs(float(fut.positions().get(sym, 0.0))) <= _FLAT_EPS:
                res["fut_ok"], res["fut"] = True, "already-flat"
    if not res.get("spot_ok"):
        with contextlib.suppress(Exception):
            step = float(spot.exchange_filters().get(sym, {}).get("step", 0.0) or 0.0)
            held = float(spot.balances().get(sym.replace("USDT", ""), 0.0))
            if held <= max(step, _FLAT_EPS):   # nothing left above the venue's tradable increment
                res["spot_ok"], res["spot"] = True, "already-flat"
    return res


def _execute_pair_impl(sym: str, qty: float, spot_side: str, fut_side: str) -> dict[str, Any]:
    """Fill both carry legs -- maker-first (execution alpha: lower fees) if enabled, else market.

    Returns {"spot": mode, "fut": mode, "spot_ok": bool, "fut_ok": bool} -- callers MUST check
    the _ok flags before treating a leg as filled; a leg failing must not abort the whole
    rebalance (that is what `_safe()` still protects), but it must never be reported as success.
    Maker path has a taker fallback; on ANY maker error we fall back to a plain market pair."""
    # CLOSES BYPASS THE MAKER PATH (2026-07-27, incident #6 recurrence). _MAKER=True made
    # _maker_pair the DEFAULT, and its post-only limits carry neither reduceOnly nor a venue
    # size cap -- so repeated close attempts accumulated resting fills that bought a short
    # through zero into a long. Twice: COOKIEUSDT +916,772, then 1000CATUSDT +1,138,985.
    # A close is a CERTAINTY problem, not a fee problem; the desk's own note already says
    # "patient on OPENS, fast on CLOSES". Opens keep the maker rebate, which is where it pays.
    _CLOSE_IS_MARKET_ONLY = spot_side == "SELL"
    if _MAKER and not _CLOSE_IS_MARKET_ONLY:
        try:
            # patient on OPENS (spot BUY = entering a carry), fast on CLOSES (spot SELL =
            # unwinding, where the rails need speed). See the fee audit note above.
            _w = _MAKER_WAIT_OPEN if spot_side == "BUY" else _MAKER_WAIT
            return _maker_pair(sym, qty, spot_side, fut_side, wait=_w)
        except Exception as e:  # maker machinery failed -> safe market fallback
            with contextlib.suppress(Exception):
                _ERR.write_text(f"{datetime.now(tz=UTC).isoformat()} maker fail {sym}: {e!r}\n")
    spot_res: object = None
    fut_res: object = None
    # CLOSE legs are reduceOnly (2026-07-27 incident). spot_side=="SELL" IS the close/unwind
    # direction; the futures leg then BUYS to cover a short, which is exactly the order that
    # walked COOKIEUSDT through zero into a +916,772 long. reduceOnly makes that impossible.
    # Opens (spot BUY / futures SELL) must NOT be reduceOnly -- they establish the short.
    _reduce_only_leg = spot_side == "SELL"
    with _safe():
        spot_res = spot.place_market(sym, spot_side, qty)
    with _safe():
        fut_res = fut.place_market(sym, fut_side, qty, reduce_only=_reduce_only_leg)
    spot_ok, fut_ok = _filled(spot_res), _filled(fut_res)
    if not (spot_ok and fut_ok):
        with contextlib.suppress(Exception):
            _ERR.write_text(f"{datetime.now(tz=UTC).isoformat()} unfilled leg {sym} "
                            f"spot_ok={spot_ok} fut_ok={fut_ok} spot_res={spot_res!r} "
                            f"fut_res={fut_res!r}\n")
    return {"spot": "taker", "fut": "taker", "spot_ok": spot_ok, "fut_ok": fut_ok}


def _mark(rb: dict[str, Any]) -> dict[str, float | None]:
    pos, spot_px, fut_px = rb["pos"], rb["spot_px"], rb["fut_px"]
    spot_pnl = perp_pnl = notional = 0.0
    for _sym, p in pos.items():
        spx = spot_px.get(_sym, p["spot_cost"])
        fpx = fut_px.get(_sym, p["perp_entry"])
        spot_pnl += float(p["spot_qty"]) * (spx - float(p["spot_cost"]))   # our long-spot legs
        perp_pnl += abs(float(p["perp_qty"])) * (float(p["perp_entry"]) - fpx)   # short (display)
        notional += float(p["spot_qty"]) * spx
    # REAL net = spot side + futures side, SYMMETRIC on realized PnL. The futures-equity delta
    # already contains its realized closes + funding + fees; the spot side needs open marks PLUS
    # the accumulated realized PnL of closed spot legs (their proceeds sit in the spot wallet,
    # invisible to open-position marks -- omitting them fabricated a loss as carries closed).
    state = rb["state"]
    spot_realized = float(state.get("realized_spot_pnl", 0.0))
    net = spot_pnl + spot_realized
    fut_pnl = 0.0
    # None, NOT 0.0 -- these come from a separate venue call that can fail on its own, and a
    # failed measurement must never be publishable as a measured zero (2026-07-26 incident).
    funding: float | None = None
    fut_commission: float | None = None
    if fut.has_keys():
        with _safe():
            fut_eq = fut.account_summary()["equity"]
            # EFFECTIVE inception here too (R0071b, 2026-07-31): this reporting site kept the
            # raw inception after the rail site was fixed, so the first post-deposit dashboard
            # tick would have shown the whole deposit as fabricated P&L -- the exact two-sites/
            # one-truth class the equity bug came from.
            start_eq = float(capital_events.effective_start_equity(
                float(state.get("start_futures_equity", fut_eq))))
            fut_pnl = fut_eq - start_eq                   # futures leg (realized+funding+fees+unrl)
            net = spot_pnl + spot_realized + fut_pnl
        # SEPARATE guard from the equity read above. Sharing one `_safe()` made the failure
        # PARTIAL: the equity assignment landed, then the income call threw, and the swallowed
        # exception left funding/commission at zero -- publishing a real futures PnL next to a
        # fabricated zero harvest, which is exactly the combination the bleed alarm reads as a
        # total bleed. `read_income` retries transient 5xx and returns None when it truly cannot
        # measure, so "unknown" survives all the way to the dashboard instead of decaying to 0.
        if state.get("start"):
            with _safe():
                start_ms = int(datetime.fromisoformat(str(state["start"])).timestamp() * 1000)
                # ONE income call, BOTH numbers -- `income_summary` has always returned the exact
                # paginated `commission` and this book read only `funding`, discarding the fee
                # bill that is the single largest term of the leak it was alarming about.
                inc = read_income(lambda: fut.income_summary(start_ms))
                if inc is not None:
                    funding = float(inc.get("funding", 0.0))
                    fut_commission = abs(float(inc.get("commission", 0.0)))
    return {"spot_pnl": round(spot_pnl, 2), "perp_pnl": round(perp_pnl, 2),
            "spot_realized": round(spot_realized, 2), "fut_pnl": round(fut_pnl, 2),
            "funding": None if funding is None else round(funding, 2), "net_pnl": round(net, 2),
            "fut_commission": None if fut_commission is None else round(fut_commission, 2),
            "notional": round(notional, 2)}


def _emit(rb: dict[str, Any], marks: dict[str, float | None], dry: bool) -> None:
    pos = rb["pos"]
    # CARRY-LEAK ALARM ON THE BOOK THAT HOLDS THE MONEY (2026-07-26). `carry_bleed_report` was
    # only ever wired into the MOLDED book (run_live_combined), so the PRIMARY executed book --
    # this file -- shipped a dashboard with NO bleed alarm at all, which is exactly how a leak
    # runs for weeks unnoticed. Same function, same thresholds, now on the executed book.
    # spot side = open marks + realized of closed spot legs; fut side = futures-equity delta.
    bleed = carry_bleed_report(funding=marks["funding"],
                               spot_pnl=round((marks["spot_pnl"] or 0.0)
                                              + (marks["spot_realized"] or 0.0), 2),
                               fut_pnl=marks.get("fut_pnl") or 0.0)
    # Attribute the leak ONLY when both terms are real measurements. With an unknown fee bill the
    # split would dump the entire commission into `residual`, manufacturing exactly the phantom
    # that `attribute_non_funding`'s own docstring warns against -- an unexplained quantity that
    # looks explained. No measurement is better than a confident wrong one.
    fut_comm = marks.get("fut_commission")
    leak = (attribute_non_funding(
        bleed.non_funding_pnl,
        dedup_basis(json.loads(_TRADES.read_text("utf-8")) if _TRADES.exists() else []),
        fut_comm)
        if bleed.non_funding_pnl is not None and fut_comm is not None else None)
    out = {
        "updated": datetime.now(tz=UTC).isoformat(),
        "mode": "dry" if dry else "live-paper",
        "strategy": "delta-neutral cash-and-carry (long spot + short perp, positive funding)",
        "executed": not dry, "n_carries": len(pos),
        "deployed_notional": marks["notional"],
        "net_pnl": marks["net_pnl"], "funding_harvested": marks["funding"],
        "spot_leg_pnl": marks["spot_pnl"], "perp_leg_pnl": marks["perp_pnl"],
        "spot_realized_pnl": marks["spot_realized"],
        "fut_leg_net": marks.get("fut_pnl", 0.0),
        "non_funding_pnl": bleed.non_funding_pnl,
        "harvest_eaten_frac": bleed.harvest_eaten_frac,
        "bleed_alert": bleed.alert, "bleed_verdict": bleed.verdict,
        # Publishes WHETHER the harvest was measured at all. Downstream (max_audit, the dashboard,
        # the molded book) must be able to tell "earned nothing" from "could not read the venue";
        # they are opposite states and only one of them is an execution problem.
        "funding_measured": bleed.measured,
        # WHERE the leak went, not just how big it is -- the alarm alone is unactionable and the
        # integrity watch is required to attribute it every cycle.
        "leak_attribution": leak,
        "fut_commission": marks.get("fut_commission"),
        "carries": [{"symbol": s, "qty": p["spot_qty"], "funding_8h": p["funding"]}
                    for s, p in pos.items()],
        "last_actions": rb["actions"],
        "risk": rb.get("risk"),
        "note": ("PRIMARY executed book (paper). Delta-neutral: spot hedges perp, profit = funding "
                 "harvested on the short perp. Builds the forward track record the gate sizes on."),
    }
    _WEB.parent.mkdir(parents=True, exist_ok=True)
    _WEB.write_text(json.dumps(out, indent=2, default=str), "utf-8")


def _live_params(top: int, hold_top: int, capital: float) -> tuple[int, int, float]:
    """LIVE-tunable params: override top / hold_top / capital from data/cashcarry_config.json each
    rebalance WITHOUT restarting the executor. Changing a param used to require the flatten+restart
    the 2026-07-10 churn fix needed; now just write the JSON and the running loop picks it up next
    cycle. argv are the defaults; any key present in the file overrides. Defensive -> any error
    (missing/corrupt file, bad type) silently falls back to the argv values."""
    try:
        if _CONFIG.exists():
            cfg = json.loads(_CONFIG.read_text("utf-8"))
            top = int(cfg.get("top", top))
            hold_top = int(cfg.get("hold_top", hold_top))
            capital = float(cfg.get("capital", capital))
    except (ValueError, TypeError, OSError):
        pass
    return top, hold_top, capital



def _foreign_executor_alive() -> bool:
    """True when a DIFFERENT live executor owns the heartbeat.

    SINGLE-BOOK INVARIANT (2026-07-26): two --live executors on one delta-neutral book
    double-order and churn. The startup-only lock could not catch a duplicate spawned during a
    slow heartbeat window -- both then refreshed the same file forever. Same failure the dead-man
    rail hit on 07-11 and fixed with a per-loop PID check; the executor now does the same.
    """
    try:
        parts = _HB.read_text("utf-8").split()
        if not parts or not parts[0].isdigit():
            return False                       # legacy/unowned heartbeat -- reclaim it
        pid = int(parts[0])
        if pid == os.getpid():
            return False
        return (time.time() - _HB.stat().st_mtime) < _HB_TICK * 2.5
    except (OSError, ValueError):
        return False


def main() -> None:
    # L1.42 STRICT: the executor must NOT trade under a tampered core or a doctrine
    # missing a law family. Every other organ pages and continues; here, refusing to
    # act IS the safe direction -- an unlawful trade cannot be undone.
    _law_guard(strict=True)
    ap = argparse.ArgumentParser()
    _enable_fee_burn()           # Gate-0 fee lever: on from the first tick
    ap.add_argument("--top", type=int, default=5, help="number of carries to hold (opens)")
    ap.add_argument("--hold-top", type=int, default=60,
                    help="hysteresis: keep a carry while it still pays positive funding (wide set)")
    ap.add_argument("--capital", type=float, default=2000.0)
    ap.add_argument("--minutes", type=float, default=0.0)
    ap.add_argument("--interval", type=float, default=600.0)
    ap.add_argument("--live", action="store_true")
    ap.add_argument("--no-maker", action="store_true", help="disable maker-first execution")
    args = ap.parse_args()
    global _MAKER
    _MAKER = not args.no_maker
    dry = not args.live
    if not (spot.has_keys() and fut.has_keys()):
        raise SystemExit("need BOTH spot-testnet and futures-testnet keys")

    # single-instance lock: a fresh heartbeat means another live executor runs (no double book).
    # STAND BY rather than exit. Exiting here returned 0, and under `Restart=always/RestartSec=15`
    # systemd respawned this process every ~19s for as long as the foreign owner lived -- the
    # IDENTICAL storm the kill path hit on 2026-07-13 (14,225 restarts over 3 days) and fixed by
    # idling instead of exiting. That fix was applied to the kill exit and left standing on this
    # one; on 2026-07-26 an orphaned pre-fix executor held the heartbeat and this path storm-
    # spawned ~190 processes/hour while the fixed code never got to run. Standing by also means
    # the book is picked up automatically the moment the foreign owner dies, instead of on the
    # next storm tick. `_foreign_executor_alive` is the SAME predicate the in-loop check uses
    # (PID-aware, reclaims a legacy/unowned heartbeat), so startup and runtime can no longer
    # disagree about who owns the book.
    standby_noted = False
    while not dry and _foreign_executor_alive():
        if not standby_noted:                     # log ONCE: a per-tick log is its own noise storm
            with contextlib.suppress(OSError):
                print(f"another cash-carry executor owns the book "
                      f"({_HB.read_text('utf-8').strip()}) -- standing by, not exiting "
                      f"(single-book invariant; will take over when it stops)")
            standby_noted = True
        time.sleep(_HB_TICK)

    forever = args.minutes <= 0
    deadline = time.monotonic() + args.minutes * 60.0
    print(f"CASH-CARRY executor | {'LIVE-PAPER' if args.live else 'DRY'} | top {args.top} | "
          f"${args.capital} | hb {_HB_TICK}s | rebalance {args.interval}s")
    last_work = 0.0
    jitter = 1.0                                          # +-15% cadence jitter (anti-front-run:
    rng = random.Random()                                 # a fixed 600s beat is detectable at size)
    killed = False
    while forever or time.monotonic() < deadline:
        if not dry and _foreign_executor_alive():
            print("another live executor owns the book -- exiting (single-book "
                  "invariant)")
            return
        if not dry:                                       # fast heartbeat (decoupled from work)
            _HB.parent.mkdir(parents=True, exist_ok=True)
            # PID-owned: lets every OTHER executor detect that it no longer owns
            # the book (single-book invariant, 2026-07-26).
            _HB.write_text(f"{os.getpid()} {datetime.now(tz=UTC).isoformat()}",
                           "utf-8")
        if _KILL.exists():
            # IDLE here instead of exiting: exiting made systemd respawn every ~17s for as long
            # as the kill file stood (14k restarts after the 2026-07-13 fire), which also starved
            # the daily data flywheel that rides this loop. Close everything (idempotent -- retried
            # while any leg remains), keep the flywheel + dashboard feeds alive, resume trading
            # automatically the moment the kill file is cleared.
            if not killed:
                print("KILL: closing all carries + idling until the kill file clears")
                killed = True
            with contextlib.suppress(Exception):
                _daily_data_tasks()                       # halted book must not starve the flywheel
            try:
                rb = _rebalance(0, 0, 0.0, dry=dry)       # top=0, hold=0 -> closes everything
            except Exception as exc:
                # A venue outage/ban must not kill the KILL loop: close-all is idempotent and
                # retried every tick while any leg remains. Crashing here made systemd respawn-
                # hammer a banned endpoint every ~5min (2026-07-31 418 incident).
                print(f"KILL: close-all deferred this tick ({exc})")
                time.sleep(_HB_TICK)
                continue
            with contextlib.suppress(Exception):
                _emit(rb, _mark(rb), dry)                 # dashboard stays honest while halted
            time.sleep(_HB_TICK)
            continue
        killed = False
        # EVERY tick: mark + write feeds (cheap, keeps the dashboard live). Orders every interval.
        try:
            if time.time() - last_work >= args.interval * jitter:
                _daily_data_tasks()                       # once per UTC day: archive OI/LS/taker
                top, hold_top, capital = _live_params(args.top, args.hold_top, args.capital)
                cap = _dynamic_capital(capital)           # dynamic-leverage sized (when proven)
                rb = _rebalance(top, hold_top, cap, dry=dry)   # places orders (live-tunable params)
                last_work = time.time()
                jitter = rng.uniform(0.85, 1.15)
            else:
                rb = _book_snapshot()                     # just read + mark (no orders)
            marks = _mark(rb)
            _emit(rb, marks, dry)
            if not dry:                                   # refresh the dashboard molded feed now
                with contextlib.suppress(Exception):
                    subprocess.run([sys.executable, "scripts/run_live_combined.py"],
                                   timeout=60, capture_output=True, check=False)
            print(f"[{datetime.now(UTC):%H:%M:%S}] carries={len(rb['pos'])} "
                  f"net=${marks['net_pnl']} funding=${marks['funding']} {rb['actions']}")
        except Exception as e:  # loop must survive transient errors -- but LOG them visibly
            with contextlib.suppress(Exception):
                _ERR.write_text(f"{datetime.now(tz=UTC).isoformat()} cycle error: {e!r}\n")
            print(f"cycle error (logged): {e!r}"[:200])
        if not forever and time.monotonic() >= deadline:
            break
        time.sleep(_HB_TICK)
    print("cash-carry executor done.")




# --- BNB FEE DISCOUNT (principal 2026-07-23; Gate-0 lever) -----------------------------------
# Live VIP0 fees (~20-25 bps round-trip) are the single biggest live drag on a book that turns
# over; BNB burn takes ~25% off. Maker-first is already implemented (_MAKER) -- this is the
# other, RISKLESS half, wired now so it is already ON at Gate 0 rather than a day-1 scramble.
# Best-effort + idempotent: a venue that lacks or rejects the endpoint changes nothing.
def _enable_fee_burn() -> None:
    """Switch BNB fee burn ON for futures and spot. Pure cost reduction, no risk surface."""
    with contextlib.suppress(Exception):
        fut._signed("/fapi/v1/feeBurn", {"feeBurn": "true"}, method="POST")
    with contextlib.suppress(Exception):
        spot._signed("/sapi/v1/bnbBurn", {"spotBNBBurn": "true"}, method="POST")


if __name__ == "__main__":
    main()

```

### scripts/run_deadman_switch.py
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

## TIER 2 -- your shard

### libs/alpha/health.py
```python
"""Alpha health monitoring — live vs expected, drift, and regime sensitivity.

Each component is a health score in [0, 1] (1 = meeting or beating expectation). The overall
health is the mean of the available components. Components with no expected baseline are skipped.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from libs.alpha.card import ExpectedMetrics, LiveMetrics


class AlphaHealth(BaseModel):
    model_config = ConfigDict(frozen=True)

    overall: float
    healthy: bool
    components: dict[str, float]

    def __bool__(self) -> bool:
        return self.healthy


def _clip01(x: float) -> float:
    return max(0.0, min(1.0, x))


def _higher_better(live: float | None, expected: float | None) -> float | None:
    """Health where a higher metric is better (sharpe, cagr, win rate, ...)."""
    if expected is None or live is None:
        return None
    if expected <= 0:
        return 1.0 if live >= expected else 0.0
    return _clip01(live / expected)


def _lower_better(live: float | None, expected: float | None) -> float | None:
    """Health where a lower metric is better (drawdown magnitude)."""
    if expected is None or live is None:
        return None
    if live <= 0:
        return 1.0
    if expected <= 0:
        return 0.0
    return _clip01(expected / live)


def calculate_alpha_health(
    expected: ExpectedMetrics, live: LiveMetrics, *, threshold: float = 0.6
) -> AlphaHealth:
    """Compute per-component health (live vs expected) and an overall score."""
    components: dict[str, float] = {}

    def add(name: str, value: float | None) -> None:
        if value is not None:
            components[name] = value

    add("sharpe", _higher_better(live.sharpe, expected.sharpe))
    add("cagr", _higher_better(live.cagr, expected.cagr))
    add("win_rate", _higher_better(live.win_rate, expected.win_rate))
    add("profit_factor", _higher_better(live.profit_factor, expected.profit_factor))
    add("expectancy", _higher_better(live.expectancy, expected.expectancy))
    add("drawdown_divergence", _lower_better(live.max_drawdown, expected.max_drawdown))
    add("regime_sensitivity", _clip01(live.regime_stability))

    if (
        expected.trade_mean is not None
        and expected.trade_std
        and live.trade_mean is not None
    ):
        shift = abs(live.trade_mean - expected.trade_mean) / expected.trade_std
        components["trade_distribution"] = _clip01(1.0 - shift)

    overall = sum(components.values()) / len(components) if components else 1.0
    return AlphaHealth(overall=overall, healthy=overall >= threshold, components=components)

```

### libs/alpha_factory/alpha_dna.py
```python
"""Alpha DNA — a structural fingerprint of an alpha.

The DNA captures *what kind* of strategy an alpha is (signal type, horizon, factor/regime
sensitivities, capacity, turnover, risk). It powers similarity, embedding, and "what makes
winners win" analysis. ``AlphaDNA`` itself lives in ``models``; this module builds and compares.
"""

from __future__ import annotations

import math
from collections.abc import Mapping

from libs.alpha_factory.models import AlphaDNA


def build_alpha_dna(
    *,
    signal_type: str,
    market: str,
    timeframe: str,
    holding_period: str,
    factor_exposures: Mapping[str, float] | None = None,
    regime_affinity: Mapping[str, float] | None = None,
    volatility_sensitivity: float = 0.0,
    trend_sensitivity: float = 0.0,
    mean_reversion_sensitivity: float = 0.0,
    capacity_estimate: float = 0.0,
    turnover_profile: float = 0.0,
    risk_profile: float = 0.0,
) -> AlphaDNA:
    """Construct an :class:`AlphaDNA` profile."""
    return AlphaDNA(
        signal_type=signal_type,
        market=market,
        timeframe=timeframe,
        holding_period=holding_period,
        factor_exposures=dict(factor_exposures or {}),
        regime_affinity=dict(regime_affinity or {}),
        volatility_sensitivity=volatility_sensitivity,
        trend_sensitivity=trend_sensitivity,
        mean_reversion_sensitivity=mean_reversion_sensitivity,
        capacity_estimate=capacity_estimate,
        turnover_profile=turnover_profile,
        risk_profile=risk_profile,
    )


def dna_distance(a: AlphaDNA, b: AlphaDNA) -> float:
    """Euclidean distance between two DNA scalar-gene vectors (0 = identical genes)."""
    return math.sqrt(sum((x - y) ** 2 for x, y in zip(a.numeric_vector(), b.numeric_vector(),
                                                       strict=True)))

```

### libs/alpha_factory/idea_ranking_engine.py
```python
"""Idea ranking engine — research the highest-value ideas first.

Scores future research ideas by expected edge, robustness, capacity, novelty, regime need, and
portfolio need, penalizing crowding, into a 0-100 priority. Ranking is total and deterministic.
"""

from __future__ import annotations

from collections.abc import Sequence

from libs.alpha_factory.models import IdeaCandidate, IdeaScore

_WEIGHTS: dict[str, float] = {
    "expected_edge": 0.25,
    "expected_robustness": 0.15,
    "expected_capacity": 0.10,
    "novelty": 0.15,
    "regime_need": 0.10,
    "portfolio_need": 0.10,
    "uncrowded": 0.15,
}


def _clip01(x: float) -> float:
    return max(0.0, min(1.0, x))


class IdeaRankingEngine:
    """Prioritizes research ideas by expected value."""

    def score(self, candidate: IdeaCandidate) -> IdeaScore:
        components = {
            "expected_edge": _clip01(candidate.expected_edge),
            "expected_robustness": _clip01(candidate.expected_robustness),
            "expected_capacity": _clip01(candidate.expected_capacity),
            "novelty": _clip01(candidate.novelty),
            "regime_need": _clip01(candidate.regime_need),
            "portfolio_need": _clip01(candidate.portfolio_need),
            "uncrowded": 1.0 - _clip01(candidate.crowding),
        }
        score = 100.0 * sum(_WEIGHTS[k] * v for k, v in components.items())
        return IdeaScore(
            idea_id=candidate.idea_id, category=candidate.category,
            idea_priority_score=score, components=components,
        )

    def rank(self, candidates: Sequence[IdeaCandidate]) -> list[IdeaScore]:
        scores = [self.score(c) for c in candidates]
        return sorted(scores, key=lambda s: s.idea_priority_score, reverse=True)

```

### libs/core/enums.py
```python
"""Core enumerations shared across the platform.

These are the single source of truth for environment, run-mode, and log-level vocabularies.
They are plain ``str`` enums so they serialize cleanly to YAML/JSON and SQLite.
"""

from __future__ import annotations

from enum import StrEnum


class Environment(StrEnum):
    """Deployment environment. Selects which ``config/<env>.yaml`` overlay is loaded."""

    DEV = "dev"
    LIVE = "live"
    TEST = "test"


class RunMode(StrEnum):
    """The three run modes of the single codebase (Architecture v1.0)."""

    RESEARCH = "research"
    TRADE = "trade"
    OPS = "ops"


class LogLevel(StrEnum):
    """Logging verbosity levels, mirroring the stdlib level names."""

    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"

    @property
    def numeric(self) -> int:
        """Return the stdlib numeric level for this name."""
        import logging

        return int(getattr(logging, self.value))

```

### libs/costs/params.py
```python
"""Per-instrument Fusion cost parameters.

All-in cost is modelled, never the advertised "zero spread": raw spread + commission +
slippage + financing + (optional) gap risk. Defaults are reasoned priors for a Fusion Zero
ECN account and are deliberately conservative; calibrate against realized fills before live.

Round-turn convention: ``spread_price`` is the *full* spread paid over a round turn;
``slippage_price_per_side`` is applied on entry and exit.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from libs.costs.errors import CostError


class CostParams(BaseModel):
    """Cost parameters for one instrument (prices in quote units, money in account ccy)."""

    model_config = ConfigDict(frozen=True)

    instrument: str
    contract_size: float = Field(gt=0)  # units per lot (oz, base ccy, index points)
    commission_per_lot: float = Field(ge=0)  # round-turn commission per lot
    spread_price: float = Field(ge=0)  # full round-turn spread in price units
    slippage_price_per_side: float = Field(ge=0)
    swap_long_per_lot_per_night: float = 0.0  # positive = cost to hold long overnight
    swap_short_per_lot_per_night: float = 0.0
    gap_risk_fraction: float = Field(ge=0, default=0.0)  # expected adverse gap, fraction of price


_DEFAULTS: dict[str, CostParams] = {
    p.instrument: p
    for p in (
        CostParams(
            instrument="EURUSD", contract_size=100_000, commission_per_lot=7.0,
            spread_price=0.00002, slippage_price_per_side=0.00001,
            swap_long_per_lot_per_night=0.7, swap_short_per_lot_per_night=0.3,
            gap_risk_fraction=0.002,
        ),
        CostParams(
            instrument="GBPUSD", contract_size=100_000, commission_per_lot=7.0,
            spread_price=0.00003, slippage_price_per_side=0.000015,
            swap_long_per_lot_per_night=0.8, swap_short_per_lot_per_night=0.4,
            gap_risk_fraction=0.0025,
        ),
        CostParams(
            instrument="USDJPY", contract_size=100_000, commission_per_lot=7.0,
            spread_price=0.003, slippage_price_per_side=0.0015,
            swap_long_per_lot_per_night=0.6, swap_short_per_lot_per_night=0.5,
            gap_risk_fraction=0.002,
        ),
        CostParams(
            instrument="XAUUSD", contract_size=100, commission_per_lot=7.0,
            spread_price=0.12, slippage_price_per_side=0.03,
            swap_long_per_lot_per_night=5.0, swap_short_per_lot_per_night=4.0,
            gap_risk_fraction=0.01,
        ),
        CostParams(
            instrument="XAGUSD", contract_size=5_000, commission_per_lot=7.0,
            spread_price=0.012, slippage_price_per_side=0.004,
            swap_long_per_lot_per_night=4.0, swap_short_per_lot_per_night=3.0,
            gap_risk_fraction=0.015,
        ),
        CostParams(
            instrument="US500", contract_size=1, commission_per_lot=0.0,
            spread_price=0.5, slippage_price_per_side=0.2,
            swap_long_per_lot_per_night=2.0, swap_short_per_lot_per_night=1.5,
            gap_risk_fraction=0.01,
        ),
        CostParams(
            instrument="NAS100", contract_size=1, commission_per_lot=0.0,
            spread_price=1.5, slippage_price_per_side=0.5,
            swap_long_per_lot_per_night=2.5, swap_short_per_lot_per_night=2.0,
            gap_risk_fraction=0.012,
        ),
        CostParams(
            instrument="BTCUSD", contract_size=1, commission_per_lot=0.0,
            spread_price=20.0, slippage_price_per_side=10.0,
            swap_long_per_lot_per_night=15.0, swap_short_per_lot_per_night=12.0,
            gap_risk_fraction=0.03,
        ),
    )
}

DEFAULT_COST_PARAMS: dict[str, CostParams] = dict(_DEFAULTS)


def get_cost_params(
    instrument: str, registry: dict[str, CostParams] | None = None
) -> CostParams:
    """Return cost params for ``instrument`` from ``registry`` (defaults if omitted)."""
    table = registry if registry is not None else DEFAULT_COST_PARAMS
    try:
        return table[instrument]
    except KeyError as exc:
        raise CostError(f"no cost parameters for instrument {instrument!r}") from exc

```

### libs/data/lake.py
```python
"""Parquet medallion lake (Bronze / Silver / Gold).

Hive-partitioned by ``year``/``month`` under ``{base}/{layer}/{asset_class}/{symbol}/{tf}`` for
DuckDB partition pruning. Writes replace matching month partitions (corrections create new
partition contents); dataset-level immutability is enforced via the store's snapshot catalog.
"""

from __future__ import annotations

from enum import StrEnum
from pathlib import Path

import pandas as pd
import pyarrow as pa
import pyarrow.dataset as ds

from libs.data.instruments import get_spec
from libs.data.schema import BAR_COLUMNS, TIMESTAMP, empty_bars, validate_bars
from libs.data.timeframe import Timeframe

_PARTITION_COLS = ["year", "month"]


class Layer(StrEnum):
    BRONZE = "bronze"
    SILVER = "silver"
    GOLD = "gold"


class ParquetLake:
    """Read/write bars to the partitioned Parquet lake."""

    def __init__(self, base_dir: str | Path) -> None:
        self.base_dir = Path(base_dir)

    def path(self, layer: Layer, symbol: str, timeframe: Timeframe) -> Path:
        spec = get_spec(symbol)
        return self.base_dir / layer.value / spec.asset_class.value / symbol / timeframe.value

    def write_bars(
        self, layer: Layer, symbol: str, timeframe: Timeframe, df: pd.DataFrame
    ) -> Path:
        """Write a bar frame to the lake, partitioned by year/month. Returns its path."""
        validate_bars(df)
        path = self.path(layer, symbol, timeframe)
        if df.empty:
            path.mkdir(parents=True, exist_ok=True)
            return path
        out = df.copy()
        out["year"] = out[TIMESTAMP].dt.year.astype("int32")
        out["month"] = out[TIMESTAMP].dt.month.astype("int32")
        table = pa.Table.from_pandas(out, preserve_index=False)
        ds.write_dataset(
            table,
            base_dir=str(path),
            format="parquet",
            partitioning=_PARTITION_COLS,
            partitioning_flavor="hive",
            existing_data_behavior="delete_matching",
            basename_template="part-{i}.parquet",
        )
        return path

    def read_bars(
        self,
        layer: Layer,
        symbol: str,
        timeframe: Timeframe,
        *,
        start: pd.Timestamp | None = None,
        end: pd.Timestamp | None = None,
    ) -> pd.DataFrame:
        """Read bars back from the lake, sorted ascending, in the canonical schema (+ extras)."""
        path = self.path(layer, symbol, timeframe)
        if not path.exists() or not any(path.rglob("*.parquet")):
            return empty_bars()
        table = ds.dataset(
            str(path), format="parquet", partitioning="hive"
        ).to_table()
        df = table.to_pandas()
        df = df.drop(columns=[c for c in _PARTITION_COLS if c in df.columns])
        df[TIMESTAMP] = pd.to_datetime(df[TIMESTAMP], utc=True)
        df = df.sort_values(TIMESTAMP).reset_index(drop=True)
        if start is not None:
            df = df[df[TIMESTAMP] >= start]
        if end is not None:
            df = df[df[TIMESTAMP] <= end]
        df = df.reset_index(drop=True)
        ordered = [*BAR_COLUMNS, *[c for c in df.columns if c not in BAR_COLUMNS]]
        return validate_bars(df[ordered], require_sorted=True)

```

### libs/data/onchain_flows.py
```python
"""On-chain stablecoin EXCHANGE-RESERVE reader -- keyless, free, no API key.

Reads the USDT + USDC balances held by known exchange hot wallets via public Ethereum JSON-RPC
(`eth_call` -> ERC-20 `balanceOf`), summed into a total exchange stablecoin reserve. Daily netflow =
day-over-day change in that reserve (the standard CryptoQuant-style "exchange netflow" metric):
reserve UP = net inflow (stables parked on exchanges = dry powder / potential buy pressure); reserve
DOWN = net outflow (stables leaving exchanges). The sign of the edge is an empirical question.
Orthogonal to funding + price -> validated forward, never assumed.

No key, no paid tier: uses public RPC endpoints (fallback across several) and publicly-labelled
exchange addresses. Cheap -- a handful of eth_call per run, not a log scan. Pure/stdlib (urllib).
"""

from __future__ import annotations

import json
import urllib.request
from typing import Any

# public, keyless Ethereum JSON-RPC endpoints (tried in order with fallback)
_RPCS = (
    "https://ethereum-rpc.publicnode.com",
    "https://eth.llamarpc.com",
    "https://cloudflare-eth.com",
    "https://rpc.ankr.com/eth",
)

# ERC-20 stablecoins (6 decimals both)
_TOKENS = {
    "USDT": ("0xdAC17F958D2ee523a2206206994597C13D831ec7", 6),
    "USDC": ("0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48", 6),
}

# publicly-labelled exchange hot wallets (Etherscan-tagged; public data)
_EXCHANGE_WALLETS = {
    "binance": [
        "0x28C6c06298d514Db089934071355E5743bf21d60",
        "0x21a31Ee1afC51d94C2eFcCAa2092aD1028285549",
        "0xDFd5293D8e347dFe59E90eFd55b2956a1343963d",
        "0x9696f59E4d72E237BE84fFD425DCaD154Bf96976",
        "0x4976A4A02f38326660D17bf34b431dC6e2eb2327",
    ],
    "coinbase": [
        "0x71660c4005BA85c37ccec55d0C4493E66Fe775d3",
        "0x503828976D22510aad0201ac7EC88293211D23Da",
        "0xdDBd2B932c763bA5b1b7AE3B362eac3e8d40121A",
        # Coinbase Prime 1 -- custodian wallet holding ~$16M USDC+USDT (verified 2026-07-04)
        "0xcd531ae9efcce479654c4926dec5f6209531ca7b",
    ],
    # OKX and Kraken hold negligible L1 USDT/USDC; they route stablecoins via L2s / internal nets.
    # Checked 2026-07-04: best OKX L1 address holds <$2K, Kraken <$3K. Not added.
    "okx": [
        "0x5041ed759Dd4aFc3a72b8192C143F72f4724081A",
        "0x236F9F97e0E62388479bf9E5BA4889e46B0273C3",
    ],
}

_BALANCE_OF = "0x70a08231"                              # ERC-20 balanceOf(address) selector
_TOTAL_SUPPLY = "0x18160ddd"                            # ERC-20 totalSupply() selector


def _rpc(method: str, params: list[Any]) -> Any:
    """One JSON-RPC call with fallback across public endpoints. Returns the `result` or raises."""
    body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params}).encode()
    last: Exception | None = None
    for url in _RPCS:
        try:
            req = urllib.request.Request(url, data=body,
                                         headers={"Content-Type": "application/json",
                                                  "User-Agent": "quant-onchain/1.0"})
            with urllib.request.urlopen(req, timeout=20) as r:
                out = json.loads(r.read())
            if "result" in out:
                return out["result"]
            last = RuntimeError(str(out.get("error"))[:120])
        except Exception as e:  # try the next endpoint
            last = e
    raise RuntimeError(f"all RPC endpoints failed: {last!r}")


def erc20_balance(token_addr: str, holder: str, decimals: int) -> float:
    """ERC-20 balanceOf(holder) in whole tokens (keyless eth_call)."""
    data = _BALANCE_OF + holder.lower().removeprefix("0x").rjust(64, "0")
    res = _rpc("eth_call", [{"to": token_addr, "data": data}, "latest"])
    return int(res, 16) / (10 ** decimals) if res and res != "0x" else 0.0


def stablecoin_supply() -> dict[str, Any]:
    """Total USDT + USDC supply on Ethereum L1 (keyless eth_call -> totalSupply).

    Daily change in total supply = net minting/burning = global new-capital signal.
    Orthogonal to exchange reserves: reserves measure WHERE stables are; supply measures HOW MANY.
    """
    totals: dict[str, float] = {}
    for name, (addr, dec) in _TOKENS.items():
        res = _rpc("eth_call", [{"to": addr, "data": _TOTAL_SUPPLY}, "latest"])
        totals[name] = int(res, 16) / (10 ** dec) if res and res != "0x" else 0.0
    total = round(sum(totals.values()), 2)
    return {"total_supply_usd": total,
            "per_token": {k: round(v, 2) for k, v in totals.items()}}


def exchange_reserves() -> dict[str, Any]:
    """Total USDT+USDC held by the tracked exchange hot wallets, plus a per-exchange breakdown."""
    per_exchange: dict[str, float] = {}
    per_token: dict[str, float] = dict.fromkeys(_TOKENS, 0.0)
    for exch, wallets in _EXCHANGE_WALLETS.items():
        subtotal = 0.0
        for token, (addr, dec) in _TOKENS.items():
            for w in wallets:
                bal = erc20_balance(addr, w, dec)
                subtotal += bal
                per_token[token] += bal
        per_exchange[exch] = round(subtotal, 2)
    total = round(sum(per_token.values()), 2)
    return {"total_reserve_usd": total,
            "per_token": {k: round(v, 2) for k, v in per_token.items()},
            "per_exchange": per_exchange,
            "n_wallets": sum(len(w) for w in _EXCHANGE_WALLETS.values())}

```

### libs/execution/paper_broker.py
```python
"""Paper broker — a deterministic in-memory gateway for demo/paper trading.

Implements the :class:`BrokerGateway` protocol with deterministic fills at a per-symbol mark price
(plus optional fixed slippage), idempotent dedup, and position tracking. No real capital and no
external connectivity: this is the demo/paper execution venue. The real venue is ``MT5Broker``.
"""

from __future__ import annotations

from libs.execution.broker import BrokerOrderResult, BrokerPosition, OrderRequest


class PaperBroker:
    """A deterministic, idempotent paper-trading broker (no live capital)."""

    def __init__(self, *, default_price: float = 100.0, slippage_bps: float = 0.0) -> None:
        self.default_price = default_price
        self.slippage_bps = slippage_bps
        self._prices: dict[str, float] = {}
        self._by_client: dict[str, BrokerOrderResult] = {}
        self._positions: dict[str, list[float]] = {}  # instrument -> [qty, avg]
        self._next_ticket = 1

    def set_price(self, instrument: str, price: float) -> None:
        self._prices[instrument] = price

    def _fill_price(self, instrument: str, side: str) -> float:
        mark = self._prices.get(instrument, self.default_price)
        slip = mark * (self.slippage_bps / 1e4)
        return mark + slip if side == "buy" else mark - slip  # adverse slippage

    # --- BrokerGateway protocol ------------------------------------------------
    def place_order(self, request: OrderRequest) -> BrokerOrderResult:
        if request.idempotency_key in self._by_client:
            return self._by_client[request.idempotency_key]  # idempotent dedup
        ticket = self._next_ticket
        self._next_ticket += 1
        price = self._fill_price(request.instrument, request.side)
        self._apply_position(request, price)
        result = BrokerOrderResult(
            client_order_id=request.idempotency_key, broker_order_id=ticket, status="filled",
            filled_qty=request.qty, fill_price=price, deal_id=ticket, message="paper fill",
        )
        self._by_client[request.idempotency_key] = result
        return result

    def _apply_position(self, request: OrderRequest, price: float) -> None:
        signed = request.qty if request.side == "buy" else -request.qty
        qty, avg = self._positions.get(request.instrument, [0.0, 0.0])
        new_qty = qty + signed
        if qty == 0:
            new_avg = price
        elif (qty > 0) == (signed > 0) and new_qty != 0:
            new_avg = (avg * abs(qty) + price * abs(signed)) / abs(new_qty)
        else:
            new_avg = price if new_qty != 0 else 0.0
        self._positions[request.instrument] = [new_qty, new_avg]

    def cancel_order(self, broker_order_id: int) -> bool:
        return True

    def get_positions(self) -> list[BrokerPosition]:
        return [
            BrokerPosition(instrument=sym, qty=qa[0], avg_price=qa[1])
            for sym, qa in self._positions.items()
            if qa[0] != 0
        ]

    def get_order(self, client_order_id: str) -> BrokerOrderResult | None:
        return self._by_client.get(client_order_id)

```

### libs/execution/staging.py
```python
"""Live-deployment stage machine (S0 -> S1 -> S2). Pure state logic, no exchange calls.

Per docs/LIVE_CONNECTOR_SPEC.md section 2:
  S0 testnet/paper (current) -> S1 live-minimum -> S2 full automation.
  S1 entry (Gate 0): principal places keys + explicit sign-off; capital fraction <= 0.10 of
    authorized live capital; 4-5 liquid symbols at venue-minimum notional.
  S2 entry (automatic, ALL must hold): >=8 weeks live, >=10 resolved calibration rows, 0
    critical drill failures, realized cost <= 1.25x modeled.
  Any tripwire demotes ONE stage instantly; demotions are unlimited and never gated. Promotion
  never skips a stage. Every transition is logged to state["history"] for auditability.

State lives in data/stage_state.json. This module only reads/writes that file and evaluates the
evidence dict the CALLER supplies -- it does not itself measure live_weeks, calibration rows,
etc. (those live in their own state files); keeping the gate arithmetic here and the measurement
elsewhere keeps this file pure and easy to property-test.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from libs.core.logging import get_logger

# OBSERVABILITY (gap #56, 2026-07-29): the state file records WHERE the machine is; the log
# records WHY it moved, at the moment it moved. state["history"] survives, but a demotion that
# is instantly followed by a crash left no trail of the reason before this. Library never
# configures handlers -- the owning script does.
_log = get_logger(__name__)

_STATE = Path("data/stage_state.json")
_STAGES = ("S0", "S1", "S2")


def _load() -> dict[str, Any]:
    try:
        d = json.loads(_STATE.read_text("utf-8"))
        if isinstance(d, dict) and d.get("stage") in _STAGES:
            d.setdefault("history", [])
            return d
    except (OSError, json.JSONDecodeError):
        pass
    return {"stage": "S0", "history": []}


def _save(state: dict[str, Any]) -> None:
    _STATE.write_text(json.dumps(state, indent=2), "utf-8")


def current_stage() -> str:
    return str(_load().get("stage", "S0"))


def s1_entry_met(evidence: dict[str, Any]) -> tuple[bool, str]:
    """Mechanical S1 (Gate 0) preconditions. ``principal_signoff`` is a human act the caller
    records after the fact -- this function never fabricates consent, it only checks the flag."""
    checks = {
        "principal_signoff": bool(evidence.get("principal_signoff")),
        "capital_fraction_le_010": float(evidence.get("capital_fraction", 1.0)) <= 0.10,
        "symbol_count_4_5": 4 <= int(evidence.get("symbol_count", 0)) <= 5,
        "keys_present": bool(evidence.get("keys_present")),
        "connector_verified": bool(evidence.get("connector_verified")),
    }
    return all(checks.values()), ", ".join(f"{k}={v}" for k, v in checks.items())


def s2_entry_met(evidence: dict[str, Any]) -> tuple[bool, str]:
    """S2 entry: automatic, numeric, no discretionary language -- ALL must hold."""
    checks = {
        "live_weeks_ge_8": float(evidence.get("live_weeks", 0.0)) >= 8.0,
        "calibration_rows_ge_10": int(evidence.get("calibration_rows", 0)) >= 10,
        # FAIL-CLOSED DEFAULT. Found independently by mutation testing TWICE: this account
        # 2026-07-26 (default flipped 0 -> 1) and the other account 2026-07-29 (default -> -1,
        # gap #53), three days apart, same bug. This read
        # `evidence.get("critical_drill_failures", 0) == 0`, so an ABSENT drill record was treated
        # as "zero failures" and the S2 gate PASSED on missing evidence. Every other check here
        # already defaults to the refusing side (live_weeks 0.0, calibration_rows 0, cost_ratio
        # 999.0); this one alone defaulted permissive. A sentinel of -1 keeps "0 failures" as the
        # only passing value while making "no record" a refusal. Direction is strictly
        # conservative: this can only ever DECLINE a promotion, never authorise a trade.
        "critical_drill_failures_eq_0": int(evidence.get("critical_drill_failures", -1)) == 0,
        "realized_cost_le_1_25x": float(evidence.get("cost_ratio", 999.0)) <= 1.25,
    }
    return all(checks.values()), ", ".join(f"{k}={v}" for k, v in checks.items())


def promote(evidence: dict[str, Any]) -> tuple[bool, str]:
    """Attempt to advance exactly one stage. Never skips S1 to reach S2 from S0."""
    state = _load()
    stage = state["stage"]
    if stage == "S0":
        met, why = s1_entry_met(evidence)
        target = "S1"
    elif stage == "S1":
        met, why = s2_entry_met(evidence)
        target = "S2"
    else:
        return False, "already at S2 (terminal stage)"
    if not met:
        _log.info("promote REFUSED from %s: %s", stage, why)
        return False, f"gate not met: {why}"
    state["stage"] = target
    state["history"].append({
        "ts": datetime.now(tz=UTC).isoformat(), "action": "promote",
        "from": stage, "to": target, "evidence": why,
    })
    _save(state)
    _log.warning("STAGE PROMOTED %s -> %s: %s", stage, target, why)
    return True, f"promoted {stage} -> {target}: {why}"


def demote(reason: str) -> tuple[bool, str]:
    """Demote exactly one stage. Unlimited, instant, never gated by evidence."""
    state = _load()
    stage = state["stage"]
    idx = _STAGES.index(stage)
    if idx == 0:
        return False, "already at S0 (floor stage)"
    target = _STAGES[idx - 1]
    state["stage"] = target
    state["history"].append({
        "ts": datetime.now(tz=UTC).isoformat(), "action": "demote",
        "from": stage, "to": target, "reason": reason,
    })
    _save(state)
    # A demotion is the risk machinery working; it is logged at WARNING because it must be
    # visible in any live-session log without raising the level.
    _log.warning("STAGE DEMOTED %s -> %s: %s", stage, target, reason)
    return True, target

```

### libs/ops/errors.py
```python
"""Operational-resilience errors."""

from __future__ import annotations

from libs.core.errors import QuantPlatformError


class OpsError(QuantPlatformError):
    """Base error for backup/restore/watchdog/safe-halt operations."""

```

### libs/ops/watchdog.py
```python
"""Process watchdog and safe-halt orchestration (fail-closed).

The watchdog turns heartbeat silence into a restart recommendation; the safe-halt controller
fuses the platform's hard stop signals (reconciliation divergence, drawdown HALT level, heartbeat
loss, unresolved critical alerts) into a single deterministic halt decision. It recommends the
halt — the execution/risk layer enforces it — so this stays a pure, auditable decision function.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from libs.risk.drawdown import DrawdownLevel


class ProcessWatchdog:
    """Heartbeat liveness: recommends a restart when a process goes silent too long."""

    def __init__(self, *, max_silence_seconds: float) -> None:
        self.max_silence_seconds = max_silence_seconds

    def alive(self, *, last_beat_epoch: float, now_epoch: float) -> bool:
        return (now_epoch - last_beat_epoch) <= self.max_silence_seconds

    def action(self, *, last_beat_epoch: float, now_epoch: float) -> str:
        alive = self.alive(last_beat_epoch=last_beat_epoch, now_epoch=now_epoch)
        return "ok" if alive else "restart"


class HaltDecision(BaseModel):
    model_config = ConfigDict(frozen=True)

    halt: bool
    reasons: list[str] = Field(default_factory=list)


class SafeHaltController:
    """Fuses hard stop signals into one fail-closed halt decision (recommend-only)."""

    def evaluate(
        self,
        *,
        reconciliation_divergence: bool = False,
        drawdown_level: DrawdownLevel = DrawdownLevel.NORMAL,
        heartbeat_alive: bool = True,
        critical_alerts: int = 0,
    ) -> HaltDecision:
        reasons: list[str] = []
        if reconciliation_divergence:
            reasons.append("reconciliation divergence")
        if drawdown_level is DrawdownLevel.HALT:
            reasons.append("drawdown governor at HALT")
        if not heartbeat_alive:
            reasons.append("heartbeat lost")
        if critical_alerts > 0:
            reasons.append(f"{critical_alerts} unresolved critical alert(s)")
        return HaltDecision(halt=bool(reasons), reasons=reasons)

```

### libs/research/anytime_valid.py
```python
"""Always-valid (anytime) sequential testing for forward validation -- gap #25.

WHY THIS EXISTS
The desk's forward gate is a fixed 40/90-day clock. That is safe but blunt: a genuinely strong
edge waits the full calendar even once its evidence is overwhelming, and a weak one consumes the
same budget. The principal asked to cut 90 -> 40 days. That is the WRONG lever -- it buys speed by
lowering the evidence bar for everything, including noise.

The right lever is an e-process. Under H0 (mean <= 0) the capital process below is a non-negative
supermartingale, so by Ville's inequality:

    P( sup_t  E_t >= 1/alpha )  <=  alpha

That bound holds at EVERY t simultaneously -- so you may peek daily, stop the instant E_t
crosses 1/alpha, and the type-I error is still <= alpha.

MEASURED RESULT (Monte Carlo, 2026-07-22) -- READ THIS BEFORE USING IT AS A SPEEDUP:
  null (no edge)      : 3/300 paths crossed = 1.0% at alpha=0.01  -> type-I control VERIFIED
  strong (Sharpe ~2)  : 6/40 graduated, MEDIAN 132 days           -> SLOWER than the fixed 90d
  weak (Sharpe ~0.3)  : 0/40 graduated                            -> correctly rejects
This test is RIGOROUS, not FAST. A Sharpe-2 edge on daily returns has per-observation signal
~0.105, so the e-process grows at ~mu^2/2sigma^2 ~ 0.0055/day and needs ~800 days to reach
log(1/alpha). That is fundamental to e-processes on weak per-observation signal, not an
implementation flaw. CONCLUSION: this does NOT replace the 40/90d clock to go faster -- it is
a stricter SECONDARY check. The only real accelerants are MORE OBSERVATIONS (higher frequency
or cross-sectional breadth), never a cleverer test. There is no free lunch on validation speed.

This does NOT replace the desk's economic gates (orthogonality, capacity, cost, crowding). It
replaces only the "how long must we wait" question.

Pure numpy/stdlib, deterministic, offline -- cheap to run every cycle.
"""
from __future__ import annotations

import numpy as np

# Mixture grid over the betting fraction. Small lambdas are conservative (slow but robust to fat
# tails); large lambdas grow fast on a real edge. Mixing means we never have to pick one.
_LAMBDAS = np.linspace(0.02, 0.45, 40)
_MIN_OBS = 20                     # below this the estimate of scale is not trustworthy


def e_value(returns: np.ndarray | list[float]) -> float:
    """Mixture e-value for H0: mean(returns) <= 0. Larger = stronger evidence AGAINST H0.

    Each component is the capital of a bettor wagering fraction ``lam`` of its bankroll on the
    next standardized return: prod(1 + lam * z_i). Capital is mixed uniformly over ``_LAMBDAS``,
    which is itself a valid e-value (a convex mixture of e-values is an e-value)."""
    r = np.asarray(returns, dtype="float64")
    r = r[np.isfinite(r)]
    if r.size < _MIN_OBS:
        return 0.0
    s = float(r.std(ddof=1))
    if s <= 0.0:
        return 0.0
    z = r / s
    # keep every component strictly positive: 1 + lam*z > 0  <=>  lam < 1/max(-z)
    worst = float(np.min(z))
    lam_max = 0.99 / abs(worst) if worst < 0 else float(_LAMBDAS[-1])
    lams = _LAMBDAS[lam_max > _LAMBDAS]
    if lams.size == 0:
        return 0.0
    # work in logs for numerical stability, then mix
    log_caps = np.array([np.sum(np.log1p(lam * z)) for lam in lams])
    m = float(np.max(log_caps))
    mix = m + np.log(np.mean(np.exp(log_caps - m)))
    return float(np.exp(mix))


def graduates(returns: np.ndarray | list[float], *, alpha: float = 0.01) -> dict[str, float | bool]:
    """Anytime-valid verdict. Safe to call every day on the same growing series.

    alpha=0.01 is deliberately stricter than a usual 0.05: this gate can be peeked at daily and
    the desk's whole failure mode is promoting noise."""
    e = e_value(returns)
    thr = 1.0 / alpha
    return {"e_value": round(e, 4), "threshold": thr, "graduates": bool(e >= thr),
            "n": int(np.size(returns)), "alpha": alpha}


def days_to_graduation(returns: np.ndarray | list[float], *, alpha: float = 0.01) -> int | None:
    """First index at which the e-process would have crossed -- i.e. how much calendar the
    always-valid rule would have SAVED versus a fixed clock. None if it never crosses."""
    r = np.asarray(returns, dtype="float64")
    for t in range(_MIN_OBS, r.size + 1):
        if e_value(r[:t]) >= 1.0 / alpha:
            return t
    return None

```

### libs/research/tail_funding.py
```python
"""Cross-venue funding divergence on the THIN TAIL of the perp universe -- a §42 hunting ground.

The desk already screens funding on the liquid names. Those are exactly the names where every
funded arbitrageur is already looking, so a divergence there is either gone before you reach it or
compensation for a risk you have not identified. §42 says the structural advantage is the opposite
end: symbols too small to be worth a fund's operational effort. A $30k open-interest perp listed on
two venues can carry a persistent funding gap for days simply because nobody with capital has
bothered to build the plumbing for a position that size.

THE UNIT OF THE SCREEN IS THE ANNUALISED SPREAD, NOT THE RAW RATE. A raw funding rate says how rich
one venue is; the SPREAD between two venues on the same instrument is the part that is harvestable
delta-neutral (long the cheap venue, short the rich one), which is the only form a book this size
should care about. Annualising is what makes it comparable to every other carry number the desk
already reasons about.

WHAT THIS IS NOT. It is a SCREEN, not a signal and not a strategy. It logs candidates and their
persistence; promotion is the ordinary gate's business, and a spread that looks enormous is usually
either a stale quote, a symbol that is about to be delisted on one side, or a venue that cannot
actually be traded at that size. Those are the failure modes the filters below exist for.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

#: Funding settles every 8h on both venues screened, so a rate is 3x/day, 1095x/year.
_INTERVALS_PER_YEAR = 3 * 365
#: Below this the spread is not worth the two-venue operational overhead at any size.
MIN_SPREAD_ANNUAL = 0.10
#: Above this it is almost certainly a stale quote or a symbol in trouble, not an edge. Screened
#: OUT rather than ranked first -- the biggest number in a noisy panel is the likeliest artifact,
#: and a screen that sorts by magnitude finds its own worst data every single day.
MAX_CREDIBLE_ANNUAL = 5.00


class VenueQuote(BaseModel):
    """One venue's funding picture for one symbol."""

    model_config = ConfigDict(frozen=True)

    symbol: str
    venue: str
    funding_rate: float               # per 8h interval
    open_interest_usd: float = 0.0


class Divergence(BaseModel):
    """A harvestable funding gap on one symbol across two venues."""

    model_config = ConfigDict(frozen=True)

    symbol: str
    long_venue: str                   # cheap side: funding is lowest (you are paid to be long)
    short_venue: str                  # rich side
    spread_annual: float
    min_oi_usd: float                 # the BINDING side -- capacity is the thinner leg
    credible: bool
    note: str = ""


def annualise(rate_per_interval: float) -> float:
    """A per-8h funding rate as an annual fraction."""
    return float(rate_per_interval) * _INTERVALS_PER_YEAR


def tail_universe(quotes: list[VenueQuote], *, quantile: float = 0.5) -> set[str]:
    """Symbols in the THIN end of the universe by open interest -- where the desk has an edge.

    Deliberately a QUANTILE of the observed universe rather than a dollar cutoff: what counts as
    "thin" is a fact about the venue's current universe, and a hardcoded dollar line would rot the
    same way the flat $100k capacity floor did. Taking the bottom half by default is a screen, not
    a claim -- the capacity gate decides fillability afterwards.
    """
    by_symbol: dict[str, float] = {}
    for q in quotes:
        by_symbol[q.symbol] = max(by_symbol.get(q.symbol, 0.0), q.open_interest_usd)
    known = sorted(v for v in by_symbol.values() if v > 0)
    if not known:
        return set(by_symbol)             # no OI data -> screen everything rather than nothing
    # ceil(n*q) - 1, NOT int(n*q): with two symbols and q=0.5 the latter indexes the LARGER one and
    # the "thin tail" quietly becomes the whole universe -- a screen that selects everything is not
    # a screen, and it would have pointed this straight back at the liquid names §42 avoids.
    import math
    idx = max(0, min(len(known) - 1, math.ceil(len(known) * quantile) - 1))
    cutoff = known[idx]
    return {s for s, oi in by_symbol.items() if oi <= cutoff or oi <= 0}


def divergences(
    quotes: list[VenueQuote],
    *,
    min_spread_annual: float = MIN_SPREAD_ANNUAL,
    tail_only: bool = True,
) -> list[Divergence]:
    """Cross-venue funding gaps, thin-tail first, with the implausible ones flagged not ranked.

    Capacity is reported as the MINIMUM open interest across the two legs, because a delta-neutral
    pair can only be as large as its thinner side -- taking the larger leg's depth would overstate
    what is actually harvestable, which is the same "capacity you cannot fill" error §42 is about.
    """
    tail = tail_universe(quotes) if tail_only else {q.symbol for q in quotes}
    grouped: dict[str, list[VenueQuote]] = {}
    for q in quotes:
        if q.symbol in tail:
            grouped.setdefault(q.symbol, []).append(q)

    out: list[Divergence] = []
    for symbol, qs in grouped.items():
        if len({q.venue for q in qs}) < 2:
            continue                      # one venue is not a spread
        cheap = min(qs, key=lambda q: q.funding_rate)
        rich = max(qs, key=lambda q: q.funding_rate)
        spread = annualise(rich.funding_rate - cheap.funding_rate)
        if spread < min_spread_annual:
            continue
        credible = spread <= MAX_CREDIBLE_ANNUAL
        out.append(Divergence(
            symbol=symbol, long_venue=cheap.venue, short_venue=rich.venue,
            spread_annual=round(spread, 4),
            min_oi_usd=round(min(cheap.open_interest_usd, rich.open_interest_usd), 2),
            credible=credible,
            note="" if credible else (
                f"spread {spread:.0%} annual exceeds the {MAX_CREDIBLE_ANNUAL:.0%} credibility "
                "ceiling -- treat as a stale quote or a symbol in trouble until a second "
                "observation confirms it, NOT as the best opportunity in the panel"),
        ))
    # Credible first, then widest. Never magnitude alone: the biggest number in a noisy cross-venue
    # panel is the likeliest artifact, and sorting on it surfaces the desk's own worst data daily.
    return sorted(out, key=lambda d: (not d.credible, -d.spread_annual))

```

### libs/self_improvement/drift_detector.py
```python
"""Alpha drift detector — training vs live distribution shift (PSI).

When the live distribution drifts from training, confidence should drop and revalidation should
be triggered. Detection is statistical (Population Stability Index); the response is a
recommendation (Stage 13 does not pause capital directly).
"""

from __future__ import annotations

import numpy as np
from pydantic import BaseModel, ConfigDict


class DriftResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    psi: float
    drifted: bool
    recommendation: str

    def __bool__(self) -> bool:
        return not self.drifted


def population_stability_index(
    expected: np.ndarray, actual: np.ndarray, *, bins: int = 10, eps: float = 1e-6
) -> float:
    """Population Stability Index between a training (expected) and live (actual) sample."""
    e = np.asarray(expected, dtype="float64")
    a = np.asarray(actual, dtype="float64")
    if len(e) < 2 or len(a) < 2:
        return 0.0
    edges = np.unique(np.quantile(e, np.linspace(0.0, 1.0, bins + 1)))
    if len(edges) < 2:
        return 0.0
    edges[0], edges[-1] = -np.inf, np.inf
    e_prop = np.histogram(e, edges)[0] / len(e) + eps
    a_prop = np.histogram(a, edges)[0] / len(a) + eps
    return float(np.sum((a_prop - e_prop) * np.log(a_prop / e_prop)))


class AlphaDriftDetector:
    """Flags distribution drift and recommends reduce-confidence / revalidate."""

    def __init__(self, *, psi_threshold: float = 0.20) -> None:
        self.psi_threshold = psi_threshold

    def detect(self, training: np.ndarray, live: np.ndarray) -> DriftResult:
        psi = population_stability_index(training, live)
        drifted = psi > self.psi_threshold
        recommendation = (
            "reduce confidence, pause signal, trigger revalidation"
            if drifted
            else "no drift detected"
        )
        return DriftResult(psi=psi, drifted=drifted, recommendation=recommendation)

```

### libs/self_improvement/meta_learning.py
```python
"""Meta-learning engine — learn relationships; deploy NOTHING without the gauntlet.

Learns which regimes favour which alphas. Per the meta-learning governance directive, no learned
policy may be deployed automatically: an insight is ``deployable`` only after it passes CPCV,
PBO, DSR, and walk-forward validation (the verdicts are supplied by the validation layer).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

import numpy as np

from libs.self_improvement.models import MetaInsight


def meta_learning_governance_gate(
    *, cpcv_pass: bool, dsr_pass: bool, pbo_pass: bool, walk_forward_pass: bool
) -> bool:
    """A learned relationship is deployable only if every validation gate passes."""
    return bool(cpcv_pass and dsr_pass and pbo_pass and walk_forward_pass)


class MetaLearningEngine:
    """Learns regime->alpha affinity as a non-deployable insight until governed."""

    def learn_regime_affinity(
        self, regime_labels: Sequence[str], returns_by_alpha: Mapping[str, np.ndarray]
    ) -> MetaInsight:
        regimes = sorted(set(regime_labels))
        labels = np.asarray(regime_labels)
        relationship: dict[str, dict[str, float]] = {}
        for alpha_id, returns in returns_by_alpha.items():
            arr = np.asarray(returns, dtype="float64")
            per_regime: dict[str, float] = {}
            for regime in regimes:
                mask = labels == regime
                per_regime[regime] = float(arr[mask].mean()) if mask.any() else 0.0
            relationship[alpha_id] = per_regime
        return MetaInsight(
            description="regime->alpha mean-return affinity",
            relationship=relationship,
            evidence={"n_observations": len(labels), "regimes": regimes},
            deployable=False,
        )

    def govern(
        self,
        insight: MetaInsight,
        *,
        cpcv_pass: bool,
        dsr_pass: bool,
        pbo_pass: bool,
        walk_forward_pass: bool,
    ) -> MetaInsight:
        """Return the insight with ``deployable`` set only if all gates pass."""
        deployable = meta_learning_governance_gate(
            cpcv_pass=cpcv_pass, dsr_pass=dsr_pass, pbo_pass=pbo_pass,
            walk_forward_pass=walk_forward_pass,
        )
        return insight.model_copy(update={"deployable": deployable})

```

### libs/self_improvement/research_priority.py
```python
"""Research priority engine — guide future research toward the highest-value areas.

Reuses the discovery layer's research-ROI ranking and combines it with decaying-family signals:
families that are decaying (and would leave portfolio/regime gaps) get higher research priority.
"""

from __future__ import annotations

from collections.abc import Mapping

from libs.discovery.research_roi import CategoryStat, rank_categories
from libs.self_improvement.models import ResearchPriority


class ResearchPriorityEngine:
    """Ranks research categories by need (decay) and expected yield (ROI)."""

    def prioritize(
        self,
        *,
        decaying_by_category: Mapping[str, float],
        roi_stats: Mapping[str, CategoryStat] | None = None,
    ) -> list[ResearchPriority]:
        yields = dict(rank_categories(dict(roi_stats))) if roi_stats else {}
        categories = set(decaying_by_category) | set(yields)
        priorities: list[ResearchPriority] = []
        for category in categories:
            decay = float(decaying_by_category.get(category, 0.0))
            yield_score = float(yields.get(category, 0.0))
            score = decay + yield_score  # decay = need now, yield = expected payoff
            reason = (
                f"decay_pressure={decay:.2f}, expected_yield={yield_score:.2f}"
                if score > 0
                else "no current research pressure"
            )
            priorities.append(
                ResearchPriority(category=category, priority_score=score, reason=reason)
            )
        return sorted(priorities, key=lambda p: p.priority_score, reverse=True)

```

### libs/signal_engine/ranking.py
```python
"""Opportunity ranking — order trade candidates by the institutional score.

Ranks highest-to-lowest by the master institutional score, breaking ties by confidence then edge
so the most corroborated opportunity wins. Ranking is total and deterministic.
"""

from __future__ import annotations

from collections.abc import Sequence

from libs.signal_engine.models import TradeCandidate


def _key(c: TradeCandidate) -> tuple[float, float, float]:
    return (c.institutional.score, c.confidence.confidence, c.edge.edge_score)


def rank_trade_candidates(candidates: Sequence[TradeCandidate]) -> list[TradeCandidate]:
    """Return candidates sorted from best to worst by institutional score."""
    return sorted(candidates, key=_key, reverse=True)


class SignalRanker:
    """Object wrapper around :func:`rank_trade_candidates`."""

    def rank(self, candidates: Sequence[TradeCandidate]) -> list[TradeCandidate]:
        return rank_trade_candidates(candidates)

```

### libs/stage14/models.py
```python
"""Stage 14 models — sleeves, portfolio state, budgets, scores, and the output package.

Stage 14 transforms approved Stage 13.5 :class:`SignalPackage` objects into capital allocations
optimized for long-term compounded wealth. These models describe the allocation vocabulary; the
engines compute them. Reuses Stage 13.5 ``Regime`` and the platform's existing risk primitives.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from libs.core.time import to_iso8601, utcnow


class AlphaSleeve(StrEnum):
    """Capital is budgeted at the sleeve level before the position level."""

    TREND = "trend"
    MOMENTUM = "momentum"
    BREAKOUT = "breakout"
    MEAN_REVERSION = "mean_reversion"
    VOLATILITY = "volatility"
    CARRY = "carry"
    MACRO = "macro"
    OTHER = "other"

    @classmethod
    def from_text(cls, text: str) -> AlphaSleeve:
        try:
            return cls(text.strip().lower().replace(" ", "_"))
        except ValueError:
            return cls.OTHER


class PortfolioState(StrEnum):
    """The portfolio risk regime; modulates budgets, Kelly fractions, and leverage."""

    NORMAL = "normal"
    CAUTION = "caution"
    DEFENSIVE = "defensive"
    CRISIS = "crisis"
    RECOVERY = "recovery"


class RiskBudget(BaseModel):
    """Risk (not capital) budgets that drive allocation."""

    model_config = ConfigDict(frozen=True)

    vol_budget: float = 0.15            # annualized portfolio volatility target
    drawdown_budget: float = 0.20       # max tolerated drawdown
    tail_budget: float = 0.10           # tail-risk allowance
    correlation_budget: float = 0.60    # max acceptable average pairwise correlation
    capacity_budget: float = 0.80       # max capacity utilization


class GeometricGrowthResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    expected_cagr: float
    expected_geometric_return: float
    expected_terminal_wealth: float
    growth_efficiency: float
    geometric_growth_score: float  # 0-100


class GrowthSimResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    cagr_median: float
    cagr_p5: float
    cagr_p95: float
    terminal_wealth_median: float
    probability_of_ruin: float
    expected_log_growth: float
    survival_probability: float


class SurvivalResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    survival_probability: float
    probability_of_ruin: float
    stress_survival: float
    survival_score: float  # 0-100


class PortfolioCapacityResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    capacity_utilization: float  # 0..1
    capacity_score: float        # 0-100
    forecast_slippage: float
    impact_cost: float


class CapacityGovernorAction(BaseModel):
    model_config = ConfigDict(frozen=True)

    action: str          # "ok" | "scale" | "block" | "zero"
    scale_factor: float  # multiplier to apply to size (1.0 = unchanged, 0.0 = blocked)
    reason: str


class StressResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    stress_score: float  # 0-100 (higher = more resilient)
    worst_drawdown: float
    by_scenario: dict[str, float]


class ResilienceResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    resilience_score: float  # 0-100
    components: dict[str, float]


class CorrelationResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    avg_pairwise: float
    max_pairwise: float
    concentration: float  # 0..1
    acceptable: bool


class ConvexityResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    skew: float
    convexity: float
    crisis_alpha: float
    convexity_score: float  # 0-100


class EfficiencyResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    capital_efficiency_score: float  # 0-100
    return_per_risk: float
    return_per_capacity: float


class LeverageDecision(BaseModel):
    model_config = ConfigDict(frozen=True)

    leverage: float
    rationale: str


class ReinvestmentDecision(BaseModel):
    model_config = ConfigDict(frozen=True)

    reinvestment_rate: float  # 0..1
    rationale: str


class MarginalContribution(BaseModel):
    model_config = ConfigDict(frozen=True)

    by_signal: dict[str, float]
    total: float


class InstitutionalPortfolioScore(BaseModel):
    model_config = ConfigDict(frozen=True)

    score: float  # 0-100
    components: dict[str, float]


class KillDecision(BaseModel):
    """Portfolio-level kill criteria (distinct from per-strategy kills)."""

    model_config = ConfigDict(frozen=True)

    halt: bool = False
    defensive_mode: bool = False
    no_new_capital: bool = False
    reasons: list[str] = Field(default_factory=list)


class PortfolioPackage(BaseModel):
    """One symbol's final allocation — Stage 14's output to the Risk Engine."""

    model_config = ConfigDict(frozen=True)

    symbol: str
    sleeve: AlphaSleeve
    allocation: float       # fraction of portfolio capital
    position_size: float    # allocation x leverage x capital (account currency)
    kelly_fraction: float
    leverage: float
    expected_return: float
    expected_sharpe: float
    expected_sortino: float
    expected_calmar: float
    expected_drawdown: float
    geometric_growth_score: float
    survival_score: float
    capacity_score: float
    diversification_score: float
    fragility_score: float
    portfolio_contribution: float
    institutional_score: float
    timestamp: str = Field(default_factory=lambda: to_iso8601(utcnow()))


class PortfolioConstructionResult(BaseModel):
    """The full Stage 14 output: allocations, rejections, state, and kill status."""

    model_config = ConfigDict(frozen=True)

    generated_at: str = Field(default_factory=lambda: to_iso8601(utcnow()))
    packages: list[PortfolioPackage] = Field(default_factory=list)
    rejected: dict[str, str] = Field(default_factory=dict)  # symbol -> reason (allocation 0)
    state: PortfolioState = PortfolioState.NORMAL
    kill: KillDecision = KillDecision()
    total_allocation: float = 0.0

```

### libs/stage15/__init__.py
```python
"""``libs.stage15`` — alpha discovery, edge research & live validation factory.

The orchestration layer that turns the platform from infrastructure-rich to edge-rich: it threads
candidates through Discovery -> Validation -> Walk-Forward -> Shadow -> Paper -> Allocation ->
Monitoring -> Revalidation -> Retirement, gated by economic mechanism, regime resilience, portfolio
contribution, and a fail-closed governance gate, all under a research kill-switch. Optimized for the
*smallest* number of durable, low-correlation, economically-grounded alphas that survive live.

Reuses Architecture v1.0 throughout: ``libs.discovery`` (alpha factory, capacity, fragility,
regime diversification), ``libs.validation`` (gauntlet, economic prior, FDR, walk-forward), the
``libs.alpha_factory`` research OS, ``libs.alpha`` lifecycle/retirement, ``libs.signal_engine``
shadow deployment, and Stage 14. No duplicate abstractions; existing engines are not redefined.
"""

from __future__ import annotations

from libs.stage15.audit import ResearchAudit
from libs.stage15.contribution import AlphaContributionForecaster
from libs.stage15.economic_mechanism import EconomicMechanismEngine
from libs.stage15.errors import ResearchGovernanceError, Stage15Error
from libs.stage15.governance import ResearchGovernanceEngine, alpha_governance_gate
from libs.stage15.models import (
    AlphaGovernanceVerdict,
    AlphaQualityScore,
    AlphaScores,
    ContributionForecast,
    MechanismResult,
    MechanismType,
    PipelineRecord,
    PipelineStage,
    RegimeValidationResult,
    ResearchKillDecision,
    ResearchPipelineResult,
    ResearchPriority,
    ResearchRegime,
)
from libs.stage15.orchestrator import AlphaPipelineInput, ResearchOrchestrator
from libs.stage15.priority import ResearchCandidate, ResearchPriorityEngine
from libs.stage15.regime_validation import RegimeValidationEngine
from libs.stage15.scoring import alpha_quality_score

__all__ = [  # noqa: RUF022  # grouped by concern
    # models / enums
    "MechanismType",
    "ResearchRegime",
    "PipelineStage",
    "AlphaScores",
    "AlphaQualityScore",
    "MechanismResult",
    "RegimeValidationResult",
    "ContributionForecast",
    "ResearchPriority",
    "AlphaGovernanceVerdict",
    "ResearchKillDecision",
    "PipelineRecord",
    "ResearchPipelineResult",
    # engines
    "EconomicMechanismEngine",
    "RegimeValidationEngine",
    "AlphaContributionForecaster",
    "ResearchPriorityEngine",
    "ResearchCandidate",
    "alpha_quality_score",
    # governance
    "alpha_governance_gate",
    "ResearchGovernanceEngine",
    # orchestrator + audit
    "ResearchOrchestrator",
    "AlphaPipelineInput",
    "ResearchAudit",
    # errors
    "Stage15Error",
    "ResearchGovernanceError",
]

```

### libs/stage15/economic_mechanism.py
```python
"""Economic mechanism engine — every alpha must have a documented causal explanation.

Statistical significance alone is insufficient. Reuses the validation layer's economic-prior gate
(which requires the mechanism plus why-it-works / why-it-might-fail / decay-detection fields). No
causal mechanism -> REJECT.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from libs.stage15.models import MechanismResult, MechanismType
from libs.validation.economic_prior import EconomicPrior, economic_prior_gate


class EconomicMechanismEngine:
    """Requires a documented causal mechanism for every alpha (fail-closed)."""

    def require(self, prior: Mapping[str, Any] | EconomicPrior) -> MechanismResult:
        gate = economic_prior_gate(prior)
        mechanism = self._extract_mechanism(prior)
        return MechanismResult(
            present=gate.passed,
            mechanism=mechanism,
            missing=list(gate.missing),
            message=gate.message,
        )

    def has_mechanism(self, prior: Mapping[str, Any] | EconomicPrior) -> bool:
        return self.require(prior).present

    @staticmethod
    def _extract_mechanism(prior: Mapping[str, Any] | EconomicPrior) -> MechanismType | None:
        raw = prior.mechanism if isinstance(prior, EconomicPrior) else prior.get("mechanism")
        if raw is None:
            return None
        try:
            return MechanismType(raw)
        except ValueError:
            return None

```

### libs/store/snapshots.py
```python
"""Snapshot catalog + database snapshot/restore.

Two snapshot kinds share one catalog:

* ``database`` — a consistent point-in-time copy of the SQLite system of record (via the
  SQLite online-backup API), hashed for tamper detection. :func:`create_snapshot` /
  :func:`restore_snapshot`.
* ``dataset`` — a reference to an immutable Parquet dataset version (registered by Stage 3
  via :func:`register_dataset_snapshot`) so an experiment can bind an exact data version.
"""

from __future__ import annotations

import hashlib
import shutil
import sqlite3
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from libs.core.ids import generate_id
from libs.core.time import to_iso8601, utcnow
from libs.store.connection import Database
from libs.store.hashchain import canonical_json
from libs.store.models import SnapshotRecord


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _row_to_snapshot(row: sqlite3.Row) -> SnapshotRecord:
    import json

    return SnapshotRecord(
        id=row["id"],
        created_at=row["created_at"],
        kind=row["kind"],
        label=row["label"],
        path=row["path"],
        sha256=row["sha256"],
        row_counts=json.loads(row["row_counts_json"]) if row["row_counts_json"] else None,
        meta=json.loads(row["meta_json"]) if row["meta_json"] else None,
    )


def _insert_catalog_row(
    db: Database,
    *,
    snapshot_id: str,
    kind: str,
    label: str | None,
    path: str | None,
    sha256: str | None,
    row_counts: Mapping[str, Any] | None,
    meta: Mapping[str, Any] | None,
) -> SnapshotRecord:
    created_at = to_iso8601(utcnow())
    with db.transaction() as conn:
        conn.execute(
            "INSERT INTO snapshots "
            "(id, created_at, kind, label, path, sha256, row_counts_json, meta_json) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                snapshot_id, created_at, kind, label, path, sha256,
                canonical_json(dict(row_counts)) if row_counts is not None else None,
                canonical_json(dict(meta)) if meta is not None else None,
            ),
        )
    record = get_snapshot(db, snapshot_id)
    assert record is not None
    return record


def create_snapshot(
    db: Database,
    snapshot_dir: str | Path,
    *,
    label: str | None = None,
    meta: Mapping[str, Any] | None = None,
) -> SnapshotRecord:
    """Create a consistent database snapshot file and register it in the catalog."""
    snapshot_dir = Path(snapshot_dir)
    snapshot_dir.mkdir(parents=True, exist_ok=True)
    snapshot_id = generate_id("snap")
    target = snapshot_dir / f"{snapshot_id}.sqlite"

    dest = sqlite3.connect(str(target))
    try:
        db.connection.backup(dest)
    finally:
        dest.close()

    sha256 = _sha256_file(target)
    return _insert_catalog_row(
        db,
        snapshot_id=snapshot_id,
        kind="database",
        label=label,
        path=str(target),
        sha256=sha256,
        row_counts=None,
        meta=meta,
    )


def restore_snapshot(db: Database, snapshot_id: str, target_path: str | Path) -> Path:
    """Restore a database snapshot to ``target_path`` after verifying its hash.

    Raises:
        KeyError: if the snapshot id is unknown.
        ValueError: if the snapshot is not a database snapshot, the file is missing, or its
            SHA-256 no longer matches the catalog (tamper detection).
    """
    record = get_snapshot(db, snapshot_id)
    if record is None:
        raise KeyError(f"snapshot not found: {snapshot_id}")
    if record.kind != "database":
        raise ValueError(f"snapshot {snapshot_id} is not a database snapshot")
    if record.path is None:
        raise ValueError(f"snapshot {snapshot_id} has no file path")
    source = Path(record.path)
    if not source.is_file():
        raise ValueError(f"snapshot file is missing: {source}")
    actual = _sha256_file(source)
    if actual != record.sha256:
        raise ValueError(
            f"snapshot {snapshot_id} failed integrity check: "
            f"expected {record.sha256}, got {actual}"
        )
    target = Path(target_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, target)
    return target


def register_dataset_snapshot(
    db: Database,
    *,
    label: str,
    path: str,
    sha256: str,
    row_counts: Mapping[str, Any] | None = None,
    meta: Mapping[str, Any] | None = None,
) -> SnapshotRecord:
    """Register an immutable Parquet dataset version in the catalog (used by Stage 3)."""
    snapshot_id = generate_id("snap")
    return _insert_catalog_row(
        db,
        snapshot_id=snapshot_id,
        kind="dataset",
        label=label,
        path=path,
        sha256=sha256,
        row_counts=row_counts,
        meta=meta,
    )


def get_snapshot(db: Database, snapshot_id: str) -> SnapshotRecord | None:
    row = db.execute("SELECT * FROM snapshots WHERE id = ?", (snapshot_id,)).fetchone()
    return _row_to_snapshot(row) if row else None


def list_snapshots(db: Database, *, kind: str | None = None) -> list[SnapshotRecord]:
    if kind is None:
        rows = db.execute("SELECT * FROM snapshots ORDER BY created_at").fetchall()
    else:
        rows = db.execute(
            "SELECT * FROM snapshots WHERE kind = ? ORDER BY created_at", (kind,)
        ).fetchall()
    return [_row_to_snapshot(row) for row in rows]

```

### libs/validation/errors.py
```python
"""Validation-layer exceptions."""

from __future__ import annotations

from libs.core.errors import QuantPlatformError


class ValidationError(QuantPlatformError):
    """Invalid validation inputs, or a guarded resource (lockbox) misused."""

```

### scripts/batch_altdata.py
```python
"""Batch ALT-DATA orthogonal screen -- multilingual retail attention (Wikipedia pageviews per
language = different geographic user bases) + DeFi protocol-health/flow channels (DefiLlama).
All free, no key, daily history. Hardened harness (de-contam + SUSPECT-LOOKAHEAD rails). These are
genuinely NOT price/derivative feeds -- exactly the low-correlation channels worth screening.
Run from repo root."""
from __future__ import annotations

import json
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

import numpy as np

from libs.research.axis_screen import stage_a_screen


def _get(url: str):
    req = urllib.request.Request(url, headers={"User-Agent": "quant-altdata/1.0 (research)"})
    with urllib.request.urlopen(req, timeout=35) as r:
        return json.loads(r.read().decode())


def _binance() -> dict[str, float]:
    rows = _get("https://api.binance.com/api/v3/klines?symbol=BTCUSDT&interval=1d&limit=900")
    return {datetime.fromtimestamp(int(r[0]) / 1000, tz=UTC).date().isoformat(): float(r[4])
            for r in rows}


# --- multilingual Wikipedia pageviews (retail attention, per language population) ---------
_WIKI = ("https://wikimedia.org/api/rest_v1/metrics/pageviews/per-article/"
         "{proj}.wikipedia/all-access/all-agents/{art}/daily/20240101/20260722")
_WIKI_ARTS = {"wiki_btc_en": ("en", "Bitcoin"), "wiki_btc_ja": ("ja", "ビットコイン"),
              "wiki_btc_ko": ("ko", "비트코인"), "wiki_btc_ru": ("ru", "Биткойн"),
              "wiki_btc_zh": ("zh", "比特幣")}


def _wiki(proj: str, art: str) -> dict[str, float]:
    art_enc = urllib.request.quote(art, safe="")
    d = _get(_WIKI.format(proj=proj, art=art_enc))
    out = {}
    for it in d.get("items", []):
        ts = str(it["timestamp"])            # YYYYMMDD00
        out[f"{ts[0:4]}-{ts[4:6]}-{ts[6:8]}"] = float(it["views"])
    return out


# --- DefiLlama protocol-health / flow channels -------------------------------------------
def _llama_tvl() -> dict[str, float]:
    d = _get("https://api.llama.fi/v2/historicalChainTvl")
    return {datetime.fromtimestamp(int(x["date"]), tz=UTC).date().isoformat(): float(x["tvl"])
            for x in d}


def _llama_chart(url: str) -> dict[str, float]:
    d = _get(url)
    chart = d.get("totalDataChart", [])
    return {datetime.fromtimestamp(int(ts), tz=UTC).date().isoformat(): float(v)
            for ts, v in chart}


def _llama_dex() -> dict[str, float]:
    return _llama_chart("https://api.llama.fi/overview/dexs?excludeTotalDataChartBreakdown=true")


def _llama_fees() -> dict[str, float]:
    return _llama_chart("https://api.llama.fi/overview/fees?excludeTotalDataChartBreakdown=true")


def _llama_stables() -> dict[str, float]:
    d = _get("https://stablecoins.llama.fi/stablecoincharts/all")
    out = {}
    for x in d:
        v = x.get("totalCirculatingUSD") or x.get("totalCirculating") or {}
        peg = v.get("peggedUSD") if isinstance(v, dict) else None
        if peg is not None:
            out[datetime.fromtimestamp(int(x["date"]), tz=UTC).date().isoformat()] = float(peg)
    return out


SOURCES = list(_WIKI_ARTS.items())  # wiki handled specially below
LLAMA = {"defi_tvl": _llama_tvl, "dex_volume": _llama_dex,
         "protocol_fees": _llama_fees, "stablecoin_supply": _llama_stables}


def _screen(name: str, series: dict[str, float], gb: dict[str, float], retmap: dict[str, float]):
    dates = sorted(set(series) & set(gb))
    if len(dates) < 90:
        print(f"{name:22s} thin/blocked ({len(dates)}d)")
        return None
    sig = np.array([series[d] for d in dates])
    ret = np.array([retmap[d] for d in dates])
    r = stage_a_screen(sig, ret, name=name)
    print(f"{name:22s} {len(dates)}d | IC {r.get('ic')} | same {r.get('same_period_corr')} "
          f"| resid {r.get('residual_ic')} | momSh {r.get('sharpe_momentum')} "
          f"| revSh {r.get('sharpe_reversal')} | {r['verdict']}")
    return r


def main() -> None:
    gb = _binance()
    dts = sorted(gb)
    btc = np.array([gb[d] for d in dts])
    retmap = {dts[0]: 0.0}
    for i in range(1, len(dts)):
        retmap[dts[i]] = btc[i] / btc[i - 1] - 1.0

    results = []
    for name, (proj, art) in _WIKI_ARTS.items():
        try:
            s = _wiki(proj, art)
        except Exception as e:
            print(f"{name:22s} DATA-BLOCKED ({type(e).__name__}: {e})")
            continue
        r = _screen(name, s, gb, retmap)
        if r:
            results.append(r)
    for name, fetch in LLAMA.items():
        try:
            s = fetch()
        except Exception as e:
            print(f"{name:22s} DATA-BLOCKED ({type(e).__name__}: {e})")
            continue
        r = _screen(name, s, gb, retmap)
        if r:
            results.append(r)

    Path("data/batch_altdata_screen.json").write_text(
        json.dumps({"updated": datetime.now(tz=UTC).isoformat(), "results": results}, indent=1),
        "utf-8")
    surv = [r["name"] for r in results if r["verdict"] == "SCREEN-INTERESTING"]
    print(f"\nSURVIVORS (passed de-contam + lookahead rails): {surv or 'NONE'}")


if __name__ == "__main__":
    main()

```

### scripts/check_shell_hygiene.py
```python
"""Shell-hygiene gate for the ops/ launcher scripts (CI step, 2026-07-20).

Why this exists: on 2026-07-19 an unescaped ``$300`` inside run_cro_ai.sh's double-quoted
PROMPT expanded as positional ``$3`` + "00" under ``set -u`` and crashed the brain launcher
BEFORE it reached Claude -- the desk lost a full reasoning day during an open dead-man
incident, silently (no log file was even created). Two independent micro-auditors converged
on gating this class in CI (2026-07-20 inbox: kimi shellcheck/dry-run, mistral pre-commit
lint). Three layers, cheapest-first:

1. ``bash -n`` syntax check on every ops/*.sh (catches plain syntax rot);
2. an unescaped ``$NN`` scan: ``$`` followed by 2+ digits in a shell script is almost
   certainly a money literal, never a positional (those are single-digit or ``${10}``) --
   this is the static check that WOULD have caught $300, which ``bash -n`` cannot;
3. a full dry-run of run_cro_ai.sh (BRAIN_DRY_RUN=1): builds the entire prompt under
   ``set -u`` with zero auth/network/token/log side effects, so ANY future bad expansion
   in the prompt assembly fails CI instead of killing a live cycle.

    .venv/bin/python scripts/check_shell_hygiene.py
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
_OPS = _ROOT / "ops"

# unescaped $ then 2+ digits (a preceding backslash escapes it; $1..$9 positionals are fine)
_MONEY_LITERAL = re.compile(r"(?<!\\)\$[0-9]{2,}")


def main() -> int:
    failures: list[str] = []
    scripts = sorted(_OPS.glob("*.sh"))
    if not scripts:
        print("FAIL: no ops/*.sh found -- gate misconfigured")
        return 1

    for sh in scripts:
        r = subprocess.run(["bash", "-n", str(sh)], capture_output=True, text=True, check=False)
        if r.returncode != 0:
            failures.append(f"bash -n {sh.name}: {r.stderr.strip()[:200]}")
        for i, line in enumerate(sh.read_text("utf-8").splitlines(), 1):
            if _MONEY_LITERAL.search(line):
                failures.append(
                    f"{sh.name}:{i}: unescaped $<digits> literal (the 2026-07-19 crash "
                    f"class) -- escape as \\$ : {line.strip()[:120]}")

    r = subprocess.run(["bash", str(_OPS / "run_cro_ai.sh")], capture_output=True, text=True,
                       env={"BRAIN_DRY_RUN": "1", "PATH": "/usr/bin:/bin", "HOME": "/home/quant"},
                       cwd=str(_ROOT), check=False)
    if r.returncode != 0 or "DRY-RUN OK" not in r.stdout:
        failures.append(f"run_cro_ai.sh dry-run failed (rc={r.returncode}): "
                        f"{(r.stderr or r.stdout).strip()[:200]}")

    for f in failures:
        print(f"FAIL: {f}")
    print("shell hygiene:", "ALL OK" if not failures else f"{len(failures)} failure(s)")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())

```

### scripts/collect_research_feed.py
```python
"""Nightly research feed -- keyless arXiv q-fin ingestion into the vault (Phase-2 surveillance).

Pulls the newest quantitative-finance papers (q-fin.TR trading/microstructure, q-fin.PM portfolio,
q-fin.ST statistical finance) from the free arXiv Atom API, dedupes against the archive, and
appends NEW items to docs/research/feed_inbox.md -- the inbox the CRO cycle processes (per
SKILL.md): summarize -> economic intuition -> EV-score -> either graveyard-reject or distill into a
topic note + research queue. Mechanical fetch only; ALL judgment stays in the CRO cycle. Keyless,
stdlib, one call/day. SSRN/blogs/changelogs deliberately NOT scraped (fragile, ToS, low
signal-per-maintenance-hour) -- those remain the CRO's WebSearch job.

    python scripts/collect_research_feed.py
"""

from __future__ import annotations

import json
import ssl
import urllib.request
import xml.etree.ElementTree as ET
from datetime import UTC, datetime
from pathlib import Path

import certifi

_ARCHIVE = Path("data/research_feed.json")
_INBOX = Path("docs/research/feed_inbox.md")
_API = ("http://export.arxiv.org/api/query?search_query="
        "cat:q-fin.TR+OR+cat:q-fin.PM+OR+cat:q-fin.ST"
        "&sortBy=submittedDate&sortOrder=descending&max_results=25")
_NS = {"a": "http://www.w3.org/2005/Atom"}
_KEEP = 500


def _text(e: ET.Element, tag: str) -> str:
    return (e.findtext(f"a:{tag}", "", _NS) or "").strip()


def _fetch() -> list[dict[str, str]]:
    # certifi context: this machine's system store lacks the arXiv CA chain (urllib default fails)
    ctx = ssl.create_default_context(cafile=certifi.where())
    req = urllib.request.Request(_API, headers={"User-Agent": "quant-research-feed/1.0"})
    with urllib.request.urlopen(req, timeout=30, context=ctx) as r:
        root = ET.fromstring(r.read())
    out = []
    for e in root.findall("a:entry", _NS):
        out.append({"id": _text(e, "id"), "title": " ".join(_text(e, "title").split()),
                    "published": _text(e, "published")[:10],
                    "abstract": " ".join(_text(e, "summary").split())[:600]})
    return out


def main() -> None:
    try:
        arch = json.loads(_ARCHIVE.read_text("utf-8"))
    except (OSError, json.JSONDecodeError):
        arch = {"seen": {}}
    seen = arch.get("seen", {})
    new = [it for it in _fetch() if it["id"] and it["id"] not in seen]
    today = datetime.now(tz=UTC).date().isoformat()
    for it in new:
        seen[it["id"]] = today
    arch["seen"] = dict(list(seen.items())[-_KEEP:])
    _ARCHIVE.parent.mkdir(parents=True, exist_ok=True)
    _ARCHIVE.write_text(json.dumps(arch), "utf-8")

    if new:
        _INBOX.parent.mkdir(parents=True, exist_ok=True)
        head = ("# Research feed inbox (auto-fetched; CRO processes then DELETES entries)\n\n"
                "For each item: economic intuition -> orthogonality vs the alpha map -> EV-score "
                "(alpha_economics) -> graveyard-reject OR distill into docs/research/<topic>.md "
                "with [[wikilinks]] + research queue.\n")
        body = _INBOX.read_text("utf-8") if _INBOX.exists() else head
        if not body.startswith("# Research feed inbox"):
            body = head + body
        for it in new:
            body += (f"\n## {it['title']}\n- {it['published']} · {it['id']}\n"
                     f"- {it['abstract']}\n")
        _INBOX.write_text(body, "utf-8")
    print(f"research feed: {len(new)} new paper(s) -> inbox (archive {len(arch['seen'])})")


if __name__ == "__main__":
    main()

```

### scripts/max_audit.py
```python
#!/usr/bin/env python3
"""DAILY MAXIMIZATION SWEEP (principal standing order 2026-07-21).

The principal kept discovering -- only by personally pressuring the system -- that organs were
quietly below potential: audits seeing 1% of the code, prompts carrying 40x-stale budget
figures, quotas behaving as ceilings, credits sitting idle, miners dying silently on quota.
This script institutionalizes that pressure as a DAILY MECHANICAL SWEEP: pure filesystem
reads, no LLM cost, run by cron and at every brain-cycle start.

Layers above it: every 3-day panel carries a full-system recommendations sweep, and the
zero-based MAXIMIZATION panel mission re-derives each organ's ceiling from scratch on rotation.

Rules of the sweep:
 - a below-max state is a DEFECT unless acknowledged with a reason AND an expiry (max 30d) in

#  EXHAUSTION: there is no acceptable number of un-acked below-max states. Sweep every
#  organ every run; a check skipped for time is a defect hidden for time.
   data/max_audit_acks.json -- no permanent burial, ever
 - defects persisting >48h un-acked ESCALATE to the principal page (PRINCIPAL_ACTION.md):
   nothing can sit below max for more than two days without either being fixed or him knowing
 - one broken check must never kill the sweep (every check is fenced)
"""
from __future__ import annotations

import contextlib
import json
import re
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:          # fences import libs; a blind checker is a defect
    sys.path.insert(0, str(ROOT))
LOGS = ROOT / "data/cro_ai_logs"
REPORT = ROOT / "data/max_audit_report.json"
ACKS = ROOT / "data/max_audit_acks.json"
PA = ROOT / "data/PRINCIPAL_ACTION.md"

ESCALATE_H = 48.0
NOW = time.time()

# organ -> (glob, min_bytes_for_success, max_age_hours)
ORGANS = {
    "brain-cycle":      ("2026*_*.log",              2000, 8.0),
    "frontier-en":      ("frontier_en_*.log",        1500, 36.0),
    "frontier-cn":      ("frontier_cn_*.log",        1500, 36.0),
    "frontier-ru":      ("frontier_ru_*.log",        1500, 36.0),
    "frontier-kr":      ("frontier_kr_*.log",        1500, 36.0),
    "frontier-jp":      ("frontier_jp_*.log",        1500, 36.0),
    "frontier-ar":      ("frontier_ar_*.log",        1500, 36.0),
    "frontier-br":      ("frontier_br_*.log",        1500, 36.0),
    "dataaxis-dig":     ("dataaxis_*.log",           1500, 96.0),
    "litminer-dig":     ("litminer_*.log",           1500, 216.0),
    "prospector-dig":   ("prospector_*.log",         1500, 216.0),
    "blindrediscovery": ("blindrediscovery_*.log",   1500, 840.0),
}


def _j(path: Path, default):
    try:
        return json.loads(path.read_text("utf-8"))
    except Exception:
        return default


def _acquired_axes() -> list[str]:
    """The ingested-data surface as NAMES (not a count): bronze lake stores + forward clocks."""
    names: list[str] = []
    lake = ROOT / "data/lake/bronze"
    if lake.exists():
        names += [p.name for p in lake.iterdir() if p.is_dir()]
    for pat in ("data/*_premium.jsonl", "data/*_supply.jsonl", "data/*_activity.jsonl"):
        names += [p.stem for p in ROOT.glob(pat)]
    return list(dict.fromkeys(names))  # de-dup, preserve order


def _converted_axes() -> list[str]:
    """Every axis the desk has actually CONVERTED, from the real conversion artifacts.

    An axis is 'converted' (covered) if a tested-hypothesis artifact exists for it -- regardless of
    outcome (tested-and-rejected is still converted; the graveyard is coverage). Three sources, all
    the desk's real conversion record, so the coverage metric credits work that genuinely happened
    instead of only the new --axis tag: (1) forward-clock shadows (web/axis_shadows.json), (2)
    reconstructed held-out OOS reports (reports/reconstructed_oos/*.json), (3) research_memory
    hypotheses tagged with --axis. Lowercased for tolerant matching against acquired-axis names.
    """
    tags: set[str] = set()
    # (1) forward-clock shadow registry -- each axis under a live forward clock
    shadows = _j(ROOT / "web/axis_shadows.json", {})
    for rec in (shadows.get("axes", []) if isinstance(shadows, dict) else []):
        ax = rec.get("axis") if isinstance(rec, dict) else None
        if isinstance(ax, str) and ax.strip():
            tags.add(ax.strip().lower())
    # (2) reconstructed held-out OOS reports -- each backfilled + diff-verified axis
    oos_dir = ROOT / "reports/reconstructed_oos"
    if oos_dir.exists():
        for rep in oos_dir.glob("*.json"):
            tags.add(rep.stem.lower())
            d = _j(rep, {})
            for r in (d.get("results", []) if isinstance(d, dict) else []):
                s = r.get("sleeve") if isinstance(r, dict) else None
                if isinstance(s, str) and s.strip():
                    tags.add(s.strip().lower())
    # (3) research_memory hypotheses tagged with the axis they screen (the --axis flag)
    try:
        import sqlite3
        con = sqlite3.connect(str(ROOT / "data/sor_research.sqlite"))
        for (mj,) in con.execute(
            "SELECT metrics_json FROM research_memory WHERE category != 'method' "
            "AND metrics_json IS NOT NULL"
        ):
            try:
                axis = (json.loads(mj) or {}).get("axis")
            except Exception:
                axis = None
            if isinstance(axis, str) and axis.strip():
                tags.add(axis.strip().lower())
        con.close()
    except Exception:
        pass
    return sorted(tags)


def _trial_mechanisms() -> list[str]:
    """The trials-ledger ``family`` column (the mechanism key) across candidate runtime DBs.

    Feeds the effective (independence-clustered) trial count. Robust to the ledger living in any of
    the sor databases; returns [] if unreachable so the monitor degrades to its prior behavior.
    """
    import sqlite3
    for name in ("sor_research.sqlite", "sor.sqlite", "sor_demo.sqlite", "sor_live.sqlite"):
        db = ROOT / "data" / name
        if not db.exists():
            continue
        try:
            con = sqlite3.connect(str(db))
            rows = con.execute("SELECT family FROM trials_ledger").fetchall()
            con.close()
            if rows:
                return [str(r[0]) for r in rows if r[0] is not None]
        except Exception:
            continue
    return []


def _fenced(fn, defects, label):
    try:
        fn(defects)
    except Exception as e:
        defects.append((f"sweep-broken-{label}", f"max_audit check '{label}' itself failed: "
                        f"{e!r} -- a blind checker is a defect"))


# ARTIFACT PARITY (2026-07-25): claude writes deliverables via FILE TOOLS, so a SUCCESSFUL organ
# run can leave only the shell's ~58-byte start/exit header in its log. Judging production by log
# size alone made this sweep report 'organ never fired' on demonstrably working organs (the 07-25
# frontier dig wrote prospector_coverage.md at 13:37 while its log stayed 58b). An organ counts as
# having produced when its log is substantial OR a declared artifact advanced. Keep in sync with
# libs/ops/organ_catchup.py ORGANS.
ORGAN_ARTIFACTS: dict[str, tuple[str, ...]] = {
    "brain-cycle": ("data/decision_ledger.json", "docs/research/cadence_duties.md"),
    "dataaxis-dig": ("docs/research/data_axis_watchlist.md", "data/data_universe_map.json"),
    "prospector-dig": ("docs/research/prospector_watchlist.md",
                       "docs/research/prospector_coverage.md"),
    "litminer-dig": ("docs/research/improvement_inbox.md",),
    "frontier-en": ("docs/research/prospector_coverage.md",
                    "docs/research/search_operator_library.md"),
    "frontier-cn": ("docs/research/prospector_coverage.md",),
    "frontier-ru": ("docs/research/prospector_coverage.md",),
    "frontier-kr": ("docs/research/prospector_coverage.md",),
    "frontier-jp": ("docs/research/prospector_coverage.md",),
    "frontier-ar": ("docs/research/prospector_coverage.md",),
    "frontier-br": ("docs/research/prospector_coverage.md",),
}


def _artifact_age_h(organ: str) -> float:
    """Hours since this organ's freshest declared artifact advanced (inf if none)."""
    best = 0.0
    for rel in ORGAN_ARTIFACTS.get(organ, ()):
        try:
            best = max(best, (ROOT / rel).stat().st_mtime)
        except OSError:
            continue
    return (NOW - best) / 3600 if best else float("inf")


def check_organs(defects) -> None:
    for organ, (pat, min_b, max_h) in ORGANS.items():
        ok = [p for p in LOGS.glob(pat) if p.stat().st_size >= min_b]
        art_h = _artifact_age_h(organ)
        if not ok and art_h > max_h:
            defects.append((f"organ-never-{organ}",
                            f"{organ}: no substantial log (pattern {pat}, >= {min_b}b) AND no "
                            f"declared artifact written in {max_h}h -- organ has never fired or "
                            "always dies"))
            continue
        if not ok:
            continue                      # artifacts prove production; stub log is expected
        age_h = min((NOW - max(p.stat().st_mtime for p in ok)) / 3600, art_h)
        if age_h > max_h:
            defects.append((f"organ-stale-{organ}",
                            f"{organ}: last SUCCESSFUL run {age_h:.0f}h ago "
                            f"(cadence expects <= {max_h:.0f}h) -- silently degraded"))


# A real death SAYS so. A ~58b log is the normal signature of a SUCCESSFUL claude organ (it writes
# deliverables via file tools, so only the shell's start/exit header reaches the log) -- the old
# size-only rule reported 22 'deaths' in 48h while those organs were writing real artifacts.
_DEATH_MARKERS = ("out of usage credits", "session limit", "hit your limit",
                  "issue with the selected model", "auth", "not found", "traceback",
                  "permission denied", "refusing to send")


#: label -> pgrep pattern of the organ that WRITES that product, in BRACKET-TRICK form
#: (`run_cro_ai[.]sh`). The bracket is not decoration: the decision ledger records a monitor
#: that self-matched its own pgrep and reported a dead cycle as RUNNING for 80 minutes, so
#: every pattern this desk greps for a liveness answer is written so it cannot match the
#: checker's own argv.
_PRODUCER_PGREP = {
    "cron-cycle":         "run_cro_ai[.]sh",
    "prospector-product": "run_prospector_dig[.]sh",
    "dataaxis-product":   "run_dataaxis_dig[.]sh",
    "litminer-product":   "run_litminer_dig[.]sh",
    "frontier-product":   "run_frontie[r]",
}


def _producer_running(label: str) -> bool:
    """True while the organ that writes this product is still running.

    IN-FLIGHT IS NOT A STUB (2026-07-26). check_production compared a product's size against a
    success threshold with no liveness test, so an organ that was running CORRECTLY was reported
    as a defect: the 15:00 brain cycle was 20 seconds old, its log held only the shell's start
    header (53b), and the sweep filed it as `production-stub ... ran but produced a stub, not
    real output (the quota-stub / refuse class)`. A claude organ writes deliverables via file
    tools and its log stays tiny until exit, so EVERY healthy cycle trips that rule for its whole
    runtime. organ_catchup already guards exactly this way (is_running + RETRY_COOLDOWN_S); the
    audit did not, and a monitor that cries wolf on healthy work is how a desk learns to ignore
    its own pager -- the same blindness the stub-death check exists to prevent.
    """
    pat = _PRODUCER_PGREP.get(label)
    if not pat:
        return False
    try:
        return subprocess.run(["pgrep", "-f", pat], capture_output=True,
                              timeout=10, check=False).returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False               # cannot prove it is alive -> fall through and report


def check_stub_deaths(defects) -> None:
    dead = []
    for p in LOGS.glob("*.log"):
        try:
            if p.stat().st_size >= 600 or (NOW - p.stat().st_mtime) >= 48 * 3600:
                continue
            txt = p.read_text("utf-8", errors="ignore").lower()
        except OSError:
            continue
        if any(m in txt for m in _DEATH_MARKERS):
            dead.append(p)
    if len(dead) >= 3:
        defects.append(("stub-deaths",
                        f"{len(dead)} organ runs died at birth in 48h (log CONTENT names a quota/"
                        f"auth/model failure): {', '.join(p.name for p in dead[:6])}"))


#: Long-lived daemons whose code is loaded ONCE at process start. Add any new always-on service.
_DAEMONS = {
    "quant-cashcarry": "scripts/run_cashcarry_executor.py",
    "quant-deadman": "scripts/run_deadman_switch.py",
    "quant-liquidations": "scripts/liquidation_listener.py",
    "quant-dashboard": "scripts/serve_dashboard.py",
}


def _import_closure(entry: Path, seen: set[Path] | None = None) -> set[Path]:
    """Repo-local modules an entry point actually imports, followed transitively.

    Resolves `from libs.x.y import z` and `import libs.x.y` to files under the repo. Anything
    unresolvable is stdlib/third-party and is skipped -- those ship with the interpreter and do
    not change under a running process.
    """
    import ast
    seen = seen if seen is not None else set()
    if entry in seen or not entry.exists():
        return seen
    seen.add(entry)
    try:
        tree = ast.parse(entry.read_text("utf-8", errors="ignore"))
    except (OSError, SyntaxError):
        return seen
    mods: set[str] = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.Import):
            mods |= {a.name for a in n.names}
        elif isinstance(n, ast.ImportFrom) and n.module and not n.level:
            mods.add(n.module)
    for m in mods:
        if m.split(".")[0] not in {"libs", "app", "scripts"}:
            continue
        for cand in (ROOT / (m.replace(".", "/") + ".py"),
                     ROOT / m.replace(".", "/") / "__init__.py"):
            if cand.exists():
                _import_closure(cand, seen)
    return seen


def _worker_pids(rel: str) -> list[int]:
    """PIDs actually running an entry script, discovered WITHOUT asking systemd.

    Independence is the point: systemd only knows about the children it started, so an orphan
    that outlived a unit restart is invisible in `systemctl show`. pgrep sees the process table.

    ARGV-EXACT, never a substring (caught on this check's first live run): `pgrep -f` matches the
    whole command line, and every brain/subagent process carries the full doctrine via
    `--append-system-prompt` -- which quotes `scripts/run_cashcarry_executor.py` and
    `scripts/run_deadman_switch.py` in the risk-path duty. A bare `pgrep -f <rel>` therefore
    returned claude processes as executor and dead-man workers, which would have invented
    ownership defects and measured a brain's start time as a daemon's uptime. A monitor that
    reports the wrong process is worse than no monitor. So: argv[0] must be a python, and the
    script must be an argv element in its own right, not text buried inside one.
    """
    import subprocess
    try:
        out = subprocess.run(["pgrep", "-f", rel], capture_output=True, text=True,
                             timeout=10, check=False).stdout.split()
    except (OSError, subprocess.SubprocessError):
        return []
    pids = []
    for p in out:
        if not p.isdigit():
            continue
        try:
            argv = Path(f"/proc/{p}/cmdline").read_bytes().decode("utf-8", "replace").split("\0")
        except OSError:
            continue                                  # exited between pgrep and here
        argv = [a for a in argv if a]
        if not argv or "python" not in Path(argv[0]).name:
            continue
        if any(a == rel or a.endswith("/" + rel) for a in argv[1:]):
            pids.append(int(p))
    return pids


def check_stale_daemons(defects) -> None:
    """A daemon running code older than its own source is a fix that DID NOT SHIP.

    Origin (2026-07-26): the carry-leak alarm was committed 02:29Z and the executor had been up
    since 00:38Z, so python had already loaded the pre-fix module. The alarm sat inert for 8.7
    hours over a book bleeding 510% of its funding harvest -- the dashboard read "clean" because
    the field was simply absent. Same class as 2026-07-10, when a churn fix was inert for two
    days. Both were caught by hand; nothing mechanical looked.

    Compared against the IMPORT CLOSURE, not any-file-newer: a repo-wide mtime test fires on
    every unrelated commit, and a check that always fires is a check nobody reads.

    OWNERSHIP (2026-07-26, second instance the same day): the first version asked systemd for
    MainPID and skipped on `0`. But `0` is exactly what systemd reports while a unit sits in
    `activating (auto-restart)` -- which is the state an ORPHANED worker causes, because the
    orphan holds the singleton lock and every supervised spawn exits on it. So the detector was
    blind to the single most common way code goes inert: work being done by a process systemd
    does NOT own, surviving every `systemctl restart`. Verified live: quant-cashcarry MainPID=0
    while orphan pid 817906 (up 8.0h, pre-fix code) held the book and the unit respawned ~190
    processes/hour against it. The worker is now discovered INDEPENDENTLY of systemd, and the
    ownership mismatch is itself a defect -- an unsupervised worker means restarts do not ship
    fixes and crash-recovery is an illusion.
    """
    import subprocess
    for svc, rel in _DAEMONS.items():
        entry = ROOT / rel
        if not entry.exists():
            continue
        sd_pid, state = "", ""
        with contextlib.suppress(OSError, subprocess.SubprocessError):
            sd_pid = subprocess.run(["systemctl", "show", "-p", "MainPID", "--value", svc],
                                    capture_output=True, text=True, timeout=10).stdout.strip()
            state = subprocess.run(["systemctl", "show", "-p", "ActiveState", "--value", svc],
                                   capture_output=True, text=True, timeout=10).stdout.strip()
        workers = _worker_pids(rel)
        if not workers:
            continue                                  # not running -- check_organs owns that
        # OWNERSHIP first: a fix cannot ship into a process the supervisor does not control.
        if sd_pid not in {str(p) for p in workers}:
            oldest = min(workers, key=lambda p: Path(f"/proc/{p}").stat().st_mtime)
            age = (NOW - Path(f"/proc/{oldest}").stat().st_mtime) / 3600.0
            storm = (" and the unit is stuck in auto-restart, respawning against it"
                     if state == "activating" else "")
            defects.append((f"daemon-unsupervised-{svc}",
                            f"{svc} work is being done by pid {oldest} (up {age:.1f}h) which "
                            f"systemd does NOT own (MainPID={sd_pid or 'unknown'}, "
                            f"state={state or 'unknown'}){storm}. `systemctl restart` cannot "
                            "replace this process, so fixes do not ship and crash-recovery is "
                            "an illusion. Stop the unit, kill the orphan, start the unit, and "
                            "verify MainPID matches the worker."))
        for pid in sorted(workers, key=lambda p: Path(f"/proc/{p}").stat().st_mtime)[:1]:
            try:
                started = Path(f"/proc/{pid}").stat().st_mtime
            except OSError:
                continue
            stale = sorted(p for p in _import_closure(entry) if p.stat().st_mtime > started)
            if stale:
                age = (NOW - started) / 3600.0
                names = ", ".join(p.relative_to(ROOT).as_posix() for p in stale[:4])
                defects.append((f"daemon-stale-code-{svc}",
                                f"{svc} (pid {pid}, up {age:.1f}h) imports {len(stale)} file(s) "
                                f"MODIFIED SINCE IT STARTED: {names} -- python loaded the old "
                                "module at start, so every fix in those files is INERT in the "
                                "running process. Restart the unit and verify the new behaviour "
                                "appears in its output; a committed fix is not a shipped fix."))


def check_panel(defects) -> None:
    log = ROOT / "data/external_panel_log.jsonl"
    if not log.exists():
        defects.append(("panel-never", "external panel has never logged a run"))
        return
    last = ""
    with log.open() as f:
        for line in f:
            last = line
    ts = json.loads(last).get("ts", "")
    age_h = (datetime.now(tz=UTC) - datetime.fromisoformat(ts)).total_seconds() / 3600
    if age_h > 96:
        defects.append(("panel-stale",
                        f"external panel last ran {age_h:.0f}h ago (3d cadence + slack = 96h) "
                        "-- review capability is down (credits? crash?)"))


def check_coverage(defects) -> None:
    m = _j(ROOT / "data/audit_coverage.json", {})
    if not m:
        defects.append(("coverage-missing", "audit_coverage.json absent -- coverage untracked"))
        return
    files = m.get("files", {})
    stale_risk = 0
    for rec in files.values():
        if rec.get("review_class") == 1:
            la = rec.get("last_audited")
            if not la or (datetime.now(tz=UTC) - datetime.fromisoformat(la)).days > 14:
                stale_risk += 1
    if stale_risk:
        defects.append(("coverage-risk-stale",
                        f"{stale_risk} RISK-class (money path) files past their 14d review "
                        "floor -- the exact class that must never go stale"))
    if int(m.get("code_budget_chars", 999999)) <= 40000:
        defects.append(("coverage-budget-floor",
                        "adaptive review payload pinned at its 40k floor -- seats are blanking "
                        "repeatedly; coverage is crawling"))
    for seat, n in (m.get("seat_blanks") or {}).items():
        if int(n) >= 3:
            defects.append((f"seat-chronic-{seat.split('/')[-1]}",
                            f"panel seat {seat} blanked {n}x -- chronic capacity failure, "
                            "swap-candidate with evidence"))


def check_findings(defects) -> None:
    d = _j(ROOT / "data/findings_ledger.json", {})
    old = [f for f in d.get("findings", [])
           if f.get("ruling") == "accepted" and not f.get("fixed")
           and (datetime.now(tz=UTC) - datetime.fromisoformat(f["raised"])).days > 14]
    if old:
        ids = ", ".join(f["id"] for f in old[:5])
        defects.append(("findings-rotting",
                        f"{len(old)} ACCEPTED panel findings unfixed >14d ({ids}) -- the loop "
                        "the audit system exists for is open"))


def check_idle_capability(defects) -> None:
    if (ROOT / "data/secrets/databento.json").exists():
        cme = ROOT / "data/lake/bronze/cme"
        pulled = list(cme.glob("*.csv")) if cme.exists() else []
        if not pulled:
            defects.append(("idle-databento",
                            "Databento key verified but ZERO CME data pulled to Bronze -- "
                            "one-time credits idling"))
    vl = ROOT / "docs/research/video_locked_log.md"
    if vl.exists():
        stale_rows = 0
        for line in vl.read_text("utf-8").splitlines():
            if line.startswith("| 2026"):
                try:
                    d = datetime.fromisoformat(line.split("|")[1].strip())
                    if (datetime.now(tz=UTC) - d.replace(tzinfo=UTC)).days > 7:
                        stale_rows += 1
                except Exception:
                    pass
        if stale_rows:
            defects.append(("video-locked-unactioned",
                            f"{stale_rows} video-locked mechanisms logged >7d with no unlock "
                            "decision -- evidence gate met but purchase page never made?"))


def check_directives(defects) -> None:
    """Time-boxed work orders: registered with a due date; past-due = defect. This is how
    'the brain will do it next cycle' gets teeth instead of drifting forever."""
    for d in _j(ROOT / "data/max_audit_directives.json", []):
        if d.get("due", "9999") < datetime.now(tz=UTC).isoformat():
            defects.append((f"directive-overdue-{d['id']}",
                            f"work order '{d['id']}' past due {d['due'][:10]}: {d['msg']}"))


def check_verify_lag(defects) -> None:
    """The verify pass audits the CRO's own triage -- and the CRO fires it. If triage-bearing
    panels keep running without a verify run following, the auditee is skipping his auditor."""
    log = ROOT / "data/external_panel_log.jsonl"
    if not log.exists():
        return
    last_triage, last_verify = None, None
    with log.open() as f:
        for line in f:
            try:
                r = json.loads(line)
            except Exception:
                continue
            if r.get("mission") == "verify":
                last_verify = r.get("ts")
            elif r.get("mission") in ("audit", "tier1", "premortem", "maximization"):
                last_triage = r.get("ts")
    if last_triage and (not last_verify or last_verify < last_triage):
        age_h = (datetime.now(tz=UTC) - datetime.fromisoformat(last_triage)
                 ).total_seconds() / 3600
        if age_h > 48:
            defects.append(("verify-pass-skipped",
                            f"last triage-bearing panel ({last_triage[:16]}) has had NO verify "
                            "pass after it for >48h -- the auditee is skipping his auditor"))


def check_blind_trigger(defects) -> None:
    """Blind Rediscovery is state-driven, not clock-driven: fire it early when the desk has
    materially new internal raw material (data axes / graveyard entries) since its last run."""
    state = _j(ROOT / "data/cadence_state.json", {})
    last = state.get("last_blind_rediscovery")
    seen = _j(ROOT / "data/blind_trigger_baseline.json", {})

    umap = _j(ROOT / "data/data_universe_map.json", {})
    srcs = umap.get("sources", {})
    n_sources = len(srcs) if isinstance(srcs, (dict, list)) else 0
    gy = ROOT / "docs/graveyard.md"
    n_grave = (sum(1 for ln in gy.read_text("utf-8").splitlines() if ln.startswith("| "))
               if gy.exists() else 0)

    base_src = int(seen.get("sources", 0))
    base_grave = int(seen.get("graveyard", 0))
    d_src, d_grave = n_sources - base_src, n_grave - base_grave

    # thresholds: enough NEW material that first-principles invention has fresh ground
    if d_src >= 5 or d_grave >= 10:
        defects.append(("blind-rediscovery-due-by-state",
                        f"internal state changed materially since last blind-rediscovery "
                        f"({last or 'never'}): +{d_src} data sources, +{d_grave} graveyard "
                        "entries. Fire ops/run_blindrediscovery_dig.sh -- fresh-eyes invention "
                        "has new raw material; do not wait for the monthly floor."))


def check_self_application(defects) -> None:
    """Each of these encodes a max-fix the principal forced this session, as a REGRESSION guard.
    His pressure, made permanent: a future edit that undoes any becomes a same-day defect."""
    orgs = ["run_cro_ai.sh", "run_frontier_miner.sh", "run_prospector_dig.sh",
            "run_litminer_dig.sh", "run_dataaxis_dig.sh", "run_blindrediscovery_dig.sh"]
    for name in orgs:
        fp = ROOT / "ops" / name
        if not fp.exists():
            defects.append((f"organ-missing-{name}", f"organ script {name} vanished"))
            continue
        txt = fp.read_text("utf-8", errors="ignore")
        if "claude" in txt and "-p " in txt:
            if "--effort" not in txt:
                defects.append((f"effort-dropped-{name}",
                                f"{name}: claude call lost its --effort flag (max-reasoning "
                                "regressed to CLI default) -- re-add xhigh"))
            if "--append-system-prompt" not in txt and "_DOCTRINE" not in txt:
                defects.append((f"doctrine-dropped-{name}",
                                f"{name}: lost the principal-doctrine injection "
                                "(--append-system-prompt \"$_DOCTRINE\") -- the max-push stance "
                                "is no longer in this organ"))
    # cost-censorship must never creep back into the advisory layer
    for mp in (ROOT / "prompts/panel_missions").glob("*.txt"):
        if mp.stem == "maximization":
            continue  # legitimately quotes fossils as the anti-patterns it hunts
        t = mp.read_text("utf-8", errors="ignore").lower()
        for fossil in ("worthless", "$1/mo", "at most rare one-off cheap"):
            if fossil in t and "not worthless" not in t:
                # 'worthless' is allowed only in the sanctioned "a recommendation ignoring
                # STRUCTURAL constraints is worthless" phrasing; flag other reappearances
                if fossil == "worthless" and "structural" in t:
                    continue
                defects.append((f"cost-censorship-{mp.stem}",
                                f"panel mission {mp.name}: cost-self-censorship language "
                                f"'{fossil}' reappeared -- money-recs must stay proposable"))
    # recorder scope + liveness -- measure the GROUND-TRUTH tape, not the source code.
    # Until 2026-07-23 this regex-scanned run_recorder.py for a literal `_SYMBOLS = (...)`
    # tuple; gap #39 (2026-07-22) made _SYMBOLS a dynamic expression, so the regex matched
    # nothing, read 0, and FALSE-fired "dropped to 0" while 30 symbols were actively
    # recording. Counting the symbol directories that received a fresh write is the true
    # breadth measure AND catches a silent write-stall the source regex could never see --
    # the desk's own "heartbeat liveness != data liveness" lesson applied to the breadth
    # check (a stalled recorder keeps a fresh heartbeat but stops writing files).
    fut_root = ROOT / "data/moat/fut"
    if fut_root.exists():
        cutoff = time.time() - 1800.0   # a symbol counts only if written in the last 30 min
        live = sum(1 for d in fut_root.iterdir()
                   if d.is_dir() and any(f.stat().st_mtime > cutoff
                                         for f in d.glob("*.jsonl.gz")))
        if live < 20:
            defects.append(("recorder-scope-shrank",
                            f"recorder futures tape has {live} symbols written in the last "
                            "30min (expansion floor is 20) -- forward-tape breadth regressed "
                            "or the recorder stalled"))
    # bybit second-venue recorder must still exist
    if not (ROOT / "scripts/run_recorder_bybit.py").exists():
        defects.append(("bybit-recorder-gone", "second-venue (bybit) recorder script removed -- "
                        "cross-venue tape breadth lost"))
    # CI GATE must be GREEN -- a red desk-wide gate is the safety net down for everyone and
    # sat UNDETECTED for 81h (2026-07-22..23: a stale deadman test failed at HEAD while the
    # brain cycle that runs run_ci was quota-dead, so nothing surfaced the red). run_ci writes
    # data/.ci_last_run.json on every run; surface a red result mechanically so it enters the
    # 48h escalation path instead of hiding until a human notices.
    ci_marker = ROOT / "data/.ci_last_run.json"
    if ci_marker.exists():
        with contextlib.suppress(OSError, json.JSONDecodeError):
            ci = json.loads(ci_marker.read_text("utf-8"))
            if ci.get("ok") is False:
                defects.append(("ci-gate-red",
                                f"last CI run ({ci.get('ts')}) was RED -> {ci.get('failed')}; "
                                "the desk-wide safety gate is down. Run scripts/run_ci.py + fix"))


def check_dig_depth(defects) -> None:
    """Depth guard: a substantial dig log that shows NO depth markers (never mined a reply
    chain, followed a fork, or chased a citation) is breadth-theater -- flag it. Depth quality
    ultimately shows in output and is judged by red-team/maximization; this catches the gross
    wide-and-shallow case mechanically."""
    markers = ("repl", "comment", "thread", "fork", "citation", "issue", "discussion",
               ">=2", "deep", "exhaust", "debunk")
    for pat in ("frontier_*.log", "dataaxis_*.log", "prospector_*.log", "litminer_*.log"):
        logs = sorted(LOGS.glob(pat), key=lambda p: p.stat().st_mtime, reverse=True)
        if not logs:
            continue
        newest = logs[0]
        _mand = ROOT / "data/depth_mandate_baseline"
        if not _mand.exists():
            _mand.write_text(str(NOW))
        try:
            _base = float(_mand.read_text().strip())
        except Exception:
            _base = NOW
        if newest.stat().st_mtime < _base:
            continue                                  # pre-mandate dig -- not judged
        if (NOW - newest.stat().st_mtime) > 4 * 86400:
            continue                                  # stale digs handled by check_organs
        if newest.stat().st_size < 1500:
            continue                                  # stub/quota-death handled elsewhere
        txt = newest.read_text("utf-8", errors="ignore").lower()
        hits = sum(1 for m in markers if m in txt)
        if hits < 2:
            defects.append((f"dig-shallow-{newest.stem}",
                            f"{newest.name}: substantial dig with <2 depth markers "
                            f"({hits}) -- breadth-theater, no reply/fork/citation mining "
                            "evident. Depth mandate not honored."))


def check_interrogation(defects) -> None:
    """The last successful brain cycle must show evidence it ran the self-interrogation battery.
    A cycle that did not probe is a cycle that trusted itself -- the exact failure this catches.
    Only judged on cycles that ran AFTER the protocol existed."""
    base_f = ROOT / "data/interrogation_baseline"
    if not base_f.exists():
        base_f.write_text(str(NOW))
        return
    try:
        base = float(base_f.read_text().strip())
    except Exception:
        return
    cyc = [p for p in LOGS.glob("2026*_*.log")
           if p.stat().st_mtime >= base and p.stat().st_size >= 2000]
    if not cyc:
        return                                        # no post-protocol successful cycle yet
    newest = max(cyc, key=lambda p: p.stat().st_mtime)
    txt = newest.read_text("utf-8", errors="ignore").lower()
    if not any(k in txt for k in ("interrogat", "probe", "verified with a fresh read",
                                  "self-interrog", "angle")):
        defects.append(("cycle-skipped-interrogation",
                        f"{newest.name}: last successful cycle shows no self-interrogation "
                        "evidence -- it trusted itself instead of probing. Protocol not honored."))


def check_generation(defects) -> None:
    """Hypothesis testing is the primary output. If SUCCESSFUL brain cycles have run since a
    baseline but last_live_generate has not advanced, generation is being skipped -- escalate.
    Also flags the simple case: generation owed and long-stale.

    ARTIFACT OVER FLAG (2026-07-28). This read ONLY cadence_state.last_live_generate -- a key a
    cycle sets by hand -- and so reported generation "skipped" on a day the Stage-A executor had
    already screened and written real verdicts, while it would equally have reported generation
    DONE for a cycle that touched nothing but the timestamp. Both errors have the same root: the
    check trusted a flag instead of demanding the product, which is the exact failure the desk's
    own check_production exists to catch (`scheduled but not PRODUCING`). The verdict ledger is
    the artifact -- newest of {flag, last real verdict row} wins, and a run that screens without
    updating the key is now correctly credited.
    """
    cs = _j(ROOT / "data/cadence_state.json", {})
    last_gen = cs.get("last_live_generate") or cs.get("gen_done_fred_macro")
    verdicts = ROOT / "data/stage_a_verdicts.jsonl"
    last_verdict = None
    if verdicts.exists():
        with contextlib.suppress(Exception):
            for ln in reversed(verdicts.read_text("utf-8").splitlines()):
                if ln.strip() and (ts := json.loads(ln).get("ts")):
                    last_verdict = ts                 # newest row carrying a real timestamp
                    break
    if last_verdict and (not last_gen or last_verdict > last_gen):
        last_gen = last_verdict
    # successful cycles since a fixed watch baseline
    base_f = ROOT / "data/generation_watch_baseline"
    if not base_f.exists():
        base_f.write_text(str(NOW))
    try:
        base = float(base_f.read_text().strip())
    except Exception:
        base = NOW
    good_cycles = [p for p in LOGS.glob("2026*_*.log")
                   if p.stat().st_mtime >= base and p.stat().st_size >= 2000]
    if not good_cycles:
        return                                        # no successful cycle yet -- quota, not skip
    newest_cycle = max(p.stat().st_mtime for p in good_cycles)
    gen_ts = 0.0
    if last_gen:
        with contextlib.suppress(Exception):
            gen_ts = datetime.fromisoformat(last_gen).timestamp()
    # a successful cycle ran AFTER the last generation -> generation was skipped
    if newest_cycle > gen_ts + 3600:
        defects.append(("generation-skipped",
                        f"a successful brain cycle ran with no generation after it "
                        f"(last screened verdict / gen flag: {last_gen}) -- hypothesis testing, "
                        "the desk's PRIMARY output, "
                        "is being crowded out by meta-duties. Generation-first duty not honored."))


def check_self_sufficiency(defects) -> None:
    """The meta-check: is the desk finding its own gaps, or is the principal still doing it?
    Reads the blind-spot ledger; if over the recent window the principal is the primary finder,
    the whole maximization apparatus is not yet working -- the top-level defect."""
    lg = ROOT / "data/blind_spot_ledger.jsonl"
    if not lg.exists():
        return
    rows = []
    for line in lg.read_text("utf-8").splitlines():
        with contextlib.suppress(Exception):
            rows.append(json.loads(line))
    live = [r for r in rows if not r.get("baseline")]  # judge post-baseline gaps only
    if len(live) < 8:
        return                                          # not enough signal yet
    by = {"self": 0, "guard": 0, "principal": 0}
    for r in live:
        by[r.get("origin", "principal")] = by.get(r.get("origin", "principal"), 0) + 1
    if by["principal"] > by["self"] + by["guard"]:
        defects.append(("system-not-self-sufficient",
                        f"blind-spot ledger: principal still the primary gap-finder "
                        f"({by['principal']} vs self {by['self']} + guard {by['guard']}) -- the "
                        "maximization system is not yet doing its job. TOP defect."))


def _blind_rows_window(days=7):
    lg = ROOT / "data/blind_spot_ledger.jsonl"
    if not lg.exists():
        return []
    cut = NOW - days * 86400
    out = []
    for line in lg.read_text("utf-8").splitlines():
        try:
            r = json.loads(line)
        except Exception:
            continue
        if r.get("baseline"):
            continue
        try:
            if datetime.fromisoformat(r["ts"]).timestamp() >= cut:
                out.append(r)
        except Exception:
            pass
    return out


def check_rubberstamp_detector(defects) -> None:
    """Signature: >=3 successful cycles CLAIMED interrogation, found ZERO gaps themselves, yet
    the principal found >=2 in the same window. That is probing theater. Auto-activate the
    enforcement, page, and log -- the desk deciding for itself that it needs the higher bar."""
    flag = ROOT / "data/ANTIRUBBERSTAMP_ACTIVE"
    if flag.exists():
        return                                        # already active
    cyc = [p for p in LOGS.glob("2026*_*.log") if p.stat().st_size >= 2000
           and (NOW - p.stat().st_mtime) < 7 * 86400]
    interrogated = 0
    for p in cyc:
        t = p.read_text("utf-8", errors="ignore").lower()
        if any(k in t for k in ("interrogat", "probe", "self-interrog")):
            interrogated += 1
    rows = _blind_rows_window(7)
    self_ct = sum(1 for r in rows if r.get("origin") == "self")
    princ_ct = sum(1 for r in rows if r.get("origin") == "principal")
    if interrogated >= 3 and self_ct == 0 and princ_ct >= 2:
        flag.write_text(f"auto-activated {datetime.now(tz=UTC).isoformat()}: {interrogated} "
                        f"cycles claimed interrogation, 0 self-gaps, {princ_ct} principal-gaps "
                        "-- rubber-stamp signature")
        defects.append(("rubberstamp-detected-ACTIVATED",
                        f"RUBBER-STAMP SIGNATURE: {interrogated} cycles claimed to interrogate but "
                        f"found 0 gaps while the principal found {princ_ct}. Anti-rubber-stamp "
                        "enforcement AUTO-ACTIVATED -- cycles must cite named reads per angle."))
        try:
            import subprocess
            subprocess.run(["python", "scripts/blind_spot.py", "log", "--origin", "guard",
                            "--summary", "auto-activated anti-rubber-stamp: interrogation was "
                            "probing theater (claimed, found nothing, principal found real gaps)"],
                           cwd=str(ROOT), timeout=20)
        except Exception:
            pass


def check_rubberstamp_enforcement(defects) -> None:
    """Active only when the flag exists: the newest successful cycle must show NAMED VERIFIED
    READS (file-path citations proving it actually looked), not bare 'verified' prose."""
    flag = ROOT / "data/ANTIRUBBERSTAMP_ACTIVE"
    if not flag.exists():
        return
    cyc = [p for p in LOGS.glob("2026*_*.log")
           if p.stat().st_size >= 2000 and (NOW - p.stat().st_mtime) < 2 * 86400]
    if not cyc:
        return
    newest = max(cyc, key=lambda p: p.stat().st_mtime)
    t = newest.read_text("utf-8", errors="ignore")
    cites = len(set(re.findall(r"[\w/]+\.(?:py|json|md|sh|txt)", t)))
    if cites < 5:
        defects.append(("rubberstamp-enforced",
                        f"{newest.name}: anti-rubber-stamp ACTIVE but the cycle cites only {cites} "
                        "named reads -- interrogation lacks verified-read evidence. Cite the "
                        "specific file+value per probe angle, do not rubber-stamp."))


def check_clock_saturation(defects) -> None:
    """OBJECTIVE #2 CLOCK-SATURATION DUTY (principal 2026-07-23), made mechanical.

    Every VERIFIED data axis must have a pre-registered hypothesis ACCRUING within 7 days. An
    empty forward-validation slot is idle capital's research twin: the axis was ingested (real
    cost paid) but is generating zero evidence, so the discovery objective is silently stalled.

    This duty shipped as prompt text only -- and prompt-only duties are aspirations. The desk's
    recursion rule is that every manual probe becomes a standing automatic check, so it is fenced
    here. Axes are read from the Bronze lake (what was actually ingested, not what a doc claims);
    clocks are read from cadence_state gen_done_* (what actually ran)."""
    bronze = ROOT / "data/lake/bronze"
    cad_p = ROOT / "data/cadence_state.json"
    if not bronze.exists() or not cad_p.exists():
        return
    try:
        cad = json.loads(cad_p.read_text("utf-8"))
    except Exception:
        return
    # INPUT STORES are not axes: raw price/metrics lakes feed constructions but cannot carry
    # a hypothesis themselves (the constructions built FROM them do). Excluding them keeps this
    # check pointed at genuinely idle research axes instead of manufacturing false defects.
    _input_stores = {"futclose_daily", "oi_ls_daily", "fx", "index", "crypto", "binance_metrics"}
    axes = sorted(d.name for d in bronze.iterdir() if d.is_dir() and d.name not in _input_stores)
    if not axes:
        return
    stale = []
    for ax in axes:
        ts = cad.get(f"gen_done_{ax}") or cad.get(f"gen_done_{ax}_family")
        if not ts:
            stale.append(f"{ax}(never)")
            continue
        try:
            age_d = (NOW - datetime.fromisoformat(ts).timestamp()) / 86400.0
            if age_d > 7:
                stale.append(f"{ax}({age_d:.0f}d)")
        except Exception:
            stale.append(f"{ax}(unparsable)")
    if stale:
        defects.append((
            "clock-saturation",
            f"OBJECTIVE #2 breach: {len(stale)}/{len(axes)} verified axes have NO hypothesis "
            f"accruing within 7d -- {', '.join(stale[:8])}"
            f"{' ...' if len(stale) > 8 else ''}. An empty forward clock is idle research "
            "capital: pre-register a hypothesis on each, or ledger why the axis is not yet "
            "testable (e.g. forward history under the gauntlet minimum)."))


def check_vendor_replacement(defects) -> None:
    """FREE-ALTERNATIVES-TO-PAID enforcement (principal 2026-07-24). The dataaxis dig's pillar 6
    mandates decomposing every paid vendor into a free reconstruction with a ground-truth diff;
    this check makes that output rot-proof: entries must be complete, UNVERIFIED grades must not
    sit while a daily dig runs, and the free-hunt itself must keep landing updates."""
    ump = ROOT / "data/data_universe_map.json"
    if not ump.exists():
        defects.append(("vendor-replacement", "data_universe_map.json MISSING"))
        return
    try:
        d = json.loads(ump.read_text("utf-8"))
    except Exception as e:
        defects.append(("vendor-replacement", f"universe map unreadable: {e!r}"))
        return
    vr = (d.get("sources") or {}).get("vendor_replacement") or []
    if not isinstance(vr, list) or not vr:
        defects.append(("vendor-replacement",
                        "no vendor_replacement entries -- the free-alternatives hunt has "
                        "recorded zero paid-vendor decompositions"))
        return
    for e in vr:
        v = str(e.get("vendor", "?"))[:40]
        if not e.get("free_path"):
            defects.append(("vendor-replacement",
                            f"{v}: NO free_path -- a paid product with no owned reconstruction"))
        if not e.get("ground_truth_for_diff"):
            defects.append(("vendor-replacement",
                            f"{v}: NO ground_truth_for_diff -- verify-don't-trust is impossible; "
                            "find a free sample/reference to diff the reconstruction against"))
        g = str(e.get("grade", "")).lower()
        if "unverified" in g:
            defects.append(("vendor-replacement",
                            f"{v}: grade UNVERIFIED while the free-data dig runs DAILY -- "
                            "verify the free path this cycle or ledger why it cannot be"))
    # the hunt itself must keep landing: daily dig -> map bookkeeping must move
    try:
        lfd = datetime.fromisoformat(str(d.get("last_free_dig")))
        age_d = (NOW - lfd.timestamp()) / 86400.0
        if age_d > 3:
            defects.append(("vendor-replacement",
                            f"last_free_dig {age_d:.1f}d old while the data-axis dig is DAILY -- "
                            "the free-alternatives hunt is not landing updates to the map"))
    except Exception:
        defects.append(("vendor-replacement", "last_free_dig missing/unparsable in universe map"))


def check_forensics_fresh(defects) -> None:
    """DAILY PnL/churn/loss analysis is GUARANTEED, not assumed (principal 2026-07-24): the
    trade-forensics probe (the mechanical version of the probes that found gaps #42/#43/#34)
    must have produced a fresh verdict within 26h, or the desk is flying without its daily
    bleed detection -- the exact silent-leak failure mode the integrity watch exists to kill."""
    fj = ROOT / "web/trade_forensics.json"
    if not fj.exists():
        defects.append(("forensics-stale", "web/trade_forensics.json MISSING -- daily "
                        "trade-class bleed analysis has never produced output"))
        return
    age_h = (NOW - fj.stat().st_mtime) / 3600.0
    if age_h > 26:
        defects.append(("forensics-stale",
                        f"trade_forensics.json {age_h:.0f}h old (>26h) -- the daily churn/"
                        "bleed/PnL analysis is not landing; check daily_research_cycle"))


def check_carry_funding_measured(defects) -> None:
    """The carry-leak alarm must be able to SEE (2026-07-26 incident).

    The alarm is denominated in the funding harvest, so a failed venue read blinds it entirely.
    Before this check the executor filled that gap with `0.0` and the alarm dutifully published an
    `inf%` total-bleed verdict against a book that had really earned $101.96 -- an HTTP 502
    rendered as an economic judgement. The fix makes the harvest honestly None, which means the
    alarm now goes QUIET during an outage instead of loud-and-wrong; that trade is only safe if
    the silence itself is a tracked defect, which is this function. A blind alarm and a clean book
    look identical on a dashboard and must never look identical here.
    """
    cj = ROOT / "web/cashcarry_live.json"
    if not cj.exists():
        return                                        # book not running is a different check
    try:
        cc = json.loads(cj.read_text("utf-8"))
    except Exception:
        defects.append(("carry-funding-unmeasured", "web/cashcarry_live.json unparsable -- the "
                        "carry-leak alarm cannot be read at all"))
        return
    # Absent key = an executor predating the fix, which is exactly the silent-zero state.
    if cc.get("funding_measured", False) is not True:
        age_h = (NOW - cj.stat().st_mtime) / 3600.0
        defects.append((
            "carry-funding-unmeasured",
            f"carry funding harvest UNMEASURED (venue income read failing, book {age_h:.0f}h old) "
            f"-- the leak alarm is BLIND: it cannot tell a clean hedge from a bleeding one, and "
            f"the forward track record the sizing gate reads is accruing without its edge term. "
            f"Verdict: {str(cc.get('bleed_verdict', ''))[:120]}"))
        return
    # THE ALARM ACTUALLY FIRING must fail something too. Until 2026-07-31 this branch did not
    # exist: bleed_alert was computed, written to JSON, rendered on the dashboard -- and gated
    # nothing, so a book whose non-funding P&L was 3146% of its harvest could read as a SURVIVOR.
    # A fence firing into a field nobody reads is not a fence.
    if cc.get("bleed_alert") is True:
        defects.append((
            "carry-bleed-alarm",
            f"carry leak alarm FIRING and unactioned -- {str(cc.get('bleed_verdict', ''))[:200]}"))


def check_memory_hygiene(defects) -> None:
    """MEMORY layer fences (principal 2026-07-24): institutional memory must be written, fresh,
    and retrievable -- a memory system nobody writes to or that outgrows retrieval is theater.
    Found at audit time: research_memory had 0 rows ever while mission directives claim to write
    it; the brain memory index was a week stale and used the principal old name."""
    # (a) the brain's own memory index must stay fresh (it is the first thing cycles read)
    mi = ROOT / "ops/memory/MEMORY.md"
    if mi.exists():
        age_d = (NOW - mi.stat().st_mtime) / 86400.0
        if age_d > 7:
            defects.append(("memory-index-stale",
                            f"ops/memory/MEMORY.md {age_d:.0f}d old -- the brain memory index "
                            "must be refreshed weekly with current desk state (cycle duty)"))
    # (b) research_memory must actually be written by the analyst missions that cite it
    try:
        import sqlite3
        n = sqlite3.connect(str(ROOT / "data/sor_research.sqlite")).execute(
            "SELECT COUNT(*) FROM research_memory").fetchone()[0]
        if n == 0:
            defects.append(("research-memory-unused",
                            "research_memory has 0 rows EVER while mission directives claim "
                            "every analyst pass writes to it -- either write it (hypothesis ID + "
                            "economic logic + EV score per mission) or remove the claim"))
    except Exception:
        pass
    # (c) ledger bloat: append-only is sacred, but retrieval must survive growth
    lp = ROOT / "data/decision_ledger.json"
    if lp.exists() and lp.stat().st_size > 1_500_000:
        defects.append(("ledger-bloat",
                        f"decision_ledger.json {lp.stat().st_size/1e6:.1f}MB -- run the memory-"
                        "consolidation duty (archive-never-delete, index the archive) before "
                        "tail-reads go lossy"))


def check_prompt_layer(defects) -> None:
    """PROMPT-LAYER hygiene (principal 2026-07-24 prompt audit): the prompts are organs too.
    (a) Doctrine bloat: the doctrine is prepended to EVERY organ call; past ~16k chars the
    stacked supreme-blocks start diluting mission instructions -- consolidate, never just stack.
    (b) State-triggered prompt review: the 28d review cadence is calendar-based, but when the
    contract/doctrine change materially the review is due by STATE (the blind-rediscovery
    precedent) -- a week of unreviewed prompt mutations is how contradictions accrete."""
    doc = ROOT / "ops/principal_doctrine.txt"
    if doc.exists() and doc.stat().st_size > 16000:
        defects.append(("prompt-doctrine-bloat",
                        f"principal_doctrine.txt {doc.stat().st_size/1000:.1f}k chars (>16k) -- "
                        "consolidate the stacked axiom blocks into tighter prose (preserve every "
                        "commitment, cut the repetition); every organ pays this context"))
    try:
        cad = json.loads((ROOT / "data/cadence_state.json").read_text("utf-8"))
        last_rev = datetime.fromisoformat(cad["last_prompt_review"]).timestamp()
        contract = (ROOT / "ops/run_cro_ai.sh").stat().st_mtime
        doc_m = doc.stat().st_mtime if doc.exists() else 0
        newest_change = max(contract, doc_m)
        if newest_change > last_rev and (NOW - newest_change) / 86400.0 > 7:
            defects.append(("prompt-review-due-by-state",
                            "contract/doctrine changed materially since the last prompt review "
                            f"({cad['last_prompt_review'][:10]}) and the newest change is >7d "
                            "old -- run the prompt-review duty NOW (check for duty collisions, "
                            "stale numbers, contradictions), do not wait for the 28d floor"))
    except Exception:
        pass


def check_bnb_funded(defects) -> None:
    """BNB fee-burn is enabled (feeBurn:True) but only DISCOUNTS when BNB is held. Audit 2026-07-24:
    balance 0 -> the whole commission line was paid at rack rate while the desk believed the ~25%
    discount was active. feeBurn:True is STATE; a funded BNB balance is the OUTCOME that matters."""
    try:
        from libs.execution import binance_testnet as _fut
        bal = 0.0
        for b in _fut._signed("/fapi/v2/balance", {}):
            if b.get("asset") == "BNB":
                bal = float(b.get("balance", 0.0))
        if bal <= 0.0:
            defects.append(("bnb-burn-unfunded",
                            "fee-burn is ON (feeBurn:True) but BNB balance is 0 -- the ~25% "
                            "discount is INERT and commissions are paid at rack rate. Fund a small "
                            "BNB balance (or accept it as a testnet limitation and ledger why)."))
    except Exception:
        pass


def check_production(defects) -> None:
    """OUTCOME-LEVEL fence (principal 2026-07-24): does each scheduled organ actually PRODUCE its
    output artifact within cadence? State-freshness checks miss the class where a scheduler fires
    but nothing is produced (cron self-match), an organ runs but refuses to emit (panel
    sanitizer), or a duty is claimed but writes nothing (research_memory). Product artifacts, not
    state files -- state can be touched without producing."""
    import glob as _glob
    # (label, product glob, max_age_h, min_bytes). Products, not state files.
    manifest = [
        ("cron-cycle", "data/cro_ai_logs/2026*_????.log", 26, 2000),
        ("panel-verdicts", "data/panel_verdicts.jsonl", 96, 100),
        ("dataaxis-product", "docs/research/data_axis_watchlist.md", 30, 100),
        ("prospector-product", "docs/research/prospector_watchlist.md", 30, 100),
        ("litminer-product", "docs/research/*iterature*coverage*.md", 30, 50),
        ("frontier-product", "docs/research/prospector_coverage.md", 30, 100),
        ("crypto-factory", "web/autodiscovery_crypto.json", 30, 100),
        ("forensics", "web/trade_forensics.json", 30, 50),
    ]
    for label, pat, max_h, min_b in manifest:
        hits = [Path(q) for q in _glob.glob(str(ROOT / pat))]
        if not hits:
            defects.append(("production-missing",
                            f"{label}: NO product artifact exists ({pat}) -- the organ has never "
                            "produced output, only (maybe) been scheduled"))
            continue
        newest = max(hits, key=lambda q: q.stat().st_mtime)
        age_h = (NOW - newest.stat().st_mtime) / 3600.0
        sz = newest.stat().st_size
        if age_h > max_h:
            defects.append(("production-stale",
                            f"{label}: {newest.name} {age_h:.0f}h old (cad {max_h}h) "
                            "-- scheduled but not PRODUCING; verify the organ actually runs end-to-"
                            "end, not just that its timer/cron fires (the cron-self-match class)"))
        elif sz < min_b and not _producer_running(label):
            defects.append(("production-stub",
                            f"{label}: product {newest.name} is {sz}b (<{min_b}b) -- ran but "
                            "produced a stub, not real output (the quota-stub / refuse class)"))
    # research_memory must GROW, not just be non-zero (the null-pipe class)
    try:
        import sqlite3
        n = sqlite3.connect(str(ROOT / "data/sor_research.sqlite")).execute(
            "SELECT COUNT(*) FROM research_memory WHERE created_at >= datetime('now','-7 days') "
            "AND category != 'method'"   # exclude meta/seed rows -- a self-referential seed must
            "").fetchone()[0]             # not green the guard (2026-07-24 audit: 1 seed did)
        if n == 0:
            defects.append(("production-research-memory-flat",
                            "research_memory added 0 rows in 7d -- the conversion loop is not "
                            "recording experiments (writable via scripts/research_memory.py; the "
                            "duty exists, verify missions actually call it)"))
    except Exception:
        pass


def check_gate_optimality(defects) -> None:
    """GATE-OPTIMALITY MONITOR (principal 2026-07-24): the DSR/gauntlet bar must stay OPTIMAL --
    a gate that rejects ~100pct or accepts ~100pct of candidates carries ZERO information and is
    a defect (good alphas lost to an accidentally-too-high bar cost as much as false ones
    admitted). Reads the per-gate rejection histogram; flags any gate at >=98pct reject over a
    non-trivial sample as suspect (mis-applied campaign-level veto, mis-calibration, or a bar
    that has silently become unclearable)."""
    wf = ROOT / "web/autodiscovery_crypto.json"
    if not wf.exists():
        return
    try:
        d = json.loads(wf.read_text("utf-8"))
    except Exception:
        return
    tested = int(d.get("cumulative_tested", 0) or 0)
    hist = d.get("rejection_by_gate", {}) or {}
    if tested < 30 or not hist:
        return
    pegged = [g for g, n in hist.items() if tested and (int(n) / tested) >= 0.98]
    if pegged:
        # Reconciliation rule 3: COMPUTE effective-vs-raw n_trials instead of only asking a human
        # to "audit" it. A raw tally that inflates far past the independent-mechanism count sets
        # the DSR bar unclearable -- the concrete way a pegged gate becomes a survivor-killer.
        from libs.autodiscovery.extraction_parity import effective_trial_count
        eff = effective_trial_count(_trial_mechanisms())
        infl = (f" Effective-vs-raw n_trials: raw {eff.raw} vs {eff.effective} independent "
                f"mechanisms ({eff.inflation:.1f}x inflation) -- "
                + ("deflate DSR by the EFFECTIVE count." if eff.inflation > 1.5
                   else "count is not the cause here.")) if eff.raw else ""
        defects.append((
            "gate-optimality",
            f"gate(s) rejecting >=98pct of {tested} candidates: {', '.join(sorted(pegged))} -- "
            "a ~100pct-constant gate carries zero information. Verify it is genuinely "
            "discriminating, not a campaign-level statistic mis-applied per-candidate or a bar "
            f"risen unclearable; real alphas may be dying at it.{infl}"))
    if int(d.get("cumulative_survivors", 0) or 0) == 0 and tested >= 200:
        defects.append((
            "gate-optimality-zero-survivors",
            f"0 survivors across {tested} tested -- expected on picked-clean price space, but "
            "confirm the funnel can EVER promote: is any single gate the 100pct bottleneck, and "
            "is the walk-forward/per-candidate path able to pass a genuinely-good synthetic?"))


def check_welded_gates(defects) -> None:
    """WELDED-GATE SCAN (RECURSION RULE, 2026-07-30): a per-candidate gate fed a CAMPAIGN CONSTANT.

    Origin, measured this cycle on the real 420-candidate campaign: PBO and White's Reality Check
    take ONLY the returns matrix -- the candidate's own returns are never an input -- so used as
    per-candidate gates they are campaign constants. At PBO 0.6159 / RC p 0.4220 that forced
    420/420 rejections regardless of merit, and 420-tested/0-survivors measured the instrument
    rather than the market. The orchestrator was repaired (pbo 0/420 -> 209/420) and 21 OTHER
    gauntlet scripts were still welded at the time of writing.

    Mechanical so it can never rot back: flags any call site that computes campaign_pbo_rc() and
    feeds the result to validate() as pbo=/rc=. Legitimate non-gate uses are exempt -- the
    deprecated shim itself, the measurement harness that deliberately runs BOTH arms to compare,
    and tests that assert the legacy path still behaves exactly as before.
    """
    exempt = {
        "libs/autodiscovery/validation.py",      # defines the deprecated shim
        "scripts/measure_gate_histogram.py",     # runs both arms on purpose, to compare them
        "scripts/max_audit.py",                  # this scanner DESCRIBES the pattern in prose;
                                                 # scanning itself is the cron-self-match class
    }
    welded: list[str] = []
    for base in ("scripts", "libs"):
        for p in sorted((ROOT / base).rglob("*.py")):
            rel = p.relative_to(ROOT).as_posix()
            if rel in exempt or "/tests/" in f"/{rel}" or rel.startswith("tests/"):
                continue
            try:
                src = p.read_text("utf-8", errors="replace")
            except Exception:
                continue
            # The weld signature: the campaign constant is computed AND handed to validate() as a
            # per-candidate gate input. Either half alone is not the defect.
            if "campaign_pbo_rc(" in src and re.search(r"\bpbo\s*=\s*pbo\b|\brc\s*=\s*rc\b"
                                                       r"|pbo=pbo_once|rc=rc_once", src):
                welded.append(rel)
    if welded:
        shown = ", ".join(welded[:6]) + (f" ... +{len(welded) - 6} more" if len(welded) > 6 else "")
        defects.append((
            "welded-gate-campaign-constant",
            f"{len(welded)} validation path(s) still feed a CAMPAIGN CONSTANT to a per-candidate "
            f"gate: {shown}. PBO/RC do not read the candidate's own returns, so every candidate in "
            "a batch gets one verdict whatever its merit -- measured at 420/420 rejected. Migrate "
            "to campaign_gate_stats() + validate(campaign=..., column=...). PHANTOM-EDGE CRITICAL: "
            "verify the column index maps to the matrix column_stack order per file -- a mis-mapped "
            "index hands one candidate's passing verdict to another, which is worse than the weld."))


def check_data_utilization(defects) -> None:
    """DATA-UTILIZATION LAW, reconciled with the GATE-OPTIMALITY MONITOR (principal 2026-07-24).

    The naive law ("idle data is paralysis; scale extraction") conflicts with gate-optimality:
    mass combinatorial/genetic generation to clear the flag explodes the trial count and deflates
    the DSR bar unclearable (the 420->0 dynamic). Binding reconciliation (extraction_parity.py):
    paralysis is a COVERAGE gap, NOT a volume gap. It clears when every ingested axis carries >=1
    screened, economically-motivated hypothesis (~one mechanism-first trial per axis, ~20 trials),
    never on hypothesis count. So this check measures COVERAGE of the acquired surface, and its
    remedy is mechanism-first coverage of the idle axes -- explicitly NOT volume."""
    from libs.autodiscovery.extraction_parity import axis_coverage

    acquired = _acquired_axes()
    if len(acquired) < 8:
        return  # too small a surface to judge parity
    tags = _converted_axes()
    # tolerant match: an acquired axis is 'covered' if any converted-axis name shares its normalized
    # name (handles collector-store vs axis-name drift, e.g. cny_premium.jsonl <-> cny_premium)
    def _covered(axis: str) -> bool:
        a = axis.lower()
        return any(t == a or t in a or a in t for t in tags)
    covered = [a for a in acquired if _covered(a)]
    rep = axis_coverage(axes=acquired, screened_axes=covered)
    if not rep.cleared:
        shown = ", ".join(rep.idle[:8]) + (" ..." if len(rep.idle) > 8 else "")
        defects.append((
            "data-utilization-paralysis",
            f"{len(rep.idle)}/{rep.n_axes} ingested axes have 0 screened hypothesis "
            f"({rep.coverage_frac:.0%} coverage): {shown} -- DATA PARALYSIS is a COVERAGE gap. "
            "Convert each idle axis MECHANISM-FIRST: one screened, economically-motivated "
            "hypothesis per axis (tag it via research_memory.py --axis). Do NOT clear this by "
            "generating volume -- combinatorial/genetic expansion is EARNED per axis only after "
            "its single-axis screen shows signal (else it is pure DSR deflation)."))


def check_post_gate0_activation(defects) -> None:
    """POST-GATE-0 ACTIVATION INTERLOCK (enforces 'nothing deferred may be skipped').

    The freeze-exit is auto-detected by run_cadence and the POST_GATE0 manifest is flagged for
    activation -- but activation itself was a DIRECTIVE the brain cycle had to obey, with no check
    that it actually happened. This closes that: the moment Gate 0 is complete
    (``data/gate0_complete``) but the cadence state has not set ``post_gate0_activated``, the entire
    deferred queue (docs/POST_GATE0_MANIFEST.md) is sitting un-built -- a defect that escalates to
    the principal at 48h. So the automatic build is VERIFIED to fire, never silently missed."""
    if not (ROOT / "data/gate0_complete").exists():
        return  # pre-Gate-0: the freeze correctly holds, the manifest is not due yet
    state = _j(ROOT / "data/cadence_state.json", {})
    if not (isinstance(state, dict) and state.get("post_gate0_activated")):
        defects.append((
            "post-gate0-activation",
            "Gate 0 is COMPLETE (data/gate0_complete) but post_gate0_activated is NOT set -- the "
            "POST_GATE0 manifest has not activated, so every deferred item (data collectors, "
            "growth ramp, live organs, runtime-gated research completions) is sitting un-built. "
            "Activate docs/POST_GATE0_MANIFEST.md top-to-bottom in EV order THIS cycle; nothing "
            "deferred may be skipped."))


def check_rejection_shadow(defects) -> None:
    """REJECTION-SHADOW standing duty (gate-calibration, MAX_SURVIVORS Part 1.2): the gauntlet
    rejects most candidates -- correct on picked-clean price space -- but a gate that drifted
    over-strict silently LEAKS real edges. run_rejection_shadow.py shadow-tracks a sample of rejects
    forward and writes web/reject_shadow.json. This check surfaces its verdict every cycle: (a) an
    OVER-STRICT gate is a defect (recover the leaked edges); (b) rejects piling up with the audit
    never run / stale is itself a defect (the recovery loop is off). Pure recovery, no new data."""
    rf = ROOT / "web/reject_shadow.json"
    d = _j(rf, None)
    if not isinstance(d, dict):
        return  # runner has never produced output yet -- surfaced by production/organ checks
    audit = d.get("audit", {}) if isinstance(d.get("audit"), dict) else {}
    if audit.get("over_strict"):
        leak = audit.get("leak_frac", 0.0)
        n = audit.get("n_rejects", 0)
        defects.append((
            "rejection-shadow-overstrict",
            f"gate OVER-STRICT: {audit.get('n_would_have_paid', 0)}/{n} shadowed rejects "
            f"({float(leak):.0%}) would have paid out-of-sample -- the gate is leaking survivors. "
            "Re-calibrate (effective-trial count, per-gate bar) and re-examine the leaked ids; "
            "this is pure recovery, no new data."))
    n_elig = int(d.get("n_eligible", 0) or 0)
    n_pending = int(d.get("n_pending_rescore", 0) or 0)
    if n_elig >= 5 and n_pending == n_elig:
        defects.append((
            "rejection-shadow-unscored",
            f"{n_elig} rejects are old enough to judge but NONE are forward-scored -- the reject "
            "forward-evaluator is not feeding data/reject_forward_scores.json, so the gate-leak "
            "audit cannot run. Wire the re-score so wrongly-rejected edges can be recovered."))


def check_source_backlog(defects) -> None:
    """SOURCE-VERIFICATION BACKLOG DUTY: the catalogue (data_axis_watchlist.md) already grows
    faster than it gets verified -- prospector/litminer run daily and add candidate source cards;
    verifying one (real docs read, real endpoint test) is the actual bottleneck, not discovery.
    Flags a STALE backlog: pending cards exist but the watchlist file hasn't been touched (a card
    resolved/added) in a long time -- the verification loop has stopped, silently, while discovery
    keeps running. This is the coverage-not-volume discipline applied to sourcing: the fix is
    working scripts/source_backlog_next.py's queue, never cataloguing more."""
    from libs.research.source_backlog import backlog_from_file

    wf = ROOT / "docs/research/data_axis_watchlist.md"
    if not wf.exists():
        return
    rep = backlog_from_file(wf, limit=1)
    pending = rep.n_verification_pending + rep.n_legitimacy_pending
    if pending == 0:
        return
    stale_days = 14.0
    age_h = (NOW - wf.stat().st_mtime) / 3600.0
    if age_h / 24.0 > stale_days:
        defects.append((
            "source-backlog-stale",
            f"{pending} catalogued source(s) still pending (verification or legitimacy decision) "
            f"and the watchlist has not been touched in {age_h / 24.0:.0f}d -- discovery is "
            "outrunning verification. Run scripts/source_backlog_next.py and clear the next item, "
            "do not catalogue more."))


def check_depth_parity(defects) -> None:
    """DEPTH-BREADTH PARITY LAW enforcement (charter §32): depth must keep pace with breadth,
    never lag it. A forward-clock axis that sits SHALLOW (< DEEP_DAYS of history) while the desk
    keeps widening breadth is a defect -- a shallow axis waits weeks on the forward clock and
    cannot validate, so breadth without depth is unconverted potential (the utilisation-without-
    conversion trap). Flags shallow clock axes as backfill targets (reconstruct to archive depth,
    MAX_SURVIVORS Part 1 #1). An axis already backfilled (has a reconstructed_oos report) is deep;
    an archive-thin axis that has logged its measured depth ceiling is exempt -- depth is never
    faked to clear this flag."""
    # deep_days is evidence-adjustable within hard bounds (self-tuning, not a free knob)
    from libs.self_improvement.adaptive_thresholds import ThresholdBook
    deep_days = ThresholdBook(ROOT / "data/adaptive_thresholds.json").get("depth_deep_days")
    clocks: list[Path] = []
    for pat in ("data/*_premium.jsonl", "data/*_supply.jsonl", "data/*_activity.jsonl"):
        clocks += list(ROOT.glob(pat))
    if len(clocks) < 3:
        return  # too few series to judge depth-vs-breadth
    deep_names: set[str] = set()
    oos = ROOT / "reports/reconstructed_oos"
    if oos.exists():
        for r in oos.glob("*.json"):
            deep_names.add(r.stem.lower())
    # archive-relative exemption: an axis whose archive genuinely maxes out below deep_days logs its
    # measured ceiling here (axis -> max available days); at/above it, the axis is as deep as its
    # archive allows and is NOT flagged (§32: 'as deep as the archive legitimately allows').
    ceilings = _j(ROOT / "data/depth_ceilings.json", {})
    shallow: list[tuple[str, int]] = []
    for c in clocks:
        stem = c.stem.lower()
        if any(stem in d or d in stem for d in deep_names):
            continue  # already backfilled to archive depth
        try:
            with c.open("r", encoding="utf-8") as fh:
                n = sum(1 for _ in fh)
        except Exception:
            continue
        ceiling = ceilings.get(c.stem) if isinstance(ceilings, dict) else None
        if isinstance(ceiling, (int, float)) and n >= int(ceiling):
            continue  # as deep as its own archive allows -- exempt, never faked
        if n < deep_days:
            shallow.append((c.stem, n))
    if shallow:
        shown = ", ".join(f"{s}({n}d)" for s, n in sorted(shallow, key=lambda x: x[1])[:8])
        defects.append((
            "depth-parity",
            f"{len(shallow)} axis(es) shallow (<{int(deep_days)}d) while breadth widens: {shown} "
            "-- DEPTH LAGGING BREADTH (§32). A shallow axis waits weeks on the forward clock and "
            "cannot validate; breadth without depth is unconverted potential. Backfill each to its "
            "archive-depth ceiling and diff-verify (MAX_SURVIVORS Part 1 #1) -- never fake depth; "
            "an archive-thin axis logs its measured ceiling and is exempt."))


def check_ci_scope(defects) -> None:
    """MAP-vs-TERRITORY (audit 3.1): the CI gate must run the whole test tree, not a hardcoded
    subset. GAP #31's stated blocker (duplicate basenames) expired -- pyproject sets
    import-mode=importlib and the tree collects cleanly. A gate that runs a handful of named
    files certifies almost nothing: the ruin path (tests/risk) and the anti-false-positive path
    (tests/validation) are the largest ungated directories, and freshly-shipped tests land in
    ungated dirs by default. Parses the pytest ARGUMENT TOKENS (a comment mentioning the tree
    must not satisfy the check)."""
    ci = ROOT / "scripts/run_ci.py"
    tests_dir = ROOT / "tests"
    if not (ci.exists() and tests_dir.exists()):
        return
    body = ci.read_text("utf-8")
    named = re.findall(r'"(tests/[A-Za-z0-9_./-]*)"', body)
    if not named:
        return
    whole_tree = any(t.rstrip("/") == "tests" for t in named)
    if whole_tree:
        return
    total = sum(1 for _ in tests_dir.rglob("test_*.py"))
    gated_files = sum(1 for t in named if t.endswith(".py"))
    gated_dirs = [t for t in named if not t.endswith(".py")]
    defects.append((
        "ci-scope-partial",
        f"run_ci.py gates a HARDCODED subset -- {gated_files} named test files + "
        f"{len(gated_dirs)} dir(s) {gated_dirs} -- out of ~{total} test files in the tree. The "
        "ruin path (tests/risk) and anti-false-positive path (tests/validation) are ungated, and "
        "new tests land ungated by default. Replace the named paths with the tests/ tree: the "
        "importlib collection blocker (GAP #31) has expired. Freeze-legal, highest-ROI."))


def check_review_risks_tracked(defects) -> None:
    """MAP-vs-TERRITORY (audit 4.1): every risk NAMED in a review doc must inherit the
    GAP_REGISTER escalation loop (weekly re-rank, 7-day staleness). Nothing reconciles the two,
    so the desk's two largest structural risks (counterparty concentration, key-person) sit in a
    doc that is read but never re-ranked."""
    sr = ROOT / "docs/SYSTEM_REVIEW.md"
    gr = ROOT / "docs/GAP_REGISTER.md"
    if not (sr.exists() and gr.exists()):
        return
    reg = gr.read_text("utf-8").lower()
    # the named structural risks the audit flagged as untracked
    for key, label in (("counterparty", "counterparty/single-venue concentration"),
                       ("key-person", "principal key-person risk"),
                       ("per-venue", "per-venue exposure cap")):
        named_in_review = key in sr.read_text("utf-8").lower()
        tracked = key.replace("-", " ") in reg or key in reg
        if named_in_review and not tracked:
            defects.append(("review-risk-untracked",
                            f"'{label}' named in SYSTEM_REVIEW, NO GAP_REGISTER row -- "
                            "it never enters the weekly re-rank/staleness/escalation loop. Add a "
                            "tracked row so a named risk cannot silently escape the discipline."))


#: The desk's working book. Capacity-bound edges are the ONE structural advantage a book this
#: size has, so the reference is explicit rather than implied.
DESK_BOOK_USD = 50_000.0


#: Neither band may fall below this share of the screened funnel. SYMMETRIC on purpose: a funnel
#: that is 100% niche is as defective as one that is 100% fund-shaped, because both mean a whole
#: class of alpha is going unhunted and the objective is the MAXIMUM NUMBER of them.
_BAND_MIN_SHARE = 0.25


def check_capacity_hunt(defects) -> None:
    """§42: BOTH capacity bands must be hunted -- the funnel may not collapse onto either one.

    PROSPECTOR_SPEC names capacity-bound edges -- the ones a fund abandoned for being too small --
    as "this desk's ONE structural advantage". Until 2026-07-26 the survival gate contradicted
    that outright with a flat $100k capacity floor, so the niche was unreachable by construction.
    Removing the block is necessary and NOT sufficient: a desk merely permitted to hunt small will
    still default to fund-shaped ideas, because that is what the literature is written about.

    SYMMETRIC, BY PRINCIPAL DIRECTION (2026-07-26). The first version of this check enforced a
    NICHE FLOOR, which is the same bias pointed the other way: it would have sat silent while the
    desk hunted nothing but tiny edges, and a funnel with no large edges in it has no successor
    inventory for the day the book outgrows the small ones. The objective is the maximum number of
    simultaneous uncorrelated alphas, so BOTH bands are measured and EITHER one collapsing is the
    defect. Small edges expire first -- that is arithmetic, and it is handled by
    `check_capacity_runway`, not by preferring them here.
    """
    caps: list[float] = []
    names: list[str] = []
    with contextlib.suppress(Exception):
        from libs.autodiscovery.memory import CandidateStore
        store = CandidateStore(ROOT / "data/research_memory.db")
        for c in store.all():
            cap = float(getattr(c.metrics, "capacity_usd", 0.0) or 0.0)
            if cap > 0:
                caps.append(cap)
                names.append(str(getattr(getattr(c, "hypothesis", None), "subtype", "") or ""))
    if len(caps) < 5:
        return  # too few scored candidates to judge where the hunt is pointed
    from libs.research.capacity_policy import DEFAULT_SLEEVES, capacity_band, declared_allocation
    # Whole-book figure -> must be divided by the sleeve count: no single edge is filled with the
    # entire desk. Judging candidates against all $50k would inflate the requirement 8x and mark
    # perfectly tradeable small edges "unfillable" -- the flat-floor bug wearing a new hat.
    #
    # A DECLARED sleeve is banded at its declaration, because that is how every scorer judges it.
    # Banding at equal weight here would have the audit call an edge UNFILLABLE while the scorer
    # calls the same edge NICHE -- two answers to one question, and the audit is meant to be the
    # thing that catches that class of disagreement, not a source of it.
    bands = [capacity_band(c, DESK_BOOK_USD, DEFAULT_SLEEVES,
                           allocation_usd=declared_allocation(name))
             for c, name in zip(caps, names, strict=True)]
    in_niche = sum(1 for b in bands if b == "NICHE")
    larger = sum(1 for b in bands if b in ("SCALABLE", "FUND-SCALE"))
    unfillable = sum(1 for b in bands if b == "UNFILLABLE")
    fillable = in_niche + larger
    if unfillable:
        defects.append((
            "capacity-hunt-unfillable",
            f"§42: {unfillable}/{len(caps)} scored candidates cannot absorb the required headroom "
            f"on a ${DESK_BOOK_USD:,.0f} book at all -- the desk would BE the edge. Small is the "
            "advantage; too small to fill is not. These should be screened out before scoring, "
            "not carried as candidates."))
    if fillable < 5:
        return  # too few FILLABLE candidates to judge how the hunt is split between bands
    if in_niche / fillable < _BAND_MIN_SHARE:
        defects.append((
            "capacity-hunt-fund-shaped",
            f"§42: only {in_niche}/{fillable} fillable candidates ({in_niche / fillable:.0%}) sit "
            f"in the NICHE band -- below the {_BAND_MIN_SHARE:.0%} both bands must hold. The "
            "prospector has drifted onto fund-scale ground, where a book this size has NO "
            "advantage and could not fill the trade if it found one. Point it back at the niche "
            "its own spec names: listing-event dislocations, thin-pair cross-venue funding, "
            "low-OI tails -- edges that pay BECAUSE they are too small to interest anyone with "
            "money. These are ADDITIONAL sleeves, not replacements for the large ones."))
    if larger / fillable < _BAND_MIN_SHARE:
        defects.append((
            "capacity-hunt-niche-only",
            f"§42: only {larger}/{fillable} fillable candidates ({larger / fillable:.0%}) can "
            f"absorb size -- below the {_BAND_MIN_SHARE:.0%} both bands must hold. Hunting ONLY "
            "small is the same bias pointed the other way, and it costs twice: alphas that would "
            "have run alongside the small ones are never found, and there is no successor "
            "inventory for the day the book outgrows the ones being run. Every small edge has a "
            "known expiry (`capacity-runway`); the replacement must be in the pipeline BEFORE it "
            "arrives, which means hunting large concurrently, not afterwards."))


#: Knobs on the capacity policy that exist ONLY to be passed by a caller. Each must have at least
#: one PRODUCTION caller -- a test does not count, because a test proves the mechanism works and
#: says nothing about whether anything runs it.
_CAPACITY_KNOBS = ("allocation_usd", "sleeve", "edge_capacity_usd")


def check_capacity_knobs_are_wired(defects) -> None:
    """§42: every capacity knob must have a PRODUCTION caller, not just a passing test.

    This exists because the same mistake was made three times in one day: the crowding floor, the
    sizer governor and `allocation_usd` were each built, unit-tested green, and never passed by any
    real caller. A parameter nothing passes is an orphaned artifact (§36) with camouflage -- the
    tests genuinely prove the mechanism, so the gap is invisible in exactly the way review is worst
    at catching. Reviewing harder does not fix a class of error; a check does.

    The rule is deliberately blunt: for each knob, at least one call site under libs/ or scripts/
    that is NOT the definition and NOT a test must pass it by keyword.
    """
    import re
    prod: list[tuple[str, str]] = []
    for base in ("libs", "scripts"):
        for path in sorted((ROOT / base).rglob("*.py")):
            rel = str(path.relative_to(ROOT))
            if "test" in rel:
                continue
            with contextlib.suppress(OSError):
                prod.append((rel, path.read_text("utf-8", errors="ignore")))
    for knob in _CAPACITY_KNOBS:
        # a CALL passes `knob=`; a DEFINITION writes `knob: type` or `knob=default` in a signature
        callers = [rel for rel, text in prod
                   if re.search(rf"\b{knob}\s*=\s*(?!None\s*[,)])[\w.\[\]()\"']", text)
                   and "capacity_policy.py" not in rel and "/sizing.py" not in rel]
        if not callers:
            defects.append((
                "capacity-knob-orphaned",
                f"§42: `{knob}` is a capacity knob that NO production code passes -- it is wired "
                "to nothing and clamps nothing, while its unit tests pass and make it look "
                "finished. That is the orphaned-artifact failure (§36) in its most deceptive "
                "form. Either thread it from a real caller or delete it; a knob that only tests "
                "use is a false assurance, which is worse than no knob at all."))


def check_capacity_governor_reachable(defects) -> None:
    """§42: the capacity clamp must be THREADED to the gate, not merely defined in the sizer.

    A governor no caller passes is an orphaned artifact (§36) that tests green forever while
    clamping nothing -- and it is the most dangerous kind, because the tests prove the mechanism
    works and say nothing about whether it runs. This checks the join: `OrderIntent` must carry
    `edge_capacity_usd`, and `risk_gate` must hand it to `calculate_position_size`. Structural, so
    it survives the numbers being re-tuned and fails the moment the wire is cut.
    """
    gate = ROOT / "libs/risk/gate.py"
    sizing = ROOT / "libs/risk/sizing.py"
    if not gate.exists() or not sizing.exists():
        return
    g, s = gate.read_text("utf-8", errors="ignore"), sizing.read_text("utf-8", errors="ignore")
    if "edge_capacity_usd" not in s:
        defects.append((
            "capacity-governor-missing",
            "§42: libs/risk/sizing.py has no edge_capacity_usd governor. Nothing stops a sleeve "
            "being sized past what its edge can hold, which does not lose money slowly -- it "
            "DESTROYS the edge, because the desk's own flow becomes the counterparty."))
        return
    if "edge_capacity_usd" not in g:
        defects.append((
            "capacity-governor-orphaned",
            "§42: the sizer HAS a capacity governor and libs/risk/gate.py never passes it, so it "
            "clamps nothing on any real order while its tests stay green. That is exactly the "
            "orphaned-artifact failure §36 exists to catch, in the one place it can cost capital: "
            "thread intent.edge_capacity_usd into calculate_position_size."))


def _funded_by_sleeve() -> dict[str, float]:
    """Live notional per sleeve, from whatever the desk actually publishes. Empty pre-Gate-0."""
    out: dict[str, float] = {}
    with contextlib.suppress(Exception):
        raw = json.loads((ROOT / "web/portfolio.json").read_text("utf-8"))
        for name, row in (raw.get("sleeves") or {}).items():
            with contextlib.suppress(Exception):
                out[str(name)] = float(row["notional_usd"])
    return out


def check_capacity_allocation_honesty(defects) -> None:
    """§42: a DECLARED allocation is a commitment, and this is what makes it one.

    Allowing a candidate to be judged against the equity it will actually be funded with is
    strictly correct and unblocks the small edges the desk exists to trade. It is also the easiest
    bypass in the whole capacity policy: declare $1, pass every gate forever. So the declaration is
    checked from both ends -- it must be possible under its own edge's capacity, and it must match
    what the sleeve is really funded with.

    "No live funding data" is reported as UNVERIFIED, never as a pass. Pre-Gate-0 that is the
    normal state, and the distinction is the entire point: a check that prints the same thing when
    it verified something and when it verified nothing is not a check.
    """
    from libs.research.sleeve_allocations import inconsistent, load, overfunded, unverified
    allocs = load(ROOT / "data/sleeve_allocations.json")
    if not allocs:
        return   # nothing declared -> equal weight applies, and equal weight is STRICTER
    funded = _funded_by_sleeve()
    for a in inconsistent(allocs):
        defects.append((
            "capacity-declaration-impossible",
            f"§42: sleeve '{a.sleeve}' declares ${a.declared_usd:,.0f} against a "
            f"${a.capacity_usd:,.0f} edge, whose ceiling is ${a.ceiling_usd:,.0f}. The declaration "
            "does not qualify under its own numbers -- it is asking the capacity gate for a pass "
            "it cannot have. Fix the declaration or re-measure the capacity."))
    for a, got in overfunded(allocs, funded):
        defects.append((
            "capacity-declaration-breached",
            f"§42: sleeve '{a.sleeve}' declared ${a.declared_usd:,.0f} -- the number its capacity "
            f"gate was PASSED on -- and is funded with ${got:,.0f}. The gate was cleared on a "
            "commitment that is not being kept, so the edge is being traded past the size it was "
            "ever approved for. Cut the sleeve to its declaration or re-run the gate at the real "
            "size."))
    n_unver = len(unverified(allocs, funded))
    if n_unver and n_unver == len(allocs):
        defects.append((
            "capacity-declaration-unverified",
            f"§42: all {n_unver} declared allocation(s) have NO live funding figure to reconcile "
            "against, so every allocation-aware capacity pass on this desk is currently taken on "
            "trust. Expected pre-Gate-0 and not a fault -- but it must not read as verified, "
            "because the declaration is only a commitment while something checks it."))


def check_capacity_runway(defects) -> None:
    """§42(3): the desk must SEE itself outgrowing an edge, not discover it mid-trade.

    The sequence §42 commits to is edge -> size -> next edge, and the decay of a small edge as the
    book grows into it is DEFINITIONAL rather than a risk to be mitigated. That only compounds if
    the expiry is visible in advance. Every edge has a book size at which it stops being fillable;
    this reports how much growth the current shortlist survives, so the replacement pipeline can
    start BEFORE the edge dies rather than after. Two failures are worth a defect:

      - already outgrown: an edge still being scored that today's book can no longer fill;
      - no runway: nothing on the shortlist survives a doubling, so the desk is one good quarter
        from having no deployable inventory and no notice that it is coming.
    """
    from libs.research.capacity_policy import growth_runway, live_book_usd, live_sleeves
    caps: list[float] = []
    with contextlib.suppress(Exception):
        from libs.autodiscovery.memory import CandidateStore
        store = CandidateStore(ROOT / "data/research_memory.db")
        caps = [float(getattr(c.metrics, "capacity_usd", 0.0) or 0.0) for c in store.all()]
    caps = [c for c in caps if c > 0]
    if len(caps) < 5:
        return
    book, sleeves = live_book_usd(), live_sleeves()
    runways = sorted(growth_runway(c, book, sleeves) for c in caps)
    outgrown = [r for r in runways if r < 1.0]
    if outgrown:
        defects.append((
            "capacity-already-outgrown",
            f"§42(3): {len(outgrown)}/{len(caps)} scored candidates can no longer be filled by "
            f"today's ${book:,.0f} book across {sleeves} sleeves. They are inventory the desk has "
            "already grown past -- retire them and bank the mechanism, do not keep ranking them."))
    survives_2x = sum(1 for r in runways if r >= 2.0)
    if survives_2x == 0:
        defects.append((
            "capacity-no-runway",
            f"§42(3): NOTHING on the shortlist survives a doubling of the ${book:,.0f} book "
            f"(best runway {runways[-1]:.1f}x). Outgrowing an edge is the plan, but the NEXT edge "
            "has to already be in the pipeline when it happens. Hunt one tier larger NOW, while "
            "the current sleeves still pay -- both bands at once, which is the point."))


#: Every scorer that has ever had to answer "is this capacity enough?". Each one used to carry its
#: own dollar constant; they disagreed, and fixing the survival gate alone on 2026-07-26 left four
#: of them still penalising the niche. They are enumerated so a NEW one cannot quietly appear.
_CAPACITY_CONSUMERS = (
    "libs/risk/sizing.py",
    "libs/discovery/objective.py",
    "libs/research/alpha_economics.py",
    "libs/alpha_factory/capacity_intelligence.py",
    "libs/autodiscovery/validation.py",
)
#: Dollar magnitudes that mean "a fund's book" when they appear next to capacity. Finding one of
#: these in a consumer is the fingerprint of a re-inlined threshold.
_FUND_SHAPED_CONSTANTS = ("1e5", "1e6", "1e7", "100_000", "1_000_000", "100000.0", "1000000.0")


def check_deploy_path(defects) -> None:
    """INBOUND DEPLOY must be alive, and its OWED states must not rest (EXECUTION_QUEUE.md RANK 7).

    A deploy path is only worth having if its silence is detectable. Before deploy/pull_deploy.sh
    existed, git_snapshot pushed VPS->GitHub and nothing came back, so master could be arbitrarily
    far ahead of the code the desk was actually running and nothing said so. Restoring that blind
    spot by letting the puller die quietly would be the same gap wearing a newer name.

    THREE FAILURES, and the last two are the ones a naive freshness check would miss:
      * NEVER RAN / STALE -- the box stopped pulling; master is deploying nothing again.
      * CI-RED -- the puller correctly reverted a red commit, which means the box is deliberately
        parked on older code. Right call, but it is a HOLD, not a steady state: master and the box
        have diverged in what they claim to be running until someone fixes the red.
      * ACTION OWED -- the pull landed but a supervised process could not be restarted (this box
        denies systemctl to the quant user) or the ruin rail was invalidated. New code is on disk
        while the OLD code still owns the book: precisely the 2026-07-26 incident, where a
        committed funding fix sat inert in an orphaned executor for 8h.
    """
    sj = ROOT / "data/pull_deploy_state.json"
    if not sj.exists():
        # Absent is only a defect on the box that actually INSTALLED the puller. Gating on the
        # manifest instead would fire on every dev checkout and sandbox, and a fence that cries on
        # every clone is a fence people learn to ignore -- so the discriminator is a LIVE crontab
        # that references it, the same sandbox-vs-box signal check_scheduler_manifest.py uses.
        try:
            live = subprocess.run(["crontab", "-l"], capture_output=True, text=True,
                                  timeout=10, check=False).stdout
        except (OSError, subprocess.SubprocessError):
            return
        if "pull_deploy.sh" in live:
            defects.append(("deploy-never-ran",
                            "the live crontab installs deploy/pull_deploy.sh but "
                            "data/pull_deploy_state.json is MISSING -- the inbound deploy path has "
                            "never produced evidence, so 'merge is deploy' is a claim, not a "
                            "mechanism. Check the cron log for a startup failure"))
        return
    try:
        st = json.loads(sj.read_text("utf-8"))
    except (OSError, ValueError):
        defects.append(("deploy-state-unreadable",
                        "data/pull_deploy_state.json is unparseable -- the deploy path's only "
                        "evidence artifact is corrupt; treat the running code as unverified"))
        return
    age_h = (NOW - sj.stat().st_mtime) / 3600.0
    status = str(st.get("status", "?"))
    if age_h > 26:
        defects.append(("deploy-stale",
                        f"pull_deploy last ran {age_h:.0f}h ago (>26h, status {status!r}) -- the "
                        "box may be running code arbitrarily far behind master, which is the exact "
                        "blind spot the inbound path was built to close"))
    if status == "ci-red":
        defects.append(("deploy-blocked-ci-red",
                        f"pull_deploy REVERTED {st.get('to', '?')} because the CI gate was red; "
                        f"the box is parked on {st.get('from', '?')}. Correct refusal, but it is a "
                        "HOLD: master and the desk disagree about what is running until the red is "
                        "fixed. Fix the gate, do not bypass the puller"))
    if status == "deployed-action-owed":
        defects.append(("deploy-action-owed",
                        f"pull_deploy landed {st.get('to', '?')} but a supervised process was NOT "
                        f"restarted ({st.get('note', '')}). New code on disk, OLD code owning the "
                        "book -- the 2026-07-26 orphaned-executor class. Run the owed systemctl "
                        "command printed in data/cro_ai_logs/pull_deploy.log"))
    if status in ("refused-dirty", "refused-diverged"):
        defects.append(("deploy-refused",
                        f"pull_deploy is REFUSING to deploy (status {status!r}): the box has "
                        "modified tracked files or local commits. Every merge to master is a no-op "
                        "until an operator reconciles the box"))


def check_capacity_single_source(defects) -> None:
    """§42: ONE capacity policy, imported -- never a constant re-inlined next to a scorer.

    The original defect was not that the number was wrong; it was that the number existed in five
    places. Fixing the survival gate did nothing to the other four, and the exclusion simply moved
    to where nobody was looking. So the invariant is structural, not numeric: every scorer that
    judges capacity must IMPORT `libs.research.capacity_policy`, and none may carry a fund-shaped
    dollar constant on a line that mentions capacity. Checking the shape of the dependency rather
    than the value of the threshold is what makes this survive somebody re-tuning the threshold.
    """
    for rel in _CAPACITY_CONSUMERS:
        path = ROOT / rel
        if not path.exists():
            defects.append(("capacity-consumer-missing",
                            f"§42: {rel} is enumerated as a capacity consumer but does not exist. "
                            "Either it moved (update the list) or the parity guard is now blind "
                            "to wherever its logic went."))
            continue
        text = path.read_text("utf-8", errors="ignore")
        if "capacity_policy" not in text:
            defects.append(("capacity-policy-not-imported",
                            f"§42: {rel} judges capacity but does not import capacity_policy -- "
                            "it is carrying its own definition again. That is exactly how the "
                            "flat $100k floor survived being 'fixed': five copies, one patched."))
        for i, line in enumerate(text.splitlines(), start=1):
            low = line.lstrip()
            if low.startswith("#") or "capacity" not in low.lower():
                continue
            hit = next((c for c in _FUND_SHAPED_CONSTANTS if c in line), None)
            if hit is not None:
                defects.append(("capacity-constant-reinlined",
                                f"§42: {rel}:{i} puts a fund-shaped constant ({hit}) on a capacity "
                                "line. Capacity is a RATIO to deployed equity; a six/seven-figure "
                                "literal here is the excluded-by-default bug growing back."))

#: Every doc where a finding can be WRITTEN. The register is where findings are WORKED; anything
#: written here and absent there is invisible to the daily cycle.
_FINDING_DOCS = (
    "docs/SYSTEM_REVIEW.md",
    "docs/BLIND_SPOT_AUDIT.md",
    "docs/research/micro_audit_inbox.md",
    "docs/research/improvement_inbox.md",
    "docs/research/panel_rulings.md",
    # 2026-07-28: the 101-item triage. Its own header is a disposition mandate -- "don't skip any
    # -- build now, queue, or reject completely" -- which is precisely what §35 drives. Adding
    # these RAISES the open-finding count rather than lowering it; that is the honest direction.
    # Leaving them out kept ~101 items invisible to the only organ that works a backlog, and
    # coverage that rises because findings stopped being counted is the denominator trick §35
    # exists to forbid.
    "docs/research/SUBSYSTEM_TRIAGE.md",
    "docs/research/TRIAGE_ADDENDUM.md",
    "docs/GATE0_QUEUE.md",
)
#: Finding-bearing docs deliberately out of scope, with the reason -- so the scope check can tell
#: "consciously excluded" from "quietly unmonitored".
_FINDING_DOCS_EXCLUDED = {
    "docs/CYCLE_20260729_CLOSURE.md": "dated closure snapshot -- every numbered item was rowed "
                                      "via track_findings/recommendations at write time; the "
                                      "register drives them, the snapshot is the record",
    "docs/WEEKLY_MAX_CYCLE.md": "process runbook -- its numbered steps are procedure, not "
                                "findings owing dispositions",
    "docs/research/TRIAGE_20260729_PRINCIPAL_BATCH.md": "dated triage record -- verdicts were "
                                                        "rowed into the ledger 07-29; "
                                                        "historical artifact",
    "docs/research/cn_oss_extraction_20260731.md": "dig extraction card -- its 5 finds are "
                                                   "rowed as R0100 (ingest+screen) by the "
                                                   "authoring session; §33 governs the cards",
    "docs/research/blind_rediscovery_log.md": "monthly blind-rediscovery run log -- each run's "
                                              "cards are rowed into the RECOMMENDATION ledger by "
                                              "the authoring session (run 1 2026-07-31 -> "
                                              "R0202-R0210), the organ that drives conversion and "
                                              "enforces dispositions. Same precedent as "
                                              "cn_oss_extraction_20260731.md. Scope-excluded here "
                                              "so the SAME cards are not double-counted against "
                                              "two backlogs; §36 still governs the file via "
                                              "_PRODUCER_CADENCE, so a run that stops happening "
                                              "fires. If a future run's cards are ever NOT "
                                              "ledgered, move this into _FINDING_DOCS",
    "docs/research/panel_inbox.md": "raw panel transcript -- rulings are the distilled output",
    "docs/research/feed_inbox.md": "literature feed, not desk findings",
    "docs/research/data_axis_watchlist.md": "source cards -- governed by §33 dispositions",
    "docs/research/discovery_hypotheses.md": "hypotheses -- governed by §33 / the trial ledger",
    "docs/research/literature_coverage.md": "coverage log -- governed by §33",
    "docs/research/prospector_coverage.md": "coverage log -- governed by §33, same as its "
                                            "literature_coverage sibling",
    "docs/research/MEASUREMENT_DOCTRINE.md": "standing doctrine -- its numbered items are "
                                             "principles that bind organs, not findings owing "
                                             "a disposition",
    "docs/POST_GATE0_MANIFEST.md": "deferred builds -- driven by check_post_gate0_activation",
    "docs/research/DAILY_INTEGRITY_WATCH.md": "standing checklist, not findings",
    "docs/research/FREE_DATA_ADDENDA_BCD.md": "source catalogue -- source cards, not findings",
    "docs/research/FREE_DATA_ALTERNATIVES_SPEC.md": "spec document, not findings",
    "docs/research/GAP14_ROOTCAUSE.md": "forensic writeup for a gap row that already exists",
    "docs/research/GAP32_RESIZE_UP_SPEC.md": "spec for GAP #32 -- the row is the tracked item",
    "docs/research/GAP19_RECONCILE_GUARD_SPEC.md": "spec for GAP #19 -- the row is tracked",
    "docs/research/CRISIS_AUTOPSY_SPEC.md": "spec document, not findings",
    "docs/research/MAX_SURVIVORS_PROGRAM.md": "programme design, not findings",
    "docs/research/HYPOTHESIS_MAX_SPEC.md": "spec document, not findings",
    "docs/research/SPECIALIZED_SEATS_SPEC.md": "spec document, not findings",
    "docs/research/BYBIT_SECOND_VENUE_SPEC.md": "spec document, not findings",
    "docs/research/DISCOVERY_TELEMETRY_SPEC.md": "spec document, not findings",
    "docs/research/NLP_NORMALIZATION_SPEC.md": "spec document, not findings",
    "docs/research/PROSPECTOR_SPEC.md": "spec document, not findings",
    "docs/research/LITERATURE_SPEC.md": "spec document, not findings",
    "docs/research/GROWTH_UNLOCK_LADDER.md": "ladder definition, not findings",
    "docs/research/TWO_STAGE_DISCOVERY_LAW.md": "law text, not findings",
    "docs/research/DIGGER_TARGET_ROADMAP.md": "target list -- §33 governs what it yields",
    "docs/research/STRUCTURAL_EDGE_IDEAS.md": "idea list -- §33 / trial ledger governs",
    "docs/research/AXIS_PREREGISTRATIONS.md": "pre-registrations -- the trial ledger governs",
    "docs/DIGGING_CHARTER.md": "the law itself",
    "docs/OPERATOR_COMPACT.md": "operator agreement, not findings",
    "docs/GO_LIVE_CHECKLIST.md": "checklist -- gated by GAP #2",
    "docs/EVIDENCE_GATED_PROGRESSIONS.md": "progression definitions, not findings",
    "docs/KILL_THESIS.md": "kill criteria, not findings",
    "docs/REPO_EXTRACTION.md": "adoption record, not findings",
    "docs/RD_AGENT_AUDIT.md": "historical audit -- superseded by SYSTEM_REVIEW",
    "docs/institutional_knowledge.md": "knowledge base, not an obligation list",
    "docs/desk_digest.md": "generated digest",
    "docs/graveyard.md": "terminal by construction",
    "docs/PROJECT_HANDOFF.md": "handoff doc, not findings",
    "docs/HOME.md": "index",
    "docs/DASHBOARD.md": "generated status",
    "docs/LIVE_CONNECTOR_SPEC.md": "spec for GAP #2 -- the row is the tracked item",
    "docs/research/oss_benchmark.md": "external benchmark log -- adoption_queue governs uptake",
    "docs/research/prospector_watchlist.md": "prospector cards -- governed by §33 dispositions",
    # VERIFIED 2026-07-26 before excluding: the file is WRITTEN by
    # scripts/generate_external_review_doc.py on every panel run, and its numbered block is a
    # verbatim copy of the GAP_REGISTER table ("## Current gap register (self-assessed, ranked)").
    # So every "finding" it carries is, by construction, already a register row -- demanding rows
    # for them would double-count the register against itself, and the next regeneration
    # overwrites anything written here. It is a DERIVED surface, never an original one: genuinely
    # new findings arrive as panel RESPONSES, which flow panel_inbox -> panel_rulings (in scope,
    # above) -> register rows. If the generator ever starts emitting desk-authored findings that
    # do not exist upstream, move it into _FINDING_DOCS.
    # trailing slash = the whole CLASS is claimed (a generator emits dated instances)
    "docs/research/deep_sweep/":
        "weekly deep-cold-audit output -- CADENCED PRODUCER (§36); findings flow to\n"
        "improvement_inbox and GAP_REGISTER rows (§35). Each dated report is one\n"
        "sweep's snapshot, superseded by the next, never converted in place.",
    "docs/EXTERNAL_PANEL_DOSSIER.md":
        "GENERATED dossier -- its numbered block is a copy of the register table; original panel "
        "findings enter via panel_inbox -> panel_rulings, which are in scope",
    # trailing slash = class entry, same design as deep_sweep/ above
    "docs/research/capability_hunt/":
        "daily L1.31 hunt records -- dated per-slot snapshots whose findings are ROWED IN THE\n"
        "SAME RUN by the hunt's own duty (L1.31/L1.39; 2026-07-31 proof: s5 -> R0153-R0173,\n"
        "every one disposed). The ledger drives them; the snapshot is the record. A hunt that\n"
        "fails to row is caught by the conversion fences on the rows' absence, and that failure\n"
        "belongs to the hunt run, not to scope.",
}


#: §36 PRODUCERS: artifacts that accumulate inventory under a cadence STATED IN THEIR OWN PROSE
#: and, until now, enforced by nothing. Each maps to the max age its own text promises. This is
#: the miner failure in its purest form -- a conversion rule written down, with no clock behind it.
_PRODUCER_CADENCE = {
    "docs/research/weak_signal_registry.md": (
        3.0, "§23: >=2 weak signals from INDEPENDENT paths auto-promote to hypothesis generation, "
             "'checked each cycle during inbox triage' -- convention, never verified"),
    "docs/research/canary_searches.md": (
        4.0, "re-run each digging session; an unexpected shift triggers targeted rediscovery "
             "BEFORE the normal cadence -- nothing confirmed the canaries were re-run"),
    "docs/research/generation_due.md": (
        8.0, "the cadence engine flags scoped generate runs and the brain executes then marks "
             "them -- nothing checked a flagged run was ever executed"),
    "docs/research/adoption_queue.md": (
        35.0, "trigger-gated methods (fracdiff, dollar bars, ...) -- nothing notices when a "
              "precondition ARRIVES, so a due adoption waits forever"),
    # (A duplicate blind_rediscovery_log.md entry lived here from 2026-07-31 until a concurrent
    # session classified the SAME file below at 31.0d. Removed rather than merged: Python keeps
    # the LAST duplicate key silently, so two entries meant one of the two stated reasons was
    # decorative and nobody could tell which. The surviving entry is the better-founded one --
    # it READS the cadence from the document's own header, which is what §36 asks for, instead of
    # inventing one here. The dropped entry's only distinct argument was a 35d-vs-31d margin so an
    # on-time monthly run cannot fire the check on its own due date; if that ever fires
    # spuriously, widen the surviving entry rather than re-adding a second key.)
    # The register is a producer too -- the one every other law routes into. Its own header
    # promises a re-rank every daily cycle; check_gap_register_health reads the self-declared
    # stamp, and this is the file-level backstop if the stamp itself stops being written.
    "docs/GAP_REGISTER.md": (
        3.0, "re-ranked at the START of every daily AI cycle by its own rule -- the organ §35 and "
             "§36 both depend on, and it was checked by nothing"),
    # THE TIER-1 BENCHMARK is a PRODUCER: sub-T1 rows are queued into the max-push hunt every
    # refresh, and the deep sweep re-grades it weekly from auditor evidence. A stale benchmark
    # silently stops queueing gaps -- the exact inventory-accumulates failure §36 catches.
    "docs/research/TIER1_BENCHMARK.md": (
        8.0, "L1.36/L1.31: re-graded weekly by the deep-sweep synthesis from auditor evidence, "
             "and parsed by run_max_push every refresh so every sub-T1 row enters the daily "
             "hunt -- if it goes stale, gaps stop being queued and nothing would say so"),
    # ALPHA HUNT records are producers under L1.39: each listed candidate owes a Stage-A screen,
    # so an un-updated hunt record means candidates are sitting un-screened -- idle findings.
    "docs/research/alpha_hunt_20260731.md": (
        14.0, "L1.39/L1.31: every candidate listed here owes a Stage-A screen (R0115 and R0120 "
              "were screened same-day); a stale record means candidates are accumulating "
              "un-screened, which is precisely the idle-findings defect"),
    "docs/EXECUTION_QUEUE.md": (
        7.0, "the ranked, unbuilt remainder (opened 2026-07-30) -- 'worked in RANK ORDER by the "
             "next cycle, the weekly GAP-MAX sweep, or any fresh session'; its own header claims "
             "a cadence and nothing checked it was ever re-worked, which is exactly the failure "
             "this law exists to catch"),
    # THE DISCRETIONARY DESK is a PRODUCER: it states the sleeve's measured constants (noise
    # floors, costs, the cost-adjusted breakeven hit rate) and every one is a MEASUREMENT that
    # drifts. A stale page means the desk is reasoning from last month's volatility regime and
    # last month's fee tier while believing they are current -- and the numbers in it are what the
    # principal reads before a capital decision, which is the most expensive place for a quietly
    # outdated figure to sit.
    # CLASSIFIED 2026-07-31 on arrival from the VPS lineage -- the §36(2) fence fired the moment
    # it landed, which is the law working. The file states its own governance in its header
    # ("Governed by §36 ... max age = one month + the early-fire rule"), so the cadence is READ
    # from its prose rather than invented here, exactly as §36 intends.
    "docs/research/blind_rediscovery_log.md": (
        31.0, "L1.9/§36: the blind-rediscovery seat runs once per cycle and logs every invention "
              "for a 12-month literature comparison -- the desk's only direct measurement of "
              "whether it is genuinely creative or an excellent summariser. Its cadence is stated "
              "in its own header (one month); going stale means the seat stopped running and the "
              "12-month comparison silently loses its baseline."),
    "docs/DISCRETIONARY_DESK.md": (
        14.0, "L1.6/L1.41: re-stated from the resolver's measured output (noise floors, realised "
              "costs, conditional hit rates, cost-adjusted breakeven) -- if it goes "
              "stale the section claims measurements that are no longer true"),
}
#: Artifacts that are terminal by nature: templates, forensic write-ups, protocol libraries. They
#: accumulate no inventory, so they owe no cadence -- recorded here so "no law" is a DECISION.
_TERMINAL_ARTIFACTS = {
    "docs/research/gate_power_audit.md":
        "dated measurement record (Type I / Type II of every gauntlet gate, 2026-08-01). It "
        "accumulates no inventory because its conclusions were CONVERTED the same day: the "
        "duplicated multiplicity correction became a code change in libs/autodiscovery/"
        "validation.py, its evidence was rowed as R0224, and its claims are pinned by "
        "tests/validation/test_dsr_single_correction.py. The numbers themselves are regenerable "
        "from scripts/audit_gate_power.py into reports/gate_power_audit.json, which is where a "
        "cadence would belong if one is ever wanted -- the doc is the write-up, not a queue. The "
        "two findings it does NOT convert (min-length truncation, top-K screen) are carried as "
        "ledger rows, not as unread inventory here.",
    "docs/research/cn_oss_extraction_20260731.md":
        "dated verification record (10 CN OSS projects: 8 real, 1 hallucinated, 1 proprietary). "
        "It accumulates no inventory: its 5 extracted axes were rowed as R0100 and appended to "
        "data_axis_watchlist.md, and its verdicts were folded into ops/frontier_cn_prompt.txt so "
        "the CN seat never re-spends the verification. The doc is the evidence, not a queue.",
    "docs/research/BITMEX_DECADE_INGEST_SPEC.md":
        "build spec (directive bitmex-ingest-spec, closed 2026-07-31) -- executed via its phase "
        "artifacts: phase 1 landed same-day (data/bitmex_funding.jsonl, 11,148 rows 2016->now); "
        "phase 2 is the tranche cron line the spec defines. Conversion is tracked on those "
        "artifacts, not on this doc.",
    "docs/research/FRONTIER_MINER_TEMPLATE.md": "template spec -- instantiated, not converted",
    "docs/research/GAP34_FORENSIC.md": "forensic write-up for a closed gap",
    "docs/research/self_interrogation_patterns.md": "protocol library -- applied, not converted",
    "docs/playbooks/carry.md": "runbook -- followed, not converted",
    "docs/playbooks/go_live.md": "runbook -- followed; the gate is GAP #2",
    "docs/playbooks/ops_checklist.md": "runbook -- followed, not converted",
    # STANDING DOCTRINE (2026-07-28). These bind organs; they are not inventory awaiting
    # conversion, and "convert the doctrine" is not a coherent action. Terminal is the DECISION
    # the law demands, not a default -- each governs behaviour and is superseded by amendment,
    # never worked off a queue.
    "docs/research/EXPLORATION_DOCTRINE.md": "standing doctrine -- binds organs, not an inventory",
    "docs/research/MEASUREMENT_DOCTRINE.md": "standing doctrine -- binds organs, not an inventory",
    "docs/research/OPERATING_DOCTRINE.md": "standing doctrine -- governs what to build",
    "docs/research/RESEARCH_EXCELLENCE.md": "standing doctrine -- governs how research is run",
    "docs/DESK_BRIEF.md":
        "derived snapshot -- machine-generated from measured state by research_exchange.py and "
        "overwritten on each run, so converting it is meaningless. Terminal by construction, the "
        "same reasoning already applied to EXTERNAL_PANEL_DOSSIER.md.",
    "docs/research/MECHANISM_GRAPH.md":
        "reference structure CONSUMED by hypothesis_generator.py + llm_blind_researcher.py to "
        "choose what gets asked -- applied, not converted (cf. self_interrogation_patterns.md). "
        "It declares no cadence, and inventing one would build a gate that fires forever.",
    "docs/EXTERNAL_PANEL_DOSSIER.md":
        "derived snapshot -- REGENERATED from live state on every panel run by "
        "generate_external_review_doc.py, never an inventory. Its findings flow panel responses "
        "-> panel_inbox -> panel_rulings -> GAP_REGISTER rows (§35), so converting the dossier "
        "itself is meaningless: the next run overwrites it. Terminal by construction.",
    # CLASSIFIED 2026-07-29 (closure cycle). This check FIRED on the four documents that cycle
    # created, which is the law working: each is classified below as a DECISION, never a default.
    "docs/CYCLE_20260729_CLOSURE.md":
        "CYCLE REPORT -- a dated record of one cycle's measured results with every proving command, "
        "same class as a forensic write-up (GAP34_FORENSIC.md). Its open items are carried by "
        "GAP_REGISTER rows and the ratchet fence, not by converting the report.",
    "docs/WEEKLY_MAX_CYCLE.md":
        "standing contract for the weekly gap-max sweep (constitution L4) -- it BINDS the sweep's "
        "conduct and effort floor and is superseded by amendment, never worked off a queue. Same "
        "class as the standing doctrines above.",
    "docs/research/MUTATION_BASELINE.md":
        "MEASUREMENT RECORD with a live artifact behind it (data/mutation_score.json) and a "
        "ratchet fence that keeps it honest (check_ratchets: test_strength_min_kill_rate, floor "
        "only rises). Its 'owed next' targets are tracked by that fence and by GAP #53's row, not "
        "by converting the write-up -- the write-up is the evidence, the fence is the queue.",
    "docs/research/COT_SCREEN_RESULT.md":
        "SCREEN RESULT, terminal by construction: a Stage-A screen has zero promotion authority, "
        "so there is nothing to convert. Its two dispositions are already routed -- the "
        "positioning-axis REJECT is recorded against register #77 (and cancels the queued crypto "
        "positioning acquisition), and the un-measurable decay leaves the borrowed -58% prior "
        "labelled borrowed under register #71. Re-entry needs a named enabling change (L1.16a).",
    "docs/research/TRIAGE_20260729_PRINCIPAL_BATCH.md":
        "TRIAGE LEDGER in the same class as SUBSYSTEM_TRIAGE.md / TRIAGE_ADDENDUM.md: every row "
        "already carries its disposition (BUILT / UPGRADED / BUILD / QUEUE / REJECT with reason), "
        "so the document IS the conversion record rather than inventory awaiting one. Rows that "
        "became work carry register rows; rows that were rejected carry their reason.",
}


def check_gap_register_health(defects) -> None:
    """§36(3): the register is held to the rules it states about ITSELF.

    §35 and §36 route every finding INTO the register, which makes it the load-bearing organ for
    both -- and it was checked by nothing. Its own header declares 're-ranked at the START of every
    daily AI cycle', 'items stale >7 days MUST be escalated (implement / defer with deadline /
    retire with reason)' and 'never empty without written justification'. All three were rules
    written INSIDE the document they govern: exactly the shape §36 names as a rule with no clock.
    Routing findings into a bucket nobody empties is not an improvement, it is a tidier backlog.

    The re-rank age comes from the SELF-DECLARED stamp, never from mtime or commit time -- editing
    the file must not be able to fake a re-rank that never happened.
    """
    from libs.research.finding_registry import register_health

    gr = ROOT / "docs/GAP_REGISTER.md"
    if not gr.exists():
        return
    h = register_health(gr.read_text("utf-8"), today=datetime.now(UTC).date())
    if h.n_rows == 0:
        defects.append(("gap-register-unparseable", f"§36(3): {h.verdict}"))
        return
    if h.stale_rows:
        shown = ", ".join(h.stale_rows[:5])
        more = f" (+{len(h.stale_rows) - 5} more)" if len(h.stale_rows) > 5 else ""
        defects.append((
            "gap-register-rows-stale",
            f"§36(3): {len(h.stale_rows)} OPEN row(s) past the register's own 7-day escalation "
            f"bar, oldest {h.oldest_open_days:.0f}d: {shown}{more}. Each owes one of the three "
            "exits the register names -- implement, defer WITH a deadline, or retire with a "
            "reason. Re-ranking the header is not one of them: the rule is about ITEMS, and "
            "measuring the re-rank stamp instead let a daily stamp make every row immortal."))
    if h.rerank_breach:
        defects.append((
            "gap-register-rerank-breach",
            f"§36(3): {h.verdict} Re-rank now and escalate anything genuinely stuck -- this is the "
            "organ every other law depends on; when it stops moving, everything routed into it "
            "stops with it, silently."))
    elif h.rerank_stale:
        defects.append((
            "gap-register-rerank-stale",
            f"§36(3): {h.verdict} Caught as DRIFT, before the 7-day escalation bar it sets for "
            "itself."))
    if h.undated_open:
        defects.append((
            "gap-register-parked-rows",
            f"§36(3): {len(h.undated_open)} open row(s) carry NO date in their plan -- "
            f"{', '.join(h.undated_open)}. The register's own three exits are implement / defer "
            "WITH A DEADLINE / retire with reason; a row with no date took none of them and is "
            "parked, which is the state the rule exists to forbid."))
    if h.ownerless:
        defects.append((
            "gap-register-ownerless",
            f"§36(3): open row(s) with no owner -- {', '.join(h.ownerless)}. Unowned work is "
            "nobody's, and the escalation has no addressee."))


def check_producer_cadence(defects) -> None:
    """§36: an artifact that accumulates inventory declares a cadence and is HELD to it.

    The miner failure, in its purest form: four artifacts state a conversion rule in their own
    prose -- 'auto-promote on convergence', 're-run each digging session', 'the brain executes and
    marks them', 'monthly trigger re-check' -- and NOTHING checked any of it. A rule written in a
    document it governs is a rule with no clock; it is obeyed exactly as long as somebody
    remembers, which is the failure §33 and §35 each closed for their own surface.

    Age is measured from the last COMMIT, not mtime: a fresh clone stamps every file at checkout,
    and this check must mean the same thing on the VPS and in a sandbox.
    """
    import subprocess

    stale = []
    for rel, (max_days, why) in _PRODUCER_CADENCE.items():
        p = ROOT / rel
        if not p.exists():
            continue
        try:
            out = subprocess.run(["git", "log", "-1", "--format=%ct", "--", rel],
                                 cwd=ROOT, capture_output=True, text=True, timeout=15)
        except (OSError, subprocess.SubprocessError):
            return  # no git -- the check does not apply here
        if out.returncode != 0 or not out.stdout.strip():
            continue
        with contextlib.suppress(ValueError):
            age_d = (NOW - float(out.stdout.strip())) / 86400.0
            if age_d > max_days:
                stale.append(f"{Path(rel).name} {age_d:.0f}d (bar {max_days:.0f}d) -- {why}")
    for s in stale:
        defects.append((
            "producer-cadence-stale",
            f"§36: {s}. The artifact's own text promises this cadence; nothing enforced it until "
            "now. Work it and commit, or amend the stated cadence to one the desk actually keeps "
            "-- a promise nobody checks is how inventory rots in plain sight."))


def check_artifact_governance(defects) -> None:
    """§36(2): EVERY artifact is claimed by a law -- so the miner problem cannot reappear anywhere.

    §33 governs mined cards, §35 governs findings, §36 governs cadenced producers. Each closed the
    same failure on its own surface, one surface at a time -- which is a losing game, because the
    NEXT artifact arrives ungoverned by default and nobody notices until it has rotted. This
    inverts it: every docs/ markdown must be claimed by some law, or explicitly recorded as
    terminal WITH A REASON. An unclaimed artifact is the miner problem waiting to happen, and it
    now fires on the day it appears rather than months later.
    """
    claimed = (set(_DIG_DOCS) | set(_DIG_DOCS_EXCLUDED) | set(_FINDING_DOCS)
               | set(_FINDING_DOCS_EXCLUDED) | set(_PRODUCER_CADENCE) | set(_TERMINAL_ARTIFACTS))
    # A trailing-slash claim governs a whole DIRECTORY CLASS. Generators (the weekly deep sweep)
    # emit dated instances forever, so exact-path claims could never keep up and the check would
    # fire permanently on correctly-governed output. Claim the class once; instances inherit it.
    claimed_prefixes = tuple(c for c in claimed if c.endswith("/"))
    audit_src = ""
    with contextlib.suppress(OSError):
        audit_src = Path(__file__).read_text("utf-8")
    cands = [p.relative_to(ROOT).as_posix() for p in sorted((ROOT / "docs").rglob("*.md"))]
    # GITIGNORED PATHS ARE NOT ARTIFACTS (2026-07-28). This walked docs/ raw, so locally-generated
    # scratch that git is explicitly told to ignore (docs/audit_shards/shard_*.md) was demanded to
    # carry a governance claim. Those files do not exist on a clean checkout, which made this check
    # -- and the CI test that asserts on it -- ENVIRONMENT-DEPENDENT: red on the box that generated
    # the scratch, green on a runner that never did. A gate whose verdict depends on which machine
    # ran it cannot be trusted in either direction. Governance applies to what is COMMITTED.
    with contextlib.suppress(OSError, subprocess.SubprocessError):
        ig = subprocess.run(["git", "check-ignore", "--stdin"], cwd=ROOT, input="\n".join(cands),
                            capture_output=True, text=True, timeout=20)
        if ig.returncode in (0, 1):        # 0 = some ignored, 1 = none ignored; 128 = no git
            skip = {ln.strip() for ln in ig.stdout.splitlines() if ln.strip()}
            cands = [c for c in cands if c not in skip]
    unclaimed = []
    for rel in cands:
        if (rel in claimed or rel.startswith(claimed_prefixes)
                or rel.endswith("GAP_REGISTER.md")):
            continue
        if Path(rel).name in audit_src:      # named by some other check -- already governed
            continue
        unclaimed.append(Path(rel).name)
    if unclaimed:
        defects.append((
            "artifact-ungoverned",
            f"§36(2): {len(unclaimed)} docs artifact(s) claimed by NO law -- "
            f"{', '.join(unclaimed[:8])}. Every artifact is governed by §33 (mined cards), §35 "
            "(findings), §36 (cadenced producers), or recorded terminal with a reason. Ungoverned "
            "is how the miner problem reappears: inventory accumulates and nothing ever converts "
            "it. Classify each -- 'no law' must be a DECISION, never a default."))


def check_findings_tracked(defects) -> None:
    """EVERY FINDING MUST REACH THE LOOP THAT DRIVES IT (§35).

    The register is the desk's only organ that DRIVES work: weekly re-rank, 7-day staleness,
    escalation. Every other doc is a place findings are WRITTEN. The daily cycle acts on the
    register, so a finding absent from it is not merely slow -- it is invisible, and however
    carefully it was found it will never be worked.

    Generalises check_review_risks_tracked, which enforced this for THREE HARDCODED KEYS and so
    could only ever catch risks somebody remembered to hardcode -- the same brittleness one level
    up. Matching is deliberately generous (one distinctive token is enough): a false accept is
    cheap, a false alarm trains the reader to ignore the check, and an ignored check is worse than
    no check because it looks like coverage.
    """
    from libs.research.finding_registry import coverage_report, parse_findings

    gr = ROOT / "docs/GAP_REGISTER.md"
    if not gr.exists():
        return
    register = gr.read_text("utf-8")
    findings = []
    for rel in _FINDING_DOCS:
        p = ROOT / rel
        if p.exists():
            with contextlib.suppress(OSError):
                findings += parse_findings(p.read_text("utf-8"), source=rel)
    if not findings:
        return
    rep = coverage_report(findings, register)
    if rep.n_untracked:
        defects.append((
            "findings-untracked",
            f"§35: {rep.n_untracked}/{rep.n_open} open finding(s) have NO GAP_REGISTER trace "
            f"({rep.coverage:.0%} coverage) -- {'; '.join(rep.untracked_names)}. The daily cycle "
            "works the register; a finding that never lands there is invisible to it forever. "
            "Add a row (mechanism, trigger, owner) or record it as closed -- being written down "
            "somewhere is not the same as being driven."))


#: TRACKED (docs/, not gitignored data/) -- a coverage floor stored where `rm` resets it is not a
#: floor. In git, a reset shows in `git status`, in the diff, and in check_dig_uncommitted.
FINDINGS_RECORD = ROOT / "docs/research/findings_coverage_record.json"


def check_findings_ratchet(defects) -> None:
    """§35(7): coverage holds at 100% and the FLOOR ONLY RISES -- over a scope that cannot shrink.

    A one-off 100% is a snapshot. The law needs a floor, and the floor needs an honest denominator:
    the cheapest way to reach 100% is not to row the findings but to SHRINK THE DENOMINATOR --
    exclude a doc from scope, or delete the finding. Same loophole §34 closed for mining (fake a
    conversion rate by mining less), closed the same way: coverage, open-finding count and
    docs-scanned all ratchet UP together, and a worse cycle produces a defect rather than a
    relaxed bar.
    """
    from libs.research.finding_registry import (
        CoverageRatchet,
        coverage_report,
        parse_findings,
        update_coverage_ratchet,
    )

    gr = ROOT / "docs/GAP_REGISTER.md"
    if not gr.exists():
        return
    findings, n_docs = [], 0
    for rel in _FINDING_DOCS:
        p = ROOT / rel
        if p.exists():
            n_docs += 1
            with contextlib.suppress(OSError):
                findings += parse_findings(p.read_text("utf-8"), source=rel)
    if not findings:
        return
    rep = coverage_report(findings, gr.read_text("utf-8"))

    prior = CoverageRatchet()
    with contextlib.suppress(Exception):
        prior = CoverageRatchet.model_validate_json(FINDINGS_RECORD.read_text("utf-8"))
    new, verdict = update_coverage_ratchet(
        prior, rep, n_docs=n_docs, at=datetime.now(UTC).isoformat())
    with contextlib.suppress(OSError):
        FINDINGS_RECORD.parent.mkdir(parents=True, exist_ok=True)
        FINDINGS_RECORD.write_text(new.model_dump_json(indent=2), "utf-8")

    if verdict.scope_shrank:
        defects.append(("findings-scope-shrank", f"§35(7): {verdict.verdict}"))
    if verdict.coverage_regressed:
        defects.append(("findings-coverage-regressed", f"§35(7): {verdict.verdict}"))
    if rep.coverage < 1.0 and not verdict.coverage_regressed:
        defects.append((
            "findings-coverage-below-100",
            f"§35(7): {verdict.verdict} The standing target is 100% -- every finding the desk has "
            "made reaches the loop that drives it, or is recorded closed. Anything less means the "
            "cycle is provably blind to work it already knows about."))


def check_findings_scope(defects) -> None:
    """The finding-scan's own scope is audited -- a new findings doc must not appear unmonitored.

    Same shape as check_mine_scope: a fixed doc list is the check's blast radius, and a finding
    written outside it evades §35 with no code change and no diff. Every docs/ markdown carrying
    numbered findings must be in scope or excluded WITH A REASON; never decided by omission.
    """
    from libs.research.finding_registry import parse_findings

    # TRAILING-SLASH CLASS CLAIMS (2026-07-26). check_artifact_ungoverned already honours these,
    # with a comment stating exactly why: generators emit dated instances forever, so exact-path
    # claims "could never keep up and the check would fire permanently on correctly-governed
    # output". This sibling check never got the same treatment, so `docs/research/deep_sweep/` --
    # excluded WITH a stated reason since it was written -- was never actually excluded here, and
    # every weekly sweep report re-fired findings-scope-unmonitored. The defect was therefore
    # UNCLOSABLE by construction: the only way to satisfy it was to list files that do not exist
    # yet. A convention honoured by one check and ignored by its sibling in the same file is the
    # generalise-the-rule blind spot; the two now read the claims the same way.
    _excluded_prefixes = tuple(c for c in _FINDING_DOCS_EXCLUDED if c.endswith("/"))
    rogue = []
    for p in sorted((ROOT / "docs").rglob("*.md")):
        rel = p.relative_to(ROOT).as_posix()
        if (rel in _FINDING_DOCS or rel in _FINDING_DOCS_EXCLUDED
                or rel.startswith(_excluded_prefixes) or rel.endswith("GAP_REGISTER.md")):
            continue
        with contextlib.suppress(OSError):
            n = len(parse_findings(p.read_text("utf-8"), source=rel))
            if n >= 5:  # a handful of numbered lines is prose; a pile of them is a findings doc
                rogue.append(f"{p.name}({n})")
    if rogue:
        defects.append((
            "findings-scope-unmonitored",
            "§35 scope: doc(s) carrying numbered findings outside the scan -- "
            f"{', '.join(rogue[:6])}. Findings written there owe no register row and are "
            "invisible to §35 -- a bypass needing no code change and leaving no diff. Add to "
            "_FINDING_DOCS or _FINDING_DOCS_EXCLUDED with a stated reason."))


#: Day-over-day collapse thresholds for the live book. Deliberately loose: this catches a book
#: LOSING ITSELF, not ordinary rebalancing. A tight bar here would fire on every rotation and be
#: acknowledged into silence, which is worse than no check.
_BOOK_EQUITY_DROP = 0.10       # 10% marked equity in one day
_BOOK_CARRY_DROP = 0.50        # half the positions gone in one day


def check_book_collapse(defects) -> None:
    """The book losing most of itself overnight must be LOUD. Nothing watched this.

    On 2026-07-26 concurrent carries went 10 -> 2 and deployed notional fell 30% in a single day,
    and no organ said a word: the desk had checks for idle code, mining regression and stale
    findings, and none for its own positions vanishing. Either the executor unwound eight carries
    or a state file was truncated -- both are things you want to hear about the same morning, and
    the second one silently corrupts every downstream number that reads the book.

    Reads the attestation chain only, so it works from the record rather than from live venue
    access, and stays quiet on a single row (no prior day = nothing to compare).
    """
    rows = []
    with contextlib.suppress(Exception):
        for line in (ROOT / "data/nav_attestation.jsonl").read_text("utf-8").splitlines():
            if line.strip():
                rows.append(json.loads(line))
    if len(rows) < 2:
        return
    prev, cur = rows[-2], rows[-1]

    def _f(row, key):
        try:
            return float(row.get(key) or 0.0)
        except (TypeError, ValueError):
            return 0.0

    p_eq, c_eq = _f(prev, "equity_marked"), _f(cur, "equity_marked")
    if p_eq > 0 and (p_eq - c_eq) / p_eq > _BOOK_EQUITY_DROP:
        defects.append((
            "book-equity-collapse",
            f"marked equity fell {(p_eq - c_eq) / p_eq:.0%} in one day "
            f"(${p_eq:,.0f} -> ${c_eq:,.0f}) on {cur.get('date')}. Past the "
            f"{_BOOK_EQUITY_DROP:.0%} bar -- establish whether this is P&L or a bad read BEFORE "
            "any number derived from the book is trusted again."))

    p_n, c_n = int(_f(prev, "n_carries")), int(_f(cur, "n_carries"))
    if p_n >= 4 and c_n < p_n * (1.0 - _BOOK_CARRY_DROP):
        defects.append((
            "book-carries-collapse",
            f"concurrent carries fell {p_n} -> {c_n} on {cur.get('date')} (deployed "
            f"${_f(prev, 'deployed_notional'):,.0f} -> ${_f(cur, 'deployed_notional'):,.0f}). "
            "Either the executor unwound most of the book or the position state was truncated. "
            "The second is silent and corrupts every downstream figure -- confirm which."))

    p_r, c_r = _f(prev, "realized_spot_pnl"), _f(cur, "realized_spot_pnl")
    if p_r > 0 and c_r < p_r:
        defects.append((
            "book-realized-pnl-fell",
            f"REALIZED spot P&L fell ${p_r:,.2f} -> ${c_r:,.2f} on {cur.get('date')}. Realized "
            "P&L is banked and should only ratchet up; a fall means the accounting is being "
            "restated, which is a data-integrity problem rather than a trading loss."))



#: §33's ratchets bind on the desk's own history. Below this many records that history is noise,
#: and a ratchet calibrated on noise blocks real work for no reason.
_MINE_RATCHET_MIN_RECORDS = 10


def check_mine_evidence_base(defects) -> None:
    """A ratchet calibrated on two observations is superstition with a JSON file.

    §33's conversion ratchet, latency-regression bound and tier weights all bind against
    best-ever values. Those are meaningful once there is a distribution and meaningless before:
    with n=2, a single fast conversion sets a "best median latency" that every future cycle is
    then held to. The machinery is orders of magnitude heavier than the evidence under it.

    This does not weaken the ratchet -- it reports when the ratchet is running ahead of its own
    evidence base, so a bar that starts biting can be read as "too few observations" rather than
    "the desk got worse".
    """
    n = 0
    with contextlib.suppress(Exception):
        n = int(json.loads(
            (ROOT / "docs/research/conversion_record.json").read_text("utf-8"))["n_records"])
    if 0 < n < _MINE_RATCHET_MIN_RECORDS:
        defects.append((
            "mine-ratchet-thin-evidence",
            f"§33 ratchets are binding on {n} record(s), under the {_MINE_RATCHET_MIN_RECORDS} "
            "needed for a distribution. Best-ever latency and conversion rate set from a handful "
            "of observations are noise the desk then holds itself to forever. Treat §33 bars as "
            "ADVISORY until the base is real -- and do not tighten them on this evidence."))


#: One-shot scripts that legitimately ran once and are kept for provenance. Anything NOT listed
#: here must be reachable, so the exemption is a written decision rather than a silent default.
_ONESHOT_SCRIPTS = frozenset({
    "backfill_onchain_oos.py", "batch_onchain.py", "batch_premium.py", "build_dev_factor.py",
    "dl_metrics_history.py", "pull_cme.py",
    # classified 2026-07-31 (orphan-scripts sweep):
    "collect_bitmex_funding.py",   # phase-1 decade ingest, ran 07-31 -> data/bitmex_funding.jsonl
                                   # (11,148 rows); forward funding comes from the live collectors,
                                   # phase-2 tranche runner is rowed separately
    "flatten_cookie.py",           # principal-approved COOKIEUSDT incident tool, ran once 07-28
    "hl_filter_test.py",           # elite-trader premise experiment (kernel of the 26-layer spec
    "screen_smart_dumb.py",        # decision) -- both ran once, verdicts recorded in data/hl_*.log
    "verify_fixes.py",             # dated live-code verification of the a1bcd86 fixes, ran once
})


def check_orphan_scripts(defects) -> None:
    """§36: a SCRIPT nothing runs is an orphan too -- and the orphan check could not see it.

    `check_orphan_code` walks the import graph from `scripts/` as its ROOTS, so "is this script
    itself reached by anything?" was unaskable by construction. The blind spot was exactly the
    shape of scripts/: on 2026-07-26 eight scripts were written and wired to nothing, including
    `page_digest.py`, which describes itself as a daily job and was absent from the daily cycle.

    Reachability is generous on purpose -- the cycle, any other script, any lib, CI config, or a
    documented runbook all count. What is left is genuinely unreferenced, and a one-shot that
    honestly ran once belongs in `_ONESHOT_SCRIPTS` with that stated, not in silence.
    """
    import re
    sdir, corpus = ROOT / "scripts", []
    if not sdir.exists():
        return
    for pat in ("scripts/*.py", "libs/**/*.py", "*.md", "docs/**/*.md", "ops/*",
                "*.toml", "*.yml", "*.yaml", "*.sh", ".github/**/*"):
        for f in ROOT.glob(pat):
            # THIS FILE IS EXCLUDED. Naming a script in the checker's own prose must not exempt
            # it -- the first version described `page_digest.py` in this very docstring and
            # thereby marked it reachable. A checker that launders its examples into passes is
            # the same false-negative class as the one-hop orphan check it replaced.
            #
            # AUDIT REPORTS ARE EXCLUDED FOR THE SAME REASON, one file wider (found 2026-07-30 by
            # this check's own test going red). A deep-sweep report DESCRIBES orphans; it does not
            # wire them. 20260730_research-engine.md:786 reads "scripts/page_digest.py: grep -> no
            # hits" -- the report correctly IDENTIFIED the orphan, and writing that sentence down
            # made this detector count it as referenced and fall silent. Diagnosing a problem must
            # never be what silences its detection, or the desk's own audits become the thing that
            # hides the findings.
            # docs/audit_shards/ excluded 2026-07-31, third instance of the same class: the
            # sharded audit dossiers QUOTE orphan findings verbatim ("scripts/page_digest.py:
            # no hits"), and that quotation silenced this very detector for a day.
            if (f.is_file()
                    and f.name not in ("daily_research_cycle.py", "max_audit.py")
                    and "deep_sweep" not in f.as_posix()
                    and "audit_shards" not in f.as_posix()):
                with contextlib.suppress(OSError):
                    corpus.append(f.read_text("utf-8", errors="ignore"))
    blob = "\n".join(corpus)
    cycle = set(re.findall(r'"scripts/([a-z_0-9]+\.py)"',
                           (sdir / "daily_research_cycle.py").read_text("utf-8", errors="ignore")))
    dead = []
    for f in sorted(sdir.glob("*.py")):
        if f.name in cycle or f.name in _ONESHOT_SCRIPTS or f.name == "daily_research_cycle.py":
            continue
        stem = re.escape(f.stem)
        if not re.search(rf"scripts/{re.escape(f.name)}|scripts\.{stem}\b|\b{stem}\b", blob):
            dead.append(f.name)
    if dead:
        defects.append((
            "orphan-scripts",
            f"§36: {len(dead)} script(s) referenced by NOTHING -- not the daily cycle, not another "
            f"script, not a lib, not CI, not a runbook: {', '.join(dead[:8])}"
            f"{'...' if len(dead) > 8 else ''}. check_orphan_code treats scripts/ as its ROOTS, so "
            "it cannot see these. Wire each into a cadence, add it to _ONESHOT_SCRIPTS with the "
            "reason it ran once, or delete it -- built-and-forgotten must not look like finished."))
    if (sdir / "test_review_fixes.py").exists():
        defects.append((
            "test-outside-test-tree",
            "scripts/test_review_fixes.py is a test file living outside tests/, so pytest never "
            "collects it. Move it to tests/ or rename it -- a test that never runs is worse than "
            "no test, because it reads as coverage."))


#: Every doc that can carry a numbered law. A number must identify ONE law across all of them.
_LAW_DOCS = ("docs/DIGGING_CHARTER.md", "ops/principal_doctrine.txt")


def check_law_numbers_unique(defects) -> None:
    """A law number must name exactly one law. Nothing enforced that, and it collided.

    On 2026-07-26 two accounts independently wrote a §38 and a §39 for DIFFERENT laws, hours
    apart on separate branches; it surfaced only because the merge conflicted. A citation to
    "§39" then resolves to whichever copy the reader happens to open, which is §36's
    no-ungoverned-artifact rule failing at the citation layer -- the law numbers themselves were
    the ungoverned artifact.

    Reports the next free number too, so allocating one is a lookup rather than a guess.
    """
    import re
    from collections import defaultdict
    titles: dict[int, set[str]] = defaultdict(set)
    for rel in _LAW_DOCS:
        path = ROOT / rel
        if not path.exists():
            continue
        text = path.read_text("utf-8", errors="ignore")
        for num, title in re.findall(r"^##\s*(\d+)\.\s*([^\n(]{4,60})", text, re.M):
            titles[int(num)].add(title.strip().rstrip("—-").strip().upper()[:40])
    clashes = {n: ts for n, ts in titles.items() if len(ts) > 1}
    if clashes:
        detail = "; ".join(f"§{n} claimed by {len(ts)}: {' | '.join(sorted(ts))}"
                           for n, ts in sorted(clashes.items()))
        defects.append((
            "law-number-collision",
            f"§36: {detail}. A citation to one of these resolves to whichever copy the reader "
            "opens. Renumber the later law -- the trunk keeps the number it landed with."))
    if titles:
        nxt = max(titles) + 1
        marker = ROOT / "docs/research/next_law_number.txt"
        with contextlib.suppress(OSError):
            marker.parent.mkdir(parents=True, exist_ok=True)
            marker.write_text(
                f"{nxt}\n\nNext free law number, recomputed every sweep by "
                f"max_audit.check_law_numbers_unique. Two accounts collided on 38/39 on "
                f"2026-07-26 because allocation was a guess; read this file instead of guessing.\n",
                "utf-8")


def check_orphan_code(defects) -> None:
    """MAP-vs-TERRITORY (audit 2.x): the desk flags idle DATA/capital/clocks but not idle CODE.
    Flags library packages that are almost entirely unreachable from any scripts/ entry point --
    e.g. libs/backtest (the independent cross-check engine) applied to zero strategies. Bounded:
    reports only near-fully-orphaned packages to stay cheap and low-noise."""
    libs = ROOT / "libs"
    scripts = ROOT / "scripts"
    if not (libs.exists() and scripts.exists()):
        return
    # TRANSITIVE reachability. The old proxy checked only DIRECT imports in scripts/, so a package
    # reached through one hop -- scripts -> libs.research.listing_events -> libs.features.labels --
    # was reported as idle while being genuinely run. A check that cries wolf gets acknowledged
    # into silence, which costs more than the check ever earned, and it under-reported too: a
    # package imported ONLY by another orphan is still an orphan and used to look reachable.
    import re

    def _pkgs_in(text: str) -> set[str]:
        return set(re.findall(r"\blibs\.([a-z_][a-z0-9_]*)", text))

    pkg_text: dict[str, str] = {}
    for d in libs.iterdir():
        if d.is_dir() and (d / "__init__.py").exists():
            with contextlib.suppress(OSError):
                pkg_text[d.name] = "\n".join(
                    f.read_text("utf-8", errors="ignore") for f in d.rglob("*.py"))

    reached: set[str] = set()
    frontier = _pkgs_in("\n".join(f.read_text("utf-8", errors="ignore")
                                  for f in scripts.glob("*.py")))
    while frontier:                       # BFS from the entry points, not a single hop
        nxt = frontier.pop()
        if nxt in reached or nxt not in pkg_text:
            continue
        reached.add(nxt)
        frontier |= _pkgs_in(pkg_text[nxt]) - reached

    suspicious = []
    for pkg in sorted(d for d in libs.iterdir() if d.is_dir() and (d / "__init__.py").exists()):
        name = pkg.name
        mods = [m.stem for m in pkg.glob("*.py") if m.stem != "__init__"]
        if len(mods) < 3 or name in reached:
            continue
        suspicious.append(f"{name}({len(mods)} modules)")
    if suspicious:
        defects.append(("orphan-code",
                        "library package(s) unreachable from ANY scripts/ entry point, "
                        "directly or transitively (idle code -- "
                        f"the class never monitored): {', '.join(suspicious[:6])}. Wire the "
                        "safeguard (e.g. libs/backtest cross_engine) or retire on the record -- "
                        "verify against dynamic imports before deleting."))


#: Modules on the MONEY PATH: the ones where "built, tested green, called by nobody" stops being
#: untidy and becomes a safety defect. Every one of these must be reachable from a production
#: entry point, because an S1 desk whose rails have never executed outside pytest has no rails.
#: This list is deliberately short. `check_orphan_code` is package-granular and could not see any
#: of it: libs/execution is reachable via ea_bridge, so staging.py sat orphaned inside a "live"
#: package for 8 days -- imported by its own test and nothing else -- while the register carried
#: the connector as PARTIAL and the audit reported clean.
_MONEY_PATH_MODULES = (
    "libs.execution.staging",
    "libs.execution.binance_live",
    "libs.execution.binance_spot_live",
    "libs.execution.protective_stops",
    "libs.execution.canary",
    "libs.execution.ramp_gate",
    "libs.ops.derisk_ladder",
    "libs.risk.gate",
    "libs.risk.sizing",
)


def _module_reachability() -> tuple[set[str], dict[str, str]]:
    """Transitive MODULE-level reachability from production entry points (scripts/, app/, api/).

    Package granularity is the blind spot this replaces: asking "is libs.execution used?" answers
    yes forever while any one module in it is imported, which is why a dead stage machine inside
    a live package was invisible. Tests are NOT entry points -- being imported by your own test
    is exactly the condition under audit.
    """
    import re

    mods: dict[str, str] = {}
    for f in (ROOT / "libs").rglob("*.py"):
        if f.stem == "__init__":
            continue
        with contextlib.suppress(OSError):
            mods[".".join(f.relative_to(ROOT).with_suffix("").parts)] = \
                f.read_text("utf-8", errors="ignore")

    def _refs(text: str) -> set[str]:
        out = {"libs." + m.group(1) for m in re.finditer(r"\blibs\.([a-z0-9_.]+)", text)}
        # `from libs.execution import staging` names the module in the IMPORT list, not the path
        for m in re.finditer(r"from\s+(libs[a-z0-9_.]*)\s+import\s+([^\n(]+)", text):
            for n in m.group(2).split(","):
                token = n.strip().split(" ")[0]
                if token:
                    out.add(f"{m.group(1)}.{token}")
        return out

    frontier: set[str] = set()
    for entry in ("scripts", "app", "api"):
        d = ROOT / entry
        if d.exists():
            for f in d.rglob("*.py"):
                with contextlib.suppress(OSError):
                    frontier |= _refs(f.read_text("utf-8", errors="ignore"))

    reached: set[str] = set()
    while frontier:
        n = frontier.pop()
        if n in reached:
            continue
        reached.add(n)
        if n in mods:
            frontier |= _refs(mods[n]) - reached
        # a package __init__ that re-exports counts as a hop
        init = ROOT / Path(n.replace(".", "/")) / "__init__.py"
        if init.exists():
            with contextlib.suppress(OSError):
                frontier |= _refs(init.read_text("utf-8", errors="ignore")) - reached
    return reached, mods


def check_decision_ledger_matures(defects) -> None:
    """The self-improvement loop must have a QUEUE, not just a cadence.

    The ledger's policy promises "the monthly governance review scores each matured entry so
    decision QUALITY compounds". Measured 2026-07-26: 189 decisions, 2 scored, and 175 with no
    review date at all -- nothing could mature, so the monthly review ran against an empty queue
    and correctly reported no work. A cadence pointed at an empty queue looks identical to a
    cadence with nothing to do, which is why this went unnoticed for the ledger's whole life.
    """
    try:
        from datetime import date as _date

        from libs.research.decision_review import health as _health
        doc = json.loads((ROOT / "data" / "decision_ledger.json").read_text("utf-8"))
    except (OSError, json.JSONDecodeError, ImportError):
        return
    rows = doc.get("decisions", []) if isinstance(doc, dict) else doc
    rows = [r for r in rows if isinstance(r, dict)]
    if not rows:
        return
    h = _health(rows, _date.today())
    if h.no_review_date:
        defects.append((
            "decision-ledger-undated",
            f"{h.no_review_date} of {h.total} logged decisions carry NO review date -- they can "
            "never come due, so the scoring cadence has nothing to pull and reports clean "
            "forever. Run scripts/run_decision_review.py to derive them."))
    elif h.due:
        defects.append((
            "decision-ledger-unscored",
            f"{h.due} decision(s) matured and unscored, oldest {h.oldest_overdue_d}d past due "
            f"({h.scored}/{h.total} = {h.scored_pct}% ever scored). Scoring is a JUDGEMENT and is "
            "never automated -- see data/decision_review.json for the worklist."))


def check_money_path_wired(defects) -> None:
    """Every money-path module must have a PRODUCTION caller, not just a test.

    This is the §36 orphaned-artifact failure in the one place it can cost the whole book, and
    it is checked structurally -- "is there a path from an entry point to this module" -- rather
    than by naming a caller, so it survives the callers being renamed or moved.
    """
    reached, mods = _module_reachability()
    missing = [m for m in _MONEY_PATH_MODULES if m in mods and m not in reached]
    absent = [m for m in _MONEY_PATH_MODULES if m not in mods]
    if missing:
        defects.append((
            "money-path-orphaned",
            f"money-path module(s) with NO production caller -- reachable only from their own "
            f"tests: {', '.join(missing)}. A rail that has never executed outside pytest is not "
            "a rail; wire it into an entry point (see scripts/run_live_guard.py) or delete it "
            "and stop counting it as built."))
    if absent:
        defects.append((
            "money-path-module-missing",
            f"money-path module(s) named by the guard but absent from the tree: "
            f"{', '.join(absent)}. A moved or deleted file must not silently make this check "
            "blind to wherever the logic went."))


def check_orphan_modules(defects) -> None:
    """Census of individually-unreachable libs MODULES (informational, not a wall of noise).

    Reported as a single number rather than 60-odd names on purpose: the package-level check
    stays the blocking one for whole idle subsystems, this tracks the long tail so it cannot
    grow unnoticed, and `check_money_path_wired` is what actually blocks. A check that prints a
    list nobody can action gets acknowledged into silence and takes the useful ones with it.
    """
    reached, mods = _module_reachability()
    orphans = sorted(m for m in mods if m not in reached)
    if len(orphans) > _ORPHAN_MODULE_BUDGET:
        defects.append((
            "orphan-modules",
            f"{len(orphans)} of {len(mods)} libs modules are unreachable from any production "
            f"entry point (budget {_ORPHAN_MODULE_BUDGET}). Newest offenders: "
            f"{', '.join(orphans[:5])}. Wire or retire -- the budget ratchets DOWN as the "
            "backlog is worked off, never up."))


#: Ratchet for the module-orphan census. 67 -> 66 when run_live_guard.py wired the stage machine
#: and connectors back in; 66 -> 49 when run_alpha_factory.py gave the seventeen research engines
#: a production caller; 49 -> 45 when lockbox/fdr/cpcv/baselines were wired into the promotion
#: path. Lower this as the backlog clears; raising it to make the check pass is the one edit that
#: defeats its purpose.
_ORPHAN_MODULE_BUDGET = 45


#: Docs where mined finds ACCUMULATE UN-DISPOSITIONED -- the only place §33 inventory can rot.
#: Deliberately excluded, each for a reason (the check must flag rot, not paperwork):
#:   graveyard.md              -- a graveyard entry IS a disposition; terminal by construction
#:   negative_knowledge.md     -- own terminal schema (``[priority: ...] review-due: <date>``)
#:   search_operator_library.md-- own terminal schema (``[status: active|watch|archived]``)
#:   prospector_watchlist.md   -- prose STEP headers, not carded finds
_DIG_DOCS = (
    "docs/research/data_axis_watchlist.md",
    "docs/research/feed_inbox.md",
    "docs/research/discovery_hypotheses.md",
    "docs/research/literature_coverage.md",
)
#: Card-bearing docs deliberately OUT of §33 scope, each with its reason. Kept explicit so the
#: scope check below can tell "consciously excluded" from "quietly unmonitored".
_DIG_DOCS_EXCLUDED = {
    "docs/research/micro_audit_inbox.md":
        "audit findings, not mined finds -- own rotting-findings check",
    "docs/research/panel_inbox.md": "external panel output -- own rulings/scoring loop",
}
#: Committed-state is checked over the whole research surface, including the excluded docs above:
#: a graveyard entry is self-dispositioning but still has to reach git to exist.
_DIG_TRACKED = ("docs/research", "docs/graveyard.md")
#: Written when the backlog is non-empty; every ops/run_*_dig.sh refuses to start while it exists.
MINING_SUSPENDED = ROOT / "data/mining_suspended"


def _conversion_artifacts() -> list[str]:
    """Names the desk can CORROBORATE on disk -- the artifact-only credit set for §33.

    Mirrors ``_converted_axes``: a conversion is credited from things that exist (a collector's
    output, a reconstructed-OOS report, a screened axis in research memory), never from a claim in
    a document. An organ does not grade its own homework.
    """
    names: set[str] = set()
    with contextlib.suppress(Exception):
        names.update(_converted_axes())
    for pat in ("data/*.jsonl", "data/batch_*.json", "reports/reconstructed_oos/*.json"):
        with contextlib.suppress(Exception):
            names.update(p.stem.lower() for p in ROOT.glob(pat))
    for pat in ("scripts/collect_*.py", "scripts/backfill_*.py"):
        with contextlib.suppress(Exception):
            names.update(p.stem.replace("collect_", "").replace("backfill_", "").lower()
                         for p in ROOT.glob(pat))
    return sorted(n for n in names if n)


MINE_LEDGER = ROOT / "data/mine_conversion_log.jsonl"
#: TRACKED on purpose (docs/, not gitignored data/). The ratchet's whole guarantee is that the
#: bar never loosens -- stored under data/* it was one `rm` from a fresh record, so the monotonic
#: standard was erasable by an organ that wanted an easier bar. In docs/ a reset shows up in
#: `git status`, in the diff, and in check_dig_uncommitted. Tampering becomes visible, not silent.
MINE_RATCHET = ROOT / "docs/research/conversion_record.json"
MINE_PRIORS = ROOT / "data/mine_generation_priors.json"


def _mine_thresholds() -> dict[str, Any]:
    """§33 bars, evidence-adjustable within hard tighten-only bounds (the desk's ThresholdBook)."""
    out = {"kill": 0.60, "stale": 14.0, "regress": 1.5}
    try:
        from libs.self_improvement.adaptive_thresholds import ThresholdBook
        b = ThresholdBook(ROOT / "data/adaptive_thresholds.json")
        out = {"kill": b.get("mine_kill_share_bar"),
               "stale": b.get("mine_stale_owing_days"),
               "regress": b.get("mine_latency_regress_mult")}
    except Exception:
        pass
    return out


def _mine_items():
    """Parse every owing carded find, tiered against the axes the desk has ALREADY ingested."""
    from libs.research.mine_conversion import parse_dispositions
    from libs.research.source_backlog import parse_watchlist
    axes = []
    with contextlib.suppress(Exception):
        axes = _acquired_axes()
    items = []
    for rel in _DIG_DOCS:
        p = ROOT / rel
        if not p.exists():
            continue
        with contextlib.suppress(Exception):
            text = p.read_text("utf-8")
            found = parse_dispositions(text, source=rel, ingested_axes=axes)
            # A source card's OWN grade is already a disposition -- 'verified-clean' and
            # 'destroyed-at-source' are terminal in the existing taxonomy, so demanding a second
            # §33 tag would be paperwork, not conversion. Reuse the graded classifier the desk
            # already has rather than duplicating the grade rules here.
            with contextlib.suppress(Exception):
                resolved = {c.name.lower() for c in parse_watchlist(text)
                            if c.category == "resolved"}
                if resolved:
                    found = [i for i in found
                             if not any(r in i.name.lower() for r in resolved)]
            items += found
    return items


def _mine_backing() -> dict[str, Any]:
    """Artifact-only credit, per disposition. `killed` is backed by the GRAVEYARD -- which is what
    makes mass-killing the backlog cost more than converting it, rather than less."""
    arte = _conversion_artifacts()
    grave = []
    gp = ROOT / "docs/graveyard.md"
    if gp.exists():
        with contextlib.suppress(Exception):
            grave = [ln.strip(" #-*").lower() for ln in gp.read_text("utf-8").splitlines()
                     if ln.strip()]
    return {"wired": arte, "screened": arte, "killed": grave}


def check_mine_conversion(defects) -> None:
    """§33 MINED-TO-WIRED (stock + quality + value): no carded find sleeps twice, a backlog
    SUSPENDS mining, and the backlog is PRICED so it cannot be cleared by doing only easy work.

    Mined intelligence is inventory, and un-converted inventory depreciates. Mining is not the
    product; conversion is. This writes the gate file the digger shells refuse to start against,
    so an organ producing faster than the desk converts pays the cost itself -- flow control, not
    punishment. Three teeth beyond mere reporting: `killed` is corroborated against the graveyard
    (closing the mass-kill escape hatch), the backlog is TIER-WEIGHTED, and a priority inversion
    (cheap work finished while a Tier-1 defect-closer still owes) is its own defect.
    """
    from libs.research.mine_conversion import (
        append_snapshot,
        conversion_report,
        first_seen_map,
        load_ledger,
        vanished,
    )

    items = _mine_items()
    if not items:
        return  # nothing carded -- nothing owed (a fresh clone, not a defect)
    thr = _mine_thresholds()
    today = datetime.now(UTC).date()
    ledger = load_ledger(MINE_LEDGER)
    rep = conversion_report(items, as_of=today, backing=_mine_backing(), root=ROOT,
                            first_seen=first_seen_map(ledger))
    gone = vanished(items, ledger, as_of=today)
    if gone:
        defects.append((
            "mine-item-vanished",
            f"§33: {len(gone)} find(s) owed a disposition in the last snapshot and have "
            f"DISAPPEARED from the docs -- {', '.join(gone[:8])}. Deleting the card does not "
            "delete the obligation: the ledger remembers. Restore the item and dispose of it "
            "properly, or record the deletion as a `killed` with its graveyard mechanism."))
    with contextlib.suppress(OSError):
        append_snapshot(MINE_LEDGER, items)

    # the gate file IS the enforcement -- a reported backlog that stops nothing is a wish
    try:
        if rep.suspend_mining:
            MINING_SUSPENDED.parent.mkdir(parents=True, exist_ok=True)
            MINING_SUSPENDED.write_text(rep.verdict + "\n", "utf-8")
        elif MINING_SUSPENDED.exists():
            MINING_SUSPENDED.unlink()
    except OSError:
        pass  # a read-only checkout still reports; it just cannot gate

    if rep.n_backlog:
        defects.append((
            "mine-conversion-backlog",
            f"§33: {rep.n_backlog}/{rep.n_items} carded find(s) owe a disposition (weighted "
            f"{rep.weighted_backlog}, highest tier owing T{rep.top_tier_owing}) -- "
            f"{', '.join(rep.backlog_names)}. MINING IS SUSPENDED (data/mining_suspended): the "
            "whole dig slot reassigns to conversion, HIGHEST TIER FIRST, catalogue nothing new "
            "until it clears. Every item takes exactly one of wired / screened / killed / "
            "deferred(DATE) -- silence is the defect."))
    if rep.n_illegal:
        defects.append((
            "mine-conversion-illegal",
            f"§33: {rep.n_illegal} disposition(s) are not legal -- {', '.join(rep.illegal_names)}."
            " An UNDATED deferral is the hiding place every rotting backlog uses: name the blocker"
            " and give a date, or pick a terminal disposition."))
    if rep.n_unbacked:
        defects.append((
            "mine-conversion-unbacked",
            f"§33: {rep.n_unbacked} item(s) CLAIM a terminal disposition with no corroborating "
            f"artifact -- {', '.join(rep.unbacked_names)}. Conversion is credited from artifacts "
            "on disk, never from a report; a 'killed' needs its GRAVEYARD entry with the mechanism "
            "of death. Produce the artifact or downgrade the claim."))
    if rep.kill_share > thr["kill"] and (rep.n_killed + rep.n_wired + rep.n_screened) >= 4:
        defects.append((
            "mine-conversion-killspike",
            f"§33 quality: {rep.kill_share:.0%} of terminal dispositions are 'killed' (bar "
            f"{thr['kill']:.0%}) -- the backlog is being cleared by GRAVEYARD rather than by "
            "conversion. A disposition is not automatically a conversion; a bad batch is real but "
            "so is the cheap exit, and this is its signature. Justify each kill's mechanism."))
    if rep.n_fuzzy_credited and not rep.n_unbacked:
        defects.append((
            "mine-conversion-fuzzy",
            f"§33 evidence standard: {rep.n_fuzzy_credited} terminal claim(s) are credited by "
            "NAME MATCHING, not by a named artifact. Fuzzy credit breaks silently on a rename and "
            "grants silently on a coincidence. Use the exact form -- "
            "`[§33: wired -> data/upbit_1m.jsonl]` -- which must exist and be non-empty. Not a "
            "backlog defect; a standard the desk should be ratcheting up."))
    if rep.priority_inversion:
        defects.append((
            "mine-conversion-inversion",
            f"§33.6 priority inversion: a T{rep.top_tier_owing} item still owes while cheaper-tier "
            "work was completed. Defect-closers (a permanently-firing gate made satisfiable) "
            "outrank mechanism priors, which outrank new surfaces, which outrank operators. Work "
            "the expensive tier FIRST -- clearing the easy tail is how a backlog looks like "
            "progress while the valuable item rots."))


def check_mine_flow(defects) -> None:
    """§33 FLOW + FEEDBACK + RATCHET: is conversion getting FASTER, and does it steer generation?

    A stock check says whether inventory exists; only a flow check says whether the desk is
    improving. And conversion outcomes that dead-end in an audit report are a fence -- fed back as
    per-class priors they become a control system, which is what maximum utilisation actually
    means. The bar is the desk's OWN BEST-EVER performance: every record tightens it permanently
    and it never loosens, so there is no "good enough", only better-than-our-best or a regression.
    """
    from libs.research.mine_conversion import (
        class_priors,
        feedback_applied,
        flow_stats,
        law_effectiveness,
        ledger_regressed,
        load_ledger,
        load_ratchet,
        priors_payload,
        tier_calibration,
        update_ratchet,
    )

    ledger = load_ledger(MINE_LEDGER)
    if len(ledger) < 2:
        return  # a single snapshot cannot measure flow -- not a defect, just no history yet
    thr = _mine_thresholds()
    flow = flow_stats(ledger)
    n_names = len({str(i.get("n", "")) for r in ledger for i in r["items"]})
    rate = (flow.n_converted / n_names) if n_names else 0.0

    priors = class_priors(ledger)
    if priors:
        with contextlib.suppress(OSError):
            MINE_PRIORS.parent.mkdir(parents=True, exist_ok=True)
            MINE_PRIORS.write_text(json.dumps(priors_payload(priors), indent=2), "utf-8")

    prior = load_ratchet(MINE_RATCHET)
    truncated, why_trunc = ledger_regressed(prior, ledger)
    if truncated:
        defects.append((
            "mine-ledger-truncated",
            f"§33: {why_trunc}. The ledger is the evidence base for latency, the per-class priors "
            "and the ratchet itself -- erasing it resets all three and hands back an easier bar. "
            "The high-water marks in docs/research/conversion_record.json are what caught this."))
    new_ratchet, verdict = update_ratchet(
        prior, flow, conversion_rate=rate, regress_mult=thr["regress"], ledger=ledger)
    with contextlib.suppress(OSError):
        MINE_RATCHET.write_text(new_ratchet.model_dump_json(indent=2), "utf-8")

    if flow.oldest_owing_days > thr["stale"]:
        defects.append((
            "mine-flow-rotting",
            f"§33: '{flow.oldest_owing_name}' has owed a disposition for "
            f"{flow.oldest_owing_days:.0f}d (bar {thr['stale']:.0f}d). Age IS the damage -- a "
            "finding depreciates while it waits, and the desk has been faster than this."))
    if verdict.regressed:
        defects.append((
            "mine-flow-regression",
            f"§33 RATCHET: {verdict.verdict} Next-cycle bar {verdict.next_bar_days:.1f}d. The "
            "standard is the desk's own record and it only moves down -- recover the pace or "
            "log the measured reason it is no longer achievable."))
    if flow.latency_worsening and not verdict.regressed:
        defects.append((
            "mine-flow-slowing",
            f"§33: conversion latency is TRENDING worse (median {flow.median_latency_days:.1f}d, "
            "recent half >1.5x the earlier half). Catch it as a trend, before it becomes a "
            "regression against the record."))
    # THE LAW HELD TO ITS OWN STANDARD -- everything else here pressures the desk; these two ask
    # whether §33's own machinery earns its place, which the no-ceiling axiom demands of anything
    # claiming to be at max.
    cal = tier_calibration(ledger)
    if cal.inverted:
        defects.append((
            "mine-tier-miscalibrated",
            f"§33 self-audit: {cal.verdict} The T1=8..T4=1 weighting is an ASSERTION, and measured "
            "outcomes contradict it -- priority enforcement is currently steering effort toward "
            "work that does not finish. Re-tier the affected finds (explicit `tier:N`) or fix the "
            "inference keywords; do not leave a weighting in force that the evidence rejects."))
    eff = law_effectiveness(ledger)
    if eff.conclusive and not eff.improving:
        defects.append((
            "mine-law-ineffective",
            f"§33 self-audit: {eff.verdict} A law is not exempt from the evidence standard it "
            "enforces. Trend, not counterfactual (no pre-§33 baseline exists) -- but flat is flat. "
            "Either the gate is not biting or conversion is bottlenecked elsewhere; establish "
            "which before adding more enforcement on top."))
    ok, why = feedback_applied(ledger, priors)
    if not ok:
        defects.append((
            "mine-feedback-ignored",
            f"§33.4 closed loop: {why} data/mine_generation_priors.json is published every "
            "sweep -- generation MUST read it and reweight. A prior nothing acts on is the same "
            "failure as a law with no monitor."))


def check_mine_scope(defects) -> None:
    """A find written somewhere unscanned is a find outside the law -- with no code change needed.

    §33 reads a FIXED list of docs. That list is the law's blast radius, and a digger that writes
    its cards to any other file evades every check in the family without touching tracked code --
    the one bypass that does not show up in a diff. So the scope itself is audited: any
    docs/research markdown carrying numbered cards must be either IN the scanned set or in the
    explicit exclusion list with a stated reason. Consciously excluded is fine; quietly unmonitored
    is not. Same shape as check_review_risks_tracked -- a thing named in one place must inherit the
    discipline of the other, and nothing may fall between them by omission.
    """
    research = ROOT / "docs/research"
    if not research.is_dir():
        return
    card = re.compile(r"^### \d+\.", re.MULTILINE)
    rogue = []
    for p in sorted(research.glob("*.md")):
        rel = p.relative_to(ROOT).as_posix()
        if rel in _DIG_DOCS or rel in _DIG_DOCS_EXCLUDED:
            continue
        with contextlib.suppress(OSError):
            n = len(card.findall(p.read_text("utf-8", errors="ignore")))
            if n:
                rogue.append(f"{p.name}({n} cards)")
    if rogue:
        defects.append((
            "mine-scope-unmonitored",
            f"§33 scope: card-bearing research doc(s) outside the law -- {', '.join(rogue[:8])}. "
            "Findings written here owe no disposition and are invisible to every §33 check, which "
            "is the one bypass that needs no code change. Add each to _DIG_DOCS (in scope) or to "
            "_DIG_DOCS_EXCLUDED with a stated reason -- never leave it decided by omission."))


def check_mine_gate(defects) -> None:
    """The gate must be DERIVED, not a deletable flag -- and it must actually run.

    `data/mining_suspended` was a file, and a file is something `rm` defeats: deleting it would
    have restored mining without converting anything, making the law advisory again. The shells
    now RUN scripts/mine_gate.py, which recomputes the backlog from the docs. Two failure modes
    are checked here because the gate fails OPEN by design (a bug must never freeze the desk's
    entire research intake for a week): the script must exist, and it must execute cleanly.
    """
    import subprocess

    gate = ROOT / "scripts/mine_gate.py"
    if not gate.exists():
        defects.append(("mine-gate-missing",
                        "§33: scripts/mine_gate.py is absent -- the digger shells call it to "
                        "recompute the backlog, and without it the gate degrades to whatever the "
                        "shells do on a missing command. Restore it."))
        return
    shells = [*sorted(ROOT.glob("ops/run_*dig*.sh")), ROOT / "ops/run_frontier_miner.sh"]
    untrusting = [s.name for s in shells if s.exists() and "mine_gate.py" not in
                  s.read_text("utf-8", errors="ignore")]
    if untrusting:
        defects.append(("mine-gate-bypassed",
                        f"§33: digger shell(s) do NOT invoke the derived gate -- "
                        f"{', '.join(untrusting)}. A shell that skips mine_gate.py mines "
                        "regardless of the backlog; that is the law switched off for that organ."))
    try:
        r = subprocess.run([sys.executable, str(gate), "--explain"], cwd=ROOT,
                           capture_output=True, text=True, timeout=120)
    except (OSError, subprocess.SubprocessError) as exc:
        defects.append(("mine-gate-broken",
                        f"§33: the gate script could not be executed ({type(exc).__name__}). It "
                        "fails OPEN by design, so a broken gate silently authorises mining -- "
                        "this defect is the only thing that surfaces it. Fix before the next dig."))
        return
    if "GATE-ERROR" in (r.stdout + r.stderr):
        defects.append(("mine-gate-broken",
                        f"§33: the gate script raised and failed OPEN -- {r.stdout.strip()[:220]}. "
                        "Mining is currently UNGATED. Fix before the next dig."))


def check_dig_uncommitted(defects) -> None:
    """A dig finding not in git DID NOT HAPPEN -- VPS disk is not institutional memory.

    The best output of a cycle is one disk failure from never having existed, and an audit that
    reads only the repo cannot see it at all (the map-vs-territory failure, applied to the desk's
    own research). Compares each dig doc's mtime against the last commit that touched it.
    """
    import subprocess

    # Asked exactly, via git's own index -- NOT file mtimes. A fresh clone stamps every file with
    # the checkout time, so an mtime-vs-commit-time comparison reports the entire research surface
    # as uncommitted on any re-clone. `git status --porcelain` answers the real question.
    try:
        out = subprocess.run(["git", "status", "--porcelain", "--", *_DIG_TRACKED],
                             cwd=ROOT, capture_output=True, text=True, timeout=20)
    except (OSError, subprocess.SubprocessError):
        return  # no git available -- the check simply does not apply here
    if out.returncode != 0:
        return
    stale = []
    for line in out.stdout.splitlines():
        if len(line) > 3:
            code, path = line[:2].strip() or "??", line[3:].strip()
            # RATCHET GRACE (R0147): conversion/holdings records are re-ticked by cron every
            # ~15min, so the working tree is dirty on them within seconds of ANY commit -- as
            # written, this gate could never stay satisfied (measured: re-fired 60s after a
            # commit, aged 141.8h across a day with 4 snapshot commits). "By end of cycle"
            # means a snapshot commit exists within the cycle window, not a perpetually clean
            # tree: a file whose last COMMIT is <6h old was snapshotted this cycle and is not
            # debt. New/untracked files (??) get no grace -- they have never been committed.
            if code != "??":
                try:
                    last = subprocess.run(["git", "log", "-1", "--format=%ct", "--", path],
                                          cwd=ROOT, capture_output=True, text=True, timeout=20)
                    import time
                    if last.returncode == 0 and last.stdout.strip() and \
                            time.time() - int(last.stdout.strip()) < 6 * 3600:
                        continue
                except (OSError, ValueError, subprocess.SubprocessError):
                    pass                     # grace unreadable -> file stays counted (fail firm)
            stale.append(f"{Path(path).name}[{code}]")
    if stale:
        defects.append((
            "dig-output-uncommitted",
            f"§33: dig output UNCOMMITTED -- {', '.join(stale[:8])}. Output not "
            "committed and pushed by end of cycle DID NOT HAPPEN and earns zero credit: git is "
            "the institutional memory, VPS disk is not. Commit, push, and VERIFY the push."))


MINING_RECORD = ROOT / "docs/research/mining_record.json"   # tracked in git, like the §33 record


def check_mining_nonregression(defects) -> None:
    """MINING MAY NEVER REGRESS (principal 2026-07-25, strict). Conversion ratchets UP; mining
    volume ratchets up too and is never allowed to fall. Without this, the cheapest way to raise a
    conversion RATE is to shrink the denominator -- mine less. That is a regression in the desk's
    single irreplaceable input (unprocessed data is unrealized option value; living-web sources
    decay and cannot be re-mined later), so it is a defect, never an optimisation."""
    led = ROOT / "data/mine_conversion_log.jsonl"
    if not led.exists():
        return
    rows = []
    for line in led.read_text("utf-8", errors="ignore").splitlines():
        try:
            rows.append(json.loads(line))
        except Exception:
            continue
    if len(rows) < 3:
        return                                    # not enough history to call a trend
    counts = [len(r.get("items", [])) for r in rows if isinstance(r.get("items"), list)]
    if len(counts) < 3:
        return
    best = max(counts)
    recent = counts[-1]
    try:
        rec = json.loads(MINING_RECORD.read_text("utf-8")) if MINING_RECORD.exists() else {}
    except Exception:
        rec = {}
    record = max(int(rec.get("best_finds", 0)), best)
    if record > int(rec.get("best_finds", 0)):
        MINING_RECORD.write_text(json.dumps(
            {"best_finds": record, "updated": datetime.now(tz=UTC).isoformat(),
             "note": "desk's best-ever carded-find count in one snapshot; ratchets UP only -- "
                     "mining volume may never regress (principal 2026-07-25)"}, indent=1), "utf-8")
    # a genuine regression: latest materially below the all-time record
    if record >= 5 and recent < record * 0.6:
        defects.append((
            "mining-regression",
            f"MINING REGRESSED: latest snapshot carries {recent} carded finds vs the desk's "
            f"record of {record}. Mining volume must NEVER fall -- conversion pressure is never "
            "allowed to shrink acquisition (the cheapest way to fake a conversion rate is to mine "
            "less). Raise mining back above the record; scale extraction to meet it, never the "
            "reverse."))


def check_no_mining_throttle(defects) -> None:
    """STRUCTURAL anti-throttle guard (principal 2026-07-25). Re-verifies every surface a mining
    throttle could return through, so a future edit cannot quietly shrink the desk's intake."""
    gate = ROOT / "scripts/mine_gate.py"
    if gate.exists():
        g = gate.read_text("utf-8", errors="ignore")
        if "return 1" in g.split("def main")[-1]:
            defects.append(("mining-throttle-returned",
                            "scripts/mine_gate.py can exit non-zero again -- that BLOCKS diggers. "
                            "The gate must always exit 0; the backlog steers PRIORITY, never "
                            "whether a dig runs."))
        v = ROOT / "libs/research/mine_conversion.py"
        if v.exists() and "catalogue nothing new" in v.read_text("utf-8", errors="ignore"):
            defects.append(("mining-throttle-language",
                            "the §33 verdict text tells a dig to 'catalogue nothing new' -- that "
                            "string is injected into the dig prompt and throttles mining through "
                            "LANGUAGE. Conversion preempts priority, never acquisition."))
    for sh in [*sorted((ROOT / "ops").glob("run_*dig*.sh")), ROOT / "ops/run_frontier_miner.sh"]:
        try:
            txt = sh.read_text("utf-8", errors="ignore")
        except OSError:
            continue
        if "mine_gate.py" in txt and ("if ! " in txt and "exit 0" in txt):
            defects.append(("mining-throttle-shell",
                            f"{sh.name} carries a blocking early-exit on the mining gate -- a dig "
                            "must never be skipped for a conversion backlog."))


CARRYOVER_LEDGER = ROOT / "data/carryover_sweeps.jsonl"


def check_carryover_skipped(defects) -> None:
    """§37: work the brain was SHOWN and did not do -- distinct from work it never saw.

    The brain is a metered session; it dies on quota, and the cycle's owed work used to die with
    it. §37 records every sweep and hands the backlog back on return. This check closes the other
    half: an item that survived sweeps the brain was AWAKE for was not missed, it was SKIPPED --
    and a plain queue cannot tell the two apart, because a long queue looks identical whether
    nobody was home or everybody walked past it. Only the second is a defect: blaming the desk for
    an outage is unfair, and excusing avoidance is expensive.
    """
    from libs.ops.carryover import carryover_state, load_sweeps

    sweeps = load_sweeps(CARRYOVER_LEDGER)
    if len(sweeps) < 3:
        return  # too little history to distinguish a skip from a fresh item
    st = carryover_state(sweeps, now=NOW)
    skipped = st.skipped_items
    if not skipped:
        return
    worst = ", ".join(f"{i.defect_id}({i.seen_by_live_brain}x awake, {i.age_days:.0f}d)"
                      for i in skipped[:6])
    defects.append((
        "carryover-skipped",
        f"§37: {len(skipped)} item(s) survived sweeps the brain was AWAKE for -- {worst}. "
        f"{st.n_dead_sweeps} cycle(s) were lost to quota and are NOT the excuse for these: the "
        "brain ran, was handed the item, and carried it anyway. Do them, or record in the ledger "
        "why not -- silently carrying an item a third time is what this exists to stop."))


#: Every check the sweep runs. Module-level so other organs (§37 carry-over) can
#: enumerate the same set instead of keeping a second copy that silently drifts.
def check_recommendation_rows(defects) -> None:
    """§42 X1 wire (2026-07-31): the recommendation ledger joins the carry-over pressure loop.

    Measured before this check existed (meta audit 2026-07-31): NO row older than 3.67 days had
    ever been implemented -- λ≈14 rows/day arrived, terminal disposals ran ≈3.2/day and almost
    entirely same-session, so the undone stock grew +10/day and old rows were simply never seen
    again. Directives, findings and gap-register rows all had max_audit gates; the §42 ledger --
    the one organ whose law says nothing recommended is ever forgotten -- had none, so the §37
    brief (built FROM these checks) could not carry its rows across sessions.

    Per-row stable IDs (`rec-owed-R0031`) let the sweep ledger track each row's survival count
    individually, which is the §37 pressure that actually moves work. The per-row list is capped
    to the OLDEST offenders so the pager stays readable; the summary defect carries the TRUE
    totals so the cap hides nothing (no-silent-caps). Grace/due semantics mirror
    scripts/recommendations.py (GRACE_H=24, terminal={implemented,rejected}); a parity test in
    tests/test_desk_integrity_checks.py locks the two against drifting apart.
    """
    _PER_ROW_CAP = 12
    d = _j(ROOT / "docs/research/recommendation_ledger.json", {})
    rows = d.get("recommendations", []) if isinstance(d, dict) else []
    if not rows:
        return
    now = datetime.now(UTC)

    def _age_h(iso):
        try:
            return (now - datetime.fromisoformat(iso)).total_seconds() / 3600.0
        except (TypeError, ValueError):
            return 0.0

    overdue = []
    for r in rows:
        st = r.get("status")
        if st == "open" and _age_h(r.get("raised", "")) > 24.0:
            overdue.append((_age_h(r.get("raised", "")), r, "undisposed"))
        elif st == "scheduled":
            due = str(r.get("due") or "")
            if due and due < now.date().isoformat():
                overdue.append((_age_h(r.get("raised", "")), r, f"scheduled-past-due({due})"))
    if not overdue:
        return
    overdue.sort(key=lambda t: -t[0])
    for age_h, r, why in overdue[:_PER_ROW_CAP]:
        defects.append((f"rec-owed-{r.get('id', '?')}",
                        f"§42: {r.get('id')} {why} {age_h / 24.0:.1f}d "
                        f"[{r.get('source', '?')}]: {str(r.get('summary', ''))[:120]}"))
    defects.append(("rec-ledger-backlog",
                    f"§42: {len(overdue)} recommendation row(s) owe a disposition "
                    f"({sum(1 for *_, w in overdue if w == 'undisposed')} undisposed past 24h "
                    f"grace, {sum(1 for *_, w in overdue if w != 'undisposed')} scheduled past "
                    f"due; oldest {overdue[0][0] / 24.0:.1f}d, {_PER_ROW_CAP} oldest shown "
                    f"per-row). Dispose via scripts/recommendations.py dispose -- implemented "
                    f"with --commit, rejected with a real --reason, or scheduled with an "
                    f"enforced --due. Deleting rows is the denominator trick and is detected."))


CHECKS = [("carryover-skipped", check_carryover_skipped),
          ("recommendation-rows", check_recommendation_rows),
          ("organs", check_organs), ("stubs", check_stub_deaths),
                      ("stale-daemons", check_stale_daemons),
                      ("panel", check_panel), ("coverage", check_coverage),
                      ("findings", check_findings), ("idle", check_idle_capability),
                      ("directives", check_directives), ("verify", check_verify_lag),
                      ("blind", check_blind_trigger),
                      ("self-application", check_self_application),
                      ("dig-depth", check_dig_depth),
                      ("interrogation", check_interrogation),
                      ("generation", check_generation),
                      ("clock-saturation", check_clock_saturation),
                      ("vendor-replacement", check_vendor_replacement),
                      ("forensics-fresh", check_forensics_fresh),
                      ("carry-funding-measured", check_carry_funding_measured),
                      ("memory-hygiene", check_memory_hygiene),
                      ("prompt-layer", check_prompt_layer),
                      ("gate-optimality", check_gate_optimality),
                      ("welded-gates", check_welded_gates),
                      ("data-utilization", check_data_utilization),
                      ("mining-nonregression", check_mining_nonregression),
                      ("no-mining-throttle", check_no_mining_throttle),
                      ("ci-scope", check_ci_scope),
                      ("review-risks", check_review_risks_tracked),
                      ("findings-tracked", check_findings_tracked),
                      ("findings-scope", check_findings_scope),
                      ("findings-ratchet", check_findings_ratchet),
                      ("gap-register-health", check_gap_register_health),
                      ("producer-cadence", check_producer_cadence),
                      ("artifact-governance", check_artifact_governance),
                      ("orphan-code", check_orphan_code),
                      ("money-path-wired", check_money_path_wired),
                      ("decision-maturity", check_decision_ledger_matures),
                      ("orphan-modules", check_orphan_modules),
                      ("capacity-hunt", check_capacity_hunt),
                      ("deploy-path", check_deploy_path),
                      ("capacity-single-source", check_capacity_single_source),
                      ("capacity-runway", check_capacity_runway),
                      ("capacity-allocation-honesty", check_capacity_allocation_honesty),
                      ("capacity-governor-reachable", check_capacity_governor_reachable),
                      ("capacity-knobs-wired", check_capacity_knobs_are_wired),
                      ("book-collapse", check_book_collapse),
                      ("mine-evidence-base", check_mine_evidence_base),
                      ("orphan-scripts", check_orphan_scripts),
                      ("law-numbers", check_law_numbers_unique),
                      ("mine-conversion", check_mine_conversion),
                      ("mine-flow", check_mine_flow),
                      ("mine-gate", check_mine_gate),
                      ("mine-scope", check_mine_scope),
                      ("dig-uncommitted", check_dig_uncommitted),
                      ("depth-parity", check_depth_parity),
                      ("source-backlog", check_source_backlog),
                      ("rejection-shadow", check_rejection_shadow),
                      ("post-gate0-activation", check_post_gate0_activation),
                      ("production", check_production),
                      ("bnb-funded", check_bnb_funded),
                      ("self-sufficiency", check_self_sufficiency),
                      ("rs-detect", check_rubberstamp_detector),
                      ("rs-enforce", check_rubberstamp_enforcement)]


PAID_TARGETS = ROOT / "docs/research/paid_dataset_targets.md"
HOLDINGS_RECORD = ROOT / "docs/research/holdings_record.json"   # git-tracked, ratchets UP only


def check_paid_target_registry(defects) -> None:
    """§42: the paid-dataset target registry must exist, be hunted, and GROW.

    §38 hunts a replacement when a source fails -- reactive. §42 keeps a standing list of every
    valuable paid dataset with a live free-replacement status, so the desk already knows what it
    would do if a vendor vanished. A FIXED list is the same blind spot in a different shape, so
    the list growing is itself the deliverable.
    """
    if not PAID_TARGETS.exists():
        defects.append(("paid-registry-missing",
                        "§42: docs/research/paid_dataset_targets.md is missing -- the desk has no "
                        "standing list of paid datasets to hunt free replacements for, so it can "
                        "only react to failures instead of anticipating them"))
        return
    txt = PAID_TARGETS.read_text("utf-8", errors="ignore")
    rows = [ln for ln in txt.splitlines() if ln.startswith("| ") and "---" not in ln]
    n = max(0, len(rows) - 1)                      # minus the header row
    open_items = sum(1 for ln in rows if "OPEN" in ln)
    try:
        rec = json.loads(HOLDINGS_RECORD.read_text("utf-8")) if HOLDINGS_RECORD.exists() else {}
    except Exception:
        rec = {}
    best = int(rec.get("best_paid_targets", 0))
    if n > best:
        rec["best_paid_targets"] = n
        rec["updated"] = datetime.now(tz=UTC).isoformat()
        rec.setdefault("note", "§42 ratchet: registry size and holdings only grow; a fall is a "
                               "regression defect, never a new normal")
        HOLDINGS_RECORD.write_text(json.dumps(rec, indent=1), "utf-8")
    elif n < best:
        defects.append(("paid-registry-shrank",
                        f"§42: paid-dataset registry fell to {n} entries from a record of {best} "
                        "-- the hunt list may only GROW. Restore the removed targets or record "
                        "why each is genuinely no longer a dataset worth replacing."))
    # a registry nobody advances is a document, not a hunt
    age_d = (NOW - PAID_TARGETS.stat().st_mtime) / 86400.0
    if age_d > 14 and open_items:
        defects.append(("paid-registry-stagnant",
                        f"§42: {open_items} OPEN replacement hunts and the registry has not been "
                        f"touched in {age_d:.0f}d. Every dig must advance the top OPEN item it "
                        "can and ADD any paid dataset it encountered -- a list that never grows "
                        "is the same blind spot in a different shape."))


def check_holdings_never_shrink(defects) -> None:
    """§42(4): non-noise information holdings grow monotonically -- quantity AND quality.

    Counts the desk's live data surface (lake axis dirs + forward-clock/series jsonl files) and
    ratchets it against the best-ever. A source removed without replacement, a series left to rot,
    or history quietly dropped is a §34 regression arriving by attrition rather than by mining
    less. Today's holdings are the FLOOR, never the target.
    """
    lake = ROOT / "data/lake/bronze"
    axes = sum(1 for _ in lake.iterdir()) if lake.exists() else 0
    series = len(list(ROOT.glob("data/*.jsonl")))
    surface = axes + series
    if surface == 0:
        return
    try:
        rec = json.loads(HOLDINGS_RECORD.read_text("utf-8")) if HOLDINGS_RECORD.exists() else {}
    except Exception:
        rec = {}
    best = int(rec.get("best_surface", 0))
    if surface > best:
        rec["best_surface"] = surface
        rec["updated"] = datetime.now(tz=UTC).isoformat()
        HOLDINGS_RECORD.write_text(json.dumps(rec, indent=1), "utf-8")
    elif best >= 8 and surface < best * 0.9:
        defects.append(("holdings-shrank",
                        f"§42(4): information surface fell to {surface} (axes+series) from a "
                        f"record of {best}. Holdings may NEVER shrink -- a dropped source, a "
                        "rotted series or discarded history is a regression by attrition. Restore "
                        "it or record the replacement that supersedes it."))


FEE_RECORD = ROOT / "docs/research/fee_ratio_record.json"   # git-tracked; ratchets DOWN only


def check_fee_carry_ratio(defects) -> None:
    """§40: fees must always shrink RELATIVE to the carry they consume.

    Absolute fees say nothing -- a bigger book pays more and earns more. The viability number is
    what fraction of the harvest the fees eat. This desk went from fees at 2.4x funding to
    commission -133 -> -30 over 7 days once patient-maker opens and the single-book invariant
    landed; that gain becomes the floor, and any material worsening is a defect rather than a new
    normal.
    """
    try:
        import time as _t

        from libs.execution import binance_testnet as _fut
        # PAGINATE (2026-07-26). This called `_signed(/fapi/v1/income, limit=1000)` directly and
        # got back exactly 1000 rows -- the cap. Binance serves <=1000 rows/call, and this book
        # books >1000 income rows in 7 days, so the window silently truncated to its most recent
        # slice: funding read 2.80 against a true 13.57, commission 29.14 against a true 129.18.
        # The understated funding then tripped this function's own flat-book guard, so §40 never
        # fired even once it was registered. Worse, the truncated 2.80 was mistaken for a real
        # flat book and written into the guard's comment as the 07-25 dead-man fire -- the bug
        # manufactured its own justification. `income_summary` is the audited paginated+deduped
        # helper and is the ONLY sanctioned way to read this endpoint (institutional_knowledge:
        # "paginate every venue history endpoint... truncation never throws an error").
        inc = _fut.income_summary(int((_t.time() - 7 * 86400) * 1000))
    except Exception:
        return                                    # venue unreachable is not a fee defect
    funding = float(inc.get("funding", 0.0))
    commission = abs(float(inc.get("commission", 0.0)))
    if funding < 5.0:
        # FLAT-BOOK GUARD: with almost no harvest the ratio explodes for reasons unrelated to
        # execution quality. Firing here would be a false defect, and false defects train the
        # desk to ignore the check.
        return
    ratio = commission / funding
    try:
        rec = json.loads(FEE_RECORD.read_text("utf-8")) if FEE_RECORD.exists() else {}
    except Exception:
        rec = {}
    best = float(rec.get("best_ratio", 9e9))
    if ratio < best:
        FEE_RECORD.write_text(json.dumps(
            {"best_ratio": round(ratio, 4), "commission_7d": round(commission, 2),
             "funding_7d": round(funding, 2),
             "updated": datetime.now(tz=UTC).isoformat(),
             "note": "§40 ratchet: fees as a fraction of funding earned. Ratchets DOWN only -- a "
                     "material worsening is a defect, never a new normal."}, indent=1), "utf-8")
        # NO EARLY RETURN (2026-07-26): banking a new best must never suppress the ABSOLUTE alarm
        # below. The first run on this book would otherwise record fees at 9.5x the harvest as
        # "best ever" and report nothing at all -- a ratchet is a relative test, and a sleeve
        # whose fees exceed its entire harvest is broken in absolute terms however it trends.
    if ratio > best * 1.3 and best < 9e8:
        defects.append((
            "fee-ratio-regression",
            f"§40: fees are eating {ratio:.2f}x the funding harvest (7d: commission "
            f"{commission:.2f} vs funding {funding:.2f}) against a best-ever of {best:.2f}x. "
            "Fees must always fall RELATIVE to carry. Check maker fill-rate (patient opens should "
            "keep it climbing), churn (24h min-hold), BNB burn funding at live, and whether "
            "turnover rose without a matching rise in harvest."))
    if ratio > 1.0:
        defects.append((
            "fee-ratio-above-one",
            f"§40: fees ({commission:.2f}) EXCEED the funding earned ({funding:.2f}) over 7d "
            f"-- ratio {ratio:.2f}x. The sleeve cannot be net-positive while this holds, "
            "regardless of how good the signal is. This is the single most direct drag on CAGR."))


def check_close_retry_loop(defects) -> None:
    """A carry that keeps failing to close is a CHURN ENGINE, not a stuck position.

    ORIGIN (2026-07-28 incident, and the reason this is mechanical rather than a lesson): every
    futures hedge had been force-closed out from under the book, so the close path's reduceOnly
    cover had nothing to reduce. The venue rejects that order, `_filled` returns False, and the
    pair stayed tracked for a retry -- every tick, forever -- while `_reconcile` rebuilt BOTH legs
    in front of each attempt. The book round-tripped its entire notional through market orders
    every 600s: 11,136 venue commission events against 251 logged round-trips, $1,456 of fees in
    48h against $113 of LIFETIME funding harvest.

    §40 (`check_fee_carry_ratio`) DID fire on this, ~27h before it was diagnosed -- but it reports
    a SYMPTOM ("fees are 63x the harvest"), which is consistent with a dozen causes and cost a
    full diagnosis to localise. This check reports the FINGERPRINT: the same symbol failing to
    close on repeat. Detection was never the gap; NAMING THE CAUSE was.

    Deliberately reads the published feed rather than re-deriving state: CLOSE-FAIL is exactly
    what the executor itself says it did, so the check cannot disagree with the book about
    reality (institutional_knowledge: a monitor that sources ground truth from the failing
    component cannot see the failure -- here the feed is the executor's own testimony, and a
    stale feed is caught by the separate liveness checks).
    """
    feed = ROOT / "web/cashcarry_live.json"
    if not feed.exists():
        return
    try:
        acts = json.loads(feed.read_text("utf-8")).get("last_actions") or []
    except Exception:
        return
    failing = sorted({a.split()[1].rstrip(":") for a in acts
                      if isinstance(a, str) and a.startswith("CLOSE-FAIL")})
    if not failing:
        return
    rebuilding = sorted({a.split()[1] for a in acts if isinstance(a, str)
                         and (a.startswith("re-hedge") or a.startswith("spot-rehedge"))})
    both = [s for s in failing if s in rebuilding]
    if both:
        defects.append(("carry-churn-loop",
                        f"CHURN LOOP: {', '.join(both)} are failing to CLOSE while the reconciler "
                        f"REBUILDS the same legs in the same tick -- the book is round-tripping "
                        f"its notional every interval and paying fees both ways for zero harvest. "
                        f"This is unbounded: it does not self-heal and it has no position limit. "
                        f"Stop the executor or clear the cause NOW, do not wait for the fee ratio "
                        f"to report it."))
    else:
        defects.append(("carry-close-failing",
                        f"close failing on {', '.join(failing)} -- each retry pays fees for a "
                        f"position that never retires. Verify the leg is not ALREADY flat (a "
                        f"reduceOnly cover against a flat position is rejected, which reads as "
                        f"'unfilled' forever) before treating this as a transient venue error."))


def check_book_absorbing_state(defects) -> None:
    """A book whose risk rail can never release it is DEAD, not safe -- and reads as healthy.

    ORIGIN (2026-07-29, found by hand during the STEP-0 integrity watch; encoded here under the
    recursion rule so it is never a hand-probe again). The carry book sat at n_carries=0 /
    deployed_notional=0 with a fresh heartbeat and NO alarm anywhere in the sweep, because every
    existing check reads a flat book as a healthy one: the bleed alarm needs non-funding PnL, §40
    needs >$5 of funding to divide by, and `check_close_retry_loop` needs CLOSE-FAIL actions. A
    book doing NOTHING trips none of them.

    What was actually happening: the 07-25→07-28 churn loop billed $1,750.65 of commission against
    $113.04 of lifetime funding, driving combined equity to -37.2% from inception. `risk_controls`
    flattens at -35% measured against a FIXED `start_equity`, and its response -- flatten -- removes
    the only mechanism (carrying) by which equity could ever climb back. So the verdict is
    self-sustaining: flat forever, evidence clock stopped, and the forward track record the live
    gate sizes on silently stopped accruing.

    That absorbing property is CORRECT for real capital: a book that lost a third of its equity
    must stop and get human review, never auto-resume. The defect is not the rail, it is that
    NOTHING SAID SO -- the rail's design assumes a human re-baselines it, and no organ ever
    escalated that a human decision was owed. This check is that escalation.

    Deliberately recomputes the verdict through the SAME pure function the executor calls, from
    the same state file, rather than re-deriving a threshold here: a monitor that keeps its own
    copy of the rule eventually disagrees with the book about the book's own state. Reads that
    fail leave the check SILENT -- an unmeasurable equity must never manufacture a defect (the
    07-26 "no measurement beats a confident wrong one" lesson).

    NOT a rail change and must never become one: re-baselining a ruin rail after it fired is
    Tier-3 (principal-only). This check reports; the principal decides.
    """
    feed = ROOT / "web/cashcarry_live.json"
    st_p = ROOT / "data/cashcarry_positions.json"
    if not (feed.exists() and st_p.exists()):
        return
    try:
        from libs.risk import risk_controls
        fd = json.loads(feed.read_text("utf-8"))
        st = json.loads(st_p.read_text("utf-8"))
    except Exception:
        return
    fut_leg = fd.get("fut_leg_net")
    if fut_leg is None:                       # futures equity unmeasured this tick -> stay silent
        return
    try:
        start = float(st["start_futures_equity"])
        fut_eq = start + float(fut_leg)
        # Flat book: unrealised spot is 0, so the spot side is exactly the banked realised PnL.
        eq_c = fut_eq + float(st.get("realized_spot_pnl", 0.0))
        peak = float(st.get("peak_combined_equity", start))
        gross = float(fd.get("deployed_notional") or 0.0)
        n_carries = int(fd.get("n_carries") or 0)
    except (KeyError, TypeError, ValueError):
        return
    verdict = risk_controls.evaluate(eq_c, start, peak, gross, ruin_cap_lev=8.0)
    if verdict.action != "flatten":
        return
    if n_carries > 0 or gross > 0:
        # Flatten WITH inventory is the rail doing its job mid-unwind -- transient, not absorbing.
        return
    defects.append((
        "book-absorbing-state",
        f"BOOK DEAD, NOT IDLE: the carry book is flat (n_carries=0) while risk_controls still "
        f"returns FLATTEN -- {'; '.join(verdict.reasons)}. A flat book earns no funding, so equity "
        f"cannot rise, so the verdict never clears: this state is ABSORBING and the forward track "
        f"record the live gate sizes on has STOPPED ACCRUING (combined equity ${eq_c:,.2f} vs "
        f"${start:,.2f} inception). Every other check reads this as a healthy flat book. "
        f"Re-baselining a fired ruin rail is TIER-3 (principal-only) -- do NOT self-clear it; "
        f"page the principal with the attribution of what caused the drawdown."))


DOCTRINE = ROOT / "ops/principal_doctrine.txt"

# Duties that must reach EVERY organ, not just the brain. The list is explicit rather than
# inferred: a heuristic would either miss a renamed duty or nag about the many duties that are
# CORRECTLY brain-only (audit coverage, red-team panels, risk-path depth, the independence gate).
_UNIVERSAL = ("PROACTIVE BATTERY DUTY", "NO-ORPHANED-RECOMMENDATION LAW", "NOVELTY GATE",
              "TARGET/HORIZON SWEEP DUTY", "RESEARCH-MEMORY DUTY", "FREE-FIRST DATA PROTOCOL",
              "BLIND-SPOT ORIGIN DUTY", "FINDING LIFECYCLE DUTY", "SELF-INTERROGATION DUTY",
              "TWO-STAGE DISCOVERY LAW", "SCREEN-ON-DISCOVERY DUTY", "MINING-NEVER-REGRESSES LAW",
              "NO-CEILING AXIOM", "FREE-FRONTIER AXIOM", "DATA-UTILIZATION")


def check_universal_doctrine(defects) -> None:
    """Every universal duty must live in the SHARED doctrine, and every organ must inject it.

    ORIGIN (2026-07-26): the doctrine ordered every digger to screen new axes (SCREEN-ON-DISCOVERY)
    while the rules that keep screening honest -- novelty gate, target/horizon trial accounting,
    research-memory -- lived only in the brain's own prompt. Diggers were commanded to do the
    dangerous half of the job without the discipline that makes it safe. A universal law parked in
    one organ's prompt is not a law, it is a local habit.
    """
    if not DOCTRINE.exists():
        defects.append(("doctrine-missing",
                        "ops/principal_doctrine.txt is gone -- every organ injects it as its "
                        "system prompt, so the desk is running with no standing law at all"))
        return
    txt = DOCTRINE.read_text("utf-8", errors="ignore")
    missing = [d for d in _UNIVERSAL if d not in txt]
    if missing:
        defects.append(("doctrine-universal-missing",
                        f"universal duties absent from the shared doctrine: {', '.join(missing)}. "
                        "These bind every organ; if one lives only in a single organ's prompt, "
                        "every other organ operates without it -- which is how diggers came to be "
                        "ordered to screen axes with no novelty gate or trial accounting."))
    # A duty is only universal if every reasoning organ actually injects the doctrine.
    naked = []
    for sh in sorted(ROOT.glob("ops/run_*.sh")):
        body = sh.read_text("utf-8", errors="ignore")
        if re.search(r"claude .*(-p|--append-system-prompt)", body) and "_DOCTRINE" not in body:
            naked.append(sh.name)
    if naked:
        defects.append(("doctrine-not-injected",
                        f"reasoning organs invoking claude WITHOUT the doctrine: {naked}. "
                        "An organ that does not inject it is exempt from every standing law the "
                        "desk has, silently."))


# Checks DEFINED BELOW the CHECKS literal must be registered here -- appending them up there is a
# NameError, which is exactly how four of them ended up dead. Keep the order explicit (the list is
# the run order); `check_registry_complete` below is what makes a future omission impossible.
CHECKS += [("fee-carry-ratio", check_fee_carry_ratio),
           ("close-retry-loop", check_close_retry_loop),
           ("paid-target-registry", check_paid_target_registry),
           ("holdings-ratchet", check_holdings_never_shrink),
           ("book-absorbing-state", check_book_absorbing_state),
           ("universal-doctrine", check_universal_doctrine)]

#: Module-level `check_*` functions that are deliberately NOT swept. Empty by design: an exemption
#: must be argued in writing here, never assumed by silence.
_CHECKS_EXEMPT: set[str] = set()


def check_registry_complete(defects) -> None:
    """A written check that is never registered is a law the desk believes it is enforcing.

    Origin (2026-07-26): `check_fee_carry_ratio` (§40 fee ratchet), `check_paid_target_registry`
    and `check_holdings_never_shrink` (§39) and `check_universal_doctrine` were all authored,
    committed, and NEVER added to CHECKS -- four consecutive charters shipped with zero
    enforcement. The cause is structural, not careless: CHECKS is a literal defined ABOVE most of
    the checks, so the natural "append next to the others" edit raises NameError at import and the
    registration quietly gets dropped. Nothing mechanical looked, because the checker that would
    have looked was itself one of the unregistered ones.

    This closes the class: every module-level `check_*` callable must be in CHECKS or argued into
    `_CHECKS_EXEMPT`. Silence is no longer a way to ship a dead law.
    """
    registered = {fn.__name__ for _, fn in CHECKS}
    orphans = sorted(
        name for name, obj in globals().items()
        if name.startswith("check_") and callable(obj)
        and name not in registered and name not in _CHECKS_EXEMPT)
    if orphans:
        defects.append((
            "check-unregistered",
            f"{len(orphans)} check(s) authored but NEVER RUN -- the law they enforce is inert "
            f"while the desk believes it is enforced: {', '.join(orphans)}. Add each to CHECKS "
            "(register BELOW its definition) or justify it in _CHECKS_EXEMPT."))


CHECKS += [("check-registry", check_registry_complete)]


CONSTITUTION = ROOT / "docs/CONSTITUTION.md"
CONST_REVIEW = ROOT / "docs/research/constitution_review.md"


def check_constitution(defects) -> None:
    """The constitution governs (installed 2026-07-29): present, injected, and reviewed.

    L2.8 makes stability the default review outcome -- but an UNREVIEWED constitution is not
    stable, it is unexamined. The quarterly cadence is enforced as an age fence rather than a new
    scheduler: the defect fires, the brain runs the review (default verdict: unchanged, stated
    explicitly), writes the artifact, the fence goes green. No second orchestrator.
    """
    if not CONSTITUTION.exists() or CONSTITUTION.stat().st_size < 8000:
        defects.append(("constitution-missing",
                        "docs/CONSTITUTION.md is missing or gutted -- the desk's governing "
                        "operating system is not installed; every organ is running on doctrine "
                        "fragments with no Level-1 objective hierarchy"))
        return
    doct = (ROOT / "ops/principal_doctrine.txt").read_text("utf-8", errors="ignore")
    if "docs/CONSTITUTION.md" not in doct or "E[log(W_T)]" not in doct:
        defects.append(("constitution-not-injected",
                        "the doctrine no longer declares docs/CONSTITUTION.md governing (or lost "
                        "the L1.1 objective) -- organs are being briefed without the "
                        "constitutional core, which voids universal enforcement"))
    if CONST_REVIEW.exists():
        age_d = (NOW - CONST_REVIEW.stat().st_mtime) / 86400.0
        if age_d > 92:
            defects.append(("constitution-review-overdue",
                            f"L4 quarterly constitutional review is {age_d:.0f}d old (>92d). Run "
                            "it per L2.8: rank candidate changes by ERV, default outcome "
                            "STABILITY stated explicitly, write the verdict to "
                            "docs/research/constitution_review.md."))
    elif (NOW - CONSTITUTION.stat().st_mtime) / 86400.0 > 92:
        defects.append(("constitution-review-overdue",
                        "no constitutional review artifact exists and the constitution is >92d "
                        "old -- L4 requires the quarterly review; write "
                        "docs/research/constitution_review.md with the ERV-ranked verdict."))


CHECKS += [("constitution", check_constitution)]   # registered BELOW its definition


def main() -> None:
    defects: list[tuple[str, str]] = []
    for label, fn in CHECKS:
        _fenced(fn, defects, label)

    acks = _j(ACKS, {})
    live, acked = [], []
    for did, msg in defects:
        a = acks.get(did)
        if a and a.get("until", "") > datetime.now(tz=UTC).isoformat():
            acked.append((did, a.get("reason", "")))
        else:
            live.append((did, msg))

    prev = _j(REPORT, {})
    first_seen = prev.get("first_seen", {})
    now_iso = datetime.now(tz=UTC).isoformat()
    first_seen = {d: t for d, t in first_seen.items() if d in {x for x, _ in live}}
    for did, _ in live:
        first_seen.setdefault(did, now_iso)
    REPORT.write_text(json.dumps(
        {"ran": now_iso, "live": [{"id": d, "msg": m} for d, m in live],
         "acked": [d for d, _ in acked], "first_seen": first_seen}, indent=1), "utf-8")

    print(f"MAX-AUDIT {now_iso[:16]}  live defects: {len(live)}  acked: {len(acked)}")
    for did, msg in live:
        age_h = (datetime.now(tz=UTC) - datetime.fromisoformat(first_seen[did])
                 ).total_seconds() / 3600
        print(f"  [{age_h:>5.1f}h] {did}: {msg}")
    for did, reason in acked:
        print(f"  [ acked] {did}: {reason}")

    overdue = [(d, m) for d, m in live
               if (datetime.now(tz=UTC) - datetime.fromisoformat(first_seen[d])
                   ).total_seconds() / 3600 > ESCALATE_H]
    # DELIVERY FIX (2026-07-24 external audit): the pager reads only PRINCIPAL_ACTION line 1.
    # The old code appended the escalation BELOW existing content (a stale RESOLVED line stayed
    # at line 1) AND only wrote once ever (one-shot latch), so 24 live defects never paged. Now
    # the escalation OWNS line 1 whenever defects are overdue, and is CLEARED when none are --
    # so the pager surfaces the truth and stops crying resolved-wolf.
    # URGENT CARVE-OUT (2026-07-28). Owning line 1 unconditionally fixed the stale-RESOLVED bug by
    # creating the opposite one: with defects essentially always overdue, the ROUTINE 48h sweep
    # permanently outranked every EVENT-DRIVEN page, so a Tier-3 ask the CRO cannot act on alone
    # (a dead-man reset) was delivered as "20 below-max states". A standing sweep is never more
    # urgent than a blocker only the principal can clear. A page marked `URGENT <ISO-date>:` keeps
    # line 1 while it is FRESH -- the date is mandatory precisely so this cannot rot back into the
    # stale line 1 the 07-24 fix removed; past _URGENT_TTL_D it is demoted automatically.
    _MARK = "MAX-AUDIT ESCALATION"
    _URGENT_TTL_D = 7.0
    existing = PA.read_text("utf-8") if PA.exists() else ""
    # DATA LOSS FIX (2026-07-28). This was `existing.split(_MARK)[0]`, which keeps only the text
    # BEFORE the marker. Once the escalation owned line 1 -- i.e. every run after the first -- that
    # expression returned "" and SILENTLY DELETED the entire human-written page below it. Every
    # PRINCIPAL_ACTION page the CRO wrote was destroyed by the next sweep, on the desk's only
    # human-escalation channel, from 2026-07-24 until this fix. Found by re-reading the file after
    # writing it rather than trusting the write. Strip the escalation BLOCK ONLY: its header line
    # plus the indented bullets that belong to it; every other line is somebody's message and is
    # preserved.
    kept, skipping = [], False
    for ln in existing.splitlines():
        if ln.startswith(_MARK):
            skipping = True
            continue
        if skipping and (ln.startswith("  - ") or not ln.strip()):
            continue                       # bullets + the blank line that trails the block
        skipping = False
        kept.append(ln)
    body = "\n".join(kept).strip()
    # POSITION FIX (2026-07-30). This checked only `body.startswith("URGENT ")`, so the carve-out
    # required the URGENT block to be the FIRST paragraph. On 07-30 an unrelated PURCHASE DECISION
    # notice was prepended above it, which silently disabled the carve-out: the routine 48h sweep
    # retook line 1 and the principal was paged "24 below-max state(s)" while TWO Tier-3 rulings the
    # whole discovery pipeline is blocked on (dead carry book, pbo/rc gate flip) sat below the fold.
    # Third recurrence of one family -- 07-24 stale line 1, 07-28 silent deletion, now demotion by a
    # neighbour's insert -- because the carve-out was POSITIONAL and no writer owns a position. Find
    # a fresh URGENT block ANYWHERE in the body and hoist it; reordering only, nothing dropped.
    # FORMAT-FRAGILITY FIX (2026-07-31, FOURTH recurrence of the family: 07-24 stale line 1,
    # 07-28 silent deletion, 07-30 demotion-by-neighbour, now demotion-by-ANNOTATION). The stamp
    # parse was `split("URGENT ",1)[1].split(":",1)[0]` -> fromisoformat, so the moment a human
    # annotated the header ("URGENT 2026-07-29 (updated 07-31): ...") recognition threw, was
    # suppressed, and the routine sweep silently retook line 1 from two Tier-3 asks -- caught
    # live by test_max_audit_run_preserves_a_written_page. Recognition now keys on the first
    # ISO-DATE TOKEN anywhere in the paragraph head, so annotations cannot disarm it. And hoist
    # the RUN of all fresh URGENT paragraphs, not just the first -- with two pending Tier-3
    # asks, "one above the fold, one buried" is the same failure at half size.
    urgents: list[tuple[str, str]] = []       # (iso_date, para)
    paras = body.split("\n\n")
    remaining: list[str] = []
    for para in paras:
        hoisted = False
        if para.startswith("URGENT"):
            m_date = re.search(r"(\d{4}-\d{2}-\d{2})", para[:80])
            if m_date:
                with contextlib.suppress(Exception):
                    age_d = (NOW - datetime.fromisoformat(m_date.group(1))
                             .replace(tzinfo=UTC).timestamp()) / 86400.0
                    if age_d <= _URGENT_TTL_D:
                        urgents.append((m_date.group(1), para))
                        hoisted = True
        if not hoisted:
            remaining.append(para)
    body = "\n\n".join(remaining).strip()
    # NEWEST URGENT OWNS LINE 1 (2026-07-31, fifth member of the demotion family: a fresh
    # book-frozen ask landed BELOW two older URGENTs because hoisting preserved body order).
    # Sort is by stamp desc and stable, so same-day blocks keep their written order.
    urgents.sort(key=lambda t: t[0], reverse=True)
    urgent = "\n\n".join(p for _, p in urgents)
    if overdue:
        head = (f"{_MARK}: {len(overdue)} below-max state(s) >48h unfixed/unacked -- "
                + "; ".join(f"{d}" for d, _ in overdue[:6])
                + (" ..." if len(overdue) > 6 else "") + "\n"
                + "".join(f"  - {d}: {m}\n" for d, m in overdue[:8]))
        # fresh urgent pages keep the top; otherwise the escalation owns line 1 as before
        PA.write_text((urgent + "\n\n" if urgent else "") + head + "\n" + body, "utf-8")
        print(f"ESCALATED to principal page (line {'2' if urgent else '1'}): "
              f"{len(overdue)} defect(s) >48h" + (" -- behind a fresh URGENT page" if urgent else ""))
    elif existing != body + ("\n" if body else ""):
        PA.write_text(body + ("\n" if body else ""), "utf-8")  # cleared: drop stale escalation
        print("escalation cleared: no overdue defects")


if __name__ == "__main__":
    main()

```

### scripts/mine_gate.py
```python
#!/usr/bin/env python3
"""§33 conversion PRIORITY directive -- RECOMPUTED from the docs, never read from a flag.

MINING IS NEVER THROTTLED (principal 2026-07-25). This never blocks a dig; it tells the dig
what to do FIRST. Unprocessed data is unrealized option value and living-web sources decay,
so acquisition is never cut to meet extraction -- extraction is scaled up to meet acquisition.
The backlog therefore preempts the dig's PRIORITY, not its EXISTENCE.

A gate that is a file is a gate anything can delete: `rm data/mining_suspended` would have
restored mining without converting a thing, which makes the whole law advisory again. So the
diggers no longer TRUST a flag -- they RUN this, and it derives the backlog from the same source
of truth the daily sweep uses. Deleting state cannot help, because there is no state to delete;
the only way to open the gate is to actually dispose of the findings, and the only way to disable
it is to edit tracked code, which shows up in a diff and in review.

    python3 scripts/mine_gate.py            # ALWAYS exit 0; prints the conversion PRIORITY block
    python3 scripts/mine_gate.py --explain  # always exit 0; print the full §33 block

FAIL-OPEN, LOUDLY. If this script itself breaks, it exits 0 (mining proceeds) and prints a
GATE-ERROR line. The asymmetry is deliberate and costed: a day of over-mining is cheap and
recoverable, while a bug that silently freezes every digger for a week is a self-inflicted outage
of the desk's entire research intake. The failure is not swallowed -- `max_audit.check_mine_gate`
fires a defect whenever this script cannot run, so a broken gate surfaces within one sweep instead
of hiding behind either outcome.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def evaluate() -> tuple[bool, str]:
    """Return (suspended, reason). Recomputes from the docs -- reads no gate file."""
    from datetime import UTC, datetime

    from scripts.max_audit import _mine_backing, _mine_items

    from libs.research.mine_conversion import conversion_report

    items = _mine_items()
    if not items:
        return False, "no carded finds -- nothing owed"
    rep = conversion_report(items, as_of=datetime.now(UTC).date(),
                            backing=_mine_backing(), root=ROOT)
    return rep.suspend_mining, rep.verdict


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--explain", action="store_true",
                    help="print the verdict but always exit 0 (for humans, not for the shells)")
    # --explain is retained for CLI compatibility but no longer branches: BOTH paths exit 0
    # now that mining is never throttled, so the parsed value is deliberately unused.
    ap.parse_args()
    try:
        suspended, reason = evaluate()
    except Exception as exc:
        print(f"[§33] GATE-ERROR {type(exc).__name__}: {exc} -- failing OPEN; "
              "max_audit.check_mine_gate will raise this as a defect")
        return 0
    # Label matches the law: the backlog steers PRIORITY, it never suspends mining.
    print(f"[§33] {'CONVERT-FIRST' if suspended else 'BACKLOG-CLEAR'} -- {reason}")
    # ALWAYS 0: mining is never throttled (principal 2026-07-25). The backlog steers the
    # dig's PRIORITY, never its existence -- unprocessed data is unrealized option value and
    # living-web sources decay, so acquisition is never cut to meet extraction. `suspended`
    # is retained purely as a reporting signal for the max_audit mine-conversion defects.
    _ = suspended
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

```

### scripts/run_live_demo.py
```python
"""LIVE DEMO TRADING ENTRYPOINT — connect MT5, generate signals, place demo trades.

This is the only script that does all three on a live MT5 DEMO account:
  1. Connects to the MetaTrader5 terminal (aborts unless the account is a DEMO account).
  2. Pulls real bars and generates signals via the pre-registered strategy layer
     (app.signal_builder.build_live_signals) -> Stage 13.5 -> Stage 14 -> risk gate.
  3. Places demo trades through the execution venue:
       --venue ea    : via the hardened MT5 Execution EA (QuantPlatformExecutor.mq5, must be
                       attached to a chart). Python -> file queue -> EA -> demo account.  [default]
       --venue paper : via the in-process PaperBroker (no real orders) — for a dry run.

It loops every --interval seconds for --minutes, then stops. NO live (real-money) trading: the
script refuses any account whose trade_mode is not DEMO.

Usage (from the project root, venv active):
    python scripts/run_live_demo.py --minutes 30 --interval 60 --venue ea \
        --symbols EURUSD,XAUUSD --comm-dir "<MT5 common>/Files/quant_ea"
"""

from __future__ import annotations

import argparse
import time
from datetime import UTC, datetime
from pathlib import Path

from migrations import MIGRATIONS

from app.demo_runner import DemoRunner
from app.feed import MT5Feed
from app.mt5_adapter import MT5Adapter
from app.signal_builder import build_live_signals
from libs.execution.broker import BrokerGateway
from libs.execution.ea_bridge import EABridge
from libs.execution.paper_broker import PaperBroker
from libs.store.connection import Database
from libs.store.migrations import run_migrations


def _make_broker(venue: str, comm_dir: str) -> BrokerGateway:
    if venue == "ea":
        return EABridge(Path(comm_dir))  # Python -> file queue -> the MT5 Execution EA
    if venue == "paper":
        return PaperBroker()
    raise SystemExit(f"unknown venue {venue!r} (use 'ea' or 'paper')")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--symbols", default="EURUSD,XAUUSD")
    parser.add_argument("--minutes", type=float, default=30.0)
    parser.add_argument("--interval", type=float, default=60.0)
    parser.add_argument("--venue", choices=("ea", "paper"), default="ea")
    parser.add_argument("--comm-dir", default="data/quant_ea")
    parser.add_argument("--db", default="data/sor_live_demo.sqlite")
    parser.add_argument("--capital", type=float, default=100_000.0)
    parser.add_argument("--timeframe", default="H1")
    args = parser.parse_args()
    symbols = [s.strip() for s in args.symbols.split(",") if s.strip()]

    # 1) Connect to MT5 and HARD-GATE on a demo account.
    adapter = MT5Adapter()
    acct = adapter.account_info()
    if acct.login and getattr(acct, "currency", None) is None:
        adapter.shutdown()
        raise SystemExit("could not read MT5 account info")
    mode = _trade_mode(adapter)
    if mode != 0:
        adapter.shutdown()
        raise SystemExit(f"refusing to run: account trade_mode={mode} is not DEMO (0)")
    print(f"connected: login={acct.login} currency={acct.currency} trade_mode=DEMO")

    # 2) Wire the live feed (real bars -> pre-registered signals) and the venue.
    feed = MT5Feed(adapter, symbols, signal_builder=build_live_signals, timeframe=args.timeframe)
    broker = _make_broker(args.venue, args.comm_dir)
    db = Database(Path(args.db))
    run_migrations(db, MIGRATIONS)
    runner = DemoRunner(db, capital=args.capital, broker=broker)

    # 3) Live loop: poll -> full pipeline -> place demo trades -> heartbeat -> sleep.
    deadline = time.monotonic() + args.minutes * 60.0
    totals = [0, 0, 0, 0, 0]
    try:
        while time.monotonic() < deadline:
            if isinstance(broker, EABridge):
                broker.write_heartbeat()
            observations = feed.poll()
            counts = runner.process_batch(observations, tag=datetime.now(UTC).strftime("%H%M%S"))
            totals = [t + c for t, c in zip(totals, counts, strict=True)]
            print(f"[{datetime.now(UTC):%H:%M:%S}] signals={counts[0]} alloc={counts[1]} "
                  f"submitted={counts[2]} filled={counts[3]} rejected={counts[4]}")
            time.sleep(args.interval)
    finally:
        adapter.shutdown()
        db.close()

    print(f"\nLIVE DEMO SESSION DONE: signals={totals[0]} allocations={totals[1]} "
          f"orders_submitted={totals[2]} orders_filled={totals[3]} risk_rejections={totals[4]}")


def _trade_mode(adapter: MT5Adapter) -> int:
    import MetaTrader5 as mt5

    info = mt5.account_info()
    return int(info.trade_mode) if info is not None else -1


if __name__ == "__main__":
    main()

```

### scripts/source_backlog_next.py
```python
#!/usr/bin/env python3
"""Print the next source(s) to VERIFY this cycle -- clears the existing catalogue, never
generates more.

The bottleneck in the desk's data-hunting pipeline was never generation (prospector/litminer
already catalogue faster than anything gets verified) -- it is verification: reading the actual
docs/ToS and testing the actual endpoint (the Baidu-vs-NAVER distinction this session took real
reading, not a prompt). This script does exactly the mechanical half of that: parse the existing
watchlist, exclude anything already resolved ("if not already in system"), and surface a bounded
batch to work on THIS cycle. The actual verification (read the docs, hit the endpoint, grade it) is
a cycle-level research task, not something this script does for you.

Usage: source_backlog_next.py [--watchlist docs/research/data_axis_watchlist.md] [--limit 3]
"""
from __future__ import annotations

import argparse
from pathlib import Path

from libs.research.source_backlog import backlog_from_file


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--watchlist", default="docs/research/data_axis_watchlist.md")
    # 0 = UNBOUNDED (default, principal 2026-07-25: no throttles on research). Conversion
    # must always maximise and exhaust; a per-cycle cap on how many findings can even be
    # SURFACED throttles the conversion half of the objective before work begins.
    p.add_argument("--limit", type=int, default=0)
    a = p.parse_args()

    path = Path(a.watchlist)
    if not path.exists():
        print(f"no watchlist at {path} -- nothing to pick from")
        return
    rep = backlog_from_file(path, limit=a.limit)
    print(f"SOURCE BACKLOG: {rep.n_total} catalogued, {rep.n_resolved} resolved (excluded), "
          f"{rep.n_verification_pending} pending verification, "
          f"{rep.n_legitimacy_pending} pending a legitimacy decision")
    print(f"  {rep.verdict}")
    if rep.next_verification:
        print("  VERIFY this cycle (technical check -- docs + endpoint):")
        for name in rep.next_verification:
            print(f"    - {name}")
    if rep.next_legitimacy:
        print("  DECIDE this cycle (policy/legal, not a technical test):")
        for name in rep.next_legitimacy:
            print(f"    - {name}")


if __name__ == "__main__":
    main()

```
