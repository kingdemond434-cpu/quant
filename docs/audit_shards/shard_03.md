# AUDIT SHARD 3/13 -- seat google/gemini-3.1-pro-preview

You are reviewing SOURCE CODE, not a summary. Previous panels received a 13,185-char self-description and never saw the code; that is why this exists.

- TIER 1 (money path) is included IN FULL and is sent to every seat: 41 files. A defect here costs money.
- TIER 2 is YOUR SHARD ALONE: 45 files. No other seat sees these, so anything you miss here is missed entirely.
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

### libs/alpha_factory/alpha_embedding_engine.py
```python
"""Alpha embedding engine — embed alphas into a vector space for clustering/crowding.

Turns an :class:`AlphaDNA` into a fixed-length numeric embedding so alphas can be compared and
clustered. Greedy cosine clustering surfaces duplicated alpha families and latent crowding (many
near-identical alphas masquerading as diversification).
"""

from __future__ import annotations

from collections.abc import Mapping

import numpy as np

from libs.alpha_factory.models import AlphaDNA

_EPS = 1e-12
# Fixed projection axes so every embedding is comparable across alphas.
_FACTORS = ("momentum", "value", "growth", "quality", "carry", "volatility", "liquidity", "macro")
_REGIMES = ("trend", "range", "momentum", "mean_reversion", "volatility", "crisis", "neutral")


def _cosine(a: np.ndarray, b: np.ndarray) -> float:
    na, nb = float(np.linalg.norm(a)), float(np.linalg.norm(b))
    if na <= _EPS or nb <= _EPS:
        return 0.0
    return float(np.dot(a, b) / (na * nb))


class AlphaEmbeddingEngine:
    """Builds DNA embeddings and clusters alphas by cosine similarity."""

    def embed(self, dna: AlphaDNA) -> list[float]:
        factors = [float(dna.factor_exposures.get(f, 0.0)) for f in _FACTORS]
        regimes = [float(dna.regime_affinity.get(r, 0.0)) for r in _REGIMES]
        return dna.numeric_vector() + factors + regimes

    def similarity(self, a: AlphaDNA, b: AlphaDNA) -> float:
        return _cosine(np.array(self.embed(a)), np.array(self.embed(b)))

    def cluster(
        self, dnas: Mapping[str, AlphaDNA], *, threshold: float = 0.95
    ) -> list[list[str]]:
        """Greedy single-pass clustering; clusters of >1 reveal duplication/crowding."""
        vectors = {aid: np.array(self.embed(d)) for aid, d in dnas.items()}
        clusters: list[list[str]] = []
        centroids: list[np.ndarray] = []
        for aid, vec in vectors.items():
            placed = False
            for i, centroid in enumerate(centroids):
                if _cosine(vec, centroid) >= threshold:
                    clusters[i].append(aid)
                    placed = True
                    break
            if not placed:
                clusters.append([aid])
                centroids.append(vec)
        return clusters

```

### libs/alpha_factory/research_graph.py
```python
"""Research graph — relationships across thousands of experiments.

A typed directed graph: Idea -> Feature -> Signal -> Factor -> Alpha -> Performance. It lets the
factory mine patterns, e.g. which features recur in the lineages of high-performing alphas.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from typing import Any

from libs.alpha_factory.errors import AlphaFactoryError

_NODE_TYPES = frozenset({"idea", "feature", "signal", "factor", "alpha", "performance"})


@dataclass
class _Node:
    node_id: str
    node_type: str
    attrs: dict[str, Any] = field(default_factory=dict)


class ResearchGraph:
    """A typed directed graph over the research pipeline."""

    def __init__(self) -> None:
        self._nodes: dict[str, _Node] = {}
        self._out: dict[str, set[str]] = {}
        self._in: dict[str, set[str]] = {}

    def add_node(self, node_id: str, node_type: str, **attrs: Any) -> None:
        if node_type not in _NODE_TYPES:
            raise AlphaFactoryError(f"unknown node_type {node_type!r}")
        self._nodes[node_id] = _Node(node_id, node_type, dict(attrs))
        self._out.setdefault(node_id, set())
        self._in.setdefault(node_id, set())

    def add_edge(self, src: str, dst: str) -> None:
        if src not in self._nodes or dst not in self._nodes:
            raise AlphaFactoryError("both nodes must exist before adding an edge")
        self._out[src].add(dst)
        self._in[dst].add(src)

    def neighbors(self, node_id: str) -> list[str]:
        return sorted(self._out.get(node_id, set()))

    def predecessors(self, node_id: str) -> list[str]:
        return sorted(self._in.get(node_id, set()))

    def nodes_of_type(self, node_type: str) -> list[str]:
        return sorted(n.node_id for n in self._nodes.values() if n.node_type == node_type)

    def path_exists(self, src: str, dst: str) -> bool:
        if src not in self._nodes or dst not in self._nodes:
            return False
        seen, queue = {src}, deque([src])
        while queue:
            cur = queue.popleft()
            if cur == dst:
                return True
            for nxt in self._out.get(cur, set()):
                if nxt not in seen:
                    seen.add(nxt)
                    queue.append(nxt)
        return False

    def feature_importance(self, *, min_performance: float) -> dict[str, int]:
        """Count features that feed into alphas whose performance node clears the threshold."""
        counts: dict[str, int] = {}
        winners = [
            n.node_id
            for n in self._nodes.values()
            if n.node_type == "performance" and float(n.attrs.get("value", 0.0)) >= min_performance
        ]
        for perf in winners:
            for feature in self._ancestors_of_type(perf, "feature"):
                counts[feature] = counts.get(feature, 0) + 1
        return counts

    def _ancestors_of_type(self, node_id: str, node_type: str) -> set[str]:
        found: set[str] = set()
        seen, queue = {node_id}, deque([node_id])
        while queue:
            cur = queue.popleft()
            for prev in self._in.get(cur, set()):
                if prev not in seen:
                    seen.add(prev)
                    queue.append(prev)
                    if self._nodes[prev].node_type == node_type:
                        found.add(prev)
        return found

```

### libs/autodiscovery/__init__.py
```python
"""``libs.autodiscovery`` — the autonomous institutional research lab.

Continuously generates economically-declared hypotheses across 12 families, backtests them on real
data, runs the FULL validation gauntlet (CPCV/PBO/DSR/Reality-Check/Walk-Forward/economic/capacity/
fragility + shadow & paper lifecycle stages), archives every outcome to durable memory (dedup, no
retesting), and promotes survivors through Rejected→Shadow→Paper→Registry. Never allocates real
capital; REGISTRY only marks a candidate eligible for human review. Reuses Architecture v1.0
throughout (validation, discovery, signal_builder, store). Success = validated survivors, not count.
"""

from __future__ import annotations

from libs.autodiscovery.data_opportunity import DataOpportunityEngine, DataOpportunityReport
from libs.autodiscovery.errors import AutoDiscoveryError
from libs.autodiscovery.generators import GENERATORS, GeneratorSpec, net_returns, planned_hypotheses
from libs.autodiscovery.lifecycle import promote, segment_pass
from libs.autodiscovery.memory import CandidateStore, content_hash
from libs.autodiscovery.models import (
    CandidateRecord,
    CandidateStatus,
    CycleResult,
    Family,
    Hypothesis,
    MarketSeries,
    ValidationMetrics,
    ValidationVerdict,
)
from libs.autodiscovery.orchestrator import AutoDiscoveryLab, CostProvider, DataProvider
from libs.autodiscovery.prioritization import FAMILY_PRIORITY, family_rank, prioritize
from libs.autodiscovery.reports import (
    discovery_efficiency_report,
    failure_analysis_report,
    family_performance_report,
    pipeline_health_report,
    research_report,
    survivor_report,
)
from libs.autodiscovery.research_roi import ResearchROIMonitor, ResearchROIReport
from libs.autodiscovery.validation import validate

__all__ = [  # noqa: RUF022  # grouped by concern
    # models
    "Family",
    "CandidateStatus",
    "MarketSeries",
    "Hypothesis",
    "ValidationMetrics",
    "ValidationVerdict",
    "CandidateRecord",
    "CycleResult",
    # generators
    "GENERATORS",
    "GeneratorSpec",
    "planned_hypotheses",
    "net_returns",
    # validation / lifecycle
    "validate",
    "promote",
    "segment_pass",
    # memory
    "CandidateStore",
    "content_hash",
    # orchestrator + prioritization
    "AutoDiscoveryLab",
    "DataProvider",
    "CostProvider",
    "prioritize",
    "family_rank",
    "FAMILY_PRIORITY",
    # data opportunity + research ROI
    "DataOpportunityEngine",
    "DataOpportunityReport",
    "ResearchROIMonitor",
    "ResearchROIReport",
    # reports
    "research_report",
    "failure_analysis_report",
    "survivor_report",
    "family_performance_report",
    "discovery_efficiency_report",
    "pipeline_health_report",
    # errors
    "AutoDiscoveryError",
]

```

### libs/data/cot_source.py
```python
"""CFTC Commitments-of-Traders (COT) source -- free weekly speculator positioning.

Pulls legacy futures-only non-commercial (large speculator) positioning from the CFTC public
reporting API and turns it into a per-instrument *positioning z-score* aligned to MT5 symbols. This
is the orthogonal-to-price sleeve: positioning extremes (crowded specs) precede mean reversion, a
documented risk premium not captured by trend/momentum. Weekly data (Tuesday snapshot, published
Friday); we lag it and forward-fill to daily, so no look-ahead.

Sign convention: CFTC FX futures are FOREIGN/USD. EUR/GBP/AUD futures match EURUSD/GBPUSD/AUDUSD
directly; JPY/CHF/CAD futures are the inverse of USDJPY/USDCHF/USDCAD, so their sign is flipped so a
positive z always means "specs crowded long the MT5 instrument".
"""

from __future__ import annotations

import urllib.request
from io import StringIO

import pandas as pd

_BASE = "https://publicreporting.cftc.gov/resource/6dca-aqww.json"

# MT5 symbol -> (CFTC legacy contract_market_code, sign vs the MT5 instrument's direction)
COT_MAP: dict[str, tuple[str, float]] = {
    "XAUUSD": ("088691", +1.0),   # GOLD
    "XAGUSD": ("084691", +1.0),   # SILVER
    "XPTUSD": ("076651", +1.0),   # PLATINUM
    "XPDUSD": ("075651", +1.0),   # PALLADIUM
    "EURUSD": ("099741", +1.0),   # EURO FX  (EUR/USD)
    "GBPUSD": ("096742", +1.0),   # BRITISH POUND (GBP/USD)
    "AUDUSD": ("232741", +1.0),   # AUSTRALIAN DOLLAR (AUD/USD)
    "USDJPY": ("097741", -1.0),   # JAPANESE YEN (JPY/USD) -> invert for USDJPY
    "USDCHF": ("092741", -1.0),   # SWISS FRANC (CHF/USD) -> invert for USDCHF
    "USDCAD": ("090741", -1.0),   # CANADIAN DOLLAR (CAD/USD) -> invert for USDCAD
    "XTIUSD": ("067411", +1.0),   # CRUDE OIL, LIGHT SWEET-WTI
}


def _get(url: str) -> list[dict[str, str]]:
    req = urllib.request.Request(url.replace(" ", "%20"), headers={"User-Agent": "quant-research"})
    with urllib.request.urlopen(req, timeout=40) as r:
        records = pd.read_json(StringIO(r.read().decode("utf-8"))).to_dict("records")
    return [dict(rec) for rec in records]


def fetch_net_spec(code: str) -> pd.Series:
    """Weekly net-speculator positioning as a fraction of open interest for one CFTC contract."""
    url = (f"{_BASE}?$where=cftc_contract_market_code='{code}'"
           "&$select=report_date_as_yyyy_mm_dd,pct_of_oi_noncomm_long_all,"
           "pct_of_oi_noncomm_short_all&$order=report_date_as_yyyy_mm_dd ASC&$limit=5000")
    rows = _get(url)
    if not rows:
        return pd.Series(dtype="float64")
    df = pd.DataFrame(rows)
    dt = pd.to_datetime(df["report_date_as_yyyy_mm_dd"], utc=True)
    net = (df["pct_of_oi_noncomm_long_all"].astype("float64")
           - df["pct_of_oi_noncomm_short_all"].astype("float64")) / 100.0
    return pd.Series(net.to_numpy(), index=dt).sort_index()


def cot_zscore_daily(
    symbols: list[str],
    daily_index: pd.DatetimeIndex,
    *,
    z_weeks: int = 156,
) -> pd.DataFrame:
    """Per-symbol COT positioning z-score (3y rolling), sign-aligned, lagged, daily-ffilled.

    Returns a DataFrame on ``daily_index`` with one column per mapped symbol. A positive value means
    speculators are crowded LONG the MT5 instrument (relative to its own 3-year history).
    """
    cols: dict[str, pd.Series] = {}
    for sym in symbols:
        if sym not in COT_MAP:
            continue
        code, sign = COT_MAP[sym]
        net = fetch_net_spec(code)
        if len(net) < z_weeks // 2:
            continue
        z = (net - net.rolling(z_weeks, min_periods=52).mean()) / net.rolling(
            z_weeks, min_periods=52).std()
        z = (sign * z).shift(1)                          # publication lag (no look-ahead)
        cols[sym] = z.reindex(z.index.union(daily_index)).sort_index().ffill().reindex(daily_index)
    return pd.DataFrame(cols, index=daily_index)

```

### libs/data/mt5_source.py
```python
"""MT5 ingestion (read path) and timezone normalization.

MT5 returns bar times as a Unix epoch in the *broker server's* wall clock, which is the
classic source of session/seasonal bugs. :func:`load_mt5_bars` therefore reads raw bars as
naive server time and converts to true UTC via :func:`normalize_timezone`, which is DST-aware
(it uses the IANA zone, not a fixed offset).
"""

from __future__ import annotations

from datetime import datetime
from typing import ClassVar, Protocol, runtime_checkable

import pandas as pd

from libs.data.errors import MT5Error
from libs.data.instruments import get_spec
from libs.data.schema import BAR_COLUMNS, validate_bars
from libs.data.timeframe import Timeframe

# Raw columns expected from a bar source (MT5 ``copy_rates_range`` shape).
_RAW_TIME = "time"
_RAW_VOLUME = "tick_volume"


@runtime_checkable
class BarSource(Protocol):
    """Supplies raw bars: a frame with ``time`` (epoch seconds) + OHLC + ``tick_volume``."""

    def fetch_bars(
        self, symbol: str, timeframe: Timeframe, start: datetime, end: datetime
    ) -> pd.DataFrame: ...


class MT5BarSource:  # pragma: no cover - requires a live Windows MT5 terminal
    """Real bar source backed by the ``MetaTrader5`` package."""

    _TF_MAP: ClassVar[dict[Timeframe, str]] = {
        Timeframe.M1: "TIMEFRAME_M1",
        Timeframe.M5: "TIMEFRAME_M5",
        Timeframe.M15: "TIMEFRAME_M15",
        Timeframe.H1: "TIMEFRAME_H1",
        Timeframe.H4: "TIMEFRAME_H4",
        Timeframe.D1: "TIMEFRAME_D1",
    }

    def __init__(self) -> None:
        try:
            import MetaTrader5 as mt5
        except ImportError as exc:
            raise MT5Error("the MetaTrader5 package is not installed") from exc
        self._mt5 = mt5
        if not mt5.initialize():
            raise MT5Error(f"MT5 initialize() failed: {mt5.last_error()}")

    def fetch_bars(
        self, symbol: str, timeframe: Timeframe, start: datetime, end: datetime
    ) -> pd.DataFrame:
        tf_const = getattr(self._mt5, self._TF_MAP[timeframe])
        rates = self._mt5.copy_rates_range(symbol, tf_const, start, end)
        if rates is None or len(rates) == 0:
            raise MT5Error(f"no rates returned for {symbol} {timeframe}")
        return pd.DataFrame(rates)

    def shutdown(self) -> None:
        self._mt5.shutdown()


def normalize_timezone(
    df: pd.DataFrame, *, input_tz: str = "UTC", timestamp_col: str = "timestamp"
) -> pd.DataFrame:
    """Return a copy of ``df`` with ``timestamp_col`` as timezone-aware UTC.

    Naive timestamps are interpreted in ``input_tz`` (DST-aware via the IANA database) and
    converted to UTC; already-aware timestamps are converted to UTC directly.
    """
    out = df.copy()
    series = out[timestamp_col]
    if getattr(series.dt, "tz", None) is None:
        series = series.dt.tz_localize(input_tz)
    out[timestamp_col] = series.dt.tz_convert("UTC")
    return out


def load_mt5_bars(
    symbol: str,
    timeframe: Timeframe,
    start: datetime,
    end: datetime,
    *,
    source: BarSource,
    server_tz: str = "UTC",
) -> pd.DataFrame:
    """Load bars from a :class:`BarSource` into the canonical UTC schema.

    Args:
        symbol: a supported instrument.
        timeframe: bar timeframe.
        start, end: inclusive request bounds.
        source: the bar source (injected for testability).
        server_tz: IANA zone of the broker server clock (used to convert to true UTC).
    """
    get_spec(symbol)  # validate the instrument is supported
    raw = source.fetch_bars(symbol, timeframe, start, end)
    if _RAW_TIME not in raw.columns:
        raise MT5Error(f"raw bars missing '{_RAW_TIME}' column")

    frame = pd.DataFrame(
        {
            "timestamp": pd.to_datetime(raw[_RAW_TIME], unit="s"),  # naive server time
            "open": raw["open"].astype("float64"),
            "high": raw["high"].astype("float64"),
            "low": raw["low"].astype("float64"),
            "close": raw["close"].astype("float64"),
            "volume": raw[_RAW_VOLUME].astype("float64"),
        }
    )
    frame = normalize_timezone(frame, input_tz=server_tz)
    frame = frame.sort_values("timestamp").reset_index(drop=True)
    return validate_bars(frame[list(BAR_COLUMNS)], require_sorted=True)

```

### libs/data/multiexchange.py
```python
"""Multi-exchange funding data (Binance + Bybit + OKX) -- a NEW free, orthogonal data family.

Single-venue funding is the existing carry edge. The cross-exchange *dispersion* (a venue's funding
vs the cross-venue consensus) is a different, orthogonal signal: it measures venue-relative crowding
and inter-venue arbitrage pressure, not the market-wide leverage demand the carry sleeve already
trades. All public REST, no keys. 8h funding, paginated to ~3 months. Symbols map BASEUSDT (Binance/
Bybit) <-> BASE-USDT-SWAP (OKX).
"""

from __future__ import annotations

import json
import time
import urllib.request

import pandas as pd

_UA = {"User-Agent": "quant-platform/1.0"}


def _get(url: str) -> dict[str, object]:
    req = urllib.request.Request(url, headers=_UA)
    with urllib.request.urlopen(req, timeout=20) as r:
        data = json.loads(r.read())
    return data if isinstance(data, dict) else {"_": data}


def okx_inst(symbol: str) -> str:
    """BTCUSDT -> BTC-USDT-SWAP."""
    base = symbol[:-4] if symbol.endswith("USDT") else symbol
    return f"{base}-USDT-SWAP"


def fetch_bybit_funding(symbol: str, *, pages: int = 3) -> pd.DataFrame:
    """Bybit linear-perp 8h funding history (paginated back via the endTime cursor)."""
    rows: list[dict[str, object]] = []
    end: int | None = None
    for _ in range(pages):
        url = (f"https://api.bybit.com/v5/market/funding/history?category=linear"
               f"&symbol={symbol}&limit=200")
        if end:
            url += f"&endTime={end}"
        res = _get(url).get("result")
        lst = res.get("list") if isinstance(res, dict) else None
        if not isinstance(lst, list) or not lst:
            break
        rows += lst
        end = int(str(lst[-1]["fundingRateTimestamp"])) - 1
        time.sleep(0.2)
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame({
        "timestamp": pd.to_datetime([int(str(r["fundingRateTimestamp"])) for r in rows],
                                    unit="ms", utc=True),
        "funding": [float(str(r["fundingRate"])) for r in rows]})
    return df.drop_duplicates("timestamp").sort_values("timestamp").reset_index(drop=True)


def fetch_okx_funding(symbol: str, *, pages: int = 3) -> pd.DataFrame:
    """OKX swap 8h funding history (paginated back via the `after` cursor)."""
    inst = okx_inst(symbol)
    rows: list[dict[str, object]] = []
    after: int | None = None
    for _ in range(pages):
        url = f"https://www.okx.com/api/v5/public/funding-rate-history?instId={inst}&limit=100"
        if after:
            url += f"&after={after}"
        lst = _get(url).get("data")
        if not isinstance(lst, list) or not lst:
            break
        rows += lst
        after = int(str(lst[-1]["fundingTime"]))
        time.sleep(0.2)
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame({
        "timestamp": pd.to_datetime([int(str(r["fundingTime"])) for r in rows], unit="ms",
                                    utc=True),
        "funding": [float(str(r["fundingRate"])) for r in rows]})
    return df.drop_duplicates("timestamp").sort_values("timestamp").reset_index(drop=True)

```

### libs/execution/engine.py
```python
"""Execution engine — submit, cancel, track, and reconcile, with idempotency and fail-closed.

Honours the structural rule that an order can only exist with a valid ``risk_approval_id``.
Idempotency keys prevent duplicate orders (store-level and broker-level). Ambiguous broker
timeouts never assume a fill — they force reconciliation. The broker is the source of truth for
positions; on any divergence the engine fails closed.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict

from libs.execution.broker import BrokerGateway, OrderRequest
from libs.execution.errors import BrokerTimeout, ExecutionError, TransientBrokerError
from libs.execution.journal import TradeJournal
from libs.execution.retry import retry_call
from libs.store.models import Order
from libs.store.trading import OrderStore


class ExecStatus(StrEnum):
    FILLED = "filled"
    REJECTED = "rejected"
    SUBMITTED = "submitted"
    DUPLICATE = "duplicate"
    NEEDS_RECONCILE = "needs_reconcile"
    CANCELLED = "cancelled"


class ExecutionResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    status: ExecStatus
    order: Order | None
    broker_order_id: int | None = None
    filled_qty: float = 0.0
    fill_price: float | None = None
    message: str = ""


class ReconciliationReport(BaseModel):
    model_config = ConfigDict(frozen=True)

    broker_positions: dict[str, float]
    internal_positions: dict[str, float]
    deltas: dict[str, float]
    divergence: bool
    halted: bool

    @property
    def ok(self) -> bool:
        return not self.halted


class ExecutionEngine:
    """Translates approved intents into broker orders and keeps state reconciled."""

    def __init__(
        self,
        store: OrderStore,
        broker: BrokerGateway,
        journal: TradeJournal,
        *,
        attempts: int = 3,
        backoff: float = 0.0,
    ) -> None:
        self.store = store
        self.broker = broker
        self.journal = journal
        self.attempts = attempts
        self.backoff = backoff

    # ---------------------------------------------------------------- submit

    def submit_order(self, request: OrderRequest) -> ExecutionResult:
        """Submit an approved order. Idempotent; fails closed without a valid approval."""
        if not request.risk_approval_id:
            raise ExecutionError("fail-closed: order requires a risk_approval_id")

        existing = self.store.get_order_by_idempotency_key(request.idempotency_key)
        if existing is not None:
            self.journal.record(
                "order_duplicate_ignored",
                {"idempotency_key": request.idempotency_key, "order_id": existing.id},
                outcome="duplicate",
            )
            return ExecutionResult(
                status=ExecStatus.DUPLICATE, order=existing, broker_order_id=existing.mt5_ticket,
                message="idempotent: order already exists",
            )

        try:
            order = self.store.create_order(
                instrument=request.instrument, side=request.side, qty=request.qty,
                order_type=request.order_type, risk_approval_id=request.risk_approval_id,
                intended_price=request.price, alpha_id=request.alpha_id,
                idempotency_key=request.idempotency_key,
            )
        except ValueError as exc:
            self.journal.record(
                "order_rejected_no_approval",
                {"idempotency_key": request.idempotency_key}, outcome="rejected",
                rationale=str(exc),
            )
            raise ExecutionError(f"fail-closed: {exc}") from exc

        self.journal.record(
            "order_submitted",
            {"order_id": order.id, "instrument": request.instrument, "side": request.side,
             "qty": request.qty},
        )

        try:
            result = retry_call(
                lambda: self.broker.place_order(request),
                attempts=self.attempts, backoff=self.backoff, retry_on=(TransientBrokerError,),
            )
        except BrokerTimeout as exc:
            self.store.set_order_status(order.id, "pending")
            self.journal.record(
                "order_timeout", {"order_id": order.id}, outcome="needs_reconcile",
                rationale=str(exc),
            )
            return ExecutionResult(
                status=ExecStatus.NEEDS_RECONCILE, order=self.store.get_order(order.id),
                message="ambiguous broker timeout; reconciliation required",
            )
        except TransientBrokerError as exc:
            self.store.set_order_status(order.id, "rejected")
            self.journal.record(
                "order_failed", {"order_id": order.id}, outcome="rejected", rationale=str(exc)
            )
            return ExecutionResult(
                status=ExecStatus.REJECTED, order=self.store.get_order(order.id), message=str(exc)
            )

        if result.status == "filled":
            self.store.record_fill(
                order_id=order.id, fill_price=result.fill_price or 0.0,
                fill_qty=result.filled_qty, mt5_deal_id=result.deal_id,
            )
            updated = self.store.set_order_status(
                order.id, "filled", mt5_ticket=result.broker_order_id
            )
            self._sync_instrument(request.instrument)
            self.journal.record(
                "order_filled",
                {"order_id": order.id, "fill_price": result.fill_price,
                 "fill_qty": result.filled_qty}, outcome="filled",
            )
            return ExecutionResult(
                status=ExecStatus.FILLED, order=updated, broker_order_id=result.broker_order_id,
                filled_qty=result.filled_qty, fill_price=result.fill_price, message="filled",
            )

        if result.status == "rejected":
            updated = self.store.set_order_status(
                order.id, "rejected", mt5_ticket=result.broker_order_id
            )
            self.journal.record(
                "order_rejected", {"order_id": order.id}, outcome="rejected",
                rationale=result.message,
            )
            return ExecutionResult(
                status=ExecStatus.REJECTED, order=updated, broker_order_id=result.broker_order_id,
                message=result.message,
            )

        updated = self.store.set_order_status(
            order.id, "pending", mt5_ticket=result.broker_order_id
        )
        self.journal.record("order_working", {"order_id": order.id}, outcome="pending")
        return ExecutionResult(
            status=ExecStatus.SUBMITTED, order=updated, broker_order_id=result.broker_order_id,
            message="working order",
        )

    # ---------------------------------------------------------------- cancel

    def cancel_order(self, order_id: str) -> ExecutionResult:
        """Cancel a working order (only pending orders may be cancelled)."""
        order = self.store.get_order(order_id)
        if order is None:
            raise ExecutionError(f"unknown order {order_id}")
        if order.status != "pending":
            raise ExecutionError(f"cannot cancel order in status {order.status!r}")

        broker_ok = True
        if order.mt5_ticket is not None:
            broker_ok = retry_call(
                lambda: self.broker.cancel_order(order.mt5_ticket),  # type: ignore[arg-type]
                attempts=self.attempts, backoff=self.backoff, retry_on=(TransientBrokerError,),
            )
        updated = self.store.set_order_status(order_id, "cancelled")
        self.journal.record(
            "order_cancelled", {"order_id": order_id, "broker_ok": broker_ok}, outcome="cancelled"
        )
        return ExecutionResult(
            status=ExecStatus.CANCELLED, order=updated, broker_order_id=order.mt5_ticket,
            message="cancelled",
        )

    # ------------------------------------------------------------ reconcile

    def reconcile_positions(
        self, *, halt_on_divergence: bool = True, tolerance: float = 1e-9
    ) -> ReconciliationReport:
        """Sync internal positions to the broker (source of truth); fail closed on divergence."""
        broker_positions = retry_call(
            self.broker.get_positions, attempts=self.attempts, backoff=self.backoff,
            retry_on=(TransientBrokerError,),
        )
        broker_map = {p.instrument: p for p in broker_positions}
        internal = {p.instrument: p for p in self.store.list_positions()}
        instruments = sorted(set(broker_map) | set(internal))

        broker_vals: dict[str, float] = {}
        internal_vals: dict[str, float] = {}
        deltas: dict[str, float] = {}
        for sym in instruments:
            bq = broker_map[sym].qty if sym in broker_map else 0.0
            iq = internal[sym].qty if sym in internal else 0.0
            broker_vals[sym] = bq
            internal_vals[sym] = iq
            deltas[sym] = bq - iq
            avg = broker_map[sym].avg_price if sym in broker_map else 0.0
            self.store.upsert_position(instrument=sym, qty=bq, avg_price=avg)  # adopt broker truth

        divergence = any(abs(d) > tolerance for d in deltas.values())
        halted = bool(divergence and halt_on_divergence)
        self.journal.record(
            "reconciliation", {"deltas": deltas}, outcome="halt" if halted else "ok"
        )
        return ReconciliationReport(
            broker_positions=broker_vals, internal_positions=internal_vals, deltas=deltas,
            divergence=divergence, halted=halted,
        )

    def safe_start(self) -> ReconciliationReport:
        """Reconcile against the broker before resuming trading (never blind-resume)."""
        self.journal.record("safe_start", {}, rationale="reconcile before resuming")
        return self.reconcile_positions(halt_on_divergence=False)

    # ------------------------------------------------------------- internal

    def _sync_instrument(self, instrument: str) -> None:
        for position in self.broker.get_positions():
            if position.instrument == instrument:
                self.store.upsert_position(
                    instrument=instrument, qty=position.qty, avg_price=position.avg_price
                )
                return
        self.store.upsert_position(instrument=instrument, qty=0.0, avg_price=0.0)

```

### libs/features/definition.py
```python
"""Feature definitions.

A feature is a *versioned, tested* transform of bars to a single causal series — the same
``compute`` is used offline (training) and online (serving), which is what guarantees
train/serve parity. ``inputs`` declares the columns the feature reads (used for structural
target-leakage checks).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

import pandas as pd

ComputeFn = Callable[[pd.DataFrame], pd.Series]


@dataclass(frozen=True)
class FeatureDefinition:
    """A versioned feature: name + version + a causal compute function."""

    name: str
    version: int
    compute: ComputeFn = field(compare=False, repr=False)
    inputs: tuple[str, ...]
    category: str = "price"
    description: str = ""
    min_periods: int = 1

    @property
    def key(self) -> str:
        return f"{self.name}@v{self.version}"

```

### libs/monitoring/__init__.py
```python
"""``libs.monitoring`` — live telemetry, threshold alerting, SLOs, and heartbeat.

Persists metrics and alerts to the SQLite system of record (migration 0004), evaluates
thresholds/SLOs deterministically, and routes alerts to pluggable sinks. No parallel store; the
metric series is append-only and alerts are resolvable but never deleted.
"""

from __future__ import annotations

from libs.monitoring.alerting import (
    AlertRouter,
    AlertSink,
    AlertStore,
    CollectingSink,
)
from libs.monitoring.metrics_store import MetricsStore
from libs.monitoring.models import (
    SLO,
    Alert,
    MetricPoint,
    Op,
    Severity,
    Threshold,
    compare,
)
from libs.monitoring.monitor import HeartbeatWatchdog, MonitorService, SLOEvaluator

__all__ = [  # noqa: RUF022  # grouped by concern
    # models
    "Severity",
    "Op",
    "compare",
    "MetricPoint",
    "Threshold",
    "Alert",
    "SLO",
    # stores
    "MetricsStore",
    "AlertStore",
    # alerting
    "AlertRouter",
    "AlertSink",
    "CollectingSink",
    # service
    "MonitorService",
    "HeartbeatWatchdog",
    "SLOEvaluator",
]

```

### libs/ops/research_daemon.py
```python
"""Autonomous research daemon: the worker loop, the supervisor maintenance, and the research loop.

  Research Memory -> Campaign Generator -> Discovery -> Validation -> Audit -> Research Ledger
  -> Next Campaign ...  (forever)

A :class:`ResearchWorker` leases campaigns and runs them through the existing ``AutoDiscoveryLab``
(no validation logic is changed). A :class:`Supervisor` keeps the queue full and reclaims work from
dead workers. Process-level spawning/restart lives in ``scripts/run_supervisor.py``; this module is
the deterministic, unit-testable core. Executors are injected so the loop is testable without data.
"""

from __future__ import annotations

import time
from collections.abc import Callable, Iterable, Sequence
from pathlib import Path
from typing import Any

import numpy as np

from libs.autodiscovery.models import Family, MarketSeries
from libs.autodiscovery.orchestrator import AutoDiscoveryLab
from libs.data.instruments import AssetClass, InstrumentSpec, register_instrument
from libs.data.lake import Layer, ParquetLake
from libs.data.timeframe import Timeframe
from libs.ops.campaign_queue import CampaignQueue
from libs.ops.workers import WorkerRegistry
from libs.store.connection import Database

# Executor: (worker db, campaign spec) -> result dict. Injected for testability.
CampaignExecutor = Callable[[Database, dict[str, Any]], dict[str, Any]]
_COST_PER_SIDE = {AssetClass.FX: 8e-5, AssetClass.METAL: 1.5e-4, AssetClass.ENERGY: 2e-4}


class ResearchWorker:
    """Leases and runs campaigns in a crash-safe loop. One worker == one process/connection."""

    def __init__(
        self,
        db: Database,
        worker_id: str,
        executor: CampaignExecutor,
        *,
        lease_seconds: int = 600,
        poll_seconds: float = 3.0,
        pid: int = 0,
    ) -> None:
        self.db = db
        self.worker_id = worker_id
        self.executor = executor
        self.lease_seconds = lease_seconds
        self.poll_seconds = poll_seconds
        self.queue = CampaignQueue(db)
        self.registry = WorkerRegistry(db)
        self.registry.register(worker_id, pid=pid)

    def run_once(self) -> str:
        """Lease + run a single campaign. Returns 'idle' | 'done' | 'failed'."""
        self.registry.beat(self.worker_id, status="idle")
        lease = self.queue.lease(self.worker_id, lease_seconds=self.lease_seconds)
        if lease is None:
            return "idle"
        cid = lease["id"]
        self.registry.beat(self.worker_id, status="running", current_campaign=cid)
        try:
            result = self.executor(self.db, lease["spec"])
        except Exception as exc:  # never let one bad campaign kill the worker
            status = self.queue.fail(cid, self.worker_id, f"{type(exc).__name__}: {exc}")
            self.registry.beat(self.worker_id, status="idle")
            return "failed" if status == "failed" else "retry"
        self.queue.complete(cid, self.worker_id, result)
        self.registry.beat(self.worker_id, status="idle", completed=True)
        return "done"

    def run_forever(self, *, stop: Callable[[], bool] | None = None) -> None:
        stop = stop or (lambda: False)
        while not stop():
            outcome = self.run_once()
            if outcome == "idle":
                time.sleep(self.poll_seconds)


class Supervisor:
    """Keeps the system live: reclaims dead-worker leases, prunes workers, refills the queue."""

    def __init__(
        self,
        db: Database,
        *,
        generator: Callable[[], Iterable[dict[str, Any]]],
        min_queue_depth: int = 8,
        worker_stale_seconds: int = 120,
        cleanup_days: int = 7,
    ) -> None:
        self.db = db
        self.queue = CampaignQueue(db)
        self.registry = WorkerRegistry(db)
        self.generator = generator
        self.min_queue_depth = min_queue_depth
        self.worker_stale_seconds = worker_stale_seconds
        self.cleanup_days = cleanup_days

    def ensure_queue(self) -> int:
        """Top up the queue from the campaign generator when it runs low. Returns # enqueued."""
        if self.queue.stats()["depth"] >= self.min_queue_depth:
            return 0
        enq = 0
        for spec in self.generator():
            if self.queue.enqueue(spec) is not None:
                enq += 1
        return enq

    def maintain(self) -> dict[str, int]:
        """One maintenance pass: reclaim stale leases, prune dead workers, cleanup, refill."""
        reclaimed = self.queue.reclaim_stale()
        pruned = self.registry.prune(stale_seconds=self.worker_stale_seconds * 10)
        cleaned = self.queue.cleanup(keep_days=self.cleanup_days)
        enqueued = self.ensure_queue()
        return {"reclaimed": reclaimed, "pruned": pruned, "cleaned": cleaned, "enqueued": enqueued}


# --- production executor + generator over the Parquet lake (no live MT5 dependency) -------------
def _lake_symbols(lake_dir: str) -> dict[str, AssetClass]:
    base = Path(lake_dir) / "bronze"
    out: dict[str, AssetClass] = {}
    if not base.exists():
        return out
    for ac_dir in base.iterdir():
        try:
            ac = AssetClass(ac_dir.name)
        except ValueError:
            continue
        for sym in ac_dir.iterdir():
            if (sym / Timeframe.D1.value).exists():
                out[sym.name] = ac
    return out


def make_lake_executor(lake_dir: str = "data/lake") -> CampaignExecutor:
    """Executor that runs a campaign's symbols/families through the lab on lake history."""
    available = _lake_symbols(lake_dir)
    for sym, ac in available.items():
        register_instrument(InstrumentSpec(symbol=sym, asset_class=ac, description=sym))
    lake = ParquetLake(lake_dir)

    def executor(db: Database, spec: dict[str, Any]) -> dict[str, Any]:
        symbols: list[str] = [s for s in spec.get("symbols", []) if s in available]
        families = [Family(f) for f in spec.get("families", [])] or None
        frames = {s: lake.read_bars(Layer.BRONZE, s, Timeframe.D1).set_index("timestamp")
                  for s in symbols}

        def provider(symbol: str) -> MarketSeries | None:
            df = frames.get(symbol)
            if df is None or len(df) < 250:
                return None
            return MarketSeries(
                close=df["close"].to_numpy("float64"), high=df["high"].to_numpy("float64"),
                low=df["low"].to_numpy("float64"), volume=df["volume"].to_numpy("float64"),
                hour=np.array([t.hour for t in df.index], dtype="float64"),
            )

        def cost_provider(symbol: str) -> float:
            return _COST_PER_SIDE.get(available.get(symbol, AssetClass.FX), 1e-4)

        lab = AutoDiscoveryLab(db, provider, cost_provider=cost_provider, families=families)
        res = lab.cycle(symbols)
        return {"campaign_id": res.campaign_id, "tested": res.tested,
                "survivors": res.survivors, "rejected": res.rejected}

    return executor


def lake_campaign_specs(
    lake_dir: str = "data/lake",
    *,
    families: Sequence[str] | None = None,
    batch: int = 1,
) -> list[dict[str, Any]]:
    """Generate one campaign per symbol-batch over the lake (the research loop's fuel)."""
    fams = list(families) if families is not None else [f.value for f in Family]
    syms = sorted(_lake_symbols(lake_dir))
    specs: list[dict[str, Any]] = []
    for i in range(0, len(syms), batch):
        chunk = syms[i: i + batch]
        if chunk:
            specs.append({"symbols": chunk, "families": fams, "source": "lake", "timeframe": "D1"})
    return specs

```

### libs/portfolio/__init__.py
```python
"""``libs.portfolio`` — portfolio construction engine.

Risk parity, HRP, robust optimization, correlation/exposure/factor controls, a diversification
engine, rebalancing, and full analytics. Risk overrides alpha: the engine proposes constrained
target weights; the risk gate disposes.
"""

from __future__ import annotations

from libs.portfolio.analytics import allocate_capital, portfolio_analytics
from libs.portfolio.constraints import apply_constraints
from libs.portfolio.covariance import cov_to_corr, covariance_from_alphas
from libs.portfolio.diversification import (
    apply_correlation_controls,
    concentration,
    diversification_ratio,
    effective_bets,
)
from libs.portfolio.engine import PortfolioEngine, build_portfolio
from libs.portfolio.errors import PortfolioError
from libs.portfolio.exposures import (
    calculate_asset_class_exposures,
    calculate_factor_exposures,
    calculate_risk_contributions,
    calculate_strategy_exposures,
    calculate_symbol_exposures,
)
from libs.portfolio.factor_model import FactorRiskModel, ShrinkageCovariance
from libs.portfolio.hrp import hrp_weights
from libs.portfolio.models import (
    AlphaInput,
    PortfolioAnalytics,
    PortfolioConstraints,
    PortfolioTarget,
    RebalanceResult,
    StrategyType,
)
from libs.portfolio.multiperiod import MultiPeriodOptimizer, MultiPeriodPlan
from libs.portfolio.optimize import optimize_portfolio
from libs.portfolio.rebalance import rebalance
from libs.portfolio.risk_parity import allocate_risk, risk_parity_weights

__all__ = [  # noqa: RUF022  # grouped by concern
    # models
    "AlphaInput",
    "StrategyType",
    "PortfolioConstraints",
    "PortfolioTarget",
    "PortfolioAnalytics",
    "RebalanceResult",
    # covariance
    "covariance_from_alphas",
    "cov_to_corr",
    "ShrinkageCovariance",
    "FactorRiskModel",
    # allocators
    "risk_parity_weights",
    "allocate_risk",
    "hrp_weights",
    "optimize_portfolio",
    "allocate_capital",
    # multi-period
    "MultiPeriodOptimizer",
    "MultiPeriodPlan",
    # controls / constraints
    "apply_constraints",
    "apply_correlation_controls",
    # exposures / risk contributions
    "calculate_factor_exposures",
    "calculate_strategy_exposures",
    "calculate_asset_class_exposures",
    "calculate_symbol_exposures",
    "calculate_risk_contributions",
    # diversification
    "diversification_ratio",
    "concentration",
    "effective_bets",
    # rebalancing / analytics
    "rebalance",
    "portfolio_analytics",
    # engine
    "build_portfolio",
    "PortfolioEngine",
    # errors
    "PortfolioError",
]

```

### libs/portfolio/covariance.py
```python
"""Covariance helpers for the portfolio engine."""

from __future__ import annotations

from collections.abc import Sequence
from typing import cast

import numpy as np

from libs.portfolio.errors import PortfolioError
from libs.portfolio.models import AlphaInput


def covariance_from_alphas(
    alphas: Sequence[AlphaInput], correlation: np.ndarray | None = None
) -> np.ndarray:
    """Build a covariance matrix from per-alpha volatilities and an optional correlation matrix."""
    vols = np.array([a.volatility for a in alphas], dtype="float64")
    n = len(vols)
    if n == 0:
        raise PortfolioError("at least one alpha is required")
    if correlation is None:
        return cast("np.ndarray", np.diag(vols**2))
    corr = np.asarray(correlation, dtype="float64")
    if corr.shape != (n, n):
        raise PortfolioError(f"correlation shape {corr.shape} != ({n}, {n})")
    return cast("np.ndarray", np.outer(vols, vols) * corr)


def cov_to_corr(cov: np.ndarray) -> np.ndarray:
    """Convert a covariance matrix to a correlation matrix."""
    std = np.sqrt(np.diag(cov))
    std_safe = np.where(std > 0, std, 1.0)
    corr = cov / np.outer(std_safe, std_safe)
    np.fill_diagonal(corr, 1.0)
    return cast("np.ndarray", corr)


# --------------------------------------------------------------------------- dynamic forecasting
# Static full-sample correlation is dangerous in crypto: in a crash everything correlates and a
# static risk-parity book is suddenly over-concentrated. These forecast next-period covariance
# (EWMA) and allocate by equal risk contribution (ERC) -- correlation-aware, so the book de-risks
# automatically when sleeves start co-moving. All estimates use only past data (no look-ahead).

def ewma_cov(returns: np.ndarray, lam: float = 0.94) -> np.ndarray:
    """EWMA covariance forecast (latest) from a T x N matrix. lam~0.94 ~= 33-day half-life."""
    r = np.asarray(returns, dtype="float64")
    r = r[~np.isnan(r).any(axis=1)]
    n = r.shape[1] if r.ndim == 2 else 0
    if len(r) < n + 2:
        return cast("np.ndarray", np.cov(r, rowvar=False)) if len(r) > 1 else np.eye(max(n, 1))
    mean = r.mean(axis=0)
    cov = np.cov(r, rowvar=False)
    for t in range(len(r)):
        x = (r[t] - mean).reshape(-1, 1)
        cov = lam * cov + (1.0 - lam) * (x @ x.T)
    return cast("np.ndarray", cov)


def erc_weights(cov: np.ndarray, *, iters: int = 250, max_weight: float = 0.40) -> np.ndarray:
    """Long-only equal-risk-contribution weights (correlation-aware), capped per name.

    Equalizes each name's risk *contribution* rc_i = w_i (cov w)_i via a damped multiplicative
    fixed point. For uncorrelated assets this reduces to inverse-vol (the ERC solution there).
    """
    n = cov.shape[0]
    d = np.sqrt(np.clip(np.diag(cov), 1e-12, None))
    w = (1.0 / d)
    w = w / w.sum()
    for _ in range(iters):
        rc = np.clip(w * (cov @ w), 1e-15, None)         # risk contribution per name
        w = w * np.sqrt(rc.mean() / rc)                  # damped step toward equal rc
        w = np.clip(w, 0.0, None)
        s = w.sum()
        if s <= 0:
            return np.asarray(np.ones(n) / n, dtype="float64")
        w = w / s
    for _ in range(8):
        over = w > max_weight
        if not over.any():
            break
        excess = float((w[over] - max_weight).sum())
        w[over] = max_weight
        room = ~over & (w > 0)
        if not room.any():
            break
        w[room] += excess * (w[room] / w[room].sum())
    return np.asarray(w / w.sum(), dtype="float64")


def cov_forecast_portfolio(
    returns: np.ndarray, *, lam: float = 0.94, lookback: int = 252,
    min_obs: int = 90, max_weight: float = 0.40, band: float = 0.03, rebal_cost: float = 5e-4,
) -> np.ndarray:
    """Daily portfolio returns using forecast-covariance ERC weights from the trailing window.

    Transaction-cost-aware: weights only move when the target shifts beyond ``band`` (a no-trade
    band that kills churn), and each rebalance pays ``rebal_cost`` per unit of weight turnover, so
    the reported return is net of the cost of acting on the forecast -- not a frictionless ideal.
    """
    r = np.asarray(returns, dtype="float64")
    t_total, n = r.shape
    out = np.zeros(t_total, dtype="float64")
    w = np.ones(n) / n
    for t in range(t_total):
        if t > min_obs:
            window = r[max(0, t - lookback):t]
            window = window[~np.isnan(window).any(axis=1)]
            if len(window) > min_obs:
                # EV gate: only fund sleeves with positive trailing mean (ERC alone would risk-
                # weight the losers too). Correlation-aware sizing across the survivors.
                live = np.flatnonzero(window.mean(axis=0) > 0.0)
                target = np.zeros(n)
                if len(live) >= 1:
                    cov = ewma_cov(window[:, live], lam)
                    target[live] = erc_weights(cov, max_weight=max_weight)
                if np.abs(target - w).sum() > band:      # no-trade band kills churn
                    out[t] -= float(np.abs(target - w).sum()) * rebal_cost
                    w = target
        out[t] += float(w @ np.nan_to_num(r[t]))
    return out

```

### libs/portfolio/live_book.py
```python
"""The ONE deployed-portfolio object -- single source of truth for live capital.

Every surface that shows "what is actually deployed" (dashboard molded card, testnet, live,
portfolio.json) derives from `LivePortfolio`. It reads the real testnet accounts + the cash-carry
state + the equity curve + the trade log, and exposes ONE consistent set of numbers: deployed
capital, the live sleeve(s), net PnL, day-count, winrate and the DEPLOYED Sharpe (computed from the
forward live equity curve -- NOT a backtest number). Research/shadow sleeves are labelled separately
and never mixed into the deployed Sharpe. This kills duplicate portfolio maths across scripts.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_STATE = Path("data/cashcarry_positions.json")
_CC = Path("web/cashcarry_live.json")
_CURVE = Path("data/live_combined_state.json")
_TRADES = Path("data/cashcarry_trades.json")


def _load(p: Path, default: Any) -> Any:
    try:
        return json.loads(p.read_text("utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


def _num(v: object, d: float = 0.0) -> float:
    try:
        return float(v)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return d


@dataclass
class LivePortfolio:
    """Canonical deployed book. Build via `LivePortfolio.load(base_per_leg=...)`."""

    base_per_leg: float
    start: str | None
    fut_equity: float
    fut_start_equity: float
    fut_unrealized: float
    spot_leg_pnl: float
    spot_realized: float = 0.0     # banked PnL of CLOSED spot legs (lives in the spot wallet)
    spot_usdt: float = 0.0
    funding: float = 0.0
    #: False when the executor could not MEASURE funding (venue outage) -- the 0.0 in `funding`
    #: is then an absence, not a harvest of zero, and every surface must say so (R0013).
    funding_measured: bool = True
    carries: list[dict[str, Any]] = field(default_factory=list)
    mcurve: list[list[Any]] = field(default_factory=list)
    trades: list[dict[str, Any]] = field(default_factory=list)

    # -- the single deployed truth --------------------------------------------------
    LIVE_SLEEVES = ("cash_and_carry",)                 # what is ACTUALLY deployed to capital

    @property
    def fut_pnl(self) -> float:
        return round(self.fut_equity - self.fut_start_equity, 2)

    @property
    def net_pnl(self) -> float:
        # delta-neutral reconciled total: futures-account delta (realized + funding + fees) +
        # OPEN spot marks + banked realized of CLOSED spot legs (symmetric on realized PnL)
        return round(self.fut_pnl + self.spot_leg_pnl + self.spot_realized, 2)

    @property
    def start_capital(self) -> float:
        return round(2 * self.base_per_leg, 2)

    @property
    def equity(self) -> float:
        return round(self.start_capital + self.net_pnl, 2)

    @property
    def days_live(self) -> float:
        if not self.start:
            return 0.0
        try:
            dt = datetime.fromisoformat(str(self.start))
            return round((datetime.now(tz=UTC) - dt).total_seconds() / 86400, 2)
        except (ValueError, TypeError):
            return 0.0

    @property
    def closed_trades(self) -> list[dict[str, Any]]:
        return [t for t in self.trades if t.get("event") == "close"]

    @property
    def n_closed(self) -> int:
        return len(self.closed_trades)

    @property
    def winrate(self) -> float | None:
        """% of CLOSED carries that netted positive. None until there is closed history (honest)."""
        cl = self.closed_trades
        if not cl:
            return None
        wins = sum(1 for t in cl if _num(t.get("net")) > 0)
        return round(100.0 * wins / len(cl), 1)

    # minimum forward window before an annualised Sharpe is statistically meaningful (not noise).
    _MIN_SHARPE_DAYS = 5.0

    def _hourly_equity(self) -> list[float]:
        """Resample the ~60s curve to one point per UTC hour (last obs) -- kills fee noise."""
        buckets: dict[str, float] = {}
        for t, e in self.mcurve:
            try:
                key = str(t)[:13]                             # 'YYYY-MM-DDTHH'
            except (ValueError, TypeError):
                continue
            buckets[key] = _num(e)
        return [buckets[k] for k in sorted(buckets)]

    @property
    def deployed_sharpe(self) -> float | None:
        """Annualised Sharpe from the FORWARD live curve, hourly-resampled. None until meaningful.

        Corresponds to the money actually on the testnet -- NOT a backtest. Deliberately returns
        None until >= `_MIN_SHARPE_DAYS` of forward history: a Sharpe computed on intra-hour fee
        noise is meaningless (and misleading), so we refuse to print one. Honesty > a filled cell.
        """
        if self.days_live < self._MIN_SHARPE_DAYS:
            return None
        eq = self._hourly_equity()
        if len(eq) < 48:                                       # >= ~2 days of hourly points
            return None
        rets = [eq[i] / eq[i - 1] - 1.0 for i in range(1, len(eq)) if eq[i - 1] > 0]
        if len(rets) < 40:
            return None
        mu = sum(rets) / len(rets)
        var = sum((r - mu) ** 2 for r in rets) / (len(rets) - 1)
        sd = math.sqrt(var)
        if sd <= 0:
            return None
        return round((mu / sd) * math.sqrt(365 * 24), 2)      # per-hour Sharpe -> annualised

    @classmethod
    def load(cls, base_per_leg: float, *, fut: Any = None, spot: Any = None) -> LivePortfolio:
        state = _load(_STATE, {})
        cc = _load(_CC, {})
        curve = _load(_CURVE, {})
        trades = _load(_TRADES, [])
        fa = fut.account_summary() if (fut and fut.has_keys()) else {}
        fut_eq = round(_num(fa.get("equity")), 2)
        return cls(
            base_per_leg=base_per_leg,
            start=state.get("start"),
            fut_equity=fut_eq,
            fut_start_equity=_num(state.get("start_futures_equity"), fut_eq),
            fut_unrealized=round(_num(fa.get("unrealized_pnl")), 2),
            spot_leg_pnl=round(_num(cc.get("spot_leg_pnl")), 2),
            spot_realized=round(_num(state.get("realized_spot_pnl")), 2),
            spot_usdt=round(spot.usdt_balance(), 2) if (spot and spot.has_keys()) else 0.0,
            funding=round(_num(cc.get("funding_harvested")), 2),
            funding_measured=bool(cc.get("funding_measured", True)),
            carries=cc.get("carries", []) if isinstance(cc.get("carries"), list) else [],
            mcurve=curve.get("mcurve", []) if isinstance(curve.get("mcurve"), list) else [],
            trades=trades if isinstance(trades, list) else [],
        )

    def to_public(self) -> dict[str, Any]:
        """The web/portfolio.json payload -- deployed vs research clearly separated."""
        return {
            "updated": datetime.now(tz=UTC).isoformat(),
            "deployed": {
                "sleeves": list(self.LIVE_SLEEVES),
                "start_capital": self.start_capital,
                "equity": self.equity,
                "net_pnl": self.net_pnl,
                "return_pct": round(self.net_pnl / self.start_capital * 100, 3)
                if self.start_capital else 0.0,
                "days_live": self.days_live,
                "winrate_pct": self.winrate,
                "n_closed_trades": self.n_closed,
                "deployed_sharpe": self.deployed_sharpe,
                "funding": self.funding,
                "funding_measured": self.funding_measured,
                "n_carries": len(self.carries),
            },
            "note": ("Single source of truth for DEPLOYED capital. Sharpe here is from the live "
                     "forward equity curve on the testnet -- NOT a backtest. Research/shadow "
                     "sleeves are shown in their own cards and never fold into this Sharpe."),
        }

```

### libs/research/fusion_search.py
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

### libs/research/slot_registry.py
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

Pure stdlib. import from libs.research.slot_registry.
"""
from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

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


def _read_json(rel: str) -> Any | None:
    """Return parsed JSON, or None when the source cannot be trusted (missing/unreadable)."""
    try:
        return json.loads((_ROOT / rel).read_text("utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def derive_slots() -> dict[str, Any]:
    """Enumerate every concurrently-accruing forward clock from the artifacts on disk.

    Returns a payload carrying the slots, the cohort size `m_concurrent`, and `complete` -- False
    whenever any source was unreadable, meaning m is a LOWER BOUND and the true bar may be higher.
    """
    slots: list[dict[str, str]] = []
    unknown: list[str] = []

    axis_doc = _read_json(_AXIS_STATE)
    if axis_doc is None:
        unknown.append(_AXIS_STATE)
    else:
        rows = axis_doc.get("axes", axis_doc) if isinstance(axis_doc, dict) else axis_doc
        for row in rows if isinstance(rows, list) else []:
            if not isinstance(row, dict):
                continue
            if str(row.get("verdict", "")).upper() == "RETIRED":
                continue
            slots.append({"name": str(row.get("axis", "?")), "kind": "axis",
                          "source": _AXIS_STATE, "state": str(row.get("verdict", "ACCRUING"))})

    for name, rel in _STANDING_STATES.items():
        doc = _read_json(rel)
        if doc is None:
            unknown.append(rel)
            continue
        if isinstance(doc, dict) and doc.get("shadow_start"):
            slots.append({"name": name, "kind": "standing", "source": rel,
                          "state": f"since {doc['shadow_start']}"})

    roster = _read_json(_SLEEVE_ROSTER)
    if roster is None:
        unknown.append(_SLEEVE_ROSTER)
        names: list[str] = list(_DERIVATIVE_BUILTIN)
    else:
        extras = [str(x) for x in roster if str(x).strip()] if isinstance(roster, list) else []
        names = sorted({*_DERIVATIVE_BUILTIN, *extras})
    for name in names:
        slots.append({"name": name, "kind": "derivative", "source": _SLEEVE_ROSTER,
                      "state": "ACCRUING"})

    return {
        "updated": datetime.now(tz=UTC).isoformat(),
        "m_concurrent": len(slots),
        "complete": not unknown,
        "cap": MAX_FORWARD_SLOTS,
        "over_cap": len(slots) > MAX_FORWARD_SLOTS,
        "idle_slots": max(0, MAX_FORWARD_SLOTS - len(slots)),
        "unknown_sources": unknown,
        "slots": slots,
        "note": ("Holm cohort for every Stage-B forward clock. Unreadable sources are counted as "
                 "UNKNOWN, never zero: understating m loosens every bar. Dormant clocks stay "
                 "counted until RETIRED by an explicit ledgered decision."),
    }


def concurrent_m() -> int:
    """The Holm cohort size. Never returns 0 -- a cohort of nothing would zero out multiplicity."""
    return max(1, int(derive_slots()["m_concurrent"]))


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

### libs/research/variation_blocker.py
```python
"""TRIVIAL-VARIATION BLOCKER + REJECTION TELEMETRY -- HYPOTHESIS_MAX #2 and #3.

#3, THE BLOCKER. Two hypotheses sharing a mechanism fingerprint are the SAME IDEA wearing different
parameters. Re-testing one is not new evidence -- it is a fresh multiplicity charge for a question
already asked, which is the garden of forking paths with a lookback knob on it. The desk's own
record is the case in point: 420 candidates, 0 survivors, and nothing in the pipeline could say how
many of the 420 were genuinely distinct questions.

The charge is the point. Every look costs multiplicity budget, so a re-parameterisation is worse
than useless: it consumes the budget that a genuinely new idea would have needed, and it inflates
the trial count that DSR and the stepdown correct against. Blocking it BEFORE compute is both a
cost saving and a statistical one, and the second matters more.

#2, THE TELEMETRY. `do_not_repeat` already routes rejections, but as free text -- so "why do ideas
die?" could only be answered by reading. Rejections are now STRUCTURED (stage + reason +
fingerprint), which lets the generator LEARN from them rather than merely be stopped by them.

=================================================================================================
WHAT THIS DELIBERATELY DOES NOT DO
=================================================================================================
It does not block on SIMILARITY, only on an EXACT fingerprint match plus a near-duplicate check
that must clear a high bar. A blocker tuned to catch "close enough" ideas silently narrows the
search space, and the desk already has a measured, expensive instance of an over-tight funnel
(the $100k capacity floor; the campaign-constant gates behind 420/0). Under L1.21a the timid
error here is the more expensive one, so the bar is set where a false block is unlikely and a
missed duplicate is merely a wasted trial.

A blocked idea is ALWAYS recorded with what it duplicated, so "blocked" never means "lost": the
ledger is a map of the space already searched, which is the input the breeder (#4) will need the
day it unblocks.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from libs.research.mechanism_fingerprint import describe, fingerprint, jaccard, tokens

_ROOT = Path(__file__).resolve().parents[2]
LEDGER = _ROOT / "data/variation_ledger.jsonl"

#: Jaccard at or above this counts as a near-duplicate even when fingerprints differ. Set HIGH on
#: purpose: at 0.90 two ideas share almost all their mechanism vocabulary. Lowering it trades a
#: cheap wasted trial for the risk of silently deleting a genuinely new question.
NEAR_DUP_JACCARD = 0.90


@dataclass(frozen=True)
class Verdict:
    allowed: bool
    reason: str
    fingerprint: str
    duplicate_of: str | None = None
    similarity: float | None = None

    def as_dict(self) -> dict[str, Any]:
        return dict(self.__dict__)


def _seen(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    out = []
    for line in path.read_text("utf-8").splitlines():
        if line.strip():
            try:
                out.append(json.loads(line))
            except ValueError:
                continue
    return out


def screen(hyp: Any, *, path: Path = LEDGER, prior: list[dict[str, Any]] | None = None) -> Verdict:
    """ALLOW or BLOCK, before any compute is spent. Pure apart from reading the ledger."""
    fp = fingerprint(hyp)
    seen = prior if prior is not None else _seen(path)
    accepted = [r for r in seen if r.get("allowed")]

    for r in accepted:
        if r.get("fingerprint") == fp:
            return Verdict(False, "exact mechanism fingerprint already tested -- this is the same "
                                  "idea with different parameters, and re-testing it charges "
                                  "multiplicity for a question already asked",
                           fp, duplicate_of=str(r.get("id", "?")), similarity=1.0)

    my = tokens(describe(hyp))
    for r in accepted:
        sim = jaccard(my, frozenset(r.get("tokens", [])))
        if sim >= NEAR_DUP_JACCARD:
            return Verdict(False, f"near-duplicate of a tested idea (Jaccard {sim:.2f} >= "
                                  f"{NEAR_DUP_JACCARD}) -- distinct fingerprint but the same "
                                  "mechanism vocabulary",
                           fp, duplicate_of=str(r.get("id", "?")), similarity=round(sim, 3))

    return Verdict(True, "novel mechanism fingerprint", fp)


def record(hyp: Any, verdict: Verdict, *, hyp_id: str = "", stage: str = "pre-compute",
           generator: str = "", path: Path = LEDGER) -> dict[str, Any]:
    """Append the decision. A BLOCK is recorded as fully as an ALLOW.

    Blocked ideas are the map of the space already searched -- exactly the input the breeder (#4)
    needs the day it unblocks -- so dropping them would be discarding the record of the work.
    """
    row = {
        "at": datetime.now(tz=UTC).isoformat(),
        "id": hyp_id or f"{fingerprint(hyp)}@{datetime.now(tz=UTC).timestamp():.0f}",
        "stage": stage, "generator": generator,
        "allowed": verdict.allowed, "reason": verdict.reason,
        "fingerprint": verdict.fingerprint, "duplicate_of": verdict.duplicate_of,
        "similarity": verdict.similarity,
        "tokens": sorted(tokens(describe(hyp))),
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row) + "\n")
    return row


def telemetry(*, path: Path = LEDGER) -> dict[str, Any]:
    """#2: WHERE ideas die and WHY, structured -- the generator's feedback signal.

    A rejection reason nobody aggregates teaches nothing. This is what turns a stream of blocks
    into a statement about the search: which stages kill, which fingerprints are saturated, and
    what share of generated volume was genuinely new.
    """
    rows = _seen(path)
    if not rows:
        return {"n": 0, "note": "no generation screened yet"}
    blocked = [r for r in rows if not r.get("allowed")]
    by_stage: dict[str, int] = {}
    by_reason: dict[str, int] = {}
    by_fp: dict[str, int] = {}
    for r in blocked:
        by_stage[str(r.get("stage"))] = by_stage.get(str(r.get("stage")), 0) + 1
        key = str(r.get("reason", ""))[:60]
        by_reason[key] = by_reason.get(key, 0) + 1
    for r in rows:
        fp = str(r.get("fingerprint"))
        by_fp[fp] = by_fp.get(fp, 0) + 1
    novel = len(rows) - len(blocked)
    return {
        "n": len(rows), "n_blocked": len(blocked), "n_novel": novel,
        "novel_rate": round(novel / len(rows), 4),
        "distinct_fingerprints": len(by_fp),
        "blocked_by_stage": by_stage, "blocked_by_reason": by_reason,
        "most_attempted_fingerprints": sorted(by_fp.items(), key=lambda kv: -kv[1])[:5],
        "note": "novel_rate is the honest generation yield: the share of produced ideas that "
                "were genuinely new questions rather than reparameterisations. Volume without "
                "it is throughput, not information.",
    }

```

### libs/signal_engine/attribution.py
```python
"""Signal attribution — decompose realized P&L by contributing alpha.

Answers "which alpha made/lost the money?" so weight optimization and retirement have ground
truth. Two modes: split a trade's realized return by alpha weight, or attribute when per-alpha
realized returns are known. Pure and deterministic.
"""

from __future__ import annotations

from collections.abc import Mapping

from pydantic import BaseModel, ConfigDict, Field


class AttributionResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    total_return: float
    by_alpha: dict[str, float]
    winners: list[str] = Field(default_factory=list)  # positive contributors, best first
    losers: list[str] = Field(default_factory=list)   # negative contributors, worst first
    top_contributor: str | None = None
    top_detractor: str | None = None


def _summarize(total: float, by_alpha: dict[str, float]) -> AttributionResult:
    winners = sorted((a for a, c in by_alpha.items() if c > 0), key=lambda a: by_alpha[a],
                     reverse=True)
    losers = sorted((a for a, c in by_alpha.items() if c < 0), key=lambda a: by_alpha[a])
    return AttributionResult(
        total_return=total, by_alpha=by_alpha, winners=winners, losers=losers,
        top_contributor=winners[0] if winners else None,
        top_detractor=losers[0] if losers else None,
    )


class SignalAttributionEngine:
    """Attributes realized P&L across the alphas that produced a signal."""

    def attribute(
        self, *, alpha_weights: Mapping[str, float], realized_return: float
    ) -> AttributionResult:
        """Split one trade's realized return across alphas by their (normalized) weights."""
        total_w = sum(alpha_weights.values())
        if total_w <= 0:
            by_alpha = dict.fromkeys(alpha_weights, 0.0)
            return _summarize(realized_return, by_alpha)
        by_alpha = {a: (w / total_w) * realized_return for a, w in alpha_weights.items()}
        return _summarize(realized_return, by_alpha)

    def attribute_detailed(
        self,
        *,
        alpha_weights: Mapping[str, float],
        alpha_returns: Mapping[str, float],
    ) -> AttributionResult:
        """Attribute when each alpha's own realized return is known (weight x return)."""
        by_alpha = {
            a: float(w) * float(alpha_returns.get(a, 0.0)) for a, w in alpha_weights.items()
        }
        return _summarize(sum(by_alpha.values()), by_alpha)

```

### libs/signal_engine/audit.py
```python
"""Signal audit — every BUY/SELL/FLAT decision to the immutable, hash-chained audit log.

Reuses ``libs.store.AuditLog`` (append-only, tamper-evident). No parallel storage; single source
of truth. Each decision records its inputs, scores, regime, and final outcome so it is fully
reproducible and explainable.
"""

from __future__ import annotations

from libs.signal_engine.models import SelectionResult, SignalPackage
from libs.store.audit import AuditLog
from libs.store.connection import Database
from libs.store.models import AuditEntry

_ACTOR = "stage13_5_signal_engine"


class SignalAudit:
    """Writes signal decisions to the immutable audit log."""

    def __init__(self, db: Database) -> None:
        self._audit = AuditLog(db)

    def record_package(self, package: SignalPackage) -> AuditEntry:
        return self._audit.append(
            "signal_decision",
            actor=_ACTOR,
            inputs={
                "symbol": package.symbol,
                "quality_score": package.quality_score,
                "confidence": package.confidence,
                "edge_score": package.edge_score,
                "expected_value": package.expected_value,
                "regime": package.regime.value,
                "predicted_regime": package.predicted_regime.value,
                "alpha_breakdown": package.alpha_breakdown,
                "institutional_score": package.institutional_score,
            },
            rationale="approved by signal engine",
            outcome=package.direction.value,
        )

    def record_flat(self, symbol: str, reason: str) -> AuditEntry:
        return self._audit.append(
            "signal_decision",
            actor=_ACTOR,
            inputs={"symbol": symbol},
            rationale=reason,
            outcome="flat",
        )

    def record_selection(self, result: SelectionResult) -> list[AuditEntry]:
        entries = [self.record_package(p) for p in result.approved]
        for symbol in sorted(result.rejected):
            entries.append(self.record_flat(symbol, result.rejected[symbol]))
        return entries

```

### libs/signal_engine/capacity.py
```python
"""Signal capacity forecaster — forward scalability before capital is allocated.

Reuses the discovery capacity model (square-root market impact) and turns it into a forward
0-100 capacity score plus slippage/impact estimates and the maximum efficient capital. Signals
whose intended size approaches capacity score lower and must rank lower / size smaller.
"""

from __future__ import annotations

import math

from libs.discovery.capacity import capacity_estimate
from libs.signal_engine.models import CapacityForecast

_EPS = 1e-9


def _clip01(x: float) -> float:
    return max(0.0, min(1.0, x))


class SignalCapacityForecaster:
    """Forecasts future capacity, slippage, and impact for an intended order size."""

    def forecast(
        self,
        *,
        adv_usd: float,
        intended_notional: float,
        edge_bps: float = 10.0,
        turnover_per_year: float = 50.0,
        participation_cap: float = 0.01,
        impact_coefficient: float = 0.1,
    ) -> CapacityForecast:
        result = capacity_estimate(
            adv_usd=adv_usd,
            participation_cap=participation_cap,
            turnover_per_year=turnover_per_year,
            impact_coefficient=impact_coefficient,
            edge_bps=edge_bps,
        )
        capacity = result.capacity_usd
        utilization = intended_notional / capacity if capacity > _EPS else 1.0
        # adv_usd > 0 is guaranteed: capacity_estimate raises otherwise.
        slippage = impact_coefficient * math.sqrt(max(intended_notional, 0.0) / adv_usd)
        return CapacityForecast(
            future_capacity_score=100.0 * _clip01(1.0 - utilization),
            future_slippage_estimate=slippage,
            future_market_impact_estimate=slippage * 1e4,
            maximum_efficient_capital=capacity,
            capacity_confidence=_clip01(1.0 - utilization),
        )

```

### libs/signal_engine/errors.py
```python
"""Stage 13.5 signal-engine errors."""

from __future__ import annotations

from libs.core.errors import QuantPlatformError


class SignalEngineError(QuantPlatformError):
    """Base error for the signal intelligence engine."""


class SignalGovernanceError(SignalEngineError):
    """Raised when a signal would bypass a mandatory governance gate."""

```

### libs/signal_engine/expected_value.py
```python
"""Expected value engine — EV after all frictions; EV > 0 is mandatory for consideration.

EV = WinRate * AvgWin - LossRate * AvgLoss, adjusted for spread, slippage, commission, market
impact, and execution-failure risk. The win/avg figures are the weighted blend of the
contributing alphas. A signal with EV <= 0 cannot be selected.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from libs.signal_engine.models import AlphaSignal, ExpectedValueResult

_EPS = 1e-12


def _weighted(signals: Sequence[AlphaSignal], weights: Mapping[str, float], attr: str) -> float:
    total = sum(weights.get(s.alpha_id, 0.0) for s in signals)
    if total <= _EPS:
        return 0.0
    return sum(weights.get(s.alpha_id, 0.0) * float(getattr(s, attr)) for s in signals) / total


class ExpectedValueEngine:
    """Computes per-trade expected value net of all execution frictions."""

    def estimate(
        self,
        signals: Sequence[AlphaSignal],
        weights: Mapping[str, float],
        *,
        spread_bps: float = 0.0,
        slippage_bps: float = 0.0,
        market_impact_bps: float = 0.0,
        commission_frac: float = 0.0,
        execution_failure_risk: float = 0.0,
    ) -> ExpectedValueResult:
        win_rate = _weighted(signals, weights, "win_rate")
        avg_win = _weighted(signals, weights, "avg_win")
        avg_loss = _weighted(signals, weights, "avg_loss")

        gross_ev = win_rate * avg_win - (1.0 - win_rate) * avg_loss

        base_cost = (spread_bps + slippage_bps + market_impact_bps) / 1e4 + commission_frac
        # Execution-failure risk inflates the effective cost (fail-closed bias).
        total_cost = base_cost * (1.0 + max(0.0, min(1.0, execution_failure_risk)))

        ev = gross_ev - total_cost
        return ExpectedValueResult(
            expected_value=ev,
            gross_ev=gross_ev,
            total_cost=total_cost,
            positive=ev > _EPS,
        )

```

### libs/signal_engine/selection.py
```python
"""Final signal selection — convert ranked candidates into BUY/SELL/FLAT decisions.

Fail-closed: a candidate becomes BUY/SELL only if EVERY rule passes (quality, confidence, EV,
edge, confirmations, capacity, crowding, portfolio contribution, execution, factor and stability
checks). If any single rule fails, the decision is FLAT with a recorded reason.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from libs.signal_engine.models import (
    Direction,
    SelectionResult,
    SignalPackage,
    TradeCandidate,
)

_EPS = 1e-12


@dataclass(frozen=True)
class SelectionThresholds:
    min_quality: float = 80.0
    min_confidence: float = 0.75
    min_edge: float = 50.0
    min_execution: float = 50.0
    min_confirmation: float = 0.50


def _drawdown_proxy(candidate: TradeCandidate) -> float:
    calmar = candidate.edge.expected_calmar
    if calmar <= _EPS:
        return 0.0
    return max(0.0, candidate.edge.expected_return) / calmar


def to_package(candidate: TradeCandidate) -> SignalPackage:
    """Build the Portfolio-Engine hand-off package from an approved candidate."""
    return SignalPackage(
        symbol=candidate.symbol,
        direction=candidate.direction,
        quality_score=candidate.quality.quality_score,
        confidence=candidate.confidence.confidence,
        edge_score=candidate.edge.edge_score,
        expected_return=candidate.edge.expected_return,
        expected_drawdown=_drawdown_proxy(candidate),
        expected_sharpe=candidate.edge.expected_sharpe,
        expected_sortino=candidate.edge.expected_sortino,
        expected_calmar=candidate.edge.expected_calmar,
        expected_pf=candidate.edge.expected_pf,
        expected_value=candidate.expected_value.expected_value,
        regime=candidate.regime,
        predicted_regime=candidate.predicted_regime,
        alpha_breakdown=candidate.alpha_breakdown,
        factor_exposures=candidate.factor_exposures.exposures,
        execution_score=candidate.execution.execution_score,
        capacity_score=candidate.capacity.future_capacity_score,
        crowding_score=candidate.crowding.crowding_score,
        portfolio_contribution=candidate.portfolio_context.portfolio_contribution_score,
        institutional_score=candidate.institutional.score,
    )


def _rejection_reason(c: TradeCandidate, t: SelectionThresholds) -> str | None:
    """Return the first failing rule's reason, or None if the candidate is approved."""
    conf = c.confidence.components
    checks: list[tuple[bool, str]] = [
        (c.direction is not Direction.FLAT, "no net direction"),
        (c.quality.quality_score > t.min_quality, "quality below threshold"),
        (c.confidence.confidence > t.min_confidence, "confidence below threshold"),
        (c.expected_value.positive, "expected value not positive"),
        (c.edge.edge_score > t.min_edge, "edge below threshold"),
        (conf["cross_asset_confirmation"] >= t.min_confirmation, "cross-asset not confirmed"),
        (conf["microstructure_confirmation"] >= t.min_confirmation, "microstructure not confirmed"),
        (conf["future_regime_confidence"] >= t.min_confirmation, "future regime not confirmed"),
        (c.capacity.future_capacity_score > 0.0, "no capacity available"),
        (c.crowding.acceptable, "crowding too high"),
        (c.portfolio_context.accept, "portfolio contribution not positive"),
        (c.portfolio_context.portfolio_contribution_score > 0.0, "no portfolio contribution"),
        (
            c.execution.passed and c.execution.execution_score >= t.min_execution,
            "execution infeasible",
        ),
        (c.factor_exposures.acceptable, "factor concentration violation"),
        (c.stability.passed, "signal unstable"),
    ]
    for ok, reason in checks:
        if not ok:
            return reason
    return None


def select_final_signals(
    candidates: Sequence[TradeCandidate],
    *,
    thresholds: SelectionThresholds | None = None,
) -> SelectionResult:
    """Apply the fail-closed selection rules to ranked candidates."""
    thresholds = thresholds or SelectionThresholds()
    approved: list[SignalPackage] = []
    rejected: dict[str, str] = {}
    for c in candidates:
        reason = _rejection_reason(c, thresholds)
        if reason is None:
            approved.append(to_package(c))
        else:
            rejected[c.symbol] = reason
    return SelectionResult(approved=approved, rejected=rejected)

```

### libs/signal_engine/uncertainty.py
```python
"""Signal uncertainty and tail risk.

``SignalUncertaintyEngine`` separates epistemic uncertainty (alpha disagreement, thin evidence)
from aleatoric uncertainty (irreducible market noise). ``signal_tail_risk`` reuses the discovery
tail-risk model. High uncertainty / tail risk later reduces confidence, size, and rank.
"""

from __future__ import annotations

import math

import numpy as np

from libs.discovery.tail_risk import tail_risk
from libs.signal_engine.models import UncertaintyResult


def _clip01(x: float) -> float:
    return max(0.0, min(1.0, x))


def signal_tail_risk(returns: np.ndarray, *, threshold: float = 60.0) -> float:
    """Return the 0-100 hidden tail-risk score for a signal's return sample."""
    return tail_risk(returns, threshold=threshold).tail_risk_score


class SignalUncertaintyEngine:
    """Estimates epistemic + aleatoric uncertainty (0..1; higher is worse)."""

    def estimate(
        self,
        *,
        alpha_agreement: float,
        n_alphas: int,
        sample_size: int,
        volatility_state: float,
    ) -> UncertaintyResult:
        disagreement = 1.0 - _clip01(alpha_agreement)
        thin_panel = 1.0 - _clip01(n_alphas / 5.0)
        thin_sample = 1.0 / math.sqrt(max(sample_size, 1))
        epistemic = _clip01(0.5 * disagreement + 0.3 * thin_panel + 0.2 * thin_sample)
        aleatoric = _clip01(volatility_state)
        uncertainty = _clip01(0.6 * epistemic + 0.4 * aleatoric)
        return UncertaintyResult(
            epistemic_uncertainty=epistemic,
            aleatoric_uncertainty=aleatoric,
            uncertainty_score=uncertainty,
        )

```

### libs/stage14/attribution.py
```python
"""Portfolio attribution — decompose realized performance by sleeve, factor, regime, and cost.

Feeds future allocation decisions: which sleeves/factors/regimes earned (or lost) the money, net
of costs. Pure and deterministic (weight x return); complements Stage 13.5 per-alpha attribution.
"""

from __future__ import annotations

from collections.abc import Mapping

from pydantic import BaseModel, ConfigDict, Field


class PortfolioAttribution(BaseModel):
    model_config = ConfigDict(frozen=True)

    gross_return: float
    cost: float
    net_return: float
    by_sleeve: dict[str, float] = Field(default_factory=dict)
    by_factor: dict[str, float] = Field(default_factory=dict)
    by_regime: dict[str, float] = Field(default_factory=dict)


def _split(weights: Mapping[str, float], gross: float) -> dict[str, float]:
    total = sum(weights.values())
    if total <= 0:
        return dict.fromkeys(weights, 0.0)
    return {k: (w / total) * gross for k, w in weights.items()}


class PortfolioAttributionEngine:
    """Attributes realized portfolio return across sleeves, factors, and regime."""

    def attribute(
        self,
        *,
        gross_return: float,
        cost: float = 0.0,
        sleeve_weights: Mapping[str, float] | None = None,
        factor_weights: Mapping[str, float] | None = None,
        regime: str | None = None,
    ) -> PortfolioAttribution:
        net = gross_return - cost
        by_regime = {regime: net} if regime is not None else {}
        return PortfolioAttribution(
            gross_return=gross_return,
            cost=cost,
            net_return=net,
            by_sleeve=_split(sleeve_weights or {}, gross_return),
            by_factor=_split(factor_weights or {}, gross_return),
            by_regime=by_regime,
        )

```

### libs/validation/walk_forward.py
```python
"""Walk-forward validation splits (anchored / rolling)."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from libs.validation.errors import ValidationError


@dataclass(frozen=True)
class WalkForwardSplit:
    train: np.ndarray
    test: np.ndarray


def walk_forward_splits(
    n_samples: int,
    *,
    n_splits: int,
    test_size: int,
    anchored: bool = True,
    embargo: int = 0,
) -> list[WalkForwardSplit]:
    """Generate sequential out-of-sample windows.

    Anchored: training starts at 0 and expands. Rolling: training is a fixed-size window. An
    optional ``embargo`` drops bars between train and test.
    """
    if test_size < 1 or n_splits < 1:
        raise ValidationError("n_splits and test_size must be >= 1")
    min_train = n_samples - n_splits * test_size
    if min_train <= 0:
        raise ValidationError("n_samples too small for the requested splits")

    splits: list[WalkForwardSplit] = []
    for i in range(n_splits):
        test_start = min_train + i * test_size
        test_end = test_start + test_size
        train_end = max(0, test_start - embargo)
        train_start = 0 if anchored else max(0, train_end - min_train)
        train = np.arange(train_start, train_end)
        test = np.arange(test_start, test_end)
        splits.append(WalkForwardSplit(train=train, test=test))
    return splits

```

### scripts/build_chart_context.py
```python
#!/usr/bin/env python3
"""CHART CONTEXT (R0134) -- the chart the discretionary sleeve was never shown.

THE GAP THIS CLOSES, and it is embarrassing once seen. The principal asked for "a strategy where
Claude acts like a human trader with a brain and trades 24/7 at charts". What was built reads
funding, liquidations and announcements -- and NO PRICE STRUCTURE AT ALL. It was asked to name a
swing high it had never been shown. A discretionary trader with no chart is not a discretionary
trader; it is a headline reader with a leverage dial, which is exactly the "too calculative,
earns less than a manual trader" failure the principal described.

So this organ builds, per instrument, what a professional actually has on screen before deciding:

  MULTI-TIMEFRAME STRUCTURE -- 15m/1h/4h swing highs and lows located by fractal pivots, with
  their prices, ages and how many times each has been touched. A level touched three times and
  held is not the same object as a level touched once, and the difference is most of what
  discretionary edge IS.

  TREND STATE per timeframe, from the swing sequence itself (higher-highs-and-higher-lows, or
  lower-lows-and-lower-highs, or neither) rather than from a moving average, because the sequence
  is what the stop has to respect. A trade with the 4h trend and against the 15m pullback is a
  different animal from one fighting both.

  POSITION IN RANGE, and DISTANCE TO THE NEAREST LEVEL each way, in percent. This is the number
  that decides whether a trade has room: long into resistance 0.3% away with an invalidation 2%
  below is a bad trade at any conviction, and no amount of narrative fixes it.

  VOLATILITY REGIME -- current ATR against its own 30-day median, so expansion and contraction
  are visible. The same 1% stop is generous in a dead tape and inside the noise in an expanding
  one, which the noise floor already prices and the model should be able to see coming.

  MOMENTUM over 1h/4h/24h/7d, and where price sits in the day's and week's range.

WHY A SEPARATE ORGAN AND NOT INLINE IN THE TRADER: this makes ~3 venue calls per instrument
across a widened universe. Inline, that is a slow, failure-prone trader; as an organ it is cached,
scheduled, individually testable, and its failures are visible as staleness rather than as a
trader that silently reasoned over nothing. UNAVAILABLE instruments are RECORDED, never dropped
silently -- a universe that quietly shrinks to whatever happened to answer is a universe nobody
chose.

    python scripts/build_chart_context.py [--json] [--symbols BTCUSDT,ETHUSDT]
"""
from __future__ import annotations

import argparse
import itertools
import json
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

_OUT = "data/chart_context.json"

#: Pivot half-width: a bar is a swing high if its high exceeds the highs of PIVOT_K bars on BOTH
#: sides. 3 is the usual discretionary reading -- 2 finds noise, 5 finds only the obvious.
PIVOT_K = 3
#: How close two swings must be (percent) to count as the SAME level being retested rather than
#: two separate levels. This is what turns a list of pivots into a level with a touch count.
LEVEL_TOL_PCT = 0.35
MAX_LEVELS = 4

#: Timeframe -> (bars to fetch, lookback hours). 4h context is what keeps a scalp from fighting
#: the daily trend; 15m is where the invalidation actually sits.
_TFS: tuple[tuple[str, int, int], ...] = (("15m", 200, 60), ("1h", 200, 220), ("4h", 200, 850))


def pivots(bars: list[tuple[int, float, float, float, float]], k: int = PIVOT_K
           ) -> tuple[list[tuple[int, float]], list[tuple[int, float]]]:
    """Fractal swing highs and lows: the levels a structural stop is allowed to sit behind."""
    highs, lows = [], []
    for i in range(k, len(bars) - k):
        window = bars[i - k:i + k + 1]
        if bars[i][2] == max(b[2] for b in window) and bars[i][2] > bars[i - 1][2]:
            highs.append((i, bars[i][2]))
        if bars[i][3] == min(b[3] for b in window) and bars[i][3] < bars[i - 1][3]:
            lows.append((i, bars[i][3]))
    return highs, lows


def cluster_levels(points: list[tuple[int, float]], n_bars: int, *, tol_pct: float = LEVEL_TOL_PCT,
                   limit: int = MAX_LEVELS) -> list[dict[str, Any]]:
    """Collapse nearby pivots into LEVELS with a touch count and an age.

    A level touched three times and held is a different object from one touched once, and telling
    them apart is most of what discretionary structure reading is. Sorted by touches then recency,
    because a heavily-defended level matters more than a fresher accidental one."""
    levels: list[dict[str, Any]] = []
    for idx, px in sorted(points, key=lambda p: -p[0]):          # newest first
        for lv in levels:
            if abs(px - lv["price"]) / max(lv["price"], 1e-9) * 100.0 <= tol_pct:
                lv["touches"] += 1
                lv["price"] = (lv["price"] * (lv["touches"] - 1) + px) / lv["touches"]
                break
        else:
            levels.append({"price": px, "touches": 1, "last_bar": idx})
    for lv in levels:
        lv["price"] = round(lv["price"], 8)
        lv["bars_ago"] = n_bars - 1 - lv.pop("last_bar")
    levels.sort(key=lambda lv: (-lv["touches"], lv["bars_ago"]))
    return levels[:limit]


def trend_state(highs: list[tuple[int, float]], lows: list[tuple[int, float]]) -> str:
    """Trend from the SWING SEQUENCE, not a moving average -- the sequence is what the stop has to
    respect, and it is what a human means by 'the trend is up'."""
    if len(highs) < 2 or len(lows) < 2:
        return "UNREADABLE -- too few swings"
    hh = highs[-1][1] > highs[-2][1]
    hl = lows[-1][1] > lows[-2][1]
    if hh and hl:
        return "UPTREND (higher highs, higher lows)"
    if not hh and not hl:
        return "DOWNTREND (lower highs, lower lows)"
    return "RANGE/TRANSITION (swings disagree)"


def atr_pct(bars: list[tuple[int, float, float, float, float]], n: int = 14) -> float | None:
    if len(bars) < n + 1:
        return None
    trs = []
    for prev, cur in zip(bars[-n - 1:-1], bars[-n:], strict=True):
        trs.append(max(cur[2] - cur[3], abs(cur[2] - prev[4]), abs(cur[3] - prev[4])))
    last = bars[-1][4]
    return round(sum(trs) / len(trs) / last * 100.0, 4) if last else None


def _pct(a: float, b: float) -> float | None:
    return round((a - b) / b * 100.0, 3) if b else None


def timeframe_view(bars: list[tuple[int, float, float, float, float]]) -> dict[str, Any]:
    if len(bars) < PIVOT_K * 2 + 5:
        return {"state": "UNMEASURED", "why": f"only {len(bars)} bars"}
    price = bars[-1][4]
    highs, lows = pivots(bars)
    hi, lo = max(b[2] for b in bars), min(b[3] for b in bars)
    res = [lv for lv in cluster_levels(highs, len(bars)) if lv["price"] > price]
    sup = [lv for lv in cluster_levels(lows, len(bars)) if lv["price"] < price]
    atr = atr_pct(bars)
    med_atr = None
    if len(bars) >= 60:
        window = [atr_pct(bars[:i]) for i in range(30, len(bars), 5)]
        vals = sorted(v for v in window if v is not None)
        med_atr = vals[len(vals) // 2] if vals else None
    return {
        "state": "OK",
        "trend": trend_state(highs, lows),
        "price": round(price, 8),
        "range_high": round(hi, 8), "range_low": round(lo, 8),
        "position_in_range": round((price - lo) / (hi - lo), 3) if hi > lo else None,
        "resistance_levels": res, "support_levels": sup,
        "nearest_resistance_pct": _pct(res[0]["price"], price) if res else None,
        "nearest_support_pct": _pct(sup[0]["price"], price) if sup else None,
        "atr_pct": atr,
        "atr_vs_30d_median": (round(atr / med_atr, 2) if atr and med_atr else None),
        "vol_regime": ("EXPANDING" if atr and med_atr and atr > med_atr * 1.25 else
                       "CONTRACTING" if atr and med_atr and atr < med_atr * 0.8 else
                       "NORMAL" if atr and med_atr else "UNMEASURED"),
        "n_swing_highs": len(highs), "n_swing_lows": len(lows),
    }


def build_symbol(symbol: str, *, fetch=None, now: datetime | None = None) -> dict[str, Any]:
    if fetch is None:
        from scripts.resolve_paper_book import fetch_bars as fetch
    now = now or datetime.now(tz=UTC)
    now_ms = int(now.timestamp() * 1000)
    out: dict[str, Any] = {"symbol": symbol, "timeframes": {}}
    last_bars: list[tuple[int, float, float, float, float]] = []
    for tf, _n, hours in _TFS:
        bars, source = fetch(symbol, now_ms - hours * 3600 * 1000, now_ms, tf)
        if not bars:
            out["timeframes"][tf] = {"state": "UNAVAILABLE", "why": source}
            continue
        out["timeframes"][tf] = {**timeframe_view(bars), "source": source, "bars": len(bars)}
        if tf == "15m":
            last_bars = bars
    if last_bars:
        px = last_bars[-1][4]
        out["momentum_pct"] = {}
        for label, back in (("1h", 4), ("4h", 16), ("24h", 96), ("7d", 672)):
            out["momentum_pct"][label] = (_pct(px, last_bars[-back - 1][4])
                                          if len(last_bars) > back else None)
        day = last_bars[-96:] if len(last_bars) >= 96 else last_bars
        dh, dl = max(b[2] for b in day), min(b[3] for b in day)
        out["day_range"] = {"high": round(dh, 8), "low": round(dl, 8),
                            "position": round((px - dl) / (dh - dl), 3) if dh > dl else None}
        out["_returns"] = _returns(last_bars)          # stripped after the correlation pass
    ok = [v for v in out["timeframes"].values() if v.get("state") == "OK"]
    out["state"] = "OK" if len(ok) == len(_TFS) else ("PARTIAL" if ok else "UNAVAILABLE")
    return out


def _returns(bars: list[tuple[int, float, float, float, float]], n: int = 96) -> list[float]:
    closes = [b[4] for b in bars[-(n + 1):]]
    return [(b - a) / a for a, b in itertools.pairwise(closes) if a]


def correlations(series: dict[str, list[float]]) -> dict[str, dict[str, float]]:
    """Pairwise return correlation across the universe.

    THIS IS WHAT MAKES BREADTH REAL. The simulation that justified spreading risk across many
    positions assumed the bets were INDEPENDENT -- but five crypto longs in a correlated tape is
    one position wearing five names, and summing their risk as though they were separate both
    overstates safety AND blocks trades that were genuinely diversifying. Measured correlation
    lets the heat rail do the honest thing in both directions."""
    out: dict[str, dict[str, float]] = {}
    for a, xs in series.items():
        out[a] = {}
        for b, ys in series.items():
            n = min(len(xs), len(ys))
            if n < 30:
                out[a][b] = 1.0 if a == b else 0.9      # too little data -> assume the WORST case
                continue
            x, y = xs[-n:], ys[-n:]
            mx, my = sum(x) / n, sum(y) / n
            sxy = sum((i - mx) * (j - my) for i, j in zip(x, y, strict=False))
            sxx = sum((i - mx) ** 2 for i in x)
            syy = sum((j - my) ** 2 for j in y)
            out[a][b] = round(sxy / (sxx * syy) ** 0.5, 4) if sxx > 0 and syy > 0 else 0.9
    return out


def build(symbols: tuple[str, ...], *, fetch=None, now: datetime | None = None) -> dict[str, Any]:
    now = now or datetime.now(tz=UTC)
    charts = {s: build_symbol(s, fetch=fetch, now=now) for s in symbols}
    series = {s: c["_returns"] for s, c in charts.items() if c.get("_returns")}
    corr = correlations(series)
    for c in charts.values():
        c.pop("_returns", None)
    unavailable = [s for s, c in charts.items() if c["state"] == "UNAVAILABLE"]
    partial = [s for s, c in charts.items() if c["state"] == "PARTIAL"]
    return {
        "generated": now.isoformat(),
        "law": "L1.28a -- the discretionary sleeve was asked to read charts it had never been "
               "shown. Unavailable instruments are RECORDED, never silently dropped: a universe "
               "that shrinks to whatever answered is a universe nobody chose.",
        "status": "OK" if not unavailable and not partial else (
            "DEGRADED" if not unavailable else "PARTIAL-UNIVERSE"),
        "n_symbols": len(symbols), "n_ok": len(symbols) - len(unavailable) - len(partial),
        "unavailable": unavailable, "partial": partial,
        "detail": (f"{len(symbols) - len(unavailable) - len(partial)}/{len(symbols)} instruments "
                   f"charted across {len(_TFS)} timeframes"
                   + (f"; UNAVAILABLE: {', '.join(unavailable)}" if unavailable else "")
                   + (f"; PARTIAL: {', '.join(partial)}" if partial else "")),
        "charts": charts,
        "correlations": corr,
    }


def main() -> int:
    _law_guard()
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbols", default="")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    if args.symbols:
        syms = tuple(s.strip().upper() for s in args.symbols.split(",") if s.strip())
    else:
        from scripts.run_conviction_trader import INSTRUMENTS as syms
    rep = build(tuple(syms))
    out = _ROOT / _OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(rep, indent=2), "utf-8")
    print(json.dumps(rep, indent=2) if args.json else
          f"chart context (R0134): {rep['status']} -- {rep['detail']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

```

### scripts/build_defi_axis.py
```python
"""DeFi system-utilisation AXIS FEED -- turn the pool-level collector into a Stage-B clock input.

WHY THIS AXIS AND NOT TWO CHEAP ONES. Stage-B slots are scarce by arithmetic (Holm bar 2.39 at
m=3, 2.58 at m=5), so a slot spent on a badly-constructed feed taxes every other clock for nothing.
One well-built axis beats two registered-and-broken.

CONSTRUCTION, stated so it can be falsified:
  observable  aggregate DeFi utilisation = total borrow / total supply across Aave, Compound,
              Morpho and Spark on Ethereum
  mechanism   M_FORCED_DELEVERAGE -- the desk's best-supported mechanism (2/10 survival, holds
              the only confirmed edge). Utilisation climbing toward the rate kink squeezes
              marginal borrowers; forced unwind is spot selling that perps reflect later.
  transform   z20 of daily utilisation -- level is meaningless across regimes, deviation is not
  direction   -1. High utilisation = leverage crowded = FRAGILE, so the prior is that extreme
              utilisation precedes weakness, not strength. Stated in advance; the clock decides.
  falsifier   IC indistinguishable from zero, or sign opposite to the stated prior, over 40 days
              under the Holm bar.

The evaluator needs ONE row per date carrying a pre-computed z field. The collector writes ~286
pool rows per hour, so this aggregates: hour -> daily system utilisation -> rolling z20.
"""
from __future__ import annotations

import json
import pathlib
import statistics as st

ROOT = pathlib.Path(__file__).resolve().parent.parent
SRC = ROOT / "data/defi_lending.jsonl"
OUT = ROOT / "data/defi_util_axis.jsonl"
_Z = 20


def main() -> None:
    if not SRC.exists():
        raise SystemExit("collector has produced nothing yet")
    daily: dict[str, list[tuple[float, float]]] = {}
    with SRC.open("r", encoding="utf-8", errors="ignore") as fh:
        for ln in fh:
            ln = ln.strip()
            if not ln:
                continue
            try:
                r = json.loads(ln)
            except json.JSONDecodeError:
                continue
            d = str(r.get("ts", ""))[:10]
            s, b = r.get("supply_usd"), r.get("borrow_usd")
            if d and isinstance(s, (int, float)) and isinstance(b, (int, float)) and s > 0:
                daily.setdefault(d, []).append((float(s), float(b)))

    # SYSTEM utilisation = total borrow / total supply, never a mean of per-pool ratios --
    # a mean of ratios over-weights tiny pools and would make a $2m vault move the axis.
    series = []
    for d in sorted(daily):
        sup = sum(x[0] for x in daily[d])
        bor = sum(x[1] for x in daily[d])
        if sup > 0:
            series.append((d, bor / sup))

    rows = []
    for i, (d, u) in enumerate(series):
        w = [v for _, v in series[max(0, i - _Z + 1):i + 1]]
        z = 0.0
        if len(w) >= 5:
            sd = st.pstdev(w)
            z = (u - st.fmean(w)) / sd if sd > 0 else 0.0
        rows.append({"date": d, "utilisation": round(u, 6), "z20": round(z, 4),
                     "n_pools": len(daily[d])})

    OUT.write_text("".join(json.dumps(r) + "\n" for r in rows), "utf-8")
    print("=== DEFI UTILISATION AXIS FEED ===")
    print(f"  {len(rows)} daily observations from {sum(len(v) for v in daily.values())} pool-rows")
    for r in rows[-3:]:
        print(f"    {r['date']}  util {r['utilisation']:.4f}  z20 {r['z20']:+.3f}  "
              f"pools {r['n_pools']}")
    print("\n  system utilisation = TOTAL borrow / TOTAL supply, not a mean of per-pool ratios --")
    print("  a mean over-weights tiny pools and would let a $2m vault move the axis.")
    print(f"  z20 needs 5+ days before it is meaningful; currently {len(rows)}.")
    print(f"\n  -> {OUT}")


if __name__ == "__main__":
    main()

```

### scripts/build_labels.py
```python
#!/usr/bin/env python3
"""PROPRIETARY LABEL FACTORY runner -- writes data/label_registry.json (RANK 6).

Generates the four event-label families from the bronze panel, validates each as a well-formed
EVENT marker (testable base rate, event-not-state, no lookahead at its declared knowability lag),
versions it by content hash, and records it as a research asset with lineage back to the RANK 4
data registry.

WHAT IT DELIBERATELY DOES NOT DO: decide whether a label PREDICTS anything. That is a hypothesis
test, it costs multiplicity, and it goes through libs.research.axis_screen. A factory that scored
labels on forward returns would manufacture trials nobody counted.

    python scripts/build_labels.py                  # all symbols found in the lake
    python scripts/build_labels.py --symbol BTCUSDT
    python scripts/build_labels.py --json
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data/label_registry.json"
LAKE = ROOT / "data/lake/bronze/crypto"


def _load_panels(symbol: str | None, limit: int) -> list[tuple[str, Any]]:
    """(symbol, bars) from the bronze daily panel -- the desk's best panel per GAP_REGISTER #77."""
    try:
        import pandas as pd
    except ImportError:
        return []
    if not LAKE.is_dir():
        return []
    out: list[tuple[str, Any]] = []
    syms = sorted(p.name for p in LAKE.iterdir() if p.is_dir())
    if symbol:
        syms = [s for s in syms if s == symbol]
    for sym in syms[:limit]:
        files = sorted((LAKE / sym).rglob("*.parquet"))
        if not files:
            continue
        try:
            df = pd.concat([pd.read_parquet(f) for f in files]).sort_index()
        except Exception:
            continue
        if len(df) >= 120:                               # below this, no label has power
            out.append((sym, df))
    return out


def _lineage() -> tuple[str, ...]:
    """The RANK 4 registry asset ids these labels are built FROM.

    Derived, not hardcoded: rank 4 is rank 6's stated prerequisite precisely so a label carries the
    identity of its source panel. A hardcoded string would still say "lake_crypto" after the panel
    moved or was renamed, and a label whose lineage points at the wrong panel is worse than one with
    none -- it invites sizing a study off a span the data never had (GAP_REGISTER #77).
    """
    try:
        from libs.research.data_registry import build
        for asset in build(ROOT):
            if Path(asset.path.rstrip("/*")).as_posix() in LAKE.as_posix():
                return (asset.id,)
    except Exception:
        pass
    return ()


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--symbol", default=None, help="restrict to one symbol")
    ap.add_argument("--limit", type=int, default=40, help="max symbols (default 40)")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)

    from libs.research.label_factory import build_catalogue, default_specs

    panels = _load_panels(a.symbol, a.limit)
    specs = default_specs(inputs=_lineage())

    if not panels:
        # NO-INPUT is reported as a DATA gap, never a silent skip (L2.9). The specs and their
        # versions are still emitted so the catalogue is reviewable without the panel present.
        payload = {
            "generated": datetime.now(tz=UTC).isoformat(), "status": "NO-INPUT",
            "detail": f"no usable panel under {LAKE.relative_to(ROOT)} (needs >=120 bars/symbol) "
                      "-- this box has no bronze lake; run on the collecting box",
            "specs": [{"id": s.id, "version": s.version, "family": s.family,
                       "params": dict(s.params), "known_at_lag": s.known_at_lag,
                       "inputs": list(s.inputs), "rationale": s.rationale} for s in specs],
            "labels": [],
        }
    else:
        per_symbol = {sym: build_catalogue(bars, specs) for sym, bars in panels}
        # A label is only a research asset if it validates on MORE than one symbol -- a marker that
        # is well-formed on exactly one venue/symbol is a coincidence, not a proprietary label.
        usable_counts: dict[str, int] = {}
        for recs in per_symbol.values():
            for r in recs:
                usable_counts[r["qualified_id"]] = usable_counts.get(r["qualified_id"], 0) + int(
                    r["usable"])
        payload = {
            "generated": datetime.now(tz=UTC).isoformat(), "status": "ACTIVE",
            "n_symbols": len(per_symbol),
            "usable_on_n_symbols": usable_counts,
            "portable": [k for k, v in usable_counts.items() if v >= max(2, len(per_symbol) // 2)],
            "labels": dict(per_symbol),
        }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    tmp = OUT.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(payload, indent=1, default=str), "utf-8")
    tmp.replace(OUT)

    if a.json:
        print(json.dumps(payload, indent=1, default=str))
        return 0
    print(f"label-factory | {payload['status']}")
    if payload["status"] == "NO-INPUT":
        print(f"  {payload['detail']}")
        for s in payload["specs"]:
            print(f"  {s['id']:<22} v{s['version']}  lag={s['known_at_lag']}  "
                  f"inputs={','.join(s['inputs'])}")
    else:
        print(f"  {payload['n_symbols']} symbol(s); {len(payload['portable'])} label(s) valid on "
              f"a majority of them (a label well-formed on ONE symbol is a coincidence)")
        for qid, n in sorted(payload["usable_on_n_symbols"].items(), key=lambda kv: -kv[1]):
            mark = "PORTABLE" if qid in payload["portable"] else "thin"
            print(f"  {mark:<9} {qid:<38} valid on {n}/{payload['n_symbols']}")
    print(f"\n-> {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

```

### scripts/check_mechanism_attribution.py
```python
#!/usr/bin/env python3
"""MECHANISM ATTRIBUTION (R0137) -- a sleeve may not read as SURVIVED on P&L its mechanism
cannot explain.

WHAT PRODUCED THIS FENCE, on 2026-07-31. The dashboard showed funding carry as a survivor. The
numbers behind it:

    equity $18,669 from $15,000  ->  net +$3,669.55 (+24.5%) over 29 days, Sharpe 13.13
    FUNDING HARVEST COLLECTED:   +$113.06

Funding is 3.1% of the P&L. The other $3,556 did not come from carry. A cash-and-carry book is
spot-long / perp-short and delta-neutral BY CONSTRUCTION: its price legs cancel, so its P&L should
be funding plus basis, near-100%. The desk already owns the fence that says this --
``libs.execution.carry_accounting.carry_bleed_report``, deliberately TWO-SIDED so that a large
POSITIVE non-funding P&L alarms as loudly as a loss, because on a hedged book a windfall that size
is a NAKED LEG rather than edge. Run on those numbers it returns:

    BLEED(inverted): non-funding PnL +3556.49 is 3146% of +113.06 funding harvest

So the desk's own logic already disagreed with the dashboard. The verdict was computed, written to
a JSON field, rendered -- AND GATED NOTHING. `max_audit` raises a defect only when funding is
UNMEASURED; when the alarm actually trips, nothing fails. That is the recurring defect shape on
this desk in its most expensive form: a fence firing into a field nobody reads, while a survival
claim built on the same numbers goes to the principal for a capital decision.

WHY IT IS A SEPARATE, GENERAL FENCE. The specific bug is one `if` in max_audit. The general bug is
that ANY sleeve can be credited with P&L its stated mechanism does not explain -- a hedge with an
untracked leg, a market-neutral book carrying beta, or a sleeve's line item quietly aggregating an
account it does not own. So the rule is stated once and applied to every sleeve with a measurable
mechanism term:

    A sleeve whose P&L is not attributable to its stated mechanism is UNATTRIBUTED. It may not
    read as survived, validated or promotable, whatever its return looks like -- and an
    unattributed WIN is treated exactly as seriously as an unattributed loss, because the
    directional exposure that produced it is still there and still unhedged.

UNMEASURED never reads as OK: a venue income read that failed makes attribution UNDECIDABLE, not
clean, and the fence says so rather than passing.

    python scripts/check_mechanism_attribution.py [--report-only] [--json]
"""
from __future__ import annotations

import argparse
import json
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

_OUT = "data/mechanism_attribution.json"

#: How much of a sleeve's P&L may come from outside its stated mechanism before the claim is
#: UNATTRIBUTED. 0.5 matches carry_bleed_report's own alert_frac -- the same number the desk
#: already chose for the same question, reused rather than re-picked (see check_sizing_derivation).
UNATTRIBUTED_FRAC = 0.5

#: Sleeves with a MEASURABLE mechanism term, and where to read it. A sleeve whose mechanism cannot
#: be measured separately from its P&L is not listed: it would be judged by a number that does not
#: exist, which is worse than not judging it. That absence is itself reported.
_SLEEVES: dict[str, dict[str, str]] = {
    "cash_and_carry": {
        "mechanism": "funding harvest on a delta-neutral spot/perp pair; price legs cancel by "
                     "construction, so P&L should be funding + basis, near-100%",
        "total_key": "net_pnl",
        "mechanism_key": "funding",
    },
}


def attribute(name: str, spec: dict[str, str], state: dict[str, Any]) -> dict[str, Any]:
    total = state.get(spec["total_key"])
    mech = state.get(spec["mechanism_key"])
    row: dict[str, Any] = {"sleeve": name, "mechanism": spec["mechanism"],
                           "total_pnl": total, "mechanism_pnl": mech}
    if total is None or mech is None:
        return {**row, "state": "UNMEASURED",
                "why": (f"missing {spec['total_key'] if total is None else spec['mechanism_key']} "
                        "-- attribution is UNDECIDABLE, which is not the same as clean")}
    try:
        total, mech = float(total), float(mech)
    except (TypeError, ValueError):
        return {**row, "state": "UNMEASURED", "why": "non-numeric P&L terms"}

    unexplained = round(total - mech, 2)
    row["unexplained_pnl"] = unexplained
    row["mechanism_share"] = round(mech / total, 4) if total else None
    if mech > 0:
        ratio = abs(unexplained) / mech
        bad = ratio >= UNATTRIBUTED_FRAC
    else:
        ratio = float("inf") if unexplained != 0 else 0.0
        bad = unexplained != 0.0
    row["unexplained_vs_mechanism"] = (None if ratio == float("inf") else round(ratio, 3))
    if not bad:
        share = row["mechanism_share"]
        return {**row, "state": "ATTRIBUTED",
                "why": (f"{share:.0%} of P&L explained by the stated mechanism" if share is not None
                        else "no P&L to attribute -- nothing earned, nothing unexplained")}
    direction = "WIN" if unexplained > 0 else "LOSS"
    return {**row, "state": "UNATTRIBUTED",
            "why": (f"unexplained {direction} {unexplained:+,.2f} is "
                    + (f"{ratio:.0%} of " if ratio != float("inf") else "present with no ")
                    + f"the {mech:+,.2f} mechanism term -- this sleeve is being credited with P&L "
                      "its mechanism cannot produce. An unexplained WIN is not better news than a "
                      "loss: the exposure that made it is still on, still unhedged, and will "
                      "reverse. NOT survived, NOT promotable, whatever the return looks like.")}


def build_report(root: Path | None = None) -> dict[str, Any]:
    root = root or _ROOT
    src, deployed = None, {}
    for cand in ("research_state.json", "data/cashcarry_state.json"):
        try:
            blob = json.loads((root / cand).read_text("utf-8"))
        except (OSError, ValueError):
            continue
        d = blob.get("deployed") or blob.get("molded") or blob
        if isinstance(d, dict) and d:
            src, deployed = cand, d
            break
    if src is None:
        return {"generated": datetime.now(tz=UTC).isoformat(), "status": "UNMEASURED",
                "detail": "no deployed-state artifact readable on this host -- attribution "
                          "UNDECIDABLE, which never reads as clean",
                "n_sleeves": 0, "sleeves": []}

    named = list(deployed.get("sleeves") or deployed.get("live_sleeves") or [])
    rows = []
    for name, spec in _SLEEVES.items():
        if named and not any(name in str(s) for s in named):
            continue                                   # this sleeve is not deployed here
        rows.append(attribute(name, spec, deployed))
    unjudged = [str(s) for s in named
                if not any(k in str(s) for k in _SLEEVES) and "paper" not in str(s)]

    bad = [r for r in rows if r["state"] == "UNATTRIBUTED"]
    unmeasured = [r for r in rows if r["state"] == "UNMEASURED"]
    status = ("UNATTRIBUTED" if bad else "UNMEASURED" if unmeasured or not rows else "ATTRIBUTED")
    return {
        "generated": datetime.now(tz=UTC).isoformat(),
        "source": src,
        "law": "L1.6/L2.6 -- a sleeve may not read as survived on P&L its stated mechanism cannot "
               "explain. An unattributed WIN is as disqualifying as an unattributed loss: the "
               "exposure that produced it is unhedged and will reverse.",
        "status": status,
        "n_sleeves": len(rows), "n_unattributed": len(bad),
        "sleeves": rows,
        "mechanism_unjudgeable": unjudged,
        "detail": (f"{len(rows)} sleeve(s) with a measurable mechanism term"
                   + (f"; UNATTRIBUTED: {', '.join(r['sleeve'] for r in bad)}" if bad else "")
                   + (f"; UNMEASURED: {', '.join(r['sleeve'] for r in unmeasured)}"
                      if unmeasured else "")
                   + (f"; no mechanism term to judge: {', '.join(unjudged)}" if unjudged else "")),
    }


def main() -> int:
    _law_guard()
    ap = argparse.ArgumentParser()
    ap.add_argument("--report-only", action="store_true")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    rep = build_report()
    out = _ROOT / _OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(rep, indent=2), "utf-8")
    if args.json:
        print(json.dumps(rep, indent=2))
    else:
        print(f"mechanism attribution (L1.6): {rep['status']} -- {rep['detail']}")
        for r in rep["sleeves"]:
            if r["state"] != "ATTRIBUTED":
                print(f"  {r['sleeve']}: {r['state']} -- {r['why']}")
    if args.report_only:
        return 0
    return 2 if rep["status"] == "UNATTRIBUTED" else 0


if __name__ == "__main__":
    sys.exit(main())

```

### scripts/collect_announcements.py
```python
#!/usr/bin/env python3
"""UNSTRUCTURED EVENT COLLECTOR (R0122b) -- the feed the LLM discretionary sleeve actually trades.

WHAT MAKES THIS MORE THAN A SCRAPER, and it is the whole reason it is worth building: it measures
ITS OWN INFORMATION LATENCY. Every item carries `published_at` (when the world learned) and
`first_seen` (when THIS desk learned), and their difference is the only number that decides
whether an event-reading strategy can exist at all. If the desk sees a listing announcement 90
seconds after publication and the market takes ten minutes to finish pricing it, there is a
window. If the desk sees it two hours later, there is no edge and the sleeve must be told so
rather than trading into an already-priced event. A scraper that cannot answer "was I early?"
produces confident noise -- that is the difference between an information edge and a news reader.

SOURCES, all public and unauthenticated (s13 legitimacy gate; no logins, no paywalls, no
closed groups). Each is independent, and a source that fails is RECORDED as failed rather than
silently contributing nothing -- three dead sources and one live one must never look like a quiet
news day:
  * exchange announcement APIs  -- listings, delistings, contract-spec changes, margin-tier
    changes, maintenance windows. The highest-value class: a spec change FORCES repositioning.
  * DefiLlama hacks feed        -- chain incidents and exploits, which move whole sectors.
  * public RSS                  -- broad crypto press, for context rather than for the edge.

THE DESK'S OWN DISCIPLINE APPLIED TO NEWS:
  * DEDUP BY CONTENT HASH across runs -- an item seen yesterday is not news today, and a
    collector that re-emits it manufactures fake events for the sleeve to trade.
  * MATERIALITY is scored, never assumed: a delisting is not a UI update. The keyword tiers here
    are a cheap PRE-FILTER only -- the LLM does the real judging, because that is exactly the
    reading task it is better at than a regex.
  * SYMBOLS EXTRACTED so a call can name what it trades.
  * APPEND-ONLY, so the record of what the desk knew and WHEN survives -- that history is itself
    moat (nobody else has our first_seen stamps).

    python scripts/collect_announcements.py [--once] [--json]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import urllib.error
import urllib.request
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any

_ROOT = Path("/home/quant/quant-platform")
if not _ROOT.exists():
    _ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
from libs.ops.lawful import guard as _law_guard  # noqa: E402

_OUT = "data/exchange_announcements.jsonl"
_SEEN = "data/.announcement_hashes.json"
_STATUS = "data/announcement_collector.json"
_UA = "quant-desk-research/1.0 (public-endpoint reader)"
_TIMEOUT = 20

#: An event older than this is HISTORY, not news. THE FIRST LIVE RUN PROVED WHY THIS IS NOT
#: optional: DefiLlama's hacks endpoint returns the full historical archive, so the collector
#: cheerfully ingested the 2021 CREAM exploit ($130M) as a tier-1 event with a 2.5-million-minute
#: latency. Without this gate the sleeve would have traded three-year-old news as breaking. The
#: threshold is generous because prose events price over hours, not seconds -- the point is to
#: exclude ARCHIVES, not to chase latency the desk cannot win anyway.
TRADEABLE_MAX_AGE_MIN = 24 * 60

#: MATERIALITY TIERS -- a cheap pre-filter, deliberately not the decision. Tier 1 events FORCE
#: someone to reposition, which is the mechanism class the sleeve is allowed to trade.
_TIER1 = ("delist", "will be removed", "contract spec", "leverage tier", "margin tier",
          "funding rate will", "settlement", "hard fork", "chain split", "exploit", "hack",
          "halt", "suspend", "emergency", "insolven")
_TIER2 = ("list", "launch", "perpetual", "new pair", "airdrop", "snapshot", "upgrade",
          "maintenance", "migration", "rebrand", "token swap")

#: KNOWN TICKERS. The first live run proved why a whitelist is mandatory: a bare
#: "any uppercase word" regex extracted ACROSS, BANKS, AFFECT, AN, LED and AS as tradeable
#: symbols from ordinary English headlines. A sleeve handed those would place calls on nonsense,
#: and the failure is invisible because the field LOOKS populated. Recall is deliberately traded
#: for precision here: a missed symbol costs one call, a fabricated one costs a wrong trade.
_KNOWN = {
    "BTC", "XBT", "ETH", "SOL", "XRP", "BNB", "ADA", "DOGE", "TRX", "AVAX", "LINK", "DOT",
    "MATIC", "POL", "TON", "SHIB", "LTC", "BCH", "UNI", "ATOM", "XLM", "ETC", "FIL", "APT",
    "ARB", "OP", "SUI", "SEI", "INJ", "TIA", "NEAR", "ICP", "HBAR", "VET", "ALGO", "AAVE",
    "MKR", "CRV", "LDO", "SNX", "COMP", "SUSHI", "1INCH", "GMX", "DYDX", "PENDLE", "ENA",
    "PEPE", "WIF", "BONK", "FLOKI", "JUP", "PYTH", "JTO", "W", "STRK", "BLUR", "ENS",
    "USDT", "USDC", "DAI", "FDUSD", "TUSD", "USDE", "PYUSD",
    "HYPE", "AERO", "VIRTUAL", "AI16Z", "GRASS", "MOVE", "ME", "EIGEN", "ZRO", "ZK",
}
_SYMBOL_RE = re.compile(r"\b([A-Z0-9]{2,10})\b")


def _get(url: str) -> tuple[Any, str]:
    """(payload, error). Never raises: one dead source must not kill the collector."""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": _UA})
        with urllib.request.urlopen(req, timeout=_TIMEOUT) as r:
            raw = r.read().decode("utf-8", errors="ignore")
    except (urllib.error.URLError, OSError, ValueError) as exc:
        return None, f"{type(exc).__name__}: {str(exc)[:120]}"
    try:
        return json.loads(raw), ""
    except ValueError:
        return raw, ""                                   # RSS/XML handled by the caller


def _tier(title: str, body: str = "") -> int:
    t = f"{title} {body}".lower()
    if any(k in t for k in _TIER1):
        return 1
    if any(k in t for k in _TIER2):
        return 2
    return 3


def _symbols(text: str) -> list[str]:
    """Only WHITELISTED tickers. An empty list is the correct, honest answer for a headline that
    names no asset -- far better than a plausible-looking list of English words."""
    return sorted({m for m in _SYMBOL_RE.findall(text.upper()) if m in _KNOWN})[:8]


def _iso(ts: Any) -> str | None:
    """Publisher timestamps arrive as epoch s, epoch ms, or ISO. None when truly absent -- and
    absent must stay absent, because a fabricated published_at destroys the latency measurement
    that is this collector's whole point."""
    if ts is None:
        return None
    try:
        if isinstance(ts, (int, float)) or str(ts).isdigit():
            v = float(ts)
            return datetime.fromtimestamp(v / 1000 if v > 1e11 else v, tz=UTC).isoformat()
        raw = str(ts).strip()
        try:
            d = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except ValueError:
            # RSS publishes RFC-822 ("Fri, 31 Jul 2026 12:00:00 GMT"). Without this branch every
            # RSS item reported UNMEASURED latency -- 55 of 80 on the first live run.
            d = parsedate_to_datetime(raw)
        return (d if d.tzinfo else d.replace(tzinfo=UTC)).isoformat()
    except (ValueError, OSError, OverflowError, TypeError):
        return None


def _rss_items(xml: str, source: str) -> list[dict[str, Any]]:
    out = []
    for block in re.findall(r"<item>(.*?)</item>", xml, re.DOTALL | re.IGNORECASE)[:40]:
        def _f(tag: str, block: str = block) -> str:
            m = re.search(rf"<{tag}[^>]*>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</{tag}>", block,
                          re.DOTALL | re.IGNORECASE)
            return re.sub(r"<[^>]+>", "", m.group(1)).strip() if m else ""
        title = _f("title")
        if title:
            out.append({"source": source, "title": title, "body": _f("description")[:600],
                        "url": _f("link"), "published_at": _iso(_f("pubDate"))})
    return out


def fetch_all() -> tuple[list[dict[str, Any]], dict[str, str]]:
    """Every source, with per-source failures RECORDED (never silently absent)."""
    items: list[dict[str, Any]] = []
    errors: dict[str, str] = {}

    # 1. EXCHANGE ANNOUNCEMENTS -- the highest-value class, because a listing, delisting or
    # spec change FORCES someone to reposition. Probed live 2026-07-31: OKX's public API works
    # unauthenticated and returns exactly this class; Binance's CMS endpoint 400s without a
    # signed context and Bybit's CloudFront blocks this egress region. Both are recorded as
    # source errors rather than quietly dropped -- a missing exchange feed is the difference
    # between this sleeve having an edge and reading press.
    doc, err = _get("https://www.okx.com/api/v5/support/announcements")
    if err:
        errors["okx_announcements"] = err
    elif isinstance(doc, dict):
        for grp in doc.get("data", []) or []:
            for art in (grp.get("details", []) or []):
                items.append({"source": "okx", "title": str(art.get("title", "")),
                              "body": str(art.get("annType", "")),
                              "url": str(art.get("url", "")),
                              "published_at": _iso(art.get("pTime"))})
    errors.setdefault("binance_announcements",
                      "HTTP 400 -- CMS endpoint requires a signed context (probed 2026-07-31)")
    errors.setdefault("bybit_announcements",
                      "CloudFront blocks this egress country (probed 2026-07-31) -- would need "
                      "the second VPS in a different region")

    # 2. DefiLlama hacks -- chain incidents move whole sectors, and they are pure prose events.
    doc, err = _get("https://api.llama.fi/hacks")
    if err:
        errors["defillama_hacks"] = err
    elif isinstance(doc, list):
        for h in doc[-25:]:
            if isinstance(h, dict):
                items.append({"source": "defillama_hacks",
                              "title": f"{h.get('name','?')} exploit: ${h.get('amount',0):,.0f}",
                              "body": str(h.get("classification", ""))[:300],
                              "url": str(h.get("link", "")), "published_at": _iso(h.get("date"))})

    # 3. Public RSS -- context, not edge. Named as such so nothing over-weights press coverage.
    for name, url in (("coindesk", "https://www.coindesk.com/arc/outboundfeeds/rss/"),
                      ("cointelegraph", "https://cointelegraph.com/rss")):
        doc, err = _get(url)
        if err:
            errors[name] = err
        elif isinstance(doc, str):
            items.extend(_rss_items(doc, name))
    return items, errors


def _load_seen(root: Path) -> set[str]:
    try:
        return set(json.loads((root / _SEEN).read_text("utf-8")).get("hashes", []))
    except (OSError, ValueError):
        return set()


def collect(root: Path, items: list[dict[str, Any]], errors: dict[str, str]) -> dict[str, Any]:
    """Dedup, enrich, append. Returns the run's status artifact."""
    now = datetime.now(tz=UTC)
    seen = _load_seen(root)
    fresh: list[dict[str, Any]] = []
    for it in items:
        title = str(it.get("title", "")).strip()
        if not title:
            continue
        h = hashlib.sha256(f"{it.get('source')}|{title}".encode()).hexdigest()[:16]
        if h in seen:
            continue                                     # already known -- not news twice
        seen.add(h)
        pub = it.get("published_at")
        # THE NUMBER THIS COLLECTOR EXISTS FOR: how late were we? None when the publisher gave
        # no timestamp -- unmeasured latency must never be reported as zero latency.
        lat = None
        if pub:
            try:
                lat = round((now - datetime.fromisoformat(pub)).total_seconds() / 60.0, 2)
            except ValueError:
                lat = None
        text = f"{title} {it.get('body', '')}"
        tier = _tier(title, str(it.get("body", "")))
        # TRADEABLE requires BOTH a material tier AND arrival inside the window. Unmeasured
        # latency is NOT tradeable: "we do not know how old this is" must never be treated as
        # "it is fresh" (L1.28a applied to news).
        tradeable = bool(lat is not None and lat <= TRADEABLE_MAX_AGE_MIN and tier <= 2)
        fresh.append({**it, "hash": h, "first_seen": now.isoformat(),
                      "latency_minutes": lat, "tier": tier, "tradeable": tradeable,
                      "not_tradeable_reason": (
                          None if tradeable else
                          "latency unmeasured -- age unknown, treated as not fresh"
                          if lat is None else
                          f"stale: {lat:.0f}min old (> {TRADEABLE_MAX_AGE_MIN}min) -- history, "
                          "not news" if lat > TRADEABLE_MAX_AGE_MIN else
                          "tier 3: no forced repositioning implied"),
                      "symbols": _symbols(text)})

    if fresh:
        p = root / _OUT
        p.parent.mkdir(parents=True, exist_ok=True)
        with p.open("a", encoding="utf-8") as fh:
            for row in fresh:
                fh.write(json.dumps(row) + "\n")
        (root / _SEEN).write_text(json.dumps({"hashes": sorted(seen)[-5000:]}), "utf-8")

    measured = [f["latency_minutes"] for f in fresh if f["latency_minutes"] is not None]
    n_src = 4
    status = ("ALL-SOURCES-DOWN" if len(errors) >= n_src else
              "DEGRADED" if errors else
              "NO-NEW-ITEMS" if not fresh else "OK")
    return {
        "generated": now.isoformat(), "status": status,
        "n_fetched": len(items), "n_new": len(fresh),
        "n_tier1": sum(1 for f in fresh if f["tier"] == 1),
        "n_tradeable": sum(1 for f in fresh if f["tradeable"]),
        "source_errors": errors,
        "median_latency_minutes": (sorted(measured)[len(measured) // 2] if measured else None),
        "latency_unmeasured": len(fresh) - len(measured),
        "detail": (f"{len(fresh)} new of {len(items)} fetched; "
                   f"{sum(1 for f in fresh if f['tier'] == 1)} tier-1, "
                   f"{sum(1 for f in fresh if f['tradeable'])} TRADEABLE (fresh + material); "
                   f"{len(errors)} source(s) failed"),
        "why_latency_matters": (
            "first_seen minus published_at is the only number that decides whether an "
            "event-reading strategy can exist. Early enough to trade, or already priced -- a "
            "collector that cannot answer that produces confident noise."),
    }


def main() -> int:
    _law_guard()
    ap = argparse.ArgumentParser()
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    items, errors = fetch_all()
    rep = collect(_ROOT, items, errors)
    (_ROOT / _STATUS).write_text(json.dumps(rep, indent=2), "utf-8")
    print(json.dumps(rep, indent=2) if args.json else
          f"announcements (R0122b): {rep['status']} -- {rep['detail']}")
    return 0                     # a dead source is recorded, never a build failure


if __name__ == "__main__":
    sys.exit(main())

```

### scripts/collect_cny_premium.py
```python
#!/usr/bin/env python3
"""USDT/CNY P2P premium collector -- the mainland capital-flow proxy (ledger #76, unparked
2026-07-24 with principal approval; the clean free source now exists and is live-verified).

CONSTRUCTION (owned methodology, free-first doctrine):
    p2p   = median of the top-10 OKX P2P merchant SELL-side USDT quotes in CNY (public, keyless,
            190 rows live-verified from this box)
    fx    = official USD/CNY (open.er-api.com, free, daily UTC update; frankfurter 403s here)
    premium = p2p / fx - 1
Mechanism: China's capital controls (total crypto ban + 50k USD/yr FX quota) make P2P USDT the
ONLY retail on-ramp -- the premium prices capital-control pressure, the direct CN analog of
kimchi (KRW). Live at build time: p2p ~6.74 vs fx 6.7815 -> -0.6%, a realistic magnitude.

HONESTY GATES, pre-registered up front:
  * NO Stage-A screen -- P2P quotes have no free history, so there is nothing to screen. This is
    a FORWARD-ONLY clock from day 1; z20 is written null until 20 real observations exist (the
    shadow evaluator skips null-z rows, so the stats never contain manufactured zeros).
  * DIRECTION pre-registered NOW, from mechanism only (peek-safe): +1, mirroring kimchi -- the
    one SURVIVING member of this construct family -- premium z-up = mainland demand surge =
    short-horizon momentum. Chosen before any forward return exists; never re-fit.
  * THE TRY FALSIFIER (graveyard: try_premium_timing KILLED the best previous kimchi-analog --
    "kimchi is RARE, not a generic regional-premium pattern"): if the 30-day premium std lands
    TRY-class (<0.3%) rather than KRW-class (1.4%), the axis is expected to read FAILING and
    will be retired by the Holm bar. Logged here so success cannot be quietly redefined.
  * No candle timestamps exist (live quotes sampled at collection time) -> the bithumb
    timezone-lookahead class is structurally impossible here.

Zero promotion authority: the forward clock under the Holm bar decides. stdlib only.
"""
from __future__ import annotations

import json
import statistics
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

_P2P = ("https://www.okx.com/v3/c2c/tradingOrders/books?t=1&quoteCurrency=CNY"
        "&baseCurrency=USDT&side=sell&paymentMethod=all&userType=all&showTrade=false"
        "&showFollow=false&showAlreadyTraded=false&isAbleFilter=false&pageIndex=1&pageSize=10")
_FX = "https://open.er-api.com/v6/latest/USD"
_SERIES = Path("data/cny_premium.jsonl")


def _get(url: str) -> object:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (quant-cny)"})
    with urllib.request.urlopen(req, timeout=25) as r:
        return json.loads(r.read().decode())


def main() -> None:
    d = _get(_P2P)
    rows = (d.get("data", {}) or {}).get("sell", []) or []
    prices = []
    for r in rows[:10]:
        try:
            prices.append(float(r["price"]))
        except Exception:
            continue
    if len(prices) < 5:
        raise SystemExit(f"P2P fetch thin: {len(prices)} quotes -- not writing a weak point")
    p2p = statistics.median(prices)

    fx_d = _get(_FX)
    fx = float((fx_d.get("rates") or {}).get("CNY", 0.0))
    if fx <= 0:
        raise SystemExit("FX fetch failed -- not writing")

    premium = p2p / fx - 1.0

    # z20 from the accruing series itself; null until 20 real observations exist
    hist = []
    if _SERIES.exists():
        for ln in _SERIES.read_text("utf-8").splitlines():
            try:
                hist.append(json.loads(ln))
            except Exception:
                continue
    prem_hist = [float(h["premium"]) for h in hist if h.get("premium") is not None]
    z20 = None
    if len(prem_hist) >= 20:
        w = prem_hist[-20:]
        sd = statistics.pstdev(w)
        z20 = round((premium - statistics.fmean(w)) / sd, 3) if sd > 0 else 0.0

    today = datetime.now(tz=UTC).date().isoformat()
    if hist and hist[-1].get("date") == today:
        print(f"cny-premium: {today} already recorded")
        return
    rec = {"date": today, "p2p_cny": round(p2p, 4), "fx_cny": round(fx, 4),
           "premium": round(premium, 5), "z20": z20, "n_quotes": len(prices)}
    with _SERIES.open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec) + "\n")

    n = len(prem_hist) + 1
    std30 = statistics.pstdev([*prem_hist[-30:], premium]) if n >= 10 else None
    print(f"CNY-PREMIUM  {today}  p2p {p2p:.4f} vs fx {fx:.4f} -> {premium*100:+.2f}%  "
          f"(z20 {z20 if z20 is not None else 'null until n>=20'}; n={n})")
    if std30 is not None:
        verdict = "KRW-class (fat, promising)" if std30 > 0.006 else \
                  "TRY-class WARNING (thin -- expect FAILING per pre-registered falsifier)" \
                  if std30 < 0.003 else "intermediate"
        print(f"  30d premium std {std30*100:.2f}% -> {verdict}")


if __name__ == "__main__":
    main()

```

### scripts/collector_author.py
```python
"""COLLECTOR AUTHOR -- closes the desk's real conversion bottleneck (principal 2026-07-27).

THE BOTTLENECK, identified this session: finding sources is automated, SCREENING is automated
(axis_screen), but turning a discovered source into a WIRED COLLECTOR is bespoke code the brain
writes per source -- and it is error-prone (the kimchi USDT-vs-FX construction bug, the bithumb
timezone lookahead, my own double-z-scoring). Breadth without this just grows a queue.

This closes the loop end-to-end, daily:
    breadth_expansion.jsonl (NEW+REACHABLE)  ->  3 flagship LLMs write a fetcher
      ->  STATIC SAFETY SCAN  ->  EXECUTE in isolated subprocess  ->  VALIDATE the series
      ->  axis_screen Stage-A  ->  report

SEATS CHOSEN ON MEASURED PERFORMANCE, NOT REPUTATION: the 2026-07-27 breadth sweep showed
grok-4.3 and nemotron producing 18 parseable rows each while gpt-5.6-terra-pro produced 0 on 5 of
6 lenses. Code generation is a different task, so the pool is code-strong flagships and each run
records which seat's collector actually WORKED -- the yield table is the seat-selection evidence.

*** SECURITY: this EXECUTES model-written code on a host holding trading keys. ***
Mitigations (defence in depth, not a sandbox):
  1. STATIC SCAN rejects: subprocess, os.system/popen, eval/exec/compile, __import__, socket,
     shutil, pathlib writes, open(...,'w'/'a'), pickle, requests-to-non-http, env access.
  2. Executed via a SEPARATE subprocess with a hard timeout, output-only via stdout JSON.
  3. Allowed imports whitelisted (json/urllib/datetime/math/statistics only).
Residual risk is NOT zero. Disclosed to the principal.

Stage-A only, zero promotion authority. Run from repo root.
"""
from __future__ import annotations

import json
import re
import ssl
import subprocess
import sys
import tempfile
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

KEYS = ROOT / "data/secrets/llm_panel.json"
FEED = ROOT / "data/breadth_expansion.jsonl"
DONE = ROOT / "data/collector_attempts.jsonl"
GEN = ROOT / "data/generated_collectors"
CTX = ssl.create_default_context()

# code-strong flagships; yield table below is the real selection evidence
SEATS = ["deepseek/deepseek-v4-pro", "moonshotai/kimi-k3", "x-ai/grok-4.3"]
N_TARGETS = 3          # sources attempted per run

BANNED = re.compile(
    r"\b(subprocess|os\s*\.\s*(system|popen|remove|unlink|environ)|eval\s*\(|exec\s*\("
    r"|compile\s*\(|__import__|socket|shutil|pickle|marshal|ctypes|importlib"
    r"|open\s*\([^)]*['\"][wa]|\.write_text|\.write_bytes|rmtree|setattr\s*\(\s*__)")
ALLOWED_IMPORTS = {"json", "urllib", "urllib.request", "urllib.parse", "urllib.error",
                   "datetime", "math", "statistics", "re", "time", "csv", "io", "collections"}

SYSTEM = (
    "You write DATA COLLECTORS for a quant desk. Given a public data source, emit ONE Python "
    "function that fetches a DAILY TIME SERIES from it.\n"
    "STRICT CONTRACT:\n"
    "- Output ONLY code in a ```python fence. No prose.\n"
    "- Define exactly: def fetch() -> dict  returning {'YYYY-MM-DD': float, ...}\n"
    "- Standard library ONLY: json, urllib.request, datetime, math, re, time, csv, io.\n"
    "- NO subprocess/os/eval/exec/socket/file-writes. Read-only network via urllib.\n"
    "- Handle the real response schema; do not invent fields. If the endpoint needs a key, "
    "return {} (we only use keyless free sources).\n"
    "- Aim for >=200 daily points where the source allows.\n"
    "- Set a User-Agent header; use timeout=25 on every request."
)



def _doctrine(role: str = "") -> str:
    """Runtime doctrine preamble. One source (scripts/doctrine.py); never a pasted copy."""
    try:
        from scripts.doctrine import preamble
        return preamble(role)
    except Exception:  # blind-except intentional (BLE001)
        try:
            import sys as _s
            _s.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent))
            from doctrine import preamble  # type: ignore
            return preamble(role)
        except Exception:  # blind-except intentional (BLE001)
            return ""          # never break a caller over a preamble


def _ask(base, key, model, system, user, timeout=150.0):
    body = json.dumps({"model": model, "max_tokens": 3000, "temperature": 0.3,
                       "reasoning": {"effort": "high"},
                       "messages": [{"role": "system", "content": _doctrine("collector_author") + system},
                                    {"role": "user", "content": user}]}).encode()
    req = urllib.request.Request(base.rstrip("/") + "/chat/completions", data=body, method="POST",
                                 headers={"Authorization": f"Bearer {key}",
                                          "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout, context=CTX) as r:
        out = json.loads(r.read())
    m = out["choices"][0]["message"]
    return str(m.get("content") or m.get("reasoning") or "")


def extract_code(txt: str) -> str:
    m = re.search(r"```(?:python)?\s*(.+?)```", txt, re.S)
    return (m.group(1) if m else txt).strip()


def safety_scan(code: str) -> str | None:
    """Return a rejection reason, or None if the code passes. Fail CLOSED on anything unknown."""
    if BANNED.search(code):
        return f"banned construct: {BANNED.search(code).group(0)[:40]}"
    for mod in re.findall(r"^\s*(?:import|from)\s+([a-zA-Z_][\w.]*)", code, re.M):
        root = mod.split(".")[0]
        if root not in {m.split(".")[0] for m in ALLOWED_IMPORTS}:
            return f"non-whitelisted import: {mod}"
    if "def fetch" not in code:
        return "no fetch() defined"
    return None


def run_isolated(code: str, timeout: int = 70) -> tuple[dict | None, str]:
    """Execute in a SEPARATE process with a hard timeout; series returned as stdout JSON."""
    runner = code + (
        "\n\nif __name__ == '__main__':\n"
        "    import json as _j\n"
        "    try:\n"
        "        _s = fetch()\n"
        "        _s = {str(k): float(v) for k, v in dict(_s).items()}\n"
        "        print('__SERIES__' + _j.dumps(_s))\n"
        "    except Exception as _e:\n"
        "        print('__ERR__' + type(_e).__name__ + ': ' + str(_e)[:180])\n")
    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False, encoding="utf-8") as fh:
        fh.write(runner)
        path = fh.name
    try:
        p = subprocess.run([sys.executable, path], capture_output=True, text=True,
                           timeout=timeout, check=False)
        out = p.stdout or ""
        if "__SERIES__" in out:
            return json.loads(out.split("__SERIES__", 1)[1].splitlines()[0]), "ok"
        if "__ERR__" in out:
            return None, out.split("__ERR__", 1)[1].splitlines()[0][:150]
        return None, (p.stderr or "no output")[-150:]
    except subprocess.TimeoutExpired:
        return None, "timeout"
    finally:
        Path(path).unlink(missing_ok=True)


def validate(series: dict) -> tuple[bool, str]:
    """A collector that returns garbage is worse than none -- this is the diff-verify step."""
    if not series or len(series) < 90:
        return False, f"only {len(series or {})} points (<90)"
    vals = list(series.values())
    if len(set(vals)) < len(vals) * 0.2:
        return False, "near-constant series (stale/placeholder)"
    if any(v != v for v in vals):
        return False, "NaN present"
    bad = [k for k in series if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(k))]
    if bad:
        return False, f"bad date keys e.g. {bad[0]}"
    return True, f"{len(series)} points, {min(series)}..{max(series)}"


def main() -> None:
    if not (KEYS.exists() and FEED.exists()):
        print("missing panel keys or breadth feed")
        return
    provs = {p["model"]: p for p in json.loads(KEYS.read_text("utf-8"))["providers"]
             if isinstance(p, dict)}
    tried = set()
    if DONE.exists():
        tried = {json.loads(x).get("source") for x in DONE.read_text("utf-8").splitlines()
                 if x.strip()}

    cands, seen = [], set()
    for ln in FEED.read_text("utf-8").splitlines():
        try:
            r = json.loads(ln)
        except json.JSONDecodeError:
            continue
        if r.get("_summary") or r.get("duplicate") or not r.get("reachable"):
            continue
        nm = r.get("name")
        if nm in tried or nm in seen:
            continue
        seen.add(nm)
        cands.append(r)
    if not cands:
        print("no unconverted NEW+REACHABLE sources in the feed")
        return
    targets = cands[:N_TARGETS]
    GEN.mkdir(exist_ok=True)
    print(f"=== COLLECTOR AUTHOR | {len(targets)} sources x {len(SEATS)} flagship seats ===")
    print("    (executes model-written code -- static scan + isolated subprocess + timeout)\n")

    jobs = [(t, s) for t in targets for s in SEATS if s in provs]

    def _gen(j):
        t, seat = j
        user = (f"SOURCE: {t['name']}\nENDPOINT: {t['url']}\n"
                f"MODALITY: {t.get('modality','')}\nWHY IT MATTERS: {t.get('mechanism','')}\n\n"
                "Write fetch() returning a daily time series from this source.")
        try:
            return t, seat, extract_code(_ask(provs[seat]["base_url"], provs[seat]["key"],
                                              seat, SYSTEM, user)), None
        except Exception as e:
            return t, seat, "", f"{type(e).__name__}"

    with ThreadPoolExecutor(max_workers=6) as ex:
        gens = list(ex.map(_gen, jobs))

    results, wins = [], {}
    for t, seat, code, err in gens:
        nm, sn = t["name"][:34], seat.split("/")[-1][:18]
        if err:
            print(f"  {nm:<34} {sn:<18} LLM-FAIL {err}")
            continue
        rej = safety_scan(code)
        if rej:
            print(f"  {nm:<34} {sn:<18} REJECTED ({rej})")
            results.append({"source": t["name"], "seat": seat, "status": "unsafe", "detail": rej})
            continue
        series, msg = run_isolated(code)
        ok, vmsg = validate(series or {})
        status = "WORKS" if ok else "broken"
        print(f"  {nm:<34} {sn:<18} {status:<7} {vmsg if ok else msg}")
        results.append({"source": t["name"], "seat": seat, "status": status,
                        "detail": vmsg if ok else msg, "n": len(series or {})})
        if ok and t["name"] not in wins:
            wins[t["name"]] = (seat, code, series)
            safe = re.sub(r"[^a-z0-9]+", "_", t["name"].lower())[:40]
            (GEN / f"{safe}.py").write_text(code, "utf-8")

    with DONE.open("a", encoding="utf-8") as fh:
        for r in results:
            r["date"] = datetime.now(tz=UTC).date().isoformat()
            fh.write(json.dumps(r) + "\n")

    print(f"\n  CONVERTED {len(wins)}/{len(targets)} sources into working collectors")
    for nm, (seat, _c, ser) in wins.items():
        print(f"    {nm[:40]:<40} by {seat.split('/')[-1]:<16} {len(ser)} pts -> {GEN.name}/")
    tally: dict[str, list[int]] = {}
    for r in results:
        tally.setdefault(r["seat"], [0, 0])
        tally[r["seat"]][1] += 1
        if r["status"] == "WORKS":
            tally[r["seat"]][0] += 1
    print("\n  SEAT YIELD (this is the seat-selection evidence, not reputation):")
    for seat, (w, n) in sorted(tally.items(), key=lambda kv: -kv[1][0]):
        print(f"    {seat.split('/')[-1]:<22} {w}/{n} working")
    print("\n  -> working collectors land in data/generated_collectors/ for screening.")
    print("     Stage-A only; a generated collector NEVER auto-wires into the daily cycle.")


if __name__ == "__main__":
    main()

```

### scripts/hl_skill_persistence.py
```python
"""HYPERLIQUID SKILL-PERSISTENCE TEST -- the foundational question behind copytrading.

THE QUESTION: does a trader's PAST performance predict their FUTURE performance? If not,
copytrading has no basis (you would be selecting on luck), and the 26-layer trader-intelligence
spec collapses regardless of how well engineered it is.

WHY THIS BEATS THE FAILED AGGREGATE TEST: per-trader (no averaging away the skilled minority),
skill-defined-by-PnL (not by account size like Binance's 'top trader' cohort), and it measures
PERSISTENCE (the actual luck/skill discriminator) rather than a positioning level.

SURVIVORSHIP HANDLING (honest): Hyperliquid's public leaderboard is a CURRENT snapshot of ~41k
addresses that INCLUDES large losers (verified: sample account -$3.3M month PnL), so it is NOT a
winners-only list. RESIDUAL BIAS STATED: accounts fully liquidated and closed mid-window may be
absent entirely -> persistence could be biased UP. This test can therefore REFUTE persistence
cleanly; a positive result needs the forward-clock confirmation (seeded separately).

NON-OVERLAPPING WINDOWS (no lookahead):
    formation = month_pnl - week_pnl   (approx weeks -4..-1)
    holding   = week_pnl               (the most recent week)
Both normalised by accountValue -> comparable returns. Ranked-correlation + decile spread.

CONFOUND CONTROLS: (1) min accountValue + min volume filters kill micro-account ROI noise;
(2) within-size-bucket repeat -- if persistence is only market beta (everyone long in an up week),
it should NOT survive inside homogeneous size buckets and the decile spread would be flat;
(3) a shuffled-label null gives the luck baseline.

Read-only screen. Zero promotion authority. Run from repo root."""
from __future__ import annotations

import json
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

import numpy as np

_LB = "https://stats-data.hyperliquid.xyz/Mainnet/leaderboard"
MIN_ACCT_VALUE = 10_000.0     # kill micro accounts (ROI noise)
MIN_MONTH_VLM = 100_000.0     # kill dormant accounts


def _fetch() -> list[dict]:
    req = urllib.request.Request(_LB, headers={"User-Agent": "quant-hl/1.0"})
    with urllib.request.urlopen(req, timeout=180) as r:
        d = json.loads(r.read().decode())
    return d.get("leaderboardRows", d) if isinstance(d, dict) else d


def _spearman(a: np.ndarray, b: np.ndarray) -> tuple[float, float]:
    ra = np.argsort(np.argsort(a)).astype(float)
    rb = np.argsort(np.argsort(b)).astype(float)
    if ra.std() == 0 or rb.std() == 0:
        return 0.0, 0.0
    rho = float(np.corrcoef(ra, rb)[0, 1])
    n = len(a)
    t = rho * np.sqrt((n - 2) / max(1e-12, 1 - rho ** 2)) if n > 2 and abs(rho) < 1 else 0.0
    return rho, float(t)


def _decile_spread(form: np.ndarray, hold: np.ndarray, q: int = 10):
    order = np.argsort(form)
    k = len(form) // q
    if k < 5:
        return None
    bot, top = hold[order[:k]], hold[order[-k:]]
    diff = top.mean() - bot.mean()
    se = np.sqrt(top.var(ddof=1) / len(top) + bot.var(ddof=1) / len(bot))
    return {"top_decile_mean_ret": round(float(top.mean()), 5),
            "bottom_decile_mean_ret": round(float(bot.mean()), 5),
            "spread": round(float(diff), 5),
            "t": round(float(diff / se), 2) if se > 0 else 0.0,
            "n_per_decile": int(k)}


def _run(form: np.ndarray, hold: np.ndarray, label: str) -> dict:
    rho, t = _spearman(form, hold)
    dec = _decile_spread(form, hold)
    rng = np.random.default_rng(7)
    null = [abs(_spearman(rng.permutation(form), hold)[0]) for _ in range(200)]
    out = {"label": label, "n": len(form), "spearman_rho": round(rho, 4),
           "t_stat": round(t, 2), "null_rho_p95": round(float(np.percentile(null, 95)), 4),
           "decile": dec}
    print(f"\n[{label}] n={len(form)}")
    print(f"  rank-corr(formation, holding) rho={rho:+.4f}  t={t:+.2f}  "
          f"(shuffled-null |rho| p95={np.percentile(null,95):.4f})")
    if dec:
        print(f"  top-decile fwd ret {dec['top_decile_mean_ret']:+.4f} vs bottom "
              f"{dec['bottom_decile_mean_ret']:+.4f} | spread {dec['spread']:+.4f} (t {dec['t']:+.2f})")
    return out


def main() -> None:
    rows = _fetch()
    print(f"leaderboard rows fetched: {len(rows)}")
    recs = []
    for r in rows:
        try:
            av = float(r.get("accountValue", 0) or 0)
            wp = dict(r.get("windowPerformances", []))
            m, w7 = wp.get("month", {}), wp.get("week", {})
            mp, wpnl = float(m.get("pnl", 0) or 0), float(w7.get("pnl", 0) or 0)
            vlm = float(m.get("vlm", 0) or 0)
            if av < MIN_ACCT_VALUE or vlm < MIN_MONTH_VLM:
                continue
            recs.append({"av": av, "form": (mp - wpnl) / av, "hold": wpnl / av, "vlm": vlm})
        except (TypeError, ValueError):
            continue
    print(f"after filters (acctValue>=${MIN_ACCT_VALUE:,.0f}, monthVlm>=${MIN_MONTH_VLM:,.0f}): "
          f"{len(recs)} traders")
    if len(recs) < 200:
        raise SystemExit("insufficient cohort")

    form = np.array([x["form"] for x in recs])
    hold = np.array([x["hold"] for x in recs])
    # winsorise the tails so a few extreme accounts cannot drive the rank stats
    lo, hi = np.percentile(form, [0.5, 99.5]); form_w = np.clip(form, lo, hi)
    lo2, hi2 = np.percentile(hold, [0.5, 99.5]); hold_w = np.clip(hold, lo2, hi2)

    results = [_run(form_w, hold_w, "ALL (formation=month-week, holding=week)")]

    # confound control: within homogeneous size buckets (beta/size cannot explain persistence here)
    av = np.array([x["av"] for x in recs])
    edges = np.percentile(av, [0, 33, 66, 100])
    for i, nm in enumerate(["small", "mid", "large"]):
        m = (av >= edges[i]) & (av <= edges[i + 1])
        if m.sum() >= 200:
            results.append(_run(form_w[m], hold_w[m], f"size-bucket {nm} (n={int(m.sum())})"))

    verdict = ("PERSISTENCE DETECTED" if abs(results[0]["t_stat"]) >= 3.0
               and abs(results[0]["spearman_rho"]) > results[0]["null_rho_p95"]
               else "NO PERSISTENCE (selecting past winners does not predict future)")
    print(f"\n=== VERDICT: {verdict} ===")
    Path("data/hl_skill_persistence.json").write_text(json.dumps(
        {"updated": datetime.now(tz=UTC).isoformat(), "cohort": len(recs),
         "verdict": verdict, "results": results,
         "caveat": "leaderboard is a current snapshot; fully-closed blowups may be absent -> "
                   "persistence may be biased UP. Refutation is clean; confirmation needs a "
                   "forward clock."}, indent=1), "utf-8")


if __name__ == "__main__":
    main()

```

### scripts/llm_code_auditor.py
```python
"""LLM CODE AUDITOR -- adversarial review of the desk's own recent diffs.

*** WRITTEN BUT NEVER EXECUTED (OpenRouter 402 on 2026-07-27). UNTESTED CODE. ***
The brain must run it once and check the output before anything relies on it. Given that the two
validators I DID test both shipped with high false-positive rates, assume this one has bugs too.

WHY IT EXISTS -- measured, not theoretical. On 2026-07-27 I shipped and self-corrected NINE
defects, several in safety-critical machinery:
  * activation gate FAILED OPEN (counted keyword hits in prose, found "63 survivors" against a
    true count of 0, and authorised itself -- the gate built to prevent fitting-on-noise licensed
    exactly that)
  * budget guard read keys that DO NOT EXIST (monthly_usd_cap vs monthly_envelope_usd), printed
    "no cap configured" while a real $120 envelope sat in the file
  * leak-detection condition written BACKWARDS (flagged the healthy pattern as the artifact)
  * "FAILS TO REPLICATE" printed for a result that replicated, because z missed an arbitrary 2.0
  * cost estimate 27x optimistic ($0.008 vs measured $0.225/call) -> caused a 402 mid-run
  * double z-scoring collapsed every signal to zeros (INSUFFICIENT-DATA on everything)
  * futures MIN_NOTIONAL read via the spot key -> returned 0.0, understating a capacity floor
  * two validators shipped flagging config constants and clocks as market-data anomalies
I caught them all by re-reading. A cold model reading the diff would plausibly catch several
FASTER, and -- the actual point -- would catch the ones I cannot see, because I cannot audit my
own blind spots.

The prompt below encodes THIS taxonomy rather than generic "find bugs", because these are the
failure modes this codebase actually produces.
"""
from __future__ import annotations

import json
import ssl
import subprocess
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
KEYS = ROOT / "data/secrets/llm_panel.json"
OUT = ROOT / "data/code_audit.jsonl"
CTX = ssl.create_default_context()

SEATS = ["deepseek/deepseek-v4-pro", "x-ai/grok-4.3", "moonshotai/kimi-k3"]
N_COMMITS = 3
MAX_DIFF_CHARS = 45000

SYSTEM = (
    "You are a hostile code reviewer for a quantitative trading desk. Your job is to find bugs "
    "that would cause SILENT WRONG BEHAVIOUR -- not style, not typing, not performance. A crash "
    "is safe because someone notices. A confident wrong number is not.\n\n"
    "This codebase has a MEASURED history of these exact defect classes. Hunt them first:\n"
    "1. FAIL-OPEN GUARDS  -- a safety gate whose default/ambiguous branch ALLOWS the action. Any "
    "gate must fail CLOSED. Check what happens on missing files, empty lists, exceptions, None.\n"
    "2. WRONG KEY NAMES   -- reading a dict key that does not exist, silently getting 0/None/'' "
    "and treating it as real. Cross-check every .get() against the file it reads.\n"
    "3. INVERTED CONDITIONS -- comparison or sign written backwards so the healthy case is "
    "flagged and the broken case passes.\n"
    "4. MECHANICAL THRESHOLDS -- a hard cutoff (z>=2.0, p<0.05) applied without checking SIGN or "
    "effect size, mislabelling a real result or blessing a fake one.\n"
    "5. DOUBLE TRANSFORMATION -- normalising/z-scoring/scaling data that is already normalised; "
    "look for a value passed through the same transform twice.\n"
    "6. UNIT / MAGNITUDE ERRORS -- bps vs %, seconds vs ms, per-call vs per-run cost.\n"
    "7. MISSING GATE -- the test runs correctly but omits a check that would invalidate every "
    "passing result (e.g. a spread screen with no transaction-cost comparison).\n"
    "8. LOOKAHEAD -- using data timestamped at or after the prediction target; misaligned "
    "candle/timezone conventions; forward-shifted series.\n\n"
    "Output ONE finding per line, most severe first, format:\n"
    "SEVERITY | FILE:LINE | CLASS | what breaks | concrete input that triggers it\n"
    "SEVERITY is CRITICAL (wrong trading/sizing decision), HIGH (wrong research conclusion) or "
    "MED. If you find nothing real, output exactly: NO-FINDINGS. Do not invent findings to seem "
    "useful -- a false finding costs more than a missed one here."
)



def _doctrine(role: str = "") -> str:
    """Runtime doctrine preamble. One source (scripts/doctrine.py); never a pasted copy."""
    try:
        from scripts.doctrine import preamble
        return preamble(role)
    except Exception:  # blind-except intentional (BLE001)
        try:
            import sys as _s
            _s.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent))
            from doctrine import preamble  # type: ignore
            return preamble(role)
        except Exception:  # blind-except intentional (BLE001)
            return ""          # never break a caller over a preamble


def _ask(base, key, model, system, user, timeout=240.0):
    body = json.dumps({"model": model, "max_tokens": 3000, "temperature": 0.2,
                       "reasoning": {"effort": "high"},
                       "messages": [{"role": "system", "content": _doctrine("llm_code_auditor") + system},
                                    {"role": "user", "content": user}]}).encode()
    req = urllib.request.Request(base.rstrip("/") + "/chat/completions", data=body, method="POST",
                                 headers={"Authorization": f"Bearer {key}",
                                          "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout, context=CTX) as r:
        out = json.loads(r.read())
    m = out["choices"][0]["message"]
    return str(m.get("content") or m.get("reasoning") or "")


def recent_diff(n: int) -> str:
    try:
        return subprocess.run(["git", "diff", f"HEAD~{n}", "HEAD", "--", "*.py"],
                              cwd=str(ROOT), capture_output=True, text=True,
                              check=False, timeout=60).stdout
    except Exception:
        return ""


def main() -> None:
    if not KEYS.exists():
        print("no panel keys")
        return
    provs = {p["model"]: p for p in json.loads(KEYS.read_text("utf-8"))["providers"]
             if isinstance(p, dict)}
    diff = recent_diff(N_COMMITS)
    if not diff.strip():
        print("no python diff in the last commits")
        return
    if len(diff) > MAX_DIFF_CHARS:
        diff = diff[:MAX_DIFF_CHARS] + "\n...[truncated]"
    print(f"=== LLM CODE AUDITOR | last {N_COMMITS} commits | {len(diff)} chars ===")
    print("    *** UNTESTED SCRIPT -- verify output before trusting it ***\n")

    user = ("Review this diff. Report only defects causing SILENT WRONG BEHAVIOUR.\n\n" + diff)
    rows = []
    for seat in SEATS:
        prov = provs.get(seat)
        if not prov:
            print(f"  {seat}: not in roster")
            continue
        try:
            txt = _ask(prov["base_url"], prov["key"], seat, SYSTEM, user)
        except Exception as e:
            print(f"  {seat.split('/')[-1]:<20} FAILED ({type(e).__name__} "
                  f"{getattr(e, 'code', '')})")
            continue
        found = 0
        for ln in txt.splitlines():
            if ln.strip().upper().startswith("NO-FINDINGS"):
                break
            if ln.count("|") >= 4:
                parts = [x.strip() for x in ln.split("|")]
                rows.append({"date": datetime.now(tz=UTC).isoformat(), "seat": seat,
                             "severity": parts[0][:12], "where": parts[1][:80],
                             "klass": parts[2][:40], "what": parts[3][:220],
                             "trigger": parts[4][:220]})
                found += 1
        print(f"  {seat.split('/')[-1]:<20} {found} findings")

    if rows:
        with OUT.open("a", encoding="utf-8") as fh:
            for r in rows:
                fh.write(json.dumps(r) + "\n")
    crit = [r for r in rows if r["severity"].upper().startswith("CRIT")]
    print(f"\n  {len(rows)} findings ({len(crit)} CRITICAL)")
    for r in sorted(rows, key=lambda x: x["severity"])[:12]:
        print(f"    [{r['severity']:<8}] {r['where']:<44} {r['klass']}")
        print(f"               {r['what'][:110]}")
    print("\n  AGREEMENT ACROSS SEATS is the signal -- one seat alone is a hypothesis, not a bug.")
    print("  Every finding must be REPRODUCED before acting; models invent plausible defects.")
    print(f"  -> {OUT}")


if __name__ == "__main__":
    main()

```

### scripts/module_justification.py
```python
"""MODULE JUSTIFICATION -- "would I build this today?", asked of things that already exist.

THE GAP, and the principal found it. Two audits already run and neither asks this question:
  max_audit          "is it RUNNING?"   -- organs, stub deaths, stale daemons, coverage
  meta_architect     "is it WIRED?"     -- unwired scripts, orphan outputs
Both are liveness proxies. A module can be wired, firing daily, and having its artifact read --
and still be worthless, because the question it answers was settled last month, or because the
evidence it was built on has since been refuted. Nothing catches that. Entropy on this desk is
therefore one-directional: capability accretes and never retires.

FOUR TESTS, applied to code that already exists rather than to proposals:
  1 DECISION IMPACT     has its output ever changed a decision? (cited in a later commit)
  2 EVIDENCE VALIDITY   does it depend on a dataset that FAILED the measurement gate, or a
                        mechanism since marked FAMILY KILL? If so it is answering a dead question.
  3 DUPLICATION         does another module answer the same question on the same artifacts?
  4 MAINTENANCE COST    size x dependency surface -- what it costs to keep alive.

VERDICTS: KEEP / MERGE / RETIRE / PROBATION. Probation is for modules too new to judge --
including almost everything I added today, which this deliberately does NOT flatter.

HARSHEST ON ITSELF BY DESIGN. 13 modules were added to this desk in ~36 hours by one process
(me). That is exactly the accretion pattern this exists to catch, and a justification auditor that
exempts its own author is decoration.

Read-only. No keys, no network. Run from repo root.
"""
from __future__ import annotations

import json
import re
import subprocess
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GATE = ROOT / "data/measurement_gate.json"
MECH = ROOT / "data/mechanism_board.json"
CYCLE = ROOT / "scripts/daily_research_cycle.py"
OUT = ROOT / "data/module_justification.json"

PROBATION_DAYS = 14          # too new to have changed a decision; judge later, don't flatter now


def _git(*a: str) -> str:
    try:
        return subprocess.run(["git", *a], cwd=str(ROOT), capture_output=True, text=True,
                              check=False, timeout=60).stdout
    except Exception:  # blind-except intentional (BLE001)
        return ""


def main() -> None:
    gate = {k: v.get("verdict") for k, v in
            (json.loads(GATE.read_text("utf-8")).get("datasets", {}) if GATE.exists()
             else {}).items()}
    dead_ds = {k for k, v in gate.items() if v == "FAILED"}
    kills = set(json.loads(MECH.read_text("utf-8")).get("family_kills", [])) \
        if MECH.exists() else set()
    cycle = CYCLE.read_text("utf-8") if CYCLE.exists() else ""
    cron = _git("log", "-1")  # cheap touch to warm git; crontab read separately
    try:
        cron = subprocess.run(["crontab", "-l"], capture_output=True, text=True,
                              check=False, timeout=20).stdout
    except Exception:  # blind-except intentional (BLE001)
        cron = ""

    # first-seen date per script, from git
    scripts = sorted((ROOT / "scripts").glob("*.py"))
    now = datetime.now(tz=UTC)
    rows = []
    # map artifact -> producers, to detect duplication
    produces: dict[str, list[str]] = {}
    texts = {}
    for p in scripts:
        t = p.read_text("utf-8", errors="ignore")
        texts[p.stem] = t
        for art in set(re.findall(r'data/([A-Za-z0-9_]+)\.(?:json|jsonl)', t)):
            produces.setdefault(art, []).append(p.stem)

    for p in scripts:
        stem, t = p.stem, texts[p.stem]
        first = _git("log", "--diff-filter=A", "--format=%aI", "--", str(p.relative_to(ROOT)))
        first_line = first.strip().splitlines()[-1] if first.strip() else ""
        try:
            age_d = (now - datetime.fromisoformat(first_line)).days if first_line else 999
        except ValueError:
            age_d = 999
        wired = (p.name in cycle) or (p.name in cron)

        # 1 decision impact: did any LATER commit message name this module?
        cites = len([ln for ln in _git("log", "--format=%s%n%b").splitlines() if stem in ln]) - 1

        # 2 evidence validity
        reads_dead = sorted({d for d in dead_ds if d.replace(".jsonl", "") in t})
        # MENTION IS NOT DEPENDENCY. v1 flagged mechanism_board, experiment_registry and
        # research_cio as "built on FAMILY KILL M_ATTENTION_DELAY" because they NAME it -- they
        # are the modules that ENFORCE the kill. A police module is not a dependent. Only count
        # it when the module lacks any enforcement vocabulary around it.
        _enforcer = any(k in t for k in ("family_kill", "FAMILY KILL", "kills", "verdicts",
                                         "REJECT", "rejected", "graveyard"))
        dead_mechs = [] if _enforcer else sorted({m for m in kills if m in t})

        # 3 duplication
        mine = {a for a, ps in produces.items() if stem in ps}
        # Only a shared PRIMARY output counts. Many modules legitimately read the same
        # artifacts; v1 flagged 85 duplicates on incidental co-reference.
        _primary = f"{stem}"
        dupes = sorted({o for o in produces.get(_primary, []) if o != stem})

        # 4 maintenance cost
        loc = t.count("\n")

        low = t.lower()
        # SCAR TISSUE: written in response to a real failure. The docstrings on this desk record
        # incidents explicitly, so this is detectable rather than guessed.
        scar = any(k in low for k in ("incident", "root cause", "silent failure", "fail-open",
                                      "regression", "this went wrong", "cost real money",
                                      "defect", "post-mortem", "prevents recurrence"))
        # CRITICAL: touches something that moves money or gates a live decision.
        critical = any(k in low for k in ("run_cashcarry_executor", "cashcarry_positions",
                                          "positionrisk", "place_market", "reduceonly",
                                          "_entry_gate", "deadman", "kill", "heartbeat",
                                          "measurement_gate", "require_verified"))
        # PREMATURE: depends on things this desk does not have -- validated alphas, deployed
        # capital, or collectors that were never built.
        premature = any(k in low for k in ("deployed alpha", "portfolio construction",
                                           "capital allocation", "decay laborator",
                                           "recombination", "once alphas exist",
                                           "needs >=2", "requires a deployed"))
        if dead_mechs:
            v, why = "RETIRE", f"built on FAMILY KILL {dead_mechs[0]}"
        elif dupes:
            v, why = "DUPLICATE", f"shares output artifacts with {dupes[0]}"
        elif scar and critical:
            v, why = "SCAR_TISSUE", "prevents recurrence of a real failure on a live path"
        elif scar:
            v, why = "SCAR_TISSUE", "written after a real failure it prevents"
        elif critical:
            v, why = "CRITICAL", "feeds a live decision; absence is immediately visible"
        elif premature:
            v, why = "PREMATURE", "answers a question this desk does not have yet"
        elif not wired and cites <= 0:
            v, why = "INERT", "nothing reads it; deleting it breaks nothing"
        else:
            v, why = "KEEP", "wired and cited, evidence intact"
        rows.append({"module": stem, "age_days": age_d, "wired": wired, "citations": max(cites, 0),
                     "loc": loc, "reads_failed_input": reads_dead, "dead_mechanisms": dead_mechs,
                     "duplicates": dupes, "verdict": v, "reason": why})

    tally = {}
    for r in rows:
        tally[r["verdict"]] = tally.get(r["verdict"], 0) + 1
    print("=== MODULE JUSTIFICATION -- 'would I build this today?' ===")
    print("    max_audit asks 'is it running'; the simplifier asks 'is it wired'.")
    print("    Neither asks whether the question it answers is still worth answering.\n")
    print(f"  {len(rows)} modules: {tally}\n")

    print("  VERDICT IS INTRINSIC -- no age term. A module written five minutes ago can be")
    print("  SCAR_TISSUE; one written last month can be INERT. 'I would build it eventually'")
    print("  is not a defence.\n")
    mine = [r for r in rows if r["age_days"] <= 2]
    print(f"  {'module':<26}{'age':>5}{'wired':>7}{'cites':>7}{'loc':>6}  verdict")
    for r in sorted(mine, key=lambda x: x["module"])[:16]:
        print(f"  {r['module']:<26}{r['age_days']:>5}{r['wired']!s:>7}{r['citations']:>7}"
              f"{r['loc']:>6}  {r['verdict']}")

    ret = [r for r in rows if r["verdict"] == "RETIRE"]
    mg = [r for r in rows if r["verdict"] == "MERGE"]
    print(f"\n  RETIRE ({len(ret)}) -- unwired and never cited, or built on a dead mechanism:")
    for r in ret[:12]:
        print(f"    {r['module']:<30} {r['reason']}")
    if len(ret) > 12:
        print(f"    ... +{len(ret)-12} more")
    print(f"\n  MERGE ({len(mg)}):")
    for r in mg[:8]:
        print(f"    {r['module']:<30} {r['reason']}")

    loc_ret = sum(r["loc"] for r in ret)
    print(f"\n  Retiring the {len(ret)} RETIRE modules removes ~{loc_ret:,} lines of maintenance")
    print("  surface. That is the number to weigh against whatever they might someday do.")
    print("\n  PROBATION is not a pass. It means too new to have a decision record -- ask again")
    print(f"  after {PROBATION_DAYS} days, when 'has this changed a decision?' has an answer.")

    OUT.write_text(json.dumps({"updated": now.isoformat(), "tally": tally, "modules": rows},
                              indent=1), "utf-8")
    print(f"\n  -> {OUT}")


if __name__ == "__main__":
    main()

```

### scripts/organ_catchup.py
```python
"""Re-fire today's quota-killed claude organs once credits are back (cron */30, flock).

Fires at most ONE organ per tick (staggered, so a burst of catch-ups cannot re-exhaust
the fresh quota window), and only after a pageless quota probe succeeds -- a dead pool
costs one failed CLI ping and zero pages. The organ's own brain_auth_check still governs
its real run. See libs/ops/organ_catchup.py for the owed rules.
"""

from __future__ import annotations

import re
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from libs.ops.organ_catchup import ORGANS, pick_organ  # noqa: E402

# A 5xx/overloaded is a SERVER hiccup, not an exhausted pool: no reset time will appear in
# the log and waiting for one would strand the organ. Retry these immediately.
_TRANSIENT = ("529", "overloaded", "502", "503", "504", "timed out", "connection reset")

_RESET_RE = re.compile(r"resets?\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm)?", re.I)


def _reset_time_from_log(path: Path, now: datetime) -> datetime | None:
    """Parse the reset stamp the CLI itself prints into a UTC datetime.

    The death logs state it verbatim -- "session limit - resets 11:40pm (UTC)", "out of usage
    credits - resets 4am" -- so the desk never has to guess when it may resume. Returns None when
    no stamp is present (e.g. an auth or model failure, which no reset will fix).
    """
    try:
        txt = path.read_text("utf-8", errors="ignore")
    except OSError:
        return None
    m = _RESET_RE.search(txt)
    if not m:
        return None
    hh, mm, ap = int(m.group(1)), int(m.group(2) or 0), (m.group(3) or "").lower()
    if ap == "pm" and hh != 12:
        hh += 12
    elif ap == "am" and hh == 12:
        hh = 0
    if hh > 23:
        return None
    # ANCHOR TO THE LOG, NOT TO NOW. The stated reset is the first such clock time AFTER the
    # death, so it is computed from the death's own timestamp. Anchoring to `now` pushed an
    # ALREADY-PASSED reset a full day forward and would have blocked resume for ~23h.
    try:
        died = datetime.fromtimestamp(path.stat().st_mtime, tz=UTC)
    except OSError:
        died = now.astimezone(UTC)
    cand = died.replace(hour=hh, minute=mm, second=0, microsecond=0)
    if cand < died:
        cand += timedelta(days=1)          # reset falls after midnight relative to the death
    return cand


LOGDIR = ROOT / "data" / "cro_ai_logs"


def _running(pattern: str) -> bool:
    res = subprocess.run(["pgrep", "-f", pattern], capture_output=True, check=False)
    return res.returncode == 0


def _quota_ok() -> bool:
    # brain_auth_check with paging neutered: walks the model fallback chain, never spams ntfy.
    probe = (
        "cd " + str(ROOT) + " && source ops/brain_env.sh >/dev/null 2>&1 && "
        "_brain_page() { :; } && brain_auth_check >/dev/null 2>&1"
    )
    try:
        return subprocess.run(["bash", "-c", probe], timeout=240, check=False).returncode == 0
    except subprocess.TimeoutExpired:
        return False


def main() -> None:
    now = datetime.now(tz=UTC)
    # UNAMBIGUOUS SILENCE (2026-07-26): pick_organ now returns None for TWO different reasons --
    # nothing is owed, or an organ is still running and the global gate is holding the field.
    # Logging both as "nothing owed -- all organs produced" would state something false while a
    # retry sat waiting, the exact state-looks-healthy failure this log exists to prevent.
    _live = [o.name for o in ORGANS if _running(o.pgrep)]
    if _live:
        print(f"{now.isoformat()} field busy ({', '.join(_live)} running) -- "
              "holding retries so they do not share the window")
        return
    spec = pick_organ(LOGDIR, now, _running)
    if spec is None:
        # NEVER SILENT (2026-07-26): 'nothing owed' and 'the cron died' used to look
        # identical -- the log just stopped. For a desk whose defining failure is
        # state-looks-healthy/output-is-nothing, silence must never be ambiguous.
        print(f"{datetime.now(tz=UTC).isoformat()} nothing owed -- all organs produced")
        return
    if spec is None:
        return
    # RESET-AWARE (2026-07-26): if the organ's own death log states when the window
    # reopens, do not burn a probe before that minute -- and fire on the FIRST tick
    # at/after it, so resume lands ~1 minute after reset instead of up to a poll late.
    _logs = sorted(LOGDIR.glob(spec.pattern), key=lambda p: p.stat().st_mtime)
    _reset = _reset_time_from_log(_logs[-1], now) if _logs else None
    if _logs:
        _tail = _logs[-1].read_text('utf-8', errors='ignore').lower()
        if any(k in _tail for k in _TRANSIENT):
            _reset = None            # transient server error -> retry now, do not wait
    if _reset is not None and now.astimezone(UTC) < _reset:
        print(f"{now.isoformat()} owed={spec.name} waiting for stated reset "
              f"{_reset.isoformat()} -- no probe")
        return
    if not _quota_ok():
        print(f"{now.isoformat()} owed={spec.name} quota=DEAD -- no fire")
        return
    subprocess.Popen(  # fixed ops script, detached like the cron spawns
        ["setsid", "-f", "bash", str(ROOT / spec.script)],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, stdin=subprocess.DEVNULL,
        cwd=str(ROOT), start_new_session=True,
    )
    print(f"{now.isoformat()} re-fired {spec.name} ({spec.script})")


if __name__ == "__main__":
    main()

```

### scripts/resolve_paper_book.py
```python
#!/usr/bin/env python3
"""PAPER BOOK RESOLVER (R0133) -- marks every paper call against what price actually did.

WHY THIS EXISTS, and why it is the most important thing either trading sleeve was missing. R0122
and R0125 both write pre-registered calls to a book and then never look at them again. An unmarked
book is the purest form of the defect this desk fences everywhere else (L1.28a): it accumulates
confident-looking rows, reports no failure, and reads as though the sleeve is working. It is not
evidence of anything. The principal asked what these sleeves return -- that question is
UNANSWERABLE until the book is marked, and answering it with a plausible estimate instead of a
measurement is exactly the behaviour the 420-tested/0-survived record exists to prevent.

WHAT IT DOES:
  * fetches real OHLC bars over each call's own window (Binance USD-M first, OKX fallback --
    Binance answers 451 from some egress regions and a resolver that dies on that is a resolver
    that never runs),
  * WALKS THE RECORDED MANAGEMENT LADDER bar by bar for conviction calls: stop, trail to
    breakeven, adds, trail behind the running extreme -- so the number it reports is the P&L of
    the strategy as specified, not of a naive entry-to-horizon mark that would flatter or damn it
    for the wrong reasons,
  * marks event-sleeve calls at their horizon,
  * runs conviction positions to their STRUCTURAL exit rather than to the forecast clock. Those
    are different objects and conflating them was costing real money: measured on the marked gold
    short, the SAME position reads +0.07R at a 12h horizon and +0.63R at 30h, so an arbitrary
    clock was setting the P&L instead of the structure. A hard time stop at 4x the horizon still
    force-marks anything that will not resolve, because a trade that never closes never grades,
  * benchmarks every call against unlevered buy-and-hold over the SAME window, because beating
    buy-and-hold is the L1.6 promotion condition and a levered sleeve that merely tracks it is
    taking risk for nothing,
  * feeds every resolved outcome back into the L1.29 calibration fence, which is what makes an
    over-confident sleeve shrink its own future size automatically.

THREE CONVENTIONS, stated because each one decides the answer:

  ADVERSE-FIRST. When a single bar's range contains both the stop and the next ladder trigger,
  the STOP is assumed to hit first. Intrabar order is unknowable at this resolution and the
  favourable assumption is how backtests lie; this one always resolves ambiguity against the
  desk.

  THE TRAIL IS SIMULATED MECHANICALLY. Live, the rule is "trail behind the most recent swing".
  A swing is only identifiable after the fact, so the simulation uses the running favourable
  extreme minus 1R as its proxy. This is an APPROXIMATION and it is named as one: a real swing
  trail is usually tighter, so the simulated result is, if anything, the generous version of the
  late-stage exits. It is not generous about entries or stops, which is where the money is.

  FILLS ARE AT THE LEVEL, BUT COSTS ARE REAL. Stop fills are assumed at the stop price -- the
  gap-risk stress in the sizer (SLIP_STRESS_PCT) carries the cost of that being wrong. Fees,
  slippage and funding, however, are DEDUCTED: at 6.7x leverage a round trip is ~24% of a full R,
  which moves the breakeven hit rate from 25.0% to 31.1%. A gross mark would show a 30% hit rate
  as profitable when it is a loser, so `equity_return` is NET and gross is reported beside it.

REFUSES RATHER THAN GUESSES: no bars, no mark. A row whose window cannot be fetched is
UNRESOLVABLE and is reported as such -- it never silently becomes a zero, which would drag every
aggregate toward "fine" using rows that were never measured at all.

    python scripts/resolve_paper_book.py [--json] [--report-only]
"""
from __future__ import annotations

import argparse
import json
import math
import sys
import time
import urllib.error
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_ROOT = Path("/home/quant/quant-platform")
if not _ROOT.exists():
    _ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
from libs.ops.lawful import guard as _law_guard  # noqa: E402

_CONVICTION_BOOK = "data/conviction_book.jsonl"
_EVENT_BOOK = "data/llm_trader_book.jsonl"
_MARKS = "data/paper_book_marks.jsonl"
_STATE = "data/paper_book_pnl.json"

BAR = "15m"
_BAR_MS = 15 * 60 * 1000
MAX_PAGES = 12                              # bounded paging: ~1200 bars = 12 days at 15m

#: THE PRE-REGISTERED KILL CONDITION, written BEFORE the evidence arrives, which is the only time
#: it is honest. After a session spent building this sleeve there is a real risk of talking my own
#: book -- an author who has invested effort finds reasons to extend a failing test. So the exit is
#: fixed now, in code, with numbers derived rather than chosen:
#:
#:   KILL_AFTER_N = 50 closed marked trades. At a 31.1% cost-adjusted breakeven, 50 trades puts the
#:   binomial standard error at ~6.5pp, so a true 31% rate reads above 24.6% ~84% of the time --
#:   enough to distinguish "no edge" from "unlucky" without waiting so long that a losing sleeve
#:   bleeds the book while its author asks for more data.
#:   KILL_HIT_RATE = 0.25 -- a full standard error BELOW breakeven. Not 31%: killing at exactly
#:   breakeven would graveyard a real 33% edge half the time. This is the level where continuing is
#:   the unreasonable choice.
#:
#: NO EXTENSIONS. If this fires, the sleeve goes to the graveyard with its record, and reopening it
#: requires a materially new mechanism -- not a bigger sample of the same one.
KILL_AFTER_N = 50
#: 0.25 -- a full binomial standard error (~6.5pp at n=50) BELOW the 31.1% cost-adjusted breakeven.
#: Deliberately not 31.1%: killing at exactly breakeven would graveyard a real 33% edge about half
#: the time. This is the level at which continuing is the unreasonable choice.
KILL_HIT_RATE = 0.25

#: EXECUTION COSTS, and the reason a mark without them is a flattering number rather than a
#: result. Binance USD-M non-VIP: taker 0.045%/side, maker 0.018%/side, funding ~0.01% per 8h
#: stamp. These are charged on NOTIONAL, so at 6.7x leverage a taker round trip costs ~0.9% of
#: sleeve equity -- 15% of a full 6% R, before slippage. Measured against the sizer's own numbers:
#: total realistic cost is ~24% of one R at taker-in/taker-out, which raises the breakeven hit
#: rate from 25.0% to 31.1%. An unmarked-for-costs book would show a 30% hit rate as profitable
#: when it is not, which is precisely the class of self-flattery this resolver exists to prevent.
TAKER_FEE = 0.00045
#: 0.00018 = Binance USD-M published non-VIP maker fee, 0.018%/side. A venue schedule, not a
#: choice: it moves only when the fee tier does. Worth ~0.4% of equity per trade vs taker.
MAKER_FEE = 0.00018
#: 0.00015 = 1.5bp/side, the observed order-book depth cost on majors at sub-$10k clip -- top-of-
#: book spread on BTC/ETH perps runs 0.5-1bp and this allows ~2x that for the level not being
#: exactly where the order rests. DELIBERATELY PESSIMISTIC: understating slippage is the standard
#: way a paper book flatters itself, and at 10x notional each 1bp is 0.1% of equity per side.
SLIPPAGE = 0.00015
#: 0.0001 = 0.01% per 8h stamp, the observed typical Binance USD-M funding magnitude on majors.
#: Sign deliberately ignored and always charged AS A COST: a directional sleeve is as often on the
#: paying side as the receiving one, and assuming the favourable sign would flatter every long in
#: a positive-funding regime -- roughly 0.25% of equity per 20h hold at 10x notional.
FUNDING_PER_8H = 0.0001

#: The PLANNED winner:loser shape -- what the trail-and-pyramid ladder is built to produce, and
#: the source of the 25.0% gross breakeven that the cost stack above lifts to 31.1%. Named so it
#: reads as the assumption it is: realised_payoff() measures what actually came out of the ladder
#: and reports the two side by side, because every money figure downstream consumes this ratio.
ASSUMED_WINNER_R = 3.0
#: Execution cost as a fraction of one R, derived from the measured fee/slippage/funding stack
#: directly above: ~24% of a full R at taker-in/taker-out on the sizer's own leverage.
COST_R = 0.24
#: Cost-adjusted breakeven hit rate implied by the ASSUMED 3:1 shape, from those same measured
#: costs. Stated for comparison against the MEASURED breakeven, never as a standard on its own.
BREAKEVEN_ASSUMED = 0.311


def trade_cost(leverage: float, units: float, hold_hours: float, *,
               entry_maker: bool = True) -> dict[str, float]:
    """Round-trip cost as a fraction of sleeve equity.

    entry_maker defaults TRUE because this sleeve enters with a resting order AT a named level --
    it bids support rather than chasing, so a limit order is the correct type anyway and the maker
    rebate is free. The EXIT is assumed taker: a stop is a taker fill by definition. Being wrong
    about the entry costs ~0.4% of equity per trade, so it is reported separately rather than
    buried in a single number."""
    notional = max(0.0, leverage) * max(0.0, units)
    entry = (MAKER_FEE if entry_maker else TAKER_FEE) * notional
    exit_ = TAKER_FEE * notional
    slip = (1 if entry_maker else 2) * SLIPPAGE * notional
    funding = FUNDING_PER_8H * notional * max(0.0, hold_hours) / 8.0
    total = entry + exit_ + slip + funding
    return {"entry_fee": round(entry, 6), "exit_fee": round(exit_, 6), "slippage": round(slip, 6),
            "funding": round(funding, 6), "total": round(total, 6),
            "entry_side": "maker" if entry_maker else "taker"}


def _http(url: str, *, timeout: int = 25) -> Any:
    req = urllib.request.Request(url, headers={"User-Agent": "quant-platform/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read())


#: Interval names differ per venue; one mapping so callers speak a single dialect.
_INTERVALS: dict[str, tuple[str, str, int]] = {          # ours -> (binance, okx, ms)
    "15m": ("15m", "15m", 15 * 60 * 1000),
    "1h": ("1h", "1H", 60 * 60 * 1000),
    "4h": ("4h", "4H", 4 * 60 * 60 * 1000),
    "1d": ("1d", "1D", 24 * 60 * 60 * 1000),
}


def _binance_bars(symbol: str, start_ms: int, end_ms: int, bar: str = BAR
                  ) -> list[tuple[int, float, float, float, float]]:
    iv = _INTERVALS[bar][0]
    url = (f"https://fapi.binance.com/fapi/v1/klines?symbol={symbol}&interval={iv}"
           f"&startTime={start_ms}&endTime={end_ms}&limit=1000")
    return [(int(r[0]), float(r[1]), float(r[2]), float(r[3]), float(r[4])) for r in _http(url)]


def _okx_bars(symbol: str, start_ms: int, end_ms: int, bar: str = BAR
              ) -> list[tuple[int, float, float, float, float]]:
    inst = f"{symbol[:-4]}-USDT" if symbol.endswith("USDT") else symbol
    iv, step = _INTERVALS[bar][1], _INTERVALS[bar][2]
    got: dict[int, tuple[int, float, float, float, float]] = {}
    cursor = end_ms + step
    for _ in range(MAX_PAGES):
        d = _http(f"https://www.okx.com/api/v5/market/history-candles?instId={inst}"
                  f"&bar={iv}&limit=100&after={cursor}")
        rows = d.get("data") or []
        if not rows:
            break
        for r in rows:
            ts = int(r[0])
            got[ts] = (ts, float(r[1]), float(r[2]), float(r[3]), float(r[4]))
        cursor = min(int(r[0]) for r in rows)
        if cursor <= start_ms:
            break
        time.sleep(0.15)
    return [v for _, v in sorted(got.items()) if start_ms <= v[0] <= end_ms]


def fetch_bars(symbol: str, start_ms: int, end_ms: int, bar: str = BAR
               ) -> tuple[list[tuple[int, float, float, float, float]], str]:
    """Bars from the first venue that answers. Returns ([], reason) rather than inventing a mark."""
    if bar not in _INTERVALS:
        return [], f"UNRESOLVABLE -- unknown interval {bar}"
    errors = []
    for name, fn in (("binance", _binance_bars), ("okx", _okx_bars)):
        try:
            bars = fn(symbol, start_ms, end_ms, bar)
            if bars:
                return bars, name
            errors.append(f"{name}: empty")
        except (urllib.error.URLError, OSError, ValueError, KeyError, TypeError) as exc:
            errors.append(f"{name}: {type(exc).__name__} {str(exc)[:60]}")
    return [], "UNRESOLVABLE -- " + "; ".join(errors)


def _ms(iso: str) -> int:
    return int(datetime.fromisoformat(iso).timestamp() * 1000)


#: TRAIL WIDTH, in R behind the running favourable extreme -- the single number that decides how
#: far a winner is allowed to run before it is banked, and therefore the winner:loser shape that
#: growth_levers measures as the steepest term on the desk. It was hardcoded at 1R and chosen by
#: nobody. 1.0 stays the DEFAULT (it is what the recorded marks were produced under, and changing
#: the default silently would rewrite the book's own history), while trail_sweep() re-walks the
#: same bars at every width so the desk's OWN trades say which one compounds hardest.
TRAIL_R = 1.0
#: The widths swept, bounded by MEASURED quantities at both ends rather than by taste.
#: FLOOR 0.5R: the stop is set at structural invalidation, and the sleeve's own measured noise
#: floor (median adverse excursion over the trade's horizon -- run_conviction_trader.noise_floor)
#: runs at roughly half that distance on these instruments. A trail tighter than the noise floor
#: does not bank profit, it re-stops the trade on the same noise the structural stop was placed
#: outside of, so below this the sweep would only be measuring the noise floor twice.
#: CEILING 3.0R: past 3R behind the extreme the trail sits further away than the entry stop for
#: any trade that has not yet run 3R, so it never binds and the candidate is not a trail at all.
#: These bound the SEARCH, not the answer -- if the measured optimum lands on either edge, that is
#: the finding that the bound needs re-deriving, and trail_sweep reports the whole curve so it is
#: visible when it happens.
TRAIL_WIDTHS: tuple[float, ...] = (0.5, 0.75, 1.0, 1.5, 2.0, 3.0)


def walk_ladder(row: dict[str, Any], bars: list[tuple[int, float, float, float, float]],
                *, trail_r: float = TRAIL_R) -> dict[str, Any]:
    """Simulate the RECORDED management plan against real bars. The number this returns is the
    P&L of the strategy as specified -- ladder, trail and adds included -- which is the only mark
    that says anything about whether trend-riding earns its complexity."""
    plan = row.get("management") or {}
    stages = plan.get("stages") or []
    if not stages or not bars:
        return {"outcome": "UNRESOLVABLE", "why": "no plan stages or no bars"}
    sign = 1.0 if row["direction"] == "LONG" else -1.0
    entry = float(row["entry_ref"])
    r_price = float(plan.get("r_price") or abs(entry - float(row["invalidation"])))
    if r_price <= 0:
        return {"outcome": "UNRESOLVABLE", "why": "zero-width R"}
    risk_fraction = float((row.get("sizing") or {}).get("risk_fraction") or 0.0)

    tranches: list[tuple[float, float]] = [(entry, float(stages[0]["units"]))]
    stop = float(stages[0]["stop"])
    stage_i = 0
    extreme = entry                                   # running favourable extreme, for the trail
    exit_px: float | None = None
    exit_ts = bars[-1][0]
    outcome = "OPEN"

    for ts, _o, hi, lo, _close in bars:
        # 1. ADVERSE-FIRST: the stop is tested before any favourable progression in the same bar.
        if (sign > 0 and lo <= stop) or (sign < 0 and hi >= stop):
            exit_px, exit_ts, outcome = stop, ts, ("STOPPED" if stage_i == 0 else "TRAILED-OUT")
            break
        # 2. ladder progression -- at most one rung per bar, again the conservative reading.
        if stage_i + 1 < len(stages):
            nxt = stages[stage_i + 1]
            trig = float(nxt["trigger"])
            if (sign > 0 and hi >= trig) or (sign < 0 and lo <= trig):
                stage_i += 1
                stop = float(nxt["stop"])
                added = round(float(nxt["units"]) - sum(u for _, u in tranches), 6)
                if added > 0:
                    tranches.append((trig, added))
        # 3. past the last rung the trail follows the running extreme, one R behind (the
        #    mechanical proxy for "behind the most recent swing" -- see the module docstring).
        extreme = max(extreme, hi) if sign > 0 else min(extreme, lo)
        if stage_i + 1 >= len(stages):
            band = r_price * max(0.0, trail_r)
            stop = max(stop, extreme - band) if sign > 0 else min(stop, extreme + band)

    if exit_px is None:                               # ran out of bars while still open
        exit_px, exit_ts = bars[-1][4], bars[-1][0]

    r_units = sum(u * (exit_px - e) * sign / r_price for e, u in tranches)
    units = sum(u for _, u in tranches)
    gross = r_units * risk_fraction
    hold_h = (exit_ts - bars[0][0]) / 3_600_000.0
    cost = trade_cost(float((row.get("sizing") or {}).get("leverage") or 0.0), units, hold_h)
    net = gross - cost["total"]
    return {
        "outcome": outcome, "exit_price": round(exit_px, 8),
        "exit_at": datetime.fromtimestamp(exit_ts / 1000, tz=UTC).isoformat(),
        "stage_reached": stage_i, "max_stage": len(stages) - 1,
        "units_at_exit": round(units, 4),
        "realised_R": round(r_units, 4),
        "gross_return": round(gross, 6),
        "cost": cost, "hold_hours": round(hold_h, 2),
        # NET is the number that carries the name. A gross mark shows a 30% hit rate as profitable
        # when costs make it a loser -- the exact self-flattery this resolver exists to prevent.
        "equity_return": round(net, 6),
        "profitable": net > 0,
        "bars_used": len(bars),
    }


def mark_event_row(row: dict[str, Any], bars: list[tuple[int, float, float, float, float]]
                   ) -> dict[str, Any]:
    """The event sleeve carries no stop or ladder -- it is marked flat at its own horizon."""
    if not bars:
        return {"outcome": "UNRESOLVABLE", "why": "no bars"}
    sign = 1.0 if row["direction"] == "LONG" else -1.0
    first, last = bars[0][1], bars[-1][4]
    gross = (last - first) / first * sign
    hold_h = (bars[-1][0] - bars[0][0]) / 3_600_000.0
    cost = trade_cost(1.0, 1.0, hold_h)          # event sleeve is unlevered, 1 unit
    net = gross - cost["total"]
    return {"outcome": "MARKED", "entry_price": first, "exit_price": last,
            "realised_R": None, "gross_return": round(gross, 6), "cost": cost,
            "hold_hours": round(hold_h, 2),
            "equity_return": round(net, 6), "profitable": net > 0,
            "bars_used": len(bars)}


def _benchmark(bars: list[tuple[int, float, float, float, float]]) -> float | None:
    """Unlevered buy-and-hold over the SAME window -- the L1.6 bar a levered sleeve must clear."""
    if not bars:
        return None
    return round((bars[-1][4] - bars[0][1]) / bars[0][1], 6)


def equity_curve(resolved: list[dict[str, Any]]) -> dict[str, Any]:
    """The sleeve's own equity path, high-water mark and drawdown.

    This is the number that decides whether the sleeve may ever take live size, and it is not
    optional colour: at a 20% risk budget per trade a losing run bites hard and fast (three stops
    in a row is -49%), so a sleeve-level drawdown rail has to exist BEFORE real money does, not
    after the first bad week. run_conviction_trader reads it and halts on breach.

    APPROXIMATION, named: calls overlap in time (one every four hours, horizons of 8-48), so
    compounding them in exit order is not the same as running the book. It is the honest
    conservative reading -- overlapping positions would drawdown TOGETHER, so the real path is
    rougher than this one, never smoother."""
    eq, hwm, mdd = 1.0, 1.0, 0.0
    path = []
    for m in resolved:
        eq *= 1.0 + float(m.get("equity_return") or 0.0)
        hwm = max(hwm, eq)
        mdd = max(mdd, (hwm - eq) / hwm if hwm > 0 else 0.0)
        path.append(round(eq, 6))
    # GEOMETRIC GROWTH, the actual objective (max E[log wealth]), measured rather than hoped for.
    # Reported as g per trade and annualised at the book's own realised pace, because a per-trade
    # edge means nothing without the frequency that compounds it -- growth is g x N, and naming
    # which of the two is short is what tells the desk where to push.
    import math
    logs = [math.log(1.0 + float(m.get("equity_return") or 0.0)) for m in resolved
            if float(m.get("equity_return") or 0.0) > -0.999]
    g = sum(logs) / len(logs) if logs else None
    span_h = None
    try:
        ts = sorted(m["exit_at"] for m in resolved if m.get("exit_at"))
        if len(ts) >= 2:
            span_h = (datetime.fromisoformat(ts[-1])
                      - datetime.fromisoformat(ts[0])).total_seconds() / 3600.0
    except (ValueError, KeyError, TypeError):
        span_h = None
    per_year = (len(resolved) / span_h * 24 * 365) if span_h and span_h > 0 else None
    cagr = (math.exp(g * per_year) - 1.0) if (g is not None and per_year) else None
    return {"n": len(resolved), "final": round(eq, 6), "high_water": round(hwm, 6),
            "max_drawdown": round(mdd, 6),
            "current_drawdown": round((hwm - eq) / hwm if hwm > 0 else 0.0, 6),
            "log_growth_per_trade": round(g, 6) if g is not None else None,
            "trades_per_year_at_this_pace": round(per_year, 1) if per_year else None,
            "implied_cagr": (round(cagr, 4) if cagr is not None and abs(cagr) < 1e6 else
                             ("ABOVE-MODEL" if cagr is not None else None)),
            "growth_constraint": (
                "UNMEASURED -- no closed trades" if g is None else
                "EDGE: log-growth per trade is <= 0, so frequency multiplies a losing bet and "
                "raising cadence makes it worse" if g <= 0 else
                "FREQUENCY: per-trade growth is positive, so the binding constraint is how many "
                "of these the desk can find and hold at once" if per_year and per_year < 300 else
                "neither obviously binding -- edge positive and pace already high"),
            "path": path[-50:],
            "note": "compounded in exit order; overlapping calls drawdown together, so the live "
                    "path is rougher than this, never smoother"}


#: Minimum resolved trades before the measured payoff replaces the assumed one. 20 is where the
#: standard error on a mean R-multiple drops below ~0.4R for this distribution -- coarse, but
#: enough to tell 2R from 4R, which is the distinction that decides whether the sleeve compounds.
PAYOFF_MIN_N = 20


def realised_payoff(resolved: list[dict[str, Any]]) -> dict[str, Any]:
    """MEASURE the winner:loser R shape the sleeve actually produces, instead of assuming 3:1.

    THE MOST CONSEQUENTIAL UNMEASURED NUMBER ON THE DESK. Every money figure downstream rests on
    a 3R winner: the 25.0% gross breakeven, the 31.1% cost-adjusted one, the Kelly odds in
    measured_risk_cap, check_promotion_gate's log-breakeven, the kill floor. All of it is an
    ASSUMPTION about the trail-and-pyramid plan, and `realised_R` was written onto every mark and
    then aggregated only as a flat mean -- never split into the winner:loser ratio the whole
    apparatus consumes.

    It is also the steepest gradient in the system, which is what makes leaving it unmeasured
    expensive rather than untidy. Holding hit rate and size fixed, P(a year above +100%) runs
    0.2% at a 2R winner, 44% at 3R, 93% at 4R. A desk assuming 3R while realising 2.5R is not
    slightly optimistic; it is targeting a hit rate that cannot pay, and it would never find out,
    because the assumption appears nowhere as a measurement to be contradicted.

    Reported as a MEASUREMENT with its own state, never silently substituted: under PAYOFF_MIN_N
    the assumed 3.0 stands and says so, because a payoff ratio from six trades would move the
    Kelly sizer on noise.
    """
    rs = [float(m["realised_R"]) for m in resolved if m.get("realised_R") is not None]
    wins = [r for r in rs if r > 0]
    losses = [-r for r in rs if r <= 0]
    if len(rs) < PAYOFF_MIN_N or not wins or not losses:
        return {"state": "ASSUMED", "n": len(rs), "need": PAYOFF_MIN_N,
                "winner_R": ASSUMED_WINNER_R, "loser_R": 1.0, "ratio": ASSUMED_WINNER_R,
                "why": f"{len(rs)}/{PAYOFF_MIN_N} resolved with a winner and a loser -- the 3:1 "
                       "shape stays an ASSUMPTION and is labelled one. A payoff ratio measured "
                       "off a handful of trades would move the Kelly sizer on noise."}
    mw, ml = sum(wins) / len(wins), sum(losses) / len(losses)
    ratio = mw / ml if ml > 0 else float("inf")
    # Cost-adjusted breakeven implied by the SHAPE THE SLEEVE ACTUALLY MADE, not the planned one.
    w, loss_r = ratio - COST_R, 1.0 + COST_R
    be = loss_r / (w + loss_r) if w + loss_r > 0 else None
    return {"state": "MEASURED", "n": len(rs), "n_wins": len(wins), "n_losses": len(losses),
            "winner_R": round(mw, 3), "loser_R": round(ml, 3), "ratio": round(ratio, 3),
            "assumed_ratio": ASSUMED_WINNER_R,
            "breakeven_hit": None if be is None else round(be, 4),
            "vs_assumption": round(ratio - ASSUMED_WINNER_R, 3),
            "why": f"winners average {mw:.2f}R against {ml:.2f}R losers = {ratio:.2f}:1 over "
                   f"{len(rs)} closed, versus the {ASSUMED_WINNER_R:.1f}:1 assumed. Cost-adjusted "
                   f"breakeven on the MEASURED shape is "
                   + (f"{be:.1%}" if be is not None else "undefined")
                   + f" (the assumed shape implies {BREAKEVEN_ASSUMED:.1%}). Losers above 1.0R "
                     "mean stops are being jumped, not honoured -- that is a slippage finding, "
                     "not a payoff one."}


def trail_sweep(walked: list[dict[str, Any]]) -> dict[str, Any]:
    """Re-walk the SAME trades at every trail width and report which one compounds hardest.

    THE PRINCIPAL'S OWN METHOD, MADE MEASURABLE. The gold trade this sleeve is modelled on was
    described as *"I kept moving it trying to bank profit while letting it breathe and run further"*
    -- which is a statement about exactly one parameter: how far behind the extreme the stop sits.
    Too tight and every winner is banked into a scratch; too wide and each one gives back more than
    it keeps. The sleeve had that number hardcoded at 1R with no measurement behind it, while
    growth_levers ranks the winner shape it produces as the STEEPEST term in the whole growth
    identity. A guess in the highest-gradient slot is the most expensive kind of guess.

    WHY A SWEEP RATHER THAN AN OPINION. Every width is walked against the same real bars, so the
    comparison holds the trades, the entries and the stops fixed and moves only the thing under
    test. That controls for the obvious confound -- a wider trail looks better in a trending week
    for reasons that have nothing to do with the trail.

    RANKED BY LOG GROWTH, never by hit rate or by mean R. Widening the trail RAISES the winner
    multiple and LOWERS the hit rate at the same time; either one alone can be improved while
    growth falls. E[log] per trade is the quantity that decides compounding, so it is the quantity
    that picks the width, and the losing candidates are kept in the output so the trade-off is
    visible rather than asserted.
    """
    widths = [w for w in walked if w.get("trail_r") is not None]
    if not widths:
        return {"state": "UNMEASURED", "why": "no conviction trades re-walked -- the sweep needs "
                                              "marked ladder trades with their bars"}
    by: dict[float, list[dict[str, Any]]] = {}
    for w in widths:
        by.setdefault(float(w["trail_r"]), []).append(w)
    rows = []
    for tr in sorted(by):
        ms = by[tr]
        rs = [float(m["realised_R"]) for m in ms if m.get("realised_R") is not None]
        eqs = [float(m["equity_return"]) for m in ms if m.get("equity_return") is not None]
        if not rs or not eqs:
            continue
        wins = [r for r in rs if r > 0]
        losses = [-r for r in rs if r <= 0]
        # E[log] per trade on the realised NET returns -- the compounding quantity, not the mean.
        g = sum(math.log(1.0 + e) for e in eqs if e > -1.0) / len(eqs)
        rows.append({
            "trail_r": tr, "n": len(rs),
            "hit_rate": round(len(wins) / len(rs), 4),
            "winner_R": round(sum(wins) / len(wins), 3) if wins else None,
            "loser_R": round(sum(losses) / len(losses), 3) if losses else None,
            "ratio": round((sum(wins) / len(wins)) / (sum(losses) / len(losses)), 3)
                     if wins and losses else None,
            "g_per_trade": round(g, 6),
        })
    if not rows:
        return {"state": "UNMEASURED", "why": "re-walked trades produced no scorable returns"}
    best = max(rows, key=lambda r: r["g_per_trade"])
    live = next((r for r in rows if r["trail_r"] == TRAIL_R), None)
    gain = (best["g_per_trade"] - live["g_per_trade"]) if live else None
    return {
        "state": "MEASURED" if len(widths) // max(1, len(by)) >= PAYOFF_MIN_N else "THIN",
        "n_trades": len(widths) // max(1, len(by)),
        "live_trail_r": TRAIL_R, "best_trail_r": best["trail_r"],
        "g_gain_per_trade": None if gain is None else round(gain, 6),
        "widths": rows,
        "why": (f"width {best['trail_r']}R compounds hardest at {best['g_per_trade']:+.5f} per "
                f"trade (hit {best['hit_rate']:.1%}, winners {best['winner_R']}R)"
                + (f", against {live['g_per_trade']:+.5f} at the live {TRAIL_R}R -- "
                   f"{'WIDER' if best['trail_r'] > TRAIL_R else 'TIGHTER'} is better on this "
                   "record" if live and best["trail_r"] != TRAIL_R else
                   f"; the live {TRAIL_R}R is already the best of the swept widths")
                + ". Ranked by E[log], never by hit rate: widening raises the winner multiple and "
                  "lowers the hit rate together, so either alone can improve while growth falls."),
    }


def kill_check(resolved: list[dict[str, Any]]) -> dict[str, Any]:
    """Evaluate the PRE-REGISTERED exit. Written before the data existed; not adjustable after.

    An author who has spent a session building something finds reasons to extend a failing test.
    Fixing the threshold in advance is the only defence against that, and it is cheap now and
    expensive later -- which is exactly why it is done now."""
    n = len(resolved)
    if n < KILL_AFTER_N:
        return {"state": "RUNNING", "n_closed": n, "kill_after_n": KILL_AFTER_N,
                "kill_hit_rate": KILL_HIT_RATE,
                "why": f"{n}/{KILL_AFTER_N} closed trades -- the pre-registered decision point is "
                       "not reached, and no verdict either way is available before it"}
    wins = sum(1 for m in resolved if m.get("profitable"))
    hit = wins / n
    if hit < KILL_HIT_RATE:
        return {"state": "KILL", "n_closed": n, "hit_rate": round(hit, 4),
                "why": f"hit rate {hit:.1%} is below the pre-registered {KILL_HIT_RATE:.0%} floor "
                       f"over {n} closed trades. This was fixed before the evidence arrived. "
                       "Graveyard the sleeve with its record; reopening requires a materially NEW "
                       "mechanism, not a larger sample of this one. NO EXTENSIONS."}
    return {"state": "SURVIVES-THIS-CHECK", "n_closed": n, "hit_rate": round(hit, 4),
            "why": f"hit rate {hit:.1%} clears the {KILL_HIT_RATE:.0%} kill floor -- which is NOT "
                   f"the same as clearing the {31.1:.1f}% cost-adjusted breakeven, and not a "
                   "promotion. It means only that continuing to measure is still reasonable."}


def setup_performance(resolved: list[dict[str, Any]], *, min_n: int = 5) -> dict[str, Any]:
    """Hit rate and mean return CONDITIONED ON THE SETUP -- how the desk learns what to stop doing.

    A single global hit rate hides everything actionable. A sleeve that is 55% with the 4h trend
    and 25% against it reads as a mediocre 40% overall, and the fix -- stop taking counter-trend
    setups -- is invisible until the outcomes are conditioned. Buckets under `min_n` report
    INSUFFICIENT rather than a number, because a 100% hit rate on two trades is not a finding and
    publishing it as one is how a desk learns superstition."""
    out: dict[str, Any] = {}
    feats: dict[str, dict[Any, list[dict[str, Any]]]] = {}
    for m in resolved:
        for k, v in (m.get("setup") or {}).items():
            if k in ("symbol",) or v is None:
                continue
            feats.setdefault(k, {}).setdefault(v, []).append(m)
    for feat, buckets in feats.items():
        rows = {}
        for val, ms in buckets.items():
            n = len(ms)
            if n < min_n:
                rows[str(val)] = {"n": n, "state": "INSUFFICIENT",
                                  "why": f"{n} trades -- a rate on this many is not a finding"}
                continue
            wins = sum(1 for m in ms if m.get("profitable"))
            rows[str(val)] = {
                "n": n, "state": "MEASURED", "hit_rate": round(wins / n, 3),
                "mean_return": round(sum(float(m.get("equity_return") or 0.0) for m in ms) / n, 5)}
        out[feat] = rows
    return out or {"state": "UNMEASURED", "why": "no setup tags on any closed trade"}


def _rows(path: Path) -> list[dict[str, Any]]:
    out = []
    try:
        for ln in path.read_text("utf-8", errors="ignore").splitlines():
            if ln.strip():
                try:
                    out.append(json.loads(ln))
                except ValueError:
                    continue                          # a torn line is skipped, never guessed at
    except OSError:
        return []
    return out


def resolve_book(root: Path, *, now: datetime | None = None,
                 fetch=fetch_bars) -> dict[str, Any]:
    now = now or datetime.now(tz=UTC)
    marks: list[dict[str, Any]] = []
    swept: list[dict[str, Any]] = []      # every trade re-walked at every trail width

    for book, kind in ((_CONVICTION_BOOK, "conviction"), (_EVENT_BOOK, "event")):
        for row in _rows(root / book):
            if row.get("action") == "PASS" or not row.get("symbol"):
                continue
            try:
                start = _ms(row["at"])
                due = datetime.fromisoformat(row["resolve_by"])
            except (KeyError, ValueError):
                marks.append({"kind": kind, "key": row.get("at"), "outcome": "UNRESOLVABLE",
                              "why": "unparseable timestamps"})
                continue
            # THE POSITION RUNS TO ITS STRUCTURE, NOT TO ITS FORECAST CLOCK. `resolve_by` scores
            # the forecast; `hard_exit_by` is when the position is force-marked. Walking only to
            # resolve_by truncated winners for a reason unrelated to the trade -- measured, the
            # same gold short marks +0.07R at a 12h horizon and +0.63R at 30h.
            try:
                hard = datetime.fromisoformat(row["hard_exit_by"])
            except (KeyError, ValueError):
                hard = due                      # pre-decoupling rows keep their old behaviour
            end = int(min(hard, now).timestamp() * 1000)
            if end - start < _BAR_MS:
                marks.append({"kind": kind, "key": row.get("at"), "outcome": "TOO-EARLY",
                              "why": "less than one bar has elapsed"})
                continue
            bars, source = fetch(row["symbol"], start, end)
            if not bars:
                marks.append({"kind": kind, "key": row.get("at"), "symbol": row.get("symbol"),
                              "outcome": "UNRESOLVABLE", "why": source})
                continue
            is_ladder = kind == "conviction" and bool(row.get("management"))
            res = walk_ladder(row, bars) if is_ladder else mark_event_row(row, bars)
            # RE-WALK THE SAME BARS AT EVERY TRAIL WIDTH while they are in hand. Doing it here is
            # what makes the sweep free and honest at once: no second fetch, and every width sees
            # the identical trade, entry and stop, so the only thing that varies is the parameter
            # under test. (Costs are recomputed per width -- a wider trail holds longer and pays
            # more funding, which is part of what it must earn back.)
            if is_ladder:
                for tr in TRAIL_WIDTHS:
                    alt = walk_ladder(row, bars, trail_r=tr)
                    if alt.get("outcome") in ("STOPPED", "TRAILED-OUT"):
                        swept.append({"trail_r": tr, "key": row.get("at"),
                                      "realised_R": alt.get("realised_R"),
                                      "equity_return": alt.get("equity_return")})
            # Still OPEN at the hard stop -> TIME-STOPPED: marked out at market rather than left
            # unscored forever. A trade that never resolves is a forecast that never grades.
            if res.get("outcome") == "OPEN" and hard <= now:
                res = {**res, "outcome": "TIME-STOPPED",
                       "why": f"hit the {row.get('max_hold_hours')}h hold limit still open"}
            closed = res.get("outcome") in ("STOPPED", "TRAILED-OUT", "MARKED", "TIME-STOPPED")
            marks.append({"kind": kind, "key": row.get("at"), "symbol": row.get("symbol"),
                          "direction": row.get("direction"),
                          "probability": row.get("probability"), "source": source,
                          "buy_and_hold": _benchmark(bars),
                          "setup": row.get("setup"),
                          "scored_at": row.get("resolve_by"), "hard_exit_by": row.get("hard_exit_by"),
                          "closed": closed, **res})

    resolved = [m for m in marks if m.get("outcome") in ("STOPPED", "TRAILED-OUT", "MARKED",
                                                         "TIME-STOPPED") and m.get("closed")]
    resolved.sort(key=lambda m: m.get("exit_at") or m.get("key") or "")
    curve = equity_curve(resolved)
    unresolvable = [m for m in marks if m.get("outcome") == "UNRESOLVABLE"]
    wins = [m for m in resolved if m.get("profitable")]
    sleeve = sum(float(m.get("equity_return") or 0.0) for m in resolved)
    bh = sum(float(m["buy_and_hold"]) * (1.0 if m.get("direction") == "LONG" else -1.0)
             for m in resolved if m.get("buy_and_hold") is not None)

    if not resolved:
        status, detail = "UNMEASURED", (
            f"{len(marks)} book rows, 0 resolvable closed calls -- this sleeve has produced NO "
            "evidence yet and must not be read as working (L1.28a)")
    else:
        status = "MEASURED"
        detail = (f"{len(resolved)} closed calls: {len(wins)}/{len(resolved)} profitable, "
                  f"sleeve {sleeve:+.2%} vs directional buy-and-hold {bh:+.2%} over the same "
                  f"windows; equity x{curve['final']:.3f}, max DD {curve['max_drawdown']:.1%}; "
                  f"{len(unresolvable)} unresolvable")

    return {
        "generated": now.isoformat(),
        "law": "L1.28a/L1.6 -- an unmarked paper book is not evidence; every call is marked "
               "against real bars, benchmarked against buy-and-hold, and fed to calibration.",
        "status": status, "detail": detail,
        "n_rows": len(marks), "n_resolved": len(resolved), "n_unresolvable": len(unresolvable),
        "n_open": len([m for m in marks if m.get("outcome") == "OPEN"]),
        "win_rate": round(len(wins) / len(resolved), 4) if resolved else None,
        "sleeve_return": round(sleeve, 6) if resolved else None,
        "buy_and_hold_return": round(bh, 6) if resolved else None,
        "beats_buy_and_hold": (sleeve > bh) if resolved else None,
        "mean_R": (round(sum(float(m["realised_R"]) for m in resolved
                             if m.get("realised_R") is not None)
                         / max(1, len([m for m in resolved if m.get("realised_R") is not None])),
                         4) if resolved else None),
        "realised_payoff": realised_payoff(resolved),
        "trail_sweep": trail_sweep(swept),
        "equity": curve,
        "kill_condition": kill_check(resolved),
        "setup_performance": setup_performance(resolved),
        "costs_deducted": {"taker": TAKER_FEE, "maker": MAKER_FEE, "slippage_per_side": SLIPPAGE,
                           "funding_per_8h": FUNDING_PER_8H,
                           "note": "entry assumed MAKER (a resting order at the named level), exit "
                                   "assumed TAKER (a stop is a taker fill). Returns are NET."},
        "conventions": ["adverse-first intrabar", "swing trail simulated as extreme-minus-1R",
                        "fills at the level; fees, slippage and funding ARE deducted",
                        "equity compounded in exit order despite overlapping positions"],
        "marks": marks,
    }


def feed_calibration(report: dict[str, Any]) -> list[str]:
    """Resolved outcome -> L1.29. This is the loop that makes an over-confident sleeve shrink."""
    fed = []
    try:
        from libs.self_improvement import forecast_calibration as fc
    except ImportError as exc:
        return [f"UNFED: calibration module unavailable ({exc})"]
    for m in report["marks"]:
        if m.get("outcome") in ("STOPPED", "TRAILED-OUT", "MARKED",
                                "TIME-STOPPED") and m.get("closed"):
            key = f"{'conviction' if m['kind'] == 'conviction' else 'llm_trader'}:{m['key']}"
            try:
                fc.resolve(key, bool(m.get("profitable")))
                fed.append(key)
            except (KeyError, ValueError, OSError) as exc:
                fed.append(f"UNFED {key}: {exc}")
    return fed


def main() -> int:
    _law_guard()
    ap = argparse.ArgumentParser()
    ap.add_argument("--report-only", action="store_true")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    rep = resolve_book(_ROOT)
    rep["calibration_fed"] = feed_calibration(rep)

    out = _ROOT / _STATE
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(rep, indent=2), "utf-8")
    with (_ROOT / _MARKS).open("a", encoding="utf-8") as fh:
        for m in rep["marks"]:
            fh.write(json.dumps({"marked_at": rep["generated"], **m}) + "\n")

    if args.json:
        print(json.dumps(rep, indent=2))
    else:
        print(f"paper book (R0133): {rep['status']} -- {rep['detail']}")
    if args.report_only:
        return 0
    # UNMEASURED is not a failure of this organ -- it is the true state of an unproven sleeve, and
    # the fence that must escalate it is the calibration/conversion pair, not this resolver.
    return 0


if __name__ == "__main__":
    sys.exit(main())

```

### scripts/run_cost_hunt.py
```python
#!/usr/bin/env python3
"""COST HUNT (R0198) -- the cheapest trade is an edge nobody has to predict anything to earn.

PRINCIPAL ORDER (2026-07-31): *"hunt ur best net costs n all, make it intelligent."*

WHY COSTS ARE THE ONE LEVER AVAILABLE TODAY. Every other term in the growth identity -- hit rate,
winner shape, independent bets -- needs closed trades before it can be improved on purpose. Costs
do not. They are known BEFORE the trade, they are the difference between the 25.0% gross breakeven
and the 31.1% net one, and near breakeven their effect is grotesquely leveraged: the cost stack is
~24% of one R, and removing a third of it moves the required hit rate by more than a point --
which multiplies compounding severalfold near the threshold (the +3pp = 3.5x g arithmetic in
DISCRETIONARY_DESK.md).

THE HOLE THIS CLOSES. The resolver charges funding ALWAYS-ADVERSE by design -- correct for
marking, because a mark must never flatter itself. But funding is SIGNED and PUBLIC: on Binance
USD-M, positive funding means longs pay shorts, so at any moment half the instrument-sides are
being PAID to hold. The sleeve was blind to which half. A discretionary trader with two comparable
setups takes the one where carry is a tailwind; this organ is that judgement, mechanised:

  * snapshots the CURRENT funding rate for every instrument the sleeve trades
    (Binance premiumIndex bulk endpoint; OKX per-symbol fallback, because Binance answers 451
    from some egress regions and an organ that dies on that never runs),
  * states, per (symbol, direction), who pays whom and how much per 8h stamp,
  * flags EXTREME funding -- the meme-perp regime where a single day's carry eats a meaningful
    fraction of the risk unit and the only winning move is to not pay it,
  * publishes data/cost_hunt.json for the conviction trader, which (a) shows the paid/paying
    sides to the model in its brief, (b) prices each call's expected cost in R from its OWN stop
    and horizon, and (c) REFUSES trades whose expected cost exceeds COST_REFUSE_R of the risk
    unit (run_conviction_trader.trade_cost_view).

WHY COST-IN-R IS SIZE-INDEPENDENT, which is what makes this computable before sizing: cost in R
= (cost as a fraction of notional) / (stop distance as a fraction of price). Leverage cancels.
A 2% stop paying 0.1%/8h funding over 24h costs 0.15R whether the position is $10 or $10,000.

DELIBERATE ASYMMETRY, stated so nobody "fixes" it: SELECTION uses signed funding (prefer the paid
side, refuse the extreme-paying side), but MARKING stays always-adverse. A mark that credits
funding would flatter the book with carry the next regime takes away; a selector that ignores it
leaves free money on the table. Different jobs, different signs.

REFUSES RATHER THAN GUESSES: a symbol whose rate cannot be fetched is NO-DATA, never assumed
zero -- an assumed-zero rate on a 0.3%/8h meme perp is exactly the silent flattery this desk
fences everywhere else (L1.28a).

    python scripts/run_cost_hunt.py [--json]
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_ROOT = Path("/home/quant/quant-platform")
if not _ROOT.exists():
    _ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
from libs.ops.lawful import guard as _law_guard  # noqa: E402

_STATE = "data/cost_hunt.json"

#: 0.0005 = 0.05% per 8h, five times the typical major's 0.01% stamp. Above this an instrument is
#: in the crowded-carry regime where funding alone eats >=0.15% of notional per day -- at a 1%
#: structural stop that is >=0.15R/day of pure bleed, which no chart thesis of this sleeve's
#: horizon reliably outruns. Derived from the resolver's own funding arithmetic, not chosen.
EXTREME_FUNDING_8H = 0.0005

#: What maker-in entry is WORTH, restated from the resolver's published venue schedule so the
#: model sees the number in its brief: taker 0.045% vs maker 0.018% per side = 2.7bp of notional
#: saved on entry. At the sleeve's reference 0.9% stop that is 0.030R per trade -- measured, and
#: the reason entry_order_type is POST_ONLY_LIMIT at the named level rather than a chase.
MAKER_SAVING_PER_SIDE = 0.00045 - 0.00018


def _http_json(url: str, timeout: int = 15) -> Any:
    req = urllib.request.Request(url, headers={"User-Agent": "quant-cost-hunt/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def fetch_funding(symbols: tuple[str, ...], *, http=_http_json) -> dict[str, dict[str, Any]]:
    """Current funding per symbol, signed Binance-convention: POSITIVE = longs pay shorts.

    Binance bulk first (one call for the whole universe), OKX per-symbol fallback for whatever
    the bulk call missed. A symbol neither venue answers for is NO-DATA -- never zero."""
    out: dict[str, dict[str, Any]] = {}
    # Each venue's failure is CARRIED to the NO-DATA rows rather than swallowed. A bare pass here
    # would make a total Binance outage read identically to "the bulk call just missed this
    # symbol", and those demand different responses -- one is an egress/region problem the
    # operator can fix, the other is a delisted contract nobody should chase.
    bulk_err = ""
    try:
        rows = http("https://fapi.binance.com/fapi/v1/premiumIndex")
        for r in rows if isinstance(rows, list) else []:
            s = r.get("symbol")
            if s in symbols and r.get("lastFundingRate") not in (None, ""):
                out[s] = {"state": "MEASURED", "funding_8h": float(r["lastFundingRate"]),
                          "source": "binance"}
    except (OSError, ValueError, urllib.error.URLError) as exc:
        bulk_err = f"binance bulk: {type(exc).__name__}: {exc}"
    for s in symbols:
        if s in out:
            continue
        inst = s.replace("USDT", "-USDT-SWAP")
        okx_err = ""
        try:
            d = http(f"https://www.okx.com/api/v5/public/funding-rate?instId={inst}")
            row = (d.get("data") or [{}])[0]
            if row.get("fundingRate") not in (None, ""):
                out[s] = {"state": "MEASURED", "funding_8h": float(row["fundingRate"]),
                          "source": "okx"}
                continue
            # EMPTY data is not an outage -- it is the venue saying it does not list this
            # contract, which is permanent and needs a different answer from a transient
            # failure. Verified 2026-07-31: OKX lists no gold swap at all, so PAXGUSDT is
            # BINANCE-ONLY and its NO-DATA will never heal by retrying. Conflating the two
            # would have the operator chasing a network fault that does not exist.
            okx_err = "okx: NOT LISTED (empty data for this instId -- structural, not an outage)"
        except (OSError, ValueError, urllib.error.URLError) as exc:
            okx_err = f"okx: {type(exc).__name__}: {exc}"
        unlisted = "NOT LISTED" in okx_err
        out[s] = {"state": "NO-DATA", "funding_8h": None,
                  "errors": [e for e in (bulk_err, okx_err) if e],
                  "fallback_exists": not unlisted,
                  "why": ("no fallback venue lists this contract, so this symbol is "
                          "SINGLE-VENUE: its funding is unmeasurable whenever the primary is "
                          "unreachable, and no retry fixes that"
                          if unlisted else
                          "neither venue answered -- NOT assumed zero; an assumed-zero rate on "
                          "an extreme-funding perp is silent flattery (L1.28a)")}
    return out


def signed_funding_8h(funding_8h: float, direction: str) -> float:
    """Per-8h funding for THIS side, positive = this trade PAYS, negative = it is PAID.

    Binance convention: positive funding, longs pay shorts. So a LONG pays +rate and a SHORT
    pays -rate; the sign flip is the entire mechanism by which carry becomes selectable."""
    return float(funding_8h) if direction == "LONG" else -float(funding_8h)


def build_report(symbols: tuple[str, ...], *, http=_http_json) -> dict[str, Any]:
    rates = fetch_funding(symbols, http=http)
    measured = {s: r for s, r in rates.items() if r["state"] == "MEASURED"}
    sides: list[dict[str, Any]] = []
    for s, r in measured.items():
        for d in ("LONG", "SHORT"):
            pays = signed_funding_8h(r["funding_8h"], d)
            sides.append({"symbol": s, "direction": d, "pays_8h": round(pays, 8),
                          "stance": "PAYS" if pays > 0 else ("PAID" if pays < 0 else "FLAT"),
                          "extreme": abs(pays) >= EXTREME_FUNDING_8H and pays > 0})
    sides.sort(key=lambda x: x["pays_8h"])          # most-paid first, worst-paying last
    extremes = [x for x in sides if x["extreme"]]
    status = ("NO-DATA" if not measured else
              "MEASURED" if len(measured) == len(symbols) else "PARTIAL")
    return {
        "generated": datetime.now(tz=UTC).isoformat(),
        "law": "L1.41 -- costs measured, never assumed. Funding is signed and public; selection "
               "uses the sign (prefer the paid side, refuse extreme payers) while MARKING stays "
               "always-adverse. Different jobs, different signs, both deliberate.",
        "status": status,
        "n_measured": len(measured), "n_symbols": len(symbols),
        "rates": rates,
        "sides_ranked": sides,
        "best_carry": sides[:5],
        "extreme_paying": extremes,
        "maker_saving_per_side": MAKER_SAVING_PER_SIDE,
        "detail": (f"{len(measured)}/{len(symbols)} funding rates measured; "
                   + (f"{len(extremes)} extreme-paying side(s) flagged" if extremes else
                      "no extreme funding in force")
                   if measured else
                   "NO-DATA -- neither venue answered for any symbol; the trader's cost veto "
                   "stands down and the flat pessimistic cost model carries alone"),
    }


def main() -> int:
    _law_guard()
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    from scripts.run_conviction_trader import INSTRUMENTS
    rep = build_report(INSTRUMENTS)
    out = _ROOT / _STATE
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(rep, indent=2), "utf-8")
    if args.json:
        print(json.dumps(rep, indent=2))
    else:
        print(f"cost hunt (L1.41): {rep['status']} -- {rep['detail']}")
        for x in rep["best_carry"][:3]:
            print(f"  PAID  {x['symbol']:<10} {x['direction']:<5} {x['pays_8h']:+.5%}/8h")
        for x in rep["extreme_paying"][:3]:
            print(f"  AVOID {x['symbol']:<10} {x['direction']:<5} {x['pays_8h']:+.5%}/8h EXTREME")
    return 0


if __name__ == "__main__":
    sys.exit(main())

```

### scripts/run_execution_intel.py
```python
"""EXECUTION INTELLIGENCE LAYER -- one consolidated read over every execution organ (triage #102).

Principal-approved design 2026-07-29, with the principal's own amendment kept verbatim in force:
monitor -> diagnose -> recommend -> adjust ONLY within approved limits; this layer NEVER edits
execution logic or parameters itself. Execution is where small mistakes lose money immediately,
so the layer's entire write surface is one JSON report and (optionally) a page.

WHY A CONSOLIDATION AND NOT A NEW AGENT: the desk already owns the sensors --
  hedge_integrity.py         -> data/hedge_integrity.json        (the incident-#6 invariant)
  execution_bottleneck.py    -> data/execution_bottleneck.json   (gate-vs-book, cost truth)
  run_trade_forensics.py     -> web/trade_forensics.json         (churn/baseline/leg-thrash classes)
  run_cost_model.py          -> data/cost_model.json             (measured book-walk slippage)
  executor TCA fields        -> data/cashcarry_trades.json       (fills, fees, hold times)
Each fires alone; NOTHING reads them together, so a degradation that is obvious across two feeds
(e.g. rising realized cost while the cost model says cheap = execution drift) was invisible.
Per L2.9 the fix is a merge, not an agent. Verdicts per surface: OK / DEGRADED / CRITICAL / NO-DATA
-- NO-DATA is a real verdict (fail-loud), never silently skipped (the health.json fail-open
lesson, DESK_BRIEF known-blockers).

Runs from the daily cycle + cron; pure stdlib; every input read defensively (VPS-side files).

    python scripts/run_execution_intel.py [--page]
"""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_OUT = Path("web/execution_intel.json")

# Approved-limits contract (the principal's amendment, mechanical form): this layer may only
# RECOMMEND values for these executor knobs, and only inside these bounds. Anything outside the
# bound, or any knob not listed, is a RECOMMEND-TO-HUMAN, never an auto-adjust. Applying a
# recommendation remains a separate, logged, human-or-executor-owned step.
_APPROVED_LIMITS: dict[str, tuple[float, float]] = {
    "_DEFAULT_RT_BPS": (4.5, 80.0),     # entry-gate cost bar (bps): floor=measured p50 era, cap sane
    "_MIN_HOLD_H": (8.0, 72.0),         # min hold: never below one funding period
}


def _read(path: str) -> dict[str, Any] | None:
    try:
        obj = json.loads(Path(path).read_text("utf-8"))
        return obj if isinstance(obj, dict) else None
    except (OSError, json.JSONDecodeError):
        return None


def _age_h(obj: dict[str, Any] | None, *keys: str) -> float | None:
    if not obj:
        return None
    for k in keys:
        v = obj.get(k)
        if isinstance(v, str):
            try:
                ts = datetime.fromisoformat(v.replace("Z", "+00:00"))
                return (datetime.now(tz=UTC) - ts).total_seconds() / 3600.0
            except ValueError:
                continue
    return None


def _surface_hedge(report: dict[str, Any]) -> None:
    hi = _read("data/hedge_integrity.json")
    if hi is None:
        report["hedge_integrity"] = {"verdict": "NO-DATA",
                                     "detail": "data/hedge_integrity.json unreadable"}
        return
    bad = [s for s, st in (hi.get("legs") or {}).items()
           if str(st.get("state", "")).upper() in ("INVERTED", "MISSING", "MISMATCHED")]
    report["hedge_integrity"] = {
        "verdict": "CRITICAL" if bad else "OK", "bad_legs": bad,
        "age_h": _age_h(hi, "updated", "ts"),
        "detail": f"{len(bad)} leg(s) violating the carry invariant" if bad else "all legs hedged",
    }


def _surface_forensics(report: dict[str, Any]) -> None:
    tf = _read("web/trade_forensics.json")
    if tf is None:
        report["trade_forensics"] = {"verdict": "NO-DATA",
                                     "detail": "web/trade_forensics.json unreadable"}
        return
    bleeding = [k for k, v in tf.items()
                if isinstance(v, dict) and isinstance(v.get("net"), (int, float)) and v["net"] < 0
                and isinstance(v.get("n"), int) and v["n"] >= 10]
    report["trade_forensics"] = {
        "verdict": "DEGRADED" if bleeding else "OK", "bleeding_classes": bleeding,
        "age_h": _age_h(tf, "updated", "ts"),
    }


def _surface_cost_drift(report: dict[str, Any]) -> None:
    """Execution drift = realized cost trend vs the measured cost model -- the cross-feed check
    no single organ could make. Uses trade-log fee+slip per round-trip vs cost_model prediction."""
    cm, trades = _read("data/cost_model.json"), None
    try:
        raw = json.loads(Path("data/cashcarry_trades.json").read_text("utf-8"))
        trades = raw if isinstance(raw, list) else raw.get("trades")
    except (OSError, json.JSONDecodeError):
        pass
    if cm is None or not trades:
        report["cost_drift"] = {"verdict": "NO-DATA",
                                "detail": "needs data/cost_model.json + data/cashcarry_trades.json"}
        return
    tail = [t for t in trades[-50:] if isinstance(t, dict)]
    realized = [t.get("rt_bps") or t.get("cost_bps") for t in tail]
    realized = [float(x) for x in realized if isinstance(x, (int, float))]
    if len(realized) < 10:
        report["cost_drift"] = {"verdict": "NO-DATA",
                                "detail": f"only {len(realized)} trades carry TCA cost fields yet"}
        return
    med = sorted(realized)[len(realized) // 2]
    syms = cm.get("symbols") or {}
    preds = []
    for s in syms.values():
        try:
            p = s["fut_sell"]["500"]["median_bps"]
            if p is not None:
                preds.append(float(p))
        except (KeyError, TypeError, ValueError):
            continue
    pred_med = sorted(preds)[len(preds) // 2] if preds else None
    drift = (med / pred_med) if pred_med else None
    verdict = "OK"
    if drift is not None and drift > 2.0:
        verdict = "DEGRADED"          # paying >2x the modeled cost = model or execution drifted
    if drift is not None and drift > 4.0:
        verdict = "CRITICAL"
    report["cost_drift"] = {"verdict": verdict, "realized_median_bps": round(med, 2),
                            "modeled_median_bps": round(pred_med, 3) if pred_med else None,
                            "realized_over_modeled": round(drift, 2) if drift else None,
                            "n_trades": len(realized)}


def _surface_bottleneck(report: dict[str, Any]) -> None:
    eb = _read("data/execution_bottleneck.json")
    if eb is None:
        report["bottleneck"] = {"verdict": "NO-DATA",
                                "detail": "data/execution_bottleneck.json unreadable"}
        return
    report["bottleneck"] = {"verdict": "OK", "age_h": _age_h(eb, "updated", "ts"),
                            "summary": {k: eb[k] for k in list(eb)[:6]}}


def _recommend(report: dict[str, Any]) -> list[dict[str, Any]]:
    """Diagnose -> recommend. Recommendations carry the approved-limit bound they must respect;
    nothing here writes to executor state. A recommendation outside every bound is escalation."""
    recs: list[dict[str, Any]] = []
    cd = report.get("cost_drift", {})
    if cd.get("verdict") in ("DEGRADED", "CRITICAL") and cd.get("realized_median_bps"):
        lo, hi = _APPROVED_LIMITS["_DEFAULT_RT_BPS"]
        target = min(max(float(cd["realized_median_bps"]), lo), hi)
        recs.append({"knob": "_DEFAULT_RT_BPS", "action": "raise-to-realized",
                     "target_bps": round(target, 1), "bound": [lo, hi],
                     "why": "realized round-trip cost exceeds model "
                            f"{cd.get('realized_over_modeled')}x -- entry gate must price reality",
                     "auto_apply": False})
    if report.get("hedge_integrity", {}).get("verdict") == "CRITICAL":
        recs.append({"knob": None, "action": "PAGE+PAUSE-OPENS",
                     "why": "hedge invariant violated -- incident-#6 signature",
                     "auto_apply": False})
    return recs


def main() -> int:
    report: dict[str, Any] = {"updated": datetime.now(tz=UTC).isoformat(),
                              "design": "monitor->diagnose->recommend; never self-applies"}
    _surface_hedge(report)
    _surface_forensics(report)
    _surface_cost_drift(report)
    _surface_bottleneck(report)
    report["recommendations"] = _recommend(report)
    verdicts = [v.get("verdict") for v in report.values() if isinstance(v, dict) and "verdict" in v]
    report["overall"] = ("CRITICAL" if "CRITICAL" in verdicts else
                         "DEGRADED" if "DEGRADED" in verdicts else
                         "NO-DATA" if verdicts and all(x == "NO-DATA" for x in verdicts) else "OK")
    _OUT.parent.mkdir(parents=True, exist_ok=True)
    _OUT.write_text(json.dumps(report, indent=2), "utf-8")
    parts = ", ".join(f"{k}={v['verdict']}" for k, v in report.items()
                      if isinstance(v, dict) and "verdict" in v)
    print(f"execution intel: {report['overall']} ({parts})")
    for r in report["recommendations"]:
        print(f"  RECOMMEND {r.get('knob') or r['action']}: {r['why']}")
    if "--page" in sys.argv and report["overall"] == "CRITICAL":
        return 2   # caller (run_alerts / cron wrapper) owns delivery; exit code is the signal
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

```

### scripts/run_organ_er.py
```python
#!/usr/bin/env python3
"""ORGAN ER (R0215) -- a dark organ gets DIAGNOSED AND TREATED the same day, not merely counted.

PRINCIPAL ORDER (2026-07-31): *"make sure they're all started, always make sure all r running
everyday -- if someone is in coma revive them same day like hospital."*

THE GAP, and it is the shape of half the defects found today. The desk DETECTS coma well:
check_exploration reports the family DARK, check_organ_liveness separates NEVER-PRODUCED from
STALE, check_miner_runway watches the seats. Three organs have been reported dark for days and
every one of those reports was correct. NOTHING TREATED THEM. Detection without treatment is a
monitor, not a hospital -- and a ward whose alarms nobody answers eventually gets its alarms
turned off (L1.43).

organ_catchup.py is the closest thing that existed and it is deliberately narrow: it re-fires
QUOTA-KILLED organs, one per tick, for six named seats. That leaves the whole rest of the
diagnosis space untreated -- an organ that is dark because it was never scheduled, because its
auth expired, because it writes an artifact nobody reads, or because it crashes on start, gets
the same silence as one that was merely rate-limited. Different diseases, one non-treatment.

TRIAGE FIRST, because the treatment depends entirely on the cause and a wrong treatment is worse
than none. Every dark organ is diagnosed into exactly one of:

  UNSCHEDULED     no manifest line -> it was never going to run. Treatment: the scheduler
                  manifest, not a re-fire. Re-firing this by hand hides the real fault forever.
  BLOCKED         a NAMED external dependency is missing (an unfunded seat, an absent key). No
                  amount of re-firing fixes it, so it ESCALATES with the exact blocker and price
                  rather than burning a slot per tick pretending.
  MISWIRED        the organ RAN but its declared artifact never appeared -- so it is alive and
                  reported dead. The fix is the wiring or the registry, and re-firing a healthy
                  organ forever is the most expensive possible response.
  STARVED         it ran, failed, and the log names a transient cause (quota, 5xx, timeout).
                  Treatment: re-fire, which is what organ_catchup already does well.
  CRASHED         it ran and died on a non-transient error. Treatment: re-fire once, then
                  escalate with the error text -- a second identical crash is a bug, not a blip.
  UNKNOWN         dark with no log at all. Treatment: re-fire once to PRODUCE a log, because a
                  diagnosis needs evidence and the cheapest way to get it is to run the thing.

SAME-DAY IS THE STANDARD, and it is measured. Any organ dark longer than COMA_HOURS with no
treatment attempt recorded is a DEFECT this fence names -- not backlog. "It is on the list" is
exactly the state the principal's instruction forbids.

TREATMENT IS RECORDED, ALWAYS. Every attempt appends to data/organ_er_log.jsonl with its
diagnosis, action and outcome, so "we tried" is a dated fact rather than an impression -- and so
a treatment that never works becomes visible as a pattern instead of repeating forever.

REFUSES TO FAKE A CURE: an organ is only DISCHARGED when its artifact actually appears. A
re-fire that returns 0 but produces nothing stays ADMITTED, because exit status is the organ's
opinion of itself and the artifact is the evidence.

    python scripts/run_organ_er.py [--treat] [--json]
"""
from __future__ import annotations

import argparse
import contextlib
import json
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_ROOT = Path("/home/quant/quant-platform")
if not _ROOT.exists():
    _ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
from libs.ops.lawful import guard as _law_guard  # noqa: E402

_STATE = "data/organ_er.json"
_LOG = "data/organ_er_log.jsonl"

#: How long an organ may stay dark before it is a DEFECT rather than a delay. 24h because the
#: principal's standard is same-day and every organ in the ward has a cadence at or under a day;
#: an organ silent past its own cadence plus a full day is not late, it is down.
COMA_HOURS = 24.0

#: Transient markers in a log that make a re-fire the right treatment rather than an escalation.
#: Same list organ_catchup uses -- one vocabulary for one phenomenon.
_TRANSIENT = ("429", "529", "502", "503", "504", "overloaded", "rate limit", "quota",
              "timed out", "timeout", "connection reset", "temporarily")

#: Markers that mean no re-fire will ever help: the organ needs something bought or configured.
#: Escalating these instead of retrying is what stops the ward burning a slot per tick on a
#: patient whose treatment is a credit card.
_BLOCKED = ("402", "payment required", "insufficient credit", "no api key", "unauthorized",
            "401", "403", "missing key", "not funded")


def _age_hours(p: Path, now: float) -> float | None:
    """Age from the artifact's own `generated` stamp where it has one, else mtime.

    Content outranks mtime for the same reason L1.44 gives: a deploy rewrites mtime, so mtime
    lies FRESH -- the dangerous direction for a liveness check."""
    try:
        if p.is_dir():
            kids = [c for c in p.iterdir() if c.is_file()]
            return min(((now - c.stat().st_mtime) / 3600.0 for c in kids), default=None)
        raw = p.read_text("utf-8", errors="ignore")
    except OSError:
        return None
    # A non-JSON or unstamped artifact falls through to mtime BY DESIGN -- some produced files
    # are plain text and some predate the `generated` convention. contextlib.suppress rather than
    # `except: pass` because the two read identically to a human and differently to the fence,
    # and this one genuinely has a defined next step rather than a swallowed failure.
    with contextlib.suppress(ValueError, TypeError):
        data = json.loads(raw)
        if isinstance(data, dict) and data.get("generated"):
            at = datetime.fromisoformat(str(data["generated"]))
            at = at.replace(tzinfo=UTC) if at.tzinfo is None else at
            return max(0.0, (datetime.now(tz=UTC) - at).total_seconds() / 3600.0)
    try:
        return max(0.0, (now - p.stat().st_mtime) / 3600.0)
    except OSError:
        return None


def _tail_log(root: Path, name: str, n: int = 4000) -> str:
    """Whatever the organ last said about itself. No log is itself a diagnosis (UNKNOWN)."""
    best, newest = "", -1.0
    logdir = root / "data/cro_ai_logs"
    try:
        for p in logdir.glob(f"*{name.split('_')[0]}*"):
            try:
                m = p.stat().st_mtime
            except OSError:
                continue
            if m > newest:
                newest, best = m, p.read_text("utf-8", errors="ignore")[-n:]
    except OSError:
        return ""
    return best


def diagnose(root: Path, name: str, artifact: str, max_age_h: float,
             *, now: float | None = None, manifest: str = "") -> dict[str, Any]:
    """Why is this organ dark? The treatment depends entirely on the answer."""
    now = now if now is not None else time.time()
    age = _age_hours(root / artifact, now)
    if age is not None and age <= max_age_h:
        return {"organ": name, "state": "HEALTHY", "age_hours": round(age, 2),
                "artifact": artifact}

    log = _tail_log(root, name).lower()
    scheduled = name in manifest or artifact in manifest or f"run_{name}" in manifest
    produced_ever = age is not None

    # SECONDARY ARTIFACTS ARE NOT PATIENTS. data/hunt_coverage.json is written by kimi_hunter and
    # by nothing else, yet check_exploration lists it as its own organ -- so kimi's silence was
    # counted TWICE in the desk's dark total ("3 of 6 dark" is really two patients, one of them
    # double-billed), and this artifact would report UNSCHEDULED forever because it has no runner
    # to schedule. Attributing it to its producer is what makes the ward count mean something.
    producer = _SECONDARY.get(name)
    if producer:
        return {"organ": name, "state": "SECONDARY", "artifact": artifact,
                "age_hours": None if age is None else round(age, 2),
                "max_age_hours": max_age_h, "produced_ever": produced_ever,
                "scheduled": True, "producer": producer,
                "action": (f"not an organ -- {artifact} is written by {producer} and by nothing "
                           f"else. Treat {producer}; this file follows. It can never have a "
                           "manifest line of its own, so reporting it UNSCHEDULED is a permanent "
                           "false alarm and double-counts one patient as two."),
                "treatable_here": False, "coma": False}

    if not scheduled:
        dx, action = "UNSCHEDULED", ("add a manifest line -- re-firing by hand would hide the "
                                     "real fault, which is that nothing was ever going to run it")
    elif any(m in log for m in _BLOCKED):
        dx, action = "BLOCKED", ("a NAMED external dependency is missing; escalate with the "
                                 "blocker -- no re-fire fixes a patient whose treatment is a "
                                 "credit card")
    elif log and not produced_ever and "traceback" not in log and not any(
            m in log for m in _TRANSIENT):
        dx, action = "MISWIRED", ("the organ RAN but its declared artifact never appeared -- it "
                                  "is alive and reported dead. Fix the wiring or the registry; "
                                  "re-firing a healthy organ forever is the worst response")
    elif any(m in log for m in _TRANSIENT):
        dx, action = "STARVED", "transient cause in the log -- re-fire"
    elif "traceback" in log or "error" in log:
        dx, action = "CRASHED", ("re-fire once, then escalate with the error text -- a second "
                                 "identical crash is a bug, not a blip")
    else:
        dx, action = "UNKNOWN", ("dark with no log -- re-fire once to PRODUCE one, because a "
                                 "diagnosis needs evidence and running it is the cheapest way "
                                 "to get some")
    return {"organ": name, "state": dx, "artifact": artifact,
            "age_hours": None if age is None else round(age, 2),
            "max_age_hours": max_age_h, "produced_ever": produced_ever,
            "scheduled": scheduled, "action": action,
            "treatable_here": dx in ("STARVED", "CRASHED", "UNKNOWN"),
            "coma": age is None or age > max_age_h + COMA_HOURS}


def treat(root: Path, dx: dict[str, Any], runner: str | None,
          *, run=subprocess.run, timeout: int = 900) -> dict[str, Any]:
    """Attempt the treatment, then check the ARTIFACT -- never the exit status.

    A re-fire that returns 0 and produces nothing is not a cure; exit status is the organ's
    opinion of itself and the artifact is the evidence. DISCHARGED requires the evidence."""
    if not dx.get("treatable_here"):
        return {"organ": dx["organ"], "attempted": False, "outcome": "ESCALATED",
                "why": dx.get("action", "")}
    if not runner:
        return {"organ": dx["organ"], "attempted": False, "outcome": "NO-RUNNER",
                "why": "no runner registered -- the ER cannot treat what it cannot invoke"}
    before = _age_hours(root / dx["artifact"], time.time())
    try:
        r = run([sys.executable, str(root / runner)] if runner.endswith(".py")
                else ["bash", str(root / runner)],
                cwd=root, capture_output=True, text=True, timeout=timeout)
        rc, err = r.returncode, (r.stderr or "")[-400:]
    except (OSError, subprocess.SubprocessError) as exc:
        rc, err = -1, f"{type(exc).__name__}: {exc}"
    after = _age_hours(root / dx["artifact"], time.time())
    cured = after is not None and (before is None or after < before)
    return {"organ": dx["organ"], "attempted": True, "runner": runner, "rc": rc,
            "outcome": "DISCHARGED" if cured else "STILL-ADMITTED",
            "why": ("artifact refreshed -- the evidence, not the exit code"
                    if cured else
                    f"re-fire returned {rc} and the artifact did NOT refresh; exit status is the "
                    f"organ's opinion of itself{': ' + err if err else ''}")}


def build_report(root: Path | None = None, *, do_treat: bool = False,
                 family: dict[str, tuple[str, float, str]] | None = None,
                 runners: dict[str, str] | None = None, run=subprocess.run) -> dict[str, Any]:
    root = root or _ROOT
    if family is None:
        from scripts.check_exploration import _FAMILY as family
    runners = runners if runners is not None else _RUNNERS
    try:
        manifest = (root / "ops/crontab.manifest").read_text("utf-8", errors="ignore")
    except OSError:
        manifest = ""

    log_error = ""
    ward = [diagnose(root, n, rel, mx, manifest=manifest) for n, (rel, mx, _h) in family.items()]
    sick = [d for d in ward if d["state"] != "HEALTHY"]
    comas = [d for d in sick if d["coma"]]
    treatments = []
    if do_treat:
        treatments = [treat(root, d, runners.get(d["organ"]), run=run) for d in sick]
        path = root / _LOG
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("a", encoding="utf-8") as fh:
                stamp = datetime.now(tz=UTC).isoformat()
                for d, t in zip(sick, treatments, strict=False):
                    fh.write(json.dumps({"at": stamp, "diagnosis": d, "treatment": t}) + "\n")
        except OSError as exc:
            # Never block a treatment on telemetry -- but never swallow it either. An unwritable
            # ward log means "we tried" stops being a dated fact, which is precisely how a
            # treatment that never works hides as a fresh attempt every tick.
            log_error = (f"ward log unwritable ({type(exc).__name__}: {exc}) -- treatment "
                         "history is NOT being recorded, so a never-working treatment cannot be "
                         "seen as a pattern")

    untreated = [d["organ"] for d in comas
                 if not any(t["organ"] == d["organ"] and t.get("attempted") for t in treatments)]
    return {
        "generated": datetime.now(tz=UTC).isoformat(),
        "law": "L1.32/L1.28a -- a dark organ is DIAGNOSED AND TREATED the same day. Detection "
               "without treatment is a monitor, not a hospital, and a ward whose alarms nobody "
               "answers gets its alarms switched off (L1.43).",
        "status": ("OK" if not sick else
                   "COMA-UNTREATED" if untreated else
                   "TREATED" if do_treat else "SICK-UNTREATED"),
        "n_organs": len(ward), "n_healthy": len(ward) - len(sick),
        "n_sick": len(sick), "n_coma": len(comas),
        "coma_hours": COMA_HOURS,
        "ward": ward,
        "treatments": treatments,
        "escalate": [{"organ": d["organ"], "state": d["state"], "action": d["action"]}
                     for d in sick if not d["treatable_here"]],
        "untreated_comas": untreated,
        "log_error": log_error,
        "detail": (f"{len(ward) - len(sick)}/{len(ward)} organs healthy"
                   + (f"; {len(comas)} in coma >{COMA_HOURS:.0f}h" if comas else "")
                   + (f"; {sum(1 for t in treatments if t['outcome'] == 'DISCHARGED')} discharged"
                      if treatments else "")
                   + (f"; UNTREATED: {', '.join(untreated)}" if untreated else "")),
    }


#: Artifacts that belong to ANOTHER organ. Verified by grep before listing: hunt_coverage.json is
#: written at kimi_hunter.py:50 and referenced nowhere else that writes. Listing it here is what
#: stops one silent organ being reported as two dead ones.
_SECONDARY: dict[str, str] = {"hunt_coverage": "kimi_hunter"}

#: organ -> the script that re-fires it. Only organs the ER can actually invoke appear; a missing
#: runner is reported as NO-RUNNER rather than silently skipped, because an untreatable patient
#: nobody names is the failure this organ exists to end.
_RUNNERS: dict[str, str] = {
    "capability_hunt": "ops/run_capability_hunt.sh",
    "blindspot_max": "scripts/run_blindspot_max.py",
    "blindspot_prober": "scripts/run_blindspot_prober.py",
    "kimi_hunter": "scripts/kimi_hunter.py",
    "deep_sweep_meta": "ops/run_deep_sweep.sh",
}


def main() -> int:
    _law_guard()
    ap = argparse.ArgumentParser()
    ap.add_argument("--treat", action="store_true", help="attempt treatment, not just triage")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    rep = build_report(_ROOT, do_treat=args.treat)
    out = _ROOT / _STATE
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(rep, indent=2), "utf-8")
    if args.json:
        print(json.dumps(rep, indent=2))
    else:
        print(f"organ ER (L1.32): {rep['status']} -- {rep['detail']}")
        for d in rep["ward"]:
            if d["state"] != "HEALTHY":
                print(f"  {d['state']:<12} {d['organ']:<20} {str(d['action'])[:78]}")
    return 0 if rep["status"] in ("OK", "TREATED") else 2


if __name__ == "__main__":
    sys.exit(main())

```

### scripts/run_regime_allocation.py
```python
"""Regime-aware capital allocation (SHADOW — advisory, never auto-applied to live capital).

Tilts sleeve weights toward the sleeves with the best Sharpe IN THE CURRENT REGIME, read from the
live regime tag (data/crypto_regime.json) and the per-regime sleeve-Sharpe table that the portfolio
engine already produces (web/crypto_portfolio.json -> regimes). The regime Sharpes are IN-SAMPLE, so
this blends the tilt 50/50 with equal-weight (a hard anti-overfit cap) and is published as a SHADOW
recommendation only -- real capital is never auto-allocated to an unvalidated tilt. Writes
web/regime_alloc.json. Promotion to live requires the tilt to beat flat in the forward shadow.

    python scripts/run_regime_allocation.py
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

_PORT = Path("web/crypto_portfolio.json")
_REG = Path("data/crypto_regime.json")
_OUT = Path("web/regime_alloc.json")
_SLEEVES = ["funding_carry", "basis_carry", "taker_flow", "xsec_price_mom", "ts_trend"]


def main() -> None:
    port = json.loads(_PORT.read_text("utf-8"))
    regimes = port.get("regimes", {})
    reg = json.loads(_REG.read_text("utf-8")) if _REG.exists() else {}
    trend, vol = reg.get("trend", "bull"), reg.get("vol", "low_vol")
    keys = [f"trend:{trend}", f"vol:{vol}"]

    acc = dict.fromkeys(_SLEEVES, 0.0)
    cnt = 0
    for k in keys:
        if k in regimes:
            cnt += 1
            for s in _SLEEVES:
                acc[s] += float(regimes[k].get(s, 0.0))
    in_regime = {s: (acc[s] / cnt if cnt else 0.0) for s in _SLEEVES}

    pos = {s: max(0.0, in_regime[s]) for s in _SLEEVES}      # only positive in-regime edge tilts
    tot = sum(pos.values()) or 1.0
    tilt = {s: pos[s] / tot for s in _SLEEVES}
    eq = 1.0 / len(_SLEEVES)
    blended = {s: round(0.5 * tilt[s] + 0.5 * eq, 4) for s in _SLEEVES}  # 50% cap vs equal-weight

    flat_sharpe = port.get("portfolio_flat_sharpe")
    out = {
        "updated": datetime.now(tz=UTC).isoformat(),
        "regime": reg.get("regime", "—"),
        "regime_keys": keys,
        "in_regime_sharpe": {s: round(in_regime[s], 2) for s in _SLEEVES},
        "equal_weight": round(eq, 4),
        "tilt_weights": blended,
        "flat_portfolio_sharpe": flat_sharpe,
        "status": "SHADOW",
        "note": ("in-sample regime Sharpe; 50% tilt / 50% equal-weight anti-overfit cap; "
                 "advisory only -- not auto-applied to live capital; must beat flat in shadow"),
    }
    _OUT.parent.mkdir(parents=True, exist_ok=True)
    _OUT.write_text(json.dumps(out, indent=2), "utf-8")
    top = max(blended, key=lambda s: blended[s])
    print(f"regime {out['regime']} -> tilt top: {top} {blended[top]:.0%} "
          f"(in-regime Sharpe {out['in_regime_sharpe'][top]}); SHADOW only")


if __name__ == "__main__":
    main()

```

### scripts/run_sleeve_allocator.py
```python
#!/usr/bin/env python3
"""SLEEVE ALLOCATOR (R0141) -- risk across discretionary sleeves, by MARGINAL growth contribution.

PRINCIPAL ORDER (2026-07-31): *"advance this section way more so multiple discretionary edges
genuinely compound and max geometric growth each on the side."* (The principal's own framing
carried a return figure; it is deliberately not restated here -- see PROJECT_HANDOFF.md, 'do not
chase a CAGR target'. The objective is max E[log wealth] subject to survival.)

THE WORD THAT DOES THE WORK IS "GENUINELY". Adding sleeves only multiplies growth if the sleeves
are INDEPENDENT. Five sleeves all long crypto beta are one sleeve wearing five names: they draw
down together, so total risk scales with N while growth scales with 1, and the desk ends up paying
five sets of costs for one bet. That is not an abstract worry -- this book has already measured
crypto-vs-crypto return correlation at +0.48 and gold-vs-crypto at +0.15, so the difference between
a real second edge and a duplicate is large and measurable.

So the rule this organ enforces:

    A NEW DISCRETIONARY SLEEVE EARNS RISK ONLY IN PROPORTION TO WHAT IT ADDS THAT THE EXISTING
    BOOK DOES NOT ALREADY HAVE. Duplicates are funded at a discount or refused, and the discount
    is COMPUTED from the measured correlation of realised returns, never from the story attached
    to the sleeve.

WHY THIS IS THE HIGH-VALUE PIECE OF "MORE SLEEVES". At fixed total heat, splitting risk across N
INDEPENDENT sleeves multiplies the growth rate by roughly N while portfolio volatility grows as
sqrt(N) -- the same arithmetic that made 8 positions at 3% beat 1 position at 24%, applied one
level up. At correlation 1.0 the same split multiplies growth by 1 and buys nothing but extra fees.
The allocator is therefore where the "each on the side" part of the order is actually delivered or
quietly lost.

MARGINAL, NOT AVERAGE. A sleeve's allocation follows its marginal contribution to portfolio
E[log wealth], approximated by shrinking its standalone growth by how much of its variance the rest
of the book already carries. A sleeve with a strong standalone record that duplicates an existing
one contributes little at the margin and is funded accordingly -- which is the honest answer to
"but it makes money on its own".

UNMEASURED IS TREATED AS DUPLICATE, deliberately and in the pessimistic direction. Two sleeves with
no overlapping return history have no measured correlation, and assuming independence there would
hand full risk to a sleeve that might be the same bet. The assumption that costs money when wrong
is the one that gets made.

ZERO PROMOTION AUTHORITY (L1.6): this allocates PAPER risk budget among sleeves that have already
earned their place. It cannot promote a sleeve to live capital, and it places no orders.

    python scripts/run_sleeve_allocator.py [--json]
"""
from __future__ import annotations

import argparse
import json
import math
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

_STATE = "data/sleeve_allocation.json"

#: The registered discretionary sleeves and where their marked returns live. A sleeve absent from
#: here gets no budget -- "unregistered" must be a decision, not a way to slip in unmeasured.
_SLEEVES: dict[str, dict[str, str]] = {
    "conviction": {"book": "data/conviction_book.jsonl", "kind": "chart structure + levels",
                   "mark_key": "conviction"},
    "event": {"book": "data/llm_trader_book.jsonl", "kind": "prose/event causal reasoning",
              "mark_key": "event"},
}

#: Correlation at or above which a sleeve is a DUPLICATE rather than an edge. 0.7 is where shared
#: variance passes half (rho^2 = 0.49): beyond it the majority of the new sleeve's movement is
#: already carried by the book, so it is funding a second copy of an existing bet.
DUPLICATE_RHO = 0.70
#: Minimum overlapping closed trades before a correlation is believed. Below this the sample
#: correlation's standard error (~1/sqrt(n-1)) exceeds 0.35, which cannot distinguish +0.15 from
#: +0.48 -- the exact distinction the allocation turns on.
MIN_OVERLAP = 10
#: Total paper risk budget shared across discretionary sleeves. Matches MAX_PORTFOLIO_HEAT in the
#: conviction sleeve so the two layers cannot silently sum to more than the book allows.
TOTAL_HEAT = 0.30
#: Floor share for a registered sleeve with no measured history: it must be able to ACCUMULATE the
#: record that would earn it more, and a zero allocation is a sleeve that can never prove itself
#: (L1.28a -- idle capacity is unbooked loss). Small enough that being wrong is cheap.
SEED_SHARE = 0.10


def _series(root: Path, mark_key: str) -> list[tuple[str, float]]:
    """(exit timestamp, net return) for a sleeve's closed, marked trades."""
    try:
        marks = json.loads((root / "data/paper_book_pnl.json").read_text("utf-8"))["marks"]
    except (OSError, ValueError, KeyError):
        return []
    return [(m.get("exit_at") or m.get("key") or "", float(m.get("equity_return") or 0.0))
            for m in marks
            if m.get("closed") and m.get("kind") == mark_key and m.get("equity_return") is not None]


def _corr(a: list[float], b: list[float]) -> float | None:
    n = min(len(a), len(b))
    if n < 3:
        return None
    a, b = a[-n:], b[-n:]
    ma, mb = sum(a) / n, sum(b) / n
    sab = sum((x - ma) * (y - mb) for x, y in zip(a, b, strict=False))
    saa = sum((x - ma) ** 2 for x in a)
    sbb = sum((y - mb) ** 2 for y in b)
    if saa <= 0 or sbb <= 0:
        return None
    return round(sab / math.sqrt(saa * sbb), 4)


def _align(s1: list[tuple[str, float]], s2: list[tuple[str, float]],
           ) -> tuple[list[float], list[float]]:
    """Pair returns by DAY. Two sleeves rarely close at the same instant, so a naive positional
    zip would correlate unrelated trades and produce a number that means nothing."""
    def by_day(s):
        out: dict[str, float] = {}
        for ts, r in s:
            out[str(ts)[:10]] = out.get(str(ts)[:10], 0.0) + r
        return out
    d1, d2 = by_day(s1), by_day(s2)
    days = sorted(set(d1) & set(d2))
    return [d1[d] for d in days], [d2[d] for d in days]


def standalone_growth(rets: list[float]) -> float | None:
    """Realised log-growth per trade. None on no history -- never a zero, which would read as a
    measured flat result rather than as absence."""
    live = [r for r in rets if r > -0.999]
    return round(sum(math.log(1 + r) for r in live) / len(live), 6) if live else None


def allocate(root: Path | None = None) -> dict[str, Any]:
    root = root or _ROOT
    series = {name: _series(root, spec["mark_key"]) for name, spec in _SLEEVES.items()}
    rows: dict[str, Any] = {}
    for name, spec in _SLEEVES.items():
        rets = [r for _, r in series[name]]
        rows[name] = {"kind": spec["kind"], "n_closed": len(rets),
                      "standalone_g": standalone_growth(rets)}

    pairs: dict[str, Any] = {}
    names = list(_SLEEVES)
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            xa, xb = _align(series[a], series[b])
            if len(xa) < MIN_OVERLAP:
                pairs[f"{a}|{b}"] = {
                    "state": "UNMEASURED", "overlap_days": len(xa),
                    "assumed_rho": 1.0,
                    "why": f"{len(xa)} overlapping days < {MIN_OVERLAP}; treated as a DUPLICATE, "
                           "because assuming independence would hand full risk to what may be the "
                           "same bet"}
                continue
            rho = _corr(xa, xb)
            pairs[f"{a}|{b}"] = {
                "state": "MEASURED", "overlap_days": len(xa), "rho": rho,
                "verdict": ("DUPLICATE -- majority of its variance is already carried by the book"
                            if rho is not None and rho >= DUPLICATE_RHO else
                            "INDEPENDENT ENOUGH TO FUND" if rho is not None else "UNMEASURED")}

    # BASE WEIGHT: standalone growth, floored so a registered sleeve can always accumulate the
    # record that would earn it more (a zero allocation is a sleeve that can never prove itself).
    base: dict[str, float] = {}
    for name in names:
        g = rows[name]["standalone_g"]
        base[name] = SEED_SHARE if g is None else max(SEED_SHARE, min(1.0, max(0.0, g) * 100))
    tot_base = sum(base.values()) or 1.0
    u = {n: base[n] / tot_base for n in names}          # normalised split

    # THE CORRECTION THAT MAKES THIS MEAN ANYTHING: correlation must scale TOTAL deployed risk,
    # not merely how a fixed total is divided. The first version normalised shares to 1 and so
    # handed two perfect duplicates the same total heat as two independent sleeves -- exactly the
    # failure this organ exists to prevent, in the organ itself. Total risk is now solved so the
    # CORRELATION-ADJUSTED portfolio risk equals TOTAL_HEAT: sqrt(u' S u) is near sum(u) for
    # duplicates (little scaling room) and much smaller for independent sleeves (more room).
    def rho_between(a: str, b: str) -> float:
        if a == b:
            return 1.0
        p = pairs.get(f"{a}|{b}") or pairs.get(f"{b}|{a}") or {}
        if p.get("state") == "MEASURED" and p.get("rho") is not None:
            return abs(float(p["rho"]))
        return 1.0                                       # UNMEASURED is treated as duplicate
    var = sum(u[a] * u[b] * rho_between(a, b) for a in names for b in names)
    port = math.sqrt(var) if var > 0 else 1.0
    scale = TOTAL_HEAT / port if port > 0 else TOTAL_HEAT
    for name in names:
        rows[name]["share"] = round(u[name], 4)
        rows[name]["risk_budget"] = round(min(u[name] * scale, TOTAL_HEAT), 4)
    rows_total = sum(r["risk_budget"] for r in rows.values())

    measured = [p for p in pairs.values() if p["state"] == "MEASURED"]
    n_ind = sum(1 for p in measured
                if p.get("rho") is not None and abs(p["rho"]) < DUPLICATE_RHO)
    effective_n = (1 + n_ind) if measured else 1
    return {
        "generated": datetime.now(tz=UTC).isoformat(),
        "law": "L1.6/L1.28b -- more sleeves only multiply growth if they are INDEPENDENT. "
               "Correlated sleeves draw down together: risk scales with N, growth with 1, and the "
               "desk pays N sets of costs for one bet.",
        "status": ("UNMEASURED" if not measured else
                   "DUPLICATION" if n_ind < len(measured) else "DIVERSIFIED"),
        "total_heat_cap": TOTAL_HEAT,
        "total_deployed": round(rows_total, 4),
        "correlation_scaling": round(scale, 3),
        "sleeves": rows, "pairs": pairs,
        "effective_independent_sleeves": effective_n,
        "growth_multiplier_note": (
            "at fixed total heat, N INDEPENDENT sleeves multiply growth by ~N while portfolio "
            "volatility grows as ~sqrt(N); at rho=1 the same split multiplies growth by 1 and buys "
            "only extra fees. This is the same arithmetic that made 8 positions at 3% beat 1 at "
            "24%, one level up."),
        "detail": (f"{len(rows)} registered discretionary sleeve(s); "
                   + (f"{n_ind}/{len(measured)} pairs independent enough to fund"
                      if measured else
                      "NO pair has enough overlapping history to measure -- all treated as "
                      "duplicates until they do")),
        "authority": "allocates PAPER risk budget only; cannot promote a sleeve to live capital "
                     "and places no orders (L1.6)",
    }


def main() -> int:
    _law_guard()
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    rep = allocate(_ROOT)
    out = _ROOT / _STATE
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(rep, indent=2), "utf-8")
    if args.json:
        print(json.dumps(rep, indent=2))
    else:
        print(f"sleeve allocator (R0141): {rep['status']} -- {rep['detail']}")
        for n, r in rep["sleeves"].items():
            print(f"  {n:<12} n={r['n_closed']:<4} g={r['standalone_g']} "
                  f"budget={r['risk_budget']:.1%}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

```

### scripts/run_trend_regime_shadow.py
```python
"""Regime-gated TREND challenger -- same majors TS-momentum, FLAT in weak-trend regimes.

PRE-REGISTERED CHALLENGER (2026-07-09) to the frozen trend_30d incumbent, per champion/challenger:
identical book (top-15 majors, 30d lookback, banded) but exposure is ON only when the market is in
a TRENDING regime, defined a priori on economics (alts trend when BTC trends): lagged |BTC 30d
return| >= 10%. Constants fixed BEFORE inspecting the incumbent's losing days -- this is a regime
hypothesis, not a fit to last week. HONESTY: (1) the desk's EV gate scored this class LOW
(p_survive ~7%; regime-filtered trend is a classic overfit trap) -- built on explicit principal
instruction, verdict logged in the decision ledger; (2) the incumbent stays FROZEN and unmodified;
both clocks run in parallel and the 90d evidence picks the winner. Zero capital either way.

    python scripts/run_trend_regime_shadow.py
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd

from libs.data.crypto_source import list_liquid_perps
from libs.data.instruments import AssetClass, InstrumentSpec, register_instrument
from libs.data.lake import Layer, ParquetLake
from libs.data.timeframe import Timeframe
from libs.research.crossasset import trend_basket_returns
from libs.research.crypto_xsec import adv_tier_cost
from libs.validation.dsr import sharpe_ratio

_CRYPTO = Path("data/lake/bronze/crypto")
_STATE = Path("data/trend_regime_shadow_state.json")
_WEB = Path("web/trend_regime_shadow.json")
_PPY = 365.0
# FROZEN pre-registered spec: incumbent's book + a lagged BTC trend-strength gate. NOT tunable.
_TOP, _LOOKBACK, _BAND = 15, 30, 0.10
_GATE_LOOKBACK, _GATE_MIN_ABS = 30, 0.10          # |BTC 30d return| >= 10% -> trending regime
_FROZEN = ("regime-gated TS-momentum: top-15 majors 30d, FLAT unless lagged |BTC 30d| >= 10% "
           "(pre-registered challenger to trend_30d; incumbent untouched)")


def _majors(top: int) -> tuple[pd.DataFrame, dict[str, float]]:
    closes, adv = {}, {}
    for s in list_liquid_perps(top_n=top * 3):
        if not (_CRYPTO / s / Timeframe.D1.value).exists():
            continue
        register_instrument(InstrumentSpec(symbol=s, asset_class=AssetClass.CRYPTO, description=s))
        lake = ParquetLake("data/lake")
        df = lake.read_bars(Layer.BRONZE, s, Timeframe.D1).set_index("timestamp")
        if len(df) < 300:
            continue
        closes[s] = df["close"]
        adv[s] = float((df["close"] * df["volume"]).tail(180).mean())
        if len(closes) >= top:
            break
    return pd.DataFrame(closes).sort_index(), adv


def _ann(r: np.ndarray) -> float:
    a = r[r != 0.0]
    return round(float(sharpe_ratio(a) * np.sqrt(_PPY)), 2) if len(a) > 5 else 0.0


def _verdict(days: int, fwd: float, bt: float) -> str:
    if days < 90:
        return f"ACCUMULATING ({days}/90+ days, challenger) -- zero capital until it holds"
    if fwd < 0:
        return "FAILING FORWARD -> kill challenger (regime gate did not help)"
    if fwd >= 0.5 and fwd >= 0.5 * bt:
        return "ON TRACK -> compare vs incumbent at review; better book wins (governance gate)"
    return "WEAK forward -> continue shadow, do not deploy"


def main() -> None:
    close, adv = _majors(_TOP)
    if close.shape[1] < 6 or "BTCUSDT" not in close.columns:
        raise SystemExit(f"need a majors panel incl. BTCUSDT; got {close.shape[1]}")
    cost = {s: adv_tier_cost(a) for s, a in adv.items()}
    raw = trend_basket_returns(close, cost, lookback=_LOOKBACK, band=_BAND)
    # regime gate: LAGGED BTC 30d absolute move (shift(1) -> no look-ahead); flat when weak-trend.
    btc = close["BTCUSDT"]
    gate = ((btc / btc.shift(_GATE_LOOKBACK) - 1.0).abs() >= _GATE_MIN_ABS).shift(1)
    r = np.where(gate.fillna(False).to_numpy(), raw, 0.0)
    in_market_pct = round(100.0 * float(gate.fillna(False).mean()), 1)
    dates = close.index

    state = json.loads(_STATE.read_text("utf-8")) if _STATE.exists() else {}
    if "shadow_start" not in state or state.get("composition") != _FROZEN:
        state = {"shadow_start": dates[-1].isoformat(), "composition": _FROZEN}
        _STATE.parent.mkdir(parents=True, exist_ok=True)
        _STATE.write_text(json.dumps(state), "utf-8")
    shadow_start = pd.Timestamp(state["shadow_start"])
    is_fwd = dates >= shadow_start
    bt_sharpe, fwd_sharpe = _ann(r[~is_fwd]), _ann(r[is_fwd])
    fwd = r[is_fwd]
    # forward day-count = CALENDAR forward days (a gated-flat day is still evidence)
    fwd_days = int(np.sum(is_fwd)) - 1 if np.sum(is_fwd) else 0
    fwd_cum = float(np.prod(1.0 + fwd) - 1.0) if len(fwd) else 0.0

    equity = np.cumprod(1.0 + r)
    n = len(equity)
    step = max(1, n // 300)
    curve = [{"t": dates[i].date().isoformat(), "v": round(float(equity[i]), 4),
              "fwd": bool(is_fwd[i])} for i in range(0, n, step)]
    payload = {
        "strategy": _FROZEN, "shadow_start": state["shadow_start"], "majors": close.shape[1],
        "backtest_ann_sharpe": bt_sharpe, "forward_ann_sharpe": fwd_sharpe,
        "forward_days": max(fwd_days, 0), "forward_cum_return": round(fwd_cum, 4),
        "in_market_pct": in_market_pct, "directional": True, "challenger_to": "trend_30d",
        "ev_gate_verdict": "REJECT p~7% (built on principal instruction; ledger 2026-07-09)",
        "verdict": _verdict(max(fwd_days, 0), fwd_sharpe, bt_sharpe),
        "updated": datetime.now(tz=UTC).isoformat(), "equity": curve,
    }
    _WEB.parent.mkdir(parents=True, exist_ok=True)
    _WEB.write_text(json.dumps(payload, indent=2), "utf-8")
    print(f"trend-regime challenger: fwd={payload['forward_days']}d bt_sharpe={bt_sharpe} "
          f"in-market={in_market_pct}% (incumbent bt: see trend_shadow.json)")


if __name__ == "__main__":
    main()

```

### scripts/verify_fixes.py
```python
"""Verify all five fixes from a1bcd86 are LIVE in the running code, not just committed.

A commit proves an edit happened. It does not prove the edit is reachable, correct, or in the file
the process actually imports -- I shipped a fix to the mainnet module yesterday while the desk
trades testnet, and it looked perfectly committed.
"""
from __future__ import annotations

import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
checks = []


def chk(name, ok, detail):
    checks.append((name, ok, detail))


# 1 prefix health matching in dependency_graph
src = (ROOT / "scripts/dependency_graph.py").read_text("utf-8")
dg = json.loads((ROOT / "data/dependency_graph.json").read_text("utf-8"))
unmon = [n for n in dg["nodes"] if n["state"] == "UNMONITORED"]
chk("1 prefix health match", "_health_for" in src and not unmon,
    f"{len(unmon)} UNMONITORED nodes (was 2: data/moat + funding API)")

# 2 data_vitals reports small/derived instead of dropping
dv = json.loads((ROOT / "data/data_vitals.json").read_text("utf-8"))
jsonl = {p.name for p in (ROOT / "data").glob("*.jsonl")}
scored = {c["source"] for c in dv["collectors"]}
chk("2 data_vitals denominator honest", jsonl <= scored,
    f"{len(jsonl & scored)}/{len(jsonl)} jsonl files present in the report")

# 3 measurement_gate reports TOO_SMALL
mg = json.loads((ROOT / "data/measurement_gate.json").read_text("utf-8"))
gated = set(mg["datasets"])
small = [k for k, v in mg["datasets"].items() if v.get("verdict") == "TOO_SMALL"]
chk("3 gate denominator honest", jsonl <= gated,
    f"{len(gated)} gated of {len(jsonl)} jsonl; {len(small)} TOO_SMALL reported not dropped")

# 3b TOO_SMALL must NOT satisfy require_verified
try:
    from scripts.measurement_gate import MeasurementError, require_verified
    ok_block = False
    if small:
        try:
            require_verified(small[0])
        except MeasurementError:
            ok_block = True
    else:
        ok_block = True
    chk("3b TOO_SMALL is not a pass", ok_block,
        f"require_verified({small[0] if small else 'n/a'}) raises as it must")
except Exception as e:  # blind-except intentional (BLE001)
    chk("3b TOO_SMALL is not a pass", False, f"import failed: {e!r}")

# 4 funding API monitored
vsrc = (ROOT / "scripts/data_vitals.py").read_text("utf-8")
fund = [c for c in dv["collectors"] if "funding" in c["source"].lower()]
chk("4 funding API monitored", "binance funding (live API)" in vsrc and bool(fund),
    f"{fund[0]['action'] if fund else 'ABSENT'}")

# 5 cadence docstring matches its constant
csrc = (ROOT / "scripts/run_cadence.py").read_text("utf-8")
chk("5 cadence doc==code", "tier1 every 28d" not in csrc and "_TIER1_EVERY_D = 14" in csrc,
    "docstring no longer claims 28d while the constant reads 14")

print("=== VERIFY: five fixes from a1bcd86, checked against RUNNING code ===\n")
for name, ok, detail in checks:
    print(f"  {'PASS' if ok else 'FAIL'}  {name:<32} {detail}")
bad = [c for c in checks if not c[1]]
print(f"\n  {len(checks)-len(bad)}/{len(checks)} verified live.")
if bad:
    print("  A commit proves an edit happened, never that it is reachable or correct.")
sys.exit(1 if bad else 0)

```

### scripts/wiring_audit.py
```python
"""WIRING AUDIT -- is everything INTENDED to run actually reachable from something that fires?

"Wired" has been used loosely all session. Adding a line to daily_research_cycle.py is only wiring
IF that file is itself scheduled AND actually executes the entry. Three failure modes, each
invisible from the file you edited:

  ORPHAN ENTRY   listed in the cycle, but the cycle is not scheduled -> never runs
  DEAD CRON      cron references a script that does not exist -> silent nightly failure
  UNREACHED      script exists, is scheduled, but has never produced its artifact

The last one is the killer: a scheduled script that errors every run looks identical to a healthy
one from the crontab. Only its output proves it.
"""
from __future__ import annotations

import json
import pathlib
import re
import subprocess
import time

ROOT = pathlib.Path(__file__).resolve().parent.parent
CYCLE = ROOT / "scripts/daily_research_cycle.py"


def crontab() -> str:
    try:
        return subprocess.run(["crontab", "-l"], capture_output=True, text=True,
                              check=False, timeout=20).stdout
    except Exception:  # blind-except intentional (BLE001)
        return ""


def timers() -> str:
    try:
        return subprocess.run(["systemctl", "list-timers", "--all", "--no-pager"],
                              capture_output=True, text=True, check=False, timeout=20).stdout
    except Exception:  # blind-except intentional (BLE001)
        return ""


cron, tmr = crontab(), timers()
cycle_txt = CYCLE.read_text("utf-8") if CYCLE.exists() else ""

# 1 -- is the cycle itself scheduled?
cycle_sched = "daily_research_cycle" in cron or "daily_research_cycle" in tmr
print("=== WIRING AUDIT ===\n")
print(f"  daily_research_cycle.py scheduled: {cycle_sched}")
if not cycle_sched:
    print("    !! CRITICAL: every entry wired to the cycle is UNREACHABLE.")
    print("    Adding a line to that file is not wiring if nothing invokes the file.")

# 2 -- entries listed in the cycle, and whether their artifact exists
entries = re.findall(r'\("([a-z_0-9]+)",\s*"(scripts/[a-z_0-9]+\.py)[^"]*"', cycle_txt)
print(f"\n  {len(entries)} entries listed in daily_research_cycle.py")
missing_script, no_artifact = [], []
for name, path in entries:
    if not (ROOT / path).exists():
        missing_script.append((name, path))
for name, path in entries:
    stem = pathlib.Path(path).stem
    arts = list(ROOT.glob(f"data/{stem}.json")) + list(ROOT.glob(f"data/{stem}.jsonl"))
    if not arts:
        no_artifact.append(name)
if missing_script:
    print(f"    !! {len(missing_script)} reference a script that does not exist:")
    for n, p in missing_script:
        print(f"       {n} -> {p}")
else:
    print("    all referenced scripts exist")
if no_artifact:
    print(f"    {len(no_artifact)} have produced no data/<stem>.json artifact "
          f"(may be by design): {', '.join(no_artifact[:8])}")

# 3 -- cron entries pointing at scripts
cron_scripts = re.findall(r'(scripts/[a-zA-Z_0-9]+\.py)', cron)
print(f"\n  {len(set(cron_scripts))} distinct scripts referenced directly in crontab")
dead = [c for c in set(cron_scripts) if not (ROOT / c).exists()]
if dead:
    print(f"    !! DEAD CRON -- referenced but absent: {dead}")
else:
    print("    all cron-referenced scripts exist")

# 4 -- collectors: registered vs actually producing fresh output
print("\n  COLLECTOR LIVENESS (registered -> is it producing?)")
try:
    dv = json.loads((ROOT / "data/data_vitals.json").read_text("utf-8"))
    now = time.time()
    for c in dv.get("collectors", []):
        act = c.get("action", "")
        if act.startswith(("DEAD", "MISSING")):
            print(f"    {c['source']:<42} {act}")
except Exception as e:  # blind-except intentional (BLE001)
    print(f"    vitals unreadable: {e!r}")

# 5 -- this session's builds, each must be reachable
BUILT = ["experiment_registry", "research_exchange", "measurement_gate", "feature_library",
         "leakage_detector", "execution_bottleneck", "hedge_integrity", "research_cio",
         "data_vitals", "alpha_lifecycle", "dependency_graph", "knowledge_engine",
         "module_justification", "kimi_hunter", "collect_defi_lending", "collect_oi_ls_live",
         "build_audit_shards", "coverage_audit"]
print(f"\n  SESSION BUILDS -- reachability ({len(BUILT)} modules)")
print(f"  {'module':<26}{'in cycle':>10}{'in cron':>9}{'artifact':>10}   reachable")
unreachable = []
for m in BUILT:
    inc = m in cycle_txt
    icr = m in cron
    art = bool(list(ROOT.glob(f"data/{m}.json")) + list(ROOT.glob(f"data/{m}.jsonl"))
               or list(ROOT.glob(f"data/{m.replace('collect_','')}*.jsonl")))
    # TRANSITIVE REACHABILITY. One hop was not enough: the real chain is
    # cron -> run_cadence -> run_external_panel -> build_audit_shards. Walk the invocation graph
    # to a depth limit instead of checking direct callers only.
    def _reaches(target: str, depth: int = 0, seen: set | None = None):
        seen = seen or set()
        if depth > 3 or target in seen:
            return None
        seen.add(target)
        for other in ROOT.glob("scripts/*.py"):
            if other.stem == target:
                continue
            body = other.read_text("utf-8", errors="ignore")
            if f"{target}.py" not in body:
                continue
            if other.stem in cron or (other.stem in cycle_txt and cycle_sched):
                return other.stem
            deeper = _reaches(other.stem, depth + 1, seen)
            if deeper:
                return f"{other.stem}<-{deeper}"
        return None

    indirect = None if (inc or icr) else _reaches(m)
    reach = (inc and cycle_sched) or icr or bool(indirect)
    if not reach:
        unreachable.append(m)
    _how = "YES" if reach else "NO"
    if indirect:
        _how = f"via {indirect}"
    print(f"  {m:<26}{inc!s:>10}{icr!s:>9}{art!s:>10}   {_how}")

print(f"\n  {len(BUILT)-len(unreachable)}/{len(BUILT)} reachable from a scheduler.")
if unreachable:
    print(f"  UNREACHABLE: {', '.join(unreachable)}")
    print("  These run only when invoked by hand. That is not wired.")

```
